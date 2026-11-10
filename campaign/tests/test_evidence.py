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

from .support import lane_doc, metrics, oom_watchdog, receipt, recipe, sidecar_receipt, write

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


class LadderField(unittest.TestCase):
    """The receipt's `ladder` field names its evidence; it is never blank beside `measured`.

    Measured 2026-11-08: the 753B sidecar arm's receipt read `marker_shape: sparkrun_benchmark`
    with `ladder: ""` while `ladder.json` held seven rows, so the cells had to be recovered from
    the CSV. A sidecar has no ladder field of its own; the field is read from the artefact.
    """

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_a_sidecar_names_the_artefact_and_its_rows(self) -> None:
        arm_dir = sidecar_receipt(self.root, "arm", cells=7, score="100")
        self.assertEqual(evidence.ladder_status(arm_dir), "measured \u2014 ladder.json (7 rows)")

    def test_a_sidecar_without_a_ladder_says_absent(self) -> None:
        arm_dir = sidecar_receipt(self.root, "arm", score="100")
        (arm_dir / "ladder.json").unlink()
        self.assertEqual(
            evidence.ladder_status(arm_dir),
            "absent \u2014 no ladder artefact in this receipt",
        )

    def test_a_broken_ladder_artefact_is_named_not_hidden(self) -> None:
        arm_dir = sidecar_receipt(self.root, "arm", cells=0, score=None)
        self.assertTrue(
            evidence.ladder_status(arm_dir).startswith("not a measurement \u2014 ladder.json"),
            evidence.ladder_status(arm_dir),
        )

    def test_a_flat_marker_verdict_is_copied_verbatim(self) -> None:
        self.assertEqual(evidence.ladder_status(receipt(self.root, "ok", ladder="ok")), "ok")
        self.assertEqual(
            evidence.ladder_status(receipt(self.root, "failed", ladder="failed (rc=2)")),
            "failed (rc=2)",
        )

    def test_negative_control_the_marker_copy_leaves_the_sidecar_ladder_blank(self) -> None:
        # The pre-fix receipt: copying only the marker's own field left it empty on a sidecar.
        arm_dir = sidecar_receipt(self.root, "arm", cells=7, score="100")
        self.assertEqual((evidence.marker_fields(arm_dir) or {}).get("ladder", ""), "",
                         "the control must reproduce the blank-ladder receipt")
        self.assertNotEqual(evidence.ladder_status(arm_dir), "")


