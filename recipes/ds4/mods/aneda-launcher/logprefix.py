#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Stamp the Aneda serve stream with the record envelope.

Step 1 of the logging plan ships no image rebuild: the engine and front still
print bare text, so launch.sh pipes each stream through this filter at the
boundary. A line that already carries the envelope (`ts=`) passes through
untouched, so Step 2's in-process records flow through the same pipe unchanged.

Grammar (the same one engine/common/log.h and frontend/src/log.rs emit):

  ts=<UTC ISO-8601 ms> level=<debug|info|warn|error|fatal> node=<hostname>
  rank=<0-3> src=<engine|front|vision|launcher|mod> event=<noun.verb> [msg="<text>"]

The old text is kept verbatim as the tail: sparkrun's log scraper is a
substring gate, and in-process events replace these lines one at a time. Bytes
in, bytes out, so a line the engine wrote cannot fail to decode.

Run (launch.sh does this under a restart loop):
    python3 -u logprefix.py --src engine --rank 0
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
from datetime import datetime, timezone

EVENT = "log.line"


def stamp(src: str, rank: str, node: str) -> bytes:
    """The envelope for one line, timestamped now (UTC, milliseconds)."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:23]
    return f"ts={ts}Z level=info node={node} rank={rank} src={src} event={EVENT} ".encode()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stamp Aneda log lines with the record envelope.")
    ap.add_argument("--src", default="engine")
    ap.add_argument("--rank", default="0")
    args = ap.parse_args(argv)
    # No DNS: ANEDA_NODE_HOST is the recipe's rendered name; gethostname is local.
    node = os.environ.get("ANEDA_NODE_HOST") or socket.gethostname()
    try:
        for line in sys.stdin.buffer:
            if line.startswith(b"ts="):
                sys.stdout.buffer.write(line)
            else:
                # One record per line: terminate a final line that had no newline.
                sys.stdout.buffer.write(stamp(args.src, args.rank, node) + line.rstrip(b"\n") + b"\n")
            sys.stdout.buffer.flush()
    except BrokenPipeError:
        os._exit(0)  # downstream gone is the container stopping, not an error
    return 0


if __name__ == "__main__":
    sys.exit(main())
