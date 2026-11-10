# `ernie55-flashinfer-sparse-sglang`

Move ERNIE 5.5 Flash's six MLA layers onto FlashInfer's SM120/121 sparse-MLA
decode kernel, keeping the `top-k + last window` page set and the learnable
sink, and the logits those two decide.

Why a shim and not a flag: `Ernie5_5MlaAttnBackend.__init__` assigns
`self.dsa_prefill_impl = self.dsa_decode_impl = "flashmla_sparse"` **after**
`super().__init__()` (`srt/layers/attention/ernie55_backend.py:83-85`), and the
model override refuses any other `--dsa-prefill-backend`/
`--dsa-decode-backend` value at launch
(`srt/arg_groups/model_overrides/ernie55.py`, `_validate_features`). FlashMLA
cannot serve this board: `is_sm100f()` gates on `major == 10`
(`csrc_legacy/api/common.h:94-96` at FlashMLA@46b6727a, raise at
`csrc_legacy/api/sparse_decode.cpp:386`) and the SM100 decode kernel asserts a
227 KiB shared-memory plan against GB10's 101,376 B opt-in. The 2026-11-10 boot
died in decode CUDA-graph capture at `sparse_decode.cpp:386`.

Pinned engine: `lmsysorg/sglang:nightly-dev-cu13-20261110-4a5c6b8f` (upstream
main `4a5c6b8f632f1bb9ef1fb7724da9fda771dda6be`), FlashInfer 0.7.3 with the
`sm121a` provider.

## The five sites

| # | file | change |
|:--|:--|:--|
| 1 | `srt/layers/attention/ernie55_backend.py:83-85` | on `major == 12` with an fp8 latent pool, select `flashinfer_sparse_mla` instead of the hardcoded `flashmla_sparse`; SM100/103 stay upstream |
| 2 | `srt/layers/attention/dsa_backend.py:2415,2815` | the "sinks require flashmla_sparse" gate admits `flashinfer_sparse_mla`, whose route carries the same FlashMLA V4 sink |
| 3 | `kernels/ops/attention/flash_mla_sm120.py` (`_validate_flashinfer_sparse_mla_backend`) | admit `Ernie5_5_MoeForCausalLM` on SM12x + fp8. ERNIE switches impl *after* its `super().__init__()`, and this gate is what allocates the 384 MiB sparse workspace, so the allocation has to happen while the pin still reads `flashmla_sparse` |
| 4 | `kernels/ops/attention/flash_mla_sm120.py` (`flashinfer_sparse_mla_forward`) and the two call sites in `dsa_backend.py` | plumb the per-head sink into the dispatcher (`sinks`) |
| 5 | `srt/layers/attention/ernie55_backend.py` | override `_forward_flashinfer_sparse_mla` to build the `top-k + last window` page set and its per-row length before the call |

Everything is a text patch with `sparkrun:` markers. Any anchor that does not
match exactly once aborts the launch and writes nothing: a partial apply boots
into wrong logits rather than an error.

## Site 5, or why this port is not a silent-wrong-logits patch

The indexer cannot see the last `window` tokens. `Ernie5_5MlaAttnBackend`
feeds the indexer `_topk_lengths(seq_lens, window) = (seq_lens - window).clamp_min(0)`
(`ernie55_backend.py:72-74`, applied at `:127-146`), so positions inside the
trailing window are outside the indexer's candidate range by construction. They reach attention
only through `append_window_to_topk` (`ernie55_backend.py:180-189`), which
merges them into the page table and returns a per-row `topk_length`. An impl
switch that skips that call drops every one of those positions and still emits
tokens.

This shim keeps the call. The override runs the engine's own
`append_window_to_topk` with the same arguments `_forward_flashmla_sparse`
uses (`dsa_seqlens_expanded`, `real_page_table`, `window`, `metadata.page_size`,
`SPARSE_PREFILL_TOPK_ALIGNMENT`, `token_to_batch_idx`, `topk_indices_offset`),
then hands the appended table and the appended per-row count to
`flashinfer_sparse_mla_forward`. That function's `seq_lens` **is** the
per-token active length on this route: `_core.py` normalizes it to the sparse
top-k lengths and rejects `sparse_mla_top_k_lens` with "pass per-token active
top-k lengths via seq_lens instead". The top-k width is taken from
`indices.shape[1]`, i.e. the appended 2176 columns, so no row's window slots
are clamped off. The FlashMLA route and this one therefore consume the same
page set and the same count; only the kernel reading them moves. That is the
equivalence argument, and it is structural, not numerical: it holds because
both routes run the same engine function on the same inputs.

Two deliberate details. The override does not apply `_read_rows` masking
(dead DP rows keep their computed output instead of an empty candidate set);
the fp8 branch of `_forward_flashmla_sparse` -- the reference this route
replaces -- does not apply it either, and those rows' outputs are not read.
And the DSA indexer is not part of this port: the 2026-11-10 boot reached the
sparse decode call inside decode CUDA-graph capture, which runs the indexer
and the top-k metadata first in the same forward, so those kernels already
execute on GB10.

## The sink

