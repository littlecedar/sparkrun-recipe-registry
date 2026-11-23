#!/usr/bin/env python3
"""Dispatch session/code work from the register — the half of queue mode that has no fleet.

`campaign/` dispatches rows that carry `recipe` + `tp` (a boot). The register also carries rows a
session can do with no fleet at all, and those had no dispatcher: they sat `queued` while a human
read the board. This is that dispatcher, and it is a *tools/* script on purpose — it only shells out
to `tools/task-queue.py`, so it needs no campaign package, no `uv --project campaign` environment and
no import path: the register's own CLI is the whole interface.

Protocol (`mad-science/QUEUE.md` §States and transitions, design `campaign/DESIGN.md`
§"Session/code director"):

  queued --(this script: --state scheduled --scheduled-by session-director:<name>)--> scheduled
  scheduled --(a worker session: --state running --claimed-by <session>)--> running
  running --(the worker: done with a receipt, queued with a reason, blocked on the row that is now
            the work)--> done | queued | blocked

Never: boot anything, take a lease, touch a `running` row, open a `blocked` row, answer an `ask`, or
rewrite a row's notes beyond the one line an expired assignment appends. Every write goes through the
tool, so a register the tool refuses is never written by this script either.

Usage:
    uv run python -B tools/session-director.py --once --dry-run
    uv run python -B tools/session-director.py --once --dispatcher-name worker-a
    uv run python -B tools/session-director.py --dispatcher-name worker-a --interval 60

Exit codes: 0 ok, 1 the register or a write failed (the message names the row), 2 usage.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from collections.abc import Callable
from typing import Any

DEFAULT_QUEUE = Path("mad-science/queue.json")
DEFAULT_TOOL = Path(__file__).resolve().parent / "task-queue.py"
DEFAULT_TIMEOUT_MIN = 30.0
PREFIX = "session-director"

Run = Callable[..., subprocess.CompletedProcess[str]]


class DirectorError(Exception):
    """A register or write failure; the message names the row."""

    exit_code = 1


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def stamp(moment: dt.datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_stamp(value: str) -> dt.datetime | None:
    """`2026-11-22T21:38:05Z` -> aware datetime; anything else -> None (a hand-edit defect)."""
    try:
        return dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.UTC)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- register reads

def read_rows(tool: Path, queue: Path, run: Run = subprocess.run) -> list[dict[str, Any]]:
    """`queue --json`: the register's own weighted, tiered ordering. Never re-derived here."""
    command = [sys.executable, "-B", str(tool), "--file", str(queue), "queue", "--json"]
    result = run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise DirectorError(f"{queue}: queue --json failed: "
                            f"{(result.stderr or '').strip()[:300]}")
    try:
        rows = json.loads(result.stdout)
    except ValueError as exc:
        raise DirectorError(f"{queue}: queue --json is not JSON: {exc}") from exc
    if not isinstance(rows, list):
        raise DirectorError(f"{queue}: queue --json is not a list of tasks")
    return rows


def _lane_of(row: dict[str, Any]) -> str:
    """The lane a row's provenance names, or "".

    Rows have no `lane` field: the lane is a directory in `provenance` (`recipes/ds4/README.md:3064`)
    and nothing else is a reliable key, so `--lane` is a filter on exactly that spelling.
    """
    provenance = str(row.get("provenance", ""))
    marker = "recipes/"
    if marker not in provenance:
        return ""
    tail = provenance.split(marker, 1)[1]
    return tail.split("/", 1)[0].strip()


def select(rows: list[dict[str, Any]], *, lanes: tuple[str, ...] = (),
           models: tuple[str, ...] = (), states: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """The rows this dispatcher may take, in the register's order (pure).

    `states` maps id -> state so a caller can pass the register's own view; it defaults to the
    states the rows themselves carry, which is what `queue --json` gives.
    """
    state_of = dict(states or {})
    for row in rows:
        state_of.setdefault(str(row.get("id")), str(row.get("state", "")))
    wanted_models = {m.strip().lower() for m in models if m.strip()}
    wanted_lanes = {lane.strip() for lane in lanes if lane.strip()}
    taken: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("state")) != "queued":
            continue                                  # scheduled/running/blocked/ask/done: not ours
        if row.get("recipe") is not None or row.get("tp") is not None:
            continue                                  # a fleet row is the campaign's
        # `queue --json` omits `done` rows, so a blocker absent from the list is done; a dangling
        # id cannot reach here (the tool refuses one), and a live blocker keeps the row `blocked`.
        if any(state_of.get(str(b), "done") != "done" for b in row.get("blocked_by", []) or []):
            continue
        if wanted_models and str(row.get("model", "")).strip().lower() not in wanted_models:
            continue
        if wanted_lanes and _lane_of(row) not in wanted_lanes:
            continue
        taken.append(row)
    return taken


