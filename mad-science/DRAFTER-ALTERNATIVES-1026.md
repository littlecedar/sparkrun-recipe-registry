# Drafter alternatives search — DFlash/DSpark-style drafters for existing arms (owner round-4 §7 "also look for alternative drafters, such as DFlash and DSpark")

tp4-single, 2026-10-26, window 4. Read-only survey; no boots. Question: beyond the drafters our arms
already run, what drafter families exist, which are engine-supported in the images we actually pin,
and which have drafter weights for our checkpoints?

## Contents

- [What our arms run today (the baseline set)](#what-our-arms-run-today-the-baseline-set)
- [The drafter families the search surfaced](#the-drafter-families-the-search-surfaced)
- [Concrete next steps (each a separate task, none blocking)](#concrete-next-steps-each-a-separate-task-none-blocking)
- [Sources](#sources)

## What our arms run today (the baseline set)

| arm | engine | drafter | status |
|---|---|---|---|
| ds4 1017 (SGLang TP=4) | SGLang | **DSpark k=5** | engaged, window-3/4 receipts |
| GLM-5.3-Flash (TensorFold TP=4) | TensorFold | **DFlash2** (`incoai/GLM-5.3-Flash-DFlash2`, CC BY-NC-ND) | shipped, acceptance 76.6 % (trial) |
| Beam-1.0 501B (vLLM TP=4 probe) | vLLM | **DFlash2** (`…-DFlash2` @`163b276b`, pool snapshot path) | window-4 A/B: C1 +20 %, other cells within noise |
| qwen3.8-27b (SGLang probe) | SGLang | **DFlash2** | `qwen3.8-27b-nvfp4-dflash2-sglang.yaml` |
| Ornith-1.5-122B (vLLM TP=4) | vLLM | **MTP graft** (`mtp*` unquantised in the vendor NVFP4) | draft tier |
| Mellum2.1 12B (llama.cpp) | llama.cpp | **MTP head** (`-md` + `draft-mtp`) | measured-rejected at every length; n=1 retested 2026-10-26, rejection stands |
| zz ngram / UNO-tree probes | SGLang / llama.cpp | **NGRAM / UNO tree** | probed, retired (`attic/`) |

## The drafter families the search surfaced

1. **DSpark** (paper 2607.05147; SGLang integration `sgl-project/sglang#30261` at `692c5f7d`, image
   `lmsysorg/sglang:dev-dspark`; LMSYS blog 2026-07-06). Semi-autoregressive **block** drafter (dense
   line e.g. Qwen3, sparse line e.g. DeepSeek-V4) + confidence head + Sequential Temperature Scaling;
   per-request **variable-length verify** (`static`/`compact`/`cap-accept`) over ragged full-CUDA-graph
   replay; SPS cost-table scheduler inside the Spec-V2 overlap runtime. LMSYS reproduce the paper's
   shape on DeepSeek-V4-Flash H200 DP4: best throughput/latency frontier across batch 1–256, ahead of
   both MTP and non-spec; the dynamic trim's win is a **high-batch effect** (ties at batch 1). Roadmap
   issue `sgl-project/sglang#30344` (model/parallelism coverage still growing).
   *Relevance:* we already run DSpark k=5 on ds4 — the open cell is whether our engine build carries
   the ragged-verify/compact path (`SGLANG_RAGGED_VERIFY_MODE`) or a pre-`#30261` DSpark; a
   `dev-dspark`-class image would buy the high-concurrency trim our C10 aggregate cells measure.
2. **DFlash / DFlash2** (paper 2602.06036; LMSYS blog 2026-06-15 with Modal + Z Lab; SGLang **Spec V2**
   now default). Lightweight **block diffusion** drafter, parallel drafting, consistently ahead of
   EAGLE-3 in the paper across tasks and concurrency; the follow-on **DLoop** appears on the HF daily
   papers as the next iteration. Drafter weights are per-checkpoint artifacts (the reason GLM-Flash and
   Beam have DFlash2 packs and others do not).
   *Relevance:* adoption is gated by drafter-weights availability per checkpoint, not engine support —
   the same gate the Beam A/B hit. For checkpoints without a published pack (ds4 1017, ornith,
   GLM-5.3-753B), this stays a "when upstream publishes" item.
3. **EAGLE / EAGLE-3 and MTP** — the established baselines both papers beat; already represented in the
   fleet (MTP graft on ornith, MTP head on Mellum; SGLang `--speculative-algorithm EAGLE` is the MTP
   spelling in the DSpark repro). No new adoption surface.
4. **Medusa-style multi-heads** (vLLM blog 2026-07-28 "Parallel All the Way Down" surveys the
   single-token→parallel drafting shift; AMD-GPU post 2026-08-23 measures vLLM spec paths) —
   vLLM-side coverage exists, but no Medusa heads for our checkpoints; same weights-availability gate.
5. **Retrieval/tree drafters** (prompt-lookup, ngram, UNO tree) — already probed in this registry and
   retired negative (`attic/`); the 2026-10-22 k2-horizon UNO-tree probe and the spark-x2.6 ngram arm
   are the repo's own evidence that this family underperforms the block drafters here.

## Concrete next steps (each a separate task, none blocking)

- **Check our ds4 engine for post-`#30261` DSpark** (`SGLANG_RAGGED_VERIFY_MODE` in the image's arg
  parser / `strings` on sglang) — if absent, a `dev-dspark` image boot is the highest-value single
  boot: DSpark compact is exactly the mechanism our C10 aggregate cells are shaped by.
- **DFlash2 weights watch** for ds4 1017 / ornith: the Beam A/B's +20 % C1 (within-noise elsewhere)
  is the only same-window evidence; if Modal/Z Lab publish packs for those checkpoints, the A/B
  repeats with the [#36] ≥2 % keeper bar (spec-decode arms exempt per the drafter policy ruling).
- **llama.cpp `draft-dflash`**: upstream's arg parser already spells `--spec-type draft-dflash`
  (verified in-source at `a37cc4610`, `common/arg.cpp:4314-4324` + the optional FC-input-scale commit) —
  if a GGUF-convertible DFlash drafter appears for any of our llama.cpp checkpoints (Mellum first),
  the zz- probe pattern (one arm, `-o` knob, same sweep geometry) is the template.

## Sources

- `https://www.lmsys.org/blog/2026-07-06-dspark-sglang/` (DSpark in SGLang; `sglang#30261`, `#30344`,
  `dev-dspark` image, commit `692c5f7d`).
- `https://www.lmsys.org/blog/2026-06-15-next-generation-speculative-decoding-dflash-v2/` (DFlash +
  Spec V2 default).
- `https://arxiv.org/html/2607.05147v1` (DSpark paper), `https://arxiv.org/html/2602.06036v2`
  (DFlash paper, beats EAGLE-3 across tasks/concurrency).
- `https://vllm.ai/blog/2026-07-28-speculators-parallel-drafting` (parallel-drafting survey),
  `https://vllm.ai/blog/2026-08-23-speculative-decoding-amd-gpus` (vLLM spec measurements).
- In-repo receipts: window-3/4 ds4 DSpark k=5 engagements, Beam DFlash2 A/B
  (`beam-b1-ladder.csv` vs `beam-b2-ladder.{csv,yaml}`), Mellum MTP sweep + retest.