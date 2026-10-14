#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Pre-launch mod for the TensorFold DeepSeek-V4.1-Flash TP=2 lane: fetch the
# Engram tables from the *online* official HF repo, on the pointer of need, so
# the lane does not depend on someone having rsync'd 189 GiB of checkpoint
# shards into the node's HF cache by hand.
#
# Why this is a mod and not a host step: Engram is node-local (~47-95 GiB per
# node) and the launcher reads it from `/cache/huggingface/hub/dsv41-engram`.
# A mod runs on every runner node, in the container, before the serve command,
# so provisioning travels with the recipe.
#
# It does NOT block the boot: the engine serves degraded without the tables and
# picks them up on the next boot, so a first boot need not wait ~4-8 minutes on
# the CDN. A complete directory makes this a no-op. Set MOD_ENGRAM_WAIT=1 to
# block until the tables are on disk instead (pre-warm / CI).
#
# Knobs (all `${VAR:-default}`): MOD_ENGRAM_DIR, MOD_ENGRAM_WAIT, MOD_ENGRAM_WORKERS,
# MOD_ENGRAM_SEGMENT_MB, MOD_ENGRAM_REPO, MOD_ENGRAM_REVISION, MOD_TIMEOUT,
# MOD_CACHEDIR, MOD_LOGDIR.
set -euo pipefail

export MOD_NAME="dsv41-engram-fetch"
export MOD_DESCRIPTION="Fetch DeepSeek-V4.1-Flash Engram tables from the online HF repo"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

export TIMEOUT="${MOD_TIMEOUT:-180}"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export UV_LINK_MODE=copy
export USER_UID="$(stat -c '%u' /cache/runtime)"
export USER_GID="$(stat -c '%g' /cache/runtime)"

# Where the launcher reads the tables (mods/tensorfold-dsv41-launcher/launcher.py
# ENGRAM_DIR default); the mod and the launcher must agree, so one is derived
# from the other by this shared default.
ENGRAM_DIR="${MOD_ENGRAM_DIR:-${TENSORFOLD_ENGRAM_DIR:-/cache/huggingface/hub/dsv41-engram}}"
WAIT="${MOD_ENGRAM_WAIT:-0}"
WORKERS="${MOD_ENGRAM_WORKERS:-16}"
SEGMENT_MB="${MOD_ENGRAM_SEGMENT_MB:-256}"
LAYERS="${MOD_ENGRAM_LAYERS:-1,14}"
LIMIT_ROWS="${MOD_ENGRAM_LIMIT_ROWS:-}"
# Extra builder flags as one word-split string. Kept as a string (not an array)
# because it is expanded inside an (unquoted) heredoc for the detached wrapper,
# where an array expansion would collapse "a b" into a single word.
EXTRA_ARGS=""
[[ -n "${LIMIT_ROWS}" ]] && EXTRA_ARGS="${EXTRA_ARGS} --limit-rows ${LIMIT_ROWS}"
[[ -n "${MOD_ENGRAM_HF_TOKEN:-}" ]] && EXTRA_ARGS="${EXTRA_ARGS} --token ${MOD_ENGRAM_HF_TOKEN}"
REPO="${MOD_ENGRAM_REPO:-deepseek-ai/DeepSeek-V4.1-Flash}"
REVISION="${MOD_ENGRAM_REVISION:-main}"
BUILDER="${MOD_DIR}/build-dsv41-engram.py"
FETCH_LOG="${LOGDIR}/${MOD_NAME}.fetch.log"

reown() { chown -R "${USER_UID}:${USER_GID}" "${@}"; }

log() {
  local _message _ts
  _message="${*}"
  _ts="$(date -Ins)"
  printf '%s [%s] %s\n' "$_ts" "${MOD_NAME}" "${_message}" | tee -a "${LOGDIR}/${MOD_NAME}.log"
  [[ -x "$(type -fp logger)" ]] && logger -t "${MOD_NAME}" -- "${_message}" || true
}
log_var() { log "$1=${!1:-}"; }

