"""Guards for tools/doc-census.py — the entry points' counts are derived, not remembered.

Run:
    uv run python -B -m unittest discover -s tests

Stdlib-only, no network, no cluster, like every other guard here.

Why this file exists.  A global count restated in prose rots the moment the tree
changes, and on 2026-10-31 four entry-point counts were stale at once
(`AGENTS.md` claimed 79 tracked recipes against 80, 46 test modules against 51).
`tools/doc-census.py` derives those four from the tracked tree; this file is
what makes the derivation load-bearing — without it the tool is a report, and a
report gets skipped.

The negative controls are the point, not the happy path: a mutated count in a
copy of an entry point must fail the check *and* name its file and line, and
`--fix` must rewrite the digits without touching one byte around them.  A
checker that cannot be shown to fire is the decoration this repo already has a
word for.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "doc-census.py"

# A miniature entry point: one correct statement per checked pattern shape.
GOOD = "# Facts\n\n80 tracked recipes. 51 test modules. 35 profiles. 19 `SKILL.md` dirs.\n"
BAD = "# Facts\n\n79 tracked recipes. 51 test modules. 35 profiles. 19 `SKILL.md` dirs.\n"
FACTS = ["--fact", "recipes=80", "--fact", "test_modules=51",
         "--fact", "profiles=35", "--fact", "skills=19"]


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), *args],
                          capture_output=True, text=True, cwd=REPO_ROOT, check=False)


class EntryPointCounts(unittest.TestCase):
    def test_roster_docs_exist(self):
        """A rename must fail here, not silently disable the whole check."""
        for name in ("AGENTS.md", "README.md"):
            self.assertTrue((REPO_ROOT / name).is_file(), f"missing roster doc {name}")

    def test_entry_points_agree_with_the_tracked_tree(self):
        out = run("--check")
        self.assertEqual(out.returncode, 0,
                         f"stale count in an entry point:\n{out.stderr}")

    def test_facts_are_derived_from_git_not_the_working_tree(self):
        """An untracked draft recipe must not move the checked number.

        2026-10-30: five commits were reported green off a local suite while CI
        failed, because the tool read an untracked `.scratch/` file.  The count
        has the same failure: a draft recipe on the workstation is not a recipe
        the registry ships.
        """
        git = shutil.which("git")
        if not git:
            self.skipTest("git not on PATH")
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([git, "init", "-q", tmp], check=True, capture_output=True)
            lane = Path(tmp, "recipes", "lane")
            lane.mkdir(parents=True)
            Path(lane, "shipped.yaml").write_text("x: 1\n")
            subprocess.run([git, "-C", tmp, "add", "recipes/lane/shipped.yaml"],
                           check=True, capture_output=True)
            Path(lane, "draft.yaml").write_text("x: 2\n")  # untracked
            out = run("--root", tmp, "--json")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["facts"]["recipes"], 1)


class NegativeControls(unittest.TestCase):
    """The check must fire on a wrong number, and only on the number."""

    def _tree(self, text: str) -> tempfile.TemporaryDirectory:
        tmp = tempfile.TemporaryDirectory()
        Path(tmp.name, "AGENTS.md").write_text(text)
        Path(tmp.name, "README.md").write_text("# README\n")
        return tmp

    def test_correct_statements_pass(self):
        with self._tree(GOOD) as tmp:
            out = run("--root", tmp, "--check", *FACTS)
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_stale_count_is_named_by_file_and_line(self):
        with self._tree(BAD) as tmp:
            out = run("--root", tmp, "--check", *FACTS)
        self.assertEqual(out.returncode, 1, "a stale count must fail the check")
        self.assertIn("AGENTS.md:3:", out.stderr)
        self.assertIn("stated 79, actual 80", out.stderr)

    def test_fix_rewrites_the_digits_and_nothing_else(self):
        with self._tree(BAD) as tmp:
            out = run("--root", tmp, "--fix", *FACTS)
            fixed = Path(tmp, "AGENTS.md").read_text()
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(fixed, GOOD, "--fix must change only the number")


if __name__ == "__main__":
    unittest.main()