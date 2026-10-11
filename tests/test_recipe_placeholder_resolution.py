"""Guard: every {placeholder} in a shipped recipe's command must resolve.

Run:
    python3 -m unittest discover -s tests -v

Stdlib-only, deliberate. Recipes are parsed as text with the hand-rolled
subset parser (no PyYAML), per AGENTS.md.

Why this exists. 2026-10-11: an edit to
`recipes/ornith/ornith-1.5-35b-a3b-nvfp4-dflash2-sglang.yaml` accidentally
cut the adjacent `speculative_algorithm: DFLASH` default while removing a
comment. `sparkrun recipe validate` PASSED — it does not check that a
`{placeholder}` in `command:` has a corresponding default — and the recipe
pushed, so the next boot died at the engine with
`Unknown speculative algorithm name: {SPECULATIVE_ALGORITHM}`: the
unresolved literal flowed into the serve line verbatim. This guard closes
that gap: every placeholder in every shipped recipe's `command:` must come
from the recipe's `defaults`, a known top-level field, or the runtime's
injected set.

Negative controls live in NegativeControls: a command referencing a missing
default must FAIL, and comments must be stripped before matching so prose
that quotes a placeholder does not fire the guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPES_DIR = REPO_ROOT / "recipes"

# Placeholders sparkrun itself injects or that are documented escape hatches,
# not `defaults:` keys.
INJECTED = {
    "model",       # sparkrun rewrites to the prepared snapshot path
    "model_revision",  # sparkrun renders from the top-level pin / manifest
    "extra_args",  # documented escape hatch (qwen3 lane), appended last
}

PLACEHOLDER_RE = re.compile(r"\{([a-z0-9_]+)\}")


def strip_comment_lines(text: str) -> str:
    """Drop whole-line `#` comments so prose quoting a placeholder is inert."""
    return "\n".join(
        ln for ln in text.splitlines() if not ln.lstrip().startswith("#")
    )


def _defaults_keys(text: str) -> set[str]:
    """Top-level keys under the `defaults:` block, indentation-2 flat keys.

    The recipes use a flat `defaults:` mapping (no nesting), so any line
    matching `^  ([a-z0-9_]+):` inside the block is a key. The block ends at
    the next top-level key (`command:`, `env:`, ...).
    """
    keys: set[str] = set()
    in_defaults = False
    for ln in text.splitlines():
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        if re.match(r"^[a-z0-9_]+:", ln):
            in_defaults = ln.startswith("defaults:")
            continue
        if in_defaults:
            m = re.match(r"^  ([a-z0-9_]+):", ln)
            if m:
                keys.add(m.group(1))
    return keys


class PlaceholderResolution(unittest.TestCase):
    def test_every_placeholder_resolves_in_every_recipe(self):
        checked = 0
        for path in sorted(RECIPES_DIR.glob("*/*.yaml")):
            text = strip_comment_lines(path.read_text(encoding="utf-8"))
            command_match = re.search(r"^command: *>(?:\n(.*?))?(?=^[a-z0-9_]+:|\Z)", text, re.M | re.S)
            self.assertIsNotNone(command_match, f"{path}: no folded command block")
            command = command_match.group(1) or ""
            defaults = _defaults_keys(text)
            missing = sorted(
                {
                    tok
                    for tok in PLACEHOLDER_RE.findall(command)
                    if tok not in defaults and tok not in INJECTED
                }
            )
            self.assertEqual(
                missing,
                [],
                f"{path.relative_to(REPO_ROOT)}: command placeholders with no "
                f"defaults entry (boot would inject the literal): {missing}",
            )
            checked += 1
        self.assertGreater(checked, 15, "expected to check the full shipped set")


class NegativeControls(unittest.TestCase):
    def test_missing_default_fails(self):
        text = (
            "recipe_version: 2\n"
            "model: m/n\n"
            "defaults:\n"
            "  port: 8000\n"
            "command: >\n"
            "  serve --flag {not_a_default}\n"
        )
        command = re.search(r"^command: *>(?:\n(.*?))?(?=^[a-z0-9_]+:|\Z)", text, re.M | re.S)
        defaults = _defaults_keys(text)
        missing = [
            tok
            for tok in PLACEHOLDER_RE.findall(command.group(1))
            if tok not in defaults and tok not in INJECTED
        ]
        self.assertEqual(missing, ["not_a_default"])

    def test_commented_placeholder_is_ignored(self):
        text = (
            "recipe_version: 2\n"
            "model: m/n\n"
            "defaults:\n"
            "  port: 8000\n"
            "# the {ghost} placeholder is quoted in this comment only\n"
            "command: >\n"
            "  serve --port {port}\n"
        )
        stripped = strip_comment_lines(text)
        command = re.search(r"^command: *>(?:\n(.*?))?(?=^[a-z0-9_]+:|\Z)", stripped, re.M | re.S)
        defaults = _defaults_keys(stripped)
        missing = [
            tok
            for tok in PLACEHOLDER_RE.findall(command.group(1))
            if tok not in defaults and tok not in INJECTED
        ]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
