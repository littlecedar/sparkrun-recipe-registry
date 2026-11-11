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
4. **BF16 query** (see the stop verdict below). `srt/models/deepseek_v4.py:2294-2306` allocates an
   `float8_e4m3fn` `q_out` whenever `token_to_kv_pool.uniform_fp8`; the SM12x route rejects FP8
   queries (`_core.py:1304-1306`), so that buffer becomes `torch.bfloat16` on capability major 12
   and the two `q.to(float8)` casts in the backend (`:335`, `:472`) are skipped there. SM100/103
   keeps both casts.
5. **528 B `fp8_dsv41_inline` KV ABI** (see the stop verdict below). The uniform-FP8 pool rows go
   from 512 B to 528 B on SM12x: the same 512 e4m3 data bytes plus each token's 16 UE8M0 group-32
   scale bytes, written once as the constant `0x7F` (unit scale) at allocation. Touches the pool
   (`get_bytes_per_token`, `create_buffer`, `kv_cache_total_dim`, `bytes_per_page_padded`,
   `set_key_buffer_fused`), the uniform SWA store (`kv_norm_rope_store.py` row pitch, now a
   `row_bytes` launch parameter), the backend views (`:250-260` → `uint8` `(pages, 1, page, 528)`)
   and an explicit `kv_cache_format=` on both calls. The fused c1/c2 compressor store is compiled
   for 512 B rows, so on SM12x it is bypassed to the torch path that ends in the pool's own
   `set_key_buffer_fused`; the packed FlashMLA SWA store (`set_swa_key_buffer_radix_fused`) asserts
   rather than write 512 B rows at the new pitch.

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

Rebuild `:0.2.1`'s Dockerfile with the FlashInfer line moved to 0.7.3 + the `sm121a` provider
wheel (the base is `~/builds/deepgemm-sm121/ctx/Dockerfile.sm121` per the lane README). **`.35` is
free for builds** (2026-11-10). The pip-overlay alternative exists but is not preferred: the two
public wheels are `flashinfer_python-0.7.3-py3-none-any.whl` (79.8 MB, sha256 `548a3ea1…ae40`)
and `flashinfer_jit_cache_sm121a-0.7.3+cu130` aarch64 (234 MB, sha256 `e5059124…b01ed`), and it
fixes none of deltas 2–3, so it buys a boot that dies in the same place with a different
traceback.

**Carry cost, once per digest (VERIFIED 2026-11-10).** The built image
`dsv41-sm121-dg:0.2.1-fi073` (`sha256:7752ccd687be…`, 35.1 GB) exists only on `.35`, where it was
built. A quartet boot needs it on `.31`–`.34` too: `docker save … | ssh red@<node> docker load`
per rank, ~140 GB over the fabric per experiment, once per digest. A receipt must record the carry
and a per-rank `docker image inspect -f '{{.Id}}'` match, so a later session does not silently boot
a stale image on three ranks. (Stale-image boots are invisible in the logs: the ranks disagree on
kernel ABI, not on the tag.)

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

### Stop verdict (2026-11-10, `arm5-port`): the three deltas are not sufficient

Read end-to-end, the 0.7.x SM12x route rejects `:0.2.1`'s KV cache and query **before any kernel
runs**, so a three-delta image dies at the first decode step with a `ValueError`, not a silent
wrong-logits token. The three deltas stay necessary; two more are not covered by them. Sources
below are `flashinfer_python-0.7.3` (PyPI wheel sha256
`548a3ea1f9057025ace0a21b298824f8de049eb4b6c5c458f763309509e2ae40`), byte-identical to tag
`v0.7.3` for every file cited (`_core.py` `da3ed283…`, `_sparse_mla_sm120/_api.py` `c2c95f6e…`,
`_policy.py` `c4c95e27…`).

1. **BF16 query (delta 4).** `backend="sparse"` (`_core.py:2413-2416`) dispatches to
   `_trtllm_batch_decode_sparse_mla_dsv4_sm120` (`:1262`), which begins
   `if query.dtype != torch.bfloat16: raise ValueError("SM120 DSv4 sparse MLA only supports BF16
   query…")` (`:1304-1306`; contract also `_api.py:684`). The fork hands it FP8 at both sites
   (`deepseek_v4_trtllm_backend.py:335,472`), and q is *already* FP8 upstream:
   `srt/models/deepseek_v4.py:2294-2306` fills an `float8_e4m3fn` `q_out` whenever
   `token_to_kv_pool.uniform_fp8` (the trtllm pool flag). Delta 2 also has to turn that fused FP8
   Q-prep branch off for this route — an upstream edit, not a call-site edit.
