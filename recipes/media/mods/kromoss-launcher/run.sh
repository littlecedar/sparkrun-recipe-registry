#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Pre-launch mod for the lodestones/Kromoss arm (media lane, media-gen).
#
# The engine is diffusers' `MOSSImagePipeline` — shipped as the checkpoint's own
# `pipeline_moss_image.py` and loaded via `custom_pipeline="pipeline_moss_image"`
# + `trust_remote_code=True` — which is neither sglang nor vLLM: there is no
# serving runtime for it. This mod is the same shape as the Qwen-Image-2.1-Turbo
# launcher (`recipes/media/mods/qwen-image-2.1-turbo-launcher/run.sh`): the
# serving image (the recipe's pinned `vllm/vllm-openai` build) is used only as a
# base for its arm64 CUDA torch build; a *venv* is staged on top of it
# (--system-site-packages, so the image's torch/CUDA stack is inherited and never
# re-downloaded) carrying diffusers >= 0.41 and transformers >= 5.17 — both above
# the card's stated floors (diffusers >= 0.38, transformers >= 5.3). The recipe's
# `command:` runs <RUNTIME_DIR>/venv/bin/python .../kromoss-launcher/server.py,
# so the venv is the engine.
#
# The engine gate cannot import `MOSSImagePipeline` (it lives in the checkpoint,
# loaded at serve time via trust_remote_code), so the gate asserts
# `DiffusionPipeline` + the version floors instead — the trust_remote_code import
# failure is then a loud serve-time 500, not a silent gap.
#
# Fail-closed: the arm cannot serve without a working venv, so a failed stage
# stops the launch rather than starting a server that cannot import its engine.
# Idempotent from content: the gate is a real import + version assertion on the
# existing venv, not a marker file or a timestamp.
set -euo pipefail

#####################################################################
# Metadata
#####################################################################
export MOD_NAME="kromoss-launcher"
export MOD_DESCRIPTION="diffusers MOSSImagePipeline (custom pipeline) venv + server for Kromoss"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export TIMEOUT="${MOD_TIMEOUT:-180}"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export RUNTIME_DIR="${KROMOSS_RUNTIME_DIR:-${CACHEDIR}/kromoss}"
export VENV_DIR="${RUNTIME_DIR}/venv"
export SAMPLE_DIR="${RUNTIME_DIR}/samples"
# uv's symlinking gets messed up across permissions boundaries, so we copy.
export UV_LINK_MODE=copy
export USER_UID="$(stat -c '%u' /cache/runtime)"
export USER_NAME="$(stat -c '%U' /cache/runtime)"
export USER_GID="$(stat -c '%g' /cache/runtime)"
export USER_GROUP="$(stat -c '%G' /cache/runtime)"

# Pinned engine requirements (above the card's floors; see header).
export DIFFUSERS_REQ="${KROMOSS_DIFFUSERS_REQ:-diffusers>=0.41.0}"
export TRANSFORMERS_REQ="${KROMOSS_TRANSFORMERS_REQ:-transformers>=5.17.0}"

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
mkdir -p "${RUNTIME_DIR}" "${SAMPLE_DIR}"
reown "${RUNTIME_DIR}"

# flashinfer's JIT logger opens <XDG_CACHE_HOME>/flashinfer/.cache/…/flashinfer_jit.log
# at import, and its tree is a sibling of this runtime dir. The engine gate
# below runs `from diffusers import DiffusionPipeline`, which imports
# diffusers' quantizers → flashinfer, so the *gate* creates that tree as root
# while the serve runs as the pool user — the 2026-11-22 first boot then died
# with PermissionError on flashinfer_jit.log before diffusers finished loading.
# Repair it around the gate (once for a stale tree the gate itself could not
# write, once for what the gate just wrote) so a retry needs no manual chown.
# The JIT cache is rebuildable: clear it when this user cannot own it.
repair_flashinfer_cache() {
  local dir
  dir="$(dirname "${RUNTIME_DIR}")/flashinfer"
  [[ -e "${dir}" ]] || return 0
  reown "${dir}"
  if [[ ! -w "${dir}" ]]; then
    log "clearing unwritable ${dir} (flashinfer rebuilds its JIT cache)"
    rm -rf "${dir}" || log "WARN: cannot clear ${dir}; the serve will fail on flashinfer_jit.log"
  fi
}
repair_flashinfer_cache

#####################################################################
# Fail-closed environment gate
#####################################################################
check() {
  if [[ -e "$1" ]]; then log "gate OK: $1"; else log "gate MISSING: $1"; exit 1; fi
}
check "${MOD_DIR}/server.py"
check /cache/huggingface/hub

# The venv's own engine must import, and be at the required floor. This is the
# content gate: a venv that exists but cannot import DiffusionPipeline is
# rebuilt, not trusted.
engine_ok() {
  [[ -x "${VENV_DIR}/bin/python" ]] || return 1
  "${VENV_DIR}/bin/python" - <<'PY' >/dev/null 2>&1
import importlib.metadata as md
from packaging.version import Version
assert Version(md.version("diffusers")) >= Version("0.41.0"), "diffusers below floor"
assert Version(md.version("transformers")) >= Version("5.17.0"), "transformers below floor"
from diffusers import DiffusionPipeline  # noqa: F401
PY
}

if engine_ok; then
  log "engine gate OK (existing venv at ${VENV_DIR})"
else
  log "staging engine venv at ${VENV_DIR} (${DIFFUSERS_REQ} ${TRANSFORMERS_REQ} accelerate safetensors)"
  rm -rf "${VENV_DIR}"
  # Keep pip's cache inside our own managed dir: the ambient PIP cache path is
  # not writable in this container, and pip then disables caching entirely.
  export PIP_CACHE_DIR="${RUNTIME_DIR}/pip-cache"
  mkdir -p "${PIP_CACHE_DIR}"
  python3 -m venv --system-site-packages "${VENV_DIR}"
  "${VENV_DIR}/bin/python" -m pip install --quiet --upgrade pip
  "${VENV_DIR}/bin/python" -m pip install --quiet --upgrade \
    "${DIFFUSERS_REQ}" "${TRANSFORMERS_REQ}" accelerate safetensors
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
# The gate above imported diffusers as root, so flashinfer's tree is root-owned
# again; hand it to the pool user before the serve starts.
repair_flashinfer_cache
log_var VENV_DIR
log_var SAMPLE_DIR
log "Done."
