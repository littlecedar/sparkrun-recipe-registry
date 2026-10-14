# Decision-model research (2026-10-11)

Read-only research pass for the new decision lane. Candidate claims carry their
receipt URLs inline; `[INFERENCE]` marks a derived number, not a read one. The
co-location budget constants come from `recipes/embed/README.md` /
`recipes/rerank/README.md` (121.69 GiB usable; caps must sum ≤ ~0.85).

Selection weighting (`mad-science/TODO.md` decisions #11): node count > speed >
accuracy > memory footprint. Core lane constraint: co-location with the shipped
embed + rerank 2B pair (and eventually TTS) on ONE GB10 node.

## 1. Owner leads — resolution

### Lead A — "Cloudflare/Clef": RESOLVES as an open-weight family

| | Cloudflare/clef | Cloudflare/clef-flash |
|---|---|---|
| Backbone | `Qwen/Qwen3.8-27B` + vision encoder (frozen, prefill-only) | `Qwen/Qwen3.5-9B` + vision encoder |
| Weights on disk | 12 shards, **54.72 GB** + `joint_head.safetensors` 0.256 GB | 4 shards, **18.82 GB** + `joint_head` 0.244 GB |
| VRAM (vendor, single concurrency, 64k ctx) | **85 GB** | **41 GB** |
| License | Apache-2.0 | Apache-2.0 |
| Serving | SGLang `lmsysorg/sglang:dev-clef`, `POST /v1/systemone` | same |
| Latency (vendor Decision Index run) | median 209.3 ms / p95 238.6 ms | median **38.8 ms** / p95 122.4 ms |
| Multimodal | text, JSON, images, video | same |

Sources: https://huggingface.co/Cloudflare/clef,
https://huggingface.co/Cloudflare/clef-flash,
https://docs.sglang.io/cookbook/autoregressive/Cloudflare/clef,
https://www.theregister.com/ai-and-ml/2026/10/01/cloudflare-tries-to-outplay-jev-with-open-weight-clef-models/5300649,
https://developers.cloudflare.com/workers-ai/models/clef/.

The API is deliberately Jev/SystemOne-compatible (`choice`/`noul`/`score`
questions, calibrated probabilities, no text generation).

**Trap:** Cloudflare's leaderboard is self-reported (the vendor says so) and not
reproduced on the community board.

### Lead B — "Jev distillations on HF": RESOLVES, asymmetrically

1. **TypeSafe's Jev itself is closed** — API only, no weights
   (https://typesafe.ai/blog/introducing-system-one-models-and-jev,
   https://huggingface.co/spaces/multimodalart/jev-decision-index).
2. **The artifacts that deserve the name "Jev distillation" are
   `autotrust/JEV-9B` / `JEV-27B`** — explicit students of TypeSafe Jev 1.13,
   trained on `SargeDev/jev-distill-corpus-v3` (740,957 rows), publishing
   distribution-level fidelity no other reproduction publishes: mean
   **KL ≈ 0.019** to the teacher's output distributions (25,376 held-out rows),
   ECE 0.0007.
   https://huggingface.co/autotrust/JEV-9B,
   https://huggingface.co/autotrust/JEV-27B,
   https://huggingface.co/datasets/SargeDev/jev-distill-corpus-v3
   The Jev Decision Index space tracks ~130 open reproductions and separates
   trained/distilled from decoding/diffusion tricks; a "Jev" in a repo name
   proves nothing.

Microsoft-Decision-1 (accuracy reference in this space) is **closed** — Foundry
+ OpenRouter only. Keep as a quality ceiling, exclude from the lane.
https://commandline.microsoft.com/microsoft-decision-1-model-foundry

## 2. Shortlist (8 candidates beyond the leads)

Sizes are raw file bytes from the Hub; GiB conversions in §3.

| # | Candidate | Size | Latency (vendor, other silicon) | Quality | Licence | Runtime |
|---|---|---|---|---|---|---|
| 1 | `vllm-sr/Decision-2.0-Kai-0.6B` | 1.503 GB + head | **4.9 ms** | JevArena 48.6; Jev DI 16.3 | Apache-2.0 | vendor `vllm-srun` / `trust_remote_code`; CPU-capable |
| 2 | `autotrust/JEV-9B` | ~18 GB (bf16 9B + 173 MB LoRA) | ≈90 ms single / **2.5 ms batched @128** (~340 dec/s, B200) | ECE 0.0007, `noul` AUROC 0.996, 90.2% choice agreement, KL≈0.019 | Apache-2.0 | **native vLLM** with LoRA; System 2 = bit-identical base |
| 3 | `vllm-sr/Decision-2.0-Sol-2B` | 3.02+1.76 GB + head | 7.2 ms | JevArena 52.1; DI 29.5 | Apache-2.0 | vendor runtime; GGUF exists |
| 4 | `vllm-sr/Decision-2.0-Nox-4B` | ~7.8 GB [INFERENCE] | 12.9 ms | JevArena 63.6; DI 43.8 | Apache-2.0 | vendor runtime |
| 5 | `vllm-sr/d3-edge` (Decision 3.0) | 1.19 GB + readout | 6.7 ms text / +image 41.9 ms | DI 0.3 public 28.82 | Apache-2.0 | own `d3_server.py`; **0 downloads, zero boot history** |
| 6 | `jaredpalmer/kev-0.8b` | 3.8 GB resident | 22.7/16.1 ms per 6 q | decision-v7 0.838; breadth 0.586 | Apache-2.0 | own `kev.serve`; ladder 0.8B/4B(14.3 GB)/9B |
| 7 | `convaiinnovations/laya` | ~0.8 GB EN / ~0.65 GB mult | 32.8–39.5 ms | MASSIVE-EN 0.783, XNLI-EN 0.860 | Apache-2.0 | `laya-serve` on `/v1/systemone`; **CPU-real** |
| 8 | `fastino/GLiNER2.5-Decide` | 1.95 GB | n/a (encoder) | 60.2% exact on `fast-decisions` | Apache-2.0 | `gliner2[local]`; **O(n²·d) context ceiling, caps ctx 512** |

Also seen, not shortlisted: `Hanno-Labs/bosun-v3.1-1.7b` (own in-family suite
only), `internlm/Intern-Decision-*`, `Mapika/decider-*`,
`llm-semantic-router/Decision-1.0-*`, `bespokelabs/Bespoke-Nimble-9B`,
`denis-pplx/autojev-27b`, `kurcontko/clef-NVFP4` (27B is out of the envelope
regardless of format).

## 3. Co-location budget (one GB10 node)

Shipped tenants: embed 2B cap 0.25 (30.42 GiB) + reranker 2B cap 0.30 (36.51
GiB) = 66.93 GiB → **54.76 GiB free**. TTS pick: `hexgrad/Kokoro-82M`
(0.305 GiB, Apache-2.0) or `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` (1.687 GiB)
→ **~54.5 GiB left for the decision model**.

| Candidate | stack total (GiB) | % of 121.69 | fits? |
|---|---:|---:|:--:|
| Decision-2.0-Kai-0.6B | ~71 | 59% | ✅ |
| d3-edge | ~70 | 58% | ✅ |
| laya | ~68 | 56% | ✅ |
| GLiNER2.5-Decide | ~69 | 57% | ✅ |
| Decision-2.0-Sol-2B | ~75 | 61% | ✅ |
| Decision-2.0-Nox-4B | ~82 | 67% | ✅ |
| kev-0.8b / kev-4B | ~71 / ~81 | 58/66% | ✅ |
| **autotrust/JEV-9B** | ~86 | 71% | ✅ |
| **Cloudflare/clef-flash** | **105** | **87%** | ⚠️ only if embed/rerank caps drop to ~0.15/0.18 |
| Cloudflare/clef 27B | 146 | 120% | ❌ impossible — would need its own node |

Reservation ≠ weights: vLLM preallocates KV up to the cap; a prefill-only
decision model at ≤4–16k ctx needs a small own cap (~0.06–0.10 through 4B,
~0.16 for JEV-9B).

Free compute: GB10 big.LITTLE interleaved clusters — embed pins cores 5-9,
reranker 15-19; **cores 0-4 and 10-14 (A725) are unclaimed** and can host a
CPU-capable decision model (Kai-0.6B, laya) plus Kokoro at no GPU cost.

## 4. Recommended first three recipes

1. **`autotrust/JEV-9B`** — the lead, native vLLM:
   `vllm serve JEV-9B --enable-lora --max-lora-rank 32
   --lora-modules jev-decision=<path>/adapter_vllm
   --logprobs-mode processed_logprobs --max-model-len 4096`.
   Boot gate: verify `--logprobs-mode processed_logprobs` exists at our pinned
   vLLM build. LoRA-fetch mod precedent: `mods/provide-uno-lora-k2-horizon-7b/`.
2. **`Cloudflare/clef-flash`** — SGLang-native (`lmsysorg/sglang:dev-clef`,
   `/v1/systemone`), best small-tier published accuracy, 38.8 ms median,
   multimodal. Cost: forces an embed/rerank cap re-negotiation. Vendor numbers
   are self-reported/unreproduced — measure on our nodes.
3. **`vllm-sr/Decision-2.0-Kai-0.6B` (+ `Sol-2B` ladder arm)** — 4.9 ms, 1.4
   GiB, cheapest lane proof; cost is a new runtime family (`vllm-srun`) and
   `readiness: inference: false`.

Watch, do not build yet: `vllm-sr/d3-edge` (zero boot history, published hours
before this research).

## 5. Cross-cutting facts the recipes must handle

1. **Decision models are not chat models.** None answers
   `/v1/chat/completions`; they are prefill-only scorers behind
   `/v1/systemone` or bespoke endpoints. Any recipe inherits the pooling lane's
   readiness trap: `readiness: inference: false`, port + `/health` only.
2. **Published latencies are H200/B200/MI325X/T4/L4 numbers — none from GB10.**
   The lane's own C1-equivalent latency/throughput must be measured on
   the two free benchmark nodes before any selection claim.
3. **Accuracy yardstick exists and is community-owned:** Jev Decision Index
   0.2/0.3 suites (`multimodalart/jev-decision-index`), JevBench
   (`benchmarkheaven/JevBench`), TypeSafe's four workflow evals
   (evals.typesafe.ai); plus the `tool-eval-bench` decision plugin (Typed
   Decisions split) already adopted as the shared battery.
4. **Two drop-in runtime families only:** SGLang (clef/clef-flash) and vLLM
   (JEV-9B). Everything else needs a bespoke server or `trust_remote_code`.
5. **No lane artifacts exist yet** — no decision or TTS recipe, mod, test, or
   benchmarking profile in the tree; the 👂/👄/🎼 flags in `recipes/README.md`
   are declarative only.

6. **The `vllm-srun` golden check is bound to its own pinned revisions.** The
   runtime's recorded reference answers (`golden_answers.json`) and kernel
   choices attach to, and are looked up by, **content identity** — only for the
   revision the image's built-in table pins (`registry/tables/common.py`,
   `registry/builtin.py`). A newer Hub revision is *served* (readiness passes)
   but reports golden `unverified`, never `matched`; a different-content
   revision cannot be golden-vouched at all. Verified 2026-10-14 — see
   "Revision-drift determination" in `README.md`; receipts
   `~/benchmarks/decision-revision-20261014/` on the head.
