# Board — generated 2026-10-26 20:21 ET

## In flight

| where | owner | what |
|---|---|---|
| census | board-keeper | **20:21 ET 2026-10-26, all six nodes (read-only `ssh` + `docker ps` per node + `nvidia-smi`)**: `.30` — nothing live (no reservation); `.31`–`.34` — `sparkrun_c989632ede4f538e_06d0703ef003` up ~1 h (adoption serve idle after TRIAL-DONE, GPUs 0 %); `.35` — nothing live (no reservation) — spares idle + no successor claimed on the idle quartet = **dead-time signature**, reported in the 20:21 cycle |
| adoption boot (idle) | tp4-recovery | ship landed `0326719` (canary-roce-aff52fa5 is production); boot `c989632ede4f538e_06d0703ef003` still up with all cells complete and **no successor task claimed** — holder should stop it by task id or hand the quartet to the next claimant (flag-track rows re-based on the shipped overlay are the natural next work) |
| tp4-single media/GGUF work | tp4-single | solo boots ended this hour: `.30` Kokoro demo boot and the `.35` Mellum-upstream boot are both down after their cells (media DEMO receipts `e32114c`, Mellum retest negative `edfb2ea`, GGUF/drafter docs `0212cb4`) |

## Work queue

Mirrors `mad-science/queue.json` via `tools/task-queue.py` (check **ok**, 29 tasks, at 20:21). Ship landed: `ds4-upstream-adapter-trial` **done** (`f2e743c`, ship commit `0326719`); `w4-b12x-parity`, `dsv41-vllm-ship-recipe`, `b12x-vllm-tuning-round` withdrawn (`f75ae31`); `mellum-mtp-zz-probe`, `w4-s0-control`, Beam cells remainder, `h2h-ds4-needle-131k-983k-rerun` **done** (`5284211`). Flag track (candidate 6, S1, S2, S3) still carries `blocked` state in the ledger post-ship — mirrored below. Running/queued now: `ds4-knapcio-byte-reproducible` claims **running** on a single node but `.30`/`.35` are both empty — wedge-shaped-lie flagged; `ds4-adapter-report-gate` (the 20 h re-port, queued); build-gated arms 3/5 (queued, w 3.00); new h2h tiers (glm tools/needle/house/doc-refresh queued):

| job | node cost | holds | state |
|---|---|---|---|
| 1. `ds4-knapcio-byte-reproducible` — deterministic knapcio build (bytecode off, `SOURCE_DATE_EPOCH`) | single | tp4-recovery (claimed) | ledger says **running** but no container exists on `.30`/`.35` — flagged |
| 2. w4-candidate6-reasoning-effort | quartet | tp4-recovery | blocked (ledger state post-ship — verify the blocker flipped) |
| 3. w4-s1-cache-report | quartet | tp4-recovery | blocked (same) |
*(Later rows: S2 lpm, S3 min-free-slots-delay (blocked, w 1.50); build-gated survey arms 3/5 (queued, w 3.00); h2h tiers — `h2h-glm-tools-leg` (w 1.50), `h2h-glm-needle-3rungs` (w 2.50), `h2h-glm-flash-house-recipe` (w 1.50), `h2h-doc-refresh` (w 0.50); `ds4-adapter-report-gate` (the 20 h re-port, w 14.00-class, queued); `ornith-toolcall-ohmympi-triage` (owner-directed, `43ef022`). Done in the ledger: adapter trial, mellum probe, S0, Beam remainder, needle rerun; withdrawn: b12x parity/ship-recipe/tuning-round.)*

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