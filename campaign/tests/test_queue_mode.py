"""The director's queue mode: the register is the plan source, and the claim is the lock.

A manifest campaign is a hand-written list; a queue campaign reads `mad-science/queue.json`, so the
question "what should run next" is answered by the register's own weighted order rather than by
whoever wrote the file. These tests pin the four things that make that safe without a fleet:

* only a `queued` row naming a `recipe` and `tp` is work — `blocked`, another session's `running`
  claim, an authoring row and a quartet on two hosts are excluded, each by name and reason;
* the claim is written to the register **before** the lease exists, because the lease is what a
  worker launches from (a recording shell-out stands in for the tool);
* a measured arm closes its row with the receipt, a failed one goes back to `queued` and says why,
  and a recorded negative closes the row with its citation instead of being booted again;
* a drained queue keeps serving at a bounded interval (a row can appear later) while `--once`
  drains and exits 0, and neither spins on rows that are blocked or not bootable.

Ordering itself is not re-derived here: `tools/task-queue.py queue --json` is the one implementation
of the weight arithmetic, and `tests/test_task_queue_tool.py` pins the machine read to the human
ordering. `RealRegister` runs that tool for real against a throwaway checkout, so the argv this
package builds is the argv the tool's parser accepts.
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from sparkrun_campaign import director as director_module
from sparkrun_campaign import fleet, plan, protocol, state

from .support import lane_doc, manifest, receipt, recipe

SESSION = "sparkrun-campaign:test"


def flag(argv: list[str], name: str) -> str:
    """The value after `name` in a recorded tool call, or "" when the flag was not passed."""
    return argv[argv.index(name) + 1] if name in argv else ""


def row(task_id: str, recipe_path: str = "", tp: int = 0, *, state_: str = "queued",
        node_cost: str = "", claimed_by: str = "", env: dict | None = None,
        blocked_by: list | None = None) -> dict:
    """A register row as `queue --json` prints it: every schema field, plus the optional two."""
    entry = {
        "id": task_id, "title": task_id, "estimate_h": 1.0, "blocks": [], "blocked_by": [],
        "state": state_, "model": "", "node_cost": node_cost, "notes": f"why {task_id} exists",
        "provenance": "test", "evidence": "", "claimed_by": claimed_by, "claimed_at": "",
    }
    if recipe_path:
        entry["recipe"] = recipe_path
    if tp:
        entry["tp"] = tp
    if env:
        entry["env"] = env
    if blocked_by is not None:
        entry["blocked_by"] = list(blocked_by)
    return entry


class Shell:
    """Stands in for `tools/task-queue.py`: serves rows, records every write argv."""

    def __init__(self, rows: list[dict], refuse_writes: bool = False):
        self.rows = rows
        self.refuse_writes = refuse_writes
        self.calls: list[list[str]] = []

    def __call__(self, command, **kwargs):
        self.calls.append(list(command))
        if "queue" in command:
            return subprocess.CompletedProcess(command, 0, json.dumps(self.rows), "")
        if self.refuse_writes:
            return subprocess.CompletedProcess(command, 1, "",
                                               f"{flag(command, '--id')}: no such task")
        return subprocess.CompletedProcess(command, 0, "", "")

    def updates(self) -> list[list[str]]:
        return [call for call in self.calls if "update" in call]

    def states(self, task_id: str) -> list[str]:
        return [flag(call, "--state") for call in self.updates() if flag(call, "--id") == task_id]

    def last_update(self, task_id: str) -> list[str]:
        found = [call for call in self.updates() if flag(call, "--id") == task_id]
        return found[-1] if found else []


class FakeClock:
    def __init__(self, now: float = 1000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


class FakeFleet:
    def __init__(self):
        self.containers: dict[str, list[str]] = {}

    def reap(self, hosts: list[str], recipe_path: str) -> dict:
        found = [(host, name) for host in hosts for name in self.containers.pop(host, [])]
        return {"found": found, "removed": found, "after": []}


class QueueCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        recipe(self.repo, "lane", "one")
        recipe(self.repo, "lane", "two")
        recipe(self.repo, "lane", "good")
        recipe(self.repo, "lane", "negative",
               marker="2026-11-01 \u2014 died at engine load (docs/lane.md:2)")
        lane_doc(self.repo)
        tool = self.repo / "tools" / "task-queue.py"
        tool.parent.mkdir(parents=True)
        tool.write_text("# fixture: the shell is faked\n", encoding="utf-8")
        run_arm = self.repo / "tools" / "run-arm.sh"
        run_arm.write_text("#!/bin/sh\n", encoding="utf-8")
        run_arm.chmod(0o755)
        self.queue = self.repo / "mad-science" / "queue.json"
        self.queue.parent.mkdir()
        self.shell = Shell([])
        self.receipts = self.tmp / "benchmarks"
        self.root = self.tmp / "campaign"
        self.clock = FakeClock()
        self.fleet = FakeFleet()
        self.out = io.StringIO()

    def build(self, hosts=("node-a", "node-b"), once: bool = False,
              retries: int | None = None,
              exclude_hosts: tuple[str, ...] | None = None):
        campaign = state.Campaign.open(self.root / "state.json", campaign="test",
                                        hosts=hosts, max_parallel=2, retries=retries)
        self.addCleanup(campaign.close)
        leader = director_module.Director(
            campaign,
            [],
            root=self.root,
            receipts_root=self.receipts,
            repo_root=self.repo,
            run_arm_sh=self.repo / "tools" / "run-arm.sh",
            clock=self.clock,
            spawn=False,
            out=self.out,
            fleet_reap=self.fleet.reap,
            register=plan.Register(self.repo / "tools" / "task-queue.py", self.queue, SESSION,
                                   run=self.shell),
            once=once,
            exclude_hosts=(plan.MEMORY_RISKY_EXCLUDED_HOSTS if exclude_hosts is None
                           else exclude_hosts),
        )
        return leader, campaign


class PlanFromTheRegister(QueueCase):
    def test_the_plan_follows_the_registers_order(self) -> None:
        # `queue --json` is already weighted; the campaign preserves that order and adds nothing.
        self.shell.rows = [row("light-task", "recipes/lane/two.yaml", 1, node_cost="single"),
                           row("heavy-task", "recipes/lane/one.yaml", 1, node_cost="single")]
        leader, campaign = self.build()
        leader.prepare()
        self.assertEqual(campaign.order, ["two", "one"])
        self.assertEqual(leader.handle(protocol.poll("w1"))["lease"]["arm"], "two")

    def test_blocked_running_authoring_and_oversized_rows_are_excluded_with_reasons(self) -> None:
        self.shell.rows = [
            row("blocked-task", "recipes/lane/one.yaml", 1, state_="blocked", node_cost="single"),
            row("claimed-task", "recipes/lane/two.yaml", 1, state_="running", node_cost="single",
                claimed_by="another-session"),
            row("authoring-task"),
            row("quartet-task", "recipes/lane/negative.yaml", 4, node_cost="quartet"),
            row("good-task", "recipes/lane/good.yaml", 1, node_cost="single"),
        ]
        leader, campaign = self.build()
        leader.prepare()
        text = self.out.getvalue()
        self.assertEqual(campaign.order, ["good"])
        self.assertIn("queue-skip: blocked-task (register state blocked)", text)
        self.assertIn("queue-skip: claimed-task (claimed running by another-session)", text)
        self.assertIn("queue: 1 row(s) queued without a recipe (authoring, not bootable)", text)
        self.assertIn("queue-skip: quartet-task (tp=4 needs 4 hosts, 2 declared)", text)
        self.assertNotIn("queue-skip: good-task", text)

    def test_a_queued_row_with_a_live_blocking_edge_is_excluded(self) -> None:
        self.shell.rows = [row("held-task", "recipes/lane/one.yaml", 1, node_cost="single",
                               blocked_by=["a-dependency"])]
        leader, campaign = self.build()
        leader.prepare()
        self.assertEqual(campaign.order, [])
        self.assertIn("queue-skip: held-task (blocked by a-dependency)", self.out.getvalue())

    def test_two_runnable_rows_naming_one_recipe_skip_only_that_recipe(self) -> None:
        self.shell.rows = [row("a", "recipes/lane/one.yaml", 1, node_cost="single"),
                           row("b", "recipes/lane/one.yaml", 1, node_cost="single"),
                           row("good", "recipes/lane/good.yaml", 1, node_cost="single")]
        leader, campaign = self.build()
        leader.prepare()
        self.assertEqual(campaign.order, ["good"])
        self.assertIn("queue-skip: one (a and b both name recipe recipes/lane/one.yaml)",
                      self.out.getvalue())
        self.assertEqual(leader.handle(protocol.poll("w1"))["lease"]["arm"], "good")

    def test_a_duplicate_pair_does_not_abort_a_drained_tick(self) -> None:
        self.shell.rows = [row("good", "recipes/lane/good.yaml", 1, node_cost="single")]
        leader, campaign = self.build()
        leader.prepare()
        self.assertEqual(campaign.order, ["good"])

        self.shell.rows = [row("a", "recipes/lane/one.yaml", 1, node_cost="single"),
                           row("b", "recipes/lane/one.yaml", 1, node_cost="single"),
                           row("new", "recipes/lane/two.yaml", 1, node_cost="single")]
        leader._last_poll = 0.0
        leader._wait_for_rows()
        self.assertEqual(campaign.order, ["good", "two"],
                         "the ambiguous recipe is skipped; the new row is adopted")
        self.assertIn("a and b both name recipe", self.out.getvalue())
        self.assertIn("1 new runnable row(s): two", self.out.getvalue())

    def test_a_row_naming_a_deleted_recipe_skips_only_that_arm(self) -> None:
        self.shell.rows = [row("gone-task", "recipes/lane/gone.yaml", 1, node_cost="single"),
                           row("good", "recipes/lane/good.yaml", 1, node_cost="single")]
        leader, campaign = self.build()
        leader.prepare()
        self.assertEqual(campaign.order, ["good"])
        self.assertIn("queue-skip: gone (recipes/lane/gone.yaml does not exist",
                      self.out.getvalue())
        self.assertEqual(leader.handle(protocol.poll("w1"))["lease"]["arm"], "good")

    def test_a_plan_defect_is_not_reported_as_an_unreadable_register(self) -> None:
        self.shell.rows = [row("authoring-task")]
        leader, _ = self.build()
        leader.prepare()

        def broken_plan():
            raise plan.PlanError("a and b both name recipe x")

        leader._plan = broken_plan
        leader._last_poll = 0.0
        leader._wait_for_rows()
        self.assertIn("queue: plan defect this tick (a and b both name recipe x)",
                      self.out.getvalue())
        self.assertNotIn("cannot read the register", self.out.getvalue())

    def test_the_control_combined_handler_mislabels_a_plan_defect(self) -> None:
        def old_tick(exc) -> str:
            """Tonight's tick: one handler for both failures, and nothing is adopted."""
            if isinstance(exc, (plan.RegisterError, plan.PlanError)):
                return f"cannot read the register ({exc}); retrying in 30s"
            return ""

        self.assertIn("cannot read the register",
                      old_tick(plan.PlanError("a and b both name recipe x")))

    def test_a_quartet_row_runs_when_four_hosts_are_declared(self) -> None:
        self.shell.rows = [row("quartet-task", "recipes/lane/one.yaml", 4, node_cost="quartet")]
        # The placement guard is disabled here on purpose: this test is quartet admission, and a
        # four-node set that names none of its exclusions is refused (see MemoryRiskyRows).
        leader, campaign = self.build(hosts=("n1", "n2", "n3", "n4"), exclude_hosts=())
        leader.prepare()
        self.assertEqual(campaign.order, ["one"])
        self.assertEqual(leader.handle(protocol.poll("w1"))["lease"]["hosts"],
                         ["n1", "n2", "n3", "n4"])

    def test_manifest_mode_never_writes_to_the_register(self) -> None:
        self.shell.rows = [row("unused", "recipes/lane/one.yaml", 1, node_cost="single")]
        campaign = state.Campaign.open(self.root / "state.json", campaign="test",
                                        hosts=("node-a", "node-b"), max_parallel=2)
        self.addCleanup(campaign.close)
        leader = director_module.Director(
            campaign, plan.load_manifest(manifest(self.tmp / "m.json", [
                ("one", "recipes/lane/one.yaml", 1)])),
            root=self.root, receipts_root=self.receipts, repo_root=self.repo,
            run_arm_sh=self.repo / "tools" / "run-arm.sh", clock=self.clock, spawn=False,
            out=self.out, fleet_reap=self.fleet.reap)
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        self.assertEqual(lease["arm"], "one")
        self.assertEqual(self.shell.calls, [], "a manifest campaign has no register to write")


