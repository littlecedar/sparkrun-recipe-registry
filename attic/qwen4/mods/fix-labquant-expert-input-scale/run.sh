#!/usr/bin/env bash
# Replace labquant's routed-expert STATIC activation scales for the coherence bisect.
#
# WHAT IS BEING TESTED
# Both exports declare input_activations.dynamic = False for the routed experts
# (measured from quantization_config.config_groups: labquant
# group_nvfp4_routed_experts, radixark group_0), so the NVFP4 expert GEMMs quantise
# activations with per-tensor STATIC scales loaded from <expert>.<proj>.input_scale.
# modelopt_quant.py:2436-2439, on the exact backend this recipe selects
# (--moe-runner-backend flashinfer_cutlass), collapses all 512 per-expert scales to
# ONE scalar per layer per projection:
#
#     if self.enable_flashinfer_cutlass_moe or self.enable_flashinfer_trtllm_moe:
#         w13_input_scale = layer.w13_input_scale.max().to(torch.float32)
#         w2_input_scale  = layer.w2_input_scale.max().to(torch.float32)
#
# So the value the kernel actually receives is a MAX over experts, which means a
# single outlier governs a whole layer. Measured over the 73,728 shared
# input_scale tensors: labquant max 1.95238 vs RadixArk max 0.0288 (~67x), 26.6%
# differ by more than 3.16x, and labquant's are systematically larger with some
# expert down_proj values ~200x apart (0.196 vs 0.00097).
#
# Why that produces exactly what we see: an activation scale ~67x too large makes
# every FP4 code round toward zero, so each expert MLP contributes ~nothing while
# every expert WEIGHT stays byte-correct. That is why the dense-MXFP8 checks
# (corr 0.99965), the routed-WEIGHT checks (corr 0.995-0.998) and the PLE table
# check (0.994) all passed and the model still serves token soup. It is also the
# only hypothesis that survives both null results so far: removing the draft head
# and switching the fp8 GEMM backend both leave the expert activation scale alone.
#
# THIS IS A DIAGNOSTIC, NOT A FIX. RadixArk's values are legitimate for RadixArk's
# quantisation run (producer 0.46.0) and NOT automatically correct for labquant's
# (0.39.0.dev290). Coherent output would prove the expert activation scale is the
# broken component; the real fix would then be to recalibrate or clamp, not to
# borrow another checkpoint's numbers. Do not merge this mod as a fix.
#
# Modes, via MOD_ISCALE_MODE:
#   radixark     (default) copy RadixArk's value for every shared name. Tests
#                "is the activation scale the broken thing at all".
#   clamp-median replace every value with the median of labquant's OWN values. Keeps
#                labquant's own calibration magnitude but removes outliers, so the
#                per-layer max becomes a representative number instead of a freak.
#                If this also restores coherence, the defect is the OUTLIERS under a
#                max-reduction, not the absolute magnitudes -- a materially different
#                (and much easier) fix.
#   report       change nothing, print the before/after per-layer maxima only.
#
# Two modes that both restore coherence with different causes is a real possible
# outcome; that is why both are built in rather than picking one and hoping.
#
# SCOPE / COST
# All 73,728 expert input_scale tensors live in ONE file,
# model-00036-of-00036.safetensors: 9,669,968 bytes, of which the data region is
# 294,912 bytes (73,728 x F32 scalars) and the rest is the header. Rewriting it
# outright is trivial and takes well under a second. The tensor NAMES are unchanged,
# so model.safetensors.index.json stays valid and is not touched.
set -uo pipefail

MODE="${MOD_ISCALE_MODE:-radixark}"
OUT_DIR="${MOD_LABQ_OUT:-/cache/runtime/labq-patched}"
OUT_DIR="${OUT_DIR%/}"
# HF cache dir naming is `models--<org>--<repo>`, not `<org>--<repo>`. Getting
# this wrong is not a crash-class error, it is worse: the check below fires with
# a clear message rather than silently finding zero reference tensors, which is
# the failure mode that would have made the whole arm a no-op that "passed".
RADIX_REPO="${MOD_ISCALE_RADIX_REPO:-models--RadixArk--Qwen3.8-Flash-Next-NVFP4}"
RADIX_REV="${MOD_ISCALE_RADIX_REV:-7b719225242aacd3dbd3f9407468c2ee9a9d2594}"
SHARD="model-00036-of-00036.safetensors"

