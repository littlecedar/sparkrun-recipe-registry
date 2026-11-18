"""Guards tools/agentic-battery.py -- the agentic coding comparison lane.

Run: uv run python -B -m unittest tests.test_agentic_battery -v
Stdlib-only. The self-test's endpoint is a real loopback HTTP server, so the tool loop, the
sandbox and every hidden checker are exercised without a serve.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
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


class SelfTest(unittest.TestCase):
    def test_selftest_loop_passes_and_fails(self):
        self.assertEqual(TOOL.selftest(), 0)

    def test_help_exits_clean(self):
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as caught:
            TOOL.main(["--help"])
        self.assertEqual(caught.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
