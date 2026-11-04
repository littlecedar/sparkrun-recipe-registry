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
* a pooling arm's receipt carries a machine-readable `suite: n/a` beside its ladder, and
  carries no suite marker at all when its ladder failed
  (`PoolingReceipt`, which executes the branch against a stub `sparkrun`);
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


# The teardown, from the stop call to its verdict line: stop, leftover removal, census, gate.
TEARDOWN_START = 'sparkrun stop "$TID" 2>&1 | tail -1'
TEARDOWN_END = 'echo "ARM DONE $NAME rc=$rc"'


def teardown_region(text: str) -> str:
    """The teardown slice verbatim: what an arm does after its measurement is recorded."""
    start = text.index(TEARDOWN_START)
    end = text.index(TEARDOWN_END, start) + len(TEARDOWN_END)
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


# ---------------------------------------------------------------------------
# A pooling arm's receipt: the files a consumer may read, and the ones it must not.
# ---------------------------------------------------------------------------

# The arm body, not its `)` label: slices are executed, so what is under test is the
# file's own control flow rather than a restatement of it in Python.
POOLING_ARM_AT = 'kind=embed; case "$RECIPE" in */rerank/*) kind=rerank ;; esac'
CASE_ARM_END = "\n      ;;\n"
POOLING_REASON = "the chat suite cannot address /v1/embeddings or /v1/rerank"
# A stub, not a server: it writes `--output` the way sparkrun's exporter does (primary yaml
# plus the json sidecar) and exits 2 for the failed-ladder case, writing nothing.
SPARKRUN_STUB = """#!/usr/bin/env bash
out=
while [ $# -gt 0 ]; do
  case "$1" in
    --output) out=$2; shift 2 ;;
    *) shift ;;
  esac
done
[ -n "$out" ] || exit 0
printf 'framework: pooling-bench\\nruns: []\\n' > "$out"
printf '{"runs": []}\\n' > "${out%.yaml}.json"
"""
FAILED_LADDER_STUB = "#!/usr/bin/env bash\nexit 2\n"


def case_arm(text: str, start_marker: str) -> str:
    """One `case` arm body, without its `)` label and `;;` terminator."""
    at = text.index(start_marker)
    start = text.rindex("\n", 0, at) + 1
    return text[start : text.index(CASE_ARM_END, at)] + "\n"


def chat_arm(text: str) -> str:
    """The default arm — the one the pooling branch must not disturb."""
    at = text.index(POOLING_ARM_AT)
    start = text.index("\n    *)\n", at) + len("\n    *)\n")
    return text[start : text.index(CASE_ARM_END, start)] + "\n"


def artifacts_function(text: str) -> str:
    start = text.index("artifacts() {")
    return text[start : text.index("\n}\n", start) + 3]


# ---------------------------------------------------------------------------
# A decision arm's receipt: a ladder plus an accuracy log, and now a marker saying so.
# ---------------------------------------------------------------------------

DECISION_ARM_AT = "api=${ARM_LADDER_API:-systemone}"
# Stubs, not tools: `decision-ladder.py` writes its `--json` artefact, `tool-eval-bench` prints
# a score the marker must name the location of rather than copy.
LADDER_STUB = """#!/usr/bin/env bash
out=
while [ $# -gt 0 ]; do
  case "$1" in
    --json) out=$2; shift 2 ;;
    *) shift ;;
  esac
done
[ -n "$out" ] || exit 0
printf '{"runs": []}\\n' > "$out"
"""
FAILED_LADDER_STUB_JSON = "#!/usr/bin/env bash\nexit 2\n"
ACCURACY_STUB = "#!/usr/bin/env bash\nprintf 'DECISION ACCURACY 0.42\\n'\n"


def decision_arm(text: str) -> str:
    """The decision arm body: ladder, accuracy instrument, receipt artefacts."""
    return case_arm(text, DECISION_ARM_AT)


