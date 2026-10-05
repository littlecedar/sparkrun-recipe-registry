#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Make the PLE n-gram table of local-inference-lab/Qwen3.8-Flash-Next-NVFP4
# loadable by SGLang by rewriting it from packed NVFP4 into plain fp8 e4m3.
#
# The checkpoint stores 160 logical columns as 80 packed bytes plus one e4m3
# block scale per 16 columns. SGLang's Qwen4-Exp loader has an fp8 PLE path but
# no packed-NVFP4 unpack, so it dies with
#   RuntimeError: The size of tensor a (160) must match the size of tensor b (80)
# in copy_ple_rows_to_tp_embedding.
#
# This mod writes 16 replacement shards holding the unpacked fp8 tensors --
# exactly the width RadixArk's working checkpoint uses -- and sets
# text_config.ple_embedding_dtype = "float8_e4m3fn" so the engine selects its
# own already-tested fp8 path (qwen4_exp.py _ple_table_is_fp8). No engine source
# patch, no anchor fragility.
#
# IMPORTANT STRUCTURAL FACT (measured, cost me one failed boot): the 128 block
# scale tensors are present in the shard file HEADERS but ABSENT from the
# model.safetensors.index.json weight_map. Discovering them via the index finds
# 128 weights and zero scales. The loader works because it iterates each shard
# file's own tensors rather than trusting the index. So: enumerate via headers,
# and do not rewrite the index -- its entries still name the same files.
#
# Conversion (VERIFIED against an independent fp8 encoding of the same table;
# read README.md before changing any of it):
#     value = (E2M1[low nibble]  / 6) * block_scale   -> element 2i
#     value = (E2M1[high nibble] / 6) * block_scale   -> element 2i+1
#
# THE /6 IS NOT THE WHOLE SCALE, AND THIS IS WHY THE MODEL USED TO BE BROKEN.
# An earlier revision of this mod concluded `weight_scale_2` was inert metadata
# and did not apply it. The table conversion itself was, and remains, correct --
# the bug is only that nothing ever supplied the *other* half of the scale.
#
# Where the old reasoning went wrong. The probe scored candidate formulas with
# normed MAE against RadixArk's RAW stored table. That reference silently
# presupposes there is no engine-side per-tensor multiply: comparing raw-to-raw
# is the wrong SCOPE, because the engine multiplies the table by a buffer after
# loading it. Fix the reference's scope and the table's ranking inverts. (To be
# explicit about the instrument, since it is tempting to blame it and the blame
# does not hold: normed MAE normalised by the reference's magnitude scores |k-1|
# for a candidate off by scale k, so it DOES see a global scale. The reference
# was the error, not the metric.) The README says "the exporter recorded [g] but
# did not fold into the block scales" -- true -- and then reads it as "therefore
# inert", which conflates "the exporter did not fold it in" with "nothing
# applies it". The engine's buffer applies it.
#
# Measured with the right instrument (absolute relative-L2 between the two
# engine-FINAL tables, i.e. each after its own engine weight_scale multiply).
# For a pure scale error k, relative error is exactly |k-1|, which is why these
# land on the predicted values and the arithmetic cross-checks itself:
#     buffer = 1.0                relL2 = 5011.5  <- what shipped, and the bug
#     buffer = weight_scale_2     relL2 =    0.83 <- |1/6 - 1| = 0.833 exactly
#     buffer = 6*weight_scale_2   relL2 =    0.098 == the achievable floor
# The floor is what you get using RadixArk's own scalar (0.09814); the residual
# is two independent quantisations of one bf16 source disagreeing.
#
# Why 6: the engine multiplies the table by a per-tensor buffer
# (qwen4_exp.py:530 `register_buffer("weight_scale", torch.ones(1, bf16))`,
# applied at :585 and :1202). The true weight is c*s*g, this mod writes c*s/6,
# so the buffer must restore the factor this mod divided out:
#     emitted weight_scale = CODEBOOK_DIVISOR * weight_scale_2
# That is the invariant. If CODEBOOK_DIVISOR ever changes, this product has to
# change with it; a future reader who changes one without the other quietly
# reintroduces a 6x error on the path that feeds the residual stream.
#
# Why the mod must emit it rather than the checkpoint supplying it: the engine
# buffer matcher (qwen4_exp.py:1810) accepts only the exact name `weight_scale`.
# labquant stores the same number under `weight_scale_2`, which the matcher
# rejects; it falls through to the generic path and is dropped with a single
# warning ("Parameter ...ngram_embedding.weight_scale_2 not found while loading
# Qwen4-Exp VL weights"). The buffer then keeps its init value 1.0 and nothing
# else ever complains -- a ~5000x error that passes every load-time assertion.
# RadixArk ships the identical tensor under the accepted name, which is the only
# reason that checkpoint works.
#
# Output goes to the per-model runtime cache, which is HOST-LOCAL NVMe, and is
# reused across boots. The shared Hugging Face cache is never written.
# Idempotent. Fails closed on any deviation from the pinned contract.
#
# REQUIRES the server to run with --no-ple-offload-embedding: qwen4_exp.py
# raises "fp8 PLE auto-switch is unsupported with ple_offload_embedding".
#####################################################################

