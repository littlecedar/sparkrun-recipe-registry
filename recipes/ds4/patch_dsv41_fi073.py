#!/usr/bin/env python3
"""FlashInfer 0.7.x SM121 deltas for the DSV4 trtllm sparse-MLA backend.

Applied inside ``dsv41-sm121-dg:0.2.1`` after the 0.7.3 wheel overlay. The
deltas are the ones named in ``mad-science/SM121-SPARSE-MLA-PORT.md`` section
Port A and its stop verdict:

* ``backend="trtllm-gen"`` -> ``"auto"``: trtllm-gen is SM100/103-only in every
  release through ``v0.7.4rc2``; ``"auto"`` resolves to the packed SM120
  ``"sparse"`` backend on SM12x (``flashinfer/mla/_core.py:1226-1255``).
* the combined ``sparse_indices``/``sparse_topk_lens`` table becomes the 0.7.x
  split segments: SWA table + ``swa_topk_lens``, compressed tail as
  ``extra_sparse_indices`` + ``extra_sparse_topk_lens`` counted without the
  fixed 128 SWA slots.
* the persistent trtllm counter-buffer WAR is dropped when FlashInfer no longer
  exposes ``_get_trtllm_gen_multi_ctas_kv_counter_buffer`` (removed in 0.7.x;
  the SM12x route takes no counter buffer).
* the DSpark draft block's table (SWA_WINDOW + block, 64-aligned to 192) is
  passed whole as the SWA segment: every entry indexes SWA storage
  (``compress_ratio == 0``) and its per-row count is a total, not a
  compressed count, so the 0.7.x split call adds no tail for it.
* BF16 query (SM12x only): the route rejects FP8 queries
  (``_core.py:1304-1306``), so the uniform-FP8 pool's contiguous FP8 Q buffer
  and both ``q.to(float8)`` casts are gated off on capability major 12. The
  DSpark draft model allocates its own Q buffer in the draft attention forward
  (``deepseek_v4_dspark.py``), so that site is gated too.
* 528-byte inline-scale KV (SM12x only): ``_core.py:1384-1400`` accepts packed
  ``uint8`` rows at 528 bytes per token (512 all-FP8 values + 16 UE8M0
  group-32 scale bytes) instead of the fork's 512-byte footerless pool. The
  store is unit-scale, so every token's footer is the constant 2^0 code and is
  written once at allocation. The fused c1/c2 compressor store is compiled for
  the 512-byte rows, so it is bypassed to the torch path that ends in the
  pool's ``set_key_buffer_fused``.
* the prefill split hands the route row-packed index tables
  (``.contiguous()``): 0.7.3 builds call metadata from the tensors' own strides
  and refuses a column slice of the combined table as "no matching decode
  instantiation" (``_sparse_mla_sm120/_prepared.py:175``). Measured on the GB10
  at 193 and 16,384 rows: packed admitted and executed, sliced refused -- on
  both the functional call and the wrapper's ``run``. Decode keeps its sliced
  tables up to the 64-row envelope.
* the target-verify decode batch (16 requests x 6 draft tokens = 96 rows)
  re-runs that route from ``_forward_trtllm_decode``: its split tables are
  packed ``.contiguous()`` only when ``bs > 64``, above the decode envelope.
  The routed prefill variant consumes the same per-token indices and lengths
  and drops ``seq_lens``/``cum_seq_lens_q`` (``mla/_core.py:2413``), so a
  verify batch keeps its per-token visibility; the served <=64-row decode is
  byte-identical to before.

SM100/103 keeps the FP8 Q path and the 512-byte pool byte-for-byte: every
change below is gated on ``is_sm120_supported()`` (capability major 12).
Every anchor must match exactly once, so a base-tree move fails the build
instead of shipping a half-patched image.
"""
import os
import pathlib

ROOT = pathlib.Path(
    os.getenv("DSV41_FI073_TREE", "/sgl-workspace/sglang/python/sglang/srt")
)
PKG = ROOT.parent
BACKEND = ROOT / "layers/attention/deepseek_v4_trtllm_backend.py"
BACKEND_BASE = ROOT / "layers/attention/deepseek_v4_backend.py"
MODEL = ROOT / "models/deepseek_v4.py"
DSPARK = ROOT / "models/deepseek_v4_dspark.py"
POOL = ROOT / "mem_cache/deepseek_v4_memory_pool.py"
STORE = PKG / "kernels/ops/attention/dsv4/kv_norm_rope_store.py"


def patch(path, old, new):
    p = pathlib.Path(path)
    s = p.read_text()
    assert s.count(old) == 1, (str(path), s.count(old), old[:80])
    p.write_text(s.replace(old, new, 1))


# --- delta 3: counter-buffer WAR --------------------------------------------
SEMAPHORE_OLD = '    _orig = _fi_core._get_trtllm_gen_multi_ctas_kv_counter_buffer\n'
SEMAPHORE_NEW = (
    '    if not hasattr(_fi_core, "_get_trtllm_gen_multi_ctas_kv_counter_buffer"):\n'
    '        # FlashInfer >= 0.7 removed the private request-count sizing helper;\n'
    '        # the SM12x sparse route takes no counter buffer, so the WAR is moot.\n'
    '        return\n'
    '    _orig = _fi_core._get_trtllm_gen_multi_ctas_kv_counter_buffer\n'
)

