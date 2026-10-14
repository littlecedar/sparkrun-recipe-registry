# Ornith lane — `recipes/ornith/`

Serving recipes for **Ornith 1.5**, the self-improving agentic-coding model family from the
[Ornith Team](https://ornith.ai/ornith_1_5.html), on NVIDIA DGX Spark (GB10, SM121, 128 GB
unified LPDDR5X per node, 200 GbE ConnectX-7 RoCE). This directory is the `ornith` lane; it
ships **three** recipes, one per model scale:

| Recipe                                            | Scale | Runtime | Nodes (TP) | C1 t/s |  Size |  Mem | Flags  | Model Cards                                                                                 |
|:--------------------------------------------------|:------|:--------|:-----------|-------:|------:|-----:|:-------|:--------------------------------------------------------------------------------------------|
| `littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm.yaml` | 397B | vLLM | 4 (TP=4) |  41.86 | 235GB | 0.80 | 🌲👀🧠🦾🔧     | [Model][model-397b-graft]                                                                   |
| `ornith-1.5-35b-a3b-nvfp4-dflash2-sglang.yaml`    | 35B-A3B | SGLang | 1 (TP=1) |    100 |  45GB | 0.85 | ✨🚀🌲👀🧠🦾🔧 | [Model][model-35b] · [Draft][draft-dflash2]                                                 |
| `ornith-1.5-9b-nvfp4-dflash-sglang.yaml`          | 9B | SGLang | 1 (TP=1) |     55 |  11GB | 0.85 | ✨🚀🤏👀🧠🦾🔧     | [Model][model-9b] · [Draft][draft-9b]                                                       |

