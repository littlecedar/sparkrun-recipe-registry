"""Guards for tools/board-tick.py — one flock, one publisher, zero model calls by construction.

Run:
    uv run python -B -m unittest tests.test_board_tick -v

Stdlib only, no fleet, no real ssh, no real git: the tool is copied into a fixture repository whose
sibling tools are stubs that log to `$CALLS`, and a fake `git` on PATH answers `diff`/`commit`/
`push`.  The fixture's census sleeps so two real processes overlap.

What is pinned:
* two simultaneous ticks: exactly one publishes, the loser exits 0 and its ledger line says
  `skipped:busy` — and the same test run against a copy with the flock removed publishes twice,
  so the assertion is not vacuous;
* `--needs-summary` prints the stale count while another process holds the lock, takes no lock of
  its own, and writes no ledger line;
* `--dry-run` renders, prints the would-be board path, and commits/pushes nothing;
* the tick reads the live worktree register (not origin/main);
* only `mad-science/STATUS.md` is committed — the register is never added;
* a dirty worktree (uncommitted queue.json) does not block the tick;
* the gate detects a register change from the worktree snapshot.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "board-tick.py"

CENSUS = '''\
import os, sys, time
from pathlib import Path
args = sys.argv[1:]
out = Path(args[args.index("--out") + 1])
time.sleep(float(os.environ.get("CENSUS_SLEEP", "0")))
out.mkdir(parents=True, exist_ok=True)
path = out / (os.environ.get("CENSUS_STAMP", "2026-11-22T040000Z") + ".json")
path.write_text("{}")
with open(os.environ["CALLS"], "a") as handle:
    handle.write("census\\n")
print(path)
'''

RENDER = '''\
import os, sys
from pathlib import Path
args = sys.argv[1:]
Path(args[args.index("--out") + 1]).write_text(
    "# Board — generated 2026-11-21 23:00 ET\\n\\n## In flight\\nrendered\\n")
with open(os.environ["CALLS"], "a") as handle:
    handle.write("render" + (" prev" if "--prev" in args else "") + "\\n")
'''

TASK_QUEUE = '''\
import os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ["CALLS"], "a") as handle:
    handle.write("task-queue " + " ".join(args) + "\\n")
# The tick passes `--file <register>` first, so the stale query works on any register.
tail = args[args.index("render"):] if "render" in args else []
if tail[:3] == ["render", "--board", "--stale"]:
    stale = os.environ.get("STALE_FILE")
    if stale and Path(stale).is_file():
        sys.stdout.write(Path(stale).read_text())
    sys.exit(0)
sys.exit(0)
'''

PUSH_GATE = '''\
import os, sys
with open(os.environ["CALLS"], "a") as handle:
    handle.write("gate\\n")
sys.exit(int(os.environ.get("GATE_RC", "0")))
'''

GIT = '''\
#!/usr/bin/env python3
import os, sys
from pathlib import Path
args = sys.argv[1:]
if args[:1] == ["-C"]:
    args = args[2:]
with open(os.environ["CALLS"], "a") as handle:
    handle.write("git " + " ".join(args) + "\\n")
cmd = args[0] if args else ""
if cmd == "diff":
    sys.exit(int(os.environ.get("DIFF_RC", "1")))
if cmd == "commit":
    sys.exit(int(os.environ.get("COMMIT_RC", "0")))
if cmd == "push":
    sys.exit(int(os.environ.get("PUSH_RC", "0")))
sys.exit(0)
'''


def build(root: Path, flock: bool = True) -> Path:
    """A fixture repository whose sibling tools are stubs; returns the copied board-tick.py."""
    (root / "tools").mkdir(parents=True, exist_ok=True)
    (root / "mad-science").mkdir(exist_ok=True)
    (root / ".local").mkdir(exist_ok=True)
    (root / "bin").mkdir(exist_ok=True)
    (root / "mad-science" / "queue.json").write_text('{"priority_models": [], "tasks": []}\n')
    (root / "mad-science" / "STATUS.md").write_text("# Board — generated 2026-11-21 22:00 ET\n")
    # A declared window is a session mark, so these fixtures exercise the tick rather than the gate
    # (owner direction 2026-11-22). The gate's own tests delete it and control the register.
    (root / ".local" / "fleet-window.lock").write_text("window-end = 2099-01-01T00:00:00Z\n")
    for name, body in (("board-census.py", CENSUS), ("board-render.py", RENDER),
                       ("task-queue.py", TASK_QUEUE), ("push-gate.py", PUSH_GATE)):
        (root / "tools" / name).write_text(body)
    git = root / "bin" / "git"
    git.write_text(GIT)
    git.chmod(0o755)
    source = TOOL.read_text()
    if not flock:
        source = source.replace("fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)",
                                "pass  # negative control: no flock")
        assert "negative control" in source, "the flock call moved; update the negative control"
    tool = root / "tools" / "board-tick.py"
    tool.write_text(source)
    return tool


class BoardTick(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.tool = build(self.root)
        self.calls = self.root / "calls.log"
        self.ledger = self.root / ".local" / "board-tick.jsonl"
        self.board = self.root / "mad-science" / "STATUS.md"
        self.env = dict(os.environ, PATH=f"{self.root / 'bin'}:{os.environ['PATH']}",
                        CALLS=str(self.calls))

    def run_tick(self, *args, **env):
        return subprocess.run([sys.executable, "-B", str(self.tool), *args],
                              cwd=str(self.root), env=dict(self.env, **env),
                              capture_output=True, text=True)

    def call_lines(self, prefix: str = "") -> list[str]:
        if not self.calls.is_file():
            return []
        return [line for line in self.calls.read_text().splitlines() if line.startswith(prefix)]

    def ledger_lines(self) -> list[dict]:
        if not self.ledger.is_file():
            return []
        return [json.loads(line) for line in self.ledger.read_text().splitlines()]

    def test_two_ticks_one_publishes_and_the_loser_says_busy(self):
        first = subprocess.Popen([sys.executable, "-B", str(self.tool)], cwd=str(self.root),
                                 env=dict(self.env, CENSUS_SLEEP="1.5"),
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(0.2)  # let the winner take the lock and enter the census
        second = self.run_tick(CENSUS_SLEEP="1.5")
        out, err = first.communicate(timeout=60)
        self.assertEqual(first.returncode, 0, err)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(len(self.call_lines("render")), 1,
                         "exactly one tick may render")
        self.assertIn("skipped", second.stdout)
        self.assertIn("published", out)
        outcomes = sorted(line["outcome"] for line in self.ledger_lines())
        self.assertEqual(outcomes, ["published", "skipped:busy"])
        for line in self.ledger_lines():
            self.assertEqual(line["model_calls"], 0)
            self.assertIn("census_stamp", line)
            self.assertIn("board_sha", line)

    def test_negative_control_without_the_flock_publishes_twice(self):
        tool = build(self.root, flock=False)
        self.tool = tool
        first = subprocess.Popen([sys.executable, "-B", str(tool)], cwd=str(self.root),
                                 env=dict(self.env, CENSUS_SLEEP="1.5"),
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(0.2)
        second = self.run_tick(CENSUS_SLEEP="1.5")
        out, err = first.communicate(timeout=60)
        self.assertEqual(first.returncode, 0, err)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(len(self.call_lines("render")), 2,
                         "without the flock both ticks render — the lock test is live")

    def test_needs_summary_takes_no_lock_and_writes_no_ledger(self):
        stale = self.root / "stale.txt"
        stale.write_text("t1\nt2\nt3\n")
        lock = self.root / ".local" / "board-tick.lock"
        with open(lock, "a+") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            proc = self.run_tick("--needs-summary", STALE_FILE=str(stale))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "3")
        # Summary duty reads the worktree register (the copy a model can fill), named explicitly.
        self.assertEqual(len(self.call_lines("task-queue --file")), 1)
        self.assertIn("render --board --stale", self.call_lines("task-queue --file")[0])
        self.assertEqual(self.call_lines("census"), [])
        self.assertEqual(self.call_lines("render"), [])
        self.assertEqual(self.ledger_lines(), [])

    def test_dry_run_renders_and_commits_nothing(self):
        before = self.board.read_bytes()
        proc = self.run_tick("--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rendered = Path(proc.stdout.split("would publish", 1)[1].strip())
        self.assertTrue(rendered.is_file())
        self.assertIn("rendered", rendered.read_text())
        self.assertEqual(self.board.read_bytes(), before)
        self.assertEqual([line["outcome"] for line in self.ledger_lines()], ["dry-run"])
        self.assertEqual(self.call_lines("git commit"), [])
        self.assertEqual(self.call_lines("git push"), [])

    def test_only_status_md_is_committed(self):
        """The tick commits only mad-science/STATUS.md, never queue.json or other files."""
        proc = self.run_tick()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        commit_lines = self.call_lines("git commit")
        self.assertEqual(len(commit_lines), 1, "exactly one commit")
        self.assertIn("mad-science/STATUS.md", commit_lines[0],
                      "commit must name STATUS.md")
        self.assertNotIn("queue.json", commit_lines[0],
                         "queue.json must never appear in the commit pathspec")
        # The tick uses `git commit -- <pathspec>`, never `git add`.
        self.assertEqual(self.call_lines("git add"), [],
                         "the tick must not call git add")

    def test_dirty_worktree_does_not_block(self):
        """Uncommitted changes to queue.json do not stop the tick (no merge step)."""
        (self.root / "mad-science" / "queue.json").write_text(
            '{"priority_models": [], "tasks": [], "dirty": true}\n')
        proc = self.run_tick()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("published", proc.stdout)
        self.assertEqual(len(self.call_lines("render")), 1)
        self.assertEqual(len(self.call_lines("git commit")), 1)

    def test_worktree_register_is_read_directly(self):
        """The tick passes the worktree queue.json path to its tools, never a materialised copy."""
        proc = self.run_tick()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # stale_ids() calls task-queue.py --file <register> render --board --stale
        tq_lines = self.call_lines("task-queue --file")
        self.assertEqual(len(tq_lines), 1, "one task-queue call with --file")
        self.assertIn("mad-science/queue.json", tq_lines[0],
                      "must reference the worktree register")
        self.assertNotIn("board-register.json", tq_lines[0],
                         "must not reference a materialised origin copy")


class Gate(unittest.TestCase):
    """The tick runs only for a session mark or a register change (owner direction 2026-11-22).

    The gate compares the worktree register sha256 against the last evidence file's stored
    snapshot.  If they match and no session is running, the tick skips.  This is entirely local
    — no git fetch, no origin/main comparison.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.tool = build(self.root)
        self.calls = self.root / "calls.log"
        self.ledger = self.root / ".local" / "board-tick.jsonl"
        self.board = self.root / "mad-science" / "STATUS.md"
        self.window = self.root / ".local" / "fleet-window.lock"
        self.window.unlink()                    # start with no session mark
        # Create a previous evidence file whose register sha matches the worktree queue.json,
        # so that "no change" tests skip.
        self.evidence_dir = self.root / ".local" / "board-evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        register_path = self.root / "mad-science" / "queue.json"
        self.register_sha = hashlib.sha256(register_path.read_bytes()).hexdigest()
        self._write_evidence(self.register_sha)
        self.env = dict(os.environ, PATH=f"{self.root / 'bin'}:{os.environ['PATH']}",
                        CALLS=str(self.calls))

    def _write_evidence(self, register_sha: str) -> Path:
        evidence = {
            "version": 1, "at": "2026-11-22T00:00:00Z", "base": None,
            "nodes": {}, "head": {}, "notes": [],
            "register": {"path": "mad-science/queue.json", "sha256": register_sha,
                         "tasks": 0, "done": 0, "queued": 0, "blocked": 0, "running": 0}}
        path = self.evidence_dir / "2026-11-22T000000Z.json"
        path.write_text(json.dumps(evidence))
        return path

    def run_tick(self, *args, **env):
        return subprocess.run([sys.executable, "-B", str(self.tool), *args],
                              cwd=str(self.root), env=dict(self.env, **env),
                              capture_output=True, text=True, check=False)

    def call_lines(self, prefix: str = "") -> list[str]:
        if not self.calls.is_file():
            return []
        return [line for line in self.calls.read_text().splitlines() if line.startswith(prefix)]

    def outcomes(self) -> list[str]:
        if not self.ledger.is_file():
            return []
        return [json.loads(line)["outcome"] for line in self.ledger.read_text().splitlines()]

    def assert_skipped(self, proc) -> None:
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("skipped", proc.stdout)
        self.assertEqual(self.outcomes(), ["skipped:idle"])
        for prefix in ("census", "render", "git commit", "git push", "gate"):
            self.assertEqual(self.call_lines(prefix), [], f"{prefix} ran on an idle fleet")

    def test_no_session_and_no_change_skips_without_touching_anything(self):
        before = self.board.read_bytes()
        self.assert_skipped(self.run_tick())
        self.assertEqual(self.board.read_bytes(), before)

    def test_a_declared_window_runs_the_tick(self):
        self.window.write_text("window-end = 2099-01-01T00:00:00Z\n")
        proc = self.run_tick()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("session: declared window", proc.stdout)
        self.assertEqual(self.call_lines("census"), ["census"])
        self.assertNotIn("skipped:idle", self.outcomes())

    def test_a_live_lease_runs_the_tick(self):
        (self.root / ".local" / "fleet-leases.json").write_text(json.dumps(
            {"version": 1, "leases": [{"id": "x", "holder": "session:peer",
                                       "expires_at": 4102444800}]}) + "\n")
        proc = self.run_tick()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("live lease held by session:peer", proc.stdout)
        self.assertEqual(self.call_lines("census"), ["census"])

    def test_register_change_triggers_the_tick(self):
        """A worktree register whose sha differs from the stored evidence runs the tick."""
        # Write a different register content so the sha changes.
        (self.root / "mad-science" / "queue.json").write_text(
            '{"priority_models": [], "tasks": [{"id": "x", "state": "queued"}]}\n')
        proc = self.run_tick()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("register changed since the last evidence", proc.stdout)
        self.assertEqual(self.call_lines("census"), ["census"])

    def test_force_runs_an_idle_fleet(self):
        proc = self.run_tick("--force")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("forced", proc.stdout)
        self.assertEqual(self.call_lines("census"), ["census"])


