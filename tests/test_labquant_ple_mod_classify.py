# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Guard the PLE-file classifier in recipes/qwen4/mods/unpack-labquant-ple-nvfp4-to-fp8/run.sh.

The step-5500 revision (`6c01ac37`) makes one PLE shard carry non-PLE tensors
(`ple.norm_*.weight`, `ngram_embedding.weight_scale_2`) alongside its 16 PLE
tensors.  The classifier must PRESERVE those through a rewrite instead of
skipping the whole file (which silently drops 8 pairs and trips the
EXPECTED_GROUPS gate).  It must still fail closed on a genuinely corrupt file.

This test runs the *actual* classifier text extracted from run.sh against
synthetic shard headers, so a future edit to the classification is exercised
here without needing a GPU or a 106 GB checkpoint.  Stdlib only.
"""
from __future__ import annotations

import json
import os
import re
import unittest
from pathlib import Path

RUN_SH = Path(__file__).resolve().parent.parent / "recipes" / "qwen4" / "mods" / "unpack-labquant-ple-nvfp4-to-fp8" / "run.sh"

W = (2500012, 80)
S = (2500012, 10)


def _classifier_source() -> str:
    """The classifier block of run.sh, from the index scan through the contract log."""
    src = RUN_SH.read_text()
    start = src.index("files_with_ple = sorted(")
    stop = 'f"weight {EXPECTED_W} U8, scale {EXPECTED_S} F8_E4M3")'
    return src[start: src.index(stop, start) + len(stop)]


def _key_pattern() -> re.Pattern:
    """The exact KEY regex object the classifier uses (eval'd from run.sh)."""
    for line in RUN_SH.read_text().splitlines():
        if line.startswith("KEY = re.compile("):
            return eval(line.split("=", 1)[1].strip())
    raise AssertionError("KEY regex not found in run.sh")


def classify(headers, weight_map, groups, n_files):
    """Execute the extracted classifier; returns (pairs, ple_dedicated, passthrough).

    Raises SystemExit (the mod's fail-closed path) on a contract violation.
    """
    g = {
        "json": json, "os": os, "re": re,
        "SNAP": "/nonexistent",
        "wm": weight_map,
        "header_of": lambda f: headers[f],
        "KEY": _key_pattern(),
        "EXPECTED_W": W, "EXPECTED_S": S,
        "EXPECTED_GROUPS": groups, "EXPECTED_PLE_ONLY_FILES": n_files,
        "log": lambda *a: None,
        "die": lambda msg: (_ for _ in ()).throw(SystemExit(msg)),
    }
    exec(compile(_classifier_source(), "<classifier>", "exec"), g)
    return g["pairs"], g["ple_dedicated"], g["passthrough"]


def _ple(shard):
    return {
        f"model.language_model.layers.1.ple.ple_embedding.ngram_embedding.shard_{shard}.weight":
            {"shape": list(W), "dtype": "U8"},
        f"model.language_model.layers.1.ple.ple_embedding.ngram_embedding.shard_{shard}.weight_scale":
            {"shape": list(S), "dtype": "F8_E4M3"},
    }


def _wm(headers):
    return {n: f for f, h in headers.items() for n in h}


class ClassifierTest(unittest.TestCase):
    def test_pure_ple_file(self):
        h = _ple(0)
        headers = {"a.safetensors": h}
        pairs, _files, pt = classify(headers, _wm(headers), 1, 1)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pt, {})

    def test_passthrough_keeps_non_ple_tensors(self):
        # The step-5500 shape: PLE pairs + norms + weight_scale_2 in ONE file.
        h = _ple(0)
        h["model.language_model.layers.1.ple.norm_conv.weight"] = {"shape": [10240], "dtype": "F32"}
        h["model.language_model.layers.1.ple.ple_embedding.ngram_embedding.weight_scale_2"] = {"shape": [1], "dtype": "F32"}
        headers = {"a.safetensors": h}
        pairs, _files, pt = classify(headers, _wm(headers), 1, 1)
        self.assertEqual(len(pairs), 1, "the PLE pair must still be converted")
        self.assertEqual(len(pt["a.safetensors"]), 2, "non-PLE tensors must be recorded for passthrough")
        self.assertIn("model.language_model.layers.1.ple.norm_conv.weight", pt["a.safetensors"])

    def test_incomplete_pair_fails_closed(self):
        h = _ple(0)
        h.pop("model.language_model.layers.1.ple.ple_embedding.ngram_embedding.shard_0.weight_scale")
        headers = {"a.safetensors": h}
        with self.assertRaises(SystemExit):
            classify(headers, _wm(headers), 1, 1)

    def test_shape_contract_fails_closed(self):
        h = _ple(0)
        h["model.language_model.layers.1.ple.ple_embedding.ngram_embedding.shard_0.weight"]["shape"] = [2500012, 160]
        headers = {"a.safetensors": h}
        with self.assertRaises(SystemExit):
            classify(headers, _wm(headers), 1, 1)

    def test_group_count_fails_closed(self):
        h = _ple(0)
        headers = {"a.safetensors": h}
        with self.assertRaises(SystemExit):
            classify(headers, _wm(headers), 128, 1)


if __name__ == "__main__":
    unittest.main()
