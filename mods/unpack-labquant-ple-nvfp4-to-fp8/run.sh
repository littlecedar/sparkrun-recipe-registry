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
# weight_scale_2 is INERT for this tensor and is not applied -- see README.md.
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
# Never write through a symlink: that would rewrite the shared HF snapshot.
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
produced = set(ple_dedicated) | {"config.json"}
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
