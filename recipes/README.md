# Little Cedar Sparkrun Recipes

_Brought to you by Little Cedar Group._

These are the recipes we are using in the office on our humble 6-node DGX Spark cluster.

# Recipes

## DeepSeek V4

| Recipe                                       | Flags  | C1 t/s |  Size |  Mem | TP | Model Cards                                                |
|:---------------------------------------------|:-------|-------:|------:|-----:|---:|:-----------------------------------------------------------|
| deepseek-v4.1-flash-knapcio-tp4-1m-sglang    | ✨🚚🌲👀 |   46.5 | 510GB | 0.80 |  4 | [Model][deepseek-ai/DeepSeek-V4.1-Flash]                   |
| deepseek-v4.1-flash-tensorfold-tp2-1m-sglang | 🚀🚚1  |   73.0 | 385GB |    — |  2 | [Model][littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram] |

## Ornith 1.5

| Recipe                                           | Flags  | C1 t/s |  Size |  Mem | TP | Model Cards                                                                            |
|:------------------------------------------------|:------|------:|-----:|----:|---:|:--------------------------------------------------------------------------------------|
| littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm | 🌲👀🧠🦾🔧 |  41.86 | 235GB | 0.80 |  4 | [Model][littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft]                                   |
| ornith-1.5-35b-a3b-nvfp4-dflash2-sglang          | ✨🚀🌲👀🧠🦾🔧 |    100 |  45GB | 0.85 |  1 | [Model][ornith-ai/Ornith-1.5-35B-A3B-NVFP4] [Draft][jzinno/Ornith-1.5-35B-A3B-DFlash2] |
| ornith-1.5-9b-nvfp4-dflash-sglang               | ✨🚀🤏👀🧠🦾🔧 |    55 |  11GB | 0.85 |  1 | [Model][ornith-ai/Ornith-1.5-9B-NVFP4] [Draft][ornith-ai/Ornith-1.5-9B-DFlash]        |

## Embed

| Recipe                                   | Flags    | C1 t/s | Size |  Mem | TP | Model Cards                                    |
|:----------------------------------------|:--------|------:|----:|----:|---:|:----------------------------------------------|
| qwen3-vl-embedding-2b-vllm-b12x          | 🚀🌲👀📶🤏 |      — |    — | 0.25 |  1 | [Model][Qwen/Qwen3-VL-Embedding-2B]            |
| qwen3-vl-embedding-8b-awq-4bit-vllm-b12x | 🚀🌲👀📶🤏 |      — |    — | 0.30 |  1 | [Model][gonuit/Qwen3-VL-Embedding-8B-AWQ-4bit] |

## Rerank

| Recipe                                   | Flags    | C1 t/s | Size |  Mem | TP | Model Cards                                    |
|:----------------------------------------|:--------|------:|----:|----:|---:|:----------------------------------------------|
| qwen3-vl-reranker-2b-vllm-b12x           | 🚀🌲👀🔃🤏 |      — |    — | 0.30 |  1 | [Model][Qwen/Qwen3-VL-Reranker-2B]             |
| qwen3-vl-reranker-8b-vllm-b12x           | 🌲👀🔃🤏 |      — |    — | 0.30 |  1 | [Model][Qwen/Qwen3-VL-Reranker-8B]             |

## Qwen 3x

| Recipe                               | Flags  | C1 t/s | Size |  Mem | TP | Model Cards                                                             |
|:------------------------------------|:------|------:|----:|----:|---:|:-----------------------------------------------------------------------|
| qwen3.8-27b-nvfp4-dflash2-sglang     | 🌲🚀👀 |     50 | 21GB | 0.85 |  1 | [Model][RadixArk/Qwen3.8-27B-NVFP4] [Draft][incoai/Qwen3.8-27B-DFlash2] |
| qwen3-coder-next-int4-autoround-vllm | 🌲🚀   |    71.7 | 41GB | 0.85 |  1 | [Model][Intel/Qwen3-Coder-Next-int4-AutoRound] — vLLM; **measured 2026-10-11, 2.1× the DFlash2 C1; house battery 35/37** |
| qwen3.8-27b-mlx4bit-tensorfold-sglang | 👀     |   41.3 | 19GB |    — |  1 | [Model][TensorFold/Qwen3.8-27B-MLX-4bit] [Draft][z-lab/Qwen3.8-27B-DFlash2] — **TensorFold** engine (MiaAI-Lab); booted 2026-10-14, house battery 37/37 |

## Qwen 4x

