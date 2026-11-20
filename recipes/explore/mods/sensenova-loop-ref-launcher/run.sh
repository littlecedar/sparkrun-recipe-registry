#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
# Fail-closed gate for the SenseNova-Loop reference arm. This mod modifies no
# image file: it proves the reference server is present and that the pinned image
# carries the transformers backbone the checkpoint's remote code subclasses, then
# hands the serve to the recipe's command.
set -euo pipefail

MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "$MOD_DIR/serve.py" ] || { echo "[sensenova-loop-ref] serve.py missing" >&2; exit 2; }

python3 -c "import transformers, fastapi, uvicorn, torch" 2>/dev/null || {
  echo "[sensenova-loop-ref] the pinned image must carry transformers+fastapi+uvicorn+torch" >&2
  exit 2
}

# `modeling_sensenova_loop.py` subclasses transformers' `qwen3_5` text tower and calls both
# mask builders out of that module's namespace; an image whose transformers predates the
# module cannot load the checkpoint at all, so the gate names the exact symbols it needs.
python3 -c "
from transformers.models.qwen3_5 import modeling_qwen3_5 as m
m.create_causal_mask
m.create_recurrent_attention_mask
m.Qwen3_5ForConditionalGeneration
" 2>/dev/null || {
  echo "[sensenova-loop-ref] pinned transformers lacks the qwen3_5 backbone the remote code subclasses" >&2
  exit 2
}

echo "[sensenova-loop-ref] reference route: transformers trust_remote_code; no pinned engine registers SenseNovaLoopForConditionalGeneration"
echo "[sensenova-loop-ref] gate ok: $MOD_DIR/serve.py"
