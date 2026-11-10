#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Move ERNIE 5.5 Flash's sparse-MLA layers onto FlashInfer's SM121 kernel.

FlashMLA's sparse decode has no SM12x build and cannot be given one cheaply:
`is_sm100f()` gates on `major == 10` (csrc_legacy/api/common.h:94-96 at
FlashMLA@46b6727a, raise at csrc_legacy/api/sparse_decode.cpp:386) and the
SM100 kernel asserts a 227 KiB shared-memory plan against GB10's 101,376 B
opt-in. FlashInfer 0.7.3 in this image ships the same DSv3.2/GLM sparse kernel
for `[120, 121]`, reads the same 656 B/token packed DSA cache, and takes the
same per-row length and per-head sink.

Five sites, all in the installed tree (pinned image, upstream sglang main
4a5c6b8f):

1. ernie55_backend.py  -- select `flashinfer_sparse_mla` on SM12x. ERNIE pins
   `flashmla_sparse` *after* `super().__init__()`, so no `--dsa-*` flag can
   reach it.
2. dsa_backend.py      -- let the sink gate admit `flashinfer_sparse_mla`
   (two sites: forward_extend, forward_decode). FlashInfer's route carries the
   identical FlashMLA V4 sink, so the gate's reason ("sinks are only wired
   into flashmla_sparse") stops holding on SM12x.
3. flash_mla_sm120.py  -- admit ERNIE to the SM12x sparse whitelist, which is
   what allocates the backend's sparse workspace; ERNIE's backend switches
   impl after its own `super().__init__()`, so the allocation has to happen
   while it still reads `flashmla_sparse`.
4. flash_mla_sm120.py  -- plumb the sink into `flashinfer_sparse_mla_forward`,
   and dsa_backend.py -- pass it from the two call sites.
5. ernie55_backend.py  -- the semantic site: override
   `_forward_flashinfer_sparse_mla` so the kernel receives the `top-k + last
   window` page set and its per-row length. The append lives only in
   `_forward_flashmla_sparse`; an impl switch without it drops the trailing
   `window` tokens and answers with wrong logits and no error. The override
   calls the engine's own `append_window_to_topk` -- the same call the
   FlashMLA route makes -- and hands the result to the FlashInfer route.

Fail-closed: every anchor below must match exactly once (or already carry its
marker). One miss aborts the launch and writes nothing, because a partial
apply boots into wrong logits rather than an error.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from typing import NoReturn

# --- 1 + 5: ernie55_backend.py ------------------------------------------------

MARKER_IMPL = "sparkrun: SM12x runs FlashInfer's sparse-MLA kernel"
MARKER_APPEND = "sparkrun: FlashInfer SM121 sparse-MLA route"

OLD_IMPL = (
    "        # Learnable sinks are only wired into flashmla_sparse.\n"
    '        self.dsa_prefill_impl = "flashmla_sparse"\n'
    '        self.dsa_decode_impl = "flashmla_sparse"\n'
)
NEW_IMPL = (
    "        # sparkrun: SM12x runs FlashInfer's sparse-MLA kernel\n"
    "        # FlashMLA's sparse decode has no SM12x build (arch gate in\n"
    "        # csrc_legacy/api/common.h, plus a 227 KiB shared-memory plan\n"
    "        # against GB10's 99 KiB opt-in); FlashInfer's SM120/121 kernel\n"
    "        # takes the same packed 656 B cache, per-row length and sink.\n"
    "        # SM100/SM103 keep the upstream pin byte for byte.\n"
    "        if (\n"
    "            self.device_sm_major == 12\n"
    "            and self.kv_cache_dtype == torch.float8_e4m3fn\n"
    "        ):\n"
    '            self.dsa_prefill_impl = "flashinfer_sparse_mla"\n'
    '            self.dsa_decode_impl = "flashinfer_sparse_mla"\n'
    "        else:\n"
    "            # Learnable sinks are only wired into flashmla_sparse.\n"
    '            self.dsa_prefill_impl = "flashmla_sparse"\n'
    '            self.dsa_decode_impl = "flashmla_sparse"\n'
)

# The class this override is attached to must exist exactly once: the append
# itself is position-independent, but it is meaningless against a renamed class.
CLASS_ANCHOR = "class Ernie5_5MlaAttnBackend(DeepseekSparseAttnBackend):\n"

APPENDED = '''

# --- sparkrun: FlashInfer SM121 sparse-MLA route ----------------------------
# FlashMLA's sparse decode refuses SM12x twice over (arch gate in
# csrc_legacy/api/common.h, and a 227 KiB shared-memory plan against GB10's
# 99 KiB opt-in). FlashInfer's SM120/121 sparse kernel consumes the same
# packed 656 B/token DSA cache and documents the same learnable-sink contract
# (`lse' = log(exp(lse) + exp(sink))`). What stays here is everything that
# decides the answer: the `top-k + last window` page set, its per-row length,
# and the per-head sink. Only the call that reads them moves.
def _sparkrun_forward_flashinfer_sparse_mla(
    self,
    q_all: torch.Tensor,
    kv_cache: torch.Tensor,
    page_table_1: torch.Tensor,
    seq_lens: torch.Tensor,
    sm_scale: float,
    skip_softmax_threshold_scale_factor: Optional[float],
    attn_sink: Optional[torch.Tensor] = None,
) -> torch.Tensor:
    from sglang.kernels.ops.attention.dsa.append_window_to_topk import (
        append_window_to_topk,
    )
    from sglang.kernels.ops.attention.flash_mla_sm120 import (
        flashinfer_sparse_mla_forward,
    )

    if attn_sink is None:
        # Every ERNIE 5.5 Flash MLA layer carries a learnable sink. A call
        # without one means the sink was dropped between the layer and here.
        raise RuntimeError("ERNIE 5.5 Flash MLA layers always carry a sink")
    metadata = self.forward_metadata
    num_rows = q_all.shape[0]
    # The same call the flashmla_sparse route makes: append the trailing
    # `window` slots to the indexer's top-k and return each row's live count.
    # Dropping this is the silent-wrong-logits failure the port exists for.
    page_table_1, topk_length = append_window_to_topk(
        page_table_1[:num_rows].to(torch.int32),
        metadata.dsa_seqlens_expanded,
        metadata.real_page_table,
        window=self.window,
        page_size=metadata.page_size,
        alignment=SPARSE_PREFILL_TOPK_ALIGNMENT,
        page_rows=metadata.token_to_batch_idx,
        ragged_offsets=metadata.topk_indices_offset,
    )
    # `seq_lens` is metadata's cache length, not the kernel's: the sparse
    # SM120 route takes the appended per-row count instead, exactly as the
    # FlashMLA route does. The top-k width comes from the appended table, so
    # no row's window rows are clamped off.
    del seq_lens
    return flashinfer_sparse_mla_forward(
        q=q_all,
        kv_cache=kv_cache,
        indices=page_table_1,
        seq_lens=topk_length,
        workspace_buffer=self.workspace_buffer,
        page_size=self.physical_page_size,
        kv_cache_dim=self.kv_cache_dim,
        qk_nope_head_dim=self.qk_nope_head_dim,
        kv_lora_rank=self.kv_lora_rank,
        qk_rope_head_dim=self.qk_rope_head_dim,
        sm_scale=sm_scale,
        skip_softmax_threshold_scale_factor=skip_softmax_threshold_scale_factor,
        attn_sink=attn_sink,
    )


Ernie5_5MlaAttnBackend._forward_flashinfer_sparse_mla = (
    _sparkrun_forward_flashinfer_sparse_mla
)
'''

# --- 2: dsa_backend.py --------------------------------------------------------

MARKER_GATE = "sparkrun: flashinfer_sparse_mla carries the same sink"
MARKER_CALL = "sparkrun: hand the sink to the FlashInfer route"

