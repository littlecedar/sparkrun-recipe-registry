#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# The drowzeys "keys-Qwen3.8-27B-NVFP4-DFlash2-Ablit-Cybersecurity-Unlock-1M-Context-YARN"
# overlay ships NO weights: it is config + an uncensored (cybersecurity-unlock) chat
# template + YaRN rope overlays on top of a stock body pack. This mod fetches the one
# piece the engine cannot get from the body checkpoint -- the chat template -- plus the
# two rope overlays the 1M route needs, into the sparkrun runtime cache, so the recipe
# can point `--chat-template` at it. The stock snapshot is never modified.
#
# Source repo (gated: auto; the node's HF_TOKEN must have accepted its release):
#   drowzeys/keys-Qwen3.8-27B-NVFP4-DFlash2-Ablit-Cybersecurity-Unlock-1M-Context-YARN-Single-DGXSpark
#
# Fail closed: a missing template leaves the arm serving the body's stock template, which
# is NOT the arm -- so a fetch failure is fatal, not a warning.
#####################################################################

#####################################################################
# Metadata
#####################################################################
export MOD_NAME="provide-uncensored-chat-template"
export MOD_DESCRIPTION="Fetch the drowzeys uncensored chat template + YaRN rope overlays into the runtime cache"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export TIMEOUT="${MOD_TIMEOUT:-180}"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export UV_LINK_MODE=copy
export USER_UID="$(stat -c '%u' /cache/runtime)"
export USER_NAME="$(stat -c '%U' /cache/runtime)"
export USER_GID="$(stat -c '%g' /cache/runtime)"
export USER_GROUP="$(stat -c '%G' /cache/runtime)"

# Overlay repo revision, pinned. Overridable for a re-pin A/B.
OVERLAY_REPO="${OVERLAY_REPO:-drowzeys/keys-Qwen3.8-27B-NVFP4-DFlash2-Ablit-Cybersecurity-Unlock-1M-Context-YARN-Single-DGXSpark}"
export OVERLAY_REVISION="${OVERLAY_REVISION:-a9cf9de0e143513bb16183d65d9f4ca246906321}"
export OUTDIR="${OUTDIR:-${CACHEDIR}/uncensored-template}"
export TOKENFILE="${TOKENFILE:-/cache/huggingface/token}"

#####################################################################
# Helpers
#####################################################################
reown() {
  local path="$1"
  chown -R "${USER_UID}:${USER_GID}" "${path}" 2>/dev/null || true
}

log() {
  if [[ $# -gt 0 ]]; then
    printf '%s\n' "$*"
  else
    cat
  fi
}

log_var() {
  local name="$1"
  printf '  %s=%s\n' "${name}" "${!name-}"
}

log_cmd() {
  printf '  $ %s\n' "$*"
  "$@"
}

die() {
  log "FATAL: $*"
  exit 1
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
  gzip -c "${LOGDIR}/${MOD_NAME}.log" > "${LOGDIR}/${MOD_NAME}.log.gz"
  rm -f "${LOGDIR}/${MOD_NAME}.log"
fi
exec > >(tee -a "${LOGDIR}/${MOD_NAME}.log") 2>&1
reown "${LOGDIR}"

#####################################################################
# Main
#####################################################################
log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log "${MOD_MAINTAINER}"

mkdir -p "${OUTDIR}"
reown "${OUTDIR}"

TEMPLATE="${OUTDIR}/chat_template.jinja"
if [[ -s "${TEMPLATE}" ]]; then
  log "template already present (${TEMPLATE}) -- idempotent no-op"
else
  [[ -s "${TOKENFILE}" ]] || die "no HF token at ${TOKENFILE}; the overlay repo is gated"
  TOKEN="$(cat "${TOKENFILE}")"
  python3 - "$OVERLAY_REPO" "$OVERLAY_REVISION" "$OUTDIR" "$TOKEN" <<'PY'
import os, shutil, sys, urllib.request
repo, rev, outdir, token = sys.argv[1:5]
base = f"https://huggingface.co/{repo}/resolve/{rev}"
want = [
    "chat_template_b5_uncensored.jinja",
    "yarn_hf_overrides.json",
    "dflash2_config_yarn_1m.json",
]
for name in want:
    req = urllib.request.Request(f"{base}/{name}", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    if not data:
        raise SystemExit(f"empty body for {name}")
    tmp = os.path.join(outdir, name + ".tmp")
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, os.path.join(outdir, name))
    print(f"  fetched {name} ({len(data)} bytes)")
# The recipe serves this fixed name; keep it a real file, not a symlink into the cache.
shutil.copyfile(os.path.join(outdir, "chat_template_b5_uncensored.jinja"),
                os.path.join(outdir, "chat_template.jinja"))
PY
fi

[[ -s "${TEMPLATE}" ]] || die "template not written"
reown "${OUTDIR}"
log "template: $(wc -c < "${TEMPLATE}") bytes at ${TEMPLATE}"
log "Done."
