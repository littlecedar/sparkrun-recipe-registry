#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Patch vLLM v0.32.0's `sliding_window: 0 -> None` conversion so it survives
# the transformers strict-dataclass setattr validation. The arm this ships
# for is poolside/Laguna-M.1-NVFP4, whose config.json declares
# `sliding_window: 0` ("sliding window disabled").
#
# THE BLOCKER (observed 2026-10-24, task sparkrun_dee59939d01336f0_0f4dd833099b,
# receipt ~/benchmarks/tp2-queue-20261024/LAGUNA-M1-REBOOT-FAILED.md): vLLM
# v0.32.0 `ModelConfig.__post_init__` (vllm/config/model.py:806-808) converts
# a checkpoint's `sliding_window: 0` to None *by assignment*:
#
#     if self.get_sliding_window() == 0:
#         self.disable_sliding_window = True
#         self.hf_text_config.sliding_window = None
#
# but `hf_text_config` is a transformers `PreTrainedConfig`, which since
# transformers 5 is a `@strict` huggingface_hub dataclass: `__setattr__` runs
# `type_validator` on every assignment, and `sliding_window` is typed plain
# `int`, so the deliberate None raises
# `StrictDataclassFieldValidationError: Field 'sliding_window' expected int,
# got NoneType` before the engine serves one request. The same assignment
# recurs at :901-904 on the `--disable-sliding-window` path, so that flag
# crashes the same way.
#
# THE FIX: route the two deliberate None assignments through
# `object.__setattr__`, which calls the base implementation directly and
# bypasses only the strict-validation override. The semantics are unchanged —
# None is exactly what vLLM means by "sliding window disabled" here, and
# `get_sliding_window()` (model.py:1614) already reads it back with
# `getattr(..., None)`. The conversion still happens before
# `get_and_verify_max_len`, so the max_model_len capping comment at :802-805
# still holds.
#
# FAIL-CLOSED: the mod aborts the launch (non-zero exit tears the launch
# down) unless the pinned file carries BOTH exact needles, so a re-pin that
# changes or fixes this code fails loudly instead of booting unpatched or
# double-patching.

MOD_NAME="fix-vllm-strict-sliding-window"
MOD_DESCRIPTION="Let vLLM v0.32.0 assign sliding_window=None on transformers strict configs"
LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/${MOD_NAME}.log"
exec >>"$LOG" 2>&1
echo "[$(date -u +%FT%TZ)] $MOD_NAME starting"

TARGET="/usr/local/lib/python3.12/dist-packages/vllm/config/model.py"
NEEDLE='self.hf_text_config.sliding_window = None'
REPLACEMENT='object.__setattr__(self.hf_text_config, "sliding_window", None)'

[ -f "$TARGET" ] || { echo "FATAL: $TARGET not found — wrong image?"; exit 1; }

COUNT=$(grep -cF -- "$NEEDLE" "$TARGET" || true)
if [ "$COUNT" -lt 1 ]; then
  echo "FATAL: needle not present in $TARGET — image re-pinned or upstream fixed; aborting (fail-closed)."
  exit 1
fi
if grep -qF -- "$REPLACEMENT" "$TARGET"; then
  echo "already patched, nothing to do"
  exit 0
fi

python3 - "$TARGET" <<'PYEOF'
import sys
path = sys.argv[1]
needle = 'self.hf_text_config.sliding_window = None'
replacement = 'object.__setattr__(self.hf_text_config, "sliding_window", None)'
with open(path) as f:
    text = f.read()
count = text.count(needle)
patched = text.replace(needle, replacement)
with open(path, "w") as f:
    f.write(patched)
print(f"patched {count} occurrence(s)")
PYEOF

# Verify: no plain assignment remains, both sites patched, file still parses.
if grep -qF -- "$NEEDLE" "$TARGET"; then
  echo "FATAL: plain needle remains after patch — aborting."
  exit 1
fi
python3 -c "import py_compile; py_compile.compile('$TARGET', doraise=True)" \
  || { echo "FATAL: patched file does not compile — aborting."; exit 1; }
echo "[$(date -u +%FT%TZ)] $MOD_NAME done"
