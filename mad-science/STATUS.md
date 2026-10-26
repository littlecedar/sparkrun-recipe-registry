# Board — generated 2026-10-26 14:59 ET

## In flight

| where | owner | what |
|---|---|---|
| census | board-keeper | **14:59 ET 2026-10-26, all six nodes (read-only `ssh` + `docker ps` + per-boot workload probe)**: ALL SIX NODES EMPTY — 0 running containers on `.30`–`.35` (ranks still handed back from the c3 terminal stop; the ornith-triage boot has not been fired; no spares boot live). No workload probe available (nothing to probe) |
| knob gates on the shipped line (COMPLETE) | tp4-recovery | **both cells spent on the shipped `canary-roce-aff52fa5` line** (`0123dda`): S1 ship-line measurement reproduces the wiring-check evidence shape (cached-token 28928 @ 32k, 119552 @ 131k, TTFT collapse 15.22→0.28 s / 27.18→0.45 s); candidate6 house battery **37/37 both arms** (high-default vs `reasoning_effort=max` via chat-template kwargs), **0 paired flips — parity PASS → the knob SHIPS (high default stays)** |
| launcher flag-collapse root cause (RECORDED) | quartet-holder | `-o extra_args=` is **INERT** on the sglang launcher (the value collapses at fold time) — the valueless flag must pass via `-o env.EXTRA_SGLANG_ARGS=…` (`0123dda` queue note, boot `…_7f5f562975f3`) |
| c3 chain (TERMINAL — NO-SHIP) | adapter-report-gate | **row 21** (`a9bec51`): DeepGEMM paged-sparse API SM100-only (`attention.hpp:301` arch-major==10) vs GB10 SM121 — no in-image fix. The no-ship record is LANDED in DEEPSEEK §17/§19, queue, ds4 README (`6ffdda8`); shipped line STANDS; arm3 indexer-scoring + arm5 trtllm ARCH-GATED (same SM100 gate) |
| queue deltas | tp4-recovery | `ds4-repro-config-created` **WITHDRAWN** (image-ID-DROPPED ruling — byte-repro suffices); `chunk-32768-overlay-reprobe` DONE NOT-SHIPPABLE (`f3cf420`); `glm-flash-concurrency-degradation-search` DEFERRED (row 19) |

Mirrors `mad-science/queue.json` via `tools/task-queue.py` (check **ok**, 41 tasks, at 14:59). **Running**: `pool-prefetch-missing-bodies` only. Scheduler top-3 (queued, tier dsv4.1-1017): `ornith-toolcall-ohmympi-triage` (w 3.00), `tensorfold-metrics-bridge-generalization` (w 1.50), `h2h-glm-flash-house-recipe` (w 1.50). Later: `h2h-doc-refresh` (w 0.50), `h2h-beam-house-and-bfcl-category` (w 2.50), `glm-flash-concurrency-degradation-search` (w 5.00 — DEFERRED, row 19), idle-only `h3-quartet-retry`:
| job | node cost | holds | state |
|---|---|---|---|
| 1. `chunk-32768-overlay-reprobe` — 32768 prefill-chunk probe on the aff52fa5 overlay | quartet | tp4-recovery | DONE — NOT shippable (pool −72%, needles TRUNCATED, `f3cf420`) |
| 2. `w4-survey-arm3-indexer-scoring` — SGLang PR #43401 candidate-only indexer scoring | quartet | tp4-recovery | ARCH-GATED (DeepGEMM SM100-only, row 21 — withdrawn) |
| 3. `ds4-repro-config-created` — pin the knapcio image config created stamp | single | tp4-recovery | WITHDRAWN (image-ID-DROPPED ruling — byte-repro suffices) |
*(Later rows: `ds4-adapter-report-gate` (w 14.00-class — c3 TERMINAL NO-SHIP, row 21); knob track DONE (S1 + candidate6 ships, `0123dda`). Done in the ledger: knob gates (S1 evidence + candidate6 parity PASS), c3 no-ship record (`6ffdda8`), flag-collapse root cause, flag track (candidate6/S1/S2/S3), main-image-boot-gate, chunk-32768 reprobe (NOT shippable), H3 first four-rank cell, adapter trial, byte-reproducible, mellum probe + speedup levers, S0, Beam remainder, h2h-glm-needle-3rungs, h2h-glm-tools-leg; withdrawn: b12x parity/ship-recipe/tuning-round, `ds4-repro-config-created`.)*

