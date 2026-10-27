# Board — generated 2026-10-27 13:10 ET

## In flight

| where | owner | what |
|---|---|---|
| ds4 quartet, `.31`–`.34` | unattributed session — sparkrun job `c989632ede4f538e_b4e3c94ef77c` | `@littlecedar/deepseek-v4.1-flash-knapcio-tp4-1m-sglang` (tp=4) on `littlecedar/dgx-spark-dsv41:canary-roce-aff52fa5` — the shipped pin — up 13 h, all four ranks healthy. Probed 13:07 ET per the row-15 rule: `.31` `/v1/models` **200**; `.32`–`.34` follower `/health` **200** (`/v1/models` 404 there is the follower shape, not a fault); serve logs mtime 13:06–13:07 ET carrying live in-container Engram telemetry (layer 14, hit rate 84.9 / 77.3 / 71.1 % on TP1–3), 5–6 `sglang` procs per rank. **No `.scratch/fleet-window.lock` — third refresh cycle reporting it** |
| census | this tick — session `…16-46-35Z_01a17e41` | **13:01–13:08 ET, all six nodes (read-only ssh)**: 4 containers — `.31`–`.34` **1 each** (quartet); `.30` and `.35` **0, nothing live (no reservation)**, verified after the ornith solo + mellum stops at 13:04 ET. Root avail 1.2–1.9 TB (low `.34` 1193 G); BeeGFS pool **11 TB** (10 TB at 02:00 — the `.30` `unsloth/Qwen3.8-Flash-Next-GGUF` fetch finished, no `hf download` process left). One orphan anonymous volume on `.35` (4 KB, created 2026-10-22 01:12) removed; `.30`/`.35` volume counts now 0 |

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
| `h3-quartet-retry` — MiniMax-H3 four-rank video probe (baseline cell completes since 2026-10-26; axes optional) | quartet | — | queued, idle-only |
| `h2h-second-boot-ladder` — controlled second-boot ladder per arm (sigma column) | quartet | — | queued |

## Landed this session

| time ET | commit | one clause |
|---|---|---|
| 02:05 ET | `ba78d62` *(peer commit)* | the `.30` ornith solo's O_DIRECT question settled from its own serve log — it loaded with buffered reads, so it never served the `f70c3b5` line |
| 12:54 ET | `787cb7e` | mellum + humanizer move off the deprecated `--no-mmap` to `--load-mode none` (same policy, `common/arg.cpp:2672`); the `.35` boot that raised the warning had launched the published ref, before this landed |
| 12:55 ET | `9f065d4` | all 11 llama.cpp arms swept — none other carries the deprecated spelling; the upstream Dockerfile help note becomes ref-agnostic and the GGUF note gets dated pointers |
| 13:04 ET | — (stops) | ornith solo `78c7e2fa…` and mellum `a16b25d0…` stopped by id at owner instruction; `.30`/`.35` verified at 0 containers and 0 volumes |