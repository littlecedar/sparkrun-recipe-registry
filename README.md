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
| deepseek-v4.1-flash-knapcio-tp4-1m-sglang    | ✨🚚🌲👀  |   67.2 |   89.9 |  113.4 |   115.4 | 510GB |   78% |  4 | [Model][deepseek-ai/DeepSeek-V4.1-Flash-1017] — v2.4 image on the 1017 base; **C1 is the pooled 67.18 ± 6.97** t/s (n=25, CV 10.4 %, four same-config takes in the 2026-10-18 TP=4 window), not the single-boot 81.0 it replaces; ladder + suite `~/benchmarks/tp4-20261018/` (`knapcio-ladder`, `knapcio-ladder-suiteboot`): house 36/37, needle 3/3 @32k+131k+983k, TEB 90; depth-0 C4 118.9 / C8 107.5 / C16 115.9 at parity with the V4.1 base |
| deepseek-v4.1-flash-tensorfold-tp2-1m-sglang | 🚀🚚1👀  |   66.4 |   47.8 |   44.8 |    48.4 | 385GB | 84%\* |  2 | [Model][LibertAIDAI/DeepSeek-V4.1-Flash-1017-EXL3-2.9bpw] — 1017 refresh; interleaved ladder 2026-10-18 (5 runs/cell, `~/benchmarks/ds4-1017-ab-interleaved-20261018/`) |

