#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Pre-exec staging for the dual-name ("weightless") arm. The engine reads a GLP
# control vector — per-layer unit directions, no weights — and projects it out
# of the residual stream for requests addressed to the steered served name.
#
# This mod owns exactly one thing: the file must be on every node, at a path the
# recipe can name, with the bytes the vector's author published. It never
# downloads: the vector arrives through the recipe's second distribution entry
# (the hub cache), and a boot without it must fail here rather than serve an
# unsteered model under the steered name.
#
# The vector's own licence is MIT; the repository is access-gated (a Responsible
# Use Agreement accepted once per account), which is why the failure message
# carries the exact `hf download` line instead of fetching anything itself.
#####################################################################

#####################################################################
# Metadata
#####################################################################
export MOD_NAME="glp-vector-stage"
export MOD_DESCRIPTION="Stage and verify the GLP steering vector on every node"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export GLP_ROOT="${GLP_ROOT:-/cache/runtime/glp}"
export VECTOR_DEST="${GLP_ROOT}/vector.gguf"

# The published vector, pinned by revision and digest (upstream
# config/cluster.json `glp`; docs/setup.md §"GLP steering file").
export GLP_REPO="msuiche/DeepSeek-V4.1-Flash-1017-abliterated-cyber-GLP-39-L1-39-a0.75"
export GLP_REVISION="2715ffd51f59899115853e1118db080536966c44"
export GLP_FILE="glp.deepseek-v41-flash-1017-GLP-39-L1-39-a0.75.gguf"
export GLP_SHA256="9c66d47701e0ceb42c33906f2d3789c0f1f16b21e7d97185f20f7f3f09fbf5cf"
# Hugging Face names a repo directory after its id, with "/" -> "--".
export GLP_REPO_DIR="models--msuiche--DeepSeek-V4.1-Flash-1017-abliterated-cyber-GLP-39-L1-39-a0.75"

#####################################################################
# Helpers (per mods/mod-template harness)
#####################################################################
reown() {
  # Chown a path to the owner of the .cache bind mount (mods run as root).
  local target="${1}" uid gid
  [[ -e "${target}" ]] || return 0
  uid=$(stat -c '%u' /cache/runtime 2>/dev/null) || uid=0
  gid=$(stat -c '%g' /cache/runtime 2>/dev/null) || gid=0
  chown -R "${uid}:${gid}" "${target}" 2>/dev/null || true
}

log() {
  echo "[$MOD_NAME] $*" | tee -a "${LOGDIR}/${MOD_NAME}.log"
}

log_var() {
  log "${1}=${!1:-}"
}

die() {
  log "FATAL: $*"
  exit 2
}

# /cache/runtime is sparkrun's runtime-cache bind mount (core/runtime_cache.py:
# RUNTIME_CACHE_CONTAINER_PATH), so it is a different filesystem from the
# container's overlay root. With the cache disabled the staged vector would land
# in the overlay and vanish with the container, and the next boot would fail at
# a point where the engine has already loaded 72 GiB of weights — refuse here,
# where a non-zero mod exit tears the launch down.
require_runtime_cache_mount() {
  local root_dev base_dev
  root_dev=$(stat -c %d / 2>/dev/null) || root_dev=""
  base_dev=$(stat -c %d "${GLP_ROOT%/*}" 2>/dev/null) || base_dev=""
  if [[ -z "${base_dev}" || "${base_dev}" == "${root_dev}" ]]; then
    die "runtime cache is not mounted: ${GLP_ROOT%/*} is the container overlay, not sparkrun's runtime-cache bind mount — drop SPARKRUN_NO_RUNTIME_CACHE or re-enable runtime_cache"
  fi
}

sha256_of() {
  sha256sum "${1}" 2>/dev/null | cut -d' ' -f1
}

download_hint() {
  cat <<EOF
  hf download ${GLP_REPO} \\
    ${GLP_FILE} \\
    --revision ${GLP_REVISION}
EOF
}