log() { echo "[$(date -u +%H:%M:%S)] [fix-labquant-expert-input-scale] $*"; }

log "mode=$MODE out=$OUT_DIR"
[ -d "$OUT_DIR" ] || { log "FATAL: $OUT_DIR does not exist"; exit 1; }
SRC_SHARD="$OUT_DIR/$SHARD"
[ -e "$SRC_SHARD" ] || { log "FATAL: $SRC_SHARD missing"; exit 1; }
SNAP="/cache/huggingface/hub/$RADIX_REPO/snapshots/$RADIX_REV"
[ -d "$SNAP" ] || { log "FATAL: RadixArk snapshot not mounted at $SNAP"; exit 1; }

export MODE OUT_DIR SNAP SHARD
python3 - <<'PY'
import json, os, struct, statistics, sys

mode = os.environ["MODE"]
out_dir = os.environ["OUT_DIR"]
snap = os.environ["SNAP"]
shard = os.environ["SHARD"]
TARGET_SUFFIX = ".input_scale"


def resolve(p):
    """Served-tree entries are symlinks whose targets are CONTAINER paths, so
    resolve() has to work both inside a container (target exists) and from a host
    (needs the /cache -> /home/red/.cache remap)."""
    r = os.path.realpath(p)
    if os.path.exists(r):
        return r
    for a, b in {"/cache/huggingface": "/home/red/.cache/huggingface",
                 "/cache/sparkrun": "/home/red/.cache/sparkrun"}.items():
        if r.startswith(a):
            alt = b + r[len(a):]
            if os.path.exists(alt):
                return alt
    return r


def read_header(path):
    with open(path, "rb") as fh:
        n = struct.unpack("<Q", fh.read(8))[0]
        h = json.loads(fh.read(n))
    h.pop("__metadata__", None)
    return h, 8 + n


def is_target(name, meta):
    """Routed-expert static activation scale.

    Shape is the empty tuple, NOT (1,): these scalars are stored as rank-0 F32.
    A filter written as `shape != [1]` silently matches nothing, and the natural
    misreading of an empty result is "this checkpoint has no input_scale" -- which
    is a wrong conclusion that looks like a finding. Check dtype and shape
    explicitly and count what was skipped.
    """
    return (name.endswith(TARGET_SUFFIX) and ".experts." in name
            and meta.get("dtype") == "F32" and list(meta.get("shape") or []) == [])


# ---------------------------------------------------------------- read labquant
src_path = os.path.join(out_dir, shard)
src_real = resolve(src_path)
hdr, hdr_len = read_header(src_real)
targets = {k: v for k, v in hdr.items() if is_target(k, v)}
n_skipped_iscale = sum(1 for k, v in hdr.items()
                       if k.endswith(TARGET_SUFFIX) and k not in targets)
print(f"  shard {shard}: {len(hdr)} tensors, {len(targets)} routed-expert "
      f"input_scale targets, {n_skipped_iscale} .input_scale names SKIPPED "
      f"(not expert+rank-0-F32 -- inspect if nonzero)")
if not targets:
    print("  FATAL: no targets matched. Before concluding anything, verify the "
          "dtype/shape filter against the actual header rather than assuming.")
    sys.exit(1)

vals = {}
with open(src_real, "rb") as fh:
    for k, m in targets.items():
        s, e = m["data_offsets"]
        fh.seek(hdr_len + s)
        vals[k] = struct.unpack("<f", fh.read(4))[0]


