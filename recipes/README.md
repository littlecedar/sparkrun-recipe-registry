# Little Cedar Sparkrun Recipes

_Brought to you by Little Cedar Group._

These are the recipes we are using in the office on our humble 6-node DGX Spark cluster.

# Recipes

## DeepSeek V4

| Recipe                                 | Flags  | C1 t/s |  Size |  Mem | TP | Model Cards                                                 |
|:---------------------------------------|:-------|-------:|------:|-----:|---:|:------------------------------------------------------------|
| deepseek-v4.1-flash-knapcio-tp4-1m-sglang | ✨🚚🌲 |   46.5 | 510GB | 0.80 |  4 | [Model][deepseek-ai/DeepSeek-V4.1-Flash]                    |

## Ornith 1.5

| Recipe                                      | Flags  | C1 t/s |  Size |  Mem | TP | Model Cards                                                                                |
|:--------------------------------------------|:-------|-------:|------:|-----:|---:|:-------------------------------------------------------------------------------------------|
| littlecedar-ornith-1.5-397b-nvfp4-mtp-graft | 🌲     |  41.86 | 235GB | 0.85 |  4 | [Model][littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft]                                       |
| ornith-1.5-35b-a3b-nvfp4-dflash2-sglang     | ✨🚀🌲 |    100 |  45GB | 0.85 |  1 | [Model][ornith/Ornith-1.5-397B-NVFP4-MTP-Graft] [Draft][jzinno/Ornith-1.5-35B-A3B-DFlash2] |

## Qwen-VL

| Recipe | Flags | C1 t/s | Size | Mem | TP | Model Cards |
|:-------|:------|-------:|-----:|----:|---:|:------------|
| ?      | ?     |      ? |    ? |   ? |  ? | ?           |

## Qwen 3x

| Recipe                                    | Flags  | C1 t/s | Size |  Mem | TP | Model Cards                                                             |
|:------------------------------------------|:-------|-------:|-----:|-----:|---:|:------------------------------------------------------------------------|
| qwen3.8-27b-nvfp4-dflash2-sglang          | ✨🚀🌲 |     50 | 21GB | 0.85 |  1 | [Model][RadixArk/Qwen3.8-27B-NVFP4] [Draft][incoai/Qwen3.8-27B-DFlash2] |
| qwen3-coder-next-int4-autoround-vllm.yaml | 🚀🌲   |     70 | 41GB | 0.85 |  1 | [Model][Intel/Qwen3-Coder-Next-int4-AutoRound]                          |

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

# Notes

Per-family agent guides: the Qwen3.8-Flash-Next lane carries its own
[`qwen4/AGENTS.md`](qwen4/AGENTS.md) (state, constraints, workstream plan, runbook) and
[`qwen4/README.md`](qwen4/README.md) (the recipe/lane summary), with `../attic/qwen4/NOTES.md` (working notes).
Read those before starting work in that directory. Archived arms and the lane's research record,
journal, and coordination ledger live under [`../attic/qwen4/`](../attic/qwen4/).

# Model Flags

| Flag | Tag           | Description                              |
|:-----|:--------------|:-----------------------------------------|
| ✨   | official      | Uses official weights                    |
| 🌲   | lcg_favorite  | Little Cedar Group:tm: Favorite          |
| 🚀   | fast          | C1 Fast (>= 50t/s avg)                   |
| 🐢   | slow          | C1 Slow (< 40t/s avg)                    |
| 🚚   | large_context | Large context (>= 512k tokens)           |
| 1    | single_user   | Low concurrency, single-user recommended |
| 🏴   | uncensored    | Uncensored model                         |
| 🚩   | dangerous     | Dangerous and may crash your Sparks!     |    
| 💀   | broken        | Currently broken                         |

_Flags indicate characteristics of the model and are set in the recipe metadata._

# References

* https://spark-arena.com

<!-- Links -->
[RadixArk/Qwen3.8-27B-NVFP4]: https://huggingface.co/RadixArk/Qwen3.8-27B-NVFP4
[RadixArk/Qwen3.8-Flash-Next-NVFP4]: https://huggingface.co/RadixArk/Qwen3.8-Flash-Next-NVFP4
[local-inference-lab/Qwen3.8-Flash-Next-NVFP4]: https://huggingface.co/local-inference-lab/Qwen3.8-Flash-Next-NVFP4
[incoai/Qwen3.8-27B-DFlash2]: https://huggingface.co/incoai/Qwen3.8-27B-DFlash2
[littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft]: https://huggingface.co/littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft
[ornith/Ornith-1.5-397B-NVFP4-MTP-Graft]: https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B-NVFP4
[jzinno/Ornith-1.5-35B-A3B-DFlash2]: https://huggingface.co/jzinno/Ornith-1.5-35B-A3B-DFlash2
[Intel/Qwen3-Coder-Next-int4-AutoRound]: https://huggingface.co/Intel/Qwen3-Coder-Next-int4-AutoRound
[bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard]: https://huggingface.co/bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard
[deepseek-ai/DeepSeek-V4.1-Flash]: https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash