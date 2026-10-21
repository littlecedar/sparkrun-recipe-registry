#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Pre-launch mod for the LTX-2.5 T2V arm (explore lane, media-gen).
#
# The engine is ComfyUI, which is neither sglang nor vLLM: the recipe's
# `runtime: vllm` is only the launcher/distribution contract, and its
# `command:` runs
#   <RUNTIME_DIR>/venv/bin/python /workspace/mods/ltx-25-launcher/launcher.py
# so this mod owns the unit the runbook pinned (ComfyUI v0.34.0 + comfy-kitchen
# 0.2.31 + comfy-aimdo 0.4.15 + frontend 1.49.6 + workflow-templates 0.11.48 +
# embedded-docs 0.5.10, torch cu130) and the gated weights.
#
# Two hard constraints shape the flow:
#
#   1. sparkrun runs pre_exec hooks under a 600 s SSH timeout
#      (orchestration/hooks.py). A cold node needs a torch venv plus 36.9 GB of
#      weights, which must not block that hook. So the mod gates fast (token,
#      gate acceptance, nothing else), writes `stage.status`, and detaches the
#      heavy work with setsid/nohup; the launcher streams `stage.log` and waits.
#      A failed stage is fatal at the launcher (and therefore at readiness).
#
#   2. Lightricks/LTX-2.5 is `gated: auto`. sparkrun's anonymous distribution
#      cannot fetch it, so the recipe disables model distribution and this mod
#      fetches with the node's accepted HF_TOKEN into the node's HF cache
#      (`HF_HOME`, mounted at /cache/huggingface). No token, or a token whose
#      account has not accepted the gate, dies here with the prerequisite
#      named -- never a silent hang.
#
# Idempotent from content: the engine gate is a real import + exact version
# assertion, the weight gate is the five non-empty files, and both are re-run
# on every launch; a complete runtime dir makes this a no-op.
#
# Knobs (all `${VAR:-default}`): MOD_FETCH_TIMEOUT, MOD_STAGE_TIMEOUT,
# MOD_CACHEDIR, MOD_LOGDIR, LTX_RUNTIME_DIR, HF_HOME, HF_TOKEN.
#
# LICENSE: Lightricks/LTX-2.5 is under the ltx-2.x-community-license-agreement
# (free for Commercial Entities below a $10M annual-revenue threshold; read
# https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x before handing
# outputs to a third party). This mod ships a fetcher, not weights.
set -euo pipefail

export MOD_NAME="ltx-25-launcher"
export MOD_DESCRIPTION="ComfyUI v0.34.0 + gated LTX-2.5 weights for the T2V arm"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export TIMEOUT="${MOD_TIMEOUT:-180}"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export RUNTIME_DIR="${LTX_RUNTIME_DIR:-${CACHEDIR}/ltx-25}"
export COMFY_DIR="${RUNTIME_DIR}/ComfyUI"
export VENV_DIR="${RUNTIME_DIR}/venv"
export OUTPUT_DIR="${RUNTIME_DIR}/output"
export STAGE_STATUS="${RUNTIME_DIR}/stage.status"
export STAGE_LOG="${RUNTIME_DIR}/stage.log"
export MODLOG="${LOGDIR}/${MOD_NAME}.log"

export MODEL="Lightricks/LTX-2.5"
export MODEL_REVISION="49b093a39c19169a8a81721dcc541e07e945232f"
# The receipt measured this transformer; the bf16/int8-convrot siblings exist
# for other engines and are not fetched.
export TRANSFORMER="ltx-2.5-22b-distilled-transformer-nvfp4.safetensors"
# Explicit filenames on purpose: `hf download --include` silently drops the
# first pattern (runbook trap), so the files are listed one by one.
export WEIGHT_FILES=(
  "diffusion_models/${TRANSFORMER}"
  "vae/ltx-2.5-video-vae-bf16.safetensors"
  "vae/ltx-2.5-audio-vae-bf16.safetensors"
  "latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors"
  "text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors"
)
export COMFY_TAG="v0.34.0"
export COMFY_TARBALL_URL="https://codeload.github.com/comfyanonymous/ComfyUI/tar.gz/refs/tags/${COMFY_TAG}"
export TORCH_INDEX="https://download.pytorch.org/whl/cu130"

export HF_HOME="${HF_HOME:-/cache/huggingface}"
export HF_HUB_CACHE="${HF_HUB_CACHE:-${HF_HOME}/hub}"
export UV_LINK_MODE=copy
# The mount root is created by sparkrun; create it anyway so the ownership
# inference below cannot silently produce an empty uid:gid.
mkdir -p "${CACHEDIR}"
export USER_UID="$(stat -c '%u' "${CACHEDIR}")"
export USER_GID="$(stat -c '%g' "${CACHEDIR}")"
export USER_NAME="$(stat -c '%U' "${CACHEDIR}")"
export USER_GROUP="$(stat -c '%G' "${CACHEDIR}")"

