#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Make local-inference-lab/Qwen3.8-Flash-Next-NVFP4 loadable under SGLang's
# `--quantization modelopt_mixed`.
#
# See README.md in this directory for the full mechanism. Short version: the
# checkpoint's quantization metadata is FLAT in both config.json and
# hf_quant_config.json, but SGLang's get_quant_config() only accepts the flat
# shape when it can use the inline config.json block. For modelopt_mixed it
# falls through to hf_quant_config.json unless `quantized_layers` is present
# AND one of `kv_cache_quant_algo`/`kv_cache_scheme` is present. This
# checkpoint has the former but neither KV key, so SGLang falls through to a
# file it then indexes as config["quantization"]["quant_algo"] and dies with
# KeyError: 'quantization' during model load.
#
# Fix: declare kv_cache_quant_algo: null in a patched COPY of config.json.
# "null" is truthful -- the model card states there is no KV-cache quantization
# metadata and we serve bf16 KV. That keeps the loader on the inline path,
# which ModelOptMixedPrecisionConfig.from_config() accepts.
#
# The patched tree is built in /cache/runtime (sparkrun's per-model runtime
# cache, already a RW bind mount) as a directory of symlinks to the real
# snapshot with one real patched config.json. The shared Hugging Face cache is
# NEVER written. Idempotent; safe to re-run; never overwrites anything it did
# not create.
#
# Exposes the result as the recipe default {patched_model_path}.
#####################################################################

#####################################################################
# Metadata
#####################################################################
MOD_NAME="fix-labquant-modelopt-mixed-flat-schema"
MOD_DESCRIPTION="Patch labquant Qwen3.8-Flash-Next quant config for modelopt_mixed"
MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
TIMEOUT="${MOD_TIMEOUT:-180}"
LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"

# The checkpoint, as it appears INSIDE the container. sparkrun bind-mounts the
# host's ~/.cache/huggingface at /cache/huggingface.
HF_HUB="${HF_HUB:-/cache/huggingface/hub}"
REPO="${MOD_LABQ_REPO:-local-inference-lab--Qwen3.8-Flash-Next-NVFP4}"
# Pin the revision we validated against. Override with MOD_LABQ_REVISION.
REVISION="${MOD_LABQ_REVISION:-7c4f1bc1a2d6847e0cbc01ac6b823f00251de8dd}"

OUT_DIR="${MOD_LABQ_OUT:-/cache/runtime/labq-patched}"
OUT_DIR="${OUT_DIR%/}"

# Guard: this mod rebuilds OUT_DIR with `rm -rf`, so only ever allow a single,
# dedicated, non-empty path component under the known-writable cache root.
_p="${OUT_DIR#/cache/runtime/}"
if [ "${_p}" = "${OUT_DIR}" ] || [ -z "${_p}" ] || [ "${_p}" = "." ]; then
  die "OUT_DIR=${OUT_DIR} is not a dedicated subdirectory of /cache/runtime; refusing to rm -rf it"
fi
case "${_p}" in
  */*|*..*|"*$"*|*'$'*|*'`'*|*' '*|*[$'\t']*) die "OUT_DIR component '${_p}' is not a simple safe name" ;;
esac

USER_UID="$(stat -c '%u' /cache/runtime)"
USER_GID="$(stat -c '%g' /cache/runtime)"

#####################################################################
# Helpers
#####################################################################
linkify_all() {
  # Refresh the symlinks this mod owns and nothing else.
  #
  # `ln -sfn` UNLINKS an existing regular file and puts a link in its place -- verified
  # directly, a 3.2 GB file became a 13-byte symlink with no error. So it must never be
  # pointed at a regular file in OUT_DIR: those belong to sibling mods, above all the
  # unpacked fp8 PLE shards from mods/unpack-labquant-ple-nvfp4-to-fp8, and clobbering
  # them would make the engine read PACKED NVFP4 where it expects fp8 -- a silent,
  # wrong-answers failure rather than a loud one.
  #
  # Policy: refresh links (ours), leave regular files (theirs), create what is missing.
  local f b n_link=0 n_keep=0 n_new=0
  for f in "${SNAP}"/*; do
    b="$(basename "$f")"
    [ "$b" = "config.json" ] && continue
    if [ -L "${OUT_DIR}/${b}" ]; then
      ln -sfn "$f" "${OUT_DIR}/${b}"; n_link=$((n_link+1))
    elif [ -e "${OUT_DIR}/${b}" ]; then
      n_keep=$((n_keep+1))          # regular file owned by a sibling mod: never touch
    else
      ln -s "$f" "${OUT_DIR}/${b}"; n_new=$((n_new+1))
    fi
  done
  log "linked tree: ${n_link} links refreshed, ${n_new} created, ${n_keep} regular files preserved"
}

log()  { echo "[mod:${MOD_NAME}] $*"; }
warn() { echo "[mod:${MOD_NAME}] WARNING: $*" >&2; }
die()  { echo "[mod:${MOD_NAME}] ERROR: $*" >&2; exit 1; }

reown() { chown -R "${USER_UID}:${USER_GID}" "${@}"; }

mkdir -p "${LOGDIR}" 2>/dev/null || true

#####################################################################
# Locate the snapshot
#####################################################################
SNAP=""
if [ -d "${HF_HUB}/models--${REPO}/snapshots/${REVISION}" ]; then
  SNAP="${HF_HUB}/models--${REPO}/snapshots/${REVISION}"
else
  # Fall back to whatever single snapshot exists, but say so loudly: an
  # unverified revision is how we got a weights-free 45 MB snapshot once.
  for d in "${HF_HUB}/models--${REPO}/snapshots"/*/; do
    [ -d "$d" ] || continue
    SNAP="${d%/}"
    break
  done
  [ -n "${SNAP}" ] && warn "requested revision ${REVISION} not cached; using ${SNAP} instead"