| Recipe                                  | Flags   | C1 t/s |  Size |  Mem | TP | Model Cards                                                    |
|:----------------------------------------|:--------|-------:|------:|-----:|---:|:---------------------------------------------------------------|
| qwen3.8-flash-next-nvfp4-labquant-sglang | 🌲🚀👀 |   40.3 | 106GB | 0.80 |  2 | [Model][local-inference-lab/Qwen3.8-Flash-Next-NVFP4]          |
| qwen3.8-flash-next-nvfp4-solo-vllm-b12x | 🌲     |   33.9 | 135GB | 0.80 |  1 | [Model][local-inference-lab/Qwen3.8-Flash-Next-NVFP4] — **solo TP=1, PLE table streamed from disk** |

## IFM K2-Horizon

| Recipe                                    | Flags  | C1 t/s |  Size |  Mem | TP | Model Cards                                                    |
|:------------------------------------------|:-------|-------:|------:|-----:|---:|:---------------------------------------------------------------|
| k2-horizon-0.9b-bf16-sglang               | ✨🚀🤏🧠🔧 |   77.6 |  2GB | 0.85 |  1 | [Model][IFM/K2-Horizon-0.9B]                                   |
| k2-horizon-7b-fp8-uno-sglang              | 🚀🤏🧠🔧🦾 |   32.4 | 11GB | 0.82 |  1 | [Model][IFM/K2-Horizon-7B-FP8] — **UNO spec decode, fastest** |

## GLM 5.3

**No shipped recipe** — see [`glm/README.md`](glm/README.md) for the lane's TensorFold runbook notes and [`../attic/glm/`](../attic/glm/ARMS-MANIFEST.md) for the archived `glm-5.3-flash-nvfp4-dflash-vllm` recipe.

## Decision

| Recipe                      | Flags | Accuracy | Size |             API | TP | Model Cards                            |
|:----------------------------|:------|---------:|-----:|----------------:|---:|:---------------------------------------|
| jev-9b-decision-vllm        | 🤏🚮    |    67.0% | 18GB | /v1/completions |  1 | [Model][autotrust/JEV-9B]              |
| clef-flash-decision-sglang  | 🤏🚮    |    70.3% | 19GB |   /v1/systemone |  1 | [Model][Cloudflare/clef-flash]         |
| kai-0.6b-decision-vllm-srun | 🤏🖥🚮  |    47.5% |  2GB |   /v1/systemone |  1 | [Model][vllm-sr/Decision-2.0-Kai-0.6B] |
| sol-2b-decision-vllm-srun   | 🤏🖥🚮  |      55% |  5GB |   /v1/systemone |  1 | [Model][vllm-sr/Decision-2.0-Sol-2B]   |

## Explore

| Recipe                                          | Flags | C1 t/s |  Size |  Mem | TP | Model Cards                                                                 |
|:------------------------------------------------|:------|-------:|------:|-----:|---:|:----------------------------------------------------------------------------|
| ling-3.0-flash-int4-dspark-sglang                | 🧠    |   45.5 | 154GB | 0.80 |  1 | [Model][inclusionAI/Ling-3.0-flash-int4] [Draft][inclusionAI/Ling-3.0-flash-dspark] — **boot-verified, house battery 37/37; 262k needle-verified at mem-fraction 0.80** |
| kolibri-1-78b-fp8-vllm                           | ✨🧠🔧 |   47.3 |  74GB | 0.78 |  1 | [Model][Aleph-Alpha/Kolibri-1] — **boot-verified, house battery 36/37 (37/37 union across token budgets)** |
| poolside-laguna-xs-2.1-nvfp4-dflash-vllm        | ✨🧠🔧 |   57.4 | 22.5GB | 0.55 |  1 | [Model][poolside/Laguna-XS-2.1-NVFP4] [Draft][poolside/Laguna-XS-2.1-DFlash] — **boot-verified 2026-10-14, house battery 36/37; 262k pool-verified, needle probe open** |
| poolside-laguna-s-2.1-nvfp4-dflash-vllm         | ✨🧠🔧 |   20.5 |  96GB | 0.85 |  1 | [Model][poolside/Laguna-S-2.1-NVFP4] [Draft][poolside/Laguna-S-2.1-DFlash-NVFP4] — **boot-verified; 120k capped-context single-tenant arm, battery 32/37** |
| humanizer-12b-vllm                              | 🐢     |      — |  24GB | 0.85 |  1 | [Model][jialinyyzz/humanizer] — **text-rewriting arm, `/v1/completions` only (no chat template), off the lane's reasoning/tool brief** |
| qwen-image-2.1-turbo-7b-bf16-diffusers-script             | 🐢     |      — |  33GB |    — |  1 | [Model][Qwen/Qwen-Image-2.1-Turbo] — **text-to-image + editing** under a diffusers script launcher (no sglang/vLLM engine); **NON-COMMERCIAL licence, banner-marked eval-only**; boot-verified 2026-10-14, ~11.4 s/image @1024²/8-step |

