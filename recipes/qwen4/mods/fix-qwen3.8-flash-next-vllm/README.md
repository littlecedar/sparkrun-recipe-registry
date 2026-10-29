# fix-qwen3.8-flash-next-vllm

Patches vLLM's `qwen3_8_flash_next` PLE embedding layer so a FP8 PLE checkpoint can be
served with `VLLM_PLE_FP8_CHECKPOINT=1`.

## Contents

- [What it patches](#what-it-patches)
- [Why it lives here, not in mods/](#why-it-lives-here-not-in-mods)
- [Provenance](#provenance)
- [Repairs made on restore](#repairs-made-on-restore)
- [Guard](#guard)

## What it patches

`/usr/local/lib/python3.12/dist-packages/vllm/models/qwen3_8_flash_next/nvidia/ple_layer.py`,
which ships with the vLLM image (`ghcr.io/spark-arena/dgx-vllm-eugr-nightly-b12x`, pin
`@sha256:cf5a2a53…`). `apply-ple-patch.py` inserts three lines **above the first**
`if not isinstance(quant_config, Fp8Config):` in `get_embedding_method` (or wherever that check
first appears):

```python
import os
if os.environ.get("VLLM_PLE_FP8_CHECKPOINT") == "1":
    return Qwen3_8FlashNextPLEFp8EmbeddingMethod()
```

so the engine takes the FP8 PLE path instead of building a quantized method for a table that is
already FP8. The gate is an env var, so the patch is inert unless the recipe sets
`VLLM_PLE_FP8_CHECKPOINT: 1` — both arms that mount this mod do.

The insertion is anchored on a **string**, not a line number, because the three-line hunk in
upstream's `patches/ple-force-fp8.patch` stops applying as the image's line numbers move. If the
anchor is gone the script exits non-zero rather than writing a half-patched module.

## Why it lives here, not in `mods/`

Lane-local on purpose, and it exists **twice, one copy per lane**, because that is this repo's rule:
an arm resolves its `mods:` entry against *its own recipe directory*, and
`tests/test_mods_lane_locality.py` forbids a shipped recipe from reaching into `attic/`. The two
copies are byte-identical — `tests/test_qwen4_vllm_ple_mod.py` asserts it, so duplication cannot
drift:

- `attic/qwen4/mods/` for the archived W12 arm, which names `../mods/fix-qwen3.8-flash-next-vllm`
- `recipes/qwen4/mods/` for the shipped-tree probe, which names `mods/fix-qwen3.8-flash-next-vllm`

## Provenance

- Upstream: [`humanrouter/qwen38-flash-next-2x-spark`](https://github.com/humanrouter/qwen38-flash-next-2x-spark),
  `scripts/apply-ple-patch.py` (linked in the script header).
- House copy first landed under `mods/fix-qwen3.8-flash-next-vllm/`, was mounted by no recipe, and
  was deleted on 2026-10-11 in `d46d338` ("Archive the retired-lane mods and drop four unreferenced
  ones") on the recorded assumption that the only consumer, the archived W12 arm, would mount the
  **eugr registry's** mod of the same name.
- **Restored 2026-10-22 from `d46d338^`** because that assumption had rotted: the mirrored eugr
  registry (`spark-arena/eugr-recipes@0bdc9c9`, 26 mods) no longer carries
  `fix-qwen3.8-flash-next-vllm`, so the W12 arm failed at `Could not resolve mod` before launch.
  Files restored byte-identical, then three defects fixed (see below).

## Repairs made on restore

1. **`extract()` was missing** — `main()` called it and the name did not exist, so any run died with
   `NameError`; the restored body shelled out to `docker`, which does not exist inside the serve
   container the mod runs in (`FileNotFoundError: 'docker'`, W12 boot 4). Extraction is gone. The
   script now discovers the installed module with a glob over `sysconfig` `purelib`/`platlib` plus
   `dist-packages` and patches it **in place**, keeping one `.orig` backup.
2. **It patched nothing** — `main()` wrote the result to `<mods>/patched/ple_layer.py`, a copy the
   engine never imports. Nothing writes a copy any more: if no `ple_layer.py` is found, or the
   anchor is absent from a module that is not b12x-aware, the script exits non-zero.
3. **The idempotency guard looked for a string the patch never inserts** — `apply()` skipped work
   when `"PLE_FORCE_FP8" in src`, but the inserted lines contain `VLLM_PLE_FP8_CHECKPOINT`, so a
   second run stacked a duplicate block. The guard now keys on the env var the branch actually reads.

**The b12x builds are already fixed upstream.** In
`ghcr.io/spark-arena/dgx-vllm-eugr-nightly-b12x@sha256:cf5a2a53…` the PLE layer is
`vllm/models/qwen4_exp/nvidia/ple_layer.py` (not `vllm/models/qwen3_8_flash_next/nvidia/`), it has
no `if not isinstance(quant_config, Fp8Config):` guard at all, and it is b12x-aware
(`_use_b12x`, `quant_config=None if self._use_b12x else quant_config`). On that image this mod
logs `is b12x-aware with no upstream Fp8Config guard; nothing to patch` and exits 0 — the env var
is then inert, which is the honest outcome, not a silent half-apply.

Each consumer names the path that reaches *its* lane's copy: from `arms/` the attic one is one level
up (`../mods/…`), and the probe resolves its own lane's `mods/`. Both resolve from the recipe's own
directory, which is the only thing sparkrun checks.

## Guard

`tests/test_qwen4_vllm_ple_mod.py` asserts the anchor/insertion behaviour of `apply()` and that both
consumer arms reference the mod **unscoped** and that this directory exists — the two failure modes
that cost the 2026-10-22 attempt. It does not need the image; the image-side facts above (module
path, absent anchor, b12x marker) were read out of the pinned image by `docker run --rm`.
