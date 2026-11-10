# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Guard: the served checkpoint is the recipe's pin, on every path.

Two failures on 2026-11-10 motivated this file, both on the knapcio lane:

1. a quartet boot served ``snapshots/08c8657f…`` while the recipe pinned
   ``1bae0e10…`` -- ``sparkrun``'s ``bind_runtime_models`` is a no-op when no
   prepared model exists on the hosts (``distribution.model.enabled: false``),
   so the launcher received the *repo id* and resolved it through the cache's
   ``refs/main``, making ``model_revision:`` a comment;
2. an earlier boot died 143 s in on ``model-00047-of-00048.safetensors`` because
   that ``refs/main`` pointed at a half-present snapshot mid-pull.

So the launcher resolves ONLY ``DSV41_MODEL_REVISION`` and refuses otherwise.
That pin lives in two places -- the top-level ``model_revision:`` and the
recipe's ``env:`` block -- and two copies of a sha diverge unless a test holds
them together. ``RecipePinMatchesEnv`` is that guard; ``PinnedResolution`` is
the launcher logic itself. Both parse recipe TEXT with regex (no PyYAML: the
repo's tests are stdlib-only, see test_ds4_recipes.py's header).

Every guard has a negative control: a control that passes on a tree where the
pin disagrees proves nothing. The controls mutate strings in memory.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RECIPE_DIR = REPO / "recipes" / "ds4"
LAUNCHER = RECIPE_DIR / "mods" / "dsv41-sglang-overlay" / "launcher.py"
KNAPCIO = RECIPE_DIR / "deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml"
# The env key the mod's launcher reads. Only recipes that mount the overlay are
# in scope: the other ds4 lanes hand the revision to their own engine
# (``--revision`` on llama.cpp, the TensorFold launcher), so a copy here would
# be dead config on those.
ENV_KEY = "DSV41_MODEL_REVISION"
OVERLAY_MOD = "mods/dsv41-sglang-overlay"


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


# --------------------------------------------------------------------------
# Parsing. Whole-line comments go first: these recipes' prose names the flags
# and keys they explain the absence of ("until binding forced or
# `_resolved_models_dir` checks every shard"), so an unstripped comment can
# satisfy a guard that a real key would not.
# --------------------------------------------------------------------------

def _strip_comment_lines(text: str) -> str:
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _top_level(text: str, key: str) -> str | None:
    """A top-level scalar. Indented keys (``defaults:`` members) cannot match."""
    m = re.search(rf"^{re.escape(key)}:[ \t]*(\S+)[ \t]*$", _strip_comment_lines(text), re.M)
    return _unquote(m.group(1)) if m else None


def _env_lines(text: str) -> list[str]:
    """The body of the top-level ``env:`` mapping, comments already stripped."""
    lines = _strip_comment_lines(text).splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.rstrip() == "env:"), None)
    if start is None:
        return []
    body: list[str] = []
    for ln in lines[start + 1:]:
        if not ln.strip():
            continue
        if not ln.startswith((" ", "\t")):
            break
        body.append(ln)
    return body


def _env_value(text: str, key: str) -> str | None:
    m = re.search(rf"^\s+{re.escape(key)}:[ \t]*(\S+)[ \t]*$",
                  "\n".join(_env_lines(text)), re.M)
    return _unquote(m.group(1)) if m else None


def _serves_overlay(text: str) -> bool:
    return bool(re.search(rf'^\s*-\s*["\']?{re.escape(OVERLAY_MOD)}["\']?\s*$',
                          _strip_comment_lines(text), re.M))


def pin_violations(text: str) -> list[str]:
    """Every way one recipe's two copies of the pin disagree (empty = fine)."""
    if not _serves_overlay(text):
        return []                       # revision not this launcher's business
    pin = _top_level(text, "model_revision")
    if pin is None:
        return []                       # nothing pinned, nothing to mirror
    env_pin = _env_value(text, ENV_KEY)
    if env_pin is None:
        return [f"no {ENV_KEY} in env: for model_revision {pin}"]
    if env_pin != pin:
        return [f"{ENV_KEY} {env_pin} != model_revision {pin}"]
    return []


RECIPE_TEMPLATE = """\
model: deepseek-ai/DeepSeek-V4.1-Flash-1017
model_revision: {pin}
runtime: sglang
mods:
  - "mods/dsv41-sglang-overlay"
env:
  {env_line}
command: >
  python3 /workspace/mods/dsv41-sglang-overlay/launcher.py --boot
  --model deepseek-ai/DeepSeek-V4.1-Flash-1017
"""


def _recipe(pin: str = "aaaa", env: str = "DSV41_MODEL_REVISION: aaaa") -> str:
    return RECIPE_TEMPLATE.format(pin=pin, env_line=env)


class RecipePinMatchesEnv(unittest.TestCase):
    def test_every_overlay_recipe_carries_its_pin_in_env(self):
        covered = []
        for path in sorted(RECIPE_DIR.glob("*.yaml")):
            text = path.read_text(encoding="utf-8")
            if _serves_overlay(text) and _top_level(text, "model_revision"):
                covered.append(path.name)
            self.assertEqual(pin_violations(text), [], f"{path.name}: {pin_violations(text)}")
        self.assertIn(KNAPCIO.name, covered)
        self.assertGreaterEqual(len(covered), 7,
                                f"the guard covered {covered}; the glob broke")

    def test_the_launcher_reads_the_key_this_guard_writes(self):
        self.assertEqual(load_launcher().MODEL_REVISION_ENV, ENV_KEY)

    # --- negative controls: each proves the guard can fail ------------------

    def test_control_matching_pin_passes(self):
        self.assertEqual(pin_violations(_recipe()), [])

    def test_control_missing_env_line_fires(self):
        text = _recipe(env="EXTRA_SGLANG_ARGS: --enable-metrics")
        self.assertEqual(len(pin_violations(text)), 1)
        self.assertIn(ENV_KEY, pin_violations(text)[0])

    def test_control_disagreeing_pin_fires(self):
        text = _recipe(env="DSV41_MODEL_REVISION: bbbb")
        self.assertEqual(pin_violations(text),
                         [f"{ENV_KEY} bbbb != model_revision aaaa"])

    def test_control_commented_out_env_line_still_fires(self):
        # F20: the prose explaining the pin must not satisfy the guard.
        text = _recipe(env="# DSV41_MODEL_REVISION: aaaa")
        self.assertIn("no " + ENV_KEY, pin_violations(text)[0])

    def test_control_a_recipe_without_the_overlay_is_out_of_scope(self):
        text = _recipe(env="").replace('  - "mods/dsv41-sglang-overlay"\n', "")
        self.assertEqual(pin_violations(text), [])
        self.assertFalse(_serves_overlay(text))


# --------------------------------------------------------------------------
# The launcher's resolution logic.
# --------------------------------------------------------------------------

MODEL = "deepseek-ai/DeepSeek-V4.1-Flash-1017"
PIN = "08c8657f02291e11b6f6b63e0e16014f8e748518"
DECOY = "1bae0e1088993b9b82de08f59de5be5a34e42170"
SHARDS = ("model-00001-of-00002.safetensors", "model-00002-of-00002.safetensors")


def _snapshot(parent: Path, name: str) -> Path:
    snap = parent / name
    snap.mkdir(parents=True)
    (snap / "config.json").write_text("{}", encoding="utf-8")
    (snap / "chat_template.jinja").write_text("{{ mine }}", encoding="utf-8")
    (snap / "model.safetensors.index.json").write_text(
        json.dumps({"weight_map": {f"layer.{i}": s for i, s in enumerate(SHARDS)}}),
        encoding="utf-8")
    for shard in SHARDS:
        (snap / shard).write_bytes(b"w" * 16)
    return snap


