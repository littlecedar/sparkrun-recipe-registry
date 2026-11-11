#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Guard the anchor-drift behaviour of the ERNIE FlashInfer sparse-MLA mod.

The mod moves six MLA layers onto another kernel, and the failure mode it
exists to prevent is silent: a port that drops the trailing window, the
per-row length or the sink boots clean, captures CUDA graphs, serves, and
answers wrongly. So every site is an anchor that must match exactly once, a
miss must abort the launch, and a partial apply must write *nothing* -- half
a port is the wrong-logits state, not a smaller patch.

These tests drive the real script as a subprocess against a fake sglang
package on `PYTHONPATH`, one fixture per target module. The negative controls
are the point: each removes exactly one anchor and asserts the refusal, plus
that the other modules were left untouched.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = (
    REPO_ROOT
    / "recipes"
    / "explore"
    / "mods"
    / "ernie55-flashinfer-sparse-sglang"
    / "apply-ernie55-flashinfer-sparse-patch.py"
)

ERNIE_MODULE = '''\
import torch

SPARSE_PREFILL_TOPK_ALIGNMENT = 128


class DeepseekSparseAttnBackend:
    def __init__(self, model_runner, **kwargs):
        self.device_sm_major = 12
        self.kv_cache_dtype = torch.float8_e4m3fn


class Ernie5_5MlaAttnBackend(DeepseekSparseAttnBackend):
    def __init__(self, model_runner, *, window, **kwargs):
        self.window = window
        super().__init__(model_runner, **kwargs)
        # Learnable sinks are only wired into flashmla_sparse.
        self.dsa_prefill_impl = "flashmla_sparse"
        self.dsa_decode_impl = "flashmla_sparse"
        self.enable_auto_select_prefill_impl = False
'''

GATE = '''\
        if attn_sink is not None and dsa_impl != "flashmla_sparse":
            raise RuntimeError(
                f"Learnable attention sinks require flashmla_sparse, got {dsa_impl}"
            )
'''

CALL = '''\
        if True:
            return self._forward_flashinfer_sparse_mla(
                q_all=q_all,
                kv_cache=kv_cache,
                page_table_1=page_table_1,
                seq_lens=metadata.dsa_cache_seqlens_int32,
                sm_scale=layer.scaling,
                skip_softmax_threshold_scale_factor=envs.{env}.get(),
            )
'''

DSA_MODULE = (
    "class DeepseekSparseAttnBackend:\n"
    "    def forward_extend(self, attn_sink, dsa_impl, metadata, layer, q_all,"
    " kv_cache, page_table_1, envs):\n"
    + GATE
    + CALL.format(env="SGLANG_SKIP_SOFTMAX_PREFILL_THRESHOLD_SCALE_FACTOR")
    + "\n"
    "    def forward_decode(self, attn_sink, dsa_impl, metadata, layer, q_all,"
    " kv_cache, page_table_1, envs):\n"
    + GATE
    + CALL.format(env="SGLANG_SKIP_SOFTMAX_DECODE_THRESHOLD_SCALE_FACTOR")
)

FLASH_MLA_MODULE = '''\
import torch

_GLM_DSA_MODEL_ARCHS = ("GlmMoeDsaForCausalLM",)
_is_hip = False


def _validate_flashinfer_sparse_mla_backend(
    *,
    model_arch: str,
    device_sm_major: int,
    kv_cache_dtype: torch.dtype,
    prefill_impl: str,
    decode_impl: str,
) -> bool:
    selected = {prefill_impl, decode_impl}
    uses_flashinfer_sparse_mla = "flashinfer_sparse_mla" in selected
    is_glm_sm12_fp8 = (
        model_arch in _GLM_DSA_MODEL_ARCHS
        and device_sm_major == 12
        and kv_cache_dtype == torch.float8_e4m3fn
        and not _is_hip
    )
    if uses_flashinfer_sparse_mla and not is_glm_sm12_fp8:
        raise ValueError("flashinfer_sparse_mla supports only GLM")
    return uses_flashinfer_sparse_mla


def flashinfer_sparse_mla_forward(
    q: torch.Tensor,
    kv_cache: torch.Tensor,
    indices: torch.Tensor,
    seq_lens: torch.Tensor,
    workspace_buffer: torch.Tensor,
    *,
    page_size: int,
    kv_cache_dim: int,
    qk_nope_head_dim: int,
    kv_lora_rank: int,
    qk_rope_head_dim: int,
    sm_scale: float,
    skip_softmax_threshold_scale_factor: float | None,
) -> torch.Tensor:
    """Run FlashInfer's SM120 sparse MLA kernel on SGLang's packed DSA cache."""
    topk = indices.shape[1]
    result = _dispatch(
        query=q.unsqueeze(1),
        sparse_mla_top_k=topk,
        kv_scale_format="arbitrary_fp32",
        skip_softmax_threshold_scale_factor=skip_softmax_threshold_scale_factor,
    )
    return result.squeeze(1)
'''

MARKERS = {
    "ernie": (
        "sparkrun: SM12x runs FlashInfer's sparse-MLA kernel",
        "sparkrun: FlashInfer SM121 sparse-MLA route",
    ),
    "dsa": (
        "sparkrun: flashinfer_sparse_mla carries the same sink",
        "sparkrun: hand the sink to the FlashInfer route",
    ),
    "flash_mla": (
        "sparkrun: ERNIE 5.5 Flash serves the same packed DSA cache",
        "sparkrun: optional FlashMLA V4 sink",
    ),
}


