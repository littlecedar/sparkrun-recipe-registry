# Board — generated 2026-10-29 03:14 ET

## In flight

| where | owner | what |
|---|---|---|
| census | this tick — documentation session (opened 2026-10-29, first commit `6867d1b` at 03:03 ET) | **03:05 ET, all six nodes (read-only ssh)**: **no research containers fleet-wide**, 0 volumes. The quartet `.31`–`.34` runs the **production serve** — task `c989632ede4f538e_b4e3c94ef77c` (TP=4), image `littlecedar/dgx-spark-dsv41:canary-roce-aff52fa5`, `Up 2 days (healthy)` — a shipped-arm serve, excluded by directive, not absent. `.30` (head) and `.35`: **nothing live (no reservation)**. Root avail `.30`→`.35`: 1.6 / 1.9 / 2.0 / 1.9 / 1.2 / 1.3 TB |

## Work queue

| job | node cost | holds | state |
|---|---|---|---|
| `tp12-campaign-staging` — stage the 32 gated TP≤2 arms and run them; 11 of 42 measured so far (6 h) | single | — | staging is a **no-op** on models, but the image claim was too strong: re-checked 2026-10-29 03:10 ET by `docker image inspect`, `.scratch/tp12-campaign/manifest.json` names 15 container refs / **14 distinct digests**, `.30` holds **15/15** and `.35` **14/15** — the miss is the local tag-only build `sglang-main-arm64:6563312`, which has no registry to pull from, so any arm pinned to it is `.30`-only. Manifest `img_ok`/`mod_ok` flags stay stale (30 false / 7 false). Measured count re-derived from the head receipt tree `~/benchmarks/tp12-20261028/`: **10 arm dirs, 20 JSON**, so "11 of 42" over-counts by one. Remaining gate is scheduling only — and both spare nodes are free at 03:10 ET |
| `flint-four-arm-comparison` — Flint 40B-A2.5B vs Mellum 12B-A2.5B, Ornith-1.5-35B-A3B and Ornith-1.5-122B on one instrument (8 h) | single | — | queued |
| `ornith-122b-decoders-route` — SGLang arm + `incoai` DFlash2 drafter (route verdict C1 ≥ 51, falsifier C1 < 45) (3 h) | single | — | queued |
| `ornith-omp-1000turn-longrun` — 300-turn omp tool-calling run on a scratch project, extended to ~1,000 only if clean (4 h) | single | — | **ended at 137/300** — the backlog was exhausted (30 items), not a failure: zero failures of the owner-reported class across all 137 turns. Extension needs a larger backlog (or a cold-boot / post-idle trigger set), so the stage is not closed and ~1,000 turns is not taken |
| `arch-deepgemm-sm12x-paged-sparse` — DeepGEMM SM12x for the paged-sparse logits family (upstream watch) | watch | — | BLOCKED on upstream (TODO row 21) |
| `w4-survey-arm3-indexer-scoring` — SGLang PR #43401 candidate-only indexer scoring (3 h) | quartet | — | BLOCKED: build-gate re-port (owner ruling 2026-10-26) + SM12x arch gate |
| `w4-survey-arm5-trtllm-mla` — TRT-LLM sparse-MLA attention backend (3 h) | quartet | — | BLOCKED: build-gate re-port (owner ruling 2026-10-26) + SM12x arch gate |
| `h2h-glm-flash-house-recipe` — GLM-5.3-Flash 4bpw TP=4 house battery @4096 thinking-on (2 h) | quartet | — | queued |
| `glm-flash-concurrency-degradation-search` — GLM-5.3-Flash variants that do not degrade with concurrency (5 h) | quartet | — | queued, deferred to the next window (owner survey round 3) |
| `h2h-doc-refresh` — TP4-HEAD-TO-HEAD open-cells note per landed cell (0.5 h) | single | — | queued |
| `tensorfold-metrics-bridge-generalization` — metrics bridge for both GLM TensorFold launchers + a vLLM-OMNI media equivalent (1.5 h) | single | — | **queued and unbooted** — `mad-science/queue.json` still lists it `queued` (re-read 2026-10-29 03:10 ET); the 2026-10-28 12:00 ET landed row records the code landed as `4aabfc8` with no arm booted. Dropped from this table by the 03:12 ET write; restored here because the queue has not closed it. It closes when an arm prints the `metrics bridge: matched […]` line |
| `h2h-beam-house-and-bfcl-category` — Beam-1.0 NVFP4 house @4096 + BFCL category summary (3 h) | quartet | — | queued |
| `ds4-shipped-container-digest-pin` — push the local `canary-roce-aff52fa5` overlay under a registry tag, take the manifest digest, write it into `container:` (today tag-only) (0.5 h) | — | — | queued — the serve that is live right now runs that tag |
| `h2h-second-boot-ladder` — controlled second-boot ladder per arm (sigma column) (5 h) | quartet | — | queued |

## Landed this session

| time ET | commit | one clause |
|---|---|---|
| 03:03 ET | `07cecb7` | "Consolidate documentation: contents blocks, dedupe, stale facts" — this tick's archive sweep: nine completed items copied verbatim into `attic/DONE.md` under a new `# 2026-10-29 sweep` (the seven 2026-10-25 unparked retry-queue items, window-4's Beam cells (b)–(d), the OrcaCyber 15.7G ship), the unparked queue section reduced to the archive stub, `QUESTIONS.md` `#18` settled into `TODO.md` §"Settled questions", and five broken relative links repaired (`TODO.md` 3445→3310, `attic/DONE.md` 1206→1382, `QUESTIONS.md` 20→19 lines); line-set check over the original reads 0 unaccounted except the five repaired link lines. One continuity line added to `TODO.md` §Retry queue window 4 at 03:09 ET sits in the working tree, after that commit |
| 03:15 ET | working tree | board refresh — cleared the `Landed this session` table per the session-boundary rule (the prior session's sixteen rows are retired verbatim in `SESSION-RECORD.md` §"Landed rows retired at the 2026-10-29 03:10 ET board refresh", verified there against `git show 07cecb7:mad-science/STATUS.md`), dropped the `h3-quartet-retry` row because `TODO.md` archived that item today as a terminal negative (`attic/DONE.md` §`# 2026-10-29 sweep`: second deadlock repro, filed sgl-project/sglang#46390), and kept the 03:10 ET census and the manifest re-derivation unchanged |
