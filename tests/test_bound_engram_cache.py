"""Guards for the `bound-engram-cache` mod.

Run:
    python3 -m unittest discover -s tests -v

Stdlib-only, deliberate (AGENTS.md: "tools/ and tests/ are stdlib-only, on
purpose") -- this must run on a head node, in a container, and on a laptop.

Why these exist. `mods/bound-engram-cache` patches the Engram-on-disk reader
that `mods/mount-dsv41-exl3-patches` installs, adding a POSIX_FADV_DONTNEED
after each gathered read so read-once rows do not accumulate in the host page
cache (attic/ds4/MEMORY-RECLAIM-PLAN.md §7). Three things must hold, and all
are testable offline against the shipped sibling file:

  * the patch APPLIES to the shipped reader and keeps the read intact;
  * the fadvise is added ONCE PER BATCH (after the `for`, not inside it);
  * it FAILS CLOSED on anything that is not the expected reader.

Every guard has a negative control in NegativeControls; controls mutate strings
in memory or write a temp file, and never touch the repo tree.
"""

from __future__ import annotations

import ast
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MOD_DIR = REPO_ROOT / "mods" / "bound-engram-cache"
RUN_SH = MOD_DIR / "run.sh"
PATCHER = MOD_DIR / "patch_engram_fadvise.py"
MD5SUMS = MOD_DIR / "files" / "MD5SUMS.txt"
# The shipped reader this mod must patch: the sibling mod's vendored copy.
SIBLING_ENGRAM = REPO_ROOT / "mods" / "mount-dsv41-exl3-patches" / "files" / "engram.py"

MARKER = "# sparkrun mod: bound-engram-cache v1"


def _strip_comment_lines(text: str) -> str:
    """Drop whole-line `#` comments (AGENTS.md F20: prose names the patterns)."""
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def _run_patcher(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(PATCHER), *args],
        capture_output=True, text=True, timeout=120,
    )


def _patch_copy(root: Path) -> Path:
    dst = root / "engram.py"
    shutil.copy2(SIBLING_ENGRAM, dst)
    r = _run_patcher([str(dst)])
    if r.returncode != 0:
        raise AssertionError("patcher refused the shipped reader: %s" % (r.stderr,))
    return dst


class ModShape(unittest.TestCase):
    def test_mod_files_present_and_executable(self):
        for p in (RUN_SH, PATCHER, MD5SUMS, MOD_DIR / "README.md"):
            self.assertTrue(p.is_file(), "missing %s" % p)
        self.assertTrue(RUN_SH.stat().st_mode & 0o111, "run.sh not executable")
        src = RUN_SH.read_text(encoding="utf-8")
        self.assertIn("set -euo pipefail", src)
        self.assertIn('MOD_NAME="bound-engram-cache"', src)

    def test_md5sums_matches_the_patcher(self):
        """run.sh verifies the patcher at launch; drift must fail the suite first."""
        want = hashlib.md5(PATCHER.read_bytes()).hexdigest()
        got = MD5SUMS.read_text().split()[0]
        self.assertEqual(got, want, "files/MD5SUMS.txt does not match the patcher")

    def test_run_sh_is_fail_closed_and_ordered(self):
        src = RUN_SH.read_text(encoding="utf-8")
        lines = _strip_comment_lines(src)
        self.assertIn("md5sum --check", lines, "must md5-verify the patcher")
        self.assertIn('--check "${TARGET}"', lines, "must run the patcher's --check")
        # It depends on the sibling having installed the reader first.
        self.assertIn("DSV41_ENGRAM_DISK", lines,
                      "must refuse unless the on-disk reader is installed")
        self.assertIn("sparkrun-orig", lines, "must back the target up once")


