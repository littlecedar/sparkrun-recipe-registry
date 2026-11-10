"""Guards the --completions mode of tools/longctx-cell.py.

A serve whose checkpoint ships no chat template answers /v1/chat/completions with
HTTP 400, so the cell must be able to post the plain prompt to /v1/completions.
Chat mode must stay byte-identical: recorded receipts depend on that body.

Run: uv run python -B -m unittest tests.test_longctx_cell_completions -v
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
    spec = importlib.util.spec_from_file_location("longctx_cell_completions", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["longctx_cell_completions"] = module
    spec.loader.exec_module(module)
    return module


TOOL = load_tool()

# The body every recorded chat receipt carries; completions mode must not move it.
CHAT_BODY = {
    "model": "m", "messages": [{"role": "user", "content": "p"}],
    "temperature": 0, "max_tokens": 128, "stream": True,
    "stream_options": {"include_usage": True},
}


class ChatModeUnchanged(unittest.TestCase):
    def test_default_flag_is_off(self):
        args = TOOL.parse([]).parse_args(["--base-url", "http://x",
                                          "--context-length", "1m"])
        self.assertFalse(args.completions)

    def test_body_and_endpoint_are_the_old_ones(self):
        self.assertEqual(TOOL.request_body("m", "p", 128), CHAT_BODY)
        self.assertEqual(TOOL.request_target(), ("chat", "/v1/chat/completions"))

    def test_url_still_resolves_to_chat_completions(self):
        for base in ("http://h:8000", "http://h:8000/v1",
                     "http://h:8000/v1/chat/completions"):
            self.assertEqual(TOOL._url(base, TOOL.request_target()[1]),
                             "http://h:8000/v1/chat/completions", base)


class CompletionsMode(unittest.TestCase):
    def test_body_carries_the_prompt(self):
        body = TOOL.request_body("m", "p", 64, 0, completions=True)
        self.assertEqual(body["prompt"], "p")
        self.assertNotIn("messages", body)
        self.assertEqual(body["model"], "m")
        self.assertEqual(body["max_tokens"], 64)

    def test_lever_reaches_the_completions_body(self):
        body = TOOL.request_body("m", "p", 64, 64, completions=True)
        self.assertIs(body["ignore_eos"], True)
        self.assertEqual(body["min_tokens"], 64)

    def test_endpoint_and_recorded_mode(self):
        self.assertEqual(TOOL.request_target(True), ("completions", "/v1/completions"))
        self.assertEqual(TOOL._url("http://h:8000/v1/completions",
                                   TOOL.request_target(True)[1]),
                         "http://h:8000/v1/completions")

    def test_flag_parses_and_fits_the_shared_checks(self):
        args = TOOL.parse([]).parse_args([
            "--base-url", "http://x", "--context-length", "1039999",
            "--chars-per-token", "6.65", "--completions", "--model",
            "baidu/ERNIE-5.5-Flash-Base", "--max-tokens", "64",
            "--min-answer-tokens", "64"])
        self.assertTrue(args.completions)
        self.assertEqual(args.task, "retrieval")
        self.assertIsNone(TOOL.check_flags(args))


if __name__ == "__main__":
    unittest.main()
