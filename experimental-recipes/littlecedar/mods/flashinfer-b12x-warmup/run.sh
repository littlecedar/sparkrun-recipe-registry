#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# README
# Pre-compile FlashInfer SM121 CuTe-DSL kernels with a capped ninja job count
# to avoid OOMing the DGX Spark's 128 GB unified memory during compilation.
# Kernels are cached to ~/.cache/flashinfer/ and reused on subsequent launches.

# Metadata
MOD_NAME="flashinfer-b12x-warmup"
MOD_DESCRIPTION="Pre-compile FlashInfer b12x/SM121 CuTe-DSL kernels"
MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

# Mod Config
MAX_JOBS="${FLASHINFER_B12X_WARMUP_MAX_JOBS:-1}"
export MAX_JOBS
TIMEOUT="${FLASHINFER_B12X_WARMUP_TIMEOUT:-180}"
LOGDIR="${FLASHINFER_B12X_WARMUP_LOGDIR:-/cache/runtime/modlogs}"

# Helpers
log() {
  local _message
  _message="${*}"

  o() {
    local _ts _message
    _message="${*}"
    _ts="$(date -Ins)"
    ! [[ -d "${LOGDIR}" ]] && mkdir -p "${LOGDIR}"
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

#####

log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log "${MOD_MAINTAINER}"
log_var MAX_JOBS


log_cmd flashinfer collect-env

log "=== precompile ==="
log "Precompiling FlashInfer & SM121 CuTe-DSL kernels..."
2>&1 python3 -vc "
import flashinfer
import b12x
" | log

log_cmd flashinfer module-status

flashinfer_log="$(find /tmp/.cache/flashinfer/ -name flashinfer_jit.log 2>/dev/null)"

log_cmd stat "$flashinfer_log"
log_cmd cat "$flashinfer_log"
log_cmd rm -fv "$flashinfer_log"

log "Done."
