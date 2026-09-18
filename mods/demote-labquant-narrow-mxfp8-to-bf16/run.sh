#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# READ
#####################################################################
# Demote local-inference-lab/Qwen3.8-Flash-Next-NVFP4's narrow MXFP8
# projections -- in practice the Gated DeltaNet `in_proj_a` / `in_proj_b`
# pair -- from MXFP8 to plain BF16, so the server can boot at all.
#
# THE BLOCKER (work doc blocker (e), observed 2026-09-18 ~13:00):
#     ValueError: MXFP8 requires n >= 128 and k >= 128 for CUTLASS MXFP8.
#                 got m=8, n=96, k=2560
# `linear_attn.in_proj_a` and `.in_proj_b` are 48 rows each. The engine fuses
# them into `in_proj_ba` (qwen3_5.py: MergedColumnParallelLinear([48,48])), so the
# GEMM's output dimension is 96 -- and at TP=2, 48 per rank. Both are under the
# CUTLASS MXFP8 floor of 128. This is not a labquant quirk to argue with: RadixArk
# ships these same two projections BF16 (VERIFIED against its safetensors headers),
# i.e. the reference export for this model does not MXFP8 them either.
#
# WHY CONFIG ALONE CANNOT DO THIS
# `quantized_layers` keys by the COMPONENT names and would normally force fp8, but
# `ModelOptMixedPrecisionConfig._get_quant_method` checks `is_layer_skipped(...)`
# BEFORE consulting `quantized_layers` (modelopt_quant.py:294, vs :952). So an
# `ignore` entry naming the component does win. Verified on the pinned image with
# real objects rather than by reading, because the two spellings behave
# differently (probe_demote_plan4.py, 2026-09-18):
#
#   prefix model.layers.N.linear_attn.in_proj_ba
#     ignore = model.language_model.layers.N.linear_attn.in_proj_{a,b} -> Fp8LinearMethod
#     ignore = model.layers.N.linear_attn.in_proj_{a,b}                 -> UnquantizedLinearMethod
#   prefix model.language_model.layers.N.linear_attn.in_proj_ba
#     ignore = model.language_model...                                  -> UnquantizedLinearMethod
#     ignore = model.layers...                                          -> Fp8LinearMethod
#
# The engine's own prefix is the SHORT one: qwen4_exp.py:2008 rewrites checkpoint
# names with `name.replace("model.language_model.", "model.")` before matching, so
# `model.layers.N.linear_attn.in_proj_ba` is what reaches is_layer_skipped. This mod
# writes BOTH spellings for every layer, which is correct under either.
#
# WHY THE SHARD MUST BE REWRITTEN TOO, NOT JUST THE CONFIG
# This is the part that would otherwise ship a silent bug. With the layer
# unquantized the parameter is BF16, but the checkpoint still holds F8_E4M3 bytes.
# The engine's fallback loader is `param.data.copy_(loaded_weight)`
# (weight_utils.py:645), and torch happily casts e4m3 -> bf16. Measured on the
# pinned image: a byte 0x30 (== 2.0 in e4m3) landed in a BF16 parameter as 0.5 --
# the per-32-element ue8m0 block scale simply never got applied, because no one was
# asked to apply it. NO EXCEPTION WAS RAISED. A server built that way boots,
# answers, and benchmarks; it is just numerically wrong, and every number in this
# repo's benchmark tables would be a lie. So the mod decodes the MXFP8 pair to its
# true BF16 value on disk and drops the now-orphaned scale tensor.
#
# The scale must be dropped as well, or it has no destination parameter and the load
# dies at qwen4_exp.py:2140 (`abs(weight.item() - 1.0) < 1e-6`) -- and that assert's
# f-string cannot even print the tensor's name, because .item() raises first on a
# multi-element tensor (VERIFIED).
#
# EXACTNESS, not approximation
# e4m3 carries 4 significand bits; a ue8m0 scale is a power of two. So
# q * 2**(e-127) needs 4 significant bits and bf16 carries 8. The conversion is
# LOSSLESS for finite normal inputs; the mod asserts that per tensor on a sample
# instead of trusting the argument. It is not a quantisation change dressed up as a
# dequantisation: the BF16 tensor written here is the value the MXFP8 GEMM would
# have produced, bit for bit.
#
# SCOPE
# Only tensors that are (F8_E4M3 weight + uint8 weight_scale) AND whose fused output
# width falls below the floor at the configured TP. Today that is exactly 72
# tensors: in_proj_a + in_proj_b for the 36 linear_attn layers (the other 12 layers
# are full-attention and have no in_proj_a/b at all), all inside
# model-00035-of-00036.safetensors (2.79 GB). in_proj_qkv (2048), in_proj_z (2048),
# out_proj (2560) and every self_attn projection stay MXFP8, which is why this is
# not "we dequantised the attention". Cost: 4.72 MB of BF16 replaces 2.46 MB of
# MXFP8+scale, so +0.14 MB of weights per node; and see README for the one real
# runtime cost this incurs (the fused in_proj GEMM).
#
# Fails closed on any deviation from the pinned contract.
#####################################################################

