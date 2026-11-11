"""The fleet lease and the head-host gate: who may take how many ranks, and under what proof.

Owner rulings 2026-11-11: a campaign lease is the only claim for a multi-machine boot (a rank
another holder leases is honoured, and a boot that cannot be leased is refused); `.30` may host a
memory-risky shape only inside a window named per boot and with the guardrails proven at lease
time; and the six-node TP=2 x PP=3 shape is expressible in the manifest path as six named ranks.

Every test runs offline: the ledger is a file in a temporary checkout, the director's fleet is a
fake, and the head's guardrail probe is injected, so no test can ssh or boot.
"""

from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from sparkrun_campaign import director as director_module
from sparkrun_campaign import guardrails, leases, plan, protocol, state

from .support import recipe, receipt, write
from .test_director import FakeClock, FakeFleet

HEAD = ("node.30", "node.31", "node.32", "node.33", "node.34", "node.35")


class LedgerCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.clock = FakeClock()
        self.ledger = leases.Ledger(self.repo / leases.LEDGER, clock=self.clock)

    def test_an_expired_lease_holds_nothing(self) -> None:
        self.ledger.acquire("session-a", ["n1", "n2"], ttl=10)
        self.assertEqual(sorted(self.ledger.held_hosts(["n1", "n2"])), ["n1", "n2"])
        self.clock.now += 11
        self.assertEqual(self.ledger.held_hosts(["n1", "n2"]), {})
        self.assertEqual(self.ledger.leases(), [])

    def test_a_second_holder_cannot_take_a_leased_rank(self) -> None:
        self.ledger.acquire("session-a", ["n1", "n2"], ttl=600)
        with self.assertRaises(leases.LeaseError) as ctx:
            self.ledger.acquire("session-b", ["n2", "n3"], ttl=600)
        self.assertIn("n2", str(ctx.exception))
        self.assertIn("session-a", str(ctx.exception))
        self.assertEqual(len(self.ledger.leases()), 1, "a refused claim writes nothing")

    def test_the_same_holder_reclaims_its_own_ranks(self) -> None:
        self.ledger.acquire("session-a", ["n1", "n2"], ttl=600)
        second = self.ledger.acquire("session-a", ["n1", "n2"], ttl=600)
        live = self.ledger.leases()
        self.assertEqual([lease["id"] for lease in live], [second["id"]],
                         "one live record per rank set")

    def test_a_declared_window_holds_every_rank_and_refuses_a_claim(self) -> None:
        write(self.repo / ".local" / "fleet-window.lock", "session ds4-kimi-fit .31-.34\n")
        held = self.ledger.held_hosts(["n1", "n2"])
        self.assertEqual(set(held), {"n1", "n2"})
        self.assertIn("declared window", held["n1"])
        with self.assertRaises(leases.LeaseError) as ctx:
            self.ledger.acquire("session-b", ["n1"], ttl=600)
        self.assertIn("declared window", str(ctx.exception))

    def test_renew_keeps_a_live_claim_and_release_drops_it(self) -> None:
        record = self.ledger.acquire("session-a", ["n1"], ttl=10)
        self.clock.now += 8
        self.assertTrue(self.ledger.renew(record["id"]))
        self.clock.now += 8
        self.assertTrue(self.ledger.held_hosts(["n1"]))
        self.assertTrue(self.ledger.release(record["id"]))
        self.assertEqual(self.ledger.held_hosts(["n1"]), {})


