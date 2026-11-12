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
* the readiness ceiling is a knob, not a literal: `ARM_READY_TIMEOUT` (default 2250 s) drives
  the poll count with `ARM_POLL_SLEEP`, the unset path is bounded, and the rc=4 line names
  the effective ceiling (`ReadinessCeiling`);
* every booting row writes `image.txt`/`ARM_IMAGE_ID` from the container's own config sha,
  client or no client, and a missing id fails visibly instead of writing `unknown`
  (`ImageCell`).

Every assertion here needs its negative control: a copy with the stop line
deleted, one with it indented, and one with the trap removed must each fail the
matching guard.  Without them, a reformat could move the teardown inside the
happy path and every test here would still pass.
"""

from __future__ import annotations

import json
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
LAUNCHER_BLOCK_START = "  # The launcher is the only instrument that OWNS the containers"
LAUNCHER_BLOCK_END = "  # The guard is the window's stop rule"


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


def launcher_block(text: str) -> str:
    """The loop's launcher poll verbatim, so a control can remove exactly that block."""
    start = text.index(LAUNCHER_BLOCK_START)
    return text[start : text.index(LAUNCHER_BLOCK_END, start)]


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
        """A killed script must still stop the task it booted — and the launcher it left."""
        text = read_tool()
        trap = TRAP_RE.search(text)
        assert trap is not None, "no `trap ... sparkrun stop ... EXIT` line"
        # Installed after the launch and before the appearance loop, because an abandoned
        # launch must not outlive the executor; `$TID` is empty until a container resolves.
        self.assertLess(text.index("\nlaunch_arm\n"), trap.start(),
                        "the trap runs before there is a launcher to reap")
        self.assertIn('[ -n "${TID:-}" ] && sparkrun stop "$TID"', text,
                      "the trap stops a task it may not have")
        self.assertIn('[ -n "${LAUNCH:-}" ] && kill "$LAUNCH"', text,
                      "the trap never kills the launcher")

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
        self.assertEqual(text.count('-H "$HOSTS"'), 5, "every sparkrun call site must pass the pair")
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

    def test_the_receipt_root_can_be_scoped_to_a_campaign(self):
        """A campaign's numbers belong beside its state, not in the fleet-wide dated tree."""
        text = read_tool()
        self.assertIn('L="$ARM_RECEIPTS_ROOT/$NAME"', text,
                      "the executor ignores ARM_RECEIPTS_ROOT")
        self.assertIn('L="$HOME/benchmarks/tp12-$(date +%Y%m%d)/$NAME"', text,
                      "the default window was lost")
        self.assertNotIn('L="${L:-', text, "an unset root must not fall through to the cwd")
        self.assertIn('.prev-$(date +%H%M%S)', text, "the copy-aside must still be scoped to $L")

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
        # The text 0.6B tier is 1024-d; without its own mapping it takes the 4096 default
        # and every reply fails the shape check.
        self.assertIn("dimension_check=1024", text, "no 0.6B dimension override")

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

        The historical 150 x 15 s = 2250 s was below GLM-753B's own measured TTR (2538.9 s,
        recipes/glm/README.md), so a campaign recorded rc=4 "never ready" on a boot that was
        still loading. The ceiling is now a knob and the poll count is derived from it
        (`ReadinessCeiling` executes the arithmetic); the watchdog's pid is still what ends
        the loop early -- there is no `--grace` for the ceiling to sit under any more, and
        the arm that died at t=98 s would otherwise have held the loop until the ceiling.
        """
        text = read_tool()
        self.assertIn("READY_TIMEOUT=${ARM_READY_TIMEOUT:-2250}", text,
                      "the readiness ceiling lost its default")
        self.assertIn('seq 1 "$POLLS"', text, "the loop does not follow the derived ceiling")
        self.assertNotIn("seq 1 150", text, "a literal ceiling outlived the knob")
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


class RecipePathResolution(unittest.TestCase):
    """The campaign passes paths relative to the repo root, not the caller's cwd."""
    CD = 'cd "$HOME/src/sparkrun-recipe-registry" || exit 1'

    def resolves_before_port(self, text: str) -> bool:
        return text.index(self.CD) < text.index("PORT=$(sed")

    def test_the_recipe_is_resolved_before_its_port_is_read(self):
        self.assertTrue(self.resolves_before_port(read_tool()),
                        "the port is read before the recipe path resolves; it silently defaults")

    def test_moving_the_chdir_below_the_port_parse_fails_the_guard(self):
        text = read_tool().replace(self.CD + "\n", "", 1)
        text = text.replace('mkdir -p "$L"\n', 'mkdir -p "$L"\n' + self.CD + "\n", 1)
        self.assertFalse(self.resolves_before_port(text), "the guard passed a broken ordering")


class EngineExitCapture(unittest.TestCase):
    """A boot that dies before the engine writes its own log must still leave its stdout.

    Measured 2026-11-08: the marlin trial on `zz-ds4-1017-sm121-arm3-control` printed
    `Auto-detected DSV4 routed-expert layout: is_fp4_experts=True` and `[TP0] Init parallel
    begin.`, then the container was gone ~1 s later and both lines went with it. sparkrun
    launches containers `--rm` (`auto_remove` defaults true,
    `orchestration/executors/docker.py:555`), so the daemon removes one ~26 ms after its `die`
    event and every post-mortem `docker logs` answers "No such container". Nothing that runs
    after the exit can read the log: the capture is armed before the launch, attaches at
    `create`, and its files are harvested before the teardown.
    """

    ARM = "tools/engine-exit-capture.sh"
    ARM_DIR = 'CAPTURE_DIR="/tmp/sparkrun-exitcap.$$"'
    LAUNCH_CALL = "\nlaunch_arm\n"
    CAPTURED = 'echo "engine stdout captured:'
    STOP = 'sparkrun stop "$TID" 2>&1'
    MISSED = "# capture failed:"

    def arm_slice(self, text: str) -> str:
        """The arming block: what has to be live before any container can be created."""
        start = text.index(self.ARM_DIR)
        return text[start:text.index(self.LAUNCH_CALL, start)]

    def armed_before_launch(self, text: str) -> bool:
        return text.index(self.ARM_DIR) < text.index(self.LAUNCH_CALL)

    def harvest_slice(self, text: str) -> str:
        start = text.index("harvested=0")
        return text[start:text.index(self.STOP, start)]

    def test_the_capture_is_armed_on_every_host_before_the_launch(self):
        text = read_tool()
        self.assertTrue(self.armed_before_launch(text),
                        "the capture is armed after the launch it must cover")
        arm = self.arm_slice(text)
        self.assertIn('for hn in $(echo "$HOSTS"', arm,
                      "one host is captured, not the whole lease")
        self.assertIn("'sparkrun.recipe=$RECIPE'", arm,
                      "the capture is not scoped to this arm's containers. sparkrun labels "
                      "`sparkrun.recipe` with Recipe.qualified_name "
                      "(orchestration/executors/_base.py:942,1005-1006), and for a path recipe "
                      "that is the path as given (core/recipe.py:1589-1597,1924) -- i.e. "
                      "$RECIPE, never `@registry/<stem>` or a basename")
        self.assertIn("'$(( ${ARM_READY_TIMEOUT:-2250} + 900 ))'", arm,
                      "the watcher's deadline is not tied to the readiness ceiling")

    def test_moving_the_capture_below_the_launch_fails_the_guard(self):
        mutated = read_tool().replace(self.ARM_DIR, self.LAUNCH_CALL.lstrip("\n") + "\n" + self.ARM_DIR, 1)
        self.assertFalse(self.armed_before_launch(mutated), "the arming survived the mutation")

    def test_the_capture_is_harvested_and_stopped_before_the_teardown(self):
        text = read_tool()
        self.assertLess(text.index(self.CAPTURED), text.index(self.STOP),
                        "the harvest runs after the stop reaped the containers")
        self.assertIn("\nstop_capture\n", text, "nothing stops the watcher")
        self.assertLess(text.index("\nstop_capture\n"), text.index(self.STOP),
                        "the watcher keeps its event stream open across the teardown")

    def test_a_host_without_a_stream_says_so_in_the_receipt(self):
        """An absent file reads as "the engine printed nothing", which is the claim under test."""
        pre = self.harvest_slice(read_tool())
        self.assertIn(self.MISSED, pre, "a host with no capture leaves no marker")
        self.assertIn("$L/cap-$hn.log", pre, "the marker does not land in the receipt")

    def test_moving_the_harvest_after_the_stop_fails_the_guard(self):
        text = read_tool()
        start = text.index(self.CAPTURED)
        end = text.index(self.STOP, start)
        block = text[start:end]
        mutated = text[:start] + text[end:] + block
        self.assertGreater(mutated.index(self.CAPTURED), mutated.index(self.STOP),
                           "the harvest survived the mutation")

    def test_the_trap_kills_the_capture(self):
        """The watcher outlives the boot: a killed script must not leave a docker client behind."""
        text = read_tool()
        trap = TRAP_RE.search(text)
        assert trap is not None, "no `trap ... sparkrun stop ... EXIT` line"
        self.assertIn("stop_capture;", trap.group(0),
                      "a killed script leaves its `docker events` client on the node")
        mutated = text.replace("trap 'stop_capture; ", "trap '", 1)
        self.assertNotIn("trap 'stop_capture;", mutated, "the trap kill survived the mutation")


class WatchdogGetsTheWholeLease(unittest.TestCase):
    """A TP=4 rendezvous must be judged on every rank, not the API rank alone.

    Measured 2026-11-08: a 753B TP=4 boot was declared stalled on rank 0's flat io/log while
    ranks 1-3 could not be ruled out (their captures returned 70 B "no such object"). The
    watchdog probes each rank in the lease and stalls only when the group is flat.
    """

    BUILD = 'RANK_ARGS+=(--rank "$hn:sparkrun_${TID}_node_$_rank")'
    LAUNCH = "python3 tools/boot-watchdog.py"
    PASS = '"${RANK_ARGS[@]}"'

    def launch_slice(self, text: str) -> str:
        start = text.index(self.LAUNCH)
        return text[start:text.index("WD=$!", start)]

    def test_every_rank_after_zero_is_named_to_the_watchdog(self):
        text = read_tool()
        self.assertIn(self.BUILD, text, "no peer rank is computed for the lease")
        self.assertLess(text.index(self.BUILD), text.index(self.LAUNCH),
                        "the ranks are computed after the watchdog is launched")
        self.assertIn(self.PASS, self.launch_slice(text),
                      "the watchdog is launched rank-0-only")

    def test_dropping_the_peer_ranks_fails_the_guard(self):
        mutated = read_tool().replace(self.BUILD, "", 1)
        self.assertNotIn(self.BUILD, mutated, "the peer-rank build survived the mutation")

    def test_dropping_the_launch_argument_fails_the_guard(self):
        mutated = read_tool().replace(self.PASS + " ", "", 1)
        self.assertNotIn(self.PASS, self.launch_slice(mutated),
                         "the rank argument survived the mutation")


class OverrideEvidence(unittest.TestCase):
    """A row-env ARM_OPTS reaches `sparkrun run` with its values whole and is recorded verbatim.

    2026-11-08: a marlin `-o extra_args=--moe-runner-backend marlin` trial's override could not
    survive the old `${ARM_OPTS:-}` expansion — word-splitting gave `-o` the truncated value and
    left `marlin` a stray positional, which sparkrun's click parser rejects (`--option/-o` is
    `multiple=True`, one value per occurrence; `cli/_common.py:1499-1504`). The unit-separated
    form ($'\\x1f' between fields) keeps a spaced value as ONE argv entry; the plain form still
    word-splits, so the historical `-o parallel=10` usage is unchanged. Either way the effective
    value lands in `arm_opts.txt` beside `image.txt`.
    """

    SEPARATED = "-o\x1fextra_args=--moe-runner-backend marlin"
    NAIVE = "-o extra_args=--moe-runner-backend marlin"

    def run_launch(self, arm_opts: str | None) -> tuple[list[str], str, str]:
        """Run the launch block against a stub `sparkrun`, as a row env would supply ARM_OPTS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            receipt = tmp / "receipt"
            receipt.mkdir()
            bins = tmp / "bin"
            bins.mkdir()
            stub = bins / "sparkrun"
            stub.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$ARGV\"\nexit 0\n")
            stub.chmod(0o755)
            # The slice now begins at the daemon preflight and the pool/model gate, which ask each
            # host for its daemon state and its snapshot. Neither probe is what this harness
            # measures, so both answer healthy here; each probe's own behaviour is executed in
            # DaemonPreflight and ModelPathGate. `#!/usr/bin/env bash` and no `${@: -1}`: the CI
            # runner's /bin/sh is dash, where a negative index is a bad substitution and the stub
            # said nothing -- which surfaced as exit 10, the daemon preflight's unreadable code.
            ssh_stub = bins / "ssh"
            ssh_stub.write_text(
                "#!/usr/bin/env bash\n"
                'last=; for a in "$@"; do last=$a; done\n'
                'case "$last" in\n'
                '  *"sh -s"*) echo "POOL=entries:3" ;;\n'
                '  *) echo "EXE=/usr/bin/sparkrun"\n'
                '     echo "HOME=/home/stub"\n'
                '     echo "FIELD=true"\n'
                "     echo 'RAW={\"running\": true,' ;;\n"
                "esac\n"
            )
            ssh_stub.chmod(0o755)
            recipe = tmp / "arm.yaml"
            recipe.write_text(MODEL_RECIPE)
            home = tmp / "home"
            (home / ".config" / "sparkrun" / "clusters").mkdir(parents=True)
            (home / ".config" / "sparkrun" / "clusters" / "WOPR.yaml").write_text(HUB_CONFIG)
            script = tmp / "launch.sh"
            script.write_text(
                f"""#!/usr/bin/env bash
set -uo pipefail
export ARGV={str(tmp / "argv.txt")!r}
RECIPE={recipe}
HOSTS=node-a,node-b
L={receipt}
NAME=test
{override_slice(read_tool())}
wait
"""
            )
            env = {**os.environ, "PATH": f"{bins}:{os.environ['PATH']}", "HOME": str(home),
                   # The slot gate reads the recipe file; the harness is about the launch argv.
                   "ARM_ALLOW_FEW_SLOTS": "1"}
            env.pop("ARM_OPTS", None)
            if arm_opts is not None:
                env["ARM_OPTS"] = arm_opts
            out = subprocess.run(["bash", str(script)], capture_output=True, text=True,
                                 check=False, env=env, timeout=60)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.recipe_path = str(recipe)
            argv = (tmp / "argv.txt").read_text().splitlines()
            recorded = receipt / "arm_opts.txt"
            text = recorded.read_text().strip() if recorded.is_file() else "<absent>"
            return argv, text, out.stdout + out.stderr

    def test_a_spaced_value_stays_one_argv_entry(self):
        argv, recorded, out = self.run_launch(self.SEPARATED)
        self.assertEqual(argv[:2], ["run", self.recipe_path], out)
        self.assertEqual(argv[-2:], ["-o", "extra_args=--moe-runner-backend marlin"],
                         f"the override was split: {argv}")
        self.assertNotIn("marlin", argv, "the value leaked as a stray positional")
        self.assertEqual(recorded, self.SEPARATED, "the receipt does not name the override that ran")

    def test_the_plain_form_still_word_splits(self):
        argv, recorded, _out = self.run_launch("-o parallel=10")
        self.assertEqual(argv[-2:], ["-o", "parallel=10"])
        self.assertEqual(recorded, "-o parallel=10")

    def test_negative_control_the_naive_space_form_breaks_the_value(self):
        # The shape the old unquoted expansion produced: sparkrun's click parser would take the
        # truncated `-o` value and reject the stray positional. Pinned so it cannot return.
        argv, recorded, _out = self.run_launch(self.NAIVE)
        self.assertEqual(argv[-3:], ["-o", "extra_args=--moe-runner-backend", "marlin"])
        self.assertNotIn("extra_args=--moe-runner-backend marlin", argv,
                         "unquoted expansion produced a whole value; the control is void")
        self.assertEqual(recorded, self.NAIVE, "the verbatim record must not depend on the form")

    def test_the_evidence_precedes_the_launch(self):
        text = read_tool()
        self.assertLess(text.index('> "$L/arm_opts.txt"'), text.index("\nlaunch_arm\n"),
                        "the override is recorded after the launch it describes")

    def test_an_unset_override_launches_bare_and_records_none(self):
        argv, recorded, _out = self.run_launch(None)
        self.assertEqual(argv, ["run", self.recipe_path, "-H", "node-a,node-b",
                                "--cluster", "WOPR"])
        self.assertEqual(recorded, "(none)",
                         "an absent file would read as evidence that was never written")


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
            # The receipt cell the arm reads the verdict from; the stub only carries an exit
            # status, so the loop's own word comes from here (as it does in a real arm).
            (tmp / "watchdog.log").write_text(
                "WATCHDOG t=1s verdict=dead endpoint=down serve_pid=gone\n", encoding="utf-8")
            probes = tmp / "probe.log"
            script = tmp / "loop.sh"
            script.write_text(
                f"""#!/usr/bin/env bash
