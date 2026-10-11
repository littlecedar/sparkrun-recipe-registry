"""Guards for the `ornith-honed-chat-template` mod.

Run:
    python3 -m unittest discover -s tests -v

Stdlib-only, deliberate (AGENTS.md: "tools/ and tests/ are stdlib-only, on
purpose") -- this must run on a head node, in a container, and on a laptop.

Why these exist. The ornith lane's chat template is honed
(`qwen3.8-honed-v22.5.1`) and is delivered by staging a file under MOD_CACHEDIR
that the recipe's `--chat-template` flag reads. The staging is the load-bearing
step: if it silently shipped a truncated or wrong file, the served template
would drift from the verified one with no error at boot. The guards execute
`run.sh` against temp dirs and assert:

  * happy path: the staged file exists, is 30,438 B, carries the honed marker;
  * idempotence: a second run over an identical staged file exits 0 without
    rewriting it (cmp path);
  * fail-closed: a truncated template in the MOD_DIR makes the run exit 1 and
    leave no staged file.

Negative controls live in NegativeControls and only mutate files under
tempdirs; nothing here touches a real /cache (the UID inference falls back to
MOD_CACHEDIR's owner, which the env provides).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MOD_DIR = REPO_ROOT / "mods" / "ornith-honed-chat-template"
MOD_SCRIPT = MOD_DIR / "run.sh"
TEMPLATE = MOD_DIR / "chat_template.jinja"
EXPECTED_SIZE = 30438
MARKER = "qwen3.8-honed-v22.5.1"


def _run_mod(env_extra: dict[str, str], root: Path, timeout: int = 60) -> subprocess.CompletedProcess:
    workdir = root / "mod"
    workdir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MOD_SCRIPT, workdir / "run.sh")
    shutil.copy2(TEMPLATE, workdir / "chat_template.jinja")
    env = {k: v for k, v in os.environ.items() if not k.startswith("MOD_")}
    env.setdefault("PATH", "/usr/bin:/bin")
    env.update(env_extra)
    return subprocess.run(
        ["bash", str(workdir / "run.sh")],
        capture_output=True, text=True, timeout=timeout, env=env, cwd=str(workdir),
    )


def _base_env(cache: Path, **extra: str) -> dict[str, str]:
    env = {
        "MOD_CACHEDIR": str(cache),
        "MOD_LOGDIR": str(cache / "modlogs"),
    }
    env.update(extra)
    return env


def _staged(cache: Path) -> Path:
    return cache / "ornith-honed-chat-template" / "chat_template.jinja"


class ModShape(unittest.TestCase):
    def test_mod_is_executable_with_harness_and_payload(self):
        self.assertTrue(MOD_SCRIPT.is_file(), "missing %s" % MOD_SCRIPT)
        self.assertTrue(MOD_SCRIPT.stat().st_mode & 0o111, "%s not executable" % MOD_SCRIPT)
        src = MOD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("set -euo pipefail", src)
        self.assertIn("SPDX-License-Identifier: AGPL-3.0-or-later", src)
        self.assertIn("reown()", src, "mod-template harness missing reown()")
        self.assertIn(MARKER, src, "fail-closed marker check missing")

    def test_payload_matches_the_verified_template(self):
        self.assertTrue(TEMPLATE.is_file(), "missing %s" % TEMPLATE)
        self.assertEqual(TEMPLATE.stat().st_size, EXPECTED_SIZE)
        self.assertIn(MARKER, TEMPLATE.read_text(encoding="utf-8"))
        self.assertTrue(
            (MOD_DIR / "README.md").is_file(), "a new mod ships a README.md"
        )


class Staging(unittest.TestCase):
    def test_stages_the_honed_template_with_size_and_marker(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "cache"
            cache.mkdir()
            r = _run_mod(_base_env(cache), root)
            self.assertEqual(r.returncode, 0, (r.stdout, r.stderr))
            staged = _staged(cache)
            self.assertTrue(staged.is_file(), "no staged template")
            self.assertEqual(staged.stat().st_size, EXPECTED_SIZE)
            self.assertIn(MARKER, staged.read_text(encoding="utf-8"))

    def test_second_run_is_idempotent_by_content(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "cache"
            cache.mkdir()
            first = _run_mod(_base_env(cache), root)
            self.assertEqual(first.returncode, 0, first.stderr)
            staged = _staged(cache)
            inode = staged.stat().st_ino
            second = _run_mod(_base_env(cache), root)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("already staged and identical", second.stdout)
            self.assertEqual(staged.stat().st_ino, inode, "rewrote an identical file")


class NegativeControls(unittest.TestCase):
    def test_truncated_payload_fails_closed_and_stages_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "cache"
            cache.mkdir()
            workdir = root / "mod"
            workdir.mkdir()
            shutil.copy2(MOD_SCRIPT, workdir / "run.sh")
            # The negative control: same mod, truncated template.
            shutil.copy2(TEMPLATE, workdir / "chat_template.jinja")
            bad = workdir / "chat_template.jinja"
            with bad.open("r+b") as fh:
                fh.truncate(1024)
            env = {k: v for k, v in os.environ.items() if not k.startswith("MOD_")}
            env.update(_base_env(cache))
            r = subprocess.run(
                ["bash", str(workdir / "run.sh")],
                capture_output=True, text=True, timeout=60, env=env, cwd=str(workdir),
            )
            self.assertEqual(r.returncode, 1, (r.stdout, r.stderr))
            self.assertFalse(_staged(cache).exists(),
                             "a failed run must not leave a staged file")

    def test_missing_marker_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "cache"
            cache.mkdir()
            workdir = root / "mod"
            workdir.mkdir()
            shutil.copy2(MOD_SCRIPT, workdir / "run.sh")
            marker = MARKER.encode()
            good = TEMPLATE.read_bytes()
            (workdir / "chat_template.jinja").write_bytes(good.replace(marker, b"qwen3.8-honed-v00.0.0"))
            env = {k: v for k, v in os.environ.items() if not k.startswith("MOD_")}
            env.update(_base_env(cache))
            r = subprocess.run(
                ["bash", str(workdir / "run.sh")],
                capture_output=True, text=True, timeout=60, env=env, cwd=str(workdir),
            )
            self.assertEqual(r.returncode, 1, (r.stdout, r.stderr))
            self.assertFalse(_staged(cache).exists())


class RecipeWiring(unittest.TestCase):
    """The recipe must point --chat-template at the staged path and run the mod last."""

    def test_recipe_maps_the_placeholder_and_orders_the_mod(self):
        recipe = REPO_ROOT / "recipes" / "ornith" / "ornith-1.5-35b-a3b-nvfp4-dflash2-sglang.yaml"
        text = "\n".join(
            ln for ln in recipe.read_text(encoding="utf-8").splitlines()
            if not ln.lstrip().startswith("#")
        )
        self.assertIn("honed_chat_template: /cache/runtime/ornith-honed-chat-template/chat_template.jinja", text)
        self.assertIn("--chat-template {honed_chat_template}", text)
        mods_pos = text.index("@littlecedar/mods/ornith-honed-chat-template")
        pipe_pos = text.index("@littlecedar/mods/pip-install-fastsafetensors")
        self.assertGreater(mods_pos, pipe_pos, "template staging must run after pip-install")


if __name__ == "__main__":
    unittest.main()