fi

[ -n "${SNAP}" ] || die "no snapshot for models--${REPO} under ${HF_HUB}. Run sparkrun's model sync first."
SNAP="$(readlink -f "${SNAP}")"
log "snapshot: ${SNAP}"

#####################################################################
# Sanity gate: refuse to build a patched tree over a weights-free snapshot.
# This exact failure (main -> 45 MB, no shards) already cost us a boot.
#####################################################################
SHARDS="$(find "${SNAP}" -maxdepth 1 -name '*.safetensors' | wc -l | tr -d ' ')"
[ "${SHARDS}" -ge 8 ] || die "snapshot ${SNAP} has only ${SHARDS} safetensors shards; refusing to build a patched tree that cannot load. Check the pinned revision."
log "found ${SHARDS} safetensors shards"

[ -f "${SNAP}/config.json" ] || die "no config.json in ${SNAP}"
[ -f "${SNAP}/hf_quant_config.json" ] || warn "no hf_quant_config.json; the flat-schema fall-through may not apply"

# A tree assembled for a DIFFERENT snapshot must be rebuilt; a tree that is merely
# re-encountered should be refreshed in place. Without this distinction the original
# `rm -rf` ran on every boot -- which silently deleted the 51.2 GB of fp8 PLE shards
# that mods/unpack-labquant-ple-nvfp4-to-fp8 builds into this same directory, forcing
# a full 51 GB re-conversion on every single launch.
#
# The stamp deliberately lives OUTSIDE OUT_DIR. While the stamp lived inside the tree
# it stamped, a tree built before stamping existed (or one whose stamp was removed)
# could not be recognised, so the very next boot took the destructive branch and
# destroyed good work -- exactly the failure this block exists to prevent. Keeping the
# identity marker outside the wiped directory makes "is this current?" independent of
# "wipe this".
STAMP_DIR="${MOD_LABQ_STAMP_DIR:-/cache/runtime/.labq-stamps}"
STAMP="${STAMP_DIR}/$(printf '%s' "${OUT_DIR}" | tr -c 'A-Za-z0-9' '_')"
WANT_STAMP="${SNAP}"

# Second, independent guard: never destroy converted output we did not author. Real
# (non-symlink) .safetensors in OUT_DIR mean mods/unpack-labquant-ple-nvfp4-to-fp8 has
# been here; that is 51 GB of work, so require an explicit opt-in to discard it.
#
# `mkdir -p` here is NOT cosmetic. With `set -euo pipefail` a `find` on a directory
# that does not exist exits 1, and because it is the first element of a pipeline that
# failure propagates through `| wc -l | tr -d ' '`: the whole mod dies on a fresh node
# where labq-patched has never been created. Observed on 10.0.4.34 (dry run, no
# persisted runtime cache) as EXIT=1 immediately after "found 36 safetensors shards".
# Any node whose /cache/runtime was cleared -- a new node, or a model-key cache
# eviction -- would have hit this on its very first boot.
mkdir -p "${OUT_DIR}" || die "cannot create ${OUT_DIR}"
REAL_SHARDS="$(find "${OUT_DIR}" -maxdepth 1 -name '*.safetensors' -type f 2>/dev/null | wc -l | tr -d ' ')"
if [ -f "${STAMP}" ] && [ "$(cat "${STAMP}" 2>/dev/null)" = "${WANT_STAMP}" ]; then
  log "stamp matches this snapshot; refreshing config.json in place (preserving ${REAL_SHARDS} converted shards)"
