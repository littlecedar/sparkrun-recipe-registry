"""No syncthing conflict copies inside any tree the registry reads or runs.

Why this is a class bug, not litter: `.gitignore` carries `**/*.sync-conflict-*` (line 19), so a
conflict copy never reaches git — but it does land on disk, and **sparkrun reads the working tree**.
A `*.sync-conflict-*.yaml` under `recipes/` is therefore a launchable recipe (`sparkrun run
@littlecedar/<name>` resolves the filename minus `.yaml`), a copy under a lane's `mods/` changes what
a recipe ships at pre_exec, and a copy under `benchmarking/` or `tuning/` is a profile or config
sparkrun will happily list. `.github/` is the same shape for GitHub: every `*.yml` there is a
workflow, so a copy of `refresh-sweep.yml` becomes a second nightly sweep (real: one appeared on
2026-10-22 and had to be removed by hand).

The single exemption is a deliberately tracked fixture: `discover` rejects dashed module names, so
the copy of `test_qwen3_vl_embeddings` is inert as a test but kept as the repo's example of the
shape. It must exist and be tracked — that is the reason it is allowed to stay.

Text-only and stdlib: the tree walk is `pathlib`, and the two git questions (`is it tracked?`,
`is it ignored?`) use the `git` binary when present and skip with a printed reason when not.
"""
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Every directory a launch or a CI load walks. `recipes/`, `mods/`, `benchmarking/` and `tuning/`
# are named by `.sparkrun/registry.yaml` (recipes, mods, benchmarks, tuning); `plugins/` is loaded
# inside a sparkrun process via `plugins.paths`; `tests/` and `tools/` are executed by hand or by
# the gate; `.github/` is GitHub's loader.
WATCHED = ("recipes", "mods", "tools", "tests", "benchmarking", "plugins", "tuning", ".sparkrun",
           ".github")
PATTERN = "*sync-conflict*"
# The one documented exemption: tracked on purpose (27 lines of header explain it), never deleted.
FIXTURE = "tests/test_qwen3_vl_embeddings.sync-conflict-20260919-005631-AY4HZ2K.py"
PLANTED = "recipes/lane/arm.sync-conflict-20260101-000000-AAAAAA.yaml"


def conflict_copies(root):
    """Relative paths of conflict copies under the watched trees. A missing watched dir RAISES."""
    root = Path(root)
    missing = [d for d in WATCHED if not (root / d).is_dir()]
    if missing:
        raise AssertionError(f"watched dirs missing under {root}: {missing}")
    found = []
    for d in WATCHED:
        found.extend(p.relative_to(root).as_posix() for p in (root / d).rglob(PATTERN))
    return sorted(found)


def git(*args):
    """(returncode, stdout) for a git call; a missing git binary is a skip, never a pass."""
    try:
        r = subprocess.run(["git", "-C", str(REPO_ROOT), *args],
                           capture_output=True, text=True)
    except (FileNotFoundError, NotADirectoryError):
        raise unittest.SkipTest("git binary not available: the tracked/ignored questions cannot be asked")
    return r.returncode, (r.stdout or "").strip()


class WatchedTreesAreClean(unittest.TestCase):
    def test_only_the_tracked_fixture_remains(self):
        self.assertEqual(conflict_copies(REPO_ROOT), [FIXTURE])

    def test_the_fixture_is_tracked(self):
        self.assertTrue((REPO_ROOT / FIXTURE).is_file(), FIXTURE)
        code, out = git("ls-files", "--error-unmatch", FIXTURE)
        self.assertEqual(code, 0, f"{FIXTURE} must be tracked, not debris: {out}")

    def test_the_ignore_rule_keeps_copies_out_of_git(self):
        # The mechanism that makes this a class bug: ignored, therefore never reviewed, while the
        # file still sits on disk and sparkrun still reads it. `--no-index` asks the rule, not disk.
        code, out = git("check-ignore", "--no-index", "-v", PLANTED)
        self.assertEqual(code, 0, f"{PLANTED} must be ignored by .gitignore: {out}")
        self.assertIn("sync-conflict", out)


class NegativeControls(unittest.TestCase):
    def test_a_planted_copy_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            for d in WATCHED:
                (Path(tmp) / d).mkdir(parents=True)
            planted = Path(tmp) / PLANTED
            planted.parent.mkdir(parents=True)
            planted.write_text("model: some/repo\n", encoding="utf-8")
            self.assertEqual(conflict_copies(tmp), [PLANTED],
                             "a conflict copy under a watched tree must be reported")

    def test_a_copy_under_mods_is_caught_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            for d in WATCHED:
                (Path(tmp) / d).mkdir(parents=True)
            planted = Path(tmp) / "recipes/lane/mods/launcher/run.sync-conflict-20260101-000000-BBBBBB.sh"
            planted.parent.mkdir(parents=True)
            planted.write_text("#!/bin/bash\n", encoding="utf-8")
            self.assertEqual(
                conflict_copies(tmp),
                ["recipes/lane/mods/launcher/run.sync-conflict-20260101-000000-BBBBBB.sh"])

    def test_a_missing_watched_dir_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "recipes").mkdir()
            with self.assertRaises(AssertionError):
                conflict_copies(tmp)


if __name__ == "__main__":
    unittest.main()
