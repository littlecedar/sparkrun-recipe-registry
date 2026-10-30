#!/usr/bin/env python3
"""Guard for tools/py-runtime-bench.py: it must run under any interpreter and report every case.

The tool's whole purpose is to be run by *different* interpreters, so the guard runs it as a
subprocess under the current one and checks the artifact shape rather than any particular
number. A latency assertion here would be a flake generator; an assertion that a case vanished
is the failure that matters, because a dropped case silently narrows the comparison.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "py-runtime-bench.py"
CASES = ("loop", "json", "detok", "pydetok", "httparse", "asyncio")


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), *args], capture_output=True, text=True, check=False
    )


class BenchTool(unittest.TestCase):
    def test_every_case_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "r.json"
            p = run("--json", str(out), "--repeat", "1")
            self.assertEqual(p.returncode, 0, p.stderr)
            payload = json.loads(out.read_text())
        self.assertEqual(sorted(payload["ns_per_op"]), sorted(CASES))
        for name, value in payload["ns_per_op"].items():
            self.assertGreater(value, 0.0, f"{name} measured no time")

    def test_the_interpreter_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "r.json"
            run("--json", str(out), "--repeat", "1")
            payload = json.loads(out.read_text())
        self.assertIn("python", payload)
        self.assertIn("implementation", payload)
        self.assertIsInstance(payload["gil_enabled"], bool)

    def test_a_bad_repeat_is_rejected(self):
        p = run("--repeat", "0")
        self.assertEqual(p.returncode, 2)

    def test_it_runs_without_the_json_flag(self):
        p = run("--repeat", "1")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("ns/op", p.stdout)


if __name__ == "__main__":
    unittest.main()