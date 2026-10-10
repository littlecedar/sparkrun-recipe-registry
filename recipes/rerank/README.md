# Rerank lane — `recipes/rerank/`

_Brought to you by Little Cedar Group._

Multimodal cross-encoder rerankers (Qwen3-VL family), served with vLLM on a single
DGX Spark (GB10, 128 GB unified memory, TP=1). Moved out of `recipes/qwen3/` on
2026-10-10; the companion encoders live in [`recipes/embed/`](../embed/README.md).

| recipe | runtime | model | flags | C1 t/s | notes |
|---|---|---|---|---|---|
| `qwen3-vl-reranker-2b-vllm-b12x` | vllm | [Qwen/Qwen3-VL-Reranker-2B] | 🚀🌲👀🔃 | — | VL reranker (cross-encoder), colocatable with the 2B encoder. |
| `qwen3-vl-reranker-8b-vllm-b12x` | vllm | [Qwen/Qwen3-VL-Reranker-8B] | 🌲👀🔃 | — | quality-tier reranker; colocation budget documented in the recipe. |

Flags: 🚀 fast (≥ 50 t/s) · 🌲 lcg_favorite · 👀 vision · 🔃 reranking.

Facts that span both lanes (kept here because neither recipe alone states them):

- **The 2B pair colocates on one Spark** (reranker `gpu_memory_utilization: 0.30` +
  encoder `0.25` = 0.55; ports 8011/8010; `cpu_mask` splits the fast cluster 15-19 / 5-9).
  vLLM's `--gpu-memory-utilization` is an **absolute cap on total device usage**, so the
  two engines' caps must SUM to a safe fraction — raising one without lowering the other
  risks a startup `ValueError` in whichever engine launches second.
- **The reranker is asymmetric (cross-encoder)**: it resolves `classify` /
  `token_classify` rather than a score-embedding path, and image documents are consumed
  as vision tokens. The chat template that makes this correct ships via
  `mods/provide-qwen3-vl-rerank-template/`; a reranker that returns HTTP 200 with
  plausible-looking scores while computing them the wrong way is the failure mode the
  guard suite exists for.
- **Evidence docs** (git-ignored): `QWEN3-EMBED-OPTIMIZATION-WORK.md`, `EMBED-JOURNAL.md`.
- **Guard:** `tests/test_qwen3_vl_embeddings.py` (42 tests) covers both lanes' recipes
  and the shared chat template mod.

<!-- Links -->
[Qwen/Qwen3-VL-Reranker-2B]: https://huggingface.co/Qwen/Qwen3-VL-Reranker-2B
[Qwen/Qwen3-VL-Reranker-8B]: https://huggingface.co/Qwen/Qwen3-VL-Reranker-8B
