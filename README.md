<p align="center">
<img src="assets/Little-Cedar-Group-logo-3c-dark-transparent.svg" alt="Spark Arena" width="120" />
</p>
<h2 align="center">Little Cedar Group Inference Recipes for NVIDIA DGX Spark</h2>
<p align="center">
   <a href="https://spark-arena.com"><img src="https://img.shields.io/badge/Spark_Arena-community-76b900" alt="Spark Arena" /></a>  
   <a href="https://github.com/spark-arena/sparkrun"><img src="https://img.shields.io/badge/sparkrun-CLI-1e40af" alt="sparkrun CLI" /></a>
   <a href="https://sparkrun.dev"><img src="https://img.shields.io/badge/docs-sparkrun.dev-1e40af" alt="Documentation" /></a>
   <!-- <a href="https://recipes.sparkrun.dev"><img src="https://img.shields.io/badge/browse-recipes-76b900" alt="Browse Recipes" /></a> -->
</p>

---
This is the **Little Cedar Group recipe registry** for [Sparkrun][sparkrun] from the [Little Cedar Group][littlecedar] team.

- [Little Cedar Group][littlecedar] — our resilience-focused technology company
- [Mad Science](mad-science/README.md) — Our autoresearch experiments and findings.
- [Spark Arena][spark-arena] — community benchmarking hub
- [Sparkrun][sparkrun] — our favorite tool for AI workload management
- [Sparkrun Docs][sparkrun-docs] — full Sparkrun documentation
<!-- - [Sparkrun Recipe Explorer][sparkrun-recipe-explorer] — browse and filter all recipes -->

---

