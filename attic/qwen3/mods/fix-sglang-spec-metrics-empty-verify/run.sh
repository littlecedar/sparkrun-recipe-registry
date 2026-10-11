#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Making speculation explicitly NONE crashes SGLang on the first generated batch.
#
#   IndexError: list index out of range
#     .../srt/managers/tokenizer_manager.py, in _calculate_spec_decoding_metrics
#         and recv_obj.spec_verify_ct[i] > 0
#
# Chain, traced through the pinned image's own source:
#
#   1. output_streamer.py declares    spec_verify_ct: list = field(default_factory=list)
#      and appends per request only inside  if not self.spec_algorithm.is_none():
#      So with the algorithm NONE the attribute EXISTS on the wire object and holds [].
#
#   2. tokenizer_manager.py gates the metric on   if get_spec().speculative_algorithm:
#      That reads the unnormalised server-args string: None when the flag is omitted
#      (falsy - which is why ordinary no-spec servers work fine), but the literal string
#      "NONE" when it is passed explicitly, which is TRUTHY. Naming NONE explicitly is
#      precisely what routes a no-spec server into spec-decode metrics.
#
#   3. The metric then guards with  hasattr(recv_obj, "spec_verify_ct")
#      hasattr tests attribute *existence*, true for a dataclass field that merely
#      exists, so it does not describe "there is a value at index i". [0] on [] raises.
#
#   4. The sibling conjunct two lines below IS length-guarded, and the third site that
#      reads the same field elsewhere in the file is guarded correctly too. This one
#      call site just lost the conjunct. That asymmetry is the whole bug, and the fix
#      is the guard upstream already uses twice in the same file.
#
# Why this matters to this project and not just as a bug report: the no-spec control
# run is the measurement that separates speculative amplification from raw decode
# bandwidth on a dense model. On this build the flag needed to express "no speculation"
# is the flag that triggers the crash, so the control is unobtainable by configuration
# alone - and the server dies outright rather than merely losing a metric.
#
# All edits are anchored and idempotent: an anchor that does not match exactly once
# makes the mod refuse to write and exit non-zero, rather than leave a half-patched
# tree. Both sglang trees in this image (editable /sgl-workspace and site-packages) are
# patched, because patching only one is how a mod ends up silently doing nothing.
#
# This mod is NOT mounted in the shipping recipe, deliberately: the shipping config
# uses DFLASH, where the guard is a no-op, so mounting it would slow every boot for no
# benefit. Mount it on a control/experiment recipe that passes
# `speculative_algorithm: NONE`.
#
# Do not import sglang from a pre_exec hook. It runs as root against the bind-mounted
# per-model runtime cache, so a flashinfer JIT build there drops root-owned files the
# uid-1000 server can neither write nor unlink, and that model key fails to boot from
# then on. Hence the pure filesystem search in apply-spec-metrics-guard.py.
#
# Verify the anchors against a new base image (no sglang import needed):
#   python3 apply-spec-metrics-guard.py --check-only
# Then prove the harness is real rather than self-confirming:
#   python3 test_spec_metrics_guard.py <tokenizer_manager.py>   # 1 = unpatched, 0 = safe
#####################################################################

#####################################################################
# Metadata
#####################################################################
export MOD_NAME="fix-sglang-spec-metrics-empty-verify"
export MOD_DESCRIPTION="Guard spec_verify_ct indexing so --speculative-algorithm NONE cannot crash the server"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
# Mods run as root; the real uid:gid is not in the environment, so infer it from the
# ownership of the cache bind mount, exactly as the other sglang-patching mods do.
export USER_UID="$(stat -c '%u' /cache/runtime)"
export USER_NAME="$(stat -c '%U' /cache/runtime)"
export USER_GID="$(stat -c '%g' /cache/runtime)"
export USER_GROUP="$(stat -c '%G' /cache/runtime)"

#--------------------------------------------------------------------
# Chown a path to the user who owns the cache bind mount.
#--------------------------------------------------------------------
reown() {
  chown -R "${USER_UID}:${USER_GID}" "${@}"
}