def expired(rows: list[dict[str, Any]], timeout_min: float,
            at: dt.datetime | None = None) -> list[tuple[dict[str, Any], float]]:
    """`(row, age_minutes)` for every `scheduled` row older than the timeout (pure)."""
    moment = at or now_utc()
    out: list[tuple[dict[str, Any], float]] = []
    for row in rows:
        if str(row.get("state")) != "scheduled":
            continue
        since = parse_stamp(str(row.get("scheduled_at", "")))
        if since is None:
            continue                                  # the tool refuses a scheduled row with no stamp
        age = (moment - since).total_seconds() / 60.0
        if age > timeout_min:
            out.append((row, age))
    return out


# ---------------------------------------------------------------- register writes

def _call(tool: Path, queue: Path, *args: str, run: Run = subprocess.run) -> None:
    command = [sys.executable, "-B", str(tool), "--file", str(queue), *args]
    result = run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise DirectorError(f"{' '.join(args[:3])}: rc={result.returncode}: "
                            f"{(result.stderr or '').strip()[:300]}")


def _notes(row: dict[str, Any], line: str) -> str:
    """`--notes` replaces the cell, so the row's own text is carried forward."""
    current = str(row.get("notes", ""))
    return f"{current} — {line}" if current else line


def attempts(log_path: Path, row_id: str) -> int:
    """How many times this row has been handed out, from the dispatcher's own log."""
    if not log_path.exists():
        return 0
    seen = 0
    for line in log_path.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict) and entry.get("row") == row_id:
            seen += 1
    return seen


def assign(row: dict[str, Any], *, tool: Path, queue: Path, worker: str, log_path: Path,
           run: Run = subprocess.run, at: dt.datetime | None = None) -> dict[str, Any]:
    """Hand one queued row to `worker`: the tool write first, then the log line."""
    if str(row.get("state")) != "queued":
        raise DirectorError(f"{row.get('id')}: refusing to assign a {row.get('state')!r} row")
    moment = at or now_utc()
    _call(tool, queue, "update", "--id", str(row["id"]), "--state", "scheduled",
          "--scheduled-by", worker, run=run)
    entry = {"row": str(row["id"]), "worker": worker, "at": stamp(moment),
             "attempt": attempts(log_path, str(row["id"])) + 1}
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def release(row: dict[str, Any], *, tool: Path, queue: Path, timeout_min: float,
            run: Run = subprocess.run) -> None:
    """Return an expired assignment to `queued`, saying who had it and how long it sat."""
    if str(row.get("state")) != "scheduled":
        raise DirectorError(f"{row.get('id')}: refusing to expire a {row.get('state')!r} row")
    holder = str(row.get("scheduled_by", "")) or PREFIX
    _call(tool, queue, "update", "--id", str(row["id"]), "--state", "queued", "--notes",
          _notes(row, f"{PREFIX}: assignment expired after {timeout_min:g} min "
                      f"(scheduled_by {holder}); returned to queued"),
          run=run)


# ---------------------------------------------------------------- the tick

