"""Guards for tools/board-render.py — STATUS.md derived, never composed by hand.

Run:
    uv run python -B -m unittest tests.test_board_render -v

Stdlib-only, no network, no cluster.  A fake `git` on PATH prints a fixture `git log`, so the
landed rows are the same bytes on every machine; the evidence pair and the register are checked-in
fixtures mirroring today's board (a fenced serve on `.31`-`.34`, an idle `.30`/`.35`, the meta
restart loop, one live lease and one expired one).

What is pinned:
* byte equality with `tests/fixtures/board/expected-STATUS.md` — the acceptance test: any drift in
  a cell, a separator or the section order fails here rather than on the published board;
* the rendered body passes `lint_markdown`, `address_problems` and `inflight_problems`, the three
  guards `task-queue.py publish` applies;
* the shape: section order, the three table headers, and the In flight key order — the renderer
  reproduces the board's skeleton even where a cell's contents differ;
* the arithmetic: a delta's sign becomes its direction word, the base interval is computed, and a
  node absent from the base says so instead of inventing a number.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "board-render.py"
TASK_QUEUE = REPO_ROOT / "tools" / "task-queue.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "board"
EXPECTED = FIXTURES / "expected-STATUS.md"

#: `git -C <repo> log --since=<base> --format=%h %at %s` -> the checked-in log, newest first.
GIT_STUB = """#!/bin/sh
cat "$FIXTURES/git-log.txt"
"""


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


tq = _load("task_queue", TASK_QUEUE)


def inflight_order(text):
    """The In flight first cells in file order (the keys, plus any live-lease rows)."""
    lines = text.split("\n")
    start = lines.index("## In flight")
    keys = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        if not line.lstrip().startswith("|"):
            continue
        cell = line.split("|")[1].strip().strip("`").split()
        if cell and cell[0] != "where" and not set(cell[0]) <= set("-:"):
            keys.append(cell[0])
    return keys


def skeleton(text):
    """Headings plus the line that starts each table — the board's shape, not its cells."""
    lines = text.split("\n")
    shape = []
    for index, line in enumerate(lines):
        if line.startswith("## "):
            shape.append(line)
        elif (line.startswith("| ") and index + 1 < len(lines)
              and lines[index + 1].startswith("|---")):
            shape.append(line)
    return shape


class BoardRender(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        stub = self.bin / "git"
        stub.write_text(GIT_STUB, encoding="utf-8")
        stub.chmod(0o755)
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                        FIXTURES=str(FIXTURES))
        self.out = self.root / "STATUS.md"

    def render(self):
        proc = subprocess.run(
            [sys.executable, "-B", str(TOOL),
             "--evidence", str(FIXTURES / "evidence-next.json"),
             "--prev", str(FIXTURES / "evidence.json"),
             "--register", str(FIXTURES / "register.json"),
             "--repo", str(self.root), "--out", str(self.out)],
            capture_output=True, text=True, env=self.env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return self.out.read_text(encoding="utf-8")

    def test_renders_the_checked_in_board_byte_for_byte(self):
        text = self.render()
        self.assertEqual(text.encode("utf-8"), EXPECTED.read_bytes(),
                         "a cell, separator or section order drifted from the checked-in board")

    def test_the_body_passes_the_publish_guards(self):
        text = self.render()
        self.assertEqual(tq.lint_markdown(text), [])
        self.assertEqual(tq.address_problems(text), [])
        self.assertEqual(tq.inflight_problems(text), [])

    def test_the_section_skeleton_is_the_boards(self):
        text = self.render()
        self.assertEqual(skeleton(text), [
            "## In flight", "| where | owner | what |",
            "## Work queue", "| job | node cost | holds | state |",
            "## Landed session", "| time ET | commit | one clause |"])
        self.assertEqual(inflight_order(text)[:13],
                         ["census", "pool", "queue", "window", "campaign", "lease",
                          "publication", ".30", ".31", ".32", ".33", ".34", ".35"])
        self.assertEqual(inflight_order(text)[13:], ["lease-1"],
                         "one row per live lease; the expired one is not listed")

    def test_every_measurement_is_derived(self):
        text = self.render()
        # .30's root avail rose by 283,648 B on the base; .31's fell by 979,200 B.
        self.assertIn("**1,371,101,020,160 B avail** (+283,648, rose)", text)
        self.assertIn("**1,649,791,016,960 B avail** (-979,200, fell)", text)
        # A node the base never saw states that instead of inventing a delta.
        self.assertIn("(no base, unmeasured)", text)
        # The head's recorded delta becomes the pool row's restart arithmetic.
        self.assertIn("NRestarts 36,536, **+6** on the base", text)
        # Interval from the base census read (00:13:43Z) to the first node read (01:12:34Z).
        self.assertIn("**0 h 58 min 51 s** after it", text)
        # The fenced hosts are excluded from research accounting, derived from the ledger.
        self.assertIn("**no research rank**", text)
        self.assertIn("the fenced hosts hold running containers on `.31`, `.32`, `.33`, `.34`", text)
        # Landed rows come from the fixture git log, oldest first, with the ET clock.
        self.assertLess(text.index("`e4f5a6b`"), text.index("`a1b2c3d`"))
        self.assertIn("| 11-21 19:40 | `e4f5a6b` | Add the census evidence schema |", text)
        # The register block is task-queue.py's own rendering, not a second copy of it.
        data = tq.load(FIXTURES / "register.json")
        for row in tq.board_rows(data, FIXTURES / "register.json"):
            self.assertIn(row, text)

    def test_a_missing_evidence_file_exits_one(self):
        proc = subprocess.run(
            [sys.executable, "-B", str(TOOL), "--evidence", str(self.root / "nope.json")],
            capture_output=True, text=True, env=self.env)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("cannot read its inputs", proc.stderr)


if __name__ == "__main__":
    unittest.main()
