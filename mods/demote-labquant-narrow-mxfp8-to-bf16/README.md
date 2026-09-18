# demote-labquant-narrow-mxfp8-to-bf16

Demote `local-inference-lab/Qwen3.8-Flash-Next-NVFP4`'s narrow MXFP8 projections —
in practice the Gated DeltaNet `linear_attn.in_proj_a` / `.in_proj_b` pair — to plain
BF16, so the server boots at all.

**Recipe:** `recipes/qwen4/qwen3.8-flash-next-nvfp4-labquant-sglang.yaml`
**Runs after:** `mods/fix-labquant-modelopt-mixed-flat-schema`,
`mods/unpack-labquant-ple-nvfp4-to-fp8`. **Layers onto:** `/cache/runtime/labq-patched`.

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

**2. Named leaves (`EXTRA_LEAVES`, empty by default).** Below the floor is not the only
possible reason to move a projection, so the mechanism exists — but it ships **empty**, and
the history of why is the useful part. The first candidate was `index_qk_proj`: labquant
MXFP8s it (`F8_E4M3 [640,2560]` + U8 scale) where RadixArk ships the same tensor
`BF16 [640,2560]`, and both boots that reached CUDA-graph capture died inside the QSA prefill
path. It was on by default as the cheapest control for that crash. The control was run —
boot `11b2c8b941e89cb9`, 2026-09-18 22:05 — and the live tree was checked to confirm it
actually took effect (84 tensors demoted, 84 scales dropped, 168 ignore entries, the
projection present as `BF16 [640,2560]` with no surviving scale). CUDA-graph capture died
with the **identical** pinned-memory error in the same frames. So MXFP8 placement of
`index_qk_proj` does not cause it, and the demotion is off: this arm should differ from the
reference export only where the engine mechanically forces it to, and nothing forces this.
The knob stays because that crash is unresolved and a future bisect may want the lever back.

Set `MOD_DEMOTE_EXTRA_LEAVES` to a comma list to name leaves (empty string = floor test
only). A one-line file at `/cache/runtime/demote_extra_leaves` does the same for a real
launch, since a pre_exec mod has no clean way to receive an env var. That file is
deliberately **not** self-deleting: pre_exec runs once per node against the same host-mounted
`/cache/runtime`, so a file that deletes itself gives the first node one override and every
later node another — a split-brain TP group that would present as a numerical mystery rather
than an error.

Weight bytes: 4.72 MB of BF16 replaces 2.46 MB of MXFP8+scale → **+0.14 MB per node**.
Negligible.

Runtime cost: **none measured, and none expected** — but the reasoning is worth
recording because it nearly went the other way. `finalize_fused_in_proj()`
(`qwen3_5.py`) folds `in_proj_qkvz` + `in_proj_ba` into one GEMM only when **both** are
`UnquantizedLinearMethod` **and** bf16. I initially predicted that making `in_proj_ba`
bf16 would trip that guard and drag the fp8 `in_proj_qkvz` GEMM into bf16 arithmetic —
a real regression. The pre-boot gate (`preflight_patched_config.py`, run against the
patched tree on the pinned image) shows it does not: `in_proj_qkvz` is still
`Fp8LinearMethod`, the guard still declines, and the forward pass keeps running two
GEMMs exactly as it does today. The prediction was wrong because it only checked the
half of the guard this mod changes.

If a future change does make both bf16, the fused GEMM becomes `m=8, n=4120, k=2560`
in bf16, which trades MXFP8 arithmetic on the big projection for bf16 on the whole
thing — a measurement, not a claim.

## Validation performed before writing this mod

All on the pinned image / pinned snapshot, none requiring a GPU:

- `mxfp8_floor_check.py` — enumerated every MXFP8 projection from shard headers and
  applied the engine's own fusion rules. **72** projections are below the floor at
  TP=2 and they are **all** `in_proj_a`/`in_proj_b`; nothing else in this checkpoint is
  anywhere near the floor (`in_proj_qkvz` fuses to 4096, `gate_up_proj` to 2560). So
  demoting these is sufficient, not whack-a-mole. The mod reports its own count and
  warns if it differs from the 72 this revision is contracted to produce.
- `probe_demote_plan4.py` — the spelling table above, the silent-cast measurement, and
  the parameter names the GDN registers (`in_proj_ba.weight [96, 2560]`).
- `probe_demote_plan.py` — confirmed `packed_modules_mapping` is injected by
  `get_quant_config` from the **model** class (`qwen4_exp.py:1767`), not from the
  checkpoint (whose own `packed_modules_mapping` is null), which is what makes
  component-spelled `ignore` entries match the fused prefix at all.

## Fails closed

Refuses to run if: the pinned revision is not cached; `/cache/runtime/labq-patched`
does not exist (i.e. the config mod has not run); a scale tensor is not `U8`; the
members of a fused group disagree on `k`; a dequantised value is non-finite; the BF16
round-trip is not bit-exact; or the index does not exist. It never deletes the tree,
never writes through a symlink into the shared HF snapshot, and is idempotent (it
recognises an already-demoted shard by dtype + absent scale, not by size).
