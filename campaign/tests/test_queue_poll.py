"""The serve loop's poll gate: the register is re-read on every tick, not only once drained.

Measured 2026-11-21 (head `red@10.0.4.30`, `NRestarts=0`): a pending quartet with two free hosts
made `plan.next_assignment` return None, so `drained()` never turned true and the one call that
re-reads the register sat behind that gate. The register was written at 16:10; the plan in force
was built at 00:12 and never looked again. These cases pin the loop's gate -- a row queued after
start-up is ingested on the next idle poll even while an unplaceable arm waits, `--once` still
drains and exits, and a poll that runs while a lease is live never hands out a second assignment.
`refresh()` itself is covered by `test_queue_mode`.

No socket and no fleet: `_bind` returns a stand-in whose `handle_request` is one pass of the loop.
"""

from __future__ import annotations

import unittest

from sparkrun_campaign import leases, protocol, state

from .test_queue_mode import QueueCase, row


class TickingServer:
    """Stands in for the unix server: each `handle_request` is one pass of the serve loop."""

    def __init__(self, leader, on_tick=None, ticks: int = 2):
        self.leader = leader
        self.on_tick = on_tick
        self.limit = ticks
        self.ticks = 0

    def handle_request(self) -> None:
        self.ticks += 1
        if self.on_tick is not None:
            self.on_tick(self.ticks)
        if self.ticks >= self.limit:
            self.leader._stop = True

    def server_close(self) -> None:
        pass


class PollGate(QueueCase):
    HOSTS = ("node.30", "node.31", "node.32", "node.33", "node.34", "node.35")

    def test_a_row_queued_behind_an_unplaceable_arm_is_ingested_on_the_next_poll(self) -> None:
        self.shell.rows = [row("quartet-task", "recipes/lane/one.yaml", 4, node_cost="quartet")]
        # Four ranks held by another session: two free hosts cannot place a quartet, so the arm
        # stays pending and `drained()` stays false -- exactly the state that froze ingestion.
        leases.Ledger(self.repo / leases.LEDGER, clock=self.clock).acquire(
            "another-session", ["node.31", "node.32", "node.33", "node.34"], ttl=600)
        leader, campaign = self.build(hosts=self.HOSTS)
        late = row("late-task", "recipes/lane/two.yaml", 1, node_cost="single")

        def on_tick(tick: int) -> None:
            if tick == 1:
                self.shell.rows = self.shell.rows + [late]   # queued after start-up

        server = TickingServer(leader, on_tick)
        leader._bind = lambda: server
        self.assertEqual(leader.serve(), 0)
        self.assertEqual(server.ticks, 2, "the loop kept serving: nothing drained")

        self.assertFalse(leader.drained(), "the quartet still waits for four free hosts")
        self.assertEqual(campaign.order, ["one", "two"], "the late row is in the plan")
        self.assertEqual(campaign.arm("one")["status"], state.PENDING)
        self.assertEqual(campaign.arm("one")["attempts"], 0, "the unplaceable arm was not booted")
        lease = leader.handle(protocol.poll("w1"))["lease"]
        self.assertEqual((lease["arm"], lease["hosts"]), ("two", ["node.35"]))

    def test_once_drains_the_runnable_rows_and_exits_without_polling(self) -> None:
        # A recorded negative resolves at prepare, so the plan drains before any worker poll.
        self.shell.rows = [row("negative-task", "recipes/lane/negative.yaml", 1,
                               node_cost="single")]
        leader, campaign = self.build(once=True)
        server = TickingServer(leader, ticks=2)
        leader._bind = lambda: server
        self.assertEqual(leader.serve(), 0)
        self.assertIn("plan drained", self.out.getvalue())
        self.assertEqual(campaign.arm("negative")["status"], state.SKIPPED)
        self.assertEqual(server.ticks, 1, "--once exits on the first drained tick")
        self.assertEqual(len([call for call in self.shell.calls if "queue" in call]), 1,
                         "one read at prepare; --once never polls the register again")

    def test_a_poll_while_a_lease_is_live_places_the_arm_once(self) -> None:
        self.shell.rows = [row("task-one", "recipes/lane/one.yaml", 1, node_cost="single")]
        leader, campaign = self.build()
        seen: list[dict] = []

        def on_tick(tick: int) -> None:
            if tick > 1:
                leader._last_poll = 0.0    # force a register read while the lease is live
            reply = leader.handle(protocol.poll("w1"))
            if reply.get("lease"):
                seen.append(reply["lease"])

        server = TickingServer(leader, on_tick, ticks=3)
        leader._bind = lambda: server
        self.assertEqual(leader.serve(), 0)
        self.assertEqual([lease["arm"] for lease in seen], ["one"])
        self.assertEqual(campaign.arm("one")["attempts"], 1)
        assigns = [line for line in self.out.getvalue().splitlines() if line.startswith("assign:")]
        self.assertEqual(len(assigns), 1, assigns)
        self.assertNotIn("queue: no runnable rows", self.out.getvalue(),
                         "a leased arm is not a quiet plan")


if __name__ == "__main__":
    unittest.main()
