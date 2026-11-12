"""Guards for tools/task-queue.py — the owner's task-queueing policy, mechanized.

Run:
    uv run python -B -m unittest discover -s tests

Stdlib-only, no network, no cluster, like every other guard here.

What is pinned (owner policy 2026-10-26, verbatim; the dated decisions live in
`mad-science/TODO.md` §"Retry queue — window 4"; protocol in `mad-science/QUEUE.md`):

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
import datetime as dt
import fcntl
import hashlib
import importlib.util
import io
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import types
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


def qdata(tasks, questions=()):
    """A register with an open `questions[]` array, deliberately NOT relinked.

    `relink` would repair the stored/derived drift the graph must tolerate and report, so the
    graph fixtures build their `blocked_by` by hand.
    """
    return {"priority_models": ["x"], "tasks": list(tasks),
            "questions": [{"id": q, "status": "open", "summary": f"owner question {q}",
                           "provenance": "test", "asked": "2026-11-08"} for q in questions]}


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


class PlacementClassification(unittest.TestCase):
    """`memory_risky` / `exclude_hosts` must be WRITABLE, and a malformed value must be refused.

    Measured 2026-11-10: `campaign/DESIGN.md:86-93` and `plan.memory_risky()` promised a row could
    declare `memory_risky: true`, `exclude_hosts: [...]`, or override to `false`, but the writer's
    flip set had no such key — so the safe-quartet override was unreachable and `node_cost:
    quartet` was the only classification that could ever apply. A promise the tree cannot keep is
    the defect these tests pin.
    """

    def _register(self, tmp):
        path = Path(tmp) / "queue.json"
        path.write_text(json.dumps(data([task("arm", 1.0)], priority_models=["x"])))
        return path

    def test_update_writes_and_queue_reads_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._register(tmp)
            self.assertEqual(tq.main(["--file", str(path), "update", "--id", "arm",
                                      "--memory-risky", "--exclude-hosts", "node-a,node-b"]), 0)
            printed = io.StringIO()
            with contextlib.redirect_stdout(printed):
                self.assertEqual(tq.main(["--file", str(path), "queue", "--json"]), 0)
            row = json.loads(printed.getvalue())[0]
            self.assertIs(row["memory_risky"], True)
            self.assertEqual(row["exclude_hosts"], ["node-a", "node-b"])

            self.assertEqual(tq.main(["--file", str(path), "update", "--id", "arm",
                                      "--no-memory-risky"]), 0)
            printed = io.StringIO()
            with contextlib.redirect_stdout(printed):
                tq.main(["--file", str(path), "queue", "--json"])
            row = json.loads(printed.getvalue())[0]
            self.assertIs(row["memory_risky"], False,
                          "the override DESIGN.md documents: safe despite a quartet node cost")
            self.assertEqual(row["exclude_hosts"], ["node-a", "node-b"],
                             "an unset flag leaves the list alone")

    def test_a_malformed_value_is_refused_by_check(self):
        # Negative control: the round-trip test above must not pass on a schema that accepts
        # anything. Both spellings are what a hand-edit produces.
        for bad in ({"memory_risky": "yes"}, {"exclude_hosts": "node-a"},
                    {"exclude_hosts": ["node-a", ""]}):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "queue.json"
                payload = data([task("arm", 1.0)], priority_models=["x"])
                payload["tasks"][0].update(bad)
                path.write_text(json.dumps(payload))
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    self.assertEqual(tq.main(["--file", str(path), "check"]), 1)
                self.assertIn(next(iter(bad)), stderr.getvalue())

    def test_an_empty_exclusion_list_is_a_usage_defect(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._register(tmp)
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertNotEqual(tq.main(["--file", str(path), "update", "--id", "arm",
                                             "--exclude-hosts", "node-a,"]), 0)
            self.assertIn("--exclude-hosts", stderr.getvalue())


class UpdateRepairsDrift(unittest.TestCase):
    def test_update_relinks_before_validating(self):
        """`check` tells the reader to rerun `update`; that must be able to succeed.

        The mirror is derived from `blocks`, so a register whose `blocked_by` drifted is exactly the
        state `update` exists to repair -- and it used to validate first, so every rerun died on the
        same line. Measured 2026-10-30: three attempts, each printing the same instruction.
        """
        payload = data([task("a", 1.0, ["b"]), task("b", 2.0, [])], priority_models=["x"])
        payload["tasks"][1]["blocked_by"] = []          # a drift the mirror says should be ["a"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"
            path.write_text(json.dumps(payload))
            self.assertNotEqual(tq.main(["--file", str(path), "check"]), 0)
            self.assertEqual(tq.main(["--file", str(path), "update", "--id", "b", "--notes", "x"]), 0)
            self.assertEqual(tq.main(["--file", str(path), "check"]), 0)

    def test_pair_is_a_valid_node_cost(self):
        """A TP=2 arm is a pair; the checklist predated it and forced a caveat in `notes`."""
        self.assertIn("pair", tq.NODE_COSTS)


class QuestionsAndCommitBound(unittest.TestCase):
    """The two schema additions chosen 2026-11-03: a questions register, and a commit-bounded
    archive scan (the count bound netted out when one item was removed as another arrived)."""

    def _repo(self, tmp):
        import subprocess
        root = Path(tmp)
        (root / "q.json").write_text(json.dumps(data([task("a", 1.0)])), encoding="utf-8")
        (root / "TODO.md").write_text("- [ ] **old item**\n", encoding="utf-8")
        env = ["-c", "user.email=g@example.invalid", "-c", "user.name=g"]
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", *env, "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", *env, "commit", "-qm", "freeze"], cwd=root, check=True)
        return root

    def test_orphans_since_bounds_the_scan(self):
        # Only items ADDED after the boundary count: the frozen file's own item is not an orphan.
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(tmp)
            todo = root / "TODO.md"
            with open(todo, "a", encoding="utf-8") as fh:
                fh.write("- [ ] **new item**\n")
            argv = ["--file", str(root / "q.json"), "orphans", "--todo", str(todo), "--since", "HEAD"]
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = tq.main(argv)
            self.assertEqual(code, 1, "a post-cutover item is the defect")
            self.assertIn("new item", out.getvalue())
            self.assertNotIn("old item", out.getvalue())

    def test_question_numbering_only_grows(self):
        payload = data([task("a", 1.0)])
        row = {"id": 5, "summary": "s", "status": "open", "provenance": "p", "asked": "2026-11-03"}
        payload["questions"] = [row, dict(row, id=3)]
        with self.assertRaises(tq.QueueError):
            tq.validate(payload)
        payload["questions"] = [row, dict(row)]
        with self.assertRaises(tq.QueueError):
            tq.validate(payload)

    def test_questions_command_lists_only_open_rows(self):
        payload = data([task("a", 1.0)])
        payload["questions"] = [
            {"id": 1, "summary": "settled thing", "status": "answered 2026-11-02",
             "provenance": "p", "asked": "2026-11-01"},
            {"id": 2, "summary": "open thing", "status": "open", "provenance": "p",
             "asked": "2026-11-03"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(tq.main(["--file", str(path), "questions"]), 0)
            text = out.getvalue()
            self.assertIn("open thing", text)
            self.assertNotIn("settled thing", text, "a settled row leaves the array")


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

class AtomicSave(unittest.TestCase):
    """A torn write here does not look like corruption -- JSON stays valid while rows vanish."""

    def test_a_failed_replace_leaves_the_register_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"
            path.write_text(json.dumps({"priority_models": [], "tasks": [task("a", 1.0)]}), encoding="utf-8")
            before = path.read_bytes()
            data = tq.load(path)
            orig = tq.os.replace
            tq.os.replace = lambda *a, **k: (_ for _ in ()).throw(OSError("boom"))
            try:
                with self.assertRaises(OSError):
                    tq._save(path, data, [task("a", 1.0), task("b", 2.0)], row="b")
            finally:
                tq.os.replace = orig
            self.assertEqual(path.read_bytes(), before, "the register must be unchanged")
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["queue.json"], "no temp file left")

    def test_the_saved_register_keeps_its_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"
            path.write_text(json.dumps({"priority_models": [], "tasks": []}), encoding="utf-8")
            path.chmod(0o640)
            data = tq.load(path)
            tq._save(path, data, [task("a", 1.0)], row="a")
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)


class StaleWrite(unittest.TestCase):
    """A whole-file replace must lose to a peer write, not overwrite it from a stale snapshot.

    Measured 2026-11-11: a fold driver holding a pre-update snapshot reverted three machine-runnable
    fields a peer had just written, because `_save` replaced the whole tasks list.
    """

    @staticmethod
    def _register(path: Path, tasks: list) -> None:
        path.write_text(json.dumps({"priority_models": [], "tasks": tasks}, indent=2) + "\n",
                        encoding="utf-8")

    def test_a_stale_writer_refuses_nonzero_and_leaves_the_peer_row_and_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"
            self._register(path, [task("a", 1.0)])
            first, stale = tq.load(path), tq.load(path)
            peer = first["tasks"][0]
            peer["state"] = "running"
            peer["claimed_by"] = "session:peer"
            peer["claimed_at"] = "2026-11-11T06:00:00Z"
            first["tasks"].append(task("b", 2.0))
            relink(first["tasks"])
            tq._save(path, first, first["tasks"], row="b")
            written = path.read_bytes()

            # The stale process runs `update` against the snapshot it loaded before the peer wrote.
            stale["tasks"][0]["title"] = "clobbered"
            orig_load = tq.load
            tq.load = lambda _path: stale
            err = io.StringIO()
            try:
                with contextlib.redirect_stderr(err):
                    rc = tq.main(["--file", str(path), "update", "--id", "a", "--title", "clobbered"])
            finally:
                tq.load = orig_load

            self.assertEqual(rc, 1, "a stale writer must exit non-zero")
            message = err.getvalue()
            self.assertIn("a:", message, "the refusal names the row")
            self.assertIn("changed on disk", message)
            self.assertIn(f"read it on {socket.gethostname()}", message,
                          "the refusal names the host whose snapshot is stale")
            self.assertEqual(path.read_bytes(), written, "nothing written")

            reloaded = {row["id"]: row for row in tq.load(path)["tasks"]}
            self.assertEqual(sorted(reloaded), ["a", "b"], "the peer's row survives")
            self.assertEqual(reloaded["a"]["claimed_by"], "session:peer", "the live claim survives")
            self.assertEqual(reloaded["a"]["title"], "a", "the stale title is not applied")

    def test_a_single_writer_still_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"
            self._register(path, [task("a", 1.0)])
            data = tq.load(path)
            data["tasks"][0]["title"] = "renamed"
            tq._save(path, data, data["tasks"], row="a")
            self.assertEqual(tq.load(path)["tasks"][0]["title"], "renamed")

    def test_a_done_transition_still_clears_the_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"
            running = task("a", 1.0, state="running")
            running["claimed_by"] = "session:tp4-20261111"
            running["claimed_at"] = "2026-11-11T05:23:37Z"
            self._register(path, [running])
            self.assertEqual(tq.main(["--file", str(path), "done", "--id", "a"]), 0)
            row = tq.load(path)["tasks"][0]
            self.assertEqual(row["state"], "done")
            self.assertEqual((row["claimed_by"], row["claimed_at"]), ("", ""))


class TitleMonotonicity(unittest.TestCase):
    """A tick fixes its census before taking the board lock, so its whole-file rewrite can carry
    an older title than the committed board.  Three such regressions landed on 2026-11-06
    (15:00 -> 13:56 and 15:49 -> 15:28 measured), each reverting rows a fresher board held."""

    BOARD = (
        "# Board — generated {stamp} ET\n\n"
        "## In flight\n\n"
        "| where | owner | what |\n|---|---|---|\n| census | tick | 0 containers |\n"
        "| pool | — | serving |\n| queue | — | 0 open |\n| window | — | none |\n"
        "| campaign | — | idle |\n| publication | tick | base |\n"
    )

    def _repo(self, tmp, stamp):
        import subprocess
        root = Path(tmp)
        path = root / "STATUS.md"
        path.write_text(self.BOARD.format(stamp=stamp), encoding="utf-8")
        env = ["-c", "user.email=g@example.invalid", "-c", "user.name=g"]
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", *env, "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", *env, "commit", "-qm", "board"], cwd=root, check=True)
        return path

    def test_a_stale_title_is_refused(self):
        # Negative control: the pre-fix `lint` only checked markdown and passed this rewrite.
        with tempfile.TemporaryDirectory() as tmp:
            path = self._repo(tmp, "2026-11-06 15:49")
            path.write_text(self.BOARD.format(stamp="2026-11-06 13:56"), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()) as out, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(tq.main(["lint", str(path)]), 1)
            self.assertIn("title-regression", out.getvalue())

    def test_a_fresh_title_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._repo(tmp, "2026-11-06 15:49")
            path.write_text(self.BOARD.format(stamp="2026-11-06 16:04"), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tq.main(["lint", str(path)]), 0)

    def test_a_title_ahead_of_the_clock_is_refused(self):
        # Negative control: pre-fix `lint` passed a future title, and the next tick then lost nine
        # minutes because title-regression refused its honest stamp (measured 2026-11-07 17:10).
        ahead = (dt.datetime.now() + dt.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        with tempfile.TemporaryDirectory() as tmp:
            path = self._repo(tmp, "2026-11-06 15:49")
            path.write_text(self.BOARD.format(stamp=ahead), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(tq.main(["lint", str(path)]), 1)
            self.assertIn("future-stamp", out.getvalue())

    def test_the_current_minute_is_not_future(self):
        now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        with tempfile.TemporaryDirectory() as tmp:
            path = self._repo(tmp, "2026-11-06 15:49")
            path.write_text(self.BOARD.format(stamp=now), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tq.main(["lint", str(path)]), 0)


class BoardAndArchive(unittest.TestCase):
    """`render --board` and `orphans`: the queue is the register, TODO.md is the archive."""

    def test_board_emits_the_status_columns(self):
        payload = data([task("b", 1.0), task("a", 2.0, ["b"])])
        rows = tq.board_rows(payload)
        self.assertEqual(rows[0], "| job | node cost | holds | state |")
        self.assertTrue(all(r.count("|") == 5 for r in rows), "four columns, as the board has")
        body = "\n".join(rows[2:])
        self.assertIn("`a`", body)
        self.assertIn("`b`", body)
        self.assertIn("queued", body)

    def test_board_carries_notes_and_evidence(self):
        t = task("a", 1.0)
        t["notes"] = "why this arm exists"
        t["evidence"] = "~/benchmarks/lane-20261103/REPORT.md"
        body = "\n".join(tq.board_rows(data([t])))
        self.assertIn("why this arm exists", body)
        self.assertIn("evidence: `~/benchmarks/lane-20261103/REPORT.md`", body)

    def test_board_survives_multiline_and_piped_notes(self):
        # A note is prose: a newline here ends the markdown table, a raw pipe splits the cell.
        t = task("a", 1.0)
        t["notes"] = "first line\n\nFraming: `p50` vs NVMe | staging withdrawn"
        rows = tq.board_rows(data([t]))
        self.assertEqual(len(rows), 3, "one row per task, never a wrapped line")
        self.assertTrue(all(len(re.split(r"(?<!\\)\|", r)) == 6 for r in rows), "four cells per row")
        self.assertIn(r"vs NVMe \| staging", rows[2])
        self.assertIn("first line Framing:", rows[2])

    def test_a_long_note_is_truncated_to_a_pointed_at_register(self):
        """Measured 2026-11-08 14:10 ET: whole notes put 75 821 B in the 23-row work queue, and
        the 82 136 B board was read by every tick before it wrote one census row."""
        t = task("a", 1.0)
        t["notes"] = "a justification the register alone should hold. " * 90
        rows = tq.board_rows(data([t]))
        self.assertEqual(len(rows), 3, "one row per task, never a wrapped line")
        self.assertLess(max(len(r.encode()) for r in rows), 400,
                        "one board row carries a note's opening, not the note")
        self.assertIn("full note: queue.json", rows[2])
        self.assertNotIn(t["notes"], rows[2])
        self.assertEqual(t["notes"], "a justification the register alone should hold. " * 90,
                         "rendering never rewrites the register row")

    def test_a_note_at_the_budget_is_quoted_whole(self):
        """Boundary and negative control: only the over-budget note gains the pointer."""
        t = task("a", 1.0)
        t["notes"] = "x" * tq.NOTE_BUDGET
        row = tq.board_rows(data([t]))[2]
        self.assertIn("x" * tq.NOTE_BUDGET, row)
        self.assertNotIn("full note: queue.json", row)
        t["notes"] = "x" * (tq.NOTE_BUDGET + 1)
        row = tq.board_rows(data([t]))[2]
        self.assertIn("…", row)
        self.assertIn("full note: queue.json", row)
        self.assertNotIn("x" * (tq.NOTE_BUDGET + 1), row)
        # Boundary the live register hit on 2026-11-12: a cut inside a code span leaves one
        # backtick, `lint_markdown` rejects that cell and `render --board` refuses to emit.
        t["notes"] = "y" * (tq.NOTE_BUDGET - 4) + "`abc`" + "z" * 40
        row = tq.board_rows(data([t]))[2]
        self.assertEqual(row.count("`") % 2, 0, "a truncated code span drops its opening stub")
        self.assertNotIn("`abc", row)

    def test_evidence_must_be_a_string(self):
        # Negative control: a non-string evidence is a data defect, never silently ignored.
        payload = data([task("a", 1.0)])
        payload["tasks"][0]["evidence"] = ["a", "list"]
        with self.assertRaises(tq.QueueError):
            tq.validate(payload)

    def test_orphans_flags_an_unmarked_item(self):
        text = "## lane\n- [ ] **Fix the thing** — detail\n"
        orphans, dead = tq.todo_orphans(text, [task("a", 1.0)])
        self.assertEqual([t for _line, t in orphans], ["Fix the thing"])
        self.assertEqual(dead, [])

    def test_orphans_accepts_a_live_marker_on_the_next_line(self):
        text = "- [ ] **Fix the thing** — detail\n  <!-- queue: a -->\n"
        orphans, dead = tq.todo_orphans(text, [task("a", 1.0)])
        self.assertEqual((orphans, dead), ([], []))

    def test_orphans_flags_a_dead_marker(self):
        # A renamed task must not silently orphan the text its old marker covered.
        text = "- [ ] **Fix the thing** <!-- queue: renamed-away -->\n"
        orphans, dead = tq.todo_orphans(text, [task("a", 1.0)])
        self.assertEqual(orphans, [])
        self.assertEqual([ref for _line, _t, ref in dead], ["renamed-away"])

    def test_orphans_allow_permits_grandfathered_but_not_growth(self):
        # The bound is the cutover, not an amnesty: the archive's pre-freeze items are
        # tolerated, one new unmarked item is not.
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue.json"
            queue.write_text(json.dumps(data([task("a", 1.0)])), encoding="utf-8")
            todo = Path(tmp) / "TODO.md"
            todo.write_text("- [ ] **one**\n- [ ] **two**\n", encoding="utf-8")
            argv = ["--file", str(queue), "orphans", "--todo", str(todo), "--allow", "2"]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tq.main(argv), 0, "the frozen count is tolerated")
                with open(todo, "a", encoding="utf-8") as fh:
                    fh.write("- [ ] **three**\n")
                self.assertEqual(tq.main(argv), 1, "growth past the bound is the defect")

    def test_archive_does_not_grow(self):
        """TODO.md is frozen: its open-item count may not move without a queue row.

        52 is the archive's open-item count at the 2026-11-03 freeze, when the register
        became `mad-science/queue.json` and the board began rendering from it. The count
        is pinned rather than matched item-by-item because the archive's text is evidence,
        not schedule — importing it into JSON would be a second restatement of prose. A
        genuinely new item goes to the queue; if one legitimately lands in the archive,
        import it and bump this number in the same commit.
        """
        todo = REPO_ROOT / "mad-science" / "TODO.md"
        payload = json.loads((REPO_ROOT / "mad-science" / "queue.json").read_text(encoding="utf-8"))
        orphans, dead = tq.todo_orphans(todo.read_text(encoding="utf-8"), tq.validate(payload))
        self.assertEqual(dead, [], "a marker naming an unknown task")
        self.assertEqual(len(orphans), 52,
                         "the archive grew (or shrank without a marker): " +
                         "; ".join(t for _line, t in orphans[:5]))


class MarkdownLint(unittest.TestCase):
    """`lint`: a table that GFM will not render is refused before it is published.

    The defect this exists for shipped twice (2026-10-22 and 2026-11-03, `6f19662` and the
    landed table below): a header row followed straight by data rows, with no
    `|---|---|---|` delimiter, which GFM does not read as a table at all — every row becomes
    one paragraph of literal pipes. `render --board` now refuses its own output, and the
    board itself is linted here because the tick that writes the rest of the file runs
    outside this repo.
    """

    # The board's landed table as it was published on 2026-11-03: header, then a data row.
    BROKEN = (
        "## Landed session\n\n"
        "| time ET | commit | one clause |\n"
        "| 16:32 ET | `15f5bcd` | a clause |\n"
        "| 16:34 ET | `c4e5d53` | another clause |\n"
    )

    def test_missing_delimiter_is_caught(self):
        # Negative control: the pre-fix block above must be flagged, or the guard proves nothing.
        rules = [r for _line, r, _d in tq.lint_markdown(self.BROKEN)]
        self.assertEqual(rules, ["table-missing-delimiter"])

    def test_delimiter_makes_the_same_block_render(self):
        fixed = self.BROKEN.replace("| one clause |\n", "| one clause |\n|---|---|---|\n")
        self.assertEqual(tq.lint_markdown(fixed), [])

    def test_ragged_row_is_caught(self):
        text = "| a | b | c |\n|---|---|---|\n| 1 | 2 |\n"
        self.assertEqual([r for _l, r, _d in tq.lint_markdown(text)], ["table-ragged"])

    def test_pipe_inside_a_code_span_is_caught(self):
        # GFM splits cells before parsing inline markup, so a piped shell command needs `\\|`.
        text = "| a | b |\n|---|---|\n| `find . -name x | wc -l` | y |\n"
        rules = [r for _l, r, _d in tq.lint_markdown(text)]
        self.assertIn("pipe-in-code-span", rules)
        escaped = text.replace("-name x | wc", r"-name x \| wc")
        self.assertEqual(tq.lint_markdown(escaped), [])

    def test_unclosed_fence_is_caught(self):
        rules = [r for _l, r, _d in tq.lint_markdown("```\nnot a table | x |\n")]
        self.assertEqual(rules, ["unclosed-fence"])

    def test_generated_board_lints_clean(self):
        payload = data([task("a", 1.0, model="glm-5.3"),
                        task("b", 2.0, model="deepseek-v4.1-flash-1017", state="blocked")])
        t = payload["tasks"][0]
        t["notes"] = "a pipe | and a newline\ninside prose"
        rows = tq.board_rows(payload)
        self.assertEqual(tq.lint_markdown("\n".join(rows)), [])

    def test_render_refuses_markdown_it_would_break(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(tq.QueueError):
                tq._emit(["| a | b |", "| 1 | 2 |"], "test table")

    def test_a_mermaid_fence_under_the_work_queue_heading_renders(self):
        """The board carries `graph`'s block directly under `## Work queue`: lint must accept it.

        The fence is skipped by the table walker, which is the smallest change that works --
        what is pinned here is that a fenced block never turns into a phantom table, and that a
        real board (graph rows + the rendered table) lint-clean in one file.
        """
        graph, _ = tq.graph_body(data([task("a", 1.0, ["b"]), task("b", 1.0, state="blocked")]))
        rows = tq.board_rows(data([task("a", 1.0, ["b"]), task("b", 1.0, state="blocked")]))
        board = ("## Work queue\n\n```mermaid\n" + "\n".join(graph) + "\n```\n\n" + "\n".join(rows))
        self.assertEqual(tq.lint_markdown(board), [])
        # ...and a header with no delimiter row is still refused, fence or not.
        broken = board + "\n\n| a | b |\n| 1 | 2 |\n"
        self.assertIn("table-missing-delimiter", [r for _l, r, _d in tq.lint_markdown(broken)])

    def test_harness_transcript_lines_are_caught_outside_a_fence(self):
        """Measured 2026-11-09 12:10-12:12 ET: a tick captured `graph`'s output into a file and
        the shell also echoed the harness's stderr, so `--- stderr ---` and uv's `VIRTUAL_ENV`
        warning landed between the mermaid fence and the job table. `publish` exited 0 and `lint`
        printed `ok: 1 markdown file(s) render`; the banner reached the clone's board and was
        caught only by a reader before the commit."""
        head = "```mermaid\ngraph TD\n```\n\n"
        for banner in ("--- stderr ---", "warning: VIRTUAL_ENV=/tmp/x does not match"):
            self.subTest(banner=banner)
            text = head + banner + "\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"
            self.assertEqual([(line, rule) for line, rule, _d in tq.lint_markdown(text)],
                             [(5, "harness-transcript")], "line number names the banner")
            # The same line inside a fence is documentation, not a transcript.
            self.assertEqual(tq.lint_markdown("```\n" + banner + "\n```\n"), [])
        self.assertEqual(tq.lint_markdown(head + "| a | b |\n|---|---|\n| 1 | 2 |\n"), [])

    def test_the_board_renders(self):
        """The published board: every table it carries must parse."""
        board = REPO_ROOT / "mad-science" / "STATUS.md"
        self.assertEqual(tq.lint_markdown(board.read_text(encoding="utf-8")), [])

    def test_live_zone_docs_this_guard_owns_render(self):
        # Files this guard fixed and now protects. NOT the whole tree: `attic/` is frozen
        # provenance, and SESSION-RECORD's ledger fragments are mid-table continuations whose
        # header lives elsewhere — minting headers there would rewrite history, not fix it.
        for rel in ("tools/README.md",
                    "recipes/ornith/README.md",
                    "recipes/glm/mods/tensorfold-glm53-3bpw-launcher/README.md"):
            with self.subTest(file=rel):
                path = REPO_ROOT / rel
                self.assertEqual(tq.lint_markdown(path.read_text(encoding="utf-8")), [])


class DependencyGraph(unittest.TestCase):
    """`graph`: the register's *connected* open work as one mermaid block, no baked colours.

    A `blocked_by`-only graph would draw disconnected boxes and assert that nothing depends on
    anything: measured 2026-11-08, every *open* blocked row stores `blocked_by: []` while its gate
    is an owner-question citation. The default view therefore draws only rows that take part in an
    edge, in either direction -- 9 nodes and 6 edges instead of 27 boxes, 18 of them isolated --
    and the counts comment names what it left out. `--all` draws every open row.
    """

    def test_the_connected_view_draws_only_edge_participants(self):
        rows = relink([task("a", 1.0, ["b"]), task("b", 1.0),
                       task("c", 1.0, state="blocked"), task("d", 1.0)])
        body, _ = tq.graph_body(qdata(rows, [67]))
        text = "\n".join(body)
        self.assertIn('t1["a · queued"]', text)
        self.assertIn('t2["b · queued"]', text)
        self.assertNotIn("c · blocked", text, "a gated row with no edge is not drawn")
        self.assertNotIn('d · queued', text)
        self.assertIn("2 rows not drawn (--all)", text)

    def test_all_draws_every_open_row(self):
        rows = relink([task("a", 1.0, ["b"]), task("b", 1.0),
                       task("c", 1.0, state="blocked"), task("d", 1.0)])
        body, _ = tq.graph_body(qdata(rows, [67]), all_rows=True)
        text = "\n".join(body)
        for label in ("a · queued", "b · queued", "c · blocked · owner", "d · queued"):
            self.assertIn(label, text)
        self.assertNotIn("rows not drawn", text, "nothing is omitted in the --all view")

    def test_a_gated_row_is_drawn_dashed_only_in_the_all_view(self):
        body, _ = tq.graph_body(qdata([task("lonely", 1.0, state="blocked")], [67]))
        self.assertIn("no edge recorded among the open rows", "\n".join(body))
        self.assertNotIn("-->", "\n".join(body))
        full, _ = tq.graph_body(qdata([task("lonely", 1.0, state="blocked")], [67]),
                                all_rows=True)
        self.assertIn('· blocked · owner"]:::no-recorded-edge', "\n".join(full))

    def test_sparse_register_still_draws_the_question_edges(self):
        rows = [task("blocked-a", 1.0, state="blocked"), task("blocked-b", 1.0, state="blocked")]
        rows[0]["notes"] = "waiting on host policy (QUESTIONS.md #67)"
        rows[1]["notes"] = "gated by prose, no citation"
        body, warnings = tq.graph_body(qdata(rows, [67]))
        text = "\n".join(body)
        self.assertIn('Q67 · owner question 67', text)
        self.assertIn("q67 --> t1", text)                 # the citation is a real edge
        self.assertNotIn("blocked-b", text)               # the uncited row is the omission
        self.assertIn("2 blocked, 0 edges, 1 prose-gated, 1 question-gated, 1 question, "
                      "1 rows not drawn (--all)", text)
        self.assertEqual(warnings, [])

    def test_the_counts_comment_names_the_rows_not_drawn(self):
        rows = relink([task("a", 1.0, ["b"]), task("b", 1.0), task("c", 1.0, state="blocked"),
                       task("d", 1.0), task("e", 1.0)])
        rows[2]["notes"] = "#67"
        body, _ = tq.graph_body(qdata(rows, [67]))
        omitted = sum(1 for t in rows if t["state"] != "done") - 3   # a, b, c participate
        self.assertIn(f"{omitted} rows not drawn (--all)", "\n".join(body))

    def test_a_diamond_has_exactly_its_four_edges(self):
        tasks = relink([task("a", 1.0, ["b", "c"]), task("b", 1.0, ["d"]),
                        task("c", 1.0, ["d"]), task("d", 1.0)])
        body, warnings = tq.graph_body({"priority_models": ["x"], "tasks": tasks})
        self.assertEqual([l.strip() for l in body if "-->" in l],
                         ["t1 --> t2", "t1 --> t3", "t2 --> t4", "t3 --> t4"])
        self.assertEqual(warnings, [])

    def test_a_mirror_disagreement_warns_and_blocks_stays_authoritative(self):
        """`blocked_by` is `_relink`'s mirror of `blocks`; a mismatch is a register mid-edit."""
        a = task("aa", 1.0, ["bb"])
        b = task("bb", 1.0)
        b["blocked_by"] = ["cc"]          # a parent that does not name it back
        c = task("cc", 1.0)
        body, warnings = tq.graph_body({"priority_models": ["x"], "tasks": [a, b, c]})
        self.assertIn("aa -> bb: in aa.blocks, but blocked_by does not name it", warnings)
        self.assertIn("cc -> bb: in blocked_by, but cc.blocks does not name it", warnings)
        self.assertEqual([l.strip() for l in body if "-->" in l], ["t1 --> t2"],
                         "only the authoritative `blocks` edge is drawn")

    def test_max_nodes_collapses_the_rest_into_one_node(self):
        rows = [task(f"row-{i:02d}", 1.0) for i in range(10)]
        body, _ = tq.graph_body({"priority_models": ["x"], "tasks": rows},
                                max_nodes=5, all_rows=True)
        text = "\n".join(body)
        self.assertIn("%% truncated: 4 shown of 10", text)
        self.assertIn('tn["… 6 more open rows (see the table)"]', text)

    def test_output_is_byte_deterministic_and_sorted_by_id(self):
        rows = relink([task("z", 1.0), task("m", 1.0, ["z"]), task("a", 1.0)])
        first, _ = tq.graph_body({"priority_models": ["x"], "tasks": rows}, all_rows=True)
        second, _ = tq.graph_body({"priority_models": ["x"], "tasks": [rows[2], rows[0], rows[1]]},
                                  all_rows=True)
        self.assertEqual(first, second, "dict order must not reach the output")
        self.assertTrue(first[2].startswith('  t1["a · '), first[2])

    def test_a_long_label_is_truncated_only_past_the_cap(self):
        forty = "a" * 40
        long = "b" * (tq.GRAPH_LABEL + 1)
        rows = relink([task(forty, 1.0, [long]), task(long, 1.0)])
        text = "\n".join(tq.graph_body({"priority_models": ["x"], "tasks": rows})[0])
        self.assertIn(forty, text, "a 40-character id is emitted whole")
        self.assertIn("b" * tq.GRAPH_LABEL + "…", text)
        self.assertNotIn(long, text)

    def style_findings(self, block, expected_classes):
        """What the owner's style rule forbids: colour literals, and any class name but the rule.

        Mermaid ignores an unknown class silently, so a dead `:::queued` on an ordinary node
        renders fine and rots unseen -- a no-colour regex cannot see it, which is why the class
        set is asserted too.
        """
        problems = []
        if re.search(r"#[0-9a-fA-F]{3,8}\b", block):
            problems.append("a colour literal in the block")
        defs = [line for line in block.splitlines() if "classDef" in line]
        if len(defs) != 1:
            problems.append(f"{len(defs)} classDef lines, expected exactly one")
        for line in defs:
            if "stroke-dasharray" not in line:
                problems.append("the classDef is not the dashed-stroke rule")
            if "fill:" in line or "color:" in line:
                problems.append("the classDef sets fill or colour")
        classes = set(re.findall(r":::([A-Za-z0-9_-]+)", block))
        if classes != set(expected_classes):
            problems.append(f"class references {sorted(classes)}, expected {sorted(expected_classes)}")
        return problems

    def test_the_block_carries_no_baked_colour_and_only_the_dashed_class(self):
        rows = relink([task("a", 1.0, ["b"]), task("b", 1.0, state="blocked"),
                       task("c", 1.0, state="blocked")])
        connected = "\n".join(tq.graph_body(qdata(rows, [67]))[0])
        everything = "\n".join(tq.graph_body(qdata(rows, [67]), all_rows=True)[0])
        self.assertEqual(self.style_findings(connected, set()), [],
                         "the theme styles ordinary nodes; they carry no class at all")
        self.assertEqual(self.style_findings(everything, {"no-recorded-edge"}), [],
                         "the only class a block may name is the dashed stroke rule")
        self.assertIn("classDef no-recorded-edge stroke-dasharray: 4 3", everything)
        # Negative control (palette): the pre-fix classDef must be caught.
        planted_palette = everything + "\n  classDef queued fill:#dbeafe\n"
        self.assertIn("a colour literal in the block",
                      self.style_findings(planted_palette, {"no-recorded-edge"}))
        # Negative control (dead class): a colour-free `:::queued` must be caught too.
        planted_class = connected.replace('t1["a · queued"]', 't1["a · queued"]:::queued')
        self.assertNotEqual(planted_class, connected, "the mutation must change the block")
        self.assertIn("class references ['queued'], expected []",
                      self.style_findings(planted_class, set()))

    def test_an_empty_register_emits_a_block_that_says_so(self):
        body, warnings = tq.graph_body({"priority_models": [], "tasks": []})
        self.assertIn("no open rows in the register", "\n".join(body))
        self.assertEqual(warnings, [])

    def test_the_cli_prints_exactly_one_fence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"
            path.write_text(json.dumps(qdata([task("a", 1.0, state="blocked")], [67])),
                            encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                tq.cmd_graph(types.SimpleNamespace(max_nodes=tq.GRAPH_BUDGET), path)
        lines = out.getvalue().splitlines()
        self.assertEqual(lines[0], "```mermaid")
        self.assertEqual([l for l in lines if l.startswith("```")], ["```mermaid", "```"])


class GraphFileFlag(unittest.TestCase):
    """`--file` must mean the same thing before and after the `graph` subcommand.

    Measured 2026-11-08 by the board tick: `--file X graph` printed `2 edges, 11 prose-gated`
    from the default register while `graph --file Y` printed the true `3 edges, 9 prose-gated`.
    The subparser's own `--file` default overwrote the parent's parsed value, so a plausible
    diagram was drawn from the wrong file with no error -- and the rows it lost were exactly the
    ones that make the graph worth drawing.
    """

    def _write(self, path, rows):
        path.write_text(json.dumps(qdata(relink(rows), [67])), encoding="utf-8")

    def _graph(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(tq.main(argv), 0)
        return out.getvalue()

    def test_both_positions_read_the_named_file_and_the_outputs_differ(self):
        with tempfile.TemporaryDirectory() as tmp:
            two, three = Path(tmp) / "two.json", Path(tmp) / "three.json"
            self._write(two, [task("row-a", 1.0), task("row-b", 1.0, ["row-a"])])
            self._write(three, [task("one", 1.0, ["two"]), task("two", 2.0, ["three"]),
                                task("three", 3.0, state="blocked")])
            pre = self._graph(["--file", str(two), "graph"])
            post = self._graph(["graph", "--file", str(two)])
            self.assertEqual(pre, post, "the flag's position must not change the register read")
            self.assertIn("row-a", pre)
            other = self._graph(["graph", "--file", str(three)])
            self.assertNotEqual(pre, other)
            self.assertIn("one", other)
            self.assertIn("2 edges", other)

    def test_the_parent_flag_never_falls_back_to_the_default_register(self):
        """Negative control: a default register in cwd must not be read when `--file` was given."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mad-science").mkdir()
            (root / "mad-science" / "queue.json").write_text(
                json.dumps(qdata([task("default-row", 1.0)], [])), encoding="utf-8")
            named = root / "named.json"
            # an edge, so the connected view draws it and the label proves which file was read
            self._write(named, [task("named-row", 1.0, ["named-other"]),
                                task("named-other", 1.0, state="blocked")])
            cwd = os.getcwd()
            os.chdir(root)
            try:
                text = self._graph(["--file", str(named), "graph"])
            finally:
                os.chdir(cwd)
        self.assertIn("named-row", text)
        self.assertNotIn("default-row", text, "the pre-subcommand --file must be honoured")


class AddressLint(unittest.TestCase):
    """`lint` refuses a raw cluster address or hostname, as `publish` already does.

    Measured twice on 2026-11-08: a board quoted a host verbatim and the tip redded every
    session after it. `lint` is the tick's own last step before the commit, so the refusal
    belongs there too. The literals are assembled in code, not written out: this test file
    is itself tracked, and a literal here would trip the guard it proves.
    """

    @staticmethod
    def samples() -> tuple[str, ...]:
        return (
            ".".join(("10", "0", "4", "30")),
            ".".join(("192", "168", "1", "7")),
            ".".join(("172", "20", "0", "9")),
            "spark-" + "head",
            "spark-" + "01",
        )

    def lint(self, text: str) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "STATUS.md"
            path.write_text(text, encoding="utf-8")
            args = type("Args", (), {"paths": [str(path)]})()
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    tq.cmd_lint(args, path)
                except tq.QueueError:
                    return 1, out.getvalue() + err.getvalue()
            return 0, out.getvalue() + err.getvalue()

    def test_a_raw_address_is_refused(self):
        code, out = self.lint(f"held {self.samples()[0]} while waiting\n")
        self.assertEqual(code, 1, out)
        self.assertIn("cluster-address", out)
        self.assertIn("`.NN`", out, "the refusal does not say what to write instead")

    def test_the_rank_shorthand_passes(self):
        code, out = self.lint("held the rank host (`.30`) while waiting\n")
        self.assertEqual((code, out), (0, "ok: 1 markdown file(s) render\n"))

    def test_a_head_or_fleet_hostname_is_refused(self):
        for host in ("spark-" + "head", "spark-" + "01", "spark-" + "05"):
            with self.subTest(host=host):
                code, out = self.lint(f"launched on {host}\n")
                self.assertEqual(code, 1, out)
                self.assertIn("cluster-address", out)

    def test_negative_control_markdown_lint_alone_misses_it(self):
        # The pre-fix behaviour: the board renders, so only the address rule can refuse it.
        self.assertEqual(tq.lint_markdown(f"held {self.samples()[0]} while waiting\n"), [])

    def test_the_two_pattern_sources_agree(self):
        """tools/ may not import tests/, so one sample set must trip both mirrored copies."""
        spec = importlib.util.spec_from_file_location(
            "test_tracked_address_hygiene",
            REPO_ROOT / "tests" / "test_tracked_address_hygiene.py")
        assert spec is not None and spec.loader is not None
        hygiene = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hygiene)
        for sample in self.samples():
            with self.subTest(sample=sample):
                self.assertTrue(tq.address_problems(sample), "the tool copy misses it")
                self.assertTrue(hygiene.ADDRESS.search(sample) or hygiene.HOST.search(sample),
                                "the hygiene copy misses it")
        for allowed in ("rank .31 and .32", "spark-of-the-line"):
            with self.subTest(allowed=allowed):
                self.assertEqual(tq.address_problems(allowed), [])
                self.assertFalse(hygiene.ADDRESS.search(allowed) or hygiene.HOST.search(allowed))


class InflightRows(unittest.TestCase):
    """`lint`/`publish` refuse a board whose `## In flight` table lost a state row.

    Measured 2026-11-11 03:14-03:25 ET: the 03:14 board carried a `| queue |` row, the 03:17 board
    did not, and the next tick — which keeps its base's body verbatim — published without it through
    `publish` rc=0, `lint` ok and a green push gate. Every guard compares bytes against that base, so
    a base already missing the row is indistinguishable from a good one; the row set is the witness.
    """

    ROWS = ("| census | tick | read |\n| pool | — | serving |\n| queue | — | 50 open |\n"
            "| window | — | none |\n| campaign | — | idle |\n| publication | tick | base |\n")

    def board(self, rows):
        return ("# Board — generated 2026-11-11 03:21 ET\n\n## In flight\n\n"
                "| where | owner | what |\n|---|---|---|\n" + rows)

    def test_the_full_row_set_passes(self):
        self.assertEqual(tq.inflight_problems(self.board(self.ROWS)), [])

    def test_a_dropped_row_is_named(self):
        # Negative control: the shrunken table must be flagged, or the guard proves nothing.
        problems = tq.inflight_problems(self.board(self.ROWS.replace("| queue | — | 50 open |\n", "")))
        self.assertEqual([rule for _line, rule, _detail in problems], ["inflight-row-missing"])
        self.assertIn("`queue`", problems[0][2])
        self.assertNotIn("`pool`", problems[0][2])

    def test_nodes_and_the_quartet_row_are_parsed_as_keys(self):
        """The parser must read the real table shape, or every check above passes vacuously."""
        keys = tq.inflight_keys(self.board(
            self.ROWS + "| .31 | rank node_0 | 1 container |\n"
                        "| quartet `1ca17b467dcda1cc` | peer session | booting |\n"))
        self.assertIn(".31", keys)
        self.assertIn("quartet", keys)

    def test_a_board_without_the_section_is_not_reported(self):
        """This rule reports a loss, not a shape: any other markdown file stays lintable."""
        self.assertEqual(tq.inflight_problems("# Notes\n\n| a | b |\n|---|---|\n"), [])

    def test_lint_refuses_the_shrunken_board(self):
        target = Path(tempfile.mkdtemp()) / "STATUS.md"
        target.write_text(self.board(self.ROWS.replace("| queue | — | 50 open |\n", "")),
                          encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(tq.main(["lint", str(target)]), 1)
        target.write_text(self.board(self.ROWS), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(tq.main(["lint", str(target)]), 0)


def board_text(census, title=None):
    """Minimal board carrying one census stamp — the only part `publish` reads."""
    title = title or census[:16]
    # Every `_INFLIGHT_REQUIRED` row, because a board that lost one is exactly what publish refuses:
    # a fixture carrying only `census` would test a shape no real board has ever had.
    return (f"# Board — generated {title} ET\n\n"
            "## In flight\n\n| where | owner | what |\n|---|---|---|\n"
            f"| census | this tick | **{census} ET** measured |\n"
            "| pool | — | serving |\n| queue | — | 0 open |\n| window | — | none |\n"
            "| campaign | — | idle |\n| publication | tick | base sha |\n\n"
            "## Work queue\n\n| job | node cost | holds | state |\n|---|---|---|---|\n\n"
            "## Landed session\n\n| time ET | commit | one clause |\n|---|---|---|\n")


class BoardPublish(unittest.TestCase):
    """`publish`: a board older than the one on disk is refused, never written.

    The defect it exists for is measured, not hypothetical: on 2026-11-06 three ticks landed inside
    50 minutes and a peer whose census read 13:56 ET wrote it *after* a 15:15 ET board, so the file
    went backwards. `flock` serializes writers and cannot stop a slow one, so the freshness
    comparison has to happen inside the lock, against the board's own census stamp.
    """

    OLD = "2026-11-06 13:56:04"
    NEW = "2026-11-06 16:02:09"

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.board = self.dir / "STATUS.md"
        self.lock = self.dir / "board.lock"

    def publish(self, text, wait=None, expect_sha=None, base=None, remote_sha=None):
        if base is None and expect_sha is None and remote_sha is None:
            # The tick's own read: with no guard flag publish fails closed, so default to --base.
            base = self.dir / "base.md"
            base.write_text(self.board.read_text(encoding="utf-8"), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            saved, sys.stdin = sys.stdin, io.StringIO(text)
            try:
                argv = ["publish", "--board", str(self.board), "--lock", str(self.lock)]
                if wait is not None:
                    argv += ["--lock-wait", wait]
                if expect_sha is not None:
                    argv += ["--expect-sha", expect_sha]
                if remote_sha is not None:
                    argv += ["--expect-remote-sha", remote_sha]
                if base is not None:
                    argv += ["--base", str(base)]
                return tq.main(argv)
            finally:
                sys.stdin = saved

    def _commit_board(self, text):
        """Commit `text` as STATUS.md, push it to `origin/main`, and return the composed sha.

        Also leaves those bytes on disk, because that is the state a publisher reads.
        """
        self.board.write_text(text, encoding="utf-8")
        git = ["git", "-C", str(self.dir), "-c", "user.email=tick@test", "-c", "user.name=tick"]
        if not (self.dir / ".git").exists():
            subprocess.run(["git", "init", "-q", str(self.dir)], check=True)
        subprocess.run(git + ["add", "STATUS.md"], check=True)
        subprocess.run(git + ["commit", "-qm", "board"], check=True)
        subprocess.run(git + ["update-ref", "refs/remotes/origin/main", "HEAD"], check=True)
        return hashlib.sha256(self.board.read_bytes()).hexdigest()

    def test_a_peer_publish_after_the_composition_is_refused_by_the_remote_sha(self):
        """Measured 2026-11-08 23:13: a tick composed over the 22:22 board, aligned the *disk* copy to
        those bytes so `--expect-sha` matched, published, and pushed onto a remote a peer had moved
        to its own 23:12 board. Both local checks were green because neither reads the remote, and
        the push was fast-forward-clean on the fresh parent while replacing their rows.
        """
        composed = self._commit_board(board_text(self.OLD))
        self._commit_board(board_text(self.NEW))          # the peer publishes after the read
        self.board.write_text(board_text(self.OLD), encoding="utf-8")   # disk aligned to our base
        before = self.board.read_bytes()
        self.assertEqual(self.publish(board_text(self.NEW), expect_sha=composed,
                                      remote_sha=composed), 1)
        self.assertEqual(self.board.read_bytes(), before)

    def test_negative_control_the_same_publish_without_the_remote_gate_replaces_it(self):
        """Without the remote gate the identical write succeeds — the peer's board is lost, which is
        why the gate exists rather than a note about it."""
        composed = self._commit_board(board_text(self.OLD))
        self._commit_board(board_text(self.NEW))
        self.board.write_text(board_text(self.OLD), encoding="utf-8")
        self.assertEqual(self.publish(board_text(self.NEW), expect_sha=composed), 0)
        self.assertIn(self.NEW, self.board.read_text(encoding="utf-8"))

    def test_an_unmoved_remote_lets_the_publish_through(self):
        composed = self._commit_board(board_text(self.OLD))
        self.assertEqual(self.publish(board_text(self.NEW), expect_sha=composed,
                                      remote_sha=composed), 0)
        self.assertIn(self.NEW, self.board.read_text(encoding="utf-8"))

    def test_a_board_missing_an_in_flight_row_is_refused(self):
        """The 2026-11-11 loss: a body kept from a shrunken base passed every byte guard."""
        self.board.write_text(board_text(self.OLD), encoding="utf-8")
        before = self.board.read_bytes()
        shrunken = board_text(self.NEW).replace("| queue | — | 0 open |\n", "")
        self.assertEqual(self.publish(shrunken), 1)
        self.assertEqual(self.board.read_bytes(), before)

    def test_negative_control_the_same_publish_with_every_row_succeeds(self):
        self.board.write_text(board_text(self.OLD), encoding="utf-8")
        self.assertEqual(self.publish(board_text(self.NEW)), 0)
        self.assertIn(self.NEW, self.board.read_text(encoding="utf-8"))

    def test_newer_census_replaces_the_board(self):
        self.board.write_text(board_text(self.OLD), encoding="utf-8")
        self.assertEqual(self.publish(board_text(self.NEW)), 0)
        self.assertIn(self.NEW, self.board.read_text(encoding="utf-8"))

    def test_older_census_is_refused_and_leaves_the_board_bytes_alone(self):
        # Negative control: the pre-guard behaviour overwrote here and regressed the board.
        self.board.write_text(board_text(self.NEW), encoding="utf-8")
        before = self.board.read_bytes()
        self.assertEqual(self.publish(board_text(self.OLD)), 1)
        self.assertEqual(self.board.read_bytes(), before)

    def test_same_census_is_idempotent(self):
        self.board.write_text(board_text(self.NEW), encoding="utf-8")
        self.assertEqual(self.publish(board_text(self.NEW).replace("this tick", "re-run")), 0)

    def test_census_stamp_decides_over_a_newer_title(self):
        """A fresh title over a stale census is the shape of the defect, so the census is what counts."""
        self.board.write_text(board_text(self.OLD, title="2026-11-06 18:00"), encoding="utf-8")
        self.assertEqual(self.publish(board_text(self.NEW, title="2026-11-06 16:04")), 0)
        self.assertIn(self.NEW, self.board.read_text(encoding="utf-8"))

    def test_a_board_with_no_stamp_fails_closed(self):
        self.board.write_text(board_text(self.NEW), encoding="utf-8")
        before = self.board.read_bytes()
        self.assertEqual(self.publish("| where |\n|---|\n| x |\n"), 1)
        self.assertEqual(self.board.read_bytes(), before)

    def test_markdown_that_will_not_render_is_refused(self):
        self.board.write_text(board_text(self.OLD), encoding="utf-8")
        broken = board_text(self.NEW).replace("|---|---|---|\n", "", 1)
        self.assertEqual(self.publish(broken), 1)
        self.assertIn(self.OLD, self.board.read_text(encoding="utf-8"))

    def test_a_harness_transcript_banner_is_refused(self):
        """Measured 2026-11-09 12:10 ET: the banner publishes at exit 0 and reaches the clone."""
        self.board.write_text(board_text(self.OLD), encoding="utf-8")
        before = self.board.read_bytes()
        for banner in ("--- stderr ---", "warning: VIRTUAL_ENV=/tmp/x does not match"):
            self.subTest(banner=banner)
            with_banner = board_text(self.NEW).replace(
                "## Work queue\n\n", f"## Work queue\n\n{banner}\n\n")
            self.assertEqual(self.publish(with_banner), 1)
            self.assertEqual(self.board.read_bytes(), before)
        # Negative control: the same board without the echoed line publishes.
        self.assertEqual(self.publish(board_text(self.NEW)), 0)

    def test_a_cluster_address_in_the_board_is_refused_pre_push(self):
        # Measured twice on 2026-11-08: a tick quoted a host verbatim and CI redded the tip
        # for every session after it, so publish now refuses before the write.
        self.board.write_text(board_text(self.OLD), encoding="utf-8")
        before = self.board.read_bytes()
        leaking = board_text(self.NEW).replace(
            "this tick", "held " + ".".join(("10", "0", "4", "30")) + " while waiting")
        self.assertEqual(self.publish(leaking), 1)
        self.assertEqual(self.board.read_bytes(), before)
        hostname = board_text(self.NEW).replace("this tick", "launched on " + "spark-" + "01")
        self.assertEqual(self.publish(hostname), 1)
        self.assertEqual(self.board.read_bytes(), before)
        masked = board_text(self.NEW).replace("this tick", "held the rank host (`.30`)")
        self.assertEqual(self.publish(masked), 0)

    def test_an_in_place_peer_edit_is_refused_by_the_composed_sha(self):
        """Measured 2026-11-08 11:13: an equal title let a whole-file publish replace a peer's
        in-place edit, and no commit held those bytes. The stamp cannot see that write; the sha can.
        """
        self.board.write_text(board_text(self.OLD), encoding="utf-8")
        composed = hashlib.sha256(self.board.read_bytes()).hexdigest()
        edited = board_text(self.OLD).replace("this tick", "a peer's in-place edit")
        self.board.write_text(edited, encoding="utf-8")
        before = self.board.read_bytes()
        self.assertEqual(self.publish(board_text(self.NEW), expect_sha=composed), 1)
        self.assertEqual(self.board.read_bytes(), before)

    def test_the_composed_sha_publishes_when_the_board_did_not_move(self):
        self.board.write_text(board_text(self.OLD), encoding="utf-8")
        composed = hashlib.sha256(self.board.read_bytes()).hexdigest()
        self.assertEqual(self.publish(board_text(self.NEW), expect_sha=composed), 0)
        self.assertIn(self.NEW, self.board.read_text(encoding="utf-8"))

    def _peer_writes_a_row(self, row):
        """Append a row the way a peer writes the board between a publisher's read and its write."""
        self.board.write_text(self.board.read_text(encoding="utf-8") + row + "\n", encoding="utf-8")

    def test_a_peer_line_dropped_between_read_and_write_exits_3(self):
        self.board.write_text(board_text(self.OLD), encoding="utf-8")
        base = self.dir / "read.md"
        base.write_text(board_text(self.OLD), encoding="utf-8")
        self._peer_writes_a_row("| 11:08 | measurement, peer | a row written after the read |")
        before = self.board.read_bytes()
        self.assertEqual(self.publish(board_text(self.NEW), base=base), 3)
        self.assertEqual(self.board.read_bytes(), before)

    def test_identical_body_publishes(self):
        """Regression: an unchanged rewrite drops nothing, so the containment check stays quiet."""
        self.board.write_text(board_text(self.OLD), encoding="utf-8")
        self.assertEqual(self.publish(board_text(self.OLD)), 0)

    def test_retirement_is_legitimate(self):
        """A tick clears the landed table and closes queue rows: lines already in the base may go."""
        self.board.write_text(board_text(self.OLD) + "| 10:44 | `92b7503` | retired next tick |\n",
                              encoding="utf-8")
        base = self.dir / "read.md"
        base.write_text(self.board.read_text(encoding="utf-8"), encoding="utf-8")
        self.assertEqual(self.publish(board_text(self.NEW), base=base), 0)
        self.assertNotIn("92b7503", self.board.read_text(encoding="utf-8"))

    def test_negative_control_with_the_containment_check_bypassed(self):
        """The dropped-peer case must publish once the check is bypassed, or its test proves nothing."""
        self.board.write_text(board_text(self.OLD), encoding="utf-8")
        base = self.dir / "read.md"
        base.write_text(board_text(self.OLD), encoding="utf-8")
        self._peer_writes_a_row("| 11:08 | peer | row |")
        original = tq.dropped_peer_lines
        tq.dropped_peer_lines = lambda *a, **k: []  # type: ignore[assignment]
        try:
            self.assertEqual(self.publish(board_text(self.NEW), base=base), 0)
        finally:
            tq.dropped_peer_lines = original

    def test_publish_without_sha_or_base_is_refused(self):
        """Neither guard means the write is unchecked, so it fails closed with the ordinary code."""
        self.board.write_text(board_text(self.OLD), encoding="utf-8")
        before = self.board.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            saved, sys.stdin = sys.stdin, io.StringIO(board_text(self.NEW))
            try:
                rc = tq.main(["publish", "--board", str(self.board), "--lock", str(self.lock)])
            finally:
                sys.stdin = saved
        self.assertEqual(rc, 1)
        self.assertEqual(self.board.read_bytes(), before)

    def test_a_wedged_lock_refuses_instead_of_waiting(self):
        """Measured 2026-11-06: an inherited lock fd held the board lock for over an hour."""
        self.board.write_text(board_text(self.OLD), encoding="utf-8")
        before = self.board.read_bytes()
        with open(self.lock, "w") as holder:
            fcntl.flock(holder, fcntl.LOCK_EX)
            self.assertEqual(self.publish(board_text(self.NEW), wait="0"), 1)
        self.assertEqual(self.board.read_bytes(), before)

def git_repo(root: Path, *files: str) -> Path:
    """A checkout holding `files` as tracked paths: a `recipe` field must resolve to one of these."""
    import subprocess
    for name in files:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("container: example/image:tag\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "--", *files], check=True)
    return root


class BootableRows(unittest.TestCase):
    """The optional `recipe`/`tp`/`env` fields: a scheduler must never have to guess an arm.

    These are what a queue campaign (the director's `--queue` mode) boots, so each defect is a
    data error naming the row — a row that looks bootable and is not is how a campaign would boot
    the wrong recipe or half a quartet.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = git_repo(Path(self.tmp.name), "recipes/lane/arm.yaml",
                             "recipes/lane/other.yaml")
        self.queue = self.root / "mad-science" / "queue.json"
        self.queue.parent.mkdir()

    def write(self, *rows) -> Path:
        self.queue.write_text(json.dumps(data(list(rows))), encoding="utf-8")
        return self.queue

    def bootable(self, **fields) -> dict:
        row = task("a", 1.0)
        row["node_cost"] = "single"
        row.update(fields)
        return row

    def refusal(self, row) -> str:
        with self.assertRaises(tq.QueueError) as ctx:
            tq.validate({"priority_models": [], "tasks": [row]}, self.queue)
        return str(ctx.exception)

    def test_a_bootable_row_validates(self) -> None:
        rows = tq.validate(data([self.bootable(recipe="recipes/lane/arm.yaml", tp=1)]), self.queue)
        self.assertEqual(rows[0]["recipe"], "recipes/lane/arm.yaml")

    def test_an_untracked_recipe_is_refused(self) -> None:
        # A path that exists nowhere and a path that exists but is untracked are both defects: a
        # clone must be able to resolve the row, and a boot must not depend on a local-only file.
        (self.root / "recipes" / "lane" / "untracked.yaml").write_text("container: x\n",
                                                                      encoding="utf-8")
        for recipe in ("recipes/lane/ghost.yaml", "recipes/lane/untracked.yaml"):
            message = self.refusal(self.bootable(recipe=recipe, tp=1))
            self.assertIn("not a tracked file", message, recipe)
            self.assertIn("a:", message)

    def test_a_tracked_recipe_missing_from_the_worktree_is_refused(self) -> None:
        (self.root / "recipes" / "lane" / "other.yaml").unlink()
        self.assertIn("not in the worktree",
                      self.refusal(self.bootable(recipe="recipes/lane/other.yaml", tp=1)))

    def test_a_path_outside_recipes_is_refused(self) -> None:
        git_repo(self.root, "docs/lane.yaml")
        self.assertIn("recipes/<lane>/<arm>.yaml",
                      self.refusal(self.bootable(recipe="docs/lane.yaml", tp=1)))

    def test_tp_must_be_a_legal_node_count(self) -> None:
        for tp in (3, 0, True):
            self.assertIn("'tp' must be one of", self.refusal(self.bootable(
                recipe="recipes/lane/arm.yaml", tp=tp)))

    def test_tp_must_agree_with_node_cost(self) -> None:
        row = self.bootable(recipe="recipes/lane/arm.yaml", tp=2)
        self.assertIn("disagrees with node_cost", self.refusal(row))
        row = self.bootable(recipe="recipes/lane/arm.yaml", tp=1)
        row["node_cost"] = "pair"
        self.assertIn("disagrees with node_cost", self.refusal(row))

    def test_a_quartet_row_validates_on_a_quartet_cost(self) -> None:
        row = self.bootable(recipe="recipes/lane/arm.yaml", tp=4)
        row["node_cost"] = "quartet"
        self.assertEqual(tq.validate(data([row]), self.queue)[0]["tp"], 4)

    def test_env_must_be_an_object_of_strings(self) -> None:
        for env in (["ARM_TAG=d4"], {"ARM_TAG": 4}, {"ARM_TAG": None}):
            self.assertIn("'env' must be an object of string values",
                          self.refusal(self.bootable(recipe="recipes/lane/arm.yaml", tp=1, env=env)))

    def test_half_a_bootable_row_is_refused(self) -> None:
        # Neither half may stand alone: tp without a recipe names no arm, and a recipe without tp
        # asks the scheduler to guess how many nodes it takes.
        self.assertIn("without 'recipe'", self.refusal(self.bootable(tp=1)))
        self.assertIn("without 'tp'", self.refusal(self.bootable(recipe="recipes/lane/arm.yaml")))

    def test_a_register_outside_a_checkout_cannot_carry_a_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as outside_dir:
            outside = Path(outside_dir) / "mad-science" / "queue.json"
            outside.parent.mkdir()
            with self.assertRaises(tq.QueueError) as ctx:
                tq.validate({"priority_models": [], "tasks": [
                    self.bootable(recipe="recipes/lane/arm.yaml", tp=1)]}, outside)
        self.assertIn("not a git worktree", str(ctx.exception))

    def test_rows_without_the_fields_stay_legal(self) -> None:
        self.assertEqual(tq.validate(data([task("authoring", 1.0)]), self.queue)[0]["id"],
                         "authoring")

    def test_add_and_update_round_trip_the_bootable_fields(self) -> None:
        self.write(task("keep", 1.0))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(tq.main(["--file", str(self.queue), "add", "--id", "a", "--title", "a",
                                      "--estimate-h", "2", "--node-cost", "pair",
                                      "--recipe", "recipes/lane/arm.yaml", "--tp", "2",
                                      "--env", "ARM_OPTS=--serve-debug acceptance",
                                      "--env", "ARM_TAG=d4"]), 0)
            self.assertEqual(tq.main(["--file", str(self.queue), "check"]), 0)
        row = self.row("a")
        self.assertEqual((row["recipe"], row["tp"], row["env"]),
                         ("recipes/lane/arm.yaml", 2,
                          {"ARM_OPTS": "--serve-debug acceptance", "ARM_TAG": "d4"}))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(tq.main(["--file", str(self.queue), "update", "--id", "a",
                                      "--env", "ARM_TAG=d8"]), 0)
        # `update --env` merges: the other overrides and tp survive.
        self.assertEqual(self.row("a")["env"],
                         {"ARM_OPTS": "--serve-debug acceptance", "ARM_TAG": "d8"})
        self.assertEqual(self.row("a")["tp"], 2)

    def test_the_cli_refuses_a_bootable_row_that_cannot_run(self) -> None:
        self.write(self.bootable(recipe="recipes/lane/ghost.yaml", tp=1))
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(tq.main(["--file", str(self.queue), "check"]), 1)
        self.assertIn("ghost.yaml", err.getvalue())

    def test_queue_json_is_the_same_ordering(self) -> None:
        """The scheduler reads `queue --json`: it must be the ordering the human table prints."""
        seed = REPO_ROOT / "mad-science" / "queue.json"
        ordered = tq.ordering(tq.load(seed), seed)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(tq.main(["queue", "--json"]), 0)
        self.assertEqual([row["id"] for row in json.loads(out.getvalue())],
                         [task_row["id"] for task_row in ordered])

    def row(self, task_id: str) -> dict:
        tasks = json.loads(self.queue.read_text(encoding="utf-8"))["tasks"]
        return next(entry for entry in tasks if entry["id"] == task_id)


class ClaimLifecycle(unittest.TestCase):
    """A claim exists only on a running row; every exit from `running` releases it.

    A queued (or blocked, or done) row still carrying `claimed_by` is the drift that makes a
    scheduler read its own work as another session's and skip it forever, so `update` clears the
    pair and `check` refuses a hand-edited file that did not.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.queue = Path(self.tmp.name) / "queue.json"
        self.queue.write_text(json.dumps(data([task("a", 1.0)])), encoding="utf-8")

    def cli(self, *argv) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = tq.main(["--file", str(self.queue), *argv])
        return code, out.getvalue() + err.getvalue()

    def row(self) -> dict:
        return json.loads(self.queue.read_text(encoding="utf-8"))["tasks"][0]

    def claim(self) -> tuple:
        row = self.row()
        return row["state"], row.get("claimed_by", ""), row.get("claimed_at", "")

    def test_leaving_running_releases_the_claim(self) -> None:
        self.assertEqual(self.cli("update", "--id", "a", "--state", "running",
                                  "--claimed-by", "s")[0], 0)
        state, claimed_by, claimed_at = self.claim()
        self.assertEqual((state, claimed_by, bool(claimed_at)), ("running", "s", True))

        # The failed-arm path: back to the queue with the reason in `notes`.
        self.assertEqual(self.cli("update", "--id", "a", "--state", "queued",
                                  "--notes", "campaign: ladder failed")[0], 0)
        self.assertEqual(self.claim(), ("queued", "", ""))

        # The external-gate path.
        self.assertEqual(self.cli("update", "--id", "a", "--state", "running",
                                  "--claimed-by", "s")[0], 0)
        self.assertEqual(self.cli("block", "--id", "a")[0], 0)
        self.assertEqual(self.claim(), ("blocked", "", ""))

        # Completion.
        self.assertEqual(self.cli("update", "--id", "a", "--state", "running",
                                  "--claimed-by", "s")[0], 0)
        self.assertEqual(self.cli("done", "--id", "a")[0], 0)
        self.assertEqual(self.claim(), ("done", "", ""))

    def test_a_claim_without_state_running_is_refused(self) -> None:
        # Negative control: silently dropping it would look identical in the file -- an unclaimed
        # queued row -- so the mistake has to be named instead.
        code, text = self.cli("update", "--id", "a", "--claimed-by", "s")
        self.assertEqual(code, 1)
        self.assertIn("needs '--state running'", text)
        self.assertEqual(self.claim(), ("queued", "", ""))

    def test_a_non_running_row_carrying_a_claim_fails_closed(self) -> None:
        payload = json.loads(self.queue.read_text(encoding="utf-8"))
        payload["tasks"][0].update(claimed_by="s", claimed_at="2026-11-07T00:00:00Z")
        with self.assertRaises(tq.QueueError) as ctx:
            tq.validate(payload, self.queue)
        self.assertIn("a: a claim exists only on a running row", str(ctx.exception))
        self.queue.write_text(json.dumps(payload), encoding="utf-8")
        code, text = self.cli("check")
        self.assertEqual(code, 1)
        self.assertIn("claim exists only on a running row", text)

    def stale(self) -> None:
        """The row a peer's pre-fix `update` left claimed: a queued row carrying a claim."""
        payload = json.loads(self.queue.read_text(encoding="utf-8"))
        payload["tasks"][0].update(claimed_by="peer", claimed_at="2026-11-07T00:00:00Z")
        self.queue.write_text(json.dumps(payload), encoding="utf-8")

    def test_update_repairs_a_stale_claim_before_validating(self) -> None:
        # The second instance of the relink defect: the pre-validate refused the very row the
        # error text told the reader to repair, so `update --state queued` could not run at all.
        for state in ("queued", "blocked"):
            self.stale()
            code, text = self.cli("update", "--id", "a", "--state", state)
            self.assertEqual(code, 0, text)
            self.assertEqual(self.claim(), (state, "", ""))
            self.assertEqual(self.cli("check")[0], 0)

        # A running target keeps exactly the claim the flips wrote, never the stale one.
        self.stale()
        self.assertEqual(self.cli("update", "--id", "a", "--state", "running",
                                  "--claimed-by", "s")[0], 0)
        state, claimed_by, claimed_at = self.claim()
        self.assertEqual((state, claimed_by), ("running", "s"))
        self.assertNotEqual(claimed_at, "2026-11-07T00:00:00Z")
        self.assertEqual(self.cli("check")[0], 0)

        # A notes-only update (no --state) is the same repair path.
        self.assertEqual(self.cli("update", "--id", "a", "--state", "queued")[0], 0)
        self.stale()
        self.assertEqual(self.cli("update", "--id", "a", "--notes", "repaired")[0], 0)
        self.assertEqual(self.claim(), ("queued", "", ""))
        self.assertEqual(self.row()["notes"], "repaired")

    def test_the_repair_touches_only_the_named_row(self) -> None:
        payload = json.loads(self.queue.read_text(encoding="utf-8"))
        other = task("b", 1.0)
        other.update(claimed_by="peer", claimed_at="2026-11-07T00:00:00Z")
        payload["tasks"].append(other)
        self.queue.write_text(json.dumps(payload), encoding="utf-8")

        # `a` is repairable, `b` is not: updating `a` must not launder another row's defect.
        code, text = self.cli("update", "--id", "a", "--state", "queued")
        self.assertEqual(code, 1)
        self.assertIn("b: a claim exists only on a running row", text)
        # Nothing was written, including the in-memory repair of `a`.
        self.assertEqual(self.claim(), ("queued", "", ""))
        rows = {entry["id"]: entry for entry in json.loads(self.queue.read_text())["tasks"]}
        self.assertEqual(rows["a"].get("claimed_by", ""), "")
        self.assertEqual(rows["b"]["claimed_by"], "peer")

        # Each row's own update is the repair; after `b`'s, `a`'s goes through too.
        self.assertEqual(self.cli("update", "--id", "b", "--state", "queued")[0], 0)
        self.assertEqual(self.cli("update", "--id", "a", "--state", "queued")[0], 0)
        self.assertEqual(self.cli("check")[0], 0)