2. **KV storage ABI (delta 5).** `:1384-1400` admits exactly three cache forms: packed `uint8`
   rows with last dim 584 (`"fp8"`) or 528 (`"fp8_dsv41"`/`"fp8_dsv41_inline"`), or a dense cache
   whose dtype equals the (BF16) query dtype at head dim 512. The fork's uniform-FP8 pool is
   `torch.float8_e4m3fn` rows of exactly **512 B** (`deepseek_v4_memory_pool.py:347-371`;
   `kv_norm_rope_store.py:46` hardcodes `CACHE + slot * 512`, unit-scale e4m3, no scale footer),
   so the first decode raises `swa_kv_cache dtype must match query dtype, got
   torch.float8_e4m3fn and torch.bfloat16` (`:1395-1396`). The note's earlier assumption of a
   `"fp8"`/584 B fork cache is wrong (corrected in *What is NOT verified here*): the fork is
   512 B/token and footerless, and a dense FP8 cache is not an accepted form either.
   The nearest legal form is `fp8_dsv41_inline` (`_policy.py:74-82`: 512 data bytes + 16 UE8M0
   group-32 scale bytes per token, 528 B/token), which would keep the fork's data bytes
   byte-identical — a constant `0x7f` (2^0) footer reproduces its unit scale. But that reaches the
   pool width/accounting (`get_bytes_per_token`, `kv_cache_total_dim`, `bytes_per_page_padded`,
   `create_buffer`), both uniform-pool writers (`kv_norm_rope_store.py:46,97` for the SWA store,
   `set_key_buffer_fused`'s `view(-1, 512)` `index_put` for the compressed store picked by
   `compressor_trtllm.py:116`), `get_swa_key_bytes_per_token` (`deepseek_v4_memory_pool.py:1882-1888`)
   — which `deepseek_v4_backend.py:3644` uses to choose the packed-format view the DeepGEMM sparse
   MQA-logits kernel is fed — the backend's own views (`deepseek_v4_trtllm_backend.py:250-260`) and
   an explicit `kv_cache_format=` on both calls. That is a KV-ABI change across the pool, two store
   paths and the other ported kernel's format detection.

Two corrections to the deltas as written above:

- Delta 2's real shape: the 128 SWA columns are already `-1`-padded by `build_causal_swa_page_indices*`
  (`dsv4_attn_metadata_kernels.py:470-580`), so the SWA segment is `sparse_indices[:, :128]` with
  `swa_topk_lens = trtllm_swa_lens` (constant 128); the compressed tail becomes
  `extra_sparse_indices = table[:, 128:]` with `extra_sparse_topk_lens = trtllm_c4_lens - 128`
  (0.7.x counts the compressed segment only, no combined-length offset on this route).
- Delta 3: neither call site passes `multi_ctas_kv_counter_buffer=`; the WAR is the monkeypatch of
  `_fi_core._get_trtllm_gen_multi_ctas_kv_counter_buffer` at `deepseek_v4_trtllm_backend.py:102-118`,
  an `AttributeError` at backend construction on 0.7.3. The SM12x route needs no counter buffer, so
  drop the install (guarded no-op), do not rename it.
- Rung 2 as written probes `dsv3_2` (`d_qk=576`, 656 B/token) — the wrong family. This route's
  envelope is `supported_sparse_mla_sm120_configs()["dsv4_1"]` (`_policy.py:146`: 512 query,
  528 B/token, `_DECODE_DSV4_1_TOPK=512`); `dsv3_2` only proves the kernel family loads.

`dsv41-sm121-dg:0.2.1` + FlashInfer 0.7.3 + the three deltas is **not a bootable arm**. A viable
Port A is a five-delta port (4 and 5 above plus the three) and needs a host to measure; nothing was
built and no image tag was created for it.

### Implementation status (2026-11-10, `arm5-port`)

All five deltas are now implemented in `recipes/ds4/patch_dsv41_fi073.py` against the extracted
`:0.2.1` tree, every anchor asserted exactly once and a final post-condition set that fails the
build instead of shipping a half-patched image: no `backend="trtllm-gen"` survives, both call sites
carry `backend="auto"` and `kv_cache_format`, both query paths assert BF16 on SM12x, the pool
carries `_SM12X_ROW_BYTES = 528` / `_SM12X_SCALE_BYTE = 0x7F`, the kernel takes a `row_bytes`
parameter, and all four fused-compressor branches are gated. The five patched files pass
`py_compile`; SM100/103 semantics are unchanged because every branch is behind
`is_sm120_supported()`.

