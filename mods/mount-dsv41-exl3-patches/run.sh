#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Mounts tonyd2wild's DeepSeek-V4.1-Flash vLLM patch set into the
# container, in place, before `vllm serve` runs.
#
# Source: github.com/tonyd2wild/DeepSeek-V4.1-Flash-vLLM-DGX-Spark (MIT).
# The vendored files carry their own upstream SPDX headers (Apache-2.0 for
# the vLLM derivatives). See ./files/ for the tree and ./files/mounts.txt
# for the source->target map. The Engram-on-disk reader (engram.py +
# model_state.py + weight_utils.py) is the load-bearing one: without it the
# 203 GB Engram tables cannot leave unified RAM and a 4-node TP=4 boot OOMs.
#
# Contract, fail-closed:
#   * Every vendored file is md5-verified against files/MD5SUMS.txt.
#   * Every target must already exist in the image EXCEPT the ones listed in
#     NEW_TARGETS (files the upstream patch adds rather than replaces).
#   * Each replaced file is backed up ONCE to <target>.sparkrun-orig, so a
#     later debug can diff what changed and a re-run is idempotent.
#   * Idempotence is by reading the backup's presence, not timestamps.
#   * Ownership/mode are preserved from the original, or 0644 root:root for
#     new files.
#####################################################################

#####################################################################
# Metadata
#####################################################################
MOD_NAME="mount-dsv41-exl3-patches"
MOD_DESCRIPTION="Install tonyd2wild's DeepSeek-V4.1-Flash vLLM patch set (MIT)"
MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
TIMEOUT="${MOD_TIMEOUT:-180}"
MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
FILES_DIR="${MOD_DIR}/files"
# Files the patch ADDS (do not exist in the base image) rather than replaces.
NEW_TARGETS=" models/deepseek_v4_1/virtual_heads.py "
USER_UID="$(stat -c '%u' /cache/runtime)"
USER_GID="$(stat -c '%g' /cache/runtime)"

#####################################################################
# Helpers
#####################################################################

reown() {
  log "resetting permissions to ${USER_UID}:${USER_GID} on ${*}"
  chown -R "${USER_UID}:${USER_GID}" "${@}"
}

log() {
  local _message
  _message="${*}"
  o() {
    local _ts _message
    _message="${*}"
    _ts="$(date -Ins)"
    printf '%s [%s] %s\n' "$_ts" "${MOD_NAME}" "${_message}" | tee -a "${LOGDIR}/${MOD_NAME}.log"
    [[ -x "$(type -fp logger)" ]] && logger -t "${MOD_NAME}" -- "${_message}"
  }
  if [[ -z "${*}" ]]; then
    while read -rt "${TIMEOUT}" line; do
      o "${line}"
    done
  else
    o "${*}"
  fi
}

log_var() {
  local _key _val
  _key="${1}"
  _val="${!_key}"
  log "${_key}=${_val}"
}

die() {
  log "FATAL: ${*}"
  exit 1
}

#####################################################################
# Rotate logs
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

#####################################################################
# Main
#####################################################################
log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log "${MOD_MAINTAINER}"
log_var MOD_DIR

[[ -d "${FILES_DIR}" ]] || die "vendored files dir missing: ${FILES_DIR}"
[[ -f "${FILES_DIR}/mounts.txt" ]] || die "mounts.txt missing in ${FILES_DIR}"
[[ -f "${FILES_DIR}/MD5SUMS.txt" ]] || die "MD5SUMS.txt missing in ${FILES_DIR}"

# Resolve the installed vllm package directory. Never hardcode: the same
# module has lived in site-packages and in /sgl-workspace in other images.
VLLM_BASE="$(python3 -c 'import os, vllm; print(os.path.dirname(vllm.__file__))' \
  2>/dev/null || true)"
[[ -n "${VLLM_BASE}" && -d "${VLLM_BASE}" ]] || die "could not resolve vllm package dir"
log_var VLLM_BASE

# Verify every vendored file's md5 up front; refuse to install anything if any
# mismatches. A half-installed patch set is worse than none.
log "Verifying vendored file checksums..."
verify_fail=0
while read -r want name; do
  [[ -z "${want:-}" || -z "${name:-}" ]] && continue
  f="${FILES_DIR}/${name}"
  if [[ ! -f "${f}" ]]; then
    log "  MISSING ${name}"
    verify_fail=1
    continue
  fi
  got="$(md5sum "${f}" | awk '{print $1}')"
  if [[ "${got:0:8}" != "${want:0:8}" ]]; then
    log "  MISMATCH ${name}: want ${want} got ${got}"
    verify_fail=1
  fi
done < "${FILES_DIR}/MD5SUMS.txt"
[[ "${verify_fail}" -eq 0 ]] || die "vendored file checksum mismatch; refusing to install"

installed=0
while read -r src dst; do
  [[ -z "${src:-}" || "${src:0:1}" == "#" ]] && continue
  [[ -z "${dst:-}" ]] && continue
  SRC="${FILES_DIR}/${src}"
  if [[ "${dst:0:1}" == "/" ]]; then
    TGT="${dst}"
  else
    TGT="${VLLM_BASE}/${dst}"
  fi

  [[ -f "${SRC}" ]] || die "source file missing: ${SRC}"

  if [[ ! -e "${TGT}" ]]; then
    if [[ " ${NEW_TARGETS} " == *" ${dst} "* ]]; then
      log "installing NEW file ${dst}"
      mkdir -p "$(dirname "${TGT}")"
      install -m 0644 "${SRC}" "${TGT}.tmp"
      mv -f "${TGT}.tmp" "${TGT}"
      installed=$((installed + 1))
      continue
    fi
    die "target does not exist in image and is not in NEW_TARGETS: ${TGT}"
  fi

  # Preserve the original exactly once. Its presence is the idempotence key.
  if [[ ! -e "${TGT}.sparkrun-orig" ]]; then
    cp -p "${TGT}" "${TGT}.sparkrun-orig"
    log "backed up ${dst} -> ${dst}.sparkrun-orig"
  fi

  # Preserve mode and ownership from the (backed-up) original.
  mode="$(stat -c '%a' "${TGT}.sparkrun-orig")"
  u="$(stat -c '%u' "${TGT}.sparkrun-orig")"
  g="$(stat -c '%g' "${TGT}.sparkrun-orig")"
  install -m "${mode}" -o "${u}" -g "${g}" "${SRC}" "${TGT}.tmp"
  mv -f "${TGT}.tmp" "${TGT}"
  log "installed ${dst} (mode ${mode}, uid ${u}, gid ${g})"
  installed=$((installed + 1))
done < "${FILES_DIR}/mounts.txt"

log "Installed ${installed} file(s)."

# Sanity: the Engram-on-disk reader must have landed, or the whole point is
# missed and the launch will OOM ~25 minutes in instead of failing here.
if [[ -f "${VLLM_BASE}/models/deepseek_v4_1/common/engram.py" ]]; then
  if ! grep -q "DSV41_ENGRAM_DISK" "${VLLM_BASE}/models/deepseek_v4_1/common/engram.py"; then
    die "engram.py installed but DSV41_ENGRAM_DISK absent -- wrong patch tree?"
  fi
  log "verified: Engram-on-disk reader present (DSV41_ENGRAM_DISK)"
else
  die "engram.py target missing after install"
fi

reown "${LOGDIR}"
log "Done."