# --- DSpark draft table (combined window+block, one segment) -----------------
DSPARK_OLD = (
    '        if swa_width > SWA_WINDOW:\n'
    '            # DSpark attends noncausally to its context window plus the whole\n'
    '            # draft block. The tail still indexes SWA storage, not compressed\n'
    '            # KV. Use the complete block\'s visible length rather than each\n'
    '            # token\'s causal length, including for short requests.\n'
    '            compressed_kv_cache = swa_kv_cache\n'
    '            seq_lens = core_attn_metadata.swa_topk_lengths[:bs]\n'
)
DSPARK_NEW = (
    '        # DSpark draft block: its 64-aligned table (SWA_WINDOW + block) packs\n'
    '        # the noncausal context window and the block slots in SWA storage, so\n'
    '        # the 0.7.x surface takes it whole as the SWA segment: the per-row\n'
    '        # count is a total, not a compressed count, hence no tail to split;\n'
    '        # the compressed cache is the SWA cache (compress_ratio == 0) and the\n'
    '        # packed branch\'s seq_lens override is unused by this route.\n'
)

# --- delta 4a: BF16 query in the backend ------------------------------------
BACKEND_IMPORT_OLD = 'from sglang.srt.environ import envs\n'
BACKEND_IMPORT_NEW = (
    'from sglang.srt.environ import envs\n'
    'from sglang.srt.utils.common import is_sm120_supported\n'
)

DECODE_Q_OLD = (
    '        # Q preparation already returns FP8 on V4.1; to() is a no-op in that path.\n'
    '        q_fp8 = q.to(torch.float8_e4m3fn).view(bs, 1, num_heads, 512)\n'
)
DECODE_Q_NEW = (
    '        # Q preparation already returns FP8 on V4.1; to() is a no-op in that path.\n'
    '        # FlashInfer >= 0.7 SM12x takes a BF16 query instead of FP8.\n'
    '        if is_sm120_supported():\n'
    '            assert q.dtype == torch.bfloat16, (\n'
    '                f"SM12x sparse MLA needs a BF16 query, got {q.dtype}"\n'
    '            )\n'
    '            q_fp8 = q.view(bs, 1, num_heads, 512)\n'
    '        else:\n'
    '            q_fp8 = q.to(torch.float8_e4m3fn).view(bs, 1, num_heads, 512)\n'
)

PREFILL_Q_OLD = (
    '        # Retain a unit-scale cast for callers without fused FP8 Q preparation.\n'
    '        q_fp8 = q[:sum_q].to(torch.float8_e4m3fn)\n'
)
PREFILL_Q_NEW = (
    '        # Retain a unit-scale cast for callers without fused FP8 Q preparation.\n'
    '        if is_sm120_supported():\n'
    '            assert q.dtype == torch.bfloat16, (\n'
    '                f"SM12x sparse MLA needs a BF16 query, got {q.dtype}"\n'
    '            )\n'
    '            q_fp8 = q[:sum_q]\n'
    '        else:\n'
    '            q_fp8 = q[:sum_q].to(torch.float8_e4m3fn)\n'
)

# --- delta 5a: 528-byte inline-scale views + kv_cache_format ----------------
VIEWS_OLD = (
    '        token_to_kv_pool = self.token_to_kv_pool\n'
    '        swa_buf = token_to_kv_pool.get_swa_key_buffer_radix(layer_id)\n'
    '        swa_page_size = token_to_kv_pool.swa_kv_pool.page_size\n'
    '        swa_kv_cache = swa_buf.view(swa_buf.shape[0], 1, swa_page_size, 512)\n'
    '        if compress_ratio == 0:\n'
    '            compressed_kv_cache = swa_kv_cache\n'
    '        else:\n'
    '            extra_buf = token_to_kv_pool.get_extra_key_buffer(layer_id)\n'
    '            extra_page_size = token_to_kv_pool.get_extra_key_page_size(layer_id)\n'
    '            compressed_kv_cache = extra_buf.view(\n'
    '                extra_buf.shape[0], 1, extra_page_size, 512\n'
    '            )\n'
    '        return swa_kv_cache, compressed_kv_cache\n'
)
VIEWS_NEW = (
    '        token_to_kv_pool = self.token_to_kv_pool\n'
    '        swa_buf = token_to_kv_pool.get_swa_key_buffer_radix(layer_id)\n'
    '        swa_page_size = token_to_kv_pool.swa_kv_pool.page_size\n'
    '        if is_sm120_supported():\n'
    '            # 528-byte inline-scale records: 512 data + 16 UE8M0 scale bytes.\n'
    '            assert token_to_kv_pool.request_window is None, (\n'
    '                "the SM12x 528-byte KV port does not cover the bounded-replay "\n'
    '                "request window"\n'
    '            )\n'
    '            row_bytes = token_to_kv_pool.get_swa_key_bytes_per_token()\n'
    '            swa_kv_cache = swa_buf.view(torch.uint8).view(\n'
    '                swa_buf.shape[0], 1, swa_page_size, row_bytes\n'
    '            )\n'
    '        else:\n'
    '            swa_kv_cache = swa_buf.view(swa_buf.shape[0], 1, swa_page_size, 512)\n'
    '        if compress_ratio == 0:\n'
    '            compressed_kv_cache = swa_kv_cache\n'
    '        else:\n'
    '            extra_buf = token_to_kv_pool.get_extra_key_buffer(layer_id)\n'
    '            extra_page_size = token_to_kv_pool.get_extra_key_page_size(layer_id)\n'
    '            if is_sm120_supported():\n'
    '                extra_row_bytes = token_to_kv_pool.get_extra_key_bytes_per_token(\n'
    '                    layer_id\n'
    '                )\n'
    '                compressed_kv_cache = extra_buf.view(torch.uint8).view(\n'
    '                    extra_buf.shape[0], 1, extra_page_size, extra_row_bytes\n'
    '                )\n'
    '            else:\n'
    '                compressed_kv_cache = extra_buf.view(\n'
    '                    extra_buf.shape[0], 1, extra_page_size, 512\n'
    '                )\n'
    '        return swa_kv_cache, compressed_kv_cache\n'
)

