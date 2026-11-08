"""The skip source and the receipt predicate, and the controls that show each one can fail.

Acceptance items 1 and 2. Both predicates are read before any boot, so both are decidable here.
The negative controls are tonight's driver: presence-only completion, and a plan built from the
manifest alone.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from sparkrun_campaign import evidence

from .support import lane_doc, receipt, recipe, sidecar_receipt

REPO = Path(__file__).resolve().parents[2]
MARKER = "2026-11-01 \u2014 died at engine load (docs/lane.md:2)"


def presence_only(arm_dir: str | Path) -> bool:
    """Tonight's completion predicate: a file exists and is non-empty. Kept as a control."""
    return any(
        (Path(arm_dir) / name).is_file() and (Path(arm_dir) / name).stat().st_size > 0
        for name in ("ladder.json", "house.yaml")
    )


def load_next_arms():
    """`tools/next-arms.py` by path: dash-named, not importable, and registered before exec."""
    path = REPO / "tools" / "next-arms.py"
    spec = importlib.util.spec_from_file_location("next_arms_tool", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["next_arms_tool"] = module
    spec.loader.exec_module(module)
    return module


class SkipSource(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        recipe(self.root, "lane", "negative", marker=MARKER)
        recipe(self.root, "lane", "ordinary")
        lane_doc(self.root)

    def test_skip_line_names_arm_verdict_and_citation(self) -> None:
        verdicts = evidence.skips(self.root)
        self.assertEqual(list(verdicts), ["negative"])
        self.assertEqual(
            evidence.skip_line(verdicts["negative"]),
            "skip: negative (measured-rejected, docs/lane.md:2)",
        )

    def test_a_citation_that_does_not_resolve_is_reported(self) -> None:
        (self.root / "docs" / "lane.md").unlink()
        problems = evidence.citation_problems(evidence.skips(self.root), self.root)
        self.assertEqual(len(problems), 1)
        self.assertIn("docs/lane.md:2", problems[0])

    def test_a_marker_outside_metadata_is_not_the_skip_source(self) -> None:
        # sparkrun sweeps an unknown top-level key into runtime_config, so a top-level marker is a
        # silent drop wearing the right name.
        (self.root / "recipes" / "lane" / "negative.yaml").write_text(
            f'measured_rejected: "{MARKER}"\n', encoding="utf-8"
        )
        self.assertEqual(evidence.skips(self.root), {})

    def test_two_markers_on_one_arm_raise(self) -> None:
        text = (self.root / "recipes" / "lane" / "negative.yaml").read_text(encoding="utf-8")
        (self.root / "recipes" / "lane" / "negative.yaml").write_text(
            text + f'  measured_rejected: "{MARKER}"\n', encoding="utf-8"
        )
        with self.assertRaises(evidence.EvidenceError):
            evidence.skips(self.root)

    def test_a_marker_that_is_not_a_citation_raises(self) -> None:
        (self.root / "recipes" / "lane" / "negative.yaml").write_text(
            'metadata:\n  measured_rejected: "dead, see the lane doc"\n', encoding="utf-8"
        )
        with self.assertRaises(evidence.EvidenceError):
            evidence.skips(self.root)


class ReceiptFields(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_ok_marker_with_cells_is_a_measurement(self) -> None:
        arm_dir = receipt(self.root, "arm")
        self.assertEqual(evidence.done(arm_dir), (True, ""))

    def test_a_partial_ladder_is_not_a_measurement(self) -> None:
        ok, reason = evidence.done(receipt(self.root, "arm", cells=0))
        self.assertFalse(ok)
        self.assertIn("not a measurement", reason)

    def test_a_failed_ladder_field_is_not_a_measurement(self) -> None:
        ok, reason = evidence.done(receipt(self.root, "arm", ladder="failed (rc=2)"))
        self.assertFalse(ok)
        self.assertIn("ladder failed", reason)

    def test_a_ladder_field_that_is_neither_ok_nor_failed_is_not_a_measurement(self) -> None:
        ok, reason = evidence.done(receipt(self.root, "arm", ladder="maybe"))
        self.assertFalse(ok)
        self.assertIn("neither", reason)

    def test_a_yaml_that_a_benchmark_started_is_not_evidence(self) -> None:
        arm_dir = receipt(self.root, "arm", ladder="")
        (arm_dir / "ladder.json").unlink()
        (arm_dir / "ladder.yaml").write_text("benchmark_started: true\n", encoding="utf-8")
        ok, reason = evidence.done(arm_dir)
        self.assertFalse(ok)
        self.assertIn("no marker and no machine-readable artefact", reason)

    def test_the_nested_sidecar_is_read_with_its_shape(self) -> None:
        # The 2026-11-08 arms wrote sparkrun's own sidecar, not run-arm's flat marker; the reader
        # must take the shape that exists and say so instead of inventing a ladder field.
        arm_dir = sidecar_receipt(self.root, "arm", score="100")
        fields = evidence.marker_fields(arm_dir)
        self.assertEqual(fields["shape"], "sparkrun_benchmark")
        self.assertEqual(fields["house_score"], "100")
        self.assertEqual(fields["suite"], "benchmarking/standard-suite.yaml")
        self.assertNotIn("ladder", fields, "a sidecar must not gain a fabricated ladder field")
        self.assertEqual(evidence.done(arm_dir), (True, ""))

    def test_a_sidecar_without_a_result_is_not_a_measurement(self) -> None:
        empty_ladder = evidence.done(sidecar_receipt(self.root, "arm", cells=0, score=None))
        self.assertFalse(empty_ladder[0])
        self.assertIn("sparkrun_benchmark", empty_ladder[1])
        self.assertIn("not a measurement", empty_ladder[1])
        arm_dir = sidecar_receipt(self.root, "bare", score=None)
        (arm_dir / "ladder.json").unlink()
        bare = evidence.done(arm_dir)
        self.assertFalse(bare[0])
        self.assertIn("no house score", bare[1])

    def test_a_marker_with_neither_shape_raises(self) -> None:
        arm_dir = receipt(self.root, "arm", ladder="")
        (arm_dir / "house.yaml").write_text("something_else: yes\n", encoding="utf-8")
        with self.assertRaises(evidence.EvidenceError):
            evidence.marker_fields(arm_dir)

    def test_the_client_receipt_carries_the_image_id(self) -> None:
        arm_dir = sidecar_receipt(self.root, "arm", client={"image_id": "sha256:7f8f1b38", "rc": 0})
        client = evidence.client_receipt(arm_dir)
        self.assertEqual(client["image_id"], "sha256:7f8f1b38")
        self.assertEqual(client["cell"], "house4096")
        self.assertIsNone(evidence.client_receipt(receipt(self.root, "plain")))

    def test_the_accuracy_status_field_is_readable(self) -> None:
        arm_dir = receipt(self.root, "arm", accuracy="taken \u2014 the score is in teb-decision.log")
        fields = evidence.marker_fields(arm_dir)
        self.assertTrue((fields or {}).get("accuracy_status", "").startswith("taken"))

    def test_the_newest_window_that_measured_wins_over_a_newer_partial_one(self) -> None:
        receipt(self.root, "arm", window="tp12-20260101")
        receipt(self.root, "arm", cells=0, window="tp12-20260202")
        measured, _, arm_dir = evidence.find_measurement(self.root, "arm")
        self.assertTrue(measured)
        self.assertIn("tp12-20260101", arm_dir)


class NegativeControls(unittest.TestCase):
    """The predicates tonight's driver used. Each must fail on the input the campaign refuses."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_presence_only_accepts_a_partial_ladder(self) -> None:
        arm_dir = receipt(self.root, "arm", cells=0)
        self.assertTrue(presence_only(arm_dir), "the control must reproduce the 2026-11-04 defect")
        self.assertFalse(evidence.done(arm_dir)[0])

    def test_presence_only_accepts_a_failed_ladder(self) -> None:
        arm_dir = receipt(self.root, "arm", ladder="failed (rc=2)")
        self.assertTrue(presence_only(arm_dir))
        self.assertFalse(evidence.done(arm_dir)[0])


@unittest.skipUnless((REPO / "tools" / "next-arms.py").is_file(), "tools/next-arms.py not present")
class ParityWithThePlannerTool(unittest.TestCase):
    """The two implementations answer identically over the real tree and over shaped receipts."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tool = load_next_arms()

    def test_skip_source_matches_the_planner_tool_over_every_tracked_recipe(self) -> None:
        self.assertEqual(evidence.skips(REPO), self.tool.rejected_arms(str(REPO)))

    def test_done_predicate_matches_the_planner_tool(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        shapes = {
            "ok": receipt(root, "ok"),
            "partial": receipt(root, "partial", cells=0),
            "failed": receipt(root, "failed", ladder="failed (rc=2)"),
            "nonsense": receipt(root, "nonsense", ladder="maybe"),
        }
        empty = receipt(root, "empty", ladder="")
        (empty / "ladder.json").unlink()
        shapes["empty"] = empty
        for name, arm_dir in shapes.items():
            with self.subTest(shape=name):
                self.assertEqual(
                    evidence.done(arm_dir)[0],
                    self.tool.arm_measured(str(arm_dir))[0],
                )


if __name__ == "__main__":
    unittest.main()