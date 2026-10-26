# Board — generated 2026-10-26 09:54 ET

## In flight

| where | owner | what |
|---|---|---|
| census | board-keeper | **09:54 ET 2026-10-26, all six nodes (read-only `ssh` + `docker ps` + per-boot workload probe)**: `.30` 0 containers — nothing live (no reservation); `.31`–`.34` — `sparkrun_05929de845c64661_f0ce93059ea0` (node_0–node_3, Up ~17 min, health: starting): **PROBED** — `/v1/models` = **200 on port 30010** (the recipe serves on `127.0.0.1:30010`; an `:8000` probe reads 000 — the recipe's port is the answer), serve = `MiniMaxAI/MiniMax-H3` via sglang-diffusion TP=4; serve log fresh (mtime ~3 min: `Application startup complete`), GPU 0 % at both samples (video lane idle between prefill); `.35` 0 containers — nothing live (no reservation) |
| h3-quartet-retry boot | tp4-recovery | queue `h3-quartet-retry` (**running**, the window-2 re-queue): MiniMax-H3 four-rank video boot live on the quartet under the boot watchdog; rung/cell arming not yet visible — next probe |
| flag track (COMPLETE) | tp4-recovery | all four flag-track cells done and folded into tracked docs (`d84fa37`, `a70b1d4`): **candidate 6** — keep high (2.96 % paired saving, below the 10.6 % precedent, knob wired, 10/10 both arms, 0 flips); **S1** — radix-cache FINDING: the cache was already reusing (the 8.4 s revisit number was a reporting gap; `--enable-cache-report` closes it); **S2** — lpm NULL; **S3** — min-free-slots-delay measured NEGATIVE on same-line A/B (loses 7–11 %) → **do not ship** |
| boot watchdog (TOOL) | tp4-recovery | stdlib-only dead-boot killer landed (`3fe4457`: `/v1/models` + serve-pid liveness + `/proc io` deltas, loading-vs-dead discrimination, 2-consecutive-checks + grace before `sparkrun stop` by literal id, guard tests) and docs made it the standard boot chain (`4d88848`); FIRST LIVE CATCH: correctly discriminated the attempt-3 dead boot from a live load during the c3 chain |
| adapter-report-gate attempt-4 | tp4-recovery | ALIVE (12:56Z, image `sha256:6f93278a…` = parser fix + configurer sm120/121 reconciliation + kernel 0.4.7); root-cause chain recorded in `c3-NOTES.md`: attempt 2 died on the sglang-kernel 0.4.9 ABI import, attempt 3 died on the **DEEPGEMM candidate-indexer gate (`is_sm100=major-10-only`, FALSE on sm_121)**; boot.py healthcheck-port class RULED OUT (line-identical to the shipped patched canary); attempt-map correction recorded (ids had been mislabeled in flight) |

## Work queue

Mirrors `mad-science/queue.json` via `tools/task-queue.py` (check **ok** at 09:54). **Running**: `h3-quartet-retry` (boot above) and `pool-prefetch-missing-bodies` (single, serial hf-download runner). Scheduler top-3 (queued, tier dsv4.1-1017): `chunk-32768-overlay-reprobe` (w 2.00), `ds4-repro-config-created` (w 2.00), `w4-survey-arm3-indexer-scoring` (w 3.00 — build-gated; the c3 work above is its re-port prerequisite). Later: arm 5 trtllm (w 3.00), `ds4-adapter-report-gate` (w 14.00-class, attempt-4 alive), `main-image-boot-gate` (w 1.50), `tensorfold-metrics-bridge-generalization` (w 1.50, new row), `h2h-glm-flash-house-recipe` (w 1.50), `glm-flash-concurrency-degradation-search` (w 5.00), `h2h-doc-refresh` (w 0.50), `h2h-beam-house-and-bfcl-category` (w 2.50). Flag-track rows (candidate6/S1/S2/S3) **done** and removed from the open set:

| job | node cost | holds | state |
|---|---|---|---|
| 1. `chunk-32768-overlay-reprobe` — 32768 prefill-chunk probe on the aff52fa5 overlay | quartet | tp4-recovery | queued (w 2.00, scheduler top) |
| 2. `ds4-repro-config-created` — pin the knapcio image config created stamp | single | tp4-recovery | queued (w 2.00) |
| 3. `w4-survey-arm3-indexer-scoring` — SGLang PR #43401 candidate-only indexer scoring | quartet | tp4-recovery | queued (w 3.00, build-gated — the c3 chain above is its prerequisite) |
*(Later rows: arm 5 trtllm-mla (queued, w 3.00); `ds4-adapter-report-gate` (w 14.00-class, attempt-4 alive); `main-image-boot-gate` (w 1.50); `tensorfold-metrics-bridge-generalization` (w 1.50, new row); `h2h-glm-flash-house-recipe` (w 1.50); `glm-flash-concurrency-degradation-search` (w 5.00); `h2h-doc-refresh` (w 0.50); `h2h-beam-house-and-bfcl-category` (w 2.50); `ornith-toolcall-ohmympi-triage` (w 3.00). **Running**: `h3-quartet-retry` (boot above) + `pool-prefetch-missing-bodies`. Done in the ledger: flag track (candidate6/S1/S2/S3), adapter trial, byte-reproducible, mellum probe + speedup levers, S0, Beam remainder, h2h-glm-needle-3rungs, h2h-glm-tools-leg; withdrawn: b12x parity/ship-recipe/tuning-round.)*

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