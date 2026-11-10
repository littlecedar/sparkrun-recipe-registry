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
   must also be answered. Run it before the GSM8K cell: three requests.
   Exact shapes and the measured run below.

Measured 2026-11-10 on the quartet (Boot B): all four rungs passed. The
numbers, the prompt shapes and the miss list are below; the prompts, replies,
serve log and per-record JSON are the receipt's
(`head:~/benchmarks/tp4-20261110b/ernie-gate2/`).

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

The other half of rung (i) is the boot's own parameter block: the serve prints
seven usage lines, and the receipt quotes all seven verbatim. Four facts must
appear in them, or the boot is not this route however it answers: the ERNIE
backend (`ernie55`), `page_size=256` for the main pool, `kv_cache_dtype=fp8_e4m3`,
and `window_128`. Quote the lines rather than restating the facts: a value
transcribed from a recipe is not evidence that the engine used it.

Measured (Boot B): `Ready` about 1,230 s after launch, `/v1/models` answering
200 with `max_model_len` 131,072, the engine's own line
`Use ernie55 attention backend … page_size=256, kv_cache_dtype=fp8_e4m3`, the
pinned revision `028544b2`, and the seven `window_128` usage lines quoted in
the receipt. That is the configuration this port assumes, printed by the engine
rather than by the recipe.

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

**Measured 2026-11-10 (Boot B): 190/200 = 95.0 %**, 0-shot, seed 1234, mode
`completions`, `finish_reasons` `{'stop': 200}`, one empty reply. The eight
misses are one formatting difference (`120,000` against gold `120000`), six
genuine arithmetic or logic errors, and the empty reply. The card's 93.0 is
**8-shot**, so 95.0 at 0-shot is not a claim to beat it: the gate was `>= 0.93`
at 0-shot, and it passed.

Under 0.93 the cell is a stop and a backend finding; it is never re-seeded,
re-limited, or re-scored into a pass.

### Rung (iv): the window falsifier, measured

The structural fact the falsifier rests on is unchanged: the indexer's
candidate range stops `window` (128) positions before the end, so an answer
that sits in the final 128 is reachable only through `append_window_to_topk`.
`/v1/completions`, `temperature: 0`, `max_tokens: 32`,
`"model": "baidu/ERNIE-5.5-Flash-Base"`; every probe records
`usage.prompt_tokens`, so "inside the last 128" is arithmetic on the engine's
own count.

Measured 2026-11-10 (Boot B), QA-form prompts (`Question: … Reply with the code
only.`), code `ZX81-4321`:

| probe | prompt tokens | code distance from the end | reply |
|:--|--:|--:|:--|
| **T** tail-only | 7,827 | ~25 (inside the window) | `ZX81-4321` — correct |
| **N** negative (T's bytes, code removed) | 7,816 | — | no code |
| **C** control, candidate range | 4,005 | 400 | correct |
| **C** control, long context | 26,547 | 3,000 | correct |

T answering with N silent is what proves the window append reaches attention: a
port that dropped it could not have read a code 25 tokens from the end of a
7.8 k-token prompt. C answering at two distances shows the code is readable
when it is inside the candidate range, which is what makes T's answer about the
window rather than about whether the model can read a code at all.

**The earlier "PASS" was not this.** Boot A answered one code from the tail but
its control came back garbled (`4321-ZX81` for `ZX81-4321`) and there was no
negative control, so nothing distinguished reading from echoing.

**Prompt style decides this falsifier, not needle distance.** The same trio in
imperative form (`Reply only with the code.`) failed the control at 4,264 and
17,940 tokens — the reply echoed the instruction — while the QA form answered
at both distances. An imperative-form falsifier measures compliance with a
format request, not what the window delivered, so its result is not a window
verdict. The receipt must name the prompt form; Boot B used the QA form.

Receipt: all four probes' `prompt_tokens` and replies verbatim, plus the prompt
texts, in `head:~/benchmarks/tp4-20261110b/ernie-gate2/`.

## What this shim cannot prove

- Numerical equality of the sink across the two kernels -- measured at rung
  (iii).
- That SGLang's per-row `seq_lens` semantics on the SM12x sparse route match
  ERNIE's appended windows. The dispatcher is authoritative; only a call
  settles it (rung ii/iii). The structural argument above says the inputs match
  by construction; it does not say the kernel interprets them as the reference
  did.
- Throughput. This arm has one decode sample and it is not a number to quote:
  128 decode steps in 7.62 s = **16.80 tok/s**, `finish=length`, 31 prompt
  tokens, taken **while the accuracy cell was running on the same serve**. It
  says the route decodes; it says nothing about the window alone. Any rate
  quoted later must name its step count (a 3-step median is first-step
  dominated: the ds4 lane measured 56.2 ms/step over 3 steps and 31.8 over 37)
  and come from a long answer on an otherwise idle serve.

## Campaign wiring (`ARM_EXTRA_CLIENT`)

A campaign boot has no artefact contract for this arm unless the row carries a
client. The one client is the lane's own instrument,
`recipes/ds4/benchmarks/run_benchmarks.py`, over the `--completions` flag it is
gaining:

```text
ARM_EXTRA_CLIENT="python3 recipes/ds4/benchmarks/run_benchmarks.py --base-url http://$NODE:$PORT --model $SERVED --bench gsm8k --limit 200 --seed 1234 --completions --outdir $L/gsm8k"
ARM_EXTRA_TIMEOUT=7200
```

200 sequential 2048-token requests do not fit the hook's 1800 s default, hence
the timeout. The row owner pastes both into `mad-science/queue.json`; the
address is `$NODE:$PORT`, resolved at eval time, so the tracked row stays
address-free.

**Precondition (met 2026-11-10).** `--completions` landed on trunk as
`2435ff4` (`run_benchmarks: --completions measures a serve with no chat
template`), so the invocation above is coherent. Re-check on the head checkout
before the boot rather than trusting this line:

```text
python3 recipes/ds4/benchmarks/run_benchmarks.py --help | grep -q -- --completions
```

This recipe stays unmodified on purpose: the hook lives in the queue row, and
that file belongs to another session. An `ARM_EXTRA_CLIENT` naming a flag the
committed tree does not parse is inert, and inert is worse than absent because
the row then looks like it has an artefact contract.

**A campaign lease cannot measure this arm until the row carries the client.**
Without `ARM_EXTRA_CLIENT`, `tools/run-arm.sh` finishes the boot with a
ladder-only receipt and records `rc=4 never ready — no marker and no
machine-readable artefact`, which the campaign treats as a retry and re-boots.
The client above is what turns a boot into evidence; wiring it is the register
owner's edit, not the recipe's.

## Boot discipline

The ranks are a shared quartet window. Take the window only when its owner has
released it: write the claim, keep `sparkrun-campaign.service` stopped for the
duration, launch with the real `HOME`, `--cluster WOPR --transfer-mode local`,
the recipe by file path, and the fleet's 6.0 GiB `MemAvailable` stop rule
untouched. The mod is fail-closed; a refused launch is a diagnostic, not a
recipe failure.
