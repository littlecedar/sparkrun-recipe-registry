#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Install orjson Python module to make vLLM /v1/embeddings API fast
#####################################################################

MOD_NAME="pip-install-orjson"
MOD_DESCRIPTION="Install orjson to make /v1/embeddings API fast"
MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"
TIMEOUT="${MOD_TIMEOUT:-180}"
LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
USER_UID="$(stat -c '%u' /cache/runtime)"
USER_NAME="$(stat -c '%U' /cache/runtime)"
USER_GID="$(stat -c '%g' /cache/runtime)"
USER_GROUP="$(stat -c '%G' /cache/runtime)"
MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

log "Installing orjson"
log_cmd pip install --force orjson

log "mod complete"
