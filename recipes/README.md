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
| littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm | 🌲     |  41.86 | 235GB | 0.80 |  4 | [Model][littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft]                                   |
| ornith-1.5-35b-a3b-nvfp4-dflash2-sglang          | ✨🚀🌲 |    100 |  45GB | 0.85 |  1 | [Model][ornith-ai/Ornith-1.5-35B-A3B-NVFP4] [Draft][jzinno/Ornith-1.5-35B-A3B-DFlash2] |

## Qwen-VL

| Recipe                                   | Flags    | C1 t/s | Size |  Mem | TP | Model Cards                                    |
|:----------------------------------------|:--------|------:|----:|----:|---:|:----------------------------------------------|
| qwen3-vl-embedding-2b-vllm-b12x          | 🚀🌲👀📶 |      — |    — | 0.25 |  1 | [Model][Qwen/Qwen3-VL-Embedding-2B]            |
| qwen3-vl-embedding-8b-awq-4bit-vllm-b12x | 🚀🌲👀📶 |      — |    — | 0.30 |  1 | [Model][gonuit/Qwen3-VL-Embedding-8B-AWQ-4bit] |
| qwen3-vl-reranker-2b-vllm-b12x           | 🚀🌲👀🔃 |      — |    — | 0.30 |  1 | [Model][Qwen/Qwen3-VL-Reranker-2B]             |
| qwen3-vl-reranker-8b-vllm-b12x           | 🌲👀🔃   |      — |    — | 0.30 |  1 | [Model][Qwen/Qwen3-VL-Reranker-8B]             |

## Qwen 3x

| Recipe                               | Flags  | C1 t/s | Size |  Mem | TP | Model Cards                                                             |
|:------------------------------------|:------|------:|----:|----:|---:|:-----------------------------------------------------------------------|
| qwen3.8-27b-nvfp4-dflash2-sglang     | ✨🚀🌲 |     50 | 21GB | 0.85 |  1 | [Model][RadixArk/Qwen3.8-27B-NVFP4] [Draft][incoai/Qwen3.8-27B-DFlash2] |
| qwen3-coder-next-int4-autoround-vllm | 🚀🌲   |     70 | 41GB | 0.85 |  1 | [Model][Intel/Qwen3-Coder-Next-int4-AutoRound]                          |

## Qwen 4x

| Recipe                                  | Flags | C1 t/s |  Size |  Mem | TP | Model Cards                                                    |
|:----------------------------------------|:------|-------:|------:|-----:|---:|:---------------------------------------------------------------|
| qwen3.8-flash-next-nvfp4-sglang         | 🌲    |     38 | 135GB | 0.80 |  2 | [Model][RadixArk/Qwen3.8-Flash-Next-NVFP4]                     |
| qwen3.8-flash-next-nvfp4-labquant-sglang | 🌲    |     44 | 106GB | 0.80 |  2 | [Model][local-inference-lab/Qwen3.8-Flash-Next-NVFP4]          |
| qwen3.8-flash-next-nvfp4-labquant-highcon-sglang | 🌲🚀 |     44 | 106GB | 0.80 |  2 | [Model][local-inference-lab/Qwen3.8-Flash-Next-NVFP4] — **high concurrency** |
| qwen3.8-flash-next-nvfp4-labquant-longctx-sglang | 🌲   |     44 | 106GB | 0.80 |  2 | [Model][local-inference-lab/Qwen3.8-Flash-Next-NVFP4] — **long context (1M route)** |

Two of these are **production lanes** off the labquant checkpoint (see
[`qwen4/README.md`](qwen4/README.md)): `…-highcon-…` raises the mamba pool 112 → 128 and
`max_num_seqs` to 32 for aggregate throughput (peak ~88 tok/s at k≈16–24); `…-longctx-…` opens the
1M-token route (`--context-length 1000000` + YaRN RoPE, gated by
`SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN=1`) and is **quality-unverified above ~262k**.

_C1 t/s is single-stream (concurrency 1, depth 0) aggregate decode from the lane's measurement record;
these are TP=2 across two Sparks. Aggregate at k=16/d=8192 peaks near 87 (RadixArk) / 91 (labquant),
then both fall ~38% at k=24. **Read the labquant row with its caveat:** its checkpoint is more
aggressively quantised (MXFP8 attention/GDN, FP8 PLE n-gram table) and **serves text only** (the vision
tower is dropped by a required mod); no accuracy evaluation exists for it, so its speed is not evidence
of equal quality. Use the RadixArk recipe as the quality reference until an eval lands._

