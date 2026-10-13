#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Install Aleph Alpha's pure-Python vLLM plugin (aleph-alpha-inference)
# into the stock vllm/vllm-openai image so `vllm serve Aleph-Alpha/Kolibri-1`
# works on arm64 GB10 nodes (the vendor's own image is amd64-only).
# The plugin registers the `kolibri1` reasoning + tool-call parsers through
# vllm.general_plugins. Installed with --no-deps per the plugin README so the
# image's vLLM/torch/transformers are never touched.
# Idempotent via a content marker under MOD_CACHEDIR gated on a live import of
# the pinned module (the marker alone outlives the ephemeral install layer).
# Fails closed: a failed install or a failed import/entry-point check aborts
# the mod (and the launch).
#####################################################################

export MOD_NAME="install-kolibri-plugin"
export MOD_DESCRIPTION="Install the aleph-alpha-inference vLLM plugin (Kolibri parsers)"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"
export TIMEOUT="${MOD_TIMEOUT:-300}"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export UV_LINK_MODE=copy
# The mod runs as root; reown() hands cache writes back to the .cache mount's
# owner. Infer that owner from MOD_CACHEDIR (falling back to the container's
# /cache/runtime), so the mod also runs against a temp CACHEDIR in tests.
export USER_UID="$(stat -c '%u' "${CACHEDIR}" 2>/dev/null || stat -c '%u' /cache/runtime 2>/dev/null || echo 0)"
export USER_NAME="$(stat -c '%U' "${CACHEDIR}" 2>/dev/null || stat -c '%U' /cache/runtime 2>/dev/null || echo root)"
export USER_GID="$(stat -c '%g' "${CACHEDIR}" 2>/dev/null || stat -c '%g' /cache/runtime 2>/dev/null || echo 0)"
export USER_GROUP="$(stat -c '%G' "${CACHEDIR}" 2>/dev/null || stat -c '%G' /cache/runtime 2>/dev/null || echo root)"

# The plugin release this mod pins (matches the recipe's tested pairing with
# vllm/vllm-openai:v0.29.0). Bump together with the recipe's container pin.
export PLUGIN_VERSION="1.0.0"

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

if ! [[ -d "${LOGDIR}" ]]; then
  mkdir -p "${LOGDIR}"
fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log.gz" ]]; then
  rm -f "${LOGDIR}/${MOD_NAME}.log.gz"
fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log" ]]; then
  gzip  "${LOGDIR}/${MOD_NAME}.log"
  touch "${LOGDIR}/${MOD_NAME}.log"
fi
reown "${LOGDIR}"

log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log "${MOD_MAINTAINER}"

log_var PLUGIN_VERSION
log_var CACHEDIR

MARKER="${CACHEDIR}/mod-${MOD_NAME}.installed"

# Idempotence is gated on the LIVE container layer, not on the marker alone.
# MOD_CACHEDIR (/cache/runtime) is a persistent cache mount, but pip installs
# into the container's EPHEMERAL layer, which is empty on every relaunch: a
# marker that outlives its module is a stale marker (measured 2026-10-13 on
# .35 — the second boot skipped the install on a surviving marker and died
# `ModuleNotFoundError: No module named 'aleph_alpha_inference'` in
# launch_inference). So skip only when the marker records this version AND the
# module imports at that version right now.
plugin_installed_at_version() {
  python3 -c "import importlib.metadata as md; import aleph_alpha_inference; v=md.version('aleph-alpha-inference'); assert v == '${PLUGIN_VERSION}', 'have ' + v" >/dev/null 2>&1
}

if [[ -f "${MARKER}" ]] && grep -qx "${PLUGIN_VERSION}" "${MARKER}" && plugin_installed_at_version; then
  log "marker ${MARKER} records ${PLUGIN_VERSION} and the plugin imports — skipping pip install"
else
  log "Installing aleph-alpha-inference==${PLUGIN_VERSION} (--no-deps: image vLLM/torch/transformers untouched)"
  log_cmd pip install --force --break-system-packages --no-deps "aleph-alpha-inference==${PLUGIN_VERSION}"
fi

# Fail closed: the plugin must import AND be discoverable through vLLM's
# general_plugins entry-point group, or the serve would boot without the
# kolibri1 parsers.
log "Verifying plugin import + vllm.general_plugins entry point"
if ! log_cmd python3 -c "import importlib.metadata as md; import aleph_alpha_inference; eps=[e.name for e in md.entry_points(group='vllm.general_plugins')]; assert 'aleph_alpha_inference' in eps, eps; print('plugin OK:', eps)"; then
  die "aleph-alpha-inference ${PLUGIN_VERSION} failed import/entry-point verification"
fi

printf '%s\n' "${PLUGIN_VERSION}" > "${MARKER}"
reown "${MARKER}"
reown "${CACHEDIR}"

log "mod complete"
