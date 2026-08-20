#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# README
# Basic runtime environment recon for mod developers.

# Metadata
MOD_NAME="runtime-recon"
MOD_DESCRIPTION="Basic runtime environment recon for mod developers"
MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

# Mod Config
TIMEOUT="${RUNTIME_RECON_TIMEOUT:-180}"
LOGDIR="${RUNTIME_RECON_LOGDIR:-/cache/logs}"

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

#####

cap_cmd() {
  log "=== ${1} ==="
  "${@}" | log
}

log "mod description: ${MOD_DESCRIPTION}"
log "mod maintainer: ${MOD_MAINTAINER}"

log "Gathering environment info..."
cap_cmd whoami
log_var UID
log_var GID
cap_cmd env
cap_cmd flashinfer collect-env
cap_cmd flashinfer module-status

log "Done."