DECODE_CALL = (
    '        out = trtllm_batch_decode_sparse_mla_dsv4(\n'
    '            query=q_fp8,\n'
    '            swa_kv_cache=swa_kv_cache,\n'
    '            workspace_buffer=self.trtllm_workspace_buffer,\n'
    '            sparse_indices=sparse_indices,\n'
    '            compressed_kv_cache=compressed_kv_cache,\n'
    '            sparse_topk_lens=sparse_topk_lens,\n'
    '            seq_lens=seq_lens,\n'
    '            bmm1_scale=bmm1_scale,\n'
    '            bmm2_scale=bmm2_scale,\n'
    '            sinks=attn_sink,\n'
    '            kv_layout="HND",\n'
    '            backend="trtllm-gen",\n'
    '        )\n'
)
DECODE_CALL_NEW = (
    '        # 0.7.x split call: the 128 SWA columns are their own segment and\n'
    '        # the compressed tail is a second one, each with its own length.\n'
    '        # Only a compressed-layer table carries such a tail; a wider\n'
    '        # compress_ratio == 0 table is the DSpark draft\'s combined\n'
    '        # window+block table and goes whole as the SWA segment.\n'
    '        swa_topk_lens = core_attn_metadata.trtllm_swa_lens[:bs]\n'
    '        extra_sparse_indices = None\n'
    '        extra_sparse_topk_lens = None\n'
    '        if compress_ratio != 0 and sparse_indices.shape[1] > SWA_WINDOW:\n'
    '            extra_sparse_indices = sparse_indices[:, SWA_WINDOW:]\n'
    '            extra_sparse_topk_lens = sparse_topk_lens - SWA_WINDOW\n'
    '            sparse_indices = sparse_indices[:, :SWA_WINDOW]\n'
    '        out = trtllm_batch_decode_sparse_mla_dsv4(\n'
    '            query=q_fp8,\n'
    '            swa_kv_cache=swa_kv_cache,\n'
    '            workspace_buffer=self.trtllm_workspace_buffer,\n'
    '            sparse_indices=sparse_indices,\n'
    '            compressed_kv_cache=compressed_kv_cache,\n'
    '            swa_topk_lens=swa_topk_lens,\n'
    '            extra_sparse_indices=extra_sparse_indices,\n'
    '            extra_sparse_topk_lens=extra_sparse_topk_lens,\n'
    '            seq_lens=seq_lens,\n'
    '            bmm1_scale=bmm1_scale,\n'
    '            bmm2_scale=bmm2_scale,\n'
    '            sinks=attn_sink,\n'
    '            kv_layout="HND",\n'
    '            kv_cache_format=(\n'
    '                "fp8_dsv41_inline" if is_sm120_supported() else "fp8"\n'
    '            ),\n'
    '            backend="auto",\n'
    '        )\n'
)

PREFILL_CALL = (
    '        out = trtllm_batch_decode_sparse_mla_dsv4(\n'
    '            query=q_fp8,\n'
    '            swa_kv_cache=swa_kv_cache,\n'
    '            workspace_buffer=self.trtllm_workspace_buffer,\n'
    '            sparse_indices=sparse_indices,\n'
    '            compressed_kv_cache=compressed_kv_cache,\n'
    '            sparse_topk_lens=sparse_topk_lens,\n'
    '            seq_lens=seq_lens,\n'
    '            out=out_arg,\n'
    '            bmm1_scale=bmm1_scale,\n'
    '            bmm2_scale=bmm2_scale,\n'
    '            sinks=attn_sink,\n'
    '            kv_layout="HND",\n'
    '            backend="trtllm-gen",\n'
    '            cum_seq_lens_q=cum_seq_lens_q,\n'
    '            max_q_len=max_q_len,\n'
    '        )\n'
)
PREFILL_CALL_NEW = (
    '        # Same split as decode; the per-chunk SWA lens are constant 128 and\n'
    '        # the compressed counts drop the fixed SWA width.\n'
    '        if core.trtllm_prefill_swa_lens is None:\n'
    '            core.trtllm_prefill_swa_lens = _tile_padded_pf(SWA_WINDOW)\n'
    '        swa_topk_lens = core.trtllm_prefill_swa_lens\n'
    '        extra_sparse_indices = None\n'
    '        extra_sparse_topk_lens = None\n'
    '        if sparse_indices.shape[1] > SWA_WINDOW:\n'
    '            extra_sparse_indices = sparse_indices[:, SWA_WINDOW:]\n'
    '            extra_sparse_topk_lens = sparse_topk_lens - SWA_WINDOW\n'
    '            sparse_indices = sparse_indices[:, :SWA_WINDOW]\n'
    '        out = trtllm_batch_decode_sparse_mla_dsv4(\n'
    '            query=q_fp8,\n'
    '            swa_kv_cache=swa_kv_cache,\n'
    '            workspace_buffer=self.trtllm_workspace_buffer,\n'
    '            sparse_indices=sparse_indices,\n'
    '            compressed_kv_cache=compressed_kv_cache,\n'
    '            swa_topk_lens=swa_topk_lens,\n'
    '            extra_sparse_indices=extra_sparse_indices,\n'
    '            extra_sparse_topk_lens=extra_sparse_topk_lens,\n'
    '            seq_lens=seq_lens,\n'
    '            out=out_arg,\n'
    '            bmm1_scale=bmm1_scale,\n'
    '            bmm2_scale=bmm2_scale,\n'
    '            sinks=attn_sink,\n'
    '            kv_layout="HND",\n'
    '            kv_cache_format=(\n'
    '                "fp8_dsv41_inline" if is_sm120_supported() else "fp8"\n'
    '            ),\n'
    '            backend="auto",\n'
    '            cum_seq_lens_q=cum_seq_lens_q,\n'
    '            max_q_len=max_q_len,\n'
    '        )\n'
)

