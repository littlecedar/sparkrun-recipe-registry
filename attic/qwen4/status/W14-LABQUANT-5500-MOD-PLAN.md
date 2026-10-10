# Labquant step-5500 upgrade — 7-mod chain re-verification plan

**Date:** 2026-10-10 · **Status:** analysis only; no mod was changed and no boot was spent.
**Prepared from live HF Hub headers (not inferred).** This is the deliverable that gates the
labquant accuracy-upgrade candidate identified in the 2026-10-10 scan.

## Target revision — correction

The brief's `6909a5be` (2026-10-02) is superseded: **current main is `6c01ac37` (2026-10-06)**,
which restored `text_config.ple_embedding_dtype = "nvfp4"`. Both revisions share an **identical
43-file layout**, so the verdicts below apply to `6c01ac37`.

| | pin `7c4f1bc1` (shipped) | new layout |
|---|---|---|
| safetensors | 36 files, 105.84 GB | 41 × `model-…-of-00041` + 2 × `hybrid-main-*` = 43 files, 106.33 GB |
| placeholders | — | `model-00023/24/25-of-00041` are exactly 40 bytes = **valid empty safetensors headers** (index-absent; `header_of()` returns `{}` and does NOT crash) |
| PLE files | 16 dedicated files, **16 tensors each** (all `.ngram_embedding.*`) | same 16 files, byte-identical shapes, but **20 tensors each**: + `ple.norm_{conv,key,query}.weight` F32 [10240] ×3 + `ngram_embedding.weight_scale_2` F32 [1] |
| GDN attention | — | all `in_proj_a/b` (72+72) F8_E4M3 + U8 scale, in `hybrid-main-00002` (2.787 GB == the pin's `model-00035-of-00036`) |
| vision tower | quantised (the thing `skip-labquant-vision-tower` works around) | **BF16 only**, already inside `quantization_config.ignore` (`model.visual.*`) |
| MTP | — | `hybrid-main-00001` holds MTP expert `weight_scale_2` F32 scalars (4,608 index entries) — the step-5500 NVFP4-MTP re-quant |

## Per-mod verdicts

| # | mod | verdict | the load-bearing fact |
|---|---|---|---|
| 1 | `@eugr/mods/drop-caches` | **SURVIVES** | touches no checkpoint path/shape/count |
| 2 | `fix-labquant-modelopt-mixed-flat-schema` | **SURVIVES** (degrades to a no-op passthrough tree-builder) | new config has BOTH `quantized_layers` AND `kv_cache_quant_algo` → inline path OK → `STATE='OK'` passthrough; still builds the `/cache/runtime/labq-patched` tree the recipe serves. The `KeyError:'quantization'` bug it fixed is pre-fixed upstream |
| 3 | `unpack-labquant-ple-nvfp4-to-fp8` | **BREAKS — fails closed, no corruption** | assumes the 16 PLE files are PLE-DEDICATED (`run.sh:184 EXPECTED_PLE_ONLY_FILES=16`, `:216-220` classifies any file with a non-matching tensor as 'mixed' and skips it). New PLE files hold 20 tensors → all 16 classified mixed → `pairs=0` → die at `:242-243` ("expected 128 packed PLE pairs, found 0"). **Tensor shapes themselves are UNCHANGED** (U8 [2500012,80] + F8_E4M3 [2500012,10] byte-identical to the pin) — a file-inventory break, not a tensor-contract break |
| 4 | `diag-qwen4-unplaced-scales` | **SURVIVES** | image-pinned diagnostic; anchor matched exactly 1; checkpoint-agnostic |
| 5 | `fix-labquant-mxfp8-weight-scale-name` | **SURVIVES** | conditional rename fires only when `<X>.weight_scale` is absent AND `weight_scale_inv` present; premise intact (144 shared-expert scale entries); degrades to a logged no-op on any naming change |
| 6 | `demote-labquant-narrow-mxfp8-to-bf16` | **SURVIVES** | candidate files derived from the index regex `.in_proj_[ab].weight$` (`run.sh:276-278`), so the shard rename does not matter; **EXPECTED_NARROW=72 contract holds** (72+72 all F8_E4M3 + U8 scale); index surgery works on the new index |
| 7 | `skip-labquant-vision-tower` | **SURVIVES mechanically, but OBSOLETE — re-verify and likely DROP** | the new vision tower is BF16 and already in `quantization_config.ignore`, so the load failure it works around no longer exists; keeping it now only removes vision capability for zero benefit |

## The re-verification plan (before the chain can ship against `6c01ac37`)

1. **Fix mod 3**: change the 'mixed → skip' policy to *preserve-and-rewrite* — stream each PLE
   file through, keeping the 3 `ple.norm_*` F32 tensors and the `weight_scale_2` scalar alongside
   the converted PLE pairs, instead of classifying the file as mixed. Discovery via the index
   still finds the 16 files (the index listing the 128 PLE block scales is harmless). Keep
   fail-closed: the `EXPECTED_NARROW`-style numeric contracts and the die-on-mismatch paths stay.
2. **Drop mod 7** from the chain (obsolete; keeping it removes vision for zero benefit). Confirm
   no guard pins the 7-mod list (checked 2026-10-10: `tests/` pins ds4/ifm chains, not labquant's)
   and update the recipe banner comment that names the chain.
3. **Re-pin** `model_revision:` to `6c01ac37` (the pin key, not `revision:` — the known live
   defect class).
4. **Boot + verify**: one TP=2 boot on the pair; check the serve log for the mod chain's
   assertions passing; run the W3 38-task battery (expect ≥ 37/38; the upgrade's claim is
   accuracy on the routed experts, throughput unchanged — verify a decode cell against the
   shipped labquant numbers).
5. **Guard discipline**: the negative-control convention applies to any mod-3 change — prove the
   new preserve-and-rewrite path refuses on a genuinely corrupt PLE file, not just on the new
   layout.
