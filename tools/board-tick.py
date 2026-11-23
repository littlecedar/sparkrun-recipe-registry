#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""One status-board tick: lock, census, render, publish, commit, push.

Why this exists.  The hourly tick used to be a model session composing `mad-science/STATUS.md` by
hand: 22 sessions on 2026-11-21 read 4.61 M context tokens to write one census row, and three
concurrent ticks at 03:00 choked the model because the `/tmp` pid-lock could not tell several
timers apart.  Every cell of the board is now derived (`board-census.py` + `board-render.py`), so a
tick is this script; a model is invoked only when a register row has no fresh summary.

Single-flight is one `flock(LOCK_EX|LOCK_NB)` on `.local/board-tick.lock`, held across collect ->
render -> publish -> commit -> push.  No stale-lock policy exists and none is needed: the
kernel drops a flock when the holder exits, so the pid and start time inside the file are
informational only.  A wedged holder is found with `fuser -v .local/board-tick.lock`; `--wait S`
retries for a bounded time instead of killing it.

The tick reads the live register from the worktree (`mad-science/queue.json` on disk), not from
`origin/main`.  The worktree has the uncommitted claims and running tasks that are the correct
state to render.  Only `mad-science/STATUS.md` is committed; the register is never touched.

Usage:
    tools/board-tick.py                 # full tick: publish, commit, push
    tools/board-tick.py --no-push       # stop after the commit
    tools/board-tick.py --dry-run       # render only, print the would-be board path (bypasses the gate)
    tools/board-tick.py --needs-summary # print the count of stale row summaries; no lock, no tick
    tools/board-tick.py --force         # run even when the gate says the register is unchanged

The gate (owner direction 2026-11-22) is what makes a short timer affordable: the tick runs only
when a Mad Science session is running (a declared window, or a live lease in the fleet ledger) or
the worktree register's sha256 changed since the last evidence file.  Otherwise it writes
`skipped:idle` to the ledger and exits 0 without a census, a render, a publish or a commit.

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
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOLS = REPO / "tools"
LOCK = REPO / ".local" / "board-tick.lock"
LEDGER = REPO / ".local" / "board-tick.jsonl"
EVIDENCE = REPO / ".local" / "board-evidence"
BOARD = REPO / "mad-science" / "STATUS.md"
REGISTER = "mad-science/queue.json"

#: A Mad Science session's own marks, both already read by the campaign and `queue-drip.py`: a
#: declared window, or a live lease in the fleet ledger. No new marker is invented here.
WINDOW_LOCKS = (REPO / ".local" / "fleet-window.lock", REPO / ".scratch" / "fleet-window.lock")
LEASES = REPO / ".local" / "fleet-leases.json"


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


def stale_ids(register: Path) -> list[str]:
    proc = tool("task-queue.py", "--file", str(register), "render", "--board", "--stale")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode(errors="replace").strip() or "render --stale failed")
    return [line for line in proc.stdout.decode(errors="replace").splitlines() if line.strip()]


def previous_evidence() -> Path | None:
    names = sorted(p.name for p in EVIDENCE.glob("*.json")) if EVIDENCE.is_dir() else []
    return EVIDENCE / names[-1] if names else None


def live_lease(now: float | None = None) -> str:
    """The holder of the first unexpired lease in the fleet ledger, or "" (read-only)."""
    try:
        data = json.loads(LEASES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    stamp = time.time() if now is None else now
    for lease in data.get("leases") or []:
        try:
            if float(lease.get("expires_at") or 0) > stamp:
                return str(lease.get("holder") or lease.get("id") or "an unnamed holder")
        except (AttributeError, TypeError, ValueError):
            continue
    return ""


def session_mark() -> str:
    """Why a Mad Science session counts as running, or "" — a declared window or a live lease.

    Both are the repo's own mechanisms (`campaign/sparkrun_campaign/leases.py`): a window lock is
    a session's hands-off declaration and a live lease is a boot it holds. Nothing new is invented.
    """
    for path in WINDOW_LOCKS:
        if path.is_file():
            return f"declared window {path.relative_to(REPO)}"
    holder = live_lease()
    return f"live lease held by {holder}" if holder else ""


def register_snapshot() -> dict | None:
    """sha256 and state counts of the worktree register, or None if unreadable."""
    path = REPO / REGISTER
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return {"sha256": sha256(raw), "error": "invalid JSON"}
    tasks = [t for t in data.get("tasks") or [] if isinstance(t, dict)]
    counts = Counter(t.get("state") for t in tasks)
    return {"sha256": sha256(raw), "tasks": len(tasks),
            "done": counts.get("done", 0), "queued": counts.get("queued", 0),
            "blocked": counts.get("blocked", 0), "running": counts.get("running", 0),
            "scheduled": counts.get("scheduled", 0), "ask": counts.get("ask", 0)}


def gate() -> str:
    """Why this tick should run, or "" when it should not (pure decision, no side effects).

    Owner direction 2026-11-22: the board updates and ships a commit only when a Mad Science
    session is running **or** the worktree register changed since the last evidence file.
    `--force` overrides it.
    """
    mark = session_mark()
    if mark:
        return f"session: {mark}"
    previous = previous_evidence()
    if previous is None:
        return "no previous evidence"
    try:
        prev = json.loads(previous.read_text(encoding="utf-8"))
        prev_reg = prev.get("register") or {}
    except (OSError, ValueError):
        return "previous evidence unreadable"
    current = register_snapshot()
    if current is None:
        return "register unreadable"
    if current.get("sha256") != prev_reg.get("sha256"):
        return "register changed since the last evidence"
    return ""


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
    why = "forced" if (args.force or args.dry_run) else gate()
    if not why:
        ledger("skipped:idle", rows=0, census_stamp=None)
        print("board-tick: skipped — no session mark and no register change since the last "
              "evidence")
        return 0
    print(f"board-tick: running ({why})")

    register = REPO / REGISTER   # the live worktree register
    rows = len(stale_ids(register))
    census_stamp: str | None = None
    previous = previous_evidence()   # before the census writes this tick's file

    proc = tool("board-census.py", "--out", str(EVIDENCE), "--register", str(register))
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
        render_args = ["--evidence", str(evidence), "--register", str(register),
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

        # Write the board directly (flock guarantees single-writer safety).
        BOARD.write_bytes(rendered.read_bytes())

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
            stderr = proc.stderr.decode(errors="replace")
            if "non-fast-forward" in stderr or "fetch first" in stderr:
                ledger("failed:push", rows=rows, census_stamp=census_stamp)
                print(f"board-tick: failed:push — {stderr.strip().splitlines()[-1][:200]}")
                return 0
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
    parser.add_argument("--force", action="store_true",
                        help="run even when no session mark exists and the register is unchanged")
    args = parser.parse_args(argv)

    if args.needs_summary:
        try:
            # Summary duty asks about the register this session can *write* (the worktree copy):
            # the model fills it with `task-queue.py summarize`, and counting origin's copy would
            # re-report the same rows every hour until someone pushed them. The render still
            # describes origin, so a locally-written summary reaches the board when it is pushed.
            print(len(stale_ids(REPO / REGISTER)))
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