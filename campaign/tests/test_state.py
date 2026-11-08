"""Persisted state: atomic writes, the single-director lock, and lease expiry (acceptance item 7)."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from sparkrun_campaign import state


class Persistence(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.path = self.root / "state.json"
        self.campaign = state.Campaign.open(self.path, campaign="test", hosts=("node-a", "node-b"),
                                            max_parallel=2)
        self.addCleanup(self.campaign.close)

    def test_a_reloaded_campaign_keeps_every_arm_status(self) -> None:
        self.campaign.add("one", "recipes/lane/one.yaml")
        self.campaign.add("two", "recipes/lane/two.yaml", tp=2)
        self.campaign.assign("one", "w1", ["node-a"], now=10.0)
        self.campaign.close()
        reloaded = state.Campaign.open(self.path)
        self.addCleanup(reloaded.close)
        self.assertEqual(reloaded.order, ["one", "two"])
        self.assertEqual(reloaded.arm("one")["status"], "leased")
        self.assertEqual(reloaded.arm("two")["tp"], 2)
        self.assertEqual(reloaded.arm("one")["lease"]["worker"], "w1")

    def test_a_write_that_cannot_be_encoded_leaves_the_previous_document(self) -> None:
        state.write_json(self.path, {"generation": 1})
        with self.assertRaises(TypeError):
            state.write_json(self.path, {"generation": 2, "bad": object()})
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), {"generation": 1})
        self.assertFalse((self.root / "state.json.tmp").exists())

    def test_a_second_director_is_refused(self) -> None:
        with self.assertRaises(state.StateError):
            state.Campaign.open(self.path)

    def test_an_explicit_retry_budget_overrules_the_stored_one(self) -> None:
        # The defect: a restart with --retries 1 left a terminal arm terminal because the state's
        # `retries=0` won. The invocation is the newer decision.
        self.campaign.add("one", "recipes/lane/one.yaml")
        self.campaign.assign("one", "w1", ["node-a"], now=10.0)
        self.campaign.finish("one", status=state.FAILED, rc=0, reason="partial ladder")
        self.assertEqual(self.campaign.retries, 0)
        self.campaign.close()

        reopened = state.Campaign.open(self.path, retries=1)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.retries, 1)
        self.assertEqual(reopened.arm("one")["failures"], 1)

    def test_an_omitted_retry_budget_keeps_the_stored_one(self) -> None:
        self.campaign.close()
        first = state.Campaign.open(self.path, retries=2)
        first.close()
        reopened = state.Campaign.open(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.retries, 2)

    def test_a_new_campaign_needs_a_name(self) -> None:
        with self.assertRaises(state.StateError):
            state.Campaign.open(self.root / "other.json")


class Leases(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.campaign = state.Campaign.open(self.root / "state.json", campaign="test",
                                            hosts=("node-a", "node-b"))
        self.addCleanup(self.campaign.close)
        self.campaign.add("one", "recipes/lane/one.yaml", tp=2)
        self.campaign.add("two", "recipes/lane/two.yaml")

    def test_a_lease_carries_everything_the_worker_needs(self) -> None:
        lease = self.campaign.assign("one", "w1", ["node-a", "node-b"], now=100.0)
        for key in ("id", "arm", "path", "tp", "env", "hosts", "expires_at"):
            self.assertIn(key, lease)
        self.assertEqual(lease["path"], "recipes/lane/one.yaml")
        self.assertEqual(lease["tp"], 2)

    def test_a_live_lease_holds_every_host_it_took(self) -> None:
        self.campaign.assign("one", "w1", ["node-a", "node-b"], now=100.0)
        self.assertEqual(self.campaign.free_hosts(100.0), [])
        self.assertEqual(self.campaign.free_hosts(100.0 + state.LEASE_TTL + 1), ["node-a", "node-b"])

    def test_a_beat_extends_the_deadline_and_a_late_beat_does_not(self) -> None:
        lease = self.campaign.assign("one", "w1", ["node-a"], now=100.0)
        self.assertTrue(self.campaign.beat(lease["id"], now=100.0 + state.LEASE_TTL - 1))
        self.assertFalse(self.campaign.beat(lease["id"], now=100.0 + state.LEASE_TTL * 4))

    def test_an_expired_lease_comes_back_needing_a_reap_of_every_host(self) -> None:
        self.campaign.assign("one", "w1", ["node-a", "node-b"], now=100.0)
        expired = self.campaign.expire(100.0 + state.LEASE_TTL + 1)
        self.assertEqual(expired, [{"arm": "one", "hosts": ["node-a", "node-b"]}])
        record = self.campaign.arm("one")
        self.assertEqual(record["status"], "pending")
        self.assertEqual(record["needs_reap"], ["node-a", "node-b"])
        self.assertIsNone(record["lease"])

    def test_a_cleared_reap_returns_a_blocked_arm_to_the_queue(self) -> None:
        self.campaign.assign("one", "w1", ["node-a"], now=100.0)
        self.campaign.expire(100.0 + state.LEASE_TTL + 1)
        self.campaign.block("one", "cannot verify leftovers on node-a", ["node-a"])
        self.assertEqual(self.campaign.arm("one")["status"], "blocked")
        self.campaign.cleared("one")
        self.assertEqual(self.campaign.arm("one")["status"], "pending")
        self.assertEqual(self.campaign.arm("one")["needs_reap"], [])

    def test_a_blocked_arm_keeps_what_the_report_knew(self) -> None:
        self.campaign.assign("one", "w1", ["node-a"], now=100.0)
        self.campaign.block("one", "container left behind", ["node-a"], rc=6, measured=True)
        last = self.campaign.arm("one")["last"]
        self.assertEqual(last["rc"], 6)
        self.assertTrue(last["measured"])

    def test_history_is_bounded(self) -> None:
        for _ in range(state.HISTORY_CAP + 5):
            self.campaign.event("one", "note")
        self.assertEqual(len(self.campaign.arm("one")["history"]), state.HISTORY_CAP)


if __name__ == "__main__":
    unittest.main()