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

| Recipe | Flags | t/s (C1 / C4 / C8 / C16) | Size | Mem | TP | Model Cards |
|:-------|:------|------:|-----:|----:|---:|:------------|
| deepseek-v4.1-flash-exl3-tp3-vllm | | 34.3 / 59.1 / 77.7 (k=3, DSpark) | 460GB | 0.80 | 3 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |
| deepseek-v4.1-flash-exl3-tp4-vllm | | 38.8 / 66.3 / 88.5 / 122.0 (k=3) | 460GB | 0.85 | 4 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |
| deepseek-v4.1-flash-exl3-tp4-1m-vllm | 🚚 | 40.7 / 65.4 / 84.5 / 121.3 (k=3); 1M ctx; needle ✓@799K | 460GB | 0.85 | 4 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |
| deepseek-v4.1-flash-exl3-tp6-vllm | | 40.0 / 78.0 / 107.9 / 151.1 (k=3, DSpark) | 460GB | 0.85 | 6 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |
| deepseek-v4.1-flash-exl3-tp6-1m-vllm | 🚚 | 43.4 / 72.7 / 110.2 / 149.1 (k=3, DSpark); 1M ctx; needle ✓@799K | 460GB | 0.85 | 6 | [Model][bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard] |

**The `exl3-*-vllm` rows** use the EXL3 3.5 bpw checkpoint and
`littlecedar/dgx-spark-dsv41:exl3a` with `mods/mount-dsv41-exl3-patches`
(Engram-on-disk; without it the boot OOMs). The t/s column is C1 / C4 / C8 / C16
aggregate, greedy, distinct prompts, **cold** server, non-streaming decode
(`usage.completion_tokens`/elapsed — NOT an SSE chunk count, which under-reports
~3.5× under spec decode). **All five rows ship DSpark k=3** (2026-09-27): TP=3
and TP=6 included, via the mod's `config_speculative.py`, which applies the
virtual-heads declaration to the drafter.

**Retune 2026-09-27 (this row set): the four TP=4/TP=6 recipes ship
`max_num_seqs: 16` and `gpu_memory_utilization: 0.85`, with the CUDA-graph
capture ladder extended to `16·(k+1) = 64`.** Every number above is from a boot
of the recipe **exactly as shipped**. Effect: the granted KV pool rose on every
arm — TP=4 300K 3.88M→**5.20M** tok (+34 %), TP=4 1M 4.20M→**5.75M** (+37 %),
TP=6 300K 12.0M→**13.6M** (+13 %), TP=6 1M 13.1M→**15.0M** (+15 %) — and C16 is
newly reachable (the old 8-seq cap queued it). `max_num_seqs` is the resident
slot count; **maximum concurrency is pool/ctx** (AGENTS.md §6.5), so the TP=4 1M
arm's 16 slots *queue* a full-1M workload rather than running it 16-wide, while
the other three run 16 concurrent requests outright. TP=3 is unchanged (8, 0.80)
— outside the retune's TP=4/TP=6 scope.

**The 1M rows now carry a 🚀 note in the prose, not a flag:** their C16
aggregate exceeds 60 t/s (121.3 / 149.1), so a case could be made for the `fast`
tag. **We did not add it**: the flag legend's own threshold is an *average*
("> 60t/s avg"), these are C16-*aggregate* figures, and the single-stream rates
(C1 40.7 / 43.4) sit below it. Tagging on an aggregate would be the exact
`tg t/s` misreading `benchmarking/README.md` warns against. A future retune may
promote it deliberately; this one does not.

**Watch the harness when comparing.** These C1/C4/C8/C16 come from one cold boot
each on the same bench script (`.scratch/ds4/gmu/measure_arm.py`, distinct
prompts, greedy, non-streaming). The earlier rows' 36.7/72.8/96.1 (TP=4) and
44.5/72.5/115.3 (TP=6 300K) came from the AGENTS.md §7.7 k-sweep harness at
gmu 0.80 / 8 seqs and are **NOT directly comparable** — compare within a harness,
and prefer the retune rows above. Inter-boot scatter on GB10 is 7–25 %; a single
boot per arm ranks nothing, so the C16 column (the least-scattered, most
capacity-bound cell) is the one to trust for the retune's effect.

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