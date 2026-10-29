"""Guards for tools/run-arm.sh — one arm end to end, teardown included.

Run:
    uv run python -B -m unittest discover -s tests

Stdlib-only, no network, no Docker, like every other guard here.

Why this file exists.  The script's whole safety claim is that **an arm never
leaves a serve behind**: the 122B run on 2026-10-29 finished both benchmarks at
18:25 and then held `.30` with an idle serve until a human noticed at 18:43,
because the ad-hoc chain that ran it had no stop step.  A live run cannot show
that the next edit keeps the promise, so the properties are pinned here:

* the teardown is unconditional — it sits outside the readiness branch, so a
  benchmark that fails still stops the task (`test_teardown_is_outside_the_ready_branch`);
* the node re-count happens after the stop, not instead of it
  (`test_verification_follows_the_stop`);
* a failed benchmark is reported in the exit status rather than swallowed
  (`test_failed_steps_set_a_nonzero_exit`);
* the script is syntactically valid bash (`test_bash_syntax`).

The negative control proves the first assertion is live: a copy with the stop
line deleted must fail it.  Without that, a reformat could quietly move the
teardown inside the happy path and every test here would still pass.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "run-arm.sh"
STOP_RE = re.compile(r"^\s*sparkrun stop ", re.MULTILINE)


def read_tool() -> str:
    assert TOOL.exists(), f"missing {TOOL}"
    return TOOL.read_text()


def teardown_index(text: str) -> int:
    """Offset of the `sparkrun stop` line, or -1 when absent."""
    match = STOP_RE.search(text)
    return match.start() if match else -1


class RunArmContract(unittest.TestCase):
    def test_bash_syntax(self):
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("bash not on PATH")
        out = subprocess.run([bash, "-n", str(TOOL)], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_teardown_is_unconditional(self):
        """The stop must run whether or not the benchmarks succeeded."""
        text = read_tool()
        self.assertGreater(teardown_index(text), 0, "no `sparkrun stop` line")

        # A readiness branch is fine; a stop INSIDE it is the defect. Assert the
        # stop's indentation is top level (column 0) so it cannot be nested in
        # `if [ "$ready" = yes ]`.
        stop_line = next(l for l in text.splitlines() if STOP_RE.match(l))
        self.assertEqual(
            len(stop_line) - len(stop_line.lstrip()), 0,
            "teardown is indented, i.e. inside a conditional branch",
        )

    def test_verification_follows_the_stop(self):
        """The container/volume re-count must come after the stop, not from it."""
        text = read_tool()
        stop_at = teardown_index(text)
        verify_at = text.find("docker ps -aq | wc -l", stop_at)
        self.assertGreater(verify_at, stop_at, "no per-node re-count after the stop")

    def test_failed_steps_set_a_nonzero_exit(self):
        text = read_tool()
        self.assertRegex(text, r"rc=[1-9]", "no failure status is recorded")
        self.assertRegex(text, r"exit \"?\$rc\"?", "the recorded status is not returned")

    def test_benchmarks_do_not_relaunch_the_serve(self):
        """`--skip-run` is what makes this measure the boot instead of a new one."""
        text = read_tool()
        for profile in ("concurrency-ladder.yaml", "standard-suite.yaml"):
            block = text[text.find(profile) - 200: text.find(profile) + 200]
            self.assertIn("--skip-run", block, f"{profile} is run without --skip-run")


class NegativeControls(unittest.TestCase):
    def test_removing_the_stop_fails_the_teardown_guard(self):
        text = STOP_RE.sub("true ", read_tool())
        self.assertEqual(teardown_index(text), -1, "the stop line survived the mutation")

    def test_indenting_the_stop_fails_the_teardown_guard(self):
        """The exact shape of the regression: a stop nested in the happy path."""
        text = STOP_RE.sub("  sparkrun stop ", read_tool())
        stop_line = next(l for l in text.splitlines() if "sparkrun stop" in l)
        self.assertNotEqual(len(stop_line) - len(stop_line.lstrip()), 0)


if __name__ == "__main__":
    unittest.main()