#####################################################################
# Helpers
#####################################################################
reown() {
  if [[ -z "${USER_UID:-}" || -z "${USER_GID:-}" ]]; then
    log "no cache owner resolved; skipping chown on ${*}"
    return 0
  fi
  if [[ "$(id -u)" -eq 0 ]]; then
    log "resetting permissions to ${USER_UID}:${USER_GID} on ${*}"
    chown -R "${USER_UID}:${USER_GID}" "${@}"
  else
    log "not root (uid $(id -u)); skipping chown on ${*}"
  fi
}

log() {
  local _message _ts
  _message="${*}"
  _ts="$(date -Ins)"
  # stdout is the docker-exec/launcher stream; the detached stage's stdout is
  # appended to STAGE_LOG by its caller, so do not append there twice.
  printf '%s [%s] %s\n' "$_ts" "${MOD_NAME}" "${_message}" | tee -a "${MODLOG}"
  [[ -x "$(type -fp logger)" ]] && logger -t "${MOD_NAME}" -- "${_message}" || true
}
log_var() { log "$1=${!1:-}"; }

write_status() {
  # shellcheck disable=SC2068  # deliberate word split: "ok <ts>"
  printf '%s\n' "$*" > "${STAGE_STATUS}.tmp"
  mv -f "${STAGE_STATUS}.tmp" "${STAGE_STATUS}"
}

die() {
  log "FATAL: $*"
  write_status failed "$*"
  exit 1
}

#####################################################################
# Paths + logs
#####################################################################
mkdir -p "${RUNTIME_DIR}" "${OUTPUT_DIR}" "${LOGDIR}"
# A pristine node may have the HF mount but no hub/ dir yet (this arm disables
# sparkrun's model distribution, which would otherwise create it).
if [[ ! -d "${HF_HUB_CACHE}" ]]; then
  mkdir -p "${HF_HUB_CACHE}"
  [[ "$(id -u)" -eq 0 ]] && chown "${USER_UID}:${USER_GID}" "${HF_HUB_CACHE}" || true
fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log.gz" ]]; then rm -f "${LOGDIR}/${MOD_NAME}.log.gz"; fi
if [[ -f "${MODLOG}" ]]; then gzip "${MODLOG}" || true; fi
touch "${MODLOG}"
touch "${STAGE_LOG}"
reown "${LOGDIR}"

log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log_var USER_NAME

#####################################################################
# Gates (cheap; safe inside the 600 s pre_exec hook)
#####################################################################
check() {
  if [[ -e "$1" ]]; then log "gate OK: $1"; else log "gate MISSING: $1"; exit 1; fi
}
check "${MOD_DIR}/launcher.py"
check "${MOD_DIR}/expand2.py"
check "${HF_HUB_CACHE}"

for bin in curl tar python3 hf timeout; do
  command -v "${bin}" >/dev/null 2>&1 || die "required tool missing from the image: ${bin}"
done

engine_ok() {
  [[ -x "${VENV_DIR}/bin/python" ]] || return 1
  grep -q "^__version__ = \"0.34.0\"" "${COMFY_DIR}/comfyui_version.py" 2>/dev/null || return 1
  "${VENV_DIR}/bin/python" - <<'PY' >/dev/null 2>&1
import importlib.metadata as md
import torch
assert torch.cuda.is_available(), "torch cannot see CUDA"
assert tuple(int(x) for x in torch.__version__.split("+")[0].split(".")[:2]) >= (2, 14), torch.__version__
for name, ver in {
    "comfy-kitchen": "0.2.31",
    "comfy-aimdo": "0.4.15",
    "comfyui-frontend-package": "1.49.6",
    "comfyui-workflow-templates": "0.11.48",
    "comfyui-embedded-docs": "0.5.10",
}.items():
    assert md.version(name) == ver, "%s == %s, expected %s" % (name, md.version(name), ver)
PY
}

weights_ok() {
  local f
  for f in "${WEIGHT_FILES[@]}"; do
    [[ -s "${COMFY_DIR}/models/${f}" ]] || return 1
  done
}

token_present() {
  [[ -n "${HF_TOKEN:-}" || -n "${HUGGING_FACE_HUB_TOKEN:-}" || -s "${HF_HOME}/token" ]]
}

