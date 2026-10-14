#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Purpose: make the IFM/K2-Horizon-7B-Uno LoRA adapter available at a fixed
#          in-container path for --uno-lora-path, since sparkrun's artifact
#          distribution only fetches a recipe's single `model:` field.
# See: recipes/ifm/k2-horizon-7b-fp8-uno-sglang.yaml and
#      recipes/ifm/K2-7B-MODEL-OPTIMIZATION-WORK.md section 6.
set -euo pipefail

#####################################################################
# README
#####################################################################
# WHY THIS MOD EXISTS
#
# sparkrun distributes exactly one artifact per recipe: the `model:` field. SGLang's
# native UNO speculative algorithm needs a SECOND one -- a PEFT conditional-LoRA
# adapter (IFM/K2-Horizon-7B-Uno) passed via --uno-lora-path. There is no recipe
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
# The adapter is 1,396,763,616 B. Re-downloading it on every launch of a probe
# recipe is wasteful and adds a network dependency to something meant to be
# reproducible, so an existing file is verified by size then by SHA-256 and kept
# if both match. A truncated copy from an interrupted download fails the size
# check and is re-fetched.
#
# EXPECTED VALUES (VERIFIED from the HF API on 2026-09-20; re-derive with:
#   curl -s https://huggingface.co/api/models/IFM/K2-Horizon-7B-Uno?blobs=true)
#   revision 669f041aab04fad836e757ede9a028058b064996
#   adapter_model.safetensors  size 1396763616
#                            sha256 cfef2bbff2802f2fb77d25d279af49b11746fc0a4de06f306f745c7bbe4e00ad
# If the pin moves, update UNO_LORA_SHA256 too. Do not relax the check to "size
# only" -- the point is to know which weights a result came from.
#####################################################################

#####################################################################
# Metadata
#####################################################################
MOD_NAME="provide-uno-lora-k2-horizon-7b"
MOD_DESCRIPTION="Fetch and verify the IFM/K2-Horizon-7B-Uno adapter for --uno-lora-path"
MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export UNO_LORA_REPO="${UNO_LORA_REPO:-IFM/K2-Horizon-7B-Uno}"
export UNO_LORA_REVISION="${UNO_LORA_REVISION:-669f041aab04fad836e757ede9a028058b064996}"
export UNO_LORA_DIR="${UNO_LORA_DIR:-/cache/runtime/uno-lora/K2-Horizon-7B-Uno}"
export UNO_LORA_SIZE="${UNO_LORA_SIZE:-1396763616}"
export UNO_LORA_SHA256="${UNO_LORA_SHA256:-cfef2bbff2802f2fb77d25d279af49b11746fc0a4de06f306f745c7bbe4e00ad}"
export TIMEOUT="${MOD_TIMEOUT:-900}"

CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
mkdir -p "${LOGDIR}" "${UNO_LORA_DIR%/*}"

log() { printf '%s [%s] %s\n' "$(date -Ins)" "${MOD_NAME}" "${*}" | tee -a "${LOGDIR}/${MOD_NAME}.log"; }
reown() { local u g; u="$(stat -c '%u' "${CACHEDIR}" 2>/dev/null || echo 0)"; g="$(stat -c '%g' "${CACHEDIR}" 2>/dev/null || echo 0)"; chown -R "${u}:${g}" "${@}" 2>/dev/null || true; }

log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log "repo=${UNO_LORA_REPO} revision=${UNO_LORA_REVISION} dir=${UNO_LORA_DIR}"

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
  #
  # Uses the huggingface_hub Python API rather than the CLI because the CLI
  # entrypoint name has moved between releases (`huggingface-cli` -> `hf`) and a
  # probe recipe should not fail on that. huggingface_hub is a hard dependency of
  # sglang, so it is present in the pinned image.
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
    # Only the two artifacts the engine reads. Skips the results figure and the
    # prose, which together are most of the repo's non-LFS bytes.
    allow_patterns=["adapter_config.json", "adapter_model.safetensors"],
)
print("snapshot_download ->", p)
PY
  ) 2>&1 | tee -a "${LOGDIR}/${MOD_NAME}.log"; then
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
#
# lora_alpha 8192 with r 128 (scaling 64) looks like a typo and is not one;
# printing it here means a later reader can tell which adapter a result came
# from without re-fetching it.
#####################################################################
python3 - <<'PY' || true
import json, pathlib
p = pathlib.Path(__import__("os").environ["UNO_LORA_DIR"]) / "adapter_config.json"
try:
    c = json.loads(p.read_text())
    print("adapter_config: base=%s peft=%s r=%s alpha=%s dropout=%s targets=%s" % (
        c.get("base_model_name_or_path"), c.get("peft_type"), c.get("r"),
        c.get("lora_alpha"), c.get("lora_dropout"),
        ",".join(c.get("target_modules") or [])))
except Exception as exc:
    print("adapter_config: unreadable (%s)" % exc)
PY

reown "${UNO_LORA_DIR%/*}" "${LOGDIR}"
log "Done. --uno-lora-path ${UNO_LORA_DIR}"