#####################################################################
# Metadata
#####################################################################
MOD_NAME="unpack-labquant-ple-nvfp4-to-fp8"
MOD_DESCRIPTION="Unpack labquant Qwen3.8-Flash-Next PLE table from NVFP4 to fp8"
MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
# Converts ~51 GB on a cold cache; give it room. Sparkrun honours MOD_TIMEOUT.
export TIMEOUT="${MOD_TIMEOUT:-2400}"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export USER_UID="$(stat -c '%u' /cache/runtime)"
export USER_GID="$(stat -c '%g' /cache/runtime)"

HF_HUB="${HF_HUB:-/cache/huggingface/hub}"
REPO="${MOD_LABQ_REPO:-local-inference-lab--Qwen3.8-Flash-Next-NVFP4}"
REVISION="${MOD_LABQ_REVISION:-7c4f1bc1a2d6847e0cbc01ac6b823f00251de8dd}"

# Same tree the config-schema mod builds. Both mods add to it; neither deletes it.
OUT_DIR="${MOD_LABQ_OUT:-/cache/runtime/labq-patched}"
OUT_DIR="${OUT_DIR%/}"
_p="${OUT_DIR#/cache/runtime/}"
if [ "${_p}" = "${OUT_DIR}" ] || [ -z "${_p}" ] || [ "${_p}" = "." ]; then
  echo "ERROR: OUT_DIR=${OUT_DIR} is not a dedicated subdirectory of /cache/runtime" >&2
  exit 1
