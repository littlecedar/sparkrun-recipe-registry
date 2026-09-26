# instanttensor-hybrid-draft-loader

Patches vLLM's central `get_model()` so a **speculative draft** may load with
lazy safetensors while the **target** model stays on InstantTensor. Run it on
every rank (sparkrun applies mods per node).

| | |
|:--|:--|
| Source | [eugr/spark-vllm-docker](https://github.com/eugr/spark-vllm-docker) `mods/instanttensor-hybrid-draft-loader/` (fetched 2026-09-25) |
| License | Apache-2.0 (upstream mod). `patch_model_loader.py` vendored VERBATIM except its SPDX header; see the file header and `files/UPSTREAM-README.md`. |
| Verified against | image `littlecedar/dgx-spark-dsv41:exl3a` (vLLM `0.28.1rc1.dev388+g8a728663c`), 2026-09-25, by running the vendored patcher against the image's real `model_loader/__init__.py` |

## Why it exists

With `--load-format instanttensor`, when a speculative draft shares the target
checkpoint (embedded MTP, or a same-path/same-revision drafter), vLLM runs a
**second** InstantTensor GPU-streaming pass over the whole checkpoint just to
keep a small subset of draft tensors. This mod resolves the loader per model at
`get_model()` and switches only the draft to lazy safetensors, leaving rejected
draft tensors as CPU memory-mapped views rather than staging and cloning them on
the GPU.

## It is a no-op unless both hold (so it is safe to list everywhere)

1. the effective `load_format` is `instanttensor`; **and**
2. a real speculative draft exists whose effective loader would also be
   InstantTensor.

In `auto` (default) mode a **same model path and revision** draft is the only
case that flips. The DS4.1 DSpark drafter is a **separate** model path, so on our
recipes the mod does nothing and the boot is byte-identical to InstantTensor
alone. It is listed for parity, so a future same-checkpoint draft benefits
without a recipe change.

## Mechanics (fail-closed)

1. `patch_model_loader.py` is **md5-verified** against `files/MD5SUMS.txt`.
2. The patcher runs its own `--check` **before** writing: if the image's
   `get_model()` does not match the vendored anchor exactly, it refuses and the
   mod exits non-zero. A mismatched vLLM never receives a silent patch.
3. The target file is backed up once to `<target>.sparkrun-orig`.
4. Idempotence is by the marker text (`# spark-vllm mod: … v1`), not timestamps,
   so a re-run is a no-op and `--check` then reports `already patched`.
5. Stale `__pycache__` next to the patched source is removed.

## Knobs

`INSTANTTENSOR_DRAFT_LOADER` = `auto` (default) | `safetensors` | `instanttensor`.
**Spray it via the recipe `env:` block**, not the mod: the *patched vLLM* reads
it at runtime, during `get_model()`. `VLLM_SITE_PACKAGES` overrides the vLLM
root for a different base image. `MOD_TIMEOUT`, `MOD_LOGDIR` come from the
shared harness.

## Caveat

This vendors third-party code. The checksum proves the patcher is the file we
fetched; it does not prove the patch is correct for a future vLLM. The
`--check`-before-write contract is what makes that safe: a changed `get_model()`
fails the mod loudly instead of mis-patching the loader.
