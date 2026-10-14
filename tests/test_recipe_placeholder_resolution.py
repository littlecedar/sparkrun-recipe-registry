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

Known blind spots (documented, not enforced): a `{placeholder}` nested inside a `defaults:` VALUE
that is consumed wholesale (e.g. a JSON blob under `speculative_config`) is not checked, and
PLACEHOLDER_RE is snake_case-only. No shipped recipe trips either today. The LiteralShaConsistency
class below additionally guards the literal snapshot-path pattern: in a recipe that hardcodes
`/cache/.../snapshots/<sha>` and/or `--revision=<sha>`, every 40-hex token in the command must equal
the top-level `model_revision`, so a revision bump cannot silently serve a stale snapshot.
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


class LiteralShaConsistency(unittest.TestCase):
    """In a recipe that hardcodes the snapshot-path pattern, every 40-hex token
    in the command must equal the top-level `model_revision` — otherwise a
    revision bump that edits one of the three places (top-level pin, snapshot
    path, --revision=) silently serves a stale snapshot or dies at
    distribution.
    """

    SHA_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])")

    def test_command_shas_match_model_revision(self):
        checked = 0
        for path in sorted(RECIPES_DIR.glob("*/*.yaml")):
            text = strip_comment_lines(path.read_text(encoding="utf-8"))
            pin = re.search(r"^model_revision:\s*([0-9a-f]{40})\s*$", text, re.M)
            if not pin:
                continue
            command = re.search(
                r"^command: *>(?:\n(.*?))?(?=^[a-z0-9_]+:|\Z)", text, re.M | re.S
            )
            self.assertIsNotNone(command, f"{path}: no folded command block")
            shas = set(self.SHA_RE.findall(command.group(1) or ""))
            unexpected = sorted(s for s in shas if s != pin.group(1))
            self.assertEqual(
                unexpected,
                [],
                f"{path.relative_to(REPO_ROOT)}: command carries a 40-hex token "
                f"that does not match model_revision {pin.group(1)}: {unexpected}",
            )
            checked += 1
        self.assertGreaterEqual(checked, 3, "expected the literal-path recipes")

    def test_mismatched_revision_fails(self):
        text = (
            "recipe_version: 2\n"
            "model: m/n\n"
            "model_revision: " + "a" * 40 + "\n"
            "command: >\n"
            "  vllm serve\n"
            "  /cache/huggingface/hub/models--m--n/snapshots/" + "b" * 40 + "\n"
            "  --revision=" + "c" * 40 + "\n"
        )
        command = re.search(
            r"^command: *>(?:\n(.*?))?(?=^[a-z0-9_]+:|\Z)",
            strip_comment_lines(text), re.M | re.S,
        )
        shas = set(self.SHA_RE.findall(command.group(1)))
        self.assertEqual(len(shas), 2, "control must produce two distinct SHAs")


class InertDefaults(unittest.TestCase):
    """A `defaults:` key the `command:` never references never reaches the
    engine — sparkrun's render only substitutes placeholders, so such a key is
    a silent drop (`-o key=` cannot reach it either). The session that found
    this shipped three: `moe_backend`, `tensor_parallel` and
    `num_speculative_tokens` all looked wired and were not, and one of them
    (`moe_backend`) was only caught by a subagent boot.
    Exceptions, with reasons: `extra_args` is a documented escape hatch whose
    wiring is per-recipe (two qwen4 arm recipes predate this guard and do not
    reference it); `mm_encoder_tp_mode` is read by the vLLM runtime's flag
    map for the ornith 397B arm rather than by its template; and
    `speculative_draft_model_revision` is read by the sglang runtime's draft
    *distribution* path (`runtimes/sglang.py::_detect_speculative_draft_revision`)
    rather than by a serve flag, so an arm may declare it purely to pin the
    snapshot sparkrun stages on a node.
    """

    ALLOWED_UNREFERENCED = {
        "extra_args",
        "mm_encoder_tp_mode",
        "speculative_draft_model_revision",
    }
    # host/port are conventionally referenced too, but a couple of recipes pass
    # them via other spellings; do not police them here.
    NOT_POLICED = {"host", "port"}

    def _blocks(self, text: str):
        defaults = re.search(r"^defaults:\n((?:  .*\n|\n)*)", text, re.M)
        command = re.search(r"^command: *>(?:\n(.*?))?(?=^[a-z0-9_]+:|\Z)", text, re.M | re.S)
        return defaults, command

    def test_every_default_reaches_the_command(self):
        checked = 0
        for path in sorted(RECIPES_DIR.glob("*/*.yaml")):
            text = strip_comment_lines(path.read_text(encoding="utf-8"))
            defaults, command = self._blocks(text)
            if not defaults or not command:
                continue
            keys = set(re.findall(r"^  ([a-z0-9_]+):", defaults.group(1), re.M))
            refs = set(PLACEHOLDER_RE.findall(command.group(1) or ""))
            inert = sorted(keys - refs - self.ALLOWED_UNREFERENCED - self.NOT_POLICED)
            self.assertEqual(
                inert, [],
                f"{path.relative_to(REPO_ROOT)}: defaults the command never "
                f"references (silent drop, -o cannot reach them): {inert}",
            )
            checked += 1
        self.assertGreater(checked, 15, "expected the full shipped set")

    def test_inert_default_fails(self):
        text = (
            "recipe_version: 2\n"
            "model: m/n\n"
            "defaults:\n"
            "  port: 8000\n"
            "  moe_backend: marlin\n"
            "command: >\n"
            "  serve --port {port}\n"
        )
        defaults, command = self._blocks(text)
        keys = set(re.findall(r"^  ([a-z0-9_]+):", defaults.group(1), re.M))
        refs = set(PLACEHOLDER_RE.findall(command.group(1) or ""))
        inert = sorted(keys - refs - self.ALLOWED_UNREFERENCED - self.NOT_POLICED)
        self.assertEqual(inert, ["moe_backend"])