#--------------------------------------------------------------------
# Timestamped logging to both stdout and the per-mod log.
#
# Contract inherited from the other sglang mods in this repo: called with no
# arguments it consumes STDIN line by line, so `cmd 2>&1 | log` works. A log()
# that only handles "${*}" silently throws away every pipeline diagnostic and
# leaves a blank line where the evidence was - which is exactly how this mod's
# first container run ended up reporting "nothing found" with no reason.
#--------------------------------------------------------------------
o() {
  local _ts _message
  _message="${*}"
  _ts="$(date -Ins)"
  printf '%s [%s] %s\n' "$_ts" "${MOD_NAME}" "${_message}" | tee -a "${LOGDIR}/${MOD_NAME}.log"
  [[ -x "$(type -fp logger)" ]] && logger -t "${MOD_NAME}" -- "${_message}" || true
}

log() {
  if [[ -z "${*}" ]]; then
    local _line
    # -t 60 only guards against a wedged producer; it is long enough that a slow
    # python start cannot truncate the output. The "|| [[ -n ]] " tail keeps a final
    # line that arrives without a trailing newline, which python's print never does but
    # a killed process's last write can.
    while read -rt 60 _line || [[ -n "${_line}" ]]; do
      o "${_line}"
      _line=""
    done
  else
    o "${*}"
  fi
}

mkdir -p "${LOGDIR}"

log "mod starting (uid=$(id -u))"

#--------------------------------------------------------------------
# Opt-out, so the stock behaviour stays A/B-able without rebuilding.
# Default ON: the guard is inert whenever a spec engine is active.
#--------------------------------------------------------------------
if [[ "${SGLANG_FIX_SPEC_METRICS_VERIFY_GUARD:-1}" != "1" ]]; then
  log "SGLANG_FIX_SPEC_METRICS_VERIFY_GUARD!=1 - leaving sglang untouched"
  log "mod complete (skipped)"
  exit 0
fi

#--------------------------------------------------------------------
# 1. Report what is there before changing anything. A check over an empty
#    target list always "passes", so the denominator is printed and asserted.
#--------------------------------------------------------------------
log "locating and checking targets..."
python3 "${MOD_DIR}/apply-spec-metrics-guard.py" --check-only 2>&1 | log || {
  log "ERROR: no tokenizer_manager.py found, or no anchor present."
  log "       The sglang layout changed. Refusing to patch blind."
  exit 1
}

#--------------------------------------------------------------------
# 2. Patch. Failures are loud and specific, never a silent no-op.
#--------------------------------------------------------------------
log "applying guard..."
if ! python3 "${MOD_DIR}/apply-spec-metrics-guard.py" 2>&1 | log; then
  log "ERROR: patching failed; see the per-file status lines above."
  exit 1
fi

#--------------------------------------------------------------------
# 3. Prove it. The harness reads the real patched file, extracts the real
#    function, and executes it against an empty spec_verify_ct - the exact
#    input that used to kill the server. It also runs a positive control, so
#    "no crash" cannot mean "the harness does nothing".
#
#    The target list comes from the patcher's own --list-only rather than a
#    second copy of the search logic: two copies drift, and a verification loop
#    over a list that silently differs from the list that was patched verifies
#    nothing. A failing pipeline in an `if` condition does not trip `set -e`, so
#    the else-branch is what catches a bad patch - do not "simplify" it to `if !`.
#--------------------------------------------------------------------
TARGETS=()
while IFS= read -r line; do
  [[ -n "${line}" ]] && TARGETS+=("${line}")
done < <(python3 "${MOD_DIR}/apply-spec-metrics-guard.py" --list-only)

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  log "ERROR: empty target list after patching - cannot verify anything."
  exit 1
fi

log "verifying ${#TARGETS[@]} target(s) by executing the patched function..."
n_ok=0
for t in "${TARGETS[@]}"; do
  if python3 "${MOD_DIR}/test_spec_metrics_guard.py" "${t}" 2>&1 | log; then
    n_ok=$((n_ok + 1))
  else
    log "ERROR: verification did not pass for ${t}"
    exit 1
  fi
done
log "verified ${n_ok}/${#TARGETS[@]} target(s) guard empty spec_verify_ct"

#--------------------------------------------------------------------
# 4. Mods run as root; hand the tree back to the serving user.
#--------------------------------------------------------------------
log "re-owning patched trees to ${USER_UID}:${USER_GID} (${USER_NAME}/${USER_GROUP})"
for t in "${TARGETS[@]}"; do
  reown "$(dirname "${t}")"
done

log "mod complete"