# --- delta 8: row-packed prefill index tables -------------------------------
# 0.7.3 prepares call metadata from the tensors themselves, and its prefill
# (and every call above `_DECODE_MAX_TOKENS`) is admitted only when the index
# tables are row-packed: a column slice of the combined table keeps the wider
# row stride and comes back as "no decode kernel for this shape: ...
# Mismatch: no matching decode instantiation" at
# `_sparse_mla_sm120/_prepared.py:175`. Measured on the GB10 with this image
# (receipt `arm5-fi073c-20261111/probe_prefill_stride_matrix.py`): 193 and
# 16,384 rows are admitted and executed with packed tables, refused with the
# sliced ones, on both the functional call and the wrapper's `run`. Decode is
# untouched up to the 64-row envelope; delta 9 repacks it above that, where
# the target-verify batch lands.
PREFILL_SPLIT_OLD = (
    '        extra_sparse_indices = None\n'
    '        extra_sparse_topk_lens = None\n'
    '        if sparse_indices.shape[1] > SWA_WINDOW:\n'
    '            extra_sparse_indices = sparse_indices[:, SWA_WINDOW:]\n'
    '            extra_sparse_topk_lens = sparse_topk_lens - SWA_WINDOW\n'
    '            sparse_indices = sparse_indices[:, :SWA_WINDOW]\n'
)
PREFILL_SPLIT_NEW = (
    '        extra_sparse_indices = None\n'
    '        extra_sparse_topk_lens = None\n'
    '        if sparse_indices.shape[1] > SWA_WINDOW:\n'
    '            # Packed rows only: the metadata check reads the tensors\' own\n'
    '            # strides, and a column slice of the combined table is refused.\n'
    '            extra_sparse_indices = sparse_indices[:, SWA_WINDOW:].contiguous()\n'
    '            extra_sparse_topk_lens = sparse_topk_lens - SWA_WINDOW\n'
    '            sparse_indices = sparse_indices[:, :SWA_WINDOW].contiguous()\n'
)

# --- delta 9: row-packed decode split above the 64-row envelope -------------
# The target-verify call runs `_forward_trtllm_decode` with one row per draft
# token (16 requests x 6 = 96), above FlashInfer's 64-row decode envelope, so
# the library executes its prefill variant -- which refuses the decode path's
# column slices exactly as delta 8's prefill call did. SM12x visibility is the
# per-token sparse table alone (the routed call forwards no seq_lens /
# cum_seq_lens_q, `mla/_core.py:2413`), so the same tables keep a verify
# batch's math. Only rows above 64 pay the repack; <=64-row decode is
# byte-identical to the served path.
DECODE_SPLIT_OLD = (
    '        if compress_ratio != 0 and sparse_indices.shape[1] > SWA_WINDOW:\n'
    '            extra_sparse_indices = sparse_indices[:, SWA_WINDOW:]\n'
    '            extra_sparse_topk_lens = sparse_topk_lens - SWA_WINDOW\n'
    '            sparse_indices = sparse_indices[:, :SWA_WINDOW]\n'
)
DECODE_SPLIT_NEW = (
    '        if compress_ratio != 0 and sparse_indices.shape[1] > SWA_WINDOW:\n'
    '            extra_sparse_indices = sparse_indices[:, SWA_WINDOW:]\n'
    '            extra_sparse_topk_lens = sparse_topk_lens - SWA_WINDOW\n'
    '            sparse_indices = sparse_indices[:, :SWA_WINDOW]\n'
    '            if bs > 64:\n'
    '                # Above the 64-row decode envelope this call runs the\n'
    '                # prefill variant, which refuses the column slices above\n'
    '                # for their wider row stride.\n'
    '                extra_sparse_indices = extra_sparse_indices.contiguous()\n'
    '                sparse_indices = sparse_indices.contiguous()\n'
)

# --- delta 4b: BF16 query buffer in the model -------------------------------
MODEL_IMPORT_OLD = 'from sglang.srt.utils.custom_op import register_custom_op\n'
MODEL_IMPORT_NEW = (
    'from sglang.srt.utils.common import is_sm120_supported\n'
    'from sglang.srt.utils.custom_op import register_custom_op\n'
)
MODEL_Q_OLD = (
    '            q_out = torch.empty(\n'
    '                (x.shape[0], self.n_local_heads, self.head_dim),\n'
    '                dtype=torch.float8_e4m3fn,\n'
    '                device=x.device,\n'
    '            )\n'
)
MODEL_Q_NEW = (
    '            # FlashInfer >= 0.7 SM12x takes a BF16 query; the contiguous FP8\n'
    '            # buffer is a trtllm-gen (SM100/103) contract only.\n'
    '            q_out = torch.empty(\n'
    '                (x.shape[0], self.n_local_heads, self.head_dim),\n'
    '                dtype=(\n'
    '                    torch.bfloat16\n'
    '                    if is_sm120_supported()\n'
    '                    else torch.float8_e4m3fn\n'
    '                ),\n'
    '                device=x.device,\n'
    '            )\n'
)

