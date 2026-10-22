#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Pre-launch mod for the Qwen-Image-2.1-Turbo (explore lane, media-gen) arm.
#
# The engine is diffusers' `QwenImage21Pipeline`, which is neither sglang nor
# vLLM: there is no serving runtime for it. The serving image
# (the recipe's pinned `vllm/vllm-openai` build) is used only as a base for its arm64 CUDA torch
# build; this mod stages a *venv* on top of it (--system-site-packages, so the
# image's torch/CUDA stack is inherited and never re-downloaded) carrying
# diffusers >= 0.41 (pipeline-configured sampling sigmas, PR #14950) and
# transformers >= 5.17. The recipe's `command:` runs
#   <RUNTIME_DIR>/venv/bin/python /workspace/mods/<this>/server.py
# so the venv is the engine.
#
# Fail-closed: the arm cannot serve without a working venv, so a failed stage
# stops the launch rather than starting a server that cannot import its engine.
# Idempotent from content: the gate is a real import + version assertion on the
# existing venv, not a marker file or a timestamp.
set -euo pipefail

#####################################################################
# Metadata
#####################################################################
export MOD_NAME="qwen-image-2.1-turbo-launcher"
export MOD_DESCRIPTION="diffusers QwenImage21Pipeline venv + server for Qwen-Image-2.1-Turbo"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export TIMEOUT="${MOD_TIMEOUT:-180}"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export RUNTIME_DIR="${QI_RUNTIME_DIR:-${CACHEDIR}/qwen-image}"
export VENV_DIR="${RUNTIME_DIR}/venv"
export SAMPLE_DIR="${RUNTIME_DIR}/samples"
# uv's symlinking gets messed up across permissions boundaries, so we copy.
export UV_LINK_MODE=copy
export USER_UID="$(stat -c '%u' /cache/runtime)"
export USER_NAME="$(stat -c '%U' /cache/runtime)"
export USER_GID="$(stat -c '%g' /cache/runtime)"
export USER_GROUP="$(stat -c '%G' /cache/runtime)"

# Pinned engine requirements. Diffusers 0.41.0 is the first release carrying
# `QwenImage21Pipeline` (the checkpoint's model_index.json declares
# `_diffusers_version: 0.41.0.dev0`); transformers 5.17 is the card's floor.
export DIFFUSERS_REQ="${QI_DIFFUSERS_REQ:-diffusers>=0.41.0}"
export TRANSFORMERS_REQ="${QI_TRANSFORMERS_REQ:-transformers>=5.17.0}"

#####################################################################
# Helpers
#####################################################################
reown() {
  if [[ "$(id -u)" -eq 0 ]]; then
    log "resetting permissions to ${USER_UID}:${USER_GID} on ${*}"
    chown -R "${USER_UID}:${USER_GID}" "${@}"
  else
    # The container may run as the cache owner instead of root (this image's
    # default user is the cache UID); then the mod cannot chown and does not
    # need to -- everything it wrote is already owned by that user.
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
mkdir -p "${RUNTIME_DIR}" "${SAMPLE_DIR}"
reown "${RUNTIME_DIR}"

#####################################################################
# Fail-closed environment gate
#####################################################################
check() {
  if [[ -e "$1" ]]; then log "gate OK: $1"; else log "gate MISSING: $1"; exit 1; fi
}
check "${MOD_DIR}/server.py"
check /cache/huggingface/hub

# The venv's own engine must import, and be at the required floor. This is the
# content gate: a venv that exists but cannot import QwenImage21Pipeline is
# rebuilt, not trusted.
engine_ok() {
  [[ -x "${VENV_DIR}/bin/python" ]] || return 1
  "${VENV_DIR}/bin/python" - <<'PY' >/dev/null 2>&1
import importlib.metadata as md
from packaging.version import Version
assert Version(md.version("diffusers")) >= Version("0.41.0"), "diffusers below floor"
assert Version(md.version("transformers")) >= Version("5.17.0"), "transformers below floor"
from diffusers import QwenImage21Pipeline  # noqa: F401
PY
}

if engine_ok; then
  log "engine gate OK (existing venv at ${VENV_DIR})"
else
  log "staging engine venv at ${VENV_DIR} (${DIFFUSERS_REQ} ${TRANSFORMERS_REQ} accelerate)"
  rm -rf "${VENV_DIR}"
  # Keep pip's cache inside our own managed dir: the ambient PIP cache path is
  # not writable in this container, and pip then disables caching entirely.
  export PIP_CACHE_DIR="${RUNTIME_DIR}/pip-cache"
  mkdir -p "${PIP_CACHE_DIR}"
  python3 -m venv --system-site-packages "${VENV_DIR}"
  "${VENV_DIR}/bin/python" -m pip install --quiet --upgrade pip
  "${VENV_DIR}/bin/python" -m pip install --quiet --upgrade \
    "${DIFFUSERS_REQ}" "${TRANSFORMERS_REQ}" accelerate
  if engine_ok; then
    log "engine gate OK after install"
  else
    log "engine gate FAILED after install"
    exit 1
  fi
fi
ENGINE_VERSIONS="$("${VENV_DIR}/bin/python" -c 'import importlib.metadata as md; print("diffusers %s transformers %s torch %s" % (md.version("diffusers"), md.version("transformers"), md.version("torch")))')"
log "engine versions: ${ENGINE_VERSIONS}"

reown "${RUNTIME_DIR}"
log_var VENV_DIR
log_var SAMPLE_DIR
log "Done."
