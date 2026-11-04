"""The acceptance checklist, item by item; the ones that need an arm are here as skipped tests.

An item is done when the campaign run shows it, not when the code compiles, so this module keeps
the four hardware items in the suite instead of in a prose checklist. Each skipped test names the
receipt evidence the campaign run must produce; un-skipping one is a code change someone makes when
they want to re-litigate the claim, and the reason string says what to look for.

Item map (off-hardware halves live in the modules named):

1. reads the skip source, prints `skip: <arm> (<verdict>, <doc>:<line>)` before any boot
   -> `test_director.SkipSource`, `test_evidence.SkipSource`
2. reads receipt FIELDS (`ladder` / `accuracy_status`), not file presence
   -> `test_evidence.ReceiptFields`, `test_director.CompletionIsReadFromReceipts`
3. reaps a dead serve in <= 2 probes                -> skipped below (needs a boot)
4. preserves the serve log across that reap          -> partially proven: the receipt names the
   harvested logs (`test_director...test_the_receipt_keeps_the_serve_log_of_a_watchdog_reaped_arm`);
   the live capture is skipped below
5. reaps EVERY rank, not rank 0 alone                -> grammar/listing half proven
   (`test_fleet`), the live teardown is skipped below
6. leaves no container behind on any host after any arm -> the block-and-record half is proven
   (`test_director.Leftovers`); the live absence is skipped below
7. resumes a half-finished campaign after a reboot   -> `test_director.Resume`
8. writes per-arm receipts                          -> `test_director.CompletionIsReadFromReceipts`
"""

from __future__ import annotations

import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REASON = ("needs a real arm: satisfied by the phase-2 unattended campaign run, which must show it "
          "in the per-arm receipts under the campaign root and in each arm's tp12-* window")


class HardwareItems(unittest.TestCase):
    @unittest.skip(REASON + " -- item 3: a serve that dies during load is stopped on the second "
                            "consecutive observed absence; the watchdog log must read verdict=dead "
                            "at the second observation (~2 probes at --interval 10)")
    def test_item_3_reaps_a_dead_serve_within_two_probes(self) -> None:
        """Evidence: `<window>/<arm>/watchdog.log` has `verdict=dead` on the second sighting, and
        `run-arm.sh` ends the arm without waiting out its readiness loop."""

    @unittest.skip(REASON + " -- item 4: after that reap the arm's receipt still carries the "
                            "engine's own log, harvested before the stop made it unreachable")
    def test_item_4_preserves_the_serve_log_across_the_reap(self) -> None:
        """Evidence: `<window>/<arm>/serve-node_0.log` exists for an arm whose watchdog verdict is
        `dead`, and the campaign receipt's `serve_logs` names it."""

    @unittest.skip(REASON + " -- item 5: after the stop, a rank-1 container on the second host is "
                            "gone too; the 2026-11-04 failure was a survivor that reported rc=0")
    def test_item_5_reaps_every_rank_on_every_host(self) -> None:
        """Evidence: the campaign receipt's `leftovers` is empty for an arm that ran TP=2, and the
        end-of-arm probe asked both hosts."""

    @unittest.skip(REASON + " -- item 6: no container of any finished arm remains on any host the "
                            "campaign used; a survivor blocks the arm instead of being reported as "
                            "clean")
    def test_item_6_leaves_no_container_behind(self) -> None:
        """Evidence: every receipt's `leftovers` is empty, and a post-campaign probe of the
        campaign's hosts lists no `sparkrun_*` container for any planned arm."""

    @unittest.skip(REASON + " -- the umbrella: one unattended multi-arm campaign on the declared "
                            "node set, covering all eight items in one run with no human step")
    def test_the_unattended_multi_arm_campaign(self) -> None:
        """Evidence: the campaign root's `state.json` shows every arm measured/failed/skipped with
        no lease left, `receipts/` holds one JSON per arm, and the journal shows the `skip:` lines
        before the first `assign:` line."""


class Preflight(unittest.TestCase):
    """What the campaign cannot satisfy items 3-6 without, checked before a window is spent."""

    @unittest.skipUnless((REPO / "tools" / "run-arm.sh").is_file(), "tools/ tree not present")
    def test_the_per_arm_executor_exists(self) -> None:
        self.assertTrue((REPO / "tools" / "run-arm.sh").is_file())
        self.assertTrue((REPO / "tools" / "boot-watchdog.py").is_file())


if __name__ == "__main__":
    unittest.main()