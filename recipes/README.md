# Little Cedar Sparkrun Recipes

_Brought to you by Little Cedar Group._

These are the recipes we are using in the office on our humble 6-node DGX Spark cluster.

# Recipes

## DeepSeek V4

The five `exl3-*-vllm` rows are the current DeepSeek recipe suite — all boot and
serve on our cluster (measured 2026-09-24/25). The earlier SGLang recipes
(`deepseek-v4-flash-0731-*-sglang`, `deepseek-v4.1-flash-mxfp4-tp4/tp8-sglang`)
were removed because they do not boot: the three V4-Flash TP=2 rows die ~5 min
into init (rank-0 scheduler SIGTERM, no OOM; DSpark, shared-expert fusion and the
watchdog each ruled out by a control), and the two V4.1 rows fail the MXFP4-Cutlass
MoE partition check (`moe_intermediate_size 2304/4 = 576`, not a multiple of 128)
— plus `dev-dsv41` lacks the `b12x` kernels. See
`recipes/ds4/DS4-MODEL-OPTIMIZATION-WORK.md` §7.5.3/§7.5.4 and JOURNAL.

| Recipe | Flags | t/s (C1 / C4 / C8) | Size | Mem | TP | Model Cards |
|:-------|:------|------:|-----:|----:|---:|:------------|
| deepseek-v4.1-flash-exl3-tp3-vllm | | 15.8 / 47.1 / 69.1 | 460GB | 0.80 | 3 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |
| deepseek-v4.1-flash-exl3-tp4-vllm | | 37.5 / 61.9 / 88.5 | 460GB | 0.80 | 4 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |
| deepseek-v4.1-flash-exl3-tp4-1m-vllm | 🚚 | 1M ctx; needle ✓@799K; 746 t/s prefill | 460GB | 0.80 | 4 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |
| deepseek-v4.1-flash-exl3-tp6-vllm | | 29.4 / 63.8 / 108.0 | 460GB | 0.80 | 6 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |
| deepseek-v4.1-flash-exl3-tp6-1m-vllm | 🚚 | 1M ctx; KV 14.0M; needle ✓@799K | 460GB | 0.80 | 6 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |

**The `exl3-*-vllm` rows** use the EXL3 3.5 bpw checkpoint and
`littlecedar/dgx-spark-dsv41:exl3a` with `mods/mount-dsv41-exl3-patches`
(Engram-on-disk; without it the boot OOMs). The t/s column is C1 / C4 / C8
aggregate, greedy, distinct prompts. C8 on TP=6 is the fleet's best. TP=6 is
no-spec (the DSpark drafter's 128 experts don't divide by 6); TP=4 carries DSpark.
Quality battery (measured on TP=3, TP=4 and TP=6): 19/19 easy, 17/18 hard,
identical across all three — no measured quality cost from the padding.

V4.1-Flash is 510 GB, of which **203 GB is two Engram embedding tables**, and it
will not fit at TP=2 on any amount of RAM a Spark pair has.

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
[bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard]: https://huggingface.co/bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard