#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Pre-launch mod that makes a non-8-step Qwen-Image-2.1-Turbo schedule
# expressible over the wire.
#
# The launcher mod (`mods/qwen-image-2.1-turbo-launcher`) forwards a request's
# `num_inference_steps` into `pipe(**call)`, and diffusers ignores it: the
# checkpoint's saved `sample_sigmas` in model_index.json are the pipeline's
# config default, so a live request with `num_inference_steps: 12` returned
# `steps: 8` at the same 11.231 s (media-gen-20261018, §5). The one argument
# that overrides that config is `sigmas` — diffusers 0.41
# `QwenImage21Pipeline.__call__` does, verbatim,
#     if sigmas is None:
#         sigmas = self.config.sample_sigmas
# and `retrieve_timesteps` hands a supplied `sigmas` to the scheduler, whose
# length sets the step count. `server.py` has no such field.
#
# This mod generates `<RUNTIME_DIR>/sigmas-server.py` from the launcher's
# server.py: same server, plus a `sigmas` request field (and a
# `num_inference_steps` that resamples the checkpoint's own grid instead of
# being silently dropped). The probe recipe's `command:` runs the generated
# file; the shipped launcher is never modified.
#
# Fail-closed: the patch is anchored on the launcher's exact step-plumbing
# lines and its `out = pipe(**call)` call site. A launcher that changed shape
# stops the launch instead of serving a server whose `sigmas` field is a lie.
# Idempotent from content: every launch regenerates the target from the
# launcher's source, so a re-run cannot double-patch or drift.
set -euo pipefail

#####################################################################
# Metadata
#####################################################################
export MOD_NAME="qwen-image-sigmas"
export MOD_DESCRIPTION="patch the Qwen-Image server so /generate accepts a sigmas schedule"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export TIMEOUT="${MOD_TIMEOUT:-120}"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export RUNTIME_DIR="${QI_RUNTIME_DIR:-${CACHEDIR}/qwen-image}"
export VENV_DIR="${RUNTIME_DIR}/venv"
# Dotted against the sibling mod: `mods:` is expanded in recipe order, so the
# launcher runs first and owns the venv this mod gates on.
export BASE_MOD="${QI_BASE_MOD:-$(dirname "${MOD_DIR}")/qwen-image-2.1-turbo-launcher}"
export TARGET="${RUNTIME_DIR}/sigmas-server.py"
export USER_UID="$(stat -c '%u' /cache/runtime)"
export USER_NAME="$(stat -c '%U' /cache/runtime)"
export USER_GID="$(stat -c '%g' /cache/runtime)"
export USER_GROUP="$(stat -c '%G' /cache/runtime)"

#####################################################################
# Helpers
#####################################################################
log() {
  local _message _ts
  _message="${*}"
  _ts="$(date -Ins)"
  printf '%s [%s] %s\n' "$_ts" "${MOD_NAME}" "${_message}" | tee -a "${LOGDIR}/${MOD_NAME}.log"
  [[ -x "$(type -fp logger)" ]] && logger -t "${MOD_NAME}" -- "${_message}" || true
}
log_var() { log "${1}=${!1:-}"; }

die() {
  log "FATAL: ${*}"
  exit 1
}

reown() {
  if [[ "$(id -u)" -eq 0 ]]; then
    log "resetting permissions to ${USER_UID}:${USER_GID} on ${*}"
    chown -R "${USER_UID}:${USER_GID}" "${@}"
  else
    # Same non-root image as the launcher: everything written is already owned
    # by the cache user, and chown would fail under `set -e`.
    log "not root (uid $(id -u)); skipping chown on ${*}"
  fi
}

#####################################################################
# Rotate logs
#####################################################################
if ! [[ -d "${LOGDIR}" ]]; then mkdir -p "${LOGDIR}"; fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log.gz" ]]; then rm -f "${LOGDIR}/${MOD_NAME}.log.gz"; fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log" ]]; then gzip "${LOGDIR}/${MOD_NAME}.log" || true; fi
touch "${LOGDIR}/${MOD_NAME}.log"
reown "${LOGDIR}"

log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log_var USER_NAME
log_var USER_GROUP

