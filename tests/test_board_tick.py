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
if args[:3] == ["render", "--board", "--stale"]:
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
if cmd == "show":
    remote = Path(os.environ["REMOTE_BOARD"])
    if remote.is_file():
        sys.stdout.buffer.write(remote.read_bytes())
        sys.exit(0)
    sys.exit(128)
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
    (root / "remote-STATUS.md").write_text("# Board — generated 2026-11-21 22:00 ET\n")
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
        self.assertEqual(self.call_lines("task-queue render"), ["task-queue render --board --stale"])
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


if __name__ == "__main__":
    unittest.main()