class PatchBehaviour(unittest.TestCase):
    def test_patch_applies_and_keeps_the_read_intact(self):
        with tempfile.TemporaryDirectory() as td:
            dst = _patch_copy(Path(td))
            text = dst.read_text()
            self.assertEqual(text.count(MARKER), 1, "marker must appear exactly once")
            self.assertIn("POSIX_FADV_DONTNEED", text)
            # Exactly one preadv call survives: the read is unchanged.
            fn = self._fn_ast(text)
            preadv = [c for c in ast.walk(fn)
                      if isinstance(c, ast.Call)
                      and isinstance(c.func, ast.Attribute) and c.func.attr == "preadv"]
            self.assertEqual(len(preadv), 1, "the preadv read must be untouched")

    def test_fadvise_is_per_batch_not_per_row(self):
        """The fadvise must sit AFTER the `for`, not inside it (once per batch)."""
        with tempfile.TemporaryDirectory() as td:
            text = _patch_copy(Path(td)).read_text()
            fn = self._fn_ast(text)
            for_node = [n for n in fn.body if isinstance(n, ast.For)]
            self.assertEqual(len(for_node), 1, "expected one gather loop")
            inside = {id(n) for n in ast.walk(for_node[0])}
            fadvise = [n for n in ast.walk(fn)
                       if isinstance(n, ast.Call)
                       and isinstance(n.func, ast.Attribute)
                       and n.func.attr == "posix_fadvise"]
            self.assertEqual(len(fadvise), 1, "expected exactly one fadvise call")
            self.assertNotIn(id(fadvise[0]), inside,
                             "fadvise must not be inside the per-row loop")

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            dst = _patch_copy(Path(td))
            once = dst.read_text()
            r = _run_patcher([str(dst)])
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(dst.read_text(), once, "second run must be a no-op")
            r = _run_patcher(["--check", str(dst)])
            self.assertEqual(r.returncode, 0)
            self.assertIn("already patched", r.stdout)

    def test_check_reports_compatible_on_the_shipped_reader(self):
        r = _run_patcher(["--check", str(SIBLING_ENGRAM)])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("compatible", r.stdout)

    @staticmethod
    def _fn_ast(text: str) -> ast.FunctionDef:
        tree = ast.parse(text)
        fns = [n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "_kai_pread_rows"]
        assert len(fns) == 1, "expected exactly one _kai_pread_rows"
        return fns[0]


class NegativeControls(unittest.TestCase):
    """A guard that cannot fail proves nothing. These mutate copies in temp dirs."""

    def test_refuses_a_reader_without_the_anchor(self):
        with tempfile.TemporaryDirectory() as td:
            bogus = Path(td) / "engram.py"
            bogus.write_text(
                "def _kai_pread_rows(fd, base, rel, lo, hi, row_bytes, buf):\n"
                "    return None\n"
            )
            r = _run_patcher(["--check", str(bogus)])
            self.assertNotEqual(r.returncode, 0,
                                "must refuse a file that is not the shipped reader")

    def test_refuses_when_a_second_preadv_appears(self):
        """Two preadv calls means the reader changed; refuse rather than guess."""
        with tempfile.TemporaryDirectory() as td:
            text = SIBLING_ENGRAM.read_text().replace(
                "            got += n\n",
                "            got += n\n            n2 = _kai_os.preadv(fd, [view[got:]], off)\n",
                1,
            )
            mutated = Path(td) / "engram.py"
            mutated.write_text(text)
            r = _run_patcher(["--check", str(mutated)])
            self.assertNotEqual(r.returncode, 0, "a second preadv must be refused")

    def test_patch_is_not_vacuous(self):
        """The patched output must differ from the input (guards a no-op patch)."""
        with tempfile.TemporaryDirectory() as td:
            dst = _patch_copy(Path(td))
            self.assertNotEqual(
                dst.read_text(), SIBLING_ENGRAM.read_text(),
                "the patched reader must differ from the shipped one",
            )

    def test_marker_must_have_the_fadvise(self):
        """A marker-only edit (no fadvise) must be rejected by the shape check."""
        with tempfile.TemporaryDirectory() as td:
            text = SIBLING_ENGRAM.read_text()
            text = text.replace(
                "def _kai_pread_rows(\n", "def _kai_pread_rows(\n    " + MARKER + "\n", 1
            )
            marker_only = Path(td) / "engram.py"
            marker_only.write_text(text)
            r = _run_patcher(["--check", str(marker_only)])
            self.assertNotEqual(r.returncode, 0,
                                "a marker with no fadvise must be refused")


if __name__ == "__main__":
    unittest.main()
