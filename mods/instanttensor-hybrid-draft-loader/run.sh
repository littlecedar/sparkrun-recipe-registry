#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
# SPDX-FileCopyrightText: eugr (github.com/eugr/spark-vllm-docker)
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Patch vLLM's central `get_model()` so that a *speculative draft* may load
# with lazy safetensors while the *target* model stays on InstantTensor.
#
# WHY EXISTS: when `--load-format instanttensor` is set and a speculative draft
# shares the target checkpoint (embedded MTP or a same-path drafter), vLLM
# otherwise runs a SECOND InstantTensor GPU-streaming pass over the whole
# checkpoint just to keep a small subset of draft tensors. This mod resolves
# the loader *per model* at `get_model()` and switches only the draft to
# lazy safetensors, which keeps the rejected draft tensors as CPU
# memory-mapped views instead of staging and cloning them on the GPU.
#
# Source: eugr/spark-vllm-docker (github.com/eugr/spark-vllm-docker),
# mods/instanttensor-hybrid-draft-loader/ (Apache-2.0). `patch_model_loader.py`
# is vendored VERBATIM (only its SPDX header differs); `run.sh` is rewritten in
# this repo's mod style. Upstream README is vendored as ./files/UPSTREAM-README.md.
#
# IT IS A NO-OP UNLESS BOTH HOLD (by design, safe to list on every recipe):
#   * the effective load_format is `instanttensor`; AND
#   * a real speculative draft exists whose effective loader would also be
#     InstantTensor.
# In `auto` (default) mode a same-path/same-revision draft is the ONLY case
# that flips. Our DS4.1 DSpark drafter is a SEPARATE model path, so on our
# recipes the mod does nothing and the boot is byte-identical to InstantTensor
# alone. It is listed so a later same-checkpoint draft benefits automatically.
#
# CONTRACT, fail-closed (mirrors mount-dsv41-exl3-patches):
#   * The vendored patcher is md5-verified against files/MD5SUMS.txt.
#   * The patcher runs its own `--check` BEFORE writing: if the image's
#     `get_model()` does not match the vendored anchor exactly, it refuses and
#     this mod exits non-zero -- a mismatched vLLM never gets a silent patch.
#   * The target file is backed up ONCE to <target>.sparkrun-orig.
#   * Idempotence is by the marker text, not timestamps: a re-run is a no-op.
#   * Env passthrough: INSTANTTENSOR_DRAFT_LOADER (auto|safetensors|instanttensor)
#     is read by the PATCHED vLLM at runtime, so it must reach the serve process.
#     Spray it via the recipe `env:` block, not here.
#####################################################################

#####################################################################
# Metadata
#####################################################################
MOD_NAME="instanttensor-hybrid-draft-loader"
MOD_DESCRIPTION="Keep InstantTensor for the target; let a same-checkpoint draft load lazily"
MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
TIMEOUT="${MOD_TIMEOUT:-180}"
MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
FILES_DIR="${MOD_DIR}/files"
PATCHER="${MOD_DIR}/patch_model_loader.py"
# vLLM lives here in littlecedar/dgx-spark-dsv41:exl3a. Overridable for a
# different base image without editing this file.
PYTHON_ROOT="${VLLM_SITE_PACKAGES:-/usr/local/lib/python3.12/dist-packages}"
TARGET="${PYTHON_ROOT}/vllm/model_executor/model_loader/__init__.py"
USER_UID="$(stat -c '%u' /cache/runtime)"
USER_GID="$(stat -c '%g' /cache/runtime)"

#####################################################################
# Helpers
#####################################################################

reown() {
  log "resetting permissions to ${USER_UID}:${USER_GID} on ${*}"
  chown -R "${USER_UID}:${USER_GID}" "${@}"
}

log() {
  local _message
  _message="${*}"

  o() {
    local _ts _message
    _message="${*}"
    _ts="$(date -Ins)"
    printf '%s [%s] %s\n' "$_ts" "${MOD_NAME}" "${_message}" | tee -a "${LOGDIR}/${MOD_NAME}.log"
    [[ -x "$(type -fp logger)" ]] && logger -t "${MOD_NAME}" -- "${_message}"
  }

  if [[ -z "${*}" ]]; then
    while read -rt "${TIMEOUT}" line; do
      o "${line}"
    done
  else
    o "${*}"
  fi
}

log_var() {
  local _key _val
  _key="${1}"
  _val="${!_key}"
  log "${_key}=${_val}"
}

log_cmd() {
  log "            "
  log "            "
  log "=== ${1} ==="
  "${@}" 2>&1 | log
}

die() {
  log "FATAL: ${*}"
  exit 1
}

#####################################################################
# Preflight
#####################################################################
if ! [[ -d "${LOGDIR}" ]]; then
  mkdir -p "${LOGDIR}"
fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log.gz" ]]; then
  rm -f "${LOGDIR}/${MOD_NAME}.log.gz"
fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log" ]]; then
  gzip "${LOGDIR}/${MOD_NAME}.log"
  touch "${LOGDIR}/${MOD_NAME}.log"
fi
reown "${LOGDIR}"

log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log "${MOD_MAINTAINER}"

[[ -f "${PATCHER}" ]] || die "patcher not found at ${PATCHER}"
[[ -f "${TARGET}" ]] || die "vLLM model-loader module not found at ${TARGET}"

# md5-verify the vendored patcher against files/MD5SUMS.txt (fail-closed).
if [[ -f "${FILES_DIR}/MD5SUMS.txt" ]]; then
  log "verifying vendored patcher against files/MD5SUMS.txt"
  ( cd "${MOD_DIR}" && md5sum --check --quiet "${FILES_DIR}/MD5SUMS.txt" ) \
    || die "md5 mismatch: the vendored patcher does not match files/MD5SUMS.txt"
fi

log_var TARGET
log_var INSTANTTENSOR_DRAFT_LOADER

#####################################################################
# Back up the target ONCE (idempotence by presence, not timestamps)
#####################################################################
BACKUP="${TARGET}.sparkrun-orig"
if [[ ! -f "${BACKUP}" ]]; then
  log "backing up ${TARGET} -> ${BACKUP}"
  cp -p "${TARGET}" "${BACKUP}"
  reown "${BACKUP}"
else
  log "backup already exists at ${BACKUP}; not overwriting"
fi

#####################################################################
# Patch (compatibility-checked, idempotent)
#####################################################################
log "compatibility check BEFORE writing (refuses on an unexpected get_model)"
log_cmd python3 "${PATCHER}" --check "${TARGET}"

log "applying the hybrid-draft-loader patch"
log_cmd python3 "${PATCHER}" "${TARGET}"

log "compatibility check AFTER writing (must report 'already patched')"
log_cmd python3 "${PATCHER}" --check "${TARGET}"

# Stale bytecode would shadow the patched source.
find "$(dirname "${TARGET}")" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

log "mod complete"
