# Mistral-Large-4-1T-A52B-NVFP4 on the WOPR fleet — feasibility, 2026-11-03

**Status: analysis complete. Verdict: park it on the fleet.** No boot attempted, no node contacted, no
`ssh`, nothing in `recipes/` changed. This closes the queue row `mistral-large-4-1t-feasibility`.

Every weight byte below was recomputed on 2026-11-03 from the published checkpoint's own safetensors
headers — 32 ranged reads of the header JSON, which returns every tensor's dtype, shape, and offset.
The 32 header sums equal the index's `metadata.total_size` exactly, so the composition table in §2 is
the checkpoint, not the card. Card claims appear only where labeled AUTHOR-REPORTED.

Evidence labels: **VERIFIED** = read from a primary artifact here or measured on this fleet;
**LIKELY** = strong secondary evidence; **SPECULATIVE** = reasoning without a source.
`[INFERENCE]` marks arithmetic over verified inputs.

## Contents

- [1. What was read](#1-what-was-read)
- [2. What the checkpoint is](#2-what-the-checkpoint-is)
- [3. Fit arithmetic — every shape dies, for three different reasons](#3-fit-arithmetic--every-shape-dies-for-three-different-reasons)
- [4. The second, independent blocker: engine state](#4-the-second-independent-blocker-engine-state)
- [5. Three paths and what each costs](#5-three-paths-and-what-each-costs)
- [6. Displacement cost of any TP=6 attempt](#6-displacement-cost-of-any-tp6-attempt)
- [7. What would falsify this](#7-what-would-falsify-this)
- [8. Provenance](#8-provenance)

## 1. What was read

| artifact | value | label |
|---|---|---|
| repo | `mistralai/Mistral-Large-4-1T-A52B-NVFP4`, revision `bb6d00fe249b0e876f0cffc6b85014be02de3e68`, last modified 2026-10-29T16:46Z | VERIFIED (Hub API, 2026-11-03) |
| access, license | `gated: false`, `private: false`; `LICENSE` = Mistral Ecosystem Open-Weight License (2632 B), card: modified MIT, commercial use allowed, Model-as-a-Service resale needs a separate Mistral license | VERIFIED (tree + API); license *reading* AUTHOR-REPORTED |
| files | 44: 32 consolidated shards + index + `params.json` + `config`-side files + tokenizer, `tekken.json`, `chat_template.jinja`, `processor_config.json`, LICENSE, README, one evaluation PNG | VERIFIED (tree API) |
| bytes | shards 610,030,457,408 B on disk = index `metadata.total_size` 610,030,457,408; whole repo 610,105,677,691 B (tokenizer 27.9 MB + tekken 25.8 MB) | VERIFIED, both sums recomputed |
| base checkpoint | `mistralai/Mistral-Large-4-1T-A52B`, rev `af26e786…` (modified 2026-11-02), **1,060,618,650,948 B = 1060.6 GB / 987.8 GiB**, 54 shards + 71 files, FP8 block-128×128 with `modules_to_not_convert` naming the vision tower, projector, `kv_b_proj`, `indexer.wk`, indexer `weights_proj`, and `kv_a_proj_with_mqa` | VERIFIED (tree + `config.json`) |

No node was touched; nothing here is a boot claim.

## 2. What the checkpoint is

Architecture `MistralLarge4ForConditionalGeneration` (`model_type: mistral_large4`), MLA attention with
64 query and 64 KV heads, DeepSeek-style sparse attention (DSA), 128 routed experts top-4 plus one shared
expert, 72 layers (layer 0 dense), 204,800-token vocab, and an embedded DSpark draft head. All VERIFIED
from `params.json` and the tensor shapes:

- attention per layer: `wq [8192, 6144]` = 64 heads × 128 (nope 64 + rope 64), `wo [6144, 8192]` =
  64 heads × v_head_dim 128, `wkv_b [12288, 512]` = 64 heads × 192, `wkv_a_with_mqa [576, 6144]` =
  kv_lora_rank 512 + qk_rope 64. MLA, not MHA: the cache is the 576-value latent per layer.
- DSA indexer on **44 of 72** layers (`dsa.sharing` is a comma string of 44 `full` and 28 `shared`),
  `wk [128, 6144]`, one shared index key head, `wq_b [4096, 6144]` = 32 index heads × 128,
  `topk 2048`, `fp8_indexer: True`, `fp8_kv_cache: True`.
- KV sharing: `source_layers_str` maps 72 layers onto 63 distinct KV sources — layers
  39, 43, 47, 51, 55, 59, 63, 67, 71 all read layer 35's KV. **63 cache-bearing layers, not 72.**
- 1,048,576-token context: `max_position_embeddings 1048576`, YaRN ×2048 from 512.
- DSpark/MTP head: 3 backbone layers (dense FFN 24576) + `target_projection [6144, 30720]`
  (5 target layers × 6144, matching `target_activation_layers 1,18,36,54,71`), `markov_rank 512`,
  `head_type rnn`, `draft_input position_specific`, `depth 3`. 4.20 GB in BF16.
- vision encoder: 30 layers, hidden 2048, image 1540², patch 14 — 3.41 GB in BF16.
- quantization (`modelopt`, `MIXED_PRECISION`, group 16): routed experts NVFP4 (packed `U8`, one
  `F8_E4M3` scale per 16), everything else FP8 e4m3 per-block or BF16.

Measured composition:

| component | bytes | GB | share | params | bpw |
|---|---|---|---|---|---|
| routed experts (71 layers × 128 experts × 3 × 6144²) | 578,914,833,408 | 578.915 | 94.9 % | 1,029,181,538,304 | 4.500 |
| attention + DSA indexer (72 layers, incl. `kv_a_norm`) | 9,865,974,272 | 9.866 | 1.6 % | 9.109 B | 8.665 |
| shared expert (71 layers) | 8,042,443,776 | 8.042 | 1.3 % | 8.040 B | 8.002 |
| embed + lm_head (untied) + final norm | 5,033,177,088 | 5.033 | 0.8 % | 2.517 B | 16.000 |
| DSpark/MTP head | 4,199,938,048 | 4.200 | 0.7 % | 2.100 B | 16.000 |
| vision tower + adapter + patch merger | 3,408,437,248 | 3.408 | 0.6 % | 1.704 B | 16.000 |
| dense FFN, layer 0 | 453,095,424 | 0.453 | 0.1 % | 0.453 B | 8.002 |
| MoE router gates (71 × [128, 6144] BF16) | 111,673,344 | 0.112 | — | 0.056 B | 16.000 |
| per-layer FFN norms (72 × 6144 BF16) | 884,736 | 0.001 | — | 0.0004 B | 16.000 |
| `lerope.alpha` | 64 | — | — | 32 | 16.000 |
| **total** | **610,030,457,408** | **610.03 GB / 568.14 GiB** | | **1,053,161,275,680 = 1.0532 T** | **4.634** |

Every row is a byte count from the headers; the rows sum to the index's `total_size` exactly, which is
the check that the classification is complete rather than merely plausible.

Active parameters per token, computed from those shapes: 4 of 128 routed experts per MoE layer =
71 × 4 × 113,246,208 = 32.162 B, plus shared expert 8.040 B, attention + indexer 9.109 B, layer-0 dense
0.453 B, router gates 0.056 B, embed/head 2.517 B → **52.34 B active, 49.82 B excluding embeddings**
`[INFERENCE]`, against the card's 49 B / 52 B (AUTHOR-REPORTED). The name's "A52B" is consistent with
the tensors.

## 3. Fit arithmetic — every shape dies, for three different reasons

The fleet envelope, measured (fleet docs, VERIFIED): device **121.69 GiB** unified per node, **103.7 GiB
usable** once the OS and page cache take their ~18 GiB ([`DEEPSEEK.md`](DEEPSEEK.md):1494). The queue row's
"128 GB unified" is the marketing label for the same pool (121.69 GiB = 130.66 GB), and the row's
"~26 GB/rank left" subtracted from that label and ignored the OS reserve. Recomputed against the usable
line, TP=6 leaves **9.0 GiB**, not 26 GB — and less than that once §3.3 is applied.

### 3.1 Weights alone

| shape | weights/rank (naive ÷ ranks) | vs usable 103.7 GiB | vs device 121.69 GiB |
|---|---|---|---|
| TP=2 | 305.02 GB = 284.07 GiB | −180.4 GiB | −162.4 GiB |
| TP=4 | 152.51 GB = **142.03 GiB** | **−38.3 GiB** | **−20.3 GiB over the device** |
| TP=6 | 101.67 GB = **94.69 GiB** | +9.0 GiB | +27.0 GiB |
| TP=8 | 76.25 GB = 71.02 GiB | +32.7 GiB | +50.7 GiB |

TP=4 is not a tuning question: 142 GiB of weights cannot be loaded into a 121.69 GiB device, so the serve
refuses before any KV cache exists. That is the row's original verdict, confirmed.

### 3.2 KV cache — the number that decides TP=6

MLA latent per token per cache-bearing layer = 512 + 64 = 576 values; 63 layers (not 72, §2) →
**36,288 values/token**, plus the DSA index cache 44 layers × 128 = **5,632 values/token**.
With the card's required `--kv-cache-dtype fp8_ds_mla` and `fp8_indexer`, one byte each:

- **41,920 B/token = 40.9 KiB/token**, model-wide.
- 8k → 0.34 GB; 128k → 5.49 GB; **1M → 43.96 GB for a single sequence**.
- BF16 KV doubles it: 83,840 B/token, 87.91 GB at 1M — which is why the card pins fp8 KV.

TP=6 headroom after weights and one 1M sequence's KV: 101.67 + 7.33 = 109.0 GB of 111.34 GB of usable
memory per rank → **2.35 GB left** for activations, CUDA graphs, Expert-parallel buffers, and the
chunked-prefill working set of a 1M prompt. At 128k it is 8.76 GB left; at 8k, 9.62 GB.

### 3.3 Head divisibility — the actual arithmetic

Attention divides by whole heads, and this model has 64 query heads, 64 KV heads, and 32 index heads:

- 64 ÷ 6 = **10 with remainder 4**. `wq` has 8192 output rows = 64 × 128; 8192 ÷ 6 = **1365.33 rows**.
- 32 ÷ 6 = **5 with remainder 2**; indexer `wq_b` 4096 rows ÷ 6 = **682.67**.
- `wkv_b` 12,288 rows = 64 heads × 192; 12,288 ÷ 6 = 2,048 rows, which is 10.67 heads' worth. Whole rows,
  fractional heads — and row-divisibility is not head-divisibility, because each head's 192-row block is
  laid out contiguously.
- Legal TP degrees for 64 heads: 1, 2, 4, 8, 16, 32, 64. **Six is not one of them,** and neither vLLM nor
  SGLang splits a head across ranks.
- Expert parallelism is *not* the binding constraint: 128 experts ÷ 6 = 21.33, and uneven expert sharding
  is legal. The wall is heads alone.

### 3.4 The shapes people actually propose, all refuted

Per-rank bytes with each module placed where it must go: experts ÷ EP, `attention`, `shared expert`,
`embed`/head ÷ TP, and the vision tower (3.41 GB) and DSpark head (4.20 GB) **replicated** on every rank —
the usual case, since both *can* be tensor-parallel but serve lines frequently leave them whole `[INFERENCE]`.

| shape | heads ÷ TP | experts/rank | weights/rank | verdict |
|---|---|---|---|---|
| TP=4 | 16 ✓ | 144.7 GB | 147.4 GiB | impossible — 43.7 GiB over usable, before KV |
| TP=6 | 10.67 ✗ | 96.5 GB | 100.7 GiB | **impossible twice** — heads do not divide, and only 3.0 GiB survives before KV |
| TP=8 | 8 ✓ | 72.4 GB | 77.3 GiB | fits comfortably, but 8 ranks exceed a 6-node fleet |
| TP=2 × DP=3 (EP=6) | 32 ✓ | 96.5 GB | 107.9 GiB | impossible — 4.2 GiB over usable at zero KV |
| TP=1 × DP=6 (EP=6) | 64 ✓ | 96.5 GB | 118.8 GiB | impossible — 15.1 GiB over usable at zero KV |

The hybrid rows matter because they are the obvious answer to "6 does not divide 64": turn the sixth rank
into data parallelism instead of tensor parallelism. It fails on bytes, not on divisibility — 96.5 GB of
experts per rank is 87 % of the usable pool before a single KV page exists. Even the gentlest reading
(replicated vision and draft sharded instead of whole) leaves TP=2 × DP=3 at 106.0 GiB, still 2.3 GiB over.

**So: TP=4 dies on weight bytes, TP=6 dies on heads and then on bytes, the 6-rank hybrids die on bytes,
and the only shape that fits (TP=8) needs hardware this fleet does not have.**

## 4. The second, independent blocker: engine state

Memory is not the only thing standing in the way. No engine the registry can pin today can load this
architecture at all, which matters because it is the blocker path (a) does **not** escape.

**The card's own commands are the evidence.** vLLM: `--tensor-parallel-size 8 --kv-cache-dtype fp8_ds_mla`
— eight ranks, i.e. the publisher also considers 4 ranks insufficient. SGLang: `--tp-size 4
--speculative-algorithm DSPARK --max-running-requests 64`, where `--tp-size 4` is documented as "example
tensor-parallel size for a Blackwell node" — a 4-GPU B200/GB200 node of 180–192 GB per device, not four
GB10s of 121.69 GiB.

**Which images carry it, and what they are:**

| image | created (UTC) | build provenance | CUDA | what that means |
|---|---|---|---|---|
| `vllm/vllm-openai:mistral-large-4` | 2026-10-29T00:17Z (amd64), 00:32Z (arm64) | `VLLM_IMAGE_TAG=local/vllm-openai:dev`, `VLLM_BUILD_COMMIT=unknown`, `VLLM_BUILD_URL=` empty, pipeline `local` | 13.0.3 | a local, unreleased dev build with **no commit recorded** — not pinnable beyond its digest |
| `lmsysorg/sglang:mistral-large-4` | 2026-10-29T13:55Z | `SGLANG_BUILD_COMMIT=c10e0e17735f7981c7cc46891eed6908b7701e58`, tag `nightly-dev-20261029-c10e0e17`, Actions run 40793125062 | 13.0.3, NCCL 2.28.3 | a real commit, but a **nightly**, and `c10e0e17` is 444 commits *behind* main |

Both tags publish an arm64 variant (VERIFIED from the image indexes), and the arm64 vLLM config's
`TORCH_CUDA_ARCH_LIST=9.0 10.0 10.3 12.0 12.1` does include sm_121 — so a GB10 kernel-arch gap is *not*
the problem, which is worth stating because it is the usual first guess.

**Neither public main tree has the architecture** (read 2026-11-03):

- vLLM `main`, `vllm/model_executor/models/registry.py`: no `mistral_large4` key and no `MistralLarge4`
  class. The highest Mistral arch present is `mistral_large_3`.
- SGLang `main`: 11,863 files, no `mistral_large4` model file, no `le_chonk`, and `mistral.py` /
  `mistral_large_3.py` contain no reference to either. The highest Mistral arch present is
  `mistral_large_3`.
- The SGLang nightly's own tree at `c10e0e17` (11,555 files) likewise has no `mistral_large4` file, while
  its `dspark` footprint is 70 paths — the general spec-decode kernels exist, the arch does not.

**What does exist upstream** (so the missing part is narrow, and named):

- `fp8_ds_mla` and `nvfp4_ds_mla` KV dtypes: `vllm/config/cache.py:52-53`.
- `method="dspark"`: `vllm/config/speculative.py:81` (`DSparkModelTypes = Literal["dspark"]`), with
  `dspark_markov_rank` plumbing, and validators written for the `minimax_m3` and `qwen3` variants.

**What this model needs on top of that:** an arch implementation registering `mistral_large4` and its
`params.json` surface (MLA-64 with kv sharing over 63 sources, DSA with 32 index heads and topk 2048 on
44 of 72 layers, NVFP4 packed experts with per-16 scales, the vision tower), the DSpark path for this
checkpoint's `markov_rank 512` / `head_type rnn` / `position_specific` draft input, and `fp8_ds_mla` KV
(the card calls it *required*, not optional). Our production engine is the `ds4` line
(`littlecedar/dgx-spark-dsv41:canary-roce-aff52fa5`, a DeepSeek-V4.1-Flash fork pinned by digest, TP=4,
`mem-fraction-static 0.78`), which shares the DSA/MoE lineage but carries no `mistral_large4` `[INFERENCE:
it forks a tree that does not contain the arch]`.

Consequence: a fleet arm would be tuned against an unreleased branch of whichever engine, with no upstream
commit to bisect against and no release to pin. The house rule — every arm pins an image by digest *and*
names the engine ref it was built from — cannot be satisfied for the vLLM tag today, and is satisfied only
in the weak sense for the SGLang nightly.

## 5. Three paths and what each costs

### (a) Requantize to reach 4 ranks — a checkpoint-conversion project

Target, derived from the envelope rather than guessed. Per-rank budget = 0.85 × 121.69 = **103.44 GiB**
(the card's own `gpu_memory_utilization`), minus **8 GiB** for activations, CUDA graphs, and comm buffers
`[INFERENCE: no measurement of this model's activation peak exists; 8 GiB is the reserve the ds4 TP=4
line leaves itself at `mem-fraction-static` 0.78]`, minus KV for one sequence at the stated context:

| context | KV/rank (fp8) | weights/rank allowed | total weights | **overall bpw** | **routed experts bpw** |
|---|---|---|---|---|---|
| 8k | 0.08 GiB | 95.36 GiB | 409.6 GB | **3.11** | 2.94 |
| 128k | 1.28 GiB | 94.16 GiB | 404.4 GB | **3.07** | 2.90 |
| 1M | 10.23 GiB | 85.20 GiB | 365.9 GB | **2.78** | 2.60 |

The non-expert 31.1 GB stays as shipped (10.4 bpw), so the whole ask lands on the experts: **4.500 bpw
today, 2.6–2.9 bpw required.** Costs, in the order they bite:

1. **Source.** You cannot re-derive 2.6 bpw from 4-bit NVFP4 experts — that is double quantization of an
   already-quantized tensor. The usable source is the FP8 base repo: **1,060.6 GB / 987.8 GiB**, 54
   shards, 1.7× the NVFP4 download, pulled into the BeeGFS pool first.
2. **The conversion itself.** 1.029 T expert parameters re-quantized with per-expert or per-tier
   allocation, then accuracy-gated. The fleet has a precedent for the *scale* of this (the GSQ strata
   export, an externally built mixed-tier rebuild), and none for doing it in-house on a 1T-parameter MoE.
3. **The kernels.** Below 4 bits there is no NVFP4 tensor-core path; every sub-4-bit MoE route in this
   registry is a vendored-engine project (EXL3 on TensorFold, the strata `PTQ1_0`/`Q2_0`/`Q3_K` tiers on
   a research engine). None of them knows `mistral_large4`, so (a) inherits §4's blocker and adds its own.
4. **Calibration.** The heaviest weight residency this fleet has booted at TP=4 is GLM-753B at 3.0 bpw
   EXL3 — 282 GB total, **65.7 GiB/rank** `[INFERENCE: 753e9 × 3.0 / 8]`. Path (a) would ask 380–410 GB,
   i.e. **1.35–1.45× more weight per rank than any successful boot**, on a model whose per-token KV
   (41,920 B) is at the top of anything this fleet has served at that degree.

One thing (a) buys beyond TP=4: at ≤3.0 bpw the 6-node **TP=2 × DP=3** hybrid becomes viable — experts
578.9 × (3.0/4.5) ÷ 6 = 64.3 GB + 19.4 GB non-expert = 83.7 GB = 78.0 GiB/rank, leaving 25.7 GiB for KV
`[INFERENCE]`. Heads divide at TP=2. That shape is the only fleet-internal future for this model, and it
still needs the arch (§4) before any of it can be tested.

### (b) Rent an 8-rank box — the checkpoint fits as published

610.03 GB ÷ 8 = **76.25 GB = 71.02 GiB per rank**, and 64 ÷ 8 = 8 heads/rank, 32 ÷ 8 = 4 index heads/rank:
both divisibility walls vanish. One 8×B200 node (180 GB HBM each) leaves ~100 GB/rank for KV, so the 1M
context is free rather than fought for: 43.96 GB model-wide at 1M = 5.5 GB/rank.

| item | figure | label |
|---|---|---|
| hardware | 8× B200 (180 GB) / B300 (288 GB) / GB200 (192 GB), sm_100-class, NVFP4 native | the card's vLLM command is literally `--tensor-parallel-size 8` (VERIFIED); per-device capacities are vendor specs (LIKELY) |
| engine | Mistral's own `vllm/vllm-openai:mistral-large-4`, the card's exact command; the §4 provenance gap is theirs to carry | VERIFIED |
| weights | 610 GB download once, then 76.25 GB/rank resident leaving 72 GiB/rank spare | VERIFIED arithmetic |
| price | on-demand B200 price indexes updated 2026-10-27: lowest $3.50/GPU-hr, median $8.19 → **$28–66/hr** for 8 GPUs, **$672–1,572 per 24 h** | LIKELY (secondary price indexes, quoted 2026-11-03) |

What (b) answers that nothing else can: whether the model is worth any of this. One rented day gives a
house-battery score, a C1/C10 ladder, and DSpark acceptance on the model as published — none of which a
requant could produce honestly, because a requant's quality is exactly what would be in question.

### (c) Park it

Cost: zero, and nothing measured today depends on it. This is the recommendation for fleet work.

**Ranked verdict.** Park for the fleet. If the model is wanted on merit, rent the 8-rank box for one day
and let the numbers decide — (b) is bounded, reversible, and tests the model as published. Path (a) is
strictly dominated: it is a multi-day conversion on a 1.06 TB source, to a sub-4-bit format with no kernel
support, in an architecture no engine has — solving the *harder* half of §4 first, to save a rental bill.

## 6. Displacement cost of any TP=6 attempt

TP=6 is not a six-node-shaped experiment; it is the whole fleet. Displacing it costs:

- **The production serve.** `.31`–`.34` each run one container of
  `littlecedar/dgx-spark-dsv41:canary-roce-aff52fa5` (DeepSeek-V4.1-Flash-1017, TP=4, `ep-size 1`,
  `mem-fraction-static 0.78`), `Up 7 days (healthy)` at the 2026-11-03 12:02 ET census. A six-rank window
  stops it for the window's whole duration.
- **The campaign baseline, not just the day.** That serve *is* the reference arm for every TP=4
  head-to-head cell in [`TP4-HEAD-TO-HEAD-1025.md`](TP4-HEAD-TO-HEAD-1025.md) and the shipped ladder's
  floor. Killing it mid-campaign invalidates same-window comparisons, not merely the hours it is down.
- **A cold restart on exit.** Weight load, CUDA-graph capture, and cold Engram first reads (measured
  1497.7 µs cold versus 0.5 µs hot per 4 KiB block, `.35`, n=200) — the serve comes back worse than it
  left, for a while.
- **Declaration, not scheduling.** A four-rank claim already needs a declared window and the
  `.local/fleet-window.lock` (`AGENTS.md`); a six-rank claim is the maximum the fleet can express, and it
  cannot run as a background job beside anything. It also would not work: §3.3 rules TP=6 out on
  divisibility, so the window would buy a failed boot at full-fleet cost.

The row's `node_cost` is deliberately blank: this study cost no node time and proposes none.

## 7. What would falsify this

- **A published sub-4-bit `mistral_large4` checkpoint with kernels** (experts at ≤2.9 bpw from a
  trustworthy producer, not a requant of the NVFP4) turns (a) from a project into a download.
- **The arch landing in a released vLLM or SGLang, at a named commit**, makes §4 solvable and lets anyone
  measure the thing on rented hardware with a pinnable engine.
- **A variant with a head count divisible by 6** (48 or 96 heads) would reopen the six-node shapes — the
  bytes still fail, but the hybrid TP=2 × DP=3 would only need a quantization nudge, not a project.
- **A 4-rank-capable published quant at ≤3.1 bpw** is the single fact that would move the verdict on the
  fleet. Nothing about the current checkpoint can be argued into that shape: 142 GiB/rank is 121.69 GiB
  of device.

What does *not* change the verdict: a faster interconnect, more concurrency headroom, or an engine patch
that pads heads. Padding 64 heads to 66 to make 11 per rank requires sharding a pre-quantized, per-head
MLA layout the checkpoint does not provide, and re-quantizing the attention weights to do it.

## 8. Provenance

| source | what it gave | read |
|---|---|---|
| Hub API `models/mistralai/Mistral-Large-4-1T-A52B-NVFP4` + `/tree/main?recursive=true` | revision, gating, 44-file list and sizes | 2026-11-03 |
| `consolidated.safetensors.index.json` `metadata.total_size` + 32 safetensors headers (ranged reads) | every tensor's dtype, shape, offset; the §2 composition and bpw table | 2026-11-03 |
| `params.json` (42,094 B), `config.json` of the base repo, `LICENSE`, `README.md`, `processor_config.json` | architecture, MLA/DSA/kv-sharing/MTP surface, quantization config, card commands, license | 2026-11-03 |
| Hub API `models/mistralai/Mistral-Large-4-1T-A52B` + tree | FP8 base repo, 1060.6 GB, 54 shards, `modules_to_not_convert` | 2026-11-03 |
| Docker Registry API, `vllm/vllm-openai:mistral-large-4` and `lmsysorg/sglang:mistral-large-4` (amd64 and arm64 config blobs) | creation dates, digests, build commits, CUDA/NCCL versions, `TORCH_CUDA_ARCH_LIST` | 2026-11-03 |
| `raw.githubusercontent.com` vLLM `main` (`models/registry.py`, `config/cache.py`, `config/speculative.py`); SGLang `main` tree, `mistral.py`, `mistral_large_3.py`, and the tree at `c10e0e17` | absence of `mistral_large4`, presence of `fp8_ds_mla` and `dspark` | 2026-11-03 |
| [`DEEPSEEK.md`](DEEPSEEK.md):1494 and `AGENTS.md` fleet notes | 121.69 GiB device, ~103.7 GiB usable | house doc |
| [`STATUS.md`](STATUS.md) 12:02 ET census, [`TP4-HEAD-TO-HEAD-1025.md`](TP4-HEAD-TO-HEAD-1025.md) | production pin, TP=4 shape, `Up 7 days`, baseline role | house doc |
| on-demand B200 price indexes (inferencehub.org/gpus/b200 updated 2026-10-27; bargo.ai/gpu/b200) | $3.50–8.19 per GPU-hour | 2026-11-03, LIKELY |

Author-reported and not verified here: the card's evaluation table (NVFP4 matches FP8 across GDP.pdf,
MathVision, Graphwalks 512k, DeepSWE, SWE-bench Pro, Terminal-Bench 4, AutomationBench, CyberGym), its
49 B/52 B active-parameter split, and the license's own summary of the license text.
