#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Pre-launch mod for the Viggle-Remake v2v arm (media lane).
#
# The engine is ComfyUI, which is neither sglang nor vLLM: the recipe's
# `runtime: vllm` is only the launcher/distribution contract, and its
# `command:` runs
#   <RUNTIME_DIR>/venv/bin/python /workspace/mods/viggle-remake-launcher/launcher.py
# so this mod owns ComfyUI (tag-pinned), the Viggle node pack, the MiniMax-H3
# single-file repack the graph loads, and the two Remake LoRAs.
#
# Three constraints shape the flow:
#
#   1. sparkrun runs pre_exec hooks under a 600 s SSH timeout
#      (orchestration/hooks.py). A cold node needs a torch venv plus ~39.5 GiB
#      of base components, so the mod gates fast, writes `stage.status` and
#      detaches the heavy work; launcher.py streams `stage.log` and waits.
#
#   2. The base model here is NOT the repo the recipe names. The graph needs
#      Comfy-Org's single-file repack of MiniMax-H3, and the bf16 build is
#      124 GB against ~109 GB of usable unified memory, so this arm stages the
#      AdaLN-PRUNED fp8 DiT + the NVFP4-AWQ text encoder + both VAEs (39.54 GiB
#      measured by the shipped H3 arm) and repoints the graph's two loaders at
#      them. Both repos are fetched by file, not by repo: `hf download` with
#      explicit filenames, because this repo's total size is 156 GiB.
#
#   3. Idempotent from content: the ComfyUI gate re-reads the tag marker it
#      wrote, the weight gate is the six files, and a complete runtime dir makes
#      this mod a no-op.
#
# Knobs (all `${VAR:-default}`): MOD_FETCH_TIMEOUT, MOD_STAGE_TIMEOUT,
# MOD_CACHEDIR, MOD_LOGDIR, VIGGLE_RUNTIME_DIR, OMNI_RUNTIME_DIR, HF_HOME,
# HF_TOKEN.
#
# LICENSE: Viggle Remake is a Model Derivative of MiniMax H3 and is distributed
# under the MiniMax H3 COMMUNITY LICENSE AGREEMENT (territorial: not usable in
# the EU, UK, Republic of Korea or USA; NOTICE carriage; credit line). The
# node pack, the workflows and the Python under comfyui/ are Apache-2.0. This
# mod ships a fetcher, not weights. Read the recipe banner.
set -euo pipefail

export MOD_NAME="viggle-remake-launcher"
export MOD_DESCRIPTION="ComfyUI 0.42.0 + MiniMax-H3 pruned repack + Viggle Remake LoRAs"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export TIMEOUT="${MOD_TIMEOUT:-180}"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export RUNTIME_DIR="${VIGGLE_RUNTIME_DIR:-${CACHEDIR}/viggle-remake}"
export COMFY_DIR="${RUNTIME_DIR}/ComfyUI"
export VENV_DIR="${RUNTIME_DIR}/venv"
export WORKFLOW_DIR="${RUNTIME_DIR}/workflows"
export OUTPUT_DIR="${RUNTIME_DIR}/output"
export INPUT_DIR="${RUNTIME_DIR}/input"
export STAGE_STATUS="${RUNTIME_DIR}/stage.status"
export STAGE_LOG="${RUNTIME_DIR}/stage.log"
export STAGED_ENV="${RUNTIME_DIR}/staged.env"
export MODLOG="${LOGDIR}/${MOD_NAME}.log"

# The LoRA repo, pinned. The recipe carries this same pin; launcher.py fails
# closed when the two disagree (staged.env vs --revision).
export MODEL="Viggle/Viggle-Remake"
export MODEL_REVISION="7e5be143702dd53b9154482de673b8519ed2d4d6"
# The base repack the graph loads, and the snapshot the shipped H3 arm measured.
export BASE_MODEL="Comfy-Org/MiniMax-H3"
export BASE_REVISION="e5eb578a89295337b8ff433a035929ce0279e0b6"

export COMFY_TAG="v0.42.0"
export COMFY_TARBALL_URL="https://codeload.github.com/comfyanonymous/ComfyUI/tar.gz/refs/tags/${COMFY_TAG}"
export TORCH_INDEX="https://download.pytorch.org/whl/cu130"

# Explicit filenames on purpose: `hf download --include` silently drops the
# first pattern (runbook trap), so every file is named.
export BASE_FILES=(
  "diffusion_models/minimax_h3_fl2va_pruned_fp8_scaled.safetensors"
  "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
  "vae/minimax_h3_video_vae_fp16.safetensors"
  "vae/minimax_h3_audio_vae_fp32.safetensors"
)
export LORA_FILES=(
  "comfyui/viggle_remake_swap_comfyui.safetensors"
  "comfyui/viggle_remake_edit_comfyui.safetensors"
)

