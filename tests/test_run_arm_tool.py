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


class DockerLogCapture(unittest.TestCase):
    """A boot that dies before the engine writes its log must still leave its own stdout."""
    KILL = 'for p in ${LOGFOLLOW[@]:-}; do kill "$p" 2>/dev/null; done'
    HARVEST = 'echo "serve logs harvested:'
    STOP = 'sparkrun stop "$TID" 2>&1'
    INSPECT = "docker inspect -f 'exit={{.State.ExitCode}} oom={{.State.OOMKilled}} status={{.State.Status}}'"

    def follower_slice(self, text: str) -> str:
        start = text.index("docker logs -f")
        return text[start:text.index("python3 tools/boot-watchdog.py", start)]

    def pre_stop_slice(self, text: str) -> str:
        start = text.index(self.HARVEST)
        return text[start:text.index(self.STOP, start)]

    def test_every_rank_is_streamed_and_the_follower_is_killed_before_the_stop(self):
        text = read_tool()
        self.assertIn("docker logs -f", text, "no rank is streamed")
        self.assertLess(text.index("LOGFOLLOW=()"), text.index("docker logs -f"))
        self.assertLess(text.index("docker logs -f"), text.index(self.STOP))
        self.assertIn(self.INSPECT, self.follower_slice(text),
                      "a silent death leaves only the banner; the exit state is not captured")
        self.assertIn(self.KILL, self.pre_stop_slice(text),
                      "the follower is not killed before the stop")

    def test_removing_the_exit_state_fails_the_guard(self):
        text = read_tool().replace(self.INSPECT, "")
        self.assertNotIn(self.INSPECT, self.follower_slice(text),
                         "the exit-state inspect survived the mutation")

    SNAPSHOT = "docker logs '$c'"
    MISSED = "# capture failed:"
    FOLLOW_MARKER = "# capture: docker logs -f"

    def pre_reap_slice(self, text: str) -> str:
        """The harvest loop and everything after it, up to the stop that reaps the containers."""
        start = text.index("harvested=0")
        return text[start:text.index(self.STOP, start)]

    def test_each_rank_is_snapshotted_while_its_container_still_exists(self):
        """2026-11-08: a reaped 753B boot's `docker-10_0_4_30.log` held only "no such object".

        The live follower ends when the container does, and its last write was docker's own
        error, read as engine output. The pre-stop snapshot is the copy that survives, and a
        snapshot that fails says so in the file instead of leaving that error behind.
        """
        text = read_tool()
        pre = self.pre_reap_slice(text)
        self.assertIn(self.SNAPSHOT, pre, "no docker logs snapshot before the stop")
        self.assertIn(self.MISSED, pre, "a failed snapshot is not marked in the log")
        self.assertLess(text.index(self.SNAPSHOT), text.index(self.STOP),
                        "the snapshot runs after the container is reaped")

    def test_docker_errors_never_land_in_the_rank_log(self):
        text = read_tool()
        follower = self.follower_slice(text)
        self.assertIn('2> "$f.err"', follower, "docker's stderr is not separated from the log")
        self.assertIn(self.FOLLOW_MARKER, follower, "a failed follow is not marked in the log")

    def test_moving_the_snapshot_after_the_stop_fails_the_guard(self):
        text = read_tool()
        start = text.index("harvested=0")
        end = text.index(self.STOP, start)
        mutated = text[:start] + text[start:end].replace(self.SNAPSHOT, "", 1) + text[end:]
        mutated = mutated.replace(self.STOP, self.STOP + "\n" + self.SNAPSHOT, 1)
        self.assertNotIn(self.SNAPSHOT, self.pre_reap_slice(mutated),
                         "the guard passed a snapshot that runs after the stop")

    def test_folding_docker_stderr_back_into_the_log_fails_the_guard(self):
        mutated = read_tool().replace('2> "$f.err"', "2>&1", 1)
        self.assertNotIn('2> "$f.err"', self.follower_slice(mutated),
                         "the stderr split survived the mutation")

    def test_removing_the_pre_stop_kill_fails_the_guard(self):
        text = read_tool()
        start = text.index(self.HARVEST)
        end = text.index(self.STOP, start)
        mutated = text[:start] + text[start:end].replace(self.KILL, "", 1) + text[end:]
        self.assertNotIn(self.KILL, self.pre_stop_slice(mutated),
                         "the pre-stop kill survived the mutation")


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
    """A row-env ARM_OPTS reaches `sparkrun run` and is recorded verbatim in the receipt.

    Measured 2026-11-08: a marlin `-o extra_args=--moe-runner-backend marlin` trial produced
    numbers and nothing in the receipt named the override, because `-o` is a CLI argument and
    never container env -- `docker inspect` cannot recover it. A campaign row's `env` map reaches
    this script as environment (queue-drip and the campaign worker export it), so ARM_OPTS is the
    row's override field and its effective value is launch evidence beside image.txt.
    """

    FLAGS = "-o extra_args=--moe-runner-backend marlin"

    def run_launch(self, arm_opts: str | None) -> tuple[list[str], str, str]:
        """Run the launch block with a stub `sparkrun`, as a row env would supply ARM_OPTS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            receipt = tmp / "receipt"
            receipt.mkdir()
            bins = tmp / "bin"
            bins.mkdir()
            stub = bins / "sparkrun"
            stub.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$ARGV\"\nexit 0\n")
            stub.chmod(0o755)
            supplied = "" if arm_opts is None else f"export ARM_OPTS={arm_opts!r}"
            script = tmp / "launch.sh"
            script.write_text(
                f"""#!/usr/bin/env bash
