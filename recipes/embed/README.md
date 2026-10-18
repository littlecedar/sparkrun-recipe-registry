# Embed lane — `recipes/embed/`

_Brought to you by Little Cedar Group._

Multimodal embedding encoders (Qwen3-VL family), served with vLLM's pooling runner on a
single DGX Spark (GB10, 128 GB unified memory, TP=1). Moved out of `recipes/qwen3/` on
2026-10-10; the companion rerankers live in [`recipes/rerank/`](../rerank/README.md).

Both encoders are **pooling engines**: they expose `/v1/embeddings` (+ vLLM's Cohere
`/v2/embed`), `/health`, and `/v1/models` — and **no `/chat/completions`**. Both recipes
therefore disable sparkrun's default inference probe (`readiness: inference: false`, port +
`/health` only); the chat-completion probe can only time out, and `sparkrun run` would then
exit 1 on a healthy server.

Flags: 🚀 fast (≥ 50 t/s) · 🌲 lcg_favorite · 👀 vision · 📶 embedding · 🤏 smol.

## Contents

- [qwen3-vl-embedding-2b-vllm-b12x](#qwen3-vl-embedding-2b-vllm-b12x)
- [qwen3-vl-embedding-8b-awq-4bit-vllm-b12x](#qwen3-vl-embedding-8b-awq-4bit-vllm-b12x)
- [Serving the encoder correctly](#serving-the-encoder-correctly-client-contract)
- [Attic index](#attic-index)

## qwen3-vl-embedding-2b-vllm-b12x

[Qwen/Qwen3-VL-Embedding-2B](https://huggingface.co/Qwen/Qwen3-VL-Embedding-2B) —
multimodal embedding encoder, the low-cost tier, sized to colocate with the 2B reranker on
one Spark.

| | |
|---|---|
| params / dtype | 2B (2127.5M) · bf16 |
| weights on disk | 4.26 GB (single `model.safetensors`, 4,255,140,312 bytes) |
| TP / nodes | 1 / 1 |
| port | 8010 (the reranker holds 8011) |
| `gpu_memory_utilization` | 0.25 |
| context / batching | `max_model_len: 32768`, `max_num_batched_tokens: 16384`, `max_num_seqs: 32` |
| cpu_mask | `5-9` (fast X925 cluster half; solo: `-o cpu_mask=5-9,15-19`) |
| flags | `--runner pooling --convert embed --limit-mm-per-prompt '{"image": 4, "video": 1}' --attention-backend b12x --block-size 128 --load-format instanttensor` |
| tags | 🚀 fast · 🌲 lcg_favorite · 👀 vision · 📶 embedding · 🤏 smol |
| license | Apache-2.0 |

`--gpu-memory-utilization` is an **absolute cap on total device usage**, so the encoders and
rerankers that share a host must have caps that SUM to a safe fraction: this 0.25 + the 2B
reranker's 0.30 = 0.55 of 121 GB, in either startup order. Raising one without lowering the
other risks a startup `ValueError` in whichever engine launches second.

Knob notes carried out of the recipe's YAML comments (2026-10-14):

- `port: 8010` is distinct from the 2B reranker's 8011 so both engines can be up at once on one
  host.
- `max_model_len: 32768` is a deliberate cap, not the model's ceiling (native capacity is
  262,144); a long-document embed needs the room.
- `max_num_batched_tokens: 16384` is the first knob to raise for more throughput per step — this
  workload is prefill-bound, so that budget, not `max_num_seqs`, sets the profiled peak.
- `dtype: bfloat16` is explicit because the siblings declare `float32` inside `text_config`, and
  auto-resolution would double the footprint of a model we intend to colocate.

## qwen3-vl-embedding-8b-awq-4bit-vllm-b12x

[gonuit/Qwen3-VL-Embedding-8B-AWQ-4bit](https://huggingface.co/gonuit/Qwen3-VL-Embedding-8B-AWQ-4bit)
— 4-bit W4A16 quant of [Qwen/Qwen3-VL-Embedding-8B](https://huggingface.co/Qwen/Qwen3-VL-Embedding-8B),
the quality tier that still fits one Spark. Accepted by vLLM's compressed-tensors path
(`W4A16_ASYM`, served by `MarlinLinearKernel`); the vision tower is deliberately excluded
from quantization.

| | |
|---|---|
| params / dtype | 8B · awq4 (W4A16) |
| weights on disk | 6.01 GB |
| TP / nodes | 1 / 1 |
| port | 8012 (8010 embed-2B, 8011 rerank-2B, 8012 embed-8B) |
| `gpu_memory_utilization` | 0.30 |
| context / batching | `max_model_len: 32768`, `max_num_batched_tokens: 16384`, `max_num_seqs: 32` |
| cpu_mask | `5-9,15-19` (whole fast cluster; colocated: `-o cpu_mask=5-9`, reranker on `15-19`) |
| flags | `--runner pooling --convert embed --limit-mm-per-prompt '{"image": 4, "video": 1}' --attention-backend b12x --block-size 128 --load-format instanttensor` |
| tags | 🚀 fast · 🌲 lcg_favorite · 👀 vision · 📶 embedding · 🤏 smol |
| license | Apache-2.0 |

**Do not size memory from `sparkrun recipe vram`'s "Model weights" line.** For a 4-bit
checkpoint that line falls back to `param_count × dtype_bytes` (0.5 B/param for awq4) and
printed 3.73 GB here — the same number it prints for the 2B bf16 model — against a real
**6.01 GB** on disk. Verify against `model.safetensors.index.json` `metadata.total_size`
instead. This encoder colocates with `Qwen/Qwen3-VL-Reranker-8B` on one GB10:
32.80 + 32.24 = **65.03 GiB of 121.69 GiB (53%)** at the shipped 0.30/0.30 caps, ~57 GiB
still free.

## Serving the encoder correctly (client contract)

The checkpoint ships `config_sentence_transformers.json` with
`prompts {"default": "Represent the user's input."}` — the instruction the encoder was
trained with. vLLM loads that file and logs `Loaded prompt prefixes for input_type:
['default']`, but it applies the prefix **only** on the Cohere `/v2/embed` path, and only
when the request sets `input_type`. A plain `POST /v1/embeddings {"input": "..."}` body
resolves to `EmbeddingCompletionRequest`, which reaches the base pooling path: no task
prefix and no chat template. It returns vectors — computed from a prompt the model was
never trained on. **A 200-OK carrying a 2048-dim vector is therefore not evidence of a
correct embed.**

Two caller forms are supported by these recipes as written:

1. **chat form** — `{"input": [{"role": "system", "content": "Represent the user's input."},
   {"role": "user", "content": "..."}], "encoding_format": "float"}`
   applies the model's ChatML template; matches Qwen's published vLLM example. `input` is a
   **list of messages**, not `{"messages": [...]}` — the pinned vLLM's
   `EmbeddingChatInputRequest` declares `input: list[ChatCompletionMessageParam]` and rejects
   the nested form with a 400 listing every `EmbeddingCompletionRequest` alternative
   (`tools/pooling-bench.py`, `build_embed_request`).
2. **`POST /v2/embed`** with `{"texts": [...], "input_type": "default"}`
   makes vLLM prepend the checkpoint's own instruction for you.

The two are **not** byte-identical prompts (system message vs prefix); pick one after
comparing retrieval quality, not before. Pair the choice with a smoke test against the
endpoint you actually serve — [`tools/pooling-bench.py`](../../tools/pooling-bench.py)
checks dimension, distinct-inputs, and repeat-stability, not just the status line.

**Measuring the lane is a separate contract from serving it.** No standard benchmark profile
can measure a pooling engine: against one, `llama-benchy` fails its first task
(`Warmup failed: HTTP 404`, exit 1) and the run ends as `Error: Benchmark incomplete` —
measured 2026-10-15 on the installed stack (sparkrun 0.4.0, llama-benchy 0.4.0), so a
`concurrency-ladder.yaml` run against this lane is an error and never a number
(`tools/README.md` §pooling-bench.py). The lane's `units/s` numbers
(`attic/embed/AGENTS.md`) come from `tools/pooling-bench.py` at named concurrency points —
the C1/C4/C8/C16/C32 sweep at `--requests 100 --input-tokens 256 --mode embed-v1-chat`
(`.scratch/embed/csweep8b-order1-c*.json`). The same instrument is now reachable as a
sparkrun framework, `framework: pooling-bench` via
[`plugins/pooling_bench_framework.py`](../../plugins/pooling_bench_framework.py),
which is out-of-tree and therefore registers only after the one-line `plugins.paths` opt-in
documented there.

## Attic index

`attic/embed/` holds the lane's research record — every fact that is not part of a shipped
recipe's contract, so the recipe sections above can stay about serving.

| file | what it holds / question it answers |
|---|---|
| `AGENTS.md` | Measured performance and colocation numbers (2B-pair and 8B+8B throughput penalties, the 3,900 tok/s prefill bound), the b12x block-size hardware receipt, the `cpu_mask` / `convert` / `limit_mm_per_prompt` knob rationale, negative results, the guard-suite map, and the retired 8B BF16 tier (measured, never shipped; retired 2026-10-18) with its receipt. |
