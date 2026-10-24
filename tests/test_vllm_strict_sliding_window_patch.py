"""Guards for the Laguna-M.1 vLLM sliding-window patch (explore lane).

Run:
    python3 -m unittest tests.test_vllm_strict_sliding_window_patch -v

Stdlib-only, like the rest of tests/ (AGENTS.md).

What this guards
----------------
`recipes/explore/mods/fix-vllm-strict-sliding-window/run.sh` patches the pinned
vLLM v0.32.0 image in-container: the checkpoint poolside/Laguna-M.1-NVFP4
declares `sliding_window: 0`, vLLM's `ModelConfig.__post_init__` converts that
to None by plain assignment, and the transformers strict-dataclass setattr
rejects None for the plain-`int` field — the engine dies before serving one
request (observed 2026-10-24, receipt
`~/benchmarks/tp2-queue-20261024/LAGUNA-M1-REBOOT-FAILED.md`).

The mod makes a fail-closed claim, and these tests pin the pieces that claim
stands on: the needle and replacement are quoted exactly (so a reworded mod
cannot silently drift from the engine source), every abort path exits
non-zero, the patch is idempotent, and the recipe actually references the mod.
The needle/replacement values themselves are also asserted against the real
upstream v0.32.0 text shape here as literals — the test file carries the
expected line so a future editor sees both sides of the contract in one place.
"""

from __future__ import annotations

import pathlib
import re
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
MOD = REPO / "recipes/explore/mods/fix-vllm-strict-sliding-window/run.sh"
RECIPE = REPO / "recipes/explore/poolside-laguna-m1-nvfp4-vllm-tp2.yaml"

# The exact source line the pinned v0.32.0 `vllm/config/model.py` carries at
# :808 (the 0 -> None conversion) and :904 (the --disable-sliding-window path).
NEEDLE = "self.hf_text_config.sliding_window = None"
# The bypass: object.__setattr__ calls the base implementation directly and so
# skips only the strict-validation override, preserving vLLM's semantics.
REPLACEMENT = 'object.__setattr__(self.hf_text_config, "sliding_window", None)'


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


class TestModContract(unittest.TestCase):
    def setUp(self) -> None:
        self.script = read(MOD)

    def test_needle_and_replacement_quoted_exactly(self) -> None:
        self.assertIn(NEEDLE, self.script)
        self.assertIn(REPLACEMENT, self.script)

    def test_fail_closed_when_needle_missing(self) -> None:
        # The count check must abort (exit 1), not warn, when the needle is
        # absent — a re-pinned image must fail loudly.
        m = re.search(
            r"if \[ \"\$COUNT\" -lt 1 \]; then\n(.*?)\nfi", self.script, re.DOTALL
        )
        self.assertIsNotNone(m, "needle-count abort block not found")
        self.assertIn("exit 1", m.group(1))

    def test_fail_closed_on_remaining_needle(self) -> None:
        # Post-patch verification: a plain needle left behind aborts.
        m = re.search(
            r'if grep -qF -- "\$NEEDLE" "\$TARGET"; then\n(.*?)\nfi',
            self.script,
            re.DOTALL,
        )
        self.assertIsNotNone(m, "post-patch verification block not found")
        self.assertIn("exit 1", m.group(1))

    def test_patch_is_idempotent(self) -> None:
        self.assertIn("already patched", self.script)
        self.assertIn("exit 0", self.script)

    def test_every_abort_path_is_nonzero(self) -> None:
        # Every FATAL line is followed by (or is on a line ending with) exit 1.
        fatal_lines = [
            line
            for line in self.script.splitlines()
            if "FATAL" in line and "echo" in line
        ]
        self.assertTrue(fatal_lines, "expected fail-closed FATAL aborts")
        for line in fatal_lines:
            idx = self.script.splitlines().index(line)
            tail = "\n".join(self.script.splitlines()[idx : idx + 2])
            self.assertIn("exit 1", tail, f"FATAL without exit 1: {line.strip()}")

    def test_patch_targets_vllm_config_model_py(self) -> None:
        self.assertIn(
            "/usr/local/lib/python3.12/dist-packages/vllm/config/model.py",
            self.script,
        )


class TestRecipeWiring(unittest.TestCase):
    def test_recipe_references_the_mod(self) -> None:
        self.assertIn("mods/fix-vllm-strict-sliding-window", read(RECIPE))

    def test_recipe_pins_v0320_image(self) -> None:
        # The patch is version-specific: it must only ship beside the pin it
        # was written against.
        self.assertRegex(read(RECIPE), r"vllm/vllm-openai:v0\.32\.0@")


if __name__ == "__main__":
    unittest.main()
