#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""One status-board tick: lock, census, render, publish, commit, gate, push.

Why this exists.  The hourly tick used to be a model session composing `mad-science/STATUS.md` by
hand: 22 sessions on 2026-11-21 read 4.61 M context tokens to write one census row, and three
concurrent ticks at 03:00 choked the model because the `/tmp` pid-lock could not tell several
timers apart.  Every cell of the board is now derived (`board-census.py` + `board-render.py`), so a
tick is this script; a model is invoked only when a register row has no fresh summary.

Single-flight is one `flock(LOCK_EX|LOCK_NB)` on `.local/board-tick.lock`, held across collect ->
render -> publish -> commit -> gate -> push.  No stale-lock policy exists and none is needed: the
kernel drops a flock when the holder exits, so the pid and start time inside the file are
informational only.  A wedged holder is found with `fuser -v .local/board-tick.lock`; `--wait S`
retries for a bounded time instead of killing it.

Usage:
    tools/board-tick.py                 # full tick: publish, commit, gate, push
    tools/board-tick.py --no-push       # stop after the commit
    tools/board-tick.py --dry-run       # render only, print the would-be board path
    tools/board-tick.py --needs-summary # print the count of stale row summaries; no lock, no tick

Every invocation except `--needs-summary` appends one JSON line to `.local/board-tick.jsonl`:
`{at, pid, outcome, model_calls, summaries_written, rows_changed, census_stamp, board_sha}`.
`model_calls` is 0 by construction (this script calls no model) and `rows_changed` is the stale
summary count, so the caller knows whether a model is needed at all.

Stdlib only.  The sibling tools are run as subprocesses, never imported.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOLS = REPO / "tools"
LOCK = REPO / ".local" / "board-tick.lock"
LEDGER = REPO / ".local" / "board-tick.jsonl"
EVIDENCE = REPO / ".local" / "board-evidence"
BOARD = REPO / "mad-science" / "STATUS.md"
REGISTER = "mad-science/queue.json"

#: A publish refusal that means a peer moved the board, not that the render is defective.
PEER_MARKERS = ("carries board sha256", "on disk is sha256", "on disk carries",
                "peer wrote after read", "peer published")


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def board_bytes() -> bytes:
    try:
        return BOARD.read_bytes()
    except FileNotFoundError:
        return b""


def tool(name: str, *args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-B", str(TOOLS / name), *args],
                          input=stdin, capture_output=True, cwd=REPO)


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True)


def ledger(outcome: str, *, rows: int, census_stamp: str | None) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    record = {"at": iso_now(), "pid": os.getpid(), "outcome": outcome, "model_calls": 0,
              "summaries_written": 0, "rows_changed": rows, "census_stamp": census_stamp,
              "board_sha": sha256(board_bytes()) if BOARD.exists() else None}
    with open(LEDGER, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def stale_ids() -> list[str]:
    proc = tool("task-queue.py", "render", "--board", "--stale")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode(errors="replace").strip() or "render --stale failed")
    return [line for line in proc.stdout.decode(errors="replace").splitlines() if line.strip()]


def previous_evidence() -> Path | None:
    names = sorted(p.name for p in EVIDENCE.glob("*.json")) if EVIDENCE.is_dir() else []
    return EVIDENCE / names[-1] if names else None


def remote_board_sha() -> str:
    """sha256 of the board at origin/main, or `(absent)` — the value publish compares against."""
    git("fetch", "--quiet", "origin", "main")
    show = git("show", "origin/main:mad-science/STATUS.md")
    if show.returncode != 0:
        return "(absent)"
    return sha256(show.stdout)


def try_lock(handle, wait: float) -> bool:
    deadline = time.monotonic() + wait
    while True:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.5)


def holder(handle) -> str:
    handle.seek(0)
    raw = handle.read()
    try:
        data = json.loads(raw)
        return f"pid {data.get('pid', '?')}, started {data.get('at', '?')}"
    except (ValueError, AttributeError):
        return "holder unknown (unreadable lock file)"


def fail(step: str, proc: subprocess.CompletedProcess, rows: int,
         census_stamp: str | None) -> int:
    ledger(f"failed:{step}", rows=rows, census_stamp=census_stamp)
    sys.stderr.write(proc.stderr.decode(errors="replace"))
    return 1