def per_layer_max(d, suffix):
    """Engine's reduction: max over experts, per layer, per projection group."""
    import re
    out = {}
    for k, v in d.items():
        if not k.endswith(suffix):
            continue
        m = re.search(r"layers\.(\d+)\.", k)
        if m:
            out.setdefault(int(m.group(1)), []).append(v)
    return {L: max(vs) for L, vs in out.items()}


before_w13 = per_layer_max(vals, ".gate_proj.input_scale")
before_w2 = per_layer_max(vals, ".down_proj.input_scale")
print(f"  BEFORE: global max input_scale = {max(vals.values()):.6g}, "
      f"median = {statistics.median(vals.values()):.6g}")
print(f"  BEFORE per-layer max (engine's w13 proxy, gate_proj): "
      f"min={min(before_w13.values()):.6g} median={statistics.median(before_w13.values()):.6g} "
      f"max={max(before_w13.values()):.6g}")
print(f"  BEFORE per-layer max (w2 proxy, down_proj): "
      f"min={min(before_w2.values()):.6g} median={statistics.median(before_w2.values()):.6g} "
      f"max={max(before_w2.values()):.6g}")

if mode == "report":
    print("  mode=report: nothing written")
    sys.exit(0)

# ---------------------------------------------------------------- replacements
# An earlier revision of this block was deleted and rewritten, which silently
# removed the code that BUILT `ref` and `med` while leaving the code that READ
# them. That produced NameError at line 101 -- invisible for hours because the
# mod's exit status was swallowed (see the shell wrapper above). Rebuilding both
# here, and note the order: `med` is used by clamp-median, `ref` by radixark.
ref = {}
if mode == "radixark":
    for f in sorted(os.listdir(snap)):
        if not f.endswith(".safetensors"):
            continue
        h, hl = read_header(resolve(os.path.join(snap, f)))
        want = {k: v for k, v in h.items() if is_target(k, v)}
        if not want:
            continue
        with open(resolve(os.path.join(snap, f)), "rb") as fh:
            for k, m in want.items():
                s, e = m["data_offsets"]
                fh.seek(hl + s)
                ref[k] = struct.unpack("<f", fh.read(4))[0]
    print(f"  RadixArk reference: {len(ref)} routed-expert input_scale tensors "
          f"read from {snap}")
    if not ref:
        print("  FATAL: RadixArk reference is empty. Proceeding would leave every "
              "value untouched and look exactly like a successful no-op run.")
        sys.exit(1)
    missing = [k for k in vals if k not in ref]
    if missing:
        print(f"  WARNING: {len(missing)} labquant names have no RadixArk "
              f"counterpart; they keep their original value, so this arm only "
              f"PARTIALLY tests the hypothesis. Examples: {missing[:3]}")

med = statistics.median(vals.values())

new = {}
for k in vals:
    if mode == "radixark" and k in ref:
        new[k] = ref[k]
    elif mode == "clamp-median":
        new[k] = med
    else:
        new[k] = vals[k]
replaced = sum(1 for k in vals if new[k] != vals[k])
if replaced == 0 and mode != "report":
    # NOT a failure. `new[k]` is by construction the target value for every k, so
    # replaced == 0 means the checkpoint already holds the targets, i.e. this tree
    # was fixed by a previous run and the mod is correctly doing nothing. Aborting
    # here would make a second boot of an already-patched tree die -- a fix that
    # cannot be re-run is worse than no fix. The genuinely-broken case (empty
    # reference) is caught explicitly above, where `ref` is built.
    print(f"  all {len(vals)} values already at their target; nothing to change "
          f"(idempotent re-run). If this is the FIRST run on a fresh tree, that is "
          f"suspicious -- check that the reference is the checkpoint you expect.")

after_w13 = per_layer_max(new, ".gate_proj.input_scale")
after_w2 = per_layer_max(new, ".down_proj.input_scale")
print(f"  AFTER per-layer max (w13 proxy): min={min(after_w13.values()):.6g} "
      f"median={statistics.median(after_w13.values()):.6g} max={max(after_w13.values()):.6g}")
