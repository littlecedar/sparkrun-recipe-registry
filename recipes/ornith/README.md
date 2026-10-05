# Ornith 1.5 on DGX Spark — `ornith`

Serving recipes for **Ornith 1.5**, the self-improving agentic-coding model family from the
[Ornith Team](https://ornith.ai/ornith_1_5.html), on NVIDIA DGX Spark (GB10, SM121, 128 GB
unified LPDDR5X per node, 200 GbE ConnectX-7 RoCE). This directory is the `ornith` lane; it
ships **two** recipes, one per model scale:

| Recipe                                            | Scale | Runtime | Nodes (TP) | C1 t/s |  Size |  Mem | Flags  | Model Cards                                                                                 |
|:--------------------------------------------------|:------|:--------|:-----------|-------:|------:|-----:|:-------|:--------------------------------------------------------------------------------------------|
| `ornith-1.5-35b-a3b-nvfp4-dflash2-sglang.yaml`    | 35B-A3B | SGLang | 1 (TP=1) |    100 |  45GB | 0.85 | ✨🚀🌲 | [Model][model-35b] · [Draft][draft-dflash2]                                                 |
| `littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm.yaml` | 397B | vLLM | 4 (TP=4) |  41.86 | 235GB | 0.80 | 🌲     | [Model][model-397b-graft]                                                                   |

