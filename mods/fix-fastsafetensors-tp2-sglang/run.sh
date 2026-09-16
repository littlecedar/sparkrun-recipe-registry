#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Make --load-format fastsafetensors work under multi-node tensor
# parallel on DGX Spark.
#
# SGLang derives the CUDA device for the fastsafetensors pool from the
# global process-group rank instead of the local device index. DGX Spark
# is 1 GPU per node, so at TP=2 the rank-1 host is asked for cuda:1 and
# dies with "invalid device ordinal". It works at TP=1 only because rank
# 0 happens to be a valid device index.
#
# Upstream: https://github.com/sgl-project/sglang/issues/29272
# (open, unmerged as of 2026-09-15; PRs #26597 and #29717 are duplicate
# one-line fixes that have stalled).
#
# This mod patches the installed sglang in place. SGLang ships as source
# in the pinned image, so no bytecode cache invalidation is needed.
#
# Companion mod: pip-install-fastsafetensors (the module is not installed
# in the pinned container; both are required to use the loader).
#
# Use with:
#   load_format: fastsafetensors
#   mods:
#     - fix-fastsafetensors-tp2-sglang
#     - pip-install-fastsafetensors
#
# Order matters: mods resolve into sequential pre_exec entries, so the
# patch listed after the pip install runs against the final tree.
#####################################################################

#####################################################################
# Metadata
#####################################################################
export MOD_NAME="fix-fastsafetensors-tp2-sglang"
export MOD_DESCRIPTION="Patch SGLang fastsafetensors device selection for TP>1 on DGX Spark"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export TIMEOUT="${MOD_TIMEOUT:-180}"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
# Mods run as root and we can't tell the real uid:gid from environment,
# so we have to infer from /cache/runtime ownership.
export USER_UID="$(stat -c '%u' /cache/runtime)"
export USER_NAME="$(stat -c '%U' /cache/runtime)"
export USER_GID="$(stat -c '%g' /cache/runtime)"
export USER_GROUP="$(stat -c '%G' /cache/runtime)"

#####################################################################
# Helpers
#####################################################################

#--------------------------------------------------------------------
# Chown a path to the user who owns the .cache bind mount.
#
# Since mods run as root, changes to paths and files that require
# user access may fail if owned by root. Use this to fix that.
#--------------------------------------------------------------------
reown() {
  chown -R "${USER_UID}:${USER_GID}" "${@}"
}

#--------------------------------------------------------------------
# General logging helper
#
# Formats and sends to log anything on STDIN or given as args.
#--------------------------------------------------------------------
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

#--------------------------------------------------------------------
# Quickly log a variable name and its value.
#--------------------------------------------------------------------
log_var() {
  local _key _val
  _key="${1}"
  _val="${!_key}"
  log "${_key}=${_val}"
}

#--------------------------------------------------------------------
# Simple command logging harness
#
# Provide a simple command and its arguments as args to this.
# Complex pipelines don't work well; pipe pipelines to log().
#--------------------------------------------------------------------
log_cmd() {
  log "            "
  log "            "
  log "=== ${1} ==="
  "${@}" 2>&1 | log
}

#--------------------------------------------------------------------
# Run an inline python snippet with logging, without leaving a file.
#--------------------------------------------------------------------
log_py() {
  log "            "
  log "            "
  log "=== ${1} ==="
  python3 -c "${2}" 2>&1 | log
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
  gzip  "${LOGDIR}/${MOD_NAME}.log"
  touch "${LOGDIR}/${MOD_NAME}.log"
fi
reown "${LOGDIR}"

#####################################################################
# Main mod scripting zone
#
# Add your mod commands below here.
# You can add additional helpers in the helpers section if you like.
# There are no real rules, just organization and pattern.
#
log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log "${MOD_MAINTAINER}"
#
#####################################################################

log "Gathering environment info..."
log_cmd whoami
# NB: do not use log_var for UID/GID here. Bash 5.2 indirect expansion
# (${!k}) throws "unbound variable" for GID under `set -u`, which would
# abort the whole mod. `id` reports the same thing without the trap.
log_cmd id

log "Checking the fastsafetensors loader is actually installed..."
# Non-fatal: this mod only patches sglang. A missing module means the
# recipe also needs the pip-install-fastsafetensors mod, and we say so
# rather than failing here or silently installing anything.
if python3 -c "import fastsafetensors" >/dev/null 2>&1; then
  log_py "fastsafetensors version" "import fastsafetensors, os; print('installed at', os.path.dirname(fastsafetensors.__file__))"
else
  log "WARNING: python module 'fastsafetensors' is NOT installed in this container."
  log "WARNING: add the 'pip-install-fastsafetensors' mod to this recipe, or"
  log "WARNING: --load-format fastsafetensors will fail at weight load."
fi

log "Checking sglang is importable..."
log_py "sglang version" "import sglang; print('sglang', sglang.__version__)"

log "Applying patches..."
log_cmd python3 "${MOD_DIR}/apply-fastsafetensors-tp2-patch.py"

log "Verifying the patched device selection..."
# Audit evidence for tuning runs: log the line that will actually execute.
log_py "post-patch check" "
import importlib.util, re
spec = importlib.util.find_spec('sglang.srt.model_loader.weight_utils')
src = open(spec.origin, encoding='utf-8').read()
if 'sparkrun: global rank is not a local CUDA device index' not in src:
    raise SystemExit('patch marker missing after apply')
for line in src.splitlines():
    if 'torch.device' in line and 'cuda:' in line and 'rank' not in line:
        print('OK:', line.strip())
"

#####################################################################
# Log Completion
#####################################################################
log "Done."
