#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Acceptance rung (i) for the ERNIE sparse-MLA port: imports and the envelope.

No GPU, no weights, no boot. This runs at every launch, after the patch, and
fails the launch when the port is not in the state the boot will assume:

* the three patched modules are importable and carry the patched behaviour
  (not just the marker text -- the class attribute is checked, the whitelist is
  called with ERNIE's arguments, and the sink parameter is in the signature);
* FlashInfer ships the SM120/121 sparse-MLA kernel this route calls, at the
  version floor that has it;
* the kernel envelope admits ERNIE's served shape on GB10.

The envelope is FlashInfer's own static, GPU-less table
(`supported_sparse_mla_sm120_configs`), so this prediction needs no device.
Rung (ii), the boot to `Ready` past CUDA-graph capture, and rung (iii)-(iv),
the quality cell and the window falsifier, need the quartet; see the mod's
README for those.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import os
import re
import sys
from typing import NoReturn

# ERNIE 5.5 Flash served shape, from the pinned checkpoint's config.json:
# hybrid_mla_num_attention_heads 64 across TP=4 = 16 query heads per rank,
# index_topk 2048, sliding_window 128. The appended page set is
# ceil_align(2048 + 128, 128) = 2176 wide (SPARSE_PREFILL_TOPK_ALIGNMENT).
INDEX_TOPK = 2048
WINDOW = 128
ALIGNMENT = 128
PAGE_BLOCK_SIZE = 64
D_QK = 576  # 512 latent + 64 rope
BYTES_PER_TOKEN = 656
FLASHINFER_MIN = (0, 7, 0)
TP_HEADS = (8, 16, 32, 64)  # TP=8, 4, 2, 1

MARKERS = {
    "sglang.srt.layers.attention.ernie55_backend": (
        "sparkrun: SM12x runs FlashInfer's sparse-MLA kernel",
        "sparkrun: FlashInfer SM121 sparse-MLA route",
    ),
    "sglang.srt.layers.attention.dsa_backend": (
        "sparkrun: flashinfer_sparse_mla carries the same sink",
        "sparkrun: hand the sink to the FlashInfer route",
    ),
    "sglang.kernels.ops.attention.flash_mla_sm120": (
        "sparkrun: ERNIE 5.5 Flash serves the same packed DSA cache",
        "sparkrun: optional FlashMLA V4 sink",
    ),
}


def die(msg: str) -> NoReturn:
    print(f"verify-ernie55-flashinfer-sparse: ERROR: {msg}")
    sys.exit(1)


def module_source(module: str) -> str:
    spec = importlib.util.find_spec(module)
    if spec is None or not spec.origin:
        die(f"cannot locate {module}")
    with open(spec.origin, encoding="utf-8") as fh:
        return fh.read()


def check_markers() -> None:
    for module, markers in MARKERS.items():
        src = module_source(module)
        for marker in markers:
            if marker not in src:
                die(f"{module} is missing its patch marker {marker!r}")
        print(f"patch markers ok: {module}")


def version_tuple(text: str) -> tuple[int, ...]:
    found = re.match(r"(\d+)\.(\d+)\.(\d+)", text)
    if not found:
        die(f"cannot parse FlashInfer version {text!r}")
    return tuple(int(part) for part in found.groups())


def check_flashinfer() -> None:
    import flashinfer

    version = getattr(flashinfer, "__version__", "")
    if version_tuple(version) < FLASHINFER_MIN:
        die(f"FlashInfer {version} predates {FLASHINFER_MIN}: no SM120 sparse MLA")
    print(f"flashinfer {version}")

    configs = flashinfer.mla.supported_sparse_mla_sm120_configs()
    # kv_scale_format="arbitrary_fp32" at d_qk 576 selects GLM_NSA; ERNIE's
    # pool writes arbitrary amax/448 fp32 tile scales (kv_scale_ue8m0 is only
    # set for Kimi), so that is the family this route runs. Upstream keeps it
    # equal to dsv3_2 -- same kernel, ABI and constants.
    for family in ("glm_nsa", "dsv3_2"):
        if family not in configs:
            die(f"FlashInfer {version} has no {family} sparse-MLA config")
        config = configs[family]
        if (
            config.d_qk != D_QK
            or config.bytes_per_token != BYTES_PER_TOKEN
            or config.max_num_tokens < 1
        ):
            die(
                f"{family}: d_qk {config.d_qk}, {config.bytes_per_token} B/token "
                f"-- expected {D_QK} and {BYTES_PER_TOKEN}"
            )

    decoded = configs["glm_nsa"]
    topk_width = -(-(INDEX_TOPK + WINDOW) // ALIGNMENT) * ALIGNMENT
    if topk_width % 64:
        # FlashInfer's ordinary prefill requires topk % 64 == 0.
        die(f"appended top-k width {topk_width} is not a multiple of 64")
    admitted = []
    for heads in TP_HEADS:
        ok = decoded.supports_decode(
            num_heads=heads,
            topk=topk_width,
            page_block_size=PAGE_BLOCK_SIZE,
        )
        admitted.append(f"{heads}h{'ok' if ok else 'NO'}")
        if not ok:
            die(
                f"glm_nsa does not admit {heads} heads at topk {topk_width}, "
                f"page {PAGE_BLOCK_SIZE}"
            )
    print(
        f"envelope ok: glm_nsa d_qk {decoded.d_qk}, {decoded.bytes_per_token} B/token, "
        f"decode <= {decoded.max_num_tokens} tokens, topk {topk_width}, "
        f"page {PAGE_BLOCK_SIZE} ({', '.join(admitted)})"
    )


def check_patched_behaviour() -> None:
    backend = importlib.import_module("sglang.srt.layers.attention.ernie55_backend")
    override = backend.Ernie5_5MlaAttnBackend._forward_flashinfer_sparse_mla
    if override.__name__ != "_sparkrun_forward_flashinfer_sparse_mla":
        die("Ernie5_5MlaAttnBackend does not carry the window-append override")

    sm120 = importlib.import_module(
        "sglang.kernels.ops.attention.flash_mla_sm120"
    )
    params = inspect.signature(sm120.flashinfer_sparse_mla_forward).parameters
    if "attn_sink" not in params:
        die("flashinfer_sparse_mla_forward does not take attn_sink")

    import torch

    admitted = sm120._validate_flashinfer_sparse_mla_backend(
        model_arch="Ernie5_5_MoeForCausalLM",
        device_sm_major=12,
        kv_cache_dtype=torch.float8_e4m3fn,
        # The value ERNIE's __init__ still holds while super().__init__ runs:
        # the allocation this gate controls has to happen there.
        prefill_impl="flashmla_sparse",
        decode_impl="flashmla_sparse",
    )
    if not admitted:
        die("the SM12x sparse whitelist does not allocate ERNIE's workspace")
    print("patched behaviour ok: override bound, sink plumbed, workspace admitted")


def report_device() -> None:
    import torch

    if not torch.cuda.is_available():
        print("device: no CUDA visible to this process (mod ran without a GPU)")
        return
    major, minor = torch.cuda.get_device_capability()
    print(f"device: sm_{major}{minor} {torch.cuda.get_device_name()}")
    if (major, minor) != (12, 1):
        # Not fatal: the shim is keyed on major == 12, and a different board
        # changes the record, not the patch.
        print("note: this is not the GB10 target; the route still gates on sm_12x")


def main() -> int:
    # Before any sglang import: FlashInfer must not build a kernel on the way
    # to a pure-Python capability table.
    os.environ.setdefault("FLASHINFER_DISABLE_JIT", "1")
    check_markers()
    check_patched_behaviour()
    check_flashinfer()
    report_device()
    print("rung (i) ok: import + envelope")
    return 0


if __name__ == "__main__":
    sys.exit(main())