# --- delta 6: BF16 query on the DSpark draft path ---------------------------
# The draft model owns a second Q-buffer allocation (its attention forward),
# so the model-side gate in delta 4b never reached it: the draft handed the
# ported decode an FP8 query and tripped the backend's fail-closed BF16 assert
# during draft CUDA-graph capture.
DSPARK_IMPORT_OLD = 'from sglang.srt.utils import add_prefix, is_npu\n'
DSPARK_IMPORT_NEW = (
    'from sglang.srt.utils import add_prefix, is_npu\n'
    'from sglang.srt.utils.common import is_sm120_supported\n'
)
DSPARK_Q_OLD = (
    '            q_out = torch.empty(\n'
    '                (hidden_states.shape[0], self.n_local_heads, self.head_dim),\n'
    '                dtype=torch.float8_e4m3fn,\n'
    '                device=hidden_states.device,\n'
    '            )\n'
)
DSPARK_Q_NEW = (
    '            # FlashInfer >= 0.7 SM12x takes BF16 query; the contiguous FP8\n'
    '            # buffer is a trtllm-gen (SM100/103) contract only.\n'
    '            q_out = torch.empty(\n'
    '                (hidden_states.shape[0], self.n_local_heads, self.head_dim),\n'
    '                dtype=(\n'
    '                    torch.bfloat16\n'
    '                    if is_sm120_supported()\n'
    '                    else torch.float8_e4m3fn\n'
    '                ),\n'
    '                device=hidden_states.device,\n'
    '            )\n'
)

# --- delta 5b: 528-byte pool rows -------------------------------------------
POOL_IMPORT_OLD = 'from sglang.srt.utils import ceil_div, is_gfx95_supported, is_hip\n'
POOL_IMPORT_NEW = (
    'from sglang.srt.utils import (\n'
    '    ceil_div,\n'
    '    is_gfx95_supported,\n'
    '    is_hip,\n'
    '    is_sm120_supported,\n'
    ')\n'
)
POOL_CLASS_OLD = (
    'class DeepSeekV4UniformFP8KVPool(DeepSeekV4SingleKVPool):\n'
    '    """Each token is 448 NoPE + 64 RoPE contiguous e4m3 values, without in-cache\n'
    '    scales or per-page padding; the backend supplies the dequant scale."""\n'
    '\n'
    '    def get_bytes_per_token(self) -> int:\n'
    '        return self.qk_nope_head_dim + self.qk_rope_head_dim\n'
    '\n'
    '    def create_buffer(self, *, num_pages: int):\n'
    '        bytes_per_token = self.get_bytes_per_token()\n'
    '        assert bytes_per_token == 512, (\n'
    '            "DSV4 uniform-FP8 KV layout: qk_nope_head_dim (448) + "\n'
    '            "qk_rope_head_dim (64), all e4m3 = 512 bytes/token"\n'
    '        )\n'
    '        self.kv_cache_total_dim = bytes_per_token\n'
    '        self.bytes_per_page_padded = self.page_size * bytes_per_token\n'
    '\n'
    '        return torch.zeros(\n'
    '            num_pages,\n'
    '            self.page_size * bytes_per_token,\n'
    '            dtype=torch.float8_e4m3fn,\n'
    '            device=self.device,\n'
    '        )\n'
    '\n'
    '    def get_key_buffer(self, layer_id: int):\n'
    '        return self.kv_buffer[layer_id]\n'
    '\n'
    '    def set_key_buffer(\n'
    '        self,\n'
    '        layer_id: int,\n'
    '        loc: torch.Tensor,\n'
    '        cache_nope_fp8_rope_bf16_pack: NopeFp8RopeBf16Pack,\n'
    '    ):\n'
    '        raise NotImplementedError(\n'
    '            "The packed NopeFp8RopeBf16Pack store does not apply to the "\n'
    '            "uniform-FP8 pool; use set_key_buffer_fused."\n'
    '        )\n'
    '\n'
    '    def set_key_buffer_fused(\n'
    '        self,\n'
    '        layer_id: int,\n'
    '        loc: torch.Tensor,\n'
    '        cache_k: torch.Tensor,\n'
    '        freqs_cis: Optional[torch.Tensor] = None,\n'
    '    ) -> None:\n'
    '        """Store normed/roped rows as e4m3 with the backend\'s fixed unit scale;\n'
    '        uint8 views work around index_put not supporting FP8 dtypes."""\n'
    '\n'
    '        assert freqs_cis is None, "the uniform-FP8 pool takes finished (rotated) rows"\n'
    '        assert cache_k.dim() == 2 and cache_k.shape[1] == self.kv_cache_total_dim\n'
    '        self.kv_buffer[layer_id].view(torch.uint8).view(-1, self.kv_cache_total_dim)[\n'
    '            loc.long()\n'
    '        ] = cache_k.to(torch.float8_e4m3fn).view(torch.uint8)\n'
)
POOL_CLASS_NEW = (
    'class DeepSeekV4UniformFP8KVPool(DeepSeekV4SingleKVPool):\n'
    '    """Each token is 448 NoPE + 64 RoPE contiguous e4m3 values, without in-cache\n'
    '    scales or per-page padding; the backend supplies the dequant scale.\n'
    '\n'
    '    On SM12x (FlashInfer >= 0.7\'s sparse route) a token is a 528-byte\n'
    '    inline-scale record instead: the same 512 e4m3 values followed by 16\n'
    '    UE8M0 group-32 scale bytes. The store is unit-scale, so each footer is\n'
    '    the constant 2^0 code and is written once at allocation."""\n'
    '\n'
    '    _SM12X_ROW_BYTES = 528\n'
    '    _SM12X_SCALE_BYTE = 0x7F\n'
    '\n'
    '    def get_bytes_per_token(self) -> int:\n'
    '        if is_sm120_supported():\n'
    '            return self._SM12X_ROW_BYTES\n'
    '        return self.qk_nope_head_dim + self.qk_rope_head_dim\n'
    '\n'
    '    def create_buffer(self, *, num_pages: int):\n'
    '        data_bytes = self.qk_nope_head_dim + self.qk_rope_head_dim\n'
    '        assert data_bytes == 512, (\n'
    '            "DSV4 uniform-FP8 KV layout: qk_nope_head_dim (448) + "\n'
    '            "qk_rope_head_dim (64), all e4m3 = 512 bytes/token"\n'
    '        )\n'
    '        bytes_per_token = self.get_bytes_per_token()\n'
    '        self.kv_cache_total_dim = bytes_per_token\n'
    '        self.bytes_per_page_padded = self.page_size * bytes_per_token\n'
    '\n'
    '        buf = torch.zeros(\n'
    '            num_pages,\n'
    '            self.page_size * bytes_per_token,\n'
    '            dtype=torch.float8_e4m3fn,\n'
    '            device=self.device,\n'
    '        )\n'
    '        if bytes_per_token != data_bytes:\n'
    '            # Constant unit-scale footer; the stores write only the data bytes.\n'
    '            buf.view(torch.uint8).view(-1, bytes_per_token)[:, data_bytes:] = (\n'
    '                self._SM12X_SCALE_BYTE\n'
    '            )\n'
    '        return buf\n'
    '\n'
    '    def get_key_buffer(self, layer_id: int):\n'
    '        return self.kv_buffer[layer_id]\n'
    '\n'
    '    def set_key_buffer(\n'
    '        self,\n'
    '        layer_id: int,\n'
    '        loc: torch.Tensor,\n'
    '        cache_nope_fp8_rope_bf16_pack: NopeFp8RopeBf16Pack,\n'
    '    ):\n'
    '        raise NotImplementedError(\n'
    '            "The packed NopeFp8RopeBf16Pack store does not apply to the "\n'
    '            "uniform-FP8 pool; use set_key_buffer_fused."\n'
    '        )\n'
    '\n'
    '    def set_key_buffer_fused(\n'
    '        self,\n'
    '        layer_id: int,\n'
    '        loc: torch.Tensor,\n'
    '        cache_k: torch.Tensor,\n'
    '        freqs_cis: Optional[torch.Tensor] = None,\n'
    '    ) -> None:\n'
    '        """Store normed/roped rows as e4m3 with the backend\'s fixed unit scale;\n'
    '        uint8 views work around index_put not supporting FP8 dtypes."""\n'
    '\n'
    '        assert freqs_cis is None, "the uniform-FP8 pool takes finished (rotated) rows"\n'
    '        data_bytes = self.qk_nope_head_dim + self.qk_rope_head_dim\n'
    '        assert cache_k.dim() == 2 and cache_k.shape[1] == data_bytes\n'
    '        self.kv_buffer[layer_id].view(torch.uint8).view(\n'
    '            -1, self.kv_cache_total_dim\n'
    '        )[loc.long(), :data_bytes] = cache_k.to(torch.float8_e4m3fn).view(\n'
    '            torch.uint8\n'
    '        )\n'
)

