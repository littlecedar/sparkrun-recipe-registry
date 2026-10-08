"""Guards for tools/build-dsv41-combined.py -- the combined local HF repo vendorer.

Run:
    python3 -m unittest tests.test_dsv41_combined_tool -v

Stdlib-only and network-free. The builder shells out to ``hf`` and to the Engram
builder, so these guards test the pure plumbing: the engram-overlay subdir
layout, the combined-repo discovery the launcher depends on, the embedded-prompt
refresh, and the manifest hashing (which must never record template *content*).

Why these exist. The combined repo is the single source the TP=2 lane boots
from; if the tables landed at the repo root (where the engine's non-recursive
glob would scan the 39 EXL3 shards), or the engram subdir were renamed, the lane
would silently serve degraded -- a warning at worst. These guards pin the two
paths that must agree: the tool that writes ``engram/`` and the launcher that
reads it.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL_PATH = REPO_ROOT / "tools" / "build-dsv41-combined.py"
LAUNCHER = REPO_ROOT / "mods" / "tensorfold-dsv41-launcher" / "launcher.py"
COMBINED_RECIPE = (
    REPO_ROOT / "recipes" / "ds4" / "deepseek-v4.1-flash-exl3-engram-tp2-1m-sglang.yaml"
)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class OverlayLayout(unittest.TestCase):
    """The tool must write the tables into ``<out>/engram/``, not the repo root."""

    def setUp(self):
        self.tool = _load(TOOL_PATH, "build_dsv41_combined")
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_engram_subdir_constant(self):
        # If this default moves, the launcher's model_dir/engram probe must move
        # with it -- the two are a contract (see LauncherCombinedProbe).
        src = TOOL_PATH.read_text()
        self.assertIn('subdir: str = "engram"', src)

    def test_refresh_rewrites_only_the_template_field(self):
        out = self.out
        (out / "provenance").mkdir()
        (out / "chat_template.jinja").write_text("UPSTREAM-PROMPT", encoding="utf-8")
        cfg = {"bos_token": "x", "chat_template": "OLD-PROMPT", "model_max_length": 9}
        (out / "tokenizer_config.json").write_text(json.dumps(cfg), encoding="utf-8")

        self.tool.refresh_embedded_template(out)

        got = json.loads((out / "tokenizer_config.json").read_text())
        self.assertEqual(got["chat_template"], "UPSTREAM-PROMPT")
        self.assertEqual(got["bos_token"], "x")
        self.assertEqual(got["model_max_length"], 9)
        # The old config is preserved for provenance.
        backup = json.loads((out / "provenance" / "tokenizer_config.exl3.json").read_text())
        self.assertEqual(backup["chat_template"], "OLD-PROMPT")

    def test_refresh_is_a_noop_without_an_embedded_template(self):
        out = self.out
        (out / "chat_template.jinja").write_text("PROMPT", encoding="utf-8")
        cfg = {"bos_token": "x"}  # upstream-style minimal config
        (out / "tokenizer_config.json").write_text(json.dumps(cfg), encoding="utf-8")
        self.tool.refresh_embedded_template(out)
        self.assertEqual(json.loads((out / "tokenizer_config.json").read_text()), cfg)

    def test_manifest_hashes_bytes_and_skips_meta(self):
        out = self.out
        (out / "model-00001-of-00039.safetensors").write_bytes(b"weights")
        (out / "provenance").mkdir()
        (out / "provenance" / "SOURCES.json").write_text("{}")
        (out / ".cache").mkdir()
        (out / ".cache" / "junk").write_bytes(b"x")
        (out / "engram").mkdir()
        (out / "engram" / "engram-l1.partial").write_bytes(b"half")
        dst = out / "provenance" / "MANIFEST.json"

        self.tool.write_manifest(out, dst, {"primary": {"repo": "r"}})

        man = json.loads(dst.read_text())
        paths = sorted(f["path"] for f in man["files"])
        self.assertEqual(paths, ["model-00001-of-00039.safetensors"])
        want = hashlib.sha256(b"weights").hexdigest()
        self.assertEqual(man["files"][0]["sha256"], want)
        # No manifest field may ever carry file *content* (a prompt lives in the
        # repo, and its bytes must not leak into the manifest).
        self.assertNotIn("UPSTREAM-PROMPT", dst.read_text())


class LauncherCombinedProbe(unittest.TestCase):
    """The launcher must prefer ``<model_dir>/engram/`` when the model dir is a
    combined repo, and fall back otherwise."""

    def setUp(self):
        self.mod = _load(LAUNCHER, "tf_launcher_combined")
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.mod.HF_HUB = str(self.root / "hub")
        self.mod.ENGRAM_DIR = str(self.root / "hub" / "dsv41-engram")

    def tearDown(self):
        self.tmp.cleanup()

    def test_combined_engram_subdir_wins(self):
        combined = self.root / "combined"
        (combined / "engram").mkdir(parents=True)
        (combined / "engram" / "engram-l1.safetensors").write_bytes(b"x")
        (combined / "engram" / "engram-l14.safetensors").write_bytes(b"x")
        (combined / "model-00001-of-00039.safetensors").write_bytes(b"w")
        self.assertEqual(
            self.mod.resolve_engram_dir(str(combined)), str(combined / "engram")
        )

    def test_plain_exl3_dir_falls_through_to_mod_dir(self):
        combined = self.root / "exl3-only"
        combined.mkdir()
        (combined / "model-00001-of-00039.safetensors").write_bytes(b"w")
        mod_out = Path(self.mod.ENGRAM_DIR)
        mod_out.mkdir(parents=True)
        (mod_out / "engram-l1.safetensors").write_bytes(b"x")
        self.assertEqual(
            self.mod.resolve_engram_dir(str(combined)), str(mod_out)
        )

    def test_empty_combined_subdir_falls_through(self):
        combined = self.root / "combined"
        (combined / "engram").mkdir(parents=True)  # empty
        mod_out = Path(self.mod.ENGRAM_DIR)
        mod_out.mkdir(parents=True)
        (mod_out / "engram-l14.safetensors").write_bytes(b"x")
        self.assertEqual(
            self.mod.resolve_engram_dir(str(combined)), str(mod_out)
        )


class CombinedRecipe(unittest.TestCase):
    """The combined recipe offsets the fetch mod with the shipped tables."""

    def setUp(self):
        self.text = COMBINED_RECIPE.read_text()
        # Comments document the forbidden string (F20), so executable lines only.
        self.clean = "\n".join(
            ln for ln in self.text.splitlines() if not ln.lstrip().startswith("#")
        )

    def test_recipe_uses_the_combined_model(self):
        self.assertIn(
            "model: littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram", self.text
        )

    def test_no_engram_fetch_mod(self):
        # The tables ship inside the repo; the detached fetch must NOT be listed,
        # or every node re-fetches 189 GiB it already has.
        self.assertNotIn("dsv41-engram-fetch", self.clean)
        self.assertIn("mods/tensorfold-dsv41-launcher", self.clean)

    def test_engram_dir_is_not_declared_because_the_launcher_finds_it(self):
        # No operator knob required: resolve_engram_dir(model_dir) does the work.
        self.assertNotIn("TENSORFOLD_ENGRAM_DIR", self.clean)


if __name__ == "__main__":
    unittest.main()