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

`C1 t/s` is single-stream decode as recorded in the parent [`README.md`](../../README.md);
`Size` is the per-node footprint the registry records and `Mem` is the recipe's
`gpu_memory_utilization`. Flags are defined in [Model Flags](../../README.md#model-flags). A dash is
an **unmeasured** arm, not a zero. All three recipes are `sparkrun recipe validate`-clean.

A **fourth** arm, [`ornith-1.5-35b-a3b-nvfp4-yarn-1m-sglang`](#the-yarn-1m-arm), serves the same 35B
checkpoint at the model card's **YaRN long-context route** (~1M-token window, no draft). It is
**built, not booted** — no C1, no house battery, no needle receipt — so it holds no row in the table
above and no index row in the parent; the arm, the memory consequence and the pre-registered needle
gate are in its own section below.

Ornith 1.5 is a **reasoning model** — assistant turns open with a ` thinking … </think>` block and
tool calls are Qwen-style XML — so all three recipes wire the `qwen3` reasoning parser and a Qwen
tool-call parser (`qwen3_coder` on SGLang, `qwen3_xml` on vLLM), surfacing the chain-of-thought as
`reasoning_content` and tool calls as OpenAI `tool_calls`. Recommended sampling (model card):
`temperature=0.6`, `top_p=0.95`, `top_k=20` for general use, `temperature=1.0` to reproduce the
reported benchmark numbers. The three shipped recipes serve the 262,144-token native context as-is;
the card's YaRN long-context override is served **only** by the boot-pending 1M arm (see
[Lane caveats](#lane-caveats)).

Lane state, knob rationale, negative results, measurement histories, boot receipts and the
archived arms live in [`../../attic/ornith/`](../../attic/ornith/) — see [Attic index](#attic-index).

## Contents

- [`littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm`](#littlecedar-ornith-15-397b-nvfp4-mtp-graft-vllm) — flagship 397B MoE, 4 nodes TP=4 (vLLM)
- [`ornith-1.5-35b-a3b-nvfp4-dflash2-sglang`](#ornith-15-35b-a3b-nvfp4-dflash2-sglang) — 35B-A3B MoE, the fast single-Spark lane (SGLang)
- [`ornith-1.5-9b-nvfp4-dflash-sglang`](#ornith-15-9b-nvfp4-dflash-sglang) — small dense 9B single-Spark arm (SGLang)
- [The YaRN 1M arm](#the-yarn-1m-arm) — the card's long-context route on the 35B, **built and not booted**
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
| license | MIT (same as the family) |

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

**Serving notes moved from the recipe comments (2026-10-14).** The checkpoint is multimodal
(image-text-to-text) and is served with no `--limit-mm-per-prompt` cap; the vision encoder uses
`--mm-encoder-tp-mode data`. The `--speculative-config` JSON carries **literal** values — a nested
`{max_model_len}` inside a default is *not* substituted (the render is a single pass over `command:`)
— and must keep its shell single quotes (the JSON holds double quotes).

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
| decode C1 | **100.8 t/s** @ d0 (σ 12.1, n=5) — 2026-10-15, accept len mean 2.94; prior 99.6 (2026-10-13, σ 9.1) / 100.2 @ d8192 (σ 3.9) |
| decode C2 · C5 · C10 | **158.2 · 220.4 · 249.9 t/s** @ d0 (σ 6.2 / 10.0 / 4.6, n=5) |
| quality | 37/37 house battery (19/19 easy + 18/18 hard, 0 flakes); needle **32k 3/3 · 128k 3/3 · 262k 3/3**; gsm8k **88.5%** (177/200), arc **93.0%** (186/200), 0 empty / 0 truncated |
| tool calls | BFCL v3 **86.9%** (1078/1240, 5 AST categories, 0 transport errors); tool-eval-bench **100** (15/15 core, ref `v2.6.0`) |
| standard pass | 2026-10-15, `.34`, one boot — receipts `~/benchmarks/ornith-35b-suite-20261015/`: `summary.json` (quality), `hard/` (gsm8k/arc), `perf-ladder.yaml` (bench `bench_8c7486cad451`), `teb.yaml` (bench `bench_6b5b53dd4efb`), `serve.log`, `launch.log` |
| standard pass (2026-10-16) | Re-run, one boot on `.34`, three legs — receipts `~/benchmarks/ornith-35b-suite-20261016/`: eval-suite 1.0.1 verdict **ok** (contract ok; house **37/37** = easy 19/19 + hard 18/18; needle **3/3 at each of 32k / 131k / 262k**, the top rung at 256,394-token prompts, 142.5–142.9 s per probe); ladder **C1 101.8 ± 8.7 · C2 153.1 ± 6.4 · C5 217.4 ± 10.0 · C10 244.2 ± 3.2 t/s** @ d0 (per-stream 101.8 / 79.8 / 54.5 / 34.2, ttfr 303 / 582 / 1208 / 1973 ms); tool-eval-bench v2.6.0 **100** (15/15 pass, 0 partial, 0 fail; deployability 95, responsiveness 83). Reproduces the 2026-10-15 pass. |
| license | MIT (checkpoint; the NVFP4 export is MIT) |

**The 2026-10-15 standard pass is the lane's first tool-call and concurrency measurement.** One boot,
three legs, `benchmarking/concurrency-ladder.yaml` at d0 (5 runs/cell) and
`benchmarking/standard-suite.yaml` (core 15, greedy); decode-phase rows only, ttfr 296 / 579 / 1199 /
1959 ms at c1/c2/c5/c10. Boot facts from the serve log: `max_running_requests=48`,
`max_mamba_cache_size=632` — the hybrid state pool does **not** clamp the admission cap here (the 9B
sibling granted 273); `max_total_num_tokens=1172758`; accept len mean **2.94** over 2245 decode
batches (min 1.57, max 3.85), 2.94 at c1 and 2.51 at c10, i.e. spec decode engaged throughout. The
`DFLASH block size mismatch` warning (4 draft tokens vs the draft's `block_size: 16`) is the
documented warning-only mismatch. Two things are worth knowing about the receipts: the suite's own
`hard` axis **errored on an instrument flag** (`--hard-bench gsm8k,arc` is not a valid
`run_benchmarks.py --bench` choice; `--bench` takes one of `house|gsm8k|arc|all`), so the suite exits
1 and its `hard` verdict is an artifact defect, not a model result — the two benchmarks were re-run
by hand on the same boot into `hard/` with the suite's other parameters (limit 200, seed 1234,
thinking off); and the 262k needle depth passed **3/3** here against 2/3 on 2026-10-14 (that miss was
a completion-budget artifact).

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
30,438 B) staged by `recipes/ornith/mods/ornith-honed-chat-template` under
`/cache/runtime/ornith-honed-chat-template/` and read via `--chat-template`. **Never inject it into
the HF snapshot** — sparkrun validates every cached model file against a hub manifest and an
injected snapshot fails `wrong_size` at distribution.

**Launch caveat.** `@eugr/mods/drop-caches` is inert here (see [Lane caveats](#lane-caveats)); the
`@littlecedar/mods/pip-install-fastsafetensors` mod supplies `--load-format fastsafetensors`.

**Serving notes moved from the recipe comments (2026-10-14).** The checkpoint is Qwen3.5-MoE
multimodal (image-text-to-text; config carries a `vision_config` and image/video token ids) and is
served with no `--limit-mm-per-prompt` cap.

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
| decode C2 · C5 · C10 | **101.1 · 159.0 · 148.9 t/s** @ d0 (σ 8.3 / 7.8 / 4.8, n=5) — same-boot C1 **58.0** (σ 8.8); bench `bench_92725c90d298` |
| standard suite (2026-10-18) | 5/5 legs `ok` — contract `ok` (`max_model_len=262144`, ready, finish `stop`), house **37/37**, needle **3/3** @32k · 131,072 · 262,144, arc **91.5 %** / gsm8k **92.5 %** (n=200 each, every reply `finish=stop`, empty 0), bfcl **88.1 %** (1092/1240), 0 transport errors — receipt `~/benchmarks/ornith-9b-suite-20261018/` |
| license | MIT |

**Concurrency ladder, 2026-10-15 (`.34`, one fresh boot, `benchmarking/concurrency-ladder.yaml`, d0,
5 runs/cell, decode-phase rows only).** The C1 headline is confirmed on this boot at **58.0 t/s**
(σ 8.8) and the curve climbs to **101.1 / 159.0 t/s** at c2/c5 before **148.9** at c10 — a ~6%
inversion at the top of the ladder. That is **inside the profile's stated 7–25% inter-boot noise
floor**, and no same-window control boot was run for this arm, so the honest reading is a
*plateau at c5–c10*, not a knee; a single window cannot resolve anything under ~7%. ttfr 535 / 1016
/ 2292 / 3863 ms; TTR port 206.2 s / HTTP 220.7 s (cold — the boot had just distributed 8.24 GiB of
weights + 2.41 GiB of draft). Receipts `~/benchmarks/ornith-9b-ladder-20261015/` (`launch.log`,
`perf-ladder.yaml|json|csv`, bench `bench_92725c90d298`). Two receipt caveats worth knowing: a
benchmark-owned launch (no `--skip-run`) **stops its own serve on completion**, so the container's
serve log — the only place the engine's admission/mamba grants appear — died with it and this boot's
`max_running_requests` / `max_mamba_cache_size` are **not** in the receipt (the arm's grant record
therefore stays the 2026-10-14 reading, 48 / 273 on `.30`); and re-running the same
recipe+profile+args does **not** re-measure — sparkrun finds the completed `bench_*` state and
re-emits the recorded numbers ("no requests will be sent"; `--fresh` is required to measure again).

**The suite ran on its own boot, so it does not share a window with the ladder above.** That boot
allocated a 1,563,690-token fp8 KV pool with `max_running_requests=48` (unclamped — the hybrid state
pool is not the admission cap here either). No ladder was re-taken on it, and this doc does not pair
its quality figures with the 2026-10-15 speed cells.

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

**Serving notes moved from the recipe comments (2026-10-14).** The checkpoint is Qwen3.5 multimodal
(image-text-to-text) and is served with no `--limit-mm-per-prompt` cap. `kv_cache_dtype: fp8_e4m3` is
safe to spell: the checkpoint's `hf_quant_config` ships `kv_cache_quant_algo: FP8`, so the literal and
the checkpoint agree (an `auto` resolves silently). `moe_runner_backend` is meaningless here (dense
MLP, no experts), and the `mamba_*` trio would apply (the checkpoint *is* a hybrid GDN model) but is
deliberately left to engine defaults.

## The YaRN 1M arm

SGLang · **1 node (TP=1)** · built 2026-10-15 · **boot pending — nothing measured, no index row yet**.

| | |
|---|---|
| recipe | `ornith-1.5-35b-a3b-nvfp4-yarn-1m-sglang.yaml` |
| runtime / container | SGLang — the same digest-pinned `lmsysorg/sglang:dev-cu13@sha256:9a352a35c973a2357372e85f3bcb5388b6b3c46c1329165987260f3b089647dc` as the 35B sibling (sglang v0.5.18 — §9 of the attic carries the derivation and the source citations) |
| model | [ornith-ai/Ornith-1.5-35B-A3B-NVFP4] — the 35B checkpoint the sibling serves, at the same pin `94e431d9cc47fa1986a7a1a4e9a80f7f118b03aa` (Hub `main`, 2026-08-26) |
| window | `max_model_len: 1000000`, the card's number; the YaRN factor-4.0 route reaches 4 × 262,144 = 1,048,576 positions, so nothing above that is left |
| flags | ✨🚚👀🧠🦾🔧 — **no** 🚀 (no measured C1) and **no** 🌲 (the arm has to earn it) |
| draft | **none** — deliberate, see below |
| status | `validate`-clean; `sparkrun run … -n` renders; **no boot, no C1, no house battery, no needle receipt** |
| license | MIT (same checkpoint as the sibling) |

**The route is the model card's, not ours.** Both Ornith 1.5 cards publish it; the 35B card, verbatim:
Ornith "handles context windows of up to 262,144 tokens. When a task's combined input and output must
go beyond this limit, we suggest extending the effective window with RoPE scaling — YaRN is the
technique we validate against … With a scaling factor of 4.0, the usable window grows to roughly 1M
tokens", switched on either in the checkpoint's `config.json` or at launch (SGLang:
`SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN=1 … --json-model-override-args '{"rope_scaling": {…}}'
--context-length 1000000`). The card also carries the warning that makes this an arm rather than a
default: *"Open-source runtimes implement YaRN statically: the same scaling factor is applied to every
request regardless of its length, which can slightly hurt quality on ordinary-length inputs."*

**The card's `rope_scaling` spelling is not the one this checkpoint/engine honours — the override has
to nest and be complete.** The checkpoint keeps its rope config at `text_config.rope_parameters`
(`rope_type: default`, `rope_theta: 1e7`, `partial_rotary_factor: 0.25`, `mrope_section: [11, 11, 10]`,
`mrope_interleaved: true`), sglang v0.5.18 reads `hf_text_config.rope_parameters` first
(`configs/model_config.py:328-330`), and the override replaces that dict wholesale
(`utils/hf_transformers/config.py:266-275` → `PretrainedConfig.update`, a `setattr` loop). So the arm
sends `{"text_config": {"rope_parameters": {"rope_type": "yarn", "factor": 4.0,
"original_max_position_embeddings": 262144, "rope_theta": 10000000, "partial_rotary_factor": 0.25,
"mrope_section": [11, 11, 10], "mrope_interleaved": true}}}` — restating the mrope keys is not
cosmetic: `model_config.py:332-336` derives `model_is_mrope` from `mrope_section` being present, so
dropping them moves this multimodal checkpoint onto the plain-RoPE path. The same fleet measured the
silent failure this avoids (qwen4, 2026-10-04: a flat form leaves `rope_type: default`). The
`SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN=1` env is **load-bearing, not advice**: this build
*raises* `ValueError` above the derived 262,144 (`model_config.py:819-843`) rather than warning.

**Memory — a 1M window on 128 GB is pool-bound, and the pool already covers it.** KV costs
`2 (K,V) × num_key_value_heads × head_dim × bytes` over the **full-attention layers only**: this
hybrid checkpoint is 40 layers with `full_attention_interval: 4` (30 GDN + 10 full attention),
2 KV heads, `head_dim` 256, so fp8 KV is **10,240 B/token (10.0 KiB)** and a 1M-token request needs
**~10.0 GiB**. The lane's recorded 262k boot (2026-10-15, `.34`, mem-fraction 0.85) allocated a pool
of **1,172,758 tokens** — K 5.59 GiB + V 5.59 GiB, which is that same 10,235 B/token to 0.05% — so
**one full-window stream plus ~124k tokens of completion fits, with ~11.8% headroom**, and raising
the window costs no memory change (the pool is sized from free memory, not from `--context-length`).
What the arm *grants* is that pool, read from its own serve log (`max_total_num_tokens`), not the
window flag — a busier node grants less. Do **not** quote sparkrun's own dry-run estimate here: it
reports `KV demand 38.1 GiB` / `~2.27M tokens` because it assumes every one of the 40 layers caches
the full window.

**No draft, deliberately.** The sibling's `jzinno/Ornith-1.5-35B-A3B-DFlash2` head is a 262,144-window
artifact (`max_position_embeddings: 262144`, `rope_type: default`, sliding window 4096), and SGLang has
no per-draft rope override, so above 262,144 it would be scored at positions it was never trained for
— and at ≈1 accepted token/step it costs throughput instead of adding it. SGLang's own model config
only special-cases a draft as the *shorter* model (`model_config.py:834-840`), and another vendor's
DFlash2+YaRN arm (the drowzeys Qwen3.8-27B "1M Context YARN" overlay, which the `cybersec` lane
serves) says the same thing in its own docs: *"the 1M YaRN seat needs a rope override and no draft"*.
Dropping it also isolates the arm's real question — does YaRN hold above 262,144 — from a confound.
Cost: plain decode (~34 t/s by the sibling's own 100.8 t/s ÷ acceptance 2.94), which is the right
trade for a depth arm. The 262k sibling keeps DFlash2 and its ~100 t/s.

**What a boot must prove (pre-registered gate).** One boot, `tools/needle-haystack.py`, depths
`10,50,90`, seed 1234, 64-token budget — the shape the lane's recorded ladders use — at
**512k, 768k and 1M**, plus a **262,144 control rung on the same boot** for the card's
static-YaRN-degrades-ordinary-length warning. A rung passes only if every key is retrieved *and* the
server counts ≥95% of the requested context (`usage.prompt_tokens`), so a short window reports
`TRUNCATED` rather than a false pass; the ladder verdict is the worst rung, exit 0 only on `PASS`.
Then: `GET /v1/models` must read `max_model_len: 1000000`, and the serve log's `max_total_num_tokens`
must exceed the 980k-token prompt the instrument paces to. Cost ≈ 1–2 h (the recorded ladder:
45 s per 128k, 142 s per 256k prefill on this node). Nothing in this section becomes a
lane claim until that receipt exists.

Full provenance — the card quote, the engine citations, the KV table and three open boot
questions — is [`attic/ornith/AGENTS.md`](../../attic/ornith/AGENTS.md) §9.

## Lane caveats

- **The YaRN long-context route is now an arm, and only that arm enables it.** Both model cards
  describe extending the native 262,144-token window with **YaRN RoPE scaling** (factor 4.0 →
  roughly 1M tokens) via `config.json` or a launch-time override (`--hf-overrides` on vLLM,
  `--json-model-override-args` on SGLang, each gated by the engine's "allow longer context" env
  var). The three shipped recipes serve 262,144 as-is; [the 1M arm](#the-yarn-1m-arm) is the only
  recipe that turns it on, and it is **built, not booted** — this lane has **no needle evidence
  above 262,144** (32k 3/3, 128k 3/3 and 262,144 2/3 → 3/3 are all inside the native window).
  Open-source runtimes apply YaRN *statically*, so the factor is in force for every request and can
  erode quality on ordinary-length inputs; enable it only when a workload genuinely needs the
  window, and do not serve the 1M arm until its gate passes.
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
