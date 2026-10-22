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
checkpoint at the model card's **YaRN long-context route** (~1M-token window, no draft). It **boots**
and serves (`max_model_len` 1,000,000, KV pool 1,202,898 tokens), and its pre-registered needle gate is
**5 of 6 rungs PASS — through 768k and at 1M depths 10 % and 50 %; the 1M depth-90 % rung failed twice
the same way** (`RemoteDisconnected` mid-prefill, serve process gone). The arm therefore **ships for
≤768k workloads, with 1M supported to depth 50 %**; the last 10 % of the window is unmeasured, so
depth 90 failure caps the documented depth, not the arm. The gate table, the memory consequence and
what the two crashes do and do not establish are in its own section below.

Ornith 1.5 is a **reasoning model** — assistant turns open with a ` thinking … </think>` block and
tool calls are Qwen-style XML — so all three recipes wire the `qwen3` reasoning parser and a Qwen
tool-call parser (`qwen3_coder` on SGLang, `qwen3_xml` on vLLM), surfacing the chain-of-thought as
`reasoning_content` and tool calls as OpenAI `tool_calls`. Recommended sampling (model card):
`temperature=0.6`, `top_p=0.95`, `top_k=20` for general use, `temperature=1.0` to reproduce the
reported benchmark numbers. The three shipped recipes serve the 262,144-token native context as-is;
the card's YaRN long-context override is served **only** by the ≤768k-capped 1M arm (see
[Lane caveats](#lane-caveats)).

Lane state, knob rationale, negative results, measurement histories, boot receipts and the
archived arms live in [`../../attic/ornith/`](../../attic/ornith/) — see [Attic index](#attic-index).

## Contents

- [`littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm`](#littlecedar-ornith-15-397b-nvfp4-mtp-graft-vllm) — flagship 397B MoE, 4 nodes TP=4 (vLLM)
- [`ornith-1.5-35b-a3b-nvfp4-dflash2-sglang`](#ornith-15-35b-a3b-nvfp4-dflash2-sglang) — 35B-A3B MoE, the fast single-Spark lane (SGLang)
- [`ornith-1.5-9b-nvfp4-dflash-sglang`](#ornith-15-9b-nvfp4-dflash-sglang) — small dense 9B single-Spark arm (SGLang)
- [The YaRN 1M arm](#the-yarn-1m-arm) — the card's long-context route on the 35B; **ships for ≤768k, 1M supported to depth 50 % — the 1M d90 rung failed twice**
- [Lane caveats](#lane-caveats)
- [Attic index](#attic-index)

### littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm

| | |
|---|---|
| recipe | `littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm.yaml` |
| runtime / container | vLLM — `ghcr.io/spark-arena/dgx-vllm-eugr-nightly@sha256:b94ac8ac47603f9c3d14f88c12b90eacbc37c7a42f922631cb8c9ac80f7b37c3` (digest-pinned; tag `nightly-20260913`, vLLM `0.29.1rc1.dev17+gd2d649e67`) |
| model | [littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft] — a Little Cedar derivative that **grafts the BFP16 MTP MoE from the base model onto the NVFP4 quantization** (the base is `ornith-ai/Ornith-1.5-397B`, ≈800 GB in bf16); `model_revision: b4864e44…` (2026-09-04) — our own artifact, so it is pinned like any other installed repo |
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
| runtime / container | SGLang — `lmsysorg/sglang:v0.5.22@sha256:e3a4f06001a29542fc4a8638536d9ffc5eb9c9942b08603c09b19a56eae4a1ae` (digest-pinned to the **published** multi-arch index — `docker buildx imagetools inspect` prints it, it is not a local `docker images` id; bumped from `v0.5.21@b1259f3e…` on 2026-10-22 — §"Engine bump to SGLang 0.5.22") |
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

**MoE backend (2026-10-19, interleaved).** The shipped `moe_runner_backend: flashinfer_cutlass` beats
`marlin` on the ladder: a four-boot interleaved pair (control/marlin/control/marlin) reads C1 94.1-95.0
vs 102.0-104.6 (+9.3 % means) and C2 +3.6 %, but C5 217.3-223.2 vs 198.7-209.9 (−7.2 %) and C10
240.1-244.6 vs 218.6-219.1 (−9.7 %). Marlin shifts the curve toward single-stream; the default stands.
Receipt `~/benchmarks/ornith-marlin-20261019/`; the detail is in the attic.

**Community W4A16 pack (measured 2026-10-19; archived).**
`attic/ornith/ornith-1.5-35b-a3b-nvfp4-w4a16-mtp-sglang.yaml` boots with its in-checkpoint EAGLE head
and reads C1 58.9 / C2 88.9 / C5 143.5 / C10 158.4 t/s @ d0 with house 37/37 — ~40 % below the official
export, so it is archived rather than served. Receipt `~/benchmarks/ornith-r0b0t-20261019/`.

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
| runtime / container | SGLang — `lmsysorg/sglang:v0.5.22@sha256:e3a4f06001a29542fc4a8638536d9ffc5eb9c9942b08603c09b19a56eae4a1ae` (digest-pinned to the **published** multi-arch index — `docker buildx imagetools inspect` prints it, it is not a local `docker images` id; bumped from `v0.5.21@b1259f3e…` on 2026-10-22 — §"Engine bump to SGLang 0.5.22") |
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

SGLang · **1 node (TP=1)** · built 2026-10-15 · **booted 2026-10-18; ships for ≤768k — gate 5 of 6 rungs
PASS (262,144 / 512k / 768k, then 1M at depths 10 % and 50 %), 1M depth 90 % failed twice with the
mechanism unlogged**.

**d90 re-take 2026-10-20: PASS.** Depth 90 % at a 1,000,000-token request retrieved the needle
(1/1 hits), prompt counted **977,975 tokens**, **1,885.7 s**; the serve stayed up afterwards
(`GET /v1/models` 200) and the container was still healthy 34 min after boot. With the failing-boot
capture armed for the whole request — `docker exec <c> tail -F /tmp/sparkrun_serve.log` streamed to
`serve-stream.log` (119,827 B captured) and `docker events --filter event=die` into `docker-events.log`
(empty) — **nothing died and nothing was written**, which is the null result this rung owes rather than
a mechanism: this is now **2 of 2 d90 passes since the two 2026-10-18 exits**, so the exit is
intermittent and still unnamed. Receipt `~/benchmarks/ornith-yarn-d90-20261020/`.

| | |
|---|---|
| recipe | `ornith-1.5-35b-a3b-nvfp4-yarn-1m-sglang.yaml` |
| runtime / container | SGLang — the same digest-pinned `lmsysorg/sglang:v0.5.22@sha256:e3a4f06001a29542fc4a8638536d9ffc5eb9c9942b08603c09b19a56eae4a1ae` as the 35B sibling (a **published** index digest, not a local image id — §"Engine bump to SGLang 0.5.22" carries the derivation and the boot receipt; the 0.5.18/0.5.21 derivations are history) |
| model | [ornith-ai/Ornith-1.5-35B-A3B-NVFP4] — the 35B checkpoint the sibling serves, at the same pin `94e431d9cc47fa1986a7a1a4e9a80f7f118b03aa` (Hub `main`, 2026-08-26) |
| window | `max_model_len: 1000000`, the card's number; the YaRN factor-4.0 route reaches 4 × 262,144 = 1,048,576 positions, so nothing above that is left |
| flags | ✨🚚👀🧠🦾🔧 — **no** 🚀 (no measured C1) and **no** 🌲 (the arm has to earn it) |
| draft | **none** — deliberate, see below |
| status | **boots and serves**: `GET /v1/models` `max_model_len` **1,000,000**, KV pool `max_total_num_tokens` **1,202,898** (earlier boot: 1,203,041), `max_running_requests` 48, 977k-token prompts admitted (≈60 s engine start). Needle gate below: **5 of 6 rungs PASS**, 1M d90 **ERROR ×2 and unmeasured**. Still **no C1** and **no house battery** |
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

**The gate, measured (pre-registered; not re-cut after seeing numbers).** One ladder per boot:
`tools/needle-haystack.py --timeout 3000 --max-tokens 512`, depths 10/50/90, seed 1234. A rung passes
only if every planted key is retrieved *and* the server counts ≥95 % of the requested context
(`usage.prompt_tokens`); a short count is `TRUNCATED` (exit 3), a retrieval miss is `FAIL`.

| rung | requested | depths | fill (`prompt_tokens`) | verdict |
|---|---|---|---|---|
| **262,144 control** | 262,144 | 10 / 50 / 90 | 99.66–99.86 % | **PASS 3/3** — earlier 2026-10-18 run, not re-run on this boot |
| **512k** | 512,000 | 10 / 50 / 90 | ≥95 % on every depth | **PASS 3/3** — same earlier run |
| **768k** | 768,000 | 10 / 50 / 90 | 99.7–99.8 % | **PASS 3/3** — same earlier run |
| **1M · depth 10 %** | 1,000,000 | 10 | **97.74 %** (977,427) | **PASS**, 1,737 s — same earlier run |
| **1M · depth 50 %** | 1,000,000 | 50 | **97.75 %** (977,487) | **PASS**, 1,886 s, key `3881-RAVEN`, `finish_reason: stop` — the 19:57 boot |
| **1M · depth 90 %** | 1,000,000 | 90 | **97.8 %** (977,975) | **PASS on the third attempt** — 1,891 s, key retrieved, `finish_reason: stop` (2026-10-19, pool 1,205,530); the two 2026-10-18 attempts died mid-prefill (`RemoteDisconnected` after 1,246 s and 398 s) |

**Outcome: the gate is 6 of 6 rungs across three boots, and the depth-90 % rung is intermittent, not
broken.** Every rung through 768k passes 3/3, and 1M passes at depth 10 %, 50 % (2026-10-18) and 90 %
(2026-10-19: 97.8 % fill, 1,891 s, key retrieved). The 2026-10-19 pass crossed the same depth in the
same memory regime — 11 GiB available at the end of prefill — that killed the two 2026-10-18 attempts
mid-prefill, so the exit is intermittent and the pre-registered "all three depths PASS at 1M" is met
by one boot while the mechanism behind the two failures remains unlogged. **The arm ships for ≤768k
workloads, with 1M measured through depth 90 % and not claimed to be reliable.**

**What the d90 crashes do and do not establish (retry boot, 2026-10-18, `.34`).** The retry granted
`max_total_num_tokens` **1,202,898** with `available_gpu_mem` 12.55 GB, admitted the 980,633-token
prompt, and had prefilled **43.7 %** of it (551,863 tokens still pending at the last logged chunk,
input throughput 592 t/s) when the serve process exited at 21:01:38 local; the instrument saw
`RemoteDisconnected` 398 s in, against a 3,000 s per-request timeout.

- **Not a host OOM kill.** `earlyoom` samples memory once a second on this node: **11.3 GiB was
  available (9.09 %) through the last whole second**, it logged no kill, and `dmesg` carries no
  OOM-killer record.
- **Not a driver fault that logs.** No `Xid`, `NVRM`, or Oops line appears in `dmesg` at the second.
  The ring buffer's only `NV_ERR_NO_MEMORY` burst is from an earlier, co-tenant-starved boot.
- **Not a client timeout.** The instrument allowed 3,000 s; the request had run 398 s.
- **Named: a serve-side process exit mid-prefill.** The process released ~109 GiB of unified memory
  within 2 s (available 11.3 → 17.8 → 68.0 → 120.5 GiB) and dockerd deleted the container 2 s after
  that, with no HTTP response ever sent. The *mechanism* is **unlogged**: the last serve-log line is a
  normal prefill chunk, and the process's final stderr and its exit code died with the container.
- **`--no-rm` did not preserve it.** The launch passed `--no-rm` and the job record
  (`~/.cache/sparkrun/jobs/dadfb04b5145d956_….yaml`) carries `executor_config.auto_remove: false`, yet
  dockerd handled a task-delete at 21:01:40. Treat these containers as ephemeral and stream the log to
  the host.
- **And one pass, same regime (2026-10-19).** The third attempt (full pool 1,205,530, no co-tenant)
  crossed depth 90 % with the node at **110 used / 11 GiB available** and returned `200 OK`, key
  retrieved — so the exit is intermittent, not a deterministic d90 behaviour. The engine log lives at
  `/tmp/sparkrun_serve.log` **inside** the container (the container's stdout carries only the CUDA
  banner), so harvest it with `docker cp` before any death; `docker events
  --filter event=die --format '… exit={{.Actor.Attributes.exitCode}}'` is the capture that survives a
  task-delete. Receipt `~/benchmarks/ornith-yarn-d90-20261019/`.

The evidence that would name the mechanism: a serve log **streamed** to the host (not copied on a 10 s
interval, which lost the final ≤6 s of prefill plus any traceback) together with the container's exit
code and `OOMKilled` flag, or a `docker events` capture across the death. Receipt:
`~/benchmarks/ornith-yarn-1m-20261018/diag-d90-retry/` (`serve.log`, `metrics.log`, `dmesg.log`,
`journal-crash-window.txt` — the 1 Hz `earlyoom` trace and the `dockerd` task-delete — plus
`sparkrun-job.yaml` and `launch.log`).

**A boot only grants what the node has free.** Four launches of this unchanged recipe on `.34` across
two sessions produced `max_total_num_tokens` of **1,203,041**, **282,227**, **69,281**, and
**1,202,898** — the two middle values while a co-tenant ComfyUI process held ~9.9–13.6 GiB of the
121.7 GiB unified pool; at 69,281 tokens the instrument cannot even send its prompt (HTTP 400, "Input
length (978633 tokens) exceeds the maximum allowed length (69275 tokens)") and every 1M rung reports
`TRUNCATED`. Read the grant from the serve log before starting a ladder — a starved boot is
indistinguishable from a window failure in the verdict. Receipts:
`~/benchmarks/ornith-yarn-d90-20261019/` (the surviving d90 evidence: `needle-d90.json`,
`serve.log` harvested from the container's `/tmp`, `launch.log`, and the death-capture
`events.log`/`mem.log`/`serve-stream.log`) and `~/benchmarks/ornith-yarn-1m-20261018/` — the latter
is **no longer on the head** (checked 2026-10-19, together with `.34` and `.35`), so the 2026-10-18
numbers are carried by this README and `attic/ornith/AGENTS.md`.

Full provenance — the card quote, the engine citations, the KV table and three open boot
questions — is [`attic/ornith/AGENTS.md`](../../attic/ornith/AGENTS.md) §9.

## Engine bump to SGLang 0.5.21 (executed 2026-10-21 — all three arms validated)

**Status: validated on the new digest; the pins are applied.** The register item
(`mad-science/TODO.md`, `## ornith`) closed with this pass: the 35B and 9B arms and the YaRN 1M arm
each booted and passed its gate on `lmsysorg/sglang:v0.5.21`, on a free `.34`/`.35` pair, ~25 min
of serve time plus the YaRN needle ladder. Evidence history lives in
[`attic/ornith/AGENTS.md`](../../attic/ornith/AGENTS.md) §"Engine-bump adjudication".

**Target.** `lmsysorg/sglang:v0.5.21`, index digest
`sha256:b1259f3ea3275f66237c498ea388919729018bc9f01c3d638391e06e2cf3f469` (tag pushed 2026-10-01,
release published 2026-10-02). Multi-arch: the index carries `linux/arm64`
(`sha256:1f176b3a1dd1205d2a462ab80ea9fc17769a32e53cb6f3c690efa2dc2c384977`, 14.8 GB compressed) and
`linux/amd64`, so a GB10 node resolves a native image; the container labels record the upstream
build commit `e00930c5489053f26d86b179cee0d087f846acbb`. The previous pin was
`dev-cu13@sha256:9a352a35…`, a 2026-09-08 arm64 nightly whose serve log reported
`0.0.0.dev1+g20ca564bf` — v0.5.18 plus eight commits. `dev-cu13` has since moved
(`sha256:b0473834763b…`), so the pin was the only build guarantee.

**The recorded blocker never existed at the target release.** The 2026-10-10 scan said the bump
breaks this lane because `mamba_radix_cache_strategy` and `mamba_full_memory_ratio` "were removed
upstream". Both are still declared fields at v0.5.21 (`arg_groups/fields/exec_.py:450-457`,
`arg_groups/fields/schedule.py:214-218`), still register as
`--mamba-radix-cache-strategy` / `--mamba-full-memory-ratio` (`arg_groups/arg_utils.py:290`), and
`extra_buffer_lazy` is still an allowed choice with the DFLASH lazy-verify hook wired explicitly
(`arg_groups/mamba_hook.py:113-120`). sglang#40313 (merged 2026-09-20, shipped in v0.5.21) removed
the *classes* `MambaRadixCache` and `SWARadixCache`, which no recipe or mod imports. LIKELY origin
of the false claim: v0.5.20 moved every field declaration out of `server_args.py` into
`arg_groups/fields/`, so a grep for the flag in `server_args.py` returns nothing at 0.5.20 and 0.5.21
while the flag still works. The boot confirms it: both 35B `--mamba-*` flags and the 9B's
`extra_buffer_lazy`-free defaults served without an argparse error.

**The two named wins, measured.** The DFlash reranker (LiLiCorr, sglang#37462, first release
v0.5.21) does **not** reach this lane: it engages only for a draft checkpoint carrying
`lilicorr_*` geometry in `dflash_config` (`srt/speculative/lilicorr_utils.py:46-52`), and the PR
ships no checkpoints — neither the `jzinno` DFlash2 head nor the first-party 9B DFlash head has one.
The GDN QKV materialization removal (sglang#33778, first release v0.5.21) **does** apply on the
Triton linear-attention verify path (`layers/attention/linear/gdn_backend.py:1019-1022`,
`kernels/gdn_triton.py:44`) these arms resolve to — and **produced no measured gain here**: the
ladders below read at or slightly below the prior bands, never above them. The bump's value is the
refuted blocker (the lane stops depending on a dead-end 2026-09-08 nightly) plus 0.5.21's fixes,
not a throughput win.

**Pin edits (applied to all three recipes, one line each):**

```diff
--- a/recipes/ornith/*.yaml
+++ b/recipes/ornith/*.yaml
@@
-container: lmsysorg/sglang:dev-cu13@sha256:9a352a35c973a2357372e85f3bcb5388b6b3c46c1329165987260f3b089647dc
+container: lmsysorg/sglang:v0.5.21@sha256:b1259f3ea3275f66237c498ea388919729018bc9f01c3d638391e06e2cf3f469
```

`tests/test_ornith_recipes.py` (29 tests) passes unchanged — it asserts a shared digest-pinned
container, not a literal digest.

**Measured 2026-10-21 (receipts `~/benchmarks/ornith-0.5.21-bump-20261021/`).** One serve per arm;
the 35B on `.34` and the 9B on `.35` ran concurrently, then the YaRN arm alone on `.34`.

| arm | boot / grant | quality | ladder @ d0, n=5, vs on-file band |
|---|---|---|---|
| 35B DFlash2 (`.34`) | engine `0.5.21`; HTTP-ready **223.6 s**; `max_running_requests=48`; `max_mamba_cache_size=611` (on file 632, does not clamp); pool **1,125,837** tokens (on file 1,172,758) | contract ok; house **37/37** (19/19 + 18/18); needle **3/3** at 32k / 131k / 262k | C1 **96.5** · C2 **148.3** · C5 **213.9** · C10 **244.1** vs 100.8–101.8 / 153.1–158.2 / 217.4–220.4 / 244.2–249.9 — every cell inside the recorded σ (largest delta −5.2 % at C1, σ 8.7–12.1) |
| 9B DFlash (`.35`) | HTTP-ready **235.7 s**; `max_running_requests=48`; `max_mamba_cache_size=272` (on file 273); pool **1,523,077** tokens | contract ok; house **37/37**; needle **3/3** × 3 | C1 **53.9** · C2 **89.6** · C5 **151.7** · C10 **147.7** vs 52–59 / 101.1 / 159.0 / 148.9 — C1/C5/C10 inside σ; C2 −11.4 %, outside its σ 8.3 |
| YaRN 1M (`.34`) | `context_len=1000000`; pool **1,192,993** tokens (on-file boots 1,202,898–1,205,530); 12.27 GB free | needle **6/6 rungs PASS**: 262k / 512k / 768k **3/3** each; 1M at depths 10 / 50 / 90 % **3/3**, fills **97.74 / 97.75 / 97.80 %** (977,427 / 977,487 / 977,975 tokens) | no C1 and no house battery, by the arm's registered bar |

The 9B C2 cell was re-laddered **on `.34`** — the node the on-file band was measured on — in a
ladder-only boot: C1 **60.6** · C2 **97.8** · C5 **156.1** · C10 **147.8**. C2 is −3.2 % against
101.1 (σ 8.3), so **the .35 reading was a cross-node artifact, not an engine shift**; the flagged
cell clears and the bump is clean on all three arms.

**The 1M depth-90 % intermittent did not reproduce.** The d90 rung passed **on the first attempt**
at 97.80 % fill (on file: two mid-prefill exits, then two passes, all on the old build); the retry
rule was declared before the run and went unused. The streamed serve-log capture
(`arm-yarn/serve-stream.log`, 593 KB) and `docker events --filter event=die` (`docker-events.log`)
were armed for the whole request: no die event except the deliberate `docker stop` at the end
(exit 137), and the serve answered through the rungs. **4 of 4 d90 passes now, on two builds** — the
exit remains unmechanized but has not recurred since the capture was fixed.

Spec decode stayed engaged on both spec arms: 35B accept len **2.52–2.64** (on file mean 2.94), 9B
**2.56–2.59** (on file mean 3.35) — both well above the 1.0 misconfiguration mark, both slightly
below their old means, consistent with the ladder's small downward drift.

**Ops notes from this pass.**

- **Rendering from `/<home-dir>/development` fails for this lane**: sparkrun resolves the lane-local
  mod `mods/ornith-honed-chat-template` relative to the `development/` symlink, not the symlink's
  target, and dies with "Could not resolve mod". Run from
  `/<home-dir>/src/sparkrun-recipe-registry` (the recipe's real path) — the render there is correct.
- The v0.5.21 image was pulled directly (`docker pull …@sha256:b1259f3e…`, ≈ 5 min per node), so
  sparkrun's distribution step was a no-op on both nodes.
- The 9B `.35` serve log was lost: `sparkrun stop --all` removed the `--no-rm` container. Its
  accept-len lines above are from live `docker exec` reads during the session, not a file; the 35B
  and YaRN logs were `docker cp`'d before their stops (`arm-35b/serve.log`, `arm-yarn/serve.log`).
  Stop with `sparkrun stop <cluster-id> -H <node>` and copy the log first.

**Cost, against the register's 6–9 h.** The pass used ~25 min of serve time for both spec arms
(boot + suite + ladder each, concurrent) plus ~3.5 h for the YaRN needle ladder (27 min per of the
262k/512k/768k rungs and 95 min for the 1M rung's three depths) — roughly **4 h total on a free
pair**, inside the registered 3.5–5.5 h estimate and the register's 6–9 h block.

## Engine bump to SGLang 0.5.22 (executed 2026-10-22 — all three arms validated)

**Status: validated on the new digest; the pins are applied.** One patch past 0.5.21. Each arm booted
alone on **`.35`**, one at a time, and passed its gate; receipts are
`~/benchmarks/sglang-0522-20261022/` (`arm-a-35b/`, `arm-b-9b/`, `arm-c-yarn/`). Evidence history lives
in [`attic/ornith/AGENTS.md`](../../attic/ornith/AGENTS.md) §"Engine-bump adjudication — 0.5.21 → 0.5.22".

**Target.** `lmsysorg/sglang:v0.5.22`, index digest
`sha256:e3a4f06001a29542fc4a8638536d9ffc5eb9c9942b08603c09b19a56eae4a1ae` (`v0.5.22-cu130` resolves to
the same index; `latest` did too on 2026-10-22). The index carries a native `linux/arm64` child,
`sha256:06441be3de19a816ddbac917535e920cbfc7fc43171abc08417394f43634ffb6`, verified **on the node**
with `docker manifest inspect` before the pull. Runtime moved with the tag: sglang `0.5.22`,
torch `2.14.1+cu130` (was `2.13.0+cu130`), python `3.12.15`, cuDNN `9.14.0.64`, `nccl_torch 2.30.7`.

That digest is a **registry manifest, not an image id**: `docker buildx imagetools inspect
lmsysorg/sglang:v0.5.22` (run 2026-10-22) prints it as the index digest with three child manifests
(`linux/amd64` `5fc09edb…`, `linux/arm64` `06441be3…`, and the `unknown/unknown` attestation
`5d21fc51…`). A number read off `docker images` is a config digest and never matches this one — do not
compare the two, and do not "correct" the pin to a local id.

**Pin edit (all three recipes, one line each):**

```diff
--- a/recipes/ornith/*.yaml
+++ b/recipes/ornith/*.yaml
@@
-container: lmsysorg/sglang:v0.5.21@sha256:b1259f3ea3275f66237c498ea388919729018bc9f01c3d638391e06e2cf3f469
+container: lmsysorg/sglang:v0.5.22@sha256:e3a4f06001a29542fc4a8638536d9ffc5eb9c9942b08603c09b19a56eae4a1ae
```

`tests/test_ornith_recipes.py` (29 tests) passes unchanged — it asserts a shared digest-pinned
container, not a literal digest.

**Measured 2026-10-22 (receipts `~/benchmarks/sglang-0522-20261022/`).** One serve per arm, sequential
on `.35`; every boot log's `Image:` line read the new digest and the engine reported `sglang: 0.5.22`.

| arm | boot / grant | quality | ladder @ d0, vs on-file band |
|---|---|---|---|
| 35B DFlash2 | HTTP-ready **238 s** (0.5.21: 223.6); `max_running_requests=48`; `max_mamba_cache_size=614` (0.5.21: 611; on file 632, does not clamp); pool **1,133,804** tokens (0.5.21: 1,125,837) | contract ok; house **37/37** (19/19 + 18/18); needle **3/3** at 32k / 131k / 262k | n=5: C1 **97.6 ± 8.8** · C2 **152.1 ± 7.4** · C5 **228.7 ± 16.0** · C10 **242.3 ± 5.0** (ttfr 311/569/1233/2014 ms) |
| 9B DFlash | HTTP-ready **251 s** (0.5.21: 235.7); `max_mamba_cache_size=273` (0.5.21: 272); pool **1,531,959** tokens (0.5.21: 1,523,077) | contract ok; house **37/37** | not laddered (no on-file pass bar); no regression expected or claimed |
| YaRN 1M | `context_len=1000000` in `/v1/models`; pool **1,187,727** tokens (on-file boots 1,202,898–1,205,530; 0.5.21: 1,192,993); `max_mamba_cache_size=1293`; 11.11 GB free; HTTP-ready **129 s** | window assertion only, by the arm's registered bar — **no 1M needle was run** (not cheap, and the ticked bar is the boot) | — |

**The ladder, both readings, because they are not the same instrument.** The triage pass ran the
profile at `-b runs=3` (the ticket's shape): **C1 94.3 · C2 146.0 · C5 207.1 · C10 247.7**. The recorded
reading re-took the same cell set at the profile's own `runs=5` and is the one to quote:

| cell | 0.5.22, n=5 | on-file band (n=5) | delta | σ | 0.5.21 n=5 reading | delta |
|---|---|---|---|---|---|---|
| C1 | **97.6** | 100.8–101.8 | **−3.2 %** | 8.8 | 96.5 | +1.1 % |
| C2 | **152.1** | 153.1–158.2 | −0.7 % | 7.4 | 148.3 | +2.6 % |
| C5 | **228.7** | 217.4–220.4 | **+3.8 % above the band** | 16.0 | 213.9 | +6.9 % |
| C10 | **242.3** | 244.2–249.9 | −0.8 % | 5.0 | 244.1 | −0.7 % |

Every cell sits inside the band's own σ, and the **direction** is: C1 down ~3 %, C2/C10 flat, C5 up
~4 %. That is not a regression to plan around, but it is also not the "GDN win" 0.5.21 hoped for — the
bump's value here stays *being on the current patch release*, not throughput.

**Engine-log delta vs the 0.5.21 boot: none.** Both builds' serve logs carry **zero** `WARNING` /
`ERROR` / `Traceback` lines (`arm-a-35b/serve.log` 707 lines, `0` matches; the 0.5.21 arm's log, `0`).
The 35B spec decode stayed engaged; the 9B and 1M arms booted without the `--mamba-*` flags changing
meaning.

**Ops notes from this pass.**

- **Boot by recipe file path, never `@littlecedar/<name>`.** The registry ref resolves the *published*
  copy, so the first launch silently booted `v0.5.21` from it while the worktree was already at
  `v0.5.22`; the give-away is the launch log's `Image:`/`Distributing image` lines naming the old
  digest plus `sglang: 0.5.21` in the versions block. See the root `AGENTS.md` §"Development Commands".
- **`docker pull repo:tag@sha256:…` leaves the image UNTAGGED**; a peer's `image prune` on the shared
  fleet removed one such pull. Re-tag it (`docker tag lmsysorg/sglang@sha256:e3a4f060… lmsysorg/sglang:v0.5.22`)
  as soon as the pull lands.
- **Verify the pin on the node immediately before each boot.** A peer's `git pull`/checkout on the
  shared head reverted an uncommitted `container:` edit mid-campaign and the next boot silently
  launched the previous engine; the guard used here is
  `grep -q e3a4f06001a29542 <recipe> || exit 3`.
- Nodes are scarce: `.31`–`.33` were held by another worker's TP=4 boot, so this pass ran entirely on
  `.35`, one arm at a time. `sparkrun stop <cluster-id> -H <node>` then **assert `docker ps -aq` = 0**
  worked at every arm boundary.

**Cost.** Six sequential arms on one node, ~2 h wall: three boots (~4 min each) + the 35B suite
(~11 min needle) + two 35B ladders + three sub-2-minute house batteries on the small arms.

## Lane caveats

- **The YaRN long-context route is now an arm, and only that arm enables it.** Both model cards
  describe extending the native 262,144-token window with **YaRN RoPE scaling** (factor 4.0 →
  roughly 1M tokens) via `config.json` or a launch-time override (`--hf-overrides` on vLLM,
  `--json-model-override-args` on SGLang, each gated by the engine's "allow longer context" env
  var). The three native-window recipes serve 262,144 as-is; [the 1M arm](#the-yarn-1m-arm) is the
  only recipe that turns it on. It is **booted and measured** (2026-10-18) and **ships for ≤768k
  workloads, with 1M supported to depth 50 %** — every rung through 768k passes 3/3, 1M passes at
  depths 10 % and 50 %, and **1M depth 90 % failed twice** with the serve process exiting mid-prefill,
  so there is **no measurement at the far end of the 1M window** and none is claimed. Open-source
  runtimes apply YaRN *statically*, so the factor is in force for every request and can erode quality
  on ordinary-length inputs; the 262,144 control rung passes at 99.66–99.86 % fill, which is the
  lane's check on that warning. Do not describe depth-90 % 1M retrieval as working: the depth cap is
  the arm's documented envelope, and raising it needs a boot whose serve log is streamed to the host
  for the whole request.
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
