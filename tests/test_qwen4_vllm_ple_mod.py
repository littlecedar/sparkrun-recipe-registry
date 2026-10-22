"""Guards for the house `fix-qwen3.8-flash-next-vllm` mod and its two consumers.

Run:
    python3 -B -m unittest discover -s tests -v

Why these exist. The mod was deleted on 2026-10-11 on the assumption that the eugr registry carried
the same patch; by 2026-10-22 the mirror (`spark-arena/eugr-recipes@0bdc9c9`, 26 mods) did not, and
the W12 arm died at `Could not resolve mod` before it could launch. Two things must therefore hold,
and both are testable without the vLLM image:

  * `apply()` inserts the PLE_FORCE_FP8 early return above its anchor and is idempotent; a missing
    anchor raises instead of writing a half-patched module (the image's line numbers move).
  * every arm that mounts the mod names a path that RESOLVES from that arm's own directory — sparkrun
    joins a `mods:` entry onto the recipe's directory, not the repo root, which is the silent half of
    the same failure.

Negative controls mutate strings in memory and touch nothing on disk.
"""

from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MOD_DIR = REPO_ROOT / "attic" / "qwen4" / "mods" / "fix-qwen3.8-flash-next-vllm"
# One copy per lane: the attic arm resolves `../mods`, the shipped-tree probe resolves its own
# `mods/`. Duplication is the repo's lane-locality rule, so parity is asserted instead of assumed.
MOD_DIR_LANE = REPO_ROOT / "recipes" / "qwen4" / "mods" / "fix-qwen3.8-flash-next-vllm"
MOD_NAME = "fix-qwen3.8-flash-next-vllm"
ARMS = (
    REPO_ROOT / "attic" / "qwen4" / "arms" / "qwen3.8-flash-next-nvfp4-vllm.yaml",
    REPO_ROOT / "recipes" / "qwen4" / "zz-qwen38-next-vllm-tp2-pinned.yaml",
)
NEEDLE = "if not isinstance(quant_config, Fp8Config):"

_COMMENT_LINE = re.compile(r"(?m)^\s*#.*$")


def load_mod():
    spec = importlib.util.spec_from_file_location("apply_ple_patch", MOD_DIR / "apply-ple-patch.py")
    assert spec and spec.loader, "apply-ple-patch.py is not importable"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mod_entries(text: str) -> list[str]:
    clean = _COMMENT_LINE.sub("", text)
    match = re.search(r"^mods:\n((?:  - .*\n|\n)*)", clean, re.MULTILINE)
    if not match:
        return []
    return re.findall(r'^  - "?([^"\n]+)"?$', match.group(1), re.MULTILINE)

class PatchBehaviour(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_installs_the_branch_above_its_anchor(self):
        rebuilt = (
            "def get_embedding_method(quant_config):\n"
            f"    {NEEDLE}\n"
            "        return Qwen3_8FlashNextPLEFp8EmbeddingMethod()\n"
        )
        lines = self.mod.apply(rebuilt).splitlines()
        anchor = lines.index(f"    {NEEDLE}")
        self.assertEqual(lines[anchor - 3], "    import os")
        self.assertEqual(lines[anchor - 2], '    if os.environ.get("VLLM_PLE_FP8_CHECKPOINT") == "1":')
        self.assertEqual(lines[anchor - 1], "        return Qwen3_8FlashNextPLEFp8EmbeddingMethod()")

    def test_is_idempotent(self):
        rebuilt = f"def f():\n    {NEEDLE}\n"
        once = self.mod.apply(rebuilt)
        self.assertEqual(self.mod.apply(once), once)

    def test_missing_anchor_raises(self):
        with self.assertRaises(SystemExit):
            self.mod.apply("def f():\n    return None\n")

    def test_the_env_gate_the_patch_reads_is_the_env_the_arms_set(self):
        for arm in ARMS:
            self.assertIn("VLLM_PLE_FP8_CHECKPOINT: 1", arm.read_text(encoding="utf-8"), arm.name)


class ConsumersResolveTheMod(unittest.TestCase):
    def test_mod_ships_with_its_readme(self):
        for directory in (MOD_DIR, MOD_DIR_LANE):
            for name in ("run.sh", "apply-ple-patch.py", "README.md"):
                self.assertTrue((directory / name).is_file(), f"{directory}/{name}")

    def test_the_two_lane_copies_are_byte_identical(self):
        for name in ("run.sh", "apply-ple-patch.py", "README.md"):
            self.assertEqual(
                (MOD_DIR / name).read_bytes(), (MOD_DIR_LANE / name).read_bytes(),
                f"the lane copies of {name} have drifted",
            )
    def test_no_arm_asks_the_registry_for_it(self):
        for arm in ARMS:
            self.assertNotIn(f"@eugr/mods/{MOD_NAME}", arm.read_text(encoding="utf-8"), arm.name)

    def test_every_mount_resolves_from_the_arms_own_directory(self):
        for arm in ARMS:
            entries = [e for e in mod_entries(arm.read_text(encoding="utf-8")) if e.startswith((".", "mods/"))]
            self.assertIn(MOD_NAME, [e.rsplit("/", 1)[-1] for e in entries], arm.name)
            for entry in entries:
                self.assertTrue(
                    (arm.parent / entry).resolve().is_dir(),
                    f"{arm.name}: {entry} does not resolve from the recipe directory",
                )


class NegativeControls(unittest.TestCase):
    def test_bare_mods_ref_does_not_resolve_from_the_arms_dir(self):
        # sparkrun joins `mods:` onto the RECIPE's directory, so from arms/ a bare `mods/<name>`
        # looks in arms/mods/ (absent) while `../mods/<name>` finds the attic lane's copy.
        arm = ARMS[0]
        self.assertFalse((arm.parent / f"mods/{MOD_NAME}").is_dir())
        self.assertTrue((arm.parent / f"../mods/{MOD_NAME}").is_dir())

    def test_shipped_probe_resolves_its_own_lane_copy(self):
        arm = ARMS[1]
        self.assertTrue((arm.parent / f"mods/{MOD_NAME}").is_dir())

    def test_registry_reference_is_detected(self):
        text = ARMS[1].read_text(encoding="utf-8").replace(
            f'"mods/{MOD_NAME}"', f'"@eugr/mods/{MOD_NAME}"'
        )
        self.assertIn(f"@eugr/mods/{MOD_NAME}", text)

    def test_removed_mount_is_detected(self):
        text = ARMS[1].read_text(encoding="utf-8").replace(f'  - "mods/{MOD_NAME}"\n', "")
        names = [e.rsplit("/", 1)[-1] for e in mod_entries(text)]
        self.assertNotIn(MOD_NAME, names)



if __name__ == "__main__":
    unittest.main()
