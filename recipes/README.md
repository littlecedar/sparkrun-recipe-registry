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
— plus `dev-dsv41` lacks the `b12x` kernels. See `recipes/ds4/AGENTS.md` §9.

| Recipe | Flags | t/s (C1 / C4 / C8) | Size | Mem | TP | Model Cards |
|:-------|:------|------:|-----:|----:|---:|:------------|
| deepseek-v4.1-flash-exl3-tp3-vllm | | 34.3 / 59.1 / 77.7 (k=3, DSpark) | 460GB | 0.80 | 3 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |
| deepseek-v4.1-flash-exl3-tp4-vllm | | 36.7 / 72.8 / 96.1 (k=3) | 460GB | 0.80 | 4 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |
| deepseek-v4.1-flash-exl3-tp4-1m-vllm | 🚚 | 1M ctx; needle ✓@799K; 746 t/s prefill | 460GB | 0.80 | 4 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |
| deepseek-v4.1-flash-exl3-tp6-vllm | | 44.5 / 72.5 / 115.3 (k=3, DSpark) | 460GB | 0.80 | 6 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |
| deepseek-v4.1-flash-exl3-tp6-1m-vllm | 🚚 | 1M ctx; KV 13.05M; C8 118.4 (k=3, DSpark); needle ✓@799K | 460GB | 0.80 | 6 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |

**The `exl3-*-vllm` rows** use the EXL3 3.5 bpw checkpoint and
`littlecedar/dgx-spark-dsv41:exl3a` with `mods/mount-dsv41-exl3-patches`
(Engram-on-disk; without it the boot OOMs). The t/s column is C1 / C4 / C8
aggregate, greedy, distinct prompts. **All five rows ship DSpark k=3**
(2026-09-27): TP=3 and TP=6 included, via the mod's `config_speculative.py`,
which applies the virtual-heads declaration to the drafter. **All three
DSpark-eligible arms booted and were measured 2026-09-27** — TP=3 34.3/59.1/77.7,
TP=6 300K 44.5/72.5/115.3, TP=6 1M 35.3/–/118.4 t/s, accept length ~2.4–2.5.
The TP=3/TP=6 single boots are **cold**; the TP=4 row and the 1M no-spec figures
are warm — compare within a regime. C8 on TP=6 (118.4 at 1M) is the fleet's best.
Quality battery (measured on TP=3, TP=4 and TP=6): 19/19 easy, 17/18 hard,
identical across all three — no measured quality cost from the padding.

**Watch the harness when comparing the TP=4 row.** Its shipped config changed to
k=3 and its numbers (36.7 / 72.8 / 96.1) come from the AGENTS.md §7.7 k-sweep harness —
the same harness measured k=5 at 33.3 / 62.1 / 84.4 on four boots. The earlier
k=5 "warm repeat" row (37.5 / 61.9 / 88.5) is a *different* harness and is NOT
directly comparable to the k=3 row; compare within the sweep, not across it.

**The DSpark draft depth is k=3, and that is measured, not inherited.** A 13-boot
sweep over k ∈ {1..5} on the TP=4 lane (AGENTS.md §7.7) found every k in {1,2,3}
beats the upstream-default k=5 at every concurrency ≥4: k=3 has the best C1
(+10% over k=5) and k=1 the best C8 (+27%). k=5 accepts *more* tokens per step
(2.44 vs 2.25) and is still *slower* — its 4th/5th verify slots land only 12%/5%
of the time. All five rows ship k=3; k=1 is the batch-serving arm. (k=6 is
illegal: vLLM rejects it, `must be divisible by n_predict=5`.)

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