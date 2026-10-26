# Board — generated 2026-10-26 01:59 ET

## In flight

| where | owner | what |
|---|---|---|
| census | board-keeper | **01:59 ET 2026-10-26, all six nodes (read-only `ssh` + `docker ps` per node + `nvidia-smi`)**: `.30` — nothing live (no reservation) (a 96 % GPU reading at the instant is the known teardown-sampling artifact; no compute app registered); `.31`–`.34` — `sparkrun_7d9a3a61b33a29e4_c7091cac7b11` up ~3 h, **all four GPUs 96 %** (GLM 3bpw needle rerun, 983k rung in flight under its 7200 s cap); `.35` — nothing live (no reservation) — spares-lane between cells: spares escalation fired (both spares empty while window work runs), re-queue work available |
| glm-needle-3rungs rerun | tp4-recovery | queue `h2h-glm-needle-3rungs` (**running**): GLM 3bpw arm, rungs 32k **PASS** (rc=0, 04:29Z) and 131k **PASS** (rc=0, 05:31Z, ~62 min), 983k in flight (~30 min at last check); Flash arm's rungs chained next on the refetched 175.7 GB body (owner ruling: BOTH arms in the h2h doc) |
| spares-lane close-out | spares-lane | media demo suite **closed — all five arms** landed (Kokoro RTF 0.64, humanizer, drama-3, Qwen-Image demo `22a6328`, LTX-2.5 T2V `ffa5518`); embed ladder measured (`qwen3vl-embed-ladder` RECEIPT, bench v3); Mellum levers 2/5 measured-closed, zz- probe re-pinned to the Q8_0 MTP head (`f532980`); both spares went idle after their cells — next single-node work is the re-queued window-2 rows |
| adapter re-port | tp4-recovery | **STARTED** per owner ruling (survey #4): `recipes/ds4/mods/dsv41-sglang-overlay/launcher.py` has uncommitted edits in flight (20 h estimate, re-port + gate update) |
| window-2/3 re-queue holder | tp4-recovery | survey #5 re-queued `h3-quartet-retry`, `chunk-32768-overlay-reprobe`, `main-image-boot-gate` (`1643410`); Beam staging stays parked |

## Work queue

Mirrors `mad-science/queue.json` via `tools/task-queue.py` (check **ok** at 01:59). Owner survey folded (`d2adf8f`): window-2 rows re-queued (h3-quartet-retry, `chunk-32768-overlay-reprobe`, `main-image-boot-gate`; Beam staging stays parked), byte-repro narrowed to `ds4-repro-config-created` (image-ID repro dropped — content comparison is the path), bridge generalization sequenced, spares policy = worker discretion. Running: `h2h-glm-needle-3rungs` (boot above). Scheduler top-3 (all queued, tier dsv4.1-1017): candidate 6, S1 cache-report, S2 lpm (each w 1.50):

| job | node cost | holds | state |
|---|---|---|---|
| 1. w4-candidate6-reasoning-effort — `reasoning_effort` high on the main-image base | quartet | tp4-recovery | queued (w 1.50, scheduler top) |
| 2. w4-s1-cache-report — prefix-cache truth (`--enable-cache-report`) | quartet | tp4-recovery | queued (w 1.50) |
| 3. w4-s2-lpm — lpm alongside `--enable-cache-report` | quartet | tp4-recovery | queued (w 1.50) |
*(Later rows: S3 min-free-slots-delay (queued, w 1.50); `chunk-32768-overlay-reprobe` (w 2.00) and `ds4-repro-config-created` (w 2.00); build-gated survey arms 3/5 (w 3.00); `ds4-adapter-report-gate` (the 20 h re-port, **started**, w 14.00-class); **running**: `h2h-glm-needle-3rungs` (w 2.50, boot above); `h2h-glm-flash-house-recipe` (w 1.50), `glm-flash-concurrency-degradation-search` (w 5.00), `h2h-doc-refresh` (w 0.50), `main-image-boot-gate` (w 1.50), `ornith-toolcall-ohmympi-triage` (w 3.00). Done in the ledger: adapter trial, byte-reproducible, mellum probe + speedup levers, S0, Beam remainder, ds4 needle rerun; withdrawn: b12x parity/ship-recipe/tuning-round.)*

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