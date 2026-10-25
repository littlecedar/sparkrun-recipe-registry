#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Chat-template staging for the MAIN-tree probe arm
# (`zz-ds4-1017-main-tree-sglang.yaml`), which serves the 1017 checkpoint
# on the stock `sglang-main-arm64:6563312` build instead of the knapcio
# overlay image. The 2026-10-17 refresh ships no `chat_template.jinja` by
# design (its card replaces the Jinja template with `encoding/encoding.py`),
# and a templateless checkpoint serves with SGLang's default template — wrong
# chat format for any accuracy cell. This mod copies the lane's patched
# template (same file the `dsv41-sglang-overlay` launcher stages for the
# knapcio stack) to a fixed path under the sparkrun-managed runtime cache;
# the recipe's `command:` passes it to `--chat-template`.
#
# The overlay launcher's symlink-farm approach is not used here: the stock
# tree's serve takes `--chat-template <file>` directly, so one real file
# staged into the runtime cache is the whole job.
#####################################################################

#####################################################################
# Metadata
#####################################################################
export MOD_NAME="dsv41-chat-template-stage"
export MOD_DESCRIPTION="Stage the ds4 1017 chat template for the main-tree probe arm"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Config
#####################################################################
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
# LITERAL path, matched by the recipe's {chat_template} default — mods run
# before the serve command, so nothing else can hand it a dynamic path.
# The leaf directory is sparkrun's (created + chowned by the launcher); these
# subpaths are ours to create, root-owned otherwise.
export TEMPLATE_DST_DIR="/cache/runtime/dsv41-maintree"
export TEMPLATE_DST="${TEMPLATE_DST_DIR}/chat_template.jinja"

#####################################################################
# Helpers (per mods/mod-template harness)
#####################################################################
reown() {
  # Chown a path to the owner of the .cache bind mount (mods run as root).
  local target="${1}"
  if [[ -e "${target}" ]]; then
    chown -R "$(stat -c '%u' /cache/runtime):$(stat -c '%g' /cache/runtime)" "${target}" || true
  fi
}

log() {
  echo "[$MOD_NAME] $*" | tee -a "${LOGDIR}/${MOD_NAME}.log"
}

log_var() {
  log "${1}=${!1}"
}

#####################################################################
# Rotate logs
#####################################################################
mkdir -p "${LOGDIR}"
if [[ -f "${LOGDIR}/${MOD_NAME}.log.gz" ]]; then
  rm -f "${LOGDIR}/${MOD_NAME}.log.gz"
fi
reown "${LOGDIR}"

log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log "${MOD_MAINTAINER}"

#####################################################################
# Main: stage the template
#####################################################################
log_var TEMPLATE_DST
if [[ ! -f "${MOD_DIR}/chat_template.jinja" ]]; then
  log "FATAL: ${MOD_DIR}/chat_template.jinja missing; refusing to boot a templateless endpoint"
  exit 2
fi
mkdir -p "${TEMPLATE_DST_DIR}"
install -m 0644 "${MOD_DIR}/chat_template.jinja" "${TEMPLATE_DST}"
reown "${TEMPLATE_DST_DIR}"
log "staged ${TEMPLATE_DST} ($(wc -c < "${TEMPLATE_DST}") bytes)"
log "Done."
