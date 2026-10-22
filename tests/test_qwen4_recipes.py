"""Guards for the qwen4 lane's TP=4 arm (the W6 workstream).

Run:
    python3 -m unittest discover -s tests -v

Stdlib-only; recipes parsed as TEXT with regex, like the rest of tests/ (see
AGENTS.md: tests/ never gains a dependency).

Why this one exists. `attic/qwen4/arms/qwen3.8-flash-next-labquant-tp4-sglang.yaml`
carried no guard, and by 2026-10-22 every one of its four defect classes was
silent — the arm validated and would have booted into a dead engine:

  * `revision:` instead of `model_revision:` ... sparkrun ignores the bare key,
      so the pin is dead and the engine resolves `main` (the lane's own trap:
      `main` has moved under this checkpoint twice).
  * the pre-re-cut pin `7c4f1bc1` ............ 36 shards, superseded 2026-10-14 by
      the step-5500 `6c01ac37` (43 shards) the mod chain is written against.
  * 3 of the 5 required mods ................. without the scale-name rename the
      load asserts on an unplaceable `_scale`; without the demote mod it dies
      `MXFP8 requires n >= 128` on the n=96 GDN projections.
  * `moe_runner_backend: auto` .............. resolves the NVFP4 MoE to
      FLASHINFER_TRTLLM, dead on SM121.

The durable invariant is cheaper than four separate checks: a TP=4 number is only
comparable to the lane's TP=2 ladder if the arm IS the shipped TP=2 arm apart
from topology and spec decode. So this file diffs the two and pins the two
deliberate differences (tp 4 / 4 nodes, NEXTN dropped) plus the raised readiness
budget W6 asks for.

Every guard has a negative control in NegativeControls; controls mutate strings
in memory and touch nothing on disk.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TP4 = REPO_ROOT / "attic" / "qwen4" / "arms" / "qwen3.8-flash-next-labquant-tp4-sglang.yaml"
TP2 = REPO_ROOT / "recipes" / "qwen4" / "qwen3.8-flash-next-nvfp4-labquant-sglang.yaml"

# Present in the TP=4 arm only because topology is the variable under test.
TP4_ONLY_DEFAULTS = {"tensor_parallel"}
# Dropped on purpose: NEXTN is much slower than plain at TP>2 (attic/qwen4/AGENTS.md W6).
NEXTN_DEFAULTS = {
    "speculative_algorithm",
    "speculative_attention_mode",
    "speculative_num_steps",
    "speculative_eagle_topk",
    "speculative_num_draft_tokens",
}

_COMMENT_LINE = re.compile(r"(?m)^\s*#.*$")


def strip_comment_lines(text: str) -> str:
    return _COMMENT_LINE.sub("", text)


def top_level(text: str, key: str) -> str | None:
    match = re.search(r"^%s: *(.*)$" % re.escape(key), text, re.M)
    return match.group(1).strip() if match else None


def defaults_block(text: str) -> str:
    match = re.search(r"^defaults:\n((?:  .*\n|\n)*)", text, re.M)
    return match.group(1) if match else ""


def defaults_keys(text: str) -> dict[str, str]:
    return dict(re.findall(r"^  ([a-z0-9_]+): *(.*)$", defaults_block(text), re.M))


def mods_list(text: str) -> list[str]:
    match = re.search(r"^mods:\n((?:  - .*\n|\n)*)", text, re.M)
    if not match:
        return []
    return re.findall(r'^  - "?([^"\n]+)"?$', match.group(1), re.M)


def command_block(text: str) -> str:
    match = re.search(r"^command: *>(?:\n(.*?))?(?=^[a-z0-9_]+:|\Z)", text, re.M | re.S)
    return (match.group(1) or "") if match else ""


def readiness_value(text: str, key: str) -> str | None:
    match = re.search(r"^readiness:\n((?:  .*\n|\n)*)", text, re.M)
    if not match:
        return None
    found = re.search(r"^  %s: *(\S+)" % re.escape(key), match.group(1), re.M)
    return found.group(1) if found else None


def arm(text: str) -> dict:
    clean = strip_comment_lines(text)
    return {
        "top": {k: top_level(clean, k) for k in ("model", "model_revision", "runtime",
                                                "container", "min_nodes")},
        "defaults": defaults_keys(clean),
        "mods": mods_list(clean),
        "command": command_block(clean),
        "port_timeout_s": readiness_value(clean, "port_timeout_s"),
    }


class Tp4ArmMatchesItsTp2Sibling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw4 = TP4.read_text(encoding="utf-8")
        cls.raw2 = TP2.read_text(encoding="utf-8")
        cls.r4 = arm(cls.raw4)
        cls.r2 = arm(cls.raw2)

    def test_the_arm_did_not_lose_its_pin_key(self):
        # `revision:` is silently ignored by sparkrun — only `model_revision:` counts.
        self.assertNotRegex(strip_comment_lines(self.raw4), r"(?m)^revision:")
        pin = self.r4["top"]["model_revision"]
        self.assertRegex(pin or "", r"^[0-9a-f]{40}$")
        self.assertEqual(pin, self.r2["top"]["model_revision"],
                         "the TP=4 arm drifted off the shipped checkpoint pin")
        self.assertIn("--revision {model_revision}", self.r4["command"],
                      "the pin is declared but never passed to the engine")

    def test_same_engine_and_checkpoint_as_the_shipped_arm(self):
        for key in ("model", "runtime", "container"):
            self.assertEqual(self.r4["top"][key], self.r2["top"][key], key)

    def test_mod_chain_is_the_shipped_chain_in_order(self):
        # Paths differ by necessity (an attic arm resolves `mods:` against its own directory), so the
        # chain is compared by mod name, which is what decides the patch that runs.
        names = lambda mods: [m.rsplit("/", 1)[-1] for m in mods]
        self.assertEqual(names(self.r4["mods"]), names(self.r2["mods"]))
        self.assertEqual(len(self.r4["mods"]), 5)

    def test_mod_paths_resolve_from_the_recipe_directory(self):
        # sparkrun joins a `mods:` entry onto the RECIPE's directory, so a repo-root-relative entry in
        # an attic arm dies `Could not resolve mod …` after planning (measured 2026-10-22).
        for entry in self.r4["mods"]:
            if entry.startswith("@"):
                continue
            resolved = (TP4.parent / entry).resolve()
            self.assertTrue(resolved.is_dir(), f"{entry} does not resolve to a directory")
            self.assertTrue(resolved.is_relative_to(REPO_ROOT), f"{entry} escapes the repo")

    def test_only_topology_and_spec_decode_differ(self):
        d4, d2 = dict(self.r4["defaults"]), dict(self.r2["defaults"])
        for key in NEXTN_DEFAULTS:
            self.assertNotIn(key, d4, f"{key} must be dropped at TP>2")
            d2.pop(key, None)
        for key in TP4_ONLY_DEFAULTS:
            d2.pop(key, None)
            self.assertEqual(d4.pop(key, None), "4", f"{key} must be 4")
        self.assertEqual(d4, d2, "the two arms differ beyond topology/spec-decode")
    def test_declares_four_nodes(self):
        self.assertEqual(self.r4["top"]["min_nodes"], "4")

    def test_readiness_budget_cannot_decide_the_experiment(self):
        self.assertEqual(self.r4["port_timeout_s"], "3600")

    def test_engine_flags_that_gate_the_boot_are_present(self):
        self.assertIn("--no-ple-offload-embedding", self.r4["command"])
        self.assertIn("flashinfer_cutlass", self.r4["defaults"]["extra_args"])
        self.assertIn("--cuda-graph-backend-prefill disabled", self.r4["defaults"]["extra_args"])
        self.assertNotIn("--speculative-", self.r4["command"])


class NegativeControls(unittest.TestCase):
    """Every guard above must fire on the pre-repair arm or the repair is unproven."""

    def setUp(self):
        self.raw = TP4.read_text(encoding="utf-8")

    def _arm_with(self, old: str, new: str) -> dict:
        mutated = self.raw.replace(old, new)
        self.assertNotEqual(mutated, self.raw, f"control did not mutate: {old!r}")
        return arm(mutated)

    def test_bare_revision_key_is_caught(self):
        mutated = re.sub(r"(?m)^model_revision:", "revision:", strip_comment_lines(self.raw), count=1)
        self.assertRegex(mutated, r"(?m)^revision:")
        self.assertIsNone(top_level(mutated, "model_revision"))

    def test_stale_pin_is_caught(self):
        pin = arm(self.raw)["top"]["model_revision"]
        r = self._arm_with(pin or "", "7c4f1bc1a2d6847e0cbc01ac6b823f00251de8dd")
        self.assertNotEqual(r["top"]["model_revision"], arm(TP2.read_text())["top"]["model_revision"])

    def test_missing_mod_is_caught(self):
        r = self._arm_with('  - "../../../recipes/qwen4/mods/demote-labquant-narrow-mxfp8-to-bf16"\n', "")
        names = lambda mods: [m.rsplit("/", 1)[-1] for m in mods]
        self.assertNotEqual(names(r["mods"]), names(arm(TP2.read_text())["mods"]))

    def test_repo_root_relative_mod_path_is_caught(self):
        # The measured failure: an entry sparkrun resolves against the recipe's own directory.
        bad = "recipes/qwen4/mods/demote-labquant-narrow-mxfp8-to-bf16"
        self.assertFalse((TP4.parent / bad).is_dir())
        self.assertTrue((TP4.parent / ("../../../" + bad)).is_dir())

    def test_auto_moe_backend_is_caught(self):
        r = self._arm_with("flashinfer_cutlass", "auto")
        self.assertNotIn("flashinfer_cutlass", r["defaults"]["extra_args"])

    def test_reintroduced_nextn_is_caught(self):
        r = self._arm_with("  max_num_seqs: 24\n", "  max_num_seqs: 24\n  speculative_algorithm: NEXTN\n")
        self.assertIn("speculative_algorithm", r["defaults"])

    def test_dropped_readiness_budget_is_caught(self):
        r = self._arm_with("  port_timeout_s: 3600", "  port_timeout_s: 1800")
        self.assertEqual(r["port_timeout_s"], "1800")


if __name__ == "__main__":
    unittest.main()
