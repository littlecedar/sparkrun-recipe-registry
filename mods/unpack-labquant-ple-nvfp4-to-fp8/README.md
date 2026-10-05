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

### `weight_scale_2` — SUPERSEDED. It IS applied, and not applying it broke the model.

**This section used to say the opposite. Read it as a post-mortem, not as guidance.**

There is one extra PLE tensor: `…ngram_embedding.weight_scale_2`, `F32 [1]`, value
**3.324236240587197e-05**. In ModelOpt's two-level NVFP4 scheme that is the per-tensor
global scale. The table below is what this file used to argue from — normed MAE,
element-wise, against RadixArk's independent fp8 encoding of the same rows:

| dequantisation hypothesis | normed MAE vs reference |
|---|---|
| `codebook * scale / 6` | **0.08586** |
| `codebook * scale * g` | 0.99980 |
| `codebook * scale * g / 6` | 29843.3 |
| `codebook * scale / g` | 179064.9 |

> **Do not read that table quantitatively.** One row is arithmetically impossible as written:
> `codebook*scale*g/6` *is* `(codebook*scale*g)/6`, so it is the 0.99980 candidate divided by 6 —
> a candidate 6x *smaller* than one that already sits far below the reference, which cannot move
> the error to 29843. Rows 3 and 4 also differ from `1/g` and `6/g` by a consistent ~0.8%, so
> whatever produced them used a `g` or a normalisation that is not recorded here. I could not
> reconstruct it from what is in this file, so the rows are left as historically measured rather
> than silently corrected, and the cause of the inconsistency is **unknown** rather than
> explained. Nothing in the conclusion depends on them: the `6 * weight_scale_2` factor is
> established by the engine-final relative-L2 table below, which is independent of this one. If
> you need these numbers, regenerate them.

From that table the previous revision concluded `weight_scale_2` was "inert metadata …
a leftover global amax the exporter recorded but did not fold into the block scales",
and shipped the mod without applying it. **The conversion formula was right. The
conclusion drawn from it was wrong**, because the question the table answers
("what does the *stored* table decode to?") is not the question that matters ("what
does the *engine* end up multiplying by?"). Between those two sits a buffer.

The engine multiplies this table by a per-tensor buffer after loading:
`qwen4_exp.py:530` `register_buffer("weight_scale", torch.ones(1, dtype=torch.bfloat16),
persistent=True)`, applied at `:585` and `:1202`. So the stored table is only ever half
of the value. labquant records the other half as `weight_scale_2`; the engine's buffer
matcher at `:1810` accepts **only the exact name `weight_scale`**, rejects
`weight_scale_2`, and the tensor is dropped with one log line:

```
Parameter model.layers.1.ple.ple_embedding.ngram_embedding.weight_scale_2
not found while loading Qwen4-Exp VL weights
```

The buffer then keeps its init value **1.0**. RadixArk ships the identical number
under the name the engine reads (`ngram_embedding.weight_scale`, `BF16 [1]` =
**1.9931793212890625e-04**), which is the only reason that checkpoint works and this
one served token salad while passing every load-time assertion.

And `6 * 3.324236240587197e-05 = 1.9945417443523182e-04` — RadixArk's value, to 0.07%.

It is a **single** tensor, not a per-layer one. Measured by scanning every shard
header in both checkpoints: labquant has exactly 1 name ending
`.ngram_embedding.weight_scale_2` (`F32 [1]`, `model-00034-of-00036.safetensors`) and
RadixArk exactly 1 ending `.ngram_embedding.weight_scale` (`BF16 [1]`,
`model-plefp8-00009.safetensors`), both nominally at layer 1. That is consistent with
the n-gram table being hash-sharded rather than replicated per layer — the 128
`shard_N` tensors are buckets, not per-layer copies — so one scalar governs the whole
path, and emitting one file is a complete fix rather than 1/48th of one. (An earlier
draft of this paragraph claimed "36 layers". That number was never measured. The
1-layer figure above is.)

### Why the old probe misled us, stated precisely (and it was not the metric)

It is tempting to blame normed MAE, and **that blame does not hold**. Normed MAE against
reference `b` scores `|k-1|` for a candidate off by scale `k` — it sees a global scale
factor sharply. The table above is the proof, and it is self-consistent to three
significant figures: for candidate `cs*k` against raw reference `cs/6` the metric computes
`6*|k - 1/6|`, so `k=g=3.3e-5` gives 6·|0.0000332−0.1667| ≈ **0.9998** (measured 0.99980)
and `k=1/g≈30080` gives 6·30080 ≈ **180494** (measured 179065). The instrument was fine.

The error was **scope**. The reference was RadixArk's *raw stored* table, which silently
presupposes there is no engine-side multiply. Comparing raw-to-raw can only ever rank
*shapes*; the correct hypothesis `cs*g/6` was penalised 29843 for being correct, because
against a raw reference it genuinely is 6× too small. Fix the reference's scope — compare
the two **engine-final** tables, each after its own `weight_scale` multiply — and the
ranking inverts. Using absolute relative-L2, which for a pure scale error is exactly
`|k-1|`:

| engine buffer value | relL2 vs RadixArk engine-final table |
|---|---|
| `1.0` (what shipped) | **5011.5** |
| `weight_scale_2` | 0.834 = \|1/6 − 1\| exactly |
| `6 * weight_scale_2` (**the fix**) | **0.098** |
| RadixArk's own `weight_scale` | 0.098 — the achievable floor |

Hitting the floor means the fix is as correct as this checkpoint can be; the residual 9.8%
is the same two-independent-quantisations disagreement as the 8.6% above. Note the second
row landing on exactly |1/6 − 1| is the `/6` relationship confirming itself independently.

The generalisable lesson, and it is the same one §7 of the work doc keeps re-learning:
**verify the value at the point of use, not at the point of storage.** Every check here
passed on stored bytes. The defect was in the name the loader looked for.

`block_absmax/stored_scale == 6.0` still does not say anything about `g` — dequantising
with `c*s` yields `absmax = 6*s` by construction, so that ratio is the codebook max
whatever `g` is. It pinned the codebook. That part of the old note was correct; only its
scope was too narrow.

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
cached on **host-local disk** per node rather than the HF cache, and reused across boots.

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