`add_full_attention_sink_bias: true` in the checkpoint config, materialised as
`learnable_sink_param`, a float32 `(num_local_heads,)` parameter whose weights
come from `self_attn.core_attention.softmax_offset` (`ernie55.py:1171`). The
model does not apply it itself: `deepseek_common/attention_forward_methods/`
`forward_mla.py:845-846` passes it as `attn_sink` into the attention backend,
and the kernel adds it as a virtual logit. So parity is a kernel-contract
question:

- FlashMLA's V4 convention: `output *= sigmoid(lse - sink)`,
  `lse' = log(exp(lse) + exp(sink))`.
- FlashInfer's `_sparse_mla_sm120/_api.py:745-748` documents the identical
  convention, and its base-2 LSE contract adds `attn_sink * log2(e) * lse_scale`
  for a finite sink -- the natural-log virtual logit, converted once.

Same tensor, same shape, same convention. What is *not* proved here is float
equality of the two implementations; rung (iii) measures it.

## ERNIE's shape against the kernel envelope

From the pinned checkpoint's `config.json` (revision `028544b2…`):
`hybrid_mla_num_attention_heads: 64` (16 per rank at TP=4), `index_topk: 2048`,
`sliding_window: 128`, `hybrid_mla_kv_lora_rank: 512`,
`hybrid_mla_qk_rope_head_dim: 64`, absorbed value dim 512, so `d_qk = 576` and
the MLA pool is the 656 B/token packed DSA row
(`fp8_ds_mla_row_width(512, 64) = 512 + 4*4 + 128`). The appended width is
`ceil_align(2048 + 128, 128) = 2176`, which is also a multiple of 64, the
width FlashInfer's ordinary prefill requires.

`kv_scale_format` is `"arbitrary_fp32"`: ERNIE's pool writes `amax/448` fp32
tile scales (`kv_scale_ue8m0` is only set for Kimi-K3.1,
`mem_cache/kv_cache_configurator.py:2351`), and that is exactly what the
already-validated GLM DSA route passes at `d_qk = 576`. The scale-format
literal is part of `flashinfer_sparse_mla_forward`, so this shim inherits it
instead of choosing it.

GPU-less envelope check (`supported_sparse_mla_sm120_configs()`, pure Python
static tables): `glm_nsa` (identical object to `dsv3_2`, same kernel, ABI, and
constants) reports `d_qk 576`, `656 B/token`, decode up to 64 tokens, runtime
page size, up to 128 heads, top-k at least 1. `supports_decode(num_heads=h,
topk=2176, page_block_size=64)` is `True` for `h` in 8, 16, 32, 64, i.e. TP 8
through TP 1. Measured 2026-11-10 with `flashinfer-python==0.7.3` on a
GPU-less x86 host: `glm_nsa is dsv3_2` (one object in 0.7.3), `d_qk 576`,
`656 B/token`, `max_num_tokens 64`, `page_block_size 64` with runtime page
sizes, and `supports_decode` true at both topk 2048 and 2176 for all four head
counts. No head padding is needed -- unlike the FlashMLA route's fixed
64/128-head kernel, this one takes the rank's real head count.

## Acceptance ladder

Each rung is a stop. Rungs (i) and (ii) are passed by a wrong-logits port; only
(iii) and (iv) are about the answer.

1. **Import + envelope** (no GPU) -- this mod's `verify-…py`, run at every
   launch. Patched behaviour present, FlashInfer >= 0.7, envelope admits
   ERNIE's shape, `2176 % 64 == 0`.
2. **Boot** -- TP=4 on the quartet passes CUDA-graph capture and reaches
   `Ready`. The image prints its own resolved snapshot path on the load line;
   copy it into the receipt. Serving endpoint is `/v1/completions`: the
   checkpoint ships no chat template.
3. **Quality cell** -- greedy GSM8K, the checkpoint's own upstream gate
   (`test/registered/e2e/models/test_ernie55_flash.py`: four B200s,
   `accuracy >= 0.93`). A wrong-logits port passes (i) and (ii) and fails here.
   Exact invocation below.
4. **Window falsifier** -- a needle only in the final `window` tokens must be
   answered, and the control with the needle in the indexer's candidate range
   must also be answered. Run it before the GSM8K cell: two requests.
   Exact shapes below.

### What rung (i) prints, verbatim

The mod runs `verify-ernie55-flashinfer-sparse.py` at every launch and appends
to `/cache/runtime/modlogs/ernie55-flashinfer-sparse-sglang.log`. A passing
rung (i) ends with these lines, in this order (the capability line varies):

```text
patch markers ok: sglang.srt.layers.attention.ernie55_backend
patch markers ok: sglang.srt.layers.attention.dsa_backend
patch markers ok: sglang.kernels.ops.attention.flash_mla_sm120
patched behaviour ok: override bound, sink plumbed, workspace admitted
flashinfer 0.7.3
envelope ok: glm_nsa d_qk 576, 656 B/token, decode <= 64 tokens, topk 2176, page 64 (8hok, 16hok, 32hok, 64hok)
device: sm_121 NVIDIA GB10
rung (i) ok: import + envelope
```

