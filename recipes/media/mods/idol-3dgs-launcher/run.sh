#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Pre-launch mod for the speridlabs/idol image-to-3D arm (media lane, eval-only).
#
# The engine is the project's own `idol` SDK (pip `idol`, `python -m idol.sample`);
# neither sglang nor vLLM serve it. This mod stages a *venv* on the recipe's
# pinned image (--system-site-packages, so the image's torch/CUDA build is
# inherited and never re-downloaded) carrying the SDK plus its pure-Python
# dependencies, and it stages torchvision only when the image lacks it. It never
# replaces torch: the image's build is the one sm_121 support rides on, so the
# torch version is captured before the stage and asserted unchanged after it.
#
# Two gated encoders are NOT downloaded here. The WOPR profile disables model
# distribution (`distribution.model.enabled: false`) and the container runs
# `HF_HUB_OFFLINE=1`, so the arm serves from pre-staged pool snapshots only.
# The SDK resolves both encoders by repo id from idol's own config.json, with no
# revision argument, which in offline mode means it needs `refs/main` in each
# pool repo — a SHA-pinned `hf download --revision <sha>` writes no ref file, so
# this mod gates on `refs/main` plus the files it names and fails closed, naming
# the `hf download` and the gate acceptance that fixes it. Idol's weights are
# gated separately: the recipe passes `{model}` (the prepared snapshot) and the
# server asserts the five weight files are there.
#
# Fail-closed: the arm cannot serve without a usable venv or without the staged
# encoders, so every gate here stops the launch instead of starting a server
# that will die at `from_pretrained`. Idempotent from content: the engine gate is
# a real import and version assertion on the existing venv, not a marker file.
set -euo pipefail

#####################################################################
# Metadata
#####################################################################
export MOD_NAME="idol-3dgs-launcher"
export MOD_DESCRIPTION="idol SDK (image-to-3DGS) venv + sampler server"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export TIMEOUT="${MOD_TIMEOUT:-1800}"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export HF_HUB="${MOD_HF_HUB:-${HF_HUB_CACHE:-/cache/huggingface/hub}}"
# uv's symlinking gets messed up across permissions boundaries, so we copy.
export UV_LINK_MODE=copy
export USER_UID="$(stat -c '%u' /cache/runtime)"
export USER_NAME="$(stat -c '%U' /cache/runtime)"
export USER_GID="$(stat -c '%g' /cache/runtime)"
export USER_GROUP="$(stat -c '%G' /cache/runtime)"

export RUNTIME_DIR="${IDOL_RUNTIME_DIR:-${CACHEDIR}/idol}"
export VENV_DIR="${RUNTIME_DIR}/venv"
export SAMPLE_DIR="${RUNTIME_DIR}/samples"
export FIXTURE="${MOD_DIR}/fixtures/idol-fixture-rgba.png"

# Pinned engine requirements. diffusers 0.41.0 is the floor the media lane's
# sibling arms stage and it carries `AutoencoderKLFlux2` (the FLUX.2 VAE the SDK
# loads for its second image encoder); transformers 5.17 carries `DINOv3ViT`.
export DIFFUSERS_REQ="${IDOL_DIFFUSERS_REQ:-diffusers>=0.41.0}"
export TRANSFORMERS_REQ="${IDOL_TRANSFORMERS_REQ:-transformers>=5.17.0}"
export TENSORDICT_REQ="${IDOL_TENSORDICT_REQ:-tensordict>=0.8}"
export PLYFILE_REQ="${IDOL_PLYFILE_REQ:-plyfile>=1.0}"
# torchvision is only installed when the image lacks it, and then with --no-deps:
# 0.28.0 is the release whose `torch==2.13.0` pin matches the image's torch, and
# --no-deps keeps pip from considering a torch swap at all.
export TORCHVISION_PIN="${IDOL_TORCHVISION_PIN:-torchvision==0.28.0}"
# The SDK commit (speridlabs/idol-sdk main at 2026-11-08), installed from the
# archive tarball: no git binary in the serving image and no PyPI release of it.
export IDOL_SDK_REV="${IDOL_SDK_REV:-4702a7f00850e34b6e83a2170cc123c3e9570744}"
export IDOL_SDK_URL="https://codeload.github.com/speridlabs/idol-sdk/tar.gz/${IDOL_SDK_REV}"