`C1 t/s` is single-stream decode as recorded in the parent [`recipes/README.md`](../README.md);
`Size` is the per-node footprint the registry records and `Mem` is the recipe's
`gpu_memory_utilization`. Flags are defined in [Model Flags](../README.md#model-flags).
Both recipes are `sparkrun recipe validate`-clean on sparkrun v0.3.10 (verified 2026-10-04).

## About the model

Ornith 1.5 extends Ornith 1.0 (itself a continued-pretraining of Qwen3.5 and Gemma 4) by expanding
the self-scaffolding loop into end-to-end self-improvement: the model proposes tasks, builds the
evaluation harness, and produces solution rollouts. It is an **agentic coding** family — Terminal-Bench,
SWE-bench, MCP-Atlas, Toolathlon — and it is a **reasoning model**: assistant turns open with a
` thinking … </think>` block, and tool calls are emitted as Qwen-style XML. Both recipes therefore wire
the `qwen3` reasoning parser and a Qwen tool-call parser (`qwen3_coder` on SGLang, `qwen3_xml` on vLLM) so
the chain-of-thought surfaces as `reasoning_content` and tool calls as OpenAI `tool_calls` — matching the
launch parameters the [upstream model cards](https://ornith.ai/ornith_1_5.html) publish. The 262,144-token
native context is served as-is; the model card's YaRN long-context override is **not** in either shipped
recipe (see [Caveats](#caveats)).

Recommended sampling (model card): `temperature=0.6`, `top_p=0.95`, `top_k=20` for general use,
`temperature=1.0` to reproduce the reported benchmark numbers.

## `ornith-1.5-35b-a3b-nvfp4-dflash2-sglang.yaml` — the fast single-Spark lane

The 35B-A3B is a MoE that activates ~3B parameters per token, so it fits and serves on **one** Spark
(the registry records a 45 GB footprint at `gpu_memory_utilization: 0.85`). The recipe pairs the official
NVFP4 checkpoint with the [`jzinno/Ornith-1.5-35B-A3B-DFlash2`][draft-dflash2] speculative draft and
turns on DFlash2 (`--speculative-algorithm DFLASH`, 4 draft tokens) — the recipe behind the ~100 t/s C1
row in the parent table.

Wiring worth knowing:

- **Model:** [`ornith-ai/Ornith-1.5-35B-A3B-NVFP4`][model-35b] — NVFP4 (`modelopt`, mixed precision: FP8
  on attention / linear-attention projections, W4A16_NVFP4 on the routed and shared experts and `lm_head`).
  `config.json` reports `model_type: qwen3_5_moe`, 40 layers with full attention every 4th layer
  (`full_attention_interval: 4`), 256 experts with top-8 routing, `max_position_embeddings: 262144`. The
  NF4/NVFP4 checkpoint is MIT-licensed.
- **Runtime:** SGLang, container `lmsysorg/sglang:dev-cu13@sha256:9a352a35…` (digest-pinned).
- **Hybrid-mamba memory:** `mamba_full_memory_ratio: 3.51` with `mamba_ssm_dtype: bfloat16` and
  `mamba_radix_cache_strategy: extra_buffer_lazy`. 3.51 is a **house value copied across lanes, not a
  value derived from this checkpoint** — the same trio appears in the Qwen3.8-27B dflash2 recipe, and the
  qwen3 lane's worklog flags it as a shared default with no recorded rationale. It reallocates the
  leftover pool heavily toward linear-attention (GDN) state; the concurrency consequences are the
  `max_mamba_cache_size` question, not a source-reading question.
- **`max_num_seqs: 48`** with `--max-running-requests 48`. Note this is the admission cap, and on this
  stack the *effective* ceiling can be the mamba state pool, not `max_num_seqs`.
- **Spec decode is user-visible in the log:** check `Mean acceptance length > 1` on `Decode batch` lines.
  A DFlash2 boot that serves but accepts ≈1 token/step is a misconfiguration, not a win.
- **`--load-format fastsafetensors`** is supplied by the `@littlecedar/mods/pip-install-fastsafetensors`
  mod; `@eugr/mods/drop-caches` is inert here (see [Caveats](#caveats)).

**Independent evidence for the draft.** The DFlash2 model card reports a held-out serving evaluation on
one DGX Spark: autoregressive serving at C1 = **79.3 tok/s**, and the DFlash2 draft at C1 = **114.2 tok/s
(+44%)** with mean accepted length **4.02**, rising to 236.5 tok/s aggregate at C8. Those numbers were
measured by the draft author on a **different engine configuration** than ours (their reference run uses
`--moe-runner-backend marlin`, `--mamba-radix-cache-strategy extra_buffer`, `--mamba-ssm-dtype float32`,
and 10 draft tokens; we ship `flashinfer_cutlass`, `extra_buffer_lazy`, `bfloat16`, and 4 draft tokens),
so treat 114.2 as a **corroborating reference point, not this recipe's measured number**. Our published
C1 of ~100 t/s sits between the author's AR and DFlash2 figures, consistent with the shipped recipe — but
it has not been re-measured on our nodes with a pinned harness in this pass.

## `littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm.yaml` — the flagship 4-node lane

The 397B is the flagship MoE. It is served on **four** Sparks with vLLM at TP=4, `--enable-expert-parallel`,
and the checkpoint's own MTP head as the speculative method (3 tokens). The registry records a **235 GB
per-node** footprint at `gpu_memory_utilization: 0.80`, which is why it needs four nodes and cannot be a
single-Spark recipe.

- **Model:** [`littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft`][model-397b-graft] — a Little Cedar derivative
  that **grafts the BFP16 MTP MoE from the base model onto the NVFP4 quantization** (the base is
  `ornith-ai/Ornith-1.5-397B`, ≈800 GB in bf16). Its model card reports **41.86 tok/s** on a 4× DGX Spark
  vLLM run and links the full [Spark Arena benchmark](https://spark-arena.com/benchmark/c41b9f16-d269-4dd4-a179-cd2890b5f07c);
  that figure is the `C1 t/s` in our parent table. MIT-licensed, same as the family.
- **Runtime:** vLLM, container `ghcr.io/spark-arena/dgx-vllm-eugr-nightly:latest`. **Unlike the other
  pinned recipes in this registry (and unlike the 35B lane above), this container is *not* digest-pinned** —
  `:latest` is a moving tag, so a future pull can change the engine underneath the recipe. Treat the
  measured 41.86 t/s as tied to whatever the tag resolved to when it was recorded.
- **Loader / engines:** `--load-format instanttensor` via `@eugr/mods/instanttensor-hybrid-draft-loader`,
  `moe_backend: marlin`, `linear_backend: flashinfer_cutlass`, `attention_backend: flashinfer`,
  `kv_cache_dtype: fp8_e4m3`, `performance_mode: throughput`, `mm_encoder_tp_mode: data`.
- **Long context flag:** `VLLM_ALLOW_LONG_MAX_MODEL_LEN: 1` is set, but `max_model_len` is **262144** — the
  native window. The env var only lifts vLLM's refusal to exceed the checkpoint's declared maximum; it does
  not by itself extend context.

## Caveats

### The YaRN long-context route is documented upstream but not shipped here

Both model cards describe extending the native 262,144-token window with **YaRN RoPE scaling** — factor
4.0 → roughly 1M tokens — via either the checkpoint's `config.json` or a launch-time override
(`--hf-overrides` on vLLM, `--json-model-override-args` on SGLang, each gated by the engine's
"allow longer context" env var). **Neither recipe in this directory enables it.** The upstream caveat is
worth repeating: open-source runtimes apply YaRN *statically*, so the factor is in force for every request
and can erode quality on ordinary-length inputs — enable it only when a workload genuinely needs the
window, and size the factor to it. If you add YaRN here, that is new, quality-unverified territory; there
is no needle-in-a-haystack evidence for Ornith in this registry.

### `@eugr/mods/drop-caches` is inert under a default launch

Every Ornith recipe — the two shipped here and the three archived — lists `@eugr/mods/drop-caches`. Per
[`mods/drop-caches/README.md`](../../mods/drop-caches/README.md) that upstream mod **silently does nothing**:
its background loop keeps the process "alive" so it reads as success, but under sparkrun's default rootless
launch `/proc/sys` is mounted read-only (the write fails), and its command has a redirect-order bug that
sends the value to its log file instead of `/proc/sys/vm/drop_caches`. It has been left in place rather than
silently rewritten; the fixed, fail-closed replacement is the in-registry
[`@littlecedar/mods/drop-caches`](../../mods/drop-caches/README.md), which additionally requires a
`--rootful` (privileged) launch to work at all.

### The 397B container tag floats

Called out above: `ghcr.io/spark-arena/dgx-vllm-eugr-nightly:latest` is the one unpinned container in the
Ornith lane. A digest pin would make the 41.86 t/s reproducible.

### No guard suite for this lane

The registry conventionally backs each lane with a `tests/test_<lane>_recipes.py` guard file
(`test_ds4_recipes.py`, `test_ifm_recipes.py`, and siblings). **There is no `tests/test_ornith_recipes.py`.**
Nothing here is mechanically enforced beyond `sparkrun recipe validate`; edits to these recipes get no
regression coverage.

## Archived recipes

Three Ornith recipes were moved to [`attic/ornith/`](../../attic/ornith/) (commit `e0633ed`) and are **not**
part of the shipped surface:

- A `littlecedar-ornith-1.5-397b-*` b12x fork of the 397B vLLM recipe — an earlier variant carrying
  `CUTE_DSL_ARCH` and other b12x env switches, tagged `broken` in its metadata.
- `ornith-1.5-35b-a3b-nvfp4-vllm.yaml` and `ornith-1.5-35b-a3b-nvfp4-vllm-b12x.yaml` — vLLM arms for the
  35B. The registry carries **no measured figure** for either, and the DFlash2 draft is an
  SGLang-targeted artifact (its card only documents SGLang usage), so the shipped 35B recipe is the
  SGLang one; the vLLM arms are retained as provenance, not as a benchmarked comparison.

They are kept as provenance; the b12x API surfaces they referenced are not covered by any current guard.

## Validation

```bash
H="$PWD/.local/sparkrun-home"
HOME="$H" sparkrun recipe validate recipes/ornith/ornith-1.5-35b-a3b-nvfp4-dflash2-sglang.yaml
HOME="$H" sparkrun recipe validate recipes/ornith/littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm.yaml
```

Both recipes validate clean. See [`AGENTS.md`](../../AGENTS.md) for the full run/lint/benchmark workflow.

## References

- Ornith 1.5 announcement — <https://ornith.ai/ornith_1_5.html>
- DFlash 2 — [Keep Drafting Parallel](https://inco.ai/blog/dflash2/) · [DFlash: Block Diffusion for Flash Speculative Decoding](https://arxiv.org/abs/2602.06036)

<!-- Links -->
[model-35b]: https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B-NVFP4
[model-397b-graft]: https://huggingface.co/littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft
[draft-dflash2]: https://huggingface.co/jzinno/Ornith-1.5-35B-A3B-DFlash2