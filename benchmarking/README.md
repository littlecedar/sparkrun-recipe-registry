# Benchmark Profiles

llama-benchy profiles used by `sparkrun benchmark performance --profile <this dir>/<name>.yaml`.

Two rules that matter more than any individual profile, both learned expensively here:

1. **`tg t/s` in the sparkrun table is an AGGREGATE across concurrent streams, not a per-stream
   rate.** Read the `tg_req_throughput` field in the JSON instead, or the number misstates by a
   factor of `concurrency`. `reconcile-headline.yaml` exists because published numbers were
   ambiguous this way.
2. **Never read a result from the printed sparkrun table. Read the `runs/*.json`.** The progress
   table prints rows like `16384  8  988.5  70.4  12239.7  3` with **no column header at all**, and
   it prints **only the decode-phase row** of what is actually a two-row result. Decoded against the
   JSON, those columns are `depth, concurrency, pp_throughput(decode row), tg_throughput(decode
   row), ttfr(decode row), runs`. The trap is the second row: the JSON also holds a prefill-phase
   row (`is_context_prefill_phase: true`) whose same-named fields are very different — for this same
   run `pp_throughput` is **2135.9** there and **988.5** in the printed row, and `ttfr` is **37.6 s**
   there versus **12.2 s** printed. So assuming the printed third column is "the prefill number" is
   wrong, and quoting the printed `ttfr` as time-to-first-token quotes a value **3x low**. Neither
   mistake raises an error. Read the named fields and select the phase explicitly:
   `/tmp/srhome/.cache/sparkrun/benchmarks/bench_<id>/runs/NNN_d<depth>_c<c>.json`, with
   `tg_throughput` (aggregate), `tg_req_throughput` (per stream), `pp_throughput`, `ttfr`, and
   `is_context_prefill_phase` to choose the row. `summarize_ceiling.py` and `analyze_phase28.py`
   already do this.
   **This rule was wrong on its first version** — it called 988.5 "prefill t/s", which is the decode
   row's value, and I wrote that after checking the JSON once and misreading which row I had read.
   That is the whole argument for reading the JSON rather than the table: it applies to
   documentation about the table too.

3. **`args.concurrency` does not clamp the server.** Offering c = 40 to a server whose pool
   grants 20 produces 20 running requests plus a queue. Judge capacity from `#running-req` and
   `full token usage` in the server log, never from the profile's own field.

Inter-boot noise is not one number: **a no-spec boot reproduces to ±0.25 % (12.52–12.58 tok/s), but a
DFLASH boot spreads ~±15 % (21.2–30.2 across 20 identical boots)** — WORK.md §3. So no profile here
with `runs` < 5 supports a **cross-boot** comparison, and even `runs: 7` needs a same-window control: with 7 runs the
standard error of a DFLASH mean is still ~6 %, which is smaller than many of the effects being tested
and larger than several that were initially claimed. Pair within a node and interleave; the pooled
across-node estimate on this recipe has been wrong by 8 points.

**Cross-boot and within-cell noise are different quantities, and the rule above applies to the first
only.** Within-cell per-run spread, measured over the 97 archived cells that have ≥ 2 runs: **median cv
3.6 %**, 57 % below 5 %, 68 % below 10 %. So a **same-boot** `runs: 2` pair resolves a 20 % effect
comfortably, which is why most of the 23 profiles here with `runs` < 5 are legitimate — they are
same-boot control cells for effects in the 20–56 % range. Pick `runs` from the effect size you need to
detect, not from a blanket minimum. The ordering that matters: **same-boot or interleaved beats more
runs**, always, because a control in the same container removes the 7–25 % term that repetition cannot
touch.

**And do not assume low concurrency is the quiet regime.** The six worst within-cell cvs in the whole
archive (11–15 %) are at **depth 0, c = 1** — single stream, no queueing, no pool pressure, the
cleanest-looking cell in the matrix. Depth 16384 at c = 1 is also ~11 %. A profile reaching for `c = 1`
to be "clean" should print its own per-run values before believing that; `summarize_ceiling.py` does.

## Smoke / validation

