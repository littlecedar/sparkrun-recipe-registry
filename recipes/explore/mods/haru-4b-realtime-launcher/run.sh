#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
# Install Haru-4B's serving plugin into the pinned vLLM-Omni image, then prove the
# engine hooks it targets exist there. Haru is a custom speech-to-speech architecture
# with no modeling code in the checkpoint, so nothing loads it until this plugin
# registers `HaruForConditionalGeneration` with vLLM and vLLM-Omni.
set -euo pipefail

export MOD_NAME="haru-4b-realtime-launcher"
export MOD_DESCRIPTION="Install the Haru-4B vLLM-Omni plugin and gate on its engine hooks"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"
export TIMEOUT="${MOD_TIMEOUT:-600}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export USER_UID="$(stat -c '%u' /cache/runtime)"
export USER_NAME="$(stat -c '%U' /cache/runtime)"
export USER_GID="$(stat -c '%g' /cache/runtime)"
export USER_GROUP="$(stat -c '%G' /cache/runtime)"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# PyPI releases of the author's two packages. The plugin is tested against the
# vLLM 0.32.0 / vLLM-Omni 0.32.0 releases, which is exactly what the image carries.
HARU_SPEECH_VERSION="0.1.1"
HARU_VLLM_VERSION="0.1.1"

reown() {
  if [[ "$(id -u)" != "0" ]]; then
    log "reown: not root (uid $(id -u)); skipping chown of ${*}"
    return 0
  fi
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
    return 0
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
  exit 2
}

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

#####################################################################
# Gate 1: the image must be a vLLM-Omni image on the 0.32 release line, the pair
# the plugin is tested against. This is the cheap named refusal; Gate 3 below is
# the load-bearing one, because a nightly can carry a 0.32 label and still have
# moved the hooks.
#####################################################################
python3 -c "import vllm, vllm_omni, torch" 2>/dev/null \
  || die "not a vLLM-Omni image: vllm + vllm_omni + torch must import"
log_cmd python3 -c "import vllm, vllm_omni, torch, transformers; print('vllm', vllm.__version__, '| vllm_omni', vllm_omni.__version__, '| torch', torch.__version__, '| transformers', transformers.__version__)"
python3 - <<'PY' || die "image is not vLLM 0.32.0 + vLLM-Omni 0.32.0: haru-speech-vllm 0.1.1 targets that release pair"
import sys
import vllm, vllm_omni
def parts(v):
    return tuple(int(p) for p in v.split(".")[:2] if p.isdigit())
if parts(vllm.__version__)[:2] != (0, 32) or parts(vllm_omni.__version__)[:2] != (0, 32):
    print("version mismatch: vllm %s, vllm_omni %s" % (vllm.__version__, vllm_omni.__version__), file=sys.stderr)
    sys.exit(1)
PY

#####################################################################
# Gate 2: the wheel's own deploy config is shipped by this mod (the plugin's
# is bundled inside the wheel; we carry a copy so the stage knobs are visible
# in this repository). Refuse to hand vLLM-Omni a path that does not exist.
#####################################################################
DEPLOY_CONFIG="${MOD_DIR}/deploy/haru.yaml"
[ -f "${DEPLOY_CONFIG}" ] || die "deploy config missing: ${DEPLOY_CONFIG}"
log "deploy config: ${DEPLOY_CONFIG}"

#####################################################################
# Install. `--no-deps` on purpose: the image already carries torch, transformers,
# vLLM and vLLM-Omni at the versions the plugin targets, and letting pip resolve
# `haru-speech`'s `transformers>=5.16` could silently upgrade the engine's own
# transformers. The two packages are pure Python; Gate 3 imports everything the
# serve path actually touches, so a dependency that is genuinely absent fails here
# by name instead of mid-load.
#####################################################################
installed_version() {
  python3 -c "import importlib.metadata as m; print(m.version('$1'))" 2>/dev/null || true
}

if [[ "$(installed_version haru-speech)" == "${HARU_SPEECH_VERSION}" \
   && "$(installed_version haru-speech-vllm)" == "${HARU_VLLM_VERSION}" ]]; then
  log "haru-speech ${HARU_SPEECH_VERSION} + haru-speech-vllm ${HARU_VLLM_VERSION} already installed; skipping"
else
  log "installing haru-speech==${HARU_SPEECH_VERSION} haru-speech-vllm==${HARU_VLLM_VERSION}"
  log_cmd pip install --no-deps --break-system-packages \
    "haru-speech==${HARU_SPEECH_VERSION}" "haru-speech-vllm==${HARU_VLLM_VERSION}"
fi

#####################################################################
# Gate 3: registration + the duplex plugin's own import surface. This is the
# load-bearing check: `register()` resolves the vLLM model registry,
# vLLM-Omni's omni registry, `Qwen3_5ForCausalLMConfig` and the pipeline
# registry, and `HaruDuplexPlugin` pulls `vllm_omni.engine.duplex.*` and the
# cumulative data plane. Any hook the image moved shows up here, before boot.
#####################################################################
log "gating on plugin registration"
python3 - <<'PY' 2>&1 | log || die "haru-speech-vllm does not register on this image: the engine hooks it needs are absent"
import haru, haru_vllm
from haru_vllm.duplex.plugin import HaruDuplexPlugin
haru_vllm.register()
print("haru", haru.__version__, "| haru_vllm", haru_vllm.__version__, "| registered HaruForConditionalGeneration")
PY

reown "${LOGDIR}"
log "mod complete"