elif [ "${REAL_SHARDS}" -gt 0 ] && [ "${MOD_LABQ_FORCE_REBUILD:-0}" != "1" ]; then
  log "no current stamp, but ${REAL_SHARDS} converted shard files are present -- refusing to rm -rf; refreshing in place"
  log "  (set MOD_LABQ_FORCE_REBUILD=1 to rebuild the tree from scratch, discarding them)"
else
  log "rebuilding ${OUT_DIR} from scratch (no stamp match, ${REAL_SHARDS} real shards present)"
  rm -rf "${OUT_DIR}"
  mkdir -p "${OUT_DIR}" || die "cannot create ${OUT_DIR}"
fi
mkdir -p "${STAMP_DIR}" 2>/dev/null || true

#####################################################################
# Verify the problem is actually present before "fixing" it
#
# Test the SNAPSHOT config, not the patched output: the patched output always
# looks fixed, so testing it would report "nothing to do" forever and mask a
# changed upstream checkpoint.
#####################################################################
STATE="$(python3 - "${SNAP}/config.json" <<'PY'
import json, sys
qc = json.load(open(sys.argv[1])).get("quantization_config") or {}
inline_ok = ("quantized_layers" in qc) and (
    ("kv_cache_quant_algo" in qc) or ("kv_cache_scheme" in qc))
flat = False
try:
    hq = json.load(open(sys.argv[1].rsplit("/", 1)[0] + "/hf_quant_config.json"))
    flat = "quantization" not in hq
except FileNotFoundError:
    pass
# NEEDS_FIX == SGLang would fall through AND the fall-through target is flat
print("NEEDS_FIX" if (not inline_ok and flat) else "OK")
print("inline_quantized_layers", "quantized_layers" in qc)
print("inline_kv_key", ("kv_cache_quant_algo" in qc) or ("kv_cache_scheme" in qc))
print("hf_quant_config_is_flat", flat)
PY
)"
echo "${STATE}" | sed 's/^/[mod:'"${MOD_NAME}"']   /'
if ! echo "${STATE}" | grep -q '^NEEDS_FIX'; then
  log "config already accepted by the modelopt_mixed inline path; nothing to patch"
  mkdir -p "${OUT_DIR}"
  # Materialise config.json as a REAL COPY even when no patch is needed. Linking it
  # into the shared snapshot is dangerous twice over: a sibling mod that later wants
  # to edit config.json would either write through the link into the shared HF cache
  # (corrupting it for every consumer) or, if it is written correctly, refuse and
  # deadlock. A real copy makes this mod's output safe to depend on either way.
  rm -f "${OUT_DIR}/config.json"
  cp "${SNAP}/config.json" "${OUT_DIR}/config.json" || die "could not copy config.json"
  linkify_all
  printf '%s' "${WANT_STAMP}" > "${STAMP}"
  reown "${OUT_DIR}"
  log "tree at ${OUT_DIR} (config.json copied, unpatched)"
  exit 0
fi

#####################################################################
# Build the patched tree
#
# Refresh symlinks IN PLACE here. `ln -sfn` overwrites the link it manages and
# touches nothing else, so files owned by sibling mods in this same directory
# (notably the fp8 PLE shards from unpack-labquant-ple-nvfp4-to-fp8) survive.
# The only destructive step is the stamped rebuild above.
#####################################################################
# Refresh symlinks IN PLACE. linkify_all() refreshes the links this mod owns and leaves
# every regular file alone, so files owned by sibling mods in this same directory
# (notably the fp8 PLE shards from unpack-labquant-ple-nvfp4-to-fp8) survive.
# The only destructive step is the stamped rebuild above.
#####################################################################
linkify_all

# Break any existing link BEFORE writing. If a previous run took the passthrough
# branch, OUT_DIR/config.json is a symlink into the shared Hugging Face cache, and
# opening it for write would FOLLOW the link and rewrite the snapshot in place --
# corrupting the shared cache for every other consumer. Never write through a link.
if [ -L "${OUT_DIR}/config.json" ]; then
  rm -f "${OUT_DIR}/config.json"
fi

python3 - "${SNAP}/config.json" "${OUT_DIR}/config.json" <<'PY'
import json, os, sys
src, dst = sys.argv[1], sys.argv[2]
assert not os.path.islink(dst), \
    f"refusing to write {dst}: it is a symlink into the shared HF cache"
