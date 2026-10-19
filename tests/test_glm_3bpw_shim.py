# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Guard the two silent-failure mechanisms of the GLM-5.3 3.0bpw TP=4 shim.

`recipes/glm/mods/tensorfold-glm53-3bpw-launcher` boots an engine whose
`TF_TP_WORLD` defaults to 2 when unset (`split.py` bakes it at import,
`engine.py` uses it as `nranks`) while the guard that would derive it from
`--tp` is a no-op. Four ranks then died in `ncclCommInitRank(world=2, rank=3)`
with NCCL error 4 before any transport stage was reached (2026-10-18 receipt).
sparkrun sets neither `TF_TP_WORLD` nor a stale-lock sweep, so both are this
mod's job and both are silent when wrong.

Stdlib only; no GPU, no image, no checkpoint.
"""
from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
MOD_DIR = REPO_ROOT / "recipes" / "glm" / "mods" / "tensorfold-glm53-3bpw-launcher"
RECIPE = REPO_ROOT / "recipes" / "glm" / "glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang.yaml"


def load_shim():
    spec = importlib.util.spec_from_file_location("glm_3bpw_launcher_shim", MOD_DIR / "launcher.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def args(tp: int) -> SimpleNamespace:
    return SimpleNamespace(tp=tp, kv="q5", dcp=tp, extents=1)


class TpWorld(unittest.TestCase):
    """The engine's NCCL world must come from the launch's own --tp."""

    def setUp(self) -> None:
        self.mod = load_shim()

    def test_world_follows_tp(self) -> None:
        for tp in (2, 4):
            self.assertEqual(str(tp), self.mod.lane_env(args(tp))["TF_TP_WORLD"])

    def test_world_is_not_a_constant(self) -> None:
        # Negative control: a hardcoded TF_TP_WORLD in CONSTANT_ENV would pass
        # test_world_follows_tp for exactly one world and silently pin it.
        self.assertNotIn("TF_TP_WORLD", self.mod.CONSTANT_ENV)


class LockSweep(unittest.TestCase):
    """A killed boot's JIT lock must not block the next start."""

    def test_run_sh_removes_the_build_locks(self) -> None:
        body = (MOD_DIR / "run.sh").read_text()
        sweep = [ln for ln in body.splitlines() if ln.startswith("rm -f ") and "lock" in ln]
        self.assertTrue(sweep, "run.sh does not sweep the JIT build locks")
        self.assertTrue(any("${EXT_DIR}" in ln for ln in sweep))

    def test_run_sh_sweeps_after_creating_the_dir(self) -> None:
        body = (MOD_DIR / "run.sh").read_text()
        created = body.index('mkdir -p "${EXT_DIR}"')
        swept = next(i for i, ln in enumerate(body.splitlines())
                     if ln.startswith("rm -f ") and "lock" in ln)
        self.assertGreater(swept, body[:created].count("\n"))


class Recipe(unittest.TestCase):
    def test_recipe_names_the_shim_and_pins_the_image(self) -> None:
        body = RECIPE.read_text()
        self.assertIn('"mods/tensorfold-glm53-3bpw-launcher"', body)
        self.assertRegex(body, re.compile(r"(?m)^container: .+@sha256:[0-9a-f]{64}$"))

    def test_served_name_is_not_the_model_placeholder(self) -> None:
        body = RECIPE.read_text()
        self.assertIn("served_model_name: GLM-5.3-EXL3-3.0bpw", body)
        self.assertNotRegex(body, re.compile(r"(?m)^\s*served_model_name:.*\{model\}"))


if __name__ == "__main__":
    unittest.main()
