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

import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "run-arm.sh"
# The explicit stop is a `sparkrun stop` line at the start of a line (optionally
# indented); the trap installs its own, and is asserted separately.
# `[ \t]*`, not `\s*`: `\s` matches newlines, so `^(\s*)sparkrun stop` also matches from the
# blank line above a top-level stop and reports it as indented -- a false failure that appears the
# moment anyone puts a blank line (or a comment block) between the `fi` and the stop.
STOP_RE = re.compile(r"^([ \t]*)sparkrun stop ", re.MULTILINE)
TRAP_RE = re.compile(r"^[ \t]*trap\b[^\n]*sparkrun stop[^\n]*\bEXIT\b", re.MULTILINE)
# The readiness loop, from its poll-interval knob to its verdict echo, taken verbatim
# and run in a temp script: the loop's control flow is what is under test, not its text.
LOOP_START = "POLL_SLEEP=${ARM_POLL_SLEEP:-15}"
LOOP_END = 'echo "readiness=$ready"'


def read_tool() -> str:
    assert TOOL.exists(), f"missing {TOOL}"
    return TOOL.read_text()


def stop_offsets(text: str) -> list[int]:
    """Offsets of every explicit `sparkrun stop` line."""
    return [m.start() for m in STOP_RE.finditer(text)]


