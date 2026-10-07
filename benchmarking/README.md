# Benchmark Profiles

llama-benchy profiles used by `sparkrun benchmark performance <recipe> --profile <this dir>/<name>.yaml`.

**This directory is the curated library, not the archive.** It holds the profiles that are tracked,
named below, or cited by a recipe/tool/test. The **82 single-use experiment arms** from the finished
qwen4 and qwen3 optimization campaigns were archived under `attic/benchmarking/` with a per-profile
`ARMS-MANIFEST.md`, and that archive was itself deleted from the tree in commit `b4ab22b` (2026-10-06).
If a `bench_*` id cites a profile that is not here, recover it with `git show b4ab22b^:<path>`.

---

## Rules that matter more than any individual profile

Both were learned expensively here.

1. **`tg t/s` in the sparkrun table is an AGGREGATE across concurrent streams, not a per-stream
   rate.** Read the `tg_req_throughput` field in the JSON instead, or the number misstates by a
   factor of `concurrency`. `reconcile-headline.yaml` exists because published numbers were
   ambiguous this way.

2. **Never read a result from the printed sparkrun table. Read the `runs/*.json`.** The progress
   table prints rows like `16384  8  988.5  70.4  12239.7  3` with **no column header at all**, and
   it prints **only the decode-phase row** of what is actually a two-row result. Decoded against the
   JSON, those columns are `depth, concurrency, pp_throughput(decode row), tg_throughput(decode
   row), ttfr(decode row), runs`. The trap is the second row: the JSON also holds a prefill-phase
   row (`is_context_prefill_phase: true`) whose same-named fields are very different — in that same
   run `pp_throughput` is **2135.9** there and **988.5** in the printed row, and `ttfr` is **37.6 s**
   there versus **12.2 s** printed. So assuming the printed third column is "the prefill number" is
   wrong, and quoting the printed `ttfr` as time-to-first-token quotes a value **3x low**. Neither
   mistake raises an error. Read the named fields and select the phase explicitly from
   `~/.cache/sparkrun/benchmarks/bench_<id>/runs/NNN_d<depth>_c<c>.json`:
   `tg_throughput` (aggregate), `tg_req_throughput` (per stream), `pp_throughput`, `ttfr`, and
   `is_context_prefill_phase` to choose the row.

3. **`args.concurrency` does not clamp the server.** Offering c = 40 to a server whose pool grants 20
   produces 20 running requests plus a queue. Judge capacity from `#running-req` and `full token
   usage` in the server log, never from the profile's own field.

**Noise.** Inter-boot noise is not one number: a no-spec boot reproduces to ±0.25 %, but a DFLASH
boot spreads ~±15 % across 20 identical boots. So no profile here with `runs` < 5 supports a
**cross-boot** comparison, and even `runs: 7` needs a same-window control. **Within-cell** spread is
different: over the archived cells with ≥ 2 runs the median per-run cv is **3.6 %**, so a **same-boot**
`runs: 2` pair resolves a 20 % effect comfortably. Pick `runs` from the effect size you need to
detect, not from a blanket minimum, and prefer **same-boot or interleaved** over more runs — a control
in the same container removes the 7–25 % term that repetition cannot touch. **And low concurrency is
not the quiet regime:** the worst within-cell cvs in the archive (11–15 %) are at depth 0, c = 1.

---

## Smoke / validation

| profile | depth | concurrency | runs | use |
|---|---|---|---|---|
| `boot-check` | 0 | 1 | 1 | Fastest proof a recipe launches and serves. **Not for comparisons** — one run at one depth resolves nothing. |
| `fast-smoke` | 0, 8192, 100000 | 1 | 3 | Default broad pass. Most historical numbers were taken with this, so it is the shape to reproduce when comparing to the past. |
| `triage-smoke` | 0, 8192, 100000 | 1, 2 | 5 | `fast-smoke` with the repetition count needed to say anything. |
| `deep-smoke` | 0, 8192, 100000 | 1, 2, 5 | 7 | Widest matrix. Long; use when a decision rests on the result. |
| `orchestration-smoke` | 0 | 1 | 1 | **Run this before any multi-arm experiment.** Proves the driver can resolve the recipe, render the command, launch, and read results back. Phase 11 lost its whole first queue to a YAML error that this would have caught in one boot. |

## Paired depth control

