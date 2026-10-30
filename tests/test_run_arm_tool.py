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
* the script cannot be killed and leave the task running: an `EXIT INT TERM`
  trap is installed as soon as the task id is known
  (`test_exit_trap_covers_a_killed_script`);
* the node re-count happens after the stop, not instead of it
  (`test_verification_follows_the_stop`);
* a failed benchmark is reported in the exit status rather than swallowed
  (`test_failed_steps_set_a_nonzero_exit`);
* the script is syntactically valid bash (`test_bash_syntax`).

Every assertion here needs its negative control: a copy with the stop line
deleted, one with it indented, and one with the trap removed must each fail the
matching guard.  Without them, a reformat could move the teardown inside the
happy path and every test here would still pass.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "run-arm.sh"
# The explicit stop is a `sparkrun stop` line at the start of a line (optionally
# indented); the trap installs its own, and is asserted separately.
STOP_RE = re.compile(r"^(\s*)sparkrun stop ", re.MULTILINE)
TRAP_RE = re.compile(r"^\s*trap\b[^\n]*sparkrun stop[^\n]*\bEXIT\b", re.MULTILINE)


def read_tool() -> str:
    assert TOOL.exists(), f"missing {TOOL}"
    return TOOL.read_text()


def stop_offsets(text: str) -> list[int]:
    """Offsets of every explicit `sparkrun stop` line."""
    return [m.start() for m in STOP_RE.finditer(text)]


class RunArmContract(unittest.TestCase):
    def test_bash_syntax(self):
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("bash not on PATH")
        out = subprocess.run([bash, "-n", str(TOOL)], capture_output=True, text=True, check=False)
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_teardown_is_unconditional(self):
        """The stop must run whether or not the benchmarks succeeded."""
        text = read_tool()
        offsets = stop_offsets(text)
        self.assertTrue(offsets, "no `sparkrun stop` line")

        # A readiness branch is fine; a stop INSIDE it is the defect. Assert at
        # least one stop sits at top level (column 0) so it cannot be nested in
        # `if [ "$ready" = yes ]`.
        top_level = [m for m in STOP_RE.finditer(text) if m.group(1) == ""]
        self.assertTrue(
            top_level,
            "every `sparkrun stop` is indented, i.e. inside a conditional branch",
        )

    def test_exit_trap_covers_a_killed_script(self):
        """A killed script must still stop the task it booted."""
        text = read_tool()
        trap = TRAP_RE.search(text)
        assert trap is not None, "no `trap ... sparkrun stop ... EXIT` line"
        tid_at = text.find("TID=${N#sparkrun_}")
        self.assertGreater(tid_at, 0, "task id is not parsed where expected")
        self.assertGreater(trap.start(), tid_at, "the trap is installed before $TID is known")

    def test_verification_follows_the_stop(self):
        """The container/volume re-count must come after the stop, not from it."""
        text = read_tool()
        stop_at = stop_offsets(text)[-1]
        verify_at = text.find("docker ps -aq | wc -l", stop_at)
        self.assertGreater(verify_at, stop_at, "no per-node re-count after the stop")

    def test_refused_launch_fails_fast(self):
        """A launch that exits at once must not sit in the container-wait loop."""
        text = read_tool()
        self.assertRegex(text, r"LAUNCH=\$!", "the launcher pid is not captured")
        self.assertIn('kill -0 "$LAUNCH"', text, "the wait loop does not poll the launcher")
        self.assertRegex(text, r"exit 5", "a refused launch has no distinct exit status")

    def test_serve_port_comes_from_the_recipe(self):
        """Probing 8000 on an 8020 arm looks like a boot that never readies."""
        text = read_tool()
        self.assertIn('PORT=$(sed -n', text, "the port is not parsed from the recipe")
        self.assertIn('PORT=${PORT:-8000}', text, "no default when the recipe omits a port")
        self.assertNotIn(':8000/v1/models', text, "a hardcoded 8000 endpoint survived")
        self.assertIn('"http://$NODE:$PORT/v1/models"', text, "the probe does not use $PORT")

    def test_a_dead_owners_claim_is_released_before_launching(self):
        """A dead claim refuses every launch; the recovery is documented and safe."""
        text = read_tool()
        self.assertIn('sparkrun daemon resources reconcile', text, "no claim reconcile")
        self.assertIn('not r.get("alive", True)', text, "live claims are not excluded")

    def test_a_foreign_container_holding_the_port_refuses_the_launch(self):
        """A dead peer's container on the port makes this arm measure nothing."""
        text = read_tool()
        self.assertIn('is held by $BLOCKER', text, "no port-conflict refusal")
        self.assertIn('exit 7', text, "the refusal does not stop the run")
        self.assertNotIn('docker rm -f $BLOCKER', text, "a foreign container is removed")

    def test_the_leftover_gate_is_per_arm_not_per_node(self):
        """A peer arm on the other free node is not this arm's leftover."""
        text = read_tool()
        self.assertIn("gate on this arm's container", text.lower(), "no note of the scoping")
        self.assertNotIn('case "$left" in', text, "a node-wide count still gates the run")
        self.assertIn('this arm\'s container is still running', text, "the gate does not name the container")

    def test_a_surviving_container_is_removed_and_fails_the_run(self):
        """`sparkrun stop` can be refused; the node must not stay held."""
        text = read_tool()
        self.assertIn('container survived sparkrun stop', text, "no stop retry")
        self.assertIn('docker rm -f $N', text, "no by-name removal of this launch's container")
        self.assertIn('rc=6', text, "leftover state does not fail the run")
        self.assertIn("this arm's container is still running", text, "no leftover report")

    def test_a_leftover_container_of_the_same_recipe_is_cleared_first(self):
        """Two containers of one recipe collide on the port; the old one answers."""
        text = read_tool()
        self.assertIn('sparkrun.recipe', text, "the leftover probe does not use the recipe label")
        self.assertIn('stopping leftover container', text, "no leftover stop")
        self.assertIn('LEFTOVER=', text, "no leftover probe")

    def test_an_existing_receipt_is_moved_aside(self):
        """A relaunch overwrote a failed instrument's receipt with a truncated one."""
        text = read_tool()
        self.assertIn('.prev-$(date +%H%M%S)', text, "no receipt copy-aside")

    def test_rc_zero_requires_machine_readable_artifacts(self):
        """A printed table with no yaml/json is not a measurement."""
        text = read_tool()
        self.assertIn('artifacts() {', text, "no artifact assertion")
        self.assertIn('artifacts "$L/ladder.yaml" "$L/house.yaml"', text,
                      "the chat branch does not assert its outputs")
        self.assertIn('artifacts "$L/ladder.json" "$L/teb-decision.log"', text,
                      "the decision branch does not assert its outputs")
        self.assertIn('rc=5', text, "a missing artifact does not set a status")

    def test_decision_arms_use_the_decision_instruments(self):
        """llama-benchy and the chat suite cannot read /v1/systemone."""
        text = read_tool()
        self.assertIn('*/decision/*)', text, "no decision branch")
        self.assertIn('tools/decision-ladder.py', text, "the ladder is not the lane's")
        self.assertIn('--decision-bench-only', text, "no decision accuracy instrument")
        self.assertIn('DECISION_CASES', text, "the case split is not configurable")

    def test_readiness_outlasts_the_watchdog_grace(self):
        """A 1350 s ceiling under a 1800 s grace stops a serve still loading."""
        text = read_tool()
        self.assertIn('seq 1 150', text, "readiness ceiling is below the watchdog's grace")

    def test_failed_steps_set_a_nonzero_exit(self):
        text = read_tool()
        self.assertRegex(text, r"rc=[1-9]", "no failure status is recorded")
        self.assertRegex(text, r"exit \"\$rc\"", "the recorded status is not returned")

    def test_benchmarks_do_not_relaunch_the_serve(self):
        """`--skip-run` is what makes this measure the boot instead of a new one."""
        text = read_tool()
        for profile in ("concurrency-ladder.yaml", "standard-suite.yaml"):
            at = text.find(profile)
            self.assertGreater(at, 0, f"{profile} not invoked")
            self.assertIn("--skip-run", text[at - 250: at + 250], f"{profile} without --skip-run")


