# Board — generated 2026-10-28 01:14 ET

## In flight

| where | owner | what |
|---|---|---|
| ds4 quartet, `.31`–`.34` | **production serve** — standing line; the lock rule binds declared research windows, and settled `TODO.md` `#4`/`#51` recognise these ranks serving the fleet's own inference. sparkrun job `c989632ede4f538e_b4e3c94ef77c` | `@littlecedar/deepseek-v4.1-flash-knapcio-tp4-1m-sglang` (tp=4) on image `littlecedar/dgx-spark-dsv41:canary-roce-aff52fa5` — `RepoDigests` still **0** (local id `sha256:3f4480818acb…`; queue row `ds4-shipped-container-digest-pin`), **`Up 25 hours (healthy)`** on all four at 01:09 ET. **Serving live traffic**: rank0's last 400 serve-log lines hold **61** `POST /v1/chat/completions` **200** against 18 loopback `GET /health`, latest **01:10:20 ET** from `.30`; decode `#running-req: 2`, accept len 5.23, 175.2 tok/s at 01:10:24 ET |
| TP≤2 campaign, `.30` + `.35` | this tick — session `…03-21-32Z_01a18086`, 2 detached slots (`campaign.py` on the head) | full breakfast per arm = `concurrency-ladder.yaml` + `standard-suite.yaml` on **one** boot (`--skip-run`), `--fresh` on every call. **3 of 42 arms complete** (rows below); slot A on `k2-horizon-7b-fp8-uno-sglang`, slot B finishing `spark-x2.6-4b-bf16-sglang`'s house. **32 of 42 are gated**: 25 need an image pull (11 digests absent on both free nodes), 2 a model fetch, 5 both — no TP=2 arm is runnable yet. One result **invalidated, not counted**: the laguna ladder was a benchmark-state re-emit (0 s, no requests sent) and is requeued with `--fresh`. Receipts `~/benchmarks/tp12-20261028/<arm>/`, ledger `.scratch/tp12-campaign/ledger.jsonl` |
| census | this tick — session `…03-21-32Z_01a18086` (opened 23:21 ET) | **01:09 ET, all six nodes (read-only ssh)**: 6 containers — `.30` **1** (campaign slot A), `.31`–`.34` **1 each** (production quartet, `Up 25 hours (healthy)`), `.35` **1** (campaign slot B); nothing else live on any node. Root avail `.30`→`.35`: 1.7 / 1.9 / 1.9 / 1.8 / 1.2 / 1.3 TB; BeeGFS pool **11 TB** free on every node; `ps` at 01:11:19 ET shows **no `hf download`/`hf sync` process** on any of the six; volumes **0 fleet-wide** |

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
| 00:28 ET | `50167f7` | `plugins/plugin.toml` sidecar (`sparkrun = ">=0.4.2a0,<0.5"`): the pooling plugin's `sparkrun update` row renders a real range instead of `unknown`, and the `a0` floor is what admits the 0.4.2/0.4.3 alphas — the Python half stays `unknown` because the core reads it only from a distribution; verified at `spark-arena/sparkrun@561b14b`, suite 1007 OK (2 skipped) |
| 00:55 ET | measurement | `k2-horizon-0.9b-bf16-sglang` full breakfast — ladder C1 **78.3** / C2 **175.4** / C5 **340.5** / C10 **498.8** tg t/s (5 runs per cell), house **70** (9 pass / 3 partial / 3 fail); receipts `~/benchmarks/tp12-20261028/k2-horizon-0.9b-bf16-sglang/` |
| 00:58 ET | measurement | `ornith-1.5-9b-nvfp4-dflash-sglang` — ladder C1 **53.3** / C2 **91.4** / C5 **149.7** / C10 **144.5** (C5→C10 degrades, σ 3.8), house **97** (14 / 1 / 0); receipts `~/benchmarks/tp12-20261028/ornith-1.5-9b-nvfp4-dflash-sglang/` |
| 01:08 ET | measurement | `k2-horizon-0.9b-bf16-uno-sglang` — ladder C1 **121.1** / C2 **220.8** / C5 **383.8** / C10 **516.3**, house **83** (11 / 3 / 1); UNO beats the plain bf16 sibling at every rung (78.3 / 175.4 / 340.5 / 498.8); receipts `~/benchmarks/tp12-20261028/k2-horizon-0.9b-bf16-uno-sglang/` |