## IFM K2-Horizon

| Recipe                                    | Flags  | C1 t/s |  Size |  Mem | TP | Model Cards                                                    |
|:------------------------------------------|:-------|-------:|------:|-----:|---:|:---------------------------------------------------------------|
| k2-horizon-0.9b-bf16-sglang               | ✨🚀   |   77.6 |  2GB | 0.85 |  1 | [Model][IFM/K2-Horizon-0.9B]                                   |
| k2-horizon-7b-fp8-uno-sglang              | 🚀    |   32.4 | 11GB | 0.82 |  1 | [Model][IFM/K2-Horizon-7B-FP8] — **UNO spec decode, fastest** |

_Native SGLang on GB10. C1 t/s measured at concurrency 1, depth 0
(`benchmarking/decode-triage.yaml`); the 7B figure is the mean over several clean
boots from the 2026-10-09 campaign. The shipped 7B arm is **UNO spec decode
(32.4 t/s, +52 % over plain)** — the lane's fastest at single-stream and, once
`max_num_seqs` is raised off the old 8, at aggregate concurrency too (145.5 t/s at
c=8). It needs two mods — one fetches the `K2-Horizon-7B-Uno` draft adapter, one
relaxes SGLang's `fa3`-only UNO gate so `--attention-backend fa4` can serve on
GB10 — and it is accuracy-lossless on the shared instrument. The plain 7B and
NGRAM arms were retired to [`../attic/ifm/arms/`](../attic/ifm/arms/) (plain is
dominated by both spec arms; NGRAM is slower at d0 and at c=8, its only edge, at
d8k, falling inside the lane's inter-boot noise floor). The lane also carries
**measured accuracy** for both dense models (house / gsm8k / arc) and a
`page-size` / `fa4` / cuda-graph arm sweep — see [`ifm/README.md`](ifm/README.md).
The withdrawn 36B-A4B sub-lane (4 arms + the `patch-sglang-k2-horizon-fp8` gate mod)
is archived under [`../attic/ifm/`](../attic/ifm/)._

# Model Flags

| Flag | Tag           | Description                              |
|:-----|:--------------|:-----------------------------------------|
| ✨   | official      | Uses official weights                    |
| 🌲   | lcg_favorite  | Little Cedar Group:tm: Favorite          |
| 🚀   | fast          | C1 Fast (>= 50t/s avg)                   |
| 🐢   | slow          | C1 Slow (< 40t/s avg)                    |
| 🚚   | large_context | Large context (>= 512k tokens)           |
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

# Notes

Per-family agent guides: the Qwen3.8-Flash-Next lane carries its own
[`qwen4/AGENTS.md`](qwen4/AGENTS.md) (state, constraints, workstream plan, runbook) and
[`qwen4/README.md`](qwen4/README.md) (the recipe/lane summary), with `../attic/qwen4/NOTES.md` (working notes).
Read those before starting work in that directory. Archived arms and the lane's research record,
journal, and coordination ledger live under [`../attic/qwen4/`](../attic/qwen4/).

The DeepSeek V4.1-Flash lanes are documented in [`ds4/README.md`](ds4/README.md) (user guide)
and [`ds4/AGENTS.md`](ds4/AGENTS.md) (design, boot gates, guards, and measurement discipline for
both the knapcio TP=4 and TensorFold TP=2 lanes); the retired vLLM/EXL3 lane is under
[`../attic/ds4/`](../attic/ds4/).


The IFM K2-Horizon lanes are documented in [`ifm/README.md`](ifm/README.md) (recipe
summary) and [`ifm/AGENTS.md`](ifm/AGENTS.md) (constraints, falsified claims, guards,
and the validation ritual for the `0.9B` / `7B-FP8` set); the
research record, journals, and `COOP.md` are beside them.

The Ornith 1.5 lanes are documented in [`ornith/README.md`](ornith/README.md) (per-recipe wiring,
caveats, and the three archived arms); the lane carries no `AGENTS.md` and no guard suite.

# References

* https://spark-arena.com

<!-- Links -->
[RadixArk/Qwen3.8-27B-NVFP4]: https://huggingface.co/RadixArk/Qwen3.8-27B-NVFP4
[RadixArk/Qwen3.8-Flash-Next-NVFP4]: https://huggingface.co/RadixArk/Qwen3.8-Flash-Next-NVFP4
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
[deepseek-ai/DeepSeek-V4.1-Flash]: https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash