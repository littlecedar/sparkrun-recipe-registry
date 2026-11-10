#!/usr/bin/env python3
"""FlashInfer 0.7.x SM121 deltas for the DSV4 trtllm sparse-MLA backend.

Applied inside ``dsv41-sm121-dg:0.2.1`` after the 0.7.3 wheel overlay. The
three changes are the ones named in ``mad-science/SM121-SPARSE-MLA-PORT.md``
section Port A:

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

Every anchor must match exactly once, so a base-tree move fails the build
instead of shipping a half-patched image.
"""
import os
import pathlib

ROOT = pathlib.Path(
    os.getenv("DSV41_FI073_TREE", "/sgl-workspace/sglang/python/sglang/srt")
)
BACKEND = ROOT / "layers/attention/deepseek_v4_trtllm_backend.py"


def patch(path, old, new):
    p = pathlib.Path(path)
    s = p.read_text()
    assert s.count(old) == 1, (str(path), s.count(old), old[:80])
    p.write_text(s.replace(old, new, 1))


SEMAPHORE_OLD = '    _orig = _fi_core._get_trtllm_gen_multi_ctas_kv_counter_buffer\n'
SEMAPHORE_NEW = (
    '    if not hasattr(_fi_core, "_get_trtllm_gen_multi_ctas_kv_counter_buffer"):\n'
    '        # FlashInfer >= 0.7 removed the private request-count sizing helper;\n'
    '        # the SM12x sparse route takes no counter buffer, so the WAR is moot.\n'
    '        return\n'
    '    _orig = _fi_core._get_trtllm_gen_multi_ctas_kv_counter_buffer\n'
)

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
    '        if swa_width > SWA_WINDOW:\n'
    '            # The 0.7.x split call has no combined length: the DSpark draft\n'
    '            # tail lives in SWA storage but its per-row length is a total, not\n'
    '            # a compressed count, so re-plumbing it needs its own measurement.\n'
    '            raise NotImplementedError(\n'
    '                "FlashInfer 0.7.x SM121 port: the DSpark noncausal draft path "\n'
    '                "(swa_width > 128 with compress_ratio=0) is not re-plumbed for "\n'
    '                "the split sparse-table call; run without speculative decoding."\n'
    '            )\n'
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
    '        swa_topk_lens = core_attn_metadata.trtllm_swa_lens[:bs]\n'
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
    '            bmm1_scale=bmm1_scale,\n'
    '            bmm2_scale=bmm2_scale,\n'
    '            sinks=attn_sink,\n'
    '            kv_layout="HND",\n'
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
    '            backend="auto",\n'
    '            cum_seq_lens_q=cum_seq_lens_q,\n'
    '            max_q_len=max_q_len,\n'
    '        )\n'
)

patch(BACKEND, SEMAPHORE_OLD, SEMAPHORE_NEW)
patch(BACKEND, DSPARK_OLD, DSPARK_NEW)
patch(BACKEND, DECODE_CALL, DECODE_CALL_NEW)
patch(BACKEND, PREFILL_CALL, PREFILL_CALL_NEW)

text = BACKEND.read_text()
assert 'backend="trtllm-gen"' not in text, "a trtllm-gen call site survived the patch"
assert text.count("backend=\"auto\"") == 2, text.count("backend=\"auto\"")
print("patched:", BACKEND)
