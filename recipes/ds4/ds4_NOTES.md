# ds4_NOTES — DeepSeek V4.1-Flash EXL3 lane: working record

Session log for `model_symbol=ds4`. Durable facts graduate into `AGENTS.md` and
`recipes/README.md`; this file is pruned. Read `AGENTS.md` first.

## Prior session (2026-09-27/28) — the `max_num_seqs=16` / `gmu 0.85` retune

Four recipes (`…exl3-{tp4,tp4-1m,tp6,tp6-1m}`) retuned to `max_num_seqs: 16`,
`gmu: 0.85`, capture ladder to 64; every arm booted as-shipped and measured.
Consolidated in **AGENTS.md §7.12** and the README table — **do not re-derive
here.** Headline: TP6-1M KV 15,034,010 tokens, C1/C4/C8/C16 = 43.4/72.7/110.2/149.1.

## This session (2026-10-01) — spark-arena-v2 long-context collapse

> **Later same day, mechanism RESOLVED — see "MECHANISM RESOLVED" at the bottom
> and `PERF-ISSUES.md` §9.** The collapse is a **cold deep prefill**, not decode
> starvation. The sections below are the chronological record.

**Objective:** the shipped TP6-1M recipe was benchmarked with
`sparkrun benchmark performance --profile spark-arena-v2` and "wildly
underperformed" vs the README t/s. Analyze from `/home/red/bench2` on `10.0.4.30`
and write solutions to `recipes/ds4/PERF-ISSUES.md`.

**Finding: the recipe is fine; the two numbers measure different things.**
- README's t/s come from a **short-prompt** concurrency harness
  (`.scratch/ds4/gmu/measure_arm.py`) — reproduced live today: **C1/C4/C8/C16 =
  33.8/64.1/99.6/131.9 t/s.** No fault at short context.
- spark-arena-v2 measures `pp=2048, tg=128` **at `depth` tokens and concurrency
  1–10 with `prefix_caching: true`.** The recipe **collapses at long context,
  c≥2**: decode agg 1–8 t/s at `d16384/32768/100000` vs ~35–45 at `c1` and the
  whole `65535` row. Non-monotonic in depth ⇒ a pathology, not a capacity curve.

**Two coupled symptoms, both only when a long-context request shares the engine
with concurrent work:**
1. **Starving step:** the engine admits 2 reqs (`Running: 2, Waiting: 0`, KV
   usage 1–2 %) but services one at **0.1–0.4 t/s** while the other runs at
   30–45 t/s. Aggregate decode falls to **1–2 t/s** from ~40. VERIFIED live.
2. **Intermittent `Mean acceptance length: 1.00`** (drafts 3, accepts 0) on the
   stalled request, recovering to ~2.7 once the working set drains. Correlated
   symptom, **not** the root cause (in the `mnbt=8192` boot acceptance was 3.00
   *while* generation was 0.2 t/s). This is the `vLLM #47930` shape the recipe
   body suspected.

**RULED OUT by live A/B on the failing cell (`d32768 c2`, truly-cold unique):**
- `max_num_batched_tokens` 4096→8192: collapse unchanged (agg 1.50); KV pool
  shrank 14,925,444 → 12,959,193 (−13 %).
- DSpark `k=3`→`k=1`: collapse unchanged (agg 1.89).
- Prefix-cache reuse: cold-unique prompts collapse exactly like warm ones.
So the cause is a **long-context DSpark decode-path / scheduler starvation**, not
spec width, step budget, or prefix caching. Next: profiler run on one node.

**Mechanism evidence (live 2026-10-01):**
- Cold 98.8K prefill at c1: TTFT **255 s** (≈390 t/s). Warm: **1.0 s**, decode
  44–55 t/s — long context is healthy once cached and alone.
- **2× cold 32.5K prompts:** one req 1.5 t/s, other 35 t/s; aggregate **1.55 t/s**.
  The benchmark's serialized TTFR staircase (161, 322, 483, … s at `c5 d100000`)
  is N× the single cold prefill.
- Prior `spark-arena-v2` run (`bench_fbc26cb5f73e`, 2026-09-25,
  `max_num_seqs=8`/`gmu 0.80`/**no DSpark**/patch-mod-only): **100000 healthy**
  (29–52 t/s); only 32768 collapsed. Sharper bisect arm than k value.

**Solutions written to `PERF-ISSUES.md`:** profiler run first (find the stall);
cheap falsifiers `--no-enable-prefix-caching`, `--enforce-eager`,
`--disable-chunked-prefill`, sparse-MLA autotune check; then document the
operating envelope if unfixable.

## Artifacts

- `.scratch/ds4/perf/` — the bench JSON/CSV/YAML, `probe_ttft.py` /
  `probe_longctx.py`, live probes (`probe-A..F.out`), `serve-oct1-live.log`,
  `measure_arm.py`, `run-k1.sh`, `repro-longctx.yaml`.
- `.scratch/ds4/perf2/` — **new this session**: `warm_cold.py` (the decisive
  warm-vs-cold probe; also copied to `red@10.0.4.30:~`), and the TP=4 1M boot logs
  (`tp4-1m.boot.log`, `tp4-1m-lptt.boot.log`).
- `recipes/ds4/PERF-ISSUES.md` — the deliverable (§9 is the resolution).

## Process notes (new, worth keeping)

- `sparkrun benchmark performance --profile <name>` resolves the profile from the
  registry cache (`~/.cache/sparkrun/registries/<reg>/benchmarking/`), **not**
  `benchmarking/` of the working tree; `boot-check` is not in the littlecedar
  registry (its `benchmarking/` has only deep-smoke/fast-smoke/triage-smoke).
- The `sparkrun run`/`benchmark` container is ephemeral; `docker logs` is empty
  and the serve log lives at `/tmp/sparkrun_serve.log` **inside** the container.
  Read it with `docker exec <ctr> cat`. Containers are reaped after a run, so
  capture artifacts before finishing.
- `docker ps` on the head node shows only `…_node_0`; the other five ranks run on
  the peer nodes under the same deterministic cluster id.
- `rtk ssh` with a multi-line command containing parens breaks the remote shell;
  keep remote one-liners paren-free.


## Follow-up to the 2026-10-01 long-context collapse triage (2026-10-01, ds4)

The triage agent finished `PERF-ISSUES.md` and handed off to the solutions agent.
This session added a second, independent pass over the triage's own benchmark
artifact — `.scratch/ds4/perf/benchmark_deepseek-v4.1-flash-exl3-tp6-1m-vllm_spark-arena-v2_tp6.csv`
(the JSON copy at `.scratch/ds4/perf/benchmark_*.json` — it is the `--output` file,
so the `bench_*/runs/` scratch dir it names may be gone, but this file is durable).
**Goal: re-derive the served-decode numbers by hand and check them against the
triage's §1 table.** The triage §1 table (e.g. d32768 c1/c2/c5/c10 = 36.1/5.3/3.1/2.7)
now reproduces to 0.1 t/s.

### Reconciliation of the phase labels (kept — the table-reading rule)
Each bench cell has **two** phases: `ctx_pp`/`ctx_tg` (context-load, Phase A) and
`pp2048`/`tg128` (serving, Phase B). The triage §1 table is the **serving `tg128`
aggregate**; the re-derivation reproduced it to 0.1 t/s (e.g. d32768 c1/c2/c5/c10 =
36.1/5.2/3.1/2.7; d65535 = 34.4/29.9/32.1/33.5). **Superseded interpretation:** the
non-monotonic depth signature was read as a scheduling/spec-decode pathology; §9
shows it is the warm-vs-cold serving-prefill split (d65535's serving prompt was a
prefix hit; its context-load phase is still collapsed). See `PERF-ISSUES.md` §9.

### Superseded A/B list
The earlier "ready-to-run A/B + profiler" list (`--no-enable-prefix-caching`,
`--enforce-eager`, k=1, `--disable-chunked-prefill`) is **superseded** by §9: the
target is now the *cold deep prefill*, not the decode path. Keep only
`--no-enable-prefix-caching` (as a positive control that should make serving
*slower*) and the cold-prefill profiler run.


## Update 2026-10-01 — TP=4 1M reproduces (now VERIFIED live)

`deepseek-v4.1-flash-exl3-tp4-1m-vllm` was booted live this session on `ds4tp4`
and reproduces the cold-prefill collapse (d32768 c2 cold = 4.76 t/s; warm = 51.2).
So the fault is **not TP=6-specific**. Knob differences between the 1M arms
(TP=6: hf_overrides 96/12 virtual heads, mnbt 4096, KV 14.93M; TP=4: none, mnbt
8192, KV ~5.96M) mean the fault is not a function of TP degree, padding, mnbt, or
pool size. `mnbt` 4096-vs-8192 independently re-corroborates triage §3A. `ds4tp4`
(4 workers, head free) is the cheap iteration cluster; no TP-degree bisect needed.

The two 1M recipes are **not** "identical except max_model_len" with each other —
that lockstep guard is 1M-vs-300K *within* a TP degree.


## Session 2026-10-01 (cont.) — MECHANISM RESOLVED (TP=4 1M live A/B)

**Headline: the collapse is the cost of a COLD deep prefill, not a decode bug and
not a capacity curve. Warm long-context concurrency is healthy.**
Full write-up: `PERF-ISSUES.md` §9.

Decisive experiment (`warm_cold.py`, `.scratch/ds4/perf2/`; booted
`…exl3-tp4-1m-vllm` as-shipped on cluster `ds4tp4`, head `.32`, head `.30` left
free). Same serving shape as spark-arena-v2, one variable flipped (prefix primed
or not):

| cell | mode | TTFT | decode | aggregate |
|:--|:--|--:|:--|--:|
| d32768 c1 | cold-unique | **63.1 s** | 33.5 t/s | 1.9 |
| d32768 c1 | warm | **0.4 s** | 37.6 t/s | 33.5 |
| d32768 c2 | cold | 25/49 s | 4.5/26.5 | 4.8 |
| d32768 c2 | **warm** | 0.8/0.4 s | 30.4/27.9 | **51.2** |
| d65535 c1 | warm | 0.6 s | 34.7 | 29.9 |

- **Warm long-context concurrency = 51 t/s** (bench reported 5.2). The recipe is
  fine; spark-arena-v2's serving row at `depth>0` mostly measures a cold prefill.
- **Why the bench numbers look like starvation:** llama-benchy's serving `ttfr` is
  the FULL prefill time and `tg_throughput` starts at the first token, so a cold
  serving prefill inflates TTFT (d32768 c1 = 54 s) and pollutes the decode rate.
  Server log during c5 cold: `Running: 4–5, Waiting: 0–1`, `prompt throughput ≈
  3182 t/s` ticking, `generation ≈ 0.6 t/s` — a prefill is running, the decodes
  wait. That is the triage's "one req 0.1–0.4 t/s" symptom.
- **Non-monotonic depth = cache-hit lottery, not capacity.** d65535's serving
  prompt happened to be a prefix hit (its *context-load* phase is still collapsed:
  ctx_tg 2.55, ctx TTFT 103 s). d32768/100000 missed → cold serving prefill.
  **The corpus (~150K tok) does NOT repeat at these depths** (I earlier wrote that
  it did — wrong; retracted). I did not pin the exact hash/alignment hit condition;
  the warm/cold A/B settles the mechanism without it.
- **`--long-prefill-token-threshold 2048` — TESTED, partial.** Fresh TP=4 1M boot
  with the flag: d32768 c1 cold TTFT **63→28.5 s** (chunked deep prefill is ~2×
  faster than a monolithic 32K chunk), but d32768 c5 cold agg decode 5.0→**5.8**.
  Five cold 32K prefills are ~164K tokens of irreducible prefill work; capping the
  chunk speeds each prefill but cannot remove the work. Cheap prefill win, not the
  collapse fix.

**Boot-log facts (VERIFIED):**
- TP=4 1M boots with **no `hf_overrides`** and KV **5,955,167 tok** (shipped);
  5,801,712 with the long-prefill flag. Same autotune/`tactic=-1` lines as TP=6.
- FlashInfer sparse-MLA decode autotune **loads cached configs** (TP=6: 140;
  TP=4: 35→147 after re-autotune) — does not tune fresh; deep shapes may miss.
- `mxfp8_gemm`: "No tuned config covers … falling back to
  CutlassMxfp8GemmRunner tactic=-1" for rows 64/32/16/8 (graph-capture sizes).
- Engram disk stager (`engram.py EngramDiskStager.stage`) gathers+preads
  **synchronously inside `prepare_inputs`** every step (shared 32-thread pool).
  Candidate contributor to the per-step prefill cost — not yet isolated.

**Upstream (VERIFIED via GitHub):** #57413 + #50497 (V1 no cap on concurrent
partial prefills; MLA chunked-context schedule batch-column shaped) is the best
mechanistic fit. #47930/#47926 (DSpark acceptance collapse on shared prefixes) is
the acceptance symptom. #53600/#53605 (sparse-MLA decode autotune misses
`extra_topk` 256/384 → tactic=-1) is a smaller depth-keyed effect. #49369 (DSpark
can halve throughput at healthy acceptance). #56771/#55757 (SM120 sparse-MLA
prefill IMA / `sparse_mla_force_mqa`). #40969 (GB10 hang, FULL_AND_PIECEWISE).
`vllm-tune` tunes Triton MoE + fp8_w8a8 GEMM only — cannot reach sparse MLA.

