---
name: fix-labquant-modelopt-mixed-flat-schema
description: >
  Let SGLang's modelopt_mixed loader accept the
  local-inference-lab/Qwen3.8-Flash-Next-NVFP4 quantization metadata.
---

# Why this mod exists

`local-inference-lab/Qwen3.8-Flash-Next-NVFP4` ships its ModelOpt metadata in
`config.json` under `quantization_config`, and separately in a top-level
`hf_quant_config.json`. The two are in **different schemas**:

| file | shape |
|---|---|
| `config.json` → `quantization_config` | flat: `quant_algo`, `quant_method`, `config_groups`, `ignore`, `producer`, `quantized_layers` (544 entries) |
| `hf_quant_config.json` | **also flat**, same six keys |
| what `weight_utils.py` expects | **nested**: `{"producer": …, "quantization": {"quant_algo": …, "exclude_modules": […]}}` (this is what `RadixArk/…NVFP4` ships) |

SGLang's `get_quant_config()` (`srt/model_loader/weight_utils.py`) prefers the inline
`config.json` block, **except** for `quantization=modelopt_mixed`, where it deliberately
falls through to the file-based path when the inline block is judged incomplete:

```python
modelopt_mixed_config_incomplete = (
    model_config.quantization == "modelopt_mixed"
    and (
        "quantized_layers" not in hf_quant_config
        or ("kv_cache_quant_algo" not in hf_quant_config
            and "kv_cache_scheme" not in hf_quant_config)
    )
)
```

The labquant inline block has `quantized_layers` but **neither** KV-cache key, so the
guard is True, SGLang falls through to `hf_quant_config.json`, and then indexes it
unconditionally:

```python
quant_algo = config["quantization"]["quant_algo"]   # weight_utils.py:410
```

which raises `KeyError: 'quantization'` and SIGQUITs the engine during model load.
Reproduced VERIFIED in `lmsysorg/sglang:dev-cu13-qwen38-next-local@sha256:9d2a843c…`
(branch `qwen4-main-squashed`, HEAD `9b2aee2283`).

## The fix

The model card states there is **no KV-cache quantization metadata**, and we run
`--kv-cache-dtype bf16`. So `kv_cache_quant_algo` is legitimately *absent-as-null*, and
declaring it explicitly as `null` is truthful rather than fabricated. Adding it to the
inline block makes the fall-through condition False, so SGLang uses the inline block —
which `ModelOptMixedPrecisionConfig.from_config()` accepts, producing all five sub-configs
(`fp8_config`, `fp8_block_config`, `nvfp4_config`, `nvfp4a16_config`, `mxfp8_config`) and
`get_min_capability() == 80`.

We write a **patched copy** of `config.json` into the container at a fresh snapshot
directory and symlink every other file from the real snapshot, so **no shared NFS cache
is mutated** — other users and other models are untouched. The recipe then points
`--model-path` at that directory.

## What this mod does NOT claim

It does not make the checkpoint *accurate*. It makes it *loadable*. Passing config parse
is not evidence of numerical correctness; the labquant export quantises the attention/GDN
projections and the PLE n-gram table where the RadixArk export leaves them BF16, and no
eval exists for it on this cluster. Benchmark wins from it are not quality evidence.

## Failure mode

If the snapshot layout or the upstream guard changes, the mod prints `SKIP` reasons and
exits 0 rather than leaving a half-written tree. It never overwrites a file it did not
create.
