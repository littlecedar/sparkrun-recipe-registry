"""The director's decisions, driven without a fleet and without a boot.

Acceptance items 1, 2, 7 and 8 are decided here: the skip lines are printed before anything can be
assigned, "measured" comes from the receipt's fields, a dead worker's hosts are reaped before the
arm is handed out again, and every arm that ran gets its own receipt.

The fleet is a fake that holds container names per host and removes them on request, so the
leftover paths run for real against test data. Nothing here starts a process.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from sparkrun_campaign import director as director_module
from sparkrun_campaign import plan, protocol, state

from .support import lane_doc, manifest, metrics, oom_watchdog, receipt, recipe, sidecar_receipt


def presence_only(arm_dir: str | Path) -> bool:
    """Tonight's completion predicate (a file exists and is non-empty). Kept as a control."""
    return any(
        (Path(arm_dir) / name).is_file() and (Path(arm_dir) / name).stat().st_size > 0
        for name in ("ladder.json", "house.yaml")
    )


def resume_trusting(order: list[str], arms: dict, free: list[str]):
    """Tonight's resume: read the state file, hand the next pending arm straight out."""
    for arm in order:
        record = arms[arm]
        if record["status"] == "pending":
            need = 2 if record["tp"] == 2 else 1
            if len(free) >= need:
                return arm, tuple(free[:need])
    return None


