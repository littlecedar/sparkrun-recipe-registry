"""Guards for tools/session-director.py — the dispatcher for rows that need no fleet.

Run:
    uv run python -B -m unittest discover -s tests

Stdlib-only, no network, no cluster. The director's whole interface is `tools/task-queue.py`, so the
write tests run the *real* tool against a throwaway git checkout: a director that builds the right
argv and a tool that refuses it is the defect these pin, and a fake would hide it.

What is pinned (owner directive 2026-11-22, design `campaign/DESIGN.md` §"Session/code director"):

* selection is the register's own ordering and shape — `queued`, no `recipe`/`tp`, no live blocker,
  never an `ask` row (`test_a_recipe_row_is_not_taken`, `test_an_ask_row_is_not_taken`,
  `test_a_queued_row_with_a_live_blocker_is_not_taken`);
* assignment is one tool write plus one log line, and a second tick takes nothing
  (`test_assign_writes_scheduled_and_the_log`, `test_a_second_tick_takes_nothing`);
* an assignment is not a lock: an expired one returns to `queued` with its own note
  (`test_release_returns_the_row_with_the_expiry_note`);
* the never-list — it does not touch a running/blocked/ask row, and it writes nothing on a dry run
  (`test_assign_refuses_a_non_queued_row`, `test_dry_run_writes_nothing`);
* one tick hands out one row unless told otherwise (`test_limit_one_hands_out_one_row`).
"""

from __future__ import annotations

import contextlib
import datetime as dt
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "task-queue.py"
DIRECTOR = REPO_ROOT / "tools" / "session-director.py"


def _load():
    spec = importlib.util.spec_from_file_location("session_director", DIRECTOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules["session_director"] = module  # dash-named tool convention
    spec.loader.exec_module(module)
    return module


sd = _load()


def task(tid, state="queued", *, blocks=(), blocked_by=None, model="", recipe=None, tp=None,
         provenance="test", notes="", scheduled_by=None, scheduled_at=None):
    row = {"id": tid, "title": tid, "estimate_h": 1.0, "blocks": list(blocks),
           "blocked_by": list(blocked_by or []), "state": state, "model": model,
           "node_cost": "", "notes": notes, "provenance": provenance}
    if recipe is not None:
        row["recipe"] = recipe
        row["tp"] = tp
        row["node_cost"] = "single"
    if scheduled_by is not None:
        row["scheduled_by"] = scheduled_by
        row["scheduled_at"] = scheduled_at or "2026-11-22T00:00:00Z"
    return row


def git_repo(root: Path, *files: str) -> Path:
    for name in files:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("container: example/image:tag\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "--", *files], check=True)
    return root


class Selection(unittest.TestCase):
    """Which rows the dispatcher may take — pure, in the register's order."""

    def ids(self, rows, **kw):
        return [row["id"] for row in sd.select(rows, **kw)]

    def test_a_queued_session_row_is_taken(self):
        self.assertEqual(self.ids([task("a")]), ["a"])

    def test_a_recipe_row_is_not_taken(self):
        # A fleet row is the campaign's: this dispatcher never schedules a boot.
        self.assertEqual(self.ids([task("boot", recipe="recipes/lane/arm.yaml", tp=1)]), [])

    def test_an_ask_row_is_not_taken(self):
        self.assertEqual(self.ids([task("q", state="ask")]), [])

    def test_a_blocked_row_is_not_taken(self):
        self.assertEqual(self.ids([task("held", state="blocked", blocked_by=["q"])]), [])

    def test_a_running_or_scheduled_row_is_not_taken(self):
        self.assertEqual(self.ids([task("run", state="running"),
                                   task("sched", state="scheduled",
                                        scheduled_by="session-director:x")]), [])

    def test_a_queued_row_with_a_live_blocker_is_not_taken(self):
        rows = [task("work", blocked_by=["q"]), task("q", state="ask")]
        self.assertEqual(self.ids(rows), [])

    def test_negative_control_a_queued_row_with_done_blockers_is_taken(self):
        # `queue --json` omits done rows, so the blocker is absent from the list, not "done".
        self.assertEqual(self.ids([task("work", blocked_by=["finished"])]), ["work"])
        rows = [task("work", blocked_by=["q"]), task("q", state="done")]
        self.assertEqual(self.ids(rows), ["work"])

    def test_order_is_the_register_order(self):
        self.assertEqual(self.ids([task("b"), task("a")]), ["b", "a"])

    def test_the_model_filter_narrows(self):
        rows = [task("a", model="glm-5.3"), task("b", model="dsv4.1-1017")]
        self.assertEqual(self.ids(rows, models=("glm-5.3",)), ["a"])
        self.assertEqual(self.ids(rows, models=("GLM-5.3",)), ["a"], "the tag is case-insensitive")

    def test_the_lane_filter_reads_provenance(self):
        rows = [task("a", provenance="recipes/ds4/README.md:3064"),
                task("b", provenance="mad-science/STATUS.md 13:10")]
        self.assertEqual(self.ids(rows, lanes=("ds4",)), ["a"])

    def test_expired_returns_only_stale_assignments(self):
        now = dt.datetime(2026, 11, 22, 12, 0, 0, tzinfo=dt.UTC)
        rows = [task("old", state="scheduled", scheduled_by="session-director:x",
                     scheduled_at="2026-11-22T10:00:00Z"),
                task("fresh", state="scheduled", scheduled_by="session-director:x",
                     scheduled_at="2026-11-22T11:45:00Z"),
                task("queued")]
        self.assertEqual([r["id"] for r, _age in sd.expired(rows, 30.0, at=now)], ["old"])

    def test_an_unparseable_scheduled_at_is_left_alone(self):
        # The tool refuses a scheduled row with no stamp, so this cannot be a live row; refusing to
        # guess is safer than expiring a row whose clock cannot be read.
        rows = [task("odd", state="scheduled", scheduled_by="x", scheduled_at="yesterday")]
        self.assertEqual(sd.expired(rows, 0.0), [])


class RealRegister(unittest.TestCase):
    """The writes, against the tool's real parser and atomic save."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        git_repo(self.repo, "recipes/lane/arm.yaml")
        self.queue = self.repo / "mad-science" / "queue.json"
        self.queue.parent.mkdir()
        self.log = self.repo / ".local" / "session-director" / "w1.jsonl"
        self.write(task("a"), task("b"))

    def write(self, *rows):
        self.queue.write_text(json.dumps({"priority_models": [], "tasks": list(rows)}),
                              encoding="utf-8")

    def rows(self):
        return {row["id"]: row for row in json.loads(self.queue.read_text(encoding="utf-8"))["tasks"]}

    def tick(self, **kw):
        out = io.StringIO()
        kw.setdefault("worker", "session-director:w1")
        kw.setdefault("timeout_min", 30.0)
        kw.setdefault("lanes", ())
        kw.setdefault("models", ())
        kw.setdefault("dry_run", False)
        assigned, released = sd.tick(tool=TOOL, queue=self.queue, log_path=self.log, out=out, **kw)
        return assigned, released, out.getvalue()

    def test_assign_writes_scheduled_and_the_log(self):
        assigned, _, text = self.tick(limit=1)
        self.assertEqual(assigned, 1)
        self.assertIn("assigned: a -> session-director:w1 (attempt 1)", text)
        row = self.rows()["a"]
        self.assertEqual((row["state"], row["scheduled_by"]), ("scheduled", "session-director:w1"))
        self.assertTrue(row["scheduled_at"])
        self.assertEqual(self.rows()["b"]["state"], "queued", "one row per tick by default")
        entry = json.loads(self.log.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual((entry["row"], entry["worker"], entry["attempt"]), ("a", "session-director:w1", 1))

    def test_a_second_tick_takes_nothing(self):
        # Idempotency: the row is `scheduled`, so it is not `queued` and cannot be re-taken.
        self.tick(limit=1)
        assigned, _, text = self.tick(limit=1)
        self.assertEqual(assigned, 1, "the next queued row is taken, not the same one")
        self.assertEqual(self.rows()["a"]["state"], "scheduled")
        assigned, _, _ = self.tick(limit=1)
        self.assertEqual(assigned, 0)
        self.assertIn("idle: no queued session row in scope", self.tick(limit=1)[2])

    def test_limit_one_hands_out_one_row(self):
        assigned, _, _ = self.tick(limit=1)
        self.assertEqual(assigned, 1)
        self.assertEqual(self.rows()["b"]["state"], "queued")

    def test_assign_refuses_a_non_queued_row(self):
        # The never-list, at the only place it could be violated: a row the dispatcher did not take.
        for state in ("running", "blocked", "ask", "done", "scheduled"):
            with self.subTest(state=state), self.assertRaises(sd.DirectorError) as ctx:
                sd.assign(task("x", state=state, blocked_by=["q"] if state == "blocked" else ()),
                          tool=TOOL, queue=self.queue, worker="session-director:w1", log_path=self.log)
            self.assertIn("refusing to assign", str(ctx.exception))

    def test_release_returns_the_row_with_the_expiry_note(self):
        self.write(task("a", state="scheduled", scheduled_by="session-director:w1",
                        scheduled_at="2026-11-22T00:00:00Z", notes="why a exists"))
        sd.release(self.rows()["a"], tool=TOOL, queue=self.queue, timeout_min=30.0)
        row = self.rows()["a"]
        self.assertEqual(row["state"], "queued")
        self.assertNotIn("scheduled_by", row)
        self.assertIn("why a exists — session-director: assignment expired after 30 min "
                      "(scheduled_by session-director:w1)", row["notes"])

    def test_a_stale_assignment_is_expired_then_reassigned(self):
        self.write(task("a", state="scheduled", scheduled_by="session-director:w0",
                        scheduled_at="2026-11-22T00:00:00Z"))
        assigned, released, text = self.tick(limit=1)
        self.assertEqual((released, assigned), (1, 1), "expire, then hand it out again")
        self.assertIn("expired: a", text)
        self.assertEqual(self.rows()["a"]["scheduled_by"], "session-director:w1")

    def test_dry_run_writes_nothing(self):
        assigned, released, text = self.tick(dry_run=True, limit=1)
        self.assertEqual((assigned, released), (0, 0))
        self.assertIn("dry-run: would assign a", text)
        self.assertEqual(self.rows()["a"]["state"], "queued")
        self.assertFalse(self.log.exists())

    def test_a_red_register_is_reported_not_written(self):
        self.write(task("held", state="blocked"))     # blocked with no blocker: the tool refuses
        with self.assertRaises(sd.DirectorError) as ctx:
            self.tick(limit=1)
        self.assertIn("queue --json failed", str(ctx.exception))
        self.assertEqual(self.rows()["held"]["state"], "blocked", "nothing was written")

    def test_the_never_list_holds_across_a_full_tick(self):
        # A running row and a blocked row are present and untouched; only the queued row moves.
        # `blocked_by` is the tool's stored mirror of `blocks`; `queue` reads it without relinking,
        # so the fixture writes both sides the way `add --blocks` would have.
        self.write(task("busy", state="running"),
                   task("held", state="blocked", blocked_by=["q"]),
                   task("q", state="ask", blocks=["held"]), task("a"))
        assigned, released, _ = self.tick(limit=5)
        self.assertEqual((assigned, released), (1, 0))
        rows = self.rows()
        self.assertEqual(rows["busy"]["state"], "running")
        self.assertEqual(rows["held"]["state"], "blocked")
        self.assertEqual(rows["q"]["state"], "ask")
        self.assertEqual(rows["a"]["state"], "scheduled")


class Cli(unittest.TestCase):
    """The argv the operator runs: dry-run writes nothing, an anonymous real run is refused."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        git_repo(self.repo, "recipes/lane/arm.yaml")
        self.queue = self.repo / "mad-science" / "queue.json"
        self.queue.parent.mkdir()
        self.queue.write_text(json.dumps({"priority_models": [], "tasks": [task("a")]}),
                              encoding="utf-8")

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = sd.main(["--queue", str(self.queue), *argv], out=out, err=err)
        return code, out.getvalue() + err.getvalue()

    def test_dry_run_names_the_row_and_writes_nothing(self):
        code, text = self.run_cli("--once", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("dry-run: would assign a -> session-director:unassigned", text)
        self.assertEqual(json.loads(self.queue.read_text(encoding="utf-8"))["tasks"][0]["state"],
                         "queued")

    def test_a_real_run_needs_a_dispatcher_name(self):
        code, text = self.run_cli("--once")
        self.assertEqual(code, 2)
        self.assertIn("--dispatcher-name", text)

    def test_a_named_once_assigns_one_row(self):
        code, text = self.run_cli("--once", "--dispatcher-name", "w1", "--log-dir",
                                  str(self.repo / ".local" / "session-director"))
        self.assertEqual(code, 0)
        self.assertIn("assigned: a -> session-director:w1 (attempt 1)", text)
        row = json.loads(self.queue.read_text(encoding="utf-8"))["tasks"][0]
        self.assertEqual((row["state"], row["scheduled_by"]), ("scheduled", "session-director:w1"))


if __name__ == "__main__":
    unittest.main()
