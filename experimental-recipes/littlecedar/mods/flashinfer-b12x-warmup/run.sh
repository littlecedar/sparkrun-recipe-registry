#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later

set -euo pipefail


# README
# Compile FlashInfer SM121 CuTe-DSL kernels with a capped ninja job count
# to avoid OOMing the DGX Spark's 128 GB unified memory during compilation.


# Metadata
MOD_NAME="flashinfer-b12x-warmup"
MOD_DESCRIPTION="Cap ninja jobs when compiling flashinfer kernels"
MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"


# Mod Config
MAX_JOBS="${FLASHINFER_B12X_WARMUP_MAX_JOBS:-4}"
export MAX_JOBS
TIMEOUT="${FLASHINFER_B12X_WARMUP_TIMEOUT:-180}"
LOGDIR="${FLASHINFER_B12X_WARMUP_LOGDIR:-/cache/runtime/modlogs}"
# Mods run as root and we can't tell the real uid:gid from environment,
# so we have to infer from /cache/runtime ownership.
USER_UID="$(stat -c '%u' /cache/runtime)"
USER_NAME="$(stat -c '%U' /cache/runtime)"
USER_GID="$(stat -c '%g' /cache/runtime)"
USER_GROUP="$(stat -c '%G' /cache/runtime)"
MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"


# Helpers
reown() {
  chown -R "${USER_UID}:${USER_GID}" "${@}"
}

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

# Rotate logs
if [[ -f "${LOGDIR}/${MOD_NAME}.log.gz" ]]; then
  rm -f "${LOGDIR}/${MOD_NAME}.log.gz"
fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log" ]]; then
  gzip  "${LOGDIR}/${MOD_NAME}.log"
  touch "${LOGDIR}/${MOD_NAME}.log"
fi
reown "${LOGDIR}"


##### Script
log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log "${MOD_MAINTAINER}"
log_var MAX_JOBS

BUILD_BACKEND_PY="$(find /usr/local/lib -name build_backend.py | grep flashinfer)"

log "Capping ninja max build jobs by patching ${BUILD_BACKEND_PY}"
log_cmd sed -i.bak -e "s/\[\"ninja\", \"-C\",/[\"ninja\", \"-j${MAX_JOBS}\", \"-C\",/" "${BUILD_BACKEND_PY}"
log_cmd grep 'ninja_cmd.*"-j' "${BUILD_BACKEND_PY}"

sleep 5

log "preheat flashinfer b12x kernel"
log_cmd runuser -m -u "${USER_NAME}" -g "${USER_GROUP}" -- python3 "${MOD_DIR}/flashinfer-preheat.py"
log_cmd rm -fv payload.py

log "mod complete"
