"""Fleet probes and removal: what counts as "clean", and the rank-0-only defect as a control.

Item 5 (every rank) and item 6 (nothing left on any host) are decided off-hardware here, because
the listing, the grammar and the removal commands are all pure text. The one thing a test cannot do
is run them against a node -- `tests/test_checklist_hardware.py` keeps that item visible.
"""

from __future__ import annotations

import unittest

from sparkrun_campaign import fleet

RECIPE = "recipes/lane/one.yaml"


class FakeRunner:
    """A node whose container listing is a dict of host -> names; removals mutate it."""

    def __init__(self, listing: dict[str, list[str]] | None = None, remove: bool = True):
        self.listing = {host: list(names) for host, names in (listing or {}).items()}
        self.remove = remove
        self.calls: list[tuple[str, str]] = []

    def __call__(self, host: str, script: str) -> tuple[int, str]:
        self.calls.append((host, script))
        if script.startswith("docker ps"):
            return 0, "\n".join(self.listing.get(host, []))
        if script.startswith("docker rm -f "):
            name = script.split()[-1]
            if self.remove:
                self.listing[host] = [item for item in self.listing.get(host, []) if item != name]
            return 0, ""
        return 2, ""

    def removed_names(self) -> list[str]:
        return [script.split()[-1] for _, script in self.calls if script.startswith("docker rm")]


class Grammar(unittest.TestCase):
    def test_the_launchers_container_names_are_recognised(self) -> None:
        for name in ("sparkrun_abc_solo", "sparkrun_abc_node_0", "sparkrun_abc_node_11",
                     "sparkrun_abc_def-1.2_node_1"):
            with self.subTest(name=name):
                self.assertTrue(fleet.is_arm_container(name))

    def test_a_name_outside_the_grammar_is_not_ours(self) -> None:
        for name in ("sparkrun_abc", "sparkrun_abc_sidecar", "other_abc_solo",
                     "sparkrun_abc_node_x", "sparkrun__solo"):
            with self.subTest(name=name):
                self.assertFalse(fleet.is_arm_container(name))

    def test_the_task_id_is_recovered_from_a_rank_name(self) -> None:
        self.assertEqual(fleet.task_id("sparkrun_t123_node_3"), "t123")
        self.assertIsNone(fleet.task_id("not-a-container"))

    def test_the_probe_is_scoped_by_the_recipes_own_label(self) -> None:
        script = fleet.list_script(RECIPE)
        self.assertIn(f"label={fleet.LABEL}={RECIPE}", script)
        self.assertIn("-a", script)


class Leftovers(unittest.TestCase):
    def test_every_rank_on_every_host_is_found(self) -> None:
        run = FakeRunner({"node-a": ["sparkrun_t1_node_0"], "node-b": ["sparkrun_t1_node_1"]})
        self.assertEqual(
            fleet.leftovers(["node-a", "node-b"], RECIPE, run=run),
            [("node-a", "sparkrun_t1_node_0"), ("node-b", "sparkrun_t1_node_1")],
        )

    def test_a_failed_probe_raises_instead_of_reading_clean(self) -> None:
        def broken(host: str, script: str) -> tuple[int, str]:
            return 255, ""

        with self.assertRaises(OSError):
            fleet.leftovers(["node-a"], RECIPE, run=broken)

    def test_only_grammar_matched_names_are_removed(self) -> None:
        run = FakeRunner({"node-a": ["sparkrun_t1_node_0", "a-peers-container"]})
        result = fleet.reap(["node-a"], RECIPE, run=run, stop=lambda task: None)
        self.assertEqual(result["found"], [("node-a", "sparkrun_t1_node_0")])
        self.assertEqual(run.removed_names(), ["sparkrun_t1_node_0"])
        self.assertEqual(result["after"], [])

    def test_a_stubborn_container_is_reported_not_forgiven(self) -> None:
        run = FakeRunner({"node-b": ["sparkrun_t1_node_1"]}, remove=False)
        result = fleet.reap(["node-a", "node-b"], RECIPE, run=run, stop=lambda task: None)
        self.assertEqual(result["after"], [("node-b", "sparkrun_t1_node_1")])

    def test_the_launcher_is_asked_to_stop_the_task_too(self) -> None:
        stopped: list[str] = []
        run = FakeRunner({"node-a": ["sparkrun_t1_node_0"]})
        fleet.reap(["node-a"], RECIPE, run=run, stop=stopped.append)
        self.assertEqual(stopped, ["t1"])

    def test_no_command_can_delete_by_list_expansion(self) -> None:
        run = FakeRunner({"node-a": ["sparkrun_t1_node_0"]})
        fleet.reap(["node-a"], RECIPE, run=run, stop=lambda task: None)
        for _, script in run.calls:
            for forbidden in ("ps -aq", "xargs", "prune", "$("):
                self.assertNotIn(forbidden, script)


class NegativeControls(unittest.TestCase):
    def test_a_rank0_only_check_reports_clean_with_rank1_alive(self) -> None:
        """The 2026-11-04 defect: the API rank was checked, rank 1 was still serving, rc=0."""

        # The API rank is clean; the second host still runs the arm's rank 1.
        listing = {"node-a": [], "node-b": ["sparkrun_t1_node_1"]}

        def rank0_only(hosts: list[str]) -> list[tuple[str, str]]:
            return [(hosts[0], name) for name in listing.get(hosts[0], [])
                    if fleet.is_arm_container(name)]

        self.assertEqual(rank0_only(["node-a", "node-b"]), [])
        found = fleet.leftovers(["node-a", "node-b"], RECIPE, run=FakeRunner(listing))
        self.assertEqual(found, [("node-b", "sparkrun_t1_node_1")])


if __name__ == "__main__":
    unittest.main()