| profile | depth | concurrency | runs | use |
|---|---|---|---|---|
| `boot-check` | 0 | 1 | 1 | Fastest proof a recipe launches and serves. **Not for comparisons** — one run at one depth resolves nothing. |
| `fast-smoke` | 0, 8192, 100000 | 1 | 3 | Default broad pass. Most historical numbers here were taken with this, so it is the shape to reproduce when comparing to the past. |
| `triage-smoke` | 0, 8192, 100000 | 1, 2 | 5 | `fast-smoke` with the repetition count needed to say anything. |
| `deep-smoke` | 0, 8192, 100000 | 1, 2, 5 | 7 | Widest matrix. Long; use when a decision rests on the result. |
| `orchestration-smoke` | 0 | 1 | 1 | **Run this before any multi-arm experiment.** Proves the driver can resolve the recipe, render the command, launch, and read results back. Phase 11 lost its whole first queue to a YAML error that this would have caught in one boot. |

## Paired depth control

| profile | depth | concurrency | runs | use |
|---|---|---|---|---|
| `depth8k-c8` | 8192 | 8 | 3 | The two halves of a same-window interleaved depth control. **Run them alternately against one booted server with `--skip-run`** — depth is a benchmark argument, not a serve argument, so this costs no boot. |
| `depth0-c8` | 0 | 8 | 3 | Exists because the depth penalty was measured twice and disagreed: 25 % (§9) vs 32 % (§12.8) against a ±15 % noise floor. Two cross-phase boots cannot resolve that; an interleaved pair can. **Keep the two files in lockstep** — any difference other than `depth` turns a paired test into two unrelated experiments. |

## Decode measurement

| profile | depth | concurrency | runs | use |
|---|---|---|---|---|
| `decode-triage` | 0, 8192 | 1 | 5 | The workhorse for per-stream decode comparisons. Chosen over `fast-smoke` purely for `runs`. |
| `decode-prefilloff` | 0, 8192 | 1 | 7 | Same, for arms whose **prefill** CUDA graph is disabled (the labquant QSA workaround). Keeps cells where a prefill-graph penalty cannot contaminate a decode comparison. |
| `short-gen` | 0 | 1 | 5 | `tg: 32` probe. A `t/s` quoted at `tg=32` is not comparable to one at `tg=128`: prefill amortises over 4× fewer tokens and the tail is early CoT, not steady state. |
| `reconcile-headline` | 0 | 1, 2 | 5 | Reproduce a published single-number headline on the profile that produced it. |
| `confirm-blocksize` | 0 | 1 | 7 | Interleaved confirmation for a specific shipped change (`block_size 4 → 8`). Exists because `decode-triage` ran arms in separate phases and left the distributions overlapping. |

## Capacity / concurrency

| profile | depth | concurrency | runs | use |
|---|---|---|---|---|
| `concurrency-sweep` | 0, 8192 | 1, 4, 8 | 3 | Where does per-stream speed fall off, and where does the TTFT cliff start. |
| `ceiling-sweep` | 0 | 1, 8, 24, 31, 34, 40 | 3 | Depth-0 ceiling: finds the aggregate-throughput knee. **Depth-0 only on purpose** — the depth-8192 points live in `depth8k`/`ratio-at-depth`, because depth and concurrency bind different limits and mixing them in one sweep is how the "2.8× depth penalty" misreading happened. |
| `d8k_c1` | 8192 | 1, 8 | 3 | The boring baseline the ceiling sweep omitted. At c = 1 depth is free (29.9 vs 29.0 t/s); this is the profile that establishes it. Pair it with `ceiling-sweep` on the same booted server (`--skip-run`, so it costs no boot). |
| `ratio-at-depth` | 8192 | 8, 16 | 5 | **The capacity experiment.** At depth 0 the mamba *slot cap* binds; at depth 8192 the *token pool* binds (`#running-req` 14, usage 0.99). Those want opposite `mamba_full_memory_ratio` values, so the shipped 3.51 cannot be judged from depth-0 data. c = 16 sits above the 14-context wall and below the predicted 18 grant, so a real gain is visible as `#running-req` reaching 16. |
| `capacity-at-16k` | 16384 | 1, 12 | 4 | Same question at 16k, where the two limits sit far apart and the test bites harder. `c = 1` doubles as the null. **Caveat learned the hard way: `c` must be at or above the treatment arm's ceiling or the treatment is clipped by the experiment, not by capacity** — phase 26 offered 12 against a ceiling of 14, so its ratio was a lower bound. |
| `capacity-at-16k-above-ceiling` | 16384 | 16, 20 | 4 | The follow-up that fixes the above: offer **more** than the treatment ceiling, so the ceiling is actually exercised. Judge on `#running-req` vs ceiling, not on throughput — "no arm admits more than `min(cap, #tokens // L)`" is the falsifiable claim. |
| `acceptance-vs-depth` | 0, 16384 | 1 | 5 | `accept len` vs context depth **in one boot**, `tg` held fixed. Needed because decode t/s = `accept_len / step_time`, so "depth costs a single stream nothing" (a t/s statement) does **not** establish that acceptance is depth-independent. Earlier attempts failed on comparing mismatched *windows*; bucket by `#running-req` with `decode_accept_by_concurrency.py` and compare only equal buckets. |
| `cross-node-null` | 0 | 1 | 2 | Byte-identical server on two nodes, minimal decode. The reference scale for every perturbation experiment: if changing a machine moves the metric as much as changing the config does, the config result is unrankable. |

