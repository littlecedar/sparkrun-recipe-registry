# DeepSeek-V4.1-Flash-1017 on GB10 — unexplored speedups

**Status:** research note, 2026-10-19. Not a recipe change. **No boot was run for this note** and
nothing here is queued. Every candidate names a primary source with its date; anything I could not
confirm from a primary source is marked **UNVERIFIED** rather than asserted. Read it against
[`../recipes/ds4/README.md`](../recipes/ds4/README.md) for the measured lane and
[`../attic/ds4/AGENTS.md`](../attic/ds4/AGENTS.md) §12.17–12.19 for the receipts.

**Scope.** Upstream SGLang / FlashInfer / DeepGEMM / DeepEP work that touches Blackwell and
SM121, DeepSeek-V4.1-specific optimization PRs and roadmaps, NVFP4/FP8/EXL3 releases of the 1017
base, DSpark/MTP work, prefix-cache and scheduler features, CUDA 13.x image bases, and published
DGX Spark numbers. **The knobs this lane already measured are out of scope and are not repeated
here** — read them in the two documents above before proposing anything.

Evidence vocabulary follows the directory: **VERIFIED** = read from a primary artifact or measured
on GB10; **LIKELY** = strong secondary evidence; **UNVERIFIED** = no primary source, or a source
that does not cover SM121.

## The baseline these A/B plans assume

| | TP=4 SGLang line | TP=2 TensorFold line |
|:--|:--|:--|
| Recipe | `recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml` | `recipes/ds4/deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml` |
| Nodes | `.30`–`.33` — **frozen by owner policy; TP=4 findings are upgrade candidates, not queued boots** | `.34`, `.35` — the only pair that can run an interleaved A/B today |
| Serve line | launcher `RECIPE_ENV`, `littlecedar/dgx-spark-dsv41:canary-roce@sha256:acfc331a…` | TensorFold `d5d7bb3`, `littlecedar/dgx-spark-dsv41@sha256:fabbe861…` |
| C1 reference | pooled **67.18 ± 6.97** t/s, n=25 (2026-10-18) | **66.37** (1017 arm, 3 boots, 2026-10-18) |
| Ladder | `benchmarking/concurrency-ladder.yaml` (C1/C2/C5/C10, 5 runs/cell) and `benchmarking/ds4-sglang-depth0-ladder.yaml` (C1/C4/C8/C16, 3 runs/cell) | same depth-0 profile, 3 runs/cell |

