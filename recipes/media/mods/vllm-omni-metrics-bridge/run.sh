#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Ships the metrics-bridge wrapper that this lane's vLLM-Omni arm runs in
# front of `vllm-omni serve`.
#
# The recipe's `command:` is
#     python3 /workspace/mods/vllm-omni-metrics-bridge/launcher.py serve ...
# so the file the command names must be inside the container: sparkrun mounts
# a mod's own directory at /workspace/mods/<name>, which is why this mod exists
# at all (it patches nothing and installs nothing).
#
# The gate is fail-closed on the two ways that command can be a dead boot:
# an image without `vllm-omni` on PATH (the wrapper would exec nothing) and a
# wrapper that does not parse (the container's python3 would die before the
# engine starts, with the launch looking like an engine failure).
#
# It modifies no image file.
#####################################################################

#####################################################################
# Metadata
#####################################################################
export MOD_NAME="vllm-omni-metrics-bridge"
export MOD_DESCRIPTION="Ships the vLLM-Omni metrics-bridge serve wrapper (+ gate)"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export TIMEOUT="${MOD_TIMEOUT:-180}"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export USER_UID="$(stat -c '%u' /cache/runtime)"
export USER_GID="$(stat -c '%g' /cache/runtime)"

#####################################################################
# Helpers
#####################################################################
log() {
  local _message _ts
  _message="${*}"
  _ts="$(date -Ins)"
  printf '%s [%s] %s\n' "$_ts" "${MOD_NAME}" "${_message}" | tee -a "${LOGDIR}/${MOD_NAME}.log"
  [[ -x "$(type -fp logger)" ]] && logger -t "${MOD_NAME}" -- "${_message}" || true
}
log_var() { log "${1}=${!1:-}"; }

die() {
  log "FATAL: ${*}"
  exit 1
}

reown() {
  if [[ "$(id -u)" -eq 0 ]]; then
    log "resetting permissions to ${USER_UID}:${USER_GID} on ${*}"
    chown -R "${USER_UID}:${USER_GID}" "${@}"
  else
    # Same non-root image as the engine: everything written is already owned by
    # the cache user, and chown would fail under `set -e`.
    log "not root (uid $(id -u)); skipping chown on ${*}"
  fi
}

#####################################################################
# Rotate logs
#####################################################################
if [[ ! -d "${LOGDIR}" ]]; then mkdir -p "${LOGDIR}"; fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log.gz" ]]; then rm -f "${LOGDIR}/${MOD_NAME}.log.gz"; fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log" ]]; then gzip "${LOGDIR}/${MOD_NAME}.log" || true; fi
touch "${LOGDIR}/${MOD_NAME}.log"
reown "${LOGDIR}"

log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log "${MOD_MAINTAINER}"

#####################################################################
# Fail-closed engine gate
#####################################################################
command -v vllm-omni >/dev/null 2>&1 || die "vllm-omni is not on PATH: this is not a vLLM-Omni image"
command -v python3 >/dev/null 2>&1 || die "no python3: the bridge wrapper cannot run"
[[ -f "${MOD_DIR}/launcher.py" ]] || die "launcher.py is not beside run.sh (${MOD_DIR})"
python3 -c 'import ast, sys; ast.parse(open(sys.argv[1]).read())' "${MOD_DIR}/launcher.py" ||
  die "launcher.py does not parse: ${MOD_DIR}/launcher.py"

# Provenance only, never gated by the version strings: the nightly tag moves and
# the recipe's digest is the identity.
log "vllm_omni: $(python3 -c 'import vllm_omni; print(vllm_omni.__version__)' 2>/dev/null || echo '<not importable at this entrypoint>')"
log "metrics bridge: OMNI_METRICS_BRIDGE=${OMNI_METRICS_BRIDGE:-1} (0 disables; the bridge is fail-open)"
log_var MOD_DIR

log "Done."