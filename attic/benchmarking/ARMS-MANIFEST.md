# `attic/benchmarking/` — archived llama-benchy profiles

**What this is.** The llama-benchy measurement profiles that were sitting untracked in
`benchmarking/` and are **not part of the curated library documented in `benchmarking/README.md`**.
They are single-use experiment arms: each answered one question in the qwen4 (Qwen3.8-Flash-Next) or
qwen3 (Qwen-3.8-27B DFlash) optimization campaigns, and each is referenced only from the ephemeral
`.scratch/qwen3-27b/run_phase*.sh` / `.scratch/q4/launch*.sh` scripts, never from a tracked recipe,
tool, or test. Several are explicit replications or order-reversed twins of a kept profile — the
`speed = f(profile)` convention in `benchmarking/README.md` requires a new filename per replication,
which is *why* so many near-duplicates accumulated.

**Why they are here, not in `benchmarking/`.** `benchmarking/` is git-distributed to nodes and third
parties. 121 of its 126 files were untracked; the whole directory read as a live library when it was
mostly the settled debris of two finished campaigns, which is a hazard to the next reader. The
curated set stays; the rest are archived here, **tracked**, so a `bench_*` id that cites one still
resolves. This mirrors the `attic/ds4` and `attic/qwen4` convention.

**Archive criterion (mechanical, verified 2026-10-04).** A profile was moved iff it is **none** of:
* git-tracked,
* named by `benchmarking/README.md` (its curated list — the author's own "these are the library" line),
* named by any tracked file outside `benchmarking/`.

Nothing in `recipes/`, `benchmarking/`, `tools/`, or `tests/` resolves these by directory glob, so a
move breaks no consumer. **All 125 profiles (47 kept + 78 here) load through sparkrun's own
`BenchmarkSpec.load`** (checked 2026-10-04), including after redaction.

**Redaction.** Every profile here was scanned and had internal IPs / hostnames / operator paths
replaced with role placeholders (`node-free-1`, `node-restricted-2`, `the head node`, `/home/<user>/…`)
before being placed in the tracked tree — `attic/` is distributed, and internal addresses must not
enter tracked files (root `AGENTS.md`). The measurement content is unchanged; only the addresses are.
**One file was renamed on archive:** a profile whose filename was a persisted redaction token
(a 37-char hash-like string — the same class of bug `benchmarking/README.md` records for
`bs8-only.yaml`) is now `depth-cost-separation-qwen3.8-27b-dflash.yaml`, named from its own
`metadata.description`.

## Manifest

| profile | referenced from | what it asked |
|---|---|---|

| `a2-d1024.yaml` | qwen3 scratch | Item A2 low-pressure half of the interleaved pair. c=8 only, 8k-class prompt. Run it ALTERNATING with a2-d8192.yaml on one already-booted server (--sk |
| `a2-d8192.yaml` | qwen3 scratch | Item A2 high-pressure half. c=8 only, 8192 context. Run it ALTERNATING with a2-d1024.yaml on one already-booted server (--skip-run, zero boots). Full  |
| `accept-depth-c2.yaml` | qwen3 scratch | Depth-vs-acceptance at c=2, to raise the precision of an instrument that currently cannot resolve its own question. Nothing here is a new claim: it is |
| `admission-k20-cap24-gauge.yaml` | no-ref scratch | k=16/20 at the SHIPPED max_num_seqs (24) on labquant, instrumented. Second k<cap control for §19l, and the first capture of spec_accept_rate. Control  |
| `batch-depth-grid-v2.yaml` | qwen3 scratch | Non-degenerate (batch, depth) grid for qwen3.8-27b, designed to fix the two specific weaknesses in phase 44's grid. One boot, then 15 cells at zero ad |
| `batch-depth-grid.yaml` | qwen3 scratch | Non-degenerate (c, depth) grid to separate a KV-byte cost from a per-sequence cost. Section 12.28 shows why this specific shape is needed: holding c*( |
| `bs-transition-16-23.yaml` | qwen4 scratch | Fills the unmeasured k=17..23 interval for the RadixArk bs curve. k=16 is an in-boot anchor (must reproduce 86.86) and k=20/21/22/23 localise whether  |
| `cache-control-d1024.yaml` | qwen3 scratch | VALID prefix-cache eviction control. The previous attempt (same-boot-concurrency-d0.yaml, depth 0) was INERT and its result must not be quoted: llama- |
| `cache-control-d2048.yaml` | qwen3 scratch | VALID prefix-cache eviction control. The previous attempt (same-boot-concurrency-d0.yaml) was inert: llama-benchy only warms the radix cache when `dep |
| `cap20-k16-k20-gauge.yaml` | qwen4 scratch | Test of `run = min(k, cap-1)` at a second cap. cap=20 (override) with concurrency [16, 20]: k=16 is a non-binding internal control predicted to reach  |
| `cap20-lq-gauge2.yaml` | qwen4 scratch | Labquant at max_num_seqs=20 with concurrency [16, 20], second attempt at the gauge capture lost to the shared-/tmp collision. k=16 is the non-binding  |
| `composition-pair-reversed.yaml` | qwen3 scratch | ORDER-REVERSED twin of benchmarking/composition-pair.yaml. Same two cells, opposite sweep order, so that a gap which reproduces cannot be attributed t |
| `composition-pair.yaml` | qwen3 scratch | REPLICATE a 26 % step-time difference that appeared at MATCHED byte count inside a single boot, and decide whether it is real. THE OBSERVATION. Phase  |
| `cps16384-k8-16-24.yaml` | qwen4 scratch | chunked_prefill_size=16384 -> a single prefill chunk per 10,240-token request. Tests whether the k=24 recovery from cps 4096 -> 8192 continues (step c |
| `cps5120-boot7.yaml` | qwen4 scratch | labquant, cps=5120, k=16 only, metrics-FREE. SEVENTH boot at this cell, bought for the distribution question rather than the mechanism question: outli |
| `cps5120-cleanhost-falsifier.yaml` | no-ref scratch | labquant, cps=5120, k=16 only, metrics-FREE, run at least two hours away from the 2026-09-22 02:45-05:16 window. Settles whether the §19h/§19i cps tro |
| `cps5120-lowmem-manipulation.yaml` | qwen4 scratch | labquant, cps=5120, k=16 only, metrics-FREE, with host MemAvailable pinned into the low mode (~5 GB) DURING the timed window by mem_holder.py. Manipul |
| `cps5120-outside-window.yaml` | qwen4 scratch | labquant, cps=5120, k=16 only, metrics-FREE, run at least two hours away from the 2026-09-22 02:45-05:16 window. Settles whether the §19h/§19i cps tro |
| `cps5120-outwindow-rep.yaml` | qwen4 scratch | labquant, cps=5120, k=16 only, metrics-FREE, run at least two hours away from the 2026-09-22 02:45-05:16 window. Settles whether the §19h/§19i cps tro |
| `cps8192-cap32-pool112-replicate.yaml` | no-ref scratch | REPLICATION of cps=8192 + max_num_seqs=32 at the mamba pool's SHIPPED value (112), for the k=24 cell only. Byte-equivalent args to cps8192-cap32-rerun |
| `cps8192-cap32-rerun-cleanhost.yaml` | qwen4 scratch | cps=8192 with max_num_seqs=32, k=16 (anchor) / 20 / 24. Tests whether the residual −19.4% at k=24 is the remaining `k == cap` penalty, which would mak |
| `cps8192-cap32.yaml` | qwen4 scratch | cps=8192 with max_num_seqs=32, k=16 (anchor) / 20 / 24. Tests whether the residual −19.4% at k=24 is the remaining `k == cap` penalty, which would mak |
| `d0-cps8192-16384.yaml` | no-ref scratch | d=0 with chunked_prefill_size 8192 and 16384, k=8/16/24. Separates the per-step prefill budget (H1, predicts degradation at d=0) from many-long-cached |
| `d0-cps8192.yaml` | no-ref scratch | d=0 with chunked_prefill_size 8192, k=8/16/24. Second treatment point for the depth-dependent sign of the cps effect. Control: d=0 arm of bench_371a7b |
| `d0-weight-coefficient.yaml` | qwen3 scratch | qwen3.8-27b depth-0 baseline, for pinning the weight-read coefficient `a` with no depth term present. Updated 2026-09-21: **this profile cannot do the |
| `d4-r12-capacity.yaml` | qwen3 scratch | THE DOCUMENTED FIRST-PRIORITY UNTESTED CAPACITY CELL: `speculative_draft_tokens = 4` with `mamba_full_memory_ratio = 1.2`, measured against the shippe |
| `d8-r12-pool-pressure.yaml` | qwen3 scratch | POOL-PRESSURE cell: does running the token pool at ~100 % occupancy cost throughput beyond the stream count it permits? One factor changed from the sh |
| `depth-cost-separation-qwen3.8-27b-dflash.yaml` | no-ref scratch | SEPARATES THE TWO DEPTH COSTS for the qwen3.8-27b DFlash recipe: prefill work admitted per unit of generated output (section 12.23) and KV bytes read  |
| `depth-descending-replicate.yaml` | qwen3 scratch | ORDER-REVERSED replication of §12.33's depth sweep, run with --skip-run against the live container so it costs ZERO boots. §12.33 swept `depth` ASCEND |
| `depth-linearity-grid.yaml` | qwen3 scratch | Depth-linearity grid: enough DISTINCT DEPTHS, each with enough batch sizes, to test whether the depth penalty is linear in `c x depth`. This is the te |
| `depth-scaling-c8.yaml` | qwen3 scratch | Per-stream decode throughput as a function of CONTEXT LENGTH at FIXED batch (c = 8). This exists to turn an unexplained number into a shape. WORK.md 1 |
| `depth-slope-decode-metric-desc.yaml` | qwen3 scratch | DEPTH sweep scored on the server's OWN decode metric, to test whether the depth penalty survives after removing prefill contamination from the measure |
| `depth-sweep-c4-desc.yaml` | qwen3 scratch | p72 REPEATED with the depth order REVERSED. Same profile parameters as benchmarking/depth-sweep-c4.yaml — `pp` 1024, `tg` 1024, `c` 4, five depths, ru |
| `depth-sweep-c4.yaml` | qwen3 scratch | Wide DEPTH sweep at fixed `pp`, to fix a conditioning problem that §12.47 identified and that MORE RUNS CANNOT FIX. `depth` is llama-benchy's GENERATE |
| `discrim-replicate.yaml` | other scratch | Third replicate of the single cell d=8192 / pp=1024 / c=8, the discriminator cell of DEPTH-COST.md section 12.45. Zero boots: run with --skip-run --no |
| `instr-cap32-cps8192-k24-k32.yaml` | qwen4 scratch | Instrumented k=24 and k=32 on zz-rk-metrics with BOTH max_num_seqs=32 and chunked_prefill_size=8192 overridden, so the scheduler state behind §19o's c |
| `instr-depth2048-cap32-k32.yaml` | no-ref scratch | Depth-vs-slots discriminator for the running-batch ceiling. Lazy strategy, cap 32, cps 8192, k=32, depth 2048 (vs the reference boot's 8192). Mamba st |
| `instr-k24-admission-fork.yaml` | qwen4 scratch | Instrumented k=16 (internal control, must reproduce 16.00) and k=24 (the question) on zz-lq-metrics, run once per cps value at 4096 and 8192. Decides  |
| `instr-mamba-k-ladder.yaml` | no-ref scratch | Gauge-only concurrency ladder (k = 1,4,8,12,16,20,24) at d=8192 on zz-lq-metrics, to record mamba_usage directly for the first time. Decides whether t |
| `instr-mambapool-140-k32.yaml` | no-ref scratch | Causal test of §19u's ceiling rule. `max_mamba_cache_size` 112 -> 140 (never varied in this project until now), everything else identical to bench_8dd |
| `instr-nonlazy-cap32-k24k32.yaml` | no-ref scratch | §19t's causal test re-run with matched cell history: non-lazy mamba_radix_cache_strategy at concurrency [24, 32] under cap 32 / cps 8192, compared aga |
| `instr-nonlazy-cap32-k32.yaml` | qwen4 scratch | Causal test for §19s on zz-rk-metrics: is the running-batch ceiling caused by LAZILY RETAINED cache? Requires `-o mamba_radix_cache_strategy=extra_buf |
| `ladder-at-depth8k.yaml` | qwen3 scratch | Ranks the (D, ratio) capacity ladder at depth 8192 against the shipped config, in ONE concurrency point that separates all three rungs. Concurrency wa |
| `lq-cap32-k16-20-24.yaml` | qwen4 scratch | labquant under max_num_seqs=32, concurrency 16/20/24. Tests whether raising the cap lets the faster checkpoint exceed its 91.38 peak at bs=16 — a cand |
| `lq-cap32-retry-k16-24.yaml` | no-ref scratch | labquant with max_num_seqs=32 (vs the shipped 24) at d=8192, k=16 and k=24, n=7. Tests the withdrawn cap-32 claim on the shipping checkpoint and, more |
| `lq-cps-scan-k16.yaml` | qwen4 scratch | labquant at k=16 only, d=8192, n=7, for a chunked_prefill_size scan at the shipping serving point. Launch once per value: -o chunked_prefill_size=6144 |
| `lq-cps5120-k8-16-24-rep2.yaml` | no-ref scratch | Replication of cps=5120 on labquant, k=8/16/24 at d=8192, n=7. Second boot of the same condition as bench_d91021cb067c, poolable with it. Requires -o  |
| `lq-cps5120-k8-16-24.yaml` | no-ref scratch | labquant at chunked_prefill_size=5120, k=8/16/24, d=8192, shipping recipe (graphs off). Discriminates whether labquant's regression at cps=8192 is cau |
| `lq-cps8192-k8-16-24.yaml` | qwen4 scratch | labquant at chunked_prefill_size=8192, k=8/16/24, d=8192. Transfer test for §19c's only surviving recipe change, on the checkpoint we would actually s |
| `lq-ctl2-repeat.yaml` | no-ref scratch | labquant past bs=8, matched cell-for-cell to §19's RadixArk sweep. Answers where labquant's aggregate peak sits and whether its cliff is at the same c |
| `matched-b-depth.yaml` | qwen3 scratch | Matched-concurrency depth comparison, designed to be run against an ALREADY-BOOTED server with --skip-run (zero boots). WHY THESE EXACT CONCURRENCY VA |
| `mpt32768-cps8192-k8.yaml` | qwen4 scratch | Single cell, d=8192 k=8, cps=8192 + --max-prefill-tokens 32768 on RadixArk. Decides whether the k=8 TTFT floor rise attributed to chunk width is reall |
| `mpt32768-cps8192.yaml` | qwen4 scratch | Raises the per-step prefill token budget itself (--max-prefill-tokens 32768) at chunked_prefill_size=8192, to test whether the budget rather than the  |
| `mpt32768-k8-16-24.yaml` | no-ref scratch | max_prefill_tokens=32768 (vs the SGLang default 16384) at d=8192, k=8/16/24. Tests whether the scheduler's prefill budget per step -- as opposed to th |
| `pool-matched-c4-d8192-pp2048.yaml` | no-ref scratch | Cell 1 of 2 of the pool-matched pair (see pool-matched-pair.yaml for the full rationale and the pre-registered predictions). One cell per profile ON P |
| `pool-matched-c8-d4096-pp1024.yaml` | no-ref scratch | Cell 2 of 2 of the pool-matched pair (see pool-matched-pair.yaml for the full rationale and the pre-registered predictions). One cell per profile ON P |
| `pool-matched-pair.yaml` | qwen3 scratch | THE POOL-MATCHED PAIR: two cells with IDENTICAL c*depth and IDENTICAL pool demand, differing only in batch size and prompt length. Arbitrates the last |
| `pp-depth-complete.yaml` | qwen3 scratch | Completes the p66/p67 grid and replicates p67 across a NODE, in ONE boot. p66 measured (1024,1024) (4096,1024) (1024,4096) (4096,4096) and p67 added ( |
| `pp-vs-resident-discriminator.yaml` | other scratch | ONE cell, chosen to break the confound that p66 left open: is the ~25 % decode-speed step driven by PROMPT length (`pp`) or by the number of tokens re |
| `prefill-chunk-1024.yaml` | qwen4 scratch | Tests whether shrinking --chunked-prefill-size from the shipping 4096 recovers the k=24 collapse that §19a attributes to prefill work. Requires -o chu |
| `prefill-chunk-8192-rep.yaml` | qwen4 scratch | Replication of the cps=8192 k=24 recovery, in an independent boot. k=16 is the anchor (must reproduce ~88), k=24 is the claim. Requires -o chunked_pre |
| `prefill-chunk-8192-rep2.yaml` | no-ref scratch | Third independent boot of chunked_prefill_size=8192 (k=8/16/24) to gate the only recipe candidate that survived falsification. Own profile file so the |
| `prefill-chunk-8192.yaml` | qwen4 scratch | chunked_prefill_size=8192 vs the shipping 4096, at d=8192 k=8/16/24. Tests whether admitting larger prefill chunks recovers the high-concurrency prefi |
| `prefill-contention-d0-vs-d8192.yaml` | qwen4+qwen3 scratch | d=0 (no prefill) vs d=8192 at k=8/16/24, same boot, to test whether the bs>16 decline is prefill contention. d=8192 is the in-boot control and must re |
| `prefill-split-held-sum.yaml` | no-ref scratch | HOLD depth+pp CONSTANT AND VARY THE SPLIT: separates "total resident sequence drives the prefill-admission queue" from "prompt length drives it" from  |
| `prompt-vs-generate-within-boot.yaml` | qwen3 scratch | WITHIN-BOOT test of whether speculative acceptance depends on PROMPT length or on GENERATED length, at matched batch AND matched pool occupancy. Zero  |
| `q0-d1024.yaml` | qwen3 scratch | Q0 (WORK.md 12.23): is the depth-2048 throughput bump real, or blocked-run drift? Phase 38 measured per-stream decode at c=8 on ONE boot, depths run i |
| `q0-d2048.yaml` | qwen3 scratch | Q0 (WORK.md 12.23): is the depth-2048 throughput bump real, or blocked-run drift? Phase 38 measured per-stream decode at c=8 on ONE boot, depths run i |
| `ratio16k-abba-decodemetric.yaml` | qwen3 scratch | SAME-NODE ABBA replication of the 16k ratio comparison, using the harness's own decode-phase metric instead of a hand-rolled load generator. This repl |
| `reuse-vs-depth8192.yaml` | qwen3 scratch | Dose-response arm paired with cache-control-d1024.yaml. Same node, same booted server, same c sequence; only `depth` differs. At depth 8192 with the s |
| `reverse-order-replicate.yaml` | qwen3 scratch | ORDER-REVERSED replicate of p59, run against the SAME live container with --skip-run so it costs zero boots. p59 swept pp ASCENDING (1024 -> 16384) wi |
| `rk-cutlass-bs-sweep-high.yaml` | qwen4 scratch | RadixArk + flashinfer_cutlass + prefill-graph-disabled, bs 8/12/16/24 — the matched comparator for the labquant bs>8 sweep. Requires -o extra_args="-- |
| `rk-lqflags-cps8192.yaml` | qwen4 scratch | RadixArk with labquant's exact extra_args (--moe-runner-backend flashinfer_cutlass --cuda-graph-backend-prefill disabled) at chunked_prefill_size=8192 |
| `same-boot-concurrency-16k.yaml` | qwen3 scratch | Same-BOOT aggregate-vs-offered-concurrency curve at depth 16384, with a repeated point to measure drift. Costs ZERO boots: run it with --skip-run agai |
| `same-boot-concurrency-d0.yaml` | qwen3 scratch | Depth-0 twin of same-boot-concurrency-16k.yaml, used as the CONTROL for the prefix-cache hit-rate collapse measured in phase 28. At depth 16384 the pr |
| `slot-bound-branch.yaml` | other scratch | Tests whether only the min() matters, or whether WHICH constraint binds also matters. Two configs reach the same 8k capacity by opposite routes: shipp |
| `symmetric-pair-only.yaml` | qwen3 scratch | REPLICATE §12.46's free control in isolation, with the sweep order REVERSED. Zero boots: run with --skip-run --no-stop against the container already s |
| `wide-compose-c4.yaml` | qwen3 scratch | WIDE 2x2 to separate the three composition models that DEPTH-COST.md section 12.45 could not tell apart. Zero boots: run with --skip-run --no-stop aga |