def run_script(
    ernie: str = ERNIE_MODULE,
    dsa: str = DSA_MODULE,
    flash_mla: str = FLASH_MLA_MODULE,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Path]]:
    """Write the fixtures into a throwaway sglang package and run the script."""
    tmp = tempfile.mkdtemp(prefix="ernie-sparse-")
    attention = Path(tmp) / "sglang" / "srt" / "layers" / "attention"
    kernels = Path(tmp) / "sglang" / "kernels" / "ops" / "attention"
    attention.mkdir(parents=True)
    kernels.mkdir(parents=True)
    for package in (
        Path(tmp) / "sglang",
        Path(tmp) / "sglang" / "srt",
        Path(tmp) / "sglang" / "srt" / "layers",
        attention,
        Path(tmp) / "sglang" / "kernels",
        Path(tmp) / "sglang" / "kernels" / "ops",
        kernels,
    ):
        (package / "__init__.py").write_text("")
    paths = {
        "ernie": attention / "ernie55_backend.py",
        "dsa": attention / "dsa_backend.py",
        "flash_mla": kernels / "flash_mla_sm120.py",
    }
    paths["ernie"].write_text(ernie)
    paths["dsa"].write_text(dsa)
    paths["flash_mla"].write_text(flash_mla)
    env = dict(os.environ)
    env["PYTHONPATH"] = tmp
    proc = subprocess.run(
        [sys.executable, "-B", str(SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )
    return proc, paths


class AppliesEverySite(unittest.TestCase):
    def test_all_three_modules_carry_their_markers(self) -> None:
        proc, paths = run_script()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        for key, markers in MARKERS.items():
            text = paths[key].read_text()
            for marker in markers:
                self.assertIn(marker, text, f"{key} missing {marker!r}")
            compile(text, str(paths[key]), "exec")

    def test_window_append_and_sink_reach_the_flashinfer_call(self) -> None:
        proc, paths = run_script()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        ernie = paths["ernie"].read_text()
        # Site 5 is the semantic one: the override must build the appended page
        # set and hand the per-row length over, not just rename an impl.
        self.assertIn("append_window_to_topk(", ernie)
        self.assertIn("seq_lens=topk_length,", ernie)
        self.assertIn("attn_sink=attn_sink,", ernie)
        self.assertIn(
            "Ernie5_5MlaAttnBackend._forward_flashinfer_sparse_mla = (", ernie
        )
        dsa = paths["dsa"].read_text()
        self.assertEqual(2, dsa.count("attn_sink=attn_sink,"))
        self.assertIn('"flashinfer_sparse_mla",', dsa)
        flash_mla = paths["flash_mla"].read_text()
        self.assertIn("sinks=attn_sink,", flash_mla)
        self.assertIn("is_ernie_sm12_fp8", flash_mla)

    def test_second_run_is_idempotent(self) -> None:
        proc, paths = run_script()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        patched = {key: path.read_text() for key, path in paths.items()}
        proc2, paths2 = run_script(**patched)
        self.assertEqual(0, proc2.returncode, proc2.stdout + proc2.stderr)
        self.assertIn("nothing to write", proc2.stdout)
        for key, text in patched.items():
            self.assertEqual(text, paths2[key].read_text())


class FailClosedControls(unittest.TestCase):
    def assert_refused(
        self, proc: subprocess.CompletedProcess, paths: dict[str, Path]
    ) -> None:
        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        # Transactional: a later target's miss must leave the earlier ones alone.
        for key, markers in MARKERS.items():
            for marker in markers:
                self.assertNotIn(marker, paths[key].read_text())

    def test_missing_impl_anchor_refuses(self) -> None:
        fixture = ERNIE_MODULE.replace(
            "        # Learnable sinks are only wired into flashmla_sparse.\n", ""
        )
        proc, paths = run_script(ernie=fixture)
        self.assert_refused(proc, paths)
        self.assertIn("anchor found 0 time(s)", proc.stdout)

    def test_missing_class_anchor_refuses(self) -> None:
        fixture = ERNIE_MODULE.replace(
            "class Ernie5_5MlaAttnBackend(DeepseekSparseAttnBackend):\n",
            "class RenamedErnieBackend(DeepseekSparseAttnBackend):\n",
        )
        proc, paths = run_script(ernie=fixture)
        self.assert_refused(proc, paths)
        self.assertIn("class anchor found 0 time(s)", proc.stdout)

    def test_one_sink_gate_only_refuses(self) -> None:
        # One gate patched and one left raising would boot into a decode or a
        # prefill that refuses the sink; the count check must catch it first.
        fixture = DSA_MODULE.replace(GATE, "", 1)
        proc, paths = run_script(dsa=fixture)
        self.assert_refused(proc, paths)
        self.assertIn("expected 2 sink gates", proc.stdout)

    def test_missing_whitelist_anchor_refuses_without_writing(self) -> None:
        fixture = FLASH_MLA_MODULE.replace(
            "    if uses_flashinfer_sparse_mla and not is_glm_sm12_fp8:\n",
            "    if uses_flashinfer_sparse_mla and not False:\n",
        )
        proc, paths = run_script(flash_mla=fixture)
        self.assert_refused(proc, paths)
        self.assertIn("[site3-whitelist]", proc.stdout)


class CacheOwnership(unittest.TestCase):
    """The hook runs as root and imports flashinfer; the cache it writes is shared."""

    def test_verifier_import_is_pointed_away_from_the_shared_cache(self) -> None:
        script = (SCRIPT.parent / "run.sh").read_text()
        export = script.index('export FLASHINFER_WORKSPACE_BASE="$MOD_CACHE" TMPDIR="$MOD_CACHE/tmp"')
        self.assertLess(export, script.index("verify-ernie55-flashinfer-sparse.py"))
        # And a write that lands under the shared tree anyway refuses the launch.
        self.assertIn('-uid 0 -newer "$STAMP"', script)
        self.assertIn("shared flashinfer cache", script)


if __name__ == "__main__":
    unittest.main()
