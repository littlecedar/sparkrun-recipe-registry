# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Guard test for the boot watchdog (the keep-alive-masks-dead-serve defect, 21e5ec6).

The decision table is the spec: endpoint 200 -> healthy; serve child alive ->
loading (a 45-min GLM weight load must classify as loading, not dead); child
gone + endpoint dead on >=2 consecutive checks -> dead. The io-delta evidence
lines are also pinned, since they are what proves a load progressing.
"""

import importlib.util
import subprocess
import sys
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "boot-watchdog.py"


def load_tool():
    """Import tools/boot-watchdog.py (dash-named, so via importlib)."""
    spec = importlib.util.spec_from_file_location("boot_watchdog", TOOL_PATH)
    assert spec and spec.loader, f"cannot load {TOOL_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules["boot_watchdog"] = module  # before exec: @dataclass / __module__
    spec.loader.exec_module(module)
    return module


bw = load_tool()

IO_BODY = "rchar: 1234567890\nwchar: 2345678901\nread_bytes: 175716135696\n"


class TestDecide(unittest.TestCase):
    def test_endpoint_200_is_healthy_even_with_child_gone(self):
        self.assertEqual(bw.decide(True, False, 1), "healthy")

    def test_child_alive_is_loading_even_when_endpoint_down(self):
        # 45-min GLM load: endpoint down, serve pid alive -> loading, NEVER dead.
        self.assertEqual(bw.decide(False, True, 1), "loading")
        self.assertEqual(bw.decide(False, True, 5), "loading")

    def test_first_dead_sighting_is_candidate_only(self):
        self.assertEqual(bw.decide(False, False, 1), "dead_candidate")

    def test_a_child_never_seen_alive_stays_a_candidate(self):
        # Changed 2026-11-03: two naked sightings used to mean `dead`. They now mean "the
        # probe has never found the child", which is also what a serve-pid fingerprint miss
        # looks like — so it stays a candidate and is timed by --dead-grace instead of
        # being stopped on a sighting that may be the instrument's fault.
        self.assertEqual(bw.decide(False, False, 2), "dead_candidate")
        self.assertEqual(bw.decide(False, False, 9), "dead_candidate")

    def test_serve_pattern_matches_plain_python_serves(self):
        # Worker ruling 2026-10-26: a serve child running as plain `python`
        # (not python3) was invisible to the pgrep pattern, so a live load read
        # as "dead_candidate" until grace expiry. `python` must be in the
        # pattern; the endpoint stays authoritative for the healthy verdict.
        self.assertIn("python", bw.SERVE_PATTERN)
        self.assertIn("python3", bw.SERVE_PATTERN)


class TestParseIo(unittest.TestCase):
    def test_full_body(self):
        self.assertEqual(bw.parse_io(IO_BODY), (1234567890, 2345678901))

    def test_missing_counters(self):
        self.assertIsNone(bw.parse_io("read_bytes: 100\n"))
        self.assertIsNone(bw.parse_io("NO-PID\n"))


class TestPickIo(unittest.TestCase):
    """The io sample must follow the reader, not the process pgrep lists first.

    A vLLM serve loads its shards in a child `EngineCore`, so taking `head -1`
    logged io_delta=0 through the whole load — the evidence line that exists to
    prove a slow load is progressing.
    """

    def test_the_reading_child_wins_over_the_parent(self):
        sample = f"PID 75\n{IO_BODY}PID 374\nrchar: 98765432100\nwchar: 100\n"
        self.assertEqual(bw.pick_io(sample), (True, (98765432100, 100)))

    def test_no_matching_process_is_not_alive(self):
        self.assertEqual(bw.pick_io(""), (False, None))

    def test_a_match_without_io_counters_is_alive_but_io_less(self):
        # pgrep found it, /proc/<pid>/io was unreadable (exited between the two):
        # alive must stay True, or a loading serve reads as gone at grace expiry.
        self.assertEqual(bw.pick_io("PID 75\n"), (True, None))
        self.assertEqual(bw.pick_io("PID 9\nrchar: 5\nPID 10\nwchar: 7\n"), (True, None))


class TestContainerResolution(unittest.TestCase):
    """A TP=1 task's container is `<prefix>_solo`, not `_node_0` (2026-10-29 defect).

    The default name made every solo boot read `serve_pid=gone` — the container
    did not exist under that name — so a slow solo load could be stopped at
    grace expiry. The node's own `docker ps` is the source.
    """

    def test_solo_container_wins_over_the_node_0_default(self):
        self.assertEqual(
            bw.pick_container(["sparkrun_7522c749bf81cc03_bd45c6067dae_solo"], "7522c749bf81cc03_bd45c6067dae"),
            "sparkrun_7522c749bf81cc03_bd45c6067dae_solo",
        )

    def test_multi_rank_rank_0_is_picked_regardless_of_listing_order(self):
        names = ["sparkrun_abc123_node_1", "sparkrun_abc123_node_0"]
        self.assertEqual(bw.pick_container(names, "abc123"), "sparkrun_abc123_node_0")

    def test_no_running_container_falls_back_to_node_0(self):
        self.assertEqual(bw.pick_container([], "abc123"), "sparkrun_abc123_node_0")

    def test_a_foreign_task_is_never_adopted(self):
        self.assertEqual(
            bw.pick_container(["sparkrun_othertask_solo"], "abc123"), "sparkrun_abc123_node_0"
        )


class TestParser(unittest.TestCase):
    def test_required_args(self):
        with self.assertRaises(SystemExit):
            bw.main(["--endpoint", "http://x:8000"])  # missing --task-id/--node


class LogGrowth(unittest.TestCase):
    """A zero io delta is ambiguous unless the serve log is sampled too.

    Measured 2026-10-29 on the sage arm: `/proc/<pid>/io` showed no reads for
    several checks while the engine was capturing CUDA graphs and logging
    progress, which reads exactly like the keep-alive-over-a-dead-serve class.
    The log size is the discriminator.
    """

    def test_a_log_size_is_parsed(self):
        self.assertEqual(bw.parse_logsize("PID 1\nLOGSIZE 4096\n"), 4096)

    def test_no_log_size_is_none(self):
        self.assertIsNone(bw.parse_logsize("PID 1\nrchar: 7\n"))

    def test_a_malformed_size_is_none(self):
        self.assertIsNone(bw.parse_logsize("LOGSIZE nope\n"))

    def test_the_log_delta_is_reported_next_to_the_io_delta(self):
        text = TOOL_PATH.read_text()
        self.assertIn("log_delta={log_delta}", text, "the log delta is not logged")
        self.assertIn("prev_rank", text, "no previous sample to diff the log size against")
        self.assertIn("LOGSIZE", text, "the sample does not ask for the log size")


class MalformedReplies(unittest.TestCase):
    """A probe must never kill the monitor.

    Measured 2026-10-30: a vLLM pooling arm answered its port with something un-HTTP,
    `urlopen` raised `http.client.BadStatusLine`, and the watchdog died -- leaving a
    live boot with no liveness evidence at all. Un-HTTP is DOWN, not fatal.
    """

    def test_a_bad_status_line_reads_as_down(self):
        import http.client
        import unittest.mock as mock

        with mock.patch("urllib.request.urlopen", side_effect=http.client.BadStatusLine("")):
            self.assertFalse(bw.http_ok("http://127.0.0.1:1/v1/models"))

    def test_a_reset_connection_reads_as_down(self):
        import unittest.mock as mock

        with mock.patch("urllib.request.urlopen", side_effect=ConnectionResetError()):
            self.assertFalse(bw.http_ok("http://127.0.0.1:1/v1/models"))


class MemorySignal(unittest.TestCase):
    """Zero io and zero log growth does not mean stalled: a 122B load shows both."""

    def test_memory_is_parsed(self):
        self.assertEqual(bw.parse_mem("MEM 8951476224\n"), 8951476224)

    def test_missing_memory_is_none(self):
        self.assertIsNone(bw.parse_mem("LOGSIZE 12\n"))

    def test_malformed_memory_is_none(self):
        self.assertIsNone(bw.parse_mem("MEM lots\n"))

    def test_the_line_carries_all_three_signals(self):
        import pathlib

        text = pathlib.Path(TOOL_PATH).read_text()
        for sig in ("io_delta={delta}", "log_delta={log_delta}", "mem_delta={mem_delta}"):
            self.assertIn(sig, text, f"{sig} missing from the check line")
        self.assertIn("/sys/fs/cgroup/memory.current", text, "memory is not sampled")


if __name__ == "__main__":
    unittest.main()

class StallIsNotLoading(unittest.TestCase):
    """A live child that reads nothing and logs nothing is stuck, and must be stopped."""

    def test_a_frozen_boot_past_grace_is_stalled(self):
        self.assertTrue(bw.is_stalled(False, True, idle=1800, stall=600))

    def test_a_silent_boot_inside_the_stall_window_is_not_stalled(self):
        # Measured 2026-11-03 over 46 healthy boots: the longest zero-io AND zero-log
        # stretch was 150 s, so 600 s is the 4x margin this test pins.
        self.assertFalse(bw.is_stalled(False, True, idle=300, stall=600))
        self.assertFalse(bw.is_stalled(False, True, idle=150, stall=600))

    def test_recent_progress_is_not_a_stall(self):
        self.assertFalse(bw.is_stalled(False, True, idle=60, stall=600))

    def test_a_dead_child_is_the_other_path(self):
        self.assertFalse(bw.is_stalled(False, False, idle=1800, stall=600))

    def test_a_healthy_endpoint_is_never_stalled(self):
        self.assertFalse(bw.is_stalled(True, True, idle=1800, stall=600))

_GONE = (False, None, 0, None, None)


def _drive(per_rank, stall="25", ranks=(), dead_grace="0"):
    """main() over per-rank serve_state returns on a fake clock that steps 10 s a call.

    `per_rank` is `{node: [samples]}` (or a bare list for the single-rank shape); each node's
    queue is consumed in call order, then repeats the gone sample. The clock step makes the
    difference visible without a 600 s wait: the fixed predicate resets the idle clock every
    check (idle 10 s < 25 s), the io+log-only one lets it accumulate (10 s, 20 s, 30 s …)
    and fires inside four samples.
    """
    calls: list[list[str]] = []

    def fake_run(argv, **_kwargs):
        calls.append(list(argv))
        # The arming check lists containers once; the fixture's container must exist, as it
        # does on the node by the time a watchdog is armed after `node0 container up`.
        if argv[0] == "ssh" and "docker ps --format" in argv[-1]:
            return mock.Mock(stdout="sparkrun_abc123_solo\n", stderr="")
        return mock.Mock(stdout="", stderr="")

    if isinstance(per_rank, list):
        per_rank = {"n1": per_rank}
    queues = {node: list(samples) for node, samples in per_rank.items()}

    def sampler(node, _ctn, _pattern):
        queue = queues.get(node, [])
        return queue.pop(0) if queue else _GONE

    class Clock:
        t = 1000.0
        step = 10.0

        def monotonic(self):
            self.t += self.step
            return self.t

        def time(self):
            return self.t

        def sleep(self, _seconds):
            pass

    tmp = Path(tempfile.mkdtemp())
    fake = mock.Mock(run=fake_run, SubprocessError=subprocess.SubprocessError)
    with (
        mock.patch.object(bw, "time", Clock()),
        mock.patch.object(bw, "subprocess", fake),
        mock.patch.object(bw, "http_ok", return_value=False),
        mock.patch.object(bw, "serve_state", side_effect=sampler),
    ):
        rc = bw.main([
            "--endpoint", "http://127.0.0.1:1",
            "--task-id", "abc123",
            "--node", "n1",
            "--container", "sparkrun_abc123_solo",
            "--interval", "0",
            "--dead-grace", dead_grace,
            "--stall", stall,
            *(f"--rank={rank}" for rank in ranks),
            "--log", str(tmp / "watchdog.log"),
        ])
    return rc, calls, (tmp / "watchdog.log").read_text()


class MemoryIsProgress(unittest.TestCase):
    """A memory-only load is progress, not a stall — twice measured, once as a false stop.

    2026-10-30: a 122B vLLM load kept `io_delta=0` and `log_delta=0` for five minutes while
    shards landed in RAM, which is why `parse_mem` exists. 2026-11-08: a 753B boot was declared
    `stalled` at t≈2532 s against a documented 2538.9 s TTR. The progress reset read io and log
    only, so the third signal was sampled, printed, and never consulted.

    The memory signal needs a floor, not a nonzero test: that boot's own series was allocator
    jitter (+548K, -598K, +1.29M, one -90M outlier), and resetting on it would mask the frozen
    boot `is_stalled` exists to catch. `MEM_PROGRESS_FLOOR` is 128 MiB: above the whole jitter
    envelope, below a real load's ~282 MB per 10 s check.
    """

    def drive(self, per_rank, stall="25", ranks=(), dead_grace="0"):
        return _drive(per_rank, stall=stall, ranks=ranks, dead_grace=dead_grace)

    GONE = (False, None, 0, None, None)
    # The 753B boot's own memory series per check: allocator jitter, not load progress.
    JITTER = (548_000, -598_000, 1_290_000, -(90 << 20))
    BASE = 8 << 30

    def loading(self, mems):
        """serve_state returns with io and log frozen, memory at `mems`, then the child gone."""
        return [(True, (100, 200), 4096, mem, None) for mem in mems] + [self.GONE] * 2

    def climbing(self):
        # GB-scale movement per check: a load, and progress even with io and log flat.
        return self.loading([self.BASE + ((k + 1) << 30) for k in range(4)])

    def jittering(self):
        mems, mem = [], self.BASE
        for delta in self.JITTER:
            mem += delta
            mems.append(mem)
        return self.loading(mems)

    def flat(self):
        return self.loading([self.BASE] * 4)

    def test_memory_past_the_floor_is_progress(self):
        self.assertTrue(bw.progressed(False, 0, 0, 1 << 30))
        self.assertTrue(bw.progressed(False, 0, 0, bw.MEM_PROGRESS_FLOOR))
        self.assertTrue(bw.progressed(False, 0, 0, -bw.MEM_PROGRESS_FLOOR))

    def test_jitter_below_the_floor_is_not_progress(self):
        for delta in self.JITTER:
            with self.subTest(delta=delta):
                self.assertFalse(bw.progressed(False, 0, 0, delta))

    def test_all_three_flat_is_not_progress(self):
        self.assertFalse(bw.progressed(False, 0, 0, 0))

    def test_negative_control_the_naive_nonzero_rule_counts_the_jitter(self):
        # Negative control for the floor itself: a bare `mem_delta != 0` would reset on every
        # one of these samples, which is the frozen-boot masking this guard exists to prevent.
        naive = lambda ok, io, log, mem: ok or io > 0 or log > 0 or mem != 0  # noqa: E731
        self.assertTrue(all(naive(False, 0, 0, d) for d in self.JITTER))
        self.assertFalse(any(bw.progressed(False, 0, 0, d) for d in self.JITTER))

    def test_a_memory_only_load_is_never_declared_stalled(self):
        rc, _calls, log = self.drive(self.climbing())
        self.assertNotIn("verdict=stalled", log, "a memory-only load was stopped as stuck")
        self.assertEqual(log.count("verdict=loading"), 4)
        self.assertIn("mem_delta=1073741824", log, "memory did not move in the samples")
        self.assertEqual(rc, 3, "the loop must still reach the observed death that follows")

    def test_jitter_does_not_reset_the_stall_clock(self):
        # Sub-floor movement while io and log are flat: the idle clock must keep climbing.
        rc, calls, log = self.drive(self.jittering())
        self.assertIn("verdict=stalled", log, "sub-floor jitter was read as load progress")
        self.assertIn(["sparkrun", "stop", "abc123"], calls)
        self.assertEqual(rc, 3)

    def test_a_flat_boot_is_stalled(self):
        _rc, _calls, log = self.drive(self.flat())
        self.assertIn("verdict=stalled", log)

    def test_a_quiet_rank_0_with_a_moving_peer_is_not_stalled(self):
        # The TP=4 shape the single-node predicate could not judge: rank 0's io and log are flat
        # and its memory only jitters, while rank 1 climbs 1 GiB per check.
        _rc, _calls, log = self.drive(
            {"n1": self.jittering(), "n2": self.climbing()},
            ranks=["n2:sparkrun_abc123_node_1"],
        )
        self.assertIn("ranks=2", log)
        self.assertIn("peer_moved=1", log, "the peer's movement was not counted as progress")
        self.assertNotIn("verdict=stalled", log, "rank 0's silence was read as a stall")

    def test_all_ranks_flat_is_stalled(self):
        _rc, _calls, log = self.drive(
            {"n1": self.flat(), "n2": self.flat()}, ranks=["n2:sparkrun_abc123_node_1"]
        )
        self.assertIn("verdict=stalled", log, "a flat group was left loading")

    def test_an_unprobeable_rank_fabricates_no_progress_and_blocks_the_stall(self):
        unprobeable = (None, None, None, None, None)
        _rc, _calls, log = self.drive(
            {"n1": self.flat(), "n2": [unprobeable] * 6}, ranks=["n2:sparkrun_abc123_node_1"]
        )
        self.assertIn("unprobeable=1", log, "the broken peer probe is not reported")
        self.assertNotIn("peer_moved=1", log, "an unprobeable rank fabricated progress")
        self.assertNotIn("verdict=stalled", log, "a no_probe rank was read as evidence of a stall")

    def test_negative_control_the_io_and_log_only_rule_stalls_the_loading_samples(self):
        # The pre-fix predicate, injected: the same GB-climbing samples stop inside four checks.
        with mock.patch.object(
            bw, "progressed", lambda ok, io, log, mem: ok or io > 0 or log > 0
        ):
            _rc, calls, log = self.drive(self.climbing())
        self.assertIn("verdict=stalled", log, "the old predicate must declare this load stalled")
        self.assertIn(["sparkrun", "stop", "abc123"], calls)


class CrashIsAnEdgeNotATimer(unittest.TestCase):
    """A serve we watched working and then lost is dead on the second observed check.

    Measured 2026-11-03: `zz-spark-x2.6-4b-int8-sglang` died at t=98 s
    (`NotImplementedError: No implemented int8_scaled_mm for current compute capability`),
    the watchdog classified it `dead` at t=123 s, printed that verdict every 30 s, and was
    forbidden to stop it until `--grace 1800` expired — 28 minutes of a blocked stream, and
    the keep-alive meant `sparkrun run` never returned either.
    """

    def test_a_child_we_watched_go_is_dead_on_the_second_sighting(self):
        # Negative control: the pre-fix rule needed the grace clock too. One sighting is
        # still a candidate (a pgrep miss across a re-exec), the second is a death.
        self.assertEqual(bw.decide(False, False, 1, seen_alive=True), "dead_candidate")
        self.assertEqual(bw.decide(False, False, 2, seen_alive=True), "dead")
        self.assertEqual(bw.decide(False, False, 2), "dead_candidate")

    def test_a_failed_probe_is_never_a_death(self):
        """The destructive case: ssh times out on a healthy, still-loading boot.

        `serve_state` returns `alive=None` for a broken instrument, and a loading boot has
        the endpoint down by definition, so reading silence as a sighting would kill a good
        boot at the second check. This is why `None` is distinct from `False` everywhere.
        """
        self.assertEqual(bw.decide(False, None, 0), "no_probe")
        self.assertEqual(bw.decide(False, None, 5, seen_alive=True, fatal="cuda error"), "no_probe")
        self.assertFalse(bw.should_stop("no_probe", dead_grace=120, dead_for=500))

    def test_a_missing_container_is_observed_absence_not_a_failed_probe(self):
        # `docker exec` on a vanished container says so; that is evidence, not silence.
        self.assertIn("No such container", "Error response from daemon: No such container: x")

    def test_a_fatal_line_explains_a_gone_child_rather_than_overriding_a_live_one(self):
        self.assertEqual(bw.decide(False, False, 2, fatal="cuda error"), "dead")
        self.assertEqual(bw.decide(False, False, 1, fatal="cuda error"), "dead_candidate")
        # A live child still reads as loading even with a fatal in its tail: its supervisor
        # may be restarting it, and `is_stalled` owns the live-but-frozen shape.
        self.assertEqual(bw.decide(False, True, 0, seen_alive=True, fatal="notimplementederror"),
                         "loading")

    def test_an_answering_endpoint_outranks_every_death_signal(self):
        self.assertEqual(bw.decide(True, False, 5, seen_alive=True, fatal="runtimeerror"), "healthy")

    def test_each_window_acts_on_its_own_evidence(self):
        # No loading clock survives: a death and a stall each carry their evidence in the
        # verdict, and only the never-seen-alive candidate keeps a timer.
        self.assertTrue(bw.should_stop("dead", dead_grace=120, dead_for=None))
        self.assertFalse(bw.should_stop("loading", dead_grace=120, dead_for=None))
        self.assertFalse(bw.should_stop("dead_candidate", dead_grace=120, dead_for=60))
        self.assertTrue(bw.should_stop("dead_candidate", dead_grace=120, dead_for=121))
        self.assertTrue(bw.should_stop("stalled", dead_grace=120, dead_for=None))

    def test_a_fingerprint_miss_is_still_timed(self):
        # The one ambiguous shape: the container never named a matching child. It must not
        # be stopped on sight, because the pid pattern can miss a serve that is loading.
        self.assertEqual(bw.decide(False, False, 1, seen_alive=False), "dead_candidate")
        self.assertFalse(bw.should_stop("dead_candidate", dead_grace=120, dead_for=30))

    def test_the_probe_reports_the_engines_own_last_word(self):
        sample = "MEM 123\nFATAL notimplementederror\n"
        self.assertEqual(bw.parse_fatal(sample), "notimplementederror")
        # No match is not a verdict: an empty marker must never read as a cause.
        self.assertIsNone(bw.parse_fatal("MEM 123\nFATAL \n"))
        self.assertIsNone(bw.parse_fatal("PID 42\nMEM 123\n"))


class ServeLogIsCapturedBeforeTheStop(unittest.TestCase):
    """A watched death must leave the log that explains it, and the stop destroys that log.

    Measured 2026-11-04 (`qwen3.8-flash-next-uncensored-nvfp4-sglang`): the boot died at
    t=32 s, the watchdog correctly stopped it at t=43 s, and the arm then reported
    `serve logs harvested: 0 (expected one per running rank; 0 means the log was gone)` --
    rank 0's crash text was never written down. The arms that fail fastest are exactly the
    ones whose evidence matters most, so capture runs ahead of the stop.

    Asserted behaviourally, by the recorded call order: the capture (`ssh ... docker exec`)
    must come before `sparkrun stop`. Against the pre-fix file
    (`git show HEAD:tools/boot-watchdog.py`) the only recorded call is the stop, so the
    capture assertion fails there — these are controls, not restatements of the source.
    """

    CAPTURE = "META 12 1700000000\nTraceback (most recent call last):\n"

    def drive_to_one_dead_verdict(
        self, capture_stdout: str = CAPTURE, capture_error: BaseException | None = None
    ) -> tuple[int, list[list[str]], Path]:
        """Run main() until it stops the task; return (rc, recorded argv, receipt dir)."""
        calls: list[list[str]] = []

        def fake_run(argv, **_kwargs):
            calls.append(list(argv))
            if argv[0] == "ssh":
                if "docker ps --format" in argv[-1]:
                    return mock.Mock(stdout="sparkrun_abc123_solo\n", stderr="")
                if capture_error is not None:
                    raise capture_error
                return mock.Mock(stdout=capture_stdout, stderr="")
            return mock.Mock(stdout="", stderr="")

        tmp = Path(tempfile.mkdtemp())
        fake = mock.Mock(run=fake_run, SubprocessError=subprocess.SubprocessError)
        with (
            mock.patch.object(bw, "subprocess", fake),
            mock.patch.object(bw, "http_ok", return_value=False),
            # Child gone and never seen alive: a `dead_candidate`, which `--dead-grace 0`
            # stops on its first observation — the fast-reap shape this guard is about.
            mock.patch.object(bw, "serve_state", return_value=(False, None, 0, None, None)),
        ):
            rc = bw.main([
                "--endpoint", "http://127.0.0.1:1",
                "--task-id", "abc123",
                "--node", "n1",
                "--container", "sparkrun_abc123_solo",
                "--interval", "0",
                "--dead-grace", "0",
                "--log", str(tmp / "watchdog.log"),
            ])
        return rc, calls, tmp

    def test_the_capture_precedes_the_stop(self):
        rc, calls, tmp = self.drive_to_one_dead_verdict()

        self.assertEqual(rc, 3, "a dead boot must exit 3")
        stops = [i for i, argv in enumerate(calls) if argv[:2] == ["sparkrun", "stop"]]
        captures = [i for i, argv in enumerate(calls) if argv[0] == "ssh"]
        self.assertEqual(len(stops), 1, "the task must be stopped exactly once")
        self.assertTrue(captures, "no serve-log capture was attempted; the stop erases it")
        self.assertLess(captures[0], stops[0], "the stop ran before the capture, losing the log")

        written = (tmp / "serve-reaped-sparkrun_abc123_solo.log").read_text()
        self.assertTrue(
            written.startswith("META 12 1700000000"), "the capture does not record size and mtime"
        )
        self.assertIn("Traceback", written, "the capture is not the container's serve log")
        log_text = (tmp / "watchdog.log").read_text()
        self.assertIn("serve log captured for sparkrun_abc123_solo", log_text)
        self.assertIn(str(tmp / "serve-reaped-sparkrun_abc123_solo.log"), log_text)

    def test_a_failed_capture_never_prevents_the_stop(self):
        """Best-effort by construction: a broken ssh, an absent log, a refused exec."""
        cases = {
            "ssh error": {"capture_error": OSError("ssh: command not found")},
            "log absent": {"capture_stdout": "MISSING\n"},
            "refused exec": {"capture_stdout": ""},
        }
        for name, kwargs in cases.items():
            with self.subTest(case=name):
                rc, calls, tmp = self.drive_to_one_dead_verdict(**kwargs)
                self.assertEqual(rc, 3, "the stop must happen whatever the capture does")
                self.assertIn(
                    ["sparkrun", "stop", "abc123"], calls, "a failed capture blocked the stop"
                )
                self.assertIn("serve-log capture for sparkrun_abc123_solo", (tmp / "watchdog.log").read_text(),
                              "the watchdog log does not say whether the capture happened")
                self.assertFalse(
                    (tmp / "serve-reaped-sparkrun_abc123_solo.log").exists(),
                    "an empty capture was written as if it were evidence",
                )


class TestArmRefusal(unittest.TestCase):
    """A watchdog that cannot name its container must not arm (2026-11-10, ERNIE TP=4).

    The caller passed the id `sparkrun status` prints, which already carries the `sparkrun_`
    prefix; the resolver prepended another, matched nothing, and the tool armed against a
    container that did not exist. Its `--dead-grace` then stopped a healthy load 120 s in
    (shard 13/128, 37.3 GiB free). Refusal is the fix: no stop path, exit 4.
    """

    def test_a_doubled_prefix_is_refused_with_the_reason(self):
        why = bw.container_arm_refusal(
            "sparkrun_1c0dffa45afa6e47_eb5100b2911f",
            "sparkrun_sparkrun_1c0dffa45afa6e47_eb5100b2911f_node_0",
            ["sparkrun_1c0dffa45afa6e47_eb5100b2911f_node_0"],
        )
        self.assertIsNotNone(why, "the doubled prefix armed the watchdog against no container")
        self.assertIn("sparkrun_", why)
        self.assertIn("bare", why)

    def test_a_container_absent_from_the_node_is_refused(self):
        why = bw.container_arm_refusal("abc123", "sparkrun_abc123_node_0", ["sparkrun_other_solo"])
        self.assertIsNotNone(why, "armed against a container the node does not run")
        self.assertIn("sparkrun_abc123_node_0", why)
        self.assertIn("docker ps", why)

    def test_a_present_container_arms(self):
        self.assertIsNone(
            bw.container_arm_refusal("abc123", "sparkrun_abc123_node_0", ["sparkrun_abc123_node_0"])
        )

    def test_main_exits_4_and_never_stops_on_a_doubled_prefix(self):
        calls: list[list[str]] = []

        def fake_run(argv, **_kwargs):
            calls.append(list(argv))
            return mock.Mock(stdout="sparkrun_other_solo\n", stderr="")

        tmp = Path(tempfile.mkdtemp())
        fake = mock.Mock(run=fake_run, SubprocessError=subprocess.SubprocessError)
        with mock.patch.object(bw, "subprocess", fake):
            rc = bw.main(
                [
                    "--endpoint", "http://127.0.0.1:1",
                    "--task-id", "sparkrun_abc123",
                    "--node", "n1",
                    "--interval", "0",
                    "--dead-grace", "0",
                    "--log", str(tmp / "watchdog.log"),
                ]
            )
        self.assertEqual(rc, 4, "a malformed id must exit 4, not arm")
        self.assertFalse(
            [argv for argv in calls if argv[:2] == ["sparkrun", "stop"]],
            "the watchdog stopped a task it could not see",
        )
        text = (tmp / "watchdog.log").read_text()
        self.assertIn("refusing to arm", text)
        self.assertIn("already carries the 'sparkrun_' prefix", text)
        self.assertIn("WATCHDOG arm:", text, "the resolved container name was not printed")


class HookIsNotAServe(unittest.TestCase):
    """2026-11-11, ERNIE attempt 1: a mod's python `pre_exec` hook matched the serve pattern, was
    watched alive, exited (rc=137 on `.35`), and the crash-edge rule stopped a healthy boot before
    the engine started. Arming is evidence: the serve log only grows once the serve runs."""

    HOOK = (True, None, 0, None, None)       # matched python process, no serve log yet
    SERVE = (True, None, 4096, None, None)   # the engine, writing /tmp/sparkrun_serve.log

    def test_a_hook_that_exits_is_not_a_serve_death(self):
        rc, _calls, log = _drive(
            [self.HOOK, _GONE, self.SERVE, self.SERVE, _GONE, _GONE],
            stall="3600", dead_grace="1000",
        )
        verdicts = [line for line in log.splitlines() if "verdict=" in line]
        self.assertGreaterEqual(len(verdicts), 5, log)
        self.assertIn("verdict=dead_candidate", verdicts[1],
                      "the hook's exit must stay the timed candidate, never a death")
        self.assertEqual(rc, 3, log)
        self.assertIn("verdict=dead ", verdicts[-1],
                      "the real serve's death must still stop the boot")

    def test_the_old_rule_would_have_killed_the_hook(self):
        """Negative control: with seen_alive set by any matched process, the hook's exit is a death."""
        self.assertEqual(bw.decide(False, False, 2, seen_alive=True), "dead")


if __name__ == "__main__":
    unittest.main()

