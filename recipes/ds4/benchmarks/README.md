# `ds4` quality benchmarks — `deepseek` vs `deepseek-turbo`

Held-out quality comparison of the two DeepSeek-V4.1-Flash chat models exposed by
the Little Cedar cluster gateway. The question this answers is narrow and
specific: **does the EXL3 2.9 bpw quantisation behind `deepseek-turbo` cost any
quality on tasks we care about, relative to the baseline `deepseek`?**

| | `deepseek` | `deepseek-turbo` |
|:--|:--|:--|
| Served model id | `deepseek-ai/DeepSeek-V4.1-Flash` | `Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw` |
| Weights | official (MXFP4/F8) | EXL3 **2.90 bpw**, codebook `mul1` |
| Engine | SGLang | TensorFold (DSpark spec decode) |
| Gateway alias | `deepseek` | `deepseek-turbo` |
| Default thinking | **off** | **on** |

Endpoint: `http://spark-head.internal.littlecedar.net:4000/v1` (OpenAI-compatible;
only `/v1/chat/completions` is routed — `/v1/completions` returns HTTP 400).

## Headline

> Across **11 benchmarks and ~1,900 paired items** — GSM8K, ARC, HLE, GPQA
> Diamond, MMLU-Pro, MATH-500, AIME, HumanEval, MBPP, and the 37-task house
> battery — honest greedy decoding, the two models are **statistically
> indistinguishable in quality**: every benchmark is a tie under a paired
> McNemar test. The quantisation costs nothing measurable. Gaps that exist
> (≤4.4 pp) change sign from benchmark to benchmark, which is what noise looks
> like — see *Honest reading* below.

### Mid-tier result — thinking off, greedy (`temperature=0`)

Both models are forced to the **same** effective config with
`chat_template_kwargs={"enable_thinking": false}`. This is load-bearing: the two
deployments *default* to opposite thinking modes (baseline off, turbo on), so a
naive comparison measures the configuration, not the weights.

| Benchmark | `deepseek` | `deepseek-turbo` | Δ | items |
|:--|--:|--:|--:|--:|
| house battery (easy tier) | 19/19 | 19/19 | 0 | 19 |
| house battery (hard tier) | 17/18 | 17/18 | 0 | 18 |
| **house battery (total)** | **36/37 = 97.3 %** | **36/37 = 97.3 %** | **+0.0 pp** | 37 |
| **GSM8K** (0-shot) | **194/200 = 97.0 %** | **197/200 = 98.5 %** | **+1.5 pp** | 200 |
| **ARC-Challenge** (0-shot) | **186/200 = 93.0 %** | **186/200 = 93.0 %** | **+0.0 pp** | 200 |

- **House battery** = [`tools/quality-battery.py`](../../../tools/quality-battery.py),
  imported verbatim (same tasks, same scorer as earlier `ds4` runs). Both models
  fail the *same single* hard item (`hard-rev`, transposing "sparkrun") and pass
  everything else — including the exact same 19/19 easy / 17/18 hard split as the
  retired EXL3-3.5bpw checkpoint recorded in `.scratch/ds4/qh_run{2,3}.txt`.
- **GSM8K** = official `openai/gsm8k` test split, 200 items (fixed `--seed 1234`),
  0-shot. Comparable to the model card's **8-shot 93.0 EM** for the *unquantized*
  model (ours is 0-shot, so not directly comparable — see *Honest reading*).
- **ARC-Challenge** = official `allenai/ai2_arc` `ARC-Challenge`/`test`, 200 of
  1172 items (same seed), 0-shot, letter-match.

### Secondary — thinking on (diagnostic only)

Forced `enable_thinking=true`, GSM8K n=60. This is *not* the headline config; it
exists to show the default-mode divergence and its cost.

| model | score | empty replies | mean reasoning tokens | mean latency |
|:--|--:|--:|--:|--:|
| `deepseek` | 54/60 = 90.0 % | 6 | n/a (`reasoning_tokens` not reported) | 4.4 s |
| `deepseek-turbo` | 55/60 = 91.7 % | 5 | 184 | 3.2 s |

Both models score *lower* with thinking on than off on this tier, and both lose
items to the same failure: multi-step prompts that think past the 700-token
budget and return an **empty `content`** (`finish_reason: length`). The scale is
unchanged (Δ ≈ +1.7 pp for turbo). Operationally the important fact is that
`deepseek-turbo` burns reasoning tokens on **trivial** prompts — a bare
"reply with just the number" can spend the whole budget thinking
(observed: `reasoning_tokens=400` on a one-line request). Callers who want the
terse baseline behaviour must pass `enable_thinking=false`.

### Secondary — latency (same GSM8K run, thinking off)

Not a throughput benchmark (that is the recipe's performance lane) but a useful
side-signal: `deepseek-turbo` returned each GSM8K item ~28 % faster.

| model | mean wall / request | mean completion tokens | wall tok/s |
|:--|--:|--:|--:|
| `deepseek` | 2.67 s | 171 | 64.0 |
| `deepseek-turbo` | 1.93 s | 162 | 84.3 |

## Hard benchmark battery

The three mid-tier suites above cannot separate two models that are both strong.
The hard tier below is built to: **HLE**, **GPQA Diamond**, **MMLU-Pro**,
**MATH-500**, **AIME 2022-24**, **HumanEval**, and **MBPP**. It is the same
quant-vs-official question at the difficulty where a 2.9 bpw quant would show a
deficit if it had one.

| Benchmark | Harness | Grader | n run | published (unquantised) |
|:--|:--|:--|--:|:--|
| HLE (text-only) | `bench_reason.py` | MCQ letter / math_verify / strict text | 200 of 2370 | 36.8 (39.1 text-only) |
| GPQA Diamond | `bench_reason.py` | letter | 198 (all) | 90.9 |
| MMLU-Pro | `bench_reason.py` | 10-way letter | 400 of 12032 | 74.1 (base, 5-shot) |
| MATH-500 | `bench_reason.py` | `math_verify` (symbolic), numeric, text | 200 of 500 | not published (MATH 61.1 base) |
| AIME 2022-24 | `bench_reason.py` | integer | 90 (all) | AIME 2026 100 (report) |
| HumanEval | `bench_code.py` | **code execution** (dataset tests) | 164 (all) | 79.4 (base, 0-shot) |
| MBPP (sanitized) | `bench_code.py` | **code execution** (dataset asserts) | 257 (all) | not published |

Reference scores are the *unquantised* model's, gathered with sources and
confidence labels in [`REFERENCE-SCORES.md`](REFERENCE-SCORES.md); they are a
sanity frame, not an apples-to-apples comparison (different shot counts,
harnesses, and `reasoning_effort`). The measured numbers for both models are in
[`results/RESULTS.md`](results/RESULTS.md).

### Measured result (thinking off, greedy)

| Benchmark | `deepseek` | `deepseek-turbo` | Δ | discordant (ds / turbo) | McNemar p | verdict |
|:--|--:|--:|--:|:--:|--:|:--|
| House battery (37) | 36/37 = 97.3% | 36/37 = 97.3% | +0.0 | 0 / 0 | 1.00 | **tie** |
| GSM8K (200) | 194/200 = 97.0% | 197/200 = 98.5% | +1.5 | 0 / 3 | 0.25 | **tie** |
| ARC-Challenge (200) | 186/200 = 93.0% | 186/200 = 93.0% | +0.0 | 1 / 1 | 1.00 | **tie** |
| HLE text-only (200) | 13/200 = 6.5% | 13/200 = 6.5% | +0.0 | 7 / 7 | 1.00 | **tie** |
| GPQA Diamond (198) | 142/198 = 71.7% | 138/198 = 69.7% | −2.0 | 17 / 13 | 0.58 | **tie** |
| MMLU-Pro (400) | 328/400 = 82.0% | 321/400 = 80.2% | −1.8 | 13 / 6 | 0.17 | **tie** |
| MATH-500 (200) | 191/200 = 95.5% | 188/200 = 94.0% | −1.5 | 5 / 2 | 0.45 | **tie** |
| AIME 2022-24 (90) | 51/90 = 56.7% | 55/90 = 61.1% | +4.4 | 6 / 10 | 0.45 | **tie** |
| HumanEval (164, exec) | 159/164 = 97.0% | 157/164 = 95.7% | −1.2 | 3 / 1 | 0.62 | **tie** |
| MBPP (257, exec) | 200/257 = 77.8% | 198/257 = 77.0% | −0.8 | 3 / 1 | 0.62 | **tie** |

**Verdict: no benchmark separates the two at any conventional significance
level.** The largest raw gap is +4.4 pp (AIME, favouring the quantised lane),
whose discordant split is 6 vs 10 — a coin flip (p = 0.45). Six benchmarks lean
to the official weights and two to the quantised weights, i.e. the sign of the
tiny gaps is *not even consistent in direction*, which is what noise looks like.
The `discordant` column is the honest read: on HLE the two models each win exactly
7 of the 14 items they disagree on; on GSM8K **turbo wins 3 and loses 0**; on ARC
it is 1–1. Read the whole table as **a tie across the board**.

### Secondary / diagnostic arms

- **Thinking ON is worse for MCQ, symmetrically.** On GPQA, both models collapse
  to ~38–39 % with thinking on vs ~70 % with it off (`deepseek` 39.0 % on / 71.7 %
  off; `deepseek-turbo` 38.0 % on / 69.7 % off, n=100 each) — reasoning mode
  actively hurts this multiple-choice task, for both. On MATH-500, thinking on is
  a wash (`deepseek` 97.5 % on vs 95.5 % off; turbo 92.5 % on vs 94.0 % off).
- **MBPP name-anchoring matters.** With MBPP's native prose prompt (function name
  never stated), both models score **~9–10 %** — a floor caused by the harness,
  not the weights. Anchoring the required `def name(...)` from the reference
  solution lifts both to **~77 %**. The `off.nameguess` arm is retained in
  `results/` to document the difference.
- **House battery is stable.** A full repeat (both models) flipped **zero** items.

**Primary config is thinking OFF, on both models.** This is not a shortcut — it
is forced by the endpoint. On HLE-class prompts, with thinking ON, *both* models
stream hidden reasoning for the entire `max_tokens` budget and return
`finish_reason: length` with **empty visible content** (measured: `deepseek`
16 000 tokens / 307 s / empty `content`; `deepseek-turbo` 16 000 / 185 s /
empty). Thinking off answers the same items in seconds. So the only config that
actually produces graded answers on the hard tier is thinking off, and it is the
only fair same-config comparison. A secondary thinking-ON arm is run for GPQA and
a MATH-500 slice (both terminate quickly even with reasoning on).

**Two honest caveats specific to this tier:**

- **HLE is near-floor for 0-shot greedy chat on a local model** (published
  frontier HLE is ~37 %, and that is with tool use and max reasoning effort). A
  low absolute HLE score here is *expected*; the signal is the **gap between the
  two models**, not the level.
- **MBPP under-specifies the function name** in its prose prompts, so a model that
  writes a correct function under a different name fails the dataset's asserts.
  That is faithful to MBPP pass@1 but depresses both scores; read MBPP as a
  relative signal only.

## Honest reading — what this does and does not show

**Does show (VERIFIED, direct measurement):**

- Across **11 benchmarks and ~1,900 paired items** — house, GSM8K, ARC, HLE,
  GPQA, MMLU-Pro, MATH-500, AIME, HumanEval, MBPP (plus repeats) — **no benchmark
  separates the two models at p < 0.05** (paired McNemar). The quantisation costs
  nothing measurable.
- The largest gap is +4.4 pp on AIME (turbo ahead), with 6 vs 10 discordant items
  (p = 0.45); the *sign* of the small gaps is inconsistent across benchmarks
  (6 lean official, 2 lean quantised, 3 exact ties), which is the signature of
  noise rather than a real offset.
- Several benchmarks are **exactly tied or near-so**: house 36/37 both, ARC
  186/200 both, HLE 13/200 both (with a perfectly symmetric 7–7 discordant
  split), HumanEval 159 vs 157, MBPP 200 vs 198.
- The house battery reproduces **bit-for-bit across a repeat** (zero items
  flipped) — the measurement is stable run to run.
- Reasoning mode does not rescue the hard tier (thinking-ON HLE returns empty
  `content` for both models), and on GPQA it actively *hurts* the quantised lane
  (38 % on vs 70 % off).

**Does not show / caveats:**

- **Small-n noise dominates.** The biggest gaps (AIME n=90, GPQA n=198) are a
  handful of items; the paired test says those are coin flips. Read every row as
  *"a tie within noise"*, not as a ranking.
- **Hard-tier absolute levels are config-limited, not model-limited.** Our HLE
  (6.5 %) and GPQA (70 %) sit well below the published instruct-model numbers
  (HLE ~37 %, GPQA 90.9 %) because we run **0-shot, greedy, thinking off, no
  tools**, and at a 2,000–2,500-token cap on prompts where reasoning matters. This
  depresses both models equally, so it does not affect the *comparison* — but do
  not quote our HLE absolute as "the model's HLE score".
- **The comparison is unquantized-vs-quantized *as deployed*, not a controlled A/B
  on one engine.** The baseline runs SGLang; turbo runs TensorFold with DSpark
  speculative decoding. DSpark and lower-bpw weights are confounded. A difference
  in either direction could be spec-decode, not bits — which is exactly why the
  clean result (no difference) is the useful one.
- **No `lm-eval-harness` numbers.** The gateway exposes chat completions only, so
  loglikelihood-based multiple-choice (HellaSwag, MMLU) is not computable; every
  number here is *generative* and letter/text/number-matched. That is a deliberate
  scope choice, not an oversight.
- **Third-party published numbers are a sanity frame only.** See
  [`REFERENCE-SCORES.md`](REFERENCE-SCORES.md): the model card's GPQA 90.9, HLE
  36.8, HumanEval 79.4, etc. are the *unquantised instruct* model under DeepSeek's
  own harness at max reasoning effort — a different config from ours. The EXL3
  2.9 bpw card publishes **no** evals of its own, which is the gap this directory
  fills.
- **Task-family scope is now broad but not universal.** Covered: grade-school and
  competition math (GSM8K, MATH-500, AIME), science MCQ (ARC, GPQA), broad
  knowledge (MMLU-Pro), code execution (HumanEval, MBPP), frontier reasoning
  (HLE). **Not** covered: multi-turn agentic/terminal tasks (Terminal-Bench,
  SWE-bench Verified — these need a sandboxed tool loop the chat endpoint cannot
  provide), long-context retrieval at scale, and multimodal (the EXL3 checkpoint
  keeps the vision tower, but the gateway path was not exercised).

## Provenance

| Number | Source | Confidence |
|:--|:--|:--|
| All scores in this directory | measured here, this run, saved under `results/` | VERIFIED |
| Model card reference scores | [deepseek-ai/DeepSeek-V4.1-Flash](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash) | VERIFIED (as published) |
| EXL3 2.9 bpw config (bpw, codebook, DSpark) | [Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw](https://huggingface.co/Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw) | VERIFIED (as published) |
| "`deepseek` = official FP8 / `deepseek-turbo` = EXL3" | gateway `/v1/models` response `model` field, echoed per request | VERIFIED |

## Reproduce

```bash
cd recipes/ds4/benchmarks

# 1. stage the datasets once (stdlib; the `datasets` venv path covers ratelimits)
python3 fetch_data.py                      # GSM8K + ARC
python3 fetch_hard.py                      # HLE, GPQA-D, MMLU-Pro, MATH-500, AIME
                                           #   (or: .venv-qa/bin/python fetch_hard_hf.py)

# 2. mid-tier suites, both models, thinking off, matching the first tables
for m in deepseek deepseek-turbo; do
  python3 run_benchmarks.py --base-url http://spark-head.internal.littlecedar.net:4000 \
      --model "$m" --bench all --thinking off --limit 200 --seed 1234
done

# 3. hard battery (requires the math venv for symbolic grading) -- or just
#    `./run_overnight.sh <model> <logfile>` for the whole thing in order
for m in deepseek deepseek-turbo; do
  .venv-qa/bin/python bench_reason.py --base-url http://spark-head.internal.littlecedar.net:4000 \
      --model "$m" --bench all --thinking off --limit 200
  python3 bench_code.py --base-url http://spark-head.internal.littlecedar.net:4000 \
      --model "$m" --bench both --thinking off --seed 1234
done

# 4. aggregate the whole campaign into results/RESULTS.md + summary_all.json
python3 compare_all.py
```

Runs are **resumable**: every item is appended to `results/_raw/<model>.<bench>.<thinking>.jsonl`
as it completes, so an interrupted run continues where it stopped. Latency
numbers reflect a single sequential driver, not concurrent load.

## Files

| File | Role |
|:--|:--|
| `fetch_data.py` | stage GSM8K + ARC-Challenge from their upstream sources (stdlib, idempotent) |
| `fetch_hard.py` / `fetch_hard_hf.py` | stage HLE, GPQA-D, MMLU-Pro, MATH-500, AIME (datasets-server vs `datasets` library) |
| `run_benchmarks.py` | mid-tier runner; imports the house battery verbatim for the house tier |
| `bench_reason.py` | hard-tier reasoning runner (HLE/GPQA/MMLU-Pro/MATH-500/AIME) with symbolic grading |
| `bench_code.py` | code-execution runner (HumanEval/MBPP), sandboxed subprocess |
| `rescore.py` | re-score stored replies after a scorer change (pure replay, no endpoint) |
| `compare_results.py` | aggregate the three mid-tier benches → table + reply-diff counts |
| `compare_all.py` | aggregate **every** bench → `results/RESULTS.md` with paired McNemar tests |
| `run_overnight.sh` | one-model, all-benchmarks driver (run two in parallel) |
| `REFERENCE-SCORES.md` | published scores for the unquantised model, with sources + confidence |
| `.venv-qa/` | venv with `sympy`/`math_verify`/`datasets` for symbolic grading and parquet staging |
| `data/`, `data_code/` | staged datasets (regenerable) |
| `results/_raw/` | append-only per-item records + run logs (the audit trail) |
| `results/<model>.<bench>.<thinking>.json` | per-model scored results (what the READMEs quote) |
| `results/RESULTS.md`, `results/summary_all.json` | the full cross-model comparison with p-values |
| `results/SUMMARY.md`, `results/summary.json` | the earlier mid-tier-only comparison |

### A note on the scorer (why `rescore.py` exists)

The first GSM8K pass graded the value after `####` by **string match**, so a model
answering `#### 8.00` was scored wrong against a gold of `8`. That is a harness
artifact, not a quality difference — it wrongly penalised `deepseek-turbo` on 4
items and `deepseek` on 6. `score_gsm8k()` now compares **numerically**, and
`rescore.py` re-scored the stored replies to regenerate the tables above. Every
score in this directory is produced by the current scorer; the raw replies are
kept so any future scorer change is replayable the same way.