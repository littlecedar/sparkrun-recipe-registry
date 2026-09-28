#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Bound the Engram-on-disk reader's host page cache.
#
# Adds a POSIX_FADV_DONTNEED after each gathered read in the installed
# models/deepseek_v4_1/common/engram.py, so read-once Engram rows are dropped
# from the host page cache instead of accumulating. One fadvise per _kai_pread_rows
# call (per batch), not per 264-byte row.
#
# THIS IS A POST-PATCH MOD. It runs AFTER @littlecedar/mods/mount-dsv41-exl3-patches
# (which installs engram.py) and edits the installed copy. It must NOT edit that
# mod's vendored files: that mod is md5-pinned to upstream d45538f6 and fails
# closed on drift. List this mod AFTER the patch mod.
#
# CONTRACT, fail-closed:
#   * The patcher is md5-verified against files/MD5SUMS.txt.
#   * The patcher's --check runs BEFORE writing, refusing on an unexpected file.
#   * The target is backed up ONCE to <target>.sparkrun-orig.
#   * Idempotence is by the marker string, not timestamps; a re-run is a no-op.
#
# WHAT IT BUYS: nothing for KV. Measured effect is only that the host page cache
# does not fill with read-once rows. Opt-in; see MEMORY-RECLAIM-PLAN.md §7.
#####################################################################

#####################################################################
# Metadata
#####################################################################
MOD_NAME="bound-engram-cache"
MOD_DESCRIPTION="Bound the Engram-on-disk reader's host page cache (opt-in)"
MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
TIMEOUT="${MOD_TIMEOUT:-180}"
MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
FILES_DIR="${MOD_DIR}/files"
PATCHER="${MOD_DIR}/patch_engram_fadvise.py"
# Resolve the installed vllm tree the same way mount-dsv41-exl3-patches does:
# never hardcode, the module has lived in site-packages and /sgl-workspace.
VLLM_BASE="$(python3 -c 'import os, vllm; print(os.path.dirname(vllm.__file__))' 2>/dev/null || true)"
TARGET="${VLLM_BASE}/models/deepseek_v4_1/common/engram.py"
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

log_cmd() {
  log "            "
  log "            "
  log "=== ${1} ==="
  "${@}" 2>&1 | log
}

die() {
  log "FATAL: ${*}"
  exit 1
}

#####################################################################
# Preflight: log dir, rotation, metadata
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

[[ -f "${PATCHER}" ]] || die "patcher not found at ${PATCHER}"
[[ -n "${VLLM_BASE}" && -d "${VLLM_BASE}" ]] || die "could not resolve vllm package dir"
# The reader must already be installed by mount-dsv41-exl3-patches, and must be
# the on-disk reader -- otherwise this mod is being listed without its sibling.
[[ -f "${TARGET}" ]] || die "engram.py not found at ${TARGET}; list mount-dsv41-exl3-patches first"
grep -q "DSV41_ENGRAM_DISK" "${TARGET}" || die "engram.py is not the on-disk reader (DSV41_ENGRAM_DISK absent)"

# md5-verify the vendored patcher against files/MD5SUMS.txt (fail-closed).
if [[ -f "${FILES_DIR}/MD5SUMS.txt" ]]; then
  log "verifying vendored patcher against files/MD5SUMS.txt"
  ( cd "${MOD_DIR}" && md5sum --check --quiet --ignore-missing "${FILES_DIR}/MD5SUMS.txt" ) \
    || die "md5 mismatch: the vendored patcher does not match files/MD5SUMS.txt"
fi

log_var TARGET

#####################################################################
# Back up the target ONCE (idempotence by presence, not timestamps)
#####################################################################
BACKUP="${TARGET}.sparkrun-orig"
if [[ ! -f "${BACKUP}" ]]; then
  log "backing up ${TARGET} -> ${BACKUP}"
  cp -p "${TARGET}" "${BACKUP}"
  reown "${BACKUP}"
else
  log "backup already exists at ${BACKUP}; not overwriting"
fi

#####################################################################
# Patch (compatibility-checked, idempotent)
#####################################################################
log "compatibility check BEFORE writing (refuses on an unexpected reader)"
log_cmd python3 "${PATCHER}" --check "${TARGET}"

log "applying the page-cache-bound patch"
log_cmd python3 "${PATCHER}" "${TARGET}"

log "compatibility check AFTER writing (must report 'already patched')"
log_cmd python3 "${PATCHER}" --check "${TARGET}"

# A stale __pycache__ would shadow the patched source.
find "$(dirname "${TARGET}")" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

reown "${LOGDIR}"
log "Done."
