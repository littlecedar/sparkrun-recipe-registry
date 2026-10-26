# Board — generated 2026-10-26 20:19 ET

## In flight

| where | owner | what |
|---|---|---|
| census | board-keeper | **20:19 ET 2026-10-26, all six nodes (read-only `ssh` + `docker ps` per node + `nvidia-smi`)**: `.30` — nothing live (no reservation); `.31`–`.34` — `sparkrun_c989632ede4f538e_06d0703ef003` up ~1 h, health: unhealthy (serve answers 200 — see the trial row), GPUs 0 % (cells complete, serve idle); `.35` — nothing live (no reservation) — **spare-node escalation fired in the 20:19 cycle report: both spares emptied while the adapter-trial ship is still pending** |
| adapter-trial boot | tp4-recovery | queue `ds4-upstream-adapter-trial` (**running**, scheduler top; owner deadline: knapcio 1017 adoption shipped by 22:00 ET, hard midnight): cells **COMPLETE — TRIAL-DONE 20:07 ET**: trial ladder rc=0 (C1 tg 64.08 ≥ 64.0 bar; C10 tg 152.24 ≥ 110.5; C1 pp 3891 t/s), house 36/37 (easy 19/19, hard 17/18), needles 3/3 PASS (32768/131072/983040); docker healthcheck still `unhealthy` while rank-0 `/v1/models` answers 200 — serving-with-red-healthcheck, not a dead rank; awaiting the holder's ship commit (none on main as of 20:19) |
| tp4-single media/GGUF work | tp4-single | solo boots ended this hour: `.30` Kokoro demo boot and the `.35` Mellum-upstream boot are both down after their cells (media DEMO receipts `e32114c`, Mellum retest negative `edfb2ea`, GGUF/drafter docs `0212cb4`) |

## Work queue

Mirrors `mad-science/queue.json` via `tools/task-queue.py` (check **ok**, 18 tasks, at 19:56). Scheduler top: `ds4-upstream-adapter-trial` (**running**, w −2.00, blocks the flag track); then candidate 6, S1, S2, S3 (all blocked on it, w 1.50). Later: `mellum-mtp-zz-probe` **done** (upstream d854d98bae retest, rejection stands — `edfb2ea`); build-gated arms 3/5 (w 3.00); `ds4-knapcio-byte-reproducible` (w 4.00); `tp4-head-to-head-2025` (receipts-only doc landed `4447a7d`), `media-demo-workproduct`, `gguf-viability-triage` (doc landed `0212cb4`), `drafter-alternatives-search`; `dsv41-vllm-ship-recipe` and `b12x-vllm-tuning-round` withdrawn by `f75ae31` (b12x route retired to attic/ds4 — parity cancelled, C1 miss recorded 34.04 agg vs 64.0 bar, C10 aggregate identity broken at C≥5); `ds4-adapter-report-gate` rebased onto upstream HEAD. The b12x parity boot is DOWN, replaced by the adapter-trial boot above:

| job | node cost | holds | state |
|---|---|---|---|
| 1. `ds4-upstream-adapter-trial` — canary-roce-aff52fa5 re-pin boot-verify on the shipped 1017 line | quartet `.31`–`.34` | tp4-recovery | **running** (boot live, health: unhealthy flagged above) |
| 2. w4-candidate6-reasoning-effort | quartet | tp4-recovery | blocked by the adapter trial |
| 3. w4-s1-cache-report | quartet | tp4-recovery | blocked by the adapter trial |
*(Later scheduler rows: S2 lpm, S3 min-free-slots-delay (blocked, w 1.50); build-gated survey arms 3/5 (w 3.00); `ds4-knapcio-byte-reproducible` (w 4.00); `tp4-head-to-head-2025` (receipts-only, `4447a7d`), `media-demo-workproduct`, `gguf-viability-triage` (`0212cb4`), `drafter-alternatives-search`; `ds4-adapter-report-gate` rebased. `mellum-mtp-zz-probe` **done**; `w4-b12x-parity`, `dsv41-vllm-ship-recipe`, `b12x-vllm-tuning-round` withdrawn/cancelled by `f75ae31`; S0 and Beam cells remainder **done** in the ledger.)*

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