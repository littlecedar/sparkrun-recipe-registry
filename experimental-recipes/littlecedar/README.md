# Little Cedar Sparkrun Recipes

_Brought to you by Little Cedar Group._
These are recipes we are using in addition to other recipes already provided, such as eugr's wonderful
qwen3-coder-next-fp8-vllm recipe that helped us bootstrap some of our inference infrastructure. Greetz and thank you, eugr!

# Notes

## b12x
There are a few flashinfer-b12x bugs which can lead to OOMs under the right conditions.  Trying to get Ornith-1.5-397b-NVFP4 to run with b12x backends, for example, is a fool's errand right now.  Immediately after the CuTe-DSL kernels finish compiling, RAM usage jumps by >32GB, for example.  Reasonably sure it's the flashinfer-b12x MoE backend bug already reported upstream: https://github.com/vllm-project/vllm/issues/49476

# Model Flags

| Flag | Meaning           |
|------|-------------------|
| ✅   | Official          |
| ✨   | Fast (>50t/s)     |
| ❌   | Unofficial        |
| 🔥   | Uncensored/unsafe |
| 💀   | Currently broken  |

_Flags indicate characteristics of the model._

# Recipes

## Ornith

| Flags | Params | Quant | Size GB | N | Mem | PP | TP | Backend    | t/s | Model Card                           |
|-------|--------|-------|---------|---|-----|----|----|------------|-----|--------------------------------------|
| ✅    | 397b   | FP8   | 405.2   | 4 | 0.8 | 1  | 4  | flashinfer |     | [ornith-ai/Ornith-1.5-397B-FP8]      |
| ✅    | 397b   | NVFP4 | 225.9   | 4 | 0.8 | 1  | 4  | marlin     |     | [ornith-ai/Ornith-1.5-397B-NVFP4]    |
| ✅💀  | 397b   | NVFP4 | 225.9   | 4 | 0.8 | 1  | 4  | fi-b12x    |     | [ornith-ai/Ornith-1.5-397B-NVFP4]    |
| ✅    | 35b    | FP8   | 37.7    | 1 | 0.4 | 1  | 1  | flashinfer |     | [ornith-ai/Ornith-1.5-35B-A3B-FP8]   |
| ✅    | 35b    | NVFP4 | 23.8    | 1 | 0.4 | 1  | 1  | marlin     |     | [ornith-ai/Ornith-1.5-35B-A3B-NVFP4] |
| ✅    | 35b    | NVFP4 | 23.8    | 1 | 0.4 | 1  | 1  | fi-b12x    |     | [ornith-ai/Ornith-1.5-35B-A3B-NVFP4] |

## Qwen

| Flags | Params | Quant | Size GB | N | Mem | PP | TP | Backend    | t/s | Model Card                  |
|-------|--------|-------|---------|---|-----|----|----|------------|-----|-----------------------------|
| ✅    | 397b   | FP8   | 405.2   | 1 | 0.4 | 1  | 1  | flashinfer |     | [Qwen/Qwen3.8-27B-FP8]      |
| ✅🔥  | 80b    | FP8   |         | 1 | 0.8 | 1  | 1  | flashinfer |     | [Qwen/Qwen3-Coder-Next-FP8] |

# References



[ornith-ai/Ornith-1.5-397B-FP8]: https://huggingface.co/ornith-ai/Ornith-1.5-397B-FP8
[ornith-ai/Ornith-1.5-397B-NVFP4]: https://huggingface.co/ornith-ai/Ornith-1.5-397B-NVFP4
[ornith-ai/Ornith-1.5-35B-A3B-FP8]: https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B-FP8
[ornith-ai/Ornith-1.5-35B-A3B-NVFP4]: https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B-NVFP4
[Qwen/Qwen3.8-27B-FP8]: https://huggingface.co/Qwen/Qwen3.8-27B-FP8