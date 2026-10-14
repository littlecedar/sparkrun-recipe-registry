# Rerank lane — `recipes/rerank/`

_Brought to you by Little Cedar Group._

Multimodal cross-encoder rerankers (Qwen3-VL family), served with vLLM on a single
DGX Spark (GB10, 128 GB unified memory, TP=1). Moved out of `recipes/qwen3/` on
2026-10-10; the companion encoders live in [`recipes/embed/`](../embed/README.md).

## Contents

- [Shipped recipes](#shipped-recipes)
  - [`qwen3-vl-reranker-2b-vllm-b12x`](#qwen3-vl-reranker-2b-vllm-b12x)
  - [`qwen3-vl-reranker-8b-vllm-b12x`](#qwen3-vl-reranker-8b-vllm-b12x)
- [Pooling endpoints — the client contract](#pooling-endpoints--the-client-contract)
- [Attic index](#attic-index)

Flags: 🚀 fast (≥ 50 t/s) · 🌲 lcg_favorite · 👀 vision · 🔃 reranking · 🤏 smol.

## Shipped recipes

Both ship on `ghcr.io/spark-arena/dgx-vllm-eugr-nightly-b12x:latest`, one node, TP=1,
`attention_backend: b12x` (`block_size: 128`), `max_model_len: 8192`,
`max_num_batched_tokens: 8192`, `max_num_seqs: 32`, `dtype: bfloat16`, and the mods
`@littlecedar/mods/pip-install-orjson` +
`@littlecedar/mods/provide-qwen3-vl-rerank-template`. Both are pooling engines: they
serve score/rerank endpoints, not chat — read
[Pooling endpoints](#pooling-endpoints--the-client-contract) before writing a client.

### `qwen3-vl-reranker-2b-vllm-b12x`

- **repo id:** [`Qwen/Qwen3-VL-Reranker-2B`] — 2B params, bf16.
- **size / memory:** `gpu_memory_utilization: 0.30`, port **8011**. Colocates with the
  2B encoder (`0.25`): 0.30 + 0.25 = **0.55 of 121 GB (~66 GB)**, leaving ~54 GB for the
  OS and the page cache that feeds safetensors reads. vLLM's `--gpu-memory-utilization`
  is an **absolute** device cap, so the two engines' caps must SUM — raising one without
  lowering the other risks a startup `ValueError` in whichever engine launches second.
- **CPU:** `cpu_mask: 15-19` (the reranker's half of the GB10 fast cluster; the colocated
  encoder owns 5-9). Solo: `-o cpu_mask=5-9,15-19`.
- **TP / load:** `tensor_parallel: 1`, `load_format: instanttensor`.
- **flags:** 🚀🌲👀🔃🤏 (`fast, lcg_favorite, vision, reranking, smol`).
- **pooling caveat:** cross-encoder — the recipe pins `convert: classify` with the
  `Qwen3VLForSequenceClassification` / `classifier_from_token: ["no","yes"]` override;
  readiness is port + `/health` only.
- **licence:** Apache-2.0 (`Qwen/Qwen3-VL-Reranker-2B` card).

### `qwen3-vl-reranker-8b-vllm-b12x`

- **repo id:** [`Qwen/Qwen3-VL-Reranker-8B`] — 8B params, bf16. The quality tier.
- **size / memory:** `gpu_memory_utilization: 0.30`, port **8015** — outside the shipped
  8010/8011/8012 plan, so this never shadows the 2B reranker; the two are alternatives,
  not co-residents. Colocates with the 8B AWQ encoder: **65.03 GiB of 121.69 GiB** at the
  shipped caps; the pair's throughput penalty is in the embed lane's README.
- **CPU:** `cpu_mask: 15-19`, as the 2B.
- **TP / load:** `tensor_parallel: 1`, `load_format: auto`.
- **flags:** 🌲👀🔃🤏 (`lcg_favorite, vision, reranking, smol`) — **not** `fast`,
  deliberately: 28.76 units/s solo against the 2B's 119.29 on the same traffic shape
  (C8, 10 docs/query, 128 tokens/document), ~4× slower per scored document.
- **pooling caveat:** same as the 2B (cross-encoder, `convert: classify`, port + `/health`).
- **licence:** Apache-2.0 (`Qwen/Qwen3-VL-Reranker-8B` card).

## Pooling endpoints — the client contract

These recipes serve a **cross-encoder**, and getting that wrong is silent.

- **`/v1/score`** (and `/rerank`, `/v1/rerank`, `/v2/rerank`) is what these engines answer.
  There is no chat endpoint, so both recipes set `readiness: inference: false` (port +
  `/health` only) — the default chat-completion probe can only time out and `sparkrun run`
  would exit 1 on a healthy server.
- **`--convert auto` is a trap.** The shipped `architectures` is the base generative class,
  so vLLM's resolver falls through to its pooling catch-all and serves the checkpoint as a
  generic LAST-pooling *embedding* model: `/v1/score` then answers as a **bi-encoder**
  (SCORE_TYPE_MAP: embed → bi-encoder, classify → cross-encoder) with wrong scores, HTTP
  200, no warning. The recipe rewrites the arch to `Qwen3VLForSequenceClassification`,
  seeds the 2-way-softmax classifier from the `"no"`/`"yes"` token logits (exactly the
  `hf_overrides` the Qwen model card publishes, reaching vLLM through the `{hf_overrides}`
  placeholder), and writes `convert: classify` down explicitly so a default-table change
  fails loudly instead of quietly serving a different pooling task. Launch-log check: vLLM
  prints `Resolved architecture: ...` and must **not** print
  ``Resolved `--convert auto` to `--convert embed` ``.
- **Chat template.** `reranker_chat_template` is published by
  `mods/provide-qwen3-vl-rerank-template` before the serve line runs; the checkpoint's own
  `chat_template.jinja` has no `query`/`document` role handling and would silently score an
  empty pair. The mod resolves its output dir as
  `${MOD_CACHEDIR:-${XDG_CACHE_HOME:-/cache/runtime}}`, and a mod cannot export variables
  into the serve command — so if you set `MOD_CACHEDIR` elsewhere you **must** override the
  recipe path to match, or vLLM quietly falls back to the checkpoint's wrong template.
  Relocating via `runtime_cache:` in sparkrun config keeps the two aligned automatically.
- **Retrieve/score a pair** with the served template; the full derivation of this contract,
  the knob rationale, and the pre-split evidence docs are in
  [`../../attic/rerank/AGENTS.md`](../../attic/rerank/AGENTS.md).

## Attic index

Everything that is not a shipped-recipe fact lives in [`attic/rerank/`](../../attic/rerank/).

| file | holds | answers |
|---|---|---|
| [`AGENTS.md`](../../attic/rerank/AGENTS.md) | the retired lane material from this README (2026-10-14): cross-lane colocation facts, the full "serving the reranker correctly" rationale (`--convert auto` / arch derivation / `_CONFIG_REGISTRY` / `MOD_CACHEDIR`), deliberate omissions (`--async-scheduling`, `cpu_mask` big.LITTLE map, no flag-map entries), `dtype` and `max_model_len` rationale, the b12x `--block-size` receipt, the 8B quality-tier measurement and port/alternatives note, the evidence docs, and the guard-suite pointer | why the shipped recipes look the way they do, and what was measured/decided for the 8B variant |

<!-- Links -->
[Qwen/Qwen3-VL-Reranker-2B]: https://huggingface.co/Qwen/Qwen3-VL-Reranker-2B
[Qwen/Qwen3-VL-Reranker-8B]: https://huggingface.co/Qwen/Qwen3-VL-Reranker-8B
