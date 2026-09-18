---
name: skip-labquant-vision-tower
description: >
  Let SGLang load local-inference-lab/Qwen3.8-Flash-Next-NVFP4 by declaring the
  checkpoint text-only, so the MXFP8-quantised vision tower is neither built nor loaded.
---

# Why this mod exists

The labquant export **quantises the vision tower**; the RadixArk export does not. Measured
from the shard headers on the shared cache:

| checkpoint | vision tensors | dtypes | `quantized_layers` mentioning visual | `ignore` |
|---|---|---|---|---|
| RadixArk | 333 | all `BF16` | 0 of 0 | `model.visual.*` |
| labquant | 470 | 223 `BF16`, **110 `F8_E4M3`**, **110 `U8`**, 27 `F32` | **110 of 544** | *(empty)* |

SGLang builds the vision tower with **`quant_config=None`** — `qwen3_vl.py:1251`:

```python
self.visual = Qwen3VLMoeVisionModel(
    config.vision_config,
    # NOTE: Qwen3-VL vision encoder currently supports BitsAndBytes 4-bit quantization.
    # Other quantization methods (e.g., GPTQ, AWQ) are untested and may not be supported.
    quant_config=None,
    ...
)
```

So vision `Linear`s carry only `weight`/`bias` — confirmed by the diagnostic loader, which
found exactly 2 parameters under `visual.blocks.0.attn.proj.` — and there is **nowhere to
put** a scale tensor. `qwen4_exp.py:2133` rewrites `model.visual.*` → `visual.*`, and the
`endswith("_scale")` guard then dies on the first one:

```
[diag] UNPLACED _scale name=visual.blocks.0.attn.proj.weight_scale
       shape=(1152, 36) dtype=torch.uint8 numel=41472
```

This is a **structural** blocker, not a naming one: no remap can fix it, because the
destination parameter does not exist and would have no quant method to interpret it.

# The fix

`qwen3_vl.py:1243` already implements the escape hatch:

```python
self.language_model_only = getattr(config, "language_model_only", False)
if self.language_model_only:
    self.visual = None
```

and `qwen4_exp.py:2004` then skips the visual tensors during load
(`[language_model_only] Qwen4 load_weights: skipped N visual weights`).

We set `language_model_only: true` in the **patched** `config.json`. That deliberately
avoids the CLI route: `--language-model-only` is rejected for this architecture
(`server_args.py:7724` allows only `MuseGlimmerForConditionalGeneration`), but
`model_config.py:331` reads the same value straight off `hf_config`, so the checkpoint can
declare it. `is_lm_only` is then propagated back onto `hf_config` at `model_config.py:552`.

# Scope and honesty

- **This makes a text-only server.** Image and video input will not work. That is already
  true of every benchmark run here — `fast-smoke`, `deep-smoke` and `triage-smoke` are text
  prompts — so no measured capability is lost. It is **not** a general-purpose serving
  configuration and must not be used for one.
- The skipped vision weights are ~0.4% of the checkpoint's tensors and the vision tower was
  never exercised; they are dropped, not requantised.
- Because the export quantises a component the engine cannot serve, this checkpoint is
  **strictly less capable** than RadixArk as deployed here, independent of any throughput
  result. Any comparison between the two must say so.
- Verification is by log line, not by silence: a successful run must print
  `skipped ... visual weights`. Absence of the assert is not sufficient — it would also be
  absent if the load died earlier for another reason.
