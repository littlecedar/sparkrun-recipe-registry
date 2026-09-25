# Little Cedar Sparkrun Recipes

_Brought to you by Little Cedar Group._

These are the recipes we are using in the office on our humble 6-node DGX Spark cluster.

# Recipes

## DeepSeek V4

All ten recipes have been tested on our cluster (2026-09-24/25): the five
`exl3-*-vllm` rows **boot and serve** with measured t/s (C1/C4/C8 aggregate,
greedy, distinct prompts); the five SGLang rows are in a **named failure state**,
not untested — see the notes below each mechanism. t/s are measured on our nodes.
Full evidence: `recipes/ds4/JOURNAL.md` and
`recipes/ds4/DS4-MODEL-OPTIMIZATION-WORK.md` §7.5.

| Recipe | Flags | t/s (C1 / C4 / C8) | Size | Mem | TP | Model Cards |
|:-------|:------|------:|-----:|----:|---:|:------------|
| deepseek-v4-flash-0731-mxfp4-tp2-sglang | 💀 | — (dies in init) | 167GB | 0.80 | 2 | [Model][deepseek-ai/DeepSeek-V4-Flash-0731] |
| deepseek-v4-flash-0731-nvfp4-tp2-sglang | 💀 | — (dies in init) | 176GB | 0.80 | 2 | [Model][nvidia/DeepSeek-V4-Flash-0731-NVFP4] |
| deepseek-v4-flash-0731-mxfp4-tp2-nospec-sglang | 💀 | — (dies in init) | 167GB | 0.80 | 2 | [Model][deepseek-ai/DeepSeek-V4-Flash-0731] |
| deepseek-v4.1-flash-mxfp4-tp4-sglang | 💀 | — (fails fast: MoE /128) | 510GB | 0.80 | 4 | [Model][deepseek-ai/DeepSeek-V4.1-Flash] |
| deepseek-v4.1-flash-mxfp4-tp8-sglang | 💀 | — (needs 8 nodes; /128) | 510GB | 0.80 | 8 | [Model][deepseek-ai/DeepSeek-V4.1-Flash] |
| deepseek-v4.1-flash-exl3-tp3-vllm | | 15.8 / 47.1 / 69.1 | 460GB | 0.80 | 3 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |
| deepseek-v4.1-flash-exl3-tp4-vllm | | 37.5 / 61.9 / 88.5 | 460GB | 0.80 | 4 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |
| deepseek-v4.1-flash-exl3-tp4-1m-vllm | 🚚 | 1M ctx; needle ✓@799K; 746 t/s prefill | 460GB | 0.80 | 4 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |
| deepseek-v4.1-flash-exl3-tp6-vllm | | 29.4 / 63.8 / 108.0 | 460GB | 0.80 | 6 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |
| deepseek-v4.1-flash-exl3-tp6-1m-vllm | 🚚 | 1M ctx; KV 14.0M; needle ✓@799K | 460GB | 0.80 | 6 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |

**The five SGLang rows are failing for named, documented reasons, not "untested":**

- The three V4-Flash TP=2 rows all die ~5 min into init with one signature
  (rank-0 scheduler SIGTERM, no OOM, watchdog confirmed at 3600; DSpark, shared-
  expert fusion, and the watchdog are each ruled out by a control). Work doc §7.5.3.
- The two V4.1 SGLang rows hit the MXFP4-Cutlass MoE partition check:
  `moe_intermediate_size 2304 / 4 = 576` (and `/8 = 288`) is not a multiple of
  128 → `ValueError` at load. `dev-dsv41` also lacks the `b12x` kernels. TP=8
  additionally needs 8 nodes. Work doc §7.5.4.

**The five `exl3-*-vllm` rows** use the EXL3 3.5 bpw checkpoint and
`littlecedar/dgx-spark-dsv41:exl3a` with `mods/mount-dsv41-exl3-patches`
(Engram-on-disk; without it the boot OOMs). The t/s column is C1 / C4 / C8
aggregate, greedy, distinct prompts. C8 on TP=6 is the fleet's best. TP=6 is
no-spec (the DSpark drafter's 128 experts don't divide by 6); TP=4 carries DSpark.
Quality battery (measured on TP=3, TP=4 and TP=6): 19/19 easy, 17/18 hard,
identical across all three — no measured quality cost from the padding.
`tags: control, measurement_only` on the nospec V4-Flash arm marks it as a
benchmark denominator.

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
[deepseek-ai/DeepSeek-V4-Flash-0731]: https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731
[nvidia/DeepSeek-V4-Flash-0731-NVFP4]: https://huggingface.co/nvidia/DeepSeek-V4-Flash-0731-NVFP4
[deepseek-ai/DeepSeek-V4.1-Flash]: https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash
[bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard]: https://huggingface.co/bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard