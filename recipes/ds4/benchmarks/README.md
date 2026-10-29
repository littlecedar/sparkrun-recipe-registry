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

Endpoint: `http://<head-node>:4000/v1` (OpenAI-compatible;
only `/v1/chat/completions` is routed — `/v1/completions` returns HTTP 400).

## Contents

- [Headline](#headline)
  - [Mid-tier result — thinking off, greedy (temperature=0)](#mid-tier-result--thinking-off-greedy-temperature0)
  - [Sizing the token budget (truncation is not a wrong answer)](#sizing-the-token-budget-truncation-is-not-a-wrong-answer)
  - [Secondary — thinking on (diagnostic only)](#secondary--thinking-on-diagnostic-only)
  - [Secondary — latency (same GSM8K run, thinking off)](#secondary--latency-same-gsm8k-run-thinking-off)
- [Hard benchmark battery](#hard-benchmark-battery)
  - [Measured result (thinking off, greedy)](#measured-result-thinking-off-greedy)
  - [Secondary / diagnostic arms](#secondary--diagnostic-arms)
- [Honest reading — what this does and does not show](#honest-reading--what-this-does-and-does-not-show)
- [Provenance](#provenance)
- [Reproduce](#reproduce)
- [Files](#files)
  - [A note on the scorer (why rescore.py exists)](#a-note-on-the-scorer-why-rescorepy-exists)

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

`enable_thinking` is not universal. The IFM K2-Horizon chat templates key
reasoning on `reasoning_effort` (`high|medium|low`, default `high`) and contain
no `enable_thinking` at all — there, `--thinking off` is silently ignored, and a
reply always opens a reasoning block. `run_benchmarks.py` therefore carries a
second, **additive** knob: `--reasoning-effort {default,high,medium,low}`
(`default` sends no such key). It merges `reasoning_effort` into the same
`chat_template_kwargs` *alongside* whatever `--thinking` set; it never replaces
it, because the two models compared here genuinely honour `enable_thinking` and
that control is what makes the comparison a like-for-like one.

The per-benchmark row for every suite in this directory — scores, Δ, discordant
count split, McNemar p and verdict — is tabulated once, in
[`results/RESULTS.md`](results/RESULTS.md).

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

### Sizing the token budget (truncation is not a wrong answer)

A template that always opens a reasoning block spends its first tokens thinking,
so a cap too small to reach the visible answer records a truncation as a miss.
The base caps — **house 1024, gsm8k 2048, arc 1024** — are sized for that, and
`--max-tokens-scale <float>` (default `1.0`) multiplies each of them so a caller
can size budgets without editing code. Every summary JSON records the
`reasoning_effort` used, the `finish_reasons` histogram, and an `empty_replies`
count, which is how a truncation is told apart from a real answer; each
`_raw/*.jsonl` record carries its effort too, so a resume is self-describing.

### Secondary — thinking on (diagnostic only)

Forced `enable_thinking=true`, GSM8K n=60. This is *not* the headline config; it
exists to show the default-mode divergence and its cost. Scores are in
[`results/RESULTS.md`](results/RESULTS.md) (secondary arms, `on.thinkON`); the
columns here are the diagnostics the primary tables do not carry.

| model | empty replies | mean reasoning tokens | mean latency |
|:--|--:|--:|--:|
| `deepseek` | 6 | n/a (`reasoning_tokens` not reported) | 4.4 s |
| `deepseek-turbo` | 5 | 184 | 3.2 s |

Both models score *lower* with thinking on than off on this tier, and both lose
items to the same failure: multi-step prompts that think past the GSM8K cap
(700 at the time; 2048 now) and return an **empty `content`**
(`finish_reason: length`). The scale is
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

| Benchmark | Harness | Grader | n run |
|:--|:--|:--|--:|
| HLE (text-only) | `bench_reason.py` | MCQ letter / math_verify / strict text | 200 of 2370 |
| GPQA Diamond | `bench_reason.py` | letter | 198 (all) |
| MMLU-Pro | `bench_reason.py` | 10-way letter | 400 of 12032 |
| MATH-500 | `bench_reason.py` | `math_verify` (symbolic), numeric, text | 200 of 500 |
| AIME 2022-24 | `bench_reason.py` | integer | 90 (all) |
| HumanEval | `bench_code.py` | **code execution** (dataset tests) | 164 (all) |
| MBPP (sanitized) | `bench_code.py` | **code execution** (dataset asserts) | 257 (all) |

The published score for each of these benchmarks is tabulated once — with source
URL, shots, date, and confidence label — in
[`REFERENCE-SCORES.md`](REFERENCE-SCORES.md); [`results/RESULTS.md`](results/RESULTS.md)
prints it in a column beside each measured row. Those reference scores are the
*unquantized* model's, a sanity frame, not an apples-to-apples comparison
(different shot counts, harnesses, and `reasoning_effort`). The measured numbers
for both models are in [`results/RESULTS.md`](results/RESULTS.md).

### Measured result (thinking off, greedy)

The full ten-row table — scores, Δ, discordant counts, exact McNemar p, verdict,
and the published reference beside each row — is tabulated once, in
[`results/RESULTS.md`](results/RESULTS.md).

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
  python3 run_benchmarks.py --base-url http://<head-node>:4000 \
      --model "$m" --bench all --thinking off --limit 200 --seed 1234
done

# 3. hard battery (requires the math venv for symbolic grading) -- or just
#    `./run_overnight.sh <model> <logfile>` for the whole thing in order
for m in deepseek deepseek-turbo; do
  .venv-qa/bin/python bench_reason.py --base-url http://<head-node>:4000 \
      --model "$m" --bench all --thinking off --limit 200
  python3 bench_code.py --base-url http://<head-node>:4000 \
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
| `results/<model>.<bench>.<thinking>[.<effort>][.<tag>].json` | per-model scored results (what the READMEs quote); `<effort>` appears only when `--reasoning-effort` is not `default`. The model id is slugged (`/`→`_`) for the **filename only**; the raw id is kept in the payload and on the wire |
| `results/RESULTS.md`, `results/summary_all.json` | the full cross-model comparison with p-values — **the single home of this directory's measured score tables** |
| `results/summary.json` | machine-readable mid-tier comparison (reply-level divergence counts) behind `RESULTS.md` |
| `results/SUMMARY.md` | tombstone — its tables were merged into `RESULTS.md` on 2026-10-29; `compare_results.py` still emits this path, so a re-run of it restores the duplicate tables |

### A note on the scorer (why `rescore.py` exists)

The first GSM8K pass graded the value after `####` by **string match**, so a model
answering `#### 8.00` was scored wrong against a gold of `8`. That is a harness
artifact, not a quality difference — it wrongly penalised `deepseek-turbo` on 4
items and `deepseek` on 6. `score_gsm8k()` now compares **numerically**, and
`rescore.py` re-scored the stored replies to regenerate the tables above. Every
score in this directory is produced by the current scorer; the raw replies are
kept so any future scorer change is replayable the same way.