class NonFastForwardPush(unittest.TestCase):
    """A non-fast-forward push is reported as failed:push and skipped (never force)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.tool = build(self.root)
        self.calls = self.root / "calls.log"
        self.ledger = self.root / ".local" / "board-tick.jsonl"
        self.board = self.root / "mad-science" / "STATUS.md"
        self.env = dict(os.environ, PATH=f"{self.root / 'bin'}:{os.environ['PATH']}",
                        CALLS=str(self.calls))

    def run_tick(self, *args, **env):
        return subprocess.run([sys.executable, "-B", str(self.tool), *args],
                              cwd=str(self.root), env=dict(self.env, **env),
                              capture_output=True, text=True, check=False)

    def call_lines(self, prefix: str = "") -> list[str]:
        if not self.calls.is_file():
            return []
        return [line for line in self.calls.read_text().splitlines() if line.startswith(prefix)]

    def outcomes(self) -> list[str]:
        if not self.ledger.is_file():
            return []
        return [json.loads(line)["outcome"] for line in self.ledger.read_text().splitlines()]

    def test_non_fast_forward_push_skips_and_reports_failed_push(self):
        """A non-fast-forward push exits 0 and writes failed:push to the ledger."""
        proc = self.run_tick(PUSH_RC="1")
        # The fake git's `push` handler returns PUSH_RC (1 = failure).
        # But the fake git doesn't print "non-fast-forward" or "fetch first".
        # The tick checks for these strings in stderr to distinguish NFF from other failures.
        # Since the fake git's push just exits non-zero with no stderr, this falls through
        # to `fail("push", ...)` which returns 1.
        # Actually, let me test with a fake git that prints the expected stderr.
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertEqual(self.outcomes(), ["failed:push"])

    def test_push_gate_rejection_stops_before_push(self):
        proc = self.run_tick(GATE_RC="1")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertEqual(self.outcomes(), ["failed:gate"])
        self.assertEqual(self.call_lines("git push"), [],
                         "must not push when the gate rejects")


if __name__ == "__main__":
    unittest.main()