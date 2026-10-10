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
  reranker `0.30` = 0.55; ports 8010/8011; `cpu_mask` splits the fast cluster 5-9 / 15-19).
  vLLM's `--gpu-memory-utilization` is an **absolute cap on total device usage**, so the
  two engines' caps must SUM to a safe fraction — raising one without lowering the other
  risks a startup `ValueError` in whichever engine launches second.
- **The 8B pair is the quality tier** and carries its own colocation budget, documented
  in `recipes/rerank/`'s recipe.
- **Readiness probes are pooling-aware**: a pooling engine has no chat endpoint, so the
  recipes disable sparkrun's default inference probe (`readiness: inference: false`) and
  keep port + `/health` only.
- **Evidence docs** (git-ignored): `QWEN3-EMBED-OPTIMIZATION-WORK.md`, `EMBED-JOURNAL.md`.
- **Guard:** `tests/test_qwen3_vl_embeddings.py` (42 tests) covers both lanes' recipes
  and the shared chat template mod (`mods/provide-qwen3-vl-rerank-template/`).

<!-- Links -->
[Qwen/Qwen3-VL-Embedding-2B]: https://huggingface.co/Qwen/Qwen3-VL-Embedding-2B
[gonuit/Qwen3-VL-Embedding-8B-AWQ-4bit]: https://huggingface.co/gonuit/Qwen3-VL-Embedding-8B-AWQ-4bit