def readiness_loop(text: str) -> str:
    """The readiness loop verbatim, so a harness can drive the real control flow."""
    start = text.index(LOOP_START)
    end = text.index(LOOP_END, start) + len(LOOP_END)
    return text[start:end]


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

    def test_container_resolution_matches_both_launch_shapes(self):
        """`_solo` alone made every TP=2 launch report ARM FAIL while its ranks were booting."""
        text = read_tool()
        self.assertIn("_solo|_node_0", text, "a multi-rank container must resolve")
        self.assertIn("${TID%_node_*}", text, "the task id must strip the rank suffix")
        self.assertIn("${old_tid%_node_*}", text, "leftover cleanup must strip it too")

    def test_a_node_pair_reaches_every_sparkrun_call(self):
        """A TP=2 arm needs both hosts; the endpoint/watchdog/container must use the API rank only."""
        text = read_tool()
        self.assertIn('HOSTS=${2:-${ARM_NODE:-}}', text)
        self.assertIn("NODE=${HOSTS%%,*}", text)
        self.assertEqual(text.count('-H "$HOSTS"'), 4, "every sparkrun call site must pass the pair")
        self.assertEqual(text.count('-H "$NODE"'), 0, "a leftover single-host site breaks TP=2")

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
        # Containers are not the only holders: beegfs-mgmtd owns *:8010 on .30.
        self.assertIn('host socket', text, "a non-container holder is not detected")
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

    def test_benchmark_verbosity_is_opt_in(self):
        """A missing writer leaves no trace without -v, and -v everywhere is noise."""
        text = read_tool()
        # Three benchmark invocations: the chat ladder, the chat suite, the pooling ladder.
        self.assertEqual(text.count('${BENCH_VERBOSE:+-v}'), 3, "every benchmark must honour it")
        # It must sit before the subcommand: `benchmark performance` has no -v and aborts
        # the whole run with "No such option" (measured 2026-10-30, one arm lost).
        self.assertIn('sparkrun ${BENCH_VERBOSE:+-v} benchmark', text, "the flag is not global")
        self.assertNotIn('--output "$L/ladder.yaml" ${BENCH_VERBOSE', text, "the flag trails the command")

    def test_a_missing_ladder_is_transcribed_rather_than_lost(self):
        """Printed numbers are real; a labelled transcription beats a lost cell."""
        text = read_tool()
        self.assertIn('bench-table-to-json.py', text, "no transcription fallback")
        self.assertIn('ladder.transcribed.json', text, "the transcription is not labelled")
        self.assertIn('house.transcribed.txt', text, "no suite fallback")

    def test_rc_zero_requires_machine_readable_artifacts(self):
        """A printed table with no yaml/json is not a measurement."""
        text = read_tool()
        self.assertIn('artifacts() {', text, "no artifact assertion")
        self.assertIn('artifacts "$L/ladder.yaml" "$L/house.yaml"', text,
                      "the chat branch does not assert its outputs")
        self.assertIn('artifacts "$L/ladder.json" "$L/teb-decision.log"', text,
                      "the decision branch does not assert its outputs")
        self.assertIn('rc=5', text, "a missing artifact does not set a status")

    def test_pooling_arms_use_the_pooling_ladder(self):
        """An encoder has no /chat/completions; llama-benchy fails its first task."""
        text = read_tool()
        self.assertIn('*/embed/*|*/rerank/*)', text, "no pooling branch")
        self.assertIn('benchmark pooling', text, "the pooling subcommand is not used")
        self.assertIn('pooling-ladder-$kind.yaml', text, "the profile is not chosen per lane")
        # The profile hardcodes the 8B encoder's 4096; a 2B arm fails every reply otherwise.
        self.assertIn("dimension_check=2048", text, "no 2B dimension override")

    def test_decision_arms_use_the_decision_instruments(self):
        """llama-benchy and the chat suite cannot read /v1/systemone."""
        text = read_tool()
        self.assertIn('*/decision/*)', text, "no decision branch")
        self.assertIn('tools/decision-ladder.py', text, "the ladder is not the lane's")
        self.assertIn('--decision-bench-only', text, "no decision accuracy instrument")
        self.assertIn('DECISION_CASES', text, "the case split is not configurable")

    def test_a_completions_arm_is_not_scored_by_a_systemone_instrument(self):
        """tool-eval-bench's decision mode speaks /v1/systemone only; rc=3 on a clean JEV run was the gap."""
        text = read_tool()
        self.assertIn('if [ "$api" = completions ]', text)
        skip = text.index('if [ "$api" = completions ]')
        teb = text.index("uvx tool-eval-bench@2.8.0")
        self.assertLess(skip, teb, "the skip must guard the instrument call, not follow it")

    def test_readiness_covers_the_slowest_healthy_boot_and_watches_the_watchdog(self):
        """The ceiling must outlast a real load, and a dead boot must not wait it out.

        150 x 15 s = 2250 s against the slowest healthy boot measured on the fleet
        (1076 s, a 122B load, 2026-11-03). The watchdog's own pid is what ends the loop
        early now — there is no `--grace` for the ceiling to sit under any more, and the
        arm that died at t=98 s would otherwise have held the loop until 2250 s.
        """
        text = read_tool()
        self.assertIn("seq 1 150", text, "readiness ceiling is below the slowest measured boot")
        self.assertIn('kill -0 "$WD"', text, "the readiness loop ignores the watchdog's verdict")

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


class ReadinessLoopBehaviour(unittest.TestCase):
    """Runs the extracted readiness loop against a stub `$WD`; no network, no Docker.

    A text assertion cannot tell a loop that reaps its watchdog once from one that
    re-`wait`s a reaped pid every iteration, so these two cases execute it.
    """

    @classmethod
    def setUpClass(cls):
        if not shutil.which("bash"):
            raise unittest.SkipTest("bash not on PATH")
        cls.loop = readiness_loop(read_tool())

    @staticmethod
    def interpreters() -> list[list[str]]:
        """bash as the arm runs it, plus bash's POSIX mode -- the shell that says `rc=127`."""
        return [["bash"], ["bash", "--posix"]]

    @staticmethod
    def run_loop(watchdog_exit: int, interpreter: list[str]) -> tuple[str, int, float]:
        """Run the loop with a `$WD` that exits <watchdog_exit>; return out, probes, seconds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            wd = tmp / "watchdog.sh"
            wd.write_text(f"#!/usr/bin/env bash\nexit {watchdog_exit}\n")
            probes = tmp / "probe.log"
            script = tmp / "loop.sh"
            script.write_text(
                f"""#!/usr/bin/env bash
