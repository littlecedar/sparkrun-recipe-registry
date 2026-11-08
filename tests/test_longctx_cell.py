"""Guards tools/longctx-cell.py.

Run: uv run python -B -m unittest tests.test_longctx_cell -v
Stdlib-only, like the rest of tools/ and tests/.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL_PATH = REPO_ROOT / "tools" / "longctx-cell.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("longctx_cell", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["longctx_cell"] = module
    spec.loader.exec_module(module)
    return module


TOOL = load_tool()


class LengthParsing(unittest.TestCase):
    def test_units(self):
        self.assertEqual(TOOL.parse_length("1m"), 1_000_000)
        self.assertEqual(TOOL.parse_length("128k"), 128_000)
        self.assertEqual(TOOL.parse_length("1039999"), 1_039_999)


class PromptBuild(unittest.TestCase):
    def test_one_needle_and_sized(self):
        prompt, code = TOOL.build_prompt(2000, 7, 3.5)
        self.assertEqual(prompt.count("ZX81-"), 1)
        self.assertIn(code, prompt)
        self.assertGreater(len(prompt), 6000)
        self.assertTrue(prompt.rstrip().endswith("Answer with the code only."))

    def test_unique_per_seed(self):
        first, _ = TOOL.build_prompt(500, 1, 3.5)
        second, _ = TOOL.build_prompt(500, 2, 3.5)
        self.assertNotEqual(first, second)


def rec(**kw):
    base = {"error": None, "needle": True, "completion_tokens": 100,
            "decode_s": 2.0, "ms_per_step": 20.0, "prompt_tokens": 200_000,
            "steps": 100}
    base.update(kw)
    return base


class Summary(unittest.TestCase):
    def test_medians_and_aggregate(self):
        cell = TOOL.summarize([rec(), rec(ms_per_step=30.0)], 2, 4.0)
        self.assertEqual(cell["ms_per_step_median"], 25.0)
        self.assertEqual(cell["needle_hits"], 2)
        self.assertEqual(cell["aggregate_tok_per_s"], 50.0)
        self.assertEqual(cell["prompt_tokens"], [200_000])
        self.assertEqual(TOOL.verdict([cell], 200_000), [])

    def test_findings(self):
        short = TOOL.summarize([rec(prompt_tokens=1000)], 1, 1.0)
        self.assertTrue(TOOL.verdict([short], 200_000))
        miss = TOOL.summarize([rec(needle=False)], 1, 1.0)
        self.assertTrue(TOOL.verdict([miss], 200_000))
        err = TOOL.summarize([rec(error="HTTP 400")], 1, 1.0)
        self.assertTrue(TOOL.verdict([err], 200_000))

    def test_unverified_length(self):
        unverified = TOOL.summarize([rec(prompt_tokens=None)], 1, 1.0)
        self.assertIn("unverified", " ".join(TOOL.verdict([unverified], 200_000)))


class ImageId(unittest.TestCase):
    def test_flag_is_echoed(self):
        # A receipt has to pin the image its cell ran on; the id travels through
        # the tool rather than being reconstructed from the log.
        args = TOOL.parse([]).parse_args([
            "--base-url", "http://x", "--context-length", "8k",
            "--image-id", "sha256:1778ec42"])
        self.assertEqual(args.image_id, "sha256:1778ec42")
        bare = TOOL.parse([]).parse_args(["--base-url", "http://x",
                                          "--context-length", "8k"])
        self.assertIsNone(bare.image_id)

if __name__ == "__main__":
    unittest.main()
