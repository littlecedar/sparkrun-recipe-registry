#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Compatibility gate + launcher install for the knapcio DSV41 SGLang image
# (`dsv41-4x-spark:canary-roce`). The image already bakes the full
# adapter overlay at /opt/dsv41/adapter (on PYTHONPATH via its ENV), the
# b12x / b12x_next kernels, and /opt/dsv41/boot.py. This mod:
#
#   1. fails closed unless the image really is the overlay build (boot.py and
#      the adapter's sitecustomize.py must both be present), and
#   2. logs the resolved overlay paths so a boot is interpretable.
#
# The launcher.py in this directory is copied into the container at
# /workspace/mods/dsv41-sglang-overlay/ by sparkrun and invoked from the
# recipe's `command:` template; it maps sparkrun's appended per-node
# rendezvous flags onto boot.py's environment.
#
# NO file is modified in the image: the overlay is used as built. That is
# deliberate -- the upstream repo's own in-image test suite gates the build.
#####################################################################

#####################################################################
# Metadata
#####################################################################
MOD_NAME="dsv41-sglang-overlay"
MOD_DESCRIPTION="Compatibility gate + launcher for the knapcio DSV41 SGLang overlay image"
MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
BOOT="/opt/dsv41/boot.py"
ADAPTER="/opt/dsv41/adapter/sitecustomize.py"
B12X="/opt/b12x_next/b12x_next"
ENGINE_PY="/sgl-workspace/sglang/python/sglang/srt/layers/engram.py"

#####################################################################
# Helpers
#####################################################################

reown() {
  local uid gid
  uid="$(stat -c '%u' /cache/runtime 2>/dev/null || echo 0)"
  gid="$(stat -c '%g' /cache/runtime 2>/dev/null || echo 0)"
  chown -R "${uid}:${gid}" "${@}" 2>/dev/null || true
}

log() {
  local _message _ts
  _message="${*}"
  _ts="$(date -Ins)"
  printf '%s [%s] %s\n' "$_ts" "${MOD_NAME}" "${_message}" | tee -a "${LOGDIR}/${MOD_NAME}.log"
}

die() {
  log "FATAL: ${*}"
  exit 1
}

#####################################################################
# Preflight
#####################################################################
if ! [[ -d "${LOGDIR}" ]]; then
  mkdir -p "${LOGDIR}"
fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log.gz" ]]; then
  rm -f "${LOGDIR}/${MOD_NAME}.log.gz"
fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log" ]]; then
  gzip "${LOGDIR}/${MOD_NAME}.log"
  touch "${LOGDIR}/${MOD_NAME}.log"
fi
reown "${LOGDIR}"

log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log "${MOD_MAINTAINER}"

# The container(s) run as root (privileged), so /workspace is writable.
[[ -d /workspace/mods ]] || mkdir -p /workspace/mods

#####################################################################
# Fail-closed compatibility gate
#####################################################################
[[ -f "${BOOT}" ]] || die "boot.py not found at ${BOOT} -- image is not the canary-roce overlay build"
[[ -f "${ADAPTER}" ]] || die "adapter overlay not found at ${ADAPTER} -- image is not the canary-roce overlay build"
grep -q "EngramLoader" "${ADAPTER}" || die "sitecustomize.py at ${ADAPTER} is not the DSV41 overlay hook"
[[ -d "${B12X}" ]] || die "b12x_next not found at ${B12X} -- image is missing the fused MoE kernels"
[[ -f "${ENGINE_PY}" ]] || die "engine engram.py not found at ${ENGINE_PY}"

log_var() { log "${1}=${!1}"; }
log_var BOOT
log_var ADAPTER
log_var B12X
log_var ENGINE_PY
log "PYTHONPATH=${PYTHONPATH:-<unset>}"
log "overlay gate OK (no image files modified)"
log "Done."
