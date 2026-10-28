# Board — generated 2026-10-28 11:37 ET

## In flight

| where | owner | what |
|---|---|---|
| census | this tick — session `…03-21-32Z_01a18086` (opened 23:21 ET) | **11:36 ET, all six nodes (read-only ssh)**: **1 research container** — `.30` the yarn-1m omp-trial serve; `.35` released cleanly by the finished k2-7b arm (0 containers, 0 volumes). The production serve on `.31`–`.34` (tag `canary-roce-aff52fa5`, task `c989632e…`) is excluded from that count by directive, not absent. Root avail `.30`→`.35`: 1.5 / 1.8 / 1.9 / 1.7 / 1.2 / 1.3 TB; volumes **0 fleet-wide** |
| `.30` | this session | **ornith-1.5-35b-a3b-nvfp4-yarn-1m** serve for the omp tool-calling trial, task `78c7e2fa…92518412c0d2`, `/v1/models` max_model_len 1000000 (identity proven). Trial stage 1 **halted at 13 turns**: the run self-terminated after writing `DONE.md` because the harness workspace was a broken slice (630 tests, 464 import errors) and the backlog items were comment-only — a harness defect, not a model signal. Workspace rebuilt as a full-tree scratch copy with a green baseline; relaunch in progress. Ledger `~/benchmarks/ornith-longrun-20261028/stage1-ledger.jsonl` (13 turns, 47 tool calls, 0 invalid JSON, 0 empty streams, depth 4→63 measured 11:15 ET) |

## Work queue

| job | node cost | holds | state |
|---|---|---|---|
| `tp12-campaign-staging` — stage the 32 gated TP≤2 arms (11 image pulls + 5 model fetches) and run them; 11 of 42 measured so far (the previously failed 7B-uno arm now measures), all 9 TP=2 arms gated (6 h) | single | this session | running — `k2-horizon-7b-fp8-uno` unblocked by completing its incomplete pool snapshot (now measuring on `.35`); **staging pulls still not started**, and the failure class generalises: a *present-but-partial* revision fails as an opaque engine error, so the five named missing repos are not the whole gap |
| `flint-four-arm-comparison` — Flint 40B-A2.5B vs Mellum 12B-A2.5B, Ornith-1.5-35B-A3B and Ornith-1.5-122B on one instrument (8 h) | single | — | queued |
| `ornith-122b-decoders-route` — SGLang arm + `incoai` DFlash2 drafter (route verdict C1 ≥ 51, falsifier C1 < 45) (3 h) | single | — | queued |
| `ornith-omp-1000turn-longrun` — 300-turn omp tool-calling run on a scratch project, extended to ~1,000 only if clean (4 h) | single | this session | running — serve live on `.30`; **stage 1 halted at 13 turns** by a harness defect (broken workspace slice + comment-only backlog), not a model signal; relaunching on a full-tree scratch copy |
| `arch-deepgemm-sm12x-paged-sparse` — DeepGEMM SM12x for the paged-sparse logits family (upstream watch) | watch | — | BLOCKED on upstream (TODO row 21) |
| `w4-survey-arm3-indexer-scoring` — SGLang PR #43401 candidate-only indexer scoring (3 h) | quartet | — | BLOCKED: arch gate (SM12x) |
| `w4-survey-arm5-trtllm-mla` — TRT-LLM sparse-MLA attention backend (3 h) | quartet | — | BLOCKED: arch gate (SM12x) |
| `h2h-glm-flash-house-recipe` — GLM-5.3-Flash 4bpw TP=4 house battery @4096 thinking-on (2 h) | quartet | — | queued |
| `glm-flash-concurrency-degradation-search` — GLM-5.3-Flash variants that do not degrade with concurrency (5 h) | quartet | — | queued, deferred to the next window (owner survey round 3) |
| `h2h-doc-refresh` — TP4-HEAD-TO-HEAD open-cells note per landed cell (0.5 h) | single | — | queued |
| `tensorfold-metrics-bridge-generalization` — metrics bridge for both GLM TensorFold launchers + a vLLM-OMNI media equivalent (1.5 h) | single | this session | running — blueprint stage; implementation next, no GPU needed |
| `h2h-beam-house-and-bfcl-category` — Beam-1.0 NVFP4 house @4096 + BFCL category summary (3 h) | quartet | — | queued |
| `h3-quartet-retry` — MiniMax-H3 four-rank video probe (baseline cell completes since 2026-10-26; axes optional) (4 h) | quartet | — | queued — needs the quartet, which the production serve holds |
| `ds4-shipped-container-digest-pin` — push the local `canary-roce-aff52fa5` overlay under a registry tag, take the manifest digest, write it into `container:` (today tag-only) (0.5 h) | — | — | queued |
| `h2h-second-boot-ladder` — controlled second-boot ladder per arm (sigma column) (5 h) | quartet | — | queued |