def run_decision_arm(
    arm: str, ladder_ok: bool = True, api: str = ""
) -> tuple[dict[str, str], str]:
    """Execute *arm* in a temp receipt; return its file map and its output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        receipt = tmp / "receipt"
        receipt.mkdir()
        bins = tmp / "bin"
        bins.mkdir()
        for name, body in (
            ("python3", LADDER_STUB if ladder_ok else FAILED_LADDER_STUB_JSON),
            ("uvx", ACCURACY_STUB),
        ):
            stub = bins / name
            stub.write_text(body)
            stub.chmod(0o755)
        script = tmp / "arm.sh"
        script.write_text(
            "#!/usr/bin/env bash\nset -uo pipefail\n"
            f"L={receipt}\n"
            "RECIPE=recipes/decision/jev-9b-decision-vllm.yaml\n"
            "NAME=decision-arm\nNODE=head.test\nPORT=8020\nSERVED=jev-9b\n"
            "DECISION_CASES=/dev/null\n"
            "BENCH_VERBOSE=\n"
            "rc=0\n" + artifacts_function(read_tool()) + "\n" + arm + 'echo "rc=$rc"\n'
        )
        env = {**os.environ, "PATH": f"{bins}:{os.environ['PATH']}"}
        if api:
            env["ARM_LADDER_API"] = api
        out = subprocess.run(
            ["bash", str(script)],
            capture_output=True,
            text=True,
            check=False,
            env=env,
            timeout=120,
        )
        files = {path.name: path.read_text(errors="replace") for path in sorted(receipt.iterdir())}
    return files, out.stdout + out.stderr


def run_case_arm(arm: str, ladder_ok: bool = True) -> tuple[dict[str, str], str]:
    """Execute *arm* in a temp receipt and return its file name -> text map, and its output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        receipt = tmp / "receipt"
        receipt.mkdir()
        stub = tmp / "sparkrun"
        stub.write_text(SPARKRUN_STUB if ladder_ok else FAILED_LADDER_STUB)
        stub.chmod(0o755)
        script = tmp / "arm.sh"
        script.write_text(
            "#!/usr/bin/env bash\nset -uo pipefail\n"
            f"L={receipt}\n"
            "RECIPE=recipes/embed/qwen3-vl-embedding-8b-awq-4bit-vllm-b12x.yaml\n"
            "NAME=qwen3-vl-embedding-8b-awq-4bit-vllm-b12x\n"
            "HOSTS=127.0.0.1\n"
            "BENCH_VERBOSE=\n"
            "rc=0\n" + artifacts_function(read_tool()) + "\n" + arm + 'echo "rc=$rc"\n'
        )
        out = subprocess.run(
            ["bash", str(script)],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "PATH": f"{tmp}:{os.environ['PATH']}"},
            timeout=120,
        )
        if out.returncode != 0:
            raise AssertionError(f"arm harness exited {out.returncode}: {out.stdout}{out.stderr}")
        files = {path.name: path.read_text(errors="replace") for path in sorted(receipt.iterdir())}
    return files, out.stdout + out.stderr


def pooling_contract_errors(receipt: dict[str, str]) -> list[str]:
    """Every way a pooling receipt fails the contract a consumer reads it by."""
    errors = []
    if "ladder.yaml" not in receipt:
        errors.append("ladder.yaml missing")
    if "ladder.csv" in receipt:
        errors.append("ladder.csv was manufactured; pooling-bench exports no csv")
    for name in ("house.json", "house.csv"):
        if name in receipt:
            errors.append(f"{name} claims a suite this arm cannot run")
    house = receipt.get("house.yaml")
    if house is None:
        errors.append(
            "house.yaml missing; a driver whose arm-finished predicate wants a house artefact re-runs it"
        )
    else:
        for needle in ("suite: n/a", POOLING_REASON, "kind: embed", "ladder: ok"):
            if needle not in house:
                errors.append(f"house.yaml does not state {needle!r}")
    return errors


