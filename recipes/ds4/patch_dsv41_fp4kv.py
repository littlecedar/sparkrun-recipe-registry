#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""V4.1 KV layouts on SM12x for the DSV4 FlashMLA pool (queue row
``ds4-fp4-kv-layout-sm121-port-sglang``).

Applied to the pinned SGLang tree (``da64c5cb``, the tree inside
``dsv41-c3-reconciled:103ad321`` and its ``:0.2.1`` successors) by
``Dockerfile.dsv41-fp4kv``. Three engine-side gaps keep ``SGLANG_DSV4_KV_LAYOUT=v41``
from being usable on GB10, and this script closes exactly those:

1. **Selection gate** (``deepseek_v4_memory_pool.select_dsv4_kv_layout``): the
   V4.1 layouts are gated on capability major 10, so SM121 (major 12) silently
   falls back to V4. The layout itself is arch-neutral -- ``kv_layout.cuh``
   writes the same 528/288-byte records, and the store kernels are software
   e2m1 -- but the *reader* is not: SM100/103 reads them through
   ``sgl_kernel.flash_mla``, SM12x through FlashInfer's SM120 sparse route,
   which advertises the inline-scale records only from 0.7
   (``DSV41_INLINE_ROW_BYTES``). So the gate admits major 12 only when the
   installed reader says it can read them; a 0.6 wheel keeps V4 instead of
   raising inside the first decode.

2. **Pool sizing** (``pool_configurator.DSV4PoolConfigurator``): the SWA and
   ratio-1/2 terms are priced at the hardcoded V4 584 B/token, so a V4.1 pool
   would advertise a budget its allocation cannot back. ``kv_bytes`` becomes
   the selected layout's row width, and the ratio-1/2 compressed term the
   *compressed* layout's (V41 main + V41_FP4 for those ratios in auto mode).
   The V4 numbers are unchanged: ``KVLayout.V4.bytes_per_token`` is 584.

3. **SM120 reader wiring** (``flash_mla_sm120``): the FlashInfer call is the
   0.6-era footer-format one. For inline records it must skip the
   256->64 footer page-split and pass ``kv_scale_format="ue8m0_g32_inline"``,
   plus ``extra_fp4=True`` for a 288-byte compressed cache
   (``_sparse_mla_sm120/_api.py``). The V4 path passes no format argument and
   is byte-identical to before.

Every anchor must match exactly once and every post-condition is asserted, so a
base-tree move fails the build instead of shipping a half-patched image.
``--check`` verifies the anchors without writing.
"""

from __future__ import annotations

import os
import pathlib
import sys

ROOT = pathlib.Path(os.getenv("DSV41_FP4KV_TREE", "/sgl-workspace/sglang/python"))


def paths(root: pathlib.Path) -> dict[str, pathlib.Path]:
    """The four files this port touches, under a SGLang ``python`` root."""
    pkg = root / "sglang"
    return {
        "pool": pkg / "srt/mem_cache/deepseek_v4_memory_pool.py",
        "configurator": pkg / "srt/model_executor/pool_configurator.py",
        "flashmla": pkg / "kernels/ops/attention/flash_mla_sm120.py",
        "format": pkg / "kernels/ops/attention/dsv4/fp4kv_kv_format.py",
    }


EDITS: list[tuple[str, str, str]] = []


def edit(key: str, old: str, new: str) -> None:
    EDITS.append((key, old, new))


# --- 1. selection gate ------------------------------------------------------
edit(
    "pool",
    "def select_dsv4_kv_layout() -> Tuple[KVLayout, Optional[str]]:\n",
    '''def _sm120_inline_reader() -> bool:
    """Whether the installed FlashInfer reads the 528-byte inline V4.1 records.

    SM100/103 reads the V4.1 layouts through FlashMLA and needs no probe; on
    SM12x the reader is FlashInfer's SM120 sparse route, whose inline format
    arrives with 0.7. A 0.6 wheel has neither the format nor the argument, so
    the pool must stay V4 there rather than fail in the first decode.
    """
    try:
        from sglang.kernels.ops.attention.dsv4.fp4kv_kv_format import (
            sm120_reader_has_inline_route,
        )
    except ImportError:
        return False
    return sm120_reader_has_inline_route()


def select_dsv4_kv_layout() -> Tuple[KVLayout, Optional[str]]:
''',
)

edit(
    "pool",
    """    is_sm100 = (
        torch.cuda.is_available()
        and torch.version.cuda is not None
        and torch.cuda.get_device_capability()[0] == 10
    )
