"""Guards for tools/board-tick.py — one flock, one publisher, zero model calls by construction.

Run:
    uv run python -B -m unittest tests.test_board_tick -v

Stdlib only, no fleet, no real ssh, no real git: the tool is copied into a fixture repository whose
sibling tools are stubs that log to `$CALLS`, and a fake `git` on PATH answers `show`/`diff`/
`commit`/`push`.  The fixture's census sleeps so two real processes overlap.

What is pinned:
* two simultaneous ticks: exactly one publishes, the loser exits 0 and its ledger line says
  `skipped:busy` — and the same test run against a copy with the flock removed publishes twice,
  so the assertion is not vacuous;
* `--needs-summary` prints the stale count while another process holds the lock, takes no lock of
  its own, and writes no ledger line;
* a publish refusal from a peer-moved board is `refused:peer`, exit 0, no commit and no push;
* `--dry-run` renders, prints the would-be board path, and commits/pushes nothing.
"""

from __future__ import annotations

import fcntl
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
# The tick passes `--file <origin's register>` first, so the stale query is found anywhere.
tail = args[args.index("render"):] if "render" in args else []
if tail[:3] == ["render", "--board", "--stale"]:
    stale = os.environ.get("STALE_FILE")
    if stale and Path(stale).is_file():
        sys.stdout.write(Path(stale).read_text())
    sys.exit(0)
if args and args[0] == "publish":
    rc = int(os.environ.get("PUBLISH_RC", "0"))
    if rc:
        sys.stderr.write("refusing publish: origin/main carries board sha256 deadbeef, not the "
                         "cafebabe this board was composed from — a peer published in between\\n")
        sys.exit(rc)
    Path(args[args.index("--board") + 1]).write_bytes(sys.stdin.buffer.read())
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
if cmd == "fetch":
    sys.exit(0)
if cmd == "rev-parse":
    # `origin/main` exists unless the fixture says it does not (a clone with no remote).
    sys.exit(0 if os.environ.get("ORIGIN_REF", "origin/main") else 1)
if cmd == "merge-base":
    # 0 = origin/main is an ancestor of HEAD (up to date); 1 = the branch has diverged.
    sys.exit(int(os.environ.get("ANCESTOR_RC", "0")))
if cmd == "merge":
    if args[1:2] == ["--abort"]:
        sys.exit(0)
    rc = int(os.environ.get("MERGE_RC", "0"))
    if rc and os.environ.get("MERGE_DIRTY"):
        sys.stderr.write("error: Your local changes to the following files would be overwritten "
                         "by merge:\\n\\tmad-science/queue.json\\nPlease commit your changes or "
                         "stash them before you merge.\\n")
    sys.exit(rc)
if cmd == "show":
    # `<ref>:<path>` — the board and the register the tick reads from origin.
    spec = args[1] if len(args) > 1 else ""
    if spec.endswith("mad-science/queue.json"):
        register = Path(os.environ.get("ORIGIN_REGISTER", os.environ["REMOTE_BOARD"]))
        if register.is_file():
            sys.stdout.buffer.write(register.read_bytes())
            sys.exit(0)
        sys.exit(128)
    remote = Path(os.environ["REMOTE_BOARD"])
    if remote.is_file():
        sys.stdout.buffer.write(remote.read_bytes())
        sys.exit(0)
    sys.exit(128)
if cmd == "diff":
    if "--name-only" in args:
        # The gate asks which board inputs changed since the last board commit *on the ref it
        # named*: origin/main reads CHANGED, a local HEAD reads CHANGED_LOCAL. Filtering by the
        # pathspec the tool passed keeps an irrelevant change genuinely invisible.
        span = next((a for a in args[1:] if a != "--" and not a.startswith("--")), "")
        key = "CHANGED" if span.endswith("origin/main") else "CHANGED_LOCAL"
        spec = args[args.index("--") + 1:] if "--" in args else []
        for line in os.environ.get(key, "").splitlines():
            if not line:
                continue
            if not spec or any(line == p or line.startswith(p.rstrip("/") + "/") for p in spec):
                print(line)
        sys.exit(0)
    sys.exit(int(os.environ.get("DIFF_RC", "1")))
if cmd == "log":
    ref = next((a for a in args[1:] if not a.startswith("-") and a != "--"), "")
    if ref.startswith("origin/"):
        print(os.environ.get("LOG_SHA_ORIGIN", "beef5678"))
    else:
        print(os.environ.get("LOG_SHA", "abc1234"))
    sys.exit(0)
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
    (root / "remote-STATUS.md").write_text("# Board — generated 2026-11-21 22:00 ET\n")
    # A declared window is a session mark, so these fixtures exercise the tick rather than the gate
    # (owner direction 2026-11-22). The gate's own tests delete it and control the change list.
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
                        CALLS=str(self.calls), REMOTE_BOARD=str(self.root / "remote-STATUS.md"))

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
        self.assertEqual(len(self.call_lines("task-queue publish")), 1,
                         "exactly one tick may publish")
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
        self.assertEqual(len(self.call_lines("task-queue publish")), 2,
                         "without the flock both ticks publish — the lock test is live")

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
        self.assertEqual(self.call_lines("task-queue publish"), [])
        self.assertEqual(self.ledger_lines(), [])

    def test_peer_moved_board_is_refused_without_commit_or_push(self):
        before = self.board.read_bytes()
        proc = self.run_tick(PUBLISH_RC="3")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("refused:peer", proc.stdout)
        self.assertEqual(self.board.read_bytes(), before)
        self.assertEqual([line["outcome"] for line in self.ledger_lines()], ["refused:peer"])
        self.assertEqual(self.call_lines("git commit"), [])
        self.assertEqual(self.call_lines("git push"), [])
        self.assertEqual(self.call_lines("gate"), [])

    def test_dry_run_renders_and_commits_nothing(self):
        before = self.board.read_bytes()
        proc = self.run_tick("--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rendered = Path(proc.stdout.split("would publish", 1)[1].strip())
        self.assertTrue(rendered.is_file())
        self.assertIn("rendered", rendered.read_text())
        self.assertEqual(self.board.read_bytes(), before)
        self.assertEqual([line["outcome"] for line in self.ledger_lines()], ["dry-run"])
        self.assertEqual(self.call_lines("task-queue publish"), [])
        self.assertEqual(self.call_lines("git commit"), [])
        self.assertEqual(self.call_lines("git push"), [])


class Gate(unittest.TestCase):
    """The tick runs only for a session mark or a board-input change (owner direction 2026-11-22).

    Measured 2026-11-22: the only scheduler was the omp extension's per-session timer, which dies
    with its session, so the board went stale from 07:02 ET with nothing left to fire it. A durable
    timer is affordable only when an idle fleet costs nothing, so the tick decides for itself: a
    declared window or a live lease means a session is running, and otherwise a change under the
    board's own input paths since the last board commit is what earns a census, a publish and a
    commit. Everything else is one `skipped:idle` ledger line.
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
        self.env = dict(os.environ, PATH=f"{self.root / 'bin'}:{os.environ['PATH']}",
                        CALLS=str(self.calls), REMOTE_BOARD=str(self.root / "remote-STATUS.md"),
                        CHANGED="")

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
        for prefix in ("census", "render", "task-queue publish", "git commit", "git push", "gate"):
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

    def test_a_relevant_change_runs_the_tick(self):
        proc = self.run_tick(CHANGED="mad-science/queue.json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("changed on origin/main: mad-science/queue.json", proc.stdout)
        self.assertEqual(self.call_lines("census"), ["census"])

    def test_an_irrelevant_change_skips(self):
        # `.idea/` and an unrelated doc are not board inputs: the pathspec filter hides them.
        self.assert_skipped(self.run_tick(CHANGED=".idea/modules.xml\nmad-science/TODO.md"))

    def test_force_runs_an_idle_fleet(self):
        proc = self.run_tick("--force")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("forced", proc.stdout)
        self.assertEqual(self.call_lines("census"), ["census"])


class OriginAhead(unittest.TestCase):
    """The gate and the render read `origin/main`, not this clone (owner direction 2026-11-23).

    This checkout is a syncthing replica: measured 2026-11-23 it sat 23 commits behind origin while
    every fire compared the *local* board commit with the *local* HEAD and rendered the *worktree*
    register, so it wrote `skipped:idle` for an hour and would have drawn a stale queue cell if it
    had run. The gate therefore reads the last board commit and the change list on `origin/main`,
    and the register the board describes is `git show origin/main:mad-science/queue.json`.
    """

    ORIGIN_REGISTER = '{"priority_models": [], "tasks": [], "origin_marker": "from-origin"}\n'

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.tool = build(self.root)
        self.calls = self.root / "calls.log"
        self.ledger = self.root / ".local" / "board-tick.jsonl"
        self.board = self.root / "mad-science" / "STATUS.md"
        (self.root / ".local" / "fleet-window.lock").unlink()   # no session mark
        origin_register = self.root / "origin-register.json"
        origin_register.write_text(self.ORIGIN_REGISTER)
        self.env = dict(os.environ, PATH=f"{self.root / 'bin'}:{os.environ['PATH']}",
                        CALLS=str(self.calls), REMOTE_BOARD=str(self.root / "remote-STATUS.md"),
                        ORIGIN_REGISTER=str(origin_register), CHANGED="", CHANGED_LOCAL="")

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

    def test_a_commit_on_origin_opens_the_gate_and_renders_origin_register(self):
        proc = self.run_tick(CHANGED="mad-science/queue.json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("changed on origin/main: mad-science/queue.json", proc.stdout)
        self.assertEqual(self.call_lines("census"), ["census"])
        self.assertNotIn("skipped:idle", self.outcomes())
        rendered = self.root / ".local" / "board-register.json"
        self.assertTrue(rendered.is_file(), "origin's register was never materialised")
        self.assertIn("from-origin", rendered.read_text(),
                      "the render read a register other than origin's")

    def test_a_local_only_change_skips(self):
        # The negative control for the defect: HEAD moved, origin did not. The old gate compared
        # HEAD and would have run; reading origin/main, this must skip.
        proc = self.run_tick(CHANGED_LOCAL="mad-science/queue.json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("skipped", proc.stdout)
        self.assertEqual(self.outcomes(), ["skipped:idle"])
        self.assertEqual(self.call_lines("census"), [])

    def test_an_idle_fleet_with_no_origin_change_skips(self):
        proc = self.run_tick()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.outcomes(), ["skipped:idle"])
        self.assertEqual(self.call_lines("census"), [])
        self.assertFalse((self.root / ".local" / "board-register.json").exists(),
                         "a skipped tick must not materialise a register")

    def test_the_fetch_is_attempted_before_the_gate(self):
        self.run_tick()
        self.assertEqual(self.call_lines("git fetch"), ["git fetch --quiet origin main"])


class Reconcile(unittest.TestCase):
    """A diverged branch is merged before publishing, never reset or forced (owner direction 2026-11-23).

    This replica accumulates its own board commits while peers push: measured 2026-11-23 it was
    7 ahead / 35 behind and four consecutive fires rendered a fresh board and then died at `push`
    (`failed:push` in the ledger) — the board stayed stale while the gate worked. The local-only
    commits are the tick's own board commits, so a merge is the join; a merge that cannot run is
    aborted and publishes nothing.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.tool = build(self.root)
        self.calls = self.root / "calls.log"
        self.ledger = self.root / ".local" / "board-tick.jsonl"
        self.board = self.root / "mad-science" / "STATUS.md"
        (self.root / ".local" / "fleet-window.lock").unlink()   # no session mark
        self.env = dict(os.environ, PATH=f"{self.root / 'bin'}:{os.environ['PATH']}",
                        CALLS=str(self.calls), REMOTE_BOARD=str(self.root / "remote-STATUS.md"),
                        CHANGED="mad-science/queue.json")

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

    def test_a_diverged_branch_is_merged_then_published(self):
        proc = self.run_tick(ANCESTOR_RC="1", MERGE_RC="0")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("merged origin/main", proc.stdout)
        self.assertIn("git merge --no-edit origin/main", self.call_lines("git merge"))
        self.assertEqual(self.call_lines("census"), ["census"])
        self.assertEqual(self.outcomes(), ["published"])
        self.assertIn("git push", " ".join(self.call_lines("git push")))

    def test_an_up_to_date_branch_is_not_merged(self):
        proc = self.run_tick(ANCESTOR_RC="0")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.call_lines("git merge --no-edit"), [], "an ancestor needs no merge")
        self.assertEqual(self.outcomes(), ["published"])

    def test_a_conflicting_merge_fails_loudly_and_publishes_nothing(self):
        before = self.board.read_bytes()
        proc = self.run_tick(ANCESTOR_RC="1", MERGE_RC="1")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("git merge --abort", self.call_lines("git merge"),
                      "a failed merge must leave the tree as it was")
        self.assertEqual(self.outcomes(), ["failed:merge"])
        self.assertEqual(self.board.read_bytes(), before)
        for prefix in ("census", "task-queue publish", "git commit", "git push"):
            self.assertEqual(self.call_lines(prefix), [], f"{prefix} ran after a failed merge")

    def test_a_peers_uncommitted_change_skips_instead_of_failing(self):
        # Not the tick's failure and not ours to clear: name the file, publish nothing, exit 0.
        proc = self.run_tick(ANCESTOR_RC="1", MERGE_RC="1", MERGE_DIRTY="1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("a peer's uncommitted change blocks the merge", proc.stdout)
        self.assertIn("mad-science/queue.json", proc.stdout)
        self.assertEqual(self.outcomes(), ["skipped:dirty"])
        self.assertEqual(self.call_lines("census"), [])
        self.assertEqual(self.call_lines("git push"), [])


if __name__ == "__main__":
    unittest.main()
