"""Guards for the `cybersec` lane's abliterated/uncensored arms.

The lane ships five arms over seven recipe files: arms 3 and 4 carry both their SGLang negative and
the card-documented vLLM route for the same checkpoint at the same pinned revision.

These are red-team checkpoints: refusal-trained behaviour has been removed on purpose, so
the properties worth pinning are not quality ones -- they are *identity* ones. Each arm
serves exactly one checkpoint at one pinned revision, and a client (or the gateway, or a
benchmark) must see that checkpoint's repo id, not a cache path. This module asserts the
lane-level invariants that a copy/paste of a sibling recipe breaks:

* every arm pins `model_revision:` at top level **and** passes `--revision
  {model_revision}` to the engine (a pin no flag consumes is dead -- sparkrun downloads a
  commit SHA, writes no `refs/main`, and the engine then resolves its default revision and
  dies with `LocalEntryNotFoundError`);
* `--served-model-name` is never rendered from `{model}` (sparkrun rebinds `{model}` to the
  prepared on-disk snapshot, so the served id would be a `/cache/huggingface/hub/...`
  path), and the literal served value is the arm's repo id;
* no repo id is spelled into `command:` (sparkrun renders `{model}`; a literal would ship a
  path or bypass the pin);
* the two overlay arms actually consume what their new mods stage (`{chat_template_path}`,
  `{served_model_dir}`), so a mod cannot be listed and then unused;
* each new mod is a fail-closed bash script with the repo's mod harness contract.

Recipes are parsed as text (stdlib only, no PyYAML); whole-line comments are stripped
before matching so recipe prose quoting a forbidden flag is inert.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LANE = REPO_ROOT / "recipes" / "cybersec"
ATTIC = REPO_ROOT / "attic" / "cybersec"
MODS = LANE / "mods"

# arm -> (the repo the recipe serves weights from, the repo id clients must see)
ARMS: dict[str, tuple[str, str]] = {
    "qwen3.8-27b-uncensored-nvfp4-sglang.yaml": (
        "orcarouter/Qwen3.8-27B-Uncensored-NVFP4",
        "orcarouter/Qwen3.8-27B-Uncensored-NVFP4",
    ),
    # Overlay: the body is the AEON-7 pack, the arm holds the cyber-unlock chat template.
    "qwen3.8-27b-ablit-cyber-unlock-nvfp4-dflash2-sglang.yaml": (
        "sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4",
        "sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4",
    ),
    "nex-n2.5-mini-uncensored-nvfp4-sglang.yaml": (
        "orcarouter/Nex-N2.5-mini-Uncensored-NVFP4",
        "orcarouter/Nex-N2.5-mini-Uncensored-NVFP4",
    ),
    # The card-documented vLLM routes for the same two checkpoints. Same identity
    # invariants as the SGLang arms: one checkpoint, one pinned revision, repo-id served name.
    "nex-n2.5-mini-uncensored-nvfp4-vllm.yaml": (
        "orcarouter/Nex-N2.5-mini-Uncensored-NVFP4",
        "orcarouter/Nex-N2.5-mini-Uncensored-NVFP4",
    ),
    "qwen3.8-flash-next-uncensored-nvfp4-sglang.yaml": (
        "orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4",
        "orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4",
    ),
    "qwen3.8-flash-next-uncensored-nvfp4-vllm.yaml": (
        "orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4",
        "orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4",
    ),
    # Graft overlay: the combined stock pack on disk (weights + Engram tables), the abliterated
    # arm is what the engine advertises.
    "deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang.yaml": (
        "littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram",
        "drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed",
    ),
}

# arm -> extra mod it must list (the lane's two new mods). Bare `mods/<dir>` is the
# lane-local form: it resolves adjacent to the recipe (`recipes/cybersec/mods/<dir>`),
# so an in-tree mod works before a push and for a registry consumer alike.
REQUIRED_MODS = {
    "qwen3.8-27b-ablit-cyber-unlock-nvfp4-dflash2-sglang.yaml": (
        "mods/provide-uncensored-chat-template"
    ),
    "deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang.yaml": (
        "mods/graft-dsv41-ablit-wo-b"
    ),
}

NEW_MODS = ("provide-uncensored-chat-template", "graft-dsv41-ablit-wo-b")

_COMMENT_LINE = re.compile(r"(?m)^\s*#.*$")
_TOP = "^%s: *(.+)$"


def strip_comment_lines(text: str) -> str:
    """Drop whole-line `#` comments so prose quoting a flag is inert."""
    return _COMMENT_LINE.sub("", text)


def top_level(text: str, key: str) -> str | None:
    match = re.search(_TOP % re.escape(key), text, re.M)
    return match.group(1).strip() if match else None


def defaults_block(text: str) -> str:
    match = re.search(r"^defaults:\n((?:  .*\n|\n)*)", text, re.M)
    return match.group(1) if match else ""


def defaults_keys(text: str) -> dict[str, str]:
    return dict(re.findall(r"^  ([a-z0-9_]+): *(.+)$", defaults_block(text), re.M))


def command_block(text: str) -> str:
    match = re.search(r"^command: *>(?:\n(.*?))?(?=^[a-z0-9_]+:|\Z)", text, re.M | re.S)
    return (match.group(1) or "") if match else ""


def read(path: Path) -> str:
    """Read a recipe, stripped of comments. A missing file raises -- never ''."""
    return strip_comment_lines(path.read_text(encoding="utf-8"))


class LaneShape(unittest.TestCase):
    def test_every_recipe_file_exists(self) -> None:
        for name in ARMS:
            self.assertTrue((LANE / name).is_file(), f"missing arm {name}")

    def test_lane_docs_exist(self) -> None:
        self.assertTrue((LANE / "README.md").is_file(), "missing lane doc README.md")
        self.assertTrue((ATTIC / "AGENTS.md").is_file(), "missing attic lane guide AGENTS.md")

    def test_every_arm_parses_to_a_command(self) -> None:
        for name in ARMS:
            text = read(LANE / name)
            self.assertTrue(command_block(text).strip(), f"{name}: empty command block")
# arm5 serves a mod-built graft tree, not the HF snapshot: its launcher takes `--model <dir>`,
# so a `--revision` flag would have no receiver. Its pin still selects which stock revision the
# node's cache holds (sparkrun downloads by SHA) and the graft mod's resolver reads that
# snapshot -- the pin is live there too, just enforced by the mod. The command still has to
# carry sparkrun's identity token (the prepared path, via `{model}`) or
# `validate_runtime_command` refuses the launch; the serve wrapper consumes it.
GRAFT_ARM = "deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang.yaml"


class PinnedRevision(unittest.TestCase):
    """A `model_revision:` no flag consumes is a dead pin (sparkrun's own lint says so)."""

    def test_pin_is_a_full_sha(self) -> None:
        for name in ARMS:
            pin = top_level(read(LANE / name), "model_revision")
            self.assertIsNotNone(pin, f"{name}: model_revision not pinned at top level")
            self.assertRegex(pin or "", r"^[0-9a-f]{40}$", f"{name}: revision is not a 40-hex SHA")

    def test_pin_and_flag_agree(self) -> None:
        for name in ARMS:
            command = command_block(read(LANE / name))
            if name == GRAFT_ARM:
                # Serves the graft tree; `{model}` appears only as the identity token sparkrun's
                # validator looks for, and never as the served id.
                self.assertIn("--model {served_model_dir}", command, name)
                self.assertIn("--stock-model {model}", command, name)
                self.assertNotIn("--served-model-name {model}", command, name)
                continue
            self.assertIn(
                "--revision {model_revision}",
                command,
                f"{name}: pin is never passed to the engine",
            )


class ServedIdentity(unittest.TestCase):
    """`GET /v1/models` must answer with the repo id, never a cache path."""

    def test_served_name_is_the_repo_id(self) -> None:
        for name, (_model, served) in ARMS.items():
            keys = defaults_keys(read(LANE / name))
            self.assertEqual(keys.get("served_model_name"), served, f"{name}: served id drift")

    def test_served_name_flag_uses_the_default(self) -> None:
        for name in ARMS:
            command = command_block(read(LANE / name))
            self.assertIn("--served-model-name {served_model_name}", command, name)

    def test_no_path_shaped_served_name(self) -> None:
        for name in ARMS:
            command = command_block(read(LANE / name))
            self.assertNotIn("--served-model-name {model}", command, f"{name}: path-shaped served id")

    def test_command_never_spells_a_repo_id(self) -> None:
        for name in ARMS:
            command = command_block(read(LANE / name))
            for repo in ("orcarouter/", "sakamakismile/", "Mia-AiLab/", "drowzeys/", "incoai/"):
                self.assertNotIn(repo, command, f"{name}: literal {repo} in command")


class OverlayWiring(unittest.TestCase):
    """Each overlay mod must be listed AND consumed, or it is dead weight."""

    def test_overlay_arms_list_their_mod(self) -> None:
        for name, mod in REQUIRED_MODS.items():
            text = read(LANE / name)
            mods = re.search(r"^mods:\n((?:  - .*\n)+)", text, re.M)
            self.assertIsNotNone(mods, f"{name}: no mods block")
            self.assertIn(mod, (mods.group(1) if mods else ""), f"{name}: {mod} not listed")

    def test_unsensored_template_path_is_consumed(self) -> None:
        name = "qwen3.8-27b-ablit-cyber-unlock-nvfp4-dflash2-sglang.yaml"
        keys = defaults_keys(read(LANE / name))
        self.assertIn("chat_template_path", keys)
        self.assertIn("--chat-template {chat_template_path}", command_block(read(LANE / name)))

    def test_graft_output_dir_is_consumed(self) -> None:
        name = "deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang.yaml"
        keys = defaults_keys(read(LANE / name))
        self.assertEqual(keys.get("served_model_dir"), "/cache/runtime/dsv41-ablit")
        self.assertIn("--model {served_model_dir}", command_block(read(LANE / name)))

    def test_graft_arm_adds_no_second_engram_copy(self) -> None:
        """The dedup contract: one pack per node serves both TP=2 arms.

        The graft resolves its stock pack from the HF cache, so a weights-only stock would
        reintroduce the second ~189 GiB Engram build on every node; the arm must list the
        combined repo and must not mount `dsv41-engram-fetch`.
        """
        text = read(LANE / GRAFT_ARM)
        mods = re.search(r"^mods:\n((?:  - .*\n)+)", text, re.M)
        self.assertIsNotNone(mods)
        block = mods.group(1) if mods else ""
        self.assertIn("mods/graft-dsv41-ablit-wo-b", block)
        self.assertNotIn("dsv41-engram-fetch", block)
        self.assertEqual(top_level(text, "model"),
                         "littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram")
        # The launcher reads the tables from the stock pack; with no flag it would fall back to
        # the per-lane pre-warm dir that this arm no longer builds.
        self.assertIn("--stock-model {model}", command_block(text))


class NewMods(unittest.TestCase):
    def test_each_new_mod_is_fail_closed_bash(self) -> None:
        for mod in NEW_MODS:
            script = (MODS / mod / "run.sh").read_text(encoding="utf-8")
            self.assertIn("set -euo pipefail", script, mod)
            self.assertIn("SPDX-License-Identifier: AGPL-3.0-or-later", script, mod)
            self.assertIn(f'MOD_NAME="{mod}"', script, f"{mod}: MOD_NAME must match its directory")
            self.assertIn("die()", script, f"{mod}: no fail-closed helper")
            self.assertTrue((MODS / mod / "README.md").is_file(), f"{mod}: missing README")

    def test_graft_mod_never_writes_the_stock_pack(self) -> None:
        script = (MODS / "graft-dsv41-ablit-wo-b" / "run.sh").read_text(encoding="utf-8")
        # The stock dir is the graft's --src, and the mod refuses src == dst outright.
        self.assertIn('--src "${STOCK}"', script)
        self.assertIn('--dst "${OUTDIR}"', script)
        self.assertRegex(script, r"OUTDIR equals the stock snapshot")
        # Fail closed: an unverified graft must abort the launch, not serve the stock pack.
        self.assertIn("EXPECTED_N_EDITED", script)
        self.assertRegex(script, r"n_edited=\{n\}")


class NegativeControls(unittest.TestCase):
    """Every guard above must fail on the mutation it exists for."""

    def test_control_path_shaped_served_name_is_caught(self) -> None:
        mutated = "--model-path {model}\n--served-model-name {model}\n"
        self.assertIn("--served-model-name {model}", strip_comment_lines(mutated))

    def test_control_comment_quoting_the_flag_is_inert(self) -> None:
        text = "# Never {model}: on a real launch sparkrun rebinds it.\n--model-path {model}\n"
        self.assertNotIn("--served-model-name {model}", strip_comment_lines(text))

    def test_control_missing_revision_flag_is_caught(self) -> None:
        text = "model_revision: " + "a" * 40 + "\ncommand: >\n  sglang serve --model-path {model}\n"
        self.assertNotIn("--revision {model_revision}", command_block(text))

    def test_control_missing_file_raises_not_empty(self) -> None:
        with self.assertRaises(FileNotFoundError):
            read(LANE / "does-not-exist.yaml")

    def test_control_mod_without_fail_closed_helper_is_caught(self) -> None:
        script = f'MOD_NAME="{NEW_MODS[0]}"\nset -euo pipefail\n'
        self.assertNotIn("die()", script)

    def test_control_literal_repo_id_in_command_is_caught(self) -> None:
        text = "command: >\n  vllm serve orcarouter/Qwen3.8-27B-Uncensored-NVFP4\n"
        self.assertIn("orcarouter/", command_block(text))

    def test_control_stock_snapshot_as_served_arm_is_caught(self) -> None:
        # The graft arm may name the stock only via --stock-model; a command that loads it
        # (or advertises it) would be a different arm than its name claims.
        text = "command: >\n  launcher.py --model {model} --served-model-name {model}\n"
        self.assertIn("{model}", command_block(text))
        self.assertNotIn("--stock-model {model}", command_block(text))
        self.assertNotIn("--model {served_model_dir}", command_block(text))



if __name__ == "__main__":
    unittest.main()
