#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Pre-launch mod for the Edge0/Audio8-TTS-Realistic-Air arm (media lane).
#
# The engine is the checkpoint's own custom Transformers code (`ArkttsModel`
# via `auto_map` + `trust_remote_code`), which no serving runtime ships: the
# card's SGLang Omni adapter is not in the fleet pins. This mod stages the
# Python side on the image's own torch (`--system-site-packages`), in the
# kromoss/phonon shape. The card's own floor is `transformers>=4.57.0,<5` and
# its smoke test is 4.57.3; transformers 5.x is NOT allowed (the repo's
# `ArkttsModel` subclasses the 4.x `PreTrainedModel` surface).
#
# Fail-closed: no importable engine, no launch. The gate is a real import plus
# a version assertion on the existing venv, so it is idempotent from content.
set -euo pipefail

#####################################################################
# Metadata
#####################################################################
export MOD_NAME="audio8-tts-server"
export MOD_DESCRIPTION="custom-Transformers venv + OpenAI-compatible speech server for Audio8 TTS"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export TIMEOUT="${MOD_TIMEOUT:-300}"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export RUNTIME_DIR="${AUDIO8_RUNTIME_DIR:-${CACHEDIR}/audio8}"
export VENV_DIR="${RUNTIME_DIR}/venv"
export UV_LINK_MODE=copy
export USER_UID="$(stat -c '%u' /cache/runtime)"
export USER_NAME="$(stat -c '%U' /cache/runtime)"
export USER_GID="$(stat -c '%g' /cache/runtime)"
export USER_GROUP="$(stat -c '%G' /cache/runtime)"

# Pinned engine requirements (the card's floor and ceiling).
export TRANSFORMERS_REQ="${AUDIO8_TRANSFORMERS_REQ:-transformers>=4.57.0,<5}"

#####################################################################
# Helpers
#####################################################################
reown() {
  if [[ "$(id -u)" -eq 0 ]]; then
    log "resetting permissions to ${USER_UID}:${USER_GID} on ${*}"
    chown -R "${USER_UID}:${USER_GID}" "${@}"
  else
    log "not root (uid $(id -u)); skipping chown on ${*}"
  fi
}

log() {
  local _message _ts
  _message="${*}"
  _ts="$(date -Ins)"
  printf '%s [%s] %s\n' "${_ts}" "${MOD_NAME}" "${_message}" | tee -a "${LOGDIR}/${MOD_NAME}.log"
  [[ -x "$(type -fp logger)" ]] && logger -t "${MOD_NAME}" -- "${_message}" || true
}
log_var() { log "${1}=${!1:-}"; }

#####################################################################
# Rotate logs
#####################################################################
if ! [[ -d "${LOGDIR}" ]]; then mkdir -p "${LOGDIR}"; fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log.gz" ]]; then rm -f "${LOGDIR}/${MOD_NAME}.log.gz"; fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log" ]]; then gzip "${LOGDIR}/${MOD_NAME}.log" || true; fi
touch "${LOGDIR}/${MOD_NAME}.log"
reown "${LOGDIR}"

log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log_var USER_NAME
log_var USER_GROUP

#####################################################################
# Managed runtime cache
#####################################################################
mkdir -p "${RUNTIME_DIR}"
reown "${RUNTIME_DIR}"

#####################################################################
# Fail-closed environment gate
#####################################################################
check() {
  if [[ -e "$1" ]]; then log "gate OK: $1"; else log "gate MISSING: $1"; exit 1; fi
}
check "${MOD_DIR}/server.py"
check /cache/huggingface/hub

# The venv's engine must import, and transformers must sit under the 5.x
# boundary the card draws. A venv that exists but fails this is rebuilt.
engine_ok() {
  [[ -x "${VENV_DIR}/bin/python" ]] || return 1
  "${VENV_DIR}/bin/python" - <<'PY' >/dev/null 2>&1
import importlib.metadata as md
from packaging.version import Version
v = Version(md.version("transformers"))
assert Version("4.57.0") <= v < Version("5"), "transformers outside 4.57-4.x"
import soundfile  # noqa: F401
from transformers import AutoModel, AutoProcessor  # noqa: F401
PY
}

if engine_ok; then
  log "engine gate OK (existing venv at ${VENV_DIR})"
else
  log "staging engine venv at ${VENV_DIR} (${TRANSFORMERS_REQ} accelerate safetensors soundfile)"
  rm -rf "${VENV_DIR}"
  # Keep pip's cache inside our own managed dir (the kromoss reason: the
  # ambient PIP cache path is not writable in this container).
  export PIP_CACHE_DIR="${RUNTIME_DIR}/pip-cache"
  mkdir -p "${PIP_CACHE_DIR}"
  python3 -m venv --system-site-packages "${VENV_DIR}"
  "${VENV_DIR}/bin/python" -m pip install --quiet --upgrade pip
  "${VENV_DIR}/bin/python" -m pip install --quiet --upgrade \
    "${TRANSFORMERS_REQ}" accelerate safetensors soundfile
  if engine_ok; then
    log "engine gate OK after install"
  else
    log "engine gate FAILED after install"
    exit 1
  fi
fi
ENGINE_VERSIONS="$("${VENV_DIR}/bin/python" -c 'import importlib.metadata as md; print("transformers %s torch %s" % (md.version("transformers"), md.version("torch")))')"
log "engine versions: ${ENGINE_VERSIONS}"

reown "${RUNTIME_DIR}"
log_var VENV_DIR
log "Done."
