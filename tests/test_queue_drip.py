# SPDX-License-Identifier: AGPL-3.0-or-later
"""Guards for tools/queue-drip.py: the drip must never launch where it may not."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "queue_drip", Path(__file__).resolve().parent.parent / "tools" / "queue-drip.py"
)
drip = importlib.util.module_from_spec(_spec)
sys.modules["queue_drip"] = drip
_spec.loader.exec_module(drip)


def _config(tmp: str, body: str) -> Path:
    path = Path(tmp) / "fleet.yaml"
    path.write_text(body, encoding="utf-8")
    return path


class Config(unittest.TestCase):
    def test_a_missing_config_is_an_error_not_an_empty_fleet(self):
        with self.assertRaises(drip.ConfigError):
            drip.load_config(Path("/nonexistent/fleet.yaml"))

    def test_an_empty_research_list_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(drip.ConfigError):
                drip.load_config(_config(tmp, "research:\nskip: []\n"))

    def test_a_typo_key_is_refused(self):
        """`reseearch:` would otherwise parse as a fleet with nothing to do."""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(drip.ConfigError):
                drip.load_config(_config(tmp, "reseearch:\n  - 10.0.0.1\nresearch:\n  - 10.0.0.2\n"))

    def test_a_duplicate_key_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(drip.ConfigError):
                drip.load_config(_config(tmp, "research:\n  - a\nresearch:\n  - b\n"))

    def test_the_shipped_config_parses(self):
        path = Path(__file__).resolve().parent.parent / ".local" / "fleet.yaml"
        if not path.exists():
            self.skipTest("no .local/fleet.yaml on this clone (untracked by design)")
        cfg = drip.load_config(path)
        self.assertTrue(cfg["research"])
        self.assertIsInstance(cfg["poll_seconds"], int)


class Liveness(unittest.TestCase):
    def test_our_own_pid_is_alive(self):
        self.assertTrue(drip.pid_alive(os.getpid()))

    def test_a_reaped_pid_is_not(self):
        pid = os.fork()
        if pid == 0:
            os._exit(0)
        os.waitpid(pid, 0)
        self.assertFalse(drip.pid_alive(pid))

    def test_an_arm_whose_process_exited_is_not_in_flight(self):
        state = {"arm-a": {"pid": 0, "node": "n1"}, "arm-b": {"pid": os.getpid(), "node": "n2"}}
        self.assertEqual(list(drip.in_flight(state)), ["arm-b"])


class Planning(unittest.TestCase):
    def test_an_arm_already_running_is_not_planned_again(self):
        """Its receipt directory has no numbers yet, so the receipt predicate cannot see it."""
        plan = [{"arm": "a", "node": "n1"}, {"arm": "b", "node": "n2"}]
        kept = drip.drop_in_flight(plan, {"a": {"pid": os.getpid()}})
        self.assertEqual([row["arm"] for row in kept], ["b"])

    def test_a_driver_started_by_hand_also_blocks_its_arm(self):
        """The ledger and the receipts both miss an arm that started a minute ago."""
        plan = [{"arm": "jev", "path": "recipes/decision/jev.yaml", "node": "n1"},
                {"arm": "other", "path": "recipes/x/other.yaml", "node": "n2"}]
        kept = drip.drop_in_flight(plan, {}, {"recipes/decision/jev.yaml"})
        self.assertEqual([row["arm"] for row in kept], ["other"])

    def test_driver_paths_come_from_the_process_table(self):
        found = drip.live_driver_paths()
        self.assertIsInstance(found, set)
        self.assertFalse(any(" " in p for p in found), "a captured path must be one argument")

    def test_malformed_state_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text("{not json")
            with self.assertRaises(drip.ConfigError):
                drip.read_state(path)

    def test_absent_state_is_empty_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(drip.read_state(Path(tmp) / "state.json"), {})


class Windows(unittest.TestCase):
    def test_a_declared_window_stops_the_drip(self):
        """The lock outranks an idle node: a window is a promise to the other sessions."""
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "fleet-window.lock"
            lock.write_text("session: other; nodes: all\n")
            cfg = _config(tmp, "research:\n  - 10.0.0.1\n")
            orig = drip.LOCK
            drip.LOCK = lock
            try:
                rc = drip.main(["--config", str(cfg), "--state", str(Path(tmp) / "s.json"),
                                "--once", "--dry-run"])
            finally:
                drip.LOCK = orig
        self.assertEqual(rc, 3, "a declared window must refuse, not plan")


if __name__ == "__main__":
    unittest.main()