**A/B rules used below** (the lane's own, from §12.16):
1. One serve at a time; alternate arms **A/B/A/B** — never one boot per arm.
2. `--fresh` on every bench call (a reused bench id re-emits the earlier boot's numbers).
3. Assert `/v1/models` per boot so an arm cannot be mistaken for its sibling.
4. Pre-register the target cell and the falsifier. A delta counts only if the target cell's mean
   clears the control arm's 15-value range **and** the mechanism signal moves (achieved
   concurrency, accept length, `cached_tokens`, ms/step). Otherwise it is a boot slot, not a win.
5. Three boots per arm for anything quoted; two boots per arm only as a screen, extended on a
   near-threshold result.
6. Hold the shipped pool/pin **constant across arms** — a concurrent memory change is a confound,
   and the pool arithmetic is already measured.

## Ranking (expected effect × feasibility)

Scores are judgment, E×F on 1–5 each. “Nodes” says where the test can run; TP=4 items are
upgrade candidates because `.30`–`.33` are frozen.

| # | candidate | layer | target | expected | E×F | nodes |
|--:|:--|:--|:--|:--|--:|:--|
| P0 | GPU clock-latch audit | host | every cell | up to **1.9×** if a node is latched | 25 | `.34`/`.35` now, then all |
| 1 | `--min-free-slots-delay 1` | scheduler | C8/C16, worst TTFT | **+21 %** C8 decode measured on GB10 | 20 | `.30`–`.33` |
| 2 | Prefix-cache truth (`--enable-cache-report`, `lpm`) | cache | long-prefix revisit | 1.5 s vs 89 s re-prefill if hits work | 16 | `.30`–`.33` |
| 3 | Candidate-only indexer scoring (#43401) | decode kernel | 1M decode | **−17 %** step at 1M on 2×GB10 | 10 | `.30`–`.33` |
| 4 | TensorFold v0.6 bump | engine | prefill + C4/C8 | unquantified release, prefill-heavy | 9 | `.34`/`.35` |
| 5 | TRT-LLM sparse MLA (`--dsv4-attn-backend trtllm`) | attention kernel | C5/C10, 128K | **2.26×** kernel geomean on GB10 | 8 | `.30`–`.33` |
| 6 | `reasoning_effort` high, not max | workload | output tokens | **0.55–0.8×** reasoning cost | 8 | both |
| 7 | Rebuild on newer SGLang + CUDA 13.3 | composite | prefill + decode | per-PR; +19 % cold prefill claimed | 6 | `.30`–`.33` |
| 8 | Encoder SWA bounded replay stack | prefix cache | 64K-hit TTFT | 4.6 s → ~1.0 s at 16 hits | 6 | `.30`–`.33` |
| 9 | DSpark compact verify (#42718) | spec decode | C5/C10/C16 | high-batch only; no GB10 number | 4.5 | `.30`–`.33` |
| 10 | 1017 NVFP4 checkpoint (W4A4) | quant | decode + prefill | +8 % C1 decode, −30 % 655K needle (pre-1017 pack) | 4 | `.30`–`.33` |
| 11 | DCP2 decode context parallelism | attention | 1M decode | +3.4 % full model (2×GB10, uncontrolled) | 3 | none upstream |

---

## P0. Is any node's SM clock latched below 1 GHz? (host; check before any A/B)

**Mechanism.** A GB10 can come up with its SM clock latched low; the reported case is two of four
Sparks stuck **below 1 GHz**, where a reboot did not clear it and unplugging the node did.
**Source:** tonyd615, NVIDIA forum, 2026-09-10 —
[DeepSeek-V4.1-Flash 552B MoE on 4× DGX Spark TP4](https://forums.developer.nvidia.com/t/deepseek-v4-1-flash-552b-moe-on-4x-dgx-spark-tp4-77-2-tok-s-c1-on-peak-52-code-72-tok-s-on-a-warm-code-run-47-math-39-reasoning-23-prose/382897)
(“41 with CUDA graphs + DSpark → 77 after un-latching 2 GPUs stuck below 1 GHz”).

**Expected effect.** 41 → 77 tok/s on the reporting fleet, **1.9×**, but only if a node is
latched; otherwise zero. This is a precondition, not a knob: a latched node corrupts every
cross-boot comparison in the lane.

**Artifact.** None. Read `nvidia-smi --query-gpu=clocks.sm,clocks.max.sm --format=csv,noheader`
once per node before a window, and sample `nvidia-smi dmon -s u -d 1` **during** the ladder on
each rank.

**GB10 evidence.** Reported on 4× GB10, 2026-09-10 (`LIKELY`: one fleet, one post, no raw log).
The knapcio stack separately lists “locked GPU clocks” as tested and not adopted
([`CHANGELOG.md`](https://github.com/knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4/blob/main/CHANGELOG.md),
v2.2 entry, 2026-09-25) — that is a *cap*, not a latch, and does not contradict the finding.

**A/B plan (`.34`/`.35`, runnable now).** One serve, one ladder; record per-node `clocks.sm`
every second. If both sit at `clocks.max.sm` for the whole run, this is closed on our fleet at
zero cost. If either sits low, power-cycle that node and re-run the same ladder; the falsifier is
“clocks at max and throughput unchanged”, and the confirmer is “clocks low, throughput rises
after the cycle with no code change”.

### P0 result (2026-10-19) — no latch on the pair; closed negative

Probed `.34` and `.35`: idle `clocks.sm` reads 208 MHz (normal idle state, not evidence either
way), but under a 60 s bf16 matmul load both ramp to **2171-2190 MHz** against `clocks.max.sm` =
3003 MHz, with `clocks_throttle_reasons.active = 0x4` (**SW Power Cap**, no HW slowdown). That is
the pair's documented ~2200 MHz operating point, not a latched-low clock. A first `.35` attempt
produced no kernel load (container cold start outran the timeout) and was discarded rather than
read as a latch. **P0 is closed as a precondition and costs nothing further**; the per-ladder
`nvidia-smi dmon` sampling stays the rule for any quoted A/B. The production nodes `.30`-`.33`
were then read once without extra load, while their TP=4 serve was live: **2184-2190 MHz** with
`clocks_throttle_reasons.active = 0x0` on all four, so the fleet's serving nodes are not latched
either. Receipt: `~/benchmarks/ds4-p0-clock-20261019/REPORT.md` on the head.

---

## 1. Single-slot prefill admission — `--min-free-slots-delay 1` (scheduler; TP=4)

**Mechanism.** SGLang classifies DSpark as DFlash-family, and at `--max-running-requests >= 8` it
auto-enables an admission delayer that holds new prefills until
`min(4, max(2, (max_running_requests + 5) // 6))` slots are free — **3 at 16** — so a steady
arrival stream sustains ~13–14 of 16, not 16. Passing `--min-free-slots-delay 1` lets a waiting
prefill enter with one slot free (≤1 disables the delay).
**Sources:** MiaAI-Lab README, read 2026-10-19
([`DeepSeek-v4.1-Flash-DGX-Sparks`](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-DGX-Sparks),
“Admission at concurrency 8”); sparkring’s SGLang profile, read 2026-10-19
([profile README](https://github.com/FujitsuPolycom/sparkring/blob/main/profiles/deepseek-v41-flash-sglang-cycle/README.md));
knapcio v2.4 profile table, 2026-10-12
([README](https://github.com/knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4)).

**Expected effect (GB10, measured).** sparkring’s 2026-09-17 TP4/EP4 record: C8 decode
**85.9 → 104.0 tok/s (+21 %)**, C8 worst first-token wait **17.0 s → 1.2 s**; the record says the
C8 gain reproduced on every later boot with the flag.
**Confound, stated:** that boot also changed `mem_fraction_static` 0.90 → 0.80 and the pool
1,500,000 → 7,000,000, so the *pool* is entangled with the flag. The scheduler mechanism and the
17 s → 1.2 s wait are not pool effects. Our own ladder says C10 ≈ C5, so the effect should appear
at C16, not C5/C10.
**Source:** [`sglang-79f656a6-nvfp4-20260917.md`](https://github.com/FujitsuPolycom/sparkring/blob/main/performance/records/deepseek-v41-flash/sglang-79f656a6-nvfp4-20260917.md)
(2026-09-17).

**Artifact / flag.** `--min-free-slots-delay 1`. No image change. It rides
`EXTRA_SGLANG_ARGS`, which the overlay appends after its own two flags
(`launcher.py:extra_sglang_args`) and which is **not** a `RECIPE_ENV` key, so a launch-time
override survives: `-o env.EXTRA_SGLANG_ARGS='--min-free-slots-delay 1'`. Confirm the effective
value in the boot’s `server_args` (or the engine’s startup line), not from the recipe.

**GB10 / SM121 evidence.** Measured on 4× GB10 in a direct cycle, 2026-09-17 (`LIKELY` by this
directory’s labels: third-party receipt, one observation per cell, pool confound). The same flag
ships in Mia’s TP4 profile and in knapcio’s v2.4 table; **our launcher does not pass it** (grep of
the tree: no `min-free-slots` match).

**A/B plan (`.30`–`.33`, blocked by the freeze — upgrade candidate).**
- Arms: control = shipped line; treatment = the same launch plus
  `-o env.EXTRA_SGLANG_ARGS='--min-free-slots-delay 1'`. Everything else identical, pool pin held.
- Interleave 3 boots/arm, A/B/A/B/A/B, `--fresh`.
- Profile A: `benchmarking/ds4-sglang-depth0-ladder.yaml` (C1/C4/C8/C16, 3 runs/cell). C16 is the
  target; C1/C4 are the regression guard.
- Profile B: `benchmarking/concurrency-ladder.yaml` (C1/C2/C5/C10, 5 runs/cell) — expected flat;
  if C5/C10 move, the effect is not the delayer.
- Also record per-boot: max `running-req` seen at C16, and the worst first-token wait of a
  16-request burst (the sparkring probe shape).
- **Falsifier:** the C16 mean does not clear the control’s 15-value range, **or** achieved
  concurrency stays at ~13–14 in the treatment arm. A C16 gain without a concurrency rise is a
  boot slot.

---

## 2. Prefix-cache truth on this lane (`--enable-cache-report`, `lpm`) — cache (TP=4)

**Mechanism.** The radix cache is supposed to reuse compressed KV plus indexer keys on a matching
prefix. The lane measured `#cached-token: 0` on identical back-to-back prompts (2026-10-06,
[`recipes/ds4/README.md`](../recipes/ds4/README.md)), which is either a real zero-hit path or a
mis-read instrument. Upstream spent a long issue on exactly this symptom: on v0.5.17, long agentic
sessions missed every turn while short requests hit ~98 %, and the resolved causes were three
stacked — a gateway-injected prefix break, a client system-prompt tail that rotates, and a HiCache
`load_back` eviction storm. The source analysis in that issue also names an **SWA tombstone veto**
on multi-chunk prefixes and the chunk-front zeroing of the full→SWA mapping.
**Sources:** SGLang #35129, opened 2026-08-17, closed 2026-09-01
([issue](https://github.com/sgl-project/sglang/issues/35129)); MiaAI-Lab
[`docs/cache-reporting.md`](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-DGX-Sparks/blob/main/docs/cache-reporting.md)
(read 2026-10-19).

**Expected effect.** If hits exist after a correct measurement, the lane’s own v2.4 number is the
prize: a 388K-token session revisit takes **1.5 s instead of an 89 s re-prefill**
(knapcio CHANGELOG v2.4, 2026-10-12 — that one comes from the shipped prefix-tail budget, not a
new knob, and that budget stays as shipped; it is cited only as the size of a cache hit). If hits
are genuinely zero, the candidate becomes a bug report, not a speedup, and the falsifier below
says so.

**Artifact / flags.** `--enable-cache-report` (adds `usage.prompt_tokens_details.cached_tokens`;
Mia’s `boot.py` enables it, our launcher does not), and `--schedule-policy lpm` (default is
`fcfs`; longest-prefix-match schedules the requests that share a prefix together). Both are
serve-line flags reachable through `EXTRA_SGLANG_ARGS`; neither needs an image change.

**GB10 / SM121 evidence.** The zero-hit observation is ours; the mechanism is **UNVERIFIED** on
this stack. The HiCache branch does not apply (this lane has no HiCache), and the gateway/client
causes are external, so the surviving hypotheses are the SWA-tombstone/chunk-front path and the
measurement itself.

**A/B plan (`.30`–`.33`, upgrade candidate).**
- Phase A, same boot, no reboot between probes: send one 32K and one 131K prompt 8× back to back;
  record `cached_tokens` and TTFT per repeat. The first is cold by construction; repeats 2–8 must
  hit if the path works.
- Phase B, interleaved 2 boots/arm as a screen (extend to 3): `--schedule-policy lpm` vs `fcfs`,
  32K with a shared 16K prefix, measure cached-token fraction and p50/p90 TTFT.
- **Falsifier:** `cached_tokens` is 0 on every repeat with reporting enabled → the cache path is
  broken; stop and file it. In phase B, no change in hit fraction or TTFT → `lpm` is a null here.

---

## 3. Score candidate blocks only in paged decode consumer layers (decode kernel; TP=4)

**Mechanism.** Layer 20 publishes up to 2,048 blocks of 8 compressed positions per decode row;
the four consumer indexer layers select their top-512 **inside** those blocks. Today the paged
decode path materializes a boolean mask over the full graph capacity and every consumer still runs
the FP4 indexer over every tile of the visible context, masking non-candidates out — so consumer
cost grows with context even though at most 16,384 positions can be selected. Scoring only the
candidate blocks makes that cost context-independent.
**Source:** SGLang #43401, opened 2026-10-09, open
([PR](https://github.com/sgl-project/sglang/pull/43401)); overlapping implementation #40860, noted
in that PR’s comment (2026-10-10). Roadmap entry in #42170 (2026-10-18).

**Expected effect.** Microbench on one RTX PRO 6000 (SM120), mask + masked scan → candidates:
**4.96× at 200K context, 1 row** (78.3 → 15.8 µs), **5.73× at 200K, 4 rows** (230.3 → 40.2 µs),
1.28–1.59× at 1–4K. The saving is per consumer, and the mask was shared, so the per-consumer
saving is smaller than the table. The independent 2× GB10 lane implemented the same idea and
measured **81.7 → 67.5 ms/step (−17.4 %)** on a 1,039,999-token retrieval prompt (25.7 → 32.5
tok/s), “down from 81.7 ms”, with in-place indexer scoring and candidate-only consumer scoring.
**Source:** coolbho3k README, read 2026-10-19
([repo](https://github.com/coolbho3k/DeepSeek-v4.1-Flash-2x-DGX-Spark),
“1M-context decode” paragraph; the 1M numbers predate the current kernel set).

**Artifact.** No flag. A patch on `dsv4/fp4_indexer.py` (#43401 or #40860) inside the image’s
SGLang tree; requires an image rebuild. It is **not** in the pinned `f80c91a4b` tree (2026-09-16).

**GB10 / SM121 evidence.** The end-to-end −17 % is on 2× GB10 in a different engine/overlay
(`LIKELY`, and its own README says the current runtime has not repeated the 1M test). The PR’s
microbench is SM120, not SM121; #43401’s SM120 enablement depends on #42371.

**A/B plan (`.30`–`.33`, upgrade candidate).**
- Interleave 2 boots/arm (extend to 3 on a near-threshold result), same recipe, `--fresh`.
- Ladder: `concurrency-ladder.yaml` (C1/C2/C5/C10) — short-context regression guard.
- Long-context probe: a 1,039,999-token synthetic retrieval prompt (the shape the 2× lane used),
  greedy, ≥128 output tokens; report **ms/step** from the decode records and the needle result.
- **Falsifier:** 1M ms/step does not fall by ≥5 % while the ladder is flat, or the needle stops
  being found. A short-context gain would contradict the mechanism (there is nothing to skip at
  1–4K), so treat it as a boot slot.

---

## 4. TensorFold v0.6 on the TP=2 pair (`.34`/`.35`)

**Mechanism.** v0.6 rebases the `deepseek-v41-tp2` branch onto upstream `python-0.6` and adds a
batch of prompt-path work: the mHC post fused into the next sublayer’s mixes with rows sharing
weight tiles, matmuls reading row-strided inputs in place, the shared expert as one dense GEMM in
the grouped kernels’ order, FP4 cache writes through the one-launch kernels, Engram rows read
through `O_DIRECT`; concurrent rounds wider than the decode kernels’ bound (`TF_DS_ROUND_ROWS`)
with a separate MoE scratch for the 13+ stream batched drafter graph; and the prompt indexer at 2
rows a program / 2 warps with the served head-sum tree (`TF_DS_IDX_RB`, `TF_DS_IDX_WARPS`,
`TF_DS_IDX_TREE`).
**Source:** commit `3825f62`, 2026-10-18
([release commit](https://github.com/bertholomus/TensorFold/commit/3825f62022f25e3e5cf01fa5ea708d4a93b0a9e3));
the branch also carries `222a9c0` (2026-10-19) for DSML tool-call parsing.

**Expected effect.** **UNVERIFIED** — the release commit states the changes, not a measured
delta. The shape is prefill-heavy, with a possible C4/C8 effect from wider rounds. Our recipe pins
`d5d7bb3`, which predates v0.6, so this is a real engine delta, not a re-measurement.

**Artifact.** `ARG TENSORFOLD_REF=3825f62` in `recipes/ds4/Dockerfile.tensorfold-dsv41`, a rebuild,
and a new digest in the recipe’s `container:` line (that edit is **not** part of this note; the
recipe YAMLs are off-limits here). The v0.6 indexer knobs are engine defaults; the env names exist
only if a sweep is wanted later.

**GB10 / SM121 evidence.** The branch is GB10-only by construction (two nodes, TP=2); the build
targets SM121. No performance number exists yet (`UNVERIFIED`).

**A/B plan (`.34`/`.35`, runnable once the image is built).**
- Arms: shipped `fabbe861…` vs the v0.6 rebuild; same launcher, same checkpoint pin, same Engram.
- Interleave 3 boots/arm, A/B/A/B/A/B, `--fresh`, `/v1/models` asserted per boot.
- Ladder: `benchmarking/ds4-sglang-depth0-ladder.yaml` (C1/C4/C8/C16, 3 runs/cell) on the TP=2
  serve. Prefill probe: 32,768 and 131,072 cold tokens, one run each per boot (the lane’s existing
  probe shape).
- **Falsifier:** no cell clears the control’s 15-value range **and** prefill is within the boot
  spread. A C1-only move with flat prefill would not match the release notes and should be
  re-run before it is quoted.

---

## 5. TRT-LLM sparse MLA decode on SM121 — `--dsv4-attn-backend trtllm` (attention kernel; TP=4)

**Mechanism.** Replaces the FlashMLA sparse-MLA decode with TRT-LLM-GEN sparse MLA. FlashInfer
v0.7.1 added DeepSeek-V4.1 dual-cache sparse MLA for SM120/SM121, and v0.7.2 added the SM121
mixed-cache Cake decode kernel: it reads the two caches **in place** — 528 B/token FP8 SWA main
cache (512 E4M3 + 16 UE8M0 group-32 footer scales) and 288 B/token FP4 compressed cache (512
E2M1 dims incl. RoPE; 256 B payload + 32 B E4M3 group-16 scales) — with BF16 Q, exact on-chip
dequantization, BF16 P/V, fp32 softmax/merge. The 288 B cache is never reinterpreted as the 384 B
DSv4 NVFP4 layout.
**Sources:** FlashInfer v0.7.1 release notes, 2026-10-09
([releases](https://flashinfer.ai/releases/)) and v0.7.2, 2026-10-15; PR #5983, opened 2026-10-02,
closed 2026-10-07 ([PR](https://github.com/flashinfer-ai/flashinfer/pull/5983)). SGLang-side
enablement: #41603, opened 2026-09-29, **merged 2026-10-06**, marked done on the V4.1 roadmap
([#42170](https://github.com/sgl-project/sglang/issues/42170), updated 2026-10-18).

**Expected effect.** PR #5983’s own paired, interleaved, CUPTI benchmark against the hand-written
SM120 `sparse` kernel (same card/session, cold L2, graph), 37 representative rows: **GB10 37/37
rows faster, geomean 2.26×, min 1.28×**; RTX PRO 6000 2.46×, RTX 5090 2.48×. That is a kernel
measurement. End to end on GB300, #41603 measured sparse attention **73.5–73.8 → 44.6–45.1 µs**
at C64 × 6 verify rows and 128K context, and serving at C64 (32K in / 1K out, DSpark, Engram
offload) **564.6 → 575.4 tok/s (+1.9 %)** across two repeats. **UNVERIFIED on SM121 end to end.**

**Artifact / flags.** `--dsv4-attn-backend trtllm --cuda-graph-backend-prefill disabled`.
Requires an image with FlashInfer ≥ 0.7.0.post1 (the SM121 Cake route needs 0.7.2) **and** the
SGLang tree containing #41603. Our image pins FlashInfer 0.6.18 (`UNVERIFIED` from the image, but
the same base image reports 0.6.18 in SGLang #39173’s environment block, 2026-09-12), so this is a
rebuild.

**Compatibility, stated before the plan.** #41603 rejects V4.1 TRT-LLM prefill CUDA graphs **and
SWA bounded replay for now**. This lane ships `--enable-decoder-swa-bounded-replay` by default;
it is worth **1.37× prefill on 4× GB300** in the day-0 blog’s paired test (2026-09-10,
[blog](https://www.lmsys.org/blog/2026-09-10-deepseek-v41)). So the A/B must disable replay in
**both** arms, which gives up a known prefill win to test the decode kernel.

**GB10 / SM121 evidence.** Kernel: **VERIFIED** by the PR author on GB10 (explicit per-card
table). End to end: none on SM121 (`UNVERIFIED`).

**A/B plan (`.30`–`.33`, upgrade candidate).**
- Two images: control = shipped `acfc331a…`; treatment = the same tree + #41603 + FlashInfer
  0.7.2 (or a newer nightly), both launched with `--no-enable-decoder-swa-bounded-replay` so the
  only remaining difference is the attention backend.
- Interleave 3 boots/arm, `--fresh`; assert the resolved backend in the startup line and
  `/v1/models` per boot.
- Ladder: `concurrency-ladder.yaml` (C1/C2/C5/C10, 5 runs/cell). Add one attention-heavy cell:
  128K prompt, 6-token verify, C64 (the PR’s cell) — report sparse-attention µs if the engine logs
  it, else ms/step.
- **Falsifier:** C5/C10 decode does not clear the control’s 15-value range, or the replay-off
  control already matches the new backend (then the kernel win is hidden by something else). A
  quality miss on the house battery also falsifies it.

---

## 6. `reasoning_effort` high instead of max (workload; both lanes)

**Mechanism.** On agent loops, each turn’s reasoning stays in the prompt and is re-read by later
turns, so reasoning cost compounds. Capping the default effort reduces output and subsequent
prefill tokens without changing the answer quality on the measured set.
**Source:** LibertAIDAI 1017 EXL3 2.9 bpw model card, read 2026-10-19
([card](https://huggingface.co/LibertAIDAI/DeepSeek-V4.1-Flash-1017-EXL3-2.9bpw), “Agentic use /
reasoning effort”): on **3,738 jobs** (agentic coding, tau-bench, LiveCodeBench, AIME, chat),
`high` (75, the default) matched `max` (100) on quality at **0.55–0.8× the cost**, and `low` (50)
matched too at **0.4–0.6×**. “Avoid max for agent loops unless you need the headroom.”

**Expected effect.** 20–45 % fewer reasoning tokens at equal quality on that corpus; the engine’s
tok/s does not change. It is a cost/speedup for the workload, not a kernel.

**Artifact / flag.** Request-level `reasoning_effort` (and the served alias/cookbook default). The
SGLang V4.1 cookbook lists `SGLANG_DSV41_REASONING_EFFORT` in its env block and says the parser
maps `reasoning_effort` values; thinking is off by default on this model. **UNVERIFIED** whether
the pinned 2026-09-16 tree implements the same mapping — the lane’s chat template and parser are a
separate overlay.

**GB10 / SM121 evidence.** Quality/cost measured on the 1017 weights; the hardware is not stated
in the card (`LIKELY` that it transfers, since it is a token-count effect, not a kernel).

**A/B plan (`.34`/`.35`, same serve; or `.30`–`.33` on the TP=4 serve).**
- One boot per lane is enough: the arms are request-level, so interleave 20 requests per arm in
  the **same** serve (arm order ABBA to cancel drift).
- Measure reasoning tokens, total output tokens, and the house battery score per arm.
- **Falsifier:** house score drops below the shipped 36/37 (or the lane’s baseline) on the capped
  arm, or the token saving is <10 % on the lane’s traffic. Then the card’s corpus does not match
  ours.

---

## 7. Rebuild the image on a newer SGLang tree and CUDA 13.3 (composite; TP=4)

**Mechanism.** The image’s SGLang tree is the `dsv4.1` branch at **`f80c91a4b` (2026-09-16)**. The
V4.1 optimization roadmap (opened 2026-10-02, updated 2026-10-18) lists a batch of merged
post-09-16 work, each of which removes launches, host syncs or intermediate traffic on this
model: `q_rope_store` folded into `fused_q_norm_rope` (#41657); faster FP4 index-K gather and
`combine_topk_swa_indices` (#41658); prefill indexer raw selection, row-pair schedule IDs and host
sync removal (#41659); fused c1/c2 compression for eager extend and faster c2 decode (#41660);
trimmed prefill model-entry overhead (#41704); cached MXFP8 dispatch (#42156); reduced eager Engram
extend preparation (#42159); two extra multiply kernels removed from V4.1 attention (#42232);
fused indexer score/ReLU/weighting/head reduction (#42365); the request-window copy cuts in
#42715/#42921. **Source:** [#42170](https://github.com/sgl-project/sglang/issues/42170), updated
2026-10-18.

CUDA 13.2 also carries two SM121-relevant items: cuBLASLt “up to 3× for NVFP4 and MXFP8 on DGX
Spark for large M and N”, and PTX ISA 9.2’s direct `cvt.rn.bf16x2.e4m3x2`, which FlashInfer
#5983 uses on CUDA ≥ 13.2 and emulates below it (2026-10-02, [PR](https://github.com/flashinfer-ai/flashinfer/pull/5983)).
**Source for the CUDA claims:** NVIDIA forum recap, 2026-03-11
([thread](https://forums.developer.nvidia.com/t/cuda-13-2-dgx-spark-impact/363182)) — a user
recap citing the toolkit release notes, so **LIKELY**, not VERIFIED on our stack.

**Expected effect.** Not isolatable as one number. The roadmap’s own entries claim **+19 % cold
prefill** from the prefill CUDA graph (#43440, replaced by #43736; roadmap 2026-10-18) and the
decoder-replay fold (#43736, opened 2026-10-12, **merged 2026-10-13**) measured p50 TTFT
−38…−53 % up to C16 on GB300 with throughput +1…+5 % and TPOT flat. The H20 integration report
in #42170 (community comment, 2026-10-13) measured 524K TTFT 323 → 25.5 s and C64 +189 % for a
**whole** backport, not one PR —
**do not transfer that**. On GB10, decode is launch-bound, so the small fusions are plausible but
**UNVERIFIED**.

**Artifact.** A new base + overlay. The best-documented CUDA-13 nightly in the V4.1 cookbook is
`lmsysorg/sglang:nightly-dev-cu13-20261015-a6a8c560@sha256:0a1ba33aa4e032b8c5bcebdc69c45664074c032074add4f7db01629ec1fcc381`
(cookbook `generatedOn` 2026-10-18,
[DeepSeek-V4.1 cookbook](https://docs.sglang.io/cookbook/autoregressive/DeepSeek/DeepSeek-V4_1)).
The lane’s RoCEnante overlay, b12x/b12x_next, and the adapter set all patch engine symbols and
**refuse to boot on source drift**, so this is a re-port, not a tag bump. The adapter catalog is
[`docs/adapters.md`](https://github.com/knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4/blob/main/docs/adapters.md)
(read 2026-10-19).

**GB10 / SM121 evidence.** The prefill-graph PR’s numbers are GB300. A prefill graph also needs a
capture pool: #43736 reports **~39 GB at a 16K capture** on GB300 and had to lower its static
memory fraction. On a 121.7 GiB GB10 the shipped 1M prefill already leaves
5.7 GiB head, so the prefill graph is **UNVERIFIED and plausibly infeasible here** — test the
library fusions first, the graph separately.

**A/B plan (`.30`–`.33`, upgrade candidate; staged, not single-variable).**
- Stage 1: new tree, **no** prefill graph, same adapters/flags. Interleaved 3 boots/arm on
  `concurrency-ladder.yaml` + the 4k/32k/131k prefill ladder; falsifier is “no prefill gain and no
  decode gain outside the 15-value range”.
- Stage 2 (only if stage 1 is green): `--cuda-graph-backend-prefill breakable` with the replay
  fold, after reading the boot’s free memory. Falsifier: the 1M cold prefill wedges or
  `MemAvailable` low-water drops below the shipped 5.7 GiB.
- CUDA 13.3 base is a separate arm: prefill ladder 4k–262k, same everything else.

---

## 8. Encoder SWA bounded replay stack (prefix cache; TP=4)

**Mechanism.** Encoder-side bounded replay removes the window-checkpoint requirement for a prefix
hit: the cache keeps compressed KV and indexer keys, and on a hit SGLang recomputes the cached
prefix’s last 128 tokens to reconstruct window KV. #43166 folds that replay into the extend
forward instead of one eager 128-token forward per hit; #44673 keeps the DSpark draft’s SWA in a
per-request ring so evicting it no longer cuts the target’s prefix hits.
**Sources:** #43166, opened 2026-10-08, **merged 2026-10-15**
([PR](https://github.com/sgl-project/sglang/pull/43166)); #44673, **merged 2026-10-16**
([PR](https://github.com/sgl-project/sglang/pull/44673)); roadmap #42170 (2026-10-18); day-0 blog
§4 (2026-09-10). The day-0 blog said encoder replay excludes speculative decoding; #44673 is the
change that makes the DSpark combination work, so that older restriction is superseded.

**Expected effect.** #44673, GB300 TP4 with DSpark: a prompt whose draft SWA was evicted by 400
other prompts **re-hits 8,448 of 8,565 tokens instead of 0**; GSM8K 98.0 % with and without
decoder replay; accept length 3.81 vs 3.78. #43166: 64K-hit TTFT p50 at 16 concurrent
**4,608 → 983 ms** (flag-off control 582 ms), 7K-hit 4,530 → 878 ms. **Cost:** the flag raises
decode step p50 at 32 requests **15.3 → 24.1 ms** on that tree; the author attributes the residual
to request-window copies addressed by #42715/#42921, which are open in the roadmap.

**Artifact / flags.** `--enable-encoder-swa-bounded-replay` (opt-in; the lane ships only decoder
replay), plus the #43166/#44673 source and, for the decode-cost fix, #42715/#42921. Image rebuild.

**GB10 / SM121 evidence.** All numbers are GB300; SM121 is **UNVERIFIED**. The mechanism does not
depend on the GPU, but the decode-step cost might.

**A/B plan (`.30`–`.33`, upgrade candidate).**
- Arms: shipped; shipped + encoder replay (no other change); A/B/A/B, 3 boots/arm.
- Probe 1 (the point): warm a 65,536-token shared prefix, then send **16 concurrent** requests
  that append 1,024 new tokens; report p50/max TTFT and `cached_tokens`.
- Probe 2 (the cost): the standard ladder at C16/C10 — the flag must not cost more than 5 % on the
  target cells, or the win is for a different workload.
- **Falsifier:** hit fraction stays near zero, or the C16 decode step rises by >5 % and the
  request-window PRs are not in the image. In either case the stack is not ready for this lane.

---

## 9. DSpark compact verify with a profiled SPS table (#42718) (spec decode; TP=4)

**Mechanism.** DSpark’s confidence scheduler turns per-block survival probability into a
per-request verify budget each step; `compact` verifies only the window the scheduler picked,
front-packs the batch ragged, and replays a smaller CUDA-graph tier as budgets trim. On V4.1 the
Engram hasher asserted `num_tokens == bs * draft_token_num` and `token_req_indices` used a uniform
`repeat_interleave`, so every compact tier but the largest aborted at capture (#39173) and the
first trimmed request died. #42718 derives the token-to-request mapping with one `searchsorted`
over the layout’s `qo_indptr` and reuses Engram’s extend kernel.
**Sources:** SGLang #39173, 2026-09-12, open
([issue](https://github.com/sgl-project/sglang/issues/39173)); #42718, 2026-10-06, open with
failing CI ([PR](https://github.com/sgl-project/sglang/pull/42718)); DSpark blog, 2026-07-06
([blog](https://www.lmsys.org/blog/2026-07-06-dspark-sglang)) for the schedule.

**Expected effect.** The blog’s paired `compact` vs `no-trim`: **tie at batch 1**, with the gain
opening as concurrency grows and larger on lower-acceptance traffic; no absolute number is
transferable (different hardware/traffic). The H20 whole-deployment report in #42170 (2026-10-13)
is **not** an isolated compact-verify result. On this lane the target is C5/C10/C16.
**UNVERIFIED on GB10.**

**Artifact / flags.** `SGLANG_RAGGED_VERIFY_MODE=compact` plus a profiled
`dspark_sps.json` (`python3 -m sglang.benchmark.dspark_sps_profiler all --base-url …`), and the
#42718 (+#42709) source. Image rebuild. The lane deliberately does **not** ship the ragged cost
table because it crashes the Engram path; #42718 is the fix that makes it usable, and it is not
merged.

**GB10 / SM121 evidence.** The crash is reproduced on 4× GB10 TP4 and 3× GB10 TP3; the fix is
tested on RTX PRO 6000 (SM120) and end-to-end on 4× RTX PRO 6000, not on GB10 (`UNVERIFIED` for
the fix on SM121).

**A/B plan (`.30`–`.33`, upgrade candidate).**
- Arms: shipped verify-all vs compact with the table; 2 boots/arm interleaved (3 if near
  threshold). Assert the SPS table path and `Mean acceptance length` per boot.
- Ladder: `concurrency-ladder.yaml` (C1/C2/C5/C10) plus a C16 cell from the depth-0 profile.
- Log per cell: accept length, verify rows/step, ms/step.
- **Falsifier:** no C10/C16 gain outside the range, or accept length falls without a step-time
  fall (then trimming is lossy, not free). A capture abort or first-request crash is a hard fail.

---

## 10. A 1017 NVFP4 W4A4 checkpoint (quant; TP=4)

**Mechanism.** NVFP4 stores routed experts as E2M1 with one E4M3 scale per 16 values plus an FP32
global scale and a calibrated FP32 `input_scale` per projection, so the expert GEMMs can run W4A4
on Blackwell FP4 tensor cores instead of MXFP4 W4A16. The 1017 MXFP4→NVFP4 transcode keeps the
4-bit codes bit-exact (NVFP4’s 16-element blocks are a refinement of MXFP4’s 32); only scales
change. The 1017 NVFP4 repo is **399.51 GiB** vs the 475.24 GiB MXFP4 base, because its Engram
tables are MXFP4 (97.28 GiB vs 188.83 GiB).
**Source:** LibertAIDAI card, read 2026-10-19
([card](https://huggingface.co/LibertAIDAI/DeepSeek-V4.1-Flash-1017-NVFP4)).

**Expected effect (measured on the pre-1017 pack, same SGLang stack).** sparkring, 2026-09-17,
4× GB10 TP4/EP4, `nvidia/DeepSeek-V4.1-Flash-NVFP4` (491.1 GiB) + `MOE_RUNNER_BACKEND=flashinfer_cutlass`
vs stock: decode C1 **34.2 → 36.9 (+7.9 %)**, C4 79.1 → 80.8 (+2.1 %), C8 105.7 → 107.4 (+1.6 %);
prefill 16K/64K 3,499/3,391 → **3,697/3,682**; needle 262K 104.8 → **88.9 s**, 655K 386.9 →
**268.6 s**; C8 × 262K distinct 776.8 → **694.5 s**. Quality on a 1,440-position panel: top-1
agreement **0.9292** (code 0.992, prose 0.898), truncated top-20 KL mean 0.0293; disagreements sit
where stock’s own top-1 margin is 0.03 (vs 0.84 overall). Same-checkpoint boot-vs-boot was
identical.
**Source:** [`sglang-79f656a6-nvfp4-20260917.md`](https://github.com/FujitsuPolycom/sparkring/blob/main/performance/records/deepseek-v41-flash/sglang-79f656a6-nvfp4-20260917.md)
(2026-09-17). Note the arm also changed the MoE runner, so the delta is checkpoint+runner.

**Blocker for 1017.** The 1017 NVFP4 pack quantizes Engram to MXFP4, and NVIDIA’s card states
“the MXFP4 Engram tables are not supported in SGLang yet” (quoted in the LibertAIDAI card). The
working sparkring variant is the **pre-1017** pack, whose Engram is FP8. An upgrade would need a
1017 NVFP4 pack that keeps the Engram at FP8, which does not exist as of 2026-10-19. The pack also
needs `flashinfer_cutlass` (the image default `flashinfer_mxfp4` fails on the per-expert
`input_scale` slice) and a draft overlay for DSpark; with the draft, the reported budget fell to
5,448,448 tokens, a cut versus our shipped pool.

**Artifact.** `model_revision` on a 1017-NVFP4-with-FP8-Engram repo + `MOE_RUNNER_BACKEND=flashinfer_cutlass`
+ the DSpark draft overlay. None of this exists for 1017 today.

**GB10 / SM121 evidence.** The performance and quality numbers are GB10 (`LIKELY`: one site, one
day, one observation per cell). The 1017 variant is **UNVERIFIED** and currently unservable.

**A/B plan (`.30`–`.33`, upgrade candidate; gated on the checkpoint existing).**
- 2 boots/arm interleaved, same image, same pool **measured per boot** (the two packs have
  different budgets); assert the served snapshot path.
- Ladder + prefill ladder + a 262K needle; quality: the house battery and a 1,440-position
  top-1/KL panel against the shipped MXFP4 stack.
- **Falsifier:** top-1 agreement below 0.92 or a house-tier drop >1 item; or no decode gain once
  the budget difference is held constant.

---

## 11. DCP2 decode context parallelism (attention; TP=4, blocked upstream)

**Mechanism.** DCP stripes a request’s MLA KV across ranks by token position (`owner(p) = p mod c`),
runs attention against the owner-local shard, and merges partial outputs exactly by LSE. Decode
reads ~1/c of the cache per rank and adds one packed all-to-all per MLA layer. `--dcp-size N`,
`--dcp-comm-backend {ag_rs,a2a,fi_a2a}`, `--dcp-replicate-q-proj`.
**Source:** SGLang DCP docs, read 2026-10-19
([docs](https://docs.sglang.io/docs/advanced_features/dcp)).

**Expected effect.** A custom **concurrent DCP2** overlay on 2× GB10 measured component gains of
6–10 % (4-row decode), ~25 % (24-row, representative of C6 verification) and 16–20 % (512-row
prefill), and a full-model **+3.43 % pooled decode / +4.85 % prefill** against a historical run —
explicitly “not a fresh controlled full-model A/B”.
**Source:** coolbho3k [`docs/dcp-overlap-performance.md`](https://github.com/coolbho3k/DeepSeek-v4.1-Flash-2x-DGX-Spark/blob/main/docs/dcp-overlap-performance.md),
2026-09-18.

**Blocker.** Upstream DCP × speculative decoding is allowlisted only for **Kimi Linear + DSpark on
`tokenspeed_mla`/`cutedsl_mla`**; “everything else still raises”. DCP × DSA requires SM100/SM103
with the `trtllm` DSA backends. V4.1 uses the `dsv4` backend and ships DSpark, so `--dcp-size 2`
is not available to this lane.
**Sources:** DCP roadmap #29736, updated 2026-10-06
([issue](https://github.com/sgl-project/sglang/issues/29736)); DCP doc §“DCP × speculative
decoding”, read 2026-10-19.

**Artifact.** None usable. The 2× lane’s DCP2 is a bespoke vLLM/EXL3 overlay, not an SGLang flag.

**GB10 / SM121 evidence.** The overlay is GB10, but it is a different engine and checkpoint
(`LIKELY` for the mechanism, not for this lane).

**A/B plan.** Not runnable until upstream supports DCP with `dsv4` + DSpark. If it lands, the plan
is 3 interleaved boots/arm on the depth-0 ladder plus a 131K decode probe; falsifier is “no
long-context decode gain outside the range”, with the all-to-all cost visible at short context as
a regression.

---

## Checked and rejected (found in the search, not worth a boot here)

| Item | Why not | Source, date |
|:--|:--|:--|
| Fused TP4 low-latency decode chain (`SGLANG_OPT_DSV41_LOW_LATENCY_DECODE`) | static precondition is **SM100** (B200/B300); not SM121 | SGLang #44933, 2026-10-17 |
| mHC split-K / 160-slice decode mixing | 160 slices are SM120-only (SM121 keeps 80); end-to-end −0.5…+3.5 % on RTX PRO; open PR | #42864, 2026-10-07 |
| Bumping the verify-cap threshold | upstream fit on 6,074 uncut steps: per-position thresholds worth **+0.4 %** over the shipped 0.1; a perfect cut would be +15.5 % | knapcio `docs/adapters.md`, read 2026-10-19 |
| More L2-prefetch sub-gates (`AHEAD`, `DRAFT`, `ENGRAM`, `LMHEAD`, `WOB_MB`, `MOE`) | measured flat or slower; only `WOA` is in the line | knapcio CHANGELOG v2.2, 2026-09-25 |
| `--enable-deepseek-v4-fp4-indexer` | four-boot off/on/off/on: identical greedy output, speed and prefill (no-op on V4.1) | knapcio CHANGELOG, 2026-09-24 |
| Locked/capped GPU clocks | tested and not adopted | knapcio CHANGELOG v2.2, 2026-09-25 |
| 1,024-token prefill chunks at 1M context | −31 % prefill and −34 % on a 655K needle vs 4,096 | sparkring record, 2026-09-17 |
| MXFP8 **MoE-input** gathers in prefill SP (`DSV41_PREFILL_SP_FP8_MOE`) | bit-exact but flat on real-text prefill; not in the line | knapcio CHANGELOG v2.2, 2026-09-25 |
| `--num-continuous-decode-steps 4` | measured null on an 8× RTX PRO PCIe stack (2,741.7 vs ~2,800 tok/s); no GB10 evidence | magik.net benchmark note, read 2026-10-19 |
| Pre-1017 NVFP4 as a drop-in for the 1017 base | older weights; and the 1017 NVFP4 Engram is MXFP4, unsupported in SGLang | LibertAIDAI card, read 2026-10-19 |
| HiCache / host-tier KV / `OFFLOAD_MODE=ram` | host RAM is GPU RAM on GB10; the lane already records this | `attic/ds4/AGENTS.md` §3.2, §9 |
| EP > 1 / DeepEP | the lane ships EP=1; EP=2 loads but dies at the first decode plan | `attic/ds4/AGENTS.md` §11 |

## Unverified leads

These looked plausible but I could not confirm them from a primary source covering SM121, or the
source is a vendor claim without a GB10 measurement. They are **not** candidates yet.

- **`--fp4-gemm-backend auto` → `flashinfer_cudnn` on CUDA 13+.** The server-args docs list
  `auto` as choosing cuDNN when CUDA 13+/cuDNN 9.15+ is present, and cuBLASLt/cuDNN claim gains
  for FP4 on GB10. Our MoE is b12x, so the flag may reach only the compressed-KV/indexer FP4
  GEMMs. Also conflicts with the lane rule “do not override a resolved backend” — confirm the
  resolved value in the startup log first. Docs read 2026-10-19
  ([server args](https://docs.sglang.io/advanced_features/server_arguments.html)).
- **`sgl-deep-gemm` 0.2.0 → 0.2.2.** DeepGEMM’s 2026-09-30 release claims improved Lightning
  Indexer kernels for V4.1 (prefill and paged decode) and Sparse Indexer head counts 4–32. No
  evidence the GB10 image dispatches those kernels (the lane’s indexer path is the chunked
  backport + b12x). ([DeepGEMM #462](https://github.com/deepseek-ai/DeepGEMM/pull/462),
  2026-09-30.)
- **`DSV41_CACHE_GIB` > 4.** Upstream ships 4 GiB / 16 ways with a 67–76 % row-cache hit rate and
  says the ways are free; no published sweep of a larger cache. It trades KV pool, which is
  measured and pinned, so it needs its own boot pair.
  ([knapcio README](https://github.com/knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4), 2026-10-12.)
- **`--min-free-slots-delay` > 1.** The flag’s “batch admissions” mode is documented but the only
  measured point is 1 vs automatic. No source for a middle value.
- **`--sleep-on-idle`.** Reduces idle CPU from 47 % to 14 % upstream; no measured serving effect.
  Could matter on a 20-core GB10 shared with the GPU, or could add wakeup latency.
- **TensorFold `TF_DS_ROUND_ROWS`, `TF_DS_IDX_RB/WARPS/TREE`.** New v0.6 knobs with no sweep
  published. The defaults are the only measured point.
- **`--stream-interval` > 1.** The docs say a larger value raises throughput by reducing
  streaming flushes; it cannot change a non-streaming ladder. Unverified for streaming clients.
- **`SGLANG_OPT_FP8_WO_A_GEMM`.** The older SM121 lead; the lane instead ships the
  `DSV41_WO_A_W8` twins, and no source compares the two on this tree.

## Method and limits

Searched 2026-10-19 across SGLang issues/PRs and the V4.1 roadmap, the SGLang and FlashInfer
release notes, DeepGEMM/DeepEP PRs, the LMSYS V4.1 and DSpark posts, the V4.1 cookbook, the
knapcio/MiaAI/sparkring stacks, the 2×-Spark EXL3 repos, Hugging Face model cards for the 1017
base, and the NVIDIA DGX Spark forum. Every candidate above cites its source and date inline.

Limits, stated because they bound how much any of this can be trusted:

- **No boot, no measurement.** Every GB10 number in this note is someone else’s, on a different
  image, checkpoint revision, or peer count unless the text says otherwise.
- **Build distance.** Candidates 3, 5, 7, 8 and 9 need an image built from a tree newer than
  `f80c91a4b`, and the lane’s adapters refuse to boot on engine drift. Candidates 4, 10 and 11
  need a different image or checkpoint entirely. The real cost is the re-port, not the flag.
- **One-variable discipline.** The sparkring delayer record and the NVFP4 record both bundle a
  memory change with the tested change; the plans above hold the pool constant wherever the
  checkpoint permits it, and candidate 10 states its budget difference instead of hiding it.
- **Node policy.** `.30`–`.33` are frozen. Nothing in this note is queued; the TP=4 items are
  upgrade candidates for when the owner unfreezes those nodes. `.34`/`.35` can run P0, candidate
  4, and candidate 6 today, and nothing else.