#####################################################################
# Rotate logs
#####################################################################
mkdir -p "${LOGDIR}"
if [[ -f "${LOGDIR}/${MOD_NAME}.log.gz" ]]; then
  rm -f "${LOGDIR}/${MOD_NAME}.log.gz"
fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log" ]]; then
  gzip -c "${LOGDIR}/${MOD_NAME}.log" > "${LOGDIR}/${MOD_NAME}.log.gz"
  rm -f "${LOGDIR}/${MOD_NAME}.log"
fi
reown "${LOGDIR}"

log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log "${MOD_MAINTAINER}"

#####################################################################
# 1. The staged copy must survive the container
#####################################################################
require_runtime_cache_mount
mkdir -p "${GLP_ROOT}"

#####################################################################
# 2. Resolve the vector in the hub cache
#####################################################################
# sparkrun injects HF_HOME; the fallback is the same path its mount uses.
HUB_ROOT="${HF_HOME:-/cache/huggingface}/hub"
log_var HUB_ROOT
log_var GLP_REPO
log_var GLP_REVISION

SOURCE=""
for candidate in \
  "${HUB_ROOT}/${GLP_REPO_DIR}/snapshots/${GLP_REVISION}/${GLP_FILE}" \
  "${HUB_ROOT}/${GLP_REPO_DIR}"/snapshots/"${GLP_REVISION}"*/"${GLP_FILE}" \
  "${HUB_ROOT}/${GLP_REPO_DIR}"/snapshots/*/"${GLP_FILE}"; do
  if [[ -f "${candidate}" ]]; then
    SOURCE="${candidate}"
    break
  fi
done

if [[ -z "${SOURCE}" ]]; then
  log "Looked under: ${HUB_ROOT}/${GLP_REPO_DIR}/snapshots/"
  die "the GLP steering vector is not on this node (${GLP_FILE} @ ${GLP_REVISION}); the recipe's distribution entry must reach every rank before a boot. Accept the gated repository's agreement once, then on this node:
$(download_hint)"
fi
log "source: ${SOURCE}"

#####################################################################
# 3. Verify the bytes
#####################################################################
ACTUAL_SHA="$(sha256_of "${SOURCE}")"
if [[ "${ACTUAL_SHA}" != "${GLP_SHA256}" ]]; then
  die "GLP vector digest mismatch at ${SOURCE}: expected ${GLP_SHA256}, got ${ACTUAL_SHA:-<unreadable>} — the file is truncated, a partial download, or a different revision; re-fetch it:
$(download_hint)"
fi

#####################################################################
# 4. Stage it: idempotent on content, atomic on write
#####################################################################
if [[ -f "${VECTOR_DEST}" ]] && [[ "$(sha256_of "${VECTOR_DEST}")" == "${GLP_SHA256}" ]]; then
  log "already staged: ${VECTOR_DEST} (${GLP_SHA256})"
else
  TMP="${VECTOR_DEST}.new.$$"
  cp -f "${SOURCE}" "${TMP}"
  STAGED_SHA="$(sha256_of "${TMP}")"
  if [[ "${STAGED_SHA}" != "${GLP_SHA256}" ]]; then
    rm -f "${TMP}"
    die "copy to ${VECTOR_DEST} did not verify: expected ${GLP_SHA256}, got ${STAGED_SHA:-<unreadable>}"
  fi
  mv -f "${TMP}" "${VECTOR_DEST}"
  log "staged: ${SOURCE} -> ${VECTOR_DEST}"
fi

#####################################################################
# 5. Hand it to the user who owns the cache
#####################################################################
reown "${GLP_ROOT}"

#####################################################################
# 6. Log what the serve phase will read
#####################################################################
log "vector: ${VECTOR_DEST} ($(stat -c '%s' "${VECTOR_DEST}") bytes, sha256 ${GLP_SHA256})"
log "Done."
