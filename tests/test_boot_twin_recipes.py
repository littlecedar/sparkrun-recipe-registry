"""Second-boot twins stay behaviour-identical to their originals.

A second boot of one recipe is a sigma cell, not a new arm, but the campaign's queue plan keys an
arm by its recipe basename and refuses two rows naming one recipe (`campaign/DESIGN.md` §Queue
mode). The register therefore names the second boot through a twin file. A twin that drifts is the
second copy this repository exists to prevent, so the guard is the comment-stripped text itself.

Run:
    uv run python -B -m unittest tests.test_boot_twin_recipes -v
"""

from __future__ import annotations

import unittest
from pathlib import Path

from tests.test_ornith_recipes import parse, parse_text

REPO_ROOT = Path(__file__).resolve().parent.parent

TWINS = (
    (
        "recipes/glm/glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang.yaml",
        "recipes/glm/glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang-boot2.yaml",
    ),
    (
        "recipes/explore/zz-beam-1.0-501b-a23b-nvfp4-tp4-vllm.yaml",
        "recipes/explore/zz-beam-1.0-501b-a23b-nvfp4-tp4-vllm-boot2.yaml",
    ),
)


class BootTwins(unittest.TestCase):
    def test_each_twin_is_a_comment_only_copy(self):
        """Same launch after comments are stripped; edits belong in the original."""
        for original, twin in TWINS:
            with self.subTest(twin=twin):
                source = parse(REPO_ROOT / original)
                copy = parse(REPO_ROOT / twin)
                self.assertEqual(copy["stripped"], source["stripped"],
                                 f"{twin} drifted from {original}; edit the original and re-copy")

    def test_a_changed_value_fails_the_guard(self):
        """Negative control: the guard compares content, not filenames."""
        original, twin = TWINS[0]
        source = parse(REPO_ROOT / original)
        text = (REPO_ROOT / twin).read_text(encoding="utf-8")
        mutated = text.replace("health_timeout_s: 3600", "health_timeout_s: 1800", 1)
        self.assertNotEqual(mutated, text, "the control could not find a value to change")
        self.assertNotEqual(parse_text(mutated)["stripped"], source["stripped"],
                            "a value change passed the twin guard")


if __name__ == "__main__":
    unittest.main()