cfg = json.load(open(src))
qc = cfg.get("quantization_config")
assert isinstance(qc, dict), "config.json has no quantization_config; wrong checkpoint?"
assert "quantized_layers" in qc, "inline block lacks quantized_layers; the inline path cannot work"
assert "kv_cache_quant_algo" not in qc and "kv_cache_scheme" not in qc, \
    "a KV-cache key is already present; this mod should not have run"
# The checkpoint has no calibrated KV scales and we serve bf16 KV, so "no KV
# quantization" is the truth. Declaring it explicitly is what keeps SGLang's
# get_quant_config() on the inline path instead of falling through to the flat
# hf_quant_config.json it cannot parse.
qc["kv_cache_quant_algo"] = None
with open(dst, "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
print(f"patched: quantization_config.kv_cache_quant_algo = null (was absent)")
PY

[ -s "${OUT_DIR}/config.json" ] || die "patched config.json was not written"

# Record the stamp IMMEDIATELY after the patch succeeds and BEFORE the
# (potentially slow) verification import, so a verification failure still leaves
# a stamped tree rather than causing a destructive rebuild next launch.
#
# This fixes a real bug: the stamp used to be written only on the passthrough
# path, so after a successful patch every later launch saw "no current stamp"
# and re-ran the `rm -rf` above -- deleting the 51.2 GB of fp8 PLE shards that
# mods/unpack-labquant-ple-nvfp4-to-fp8 owns in this same directory, and
# forcing a full re-conversion on every single boot.
printf '%s' "${WANT_STAMP}" > "${STAMP}"

# Prove the patch actually yields a usable quant config, using the container's
# own SGLang. Fail here (seconds) rather than 9 minutes into a weight load.
#
# MOD_SKIP_VERIFY=1 skips this step. It exists so the tree-assembly logic can be
# unit-tested against a synthetic fixture: this step constructs a real ModelConfig,
# which needs a registered `model_type`, and no fake config satisfies that. Set only
# in tests -- in a real launch this check is what stops a bad patch from costing a
# nine-minute weight load before it surfaces.
if [ "${MOD_SKIP_VERIFY:-0}" = "1" ]; then
  log "MOD_SKIP_VERIFY=1: skipping in-container quant-config verification (test mode)"
else
python3 - "${OUT_DIR}" <<'PY'
import sys
from sglang.srt.configs.model_config import ModelConfig
from sglang.srt.configs.load_config import LoadConfig
from sglang.srt.model_loader.weight_utils import get_quant_config

PACKED = {
    "qkv_proj": ["q_proj", "k_proj", "v_proj"],
    "gate_up_proj": ["gate_proj", "up_proj"],
    "in_proj_qkvz": ["in_proj_qkv", "in_proj_z"],
    "in_proj_ba": ["in_proj_b", "in_proj_a"],
}
mc = ModelConfig(model_path=sys.argv[1], trust_remote_code=True)
qc = get_quant_config(mc, LoadConfig(), PACKED)
name = type(qc).__name__
assert "Mixed" in name, f"expected ModelOptMixedPrecisionConfig, got {name}"
print(f"get_quant_config -> {name} (min_capability={qc.get_min_capability()})")
for a in ("fp8_config", "fp8_block_config", "nvfp4_config", "nvfp4a16_config", "mxfp8_config"):
    print(f"  {a}: {'set' if getattr(qc, a, None) is not None else 'unset'}")
PY
fi

# Reown the WHOLE per-model runtime cache, not just OUT_DIR.
#
# This mod runs as root inside the per-model runtime-cache mount, and the
# get_quant_config verification ABOVE does `import sglang`, which triggers
# flashinfer's JIT build. That JIT writes flashinfer/<ver>/<arch>/
# flashinfer_jit.log into this cache as ROOT. The actual server then starts as
# uid 1000 and dies with
#   PermissionError: [Errno 13] Permission denied: '.../flashinfer_jit.log'
# and uid 1000 cannot even unlink the file to recover. Observed on 10.0.4.34 on
# 2026-09-18, caused by this mod; repaired by chown -R 1000:1000 on the per-model
# cache dir. This is the same class of failure the parent recipe documents for
# the fastsafetensors mods -- importing sglang for a config check reproduces it,
# so reown the entire mount, not just the directory this mod created.
reown /cache/runtime
reown "${OUT_DIR}"
log "patched tree ready at ${OUT_DIR} (use as --model-path)"