# --- delta 5c: 528-byte row pitch in the uniform SWA store -----------------
RADIX_STORE_OLD = (
    '    def set_swa_key_buffer_radix_fused(\n'
    '        self,\n'
    '        layer_id: int,\n'
    '        swa_loc: torch.Tensor,\n'
    '        cache_k: torch.Tensor,\n'
    '    ) -> None:\n'
    '        return fused_store_cache(\n'
)
RADIX_STORE_NEW = (
    '    def set_swa_key_buffer_radix_fused(\n'
    '        self,\n'
    '        layer_id: int,\n'
    '        swa_loc: torch.Tensor,\n'
    '        cache_k: torch.Tensor,\n'
    '    ) -> None:\n'
    '        # Fail closed instead of packing 512-byte FlashMLA rows into the\n'
    '        # 528-byte SM12x pitch; the norm+rope fused store handles that pool.\n'
    '        assert not (self.uniform_fp8 and is_sm120_supported()), (\n'
    '            "the SM12x uniform-FP8 pool stores 528-byte inline rows; use "\n'
    '            "set_swa_key_buffer_radix_fused_norm_rope (or unset "\n'
    '            "SGLANG_DSV4_USE_BF16_KV_QUANT_SOURCE)"\n'
    '        )\n'
    '        return fused_store_cache(\n'
)

SWA_STORE_OLD = (
    '            fused_k_norm_rope_uniform_fp8(\n'
    '                kv,\n'
    '                kv_weight,\n'
    '                eps,\n'
    '                freqs_cis,\n'
    '                positions,\n'
    '                swa_loc,\n'
    '                self.swa_kv_pool.get_key_buffer(self._swa_local_layer_id(layer_id)),\n'
    '            )\n'
)
SWA_STORE_NEW = (
    '            fused_k_norm_rope_uniform_fp8(\n'
    '                kv,\n'
    '                kv_weight,\n'
    '                eps,\n'
    '                freqs_cis,\n'
    '                positions,\n'
    '                swa_loc,\n'
    '                self.swa_kv_pool.get_key_buffer(self._swa_local_layer_id(layer_id)),\n'
    '                row_bytes=self.swa_kv_pool.kv_cache_total_dim,\n'
    '            )\n'
)