class LeaseCommand(unittest.TestCase):
    """The manual session's entry point writes the record the director reads."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()

    def test_the_command_writes_one_record_and_a_peer_claim_is_refused(self) -> None:
        argv = ["lease", "--hosts", "n1,n2", "--holder", "manual-a", "--ttl", "600",
                "--window", "kimi-six-node", "--repo-root", str(self.repo)]
        self.assertEqual(director_module.main(argv), 0)
        ledger = leases.Ledger(self.repo / leases.LEDGER)
        live = ledger.leases()
        self.assertEqual(len(live), 1)
        self.assertEqual(live[0]["hosts"], ["n1", "n2"])
        self.assertEqual(live[0]["holder"], "manual-a")
        self.assertEqual(live[0]["window"], "kimi-six-node")
        self.assertEqual(ledger.held_hosts(["n1"])["n1"][:5], "lease")

        refused = director_module.main(["lease", "--hosts", "n2", "--holder", "manual-b",
                                        "--ttl", "600", "--repo-root", str(self.repo)])
        self.assertEqual(refused, 3, "a refused claim exits non-zero and writes nothing")
        self.assertEqual(len(ledger.leases()), 1)

    def test_a_lease_without_an_expiry_is_refused(self) -> None:
        code = director_module.main(["lease", "--hosts", "n1", "--holder", "manual-a",
                                     "--repo-root", str(self.repo)])
        self.assertEqual(code, 2)
        self.assertEqual(leases.Ledger(self.repo / leases.LEDGER).leases(), [])


class GuardrailProof(unittest.TestCase):
    ARGV = "4242 /usr/bin/earlyoom -m 4,1 -s 100,95 -r 3600"
    SAMPLER = "777 bash /home/red/benchmarks/tp4-x/mem-guard.sh 6.0"

    def runner(self, calls: list[tuple[str, str]], *, units: dict[str, str] | None = None,
               earlyoom: str = "", sampler: str = "") -> object:
        def run(host: str, script: str) -> tuple[int, str]:
            calls.append((host, script))
            if script == "pgrep -a earlyoom":
                return (0, earlyoom) if earlyoom else (1, "")
            if script.startswith("systemctl show"):
                return 0, (units or {}).get(script.split()[-1], "-900")
            if script.startswith("pgrep -af"):
                return (0, sampler) if sampler else (1, "")
            return 1, ""

        return run

    def test_every_guardrail_is_quoted_from_the_running_host(self) -> None:
        calls: list[tuple[str, str]] = []
        proof = guardrails.prove("host-a", run=self.runner(  # type: ignore[arg-type]
            calls, earlyoom=self.ARGV, sampler=self.SAMPLER))
        self.assertIn(f"earlyoom argv: {self.ARGV}", proof)
        self.assertIn("OOMScoreAdjust ssh.service = -900", proof)
        self.assertIn("OOMScoreAdjust beegfs-storage.service = -900", proof)
        self.assertIn(f"memory sampler: {self.SAMPLER}", proof)
        self.assertEqual(len(calls), 1 + len(guardrails.UNITS) + 1)

    def test_a_non_negative_oom_score_refuses_naming_the_unit(self) -> None:
        run = self.runner([], earlyoom=self.ARGV, sampler=self.SAMPLER,
                          units={"NetworkManager.service": "0"})
        with self.assertRaises(plan.PlanError) as ctx:
            guardrails.prove("host-a", run=run)  # type: ignore[arg-type]
        self.assertIn("host-a", str(ctx.exception))
        self.assertIn("NetworkManager.service", str(ctx.exception))
        self.assertIn("0, not negative", str(ctx.exception))

    def test_a_missing_earlyoom_or_sampler_refuses_rather_than_defaulting_clean(self) -> None:
        with self.assertRaises(plan.PlanError) as ctx:
            guardrails.prove("host-a", run=self.runner(  # type: ignore[arg-type]
                [], sampler=self.SAMPLER))
        self.assertIn("earlyoom is not running", str(ctx.exception))
        with self.assertRaises(plan.PlanError) as ctx:
            guardrails.prove("host-a", run=self.runner([], earlyoom=self.ARGV))  # type: ignore[arg-type]
        self.assertIn("memory sampler", str(ctx.exception))

    def test_a_disabled_threshold_is_not_a_guard(self) -> None:
        with self.assertRaises(plan.PlanError) as ctx:
            guardrails.prove("host-a", run=self.runner(  # type: ignore[arg-type]
                [], earlyoom="1 earlyoom -m 0 -s 100,95", sampler=self.SAMPLER))
        self.assertIn("disables the kill", str(ctx.exception))


class DirectorCase(unittest.TestCase):
    """A manifest campaign over a declared host set; the fleet and the head probe are fakes."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        for arm in ("pair", "solo", "six"):
            recipe(self.repo, "lane", arm)
        self.run_arm = write(self.repo / "tools" / "run-arm.sh", "#!/bin/sh\n")
        self.run_arm.chmod(0o755)
        self.root = self.tmp / "campaign"
        self.receipts = self.tmp / "benchmarks"
        self.clock = FakeClock()
        self.fleet = FakeFleet()
        self.out = io.StringIO()
        self.ledger = leases.Ledger(self.repo / leases.LEDGER, clock=self.clock)

    def build(self, entries: list[dict], *, hosts: tuple[str, ...] = ("node-a", "node-b"),
              head_proof=None):
        path = write(self.tmp / "manifest.json", json.dumps(entries))
        campaign = state.Campaign.open(self.root / "state.json", campaign="test",
                                       hosts=hosts, max_parallel=2)
        self.addCleanup(campaign.close)
        proof = head_proof or (lambda host: self.fail(f"head_proof called unexpectedly for {host}"))
        leader = director_module.Director(
            campaign, plan.load_manifest(path),
            root=self.root, receipts_root=self.receipts, repo_root=self.repo,
            run_arm_sh=self.run_arm, clock=self.clock, spawn=False, out=self.out,
            fleet_reap=self.fleet.reap, ledger=self.ledger, head_proof=proof)
        leader.prepare()
        return leader, campaign

    def arm(self, name: str, **fields) -> dict:
        return {"arm": name, "path": f"recipes/lane/{name}.yaml", **fields}