OLD_GATE = (
    '        if attn_sink is not None and dsa_impl != "flashmla_sparse":\n'
    "            raise RuntimeError(\n"
    '                f"Learnable attention sinks require flashmla_sparse, got'
    ' {dsa_impl}"\n'
    "            )\n"
)
NEW_GATE = (
    "        # sparkrun: flashinfer_sparse_mla carries the same sink\n"
    "        # FlashInfer's sparse route documents FlashMLA's V4 convention\n"
    "        # (`lse' = log(exp(lse) + exp(sink))`), so on SM12x it takes one.\n"
    "        if attn_sink is not None and dsa_impl not in (\n"
    '            "flashmla_sparse",\n'
    '            "flashinfer_sparse_mla",\n'
    "        ):\n"
    "            raise RuntimeError(\n"
    '                f"Learnable attention sinks require flashmla_sparse, got'
    ' {dsa_impl}"\n'
    "            )\n"
)

CALL_HEAD = (
    "            return self._forward_flashinfer_sparse_mla(\n"
    "                q_all=q_all,\n"
    "                kv_cache=kv_cache,\n"
    "                page_table_1=page_table_1,\n"
    "                seq_lens=metadata.dsa_cache_seqlens_int32,\n"
    "                sm_scale=layer.scaling,\n"
    "                skip_softmax_threshold_scale_factor=envs.%s.get(),\n"
    "            )\n"
)
CALL_BODY = (
    "            # sparkrun: hand the sink to the FlashInfer route\n"
    "            return self._forward_flashinfer_sparse_mla(\n"
    "                q_all=q_all,\n"
    "                kv_cache=kv_cache,\n"
    "                page_table_1=page_table_1,\n"
    "                seq_lens=metadata.dsa_cache_seqlens_int32,\n"
    "                sm_scale=layer.scaling,\n"
    "                skip_softmax_threshold_scale_factor=envs.%s.get(),\n"
    "                attn_sink=attn_sink,\n"
    "            )\n"
)
CALL_ENVS = (
    "SGLANG_SKIP_SOFTMAX_PREFILL_THRESHOLD_SCALE_FACTOR",
    "SGLANG_SKIP_SOFTMAX_DECODE_THRESHOLD_SCALE_FACTOR",
)

# --- 3: flash_mla_sm120.py ----------------------------------------------------

MARKER_WHITELIST = "sparkrun: ERNIE 5.5 Flash serves the same packed DSA cache"
MARKER_SINK = "sparkrun: optional FlashMLA V4 sink"

OLD_WHITELIST = "    if uses_flashinfer_sparse_mla and not is_glm_sm12_fp8:\n"
NEW_WHITELIST = (
    "    # sparkrun: ERNIE 5.5 Flash serves the same packed DSA cache\n"
    "    # Its MLA sub-backend switches to this impl right after its own\n"
    "    # super().__init__(), so admit it here to allocate the sparse\n"
    "    # workspace -- otherwise the first decode calls into a None buffer.\n"
    "    is_ernie_sm12_fp8 = (\n"
    '        model_arch == "Ernie5_5_MoeForCausalLM"\n'
    "        and device_sm_major == 12\n"
    "        and kv_cache_dtype == torch.float8_e4m3fn\n"
    "        and not _is_hip\n"
    "    )\n"
    "    if is_ernie_sm12_fp8:\n"
    "        return True\n"
    + OLD_WHITELIST
)

# --- 4: flash_mla_sm120.py ----------------------------------------------------

OLD_SIG = (
    "    skip_softmax_threshold_scale_factor: float | None,\n"
    ") -> torch.Tensor:\n"
)
NEW_SIG = (
    "    skip_softmax_threshold_scale_factor: float | None,\n"
    "    # sparkrun: optional FlashMLA V4 sink, shape (num_heads,) float32\n"
    "    attn_sink: torch.Tensor | None = None,\n"
    ") -> torch.Tensor:\n"
)
OLD_DISPATCH = (
    '        kv_scale_format="arbitrary_fp32",\n'
    "        skip_softmax_threshold_scale_factor="
    "skip_softmax_threshold_scale_factor,\n"
    "    )\n"
)
NEW_DISPATCH = (
    '        kv_scale_format="arbitrary_fp32",\n'
    "        skip_softmax_threshold_scale_factor="
    "skip_softmax_threshold_scale_factor,\n"
    "        sinks=attn_sink,\n"
    "    )\n"
)