#####################################################################
# Metadata
#####################################################################
MOD_NAME="demote-labquant-narrow-mxfp8-to-bf16"
MOD_DESCRIPTION="Demote labquant Qwen3.8-Flash-Next narrow MXFP8 GDN projections to BF16"
MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export TIMEOUT="${MOD_TIMEOUT:-1200}"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export USER_UID="$(stat -c '%u' /cache/runtime)"
export USER_GID="$(stat -c '%g' /cache/runtime)"

HF_HUB="${HF_HUB:-/cache/huggingface/hub}"
REPO="${MOD_LABQ_REPO:-local-inference-lab--Qwen3.8-Flash-Next-NVFP4}"
REVISION="${MOD_LABQ_REVISION:-7c4f1bc1a2d6847e0cbc01ac6b823f00251de8dd}"

# Same tree the other labquant mods build. Run AFTER
# mods/fix-labquant-modelopt-mixed-flat-schema, which is the only one that ever
# deletes it; this mod never does.
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

# CUTLASS MXFP8 refuses n < 128 (work doc blocker (e)). TP decides the per-rank n.
MXFP8_FLOOR="${MOD_MXFP8_FLOOR:-128}"
TP="${MOD_TENSOR_PARALLEL:-2}"

# Keep the rewrite off the GPU: it would fight the server for the unified pool.
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
# Locate the snapshot and the tree
#####################################################################
[ -d "${HF_HUB}/models--${REPO}/snapshots/${REVISION}" ] || \
  die "pinned revision ${REVISION} not cached under ${HF_HUB}; this mod is pinned to it, refusing to guess"
SNAP="$(readlink -f "${HF_HUB}/models--${REPO}/snapshots/${REVISION}")"
log "snapshot: ${SNAP}"

[ -d "${OUT_DIR}" ] || \
  die "${OUT_DIR} does not exist; this mod layers onto the tree built by
       mods/fix-labquant-modelopt-mixed-flat-schema and must run after it"
[ -f "${OUT_DIR}/config.json" ] || \
  die "${OUT_DIR}/config.json missing; keep the mod order config -> ple -> demote"

log "floor=${MXFP8_FLOOR} tp=${TP} out=${OUT_DIR}"

#####################################################################
# Convert
#####################################################################
python3 - "${SNAP}" "${OUT_DIR}" "${TP}" "${MXFP8_FLOOR}" <<'PY'
import json, os, re, struct, sys, time

import torch
from safetensors import safe_open
from safetensors.torch import save_file

SNAP, OUT, TP, FLOOR = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])

F8 = "F8_E4M3"
U8 = "U8"
BF = "BF16"

# Fusion map, taken from the engine's own stacked_params_mapping
# (qwen4_exp.py:1839-1842) -- not guessed. Fusing is what makes n small enough to
# trip the floor, so the floor test has to be applied to the FUSED width.
FUSE = {
    "in_proj_b": "in_proj_ba", "in_proj_a": "in_proj_ba",
    "in_proj_qkv": "in_proj_qkvz", "in_proj_z": "in_proj_qkvz",
    "gate_proj": "gate_up_proj", "up_proj": "gate_up_proj",
    "q_proj": "qkv_proj", "k_proj": "qkv_proj", "v_proj": "qkv_proj",
}
# is_layer_skipped raises ValueError if only SOME shards of a fused pair are
# ignored ("Detected some but not all shards of ... are quantized", VERIFIED), so a
# fused group is always demoted whole or not at all.
PAIRS = {"in_proj_ba": ("in_proj_b", "in_proj_a"),
         "in_proj_qkvz": ("in_proj_qkv", "in_proj_z"),
         "gate_up_proj": ("gate_proj", "up_proj"),
         "qkv_proj": ("q_proj", "k_proj", "v_proj")}