class ServedModelNameNotRebound(unittest.TestCase):
    """`--served-model-name {model}` serves the prepared snapshot path on a launch.

    sparkrun rebinds every `{model}` occurrence to the prepared on-disk snapshot path
    (`models/runtime.py::bind_runtime_models`), so the engine advertises
    `/cache/huggingface/hub/models--<org>--<name>/snapshots/<sha>` as its model id, while `-n`
    still prints the repo id (bindings exist only on a launch). A `command:`-templated sglang
    recipe with no flag at all is the same defect with the flag omitted: SGLang falls back to
    the `--model-path` value. The supported spelling declares the literal and renders the flag
    from it — `defaults.served_model_name: <repo id>` plus
    `--served-model-name {served_model_name}` (sparkrun's own suggestion,
    `core/validation.py:339-343`).

    Exceptions, with reasons: the two ds4 shim arms render `{model}` on purpose — an
    in-container launcher normalizes the path back to the repo id before the engine starts
    (`mods/tensorfold-dsv41-launcher/launcher.py:176-196`,
    `recipes/ds4/mods/dsv41-sglang-overlay/launcher.py:391-395`), guarded by tests/test_ds4_recipes.py.
    """

    ALLOWED = {
        "ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml",
        "ds4/deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml",
    }
    REBOUND = re.compile(r"--served-model-name\s+\{model\}")

    def _rebound(self, text: str) -> bool:
        return bool(self.REBOUND.search(strip_comment_lines(text)))

    def test_no_recipe_renders_the_flag_from_model(self):
        offenders = []
        checked = 0
        for path in sorted(RECIPES_DIR.glob("*/*.yaml")):
            rel = path.relative_to(RECIPES_DIR).as_posix()
            checked += 1
            if rel in self.ALLOWED:
                continue
            if self._rebound(path.read_text(encoding="utf-8")):
                offenders.append(rel)
        self.assertEqual(
            offenders, [],
            f"recipes rendering --served-model-name from {{model}} (a launch serves the "
            f"prepared snapshot path as the model id): {offenders}",
        )
        self.assertGreater(checked, 15, "expected the full shipped set")

    def test_every_sglang_command_recipe_declares_a_served_name(self):
        missing = []
        for path in sorted(RECIPES_DIR.glob("*/*.yaml")):
            rel = path.relative_to(RECIPES_DIR).as_posix()
            if rel in self.ALLOWED:
                continue
            text = strip_comment_lines(path.read_text(encoding="utf-8"))
            is_sglang = bool(re.search(r"^runtime: sglang", text, re.M)) or (
                not re.search(r"^runtime:", text, re.M) and "sglang serve" in text
            )
            if not is_sglang or not re.search(r"^command: *>", text, re.M):
                continue  # command-less recipes auto-inject recipe.model
            if not re.search(r"^  served_model_name:", text, re.M):
                missing.append(rel)
        self.assertEqual(
            missing, [],
            f"sglang command recipes with no declared served_model_name (the engine then "
            f"advertises the --model-path value): {missing}",
        )

    def test_negative_controls(self):
        # the pre-fix spelling fires; the declared spelling does not.
        self.assertTrue(self._rebound("  --served-model-name {model}\n"))
        self.assertFalse(self._rebound("  --served-model-name {served_model_name}\n"))
        # prose quoting the old spelling in a comment must stay inert.
        self.assertFalse(self._rebound("  # was: --served-model-name {model}\n"))


if __name__ == "__main__":
    unittest.main()