class MemoryRiskyRows(QueueCase):
    """A row that needs the excluded host is refused by name; one that fits is placed off it."""

    HOSTS = ("node.30", "node.31", "node.32", "node.33", "node.34", "node.35")

    def test_a_shape_that_needs_the_excluded_host_is_refused_by_name(self) -> None:
        # E3's shape: TP=2 x PP=3 is six ranks, and the row declares the risk, so a `tp >= 4`
        # predicate would pass it and place it on the head. It stays queued and the next row runs.
        six = row("six-task", "recipes/lane/six.yaml", 6)
        six["memory_risky"] = True
        self.shell.rows = [six, row("good-task", "recipes/lane/good.yaml", 1, node_cost="single")]
        leader, campaign = self.build(hosts=self.HOSTS)
        leader.prepare()

        self.assertEqual(campaign.order, ["good"])
        self.assertNotIn("six", campaign.arms())
        self.assertIn("queue-skip: six-task (memory-risky shape needs 6 ranks, 5 declared outside "
                      "node.30)", self.out.getvalue())
        lease = leader.handle(protocol.poll("w1"))["lease"]
        self.assertEqual((lease["arm"], lease["hosts"]), ("good", ["node.31"]))
        self.assertEqual([flag(call, "--id") for call in self.shell.updates()], ["good-task"],
                         "a refused row is left queued and never claimed")

    def test_a_tp4_row_on_six_hosts_is_placed_off_the_excluded_host(self) -> None:
        self.shell.rows = [row("quartet-task", "recipes/lane/one.yaml", 4, node_cost="quartet")]
        leader, campaign = self.build(hosts=self.HOSTS)
        leader.prepare()

        self.assertEqual(campaign.order, ["one"])
        self.assertEqual(leader.handle(protocol.poll("w1"))["lease"]["hosts"],
                         ["node.31", "node.32", "node.33", "node.34"])

    def test_a_hostname_declared_set_matches_the_head_when_it_is_named(self) -> None:
        # A tracked default cannot carry the head's hostname, so a hostname-declared set names it
        # in --exclude-host / $CAMPAIGN_EXCLUDE_HOSTS; the guard then keeps the head last.
        risky = row("probe-task", "recipes/lane/one.yaml", 1)
        risky["memory_risky"] = True
        self.shell.rows = [risky]
        leader, _ = self.build(hosts=("head-node", "rank-1"), exclude_hosts=("head-node",))
        leader.prepare()

        self.assertEqual(leader.handle(protocol.poll("w1"))["lease"]["hosts"], ["rank-1"])

    def test_an_exclusion_that_matches_no_declared_host_refuses_the_plan(self) -> None:
        # Without the configured name `.30` matches nothing on a hostname-declared set; ordering
        # would put the head first while the guard looked installed, so the plan fails closed.
        risky = row("probe-task", "recipes/lane/one.yaml", 1)
        risky["memory_risky"] = True
        self.shell.rows = [risky]
        leader, _ = self.build(hosts=("head-node", "rank-1"))

        with self.assertRaises(plan.PlanError) as ctx:
            leader.prepare()
        self.assertIn("matched no declared host", str(ctx.exception))
        self.assertIn("exclude-host", str(ctx.exception))


