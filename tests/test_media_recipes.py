"""Guards for the media lane (`recipes/media/`, split out of Explore 2026-10-22).

Two things in this lane are silent when broken:

  M  `mods:` is resolved by sparkrun ADJACENT to the recipe, and
     `sparkrun recipe validate` does NOT resolve the entry (verified by
     `tests/test_k2_7b_recipes.py`). After the move, a mod kept here must be
     referenced UNSCOPED as `mods/<name>`: `@littlecedar/mods/<name>` resolves
     against the published registry clone, which has no lane dir, so the launch
     dies `Could not resolve mod`. Every reference is checked against the file
     tree, not against a hardcoded list.
  K  Kokoro-82M moved here from Decision with its identity rule intact: its
     model set is baked into the digest-pinned image, so the arm's identity is
     the image digest, and it declares `distribution_config.models.enabled:
     false` because a command that cannot name a staged snapshot would be
     rejected by the launch contract. No other lane's recipe may claim it.

No PyYAML: recipes are parsed as text by the lane guard's parser.

Run:
    uv run python -B -m unittest tests.test_media_recipes -v
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.test_ornith_recipes import parse_text

REPO_ROOT = Path(__file__).resolve().parent.parent
MEDIA = REPO_ROOT / "recipes" / "media"
KOKORO = MEDIA / "kokoro-82m-tts-cpu.yaml"
MODS_BLOCK = re.compile(r"(?m)^mods:\n((?:  - .*\n)+)")


def mod_entries(text: str) -> list[str]:
    block = MODS_BLOCK.search(text)
    if not block:
        return []
    return [m.strip().strip('"').strip("'")
            for m in re.findall(r"(?m)^  - (.+)$", block.group(1))]


def unresolved_mods(text: str, base: Path) -> list[str]:
    """Entries that do not resolve from the recipe's own directory."""
    bad = []
    for entry in mod_entries(text):
        if not entry.startswith("mods/"):
            bad.append(f"{entry} is not the unscoped mods/<name> form")
        elif not (base / entry / "run.sh").is_file():
            bad.append(f"{entry} has no run.sh beside the recipe")
    return bad


class ModsResolveAdjacent(unittest.TestCase):
    def test_every_lane_recipe_resolves_its_mods(self):
        recipes = sorted(MEDIA.glob("*.yaml"))
        self.assertTrue(recipes, "no recipes in recipes/media: the guard would pass vacuously")
        for path in recipes:
            with self.subTest(recipe=path.name):
                self.assertEqual(unresolved_mods(path.read_text(encoding="utf-8"), MEDIA), [])

    def test_every_lane_mod_is_referenced_unscoped_or_kept_on_purpose(self):
        referenced = set()
        for path in MEDIA.glob("*.yaml"):
            referenced.update(e.rsplit("/", 1)[-1]
                              for e in mod_entries(path.read_text(encoding="utf-8")))
        # qwen-image-sigmas is the prior 4-step server, kept with the arm it was
        # written for though no recipe lists it (README §Mods).
        self.assertEqual({p.name for p in (MEDIA / "mods").iterdir()},
                         referenced | {"qwen-image-sigmas"})

    def test_scoped_reference_is_caught(self):
        raw = (MEDIA / "qwen-image-2.1-turbo-7b-bf16-diffusers-script.yaml").read_text(
            encoding="utf-8")
        mutated = raw.replace('"mods/qwen-image-2.1-turbo-launcher"',
                              '"@littlecedar/mods/qwen-image-2.1-turbo-launcher"')
        self.assertNotEqual(mutated, raw)
        self.assertTrue(any("unscoped" in v for v in unresolved_mods(mutated, MEDIA)))

    def test_missing_mod_directory_is_caught(self):
        raw = (MEDIA / "qwen-image-2.1-turbo-7b-bf16-diffusers-script.yaml").read_text(
            encoding="utf-8")
        mutated = raw.replace("mods/qwen-image-2.1-turbo-launcher",
                              "mods/qwen-image-2.1-turbo-launcher-typo")
        self.assertTrue(any("run.sh" in v for v in unresolved_mods(mutated, MEDIA)))


class KokoroIdentity(unittest.TestCase):
    def test_lane_holds_kokoro(self):
        self.assertTrue(KOKORO.is_file())

    def test_identity_is_the_baked_image(self):
        r = parse_text(KOKORO.read_text(encoding="utf-8"))
        self.assertNotIn("{model}", r["command"])
        self.assertIn("/kokoro-fastapi-cpu@sha256:", r["top"]["container"])

    def test_declares_no_model_to_distribute(self):
        # The exemption from the launch contract is the declaration, not silence.
        r = parse_text(KOKORO.read_text(encoding="utf-8"))
        self.assertRegex(r["stripped"],
                         r"(?m)^distribution_config:\n  models:\n    enabled: false$")

    def test_no_other_lane_recipe_claims_it(self):
        for path in REPO_ROOT.glob("recipes/*/*.yaml"):
            if path.parent == MEDIA:
                continue
            with self.subTest(recipe=path.name):
                self.assertNotIn("kokoro", path.read_text(encoding="utf-8").lower())


if __name__ == "__main__":
    unittest.main()