## Concurrency / `max_num_seqs` cliff family

These exist to localise an ~11 % throughput penalty that appears when **offered concurrency equals
`max_num_seqs`**. They are single-cell or narrow-curve profiles intended to be run with `-o` overrides
(`max_num_seqs`, `speculative_draft_tokens`) against whichever recipe is under test — the profile
files themselves deliberately carry no recipe.

| profile | depth | concurrency | runs | question |
|---|---|---|---|---|
| `bs-sweep`, `bs-sweep-high` | 8192 | 8…24 | 7 | The original curves. |
| `bs4-only`, `bs8-only` | 8192 | 4, 8 | 9 | Single-cell reruns, arm-agnostic, for re-measuring one point without the whole sweep. |
| `bs-order-reverse` | 8192 | as sweep | 7 | Reversed cell order, to separate an effect from the order cells run in. |
| `bs-cap16-k24`, `bs-cap16-fullcurve` | 8192 | 8–24 | 7 | Under `max_num_seqs = 16`: k = 8/12/16 are non-binding internal controls; k = 24 is the treatment. |
| `bs-cap20-k16-20-24`, `bs-cap24-k16-20-24` | 8192 | 16, 20, 24 | 7 | Is k = 20 intrinsically bad, or only bad when k equals the cap? Each needs 16 healthy (control), 20 (the question), 24 (cliff reproduction) at a different cap. |
| `lq-bs-sweep-high` | 8192 | 8–24 | 7 | labquant past bs = 8, cell-for-cell matched to the RadixArk sweep, to compare where each peaks and where each falls off. |

**One real defect in this family, now fixed, plus a claim of mine that was wrong.** What was actually
broken in `bs8-only.yaml` and `bs-sweep-high.yaml` was a **missing top-level `framework:` key** —
`BenchmarkSpec.load` (`core/benchmark_profiles.py:219-226`) requires it — and both files had never been
run, so the defect was latent rather than observed. The error it raises names a `benchmark` mapping that
the loader does not require, so the message misleads. An earlier revision of this README additionally
claimed `bs8-only.yaml` was broken because its parameters sit at the **top level** rather than under
`args:`. That is false: a `--dry-run` of that profile resolves `depth: [8192]` and `concurrency: [8]`
correctly, so sparkrun accepts both shapes. The layout is an inconsistency worth normalising, **not** a
defect — and it is recorded here rather than quietly deleted because assuming "different from its
siblings" implies "broken" is exactly the kind of inference that produces confident wrong statements in
a reference document. **A profile nobody has executed is a profile nobody has validated** — which cuts
both ways: I validated the fix and did not validate my diagnosis.
| `capacity-at-16k` | 16384 | 1, 12 | 4 | Sharper falsifier for `usable = min(cap, #tokens // L)` than the 8k run: the two limits sit far apart at 16k, so it predicts **13 vs 7** usable (+86 %, more than double the 8k margin) and predicts the shipped arm is pool-bound at 7 while holding 20 slots. c = 1 is the null **and** the last untested point on "depth is capacity, not bandwidth" (at 8k, depth cost a single stream nothing). Run as `ship` vs `-o mamba_full_memory_ratio=1.2`, interleaved per node. |
| `cross-node-null` | 0 | 1 | 2 | Single-config probe run against a **byte-identical server on two nodes** to measure machine-to-machine numerical variation — the reference scale every perturbation experiment on this recipe is judged against (see `logprob_probe.py`'s node null, and WORK.md §12.11's argument that a null is a yardstick, not just a control). No overrides by design. |

