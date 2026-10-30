# SPDX-License-Identifier: AGPL-3.0-or-later
"""Guards for tools/queue-drip.py: the drip must never launch where it may not."""

from __future__ import annotations

import os
import subprocess
import time
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
                drip.load_config(_config(tmp, "reseearch:\n  - node-a\nresearch:\n  - node-b\n"))

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

    def test_a_recycled_pid_is_not_our_driver(self):
        """A live pid whose command line is something else must not keep an arm "in flight"."""
        self.assertFalse(drip.pid_is_driver(os.getpid(), "some-arm"))

    def test_a_process_that_is_not_a_driver_is_rejected_even_when_alive(self):
        child = subprocess.Popen(["sleep", "5"])
        try:
            self.assertTrue(drip.pid_alive(child.pid))
            self.assertFalse(drip.pid_is_driver(child.pid, "any-arm"))
        finally:
            child.kill()
            child.wait()

    def test_a_driver_shaped_cmdline_is_accepted(self):
        # A real driver is invoked as `run-arm.sh <recipe> <hosts>`, so the arm name is an argv
        # element. The previous fixture omitted it and passed only because "arm" is a substring of
        # "run-arm.sh" -- the exact false positive the argv comparison exists to reject.
        # python3, not `sleep`: `sleep 5 arm` exits on the bad argument before the poll sees it.
        child = subprocess.Popen(
            ["bash", "-c", "exec -a run-arm.sh python3 -c 'import time; time.sleep(5)' arm"]
        )
        try:
            # Popen returns before bash execs, so poll -- asserting immediately is the flake.
            deadline = time.time() + 2.0
            while time.time() < deadline and not drip.pid_is_driver(child.pid, "arm", ""):
                time.sleep(0.02)
            self.assertTrue(drip.pid_is_driver(child.pid, "arm", ""))
        finally:
            child.kill()
            child.wait()

    def test_a_pair_row_names_both_hosts(self):
        """A TP=2 row occupies two nodes; a ledger that records one under-reports the window."""
        self.assertEqual(drip.hosts_of({"nodes": ["n1", "n2"], "node": "n1"}), ["n1", "n2"])
        self.assertEqual(drip.hosts_of({"node": "n1"}), ["n1"])

    def test_a_ledger_row_without_a_path_still_identifies_its_driver(self):
        """Old ledger rows carry only the arm name; the driver's argv carries the recipe path."""
        child = subprocess.Popen(
            ["bash", "-c",
             "exec -a run-arm.sh python3 -c 'import time; time.sleep(5)' recipes/rerank/arm.yaml"]
        )
        try:
            deadline = time.time() + 2.0
            while time.time() < deadline and not drip.pid_is_driver(child.pid, "arm", ""):
                time.sleep(0.02)
            self.assertTrue(drip.pid_is_driver(child.pid, "arm", ""))
            self.assertFalse(drip.pid_is_driver(child.pid, "other-arm", ""))
        finally:
            child.kill()
            child.wait()

    def test_a_prefix_of_the_program_name_is_not_an_arm(self):
        """`arm` occurs inside `run-arm.sh`; that must not read as "this pid drives arm"."""
        child = subprocess.Popen(["bash", "-c", "exec -a run-arm.sh sleep 5"])
        try:
            deadline = time.time() + 2.0
            while time.time() < deadline and not drip.pid_alive(child.pid):
                time.sleep(0.02)
            self.assertFalse(drip.pid_is_driver(child.pid, "arm", ""))
        finally:
            child.kill()
            child.wait()

    def test_the_ledger_keeps_only_arms_whose_driver_is_really_alive(self):
        state = {"arm-a": {"pid": 0, "node": "n1"}, "arm-b": {"pid": 4242, "node": "n2"},
                 "arm-c": {"pid": 4243, "node": "n3"}}
        orig = drip.pid_is_driver
        drip.pid_is_driver = lambda pid, arm, path="": pid == 4242
        try:
            self.assertEqual(list(drip.in_flight(state)), ["arm-b"])
        finally:
            drip.pid_is_driver = orig


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

    def test_an_in_flight_arm_is_passed_to_the_planner_not_just_dropped(self):
        """A dropped row would leave its free node idle; the planner must be able to pick the next."""
        arms = drip.in_flight_arms({"recipes/decision/jev.yaml", "recipes/x/other.yaml"})
        self.assertEqual(arms, {"jev", "other"})

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
    def test_the_legacy_scratch_path_is_still_honoured(self):
        """A lock written before the path moved must not be ignored."""
        with tempfile.TemporaryDirectory() as tmp:
            legacy = Path(tmp) / "fleet-window.lock"
            legacy.write_text("session: other\n")
            orig = drip.LOCK_PATHS
            drip.LOCK_PATHS = (Path(tmp) / "absent.lock", legacy)
            try:
                self.assertEqual(drip.declared_window(), legacy)
            finally:
                drip.LOCK_PATHS = orig

    def test_a_declared_window_stops_the_drip(self):
        """The lock outranks an idle node: a window is a promise to the other sessions."""
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "fleet-window.lock"
            lock.write_text("session: other; nodes: all\n")
            cfg = _config(tmp, "research:\n  - node-a\n")
            orig = drip.LOCK_PATHS
            drip.LOCK_PATHS = (lock,)
            try:
                rc = drip.main(["--config", str(cfg), "--state", str(Path(tmp) / "s.json"),
                                "--once", "--dry-run"])
            finally:
                drip.LOCK_PATHS = orig
        self.assertEqual(rc, 3, "a declared window must refuse, not plan")


if __name__ == "__main__":
    unittest.main()