resolve_token() {
  if [[ -z "${HF_TOKEN:-}" ]]; then
    if [[ -n "${HUGGING_FACE_HUB_TOKEN:-}" ]]; then
      HF_TOKEN="${HUGGING_FACE_HUB_TOKEN}"
    elif [[ -s "${HF_HOME}/token" ]]; then
      HF_TOKEN="$(tr -d '\r\n' < "${HF_HOME}/token")"
    fi
  fi
  export HF_TOKEN
}

# The repo is gated. The README route answers 200 anonymously (the card stays
# public), so acceptance must be proved on a *weight* blob: a 1-byte range
# request returns 206 for an accepted token and 401 otherwise. Probe before
# detaching, so the failure is a named prerequisite instead of a launch that
# stalls or dies mid-download.
export ACCESS_PROBE_FILE="${WEIGHT_FILES[2]}"   # audio VAE: smallest weight file
access_ok() {
  local code
  code="$(curl -sS -L -o /dev/null -w '%{http_code}' --max-time 30 -r 0-0 \
    -H "Authorization: Bearer ${HF_TOKEN}" \
    "https://huggingface.co/${MODEL}/resolve/${MODEL_REVISION}/${ACCESS_PROBE_FILE}" 2>/dev/null || true)"
  log "gate acceptance probe: HTTP ${code:-none} for ${MODEL}@${MODEL_REVISION}/${ACCESS_PROBE_FILE} (206 = accepted)"
  [[ "${code}" == "206" ]]
}

#####################################################################
# Heavy staging (runs detached, not under the 600 s hook)
#####################################################################
stage_engine() {
  if engine_ok; then
    log "engine gate OK (existing ComfyUI ${COMFY_TAG} + venv at ${VENV_DIR})"
    return 0
  fi
  log "staging ComfyUI ${COMFY_TAG} + venv at ${VENV_DIR}"
  rm -rf "${COMFY_DIR}.tmp" "${VENV_DIR}"
  mkdir -p "${COMFY_DIR}.tmp"
  curl -fsSL --retry 3 --max-time 900 -o "${RUNTIME_DIR}/comfyui-${COMFY_TAG}.tar.gz" \
    "${COMFY_TARBALL_URL}" || { log "ComfyUI tarball download failed"; return 1; }
  tar xzf "${RUNTIME_DIR}/comfyui-${COMFY_TAG}.tar.gz" -C "${COMFY_DIR}.tmp" --strip-components=1 \
    || { log "ComfyUI tarball extraction failed"; return 1; }
  grep -q "^__version__ = \"0.34.0\"" "${COMFY_DIR}.tmp/comfyui_version.py" \
    || { log "downloaded ComfyUI is not v0.34.0"; return 1; }
  rm -rf "${COMFY_DIR}"
  mv "${COMFY_DIR}.tmp" "${COMFY_DIR}"

  export PIP_CACHE_DIR="${RUNTIME_DIR}/pip-cache"
  mkdir -p "${PIP_CACHE_DIR}"
  python3 -m venv "${VENV_DIR}" || return 1
  "${VENV_DIR}/bin/python" -m pip install --quiet --upgrade pip setuptools wheel || return 1
  # torch is unpinned on the cu130 index, as installed by the runbook: it
  # resolves to the measured 2.14.1 + torchvision 0.29.1 + torchaudio 2.11.0.
  "${VENV_DIR}/bin/python" -m pip install --quiet \
    torch torchvision torchaudio --index-url "${TORCH_INDEX}" || return 1
  # The runbook's install, verbatim: the image's requirements minus torch.
  grep -v -E '^(torch|torchvision|torchaudio)([<>=!~ ]|$)' "${COMFY_DIR}/requirements.txt" \
    > "${RUNTIME_DIR}/req-notorch.txt" || return 1
  "${VENV_DIR}/bin/python" -m pip install --quiet -r "${RUNTIME_DIR}/req-notorch.txt" || return 1
  if engine_ok; then
    log "engine gate OK after install"
  else
    log "engine gate FAILED after install (python3.12-dev is required for triton's first compile)"
    return 1
  fi
}

