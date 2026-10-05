"""Guards for the `drop-caches` mod.

Run:
    python3 -m unittest discover -s tests -v

Stdlib-only, deliberate (AGENTS.md: "tools/ and tests/ are stdlib-only, on
purpose") -- this must run on a head node, in a container, and on a laptop.

Why these exist. `@eugr/mods/drop-caches` is listed across this registry and is
INERT: its loop process starts and stays alive (so it reads as success) while the
host page cache is never touched. Two independent causes, both reproduced in
mods/drop-caches/README.md on 2026-09-27:

  1. rootless (sparkrun's default) mounts /proc/sys `ro`, so the write is refused;
  2. eugr's line `echo 3 > TARGET >> LOG 2>&1` sends `3` to the LOG, because bash
     applies redirects left-to-right and the last stdout redirect wins.

This mod fixes both and FAILS CLOSED. The guards below execute the mod against a
stand-in target file (MOD_DROP_CACHES_TARGET) and assert both directions:

  * writable target -> the target receives the level exactly once, rc 0;
  * unwritable / missing -> rc 1, and the target is left untouched.

The stand-in is necessary: the CI/laptop host's real /proc/sys/vm/drop_caches is
root-only (writing it needs privilege), but the code path under test -- the single
redirect and the fail-closed gate -- is byte-identical. Every guard has a negative
control in NegativeControls; controls mutate strings in memory or chmod a temp
file, and never touch the real /proc/sys.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MOD_DIR = REPO_ROOT / "mods" / "drop-caches"
MOD_SCRIPT = MOD_DIR / "run.sh"


def strip_comment_lines(text: str) -> str:
    """Drop whole-line `#` comments, because the mod's prose NAMES the bug.

    The README and the in-file comment quote the eugr redirection-order bug
    verbatim, including the pattern the structural guard forbids (AGENTS.md F20:
    a guard that scans raw text fires on its own explanatory prose). This strips
    comment lines so only executable lines are scanned.
    """
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def _run_mod(env_extra: dict[str, str], root: Path, timeout: int = 120) -> subprocess.CompletedProcess:
    workdir = root / "mod"
    workdir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MOD_SCRIPT, workdir / "run.sh")
    env = {k: v for k, v in os.environ.items() if not k.startswith("MOD_")}
    env.setdefault("PATH", "/usr/bin:/bin")
    env.update(env_extra)
    return subprocess.run(
        ["bash", str(workdir / "run.sh")],
        capture_output=True, text=True, timeout=timeout, env=env, cwd=str(workdir),
    )


def _base_env(cache: Path, target: Path | str, **extra: str) -> dict[str, str]:
    env = {
        "MOD_CACHEDIR": str(cache),
        "MOD_LOGDIR": str(cache / "modlogs"),
        "MOD_DROP_CACHES_TARGET": str(target),
    }
    env.update(extra)
    return env


class ModShape(unittest.TestCase):
    def test_mod_is_executable_and_harness_complete(self):
        self.assertTrue(MOD_SCRIPT.is_file(), "missing %s" % MOD_SCRIPT)
        self.assertTrue(MOD_SCRIPT.stat().st_mode & 0o111, "%s not executable" % MOD_SCRIPT)
        src = MOD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("set -euo pipefail", src)
        self.assertIn("SPDX-License-Identifier: AGPL-3.0-or-later", src)
        # mod-template harness bits the house convention requires
        for token in ('MOD_NAME="drop-caches"', "reown()", "log_var()", "log_cmd()"):
            self.assertIn(token, src, "mod-template harness missing %r" % token)
        self.assertIn("reown \"${LOGDIR}\"", src, "mod must re-own the log dir after writing to it")


class DropBehaviour(unittest.TestCase):
    """The write is proven at the point of use, not by a live process."""

    def test_writable_target_receives_level_exactly_once(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "cache"
            cache.mkdir()
            target = root / "fake_drop_caches"
            target.write_text("")
            r = _run_mod(_base_env(cache, target), root)
            self.assertEqual(r.returncode, 0, (r.stdout, r.stderr))
            self.assertEqual(target.read_text(), "3\n",
                             "target must receive exactly the level, once")

    def test_level_is_configurable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "cache"
            cache.mkdir()
            target = root / "fake_drop_caches"
            target.write_text("")
            r = _run_mod(_base_env(cache, target, MOD_DROP_CACHES_LEVEL="1"), root)
            self.assertEqual(r.returncode, 0, (r.stdout, r.stderr))
            self.assertEqual(target.read_text(), "1\n")

    def test_readonly_target_fails_closed_and_leaves_target_empty(self):
        """The whole point: an unprivileged drop must NOT look like success."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "cache"
            cache.mkdir()
            target = root / "fake_drop_caches"
            target.write_text("")
            target.chmod(0o444)
            r = _run_mod(_base_env(cache, target), root)
            self.assertEqual(r.returncode, 1, "a refused write must fail the launch")
            self.assertEqual(target.read_text(), "", "no level may reach an unwritable target")
            log = (cache / "modlogs" / "drop-caches.log").read_text()
            self.assertIn("ERROR", log)
            self.assertIn("NOT privileged", log)

    def test_missing_target_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "cache"
            cache.mkdir()
            r = _run_mod(_base_env(cache, root / "does-not-exist"), root)
            self.assertEqual(r.returncode, 1, "a missing drop_caches must fail the launch")

    def test_default_mode_is_once(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "cache"
            cache.mkdir()
            target = root / "fake_drop_caches"
            target.write_text("")
            r = _run_mod(_base_env(cache, target), root)
            self.assertEqual(r.returncode, 0, (r.stdout, r.stderr))
            self.assertFalse((cache / "modlogs" / "drop-caches-loop.pid").exists(),
                             "default must be `once`, no loop process")

    def test_loop_mode_writes_a_drop_line(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "cache"
            cache.mkdir()
            target = root / "fake_drop_caches"
            target.write_text("")
            r = _run_mod(_base_env(cache, target, MOD_DROP_CACHES_MODE="loop",
                                   MOD_DROP_CACHES_INTERVAL="2"), root)
            self.assertEqual(r.returncode, 0, (r.stdout, r.stderr))
            self.assertTrue((cache / "modlogs" / "drop-caches-loop.pid").exists(),
                            "loop mode must record the flusher pid")
            import time
            time.sleep(3)
            loop_log = cache / "modlogs" / "drop-caches-loop.log"
            self.assertTrue(loop_log.exists(), "loop mode must write a loop log")
            self.assertRegex(loop_log.read_text(), r"drop-caches (ok|FAILED)")
            # The flusher is a child this test owns; stop it so the suite is clean.
            pid = int((cache / "modlogs" / "drop-caches-loop.pid").read_text().strip())
            try:
                os.kill(pid, 15)
            except ProcessLookupError:
                pass

    def test_loop_rejects_non_integer_interval(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "cache"
            cache.mkdir()
            target = root / "fake_drop_caches"
            target.write_text("")
            r = _run_mod(_base_env(cache, target, MOD_DROP_CACHES_MODE="loop",
                                   MOD_DROP_CACHES_INTERVAL="soon"), root)
            self.assertEqual(r.returncode, 1)
            self.assertIn("integer", (cache / "modlogs" / "drop-caches.log").read_text())


class StructuralGuards(unittest.TestCase):
    """Static checks that the two eugr defects cannot be reintroduced."""

    # A stdout redirect to the target followed by ANOTHER stdout redirect on the
    # same line: `> X >> Y`. The lookbehind excludes fd redirects like `2>>`.
    DROP_TARGET_WRITE = re.compile(r"(?<![0-9])>\s*\S+\s*>>")

    def test_no_double_redirect_on_the_target_write(self):
        """The eugr bug was `> TARGET >> LOG`: the last stdout redirect wins."""
        exec_lines = strip_comment_lines(MOD_SCRIPT.read_text(encoding="utf-8"))
        self.assertNotRegex(
            exec_lines, self.DROP_TARGET_WRITE,
            "the drop write must have exactly ONE stdout redirect; a following "
            "`>>` steals it (the eugr redirection-order bug)",
        )

    def test_write_failure_is_gated_on_the_real_exit_status(self):
        exec_lines = strip_comment_lines(MOD_SCRIPT.read_text(encoding="utf-8"))
        self.assertIn("rc=$?", exec_lines, "the write must capture its exit status")
        self.assertRegex(exec_lines, r'die\s+"?could not write', "non-zero rc must die()")

    def test_no_silent_success_without_a_drop(self):
        """The mod must not declare success purely from having started."""
        exec_lines = strip_comment_lines(MOD_SCRIPT.read_text(encoding="utf-8"))
        self.assertIn("die", exec_lines)
        # `set -e` is NOT enough on its own: the write is in an `|| rc=$?` guard,
        # so the mod must exit explicitly. Assert the failure path calls die().
        self.assertRegex(exec_lines, r'if \[\[ "\$\{rc\}" -ne 0 \]\]; then')


class NegativeControls(unittest.TestCase):
    """A guard that cannot fail proves nothing. These mutate strings in memory."""

    def test_double_redirect_guard_fires_on_the_eugr_bug(self):
        buggy = 'echo 3 > /proc/sys/vm/drop_caches >> /tmp/drop_caches.log 2>&1'
        self.assertRegex(buggy, StructuralGuards.DROP_TARGET_WRITE,
                         "the anti-pattern must be detectable, else the guard is vacuous")

    def test_double_redirect_guard_passes_the_correct_form(self):
        correct = 'echo "${DROP_LEVEL}" > "${DROP_TARGET}" 2>> "${ERRFILE}" || rc=$?'
        self.assertNotRegex(correct, StructuralGuards.DROP_TARGET_WRITE,
                            "the shipped form must not trip the guard")

    def test_comment_stripping_removes_the_prose_that_names_the_bug(self):
        """The README/comment quotes the bug; stripping must keep the guard honest."""
        text = "# echo 3 > T >> L 2>&1  (this is the bug we fix)\necho 3 > T\n"
        self.assertNotRegex(strip_comment_lines(text), r'>\s*T\s*>>')

    def test_fail_closed_guard_would_catch_a_nowarn_version(self):
        """A version that merely logged and continued must not pass the guards."""
        lenient = 'log "drop failed"; true  # no die, no exit'
        exec_lines = strip_comment_lines(lenient)
        with self.assertRaises(AssertionError):
            # mirror the real guard assertion
            assert "rc=$?" in exec_lines, "lenient version has no rc capture"


if __name__ == "__main__":
    unittest.main()
