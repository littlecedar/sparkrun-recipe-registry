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
        node_cost: str = "", claimed_by: str = "") -> dict:
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

    def build(self, hosts=("node-a", "node-b"), once: bool = False):
        campaign = state.Campaign.open(self.root / "state.json", campaign="test",
                                        hosts=hosts, max_parallel=2)
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
            row("quartet-task", "recipes/lane/one.yaml", 4, node_cost="quartet"),
            row("good-task", "recipes/lane/one.yaml", 1, node_cost="single"),
        ]
        leader, campaign = self.build()
        leader.prepare()
        text = self.out.getvalue()
        self.assertEqual(campaign.order, ["one"])
        self.assertIn("queue-skip: blocked-task (register state blocked)", text)
        self.assertIn("queue-skip: claimed-task (claimed running by another-session)", text)
        self.assertIn("queue: 1 row(s) queued without a recipe (authoring, not bootable)", text)
        self.assertIn("queue-skip: quartet-task (tp=4 needs 4 hosts, 2 declared)", text)
        self.assertNotIn("queue-skip: good-task", text)

    def test_two_rows_naming_one_recipe_are_refused(self) -> None:
        self.shell.rows = [row("a", "recipes/lane/one.yaml", 1, node_cost="single"),
                           row("b", "recipes/lane/one.yaml", 1, node_cost="single")]
        leader, _ = self.build()
        with self.assertRaises(plan.PlanError):
            leader.prepare()

    def test_a_quartet_row_runs_when_four_hosts_are_declared(self) -> None:
        self.shell.rows = [row("quartet-task", "recipes/lane/one.yaml", 4, node_cost="quartet")]
        leader, campaign = self.build(hosts=("n1", "n2", "n3", "n4"))
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

    def test_an_untracked_recipe_is_refused_by_the_real_tool(self) -> None:
        subprocess.run(["git", "-C", str(self.repo), "rm", "--cached", "-q",
                        "recipes/lane/arm.yaml"], check=True)
        with self.assertRaises(plan.RegisterError) as ctx:
            self.register.rows()
        self.assertIn("not a tracked file", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()