class SingleClaim(DirectorCase):
    """R1: one lease is the only claim for a multi-rank boot, and another holder is honoured."""

    def test_a_multi_rank_boot_writes_its_lease_before_assignment(self) -> None:
        leader, _ = self.build([self.arm("pair", tp=2)])
        lease = leader.handle(protocol.poll("w1"))["lease"]
        self.assertEqual(lease["hosts"], ["node-a", "node-b"])

        live = self.ledger.leases()
        self.assertEqual(len(live), 1)
        self.assertEqual(live[0]["hosts"], ["node-a", "node-b"])
        self.assertEqual(live[0]["holder"], "sparkrun-campaign:test")
        self.assertEqual(live[0]["arm"], "pair")
        with self.assertRaises(leases.LeaseError):
            leases.Ledger(self.repo / leases.LEDGER, clock=self.clock).acquire(
                "another-session", ["node-a", "node-b"], ttl=600)

    def test_a_single_rank_boot_does_not_write_a_lease(self) -> None:
        leader, _ = self.build([self.arm("solo", tp=1)])
        self.assertEqual(leader.handle(protocol.poll("w1"))["lease"]["hosts"], ["node-a"])
        self.assertEqual(self.ledger.leases(), [])

    def test_a_rank_held_by_another_session_is_not_placed(self) -> None:
        self.ledger.acquire("another-session", ["node-a"], ttl=600, window="their-window")
        leader, _ = self.build([self.arm("pair", tp=2)])
        reply = leader.handle(protocol.poll("w1"))
        self.assertEqual(reply["op"], "idle")
        self.assertIn("lease-held: node-a (lease", self.out.getvalue())
        self.assertNotIn("assign:", self.out.getvalue())
        self.assertEqual(self.ledger.held_hosts(["node-a"])["node-a"][:5], "lease")

    def test_a_declared_window_lock_holds_the_whole_declared_set(self) -> None:
        write(self.repo / ".local" / "fleet-window.lock", "session they-declared\n")
        leader, _ = self.build([self.arm("pair", tp=2)])
        self.assertEqual(leader.handle(protocol.poll("w1"))["op"], "idle")
        self.assertIn("lease-held: node-a (declared window", self.out.getvalue())
        self.assertNotIn("assign:", self.out.getvalue())

    def test_the_lease_is_released_when_the_arm_reports(self) -> None:
        leader, _ = self.build([self.arm("pair", tp=2)])
        lease = leader.handle(protocol.poll("w1"))["lease"]
        self.assertEqual(len(self.ledger.leases()), 1)
        receipt(self.receipts, "pair")
        self.assertEqual(leader.handle(protocol.report(lease["id"], 0, "log run.log"))["status"],
                         "measured")
        self.assertEqual(self.ledger.leases(), [])

    def test_a_lease_refused_between_placement_and_claim_is_not_attempted(self) -> None:
        leader, _ = self.build([self.arm("pair", tp=2)])

        def steal(hosts, now=None, *, holder=""):
            # The peer writes its claim after this director read the ledger, before the lease.
            self.ledger.acquire("another-session", hosts, ttl=600)
            return {}

        leader.ledger.held_hosts = steal  # type: ignore[method-assign]
        self.assertEqual(leader.handle(protocol.poll("w1"))["op"], "idle")
        self.assertIn("lease-refused: pair on node-a,node-b", self.out.getvalue())
        self.assertNotIn("assign:", self.out.getvalue())