STAMP = ".labq-demote-stamp"
# in_proj_a/in_proj_b exist only on the linear_attn layers, which this revision
# has 36 of (the other 12 are full-attention; VERIFIED against shard 35's header:
# 72 in_proj_a weights + 72 in_proj_b weights covering layers 0..47 interleaved).
EXPECTED_NARROW = 72


def log(*a):
    print("[demote-mxfp8]", *a, flush=True)


def die(msg):
    raise SystemExit(f"[demote-mxfp8] ERROR: {msg}")


def warn(msg):
    # Named to match the bash helpers, but it must exist INSIDE the python heredoc too:
    # the contract-count check below calls it, and `warn` is a bash function the python
    # process cannot see. A launch died on exactly this NameError on 2026-09-18 because
    # the dry run never took the branch that calls it.
    print(f"[demote-mxfp8] WARNING: {msg}", flush=True)


def header_of(path):
    """A file's own header. The index does not list every tensor, so the header is
    the only trustworthy inventory of a shard."""
    with open(path, "rb") as fh:
        n = struct.unpack("<Q", fh.read(8))[0]
        hdr = json.loads(fh.read(n))
    meta = hdr.pop("__metadata__", None)
    return hdr, meta


# ------------------------------------------------------------------
# Discover the narrow MXFP8 projections from the INDEX (to find candidate files),
# then confirm dtype/shape from each file's HEADER.
# ------------------------------------------------------------------
idx_path = os.path.join(SNAP, "model.safetensors.index.json")
os.path.isfile(idx_path) or die(f"no {idx_path}")
wm = json.load(open(idx_path))["weight_map"]

# Leaves the floor test would never select but an operator can name explicitly, via
# MOD_DEMOTE_EXTRA_LEAVES (comma-separated). See the reasoning at the decision point
# below; the short version is that labquant MXFP8s the QSA indexer projection while
# RadixArk ships it BF16, and matching the reference export's placement is the control.
# Leaves beyond the CUTLASS floor that are demoted anyway, to match the reference
# export's placement. DEFAULT_ON holds the ones this project currently believes in and
# WHY; MOD_DEMOTE_EXTRA_LEAVES (or a one-line file at /cache/runtime/demote_extra_leaves)
# overrides the set completely -- set it to the empty string to get pure floor-test
# behaviour, or to a comma list to add more.
#
# Why index_qk_proj is on by default, and why that is a judgement call rather than a
# rule: it is 640x2560, comfortably ABOVE the floor, so nothing in the engine requires
# it to move. But labquant MXFP8s it while RadixArk ships the same tensor BF16 (VERIFIED
# from both checkpoints' safetensors headers: labquant has
# `layers.11.self_attn.indexer.index_qk_proj.weight` F8_E4M3 [640,2560] + a U8 scale,
# RadixArk has it BF16 [640,2560]), and both boots that got as far as CUDA-graph capture
# died inside the QSA prefill path -- `metadata.py:141 get_prefill_mqa_inputs`, which does
# `sequence_lengths.tolist()`, a D2H sync, during capture. Making this arm's placement
# match the reference export is the cheapest control for that. It is 12 tensors
# (one per full-attention layer) x ~1.6 MB, so the memory cost is ~19 MB per node.
#
# It is NOT proof of the cause. The crash is arguably a sglang bug (a D2H inside graph
# capture), and RadixArk's forward may simply take a different route through the same
# code. Treat "demoting it made it serve" as evidence about placement, not diagnosis.
# Why index_qk_proj is OFF by default, and what that costs us: it was ON, and the test
# it was designed for was run. Boot 11b2c8b941e89cb9 on 2026-09-18 22:05 loaded with
# `index_qk_proj` demoted to BF16 (VERIFIED from the live tree: 84 tensors demoted, 84
# scales dropped, 168 ignore entries, the projection present as BF16 [640,2560] with no
# surviving scale) and CUDA-graph capture died with the identical
# `Cannot copy between CPU and CUDA tensors during CUDA graph capture` in the QSA indexer.
# So MXFP8 placement of that projection is NOT what triggers (f). It is off because the
# arm should differ from the reference export only where the engine mechanically forces
# it to, and nothing forces this one. The knob stays: (f) is unresolved, this was the
# cheapest hypothesis, and a future bisect may want it.
DEFAULT_ON: set = set()
EXTRA_LEAVES_RAW = os.environ.get("MOD_DEMOTE_EXTRA_LEAVES", "")
_LEAF_FILE = "/cache/runtime/demote_extra_leaves"
if os.path.isfile(_LEAF_FILE):
    EXTRA_LEAVES_RAW = open(_LEAF_FILE).read().strip()
    log(f"extra leaves from {_LEAF_FILE}: {EXTRA_LEAVES_RAW!r}")
    # Deliberately NOT deleted here. pre_exec runs this script once per node against the
    # same host-mounted /cache/runtime, so a self-deleting file means the first node to
    # run gets one override and every later node boots with a different set of demoted
    # layers -- a split-brain TP group that would present as a numerical mystery.