export HF_HOME="${HF_HOME:-/cache/huggingface}"
export HF_HUB_CACHE="${HF_HUB_CACHE:-${HF_HOME}/hub}"
export UV_LINK_MODE=copy
mkdir -p "${CACHEDIR}"
export USER_UID="$(stat -c '%u' "${CACHEDIR}")"
export USER_GID="$(stat -c '%g' "${CACHEDIR}")"
export USER_NAME="$(stat -c '%U' "${CACHEDIR}")"
export USER_GROUP="$(stat -c '%G' "${CACHEDIR}")"

#####################################################################
# Helpers
#####################################################################
reown() {
  local p="$1"
  [[ -e "$p" ]] || return 0
  chown -R "${USER_UID}:${USER_GID}" "$p" 2>/dev/null || true
}

log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "${MODLOG}" >&2; }
log_var() { log "$1=${!1:-}"; }

write_status() { printf '%s\n' "$*" > "${STAGE_STATUS}"; reown "${STAGE_STATUS}"; }

die() { write_status "failed $*"; log "FATAL: $*"; exit 1; }

#####################################################################
# Paths + logs
#####################################################################
mkdir -p "${RUNTIME_DIR}" "${OUTPUT_DIR}" "${INPUT_DIR}" "${WORKFLOW_DIR}" "${LOGDIR}"
if [[ ! -d "${HF_HUB_CACHE}" ]]; then
  # This arm disables sparkrun's model distribution, so a pristine node may
  # have the pool mounted at /cache but no hub/ dir yet.
  mkdir -p "${HF_HUB_CACHE}" || die "cannot create HF cache ${HF_HUB_CACHE}; is the pool mounted?"
fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log.gz" ]]; then rm -f "${LOGDIR}/${MOD_NAME}.log.gz"; fi
if [[ -f "${MODLOG}" ]]; then gzip "${MODLOG}" || true; fi
touch "${MODLOG}" "${STAGE_LOG}"
reown "${LOGDIR}"

log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log_var USER_NAME

#####################################################################
# Gates (cheap; safe inside the 600 s pre_exec hook)
#####################################################################
for f in launcher.py run.sh workflows/remake_swap_api.json workflows/remake_edit_api.json; do
  [[ -e "${MOD_DIR}/${f}" ]] || die "mod payload missing: ${MOD_DIR}/${f}"
done
for bin in curl tar python3 hf; do
  command -v "${bin}" >/dev/null 2>&1 || die "required tool missing from the image: ${bin}"
done
[[ -e "${VENV_DIR}/bin/python" ]] || log "engine: venv absent, staging needed"
[[ -f "${COMFY_DIR}/.comfy-tag" ]] || log "engine: tag marker absent, staging needed"

engine_ok() {
  [[ -x "${VENV_DIR}/bin/python" ]] || return 1
  [[ -f "${COMFY_DIR}/main.py" ]] || return 1
  [[ -f "${COMFY_DIR}/custom_nodes/ComfyUI-Viggle-Remake/nodes.py" ]] || return 1
  [[ "$(cat "${COMFY_DIR}/.comfy-tag" 2>/dev/null)" == "${COMFY_TAG}" ]] || return 1
  "${VENV_DIR}/bin/python" -c 'import torch; assert torch.cuda.is_available()' >/dev/null 2>&1 || return 1
  return 0
}

weights_ok() {
  local f
  for f in "${BASE_FILES[@]}"; do
    [[ -s "${COMFY_DIR}/models/${f}" ]] || return 1
  done
  for f in "${LORA_FILES[@]}"; do
    [[ -s "${COMFY_DIR}/models/loras/$(basename "$f")" ]] || return 1
  done
  return 0
}