class Claims(QueueCase):
    def setUp(self) -> None:
        super().setUp()
        self.shell.rows = [row("task-one", "recipes/lane/one.yaml", 1, node_cost="single")]

    def test_the_claim_is_recorded_before_the_lease_exists(self) -> None:
        leader, campaign = self.build()
        leader.prepare()
        self.assertEqual(self.shell.updates(), [], "prepare must not claim anything")

        seen: list[list[str]] = []
        original = campaign.assign

        def assign(*args, **kwargs):
            # A worker can only launch from a lease, so this is the moment that must not precede
            # the claim.
            seen.extend(self.shell.updates())
            return original(*args, **kwargs)

        campaign.assign = assign
        lease = leader.handle(protocol.poll("w1"))["lease"]
        self.assertEqual(lease["arm"], "one")
        self.assertTrue(seen, "the register claim must precede the lease a worker launches from")
        self.assertEqual(flag(seen[-1], "--id"), "task-one")
        self.assertEqual(flag(seen[-1], "--state"), "running")
        self.assertEqual(flag(seen[-1], "--claimed-by"), SESSION)

    def test_a_measured_arm_closes_its_row_with_the_receipt(self) -> None:
        leader, _ = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        arm_dir = receipt(self.receipts, lease["arm"], cells=2)
        self.assertEqual(leader.handle(protocol.report(lease["id"], 0, "log run.log"))["status"],
                         "measured")
        done = self.shell.last_update("task-one")
        self.assertEqual(flag(done, "--state"), "done")
        self.assertEqual(flag(done, "--evidence"), str(arm_dir))

    def test_a_failed_arm_returns_its_row_to_the_queue_and_says_why(self) -> None:
        leader, _ = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        receipt(self.receipts, lease["arm"], cells=0)
        self.assertEqual(leader.handle(protocol.report(lease["id"], 0, "log run.log"))["status"],
                         "failed")
        self.assertEqual(self.shell.states("task-one"), ["running", "queued"],
                         "a dead arm must not be left claimed running")
        failed = self.shell.last_update("task-one")
        self.assertEqual(flag(failed, "--state"), "queued")
        # The claim is released by the tool itself on every exit from `running` (QUEUE.md); this
        # asserts the director does not re-send it, and the round-trip test below asserts the file.
        self.assertNotIn("--claimed-by", failed)
        self.assertIn("campaign:", flag(failed, "--notes"))
        self.assertIn("why task-one exists", flag(failed, "--notes"),
                      "the row keeps its own justification text")

    def test_a_blocked_arm_returns_its_row_to_the_external_gate(self) -> None:
        self.fleet.reap = lambda hosts, recipe_path: {
            "found": [("node-b", "sparkrun_t1_node_1")], "removed": [],
            "after": [("node-b", "sparkrun_t1_node_1")]}
        leader, _ = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        receipt(self.receipts, lease["arm"], cells=2)
        self.assertEqual(leader.handle(protocol.report(lease["id"], 0, "log run.log"))["status"],
                         "blocked")
        self.assertEqual(flag(self.shell.last_update("task-one"), "--state"), "blocked")

    def test_a_refused_claim_blocks_the_arm_instead_of_booting_it(self) -> None:
        self.shell.refuse_writes = True
        leader, campaign = self.build()
        leader.prepare()
        self.assertIsNone(leader.handle(protocol.poll("w1")).get("lease"))
        self.assertEqual(campaign.arm("one")["status"], "blocked")
        self.assertIn("register claim refused", campaign.arm("one")["last"]["reason"])
        self.assertEqual(self.out.getvalue().count("assign:"), 0)

    def test_a_negative_in_the_register_is_closed_with_its_citation_not_booted(self) -> None:
        self.shell.rows = [row("negative-task", "recipes/lane/negative.yaml", 1,
                               node_cost="single"),
                           row("task-one", "recipes/lane/one.yaml", 1, node_cost="single")]
        leader, campaign = self.build()
        leader.prepare()
        text = self.out.getvalue()
        self.assertIn("skip: negative (measured-rejected, docs/lane.md:2)", text)
        self.assertEqual(campaign.arm("negative")["status"], "skipped")
        closed = self.shell.last_update("negative-task")
        self.assertEqual(flag(closed, "--state"), "done")
        self.assertEqual(flag(closed, "--evidence"), "docs/lane.md:2 (measured-rejected)")
        lease = leader.handle(protocol.poll("w1"))["lease"]
        self.assertEqual(lease["arm"], "one")

    def test_a_restart_resumes_its_own_running_row(self) -> None:
        leader, campaign = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        self.assertEqual(flag(self.shell.last_update("task-one"), "--state"), "running")
        campaign.close()                                  # the process died mid-arm: no report
        self.clock.now += state.LEASE_TTL + 1

        # The register still says this arm is ours; the campaign's lease record says it needs a
        # reap. The row must stay in the plan, not be blocked as "no longer runnable".
        self.shell.rows = [row("task-one", "recipes/lane/one.yaml", 1, state_="running",
                               node_cost="single", claimed_by=SESSION)]
        leader, campaign = self.build()
        leader.prepare()

        self.assertEqual(campaign.arm("one")["status"], "pending")
        self.assertNotIn("queue-blocked: one", self.out.getvalue())
        self.assertEqual(campaign.arm("one")["needs_reap"], [])
        resumed = leader.handle(protocol.poll("w1"))["lease"]
        self.assertEqual(resumed["arm"], "one")
        self.assertEqual(flag(self.shell.last_update("task-one"), "--state"), "running")

    def test_a_claim_with_no_campaign_state_is_refused_not_adopted(self) -> None:
        # A fresh root with the same name finds a row claimed under its session id and no lease
        # record: booting it would double-boot an arm nobody has verified stopped.
        self.shell.rows = [row("task-one", "recipes/lane/one.yaml", 1, state_="running",
                               node_cost="single", claimed_by=SESSION)]
        leader, campaign = self.build()
        leader.prepare()
        self.assertEqual(campaign.order, [])
        self.assertIn(f"queue-skip: task-one (claimed running by {SESSION} with no campaign "
                      "state (stale claim))", self.out.getvalue())
        self.assertIsNone(leader.handle(protocol.poll("w1")).get("lease"))

    def test_another_sessions_claim_blocks_an_arm_this_campaign_holds(self) -> None:
        leader, campaign = self.build()
        leader.prepare()
        campaign.close()

        self.shell.rows = [row("task-one", "recipes/lane/one.yaml", 1, state_="running",
                               node_cost="single", claimed_by="another-session")]
        leader, campaign = self.build()
        leader.prepare()

        self.assertEqual(campaign.arm("one")["status"], "blocked")
        self.assertIn("claimed running by another-session", campaign.arm("one")["last"]["reason"])
        self.assertIn("queue-blocked: one", self.out.getvalue())
        self.assertIsNone(leader.handle(protocol.poll("w1")).get("lease"))


