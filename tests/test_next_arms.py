#!/usr/bin/env python3
"""Guard for tools/next-arms.py: the two selection rules that keep nodes from idling.

The tool exists because an idle free node with queued work went unnoticed for an hour. Its
value is entirely in two predicates, so those are what the tests pin, offline:

  * an arm counts as measured only when its receipt carries a machine-readable artefact (or a
    `*.yaml`), and a `.prev-*` directory is history rather than a measurement;
  * a candidate's `tp` must fit the nodes available, and a TP=2 arm must never be planned onto
    one free node.

The fleet probe (`free_nodes`) is deliberately untested here: it is one `docker ps` over ssh,
and a test would assert the network. The plan/candidate split is tested through `--json`.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "next-arms.py"


def load():
    spec = importlib.util.spec_from_file_location("next_arms", TOOL)
    assert spec and spec.loader, f"cannot load {TOOL}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules["next_arms"] = mod
    spec.loader.exec_module(mod)
    return mod


na = load()


class MeasuredArms(unittest.TestCase):
    def test_a_receipt_with_a_ladder_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            arm = Path(tmp) / "benchmarks" / "tp12-20261030" / "arm-a"
            arm.mkdir(parents=True)
            (arm / "ladder.json").write_text("{}")
            self.assertIn("arm-a", na.measured_arms(tmp, windows=("benchmarks/tp12-*",)))

    def test_a_transcribed_ladder_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            arm = Path(tmp) / "benchmarks" / "tp12-20261030" / "arm-b"
            arm.mkdir(parents=True)
            (arm / "ladder.transcribed.json").write_text("{}")
            self.assertIn("arm-b", na.measured_arms(tmp, windows=("benchmarks/tp12-*",)))

    def test_a_previous_receipt_is_history_not_a_measurement(self):
        with tempfile.TemporaryDirectory() as tmp:
            arm = Path(tmp) / "benchmarks" / "tp12-20261030" / "arm-c.prev-101010"
            arm.mkdir(parents=True)
            (arm / "ladder.json").write_text("{}")
            self.assertNotIn("arm-c.prev-101010", na.measured_arms(tmp, windows=("benchmarks/tp12-*",)))

    def test_a_logs_only_receipt_is_not_a_measurement(self):
        with tempfile.TemporaryDirectory() as tmp:
            arm = Path(tmp) / "benchmarks" / "tp12-20261030" / "arm-d"
            arm.mkdir(parents=True)
            (arm / "house.log").write_text("no artefact here")
            self.assertEqual(na.measured_arms(tmp, windows=("benchmarks/tp12-*",)), set())


class Candidates(unittest.TestCase):
    def _manifest(self, tmp: str) -> str:
        path = Path(tmp) / "manifest.json"
        path.write_text(json.dumps([
            {"arm": "solo", "path": "recipes/x/solo.yaml", "tp": 1},
            {"arm": "pair", "path": "recipes/x/pair.yaml", "tp": 2},
            {"arm": "odd", "path": "recipes/x/odd.yaml", "tp": 4},
        ]))
        return str(path)

    def test_a_tp2_arm_needs_two_free_nodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            names = [e["arm"] for e in na.candidates(self._manifest(tmp), set(), set(), 1)]
        self.assertIn("solo", names)
        self.assertNotIn("pair", names, "a TP=2 arm must not be planned onto one node")

    def test_a_tp2_arm_is_offered_when_two_nodes_are_free(self):
        with tempfile.TemporaryDirectory() as tmp:
            names = [e["arm"] for e in na.candidates(self._manifest(tmp), set(), set(), 2)]
        self.assertIn("pair", names)

    def test_a_tp4_arm_is_never_offered_on_two_nodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            names = [e["arm"] for e in na.candidates(self._manifest(tmp), set(), set(), 2)]
        self.assertNotIn("odd", names)

    def test_measured_and_skipped_arms_are_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            names = [e["arm"] for e in na.candidates(self._manifest(tmp), {"solo"}, {"pair"}, 2)]
        self.assertEqual(names, [])

    def test_nothing_is_runnable_on_zero_free_nodes(self):
        """The predicate is honest: with no node free, nothing can be placed."""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(na.candidates(self._manifest(tmp), set(), set(), 0), [])

    def test_the_backlog_is_visible_at_fleet_capacity(self):
        """What keeps an idle node from hiding work: the queue is asked at fleet capacity.

        `main` asks with `max(len(nodes), 2)` for exactly this reason, so a full fleet still
        reports what comes next instead of an empty list.
        """
        with tempfile.TemporaryDirectory() as tmp:
            names = [e["arm"] for e in na.candidates(self._manifest(tmp), set(), set(), 2)]
        self.assertIn("solo", names)
        self.assertIn("pair", names)




class NoSilentEmpties(unittest.TestCase):
    """A tool that certifies "nothing to do" wrongly is worse than no tool."""

    def test_a_missing_manifest_raises(self):
        with self.assertRaises(na.ManifestError):
            na.candidates("/nonexistent/manifest.json", set(), set(), 2)

    def test_a_malformed_manifest_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "m.json"
            bad.write_text("{not json")
            with self.assertRaises(na.ManifestError):
                na.candidates(str(bad), set(), set(), 2)

    def test_a_manifest_that_is_not_a_list_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "m.json"
            bad.write_text('{"arms": []}')
            with self.assertRaises(na.ManifestError):
                na.candidates(str(bad), set(), set(), 2)

    def test_a_measured_arm_does_not_mask_its_longer_sibling(self):
        """Substring matching reported 'nothing runnable' on the ornith family."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.json"
            path.write_text(json.dumps([
                {"arm": "zz-ornith-1.5-122b-nvfp4-sglang", "path": "recipes/o/a.yaml", "tp": 1},
                {"arm": "zz-ornith-1.5-122b-nvfp4-dflash2-sglang", "path": "recipes/o/b.yaml", "tp": 1},
            ]))
            names = [e["arm"] for e in na.candidates(str(path), {"zz-ornith-1.5-122b-nvfp4-sglang"}, set(), 2)]
        self.assertEqual(names, ["zz-ornith-1.5-122b-nvfp4-dflash2-sglang"])

    def test_a_hand_named_receipt_is_honoured_through_the_alias_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.json"
            path.write_text(json.dumps([{"arm": "nemotron-3.5-lightning-30b-a3b-nvfp4-vllm",
                                         "path": "recipes/e/n.yaml", "tp": 1}]))
            self.assertEqual(na.candidates(str(path), {"nemotron"}, set(), 2), [])


class Reporting(unittest.TestCase):
    """The CLI must explain a short plan rather than assert one."""

    def test_a_bad_manifest_exits_two_with_a_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = subprocess.run(
                [sys.executable, str(TOOL), "--nodes", "127.0.0.1", "--manifest",
                 str(Path(tmp) / "missing.json")],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(p.returncode, 2)
        self.assertIn("cannot plan", p.stderr)


class Cli(unittest.TestCase):
    def test_no_nodes_is_an_error(self):
        env = {"PATH": "/usr/bin:/bin"}
        p = subprocess.run([sys.executable, str(TOOL)], capture_output=True, text=True,
                           env=env, check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("no nodes", p.stderr)


if __name__ == "__main__":
    unittest.main()