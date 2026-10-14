---
name: diag-qwen4-unplaced-scales
description: >
  Dump what the Qwen4-Exp weight loader actually has available when it cannot place a
  `_scale` tensor, instead of dying on a bare assert.
---

# Why this mod exists

The labquant checkpoint fails to load with

```
RuntimeError: a Tensor with 51200 elements cannot be converted to Scalar
```

raised at `qwen4_exp.py:2136`:

```python
if name.endswith("_scale") and name not in params_dict:
    assert abs(loaded_weight.item() - 1.0) < 1e-6, f"Expected 1.0, ... in skipped {name}"
```

That assert is **correct** — a `_scale` tensor that is not the scalar `1.0` is a real
quantisation scale being dropped, and proceeding would serve plausible garbage. It is also
**useless for diagnosis**, for two reasons:

1. `.item()` raises *while building the f-string*, so the failing tensor's name is never
   logged. Four hours of static analysis could not identify the owner of the 51200-element
   tensor from the log.
2. It says nothing about what the model *did* build. The interesting question is not "which
   tensor is homeless" but "why is there no parameter for it" — i.e. what quant method the
   layer received and which scale parameter names it registered.

Static analysis of that question failed four times, including a probe that returned `None`
for every layer because the faked layer object lacked attributes (`lm_head` coming back
"unquantised" was the tell — it is NVFP4 on disk). So this mod replaces guessing with
observation: on the first unplaceable `_scale`, log the tensor's name/shape/dtype, the
enclosing layer's registered parameters with their classes and shapes, and every
scale-shaped name the module tree does know about. One boot then answers it.

# Scope and safety

- **Diagnostic only.** It adds a logging call and does not alter control flow: the assert
  still fires and the server still fails. It deliberately does **not** relax the assert,
  because a silent skip would load a model with dropped scales.
- Anchored and idempotent; refuses to patch if the anchor does not match exactly once.
- Reowns the whole runtime cache, because importing sglang in-container triggers flashinfer's
  JIT as root and leaves a file uid 1000 cannot open — the failure this recipe already
  documents for the fastsafetensors mods.