set -uo pipefail
NODE=127.0.0.1
PORT=1
L={tmp}
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
# Writes the artifacts the way sparkrun's exporter does, then fails: the presence gate passes and
# only the command's status can say the measurement died partway.
PARTIAL_LADDER_STUB = SPARKRUN_STUB + "exit 2\n"


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
# A ladder that died partway: the artifact exists and is non-empty, so `-s` passes and only the
# command's own status can say the measurement failed. Both writers emit incrementally.
PARTIAL_LADDER_STUB_JSON = LADDER_STUB + "exit 2\n"
ACCURACY_STUB = "#!/usr/bin/env bash\nprintf 'DECISION ACCURACY 0.42\\n'\n"
FAILED_ACCURACY_STUB = "#!/usr/bin/env bash\necho 'tool-eval-bench: every request failed' >&2\nexit 3\n"


def decision_arm(text: str) -> str:
    """The decision arm body: ladder, accuracy instrument, receipt artefacts."""
    return case_arm(text, DECISION_ARM_AT)


# What a d1 arm declares instead of an accuracy instrument: `tool-eval-bench
# --decision-bench-only` sends the Typed Decisions/JEV case shape, and a Liquid d1 arm takes
# the vendor's own `{state, questions}` body, so the recipe says so and the executor obeys.
D1_RECIPE = (
    'recipe_version: "2"\n'
    "model: LiquidAI/d1-2B-GGUF:Q8_0\n"
    "runtime: llama-cpp\n"
    "metadata:\n"
    "  decision_accuracy: none\n"
)


def run_decision_arm(
    arm: str,
    ladder_ok: bool = True,
    api: str = "",
    accuracy_ok: bool = True,
    ladder_body: str | None = None,
    recipe_text: str | None = None,
) -> tuple[dict[str, str], str]:
    """Execute *arm* in a temp receipt; return its file map and its output.

    *recipe_text* writes a temp recipe and points ``$RECIPE`` at it, which is how a test asks
    the branch to read a declaration the shipped JEV recipe does not carry.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        receipt = tmp / "receipt"
        receipt.mkdir()
        bins = tmp / "bin"
        bins.mkdir()
        ladder_stub = ladder_body or (LADDER_STUB if ladder_ok else FAILED_LADDER_STUB_JSON)
        for name, body in (
            ("python3", ladder_stub),
            ("uvx", ACCURACY_STUB if accuracy_ok else FAILED_ACCURACY_STUB),
        ):
            stub = bins / name
            stub.write_text(body)
            stub.chmod(0o755)
        if recipe_text is None:
            recipe_line = "RECIPE=recipes/decision/jev-9b-decision-vllm.yaml\n"
        else:
            recipe = tmp / "arm-recipe.yaml"
            recipe.write_text(recipe_text, encoding="utf-8")
            recipe_line = f"RECIPE={recipe}\n"
        script = tmp / "arm.sh"
        script.write_text(
            "#!/usr/bin/env bash\nset -uo pipefail\n"
            f"L={receipt}\n"
            + recipe_line
            + "NAME=decision-arm\nNODE=head.test\nPORT=8020\nSERVED=jev-9b\n"
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


def run_case_arm(
    arm: str, ladder_ok: bool = True, stub_body: str | None = None
) -> tuple[dict[str, str], str]:
    """Execute *arm* in a temp receipt and return its file name -> text map, and its output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        receipt = tmp / "receipt"
        receipt.mkdir()
        stub = tmp / "sparkrun"
        stub.write_text(stub_body or (SPARKRUN_STUB if ladder_ok else FAILED_LADDER_STUB))
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

    def test_a_partial_ladder_artifact_is_not_reported_as_ok(self):
        """Same convention as the decision marker: presence is not measurement.

        Against HEAD's text this fixture produced `suite: n/a` / `reason: pooling arm …` /
        **`ladder: ok`** for a ladder that exited 2 after writing a partial artifact, so a
        consumer read a half-written file as a measured cell.
        """
        receipt, out = run_case_arm(
            case_arm(read_tool(), POOLING_ARM_AT), stub_body=PARTIAL_LADDER_STUB
        )
        house = receipt.get("house.yaml", "")

        self.assertTrue(house, f"presence must survive a partial artifact; receipt={sorted(receipt)}")
        self.assertIn("ladder: failed (rc=2)", house, "a partial artifact was reported as measured")
        self.assertNotIn("ladder: ok", house, "the failed ladder still reads as ok")
        self.assertIn("not a cell", house, "the field does not tell a consumer what the artifact is")
        self.assertIn("pooling ladder failed", out)

    def test_an_unconditional_marker_fails_the_failed_ladder_guard(self):
        """The defect the guard prevents: a marker on an arm that measured nothing."""
        arm = case_arm(read_tool(), POOLING_ARM_AT).replace(
            'if [ -s "$L/ladder.yaml" ]; then', "if true; then"
        )
        receipt, out = run_case_arm(arm, ladder_ok=False)
        self.assertIn("pooling ladder failed", out)
        self.assertIn(
            "house.yaml", receipt, "the weakened guard wrote no marker, so the control proves nothing"
        )
        self.assertIn(
            "ladder: failed (rc=2)",
            receipt["house.yaml"],
            "a marker exists for an arm whose ladder never measured; the defect is presence itself",
        )


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


    def test_a_partial_ladder_artifact_is_not_reported_as_ok(self):
        """`-s` proves the file is non-empty, not that the ladder finished; the field decides.

        Both writers emit incrementally, so a ladder that dies partway leaves a non-empty artifact,
        the presence gate passes, and a field derived from presence alone would call it measured.
        Against HEAD's text this fixture produces exactly that receipt — `suite: n/a` /
        `reason: decision arm …` / **`ladder: ok`** / `accuracy: …` / `accuracy_log:
        teb-decision.log` / `accuracy_status: taken …` — for a ladder that exited 2, so a consumer
        would read a partial artifact as a cell. That is the accuracy bug's mirror, one field over.
        """
        files, out = run_decision_arm(
            decision_arm(read_tool()), ladder_body=PARTIAL_LADDER_STUB_JSON
        )
        house = files.get("house.yaml", "")

        self.assertTrue(house, f"presence must survive a partial artifact; receipt={sorted(files)}")
        self.assertIn("ladder: failed (rc=2)", house, "a partial artifact was reported as measured")
        self.assertNotIn("ladder: ok", house, "the failed ladder still reads as ok")
        self.assertIn("not a cell", house, "the field does not tell a consumer what the artifact is")
        self.assertIn("ladder failed", out)

    def test_a_failed_instrument_is_reported_not_hidden(self):
        """The marker's field carries the outcome; the file still exists because the arm finished.

        A decision arm that measured its ladder and then had `tool-eval-bench` fail is complete as
        a boot — the accuracy number is missing, and re-booting it does not fix that. So the marker
        must exist (suppressing it would re-create the 2026-11-04 re-boot defect inside its own
        fix) and `accuracy_status` must say `failed (rc=3)`, not `taken` off the `$api` value.

        Against the `$api`-derived marker (`git show HEAD:tools/run-arm.sh`) this test fails: that
        marker reads `accuracy_status: taken — the score is in teb-decision.log` for a run whose
        bench exited 3, so the field claimed a score the arm never got.
        """
        files, out = run_decision_arm(decision_arm(read_tool()), accuracy_ok=False)
        house = files.get("house.yaml", "")

        self.assertTrue(house, f"a finished arm's marker was suppressed; receipt={sorted(files)}")
        self.assertIn("ladder: ok", house, "the ladder did measure, whatever the bench did")
        self.assertIn("accuracy_status: failed (rc=3)", house, "a failed bench reads as scored")
        self.assertNotIn("accuracy_status: taken", house, "the run's outcome was not consulted")
        self.assertIn("accuracy_log: teb-decision.log", house, "the log is still the evidence")
        self.assertEqual(out.strip().splitlines()[-1], "rc=3", out)

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
        self.assertIn(
            "ladder: failed (rc=2)",
            files["house.yaml"],
            "a marker exists for an arm whose ladder never measured; the defect is presence itself",
        )

class DecisionAccuracyGap(BashArmHarness):
    """A d1 arm has no accuracy instrument, and its receipt must say that in words.

    `tool-eval-bench --decision-bench-only` sends the Typed Decisions/JEV case shape; a Liquid
    d1 arm takes the vendor's own `{state, questions}` body, so a run of it measures the
    instrument's failure, not the model. The recipe declares `metadata.decision_accuracy: none`
    and the executor obeys the recipe rather than manufacturing a number.
    """

    def test_a_d1_arm_takes_no_jev_shaped_score(self):
        files, out = run_decision_arm(decision_arm(read_tool()), recipe_text=D1_RECIPE)
        house = files.get("house.yaml", "")

        self.assertIn("ladder: ok", house, "the ladder did run; only the accuracy half is absent")
        self.assertIn("accuracy: none —", house, "the marker names an instrument that did not run")
        self.assertIn("accuracy_status: n/a —", house, "not-taken must not read as scored")
        self.assertNotIn("accuracy_status: taken", house, "a score is claimed for the wrong schema")
        self.assertIn("Typed Decisions/JEV", files.get("teb-decision.log", ""), out)
        self.assertEqual(out.strip().splitlines()[-1], "rc=0", out)

    def test_a_decision_arm_without_the_marker_still_runs_the_bench(self):
        """Negative control: the skip follows the recipe's declaration, it is not a blanket."""
        files, _ = run_decision_arm(decision_arm(read_tool()))
        house = files.get("house.yaml", "")

        self.assertIn("accuracy_status: taken", house, "the shipped decision arm lost its score")
        self.assertIn("accuracy: tool-eval-bench", house)
        self.assertIn("DECISION ACCURACY", files.get("teb-decision.log", ""), "the instrument never ran")


class DecisionAccuracyGapNegativeControls(BashArmHarness):
    def test_ignoring_the_declaration_takes_a_score_the_arm_never_had(self):
        """The defect the guard prevents: one score for every decision arm, schema or not."""
        arm = decision_arm(read_tool())
        marker_read = (
            "if grep -qE '^[[:space:]]*decision_accuracy:[[:space:]]*none[[:space:]]*$' "
            '"$RECIPE" 2>/dev/null; then'
        )
        self.assertIn(marker_read, arm, "the marker read was not found; control vacuous")
        weakened = arm.replace(marker_read, "if false; then")

        files, _ = run_decision_arm(weakened, recipe_text=D1_RECIPE)
        self.assertIn(
            "accuracy_status: taken",
            files.get("house.yaml", ""),
            "a d1 arm whose declaration was ignored still reports taken; the control proves nothing",
        )


# ---------------------------------------------------------------------------
# arm-scoped extra client: a quality client on the live serve, never the arm's verdict.
# ---------------------------------------------------------------------------
EXTRA_START = '  if [ -n "${ARM_EXTRA_CLIENT:-}" ]; then'


def extra_client_block(text: str) -> str:
    """The hook verbatim, from its guard to the `fi` closing it."""
    self_count = text.count(EXTRA_START)
    assert self_count == 1, f"{self_count} extra-client guards"
    start = text.index(EXTRA_START)
    return text[start : text.index("  fi\nelse\n", start) + len("  fi\n")]