""",
    """    is_v41_arch = (
        torch.cuda.is_available()
        and torch.version.cuda is not None
        and torch.cuda.get_device_capability()[0] in (10, 12)
    )
    # SM121 (GB10) is capability 12.1: the layout is the same, but the reader
    # is FlashInfer's SM120 sparse route, so admit it only where that route
    # advertises the inline-scale records.
    if is_v41_arch and torch.cuda.get_device_capability()[0] == 12:
        is_v41_arch = _sm120_inline_reader()
""",
)

edit(
    "pool",
    """    if mode == "auto" and not is_sm100:
        return KVLayout.V4, None
    assert is_sm100, "the V4.1 KV cache layouts need an SM100 / SM103 GPU"
    return KVLayout.V41, option
""",
    """    if mode == "auto" and not is_v41_arch:
        return KVLayout.V4, None
    assert is_v41_arch, (
        "the V4.1 KV cache layouts need an SM100 / SM103 GPU, or an SM12x GPU "
        "with a FlashInfer build that reads the inline-scale records"
    )
    return KVLayout.V41, option
""",
)

# --- 2. pool sizing ---------------------------------------------------------
edit(
    "configurator",
    """        from sglang.srt.mem_cache.deepseek_v4_memory_pool import (
            dsv4_unified_row_bytes,
        )
""",
    """        from sglang.srt.mem_cache.deepseek_v4_memory_pool import (
            dsv4_unified_row_bytes,
            select_dsv4_kv_layout,
        )
""",
)

edit(
    "configurator",
    """        else:
            # One FlashMLA-layout latent slot, in bytes.
            self.kv_bytes = self.qk_nope_head_dim + self.qk_rope_head_dim * 2 + 8
""",
    """        else:
            # One FlashMLA-layout latent slot: the selected V4/V4.1 row width
            # (584 V4, 528 V41), so the SWA and ratio-1/2 terms agree with the
            # pool's allocation instead of assuming the V4 footer format.
            self.kv_bytes = select_dsv4_kv_layout()[0].bytes_per_token
""",
)

edit(
    "configurator",
    """        if ratio in (1, 2):
            return (self.kv_bytes + self.low_ratio_index_bytes) / ratio
""",
    """        if ratio in (1, 2):
            if self._unified or get_exec().kernel.dsv4_attn_backend == "trtllm":
                return (self.kv_bytes + self.low_ratio_index_bytes) / ratio
            # The ratio-1/2 caches pair with the main layout: V41 main + V41_FP4
            # for these ratios in auto mode, so price the compressed row rather
            # than the SWA row.
            from sglang.srt.mem_cache.deepseek_v4_memory_pool import (
                resolve_compressed_kv_layout,
                select_dsv4_kv_layout,
            )

            layout, option = select_dsv4_kv_layout()
            compressed = resolve_compressed_kv_layout(layout, ratio, option)
            return (compressed.bytes_per_token + self.low_ratio_index_bytes) / ratio
""",
)

# --- 3. SM120 reader wiring -------------------------------------------------
edit(
    "flashmla",
    """from sglang.srt.environ import envs
from sglang.srt.utils import is_hip
""",
    """from sglang.srt.environ import envs
from sglang.srt.utils import is_hip

from .dsv4.fp4kv_kv_format import sm120_cache_format
""",
)

edit(
    "flashmla",
    "def _gather_and_dequant(k_cache, indices, page_size):\n",
    '''def _sm120_cache_format(k_cache, extra_k_cache):
    """The (kv_scale_format, extra_fp4) pair for this call's cache widths."""
    return sm120_cache_format(
        int(k_cache.shape[-1]),
        None if extra_k_cache is None else int(extra_k_cache.shape[-1]),
    )


def _sm120_format_kwargs(kv_scale_format: str, extra_fp4: bool) -> dict:
    """Format arguments for the 0.7 inline route; empty for the V4 footer call.

    The 0.6 wheel has no such parameters, and a V4.1 selection never reaches it
    (select_dsv4_kv_layout probes the reader).
    """
    if not kv_scale_format:
        return {}
    return {"kv_scale_format": kv_scale_format, "extra_fp4": extra_fp4}