fi
case "${_p}" in
  */*|*..*|*'$'*|*'`'*|*' '*|*[$'\t']*)
    echo "ERROR: OUT_DIR component '${_p}' is not a simple safe name" >&2; exit 1 ;;
esac

# Keep the unpack off the GPU: it would fight the server for the unified pool.
export CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
export TOKENIZERS_PARALLELISM=false

#####################################################################
# Helpers
#####################################################################
log()  { printf '%s [%s] %s\n' "$(date -Ins)" "${MOD_NAME}" "$*"; }
warn() { printf '%s [%s] WARNING: %s\n' "$(date -Ins)" "${MOD_NAME}" "$*" >&2; }
die()  { printf '%s [%s] ERROR: %s\n' "$(date -Ins)" "${MOD_NAME}" "$*" >&2; exit 1; }
reown() { chown -R "${USER_UID}:${USER_GID}" "${@}"; }

mkdir -p "${LOGDIR}" 2>/dev/null || true

#####################################################################
# Locate the snapshot
#####################################################################
[ -d "${HF_HUB}/models--${REPO}/snapshots/${REVISION}" ] || \
  die "pinned revision ${REVISION} not cached under ${HF_HUB}; this mod's contract is pinned to it, refusing to guess"
SNAP="$(readlink -f "${HF_HUB}/models--${REPO}/snapshots/${REVISION}")"
log "snapshot: ${SNAP}"
[ -f "${SNAP}/config.json" ] || die "no config.json in ${SNAP}"
mkdir -p "${OUT_DIR}" || die "cannot create ${OUT_DIR}"

#####################################################################
# Convert
#####################################################################
python3 - "${SNAP}" "${OUT_DIR}" <<'PY'
import json, os, re, struct, sys, time

import torch
from safetensors import safe_open
from safetensors.torch import save_file

SNAP, OUT = sys.argv[1], sys.argv[2]


def log(*a):
    print("[unpack-ple]", *a, flush=True)


def die(msg):
    raise SystemExit(f"[unpack-ple] ERROR: {msg}")


# ------------------------------------------------------------------
# VERIFIED conversion contract. See README.md; measured, not assumed.
# ------------------------------------------------------------------
E2M1 = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0]
CODEBOOK_DIVISOR = 6.0      # amax/6 convention: value = (codebook/6) * block_scale
PACK_FACTOR = 2             # two 4-bit values per byte
BLOCK = 16                  # one e4m3 scale per 16 elements along the last dim
EXPECTED_W = (2500012, 80)  # packed uint8
EXPECTED_S = (2500012, 10)  # e4m3 block scales
OUT_COLS = EXPECTED_W[1] * PACK_FACTOR   # 160, == ple_embed_dim / ngram_heads
ROW_CHUNK = 262_144         # rows per pass
EXPECTED_GROUPS = 128
EXPECTED_PLE_ONLY_FILES = 16

KEY = re.compile(r"^(.*)\.ngram_embedding\.shard_(\d+)\.(weight|weight_scale)$")

LUT = torch.tensor(E2M1 + [-m for m in E2M1], dtype=torch.float32)


def header_of(fname):
    """Read a safetensors file's own header. The index does NOT list the block
    scales, so the header is the only trustworthy inventory of a shard."""
    with open(os.path.join(SNAP, fname), "rb") as fh:
        n = struct.unpack("<Q", fh.read(8))[0]
        hdr = json.loads(fh.read(n))
    hdr.pop("__metadata__", None)
    return hdr


# ------------------------------------------------------------------
# Discover the PLE shards from the INDEX (only to find candidate files), then
# confirm the weight/scale pairing from each file's HEADER.
# ------------------------------------------------------------------
wm = json.load(open(os.path.join(SNAP, "model.safetensors.index.json")))["weight_map"]
files_with_ple = sorted({f for n, f in wm.items() if "ngram_embedding.shard_" in n})
log(f"index names {len([n for n in wm if 'ngram_embedding.shard_' in n])} PLE weights "
    f"across {len(files_with_ple)} shard files")

pairs, ple_dedicated = {}, {}
for fname in files_with_ple:
    hdr = header_of(fname)
    names = list(hdr)
    matched = {n: KEY.match(n) for n in names}
    hit = {n: m for n, m in matched.items() if m}
    if len(hit) != len(names):
        # file mixes PLE tensors with unrelated weights; converting it in place
        # would require rewriting those too, so skip and symlink it
        log(f"  {fname}: {len(names)} tensors, {len(hit)} PLE -> mixed file, left as symlink")
        continue
    per_shard = {}
    for n, m in hit.items():
        mod, shard, kind = m.group(1), int(m.group(2)), m.group(3)
        per_shard.setdefault((mod, shard), {})["scale" if kind == "weight_scale" else "weight"] = n
    incomplete = [k for k, v in per_shard.items() if len(v) != 2]
    if incomplete:
        die(f"{fname}: {len(incomplete)} PLE shards lack a weight/scale pair inside the "
            f"same file, e.g. {incomplete[:2]}")
    # dtype/shape contract
    for (mod, shard), d in per_shard.items():
        if tuple(hdr[d["weight"]]["shape"]) != EXPECTED_W:
            die(f"{fname}: {d['weight']} shape {hdr[d['weight']]['shape']} != {list(EXPECTED_W)}")
        if hdr[d["weight"]]["dtype"] != "U8":
            die(f"{fname}: packed weight dtype {hdr[d['weight']]['dtype']} != U8")
        if tuple(hdr[d["scale"]]["shape"]) != EXPECTED_S:
            die(f"{fname}: scale shape {hdr[d['scale']]['shape']} != {list(EXPECTED_S)}")
        pairs[(mod, shard)] = d
        pairs[(mod, shard)]["_file"] = fname
    ple_dedicated[fname] = sorted(per_shard)
    log(f"  {fname}: {len(per_shard)} complete packed PLE pairs -> will rewrite")

if len(pairs) != EXPECTED_GROUPS:
    die(f"expected {EXPECTED_GROUPS} packed PLE pairs, found {len(pairs)}")
if len(ple_dedicated) != EXPECTED_PLE_ONLY_FILES:
    die(f"expected {EXPECTED_PLE_ONLY_FILES} PLE-dedicated files, found {len(ple_dedicated)}")
log(f"contract OK: {len(pairs)} pairs in {len(ple_dedicated)} dedicated files, "
    f"weight {EXPECTED_W} U8, scale {EXPECTED_S} F8_E4M3")

# ------------------------------------------------------------------
# The n-gram per-tensor scale, under the name the engine reads.
#
# Discovered from shard HEADERS, not the index: like the block scales, this
# tensor is not listed in model.safetensors.index.json (measured: served index
# names 301529 tensors, shard headers hold 301530, and the single difference is
# exactly this tensor). Iterating the index would find nothing and we would
# conclude the checkpoint has no global scale -- which is how the previous
# revision came to call it absent/inert.
# ------------------------------------------------------------------
SCALE_SUFFIX = ".ngram_embedding.weight_scale_2"
EMIT_SUFFIX = ".ngram_embedding.weight_scale"
# Scan EVERY shard, not just the PLE-dedicated ones we rewrite: the scalar lives
# in model-00034-of-00036.safetensors, a mixed file this mod leaves as a symlink
# (measured, from the shard headers). Iterating `ple_dedicated` would find
# nothing and we would wrongly conclude the export has no global scale.
global_scales = {}
for fname in sorted(os.listdir(SNAP)):
    if not fname.endswith(".safetensors"):
        continue
    for n, m in header_of(fname).items():
        if n.endswith(SCALE_SUFFIX):
            global_scales[n] = (fname, m)
if not global_scales:
    die(f"no {SCALE_SUFFIX} tensor found in any PLE shard header. The engine "
        f"multiplies the n-gram table by a buffer named `weight_scale` that it "
        f"initialises to 1.0 (qwen4_exp.py:530). labquant stores the value as "
        f"`weight_scale_2`, which the engine's name matcher rejects, so without "
        f"this mod renaming it the table is applied ~1/g too large. Refusing to "
        f"emit a table we know will be mis-scaled.")

SCALE_FILE = "model-ple-ngram-weight-scale.safetensors"
written_scales = 0
for n, (fname, m) in sorted(global_scales.items()):
    layer_name = n[: -len(SCALE_SUFFIX)]
    emit_name = layer_name + EMIT_SUFFIX
    # list(), not tuple(): comparing `tuple(shape) != [1]` is ALWAYS true and
    # this exact line aborted the first boot that ran it.
    if list(m.get("shape") or []) != [1]:
        die(f"{n}: expected a 1-element scalar, got shape {m.get('shape')}")
    with safe_open(os.path.join(SNAP, fname), framework="pt") as f:
        g = f.get_tensor(n).to(torch.float32)
    # The invariant, and the reason for the multiply: the table below is written
    # as c*s/CODEBOOK_DIVISOR, so the buffer the engine multiplies by has to put
    # the divisor back. Changing CODEBOOK_DIVISOR without this product silently
    # rescales the path that feeds the residual stream.
    emit = (g * CODEBOOK_DIVISOR).to(torch.bfloat16)
    out_scale = os.path.join(OUT, SCALE_FILE)
    # Idempotent and self-healing. Checked independently of the shard-size skip
    # below: a cache built by the pre-fix version has already-unpacked shards
    # (so those are skipped) but no scalar file, and skipping here would keep
    # serving the broken tree forever.
    need = True
    if os.path.exists(out_scale):
        try:
            with safe_open(out_scale, framework="pt") as f:
                prev = f.get_tensor(emit_name).to(torch.float32) if emit_name in f else None
            need = prev is None or not torch.isclose(
                prev, emit.to(torch.float32), rtol=1e-3, atol=0).item()
        except Exception:
            need = True
    if need:
        tmp = out_scale + ".tmp"
        save_file({emit_name: emit.reshape(1)}, tmp, metadata={"format": "pt"})
        # safetensors' save_file creates 0600. Hooks can run as root while
        # `sglang serve` runs as uid 1000, and os.replace preserves the source's
        # mode, so without this the loader cannot read what we just wrote and the
        # run hangs on the health check looking like a slow boot. Same fix as the
        # shard write below.
        os.chmod(tmp, 0o644)
        os.replace(tmp, out_scale)
        written_scales += 1
    log(f"  {emit_name}: g={g.item():.9e} (as {SCALE_SUFFIX.lstrip('.')}) -> "
        f"emit {emit.item():.9e} = {CODEBOOK_DIVISOR}*g, bf16[1]"
        f"{' (written)' if need else ' (already correct)'}")


# ------------------------------------------------------------------
# Register the emitted scalar in model.safetensors.index.json.
#
# WITHOUT THIS THE ENTIRE FIX IS INERT, and it was inert for every boot up to
# now. The loader does not open every .safetensors in the directory:
# loader.py:536 globs `*.safetensors`, then loader.py:555 calls
# weight_utils.filter_duplicate_safetensors_files, whose last line (measured in
# the pinned build, weight_utils.py:760) is
#
#     hf_weights_files = [f for f in hf_weights_files if f in weight_files_in_index]
#
# That filter is active precisely because an index file EXISTS here (the
# early-return at :731 only fires when it does not). So a shard that is on disk
# but absent from the index is silently never read -- no warning, no error. The
# engine's `weight_scale` buffer keeps its init value 1.0, which is the exact
# failure this mod was written to fix, so the mod appeared to run correctly (its
# log line printed, its 178-byte file appeared with a fresh mtime) while
# contributing nothing.
#
# An earlier note here argued the loader "globs, therefore unindexed files load",
# citing that RadixArk ships 206 non-numbered `model-plefp8-*.safetensors` that
# load fine. That argument was worthless: all 206 ARE in RadixArk's index, so they
# load under either hypothesis. Measured on our own tree instead: labquant's index
# has 301529 names, my file is "ON DISK BUT NOT IN INDEX", and RadixArk's index
# DOES list `ngram_embedding.weight_scale` -> `model-plefp8-00009.safetensors`.
# The coherent checkpoint gets its scale because it is INDEXED.
#
# Note this is the same defect class as the bug being fixed -- a value sitting
# under a name the loader does not look for -- arriving one level up.
# ------------------------------------------------------------------
IDX = "model.safetensors.index.json"
idx_dst = os.path.join(OUT, IDX)

# ABLATION SWITCH, for the necessity test only. Setting MOD_PLE_SKIP_INDEX=1 writes
# the scalar shard but leaves it out of the index, reproducing the exact pre-fix
# state: file on disk, loader never opens it, engine buffer stays 1.0.
#
# Why a switch rather than editing the code back: the claim to be tested is
# "indexing this scalar is what makes labquant coherent". Everything else -- image,
# mods, flags, nodes -- has to be byte-identical between the two boots, and hand
# reverting this block risks changing something incidental and losing the
# comparison. This is also the only honest way to run it: the pre-fix state has to
# be *created* deliberately, because its historical artifacts cannot prove it. Every
# tree that could show whether boot G was indexed at test time was rewritten by my
# own later hand-runs, and an mtime records only the LAST write.
#
# Default is off. If this is ever left set, the mod silently ships the 5000x bug it
# exists to prevent, so the switch prints loudly and the verification block below is
# skipped with an explicit reason rather than passing vacuously.
SKIP_INDEX = os.environ.get("MOD_PLE_SKIP_INDEX", "") == "1"

# Read from OUT_DIR when a sibling mod has already replaced the symlink with a
# real file (mods/demote-labquant-narrow-mxfp8-to-bf16 removes the demoted scale
# entries from it). Reading SNAP there would silently undo its edits, and mods
# run in recipe order so the order is not ours to control.
idx_src = idx_dst if (os.path.isfile(idx_dst) and not os.path.islink(idx_dst)) \
    else os.path.join(SNAP, IDX)
if SKIP_INDEX:
    log(f"!! MOD_PLE_SKIP_INDEX=1: writing {SCALE_FILE} but NOT registering it in "
        f"{IDX}. This deliberately reproduces the pre-fix state for the necessity "
        f"ablation. The loader filters by the index (weight_utils.py:760), so this "
        f"shard will NOT be read and the engine's n-gram weight_scale buffer stays "
        f"at 1.0. DO NOT SHIP A TREE BUILT THIS WAY.")
else:
    idx = json.load(open(idx_src))
    wm = idx.get("weight_map")
    isinstance(wm, dict) or die(f"{IDX} has no weight_map dict")
    added_idx = 0
    for n in sorted(global_scales):
        emit_name = n[: -len(SCALE_SUFFIX)] + EMIT_SUFFIX
        if wm.get(emit_name) != SCALE_FILE:
            wm[emit_name] = SCALE_FILE
            added_idx += 1
    if os.path.islink(idx_dst):
        os.unlink(idx_dst)
    with open(idx_dst, "w") as fh:
        json.dump(idx, fh, indent=2)
        fh.write("\n")
    os.chmod(idx_dst, 0o644)
    log(f"{IDX}: registered {added_idx} n-gram scale entr{'y' if added_idx == 1 else 'ies'} "
        f"-> {SCALE_FILE} ({len(wm)} names total, read from "
        f"{'OUT_DIR (sibling mod already edited it)' if idx_src == idx_dst else 'SNAP'})")

# Verify the thing the loader will actually see, rather than trusting the write.
# This is the check whose absence let the bug survive a full day of boots: every
# prior check read the FILE, and the file was always fine.
if not os.path.isfile(idx_dst):
    die(f"{IDX} missing from {OUT} after the mods ran; the loader's index filter "
        f"cannot be predicted without it")
chk = json.load(open(idx_dst))["weight_map"]
probe = sorted(k[: -len(SCALE_SUFFIX)] + EMIT_SUFFIX for k in global_scales)[:1]
if SKIP_INDEX:
    if probe and probe[0] in chk:
        die(f"ablation requested but {probe[0]} IS in the index -- the tree would "
            f"load the fixed way and the ablation would be a no-op. Something "
            f"upstream registered it; refusing to report a meaningless result.")
    log(f"  ablation confirmed: {probe[0]} present on disk, absent from the index")
elif not probe or chk.get(probe[0]) != SCALE_FILE:
    die(f"index write did not take: {probe[0] if probe else '?'} not mapped to "
        f"{SCALE_FILE} in {idx_dst}")
# and the file it names must exist, or loader.py's own fail-fast (weight_utils.py
# :752-758) aborts the boot with "references N shard file(s) missing"
if not os.path.isfile(os.path.join(OUT, SCALE_FILE)):
    die(f"index now points at {SCALE_FILE} but that file is absent -- that turns a "
        f"silent miss into a hard boot failure")
# In ablation mode this line must NOT claim the index maps the name: it deliberately
# does not. Logging a false "verified" here would make the ablation indistinguishable
# from the fix in the very log a future reader uses to tell them apart.
if not SKIP_INDEX:
    log(f"  verified: index maps {probe[0]} -> {SCALE_FILE}, which exists")
else:
    log(f"  verified: {SCALE_FILE} exists on disk and is NOT indexed (ablation as asked)")


def unpack_pair(w_name, s_name, fname):
    rows = EXPECTED_W[0]
    out = torch.empty((rows, OUT_COLS), dtype=torch.float8_e4m3fn)
    fp = os.path.join(SNAP, fname)
    with safe_open(fp, framework="pt") as f:
        sw, ss = f.get_slice(w_name), f.get_slice(s_name)
        for a in range(0, rows, ROW_CHUNK):
            b = min(a + ROW_CHUNK, rows)
            w = sw[a:b]
            w = w.contiguous().view(torch.uint8) if w.dtype != torch.uint8 else w.contiguous()
            s = ss[a:b].contiguous().view(torch.float8_e4m3fn).to(torch.float32)
            lo, hi = w & 0x0F, (w >> 4) & 0x0F
            # low nibble -> element 2i, high nibble -> element 2i+1 (VERIFIED)
            nib = torch.stack([lo, hi], dim=-1).reshape(w.shape[0], -1)
            vals = LUT[nib.long()] * (s.repeat_interleave(BLOCK, dim=1) / CODEBOOK_DIVISOR)
            out[a:b] = vals.to(torch.float8_e4m3fn)
            del w, s, lo, hi, nib, vals
    return out


# ------------------------------------------------------------------
# Write replacement shards. The index is deliberately NOT rewritten: it maps
# tensor name -> file, and our files keep the same names and same filenames.
# ------------------------------------------------------------------
written, skipped, total_bytes = 0, 0, 0
t0 = time.time()
for fname in sorted(ple_dedicated):
    dst = os.path.join(OUT, fname)
    keys = ple_dedicated[fname]
    # An unpacked fp8 shard is ~1.5x the packed file, so size alone is a sound
    # "already converted" test. Never overwrite a file we did not create.
    want = len(keys) * EXPECTED_W[0] * OUT_COLS
    if os.path.exists(dst) and os.path.getsize(dst) > want:
        skipped += 1
        continue
    tensors = {}
    try:
        for key in keys:
            d = pairs[key]
            tensors[d["weight"]] = unpack_pair(d["weight"], d["scale"], fname)
        tmp = dst + ".tmp"
        save_file(tensors, tmp, metadata={"format": "pt"})
        os.replace(tmp, dst)
    finally:
        tensors.clear()
    written += 1
    total_bytes += os.path.getsize(dst)
    log(f"  {fname}: {len(keys)} shards unpacked")

log(f"converted {written} files ({total_bytes/1e9:.2f} GB written), "
    f"skipped {skipped} already-unpacked, in {time.time()-t0:.1f}s")

# ------------------------------------------------------------------
# Declare fp8 PLE so the engine picks its tested fp8 path.
# This is the actual trigger (qwen4_exp.py _ple_table_is_fp8).
# ------------------------------------------------------------------
cfg_dst = os.path.join(OUT, "config.json")
# Never write through a symlink: that would rewrite the node's HF snapshot.
if os.path.islink(cfg_dst):
    os.unlink(cfg_dst)
base_cfg = os.path.join(SNAP, "config.json")
cfg = json.load(open(cfg_dst if os.path.exists(cfg_dst) else base_cfg))
tc = cfg.get("text_config")
if not isinstance(tc, dict):
    die("config.json has no text_config dict; cannot set ple_embedding_dtype")
prev = tc.get("ple_embedding_dtype")
if prev != "float8_e4m3fn":
    tc["ple_embedding_dtype"] = "float8_e4m3fn"
    with open(cfg_dst, "w") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")
    log(f"text_config.ple_embedding_dtype: {prev!r} -> 'float8_e4m3fn'")
else:
    log("ple_embedding_dtype already float8_e4m3fn")

# ------------------------------------------------------------------
# Symlink everything we did not produce, so the tree is complete.
# ------------------------------------------------------------------
produced = set(ple_dedicated) | {"config.json", SCALE_FILE}
for entry in os.listdir(SNAP):
    if entry in produced:
        continue
    tgt = os.path.join(OUT, entry)
    if os.path.islink(tgt):
        os.unlink(tgt)
    elif os.path.exists(tgt):
        continue          # a real file owned by a sibling mod; leave it alone
    os.symlink(os.path.join(SNAP, entry), tgt)

log(f"patched tree complete at {OUT}")
PY

reown "${OUT_DIR}"
log "patched tree ready at ${OUT_DIR}"