print(f"  AFTER per-layer max (w2 proxy): min={min(after_w2.values()):.6g} "
      f"median={statistics.median(after_w2.values()):.6g} max={max(after_w2.values()):.6g}")
print(f"  values changed: {replaced} of {len(vals)}")

# ------------------------------------------------------------------- write it
# Copy-on-write, never through the symlink: this shard is a symlink into the shared
# HF snapshot blob, and writing there would corrupt it for every other consumer.
import torch
from safetensors.torch import save_file

DT = {"BF16": torch.bfloat16, "F32": torch.float32, "F16": torch.float16,
      "F8_E4M3": torch.float8_e4m3fn, "F8_E5M2": torch.float8_e5m2,
      "U8": torch.uint8, "I8": torch.int8, "I32": torch.int32, "I64": torch.int64}
unknown = {m["dtype"] for k, m in hdr.items() if k not in targets
           and m["dtype"] not in DT}
if unknown:
    print(f"  FATAL: shard contains dtype(s) {sorted(unknown)} this mod cannot "
          f"round-trip. Add them to DT rather than silently dropping tensors -- a "
          f"partial rewrite would load fine and be wrong.")
    sys.exit(1)

tensors = {}
for k, m in hdr.items():
    if k in targets:
        tensors[k] = torch.tensor(new[k], dtype=torch.float32)
        continue
    s, e = m["data_offsets"]
    dt = DT[m["dtype"]]
    with open(src_real, "rb") as fh:
        fh.seek(hdr_len + s)
        buf = fh.read(e - s)
    tensors[k] = torch.frombuffer(bytearray(buf), dtype=dt).view(tuple(m["shape"]))
assert len(tensors) == len(hdr), f"{len(tensors)} != {len(hdr)}: a tensor was dropped"

# Replace the symlink with a real file (the same pattern
# mods/unpack-labquant-ple-nvfp4-to-fp8 uses for the shards it rewrites).
tmp = src_path + ".tmp"
save_file(tensors, tmp, metadata={"format": "pt"})
# safetensors' save_file creates the file 0600. Pre-serve hooks run as ROOT inside
# the container while sglang serve runs as uid 1000, so a 0600 file owned by root
# is UNREADABLE by the process that has to load it -- the run hangs waiting for a
# healthy server and the failure looks like a slow boot, not a permissions bug.
# os.replace preserves the source's mode, so chmod the tmp file before renaming.
os.chmod(tmp, 0o644)
if os.path.islink(src_path):
    os.unlink(src_path)
os.replace(tmp, src_path)
st = os.stat(src_path)
print(f"  wrote {src_path} ({st.st_size} bytes, real file, {len(tensors)} tensors, "
      f"mode {oct(st.st_mode & 0o777)}, uid {st.st_uid})")
if not (st.st_mode & 0o004):
    print("  FATAL: output is not world-readable; sglang serve runs as uid 1000 and "
          "would not be able to load it.")
    sys.exit(1)

# ------------------------------------------------- verify by reading it back
h2, hl2 = read_header(src_path)
bad = 0
with open(src_path, "rb") as fh:
    for k in list(targets)[:2000]:
        s, e = h2[k]["data_offsets"]
        fh.seek(hl2 + s)
        got = struct.unpack("<f", fh.read(4))[0]
        if got != new[k]:
            bad += 1
print(f"  read-back check on 2000 sampled tensors: {bad} mismatches")
assert bad == 0, "written file does not read back"
print("  OK")
PY

# ------------------------------------------------------------------- exit status
# MUST propagate python's status. `set -uo pipefail` does NOT include -e, and the
# `log "done"` line below the heredoc previously reset $? to 0: a mod that died
# with a traceback still reported SUCCESS to sparkrun, which then happily served
# unmodified weights while every log said the fix had been applied. That cost
# hours of trusting a boot that had changed nothing. Anything that can silently
# turn a failed fix into a no-op is a defect in its own right.
PY_STATUS=$?
log "done (python exit=$PY_STATUS)"
exit $PY_STATUS