* _`*` Mem% = the engine's boot-log allocator ceiling (107.8 GiB of 128 GB); this recipe sets no util._
* _The knapcio row's **C2/C5/C10 are the lane's first** (2026-10-18, 5 runs/cell, `benchmarking/concurrency-ladder.yaml`, decode rows only): boot A 89.89 ± 3.57 / 113.44 ± 6.84 / 115.36 ± 6.62 and boot C 86.40 ± 3.59 / 108.78 ± 14.19 / 116.27 ± 6.22 t/s (sample sd, n=5; the receipt JSON's own `tg_throughput.std` is the population sd, 0.894× these) — `~/benchmarks/tp4-20261018/`, deployment `a2e141223b52793c_7afff0589a33` (three boots under one id). Its C1 cell is the **pool of four takes** (69.65 n=5, 66.40 n=10, 64.16 n=5, 69.28 n=5) = 67.18 ± 6.97, CV 10.4 %, range 56.4-87.9; against the V4.1 baseline's 59.21 ± 3.54 that is +13.5 % in the means with overlapping intervals, so a v2.4-vs-1017 C1 delta is still not established — and the earlier single-boot 81.0 is 2.0 σ above the pool's mean. Ladder shape and the DSpark γ=3 negative: `recipes/ds4/README.md` §"Measured", `attic/ds4/AGENTS.md` §12.18._
* _The knapcio row's cells are the **v2.3 serve line** (0.80 static / 4096 chunks / 9.4M pin). The shipped **v2.4 line** (0.78 / 8192 / 6.85M pin, `--prefill-decode-interval` off) measured C2 88.35 / 82.02, C5 131.83 / 130.97, C10 123.49 / 119.79 t/s on two single boots — C5 +18 %, C10 +3-7 %, C2 inside the v2.3 cells' spread; every C1 cell there is cold-contaminated (first run 19-39 t/s), so the pooled C1 stands and the row keeps the v2.3 cells. The interleave flag costs 17-28 % of ladder throughput and ships off; at 6.85M the engine reports `max_total_num_tokens=6849792` with no clamp. `~/benchmarks/ds4-v24-line-20261018/`; method in [`recipes/ds4/README.md`](recipes/ds4/README.md) §"Measured: the v2.4 serve line"._

## Ornith 1.5

| Recipe                                           | Flags   | C1 t/s | C2 t/s | C5 t/s | C10 t/s |                 Size | Mem% | TP | Model Cards                                                                                                                                                                                                                |
|:-------------------------------------------------|:--------|-------:|-------:|-------:|--------:|---------------------:|-----:|---:|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm | 🌲👀🧠🦾🔧   |  41.86 |      — |      — |       — |                251GB |  80% |  4 | [Model][littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft]                                                                                                                                                                       |
| ornith-1.5-35b-a3b-nvfp4-dflash2-sglang          | ✨🚀🌲👀🧠🦾🔧 |  101.8 |  153.1 |  217.4 |   244.2 | 23.5GB + 1.1GB draft |  85% |  1 | [Model][ornith-ai/Ornith-1.5-35B-A3B-NVFP4] [Draft][jzinno/Ornith-1.5-35B-A3B-DFlash2]                                                                                                                                     |
| ornith-1.5-9b-nvfp4-dflash-sglang                | ✨🚀🤏👀🧠🦾🔧 |     55 |  101.1 |  159.0 |   148.9 |  8.8GB + 2.6GB draft |  85% |  1 | [Model][ornith-ai/Ornith-1.5-9B-NVFP4] [Draft][ornith-ai/Ornith-1.5-9B-DFlash] — ladder 2026-10-15 (`bench_92725c90d298`); suite 2026-10-18 5/5: house 37/37, needle 3/3 @32k+131k+262k, arc 91.5%/gsm8k 92.5%, bfcl 88.1% |

* _Ornith ladder cells are @ d0, pp 2048, tg 128, n=5, decode rows read from each receipt's `--output` file._
* _The **35B** row is the 2026-10-16 re-run — `~/benchmarks/ornith-35b-suite-20261016/ornith35b-ladder.json`, per-stream 101.8 / 79.8 / 54.5 / 34.2 t/s, ttfr 303 / 582 / 1208 / 1973 ms (the 2026-10-15 pass read C2/C5/C10 158.2 / 220.4 / 249.9, i.e. within 3 %)._
* _The **9B** row's C1–C10 are the 2026-10-15 pass — `bench_92725c90d298`, `~/benchmarks/ornith-9b-ladder-20261015/perf-ladder.yaml`, same-boot C1 58.0. Its quality cells are the 2026-10-18 suite on a separate boot, `~/benchmarks/ornith-9b-suite-20261018/` (`summary.json`, `bfcl.json`)._

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

| Recipe                                | Flags | C1 t/s | C2 t/s | C5 t/s | C10 t/s |                 Size |  Mem% | TP | Model Cards                                                                                                                                                                                                   |
|:--------------------------------------|:------|-------:|-------:|-------:|--------:|---------------------:|------:|---:|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| qwen3.8-27b-nvfp4-dflash2-sglang      | 🌲🚀👀   |   33.8 |   57.4 |   89.5 |   100.9 | 21.9GB + 3.9GB draft |   85% |  1 | [Model][RadixArk/Qwen3.8-27B-NVFP4] [Draft][z-lab/Qwen3.8-27B-DFlash2] — ladder 2026-10-17 (`bench_355eee9f476f`), receipt `~/benchmarks/ladders-solo-20261017/`                                              |
| qwen3-coder-next-int4-autoround-vllm  | 🌲🚀    |   70.4 |  114.0 |  177.1 |   249.5 |               43.6GB |   85% |  1 | [Model][Intel/Qwen3-Coder-Next-int4-AutoRound] — vLLM; 2.1× DFlash2 C1; 2026-10-16 ladder, receipt `~/benchmarks/pins-20261016/qwen3coder-ladder.yaml`                                                        |
| qwen3.8-27b-mlx4bit-tensorfold-sglang | 👀     |   44.8 |   57.7 |   64.4 |    65.6 | 16.1GB + 3.9GB draft | 30%\* |  1 | [Model][TensorFold/Qwen3.8-27B-MLX-4bit] [Draft][z-lab/Qwen3.8-27B-DFlash2] — **TensorFold** engine; ladder 2026-10-17 (`bench_b10e422bb046`), arc 94.0%/gsm8k 96.5%, TEB 100, bfcl 88.2% (4096-token budget) |

* _The **TensorFold** row's bfcl cell is the 2026-10-18 re-run at `--bfcl-max-tokens 4096` — 88.2 % (1094/1240), `~/benchmarks/qwen3-tf-tools4096-20261018/`; the 85.7 % it replaces was the same arm at bfcl-eval's 512-token default, `~/benchmarks/qwen3-tf-tools-20261017/`. The id-level gain/loss split is in `recipes/qwen3/README.md`._
* _`*` no recipe util — the engine's 37.77 GiB startup estimate of 128 GB._
* _The `qwen3.8-27b-nvfp4-dflash2` row mixes boots: its **C1 33.8** is the arm's pre-loader-fix single-point reference (2026-10-15) and C2/C5/C10 are the 2026-10-17 re-measure, within noise of the shipped-boot ladder the lane doc also holds (31.7 / 54.3 / 95.5 / 94.5, `bench_017bdc06394d`)._

## Qwen 4x

| Recipe                                           | Flags | C1 t/s | C2 t/s | C5 t/s | C10 t/s |  Size | Mem% | TP | Model Cards                                                                                                                     |
|:-------------------------------------------------|:------|-------:|-------:|-------:|--------:|------:|-----:|---:|:--------------------------------------------------------------------------------------------------------------------------------|
| qwen3.8-flash-next-nvfp4-labquant-sglang         | 🌲🚀👀   |   39.9 |   69.4 |   95.0 |   104.5 | 106GB |  80% |  2 | [Model][local-inference-lab/Qwen3.8-Flash-Next-NVFP4]                                                                           |
| qwen3.8-flash-next-nvfp4-solo-vllm-b12x          | 🌲     |   33.9 |  55.49 |  64.61 |   62.04 | 106GB |  80% |  1 | [Model][local-inference-lab/Qwen3.8-Flash-Next-NVFP4] — **solo TP=1, PLE table streamed from disk**                             |
| qwen3.8-flash-next-nvfp4-labquant-highcon-sglang | 🌲🚀👀   |      — |      — |      — |       — | 106GB |  80% |  2 | [Model][local-inference-lab/Qwen3.8-Flash-Next-NVFP4] — **aggregate regime: d8192 decode 89.1 t/s at k=16 (n=7), 72.9 at k=24** |

* _The solo TP=1 row's **C1 33.9** is the 2026-10-14 decode-triage C1 (33.92 ± 1.73, pre-pin); **C2/C5/C10 are the 2026-10-18 ladder** (`bench_6b35f675861a`, receipt `~/benchmarks/ladders-solo-20261018/`), whose same-boot C1 is 34.04 — inside that cell's ±2.84. C10 (62.04) sits below C5 (64.61) because `max_num_seqs: 8` binds at ten streams, not because the KV pool is short._
* _The labquant TP=2 ladder is **39.90 ± 1.48 / 69.45 ± 7.85 / 94.98 ± 8.97 / 104.45 ± 3.00 t/s** @ d0, n=5 per cell (`bench_684c21a7cd8a`, receipt `~/benchmarks/qwen4-tp2-20261018/b1-cutlass-concurrency-ladder.{yaml,json}`, decode rows of the `--output` file). Its same-boot C1 reproduces the 2026-10-14 baseline (40.32 ± 1.94) inside the cell σ; per-request decode falls 39.90 → 15.78 t/s by c10 while the aggregate keeps rising._

## IFM K2-Horizon

| Recipe                           | Flags | C1 t/s | C2 t/s | C5 t/s | C10 t/s |                   Size | Mem% | TP | Model Cards                                                                                                                                                                        |
|:--------------------------------|:------|-------:|-------:|-------:|--------:|-----------------------:|-----:|---:|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| k2-horizon-0.9b-bf16-sglang      | ✨🚀🤏🧠🔧 |   77.6 |  181.6 |  317.6 |   503.9 |                 2.16GB |  85% |  1 | [Model][IFM/K2-Horizon-0.9B]                                                                                                                                                       |
| k2-horizon-7b-fp8-uno-sglang     | 🚀🤏🧠🔧🦾 |   32.4 |   56.1 |   94.0 |   126.0 | 11.1GB + 1.4GB adapter |  82% |  1 | [Model][IFM/K2-Horizon-7B-FP8] — **UNO spec decode, fastest**; `fp8_e4m3` KV accuracy gate passes on `triton` (fa4 cannot carry fp8 KV): house 36/37 · GSM8K 188/200 · ARC 179/200 |
| k2-horizon-0.9b-bf16-uno-sglang  | ✨🚀🤏🧠🔧 |  123.2 |  205.2 |  388.4 |   534.3 | 2.16GB + 224MB adapter |  82% |  1 | [Model][IFM/K2-Horizon-0.9B] + [Uno][IFM/K2-Horizon-0.9B-Uno] — **native UNO spec decode**: accept len 2.75 d0 / 2.64 d8192 (break-even ~2.07), 1.56× / 1.33× its same-node plain+fa4 control (79.0 / 68.0); ladder 118.5/205.2/388.4/534.3 vs control 78.6/178.8/343.3/500.1; house 33/37 · GSM8K 173/200 · ARC 144/200 (base 31/37 · 174/200 · 133/200 — ARC +11 is an open item, not a gain) |

* _The 7B row's fp8-KV gate is an accuracy pass, not a throughput claim: it ran at `attention_backend: triton`, because the shipped `fa4` asserts Q/K dtype equality and cannot serve bf16 queries into an fp8 cache, with a same-backend bf16-KV control beside it — `~/benchmarks/sweep2-20261018/` (`ifm-7b-fp8kv/`, `ifm-7b-ctl/`). The row's C1–C10 are the fa4 arm._
* _The **0.9B UNO** row is one boot (2026-10-18): C1 cells `bench_a42c59ba1ec8`, ladder `bench_ddb8a41a69d3`, decode rows only, receipt `~/benchmarks/ifm-09b-uno-20261018/`. Its control is the same recipe booted on the same node with `-o attention_backend=fa4` (`control-fa4-*`): 79.0 / 68.0 at C1 and 78.6 / 178.8 / 343.3 / 500.1 on the ladder, against the recorded flashinfer base's 80.4 / 181.6 / 317.6 / 503.9 — fa4-vs-flashinfer is a wash (−1.7 %), so the gain is UNO's. The ARC cell (+11 items, ≈1.8 SE) is **not claimed as an improvement**: it came with more truncations than the base and is most likely verify-batch numerics; settling it needs an item-level diff against a same-window plain-fa4 control, which was not taken._

## GLM 5.3

| Recipe                                           | Flags   | C1 t/s | C2 t/s | C5 t/s | C10 t/s |                 Size |  Mem% | TP | Model Cards                                                                                                                                                                                                                |
|:-------------------------------------------------|:--------|-------:|-------:|-------:|--------:|---------------------:|------:|---:|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang      | 🚚🚀🧠🔧👀   |   83.0 |  102.4 |   79.5 |    73.4 |  176GB + 2.3GB draft | 41%\* |  4 | [Model][Mia-AiLab/GLM-5.3-Flash-EXL3-4bpw-TensorFold] [Draft][incoai/GLM-5.3-Flash-DFlash2] — **boot-verified 2026-10-18**: TTR 309.6 s, KV pool 5,834,752 at 8 streams; ladder C1 83.0 / C2 102.4 / C5 79.5 / C10 73.4 t/s. The trial 98.4 t/s single-stream does **not** reproduce on the recipe path (83.0; 76.0 ex-warm-up) |
| glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang      | 🚚🧠🔧      |   31.7 |   25.3 |    —   |    —   |       273GB | 94%\* |  4 | [Model][bertholomus/GLM-5.3-EXL3-3.0bpw] — **boot-verified 2026-10-18**: full 753B at EXL3 3.0bpw, `/v1/models` at 240 s, engine load 308.7 s; c1 31.7 t/s, c2 25.3 and c4 40.6 aggregate tg (per-request 14.5 / 11.4); 100,559-token prompt TTFT 258.4 s (1M window, DCP over 4 ranks) |

* _`*` no recipe util — the engine's own startup estimate (rank 0 52.03 GiB within a 90.04 GiB ceiling; workers 50.23 GiB within 90.72-91.02 GiB)._
* _This row is the recipe's **first boot** — the lane was boot-deferred until 2026-10-18 (task `b55c050475ff4b3a_7afff0589a33`), and the recipe now carries a receipt, so it qualifies for an index row. Ladder `--skip-run` on that serve, d0 pp2048 tg128, 5 runs/cell; `±` (sample sd, n=5): C1 17.74, C2 24.01, C5 11.34, C10 8.44. C1's five runs ramp (111.3 / 84.4 / 77.6 / 79.2 / 62.6), so ex-first it is 76.0 ± 9.3. Aggregate tg peaks at C2 and falls with concurrency — the `--parallel 8` / DFlash2 verify-window shape, not a throughput claim. **Still unproven:** a quality battery through this path (the trial's 37/37 does not transfer) and any second boot. Receipts `~/benchmarks/tp4-20261018/glm-*`; method in [`recipes/glm/README.md`](recipes/glm/README.md) §"Boot receipt". The rest of the lane is runbooks plus one archived arm — [`recipes/glm/README.md`](recipes/glm/README.md), [`attic/glm/`](attic/glm/ARMS-MANIFEST.md)._
* _3.0bpw row: first boot only; c5/c10 were not run, so those cells stay empty. `94%` is the engine's own startup estimate, 96.27 GiB of a 102.86 GiB ceiling. The 2026-10-13 runbook's 35.7 t/s was an editable install of the same engine commit, not this image; receipts `~/benchmarks/glm-3bpw-boot-20261018/`._

## Decision

| Recipe                      | Flags | Accuracy | C1 req/s | C2 req/s | C5 req/s | C10 req/s |   Size | Mem% |             API | TP | Model Cards                            |
|:----------------------------|:------|---------:|---------:|---------:|---------:|----------:|-------:|-----:|----------------:|---:|:---------------------------------------|
| jev-9b-decision-vllm        | 🤏🚮    |    67.0% |      7.6 |        — |        — |         — | 18.4GB |  92% | /v1/completions |  1 | [Model][autotrust/JEV-9B]              |
| clef-flash-decision-sglang  | 🤏🚮    |    70.3% |      4.9 |        — |        — |         — | 19.1GB |  82% |   /v1/systemone |  1 | [Model][Cloudflare/clef-flash]         |
| kai-0.6b-decision-vllm-srun | 🤏🖥🚮   |    47.5% |        — |        — |        — |         — |  1.5GB |    — |   /v1/systemone |  1 | [Model][vllm-sr/Decision-2.0-Kai-0.6B] |
| sol-2b-decision-vllm-srun   | 🤏🖥🚮   |      55% |        — |        — |        — |         — |  4.8GB |    — |   /v1/systemone |  1 | [Model][vllm-sr/Decision-2.0-Sol-2B]   |

* _Mem% is what the launches served at: neither recipe renders a util flag, so vLLM ran at `--gpu-memory-utilization=0.92` and SGLang at `mem_fraction_static=0.82` (the arms' serve logs)._
* _The two `srun` arms are CPU-only (`--device cpu`), so no device cap applies._

## Explore

| Recipe                                        | Flags |      C1 t/s | C2 t/s | C5 t/s | C10 t/s |                 Size |  Mem% |                  API | TP | Model Cards                                                                                                                                                                                                                                                              |
|:----------------------------------------------|:------|------------:|-------:|-------:|--------:|---------------------:|------:|---------------------:|---:|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ling-3.0-flash-int4-dspark-sglang             | 🧠     |        45.5 |   66.2 |  100.2 |    85.9 |   77GB + 2.7GB draft |   80% | /v1/chat/completions |  1 | [Model][inclusionAI/Ling-3.0-flash-int4] [Draft][inclusionAI/Ling-3.0-flash-dspark] — **boot-verified; ladder 2026-10-18 (`bench_7c46291e9bbb`): house 37/37, arc 94.5%/gsm8k 94.0%, bfcl 88.0%, needle 3/3 @32k+131k and 2/3 @262k (supersedes the earlier 262k PASS)** |
| kolibri-1-78b-fp8-vllm                        | ✨🧠🔧   |        47.3 |   76.2 |   77.6 |    83.5 |                 79GB |   78% | /v1/chat/completions |  1 | [Model][Aleph-Alpha/Kolibri-1] — **boot-verified; ladder 2026-10-18 (`bench_b0d57361b7d7`); battery 37/37 @8192**                                                                                                                                                        |
| kolibri-1-apex-24bpw-llamacpp                 | 🚀🧠🔧   |       63.24 |  113.4 |   98.3 |    78.6 |               22.7GB |     — | /v1/chat/completions |  1 | [Model][Myric/Kolibri-1-APEX-GGUF] — **llama.cpp fork tier, APEX-2.4bpw (22.70 GiB, 2.50 bit/w)**: C1 63.24 ± 0.50 @ d0 / 60.79 ± 0.43 @ d8192, ladder 2026-10-18 (`bench_d165fa4b0bea`, triage `bench_a0ecb791dfe6`), house 37/37 @4096, TTR 22.2 s; **79 GiB available while serving 262k** — a memory-headroom result (measured solo), not a co-residency test; receipt `~/benchmarks/kolibri-gguf-20261018/` |
| kolibri-1-apex-q4k-llamacpp                   | 🚀🧠🔧   |       57.67 |  90.23 |  83.25 |   67.50 |               45.0GB |     — | /v1/chat/completions |  1 | [Model][Myric/Kolibri-1-APEX-GGUF] — **llama.cpp, uniform Q4_K (41.89 GiB)**: C1 57.67 ± 0.21 / 53.94 ± 0.55 t/s, ladder (`bench_0725bfcd80c4`) 56.16/90.23/83.25/67.50, 37/37, TTR 42.2 s. **Verdict: the 2.4bpw sibling wins on size AND speed** (−8.8 % d0, −11.3 % d8192, −20 % c2) — Q4_K's card KLD edge (0.076 vs 0.212) is uncorroborated: both saturate 37/37, zero ranking power; receipt `~/benchmarks/kolibri-gguf-20261018/q4k/` |
| kolibri-1-78b-fp8-tensorfold-drafter-sglang   | 🚀🧠🔧   |        55.6 |      — |      — |       — | 79GB + 0.8GB drafter |     — | /v1/chat/completions |  1 | [Model][Aleph-Alpha/Kolibri-1] [Draft][josch15366/Kolibri-1-block-drafter] — **TensorFold block drafter**: C1 55.6 ± 5.9 @ d0 / 54.6 ± 4.1 @ d8192 at accept len 1.91 / 1.89 (+18 % vs the shipped FP8 arm's 47.2, cross-boot); depth 4 is worse (44.5, acc 1.79); 37/37. Ships **4 streams**: the authored 6 × 262,144 needs 34.0 GiB of caches against 25.9 free, and `readiness.inference` stays false; receipt `~/benchmarks/kolibri-mtp-20261018/` (`bench_f667f0a32253`) |
| kolibri-1-nvfp4a16-fp8-vllm                   | 🚀🧠🔧   |       52.48 |  91.64 |  95.15 |  106.39 |               45.8GB |   78% | /v1/chat/completions |  1 | [Model][Quantinine/Kolibri-1-NVFP4A16-FP8] — **NVFP4-A16 experts (Marlin W4A16; GB10 has no native FP4)**: C1 52.48 ± 0.21 / 51.11 t/s, KV **4,606,739** tokens = 2.48× the FP8 arm's 1,859,922 at the same window; battery 36/37, the one miss the FP8 control's own `needle-1` empty reply; receipt `~/benchmarks/kolibri-quants-20261018/quantinine/` (`bench_94a4ba3413d9`) |
| kolibri-1-nvfp4-experts-vllm                  | 🚀🧠🔧   |       52.37 |  91.58 |  95.03 |  105.58 |               45.8GB |   78% | /v1/chat/completions |  1 | [Model][iSkye/Kolibri-1-NVFP4-Experts] — C1 52.37 ± 0.05 / 51.11, KV 4,618,726 (2.48×), 37/37; **the card's 265.9 t/s at c8 does not reproduce** — 198.6 at 8 slots, 136.1 at the shipped 4; receipt `~/benchmarks/kolibri-quants-20261018/iskye/` (`bench_d3d412717939`) |
| kolibri-1-mxfp4-mxwave-vllm                   | 🚀🧠🔧   |       51.60 |  92.64 |  96.28 |  108.20 |               43.9GB |   78% | /v1/chat/completions |  1 | [Model][kirillbilchenko/Kolibri-1-MXFP4-MxWave] — C1 51.60 ± 0.16 / 50.52, KV 4,791,929 (2.58×), 37/37; c5/c10 are **cap-limited** by `max_num_seqs: 4`, not scaling points; **behaviour bar held while its own strict KL gate missed (0.0551 vs 0.030)** — not quality parity; receipt `~/benchmarks/kolibri-quants-20261018/kirill/` (`bench_a82cc0619910`) |
| poolside-laguna-xs-2.1-nvfp4-dflash-vllm      | ✨🧠🔧   |        55.3 |   83.1 |  133.7 |   141.3 | 21.6GB + 0.9GB draft |   55% | /v1/chat/completions |  1 | [Model][poolside/Laguna-XS-2.1-NVFP4] [Draft][poolside/Laguna-XS-2.1-DFlash] — **boot 2026-10-14; suite 2026-10-17: house 35/37, needle 2/3 @32k+131k, 3/3 @262k, arc 66.0%/gsm8k 90.5%, bfcl 60.1%, TEB 97; contract fail @262k**                                       |
| poolside-laguna-s-2.1-nvfp4-dflash-vllm       | ✨🧠🔧📜  |        20.5 |   29.3 |   39.0 |    53.8 | 99.7GB + 2.2GB draft |   85% | /v1/chat/completions |  1 | [Model][poolside/Laguna-S-2.1-NVFP4] [Draft][poolside/Laguna-S-2.1-DFlash-NVFP4] — **boot-verified; 96k capped-context single-tenant arm (window re-derived 2026-10-18), battery 33/37; needle 3/3 @32k+98,304**                                                         |
| humanizer-12b-vllm                            | 🐢     |         7.6 |      — |      — |       — |               88GB ‡ |   85% |      /v1/completions |  1 | [Model][jialinyyzz/humanizer] — **text-rewriting arm, `/v1/completions` only (no chat template), off the lane's reasoning/tool brief**                                                                                                                                   |
| qwen-image-2.1-turbo-7b-bf16-diffusers-script | 🐢📜    | 0.088 img/s |      — |      — |       — |               32.5GB | 29%\* |       POST /generate |  1 | [Model][Qwen/Qwen-Image-2.1-Turbo] — **text-to-image + editing** under a diffusers script launcher (no sglang/vLLM engine); **NON-COMMERCIAL license, banner-marked eval-only**; boot-verified 2026-10-14, ~11.4 s/image @1024²/8-step                                   |
| mellum2.1-12b-a2.5b-bf16-thinking-vllm        | ✨🧠🔧   |        42.3 |   67.2 |   99.9 |   135.6 |               24.3GB |   55% | /v1/chat/completions |  1 | [Model][JetBrains/Mellum2.1-12B-A2.5B-Thinking] — **boot-verified 2026-10-15, house battery 36/37 (easy 18/19 — `needle-1`; hard 18/18)**; ladder @ d0 pp2048 tg128 n=5: C2 67.2 / C5 99.9 / C10 135.6 t/s                                                               |
| mellum2.1-12b-a2.5b-q4km-thinking-llamacpp    | ✨🧠🔧   |       111.9 |  151.1 |  208.0 |   146.4 |               8.07GB |     — | /v1/chat/completions |  1 | [Model][JetBrains/Mellum2.1-12B-A2.5B-Thinking-GGUF] — **llama.cpp arm; boot 2026-10-17: house 37/37; needle 3/3 by union @32k+131k (32k: depth 50 at 4,096 tokens, depth 90 thinking off); arc 77.0%/gsm8k 93.5%, bfcl 88.3%, TEB 97**                                  |

* _`‡` 88 GB on disk, of which 24 GB loads._
* _`*` no recipe util — peak reserved memory, 37.68 GiB of 128 GB._ 
* _`📜` Qwen-Image is NON-COMMERCIAL (`qwen-research`, eval-only under the lane banner); the Laguna-S draft declares no license, `other` in its BF16 sibling._ 
* _The llama-cpp arm caps nothing (llama.cpp sizes its own pool from `--ctx-size`/`--parallel`), so its Mem% cell is `—`. **The llama-cpp row's bfcl cell is the 4096-budget leg** (`--bfcl-max-tokens 4096`, `~/benchmarks/mellum-gguf-tools4096-20261017/`): at the pre-`3ac9581` 512 default the same arm scored 73.5 %, with 179 of the two parallel categories' 400 questions cut to no call at all; at 4096 only six are cut and the residual loss there is multi-call shape, not budget._
* _The **ling**, **kolibri** and **Laguna-S** rows' C2/C5/C10 are the 2026-10-18 ladders @ d0 pp2048 tg128 n=5, decode rows only (`ling` `bench_7c46291e9bbb` and `kolibri` `bench_b0d57361b7d7` in `~/benchmarks/ladders-solo-20261018/`; `Laguna-S` `bench_e3fdefdc2491` in `~/benchmarks/sweep2-20261018/`), whose same-boot C1s are 49.7 ± 6.0 / 47.2 ± 0.1 / 20.26 ± 0.87 — each inside the C1 σ the row quotes. Ling's 262k needle cell is 2/3: two instrument artifacts (the suite's 900 s per-request cap, needle-haystack's 64-token default) plus one genuine depth-90 miss, so it supersedes the earlier 262k PASS._
* _The six **Kolibri-1** rows added 2026-10-18 are one boot each, decode rows only (`is_context_prefill_phase: false`). Ladder cells are @ d0 pp2048 tg128 n=5 from each receipt's own `--output` file: APEX-2.4bpw `bench_d165fa4b0bea` + triage `bench_a0ecb791dfe6` in `~/benchmarks/kolibri-gguf-20261018/`; Q4_K `bench_9c0927bbd72b` / `bench_0725bfcd80c4` in `…/q4k/`; the 4-bit vLLM trio in `~/benchmarks/kolibri-quants-20261018/{quantinine,iskye,kirill}/` (`bench_94a4ba3413d9` + `bench_553796504797`, `bench_1e19955c353c` + `bench_d3d412717939`, `bench_ed7d2ab95f36` + `bench_a82cc0619910`) — their C1 cell is the triage figure and the ladder's same-boot C1 is 52.11 / 52.00 / 51.41. The drafter arm's C1 is its triage cell (`bench_f667f0a32253`, `~/benchmarks/kolibri-mtp-20261018/`); no ladder was taken on it. All three 4-bit packs run the same `vllm/vllm-openai:v0.29.0` pin + plugin 1.0.0 and engage **Marlin** W4A16 for the routed experts, because GB10 has no native FP4._
* _The two llama.cpp GGUF rows and the TensorFold drafter row render no util, so their Mem% is `—`: llama.cpp sizes its own pool from `--ctx-size`/`--parallel`, and the drafter arm's memory statement is the engine's own cache arithmetic (22.7 GiB of caches at 4 streams / 262,144) rather than a util._
* _A **Kolibri-1 1M constant-state** arm was measured 2026-10-18 (`~/benchmarks/kolibri-state-20261018/`) and gets **no row**: it is not a recipe. That release is PolyForm-Noncommercial-1.0.0, so the arm was eval-only — nothing entered `recipes/` or `mods/`. Result: a 999,155-token needle passes in 829.7 s with GPU KV at 0.2 % of a 10.63 M-token pool (the plugin patches FlashInfer fp8 KV on SM121 cleanly), but the real per-request cost is a **10.44 GiB host archive per 1M request** — ~54× the release's billed 0.208 GB — so concurrency at 1M is 1._

## Cybersec

| Recipe                                                      | Flags | C1 t/s | C2 t/s | C5 t/s | C10 t/s |                 Size |  Mem% | TP | Model Cards                                                                                                                                                               |
|:------------------------------------------------------------|:------|-------:|-------:|-------:|--------:|---------------------:|------:|---:|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| qwen3.8-27b-uncensored-nvfp4-sglang                         | 🚀👀🏴📜  |   10.2 |  19.67 |  41.12 |   75.77 |               24.7GB |   85% |  1 | [Model][orcarouter/Qwen3.8-27B-Uncensored-NVFP4] — **positive**, boots, battery 37/37                                                                                     |
| qwen3.8-27b-uncensored-nvfp4-nextn-sglang                   | 🚀👀🏴📜  |  14.72 |      — |      — |       — |               24.7GB |   85% |  1 | [Model][orcarouter/Qwen3.8-27B-Uncensored-NVFP4] — **NEXTN spec decode on the checkpoint's own BF16 MTP head**, sibling of the plain arm: C1 14.72 ± 1.13 @ d0 / 14.59 ± 1.14 @ d8192 vs the control's 10.21 / 9.66 (+44.1 % / +51.0 %), accept len 2.774 (n=39), battery 37/37; scheduler budget **167,985 tokens**, below the advertised 262,144 |
| qwen3.8-27b-ablit-cyber-unlock-nvfp4-dflash2-sglang         | 🚀👀🏴📜  |   33.3 |   49.4 |   84.6 |    92.9 | 20.6GB + 3.9GB draft |   85% |  1 | [Model][sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4] [Draft][z-lab/Qwen3.8-27B-DFlash2] — **positive**, battery 37/37; 2026-10-17 ladder `bench_3ee8fda63ada`|
| deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang | 🚀🚚1🏴📜 |   63.7 |      — |      — |       — |          119GB graft | 85%\* |  2 | [Model][drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed] — **positive** (combined EXL3 pack, shared with the ds4 TP=2 arm, + `attn.wo_b` sidecar graft), battery 36/37, 1M ctx         |

* _`*` no recipe util — the arm's documented `≤ 0.85` ceiling._ 
* _`📜` every arm in this lane is gated on the Hub (`gated: auto`): each node needs an `HF_TOKEN` with that repo's release accepted._ 
* _The AEON row's **C1 33.3** is its earlier single-point figure — **C2/C5/C10 are the 2026-10-17 ladder** (`bench_3ee8fda63ada`), the lane's first._
* _The uncensored-27B row's **C1 10.2** is its earlier decode-triage C1 (`bench_edd91a07aee4`); **C2/C5/C10 are the 2026-10-18 ladder** (`bench_4c30a992c771`, receipt `~/benchmarks/ladders-solo-20261018/`), same-boot C1 9.75 — 4.4 % below the triage figure, outside that cell's ±0.24 but one boot. It climbs to c10 because 358,261 fp8 KV tokens carry ten concurrent 2048/128 requests with no queueing._
* _The **NEXTN** row is the plain arm's checkpoint with SGLang spec decode on its own BF16 MTP head — one boot 2026-10-18, `~/benchmarks/cybersec-nextn-20261018/` (`cells.json` decode rows, `bench_cab845506821`). Its control is the same recipe without the speculative block (`bench_edd91a07aee4` / the 2026-10-14 arm-1 triage), so C1 is cross-boot; accept len 2.774 at c=1 (n=39 decode-batch lines, min 1.80). The one capability cost is the scheduler budget: `max_total_num_tokens` 167,985, i.e. the served context is **below** the advertised 262,144 — attributed to the draft pool only **unverified**, because the control's boot log was not retained. For scale, the DFlash2 sibling's ceiling is 30.2–33.8 t/s, so this arm reaches ~44–49 % of it on a different body._

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
[IFM/K2-Horizon-0.9B-Uno]: https://huggingface.co/IFM/K2-Horizon-0.9B-Uno
[Intel/Qwen3-Coder-Next-int4-AutoRound]: https://huggingface.co/Intel/Qwen3-Coder-Next-int4-AutoRound
[littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram]: https://huggingface.co/littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram
[LibertAIDAI/DeepSeek-V4.1-Flash-1017-EXL3-2.9bpw]: https://huggingface.co/LibertAIDAI/DeepSeek-V4.1-Flash-1017-EXL3-2.9bpw
[autotrust/JEV-9B]: https://huggingface.co/autotrust/JEV-9B
[Cloudflare/clef-flash]: https://huggingface.co/Cloudflare/clef-flash
[inclusionAI/Ling-3.0-flash-int4]: https://huggingface.co/inclusionAI/Ling-3.0-flash-int4
[inclusionAI/Ling-3.0-flash-dspark]: https://huggingface.co/inclusionAI/Ling-3.0-flash-dspark
[vllm-sr/Decision-2.0-Kai-0.6B]: https://huggingface.co/vllm-sr/Decision-2.0-Kai-0.6B
[vllm-sr/Decision-2.0-Sol-2B]: https://huggingface.co/vllm-sr/Decision-2.0-Sol-2B
[Aleph-Alpha/Kolibri-1]: https://huggingface.co/Aleph-Alpha/Kolibri-1
[Myric/Kolibri-1-APEX-GGUF]: https://huggingface.co/Myric/Kolibri-1-APEX-GGUF
[josch15366/Kolibri-1-block-drafter]: https://huggingface.co/josch15366/Kolibri-1-block-drafter
[Quantinine/Kolibri-1-NVFP4A16-FP8]: https://huggingface.co/Quantinine/Kolibri-1-NVFP4A16-FP8
[iSkye/Kolibri-1-NVFP4-Experts]: https://huggingface.co/iSkye/Kolibri-1-NVFP4-Experts
[kirillbilchenko/Kolibri-1-MXFP4-MxWave]: https://huggingface.co/kirillbilchenko/Kolibri-1-MXFP4-MxWave
[deepseek-ai/DeepSeek-V4.1-Flash]: https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash
[deepseek-ai/DeepSeek-V4.1-Flash-1017]: https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017
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
[Mia-AiLab/GLM-5.3-Flash-EXL3-4bpw-TensorFold]: https://huggingface.co/Mia-AiLab/GLM-5.3-Flash-EXL3-4bpw-TensorFold
[incoai/GLM-5.3-Flash-DFlash2]: https://huggingface.co/incoai/GLM-5.3-Flash-DFlash2
[bertholomus/GLM-5.3-EXL3-3.0bpw]: https://huggingface.co/bertholomus/GLM-5.3-EXL3-3.0bpw