class Draining(QueueCase):
    def test_no_runnable_rows_prints_and_once_exits_zero(self) -> None:
        self.shell.rows = [row("authoring-task")]
        leader, _ = self.build(once=True)
        self.assertEqual(leader.serve(), 0)
        text = self.out.getvalue()
        self.assertIn("queue: no runnable rows", text)
        self.assertIn("plan drained", text)

    def test_poll_mode_looks_again_at_a_bounded_interval_and_ingests_a_late_row(self) -> None:
        self.shell.rows = [row("authoring-task")]
        leader, campaign = self.build()
        leader.prepare()
        self.assertTrue(leader.drained())

        leader._wait_for_rows()
        self.assertIn("queue: no runnable rows; polling every 30s", self.out.getvalue())
        reads = len([call for call in self.shell.calls if "queue" in call])
        leader._wait_for_rows()                    # inside the interval: no read, no line
        self.assertEqual(len([call for call in self.shell.calls if "queue" in call]), reads)

        # The authoring row gains a recipe: the next look adopts it and it becomes assignable.
        self.shell.rows = [dict(row("authoring-task"), recipe="recipes/lane/two.yaml", tp=1,
                                node_cost="single")]
        leader._last_poll = 0.0
        leader._wait_for_rows()
        self.assertEqual(campaign.order, ["two"])
        self.assertIn("1 new runnable row(s): two", self.out.getvalue())
        self.assertFalse(leader.drained())
        self.assertEqual(leader.handle(protocol.poll("w1"))["lease"]["arm"], "two")

    def test_a_transient_register_error_does_not_kill_the_service(self) -> None:
        def broken(command, **kwargs):
            self.shell.calls.append(list(command))
            return subprocess.CompletedProcess(command, 1, "", "queue file is not valid JSON")

        self.shell.rows = [row("authoring-task")]
        leader, _ = self.build()
        leader.prepare()
        leader.register._run = broken
        leader._wait_for_rows()
        self.assertIn("queue: cannot read the register", self.out.getvalue())


