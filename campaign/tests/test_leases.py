"""The fleet lease and the head-host gate: who may take how many ranks, and under what proof.

Owner rulings 2026-11-11: a campaign lease is the only claim for a multi-machine boot (a rank
another holder leases is honoured, and a boot that cannot be leased is refused); `.30` may host a
memory-risky shape only inside a window named per boot and with the guardrails proven at lease
time; and the six-node TP=2 x PP=3 shape is expressible in the manifest path as six named ranks.

Every test runs offline: the ledger is a file in a temporary checkout, the director's fleet is a
fake, and the head's guardrail probe is injected, so no test can ssh or boot.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_a_syncthing_conflict_copy_is_not_a_declared_window(self) -> None:
        # The real .local/ today: no fleet-window.lock, two sync-conflict copies. A conflict copy
        # blocking every lease would be its own outage, so only the canonical name is read.
        write(self.repo / ".local" / "fleet-window.sync-conflict-20261110-115128-Y5KSV46.lock",
              "session ds4-kimi-fit .31-.34\n")
        self.assertEqual(self.ledger.held_hosts(["n1", "n2"]), {})
        record = self.ledger.acquire("session-a", ["n1", "n2"], ttl=600)
        self.assertEqual(record["hosts"], ["n1", "n2"])

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

    def test_list_reads_a_missing_ledger_and_creates_none(self) -> None:
        code = director_module.main(["lease", "--list", "--repo-root", str(self.repo)])
        self.assertEqual(code, 0)
        self.assertFalse((self.repo / leases.LEDGER).exists())

    def test_a_lease_without_an_expiry_is_refused(self) -> None:
        code = director_module.main(["lease", "--hosts", "n1", "--holder", "manual-a",
                                     "--repo-root", str(self.repo)])
        self.assertEqual(code, 2)
        self.assertEqual(leases.Ledger(self.repo / leases.LEDGER).leases(), [])


class GuardrailProof(unittest.TestCase):
    """Earlyoom fixtures are the 2026-11-11 capture; the guard is now a mechanism check.

    The capture's eleven stale `mem-guard.sh` processes are the control: there is no process scan
    any more, so they cannot satisfy anything. Only an executable script under the declared
    window's directory does, because that is what the executor will arm after the launch.
    """

    #: `.30`: the daemon plus two `--dryrun` processes, which have no thresholds.
    EARLYOOM = ("453964 /usr/bin/earlyoom -m 4,1 -s 100,95 --prefer (vllm|VLLM|sglang) "
                "--avoid (beegfs|mgmtd|meta|storage|systemd|sshd)\n"
                "1930915 earlyoom --dryrun\n3796314 earlyoom --dryrun")
    WINDOW = "tp4-20261110b"
    GUARD_OK = f"/home/red/benchmarks/{WINDOW}/mem-guard.sh"
    GUARD_MISSING = f"missing /home/red/benchmarks/{WINDOW}/mem-guard.sh"

    def runner(self, calls: list[tuple[str, str]], *, units: dict[str, str] | None = None,
               earlyoom: str = "", guard: tuple[int, str] | None = None) -> object:
        def run(host: str, script: str) -> tuple[int, str]:
            calls.append((host, script))
            if script == "pgrep -a earlyoom":
                return (0, earlyoom) if earlyoom else (1, "")
            if script.startswith("systemctl show"):
                return 0, (units or {}).get(script.split()[-1], "-900")
            if "mem-guard.sh" in script:
                return guard if guard is not None else (1, self.GUARD_MISSING)
            return 1, ""

        return run

    def prove(self, run, *, window: str = WINDOW) -> list[str]:
        return guardrails.prove("host-a", window=window, run=run)  # type: ignore[arg-type]

    def test_every_guardrail_is_quoted_from_the_running_host(self) -> None:
        calls: list[tuple[str, str]] = []
        proof = self.prove(self.runner(calls, earlyoom=self.EARLYOOM,
                                       guard=(0, self.GUARD_OK)))
        self.assertIn("earlyoom argv: 453964 /usr/bin/earlyoom -m 4,1 -s 100,95", proof[0])
        self.assertIn("OOMScoreAdjust ssh.service = -900", proof)
        self.assertIn("OOMScoreAdjust beegfs-storage.service = -900", proof)
        self.assertIn(f"guard script: {self.GUARD_OK}", proof)
        self.assertEqual(len(calls), 1 + len(guardrails.UNITS) + 1)
        guard_script = next(script for _, script in calls if "mem-guard.sh" in script)
        self.assertIn(f"/{self.WINDOW}/mem-guard.sh", guard_script)
        self.assertNotIn("pgrep", guard_script, "the guard check is not a process scan")

    def test_a_dryrun_line_first_does_not_fool_the_earlyoom_read(self) -> None:
        # pgrep prints PID order, so a surviving `--dryrun` can precede the daemon.
        lines = "\n".join(reversed(self.EARLYOOM.splitlines()))
        proof = self.prove(self.runner([], earlyoom=lines, guard=(0, self.GUARD_OK)))
        self.assertIn("earlyoom argv: 453964", proof[0])
        self.assertNotIn("dryrun", proof[0])

    def test_no_running_earlyoom_quotes_both_thresholds(self) -> None:
        with self.assertRaises(plan.PlanError) as ctx:
            self.prove(self.runner([], earlyoom="1 earlyoom --dryrun",
                                    guard=(0, self.GUARD_OK)))
        self.assertIn("no running earlyoom quotes both thresholds", str(ctx.exception))

    def test_a_non_negative_oom_score_refuses_naming_the_unit(self) -> None:
        run = self.runner([], earlyoom=self.EARLYOOM, guard=(0, self.GUARD_OK),
                          units={"NetworkManager.service": "0"})
        with self.assertRaises(plan.PlanError) as ctx:
            self.prove(run)
        self.assertIn("host-a", str(ctx.exception))
        self.assertIn("NetworkManager.service", str(ctx.exception))
        self.assertIn("0, not negative", str(ctx.exception))

    def test_a_missing_earlyoom_refuses_rather_than_defaulting_clean(self) -> None:
        with self.assertRaises(plan.PlanError) as ctx:
            self.prove(self.runner([], guard=(0, self.GUARD_OK)))
        self.assertIn("earlyoom is not running", str(ctx.exception))

    def test_a_disabled_threshold_is_not_a_guard(self) -> None:
        with self.assertRaises(plan.PlanError) as ctx:
            self.prove(self.runner([], earlyoom="1 earlyoom -m 0 -s 100,95",
                                    guard=(0, self.GUARD_OK)))
        self.assertIn("disables the kill", str(ctx.exception))

    def test_a_missing_or_non_executable_guard_script_refuses(self) -> None:
        with self.assertRaises(plan.PlanError) as ctx:
            self.prove(self.runner([], earlyoom=self.EARLYOOM, guard=(1, self.GUARD_MISSING)))
        message = str(ctx.exception)
        self.assertIn("host-a", message)
        self.assertIn(f"{self.WINDOW!r}", message)
        self.assertIn(f"~/benchmarks/{self.WINDOW}/mem-guard.sh", message)
        self.assertIn(self.GUARD_MISSING, message)

    def test_a_stale_or_foreign_guard_no_longer_satisfies_anything(self) -> None:
        # The control: the probe carries no process scan, so the eleven dead-window guards on
        # `.30` cannot pass it. The same host passes only when the script is executable.
        calls: list[tuple[str, str]] = []
        with self.assertRaises(plan.PlanError) as ctx:
            self.prove(self.runner(calls, earlyoom=self.EARLYOOM, guard=(1, self.GUARD_MISSING)))
        self.assertIn("has no executable guard script", str(ctx.exception))
        guard_script = next(script for _, script in calls if "mem-guard.sh" in script)
        self.assertNotIn("pgrep", guard_script)
        self.assertNotIn("ps ", guard_script)
        proof = self.prove(self.runner([], earlyoom=self.EARLYOOM, guard=(0, self.GUARD_OK)))
        self.assertIn(f"guard script: {self.GUARD_OK}", proof)

    def test_the_window_name_selects_the_script_path(self) -> None:
        for window in ("window-one", "window-two"):
            calls: list[tuple[str, str]] = []
            _ = self.prove(self.runner(calls, earlyoom=self.EARLYOOM,
                                       guard=(0, f"/home/red/benchmarks/{window}/mem-guard.sh")),
                           window=window)
            guard_script = next(script for _, script in calls if "mem-guard.sh" in script)
            self.assertIn(window, guard_script)

    def test_no_window_name_cannot_resolve_a_guard_script(self) -> None:
        with self.assertRaises(plan.PlanError) as ctx:
            self.prove(self.runner([], earlyoom=self.EARLYOOM), window="")
        self.assertIn("no declared window name", str(ctx.exception))

    def test_a_path_like_window_is_not_a_directory_name(self) -> None:
        with self.assertRaises(plan.PlanError) as ctx:
            self.prove(self.runner([], earlyoom=self.EARLYOOM), window="../escape")
        self.assertIn("is not a directory name", str(ctx.exception))


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
              head_proof=None, record_hosts: tuple[str, ...] = (), record_risk: str = ""):
        path = write(self.tmp / "manifest.json", json.dumps(entries))
        campaign = state.Campaign.open(self.root / "state.json", campaign="test",
                                       hosts=hosts, max_parallel=2)
        self.addCleanup(campaign.close)
        proof = head_proof or (lambda host: self.fail(f"head_proof called unexpectedly for {host}"))
        leader = director_module.Director(
            campaign, plan.load_manifest(path),
            root=self.root, receipts_root=self.receipts, repo_root=self.repo,
            run_arm_sh=self.run_arm, clock=self.clock, spawn=False, out=self.out,
            fleet_reap=self.fleet.reap, ledger=self.ledger, head_proof=proof,
            record_hosts=record_hosts, record_risk=record_risk)
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

    def test_a_declared_window_travels_to_the_executor_as_the_arming_opt_in(self) -> None:
        campaign = state.Campaign.open(self.root / "state2.json", campaign="test",
                                       hosts=("node-a", "node-b"), max_parallel=1)
        self.addCleanup(campaign.close)
        campaign.add("pair", "recipes/lane/pair.yaml", tp=2, window="kimi-six-20261112")
        lease = campaign.assign("pair", "w1", ["node-a", "node-b"], self.clock.now)
        self.assertEqual(lease["env"]["ARM_WINDOW"], "kimi-six-20261112",
                         "the executor would never arm a guard for the declared window")
        campaign.add("solo", "recipes/lane/solo.yaml", tp=1)
        plain = campaign.assign("solo", "w1", ["node-a"], self.clock.now)
        self.assertNotIn("ARM_WINDOW", plain["env"], "an undeclared window must stay no-op")

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
        def proof(host: str, window: str = "") -> list[str]:
            raise plan.PlanError(f"{host}: OOMScoreAdjust on ssh.service is 0, not negative")

        leader, campaign = self.build([self.waived()], hosts=self.HOSTS, head_proof=proof)
        self.assertEqual(leader.handle(protocol.poll("w1"))["op"], "idle")
        self.assertNotIn("assign:", self.out.getvalue(), "a refused waiver must never boot")
        self.assertEqual(campaign.arm("pair")["status"], "blocked")
        reason = campaign.arm("pair")["last"]["reason"]
        self.assertIn("node.30", reason)
        self.assertIn("ssh.service", reason)

    def test_a_proven_waiver_places_the_head_last_and_records_the_quote(self) -> None:
        seen: list[tuple[str, str]] = []

        def proof(host: str, window: str = "") -> list[str]:
            seen.append((host, window))
            return ["earlyoom argv: 4242 earlyoom -m 4,1 -s 100,95",
                    "OOMScoreAdjust ssh.service = -900",
                    "memory sampler: 777 mem-guard.sh 6.0"]

        leader, _ = self.build([self.waived()], hosts=self.HOSTS, head_proof=proof)
        lease = leader.handle(protocol.poll("w1"))["lease"]
        self.assertEqual(seen, [("node.30", "kimi-six-node-20261112")],
                         "the proof is taken for the declared window, before the lease")
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
        self.assertEqual(len(self.ledger.leases()), 1, "six ranks are one claim, not six")
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


class RecordRoot(DirectorCase):
    """R4: the rank that holds the campaign record root is refused unless its risk is declared.

    `--root` carries state.json, its lock, the socket and the receipts, so a shape taking that host
    loses its own instrument with the node. The record host is detected from the running host, but
    the rule is about the record: it fires for a declared record host whatever host this process
    runs on.
    """

    HOSTS = HEAD

    def six(self, **fields) -> dict:
        return self.arm("six", tp=2, pp=3, **fields)

    def test_a_six_rank_shape_that_must_take_the_record_host_refuses_naming_it(self) -> None:
        with self.assertRaises(plan.PlanError) as ctx:
            self.build([self.six()], hosts=self.HOSTS, record_hosts=("node.30",))
        message = str(ctx.exception)
        self.assertIn("node.30", message)
        self.assertIn("cannot avoid", message)
        self.assertIn("--accept-record-risk", message)
        self.assertIn("not a rank", message)
        self.assertIn("WOPR.yaml", message)
        self.assertFalse(self.ledger.leases(), "a refused plan writes no claim")

    def test_the_refusal_needs_neither_the_director_nor_a_hardcoded_name(self) -> None:
        # The record root on `.33` refuses even though this process runs elsewhere: the rank set
        # is what puts the record on a node, not where the director happens to sit.
        with self.assertRaises(plan.PlanError) as ctx:
            self.build([self.six()], hosts=self.HOSTS, record_hosts=("node.33",))
        self.assertIn("node.33", str(ctx.exception))

    def test_the_running_host_is_matched_by_its_own_name_or_address(self) -> None:
        self.assertEqual(
            plan.record_hosts(["node.30", "node.31"], {"node.30", "192.0.2.30"}),
            ("node.30",))
        self.assertEqual(plan.record_hosts(["192.0.2.30", "node.31"], {"192.0.2.30"}),
                         ("192.0.2.30",), "an address-form host set is detected too")
        self.assertEqual(plan.record_hosts(["node.30"], {"elsewhere"}), ())

    def test_the_declared_risk_lets_the_shape_run_and_is_recorded(self) -> None:
        reason = "owner accepted a sixth rank on the record host"
        leader, _ = self.build([self.six()], hosts=self.HOSTS,
                               record_hosts=("node.30",), record_risk=reason)
        self.assertIn(f"record-risk-accepted: node.30 ({reason})", self.out.getvalue())
        lease = leader.handle(protocol.poll("w1"))["lease"]
        self.assertEqual(sorted(lease["hosts"]), sorted(self.HOSTS))
        written = json.loads((self.root / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(written["record_risk"]["hosts"], ["node.30"])
        self.assertEqual(written["record_risk"]["reason"], reason)

    def test_a_quartet_that_fits_outside_the_record_host_is_unaffected(self) -> None:
        leader, _ = self.build([self.arm("six", tp=2, pp=2, memory_risky=True)],
                               hosts=self.HOSTS, record_hosts=("node.30",))
        self.assertNotIn("record-risk-accepted", self.out.getvalue())
        self.assertIn("record-held: node.30", self.out.getvalue())
        self.assertEqual(leader.handle(protocol.poll("w1"))["lease"]["hosts"],
                         ["node.31", "node.32", "node.33", "node.34"])

    def test_a_quartet_that_would_only_fit_by_taking_the_record_host_waits(self) -> None:
        self.ledger.acquire("another-session", ["node.31", "node.32"], ttl=600)
        leader, _ = self.build([self.arm("six", tp=2, pp=2)], hosts=self.HOSTS,
                               record_hosts=("node.30",))
        self.assertEqual(leader.handle(protocol.poll("w1"))["op"], "idle")
        self.assertNotIn("assign:", self.out.getvalue())
        leader.record_hosts = ()  # control: without the gate this tick leases the record host
        self.assertIn("node.30", leader.handle(protocol.poll("w1"))["lease"]["hosts"])


class PlanOnly(unittest.TestCase):
    """`director plan`: the placement and head proof without a state file, lease or ledger."""

    HOSTS = ("node.30", "node.31", "node.32", "node.33", "node.34", "node.35")

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "repo"
        for arm in ("six", "quartet"):
            recipe(self.repo, "lane", arm)

    def run_plan(self, entries: list[dict], prove) -> tuple[int, str]:
        path = write(self.tmp / "manifest.json", json.dumps(entries))
        out = io.StringIO()
        with mock.patch.object(director_module.guardrails, "prove", prove), \
                contextlib.redirect_stdout(out):
            code = director_module.main([
                "plan", "--manifest", str(path), "--hosts", ",".join(self.HOSTS),
                "--exclude-host", ".30", "--repo-root", str(self.repo),
                "--receipts-root", str(self.tmp / "receipts"),
            ])
        return code, out.getvalue()

    def test_a_six_rank_waiver_prints_six_hosts_with_the_head_last_and_its_proof(self) -> None:
        entries = [{"arm": "six", "path": "recipes/lane/six.yaml", "tp": 2, "pp": 3,
                    "memory_risky": True, "allow_hosts": ["node.30"],
                    "window": "fresh-window"}]
        code, text = self.run_plan(
            entries, lambda host, window="": [f"sampler: 1 bash /w/{window}/mem-guard.sh tid"])
        self.assertEqual(code, 0)
        self.assertIn("plan: six -> node.31,node.32,node.33,node.34,node.35,node.30 "
                      "(tp=2 pp=3 ranks=6 window=fresh-window)", text)
        self.assertIn("lease-proof: node.30 sampler: 1 bash /w/fresh-window/mem-guard.sh tid", text)
        self.assertIn("plan: excluded host(s) used: node.30", text)
        self.assertFalse((self.tmp / "state.json").exists())
        self.assertFalse((self.repo / ".local").exists())

    def test_a_missing_sampler_refuses_naming_the_host_and_window(self) -> None:
        entries = [{"arm": "six", "path": "recipes/lane/six.yaml", "tp": 2, "pp": 3,
                    "memory_risky": True, "allow_hosts": ["node.30"],
                    "window": "fresh-window"}]

        def refuse(host: str, window: str = "") -> list[str]:
            raise plan.PlanError(f"{host}: host memory sampler for window {window!r} is not armed")

        code, text = self.run_plan(entries, refuse)
        self.assertEqual(code, 3)
        self.assertIn("lease-refused: node.30 (node.30: host memory sampler for window "
                      "'fresh-window' is not armed", text)
        self.assertIn("plan: no state, lease or ledger written", text)

    def test_a_quartet_without_the_waiver_never_touches_the_head(self) -> None:
        entries = [{"arm": "quartet", "path": "recipes/lane/quartet.yaml", "tp": 2, "pp": 2,
                    "memory_risky": True}]
        calls: list[str] = []

        def proof(host: str, window: str = "") -> list[str]:
            calls.append(host)
            return []

        code, text = self.run_plan(entries, proof)
        self.assertEqual(code, 0)
        self.assertIn("plan: quartet -> node.31,node.32,node.33,node.34 "
                      "(tp=2 pp=2 ranks=4 window=-)", text)
        self.assertIn("plan: excluded host(s) used: none", text)
        self.assertEqual(calls, [], "a safe placement proves nothing: it touches no head")
        self.assertFalse((self.tmp / "state.json").exists())


    def test_a_six_rank_plan_refuses_the_host_holding_the_record_root(self) -> None:
        entries = [{"arm": "six", "path": "recipes/lane/six.yaml", "tp": 2, "pp": 3}]
        code, _, err = self.run_plan_risk(entries, identities={"node.30"})
        self.assertEqual(code, 2)
        self.assertIn("node.30", err)
        self.assertIn("--accept-record-risk", err)
        self.assertIn("not a rank", err)
        self.assertFalse((self.tmp / "state.json").exists(), "a refusal writes no state")
        self.assertFalse((self.repo / ".local").exists())

    def test_the_declared_risk_plans_six_hosts_and_prints_the_acceptance(self) -> None:
        entries = [{"arm": "six", "path": "recipes/lane/six.yaml", "tp": 2, "pp": 3}]
        code, text, err = self.run_plan_risk(
            entries, extra=("--accept-record-risk", "owner accepted the record host"),
            identities={"node.30"})
        self.assertEqual(code, 0, err)
        self.assertIn("record-risk-accepted: node.30 (owner accepted the record host)", text)
        self.assertIn("plan: six -> node.31,node.32,node.33,node.34,node.35,node.30", text)
        self.assertFalse((self.tmp / "state.json").exists(), "plan writes no state")

    def test_a_quartet_that_fits_outside_the_record_host_plans_normally(self) -> None:
        entries = [{"arm": "quartet", "path": "recipes/lane/quartet.yaml", "tp": 2, "pp": 2}]
        code, text, err = self.run_plan_risk(entries, identities={"node.30"})
        self.assertEqual(code, 0, err)
        self.assertIn("record-held: node.30", text)
        self.assertIn("plan: quartet -> node.31,node.32,node.33,node.34", text)

    def run_plan_risk(self, entries: list[dict], *, extra: tuple[str, ...] = (),
                      identities: set[str]) -> tuple[int, str, str]:
        """`director plan` with the running host declared, capturing the refusal on stderr."""
        path = write(self.tmp / "manifest.json", json.dumps(entries))
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(plan, "local_identities", return_value=identities), \
                mock.patch.object(director_module.guardrails, "prove",
                                  lambda host, window="": []), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = director_module.main([
                "plan", "--manifest", str(path), "--hosts", ",".join(self.HOSTS),
                "--exclude-host", ".30", "--repo-root", str(self.repo),
                "--receipts-root", str(self.tmp / "receipts"), *extra,
            ])
        return code, out.getvalue(), err.getvalue()


if __name__ == "__main__":
    unittest.main()