#####################################################################
# Heavy staging (runs detached, not under the 600 s hook)
#####################################################################
stage_engine() {
  log "stage: ComfyUI ${COMFY_TAG} venv"
  python3 -m venv "${VENV_DIR}" || die "venv create failed"
  "${VENV_DIR}/bin/pip" install -q --upgrade pip wheel || die "pip bootstrap failed"
  "${VENV_DIR}/bin/pip" install -q --index-url "${TORCH_INDEX}" torch torchvision torchaudio \
    || die "torch cu130 install failed"
  local tmp; tmp="$(mktemp -d)"
  curl -fsSL "${COMFY_TARBALL_URL}" -o "${tmp}/comfy.tgz" || die "ComfyUI tarball fetch failed"
  tar -xzf "${tmp}/comfy.tgz" -C "${tmp}" || die "ComfyUI tarball unpack failed"
  rm -rf "${COMFY_DIR}"
  mv "${tmp}/ComfyUI-${COMFY_TAG#v}" "${COMFY_DIR}" || die "ComfyUI tree move failed"
  "${VENV_DIR}/bin/pip" install -q -r "${COMFY_DIR}/requirements.txt" || die "ComfyUI requirements failed"
  # The node pack needs >=1.0 for multi-`--include` downloads; pin nothing else.
  "${VENV_DIR}/bin/pip" install -q "huggingface_hub>=1.0" || die "huggingface_hub install failed"
  # The node pack is the repo's own code (comfyui/ComfyUI-Viggle-Remake), not
  # ours; this mod ships the stage + the HTTP shim, not the nodes.
  rm -rf "${COMFY_DIR}/custom_nodes/ComfyUI-Viggle-Remake"
  hf download "${MODEL}" --revision "${MODEL_REVISION}" \
    --include "comfyui/ComfyUI-Viggle-Remake/*" --local-dir "${RUNTIME_DIR}/node-dl" \
    || die "node pack fetch failed"
  cp -r "${RUNTIME_DIR}/node-dl/comfyui/ComfyUI-Viggle-Remake" "${COMFY_DIR}/custom_nodes/" \
    || die "node pack copy failed"
  rm -rf "${RUNTIME_DIR}/node-dl"
  printf '%s\n' "${COMFY_TAG}" > "${COMFY_DIR}/.comfy-tag"
  rm -rf "${tmp}"
}

stage_weights() {
  local f
  log "stage: base repack ${BASE_MODEL}@${BASE_REVISION}"
  mkdir -p "${COMFY_DIR}/models/diffusion_models" "${COMFY_DIR}/models/text_encoders" \
           "${COMFY_DIR}/models/vae" "${COMFY_DIR}/models/loras"
  for f in "${BASE_FILES[@]}"; do
    [[ -s "${COMFY_DIR}/models/${f}" ]] && { log "have ${f}"; continue; }
    hf download "${BASE_MODEL}" --revision "${BASE_REVISION}" \
      --include "${f}" --local-dir "${COMFY_DIR}/models" || die "base fetch failed: ${f}"
  done
  log "stage: LoRAs ${MODEL}@${MODEL_REVISION}"
  for f in "${LORA_FILES[@]}"; do
    local dst="${COMFY_DIR}/models/loras/$(basename "$f")"
    [[ -s "${dst}" ]] && { log "have $(basename "$f")"; continue; }
    hf download "${MODEL}" --revision "${MODEL_REVISION}" \
      --include "${f}" --local-dir "${RUNTIME_DIR}/viggle-remake-dl" || die "lora fetch failed: ${f}"
    mv "${RUNTIME_DIR}/viggle-remake-dl/${f}" "${dst}" || die "lora move failed: ${f}"
  done
  rm -rf "${RUNTIME_DIR}/viggle-remake-dl"
}

run_stage() {
  log "stage: start (pid $$)"
  stage_engine || die "engine stage failed"
  stage_weights || die "weight stage failed"
  cp -f "${MOD_DIR}"/workflows/*_api.json "${WORKFLOW_DIR}/" || die "workflow copy failed"
  printf 'MODEL=%s\nMODEL_REVISION=%s\nBASE_MODEL=%s\nBASE_REVISION=%s\nCOMFY_TAG=%s\n' \
    "${MODEL}" "${MODEL_REVISION}" "${BASE_MODEL}" "${BASE_REVISION}" "${COMFY_TAG}" > "${STAGED_ENV}"
  reown "${RUNTIME_DIR}"
  write_status "ok"
  log "stage: done"
}

#####################################################################
# Main
#####################################################################
if [[ "${1:-}" == "--stage" ]]; then
  run_stage
  exit 0
fi

if engine_ok && weights_ok; then
  log "engine + weights present (idempotent no-op)"
  cp -f "${MOD_DIR}"/workflows/*_api.json "${WORKFLOW_DIR}/" || die "workflow copy failed"
  write_status "ok"
  log "license: Viggle Remake is a MiniMax H3 Model Derivative under the MiniMax H3 COMMUNITY LICENSE (territorial: not the EU/UK/KR/USA; NOTICE carriage; credit line); read the recipe banner"
  log "Done."
  exit 0
fi

write_status "pending"
log "stage: detaching (cold runtime or tag change)"
setsid nohup "$0" --stage >>"${STAGE_LOG}" 2>&1 &
log "stage: detached pid $!"
log "Done."