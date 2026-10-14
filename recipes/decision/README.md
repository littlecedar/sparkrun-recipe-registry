# Decision lane

Small models that make classification / routing / judgment calls — **prefill-only scorers, not
chat models** — co-located with the shipped embed + rerank pair on **one** DGX Spark (the lane's
core constraint: nodes are at a premium). This README covers the four shipped recipes. The
candidate research, verified surfaces, official scores, the CPU+GPU tandem probe and the
revision-drift determination are archived under [`attic/decision/`](../../attic/decision/)
(indexed at the end).

## Contents

- [jev-9b-decision-vllm](#jev-9b-decision-vllm)
- [clef-flash-decision-sglang](#clef-flash-decision-sglang)
- [kai-0.6b-decision-vllm-srun](#kai-06b-decision-vllm-srun)
- [sol-2b-decision-vllm-srun](#sol-2b-decision-vllm-srun)
- [Operating constraints](#operating-constraints)
  - [The `vllm-srun` runtime (Kai + Sol)](#the-vllm-srun-runtime-kai--sol)
  - [Served-id caveat](#served-id-caveat)
  - [Co-location budget](#co-location-budget)
- [Attic index](#attic-index)

Accuracy on the shared instrument (`tool-eval-bench` v2.8.0, Typed Decisions test split — 400
cases / 2000 decisions): **clef-flash 70.3% > JEV-9B 67.0% > Sol-2B 55.0% > Kai-0.6B 47.5%**.

### jev-9b-decision-vllm

| field | value |
|---|---|
| repo id | [`autotrust/JEV-9B`][jev] (pinned `7ac669b8`), + the `jev-decision` LoRA (rank 32) |
| accuracy | **67.0%** (1340/2000), ★★ |
| size | 18 GB (bf16 9B + 173 MB LoRA); ~17 GiB weights |
| API | `/v1/completions` — the card's native SystemOne scoring shape (`logprobs` + top-level `allowed_token_ids`); the server runs `--logprobs-mode processed_logprobs --enable-lora`. The chat-template surface shifts the distribution and can flip argmaxes, so score on completions, not chat. |
| TP | 1 |
| flags | 🤏 smol · 🚮 classifier |
| status | **BOOT-VERIFIED 2026-10-11** (`.34`) |

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

## Operating constraints

### The `vllm-srun` runtime (Kai + Sol)

The Decision 2.0 models run on the vendor's own runtime, **`vllm-srun`** — a standalone
single-process server shipped inside the `vllm-sr` router image (not on PyPI, no image of its
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

Co-location with the shipped embed + rerank 2B pair (and eventually TTS) on ONE GB10 node is the
lane's core constraint. After the embed (0.25) + rerank (0.30) caps, ~54.5 GiB of the node's
121.69 GiB is free (Kokoro-82M costs 0.3 GiB of it) — everything here through JEV-9B fits;
clef-flash at the vendor's 41 GB needs the embed/rerank caps lowered to ~0.15/0.18 first, a
cap-bookkeeping decision rather than a memory wall. Cores: embed pins 5-9 and rerank 15-19 (the
X925 cluster), so clef-flash (and the CPU Decision 2.0 arms) pin 0-4,10-14 (A725) to keep the
tenants from contending.

## Attic index

Files under [`attic/decision/`](../../attic/decision/):

| file | what it holds |
|---|---|
| [`DECISION-MODELS-RESEARCH.md`](../../attic/decision/DECISION-MODELS-RESEARCH.md) | The 2026-10-11 read-only candidate research: both owner leads resolved, the 8-model shortlist, the one-node co-location budget math, the recommended first recipes, and the cross-cutting facts the recipes must handle. |
| [`AGENTS.md`](../../attic/decision/AGENTS.md) | Archived lane notes moved out of this README (2026-10-14): the verified surfaces, the JEV-9B and clef-flash official scores, the Kai/Sol `vllm-srun` arms record, the CPU+GPU tandem probe, and "what these models are". |

[jev]: https://huggingface.co/autotrust/JEV-9B
[clef]: https://huggingface.co/Cloudflare/clef-flash
[kai]: https://huggingface.co/vllm-sr/Decision-2.0-Kai-0.6B
[sol]: https://huggingface.co/vllm-sr/Decision-2.0-Sol-2B
