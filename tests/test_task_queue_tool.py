"""Guards for tools/task-queue.py — the owner's task-queueing policy, mechanized.

Run:
    uv run python -B -m unittest discover -s tests

Stdlib-only, no network, no cluster, like every other guard here.

What is pinned (owner policy 2026-10-26, `mad-science/GUIDANCE.md` #2/#4; protocol in
`mad-science/QUEUE.md`):

* weight arithmetic — simple and transitive: a task's weight is its estimate minus the sum of
  the estimates of everything it transitively blocks (`test_simple_weight`,
  `test_transitive_weight_is_the_chain_total`);
* the owner's own 48 h / 24 h illustration: a 24 h task blocking 24 h of work in a 48 h queue
  weighs 0 and floats to the top (`test_owner_48h_24h_example_floats_to_the_top`);
* a done blocker stops contributing credit, so its dependents' weights rise
  (`test_done_tasks_stop_contributing_credit`);
* the priority override — DeepSeek-V4.1-Flash-1017 (either tag spelling) before GLM-5.3 before
  GLM-5.3-Flash before everything else, weight ascending within a tier
  (`test_tiering_prioritizes_the_owner_models`, `test_weight_orders_within_a_tier`);
* fail-closed validation, each with a negative control: a `blocks` cycle (a 2-cycle is refused,
  `test_two_cycle_is_refused`), a dangling id, a missing estimate, a non-numeric estimate
  (`test_dangling_ref_is_refused`, `test_missing_estimate_is_refused`,
  `test_non_numeric_estimate_is_refused`);
* `done` drops a task from the ordering and releases its blocking credit, so the queue
  re-sorts (`test_done_removes_task_and_releases_blocked_credit`).

Nothing here re-implements the tool: the fixtures are minimal task dicts and the assertions are
the properties.
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


def _load():
    spec = importlib.util.spec_from_file_location("task_queue", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["task_queue"] = module  # dash-named tool convention
    spec.loader.exec_module(module)
    return module


tq = _load()


def task(tid, est, blocks=(), model="", state="queued"):
    return {
        "id": tid, "title": tid, "estimate_h": est, "blocks": list(blocks),
        "blocked_by": [], "state": state, "model": model, "node_cost": "",
        "notes": "", "provenance": "test",
    }


def relink(tasks):
    mirror = tq.derived_blocked_by(tasks)
    for t in tasks:
        t["blocked_by"] = sorted(mirror.get(t["id"], set()))
    return tasks


# The seeded tier list: a tier may be a list of equivalent tags — the registry spells the
# primary model both ways, and both spellings must share tier 0.
def data(tasks, priority_models=(["deepseek-v4.1-flash-1017", "dsv4.1-1017"], "glm-5.3", "glm-5.3-flash")):
    return {"priority_models": [list(t) if isinstance(t, list) else t for t in priority_models],
            "tasks": relink(list(tasks))}


def ids(ordered):
    return [t["id"] for t in ordered]


class WeightArithmetic(unittest.TestCase):
    def test_simple_weight(self):
        a = task("a", 2.0)
        weight, blocked = tq.compute_weight(a, [a])
        self.assertEqual(weight, 2.0)
        self.assertEqual(blocked, {})

    def test_transitive_weight_is_the_chain_total(self):
        # a -> b -> c: a's credit is b + c (24), not just its direct dependent b (12).
        a, b, c = task("a", 24.0, ["b"]), task("b", 12.0, ["c"]), task("c", 12.0)
        tasks = relink([a, b, c])
        weight, blocked = tq.compute_weight(tasks[0], tasks)
        self.assertEqual(weight, 0.0)
        self.assertEqual(blocked, {"b": 12.0, "c": 12.0})

    def test_owner_48h_24h_example_floats_to_the_top(self):
        # The owner's illustration: a 48-hour-deep queue whose 24 h task blocks 24 h of work
        # weighs 0 and takes the top slot despite being the most expensive item. The two
        # blocked tasks are a fan-out (x -> a 12 h, x -> b 12 h) so x alone weighs 0.
        x = task("x", 24.0, ["a", "b"])
        a, b = task("a", 12.0), task("b", 12.0)
        filler1, filler2 = task("f1", 20.0), task("f2", 20.0)
        ordered = tq.ordering(data([filler1, x, a, b, filler2]))
        self.assertEqual(ids(ordered)[0], "x")
        self.assertEqual(ids(ordered)[1:], ["a", "b", "f1", "f2"])
        weight, _ = tq.compute_weight(x, [x, a, b, filler1, filler2])
        self.assertEqual(weight, 0.0)

    def test_done_tasks_stop_contributing_credit(self):
        # A done blocker no longer blocks: its dependents' weights rise and it drops out.
        a, b, c = task("a", 24.0, ["b"]), task("b", 12.0, ["c"]), task("c", 12.0, state="done")
        tasks = relink([a, b, c])
        weight, blocked = tq.compute_weight(tasks[0], tasks)
        self.assertEqual((weight, blocked), (12.0, {"b": 12.0}))


class Tiering(unittest.TestCase):
    def test_tiering_prioritizes_the_owner_models(self):
        tasks = [
            task("other", 0.1, model="whatever"),
            task("glm-flash", 0.1, model="glm-5.3-flash"),
            task("glm", 0.1, model="glm-5.3"),
            task("dsv-alias", 0.1, model="dsv4.1-1017"),
            task("dsv-long", 0.1, model="DeepSeek-V4.1-Flash-1017"),
        ]
        self.assertEqual(ids(tq.ordering(data(tasks))),
                         ["dsv-alias", "dsv-long", "glm", "glm-flash", "other"])

    def test_weight_orders_within_a_tier(self):
        tasks = [
            task("heavy", 10.0, model="glm-5.3"),
            task("light-gater", 1.0, ["heavy", "other-glm"], model="glm-5.3"),
            task("other-glm", 2.0, model="glm-5.3"),
        ]
        self.assertEqual(ids(tq.ordering(data(tasks))), ["light-gater", "other-glm", "heavy"])


class FailClosed(unittest.TestCase):
    def test_two_cycle_is_refused(self):
        tasks = relink([task("p", 1.0, ["q"]), task("q", 1.0, ["p"])])
        with self.assertRaises(tq.QueueError) as ctx:
            tq.validate(data(tasks, priority_models=["x"]))
        self.assertIn("cycle", str(ctx.exception))
        self.assertIn("p -> q -> p", str(ctx.exception))

    def test_dangling_ref_is_refused(self):
        tasks = relink([task("p", 1.0, ["ghost"])])
        with self.assertRaises(tq.QueueError) as ctx:
            tq.validate(data(tasks, priority_models=["x"]))
        self.assertIn("ghost", str(ctx.exception))

    def test_missing_estimate_is_refused(self):
        bad = task("p", 1.0)
        del bad["estimate_h"]
        with self.assertRaises(tq.QueueError) as ctx:
            tq.validate(data([bad], priority_models=["x"]))
        self.assertIn("estimate_h", str(ctx.exception))

    def test_non_numeric_estimate_is_refused(self):
        bad = task("p", "two")
        with self.assertRaises(tq.QueueError) as ctx:
            tq.validate(data([bad], priority_models=["x"]))
        self.assertIn("p", str(ctx.exception))

    def test_cli_exits_non_zero_on_a_cycle(self):
        # Negative control at the CLI layer: the same 2-cycle exits 1 with the message on stderr.
        payload = data([task("p", 1.0, ["q"]), task("q", 1.0, ["p"])], priority_models=["x"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"
            path.write_text(json.dumps(payload))
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                rc = tq.main(["--file", str(path), "queue"])
        self.assertEqual(rc, 1)
        self.assertIn("cycle", stderr.getvalue())

    def test_cli_check_and_queue_exit_zero_on_the_seeded_queue(self):
        # The tracked seed itself must validate and order cleanly (no mutation on read).
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(tq.main(["--file", str(REPO_ROOT / "mad-science" / "queue.json"), "check"]), 0)
            self.assertEqual(tq.main(["--file", str(REPO_ROOT / "mad-science" / "queue.json"), "queue"]), 0)
        self.assertEqual(stderr.getvalue(), "")


class Done(unittest.TestCase):
    def test_done_removes_task_and_releases_blocked_credit(self):
        # a (4 h) gates b (2 h) and c (2 h): a weighs 0 and floats. Marking c done drops c
        # from the ordering and releases half of a's credit, so a's weight rises to 2.
        a = task("a", 4.0, ["b", "c"])
        b, c = task("b", 2.0), task("c", 2.0)
        tasks = relink([a, b, c])
        self.assertEqual(ids(tq.ordering(data(tasks))), ["a", "b", "c"])
        c_state = dict(c, state="done")
        ordered = tq.ordering(data([a, b, c_state]))
        self.assertEqual(ids(ordered), ["a", "b"])
        weight, blocked = tq.compute_weight(a, [a, b, c_state])
        self.assertEqual((weight, blocked), (2.0, {"b": 2.0}))


if __name__ == "__main__":
    unittest.main()