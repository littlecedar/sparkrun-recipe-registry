# Ornith lane — `recipes/ornith/`

Serving recipes for **Ornith 1.5**, the self-improving agentic-coding model family from the
[Ornith Team](https://ornith.ai/ornith_1_5.html), on NVIDIA DGX Spark (GB10, SM121, 128 GB
unified LPDDR5X per node, 200 GbE ConnectX-7 RoCE). This directory is the `ornith` lane; it
ships **three** recipes, one per model scale:

| Recipe                                            | Scale | Runtime | Nodes (TP) | C1 t/s |  Size |  Mem | Flags  | Model Cards                                                                                 |
|:--------------------------------------------------|:------|:--------|:-----------|-------:|------:|-----:|:-------|:--------------------------------------------------------------------------------------------|
| `littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm.yaml` | 397B | vLLM | 4 (TP=4) |  41.86 | 235GB | 0.80 | 🌲👀🧠🦾🔧     | [Model][model-397b-graft]                                                                   |
| `ornith-1.5-35b-a3b-nvfp4-dflash2-sglang.yaml`    | 35B-A3B | SGLang | 1 (TP=1) |    100 |  45GB | 0.85 | ✨🚀🌲👀🧠🦾🔧 | [Model][model-35b] · [Draft][draft-dflash2]                                                 |
| `zz-ornith-1.5-122b-nvfp4-dflash2-sglang.yaml`       | 122B-A9B | SGLang | 1 (TP=1) |   —   |  75GB | 0.80 | 🚀🧠🦾🔧       | [drafter](https://huggingface.co/incoai/Ornith-1.5-122B-DFlash2) |
| `ornith-1.5-9b-nvfp4-dflash-sglang.yaml`          | 9B | SGLang | 1 (TP=1) |     55 |  11GB | 0.85 | ✨🚀🤏👀🧠🦾🔧     | [Model][model-9b] · [Draft][draft-9b]                                                       |

`C1 t/s` is single-stream decode as recorded in the parent [`README.md`](../../README.md);
`Size` is the per-node footprint the registry records and `Mem` is the recipe's
`gpu_memory_utilization`. Flags are defined in [Recipe Flags](../../README.md#recipe-flags). A dash is
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

  - [littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm](#littlecedar-ornith-15-397b-nvfp4-mtp-graft-vllm)
  - [ornith-1.5-35b-a3b-nvfp4-dflash2-sglang](#ornith-15-35b-a3b-nvfp4-dflash2-sglang)
  - [ornith-1.5-9b-nvfp4-dflash-sglang](#ornith-15-9b-nvfp4-dflash-sglang)
- [The YaRN 1M arm](#the-yarn-1m-arm)
- [Engine bump to SGLang 0.5.21 (executed 2026-10-21 — all three arms validated)](#engine-bump-to-sglang-0521-executed-2026-10-21--all-three-arms-validated)
- [Engine bump to SGLang 0.5.22 (executed 2026-10-22 — all three arms validated)](#engine-bump-to-sglang-0522-executed-2026-10-22--all-three-arms-validated)
- [The 122B one-node probe (measured, not shipped)](#the-122b-one-node-probe-measured-not-shipped)
- [122B quantisations and finetunes — drafter compatibility survey (2026-11-03)](#122b-quantisations-and-finetunes--drafter-compatibility-survey-2026-11-03)
- [DFlash2 draft-token sweep — matched-window result (2026-11-03)](#dflash2-draft-token-sweep--matched-window-result-2026-11-03)
- [Lane caveats](#lane-caveats)
- [Attic index](#attic-index)
- [References](#references)

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
| standard pass | 2026-10-15, `.34`, one boot — receipts `~/benchmarks/ornith-35b-suite-20261015/`: `summary.json` (quality), `hard/` (gsm8k/arc), `perf-ladder.yaml` (bench `bench_8c7486cad451`), `teb.yaml` (bench `bench_6b5b53dd4efb`), `serve.log`, `launch.log`; the tool's own per-scenario report — the only copy, since `tool-eval-bench` writes `runs/` under its CWD — is `.scratch/ornith/ornith-teb-20261015/2026-10-15T08-30-22.335952Z_f1eb66b7.md` |
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

## The 122B one-node probe (measured, not shipped)

Two **draft** arms, [`zz-ornith-1.5-122b-nvfp4-vllm.yaml`](zz-ornith-1.5-122b-nvfp4-vllm.yaml) and
[`zz-ornith-1.5-122b-ud-q3k-xl-llamacpp.yaml`](zz-ornith-1.5-122b-ud-q3k-xl-llamacpp.yaml), answer a
question the three shipped recipes cannot: can **one** DGX Spark absorb *simple* DeepSeek-V4.1-Flash
traffic with the 125.09B / **8.85B-active** MoE? The owner's easy-traffic gate is one boot that clears
**C1 ≥ 69.28**, **C10 ≥ 116.27 t/s** (both from the TP=4 DSv4 baseline, `bench_21011c740763`),
non-decreasing C5→C10, ≥ 10 streams, and house **≥ 36/37 at `--max-tokens 4096` thinking-on.
**Both tiers fail it on single-node decode, so both stay capability arms** — the fan-out that a TP=4
baseline buys is not recoverable by picking a quant or an engine.

| tier | engine · node | boot | decode @ d0, pp2048/tg128, n=5 | house | verdict |
|---|---|---|---|---|---|
| **vendor NVFP4** (mixed: attention/linear-attn FP8, rest NVFP4) | vLLM nightly `cc47adc1…`, TP=1, `.35` | TTR **665.9 s** port-open / 666.0 s HTTP-ready / 666.2 s TTFT; weights 77.63 GB, model loading 67.61 GiB in 497.1 s | C1 **27.11 ± 0.38** · C2 **39.53 ± 0.16** · C5 **60.37 ± 0.57** · C10 **73.91 ± 0.70** (ttfr 1181/1424/2896/4820 ms) | **37/37** (19/19 + 18/18) | **FAILS C1 (39 % of bar) and C10 (64 %)**; monotone, 10 streams served → capability arm |
| **unsloth UD-Q3_K_XL** (3.82 bpw) | llama.cpp `a37cc4610`, TP=1, `.34` | TTR **50.7 s** (node-local cache); 131,072 × 8 slots, `kv_unified` | C1 **27.94 ± 0.07** · C2 **42.75 ± 0.48** · C5 **43.20 ± 4.50** · C10 **not captured** | not run | **FAILS C1**; C5 < C2 means batching-poor at 8 slots → capability arm |

**What the two tiers together settle.** The **C1 wall is shared** — 27.11 t/s on vLLM/NVFP4 and
27.94 t/s on llama.cpp/Q3_K_XL, two engines and two quantisations, within 3 % — so single-stream decode
is a property of the 8.85B-active shape on one Spark, not of the stack. The tiers diverge only under
batching: NVFP4 climbs monotonically to **73.91** at C10 (2.7× C1) while the GGUF tier *loses* bandwidth
by C5 (43.20 < 42.75 C2), so **NVFP4 is the tier to keep** and the GGUF draft is superseded for this
question. Prefill is not the problem either: aggregate pp ran 1803 / 2479 / 2898 / 3136 t/s across the
four cells, i.e. healthy and rising; the gap is entirely decode-side. Against the bar the arm needs
**2.6× its C1 and 1.6× its C10**, which no launch knob on one node closes.

**Boot facts from the NVFP4 pass** (`.35`, 2026-10-22; receipts on the head in
`~/benchmarks/ornith-nvfp4-20261022/`: `ladder-nvfp4.{yaml,json,csv}`, `house-nvfp4-on.json`,
`serve.log`). `/v1/models` reported the served id `ornith-ai/Ornith-1.5-122B-NVFP4` at
`max_model_len` **262,144**; the pool line was `Available KV cache memory: 31.1 GiB` /
`GPU KV cache size: 2,341,091 tokens, Maximum concurrency for 262,144 tokens per request: 8.93x`
with `max_num_seqs=32`, `max_num_batched_tokens=8192`, `kv_cache_dtype=fp8`, flashinfer + marlin.
It is a **hybrid** model (`Qwen3_5MoeForConditionalGeneration`): the engine pads the mamba page 1.34 %
to make it equal the attention page and sets the attention block to **4224** tokens, and it logs
`Mamba cache mode is set to 'align' … when prefix caching is enabled` — so the pool is not pure
attention KV and the 8.93× figure is the engine's own estimate, not a slot count.

- **Launch it from the node, not from the control.** With `--transfer-mode local --offline`, a
  workstation-side launch refuses (`offline: model … is not in the control machine's cache
  (/home/siv/.cache/huggingface)`) even when the *node's* imported manifest reads `complete`; the same
  recipe launched on the node itself went to serving in 4.7 s. Node-side sparkrun is 0.4.1 here
  (control is 0.4.2) and still prints `Model … is unverified: offline: no saved authoritative model
  manifest … legacy compatibility` — with a `complete` manifest on the node plus
  `--transfer-mode local` that warning is benign, not a refusal.
- **Stage the weights on the node you are about to use** (`hf download … --revision f049036f…`, 23
  files, 4:56 at ~262 MB/s) rather than copying 77.63 GB off a node holding production.
- **The pin needs a `docker pull` even when the bytes are already resident.** The local image ID
  (`9a876c399945…`) matches the pinned manifest's config digest, but the repo-digest record is what
  sparkrun matches; `docker pull <repo>@sha256:cc47adc1…` took 0.3 s and moved no bytes.
- **Not measured, and not claimed:** no needle or long-context rung on either tier, no thinking-off
  leg, one repeat of the house battery, and no C10 for the GGUF tier (its `runs/` JSON was never
  flushed before the stop). This section is a two-cell gate verdict, nothing wider.

**Cell 4 — MTP spec decode, the completion cell (tplt4, 2026-10-25, `.35`).** The NVFP4 export keeps
the checkpoint's own MTP head unquantised (`ignore: ["mtp*"]`, vLLM `Qwen3_5MoeMTP`), so the
pre-registered spec-decode cell could run without a second model:
[`zz-ornith-1.5-122b-nvfp4-mtp-vllm.yaml`](zz-ornith-1.5-122b-nvfp4-mtp-vllm.yaml)
(`--speculative-config '{"method":"mtp","num_speculative_tokens":3}'`). Paired, same window,
same node (n=5, `--fresh`):

| cell | plain (control boot, same window) | **MTP n=3** | delta |
|---|---|---|---|
| C1 | 26.9 | **38.8** | **+44 %** |
| C2 | 39.3 | 48.9 | +24 % |
| C5 | 60.9 | 71.8 | +18 % |
| C10 | 74.4 | 81.2 | +9 % |
| house @4096 thinking-on | **37/37** (19/19 + 18/18) | **36/37** (easy 18/19, one miss) | −1 |

Serve-log **mean acceptance length 2.43–2.60** (> 1 — the gate passes). The control boot reproduces
the 2026-10-22 numbers within 1 % (26.9 vs 27.11), so the +44 % is spec decode, not window drift.
The 2026-10-22 verdict stands **against the easy-traffic gate** (MTP C1 38.8 is still 56 % of the
69.28 bar; the 17 t/s replacement falsifier passes with 2.3× margin, but a one-node 122B does not
replace a quartet on the owner's bars) — the cell's value is the **capability** record: MTP is a
real ~40 % C1 lever on this arm, the first one measured that moves the shared single-stream wall.
Contrast with the Mellum MTP rejection (+1.9 % at best, llama.cpp draft-mtp on a 12B-A2.5B): the
difference is the engine (vLLM's native `Qwen3_5MoeMTP` path) and the head being first-class in the
checkpoint. Recipe trap recorded: an explicit `command:` template consumes **only placeholders** —
a bare `-o speculative_config=…` is consumed nowhere (two boots rendered
`speculative_config=None`), and the JSON must be single-quoted in the template.
Receipts: `~/benchmarks/tplt4-20261024/ornith122b/` (`ladder-mtp.*`, `ladder-plain-ctl.*`,
`house-mtp.json`, `house-plain-ctl.json`, launch logs).

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

The three archived recipes were moved to `attic/ornith/` (commit `9942a40`) and are **not** part of
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

## `zz-ornith-1.5-122b-nvfp4-dflash2-sglang` — 122B with the DFlash2 block-diffusion drafter

Owner-requested arm (2026-10-30). The NVFP4 122B target with `incoai/Ornith-1.5-122B-DFlash2`
as the speculative draft, pinned `9baefc1b…`, **4 draft tokens** — the card's block size is 16, but
the 2026-11-03 same-window sweep (below) measures 15 below the no-drafter control at every rung past
C2 and 4 above it at all four, so the arm ships the measured value and 15 is now an `-o` override.

**Layer geometry verified before the boot, not assumed.** The NVFP4 export's `config.json` carries
no `num_hidden_layers`, so the drafter's `target_layer_ids: [1, 7, 14, 20, 26, 32, 39, 45]` were
checked against `model.safetensors.index.json` instead: the export holds **48 layers (0–47)**, all
eight indices exist, and the per-layer tensors are **unfused** (`mlp.experts.<n>.{up,gate,down}_proj`
individually, plus `shared_expert_gate`), so the drafter reads the layers it was trained against
rather than a renumbered or packed equivalent.

**Why the drafter should work here, and what could stop it.** DFlash 2 drafts a whole block
in one pass and the card is explicit that decoding is lossless — greedy output matches the
target and sampling preserves its distribution — so a C1 win costs no quality. Two things can
degrade it on this arm and both are in the receipt for the first boot:

- **Quantised targets.** The card's reference run is a bf16 target at TP=2. The drafter reads
  the target's hidden states at `target_layer_ids: [1, 7, 14, 20, 26, 32, 39, 45]`; an NVFP4
  export changes those states slightly, so acceptance is measured, never assumed. The
  card-exact bf16/TP=2 variant is the reference if acceptance looks low.
- **GGUF targets** need `mask_embedding.safetensors` (an exact BF16 copy of the target's
  mask-token row, in this repo, 6.4 KB) because Q8_0/K-quants store that row as zeros and
  acceptance roughly halves. An NVFP4 target keeps its embedding table in high precision, so it
  does **not** need the override — but if this arm's acceptance lands near half of the card's
  published 5–9, check the row before blaming the drafter: that is the failure mode the override
  exists for, and quantised exports are exactly where it hides.

The draft snapshot must be seeded into `refs/main` (the recipe's `pre_exec` does it): SGLang
resolves the draft through `refs/main`, and sparkrun's SHA-keyed fetch writes no refs entry.

**Gate:** serve-log acceptance length > 1 and a C1 cell at or above the plain 122B arm
(`zz-ornith-1.5-122b-nvfp4-vllm`, C1 17.9 tg t/s). **Falsifier:** no C1 gain over that arm.

**Result (2026-10-30, `.35`): the gate passes and the draft block is the finding.** C1 37.7 tg t/s,
C10 48.9 total, prefill 1614/1798 t/s at c1/c2 — against the no-drafter control's 28.95/48.97, i.e.
**+30 % at C1 and parity at C10**. With the recipe's own 15 draft tokens the same arm measured
35.2/29.1/27.4/25.8 across c1/c2/c5/c10 and prefill collapsed to 661 t/s at c2: the batching
degradation is an **over-large draft block**, not the drafter.

That extends a closed negative rather than reopening one: [`attic/ornith/AGENTS.md`](../../attic/ornith/AGENTS.md)
§4 already rejected `speculative_draft_tokens` 4 → 10 on quality (86.5/85.5 against a 99.3/99.2
control, ~19 % loss), and this arm's 15 is the same direction with a throughput penalty on top.
**Do not spend a boot re-deriving it upward** — d8 and d20 are the rejected direction, and the
corroboration is the result. The open leg is the *matched-window* control: baseline and d4 in the
same window, since the cross-table comparison above carries boot variance. Receipt:
`~/benchmarks/tp12-20261030/zz-ornith-1.5-122b-nvfp4-dflash2-sglang-d4/REPORT.md`.

## 122B quantisations and finetunes — drafter compatibility survey (2026-11-03)

Owner question (2026-10-30): which 122B quantisations and finetunes pair with the published
drafter `incoai/Ornith-1.5-122B-DFlash2`, and is there an uncensored, abliterated or
cybersecurity derivative that does? This section is the survey; it **boots nothing**. Every Hub
figure was read **2026-11-03** from the repo's own `config.json`, its
`model.safetensors.index.json` (`metadata.total_size`) or a GGUF header read over an HTTP range
request; the machine-readable evidence — per-repo licence, geometry, byte totals, and a
`weight_map` layer census — is `.scratch/ornith/hub-survey-20261103/` (`survey.json`,
`gate-safetensors.json`, `gate-gguf.json`, `cards/`). Bytes are decimal GB.

**Census.** The base repo's `base_model:*` tags plus a family name search return **67 derivative
repos** for 122B (9 finetune-tagged, 47 quantized-tagged, the rest re-splits and draft heads), so
the list below is complete as of that date, not a sample.

### The gate the drafter imposes — hard reject, not "works worse"

`incoai/Ornith-1.5-122B-DFlash2` `config.json` (read 2026-11-03):

| field | value | consequence for a target |
|---|---|---|
| `hidden_size` | **3072** | the selector projects `len(target_layer_ids) × hidden_size` from the *draft's* width, so a target of another width dies on a shape mismatch at load |
| `target_layer_ids` | **[1, 7, 14, 20, 26, 32, 39, 45]** | SGLang indexes the target's layers by these ids: `resolve_target_layer_ids` raises `ValueError("DFLASH target_layer_ids contains an out-of-range layer id")` for any id ≥ the target's layer count (`sglang/v0.5.22`, `python/sglang/srt/speculative/dflash_utils.py`) |
| `num_target_layers` | 48 | the depth it was trained against |
| `vocab_size` / `mask_token_id` | 248320 / 248077 | tokenizer and embedding table must be the family's |
| `dflash_config.block_size` | 16 | 15 draft tokens at the card's setting; this lane serves 4 (measured) |

**A finetune that changes depth or width cannot use the drafter at all.** The drafter's acceptance
property is a function of the *target's* hidden states at those eight indices; there is no engine
knob that remaps or pads them, and no fallback that keeps it lossless.

**No such finetune exists in this family.** All 67 derivatives keep `qwen3_5_moe`,
`text_config.hidden_size 3072`, `num_hidden_layers 48`, `vocab_size 248320`; every GGUF header
reads `qwen35moe`, `embedding_length 3072`, `block_count 49` (48 language layers + 1 NextN) except
the expert-pruned REAP50 file (`block_count 48`, no NextN). So the geometry gate rejects **nothing**
in the family today — the reject path is proven in engine source, not exercised by a candidate.

**Fit budget.** 128 GB unified per node, `gpu_memory_utilization: 0.80` → ~102 GB for weights plus
KV; fp8 KV on this hybrid is 10,240 B/token (10 GiB per 1M tokens, `attn` layers only), so a
≤ 90 GB checkpoint leaves ≥ 1.2M tokens of KV and a > 100 GB one does not fit at all.

### Candidates SGLang / vLLM can load (safetensors)

Every row reads `qwen3_5_moe` (`Qwen3_5MoeForConditionalGeneration`), `hidden_size` 3072,
48 layers, vocab 248,320, and carries the `mtp` head; the "drafter" column is about *acceptance*,
not geometry, unless it says otherwise. Every cell in the next three tables was read from the Hub
**2026-11-03**; "bytes" is `metadata.total_size` (index), a `tree` size sum, or a GGUF file length.

| candidate | repo id | quant / format | bytes (source) | arch · hidden / layers | drafter-compatible | fits one 128 GB node | license | verdict |
|---|---|---|---|---|---:|---|---|---|
| bf16 base | `ornith-ai/Ornith-1.5-122B` | bf16, 62 shards, **fused** expert tensors (`experts.gate_up_proj`) | 250.17 (index) | qwen3_5_moe · 3072 / 48 | geometry yes, unmeasured | **no** — needs TP=2 minimum | MIT | reject on fit: the drafter's own reference target, not a one-node arm |
| vendor FP8 | `ornith-ai/Ornith-1.5-122B-FP8` | W8A8 fp8, token-dynamic activations | 132.94 (index) | qwen3_5_moe · 3072 / 48 | geometry yes, unmeasured | **no** — 133 GB > 128 GB unified | MIT | reject on fit: the card's own TP2 reference pairing is this one, so it stays a 2-node question |
| vendor NVFP4 | `ornith-ai/Ornith-1.5-122B-NVFP4` | modelopt mixed: FP8 attention / linear-attn, NVFP4 experts | 77.61 (index) | qwen3_5_moe · 3072 / 48 | **measured**: C1 37.7 t/s, accept > 1 (d4) | yes — ~24.8 GB KV | MIT | **baseline**, already in the lane |
| cyankiwi | `cyankiwi/Ornith-1.5-122B-AWQ-INT4` | compressed-tensors **int4, group 32, asymmetric**; attention / linear-attn / shared expert / `lm_head` in `ignore`, experts quantized | 85.29 (index) | qwen3_5_moe · 3072 / 48 | geometry yes; acceptance is the open question | yes — ~17.1 GB KV | MIT | **boot arm 3** — the quant-family control |
| dealignai uncensored | `dealignai/Ornith-1.5-122B-UNCENSORED-NVFP4` | modelopt NVFP4, refusal direction projected out, **bundles the upstream drafter** under `dflash2/` (1.86 GB) | 75.65 (index) | qwen3_5_moe · 3072 / 48 | geometry yes; vendor's own vLLM check ran at ~37.8 t/s, not a speedup claim | yes — ~26.7 GB KV | MIT | **boot arm 1** — answers both halves of the question |
| devsecllm ablated | `devsecllm/Ornith-1.5-122B-NVFP4-ablated` | vendor NVFP4 with 24 of 113,047 tensors re-merged (rank-3 Heretic merge); config / tokenizer / template byte-identical | 77.61 (index) | qwen3_5_moe · 3072 / 48 | geometry yes; ablation moves 1.7–2.1 % of the attention weight norm, acceptance unmeasured | yes — ~24.8 GB KV | MIT | **boot arm 2** — the cybersecurity one |
| Sherlock-Comms | `Sherlock-Comms/Ornith-1.5-122B-NVFP4-DFlash2-RTX-Spark` | vendor NVFP4 with `lm_head` **dequantized to bf16** (nothing else changed) | 78.71 (index) | qwen3_5_moe · 3072 / 48 | geometry yes; the bf16 head fixes the **vLLM** drafter gate, which SGLang does not have | yes — ~23.7 GB KV | MIT | ranked 4, not drafted: SGLang already boots the quantized head, so it cannot answer a question the baseline has not |
| halt95 Merlin | `halt95/Ornith-1.5-122B-A10B-W4A16-Merlin` | int4 experts (g128) in 48 per-layer files + partial shards + `kv_scales`, custom loader | 71.28 (index) | qwen3_5_moe · 3072 / 48 | geometry yes | yes | MIT (+ bundled Qwen notice) | **reject** — served by the Merlin engine, a vLLM 0.32 fork with sm_86 profiles; no stock SGLang or vLLM loader |
| dealignai `ABLITERATED-NVFP4`, `ABLITERATED-GGUF` | `dealignai/Ornith-1.5-122B-ABLITERATED-*` | README + `.gitattributes` only, **no weights** | 0 | n/a | n/a | n/a | MIT | **reject** — empty repos (alternate listings of the UNCENSORED pair) |

### Candidates for the GGUF route (llama.cpp)

GGUF targets are the one place the drafter's own card warns about a **degraded** pairing, and the
warning applies to every row here (next subsection). Header reads: `qwen35moe`,
`embedding_length 3072`, `block_count 49` = 48 language layers + 1 NextN, `qwen35moe.nextn_predict_layers 1`.

| candidate | repo id | quants (GB) | arch · hidden / layers | drafter-compatible | fits one 128 GB node | license | verdict |
|---|---|---|---|---|---|---|---|
| official | `ornith-ai/Ornith-1.5-122B-GGUF` | BF16 249.36 · Q8_0 132.56 · Q6_K 102.38 · Q5_K_M 88.71 · **Q4_K_M 75.84** (+mmproj 0.91) | qwen35moe · 3072 / 49 | geometry yes — **mask gate** | Q4_K_M and Q5_K_M yes; Q6_K/Q8_0 no | MIT | viable GGUF, **no arm drafted**: the mask row is store-zeroed and no engine we run can substitute it |
| unsloth (dynamic) | `unsloth/Ornith-1.5-122B-GGUF` | UD-IQ1_M 40.36 · UD-IQ2_XXS 41.97 · UD-Q2_K_XL 44.53 · UD-IQ3_XXS 49.52 · **UD-Q3_K_XL 59.76** · UD-Q4_K_XL 79.71 · UD-Q5_K_XL 94.61 · UD-Q6_K_XL 114.22 · Q8_0 132.56 | qwen35moe · 3072 / 49 | geometry yes — mask gate | ≤ UD-Q4_K_XL yes; UD-Q5_K_XL 94.61 leaves ~7 GB KV; UD-Q6_K_XL no | MIT | lane's existing GGUF family (`zz-…-ud-q3k-xl-llamacpp`); same gate |
| mradermacher | `mradermacher/Ornith-1.5-122B-GGUF`, `…-i1-GGUF` | Q3_K_S 54.01 · Q3_K_M 59.81 · Q4_K_S 71.08 · Q4_K_M 75.84 · Q5_K_S 85.93 · Q5_K_M 88.71; i1-IQ3_M 54.88 · i1-IQ4_XS 66.80 · i1-Q4_K_M 75.84 | qwen35moe · 3072 / 49 | geometry yes — mask gate | yes ≤ Q5_K_S | MIT | viable |
| bartowski | `bartowski/Ornith-1.5-122B-GGUF` | IQ3_M 67.64 · IQ4_XS 70.21 · **Q4_K_M 78.93** · Q5_K_M 94.94 · Q6_K 109.30 · Q8_0 132.56 | qwen35moe · 3072 / 49 | geometry yes — mask gate | ≤ Q4_K_M yes; Q5_K_M 94.94 leaves ~7 GB KV; Q6_K/Q8_0 no | MIT | viable |
| AtomicChat (dynamic) | `AtomicChat/Ornith-1.5-122B-GGUF` | AD-IQ3_XXS 54.28 · **AD-IQ4_XS_S 71.22** · AD-Q5_K-Q4_K 78.46 · AD-Q6_K 104.47 · Q8_0 132.56 | qwen35moe · 3072 / 49 | geometry yes — mask gate | yes ≤ AD-Q5_K-Q4_K; AD-Q6_K 104.47 and Q8_0 do not fit | MIT | viable |
| AtomicChat uncensored | `AtomicChat/Ornith-1.5-122B-Uncensored-GGUF` | AD-IQ3_XXS 54.28 · **AD-IQ4_XS_S 71.22** | qwen35moe · 3072 / 49 | geometry yes — mask gate; refusal direction projected out in all 48 blocks, MTP head untouched | yes | MIT | uncensored GGUF option; **eval-only by policy**, no arm drafted |
| rax4901 | `rax4901/Ornith-1.5-122B-Uncensored-GGUF` | the same two builds re-split into 31 / 38 shards | qwen35moe · 3072 / 49 | as above | yes | MIT | **duplicate** of AtomicChat's uncensored pair (byte totals equal) — no separate row value |
| dealignai uncensored | `dealignai/Ornith-1.5-122B-UNCENSORED-GGUF` | **IQ2_XXS 44.07** · Q4_K_M 79.37 · + ships `dflash2/Ornith-1.5-122B-DFlash2-Q8_0.gguf` 1.00 | qwen35moe · 3072 / 49 | geometry yes — **the only pairing with a published GB10 measurement**: 26.23 t/s with the drafter vs 26.27 without (parity), Q4_K_M failed their quality check | yes | MIT | **the GGUF reference point** — a real arm would reproduce a known tie, so none is drafted |
| zephel01 | `zephel01/Ornith-1.5-122B-IQ3_XXS-16G64G-GGUF` | IQ3_XXS 51.71 (`token_embd` at IQ3_S by design) | qwen35moe · 3072 / 49 | geometry yes — mask gate | yes | MIT | viable |
| tsaipifong | `tsaipifong/Ornith-1.5-122B-MXFP4-GGUF` | MXFP4 experts 70.77 (2 shards) | qwen35moe · 3072 / 49 | geometry yes — mask gate | yes | MIT | viable |
| fajardc | `fajardc/Ornith-1.5-122B-GSQ-RCO-GGUF` | IQ3_S 53.38 with a rotation pre-pass | qwen35moe · 3072 / 49 | geometry yes — mask gate | yes | MIT | viable |
| prithivMLmods | `prithivMLmods/Ornith-1.5-122B-NVFP4-GGUF`, `…-MXFP4-MoE-MTP-GGUF` | NVFP4-derived 80.92 (+mmproj 0.91) · MXFP4_MOE 69.67 | qwen35moe · 3072 / 49 | geometry yes — mask gate; NVFP4→GGUF is a second quantisation on top of the vendor one | yes | MIT | viable, weakest provenance of the set |
| dongnhdev | `dongnhdev/Ornith-1.5-122B-MTP-GGUF` | IQ2-MTP 37.36, ships `mask_row_248077.f32` (12 KB) as a **reference fixture** | qwen35moe · 3072 / 49 | geometry yes — mask gate; the fixture is not an engine input | yes | Apache-2.0 | viable; the fixture names the row the mask gate is about |
| anik-jha | `anik-jha/Ornith-1.5-122B-24GB-GGUF` | REAP50 UD-IQ2_XXS 21.42 | qwen35moe · 3072 / **48 layers, NextN removed** | geometry yes, but **half the experts pruned** — a different model | yes | MIT | not a drafter test: capability arm only, and its own card says MTP is gone |
| GGUF drafters | `kaivoss/Ornith-1.5-122B-DFlash2-GGUF` | DFlash2 draft 0.14–3.73 (Q4_K_M 0.55 is the card's default) | `dflash` arch, 6 layers | the draft itself | yes | Apache-2.0 | the llama.cpp-side drafter for any row above |
| MTP heads (not targets) | `ToPo-ToPo/Ornith-1.5-122B-MTP-bf16` 5.05 (MLX), `SizorCloud/Ornith-1.5-122B-MTP` Q8_0 GGUF 2.69 | draft heads split out of the checkpoint | 6-layer MTP / `qwen3_5_mtp` | alternative spec-decode lever, not a DFlash2 target | yes | MIT / MIT | recorded, not candidates |

### The mask-embedding override exists as an artifact, and no engine we run reads it

The drafter loads the target's mask-token embedding (id 248077). Ornith stores that row at a scale
around 1e-6, below what fp16 block scales hold, so **every GGUF build of the target stores it as
zeros and draft acceptance roughly halves** (drafter card, read 2026-11-03). The card ships
`mask_embedding.safetensors` (an exact bf16 copy of the row) in the drafter repo, "which an engine
can read in its place". Neither engine this lane runs can, as of today:

- **SGLang v0.5.22** merges only `mask_embedding.pt` — the filename is a literal in
  `_maybe_merge_trained_mask_embedding` (`python/sglang/srt/speculative/dflash_worker_v2.py`), and
  it also requires a `mask_token_id` field and a `per_position` flag the safetensors artifact does
  not carry.
- **llama.cpp at this lane's pin** (`a37cc4610`, the build every GGUF arm here uses) reads the mask
  token's row from the **target's own token-embedding tensor** and has no mask-embedding input at
  all: `llama_vocab_mask` resolves the id in `common/speculative.cpp`, and the graph takes
  `model_other->tok_embd`. There is no `--mask-embd`-style flag in `common/arg.cpp`.

So every GGUF row above carries the same caveat, and a GGUF DFlash2 arm is postponed rather than
drafted: the one pairing with a published GB10 measurement (dealignai's IQ2_XXS) came out **at
parity** (26.23 vs 26.27 t/s), which is what a halved acceptance looks like, and the row that would
benefit — a 4-bit-or-better target — cannot get the row substituted on either engine. The engine
work that would unlock it is a `mask_embedding.safetensors` reader (`.pt`→safetensors in SGLang, a
new input in llama.cpp); until then the honest GGUF answer to the owner's question is "the drafter
runs, and buys nothing".

### Container- and engine-specific exports, rejected on format

Geometry is fine in every case (3072 / 48 as declared in the repo's `config.json`); the format is
what fails. None of these can be loaded by SGLang or vLLM on GB10 without a new engine.

| family | repos (bytes, GB) | format | drafter-compatible | license | fits one node | verdict |
|---|---|---|---|---|---|---|
| radiance `.rad` (AMD RDNA4) | `keptn/ornith-1.5-122b-fp8` 126.70 · `…-fp8-dflash2` 124.88 · `…-w4a8` 69.37 · `…-w4a8-dflash2` 68.72 | single-file radiance container; the `-dflash2` pair even merges the drafter in as MXFP4, 15 draft tokens | only inside radiance | MIT (drafter Apache-2.0) | fp8 pair no; w4a8 pair yes | **reject** — engine-specific, needs 4 RDNA4 cards |
| Infernix `.infernix` | `wallawalla47/Ornith-1.5-122B-NVFP4-Infernix` 75.33 · `…-UNCENSORED-NVFP4-Infernix` 75.87 | 3-part Infernix artifact carrying MTP + the DFlash2 drafter + a Q4 proposal head | only inside Infernix | MIT (drafter Apache-2.0) | yes | **reject** — engine-specific; its own card records `--spec dflash2` **losing 16 %** at two requests |
| cortiq `.cmf` | `infosave/Ornith-1.5-122B-cmf` q2tp 48.10 · q4tp 67.90 · q8_2f 125.06 | cortiq container, one physical MTP block kept | no | MIT | q2tp/q4tp yes, q8_2f no | **reject** — engine-specific |
| ExLlamaV3 | `Mia-AiLab/…-EXL3-EAQv1-4-bpw` 65.63 · `0xBakeer/…-EXL3-4.0` 64.73 · `vcruz305/…-EXL3-SAGE-2.58bpw` 45.17 · `davetha/…-EXL3-3bpw-mixed` 51.70 · `scorpoon/…-exl3-SC` 0 (empty) | EXL3 | no | MIT | all four non-empty yes | **reject** — no CUDA/SGLang path on this stack |
| Apple MLX | `ornith-ai/Ornith-1.5-122B-MLX` 245.16 · `-MLX-8bit` 130.68 · `-MLX-4bit` 69.65 · `ToPo-ToPo/…-mlx-4bit` 72.70 · `…-mlx-8bit` 130.68 · `araysuter/…-MLX-mixed-2bit` 40.65 · `…-down3` 45.48 · `…-group32` 47.89 · `BobClawblaw/…-MLX-4bit` 69.64 · `Duckets/…-MLX-4bit` 69.64 · `ezoushen/…-mlx-4bit` 69.64 · `…-mlx-mixed-4.46bpw` 69.03 · `pgmharikrishnan/…-MLX-Serve-mixed-4-8bit` 71.79 · `hermitdave/…-MLX-Imatrix-Mixed-MTP` 47.40 · `…-MLX-Mixed2-3-8bit-MTP` 49.05 | MLX safetensors | no | MIT (hermitdave Apache-2.0) | 4-bit class yes, 8-bit/bf16 no | **reject** — Apple Silicon only |
| JANG / oQ (MLX affine) | `OsaurusAI/…-JANGH2` 42.63 · `…-JANG_4M` 73.91 · `scottlowry/…-oQ4e-mtp` 72.97 · `…-oQ4e-fp16-mtp` 73.88 · `…-oQ5e-mtp` 87.94 · `…-oQ5e-fp16-mtp` 88.84 · `…-oQ6e-mtp` 103.04 · `…-oQ6e-fp16-mtp` 103.98 · `…-oQ8e-mtp` 133.29 · `…-oQ8e-fp16-mtp` 134.20 · `krisfremen/…-oQ2e` 43.35 | oMLX/JANG affine quantisation (`library_name: mlx`) | no | OsaurusAI MIT; **`scottlowry` and `krisfremen` declare no licence** | mixed: the ≤ 73.88 GB builds yes, oQ8e/oQ6e-fp16 no | **reject** — Apple side, and the no-licence repos could not be shipped even on a working format |
| ROCmFPX | `Harsha001/Ornith-1.5-122B-ROCmFPX` 146.15 | ROCm FPX | no | MIT | no | **reject** — AMD |
| not weights | `raahemnabeel/ornith-1.5-122b` 2.06 | 782 files of container image blobs (`image/blobs/sha256/…`) | n/a | MIT | n/a | **reject** — no checkpoint |

### The security question: uncensored, abliterated, cybersecurity at 122B

A full-family name sweep (`hf://models` search over 1008 `Ornith*` repos, 2026-11-03) with the
refusal-removal vocabulary (abliterat, uncensor, heretic, obliterat, unfiltered, cyber, dealign,
devsec) leaves **six** 122B repos — two of them the same weights re-split — and two empty alternate
listings:

| repo | what it is | pairs with the drafter? | how it was measured |
|---|---|---|---|
| `devsecllm/Ornith-1.5-122B-NVFP4-ablated` | rank-3 Heretic ablation of the vendor NVFP4 export, 24 tensors, `KL 0.0191`, refusal 97 % → 4.44 %; published **for blue-team / detection engineering** | yes — byte-identical layout to the vendor export, so the geometry gate passes by construction | its own card: HumanEval 93.3 (both), CyberBench 62.5 vs 61.3 base (McNemar p ≈ 0.28), NIAH 20/20 at 8k–196k |
| `dealignai/Ornith-1.5-122B-UNCENSORED-NVFP4` | refusal direction projected out of all 48 blocks (weights abliteration, not a SFT), MMLU −1.69 pp, HarmBench 309/320 comply; **ships the upstream drafter** under `dflash2/` | yes — and it is the only security build whose card ran the drafter on GB10 (`vLLM 0.31.1rc1`, 7 draft tokens, 37.84 t/s end-to-end; explicitly **not** a speedup claim) | its own card, bounded 4-response integration check |
| `dealignai/Ornith-1.5-122B-UNCENSORED-GGUF` | the same edit stacked as Q4_K_M / IQ2_XXS with the drafter as a GGUF under `dflash2/` | geometry yes, mask gate applies: IQ2_XXS tied the no-drafter baseline (26.23 vs 26.27 t/s), Q4_K_M failed their quality check | its own card |
| `AtomicChat/Ornith-1.5-122B-Uncensored-GGUF` | refusal-direction projection in all 48 blocks, MMLU 83.65 → 83.90 (p = 0.72), expert-only AD layouts; `rax4901`'s repo is the same two builds re-split | geometry yes, mask gate applies | its own card (KL 0.0274 for the AD-IQ4_XS_S layout) |
| `wallawalla47/Ornith-1.5-122B-UNCENSORED-NVFP4-Infernix` | the dealignai edit packed for Infernix | only inside Infernix | its own card; `--spec dflash2` lost 16 % at two requests |

**There is no 122B cybersecurity *finetune*** — no SFT on security corpora, no `Cyber-`, no
`OBLITERATED`, no `heretic` at this scale. That naming exists only on the 9B, 35B and 397B siblings
(`Cyber-Ornith-1.5-9B-OBLITERATED`, `Huihui-Ornith-1.5-35B-A3B-abliterated`,
`ressl/Ornith-1.5-397B-uncensored-*`), each of which needs its *own* drafter (9B DFlash, 35B
DFlash2, 397B DFlash) and is out of scope here. At 122B the closest thing is
`devsecllm`'s blue-team ablation, and it is an ablation of a quantisation, not a domain finetune.

**Licence verdicts.** Every 122B candidate above is **MIT** (`devsecllm`, `dealignai` — whose
bundled drafter is Apache-2.0, `AtomicChat`, `rax4901`, `wallawalla47`, `cyankiwi`, the official and
community GGUF repos), except `dongnhdev/…-MTP-GGUF` (Apache-2.0) and the two oQ owner repos that
declare **no** licence at all. **No non-commercial or otherwise restricted 122B licence exists in
the census**, so no arm is eval-only *because of its licence*. The two uncensored arms below are
eval-only by house policy instead — a refusal-removed model has to be deployed by whoever wrote the
guardrails, and promoting it out of a registry would be handing that decision to someone who never
read the card. Both carry the banner in `description:` and `metadata.eval_only`; the third arm
(`cyankiwi`, untouched alignment) is a plain MIT arm with no banner.

### Ranking and the three boot arms

| rank | arm | recipe | why it ranks here | falsifier (declared before the boot) |
|---|---|---|---|---|
| 1 | `dealignai/Ornith-1.5-122B-UNCENSORED-NVFP4` + DFlash2 | `zz-dealignai-ornith-1.5-122b-nvfp4-uncensored-dflash2-sglang.yaml` | answers both halves of the question in one boot: the smallest fitting target in the set (75.65 GB) **and** the uncensored build; its `dflash2/` copy means the same arm can also be run with no second repo staged | serve-log mean acceptance ≤ 1.05, or C1 below the shipped NVFP4 arm's 37.7 t/s → the abliteration costs acceptance; re-run against the bundled draft copy to separate "draft path wrong" from "weights changed" |
| 2 | `devsecllm/Ornith-1.5-122B-NVFP4-ablated` + DFlash2 | `zz-devsecllm-ornith-1.5-122b-nvfp4-ablated-dflash2-sglang.yaml` | the only 122B build published for cybersecurity work, and the highest prior of acceptance in the set: the export is byte-identical to the vendor NVFP4 apart from 24 tensors (index total equal to the byte) | same acceptance gate; plus a house battery at `--max-tokens 4096` thinking-on — this family's uncensored replies run 2-3× longer, so a short `max_tokens` reads as a capability miss |
| 3 | `cyankiwi/Ornith-1.5-122B-AWQ-INT4` + DFlash2 | `zz-cyankiwi-ornith-1.5-122b-awq-int4-dflash2-sglang.yaml` | the quant-family control: every other arm here is modelopt NVFP4, so this is the only row that can answer whether the drafter tolerates a *different* 4-bit family (compressed-tensors int4 g32 asymmetric) at the same geometry | boot fails to resolve the mixed-precision layout on `qwen3_5_moe`/SM121, or acceptance < 1.5 → the pairing is quant-family-specific, and the "any 4-bit target works" reading is dead |

Ranked 4 and **not** drafted: `Sherlock-Comms/…-NVFP4-DFlash2-RTX-Spark`. Its whole change is a bf16
`lm_head`, which fixes the **vLLM** gate where the official NVFP4 head makes vLLM refuse the draft.
SGLang already runs the quantized head (the shipped arm's 37.7 t/s), so this arm cannot answer a
question the baseline leaves open — it becomes interesting only if a matched-window comparison
shows the bf16 head lifting acceptance on SGLang too.

Each arm is one SGLang boot on a free node plus a decode ladder; there is no needle or long-context
leg registered for them, and the numbers they produce are single-window.

```bash
# one arm, one boot, one window; the gate is two numbers off the serve log and the ladder
sparkrun benchmark performance recipes/ornith/<arm>.yaml -H .35 --fresh \
  --profile benchmarking/decode-triage.yaml \
  --output ~/benchmarks/ornith122b-survey-20261103/<arm>.json
# acceptance: "Mean acceptance length" on the decode-batch lines (> 1 means engaged)
# cross-check: C1 against the shipped NVFP4 arm's 37.7 t/s and its no-drafter control at 28.95
```

### Recipes added by this survey

| recipe | target pin | drafter | bytes | status |
|---|---|---|---|---|
| `zz-dealignai-ornith-1.5-122b-nvfp4-uncensored-dflash2-sglang.yaml` | `e6a1c178…` | `incoai/…-DFlash2` `9baefc1b…`, 4 draft tokens | 75.65 GB | DRAFT, never booted, **eval-only** |
| `zz-devsecllm-ornith-1.5-122b-nvfp4-ablated-dflash2-sglang.yaml` | `e80d38d7…` | same | 77.61 GB | DRAFT, never booted, **eval-only** |
| `zz-cyankiwi-ornith-1.5-122b-awq-int4-dflash2-sglang.yaml` | `f37c82fd…` | same | 85.29 GB | DRAFT, never booted |

All three copy the shipped `zz-ornith-1.5-122b-nvfp4-dflash2-sglang` structure — same digest-pinned
`lmsysorg/sglang:v0.5.22`, same `pre_exec` `refs/main` seed for the pinned draft, same
`mamba_radix_cache_strategy: extra_buffer` — and set `speculative_draft_tokens: 4` rather than the
card's 15, because this lane measured 15 degrading C2–C10 with a prefill collapse and 4 winning C1
(`…-dflash2-sglang-d4` receipt). They are `zz-` drafts: not in the root README index, not claimed to
serve, and `sparkrun recipe validate`-clean. The shipped 122B DFlash2 arm keeps its 15 until the
registered matched-window control boot moves it — that knob should change with a measurement, not
with this survey.

### 122B finetunes: incoherence triage (2026-11-03)

**Symptom.** Only `zz-dealignai-…-uncensored-dflash2-sglang` has booted. On `.30` it loaded, reached
readiness, and then failed llama-benchy's coherence probe; direct HTTP probes returned **token
salad** — mixed-script fragments and repeated `.pass` — both with and without
`chat_template_kwargs.enable_thinking=false`. The other two arms (`devsecllm`, `cyankiwi`) have not
been booted. Nothing here is a throughput result: **no decode rate is recordable on any 122B finetune
arm until one serves coherently**, and a boot that emits salad has no C1 to compare against the
shipped arm's 37.7 t/s.

Owner directive: keep the arms and debug them, template and parsers first. Template first is cheap —
it is answered below from bytes already on the Hub, without a boot.

#### The template is not what changed

Every 122B repository in this family that serves today (`ornith-ai/…-NVFP4`, and `devsecllm/…-ablated`
which the vendor export is byte-identical to) and every finetune arm uses the same `--trust-remote-code`
and the same two parser flags. Reading the four repos over the Hub API on 2026-11-03:

| file | base (serves coherent) | `dealignai` finetune | verdict |
|---|---|---|---|
| `tokenizer.json` (12.8 MB) | `7b607479…` | `7b607479…` | identical |
| `vocab.json` (6.7 MB) | `4e976260…` | `4e976260…` | identical |
| `merges.txt` | `bc43d7e0…` | `bc43d7e0…` | identical |
| `tokenizer_config.json` | `53de78b0…` | `53de78b0…` | identical, incl. embedded `chat_template` (`94f89e03…` md5, 7,756 B, all four repos) |
| `chat_template.jinja` | 7,594 B | 7,593 B | **differ by a trailing newline**; the only other diff is an `loop.index0 > ns.last_query_index` branch on reasoning replay that base and finetune share the same way |
| `special_tokens_map.json` | absent | absent | markers come from `tokenizer_config.added_tokens_decoder`: `248068 <think>`, `248069 </think>`, `248045 <|im_start|>`, `248046 <|im_end|>` |
| `.py` modules | none | none | `--trust-remote-code` resolves the same `Qwen2Tokenizer` in both; there is no custom tokenizer class to pick |

None of the four repos ships a `chat_template.json`; each ships a standalone `chat_template.jinja`
alongside a `chat_template` string inside `tokenizer_config.json` (7,756 B, md5 `94f89e03…` in all
four). Whichever of the two the loader prefers, the base and the finetune differ in it the same way,
so the choice cannot separate the arm that serves coherent from the arm that emits salad.

So the tokenizer, the special-token table and the rendered prompt bytes are the **same on the arm
that serves coherent and the arm that emits salad**. Template and parser-knob hypotheses cannot
explain arm 1 by themselves; they stay on the ladder because the owner asked for them to be excluded
by measurement and because the chat path is the one variable nobody has isolated on this export.

#### What did change: the quantization layout

Both repos declare `quant_method: modelopt`, `quant_algo: MIXED_PRECISION`, 48 × 3072, vocab
248,320 — the same. The per-layer algo map is not:

| | vendor NVFP4 (serves) | `dealignai` finetune (salad) |
|---|---|---|
| routed experts, 48 layers | `W4A16_NVFP4` | `W4A16_NVFP4` |
| attention q/k/v/o, `linear_attn` projections | `FP8` (156 layers) | **`FP8_PER_CHANNEL_PER_TOKEN`** |
| shared expert gate/up/down | `W4A16_NVFP4` | **`FP8_PER_CHANNEL_PER_TOKEN`** |
| `lm_head` | `W4A16_NVFP4` (global + block scales) | **`FP8_PER_CHANNEL_PER_TOKEN`**, no `weight_scale_2` |
| `mtp` head | BF16, excluded via `ignore: ["mtp*"]` | quantized, `mtp.layers.0.mlp.experts` = **`FP8_PB_WO`**, 768 `weight_scale_inv` tensors |
| `config_groups`, `kv_cache_scheme` | present | **absent** |
| index total / shards | 77,612,366,084 B / 8 | 75,647,330,784 B / 50 |

`FP8_PER_CHANNEL_PER_TOKEN` is the number that matters. SGLang v0.5.22's
`ModelOptMixedPrecisionConfig.get_quant_method` dispatches on the per-layer algo name and implements
exactly `FP8`, `FP8_PB_WO`/`FP8_BLOCK_SCALES`, `MXFP8`, `NVFP4`, `W4A16_NVFP4`
(`python/sglang/srt/layers/quantization/modelopt_quant.py`, read at the pinned tag). Every other name
falls through to `UnquantizedLinearMethod()` for a linear or LM head and to `None` for a fused MoE
layer — silently, no warning in the dispatch. `FP8_PER_CHANNEL_PER_TOKEN` appears nowhere in that
module, in `fp8.py`, in `compressed_tensors/`, or in the quantization `__init__.py`.
`FP8_PB_WO` *is* implemented (`_BLOCK_FP8_ALGOS`), so the quantized MTP block is not the offender.

That gives a mechanism, not a guess: 308 layers of this export — including the head that every logit
passes through — would load as unquantized bf16 from fp8-serialized weights, dropping their
per-channel `weight_scale`. The server loads, reaches readiness, and emits garbage for every token,
which is exactly the observed signature. It also predicts why the base export is fine: its attention
is plain `FP8` and its head is `W4A16_NVFP4`, both implemented.

#### Confirmation, and the control that is already running (measured 2026-11-03 ~19:50 ET)

Two independent readings turned hypothesis 1 from the most likely into the established one, and they
also collapse hypotheses 2 and 3 into it.

**The algo is missing from the whole dispatch path, not one file.** Grepped at the pinned tag:
`FP8_PER_CHANNEL_PER_TOKEN` occurs **0 times** in `modelopt_quant.py` — where the per-layer dispatch
`ModelOptMixedPrecisionConfig.get_quant_method` ends in a bare `return UnquantizedLinearMethod()`
(`:1040`) after trying `FP8`, `_BLOCK_FP8_ALGOS`, `MXFP8`, `NVFP4`, `W4A16_NVFP4` — and **0 times** in
`fp8.py`, `compressed_tensors/compressed_tensors.py` and the quantization `__init__.py`. There is no
second home for it. The fused-MoE dispatch (`:1059-1069`) ends in `return None`, so a MoE layer with
that name gets no quant method at all.

**The failed arm's own serve log shows the consequence at the drafter.** Read from the live container
(`docker exec … grep 'accept rate' /tmp/sparkrun_serve.log`): `accept len: 1.00, accept rate: 0.00` on
every decode step. The DFLASH drafter borrows the target's `lm_head`, so a head loaded unquantized from
fp8 weights produces logits the target never agrees with — a 0.00 acceptance rate is what hypothesis 1
*predicts*, and it removes the drafter as an independent suspect: hypothesis 2's symptom is a downstream
effect of the same defect, not a competing cause. This is why no probe on the failed arm is on the
critical path any more.

**The control was already queued.** The two remaining arms differ in export layout, measured the same
way:

| arm | `quantized_layers` algos | layers | implementable at v0.5.22 |
|---|---|---|---|
| `dealignai/…-UNCENSORED-NVFP4` | `FP8_PER_CHANNEL_PER_TOKEN` 308, `W4A16_NVFP4` 48, `FP8_PB_WO` 1 | 349 | **no** — 308 name an algo no branch handles |
| `devsecllm/…-NVFP4-ablated` | `W4A16_NVFP4` 193, `FP8` 156 | 349 | yes, all of them; `lm_head` is `W4A16_NVFP4` |
| `cyankiwi/…-AWQ-INT4` | `compressed-tensors`, `pack-quantized`, 4-bit group 32 | — | different loader entirely (`CompressedTensorsConfig`), not this dispatch |

So the devsecllm arm **is** the falsifier, at no extra cost: same drafter, same template, same parser
pair, clean algo map. Coherent devsecllm with salad dealignai confirms hypothesis 1 outright and retires
the two probe arms; salad on both would push the cause back to the target/drafter pairing and the probes
then earn their boots. The cyankiwi arm answers a different question — whether the family's third export
family loads at all through compressed-tensors. No decode rate is recordable on any of the three until
one serves coherently.

##### Result: the layout was the defect, and the family has a servable finetune

Measured 2026-11-03 20:15 ET on `.30`, one boot each, identical serving flags, same drafter:

| arm | export algo map | probe (`The capital of France is…`) | draft acceptance |
|---|---|---|---|
| `zz-dealignai-…-uncensored-dflash2-sglang` | `FP8_PER_CHANNEL_PER_TOKEN` ×308 incl. head | token salad | **0.00** |
| `zz-devsecllm-…-ablated-dflash2-sglang` | `W4A16_NVFP4` ×193 + `FP8` ×156, head W4A16 | *"The capital of France is Paris."* | **0.62–0.64** |

That is hypothesis 1 confirmed and hypotheses 2–4 retired in one comparison: with the drafter, the
template and both parser flags held constant, only the export layout differs, and it alone separates
salad from coherent text. The drafter is not merely innocent — 0.63 acceptance is a healthy figure for
this family, so the pairing is good and the salad arm's `0.00` was the unquantized head, exactly as
predicted. **The two authored probe arms are therefore retired unspent** and stay in the tree only as
the falsifiers to reach for if a *future* export misbehaves the same way.

`dealignai/…-UNCENSORED-NVFP4` becomes a recorded negative with a precise cause. Two follow-ups could
reopen it, neither of which is work this lane should start on a hunch: an engine that implements
`FP8_PER_CHANNEL_PER_TOKEN`, or a re-export whose `quantization_config` uses only implemented algo
names. `devsecllm/…-NVFP4-ablated` is the family's first 122B finetune that serves, and its own
disposition (promote past `zz-`, or keep as an eval-only probe) waits on its ladder and suite numbers.
Nothing above is a decode rate: those are the benches' to produce, and they are running.

#### Ranked hypotheses, each with the one probe that decides it

The two probe arms below differ from the failed arm in one direction each, and both drop the drafter,
because the drafter is the only component the coherent base arm and this export do not share in
identical form:

| # | hypothesis | mechanism | decided by |
|---|---|---|---|
| 1 | **export quant dispatch** (most likely) | `FP8_PER_CHANNEL_PER_TOKEN` has no branch in `ModelOptMixedPrecisionConfig`, so 308 layers incl. `lm_head` load unquantized and lose their per-channel scale | probe A: **salad on raw completion with no drafter and no template** |
| 2 | **drafter / FP8 head** | DFLASH has no head of its own and borrows the target `lm_head`; `is_dense_head_weight` accepts only fp16/bf16/fp32, and this export's head is fp8, so the draft falls to `_greedy_sample_from_quantized_head` → `lm_head.quant_method.apply` (`speculative/dflash_worker_v2.py`). The vendor only ever validated DFlash2 on this export under vLLM, where sharing the FP8 head is called out as a build requirement | probes A **and** B coherent (drafter is then the only remaining delta to the salad arm) |
| 3 | **chat template** | a finetune ships its own template | already falsified on bytes: identical prompt for the arm that serves coherent. Probe B settles it by measurement |
| 4 | **`--reasoning-parser qwen3` / `qwen3_coder`** | `Qwen3Detector` splits on `<think>`/`</think>`, which are real special tokens here (248068/248069), so it is not mis-anchored; the known behavior on this family is reasoning text landing in `content`, as the model card itself reports | probe B: no parsers, template still applied — salad there means the chat path, not the parser |
| 5 | **`--trust-remote-code`** | a custom tokenizer/model class overriding the family's | falsified: no `.py` file in any of the four repos, `tokenizer_class` is `Qwen2Tokenizer` in all of them |

The pairing is deliberate: A is the weights with nothing else in the path, B is the chat path with no
parser. Coherent on A alone means the export is sound and the drafter's head handling is the defect
(hypothesis 2), so the fix is to serve this target with no drafter until SGLang supports an fp8 head
in the DFLASH draft sampler, or to use the export that dequantizes `lm_head` to bf16
(`Sherlock-Comms/…-DFlash2-RTX-Spark`, ranked 4 in the survey). Salad on A means the export itself is
the defect (hypothesis 1) and no drafter, template or parser work can rescue it: the arm stays a
recorded negative, and the follow-ups are an engine bump that implements the algo, or a re-export
whose `quantization_config` only uses implemented names. Salad on B but coherent on A means the defect
is in the chat path, which is the cheapest outcome to fix — drop the parser or pin
`enable_thinking=false` and re-measure.

#### The two probe arms

Both `sparkrun recipe validate`-clean, both no-drafter (speculative keys absent, not neutralised), both
carrying the eval-only banner and pin from their parent arm:

| recipe | drafter | template | parsers | probe |
|---|---|---|---|---|
| `zz-dealignai-ornith-1.5-122b-nvfp4-uncensored-dflash2-sglang.yaml` | DFlash2, 4 tokens | on | both | failed: salad |
| `zz-dealignai-ornith-1.5-122b-nvfp4-uncensored-nospec-rawchat-sglang.yaml` | **none** | **bypassed** (raw completion) | both | A |
| `zz-dealignai-ornith-1.5-122b-nvfp4-uncensored-nospec-noparsers-sglang.yaml` | **none** | on | **none** | B |

There is no SGLang serve flag that turns the tokenizer's template off, so A's template knob is
exercised at probe time: it is queried on `/v1/completions` with a literal prompt. Its parser flags
stay on the serve line only so the two arms differ in exactly one place.

```bash
# probe A — one node, free and non-production (.31-.34 are serving)
sparkrun run recipes/ornith/zz-dealignai-ornith-1.5-122b-nvfp4-uncensored-nospec-rawchat-sglang.yaml -H .35
# rendered serve line (validated, no spec flags):
#   taskset -c 5-9,15-19 sglang serve --model-path dealignai/Ornith-1.5-122B-UNCENSORED-NVFP4 \
#     --served-model-name dealignai/Ornith-1.5-122B-UNCENSORED-NVFP4 \
#     --revision e6a1c1785949cc6e1ccd8af766f0a6148f575e6b --trust-remote-code \
#     --reasoning-parser qwen3 --tool-call-parser qwen3_coder --host 0.0.0.0 --port 8000 --tp 1 \
#     --context-length 262144 --max-running-requests 32 --kv-cache-dtype fp8_e4m3 \
#     --chunked-prefill-size 4096 --mem-fraction-static 0.80 --attention-backend flashinfer \
#     --moe-runner-backend marlin --mamba-radix-cache-strategy extra_buffer
curl -sS localhost:8000/v1/completions -H 'content-type: application/json' -d '{
  "model": "dealignai/Ornith-1.5-122B-UNCENSORED-NVFP4",
  "prompt": "The capital of France is", "max_tokens": 64, "temperature": 0 }'

# probe B — same target and engine, no parser flags
sparkrun run recipes/ornith/zz-dealignai-ornith-1.5-122b-nvfp4-uncensored-nospec-noparsers-sglang.yaml -H .35
# rendered serve line: identical to A minus `--reasoning-parser qwen3 --tool-call-parser qwen3_coder`
curl -sS localhost:8000/v1/chat/completions -H 'content-type: application/json' -d '{
  "model": "dealignai/Ornith-1.5-122B-UNCENSORED-NVFP4",
  "messages": [{"role": "user", "content": "The capital of France is"}],
  "max_tokens": 64, "temperature": 0,
  "chat_template_kwargs": {"enable_thinking": false} }'

sparkrun stop <cluster-id> -H .35   # and copy the serve log first: `sparkrun stop --all` removes it
```

Only two cells are needed: A's completion text and B's chat text. llama-benchy runs on one coherent
arm afterwards, never on a salad one. Both arms are `zz-` drafts: not in the root README index, no
decode number claimed, and neither is promoted by a coherence pass alone.