class FakeClock:
    def __init__(self, now: float = 1000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


class FakeFleet:
    """Container names per host, and a removal that can be made to fail."""

    def __init__(self, stubborn: bool = False):
        self.containers: dict[str, list[str]] = {}
        self.stubborn = stubborn
        self.reaped: list[tuple[tuple[str, ...], str]] = []

    def leftovers(self, hosts: list[str], recipe_path: str) -> list[tuple[str, str]]:
        return [(host, name) for host in hosts for name in self.containers.get(host, [])]

    def reap(self, hosts: list[str], recipe_path: str) -> dict:
        found = self.leftovers(hosts, recipe_path)
        self.reaped.append((tuple(hosts), recipe_path))
        if not self.stubborn:
            for host, _ in found:
                self.containers[host] = []
        return {"found": found, "removed": [] if self.stubborn else found,
                "after": self.leftovers(hosts, recipe_path)}


class CampaignCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        recipe(self.repo, "lane", "arm-one")
        recipe(self.repo, "lane", "arm-two")
        recipe(self.repo, "lane", "negative",
               marker="2026-11-01 \u2014 died at engine load (docs/lane.md:2)")
        lane_doc(self.repo)
        self.manifest_path = manifest(self.tmp / "manifest.json", [
            ("arm-one", "recipes/lane/arm-one.yaml", 2),
            ("arm-two", "recipes/lane/arm-two.yaml", 1),
            ("negative", "recipes/lane/negative.yaml", 1),
        ])
        self.receipts = self.tmp / "benchmarks"
        self.root = self.tmp / "campaign"
        self.clock = FakeClock()
        self.fleet = FakeFleet()
        self.out = io.StringIO()

    def build(self, *, receipts_root: Path | None = None, retries: int | None = None):
        campaign = state.Campaign.open(self.root / "state.json", campaign="test",
                                       hosts=("node-a", "node-b"), max_parallel=2,
                                       retries=retries)
        leader = director_module.Director(
            campaign,
            plan.load_manifest(self.manifest_path),
            root=self.root,
            receipts_root=receipts_root or self.receipts,
            repo_root=self.repo,
            run_arm_sh=self.repo / "tools" / "run-arm.sh",
            clock=self.clock,
            spawn=False,
            out=self.out,
            fleet_reap=self.fleet.reap,
        )
        return leader, campaign

    def receipt_fields(self, arm: str) -> dict:
        return json.loads((self.root / "receipts" / f"{arm}.json").read_text(encoding="utf-8"))


class SkipSource(CampaignCase):
    def test_skip_lines_are_printed_before_anything_can_be_assigned(self) -> None:
        leader, campaign = self.build()
        leader.prepare()
        text = self.out.getvalue()
        self.assertIn("skip: negative (measured-rejected, docs/lane.md:2)", text)
        self.assertNotIn("assign:", text, "nothing may be assigned before the skip source is printed")
        self.assertEqual(campaign.arm("negative")["status"], "skipped")
        fields = self.receipt_fields("negative")
        self.assertEqual(fields["status"], "skipped")
        self.assertIn("measured-rejected", fields["reason"])

        lease = leader.handle(protocol.poll("w1"))["lease"]
        self.assertEqual(lease["arm"], "arm-one")

    def test_a_stale_citation_stops_the_campaign_before_a_boot(self) -> None:
        (self.repo / "docs" / "lane.md").unlink()
        leader, _ = self.build()
        with self.assertRaises(plan.PlanError):
            leader.prepare()


class Validate(CampaignCase):
    def make(self, root: Path, hosts=("node-a", "node-b")):
        campaign = state.Campaign.open(root / "state.json", campaign="test", hosts=hosts,
                                        max_parallel=2)
        self.addCleanup(campaign.close)
        return director_module.Director(
            campaign, [], root=root, receipts_root=self.receipts, repo_root=self.repo,
            run_arm_sh=self.repo / "tools" / "run-arm.sh", clock=self.clock, spawn=False,
            out=self.out, fleet_reap=self.fleet.reap)

    def test_duplicate_hosts_are_refused(self) -> None:
        with self.assertRaises(state.StateError):
            self.make(self.tmp / "duplicate", hosts=("node-a", "node-a")).validate()

    def test_a_missing_executor_is_refused(self) -> None:
        with self.assertRaises(state.StateError):
            self.build()[0].validate()

    def test_an_executable_executor_passes(self) -> None:
        tool = self.repo / "tools" / "run-arm.sh"
        tool.parent.mkdir(parents=True, exist_ok=True)
        tool.write_text("#!/bin/sh\n", encoding="utf-8")
        tool.chmod(0o755)
        self.build()[0].validate()

    def test_an_overlong_socket_path_is_refused(self) -> None:
        with self.assertRaises(state.StateError):
            self.make(self.tmp / ("x" * 120)).validate()


class Status(CampaignCase):
    def test_state_is_readable_while_a_run_owns_the_lock(self) -> None:
        leader, campaign = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        receipt(self.receipts, lease["arm"])
        leader.handle(protocol.report(lease["id"], 0, "log run.log"))

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(director_module.status_campaign(self.root), 0)
        lines = out.getvalue().splitlines()
        self.assertEqual(lines[0], "campaign test: 1 pending, 1 measured, 1 skipped")
        self.assertTrue(any(line.startswith("  measured arm-one") for line in lines), lines)
        self.assertTrue(any(line.startswith("  pending  arm-two") for line in lines), lines)
        self.assertTrue(any(line.startswith("  skipped  negative") for line in lines), lines)

    def test_a_missing_state_file_returns_2(self) -> None:
        self.assertEqual(director_module.status_campaign(self.tmp / "nope"), 2)


class CompletionIsReadFromReceipts(CampaignCase):
    def test_a_partial_ladder_cannot_be_reported_as_measured_by_an_rc_of_zero(self) -> None:
        leader, campaign = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        arm_dir = receipt(self.receipts, lease["arm"], cells=0)
        reply = leader.handle(protocol.report(lease["id"], 0, "log run.log"))

        self.assertEqual(reply["status"], "failed")
        self.assertIn("not a measurement", campaign.arm("arm-one")["last"]["reason"])
        self.assertTrue(presence_only(arm_dir), "the control must reproduce the defect")
        fields = self.receipt_fields("arm-one")
        self.assertEqual(fields["status"], "failed")
        self.assertEqual(fields["ladder"], "ok", "the receipt keeps the marker it refused")

    def test_a_full_ladder_is_measured_and_the_receipt_names_its_artefacts(self) -> None:
        leader, _ = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        receipt(self.receipts, lease["arm"], cells=3, serve_logs=2,
                watchdog="WATCHDOG t=10s verdict=loading endpoint=down\n")
        reply = leader.handle(protocol.report(lease["id"], 0, "log run.log"))

        self.assertEqual(reply["status"], "measured")
        fields = self.receipt_fields("arm-one")
        self.assertTrue(fields["measured"])
        self.assertEqual(fields["artefacts"], ["ladder.json"])
        self.assertEqual(fields["serve_logs"], ["serve-node_0.log", "serve-node_1.log"])
        self.assertEqual(fields["watchdog"], "loading")
        self.assertEqual(fields["leftovers"], [])
        # The receipt states which house.yaml shape produced its outcome fields.
        self.assertEqual(fields["marker_shape"], "run-arm")
        self.assertEqual(fields["client"], {})

    def test_a_sidecar_receipt_names_the_ladder_it_was_measured_from(self) -> None:
        # 2026-11-08: this arm's receipt said measured with ladder "" while the artefact held
        # seven rows; the sidecar has no ladder field, so the field is read from the artefact.
        leader, _ = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        sidecar_receipt(self.receipts, lease["arm"], cells=7, score="100")
        reply = leader.handle(protocol.report(lease["id"], 0, "log run.log"))

        self.assertEqual(reply["status"], "measured")
        fields = self.receipt_fields("arm-one")
        self.assertEqual(fields["marker_shape"], "sparkrun_benchmark")
        self.assertEqual(fields["ladder"], "measured \u2014 ladder.json (7 rows)")
        self.assertEqual(fields["house_score"], "100")

    def test_a_sidecar_without_a_ladder_artefact_says_absent_not_blank(self) -> None:
        leader, _ = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        arm_dir = sidecar_receipt(self.receipts, lease["arm"], score="100")
        (arm_dir / "ladder.json").unlink()
        leader.handle(protocol.report(lease["id"], 0, "log run.log"))

        fields = self.receipt_fields("arm-one")
        self.assertEqual(fields["ladder"], "absent \u2014 no ladder artefact in this receipt")

    def test_the_receipt_carries_the_metrics_verdict_and_its_body_count(self) -> None:
        leader, _ = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        arm_dir = receipt(self.receipts, lease["arm"], cells=2)
        metrics(arm_dir, hosts={"node-a": ("captured", "vllm:num_requests_running 1\n"),
                                "node-b": ("absent", "")})
        leader.handle(protocol.report(lease["id"], 0, "log run.log"))

        self.assertEqual(self.receipt_fields("arm-one")["metrics_status"], {
            "status": "captured",
            "reason": "http://127.0.0.1:8000/metrics fixture",
            "hosts": 2,
            "captured": 1,
        })

    def test_a_sidecar_marker_does_not_swallow_the_metrics_artifact(self) -> None:
        # marker_fields() synthesises only shape/suite/framework/house_score for a
        # sparkrun_benchmark sidecar, so a metrics field read through it would vanish for every
        # sidecar-shaped arm; the sibling artifact reader is what keeps it.
        leader, _ = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        arm_dir = sidecar_receipt(self.receipts, lease["arm"], cells=2, score="100")
        metrics(arm_dir, hosts={"node-a": ("captured", "vllm:num_requests_running 1\n")})
        leader.handle(protocol.report(lease["id"], 0, "log run.log"))

        fields = self.receipt_fields("arm-one")
        self.assertEqual(fields["marker_shape"], "sparkrun_benchmark")
        self.assertEqual(fields["metrics_status"]["status"], "captured")
        self.assertEqual(fields["metrics_status"]["captured"], 1)

    def test_a_receipt_without_a_metrics_artifact_says_no_artifact(self) -> None:
        leader, _ = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        receipt(self.receipts, lease["arm"], cells=2)
        leader.handle(protocol.report(lease["id"], 0, "log run.log"))

        self.assertEqual(self.receipt_fields("arm-one")["metrics_status"],
                         {"status": "", "reason": "no artifact"})

    def test_the_receipt_carries_the_earlyoom_verdict(self) -> None:
        leader, _ = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        arm_dir = receipt(self.receipts, lease["arm"], cells=2)
        oom_watchdog(arm_dir, state="earlyoom-terminated", exit_codes="143",
                     evidence_line="earlyoom: low memory!", hosts={"node-a": ("ok", "-")})
        leader.handle(protocol.report(lease["id"], 0, "log run.log"))

        verdict = self.receipt_fields("arm-one")["oom_watchdog"]
        self.assertEqual(verdict["state"], "earlyoom-terminated")
        self.assertIn("exit=143", verdict["reason"])

    def test_a_receipt_without_an_oom_artifact_says_no_artifact(self) -> None:
        leader, _ = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        receipt(self.receipts, lease["arm"], cells=2)
        leader.handle(protocol.report(lease["id"], 0, "log run.log"))

        self.assertEqual(self.receipt_fields("arm-one")["oom_watchdog"],
                         {"state": "", "reason": "no artifact"})

    def test_the_receipt_keeps_the_serve_log_of_a_watchdog_reaped_arm(self) -> None:
        leader, _ = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        receipt(self.receipts, lease["arm"], cells=0, serve_logs=1,
                watchdog="WATCHDOG t=10s verdict=loading endpoint=down\n"
                         "WATCHDOG t=20s verdict=dead endpoint=down serve_pid=gone\n")
        leader.handle(protocol.report(lease["id"], 3, "watchdog: serve dead and stopped (rc=3)"))

        fields = self.receipt_fields("arm-one")
        self.assertEqual(fields["status"], "failed")
        self.assertEqual(fields["serve_logs"], ["serve-node_0.log"])
        self.assertEqual(fields["watchdog"], "dead")


class Leftovers(CampaignCase):
    def test_a_survivor_on_the_second_host_blocks_the_arm_and_is_recorded(self) -> None:
        self.fleet.stubborn = True
        leader, campaign = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        self.fleet.containers["node-b"] = ["sparkrun_t1_node_1"]
        receipt(self.receipts, "arm-one", cells=2)

        reply = leader.handle(protocol.report(lease["id"], 0, "log run.log"))

        self.assertEqual(reply["status"], "blocked")
        self.assertEqual(campaign.arm("arm-one")["status"], "blocked")
        self.assertEqual(self.receipt_fields("arm-one")["leftovers"],
                         ["sparkrun_t1_node_1 on node-b"])
        self.assertIn(("node-a", "node-b"), [hosts for hosts, _ in self.fleet.reaped])

    def test_a_clean_arm_records_no_leftover_after_reaping_what_it_found(self) -> None:
        leader, _ = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        self.fleet.containers["node-a"] = ["sparkrun_t1_node_0"]
        receipt(self.receipts, "arm-one", cells=2)

        reply = leader.handle(protocol.report(lease["id"], 0, "log run.log"))

        self.assertEqual(reply["status"], "measured")
        self.assertEqual(self.receipt_fields("arm-one")["leftovers"], [])
        self.assertEqual(self.fleet.containers["node-a"], [])


class Resume(CampaignCase):
    def test_a_dead_workers_hosts_are_reaped_before_the_arm_is_handed_out_again(self) -> None:
        leader, campaign = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        self.assertEqual(sorted(lease["hosts"]), ["node-a", "node-b"])
        self.fleet.containers["node-b"] = ["sparkrun_t1_node_1"]  # the rank-1 survivor
        campaign.close()                                          # the process died: no stop, no report
        self.clock.now += state.LEASE_TTL + 1

        fresh = state.Campaign.open(self.root / "state.json")
        try:
            self.assertEqual(fresh.expire(self.clock.now),
                             [{"arm": "arm-one", "hosts": ["node-a", "node-b"]}])
            # The control boots the arm again here; the director may not until the reap is proven.
            self.assertEqual(resume_trusting(fresh.order, fresh.arms(), ["node-a", "node-b"]),
                             ("arm-one", ("node-a", "node-b")))
            handed = plan.next_assignment(fresh.order, fresh.arms(), ["node-a", "node-b"], 0)
            self.assertNotEqual(handed[0] if handed else None, "arm-one")
        finally:
            fresh.close()

        leader, campaign = self.build()
        leader.prepare()

        self.assertEqual(campaign.arm("arm-one")["needs_reap"], [])
        self.assertEqual(self.fleet.reaped[-1], (("node-a", "node-b"), "recipes/lane/arm-one.yaml"))
        self.assertEqual(leader.handle(protocol.poll("w1"))["lease"]["arm"], "arm-one")

    def test_a_measurement_already_on_disk_is_not_booted_again(self) -> None:
        leader, campaign = self.build()
        leader.prepare()
        leader.handle(protocol.poll("w1"))                    # arm-one leased, worker then dies
        receipt(self.receipts, "arm-one", cells=4)            # the numbers landed; no report came
        campaign.close()
        self.clock.now += state.LEASE_TTL + 1

        leader, campaign = self.build()
        leader.prepare()

        self.assertEqual(campaign.arm("arm-one")["status"], "measured")
        self.assertIn("measured: arm-one", self.out.getvalue())
        self.assertTrue((self.root / "receipts" / "arm-one.json").is_file())
        self.assertEqual(leader.handle(protocol.poll("w1"))["lease"]["arm"], "arm-two")

    def test_a_report_for_a_reclaimed_lease_is_ignored(self) -> None:
        leader, campaign = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        self.clock.now += state.LEASE_TTL + 1

        reply = leader.handle(protocol.report(lease["id"], 0))

        self.assertTrue(reply.get("late"))
        self.assertEqual(campaign.arm("arm-one")["status"], "pending")


class Draining(CampaignCase):
    def test_the_campaign_is_drained_only_when_no_arm_is_left_to_run(self) -> None:
        leader, campaign = self.build()
        leader.prepare()
        self.assertFalse(leader.drained())
        campaign.record_skip("arm-two", {"arm": "arm-two", "verdict": "measured-rejected",
                                        "doc": "docs/lane.md:2", "since": "2026-11-01"})
        campaign.mark_measured("arm-one", str(self.receipts), "fixture")
        self.assertTrue(leader.drained())


class Retries(CampaignCase):
    def test_a_restart_adopts_the_invocations_retry_budget(self) -> None:
        leader, campaign = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        receipt(self.receipts, lease["arm"], cells=0)         # partial ladder: failed, not measured
        self.assertEqual(leader.handle(protocol.report(lease["id"], 0, "log run.log"))["status"],
                         "failed")
        self.assertEqual(campaign.arm("arm-one")["failures"], 1)
        campaign.close()

        resumed = state.Campaign.open(self.root / "state.json", retries=1)
        self.addCleanup(resumed.close)
        self.assertEqual(resumed.retries, 1)
        self.assertEqual(
            plan.next_assignment(resumed.order, resumed.arms(), ["node-a", "node-b"],
                                 resumed.retries),
            ("arm-one", ("node-a", "node-b")),
            "the arm the stored retries=0 made terminal is inside the new budget")


class ReceiptsRoot(CampaignCase):
    def test_the_receipts_root_is_pinned_into_every_arm_that_can_still_run(self) -> None:
        leader, campaign = self.build()
        leader.prepare()
        for arm in ("arm-one", "arm-two"):
            self.assertEqual(campaign.arm(arm)["env"]["ARM_RECEIPTS_ROOT"], str(self.receipts))
        lease = leader.handle(protocol.poll("w1"))["lease"]
        self.assertEqual(lease["env"]["ARM_RECEIPTS_ROOT"], str(self.receipts),
                         "the executor writes where the evidence reader looks")

    def test_a_later_run_moves_a_pending_arms_receipts_root(self) -> None:
        leader, campaign = self.build()
        leader.prepare()
        campaign.close()

        elsewhere = self.tmp / "elsewhere"
        leader, campaign = self.build(receipts_root=elsewhere)
        leader.prepare()
        self.assertEqual(campaign.arm("arm-two")["env"]["ARM_RECEIPTS_ROOT"], str(elsewhere))
        self.assertEqual(campaign.arm("negative")["env"]["ARM_RECEIPTS_ROOT"],
                         str(self.receipts), "a skipped arm's record stays final")


if __name__ == "__main__":
    unittest.main()