#####################################################################
# Helpers
#####################################################################
reown() {
  if [[ "$(id -u)" -eq 0 ]]; then
    log "resetting permissions to ${USER_UID}:${USER_GID} on ${*}"
    chown -R "${USER_UID}:${USER_GID}" "${@}"
  else
    log "not root (uid $(id -u)); skipping chown on ${*}"
  fi
}

log() {
  local _ts
  _ts="$(date -Ins)"
  printf '%s [%s] %s\n' "$_ts" "${MOD_NAME}" "${*}" | tee -a "${LOGDIR}/${MOD_NAME}.log"
  [[ -x "$(type -fp logger)" ]] && logger -t "${MOD_NAME}" -- "${*}" || true
}
log_var() { log "${1}=${!1:-}"; }

#####################################################################
# Log rotation
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
# Managed runtime cache
#####################################################################
mkdir -p "${RUNTIME_DIR}" "${SAMPLE_DIR}"
reown "${RUNTIME_DIR}"

#####################################################################
# Fail-closed environment gate
#####################################################################
check() {
  if [[ -e "$1" ]]; then log "gate OK: $1"; else log "gate MISSING: $1"; exit 1; fi
}
check "${MOD_DIR}/server.py"
check "${FIXTURE}"
check "${HF_HUB}"

