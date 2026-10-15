<!--
SPDX-FileCopyrightText: 2026 Travis Wichert

SPDX-License-Identifier: AGPL-3.0-or-later
-->

# fix-fastsafetensors-tp2-sglang

Patches sglang's `fastsafetensors` weight loader so a 1-GPU-per-node tensor
parallel launch (the GB10 pattern: TP=2 spanning two hosts, both with only
`cuda:0`) neither crashes nor strands GPU memory. Shared by the qwen3 and
cybersec lanes.

Two independent fixes, each anchored to an exact text block in
`sglang/srt/model_loader/weight_utils.py` and each applied only if its anchor
matches exactly once (`apply-fastsafetensors-tp2-patch.py`):

|Patch|Defect|Effect if unpatched|
|---|---|---|
|`device-selection`|`torch.device(f"cuda:{rank}")` treats the *global* rank as a local device index|`invalid device ordinal` on rank ≥ 1 (upstream sgl-project/sglang#29272)|
|`staging-buffer-release`|the `FilesBufferOnDevice` from `copy_files_to_device()` is never closed|staging buffer stays resident; on GB10 it comes out of the same pool as weights and KV (~26.9 GB at TP=2 on a 27B), which pushed `--mem-fraction-static 0.85` past "no GPU memory for the KV cache"|

## Anchor drift (why there are two candidate anchors)

2026-10-15: a boot died with
`[staging-buffer-release] no candidate anchor matched exactly once` against the
then-current `lmsysorg/sglang:dev-cu13`. Upstream had moved the block — `fb`
is now bound *inside* the `try`, and the stranded `finally: pass` the mod
keyed on was replaced by a single `finally: loader.close()` (which resets file
bookkeeping only; the leak is unchanged). Two shapes are now handled:

- **current** — `try` / `finally: loader.close()` at generator-body indent,
  `loader.add_filenames()` on the line above; the patch binds `fb = None`
  before the `try` so the `finally` can always read it, then syncs and closes
  the buffer before the loader.
- **legacy** — `fb` bound before the `try`, body trapped in `finally: pass`.

A third shape still fails closed: `run.sh` refuses to launch unless both
patches applied (or the tree already carries both markers). Half-fixed is
worse than unfixed — keeping the leak while losing the device fix reproduces
the ordinal crash, and the reverse the KV OOM. To proceed deliberately with
one fix (to A/B them, say), set
`SPARKRUN_ALLOW_PARTIAL_FASTSAFETENSORS_PATCH=1`.

The mod is idempotent (`mods` re-run against a fresh container each launch)
and never leaves an unparseable module behind: the patched source is compiled
before it replaces the file, and the original owner/mode are restored.

`tests/test_fix_fastsafetensors_tp2_mod.py` drives the script against both
shapes plus two negative controls (no anchor, partial apply); it fails on the
pre-2026-10-15 script.