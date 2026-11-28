"""Guards for mods/aneda-launcher/logprefix.py -- the record envelope at the boundary.

Run:
    uv run python -B -m unittest tests.test_aneda_logprefix -v

Why these exist. Step 1 of the Aneda logging plan ships no image rebuild: the
engine and front still print bare text, so launch.sh pipes each stream through
this filter. A line that already carries the envelope (`ts=`) passes through
untouched, which is what lets the same pipe carry Step 2's in-process records
unchanged -- so idempotence is the property the whole migration leans on.

The filter runs as a subprocess here, the way launch.sh runs it (`python3 -u`),
so the tests exercise the real stdin/stdout path, including EOF. Stdlib only, no
PyYAML, no sparkrun import (AGENTS.md: tests/ runs on a head node, in a
container and on a laptop).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FILTER = REPO_ROOT / "recipes" / "ds4" / "mods" / "aneda-launcher" / "logprefix.py"

#: The envelope the filter must add, with the trailing space that separates it
#: from the old text. The timestamp shape is checked on its own below.
ENVELOPE = re.compile(
    r"^ts=\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z level=info node=\S+ "
    r"rank=\d+ src=\S+ event=\S+ "
)


def run_filter(text: str, *args: str, node: str | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "ANEDA_NODE_HOST"}
    if node is not None:
        env["ANEDA_NODE_HOST"] = node
    return subprocess.run(
        [sys.executable, "-u", str(FILTER), *args],
        input=text, capture_output=True, text=True, encoding="utf-8", timeout=60, env=env,
    )


class Envelope(unittest.TestCase):
    def test_an_unstamped_line_gains_the_envelope_and_keeps_its_text(self):
        r = run_filter("serve: req 1 done\n", "--src", "engine", "--rank", "2")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIsNotNone(ENVELOPE.match(r.stdout), r.stdout)
        self.assertEqual("serve: req 1 done\n", ENVELOPE.sub("", r.stdout, count=1))
        self.assertEqual(1, r.stdout.count("\n"), "one input line is one record")

    def test_a_stamped_line_passes_through_byte_identical(self):
        line = ('ts=2026-11-28T04:05:06.789Z level=info node=h rank=3 src=front '
                'event=req.done msg="x"\n')
        r = run_filter(line)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(line, r.stdout)

    def test_src_rank_and_node_land_in_the_record(self):
        r = run_filter("x\n", "--src", "vision", "--rank", "3", node="gb10-7")
        self.assertIn("node=gb10-7 rank=3 src=vision ", r.stdout)

    def test_defaults_are_engine_and_rank_0(self):
        r = run_filter("x\n")
        self.assertIn("rank=0 src=engine ", r.stdout)

    def test_the_timestamp_is_utc_iso_with_milliseconds(self):
        r = run_filter("x\n")
        self.assertRegex(r.stdout.split(" ", 1)[0],
                         r"^ts=\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$")

    def test_quotes_unicode_and_equals_survive_in_the_tail(self):
        line = 'req 7: msg="héllo" a=b c=d 日本語\n'
        r = run_filter(line)
        self.assertTrue(r.stdout.endswith(line), r.stdout)

    def test_eof_without_a_trailing_newline_still_emits_the_last_record(self):
        r = run_filter("last line without a newline")
        self.assertIsNotNone(ENVELOPE.match(r.stdout), r.stdout)
        self.assertTrue(r.stdout.endswith(" last line without a newline\n"), r.stdout)


class NegativeControls(unittest.TestCase):
    """A guard that cannot fail proves nothing. This mutates a copy in a temp dir."""

    def test_without_the_idempotence_check_a_stamped_line_is_double_stamped(self):
        source = FILTER.read_text(encoding="utf-8")
        mutated = source.replace('if line.startswith(b"ts="):', "if False:")
        self.assertNotEqual(source, mutated,
                            "the idempotence check moved: update this control")
        with tempfile.TemporaryDirectory() as td:
            copy = Path(td) / "logprefix.py"
            copy.write_text(mutated, encoding="utf-8")
            line = ("ts=2026-11-28T04:05:06.789Z level=info node=h rank=0 "
                    "src=engine event=x\n")
            r = subprocess.run([sys.executable, "-u", str(copy)], input=line,
                               capture_output=True, text=True, encoding="utf-8", timeout=60)
            self.assertEqual(0, r.returncode, r.stderr)
            self.assertNotEqual(line, r.stdout,
                                "the pass-through assertion would not catch this mutant")
            self.assertTrue(r.stdout.endswith(" " + line), r.stdout)


if __name__ == "__main__":
    unittest.main()
