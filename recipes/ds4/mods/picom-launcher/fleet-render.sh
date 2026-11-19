#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
# Render the picom engine's fleet file (engine/comm/fleet.cpp schema upstream).
# Usage: fleet-render.sh OUT
# Env: PICOM_RANK_TAILS (4 comma-separated tails, rank 0-3);
#      PICOM_FABRIC_A/B, PICOM_DEV_A/B, PICOM_GID_INDEX (resolved by run.sh from
#      sparkrun's injected NCCL_IB_HCA/GID or the device GIDs), PICOM_ENGRAM_READ_BATCH,
#      PICOM_ROOT (artifact paths in the file).
# Fails closed on any input the engine would reject at start: wrong tail count,
# non-octet tails, or a missing PICOM_ROOT.
set -euo pipefail

OUT="${1:?usage: fleet-render.sh OUT}"
ROOT="${PICOM_ROOT:-/cache/runtime/picom}"

: "${PICOM_RANK_TAILS:?PICOM_RANK_TAILS missing (four comma-separated address tails, rank 0-3)}"
# Resolved by run.sh (sparkrun's NCCL_IB_HCA/GID or sysfs); no literals live here.
: "${PICOM_FABRIC_A:?PICOM_FABRIC_A missing: run.sh resolves it from the RoCE GIDs}"
: "${PICOM_FABRIC_B:?PICOM_FABRIC_B missing: run.sh resolves it from the RoCE GIDs}"
: "${PICOM_DEV_A:?PICOM_DEV_A missing: run.sh resolves it from the RoCE GIDs}"
: "${PICOM_DEV_B:?PICOM_DEV_B missing: run.sh resolves it from the RoCE GIDs}"
: "${PICOM_GID_INDEX:?PICOM_GID_INDEX missing: run.sh resolves it from the RoCE GIDs}"
PICOM_ENGRAM_READ_BATCH="${PICOM_ENGRAM_READ_BATCH:-1}"

IFS=, read -r -a TAILS <<< "${PICOM_RANK_TAILS}"
[[ ${#TAILS[@]} -eq 4 ]] || {
  echo "fleet-render: PICOM_RANK_TAILS needs exactly four comma-separated octet tails, got '${PICOM_RANK_TAILS}'" >&2
  exit 2
}
for t in "${TAILS[@]}"; do
  [[ "${t}" =~ ^[0-9]{1,3}$ ]] || {
    echo "fleet-render: PICOM_RANK_TAILS entry '${t}' is not an IPv4 octet" >&2
    exit 2
  }
done

{
  echo "# rendered by fleet-render.sh at launch; do not edit (engine/comm/fleet.cpp schema)"
  # Switched fabric: ring directions share the two f0 devices (see the mod README).
  echo "NEXT_DEV0=${PICOM_DEV_A}"
  echo "NEXT_DEV1=${PICOM_DEV_B}"
  echo "PREV_DEV0=${PICOM_DEV_A}"
  echo "PREV_DEV1=${PICOM_DEV_B}"
  echo "GID_INDEX=${PICOM_GID_INDEX}"
  for r in 0 1 2 3; do
    echo "RANK${r}_NEXT_IP0=${PICOM_FABRIC_A}.${TAILS[${r}]}"
    echo "RANK${r}_NEXT_IP1=${PICOM_FABRIC_B}.${TAILS[${r}]}"
    echo "RANK${r}_PREV_IP0=${PICOM_FABRIC_A}.${TAILS[${r}]}"
    echo "RANK${r}_PREV_IP1=${PICOM_FABRIC_B}.${TAILS[${r}]}"
  done
  for r in 0 1 2 3; do
    echo "RANK${r}_WEIGHTS=${ROOT}/weights/rank${r}.dsw"
    echo "RANK${r}_HASHMAP=${ROOT}/engram/engram_hashmap.bin"
    echo "RANK${r}_ENGRAM=${ROOT}/engram"
    echo "RANK${r}_ENGRAM_READ_BATCH=${PICOM_ENGRAM_READ_BATCH}"
    echo "RANK${r}_SPILL=${ROOT}/spill"
  done
} > "${OUT}"
