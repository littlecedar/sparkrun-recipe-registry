"""`tools/push-gate.py` must reject on the committed tree what `gate.yml` rejects.

Why: on 2026-11-08 gate runs #1205-#1210 were six consecutive red pushes, five of
them a stale stated suite total and one an RFC1918 literal in tracked prose.  A
gate nobody has watched fire is the decoration this repo already has a name for,
so each class here is proved to fail *and* to quote the same assertion CI prints,
and one case proves the verdict comes from `git archive HEAD` rather than from a
worktree a peer's uncommitted edit can move.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATE = REPO / "tools" / "push-gate.py"

# Built by parts: this file is scanned by the guard it exercises, so the leak it plants
# must not be an RFC1918 literal in the scanned bytes.
LEAK = ".".join(["10", "0", "4", "34"])


def env() -> dict[str, str]:
    """The caller's shell may carry GIT_* for another repository; the fixture must not."""
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, env=env())


def commit(root: Path, message: str) -> None:
    run(["git", "-C", str(root), "add", "-A"], root)
    run(["git", "-C", str(root), "-c", "user.email=gate@example.invalid",
         "-c", "user.name=gate", "commit", "-qm", message], root)


def discovered(root: Path) -> int:
    out = run([sys.executable, "-B", "-c",
               "import unittest;print(unittest.defaultTestLoader.discover('tests').countTestCases())"],
              root)
    return int(out.stdout.strip())


def agents(total: int) -> str:
    return (f"# Fixture\n\nThe suite is **{total} tests, 2 skipped**, dated today.\n\n"
            f"snapshot: suite {total} tests (derived discovery).\n")


class PushGate(unittest.TestCase):
    def setUp(self):
        if not shutil.which("git"):
            self.skipTest("git not on PATH")
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "repo"
        (self.root / "tools").mkdir(parents=True)
        (self.root / "tests").mkdir()
        (self.root / "README.md").write_text("# Fixture\n", encoding="utf-8")
        shutil.copy2(GATE, self.root / "tools/push-gate.py")
        shutil.copy2(REPO / "tools/doc-census.py", self.root / "tools/doc-census.py")
        for name in ("test_doc_hygiene.py", "test_tracked_address_hygiene.py"):
            shutil.copy2(REPO / "tests" / name, self.root / "tests" / name)
        # `test_every_exemption_still_exists` requires every EXEMPT path to be tracked.
        (self.root / "recipes/ds4/benchmarks/data").mkdir(parents=True)
        (self.root / "recipes/ds4/benchmarks/data/hle_test.jsonl").write_text("", encoding="utf-8")
        (self.root / "tests/test_ci_workflows.py").write_text(
            "# fixture: exempt path, tracked for test_every_exemption_still_exists\n",
            encoding="utf-8")
        (self.root / "tests/test_fixture_sample.py").write_text(
            "import unittest\n\n\nclass Sample(unittest.TestCase):\n"
            + "".join(f"    def test_{i}(self):\n        pass\n\n" for i in range(4)),
            encoding="utf-8")
        run(["git", "init", "-q", str(self.root)], self.root)
        self.total = discovered(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def gate(self) -> subprocess.CompletedProcess:
        return run([sys.executable, "-B", str(self.root / "tools/push-gate.py")], self.root)

    def test_clean_committed_tree_passes(self):
        (self.root / "AGENTS.md").write_text(agents(self.total), encoding="utf-8")
        commit(self.root, "clean")
        out = self.gate()
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("push-gate: ok", out.stdout)

    def test_stale_stated_total_fails_and_quotes_the_assertion(self):
        (self.root / "AGENTS.md").write_text(agents(self.total + 1), encoding="utf-8")
        commit(self.root, "stale total")
        out = self.gate()
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn(f"states {self.total + 1} tests; discovery finds {self.total}",
                      out.stdout + out.stderr)
        self.assertIn("push-gate: repair: uv run python -B tools/doc-census.py --fix",
                      out.stdout + out.stderr)

    def test_tracked_address_literal_fails(self):
        (self.root / "AGENTS.md").write_text(agents(self.total), encoding="utf-8")
        (self.root / "docs").mkdir()
        (self.root / "docs/leak.md").write_text(f"measured on {LEAK} today\n", encoding="utf-8")
        commit(self.root, "leak")
        out = self.gate()
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn("docs/leak.md:1:", out.stdout + out.stderr)

    def test_it_reads_the_archive_not_the_worktree(self):
        """A peer's uncommitted count edit and a stray untracked test are not what CI sees."""
        (self.root / "AGENTS.md").write_text(agents(self.total), encoding="utf-8")
        commit(self.root, "clean")
        (self.root / "AGENTS.md").write_text(agents(self.total + 1), encoding="utf-8")  # dirty
        (self.root / "tests/test_untracked_draft.py").write_text(
            "import unittest\n\n\nclass Draft(unittest.TestCase):\n"
            + "".join(f"    def test_{i}(self):\n        pass\n\n" for i in range(3)),
            encoding="utf-8")
        out = self.gate()
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)


if __name__ == "__main__":
    unittest.main()