KERNEL_ROW_OLD = (
    '    SF: tl.constexpr,\n'
    '    CACHE_ROWS: tl.constexpr,\n'
    '):\n'
)
KERNEL_ROW_NEW = (
    '    SF: tl.constexpr,\n'
    '    CACHE_ROWS: tl.constexpr,\n'
    '    ROW_BYTES: tl.constexpr,\n'
    '):\n'
)
KERNEL_DST_OLD = '    dst = CACHE + slot * 512\n'
KERNEL_DST_NEW = '    dst = CACHE + slot * ROW_BYTES\n'
KERNEL_SIG_OLD = (
    '    loc: torch.Tensor,\n'
    '    cache: torch.Tensor,\n'
    ') -> None:\n'
    '    """Store norm+RoPE KV as unit-scale E4M3, without modifying ``kv``.\n'
    '\n'
    '    ``loc`` addresses contiguous 512-byte rows in the uniform-FP8 pool.\n'
    '    Active rows must have valid, distinct destinations, as with index_put.\n'
    '    """\n'
)
KERNEL_SIG_NEW = (
    '    loc: torch.Tensor,\n'
    '    cache: torch.Tensor,\n'
    '    row_bytes: int = 512,\n'
    ') -> None:\n'
    '    """Store norm+RoPE KV as unit-scale E4M3, without modifying ``kv``.\n'
    '\n'
    '    ``loc`` addresses ``row_bytes``-wide rows in the uniform-FP8 pool; on\n'
    '    SM12x the row is a 528-byte inline-scale record and only the first 512\n'
    '    bytes are written (the footer is the constant unit-scale code).\n'
    '    Active rows must have valid, distinct destinations, as with index_put.\n'
    '    """\n'
)
KERNEL_ASSERT_OLD = '    assert cache.numel() % 512 == 0\n'
KERNEL_ASSERT_NEW = '    assert cache.numel() % row_bytes == 0\n'
KERNEL_LAUNCH_OLD = (
    '        CACHE_ROWS=cache.numel() // 512,\n'
    '        num_warps=4,\n'
)
KERNEL_LAUNCH_NEW = (
    '        CACHE_ROWS=cache.numel() // row_bytes,\n'
    '        ROW_BYTES=row_bytes,\n'
    '        num_warps=4,\n'
)

# --- delta 5d: bypass the fused c1/c2 compressor store on SM12x ------------
BASE_IMPORT_OLD = 'from sglang.srt.environ import envs\n'
BASE_IMPORT_NEW = (
    'from sglang.srt.environ import envs\n'
    'from sglang.srt.utils.common import is_sm120_supported\n'
)
BASE_HELPER_OLD = 'logger = logging.getLogger(__name__)\n'
BASE_HELPER_NEW = (
    'logger = logging.getLogger(__name__)\n'
    '\n'
    '\n'
    'def _dsv4_uniform_sm12x(pool) -> bool:\n'
    '    """The fused c1/c2 compressor store is compiled for 512-byte uniform\n'
    '    rows; on SM12x the pool is 528-byte inline-scale, so the torch store\n'
    '    that ends in the pool\'s own setter must run instead."""\n'
    '    return bool(getattr(pool, "uniform_fp8", False)) and is_sm120_supported()\n'
)
VERIFY_GATE_OLD = (
    '            and layer.compressor.use_fused_compress\n'
    '            and read_ragged_verify_mode() is not RaggedVerifyMode.COMPACT\n'
)
VERIFY_GATE_NEW = (
    '            and layer.compressor.use_fused_compress\n'
    '            and not _dsv4_uniform_sm12x(self.token_to_kv_pool)\n'
    '            and read_ragged_verify_mode() is not RaggedVerifyMode.COMPACT\n'
)
EXTEND_GATE_OLD = (
    '        elif (\n'
    '            layer.compressor.use_fused_compress\n'
    '            and forward_batch.forward_mode.is_extend_without_speculative()\n'
)
EXTEND_GATE_NEW = (
    '        elif (\n'
    '            layer.compressor.use_fused_compress\n'
    '            and not _dsv4_uniform_sm12x(self.token_to_kv_pool)\n'
    '            and forward_batch.forward_mode.is_extend_without_speculative()\n'
)
FUSE_INDEX_GATE_OLD = (
    '                    and layer.compressor.use_fused_compress\n'
    '                ),\n'
)
FUSE_INDEX_GATE_NEW = (
    '                    and layer.compressor.use_fused_compress\n'
    '                    and not _dsv4_uniform_sm12x(self.token_to_kv_pool)\n'
    '                ),\n'
)
DECODE_GATE_OLD = (
    '        if layer.compressor.use_fused_compress:\n'
    '            self._low_ratio_compress_fused(layer, x, req, pos)\n'
)
DECODE_GATE_NEW = (
    '        if layer.compressor.use_fused_compress and not _dsv4_uniform_sm12x(\n'
    '            self.token_to_kv_pool\n'
    '        ):\n'
    '            self._low_ratio_compress_fused(layer, x, req, pos)\n'
)

patch(BACKEND, SEMAPHORE_OLD, SEMAPHORE_NEW)
patch(BACKEND, DSPARK_OLD, DSPARK_NEW)
patch(BACKEND, BACKEND_IMPORT_OLD, BACKEND_IMPORT_NEW)
patch(BACKEND, DECODE_Q_OLD, DECODE_Q_NEW)
patch(BACKEND, PREFILL_Q_OLD, PREFILL_Q_NEW)
patch(BACKEND, VIEWS_OLD, VIEWS_NEW)
patch(BACKEND, DECODE_CALL, DECODE_CALL_NEW)
patch(BACKEND, PREFILL_CALL, PREFILL_CALL_NEW)
patch(BACKEND, PREFILL_SPLIT_OLD, PREFILL_SPLIT_NEW)
patch(BACKEND, DECODE_SPLIT_OLD, DECODE_SPLIT_NEW)

