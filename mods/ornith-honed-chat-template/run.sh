#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Stage the honed Ornith chat template where sglang's --chat-template can
# read it. See README.md in this directory for the full story; short version:
#
# The ornith lane's verified boot surface serves a community-honed chat
# template (qwen3.8-honed-v22.5.1, 30,438 B) instead of the checkpoint's
# upstream template. The honed file was once injected directly into the
# runner nodes' HF snapshots — which sparkrun's model-preparation validator
# now rejects (its manifest records the hub's current file sizes, and the
# hub metadata changed under the pinned revision). So the injection moved
# here: sparkrun validates the untouched cache, then this mod stages the
# honed file into MOD_CACHEDIR and the recipe points --chat-template at it
# (sglang accepts a template-file path; VERIFIED against the pinned image's
# server_args.py: "the path of the chat template file").
#
# This mod never writes into the HF cache.
#####################################################################

#####################################################################
# Metadata
#####################################################################
export MOD_NAME="ornith-honed-chat-template"
export MOD_DESCRIPTION="Stage the honed Ornith chat template for --chat-template"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export TIMEOUT="${MOD_TIMEOUT:-60}"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export USER_UID="$(stat -c '%u' "${CACHEDIR}" 2>/dev/null || stat -c '%u' /cache/runtime)"
export USER_GID="$(stat -c '%g' "${CACHEDIR}" 2>/dev/null || stat -c '%g' /cache/runtime)"

OUT_DIR="${CACHEDIR}/ornith-honed-chat-template"
OUT_FILE="${OUT_DIR}/chat_template.jinja"
SRC_FILE="${MOD_DIR}/chat_template.jinja"

#####################################################################
# Helpers (harness: log to file + syslog; reown to the cache owner)
#####################################################################
reown() { chown -R "${USER_UID}:${USER_GID}" "${@}"; }

o() {
  local _ts
  _ts="$(date -Ins)"
  printf '%s [%s] %s\n' "$_ts" "${MOD_NAME}" "${*}" | tee -a "${LOGDIR}/${MOD_NAME}.log"
}
log() { o "${*}"; }

if ! [[ -d "${LOGDIR}" ]]; then
  mkdir -p "${LOGDIR}"
fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log.gz" ]]; then
  rm -f "${LOGDIR}/${MOD_NAME}.log.gz"
fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log" ]]; then
  mv "${LOGDIR}/${MOD_NAME}.log" "${LOGDIR}/${MOD_NAME}.log.1"
fi
reown "${LOGDIR}"

log "${MOD_NAME} - ${MOD_DESCRIPTION}"

#####################################################################
# Main
#####################################################################
[ -f "${SRC_FILE}" ] || { o "ERROR: ${SRC_FILE} missing"; exit 1; }

# Content idempotence, not timestamps: if the staged copy already matches,
# stop here.
if [ -f "${OUT_FILE}" ] && cmp -s "${SRC_FILE}" "${OUT_FILE}"; then
  o "already staged and identical: ${OUT_FILE}"
  exit 0
fi

mkdir -p "${OUT_DIR}"
# Never write through a symlink: unlink any existing entry first.
[ ! -L "${OUT_FILE}" ] || rm -f "${OUT_FILE}"
tmp="$(mktemp "${OUT_DIR}/.chat_template.XXXXXX")"
cp "${SRC_FILE}" "${tmp}"
chmod 644 "${tmp}"

# Fail closed BEFORE the move, so a bad run leaves no staged artifact.
EXPECTED_SIZE=30438
SIZE="$(stat -c '%s' "${tmp}")"
if [ "${SIZE}" != "${EXPECTED_SIZE}" ]; then
  rm -f "${tmp}"
  o "ERROR: staged size ${SIZE} != ${EXPECTED_SIZE}"
  exit 1
fi
if ! grep -q 'qwen3.8-honed-v22.5.1' "${tmp}"; then
  rm -f "${tmp}"
  o "ERROR: staged template missing the honed-version marker"
  exit 1
fi

mv "${tmp}" "${OUT_FILE}"
reown "${OUT_DIR}"

o "staged: ${OUT_FILE} (${SIZE} B)"
log "Done."