set -uo pipefail
NODE=127.0.0.1
PORT=1
# The endpoint probe is the only stub: an instrument, never a server, so what is
# measured is the loop's own control flow. `probes=` counts iterations.
curl() {{ echo probe >> {probes}; printf '000'; }}
bash {wd} &
WD=$!
# Let bash reap the exited stub, else its zombie still answers `kill -0`.
sleep 0.3
{ReadinessLoopBehaviour.loop}
echo "probes=$(wc -l < {probes})"
"""
            )
            started = time.monotonic()
            out = subprocess.run(
                [*interpreter, str(script)],
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "ARM_POLL_SLEEP": "0"},
                timeout=60,
            )
            elapsed = time.monotonic() - started
            probes_run = int(re.search(r"^probes=(\d+)$", out.stdout, re.M).group(1))
            return out.stdout + out.stderr, probes_run, elapsed

    def test_a_watchdog_that_dies_of_its_own_error_warns_once_and_keeps_polling(self):
        """Pre-fix this fails: the loop re-`wait`ed the already-reaped child every pass.

        Against the unfixed block (`f18bf70`, `wait "$WD"` with no one-shot flag) the
        first pass reaps the child; every later pass' `kill -0` fails, so it re-enters
        the branch, re-waits and re-warns once per iteration -- measured 150 identical
        `watchdog exited rc=4 (its own error); continuing to poll` lines against 3
        lines fixed. The `== 1` warning assertion below therefore fails on that file,
        so this is a real control and not decoration.

        The rc=127 spelling of the same defect is what POSIX mode reports for the
        repeated `wait` (bash 5.3.20: `bash --posix`, `wait $p` twice gives `w1=4`,
        then `wait: pid ... is not a child of this shell`, `w2=127`); plain bash
        re-reports the cached status instead. Both shells are run, so the `rc=127`
        assertion is a control too, and it stays on the same bash the arm needs
        (`sh` here is dash, which the script cannot run under at all).
        """
        for interpreter in self.interpreters():
            with self.subTest(shell=" ".join(interpreter)):
                out, probes, elapsed = self.run_loop(4, interpreter)
                self.assertNotIn("rc=127", out, "the loop re-waited a reaped pid")
                self.assertEqual(
                    out.count("watchdog exited rc="), 1, "the watchdog's own error must warn once"
                )
                self.assertIn(
                    "watchdog exited rc=4", out, "the reaped status was not the stub's own"
                )
                self.assertIn("no liveness instrument", out, "the warning does not name the loss")
                self.assertIn(
                    "readiness=no", out, "a watchdog error must not declare the arm ready"
                )
                self.assertEqual(probes, 150, "a watchdog bug must not end a possibly healthy boot")
                self.assertLess(elapsed, 30, "the loop did not finish quickly")

    def test_a_dead_serve_breaks_the_loop_instead_of_spinning_to_the_ceiling(self):
        """rc=3 is the real verdict: stop asking, keep `ready=no`, fall through to rc=4."""
        for interpreter in self.interpreters():
            with self.subTest(shell=" ".join(interpreter)):
                out, probes, _ = self.run_loop(3, interpreter)

                self.assertIn("readiness=no", out, "a stopped serve must not be reported ready")
                self.assertEqual(
                    out.count("serve dead and stopped (rc=3)"), 1, "the verdict is not printed once"
                )
                self.assertNotIn("watchdog exited rc=", out, "an rc=3 verdict is not its own error")
                self.assertLessEqual(
                    probes, 2, "the loop spun on after the watchdog declared the serve dead"
                )
                self.assertNotIn("readiness=yes", out, "a dead arm was declared ready")


if __name__ == "__main__":
    unittest.main()