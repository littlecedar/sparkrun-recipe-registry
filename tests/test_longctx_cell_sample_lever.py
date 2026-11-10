"""Guards the decode-sample lever of tools/longctx-cell.py.

Run: uv run python -B -m unittest tests.test_longctx_cell_sample_lever -v
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
    spec = importlib.util.spec_from_file_location("longctx_cell_lever", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["longctx_cell_lever"] = module
    spec.loader.exec_module(module)
    return module


TOOL = load_tool()

# The body every existing receipt was produced with; the lever must not move it.
PLAIN_BODY = {
    "model": "m", "messages": [{"role": "user", "content": "p"}],
    "temperature": 0, "max_tokens": 128, "stream": True,
    "stream_options": {"include_usage": True},
}


class SampleLever(unittest.TestCase):
    def test_off_body_is_unchanged(self):
        self.assertEqual(TOOL.request_body("m", "p", 128), PLAIN_BODY)

    def test_on_body_asks_for_a_long_sample(self):
        body = TOOL.request_body("m", "p", 128, 64)
        self.assertIs(body["ignore_eos"], True)
        self.assertEqual(body["min_tokens"], 64)
        self.assertEqual(body["max_tokens"], 128)  # max_tokens still the ceiling
        self.assertEqual({k: v for k, v in body.items()
                          if k not in ("ignore_eos", "min_tokens")}, PLAIN_BODY)

    def test_min_above_max_is_refused(self):
        ok = TOOL.parse([]).parse_args(["--max-tokens", "64", "--min-answer-tokens", "64"])
        self.assertIsNone(TOOL.check_flags(ok))
        bad = TOOL.parse([]).parse_args(["--max-tokens", "64", "--min-answer-tokens", "65"])
        self.assertTrue(TOOL.check_flags(bad))

    def test_long_generation_prompt_keeps_needle(self):
        prompt, code = TOOL.build_prompt(2000, 7, 3.5, "long-generation")
        self.assertEqual(prompt.count("ZX81-"), 1)
        self.assertIn(code, prompt)
        self.assertEqual(TOOL.needle_hit("code: " + code + " rest", code, True), True)
        self.assertFalse(TOOL.needle_hit("x" * 400 + code, code, True))


if __name__ == "__main__":
    unittest.main()