def tick(*, tool: Path, queue: Path, worker: str, log_path: Path, timeout_min: float,
         lanes: tuple[str, ...], models: tuple[str, ...], dry_run: bool, limit: int = 1,
         run: Run = subprocess.run, at: dt.datetime | None = None,
         out: Any = None) -> tuple[int, int]:
    """One pass: expire stale assignments, then hand out what is ready. Returns (assigned, expired)."""
    stream = out or sys.stdout
    moment = at or now_utc()
    rows = read_rows(tool, queue, run=run)
    released = 0
    for row, age in expired(rows, timeout_min, at=moment):
        if dry_run:
            print(f"dry-run: would expire {row['id']} (scheduled {age:.0f} min ago by "
                  f"{row.get('scheduled_by') or '?'})", file=stream)
            continue
        release(row, tool=tool, queue=queue, timeout_min=timeout_min, run=run)
        print(f"expired: {row['id']} (scheduled {age:.0f} min ago)", file=stream)
        released += 1
    if released:
        rows = read_rows(tool, queue, run=run)
    ready = select(rows, lanes=lanes, models=models)
    if limit > 0:
        ready = ready[:limit]
    assigned = 0
    for row in ready:
        if dry_run:
            print(f"dry-run: would assign {row['id']} -> {worker}", file=stream)
            continue
        entry = assign(row, tool=tool, queue=queue, worker=worker, log_path=log_path,
                       run=run, at=moment)
        print(f"assigned: {entry['row']} -> {worker} (attempt {entry['attempt']})", file=stream)
        assigned += 1
    if not ready:
        print(f"idle: no queued session row in scope", file=stream)
    return assigned, released


def main(argv: list[str] | None = None, *, run: Run = subprocess.run,
         out: Any = None, err: Any = None) -> int:
    ap = argparse.ArgumentParser(
        prog="session-director.py",
        description="Dispatch register rows that need no fleet: queued -> scheduled, and expire "
                    "assignments a dead worker never claimed.")
    ap.add_argument("--queue", default=str(DEFAULT_QUEUE),
                    help=f"register file (default {DEFAULT_QUEUE})")
    ap.add_argument("--tool", default=str(DEFAULT_TOOL), help="task-queue.py path")
    ap.add_argument("--dispatcher-name", default=os.environ.get("SESSION_DIRECTOR_NAME", ""),
                    help="who the assignment names (default $SESSION_DIRECTOR_NAME); the worker "
                         "that may claim these rows is 'session-director:<name>'")
    ap.add_argument("--assign-timeout", type=float, default=DEFAULT_TIMEOUT_MIN, metavar="MIN",
                    help=f"minutes a `scheduled` row may sit unclaimed (default "
                         f"{DEFAULT_TIMEOUT_MIN:g})")
    ap.add_argument("--lane", action="append", default=[], metavar="LANE",
                    help="only rows whose provenance names recipes/<LANE>/ (repeatable)")
    ap.add_argument("--model", action="append", default=[], metavar="TAG",
                    help="only rows carrying this model tag (repeatable)")
    ap.add_argument("--log-dir", default=".local/session-director",
                    help="where the JSONL assignment log lives (default .local/session-director)")
    ap.add_argument("--once", action="store_true", help="one tick and exit (default: loop)")
    ap.add_argument("--limit", type=int, default=1, metavar="N",
                    help="most rows one tick may hand out (default 1: the live path is one row, "
                         "so a dispatcher never mass-assigns work nobody is waiting for)")
    ap.add_argument("--interval", type=float, default=60.0, metavar="SEC",
                    help="seconds between ticks when looping (default 60)")
    ap.add_argument("--dry-run", action="store_true", help="print the selection, write nothing")
    args = ap.parse_args(argv)

    queue = Path(args.queue)
    tool = Path(args.tool)
    name = args.dispatcher_name.strip()
    if not name and not args.dry_run:
        print("session-director: --dispatcher-name (or $SESSION_DIRECTOR_NAME) names the worker "
              "these rows are assigned to; refusing to assign anonymously", file=err or sys.stderr)
        return 2
    worker = f"{PREFIX}:{name or 'unassigned'}"
    log_path = Path(args.log_dir) / f"{name}.jsonl"

    def one() -> int:
        tick(tool=tool, queue=queue, worker=worker, log_path=log_path,
             timeout_min=args.assign_timeout, lanes=tuple(args.lane),
             models=tuple(args.model), dry_run=args.dry_run, limit=args.limit, run=run,
             out=out or sys.stdout)
        return 0

    try:
        if args.once or args.dry_run:
            return one()
        import time
        while True:
            one()
            time.sleep(max(1.0, args.interval))
    except DirectorError as exc:
        print(f"session-director: {exc}", file=err or sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