class PinnedResolution(unittest.TestCase):
    def setUp(self):
        self.module = load_launcher()
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.repo = root / "hub" / ("models--" + MODEL.replace("/", "--"))
        self.pinned = _snapshot(self.repo / "snapshots", PIN)
        # A complete decoy at refs/main: serving it would still boot, so only a
        # pin-honouring resolver returns the pinned path here.
        self.decoy = _snapshot(self.repo / "snapshots", DECOY)
        (self.repo / "refs").mkdir()
        (self.repo / "refs" / "main").write_text(DECOY + "\n", encoding="utf-8")
        self._saved = (self.module.HF_HUB, self.module._CACHE, self.module.OVERLAY_DIR)
        self.module.HF_HUB = str(root / "hub")
        self.module._CACHE = str(root / "cache")
        self.module.OVERLAY_DIR = str(root / "cache" / "model-overlay")

    def tearDown(self):
        self.module.HF_HUB, self.module._CACHE, self.module.OVERLAY_DIR = self._saved
        self._tmp.cleanup()

    def resolve(self, **env):
        """Run the resolver; returns (env, stdout, exit code or None)."""
        env = dict(env)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            try:
                self.module.resolve_checkpoint(env)
            except SystemExit as exc:
                return env, out.getvalue(), exc.code
        return env, out.getvalue(), None

    def test_pinned_snapshot_is_served_not_refs_main(self):
        env, out, code = self.resolve(MODEL_ID=MODEL, DSV41_MODEL_REVISION=PIN)
        self.assertIsNone(code)
        self.assertEqual(env["MODEL_PATH"], str(self.pinned))
        self.assertEqual(env["DSV41_SOURCE"], str(self.pinned))
        self.assertNotEqual(env["MODEL_PATH"], str(self.decoy))
        self.assertIn("pinned revision", out)

    def test_missing_shard_dies_naming_the_file(self):
        (self.pinned / SHARDS[1]).unlink()
        env, out, code = self.resolve(MODEL_ID=MODEL, DSV41_MODEL_REVISION=PIN)
        self.assertEqual(code, 2)
        self.assertIn(SHARDS[1], out)
        self.assertNotIn("MODEL_PATH", env)

    def test_empty_shard_is_not_complete(self):
        (self.pinned / SHARDS[0]).write_bytes(b"")
        env, out, code = self.resolve(MODEL_ID=MODEL, DSV41_MODEL_REVISION=PIN)
        self.assertEqual(code, 2)
        self.assertIn(SHARDS[0], out)

    def test_repo_id_without_a_pin_is_refused(self):
        env, out, code = self.resolve(MODEL_ID=MODEL)
        self.assertEqual(code, 2)
        self.assertIn("refs/main", out)
        self.assertIn(ENV_KEY, out)
        self.assertIn("MODEL_PATH", out)         # names both ways to fix it
        self.assertNotIn("MODEL_PATH", env)

    def test_absent_pinned_snapshot_dies(self):
        env, out, code = self.resolve(MODEL_ID=MODEL, DSV41_MODEL_REVISION="deadbeef")
        self.assertEqual(code, 2)
        self.assertIn("deadbeef", out)
        self.assertIn("absent", out)

    def test_prepared_path_is_unchanged(self):
        env, _out, code = self.resolve(MODEL_ID=str(self.pinned))
        self.assertIsNone(code)
        self.assertEqual(env["MODEL_PATH"], str(self.pinned))
        self.assertEqual(env["DSV41_SOURCE"], str(self.pinned))

    def test_supplied_model_path_is_left_alone(self):
        env, _out, code = self.resolve(MODEL_ID=MODEL, MODEL_PATH=str(self.decoy))
        self.assertIsNone(code)
        self.assertEqual(env["MODEL_PATH"], str(self.decoy))
        self.assertEqual(env["DSV41_SOURCE"], str(self.decoy))


if __name__ == "__main__":
    unittest.main()
