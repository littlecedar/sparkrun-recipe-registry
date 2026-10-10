# Embed lane — `recipes/embed/`

_Brought to you by Little Cedar Group._

Multimodal embedding encoders (Qwen3-VL family), served with vLLM's pooling runner on a
single DGX Spark (GB10, 128 GB unified memory, TP=1). Moved out of `recipes/qwen3/` on
2026-10-10; the companion rerankers live in [`recipes/rerank/`](../rerank/README.md).

| recipe | runtime | model | flags | C1 t/s | notes |
|---|---|---|---|---|---|
| `qwen3-vl-embedding-2b-vllm-b12x` | vllm | [Qwen/Qwen3-VL-Embedding-2B] | 🚀🌲👀📶 | — | multimodal embedding encoder, colocatable with the 2B reranker. |
| `qwen3-vl-embedding-8b-awq-4bit-vllm-b12x` | vllm | [gonuit/Qwen3-VL-Embedding-8B-AWQ-4bit] | 🚀🌲👀📶 | — | 4-bit W4A16 encoder, quality tier. |

Flags: 🚀 fast (≥ 50 t/s) · 🌲 lcg_favorite · 👀 vision · 📶 embedding.

Facts that span both lanes (kept here because neither recipe alone states them):

- **The 2B pair colocates on one Spark** (encoder `gpu_memory_utilization: 0.25` +
  reranker `0.30` = 0.55 of 121 GB, about 66 GB, leaving ~54 GB for the OS and the page
  cache that feeds safetensors reads; ports 8010/8011; `cpu_mask` splits the fast cluster
  5-9 / 15-19). vLLM's `--gpu-memory-utilization` is an **absolute cap on total device
  usage**, so the two engines' caps must SUM to a safe fraction — raising one without
  lowering the other risks a startup `ValueError` in whichever engine launches second,
  in either startup order.
- **The 8B pair is the quality tier**; its colocation budget, the fit/throughput penalty,
  and the vram-sizing caveat are documented below.
- **Readiness probes are pooling-aware**: a pooling engine has no chat endpoint, so the
  recipes disable sparkrun's default inference probe (`readiness: inference: false`) and
  keep port + `/health` only.
- **Evidence docs** (git-ignored): `QWEN3-EMBED-OPTIMIZATION-WORK.md`, `EMBED-JOURNAL.md`.
- **Guard:** `tests/test_qwen3_vl_embeddings.py` (42 tests) covers both lanes' recipes
  and the shared chat template mod (`mods/provide-qwen3-vl-rerank-template/`).

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

1. **chat form** — `{"input": {"messages": [{"role": "system", "content":
   "Represent the user's input."}, {"role": "user", "content": "..."}]}}`
   applies the model's ChatML template; matches Qwen's published vLLM example.
2. **`POST /v2/embed`** with `{"texts": [...], "input_type": "default"}`
   makes vLLM prepend the checkpoint's own instruction for you.

The two are **not** byte-identical prompts (system message vs prefix); pick one after
comparing retrieval quality, not before.

Both recipes disable the default readiness probe (`readiness: inference: false`, port +
`/health` only) because a pooling engine has no chat endpoint and the chat-completion probe
can only time out — `sparkrun run` would then exit 1 on a healthy server. Pair it with a
smoke test against the endpoint you actually serve (`QWEN3-EMBED-OPTIMIZATION-WORK.md` §5).

Deliberate omissions and knob notes, all cheap to re-test and expensive to get wrong:

- `--async-scheduling` is **not** set. vLLM decides it for pooling runners itself ("The
  current implementation of asynchronous scheduling negatively impacts performance of
  pooling models, so we disable by default"), and the explicit-true branch hard-fails on
  other incompatibilities — no-op at best, launch failure at worst. The 0.4.0 recipes
  shipped with it; that is corrected here.
- `cpu_mask` pins the fast cluster only. GB10 is big.LITTLE with the clusters **interleaved**
  in the CPU numbering: the 10 X925 cores @ 3.9 GHz are 5-9 and 15-19, the 10 A725 cores
  @ 2.8 GHz are 0-4 and 10-14. The 2B encoder owns 5-9 and the colocated reranker 15-19, so
  neither engine's tokenizer, chat-templating, image-decode, or API worker lands on a slow
  core or contends with the other. Never use a mask that spans both clusters for a
  latency-sensitive engine. Solo (no reranker): `-o cpu_mask=5-9,15-19`.
- `limit_mm_per_prompt` caps multimodal inputs at 4 images (vLLM's default is 999), which
  bounds the profiled multimodal peak on a box that packs two engines; text retrieval and
  screenshot/document embedding both fit well inside 4. The folded style with embedded
  quotes is load-bearing — the JSON must reach the shell as one word. `convert` and
  `limit_mm_per_prompt` have no sparkrun flag-map entry, so they reach vLLM only through the
  `{...}` placeholders; `-o` warns "unmapped" while still taking effect, so do not delete
  them.

## b12x block size (both recipes)

`attention_backend: b12x` refuses vLLM's default block size. VERIFIED on hardware
2026-09-19 (authorized DGX Spark trial node; host in the git-ignored `EMBED-JOURNAL.md`):
it aborts at cache-config time with `ValueError: b12x requires --block-size in (64, 128),
got 16`, before any weight loading — so the flag combination that shipped could not boot at
all, regardless of anything else. `_B12X_SUPPORTED_PAGE_SIZES = (64, 128)` and
`_B12X_PREFERRED_PAGE_SIZE = 128` in `vllm/v1/attention/backends/b12x.py` at the pinned
commit, hence 128. `block_size` **is** in sparkrun's `VLLM_FLAG_MAP`
(`runtimes/_vllm_common.py:371`), so `-o block_size=64` works without the "unmapped"
warning the other knobs print — but 64 is only for A/B-ing partial-page KV waste on
short-text-heavy traffic, not a speed lever to reach without measuring.

## 8B-AWQ encoder (quality tier)

- **Colocating two 8B engines is real, not a forced either/or.** An earlier comment
  asserted "two 8B-scale engines will not fit a single Spark's memory budget" and made this
  recipe a *replacement* for the 2B encoder. That was never tested and it is false: this
  encoder and `Qwen/Qwen3-VL-Reranker-8B` both booted and served colocated on one GB10
  trial node at the shipped 0.30/0.30 caps, using 32.80 + 32.24 = **65.03 GiB of 121.69 GiB
  (53%)**, with ~57 GiB still free, no memory error, and the reranker passing the
  cross-encoder symmetry check. (F22)
- **Fit is not free.** Under simultaneous load the encoder fell **22.52 → 9.89 units/s
  (2.28×)** and the reranker **28.76 → 22.57 (1.27×)** — matching the 2B-pair penalty in
  `QWEN3-EMBED-OPTIMIZATION-WORK.md` §5 item 5. Size capacity from the colocated numbers,
  never from solo.
- The 8B+8B measurement used the **shipped** defaults (encoder `5-9,15-19`, reranker
  `15-19`), so the two engines overlapped on 15-19. That is the honest qualifier on those
  numbers, and it is also a second, independent confirmation that masks are not the
  contended resource here: sharing five cores changed nothing measurable, exactly as §5 item
  5(b) found (0.7% between shared and disjoint).
- **Do not size memory from `sparkrun recipe vram`'s "Model weights" line.** For a 4-bit
  checkpoint that line falls back to `param_count × dtype_bytes` (0.5 B/param for awq4) and
  printed 3.73 GB here — the same number it prints for the 2B bf16 model — against a real
  **6.01 GB** on disk. Verify against `model.safetensors.index.json`
  `metadata.total_size` instead:

  ```
  curl -s https://huggingface.co/gonuit/Qwen3-VL-Embedding-8B-AWQ-4bit/raw/main/model.safetensors.index.json \
    | python3 -c 'import json,sys;print(json.load(sys.stdin)["metadata"]["total_size"]/1e9)'
  ```

  (F12)
- **4-bit is not what makes this encoder slow.** The same engine in native BF16 (16 GB of
  weights, no quantization anywhere) prefills within **1.2%** of this one at its own best
  concurrency, while consuming 108% more memory and leaving 41% less KV at an identical
  `gpu_memory_utilization`. The encoder is prefill-bound at roughly **3,900 tokens/s** on a
  GB10 regardless of format or batching. Keep 4-bit: it is free, and the memory it saves is
  the batch headroom.
- **compressed-tensors `W4A16_ASYM` inside a multimodal Qwen3-VL works.** The open question
  was whether vLLM's compressed-tensors path accepts that scheme in a Qwen3-VL whose vision
  tower is deliberately excluded from quantization, and whether the pooling adapters
  coexist with it. RESOLVED: the recipe loads and serves; the serve log reports `Using
  MarlinLinearKernel for CompressedTensorsWNA16` with no error or traceback, and the
  vectors pass the 4096-dim, distinct-inputs, and repeat-stability checks in
  `tools/pooling-bench.py`. (F21)
- Two flag corrections carried over from the 2B recipe: `attention_backend` was
  `flashinfer-b12x` (and the 2B's old `b12x_attn`), neither of which is a member of vLLM's
  `AttentionBackendEnum` — the member is `B12X` (case-insensitive on the CLI), so neither
  could resolve to a backend; both are now `b12x`. `--async-scheduling` is removed and the
  taskset mask is narrowed to the X925 cluster via `{cpu_mask}`, for the same reasons as the
  2B recipe.

<!-- Links -->
[Qwen/Qwen3-VL-Embedding-2B]: https://huggingface.co/Qwen/Qwen3-VL-Embedding-2B
[gonuit/Qwen3-VL-Embedding-8B-AWQ-4bit]: https://huggingface.co/gonuit/Qwen3-VL-Embedding-8B-AWQ-4bit
