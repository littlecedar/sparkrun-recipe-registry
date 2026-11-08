"""`validate()` without a register path: the library call has one meaning, and it is the CLI's.

Measured 2026-11-07: the register gained its first `recipe`-bearing rows, and the archive guard
reads the live `queue.json` through `tq.validate(payload)` with no path. The function's docstring
promised "the shapes are checked and the filesystem resolution is not", but `_bootable` raised
`'recipe' cannot be resolved` instead, so a library caller validating live register data errored
where the CLI (`check`, which passes its `--file`) was green. A contract that says two things is
worse than either: the default is now *this tool's own checkout*, so a no-path call resolves
exactly what the CLI resolves; a register outside any worktree still fails, naming the path.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "task-queue.py"

_spec = importlib.util.spec_from_file_location("task_queue_root", TOOL)
tq = importlib.util.module_from_spec(_spec)
sys.modules["task_queue_root"] = tq
_spec.loader.exec_module(tq)

#: A tracked recipe of this checkout: a no-path call must resolve against the tool's own repo.
TRACKED = "recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml"


def row(**fields) -> dict:
    task = {"id": "a", "title": "a", "estimate_h": 1.0, "blocks": [], "blocked_by": [],
            "state": "queued", "model": "", "node_cost": "", "notes": "",
            "provenance": "test"}
    task.update(fields)
    return task


def payload(*rows) -> dict:
    return {"priority_models": [], "tasks": list(rows)}


class NoPathDefaultsToThisCheckout(unittest.TestCase):
    def test_a_tracked_recipe_resolves_without_a_register_path(self):
        self.assertTrue((REPO_ROOT / TRACKED).is_file(), TRACKED)
        rows = tq.validate(payload(row(recipe=TRACKED, tp=4, node_cost="quartet")))
        self.assertEqual(rows[0]["recipe"], TRACKED)

    def test_an_untracked_recipe_is_refused_and_the_message_names_this_checkout(self):
        with self.assertRaises(tq.QueueError) as ctx:
            tq.validate(payload(row(recipe="recipes/lane/ghost.yaml", tp=1, node_cost="single")))
        message = str(ctx.exception)
        self.assertIn("not a tracked file", message)
        self.assertIn(str(REPO_ROOT), message, "the default root must be the tool's own checkout")

    def test_a_register_outside_a_worktree_still_fails_through_the_cli(self):
        """A path *is* the stronger statement: a register with no checkout cannot resolve rows."""
        with tempfile.TemporaryDirectory() as tmp:
            register = Path(tmp) / "mad-science" / "queue.json"
            register.parent.mkdir()
            register.write_text(json.dumps(payload(
                row(recipe="recipes/lane/arm.yaml", tp=1, node_cost="single"))), encoding="utf-8")
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = tq.main(["--file", str(register), "check"])
        self.assertEqual(code, 1)
        self.assertIn("not a git worktree", err.getvalue())
        self.assertIn(str(register), err.getvalue())


if __name__ == "__main__":
    unittest.main()
