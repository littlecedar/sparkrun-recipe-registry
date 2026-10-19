#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Compatibility gate + cache setup for the GLM-5.3 EXL3 3.0bpw TP=4
# lane's engine image (`sparkrun/tensorfold-glm53-exl3-3bpw:0.6.0-ddfad35`
# locally; built from recipes/glm/Dockerfile.tensorfold-glm53-3bpw over
# `lmsysorg/sglang:dev-cu13`). The image is digest-pinned by the recipe;
# this mod asserts the container really is that engine before the
# launcher execs it, and creates the cache directories the launcher
# points the engine at.
#
# It modifies no image file.
#
# The gate is fail-closed on purpose. TensorFold silently ignores an env
# switch its build does not know, so an image swap that still starts a
# server would serve a *different* configuration than the one this lane
# measured. Each check is the cheapest thing that distinguishes this tree:
#
#   * `--tp` is (1, 2, 4, 6) -- upstream v0.6.0 accepts 1..2 only, and the
#     4bpw lane's patched build accepts (1, 2, 3, 4);
#   * `glm_moe_dsa` declares this exact checkpoint and no external drafter;
#   * the four env switches the launcher exports (TF_GLM_KV, TF_GLM_DCP,
#     TF_GLM_EXTENTS, TF_GLM_MTP_REUSE) are read by the installed tree;
#   * the 4bpw-only patch files are ABSENT. Their presence means the image
#     is the 106-patch build: a different TP engine, a RoCE transport this
#     fork does not have, and no guarantee the flags below mean the same.
#
# It does NOT prove the exact commit: that is the recipe's image digest.
# See README.md.
#####################################################################

#####################################################################
# Metadata
#####################################################################
export MOD_NAME="tensorfold-glm53-3bpw-launcher"
export MOD_DESCRIPTION="Compatibility gate + cache setup for the TensorFold GLM-5.3 EXL3 3.0bpw TP=4 image"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export TIMEOUT="${MOD_TIMEOUT:-180}"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
# Cacheable artifacts, under the sparkrun-managed runtime cache
# (<host> ~/.cache/sparkrun/runtime-cache/<runtime>/<model_dir> -> /cache/runtime).
# These two paths are LITERAL and must match launcher.py's CONSTANT_ENV: the
# launcher points TORCH_EXTENSIONS_DIR / TRITON_CACHE_DIR here so the CUDA
# extension compile (first start per host: the sm_121 JIT) persists per host
# instead of per container. Both live in this mod so they move together.
EXT_DIR="${CACHEDIR}/torch-extensions"
TRITON_DIR="${CACHEDIR}/triton"
export USER_UID="$(stat -c '%u' /cache/runtime)"
export USER_GID="$(stat -c '%g' /cache/runtime)"

#####################################################################
# Helpers
#####################################################################
reown() { chown -R "${USER_UID}:${USER_GID}" "${@}"; }

log() { echo "[${MOD_NAME}] $*"; }
log_var() { log "$1=${!1:-}"; }
die() { log "$*"; exit 1; }

#####################################################################
# Log rotation
#####################################################################
if [[ ! -d "${LOGDIR}" ]]; then mkdir -p "${LOGDIR}"; fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log.gz" ]]; then rm -f "${LOGDIR}/${MOD_NAME}.log.gz"; fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log" ]]; then gzip "${LOGDIR}/${MOD_NAME}.log" || true; fi
touch "${LOGDIR}/${MOD_NAME}.log"
reown "${LOGDIR}"

log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log "${MOD_MAINTAINER}"

#####################################################################
# Fail-closed engine gate
#####################################################################
command -v tensorfold >/dev/null 2>&1 || die "tensorfold is not on PATH: this is not a TensorFold image"
version="$(tensorfold --version 2>/dev/null | tail -1 || true)"
[[ "${version}" == *0.6.0* ]] || die "TensorFold $version is not the pinned v0.6.0 line"
SITE="$(python3 -c 'import os, tensorfold; print(os.path.dirname(os.path.dirname(tensorfold.__file__)))')"
[[ -d "${SITE}/tensorfold" ]] || die "no tensorfold package under ${SITE}"

