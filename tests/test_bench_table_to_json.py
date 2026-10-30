#!/usr/bin/env python3
"""Guard for tools/bench-table-to-json.py: the transcription must match the printed table,
and it must never claim to be a framework artefact.

The value of this tool is provenance, so the tests pin the provenance field and prove the
parser against a real log (a four-cell table from 2026-10-29) plus two negative controls:
a header-only file yields no rows, and text with no table yields no rows.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "bench-table-to-json.py"

REAL_LOG = """sglang rejects return_token_ids on streaming requests; benchmarking with return_token_ids=false.
sparkrun v0.4.3-alpha+gf9baff2

Runtime:   sglang
depth  conc  pp t/s  tg t/s  ttfr ms  runs
0  1  8708.8  38.0  238.1  5
0  2  8247.4  69.6  398.6  5
0  5  7708.1  134.7  1165.0  5
0  10  8146.1  189.0  1686.9  5

=== Benchmark schedule finished ===
"""


def run(log_text: str) -> tuple[int, dict | None]:
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "ladder.log"
        out = Path(tmp) / "ladder.json"
        log.write_text(log_text)
        p = subprocess.run(
            [sys.executable, str(TOOL), str(log), "--json", str(out), "--model", "X/Model"],
            capture_output=True,
            text=True,
        )
        payload = json.loads(out.read_text()) if out.exists() else None
        return p.returncode, payload


class Transcription(unittest.TestCase):
    def test_the_four_cells_match_the_printed_table(self):
        rc, payload = run(REAL_LOG)
        self.assertEqual(rc, 0)
        cells = [(r["concurrency"], r["tg_throughput"]["mean"]) for r in payload["benchmarks"]]
        self.assertEqual(cells, [(1, 38.0), (2, 69.6), (5, 134.7), (10, 189.0)])

    def test_the_provenance_says_transcribed(self):
        _, payload = run(REAL_LOG)
        self.assertIn("transcribed from", payload["source"])
        self.assertIn("no artifact", payload["source"], "a reader must be able to tell it apart")

    def test_the_model_is_recorded(self):
        _, payload = run(REAL_LOG)
        self.assertEqual(payload["model"], "X/Model")

    def test_a_header_without_rows_is_an_error_not_an_empty_success(self):
        rc, payload = run("depth  conc  pp t/s  tg t/s  ttfr ms  runs\n")
        self.assertEqual(rc, 1)
        self.assertIsNone(payload, "an empty parse must not write a file")

    def test_text_without_a_table_is_an_error(self):
        rc, payload = run("Error: Benchmark incomplete; schedule did not complete\n")
        self.assertEqual(rc, 1)
        self.assertIsNone(payload)


if __name__ == "__main__":
    unittest.main()