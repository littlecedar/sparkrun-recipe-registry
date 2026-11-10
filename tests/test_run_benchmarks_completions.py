"""Guards the --completions route of recipes/ds4/benchmarks/run_benchmarks.py.

A checkpoint that ships no chat template answers /v1/chat/completions with HTTP
400, so every bench that goes through `chat()` would have recorded 200 refusals
as a 0 % accuracy score. Chat mode must stay byte-identical: recorded receipts
and the ds4 comparison depend on that body.

Run: uv run python -B -m unittest tests.test_run_benchmarks_completions -v
Stdlib-only, like the rest of tools/ and tests/.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL_PATH = REPO_ROOT / "recipes" / "ds4" / "benchmarks" / "run_benchmarks.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("run_benchmarks_completions", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_benchmarks_completions"] = module
    spec.loader.exec_module(module)
    return module


TOOL = load_tool()

# The body every recorded ds4 chat receipt carries (thinking off).
CHAT_BODY = {
    "model": "m", "messages": [{"role": "user", "content": "p"}],
    "temperature": 0, "max_tokens": 64,
    "chat_template_kwargs": {"enable_thinking": False},
}


class ChatModeUnchanged(unittest.TestCase):
    def test_body_and_endpoint_are_the_old_ones(self):
        self.assertEqual(TOOL.request_spec("m", "p", 64, "off"),
                         ("/v1/chat/completions", CHAT_BODY))

    def test_effort_only_path_adds_no_thinking_key(self):
        path, body = TOOL.request_spec("m", "p", 64, "default")
        self.assertEqual(path, "/v1/chat/completions")
        self.assertEqual(body, {"model": "m",
                                "messages": [{"role": "user", "content": "p"}],
                                "temperature": 0, "max_tokens": 64})

    def test_reply_is_the_message_content(self):
        out = {"choices": [{"message": {"content": "A"}, "finish_reason": "stop"}]}
        self.assertEqual(TOOL.reply_from(out), "A")


class CompletionsMode(unittest.TestCase):
    def test_body_carries_the_prompt(self):
        path, body = TOOL.request_spec("m", "p", 64, "none", completions=True)
        self.assertEqual(path, "/v1/completions")
        self.assertEqual(body, {"model": "m", "prompt": "p",
                                "temperature": 0, "max_tokens": 64})
        self.assertNotIn("messages", body)
        self.assertNotIn("chat_template_kwargs", body)

    def test_reply_is_the_choice_text(self):
        # No `message` key at all: the completions endpoint answers `text`, and
        # reading it as chat would score every item as an empty reply.
        out = {"choices": [{"text": "#### 42", "finish_reason": "stop"}]}
        self.assertEqual(TOOL.reply_from(out, True), "#### 42")
        item = {"_gold": "42", "tier": "gsm8k", "category": "math", "id": "gsm8k/0",
                "prompt": "q", "max_tokens": 8}
        self.assertTrue(TOOL.score_item("gsm8k", item, TOOL.reply_from(out, True)))

    def test_thinking_controls_are_refused(self):
        for extra in (["--thinking", "off"], ["--thinking", "on"],
                      ["--reasoning-effort", "low"]):
            proc = subprocess.run(
                [sys.executable, "-B", str(TOOL_PATH), "--base-url", "http://127.0.0.1:9",
                 "--model", "m", "--completions", *extra],
                capture_output=True, text=True, timeout=120)
            self.assertEqual(proc.returncode, 2, (extra, proc.stdout, proc.stderr))
            self.assertIn("--completions refuses", proc.stderr, extra)


if __name__ == "__main__":
    unittest.main()
