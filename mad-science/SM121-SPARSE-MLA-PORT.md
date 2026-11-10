# SM121 sparse-MLA port plan (desk audit 2026-11-10)

Two arms are blocked on engine wiring rather than on a missing kernel, and both verdicts were
corrected in the lane READMEs on 2026-11-10 (`recipes/ds4/README.md` arm-5 paragraph,
`recipes/explore/README.md` ERNIE "decode-graph capture" section). This note is the executable
form of those corrections: what to change, what the change must be accepted against, and the
falsifier that catches the failure mode both ports can produce — **silent wrong logits.**

Evidence vocabulary is `mad-science/AGENTS.md`'s: VERIFIED / LIKELY / SPECULATIVE.

## The one fact both ports rest on (VERIFIED, measured 2026-11-10)

FlashInfer ships an SM121 sparse-MLA decode kernel; FlashMLA does not and cannot cheaply.

- FlashMLA HEAD `395cb3af` (2026-10-27) builds `CUDA_ARCHS = ["sm_100a", "sm_103a"]`
  (`setup.py:29`); the shipped wheel's cubins are `sm_90a/100a/103a/107a`; the runtime gate is
  `is_sm100f() { return major == 10; }` (`csrc_legacy/api/common.h:94-96` at
  `sgl-project/FlashMLA@46b6727a`, raise at `csrc_legacy/api/sparse_decode.cpp:386`).
- Opening that gate does not make the kernel run: the SM100 decode instantiation asserts
  `sizeof(SharedMemoryPlan) <= 227*1024` and calls
  `cudaFuncSetAttribute(…MaxDynamicSharedMemorySize, smem_size)`
  (`csrc/kernels/sm100/decode/sparse/head64/kernel.cuh:892-894` at `ba89a3466`), while GB10's
  opt-in dynamic smem measures **101 376 B** (`shared_memory_per_block_optin`, probe on `.30`).
  Upstream's own SM120 report hit this exact wall (`FlashMLA#124`, comment 2026-10-01).
- FlashInfer 0.7.3 `mla/_sparse_mla_sm120/_api.py:648` is
  `@supported_compute_capability([120, 121])`, takes `attn_sink`, and its `dsv3_2` envelope
  (`_policy.py:134`: `d_qk=576`, 656 B/token) accepts ERNIE's served shape —
  `supports_decode(num_heads=16, topk=2048, page_block_size=64) == True` (GPU-less probe,
  2026-11-10). The cubin ships as
  `flashinfer_jit_cache_sm121a-0.7.3+cu130/…/sparse_mla_sm120/sparse_mla_sm120.so`.

Consequence: neither arm needs new CUDA. Both need the engine to call the kernel it already has.

## Port A — `ds4-arm5-flashinfer-073-port`

Target: DeepSeek-V4.1 TRT-LLM sparse MLA (`--dsv4-attn-backend trtllm`) on GB10.

### Deltas (VERIFIED against `:0.2.1`, image `sha256:85c1ffc3…`)

1. `srt/layers/attention/deepseek_v4_trtllm_backend.py:366,506` hardcode
   `backend="trtllm-gen",`. `trtllm-gen` is SM100/103-only in **every** release through
   `v0.7.4rc2` (`flashinfer/mla/_core.py:1241-1244`; `:1062` at `v0.6.18` is the recorded error
   verbatim). SM12x has a *different* backend: `is_sm120_family = cc in ((12, 0), (12, 1))`,
   `"auto"` → `"sparse"` (`_core.py:1226-1255`, present since `v0.7.0` at `:1341`).
2. The call shape is pre-0.7. The fork passes one `sparse_indices` / `sparse_topk_lens` pair plus
   `compressed_kv_cache=swa_kv_cache`; the 0.7.x SM12x route wants the pools split —
   `swa_kv_cache` + `swa_topk_lens`, compressed via `extra_sparse_indices` /
   `extra_sparse_topk_lens`, with `kv_cache_format` naming the storage form
   (`_core.py:1821-1903`). Both call sites (`:354`, `:493`) need re-plumbing, not a rename.
3. `_fi_core._get_trtllm_gen_multi_ctas_kv_counter_buffer` (monkeypatched at `:102`) is **gone**
   in 0.7.3. Both call sites already pass `multi_ctas_kv_counter_buffer=` (a 0.7.3 kwarg), so the
   fork's shared-buffer WAR becomes unnecessary — but the install path must be guarded, not left
   to raise `AttributeError` at the first decode.

### Build shape — this is the real cost

The port needs an image carrying **both** the knapcio adapter (`/opt/dsv41/boot.py` + adapter
`sitecustomize.py` + b12x) **and** FlashInfer ≥ 0.7.0 with the `sm121a` provider. No such image
exists locally (VERIFIED by dist-info in every candidate):

| image | FlashInfer | `/opt/dsv41` |
|:--|:--|:--|
| `dsv41-sm121-dg:0.2.1` (`85c1ffc3…`) | 0.6.18 | yes |
| `canary-roce-aff52fa5` (`3f448081…`) | 0.6.18 | yes |
| `canary-roce-20261022` (`b37e4c49…`) | 0.6.18 | yes |
| `c3-reconciled:103ad321` (`13f686b3…`) | 0.6.18 | yes |
| `pin-fabbe8615bb9` (`788c3654…`) | 0.6.18 | no |
| `lmsysorg/sglang:nightly-dev-cu13-20261110-4a5c6b8f` (`97de25b1…`) | 0.7.3 + `sm121a` | no |