def _gather_and_dequant(k_cache, indices, page_size):
''',
)

edit(
    "flashmla",
    """    # --- Page-split: convert pbs=N kv_cache to pbs=64 view ---
    # Only the SWA pages actually referenced by `idx` are copied (the rest of
    # the persistent dst buffer is left untouched and never read).
    kv_u8 = k_cache.view(torch.uint8) if k_cache.dtype != torch.uint8 else k_cache
    src_pbs = k_cache.shape[1] if k_cache.ndim >= 3 else _PBS_SRC
    kv_64 = (
        _split_kv_pages_to_64(kv_u8, src_pbs, touched_indices=idx)
        if src_pbs != _PBS_DST
        else kv_u8
    )

    extra_kv_u8 = (
        extra_k_cache.view(torch.uint8)
        if extra_k_cache is not None and extra_k_cache.dtype != torch.uint8
        else extra_k_cache
    )
    extra_kv_64 = extra_kv_u8
""",
    """    kv_u8 = k_cache.view(torch.uint8) if k_cache.dtype != torch.uint8 else k_cache
    extra_kv_u8 = (
        extra_k_cache.view(torch.uint8)
        if extra_k_cache is not None and extra_k_cache.dtype != torch.uint8
        else extra_k_cache
    )
    kv_scale_format, extra_fp4 = _sm120_cache_format(kv_u8, extra_kv_u8)
    src_pbs = k_cache.shape[1] if k_cache.ndim >= 3 else _PBS_SRC
    if kv_scale_format:
        # Inline-scale V4.1 records are rows of the whole cache; the footer
        # page-split would rewrite them as 584-byte pages.
        kv_64 = kv_u8
    else:
        # --- Page-split: convert pbs=N kv_cache to pbs=64 view ---
        # Only the SWA pages actually referenced by `idx` are copied (the rest of
        # the persistent dst buffer is left untouched and never read).
        kv_64 = (
            _split_kv_pages_to_64(kv_u8, src_pbs, touched_indices=idx)
            if src_pbs != _PBS_DST
            else kv_u8
        )
    extra_kv_64 = extra_kv_u8
""",
)

edit(
    "flashmla",
    """        extra_topk_length=extra_topk_length,
        mid_out=mid_out,
        mid_lse=mid_lse,
    )

    return (output.unsqueeze(1), None)
""",
    """        extra_topk_length=extra_topk_length,
        mid_out=mid_out,
        mid_lse=mid_lse,
        **_sm120_format_kwargs(kv_scale_format, extra_fp4),
    )

    return (output.unsqueeze(1), None)
""",
)

# The prefill route takes the same caches above the 64-row decode envelope.
edit(
    "flashmla",
    """    kv_u8 = k_cache.view(torch.uint8) if k_cache.dtype != torch.uint8 else k_cache
    src_pbs = k_cache.shape[1] if k_cache.ndim >= 3 else _PBS_SRC
    idx = indices.squeeze(1) if indices.dim() == 3 else indices
    kv_64 = (
        _split_kv_pages_to_64(kv_u8, src_pbs, touched_indices=idx)
        if src_pbs != _PBS_DST
        else kv_u8
    )
    extra_kv_u8 = (
        extra_k_cache.view(torch.uint8)
        if extra_k_cache is not None and extra_k_cache.dtype != torch.uint8
        else extra_k_cache
    )
""",
    """    kv_u8 = k_cache.view(torch.uint8) if k_cache.dtype != torch.uint8 else k_cache
    src_pbs = k_cache.shape[1] if k_cache.ndim >= 3 else _PBS_SRC
    idx = indices.squeeze(1) if indices.dim() == 3 else indices
    extra_kv_u8 = (
        extra_k_cache.view(torch.uint8)
        if extra_k_cache is not None and extra_k_cache.dtype != torch.uint8
        else extra_k_cache
    )
    kv_scale_format, extra_fp4 = _sm120_cache_format(kv_u8, extra_kv_u8)
    if kv_scale_format:
        # Inline-scale V4.1 records are rows of the whole cache; the footer
        # page-split would rewrite them as 584-byte pages.
        kv_64 = kv_u8
    else:
        kv_64 = (
            _split_kv_pages_to_64(kv_u8, src_pbs, touched_indices=idx)
            if src_pbs != _PBS_DST
            else kv_u8
        )
""",
)

edit(
    "flashmla",
    """    if extra_kv_u8 is not None and extra_kv_u8.shape[1] != _PBS_DST:
""",
    """    if (
        not kv_scale_format
        and extra_kv_u8 is not None
        and extra_kv_u8.shape[1] != _PBS_DST
    ):
""",
)

edit(
    "flashmla",
    """        extra_topk_length=extra_topk_length,
        mid_out=None,
        mid_lse=None,
    )
    return (output.unsqueeze(1), None)
""",
    """        extra_topk_length=extra_topk_length,
        mid_out=None,
        mid_lse=None,
        **_sm120_format_kwargs(kv_scale_format, extra_fp4),
    )
    return (output.unsqueeze(1), None)
""",
)

# The Triton and PyTorch fallbacks read the V4 footer rows only; refuse a V4.1
# cache there instead of dequantizing the wrong stride.
edit(
    "flashmla",
    """    extra_k_cache = kwargs.get("extra_k_cache")
    extra_indices = kwargs.get("extra_indices_in_kvcache")
    extra_topk_length = kwargs.get("extra_topk_length")

    if _sm120_default_backend == "flashinfer":
""",
    """    extra_k_cache = kwargs.get("extra_k_cache")
    extra_indices = kwargs.get("extra_indices_in_kvcache")
    extra_topk_length = kwargs.get("extra_topk_length")

    kv_scale_format, _ = _sm120_cache_format(k_cache, extra_k_cache)
    if kv_scale_format and _sm120_default_backend != "flashinfer":
        raise ValueError(
            f"SGLANG_SM120_FLASHMLA_BACKEND={_sm120_default_backend} reads the "
            "584-byte V4 footer cache only; the V4.1 inline layouts need the "
            "flashinfer backend"
        )

    if _sm120_default_backend == "flashinfer":
""",
)


def apply(root: pathlib.Path = ROOT, check_only: bool = False) -> None:
    files = paths(root)
    for key, old, new in EDITS:
        path = files[key]
        text = path.read_text()
        count = text.count(old)
        if count != 1:
            raise SystemExit(f"{path}: anchor found {count} times, expected 1:\n{old[:200]}")
        if not check_only:
            path.write_text(text.replace(old, new, 1))


POST = {
    "pool": [
        "def _sm120_inline_reader() -> bool:",
        "capability()[0] in (10, 12)",
        "is_v41_arch = _sm120_inline_reader()",
        "with a FlashInfer build that reads the inline-scale records",
    ],
    "configurator": [
        "select_dsv4_kv_layout,\n        )",
        "self.kv_bytes = select_dsv4_kv_layout()[0].bytes_per_token",
        "compressed = resolve_compressed_kv_layout(layout, ratio, option)",
    ],
    "flashmla": [
        "from .dsv4.fp4kv_kv_format import sm120_cache_format",
        "def _sm120_cache_format(k_cache, extra_k_cache):",
        "def _sm120_format_kwargs(kv_scale_format: str, extra_fp4: bool) -> dict:",
        "kv_scale_format, extra_fp4 = _sm120_cache_format(kv_u8, extra_kv_u8)",
        "**_sm120_format_kwargs(kv_scale_format, extra_fp4),",
        "the V4.1 inline layouts need the ",
    ],
}

FORBIDDEN = {
    "pool": ["capability()[0] == 10", "is_sm100"],
    "configurator": ["self.kv_bytes = self.qk_nope_head_dim + self.qk_rope_head_dim * 2 + 8"],
    "flashmla": [],
}


def verify(root: pathlib.Path = ROOT) -> None:
    files = paths(root)
    if not files["format"].is_file():
        raise SystemExit(
            f"{files['format']} is missing; copy fp4kv_kv_format.py beside the dsv4 "
            "kernels before patching"
        )
    for key, needles in POST.items():
        path = files[key]
        text = path.read_text()
        for needle in needles:
            if needle not in text:
                raise SystemExit(f"{path}: post-condition missing: {needle!r}")
    for key, needles in FORBIDDEN.items():
        path = files[key]
        text = path.read_text()
        for needle in needles:
            if needle in text:
                raise SystemExit(f"{path}: patched text still contains {needle!r}")


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    apply(ROOT, check_only=check_only)
    if not check_only:
        verify(ROOT)
        print(f"patched {len(EDITS)} anchors under {ROOT}")
    else:
        print(f"{len(EDITS)} anchors present once under {ROOT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