class MetricsField(unittest.TestCase):
    """The receipt's `metrics_status` field: a sibling reader for the scrape's own artifacts.

    The artifact is read directly, never through `house.yaml`: `marker_fields()` returns only a
    synthesised dict for a `sparkrun_benchmark` sidecar, so a flat metrics key beside it would be
    dropped and that arm would read metrics-less. `None` means no artifact -- not `absent`, which
    is an engine that exposed nothing.
    """

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_captured_names_the_hosts_that_carried_a_body(self) -> None:
        arm_dir = receipt(self.root, "arm")
        metrics(arm_dir, hosts={
            "node-a": ("captured", "vllm:num_requests_running 0\n"),
            "node-b": ("captured", "vllm:num_requests_running 2\n"),
        })
        self.assertEqual(evidence.metrics_status(arm_dir), {
            "status": "captured",
            "reason": "http://127.0.0.1:8000/metrics fixture",
            "hosts": 2,
            "captured": 2,
        })

    def test_absent_keeps_the_scrapes_reason(self) -> None:
        arm_dir = receipt(self.root, "arm")
        metrics(arm_dir, status_text="# runtime=vllm port=8000\n"
                                    "absent host=node-a container=- url=- reason=http-404\n")
        self.assertEqual(evidence.metrics_status(arm_dir), {
            "status": "absent", "reason": "http-404", "hosts": 1, "captured": 0,
        })

    def test_wrong_port_carries_the_url_and_the_body_first_line(self) -> None:
        arm_dir = receipt(self.root, "arm")
        metrics(arm_dir, status_text=(
            "# runtime=vllm port=8000\n"
            "wrong_port host=node-a container=abc url=http://127.0.0.1:8000/metrics "
            "reason=not-prometheus: <html>\n"))
        verdict = evidence.metrics_status(arm_dir)
        self.assertEqual(verdict["status"], "wrong_port")
        self.assertEqual(verdict["reason"],
                         "http://127.0.0.1:8000/metrics not-prometheus: <html>")

    def test_an_unverifiable_probe_outranks_a_captured_peer(self) -> None:
        arm_dir = receipt(self.root, "arm")
        metrics(arm_dir, hosts={
            "node-a": ("captured", "vllm:num_requests_running 1\n"),
            "node-b": ("no_probe", ""),
        })
        self.assertEqual(evidence.metrics_status(arm_dir), {
            "status": "no_probe",
            "reason": "http://127.0.0.1:8000/metrics fixture",
            "hosts": 2,
            "captured": 1,
        })

    def test_no_artifact_reads_none_not_absent(self) -> None:
        self.assertIsNone(evidence.metrics_status(receipt(self.root, "arm")))

    def test_an_artifact_without_a_verdict_is_not_no_artifact(self) -> None:
        arm_dir = receipt(self.root, "arm")
        write(arm_dir / "metrics-node-a.txt", "truncated before the verdict line\n")
        self.assertEqual(evidence.metrics_status(arm_dir)["reason"],
                         "no host verdict in metrics-*.txt")

    def test_the_producer_format_is_read_verbatim(self) -> None:
        # Quoted from what `tools/run-arm.sh` actually emits (its `MetricsScrape` block writes
        # exactly this line into both files), so a fixture drift cannot green a contract the
        # producer does not write.
        header = ("captured host=head.test container=abc123def456 "
                  "url=http://127.0.0.1:8000/metrics reason=http-200")
        arm_dir = receipt(self.root, "arm")
        metrics(arm_dir, status_text=f"# runtime=vllm port=8000\n{header}\n")
        write(arm_dir / "metrics-head.test.txt",
              f"{header}\n# TYPE vllm:num_requests_running gauge\n"
              "vllm:num_requests_running 2\n")
        self.assertEqual(evidence.metrics_status(arm_dir), {
            "status": "captured",
            "reason": "http://127.0.0.1:8000/metrics http-200",
            "hosts": 1,
            "captured": 1,
        })

    def test_the_verdict_survives_a_sidecar_shaped_marker(self) -> None:
        arm_dir = sidecar_receipt(self.root, "arm", cells=2, score="100")
        metrics(arm_dir, hosts={"node-a": ("captured", "vllm:num_requests_running 1\n")})
        self.assertEqual(evidence.metrics_status(arm_dir), {
            "status": "captured",
            "reason": "http://127.0.0.1:8000/metrics fixture",
            "hosts": 1,
            "captured": 1,
        })

    def test_negative_control_a_capture_no_body_witnesses_is_a_disagreement(self) -> None:
        arm_dir = receipt(self.root, "arm")
        metrics(arm_dir, hosts={"node-a": ("captured", ""),
                                "node-b": ("captured", "  \n")})
        self.assertEqual(evidence.metrics_status(arm_dir), {
            "status": "disagrees",
            "reason": "metrics-status.txt records captured on 2 host(s), but 0 of 2 host "
                      "artifacts carried a body",
            "hosts": 2,
            "captured": 0,
        })