class BashArmHarness(unittest.TestCase):
    """A TestCase with bash, and nothing else: `run_case_arm` execs the script's own slice."""

    def setUp(self):
        if not shutil.which("bash"):
            self.skipTest("bash not on PATH")


class PoolingReceipt(BashArmHarness):
    """A pooling arm's receipt, executed: no sparkrun, no serve, no GPU.

    The measured pre-fix receipt — `git show HEAD:tools/run-arm.sh` before this fix,
    three rc=0 arms on 2026-11-04 (`qwen3-vl-embedding-8b-awq-4bit-vllm-b12x`,
    `qwen3-vl-reranker-2b-vllm-b12x`, `qwen3-vl-reranker-8b-vllm-b12x`) — held
    `ladder.yaml`, `ladder.json`, `ladder.log` and the `house.log` stub, and no
    `house.yaml`/`house.json`/`house.csv`. A driver whose "arm finished" predicate wants a
    ladder artefact *and* a house one therefore read three finished arms as unfinished and
    re-booted them. Run against that same text here, `test_a_completed_pooling_arm_states_
    its_own_gap` fails on `house.yaml missing; a driver whose arm-finished predicate wants a
    house artefact re-runs it`; against the arm with its `[ -s "$L/ladder.yaml" ]` guard
    weakened to `true`, `test_a_failed_ladder_leaves_no_suite_marker` fails because a
    `house.yaml` saying `ladder: ok` is written for an arm whose ladder never ran.
    """

    def test_a_completed_pooling_arm_states_its_own_gap(self):
        """Both sides of the driver's predicate are present, and nothing is invented."""
        receipt, out = run_case_arm(case_arm(read_tool(), POOLING_ARM_AT))
        self.assertEqual(pooling_contract_errors(receipt), [], f"receipt={sorted(receipt)} output={out}")
        self.assertIn("suite: n/a (pooling arm", receipt.get("house.log", ""), "the human line is gone")

    def test_a_failed_ladder_leaves_no_suite_marker(self):
        """The ladder's `rc=2` does not exit, so presence must not mean "finished"."""
        receipt, out = run_case_arm(case_arm(read_tool(), POOLING_ARM_AT), ladder_ok=False)
        self.assertIn("pooling ladder failed", out, "the ladder failure was swallowed")
        self.assertNotIn("ladder.yaml", receipt, "the stub wrote a ladder artefact it should not")
        for name in ("house.yaml", "house.json", "house.csv"):
            self.assertNotIn(name, receipt, f"{name} would read as a finished arm whose ladder died")
        self.assertIn("rc=5", out, "the missing ladder artefact set no status")

    def test_the_chat_arm_is_unchanged(self):
        """The pooling marker must not leak into the arm that does run the suite."""
        receipt, out = run_case_arm(chat_arm(read_tool()))
        self.assertEqual(out.strip().splitlines()[-1], "rc=0", out)
        self.assertIn("house.yaml", receipt, "the chat arm's own suite artefact is missing")
        self.assertNotIn("suite: n/a", receipt.get("house.yaml", ""), "a pooling marker reached the chat arm")


class PoolingReceiptNegativeControls(BashArmHarness):
    """The same contract, against the two receipts that caused the defect."""

    def test_the_pre_fix_receipt_fails_the_contract(self):
        """The measured 2026-11-04 shape, rebuilt from the fix minus its marker block."""
        arm = case_arm(read_tool(), POOLING_ARM_AT)
        # From the marker's first comment line to its closing `fi`: the arm as it stood
        # before this fix, nothing else removed.
        start = arm.index("      # A campaign driver calls an arm finished")
        end = arm.index("\n      fi\n", start) + len("\n      fi\n")
        block = arm[start:end]
        self.assertIn('> "$L/house.yaml"', block, "the marker block was not found; the control is vacuous")
        pre_fix = arm.replace(block, "")
        self.assertNotIn("house.yaml", pre_fix, "the pre-fix arm still writes a marker")

        files, _ = run_case_arm(pre_fix)
        self.assertEqual(sorted(files), ["house.log", "ladder.json", "ladder.log", "ladder.yaml"])
        errors = pooling_contract_errors(files)
        self.assertTrue(errors, "the pre-fix receipt passed the contract")
        self.assertIn("house.yaml missing", " ".join(errors))

    def test_an_unconditional_marker_fails_the_failed_ladder_guard(self):
        """The defect the ladder guard prevents: a marker on an arm that measured nothing."""
        arm = case_arm(read_tool(), POOLING_ARM_AT).replace(
            'if [ -s "$L/ladder.yaml" ]; then', "if true; then"
        )
        receipt, out = run_case_arm(arm, ladder_ok=False)
        self.assertIn("pooling ladder failed", out)
        self.assertIn(
            "house.yaml", receipt, "the weakened guard wrote no marker, so the control proves nothing"
        )
        self.assertIn("ladder: ok", receipt["house.yaml"], "the marker claims a ladder that never ran")


class TeardownReapsEveryRank(BashArmHarness):
    """A TP=2 stop that misses rank 1 must not end `ARM DONE rc=0`.

    Measured 2026-11-04 (`qwen3.8-flash-next-uncensored-nvfp4-sglang`): `sparkrun stop` left
    rank 1 running on the second host — `docker ps` still listed it 39 s after the stop and
    4 s after this script printed ARM DONE, and it was gone ~100 s later. The script resolved
    one container name (`docker ps | grep -m1 -E '_solo|_node_0'`) and its hygiene block and
    its leak gate both looked at `$NODE`/`$N` only, so there was no rank-1 path at all and
    the arm reported rc=0 while it leaked.

    The teardown slice is extracted verbatim and executed with `ssh`/`sparkrun` stubbed, so
    this exercises the real gate rather than restating it. Removal must also be anchored on
    the container-naming grammar (`sparkrun_${TID}_solo`, `sparkrun_${TID}_node_*`), because
    `docker ps --filter name=$TID` is a substring match and another task's id can contain
    ours — that is the near-miss case below, and it is the one that matters: a fix that
    removes anything it sees is worse than the bug.

    Against the pre-fix file (`git show 0c8e50b:tools/run-arm.sh`) the rank-1 assertions fail:
    `test_a_rank_1_leftover_on_the_second_host_is_removed` and
    `test_a_survivor_on_the_second_host_fails_the_arm` both end `ARM DONE teardown-arm rc=0`
    with `sparkrun_abc123_node_1` still listed on rank1.test — the leak tonight, reproduced.
    """

    HOSTS = ("head.test", "rank1.test")
    TID = "abc123"

    # A stub node, not a fleet: `ssh` answers from per-host files, so the recorded set of
    # removals is the assertion. Braces here are shell, not f-string — this template is
    # concatenated with the extracted slice, never formatted.
    HARNESS = """#!/usr/bin/env bash
set -uo pipefail
TID=abc123
NAME=teardown-arm
NODE=head.test
HOSTS=head.test,rank1.test
N=sparkrun_abc123_node_0
WD=
rc=0
sleep() { :; }
sparkrun() { echo "stopped $2"; }
ssh() {
  local host="${@: -2:1}" cmd="${@: -1}"
  host="${host#red@}"
  if grep -qxF "$host" "$FAIL_HOSTS" 2>/dev/null; then return 255; fi
  case "$cmd" in
    *"docker rm -f "*)
      local c="${cmd##*docker rm -f }"
      if grep -qxF "$c" "$FAIL_REMOVE" 2>/dev/null; then
        echo "removal refused for $c" >&2
        return 1
      fi
      echo "$c on $host" >> "$REMOVED"
      grep -vxF "$c" "$STATE/$host" > "$STATE/$host.new" 2>/dev/null
      mv "$STATE/$host.new" "$STATE/$host" 2>/dev/null
      return 0 ;;
    *--filter*|*"docker ps --format"*) cat "$STATE/$host" 2>/dev/null; return 0 ;;
    *) return 0 ;;
  esac
}
"""

    def run_teardown(
        self,
        state: dict[str, list[str]],
        fail_remove: tuple[str, ...] = (),
        fail_hosts: tuple[str, ...] = (),
    ) -> tuple[str, list[str]]:
        """Run the real teardown slice against stub nodes; return its output and removals."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            state_dir = tmp / "state"
            state_dir.mkdir()
            for host in self.HOSTS:
                names = state.get(host, [])
                (state_dir / host).write_text("".join(f"{n}\n" for n in names))
            removed = tmp / "removed.log"
            removed.write_text("")
            fail_remove_path = tmp / "fail-remove"
            fail_remove_path.write_text("".join(f"{n}\n" for n in fail_remove))
            fail_hosts_path = tmp / "fail-hosts"
            fail_hosts_path.write_text("".join(f"{h}\n" for h in fail_hosts))
            script = tmp / "teardown.sh"
            script.write_text(self.HARNESS + teardown_region(read_tool()) + "\n")
            out = subprocess.run(
                ["bash", str(script)],
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "STATE": str(state_dir),
                    "REMOVED": str(removed),
                    "FAIL_REMOVE": str(fail_remove_path),
                    "FAIL_HOSTS": str(fail_hosts_path),
                },
                timeout=60,
            )
            return out.stdout + out.stderr, removed.read_text().split()

    def test_a_rank_1_leftover_on_the_second_host_is_removed(self):
        name = f"sparkrun_{self.TID}_node_1"
        out, removed = self.run_teardown({
            self.HOSTS[0]: [f"sparkrun_{self.TID}_node_0"],
            self.HOSTS[1]: [name],
        })

        self.assertIn(f"removing leftover {name} on rank1.test", out, "rank 1 was never reaped")
        self.assertIn(f"{name} on rank1.test", " ".join(removed), "no removal was recorded")
        self.assertIn("ARM DONE teardown-arm rc=0", out, "both ranks gone, so the arm is clean")

    def test_a_foreign_container_whose_name_contains_the_task_id_is_left_alone(self):
        foreign = f"sparkrun_{self.TID}ff_node_1"  # another task id with ours as a prefix
        out, removed = self.run_teardown({self.HOSTS[0]: [], self.HOSTS[1]: [foreign]})

        self.assertNotIn(foreign, removed, "a substring match removed a foreign container")
        self.assertIn(f"leaving {foreign} on rank1.test", out, "the sweep did not say what it spared")
        self.assertIn("ARM DONE teardown-arm rc=0", out, "a foreign container is not this arm's leak")

    def test_a_survivor_on_the_second_host_fails_the_arm(self):
        name = f"sparkrun_{self.TID}_node_1"
        out, _ = self.run_teardown(
            {self.HOSTS[0]: [], self.HOSTS[1]: [name]}, fail_remove=(name,)
        )

        self.assertIn(
            f"this arm's container is still running after teardown: {name} on rank1.test",
            out,
            "the leak went unreported, which is how tonight's rank 1 survived into rc=0",
        )
        self.assertIn("ARM DONE teardown-arm rc=6", out, "a surviving rank did not fail the arm")
        self.assertIn(f"could not remove {name} on rank1.test", out, "a failed removal was silent")

    def test_a_failed_ssh_prints_and_continues(self):
        """Non-fatal by construction: nothing to remove is normal, an unreachable host is not fatal."""
        out, _ = self.run_teardown(
            {self.HOSTS[0]: [], self.HOSTS[1]: []}, fail_hosts=(self.HOSTS[1],)
        )

        self.assertIn("cannot list containers on rank1.test", out, "the sweep failed silently")
        self.assertIn("cannot verify containers on rank1.test", out, "the gate failed silently")
        self.assertIn("ARM DONE teardown-arm rc=0", out, "an unreachable host failed a measured arm")


class DecisionReceipt(BashArmHarness):
    """A decision arm's receipt states its own gap and never invents a score.

    Measured 2026-11-04: the lane wrote `ladder.json` + `teb-decision.log` and no `house.*`, so
    a driver whose arm-finished predicate wants a house artefact called four finished arms
    incomplete (`clef-flash-decision-sglang` rc=0, `jev-9b-decision-vllm`,
    `jev-27b-decision-vllm`, `zz-jev-9b-decision-coloc-vllm` rc=3) and re-booted them.

    The marker mirrors the pooling one — `suite: n/a`, a reason, `ladder: ok` — and then the
    accuracy half: the instrument's name, the file its output lives in, and whether it was taken
    at all, because `tool-eval-bench --decision-bench-only` speaks `/v1/systemone` only and a
    `/v1/completions` arm legitimately has no score. The score is never copied into the marker:
    a number there can drift from the log that measured it.

    The extraction runs the arm's real text against stub `decision-ladder.py` and
    `tool-eval-bench`, so these are behavioural; the failed-ladder control is the same mutation
    the pooling marker needed, `if [ -s "$L/ladder.json" ]` weakened to `if true`.
    """

    def test_a_completed_decision_arm_names_its_instrument_and_log(self):
        """Both sides of the predicate are present, and the score stays in its own file."""
        files, out = run_decision_arm(decision_arm(read_tool()))
        house = files.get("house.yaml", "")

        self.assertTrue(house, f"no house.yaml; receipt={sorted(files)} output={out}")
        self.assertIn("suite: n/a", house)
        self.assertIn("the chat suite cannot address /v1/systemone", house)
        self.assertIn("ladder: ok", house)
        self.assertIn("accuracy: tool-eval-bench --decision-bench-only", house)
        self.assertIn("accuracy_log: teb-decision.log", house)
        self.assertIn("accuracy_status: taken", house)
        self.assertNotIn("0.42", house, "the marker copied a score instead of naming where it lives")
        self.assertIn("DECISION ACCURACY 0.42", files.get("teb-decision.log", ""), out)
        self.assertEqual(out.strip().splitlines()[-1], "rc=0", out)

    def test_a_failed_ladder_leaves_no_marker(self):
        """The ladder's `rc=2` does not exit, so a marker on presence would read as finished."""
        files, out = run_decision_arm(decision_arm(read_tool()), ladder_ok=False)

        self.assertIn("ladder failed", out, "the ladder failure was swallowed")
        for name in ("house.yaml", "house.json", "house.csv"):
            self.assertNotIn(name, files, f"{name} would read as a finished arm whose ladder died")
        self.assertIn("rc=5", out, "the missing ladder artefact set no status")


    def test_a_completions_arm_says_the_instrument_could_not_address_it(self):
        """No score is legitimate here, and the marker must not read as a scored arm."""
        files, out = run_decision_arm(decision_arm(read_tool()), api="completions")
        house = files.get("house.yaml", "")

        self.assertIn("accuracy_status: not-taken", house, "a /v1/completions arm claims a score")
        self.assertIn("/v1/systemone", house, "the marker does not name what the instrument needs")
        self.assertNotIn("the score is in", house, "not-taken must not also say the score is there")
        self.assertIn("no score is taken", files.get("teb-decision.log", ""), out)
        self.assertIn("ladder: ok", house, "the ladder did run, whatever the accuracy half says")

    def test_an_unconditional_marker_fails_the_failed_ladder_guard(self):
        """The defect the guard prevents: a marker on an arm whose ladder never measured."""
        arm = decision_arm(read_tool())
        self.assertIn('if [ -s "$L/ladder.json" ]; then', arm, "the guard was not found; control vacuous")
        weakened = arm.replace('if [ -s "$L/ladder.json" ]; then', "if true; then")

        files, out = run_decision_arm(weakened, ladder_ok=False)
        self.assertIn("ladder failed", out)
        self.assertIn("house.yaml", files, "the weakened guard wrote no marker, so the control proves nothing")
        self.assertIn("ladder: ok", files["house.yaml"], "the marker claims a ladder that never ran")


if __name__ == "__main__":
    unittest.main()