---
name: unpack-labquant-ple-nvfp4-to-fp8
description: >
  Rewrite the local-inference-lab Qwen3.8-Flash-Next PLE n-gram table from packed NVFP4
  into plain fp8 e4m3, so SGLang's existing fp8 PLE loader can accept the checkpoint.
---

# Why this mod exists

`local-inference-lab/Qwen3.8-Flash-Next-NVFP4` stores the PLE n-gram embedding table in
packed NVFP4. SGLang's Qwen4-Exp loader has an fp8 PLE path but **no packed-NVFP4
unpack**, so the server dies during weight load:

```
qwen4_exp.py copy_ple_rows_to_tp_embedding
  emb.weight.data[local_start : local_start + n_rows].copy_(loaded_weight[...])
RuntimeError: The size of tensor a (160) must match the size of tensor b (80)
              at non-singleton dimension 1
```

The width mismatch is not a model difference — it is packed vs unpacked storage of the
same 160-wide table. Per shard:

| | tensor | dtype | shape | bytes |
|---|---|---|---|---|
| labquant | `ngram_embedding.shard_N.weight` | `U8` | `[2500012, 80]` | 200 MB |
| labquant | `…shard_N.weight_scale` | `F8_E4M3` | `[2500012, 10]` | 25 MB |
| RadixArk | `ngram_embedding.shard_N.weight` | `F8_E4M3` | `[2500012, 160]` | 400 MB |

## The packing contract (VERIFIED empirically, not assumed)

Established by comparing labquant's dequantised table against RadixArk's **independent**
fp8 encoding of the same rows, searching the joint space of nibble order x scale layout x
sign-bit convention. The decisive statistic is **element-wise normalised MAE**:

| hypothesis | normed MAE | float32 cosine |
|---|---|---|
| **low nibble = `2i`, sign bit 3, row-major scales** | **0.086** | 0.995 |
| high nibble = `2i` (nibbles transposed) | **1.000** | 0.000 |
| sign in bit 0 instead of bit 3 | 1.000 | 0.057 |

So:

- **low nibble = element `2i`, high nibble = element `2i+1`** (transposing these drives MAE
  to 1.000, i.e. the prediction becomes uninformative — unambiguous)
- **E2M1 codebook**, sign in bit 3: `[0, .5, 1, 1.5, 2, 3, 4, 6]` for nibbles 0-7, negated
  for 8-15 (the sign-in-bit-0 variant scores 1.000 on MAE)
- **scales are row-major**, one e4m3 value per 16 elements along the last dim
- **the stored scale is `block_absmax / 6`**, i.e. the standard NVFP4 amax/6 convention:
  `value = (codebook / 6) * scale`. Confirmed as an *identity*, not a fit —
  `block_absmax / stored_scale == 6.0` exactly, min = max = 6.0, in 100.000% of sampled
  blocks.

An earlier revision of this file led with cosine (0.995 vs 0.057) instead of MAE. Wrong
statistic to lead with: float32 reductions are imprecise on wide-dynamic-range data, and
**CPU** float32 `Tensor.norm()` measured **−2.9%** off at 96M elements where CUDA was
accurate to 4.5e-8, so a float32 cosine built from CPU norms can exceed 1 — it did here,
reporting **1.0327** where float64 gives 0.99524. The conclusion never depended on those
decimals (the candidates differ by orders of magnitude in MAE), but lead with the statistic
that cannot produce an impossible value. If you re-derive this: compute correlations in
float64 or use MAE/median, and validate any metric on data of the real scale (absmean ~30,
absmax 256 here) — a sanity check on `randn` of order 1 passes while the real case is
several percent wrong.

### `weight_scale_2` exists and must NOT be applied

There is one extra PLE tensor: `…ngram_embedding.weight_scale_2`, `F32 [1]`, value
**3.324236240587197e-05**. In ModelOpt's two-level NVFP4 scheme that is the per-tensor
global scale, and the usual dequant is `value = codebook * block_scale * global_scale`.
**Applying it here is wrong.** Measured element-wise against RadixArk's independent fp8
encoding of the same rows:

| dequantisation hypothesis | normed MAE vs reference |
|---|---|
| `codebook * scale / 6` | **0.08586** |
| `codebook * scale * g` | 0.99980 |
| `codebook * scale * g / 6` | 29843.3 |
| `codebook * scale / g` | 179064.9 |

The `g` variants are not close calls, they are degenerate: with `g = 3.3e-5`, `cs*g` is
numerically zero, and a predictor of ~zero scores a normalised MAE of exactly 1.0;
`cs/g` overshoots by `1/g ≈ 30000`, which is the MAE it returned. So `weight_scale_2` is
**inert metadata** for this tensor — a leftover global amax the exporter recorded but did
not fold into the block scales. The conversion formula is exactly:

```
value_fp8 = (codebook[nibble] / 6.0) * block_scale   ->  cast to float8_e4m3fn
```

Anyone tempted to "fix" the mod by honouring `weight_scale_2` should re-run
`.upstream-cache/probe_ple_gscale.py` first. Note also that the `block_absmax/stored_scale
== 6.0` identity does **not** prove anything about `g`: dequantising with `c*s` yields
`absmax = 6*s` by construction, so that ratio equals the codebook max no matter what `g`
is. It pinned the codebook, not the global scale. Only the absolute element-wise fit
against an independent encoding could do that.

That the residual is 8.6% rather than ~1% is expected and is *not* a conversion bug: it is
the disagreement between two independent quantisations of the same bf16 source (NVFP4's
3-bit codebook vs e4m3's 4-bit mantissa), and 8.6% is the right order for a 2-mantissa-bit
format. An e4m3 round-trip on in-range values measures 1.0% on this data.

That last point matters more than it looks. Without the `/6`, **4.65%** of dequantised
values exceed the e4m3 finite ceiling of 448 (absmax 1536), so a naive conversion would
silently saturate nearly five percent of the table and cost 2.7% total-relative error.
With it, **0.000%** exceed the ceiling.

## What the mod does

For each of the 128 PLE shards it unpacks nibbles, applies `/6 * scale`, casts to fp8
e4m3, and writes a shard carrying only `[2500012, 160]` fp8 — byte-for-byte the shape and
dtype RadixArk uses. It writes a matching `model.safetensors.index.json`, and sets
`text_config.ple_embedding_dtype = "float8_e4m3fn"` so the engine selects its own tested
fp8 path. **No engine source patch and no anchor fragility.** Everything lands in the
mod-built patched tree; the shared Hugging Face cache is never written.

## Why unpack rather than patch the loader

Two options were on the table: patch `qwen4_exp.py` to unpack in-place, or rewrite the
shards on disk. The loader patch needs a per-layer scale cache that survives arbitrary
weight/scale ordering across 128 shards in a multithreaded loader, plus an anchor that
breaks on every rebase. The disk rewrite trades ~51 GB and one-time minutes for zero
fragility and reuses a code path that already ships and works. Chosen for the latter.

Cost, measured: 22.40 GB packed weights → **51.2 GB** fp8 (`2500012 x 160 x 128`). Disk is
not the constraint (3.2 TB free per node); first-boot write time is, so the output is
cached on **host-local disk** per node rather than the NFS cache, and reused across boots.

## What this mod does NOT claim

It makes the checkpoint *loadable*, not *correct*. The PLE table is the one component the
labquant export quantises that RadixArk leaves fp8, and PLE feeds the n-gram prediction
path that speculative decoding leans on — so this is the least safe place in the model to
introduce a quantisation change. Expect a **quality** question here even though the
arithmetic is sound, and gate it on an eval before adoption. Also note the unpacked table
is fp8 either way, so this specific change buys no per-token bandwidth; the labquant
throughput case rests on its FP8 dense projections (§18.2), not on PLE.

## Failure mode

Fails closed. If shard count, shapes, or dtypes differ from the pinned contract it prints
what it found and exits non-zero rather than writing a half-converted tree. A numeric
self-check compares a sample of converted rows against an independent dequantisation and
refuses the output if the error is larger than an fp8 round-trip should produce.