Evidence status of the two new deltas' *contract* (read from the 0.7.3 wheel, not measured):

- VERIFIED — the SM120 route requires a BF16 query (`_core.py:1304-1306`) and packed `uint8`
  caches at 528 B/token for `fp8_dsv41_inline`, on both the SWA and compressed pools
  (`_core.py:1347-1350`, `:1384-1400`, `:1462-1466`); `"fp8_dsv41_inline"` requires
  `backend="sparse"` and selects the `ue8m0_g32_inline` model type (`:1162-1196`, `:1503-1509`).
- VERIFIED — inline records are rows at a uniform pitch that is a 16-byte multiple
  (528 = 16 x 33), with a page stride of whole rows; `sparse_indices`/`extra_sparse_indices` then
  address row `page * (page_stride // row_pitch) + slot`, i.e. the flat slot id when pages carry no
  padding (`_core.py:2183-2192`). The fork's compressed tail is already flat physical compressed
  slots (`phys_page * compressed_page_size + offset` from `topk_transform_paged`), so the page-id
  worry from the earlier plan does not apply to this format. Still a measurement point, not an
  assumption to skip: the first decode's tail indices are compared against the table values.
- LIKELY — the UE8M0 group-32 footer for a unit-scale store is the constant `0x7F` (2^0). Unmeasured;
  the first boot's canary answer comparison is what would catch it.
- SPECULATIVE — numerics: BF16 query (no FP8 Q quantization) and the compressor's fused → torch
  store switch change the rounding path, so this arm is not bit-identical to arm-3-control even at
  greedy settings. It must be judged by the canary answer cell, as the falsifier section says.

Built 2026-11-10 on `.35` once the quartet released it: `dsv41-sm121-dg:0.2.1-fi073` is now
`sha256:1d47404119c18e20549ba5f3ad81fbf01d80e63e5f152361adf9f3f4811e5ae6` (35,143,615,166 B),
superseding the three-delta `7752ccd68…`. The build's own gates passed (patch applied to all five
files, `py_compile`, backend import). Booted once as a quartet (2026-11-11, `.31`/`.32`/`.33`/`.35`):
the engine selects the ported route and **no ABI rejection or patch assert appears**, so deltas 4 and
5 pass the engine's checks — but the boot then sits in `FlashInfer autotune`'s dummy forward for ~28
min and was stopped, so the canary answer, the battery and every trough are unmeasured and `0x7F`
stays LIKELY. A second boot with `SGLANG_FLASHINFER_AUTOTUNE_CACHE=0` completed the autotune in
~10 min and then aborted on a TP `all_reduce` (600 s timeout, `SeqNum=2`, `NumelIn=2`) inside the
autotune's dummy forward, in the adapter's lazy `replicated_split._build` — so the blocker is a
rank-asymmetric collective in the adapter, not the tactic search and not this port's ABI. A third boot
disabled the autotuner outright (`--disable-flashinfer-autotune`, a real ServerArgs field:
`flashinfer_autotune.py:59-63` gates on it) and reached CUDA-graph capture, where the SM120 sparse
decode kernel refused the captured shape: `num_tokens=96 … (num_tokens <= 64)` with
`model_type=dsv4_1_inline` named correctly — a row-count envelope (16 bs x 6 DSpark tokens), not the
528-byte ABI. Receipts
`head:~/benchmarks/tp4-20261110b/arm5-fi073-canary/` and `…/arm5-fi073-bootC/`; both are written up in
`recipes/ds4/README.md` (arm-5 section).

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
- ~~Whether 0.7.3's `sparse` route accepts the fleet's ds4.1 `kv_cache_format`.~~ **Answered
  2026-11-10 (Port A stop verdict): it does not.** The fork's uniform pool is 512 B/token, footerless
  FP8 — not `"fp8"`/584 B as assumed here — and the route accepts only packed `uint8` 528/584 rows
  or a dense BF16 cache at head dim 512.
- ERNIE's real per-rank q-head count at TP=4 and the exact `window` the backend is constructed
  with (16 assumed from 64 heads / TP=4; `window` passed by `ernie55.py`, not read).