Rebuild `.0.2.1`'s Dockerfile with the FlashInfer line moved to 0.7.3 + the `sm121a` provider
wheel (the base is `~/builds/deepgemm-sm121/ctx/Dockerfile.sm121` per the lane README). **`.35` is
free for builds** (2026-11-10). The pip-overlay alternative exists but is not preferred: the two
public wheels are `flashinfer_python-0.7.3-py3-none-any.whl` (79.8 MB, sha256 `548a3ea1…ae40`)
and `flashinfer_jit_cache_sm121a-0.7.3+cu130` aarch64 (234 MB, sha256 `e5059124…b01ed`), and it
fixes none of deltas 2–3, so it buys a boot that dies in the same place with a different
traceback.

### Acceptance ladder (each rung is a stop)

1. `python -c "import flashinfer; print(flashinfer.__version__)"` → `0.7.3` in the built image.
2. Arg layer admits the flag: `--dsv4-attn-backend trtllm` no longer refuses (the `:0.2.1` tree
   already widened `arg_groups/deepseek_v4_hook.py:58` to `is_sm100_supported() or major == 12`).
3. First decode step clean, and the launch log/backtrace names the **sparse** backend. Rung 3 is
   the one that distinguishes a real port from a silent fall through.
4. A C1/C2 cell on the quartet, same window and control as arm-3-control (`:0.2.1`, replay off).

### Falsifier for the silent-wrong-logits class

Do **not** accept a throughput cell. Take the same prompt the shipped production canary answers,
run it on this arm, and compare the **answer text** (greedy, temperature 0) — the canary is the
same checkpoint on the same hardware via `flashmla`, so a diverging answer on an exact-match
question is the null result. A backend that skipped the compressed segment, mis-ordered the SWA
indices, or read the wrong `kv_cache_format` still passes every gate and still produces tokens;
only the answer comparison catches it.

## Port B — `ernie-flashinfer-sparse-sink-port`

Target: ERNIE-5.5-Flash-Base TP=4, 6 MLA + 37 HCA layers, on the 2026-11-10 nightly.

### Why a flag cannot exist (VERIFIED)

`--dsa-*` is resolved first, then `Ernie5_5MlaAttnBackend.__init__` **assigns over it** after
`super().__init__()`: `self.dsa_prefill_impl = self.dsa_decode_impl = "flashmla_sparse"`
(`srt/layers/attention/ernie55_backend.py:83-85`). So `flashinfer_sparse_mla` is rejected by the
parent's GLM-only whitelist (`kernels/ops/attention/flash_mla_sm120.py:678-713`) *before* the pin,
and any other value is silently discarded *after* it. `config.json` has no `learnable_sink`; the
sink is `add_full_attention_sink_bias` + `learnable_sink_param` in the model class.

### Five sites

| # | site | change | class |
|:--|:--|:--|:--|
| 1 | `ernie55_backend.py:83-85` | select the impl on `major == 12` instead of hardcoding | mechanical |
| 2 | `dsa_backend.py:2815-2818` | sink gate raises for any impl but `flashmla_sparse` | mechanical |
| 3 | `flash_mla_sm120.py:678-713` | arch whitelist GLM-only → admit ERNIE on SM12x with fp8 KV | mechanical |
| 4 | `flash_mla_sm120.py:716-753`, `dsa_backend.py:3545-3572` | pass `sinks=` (float32 `(num_heads,)`) and the per-row active length | plumbing |
| 5 | new override | reproduce the `top-k + last window` append for the FlashInfer route | **semantics** |

### Site 5, spelled out

`Ernie5_5MlaAttnBackend._forward_flashmla_sparse:180-189` calls `append_window_to_topk(...)` to
merge the indexer's `index_topk` (2048) with the trailing `window` tokens, producing the page table
**and** a per-row `topk_length`. The inherited `_forward_flashinfer_sparse_mla` has no such step
and passes `seq_lens=metadata.dsa_cache_seqlens_int32` where the SM12x route wants the active
top-k length. So an impl switch alone scores everything except the last `window` tokens as absent
and emits tokens with no error. The port must carry: the appended table, the appended per-row
length, and the sink (FlashInfer's contract: a finite sink adds `attn_sink` denominator mass, LSE
`attn_sink * log2(e) * lse_scale`; `_sparse_mla_sm120/_api.py:745-748,1086-1088`). Whether that
float32 per-head scale is numerically the same sink ERNIE's model applies is **SPECULATIVE** until
measured.

### Acceptance

1. Boot past CUDA-graph capture and reach `Ready` (the 2026-11-10 boot died there).
2. **Quality cell, not throughput**: upstream's own e2e test is greedy GSM8K ≥ 0.93 on four B200s
   (`test/registered/e2e/models/test_ernie55_flash.py`). A wrong-logits port passes every gate and
   fails only here.

### Falsifier for the silent-wrong-logits class

ERNIE has no same-hardware known-good reference (no shipped canary, and every non-FlashMLA DSA
backend is also unavailable on SM121), so the answer comparison must be built from a property the
port can violate: put the answer **only** in the final `window` tokens (needle at distance 0 at a
context length above `index_topk`) and compare against the same prompt with the answer inside the
top-k prefix. A port that drops the window answers the first null and the second correctly; a
correct port answers both. Run it before the GSM8K cell — it is one request per shape.

## What is NOT verified here

- Whether SGLang's per-row `seq_lens` semantics on the SM12x sparse route match ERNIE's appended
  windows (dispatcher is authoritative; only a call settles it).
- Whether 0.7.3's `sparse` route accepts the fleet's ds4.1 `kv_cache_format` (`fp8_dsv41`/inline,
  528 B/token, vs the fork's implicit `"fp8"`, 584 B/token).
- ERNIE's real per-rank q-head count at TP=4 and the exact `window` the backend is constructed
  with (16 assumed from 64 heads / TP=4; `window` passed by `ernie55.py`, not read).