class HeadWaiver(DirectorCase):
    """R2: `.30` hosts a risky shape only on its own declaration, with the proof at lease time."""

    HOSTS = ("node.30", "node.31")

    def waived(self, **extra) -> dict:
        return self.arm("pair", tp=2, memory_risky=True, allow_hosts=["node.30"],
                        window="kimi-six-node-20261112", **extra)

    def test_a_missing_guardrail_blocks_the_arm_naming_host_and_check(self) -> None:
        def proof(host: str) -> list[str]:
            raise plan.PlanError(f"{host}: OOMScoreAdjust on ssh.service is 0, not negative")

        leader, campaign = self.build([self.waived()], hosts=self.HOSTS, head_proof=proof)
        self.assertEqual(leader.handle(protocol.poll("w1"))["op"], "idle")
        self.assertNotIn("assign:", self.out.getvalue(), "a refused waiver must never boot")
        self.assertEqual(campaign.arm("pair")["status"], "blocked")
        reason = campaign.arm("pair")["last"]["reason"]
        self.assertIn("node.30", reason)
        self.assertIn("ssh.service", reason)

    def test_a_proven_waiver_places_the_head_last_and_records_the_quote(self) -> None:
        seen: list[str] = []

        def proof(host: str) -> list[str]:
            seen.append(host)
            return [f"earlyoom argv: 4242 earlyoom -m 4,1 -s 100,95",
                    f"OOMScoreAdjust ssh.service = -900",
                    f"memory sampler: 777 mem-guard.sh 6.0"]

        leader, _ = self.build([self.waived()], hosts=self.HOSTS, head_proof=proof)
        lease = leader.handle(protocol.poll("w1"))["lease"]
        self.assertEqual(seen, ["node.30"], "the proof is taken before the lease")
        self.assertEqual(lease["hosts"], ["node.31", "node.30"], "the safe rank comes first")
        self.assertIn("lease-proof: node.30 OOMScoreAdjust ssh.service = -900",
                      self.out.getvalue())
        record = self.ledger.leases()[0]
        self.assertEqual(record["window"], "kimi-six-node-20261112")
        self.assertIn("earlyoom argv: 4242 earlyoom -m 4,1 -s 100,95", record["proof"])

    def test_a_waiver_without_a_window_name_refuses_the_plan(self) -> None:
        with self.assertRaises(plan.PlanError) as ctx:
            self.build([self.arm("pair", tp=2, memory_risky=True, allow_hosts=["node.30"])],
                       hosts=self.HOSTS)
        self.assertIn("without a declared `window` name", str(ctx.exception))

    def test_a_waiver_without_the_risk_declaration_refuses_the_plan(self) -> None:
        with self.assertRaises(plan.PlanError) as ctx:
            self.build([self.arm("pair", tp=2, allow_hosts=["node.30"], window="w")],
                       hosts=self.HOSTS)
        self.assertIn("without memory_risky", str(ctx.exception))

    def test_the_undeclared_default_still_never_takes_the_head(self) -> None:
        # The same shape with no waiver: one safe rank for a two-rank arm, so the arm waits and
        # is never narrowed onto `.30` (the 2026-11-10 defect).
        leader, _ = self.build([self.arm("pair", tp=2, memory_risky=True)], hosts=self.HOSTS)
        self.assertEqual(leader.handle(protocol.poll("w1"))["op"], "idle")
        self.assertNotIn("assign:", self.out.getvalue())


class SixNodeShape(DirectorCase):
    """R3: tp 2 x pp 3 over six hosts, leased as six named ranks."""

    HOSTS = HEAD

    def test_tp2_pp3_leases_all_six_ranks(self) -> None:
        entries = plan.load_manifest(write(self.tmp / "six.json", json.dumps(
            [{"arm": "six", "path": "recipes/lane/six.yaml", "tp": 2, "pp": 3}])))
        self.assertEqual((entries[0]["tp"], entries[0]["pp"], entries[0]["nodes"]), (2, 3, 6))

        leader, _ = self.build([self.arm("six", tp=2, pp=3)], hosts=self.HOSTS)
        lease = leader.handle(protocol.poll("w1"))["lease"]
        self.assertEqual(sorted(lease["hosts"]), sorted(self.HOSTS))
        self.assertEqual((lease["tp"], lease["pp"], lease["nodes"]), (2, 3, 6))
        self.assertEqual(len(lease["hosts"]), 6)
        self.assertEqual(self.ledger.leases()[0]["hosts"], list(lease["hosts"]))

    def test_any_held_rank_refuses_the_six_node_lease(self) -> None:
        self.ledger.acquire("another-session", ["node.32"], ttl=600)
        leader, _ = self.build([self.arm("six", tp=2, pp=3)], hosts=self.HOSTS)
        self.assertEqual(leader.handle(protocol.poll("w1"))["op"], "idle")
        self.assertIn("lease-held: node.32", self.out.getvalue())
        self.assertNotIn("assign:", self.out.getvalue())

    def test_the_lease_names_six_ranks_and_a_five_host_set_is_not_enough(self) -> None:
        leader, _ = self.build([self.arm("six", tp=2, pp=3)], hosts=self.HOSTS[:5])
        self.assertEqual(leader.handle(protocol.poll("w1"))["op"], "idle")
        self.assertNotIn("assign:", self.out.getvalue())


if __name__ == "__main__":
    unittest.main()
