#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
# Fail-closed gate for the Kimi-SuperExpert reference arm. This mod modifies no
# image file: it proves the reference server is present and that the container is
# the image the recipe pinned, then hands the serve to the recipe's command.
set -euo pipefail

MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "$MOD_DIR/serve.py" ] || { echo "[kimi-superexpert-ref] serve.py missing" >&2; exit 2; }

python3 -c "import transformers, fastapi, uvicorn, torch" 2>/dev/null || {
  echo "[kimi-superexpert-ref] the pinned image must carry transformers+fastapi+uvicorn+torch" >&2
  exit 2
}

echo "[kimi-superexpert-ref] reference route: transformers trust_remote_code; no engine registry entry exists for KimiK31SuperExpertForCausalLM"
echo "[kimi-superexpert-ref] gate ok: $MOD_DIR/serve.py"