stage_weights() {
  if weights_ok; then
    log "weights present under ${COMFY_DIR}/models; nothing to fetch"
    return 0
  fi
  resolve_token
  [[ -n "${HF_TOKEN:-}" ]] || { log "no HF token after gate (race)"; return 1; }
  # sparkrun exports HF_HUB_OFFLINE=1 for its distribution contract (models
  # arrive already staged); this arm fetches its own gated weights, and under
  # that flag `hf download` refuses to reach the Hub. Observed 2026-10-21:
  # "offline mode is enabled" right after the engine stage passed, and an
  # `unset` was not enough from the CLI wrapper — set it to 0 explicitly.
  export HF_HUB_OFFLINE=0
  export HF_HUB_DOWNLOAD_TIMEOUT="${HF_HUB_DOWNLOAD_TIMEOUT:-60}"
  export HF_HUB_ETAG_TIMEOUT="${HF_HUB_ETAG_TIMEOUT:-30}"
  export HF_HUB_DISABLE_PROGRESS_BARS=1
  log "fetching ${#WEIGHT_FILES[@]} files of ${MODEL}@${MODEL_REVISION} into ${HF_HUB_CACHE}"
  local rc=0
  timeout "${MOD_FETCH_TIMEOUT:-7200}" hf download "${MODEL}" \
    --revision "${MODEL_REVISION}" --format quiet "${WEIGHT_FILES[@]}" \
    >>"${STAGE_LOG}" 2>&1 || rc=$?
  if [[ "${rc}" -ne 0 ]]; then
    log "hf download FAILED rc=${rc}; last lines:"
    tail -n 20 "${STAGE_LOG}" | while read -r line; do log "  ${line}"; done
    return 1
  fi
  local snap="${HF_HUB_CACHE}/models--${MODEL//\//--}/snapshots/${MODEL_REVISION}"
  local f src
  for f in "${WEIGHT_FILES[@]}"; do
    src="${snap}/${f}"
    if [[ ! -s "${src}" ]]; then log "missing after download: ${src}"; return 1; fi
    mkdir -p "${COMFY_DIR}/models/$(dirname "${f}")"
    ln -sfn "${src}" "${COMFY_DIR}/models/${f}"
    log "linked models/${f} -> ${src}"
  done
  # root wrote into the shared HF cache; hand the repo tree back to the cache
  # owner so user-side `hf` runs and later non-root readers keep working.
  reown "${HF_HUB_CACHE}/models--${MODEL//\//--}"
  [[ -d "${HF_HUB_CACHE}/.locks" ]] && reown "${HF_HUB_CACHE}/.locks" || true
  weights_ok
}

run_stage() {
  local rc=0
  stage_engine || rc=1
  if [[ "${rc}" -eq 0 ]]; then
    stage_weights || rc=1
  fi
  reown "${RUNTIME_DIR}" || true
  if [[ "${rc}" -eq 0 ]] && engine_ok && weights_ok; then
    write_status ok "$(date -Ins)"
    log "stage complete: ComfyUI ${COMFY_TAG} + ${#WEIGHT_FILES[@]} weight files"
  else
    write_status failed "stage rc=${rc}"
    log "stage FAILED (rc=${rc}); see ${STAGE_LOG}"
  fi
  exit "${rc}"
}

#####################################################################
# Main
#####################################################################
if [[ "${1:-}" == "--stage" ]]; then
  run_stage
fi

if engine_ok && weights_ok; then
  write_status ok "$(date -Ins) already-staged"
  log "runtime dir complete; nothing to stage"
else
  # Fail-closed prerequisites, synchronously (the hook's only window for a
  # named error). The stage job itself never blocks this hook.
  if ! weights_ok; then
    if ! token_present; then
      die "${MODEL} is gated and no HF token is visible on this node. Per node: (1) accept the gate at https://huggingface.co/${MODEL} with the account that owns the token; (2) run 'hf auth login' (writes \${HF_HOME}/token = ${HF_HOME}/token) or export HF_TOKEN; (3) relaunch. sparkrun's anonymous distribution cannot fetch a gated repo, so the recipe disables model distribution."
    fi
    resolve_token
    access_ok || die "${MODEL}@${MODEL_REVISION} is not readable with this node's token (gated repo; the weight probe did not return HTTP 206). The token must belong to an account that accepted https://huggingface.co/${MODEL}; re-run 'hf auth login' on this node with that account. Nothing will be downloaded until this passes."
  fi
  write_status running "pid=pending"
  log "detaching stage job (600 s pre_exec hook; log ${STAGE_LOG})"
  setsid nohup bash "${BASH_SOURCE[0]}" --stage >>"${STAGE_LOG}" 2>&1 </dev/null &
  log "stage pid $! is detached; the launcher waits for ${STAGE_STATUS}"
fi

# The 2200 MHz cap is a HOST setting (`sudo nvidia-smi -lgc 0,2200`); the
# container image has no nvidia-smi, so this is a note, not a gate. It is the
# sustained-load power-loss fix: without it a second consecutive long
# generation can take the node down, and every measured LTX cell was taken
# under the cap (costs ~20 % per run).
log "WARN clock cap: verify the HOST ran 'sudo nvidia-smi -lgc 0,2200' before launch (sustained-load power-loss fix; all LTX timings are capped)"
log "license: ${MODEL} is ltx-2.x-community-license-agreement (free below a \$10M-revenue Commercial Entity threshold); read the 2.x text before shipping outputs to third parties"
log "Done."