#####################################################################
# Fail-closed environment gate
#####################################################################
[[ -f "${BASE_MOD}/server.py" ]] || die "launcher server not staged at ${BASE_MOD}/server.py"
[[ -x "${VENV_DIR}/bin/python" ]] || die "engine venv missing at ${VENV_DIR}: the launcher mod must run before this one"
mkdir -p "${RUNTIME_DIR}"
reown "${RUNTIME_DIR}"

#####################################################################
# Generate the patched server
#####################################################################
# The anchor is the launcher's whole step-plumbing block: if the launcher ever
# stops forwarding the field, the replacement is the only place that knows how
# a step count is expressed, and a silent no-op patch would serve an 8-step
# schedule under a 4-step request.
export QI_SRC="${BASE_MOD}/server.py"
export QI_DST="${TARGET}"

patch_rc=0
"${VENV_DIR}/bin/python" - <<'PY' || patch_rc=$?
import os
import sys

src_path, dst_path = os.environ["QI_SRC"], os.environ["QI_DST"]
try:
    with open(src_path, encoding="utf-8") as fh:
        src = fh.read()
except OSError as exc:
    sys.exit("cannot read %s: %s" % (src_path, exc))

ANCHOR = (
    '    if req.get("num_inference_steps") is not None:\n'
    '        call["num_inference_steps"] = int(req["num_inference_steps"])\n'
)
if src.count(ANCHOR) != 1:
    sys.exit(
        "ANCHOR step-plumbing block found %d times (expected 1) in %s; "
        "refusing to generate an unpatchable server" % (src.count(ANCHOR), src_path)
    )
if src.count("out = pipe(**call)") != 1:
    sys.exit(
        "ANCHOR 'out = pipe(**call)' found %d times (expected 1) in %s"
        % (src.count("out = pipe(**call)"), src_path)
    )

REPLACEMENT = '''    # --- qwen-image-sigmas mod: one schedule field, honoured or refused -----
    # `num_inference_steps` cannot open the schedule: whenever the checkpoint
    # ships `sample_sigmas` the pipeline config wins and the argument is
    # dropped (measured: 12 -> steps: 8). `sigmas` is the override —
    # `if sigmas is None: sigmas = self.config.sample_sigmas` — and its
    # length is the step count the scheduler runs.
    sigmas = req.get("sigmas")
    if sigmas is None and req.get("num_inference_steps") is not None:
        n = int(req["num_inference_steps"])
        if not 1 <= n <= 256:
            raise ValueError("num_inference_steps must be 1..256, got %r" % (n,))
        saved = list(STATE["pipe"].config.sample_sigmas or [])
        if saved and n <= len(saved):
            # Resample the checkpoint's own grid, both endpoints kept.
            sigmas = (
                [saved[0]]
                if n == 1
                else [saved[round(i * (len(saved) - 1) / (n - 1))] for i in range(n)]
            )
        else:
            sigmas = [(n - i) / n for i in range(n)]
    if sigmas is not None:
        if not isinstance(sigmas, list) or not 1 <= len(sigmas) <= 256:
            raise ValueError(
                "sigmas must be a list of 1..256 floats, terminal sigma excluded"
            )
        sigmas = [float(v) for v in sigmas]
        if any(b >= a for a, b in zip(sigmas, sigmas[1:])):
            raise ValueError("sigmas must be strictly decreasing")
        if not 0.0 < sigmas[-1] <= sigmas[0] <= 1.0:
            raise ValueError("sigmas must start <= 1.0 and end > 0")
        call["sigmas"] = sigmas
'''

patched = src.replace(ANCHOR, REPLACEMENT)
if patched.count('call["sigmas"] = sigmas') != 1:
    sys.exit("replacement did not land exactly once in %s" % dst_path)

tmp = dst_path + ".tmp"
with open(tmp, "w", encoding="utf-8") as fh:
    fh.write(patched)
os.replace(tmp, dst_path)
print("patched %s -> %s (anchors 1/1, call site 1)" % (src_path, dst_path))
PY
[[ "${patch_rc}" -eq 0 ]] || die "sigmas patch failed (rc=${patch_rc}, message above)"

"${VENV_DIR}/bin/python" -m py_compile "${TARGET}" || die "generated server does not compile: ${TARGET}"
chmod 755 "${TARGET}"
reown "${TARGET}"
log_var TARGET
log "Done."