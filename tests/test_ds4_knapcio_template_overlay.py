# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Guard: the knapcio launcher's template overlay serves what SGLang reads.

The 1017 refresh ships no ``chat_template.jinja``, so ``ensure_template_overlay``
must turn a template-less checkpoint into a servable model dir: a symlink farm of
every checkpoint entry plus **one real file**, this mod's patched template. Three
properties are load-bearing and each has a negative control here:

1. the farm links the checkpoint, so nothing is copied and the 475 GB snapshot is
   never written through (a real copy or a write into the snapshot would pass a
   weaker "a template exists" assertion);
2. a checkpoint that already carries a template is served untouched -- the V4.1
   arm must not silently acquire a farm;
3. the farm is rebuilt from content, so a foreign link left by another checkpoint
   is dropped before boot (a mixed tree boots and renders the wrong format).

The mod is loaded by path: sparkrun ships the mod directory, so the launcher is
not an importable package member.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MOD_DIR = REPO / "recipes" / "ds4" / "mods" / "dsv41-sglang-overlay"
LAUNCHER = MOD_DIR / "launcher.py"
TEMPLATE = MOD_DIR / "chat_template.jinja"


def load_launcher():
    """Import the launcher module by path, registered before exec_module."""
    name = "dsv41_sglang_overlay_launcher"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, LAUNCHER)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {LAUNCHER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class TemplateOverlay(unittest.TestCase):
    def setUp(self):
        self.module = load_launcher()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.cache = self.root / "cache"
        self.cache.mkdir()
        self.checkpoint = self.root / "snapshots" / "abc123"
        (self.checkpoint / "sub").mkdir(parents=True)
        # The files _is_checkpoint_dir and the engine need, plus a shard.
        for name in ("config.json", "model.safetensors.index.json"):
            (self.checkpoint / name).write_text("{}", encoding="utf-8")
        (self.checkpoint / "model-00001-of-00048.safetensors").write_bytes(b"w" * 2048)
        (self.checkpoint / "sub" / "extra.json").write_text("{}", encoding="utf-8")
        # The launcher resolves both from module constants; redirect them.
        self._saved = (self.module._CACHE, self.module.OVERLAY_DIR)
        self.module._CACHE = str(self.cache)
        self.module.OVERLAY_DIR = str(self.cache / "model-overlay")

    def tearDown(self):
        self.module._CACHE, self.module.OVERLAY_DIR = self._saved
        self._tmp.cleanup()

    def overlay(self) -> Path:
        return Path(self.module.OVERLAY_DIR)

    def test_template_less_checkpoint_is_served_from_a_farm(self):
        env = {"MODEL_ID": str(self.checkpoint)}
        self.module.ensure_template_overlay(env, str(self.checkpoint))

        self.assertEqual(env["MODEL_PATH"], str(self.overlay()))
        self.assertEqual(env["DSV41_SOURCE"], str(self.overlay()))

        for name in ("config.json", "model.safetensors.index.json",
                     "model-00001-of-00048.safetensors", "sub"):
            link = self.overlay() / name
            self.assertTrue(link.is_symlink(), f"{name} is not a symlink")
            self.assertEqual(os.readlink(link), str(self.checkpoint / name))

        rendered = self.overlay() / "chat_template.jinja"
        self.assertTrue(rendered.is_file())
        self.assertFalse(rendered.is_symlink(), "the template must be a real file")
        self.assertEqual(rendered.read_bytes(), TEMPLATE.read_bytes(),
                         "the served template is not the mod's patched copy")

    def test_checkpoint_snapshot_is_never_written(self):
        before = {path.name for path in self.checkpoint.iterdir()}
        self.module.ensure_template_overlay({}, str(self.checkpoint))
        after = {path.name for path in self.checkpoint.iterdir()}
        self.assertEqual(before, after, "the HF snapshot gained an entry")
        self.assertFalse((self.checkpoint / "chat_template.jinja").exists(),
                         "the snapshot was written through")

    def test_a_checkpoint_with_its_own_template_is_left_alone(self):
        (self.checkpoint / "chat_template.jinja").write_text("{{ mine }}", encoding="utf-8")
        env = {"MODEL_PATH": str(self.checkpoint), "DSV41_SOURCE": str(self.checkpoint)}
        self.module.ensure_template_overlay(env, str(self.checkpoint))
        self.assertEqual(env["MODEL_PATH"], str(self.checkpoint))
        self.assertEqual(env["DSV41_SOURCE"], str(self.checkpoint))
        self.assertFalse(self.overlay().exists(),
                         "a checkpoint with a template must not acquire a farm")

    def test_rebuild_is_idempotent_and_drops_foreign_links(self):
        self.module.ensure_template_overlay({}, str(self.checkpoint))
        self.overlay().joinpath("leftover-from-another-checkpoint").symlink_to(
            self.root / "elsewhere")
        env = {}
        self.module.ensure_template_overlay(env, str(self.checkpoint))

        self.assertFalse((self.overlay() / "leftover-from-another-checkpoint").is_symlink(),
                         "a stale link survived the rebuild")
        self.assertEqual(
            sorted(path.name for path in self.overlay().iterdir()),
            sorted({path.name for path in self.checkpoint.iterdir()} | {"chat_template.jinja"}),
        )

    def test_missing_mod_template_fails_closed(self):

        saved = TEMPLATE.read_bytes()
        try:
            TEMPLATE.unlink()
            with self.assertRaises(SystemExit):
                self.module.ensure_template_overlay({}, str(self.checkpoint))
        finally:
            TEMPLATE.write_bytes(saved)

    def test_the_shipped_template_is_a_real_copy(self):
        # If the mod's template were a symlink to the checkpoint, the farm would
        # 'serve' whatever the snapshot has -- i.e. nothing.
        self.assertFalse(TEMPLATE.is_symlink())
        self.assertGreater(TEMPLATE.stat().st_size, 4096)


if __name__ == "__main__":
    unittest.main()
