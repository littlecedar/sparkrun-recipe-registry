# Mellum2.1-12B-A2.5B-Thinking — Explore-lane arm bring-up (built 2026-10-15, boot pending)

Per-arm record for [`recipes/explore/mellum2.1-12b-a2.5b-bf16-thinking-vllm.yaml`](../../recipes/explore/mellum2.1-12b-a2.5b-bf16-thinking-vllm.yaml).
Companion to [`EXPLORE-MODELS-RESEARCH.md`](EXPLORE-MODELS-RESEARCH.md) (the lane's ranked candidate
research) and to the lane's shipped set in [`recipes/explore/README.md`](../../recipes/explore/README.md).

## 1. Why this arm exists

**The owner added the `JetBrains/mellum21` collection to this lane directly on 2026-10-15**, so the arm
sits **above** the lane's ranked list: it was never scored against the lane's owner criterion ("accuracy
decides; smaller and faster preferred", 2026-10-13), has no §1 shortlist row and no ranking. Sources read
**2026-10-15** (all values below are read at the pinned revision, not from the card prose):

- collection <https://huggingface.co/collections/JetBrains/mellum21> — 2 members, positions 0/1:
  `JetBrains/Mellum2.1-12B-A2.5B-Thinking` (model) and `JetBrains/Mellum2.1-12B-A2.5B-Thinking-GGUF`
  (model); collection last updated 2026-10-08.
- card <https://huggingface.co/JetBrains/Mellum2.1-12B-A2.5B-Thinking>
- GGUF card <https://huggingface.co/JetBrains/Mellum2.1-12B-A2.5B-Thinking-GGUF>

Nothing in this arm has been booted, benchmarked or needle-probed — the entire "what the first boot must
prove" list in §6 is open. It carries no `recipes/README.md` index row until that boot receipt exists
(the lane's shipped rule: *shipped = bootable and usable*).

## 2. The checkpoint (read from the pinned revision's own files)

| field | value (source: `config.json` at the pin) |
|---|---|
| `architectures` / `model_type` | `MellumForCausalLM` / `mellum` |
| params | 12B total / 2.5B active MoE (64 routed experts, 8 per token) |
| layers | 28; `layer_types` = sliding every layer except 4/8/12/16/20/24/28 → **7 full-attention, 21 sliding** |
| `sliding_window` | 1,024 (3 of every 4 layers; `use_sliding_window: true`) |
| attention | 32 Q heads / 4 KV heads (GQA), `head_dim` 128, `attention_bias: false` |
| RoPE | **per-layer-type**: `full_attention` = `yarn`, `rope_theta` 500000, `factor` 16, `original_max_position_embeddings` 8192, `beta_fast` 32 / `beta_slow` 1, `attention_factor` 1.2772588722239782; `sliding_attention` = `default`, `rope_theta` 500000 |
| context | `max_position_embeddings` 131,072 (= 8,192 × 16) |
| width | `hidden_size` 2304, `intermediate_size` 7168, `moe_intermediate_size` 896, `norm_topk_prob: true` |
| vocab / dtype | 98,304 / `bfloat16`; `tie_word_embeddings: false`; `transformers_version` 5.8.1 |
| licence | Apache-2.0, **ungated** (`gated: false`) → no per-node `HF_TOKEN` prerequisite |

Weights: 5 shards, **24,301,065,318 B (24.30 GB / 22.4 GiB bf16)**; the repo also ships
`chat_template.jinja`, `tokenizer.json`, `special_tokens_map.json`, `tokenizer_config.json`,
`generation_config.json` and two card images — nothing the engine does not need, so no
`model_file_selection` narrowing is required (contrast `humanizer-12b-vllm`, whose snapshot carries
63.6 GB of GGUFs).

`generation_config.json` carries only `bos_token_id`/`eos_token_id` — **no sampling defaults to protect**,
so the recipe passes no `--generation-config` (the `humanizer` arm must, because its checkpoint ships
`top_k 64`).

### Chat template and reasoning behaviour (source: `chat_template.jinja` at the pin)

- Tool definitions are injected as `<tools>…</tools>` in a system turn and the model is told to emit
  `<tool_call>\n{"name": …, "arguments": …}\n</tool_call>`; tool results come back as a user turn wrapping
  `<tool_response>…</tool_response>`. That is the **hermes** wire format — hence
  `--enable-auto-tool-choice --tool-call-parser hermes` (the card's own recipe).
- The template keeps `reasoning_content` as a first-class assistant field and mirrors it into
  ` thinking` … ` response` when re-rendering history.
- **Thinking is ON by default**: with `add_generation_prompt` the template writes only
  `<|im_start|>assistant\n`; the empty ` thinking\n\n</think>\n\n` block is written **only when the caller
  passes `enable_thinking: false`**. So the recipe passes no `--default-chat-template-kwargs` — the
  opposite of the Laguna-XS arm, whose template defaults thinking OFF while the card claims it is on.

### Card claims (self-reported by JetBrains, *not* verified here)

LiveCodeBench v6 82.0 pass@1, HumanEval+ 91.5, MBPP+ 79.4, AIME 25/26 83.3, GSM-Plus 88.3,
SWE-bench Verified 47.0, Terminal-Bench 2.1 17.4, SWE-bench Pro 28.0, **BFCL v4 62.3**, WorkBench 44.6,
ToolHop 49.1, IFEval 90.6, GPQA Diamond 64.6, MMLU-Redux 87.8, XSTest 88.8, HarmBench 8.5 (lower better).
Card notes: non-agentic benchmarks greedy; agentic ones through one open-source harness (Pi v0.73.1) at
the model's default sampling, 114K context, ≤16K tokens per turn. Card sampling for chat:
**temperature 0.6, top_p 0.95, top_k 20, `max_tokens` up to 81,920** — the recipe sets no server-side
default; callers send it.

## 3. Architecture support in the pinned image (the reason this can ship without a mod)

vLLM **0.29.0** — the lane's digest-pinned `vllm/vllm-openai:v0.29.0` — registers `MellumForCausalLM`
(`vllm/model_executor/models/registry.py`, tag `v0.29.0`), implemented in
`vllm/model_executor/models/mellum.py` as a **Qwen3-MoE subclass**:

- `MellumModel(Qwen3MoeModel)` / `MellumForCausalLM(Qwen3MoeForCausalLM)` swap in `MellumDecoderLayer`.
- `MellumDecoderLayer.__init__` selects the attention type per layer from `config.layer_types[layer_idx]`
  (sliding → `per_layer_sliding_window = config.sliding_window`, full → `None`) and reads RoPE as
  **`config.rope_parameters[layer_type]`** — i.e. it expects exactly this checkpoint's per-layer-type
  rope shape. `mlp_layer_types[layer_idx] == "sparse"` → `Qwen3MoeSparseMoeBlock`.
- `vllm/reasoning/__init__.py` registers **`qwen3`** (`_REASONING_PARSERS_TO_REGISTER`); the tool-parser
  registry registers **`hermes`** (`vllm/tool_parsers/__init__.py`). There is **no** parser named
  `mellum` — the card's `qwen3` choice is the only one matching this template's ` thinking` … ` response`
  form.

The recipe's own comments hold only what an operator would otherwise get wrong (the
`executor_config: {entrypoint: ""}` requirement of the `vllm/vllm-openai` image, the `--served-model-name`
rebinding trap, and the fact that no `mellum` parser exists). Everything else in this document was moved
here from the build notes per the recipe-comment policy in the root `AGENTS.md`.

## 4. Decisions

1. **One node, TP=1.** 24.3 GB bf16 fits a ~121 GiB pool; the engine sizes 22.4 GiB of weights, and the
   arm's render (2026-10-15, `-n`) shows a 66.6 GiB budget at `gpu_memory_utilization: 0.55` against
   7.0 GiB of KV demand for the full 131,072 window by sparkrun's estimator — which assumes **every**
   layer caches the full window and therefore ignores the 3:1 sliding structure (21 of 28 layers cap at
   1,024 tokens). The true pool is whatever the engine prints. There is no TP=2 case in this lane
   (single-node arms are the lane default; 4 KV heads divide trivially into TP=1).
2. **`gpu_memory_utilization: 0.55`, deliberately below the 0.85 ceiling** — the weights are ~22.4 GiB of
   ~121 GiB and the context is cheap, so the arm keeps ~55 GiB of node headroom for co-tenants. This is
   the same reasoning as `poolside-laguna-xs-2.1-nvfp4-dflash-vllm` (0.55) and is a *headroom* choice,
   not a memory-pressure one. It is unmeasured: if concurrency later matters, util is the knob.
3. **vLLM, not SGLang.** §3 is the whole argument: the arch is in-tree at the lane's pinned tag and the
   code path matches this config's own rope/layer-type shape, the card ships a vLLM recipe, and no mod is
   needed. SGLang was not evaluated for this checkpoint; the lane's SGLang arms that needed a
   vendor/dev image were archs SGLang had only just landed.
4. **The GGUF / llama.cpp route is deliberately NOT shipped** — see §5.
5. **No speculative decoding.** The card names the MTP head "coming soon" (as of the 2026-10-15 read);
   nothing is published to draft with, so the arm ships draft-less.

## 5. The GGUF route (recorded, not shipped)

The sibling repo `JetBrains/Mellum2.1-12B-A2.5B-Thinking-GGUF` **exists** (so the main card's "GGUF …
coming soon" is stale): revision `20b439426f1e997ba575eaccaf4856ac0f76f5d5`, last commit 2026-10-07,
Apache-2.0, one file per quant, with the card's own KLD / top-token-agreement table against BF16 logits
(Wikitext-2, `n_ctx=512`):

| file | quant | bytes | KLD ↓ | top-token ↑ |
|---|---|---|---|---|
| `Mellum2.1-12B-A2.5B-Thinking-BF16.gguf` | BF16 | 24,311,970,080 | — | — |
| `Mellum2.1-12B-A2.5B-Thinking-Q8_0.gguf` | Q8_0 | 12,925,417,760 | 0.008 | 96.1% |
| `Mellum2.1-12B-A2.5B-Thinking-Q6_K.gguf` | Q6_K | 10,879,834,400 | 0.020 | 93.9% |
| `Mellum2.1-12B-A2.5B-Thinking-Q4_K_M.gguf` | **Q4_K_M** (card-recommended) | 8,071,295,264 | 0.075 | 88.0% |
| `Mellum2.1-12B-A2.5B-Thinking-MXFP4_MOE.gguf` | MXFP4_MOE (smallest) | 7,029,537,056 | 0.115 | 85.6% |

The GGUF card's own invocation is `llama-server -hf …:Q4_K_M --ctx-size 131072 --temp 0.6 --top-p 0.95
--top-k 20` (OpenAI-compatible API on port 8080; direct file form `llama-cli -m <file>`).

**Decision: do not ship it in this window.** Reasons, in order:

1. **The registry has no llama.cpp arm to copy.** sparkrun does ship the runtime
   (`sparkrun/runtimes/llama_cpp.py`, `runtime_name = "llama-cpp"`, default image prefix
   `scitrera/dgx-spark-llama-cpp`, `llama-server -m <gguf>` command form), but **no recipe under
   `recipes/` uses it** (33 files; every shipped arm is `runtime: vllm` or `runtime: sglang`) — so a
   Mellum GGUF arm would be the registry's *first* llama.cpp contract:
   image choice from two floating `:latest` first-party tags with no pin precedent here, the
   ctx/parallel/flash-attn flag set, and template/reasoning plumbing (`--jinja` for this checkpoint's
   `chat_template.jinja`, plus `--reasoning-format` vs the lane's `--reasoning-parser qwen3` habit)
   would all be invented in this arm with nothing to diff against.
2. **It adds no datapoint the vLLM arm cannot give.** The lane's brief is accuracy on one node, and the
   vLLM arm is the card's own recipe at the unquantized checkpoint. A second, unverified route doubles
   what the next window must boot.
3. **MXFP4_MOE is interesting, not measured.** A native-FP4 MoE GGUF on GB10 is exactly the kind of arm
   this registry *should* eventually carry (it is 7.0 GB, i.e. ~3.5× smaller than the bf16 arm), but
   "smaller and plausible" is not a receipt, and the card's own KLD 0.115 / 85.6% agreement is the
   strongest number available for it — self-reported, against BF16 logits on `n_ctx=512`.

If a later window builds it, the cheap path is: pin the GGUF revision above, pick one quant (Q4_K_M for
the card's recommendation, MXFP4_MOE for the size/FP4 experiment), and treat the *first* llama.cpp arm as
its own bring-up (image pin + template + reasoning-format questions) rather than as a variation of this
one.

## 6. What the first boot must prove (open questions, all of them)

1. **It loads.** The arch is in-tree at the pinned tag (§3) but this checkpoint has never been booted
   here: confirm the engine starts under the digest-pinned image with the pinned snapshot, and that
   `GET /v1/models` returns `JetBrains/Mellum2.1-12B-A2.5B-Thinking` (the served-id trap: `-n` prints the
   repo id, a real launch rebinds `{model}` — this recipe renders `--served-model-name` from a literal).
2. **The reasoning split matches the template.** The template does **not** pre-write ` thinking` into the
   generation prompt — the *model* emits it. If `--reasoning-parser qwen3` does not recognise this form,
   `reasoning_content` stays empty and the chain of thought lands inline in `content` (the
   Kolibri-class symptom). Deliberately not assumed: vLLM's parser is a text-state machine, and this is a
   different template than Qwen3's.
3. **The tool round trip.** `hermes` parsing the template's `<tool_call>` JSON, and the model's
   `<tool_response>` user-turn format surviving a multi-step exchange through vLLM.
4. **The granted KV / context.** Read `GPU KV cache size` from the serve log — sparkrun's render estimate
   (7.0 GiB KV demand at 131,072) assumes all 28 layers cache the full window and is **not** the engine's
   number.
5. **Long-context correctness, not just admission.** 131,072 is announced with YaRN factor 16 over 8,192
   on the 7 full-attention layers and a 1,024 window on the other 21: a needle probe is required before
   any context claim (precedent: `poolside-laguna-xs-2.1` is *pool-verified* only, with a rope warning
   still unexplained).
6. **Quality.** The house battery plus a BFCL datapoint against the card's self-reported 62.3 (v4
   macro-average) — the same battery the lane's other arms took, so the numbers are comparable.

Operational notes for whoever runs it: no mods and no `@littlecedar/...` mod refs, so **no registry-clone
refresh is needed**; launch from the recipe's real path on the head with `--transfer-mode local` as usual.

## 7. Build record (2026-10-15)

- Recipe written: `recipes/explore/mellum2.1-12b-a2.5b-bf16-thinking-vllm.yaml`.
- **Revision pin resolved** as `92ddae9fc7665e9f801d141d2e5a6b2caf2460c4` — `hf models info
  JetBrains/Mellum2.1-12B-A2.5B-Thinking --format json` → `sha`, cross-checked against
  `GET /api/models/JetBrains/Mellum2.1-12B-A2.5B-Thinking/refs` (single branch `main` at the same commit;
  no tags); `lastModified` 2026-10-07T23:08:12Z. Pinned in the three places the repo's guard requires
  (top-level `model_revision:`, the hardcoded snapshot path, `--revision=`).
- `sparkrun recipe validate` → **0 warnings, 1 suggestion** (`restated-managed-path`, identical to the
  lane's other hardcoded-snapshot vLLM arms; the launch validator requires the path + `--revision=` pair,
  so the suggestion is not cleared).
- `sparkrun run … -H <free node> -n` renders: weights 22.4 GiB, `gpu_memory_utilization` 0.55 → 66.6 GiB
  budget, KV space 44.2 GiB / ~827,593 tokens under the all-layers-full estimator, fit `UNVERIFIED`.
- **No boot, no benchmark, no receipt.**

## Boot receipt (2026-10-15, `.35`)

First boot, and the six open questions it was meant to answer resolved in one pass: the engine loads
the checkpoint natively (no mod), the served id is the HF repo id with `max_model_len` 131,072, and
thinking defaults ON as the template said. Decode ladder @ d0 pp2048 tg128 n=5: **C1 42.3 ± 0.1 /
C2 67.2 ± 0.6 / C5 99.9 ± 1.7 / C10 135.6 ± 1.1 t/s**; house battery **36/37** (easy 18/19 — the miss
is `needle-1`; hard 18/18). Receipt `~/benchmarks/mellum-20261015/` (`launch.log`, `models.json`,
`perf-ladder.{yaml,json,csv}`, `house.json`, `summary.json`). Known gap: the container was already
stopped when the log capture ran, so no `serve.log`/`grants.txt` — the engine's KV-cache line is the
one datum a next boot should capture first.
