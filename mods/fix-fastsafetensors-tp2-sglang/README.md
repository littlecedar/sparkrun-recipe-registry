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

## Measured effect (it is not a TP=2-only fix)

2026-10-15, qwen3.8-27B-NVFP4 DFlash2, one node, image `lmsysorg/sglang:dev-cu13`
(`sha256:c802d7b6…`), same recipe, mod log shows both patches staged and no escape
hatch. The device fix is inert at TP=1; the buffer release is not:

|quantity|before|after|
|---|---|---|
|target load, mem usage|41.90 GB|20.59 GB|
|draft load, mem usage|7.41 GB|3.78 GB|
|mamba cache size / clamp|161-163, `capped to 40`|252, no clamp|
|granted concurrency|40|48 (the recipe's literal, granted in full)|
|fp8 KV pool|213,311-221,836 tokens|497,878 tokens|

The pool doubling is why the 262,144-token needle probe passed afterwards (3/3) where
both leaky boots truncated the request at ~209k counted tokens. Read the grants from
the serve log of the boot you care about; the pre-fix numbers above belong to the
unfixed loader.

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