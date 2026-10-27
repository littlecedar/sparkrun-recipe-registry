# Board — generated 2026-10-27 02:00 ET

## In flight

| where | owner | what |
|---|---|---|
| ds4 quartet, `.31`–`.34` | unattributed session — sparkrun job `c989632ede4f538e_b4e3c94ef77c` | `@littlecedar/deepseek-v4.1-flash-knapcio-tp4-1m-sglang` (tp=4) on `littlecedar/dgx-spark-dsv41:canary-roce-aff52fa5`, up 2 h, all four ranks healthy. Probed 02:00 ET: `.31` `/v1/models` **HTTP 200**, `/tmp/sparkrun_serve.log` 3,385 lines with mtime 02:01 ET — writing, not dead. **Still no `.scratch/fleet-window.lock` in this tree** (see census drift) |
| ornith solo, `.30` | unattributed peer session — sparkrun job `78c7e2fa335a63e5_6d11c3b8b5c1` | `@littlecedar/ornith-1.5-35b-a3b-nvfp4-dflash2-sglang` (tp=1) booted ~01:50 ET, image `sha256:fd8439732b16…`. Same task-id family as the 2026-10-26 tool-call triage boot (`…_35f2cfc5f912`). **Settled by its own serve log (01:51:52 ET):** `using buffered reads instead of O_DIRECT (set FASTSAFETENSORS_ODIRECT=1 to force)` — this boot does **not** serve the `f70c3b5` ODIRECT line, so whatever it measures is the pre-`f70c3b5` recipe |
| host fetch, `.30` | unattributed peer session | `hf download unsloth/Qwen3.8-Flash-Next-GGUF` (pid 1021443); the earlier `unsloth/Qwen3.8-27B-GGUF` fetch (pid 1013773 at 01:16) finished and BeeGFS avail moved 11 TB → 10 TB. No container, nothing in `queue.json` owns it |
| census | sparkrun-recipe--1209711 | **02:00 ET 2026-10-27, all six nodes (read-only ssh)**: 5 containers — `.30` **1** (ornith solo), `.31`–`.34` **1 each** (quartet), `.35` **0, nothing live (no reservation)**. Root avail 1.1–1.8 TB; BeeGFS pool 10 TB. **Drift, second cycle running: two live sparkrun jobs, zero `.scratch/fleet-window.lock`, both holders unnamed** — escalated 01:16 and again here |

## Work queue

| job | node cost | holds | state |
|---|---|---|---|
| `flint-four-arm-comparison` — Flint 40B-A2.5B vs Mellum 12B-A2.5B, Ornith-1.5-35B-A3B and Ornith-1.5-122B on one instrument | single | — | queued |
| `ornith-122b-decoders-route` — SGLang arm + `incoai` DFlash2 drafter (route verdict C1 ≥ 51, falsifier C1 < 45) | single | — | queued |
| `ornith-omp-1000turn-longrun` — 300-turn omp tool-calling run on a scratch project, extend to ~1,000 only if clean | single | — | queued |
| `arch-deepgemm-sm12x-paged-sparse` — DeepGEMM SM12x for the paged-sparse logits family (upstream watch) | watch | — | BLOCKED on upstream (TODO row 21) |
| `w4-survey-arm3-indexer-scoring` — SGLang PR #43401 candidate-only indexer scoring | quartet | — | BLOCKED: arch gate (SM12x) |
| `w4-survey-arm5-trtllm-mla` — TRT-LLM sparse-MLA attention backend | quartet | — | BLOCKED: arch gate (SM12x) |
| `h2h-glm-flash-house-recipe` — GLM-5.3-Flash 4bpw TP=4 house battery @4096 thinking-on | quartet | — | queued |
| `glm-flash-concurrency-degradation-search` — GLM-5.3-Flash variants that do not degrade with concurrency | quartet | — | queued |
| `h2h-doc-refresh` — TP4-HEAD-TO-HEAD open-cells note per landed cell | single | — | queued |
| `tensorfold-metrics-bridge-generalization` — metrics bridge for both GLM TensorFold launchers + a vLLM-OMNI media equivalent | single | — | queued |
| `h2h-beam-house-and-bfcl-category` — Beam-1.0 NVFP4 house @4096 + BFCL category summary | quartet | — | queued |
| `h3-quartet-retry` — MiniMax-H3 four-rank video probe (two unprobed axes) | quartet | — | queued, idle-only |
| `h2h-second-boot-ladder` — controlled second-boot ladder per arm (sigma column) | quartet | — | queued |

## Landed this session

| time ET | commit | one clause |
|---|---|---|
| 00:40 ET | `7d2225e` | Flint four-arm comparison item added to `mad-science/TODO.md` §explore — roster with the on-file baselines flagged re-measure-not-quote, one instrument across all four arms, today's node fences |
| 00:44 ET | `efa5ede` | Ornith-1.5-122B decoder item + queue row: an SGLang arm against `incoai/Ornith-1.5-122B-DFlash2`, sized at the 35B's own ~2.9× draft ratio (≈79 t/s vs the 69.28 bar) |
| 00:47 ET | `ee6806b` | 122B route falsifier pre-registered before any boot (C1 ≥ 51 wins, C1 < 45 kills the route) and the draft's config read rather than assumed — vocab 248,320 / 48 layers / 262,144 window all match the target |
| 00:48 ET | `7485d6f` | corrected the drafter's authorship (`incoai` publishes the DFlash2 method; the 35B's shipped head is `jzinno`'s) and refuted the stale "only Ornith DFlash2 drafter" line in `attic/ornith/AGENTS.md` with a dated pointer |
| 00:55 ET | `8d23505` | 1,000-turn omp tool-calling trial added to the register and the queue — capture proxy, per-turn JSONL ledger, pre-registered verdicts, 12 h single node |
| 01:15 ET | `e2ea46e` | round-6 owner rulings folded as `TODO.md` row 23 (`SURVEY6 Q1`–`Q8`): all three new items next window, `.30`+`.35` in parallel, run staged at 300 turns, pattern-not-count verdict, Flint and 122B ship bars |
| 01:16 ET | `5abc1d6` | board tick: fresh probed census (quartet live, `.30`/`.35` idle), queue reconciled — `pool-prefetch-missing-bodies` closed on ledger evidence, `flint-four-arm-comparison` + `ornith-122b-decoders-route` added as scheduler rows |
| 01:53 ET | `f70c3b5` *(peer session)* | ornith-1.5-35b-a3b-nvfp4-dflash2-sglang.yaml gains `FASTSAFETENSORS_ODIRECT: 1` (1 line) — recipe edit, boot verification pending as the solo `.30` boot above |