| profile | depth | concurrency | runs | use |
|---|---|---|---|---|
| `depth8k-c8` | 8192 | 8 | 3 | The two halves of a same-window interleaved depth control. **Run them alternately against one booted server with `--skip-run`** — depth is a benchmark argument, not a serve argument, so this costs no boot. |
| `depth0-c8` | 0 | 8 | 3 | Exists because the depth penalty was measured twice and disagreed: 25 % vs 32 % against a ±15 % noise floor. **Keep the two files in lockstep** — any difference other than `depth` turns a paired test into two unrelated experiments. |

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
| `ceiling-sweep` | 0 | 1, 8, 24, 31, 34, 40 | 3 | Depth-0 ceiling: finds the aggregate-throughput knee. **Depth-0 only on purpose** — depth and concurrency bind different limits; mixing them in one sweep is how the "2.8× depth penalty" misreading happened. |
| `d8k_c1` | 8192 | 1, 8 | 3 | The boring baseline `ceiling-sweep` omitted. At c = 1 depth is free (29.9 vs 29.0 t/s). Pair it with `ceiling-sweep` on the same booted server (`--skip-run`, so it costs no boot). |
| `ratio-at-depth` | 8192 | 8, 16 | 5 | **The capacity experiment.** At depth 0 the mamba *slot cap* binds; at depth 8192 the *token pool* binds. Those want opposite `mamba_full_memory_ratio` values. |
| `capacity-at-16k` | 16384 | 1, 12 | 4 | Same question at 16k, where the two limits sit far apart and the test bites harder. `c = 1` doubles as the null. |
| `capacity-at-16k-above-ceiling` | 16384 | 16, 20 | 4 | The follow-up that offers **more** than the treatment ceiling, so the ceiling is actually exercised. Judge on `#running-req` vs ceiling, not on throughput. |
| `acceptance-vs-depth` | 0, 16384 | 1 | 5 | `accept len` vs context depth **in one boot**, `tg` fixed. Decode t/s = `accept_len / step_time`, so "depth costs a single stream nothing" does **not** establish that acceptance is depth-independent. |
| `cross-node-null` | 0 | 1 | 2 | Byte-identical server on two nodes, minimal decode. The reference scale for every perturbation experiment: if changing a machine moves the metric as much as changing the config does, the config result is unrankable. |

## Batch / `max_num_seqs` cliff family (qwen4)

These localise a throughput penalty that appears when **offered concurrency equals `max_num_seqs`**.
Most are single-cell or narrow-curve profiles meant to be run with `-o` overrides against whichever
recipe is under test — the profile files themselves deliberately carry no recipe.

| profile | depth | concurrency | runs | question |
|---|---|---|---|---|
| `bs-sweep`, `bs-sweep-high` | 8192 | 1–24 | 7 | The original curves. |
| `bs4-only`, `bs8-only` | 8192 | 4, 8 | 9 | Single-cell reruns, arm-agnostic, for re-measuring one point without the whole sweep. In-sweep bs=4 is bimodal, so an in-sweep median is a coin flip between clusters. |
| `bs-order-reverse` | 8192 | as sweep | 7 | Reversed cell order, to separate an effect from the order cells run in. |
| `bs-cap16-k24`, `bs-cap16-fullcurve` | 8192 | 8–24 | 7 | Under `max_num_seqs = 16`: k = 8/12/16 are non-binding internal controls; k = 24 is the treatment. |
| `bs-cap20-k16-20-24`, `bs-cap24-k16-20-24` | 8192 | 16, 20, 24 | 7 | Is k = 20 intrinsically bad, or only bad when k equals the cap? |
| `lq-bs-sweep-high` | 8192 | 8–24 | 7 | labquant past bs = 8, cell-for-cell matched to the RadixArk sweep. |

**A fixed defect worth knowing about (`bs8-only.yaml`).** An earlier revision of this file had its
`args` at the **top level with no `args:` key**, which made `yaml.safe_load` + `d["args"]` raise
`KeyError` on this one file and not on its siblings. It now carries a proper `args:` block, so every
profile here has the same shape. (This is recorded rather than deleted because the misdiagnosis is
instructive: the file was also briefly claimed to be *broken* for missing a top-level `framework:` —
the real loader requirement — when in fact only `bs-sweep-high.yaml` had that latent defect.)

## Depth-cost / prefill-attribution family (qwen3, 2026-09-21/22)

