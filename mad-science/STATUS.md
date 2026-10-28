# Board — generated 2026-10-27 21:04 ET

## In flight

| where | owner | what |
|---|---|---|
| ds4 quartet, `.31`–`.34` | **production serve** — standing line; no research window declared and none owed (the lock rule binds declared research windows; settled `TODO.md` `#4` recognises these ranks serving the fleet's own inference, `#51` defines the stand-down). sparkrun job `c989632ede4f538e_b4e3c94ef77c` | `@littlecedar/deepseek-v4.1-flash-knapcio-tp4-1m-sglang` (tp=4) on image `littlecedar/dgx-spark-dsv41:canary-roce-aff52fa5` — **the recipe's tag; re-read 21:03 ET that `.31`'s copy still reports `RepoDigests: []`** (only the local image id `sha256:3f4480818acb…`; no manifest digest exists to pin — queue row `ds4-shipped-container-digest-pin`) — container created 00:14 ET (`2026-10-27T04:14:27Z`), **`Up 21 hours (healthy)`** on all four ranks at 21:01 ET. Probed 21:02 ET: `.31` `/v1/models` **200** → `deepseek-ai/DeepSeek-V4.1-Flash-1017`; `.32`–`.34` `/health` **200** / `/v1/models` **404** (the TP=4 follower shape) |
| census | this tick — session `…00-44-33Z_01a17ff7` (opened 20:44 ET) | **21:01 ET, all six nodes (read-only ssh)**: 4 containers — `.31`–`.34` **1 each** (production quartet, `Up 21 hours (healthy)`); `.30` and `.35` **0, nothing live (no reservation)**. Root avail `.30`→`.35`: 1.7 / 1.9 / 1.9 / 1.8 / 1.2 / 1.3 TB (low `.34` 1218 G); BeeGFS pool **11 TB** free on every node; `ps` at 21:01 ET shows **no `hf download`/`hf sync` process** on any of the six. Volumes **0 fleet-wide** |

## Work queue

| job | node cost | holds | state |
|---|---|---|---|
| `flint-four-arm-comparison` — Flint 40B-A2.5B vs Mellum 12B-A2.5B, Ornith-1.5-35B-A3B and Ornith-1.5-122B on one instrument (8 h) | single | — | queued |
| `ornith-122b-decoders-route` — SGLang arm + `incoai` DFlash2 drafter (route verdict C1 ≥ 51, falsifier C1 < 45) (3 h) | single | — | queued |
| `ornith-omp-1000turn-longrun` — 300-turn omp tool-calling run on a scratch project, extended to ~1,000 only if clean (4 h) | single | — | queued |
| `arch-deepgemm-sm12x-paged-sparse` — DeepGEMM SM12x for the paged-sparse logits family (upstream watch) | watch | — | BLOCKED on upstream (TODO row 21) |
| `w4-survey-arm3-indexer-scoring` — SGLang PR #43401 candidate-only indexer scoring (3 h) | quartet | — | BLOCKED: arch gate (SM12x) |
| `w4-survey-arm5-trtllm-mla` — TRT-LLM sparse-MLA attention backend (3 h) | quartet | — | BLOCKED: arch gate (SM12x) |
| `h2h-glm-flash-house-recipe` — GLM-5.3-Flash 4bpw TP=4 house battery @4096 thinking-on (2 h) | quartet | — | queued |
| `glm-flash-concurrency-degradation-search` — GLM-5.3-Flash variants that do not degrade with concurrency (5 h) | quartet | — | queued, deferred to the next window (owner survey round 3) |
| `h2h-doc-refresh` — TP4-HEAD-TO-HEAD open-cells note per landed cell (0.5 h) | single | — | queued |
| `tensorfold-metrics-bridge-generalization` — metrics bridge for both GLM TensorFold launchers + a vLLM-OMNI media equivalent (1.5 h) | single | — | queued |
| `h2h-beam-house-and-bfcl-category` — Beam-1.0 NVFP4 house @4096 + BFCL category summary (3 h) | quartet | — | queued |
| `h3-quartet-retry` — MiniMax-H3 four-rank video probe (baseline cell completes since 2026-10-26; axes optional) (4 h) | quartet | — | queued — needs the quartet, which the production serve holds |
| `ds4-shipped-container-digest-pin` — push the local `canary-roce-aff52fa5` overlay under a registry tag, take the manifest digest, write it into `container:` (today tag-only) (0.5 h) | — | — | queued |
| `h2h-second-boot-ladder` — controlled second-boot ladder per arm (sigma column) (5 h) | quartet | — | queued |

## Landed this session

| time ET | commit | one clause |
|---|---|---|