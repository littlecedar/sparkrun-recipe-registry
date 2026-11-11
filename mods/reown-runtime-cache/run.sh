#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Reown the runtime-cache subtrees a root pre_exec hook writes, and fail the
# launch if the repair does not stick.
#
# Why: mods run as root, the serve runs as the cache mount's owner. The ERNIE
# sparse-MLA hook imports `flashinfer` while verifying, which births
# `/cache/runtime/flashinfer/.cache/flashinfer/<ver>/<arch>/flashinfer_jit.log`
# as `0:0`; every later uid-1000 serve on that node then dies
# `PermissionError` and cannot unlink it (measured rank 3 on `.35`,
# 2026-11-11, register row `runtime-cache-flashinfer-root-owned-subtree`).
#
# Order matters: this mod must run AFTER the mod that writes the cache root,
# because its repair is a stat of what that hook just did. A mod list is
# pre_exec order, so list it last.
#
# Not covered here: the host-side HuggingFace cache. `sparkrun setup
# fix-permissions` (default `~/.cache/huggingface`, or `--cache-dir`) owns
# that path; the runtime cache is `~/.cache/sparkrun/runtime-cache` on the
# host and needs its own command. This mod is prevention inside the container,
# not a substitute for either host repair.
#
# Knobs:
#   REOWN_PATHS  space-separated container paths (default
#                "/cache/runtime/flashinfer /cache/runtime/.cache").
#                Only paths a hook is known to create belong here: a recursive
#                chown over a model snapshot tree is not a permission fix.

set -euo pipefail

export MOD_NAME="reown-runtime-cache"
export MOD_DESCRIPTION="Hand root-created runtime-cache subtrees back to the serve user"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

export TIMEOUT="${MOD_TIMEOUT:-120}"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export REOWN_PATHS="${REOWN_PATHS:-/cache/runtime/flashinfer /cache/runtime/.cache}"

# Mods run as root and cannot see the serve user: infer it from the mount root,
# exactly as the harness does.
export USER_UID="$(stat -c '%u' "${CACHEDIR}")"
export USER_NAME="$(stat -c '%U' "${CACHEDIR}")"
export USER_GID="$(stat -c '%g' "${CACHEDIR}")"
export USER_GROUP="$(stat -c '%G' "${CACHEDIR}")"

die() {
  log "FATAL: ${*}"
  exit 1
}

reown() {
  if [[ "$(id -u)" != "0" ]]; then
    log "reown: not root (uid $(id -u)); skipping chown of ${*}"
    return 0
  fi
  log "resetting permissions to ${USER_UID}:${USER_GID} on ${*}"
  chown -R "${USER_UID}:${USER_GID}" "${@}"
}

log() {
  local _message _ts
  _message="${*}"
  _ts="$(date -Ins)"
  printf '%s [%s] %s\n' "$_ts" "${MOD_NAME}" "${_message}" | tee -a "${LOGDIR}/${MOD_NAME}.log"
}

log_var() {
  local _key _val
  _key="${1}"
  _val="${!_key}"
  log "${_key}=${_val}"
}

mkdir -p "${LOGDIR}"
reown "${LOGDIR}"
if [[ -f "${LOGDIR}/${MOD_NAME}.log.gz" ]]; then
  rm -f "${LOGDIR}/${MOD_NAME}.log.gz"
fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log" ]]; then
  gzip "${LOGDIR}/${MOD_NAME}.log"
  touch "${LOGDIR}/${MOD_NAME}.log"
fi
reown "${LOGDIR}"

log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log_var USER_UID
log_var USER_GID
log_var REOWN_PATHS

changed=0
read -r -a paths <<< "${REOWN_PATHS}"
for path in "${paths[@]}"; do
  [[ -e "${path}" ]] || {
    log "skip: ${path} does not exist"
    continue
  }
  before="$(stat -c '%u:%g' "${path}")"
  [[ "${before}" == "${USER_UID}:${USER_GID}" ]] || changed=$((changed + 1))
  reown "${path}"
  after="$(stat -c '%u:%g' "${path}")"
  log "path ${path}: owner ${before} -> ${after}"
  [[ "${after}" == "${USER_UID}:${USER_GID}" ]] ||
    die "${path} is still ${after} after chown, expected ${USER_UID}:${USER_GID}; a repair that did not stick must stop the launch"
done

log "Done. ${changed} path(s) reowned, all checked against ${USER_UID}:${USER_GID}."
