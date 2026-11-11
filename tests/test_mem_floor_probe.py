"""Guards for tools/mem-floor-probe.py — a load-only boot's floor, as a cell the runner counts.

Run:
    uv run python -B -m unittest discover -s tests

Stdlib-only, no network, no cluster, like every other guard here.

The defect this pins (measured 2026-11-10): a Kimi `--load-format dummy` probe answers its fit
question by diving through the parameter-set allocation and dying there, and the executor filed
`rc=4 "never ready — no marker and no machine-readable artefact"` on three attempts that each
held four ranks ~5 min. The floor existed only as console text, so the campaign retried it.

What is pinned:

* the arm-end cell: a written artefact produces the fixed `quality.json` envelope, and
  `tools/next-arms.py`'s own reader calls that receipt measured (`test_the_floor_cell_reads_measured`).
  This is the property `run-arm.sh`'s harvest needs; a client that writes its own JSON instead
  fails it, which is the pre-fix state;
* fail closed on partial data: a rank that stops answering mid-run, a task that never appeared,
  and a sample set shorter than `--min-samples` each exit non-zero and write **nothing**
  (`test_a_lost_rank_writes_nothing`, `test_a_task_that_never_appeared_writes_nothing`,
  `test_a_short_sample_set_writes_nothing`) — a floor built on partial data would read measured;
* a short dive is a measurement, not a failure: the artefact is written and its `verdict` says
  `dive-short` (`test_a_short_dive_is_recorded_as_short`), because the fit answer is the dive;
* the launcher's own floor lines are folded with their provenance when `--log` can parse them
  (`test_floor_lines_are_folded_with_their_file_and_line`).

Nothing here pins wording or timing: the probe is injected, intervals are milliseconds, and the
assertions are the properties.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "mem-floor-probe.py"

PROBE = """#!/bin/sh
# injected probe: `$1` host, `$2` mode, `$3` state dir
host="$1"; mode="$2"; d="$3"
case "$mode" in
  normal)
    c="$d/count-$host"; n=$(cat "$c" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$c"
    mem=$((900000 - 100000*n)); ctns=1; [ "$n" -ge 3 ] && ctns=0 ;;
  never)
    mem=900000; ctns=0 ;;
  fail)
    [ "$host" = r2.example ] && exit 7
    mem=900000; ctns=1 ;;
esac
printf 'mem=%s ctns=%s\\n' "$mem" "$ctns"
"""


def load_next_arms():
    spec = importlib.util.spec_from_file_location("next_arms", ROOT / "tools" / "next-arms.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["next_arms"] = module
    spec.loader.exec_module(module)
    return module


class MemFloorProbeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.arm = self.root / "arm"
        self.arm.mkdir()
        self.probe = self.root / "probe.sh"
        self.probe.write_text(PROBE, encoding="utf-8")
        self.probe.chmod(0o755)
        (self.arm / "task-id.txt").write_text("intent_launch\n", encoding="utf-8")
        (self.arm / "image.txt").write_text("sha256:image\n", encoding="utf-8")
        self.log = self.arm / "launch.log"
        self.log.write_text(
            "pool line available_bytes=5.89 GB full_token=2829824\n"
            "kernel: low memory! at or below SIGTERM limits\n", encoding="utf-8")

    def run_tool(self, mode: str, *extra: str):
        return subprocess.run(
            [sys.executable, "-B", str(TOOL),
             "--task-id-file", str(self.arm / "task-id.txt"),
             "--image-id-file", str(self.arm / "image.txt"),
             "--hosts", "r1.example,r2.example",
             "--interval", "0.01", "--samples", "8", "--min-samples", "2",
             "--out", str(self.arm / "mem-floor.json"),
             "--log", str(self.log),
             "--probe-cmd", f"sh {self.probe} {{host}} {mode} {self.root}",
             *extra],
            capture_output=True, text=True, timeout=120)

    def artefact(self) -> dict:
        return json.loads((self.arm / "mem-floor.json").read_text(encoding="utf-8"))

    def test_the_floor_cell_reads_measured(self) -> None:
        proc = self.run_tool("normal")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = self.artefact()
        self.assertEqual(payload["task_id"], "intent_launch")
        self.assertEqual(payload["image_id"], "sha256:image")
        self.assertEqual(sorted(payload["ranks"]), ["r1.example", "r2.example"])
        self.assertGreaterEqual(payload["sample_count"], 3)
        self.assertEqual(payload["verdict"], "measured")
        for rank in payload["ranks"].values():
            self.assertGreaterEqual(len(rank["samples"]), 2)
            self.assertIsInstance(rank["min_kb"], int)
            self.assertIsInstance(rank["min_at_s"], float)
            self.assertGreaterEqual(rank["min_at_s"], 0.0)
        quality = json.loads((self.arm / "quality.json").read_text(encoding="utf-8"))
        self.assertEqual(quality["producer"]["component"], "mem-floor-probe")
        self.assertEqual(list(quality["client"]), ["mem-floor.json"])
        # The measured set is tools/next-arms.py's own reader, not a copy of its rule.
        ok, reason = load_next_arms().arm_measured(str(self.arm))
        self.assertTrue(ok, reason)

    def test_a_lost_rank_writes_nothing(self) -> None:
        proc = self.run_tool("fail")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("lost a rank", proc.stderr)
        self.assertFalse((self.arm / "mem-floor.json").exists())
        self.assertFalse((self.arm / "quality.json").exists())
        ok, _ = load_next_arms().arm_measured(str(self.arm))
        self.assertFalse(ok)

    def test_a_task_that_never_appeared_writes_nothing(self) -> None:
        proc = self.run_tool("never")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("never appeared", proc.stderr)
        self.assertFalse((self.arm / "mem-floor.json").exists())

    def test_a_short_sample_set_writes_nothing(self) -> None:
        proc = self.run_tool("normal", "--samples", "1", "--min-samples", "3")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("short sample set", proc.stderr)
        self.assertFalse((self.arm / "mem-floor.json").exists())

    def test_a_short_dive_is_recorded_as_short(self) -> None:
        proc = self.run_tool("normal", "--expect-dive-gib", "1.0")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.artefact()["verdict"], "dive-short")

    def test_floor_lines_are_folded_with_their_file_and_line(self) -> None:
        proc = self.run_tool("normal")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = self.artefact()["floor_lines"]
        self.assertTrue(any("launch.log:1:" in line and "available_bytes=" in line
                            for line in lines), lines)
        self.assertTrue(any("low memory" in line for line in lines), lines)

    def test_the_executor_arms_the_floor_client_between_resolution_and_readiness(self) -> None:
        """The slot, not the wording: a post-ready hook has no moment on a load-only boot."""
        text = (ROOT / "tools" / "run-arm.sh").read_text(encoding="utf-8")
        guard = '[ "${ARM_EXTRA_CLIENT_AT:-post-ready}" = pre-ready ]'
        self.assertIn(guard, text)
        armed = text.index(guard)
        self.assertLess(text.index("\nlaunch_arm\n"), armed,
                        "the client must be armed after the launch is in flight")
        self.assertLess(text.index('echo "image=$IMAGE_ID"'), armed,
                        "the client waits on image.txt, so it is armed after that cell")
        self.assertLess(armed, text.index("\nready=no\n"),
                        "the client must sample before the readiness wait")
        self.assertIn("> \"$L/task-id.txt\"", text, "the task-id cell is missing")
        self.assertIn('kill "$EXTRA_PID"', text, "the sampler is never reaped")


if __name__ == "__main__":
    unittest.main()