class ExtraClientHook(BashArmHarness):
    """A second process cannot share the serve: the executor stops it, and its load pollutes cells.

    So the client rides inside the arm, after the ladder/teb and before the unconditional stop,
    with its own rc recorded in the receipt dir rather than promoted to the arm's status.
    """

    def test_the_hook_runs_after_the_cells_and_before_the_stop(self):
        text = read_tool()
        start = text.index(EXTRA_START)
        cells = text.index('artifacts "$L/ladder.yaml" "$L/house.yaml"')
        self.assertLess(cells, start, "the client runs before the arm's cells finish")
        self.assertIn("  esac\n\n  # Arm-scoped extra client", text,
                      "the hook moved inside the recipe case")
        self.assertLess(start, text.index(TEARDOWN_START),
                        "the client runs after the serve is stopped")

    def run_hook(self, env_extra: dict[str, str], house: bool = True,
                 receipt_extra: dict[str, str] | None = None) -> tuple[dict[str, str], str]:
        with tempfile.TemporaryDirectory() as tmpdir:
            receipt = Path(tmpdir)
            if house:
                (receipt / "house.yaml").write_text("suite: ok\nladder: ok\n")
            for name, text in (receipt_extra or {}).items():
                path = receipt / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            script = receipt / "hook.sh"
            script.write_text(
                "#!/usr/bin/env bash\nset -uo pipefail\n"
                f"L={receipt}\nHOSTS=head.test,rank1.test\nRECIPE=recipes/x/arm.yaml\n"
                "NODE=rank0.test\nN=container-1\n"
                "ssh() { printf 'sha256:testimage\\n'; }\nrc=0\n"
                + extra_client_block(read_tool())
                + 'echo "rc=$rc"\n'
            )
            env = {key: value for key, value in os.environ.items()
                   if key not in ("ARM_EXTRA_CLIENT", "ARM_EXTRA_TIMEOUT")}
            env.update(env_extra)
            out = subprocess.run(["bash", str(script)], capture_output=True, text=True,
                                 check=False, env=env, timeout=120)
            files = {path.name: path.read_text(errors="replace")
                     for path in sorted(receipt.iterdir())
                     if path.is_file() and path.name != "hook.sh"}
            return files, out.stdout + out.stderr

    def test_the_hook_gets_launch_facts_and_no_node_is_in_the_row(self):
        """The tracked row carries a script path; the host list is the arm's own launch fact."""
        text = read_tool()
        self.assertIn('export ARM_HOSTS="$HOSTS" ARM_RECIPE="$RECIPE" ARM_RECEIPT_DIR="$L"', text,
                      "the hook cannot derive its endpoint without the launch host list")

    def test_the_hook_receipt_records_the_resolved_image(self):
        """A local-only survey tag is not a digest; the receipt must name what ran."""
        text = read_tool()
        self.assertIn("> \"$L/image.txt\"", text, "the image id is not captured into the receipt")
        self.assertIn("ARM_IMAGE_ID=", text, "the client cannot record the image identity")

    def test_unset_is_the_previous_executor(self):
        files, out = self.run_hook({})
        self.assertNotIn("extra-client.log", files, "the unset hook left a receipt artefact")
        self.assertNotIn("extra client", out, "the unset hook ran something")
        self.assertEqual(files["house.yaml"], "suite: ok\nladder: ok\n", "the unset hook touched the marker")

    def test_a_client_runs_live_and_records_its_rc_without_touching_the_arms(self):
        files, out = self.run_hook({"ARM_EXTRA_CLIENT": "printf 'CELL PASS\\n'"})
        self.assertIn("CELL PASS", files["extra-client.log"], "the client's stdout was lost")
        self.assertIn("extra-client: rc=0", files["extra-client.log"])
        self.assertIn("extra-client: rc=0", files["house.yaml"], "the receipt does not name the client")
        self.assertEqual(out.strip().splitlines()[-1], "rc=0", "the client changed the arm's status")

    def test_a_failed_client_is_recorded_not_promoted(self):
        files, out = self.run_hook({"ARM_EXTRA_CLIENT": "false"})
        self.assertIn("extra-client: rc=1", files["extra-client.log"])
        self.assertEqual(out.strip().splitlines()[-1], "rc=0", "a client failure failed the arm")

    def test_a_wedged_client_is_bounded(self):
        started = time.monotonic()
        files, _ = self.run_hook({"ARM_EXTRA_CLIENT": "sleep 30", "ARM_EXTRA_TIMEOUT": "1"})
        self.assertLess(time.monotonic() - started, 20, "the timeout did not bound the client")
        self.assertIn("extra-client: rc=124", files["extra-client.log"], "the bound is not recorded")

    def test_the_hook_never_manufactures_the_finished_marker(self):
        files, _ = self.run_hook({"ARM_EXTRA_CLIENT": "true"}, house=False)
        self.assertNotIn("house.yaml", files,
                         "a house.yaml from the client would read as a finished arm")
        self.assertIn("extra-client: rc=0", files["extra-client.log"])

    def test_a_successful_client_result_is_normalised_into_quality_json(self):
        # The ERNIE gate: run_benchmarks.py writes `<outdir>/<stem>.json`, which the campaign's
        # measured set did not know, so a 190/200 run filed "no machine-readable artefact".
        files, _ = self.run_hook({
            "ARM_EXTRA_CLIENT":
                "mkdir -p \"$L/client\" && printf '{\"correct\": 190, \"items\": 200}' "
                "> \"$L/client/house.json\""})
        quality = json.loads(files["quality.json"])
        self.assertEqual(quality["client"]["client/house.json"],
                         {"correct": 190, "items": 200})
        self.assertEqual(quality["producer"]["component"], "ARM_EXTRA_CLIENT")
        self.assertEqual(quality["producer"]["rc"], 0)
        self.assertIn("mkdir", quality["producer"]["command"])

    def test_a_client_that_prints_after_writing_still_normalises(self):
        # `run_benchmarks.py`'s real shape: write the result, then print a summary table. The old
        # filter compared the JSON's mtime with the log's last append, so this wrote no quality.json
        # and the arm filed failed -- the rc=4 loop this normalisation exists to end.
        files, _ = self.run_hook({
            "ARM_EXTRA_CLIENT":
                "printf '{\"correct\": 190}' > \"$L/gsm8k.json\"; sleep 1.1; "
                "echo '  => gsm8k: 190/200'"})
        self.assertEqual(json.loads(files["quality.json"])["client"]["gsm8k.json"],
                         {"correct": 190})

    def test_a_pre_existing_unchanged_json_is_not_this_runs_cell(self):
        files, _ = self.run_hook({"ARM_EXTRA_CLIENT": "true"},
                                 receipt_extra={"stale.json": '{"correct": 1}'})
        self.assertNotIn("quality.json", files,
                         "a previous boot's unchanged file became this run's measurement")

    def test_an_overwritten_json_is_normalised(self):
        # A resume overwrites its own `<stem>.json`; identity must see the change, not a set diff.
        files, _ = self.run_hook({
            "ARM_EXTRA_CLIENT":
                "printf '{\"correct\": 200}' > \"$L/gsm8k.json\"; sleep 1.1; echo done"},
            receipt_extra={"gsm8k.json": '{"correct": 1}'})
        self.assertEqual(json.loads(files["quality.json"])["client"]["gsm8k.json"],
                         {"correct": 200})

    def test_a_failed_client_writes_no_measured_artefact(self):
        files, _ = self.run_hook({
            "ARM_EXTRA_CLIENT":
                "printf '{\"correct\": 1}' > \"$L/client.json\"; false"})
        self.assertNotIn("quality.json", files,
                         "a failed hook's partial JSON was promoted to a measurement")

    def test_a_client_that_writes_no_json_writes_no_measured_artefact(self):
        files, _ = self.run_hook({"ARM_EXTRA_CLIENT": "true"})
        self.assertNotIn("quality.json", files, "a marker was manufactured for an empty hook")


# ---------------------------------------------------------------------------
# The readiness ceiling and the image cell, executed from their own slices.
#
# GLM-753B's measured TTR is 2538.9 s (recipes/glm/README.md), against a hardcoded
# 150 x 15 s = 2250 s ceiling: a campaign recorded rc=4 "never ready" on a boot that
# was still loading. The ceiling is now a knob, and the image cell moved out of the
# ARM_EXTRA_CLIENT branch because every receipt must name what ran -- the concurrency
# rows had to smuggle an image-id gate into the client env to get one.

POLLS_END = 'for _ in $(seq 1 "$POLLS"); do'
IMAGE_START = "# The image cell belongs to every receipt"
IMAGE_END = 'echo "image=$IMAGE_ID"'


def ceiling_slice(text: str) -> str:
    start = text.index(LOOP_START)
    end = text.index(POLLS_END, start)
    return text[start:end]


OVERRIDE_START = "# ARM_OPTS carries `-o key=value` overrides"
OVERRIDE_END = "# The container lives on the TARGET node"


def override_slice(text: str) -> str:
    """The launch block verbatim: the override channel, its evidence write and the launch call."""
    start = text.index(OVERRIDE_START)
    return text[start : text.index(OVERRIDE_END, start)]


def image_slice(text: str) -> str:
    start = text.index(IMAGE_START)
    return text[start : text.index(IMAGE_END, start) + len(IMAGE_END)]


GUARD_START = "# guard-arm: start"
GUARD_END = "# guard-arm: end"


def guard_slice(text: str) -> str:
    start = text.index(GUARD_START)
    return text[start : text.index(GUARD_END, start) + len(GUARD_END)]


def clean_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The harness environment without the knobs under test, so a developer's shell cannot leak them."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("ARM_READY_TIMEOUT", "ARM_POLL_SLEEP", "ARM_EXTRA_CLIENT")}
    env.update(extra or {})
    return env


class ReadinessCeiling(unittest.TestCase):
    """ARM_READY_TIMEOUT drives the poll count; the default is the old 2250 s, bounded."""

    def polls(self, extra_env: dict[str, str] | None = None,
              text: str | None = None) -> int:
        script = ("set -uo pipefail\n" + ceiling_slice(text or read_tool())
                  + '\nprintf "%s\\n" "$POLLS"\n')
        out = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                             check=False, env=clean_env(extra_env), timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        return int(out.stdout.strip())

    def run_loop(self, extra_env: dict[str, str]) -> tuple[str, int, float]:
        """Execute the real loop with a `$WD` that dies of its own error, so it polls to the ceiling."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            wd = tmp / "watchdog.sh"
            wd.write_text("#!/usr/bin/env bash\nexit 4\n")
            probes = tmp / "probe.log"
            script = tmp / "loop.sh"
            script.write_text(
                f"""#!/usr/bin/env bash
set -uo pipefail
NODE=127.0.0.1
PORT=1
curl() {{ echo probe >> {probes}; printf '000'; }}
bash {wd} &
WD=$!
sleep 0.3
{readiness_loop(read_tool())}
echo "probes=$(wc -l < {probes})"
"""
            )
            started = time.monotonic()
            out = subprocess.run(["bash", str(script)], capture_output=True, text=True,
                                 check=False, env=clean_env(extra_env), timeout=120)
            elapsed = time.monotonic() - started
        probes_run = int(re.search(r"^probes=(\d+)$", out.stdout, re.M).group(1))
        return out.stdout + out.stderr, probes_run, elapsed

    def run_loop_launcher(self, text: str, extra_env: dict[str, str]) -> tuple[str, int, float]:
        """Execute the real loop with a `$LAUNCH` that exits on its own readiness verdict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            wd = tmp / "watchdog.sh"
            wd.write_text("#!/usr/bin/env bash\nexit 4\n")
            launch = tmp / "launcher.sh"
            launch.write_text(
                "#!/usr/bin/env bash\n"
                "sleep 0.6\n"
                f"echo 'ERROR: endpoint did not become ready -- rank-0 readiness probe: Timeout'"
                f" > {tmp / 'launch.log'}\n"
                "exit 1\n")
            probes = tmp / "probe.log"
            script = tmp / "loop.sh"
            script.write_text(
                f"""#!/usr/bin/env bash
set -uo pipefail
NODE=127.0.0.1
PORT=1
L={tmp}
TID=abc123
NAME=arm-under-test
curl() {{ echo probe >> {probes}; printf '000'; }}
bash {launch} &
LAUNCH=$!
bash {wd} &
WD=$!
sleep 0.2
{readiness_loop(text)}
echo "probes=$(wc -l < {probes})"
"""
            )
            started = time.monotonic()
            out = subprocess.run(["bash", str(script)], capture_output=True, text=True,
                                 check=False, env=clean_env(extra_env), timeout=180)
            elapsed = time.monotonic() - started
        probes_run = int(re.search(r"^probes=(\d+)$", out.stdout, re.M).group(1))
        return out.stdout + out.stderr, probes_run, elapsed

    def test_the_default_is_the_old_2250s_ceiling(self):
        self.assertIn("READY_TIMEOUT=${ARM_READY_TIMEOUT:-2250}", read_tool())
        self.assertEqual(self.polls({"ARM_POLL_SLEEP": "15"}), 150)

    def test_3000s_at_15s_poll_is_200_polls(self):
        self.assertEqual(self.polls({"ARM_READY_TIMEOUT": "3000",
                                     "ARM_POLL_SLEEP": "15"}), 200)

    def test_a_short_ceiling_still_makes_one_attempt(self):
        self.assertEqual(self.polls({"ARM_READY_TIMEOUT": "1",
                                     "ARM_POLL_SLEEP": "10"}), 1)

    def test_a_fractional_poll_interval_rounds_up(self):
        self.assertEqual(self.polls({"ARM_READY_TIMEOUT": "3",
                                     "ARM_POLL_SLEEP": "0.5"}), 6)

    def test_negative_control_the_default_is_load_bearing(self):
        """Emptied, the ceiling collapses to one attempt -- the positive cases above catch it."""
        text = read_tool().replace("${ARM_READY_TIMEOUT:-2250}", "${ARM_READY_TIMEOUT:-}")
        self.assertNotEqual(self.polls({"ARM_POLL_SLEEP": "15"}, text=text), 150)

    def test_the_unset_path_is_bounded(self):
        """Not silently unbounded: the historical instant-loop device still ends at 150 probes."""
        out, probes, elapsed = self.run_loop({"ARM_POLL_SLEEP": "0"})
        self.assertEqual(probes, 150, out)
        self.assertLess(elapsed, 30, "the unset ceiling did not terminate quickly")
        self.assertIn("readiness=no", out)

    def test_a_dead_launcher_ends_the_loop_instead_of_holding_its_containers(self):
        """The launcher's own readiness verdict is the end of the boot, not the start of a wait.

        A `sparkrun run` that gives up on readiness exits non-zero and leaves its containers
        running (2026-11-10: ERNIE quartet, rank-0 probe timed out at 1364 s, four containers up
        32 min until a human stopped the task). Without the launcher poll this loop sat out the
        rest of its ceiling on that decided boot, holding the node for it.
        """
        text = read_tool()
        out, probes, elapsed = self.run_loop_launcher(text, {"ARM_READY_TIMEOUT": "60",
                                                             "ARM_POLL_SLEEP": "1"})
        self.assertIn("readiness=no", out)
        self.assertIn("launcher: exited rc=1 before readiness on task abc123", out)
        self.assertLess(probes, 10, f"the loop waited out a ceiling the launcher had ended: {out}")
        self.assertLess(elapsed, 20, "the arm held the boot after the launcher gave up")
        # Negative control: the loop without its launcher poll runs the whole ceiling.
        stripped = text.replace(launcher_block(text), "")
        self.assertNotEqual(stripped, text, "the launcher poll is not in the loop any more")
        out, probes, _ = self.run_loop_launcher(stripped, {"ARM_READY_TIMEOUT": "5",
                                                           "ARM_POLL_SLEEP": "1"})
        self.assertIn("readiness=no", out)
        self.assertEqual(probes, 5, out)

    def test_the_ceiling_drives_the_real_loop(self):
        out, probes, elapsed = self.run_loop({"ARM_READY_TIMEOUT": "3",
                                              "ARM_POLL_SLEEP": "1"})
        self.assertEqual(probes, 3, out)
        self.assertLess(elapsed, 10, "the configured ceiling did not bound the loop")

    def test_the_rc_4_message_names_the_effective_ceiling(self):
        text = read_tool()
        self.assertIn("never answered 200 within ${READY_TIMEOUT}s", text)
        self.assertIn('(${POLLS} polls at ${POLL_SLEEP}s)', text)
        # Negative control: a literal in the message would hide a raised ceiling.
        mutated = text.replace("within ${READY_TIMEOUT}s", "within 2250s")
        self.assertNotIn("never answered 200 within ${READY_TIMEOUT}s", mutated)


class ImageCell(unittest.TestCase):
    """Every booting row writes image.txt / ARM_IMAGE_ID, client or no client."""

    def run_image_block(self, stub_image: str) -> tuple[str, int, dict[str, object]]:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            receipt = tmp / "receipt"
            receipt.mkdir()
            calls = tmp / "calls.log"
            script = tmp / "image.sh"
            script.write_text(
                f"""#!/usr/bin/env bash
set -uo pipefail
L={receipt}
NODE=127.0.0.1
N=sparkrun_test_solo
NAME=test
IMAGE_STUB={stub_image!r}
sleep() {{ :; }}
on_node() {{ echo x >> {calls}; [ -n "$IMAGE_STUB" ] && printf '%s\\n' "$IMAGE_STUB"; }}
{image_slice(read_tool())}
printf 'IMAGE_ENV=%s\\n' "${{ARM_IMAGE_ID:-unset}}"
"""
            )
            out = subprocess.run(["bash", str(script)], capture_output=True, text=True,
                                 check=False, timeout=30)
            retries = len(calls.read_text().splitlines())
            written = receipt / "image.txt"
            snapshot = {"exists": written.is_file(),
                        "text": written.read_text().strip() if written.is_file() else ""}
            return out.stdout + out.stderr, retries, snapshot

    def test_a_plain_boot_writes_the_image_cell_without_a_client(self):
        sha = "sha256:7f8f1b38bcf1770e527bdc9ceacdc663063d2871e464f7693a8602e0efbd4a95"
        out, retries, receipt = self.run_image_block(sha)
        self.assertEqual(receipt["text"], sha)
        self.assertIn("IMAGE_ENV=" + sha, out, "the id is not exported to the hook")
        self.assertIn("image=" + sha, out)
        self.assertEqual(retries, 1)

    def test_the_value_is_the_container_config_sha_not_a_manifest_digest(self):
        block = image_slice(read_tool())
        self.assertIn("docker inspect -f '{{.Image}}'", block)
        self.assertNotIn("RepoDigests", block)
        self.assertNotIn("manifest inspect", block)

    def test_a_missing_id_fails_visibly_and_writes_no_placeholder(self):
        out, retries, receipt = self.run_image_block("")
        self.assertIn("no image id", out)
        self.assertNotIn("unknown", out)
        self.assertFalse(receipt["exists"],
                         "a placeholder image.txt would let the receipt look complete")
        self.assertEqual(retries, 3, "the read is not retried")
        # The slice's exit status is the mechanism: executed alone it must be non-zero.
        script = f"set -uo pipefail\nL=/tmp\nNODE=127.0.0.1\nN=c\nNAME=t\nsleep(){{ :; }}\non_node(){{ :; }}\n{image_slice(read_tool())}\n"
        rc = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                            check=False, timeout=30).returncode
        self.assertNotEqual(rc, 0)

    def test_one_writer_the_extra_client_hook_does_not_race_it(self):
        text = read_tool()
        self.assertEqual(text.count('> "$L/image.txt"'), 1)
        self.assertNotIn("image.txt", extra_client_block(text))


# ---------------------------------------------------------------------------
# Blocks executed against stub nodes: the daemon preflight and the /metrics scrape.
#
# Both blocks are about a launch that fails for infrastructure reasons being read as an arm that
# failed, so the guard cannot be a text search: ssh, docker and curl are fakes on PATH and the
# script's own slice runs. `ssh` executes the remote command locally with those fakes and the
# per-host fixture directory, which is what a node's answer looks like from here.
# ---------------------------------------------------------------------------

