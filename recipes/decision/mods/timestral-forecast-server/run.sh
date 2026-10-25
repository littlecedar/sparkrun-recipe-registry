#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Pre-launch mod for the Timestral forecast arm (decision lane, CPU serve).
#
# Timestral is not an LLM and no engine serves it: the mod stages a venv
# (--system-site-packages on a torch-bearing base image) with the upstream
# runtime `pip install git+https://github.com/mistralai/timestral@<pin>` and the
# recipe's command runs the stdlib server in this directory. Python >= 3.10 and
# torch >= 2.4 are the card's floors; torch comes from the image (PyPI aarch64
# wheels carry no CUDA need here — CPU-only serve).
#
# The stage risk the item names is the ~1 GB torch wheel when the base image
# lacks torch — that is why the recipe pins a torch-bearing base rather than
# python:*-slim, exactly the trade the kokoro arm avoided the other way (it
# baked the model into the image instead).
#
# Fail-closed: the arm cannot serve without a working venv, so a failed stage
# stops the launch. Idempotent from content: the gate is a real import of
# `timestral` on the existing venv, not a marker file.
set -euo pipefail

#####################################################################
# Metadata
#####################################################################
export MOD_NAME="timestral-forecast-server"
export MOD_DESCRIPTION="timestral upstream runtime venv + stdlib forecast server"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export TIMEOUT="${MOD_TIMEOUT:-600}"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export RUNTIME_DIR="${TIMESTRAL_RUNTIME_DIR:-${CACHEDIR}/timestral}"
export VENV_DIR="${RUNTIME_DIR}/venv"
# uv's symlinking gets messed up across permissions boundaries, so we copy.
export UV_LINK_MODE=copy
export USER_UID="$(stat -c '%u' /cache/runtime)"
export USER_NAME="$(stat -c '%U' /cache/runtime)"
export USER_GID="$(stat -c '%g' /cache/runtime)"
export USER_GROUP="$(stat -c '%G' /cache/runtime)"

# The upstream runtime is pinned to a commit, never a moving ref.
export TIMESTRAL_PIN="${TIMESTRAL_PIN:-a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff}"
export TIMESTRAL_REQ="${TIMESTRAL_REQ:-timestral @ git+https://github.com/mistralai/timestral.git@${TIMESTRAL_PIN}}"

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
  printf '%s [%s] %s\n' "$_ts" "${MOD_NAME}" "${_message}" | tee -a "${LOGDIR}/${MOD_NAME}.log"
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

engine_ok() {
  [[ -x "${VENV_DIR}/bin/python" ]] || return 1
  "${VENV_DIR}/bin/python" - <<'PY' >/dev/null 2>&1
import timestral  # noqa: F401
PY
}

if engine_ok; then
  log "engine gate OK (existing venv at ${VENV_DIR})"
else
  log "staging engine venv at ${VENV_DIR} (${TIMESTRAL_REQ})"
  rm -rf "${VENV_DIR}"
  export PIP_CACHE_DIR="${RUNTIME_DIR}/pip-cache"
  mkdir -p "${PIP_CACHE_DIR}"
  python3 -m venv --system-site-packages "${VENV_DIR}"
  "${VENV_DIR}/bin/python" -m pip install --quiet --upgrade pip
  # The CUDA-runtime base ships no torch: stage the aarch64 PyPI wheel (CPU-only
  # build for this arm — the laya precedent). This is the ~1 GB stage the item names.
  "${VENV_DIR}/bin/python" -m pip install --quiet torch
  "${VENV_DIR}/bin/python" -m pip install --quiet "${TIMESTRAL_REQ}"
  if engine_ok; then
    log "engine gate OK after install"
  else
    log "engine gate FAILED after install"
    exit 1
  fi
fi
ENGINE_VERSIONS="$("${VENV_DIR}/bin/python" -c 'import importlib.metadata as md; import torch; print("timestral %s torch %s" % (md.version("timestral"), torch.__version__))')"
log "engine versions: ${ENGINE_VERSIONS}"

reown "${RUNTIME_DIR}"
log_var VENV_DIR
log "Done."
