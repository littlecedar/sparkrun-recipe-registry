# Board — generated 2026-10-27 15:01 ET

## In flight

| where | owner | what |
|---|---|---|
| ds4 quartet, `.31`–`.34` | **production serve** — standing line, no research window declared and none owed (the lock rule binds declared research windows; `QUESTIONS.md` `#4` names this the production serve). sparkrun job `c989632ede4f538e_b4e3c94ef77c` | `@littlecedar/deepseek-v4.1-flash-knapcio-tp4-1m-sglang` (tp=4) on image `littlecedar/dgx-spark-dsv41:canary-roce-aff52fa5` — **the recipe's tag; re-verified 15:01 ET that `.31`'s copy still reports an empty `RepoDigests`** (only the local image id `sha256:3f4480818acb…`; no manifest digest exists to pin — queue row `ds4-shipped-container-digest-pin`) — container created 00:14 ET, **`Up 15 hours (healthy)`** on all four ranks. Probed 15:01 ET: `.31` `/v1/models` **200** → `deepseek-ai/DeepSeek-V4.1-Flash-1017`; `.32`–`.34` **`/health` 200 / `/v1/models` 404** (the follower shape) |
| census | this tick — session `…17-34-11Z_01a17e6d` | **15:00–15:01 ET, all six nodes (read-only ssh)**: 4 containers — `.31`–`.34` **1 each** (production quartet, `Up 15 hours (healthy)`); `.30` and `.35` **0, nothing live (no reservation)**. Root avail `.30`→`.35`: 1.7 / 1.9 / 1.9 / 1.8 / 1.2 / 1.3 TB (low `.34` 1218 G); BeeGFS pool **11 TB** free on every node, and `ps` at 15:01 ET shows **no `hf download`/`hf sync` process** on any of the six. Volumes **0 fleet-wide** — the six `.34` orphans cleared at 14:04 are still gone |

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
| `ds4-shipped-container-digest-pin` — push the local `canary-roce-aff52fa5` overlay under a registry tag, take the manifest digest, write it into `container:` (today tag-only) | — | — | queued |
| `h2h-second-boot-ladder` — controlled second-boot ladder per arm (sigma column) | quartet | — | queued |

## Landed this session

| time ET | commit | one clause |
|---|---|---|
| 14:09 ET | `8fb4bf4` | re-measured the two figures `dc5bc48` had carried: `.32`–`.34` `/health` 200 / `/v1/models` 404 at 14:07 ET, and no `hf download`/`hf sync` process on any node at 14:08 ET |