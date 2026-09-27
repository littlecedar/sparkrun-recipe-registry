#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Drop the HOST kernel page cache from a privileged sparkrun mod.
#
# Why this exists
# ---------------
# `@eugr/mods/drop-caches` is listed in many recipes in this registry (qwen4,
# ds4, qwen3, ornith) but does nothing, for two independent reasons, both
# reproduced here on 2026-09-27:
#
#   1. It runs under sparkrun's rootless default, where `/proc/sys` is mounted
#      `ro` and the write is refused ("Read-only file system"). sparkrun's
#      `DockerExecutor.apply_runtime_adjustments` sets `privileged: false`
#      (docker.py:311-313) unless the launch is rootful.
#   2. Even privileged, its command has a redirection-order bug:
#          echo 3 > /proc/sys/vm/drop_caches >> /tmp/drop_caches.log 2>&1
#      Bash applies redirects left-to-right and the LAST stdout redirect wins,
#      so `3` is written to the *log* and the cache is never dropped
#      (reproduced: target 0 bytes, log "3").
#
# This mod fixes both: it writes to the target exactly once, and it FAILS CLOSED
# when the write is refused, so it can never pass as a silent no-op.
#
# The mechanism (VERIFIED 2026-09-27, Docker 29.8.1, Linux 7.2.8)
# --------------------------------------------------------------
#   unprivileged : /proc/sys mounted ro -> write "Read-only file system"
#   --privileged : write rc 0 -> host `Cached:` fell 17.93 GB -> 3.16 GB
# `/proc/sys` is NOT namespaced, so a write from inside the container drops the
# page cache of the HOST kernel. That is why the mod must be privileged, and
# why the drop is a whole-node effect, not a per-container one.
#
# Requirement: the recipe must launch rootful (privileged: true), which only
# happens for a TRUSTED recipe (`-o privileged=true`, or the `--rootful` flag /
# a cluster whose executor_config grants it). See AGENTS.md and
# `core/launcher.py:_TRUST_GATED_EXECUTOR_KEYS` -- `privileged` is trust-gated.
#
# Modes (MOD_DROP_CACHES_MODE)
# ----------------------------
#   once  (default) : sync, drop once, print the Cached before/after, exit.
#   loop            : also start a detached flusher that drops every
#                     MOD_DROP_CACHES_INTERVAL seconds (eugr parity; the loop
#                     keeps running for the life of the container, so prefer
#                     `once` unless a long load genuinely needs repeated drops).
#
# Knobs
# -----
#   MOD_DROP_CACHES_MODE      once | loop          (default: once)
#   MOD_DROP_CACHES_INTERVAL  seconds for loop mode (default: 60)
#   MOD_DROP_CACHES_TARGET    path (default /proc/sys/vm/drop_caches; test hook)
#   MOD_DROP_CACHES_LEVEL     1|2|3 (default 3)
#####################################################################

#####################################################################
# Metadata
#####################################################################
export MOD_NAME="drop-caches"
export MOD_DESCRIPTION="Drop the host page cache from a privileged container (fails closed if unprivileged)"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export TIMEOUT="${MOD_TIMEOUT:-180}"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# RUNTIME_ROOT mirrors mod-template's MOD_CACHEDIR, but honours XDG_CACHE_HOME
# (which sparkrun exports at the same mount) so it cannot drift from the recipes.
export RUNTIME_ROOT="${MOD_CACHEDIR:-${XDG_CACHE_HOME:-/cache/runtime}}"
export CACHEDIR="${RUNTIME_ROOT}"
export LOGDIR="${MOD_LOGDIR:-${RUNTIME_ROOT}/modlogs}"
export UV_LINK_MODE=copy

export DROP_TARGET="${MOD_DROP_CACHES_TARGET:-/proc/sys/vm/drop_caches}"
export DROP_LEVEL="${MOD_DROP_CACHES_LEVEL:-3}"
export DROP_MODE="${MOD_DROP_CACHES_MODE:-once}"
export DROP_INTERVAL="${MOD_DROP_CACHES_INTERVAL:-60}"

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
    [[ -x "$(type -fp logger 2>/dev/null)" ]] && logger -t "${MOD_NAME}" -- "${_message}"
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

warn() { log "WARNING: ${*}"; }
die()  { log "ERROR: ${*}"; exit 1; }

# Host page-cache size in kB, read from the (un-namespaced) /proc/meminfo.
cached_kb() {
  awk '/^Cached:/{print $2}' /proc/meminfo 2>/dev/null || true
}

#####################################################################
# Start up: resolve owner, prepare log dir, rotate logs
#####################################################################
if [[ ! -d "${RUNTIME_ROOT}" ]]; then
  echo "${MOD_NAME}: FATAL: runtime cache root ${RUNTIME_ROOT} is absent" >&2
  exit 1
