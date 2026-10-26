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

Flags: 🚀 fast (C1 > 50 u/s) · 🌲 lcg_favorite · 👀 vision · 🔃 reranking · 🤏 smol.

## Shipped recipes

Both ship on `ghcr.io/spark-arena/dgx-vllm-eugr-nightly-b12x@sha256:cf5a2a5324af897e1b576eecb3018331d2df0fad2285d61d4b109743be6434d8`, one node, TP=1,
`attention_backend: b12x` (`block_size: 128`), `max_model_len: 8192`,
`max_num_batched_tokens: 8192`, `max_num_seqs: 32`, `dtype: bfloat16`, and the mods
`@littlecedar/mods/pip-install-orjson` +
`mods/provide-qwen3-vl-rerank-template`. Both are pooling engines: they
serve score/rerank endpoints, not chat — read
[Pooling endpoints](#pooling-endpoints--the-client-contract) before writing a client.

**Knob rationale** (moved out of the recipe YAML 2026-10-14):

- `max_model_len: 8192` bounds the worst-case (query, document) pair — the trained context is
  32k, but every pair pays the template + instruction overhead; raise with `-o` for long
  documents.
- `dtype: bfloat16` is explicit: `config.json` declares bfloat16 at the top level but float32
  inside `text_config`, so the value says what we mean rather than trusting dtype resolution.
- `block_size: 128` is required by b12x (which aborts at cache-config time unless it is 64 or
  128; vLLM's default is 16); 128 is `_B12X_PREFERRED_PAGE_SIZE` at the pinned commit.
- `convert: classify` is written down explicitly so a default-table change cannot quietly turn
  the recipe into a different pooling task — the launch then fails loudly instead.
- `limit_mm_per_prompt` is a folded, embedded-quoted JSON so it survives as ONE shell word.

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
- **Solo ladder (2026-10-26, spares-lane, `.30`, first boot under `tools/boot-watchdog.py`):** the
  reranker's half alone (no encoder co-resident) scores **C1 106.7 · C4 525.8 units/s** (10
  docs/query, 128-token docs, 32/32 ok; p50 97.0/71.0 ms), with the intended cross-encoder
  asymmetry (0.688) and an exact rank fixture (0.996/0.646/0.216) — the cells the shipped 119.29
  C8 figure does not cover. Receipt `~/benchmarks/spares-20261026/qwen3vl-rerank-2b-solo/RECEIPT.md`.
- **license:** Apache-2.0 (`Qwen/Qwen3-VL-Reranker-2B` card).

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
- **residency (owner decision 2026-10-15):** stays **shipped** as the deliberate quality tier —
  the ~4× per-scored-document cost against the 2B is the accepted trade-off, not a defect. The
  checkpoint is **not** pre-cached: the first launch cold-fetches ~16 GB/node, taken as a
  cold-fetch cost rather than a residency. Closed by this decision; reopen only with new data.
- **license:** Apache-2.0 (`Qwen/Qwen3-VL-Reranker-8B` card).

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
  `recipes/rerank/mods/provide-qwen3-vl-rerank-template` before the serve line runs; the checkpoint's own
  `chat_template.jinja` has no `query`/`document` role handling and would silently score an
  empty pair. The mod resolves its output dir as
  `${MOD_CACHEDIR:-${XDG_CACHE_HOME:-/cache/runtime}}`, and a mod cannot export variables
  into the serve command — so if you set `MOD_CACHEDIR` elsewhere you **must** override the
  recipe path to match, or vLLM quietly falls back to the checkpoint's wrong template.
  Relocating via `runtime_cache:` in sparkrun config keeps the two aligned automatically.
- **Retrieve/score a pair** with the served template; the full derivation of this contract,
  the knob rationale, and the pre-split evidence docs are in
  [`../../attic/rerank/AGENTS.md`](../../attic/rerank/AGENTS.md).

**Measuring it is a separate contract — and no standard profile can do it.** Pointed at a
pooling endpoint, `llama-benchy` fails its first task (`Warmup failed: HTTP 404`, exit 1) and
sparkrun ends the run as `Error: Benchmark incomplete` — measured 2026-10-15 on the installed
stack (sparkrun 0.4.0, llama-benchy 0.4.0), so a `benchmarking/*.yaml` profile against these
recipes is an error, never a number (`tools/README.md` §pooling-bench.py). The 2B's **119.29**
and the 8B's **28.76** units/s quoted above are `units / wall_seconds` from
`tools/pooling-bench.py` runs at the shape those rows name — C8, 10 docs/query, 128
tokens/document — specifically `.scratch/embed/solo-rr34-c8.json` (1000 units / 8.383 s) and
`.scratch/embed/ctrl-8b-rerank-solo.json` (500 units / 17.383 s), not from a
`benchmarking/*.yaml` profile. The same instrument is now reachable from `sparkrun` itself as
`framework: pooling-bench` with `kind: rerank` and `docs_per_query`, via
[`plugins/pooling_bench_framework.py`](../../plugins/pooling_bench_framework.py)
(an out-of-tree plugin: it registers only after the one-line `plugins.paths` opt-in
documented there).

## Attic index

Everything that is not a shipped-recipe fact lives in [`attic/rerank/`](../../attic/rerank/).

| file | holds | answers |
|---|---|---|
| [`AGENTS.md`](../../attic/rerank/AGENTS.md) | the retired lane material from this README (2026-10-14): cross-lane colocation facts, the full "serving the reranker correctly" rationale (`--convert auto` / arch derivation / `_CONFIG_REGISTRY` / `MOD_CACHEDIR`), deliberate omissions (`--async-scheduling`, `cpu_mask` big.LITTLE map, no flag-map entries), `dtype` and `max_model_len` rationale, the b12x `--block-size` receipt, the 8B quality-tier measurement and port/alternatives note, the evidence docs, and the guard-suite pointer | why the shipped recipes look the way they do, and what was measured/decided for the 8B variant |

<!-- Links -->
[Qwen/Qwen3-VL-Reranker-2B]: https://huggingface.co/Qwen/Qwen3-VL-Reranker-2B
[Qwen/Qwen3-VL-Reranker-8B]: https://huggingface.co/Qwen/Qwen3-VL-Reranker-8B