Before those lines the same log carries the patch script's
`target: <module> -> <path>` and `patched: <path>` lines, or
`nothing to write: every site already carries its marker`; quote them, because
they name the installed files the patch actually touched on that image.

Anything else ends the launch. `envelope ok` with a `NO` entry, or a
`flashinfer` line below the floor, is a kernel-envelope refusal, not a model
result; paste the line into the receipt and stop. The `device:` line is
informational: the patch gates on `major == 12`, and a non-GB10 board changes
the record, not the route.

### Rung (iii): GSM8K, exactly

The lane instrument is chat-only (`run_benchmarks.py:108` posts
`/v1/chat/completions`, `temperature: 0`, `max_tokens` 2048), and this
checkpoint ships no chat template, so that instrument errors before it
measures. Two honest routes; the receipt names which one ran.

**Route A -- `/v1/completions` (comparable to the upstream gate).** Same data,
same sample, same scorer as the lane instrument, transported over completions:

- data `recipes/ds4/benchmarks/data/gsm8k_test.jsonl` (official test split),
  200 rows via `sample(rows, 200, 1234)` from `run_benchmarks.py`;
- prompt exactly `question + "\n\nShow your reasoning, then end with '#### <final number>'."`;
- POST `/v1/completions` with
  `{"model": "baidu/ERNIE-5.5-Flash-Base", "prompt": <prompt>, "temperature": 0, "max_tokens": 2048}`
  and read `choices[0].text`;
- score with `run_benchmarks.score_gsm8k(reply, gold)` (last number after the
  last `####`, compared numerically);
- sequential: one request at a time, 200 requests, 2048 tokens each, no
  parallel chunking. Record the `finish_reason` histogram and the
  `empty_replies` count, because "answered wrong" and "spent the budget before
  the last number" are different findings;
- gate: accuracy **>= 0.93**. Below it is a stop, not a tuning target.

**Route B -- stage a chat template first**, then run the lane command
unchanged (`tools/eval-suite.py --checks hard --hard-bench gsm8k --hard-limit
200 --hard-seed 1234`, which drives `run_benchmarks.py --bench gsm8k`). This
changes the prompt bytes relative to upstream's gate, so a Route B number is
not comparable to 0.93 without saying so.

### Rung (iv): the window falsifier, two requests

One prompt pair, `/v1/completions`, `temperature: 0`, `max_tokens: 32`,
`"model": "baidu/ERNIE-5.5-Flash-Base"`. Fixed needle text
`The vault code is QK-4173.` and a fixed question cue
`\nQuestion: What is the vault code? Reply with the code only.\nFinal answer:`
with only numbered filler lines between them, so the two prompts differ in one
thing: where the needle sits.

- **W (window).** Filler to about 4096 prompt tokens, then
  `[filler][needle][question cue]`. The needle lands roughly 25 tokens from
  the end, inside `window` (128), so the indexer cannot select it: its
  candidate range is `prompt_tokens - 128`. Answering the code here is only
  possible through the window append.
- **P (prefix control).** Filler such that the whole prompt is **at most 2048
  tokens**, with `[filler A][needle][filler B ~300 tokens][question cue]`.
  At that length the candidate count is `prompt_tokens - 128 < 2048`, so the
  indexer selects every candidate and the needle is guaranteed inside the
  top-k set (a structural control, not a lucky retrieval).
- Check both lengths against the server's own `usage.prompt_tokens`, not a
  local tokenizer estimate: W must report more than 2048 prompt tokens, P at
  most 2048.
- Pass: both replies contain `QK-4173`. The failure signature this falsifier
  exists for is W answering without the code while P answers it, which is a
  window that never reached the kernel. A different answer on both is a
  quality finding, not a window finding.
- Receipt: both prompt token counts and both replies verbatim.

Any divergence between the two falsifier answers is a backend verdict, not a
sampling artifact: same needle, same question, greedy decoding (at
`temperature: 0` the seed is inert).

## What this shim cannot prove

- Numerical equality of the sink across the two kernels -- measured at rung
  (iii).
- That SGLang's per-row `seq_lens` semantics on the SM12x sparse route match
  ERNIE's appended windows. The dispatcher is authoritative; only a call
  settles it (rung ii/iii). The structural argument above says the inputs match
  by construction; it does not say the kernel interprets them as the reference
  did.
- Throughput. This arm is not a performance claim until the quality gate
  passes. If the boot quotes any decode rate anyway, state the number of decode
  steps behind the median and take it from a long-answer request: a 3-step
  median is dominated by first-step overhead (the ds4 lane measured arm 3 at
  56.2 ms/step over 3 steps and 31.8 over 37).

## Boot discipline

The ranks are a shared quartet window. Take the window only when its owner has
released it: write the claim, keep `sparkrun-campaign.service` stopped for the
duration, launch with the real `HOME`, `--cluster WOPR --transfer-mode local`,
the recipe by file path, and the fleet's 6.0 GiB `MemAvailable` stop rule
untouched. The mod is fail-closed; a refused launch is a diagnostic, not a
recipe failure.