## Landed this session

| time ET | commit | one clause |
|---|---|---|
| 00:28 ET | `50167f7` | `plugins/plugin.toml` sidecar (`sparkrun = ">=0.4.2a0,<0.5"`): the pooling plugin's `sparkrun update` row renders a real range instead of `unknown`, and the `a0` floor is what admits the 0.4.2/0.4.3 alphas — the Python half stays `unknown` because the core reads it only from a distribution; verified at `spark-arena/sparkrun@561b14b`, suite 1007 OK (2 skipped) |
| 00:55 ET | measurement | `k2-horizon-0.9b-bf16-sglang` full breakfast — ladder C1 **78.3** / C2 **175.4** / C5 **340.5** / C10 **498.8** tg t/s (5 runs per cell), house **70** (9 pass / 3 partial / 3 fail) |
| 00:58 ET | measurement | `ornith-1.5-9b-nvfp4-dflash-sglang` — ladder C1 **53.3** / C2 **91.4** / C5 **149.7** / C10 **144.5** (C5→C10 degrades, σ 3.8), house **97** (14 / 1 / 0) |
| 01:08 ET | measurement | `k2-horizon-0.9b-bf16-uno-sglang` — ladder C1 **121.1** / C2 **220.8** / C5 **383.8** / C10 **516.3**, house **83** (11 / 3 / 1); UNO beats the plain bf16 sibling at every rung |
| 01:10 ET | measurement | `spark-x2.6-4b-bf16-sglang` — ladder C1 **21.5** / C2 **49.2** / C5 **100.2** / C10 **158.8**, house **87** (12 / 2 / 1); C1 matches the historical 20.38 control on the same image |
| 01:26 ET | measurement | `poolside-laguna-xs-2.1-nvfp4-dflash-vllm` — ladder C1 **53.4** / C2 **82.5** / C5 **129.6** / C10 **135.9**, house **83** (11 / 3 / 1); re-measured under `--fresh` after its first ladder turned out to be a benchmark-state re-emit, and it reproduces the cached figures within noise |
| 01:26 ET | measurement | `spark-x2.6-4b-fp8-sglang` — ladder C1 **40.5** / C2 **76.5** / C5 **145.9** / C10 **218.1**, house **80** (11 / 2 / 2); roughly 2× the bf16 sibling's decode at every rung |
| 01:44 ET | measurement | `zz-spark-x2.6-4b-fp8-ngram-sglang` — ladder C1 **38.9** / C2 **69.7** / C5 **133.6** / C10 **194.5**, house **0** (0 pass / 0 partial / **15 fail**): it serves and decodes, but every scenario ends `missing_step` after **42–60 s** each (passing siblings take 1–14 s), with no HTTP, timeout or connection error in the log — a behavioural failure of the ngram probe, not a transport artifact |
| 01:51 ET | measurement | `ornith-1.5-35b-a3b-nvfp4-yarn-1m-sglang` — ladder C1 **79.6** / C2 **115.7** / C5 **143.7** / C10 **202.5**, house **97** (14 / 1 / 0); best house score of the campaign so far |
| 02:01 ET | measurement | `ornith-1.5-35b-a3b-nvfp4-dflash2-sglang` — ladder C1 **92.7** / C2 **151.9** / C5 **221.5** / C10 **252.5**, house **100** (15 / 0 / 0); the campaign's best arm on both axes, and its C1 is the highest measured in this run |
| 11:18 ET | measurement | `k2-horizon-7b-fp8-uno-sglang` boot failure root-caused: not the node, not transient — the pool's copy of pinned revision `ea739ec8…` held only `config.json`, so the tokenizer fell back to a slow class with no `sentencepiece`/`tiktoken` and the serve died before opening the port (`ValueError: Couldn't instantiate the backend tokenizer`). Upstream that revision has 13 files and the pin is sound; `hf download --revision` completed 13/13. **The class generalises**: a present-but-partial revision surfaces as an engine error, so a staging census must verify snapshot file counts, not repo presence |
| 11:22 ET | measurement | `k2-horizon-7b-fp8-uno-sglang` **measured after the cache repair** — ladder C1 **32.5** / C2 **54.0** / C5 **91.2** / C10 **120.8** tg t/s (per-request 32.5 / 31.2 / 23.4 / 17.0), house **90** (deployability 81, responsiveness 60); ladder rc=0, house rc=0, stopped by task id, node released with 0 containers and 0 volumes |