fi
# Mods run as root and we can't tell the real uid:gid from environment,
# so we have to infer from the runtime-cache mount ownership.
export USER_UID="$(stat -c '%u' "${RUNTIME_ROOT}")"
export USER_NAME="$(stat -c '%U' "${RUNTIME_ROOT}")"
export USER_GID="$(stat -c '%g' "${RUNTIME_ROOT}")"
export USER_GROUP="$(stat -c '%G' "${RUNTIME_ROOT}")"

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
log_var DROP_TARGET
log_var DROP_LEVEL
log_var DROP_MODE
log_var DROP_INTERVAL
log "gathering environment info..."
log_cmd whoami
log_var USER_NAME
log_var USER_GROUP

#####################################################################
# Preflight: the target must exist
#####################################################################
[[ -e "${DROP_TARGET}" ]] || die "cache-drop target ${DROP_TARGET} does not exist; the kernel has no drop_caches here."
if [[ ! -w "${DROP_TARGET}" ]]; then
  # NB: `test -w` is unreliable as root (access(2) ignores the mode bits for
  # uid 0), so this is only an early hint. The authoritative gate is the real
  # write below, whose exit status we check.
  warn "test -w says ${DROP_TARGET} is not writable; proceeding to a real write to confirm."
fi

#####################################################################
# Do the drop, and PROVE it happened
#
# The write is the point of this mod. If it fails (rootless: /proc/sys ro), we
# die rather than log success -- the exact failure mode of @eugr/mods/drop-caches
# is that its process stays alive while the cache is untouched.
#####################################################################
ERRFILE="${LOGDIR}/${MOD_NAME}.err"
: > "${ERRFILE}"

before_kb="$(cached_kb)"
log "Cached (before): ${before_kb:-?} kB"

log "syncing filesystems..."
sync

rc=0
# Exactly ONE stdout redirection, so `echo`'s "3" goes to the target and nothing
# else can steal it (the eugr bug). stderr goes to a separate fd.
echo "${DROP_LEVEL}" > "${DROP_TARGET}" 2>> "${ERRFILE}" || rc=$?

after_kb="$(cached_kb)"
log "drop write rc=${rc}"
log "Cached (after):  ${after_kb:-?} kB"
if [[ -s "${ERRFILE}" ]]; then
  log "write stderr:"
  sed 's/^/  | /' "${ERRFILE}" | log
fi

if [[ "${rc}" -ne 0 ]]; then
  die "could not write ${DROP_TARGET} (rc=${rc}). This launch is NOT privileged: /proc/sys is mounted read-only under sparkrun's rootless default. Relaunch rootful with a TRUSTED recipe, e.g. \`sparkrun run <recipe> --rootful\` (or -o privileged=true). Refusing to continue silently -- a cache drop that did not happen must not look like success."
fi

log "host page cache drop OK: Cached ${before_kb:-?} kB -> ${after_kb:-?} kB"

#####################################################################
# Optional: keep dropping on an interval (eugr parity)
#####################################################################
if [[ "${DROP_MODE}" == "loop" ]]; then
  [[ "${DROP_INTERVAL}" =~ ^[0-9]+$ ]] || die "MOD_DROP_CACHES_INTERVAL must be an integer number of seconds, got '${DROP_INTERVAL}'."
  if (( DROP_INTERVAL < 5 )); then
    warn "MOD_DROP_CACHES_INTERVAL=${DROP_INTERVAL}s is very aggressive; a whole-node cache drop every ${DROP_INTERVAL}s will thrash other tenants."
  fi

  LOOP_SCRIPT="${RUNTIME_ROOT}/${MOD_NAME}-loop.sh"
  LOOP_LOG="${LOGDIR}/${MOD_NAME}-loop.log"
  LOOP_PID="${LOGDIR}/${MOD_NAME}-loop.pid"

  # Keep the loop self-contained: a backgrounded `bash -c` inherits no functions,
  # and nested quoting is fragile, so write a tiny standalone script instead.
  cat > "${LOOP_SCRIPT}" <<EOF
#!/bin/bash
set -uo pipefail
while true; do
  sync
  if echo ${DROP_LEVEL} > "${DROP_TARGET}" 2>>"${LOOP_LOG}"; then
    printf '%s drop-caches ok (Cached %s kB)\n' "\$(date -Ins)" "\$(awk '/^Cached:/{print \$2}' /proc/meminfo)" >> "${LOOP_LOG}"
  else
    printf '%s drop-caches FAILED rc=\$?\n' "\$(date -Ins)" >> "${LOOP_LOG}"
  fi
  sleep ${DROP_INTERVAL}
done
EOF
  chmod +x "${LOOP_SCRIPT}"
  reown "${LOOP_SCRIPT}"

  nohup bash "${LOOP_SCRIPT}" >> "${LOOP_LOG}" 2>&1 &
  loop_pid=$!
  echo "${loop_pid}" > "${LOOP_PID}"
  disown "${loop_pid}" 2>/dev/null || true
  reown "${LOOP_LOG}" "${LOOP_PID}"
  log "started drop-caches loop pid=${loop_pid} interval=${DROP_INTERVAL}s log=${LOOP_LOG}"
fi

#####################################################################
# Log Completion
#####################################################################
log "Done."
