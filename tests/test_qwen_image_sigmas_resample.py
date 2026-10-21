# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Guard the sigma-resampling path of the qwen-image launcher mod.

The checkpoint's saved `sample_sigmas` wins over `num_inference_steps`, so a
non-null step count used to be silently ignored (measured 2026-10-21: 12 steps
returned the byte-identical PNG in the same 11.47 s). `schedule_kwargs()` is what
makes the count mean something, so its invariants get a test: a strictly
decreasing list (a repeated sigma is a zero-length step), the saved endpoints
kept, and no `sigmas` kwarg at all when the shipped schedule is asked for.

`NegativeControls` re-runs each guard against shadow copies of `server.py` whose
schedule function is mutated back to the pre-mod behaviour and to the
index-rounding bug — the guards must go red on those, or they prove nothing.
"""

from __future__ import annotations

import importlib.util
import itertools
import tempfile
import unittest
from pathlib import Path

SERVER = (Path(__file__).resolve().parent.parent
          / "recipes/explore/mods/qwen-image-2.1-turbo-launcher/server.py")

# The checkpoint's shipped 8-step curve (model_index.json, Qwen/Qwen-Image-2.1-Turbo).
BASE = [1.0, 0.978453, 0.95418, 0.926626, 0.89508, 0.845148, 0.704534, 0.414568]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_shadow(name: str, source: str):
    """Import a mutated copy of server.py from a temp dir."""
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / (name + ".py")
        path.write_text(source, encoding="utf-8")
        return _load(name, path)


def _schedule(source: str) -> str:
    """The `def schedule_kwargs` block, as text, for the shadow mutations."""
    start = source.index("def schedule_kwargs(")
    end = source.index("def run_generate(")
    return source[start:end]


server = _load("qwen_launcher_server", SERVER)


def assert_schedule_guard(case: unittest.TestCase, module) -> None:
    """The invariant the measurements depend on — shared with the controls."""
    kw, used = module.schedule_kwargs({"num_inference_steps": 12}, BASE)
    case.assertTrue(used, "a 12-step request produced no sigmas")
    case.assertEqual(len(used), 12)
    case.assertIn("sigmas", kw)
    case.assertEqual(kw["sigmas"], used)
    case.assertEqual(used[0], BASE[0])
    case.assertEqual(used[-1], BASE[-1])
    for a, b in itertools.pairwise(used):
        case.assertGreater(a, b)


class ResampleSigmasTest(unittest.TestCase):
    def test_endpoints_and_length(self):
        for steps in (2, 4, 8, 12, 40):
            out = server.resample_sigmas(BASE, steps)
            self.assertEqual(len(out), steps)
            self.assertEqual(out[0], BASE[0])
            self.assertEqual(out[-1], BASE[-1])

    def test_strictly_decreasing(self):
        for steps in (2, 3, 4, 7, 12, 40):
            out = server.resample_sigmas(BASE, steps)
            for a, b in itertools.pairwise(out):
                self.assertGreater(a, b, f"steps={steps} produced {out}")

    def test_shipped_count_is_identity(self):
        self.assertEqual(server.resample_sigmas(BASE, len(BASE)), BASE)

    def test_rejects_degenerate_step_count(self):
        with self.assertRaises(ValueError):
            server.resample_sigmas(BASE, 1)


class ScheduleKwargsTest(unittest.TestCase):
    def test_explicit_sigmas_pass_through(self):
        sigmas = [1.0, 0.89508, 0.704534, 0.414568]
        kw, used = server.schedule_kwargs({"sigmas": sigmas}, BASE)
        self.assertEqual(used, sigmas)
        self.assertEqual(kw, {"sigmas": sigmas})

    def test_shipped_count_leaves_the_saved_schedule_alone(self):
        # Measured control: steps=8 after the mod stayed byte-identical to before it.
        kw, used = server.schedule_kwargs({"num_inference_steps": 8}, BASE)
        self.assertIsNone(used)
        self.assertEqual(kw, {})

    def test_absent_step_count_leaves_the_saved_schedule_alone(self):
        self.assertEqual(server.schedule_kwargs({}, BASE), ({}, None))

    def test_non_shipped_count_resamples_and_reports(self):
        assert_schedule_guard(self, server)

    def test_step_count_without_the_saved_curve_raises(self):
        with self.assertRaises(ValueError):
            server.schedule_kwargs({"num_inference_steps": 12}, None)

    def test_degenerate_count_raises(self):
        with self.assertRaises(ValueError):
            server.schedule_kwargs({"num_inference_steps": 1}, BASE)


class NegativeControls(unittest.TestCase):
    """A guard that cannot fail proves nothing. Each control mutates the module."""

    @classmethod
    def setUpClass(cls):
        cls.source = SERVER.read_text(encoding="utf-8")
        cls.live = _schedule(cls.source)

    def test_control_pre_mod_function_fails_the_guard(self):
        # The exact pre-mod behaviour, verbatim from the unpatched server.py
        # (`call["num_inference_steps"] = int(...)`, no sigmas): the field reached
        # the pipeline and was dropped, which is why 12 steps wrote an 8-step image.
        pre_mod = (
            "def schedule_kwargs(req, shipped):\n"
            "    kw = {}\n"
            "    if req.get('num_inference_steps') is not None:\n"
            "        kw['num_inference_steps'] = int(req['num_inference_steps'])\n"
            "    return kw, None\n\n\n"
        )
        shadow = _load_shadow("qwen_shadow_premod", self.source.replace(self.live, pre_mod))
        with self.assertRaises(AssertionError):
            assert_schedule_guard(self, shadow)

    def test_control_index_rounding_fails_the_guard(self):
        # The bug found while measuring: rounding indices instead of interpolating
        # values repeated a sigma and produced a zero-length step (`steps: 13` for a
        # 12-step request). The monotonicity assertion is what caught it.
        rounding = self.live.replace(
            "sigmas_used = resample_sigmas(shipped, steps)",
            "span = len(shipped) - 1\n"
            "                sigmas_used = [shipped[round(span * i / (steps - 1))]"
            " for i in range(steps)]",
        )
        self.assertNotEqual(rounding, self.live)
        shadow = _load_shadow("qwen_shadow_rounding", self.source.replace(self.live, rounding))
        with self.assertRaises(AssertionError):
            assert_schedule_guard(self, shadow)

    def test_control_a_dropped_sigmas_kwarg_fails_the_guard(self):
        dropped = self.live.replace('        kw["sigmas"] = sigmas_used\n', "        pass\n")
        self.assertNotEqual(dropped, self.live)
        shadow = _load_shadow("qwen_shadow_dropped", self.source.replace(self.live, dropped))
        with self.assertRaises(AssertionError):
            assert_schedule_guard(self, shadow)


if __name__ == "__main__":
    unittest.main()