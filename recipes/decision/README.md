# Decision lane

Small models that make classification / routing / judgment calls — **prefill-only scorers, not
chat models** — co-located with the shipped embed + rerank pair on **one** DGX Spark (the lane's
core constraint: nodes are at a premium). This README covers the six shipped recipes plus the two
candidate CPU arms measured 2026-10-18 — `kev-0.8b` serves and scores but cannot pass sparkrun's
launch gate, and `d3-edge` cannot load on a staged offline node. The
candidate research, verified surfaces, official scores, the CPU+GPU tandem probe and the
revision-drift determination are archived under [`attic/decision/`](../../attic/decision/)
(indexed at the end).

## Contents

- [jev-9b-decision-vllm](#jev-9b-decision-vllm)
- [clef-flash-decision-sglang](#clef-flash-decision-sglang)
- [kai-0.6b-decision-vllm-srun](#kai-06b-decision-vllm-srun)
- [sol-2b-decision-vllm-srun](#sol-2b-decision-vllm-srun)
- [sol-2b-decision2-gguf-llamacpp](#sol-2b-decision2-gguf-llamacpp)
- [nox-4b-decision-vllm-srun](#nox-4b-decision-vllm-srun)
- [kev-0.8b-decision-serve](#kev-0.8b-decision-serve)
- [d3-edge-decision-vllm-srun](#d3-edge-decision-vllm-srun)
- [Operating constraints](#operating-constraints)
  - [The `vllm-srun` runtime (Kai + Sol)](#the-vllm-srun-runtime-kai--sol)
  - [Served-id caveat](#served-id-caveat)
  - [Co-location budget](#co-location-budget)
- [The clef + Kai ensemble](#the-clef--kai-ensemble)
- [A `req/s` ladder, not a `t/s` ladder](#a-reqs-ladder-not-a-ts-ladder)
  - [Concurrency ladder](#concurrency-ladder)
- [Attic index](#attic-index)

Accuracy on the shared instrument (`tool-eval-bench` v2.8.0, Typed Decisions test split — 400
cases / 2000 decisions): **clef-flash 70.3% > Nox-4B 67.8% > JEV-9B 67.0% > Sol-2B 55.0% > Kai-0.6B
47.5%**; the candidate `kev-0.8b` sits below that ranking at **46.0%** and `d3-edge` has no score (their
sections follow).

Two measurements sit outside that ranking and have their own sections below: the lane's
accuracy record is **not** clef-flash alone but the **clef + Kai ensemble at 71.6%** (pooling
the two arms' per-question distributions — [§The clef + Kai
ensemble](#the-clef--kai-ensemble)), and the index's C-columns for this lane are `req/s`
ladders, not decode `t/s` ([§A `req/s` ladder, not a `t/s`
ladder](#a-reqs-ladder-not-a-ts-ladder)).

### jev-9b-decision-vllm

| field | value |
|---|---|
| repo id | [`autotrust/JEV-9B`][jev] (pinned `7ac669b8`), + the `jev-decision` LoRA (rank 32); Apache-2.0 |
| accuracy | **67.0%** (1340/2000), ★★ |
| size | 18 GB (bf16 9B + 173 MB LoRA); ~17 GiB weights |
| API | `/v1/completions` — the card's native SystemOne scoring shape (`logprobs` + top-level `allowed_token_ids`); the server runs `--logprobs-mode processed_logprobs --enable-lora`. The chat-template surface shifts the distribution and can flip argmaxes, so score on completions, not chat. |
| TP | 1 |
| flags | 🤏 smol · 🚮 classifier |
| status | **BOOT-VERIFIED 2026-10-11** (`.34`) |

`max_model_len` ships at 4096 (card-sized for decisions); raise it to 16384 only if System 2 thinking
at length is needed (the card's own note).

### clef-flash-decision-sglang

| field | value |
|---|---|
| repo id | [`Cloudflare/clef-flash`][clef] (pinned `8b2e5fd1`) |
| accuracy | **70.3%** (1406/2000), ★★ — the lane's accuracy leader |
| size | 19 GB (4 shards 18.82 GB + `joint_head` 0.244 GB); vendor 41 GB VRAM at 64k ctx |
| API | `/v1/systemone` (choice / noul / score, calibrated probabilities, no text generation; multimodal text/JSON/images/video). No chat endpoint → `readiness: inference: false`, port + `/health` only (port 8020; embed 8010, rerank 8011). |
| TP | 1 |
| flags | 🤏 smol · 🚮 classifier |
| status | **BOOT-VERIFIED 2026-10-11** |

### kai-0.6b-decision-vllm-srun

| field | value |
|---|---|
| repo id | [`vllm-sr/Decision-2.0-Kai-0.6B`][kai] (0.60B Qwen3-0.6B-Base fine-tune, 8192 ctx; pinned `cd49ea38`) |
| accuracy | **47.5%** (949/2000), ★★ |
| size | 2 GB (1.503 GB + head) |
| API | `/v1/systemone` (and the `/v1/decisions` superset), **CPU** |
| TP | 1 |
| flags | 🤏 smol · 🖥 cpu · 🚮 classifier |
| status | **BOOT-VERIFIED 2026-10-13** |

### sol-2b-decision-vllm-srun

| field | value |
|---|---|
| repo id | [`vllm-sr/Decision-2.0-Sol-2B`][sol] (1.88B, 16384 ctx; pinned `64235bef`) |
| accuracy | **55.0%** (1100/2000), ★★ |
| size | 5 GB (3.02 + 1.76 GB + head) |
| API | `/v1/systemone`, **CPU** |
| TP | 1 |
| flags | 🤏 smol · 🖥 cpu · 🚮 classifier |
| status | **BOOT-VERIFIED 2026-10-13** |

### sol-2b-decision2-gguf-llamacpp

| field | value |
|---|---|
| repo id | `vllm-sr/Decision-2.0-Sol-2B-GGUF` — `Decision-2.0-Sol-2B-Q8_0.gguf`, 2,020,436,832 B (the vendor's own GGUF of the CPU arm's checkpoint; BF16 and Q4_K_M also published) |
| recipe | [`sol-2b-decision2-gguf-llamacpp.yaml`](sol-2b-decision2-gguf-llamacpp.yaml) — llama.cpp, TP=1, one node |
| image | `littlecedar/dgx-spark-llama-cpp-decision2:c9f5974@sha256:b4808c9a6ef81775f7e05c91670f1f8853aa3d97c14f47cce3f21627cd3ba1f3` (published docker.io/arm64 2026-10-20; local id `sha256:1bb250bf…`, 2.68 GB) — built from `Xunzhuo/llama.cpp@c9f597487` on the CUDA 13.0.1 devel/runtime pair this registry pins, `-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=121a-real`, source build vendored as [`Dockerfile.llama-cpp-decision2`](Dockerfile.llama-cpp-decision2) |
| engine | `llama-server --version` → `0.6.0-dev (build 11508, commit c9f597487)`, GNU 13.3.0 aarch64 |
| accuracy | **55.0 % (1101/2000), ★★** — KL(gold‖pred) 0.351, Brier 0.189, ECE 0.054, **0 decision errors** |
| API | `/v1/systemone` (typed decision: CHOICE / SCORE / NOUL, one forward pass per case, no generated tokens), **GPU** |
| status | **BOOT-VERIFIED 2026-10-20** — launched by `sparkrun run` on the digest-pinned image and re-scored on that boot: **55.0 % (1101/2000)**, identical to the manual boot |

**It reproduces the CPU arm, and that is the point of the route.** On the same instrument
(`uvx tool-eval-bench@2.8.0 --decision-bench-only`, 400 cases / 2,000 decisions) the GGUF arm scores
**55.0 % (1101/2000)** against `sol-2b-decision-vllm-srun`'s **55.0 % (1100/2000)** — one decision
apart — with KL 0.351 vs 0.352, Brier 0.189 vs 0.190 and ECE 0.054 vs 0.058. Per type here: `noul`
65.7 % (394/600), `choice` 49.8 % (299/600), `score` 51.0 % (408/800). The difference is cost, not
accuracy: **79.9 s total and p50 195.3 ms / p95 269.8 ms per case** on the GB10 against the CPU arm's
**5,670 s (94.5 min) at p50 15.0 s** — ≈71× the pass and ≈77× the per-case latency.

The recipe carries the vendor's run line (`llama-server -hf …:Q8_0 --embeddings --pooling none
-c 8192 -b 8192 -ub 8192 -np 1`) with sparkrun's host/port/alias and `{served_model_name}`, and it
renders exactly that. **Mount caveat for a manual boot:** the HF cache's `snapshots/…Q8_0.gguf` is a
symlink into `blobs/` (itself a second-level symlink), so mounting the snapshot dir yields a dangling
path and the server dies with `failed to open GGUF file`; mount the repo root (or a plain
`hf download --local-dir` copy) instead. That was the only boot failure this arm produced.

**Publishing:** the image was built on `.34`, then `docker save | docker load` on the head and pushed
from there (the head holds the `docker.io` credential; the nodes do not), which is what produced the
`sha256:b4808c9a…` digest the recipe pins. The head's loaded id equals the node's build id
(`sha256:1bb250bf…`), so the digest pins the same content that was measured.

**The sparkrun launch reproduces the measurement.** `sparkrun run` on this recipe pulled the published
digest, came up in **26.8 s** (port open 0.7 s, health 0.0 s afterwards), served
`vllm-sr/Decision-2.0-Sol-2B-Q8_0`, and the same instrument scored **55.0 % (1101/2000)**, KL 0.351,
Brier 0.189, ECE 0.054 over **80.5 s** — decision-for-decision the manual boot's result, so the recipe
(not just the image) is the verified artifact. Receipt `~/benchmarks/sol2b-recipe-20261020/`.

`-np 1` is the vendor's slot count, so the ladder above c1 queues rather than batches — and that is
exactly what it measures: **c1 5.228 / c2 5.439 / c5 5.422 / c10 5.413 req/s** (26.14 / 27.20 / 27.11 /
27.06 decisions/s) with p50 latency **193.0 → 375.8 → 955.0 → 1941.3 ms** and every cell clean
(2,000/2,000 requests, 10,000/10,000 decisions, five runs each, `tools/decision-ladder.py --runs 5`).
Throughput is flat from c1 to c10 while latency scales with offered concurrency: one slot, a queue, no
batching — the same shape the CPU arms show for a different reason. Receipt
`~/benchmarks/sol2b-20261020/` (`teb-decision.log`, `runs/2026/10/*.md`, `build.log`, `build2.log`,
`ladder.log`, `ladder.json`).

### nox-4b-decision-vllm-srun

| field | value |
|---|---|
| repo id | [`vllm-sr/Decision-2.0-Nox-4B`][nox] (4.21B, Qwen3.5-4B-Base backbone, 16384 ctx; pinned `25e8f67d`) |
| accuracy | **67.8 % (1356/2000), ★★** — KL(gold‖pred) 0.219, Brier 0.114, ECE 0.063, **0 decision errors** |
| size | 9.7 GB (five backbone shards + a 10.5 MB decision head); 9.03 GiB on disk |
| API | `/v1/systemone` (+ `/v1/decisions`), **CPU**; `/health` is the vendor golden gate |
| TP | 1 |
| flags | 🤏 smol · 🖥 cpu · 🚮 classifier |
| status | **BOOT-VERIFIED 2026-10-21** (`.34`) — golden gate passes, `67.8 %` on the lane instrument |

**The best CPU route the lane has, and the offline-staging class it inherits.** One request per case,
one forward pass, no generated tokens: **67.8 % (1356/2000)** on
`uvx tool-eval-bench@2.8.0 --decision-bench-only` (run
`2026-10-21T19-02-40.908377Z_a3a115d0`, Typed Decisions test split `e039ebffcc28`, 400 cases) — 12.8
points over Sol-2B's 55.0 %, second in the lane behind clef-flash's 70.3 %. By type: `noul` 74.2 %
(445/600), `choice` 66.0 % (396/600), `score` 64.4 % (515/800); by workflow the weak cell is
`agent_trace_observability` at 59.4 %, the others 68.0–72.6 %.

**`/health` is the vendor's CPU golden comparison, not liveness** (tolerance 1e-3, goldens recorded on
x86), so a 503 with `GoldenResult(status='failed')` means the pack diverges, not that the boot broke.
On this aarch64 node it returned **200 `{"status":"ready","reason":null}`** — the d3-edge golden
divergence did not reproduce for this manifest (`49771ea3…` at the pin).

**The launch needs `HF_HUB_OFFLINE=0`, and the recipe now carries it.** As sparkrun stages a model
(`HF_HUB_OFFLINE=1`), this loader still calls the Hub tree API and `/health` answers 503 `status:
loading` with `OfflineModeIsEnabled` retries while never reading the staged snapshot — the d3-edge
failure, reproduced. The recipe's `env: HF_HUB_OFFLINE: '0'` is the documented mitigation and it
boots clean in ~30 s; launching without it stalls at the gate.

**Cost, measured.** The full pass took **14,066 s (3.91 h)**, 35.2 s per case, 652,665 input tokens —
1.6× the price a three-case probe predicted (21.9 s/case), because the first cases are cheaper than
the mean. Grading a candidate on this route is a 4-hour window, not a 2.4-hour one.

**Ladder: flat, as the CPU shape predicts.** `tools/decision-ladder.py --api systemone --limit 100
--runs 1` (the same limited-slice form Kai's ladder uses — 400 cases × 5 runs × 4 cells prices at
~30 h at this per-case cost): **C1 0.044 / C2 0.044 / C5 0.044 req/s** (0.22 decisions/s), p50
**22,763 → 45,480 → 113,797 ms**, 500/500 decisions clean at every level. Throughput does not move
while latency scales with offered concurrency — one forward pass at a time, no batching, a pure
queue. **C10 was not run** — the serve was stopped to free the pair for the queued flash-next TP=2
boot.

Receipt `~/benchmarks/nox4b-20261021/` (`teb-decision.log`, `runs/2026/10/<run-id>.md`, `probe.json`,
`ladder.log`, `serve.log`, `REPORT.md`).

### kev-0.8b-decision-serve

| field | value |
|---|---|
| repo id | [`jaredpalmer/kev-0.8b`][kev] (pinned `bf75a6a8`), rank-16 LoRA adapter + pointer head on `Qwen3.5-0.8B-Base`; Apache-2.0 |
| accuracy | **46.0%** (919/2000), ★ — KL(gold‖pred) 0.349, Brier 0.196, ECE 0.046 |
| size | 0.06 GiB staged (adapter + head); the ~1.6 GB backbone is fetched from the Hub at first load (a recipe stages one repo) |
| API | `/v1/systemone` (+ `/v1/systemone/permute`, `/v1/systemone/separate`), **CPU**; `/v1/models` is not OpenAI-shaped (no `data[].id`); **no `/health`** |
| TP | 1 |
| flags | 🤏 smol · 🖥 cpu · 🚮 classifier |
| status | **MEASURED 2026-10-18** (`.34`) — serve healthy, **sparkrun launch gate cannot pass** |

**Blocker — the gate, not the serve.** sparkrun's in-node startup probe requires HTTP 200 on
`/health` and polls until it sees one (`sparkrun/scripts/startup_probe.py:246-265`); `kev.serve` has
no such route, so it 404s (≈2 polls/s for the ~20 min before the launch was cancelled) and the probe
would raise `TimeoutError("health")` at `health_timeout_s: 1800`. `readiness.inference: false` skips
only the inference stage, and `health_path` is runtime-owned (`sparkrun/runtimes/_vllm_common.py:24`
→ `readiness_health_path = "/health"`), so no recipe key redirects it. The detached container keeps
serving while the launch waits, which is how this arm was measured; TTR is bounded at ≤ ~3.5 min
(the cold boot is `pip install torch==2.8.0` + `kev[serve]@1f04cfa2` plus the backbone fetch).

**Measured 2026-10-18 on `.34`** (`runbooks/kev-smoke.py`, then `tool-eval-bench` v2.8.0
`--decision-bench-only --model kev-latest` over the full 400-case / 2000-decision split, serial):
p50 **5403.4 ms** / p95 6671.5 ms per case, 2126.8 s total, 202,638 input tokens, 0 decision
errors. Per type: noul **52.5%** (315/600, KL 0.266, Brier 0.220), choice **50.5%** (303/600,
0.359, 0.174), score **37.6%** (301/800, 0.405, 0.194). Per workflow: customer_service 55.0%,
security_incidents 50.4%, invoice_processing 43.8%, agent_trace_observability 34.6%. Against laya on
the same split (**36.1%**, 723/2000, p50 4290.0 ms): **+9.9 points at 26% more latency**.

Ladder (`tools/decision-ladder.py --runs 1 --limit 30`): c1 **0.234 req/s / 1.17 decisions/s**
(p50 4290.8 ms), c2 **0.235 / 1.18** (p50 8527.0 ms) — flat aggregate throughput at doubled
per-request latency, because `Server._work` runs one request at a time without CUDA graphs; laya's
c1 is 0.449 / 2.25, so kev is **1.9× slower per case at c1**. The case cost is the shared state prefill,
not the question rows: `/v1/systemone/separate` costs 4360 ms against 4133 ms packed (742 vs 370
input tokens).

Receipt: `~/benchmarks/decision-arms2-20261018/` — `REPORT.md`, `logs/kev-launch.log` +
`logs/kev-teb.log` + `logs/kev-smoke.log` + `logs/kev-ladder.log`, `runbooks/kev-smoke.py`,
`ladder-kev-c1c2.json`, `kev-evidence/startup_probe-health-gate.py`.

### d3-edge-decision-vllm-srun

| field | value |
|---|---|
| repo id | [`vllm-sr/d3-edge`][d3] (pinned `18d61df7` — the runtime's built-in, golden-checked revision; the head `c454ee39` was probed 2026-10-22 and reverted, see below) |
| accuracy | **unmeasured** — the runtime will not serve it |
| size | 594,582,720 params (1.19 GB weights + readout) |
| API | `/v1/systemone` over text, image and video states, **CPU**; `/health` is the golden gate, not plain liveness |
| TP | 1 |
| flags | 🤏 smol · 🖥 cpu · 🚮 classifier |
| status | **NOT BOOTED 2026-10-18** (`.34`) — two blockers, both image-side. **Re-probed 2026-10-22** on the head revision (`.31` as shipped, `.35` with the Hub reachable): both blockers reproduce unchanged, pin reverted |

**Blocker 1 — offline staging.** As shipped, `/health` returns 503 `OfflineModeIsEnabled: Cannot
reach https://huggingface.co/api/models/vllm-sr/d3-edge/tree/18d61df7…`: sparkrun stages the model
with `HF_HUB_OFFLINE=1`, while the decision3 loader resolves the package through the Hub tree API
even with `--cache-dir` pointing at the staged snapshot. Kai/Sol on `vllm-srun` do not hit this, and
the node itself reaches the Hub.

**Blocker 2 — the golden gate.** With `-e HF_HUB_OFFLINE=0` (launch-time env only) the package
resolves and the model loads (594,582,720 = the manifest's `parameters.loaded`), then the runtime
refuses it: `GoldenResult(status='failed', checked=3, matched=1, reference='cpu')`. The aarch64
answers differ from the image's x86-recorded CPU goldens by **2-4e-3 in probability** — 2-4×
`CPU_TOLERANCE = 1e-3` (`supervision/readiness.py:12-14`) and deterministic across 5 attempts:
`difficulty` confidence 3.70e-3, P(0) 2.15e-3, P(1) 2.22e-3, score 2.09e-3; `reasoning` noul 3.83e-3;
`domain` matches at 8.8e-5. `/health` stays 503 and `/v1/systemone` 503 `not_ready`, so this arm has
**no score and no ladder**. Making it bootable is image-side on either count — an aarch64-recorded
CPU reference (or a per-ISA tolerance), or a decision3 loader that accepts a staged local snapshot
offline. Neither is a recipe edit.

Receipt: `~/benchmarks/decision-arms2-20261018/` — `REPORT.md`, `logs/d3-launch.log` +
`logs/d3-launch-hfonline.log`, `d3-evidence/golden-probe.log`, `golden-reference-d3-edge.json`,
`readiness-golden_check.py`, `compare_answers.py`, `container-inspect.json`.

**Re-pin probed 2026-10-22, and it changes nothing — the pin stays at `18d61df7`.** The repo's head
moved 10 commits past the pin (2026-10-11…17): `d3_format.py`, `d3_runtime.py`, `d3_server.py`,
`requirements.txt`, `MODEL_MANIFEST.json` and card / assets / `.eval_results` only, with both
`*.safetensors` blobs byte-identical, so the delta is vendor code, not weights. `18d61df7` is itself
the `d3-edge v3.1.0` release commit and the head is a post-release card/eval commit — not a newer
release. Booted at the head: `/v1/models` 200 with `ready:false`, and `/health` 503
`status:"loading"` → `OfflineModeIsEnabled: Cannot reach …/tree/c454ee39…`, i.e. blocker 1 verbatim at
the new revision; with `-e HF_HUB_OFFLINE=0` the loader resolves and the runtime then answers
`/health` 503 `"failed"` / `VerificationError: golden answers differ from the reference`, golden
`{status: failed, checked: 3, matched: 1, reference: "cpu"}` — the **same 3-checked / 1-matched
result as the pin**, so the divergence is the image's x86 reference on aarch64, not the revision.
Both sites (`model_revision:` and the literal `--revision=`) were reverted. Receipt:
`~/benchmarks/decision-d3-repin-20261022/` — `bootA.log` + `bootA-{models,health,systemone}.txt`
(as shipped), `bootB.log` + `bootB-{models,health,systemone}.json` (Hub online), `REPORT.md`.

## Operating constraints

### The `vllm-srun` runtime (Kai + Sol)

The Decision 2.0 models run on the vendor's own runtime, **`vllm-srun`** — a standalone
single-process server (`vllm_srun.cli:main`, `src/model-runtime` in the vendor's
`semantic-router` repo) shipped inside the `vllm-sr` router image (not on PyPI, no image of its
own; `vllm-srun models` lists every built-in model at its golden-checked pinned revision). Both
recipes declare `runtime: vllm` (the family whose distribution + launcher contract the command
satisfies) and clear the image's default router/gateway ENTRYPOINT
(`executor_config.entrypoint: ""`) so the serve line runs. They serve on **CPU**, pinned to the
unclaimed A725 cores (`taskset -c 0-4,10-14`, mirroring clef-flash), because the vendor marks
DGX-Spark arm64 CUDA "experimental, not qualified" — so the lane's slot for these is a decision
model at no GPU cost. `--revision=` uses the runtime's own pinned revisions (Kai `cd49ea38…`,
Sol `64235bef…`), the ones its golden readiness check is built against; `/health` gates on that
check (not plain liveness), hence the long readiness timeouts. The image is built on
`python:*-slim` and ships no standalone `kill` binary, which breaks sparkrun's detached-launch
liveness check (`docker exec <c> kill -0` exits 127 and is misread as "serve process exited");
both recipes prepend a bash-builtin `kill` shim and run as root so the shim can be written.
(vLLM / SGLang images ship procps and are unaffected.)

### Served-id caveat

sparkrun rebinds every `{model}` occurrence to the prepared snapshot path on a real launch (`-n`
still prints the repo id), so an arm that shipped `--served-model-name {model}` advertised the
cache path as its model id. clef-flash declares `served_model_name: Cloudflare/clef-flash` and
passes `--served-model-name {served_model_name}` (fixed 2026-10-13); the vllm-srun recipes pass
the repo id literally. Clients use the repo id.

### Co-location budget

Co-location with the shipped embed + rerank 2B pair (and, measured 2026-10-19, the media lane's
CPU TTS arm) on ONE GB10 node is the
lane's core constraint. The caps are absolute device caps that must SUM, and the pair's measured
hold is 74 GiB — 66.93 GiB of caps plus ~7 GiB of CUDA/b12x kernel memory — so a third engine
starts with **~42 GiB free (0.345)**, not the 54.76 GiB the cap arithmetic suggests (measured
2026-10-19 on `.34`: idle 3 GiB used; pair up 77 used / 42 free; the nominal computation in
`attic/decision/DECISION-MODELS-RESEARCH.md` §3 is a floor, not the runtime figure). JEV-9B ships
`gpu_memory_utilization: 0.20` + `max_num_seqs: 32`: 0.20 leaves 5.08 GiB of KV cache and a 0.75
cap sum, 0.16 profiles a *negative* cache (−1.66 GiB), and 0.35 is refused outright (free 40.86
vs the 42.59 GiB request, warm). `max_num_seqs` stays low because the Mamba cache blocks the
engine grants scale with the cap (57 at 0.16 vs the default 256), so the default cannot capture
graphs. clef-flash at the vendor's 41 GB still needs the embed/rerank caps lowered to
~0.15/0.18 first, a cap-bookkeeping decision rather than a memory wall; the media lane's Kokoro-82M costs **1.55 GiB**
of the residual (measured 2026-10-19 — the 0.305 GiB figure is weights only, not the process). Cores: embed pins 5-9 and rerank 15-19 (the X925 cluster), so clef-flash (and
the CPU Decision 2.0 arms) pin 0-4,10-14 (A725) to keep the tenants from contending; JEV-9B runs
unpinned.

## The clef + Kai ensemble

Co-serving the lane's accuracy leader with its smallest CPU arm and **pooling their answers**
lifts accuracy a little, and the gain is reproducible across sessions, not a one-off analysis.
The rule is an equal-weight **linear mean** of the two models' per-question distributions,
renormalised, scored by `argmax(pooled) == gold` — a client-side rule, not a different server.

| scorer | accuracy | KL(gold‖pred) | Brier |
|---|---:|---:|---:|
| clef-flash alone (GPU) | 70.3% (1406/2000) | 0.209 | 0.111 |
| Kai-0.6B alone (CPU) | 47.5% (950/2000) | 0.362 | 0.198 |
| **ensemble (linear mean)** | **71.6% (1432/2000)** | 0.196 | 0.098 |
| ensemble (log-linear) | 71.3% (1427/2000) | 0.168 | 0.086 |

Ensemble vs clef alone: **+63 / −37 discordant decisions, exact two-sided McNemar p = 0.012**
(small but real; the 2026-10-13 probe put a case-level bootstrap 95% CI of **[0.35, 2.20]** on
the +1.3 pt delta, and this run repeats the same discordant split exactly). The gain is
concentrated in the `score` kind (+2.6 pts). The log-linear (geometric-mean) pool trades ~0.3 pt
of accuracy for a larger calibration gain (KL −20%, Brier −22% vs clef alone).

Per kind (noul 600 / choice 600 / score 800): clef 81.5 / 70.3 / 61.9, Kai 62.8 / 42.5 / 39.8,
ensemble-linear 81.8 / 70.8 / 64.5.

*Measured 2026-10-15 on `.34`, both arms booted fresh for this run — the table is that run.* It
reproduces the 2026-10-13 probe's headline exactly (71.6%, +63/−37, p = 0.012): clef's own
report is identical decision-for-decision (1406/2000) and the ensemble's is too (1432/2000),
while **Kai's differs by one decision** (950 vs 949/2000; its `choice` kind 42.5% vs 42.3%) —
the same ±1–3-decision variance that batch composition produces elsewhere in this lane (the
C2/C5/C10 passes below swing 1404–1407/2000), not a configuration difference. The gain is
**pairing-specific**: clef + Sol-2B is a net loss (69.9%) and a 3-way pool dilutes (69.6%) —
Kai is the more complementary partner (argmax agreement with clef 46.3% vs Sol's 58.7%), so
this is not a property of "GPU + CPU" as such.*

### Reproduce it

Two boots, two instrument passes, one pooling command — nothing hidden:

```bash
sparkrun run recipes/decision/clef-flash-decision-sglang.yaml -H <node>        # GPU arm, :8020
sparkrun run recipes/decision/kai-0.6b-decision-vllm-srun.yaml -H <node>       # CPU arm, :8000
uvx tool-eval-bench@2.8.0 --base-url http://<node>:8020 --decision-bench-only  # -> report A (82 s on a GB10)
uvx tool-eval-bench@2.8.0 --base-url http://<node>:8000 --decision-bench-only  # -> report B (~35 min, CPU)
python3 tools/decision-tandem.py <report A> <report B> --a-name clef --b-name kai
```

`decision-tandem.py` parses each report's `### Full Trace` section (the durable artifact the
instrument writes), pools the per-question distributions and prints the table above with its
McNemar test; `--json` writes the machine-readable result. Both arms must speak
`/v1/systemone` so their option spaces match — JEV-9B does not (one `/v1/completions` request
per question) and is not poolable, which is why it is absent here.

Or **serve** the ensemble as one endpoint and let the instrument score it in a single pass:

```bash
python3 tools/decision-ensemble.py --a http://<node>:8020 --b http://<node>:8000 \
    --a-model Cloudflare/clef-flash --b-model vllm-sr/Decision-2.0-Kai-0.6B --port 8021
uvx tool-eval-bench@2.8.0 --base-url http://<node>:8021 --decision-bench-only
```

The proxy is the reference implementation of the rule for a client that would rather not
implement it (mean-then-argmax vs argmax-then-vote, tie-breaks and dropped labels are all ways
to get a different number from the same two models): it imports `decision-tandem.py`'s
`linear` / `normalise` / `argmax`, so the served ensemble and the analysed ensemble cannot
drift apart, and it answers the same wire shape both members answer. A member that is down is
a 502 (`/health` 503), never a silenced half-answer. It also advertises **one** model id
(`/v1/models`): a merged list from both members reads as an ambiguous choice to a
model-auto-detecting client, and an interactive client (tool-eval-bench v2.8.0) will sit in a
`Select model [1-2]:` prompt instead of running.

Its **rate is the pool's, not a member's**: a pooled request costs `max(member)` latency, so
the served ensemble runs at the CPU arm's pace — 0.192 req/s, p50 5.2 s on a 20-case prefix at
c1, measured 2026-10-15 behind Kai — where clef alone serves 4.9 req/s. The ensemble buys
accuracy, not speed (and the ladder numbers in the next section are per-arm, booted solo;
they are not the ensemble's).

The served end-to-end pass (2026-10-15, full 400 cases through `:8021` with both members
co-resident) scores **71.7% (1433/2000)** — one decision above the offline pooled 71.6%,
because one pooled question is an exact tie (`security_incidents_000055` severity, 0.28/0.28)
and the instrument breaks ties by first-listed option where `decision-tandem.py` breaks by
greater label. Served and offline otherwise agree on the argmax label at 1999/2000 and on the
distributions to ≤ 5·10⁻⁴ (`logs/proxy-teb-r2.log`, `reports/ensemble-served-c1.md`; a
15-question spot-check against the two members' own live answers is `0` mismatches in
`logs/proxy-correctness.log`).

**Why there is no ensemble recipe, and no `benchmarking/` profile.** A `sparkrun` recipe serves
**one** model per launch (`model:` + one `command:`; a recipe's `containers:` key is its image
*staging* list, not a serve composition), so a two-model ensemble has no recipe shape — the
lane's pair already ships as the two recipes above and the ensemble is the client rule plus the
proxy. A benchmarking profile cannot carry it either: both registered frameworks drive
`/chat/completions`, and a profile naming this lane's real instrument
(`args: {ref: v2.8.0, decision_bench_only: true}`) is *refused before the run starts* —
verified 2026-10-15, `sparkrun benchmark tools <recipe> --profile <that profile> -n` →
`BenchmarkError: tool-eval-bench modes do not provide scheduled JSON artifacts` (the plugin's
`_NO_ARTIFACT_MODES`; log: `logs/profile-refusal.log` in the receipt below). Reproducing this
lane is therefore the command block above plus the two tools, not a profile file.

Receipts (2026-10-15, `.34`): `~/benchmarks/decision-ensemble-20261015/` —
`reports/clef-alone-c1.md` and `reports/kai-alone-c1.md` (the two `### Full Trace` reports),
`ensemble.json` (the pooling result), `logs/ensemble-pool.log`, `logs/kai-teb-c1.log`, the
launch logs, and `runbooks/` (the three measurement scripts as run). The 2026-10-13 probe's
report, pairing study and co-serve contention finding are archived in
[`attic/decision/AGENTS.md`](../../attic/decision/AGENTS.md) §"CPU+GPU tandem probe
(2026-10-13)", receipts `~/benchmarks/decision-tandem-20261013/`.

## A `req/s` ladder, not a `t/s` ladder

The registry index's C1/C2/C5/C10 columns are decode `t/s`. **No arm in this lane has a decode
rate to report** — a decision model answers a prefill-only `/v1/systemone` (or
`/v1/completions`) request and emits no tokens — which is why the index's decision table heads
those columns `req/s`. Read that unit against the arm's own request shape: a "req" is one
`/v1/systemone` **case** (all five questions in one forward pass) for clef/Kai/Sol, and one
`/v1/completions` **question** for JEV-9B. The granularities are not interchangeable: clef's
C1 of 4.9 req/s is 24.5 decisions/s, while JEV's 7.6 req/s is 7.6 decisions/s.

The instrument's own concurrency knob (`--decision-bench-only --parallel N`: the same 400-case
pass with N requests in flight) and this repo's `tools/decision-ladder.py` (replaying the
vendored split) agree within 1% at every level on clef, so the shape below is not a harness
artifact:

| arm / measurement | c1 | c2 | c5 | c10 |
|---|---:|---:|---:|---:|
| clef-flash (GPU) — `req/s`, full 400-case split, instrument | 4.87 | 5.10 | 5.16 | 5.48 |
| clef-flash (GPU) — `req/s`, stride-4 slice (100 cases), harness | 4.89 | 5.11 | 5.16 | 5.51 |
| clef-flash (GPU) — p50 per request, instrument | 206 ms | 393 ms | 966 ms | 1823 ms |
| Kai-0.6B (CPU) — `req/s`, stride-4 slice, harness | 0.187 | 0.186 | 0.156 | 0.128 |
| Kai-0.6B (CPU) — p50 per request, harness | 5.70 s | 11.6 s | 30.5 s | 82.1 s |

**Both arms are serial, and the CPU arm is worse than serial under load.** clef gains 13% of
throughput at 10× concurrency while its per-request p50 inflates 8.8×: the extra requests
queue, they do not batch (each case is ~870 input tokens on the `/v1/systemone` path, not the
generation path). Kai *loses* 32% of throughput at c10 while its p50 inflates 14×: on five
pinned A725 cores, offered concurrency buys nothing and costs latency. Whether the GPU arm's
serialization is a scheduler limit, a lock inside the joint schema head, or a
`max_running_requests`-style default **is not isolated here** — what is measured is that it
does not scale.

That is the honest close for this lane's C2/C5/C10 cells: the ladder exists and is
flat-to-negative, so the columns can carry the measured `req/s` above (with the unit and the
flatness stated) or stay `—` — but a `t/s`-shaped number here would be a category error.
Sol-2B and JEV-9B are not ladded (Sol is the same `vllm-srun` CPU shape as Kai, so Kai's row is
its shape; JEV's one-request-per-question contract is supported by the harness below through
`--api completions`, but it has not been run), so their cells stay `—`.

Ladders taken 2026-10-15 on `.34` with the arms booted solo, each level a **single** closed-loop
pass (offer N, count completions; `--runs 1`, which was the only mode then and is no longer the
default):

```bash
# this repo's harness (any /v1/systemone arm); --model is required by the servers
python3 tools/decision-ladder.py --base-url http://<node>:8020 --model Cloudflare/clef-flash \
    --cases <vendored test split>.jsonl --concurrency 1,2,5,10 --runs 1 --json ladder.json
# or the instrument's own knob, on the same 400-case pass the scores come from:
uvx tool-eval-bench@2.8.0 --base-url http://<node>:8020 --decision-bench-only --parallel 10
```

The case file is the instrument's *own* vendored split — `tool_eval_bench/plugins/decision/
vendor/typed_decisions/test.jsonl.gz` in its uvx cache, `gzip -dc`'d to jsonl — and the
extracted file's sha256 is `78a228c8…`, exactly the `jsonl_sha256` recorded in that vendor
directory's `manifest.json`, so a replay is provably the same 400 cases the scores are taken
on (the receipt keeps the file beside `cases/SHA256SUMS`).

clef is ladded on both the full split and the stride-4 slice — the slice is 25 cases from each
of the four workflows, chosen because Kai cannot afford 4 × 400 requests at 5.7 s each — and
the two agree (harness c1: 4.84 req/s on the full 400 cases vs 4.89 on the slice; the
instrument's own full-split pass: 4.87), so the slice is representative. Receipts:
`~/benchmarks/decision-ensemble-20261015/` (`ladder-clef-stride4.json`,
`ladder-clef-full-c1.json`, `ladder-kai-stride4.json`, `logs/clef-teb-c*.log`,
`logs/kai-ladder-stride4.log`, `cases/SHA256SUMS`).

### Concurrency ladder

The `req/s` figures above have two instruments behind them and only one of them is concurrent.
The lane's **published rate** is `tool-eval-bench --decision-bench-only`: a *serial* pass (one
request out, the next in) unless it is given `--parallel N`, so by default it measures what one
client sees, not what the arm can serve. **C2/C5/C10 need a concurrent harness** —
[`tools/decision-ladder.py`](../../tools/decision-ladder.py) — which offers a fixed concurrency
against the same vendored split and records a cell only when that cell was verified.

```bash
# /v1/systemone arms (clef, Kai, Sol): c 1/2/5/10, five passes per cell (the 5-run convention)
python3 tools/decision-ladder.py --base-url http://<node>:8020 \
    --model Cloudflare/clef-flash --cases <vendored test split>.jsonl \
    --concurrency 1,2,5,10 --runs 5 --json ladder.json
# JEV-9B: one request per question, on the card's /v1/completions contract
python3 tools/decision-ladder.py --base-url http://<node>:8000 --api completions \
    --decision-head ~/benchmarks/jev-card/adapter_vllm/decision_head.json \
    --model autotrust/JEV-9B --cases <vendored test split>.jsonl --json jev-ladder.json
```

Per cell it reports `req/s`, aggregate `decisions/s`, the per-request `decisions/s` at that
cell's median latency, TTFT p50/p95, and decisions returned against decisions asked for. A cell
carrying a 4xx, a truncated or unparseable body, a short answer, or zero decisions is printed
**FAILED** and the run exits 1: a rate over the survivors is not the endpoint's rate.
Requests per cell are `--runs × cases` (`× questions` on the JEV path), times the levels, so a CPU
arm that cannot afford the full split cuts the slice (`--limit`, or a stride file used for every
arm) rather than the passes.

**The image arm's `—` is not a missing measurement.** The media lane's
[`qwen-image-2.1-turbo-7b-bf16-diffusers-script`](../media/README.md#qwen-image-21-turbo-7b-bf16-diffusers-script)
is a diffusers script launcher serving `POST /generate`, not an OpenAI-compatible endpoint: one image
per request and **one request at a time** — the denoise loop sits behind a single lock
([`mods/qwen-image-2.1-turbo-launcher`](../media/mods/qwen-image-2.1-turbo-launcher/README.md)).
A ladder there would time its own queue, so its C2/C5/C10 cells stay `—` by design.

## Attic index

Files under [`attic/decision/`](../../attic/decision/):
| file | what it holds |
|---|---|
| [`DECISION-MODELS-RESEARCH.md`](../../attic/decision/DECISION-MODELS-RESEARCH.md) | The 2026-10-11 read-only candidate research: both owner leads resolved, the 8-model shortlist, the one-node co-location budget math, the recommended first recipes, and the cross-cutting facts the recipes must handle. |
| [`AGENTS.md`](../../attic/decision/AGENTS.md) | Archived lane notes moved out of this README (2026-10-14): the verified surfaces, the JEV-9B and clef-flash official scores, the Kai/Sol `vllm-srun` arms record, the CPU+GPU tandem probe, "what these models are", and the archive of `#` comments removed from the recipes. Extended 2026-10-15 with §"Ensemble productized, and the req/s ladder": the fresh-boot reproduction, the served-ensemble proxy, the ladder numbers, the profile-refusal mechanism and the re-pull cost. Extended 2026-10-18 with §"kev-0.8b and d3-edge (2026-10-18)": the `/health`-gate and golden-tolerance mechanisms, cited to source. |

[jev]: https://huggingface.co/autotrust/JEV-9B
[clef]: https://huggingface.co/Cloudflare/clef-flash
[kai]: https://huggingface.co/vllm-sr/Decision-2.0-Kai-0.6B
[sol]: https://huggingface.co/vllm-sr/Decision-2.0-Sol-2B
[nox]: https://huggingface.co/vllm-sr/Decision-2.0-Nox-4B
[kev]: https://huggingface.co/jaredpalmer/kev-0.8b
[d3]: https://huggingface.co/vllm-sr/d3-edge
