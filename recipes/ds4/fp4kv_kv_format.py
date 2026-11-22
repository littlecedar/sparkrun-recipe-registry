# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""SM120 sparse-MLA cache formats for the DeepSeek-V4.1 KV layouts.

The FlashMLA pool writes one of three row formats (``kv_layout.cuh``): ``V4``
(584 B, footer scales: 448 fp8 nope + 64 bf16 rope), ``V41`` (528 B inline
records: 512 fp8 + 16 UE8M0 group-32 scales) and ``V41_FP4`` (288 B inline
records: 512 e2m1 packed + 32 e4m3 group-16 scales; compressed caches only).

FlashInfer's SM120 sparse route reads ``V4`` with no format argument -- the
0.6-era call SGLang makes today. The V4.1 formats reach it only through the 0.7
route: ``kv_scale_format="ue8m0_g32"`` for a 528-byte main cache (the footer
page the tree writes), and ``extra_fp4=True`` for a 288-byte compressed cache
(``flashinfer/mla/_sparse_mla_sm120/_api.py``: the flag requires a DSV4_1 main
cache and checks the extra cache at 288 instead of 528).

Do not use ``ue8m0_g32_inline`` here: that family expects each token's data and
scales interleaved as one 528-byte row, while ``quantize_k_cache_v41`` writes a
footer page (all data, then all scales). Measured on a GB10 2026-11-22: the
inline name reads a footer page as zeros; the footer name matches the oracle at
rel_err 0.026.

This module is copied into the pinned SGLang tree by
``Dockerfile.dsv41-fp4kv``; the patched ``flash_mla_sm120.py`` calls it so the
decision is testable without a GPU or the tree.
"""

from __future__ import annotations

V4_ROW_BYTES = 584
V41_ROW_BYTES = 528
V41_FP4_ROW_BYTES = 288

# FlashInfer's name for the 528-byte footer-scale record format. The tree's
# ``V41`` page is a footer page: ``page_size * 512`` data bytes, then
# ``page_size * 16`` UE8M0 scale bytes (``torch_quant.quantize_k_cache_v41``).
# FlashInfer's ``dsv4_1_inline`` family is the *other* arrangement -- each
# token's data followed by its own scales -- and reads zeros from a footer page.
V41_SCALE_FORMAT = "ue8m0_g32"


def sm120_cache_format(main_bytes: int, extra_bytes: int | None = None) -> tuple[str, bool]:
    """``(kv_scale_format, extra_fp4)`` for one SM120 sparse-MLA call.

    ``kv_scale_format`` is empty for the V4 footer format: the caller then makes
    the 0.6-era call with no format argument, which is what the shipped
    FlashInfer 0.6 wheel accepts.

    Raises for a pair the decode kernel cannot read, so a wrong layout is a
    failed call rather than tokens read out of the wrong stride.
    """
    main_bytes = int(main_bytes)
    if extra_bytes is not None:
        extra_bytes = int(extra_bytes)

    if main_bytes == V4_ROW_BYTES:
        # The V4 main cache only pairs with V4 caches
        # (resolve_compressed_kv_layout asserts the same).
        if extra_bytes not in (None, V4_ROW_BYTES):
            raise ValueError(
                "the V4 footer cache cannot be paired with a "
                f"{extra_bytes}-byte extra cache"
            )
        return "", False

    if main_bytes == V41_ROW_BYTES:
        if extra_bytes is None or extra_bytes == V41_ROW_BYTES:
            return V41_SCALE_FORMAT, False
        if extra_bytes == V41_FP4_ROW_BYTES:
            return V41_SCALE_FORMAT, True
        raise ValueError(
            f"the 528-byte V4.1 main cache cannot be paired with a "
            f"{extra_bytes}-byte extra cache"
        )

    raise ValueError(
        f"no SM120 sparse-MLA format for a {main_bytes}-byte main cache; "
        "expected 584 (V4) or 528 (V41)"
    )


def sm120_reader_has_v41_route() -> bool:
    """Whether the installed FlashInfer carries the V4.1 (footer-scale) route.

    Probed, not version-parsed: 0.7 exposes ``DSV41_INLINE_ROW_BYTES`` (the
    528-byte row width) beside the format resolution; a 0.6 wheel has neither,
    so a V4.1 selection on SM12x is refused at pool construction instead of
    writing nothing inside the first decode.
    """
    try:
        from flashinfer.mla._sparse_mla_sm120 import _execution
    except Exception:
        return False
    return int(getattr(_execution, "DSV41_INLINE_ROW_BYTES", 0)) == V41_ROW_BYTES