EXTRA_LEAVES = DEFAULT_ON if EXTRA_LEAVES_RAW == "" else \
    {x.strip() for x in EXTRA_LEAVES_RAW.split(",") if x.strip()}
log(f"extra leaves (default-on {sorted(DEFAULT_ON)}) -> {sorted(EXTRA_LEAVES) or '(none)'}")

# Which shard files could contain a candidate. Derived from the leaf names we care about
# rather than hardcoded, so an opt-in leaf in a different shard is still found.
_cand = [r"\.in_proj_[ab]\.weight$"] + [rf"\.{re.escape(l)}\.weight$" for l in EXTRA_LEAVES]
cand_files = sorted({f for n, f in wm.items()
                     if any(re.search(p, n) for p in _cand)})
log(f"index lists candidate weights in {len(cand_files)} file(s): {cand_files}")

groups = {}          # (prefix, fused) -> {leaf: (n, k, fname)}
dtype_of = {}
for fname in cand_files:
    hdr, _ = header_of(os.path.join(SNAP, fname))
    for name, m in hdr.items():
        dtype_of[name] = m["dtype"]
    for name, m in hdr.items():
        if not name.endswith(".weight") or m["dtype"] != F8:
            continue
        key = name[: -len(".weight")]
        leaf = key.split(".")[-1]
        pre = key[: -len(leaf) - 1]
        fused = FUSE.get(leaf)
        if fused is None:
            # Unary (unfused) projection. Keep it only if named explicitly, so the
            # default path stays exactly the floor test it was before this option.
            if leaf not in EXTRA_LEAVES:
                continue
            fused = leaf
        n, k = m["shape"]
        sc = f"{key}.weight_scale"
        if dtype_of.get(sc) != U8:
            log(f"  {sc}: dtype {dtype_of.get(sc)} != {U8}; this group is NOT a "
                f"decodeable MXFP8 pair -> skipping the whole group")
            if (pre, fused) not in groups:
                groups[(pre, fused)] = "_skip"
            continue
        if groups.get((pre, fused)) == "_skip":
            continue
        groups.setdefault((pre, fused), {})[leaf] = (n, k, fname)

targets = {}         # fname -> {weight_name: scale_name}
ignore_entries = []
dropped_scales = []
for (pre, fused), members in sorted(groups.items()):
    if members == "_skip":
        continue
    need = PAIRS.get(fused)
    if need is None:
        # A projection the engine does not fuse (index_qk_proj and friends). It can only
        # be here because an operator named it in MOD_DEMOTE_EXTRA_LEAVES; the candidate
        # scan above is keyed on the same set, so an unnamed unary leaf never reaches
        # this branch.
        need = [fused] if fused in EXTRA_LEAVES else []
    if not need or any(l not in members for l in need):
        log(f"  {pre}.{fused}: members {sorted(members)} != expected {need}; skipping")
        continue
    # CUTLASS floor test, plus the explicitly-demoted leaf set (EXTRA_LEAVES, defined
    # above the scan with its reasoning). A fused group is always handled whole, because
    # is_layer_skipped raises "Detected some but not all shards ... are quantized" on a
    # half-demoted pair.
    n_fused = sum(members[l][0] for l in need)
    per_rank = n_fused // TP
    # Take whichever is smaller. The CUTLASS message reported `n=96` at TP=2 -- the
    # FUSED total, not 96/2 -- so which of the two the kernel actually checks is not
    # something to guess about. Demoting when either is under the floor is correct
    # under both readings and, for this pair (n_fused=96 < 128 anyway), makes the
    # decision independent of TP: it fires at TP=1, 2, 4 and 8 alike. If the kernel
    # only ever checks the fused total, a TP=4 run still demotes -- which costs a few
    # MB and is strictly safer than a boot that dies on the floor.
    narrow_n = min(n_fused, per_rank)
    opted = any(l in EXTRA_LEAVES for l in need)
    if narrow_n >= FLOOR and not opted:
        continue
    reason = "below CUTLASS floor" if narrow_n < FLOOR else "explicit opt-in"
    k = members[need[0]][1]
    if any(members[l][1] != k for l in need):
        die(f"{pre}.{fused}: members disagree on k "
            f"{ {l: members[l][1] for l in need} }; cannot fuse, refusing")
    for l in need:
        n, kk, fname = members[l]
        targets.setdefault(fname, {})[f"{pre}.{l}.weight"] = f"{pre}.{l}.weight_scale"
        # Both spellings. The engine's prefix is the short one (qwen4_exp.py:2008
        # rewrites model.language_model. -> model. before matching), but writing both
        # costs 96 strings and removes the guess entirely.
        for sp in (f"{pre}.{l}", pre.replace("model.language_model.", "model.") + f".{l}"):
            if sp not in ignore_entries:
                ignore_entries.append(sp)
        dropped_scales.append(f"{pre}.{l}.weight_scale")
    log(f"  {pre}.{fused}: fused n={n_fused}, per-rank n={per_rank}, "
        f"governing n={narrow_n} -> demote {len(need)} tensor(s) "
        f"({'+'.join(need)}) to BF16, drop their scales [{reason}]")