# This fork's world-parameterized CLI. Upstream v0.6.0 is (1, 2); the 4bpw
# lane's patched build is (1, 2, 3, 4).
grep -q 'choices=(1, 2, 4, 6)' "${SITE}/tensorfold/cli_args.py" ||
  die "cli_args.py --tp choices are not (1, 2, 4, 6): this is not the glm-dsa-tp4 fork"

# The family ships this checkpoint and no external drafter (drafting is the
# checkpoint's own MTP head).
FAMILY="${SITE}/tensorfold/families/glm_moe_dsa/__init__.py"
[[ -f "${FAMILY}" ]] || die "no glm_moe_dsa family: this engine cannot read this checkpoint"
grep -q 'bertholomus/GLM-5.3-EXL3-3.0bpw' "${FAMILY}" ||
  die "the glm_moe_dsa family does not declare bertholomus/GLM-5.3-EXL3-3.0bpw"
grep -q '^DRAFTER = ""' "${FAMILY}" ||
  die "this family declares a DRAFTER; the lane's drafting path is the checkpoint's own MTP head"

# The switches launcher.py exports must be read by THIS tree (TensorFold
# ignores an env switch it does not know).
grep -q 'TF_GLM_KV' "${SITE}/tensorfold/families/glm_moe_dsa/cuda/kv8.py" ||
  die "cuda/kv8.py does not read TF_GLM_KV"
grep -q 'TF_GLM_DCP' "${SITE}/tensorfold/families/glm_moe_dsa/cuda/dcp.py" ||
  die "cuda/dcp.py does not read TF_GLM_DCP (no 1M decode context parallelism in this build)"
grep -q 'TF_GLM_EXTENTS' "${SITE}/tensorfold/families/glm_moe_dsa/cuda/multi.py" ||
  die "cuda/multi.py does not read TF_GLM_EXTENTS"
grep -q 'TF_GLM_MTP_REUSE' "${SITE}/tensorfold/families/glm_moe_dsa/cuda/mtp.py" ||
  die "cuda/mtp.py does not read TF_GLM_MTP_REUSE"

# Wrong tree, explicitly: the 4bpw lane's patch set (RoCE all-gather, TP=3,
# split-prefill own-front / microbatch). None of these exist in this fork.
for f in cuda/roce.py cuda/roce_proxy.c families/glm5_next/cuda/own_front.py \
         families/glm5_next/cuda/microbatch.py; do
  if [[ -e "${SITE}/tensorfold/${f}" ]]; then
    die "found ${f}: this is the 4bpw patched build, not the glm-dsa-tp4 fork (wrong TP engine, RoCE transport)"
  fi
done

# Imports the engine needs on this path (CPU-safe: no device is touched).
python3 -c "import tensorfold.cuda.server, tensorfold.families.glm_moe_dsa.cuda.engine, tensorfold.families.glm_moe_dsa.cuda.dcp" ||
  die "the engine does not import (tensorfold.cuda.server / glm_moe_dsa engine / dcp)"

log "engine gate OK: tensorfold ${version}, ${SITE}"

#####################################################################
# Managed runtime cache
#####################################################################
mkdir -p "${EXT_DIR}" "${TRITON_DIR}"
reown "${CACHEDIR}" "${EXT_DIR}" "${TRITON_DIR}"
# A killed boot leaves the JIT build lock behind, and the next start waits on it
# instead of compiling (its own log says so). Nothing can be building before the
# engine execs, so any lock present here is stale; the .so is kept for reuse.
rm -f "${EXT_DIR}"/*/lock "${EXT_DIR}"/*/.ninja_lock 2>/dev/null || true

log_var EXT_DIR
log_var TRITON_DIR

# The lane's transport is NCCL over this cluster's RoCE rails, configured by
# sparkrun's own probe (NCCL_IB_HCA / NCCL_SOCKET_IFNAME per node), not by the
# recipe. Logged because a boot that stalls in an all-gather is diagnosed here.
log "NCCL_IB_HCA=${NCCL_IB_HCA:-<unset>} NCCL_SOCKET_IFNAME=${NCCL_SOCKET_IFNAME:-<unset>}"

log "Done."
