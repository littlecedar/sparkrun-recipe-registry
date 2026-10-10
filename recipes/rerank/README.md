# Rerank lane — `recipes/rerank/`

_Brought to you by Little Cedar Group._

Multimodal cross-encoder rerankers (Qwen3-VL family), served with vLLM on a single
DGX Spark (GB10, 128 GB unified memory, TP=1). Moved out of `recipes/qwen3/` on
2026-10-10; the companion encoders live in [`recipes/embed/`](../embed/README.md).

| recipe | runtime | model | flags | C1 t/s | notes |
|---|---|---|---|---|---|
| `qwen3-vl-reranker-2b-vllm-b12x` | vllm | [Qwen/Qwen3-VL-Reranker-2B] | 🚀🌲👀🔃 | — | VL reranker (cross-encoder), colocatable with the 2B encoder. |
| `qwen3-vl-reranker-8b-vllm-b12x` | vllm | [Qwen/Qwen3-VL-Reranker-8B] | 🌲👀🔃 | — | quality-tier reranker; colocation budget and the fit penalty documented below. |

Flags: 🚀 fast (≥ 50 t/s) · 🌲 lcg_favorite · 👀 vision · 🔃 reranking.

Facts that span both lanes (kept here because neither recipe alone states them):

- **The 2B pair colocates on one Spark** (reranker `gpu_memory_utilization: 0.30` +
  encoder `0.25` = 0.55 of 121 GB, about 66 GB, leaving ~54 GB for the OS and the page
  cache that feeds safetensors reads; ports 8011/8010; `cpu_mask` splits the fast cluster
  15-19 / 5-9). vLLM's `--gpu-memory-utilization` is an **absolute cap on total device
  usage**, so the two engines' caps must SUM to a safe fraction — raising one without
  lowering the other risks a startup `ValueError` in whichever engine launches second,
  in either startup order.
- **The reranker is asymmetric (cross-encoder)**: it resolves `classify` /
  `token_classify` rather than a score-embedding path, and image documents are consumed
  as vision tokens. The chat template that makes this correct ships via
  `mods/provide-qwen3-vl-rerank-template/`; a reranker that returns HTTP 200 with
  plausible-looking scores while computing them the wrong way is the failure mode the
  guard suite exists for.
- **Evidence docs** (git-ignored): `QWEN3-EMBED-OPTIMIZATION-WORK.md`, `EMBED-JOURNAL.md`.
- **Guard:** `tests/test_qwen3_vl_embeddings.py` (42 tests) covers both lanes' recipes
  and the shared chat template mod.

## Serving the reranker correctly (client contract)

`--convert auto` is a trap here: the shipped `architectures` is the base generative class,
so vLLM's resolver falls through to its pooling catch-all and serves the checkpoint as a
generic LAST-pooling *embedding* model. `/v1/score` then answers as a **bi-encoder**
(SCORE_TYPE_MAP: embed → bi-encoder, classify → cross-encoder) instead of the trained
cross-encoder — wrong scores, HTTP 200, no warning. The recipe rewrites the arch to
`Qwen3VLForSequenceClassification` and seeds the 2-way-softmax classifier from the
`"no"`/`"yes"` token logits, exactly the `hf_overrides` the Qwen model card publishes.
Derive the string, never retype it:
`config["architectures"][0].replace("ConditionalGeneration", "SequenceClassification")` —
it must match vLLM's `_CONFIG_REGISTRY` key, which is also what enables the
`is_original_qwen3_reranker` / `from_2_way_softmax` pooler hook.

The architecture suffix table maps `...ForSequenceClassification` to `(pooling, classify)`,
and the recipe writes `convert: classify` down explicitly so a default-table change cannot
quietly turn this into a different pooling task — the launch then fails loudly instead.

Launch-log sanity checks: vLLM prints `Resolved architecture: ...` and must **not** print
``Resolved `--convert auto` to `--convert embed` `` for these recipes.