n_w = sum(len(v) for v in targets.values())
if n_w == 0:
    log("no projection is below the floor and none named; nothing to demote")
elif len(EXTRA_LEAVES):
    log(f"count includes {len(EXTRA_LEAVES)} explicitly-named leaf set(s); "
        f"the {EXPECTED_NARROW}-tensor contract check does not apply to that config")
elif n_w != EXPECTED_NARROW:
    # The contract for THIS pinned revision is in_proj_a+in_proj_b for the 36
    # linear_attn layers = 72 tensors (the other 12 layers are full-attention and
    # have no in_proj_a/b at all -- VERIFIED against shard 35's header). A different
    # count is either a new checkpoint or a wrong TP; either way say so loudly rather
    # than quietly writing a different tree than the work doc describes.
    warn(f"expected {EXPECTED_NARROW} narrow tensors for this revision at TP={TP}, "
         f"found {n_w}")
log(f"plan: {n_w} weight tensor(s) in {len(targets)} shard file(s), "
    f"{len(dropped_scales)} scale tensor(s) dropped, "
    f"{len(ignore_entries)} ignore entries")

# ------------------------------------------------------------------
# Decode + write. One shard at a time; a demoted tensor is small so the
# whole file is held in memory (2.8 GB shard -> ~3.5 GB peak with bf16 copies).
# ------------------------------------------------------------------
E4M3_MAX = 448.0


def demote_pair(w_u8, s_u8, name):
    """MXFP8 (e4m3 weight, ue8m0 scale) -> BF16, with the exactness claim checked."""
    q = w_u8.view(torch.float8_e4m3fn).to(torch.float32)
    n, k = q.shape
    blocks = k // 32
    if s_u8.shape != (n, blocks):
        die(f"{name}: scale shape {tuple(s_u8.shape)} != expected ({n}, {blocks})")
    mult = torch.pow(2.0, s_u8.to(torch.float32) - 127.0)     # ue8m0 -> power of two
    if torch.isnan(q).any():
        die(f"{name}: NaN in the e4m3 payload; this is not a finite MXFP8 tensor")
    if int((s_u8 == 255).sum()):
        die(f"{name}: scale byte 255 (NaN in e8m0) present; refusing to guess")
    scale = mult.repeat_interleave(32, dim=1)[:, :k]
    val = q * scale
    if not torch.isfinite(val).all():
        die(f"{name}: dequantised value is not finite (max e4m3 {E4M3_MAX} x "
            f"scale {float(scale.max())})")
    bf = val.to(torch.bfloat16)
    # The exactness argument: 4 significand bits (e4m3) x a power of two fits inside
    # bf16's 8. If that is ever false, this mod must stop rather than ship a quietly
    # re-quantised weight.
    err = (bf.to(torch.float32) - val).abs()
    denom = val.abs().amax().clamp_min(1e-30)
    rel = float((err.amax() / denom))
    if rel != 0.0:
        die(f"{name}: BF16 round-trip is NOT exact (max relative error {rel:.3e}). "
            f"The losslessness argument is wrong for this tensor; refusing.")
    return bf, rel


