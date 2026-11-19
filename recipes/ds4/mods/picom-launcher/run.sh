#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Pre-exec staging for the picom (dsgb10) arm. The engine is Picom-code's
# from-scratch TP=4 DeepSeek-V4.1-Flash build; it is NOT an SGLang/vLLM
# server, so sparkrun launches it through the vllm-distributed family
# contract with tensor_parallel: 1 and one container per rank
# (recipes/ds4/README.md, "zz-deepseek-v4.1-flash-1017-picom-tp4-1m"; the recipe
# itself is retired to attic/ds4/).
#
# This mod owns what is environment-shaped and therefore cannot be baked
# into the image or committed to the tree: the per-node fleet file the
# engine reads at start, the runtime directories, and the API key. The
# fabric addresses are cluster-internal, so they arrive as env
# (PICOM_RANK_TAILS) and are rendered here — never stored in a tracked file
# (tests/test_tracked_address_hygiene.py).
#
# The fleet file's shape is the engine's own contract
# (upstream ds41f-4xgx10-switchless/engine/comm/fleet.cpp):
#   - NEXT_DEV0/1, PREV_DEV0/1 must exist by exact ibv name on every box;
#   - each device's GID at GID_INDEX must equal the IPv4 named for that role;
#   - one IPv4 per netdev, all four ranks' NEXT/PREV IPs listed.
# On a switched fabric (this fleet) the ring's two directions ride the same
# two f0 devices, so NEXT_DEV* == PREV_DEV* and NEXT_IP* == PREV_IP*. The
# TCP 18620 bootstrap then binds rank r's PREV_IP0 and dials rank r+1's
# PREV_IP0 — same subnet, one L2 domain on the switch.
#
# The heavy per-rank artifacts (72.38 GiB weight file, 50.7 GB Engram
# shards) are prepared by launch.sh on first boot, not here: conversion
# needs the prepared checkpoint path that only the serve command receives.
#####################################################################

#####################################################################
# Metadata
#####################################################################
export MOD_NAME="picom-launcher"
export MOD_DESCRIPTION="Stage the picom (dsgb10) fleet file, runtime dirs and API key"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export PICOM_ROOT="${PICOM_ROOT:-/cache/runtime/picom}"

#####################################################################
# Helpers (per mods/mod-template harness)
#####################################################################
reown() {
  # Chown a path to the owner of the .cache bind mount (mods run as root).
  local target="${1}"
  if [[ -e "${target}" ]]; then
    chown -R "$(stat -c '%u' /cache/runtime):$(stat -c '%g' /cache/runtime)" "${target}" || true
  fi
}

log() {
  echo "[$MOD_NAME] $*" | tee -a "${LOGDIR}/${MOD_NAME}.log"
}

log_var() {
  log "${1}=${!1}"
}

die() {
  log "FATAL: $*"
  exit 2
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
# Main: validate the fabric inputs, then render the fleet file
#####################################################################
: "${PICOM_RANK_TAILS:?set PICOM_RANK_TAILS to the four fabric address tails, rank 0-3, comma-separated (e.g. 30,31,32,33)}"
PICOM_FABRIC_A="${PICOM_FABRIC_A:-192.168.0}"
PICOM_FABRIC_B="${PICOM_FABRIC_B:-192.168.1}"
PICOM_DEV_A="${PICOM_DEV_A:-rocep1s0f0}"
PICOM_DEV_B="${PICOM_DEV_B:-roceP2p1s0f0}"
PICOM_GID_INDEX="${PICOM_GID_INDEX:-3}"
PICOM_ENGRAM_READ_BATCH="${PICOM_ENGRAM_READ_BATCH:-1}"

IFS=, read -r -a TAILS <<< "${PICOM_RANK_TAILS}"
[[ ${#TAILS[@]} -eq 4 ]] || die "PICOM_RANK_TAILS needs exactly four comma-separated octet tails, got '${PICOM_RANK_TAILS}'"
for t in "${TAILS[@]}"; do
  [[ "${t}" =~ ^[0-9]{1,3}$ ]] || die "PICOM_RANK_TAILS entry '${t}' is not an IPv4 octet"
done

for d in run logs weights engram spill fleet; do
  mkdir -p "${PICOM_ROOT}/${d}"
done

FLEET="${PICOM_ROOT}/fleet.conf"
bash "${MOD_DIR}/fleet-render.sh" "${FLEET}.new" ||
  die "fleet rendering refused the fabric inputs (see the message above)"
mv -f "${FLEET}.new" "${FLEET}"
log "rendered ${FLEET} for ranks [${PICOM_RANK_TAILS}] on ${PICOM_FABRIC_A}/${PICOM_FABRIC_B} via ${PICOM_DEV_A}/${PICOM_DEV_B}, GID ${PICOM_GID_INDEX}"

#####################################################################
# API key: dsfront refuses to start without one (mode 600)
#####################################################################
KEY="${PICOM_ROOT}/run/api-key"
if [[ ! -s "${KEY}" ]]; then
  (umask 077; head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n' > "${KEY}")
  log "generated ${KEY}"
fi
chmod 600 "${KEY}"

reown "${PICOM_ROOT}"
log "Done."
