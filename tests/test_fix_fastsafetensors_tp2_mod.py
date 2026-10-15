# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Guard the anchor-drift behaviour of the fastsafetensors TP=2 patch mod.

The mod is fail-closed on anchor mismatch by design, and that design met
reality on 2026-10-15: upstream's dev branch (the floating
`lmsysorg/sglang:dev-cu13`) moved the staging-buffer anchor -- `fb` is now
bound *inside* the `try` and a single `finally: loader.close()` replaced the
`finally: pass` the mod anchored on -- so a promoted shipped recipe refused
to launch (captured: `[staging-buffer-release] anchor found 0 time(s)`).

These tests drive the real script as a subprocess against a fake
`sglang.srt.model_loader.weight_utils` on `PYTHONPATH`, one fixture per
upstream shape. The negative controls are the point: an anchor that cannot
match must exit non-zero, and a *partial* apply (device fix in, buffer fix
out -- the exact production failure) must also exit non-zero unless the
documented escape hatch is set.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "mods" / "fix-fastsafetensors-tp2-sglang" / "apply-fastsafetensors-tp2-patch.py"

MARKER_DEVICE = "sparkrun: global rank is not a local CUDA device index"
MARKER_BUFFER = "sparkrun: release the device staging buffer once consumed"

# --- the two upstream shapes the script must handle --------------------------

DEVICE_BLOCK = '    device = torch.device(f"cuda:{rank}")\n'

# Pre-2026-10-15: `fb` bound before the try, and the release stranded in a
# `finally: pass`.
LEGACY_BUFFER_BLOCK = (
    "            fb = loader.copy_files_to_device()\n"
    "            try:\n"
    "                keys = list(fb.key_to_rank_lidx.keys())\n"
    "                for k in keys:\n"
    "                    t = fb.get_tensor(k)\n"
    "                    yield k, t\n"
    "            finally:\n"
    "                pass\n"
)

# Current dev branch (read from the installed image, 2026-10-15): `fb` bound
# inside the try, single `finally: loader.close()`. The leak is unchanged.
CURRENT_BUFFER_BLOCK = (
    "        loader.add_filenames(rank_file_map)\n"  # part of the anchor
    "        try:\n"
    "            fb = loader.copy_files_to_device()\n"
    "            keys = list(fb.key_to_rank_lidx.keys())\n"
    "            for k in keys:\n"
    "                t = fb.get_tensor(k)\n"
    "                yield k, t\n"
    "        finally:\n"
    "            loader.close()\n"
)

HEAD = "def fastsafetensors_weights_iterator(pg, device, enable_gds):\n"


def fixture(buffer_block: str) -> str:
    """Embed a buffer block at its natural indent inside a valid module.

    The device anchor sits at function-body indent (4), the buffer anchors
    one or two levels deeper, so open matching `if True:` guards rather than
    reaching for `textwrap.dedent` games.
    """
    first = buffer_block.splitlines()[0]
    pad = len(first) - len(first.lstrip())
    guards = "".join(" " * n + "if True:\n" for n in range(4, pad, 4))
    return (
        HEAD
        + '    device = torch.device(f"cuda:{rank}")\n'
        + guards
        + buffer_block
        + "    yield from ()\n"
    )


def run_script(fixture_text: str, env_extra: dict | None = None):
    """Write the fixture into a throwaway sglang package and run the script."""
    tmp = tempfile.mkdtemp(prefix="ffs-tp2-")
    pkg = Path(tmp) / "sglang" / "srt" / "model_loader"
    pkg.mkdir(parents=True)
    for init in (Path(tmp) / "sglang", Path(tmp) / "sglang" / "srt", pkg):
        (init / "__init__.py").write_text("")
    target = pkg / "weight_utils.py"
    target.write_text(fixture_text)
    env = dict(os.environ)
    env["PYTHONPATH"] = tmp
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, "-B", str(SCRIPT)],
        capture_output=True, text=True, env=env, timeout=60, check=False,
    )
    return proc, target


class AppliesToBothShapes(unittest.TestCase):
    def test_legacy_two_finally_shape(self) -> None:
        proc, target = run_script(fixture(LEGACY_BUFFER_BLOCK))
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        text = target.read_text()
        self.assertIn(MARKER_DEVICE, text)
        self.assertIn(MARKER_BUFFER, text)
        compile(text, str(target), "exec")

    def test_current_single_finally_shape(self) -> None:
        # The 2026-10-15 production failure: this shape made the promoted
        # recipe refuse to launch.
        proc, target = run_script(fixture(CURRENT_BUFFER_BLOCK))
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        text = target.read_text()
        self.assertIn(MARKER_BUFFER, text)
        self.assertNotIn("finally:\n            loader.close()", text)
        compile(text, str(target), "exec")

    def test_second_run_is_idempotent(self) -> None:
        proc, target = run_script(fixture(CURRENT_BUFFER_BLOCK))
        self.assertEqual(0, proc.returncode)
        first = target.read_text()
        proc2, _ = run_script(first)
        self.assertEqual(0, proc2.returncode, proc2.stdout + proc2.stderr)
        self.assertIn("nothing to write", proc2.stdout)


class FailClosedControls(unittest.TestCase):
    def test_no_anchor_at_all_exits_nonzero(self) -> None:
        proc, _ = run_script("def swapped():  # upstream moved\n    return None\n")
        self.assertEqual(1, proc.returncode)
        self.assertIn("Refusing to launch unpatched", proc.stdout)

    def test_partial_apply_exits_nonzero(self) -> None:
        # Device anchor intact, buffer anchor gone: exactly the launch that
        # died on 2026-10-15. Half-fixed must be fatal.
        proc, _ = run_script(HEAD + DEVICE_BLOCK + "    return None\n")
        self.assertEqual(1, proc.returncode)
        self.assertIn("refusing to launch half-fixed", proc.stdout)
        self.assertIn("staging-buffer-release", proc.stdout)

    def test_partial_apply_allowed_by_escape_hatch(self) -> None:
        proc, target = run_script(
            HEAD + DEVICE_BLOCK + "    return None\n",
            {"SPARKRUN_ALLOW_PARTIAL_FASTSAFETENSORS_PATCH": "1"},
        )
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn(MARKER_DEVICE, target.read_text())


if __name__ == "__main__":
    unittest.main()