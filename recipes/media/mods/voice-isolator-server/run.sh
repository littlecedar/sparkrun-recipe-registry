#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Pre-launch mod for the inworld/voice-isolator GPU script arm (media lane).
#
# The checkpoint is a plain torch state dict (embedded config, `library_name:
# inworld-voice-isolation`, no config.json), so no serving engine loads it and
# upstream publishes no server image: the arm is the vendor SDK
# (`pip install inworld-voice-isolation`, import `inworld.voice_isolation`)
# behind a stdlib HTTP server, the kokoro/phonon/pyannote/kromoss precedent.
#
# This mod stages one thing: a venv on the recipe's pinned `vllm/vllm-openai`
# base, with `--system-site-packages` so the image's CUDA stack is inherited and
# never re-downloaded — torch 2.13.0 + torchaudio 2.11.0 (v0.32.0's
# requirements/cuda.txt) already satisfy the SDK's `torch>=2.1` /
# `torchaudio>=2.1`, so pip adds only the SDK and its missing pure-python deps.
#
# Why the base is the CUDA image and not python:*-slim: the SDK's Mamba blocks
# are pure torch (`scan.selective_scan` loops one frame at a time in Python),
# which is launch-bound, not flop-bound — measured on x86 with 5 threads, the
# offline checkpoint runs 20.3 s of compute per 2 s of audio (RTF ~10) and the
# scan alone is 3133 per-frame `mul`s + 1490 `sum`s + 42 `exp`s per forward.
# There is no mamba-ssm fused kernel for this shape in the image (its `fast`
# extra is a CUDA-only compile), so the arm is GPU-served where those launches
# are cheap. The CPU route is the recorded negative, not an option.
#
# Fail-closed: a venv that cannot import the SDK stops the launch. Idempotent
# from content: the gate is a real import + version assertion on the existing
# venv, not a marker file.
set -euo pipefail

#####################################################################
# Metadata
#####################################################################
export MOD_NAME="voice-isolator-server"
export MOD_DESCRIPTION="inworld-voice-isolation venv for the inworld/voice-isolator GPU script arm"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export RUNTIME_DIR="${VOICE_ISOLATOR_RUNTIME_DIR:-${CACHEDIR}/voice-isolator}"
export VENV_DIR="${RUNTIME_DIR}/venv"
export SDK_REQ="${VOICE_ISOLATOR_SDK_REQ:-inworld-voice-isolation==1.0.0}"
# uv's symlinking gets messed up across permissions boundaries, so we copy.
export UV_LINK_MODE=copy
export USER_UID="$(stat -c '%u' /cache/runtime)"
export USER_GID="$(stat -c '%g' /cache/runtime)"

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

#####################################################################
# Rotate logs
#####################################################################
if ! [[ -d "${LOGDIR}" ]]; then mkdir -p "${LOGDIR}"; fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log.gz" ]]; then rm -f "${LOGDIR}/${MOD_NAME}.log.gz"; fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log" ]]; then gzip "${LOGDIR}/${MOD_NAME}.log" || true; fi
touch "${LOGDIR}/${MOD_NAME}.log"
reown "${LOGDIR}"

log "${MOD_NAME} - ${MOD_DESCRIPTION}"

#####################################################################
# Fail-closed gates
#####################################################################
for f in server.py fixture-noisy.wav; do
  if [[ -e "${MOD_DIR}/${f}" ]]; then log "gate OK: ${f}"; else log "gate MISSING: ${f}"; exit 1; fi
done

mkdir -p "${RUNTIME_DIR}"
reown "${RUNTIME_DIR}"

#####################################################################
# SDK venv (content-gated)
#####################################################################
# The gate is the content: an interpreter that cannot import the SDK on the
# image's CUDA torch is rebuilt, not trusted.
engine_ok() {
  [[ -x "${VENV_DIR}/bin/python" ]] || return 1
  "${VENV_DIR}/bin/python" - <<'PY' >/dev/null 2>&1
import importlib.metadata as md
assert md.version("inworld-voice-isolation") == "1.0.0", "SDK version"
import torch
assert torch.version.cuda, "torch is not a CUDA build"
import torchaudio  # noqa: F401 - the SDK's audio module imports it
from inworld import voice_isolation
assert voice_isolation.SR == 48000, "sample rate"
PY
}

if engine_ok; then
  log "engine gate OK (existing venv at ${VENV_DIR})"
else
  log "staging SDK venv at ${VENV_DIR} (${SDK_REQ}, inheriting the image's torch)"
  rm -rf "${VENV_DIR}"
  # Keep pip's cache inside our own managed dir: the ambient PIP cache path is
  # not writable here, and pip then disables caching entirely.
  export PIP_CACHE_DIR="${RUNTIME_DIR}/pip-cache"
  mkdir -p "${PIP_CACHE_DIR}"
  python3 -m venv --system-site-packages "${VENV_DIR}"
  "${VENV_DIR}/bin/python" -m pip install --quiet --upgrade pip
  "${VENV_DIR}/bin/python" -m pip install --quiet --upgrade "${SDK_REQ}"
  if engine_ok; then
    log "engine gate OK after install"
  else
    log "engine gate FAILED after install"
    exit 1
  fi
fi
log "engine versions: $("${VENV_DIR}/bin/python" -c 'import importlib.metadata as md; print(" ".join("%s %s" % (n, md.version(n)) for n in ("torch", "torchaudio", "inworld-voice-isolation")))')"

reown "${RUNTIME_DIR}"
log "RUNTIME_DIR=${RUNTIME_DIR}"
log "Done."