class Reconciliation(QueueCase):
    """State, register and CLI precedence on a restart: which side is authoritative for what.

    The register is newer while an arm has never been leased; the state record is newer once it
    has. `--receipts-root` is newer than both because it is this run's decision, and a row flipped
    back to `queued` re-opens the gate without proving anything about the hosts.
    """

    def rows(self, env: dict | None = None, state_: str = "queued") -> None:
        self.shell.rows = [row("task-one", "recipes/lane/one.yaml", 1, state_=state_,
                               node_cost="single", env=env)]

    def test_a_pending_arm_adopts_its_rows_current_env_and_the_runs_receipts_root(self) -> None:
        self.rows({"ARM_EXTRA_CLIENT": "python3 -B tools/old-client.py"})
        leader, campaign = self.build()
        leader.prepare()
        self.assertEqual(campaign.arm("one")["env"],
                         {"ARM_EXTRA_CLIENT": "python3 -B tools/old-client.py",
                          "ARM_RECEIPTS_ROOT": str(self.receipts)})
        campaign.close()

        self.rows({"ARM_EXTRA_CLIENT": "python3 -B tools/new-client.py"})
        leader, campaign = self.build()
        leader.prepare()
        self.assertEqual(campaign.arm("one")["env"],
                         {"ARM_EXTRA_CLIENT": "python3 -B tools/new-client.py",
                          "ARM_RECEIPTS_ROOT": str(self.receipts)})
        self.assertEqual([event["kind"] for event in campaign.arm("one")["history"]],
                         ["plan", "reconcile"], "one refresh, and a second prepare changes nothing")
        lease = leader.handle(protocol.poll("w1"))["lease"]
        self.assertEqual(lease["env"]["ARM_EXTRA_CLIENT"], "python3 -B tools/new-client.py")

    def test_a_live_lease_keeps_the_env_it_was_assigned_with(self) -> None:
        self.rows({"ARM_EXTRA_CLIENT": "old-client"})
        leader, campaign = self.build()
        leader.prepare()
        self.assertEqual(leader.handle(protocol.poll("w1"))["lease"]["env"]["ARM_EXTRA_CLIENT"],
                         "old-client")

        self.rows({"ARM_EXTRA_CLIENT": "new-client"})
        leader.refresh()                       # the poll-mode re-read while the arm is running
        self.assertEqual(campaign.arm("one")["status"], "leased")
        self.assertEqual(campaign.arm("one")["env"]["ARM_EXTRA_CLIENT"], "old-client",
                         "a running arm's launch fields are frozen until its next attempt")

    def test_a_measured_arm_keeps_the_env_it_ran_with(self) -> None:
        self.rows({"ARM_EXTRA_CLIENT": "old-client"})
        leader, campaign = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        receipt(self.receipts, lease["arm"], cells=2)
        self.assertEqual(leader.handle(protocol.report(lease["id"], 0, "log run.log"))["status"],
                         "measured")
        campaign.close()

        self.rows({"ARM_EXTRA_CLIENT": "new-client"})
        leader, campaign = self.build()
        leader.prepare()
        self.assertEqual(campaign.arm("one")["status"], "measured")
        self.assertEqual(campaign.arm("one")["env"]["ARM_EXTRA_CLIENT"], "old-client")

    def test_a_failed_arms_next_attempt_adopts_the_rows_new_env_cells(self) -> None:
        self.rows({"ARM_ALLOW_FEW_SLOTS": "1"})
        leader, campaign = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        receipt(self.receipts, lease["arm"], cells=0)        # the attempt failed its ladder
        self.assertEqual(leader.handle(protocol.report(lease["id"], 0, "log run.log"))["status"],
                         "failed")
        self.assertEqual(campaign.arm("one")["attempts"], 1)
        campaign.close()

        # The row is reopened with a readiness ceiling and a client hook: they belong to the next
        # boot, not to the one already receipted, so the retry lease must carry them.
        self.rows({"ARM_ALLOW_FEW_SLOTS": "1", "ARM_READY_TIMEOUT": "3000",
                   "ARM_EXTRA_CLIENT": "python3 -B tools/client.py"})
        leader, campaign = self.build(retries=1)
        leader.prepare()
        self.assertEqual(campaign.arm("one")["env"]["ARM_READY_TIMEOUT"], "3000")
        resumed = leader.handle(protocol.poll("w1"))["lease"]
        self.assertEqual(resumed["id"], "one@2")
        self.assertEqual(resumed["env"]["ARM_READY_TIMEOUT"], "3000")
        self.assertEqual(resumed["env"]["ARM_EXTRA_CLIENT"], "python3 -B tools/client.py")

    def test_a_blocked_arm_runs_when_its_row_is_queued_again(self) -> None:
        self.rows()
        self.shell.refuse_writes = True        # claim refused: the arm is blocked, never booted
        leader, campaign = self.build()
        leader.prepare()
        self.assertIsNone(leader.handle(protocol.poll("w1")).get("lease"))
        self.assertEqual(campaign.arm("one")["status"], "blocked")
        self.assertEqual(campaign.arm("one")["attempts"], 0)
        campaign.close()

        self.shell.refuse_writes = False
        leader, campaign = self.build()
        leader.prepare()
        self.assertEqual(campaign.arm("one")["status"], "pending")
        self.assertIn("queue-unblocked: one", self.out.getvalue())
        self.assertEqual(leader.handle(protocol.poll("w1"))["lease"]["arm"], "one")
        self.assertEqual(flag(self.shell.last_update("task-one"), "--state"), "running")

    def test_a_blocked_arm_stays_blocked_while_its_row_is_blocked(self) -> None:
        self.rows()
        self.shell.refuse_writes = True
        leader, campaign = self.build()
        leader.prepare()
        leader.handle(protocol.poll("w1"))
        self.assertEqual(campaign.arm("one")["status"], "blocked")
        campaign.close()

        self.rows(state_="blocked")
        leader, campaign = self.build()
        leader.prepare()
        self.assertEqual(campaign.arm("one")["status"], "blocked")
        self.assertNotIn("queue-unblocked: one", self.out.getvalue())
        self.assertIsNone(leader.handle(protocol.poll("w1")).get("lease"))

    def test_a_queued_arm_stays_unassignable_until_a_verified_reap(self) -> None:
        self.rows()
        leader, campaign = self.build()
        leader.prepare()
        self.assertEqual(leader.handle(protocol.poll("w1"))["lease"]["arm"], "one")
        campaign.close()                       # the process died mid-arm: no stop, no report
        self.clock.now += state.LEASE_TTL + 1

        def unreachable(hosts, recipe_path):
            raise OSError("ssh refused")

        self.fleet.reap = unreachable
        leader, campaign = self.build()
        leader.prepare()
        self.assertEqual(campaign.arm("one")["status"], "blocked")
        self.assertEqual(campaign.arm("one")["needs_reap"], ["node-a"])
        self.assertIn("hosts still need a verified reap", self.out.getvalue(),
                      "a queued row must not silently leave a reaped-none arm unassignable")
        self.assertIsNone(leader.handle(protocol.poll("w1")).get("lease"))
        campaign.close()

        self.fleet = FakeFleet()
        leader, campaign = self.build()
        leader.prepare()
        self.assertEqual(campaign.arm("one")["status"], "pending")
        self.assertEqual(campaign.arm("one")["needs_reap"], [])
        self.assertEqual(leader.handle(protocol.poll("w1"))["lease"]["id"], "one@2")

    def test_an_arm_the_register_no_longer_carries_is_blocked_not_booted(self) -> None:
        self.rows()
        leader, campaign = self.build()
        leader.prepare()
        campaign.close()

        self.shell.rows = []
        leader, campaign = self.build()
        leader.prepare()
        self.assertEqual(campaign.arm("one")["status"], "blocked")
        self.assertIn("no longer a runnable row", campaign.arm("one")["last"]["reason"])
        self.assertIsNone(leader.handle(protocol.poll("w1")).get("lease"))


