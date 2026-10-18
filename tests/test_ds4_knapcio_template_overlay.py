# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Guard: the knapcio launcher's template overlay serves what SGLang reads.

The 1017 refresh ships no ``chat_template.jinja``, and this SGLang resolves the
template from ``<model_dir>/chat_template.jinja`` when the tokenizer carries no
embedded one (image ``srt/utils/hf_transformers/processor.py:383-390``; boot.py
exposes no template flag). So ``ensure_template_overlay`` must turn a
template-less checkpoint into a servable model dir: a symlink farm of every
checkpoint entry plus **one real file**, the mod's patched template. Each
property below has a negative control, because a weaker assertion passes on a
tree that would boot into the wrong contract:

1. the farm links the checkpoint, so nothing is copied and the 475 GB snapshot is
   never written through (a real copy, or a write into the snapshot, passes a bare
   "a template exists" check);
2. a checkpoint that already carries a template is served untouched -- the V4.1
   arm must not silently acquire a farm;
3. the farm is rebuilt from content, so a foreign link left by another checkpoint
   is dropped before boot (a mixed tree boots and renders the wrong format);
4. an unstaged or unstageable template fails closed (exit 2) instead of serving a
   templateless endpoint -- the 400 that motivated the whole step;
5. the mod's copy still matches the TensorFold lane's, whose sha256 (297be886…)
   the receipts cite; the two copies drift only by someone's hand.

The mod is loaded by path: sparkrun ships the mod directory, so the launcher is
not an importable package member.
"""

from __future__ import annotations

import hashlib
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
TF_TEMPLATE = REPO / "mods" / "tensorfold-dsv41-launcher" / "chat_template.jinja"
TEMPLATE_SHA256 = "297be8861c9c679686335cad993c4beeffc60c024865e37bae1a4c4e0bd1d9d3"


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
        self.checkpoint = self.root / "snapshots" / "1bae0e10"
        (self.checkpoint / "sub").mkdir(parents=True)
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

    def run_overlay(self, **kwargs) -> dict:
        env: dict = {}
        self.module.ensure_template_overlay(env, str(self.checkpoint), **kwargs)
        return env

    def test_template_less_checkpoint_is_served_from_a_farm(self):
        env = self.run_overlay()

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
        self.run_overlay()
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
        self.run_overlay()
        self.overlay().joinpath("leftover-from-another-checkpoint").symlink_to(
            self.root / "elsewhere")
        env = self.run_overlay()

        self.assertFalse((self.overlay() / "leftover-from-another-checkpoint").is_symlink(),
                         "a stale link survived the rebuild")
        self.assertEqual(
            sorted(path.name for path in self.overlay().iterdir()),
            sorted({path.name for path in self.checkpoint.iterdir()} | {"chat_template.jinja"}),
        )
        self.assertEqual(env["MODEL_PATH"], str(self.overlay()))

    def test_missing_mod_template_fails_closed(self):
        # The seam, not a delete: an interrupted run must never leave the repo
        # (and its syncthing peer) without a shipped artifact.
        with self.assertRaises(SystemExit) as caught:
            self.run_overlay(template=str(self.root / "absent.jinja"))
        self.assertEqual(caught.exception.code, 2)
        self.assertFalse(self.overlay().exists(), "nothing may be staged")

    def test_unwritable_overlay_fails_closed(self):
        if os.geteuid() == 0:
            self.skipTest("root ignores directory permissions")
        blocked = self.root / "blocked"
        blocked.mkdir()
        blocked.chmod(0o500)
        try:
            with self.assertRaises(SystemExit) as caught:
                self.run_overlay(overlay_dir=str(blocked / "model-overlay"))
            self.assertEqual(caught.exception.code, 2,
                             "an unstageable farm must fail closed, not traceback")
        finally:
            blocked.chmod(0o700)

    def test_the_mod_copy_matches_the_tensorfold_lane(self):
        data = TEMPLATE.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), TEMPLATE_SHA256,
                         "the mod's template changed; the receipts cite this sha "
                         "and the TensorFold lane serves the same file")
        self.assertEqual(data, TF_TEMPLATE.read_bytes(),
                         "the two shipped copies have drifted apart")
        self.assertFalse(TEMPLATE.is_symlink(),
                         "a symlink here would stage nothing on a fresh node")


if __name__ == "__main__":
    unittest.main()
