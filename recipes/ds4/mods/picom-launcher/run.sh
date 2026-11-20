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
  log "${1}=${!1:-}"
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
# Fabric inputs: operator override, else sparkrun's detection, else sysfs
#####################################################################
# sparkrun detects the RoCE fabric on every host and injects NCCL_IB_HCA (the
# ACTIVE devices) and NCCL_IB_GID_INDEX into the container
# (orchestration/infiniband.py:246-259). It passes no rail address, so the two
# /24s come from each device's own IPv4-mapped RoCE v2 GID in sysfs — the entry
# the engine re-checks the fleet file against at start.
PICOM_IB_SYSFS="${PICOM_IB_SYSFS:-/sys/class/infiniband}"

# DEV IDX -> the IPv4 that GID carries, empty when the entry is missing or is
# not IPv4-mapped RoCE v2 (an fe80:: link-local GID is not a fabric address).
gid_ipv4() {
  local dev="${1}" idx="${2}" base type gid hi lo
  base="${PICOM_IB_SYSFS}/${dev}/ports/1"
  type=$(cat "${base}/gid_attrs/types/${idx}" 2>/dev/null) || return 0
  [[ "${type}" == *"RoCE v2"* ]] || return 0
  gid=$(cat "${base}/gids/${idx}" 2>/dev/null) || return 0
  [[ "${gid}" == 0000:0000:0000:0000:0000:ffff:* ]] || return 0
  hi=${gid##*:ffff:}
  hi=${hi%%:*}
  lo=${gid##*:}
  printf '%d.%d.%d.%d\n' "$((16#${hi} >> 8))" "$((16#${hi} & 255))" "$((16#${lo:0:2}))" "$((16#${lo:2:2}))"
}

# DEV -> "<index> <ipv4>" of its first IPv4-mapped RoCE v2 GID, numeric order.
gid_first_ipv4() {
  local dev="${1}" idx ip
  for idx in $(ls "${PICOM_IB_SYSFS}/${dev}/ports/1/gid_attrs/types" 2>/dev/null | sort -n); do
    ip=$(gid_ipv4 "${dev}" "${idx}")
    if [[ -n "${ip}" ]]; then
      printf '%s %s\n' "${idx}" "${ip}"
      return 0
    fi
  done
}

# NAME DEV NET -> die unless DEV's GID at PICOM_GID_INDEX is a NET.x address.
verify_fabric() {
  local which="${1}" dev="${2}" net="${3}" ip
  ip=$(gid_ipv4 "${dev}" "${PICOM_GID_INDEX}")
  [[ -n "${ip}" ]] ||
    die "${which}: ${dev} has no IPv4-mapped RoCE v2 GID at index ${PICOM_GID_INDEX}: the engine's fleet check would refuse every rank"
  [[ "${ip%.*}" == "${net}" ]] ||
    die "${which}: ${dev} GID ${PICOM_GID_INDEX} is ${ip}, not a ${net}.0/24 address"
}

resolve_fabric() {
  local -a pairs=()
  local dev ip
  if [[ -n "${PICOM_DEV_A:-}" && -z "${PICOM_DEV_B:-}" ]] ||
    [[ -z "${PICOM_DEV_A:-}" && -n "${PICOM_DEV_B:-}" ]]; then
    die "set PICOM_DEV_A and PICOM_DEV_B together, or neither (sparkrun's NCCL_IB_HCA then names them)"
  fi
  if [[ -z "${PICOM_DEV_A:-}" ]]; then
    [[ -n "${NCCL_IB_HCA:-}" ]] ||
      die "PICOM_DEV_A/PICOM_DEV_B unset and sparkrun injected no NCCL_IB_HCA: no RoCE device source"
    for dev in ${NCCL_IB_HCA//,/ }; do
      ip=$(gid_first_ipv4 "${dev}")
      if [[ -n "${ip}" ]]; then
        pairs+=("${ip#* } ${dev}")
      fi
    done
    mapfile -t pairs < <(printf '%s\n' "${pairs[@]}" | sort)
    [[ ${#pairs[@]} -ge 2 ]] ||
      die "NCCL_IB_HCA='${NCCL_IB_HCA}' names fewer than two devices with an IPv4-mapped RoCE v2 GID"
    read -r ip PICOM_DEV_A <<< "${pairs[0]}"
    read -r ip PICOM_DEV_B <<< "${pairs[1]}"
    [[ "${PICOM_DEV_A}" != "${PICOM_DEV_B}" ]] ||
      die "NCCL_IB_HCA names one usable device ('${PICOM_DEV_A}'): the engine's switched ring needs two"
  fi
  if [[ -z "${PICOM_FABRIC_A:-}" || -z "${PICOM_FABRIC_B:-}" ]]; then
    ip=$(gid_first_ipv4 "${PICOM_DEV_A}")
    PICOM_FABRIC_A="${PICOM_FABRIC_A:-$(printf '%s' "${ip#* }" | cut -d. -f1-3)}"
    ip=$(gid_first_ipv4 "${PICOM_DEV_B}")
    PICOM_FABRIC_B="${PICOM_FABRIC_B:-$(printf '%s' "${ip#* }" | cut -d. -f1-3)}"
  fi
  if [[ -z "${PICOM_GID_INDEX:-}" ]]; then
    PICOM_GID_INDEX="${NCCL_IB_GID_INDEX:-}"
    if [[ ! "${PICOM_GID_INDEX}" =~ ^[0-9]+$ ]]; then
      PICOM_GID_INDEX=$(gid_first_ipv4 "${PICOM_DEV_A}")
      PICOM_GID_INDEX="${PICOM_GID_INDEX%% *}"
    fi
  fi
  [[ "${PICOM_GID_INDEX}" =~ ^[0-9]+$ ]] ||
    die "PICOM_GID_INDEX='${PICOM_GID_INDEX}' is not a GID index and ${PICOM_DEV_A} carries no IPv4-mapped RoCE v2 GID"
  verify_fabric A "${PICOM_DEV_A}" "${PICOM_FABRIC_A}"
  verify_fabric B "${PICOM_DEV_B}" "${PICOM_FABRIC_B}"
}

#####################################################################
# Main: resolve the fabric, publish what the serve phase needs, render the fleet
#####################################################################
# The four tails are no longer an operator input. sparkrun exports no host list
# to a recipe (core/env_templates.py:19 LAUNCH_FIELDS is closed), but the
# pre_exec hook environment carries rank 0's management address and this node's
# rank (orchestration/hooks.py:110-125, quoted in README.md). The serve phase
# (launch.sh) runs concurrently on all four nodes and exchanges the tails there;
# PICOM_RANK_TAILS stays an explicit override and is validated as before.
PICOM_ENGRAM_READ_BATCH="${PICOM_ENGRAM_READ_BATCH:-1}"

resolve_fabric
: "${PICOM_NODE_RANK:?PICOM_NODE_RANK missing: the recipe must render it from the launch node_rank template}"
own_ip=$(gid_ipv4 "${PICOM_DEV_A}" "${PICOM_GID_INDEX}")
own_tail="${own_ip##*.}"
[[ -n "${own_tail}" ]] ||
  die "this node's ${PICOM_DEV_A} GID ${PICOM_GID_INDEX} carries no IPv4 address; cannot learn this rank's rail tail"
log "fabric resolved: A=${PICOM_FABRIC_A}/24 via ${PICOM_DEV_A}, B=${PICOM_FABRIC_B}/24 via ${PICOM_DEV_B}, GID ${PICOM_GID_INDEX}"
log_var PICOM_DEV_A
log_var PICOM_DEV_B
log_var PICOM_FABRIC_A
log_var PICOM_FABRIC_B
log_var PICOM_GID_INDEX
log_var PICOM_NODE_RANK
log_var PICOM_NODE_HOST
# Consumed, not assumed: sparkrun's own hook environment and container env.
log_var SPARKRUN_NODE_HOST
log_var SPARKRUN_HEAD_HOST
log_var SPARKRUN_CLUSTER_ID
log_var HF_HOME

for d in run logs weights engram spill fleet; do
  mkdir -p "${PICOM_ROOT}/${d}"
done

FLEET="${PICOM_ROOT}/fleet.conf"
FABRIC_ENV="${PICOM_ROOT}/fabric.env"
# launch.sh is a separate process with only the container env; the hook-only
# SPARKRUN_* values and this node's own tail are carried over here.
{
  echo "PICOM_FABRIC_A=${PICOM_FABRIC_A}"
  echo "PICOM_FABRIC_B=${PICOM_FABRIC_B}"
  echo "PICOM_DEV_A=${PICOM_DEV_A}"
  echo "PICOM_DEV_B=${PICOM_DEV_B}"
  echo "PICOM_GID_INDEX=${PICOM_GID_INDEX}"
  echo "PICOM_RANK=${PICOM_NODE_RANK}"
  echo "PICOM_OWN_TAIL=${own_tail}"
  echo "PICOM_HEAD=${SPARKRUN_HEAD_HOST:-}"
  echo "PICOM_CACHE=${HF_HOME:-/cache/huggingface}"
} > "${FABRIC_ENV}.new"
mv -f "${FABRIC_ENV}.new" "${FABRIC_ENV}"

if [[ -n "${PICOM_RANK_TAILS:-}" ]]; then
  IFS=, read -r -a TAILS <<< "${PICOM_RANK_TAILS}"
  [[ ${#TAILS[@]} -eq 4 ]] || die "PICOM_RANK_TAILS needs exactly four comma-separated octet tails, got '${PICOM_RANK_TAILS}'"
  for t in "${TAILS[@]}"; do
    [[ "${t}" =~ ^[0-9]{1,3}$ ]] || die "PICOM_RANK_TAILS entry '${t}' is not an IPv4 octet"
  done
  # Check this rank's entry against the rail rather than trusting it: a stale
  # list fails here, not in a peer's QP.
  [[ "${TAILS[${PICOM_NODE_RANK}]}" == "${own_tail}" ]] ||
    die "PICOM_RANK_TAILS[${PICOM_NODE_RANK}]='${TAILS[${PICOM_NODE_RANK}]}' but this node's ${PICOM_DEV_A} GID ${PICOM_GID_INDEX} is ${own_ip:-absent}"
  export PICOM_FABRIC_A PICOM_FABRIC_B PICOM_DEV_A PICOM_DEV_B PICOM_GID_INDEX
  bash "${MOD_DIR}/fleet-render.sh" "${FLEET}.new" ||
    die "fleet rendering refused the fabric inputs (see the message above)"
  mv -f "${FLEET}.new" "${FLEET}"
  log "rendered ${FLEET} from PICOM_RANK_TAILS=[${PICOM_RANK_TAILS}] on ${PICOM_FABRIC_A}/${PICOM_FABRIC_B} via ${PICOM_DEV_A}/${PICOM_DEV_B}, GID ${PICOM_GID_INDEX}"
else
  log "tails not supplied: rank ${PICOM_NODE_RANK} of ${SPARKRUN_HEAD_HOST:-<no head address>} will meet the others in launch.sh (port 19110)"
fi

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