patch(MODEL, MODEL_IMPORT_OLD, MODEL_IMPORT_NEW)
patch(MODEL, MODEL_Q_OLD, MODEL_Q_NEW)

patch(DSPARK, DSPARK_IMPORT_OLD, DSPARK_IMPORT_NEW)
patch(DSPARK, DSPARK_Q_OLD, DSPARK_Q_NEW)

patch(POOL, POOL_IMPORT_OLD, POOL_IMPORT_NEW)
patch(POOL, POOL_CLASS_OLD, POOL_CLASS_NEW)
patch(POOL, SWA_STORE_OLD, SWA_STORE_NEW)
patch(POOL, RADIX_STORE_OLD, RADIX_STORE_NEW)

patch(STORE, KERNEL_ROW_OLD, KERNEL_ROW_NEW)
patch(STORE, KERNEL_DST_OLD, KERNEL_DST_NEW)
patch(STORE, KERNEL_SIG_OLD, KERNEL_SIG_NEW)
patch(STORE, KERNEL_ASSERT_OLD, KERNEL_ASSERT_NEW)
patch(STORE, KERNEL_LAUNCH_OLD, KERNEL_LAUNCH_NEW)

patch(BACKEND_BASE, BASE_IMPORT_OLD, BASE_IMPORT_NEW)
patch(BACKEND_BASE, BASE_HELPER_OLD, BASE_HELPER_NEW)
patch(BACKEND_BASE, VERIFY_GATE_OLD, VERIFY_GATE_NEW)
patch(BACKEND_BASE, EXTEND_GATE_OLD, EXTEND_GATE_NEW)
patch(BACKEND_BASE, FUSE_INDEX_GATE_OLD, FUSE_INDEX_GATE_NEW)
patch(BACKEND_BASE, DECODE_GATE_OLD, DECODE_GATE_NEW)

backend_text = BACKEND.read_text()
assert 'backend="trtllm-gen"' not in backend_text, "a trtllm-gen call site survived"
assert backend_text.count('backend="auto"') == 2, backend_text.count('backend="auto"')
assert backend_text.count('"fp8_dsv41_inline" if is_sm120_supported()') == 2
assert backend_text.count("assert q.dtype == torch.bfloat16") == 2
assert "the DSpark noncausal draft path" not in backend_text, (
    "the DSpark draft-path refusal survived"
)
assert (
    backend_text.count(
        "if compress_ratio != 0 and sparse_indices.shape[1] > SWA_WINDOW:"
    )
    == 1
), "the decode split is not gated on compressed ratios"
assert backend_text.count("if sparse_indices.shape[1] > SWA_WINDOW:") == 1, (
    "a decode split survived beside the prefill one"
)
# delta 8: the prefill split must hand the route row-packed tables.
assert backend_text.count(
    "extra_sparse_indices = sparse_indices[:, SWA_WINDOW:].contiguous()"
) == 1, "the prefill tail table is not row-packed"
assert backend_text.count(
    "sparse_indices = sparse_indices[:, :SWA_WINDOW].contiguous()"
) == 1, "the prefill SWA table is not row-packed"
# delta 9: the decode split repacks only above the 64-row envelope, so the
# served <=64-row decode keeps the slices it was measured on.
assert backend_text.count("if bs > 64:") == 1, (
    "the >64-row decode repack gate is missing"
)
assert backend_text.count(
    "extra_sparse_indices = extra_sparse_indices.contiguous()"
) == 1, "the decode tail table is not row-packed above 64 rows"
assert backend_text.count("sparse_indices = sparse_indices.contiguous()") == 1, (
    "the decode SWA table is not row-packed above 64 rows"
)
assert backend_text.count(".contiguous()") == 4, backend_text.count(".contiguous()")

model_text = MODEL.read_text()
assert "from sglang.srt.utils.common import is_sm120_supported" in model_text
assert "torch.bfloat16\n                    if is_sm120_supported()" in model_text, (
    "the SM12x BF16 Q buffer gate is missing"
)

dspark_text = DSPARK.read_text()
assert dspark_text.count("dtype=torch.float8_e4m3fn") == 0, (
    "a DSpark draft FP8 Q buffer survived; the SM12x decode never sees one"
)
assert dspark_text.count("dtype=(\n                    torch.bfloat16") == 1, (
    dspark_text.count("dtype=(\n                    torch.bfloat16")
)

pool_text = POOL.read_text()
assert "_SM12X_ROW_BYTES = 528" in pool_text
assert "_SM12X_SCALE_BYTE = 0x7F" in pool_text
assert "row_bytes=self.swa_kv_pool.kv_cache_total_dim" in pool_text

store_text = STORE.read_text()
assert "ROW_BYTES: tl.constexpr" in store_text
assert "dst = CACHE + slot * ROW_BYTES" in store_text
assert "row_bytes: int = 512" in store_text

base_text = BACKEND_BASE.read_text()
assert base_text.count("_dsv4_uniform_sm12x(self.token_to_kv_pool)") == 3, (
    base_text.count("_dsv4_uniform_sm12x(self.token_to_kv_pool)")
)
assert base_text.count("_dsv4_uniform_sm12x(") == 5, base_text.count(
    "_dsv4_uniform_sm12x("
)

print("patched:", BACKEND, MODEL, DSPARK, POOL, STORE, BACKEND_BASE, sep="\n  ")