# Contents
- [Install Our Registry](#install-the-registry)
- [Run Our Recipes](#run-little-cedar-groups-recipes)
- [Our Recipe Format](#recipe-format)
- [Recipe Flags](#recipe-flags)
- [Little Cedar Sparkrun Recipes](#little-cedar-sparkrun-recipes)
  - [DeepSeek V4](#deepseek-v4)
  - [Ornith 1.5](#ornith-15)
  - [Embed](#embed)
  - [Rerank](#rerank)
  - [Qwen 3x](#qwen-3x)
  - [Qwen 4x](#qwen-4x)
  - [IFM K2-Horizon](#ifm-k2-horizon)
  - [GLM 5.3](#glm-53)
  - [Decision](#decision)
  - [Explore](#explore)
  - [Cybersec](#cybersec)
- [License Policy](#license-policy)
- [Mechanics](#mechanics)
- [References](#references)

# Install the Registry

You can install our registry in Sparkrun like this:
```bash
sparkrun registry add @littlecedar https://github.com/littlecedar/sparkrun-registry
```
After reviewing the recipes you'd like to run, it is recommended to trust our registry like this:
```bash
sparkrun registry trust @littlecedar
```

# Run Little Cedar Group's Recipes

> [!IMPORTANT]
> Recipes flagged with `📜` require the operator to accept the upstream model repository release on Hugging Face's website. Downloads require setting `HF_TOKEN` after accepting the release. See [License Policy](#license-policy) for more information about licensing.

Our recipes are accessed with the `@littlecedar` prefix.

```bash
# List available recipes
sparkrun list @littlecedar

# Run a recipe
sparkrun run @littlecedar/our-awesome-recipe

# Check VRAM requirements before launching
sparkrun show @littlecedar/our-awesome-recipe
# or
sparkrun recipe vram @littlecedar/our-awesome-recipe
```

# Recipe Format

Our recipes follow the standard Sparkrun recipe schema with some additional metadata and formatting divergences, for example we use YAML `>` instead of `|` for readability and resilience. See
the [recipe authoring docs](https://sparkrun.dev/recipes/format/) for the full specification.

# Recipe Flags

Flags indicate characteristics of the model, runtime, mods, and recipe, and are added by us to `metadata.flags:` in the recipe's YAML.

| Flag | Tag           | Description                              |
|:-----|:--------------|:-----------------------------------------|
| ✨   | official      | Uses official weights                    |
| 🌲   | lcg_favorite  | Little Cedar Group:tm: Favorite          |
| 🚀   | fast          | C1 Fast: >= 50 t/s TP=1, >= 40 t/s TP=2  |
| 🐢   | slow          | C1 Slow: < 40 t/s (any node count)       |
| 🚚   | large_context | Large context (>= 512k tokens)           |
| 🔧   | tools         | Excellent tool use                       |
| 🧠   | reasoning     | Excellent reasoning capability           |
| 🦾   | agent         | Excellent agentic capability             |
| ⚖   | judge         | Judgement model                          |
| 🚮   | classifier    | Classification model                     |
| 🖥   | cpu           | CPU-only runtime model                   |
| 🤏   | smol          | Small model                              |
| 1    | single_user   | Low concurrency, single-user recommended |
| 👀   | vision        | Model has vision capability              |
| 👂   | listening     | Model has listening capability           |
| 🗺   | world         | Model has world-aware capability         |
| 👄   | speech        | Model has speech generation capability   |
| 📸   | image         | Model has image generation capability    |
| 🎥   | video         | Model has video generation capability    |
| 🎼   | audio         | Model has audio generation capability    |
| 📶   | embedding     | Model has embedding capability           |
| 🔃   | reranking     | Model has reranking capability           |
| 🏴   | uncensored    | Uncensored model                         |
| 📜   | license       | Gated, non-commercial, or `other`        |
| 🚩   | dangerous     | Dangerous and may crash your Sparks!     |    
| 💀   | broken        | Currently broken                         |

# Little Cedar Sparkrun Recipes

_Brought to you by Little Cedar Group._

These are the recipes we are using in the office on our humble 6-node DGX Spark cluster.

## DeepSeek V4

| Recipe                                       | Flags | C1 t/s | C2 t/s | C5 t/s | C10 t/s |  Size |  Mem% | TP | Model Cards                                                      |
|:---------------------------------------------|:------|-------:|-------:|-------:|--------:|------:|------:|---:|:-----------------------------------------------------------------|
| deepseek-v4.1-flash-knapcio-tp4-1m-sglang    | ✨🚚🌲👀  |   46.5 |      — |      — |       — | 510GB |   80% |  4 | [Model][deepseek-ai/DeepSeek-V4.1-Flash]                         |
| deepseek-v4.1-flash-tensorfold-tp2-1m-sglang | 🚀🚚1👀† |   73.0 |      — |      — |       — | 413GB | 84%\* |  2 | [Model][littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram] |

* _`*` Mem% = the engine's boot-log allocator ceiling (107.8 GiB of 128 GB); this recipe sets no util._
* _`†` vision runs in the engine, not on the HTTP surface: an `image_url` part still gets HTTP 400
from the served chat template (`attic/ds4/AGENTS.md` §12.14)._

## Ornith 1.5

| Recipe                                           | Flags   | C1 t/s | C2 t/s | C5 t/s | C10 t/s |                 Size | Mem% | TP | Model Cards                                                                            |
|:-------------------------------------------------|:--------|-------:|-------:|-------:|--------:|---------------------:|-----:|---:|:---------------------------------------------------------------------------------------|
| littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm | 🌲👀🧠🦾🔧   |  41.86 |      — |      — |       — |                251GB |  80% |  4 | [Model][littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft]                                   |
| ornith-1.5-35b-a3b-nvfp4-dflash2-sglang          | ✨🚀🌲👀🧠🦾🔧 |  101.8 |  153.1 |  217.4 |   244.2 | 23.5GB + 1.1GB draft |  85% |  1 | [Model][ornith-ai/Ornith-1.5-35B-A3B-NVFP4] [Draft][jzinno/Ornith-1.5-35B-A3B-DFlash2] |
| ornith-1.5-9b-nvfp4-dflash-sglang                | ✨🚀🤏👀🧠🦾🔧 |     55 |  101.1 |  159.0 |   148.9 |  8.8GB + 2.6GB draft |  85% |  1 | [Model][ornith-ai/Ornith-1.5-9B-NVFP4] [Draft][ornith-ai/Ornith-1.5-9B-DFlash]         |

* _Ornith ladder cells are @ d0, pp 2048, tg 128, n=5, decode rows read from each receipt's `--output` file. The **35B** row is the 2026-10-16 re-run — `~/benchmarks/ornith-35b-suite-20261016/ornith35b-ladder.json`, per-stream 101.8 / 79.8 / 54.5 / 34.2 t/s, ttfr 303 / 582 / 1208 / 1973 ms (the 2026-10-15 pass read C2/C5/C10 158.2 / 220.4 / 249.9, i.e. within 3 %); the **9B** row is the 2026-10-15 pass — `bench_92725c90d298`, `~/benchmarks/ornith-9b-ladder-20261015/perf-ladder.yaml`, same-boot C1 58.0._

## Embed

| Recipe                                   | Flags | C1 u/s | C2 u/s | C5 u/s | C10 u/s |   Size | Mem% |            API | TP | Model Cards                                    |
|:-----------------------------------------|:------|-------:|-------:|-------:|--------:|-------:|-----:|---------------:|---:|:-----------------------------------------------|
| qwen3-vl-embedding-2b-vllm-b12x          | 🚀🌲👀📶🤏 |   38.2 |   45.5 |   85.2 |   102.4 | 4.26GB |  25% | /v1/embeddings |  1 | [Model][Qwen/Qwen3-VL-Embedding-2B]            |
| qwen3-vl-embedding-8b-awq-4bit-vllm-b12x | 🚀🌲👀📶🤏 |   15.9 |      — |      — |       — | 6.01GB |  30% | /v1/embeddings |  1 | [Model][gonuit/Qwen3-VL-Embedding-8B-AWQ-4bit] |

* _The 2B row's C1–C10 are 2026-10-16 units/s from `benchmarking/pooling-ladder-embed.yaml` (c 1/2/5/10, 100 requests, ~256-token inputs, 5 warmups, salted, `-b dimension_check=2048`) — `~/benchmarks/pins-20261016/embed2b-ladder.json`. That is **not** the 8B row's shape, so the two rows' cells are not comparable._
* _C1 from the lane's `.scratch/embed/csweep8b-order1-c1.json` receipt._

## Rerank

| Recipe                         | Flags | C1 u/s | C2 u/s | C5 u/s | C10 u/s |   Size | Mem% |       API | TP | Model Cards                        |
|:-------------------------------|:------|-------:|-------:|-------:|--------:|-------:|-----:|----------:|---:|:-----------------------------------|
| qwen3-vl-reranker-2b-vllm-b12x | 🚀🌲👀🔃🤏 |  100.6 |      — |      — |       — | 4.27GB |  30% | /v1/score |  1 | [Model][Qwen/Qwen3-VL-Reranker-2B] |
| qwen3-vl-reranker-8b-vllm-b12x | 🌲👀🔃🤏  |      — |      — |      — |       — | 17.6GB |  30% | /v1/score |  1 | [Model][Qwen/Qwen3-VL-Reranker-8B] |

* _C1 from the lane's `.scratch/embed/conc-1.json` receipt._

## Qwen 3x

| Recipe                                | Flags | C1 t/s | C2 t/s | C5 t/s | C10 t/s |                 Size |  Mem% | TP | Model Cards                                                                                                                                                                                            |
|:--------------------------------------|:------|-------:|-------:|-------:|--------:|---------------------:|------:|---:|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| qwen3.8-27b-nvfp4-dflash2-sglang      | 🌲🚀👀   |   33.8 |   57.4 |   89.5 |   100.9 | 21.9GB + 3.9GB draft |   85% |  1 | [Model][RadixArk/Qwen3.8-27B-NVFP4] [Draft][z-lab/Qwen3.8-27B-DFlash2] — ladder 2026-10-17 (`bench_355eee9f476f`), receipt `~/benchmarks/ladders-solo-20261017/`                                       |
| qwen3-coder-next-int4-autoround-vllm  | 🌲🚀    |   70.4 |  114.0 |  177.1 |   249.5 |               43.6GB |   85% |  1 | [Model][Intel/Qwen3-Coder-Next-int4-AutoRound] — vLLM; 2.1× DFlash2 C1; 2026-10-16 ladder, receipt `~/benchmarks/pins-20261016/qwen3coder-ladder.yaml`                                                 |
| qwen3.8-27b-mlx4bit-tensorfold-sglang | 👀     |   44.8 |   57.7 |   64.4 |    65.6 | 16.1GB + 3.9GB draft | 30%\* |  1 | [Model][TensorFold/Qwen3.8-27B-MLX-4bit] [Draft][z-lab/Qwen3.8-27B-DFlash2] — **TensorFold** engine; ladder 2026-10-17 (`bench_b10e422bb046`), arc 94.0%/gsm8k 96.5%, TEB 100, bfcl 85.7%‡             |

* _`‡` its `tools` (bfcl) leg ran at bfcl-eval's 512-token completion default — the suite passed no `--max-tokens` until 2026-10-17 — so 25 of the 400 parallel questions came back with no call and the figure is budget-annotated, not a capability ceiling; a 4096 re-run is queued. 
* `*` no recipe util — the engine's 37.77 GiB startup estimate of 128 GB._
* _The `qwen3.8-27b-nvfp4-dflash2` row mixes boots: its **C1 33.8** is the arm's pre-loader-fix single-point reference (2026-10-15) and C2/C5/C10 are the 2026-10-17 re-measure, within noise of the shipped-boot ladder the lane doc also holds (31.7 / 54.3 / 95.5 / 94.5, `bench_017bdc06394d`)._

## Qwen 4x

| Recipe                                           | Flags | C1 t/s | C2 t/s | C5 t/s | C10 t/s |  Size | Mem% | TP | Model Cards                                                                                                                     |
|:-------------------------------------------------|:------|-------:|-------:|-------:|--------:|------:|-----:|---:|:--------------------------------------------------------------------------------------------------------------------------------|
| qwen3.8-flash-next-nvfp4-labquant-sglang         | 🌲🚀👀   |   40.3 |      — |      — |       — | 106GB |  80% |  2 | [Model][local-inference-lab/Qwen3.8-Flash-Next-NVFP4]                                                                           |
| qwen3.8-flash-next-nvfp4-solo-vllm-b12x          | 🌲     |   33.9 |      — |      — |       — | 106GB |  80% |  1 | [Model][local-inference-lab/Qwen3.8-Flash-Next-NVFP4] — **solo TP=1, PLE table streamed from disk**                             |
| qwen3.8-flash-next-nvfp4-labquant-highcon-sglang | 🌲🚀👀   |      — |      — |      — |       — | 106GB |  80% |  2 | [Model][local-inference-lab/Qwen3.8-Flash-Next-NVFP4] — **aggregate regime: d8192 decode 89.1 t/s at k=16 (n=7), 72.9 at k=24** |

## IFM K2-Horizon

| Recipe                       | Flags | C1 t/s | C2 t/s | C5 t/s | C10 t/s |                   Size | Mem% | TP | Model Cards                                                   |
|:-----------------------------|:------|-------:|-------:|-------:|--------:|-----------------------:|-----:|---:|:--------------------------------------------------------------|
| k2-horizon-0.9b-bf16-sglang  | ✨🚀🤏🧠🔧 |   77.6 |  181.6 |  317.6 |   503.9 |                 2.16GB |  85% |  1 | [Model][IFM/K2-Horizon-0.9B]                                  |
| k2-horizon-7b-fp8-uno-sglang | 🚀🤏🧠🔧🦾 |   32.4 |   56.1 |   94.0 |   126.0 | 11.1GB + 1.4GB adapter |  82% |  1 | [Model][IFM/K2-Horizon-7B-FP8] — **UNO spec decode, fastest** |

## GLM 5.3

**No shipped recipe** — this lane is runbooks only; see [`recipes/glm/README.md`](recipes/glm/README.md) for the TensorFold runbook notes and [`attic/glm/`](attic/glm/ARMS-MANIFEST.md) for the arm archived there.

## Decision

| Recipe                      | Flags | Accuracy | C1 req/s | C2 req/s | C5 req/s | C10 req/s |   Size | Mem% |             API | TP | Model Cards                            |
|:----------------------------|:------|---------:|---------:|---------:|---------:|----------:|-------:|-----:|----------------:|---:|:---------------------------------------|
| jev-9b-decision-vllm        | 🤏🚮    |    67.0% |      7.6 |        — |        — |         — | 18.4GB |  92% | /v1/completions |  1 | [Model][autotrust/JEV-9B]              |
| clef-flash-decision-sglang  | 🤏🚮    |    70.3% |      4.9 |        — |        — |         — | 19.1GB |  82% |   /v1/systemone |  1 | [Model][Cloudflare/clef-flash]         |
| kai-0.6b-decision-vllm-srun | 🤏🖥🚮   |    47.5% |        — |        — |        — |         — |  1.5GB |    — |   /v1/systemone |  1 | [Model][vllm-sr/Decision-2.0-Kai-0.6B] |
| sol-2b-decision-vllm-srun   | 🤏🖥🚮   |      55% |        — |        — |        — |         — |  4.8GB |    — |   /v1/systemone |  1 | [Model][vllm-sr/Decision-2.0-Sol-2B]   |

* _Mem% is what the launches served at: neither recipe renders a util flag, so vLLM ran at `--gpu-memory-utilization=0.92` and SGLang at `mem_fraction_static=0.82` (the arms' serve logs). 
* The two `srun` arms are CPU-only (`--device cpu`), so no device cap applies._

## Explore

| Recipe                                        | Flags |      C1 t/s | C2 t/s | C5 t/s | C10 t/s |                 Size |  Mem% |                  API | TP | Model Cards                                                                                                                                                                                                                            |
|:----------------------------------------------|:------|------------:|-------:|-------:|--------:|---------------------:|------:|---------------------:|---:|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ling-3.0-flash-int4-dspark-sglang             | 🧠     |        45.5 |      — |      — |       — |   77GB + 2.7GB draft |   80% | /v1/chat/completions |  1 | [Model][inclusionAI/Ling-3.0-flash-int4] [Draft][inclusionAI/Ling-3.0-flash-dspark] — **boot-verified, house battery 37/37; 262k needle-verified at mem-fraction 0.80**                                                                |
| kolibri-1-78b-fp8-vllm                        | ✨🧠🔧   |        47.3 |      — |      — |       — |                 79GB |   78% | /v1/chat/completions |  1 | [Model][Aleph-Alpha/Kolibri-1] — **boot-verified, house battery 36/37 (37/37 union across token budgets)**                                                                                                                             |
| poolside-laguna-xs-2.1-nvfp4-dflash-vllm      | ✨🧠🔧   |        55.3 |   83.1 |  133.7 |   141.3 | 21.6GB + 0.9GB draft |   55% | /v1/chat/completions |  1 | [Model][poolside/Laguna-XS-2.1-NVFP4] [Draft][poolside/Laguna-XS-2.1-DFlash] — **boot 2026-10-14; suite 2026-10-17: house 35/37, needle 2/3 @32k+131k, 3/3 @262k, arc 66.0%/gsm8k 90.5%, bfcl 60.1%, TEB 97; contract fail @262k**     |
| poolside-laguna-s-2.1-nvfp4-dflash-vllm       | ✨🧠🔧📜  |        20.5 |      — |      — |       — | 99.7GB + 2.2GB draft |   85% | /v1/chat/completions |  1 | [Model][poolside/Laguna-S-2.1-NVFP4] [Draft][poolside/Laguna-S-2.1-DFlash-NVFP4] — **boot-verified; 120k capped-context single-tenant arm, battery 32/37**                                                                             |
| humanizer-12b-vllm                            | 🐢     |         7.6 |      — |      — |       — |               88GB ‡ |   85% |      /v1/completions |  1 | [Model][jialinyyzz/humanizer] — **text-rewriting arm, `/v1/completions` only (no chat template), off the lane's reasoning/tool brief**                                                                                                 |
| qwen-image-2.1-turbo-7b-bf16-diffusers-script | 🐢📜    | 0.088 img/s |      — |      — |       — |               32.5GB | 29%\* |       POST /generate |  1 | [Model][Qwen/Qwen-Image-2.1-Turbo] — **text-to-image + editing** under a diffusers script launcher (no sglang/vLLM engine); **NON-COMMERCIAL license, banner-marked eval-only**; boot-verified 2026-10-14, ~11.4 s/image @1024²/8-step |
| mellum2.1-12b-a2.5b-bf16-thinking-vllm        | ✨🧠🔧   |        42.3 |   67.2 |   99.9 |   135.6 |               24.3GB |   55% | /v1/chat/completions |  1 | [Model][JetBrains/Mellum2.1-12B-A2.5B-Thinking] — **boot-verified 2026-10-15, house battery 36/37 (easy 18/19 — `needle-1`; hard 18/18)**; ladder @ d0 pp2048 tg128 n=5: C2 67.2 / C5 99.9 / C10 135.6 t/s                             |
| mellum2.1-12b-a2.5b-q4km-thinking-llamacpp    | ✨🧠🔧   |       111.9 |  151.1 |  208.0 |   146.4 |               8.07GB |     — | /v1/chat/completions |  1 | [Model][JetBrains/Mellum2.1-12B-A2.5B-Thinking-GGUF] — **llama.cpp arm; boot 2026-10-17: house 37/37; needle 3/3 by union @32k+131k (32k: depth 50 at 4,096 tokens, depth 90 thinking off); arc 77.0%/gsm8k 93.5%, bfcl 88.3%, TEB 97**|

* _`‡` 88 GB on disk, of which 24 GB loads.
* `*` no recipe util — peak reserved memory, 37.68 GiB of 128 GB. 
* `📜` Qwen-Image is NON-COMMERCIAL (`qwen-research`, eval-only under the lane banner); the Laguna-S draft declares no license, `other` in its BF16 sibling. 
* The llama-cpp arm caps nothing (llama.cpp sizes its own pool from `--ctx-size`/`--parallel`), so its Mem% cell is `—`. **The llama-cpp row's bfcl cell is the 4096-budget leg** (`--bfcl-max-tokens 4096`, `~/benchmarks/mellum-gguf-tools4096-20261017/`): at the pre-`3ac9581` 512 default the same arm scored 73.5 %, with 179 of the two parallel categories' 400 questions cut to no call at all; at 4096 only six are cut and the residual loss there is multi-call shape, not budget._

## Cybersec

| Recipe                                                      | Flags | C1 t/s | C2 t/s | C5 t/s | C10 t/s |                 Size |  Mem% | TP | Model Cards                                                                                                                                                               |
|:------------------------------------------------------------|:------|-------:|-------:|-------:|--------:|---------------------:|------:|---:|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| qwen3.8-27b-uncensored-nvfp4-sglang                         | 🚀👀🏴📜  |   10.2 |      — |      — |       — |               24.7GB |   85% |  1 | [Model][orcarouter/Qwen3.8-27B-Uncensored-NVFP4] — **positive**, boots, battery 37/37                                                                                     |
| qwen3.8-27b-ablit-cyber-unlock-nvfp4-dflash2-sglang         | 🚀👀🏴📜  |   33.3 |   49.4 |   84.6 |    92.9 | 20.6GB + 3.9GB draft |   85% |  1 | [Model][sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4] [Draft][z-lab/Qwen3.8-27B-DFlash2] — **positive**, battery 37/37; 2026-10-17 ladder `bench_3ee8fda63ada`|
| deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang | 🚀🚚1🏴📜 |   63.7 |      — |      — |       — |        119GB graft | 85%\* |  2 | [Model][drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed] — **positive** (combined EXL3 pack, shared with the ds4 TP=2 arm, + `attn.wo_b` sidecar graft), battery 36/37, 1M ctx         |

* _`*` no recipe util — the arm's documented `≤ 0.85` ceiling. 
* `📜` every arm in this lane is gated on the Hub (`gated: auto`): each node needs an `HF_TOKEN` with that repo's release accepted. 
* The AEON row's **C1 33.3** is its earlier single-point figure — **C2/C5/C10 are the 2026-10-17 ladder** (`bench_3ee8fda63ada`), the lane's first._

# License Policy

The registry carries **recipes and mods, not weights**: recipes ship repo ids, revisions and wiring, and each
downloader fetches the checkpoint from the Hub under that repo's own terms. **Third-party-downloadable** means
fetchable from a public Hub repo on those terms, with the registry shipping only the recipe (with an flag indicating special licensing). Derivatives of third-party bases are carried when their own
license permits redistribution. Where the registry only *references* upstream work (for example, the ds4 graft mod fetches
the author's script at a pinned revision) it redistributes nothing. Vendored images and mods stay under
their upstream licenses. Non-commercial and gated checkpoints are carried only where their license allows the
intended use. 

# Mechanics

See [MECHANICS.md](recipes/MECHANICS.md) for the sparkrun command-template rules every recipe author needs.

# References

* https://spark-arena.com

<!-- Links -->
[littlecedar]: https://littlecedar.net
[sparkrun]: https://sparkrun.dev
[sparkrun-docs]: https://sparkrun.dev/getting-started/quick-start/
[sparkrun-recipe-explorer]: https://recipes.sparkrun.dev
[spark-arena]: https://spark-arena.com
[RadixArk/Qwen3.8-27B-NVFP4]: https://huggingface.co/RadixArk/Qwen3.8-27B-NVFP4
[local-inference-lab/Qwen3.8-Flash-Next-NVFP4]: https://huggingface.co/local-inference-lab/Qwen3.8-Flash-Next-NVFP4
[Qwen/Qwen3-VL-Embedding-2B]: https://huggingface.co/Qwen/Qwen3-VL-Embedding-2B
[gonuit/Qwen3-VL-Embedding-8B-AWQ-4bit]: https://huggingface.co/gonuit/Qwen3-VL-Embedding-8B-AWQ-4bit
[Qwen/Qwen3-VL-Reranker-2B]: https://huggingface.co/Qwen/Qwen3-VL-Reranker-2B
[Qwen/Qwen3-VL-Reranker-8B]: https://huggingface.co/Qwen/Qwen3-VL-Reranker-8B
[littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft]: https://huggingface.co/littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft
[ornith-ai/Ornith-1.5-35B-A3B-NVFP4]: https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B-NVFP4
[jzinno/Ornith-1.5-35B-A3B-DFlash2]: https://huggingface.co/jzinno/Ornith-1.5-35B-A3B-DFlash2
[IFM/K2-Horizon-0.9B]: https://huggingface.co/IFM/K2-Horizon-0.9B
[IFM/K2-Horizon-7B-FP8]: https://huggingface.co/IFM/K2-Horizon-7B-FP8
[Intel/Qwen3-Coder-Next-int4-AutoRound]: https://huggingface.co/Intel/Qwen3-Coder-Next-int4-AutoRound
[littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram]: https://huggingface.co/littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram
[autotrust/JEV-9B]: https://huggingface.co/autotrust/JEV-9B
[Cloudflare/clef-flash]: https://huggingface.co/Cloudflare/clef-flash
[inclusionAI/Ling-3.0-flash-int4]: https://huggingface.co/inclusionAI/Ling-3.0-flash-int4
[inclusionAI/Ling-3.0-flash-dspark]: https://huggingface.co/inclusionAI/Ling-3.0-flash-dspark
[vllm-sr/Decision-2.0-Kai-0.6B]: https://huggingface.co/vllm-sr/Decision-2.0-Kai-0.6B
[vllm-sr/Decision-2.0-Sol-2B]: https://huggingface.co/vllm-sr/Decision-2.0-Sol-2B
[Aleph-Alpha/Kolibri-1]: https://huggingface.co/Aleph-Alpha/Kolibri-1
[deepseek-ai/DeepSeek-V4.1-Flash]: https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash
[orcarouter/Qwen3.8-27B-Uncensored-NVFP4]: https://huggingface.co/orcarouter/Qwen3.8-27B-Uncensored-NVFP4
[sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4]: https://huggingface.co/sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4
[drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed]: https://huggingface.co/drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed
[poolside/Laguna-XS-2.1-NVFP4]: https://huggingface.co/poolside/Laguna-XS-2.1-NVFP4
[poolside/Laguna-XS-2.1-DFlash]: https://huggingface.co/poolside/Laguna-XS-2.1-DFlash
[poolside/Laguna-S-2.1-NVFP4]: https://huggingface.co/poolside/Laguna-S-2.1-NVFP4
[poolside/Laguna-S-2.1-DFlash-NVFP4]: https://huggingface.co/poolside/Laguna-S-2.1-DFlash-NVFP4
[jialinyyzz/humanizer]: https://huggingface.co/jialinyyzz/humanizer
[Qwen/Qwen-Image-2.1-Turbo]: https://huggingface.co/Qwen/Qwen-Image-2.1-Turbo
[JetBrains/Mellum2.1-12B-A2.5B-Thinking]: https://huggingface.co/JetBrains/Mellum2.1-12B-A2.5B-Thinking
[JetBrains/Mellum2.1-12B-A2.5B-Thinking-GGUF]: https://huggingface.co/JetBrains/Mellum2.1-12B-A2.5B-Thinking-GGUF
[ornith-ai/Ornith-1.5-9B-NVFP4]: https://huggingface.co/ornith-ai/Ornith-1.5-9B-NVFP4
[ornith-ai/Ornith-1.5-9B-DFlash]: https://huggingface.co/ornith-ai/Ornith-1.5-9B-DFlash
[TensorFold/Qwen3.8-27B-MLX-4bit]: https://huggingface.co/TensorFold/Qwen3.8-27B-MLX-4bit
[z-lab/Qwen3.8-27B-DFlash2]: https://huggingface.co/z-lab/Qwen3.8-27B-DFlash2
