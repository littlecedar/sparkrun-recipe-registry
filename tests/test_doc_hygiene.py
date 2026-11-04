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
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "doc-census.py"

#: A stated suite total: `suite 1247 tests` in the snapshot paragraph, `**1247 tests,` in
#: Testing & QA. Both are entry-point statements of one fact, and the lookbehind keeps
#: unrelated counts (`(22 tests)`, `166 control tests`) out of the roster.
SUITE_TOTAL = re.compile(r"(?:(?<=suite )|(?<=\*\*))(\d+)(?= tests)")


def stated_suite_totals(text: str) -> list[tuple[int, int]]:
    """(lineno, stated total) for every suite-total statement in an entry point."""
    return [(lineno, int(found.group(1)))
            for lineno, line in enumerate(text.splitlines(), 1)
            for found in SUITE_TOTAL.finditer(line)]


def stale_suite_totals(text: str, actual: int) -> list[tuple[int, int]]:
    """The statements that disagree with the discovered count, as (lineno, stated)."""
    return [(lineno, stated) for lineno, stated in stated_suite_totals(text) if stated != actual]

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


class SuiteTotal(unittest.TestCase):
    """The stated suite total is derived from discovery, not remembered.

    Why: the number went stale three times in one night (2026-11-04) because only a run
    could produce it, and a re-run is exactly what a doc edit skips. `countTestCases()`
    executes nothing and takes under a second, so the total is checked here; the skip
    count still needs a run, which is why the statement carries the date of that run.
    """

    def test_every_stated_total_matches_the_discovered_count(self):
        text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        stated = stated_suite_totals(text)
        self.assertGreaterEqual(
            len(stated), 2,
            "both suite-total statements must be found -- a reworded statement has to fail "
            "here rather than silently drop the check")
        actual = unittest.defaultTestLoader.discover(str(REPO_ROOT / "tests")).countTestCases()
        for lineno, count in stale_suite_totals(text, actual):
            self.fail(f"AGENTS.md:{lineno}: states {count} tests; discovery finds {actual}")


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

    def test_a_stale_suite_total_is_named_by_line(self):
        """Both statement shapes are read, and a wrong total is the only thing that fires."""
        text = "# Facts\n**1250 tests,\n  all passing 2026-11-04 (2 skipped:** and suite 1247 tests\n"
        self.assertEqual(stated_suite_totals(text), [(2, 1250), (3, 1247)])
        self.assertEqual(stale_suite_totals(text, 1247), [(2, 1250)])
        self.assertEqual(stale_suite_totals(text, 1250), [(3, 1247)])
        # An unrelated count must not be read as the total, or the guard fires on a healthy doc.
        self.assertEqual(stated_suite_totals("`tests/*.sync-conflict-*.py` (22 tests)\n"), [])


if __name__ == "__main__":
    unittest.main()