class Holds(QueueCase):
    """A register hold is read at assignment time, not remembered from the plan's last read."""

    def single(self, **overrides) -> None:
        entry = row("task-one", "recipes/lane/one.yaml", 1, node_cost="single")
        if "state_" in overrides:
            entry["state"] = overrides.pop("state_")
        entry.update(overrides)
        self.shell.rows = [entry]

    def test_a_row_flipped_to_blocked_after_prepare_is_not_assigned(self) -> None:
        self.single()
        leader, campaign = self.build()
        leader.prepare()
        # A peer writes the hold while the campaign is busy; no re-read of the plan has happened.
        self.single(state_="blocked",
                    notes="DECISION 2026-11-08 04:22 ET: BLOCKED, do not re-boot")
        self.assertIsNone(leader.handle(protocol.poll("w1")).get("lease"))
        record = campaign.arm("one")
        self.assertEqual(record["status"], "blocked")
        self.assertIn("register state 'blocked'", record["last"]["reason"])
        self.assertIn("state.json had pending", record["last"]["reason"])
        self.assertIn("the register wins", self.out.getvalue())
        self.assertEqual(self.shell.states("task-one"), [],
                         "a held row must not be overwritten by a claim")

    def test_a_queued_row_with_a_blocking_edge_is_never_assigned(self) -> None:
        self.single()
        leader, campaign = self.build()
        leader.prepare()
        self.single(blocked_by=["dep-task"])
        self.assertIsNone(leader.handle(protocol.poll("w1")).get("lease"))
        self.assertIn("blocked by dep-task", campaign.arm("one")["last"]["reason"])
        self.assertEqual(self.shell.states("task-one"), [])

    def test_a_missing_blocked_by_mirror_is_not_an_edit_that_opens_the_hold(self) -> None:
        self.single()
        leader, campaign = self.build()
        leader.prepare()
        entry = dict(self.shell.rows[0])
        del entry["blocked_by"]
        self.shell.rows = [entry]
        self.assertIsNone(leader.handle(protocol.poll("w1")).get("lease"))
        self.assertIn("no blocked_by list", campaign.arm("one")["last"]["reason"])

    def test_a_hold_at_prepare_is_named_and_never_planned(self) -> None:
        self.single(state_="blocked")
        leader, campaign = self.build()
        leader.prepare()
        self.assertEqual(campaign.order, [])
        self.assertIn("queue-skip: task-one (register state blocked)", self.out.getvalue())

    def test_a_hold_that_lands_between_the_claim_and_the_lease_wins(self) -> None:
        self.single()
        leader, campaign = self.build()
        leader.prepare()
        original = leader.register._run

        def flip(command, **kwargs):
            result = original(command, **kwargs)
            if "update" in command and flag(command, "--state") == "running":
                self.single(state_="blocked")   # the peer's hold lands after our claim
            return result

        leader.register._run = flip
        self.assertIsNone(leader.handle(protocol.poll("w1")).get("lease"),
                          "the lease is issued after the re-read, so no boot can have happened")
        self.assertEqual(campaign.arm("one")["status"], "blocked")
        self.assertIn("state.json had pending", campaign.arm("one")["last"]["reason"])

    def test_the_control_state_alone_assigns_the_held_row(self) -> None:
        held = {"tp": 1, "status": "pending", "failures": 0, "needs_reap": []}
        self.assertEqual(plan.next_assignment(["one"], {"one": held}, ["node-a"]),
                         ("one", ("node-a",)),
                         "the cached state cannot see the register; _admit is the guard")

    def test_a_recipe_named_by_a_stricter_row_is_held_at_plan(self) -> None:
        queued = row("queued-row", "recipes/lane/one.yaml", 1, node_cost="single")
        blocked = row("blocked-row", "recipes/lane/one.yaml", 1, state_="blocked",
                      node_cost="single")
        self.shell.rows = [queued, blocked]
        leader, campaign = self.build()
        leader.prepare()
        self.assertEqual(campaign.order, [])
        self.assertIn("queue-skip: queued-row (recipe also named by sibling blocked-row "
                      "is 'blocked')", self.out.getvalue())
        campaign.close()

        done = dict(blocked, id="done-row", state="done")
        self.shell.rows = [queued, done]
        leader, campaign = self.build()
        leader.prepare()
        self.assertEqual(campaign.order, [])
        self.assertIn("sibling done-row is 'done'", self.out.getvalue())

    def test_a_blocked_sibling_holds_the_queued_row_at_assignment(self) -> None:
        self.single()
        leader, campaign = self.build()
        leader.prepare()
        self.shell.rows.append(row("hold-row", "recipes/lane/one.yaml", 1, state_="blocked",
                                   node_cost="single"))
        self.assertIsNone(leader.handle(protocol.poll("w1")).get("lease"))
        self.assertIn("sibling hold-row is 'blocked'", campaign.arm("one")["last"]["reason"])

    def test_close_out_does_not_requeue_a_row_a_hold_reached_first(self) -> None:
        self.single()
        leader, campaign = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        receipt(self.receipts, lease["arm"], cells=0)
        self.single(state_="blocked")       # the human's hold lands while the arm runs
        self.assertEqual(leader.handle(protocol.report(lease["id"], 0, "log run.log"))["status"],
                         "failed")
        last = self.shell.last_update("task-one")
        self.assertNotIn("--state", last, "a failed close-out must not requeue over a hold")
        self.assertIn("campaign:", flag(last, "--notes"))
        self.assertIn("keeps its blocked hold", self.out.getvalue())

    def test_raising_retries_does_not_arm_a_held_failed_row(self) -> None:
        self.single()
        leader, campaign = self.build()
        leader.prepare()
        lease = leader.handle(protocol.poll("w1"))["lease"]
        receipt(self.receipts, lease["arm"], cells=0)
        leader.handle(protocol.report(lease["id"], 0, "log run.log"))
        self.assertEqual(campaign.arm("one")["status"], "failed")
        campaign.close()

        self.single(state_="blocked")
        leader, campaign = self.build(retries=3)
        leader.prepare()
        self.assertEqual(campaign.arm("one")["status"], "blocked")
        self.assertIn("register state blocked", campaign.arm("one")["last"]["reason"])
        self.assertIsNone(leader.handle(protocol.poll("w1")).get("lease"))