**Chat-template coupling.** `reranker_chat_template` is published by
`mods/provide-qwen3-vl-rerank-template` before the serve line runs. Do not point it at the
checkpoint's `chat_template.jinja`: that template has no `query` / `document` role handling
and would silently score an empty pair. The mod resolves its output directory as
`${MOD_CACHEDIR:-${XDG_CACHE_HOME:-/cache/runtime}}`, and a mod cannot export variables into
the serve command — so if you set `MOD_CACHEDIR` to anything other than the runtime-cache
root you **must** override the recipe's path to match, or the mod publishes a template the
serve line never reads and vLLM falls back to the checkpoint's wrong one, quietly.
Relocating via `runtime_cache:` in sparkrun config keeps the two aligned automatically,
because that moves `XDG_CACHE_HOME` and leaves `MOD_CACHEDIR` unset. `TestModRuntimeRoot`
exercises this agreement.

**Readiness** — a pooling engine has no chat endpoint and the default chat-completion probe
can only time out, so both recipes set `readiness: inference: false` (port + `/health`
only). (F6)

**Deliberate omissions.** `--async-scheduling` is **not** set: vLLM disables it for pooling
runners itself ("The current implementation of asynchronous scheduling negatively impacts
performance of pooling models, so we disable by default"), so the flag is a no-op at best
and a hard failure under an explicitly-true value. `cpu_mask` pins the fast cluster only:
GB10 is big.LITTLE with the clusters interleaved (the 10 X925 cores @ 3.9 GHz are 5-9 and
15-19; the 10 A725 cores @ 2.8 GHz are 0-4 and 10-14). The reranker owns 15-19 and the
colocated encoder owns 5-9, so neither engine's tokenizer / chat-templating / image-decode /
API worker lands on a slow core or contends with the other. A score request is one forward
pass over a long prompt — prefill-bound, so the CPU-side work is exactly what would leave
the GPU idle between steps. Never use a mask that spans both clusters.

**No flag-map entries.** `hf_overrides`, `convert`, and `limit_mm_per_prompt` are not in
sparkrun's `VLLM_FLAG_MAP`, so they reach vLLM only through the `{...}` placeholders in the
serve line. `sparkrun run -o hf_overrides=...` warns that the key is unmapped while the
substitution still applies — do not "fix" the warning by deleting the placeholder. The
folded `limit_mm_per_prompt` value keeps its embedded quotes so the JSON survives as one
shell word.

**Explicit `dtype: bfloat16`.** This checkpoint's `config.json` declares bfloat16 at the top
level but float32 inside `text_config`, so the value says what we mean rather than depending
on which level vLLM's dtype resolution reads (§6 D3 in `QWEN3-EMBED-OPTIMIZATION-WORK.md`).

**`max_model_len: 8192`.** The trained/advertised context is 32k, but a reranker scores
(query, document) pairs and every pair pays the template + instruction overhead, so 8192
bounds the worst-case pair and keeps the profiled activation peak small. Raise with `-o` if
you score long documents.

**b12x block size.** `attention_backend: b12x` aborts at cache-config time unless
`--block-size` is 64 or 128 (`b12x requires --block-size in (64, 128), got 16`; vLLM's
default is 16). 128 is `_B12X_PREFERRED_PAGE_SIZE` in `vllm/v1/attention/backends/b12x.py`
at the pinned commit, and a score pair is one long prefill, so the larger page costs nothing
meaningful in partial-page waste. Same failure and same fix as the embed lane, which carries
the hardware receipt (VERIFIED 2026-09-19).

## 8B reranker (quality tier)

- **Not tagged `fast`, deliberately**: measured **28.76 units/s solo** against the 2B
  reranker's **119.29 units/s** on the same traffic shape (concurrency 8, 10 docs/query, 128
  tokens/document) — about 4× slower per scored document, which is what 4× the parameters
  costs on a prefill-bound cross-encoder. Tagging it `fast` would point people at the slower
  sibling. (F22)
- **Colocates with the 8B AWQ encoder** on one box: 65.03 GiB of 121.69 GiB at the shipped
  caps. The throughput penalty of running the pair together is recorded in the embed lane's
  README.
- Port **8015** sits outside the shipped 8010/8011/8012 plan so this never shadows the 2B
  reranker; the two are alternatives, not co-residents.

<!-- Links -->
[Qwen/Qwen3-VL-Reranker-2B]: https://huggingface.co/Qwen/Qwen3-VL-Reranker-2B
[Qwen/Qwen3-VL-Reranker-8B]: https://huggingface.co/Qwen/Qwen3-VL-Reranker-8B
