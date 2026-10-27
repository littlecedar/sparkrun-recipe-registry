# Board — generated 2026-10-27 00:14 ET

## In flight

| where | owner | what |
|---|---|---|
| census | sparkrun-recipe--1110010 | **00:11 ET 2026-10-27, all six nodes (read-only ssh + `docker ps` + `nvidia-smi`)**: 0 containers and 0 % GPU on `.30`–`.35`; nothing live (no reservation) on any node; no `.scratch/fleet-window.lock` exists; root avail 1.3–1.9 TB, BeeGFS pool 11 TB avail |
| host fetch, head | unattributed (peer session) | `.30` runs `hf download unsloth/Qwen3.8-27B-GGUF` (pid 829385, started 00:01:33 ET under an interactive shell from 22:28 Oct 26) + `sparkrun update` / registry fetch (pids 829855/830168, 00:04 ET); no container; not the pool-prefetch runner (that ended `PREFILL-DONE 2026-10-26T00:07Z`, pid gone — ledger `~/benchmarks/cache-prefill-20261026/QUEUE.md`) |

## Work queue

| job | node cost | holds | state |
|---|---|---|---|
| `arch-deepgemm-sm12x-paged-sparse` — DeepGEMM SM12x for the paged-sparse logits family (upstream watch) | watch | — | BLOCKED on upstream (TODO row 21); first in the next-window order |
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
| 23:51 ET | `bd1ce5f` | ds4 knapcio recipe `description:` now names the vendored upstream pin — `knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4 @ aff52fa5 (v2.5+, 2026-10-24)`, verified 12 commits ahead of v2.5 `c3fe50a8` via the GitHub compare API; validate + ds4 guards green |
| 00:03 ET | `77efa5d` | window-4 GLM tool-eval-bench receipts harvested from repo-root litter to `.scratch/tp4-window4/glm-teb/` (3bpw TEB-100 set cited by the board doc + the WITHDRAWN contaminated flash set, kept as negative evidence); citations in `TP4-HEAD-TO-HEAD-1025.md` and `benchmarking/README.md` repointed; `/.omp/extensions/` git-ignored; tree clean |