## Depth-cost / prefill-attribution family (qwen3, 2026-09-21/22)

These are the profiles built to answer §12.22–§12.33. **`Status` is read from whether a
`*.benchlog` recording that profile exists under `.scratch/`** — not from the profile's own
description, which states intent and cannot know whether the run happened. Of the 84 profiles
on disk, **26 have ever been executed**; a profile with no benchlog is a design note.

| profile | depth | c | runs | status | what it asks |
|---|---|---|---|---|---|
| `pp-vs-depth-acceptance` | 1024 / 1024→16384 | 4 | 3 | RUN | Is the acceptance step a PROMPT-length effect or a GENERATED-length effect? `depth` fixed, `pp` swept 1024→16384. Zero-boot. Motivated by §12.33 — that sweep varied `depth`, so it established a prompt effect and left generated length untouched. |
| `peak-vs-depth` | 1024/4096/8192 | 8 | 7 | RUN ×9 | Is the decode STEP slower at depth, or is the machine busy prefilling? The most-run profile in this directory. |
| `iso-kv` | 8192 | 8 | 3 | RUN ×4 | Three cells with equal `c×(depth+pp)` = 81,920. Tests whether cost follows batch-total KV bytes. NOTE: its `args:` are defaults for the heaviest cell only — the three cells are PAIRS driven by `run_phase42.sh` with `-b`, not a cross product of these lists. |
| `iso-prompt` | 4096 | 4 | 3 | RUN ×6 | Holds prompt length constant while varying depth, to separate prefill admission work from context length. |
| `pp-crossed-identifiability` | 4096/8192 | 2,4,8 | 3 | RUN | Crosses `pp` with `c` to break the `B = c·depth` / `P = c·(depth+pp)` collinearity that made §12.29 unanswerable. Zero-boot. Its own selftest found the additive form is the wrong model — read §12.30 before quoting its coefficients. |
| `pp-slope` | 1024/4096 | 8 | 3 | RUN | Single-variable prompt-length sweep: the cleanest measurement of decode step time vs resident tokens, because it varies exactly one thing. |
| `depth-slope-decode-metric` | 1024→16384 | 4 | 3 | RUN | Depth sweep scored on the server's OWN `gen throughput` rather than the harness's, removing prefill contamination. Source of §12.33. |
| `pp-sweep-c4c8` | 1024/8192 | 4,8 | 3 | **NOT RUN** | Vary `pp` at fixed `c` and `depth`, one live container. Superseded in practice by `pp-slope` and `pp-vs-depth-acceptance`. |
| `a2-depth-gap-c8` | 1024/8192 | 8 | 7 | **NOT RUN** | Item A2: is the ~20 % per-stream depth cost at c=8 real or noise? Closed by other means (§12.22), so this remains unexecuted. |
| `kv-residency-dissociation` | 4096→26624 | 8,24 | 7 | **NOT RUN** | Dissociates batch size from KV residency. Its `depth: 26624` cell exceeds any pool here, so it would need editing before use — treat the file as a design note, not a runnable profile. |
| `d0-baseline-dissociation` | 0 / 8192 | 8,16 | 5 | **NOT RUN** | `depth = 0` baseline to separate prefill admission from decode cost. Renamed 2026-09-22 from a path corrupted by a persisted redaction token; content unaffected. |

**A `NOT RUN` row is the useful kind.** Five of these eleven were written and never executed,
and three of those five are the ones a reader would most plausibly assume had been run, because
their descriptions are detailed and confident. The `Status` column exists so that no future
session has to infer execution from the quality of a paragraph.

### Coverage, stated so nobody over-reads this file

