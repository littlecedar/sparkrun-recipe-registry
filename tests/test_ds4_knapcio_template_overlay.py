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

import builtins
import contextlib
import hashlib
import io
import importlib.util
import os
import sys
import tempfile
import types
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


class InlineSystemShim(unittest.TestCase):
    """Guard: the shim travels on PYTHONPATH, and only for an image that needs it.

    ``dsv41-sm121-dg:0.2.1`` forward-ported ``serving_chat.py`` (it calls
    ``chat_encoding.spec_supports_inline_system``) but kept the older
    ``chat_encoding.py``, so the OpenAI server died in its lifespan and every
    survey arm ended rc=4 at ~250 s. The engine tree is root-owned in the
    container and boot.py starts the server as a subprocess, so the fix has to
    be a ``sitecustomize`` on the child's ``PYTHONPATH``. A consistent image --
    the production canary has the caller nowhere, a rebuilt image carries the
    function -- must be left untouched.
    """

    CALLER = "return chat_encoding.spec_supports_inline_system(self.chat_encoding_spec)\n"

    def setUp(self):
        self.module = load_launcher()
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.engine = root / "openai"
        self.engine.mkdir()
        self.shimdir = root / "shim"
        self._saved = (self.module.ENGINE_OPENAI_DIR, self.module.SHIM_DIR)
        self.module.ENGINE_OPENAI_DIR = str(self.engine)
        self.module.SHIM_DIR = str(self.shimdir)

    def tearDown(self):
        self.module.ENGINE_OPENAI_DIR, self.module.SHIM_DIR = self._saved
        self._tmp.cleanup()

    def stage(self, serving: str, encoding: str) -> None:
        (self.engine / "serving_chat.py").write_text(serving, encoding="utf-8")
        (self.engine / "chat_encoding.py").write_text(encoding, encoding="utf-8")

    def test_a_caller_without_the_callee_stages_the_sitecustomize(self):
        self.stage(self.CALLER, "import os\n")
        env = {"PYTHONPATH": "/opt/dsv41/adapter:/opt/b12x"}
        self.module.ensure_inline_system_shim(env)

        self.assertEqual(env["PYTHONPATH"],
                         "%s:/opt/dsv41/adapter:/opt/b12x" % self.shimdir)
        sitecustomize = self.shimdir / "sitecustomize.py"
        source = sitecustomize.read_text(encoding="utf-8")
        compile(source, str(sitecustomize), "exec")

        # The staged file answers as upstream does, and its import hook installs
        # the symbol on the real module object the server reads.
        namespace: dict = {}
        real_import = builtins.__import__
        try:
            namespace["__file__"] = str(sitecustomize)
            exec(compile(source, str(sitecustomize), "exec"), namespace)
            self.assertFalse(namespace["spec_supports_inline_system"]("dsv41"))
            self.assertTrue(namespace["spec_supports_inline_system"]("kimi_k3"))
            target = sys.modules[namespace["TARGET"]] = types.ModuleType(
                namespace["TARGET"])
            builtins.__import__("json")  # any import after the module lands runs the hook
            self.assertTrue(hasattr(target, "spec_supports_inline_system"))
        finally:
            builtins.__import__ = real_import
            sys.modules.pop(namespace.get("TARGET", ""), None)

    def test_an_image_that_needs_nothing_is_left_alone(self):
        cases = {
            "production canary (no caller)": ("import os\n", "import os\n"),
            "rebuilt image (callee present)":
                (self.CALLER, "def spec_supports_inline_system(spec):\n    return False\n"),
        }
        for name, (serving, encoding_text) in cases.items():
            with self.subTest(name):
                self.stage(serving, encoding_text)
                env = {"PYTHONPATH": "/opt/dsv41/adapter"}
                self.module.ensure_inline_system_shim(env)
                self.assertEqual(env["PYTHONPATH"], "/opt/dsv41/adapter")
                self.assertFalse(self.shimdir.exists())

    def test_the_shim_dir_is_not_added_to_pythonpath_twice(self):
        self.stage(self.CALLER, "")
        env = {"PYTHONPATH": "%s:/opt/dsv41/adapter" % self.shimdir}
        self.module.ensure_inline_system_shim(env)
        self.assertEqual(env["PYTHONPATH"], "%s:/opt/dsv41/adapter" % self.shimdir)

    def _run_shim(self, source, name="shim", checks=None):
        """Exec the staged shim with a real ``__file__`` and restore every global it touches."""
        real_import = builtins.__import__
        real_meta_path = list(sys.meta_path)
        real_path = list(sys.path)
        had_adapter = "dsv41_adapter_sitecustomize" in sys.modules
        try:
            exec(compile(source, name, "exec"), {"__file__": name})
            if checks is not None:
                checks()
        finally:
            builtins.__import__ = real_import
            sys.meta_path[:] = real_meta_path
            sys.path[:] = real_path
            if not had_adapter:
                sys.modules.pop("dsv41_adapter_sitecustomize", None)

    def _adapter_stub(self, marker: Path) -> Path:
        """A stand-in adapter: one file that records that it executed."""
        directory = Path(self._tmp.name) / "adapter"
        directory.mkdir(exist_ok=True)
        (directory / "sitecustomize.py").write_text(
            "with open(%r, 'w') as handle:\n"
            "    handle.write('ran')\n" % str(marker), encoding="utf-8")
        return directory

    def test_the_shim_chains_to_the_adapter_sitecustomize(self):
        """Python imports one ``sitecustomize``, so staging this file hid the adapter's.

        With the adapter's copy unreachable, every overlay patch it installs was
        absent -- including the b12x MoE method that lets the 576-wide per-rank
        experts load at ``EP_SIZE=1`` -- so the stock ``Mxfp4FlashinferCutlassMoEMethod``
        raised its multiples-of-128 guard and three survey arms never booted
        (measured 2026-11-09). The chain is what keeps the adapter installed on an
        image that needs this shim.
        """
        self.stage(self.CALLER, "import os\n")
        self.module.ensure_inline_system_shim({})
        shim = self.shimdir / "sitecustomize.py"
        source = shim.read_text(encoding="utf-8")

        marker = Path(self._tmp.name) / "adapter-ran"
        adapter_dir = self._adapter_stub(marker)
        sys.path[:0] = [str(adapter_dir), str(self.shimdir)]

        def check():
            self.assertEqual(marker.read_text(encoding="utf-8"), "ran",
                             "the staged shim must run the sitecustomize it shadows")
            self.assertIn("dsv41_adapter_sitecustomize", sys.modules)

        self._run_shim(source, name=str(shim), checks=check)

    def test_the_chain_call_is_what_runs_the_adapter(self):
        """Negative control: the same tree, with the trailing chain call removed."""
        self.stage(self.CALLER, "import os\n")
        self.module.ensure_inline_system_shim({})
        shim = self.shimdir / "sitecustomize.py"
        source = shim.read_text(encoding="utf-8")
        stripped = source.replace("\n_load_adapter_sitecustomize()\n", "\n")
        self.assertNotEqual(stripped, source, "the control must actually remove the call")

        marker = Path(self._tmp.name) / "adapter-not-run"
        adapter_dir = self._adapter_stub(marker)
        sys.path[:0] = [str(adapter_dir), str(self.shimdir)]

        self._run_shim(stripped, name=str(shim))
        self.assertFalse(marker.exists(),
                         "without the chain call nothing may execute the shadowed file")

    def test_a_missing_adapter_is_survivable_and_says_so(self):
        """No shadowed file on ``sys.path``: the shim still imports, and reports it."""
        self.stage(self.CALLER, "import os\n")
        self.module.ensure_inline_system_shim({})
        shim = self.shimdir / "sitecustomize.py"
        source = shim.read_text(encoding="utf-8")
        sys.path[:0] = [str(self.shimdir)]

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self._run_shim(source, name=str(shim))
        self.assertIn("overlay patches NOT installed", stderr.getvalue())
        self.assertNotIn("dsv41_adapter_sitecustomize", sys.modules)


if __name__ == "__main__":
    unittest.main()
