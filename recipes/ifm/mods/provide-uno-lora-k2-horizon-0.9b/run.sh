#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Purpose: make the IFM/K2-Horizon-0.9B-Uno LoRA adapter available at a fixed
#          in-container path for --uno-lora-path, since sparkrun's artifact
#          distribution only fetches a recipe's single `model:` field.
# See: recipes/ifm/k2-horizon-0.9b-bf16-uno-sglang.yaml
set -euo pipefail

#####################################################################
# README
#####################################################################
# WHY THIS MOD EXISTS
#
# sparkrun distributes exactly one artifact per recipe: the `model:` field. SGLang's
# native UNO speculative algorithm needs a SECOND one -- a PEFT conditional-LoRA
# adapter (IFM/K2-Horizon-0.9B-Uno) passed via --uno-lora-path. There is no recipe
# field for a second artifact, so it has to be placed by a mod.
#
# WHERE IT GOES, AND WHY NOT THE HF CACHE
#
# The container runs with HF_HOME=/cache/huggingface, HF_HUB_CACHE
# =/cache/huggingface/hub and HF_HUB_OFFLINE=1. Writing into the HF cache looks
# tidier but is the wrong place: sparkrun owns that tree's layout and its
# snapshot/refs bookkeeping, and a hand-written snapshot directory can be pruned
# or confuse the sync. A private path under the mod cache (/cache/runtime) is
# persistent across launches, is ours to own, and is invisible to the sync.
#
# IDEMPOTENCE
#
# The adapter is 223,917,616 B. Re-verifying by size then SHA-256 keeps a valid copy
# and re-fetches a truncated one, so a relaunch needs no network.
#
# EXPECTED VALUES (VERIFIED from the HF API on 2026-10-18; re-derive with:
#   curl -s https://huggingface.co/api/models/IFM/K2-Horizon-0.9B-Uno?blobs=true)
#   revision cbb5d835689a1e809e06ce1a3efff35bab0c86eb
#   adapter_model.safetensors  size 223917616
#                            sha256 5a499229d19ef4a69eb0b21884819d1b67cd983ba02b7ee2031ba8567dedfe4e
# If the pin moves, update UNO_LORA_SHA256 too. Do not relax the check to "size
# only" -- the point is to know which weights a result came from.
#
# BASE REVISION (the pairing question)
#
# adapter_config.json declares base_model_name_or_path IFM/K2-Horizon-0.9B and
# `"revision": null`, i.e. it names no base commit. Its conversion_summary.json
# pins base_weight_sha256 6392cc67c8dcc7aef1575f94ecdf3c7113b7d0e8f4e7058c4c3c74d4d876c365,
# and the base repo's single weight shard carries that same LFS sha256 at
# 9fa6faa5 (rl_stem), 76db896c and 383cb663 -- the commits after 9fa6faa5 change
# chat templates only. So the recipe's 383cb663 pin is the weights this adapter
# was trained against; there is no older-base pairing to honour.
#####################################################################

#####################################################################
# Metadata
#####################################################################
export MOD_NAME="provide-uno-lora-k2-horizon-0.9b"
export MOD_DESCRIPTION="Fetch and verify the IFM/K2-Horizon-0.9B-Uno adapter for --uno-lora-path"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export TIMEOUT="${MOD_TIMEOUT:-900}"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export USER_UID="$(stat -c '%u' "${CACHEDIR}")"
export USER_NAME="$(stat -c '%U' "${CACHEDIR}")"
export USER_GID="$(stat -c '%g' "${CACHEDIR}")"
export USER_GROUP="$(stat -c '%G' "${CACHEDIR}")"

export UNO_LORA_REPO="${UNO_LORA_REPO:-IFM/K2-Horizon-0.9B-Uno}"
export UNO_LORA_REVISION="${UNO_LORA_REVISION:-cbb5d835689a1e809e06ce1a3efff35bab0c86eb}"
export UNO_LORA_DIR="${UNO_LORA_DIR:-/cache/runtime/uno-lora/K2-Horizon-0.9B-Uno}"
export UNO_LORA_SIZE="${UNO_LORA_SIZE:-223917616}"
export UNO_LORA_SHA256="${UNO_LORA_SHA256:-5a499229d19ef4a69eb0b21884819d1b67cd983ba02b7ee2031ba8567dedfe4e}"

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
  if [[ "$(id -u)" != "0" ]]; then
    # Not every image runs the container as root (vllm/vllm-openai is 1000:1000):
    # a chown of root-owned leftovers fails with EPERM and, under `set -e`, takes the
    # whole pre-exec hook down. Skip instead of failing.
    log "reown: not root (uid $(id -u)); skipping chown of ${*}"
    return 0
  fi
  log "resetting permissions to ${USER_UID}:${USER_GID} on ${*}"
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
    return 0
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
  gzip "${LOGDIR}/${MOD_NAME}.log"
  touch "${LOGDIR}/${MOD_NAME}.log"
