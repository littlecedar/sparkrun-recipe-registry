#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Compatibility gate + cache setup for the GLM-5.3-Flash EXL3 TP=4
# lane's engine image (MiaAI-Lab's tp4-branch build of TensorFold
# v0.6.0 with 106 patches). The image is digested-pinned by the recipe;
# this mod asserts the container really is that engine before the
# launcher execs it, and creates the cache directories the launcher
# points the engine at.
#
# It modifies no image file.
#
# The gate is fail-closed on purpose. TensorFold silently ignores a
# TF_GLM_* switch its build does not know, so an image swap that still
# starts a server would serve a *different* configuration than the one
# this lane measured. Each check above is the cheapest thing that
# distinguishes this build:
#
#   * `tensorfold/cli_args.py` widened `--tp` to (1, 2, 3, 4) --
#     upstream v0.6.0 accepts tp 1..2 only (patch 0066, the TP-N engine);
#   * a handful of files exist only after the patches
#     (cuda/roce.py, families/glm5_next/cuda/{own_front,microbatch}.py,
#     vision/glm.py);
#   * the TP=4 production switches the launcher exports are read by the
#     installed tree (a build without those patches would take the env
#     and do nothing with it);
#   * the image's own build-time import assertion still holds.
#
# It does NOT prove the exact patch *bytes*: that is the recipe's digest
# pin, and the image's `tf.patches` label is only readable from the host
# (`docker image inspect`). See README.md.
#####################################################################

#####################################################################
# Metadata
#####################################################################
export MOD_NAME="tensorfold-glm-exl3-launcher"
export MOD_DESCRIPTION="Compatibility gate + cache setup for the TensorFold GLM-5.3-Flash EXL3 TP=4 image"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export TIMEOUT="${MOD_TIMEOUT:-180}"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
# Cacheable artifacts, under the sparkrun-managed runtime cache
# (<host> ~/.cache/sparkrun/runtime-cache/<runtime>/<model_dir> -> /cache/runtime).
# These two paths are LITERAL and must match launcher.py's RECIPE_ENV: the
# launcher points TORCH_EXTENSIONS_DIR / TRITON_CACHE_DIR here so the CUDA
# extension compile persists per host instead of per container. Both live in
# this mod so they move together.
EXT_DIR="${CACHEDIR}/torch-extensions"
TRITON_DIR="${CACHEDIR}/triton"
export USER_UID="$(stat -c '%u' /cache/runtime)"
export USER_GID="$(stat -c '%g' /cache/runtime)"

#####################################################################
# Helpers
#####################################################################
reown() { chown -R "${USER_UID}:${USER_GID}" "${@}"; }

log() {
  local _message _ts
  _message="${*}"
  _ts="$(date -Ins)"
  printf '%s [%s] %s\n' "$_ts" "${MOD_NAME}" "${_message}" | tee -a "${LOGDIR}/${MOD_NAME}.log"
  [[ -x "$(type -fp logger)" ]] && logger -t "${MOD_NAME}" -- "${_message}" || true
}
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

# Patched-in modules (absent from upstream v0.6.0): the ROCE all-gather, the
# split-prefill own-front and microbatch paths, the vision tower.
for f in cuda/roce.py cuda/roce_proxy.c families/glm5_next/cuda/own_front.py \
         families/glm5_next/cuda/microbatch.py vision/glm.py; do
  [[ -e "${SITE}/tensorfold/${f}" ]] || die "missing ${f}: not the patched GLM build"
done
# Patch 0066: the TP-N engine widens --tp/--rank.
grep -q 'choices=(1, 2, 3, 4)' "${SITE}/tensorfold/cli_args.py" ||
  die "cli_args.py has not been widened to --tp 4 (patch 0066): upstream serves TP<=2"
# The TP=4 production switches launcher.py exports must be read by THIS tree.
for v in TF_GLM_SIDE TF_GLM_PROMPT_OWN_FRONT TF_GLM_PROMPT_MICROBATCH; do
  grep -rq "${v}" "${SITE}/tensorfold/families/glm5_next" ||
    die "${v} is not read by this build: the launcher's TP=4 configuration would be inert"
done
# The image's own build-time assertion, unchanged.
python3 -c "import tensorfold.cuda.server, tensorfold.families.glm5_next.cuda.engine, tensorfold.vision.glm" ||
  die "the engine does not import (tensorfold.cuda.server / glm5_next engine / vision)"

# Provenance only: the build context (the patch files) is baked in beside the
# package. The count is logged, not gated -- the digest pin is the identity.
patches=$(compgen -G "/opt/tf-patches/*.patch" | wc -l || true)
log "engine gate OK: tensorfold ${version}, ${SITE}, ${patches} patch file(s) in /opt/tf-patches"

#####################################################################
# Managed runtime cache
#####################################################################
mkdir -p "${EXT_DIR}" "${TRITON_DIR}"
reown "${CACHEDIR}" "${EXT_DIR}" "${TRITON_DIR}"
log_var EXT_DIR
log_var TRITON_DIR

# The RoCE all-gathers need a device list. At TP>2 the upstream launcher passes
# the node's active RoCE devices as TF_ROCE_HCA (launcher.py copies sparkrun's
# per-node NCCL_IB_HCA); unset is a legal state (the engine derives its own),
# but it changes which path the all-gathers take, so a boot should show it.
log "NCCL_IB_HCA=${NCCL_IB_HCA:-<unset>} NCCL_SOCKET_IFNAME=${NCCL_SOCKET_IFNAME:-<unset>}"

log "Done."