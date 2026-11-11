"""Guard `mods/reown-runtime-cache`: reown, verify, fail closed, and order.

The mod exists because a root pre_exec hook left a root-owned FlashInfer cache
behind and every later uid-1000 serve died on it (register row
`runtime-cache-flashinfer-root-owned-subtree`). The defect that makes this worth
a guard is silent success: a chown that does not stick, or a mod listed before
the writer it repairs, would log a clean launch and leave the tree broken.

Tests drive `run.sh` as a subprocess with `MOD_CACHEDIR`/`MOD_LOGDIR` pointing
at a temp tree, so they touch no real cache.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MOD = REPO_ROOT / "mods" / "reown-runtime-cache"
RUN = MOD / "run.sh"


def run_mod(fixture: Path, paths: str, path_prefix: str = "", extra_env=None):
    env = {
        **os.environ,
        "MOD_CACHEDIR": str(fixture),
        "MOD_LOGDIR": str(fixture / "modlogs"),
        "REOWN_PATHS": paths,
        "PATH": f"{path_prefix}:{os.environ['PATH']}" if path_prefix else os.environ["PATH"],
    }
    env.pop("MOD_TIMEOUT", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(RUN)], env=env, capture_output=True, text=True, timeout=60
    )


class ReownsAndVerifies(unittest.TestCase):
    def test_reowns_fixture_path_and_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "flashinfer"
            (target / ".cache" / "flashinfer").mkdir(parents=True)
            (target / ".cache" / "flashinfer" / "flashinfer_jit.log").write_text("x")
            proc = run_mod(root, str(target))
            log = (root / "modlogs" / "reown-runtime-cache.log").read_text()
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr + log)
            stat = os.stat(target)
            self.assertEqual(f"{os.getuid()}:{os.getgid()}", f"{stat.st_uid}:{stat.st_gid}")
            self.assertIn(f"owner {os.getuid()}:{os.getgid()} ->", log)
            self.assertIn("all checked against", log)

    def test_absent_path_is_skipped_not_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "never-written"
            proc = run_mod(root, str(missing))
            log = (root / "modlogs" / "reown-runtime-cache.log").read_text()
            self.assertEqual(0, proc.returncode, log + proc.stderr)
            self.assertFalse(missing.exists(), "the mod created a path it was only asked to check")
            self.assertIn(f"skip: {missing} does not exist", log)


class FailsClosedOnStuckRepair(unittest.TestCase):
    def test_path_that_stays_root_owned_exits_non_zero_and_names_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "flashinfer"
            target.mkdir()
            shim = root / "shim"
            shim.mkdir()
            # A chown that reports success and changes nothing is the failure the
            # guard exists for; the stat shim reports the path as root either way.
            (shim / "chown").write_text("#!/bin/sh\nexit 0\n")
            (shim / "stat").write_text(
                "#!/bin/sh\n"
                f'case "$*" in\n'
                f'  *"{target}"*) [ "${{1:-}}" = "-c" ] && echo 0:0 || /usr/bin/stat "$@" ;;\n'
                f'  *) /usr/bin/stat "$@" ;;\n'
                "esac\n"
            )
            (shim / "chown").chmod(0o755)
            (shim / "stat").chmod(0o755)
            proc = run_mod(root, str(target), path_prefix=str(shim))
            log = (root / "modlogs" / "reown-runtime-cache.log").read_text()
            self.assertNotEqual(0, proc.returncode, proc.stdout + proc.stderr + log)
            self.assertIn(str(target), log)
            self.assertIn("still 0:0", log)


class RecipesOrderTheModAfterTheWriter(unittest.TestCase):
    MODS = (
        REPO_ROOT / "recipes" / "explore" / "ernie-5.5-flash-base-tp4-flashinfer-sparse-sglang.yaml",
        REPO_ROOT / "recipes" / "ds4" / "zz-ds4-1017-sm121-arm5-fi073.yaml",
    )
    WRITER = {
        MODS[0]: "mods/ernie55-flashinfer-sparse-sglang",
        MODS[1]: "mods/dsv41-sglang-overlay",
    }

    def test_each_recipe_lists_reown_after_the_hook_that_writes_the_cache(self) -> None:
        for recipe in self.MODS:
            with self.subTest(recipe=recipe.name):
                entries = [
                    line.strip().lstrip("- ").strip().strip('"')
                    for line in recipe.read_text(encoding="utf-8").splitlines()
                    if line.strip().startswith("- \"mods/")
                ]
                self.assertIn("mods/reown-runtime-cache", entries)
                self.assertLess(
                    entries.index(self.WRITER[recipe]),
                    entries.index("mods/reown-runtime-cache"),
                    "reown must run after the mod whose root writes it repairs",
                )


if __name__ == "__main__":
    unittest.main()