| profile | depth | c | runs | status | what it asks |
|---|---|---|---|---|---|
| `pp-vs-depth-acceptance` | 1024 / 1024→16384 | 4 | 3 | RUN | Is the acceptance step a PROMPT-length effect or a GENERATED-length effect? `depth` fixed, `pp` swept. Zero-boot. |
| `peak-vs-depth` | 1024/4096/8192 | 8 | 7 | RUN ×9 | Is the decode STEP slower at depth, or is the machine busy prefilling? The most-run profile in this directory. |
| `iso-kv` | 8192 | 8 | 3 | RUN ×4 | Three cells with equal `c×(depth+pp)` = 81,920, testing whether cost follows batch-total KV bytes. NOTE: the three cells are PAIRS driven with `-b`, not a cross product of the `args:` lists. |
| `iso-prompt` | 4096 | 4 | 3 | RUN ×6 | Holds prompt length constant while varying depth, to separate prefill admission work from context length. |
| `pp-crossed-identifiability` | 4096/8192 | 2,4,8 | 3 | RUN | Crosses `pp` with `c` to break the `B = c·depth` / `P = c·(depth+pp)` collinearity. Its own selftest found the additive form is the wrong model. |
| `pp-slope` | 1024/4096 | 8 | 3 | RUN | Single-variable prompt-length sweep: the cleanest measurement of decode step time vs resident tokens. |
| `depth-slope-decode-metric` | 1024→16384 | 4 | 3 | RUN | Depth sweep scored on the server's OWN `gen throughput` rather than the harness's, removing prefill contamination. |

**Archived 2026-10-04, deleted 2026-10-06 — the four `NOT RUN` rows of this family.** `pp-sweep-c4c8`,
`a2-depth-gap-c8`, `kv-residency-dissociation`, and `d0-baseline-dissociation` were moved to
`attic/benchmarking/` with manifest rows, then deleted with that archive in `b4ab22b`
(`git show b4ab22b^:attic/benchmarking/<name>.yaml`). They were never executed, so
they produced no `bench_*` id; their questions are closed by other means (`pp-sweep-c4c8` superseded by
`pp-slope` / `pp-vs-depth-acceptance`; `a2-depth-gap-c8` closed by the c=8 depth-cost work;
`kv-residency-dissociation` carries a `depth: 26624` cell that exceeds any pool here — a design note,
not a runnable profile; `d0-baseline-dissociation`'s question is subsumed by the depth-cost family).
Their design intent remains documented in the archived copies and in the qwen3 lane's `§N` sections.

**A `NOT RUN` row is the useful kind.** `Status` is read from whether a `.scratch/` benchlog for the
profile exists — never from the profile's own description, which states intent and cannot know whether
the run happened. A profile nobody has executed is a profile nobody has validated.

## Instrumented arms (qwen4 gauges)

These run with `--enable-metrics` and were built to answer specific qwen4 questions; they are kept
because a live recipe or the qwen4 lane still cites them.

| profile | use |
|---|---|
| `instr-cps4096-vs-2048-k16` | `chunked_prefill_size` 4096 vs 2048 at k=16, instrumented. |
| `lq-graphson-cps8192` | labquant with the prefill graph re-enabled (a deliberate falsification arm). |
| `rk-nograph-cps8192-k8-16-24` | RadixArk prefill-graph-off arm at cps=8192. |
| `pool128-cap32-causal` | The causal pool-112→128 test (§19x), RadixArk. |
| `pool128-cap32-causal-REPL` | Its replication — a **new filename is required** per replication because the bench id hashes the profile path. |

## Non-qwen4

| profile | use |
|---|---|
| `ds4-sglang-depth0-ladder` | The DeepSeek-V4.1-Flash lane's depth-0 ladder. |

---

## Adding a profile

- Keep the directory to the curated set. An arm whose question is closed is removed in a commit that
  records its rationale and a closure pointer (the `attic/benchmarking/` archive was itself deleted
  in `b4ab22b`); `git show b4ab22b^:<path>` recovers any archived profile.
- A replication needs a **new filename** — the bench id hashes `(recipe, profile path, overrides,
  nodes)`, so reusing a name silently resumes and rewrites identical JSON. `*-REPL`, `*-rep2`,
  `*-desc` are the conventions.
- Put the profile's rationale in its own `metadata.description`. It is the authoritative per-profile
  record; the tables above are an index and may lag.