#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Move ERNIE 5.5 Flash's six MLA layers from FlashMLA's SM100-only sparse
# decode onto FlashInfer's SM120/121 sparse kernel, keeping the
# `top-k + last window` page set, its per-row length and the learnable sink.
#
# The mod is fail-closed: the patch script aborts the launch and writes nothing
# if any of the five anchors does not match exactly once, and the verify script
# fails the launch if the patched behaviour or the GPU-less kernel envelope is
# not what the boot assumes. A refused launch here is a diagnostic, not a
# recipe failure: read the log and the mod's README before changing anything.
#
# Boot does not accept this port; only the quality cell does. A wrong-logits
# port boots, captures CUDA graphs, and serves. See the mod README's
# acceptance ladder.

MOD_NAME="ernie55-flashinfer-sparse-sglang"
MOD_DESCRIPTION="ERNIE 5.5 Flash MLA layers onto FlashInfer's SM121 sparse-MLA kernel"
MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
PYTHON="${PYTHON:-python3}"

mkdir -p "$LOGDIR"
if [[ -d /cache/runtime ]]; then
  chown -R "$(stat -c '%u:%g' /cache/runtime)" "$LOGDIR" 2>/dev/null || true
fi
LOG="$LOGDIR/${MOD_NAME}.log"
exec >>"$LOG" 2>&1

echo "[$(date -u +%FT%TZ)] ${MOD_NAME} starting: ${MOD_DESCRIPTION}"
command -v "$PYTHON" >/dev/null 2>&1 || {
  echo "FATAL: ${PYTHON} not on PATH in this image; cannot patch sglang."
  exit 1
}

"$PYTHON" -B "${MOD_DIR}/apply-ernie55-flashinfer-sparse-patch.py" || {
  echo "FATAL: patch refused; see the error above. Refusing to launch unpatched."
  exit 1
}
"$PYTHON" -B "${MOD_DIR}/verify-ernie55-flashinfer-sparse.py" || {
  echo "FATAL: rung (i) failed after patching. Refusing to launch."
  exit 1
}
echo "[$(date -u +%FT%TZ)] ${MOD_NAME} done"
