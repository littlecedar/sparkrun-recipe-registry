# Little Cedar Group Recipes

_Brought to you by Little Cedar Group._

# Notes

## FastSafeTensors go _hnnnnnnnnggg_

TL;DR -- `fastsafetensors` will make it look like your machine is hung until the model shards finish loading. **This can
take a long time on large models** (30+ minutes for 397b models)**!**  Nothing is wrong with your Spark (s). Be patient.

To speed up model loading, we specify `load_format: fastsafetensors` in the recipes. The (mostly cosmetic) downside of [
`fastsafetensors`](https://github.com/foundation-model-stack/fastsafetensors/blob/main/README.md) is that it loads all
model shards simultaneously which causes a massive amount of CPU and IO load. Even on the DGX Spark, which is the
perfect candidate for `fastsafetensors`, this will cause the machine to _appear_ to be hung while model shards load.
Even if you're observing this with `sudo nice --20 btop`, you can expect to see CPU utilization ramp up to 100%, load
averages higher Everest, and everything goes _hnnnnnnnggg_ for a while. This is _normal_. idfk.

# Recipes

## Ornith 1.0

> "A completely badass agentic coding model that makes Swival do tricks."

| Flags | Parameters | Quant | Size (GB) | Nodes | GPU Mem | TP | Model Card                                           |
|-------|------------|-------|-----------|-------|---------|----|------------------------------------------------------|
| ✅    | 397b       | FP8   | 405.2     | 4     | 0.8     | 4  | ornith-ai/Ornith-1.0-397B-FP8                        |
| ❌    | 397b       | MXFP4 | 225.9     | 2     | 0.8     | 2  | model/olka-fi/Ornith-1.0-397B-MXFP4                  |
| ✅    | 35b        | BF16  |           | 2     | 0.8     | 0  | ornith-ai/Ornith-1.0-35B                             |
| ✅    | 35b        | FP8   | 70.3      | 1     | 0.8     | 0  | ornith-ai/Ornith-1.0-35B-FP8                         |
| ❌🔥  | 35b        | NVFP4 | 23.8      | 1     | 0.4     | 0  | AEON-7/Ornith-1.0-35B-AEON-Ultimate-Uncensored-NVFP4 |
| ✅    | 9b         | BF16  | 18.8      | 1     | 0.4     | 0  | ornith-ai/Ornith-1.0-9B                              |

## Flags

| Flag | Meaning               |
|------|-----------------------|
| ✅   | Official/original     |
| ❌   | Unofficial/derivative |
| 🔥   | Uncensored/unsafe     |

