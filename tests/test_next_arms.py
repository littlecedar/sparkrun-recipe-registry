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
import os
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


class FreeNodes(unittest.TestCase):
    """A node the probe cannot inspect is not free."""

    def _probe(self, replies):
        orig = na.sh
        na.sh = lambda argv, timeout=30: replies[next(a for a in argv if a.startswith("red@")).removeprefix("red@")]
        try:
            return na.free_nodes(list(replies))
        finally:
            na.sh = orig

    def test_an_empty_inspectable_node_is_free(self):
        self.assertEqual(self._probe({"node-a": (0, "")}), ["node-a"])

    def test_a_node_with_a_container_is_busy(self):
        self.assertEqual(self._probe({"node-a": (0, "abc123")}), [])

    def test_a_failed_docker_call_is_busy_not_empty(self):
        """`docker ps -aq | wc -l` would have printed 0 here and called the node free."""
        self.assertEqual(self._probe({"node-a": (1, "")}), [])

    def test_an_unreachable_node_is_busy(self):
        self.assertEqual(self._probe({"node-a": (255, "")}), [])


class Placement(unittest.TestCase):
    """A TP=2 arm must never be handed one host."""

    def test_only_tp1_arms_are_planned_onto_a_node(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "m.json"
            p.write_text(json.dumps([
                {"arm": "wide", "path": "recipes/x/wide.yaml", "tp": 2},
                {"arm": "narrow", "path": "recipes/x/narrow.yaml", "tp": 1},
            ]))
            todo = na.candidates(str(p), set(), set(), 2)
        plan, pairs = na.place(["node-a"], todo)
        self.assertEqual([row["arm"] for row in plan], ["narrow"])
        self.assertEqual([e["arm"] for e in pairs], ["wide"])
        self.assertEqual(plan[0]["launch"], "./tools/run-arm.sh recipes/x/narrow.yaml node-a")


class Summary(unittest.TestCase):
    """The human-readable path must not crash where the JSON path works."""

    def test_the_summary_renders_with_a_free_node(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.json"
            path.write_text(json.dumps([{"arm": "solo", "path": "recipes/x/s.yaml", "tp": 1}]))
            orig = na.free_nodes
            na.free_nodes = lambda nodes: ["node-a"]
            try:
                rc = na.main(["--nodes", "node-a", "--manifest", str(path)])
            finally:
                na.free_nodes = orig
        self.assertEqual(rc, 0)

    def test_the_summary_renders_when_the_fleet_is_full(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.json"
            path.write_text(json.dumps([{"arm": "solo", "path": "recipes/x/s.yaml", "tp": 1}]))
            orig = na.free_nodes
            na.free_nodes = lambda nodes: []
            try:
                rc = na.main(["--nodes", "node-a", "--manifest", str(path)])
            finally:
                na.free_nodes = orig
        self.assertEqual(rc, 0, "a busy fleet has nothing unplaced, so it is not an error")

    def test_a_free_node_with_nothing_to_run_is_the_error_case(self):
        """Exit 1 is the idle-node signal, not a general failure."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.json"
            path.write_text("[]")
            orig = na.free_nodes
            na.free_nodes = lambda nodes: ["node-a"]
            try:
                rc = na.main(["--nodes", "node-a", "--manifest", str(path)])
            finally:
                na.free_nodes = orig
        self.assertEqual(rc, 1)


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


class MeasuredPredicate(unittest.TestCase):
    """A receipt that recorded a start is not a receipt that recorded a cell."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("na_measured", TOOL)
        cls._mod = importlib.util.module_from_spec(spec)
        sys.modules["na_measured"] = cls._mod
        spec.loader.exec_module(cls._mod)

    def test_a_yaml_alone_does_not_count_as_measured(self):
        with tempfile.TemporaryDirectory() as home:
            win = os.path.join(home, "benchmarks", "tp12-x")
            arm = os.path.join(win, "dead-arm")
            os.makedirs(arm)
            open(os.path.join(arm, "ladder.yaml"), "w").close()
            open(os.path.join(arm, "launch.log"), "w").close()
            self.assertEqual(self._mod.measured_arms(home, ("benchmarks/tp12-*",)), set())

    def test_a_machine_readable_artefact_does(self):
        with tempfile.TemporaryDirectory() as home:
            win = os.path.join(home, "benchmarks", "tp12-x")
            arm = os.path.join(win, "good-arm")
            os.makedirs(arm)
            open(os.path.join(arm, "ladder.json"), "w").close()
            self.assertEqual(self._mod.measured_arms(home, ("benchmarks/tp12-*",)), {"good-arm"})


class PairPlacement(unittest.TestCase):
    """A TP=2 arm takes two nodes and launches once; a pair must never be stranded idle.

    `place` used to return pairs as an unplaceable backlog, so every free-node report read
    "NOTHING RUNNABLE" while seven TP=2 arms waited -- the tool could only ever spend a node on
    single-node work.
    """

    def _tool(self):
        return self._mod

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("na_pairs", TOOL)
        cls._mod = importlib.util.module_from_spec(spec)
        sys.modules["na_pairs"] = cls._mod
        spec.loader.exec_module(cls._mod)

    def test_a_pair_takes_two_nodes_and_launches_once(self):
        todo = [{"arm": "p1", "path": "r/p1.yaml", "tp": 2}]
        plan, waiting = self._tool().place(["n1", "n2"], todo)
        self.assertEqual(waiting, [])
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["nodes"], ["n1", "n2"])
        self.assertTrue(plan[0]["launch"].endswith("r/p1.yaml n1,n2"), plan[0]["launch"])

    def test_a_pair_waits_rather_than_landing_on_one_node(self):
        """One free node is a wrong measurement (TP=1 in disguise), not a fallback."""
        todo = [{"arm": "p1", "path": "r/p1.yaml", "tp": 2}]
        plan, waiting = self._tool().place(["n1"], todo)
        self.assertEqual(plan, [])
        self.assertEqual([e["arm"] for e in waiting], ["p1"])

    def test_a_single_arm_still_fills_a_second_node(self):
        todo = [{"arm": "p1", "path": "r/p1.yaml", "tp": 2},
                {"arm": "s1", "path": "r/s1.yaml", "tp": 1}]
        plan, _ = self._tool().place(["n1", "n2", "n3"], todo)
        self.assertEqual([(r["arm"], r["nodes"]) for r in plan],
                         [("p1", ["n1", "n2"]), ("s1", ["n3"])])

    def test_json_mode_exits_cleanly(self):
        """`--json` is how queue-drip calls this tool: an exception here breaks every drip pass."""
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.json"
            manifest.write_text(json.dumps(
                [{"arm": "solo", "path": "recipes/x/solo.yaml", "tp": 1}]))
            out = subprocess.run([sys.executable, TOOL, "--nodes", "unreachable.invalid",
                                  "--json", "--manifest", str(manifest)],
                                 capture_output=True, text=True, check=False)
        self.assertNotIn("Traceback", out.stderr, out.stderr)
        self.assertIn("{", out.stdout)

    def test_no_node_is_planned_twice(self):
        todo = [{"arm": f"a{i}", "path": f"r/a{i}.yaml", "tp": 2 if i % 2 else 1}
                for i in range(6)]
        plan, _ = self._tool().place(["n1", "n2", "n3", "n4"], todo)
        used = [n for row in plan for n in row["nodes"]]
        self.assertEqual(len(used), len(set(used)), used)
        self.assertLessEqual(len(used), 4)


if __name__ == "__main__":
    unittest.main()