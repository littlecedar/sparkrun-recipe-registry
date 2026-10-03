# PERF-ISSUES — `deepseek-v4.1-flash-exl3-tp6-1m-vllm` under `sparkrun benchmark performance --profile spark-arena-v2`

**Author:** ds4 agent, 2026-10-01. **For:** the solutions agent.
**Artifacts:** `/home/red/bench2/` on `10.0.4.30`; copies + live probes under
`.scratch/ds4/perf/` (this host). Recipe: `recipes/ds4/deepseek-v4.1-flash-exl3-tp6-1m-vllm.yaml`.

> **UPDATE 2026-10-01 (later): the mechanism is RESOLVED — read §9 first.** The
> collapse is the cost of a **cold deep prefill**, not decode starvation and not a
> capacity curve. Warm long-context concurrency is healthy (51 t/s at c2 vs the
> bench's 5.2). The TL;DR below is the original triage framing, kept for
> provenance; §9 supersedes §3 (root cause) and §4 (solutions).
>
> **UPDATE 2026-10-01 (solutions agent, live TP=4 1M A/B): read §10 first.**
> §10 confirms §9's mechanism, corrects two §9 magnitudes, adds the decisive
> measurement that the cold prefill is **compute-bound, not Engram-disk-bound**,
> and reports the `--long-prefill-token-threshold` A/B as a **mixed result → no
> recipe change**. Headline: the recipe is healthy; `spark-arena-v2` at `depth>0`
> measures cold prefill, and no tuning knob examined gives a clean throughput win.

## 0. TL;DR

The recipe is **not** globally slow — at short context and at single-stream it
matches or beats the `recipes/README.md` numbers. It **collapses at long
context with ≥2 concurrent requests**, and that is what dragged the spark-arena-v2
average down.

The observable fault is **starvation**: at long context with concurrency the
engine admits both requests (`Running: 2, Waiting: 0`, KV usage 1–2 %) and then
services one at ~0.1–0.4 tokens/s while the other runs at 30–45 t/s. Aggregate
decode falls to 1–2 t/s from ~40 t/s.

**Live A/B has RULED OUT the three obvious causes** — it is *not*
`max_num_batched_tokens`, *not* DSpark `k`, and *not* prefix caching (all three
were changed and the collapse persisted, §3A). The next step is a profiler run to
find what actually stalls (see §4). The README's t/s column was measured with a
short-prompt concurrency harness (`.scratch/ds4/gmu/measure_arm.py`) that never
exercises the fault, so it is not contradictory — it is **out of scope** for
what spark-arena-v2 measures.

## 1. What the benchmark reported

`spark-arena-v2` profile (`~/.cache/sparkrun/registries/_url_70b481ce5ca0/benchmarking/spark-arena-v2.yaml`):
`depth ∈ {0,4096,8192,16384,32768,65535,100000}`, `pp=2048`, `tg=128`,
`concurrency ∈ {1,2,5,10}`, `prefix_caching: true`, `runs: 3`.

Decode-phase aggregate `tg_throughput` (t/s), from
`benchmark_deepseek-v4.1-flash-exl3-tp6-1m-vllm_spark-arena-v2_tp6.json`:

| depth | c1 | c2 | c5 | c10 |
|--:|--:|--:|--:|--:|
| 0 | 36.2 | 45.1 | 34.1 | 34.0 |
| 4096 | 35.9 | 29.1 | 21.9 | 15.1 |
| 8192 | 38.8 | 21.3 | 11.6 | 8.4 |
| 16384 | 39.4 | 7.7 | 5.5 | 4.7 |
| 32768 | 36.1 | 5.3 | 3.1 | 2.7 |
| 65535 | 34.4 | 29.9 | 32.1 | 33.5 |
| 100000 | 41.9 | 1.5 | 0.9 | 0.8 |

Read this as three regimes:
- **Healthy:** every `c1` cell (34–42 t/s), all short-context cells, and the
  whole `65535` row.
- **Degraded:** `4096–8192` at `c5/c10` (batch contention, expected).
- **Collapsed:** `16384/32768/100000` at `c≥2` (2–8 t/s, down from ~40).

The non-monotonic shape (`65535` healthy, `32768` collapsed) is the tell that
this is **not** a capacity curve — it is a per-cell scheduling/spec-decode
pathology.

## 2. Evidence

### 2.1 Provenance

- Run `bench_1ad12b1c83e8`, head `10.0.4.30`, 2026-09-30 21:25 → 2026-10-01
  10:55 UTC. Recipe exactly as shipped (`max_num_seqs=16`, `gmu=0.85`,
  DSpark `k=3`, both mods). Reproducibility caveat: `runs: 3`.
- A **prior** `spark-arena-v2` run of the same recipe, `bench_fbc26cb5f73e`
  (2026-09-25), used `max_num_seqs=8` / `gmu=0.80` / **no DSpark** / only the
  patch mod. It had **no collapse at 100000** (that row was 29–52 t/s) and
  collapsed only at `32768`. So the DSpark/retune path is strongly implicated.

### 2.2 The collapse is starvation, not a slow step

For each collapsed cell, per-request decode rates are **bimodal**: one or two
requests decode at a healthy 30–50 t/s while the others sit at 0.3–3 t/s. E.g.
`d32768 c2` inference `tg_req = [3.3, 31.5, 2.3, 31.9, 30.4, 2.4]`.

No collapsed cell has high `num_running_reqs`, and `GPU KV cache usage` stayed
at 0.9 % during the live reproduction — **this is not KV-pool exhaustion**. The
granted pool is **14,925,444 tokens (14.93×)**, verified at boot.

### 2.3 Live reproduction (2026-10-01, this session)

Booted the recipe as shipped; `GPU KV cache size: 14,925,444 tokens`. Then:

| probe | config | result |
|:--|:--|:--|
| `probe-A` | 1× 98.8K-token prompt, then repeat (prefix warm) | TTFT 1.0 s / 0.6 s, decode **44–55 t/s** → long context is fine once the prefill is cached |
| `probe-C` | 1× **truly cold** 98.8K prompt (unique head) | TTFT **255 s** (≈390 t/s prefill), decode 46 t/s |
| `probe-D` | **2× truly cold 32.5K prompts** | req0: TTFT 79 s, decode **1.5 t/s**; req1: TTFT 161 s, decode **35 t/s**; aggregate **1.55 t/s** |
| `measure_arm.py` | README harness, short prompts, c1/4/8/16 | **33.8 / 64.1 / 99.6 / 131.9 t/s** — reproduces the README |

`probe-D` is the smoking gun: two concurrent cold 32K requests produce the exact
benchmark signature (one starved request ⇒ aggregate 1.5 t/s), while a single
warm request is healthy.

### 2.4 Server log, `probe-D` window (`serve-oct1-live.log`)

```
20:51:45  prompt 3250.8 t/s  gen 0.1 t/s   Running: 2 reqs, Waiting: 0 reqs  KV 0.8%
20:52:05  prompt    0.0 t/s  gen 0.4 t/s   Running: 2 reqs, Waiting: 0 reqs  KV 0.8%
20:52:25  prompt    0.0 t/s  gen 0.1 t/s   Running: 2 reqs, Waiting: 0 reqs  KV 0.9%
20:53:05  prompt 3250.7 t/s  gen 24.1 t/s  Running: 0 reqs, Waiting: 0 reqs

SpecDecoding (same window):
20:52:15  Mean acceptance length: 1.00   Accepted: 0 / Drafted: 3   per-pos 0.000 0.000 0.000
20:52:25  Mean acceptance length: 1.00   Accepted: 0 / Drafted: 3
20:52:55  Mean acceptance length: 4.00   Accepted: 3 / Drafted: 3
20:53:05  Mean acceptance length: 2.68   Accepted: 151 / Drafted: 270  per-pos 0.811 0.511 0.356
```

Two facts, both load-bearing:
- **`Running: 2, Waiting: 0` with gen ≈ 0.1 t/s.** The scheduler believes it is
  running both requests, yet almost nothing is generated. This is the starvation
  signature, not a queue.
- **`Mean acceptance length: 1.00` with 0/3 accepted, repeatedly, then 2.68 once
  the working set drains.** Spec decode is effectively **off** on the stalled
  request — the drafter runs, accepts nothing, and bills the full verify cost.
  Acceptance recovers to a normal 2.7 (per-position 0.81/0.51/0.36) on the clean
  decode. This is exactly `#47930`'s "prefix caching collapses DSpark
  acceptance".

## 3. Root-cause hypothesis

**Leading (HIGH confidence) — scheduler / decode-path starvation at long context
under concurrency.** The engine reports `Running: 2 reqs, Waiting: 0` while
generation throughput is **0.1–0.4 t/s** and `GPU KV cache usage` is 1–2 %: both
requests are admitted and resident, yet one is advanced ~0.1 token/step instead of
~30–40, for the whole long-context load. `Mean acceptance length` is **3.00** in
the `mnbt=8192` boot (drafts 3, accepts 2) *while generation is 0.1–0.3 t/s* — so
acceptance is not the cause; the request is starved regardless.

**NEGATIVE (ruled out by live A/B, §3A):**
- `max_num_batched_tokens` 4096→8192 — no effect on the collapse, only −13 % KV.
- DSpark `k=3`→`k=1` — no effect on the collapse.
- Prefix-cache reuse — the truly-cold probes (`--unique`, unique token-0) collapse
  exactly like the warm ones, so a cache miss is not required to trigger it.

**Candidate mechanisms still open:**
- **M1 (most likely now): the DSpark *verifier/drafter* at long context is
  itself the slow step.** Even at `k=1` one request stalls; the drafter runs on the
  same sparse-MLA attention as the target. A profiler run on one node is needed
  (is a deep-context DSpark verify exceeding the step budget?).
- **M2: chunked-prefill ↔ decode interleaving at `max_num_batched_tokens`.** The
  starvation appears only when a `depth`-token context load coexists with a long
  decode batch. `mnbt` alone did not fix it, but the interaction is untested.
- **M3: a scheduling/fairness bug in this vLLM dev build** (`0.28.1rc1.dev388`)
  for long-context DSpark: the runnable set is non-empty and unserviced.

The intermittent `Mean acceptance length: 1.00` seen in the shipped-config boot
is a **correlated symptom**, not the root cause (§3A shows acceptance can be 3.00
during the same starvation).

## 3A. Experiments run (live, 2026-10-01, this session)

All cells are 2 requests (or as noted) with **unique** prompts, submitted
concurrently against one booted server; `probe_ttft.py` in `.scratch/ds4/perf/`.

| config | cell | result | verdict |
|:--|:--|:--|:--|
| **shipped** (`mnbt=4096`, k=3) | 1× warm 98.8K | TTFT 0.6–1.0 s, 44–55 t/s | long ctx healthy when warm & alone |
| **shipped** | 1× cold 98.8K | TTFT 255 s (~390 t/s prefill), 46 t/s | prefill slow but OK |
| **shipped** | **2× cold 32.5K** | one req 1.5 t/s, other 35 t/s → agg **1.55** | **collapse reproduces** |
| `mnbt=8192` | 2× cold 32.5K | one req 37.7 t/s, other 1.6 t/s → agg **1.50** | **NO FIX**; KV −13 % (14.93M → 12.96M) |
| DSpark **k=1** | 2× cold 32.5K | one req 32.3 t/s, other 2.0 t/s → agg **1.89** | **NO FIX**; KV 15.20M |
| DSpark k=1 | 2× cold 100K | not captured (workload stopped) | |

**The roles simply swap which request is starved** — the aggregate is the same.
This is why the benchmark's per-cell mean is reproducible even though the failure
looks random within a cell.

**Conclusion from the matrix:** the collapse is **not** caused by spec-decode
width (`k`), the step-token budget (`max_num_batched_tokens`), or the prefix
cache — it survives all three changes. It is a **scheduler / decode-path
starvation at long context under concurrency**: the engine admits both requests
(`Running: 2, Waiting: 0`, KV usage 1–2 %) and then services one at ~0.1–0.4
tokens/s while the other runs at 30–45 t/s, for the whole long-context load.

## 4. Suggested solutions (ranked, for the solutions agent)

> **Fast repro for iteration:** `d32768 c2` with truly-cold unique prompts
> (`probe_ttft.py http://127.0.0.1:8000 2 32768 x --unique`) reproduces the
> collapse in ~3 min. Confirm the server log shows `Running: 2, Waiting: 0` with
> `gen` ≈ 0.1–0.4 t/s.

**Already refuted — do not spend boots on these (§3A):**
~~`max_num_batched_tokens` 4096→8192~~, ~~DSpark `k=3`→`k=1`~~,
~~prefix-cache reuse~~.

**Highest value now — find what actually stalls.**
1. **Profiler run on one node (off the head, §11).** Reproduce `d32768 c2` and
   profile the engine: which kernel/phase consumes the ~5 s between tokens? Is a
   deep-context DSpark verifier step, the sparse-MLA decode, or the scheduler
   itself the stall? This decides M1 vs M2/M3 and is the only step that resolves
   the mechanism.
2. **A/B `--no-enable-prefix-caching`** as a cheap falsifier of the `#47930`
   path (the recipe body already flagged it). Low expected value now that
   cold-unique prompts collapse, but one flag and one boot.
3. **A/B `--enforce-eager`** (graphs off) on `d32768 c2`. If the stall vanishes,
   the fault is in the FULL_AND_PIECEWISE CUDA-graph capture of the long-context
   DSpark path — a concrete, shippable finding.
4. **Try `--disable-chunked-prefill`** (non-chunked prefill) on the cell. If the
   fault is prefill↔decode interleaving at depth (M2), removing chunking should
   change it.
5. **Check the sparse-MLA FlashInfer autotune**: the boot logs autotune a
   `FlashInfer SM120 sparse MLA DSv4.1 decode` config. Verify a tuned config
   covers the deep-context shapes; a `tactic=-1` fallback at 32K+ depth would be
   a concrete culprit (§7.10 is the analogous `mxfp8_gemm` case).
6. **If the recipe cannot be fixed, document the operating envelope.** The
   shipped recipe is healthy at `c=1` and at short/medium context with batch.
   The README should state that long-context **concurrent** serving is degraded,
   and the t/s table should name its harness.

## 5. Reproduction commands

```bash
# submit the exact benchmark
sparkrun benchmark performance --profile spark-arena-v2 \
  deepseek-v4.1-flash-exl3-tp6-1m-vllm

# minimal live mechanism probe (server already running)
python3 .scratch/ds4/perf/probe_ttft.py http://127.0.0.1:8000 2 32768 x --unique
# watch: docker exec <ctr> grep -E "Engine 000|SpecDecoding" /tmp/sparkrun_serve.log
```

## 6. Open questions for the solutions agent

- **What is actually consuming the step time** between the ~0.1 t/s tokens?
  A profiler run resolves M1/M2/M3 (see §4). Everything else is inference.
- Does the same starvation appear on the **300K sibling** and the **TP=4 arms**,
  at the same `(depth, concurrency)`? Predicted yes (same code path) but
  unmeasured — this determines whether it is a tp6/1M problem or a family problem.
- Is the **~390 t/s cold prefill at 98K** tokens expected, or also depressed?
  (Prior TP6-1M boot measured 579 t/s @799K; MiaAI reports 600–1100 t/s.)
- **Which change did it first?** The prior `spark-arena-v2` run
  (`bench_fbc26cb5f73e`, 2026-09-25) had 100000 healthy with
  `max_num_seqs=8`/`gmu 0.80`/**no DSpark**/patch-mod-only. A one-variable
  bisect (DSpark off; `max_num_seqs=8`; mod removed; vLLM-tune addition) would
  localise whether the 2026-09-27/30 changes introduced it or it was always
  latent. Note `k=1` did not fix it, so "DSpark on/off" is the sharper arm than
  "k value".


## 7. Follow-up to §1–§6 (independent re-derivation, 2026-10-01)

A second pass reproduced the triage's §1 numbers straight from the artifact
`benchmark_deepseek-v4.1-flash-exl3-tp6-1m-vllm_spark-arena-v2_tp6.csv`. Two
reconciliations are worth stating, because they clear two ways the section could
read today:

- **The triage §1 "t/s" column is the serving label `tg128` (Phase B), not the
  `ctx_tg` context-load label (Phase A).** Each bench cell emits two phases,
  `ctx_pp`/`ctx_tg` (context load) and `pp2048`/`tg128` (serving). Phase B is the
  real 2048-token prompt served against an already-cached load — that is the
  number `probe_ttft.py` and the README table share; Phase A is dominated by the
  2048-token prefill of the load and is slow everywhere, so it does not show the
  pathology. Reading Phase A instead of Phase B would look like a total collapse.
- **The non-monotonic shape is confirmed independently.** Served decode at c≥2 is
  39.4→7.7→5.5→4.7 (16384) / 36.1→5.2→3.1→2.7 (32768) / 41.9→1.5→0.9→0.7 (100000)
  against a flat 36.3/45.1/34.1/34.0 at d0 — and the **d65535 row sits back up
  (34.4/29.9/32.1/33.5)**. Non-monotonic-in-depth rules out a capacity curve and
  re-confirms triage §1: this is a per-cell scheduling/spec-decode pathology.

**Nothing in this pass changes the triage's conclusions or §3A.** The
`mnbt=8192` / DSpark `k=1` / prefix-cache exclusions are unchanged; this only
reproduces the served-decode decay shape. The load-bearing next check for the
solutions agent is still a **profiler run on the `d32768 c2` collapse** (triage
§4.1), not the A/B flags.

### Platform note for the solutions agent (this recipe needs the whole cluster)

`deepseek-v4.1-flash-exl3-tp6-1m-vllm` is `min_nodes: 6` = head `10.0.4.30` (rank 0
of the TP=6 group) + workers `.31`–`.35`. One recipe boot at a time per the COOP
hardware etiquette, and a 13-minute load holds all six nodes. The head node is off
limits to other work while it boots or holds a rank. Practically: the A/B arms in
§4 and the profiler run are **sequential, one-at-a-time, 6-node boots**.


## 8. Update 2026-10-01 — the TP=4 1M sibling reproduces the symptoms (user-reported)

> **Superseded by §9 (same day):** TP=4 1M was booted live and the cold-prefill
> collapse reproduces there (d32768 c2 cold 4.8 t/s; warm 51.2 t/s). Treat the
> replication as **VERIFIED**; the paragraph below is the original user-report
> write-up, kept for provenance.

The user reports `deepseek-v4.1-flash-exl3-tp4-1m-vllm` shows **the same
long-context-under-concurrency symptoms** as the TP=6 1M arm. Evidence label:
**LIKELY** — reported by the user, not yet captured as a bench artifact here (no
`*tp4-1m*` bench JSON exists under `/home/red/benchmarks/` or `bench2/`). Confirm
with the same `spark-arena-v2` profile (or the 3-minute `probe_ttft.py` repro)
before treating it as a measured replication.

**Why this matters — it is the most informative thing learned today:**

- It answers §6's open question — "does the same starvation appear on the TP=4
  arms?" — **yes**, at least for the 1M sibling. That demotes the hypothesis that
  this is a **TP=6 / virtual-heads-padding** artefact.
- The two recipes differ in exactly the knobs a topology-targeted fix would reach
  for (verified by reading both YAMLs this session):
  | knob | TP=6 1M | TP=4 1M |
  |:--|:--|:--|
  | `min_nodes` / TP degree | 6 / 6 | 4 / 4 |
  | `hf_overrides` (virtual heads) | **96/12 via `hf_overrides`** | **none** (native 64 heads, o_groups 8) |
  | `max_num_batched_tokens` | 4096 | **8192** |
  | `PYTORCH_CUDA_ALLOC_CONF` | `…,garbage_collection_threshold:0.6` | `expandable_segments:True` only |
  | KV pool (measured) | 14,925,444 tok | 5,750,109 tok (gmu 0.85) |
- A symptom that survives **different TP degree, different virtual-heads padding
  (present vs absent), different `mnbt` (4096 vs 8192), and different KV pool size**
  is not a function of any of them. Note the `mnbt` difference independently
  re-corroborates the triage's §3A `mnbt=8192`-is-not-the-cause result — TP=4 1M
  runs at 8192 natively and still collapses.
- What the two 1M arms **share**: the same EXL3 checkpoint, the same vLLM dev build
  (`0.28.1rc1.dev388`), the same DSpark drafter, the same **`max_model_len:
  1000000`**, and therefore the same deep-context sparse-MLA decode path. That
  narrows the culprit to the **long-context decode / DSpark / sparse-MLA path
  common to the 1M arms**, and away from anything TP=6-specific.

**Consequence for the solutions agent (priority change):**

1. **`max_model_len` (1M vs 300K) is now the sharper discriminator than TP=6 vs
   TP=4.** Caveat on the evidence: the 300K arms' published C1/C4/C8 numbers
   (§7.5 for TP=6, §1 for TP=4) come from the **short-prompt concurrency harness**
   and were never measured at `depth > 0`, so — exactly like the triage's §0
   warning about the README table — they do **not** bound the fault. The 300K arms
   are "healthy on the short-prompt harness", not "healthy at long-context
   concurrency", which is **unmeasured**. The decisive test is therefore: run the
   `spark-arena-v2` (or the `probe_ttft.py`) cells at `d32768 c2` on a **300K**
   arm. If 300K is healthy at depth on both TP degrees and 1M collapses on both,
   the variable is the **context length** — deep-context sparse-MLA / DSpark
   verify — not topology.
2. Do **not** spend a boot on a TP-degree bisect; TP degree is no longer a live
   variable for this fault.
3. **Run the profiler on the TP=4 1M arm, not the TP=6 arm.** TP=4 is
   `min_nodes: 4`, so a 4-node job fits on four of the five workers (e.g.
   `.31`–`.34`), leaving the head free — cheaper to iterate and it keeps the head
   clear. A single `d32768 c2` profile there tests the shared mechanism directly.


## 9. RESOLVED (mechanism) — 2026-10-01, live TP=4 1M + controlled warm/cold A/B

**The collapse is NOT a decode bug. It is the cost of a COLD deep prefill, and at
concurrency it is irreducible prefill work starving the decodes. The triage's
§2–§3 "starvation" framing is real at concurrency, but it is *the prefill
workload*, not a broken decode path.** Warm long-context concurrency is healthy
(51 t/s at c2). The recipe is not broken; the spark-arena-v2 "serving" number at
`depth>0` mostly measures a cold prefill.

### 9.1 The decisive experiment

Booted `deepseek-v4.1-flash-exl3-tp4-1m-vllm` as-shipped on the **`ds4tp4`**
cluster (`10.0.4.32`–`.35`; head `.32`; head node `.30` left free — cheaper than
the 6-node job and it still reproduces). KV pool **5,955,167 tokens**; boot log
shows the same sparse-MLA autotune + `mxfp8_gemm tactic=-1` lines as TP=6.

`warm_cold.py` (new; `.scratch/ds4/perf2/`) sends the exact spark-arena-v2
serving shape — context = `depth` corpus tokens, then the next 128 prompt tokens
— and flips one variable: whether the depth prefix was primed first.

| cell | mode | TTFT | per-req decode | aggregate |
|:--|:--|--:|:--|--:|
| d32768 c1 | **cold-unique** | **63.1 s** | 33.5 t/s | 1.9 t/s |
| d32768 c1 | **warm** | **0.4 s** | 37.6 t/s | 33.5 t/s |
| d32768 c2 | **cold** | 25.2 / 48.9 s | 4.5 / 26.5 t/s | 4.8 t/s |
| d32768 c2 | **warm** | 0.8 / 0.4 s | 30.4 / 27.9 t/s | **51.2 t/s** |
| d32768 c5 | **cold** | 25–123 s | 1.2–19 t/s | 5.0 t/s |
| d65535 c1 | **warm** | 0.6 s | 34.7 t/s | 29.9 t/s |
| d0 c1 (control) | cold | 0.8 s | 46.6 t/s | healthy |

**Warm long-context concurrency is healthy (51 t/s at c2).** The bench's 5.2 t/s
is entirely the **cold prefill** of the depth load; warm it, and the 2048/128-token
serving decode is 28–38 t/s per stream, exactly the README-class number.

**The concurrency "collapse" is prefill-bound, not stalled.** At d32768 c5 cold,
wall = 129 s for five requests; each spends ~73–123 s in prefill and ~1–4 s
decoding 128 tokens. That is 5 × 32768 ≈ **164K prefill tokens in ~100 s ≈
1600–2000 t/s aggregate prefill** — a normal TP=4 deep-prefill rate. The
"decode throughput" metric divides 128 tokens by a window that is ~99 % prefill,
so it reports ~5 t/s. **There is no starvation: the decode is fine, it is simply a
rounding error next to the prefill it follows.** The c1 monolithic-prefill case
(63 s) is the only place `--long-prefill-token-threshold` helps (28.5 s), because
it changes prefill chunking, not scheduling fairness.

### 9.2 Why the bench numbers are shaped the way they are

- **Serving-phase `ttfr` is the full prefill time** (llama-benchy
  `prefill_ratio` default 0 → no streamed chunks), and the bench's
  `tg_throughput = decode_tokens / (last_token − first_token)` starts at the first
  token. So a **cold** serving prefill inflates TTFT (d32768 c1 = 54 s in the bench
  JSON, 63 s live) and *contaminates* the reported decode rate. The "one request
  at 0.1–0.4 t/s" is a request blocked behind another request's **prefill**; the
  server log reads `Running: 4–5, Waiting: 0–1` with `prompt throughput ≈ 3182 t/s`
  ticking — i.e. a prefill is running, everyone else is stalled.
- **The non-monotonic depth shape (d65535 healthy at c≥2) is a cache-hit lottery,
  not a capacity curve.** llama-benchy builds the prompt from a **random** corpus
  slice: context = `tokens[start:start+depth]`, prompt = the next 2048. The served
  prompt is *usually* a prefix-cache hit on the depth load, but whether the hit
  lands depends on the random start's block alignment / hash boundary. The d65535
  row is the case where the serving prompt hit; its **context-load phase is still
  collapsed** (`ctx_tg` = 2.55 t/s, ctx TTFT = 103 s in the same JSON), which
  proves the depth load itself is the slow thing and the healthy serving number is
  the warm hit. (The corpus is ~150K tokens, so it does **not** repeat at these
  depths — this is not a repeat-corpus artifact.) d32768/100000 land off a hit →
  cold serving prefill → collapsed serving row.
  **Caveat:** I did not pin the exact prefix-hash/alignment condition that decides
  hit vs miss across depths; the direct warm-vs-cold A/B in §9.1 establishes the
  mechanism independent of that detail.
- **The real fault is the cost/latency of a cold deep prefill and its
  head-of-line blocking of every other request, at every concurrency.**
  `ctx_pp` at c10 d32768 is 668 t/s aggregate (≈67/stream) — the prefill is not
  catastrophically slow, it just takes ~50 s *per deep request* and, under V1's
  chunked scheduler, starves the concurrently-running decodes.

### 9.3 Upstream cross-refs (why this is a known shape)

- **vLLM #57413** (open, 2026-09-17): V1 scheduler has **no cap on concurrent
  partial prefills** → head-of-line blocking; short/medium requests starve behind a
  long prefill. **vLLM #50497** (RFC): the MLA chunked-context schedule is
  **batch-column shaped** — the longest request drives `num_chunks` and every
  prefill pays the merge each iteration. Both fit this exactly.
- **vLLM #47930** (open) / **PR #47926**: DSpark acceptance collapse on
  prefix-cache hits — the acceptance `1.00` we saw is real but secondary; it only
  applies to *shared prefixes*, and our cold-unique prompts collapse regardless.
- **vLLM #53600** (open) / **PR #53605**: sparse-MLA **decode** warmup only covers
  `extra_topk ∈ {0,128,512}`; runtime widths 256/384 → `tactic=-1` fallback. Check
  the autotune cache keys; this is a separate, smaller effect than the prefill HoL.

### 9.4 Solutions — revised (ranked)

1. **Cap long prefill per step — TESTED, partial.** Booted TP=4 1M with
   `--long-prefill-token-threshold 2048` (SchedulerConfig; default 0 = off).
   Result on the exact cold cells (`warm_cold.py`, new boot):
   | cell | shipped | +long-prefill 2048 |
   |:--|--:|--:|
   | d32768 c1 cold TTFT | 63.1 s | **28.5 s** |
   | d32768 c1 cold decode | 33.5 t/s | 35.5 t/s |
   | d32768 c5 cold agg decode | 5.0 t/s | **5.8 t/s** (ttft 73–105 s) |
   So capping the prefill chunk **≈2.2× faster per-request deep prefill at c1**
   (32768/28.5 ≈ 1150 t/s vs 32768/63 ≈ 520 t/s — chunked deep prefill is simply
   faster than a monolithic 32K chunk), but it does **not** fix the c5 stall:
   five cold 32K prefills are ~164K tokens of irreducible prefill work and the
   decodes wait for all of it. This is arithmetic, not a scheduler bug. Keep the
   flag as a cheap prefill win; do not sell it as the collapse fix.
2. **Stop benchmarking a cold prompt as if it were a serving decode.** Either
   (a) fix `spark-arena-v2` to `--no-cache` (fresh token-0) **and** report prefill
   and decode separately, per the branching caveat in the profile, or (b) accept
   that the "serving" row at `depth>0` measures a warm prefix hit — in which case
   the recipe is fine and only the *context-load* phase is slow. The profile's
   `runs: 3` mean hides the ttfr variance (see `ttfr std` in the JSON).
3. **The two cheap falsifiers now have a target.** `--no-enable-prefix-caching`
   should make the serving decode *slower* (more cold prefill); `--enforce-eager`
   tests whether the long-prefill capture path (FULL_AND_PIECEWISE) is the stall —
   re-run against the **TTFT**, not the decode number.
4. **Profiler run, reframed.** Profile one **cold deep prefill** (`d32768`), not a
   "stalled decode": which kernel/phase consumes the ~60 s? Candidates: sparse-MLA
   prefill dispatch (`sparse_mla_sm120_prefill.cu`, cf. #56771), the Engram disk
   stager (`EngramDiskStager.stage` syncs per step; cold reads of depth bytes), and
   the chunked-prefill scheduler.
5. **Do not spend boots on a TP-degree bisect** — TP=4 1M reproduces (live), so
   TP degree is not the variable.
6. **Document the operating envelope regardless.** The recipe serves long-context
   **warm** traffic at README-class rates (51 t/s at d32768 c2). A **cold** deep
   prefill costs ~30–63 s at 32K and ~160 s at 100K (c1), and at concurrency the
   prefills are serialized prefill work: five cold 32K requests need ~100 s of
   aggregate prefill before any decode is meaningful. `--long-prefill-token-threshold`
   halves the c1 cold-prefill time but not the c5 aggregate (the work is
   irreducible). The honest README statement is: "**long-context concurrent serving
   is throughput-limited by cold-prefill cost; warm-prefix long-context concurrency
   is healthy**", and the t/s table names its harness (`spark-arena-v2` serves a
   *warm* 2048-token prompt at `depth>0`).


## 10. SOLUTIONS (2026-10-01, live TP=4 1M A/B) — mechanism confirmed, no recipe change

**Agent:** solutions, `model_symbol=ds4`. **Boots:** two live boots of
`deepseek-v4.1-flash-exl3-tp4-1m-vllm` on cluster `ds4tp4` (head `.32`, `.30`
free), 2026-10-02 UTC. **Artifacts:** `.scratch/ds4/perf3/`
(`depth_ttft.py`, `disk_isolate.py`, `RESULTS-oct1.md`, boot logs). KV pools
5,781,108 (shipped) and 5,860,086 (lptt).

### 10.1 The mechanism is confirmed, and it is prefill, not decode

`depth_ttft.py` (serving shape: context = `depth` corpus tokens, prompt = 128,
**unique token-0** so no prefix hit) reproduces the bench exactly:

| depth | c | TTFT(s) | per-req decode | agg wall t/s | bench §1 |
|--|--|--|--|--|--|
| 4096 | 1 | 4.2 | 33.0 | 15.9 | — |
| 8192 | 1 | 6.3 | 35.8 | 13.0 | — |
| 16384 | 1 | 12.1 | 32.2 | 8.0 | — |
| 32768 | 1 | 24.1–24.5 (3 reps) | 32–38 | 4.6 | 36.1 |
| 32768 | 2 | 24.9 / 47.8 | 4.7 / 26.9 | **4.87** | 5.2 |
| 32768 | 5 | 25/50/74.6/99.6/120.3 | 1.3–20 | **5.05** | 3.1 |

**The decode is healthy.** Warm d32768 c2 = TTFT 0.4–0.8 s, per-req 28–30 t/s,
**aggregate 50.5 t/s** (vs the bench's 5.2). The collapse is entirely the *cold
prefill* that precedes the 128-token decode, exactly as §9 said.

The engine's own log makes the prefill/decoding split explicit. At c5 d32768:

```
Running: 2, Waiting: 3  ->  Running: 5, Waiting: 0
Avg prompt throughput: 3149.7 t/s   (on alternating 10 s ticks)
Avg generation throughput: 0.2-3.7 t/s
```

Aggregate wall prefill = 5 × 32768 / 126.7 s = **1293 t/s**, while the kernel's
reported prompt rate is **3149 t/s**. The kernel is ~2.4× faster than the cell
delivers because prefills are admitted in bursts and the slices between bursts
are near-idle. That is the throughput headroom the scheduler is leaving at
concurrency — and it is *prefill* headroom, not decode starvation.

### 10.2 Decisive: the cold deep prefill is COMPUTE-bound, not Engram-disk-bound

§9 listed the synchronous Engram disk stager as a candidate contributor. It is
not. `disk_isolate.py` sends two d32768 requests with the **identical corpus
body** (identical Engram n-gram rows) but **different fixed token-0** (both are
vLLM prefix-cache misses); the second re-reads rows the first just read:

| request | disk state | TTFT |
|--|--|--|
| cold | first read (host `drop_caches` first) | **24.10 s** |
| warm-disk | identical rows just read | **23.76 s** |

**ratio 0.99 → the disk read is not on the critical path.** The prefill is
compute-bound (sparse-MLA prefill + MoE over ~31.5K tokens at ~1300 t/s). This
closes §9's "Engram stager" candidate and demotes node-local Engram rows (E6) to
a pure *weight-load-time* follow-up (they would not move prefill latency).

### 10.3 §9 magnitudes corrected (mechanism unchanged)

- **§9's 63.1 s d32768 c1 cold TTFT is a different-boot outlier.** Same-boot
  repeats here are **24.1–24.5 s (< 2 % spread)**; the bench's own ctx-phase c1
  is 50.8 s and its serving-phase c1 is 54.4 s. The 63 s figure should not be
  quoted as the representative cost; ~24–50 s is the honest range at 32K and
  ~160 s at 100K. The *mechanism* (cold prefill is the whole story) is unaffected.
- **§9's "≈2.2× c1 win from `--long-prefill-token-threshold`" does not reproduce
  as a win** — see 10.4.

### 10.4 The one tuning A/B run: `--long-prefill-token-threshold 2048` — MIXED, not shipped

Boot B = the shipped recipe + `--long-prefill-token-threshold 2048`, same probes:

| cell | A (shipped, mnbt 8192) | B (lptt 2048) | B/A |
|--|--|--|--|
| d16384 c1 TTFT | 12.1 s | 15.4 s | 1.27 |
| d32768 c1 TTFT | **24.1 s** | **27.4 s** | 1.14 |
| d32768 c2 agg | 4.87 | 4.60 | 0.94 |
| d32768 c5 agg | 5.05 | **5.77** | 1.14 |

The cap does help aggregate prefill at high concurrency (engine log peaks at
9447 t/s; wall prefill 1477 vs 1293 t/s = 1.14×), but it costs **14–27 % on
single-stream** deep prefill: a 32K prefill flanked by decodes is split into 16
passes that re-read dense weights, and with no batch to amortise them that is a
net loss. **It is not a clean win → do not ship.** This supersedes §9.4's
c1-2.2× claim, whose baseline was the 63 s outlier boot.

**Optional arm, not the default.** For a workload that is *genuinely*
concurrent-cold (c≥5 deep prefills, no reuse), the flag can be passed one-off
without editing the recipe:

```bash
sparkrun run recipes/ds4/deepseek-v4.1-flash-exl3-tp4-1m-vllm.yaml \
  --cluster ds4tp4 -o extra_args="--long-prefill-token-threshold 2048"
```

It buys ~1.14× aggregate prefill at c5 and costs ~1.14× at c1; use it only when
the traffic shape is known to be batch-cold.

### 10.5 Why `tg t/s` at depth > 0 is unfixable by recipe tuning

`tg_throughput` (the §1 metric) = parseable decode-token timestamps / (last −
first). At `depth>0` the first token arrives after the cold prefill, but under
concurrency **later-arriving requests' first tokens pollute the window** —
measured directly: the c2 `tg_req` values are bimodal `[4.7, 26.9]` while the
window is shared. The metric is contaminated by prefill latency by construction.
No engine flag changes that; the fix is in the benchmark (see 10.6).

### 10.6 Two non-recipe fixes that do move the headline (out of this lane)

1. **Benchmark config.** The profile sets `prefix_caching: true`, which makes
   llama-benchy run the two-phase (context-load + serving) flow. Add `no_cache:
   true` (or set `prefix_caching: false`) so each cell is one cold request and
   the metrics are labelled honestly; and/or report the **ctx-phase `pp_throughput`
   / `ttfr`** (the true prefill rate and latency) instead of the `tg128` row at
   `depth>0`. Note the repo already documents this exact two-row trap in
   `benchmarking/README.md`; the triage's §1 read the serving row without the
   phase label.
2. **README two-number contract.** Publish **warm** (serving) and **cold
   (prefill)** numbers separately, each naming its harness. The shipped recipe
   serves long-context *warm* traffic at README-class rates (50.5 t/s at d32768
   c2 here); a *cold* deep prefill is ~1300 t/s on TP=4 and serialises under
   concurrency, so N cold deep requests need ~Σ(depth)/1300 s before their
   decodes are meaningful.

### 10.7 Bottom line for the recipes

**No recipe change is warranted on throughput grounds.** Verified this session:
- The recipe's decode is healthy; the bench "collapse" is cold prefill (§9, §10.1).
- The cold prefill is compute-bound, so the disk/Engram knobs cannot help (§10.2).
- The only scheduler knob tried (`lptt`) is a mixed result and is not shipped (§10.4).
- `mnbt 8192` (TP=4 native) already avoids the `max_num_scheduled_tokens=4096`
  warning the TP=6 arms log; nothing to change there.

The honest operating envelope stands: **long-context concurrent serving is
throughput-limited by cold-prefill cost and its serialisation; warm-prefix
long-context concurrency is healthy (≈51 t/s at 32K c2).** The t/s table should
name `spark-arena-v2` and say it serves a *warm* 2048-token prompt at `depth>0`.

Open follow-ups (need a profiler or the benchmark change, not more recipe boots):
(a) profile one compute-bound cold deep prefill (sparse-MLA prefill kernel vs
MoE) to see whether the ~1300 t/s has any headroom; (b) fix the profile/README
per §10.6; (c) re-test `lptt` only if a workload is genuinely concurrent-cold
(c≥5), never on a c1/realtime path.
