# fix-qwen3.8-flash-next-vllm

Patches vLLM's `qwen3_8_flash_next` PLE embedding layer so a FP8 PLE checkpoint can be
served with `VLLM_PLE_FP8_CHECKPOINT=1`.

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

Lane-local on purpose. A `@registry/mods/<name>` reference resolves only from the registry clone's
**top-level** `mods/`, so this mod cannot be reached from `mods/` either — an arm in
`recipes/qwen4/` resolves an **unscoped** `mods/<name>` against its own lane's `mods/` directory.
That is why both consumers name it `mods/fix-qwen3.8-flash-next-vllm`:

- `attic/qwen4/arms/qwen3.8-flash-next-nvfp4-vllm.yaml` (W12)
- `recipes/qwen4/zz-qwen38-next-vllm-tp2-pinned.yaml`

## Provenance

- Upstream: [`humanrouter/qwen38-flash-next-2x-spark`](https://github.com/humanrouter/qwen38-flash-next-2x-spark),
  `scripts/apply-ple-patch.py` (linked in the script header).
- House copy first landed under `mods/fix-qwen3.8-flash-next-vllm/`, was mounted by no recipe, and
  was deleted on 2026-10-11 in `9d12b93` ("Archive the retired-lane mods and drop four unreferenced
  ones") on the recorded assumption that the only consumer, the archived W12 arm, would mount the
  **eugr registry's** mod of the same name.
- **Restored 2026-10-22 from `9d12b93^`** because that assumption had rotted: the mirrored eugr
  registry (`spark-arena/eugr-recipes@0bdc9c9`, 26 mods) no longer carries
  `fix-qwen3.8-flash-next-vllm`, so the W12 arm failed at `Could not resolve mod` before launch.
  Files restored byte-identical, then three defects fixed (see below).

## Repairs made on restore

1. **`extract()` was missing** — `main()` called it and the name did not exist, so any run died with
   `NameError`. It now creates a container with `--entrypoint ""`, `docker cp`s the module out into
   a temp dir and removes the container.
2. **It patched nothing** — `main()` wrote the result to `<mods>/patched/ple_layer.py`, a copy the
   engine never imports. It now patches `ple_layer.py` **in place** inside the serve container
   (keeping one `.orig` backup) and only falls back to the file-output mode under `--out` or when
   the module is not present locally.
3. **The idempotency guard looked for a string the patch never inserts** — `apply()` skipped work
   when `"PLE_FORCE_FP8" in src`, but the inserted lines contain `VLLM_PLE_FP8_CHECKPOINT`, so a
   second run stacked a duplicate block. The guard now keys on the env var the branch actually reads.

The two consumers sit at different depths, so their references differ and both are correct:
`recipes/qwen4/zz-qwen38-next-vllm-tp2-pinned.yaml` names `mods/fix-qwen3.8-flash-next-vllm`, while
the attic arm names `../../../recipes/qwen4/mods/fix-qwen3.8-flash-next-vllm`. Each resolves from the
recipe's own directory, which is the only thing sparkrun checks.

## Guard

`tests/test_qwen4_vllm_ple_mod.py` asserts the anchor/insertion behaviour of `apply()` and that both
consumer arms reference the mod **unscoped** and that this directory exists — the two failure modes
that cost the 2026-10-22 attempt. It does not need the image; the engine-side anchor is proven by the
`--out` run recorded in the W12 receipt.
