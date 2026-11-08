#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Engram shard-6 link for `deepseek-v4.1-flash-1017-gsq-rco-coder-gguf-llamacpp.yaml`.
# The card's GGUF is split as six shards: `IQ2_XXS/...-0000i-of-00006.gguf` for
# i = 1..5 (transformer) and the Engram tables as the SIXTH shard — but the repo
# stores that file at its root, named `DeepSeek-V4.1-Flash-Engram-IQ4_NL.gguf`,
# not on shard 6's path. llama.cpp opens shards 2..6 from the directory `-m` points
# at, so shard 6 must exist under the IQ2_XXS/ name before the serve starts.
#
# This mod creates that link inside the prepared snapshot. It is idempotent
# (`ln -sfn`), fail-closed when no source file is on the node, and never touches
# the network: the Engram file is byte-identical to the unpruned GSQ-RCO release's,
# so when that repo is already in the shared pool the link points across snapshots
# instead of asking for a second 110.60 GB download.
#####################################################################

#####################################################################
# Metadata
#####################################################################
export MOD_NAME="dsv41-engram-shard-link"
export MOD_DESCRIPTION="Link the DeepSeek-V4.1 GSQ-RCO Coder Engram file into the snapshot as GGUF shard 6"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export HFHUB="${MOD_HF_HUB:-/cache/huggingface/hub}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
# The Coder repo this recipe serves; the shard-1 glob identifies its snapshot.
export CODER_REPO_DIR="models--ISTA-DASLab--DeepSeek-V4.1-Flash-1017-GSQ-RCO-Coder-GGUF"
export ENGRAM_NAME="DeepSeek-V4.1-Flash-Engram-IQ4_NL.gguf"
export SHARD6_NAME="DeepSeek-V4.1-Flash-1017-GSQ-RCO-Coder-IQ2_XXS-00006-of-00006.gguf"
export MIN_ENGRAM_BYTES=$((90 * 1024 * 1024 * 1024))

#####################################################################
# Helpers (per mods/mod-template harness)
#####################################################################
reown() {
  # Mods run as root; hand paths back to the cache owner. The link itself needs
  # -h, because chown follows symlinks by default and must not chown the 110 GB blob.
  local path
  for path in "$@"; do
    [[ -e "${path}" || -L "${path}" ]] || continue
    chown -hR "$(stat -c '%u' /cache/runtime):$(stat -c '%g' /cache/runtime)" "${path}" 2>/dev/null || true
  done
}

log() {
  echo "[${MOD_NAME}] $*" | tee -a "${LOGDIR}/${MOD_NAME}.log"
}

log_var() {
  log "${1}=${!1}"
}

#####################################################################
# Rotate logs
#####################################################################
mkdir -p "${LOGDIR}"
reown "${LOGDIR}"

log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log "${MOD_MAINTAINER}"

#####################################################################
# Main: find the snapshot, find the Engram file, link it
#####################################################################
REPO_DIR="${HFHUB}/${CODER_REPO_DIR}"
# Resolve the snapshot the runtime actually serves: sparkrun prepares by revision and
# writes no refs/ for a SHA-keyed download, so `refs/main` may be absent — try it, then
# every snapshot directory, then fall back to a bounded depth walk. The refs/ path is
# first because a depth constant is only correct for one nesting shape.
SHARD_NAME='DeepSeek-V4.1-Flash-1017-GSQ-RCO-Coder-IQ2_XXS-00001-of-00006.gguf'
SHARD1=""
REF="$(cat "${REPO_DIR}/refs/main" 2>/dev/null || true)"
if [[ -n "${REF}" && -f "${REPO_DIR}/snapshots/${REF}/IQ2_XXS/${SHARD_NAME}" ]]; then
  SHARD1="${REPO_DIR}/snapshots/${REF}/IQ2_XXS/${SHARD_NAME}"
fi
if [[ -z "${SHARD1}" ]]; then
  for candidate in "${REPO_DIR}"/snapshots/*/IQ2_XXS/"${SHARD_NAME}"; do
    if [[ -f "${candidate}" ]]; then
      SHARD1="${candidate}"
    fi
  done
fi
if [[ -z "${SHARD1}" ]]; then
  SHARD1="$(find "${REPO_DIR}/snapshots" -mindepth 1 -maxdepth 4 \
    -name "${SHARD_NAME}" -type f -print 2>/dev/null | sort | tail -n 1 || true)"
fi
if [[ -z "${SHARD1}" ]]; then
  log "FATAL: no prepared snapshot holds shard 1 under ${HFHUB}/${CODER_REPO_DIR}/snapshots."
  log "       The recipe's model spec must select the IQ2_XXS shard set, and the model"
  log "       must be pre-synced before mods run."
  exit 2
fi
SHARD_DIR="$(dirname "${SHARD1}")"
SNAPSHOT_DIR="$(dirname "${SHARD_DIR}")"
LINK="${SHARD_DIR}/${SHARD6_NAME}"
log_var LINK

# Source: this snapshot's own copy first, else any node copy of the identical file
# (the unpruned GSQ-RCO release ships the same bytes as its own shard 6).
SOURCE="${SNAPSHOT_DIR}/${ENGRAM_NAME}"
if [[ ! -s "${SOURCE}" ]]; then
  SOURCE="$(find "${HFHUB}" -mindepth 4 -maxdepth 4 -name "${ENGRAM_NAME}" -type f \
    -size +1G -printf '%s %p\n' 2>/dev/null | sort -rn | head -n 1 | cut -d' ' -f2- || true)"
fi
if [[ -z "${SOURCE}" || ! -s "${SOURCE}" ]]; then
  log "FATAL: no ${ENGRAM_NAME} on this node. Shard 6 is the Engram table set and the"
  log "       serve cannot start without it; it is NOT downloaded here (no network in a"
  log "       mod). Stage it into the pool once, outside the boot:"
  log "         hf download ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-Coder-GGUF \\"
  log "           --include '*Engram*'"
  exit 3
fi
log_var SOURCE

SIZE="$(stat -c '%s' "${SOURCE}")"
if (( SIZE < MIN_ENGRAM_BYTES )); then
  log "FATAL: ${SOURCE} is ${SIZE} B, below the ${MIN_ENGRAM_BYTES} B floor for the two"
  log "       Engram tables (card: 110.60 GB). Refusing to boot on a truncated file."
  exit 4
fi

if [[ -L "${LINK}" && "$(readlink -f "${LINK}")" == "$(readlink -f "${SOURCE}")" ]]; then
  log "shard 6 already links ${SOURCE} (${SIZE} B) - no-op"
else
  ln -sfn "${SOURCE}" "${LINK}"
  log "linked ${LINK} -> ${SOURCE} (${SIZE} B)"
fi
reown "${LINK}" "${SHARD_DIR}"

[[ "$(readlink -f "${LINK}")" == "$(readlink -f "${SOURCE}")" ]] || {
  log "FATAL: link did not resolve to the Engram file"
  exit 5
}
log "Done."