This README names **41 of 84** profiles by stem. It is not an index and will not become one: the
remaining ~54 are single-use arms driven by `.scratch/qwen3-27b/run_phase*.sh`, whose purpose
is recorded next to the finding they produced. Two verifiable properties are maintained here
instead: **every profile-citation in this README resolves to a file** (checked 2026-09-22 by
matching each backticked name against the set of stems actually present; the check must ignore
field names like `pp_throughput` and `args`, which are also backticked here and are not
profiles), and **`benchmarking/*.yaml` contains no malformed filenames** (checked 2026-09-22
after one write persisted a redaction token into a path). The `metadata.description` field in
each file is the authoritative per-profile rationale — 79 of 84 carry a substantive one; the
four exceptions are the three smoke profiles and `bs8-only`. **A profile nobody has executed is
a profile nobody has validated**, which cuts both ways: it argues for running the `NOT RUN`
rows before trusting them, not for trusting their descriptions.

## Profiles here that belong to qwen4

`benchmarking/` is shared by both recipes, and these seven came from the qwen4 batch-size work
(referenced from `recipes/qwen4/`, driven by `.scratch/q4/launch-*.sh`). They are listed so that
`ls benchmarking/` and this README agree — **do not use them for qwen3 conclusions**; they are
`t g=128` batch sweeps against qwen4's checkpoints and flag sets.

| profile | depth | concurrency | runs | purpose |
|---|---|---|---|---|
| `bs-sweep` | 8192 | 1, 2, 4, 8 | 7 | Throughput vs batch size; tests whether the fixed per-step cost F is per-step or per-token. |
| `bs-sweep-high` | 8192 | 8, 12, 16, 24 | 7 | Extends the sweep past bs=8, which was the largest value ever swept on the shipping recipe. |
| `bs-cap16-fullcurve` | 8192 | 8, 12, 16, 24 | 7 | Same cells **under `-o max_num_seqs=16`** (required). k=8/12/16 are non-binding internal controls; k=24 is the treatment. |
| `bs-cap16-k24` | 8192 | 16, 24 | 7 | The running-batch cap test alone: bs=24 collapses against the cap-16 control. |
| `bs-order-reverse` | 8192 | 8, 4, 2, 1, 4 | 7 | Turns cell *position* within a sweep into the independent variable, after an isolated bs=4 rerun disagreed with the in-sweep bs=4 cell by 25+ %. |
| `bs4-only` | 8192 | 4 | 9 | Single-cell bs=4, arm-agnostic. In-sweep bs=4 is bimodal on both qwen4 checkpoints, so an in-sweep median is a coin flip between clusters. |
| `bs8-only` | 8192 | 8 | 9 | Single-cell bs=8. **Note the schema oddity:** its args sit at top level with no `args:` key. It loads and resolves correctly (verified by dry-run: `runs 9`, `concurrency [8]`), but `yaml.safe_load` + `d["args"]` raises `KeyError` on it, so any home-grown tooling that indexes `["args"]` will crash on this one file and not on the other 24. |

## Notes on the capacity profiles

Usable long-context concurrency is `min(granted slots, #tokens // context_length)` — **not**
`#tokens // context_length`. Cutting `mamba_full_memory_ratio` buys tokens by spending slots, and
at `D = 8` slots fall fast (`cap = K // 4`). The optimum is therefore an interior point and it
moves with context length (modelled ≈3.6 at 4k, ≈2.3 at 8k, ≈1.2 at 16k). Predictions for each arm
are written into the profile's own `metadata.description` **before** the run, so a wrong prediction
stays visible in the artifact rather than being edited away afterwards.

To analyse a result, prefer the repo helpers over reading the table:
`.scratch/qwen3-27b/summarize_ceiling.py` (aggregate vs per-stream, per-run cv) and
`.scratch/qwen3-27b/decode_accept_by_concurrency.py` (accept length bucketed by *running* request
count, so depth comparisons are made at matched concurrency instead of matched *offered*
concurrency — an earlier read made that mistake and called a window mismatch a finding).

`README.md` previously listed exactly one of these profiles. If you add one, add it here; a
profile nobody can find gets re-invented, and re-inventing one usually means silently changing its
`runs` count.
