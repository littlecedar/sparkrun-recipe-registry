# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Guards for the SM121 V4.1 KV-layout port (row ds4-fp4-kv-layout-sm121-port-sglang).

Two artifacts, two guards:

* ``recipes/ds4/fp4kv_kv_format.py`` decides the FlashInfer SM120 call format from
  the cache widths. Its negative controls matter: 288 B is a *compressed* row
  only, and a V4 main cache never pairs with a V4.1 extra one -- a wrong decision
  reads the wrong stride instead of failing.
* ``recipes/ds4/patch_dsv41_fp4kv.py`` is the build-time patch. The test builds a
  fixture tree out of the script's own anchors, applies it, and asserts the
  post-conditions; the controls delete and duplicate one anchor, which must fail
  closed. The anchors themselves are checked against the pinned tree only where
  one is present (``SGLANG_FP4KV_TREE``), because CI has no image tree.

Stdlib-only, no torch, no GPU, no image.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FORMAT_MODULE = REPO / "recipes" / "ds4" / "fp4kv_kv_format.py"
PATCHER = REPO / "recipes" / "ds4" / "patch_dsv41_fp4kv.py"
DOCKERFILE = REPO / "recipes" / "ds4" / "Dockerfile.dsv41-fp4kv"


def load(path: Path, name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class CacheFormat(unittest.TestCase):
    def setUp(self):
        self.mod = load(FORMAT_MODULE, "fp4kv_kv_format")

    def test_the_three_row_widths_are_the_layout_constants(self):
        self.assertEqual(self.mod.V4_ROW_BYTES, 448 + 64 * 2 + 8)
        self.assertEqual(self.mod.V41_ROW_BYTES, 512 + 16)
        self.assertEqual(self.mod.V41_FP4_ROW_BYTES, 512 // 2 + 512 // 16)

    def test_v4_keeps_the_0_6_call(self):
        # No format argument: the shipped 0.6 wheel has neither parameter.
        self.assertEqual(self.mod.sm120_cache_format(584), ("", False))
        self.assertEqual(self.mod.sm120_cache_format(584, 584), ("", False))

    def test_v41_main_selects_the_inline_route(self):
        inline = self.mod.V41_INLINE_SCALE_FORMAT
        self.assertEqual(self.mod.sm120_cache_format(528), (inline, False))
        self.assertEqual(self.mod.sm120_cache_format(528, 528), (inline, False))
        self.assertEqual(self.mod.sm120_cache_format(528, 288), (inline, True))

    def test_an_unreadable_pair_is_refused(self):
        for main_bytes, extra_bytes in ((584, 528), (584, 288), (528, 584), (288, None)):
            with self.subTest(main=main_bytes, extra=extra_bytes):
                with self.assertRaises(ValueError):
                    self.mod.sm120_cache_format(main_bytes, extra_bytes)

    def test_the_reader_probe_is_false_without_flashinfer(self):
        # CI has no FlashInfer; the probe must answer, not raise.
        self.assertFalse(self.mod.sm120_reader_has_inline_route())


class PatchMechanics(unittest.TestCase):
    def setUp(self):
        self.mod = load(PATCHER, "patch_dsv41_fp4kv")
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.files = self.mod.paths(self.root)
        for path in self.files.values():
            path.parent.mkdir(parents=True, exist_ok=True)
        # A fixture tree containing each anchor exactly once, per file.
        for key, old, _new in self.mod.EDITS:
            path = self.files[key]
            path.write_text(path.read_text() + old if path.exists() else old, encoding="utf-8")
        self.files["format"].write_text("# stand-in\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_every_anchor_applies_and_the_post_conditions_hold(self):
        self.mod.apply(self.root)
        self.mod.verify(self.root)
        self.assertNotEqual(self.files["pool"].read_text(), "")
        self.assertIn("is_v41_arch = _sm120_inline_reader()", self.files["pool"].read_text())
        self.assertIn("**_sm120_format_kwargs(", self.files["flashmla"].read_text())

    def test_a_missing_anchor_fails_closed(self):
        text = self.files["pool"].read_text()
        key, old, _new = next(e for e in self.mod.EDITS if e[0] == "pool")
        self.files["pool"].write_text(text.replace(old, "", 1), encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.mod.apply(self.root)

    def test_a_duplicated_anchor_fails_closed(self):
        key, old, _new = next(e for e in self.mod.EDITS if e[0] == "flashmla")
        self.files["flashmla"].write_text(
            self.files["flashmla"].read_text() + old, encoding="utf-8"
        )
        with self.assertRaises(SystemExit):
            self.mod.apply(self.root)

    def test_a_missing_format_module_fails_the_build(self):
        self.files["format"].unlink()
        self.mod.apply(self.root)
        with self.assertRaises(SystemExit):
            self.mod.verify(self.root)

    def test_the_dockerfile_copies_the_module_and_runs_the_patcher(self):
        text = DOCKERFILE.read_text(encoding="utf-8")
        self.assertIn("fp4kv_kv_format.py", text)
        self.assertIn("patch_dsv41_fp4kv.py", text)
        self.assertIn("FROM dsv41-sm121-dg:0.2.1-fi073e", text)


if __name__ == "__main__":
    unittest.main()
