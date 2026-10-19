# demote-labquant-narrow-mxfp8-to-bf16

Demote `local-inference-lab/Qwen3.8-Flash-Next-NVFP4`'s narrow MXFP8 projections —
in practice the Gated DeltaNet `linear_attn.in_proj_a` / `.in_proj_b` pair — to plain
BF16, so the server boots at all.

**Recipe:** `recipes/qwen4/qwen3.8-flash-next-nvfp4-labquant-sglang.yaml`
**Runs after:** `recipes/qwen4/mods/fix-labquant-modelopt-mixed-flat-schema`,
`recipes/qwen4/mods/unpack-labquant-ple-nvfp4-to-fp8`. **Layers onto:** `/cache/runtime/labq-patched`.

## The blocker

```
ValueError: MXFP8 requires n >= 128 and k >= 128 for CUTLASS MXFP8.
            got m=8, n=96, k=2560
```

`linear_attn.in_proj_a` and `.in_proj_b` are `[48, 2560]` each. The engine fuses them
into one `in_proj_ba` `MergedColumnParallelLinear([48, 48])`, so the GEMM's output
dimension is 96 — 48 per rank at TP=2. Both are under CUTLASS's MXFP8 floor of 128.
RadixArk ships these same two projections **BF16** (verified against its safetensors
headers), so the reference export for this model does not MXFP8 them either. This is
not a labquant quirk to argue with; it is labquant having quantised something the
engine cannot execute.

## Why config alone cannot do it

`ModelOptMixedPrecisionConfig._get_quant_method` checks `is_layer_skipped(...)`
**before** consulting `quantized_layers` (`modelopt_quant.py:294` vs `:952`), so an
`ignore` entry naming the component does win — but only in the right spelling, and
that was worth measuring rather than reasoning about. Probe on the pinned image with
real `MergedColumnParallelLinear` objects (`probe_demote_plan4.py`, 2026-09-18):

| prefix passed to the engine | `ignore` spelling | resulting method |
|---|---|---|
| `model.layers.0...in_proj_ba` | `model.language_model.layers.0...in_proj_{a,b}` | `Fp8LinearMethod` |
| `model.layers.0...in_proj_ba` | `model.layers.0...in_proj_{a,b}` | **`UnquantizedLinearMethod`** |
| `model.language_model.layers.0...in_proj_ba` | `model.language_model...` | `UnquantizedLinearMethod` |
| `model.language_model.layers.0...in_proj_ba` | `model.layers...` | `Fp8LinearMethod` |
| either | only `in_proj_a` (half a fused pair) | **`ValueError`: "some but not all shards"** |

The engine's own prefix is the **short** one — `qwen4_exp.py:2008` rewrites checkpoint
names with `name.replace("model.language_model.", "model.")` before matching. The mod
writes **both** spellings for every layer, which is correct under either, and always
demotes a fused pair whole because half a pair raises.

## Why the shard bytes must be rewritten too

This is the part that would otherwise ship a silent bug. With the layer unquantized
the parameter is BF16, but the checkpoint still holds `F8_E4M3` bytes, and the
engine's fallback loader is `param.data.copy_(loaded_weight)`
(`weight_utils.py:645`). torch casts e4m3 → bf16 happily. Measured on the pinned
image: an e4m3 byte `0x30` (which decodes to **2.0**) landed in a BF16 parameter as
**0.5** — the per-32-element ue8m0 block scale was never applied, because nobody was
asked to apply it. **No exception was raised.** A server built that way boots,
answers, and benchmarks. It is just numerically wrong, and every tok/s in this repo's
tables would be describing a wrong model.

So the mod decodes the MXFP8 pair to its true BF16 value on disk and drops the
now-orphaned scale tensor. The scale must be dropped regardless: left behind it has no
destination parameter and the load dies at `qwen4_exp.py:2140`
(`abs(weight.item() - 1.0) < 1e-6`) — and that assert cannot even print the tensor's
name, because `.item()` raises first on a multi-element tensor (verified).

## Exactness, not approximation

e4m3 carries 4 significand bits; a ue8m0 scale is a power of two. Therefore
`q * 2**(e-127)` needs 4 significant bits, and bf16 carries 8. The conversion is
**lossless** for finite normal inputs. The mod does not trust that argument: it
asserts per tensor that the BF16 round-trip is bit-exact against the fp32 dequant, and
refuses to write the tree if it is not. It also refuses on NaN in the payload and on
scale byte `255` (NaN in e8m0).

This is a placement change, not a re-quantisation: the BF16 tensor written here is the
value the MXFP8 GEMM would have produced.

## Scope, and what it costs

Two reasons a projection is demoted, deliberately kept separate:

**1. The CUTLASS floor (automatic).** Only tensors that are (`F8_E4M3` weight + `uint8`
scale) **and** whose *fused* output width is below the floor at the configured TP. For the
pinned revision that is exactly **72 tensors** — `in_proj_a` + `in_proj_b` for the 36
`linear_attn` layers (the other 12 layers are full-attention and have no
`in_proj_a`/`in_proj_b` at all — verified from shard 35's header), all inside
`model-00035-of-00036.safetensors` (2.79 GB). `in_proj_qkv` (2048), `in_proj_z` (2048),
`out_proj` (2560) and every `self_attn` projection stay MXFP8, so this is not
"we dequantised the attention".

**2. Named leaves — REMOVED 2026-10-19.** The mod once accepted `MOD_DEMOTE_EXTRA_LEAVES` (and a
runtime file) to demote projections the floor test would not select. Its only stated purpose was the
QSA-prefill CUDA-graph crash, and that hypothesis is falsified: the crash is a host sync plus a
data-dependent buffer inside `get_prefill_mqa_inputs`, which reads no projection dtype, and the
demoted-`index_qk_proj` boot (`11b2c8b941e89cb9`) crashed identically. Nothing the knob could demote
can recover it, so the machinery is gone rather than shipped empty; git history keeps it if a future
bisect ever names a leaf. What remains is exactly the CUTLASS floor test below, whose count contract
is now always enforced. Analysis: `mad-science/QWEN4-DIAGNOSTICS.md`.