if [[ ! -d "${LOGDIR}" ]]; then mkdir -p "${LOGDIR}"; fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log.gz" ]]; then rm -f "${LOGDIR}/${MOD_NAME}.log.gz"; fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log" ]]; then gzip "${LOGDIR}/${MOD_NAME}.log" || true; fi
touch "${LOGDIR}/${MOD_NAME}.log"
reown "${LOGDIR}"

log "${MOD_NAME} - ${MOD_DESCRIPTION}"

# --- gates -------------------------------------------------------------------
fail=0
check() { if [[ -e "$1" ]]; then log "gate OK: $1"; else log "gate MISSING: $1"; fail=1; fi; }
check "${BUILDER}"
check /cache/huggingface/hub
command -v python3 >/dev/null 2>&1 || { log "gate MISSING: python3"; fail=1; }
[[ "${fail}" -eq 0 ]] || { log "[${MOD_NAME}] gate FAILED"; exit 1; }

log_var ENGRAM_DIR
log_var WAIT
log_var WORKERS
log_var SEGMENT_MB
log_var LAYERS
log_var REPO

mkdir -p "${ENGRAM_DIR}"
reown "${ENGRAM_DIR}"

# --- already present? no-op ----------------------------------------------
if python3 "${BUILDER}" --check --out "${ENGRAM_DIR}" --layers "${LAYERS}" >>"${LOGDIR}/${MOD_NAME}.log" 2>&1; then
  log "Engram tables already complete at ${ENGRAM_DIR}; nothing to do"
  ls -l "${ENGRAM_DIR}"/*.safetensors 2>/dev/null | while read -r l; do log "  ${l}"; done
  log "Done."
  exit 0
fi
log "Engram tables incomplete or absent at ${ENGRAM_DIR}"

# --- fetch -------------------------------------------------------------------
# A ranged, resumable fetch of ~189 GiB, and on a slow Internet link it can run
# for many hours. It is therefore ALWAYS detached and NEVER blocks the launch:
# sparkrun runs this mod as a pre-exec hook under a hard 600 s SSH timeout
# (orchestration/hooks.py), so any synchronous wait is a launch-killing risk --
# observed on 2026-10-06 (`pre_exec[2] failed ... TIMEOUT after 600s`).
#
# There is deliberately no blocking mode here. For a fresh deployment, pre-warm
# each node OUTSIDE the recipe (see the mod README): the engine serves degraded
# until the tables land and uses them on the next boot, so nothing is lost.
WAIT="${MOD_ENGRAM_WAIT:-0}"
if [[ "${WAIT}" == "1" ]]; then
  log "MOD_ENGRAM_WAIT is ignored: the fetch never blocks (600 s hook timeout). Pre-warm out-of-band instead."
fi

# Wrapper re-owns the output (the fetch runs as root; the launcher reads as the
# ssh user) and records the exit code. The log records progress; a complete dir
# makes every later launch a no-op.
FETCH_SH="${LOGDIR}/${MOD_NAME}.fetch.sh"
cat >"${FETCH_SH}" <<-RUN
#!/bin/bash
python3 -u "${BUILDER}" --repo "${REPO}" --revision "${REVISION}" \\
  --layers "${LAYERS}"${EXTRA_ARGS} \\
  --out "${ENGRAM_DIR}" --workers "${WORKERS}" --segment-mb "${SEGMENT_MB}"
rc=\$?
chown -R "${USER_UID}:${USER_GID}" "${ENGRAM_DIR}" 2>/dev/null || true
printf '%s [%s] detached fetch exit %s\n' "\$(date -Ins)" "${MOD_NAME}" "\${rc}" \\
  >> "${LOGDIR}/${MOD_NAME}.log"
RUN
chmod +x "${FETCH_SH}"
log "launching detached fetch (log: ${FETCH_LOG})"
setsid nohup "${FETCH_SH}" >"${FETCH_LOG}" 2>&1 < /dev/null &
log "fetch pid ${!} detached (survives this mod; resumes after a container stop)"

log "Done."