class RealRegister(unittest.TestCase):
    """The argv this package builds, against the tool's real parser and atomic save."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "checkout"
        recipe(self.repo, "lane", "arm")
        queue = self.repo / "mad-science" / "queue.json"
        queue.parent.mkdir(parents=True)
        queue.write_text(json.dumps({"priority_models": [], "tasks": [row(
            "campaign-arm", "recipes/lane/arm.yaml", 1, node_cost="single")]}), encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "add", "--",
                        "recipes/lane/arm.yaml", "mad-science/queue.json"], check=True)
        self.queue = queue
        self.register = plan.Register(Path(fleet.default_repo_root()) / "tools" / "task-queue.py",
                                      queue, SESSION)

    def task(self) -> dict:
        return json.loads(self.queue.read_text(encoding="utf-8"))["tasks"][0]

    def test_a_claim_then_a_done_round_trips_through_the_tool(self) -> None:
        self.assertEqual([entry["id"] for entry in self.register.rows()], ["campaign-arm"])
        self.register.update("campaign-arm", state="running", claimed_by=SESSION)
        self.assertEqual((self.task()["state"], self.task()["claimed_by"]),
                         ("running", SESSION))
        self.assertTrue(self.task()["claimed_at"])
        self.assertEqual(self.register.note("campaign-arm", "campaign: failed (rc=3)"),
                         "why campaign-arm exists \u2014 campaign: failed (rc=3)")
        self.register.update("campaign-arm", state="done", evidence="~/benchmarks/tp12-x/arm")
        self.assertEqual((self.task()["state"], self.task()["evidence"], self.task()["claimed_by"]),
                         ("done", "~/benchmarks/tp12-x/arm", ""))

    def test_a_returned_row_keeps_no_claim(self) -> None:
        """Failed and blocked paths, through the tool: the row is not left looking claimed."""
        self.register.update("campaign-arm", state="running", claimed_by=SESSION)
        self.assertEqual((self.task()["state"], self.task()["claimed_by"]), ("running", SESSION))

        self.register.update("campaign-arm", state="queued",
                             notes=self.register.note("campaign-arm", "campaign: ladder failed"))
        self.assertEqual((self.task()["state"], self.task()["claimed_by"],
                          self.task()["claimed_at"]), ("queued", "", ""))
        self.assertEqual(self.task()["notes"],
                         "why campaign-arm exists \u2014 campaign: ladder failed")

        self.register.update("campaign-arm", state="running", claimed_by=SESSION)
        self.register.update("campaign-arm", state="blocked",
                             notes=self.register.note("campaign-arm", "campaign: leftover"))
        self.assertEqual((self.task()["state"], self.task()["claimed_by"],
                          self.task()["claimed_at"]), ("blocked", "", ""))
        self.assertIn("campaign: leftover", self.task()["notes"])

    def test_an_untracked_recipe_is_refused_by_the_real_tool(self) -> None:
        subprocess.run(["git", "-C", str(self.repo), "rm", "--cached", "-q",
                        "recipes/lane/arm.yaml"], check=True)
        with self.assertRaises(plan.RegisterError) as ctx:
            self.register.rows()
        self.assertIn("not a tracked file", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()