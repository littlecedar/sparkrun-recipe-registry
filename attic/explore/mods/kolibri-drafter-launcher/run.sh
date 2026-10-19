#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Pre-launch mod for the TensorFold Kolibri-1 block-drafter arm. Fail-closed
# gate: the engine and the launcher shim must be present, and the runtime-cache
# directories the engine writes are created and re-owned. It modifies no image
# file.
set -euo pipefail

export MOD_NAME="kolibri-drafter-launcher"
export MOD_DESCRIPTION="TensorFold kolibri1 launcher for Kolibri-1 + the block drafter"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

export TIMEOUT="${MOD_TIMEOUT:-120}"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export RUNTIME_DIR="${CACHEDIR}/kolibri-tensorfold"

log() {
  local _message _ts
  _message="${*}"
  _ts="$(date -Ins)"
  printf '%s [%s] %s\n' "$_ts" "${MOD_NAME}" "${_message}" | tee -a "${LOGDIR}/${MOD_NAME}.log"
  [[ -x "$(type -fp logger)" ]] && logger -t "${MOD_NAME}" -- "${_message}" || true
}

mkdir -p "${LOGDIR}"
if [[ -f "${LOGDIR}/${MOD_NAME}.log" ]]; then
  gzip "${LOGDIR}/${MOD_NAME}.log" || true
fi
touch "${LOGDIR}/${MOD_NAME}.log"

log "${MOD_NAME} - ${MOD_DESCRIPTION}"

fail=0
for path in "${MOD_DIR}/launcher.py" /cache/huggingface/hub; do
  if [[ -e "${path}" ]]; then log "gate OK: ${path}"; else log "gate MISSING: ${path}"; fail=1; fi
done
if command -v tensorfold >/dev/null 2>&1; then
  log "tensorfold: $(command -v tensorfold) $(tensorfold --version 2>/dev/null || echo '?')"
else
  log "gate MISSING: tensorfold on PATH"; fail=1
fi
# The drafter taps Kolibri's layer 44/47/49 states: only the fork branch that
# adds them can serve this arm, so a stock TensorFold image must fail here
# rather than at the first decode.
[[ "${fail}" -eq 0 ]] || { log "overlay gate FAILED"; exit 1; }
log "overlay gate OK"

mkdir -p "${RUNTIME_DIR}" "${RUNTIME_DIR}/torch-extensions"
chown -R "$(stat -c '%u:%g' "${CACHEDIR}")" "${RUNTIME_DIR}"
log "runtime cache: ${RUNTIME_DIR}"

log "Done."
