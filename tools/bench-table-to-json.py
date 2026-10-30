#!/usr/bin/env python3
"""bench-table-to-json.py — turn a llama-benchy printed table into a labelled JSON file.

Some `sparkrun benchmark` runs print a complete ladder and write no `--output` file
(measured four times on 2026-10-29; sparkrun's own log lacks llama-benchy's `CSV output`
line in those runs, so the framework's export never ran). The numbers are still real and
still worth keeping, but a receipt whose only record is scrolled text cannot be re-read by
a tool, and a receipt that silently promotes transcribed text to an artefact is worse.

So this writes the same shape as `ladder.json` with `"source"` naming exactly where the
numbers came from. A consumer can tell a transcribed artefact from a framework-written one
by that field, and nothing has to be re-typed by hand.

Input: the table as llama-benchy prints it (a header line, then rows). Blank lines and any
other text are ignored, so `ladder.log` can be fed whole.

    python3 tools/bench-table-to-json.py ~/benchmarks/<win>/<arm>/ladder.log --json out.json

Exit codes: 0 wrote rows; 1 no table rows found; 2 bad flags.

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import sys

HEADER_FIELDS = ("depth", "conc", "pp t/s", "tg t/s", "ttfr ms", "runs")


def parse_table(text: str) -> list[dict[str, object]]:
    """Rows of a printed ladder table. A row is six numbers starting with a depth."""
    rows: list[dict[str, object]] = []
    seen_header = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("depth") and "conc" in stripped:
            seen_header = True
            continue
        parts = stripped.split()
        if len(parts) < 6:
            continue
        try:
            depth, conc, pp, tg, ttfr, runs = (float(x) for x in parts[:6])
        except ValueError:
            continue
        if not seen_header and depth != 0:
            # Without a header, trust only the documented shape: this table at depth 0.
            continue
        rows.append(
            {
                "concurrency": int(conc),
                "context_size": int(depth),
                "prompt_size": None,
                "response_size": None,
                "is_context_prefill_phase": depth > 0,
                "pp_throughput": {"mean": pp},
                "tg_throughput": {"mean": tg},
                "ttfr_ms": ttfr,
                "runs": int(runs),
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Transcribe a llama-benchy table into JSON.")
    ap.add_argument("log", help="a ladder.log (or any file containing the table)")
    ap.add_argument("--json", required=True, help="output path")
    ap.add_argument("--model", default=None, help="served model id, recorded for provenance")
    args = ap.parse_args(argv)

    try:
        text = open(args.log, encoding="utf-8", errors="replace").read()
    except OSError as exc:
        print(f"cannot read {args.log}: {exc}", file=sys.stderr)
        return 2
    rows = parse_table(text)
    if not rows:
        print(f"no ladder rows in {args.log}", file=sys.stderr)
        return 1
    payload = {
        "source": f"transcribed from {args.log} (llama-benchy table; the framework wrote no artifact)",
        "model": args.model,
        "benchmarks": rows,
    }
    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    print(f"{len(rows)} rows -> {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())