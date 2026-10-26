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


class TestParser(unittest.TestCase):
    def test_required_args(self):
        with self.assertRaises(SystemExit):
            bw.main(["--endpoint", "http://x:8000"])  # missing --task-id/--node


if __name__ == "__main__":
    unittest.main()
