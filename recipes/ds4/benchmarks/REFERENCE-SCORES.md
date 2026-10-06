# Published reference scores — DeepSeek-V4.1-Flash

Context for the local measurements in this directory. The question this file
answers: **what numbers do DeepSeek and independent evaluators publish for
DeepSeek-V4.1-Flash, so we can say whether our own local numbers are sane?**

Scope and method:

- Every row carries the benchmark + metric, the source with a full URL, the date,
  and a confidence label.
- **Primary source first.** DeepSeek's own model card, technical report, and API
  changelog are treated as one voice; independent runs (Artificial Analysis, Vals
  AI, MathArena, LiveBench aggregators) are separate voices.
- Two numbers from the *same vendor* are not "independent" — they count once.
- Where sources conflict, both are shown and the stronger source is named.
  Nothing is averaged silently.
- **Absent numbers are marked "not published". Nothing here is estimated or
  inferred from a related model.** If it is not in a source, it is not in this
  file.

Confidence labels:

| Label | Meaning |
|:--|:--|
| `VERIFIED` | Primary source (model card / tech report / changelog / official leaderboard), or two genuinely independent sources agree. |
| `LIKELY` | A single credible secondary source; not corroborated. |
| `SPECULATIVE` | Provenance unclear, or the number appears to be misattributed/conflated with another model. |

Access date for every URL below: **2026-10-05**. Model release date: **2026-09-10**.

Primary sources:

- Model card: <https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash>
- Technical report (arXiv): <https://arxiv.org/html/2609.19969v1> (mirror of the
  card's `DeepSeek_V41_Tech_Report.pdf`)
- API changelog: <https://api-docs.deepseek.com/updates/>
- EXL3 checkpoint card: <https://huggingface.co/Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw>

A note on what the base-model table is. DeepSeek publishes two separate tables.
The **base model** table (MMLU-Pro, HumanEval, MATH, GSM8K, HellaSwag, …) is a
*pretraining* evaluation of a **different checkpoint** (the `-Base` model), not
the instruct model we serve. The **instruct** table (GPQA Diamond, HLE,
Terminal-Bench, DeepSWE, …) is the released instruct model at max reasoning
effort. Mixing them up is the single easiest way to make a local number look
"wrong". Keep the columns straight.

---

## 1. Base model (pretraining checkpoint, not the instruct model)

Source: model card + technical report Table 1. All "scores within 0.3 are
equivalent" per the card. `DeepSeek-V4.1-Flash-Base`, internal harness.

| Benchmark (Metric) | Shots | DS-V4.1-Flash-Base | Confidence | Note |
|:--|:--|--:|:--|:--|
| MMLU-Pro (EM) | 5-shot | 74.1 | `VERIFIED` | Card + report Table 1 agree |
| AGIEval (EM) | 3–5-shot | 83.4 | `VERIFIED` | Card + report |
| C-Eval (EM) | 5-shot | 92.1 | `VERIFIED` | Card + report |
| SuperGPQA (EM) | 5-shot | 53.1 | `VERIFIED` | Card + report |
| SimpleQA-Verified (EM) | 25-shot | 42.3 | `VERIFIED` | Card + report |
| BBH (EM) | 3-shot | 86.1 | `VERIFIED` | Card + report |
| BBEH (EM) | 1-shot | 27.2 | `VERIFIED` | Card + report |
| DROP (F1) | 1-shot | 87.9 | `VERIFIED` | Card + report |
| HellaSwag (EM) | 0-shot | 87.2 | `VERIFIED` | Card + report |
| BigCodeBench (Pass@1) | 3-shot | 60.6 | `VERIFIED` | Card + report |
| **HumanEval (Pass@1)** | **0-shot** | **79.4** | `VERIFIED` | Card + report |
| **GSM8K (EM)** | **8-shot** | **93.0** | `VERIFIED` | Card + report |
| **MATH (EM)** | **4-shot** | **61.1** | `VERIFIED` | Card + report. This is **MATH**, not MATH-500 |
| MGSM (EM) | 8-shot | 80.2 | `VERIFIED` | Card + report |
| LongBench-V2 (EM) | 1-shot | 45.2 | `VERIFIED` | Card + report |
| MMMU-Pro (EM) | 4-shot | 56.5 | `VERIFIED` | Multimodal; card + report |
| CVBench (EM) | 4-shot | 77.9 | `VERIFIED` | Multimodal; card + report |
| DocVQA (LLM-Judge) | 4-shot | 95.6 | `VERIFIED` | Multimodal; card + report |
| RefCOCO-avg (Acc@0.5) | 0-shot | 86.0 | `VERIFIED` | Multimodal; card + report |

**Base-model gaps:** MMLU (non-Pro), MBPP, MATH-500, AIME, LiveCodeBench,
HumanEval-Plus — **not published** for the base model.

---

## 2. Instruct model — reasoning & knowledge

Source: model card + technical report Table 3 + API changelog. All instruct rows
use **max reasoning effort** (`reasoning_effort=100`), `temperature=1.0`,
`top_p=0.95`.

| Benchmark (Metric) | Score | Confidence | Sources / notes |
|:--|--:|:--|:--|
| **GPQA Diamond (Pass@1)** | **90.9** | `VERIFIED` | Card + report Table 3 + [changelog](https://api-docs.deepseek.com/updates/) + [HF eval-results tab](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash) all agree |
| **HLE (Pass@1)** | **36.8** (39.1 text-only) | `VERIFIED` | Card + report + changelog agree. 39.1† is the text-only subset |
| HLE w/ tools (Pass@1) | 63.9 | `VERIFIED` | Card + report + changelog |
| Codeforces (Rating) | 3471 | `VERIFIED` | Card + report + changelog. Internal benchmark |
| MathArena Apex (Pass@1) | 65.6 | `VERIFIED` | Card + report + changelog. Sept 2026 edition |
| AIME 2026 (Pass@1) | **100** (at max effort) | `VERIFIED` (as reported) | Technical report §B.3 text: "AIME 2026 reaches a full 100%". No shot count given |
| AIME 2025 | *(see conflict §5)* | `SPECULATIVE` | Only attributed to V4.1-Flash by a secondary blog; the 87.5 figure is the **R1-0528** changelog number. Do not trust for V4.1-Flash |

**Reasoning gaps:** MMLU-Pro **for the instruct model** — not published (only the
base-model 74.1 exists). MATH-500, AIME 2024, AIME 2025 (as a clean V4.1-Flash
number), LiveCodeBench discrete score — **not published**.

---

## 3. Instruct model — agentic & coding

Source: model card + report Table 3 + changelog. Code-agent rows use DeepSeek
Harness "Minimal" mode with a 1M-token context; DeepSWE v1.1 uses mini-SWE; all at
max reasoning effort, `temperature=1.0`, `top_p=0.95`. N=8 samples/task on
DeepSWE v1.1, N=3 on Terminal-Bench 2.1.

| Benchmark (Metric) | DeepSeek (own harness) | Confidence | Notes |
|:--|--:|:--|:--|
| **Terminal-Bench 2.1 (Pass@1)** | **90.6** | `VERIFIED` | Card + report + changelog. See §5 for the Vals independent conflict |
| Terminal-Bench 3.0 (Pass@1) | 30.0 | `VERIFIED` | Card + report + changelog |
| Terminal-Bench 4.0 (Pass@1) | 31.2 | `VERIFIED` | Card + report + changelog |
| **DeepSWE v1.1 (Resolved)** | **74.2** | `VERIFIED` | Card + report + changelog + HF eval-results |
| ProgramBench (Almost@1) | 20.3 | `VERIFIED` | Card + changelog. Report stores 20.3 as well |
| NL2Repo-Bench (Score) | 65.4 | `VERIFIED` | Report + changelog; **card table prints 64.0 for the same row** (minor internal disagreement, §5) |
| CyberGym (Pass@1) | 88.1 | `VERIFIED` | Card + report + changelog |
| SEC-Bench Pro (Pass@1) | 62.8 | `VERIFIED` | Card + report + changelog |
| ExploitGym (Pass@1) | 15.3 | `VERIFIED` | Card + report + changelog |
| Automation-Bench (Pass@1) | 54.8 | `VERIFIED` | Card + report + changelog |
| Agents' Last Exam (Pass@1) | 31.8 | `VERIFIED` | Card + report + changelog |
| Chartography w/ tools (Pass@1) | 78.9 | `VERIFIED` | Multimodal agent; card + report |
| BabyVision w/ tools (Pass@1) | 89.6 | `VERIFIED` | Multimodal agent; card + report |
| ZeroBench-main w/ tools (Pass@5) | 49.0 | `VERIFIED` | Multimodal agent; card + report |

**Agentic gaps:** **SWE-bench Verified is not published for V4.1-Flash** (only
V4-Flash 0731 at 88.80% and V4-Pro 0813 at 96.40% on the Vals leaderboard), and
**Aider Polyglot is not published** for V4.1-Flash.

---

## 4. Third-party independent evaluations

These are run by outside parties, not DeepSeek. Different harness, shot count, and
prompt format from DeepSeek's own — **not directly comparable** to §2–§3.

### 4a. Artificial Analysis Intelligence Index

| Metric | Model variant | Score | Date | Confidence | Source |
|:--|:--|--:|:--|:--|:--|
| **AA Intelligence Index** | V4.1 Flash (**Max** / reasoning) | **39** | 2026-09-10 → accessed 2026-10-05 | `VERIFIED` | [artificialanalysis.ai/models/deepseek-v4-1-flash](https://artificialanalysis.ai/models/deepseek-v4-1-flash) |
| AA Intelligence Index | V4.1 Flash (Non-reasoning) | 25 | 2026-09-10 | `VERIFIED` | same release page, [releases/deepseek-v4-1-flash](https://artificialanalysis.ai/models/releases/deepseek-v4-1-flash) |
| HLE (AA's own run) | V4.1 Flash (Max) | 39.2% | 2026-09-10 | `LIKELY` | Appears in OpenRouter's AA-sourced summary; not independently confirmed on the AA page. Consistent with DeepSeek's 39.1 text-only |

The AA index is v4.3.2, a composite of 10 evals (AA-Briefcase v1.1, GDPval-AA
v2.1, AutomationBench-AA, Terminal-Bench 4.0, SciCode, HLE, GDP.pdf, CritPt,
AA-Omniscience, AA-LCR v1.1). **A score of 40 was briefly circulated** (DeepInfra
blog, an AA X post); the AA page currently reads **39** (§5). Always check the
composite date, not just the number.

### 4b. Vals AI (independent agentic harness, mostly proprietary benchmarks)

Source: <https://www.vals.ai/models/deepseek_deepseek-v4.1-flash> (release note
dated 2026-09-10). Temperature 1, default top-p, high reasoning effort.

| Benchmark | V4.1-Flash | Confidence | Notes |
|:--|--:|:--|:--|
| Vals Index | 51.32% ± 1.13 (#23/43) | `VERIFIED` | Vals' own page; note their release note quotes 57.86% for the open-weights sub-table |
| Terminal-Bench 2.1 | **74.53%** (3 trials) | `VERIFIED` | Independent harness — far below DeepSeek's own 90.6; see §5 |
| Terminal-Bench 4.0 | 19.70% | `VERIFIED` | vs DeepSeek's 31.2 |
| SkillsBench | 69.80% | `VERIFIED` | #1/35; 61.66% without skills |
| Vibe Code Bench v1.1 | 84.74% | `VERIFIED` | #2 open-weight |
| Code Migration | 45.62% | `VERIFIED` | #1 open-weight |
| SWE-bench Verified | *(not listed for V4.1-Flash)* | — | Vals lists V4-Flash 0731 (88.80%) and V4-Pro 0813 (96.40%), not V4.1-Flash |

### 4c. MathArena (independent)

Source: <https://matharena.ai/models/deepseek_deepseek_v41_flash> (2026-09-10).

| Metric | Score | Confidence | Notes |
|:--|--:|:--|:--|
| Expected Performance (overall) | 43.3% (#20) | `VERIFIED` | MathArena's own normalized metric, **not** Apex Pass@1 |
| Overall ArXivMath | 53.28% ± 5.34% | `VERIFIED` | Independent |
| Overall BrokenArXiv | 40.87% ± 5.29% | `VERIFIED` | Independent |

DeepSeek's own **MathArena Apex 65.6** (§2) is a different metric on a different
edition — not comparable to MathArena's "Expected Performance" 43.3%.

### 4d. LiveBench (aggregated by llmrun.dev)

Source: <https://llmrun.dev/model/deepseek-ai-deepseek-v4-1-flash/benchmarks>
(2026-09-26). Aggregated from public LiveBench scores; llmrun does not run them.

| Benchmark | Score | Confidence |
|:--|--:|:--|
| LiveBench Coding | 80.0 | `LIKELY` |
| LiveBench Math | 93.3 | `LIKELY` |
| LiveBench Reasoning | 86.7 | `LIKELY` |

LiveBench is a useful independent frame for coding/math/reasoning, but these are
aggregated secondary numbers; treat as directional.

### 4e. Aggregator composites (use with care)

| Source | Metric | Value | Confidence | Notes |
|:--|:--|--:|:--|:--|
| llm-stats | LLM Stats Score rank | #15 | `LIKELY` | <https://llm-stats.com/models/deepseek-v4.1-flash> |
| BenchLM | BenchAlign score | 67.72/100 (#24/212) | `LIKELY` | <https://benchlm.ai/models/deepseek-v4-1-flash> — explicitly notes it stores *no* base-model rows on this instruct profile |
| llmrun | Composite (open models) | #4–#5 of ~78–99 | `LIKELY` | Value drifts between snapshots |

These are weighted composites over heterogeneous, mostly vendor-reported rows.
They are context, not ground truth.

---

## 5. Conflicts and things that look misattributed

1. **Terminal-Bench 2.1: 90.6 (DeepSeek) vs 74.53 (Vals).** Both are real; they
   differ by harness and scoring protocol. DeepSeek uses its own DeepSeek Harness
   Minimal mode at N=3; Vals uses a bash-only `mini-swe-agent` harness. **Neither
   is wrong — they measure different agent setups.** Quote the harness with the
   number. The Vals figure is the more conservative "what a generic bash agent
   gets" number.

2. **AA Intelligence Index: 39 (current AA page) vs 40 (DeepInfra blog, AA X
   post).** The AA page is the stronger source and updates as the index version
   changes (v4.3.2 as of access). Treat **39** as current. The 39.2 HLE figure in
   OpenRouter's summary likewise needs re-checking against AA directly.

3. **AIME 2025 = 87.5 → likely a misattribution.** A DeepInfra blog lists "AIME
   2025: 87.5%" under a V4.1-Flash capability table. The *only* primary `87.5` in
   DeepSeek's own docs is from the **2025-05-28 DeepSeek-R1-0528** changelog
   ("AIME 2025: 70.0 → 87.5"). The 2026-09-10 V4.1-Flash release notes list **no
   AIME 2025 number**. The technical report references **AIME 2026** (100% at max
   effort) in an aggregate figure. **Do not use 87.5 for V4.1-Flash.** Marked
   `SPECULATIVE`.

4. **MMLU 91 / MMLU-Pro 81.2 (DeepInfra) → likely misattributed.** The same blog
   table lists "MMLU 91%, MMLU-Pro 81.2%". DeepSeek publishes **no MMLU** for
   V4.1-Flash, and its MMLU-Pro is **74.1** (base, 5-shot). The `81.2` matches the
   **V3-0324** MMLU-Pro changelog entry. Treat both as `SPECULATIVE` for
   V4.1-Flash.

5. **NL2Repo-Bench 65.4 (report/changelog) vs 64.0 (card table).** Minor
   internal disagreement within DeepSeek's own release; BenchLM stores 65.4 citing
   the changelog. Use **65.4** and note the card prints 64.0.

6. **HF eval-results tab vs card.** The card's HF "Evaluation results" widget
   shows GPQA-Diamond 90.9, DeepSWE 74.2, Terminal-Bench 2.1 90.6 — all consistent
   with the card body. No conflict.

---

## 6. What is NOT published for the EXL3 2.9bpw checkpoint

**Verified: the EXL3 2.9 bpw checkpoint publishes no accuracy evaluations of its
own.** This is the gap our local measurement fills.

**Mia-AiLab HF card** — <https://huggingface.co/Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw>.
The card documents *quantization parameters only* (bpw 2.90, codebook `mul1`,
head_bits 6, mtp_bits 4, K-map, calibration trace, DSpark block size). It contains
**no benchmark scores**, and it says so explicitly:

> "Scores there are for the unquantized model, not this EXL3 build."
> — the card, referring to the base model's evals

**MiaAI-Lab GitHub repo** —
<https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-EXL3-2x-DGX-Sparks>. The repo
documents memory, throughput, prefill tok/s, cooperative-MoE decode deltas,
vision smoke tests, and kernel-envelope constraints. It publishes **no accuracy
benchmarks**, and states the gap plainly:

> "What is _not_ established: any quality parity probe against the native
> checkpoint."
> — repo README, images section

So: **no HLE, GPQA, MMLU-Pro, MATH, AIME, HumanEval, MBPP, SWE-bench Verified,
Terminal-Bench, or LiveCodeBench accuracy number exists for the EXL3 2.9 bpw
checkpoint from its authors.** There is no artifact to sanity-check a local
accuracy number against, on either the HF card or the GitHub repo.

**One loosely relevant third-party data point** (not from Mia-AiLab, not
corroborated): an NVIDIA developer-forum user (2026-09-14) reports "the DeepSeek
v4.1 Flash [EXL3 2x Spark] also reaches only 86/100 in my tests so far" at
`effort=max`, alongside GLM-5.3-Flash at 87/100 — on an unnamed 100-point internal
battery, temperature reportedly 1.0.
Source: <https://forums.developer.nvidia.com/t/deepseek-v4-1-flash-exl3-2-9-bpw-for-2x-dgx-sparks/383242>.
Labeled `SPECULATIVE`: single anonymous forum run, unknown task set, unknown
scoring. It is not a substitute for a controlled eval and is not comparable to
any row above.

---

## 7. Does this make our local numbers sane?

What our directory measures (see [`README.md`](README.md)) is **GSM8K 0-shot,
ARC-Challenge 0-shot, and a 37-item house battery**, on both the official-weights
lane (`deepseek`) and the EXL3 2.9 bpw lane (`deepseek-turbo`).

Sanity frame from the published numbers:

- **GSM8K.** DeepSeek's base-model number is **93.0 (8-shot)**. Our 0-shot
  measurement of ~97% on the *instruct* model at `temperature=0` is a different
  shot count and a different checkpoint, so it is not a mismatch — an instruct
  model scoring *higher* than its base model 0-shot vs the base 8-shot is
  expected, not alarming. There is **no published instruct-model GSM8K** to compare
  against, so our number stands alone as a local baseline.
- **GPQA Diamond 90.9 / HLE 36.8 / MMLU-Pro 74.1 / Terminal-Bench 90.6** are the
  only numbers meaningful for contextualizing hard-reasoning claims — and none of
  them can be reproduced through the gateway (it is chat-completions-only; see
  the README's "no lm-eval-harness numbers" caveat).
- **Nothing published exists for the EXL3 2.9bpw checkpoint at all** (§6), which
  is precisely why the local EXL3-vs-official comparison in this directory is the
  only quality evidence for that quant.

**Bottom line:** the published frontier numbers (GPQA Diamond 90.9, Terminal-Bench
2.1 90.6 own-harness, AA index 39) describe the unquantized instruct model. Our
local GSM8K/ARC/house-battery numbers are a lower-tier, generative-only frame with
no published counterpart, so they cannot be "checked" against a single number —
they can only be checked for *direction* (an instruct model should clear its base
model's 8-shot GSM8K 93.0 at 0-shot greedy, and it does).