set -uo pipefail
export ARGV={str(tmp / "argv.txt")!r}
RECIPE=recipes/lane/arm.yaml
HOSTS=node-a,node-b
L={receipt}
NAME=test
{supplied}
{override_slice(read_tool())}
wait
"""
            )
            env = {**os.environ, "PATH": f"{bins}:{os.environ['PATH']}"}
            out = subprocess.run(["bash", str(script)], capture_output=True, text=True,
                                 check=False, env=env, timeout=60)
            self.assertEqual(out.returncode, 0, out.stderr)
            argv = (tmp / "argv.txt").read_text().splitlines()
            recorded = receipt / "arm_opts.txt"
            text = recorded.read_text().strip() if recorded.is_file() else "<absent>"
            return argv, text, out.stdout + out.stderr

    def test_the_override_reaches_the_launch_and_is_recorded_verbatim(self):
        argv, recorded, out = self.run_launch(self.FLAGS)
        self.assertEqual(argv[:2], ["run", "recipes/lane/arm.yaml"], out)
        self.assertIn("extra_args=--moe-runner-backend", argv, f"the flag did not reach sparkrun: {argv}")
        self.assertEqual(argv.count("-o"), 1)
        self.assertEqual(recorded, self.FLAGS, "the receipt does not name the override that ran")

    def test_the_evidence_precedes_the_launch(self):
        text = read_tool()
        self.assertLess(text.index('> "$L/arm_opts.txt"'), text.index("\nlaunch_arm\n"),
                        "the override is recorded after the launch it describes")

    def test_negative_control_an_arm_without_overrides_launches_bare_and_records_none(self):
        argv, recorded, _out = self.run_launch(None)
        self.assertEqual(argv, ["run", "recipes/lane/arm.yaml", "-H", "node-a,node-b",
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

    def run_hook(self, env_extra: dict[str, str], house: bool = True) -> tuple[dict[str, str], str]:
        with tempfile.TemporaryDirectory() as tmpdir:
            receipt = Path(tmpdir)
            if house:
                (receipt / "house.yaml").write_text("suite: ok\nladder: ok\n")
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
                     for path in sorted(receipt.iterdir()) if path.name != "hook.sh"}
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


if __name__ == "__main__":
    unittest.main()