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
import sys
import unittest
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

    def test_second_dead_sighting_is_dead(self):
        self.assertEqual(bw.decide(False, False, 2), "dead")
        self.assertEqual(bw.decide(False, False, 3), "dead")

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
        self.assertIn("prev_logsize", text, "no previous log size to diff")
        self.assertIn("LOGSIZE", text, "the sample does not ask for the log size")


if __name__ == "__main__":
    unittest.main()
