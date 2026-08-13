# Little Cedar Sparkrun Recipes

_Brought to you by Little Cedar Group._
These are recipes we are using in addition to other recipes already provided, such as eugr's wonderful
qwen3-coder-next-fp8-vllm recipe that helped us bootstrap some of our inference infrastructure. Greetz and thanks to
you, eugr!

# Notes

## FastSafeTensors go _hnnnnnnnnggg_

TL;DR -- Loading large models loaded by `fastsafetensors` will make it look like your machine is hung until the model
shards finish loading. **This can take a long time on large models** (> 30 minutes for 397b models)**!**  Nothing is
wrong with your Spark (s), they are just sweating.

To speed up model loading, we specify `load_format: fastsafetensors` in the recipes. The (mostly cosmetic) downside of [
`fastsafetensors`](https://github.com/foundation-model-stack/fastsafetensors/blob/main/README.md) is that it loads all
model shards simultaneously which causes a massive amount of CPU and IO load. Even on the DGX Spark, which is the
perfect candidate for `fastsafetensors`, this will cause the machine to _appear_ hung while model shards load. Even if
you're observing this with `sudo nice --20 btop`, you can expect to see CPU utilization ramp up to 100%, load averages
higher Everest, and everything goes _hnnnnnnnggg_ for a while. This is apparently _normal_. idfk. `¯\_(ツ)_/¯`

## Model Flags

| Flag | Meaning               |
|------|-----------------------|
| ✅   | Official/original     |
| ✨   | Fast (>50t/s)         |
| ❌   | Unofficial/derivative |
| 🔥   | Uncensored/unsafe     |

_Flags indicate characteristics of the model._

# Recipes

## Ornith 1.0

> "A completely badass agentic coding model that makes Swival do tricks."

| Flags | Parameters | Quant | Size (GB) | Nodes | GPU Mem | TP | Model Card                                             |
|-------|------------|-------|-----------|-------|---------|----|--------------------------------------------------------|
| ✅    | 397b       | FP8   | 405.2     | 6     | 0.8     | 6  | [ornith-ai/Ornith-1.0-397B-FP8]                        |
| ❌    | 397b       | MXFP4 | 225.9     | 4     | 0.8     | 4  | [model/olka-fi/Ornith-1.0-397B-MXFP4]                  |
| ✅    | 35b        | FP8   | 37.7      | 1     | 0.4     | 0  | [ornith-ai/Ornith-1.0-35B-FP8]                         |
| ❌🔥  | 35b        | NVFP4 | 23.8      | 1     | 0.4     | 0  | [AEON-7/Ornith-1.0-35B-AEON-Ultimate-Uncensored-NVFP4] |
| ❌    | 9b         | NVFP4 | 11.7      | 1     | 0.2     | 0  | [forgeguard-ai/Ornith-1.0-9B-NVFP4]                    |
| ❌🔥  | 9b         | NVFP4 | 8.9       | 1     | 0.2     | 0  | [maci0/Ornith-1.0-9B-abliterated-NVFP4]                |

# References



[ornith-ai/Ornith-1.0-397B-FP8]: https://huggingface.co/ornith-ai/Ornith-1.0-397B-FP8
[model/olka-fi/Ornith-1.0-397B-MXFP4]: https://huggingface.co/olka-fi/Ornith-1.0-397B-MXFP4
[ornith-ai/Ornith-1.0-35B-FP8]: https://huggingface.co/ornith-ai/Ornith-1.0-35B-FP8e
[AEON-7/Ornith-1.0-35B-AEON-Ultimate-Uncensored-NVFP4]: https://huggingface.co/AEON-7/Ornith-1.0-35B-AEON-Ultimate-Uncensored-NVFP4
[forgeguard-ai/Ornith-1.0-9B-NVFP4]: https://huggingface.co/forgeguard-ai/Ornith-1.0-9B-NVFP4
[maci0/Ornith-1.0-9B-abliterated-NVFP4]: https://huggingface.co/maci0/Ornith-1.0-9B-abliterated-NVFP4