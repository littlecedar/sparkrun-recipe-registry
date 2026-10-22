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

`RequestPathTest` drives `run_generate()` itself with a stubbed torch and
pipeline: `schedule_kwargs()` being right does not prove its caller unpacks it,
and on 2026-10-22 it did not — `call.update(schedule_kwargs(...)[0])` left
`sigmas_used` undefined, so **every** `POST /generate` returned 500 while every
test above stayed green. Its control mutates that line back and must raise.
"""

from __future__ import annotations

import importlib.util
import itertools
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

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


class _FakeImage:
    def save(self, path: str) -> None:
        Path(path).write_bytes(b"\x89PNG-stub")


class _FakePipeline:
    """Fires the step callback once per sigma the caller handed it.

    `default_steps` is the checkpoint's own schedule length, used when the call
    carries no `sigmas` (the pipeline force-loads `config.sample_sigmas`).
    """

    def __init__(self, default_steps: int):
        self.default_steps = default_steps
        self.calls: list[dict] = []

    def __call__(self, **call):
        self.calls.append(call)
        steps = len(call["sigmas"]) if call.get("sigmas") else self.default_steps
        callback = call.get("callback_on_step_end")
        for index in range(steps):
            if callback is not None:
                callback(self, index, None, call)
        return types.SimpleNamespace(images=[_FakeImage()])


def _stub_torch():
    class _Cuda:
        def reset_peak_memory_stats(self):
            pass

        def max_memory_allocated(self):
            return 1024 ** 3

        def max_memory_reserved(self):
            return 1024 ** 3

    class _Generator:
        def __init__(self, device):
            self.device = device
            self.seed = None

        def manual_seed(self, seed):
            self.seed = seed
            return self

    return types.SimpleNamespace(Generator=_Generator, cuda=_Cuda())


def run_generate_stubbed(case: unittest.TestCase, module, req: dict):
    """Call run_generate() with no GPU, no diffusers and no network.

    Returns `(response, pipeline_call)`. The stub exists to reach the schedule
    unpacking; everything the pipeline itself does is out of scope here.
    """
    sample_dir = tempfile.TemporaryDirectory()
    case.addCleanup(sample_dir.cleanup)
    pipe = _FakePipeline(len(BASE))
    module.STATE["pipe"] = pipe
    module.STATE["sample_dir"] = sample_dir.name
    module.STATE["shipped_sigmas"] = list(BASE)
    with mock.patch.dict(sys.modules, {"torch": _stub_torch()}):
        response = module.run_generate(req)
    return response, pipe.calls[-1]


def assert_generate_guard(case: unittest.TestCase, module) -> None:
    """run_generate() must survive the schedule call and report what it ran."""
    response, call = run_generate_stubbed(
        case, module, {"prompt": "poster", "num_inference_steps": 4})
    case.assertEqual(response["steps"], 4)
    case.assertEqual(len(response["sigmas_used"]), 4)
    case.assertEqual(call["sigmas"], response["sigmas_used"])

    plain, plain_call = run_generate_stubbed(case, module, {"prompt": "poster"})
    case.assertIsNone(plain["sigmas_used"])
    case.assertNotIn("sigmas", plain_call)
    case.assertEqual(plain["steps"], len(BASE))
    case.assertTrue(Path(plain["image_path"]).is_file())


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


class RequestPathTest(unittest.TestCase):
    def test_reports_the_schedule_it_ran(self):
        assert_generate_guard(self, server)


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

    def test_control_a_single_element_unpack_fails_the_guard(self):
        # The 2026-10-22 live defect, verbatim: schedule_kwargs() was right, but
        # run_generate() read only element [0] while the response reports
        # `sigmas_used`, so every POST /generate raised NameError.
        unpacked = (
            '    sigmas_kw, sigmas_used = schedule_kwargs(req,'
            ' STATE.get("shipped_sigmas"))\n'
            "    call.update(sigmas_kw)\n"
        )
        self.assertIn(unpacked, self.source)
        broken = self.source.replace(
            unpacked,
            '    call.update(schedule_kwargs(req, STATE.get("shipped_sigmas"))[0])\n',
        )
        self.assertNotEqual(broken, self.source)
        shadow = _load_shadow("qwen_shadow_unpack", broken)
        with self.assertRaises(NameError):
            assert_generate_guard(self, shadow)


if __name__ == "__main__":
    unittest.main()