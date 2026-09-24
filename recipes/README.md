# Little Cedar Sparkrun Recipes

_Brought to you by Little Cedar Group._

These are the recipes we are using in the office on our humble 6-node DGX Spark cluster.

# Recipes

## DeepSeek V4

Nothing here has been measured on our own hardware yet, so every t/s is `?` —
they are placeholders awaiting a real boot, not slow results. The TP=2 pair ports
upstream-verified SGLang DGX Spark cells; the V4.1-Flash pair has **no upstream
cell for this hardware** and is our own work. The three `exl3-*-vllm` rows port
tonyd2wild/bot-lab-21's **measured** 4× Spark vLLM lane and **HAVE been booted
on our nodes (2026-09-24)**: the t/s shown are measured here (C8 aggregate).
See `recipes/ds4/JOURNAL.md`.

| Recipe | Flags | t/s | Size | Mem | TP | Model Cards |
|:-------|:------|----:|-----:|----:|---:|:------------|
| deepseek-v4-flash-0731-mxfp4-tp2-sglang | ✨ | ? | 167GB | 0.80 | 2 | [Model][deepseek-ai/DeepSeek-V4-Flash-0731] |
| deepseek-v4-flash-0731-nvfp4-tp2-sglang | 🚩 | ? | 176GB | 0.80 | 2 | [Model][nvidia/DeepSeek-V4-Flash-0731-NVFP4] |
| deepseek-v4-flash-0731-mxfp4-tp2-nospec-sglang | ✨ | ? | 167GB | 0.80 | 2 | [Model][deepseek-ai/DeepSeek-V4-Flash-0731] |
| deepseek-v4.1-flash-mxfp4-tp4-sglang | 🚩✨ | ? | 510GB | 0.80 | 4 | [Model][deepseek-ai/DeepSeek-V4.1-Flash] |
| deepseek-v4.1-flash-mxfp4-tp8-sglang | 🚩✨ | ? | 510GB | 0.80 | 8 | [Model][deepseek-ai/DeepSeek-V4.1-Flash] |
| deepseek-v4.1-flash-exl3-tp4-vllm | 🚩 | 76 (C8) | 460GB | 0.80 | 4 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |
| deepseek-v4.1-flash-exl3-tp4-1m-vllm | 🚩 | 1M ctx, 746 t/s prefill @799K | 460GB | 0.80 | 4 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |
| deepseek-v4.1-flash-exl3-tp3-vllm | 🚩 | 69 (C8, no-spec) | 460GB | 0.80 | 3 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |

`tags: control, measurement_only` on the nospec arm marks it as a benchmark
denominator, not a shipping recipe — see its header.

V4.1-Flash is 510 GB, of which **203 GB is two Engram embedding tables**, and it
will not fit at TP=2 on any amount of RAM a Spark pair has. The `exl3` rows need
`mods/mount-dsv41-exl3-patches` (Engram-on-disk reader) and the image
`littlecedar/dgx-spark-dsv41:exl3a`; without the mod the TP=4 boot OOMs. The
1M-context row is the objective's 1M deliverable. 🚩 because none of the V4.1
rows has been booted on our cluster yet.

## Ornith 1.5

| Recipe                                      | Flags  |   t/s |  Size |  Mem | TP | Model Cards                                                                                |
|:--------------------------------------------|:-------|------:|------:|-----:|---:|:-------------------------------------------------------------------------------------------|
| littlecedar-ornith-1.5-397b-nvfp4-mtp-graft | 🌲     | 41.86 | 235GB | 0.85 |  4 | [Model][littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft]                                       |
| ornith-1.5-35b-a3b-nvfp4-dflash2-sglang     | ✨🚀🌲 |   100 |  45GB | 0.85 |  1 | [Model][ornith/Ornith-1.5-397B-NVFP4-MTP-Graft] [Draft][jzinno/Ornith-1.5-35B-A3B-DFlash2] |

## Qwen 3.8

| Recipe                           | Flags | t/s | Size |  Mem | TP | Model Cards                                                             |
|:---------------------------------|:------|----:|-----:|-----:|---:|:------------------------------------------------------------------------|
| qwen3.8-27b-nvfp4-dflash2-sglang | ✨🌲  |  50 | 21GB | 0.85 |  1 | [Model][RadixArk/Qwen3.8-27B-NVFP4] [Draft][incoai/Qwen3.8-27B-DFlash2] |

## Qwen3 Coder Next

| Recipe                                    | Flags | t/s | Size |  Mem | TP | Model Cards                                    |
|:------------------------------------------|:------|----:|-----:|-----:|---:|:-----------------------------------------------|
| qwen3-coder-next-int4-autoround-vllm.yaml | 🚀🌲  |  70 | 41GB | 0.85 |  1 | [Model][Intel/Qwen3-Coder-Next-int4-AutoRound] |

# Notes

# Model Flags

| Flag  | Tag           | Description                          |
|:------|:--------------|:-------------------------------------|
| ✨    | official      | Uses official weights                |
| 🌲    | lcg_favorite  | Little Cedar Group:tm: Favorite      |
| 🚀    | fast          | Fast (> 60t/s avg)                   |
| 🐢    | slow          | Slow (< 30t/s avg)                   |
| 🚚    | large_context | Large context (> 1000000 tkns)       |
| 🏴    | uncensored    | Uncensored model                     |
| 🚩    | dangerous     | Dangerous and may crash your Sparks! |    
| 💀    | broken        | Currently broken                     |

_Flags indicate characteristics of the model and are set in the recipe metadata._

# References

* https://spark-arena.com

<!-- Links -->
[RadixArk/Qwen3.8-27B-NVFP4]: https://huggingface.co/RadixArk/Qwen3.8-27B-NVFP4
[incoai/Qwen3.8-27B-DFlash2]: https://huggingface.co/incoai/Qwen3.8-27B-DFlash2
[littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft]: https://huggingface.co/littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft
[ornith/Ornith-1.5-397B-NVFP4-MTP-Graft]: https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B-NVFP4
[jzinno/Ornith-1.5-35B-A3B-DFlash2]: https://huggingface.co/jzinno/Ornith-1.5-35B-A3B-DFlash2
[Intel/Qwen3-Coder-Next-int4-AutoRound]: https://huggingface.co/Intel/Qwen3-Coder-Next-int4-AutoRound
[deepseek-ai/DeepSeek-V4-Flash-0731]: https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731
[nvidia/DeepSeek-V4-Flash-0731-NVFP4]: https://huggingface.co/nvidia/DeepSeek-V4-Flash-0731-NVFP4
[deepseek-ai/DeepSeek-V4.1-Flash]: https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash
[bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard]: https://huggingface.co/bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard