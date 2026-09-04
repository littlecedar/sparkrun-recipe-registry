#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# A hackable sparkrun mod template for making your own mods.
# Includes:
# * Built-in configs
# * Logging & log rotation
# * Permissions management
#####################################################################

#####################################################################
# Metadata
#####################################################################
MOD_NAME="mod-template"
MOD_DESCRIPTION="A sparkrun mod template for making your own mods"
MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
TIMEOUT="${MOD_TIMEOUT:-180}"
LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
# Mods run as root and we can't tell the real uid:gid from environment,
# so we have to infer from /cache/runtime ownership.
USER_UID="$(stat -c '%u' /cache/runtime)"
USER_GID="$(stat -c '%g' /cache/runtime)"

#####################################################################
# Helpers
#####################################################################

#--------------------------------------------------------------------
# Chown a path to the user who owns the .cache bind mount.
#
# Since mods run as root, changes to paths and files that require
# user access may fail if owned by root. Use this to fix that.
#--------------------------------------------------------------------
reown() {
  chown -R "${USER_UID}:${USER_GID}" "${@}"
}

#--------------------------------------------------------------------
# General logging helper
#
# Formats and sends to log anything on STDIN or given as args.
#--------------------------------------------------------------------
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

#--------------------------------------------------------------------
# Quickly log a variable name and its value.
#--------------------------------------------------------------------
log_var() {
  local _key _val
  _key="${1}"
  _val="${!_key}"
  log "${_key}=${_val}"
}

#--------------------------------------------------------------------
# Simple command logging harness
#
# Provide a simple command and its arguments as args to this.
# Complex pipelines don't work well; pipe pipelines to log().
#--------------------------------------------------------------------
log_cmd() {
  log "            "
  log "            "
  log "=== ${1} ==="
  "${@}" | log
}

#####################################################################
# Rotate logs
#####################################################################
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

#####################################################################
# Main mod scripting zone
#
# Add your mod commands below here.
# You can add additional helpers in the helpers section if you like.
# There are no real rules, just organization and pattern.
#
log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log "${MOD_MAINTAINER}"
#
#####################################################################

log "Gathering environment info..."
log_cmd whoami
log_var UID
log_var GID
log_cmd env

#####################################################################
# Log Completion
#####################################################################
log "Done."
