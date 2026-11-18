"""Guards tools/agentic-battery.py -- the agentic coding comparison lane.

Run: uv run python -B -m unittest tests.test_agentic_battery -v
Stdlib-only. The self-test's endpoint is a real loopback HTTP server, so the tool loop, the
sandbox and every hidden checker are exercised without a serve.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL_PATH = REPO_ROOT / "tools" / "agentic-battery.py"
WANTED = (
    "fix-failing-test", "two-file-bug-hunt", "spec-to-function", "refactor-preserve-behavior",
    "config-migration", "csv-to-json-cli", "mutable-default-bug", "validation-boundary",
    "multi-file-refactor", "shell-repro-rounding", "normalize-edge-table", "stub-service-client",
    "golden-regression",
)


def load_tool():
    spec = importlib.util.spec_from_file_location("agentic_battery", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["agentic_battery"] = module
    spec.loader.exec_module(module)
    return module


TOOL = load_tool()


class TaskSet(unittest.TestCase):
    def test_ids_are_the_advertised_set(self):
        self.assertEqual(tuple(t["id"] for t in TOOL.TASKS), WANTED)

    def test_tiers_and_budgets(self):
        easy = [t for t in TOOL.TASKS if t["tier"] == "easy"]
        hard = [t for t in TOOL.TASKS if t["tier"] == "hard"]
        self.assertEqual((len(easy), len(hard)), (8, 5))
        for task in easy:
            self.assertEqual((task["max_turns"], task["wall_s"]), (16, 600))
        for task in hard:
            self.assertEqual((task["max_turns"], task["wall_s"]), (24, 900))

    def test_every_task_carries_a_reference_patch(self):
        for task in TOOL.TASKS:
            with self.subTest(task=task["id"]):
                self.assertTrue(task["solution"], "no patch proves the checker is satisfiable")

    def test_every_task_is_gradable_and_starts_red(self):
        """An untouched fixture must fail its checks: a free pass would inflate every arm."""
        for task in TOOL.TASKS:
            with self.subTest(task=task["id"]):
                self.assertTrue(task["prompt"] and task["files"] and task["checks"])
                tmp = Path(tempfile.mkdtemp())
                try:
                    ws = tmp / "ws"
                    ws.mkdir()
                    for rel, text in task["files"].items():
                        path = ws / rel
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(text)
                    passed, checks = TOOL.grade(task, ws)
                    self.assertFalse(passed, f"{task['id']} passes unsolved: {checks}")
                finally:
                    shutil.rmtree(tmp)


class Protocol(unittest.TestCase):
    def test_every_request_carries_the_fixed_cap(self):
        """Two engines with different defaults must not be measured on their defaults."""
        seen: list = []
        server, base = TOOL._mock_server([{"role": "assistant", "content": "ok"}], seen)
        try:
            TOOL.chat(base, "mock", None, [{"role": "user", "content": "hi"}], 10)
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(seen[0]["max_tokens"], TOOL.MAX_TOKENS)
        self.assertEqual(TOOL.MAX_TOKENS, 4096)
        self.assertIs(seen[0]["stream"], False)


class LabelReceipt(unittest.TestCase):
    """The label is the only serving identity a summary can carry, so its absence must be explicit."""

    def _summary(self, extra: list) -> tuple[dict, Path]:
        tmp = Path(tempfile.mkdtemp())
        server, base = TOOL._mock_server([{"role": "assistant", "content": "done"}])
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                TOOL.main(["--base-url", base, "--model", "mock",
                           "--tasks", "fix-failing-test", "--outdir", str(tmp),
                           "--fixture-root", str(tmp / "fixtures"), *extra])
        finally:
            server.shutdown()
            server.server_close()
        return json.loads((tmp / "summary.json").read_text()), tmp

    def test_label_is_recorded_in_summary(self):
        summary, tmp = self._summary(["--label", "img@sha256:abc, task t1"])
        try:
            self.assertEqual(summary["label"], "img@sha256:abc, task t1")
        finally:
            shutil.rmtree(tmp)

    def test_label_defaults_to_empty_string(self):
        summary, tmp = self._summary([])
        try:
            self.assertEqual(summary["label"], "")
        finally:
            shutil.rmtree(tmp)


class SelfTest(unittest.TestCase):
    def test_selftest_loop_passes_and_fails(self):
        self.assertEqual(TOOL.selftest(), 0)

    def test_help_exits_clean(self):
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as caught:
            TOOL.main(["--help"])
        self.assertEqual(caught.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
