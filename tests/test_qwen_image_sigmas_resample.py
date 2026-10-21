# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Guard the sigma-resampling path of the qwen-image launcher mod.

The checkpoint's saved `sample_sigmas` wins over `num_inference_steps` and a
non-null step count used to be silently ignored (measured 2026-10-21: 12 steps
returned the byte-identical PNG in the same 11.47 s). `resample_sigmas()` is what
makes the step count mean something, so its two invariants are worth a test: a
strictly decreasing list (a repeated sigma is a zero-length step) and the saved
endpoints kept, which is what keeps the resampled curve the same schedule family
rather than a different one.
"""

from __future__ import annotations

import importlib.util
import unittest
from itertools import pairwise
from pathlib import Path

SERVER = (Path(__file__).resolve().parent.parent
          / "recipes/explore/mods/qwen-image-2.1-turbo-launcher/server.py")

spec = importlib.util.spec_from_file_location("qwen_launcher_server", SERVER)
assert spec is not None and spec.loader is not None
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

# The checkpoint's shipped 8-step curve (model_index.json, Qwen/Qwen-Image-2.1-Turbo).
BASE = [1.0, 0.978453, 0.95418, 0.926626, 0.89508, 0.845148, 0.704534, 0.414568]


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
            for a, b in pairwise(out):
                self.assertGreater(a, b, f"steps={steps} produced {out}")

    def test_shipped_count_is_identity(self):
        self.assertEqual(server.resample_sigmas(BASE, len(BASE)), BASE)

    def test_rejects_degenerate_step_count(self):
        with self.assertRaises(ValueError):
            server.resample_sigmas(BASE, 1)


if __name__ == "__main__":
    unittest.main()