## Cybersec

| Recipe                                                     | Flags     | C1 t/s |  Size |  Mem | TP | Model Cards                                                     |
|:-----------------------------------------------------------|:----------|-------:|------:|-----:|---:|:----------------------------------------------------------------|
| qwen3.8-27b-uncensored-nvfp4-sglang                        | 🚀👀🏴    |   10.2 |  25GB | 0.85 |  1 | [Model][orcarouter/Qwen3.8-27B-Uncensored-NVFP4] — **positive**, boots, battery 37/37 |
| qwen3.8-27b-ablit-cyber-unlock-nvfp4-dflash2-sglang        | 🚀👀🏴    |   33.3 |  21GB | 0.85 |  1 | [Model][sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4] [Draft][incoai/Qwen3.8-27B-DFlash2] — **positive** (AEON body + drowzeys cyber template), battery 37/37 |
| deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang | 🚀🚚1🏴  |   63.7 | 197GB |    — |  2 | [Model][drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed] — **positive** (stock Mia EXL3 pack + `attn.wo_b` sidecar graft), battery 36/37, 1M ctx |
| nex-n2.5-mini-uncensored-nvfp4-sglang                      | 🚀👀🏴💀  |      — |  24GB | 0.85 |  1 | [Model][orcarouter/Nex-N2.5-mini-Uncensored-NVFP4] — **negative**: NaN sample-time logits under SGLang; vLLM route blocked on image distribution |
| qwen3.8-flash-next-uncensored-nvfp4-sglang                 | 🚀👀🏴💀  |      — | 184GB | 0.85 |  2 | [Model][orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4] — **negative**: SGLang's compressed-tensors loader refuses the export's scheme; vLLM is the next step |

# Model Flags

| Flag | Tag           | Description                              |
|:-----|:--------------|:-----------------------------------------|
| ✨   | official      | Uses official weights                    |
| 🌲   | lcg_favorite  | Little Cedar Group:tm: Favorite          |
| 🚀   | fast          | C1 Fast (>= 50t/s avg)                   |
| 🐢   | slow          | C1 Slow (< 40t/s avg)                    |
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
| 🚩   | dangerous     | Dangerous and may crash your Sparks!     |    
| 💀   | broken        | Currently broken                         |

_Flags indicate characteristics of the model and are set in the recipe metadata._

# Mechanics

See [MECHANICS.md](MECHANICS.md) for the sparkrun command-template rules every recipe author needs.

# References

* https://spark-arena.com

<!-- Links -->
[RadixArk/Qwen3.8-27B-NVFP4]: https://huggingface.co/RadixArk/Qwen3.8-27B-NVFP4
[local-inference-lab/Qwen3.8-Flash-Next-NVFP4]: https://huggingface.co/local-inference-lab/Qwen3.8-Flash-Next-NVFP4
[incoai/Qwen3.8-27B-DFlash2]: https://huggingface.co/incoai/Qwen3.8-27B-DFlash2
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
[orcarouter/Nex-N2.5-mini-Uncensored-NVFP4]: https://huggingface.co/orcarouter/Nex-N2.5-mini-Uncensored-NVFP4
[orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4]: https://huggingface.co/orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4
[drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed]: https://huggingface.co/drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed
[poolside/Laguna-XS-2.1-NVFP4]: https://huggingface.co/poolside/Laguna-XS-2.1-NVFP4
[poolside/Laguna-XS-2.1-DFlash]: https://huggingface.co/poolside/Laguna-XS-2.1-DFlash
[poolside/Laguna-S-2.1-NVFP4]: https://huggingface.co/poolside/Laguna-S-2.1-NVFP4
[poolside/Laguna-S-2.1-DFlash-NVFP4]: https://huggingface.co/poolside/Laguna-S-2.1-DFlash-NVFP4
[jialinyyzz/humanizer]: https://huggingface.co/jialinyyzz/humanizer
[Qwen/Qwen-Image-2.1-Turbo]: https://huggingface.co/Qwen/Qwen-Image-2.1-Turbo
[ornith-ai/Ornith-1.5-9B-NVFP4]: https://huggingface.co/ornith-ai/Ornith-1.5-9B-NVFP4
[ornith-ai/Ornith-1.5-9B-DFlash]: https://huggingface.co/ornith-ai/Ornith-1.5-9B-DFlash

[TensorFold/Qwen3.8-27B-MLX-4bit]: https://huggingface.co/TensorFold/Qwen3.8-27B-MLX-4bit
[z-lab/Qwen3.8-27B-DFlash2]: https://huggingface.co/z-lab/Qwen3.8-27B-DFlash2
