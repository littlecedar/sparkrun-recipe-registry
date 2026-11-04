"""Placement: which arm goes to which host, and the placement defect kept as a control.

Acceptance items about plan ordering, TP=2 pairing and reclaim-driven re-assignment are decided
here, because assignment is a pure function of the plan order, the arm records and the free hosts.
The control is tonight's static partition: the plan cut once into per-node slices, which cannot see
that a peer has nothing left to run.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from sparkrun_campaign import evidence, plan

from .support import manifest, recipe

LANE_DOC = "line one\nline two\n"


def arm_record(tp: int = 1, status: str = "pending", failures: int = 0, reaped: bool = True) -> dict[str, Any]:
    return {"tp": tp, "status": status, "failures": failures,
            "needs_reap": [] if reaped else ["node-a"]}


def static_slice(order: list[str], hosts: list[str]) -> dict[str, list[str]]:
    """Tonight's placement: cut the plan once, hand each node its share. Kept as a control."""
    half = (len(order) + 1) // 2
    return dict(zip(hosts, [order[:half], order[half:]]))


class Manifest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        for name in ("one", "two"):
            recipe(self.root, "lane", name)

    def write(self, rows) -> Path:
        path = self.root / "manifest.json"
        path.write_text(json.dumps(rows), encoding="utf-8")
        return path

    def test_order_is_the_manifest_order(self) -> None:
        entries = plan.load_manifest(manifest(
            self.root / "m.json",
            [("b", "recipes/lane/two.yaml", 1), ("a", "recipes/lane/one.yaml", 1)],
        ))
        self.assertEqual([entry["arm"] for entry in entries], ["b", "a"])

    def test_tp_defaults_to_one(self) -> None:
        entries = plan.load_manifest(self.write(
            [{"arm": "one", "path": "recipes/lane/one.yaml"}]
        ))
        self.assertEqual(entries[0]["tp"], 1)

    def test_a_duplicate_arm_is_refused(self) -> None:
        with self.assertRaises(plan.PlanError):
            plan.load_manifest(self.write([
                {"arm": "one", "path": "recipes/lane/one.yaml"},
                {"arm": "one", "path": "recipes/lane/two.yaml"},
            ]))

    def test_an_unknown_tp_is_refused(self) -> None:
        with self.assertRaises(plan.PlanError):
            plan.load_manifest(self.write([{"arm": "one", "path": "recipes/lane/one.yaml", "tp": 4}]))

    def test_a_missing_recipe_is_refused_at_plan_time(self) -> None:
        entries = plan.load_manifest(self.write([{"arm": "gone", "path": "recipes/lane/gone.yaml"}]))
        with self.assertRaises(plan.PlanError):
            plan.build(entries, {}, {}, self.root)

    def test_every_exclusion_is_explained(self) -> None:
        recipe(self.root, "lane", "gone",
               marker="2026-11-01 \u2014 died at engine load (docs/lane.md:2)")
        (self.root / "docs").mkdir(exist_ok=True)
        (self.root / "docs" / "lane.md").write_text(LANE_DOC, encoding="utf-8")
        entries = plan.load_manifest(manifest(self.root / "m.json", [
            ("one", "recipes/lane/one.yaml", 1),
            ("gone", "recipes/lane/gone.yaml", 1),
        ]))
        order, lines = plan.build(entries, evidence.skips(self.root), {}, self.root)
        self.assertEqual(order, ["one", "gone"])
        self.assertEqual(lines, ["skip: gone (measured-rejected, docs/lane.md:2)"])


class Assignment(unittest.TestCase):
    def test_a_tp2_arm_takes_two_hosts_in_one_lease(self) -> None:
        arms = {"pair": arm_record(tp=2)}
        self.assertEqual(
            plan.next_assignment(["pair"], arms, ["node-a", "node-b"]),
            ("pair", ("node-a", "node-b")),
        )
        self.assertIsNone(plan.next_assignment(["pair"], arms, ["node-a"]))

    def test_a_leased_arm_is_never_handed_out_twice(self) -> None:
        arms = {"one": arm_record(status="leased")}
        self.assertIsNone(plan.next_assignment(["one"], arms, ["node-a"]))

    def test_an_arm_waiting_for_a_reap_is_not_assignable(self) -> None:
        arms = {"one": arm_record(reaped=False)}
        self.assertIsNone(plan.next_assignment(["one"], arms, ["node-a"]))

    def test_a_failed_arm_retries_only_inside_the_budget(self) -> None:
        arms = {"one": arm_record(status="failed", failures=1)}
        self.assertIsNone(plan.next_assignment(["one"], arms, ["node-a"], retries=0))
        self.assertEqual(plan.next_assignment(["one"], arms, ["node-a"], retries=1),
                         ("one", ("node-a",)))
        arms["one"]["failures"] = 2
        self.assertIsNone(plan.next_assignment(["one"], arms, ["node-a"], retries=1))

    def test_a_skipped_arm_is_never_assigned(self) -> None:
        arms = {"one": arm_record(status="skipped")}
        self.assertIsNone(plan.next_assignment(["one"], arms, ["node-a"]))


class NegativeControls(unittest.TestCase):
    def test_a_static_slice_strands_the_node_whose_share_ran_out(self) -> None:
        order = ["long-arm", "mid-arm", "short-arm"]
        queues = static_slice(order, ["node-a", "node-b"])
        arms = {
            "long-arm": arm_record(status="leased", tp=2),
            "mid-arm": arm_record(),
            "short-arm": arm_record(status="measured"),
        }
        # node-b finished its only arm; node-a is 90 minutes into a 132-minute one.
        self.assertEqual(queues["node-b"], ["short-arm"])
        self.assertEqual([name for name in queues["node-b"] if arms[name]["status"] == "pending"], [])
        # The director hands the free node the next pending arm, whatever slice it "belongs" to.
        self.assertEqual(
            plan.next_assignment(order, arms, ["node-b"]),
            ("mid-arm", ("node-b",)),
        )

    def test_a_resume_that_trusts_the_state_file_boots_a_live_arm_again(self) -> None:
        arms = {"one": arm_record(tp=2, reaped=False)}

        def trusting(order, records, free):
            for name in order:
                if records[name]["status"] == "pending":
                    need = 2 if records[name]["tp"] == 2 else 1
                    if len(free) >= need:
                        return name, tuple(free[:need])
            return None

        self.assertEqual(trusting(["one"], arms, ["node-a", "node-b"]),
                         ("one", ("node-a", "node-b")))
        self.assertIsNone(plan.next_assignment(["one"], arms, ["node-a", "node-b"]))


if __name__ == "__main__":
    unittest.main()