def tick(args) -> int:
    rows = len(stale_ids())
    census_stamp: str | None = None
    previous = previous_evidence()  # before the census writes this tick's file

    proc = tool("board-census.py", "--out", str(EVIDENCE))
    if proc.returncode != 0:
        return fail("census", proc, rows, census_stamp)
    lines = proc.stdout.decode(errors="replace").split()
    evidence = Path(lines[-1]) if lines else None
    if evidence is None or not evidence.is_file():
        sys.stderr.write("board-tick: census wrote no evidence file\n")
        ledger("failed:census", rows=rows, census_stamp=None)
        return 1
    census_stamp = evidence.stem

    workdir = Path(tempfile.mkdtemp(prefix="board-tick-", dir=str(REPO / ".local")))
    try:
        rendered = workdir / "board.md"
        render_args = ["--evidence", str(evidence), "--register", REGISTER,
                       "--repo", str(REPO), "--out", str(rendered)]
        if previous is not None:
            render_args[2:2] = ["--prev", str(previous)]
        proc = tool("board-render.py", *render_args)
        if proc.returncode != 0:
            return fail("render", proc, rows, census_stamp)

        if args.dry_run:
            ledger("dry-run", rows=rows, census_stamp=census_stamp)
            print(f"board-tick: dry run, would publish {rendered}")
            return 0

        read = board_bytes()
        base = workdir / "base.md"
        base.write_bytes(read)
        proc = tool("task-queue.py", "publish", "--board", str(BOARD),
                    "--base", str(base), "--expect-sha", sha256(read),
                    "--expect-remote-sha", remote_board_sha(), "--remote-ref", "origin/main",
                    stdin=rendered.read_bytes())
        if proc.returncode != 0:
            stderr = proc.stderr.decode(errors="replace")
            peer = proc.returncode == 3 or (proc.returncode == 1
                                            and any(m in stderr for m in PEER_MARKERS))
            if peer:
                ledger("refused:peer", rows=rows, census_stamp=census_stamp)
                print(f"board-tick: refused:peer — {stderr.strip().splitlines()[-1][:200]}")
                return 0
            return fail("publish", proc, rows, census_stamp)

        if git("diff", "--quiet", "HEAD", "--", "mad-science/STATUS.md").returncode == 0:
            ledger("unchanged", rows=rows, census_stamp=census_stamp)
            print(f"board-tick: published {census_stamp}; board unchanged")
            return 0

        proc = git("commit", "-m", f"Refresh the status board: a {census_stamp} census",
                   "--", "mad-science/STATUS.md")
        if proc.returncode != 0:
            return fail("commit", proc, rows, census_stamp)

        if args.no_push:
            ledger("committed", rows=rows, census_stamp=census_stamp)
            print(f"board-tick: committed {census_stamp} (--no-push)")
            return 0

        proc = tool("push-gate.py")
        if proc.returncode != 0:
            return fail("gate", proc, rows, census_stamp)

        proc = git("push", "origin", "HEAD:main")
        if proc.returncode != 0:
            return fail("push", proc, rows, census_stamp)

        ledger("published", rows=rows, census_stamp=census_stamp)
        print(f"board-tick: published {census_stamp} (rows changed: {rows})")
        return 0
    finally:
        if not args.dry_run:
            shutil.rmtree(workdir, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One status-board tick: render, publish, push.")
    parser.add_argument("--wait", type=float, default=0.0,
                        help="seconds to wait for the tick lock before skipping (default 0)")
    parser.add_argument("--no-push", action="store_true", help="stop after the commit")
    parser.add_argument("--dry-run", action="store_true",
                        help="render only and print the would-be board path")
    parser.add_argument("--needs-summary", action="store_true",
                        help="print the count of stale row summaries; take no lock, do nothing else")
    args = parser.parse_args(argv)

    if args.needs_summary:
        try:
            print(len(stale_ids()))
        except RuntimeError as exc:
            print(f"board-tick: {exc}", file=sys.stderr)
            return 1
        return 0

    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK, "a+", encoding="utf-8") as handle:
        if not try_lock(handle, args.wait):
            print(f"board-tick: another tick holds {LOCK.relative_to(REPO)} "
                  f"({holder(handle)}); skipped")
            ledger("skipped:busy", rows=0, census_stamp=None)
            return 0
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps({"pid": os.getpid(), "at": iso_now()}) + "\n")
        handle.flush()
        return tick(args)


if __name__ == "__main__":
    sys.exit(main())
