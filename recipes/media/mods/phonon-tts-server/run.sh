#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Pre-launch mod for the gradium/phonon-31m-en CPU TTS arm (media lane).
#
# The engine is the `ptts` CLI (PyPI `ptts`, the vendor runtime behind the
# phonon-31m-en card) — no LLM engine serves a 31M TTS, so the arm is a small
# Python server behind the `runtime: vllm` launcher/distribution contract, the
# kokoro/laya/pyannote precedent. This mod stages what the server needs:
#
#   1. A venv on the recipe's python:3.12-slim base carrying `ptts` (pinned
#      floor 0.4.1 — the aarch64 manylinux wheel measured on this fleet).
#   2. A REAL-FILE copy of the checkpoint snapshot under
#      ${RUNTIME_DIR}/model/ — ptts' checkpoint check walks the directory, and
#      a symlinked HF snapshot (relative ../../blobs links) fails it inside a
#      container; measured 2026-10-25, which is why this is a copy, not a bind.
#
# Fail-closed: a failed stage stops the launch rather than starting a server
# that cannot render. Idempotent from content: the gate runs `ptts --version`
# on the existing venv, not a marker file.
set -euo pipefail

#####################################################################
# Metadata
#####################################################################
export MOD_NAME="phonon-tts-server"
export MOD_DESCRIPTION="ptts venv + real-file model copy for the phonon-31m-en CPU TTS arm"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export RUNTIME_DIR="${PHONON_RUNTIME_DIR:-${CACHEDIR}/phonon}"
export VENV_DIR="${RUNTIME_DIR}/venv"
export MODEL_DIR="${RUNTIME_DIR}/model"
export MODEL_REPO="/cache/huggingface/hub/models--gradium--phonon-31m-en"
export REVISION="${PHONON_REVISION:-}"
export PTTS_REQ="${PHONON_PTTS_REQ:-ptts==0.4.1}"
export USER_UID="$(stat -c '%u' /cache/runtime)"
export USER_GID="$(stat -c '%g' /cache/runtime)"

reown() {
  if [[ "$(id -u)" -eq 0 ]]; then
    chown -R "${USER_UID}:${USER_GID}" "${@}" || true
  fi
}

log() {
  local _ts
  _ts="$(date -Ins)"
  printf '%s [%s] %s\n' "$_ts" "${MOD_NAME}" "${*}" | tee -a "${LOGDIR}/${MOD_NAME}.log"
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
if [[ -e "${MOD_DIR}/server.py" ]]; then log "gate OK: server.py"; else log "gate MISSING: server.py"; exit 1; fi
if [[ -d "${MODEL_REPO}" ]]; then log "gate OK: ${MODEL_REPO}"; else log "gate MISSING: ${MODEL_REPO}"; exit 1; fi

# Resolve the revision: an explicit env wins, else the single staged snapshot.
if [[ -z "${REVISION}" ]]; then
  snapshots=("${MODEL_REPO}"/snapshots/*/)
  if [[ ${#snapshots[@]} -ne 1 ]]; then
    log "gate FAILED: expected exactly one staged snapshot, found ${#snapshots[@]}; set PHONON_REVISION"
    exit 1
  fi
  REVISION="$(basename "${snapshots[0]}")"
fi
SNAPSHOT="${MODEL_REPO}/snapshots/${REVISION}"
if [[ -f "${SNAPSHOT}/model.q8.gguf" ]]; then
  log "gate OK: snapshot ${REVISION} carries model.q8.gguf"
else
  log "gate MISSING: ${SNAPSHOT}/model.q8.gguf"
  exit 1
fi

#####################################################################
# Server + real-file model copy (idempotent by size)
#####################################################################
mkdir -p "${RUNTIME_DIR}" "${MODEL_DIR}"
# The server itself goes to a stable cache path so the recipe's command can name it
# unconditionally (the mods staging dir is not part of the serving contract).
cp "${MOD_DIR}/server.py" "${RUNTIME_DIR}/server.py"
log "server staged at ${RUNTIME_DIR}/server.py"

# -L dereferences the snapshot's relative blobs links; the copy is what ptts
# reads, so it must be real files with real bytes.
copied=0
for f in "${SNAPSHOT}"/*; do
  name="$(basename "${f}")"
  target="${MODEL_DIR}/${name}"
  src_size="$(stat -Lc '%s' "${f}")"
  if [[ -f "${target}" && "$(stat -c '%s' "${target}")" == "${src_size}" ]]; then
    continue
  fi
  cp -L "${f}" "${target}"
  copied=$((copied + 1))
done
log "model copy settled (${copied} file(s) copied this pass)"

# Content gate: the q8 gguf must be a real file with the snapshot's size.
q8_snapshot="$(stat -Lc '%s' "${SNAPSHOT}/model.q8.gguf")"
q8_target="$(stat -c '%s' "${MODEL_DIR}/model.q8.gguf")"
if [[ "${q8_snapshot}" == "${q8_target}" && "${q8_target}" -gt 1000000 ]]; then
  log "engine gate OK: model.q8.gguf ${q8_target} B"
else
  log "engine gate FAILED: model.q8.gguf size mismatch (${q8_target} vs ${q8_snapshot})"
  exit 1
fi

#####################################################################
# ptts venv (content-gated)
#####################################################################
engine_ok() {
  [[ -x "${VENV_DIR}/bin/ptts" ]] || return 1
  "${VENV_DIR}/bin/ptts" --help >/dev/null 2>&1
}

if engine_ok; then
  log "engine gate OK (existing venv at ${VENV_DIR})"
else
  log "staging ptts venv at ${VENV_DIR} (${PTTS_REQ})"
  rm -rf "${VENV_DIR}"
  export PIP_CACHE_DIR="${RUNTIME_DIR}/pip-cache"
  mkdir -p "${PIP_CACHE_DIR}"
  python3 -m venv "${VENV_DIR}"
  "${VENV_DIR}/bin/python" -m pip install --quiet --upgrade pip
  "${VENV_DIR}/bin/python" -m pip install --quiet "${PTTS_REQ}"
  if engine_ok; then
    log "engine gate OK after install ($(basename "${VENV_DIR}") ptts ready)"
  else
    log "engine gate FAILED after install"
    exit 1
  fi
fi

reown "${RUNTIME_DIR}"
log "RUNTIME_DIR=${RUNTIME_DIR}"
log "REVISION=${REVISION}"
log "Done."
