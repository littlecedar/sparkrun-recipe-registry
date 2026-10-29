# How the Numbers in the Main README Are Derived

This document explains how the performance figures in the main `README.md` are measured. The tables there are not marketing claims or theoretical peaks. They are empirical results from specific runs on specific hardware, and each number has a traceable receipt behind it. This document describes the instruments, the measurement rules, and the derivation of every column so a reader can understand what a cell means without opening the raw JSON.

The intended audience is scientific: a reader comfortable with high-school physics or lab practice and basic Python, but not necessarily an expert in GPU inference engines. Where a term has a precise technical meaning, it is defined on first use.

## Contents

- [1. The Philosophy: Measured, Not Modelled](#1-the-philosophy-measured-not-modelled)
- [2. The Measurement Cell](#2-the-measurement-cell)
  - [Reading the receipt, not the table](#reading-the-receipt-not-the-table)
- [3. The Concurrency Ladder: C1, C2, C5, C10](#3-the-concurrency-ladder-c1-c2-c5-c10)
  - [Flavors of cell in the tables](#flavors-of-cell-in-the-tables)
- [4. Core Metric Derivations](#4-core-metric-derivations)
  - [Throughput in tokens per second (t/s)](#throughput-in-tokens-per-second-ts)
  - [Size in gigabytes (GB)](#size-in-gigabytes-gb)
  - [Memory utilization (Mem%)](#memory-utilization-mem)
  - [Tensor parallelism (TP)](#tensor-parallelism-tp)
  - [Time to first token (TTFT) and prefill speed](#time-to-first-token-ttft-and-prefill-speed)
- [5. Benchmark Profiles and Instruments](#5-benchmark-profiles-and-instruments)
  - [5.1 The standard suite: tool-eval-bench](#51-the-standard-suite-tool-eval-bench)
  - [5.2 The house battery: quality-battery.py](#52-the-house-battery-quality-batterypy)
  - [5.3 The long-context probe: needle-haystack.py](#53-the-long-context-probe-needle-haystackpy)
  - [5.4 Tool calling and decision lanes: bfcl-eval.py and decision-ladder.py](#54-tool-calling-and-decision-lanes-bfcl-evalpy-and-decision-ladderpy)
  - [5.5 Embedding and reranking: pooling-bench.py](#55-embedding-and-reranking-pooling-benchpy)
  - [5.6 Media lane: the arm's own task rate](#56-media-lane-the-arms-own-task-rate)
  - [5.7 The SOP pass: eval-suite.py](#57-the-sop-pass-eval-suitepy)
  - [5.8 The llama-benchy profiles](#58-the-llama-benchy-profiles)
  - [5.9 The "house" metrics in lane READMEs](#59-the-house-metrics-in-lane-readmes)
- [6. Provenance and Validation](#6-provenance-and-validation)
  - [The two-record trap, in full](#the-two-record-trap-in-full)
  - [Prometheus gauges](#prometheus-gauges)
- [7. What Each Lane's Columns Mean](#7-what-each-lanes-columns-mean)
- [8. Reading a Footnote](#8-reading-a-footnote)
- [9. Validation Checklist Before Quoting a Number](#9-validation-checklist-before-quoting-a-number)

## 1. The Philosophy: Measured, Not Modelled

Every cell in the README tables represents an actual boot and an actual request sequence. A number is published only after the motivating gate closes on real hardware — "the completion gate" is "is there a boot/run behind it?", not "does the reasoning hold?" A device-free probe is necessary but not sufficient. If no boot or run exists, the cell stays `—`.

The registry's measurement discipline is captured in shipped form in [`../benchmarking/README.md`](../benchmarking/README.md) and the long-form evidence in [`AGENTS.md`](AGENTS.md) §"Measurement discipline before shipping a default change". The rules that matter most:

- **One boot cannot rank arms.** The GB10 inter-boot scatter is 7–25 % (3–25 % across cells). A `+12.6 %` effect that looked real at `runs=3` collapsed at `runs=7`.
- **A noise floor belongs to a (configuration, cell) pair**, never to "the boot", and it must not be inferred from a comparison you already decided is null.
- **Prefer same-boot or interleaved controls** over more runs. A control in the same container removes the 7–25 % term that repetition cannot touch.
- **`runs` is chosen from the effect size you need to detect**, not from a blanket minimum. But no profile with `runs < 5` supports a cross-boot comparison.
- **Pass `--fresh` for any intended new measurement**, and give every citable run an explicit `--output` name. The derived filename is overwritten by the next run; `runs/` is scratch and gets reaped. The `--output` file is the durable artifact.

## 2. The Measurement Cell

The fundamental unit is the **cell**. A cell is one configuration evaluated at one depth and one concurrency for a stated number of runs. "Configuration" means the model, the engine (vLLM, SGLang, llama.cpp), the parallelization (tensor parallelism), and the memory settings. "Depth" is the input context length in tokens. "Concurrency" is the number of simultaneous requests.

Each cell emits **two records**, both carrying a `tg_throughput` field: a **context-prefill record** (`is_context_prefill_phase: true`) and a **decode record**. The prefill phase processes the prompt; the decode phase generates the output. Grouping records by concurrency alone doubles the cell count and fakes bimodal boots. Every table in the README reports the **decode row** unless a footnote says otherwise. The prefill row's fields are very different: in one run the prefill `pp_throughput` was 2135.9 while the printed decode row read 988.5, and the prefill `ttfr` was 37.6 s versus 12.2 s printed. Reading the wrong row quotes a time-to-first-token three times too low, and no error is raised.

### Reading the receipt, not the table

The printed `sparkrun` progress table has no column header at all, and it prints only the decode-phase row. Never quote from that table. Read the JSON in `runs/NNN_d<depth>_c<c>.json` while it exists, or the named `--output` file that carries the same records. The fields that matter:

- `tg_throughput` — aggregate decode throughput across all concurrent streams (see §4).
- `tg_req_throughput` — per-stream decode throughput.
- `pp_throughput` — prefill-phase throughput window.
- `ttfr` — time to first token, as measured by the harness.
- `is_context_prefill_phase` — selects the row.

## 3. The Concurrency Ladder: C1, C2, C5, C10

The columns **C1**, **C2**, **C5**, and **C10** are the throughput measured at 1, 2, 5, and 10 simultaneous requests. They come from the profile `benchmarking/concurrency-ladder.yaml`: depth 0 (no prefix), prompt 2048 tokens, generated 128 tokens, concurrency 1/2/5/10, 5 runs per cell. The README's ladder cells are named for that profile. It is run `--skip-run` against the boot the quality suite used, so speed and quality share one measurement window.

**C1 is not the quiet regime and not the whole story.** It is completion-length sensitive: a varied short-answer prompt dilutes the decode rate. The worst within-cell coefficients of variation in the archive (11–15 %) are at depth 0, c = 1. For steady-state throughput, quote the C4/C8/C16 columns where they exist. A `t/s` quoted at `tg=32` is not comparable to one at `tg=128`: prefill amortises over four times fewer tokens and the tail is early chain-of-thought, not steady state.

**Aggregate, not per-stream.** A C10 cell reading 160.9 t/s means the system generated 160.9 tokens per second across all ten streams combined. The per-stream rate is roughly one-tenth of that. The published columns are aggregates. The per-stream figure is in `tg_req_throughput`. This distinction is the single most common misreading of the tables.

**Concurrency does not clamp the server.** Offering c = 40 to a server whose pool grants 20 produces 20 running requests plus a queue. Capacity is judged from `#running-req` and `full token usage` in the server log, never from the profile's own concurrency field.

### Flavors of cell in the tables

A reader comparing two cells needs to know which flavor each one is. The footnote is the only reliable label; the cell's value alone does not tell you.

- **Ladder cell.** A point on the `concurrency-ladder.yaml` run: c 1/2/5/10, d0, pp 2048, tg 128, 5 runs per cell. This is the default flavor for a C1–C10 column. Its uncertainty is the sample spread within one boot.
- **Single-point cell.** One sample from an earlier triage or concurrency sweep, quoted because the row predates the ladder or the full ladder was never run. A row whose C1 reads 33.3 while C2/C5/C10 read 49.4/84.6/92.9 is a mixed-boot row: the C1 came from a single-point receipt and the rest from a later ladder. The footnote names both.
- **Cross-boot cell.** The number comes from a boot other than the row's current shipped configuration, or from a comparison across boots. Its uncertainty includes the 7–25 % inter-boot term, not just the within-boot sample spread. A "first boot" label marks the row's first measured sample, not a replicated ladder.
- **Quality cell.** Accuracy or score columns from the suite instruments (`tool-eval-bench`, `quality-battery.py`, `bfcl-eval.py`, `needle-haystack.py`), measured on a stated boot. These are not throughput numbers and are not comparable to a t/s cell.
- **Unavailable cell (`—`).** "Not measured" or "not reported", never zero and never "memory unknown". A depth-gated long-context arm keeps its performance cells `—` by design; a llama.cpp arm with no util value reports `—`; a row measured before an instrument existed keeps `—` until it is re-run.

## 4. Core Metric Derivations

### Throughput in tokens per second (t/s)

The decode throughput is derived from the engine's own token generation rate during the decode phase, aggregated across all concurrent streams. It is a window measurement: the count of completion tokens divided by the wall-clock time of the decode phase. The aggregate `tg_` columns are windows opening at submission, so they charge scheduler queueing to the phase. For any "this phase got slower" claim, use the per-request column (`tg_req_throughput`).

### Size in gigabytes (GB)

The model checkpoint's raw weight size on disk. For a quantized checkpoint, this is the size of the quantized weights, not the theoretical full-precision size. A `23.5GB + 1.1GB draft` cell means the main model occupies 23.5 GB and the speculative-decoding draft model another 1.1 GB. `Size` is a property of the artifact, not of the boot.

### Memory utilization (Mem%)

This column has two distinct meanings and the footnote says which applies:

1. **Engine's own startup estimate.** The fraction of total device memory the engine reserved at boot. For vLLM this is `--gpu-memory-utilization`; for SGLang it is `mem_fraction_static`. When a recipe renders no util flag, the footnote states the engine default that actually ran. A `*` marks "no recipe util": the recipe rendered no util fraction, so the figure is the engine's own boot-log figure, and the lane's footnote names which one — an allocator ceiling in the DeepSeek V4 lane, the engine's startup estimate in the Qwen 3x lane, a documented upper bound in Cybersec.
2. **Allocator ceiling from the boot log.** For llama.cpp, the engine sizes its own pool from `--ctx-size` and `--parallel`, so no util fraction is configured. Where the boot log reports an allocator ceiling the footnote carries it; otherwise the cell is `—`, because the engine reported no util value. A `—` means "not reported", not "memory unknown". The same applies to a CPU-only arm: there is no device cap to report.

Mem% is never computed from a formula. It is read from the boot log or the serve log. A computed estimate is not a measurement.

### Tensor parallelism (TP)

The number of GPUs across which the model's layers are split. TP = 1 means the model runs on one device. TP = 4 means each layer is partitioned across four devices. TP is a **configuration setting, not a performance metric**, but it directly determines whether the model fits in memory and how fast it can run. A TP = 4 recipe reads a higher aggregate throughput than a TP = 1 recipe of the same model, but the comparison is not a knob comparison: different TP changes the executed configuration, so the two are separate arms. A cross-recipe throughput comparison is not a knob comparison, and the tables label it as such.

### Time to first token (TTFT) and prefill speed

The prefill phase processes the input prompt before generation begins. Its speed is not the same as the decode speed. The field `pp_req_throughput` is **prompt-size ÷ TTFT**, not a prefill speed — verified numerically: `pp_req_throughput × e2e_ttft == prompt_size`. It measures how many prompt tokens arrived per second of waiting, including queueing. The aggregate prefill columns are windows opening at submission, so they charge scheduler queueing to the phase. Any "prefill got slower" claim must use the per-request columns.

A deep prefill can look like a wedge: a ~799K-token prompt at ~600 t/s takes 20–23 minutes, `/health` returns 200 while generation times out, and killing the client does not cancel the in-flight prefill. The discipline distinguishes busy from wedged by worker CPU ticks (`/proc/<pid>/stat`), serve-log progress, and load average — not by sending a second request. A deep prefill is a busy prefill, not a dead one.

## 5. Benchmark Profiles and Instruments

The registry uses three families of instruments, each with a defined shape. A "profile" is a named set of arguments (depth, concurrency, run count, prompt lengths) passed to the instrument. Profiles are curated in [`../benchmarking/`](../benchmarking/) and the registry index [`../benchmarking/README.md`](../benchmarking/README.md).

### 5.1 The standard suite: `tool-eval-bench`

The registry's shared external benchmark. The profile `benchmarking/standard-suite.yaml` runs the core 15 scenarios, greedy sampling (temperature 0.0), 8 turns, sequential. Every arm's "standard suite" number is taken on this shape so scores compare across arms. `-b short=false` (extended + agentic, 69 scenarios) or `-b hardmode=true` (Category P) is a **different shape**: label it, never pool it. The decision lane's published scores use `tool-eval-bench` **v2.8.0**, while the profile pins v2.6.0; record the version beside any cross-lane comparison.

The instrument writes a state DB and one report per run relative to its CWD. Run it from a receipt directory, not from the repository root.

### 5.2 The house battery: `quality-battery.py`

`sparkrun`'s benchmarking path measures speed only. A quantized checkpoint can lose quality without losing a single token/s. `tools/quality-battery.py` is the in-house exact-match battery for that question. It has two tiers:

- **`easy` (19 tasks)** — arithmetic, word problems, simple logic, factual recall, formatting, code basics, one needle. It **saturates**: a competent model scores 100 %. Its number **cannot rank quality**; do not quote it as one.
- **`hard` (18 tasks)** — multi-step arithmetic with a required intermediate, reasoning probes. This tier discriminates.

The budget matters. House runs take `--max-tokens 4096`. A thinking arm at 1024 can spend the whole allowance reasoning and return a truncated answer (`finish_reason: length`). That is a **budget miss, not a capability miss**: re-ask before recording a failure. Mode is part of the number: `--thinking on|off` sends a different request shape. Thinking-on makes reasoning models emit empty `content` on hard items (a max-token artifact), so the house tier runs thinking-off unless a footnote says otherwise.

### 5.3 The long-context probe: `needle-haystack.py`

`quality-battery.py` plants a single needle in a ~3k-word haystack — a reasoning probe, not a context-window probe. `tools/needle-haystack.py` builds a haystack that reaches a requested context length, plants a needle at each requested depth, asks for it, and reports where the window was actually reached. The default depth grid is every 10 % of the window (10…100), the standard needle-in-a-haystack shape. The JSON artifact carries one record per depth with `prompt_tokens` (the server's own count), `hits`/`of`, `latency_s`, `status`, `attempts`, and **the raw reply to every needle**. The raw replies are the reason the artifact exists: summarised scores hide a wrong answer key. A server that silently truncates, was started with a smaller `max_model_len`, or answers from a short prompt still returns a 200 OK; the needle is how that is caught.

### 5.4 Tool calling and decision lanes: `bfcl-eval.py` and `decision-ladder.py`

The explore lane's brief includes tool-calling models. Three shortlist entries publish **BFCL** scores, so BFCL is the standard suite that lane needs. `tools/bfcl-eval.py` runs the official BFCL v3 questions against an OpenAI-compatible endpoint. A failed cell exits 1. The completion budget matters: the tool's default is 512 tokens; the suite's `--bfcl-max-tokens` default is 4096. An arm measured at 512 is a different shape from one measured at 4096; record the budget beside the score.

The decision lane needs a concurrent harness: the `sparkrun` benchmarking frameworks both drive `/chat/completions`, and the decision servers expose their own routes. `tools/decision-ladder.py` replays the vendored Typed Decisions split at c 1/2/5/10. It reports **req/s** and decisions/s, never t/s. A failed cell exits 1. The Accuracy column comes from the decision suite on the same boot; the req/s columns come from the ladder.

### 5.5 Embedding and reranking: `pooling-bench.py`

The embed and rerank lanes have no chat endpoint at all, so no `llama-benchy` profile can measure them. Pointed at one, `llama-benchy` fails its first task and the run ends as `Error: Benchmark incomplete`. `tools/pooling-bench.py` measures the pooling shapes directly: `/v1/embeddings`, `/v2/embed`, `/v1/score`. The registry drives it through a `framework: pooling-bench` profile (`benchmarking/pooling-ladder-embed.yaml` and `-rerank.yaml`), so a pooling sweep gets the same resumable artifact per cell as any other lane. The unit is **u/s** — units per second, where a unit is one embedding or one rerank score. The ladder runs c 1/2/5/10 with 100 requests, ~256-token inputs, 5 warmups, salted. `dimension_check` is pinned per arm.

### 5.6 Media lane: the arm's own task rate

Media arms — speech synthesis, diarisation, image and video generation, text rewriting — are not chat arms. The t/s ladder does not apply. The rate column is the arm's own task rate: images per second, seconds per clip, real-time factor for audio, wall-clock per 1k output tokens for a rewriter. Every `—` cell is by design, not a missing measurement. The instrument is the arm's own evaluation harness or a dedicated tool (`tools/humanizer-measure.py` for the rewriter, `tools/diarize-score.py` for the diariser).

### 5.7 The SOP pass: `eval-suite.py`

`tools/eval-suite.py` drives the standard evaluation pass against one live endpoint and writes one receipt directory. Axes are chosen with `--checks`: default `contract,house,needle`; add `hard,tools` for reasoning/tool-calling arms; add `horizon` for agentic ones. It calls `quality-battery.py`, `needle-haystack.py`, `bfcl-eval.py` and the ds4 hard tier (`run_benchmarks.py` — GSM8K + ARC) against that endpoint. The contract axis checks `/v1/models` served id, `max_model_len`, and one greedy completion. This is the "house 37/37, needle 3/3, ARC 187/200, GSM8K 194/200, tools 1072/1240" family of numbers in the lane READMEs.

### 5.8 The llama-benchy profiles

The majority of profiles in `benchmarking/` are `llama-benchy` shapes. A profile fixes depth, concurrency, run count, prompt length and generation length. The names encode the question: `boot-check` (d0, c1, runs 1 — not for comparisons), `fast-smoke` (d0/8192/100000, c1, runs 3), `triage-smoke` (same depths, c1/2, runs 5), `deep-smoke` (d0/8192/100000, c1/2/5, runs 7), `orchestration-smoke` (d0, c1, runs 1 — run this before any multi-arm experiment to prove the driver can resolve, render, launch, and read results), `decode-triage` (d0/8192, c1, runs 5 — the workhorse for per-stream decode comparisons), `depth8k-c8` / `depth0-c8` (paired halves of a same-window interleaved depth control, run alternately against one booted server with `--skip-run`), `concurrency-sweep` (d0/8192, c1/4/8, runs 3 — where per-stream speed falls off and the TTFT cliff starts), `ceiling-sweep` (d0, c1/8/24/31/34/40, runs 3 — finds the aggregate-throughput knee), and the family of depth-cost, capacity-at-16k, acceptance-vs-depth and instrumented arms. A profile whose question is closed is archived; a profile nobody has executed is a profile nobody has validated.

### 5.9 The "house" metrics in lane READMEs

The lane READMEs quote "house 37/37" — the quality battery's combined easy+hard score. "Needle 3/3" means three needle depths passed. "ARC 187/200" and "GSM8K 194/200" are the hard tier from `recipes/ds4/benchmarks/run_benchmarks.py`. "Tools 1072/1240" is the BFCL score. These are quality axes, not speed axes. They are reported beside the speed cells so a fast arm is not assumed to be a good arm.

## 6. Provenance and Validation

A published number is traceable to its artifact. The rules:

1. **The recipe comes from that run's `recipe_qualified_name`.** The `measurement_recipe_state` field is often `None`.
2. **A `declared_hash` is a registry-declaration hash, not the executed configuration.** It identifies the declaration, not what ran.
3. **A cross-recipe throughput comparison is not a knob comparison.** Different recipes are different configurations. Comparing them is a comparison of arms, not of knobs.
4. **Derive an output-file → bench-id mapping by hashing**, `sha256(output.json) == sha256(bench_<id>/consolidated.json)`, not by recollection. A remembered mapping is not evidence.
5. **Cite the `--output` file, not `runs/`.** `runs/` is scratch and gets reaped. The `--output` file is durable and carries the same records. A complete bench id re-emitted with no requests exits 0 — grep the log for `re-emitting`.
6. **Read the launched serve command and the resolved value of the default** before calling an override neutral. An `-o` override that changes nothing reads as a null result.
7. **Do not benchmark on a node that still has probe containers.** The readiness probe hits the old server and reports ready in ~74 s versus ~250 s. Check `docker ps -aq --filter name=sparkrun` on every node.
8. **The prompt set is part of the measurement.** Synthetic or repetitive prompts measured +25 % higher speculative acceptance over natural ones. A speed number taken on a synthetic prompt is not a speed number for natural traffic.
9. **Read the granted KV pool from the boot log**, never from a computed estimate. A computed memory estimate is not a measurement.
10. **A fix recorded only in prose has no guard.** When a test loop is extended to a new input, inject a defect and watch the suite go red. The completion gate is "is there a boot/run behind it?".

### The two-record trap, in full

A cell's JSON holds both a context-prefill record and a decode record. Both carry `tg_throughput`, `pp_throughput`, and `ttfr`. The values differ by a large factor. The printed table shows only the decode row. A reader who assumes the third printed column is "the prefill number" is wrong. A reader who quotes the printed `ttfr` as time-to-first-token quotes a value three times too low. The discipline reads the named fields and selects the phase explicitly with `is_context_prefill_phase`. Print the record count per cell before interpreting any table.

### Prometheus gauges

When a run scrapes Prometheus, the gauge dicts are keyed by label set, not by metric name. The obvious nested lookup returns `None` for every row. Assert a nonzero before believing a zero. `spec_accept_length` is last-written, not a window mean. `cache_hit_rate` is 0 during pure decode. A metric that reads zero may be a lookup failure, not a real zero.

## 7. What Each Lane's Columns Mean

The main README has separate tables per lane because each lane's instrument and metric differ. The derivation is the same discipline; the unit changes.

- **Chat lanes** (DeepSeek V4, Ornith 1.5, Qwen 3x/4x, IFM K2-Horizon, GLM 5.3): C1/C2/C5/C10 in t/s from the `concurrency-ladder` profile at depth 0. Size in GB. Mem% from the boot log. TP as a configuration value. Footnotes carry the receipt path, the run count, and any caveat about which boot produced which cell.
- **Decision lanes** (JEV-9B, clef-flash, the Decision-2.0 family): Accuracy from the decision suite on the same boot, req/s from `decision-ladder.py` at c 1/2/5/10. The unit is requests per second, not tokens per second. A CPU-only arm reports no device Mem%. The forecaster row reports Accuracy as `—` by design because no classification instrument applies.
- **Media lane**: Task rate in the arm's own unit — images per second, seconds per clip, real-time factor, or wall per 1k output tokens. The API column names the route. A CPU-only arm has no device Mem%.
- **Embed and rerank lanes**: u/s from `pooling-bench.py` at c 1/2/5/10. The API column names `/v1/embeddings` or `/v1/score`. Only the embed 2B row carries a full C1–C10 ladder: `benchmarking/pooling-ladder-embed.yaml`, c 1/2/5/10, 100 requests per cell, ~256-token inputs, 5 warmups, salted, `-b dimension_check=2048`. The embed 8B and rerank 2B rows carry C1 only, each from a single concurrency-1 receipt; the rerank 8B row has no performance cells yet. A row with only C1 is one sample, not a ladder point. The README footnote states that the 2B row's ladder is not the 8B row's shape, so the two embed rows' cells are not comparable.

## 8. Reading a Footnote

Every table's footnote carries the derivation. A typical footnote reads: "Ornith ladder cells are @ d0, pp 2048, tg 128, n=5, decode rows read from each receipt's `--output` file." That means: depth 0, prompt 2048 tokens, generated 128 tokens, five runs per cell, decode record selected from the named output artifact. A footnote that names a `bench_<id>` identifies the run. A footnote that names a receipt directory identifies the artifact tree. A footnote that says "first boot" or "single-point" tells you the cell is one sample, not a ladder. A footnote that says "cross-boot" tells you the cell's uncertainty includes the 7–25 % inter-boot term. A cell quoted without a footnote is not citable; find the receipt or treat the number as provisional.

## 9. Validation Checklist Before Quoting a Number

1. Does a boot/run exist behind the cell? If not, the cell is `—`, not a guess.
2. Is the row the decode row? Check `is_context_prefill_phase`.
3. Is the number aggregate or per-stream? The table's C-columns are aggregate; `tg_req_throughput` is per-stream.
4. Is the run count stated? A cell without `n` is not citable.
5. Is the receipt named? A path in the footnote is the citation.
6. Is the profile named? `concurrency-ladder` for the C-columns; `standard-suite` for the suite; `pooling-ladder-*` for u/s.
7. Is the shape labelled when it differs? `short=false`, `hardmode=true`, a 512-token BFCL budget, a `tg=32` probe — each is a different shape and cannot be pooled with the standard shape.
8. Is the version stated for a cross-lane comparison? `tool-eval-bench` v2.6.0 vs v2.8.0.
9. Is the noise floor stated for the cell? A noise floor belongs to a (configuration, cell) pair.
10. Is the claim within the cell's own resolution? A C1 cell with ±10.66 cannot resolve a 5 % difference.