def block_region(text: str, start: str, end: str) -> str:
    """The block between two unique markers, both included."""
    at = text.index(start)
    return text[at : text.index(end, at) + len(end)]


DP_START = "# daemon-preflight: start"
DP_END = "# daemon-preflight: end"
MP_START = "# model-path: start"
MP_END = "# model-path: end"
CI_START = "# cache-inspect: start"
CI_END = "# cache-inspect: end"
NL_START = "# native-logs: start"
NL_END = "# native-logs: end"
OOM_START = "# oom-watchdog: start"
OOM_END = "# oom-watchdog: end"
M_START = "# metrics-scrape: start"
M_END = "# metrics-scrape: end"

SSH_STUB = """#!/usr/bin/env bash
host="${@: -2:1}"; host="${host#red@}"; cmd="${@: -1}"
[ -f "$NODES/$host.on" ] || { echo "ssh: connect to host $host: Connection refused" >&2; exit 255; }
DP_HOST="$host" PATH="$BINS:$PATH" bash -c "$cmd"
"""

DOCKER_STUB = """#!/usr/bin/env bash
case "$1" in
  ps) cat "$NODES/$DP_HOST.ps" 2>/dev/null; exit 0 ;;
  exec) shift; [ "${1:-}" = "-i" ] && shift; cid="$1"; shift
        [ -f "$NODES/$DP_HOST.exec-fail" ] && { cat "$NODES/$DP_HOST.exec-fail" >&2; exit 125; }
        exec "$@" ;;
  *) exit 0 ;;
esac
"""

# Fixture lines: <curl exit code>, <http code>, then the body. A non-zero exit prints nothing,
# which is what curl does when the connection itself failed.
CURL_STUB = """#!/usr/bin/env bash
printf '%s\\n' "${DP_HOST:-?}" >> "${CURL_CALLS:-/dev/null}"
f="$NODES/$DP_HOST.curl"
[ -f "$f" ] || { echo "curl: (7) Failed to connect to 127.0.0.1" >&2; exit 7; }
ex=$(sed -n 1p "$f"); code=$(sed -n 2p "$f"); body=$(sed -n '3,$p' "$f")
[ "${ex:-0}" -ne 0 ] && { echo "curl: ($ex) probe failed" >&2; exit "$ex"; }
printf '%s\\n%s' "$body" "$code"
"""

# Fixture lines for a node's `sparkrun daemon status`: <exit code>, then stdout. The same binary is
# the driver's `model-cache` client, so those verbs read their own fixtures: an inspect attempt
# counter like the `ls` probe (`cache-inspect.<n>.txt`, falling back to `cache-inspect.txt`) and a
# `resolve.txt` for its own status and output.
NODE_SPARKRUN_STUB = """#!/usr/bin/env bash
if [ "${1:-}" = "--version" ]; then
  echo "sparkrun, version 0.4.3-alpha+gstub"; exit 0
fi
if [ "${1:-}" = "logs" ]; then
  f="$NODES/logs.txt"
  [ -f "$f" ] || { echo "sparkrun: no logs fixture" >&2; exit 1; }
  ex=$(sed -n 1p "$f"); sed -n '2,$p' "$f"; exit "${ex:-0}"
fi
if [ "${1:-}" = "model-cache" ]; then
  case "${2:-}" in
    inspect)
      n=$(sed -n 1p "$NODES/.attempt.inspect" 2>/dev/null || echo 0); n=$((n + 1))
      echo "$n" > "$NODES/.attempt.inspect"
      f="$NODES/cache-inspect.$n.txt"; [ -f "$f" ] || f="$NODES/cache-inspect.txt"
      [ -f "$f" ] || { echo "sparkrun: no inspect fixture" >&2; exit 2; }
      ex=$(sed -n 1p "$f"); sed -n '2,$p' "$f"; exit "${ex:-0}" ;;
    resolve)
      f="$NODES/resolve.txt"
      [ -f "$f" ] || { echo "Wrote manifest to ${@: -1}"; exit 0; }
      ex=$(sed -n 1p "$f"); sed -n '2,$p' "$f"; exit "${ex:-0}" ;;
  esac
fi
f="$NODES/${DP_HOST:-?}.sparkrun"
[ -f "$f" ] || { echo "sparkrun: no fixture for ${DP_HOST:-?}" >&2; exit 2; }
ex=$(sed -n 1p "$f"); sed -n '2,$p' "$f"; exit "${ex:-0}"
"""

# Fixture lines for a node's `ls -A <snapshot>`: <exit code>, then what ls prints (stdout when 0,
# stderr otherwise). `<host>.ls.<n>` answers attempt n, `<host>.ls` every other one, so a retrying
# probe can be shown recovering without a live pool. No fixture is a pool-less node.
NODE_LS_STUB = """#!/usr/bin/env bash
host="${DP_HOST:-?}"
n=$(sed -n 1p "$NODES/.attempt.$host" 2>/dev/null || echo 0); n=$((n + 1))
echo "$n" > "$NODES/.attempt.$host"
f="$NODES/$host.ls.$n"; [ -f "$f" ] || f="$NODES/$host.ls"
[ -f "$f" ] || { echo "ls: cannot access '$2': No such file or directory" >&2; exit 2; }
ex=$(sed -n 1p "$f"); out=$(sed -n '2,$p' "$f")
if [ "${ex:-0}" -eq 0 ]; then printf '%s\\n' "$out"; else printf '%s\\n' "$out" >&2; fi
exit "${ex:-0}"
"""

# Server-side authority stubs: a unit table, the mount line that names the mgmtd host, and the
# socket connect the probe runs through python3.
NODE_SYSTEMCTL_STUB = """#!/usr/bin/env bash
u="${@: -1}"
s=$(sed -n "s/^$u=//p" "$NODES/${DP_HOST:-?}.units" 2>/dev/null | head -1)
[ -n "$s" ] || { echo "Unit $u.service could not be found." >&2; exit 4; }
echo "$s"
[ "$s" = active ] && exit 0 || exit 3
"""

NODE_MOUNT_STUB = """#!/usr/bin/env bash
sed -n 1p "$NODES/${DP_HOST:-?}.mount" 2>/dev/null
exit 0
"""

NODE_IP_STUB = """#!/usr/bin/env bash
cat "$NODES/${DP_HOST:-?}.ip" 2>/dev/null
exit 0
"""

NODE_PYTHON_STUB = """#!/usr/bin/env bash
exit "$(sed -n 1p "$NODES/${DP_HOST:-?}.port" 2>/dev/null || echo 0)"
"""

# A host's earlyoom journal: <exit code> on line 1, then the lines the unit wrote. No fixture is
# an unreadable journal (journalctl failed), which is the `unknown` case, never "no line".
NODE_JOURNALCTL_STUB = """#!/usr/bin/env bash
f="$NODES/${DP_HOST:-?}.journal"
[ -f "$f" ] || { echo "journalctl: Failed to open journal: no such file" >&2; exit 1; }
ex=$(sed -n 1p "$f"); sed -n '2,$p' "$f"; exit "${ex:-0}"
"""

POOL_PRESENT = "0\nconfig.json\nmodel-00001-of-00002.safetensors\nmodel-00002-of-00002.safetensors\n"
POOL_ABSENT = "2\nls: cannot access '/fake/pool/huggingface': No such file or directory\n"
POOL_ECOMM = "2\nls: cannot access '/fake/pool/huggingface': Communication error on send\n"
POOL_TIMEOUT = "124\n"
POOL_EMPTY = "0\n"
UNITS_ACTIVE = "beegfs-mgmtd=active\nbeegfs-meta=active\nbeegfs-storage=active\n"
UNITS_STORAGE_FAILED = "beegfs-mgmtd=active\nbeegfs-meta=active\nbeegfs-storage=failed\n"
UNITS_CLIENT_IDLE = "beegfs-mgmtd=inactive\nbeegfs-meta=failed\nbeegfs-storage=active\n"
MOUNT_LINE = "192.0.2.10:/mnt/beegfs on /mnt/beegfs type beegfs (rw,sysMgmtdHost=192.0.2.10)\n"
SERVER_IP_LINE = "2: eth0    inet 192.0.2.10/24 brd 192.0.2.255 scope global eth0\n"
CLIENT_IP_LINE = "2: eth0    inet 192.0.2.11/24 brd 192.0.2.255 scope global eth0\n"
PORT_OK = "0\n"
PORT_CLOSED = "1\n"
HUB_CONFIG = "distribution:\n  hf_cache: /fake/pool/huggingface\n"
MODEL_RECIPE = (
    "runtime: vllm\n"
    "model: deepseek-ai/DeepSeek-V4.1-Flash-1017\n"
    "model_revision: 1bae0e1088993b9b82de08f59de5be5a34e42170\n"
)

DAEMON_UP = '0\n{\n  "running": true,\n  "binding": "x"\n}\n'
DAEMON_DOWN = '0\n{\n  "running": false,\n  "binding": "x"\n}\n'
DAEMON_NO_FIELD = '0\n{\n  "binding": "x"\n}\n'

CONTAINER_PS = "abc123def456 sparkrun_abc123_solo\n"
VLLM_BODY = "# HELP vllm:num_requests_running ...\nvllm:num_requests_running 1\n"


class ExecutedBlock(unittest.TestCase):
    """Runs one extracted block on stub nodes; returns (rc, output, receipt files, curl calls)."""

    def setUp(self):
        if not shutil.which("bash"):
            self.skipTest("bash not on PATH")

    def run_block(self, body, hosts=("head.test",), files=None, recipe="runtime: vllm\n",
                  ready="yes", house=False, hub=True, hub_text=None, env_extra=None, timeout=60,
                  receipt_extra=None):
        files = files or {}
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            receipt = tmp / "receipt"; receipt.mkdir()
            nodes = tmp / "nodes"; nodes.mkdir()
            bins = tmp / "bin"; bins.mkdir()
            home = tmp / "home"; home.mkdir()
            if hub:
                clusters = home / ".config" / "sparkrun" / "clusters"
                clusters.mkdir(parents=True)
                (clusters / "WOPR.yaml").write_text(hub_text or HUB_CONFIG)
            for name, stub in (("ssh", SSH_STUB), ("docker", DOCKER_STUB), ("curl", CURL_STUB),
                               ("sparkrun", NODE_SPARKRUN_STUB), ("ls", NODE_LS_STUB),
                               ("systemctl", NODE_SYSTEMCTL_STUB), ("mount", NODE_MOUNT_STUB),
                               ("journalctl", NODE_JOURNALCTL_STUB),
                               ("ip", NODE_IP_STUB), ("python3", NODE_PYTHON_STUB)):
                stub_path = bins / name
                stub_path.write_text(stub)
                stub_path.chmod(0o755)
            for host in hosts:
                (nodes / f"{host}.on").write_text("")
            for name, text in files.items():
                (nodes / name).write_text(text)
            calls = tmp / "curl-calls"; calls.write_text("")
            recipe_path = tmp / "recipe.yaml"; recipe_path.write_text(recipe)
            if house:
                (receipt / "house.yaml").write_text("suite: ok\n")
            for name, text in (receipt_extra or {}).items():
                (receipt / name).write_text(text)
            script = tmp / "arm.sh"
            script.write_text(
                "#!/usr/bin/env bash\nset -uo pipefail\n"
                f"L={receipt}\nNAME=stub-arm\nNODE={hosts[0]}\nPORT=8000\n"
                f"HOSTS={','.join(hosts)}\nTID=abc123\nRECIPE={recipe_path}\nready={ready}\n"
                + body + "\necho NEXT\necho AGG=${M_AGG:-none}\n"
            )
            run_env = {**os.environ, "PATH": f"{bins}:{os.environ['PATH']}", "NODES": str(nodes),
                       "BINS": str(bins), "CURL_CALLS": str(calls), "HOME": str(home)}
            run_env.update(env_extra or {})
            out = subprocess.run(
                ["bash", str(script)], capture_output=True, text=True, check=False, timeout=timeout,
                env=run_env,
            )
            receipt_files = {p.name: p.read_text(errors="replace")
                             for p in sorted(receipt.iterdir()) if p.is_file()}
            for sub in sorted(receipt.glob("logs/*")):
                receipt_files[f"logs/{sub.name}"] = sub.read_text(errors="replace")
            return out.returncode, out.stdout + out.stderr, receipt_files, calls.read_text().split()


class DaemonPreflight(ExecutedBlock):
    """An inactive per-node daemon must refuse the arm, not be read as a token error mid-launch.

    Measured 2026-11-08: leases @3-@6 died at `[3/6] Distributing resources` with
    `[Errno 70] Communication error on send: /home/red/.cache/huggingface/token` because the
    daemon was inactive on all four nodes, and the token file was byte-identical everywhere.
    """

    def block(self):
        return block_region(read_tool(), DP_START, DP_END)

    def test_an_inactive_daemon_on_one_host_refuses_at_9_and_names_it(self):
        rc, out, files, _ = self.run_block(
            self.block(), hosts=("head.test", "rank1.test"),
            files={"head.test.sparkrun": DAEMON_UP, "rank1.test.sparkrun": DAEMON_DOWN})
        self.assertEqual(rc, 9, out)
        self.assertIn("rank1.test", out, "the refusal does not name the host")
        self.assertIn("sparkrun daemon start", out, "the refusal does not name the fix")
        self.assertIn("[Errno 70]", out, "the failure it prevents is not named")
        self.assertIn("daemon-preflight.txt", out, "the refusal points at no evidence")
        self.assertNotIn("NEXT", out, "the arm continued past the refusal")
        probe = files["daemon-preflight.txt"]
        self.assertIn("rank1.test,", probe)
        self.assertIn("false", probe)

    def test_all_hosts_active_proceeds(self):
        rc, out, files, _ = self.run_block(
            self.block(), hosts=("head.test", "rank1.test"),
            files={"head.test.sparkrun": DAEMON_UP, "rank1.test.sparkrun": DAEMON_UP})
        self.assertEqual(rc, 0, out)
        self.assertIn("NEXT", out, "an all-active lease did not reach the launch")
        self.assertEqual(len(files["daemon-preflight.txt"].splitlines()), 2)
        first = files["daemon-preflight.txt"].splitlines()[0].split(",")
        self.assertEqual(len(first), 5, "host,binary,HOME,field,raw expected")
        self.assertNotEqual(first[1], "-", "the remote binary was not resolved")
        self.assertNotEqual(first[2], "-", "the pinned HOME was not recorded")

    def test_an_unreadable_probe_refuses_at_10_and_never_says_daemon_down(self):
        rc, out, _, _ = self.run_block(
            self.block(), hosts=("head.test", "rank1.test"),
            files={"head.test.sparkrun": DAEMON_UP})
        self.assertEqual(rc, 10, out)
        self.assertIn("could not be read", out)
        self.assertNotIn("no running sparkrun daemon", out,
                         "an unreachable host was reported as a dead daemon")
        self.assertNotIn("NEXT", out)

    def test_a_status_without_a_running_field_is_unverifiable(self):
        rc, out, _, _ = self.run_block(
            self.block(), hosts=("head.test",),
            files={"head.test.sparkrun": DAEMON_NO_FIELD})
        self.assertEqual(rc, 10, out)
        self.assertNotIn("no running sparkrun daemon", out)

    def test_negative_control_without_the_block_the_dead_daemon_proceeds(self):
        self.assertIn(DP_START, read_tool(), "the guard is gone; this control would be vacuous")
        rc, out, _, _ = self.run_block(
            "", hosts=("head.test", "rank1.test"),
            files={"head.test.sparkrun": DAEMON_UP, "rank1.test.sparkrun": DAEMON_DOWN})
        self.assertEqual(rc, 0, out)
        self.assertIn("NEXT", out)

    def test_the_probe_precedes_the_capture_arming_and_the_launch(self):
        text = read_tool()
        at = text.index(DP_START)
        self.assertLess(at, text.index("CAPTURE_DIR="), "the capture is armed before the probe")
        self.assertLess(at, text.index("\nlaunch_arm\n"), "the launch precedes the probe")
        self.assertLess(text.index("# daemon-preflight: end"), text.index("\nlaunch_arm\n"))


class MetricsScrape(ExecutedBlock):
    """A /metrics body is captured before `sparkrun stop`, with four states, never an empty file.

    `--rm` deletes the container ~26 ms after `die`, and sglang's /metrics binds on port_base+3
    inside the container, so both the timing and the namespace are load-bearing.
    """

    def block(self):
        return block_region(read_tool(), M_START, M_END)

    def sglang(self, flag="--enable-metrics"):
        return f"runtime: sglang\ncommand: sglang serve --port {{port}} {flag}\n"

    def run_metrics(self, curl_fixture, **kwargs):
        kwargs.setdefault("files", {"head.test.ps": CONTAINER_PS,
                                    "head.test.curl": curl_fixture})
        return self.run_block(self.block(), **kwargs)

    def test_a_prometheus_body_is_captured_and_the_receipt_names_what_was_probed(self):
        rc, out, files, calls = self.run_metrics(f"0\n200\n{VLLM_BODY}", house=True)
        self.assertEqual(rc, 0, out)
        self.assertIn("AGG=captured", out)
        self.assertIn("vllm:num_requests_running", files["metrics-head.test.txt"])
        header = files["metrics-head.test.txt"].splitlines()[0]
        self.assertIn("captured host=head.test container=abc123def456", header)
        self.assertIn("url=http://127.0.0.1:8000/metrics", header)
        self.assertEqual(len(calls), 1, "one connection per host expected")

    def test_the_sidecar_is_the_only_authority_and_the_marker_is_untouched(self):
        """campaign/sparkrun_campaign/evidence.py:metrics_status reads this sidecar, never a key.

        The producer contract asserted here is the one the campaign reads: a `# runtime=… port=…`
        header, one verdict line per host, and a captured host's own file carrying the body.
        """
        rc, out, files, _ = self.run_metrics(
            "0\n200\n" + VLLM_BODY, hosts=("head.test", "rank1.test"), house=True,
            files={"head.test.ps": CONTAINER_PS, "head.test.curl": "0\n200\n" + VLLM_BODY,
                   "rank1.test.ps": "aaaabbbbcccc sparkrun_abc123_node_1\n",
                   "rank1.test.curl": "0\n200\n" + VLLM_BODY})
        self.assertEqual(rc, 0, out)
        self.assertEqual(files["house.yaml"], "suite: ok\n",
                         "the scrape wrote a second copy of its verdict into the marker")
        lines = files["metrics-status.txt"].splitlines()
        self.assertTrue(lines[0].startswith("# runtime=vllm port=8000"), lines[0])
        verdicts = lines[1:]
        self.assertEqual(len(verdicts), 2, "one verdict line per host")
        for line in verdicts:
            self.assertRegex(
                line,
                r"^(captured|absent|no_probe|wrong_port) host=\S+ container=\S+ url=\S+ reason=\S")
        for host in ("head.test", "rank1.test"):
            self.assertIn("vllm:num_requests_running", files[f"metrics-{host}.txt"],
                          f"{host}'s verdict arrived without a body")

    def test_sglang_is_probed_on_the_api_port_inside_the_container(self):
        """sglang mounts Prometheus on the served app; `port_base + 3` is its ZMQ IPC channel."""
        rc, out, files, _ = self.run_metrics(
            "0\n200\n# TYPE sglang:num_requests_running gauge\n",
            recipe=self.sglang())
        self.assertEqual(rc, 0, out)
        self.assertIn("AGG=captured", out, "a TYPE line alone is a metrics body")
        self.assertIn("url=http://127.0.0.1:8000/metrics",
                      files["metrics-status.txt"], "the API port was not probed")

    def test_tensorfold_is_probed_without_a_flag(self):
        """The tensorfold shim serves /metrics unconditionally; skipping it reads as absent."""
        tick = "`"
        recipe = ("runtime: sglang\nmods:\n"
                  '  - "mods/tensorfold-glm-exl3-launcher"\n'
                  "command: python3 /workspace/mods/tensorfold-glm-exl3-launcher/launcher.py --boot\n")
        rc, out, files, calls = self.run_metrics(
            "0\n200\n# HELP tensorfold:requests_running ...\ntensorfold:requests_running 1\n",
            recipe=recipe)
        self.assertEqual(rc, 0, out)
        self.assertIn("AGG=captured", out, "an instrumented-by-default arm read as absent")
        self.assertIn("url=http://127.0.0.1:8000/metrics", files["metrics-status.txt"])
        self.assertEqual(len(calls), 1, "the arm was skipped without a probe")
        self.assertNotIn(tick + "recipe-has-no-flag" + tick, out)

    def test_a_200_that_is_not_prometheus_is_wrong_port_not_data(self):
        rc, out, files, _ = self.run_metrics("0\n200\n<html><body>proxy error</body></html>",
                                             house=True)
        self.assertEqual(rc, 0, out)
        self.assertIn("AGG=wrong_port", out)
        self.assertIn("not-prometheus", files["metrics-head.test.txt"])
        self.assertNotIn("metrics", files["house.yaml"],
                         "a foreign 200 reached the marker")

    def test_a_404_is_absent(self):
        rc, out, files, _ = self.run_metrics("0\n404\n{\"error\":\"not found\"}\n")
        self.assertIn("AGG=absent", out)
        self.assertIn("reason=http-404", files["metrics-status.txt"])

    def test_a_refusal_on_a_ready_serve_is_absent(self):
        rc, out, files, _ = self.run_metrics("7\n0\n", ready="yes")
        self.assertIn("AGG=absent", out)
        self.assertIn("listener-refused", files["metrics-status.txt"])

    def test_a_refusal_on_a_boot_that_never_readied_is_no_probe(self):
        rc, out, files, _ = self.run_metrics("7\n0\n", ready="no")
        self.assertIn("AGG=no_probe", out,
                      "a failed boot's refusal was reported as an absent surface")
        self.assertIn("serve-not-ready", files["metrics-status.txt"])

    def test_a_timeout_is_no_probe(self):
        rc, out, files, _ = self.run_metrics("28\n0\n")
        self.assertIn("AGG=no_probe", out)
        self.assertIn("exec-or-curl-exit-28", files["metrics-status.txt"])

    def test_no_container_is_no_probe_not_absent(self):
        rc, out, files, calls = self.run_metrics("0\n200\n", files={"head.test.ps": ""})
        self.assertIn("AGG=no_probe", out)
        self.assertIn("no-container", files["metrics-status.txt"])
        self.assertEqual(calls, [], "a probe ran with no container to run it in")

    def test_no_metrics_flag_is_absent_without_a_connection(self):
        rc, out, files, calls = self.run_metrics(
            "0\n200\n", recipe="runtime: sglang\ncommand: sglang serve --port {port}\n",
            files={"head.test.ps": CONTAINER_PS})
        self.assertIn("AGG=absent", out)
        self.assertIn("recipe-has-no-flag", files["metrics-status.txt"])
        self.assertEqual(calls, [], "an uninstrumented recipe was still probed")

    def test_no_probe_on_one_host_dominates_a_capture(self):
        rc, out, files, calls = self.run_metrics(
            "0\n200\n" + VLLM_BODY, hosts=("head.test", "rank1.test"),
            files={"head.test.ps": CONTAINER_PS, "head.test.curl": "0\n200\n" + VLLM_BODY,
                   "rank1.test.ps": "aaaabbbbcccc sparkrun_abc123_node_1\n",
                   "rank1.test.curl": "28\n0\n"})
        self.assertIn("AGG=no_probe", out, "an unreadable host hid behind another's capture")
        self.assertEqual(len(calls), 2)
        self.assertIn("host=head.test container=abc123def456", files["metrics-status.txt"])

    def test_the_scrape_never_manufactures_house_yaml(self):
        rc, out, files, _ = self.run_metrics(f"0\n200\n{VLLM_BODY}")
        self.assertNotIn("house.yaml", files,
                         "a house.yaml from the scrape would read as a finished arm")

    def test_negative_control_dropping_the_shape_check_captures_html(self):
        mutated = self.block().replace(
            "grep -qE '^# (TYPE|HELP) '", "grep -qE '.'")
        self.assertNotEqual(mutated, self.block(), "the shape check moved; control vacuous")
        rc, out, _, _ = self.run_block(
            mutated, files={"head.test.ps": CONTAINER_PS,
                            "head.test.curl": "0\n200\n<html><body>proxy</body></html>\n"})
        self.assertIn("AGG=captured", out,
                      "the shape check is not what keeps a foreign 200 out of the data")

    def test_negative_control_mapping_a_dead_boot_to_absent(self):
        mutated = self.block().replace(
            "ms=no_probe; why=serve-not-ready", "ms=absent; why=serve-not-ready")
        self.assertNotEqual(mutated, self.block(), "the mapping moved; control vacuous")
        rc, out, _, _ = self.run_block(
            mutated, ready="no",
            files={"head.test.ps": CONTAINER_PS, "head.test.curl": "7\n0\n"})
        self.assertIn("AGG=absent", out,
                      "the no_probe/absent split is not what protects a failed boot")

    def test_the_scrape_precedes_the_stop_and_follows_every_client(self):
        text = read_tool()
        at = text.index(M_START)
        self.assertLess(text.index("extra client rc="), at, "a client runs after the scrape")
        self.assertLess(at, text.index("\nstop_capture\n"), "the scrape is after stop_capture")
        self.assertLess(at, text.index('\nsparkrun stop "$TID"'), "the scrape is after the stop")


class PoolGate(ExecutedBlock):
    """The pool verdict is server-side; a client `ls` is a bounded follow-up, never a verdict.

    Live 2026-11-08: `beegfs-storage` down made every path under the pool answer `Communication
    error on send`, while the BeeGFS client only retries within `connCommRetrySecs=600` -- so a
    client-side `df`/`ls` alone would refuse a pool that is merely reconnecting
    (tools/README.md:217-226). Units and listening ports decide; the snapshot read only follows.
    """

    def block(self):
        return block_region(read_tool(), MP_START, MP_END)

    def run_pool(self, ls_fixture, units=UNITS_ACTIVE, mount=MOUNT_LINE, port=PORT_OK,
                 ip=SERVER_IP_LINE, **kwargs):
        kwargs.setdefault("recipe", MODEL_RECIPE)
        files = {"head.test.ls": ls_fixture, "head.test.units": units,
                 "head.test.mount": mount, "head.test.port": port, "head.test.ip": ip}
        files.update(kwargs.pop("files", {}))
        return self.run_block(self.block(), files=files, **kwargs)

    def test_a_present_snapshot_proceeds_and_records_both_verdicts(self):
        rc, out, files, _ = self.run_pool(POOL_PRESENT)
        self.assertEqual(rc, 0, out)
        self.assertIn("NEXT", out, "a staged snapshot did not reach the launch")
        model = files["model-preflight.txt"]
        self.assertIn(
            "models--deepseek-ai--DeepSeek-V4.1-Flash-1017/snapshots/1bae0e1088993b9b82de08f59de5be5a34e42170",
            model)
        self.assertIn("status=present", model)
        self.assertIn("entries=3", model)
        self.assertIn("view=host", model)
        self.assertIn("driver=", model, "the launch host is not recorded in the receipt")
        pool = files["pool-preflight.txt"]
        self.assertIn("status=pool-ready", pool)
        self.assertIn("beegfs-storage=active", pool)

    def test_an_absent_snapshot_refuses_at_12_naming_the_path(self):
        rc, out, files, _ = self.run_pool(POOL_ABSENT)
        self.assertEqual(rc, 12, out)
        self.assertIn("missing or empty", out)
        self.assertIn("models--deepseek-ai--DeepSeek-V4.1-Flash-1017", out)
        self.assertIn("status=absent", files["model-preflight.txt"])

    def test_an_empty_snapshot_is_not_present(self):
        """An empty `/cache` is the failure this gate exists for, and it reads as entries=0."""
        rc, out, files, _ = self.run_pool(POOL_EMPTY)
        self.assertEqual(rc, 12, out)
        self.assertIn("status=empty", files["model-preflight.txt"])

    def test_a_failed_storage_unit_refuses_at_11_from_the_server_side(self):
        rc, out, files, _ = self.run_pool(POOL_PRESENT, units=UNITS_STORAGE_FAILED)
        self.assertEqual(rc, 11, out)
        self.assertIn("unhealthy", out)
        self.assertIn("unit-beegfs-storage-failed", files["pool-preflight.txt"])
        self.assertNotIn("NEXT", out)

    def test_a_client_host_with_an_idle_mgmtd_is_pool_ready(self):
        """mgmtd/meta are a .30-only role: the five client hosts carry the package and never ran
        a server (`beegfs-meta=failed`, no metadata directory, standing since 2026-11-05). A
        healthy fleet must read pool-ready on those hosts, or no client host can ever boot."""
        rc, out, files, _ = self.run_pool(POOL_PRESENT, units=UNITS_CLIENT_IDLE, ip=CLIENT_IP_LINE)
        self.assertEqual(rc, 0, out)
        self.assertIn("NEXT", out)
        pool = files["pool-preflight.txt"]
        self.assertIn("role=client", pool)
        self.assertIn("status=pool-ready", pool)
        self.assertIn("beegfs-meta=failed-no-role", pool, "a client's idle meta unit read as a fault")
        self.assertIn("beegfs-mgmtd=inactive-no-role", pool)

    def test_the_host_that_owns_sysmgmtdhost_carries_the_unit_requirement(self):
        """Moving the mgmtd re-hosts the requirement: the mount names the server, not the host."""
        rc, out, files, _ = self.run_pool(POOL_PRESENT, units=UNITS_CLIENT_IDLE, ip=SERVER_IP_LINE)
        self.assertEqual(rc, 11, out)
        pool = files["pool-preflight.txt"]
        self.assertIn("role=mgmtd", pool)
        self.assertIn("unit-beegfs-mgmtd-inactive", pool)

    def test_negative_control_dropping_the_role_check_refuses_a_client(self):
        """The defect the role check prevents: three units required on every host."""
        mutated = self.block().replace('if [ "$role" = mgmtd ]; then', "if true; then")
        self.assertNotEqual(mutated, self.block(), "the role check moved; control vacuous")
        rc, out, _, _ = self.run_block(
            mutated, files={"head.test.ls": POOL_PRESENT, "head.test.units": UNITS_CLIENT_IDLE,
                            "head.test.mount": MOUNT_LINE, "head.test.port": PORT_OK,
                            "head.test.ip": CLIENT_IP_LINE})
        self.assertEqual(rc, 11, out)  # the role guard is what keeps a healthy client green

    def test_a_closed_mgmtd_port_refuses_at_11(self):
        rc, out, files, _ = self.run_pool(POOL_PRESENT, port=PORT_CLOSED)
        self.assertEqual(rc, 11, out)
        self.assertIn("mgmtd-port", files["pool-preflight.txt"])

    def test_a_client_ecomm_with_healthy_units_is_reconnecting_not_dead(self):
        rc, out, files, _ = self.run_pool(POOL_ECOMM, env_extra={"ARM_POOL_WAIT": "0"})
        self.assertEqual(rc, 13, out)  # a reconnecting client was refused as a dead pool
        self.assertIn("has not reconnected", out)
        self.assertNotIn("unhealthy", out)
        self.assertNotIn("missing or empty", out)
        self.assertIn("status=pool-reconnecting", files["pool-preflight.txt"])

    def test_one_failed_client_read_does_not_decide_the_verdict(self):
        """The negative control for the instrument: the retry window lets a reconnect through."""
        rc, out, files, _ = self.run_pool(
            POOL_PRESENT, env_extra={"ARM_POOL_WAIT": "2", "ARM_POOL_POLL": "0"},
            files={"head.test.ls.1": POOL_ECOMM})
        self.assertEqual(rc, 0, out)  # a single ECOMM decided the pool's state
        self.assertIn("NEXT", out)
        self.assertIn("status=present", files["model-preflight.txt"])

    def test_a_host_without_the_cluster_definition_refuses_at_14_as_a_host_fault(self):
        """A workstation has no WOPR profile: that is "not a launch host", never a model fault.

        The anonymous-cluster fallback is refused on purpose -- it fans the weights out per node
        and measures a different arm -- so off the head the correct behaviour is a loud refusal.
        """
        rc, out, files, _ = self.run_pool(POOL_PRESENT, hub=False)
        self.assertEqual(rc, 14, out)
        self.assertIn("not a launch host", out)
        self.assertIn("sparkrun cluster list", out)
        self.assertIn("head", out)
        self.assertNotIn("model path could not be resolved", out)
        self.assertNotIn("missing or empty", out)
        self.assertNotIn("NEXT", out, "the arm continued off a non-launch host")
        self.assertIn("cluster=absent", files["model-preflight.txt"])
        self.assertIn("driver=", files["model-preflight.txt"],
                      "the expected launch host is not recorded")

    def test_a_defined_cluster_without_hf_cache_is_still_a_model_path_fault(self):
        rc, out, files, _ = self.run_pool(
            POOL_PRESENT, hub_text="distribution:\n  model:\n    enabled: false\n")
        self.assertEqual(rc, 11, out)
        self.assertIn("could not be resolved", out)
        self.assertNotIn("not a launch host", out)
        self.assertIn("# hub=-", files["model-preflight.txt"])

    def test_negative_control_dropping_the_cluster_guard_falls_through_to_the_model_fault(self):
        """Without the guard a cluster-less host reads as 11 with the model-shaped message."""
        mutated = self.block().replace('if [ ! -f "$MP_CLUSTER" ]; then', "if false; then")
        self.assertNotEqual(mutated, self.block(), "the guard moved; control vacuous")
        rc, out, _, _ = self.run_block(
            mutated, recipe=MODEL_RECIPE, hub=False,
            files={"head.test.ls": POOL_PRESENT})
        self.assertEqual(rc, 11, out)
        self.assertIn("could not be resolved", out)

    def test_a_gguf_spec_drops_its_quant_suffix(self):
        rc, out, files, _ = self.run_pool(
            POOL_PRESENT, recipe="runtime: llama-cpp\nmodel: LiquidAI/d1-2B-GGUF:Q8_0\n"
                                 "model_revision: 4a181094d1b6addfaa3a0956f78e7ab2aa406a0c\n")
        self.assertEqual(rc, 0, out)
        self.assertIn("models--LiquidAI--d1-2B-GGUF/snapshots/4a181094", files["model-preflight.txt"])
        self.assertNotIn("Q8_0", files["model-preflight.txt"])

    def test_a_multi_host_lease_probes_every_host(self):
        rc, out, files, _ = self.run_pool(
            POOL_PRESENT, hosts=("head.test", "rank1.test"),
            files={"head.test.ls": POOL_PRESENT, "rank1.test.ls": POOL_PRESENT,
                   "rank1.test.units": UNITS_STORAGE_FAILED, "rank1.test.mount": MOUNT_LINE,
                   "rank1.test.port": PORT_OK})
        self.assertEqual(rc, 11, out)
        self.assertIn("rank1.test", out)
        self.assertIn("head.test role=mgmtd units=", files["pool-preflight.txt"])

    def test_the_verdict_is_not_a_df(self):
        """`df`/`ls` are client-connectivity probes; the verdict must come from units and ports."""
        block = self.block()
        self.assertIn("systemctl is-active", block, "the server side is not consulted")
        self.assertIn("socket.create_connection", block, "no listening-port check")
        self.assertNotIn("df ", block, "a df was read as a verdict")

    def test_negative_control_without_the_block_a_missing_snapshot_proceeds(self):
        self.assertIn(MP_START, read_tool(), "the gate is gone; this control would be vacuous")
        rc, out, _, _ = self.run_block("", recipe=MODEL_RECIPE)
        self.assertEqual(rc, 0, out)
        self.assertIn("NEXT", out)

    def test_the_gate_precedes_the_capture_and_the_launch(self):
        text = read_tool()
        at = text.index(MP_START)
        self.assertLess(text.index(DP_END), at, "the daemon probe must run first")
        self.assertLess(at, text.index("CAPTURE_DIR="), "the capture is armed before the gate")
        self.assertLess(at, text.index("\nlaunch_arm\n"), "the launch precedes the gate")


class CacheInspectGate(ExecutedBlock):
    """The executor refuses a body that is not `complete` at the pin, before it spends a boot.

    Exit 12's `ls` counts entries, and the measured Kai pin declares 36 files with 0 B present, so
    it passes that gate. `model-cache inspect` is the declared-vs-present verdict; the policy that
    keeps it from blocking every arm: only `unverified` (no saved manifest yet) gets the warn and
    proceed path, and `ARM_REQUIRE_COMPLETE_BODY=1` turns that into a refusal too.
    """

    PRELUDE = ("MP_MODEL=deepseek-ai/DeepSeek-V4.1-Flash-1017\n"
               "MP_REV=1bae0e1088993b9b82de08f59de5be5a34e42170\n"
               "MP_PATH=/fake/pool/huggingface/hub/models--x--y/snapshots/1bae0e10\n")
    COMPLETE = ("0\nHosts: 1 host(s) (--hosts)\n"
                "HOST       STATUS    LEVEL     FILES  DETAIL\n"
                "head.test  complete  metadata  84\n")
    INCOMPLETE = ("1\nHosts: 1 host(s) (--hosts)\n"
                  "HOST       STATUS      LEVEL     FILES  DETAIL\n"
                  "head.test  incomplete  metadata  36\n"
                  "head.test: 36 problem file(s)\n.gitattributes: missing\n")
    UNVERIFIED = ("1\nHosts: 1 host(s) (--hosts)\n"
                  "HOST       STATUS      LEVEL     FILES  DETAIL\n"
                  "head.test  unverified  metadata  0      no saved manifest; resolve or import"
                  " authoritative inventory first\n")
    UNAVAILABLE = ("2\nHosts: 1 host(s) (--hosts)\n"
                   "HOST       STATUS     LEVEL     FILES  DETAIL\n"
                   "head.test  unavailable  metadata  0    ssh: connect to host head.test failed\n")
    RESOLVE_OFFLINE = "1\nHTTPError: 503 Service Unavailable\n"

    def block(self):
        return block_region(read_tool(), CI_START, CI_END)

    def run_gate(self, files=None, prelude=None, env_extra=None):
        return self.run_block(
            (self.PRELUDE if prelude is None else prelude) + self.block() + "\necho NEXT",
            files=files or {"cache-inspect.txt": self.COMPLETE},
            env_extra=env_extra,
        )

    def test_an_incomplete_body_refuses_at_16_and_names_the_pin(self):
        rc, out, receipt, _ = self.run_gate({"cache-inspect.txt": self.INCOMPLETE})
        self.assertEqual(rc, 16, out)
        self.assertIn("ARM REFUSED", out)
        self.assertIn("incomplete", out)
        self.assertIn("deepseek-ai/DeepSeek-V4.1-Flash-1017", out)
        self.assertIn("1bae0e1088993b9b82de08f59de5be5a34e42170", out)
        self.assertIn("checked=36", out)
        self.assertIn("missing=36", out)
        self.assertIn("nothing was launched", out)
        self.assertNotIn("NEXT", out, "the arm continued past the refusal")
        self.assertIn("status=incomplete", receipt["cache-inspect.txt"])
        self.assertIn("36 problem file(s)", receipt["cache-inspect.txt"])

    def test_an_unavailable_observation_also_refuses(self):
        rc, out, _, _ = self.run_gate({"cache-inspect.txt": self.UNAVAILABLE})
        self.assertEqual(rc, 16, out)
        self.assertIn("unavailable", out)
        self.assertNotIn("NEXT", out)

    def test_a_complete_body_proceeds_and_logs_the_file_count(self):
        rc, out, receipt, _ = self.run_gate()
        self.assertEqual(rc, 0, out)
        self.assertIn("NEXT", out, "a complete body did not reach the launch")
        self.assertIn("cache-inspect: complete", out)
        self.assertIn("checked=84", out)
        self.assertIn("status=complete", receipt["cache-inspect.txt"])

    def test_unverified_resolves_once_and_proceeds_when_it_becomes_complete(self):
        rc, out, receipt, _ = self.run_gate(
            {"cache-inspect.1.txt": self.UNVERIFIED, "cache-inspect.2.txt": self.COMPLETE})
        self.assertEqual(rc, 0, out)
        self.assertIn("NEXT", out)
        self.assertIn("after resolve", out)
        log = receipt["cache-inspect.txt"]
        self.assertIn("### resolve", log)
        self.assertIn("status=unverified", log)
        self.assertIn("status=complete", log)

    def test_unverified_that_stays_unverified_warns_and_proceeds(self):
        rc, out, receipt, _ = self.run_gate(
            {"cache-inspect.txt": self.UNVERIFIED, "resolve.txt": self.RESOLVE_OFFLINE})
        self.assertEqual(rc, 0, out)
        self.assertIn("NEXT", out, "a manifest-less body must not block the boot")
        self.assertIn("WARN", out)
        self.assertIn("ARM_REQUIRE_COMPLETE_BODY=1", out, "the escape is not named")
        log = receipt["cache-inspect.txt"]
        self.assertIn("no saved manifest", log)
        self.assertIn("proceeding unverified", log)

    def test_the_escape_makes_unverified_a_refusal(self):
        rc, out, _, _ = self.run_gate(
            {"cache-inspect.txt": self.UNVERIFIED, "resolve.txt": self.RESOLVE_OFFLINE},
            env_extra={"ARM_REQUIRE_COMPLETE_BODY": "1"})
        self.assertEqual(rc, 16, out)
        self.assertIn("unverified", out)
        self.assertIn("nothing was launched", out)
        self.assertNotIn("NEXT", out)

    def test_no_revision_pin_skips_the_gate_rather_than_reading_main(self):
        rc, out, receipt, _ = self.run_gate(
            prelude=self.PRELUDE.replace(
                "MP_REV=1bae0e1088993b9b82de08f59de5be5a34e42170", "MP_REV="))
        self.assertEqual(rc, 0, out)
        self.assertIn("NEXT", out)
        self.assertIn("status=skipped", receipt["cache-inspect.txt"])

    def test_the_gate_precedes_the_capture_and_the_launch(self):
        text = read_tool()
        at = text.index(CI_START)
        self.assertLess(text.index(MP_END), at, "the inspect gate must follow the model path gate")
        self.assertLess(at, text.index("CAPTURE_DIR="), "the capture is armed before the gate")
        self.assertLess(at, text.index("\nlaunch_arm\n"), "the launch precedes the gate")

    def test_negative_control_without_the_block_an_incomplete_body_proceeds(self):
        self.assertIn(CI_START, read_tool(), "the gate is gone; this control would be vacuous")
        rc, out, _, _ = self.run_block(self.PRELUDE + "\necho NEXT",
                                       files={"cache-inspect.txt": self.INCOMPLETE})
        self.assertEqual(rc, 0, out)
        self.assertIn("NEXT", out)


class NativePerRankLogs(ExecutedBlock):
    """The receipt gets the workload's own per-rank serve logs, split one file per host.

    `sparkrun logs <cluster-id> -a` reads `/tmp/sparkrun_serve.log` on the head and every rank
    (`core/log_source.py:35`) and prefixes each line `[host/role] `, which is the only per-host
    split the CLI offers. Retrieval must never change the arm's rc: an `ssh` or reader failure is
    recorded with the fallback the receipt already holds.
    """

    HOSTS = ("node-a", "node-b", "node-c", "node-d")
    FOUR = ("0\n"
            "[node-a/solo] engine started\n[node-a/solo] ready in 273 s\n"
            "[node-b/node_1] rank 1 loading\n[node-b/node_1] rank 1 ready\n"
            "[node-c/node_2] rank 2 loading\n"
            "[node-d/node_3] rank 3 loading\n")
    THREE = ("0\n"
             "[node-a/solo] engine started\n"
             "[node-b/node_1] rank 1 loading\n"
             "[node-c/node_2] rank 2 loading\n")
    FAILED = "1\nError: No running workload found for cluster 'abc123'\n"

    def block(self):
        return block_region(read_tool(), NL_START, NL_END)

    def run_logs(self, fixture, receipt_extra=None, hosts=None):
        return self.run_block(
            "rc=0\n" + self.block() + "\necho AFTER rc=$rc",
            hosts=hosts or self.HOSTS,
            files={"logs.txt": fixture},
            receipt_extra=receipt_extra,
        )

    def test_every_rank_writes_its_own_file_with_the_prefix_stripped(self):
        rc, out, receipt, _ = self.run_logs(self.FOUR)
        self.assertEqual(rc, 0, out)
        self.assertIn("AFTER rc=0", out)
        self.assertEqual(receipt["logs/node-a-serve.log"], "engine started\nready in 273 s\n")
        self.assertEqual(receipt["logs/node-b-serve.log"], "rank 1 loading\nrank 1 ready\n")
        self.assertIn("rank 2 loading", receipt["logs/node-c-serve.log"])
        self.assertNotIn("[node-c/node_2]", receipt["logs/node-c-serve.log"],
                         "the label prefix leaked into the per-rank file")
        status = receipt["native-logs-status.txt"]
        for host in self.HOSTS:
            self.assertRegex(status, rf"{host} lines=[1-9][0-9]* bytes=[1-9][0-9]*")
        self.assertNotIn("missing-rank", status)

    def test_the_receipt_records_the_command_and_its_version(self):
        _, _, receipt, _ = self.run_logs(self.FOUR)
        cmd = receipt["native-logs-command.txt"]
        self.assertIn("command=sparkrun logs abc123 -a -H node-a,node-b,node-c,node-d", cmd)
        self.assertIn("--cluster WOPR", cmd)
        self.assertIn("version=0.4.3-alpha+gstub", cmd)
        self.assertIn("rc=0", cmd)

    def test_a_missing_rank_is_named_and_the_rc_is_untouched(self):
        rc, out, receipt, _ = self.run_logs(
            self.THREE, receipt_extra={"docker-node_3.log": "# capture: die exit=1\n"})
        self.assertEqual(rc, 0, out)
        self.assertIn("AFTER rc=0", out, "a missing rank changed the arm's status")
        self.assertIn("node-d", out, "the missing rank is not named in the output")
        self.assertIn("missing-rank node-d", receipt["native-logs-status.txt"])
        self.assertIn("fallback=docker-node_3.log", receipt["native-logs-status.txt"])

    def test_a_failed_reader_is_recorded_with_its_fallback_and_never_refuses(self):
        rc, out, receipt, _ = self.run_logs(self.FAILED)
        self.assertEqual(rc, 0, out)
        self.assertIn("AFTER rc=0", out, "a failed log read blocked the arm")
        status = receipt["native-logs-status.txt"]
        self.assertIn("failed rc=1", status)
        self.assertIn("No running workload", receipt["native-logs.raw"],
                      "the reader's own output is not kept beside the failure")
        self.assertIn("fallback=none", status)
        self.assertNotIn("logs/native-unattributed.log", receipt,
                         "an error line was filed as serve output")

    def test_the_exit_capture_is_still_the_stdout_and_oom_mechanism(self):
        text = read_tool()
        self.assertIn("tools/engine-exit-capture.sh", text)
        self.assertIn('docker-$rank.log', text, "the capture merge was removed")

    def test_the_native_harvest_runs_before_the_stop(self):
        text = read_tool()
        at = text.index(NL_START)
        self.assertLess(at, text.index("\nstop_capture\n"), "the containers are gone before the read")
        self.assertLess(at, text.index('\nsparkrun stop "$TID"'), "the read runs after the stop")
        self.assertGreater(at, text.index("CAPTURE_DIR="), "the capture must be armed first")

    def test_negative_control_without_the_block_no_rank_files_appear(self):
        self.assertIn(NL_START, read_tool(), "the block is gone; this control would be vacuous")
        rc, out, receipt, _ = self.run_block("rc=0\necho AFTER rc=$rc",
                                             hosts=self.HOSTS,
                                             files={"logs.txt": self.FOUR})
        self.assertEqual(rc, 0, out)
        self.assertIn("AFTER rc=0", out)
        self.assertFalse(any(name.startswith("logs/") for name in receipt),
                         "the prelude wrote a rank log without the block")


class OomWatchdog(ExecutedBlock):
    """An earlyoom kill is a SIGTERM: exit 143, no traceback, and no trace in the receipt.

    The field is the whole contract (`earlyoom-terminated` / `clean` / `unknown`), and the failure
    this class exists for is a default to `clean`: the engine then reads as having died for its own
    reasons and the next fit verdict blames it. Every case below asserts the evidence line as well
    as the label, because a label with no line is suspicion.
    """

    EARLYOOM = ('earlyoom: low memory! sending SIGTERM to process 4242 uid 1000 '
                'pdeath_signal=0 "python3"')
    DIE_143 = "# capture: die exit=143\n"

    def block(self):
        return block_region(read_tool(), OOM_START, OOM_END) + "\noom_watchdog_check"

    def run_oom(self, journal="0\n", exits=DIE_143, house=True, hosts=("head.test",), files=None):
        extra = dict(files or {})
        for host in hosts:
            if journal is not None:
                extra[f"{host}.journal"] = journal
        return self.run_block(
            self.block(), hosts=hosts, files=extra, house=house,
            receipt_extra={"docker-rank0.log": exits},
            env_extra={"OOM_SINCE": "1762613000"})

    def test_an_earlyoom_line_in_the_window_is_named_and_quoted(self):
        rc, out, files, _ = self.run_oom(journal=f"0\n{self.EARLYOOM}\n", house=True)
        self.assertEqual(rc, 0, out)
        self.assertIn("oom_watchdog=earlyoom-terminated", files["oom-watchdog.txt"])
        self.assertIn(self.EARLYOOM, files["oom-watchdog.txt"], "the line is not quoted verbatim")
        self.assertIn("oom_watchdog: earlyoom-terminated", files["house.yaml"])
        self.assertIn("head.test exit=143 journal=ok line=", files["oom-watchdog.txt"])

    def test_a_clean_exit_with_a_readable_journal_and_an_artifact_is_clean(self):
        rc, out, files, _ = self.run_oom(journal="0\n", exits="# capture: die exit=0\n", house=True)
        self.assertEqual(rc, 0, out)
        self.assertIn("oom_watchdog=clean", files["oom-watchdog.txt"])
        self.assertIn("oom_watchdog: clean", files["house.yaml"])

    def test_143_without_an_earlyoom_line_is_unknown_not_clean(self):
        rc, out, files, _ = self.run_oom(journal="0\n", house=True)
        self.assertEqual(rc, 0, out)
        self.assertIn("oom_watchdog=unknown", files["oom-watchdog.txt"])
        self.assertIn("oom_watchdog: unknown", files["house.yaml"])
        self.assertNotIn("oom_watchdog=clean", files["oom-watchdog.txt"])

    def test_137_with_an_unreadable_journal_is_unknown(self):
        rc, out, files, _ = self.run_oom(
            journal=None, exits="# capture: die exit=137\n", house=True)
        self.assertEqual(rc, 0, out)
        self.assertIn("oom_watchdog=unknown", files["oom-watchdog.txt"])
        self.assertIn("head.test exit=137 journal=unreadable line=-", files["oom-watchdog.txt"])

    def test_a_missing_result_artifact_is_unknown_even_on_a_clean_exit(self):
        rc, out, files, _ = self.run_oom(journal="0\n", exits="# capture: die exit=0\n", house=False)
        self.assertEqual(rc, 0, out)
        self.assertIn("oom_watchdog=unknown", files["oom-watchdog.txt"])
        self.assertNotIn("oom_watchdog=clean", files["oom-watchdog.txt"])

    #: A container `--memory` kill: the cgroup SIGKILLs the serve under PID 1 `sleep infinity`,
    #: so the container survives and exits 0 — measured on `.35` 2026-11-10 (`oom` before
    #: `die exit=0`, container `status=running oom=true`), which is why the exit code alone
    #: cannot name this death.
    OOM_THEN_DIE = ("# capture: create deadbeef sparkrun_t1_node_0\n"
                    "boom\n"
                    "# capture: oom deadbeef sparkrun_t1_node_0\n"
                    "# capture: die exit=0\n")

    def test_a_capped_container_with_no_artifact_is_named_cgroup_oom(self):
        rc, out, files, _ = self.run_oom(journal="0\n", exits=self.OOM_THEN_DIE, house=False)
        self.assertEqual(rc, 0, out)
        self.assertIn("oom_watchdog=cgroup-oom", files["oom-watchdog.txt"])
        self.assertIn("cgroup_oom=sparkrun_t1_node_0", files["oom-watchdog.txt"],
                      "the verdict does not name the capped container")
        self.assertIn("evidence=oom sparkrun_t1_node_0", files["oom-watchdog.txt"])
        self.assertNotIn("oom_watchdog=clean", files["oom-watchdog.txt"])

    def test_a_137_without_an_oom_event_is_still_unknown(self):
        """The false positive this branch must not introduce: 137 alone names no killer."""
        rc, out, files, _ = self.run_oom(journal="0\n", exits="# capture: die exit=137\n", house=False)
        self.assertEqual(rc, 0, out)
        self.assertIn("oom_watchdog=unknown", files["oom-watchdog.txt"])
        self.assertIn("cgroup_oom=-", files["oom-watchdog.txt"],
                      "a die-only capture manufactured a cgroup fact")

    def test_an_oom_on_an_arm_that_measured_keeps_the_fact_and_stays_clean(self):
        """A capped child on a serve that still delivered: the fact survives, the verdict does not."""
        rc, out, files, _ = self.run_oom(journal="0\n", exits=self.OOM_THEN_DIE, house=True)
        self.assertEqual(rc, 0, out)
        self.assertIn("oom_watchdog=clean", files["oom-watchdog.txt"])
        self.assertIn("cgroup_oom=sparkrun_t1_node_0", files["oom-watchdog.txt"],
                      "the capped-child fact was dropped with the verdict")

    def test_an_unreadable_journal_never_becomes_a_cgroup_verdict(self):
        rc, out, files, _ = self.run_oom(journal=None, exits=self.OOM_THEN_DIE, house=False)
        self.assertEqual(rc, 0, out)
        self.assertIn("oom_watchdog=unknown", files["oom-watchdog.txt"])
        self.assertIn("unread=1", files["oom-watchdog.txt"])

    def test_negative_control_dropping_the_oom_read_loses_the_cgroup_verdict(self):
        mutated = self.block().replace(
            "sed -n 's/^# capture: oom [^ ]* \\(.*\\)$/\\1/p'", "sed -n 's/^$//'")
        self.assertNotIn("# capture: oom", mutated, "the oom read survived the mutation")
        self.assertNotEqual(mutated, self.block(), "the reader moved; this control is vacuous")
        rc, out, files, _ = self.run_block(
            mutated, hosts=("head.test",), house=False,
            files={"head.test.journal": "0\n"},
            receipt_extra={"docker-rank0.log": self.OOM_THEN_DIE},
            env_extra={"OOM_SINCE": "1762613000"})
        self.assertEqual(rc, 0, out)
        self.assertNotIn("oom_watchdog=cgroup-oom", files["oom-watchdog.txt"],
                         "the mutation kept the verdict; the control is void")
        self.assertIn("cgroup_oom=-", files["oom-watchdog.txt"])

    def test_negative_control_ignoring_the_journal_reads_a_kill_as_clean(self):
        """The defect the field exists for: 143 + an earlyoom line, recorded as a clean death."""
        mutated = self.block().replace('if [ -n "$line" ]; then', "if false; then")
        at = mutated.index("*,137,*|*,143,*)")
        mutated = mutated[:at] + mutated[mutated.index("\n", at) + 1:]
        self.assertNotIn("*,137,*|*,143,*)", mutated, "the defect arm survived the mutation")
        self.assertNotEqual(mutated, self.block(), "the classifier moved; this control is vacuous")
        rc, out, files, _ = self.run_block(
            mutated, hosts=("head.test",),
            files={"head.test.journal": f"0\n{self.EARLYOOM}\n"}, house=True,
            receipt_extra={"docker-rank0.log": self.DIE_143},
            env_extra={"OOM_SINCE": "1762613000"})
        self.assertEqual(rc, 0, out)
        self.assertIn("oom_watchdog=clean", files["oom-watchdog.txt"],
                      "the mutation did not reproduce a clean read")

    def test_the_check_runs_in_the_exit_trap_and_before_it_on_the_early_exits(self):
        text = read_tool()
        self.assertIn("oom_watchdog_check; stop_capture", text, "the trap does not record the death")
        # The trap now precedes the appearance loop (an abandoned launch must not outlive the
        # executor), so the fail-fast `exit 5` is covered by it rather than running before it.
        self.assertLess(text.index("trap 'oom_watchdog_check"),
                        text.index("APPEAR_TIMEOUT=${ARM_CONTAINER_APPEAR_TIMEOUT"),
                        "the trap is installed after the appearance loop")
        self.assertLess(text.index("trap 'oom_watchdog_check"),
                        text.index("kill -0 \"$LAUNCH\" 2>/dev/null; then"),
                        "the appearance fail-fast runs before the stop path exists")
        self.assertIn('kill "$LAUNCH" 2>/dev/null', text, "the trap never kills the launcher")

    # -- the appearance window: it follows the launcher, not a fixed 300 s --------------------
    APPEAR_START = "APPEAR_TIMEOUT=${ARM_CONTAINER_APPEAR_TIMEOUT"
    APPEAR_END = '\n  sleep "$APPEAR_POLL"\ndone\n'

    def appear_block(self) -> str:
        text = read_tool()
        start = text.index(self.APPEAR_START)
        return text[start:text.index(self.APPEAR_END, start) + len(self.APPEAR_END)]

    def run_appear(self, env_extra=None, launch="sleep 30 & LAUNCH=$!", files=None):
        body = (
            'on_node() { ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$NODE" "$1"; }\n'
            "oom_watchdog_check() { :; }\n"
            f"{launch}\n"
            + self.appear_block()
            + '\necho "seen=$N"\n'
        )
        return self.run_block(body, files=files or {}, env_extra=env_extra,
                              receipt_extra={"launch.log": "launcher output\n"})

    def test_a_slow_launcher_is_not_failed_before_the_ceiling(self):
        rc, out, _, _ = self.run_appear(
            {"ARM_CONTAINER_APPEAR_TIMEOUT": "2", "ARM_APPEAR_POLL": "0"})
        self.assertEqual(rc, 1, out)
        self.assertIn("after 2s (ceiling 2s", out, "the failure does not name the wait and ceiling")
        self.assertIn("ARM_CONTAINER_APPEAR_TIMEOUT", out, "the knob is not named")
        self.assertIn("launcher was still running, killing it", out)
        self.assertNotIn("launcher exited with no container", out, "a slow launch was read as refused")

    def test_a_gone_launcher_fails_at_once_and_names_the_wait(self):
        rc, out, _, _ = self.run_appear(
            {"ARM_CONTAINER_APPEAR_TIMEOUT": "900", "ARM_APPEAR_POLL": "0"},
            launch="LAUNCH=999999")
        self.assertEqual(rc, 5, out)
        # Seconds come from `$SECONDS`; overhead in the harness can cross a boundary and read 1.
        # The contract is "at once" (no wait), so bound it rather than pin one wall-clock value.
        self.assertRegex(out, r"launcher exited with no container after [01]s \(ceiling 900s\)",
                         "a refused launch must fail at once, not after a wait")

    def test_a_container_that_appears_ends_the_wait(self):
        rc, out, _, _ = self.run_appear(
            {"ARM_CONTAINER_APPEAR_TIMEOUT": "900", "ARM_APPEAR_POLL": "0"},
            launch="LAUNCH=999999",
            files={"head.test.ps": "sparkrun_abc123_solo\n"})
        self.assertEqual(rc, 0, out)
        self.assertIn("seen=sparkrun_abc123_solo", out)

    def test_the_default_ceiling_covers_a_multi_rank_body(self):
        self.assertIn("ARM_CONTAINER_APPEAR_TIMEOUT:-900", read_tool(),
                      "the default window is below the measured 340 s pair distribution")

    def test_negative_control_without_the_ceiling_the_wait_does_not_end(self):
        """Removing the ceiling check leaves the old fixed-clock wait: the run hangs past it."""
        block = self.appear_block()
        mutated = block.replace(
            'if [ "$waited" -ge "$APPEAR_TIMEOUT" ]; then',
            'if [ "$waited" -ge 999999 ]; then')
        self.assertNotEqual(mutated, block, "the ceiling moved; this control is vacuous")
        body = (
            'on_node() { ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$NODE" "$1"; }\n'
            "oom_watchdog_check() { :; }\n"
            "LAUNCH=$$\n"
            + mutated
        )
        with self.assertRaises(subprocess.TimeoutExpired):
            self.run_block(body, env_extra={"ARM_APPEAR_POLL": "0.05"}, timeout=2)

    # -- the harvest count: it reports what the receipt holds ---------------------------------
    HARVEST_START = "# harvest-report: start"
    HARVEST_END = "# harvest-report: end"

    def harvest_block(self) -> str:
        text = read_tool()
        start = text.index(self.HARVEST_START)
        return text[start:text.index(self.HARVEST_END, start)]

    def test_a_reaped_only_arm_reports_one_not_zero(self):
        rc, out, _, _ = self.run_block("harvested=0\n" + self.harvest_block(), receipt_extra={
            "serve-reaped-sparkrun_abc_node_0.log": "Traceback: boom\n"})
        self.assertEqual(rc, 0, out)
        self.assertIn("serve log: serve-reaped-sparkrun_abc_node_0.log (reaped by the watchdog)", out)
        self.assertIn("receipt holds 0 live and 1 reaped serve log(s)", out)

    def test_live_and_reaped_logs_are_counted_apart(self):
        rc, out, _, _ = self.run_block("harvested=1\n" + self.harvest_block(), receipt_extra={
            "serve-0.log": "live\n",
            "serve-reaped-sparkrun_abc_node_0.log": "reaped\n"})
        self.assertEqual(rc, 0, out)
        self.assertIn("receipt holds 1 live and 1 reaped serve log(s)", out)
        self.assertIn("serve log: serve-0.log (harvested)", out)

    def test_negative_control_the_old_counter_never_names_the_reaped_log(self):
        """Pre-fix text: one number from the copy loop, so the one surviving log is invisible."""
        old = ('harvested=0\n'
               'echo "serve logs harvested: $harvested (expected one per running rank; 0 means the log was gone)"\n')
        rc, out, _, _ = self.run_block(old, receipt_extra={
            "serve-reaped-sparkrun_abc_node_0.log": "Traceback: boom\n"})
        self.assertEqual(rc, 0, out)
        self.assertNotIn("serve-reaped", out, "the old counter named the log; this control is void")


class WatchdogVerdict(ExecutedBlock):
    """`rc=3` covers two verdicts, and the receipt must carry the watchdog's own word.

    Measured 2026-11-11 (753B attempt 5): `watchdog.log` read
    `WATCHDOG t=2532s verdict=stalled …` and the arm receipt said "serve dead and stopped",
    so a frozen instrument was filed as an engine death.
    """

    CASE_START = 'case "$wd_rc" in'

    def case_block(self) -> str:
        text = read_tool()
        start = text.index(self.CASE_START)
        return text[start:text.index("    esac\n", start) + len("    esac\n")]

    def run_verdict(self, log: str, rc: int = 3, block: str | None = None):
        body = (f"ready=no\nwd_rc={rc}\nfor _ in 1; do\n"
                + (block or self.case_block()) + 'done\necho "ready=$ready"\n')
        return self.run_block(body, receipt_extra={"watchdog.log": log})

    def test_a_stall_is_not_filed_as_a_death(self):
        rc, out, files, _ = self.run_verdict(
            "WATCHDOG t=2532s verdict=stalled endpoint=down serve_pid=alive io_delta=0\n")
        self.assertEqual(rc, 0, out)
        self.assertIn("serve stalled and stopped (rc=3)", out)
        self.assertNotIn("serve dead", out, "a stall was filed as a death")
        self.assertEqual(files["watchdog-verdict.txt"].split()[0], "verdict=stalled")

    def test_a_death_still_reads_as_a_death(self):
        _rc, out, files, _ = self.run_verdict(
            "WATCHDOG t=120s verdict=dead endpoint=down serve_pid=gone\n")
        self.assertIn("serve dead and stopped (rc=3)", out)
        self.assertEqual(files["watchdog-verdict.txt"].split()[0], "verdict=dead")

    def test_an_unreadable_log_is_unknown_not_a_death(self):
        _rc, out, files, _ = self.run_verdict("")
        self.assertIn("serve unknown and stopped", out)
        self.assertEqual(files["watchdog-verdict.txt"].split()[0], "verdict=unknown")

    def test_negative_control_hardcoding_dead_reproduces_the_defect(self):
        block = self.case_block()
        mutated = block.replace("wd_verdict=${wd_verdict:-unknown}", "wd_verdict=dead")
        self.assertNotEqual(mutated, block, "the verdict read moved; this control is vacuous")
        _rc, out, _files, _ = self.run_verdict(
            "WATCHDOG t=2532s verdict=stalled endpoint=down\n", block=mutated)
        self.assertIn("serve dead", out, "the mutation did not reproduce the defect")


GOOD_GUARD = (
    "#!/bin/sh\n"
    'printf "%s\\n" "$*" >> "$GUARD_ARGV"\n'
    'printf "%s\\n" "guard start tid=$1 start_epoch=$(date +%s)" >> "$TP4_DIR/mem-guard.log"\n'
    "exec sleep 30\n"
)
STALE_GUARD = (
    "#!/bin/sh\n"
    'printf "%s\\n" "$*" >> "$GUARD_ARGV"\n'
    'printf "%s\\n" "guard start tid=task_older start_epoch=$(date +%s)" >> "$TP4_DIR/mem-guard.log"\n'
    "exec sleep 30\n"
)


class WindowGuard(unittest.TestCase):
    """A declared window arms its mem-guard and samplers before the first readiness sample.

    The guard, not a measured sampler, is what stops a risky boot (owner ruling 2026-11-11), so
    the executor proves it started the window's own script for the task id it resolved. These run
    the real block against stub `ssh`/`sparkrun` and a stub guard; no fleet, no boot.
    """

    def run_guard(self, *, window: str = "win", body: str | None = GOOD_GUARD,
                  executable: bool = True, wait: str = "3",
                  trailer: str = "stop_guard"):
        """Execute the arming block with a fake window; return rc, output, receipt, logs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            home = tmp / "home"
            window_dir = home / "benchmarks" / "win"
            window_dir.mkdir(parents=True)
            if body is not None:
                guard = window_dir / "mem-guard.sh"
                guard.write_text(body)
                guard.chmod(0o755 if executable else 0o644)
            receipt = tmp / "receipt"
            receipt.mkdir()
            bins = tmp / "bin"
            bins.mkdir()
            sparkrun = bins / "sparkrun"
            sparkrun.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "$SPARKRUN_LOG"\n')
            sparkrun.chmod(0o755)
            ssh = bins / "ssh"
            ssh.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$*" >> "$SSH_LOG"\ncat >> "$SSH_STDIN"\n'
                'printf "node pid=999 rows=0 last_avail_kB=100\\n"\n'
            )
            ssh.chmod(0o755)
            script = tmp / "guard.sh"
            script.write_text(
                "#!/usr/bin/env bash\nset -uo pipefail\n"
                f"HOME={home}\nL={receipt}\nHOSTS=node-a,node-b\nTID=task_123\nNAME=test\n"
                f"ARM_WINDOW={window!r}\nARM_GUARD_WAIT={wait!r}\n"
                f"PATH={bins}:$PATH\nexport PATH\n"
                + guard_slice(read_tool()) + "\n"
                'echo "guard_pid=${GUARD_PID:-}"\n' + trailer + "\n"
            )
            env = {
                **os.environ,
                "GUARD_ARGV": str(tmp / "guard-argv"),
                "SSH_LOG": str(tmp / "ssh.log"),
                "SSH_STDIN": str(tmp / "ssh.stdin"),
                "SPARKRUN_LOG": str(tmp / "sparkrun.log"),
            }
            out = subprocess.run(["bash", str(script)], capture_output=True, text=True,
                                 check=False, env=env, timeout=60)
            match = re.search(r"^guard_pid=(\d*)$", out.stdout, re.M)
            pid = int(match.group(1)) if match and match.group(1) else 0
            files = {path.name: path.read_text(errors="replace") for path in receipt.iterdir()}
            logs = {}
            for key, name in (("guard_argv", "guard-argv"), ("ssh", "ssh.log"),
                              ("ssh_stdin", "ssh.stdin"), ("sparkrun", "sparkrun.log")):
                path = tmp / name
                logs[key] = path.read_text(errors="replace") if path.exists() else ""
        # The stub guard sleeps 30 s; a live pid after the script exited means teardown missed it.
        logs["pid"] = str(pid)
        logs["alive"] = str(bool(pid) and Path(f"/proc/{pid}").exists())
        return out.returncode, out.stdout + out.stderr, files, logs

    def test_the_declared_window_arms_its_guard_with_the_resolved_task_id(self):
        rc, out, files, logs = self.run_guard()
        self.assertEqual(rc, 0, out)
        self.assertEqual(logs["guard_argv"].split(), ["task_123"],
                         "the guard must be invoked with the task id, not a recipe or node")
        cell = files["guard-armed.txt"]
        self.assertIn("state=armed", cell)
        self.assertIn("tid=task_123", cell)
        self.assertIn("guard_line=guard start tid=task_123", cell,
                      "the guard's own line is the proof, not the pid alone")
        self.assertRegex(cell, r"(?m)^start_utc=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertTrue(files["mem-guard.pid"].split()[0].isdigit())
        self.assertIn('TP4_TID="$TID"', logs["ssh_stdin"],
                      "the sampler must get the window's env names")
        self.assertIn("mem-sampler.sh", logs["ssh_stdin"])
        self.assertIn("task_123", logs["ssh"], "a sampler was armed without the task id")
        self.assertEqual(logs["alive"], "False", "teardown left the guard running")

    def test_a_missing_script_refuses_with_exit_15_and_stops_the_task_by_name(self):
        rc, out, files, logs = self.run_guard(body=None)
        self.assertEqual(rc, 15, out)
        self.assertIn("stop task_123", logs["sparkrun"])
        self.assertIn("state=not-armed", files["guard-armed.txt"])
        self.assertIn("script missing or not executable", files["guard-armed.txt"])
        self.assertIn("no readiness or benchmark step", out)

    def test_a_non_executable_script_is_not_armed(self):
        rc, out, files, logs = self.run_guard(executable=False)
        self.assertEqual(rc, 15, out)
        self.assertIn("stop task_123", logs["sparkrun"])
        self.assertIn("state=not-armed", files["guard-armed.txt"])

    def test_a_guard_line_for_another_task_is_not_proof(self):
        rc, out, files, _ = self.run_guard(body=STALE_GUARD)
        self.assertEqual(rc, 15, out)
        self.assertIn("no guard start line for tid=task_123", files["guard-armed.txt"])

    def test_a_spawn_that_dies_before_its_line_refuses(self):
        rc, out, files, _ = self.run_guard(body="#!/bin/sh\nexit 1\n")
        self.assertEqual(rc, 15, out)
        self.assertIn("state=not-armed", files["guard-armed.txt"])

    def test_an_arm_without_a_window_is_exactly_the_old_executor(self):
        rc, out, files, logs = self.run_guard(window="")
        self.assertEqual(rc, 0, out)
        self.assertEqual(files, {}, "an undeclared window must write no guard cell")
        self.assertEqual(logs["ssh"], "")
        self.assertEqual(logs["sparkrun"], "")

    def test_arming_sits_between_the_task_id_and_the_readiness_loop(self):
        text = read_tool()
        tid_at = text.index("printf '%s\\n' \"$TID\" > \"$L/task-id.txt\"")
        guard_at = text.index(GUARD_START)
        self.assertLess(tid_at, guard_at, "the guard is armed before the task id exists")
        self.assertLess(guard_at, text.index(LOOP_START),
                        "a readiness sample taken before the guard is armed")

    def test_the_exit_trap_kills_the_guard_after_the_task_stop(self):
        text = read_tool()
        body = TRAP_RE.search(text).group(0)
        self.assertLess(body.index('sparkrun stop "$TID"'), body.index("stop_guard"),
                        "a guard can outlive the task it was armed for")
        # The trap calls the helper, so the teardown it names is the teardown that runs.
        start = text.index("stop_guard() {")
        helper = text[start:text.index("\n}\n", start)]
        self.assertLess(helper.index('kill "$GUARD_PID"'), helper.index("stop_samplers"),
                        "the guard stops reading before its samplers do, so a stale trigger has no reader")

    def test_a_guard_that_dies_after_arming_is_caught(self):
        trailer = (
            'kill "$GUARD_PID" 2>/dev/null || true; n=0; '
            'while [ "$n" -lt 50 ]; do '
            'state=$(ps -o stat= -p "$GUARD_PID" 2>/dev/null || true); '
            'case "$state" in Z*) break ;; esac; sleep 0.05; n=$((n + 1)); done; '
            "guard_lost; echo survived"
        )
        rc, out, files, logs = self.run_guard(trailer=trailer)
        self.assertEqual(rc, 15, out)
        self.assertIn("gone mid-arm", out)
        self.assertNotIn("survived", out, "a lost guard let the arm continue")
        self.assertIn("state=lost", files["guard-lost.txt"])
        self.assertIn("tid=task_123", files["guard-lost.txt"])
        self.assertIn("stop task_123", logs["sparkrun"])

    def test_a_live_guard_passes_its_liveness_check(self):
        rc, out, files, _ = self.run_guard(trailer="guard_lost; echo survived")
        self.assertEqual(rc, 0, out)
        self.assertIn("survived", out)
        self.assertNotIn("guard-lost.txt", files)

    def test_the_readiness_loop_and_the_cell_gate_both_check_the_guard(self):
        text = read_tool()
        loop = text[text.index(LOOP_START):text.index(LOOP_END)]
        self.assertIn("guard_lost", loop, "the readiness loop cannot see a dead guard")
        self.assertLess(loop.index("guard_lost"), loop.index('sleep "$POLL_SLEEP"'),
                        "the guard is checked after the poll that the loop then trusts")
        cell = text[text.index('if [ "$ready" = yes ]; then'):]
        self.assertIn("guard_lost", cell[:cell.index("case \"$RECIPE\" in")],
                      "a benchmark cell can run under a window whose guard is gone")


class PlacementRefusalAndContainerBinding(unittest.TestCase):
    """A refusal is terminal, and the captured container is this launch's own.

    Measured 2026-11-11: `sparkrun run` refused placement (`only placed 0 of 4
    ranks`, `GPU has an existing allocation` on every host) against a peer's Kimi
    boot, and the driver went on to arm a watchdog and a mem-guard against that
    peer's `sparkrun_*_node_0` container. A stub `sparkrun`/`ssh`/`docker` runs
    the real launch+appearance slice, so the control flow is what is asserted.
    """

    START = "launch_arm() {"
    END = 'echo "arm=$NAME container=$N task=$TID port=$PORT"'

    SSH = """#!/bin/sh
last=
for a in "$@"; do last=$a; done
case "$last" in
  *"bash -s --"*) cat >/dev/null; exit 0 ;;
esac
exec /bin/sh -c "$last"
"""
    DOCKER = """#!/bin/sh
cat "$PS_FIXTURE"
[ -e "$LAUNCH_FLAG" ] && printf '%s\\n' "cccc2222dddd sparkrun_task_own_solo"
"""
    HOSTNAME = "#!/bin/sh\nexit 1\n"
    SLEEP = "#!/bin/sh\n:\n"
    SPARKRUN_REFUSE = """#!/bin/sh
printf '%s\\n' \
  'Error: cluster has insufficient free capacity for 4 node(s): Cluster cannot satisfy 4 ranks: only placed 0 of 4 ranks across 4 host(s)' \
  'node-b / GPU 0: GPU has an existing allocation; exclusive ownership prevents sharing [occupied]' \
  > "$LAUNCH_LOG"
exit 1
"""
    SPARKRUN_LAUNCH = """#!/bin/sh
: > "$LAUNCH_FLAG"
exit 0
"""

    def launch_slice(self) -> str:
        text = read_tool()
        start = text.index(self.START)
        end = text.index(self.END, start) + len(self.END)
        return text[start:end]

    def run_slice(self, mode: str) -> tuple[int, str, dict[str, str]]:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            bins = tmp / "bin"
            bins.mkdir()
            receipt = tmp / "receipt"
            receipt.mkdir()
            ps = tmp / "ps.txt"
            ps.write_text("aaaa1111bbbb sparkrun_foreign_task_solo\n")
            flag = tmp / "launched"
            launch_log = receipt / "launch.log"
            stubs = {
                "ssh": self.SSH,
                "docker": self.DOCKER,
                "hostname": self.HOSTNAME,
                "sleep": self.SLEEP,
                "sparkrun": self.SPARKRUN_REFUSE if mode == "refuse" else self.SPARKRUN_LAUNCH,
            }
            for name, body in stubs.items():
                path = bins / name
                path.write_text(body)
                path.chmod(0o755)
            script = tmp / "slice.sh"
            script.write_text(
                "#!/usr/bin/env bash\n"
                "set -uo pipefail\n"
                f"L={receipt}\nNODE=node-a\nHOSTS=node-a\nNAME=stub\nPORT=8000\n"
                "RECIPE=r.yaml\nARM_OPTS_ARR=()\n"
                + self.launch_slice()
                + "\n"
            )
            env = {
                **os.environ,
                "PATH": f"{bins}:{os.environ['PATH']}",
                "PS_FIXTURE": str(ps),
                "LAUNCH_FLAG": str(flag),
                "LAUNCH_LOG": str(launch_log),
                "ARM_CONTAINER_APPEAR_TIMEOUT": "5",
                "ARM_APPEAR_POLL": "0.01",
            }
            out = subprocess.run(
                ["bash", str(script)], capture_output=True, text=True, check=False,
                env=env, timeout=60,
            )
            files = {
                path.name: path.read_text(errors="replace")
                for path in sorted(receipt.iterdir())
            }
            return out.returncode, out.stdout + out.stderr, files

    def test_a_placement_refusal_is_terminal_and_arms_nothing(self) -> None:
        rc, out, files = self.run_slice("refuse")
        self.assertEqual(rc, 6, out)
        self.assertIn("sparkrun refused placement", out)
        self.assertIn("Nothing armed", out)
        self.assertIn("only placed 0 of 4 ranks", files.get("placement-refusal.txt", ""))
        for armed in ("watchdog.pid", "mem-guard.pid", "watchdog.log", "mem-guard.out"):
            self.assertNotIn(armed, files, f"{armed} was armed for a launch that never ran")
        self.assertNotIn("container=", out, "a refusal resolved a container it never created")

    def test_a_launch_binds_to_its_own_container_and_ignores_a_preexisting_one(self) -> None:
        rc, out, _ = self.run_slice("launch")
        self.assertEqual(rc, 0, out)
        self.assertIn("container=sparkrun_task_own_solo", out)
        self.assertNotIn("container=sparkrun_foreign_task_solo", out)
        self.assertIn("task=task", out)

    def test_the_refusal_exits_before_any_instrument_is_armed(self) -> None:
        text = read_tool()
        refusal = text.index("placement-refusal.txt")
        self.assertLess(refusal, text.index("python3 tools/boot-watchdog.py"),
                        "an instrument is armed on the path a refusal must leave")
        self.assertLess(refusal, text.index("guard-arm: start"),
                        "the window guard is armed on the path a refusal must leave")


if __name__ == "__main__":
    unittest.main()