"""Guards for tools/cache-audit.py and the policy it serves.

Run:
    uv run python -B -m unittest discover -s tests

Stdlib-only, no network, no cluster, like every other guard here.

Why this file exists.  `tools/cache-audit.py` decides which of ~99 runtime-cache trees on six nodes is
still served by a shipped recipe, and its answer is used to delete things.  Two of its rules are
load-bearing and neither is observable from the tool's output on a happy path:

1. **The leaf key is sparkrun's, not ours.**  ``sanitize(model)[:48] + "-" + sha256("<model>@<revision>")[:8]``
   — including the 48-char truncation, which silently changes the key for a long model id
   (``…-AEON-ULTIMATE-UNCENSO-b9f737e7``).  The fixture below is the set of leaves *read off the fleet*
   on 2026-10-15 plus the ``model@revision`` each was launched with, so it fails if either sparkrun
   changes its derivation or the tool drifts from it.
2. **"stale" means no recipe produces the key**, never "this looks old".  The negative controls pin
   that: a live pin, an attic-only arm, and the two ds4 leftovers (the pre-pin and the image's baked
   revision) must come out of ``recipe_keys``/``verdict`` on different verdicts, and the 72 h in-use
   rule must override the reclaim action rather than the verdict.

Nothing here re-implements the tool.  The fixture triples are the measurement; the test asks the tool
to agree with them.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "cache-audit.py"
POLICY = REPO_ROOT / "mad-science" / "STORAGE-POLICY.md"
POLICY_INDEX = REPO_ROOT / "mad-science" / "README.md"

FAMILY_DIR = "/<home-dir>/.cache/sparkrun/runtime-cache/sglang"

#: ``(model, model_revision, leaf observed on the fleet 2026-10-15)``.  The
#: first is the knapcio pin, the second the *same model unpinned* (an empty
#: revision), the third the revision the serving image bakes and the lane
#: explicitly does not serve — the three that could not be told apart by
#: `modlogs/` alone.
FLEET_LEAVES = [
    ("deepseek-ai/DeepSeek-V4.1-Flash", "5254448103b6254fc646dacbca1cbbf20e9216c1",
     "deepseek-ai__DeepSeek-V4.1-Flash-11826f49"),
    ("deepseek-ai/DeepSeek-V4.1-Flash", "", "deepseek-ai__DeepSeek-V4.1-Flash-9a74d993"),
    ("deepseek-ai/DeepSeek-V4.1-Flash", "fb2764a5cf321eaa5070ca8f9e892818f477c16d",
     "deepseek-ai__DeepSeek-V4.1-Flash-db95f94c"),
    ("littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram", "",
     "littlecedar__DeepSeek-V4.1-Flash-EXL3-2.9bpw-wit-2bd42ac5"),
    ("Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw", "64ba41b6c916a587db06eae2e19b7845f7be6e6b",
     "Mia-AiLab__DeepSeek-V4.1-Flash-EXL3-2.9bpw-a54d5c5d"),
    ("sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4",
     "8d5a3317b4fcb6f278e1cde7fcae5ed88a27443a",
     "sakamakismile__Qwen3.8-27B-AEON-ULTIMATE-UNCENSO-b9f737e7"),
]

#: Leaves the fleet holds that no recipe may claim.
STALE_LEAVES = ["deepseek-ai__DeepSeek-V4.1-Flash-9a74d993", "deepseek-ai__DeepSeek-V4.1-Flash-db95f94c"]


def _load():
    spec = importlib.util.spec_from_file_location("cache_audit", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["cache_audit"] = module
    spec.loader.exec_module(module)
    return module


audit = _load()


class KeyDerivation(unittest.TestCase):
    """The tool's key must equal sparkrun's, on the leaves that actually exist."""

    def test_fleet_leaves_round_trip(self):
        for model, revision, leaf in FLEET_LEAVES:
            self.assertEqual(audit.model_key(model, revision), leaf, f"{model}@{revision}")

    def test_hash_half_is_the_documented_sha256(self):
        # computed here, not by the tool, so a wrong hash length or encoding fails
        model, revision, leaf = FLEET_LEAVES[0]
        self.assertEqual(leaf.rsplit("-", 1)[-1], hashlib.sha256(f"{model}@{revision}".encode()).hexdigest()[:8])

    def test_label_truncation_is_active(self):
        # Negative control: the 48-char cap is what makes the AEON leaf readable
        # at all. Without it the label runs on and the key changes, so a reader
        # who "cleans up" the truncation silently mis-attributes long model ids.
        label = "sakamakismile__Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4"
        self.assertEqual(len(audit.sanitize_key_component(label)), 48)
        self.assertEqual(audit.sanitize_key_component(label), "sakamakismile__Qwen3.8-27B-AEON-ULTIMATE-UNCENSO")
        self.assertNotEqual(audit.sanitize_key_component(label, max_len=64), audit.sanitize_key_component(label))

    def test_slash_becomes_double_underscore(self):
        # `/` -> `__` keeps an org-qualified id legible as one path component;
        # a single `-` here is the difference between two directory names.
        self.assertEqual(audit.sanitize_key_component("deepseek-ai/DeepSeek-V4.1-Flash"),
                         "deepseek-ai__DeepSeek-V4.1-Flash")
        self.assertEqual(audit.sanitize_key_component("/abs/path/to/Model"), "abs__path__to__Model")


class RecipeScan(unittest.TestCase):
    """The shipped/attic split, and the negative controls that make it mean something."""

    def setUp(self):
        self.keys = audit.recipe_keys(REPO_ROOT)

    def test_shipped_pin_is_found_and_names_the_recipe(self):
        hits = self.keys.get("deepseek-ai__DeepSeek-V4.1-Flash-11826f49")
        self.assertTrue(hits, "the knapcio pin's leaf is not produced by any recipe")
        self.assertIn("shipped:recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml", hits)

    def test_stale_leftovers_are_produced_by_no_recipe(self):
        for leaf in STALE_LEAVES:
            self.assertNotIn(leaf, self.keys, f"{leaf} IS produced by a recipe; it must not read as stale")

    def test_retired_arm_is_classified_retired_not_live(self):
        # RadixArk/Qwen3.8-Flash-Next-NVFP4 was archived to attic/qwen4 on
        # 2026-10-14; its key must still resolve, but never as shipped.
        hits = self.keys.get("RadixArk__Qwen3.8-Flash-Next-NVFP4-20f83727")
        self.assertTrue(hits, "the archived qwen4 arm's leaf is not produced by any recipe")
        self.assertTrue(all(h.startswith("retired:") for h in hits), hits)
        verdict, detail = audit.verdict(audit.Tree("h", f"{FAMILY_DIR}/RadixArk__Qwen3.8-Flash-Next-NVFP4-20f83727"), self.keys)
        self.assertEqual(verdict, "retired")
        self.assertTrue(detail.startswith("attic/"), detail)

    def test_a_placeholder_model_is_not_a_repo_id(self):
        # `model: {model}` style arms must not all collapse onto one bogus key.
        keys = audit.recipe_keys(REPO_ROOT)
        self.assertNotIn(audit.model_key("{model}"), keys)
        self.assertTrue(audit.model_key("{model}").endswith("-" + hashlib.sha256(b"{model}@").hexdigest()[:8]))


class CensusParsing(unittest.TestCase):
    """Both receipt shapes, the merge rule, and the keyed/unkeyed boundary."""

    def _receipts(self, tmp: str):
        dry = Path(tmp) / "dry.txt"
        dry.write_text(
            f"  would-remove    45.0 GB  .NN:{FAMILY_DIR}/deepseek-ai__DeepSeek-V4.1-Flash-db95f94c\n"
            "Would remove 1 tree(s), 45.0 GB.\n",
            encoding="utf-8",
        )
        listing = Path(tmp) / "ls.txt"
        listing.write_text(
            "##### .NN\n"
            f"49501500K\t2026-10-10_13:59\t{FAMILY_DIR}/deepseek-ai__DeepSeek-V4.1-Flash-db95f94c\n"
            f"49980704K\t2026-10-13_11:13\t{FAMILY_DIR}/deepseek-ai__DeepSeek-V4.1-Flash-9a74d993\n",
            encoding="utf-8",
        )
        return dry, listing

    def test_dry_run_row_merges_with_the_fine_listing(self):
        with tempfile.TemporaryDirectory() as tmp:
            dry, listing = self._receipts(tmp)
            parsed = audit.parse_census([dry, listing])
            self.assertEqual(len(parsed), 2, "one row per (host, path)")
            merged = next(t for t in parsed if t.leaf.endswith("db95f94c"))
            # A first-wins parser would keep the dry-run row: 0.1-GB rounding and
            # no marker, which would report every tree as unmarked.
            self.assertEqual(merged.size, 49501500 * 1024, "the finer size must win")
            self.assertEqual(merged.stamp, "2026-10-10_13:59", "the marker must be filled from the listing")
            self.assertEqual(merged.host, ".NN")

    def test_hostless_listing_takes_the_preceding_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            dry, listing = self._receipts(tmp)
            listed = next(t for t in audit.parse_census([dry, listing]) if t.leaf.endswith("9a74d993"))
            self.assertEqual((listed.host, listed.size), (".NN", 49980704 * 1024))

    def test_family_root_is_not_a_keyed_tree(self):
        # The sweep prunes nothing when leaf == family_root; so must the verdict,
        # or a whole family is reported as one stale tree.
        self.assertFalse(audit.Tree("h", FAMILY_DIR).keyed)
        self.assertTrue(audit.Tree("h", f"{FAMILY_DIR}/deepseek-ai__DeepSeek-V4.1-Flash-9a74d993").keyed)
        self.assertEqual(audit.verdict(audit.Tree("h", FAMILY_DIR), {})[0], "unkeyed")

    def test_duplicate_hosts_are_separate_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = Path(tmp) / "two-hosts.txt"
            receipt.write_text(
                f"  would-remove    94.8 GB  .NN:{FAMILY_DIR}/deepseek-ai__DeepSeek-V4.1-Flash-db95f94c\n"
                f"  would-remove    94.8 GB  .NN:{FAMILY_DIR}/deepseek-ai__DeepSeek-V4.1-Flash-db95f94c\n",
                encoding="utf-8",
            )
            self.assertEqual(len(audit.parse_census([receipt])), 2)

    def test_prose_lines_are_not_trees(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = Path(tmp) / "chatter.txt"
            receipt.write_text(
                "Would remove 98 tree(s), 2550.4 GB.\n"
                "Re-run without --dry-run to apply.\n"
                f"# command: sparkrun setup prune-runtime-cache --hosts .NN,.NN\n"
                f"  would-remove    94.8 GB  .NN:{FAMILY_DIR}/deepseek-ai__DeepSeek-V4.1-Flash-db95f94c\n",
                encoding="utf-8",
            )
            self.assertEqual(len(audit.parse_census([receipt])), 1)


class ReclaimVerdict(unittest.TestCase):
    """`live` is never reclaimable, and the 72 h rule gates the action, not the verdict."""

    def setUp(self):
        self.keys = audit.recipe_keys(REPO_ROOT)
        self.now = dt.datetime(2026, 10, 15, 10, 0)

    def _tree(self, leaf: str, stamp: str | None):
        return audit.Tree(".NN", f"{FAMILY_DIR}/{leaf}", size=1, stamp=stamp)

    def test_live_tree_gets_no_reclaim_action(self):
        for _, _, leaf in FLEET_LEAVES[:1] + FLEET_LEAVES[3:5]:
            tree = self._tree(leaf, "2026-01-01_00:00")
            kind, _ = audit.verdict(tree, self.keys)
            self.assertEqual(kind, "live", leaf)
            self.assertEqual(audit.reclaim_note(tree, kind, self.now), "", f"{leaf} must not be reclaimable")

    def test_stale_tree_past_the_window_gets_the_guarded_sweep(self):
        tree = self._tree("deepseek-ai__DeepSeek-V4.1-Flash-db95f94c", "2026-10-10_13:59")
        self.assertEqual(audit.verdict(tree, self.keys)[0], "stale")
        self.assertEqual(audit.reclaim_note(tree, "stale", self.now),
                         "sparkrun setup prune-runtime-cache --hosts .NN --older-than 30")

    def test_superseded_but_warm_is_held_back(self):
        tree = self._tree("deepseek-ai__DeepSeek-V4.1-Flash-9a74d993", "2026-10-13_11:13")
        self.assertEqual(audit.verdict(tree, self.keys)[0], "stale")
        note = audit.reclaim_note(tree, "stale", self.now)
        self.assertTrue(note.startswith("touched 47 h"), note)
        self.assertNotIn("prune-runtime-cache", note, "the 72h rule must withhold the sweep command")

    def test_unmarked_tree_is_never_swept(self):
        # `[ -f "$_marker" ] || continue` in both sparkrun sweeps: an unmarked
        # tree is invisible to them, so it must not be handed the sweep command.
        tree = self._tree("deepseek-ai__DeepSeek-V4.1-Flash-db95f94c", None)
        self.assertTrue(audit.reclaim_note(tree, "stale", self.now).startswith("no .sparkrun-last-used marker"))

    def test_bare_date_never_reports_a_fresher_age(self):
        # A du-style listing with no time is resolved at 00:00, so the tree reads
        # as *older* than it is — the safe direction for a delete decision.
        self.assertEqual(audit.age_hours("2026-10-15", self.now), 10.0)
        self.assertIsNone(audit.age_hours(None, self.now))


class PolicyCrossReference(unittest.TestCase):
    """The tool's README row points at a policy doc that exists and states the budget.

    This guards the *link*, not the numbers: the budget is a dated measurement
    and belongs in the doc, not in a test that would freeze it.
    """

    def test_policy_doc_exists_and_states_the_budget_and_the_mechanism(self):
        self.assertTrue(POLICY.is_file(), f"{POLICY} is cited by tools/README.md and the tool's docstring")
        text = POLICY.read_text(encoding="utf-8")
        self.assertIn("Runtime cache ≤ 0.5 TB per node", text)
        self.assertIn("sparkrun setup prune-runtime-cache", text)
        self.assertIn("tools/cache-audit.py", text)

    def test_policy_is_indexed(self):
        self.assertIn("STORAGE-POLICY.md", POLICY_INDEX.read_text(encoding="utf-8"))

    def test_tracked_policy_carries_no_host_address(self):
        # This tree is distributed to third parties: node labels are `.30`-`.35`
        # and paths are `${WOPR_USER_CACHE}`-anchored, never an address.
        text = POLICY.read_text(encoding="utf-8")
        found = re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text)
        self.assertEqual(found, [], f"address-shaped token(s) in a tracked doc: {found}")


if __name__ == "__main__":
    unittest.main()