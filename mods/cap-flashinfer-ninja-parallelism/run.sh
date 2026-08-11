#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Compile FlashInfer kernels with a capped ninja job count to
# help avoid OOMing the Spark during compilation.
# See littlecedar/mod-template/run.sh for feature documentation.
#####################################################################

MOD_NAME="cap-flashinfer-ninja-parallelism"
MOD_DESCRIPTION="Cap ninja jobs when compiling flashinfer kernels"
MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"
MAX_JOBS="${MOD_MAX_JOBS:-4}"
TIMEOUT="${MOD_TIMEOUT:-180}"
LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
USER_UID="$(stat -c '%u' /cache/runtime)"
USER_NAME="$(stat -c '%U' /cache/runtime)"
USER_GID="$(stat -c '%g' /cache/runtime)"
USER_GROUP="$(stat -c '%G' /cache/runtime)"
MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export MAX_JOBS

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

if ! [[ -d "${LOGDIR}" ]]; then
  mkdir -p "${LOGDIR}"
fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log.gz" ]]; then
  rm -f "${LOGDIR}/${MOD_NAME}.log.gz"
fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log" ]]; then
  gzip  "${LOGDIR}/${MOD_NAME}.log"
  touch "${LOGDIR}/${MOD_NAME}.log"
fi
reown "${LOGDIR}"

log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log "${MOD_MAINTAINER}"
log_var MAX_JOBS

BUILD_BACKEND_PY="$(find /usr/local/lib -name build_backend.py | grep flashinfer)"

log "Capping ninja max build jobs by patching ${BUILD_BACKEND_PY}"
log_cmd sed -i.bak -e "s/\[\"ninja\", \"-C\",/[\"ninja\", \"-j${MAX_JOBS}\", \"-C\",/" "${BUILD_BACKEND_PY}"
log_cmd grep 'ninja_cmd.*"-j' "${BUILD_BACKEND_PY}"
log "Done."