**Open / next (solutions agent):** (a) whether a per-request prefill cap can be
made to interleave (vLLM #57413 is open); (b) profile one cold deep prefill
(sparse-MLA prefill vs Engram stager vs scheduler); (c) fix the bench profile
(`--no-cache`, or report prefill/decode separately, or use a fixed prompt set);
(d) document the operating envelope: long-context **warm** = README-class, cold
deep prefill = 30–160 s each and serializes under concurrency.


## Session 2026-10-01 (cont.) — SOLUTIONS: mechanism confirmed, no recipe change

**Two live TP=4 1M boots on `ds4tp4`** (head `.32`, `.30` free). Full write-up
`PERF-ISSUES.md` §10; raw `.scratch/ds4/perf3/`. Headline: **the recipe is
healthy; `spark-arena-v2` at `depth>0` measures cold prefill; no tuning knob
gives a clean win.**

- **Mechanism confirmed** (`depth_ttft.py`): d32768 c1 cold TTFT **24.1–24.5 s**
  (3 same-boot reps, <2 % spread); c2 agg **4.87** (bench 5.2) reproduces; c5 agg
  5.05. Decode is healthy: **warm d32768 c2 = 50.5 t/s**. Engine log: `prompt
  throughput 3149.7 t/s` in bursts, agg wall prefill 1293 t/s → **~2.4× prefill
  headroom the scheduler leaves at concurrency**; gen throughput 0.2–3.7 while
  prefills run.
- **DECISIVE — prefill is compute-bound, NOT Engram-disk-bound**
  (`disk_isolate.py`): identical corpus body (same disk rows), different token-0
  (both prefix misses) → cold-disk TTFT **24.10 s** vs disk-warm **23.76 s**,
  **ratio 0.99**. Closes §9's Engram-stager candidate; demotes E6 node-local rows
  to a weight-load-time follow-up.
- **§9 magnitude corrected:** the 63.1 s d32768 c1 figure is a different-boot
  outlier; same-boot is 24.1–24.5 s. Mechanism unaffected.
- **Tuning A/B — `--long-prefill-token-threshold 2048`: MIXED → NOT shipped.**
  c5 agg 5.05→5.77 (1.14×) but c1 TTFT 24.1→27.4 s (1.14× *worse*), c2 0.94.
  Supersedes §9.4's "2.2× c1 win". No recipe change.
- **Metric caveat:** `tg t/s` at `depth>0` is polluted by prefill latency (c2
  `tg_req` is bimodal `[4.7, 26.9]` in a shared window). The real fixes are in
  the benchmark profile (`no_cache: true`, or report prefill separately) and the
  README (publish warm vs cold, name the harness) — already documented in
  `benchmarking/README.md`; triage §1 read the serving row without the phase label.
- **Recipe verdict unchanged:** no throughput-motivated edit. Envelope: warm
  long-ctx concurrency ≈51 t/s @32K c2; cold deep prefill ~1300 t/s @TP4 and
  serialises (N requests need ~Σdepth/1300 s before decode matters).


## Session 2026-10-02 — NEW SECOND LANE: knapcio DSV41 SGLang (TP=4, native MXFP4)

**Objective this session:** integrate
`github.com/knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4` (SGLang, native
checkpoint, DSpark, Engram-on-NVMe) into this registry. Full provenance/plan:
**`recipes/ds4/KNAPCIO-SGLANG-INTEGRATION.md`**. Recipe:
`deepseek-v4.1-flash-sglang-tp4-knapcio.yaml`; mod: `mods/dsv41-sglang-overlay/`.

Why a new lane at all: it runs the **official** checkpoint (comparator for the
EXL3 94.4% hard-tier question, AGENTS.md E5) and upstream measures **89.7 t/s
prose c1** (~2× our vLLM EXL3 lane) from the b12x kernels + DSpark.

**The old "SGLang is a dead end" verdict is superseded for a purpose-built image.**
The prior blockers were real *for published images*: no single image was both
V4.1 and b12x; the MXFP4-Cutlass MoE rejects `2304/4 = 576` (needs a multiple of
128). Both are solved here — the repo builds `dsv41-4x-spark:canary-roce`
(dsv4.1 branch + adapter overlay + b12x_next; built on all four nodes, internet
works), and **`EP_SIZE=2`** gives `2304/2 = 1152 = 9×128`. `EP_SIZE=1` is the
upstream production line (b12x_next), a follow-up A/B.

**Feasibility verified this session:**
- The **native checkpoints are already in the shared HF cache**: `deepseek-ai/DeepSeek-V4.1-Flash`
  (snapshot `dba1be0a40aa45a94ad051997016db3960a90277`, 510.30 GB, 48 shards) and
  `deepseek-ai/DeepSeek-V4-Flash-0731`. `lmsysorg/sglang:dev-dsv41` (33.2 GB) is present.
- **Engram packs built on all four nodes**: `pack_engram.py --rank R --tp 4`,
  ~47 GiB/node at `/home/red/dsv41-engram/`. Mount the **whole `hub/` dir** — this
  cache uses the two-level `hub/blobs/<xx>/<sha>` layout, so mounting only the
  `models--…` dir leaves every blob symlink dangling.
- **Fabric is full-mesh, not a ring**: two RoCE planes (192.168.0.0/24 on
  `rocep1s0f0`, 192.168.1.0/24 on `roceP2p1s0f0`), all six pairwise pings OK,
  port 1 ACTIVE (port 2 DOWN — do not use `*s0f1`), **RoCEv2 GID index 3**.
  So the switchless-ring path is not needed.

**EP_SIZE: use 1, not 2.** EP=2 *loads* (2304/2 = 1152 = 9×128, clearing the
MXFP4-MoE `%128` check) but **dies at the first decode plan**:
`dsv41-moe-E192-N1152-k6-M5 failed to prepare … planned dynamic direct routing is
unsupported for this launch shape`. `adapter/moe_b12x_next.py` states it plainly:
"the production profile is EP_SIZE=1, EP>1 is an A/B setup". All measured numbers
below are EP=1.

**Sparkrun wiring (the load-bearing bits):**
- The image's entrypoint is `boot.py`, which builds the whole `sglang.launch_server`
  argv from env. sparkrun appends `--dist-init-addr/--nnodes/--node-rank` to the
  command assuming `sglang serve`. The mod's `launcher.py` consumes those and
  maps them onto `DIST_INIT_ADDR`/`NNODES`/`NODE_RANK`/`SERVER_PORT`, then execs
  `boot.py`. The recipe `command:` is a one-line call to the shim.
- A **local-only image is not distributable**: `sparkrun run` pulls it from a
  registry unless the recipe sets **`distribution_config.containers.enabled: false`**
  (the top-level key is `distribution_config`, NOT `distribution`). Also
  `executor_config.volumes` is a **list of `host:container` strings**, not a dict.
- `/state` must be bind-mounted writable (boot.py writes `launch.json`); the image's
  `/state` is not writable as the sparkrun user.
- Rootless sparkrun already grants `IPC_LOCK`, `memlock=-1`, `/dev/infiniband`,
  `shm_size 32gb` — so no `privileged`/`cap_add`/`user` override is needed.

**Measured (boot #4/#5 this session; bench `.scratch/ds4/knapcio/bench_sglang.py`,
two discarded warm-ups, non-streaming 200-token, distinct prompts, greedy):**

| t/s aggregate | C1 | C4 | C8 | C16 |
|:--|--:|--:|--:|--:|
| NCCL only (boot #4) | 27.4 | 62.5 | 73.2 | 155.0 |
| **+ RoCEnante (boot #5, SHIPPED)** | **46.6** | **105.6** | **132.5** | **191.0** |
| upstream v2.3 (their fabric/clock) | 89.7 | 165.9 | 244.6 | 357.2 |

**RoCEnante is the single biggest win this session: 1.70×/1.69×/1.81×/1.23× over
NCCL**, far beyond the 7–25% GB10 inter-boot spread. **C1 46.6 beats our shipped
vLLM/EXL3 TP=4 lane (40.7) on the same four nodes.** Boot log:
`RoCEnante ready: world=4 hcas=rocep1s0f0,roceP2p1s0f0 gid_index=3
max_size=2097152`. Correctness smoke `27*43 -> 1161`, planets correct; DSpark
acceptance 2.4–2.8 unchanged. Rollback is one env line (`SGLANG_ROCE_ALLREDUCE=0`).

**Remaining gap to upstream 89.7 c1 (~2×):** the **SPS table** (ragged/compact
verify; upstream: without it "the planner falls back to verify-all and the whole
thing is a no-op"). Boot #6 is generating it in-image with
`python3 -m sglang.benchmark.dspark_sps_profiler all --out /state/dspark_sps.json`
against a server booted with `SGLANG_RAGGED_VERIFY_MODE=static
SGLANG_DSPARK_ENABLE_SPS_RECORD=1`. Table must be present on every node. Also
unaccounted: upstream runs a 2200 MHz clock cap convention (we are uncapped), and
their fabric/clock differ. **89.7 remains a port, not our measurement.**
