# Little Cedar Sparkrun Recipes

_Brought to you by Little Cedar Group._

These are the recipes we are using in the office on our humble 6-node DGX Spark cluster.

# Recipes

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