class NegativeControls(unittest.TestCase):
    def test_removing_the_stop_fails_the_teardown_guard(self):
        text = STOP_RE.sub(r"\1true ", read_tool())
        self.assertEqual(stop_offsets(text), [], "the stop line survived the mutation")

    def test_indenting_every_stop_fails_the_teardown_guard(self):
        """The exact shape of the regression: a stop nested in the happy path."""
        text = STOP_RE.sub(lambda m: "  sparkrun stop ", read_tool())
        top_level = [m for m in STOP_RE.finditer(text) if m.group(1) == ""]
        self.assertEqual(top_level, [], "an unindented stop survived the mutation")

    def test_dropping_the_leftover_probe_fails_its_guard(self):
        text = read_tool().replace('stopping leftover container', 'starting')
        self.assertNotIn('stopping leftover container', text)

    def test_sending_a_decision_arm_to_the_chat_suite_fails_its_guard(self):
        text = read_tool().replace('*/decision/*)', '*/nothing/*)')
        self.assertNotIn('*/decision/*)', text)

    def test_a_hardcoded_port_fails_the_port_guard(self):
        text = read_tool().replace('"http://$NODE:$PORT/v1/models"', '"http://$NODE:8000/v1/models"')
        self.assertIn(':8000/v1/models', text)

    def test_removing_the_fail_fast_fails_its_guard(self):
        text = read_tool().replace('kill -0 "$LAUNCH"', 'true')
        self.assertNotIn('kill -0 "$LAUNCH"', text)

    def test_removing_the_trap_fails_the_trap_guard(self):
        text = TRAP_RE.sub("", read_tool())
        self.assertIsNone(TRAP_RE.search(text), "the trap line survived the mutation")


if __name__ == "__main__":
    unittest.main()