fi
reown "${LOGDIR}"

#####################################################################
# Main mod scripting zone
#####################################################################
log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log "${MOD_MAINTAINER}"
log_var UNO_LORA_REPO
log_var UNO_LORA_REVISION
log_var UNO_LORA_DIR

mkdir -p "${UNO_LORA_DIR}"

#####################################################################
# Verify-or-fetch
#####################################################################
verify() {
  local f="${UNO_LORA_DIR}/adapter_model.safetensors"
  [[ -f "${f}" ]] || return 1
  local size
  size="$(stat -c '%s' "${f}" 2>/dev/null || echo 0)"
  if [[ "${size}" != "${UNO_LORA_SIZE}" ]]; then
    log "size mismatch: have ${size}, want ${UNO_LORA_SIZE}"
    return 1
  fi
  local have
  have="$(sha256sum "${f}" | cut -d' ' -f1)"
  if [[ "${have}" != "${UNO_LORA_SHA256}" ]]; then
    log "sha256 mismatch: have ${have}, want ${UNO_LORA_SHA256}"
    return 1
  fi
  return 0
}

if verify; then
  log "adapter already present and verified - skipping download"
else
  log "adapter missing or invalid - fetching ${UNO_LORA_REPO}@${UNO_LORA_REVISION}"

  # HF_HUB_OFFLINE=1 is set by the runtime plugin so the SERVED model never
  # reaches the network. This fetch is the deliberate exception, scoped to this
  # python process: it must not leak into the server process, and it must not
  # make the main model resolution online.
  if ! (
    set -euo pipefail
    export HF_HUB_OFFLINE=0
    HF_REPO="${UNO_LORA_REPO}" HF_REV="${UNO_LORA_REVISION}" \
    HF_DIR="${UNO_LORA_DIR}" python3 - <<'PY'
import os
from huggingface_hub import snapshot_download

p = snapshot_download(
    repo_id=os.environ["HF_REPO"],
    revision=os.environ["HF_REV"],
    local_dir=os.environ["HF_DIR"],
    # Only the two artifacts the engine reads.
    allow_patterns=["adapter_config.json", "adapter_model.safetensors"],
)
print("snapshot_download ->", p)
PY
  ) 2>&1 | log; then
    log "FATAL: could not fetch ${UNO_LORA_REPO}@${UNO_LORA_REVISION}"
    log "This recipe cannot run without --uno-lora-path. Either pre-seed"
    log "  ${UNO_LORA_DIR}"
    log "by hand on every node, or fix network access for this mod."
    exit 1
  fi

  # adapter_config.json is required: sglang reads r / lora_alpha / target_modules
  # from it, so a directory holding only the weights is not a usable adapter.
  [[ -f "${UNO_LORA_DIR}/adapter_config.json" ]] || {
    log "FATAL: adapter_config.json missing in ${UNO_LORA_DIR}"
    exit 1
  }
  verify || { log "FATAL: post-download verification failed"; exit 1; }
  log "download verified"
fi

#####################################################################
# Report what the adapter declares, so the launch log records it
#####################################################################
python3 - <<'PY' || true
import json, pathlib
p = pathlib.Path("/cache/runtime/uno-lora/K2-Horizon-0.9B-Uno/adapter_config.json")
c = json.loads(p.read_text())
print(
    "adapter: base=%s r=%s lora_alpha=%s scaling=%s targets=%d"
    % (
        c.get("base_model_name_or_path"),
        c.get("r"),
        c.get("lora_alpha"),
        (c.get("lora_alpha") or 0) / (c.get("r") or 1),
        len(c.get("target_modules") or []),
    )
)
PY

reown "${UNO_LORA_DIR}" "${LOGDIR}"
log "Done. --uno-lora-path ${UNO_LORA_DIR}"