written, skipped, total_bytes = 0, 0, 0
t0 = time.time()
for fname, pairs in sorted(targets.items()):
    dst = os.path.join(OUT, fname)
    src = os.path.join(SNAP, fname)
    hdr, meta = header_of(src)
    # Idempotence: an already-demoted file has BF16 in_proj_a and no scales.
    if os.path.isfile(dst) and not os.path.islink(dst):
        dh, _ = header_of(dst)
        probe = [n for n in pairs if n in dh]
        if probe and all(dh[n]["dtype"] == BF for n in probe) \
           and not any(s in dh for s in pairs.values()):
            skipped += 1
            log(f"  {fname}: already demoted ({len(probe)} BF16 tensors), skipping")
            continue
        log(f"  {fname}: real file present but not demoted -> rewriting")
    tensors = {}
    with safe_open(src, framework="pt") as f:
        for name in hdr:
            if name in dropped_scales:
                continue
            t = f.get_tensor(name)
            wname = name if name in pairs else None
            if wname is not None:
                t, _ = demote_pair(t.view(torch.uint8),
                                   f.get_tensor(pairs[name]).view(torch.uint8),
                                   name)
            tensors[name] = t.contiguous()
    # Never write through a symlink: that would rewrite the shared HF snapshot.
    if os.path.islink(dst):
        os.unlink(dst)
    tmp = dst + ".tmp"
    save_file(tensors, tmp, metadata=({"format": "pt"} if meta is None else meta))
    os.replace(tmp, dst)
    written += 1
    total_bytes += os.path.getsize(dst)
    log(f"  {fname}: rewrote {len(pairs)} weight(s) to BF16, "
        f"dropped {len(pairs)} scale(s), {len(tensors)} tensors kept, "
        f"{total_bytes/1e9:.2f} GB")
    del tensors

log(f"shards: {written} written, {skipped} already-demoted, in {time.time()-t0:.1f}s")

# ------------------------------------------------------------------
# Index: the dropped scales ARE listed there (VERIFIED), so leaving them
# would advertise tensors that no longer exist.
# ------------------------------------------------------------------
IDX = "model.safetensors.index.json"
cfg_out = os.path.join(OUT, "config.json")
idx_src = os.path.join(SNAP, IDX)
idx_dst = os.path.join(OUT, IDX)
idx = json.load(open(idx_dst if os.path.isfile(idx_dst) and not os.path.islink(idx_dst)
                      else idx_src))
wm2 = idx.get("weight_map", {})
removed = [k for k in wm2 if k in set(dropped_scales)]
for k in removed:
    del wm2[k]
if os.path.islink(idx_dst):
    os.unlink(idx_dst)
with open(idx_dst, "w") as fh:
    json.dump(idx, fh, indent=2)
    fh.write("\n")
log(f"{IDX}: removed {len(removed)} scale entries "
    f"({len(wm2)} remain); e.g. {removed[:2]}")
if removed and len(removed) != len(dropped_scales):
    warn(f"index listed {len(removed)} of {len(dropped_scales)} dropped scales; "
         f"the rest were never indexed")

# ------------------------------------------------------------------
# config.json: the half that makes the engine build these BF16 at all.
# Read from OUT_DIR so a sibling mod's edits survive; never write a symlink.
# ------------------------------------------------------------------
if os.path.islink(cfg_out):
    os.unlink(cfg_out)
cfg = json.load(open(cfg_out if os.path.isfile(cfg_out) else os.path.join(SNAP, "config.json")))
qc = cfg.get("quantization_config")
isinstance(qc, dict) or die("config.json has no quantization_config dict")
ign = list(qc.get("ignore") or [])
have = set(ign)
added = [e for e in ignore_entries if e not in have]
qc["ignore"] = ign + added
cfg["quantization_config"] = qc
with open(cfg_out, "w") as fh:
    json.dump(cfg, fh, indent=2)
    fh.write("\n")
log(f"config.json quantization_config.ignore: {len(ign)} -> {len(qc['ignore'])} "
    f"(+{len(added)})")

with open(os.path.join(OUT, STAMP), "w") as fh:
    json.dump({"revision": os.path.basename(SNAP), "tp": TP, "floor": FLOOR,
               "demoted": n_w, "dropped_scales": len(dropped_scales),
               "ignore_added": len(added), "seconds": round(time.time() - t0, 1)},
              fh, indent=2)

# ------------------------------------------------------------------
# Symlink everything we did not produce, so the tree is complete.
# ------------------------------------------------------------------
produced = set(targets) | {"config.json", IDX, STAMP}
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
