---
name: fix-labquant-mxfp8-weight-scale-name
description: >
  Let Qwen4-Exp place the MXFP8 (ue8m0) weight scales that
  local-inference-lab/Qwen3.8-Flash-Next-NVFP4 stores as `weight_scale`, where the
  engine registers the same tensor under `weight_scale_inv`.
---

# Why this mod exists

The labquant export MXFP8-quantises the shared experts and the sparse-attention indexer
(`group_mxfp8_shared_experts`, `group_mxfp8_attention`, `MXFP8`, `group_size: 32`, empty
`ignore` list). It ships those scales as, e.g.

```
model.layers.0.mlp.shared_expert.down_proj.weight_scale   U8  [2560, 20]
```

The engine builds exactly the corresponding parameter, under a different name. From
`srt/layers/quantization/fp8.py` in the pinned image, `Fp8LinearMethod.create_fp8_weight_`
in the `block_quant` branch:

```python
scale_dtype = torch.uint8 if use_mxfp8 else torch.float32
scale = BlockQuantScaleParameter(
    data=scale_init((out_per + block_n - 1) // block_n,
                    (in_per  + block_k - 1) // block_k, dtype=scale_dtype), ...)
scale.format_ue8m0 = use_mxfp8
layer.register_parameter("weight_scale_inv", scale)
```

`use_mxfp8` forces `weight_block_size == [1, 32]` and `scale_dtype == torch.uint8`, i.e.
**the identical dtype, block layout and storage semantics as the checkpoint — the tensors
differ only in the suffix of their name.** Shapes reconcile exactly: the checkpoint's full
`[2560, 20]` scale (`640/32 = 20` blocks along K) is sharded by the weight loader to the
`[2560, 10]` parameter observed at TP=2 (`320/32 = 10`).

So the load dies on the guard that exists to catch *dropped* scales
(`qwen4_exp.py:2136`), and the only reason the name lookup misses is the suffix.

# What the mod does

In `Qwen4ExpForCausalLM.load_weights`, immediately before the per-weight dispatch, rename
`<X>.weight_scale` → `<X>.weight_scale_inv` **only when both** of these hold:

1. `<X>.weight_scale` is **not** a parameter of the model, and
2. `<X>.weight_scale_inv` **is**.

Condition 2 is what makes this safe rather than a global find-and-replace: the rename can
only ever fire on a tensor whose load was already going to fail. Nothing that loaded
correctly before can change behaviour, because for those the original name resolves and the
guard never triggers.

That matters concretely for the routed experts, whose scales are registered as
`w13_weight_scale` / `w2_weight_scale` and reach the model via `stacked_params_mapping`.
For `...experts.gate_up_proj.weight_scale`, condition 2 fails (`...gate_up_proj.weight_scale_inv`
is not a parameter either), so the rename declines and the existing stacked mapping runs
unchanged. A blanket rename **would** have broken expert loading by producing
`w13_weight_scale_inv`; the conditional is load-bearing, not decoration.

`self_attn.indexer.weight_scale` is handled by the same rule, and likewise declines if the
engine happens not to register a `weight_scale_inv` for it.

# What this mod does NOT claim

It does not make the checkpoint accurate, and it is not proof the model is numerically
correct. It changes **where a byte array is stored**, not its contents — no arithmetic, no
requantisation. The correctness question that remains is whether the engine's MXFP8 GEMM
path interprets `ue8m0` the same way this export produced it. That needs the numerical
check described in `../../recipes/qwen4/QWEN4-MODEL-OPTIMIZATION-WORK.md` §7, not this mod. Loading is
necessary, not sufficient.

Independent support that these scales are dequant scales in e8m0 form (not reciprocal, not
requiring a global factor): dequantising the labquant PLE table with
`(E2M1[codebook]/6) * block_scale` reproduces RadixArk's independent fp8 encoding of the
same weights to 0.086 normalised MAE, and applying the extra `weight_scale_2` global would
have been off by ~30000×.

# Failure mode

Anchored and idempotent: refuses to patch unless the anchor matches exactly once, and the
patched module must still import. It is a diagnostic-friendly patch — the `diag-qwen4-unplaced-scales`
mod stays installed, so if any `_scale` still cannot be placed it will say which one instead
of dying on an assert that cannot print a name.
