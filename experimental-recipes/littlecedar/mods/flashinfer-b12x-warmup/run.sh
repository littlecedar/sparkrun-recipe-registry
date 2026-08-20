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
MAX_JOBS="${FLASHINFER_B12X_WARMUP_MAX_JOBS:-8}"
export MAX_JOBS
TIMEOUT="${FLASHINFER_B12X_WARMUP_TIMEOUT:-180}"

# Helpers
log() {
  local _message
  _message="${*}"

  o() {
    local _ts _message
    _message="${*}"
    _ts="$(date -Ins)"
    printf '%s [%s] %s\n' "$_ts" "${MOD_NAME}" "${_message}"
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

#####

log "mod description: ${MOD_DESCRIPTION}"
log "mod maintainer: ${MOD_MAINTAINER}"
log_var MAX_JOBS

log "Precompiling FlashInfer SM121 CuTe-DSL kernels..."

python3 -vvc "
import flashinfer
import b12x
" | log

log "Done."