# An encoder repo must be readable offline: refs/main (written only by a
# branch-name fetch) must point at a snapshot dir holding the files the SDK
# loads. Fail-closed text names the acceptance, the fetch syntax and the trap.
gate_encoder() {
  local repo="$1"; shift
  local dir="${HF_HUB}/models--${repo//\//--}"
  local sha snap missing=()
  if [[ ! -f "${dir}/refs/main" ]]; then
    log "gate FAILED: ${repo} has no refs/main in ${dir}"
    log "  the SDK resolves this encoder by repo id with no revision, and offline resolution reads refs/main."
    log "  A sha-pinned 'hf download --revision <sha>' writes no ref file: re-fetch by branch after accepting the gate."
    log "  prerequisite: the account behind HF_TOKEN accepted https://huggingface.co/${repo}, then"
    log "    hf download ${repo} --include $(printf '%s ' "$@")"
    exit 1
  fi
  sha="$(cat "${dir}/refs/main")"
  snap="${dir}/snapshots/${sha}"
  check_path() { [[ -e "${snap}/$1" ]] || missing+=("$1"); }
  for f in "$@"; do check_path "${f}"; done
  if (( ${#missing[@]} )); then
    log "gate FAILED: ${repo} snapshot ${sha} is missing: ${missing[*]}"
    log "  prerequisite: hf download ${repo} --include $(printf '%s ' "$@")"
    exit 1
  fi
  log "gate OK: ${repo} refs/main ${sha}"
}

# Only the FLUX.2 VAE subfolder is used (ae/text-encoder/transformer weights are
# never loaded by the SDK), so the gate asks for exactly those two files.
gate_encoder facebook/dinov3-vith16plus-pretrain-lvd1689m \
  config.json model.safetensors preprocessor_config.json
gate_encoder black-forest-labs/FLUX.2-dev \
  vae/config.json vae/diffusion_pytorch_model.safetensors

IDOL_REPO_DIR="${HF_HUB}/models--speridlabs--idol"
if [[ ! -d "${IDOL_REPO_DIR}/snapshots" ]]; then
  log "gate MISSING: ${IDOL_REPO_DIR}/snapshots (idol weights are not staged in the pool)"
  log "  prerequisite: hf download speridlabs/idol   (ungated, apache-2.0, ~3 GB)"
  exit 1
fi
IDOL_SNAPSHOTS="$(ls -1 "${IDOL_REPO_DIR}/snapshots")"
log "gate OK: idol pool snapshots: ${IDOL_SNAPSHOTS//$'\n'/ }"

#####################################################################
# torch build gate: the sm_121 discriminator, read before staging anything
#####################################################################
TORCH_BEFORE="$(python3 -c 'import torch; print(torch.__version__)')"
log "image torch (before stage): ${TORCH_BEFORE}"
python3 - <<'PY'
import sys, torch
if not torch.cuda.is_available():
    sys.exit("gate FAILED: torch reports no CUDA device; this arm is a GPU arm (7.2 GB peak)")
print("cuda %s device %s capability sm_%d%d"
      % (torch.version.cuda, torch.cuda.get_device_name(0), *torch.cuda.get_device_capability(0)))
PY

#####################################################################
# Engine venv (content gate, then stage)
#####################################################################
# The gate is a real import: idol, the FLUX.2 VAE class and the torchvision op
# BiRefNet calls. torchvision is checked separately because the image may or may
# not carry it.
torchvision_ok() { "${VENV_DIR}/bin/python" -c 'import torchvision.ops.deform_conv2d' >/dev/null 2>&1; }
engine_ok() {
  [[ -x "${VENV_DIR}/bin/python" ]] || return 1
  "${VENV_DIR}/bin/python" - <<'PY' >/dev/null 2>&1
import importlib.metadata as md
from packaging.version import Version
assert Version(md.version("diffusers")) >= Version("0.41.0"), "diffusers below floor"
assert Version(md.version("transformers")) >= Version("5.17.0"), "transformers below floor"
from diffusers.models import AutoencoderKLFlux2  # noqa: F401
import idol  # noqa: F401
import tensordict  # noqa: F401
import plyfile  # noqa: F401
PY
}

if engine_ok && torchvision_ok; then
  log "engine gate OK (existing venv at ${VENV_DIR})"
else
  log "staging engine venv at ${VENV_DIR} (${DIFFUSERS_REQ} ${TRANSFORMERS_REQ} ${TENSORDICT_REQ} ${PLYFILE_REQ})"
  rm -rf "${VENV_DIR}"
  # Keep pip's cache inside our own managed dir: the ambient PIP cache path is
  # not writable in this container, and pip then disables caching entirely.
  export PIP_CACHE_DIR="${RUNTIME_DIR}/pip-cache"
  mkdir -p "${PIP_CACHE_DIR}"
  python3 -m venv --system-site-packages "${VENV_DIR}"
  "${VENV_DIR}/bin/python" -m pip install --quiet --upgrade pip
  "${VENV_DIR}/bin/python" -m pip install --quiet --upgrade \
    "${DIFFUSERS_REQ}" "${TRANSFORMERS_REQ}" "${TENSORDICT_REQ}" "${PLYFILE_REQ}" \
    accelerate safetensors
  if ! torchvision_ok; then
    log "image has no torchvision; installing ${TORCHVISION_PIN} with --no-deps"
    "${VENV_DIR}/bin/python" -m pip install --quiet --no-deps "${TORCHVISION_PIN}"
  fi
  # --no-deps on the SDK: its declared floor (torch>=2.5) would let pip look at
  # the torch requirement again, and the image's torch is the one that works.
  "${VENV_DIR}/bin/python" -m pip install --quiet --no-deps "${IDOL_SDK_URL}"
  if engine_ok && torchvision_ok; then
    log "engine gate OK after install"
  else
    log "engine gate FAILED after install"
    exit 1
  fi
fi

TORCH_AFTER="$("${VENV_DIR}/bin/python" -c 'import torch; print(torch.__version__)')"
if [[ "${TORCH_AFTER}" != "${TORCH_BEFORE}" ]]; then
  log "gate FAILED: staging changed the image torch (${TORCH_BEFORE} -> ${TORCH_AFTER})"
  exit 1
fi
ENGINE_VERSIONS="$("${VENV_DIR}/bin/python" - <<'PY'
import importlib.metadata as md
import torch
print("idol %s diffusers %s transformers %s tensordict %s torchvision %s torch %s cuda %s"
      % (md.version("idol"), md.version("diffusers"), md.version("transformers"),
         md.version("tensordict"), md.version("torchvision"), md.version("torch"), torch.version.cuda))
PY
)"
log "engine versions: ${ENGINE_VERSIONS}"

reown "${RUNTIME_DIR}"
log_var VENV_DIR
log_var SAMPLE_DIR
log_var FIXTURE
log "Done."
