#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Experimental pre-launch mod: the TensorFold DSV41 TP=2 lane *with vision*.
# It mirrors mods/tensorfold-dsv41-launcher/run.sh (same engine/launcher/cache
# gates) and adds one check: the staged VL-bias safetensors must be present, or
# the trial would silently measure the text-bias fallback. See
# recipes/ds4/AGENTS.md 12.14.
set -euo pipefail

export MOD_NAME="dsv41-vision-overlay"
export MOD_DESCRIPTION="TensorFold DSV41 TP2 + --vision (VL bias staged)"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

export TIMEOUT="${MOD_TIMEOUT:-180}"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export RUNTIME_DIR="${CACHEDIR}/tensorfold"
export UV_LINK_MODE=copy
export USER_UID="$(stat -c '%u' /cache/runtime)"
export USER_GID="$(stat -c '%g' /cache/runtime)"

# The VL bias ships inside this mod dir; sparkrun rsyncs the whole dir, so this
# path exists on every node at launch. The launcher reads the same default.
export MOD_VL_BIAS="${MOD_DIR}/vl_bias.safetensors"

reown() { chown -R "${USER_UID}:${USER_GID}" "${@}"; }

log() {
  local _message _ts
  _message="${*}"
  _ts="$(date -Ins)"
  printf '%s [%s] %s\n' "$_ts" "${MOD_NAME}" "${_message}" | tee -a "${LOGDIR}/${MOD_NAME}.log"
  [[ -x "$(type -fp logger)" ]] && logger -t "${MOD_NAME}" -- "${_message}" || true
}
log_var() { log "$1=${!1:-}"; }

if [[ ! -d "${LOGDIR}" ]]; then mkdir -p "${LOGDIR}"; fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log.gz" ]]; then rm -f "${LOGDIR}/${MOD_NAME}.log.gz"; fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log" ]]; then gzip "${LOGDIR}/${MOD_NAME}.log" || true; fi
touch "${LOGDIR}/${MOD_NAME}.log"
reown "${LOGDIR}"

log "${MOD_NAME} - ${MOD_DESCRIPTION}"

fail=0
check() {
  if [[ -e "$1" ]]; then log "gate OK: $1"; else log "gate MISSING: $1"; fail=1; fi
}
command -v tensorfold >/dev/null 2>&1 || { log "gate MISSING: tensorfold on PATH"; fail=1; }
check "${MOD_DIR}/launcher.py"
check /cache/huggingface/hub
check "${MOD_VL_BIAS}"
[[ "${fail}" -eq 0 ]] || { log "overlay gate FAILED"; exit 1; }
log "[dsv41-vision-overlay] overlay gate OK"
log_var MOD_VL_BIAS
log_var TF_DS_ENGRAM
log "tensorfold: $(command -v tensorfold) $(tensorfold --version 2>/dev/null || echo '?')"

mkdir -p "${RUNTIME_DIR}/rank-cache" "${RUNTIME_DIR}/torch-extensions"
reown "${RUNTIME_DIR}"
log_var RUNTIME_DIR

ENGRAM_DIR="${TENSORFOLD_ENGRAM_DIR:-/cache/huggingface/hub/dsv41-engram}"
if compgen -G "${ENGRAM_DIR}/*.safetensors" >/dev/null; then
  count=$(ls -1 "${ENGRAM_DIR}"/*.safetensors | wc -l)
  log "Engram: ${count} shard(s) at ${ENGRAM_DIR}"
else
  log "Engram: none at ${ENGRAM_DIR} (degraded; see recipes/ds4/README.md)"
fi

log "Done."