def die(msg: str) -> NoReturn:
    print(f"apply-ernie55-flashinfer-sparse-patch: ERROR: {msg}")
    sys.exit(1)


def locate(module: str) -> str:
    """Resolve a module of the installed sglang, not a hardcoded path."""
    spec = importlib.util.find_spec(module)
    if spec is None or not spec.origin:
        die(
            f"cannot import {module}; is sglang installed and importable in "
            "this container?"
        )
    if not os.path.isfile(spec.origin):
        die(f"{module} resolved to a non-file path: {spec.origin}")
    return os.path.realpath(spec.origin)


def replace_once(text: str, old: str, new: str, name: str, path: str) -> str:
    count = text.count(old)
    if count != 1:
        die(
            f"[{name}] anchor found {count} time(s) in {path}; refusing to "
            "launch. The pinned image's source moved -- re-read the site "
            "against recipes/explore/mods/ernie55-flashinfer-sparse-sglang/"
            "README.md before adapting."
        )
    return text.replace(old, new)


def patch_ernie(path: str, src: str) -> str:
    if MARKER_IMPL in src and MARKER_APPEND in src:
        print("[site1+5] already patched; skipping")
        return src
    if MARKER_IMPL in src or MARKER_APPEND in src:
        die(
            f"half-patched {path}: one of site 1 / site 5 landed without the "
            "other. That is exactly the silent-wrong-logits state; refusing "
            "to launch."
        )
    src = replace_once(src, OLD_IMPL, NEW_IMPL, "site1-impl-select", path)
    count = src.count(CLASS_ANCHOR)
    if count != 1:
        die(
            f"[site5-window-append] class anchor found {count} time(s) in "
            f"{path}; the ERNIE backend was renamed or merged. Refusing."
        )
    src = src.rstrip("\n") + "\n" + APPENDED
    return src


def patch_dsa(path: str, src: str) -> str:
    if MARKER_GATE in src and MARKER_CALL in src:
        print("[site2+4] already patched; skipping")
        return src
    if MARKER_GATE in src or MARKER_CALL in src:
        die(f"half-patched {path}: sink gate or call-site plumbing is missing")
    if src.count(OLD_GATE) != 2:
        die(
            f"[site2-sink-gate] expected 2 sink gates, found "
            f"{src.count(OLD_GATE)} in {path}. Refusing."
        )
    src = src.replace(OLD_GATE, NEW_GATE)
    for env_name in CALL_ENVS:
        old = CALL_HEAD % env_name
        new = CALL_BODY % env_name
        src = replace_once(src, old, new, f"site4-call-{env_name}", path)
    return src


def patch_flash_mla(path: str, src: str) -> str:
    if MARKER_WHITELIST in src and MARKER_SINK in src:
        print("[site3+4] already patched; skipping")
        return src
    if MARKER_WHITELIST in src or MARKER_SINK in src:
        die(f"half-patched {path}: whitelist or sink plumbing is missing")
    src = replace_once(src, OLD_WHITELIST, NEW_WHITELIST, "site3-whitelist", path)
    src = replace_once(src, OLD_SIG, NEW_SIG, "site4-signature", path)
    src = replace_once(src, OLD_DISPATCH, NEW_DISPATCH, "site4-sink", path)
    return src


TARGETS = (
    ("sglang.srt.layers.attention.ernie55_backend", patch_ernie),
    ("sglang.srt.layers.attention.dsa_backend", patch_dsa),
    ("sglang.kernels.ops.attention.flash_mla_sm120", patch_flash_mla),
)


def main() -> int:
    staged: list[tuple[str, str]] = []
    for module, patcher in TARGETS:
        path = locate(module)
        print(f"target: {module} -> {path}")
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        patched = patcher(path, src)
        if patched == src:
            continue
        try:
            # Never let a bad substitution land on disk, even transiently.
            compile(patched, path, "exec")
        except SyntaxError as exc:
            die(f"{path} would not compile after patching: {exc}")
        staged.append((path, patched))

    if not staged:
        print("nothing to write: every site already carries its marker")
        return 0
    # Write only once every target is clean, so a miss on the third file
    # cannot leave the first two half-ported.
    for path, patched in staged:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(patched)
        print(f"patched: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