## Landed this session

| time ET | commit | one clause |
|---|---|---|
| 08:11 ET | `5141c20` | Beam arm: card's `--reasoning-parser beam`/`--tool-call-parser beam` added to `recipes/explore/zz-beam-1.0-501b-a23b-nvfp4-tp4-vllm.yaml`; TODO gains §"Retry queue — window 4" (three tracks + owner advisories) |
| 08:12 ET | `ab6078a` | Fleet-wide Docker seccomp change enables io_uring on all six nodes: `tools/enable-io-uring.{py,sh}` + guard test, probe-before/apply-after evidence recorded; b12x boot unblocked |
| ~10:30 ET | `65f8fce` | Beam arm fix: cell-(d) comment lines had landed inside the folded command scalar and ran as engine argv (boot-2 attempt 2 crash) — notes moved above `command:`, fold cleaned |
| ~10:35 ET | `3de5d70` | Beam DFlash2 drafter by pool snapshot path (vLLM SpeculativeConfig cannot resolve a repo id under `HF_HUB_OFFLINE`); snapshot `163b276b` verified |
| ~11:00 ET | `689ee3b` | TODO window-4: owner's three dated rulings landed — drafter policy (DFlash2 stays), build-gate drift (durable re-port path), model priority (1017 primary) |
| ~11:30 ET | `cd2a60a` | Owner-directed task queue: `tools/task-queue.py` weighted scheduler + `mad-science/queue.json` seed + `QUEUE.md` protocol + guard tests |
| 16:26 ET | `7fa352d` | Beam sha guard exempts `--speculative-config` tokens + two controls; parity recipe carries BOTH ulimits (boots 2–4 proved each half alone is fatal) |
| 17:34 ET | `055ab3d` | GUIDANCE adapter background folded into tracked records; only open questions remain |
| 17:42 ET | `cbede11` | Owner answers §5–§12 folded into TODO dated advisories; GUIDANCE rewound to open questions |
| 18:00 ET | `541d843` | Owner round-5 answers folded into TODO dated advisories; `mad-science/GUIDANCE.md` deleted |
| ~18:30 ET | `0550ac7` | Queue ledger round-4/5 rulings folded: adapter trial becomes the adoption path blocking the flag track; 7 new tasks; ship-recipe state-blocked; S0 stale cite repointed to `recipes/ds4/README.md` |
| ~18:45 ET | `f75ae31` | Owner cancels the vLLM b12x 1017 route — recipe hash-moved to attic/ds4, metrics landed there (C1 34.04 agg vs 64.0 bar; house 37/37; 1M context; needle 32k 10/10), queue rows withdrawn, root AGENTS counts re-measured (78 recipes / 44 modules / 988 tests) |
| ~19:05 ET | `c3c3dd7` | ds4 trial re-pin to knapcio upstream HEAD `aff52fa5` (v2.5+, quarantined v2.4 lineage retired, #41303 backport): full in-image gate green, `Dockerfile.knapcio-dsv41-aff52fa5` vendored |
| ~19:15 ET | `bb4c67f` | Mellum MTP probe re-pinned to upstream `d854d98bae` (2026-10-25 HEAD): local build on `.35`, both gates green; ds4 README gains the sparkrun-HOME single-node launch caveat |
| ~19:25 ET | `edfb2ea` | Mellum MTP n=1 upstream retest: 102.95 ± 3.20 vs pooled baseline 98.44 ± 3.36, −0.4 % vs prior figure — rejection stands, probe arm stays `zz-`; media drama-3 pool-stub failure recorded; queue `mellum-mtp-zz-probe` done |
| ~19:35 ET | `0212cb4` | GGUF viability triage + drafter alternatives survey land (`mad-science/GGUF-VIABILITY-TRIAGE.md`, `mad-science/DRAFTER-ALTERNATIVES-1026.md`); window-4 baseline boots receipted |
| ~19:45 ET | `4447a7d` | TP=4 head-to-head receipts-only doc lands (`mad-science/TP4-HEAD-TO-HEAD-1025.md`), no new boots |
| ~20:20 ET | *(this commit)* | **Knapcio 1017 adoption SHIPPED**: production overlay = `canary-roce-aff52fa5` (`sha256:3f4480818acb…`, gate green, health-port patch lesson recorded — first trial build `21d1bf34…` shipped unpatched boot.py, serving unaffected); adoption boot verdict on landed cells: C1 64.08 agg / C10 152.24 agg / house 36/37 / needles 32k+131k 10/10 — all bars clear; 983k rung still in flight, not a ship gate; bars/receipts in `recipes/ds4/README.md`, decision in `TODO.md`, record in `DEEPSEEK.md` §5; vLLM cancellation record carries the owner's verbatim words, `TODO:773` §2(a) annotated MOOTED |
| ~20:14 ET | `4225e77` | kev-0.8b boot-killing port collision fixed (8008 = beegfs-mgmtd on mgmt nodes; moved to 8021) + `/health` route registered for sparkrun's probe |
| ~20:16 ET | `43ef022` | Queue: `ornith-toolcall-ohmympi-triage` added (owner directive, tier 3) |
| ~20:16 ET | `d91ea2f` | Queue: kev-bind-conflict-fix done; h2h gap tasks + mellum-speedup-search state |
| ~20:17 ET | `5284211` | Queue: needle-131k/983k rerun done — adoption boot 32k/131k 10/10 on the shipped overlay; 983k appends when its wrapper lands |
| ~20:18 ET | `e4b6128` | Adoption records: C1 edge caveat (64.08 clears ≥ 64.0 by +0.08, no headroom claimed), C10 152.24 |
| ~20:18 ET | `f2e743c` | Queue: adapter trial done — adoption shipped `0326719`; flag track unblocked on the aff52fa5 overlay |
| ~22:56 ET | `2fc54a7` | Records corrected: GLM-Flash 'TEB 14/15' WITHDRAWN as contaminated (it scored the lingering 3bpw serve); root cause = Flash checkpoint pin `078455ff` is a config-only stub fleet-wide (deterministic launcher ValueError, not a memory wedge); 175.7 GB body refetch flown |
| ~23:07 ET | `f656e8d` | Mellum Q8_0 draft-head discrepancy resolved with a same-window pair |
| ~23:21 ET | `0a3b4b6` | Queue: needle redo boot live on the refetched body (cause closed with per-node du evidence); 3bpw rerun chained |
| ~00:23 ET | `de99b52` | GLM 3bpw launcher: metrics bridge (live monitor scrape for TensorFold arms) |
| ~00:23 ET | `49714f2` | Qwen-Image launcher bound to the pinned snapshot dir offline (`resolve_snapshot()`) |
| ~00:23 ET | `0211825` | Queue: needle row correction — live cells are the 3bpw arm; flash arm chained next |
| ~00:32 ET | `22a6328` | Qwen-Image demo row landed; LTX-2.5 spare cell queued |
| ~01:03 ET | `21e5ec6` | TODO Runtimes: keep-alive dead-boot detection gap recorded as a lane observation |
| ~01:04 ET | `7c42590` | Metrics bridge: survive the pre-ready window; never print an unread number |
| ~01:09 ET | `ffa5518` | Last blocked media demo row closed: LTX-2.5 T2V landed on `.35` |
| ~01:24 ET | `1643410` | Queue: survey answers applied — h3-quartet-retry / chunk-32768-overlay-reprobe / main-image-boot-gate re-queued; byte-repro annotated (content comparison is the path); bridge generalization sequenced |
| ~01:26 ET | `f532980` | Mellum zz- probe re-pinned to the Q8_0 MTP head, sweep recorded |
| ~01:26 ET | `d2adf8f` | Survey answers folded into TODO dated advisories (12 rows) |
| ~01:29 ET | `007a141` | Literal-sha guard exempts the `-md` draft-head sha (gate green again) |
| ~02:05 ET | `4c222bf` | Pool-deletion policy (owner directive): models deletable only when every reference lives in attic — AGENTS.md Node hygiene carries the rule, TODO advisory row 13 quotes it |
| ~02:07 ET | `3e14f4c` | c3-only dsv41 adapter exclusions gated behind `DSV41_C3_EXCLUDES` in the overlay launcher |
| ~02:15 ET | `210d184` | 15.7G second-boot ladder landed; two authored spares rows |
| ~02:20 ET | `8da1c85` | Kolibri battery second boot reproduces 37/37 |
| ~03:28 ET | `2ae0512` | Queue: 983k rung wrapper-capped (rc=124 = wrapper timeout, not an arm failure); re-run at 14400 s on the warm 3bpw serve |
| ~07:17 ET | `a2740d6` | Queue: 983k recorded wrapper-capped ×2 (unmeasurable in-window); Flash arm takes 32k/131k only; quartet releases to the re-port |
| ~07:58 ET | `0f0ee98` | h2h: GLM needle numbers folded — both arms 32k/131k 10/10 PASS; 983k wrapper-capped on both; needle row done; quartet released to the re-port |
| ~02:07 ET | `3fe4457` | Boot watchdog lands: stdlib-only dead-boot killer (endpoint + serve-pid + io deltas, loading-vs-dead rule, grace before stop-by-id) with a 7-test decision-table guard |
| ~02:1x ET | `4d88848` | Docs: boot watchdog made the standard boot chain (boot → pre-flight → watchdog → cells → stop by id; cold 510 GB load needs 1800 s grace) |
| ~02:3x ET | `40e4911` | Reranker 2B solo measured under the boot watchdog |
| ~02:4x ET | `cd9a9b4` | Boot watchdog: two literal rail IPs scrubbed from docstring/help (tracked-address-hygiene gate red since `3fe4457`; placeholders only) |
| ~09:4x ET | `9e63795` | Queue: candidate 6 done (2.96 % paired saving, knob wired, 10/10 both arms); S1 running |
| ~09:5x ET | `d84fa37` | Queue: S1 done (cache-report = reporting fix, cache already reusing), S2 done (lpm null), S3 done-negative (min-free-slots-delay loses 7–11 % same-line) |
| ~09:5x ET | `a70b1d4` | Docs: window-4 flag-track verdicts folded into tracked docs, dated entries with receipt pointers (gate 1005 OK) |
| ~10:51 ET | `5315226` | Queue: h3-quartet-retry parked queued (priority yield) — first four-rank H3 cell COMPLETED (denoise 8/8, 113.9 s TP=4, #46390 refuted); bind fix + request shape recorded as resume state |
| ~10:56 ET | `7864ab7` | TODO advisory row 18 + clock readout caveat (survey round-2 fold) |
| ~10:57 ET | `ea0785c` | `--enable-cache-report` SHIPPED on the knapcio TP4 serve line (owner ruling): recipe + launcher valueless-flag table + guard both ways |
| ~10:57 ET | `9e392bf` | Boot watchdog: plain python added to SERVE_PATTERN (plain-python serve children were invisible; endpoint stays authoritative) |
| ~11:02 ET | `a481680` | zz- probe arm added for the main-image boot-gate (Spark-X2.6-4B bf16 on `sglang-main-arm64:6563312`, control numbers named) |
| ~11:05 ET | `33f7336` | TODO advisory row 19 (survey round-3 fold: ship ruling pre-staged, battery base, continuation vs drain, Beam parked, spares through endgame) |
| ~11:13 ET | `1a8f5e7` | Queue: main-image-boot-gate done **PASS** (main-tree image carries the Spark-X2.6 control shape at ladder+house parity, `.30`); glm-flash DEFERRED to next window (owner ruling) |
| ~12:14 ET | `865863e` | TODO advisory row 20 (survey round-4 fold: bars-clear non-inferiority rule, ship digest `644cb802…`, chunk-32768 ships-after-battery-gate, sessions killed at drain) |
| ~12:23 ET | `2fa8c59` | Board refresh 12:21 ET (chunk reprobe live, main-image-boot-gate PASS, attempt-8 staged) |
| ~12:33 ET | `f3cf420` | chunk-32768 reprobe DONE — faster prefill but pool −72%, needles TRUNCATED: NOT shippable, 16384 line unchanged (DEEPSEEK s9 addendum) |
| ~14:32 ET | `6ffdda8` | c3 re-port record: TERMINAL BLOCKED no-ship landed in DEEPSEEK §17/§19, queue, ds4 README (DeepGEMM SM100-only) |
| ~14:41 ET | `0123dda` | ds4 knob gates spent once on the shipped line: S1 evidence shape reproduced; candidate6 battery 37/37 both arms, 0 flips — parity PASS, knob ships; `-o extra_args=` inert root cause noted |