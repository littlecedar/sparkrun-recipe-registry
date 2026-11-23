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
    tools/board-tick.py --dry-run       # render only, print the would-be board path (bypasses the gate)
    tools/board-tick.py --needs-summary # print the count of stale row summaries; no lock, no tick
    tools/board-tick.py --force         # run even when the gate says the fleet is idle

The gate (owner direction 2026-11-22) is what makes a short timer affordable: the tick runs only
when a Mad Science session is running (a declared window, or a live lease in the fleet ledger) or
when a path that feeds a board cell changed since the last board commit. Otherwise it writes
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

#: The tracked paths whose change feeds a board cell: the lanes' recipes and docs, the mods, the
#: tools that derive every cell, the benchmark profiles, the campaign, and the register. A commit
#: touching only `.idea/` or an unrelated doc changes nothing the board says, so it earns no tick.
BOARD_INPUTS = ("recipes", "mods", "tools", "benchmarking", "campaign", REGISTER)

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


#: Where the register `origin/main` has is materialised: `.local/` is git-ignored, so the board
#: renders origin's rows without touching a tracked file.
REGISTER_ORIGIN = REPO / ".local" / "board-register.json"


def fetch_origin() -> str:
    """Fetch `origin` and name the ref the gate and the render read: `origin/main`, else HEAD.

    A syncthing checkout is routinely behind origin: on 2026-11-23 this clone sat 23 commits back
    and every fire wrote `skipped:idle`, because the gate compared the last *local* board commit
    with the *local* HEAD and the renderer read the *worktree* register — so commits that landed
    on origin were invisible to both. A failed fetch is not fatal: the tick falls back to the ref
    it already has and says so, because a network blip must not stop a board that is otherwise
    publishable.
    """
    proc = git("fetch", "--quiet", "origin", "main")
    if proc.returncode != 0:
        sys.stderr.write("board-tick: git fetch origin main failed; using the last fetched "
                         "origin/main\n")
    if git("rev-parse", "--verify", "--quiet", "origin/main").returncode != 0:
        return "HEAD"
    return "origin/main"


def materialize_register(ref: str) -> Path:
    """The register as `ref` has it, written under `.local/`, so the board renders origin's rows.

    `git show` is content-only: the worktree register is never read or written, so a stale shared
    clone cannot describe itself as the fleet's register.
    """
    proc = git("show", f"{ref}:{REGISTER}")
    if proc.returncode != 0 or not proc.stdout.strip():
        sys.stderr.write(f"board-tick: {ref}:{REGISTER} unreadable; falling back to the worktree "
                         f"register\n")
        return REPO / REGISTER
    REGISTER_ORIGIN.parent.mkdir(parents=True, exist_ok=True)
    REGISTER_ORIGIN.write_bytes(proc.stdout)
    return REGISTER_ORIGIN


def reconcile() -> subprocess.CompletedProcess | None:
    """Merge `origin/main` into HEAD when the branch has diverged; None when it has not.

    A syncthing replica accumulates its own board commits while peers push: measured 2026-11-23
    the clone was 7 ahead / 35 behind, so every tick rendered a fresh board and then died at
    `push` — four `failed:push` ledger lines and a board that never moved, while the gate worked.
    The local-only commits are the tick's own board commits, so a merge is the honest join; it
    never resets, rebases or forces.

    A conflict confined to `mad-science/STATUS.md` is resolvable here: that file is the tick's own
    output and is rewritten moments later, so origin's copy is taken and the merge committed. Any
    other conflicted path is somebody's work — the merge is aborted and the failure reported with
    the paths named.
    """
    if git("merge-base", "--is-ancestor", "origin/main", "HEAD").returncode == 0:
        return None
    proc = git("merge", "--no-edit", "origin/main")
    if proc.returncode == 0:
        return proc
    board = str(BOARD.relative_to(REPO))
    conflicts = [line.strip() for line in
                 git("diff", "--name-only", "--diff-filter=U").stdout.decode(errors="replace")
                 .splitlines() if line.strip()]
    if conflicts and set(conflicts) == {board}:
        git("checkout", "--theirs", "--", board)
        git("add", "--", board)
        committed = git("commit", "--no-edit")
        if committed.returncode == 0:
            return committed
    git("merge", "--abort")     # leave the tree as it was; nothing half-merged
    return proc



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


def last_board_commit(ref: str = "HEAD") -> str:
    """The commit that last wrote the board on `ref` — the tick's own capture point."""
    proc = git("log", "-1", "--format=%H", ref, "--", str(BOARD.relative_to(REPO)))
    out = proc.stdout.decode(errors="replace").strip()
    return out if proc.returncode == 0 and out else ""


def relevant_change(ref: str = "HEAD") -> str:
    """The first board-input path changed on `ref` since the last board commit there, or ""."""
    base = last_board_commit(ref)
    if not base:
        return "no board commit yet"
    proc = git("diff", "--name-only", f"{base}..{ref}", "--", *BOARD_INPUTS)
    if proc.returncode != 0:
        return ""           # a git failure is not a change; the tick's own gates still apply
    for line in proc.stdout.decode(errors="replace").splitlines():
        if line.strip():
            return line.strip()
    return ""


def gate(ref: str = "HEAD") -> str:
    """Why this tick should run, or "" when it should not (pure decision, no side effects).

    Owner direction 2026-11-22: the board updates and ships a commit only when a Mad Science
    session is running **or** something that feeds a board cell changed since the last tick. The
    change half is read from `ref` — `origin/main` on a live fleet — because this clone is a
    syncthing replica: measured 2026-11-23, 23 commits landed on origin while every fire compared
    the local board commit with the local HEAD and wrote `skipped:idle`. `--force` overrides it.
    """
    mark = session_mark()
    if mark:
        return f"session: {mark}"
    change = relevant_change(ref)
    if change:
        return f"changed on {ref}: {change}"
    return ""


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
    ref = fetch_origin()
    why = "forced" if (args.force or args.dry_run) else gate(ref)
    if not why:
        ledger("skipped:idle", rows=0, census_stamp=None)
        print("board-tick: skipped — no session mark and no board input changed on "
              f"{ref} since the last board commit there")
        return 0
    print(f"board-tick: running ({why})")
    if not args.dry_run:
        merged = reconcile()
        if merged is not None:
            stderr = merged.stderr.decode(errors="replace")
            if merged.returncode != 0 and "would be overwritten" in stderr:
                # A peer's uncommitted change sits in a path origin also changed. That is not the
                # tick's failure and not ours to clear: say whose it is and retry next fire.
                dirty = [line.strip() for line in stderr.splitlines() if line.startswith("\t")]
                print("board-tick: skipped — a peer's uncommitted change blocks the merge "
                      f"({', '.join(dirty) or 'see git status'}); nothing published")
                ledger("skipped:dirty", rows=0, census_stamp=None)
                return 0
            if merged.returncode != 0:
                return fail("merge", merged, 0, None)
            print("board-tick: merged origin/main (the branch had diverged)")
    register = materialize_register(ref)
    rows = len(stale_ids(register))
    census_stamp: str | None = None
    previous = previous_evidence()  # before the census writes this tick's file

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
    parser.add_argument("--force", action="store_true",
                        help="run even when no session mark exists and no board input changed")
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