`C1 t/s` is single-stream decode as recorded in the parent [`recipes/README.md`](../README.md);
`Size` is the per-node footprint the registry records and `Mem` is the recipe's
`gpu_memory_utilization`. Flags are defined in [Model Flags](../README.md#model-flags). A dash is
an **unmeasured** arm, not a zero. All three recipes are `sparkrun recipe validate`-clean.

Ornith 1.5 is a **reasoning model** — assistant turns open with a ` thinking … </think>` block and
tool calls are Qwen-style XML — so all three recipes wire the `qwen3` reasoning parser and a Qwen
tool-call parser (`qwen3_coder` on SGLang, `qwen3_xml` on vLLM), surfacing the chain-of-thought as
`reasoning_content` and tool calls as OpenAI `tool_calls`. Recommended sampling (model card):
`temperature=0.6`, `top_p=0.95`, `top_k=20` for general use, `temperature=1.0` to reproduce the
reported benchmark numbers. The 262,144-token native context is served as-is; the model card's YaRN
long-context override is **not** in any shipped recipe (see [Lane caveats](#lane-caveats)).

Lane state, knob rationale, negative results, measurement histories, boot receipts and the
archived arms live in [`../../attic/ornith/`](../../attic/ornith/) — see [Attic index](#attic-index).

## Contents

- [`littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm`](#littlecedar-ornith-15-397b-nvfp4-mtp-graft-vllm) — flagship 397B MoE, 4 nodes TP=4 (vLLM)
- [`ornith-1.5-35b-a3b-nvfp4-dflash2-sglang`](#ornith-15-35b-a3b-nvfp4-dflash2-sglang) — 35B-A3B MoE, the fast single-Spark lane (SGLang)
- [`ornith-1.5-9b-nvfp4-dflash-sglang`](#ornith-15-9b-nvfp4-dflash-sglang) — small dense 9B single-Spark arm (SGLang)
- [Lane caveats](#lane-caveats)
- [Attic index](#attic-index)

### littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm

| | |
|---|---|
| recipe | `littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm.yaml` |
| runtime / container | vLLM — `ghcr.io/spark-arena/dgx-vllm-eugr-nightly@sha256:b94ac8ac47603f9c3d14f88c12b90eacbc37c7a42f922631cb8c9ac80f7b37c3` (digest-pinned; tag `nightly-20260913`, vLLM `0.29.1rc1.dev17+gd2d649e67`) |
| model | [littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft] — a Little Cedar derivative that **grafts the BFP16 MTP MoE from the base model onto the NVFP4 quantization** (the base is `ornith-ai/Ornith-1.5-397B`, ≈800 GB in bf16) |
| nodes / TP | 4 nodes, `tensor_parallel: 4` + `--enable-expert-parallel` |
| size / mem | **235 GB per node** at `gpu_memory_utilization: 0.80`; `max_model_len: 262144`; `max_num_seqs: 12`; `kv_cache_dtype: fp8_e4m3` |
| spec decode | MTP — the checkpoint's own head, `num_speculative_tokens: 3` |
| flags | 🌲👀🧠🦾🔧 |
| decode C1 | card **41.86 t/s**; house **42.55 t/s** @ d0 (σ 2.78) / **38.48** @ d8192 (σ 1.91), accept len 2.68–3.06 |
| licence | MIT (same as the family) |

**The speculative config is a declared default, not inline JSON — keep it that way.**
`defaults.speculative_config` holds the whole `--speculative-config` JSON and `command:` renders it
as `--speculative-config '{speculative_config}'`. Two things depend on it **not** being inlined
back into `command:`: (a) `-o speculative_config={...}` only reaches a *declared* default, so the
MTP↔DFlash method swap is a one-knob override — inline JSON makes it a silent no-op; and (b)
sparkrun reads the draft model+revision **out of that default**
(`runtimes/_vllm_common.py::detect_spec_config_draft`) to distribute the draft to all four nodes, so
an inline JSON leaves a DFlash draft undistributed (`Revision Not Found` at serve). The vendor's own
DFlash head (`ornith-ai/Ornith-1.5-397B-DFlash`, `db9c35a0…`) is therefore a **documented one-knob
alternative**, not a recipe — measured 2026-10-14 it **loses ~12%** at both depths despite a higher
acceptance length, and it disables prefix-cache reuse on the hybrid-Mamba target. The DFlash arm is
exactly:

```bash
sparkrun benchmark performance <recipe> -H <4 nodes> --profile benchmarking/decode-triage.yaml \
  --output ~/benchmarks/ornith-397b-ab-<date>/armDFlash.json \
  -o 'speculative_config={"method":"dflash","model":"ornith-ai/Ornith-1.5-397B-DFlash","revision":"db9c35a091e89f942c609880f98bb385019dc4f8","num_speculative_tokens":8}'
```

The draft revision is pinned **inside that JSON** (vLLM's own `revision` field), never via
`model_revision:` — that SHA does not exist in the target repo.

**Engine flags.** `--load-format instanttensor` (via `@eugr/mods/instanttensor-hybrid-draft-loader`)
— `instanttensor` is **not** a separate on-disk format, vLLM maps it to the default safetensors
loader. `moe_backend: marlin`, `linear_backend: flashinfer_cutlass`, `attention_backend: flashinfer`,
`mm_encoder_tp_mode: data`. `VLLM_ALLOW_LONG_MAX_MODEL_LEN: 1` is set, but `max_model_len` stays at
the native **262144** — the env var only lifts vLLM's refusal to exceed the checkpoint's declared
maximum; it does not by itself extend context.

**Launch caveat — the container is digest-pinned on purpose.** The bare `:latest` tag served **three
different builds** across the four serving nodes on 2026-10-14, so a four-node TP=4 launch on the
bare tag is **not one engine** (a same-window A/B would compare builds). The recipe pins the build
the head already held, distributed uniformly to all four nodes; any bump must be re-distributed and
re-verified. The loader mod (`instanttensor-hybrid-draft-loader`, `auto` mode) only rewrites the
*draft* loader when the draft and target share a repo+revision (the MTP case); for the DFlash A/B it
returns the run's own loader, i.e. the standard safetensors path.

### ornith-1.5-35b-a3b-nvfp4-dflash2-sglang

| | |
|---|---|
| recipe | `ornith-1.5-35b-a3b-nvfp4-dflash2-sglang.yaml` |
| runtime / container | SGLang — `lmsysorg/sglang:dev-cu13@sha256:9a352a35c973a2357372e85f3bcb5388b6b3c46c1329165987260f3b089647dc` (digest-pinned) |
| model | [ornith-ai/Ornith-1.5-35B-A3B-NVFP4] — NVFP4 (`modelopt` mixed precision: FP8 on attention / linear-attention projections, W4A16_NVFP4 on experts and `lm_head`); `model_type: qwen3_5_moe`, 40 layers, `full_attention_interval: 4`, 256 experts top-8, `max_position_embeddings: 262144` |
| checkpoint pin | `model_revision: 94e431d9cc47fa1986a7a1a4e9a80f7f118b03aa` (the engine is offline, so `--revision {model_revision}` is required) |
| draft | [jzinno/Ornith-1.5-35B-A3B-DFlash2] — DFlash2 spec decode, 4 draft tokens; pin `speculative_draft_model_revision: 9b4852c05fd00b672b7434b1bb105bc03c8682b0` |
| nodes / TP | 1 node, `tensor_parallel: 1` |
| size / mem | 45 GB footprint at `gpu_memory_utilization: 0.85`; `max_model_len: 262144`; `max_num_seqs: 48`; `kv_cache_dtype: fp8_e4m3`; `chunked_prefill_size: 4096` |
| flags | ✨🚀🌲👀🧠🦾🔧 |
| decode C1 | **99.6 t/s** @ d0 (σ 9.1) / **100.2** @ d8192 (σ 3.9), accept len mean 2.54 |
| quality | 37/37 house battery (19/19 easy + 18/18 hard) |
| licence | MIT (checkpoint; the NVFP4 export is MIT) |

**The pinned draft needs a `refs/main` seed.** `speculative_draft_model_revision` is a
**distribution-only** key — SGLang has no serve flag for the draft head, so it never reaches the
serve line. But sparkrun fetches a SHA-pinned draft *without writing a `refs/` entry*, and SGLang's
offline draft-config lookup resolves only `refs/main`, so a pinned draft dies at startup with
`LocalEntryNotFoundError`. The recipe carries a `pre_exec` hook that writes the draft's `refs/main`
before the serve command (attic `AGENTS.md` §3.12) — **do not remove it while the pin stands**.

**`mamba_full_memory_ratio: 3.51`** with `mamba_ssm_dtype: bfloat16` and
`mamba_radix_cache_strategy: extra_buffer_lazy`. 3.51 is a **house value copied across lanes, not a
value derived from this checkpoint** — the qwen3 lane's worklog flags it as a shared default with no
recorded rationale. It reallocates the leftover pool heavily toward linear-attention (GDN) state;
the concurrency consequence is a `max_mamba_cache_size` question. `max_num_seqs: 48` is the
admission cap, but on this stack the *effective* ceiling can be the mamba state pool, not the
literal — read the grant from the serve log.

**`served_model_name` is a literal, never `{model}`.** sparkrun rebinds `{model}` to the prepared
snapshot path on a real launch, so the engine would advertise a `/cache/…` path as its model id
(`-n` does not show this). The recipe declares `served_model_name: ornith-ai/Ornith-1.5-35B-A3B-NVFP4`.

**Spec decode is user-visible in the log:** check `Mean acceptance length > 1` on `Decode batch`
lines. A DFlash2 boot that serves but accepts ≈1 token/step is a misconfiguration, not a win.

**Honed chat template.** The lane serves a community-honed template (`qwen3.8-honed-v22.5.1`,
30,438 B) staged by `@littlecedar/mods/ornith-honed-chat-template` under
`/cache/runtime/ornith-honed-chat-template/` and read via `--chat-template`. **Never inject it into
the HF snapshot** — sparkrun validates every cached model file against a hub manifest and an
injected snapshot fails `wrong_size` at distribution.

**Launch caveat.** `@eugr/mods/drop-caches` is inert here (see [Lane caveats](#lane-caveats)); the
`@littlecedar/mods/pip-install-fastsafetensors` mod supplies `--load-format fastsafetensors`.

### ornith-1.5-9b-nvfp4-dflash-sglang

| | |
|---|---|
| recipe | `ornith-1.5-9b-nvfp4-dflash-sglang.yaml` |
| runtime / container | SGLang — `lmsysorg/sglang:dev-cu13@sha256:9a352a35c973a2357372e85f3bcb5388b6b3c46c1329165987260f3b089647dc` (digest-pinned) |
| model | [ornith-ai/Ornith-1.5-9B-NVFP4] — 8.8 GB of weights, dense ~9B, multimodal; `model_revision: 155f200d85ad58464571c77d5e1122ea5d419d7b` |
| draft | [ornith-ai/Ornith-1.5-9B-DFlash] — first-party plain `DFlashDraftModel` (hidden-state taps 1/5/9/…/29 of the 32-layer target), 8 draft tokens, **deliberately unpinned** |
| nodes / TP | 1 node, `tensor_parallel: 1` |
| size / mem | 11 GB footprint at `gpu_memory_utilization: 0.85`; `max_model_len: 262144`; `max_num_seqs: 48`; `kv_cache_dtype: fp8_e4m3`; `chunked_prefill_size: 4096` |
| flags | ✨🚀🤏👀🧠🦾🔧 |
| decode C1 | **~52–59 t/s** (52–57 cold / 54–59 warm), accept len mean 3.35 |
| quality | 37/37 house battery (19/19 easy + 18/18 hard) |
| licence | MIT |

**No `mamba_*` keys and no `moe_runner_backend`, unlike the 35B arm — deliberate.** The MoE knob is
inert (the checkpoint is dense). The `mamba_*` trio is left to the engine defaults rather than
imported: the 35B's `mamba_full_memory_ratio: 3.51` is a house value copied across lanes with no
recorded derivation, and this first arm should not inherit an unmeasured traffic assumption.
Measured 2026-10-14, the hybrid state pool does **not** clamp the admission cap
(`max_running_requests=48`, `max_mamba_cache_size=273`).

**The card's `--speculative-dflash-block-size 8` is spelled via its upstream alias**
(`--speculative-num-draft-tokens`), the spelling the shipped 35B arm is boot-proven on; sparkrun has
no map key for the dflash spelling. The mismatch against the draft's `block_size: 16` is
**warning-only** (`DFLASH block size mismatch: using speculative_num_draft_tokens=8 but draft config
block_size=16`).

**The draft repo is deliberately left unpinned**, like the 35B sibling's jzinno draft: a SHA-keyed
fetch writes no `refs/` entry, and SGLang's offline draft-config lookup resolves only `refs/main`,
so a pinned draft dies at startup with `LocalEntryNotFoundError`. Pin, if ever, only after
re-checking this.

**It ships its own multimodal chat template**, not the 35B's honed one: the checkpoint's own
`chat_template.jinja` (vision tokens + an `enable_thinking` toggle) is served as-is.

**Launch caveat — client-visible, not a decode loop.** At long context the served default does not
suppress reasoning, so a client with a short `max_tokens` that reads `content` sees empty or partial
replies; the 9B is more prone to this than the 35B. Raise `max_tokens` rather than blaming the arm.

## Lane caveats

- **The YaRN long-context route is documented upstream but not shipped here.** Both model cards
  describe extending the native 262,144-token window with **YaRN RoPE scaling** (factor 4.0 →
  roughly 1M tokens) via `config.json` or a launch-time override (`--hf-overrides` on vLLM,
  `--json-model-override-args` on SGLang, each gated by the engine's "allow longer context" env
  var). **None of the shipped recipes enable it.** Open-source runtimes apply YaRN *statically*, so
  the factor is in force for every request and can erode quality on ordinary-length inputs; enable
  it only when a workload genuinely needs the window. If you add YaRN here, that is new,
  quality-unverified territory.
- **`@eugr/mods/drop-caches` is inert under a default launch.** Every Ornith recipe lists it, but per
  [`mods/drop-caches/README.md`](../../mods/drop-caches/README.md) that upstream mod **silently does
  nothing**: `/proc/sys` is mounted read-only under sparkrun's default rootless launch and its
  command has a redirect-order bug, so nothing in the pipeline clears the page cache for you. The
  fail-closed replacement is [`@littlecedar/mods/drop-caches`](../../mods/drop-caches/README.md),
  which additionally requires a `--rootful` launch.

## Attic index

Everything below is under [`../../attic/ornith/`](../../attic/ornith/) and is the lane's frozen
record: lane state, constraints, guards, measurement histories, negative results and the archived
arms. Cite it rather than this README for anything historical.

| entry | what it holds / what question it answers |
|---|---|
| [`AGENTS.md`](../../attic/ornith/AGENTS.md) | The lane's condensed operating guide moved verbatim from the lane on 2026-10-14 with its `§N` numbering intact — lane state, evidence locations, hard constraints/traps, negative results not to re-derive, quality, open items, the validation ritual and references — plus **the material cut from this README** appended under `## From recipes/ornith/README.md (2026-10-14)`: the model thesis, per-recipe wiring and measurements, the reasoning-loop and long-horizon-agentic investigations, the spec-decode A/B ladders, the caveats and the archived-recipe provenance. Read this before touching a recipe here. |
| [`NOTES.md`](../../attic/ornith/NOTES.md) | One-page, kept-current state-of-play: the three shipped recipes, the cut evidence, cache hygiene, open workstreams, the next-cheapest checks, and the do-not-re-derive list. |
| [`littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm-b12x.yaml`](../../attic/ornith/littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm-b12x.yaml) | Archived arm — an earlier `b12x` fork of the 397B vLLM recipe carrying `CUTE_DSL_ARCH` and other b12x env switches, tagged `broken` in its metadata. Provenance, not a benchmarked comparison; the b12x API surface it referenced is covered by no current guard. |
| [`ornith-1.5-35b-a3b-nvfp4-vllm.yaml`](../../attic/ornith/ornith-1.5-35b-a3b-nvfp4-vllm.yaml) | Archived arm — a 35B vLLM recipe. The registry carries **no measured figure** for it, and the DFlash2 draft is an SGLang-targeted artifact, so the shipped 35B lane is the SGLang one; retained as provenance. |
| [`ornith-1.5-35b-a3b-nvfp4-vllm-b12x.yaml`](../../attic/ornith/ornith-1.5-35b-a3b-nvfp4-vllm-b12x.yaml) | Archived arm — the `b12x` sibling of the 35B vLLM recipe; same status (no measured figure, retained as provenance). |

The three archived recipes were moved to `attic/ornith/` (commit `e0633ed`) and are **not** part of
the shipped surface.

## References

- Ornith 1.5 announcement — <https://ornith.ai/ornith_1_5.html>
- DFlash 2 — [Keep Drafting Parallel](https://inco.ai/blog/dflash2/) · [DFlash: Block Diffusion for Flash Speculative Decoding](https://arxiv.org/abs/2602.06036)

<!-- Links -->
[model-35b]: https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B-NVFP4
[model-397b-graft]: https://huggingface.co/littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft
[model-9b]: https://huggingface.co/ornith-ai/Ornith-1.5-9B-NVFP4
[draft-dflash2]: https://huggingface.co/jzinno/Ornith-1.5-35B-A3B-DFlash2
[draft-9b]: https://huggingface.co/ornith-ai/Ornith-1.5-9B-DFlash
