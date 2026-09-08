# Review: qwen3.8-flash-next-nvfp4-specification.md

Objective was to review this spec for consistency. Findings grouped by severity.
Evidence is cross-checked against sibling recipes in
`experimental-recipes/littlecedar/*.yaml` (esp. the MTP sibling
`littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm.yaml` and the b12x siblings
`ornith-1.5-35b-a3b-nvfp4-vllm[-b12x].yaml`).

## CRITICAL / will break the launch

1. `--load-format fastsafetensors` (line 22 of spec) contradicts the v2
   `defaults.load_format: instanttensor` used by every sibling. `load_format`
   controls loading from the `instanttensor` draft loader; passing
   `--load-format fastsafetensors` on the CLI overrides the default and defeats
   the draft-loader flow. This is exactly the contradiction the spec itself
   warns about ("no hardcoding `--load-format`"). Use `--load-format {load_format}`
   instead. The recipe should load via the draft loader, not raw safetensors.

2. Missing `--spec-model-path` / draft model wiring. Line 24 says the MTP draft
   model is `Qwen/Qwen3.8-Flash-Next-FP8` and lists
   `--spec-model-path Qwen/Qwen3.8-Flash-Next-FP8` as one option, but line 23's
   required JSON form uses
   `{"method":"mtp","num_speculative_tokens":...}` WITHOUT any draft-model
   pointer. For pure MTP the draft *is* the model's own MTP experts, so there is
   no separate model to point `--spec-model-path` at. The two options as written
   are contradictory and neither alone supplies the draft weights. The sibling
   397B recipe needs no `--spec-model-path` at all (pure MTP). Confirm whether
   a distinct draft path is actually needed here.

3. Spec-env `model_draft_dtype: bf16` (line 16) naming is wrong. The sibling
   MTP recipe names its draft dtype `model_mtp_dtype: bfp16` (note `bfp16`).
   Either the field name is wrong (`model_draft_dtype` vs `model_mtp_dtype`) or
   the value should be `bfp16`. Do not author this from memory — confirm the
   exact field name and value in the v2 schema/model card.

## HIGH

4. Env var `JOBS` (line 18) is the wrong key. All sibling recipes set
   `MAX_JOBS: 2` (a real CMake/pip parallelism var). `JOBS` is nonstandard and
   will be silently ignored. Use `MAX_JOBS`.

5. `VLLM_USE_FLASHINFER_MOE_FP4` (line 18) is set in siblings, but it's
   specifically an FP4 MoE knob; for NVFP4 the sibling b12x recipe sets it to `1`.
   Verify its value/type is correct for NVFP4 (4B active NVFP4 experts). Minor
   but flag to confirm rather than assume `1`.

6. Missing b12x-only env that siblings require: `VLLM_TARGET_DEVICE: cuda` and
   `CUTE_DSL_ARCH: sm_121a` are present in b12x siblings but listed only as a
   few of several knobs here. On Blackwell B10/10 you typically need
   `VLLM_TARGET_DEVICE: cuda`. Confirm all are present.

## MEDIUM / nit

7. `container` image choice line 14: spec says "prefer the
   `.../dgx-vllm-eugr-nightly-b12x:latest` image" but line 14 names a
   `dgx-vllm-eugr-nightly-b12x:latest` tag — double-check the exact image path
   against siblings (`ghcr.io/spark-arena/dgx-vllm-eugr-nightly:latest` and
   `...-b12x:latest`). Pick one consistent image; don't leave the two forms.

8. `reasoning-parser qwen3` (line 22) is used by siblings, fine. But the spec
   also lists `--reasoning-parser qwen3` in line 22's flag list while a sibling
   uses `--tool-call-parser qwen3_xml`. Confirm the parser name is right for
   this checkpoint's tool-call format (minor).

9. `kv_dtype: fp8_e4m3` in metadata (line 16) vs sibling `kv_cache_dtype: fp8_e4m3`
   in defaults. These are two different names for related things (metadata field
   vs defaults key). Fine as distinct fields, but confirm the metadata field is
   actually `kv_dtype` in v2 (sibling used neither exactly). Noting to verify.

## CONSISTENCY WITH ITSELF / STRUCTURE

10. The checklist is self-contradictory on `--load-format` (item 3) even though
    the Notes section correctly states the recipe should not hardcode load
    format. Worth removing the hard-coded flag rather than trusting the Notes.

11. Line 24 lists `--spec-model-path` as an "either/or" but the required JSON
    block on line 23 doesn't embed it — making the "or" not actually reachable.
    Collapse to a single, resolved form.

## What I did NOT have enough to confirm (needs model card / hardware)

- The NVFP4 model card's exact vLLM minimum commit and the required PR number
  (#55513 is asserted in line 14; can't verify from this repo).
- Exact required env var list for NVFP4 vs FP8 (some of these are FP8-derived).
- Whether `Qwen/Qwen3.8-Flash-Next-FP8` exists and is byte-compatible with the
  MTP experts — not present in this repo.