class OomWatchdogField(unittest.TestCase):
    """The receipt's `oom_watchdog` field: who killed the serve, read from its own artifact.

    earlyoom kills with SIGTERM, so the engine exits 143 and prints no traceback; a default of
    `clean` is how a kill gets attributed to the engine. `unknown` is a real answer (a 137/143 with
    no journal line, an unreadable journal, no result artifact), and the artifact is read directly
    because a `sparkrun_benchmark` sidecar drops every flat marker key.
    """

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_an_earlyoom_kill_carries_the_line_it_was_read_from(self) -> None:
        arm_dir = receipt(self.root, "arm")
        line = ('earlyoom: low memory! sending SIGTERM to process 4242 uid 1000 "python3"')
        oom_watchdog(arm_dir, state="earlyoom-terminated", exit_codes="143",
                     evidence_line=line, hosts={"node-a": ("ok", line)})
        verdict = evidence.oom_watchdog(arm_dir)
        self.assertEqual(verdict["state"], "earlyoom-terminated")
        self.assertIn(line, verdict["reason"], "the journal line is not quoted")
        self.assertIn("exit=143", verdict["reason"])

    def test_unknown_is_kept_verbatim_and_is_never_clean(self) -> None:
        arm_dir = receipt(self.root, "arm")
        oom_watchdog(arm_dir, state="unknown", exit_codes="143",
                     hosts={"node-a": ("ok", "-")})
        self.assertEqual(evidence.oom_watchdog(arm_dir)["state"], "unknown")
        self.assertEqual(evidence.oom_watchdog(arm_dir)["reason"],
                         "exit=143 unread=0 artifact=yes")

    def test_no_artifact_is_none_not_unknown(self) -> None:
        self.assertIsNone(evidence.oom_watchdog(receipt(self.root, "arm")))

    def test_an_artifact_without_the_header_reads_unknown(self) -> None:
        arm_dir = receipt(self.root, "arm")
        write(arm_dir / "oom-watchdog.txt", "truncated before the verdict\n")
        self.assertEqual(evidence.oom_watchdog(arm_dir)["state"], "unknown")

    def test_a_cgroup_limit_kill_is_named_not_collapsed_to_unknown(self) -> None:
        """`--memory` kill: serve SIGKILLed under `sleep infinity`, container exit 0.

        The campaign sees the fourth state and the capped container, instead of the `unknown`
        that a 137/143-only contract would report for a death with no exit code at all.
        """
        arm_dir = receipt(self.root, "arm")
        oom_watchdog(arm_dir, state="cgroup-oom", exit_codes="-", artifact="no",
                     cgroup_oom="sparkrun_t1_node_0",
                     evidence_line="oom sparkrun_t1_node_0", hosts={"node-a": ("ok", "-")})
        verdict = evidence.oom_watchdog(arm_dir)
        self.assertEqual(verdict["state"], "cgroup-oom")
        self.assertIn("cgroup_oom=sparkrun_t1_node_0", verdict["reason"],
                      "the capped container is not named")

    def test_a_capped_child_on_a_measured_arm_keeps_the_fact_and_stays_clean(self) -> None:
        arm_dir = receipt(self.root, "arm")
        oom_watchdog(arm_dir, state="clean", exit_codes="0",
                     cgroup_oom="sparkrun_t1_node_0", hosts={"node-a": ("ok", "-")})
        verdict = evidence.oom_watchdog(arm_dir)
        self.assertEqual(verdict["state"], "clean")
        self.assertIn("cgroup_oom=sparkrun_t1_node_0", verdict["reason"],
                      "the capped-child fact was dropped from the receipt")

    def test_an_unknown_verdict_is_not_promoted_by_the_fact_alone(self) -> None:
        arm_dir = receipt(self.root, "arm")
        oom_watchdog(arm_dir, state="unknown", exit_codes="137", artifact="no",
                     cgroup_oom="sparkrun_t1_node_0", hosts={"node-a": ("ok", "-")})
        self.assertEqual(evidence.oom_watchdog(arm_dir)["state"], "unknown",
                         "the fact alone is not a verdict; the header decides")

    def test_a_sidecar_marker_does_not_swallow_the_artifact(self) -> None:
        arm_dir = sidecar_receipt(self.root, "arm", cells=2)
        oom_watchdog(arm_dir, state="earlyoom-terminated", exit_codes="143",
                     evidence_line="earlyoom: low memory!", hosts={"node-a": ("ok", "-")})
        self.assertEqual(evidence.marker_fields(arm_dir)["shape"], "sparkrun_benchmark")
        self.assertEqual(evidence.oom_watchdog(arm_dir)["state"], "earlyoom-terminated")


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