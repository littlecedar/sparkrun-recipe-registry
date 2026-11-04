#!/usr/bin/env python3
"""The registry's task queue: weigh tasks, compute what they block, order the queue.

Why this exists.  Owner policy (2026-10-26, verbatim; answered in `mad-science/GUIDANCE.md` §2/§4,
file since trimmed — the dated decisions live in `mad-science/TODO.md` §"Retry queue — window 4"):

    The amount of time something takes should only determine its position in the queue --
    heavier tasks (more time) sink lower in the queue.  Lighter tasks (less time) float to
    the top.  A task's weight is reduced by a value equal to the weight of tasks it blocks.
    This means that if a queue is 48 hours deep, a task that takes 24 hours at the bottom of
    the queue would be pushed to the top of the queue if it is blocking 24 hours worth of
    other tasks.

and, the standing override:

    DeepSeek-V4.1-Flash-1017 is our primary model at this time, with GLM-5.3 and GLM-5.3-Flash
    as our secondary models of interest.  Always prioritize unblocking and running items
    related to those models until told to do otherwise.

The protocol (schema, weight arithmetic, session protocol, the TODO.md relationship) is
`mad-science/QUEUE.md`; the queue data is `mad-science/queue.json` (tracked, JSON, human-diffable).

Weight.  ``weight = estimate_h - sum(estimate_h of every task this task transitively blocks)``.
Transitive on purpose: unblocking a task unblocks the whole chain behind it, so the credit is
the chain's total time, not just the direct dependents' (worked example in QUEUE.md).  Sort
ascending — lighter floats to the top — with tiering applied first: a task's `model` tag is
matched against `priority_models` (case-insensitive; a tier entry may be a string or a list of
equivalent tags, so `dsv4.1-1017` and `deepseek-v4.1-flash-1017` share tier 0); unmatched or
empty models fall to a trailing tier.  Within a tier, weight ascending, id ascending as the
deterministic tie-break.  `done` tasks drop out of the ordering entirely.

Everything fails closed: a cycle in `blocks`, a dangling id, a missing or non-numeric estimate,
a bad state, or an out-of-sync `blocked_by` mirror exits non-zero with the offending id — no
silent defaults anywhere.

Stdlib only.  Usage:

    uv run python -B tools/task-queue.py queue                 # the ordered queue
    uv run python -B tools/task-queue.py add --id X --title "..." --estimate-h 2 \
        --blocks A,B --model dsv4.1-1017 --node-cost quartet --provenance "TODO.md §ds4"
    uv run python -B tools/task-queue.py update --id X --estimate-h 3 --state running \
        --claimed-by <session>                                  # claim: stamps claimed_at
    uv run python -B tools/task-queue.py done --id X           # recompute on next read
    uv run python -B tools/task-queue.py block --id X          # manual external block (state flip)
    uv run python -B tools/task-queue.py unblock --id X        # back to queued
    uv run python -B tools/task-queue.py weight --id X         # one task's arithmetic
    uv run python -B tools/task-queue.py render                # markdown table for TODO/STATUS
    uv run python -B tools/task-queue.py render --board        # the STATUS.md `## Work queue` table
    uv run python -B tools/task-queue.py orphans               # TODO items with no live queue row
    uv run python -B tools/task-queue.py lint [FILE ...]       # markdown that will not render (default: the board)

Since 2026-11-03 the queue is the register and `mad-science/TODO.md` is a frozen archive
(`mad-science/QUEUE.md` §"Relationship to TODO.md").  `render --board` is what a board tick
copies, so the work queue is derived rather than re-typed, and `orphans` is the archive's fail-closed
half: it reads the `<!-- archive-frozen: <sha> -->` marker and reports only open items *added since*
that commit, so an item cannot quietly live in the archive instead of the register (a count bound was
rejected — removing one grandfathered item while adding another would net out).  `questions` prints
the open owner questions from the register's `questions` array.

Exit codes: 0 ok, 1 data/validation error (message on stderr), 2 usage error (argparse).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_QUEUE = Path("mad-science/queue.json")
DEFAULT_BOARD = Path("mad-science/STATUS.md")
STATES = ("queued", "running", "blocked", "done")
NODE_COSTS = ("", "single", "pair", "quartet")
REQUIRED_STR = ("id", "title", "model", "node_cost", "notes", "provenance")


class QueueError(Exception):
    """A fail-closed queue-data defect; the message names the offending task."""


# ---------------------------------------------------------------- loading / validation

def load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise QueueError(f"queue file not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise QueueError(f"queue file is not valid JSON: {path}: {exc}") from None
    if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
        raise QueueError(f"{path}: top level must be an object with a 'tasks' list")
    if not isinstance(data.get("priority_models"), list):
        raise QueueError(f"{path}: 'priority_models' must be a list of tiers")
    return data


def _tiers(priority_models: list) -> list[frozenset[str]]:
    tiers = []
    for i, entry in enumerate(priority_models):
        tags = entry if isinstance(entry, list) else [entry]
        if not tags or not all(isinstance(t, str) and t.strip() for t in tags):
            raise QueueError(f"priority_models[{i}] must be a tag string or a non-empty list of them")
        tiers.append(frozenset(t.strip().lower() for t in tags))
    return tiers


def tier_index(model: str, tiers: list[frozenset[str]]) -> int:
    tag = model.strip().lower()
    for i, tier in enumerate(tiers):
        if tag in tier:
            return i
    return len(tiers)


def derived_blocked_by(tasks: list[dict]) -> dict[str, set[str]]:
    """Structural mirror: id -> every task whose `blocks` names it, regardless of state."""
    mirror: dict[str, set[str]] = {}
    for task in tasks:
        for target in task["blocks"]:
            mirror.setdefault(target, set()).add(task["id"])
    return mirror


def validate(data: dict) -> list[dict]:
    """Fail closed: every defect exits with a message naming the task.  Returns tasks."""
    tasks = data["tasks"]
    seen: set[str] = set()
    for i, task in enumerate(tasks):
        where = f"tasks[{i}]"
        if not isinstance(task, dict):
            raise QueueError(f"{where}: not an object")
        tid = task.get("id")
        if not isinstance(tid, str) or not tid.strip():
            raise QueueError(f"{where}: 'id' must be a non-empty string")
        if tid in seen:
            raise QueueError(f"{tid}: duplicate id")
        seen.add(tid)
        for field in REQUIRED_STR:
            if not isinstance(task.get(field), str) or (field in ("id", "title") and not task[field].strip()):
                raise QueueError(f"{tid}: '{field}' must be a non-empty string"
                                 if field in ("id", "title") else f"{tid}: '{field}' must be a string")
        est = task.get("estimate_h")
        if est is None:
            raise QueueError(f"{tid}: 'estimate_h' is missing — every task states its cost")
        if isinstance(est, bool) or not isinstance(est, (int, float)):
            raise QueueError(f"{tid}: 'estimate_h' must be a number, got {est!r}")
        if est < 0:
            raise QueueError(f"{tid}: 'estimate_h' must be >= 0, got {est}")
        if task.get("state") not in STATES:
            raise QueueError(f"{tid}: 'state' must be one of {STATES}, got {task.get('state')!r}")
        if task.get("node_cost") not in NODE_COSTS:
            raise QueueError(f"{tid}: 'node_cost' must be one of {NODE_COSTS}, got {task.get('node_cost')!r}")
        evidence = task.get("evidence")
        if evidence is not None and not isinstance(evidence, str):
            raise QueueError(f"{tid}: 'evidence' must be a receipt path (string) when present")
        for field in ("blocks", "blocked_by"):
            value = task.get(field)
            if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                raise QueueError(f"{tid}: '{field}' must be a list of task ids")
        if task["state"] == "done" and (task.get("claimed_by") or task.get("claimed_at")):
            raise QueueError(f"{tid}: a done task cannot still carry claimed_by/claimed_at")

    known = seen
    for task in tasks:
        for field in ("blocks", "blocked_by"):
            for ref in task[field]:
                if ref not in known:
                    raise QueueError(f"{task['id']}: '{field}' references unknown id {ref!r} (dangling ref)")

    mirror = derived_blocked_by(tasks)
    for task in tasks:
        if set(task["blocked_by"]) != mirror.get(task["id"], set()):
            raise QueueError(f"{task['id']}: stored 'blocked_by' {sorted(task['blocked_by'])} does not match "
                             f"the derived mirror {sorted(mirror.get(task['id'], set()))} — rerun update")

    # Cycle detection over the `blocks` edges: a cycle has no well-defined weight ordering.
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {t["id"]: WHITE for t in tasks}
    edges = {t["id"]: t["blocks"] for t in tasks}

    def visit(node: str, stack: list[str]) -> None:
        color[node] = GRAY
        stack.append(node)
        for ref in edges[node]:
            if color[ref] == GRAY:
                cycle = stack[stack.index(ref):] + [ref]
                raise QueueError(f"cycle in 'blocks': {' -> '.join(cycle)}")
            if color[ref] == WHITE:
                visit(ref, stack)
        stack.pop()
        color[node] = BLACK

    for t in tasks:
        if color[t["id"]] == WHITE:
            visit(t["id"], [])

    # The owner-question register, when present: numbering only grows, and a row must name
    # what decides it.  A settled row leaves the array (it moves to the prose record), so
    # the array is the *open* set and `questions` can answer "what is waiting on the owner"
    # without reading the markdown.
    questions = data.get("questions")
    if questions is not None:
        if not isinstance(questions, list):
            raise QueueError("'questions' must be a list")
        last = 0
        for i, question in enumerate(questions):
            where = f"questions[{i}]"
            if not isinstance(question, dict):
                raise QueueError(f"{where}: not an object")
            qid = question.get("id")
            if isinstance(qid, bool) or not isinstance(qid, int) or qid <= 0:
                raise QueueError(f"{where}: 'id' must be a positive integer (never reused)")
            if qid <= last:
                raise QueueError(f"questions: id {qid} does not come after {last} — numbering only grows")
            last = qid
            for field in ("summary", "status", "provenance", "asked"):
                value = question.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise QueueError(f"questions#{qid}: '{field}' must be a non-empty string")
    return tasks


# ---------------------------------------------------------------- weight / ordering

def blocked_set(task_id: str, edges: dict[str, list[str]], done: set[str]) -> set[str]:
    """Every still-open task reachable from task_id through `blocks` edges (task_id excluded).

    A `done` task no longer blocks, so traversal stops there: its dependents are unblocked and
    neither the done task's estimate nor anything behind it counts as blocking credit.
    """
    seen: set[str] = set()
    frontier = list(edges[task_id])
    while frontier:
        node = frontier.pop()
        if node in seen or node in done:
            continue
        seen.add(node)
        frontier.extend(edges[node])
    return seen


def compute_weight(task: dict, tasks: list[dict]) -> tuple[float, dict[str, float]]:
    edges = {t["id"]: t["blocks"] for t in tasks}
    estimates = {t["id"]: t["estimate_h"] for t in tasks}
    done = {t["id"] for t in tasks if t["state"] == "done"}
    blocked = blocked_set(task["id"], edges, done)
    total = sum(estimates[b] for b in blocked)
    return task["estimate_h"] - total, {b: estimates[b] for b in sorted(blocked)}


def ordering(data: dict) -> list[dict]:
    tasks = validate(data)
    tiers = _tiers(data["priority_models"])
    rows = []
    for task in tasks:
        if task["state"] == "done":
            continue
        weight, _ = compute_weight(task, tasks)
        rows.append((tier_index(task["model"], tiers), weight, task["id"], task))
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    return [r[3] for r in rows]


# ---------------------------------------------------------------- commands

def _save(path: Path, data: dict, tasks: list[dict]) -> None:
    """Write the register atomically: tmp file, then `os.replace`.

    This file is syncthing-shared with a live second writer, and a torn write here does NOT read as
    corruption -- JSON stays syntactically valid while task rows silently vanish, which is the one
    failure mode nobody notices. `write_text` truncates first, so a sync in that window publishes a
    half file; rename is atomic on the same filesystem, so a reader (or syncthing) sees either the old
    register or the new one.
    """
    data["tasks"] = tasks
    body = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    try:
        tmp.write_text(body, encoding="utf-8")
        try:
            os.chmod(tmp, path.stat().st_mode & 0o777)  # keep the register's mode
        except OSError:
            pass
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


def _find(tasks: list[dict], task_id: str) -> dict:
    for t in tasks:
        if t["id"] == task_id:
            return t
    raise QueueError(f"{task_id}: no such task")


def cmd_add(args, path: Path) -> None:
    data = load(path)
    tasks = validate(data)
    if any(t["id"] == args.id for t in tasks):
        raise QueueError(f"{args.id}: id already exists")
    task = {
        "id": args.id, "title": args.title, "estimate_h": args.estimate_h,
        "blocks": args.blocks.split(",") if args.blocks else [],
        "blocked_by": [], "state": "queued", "model": args.model or "",
        "node_cost": args.node_cost or "", "notes": args.notes or "",
        "provenance": args.provenance or "",
        "evidence": getattr(args, "evidence", "") or "",
        "claimed_by": "", "claimed_at": "",
    }
    for b in (args.blocked_by.split(",") if args.blocked_by else []):
        _find(tasks, b)["blocks"].append(args.id)
    tasks.append(task)
    _relink(tasks)
    validate({"tasks": tasks, "priority_models": data["priority_models"]})
    _save(path, data, tasks)
    print(f"added {args.id} (weight recomputed on next `queue`)")


def _relink(tasks: list[dict]) -> None:
    mirror = derived_blocked_by(tasks)
    for t in tasks:
        t["blocked_by"] = sorted(mirror.get(t["id"], set()))


def cmd_update(args, path: Path) -> None:
    data = load(path)
    # Relink BEFORE validating: `blocked_by` is derived from `blocks`, so a register whose mirror
    # drifted (the state `check` reports as "rerun update") failed validation on the very line
    # before the repair, and every rerun died identically. Measured 2026-10-30: three attempts.
    tasks = data.get("tasks")
    if isinstance(tasks, list):
        _relink(tasks)
    tasks = validate(data)
    task = _find(tasks, args.id)
    flips = {"state": args.state, "title": args.title, "model": args.model,
             "node_cost": args.node_cost, "notes": args.notes, "provenance": args.provenance,
             "evidence": getattr(args, "evidence", None)}
    for field, value in flips.items():
        if value is not None:
            task[field] = value
    if args.estimate_h is not None:
        task["estimate_h"] = args.estimate_h
    if args.blocks is not None:
        task["blocks"] = args.blocks.split(",") if args.blocks else []
    if args.claimed_by is not None:
        task["claimed_by"] = args.claimed_by
        task["claimed_at"] = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if task["state"] == "done":
        task["claimed_by"] = task["claimed_at"] = ""
    _relink(tasks)
    validate(data)
    _save(path, data, tasks)
    print(f"updated {args.id}: state={task['state']} estimate_h={task['estimate_h']}")





def cmd_queue(args, path: Path) -> None:
    data = load(path)
    ordered = ordering(data)
    tasks = {t["id"]: t for t in data["tasks"]}
    tiers = _tiers(data["priority_models"])
    print(f"{'tier':<4} {'weight':>8} {'est_h':>6} {'blk_h':>7}  {'state':<8} {'model':<22} "
          f"{'node':<8} id — title")
    for tier, task in enumerate_tasks_with_tier(ordered, tiers):
        weight, blocked = compute_weight(task, list(tasks.values()))
        print(f"{tier:<4} {weight:>8.2f} {task['estimate_h']:>6.2f} {sum(blocked.values()):>7.2f}  "
              f"{task['state']:<8} {task['model'] or '-':<22} {task['node_cost'] or '-':<8} "
              f"{task['id']} — {task['title']}")


def enumerate_tasks_with_tier(ordered, tiers):
    for task in ordered:
        yield tier_index(task["model"], tiers), task


def cmd_questions(args, path: Path) -> None:
    """The open owner questions, from the register rather than the markdown."""
    data = load(path)
    validate(data)
    rows = data.get("questions") or []
    open_rows = [q for q in rows if not q["status"].startswith("answered")]
    print("| # | summary | status | provenance | asked |")
    print("|---|---|---|---|---|")
    for question in open_rows:
        print(f"| {question['id']} | {question['summary']} | {question['status']} "
              f"| {question['provenance']} | {question['asked']} |")
    print(f"{len(open_rows)} open of {len(rows)} question row(s); the prose record is "
          f"`mad-science/QUESTIONS.md` and `TODO.md` §\"Settled questions\"")


def cmd_weight(args, path: Path) -> None:
    data = load(path)
    tasks = validate(data)
    task = _find(tasks, args.id)
    weight, blocked = compute_weight(task, tasks)
    tiers = _tiers(data["priority_models"])
    ordered = ordering(data)
    position = next(i for i, t in enumerate(ordered, 1) if t["id"] == args.id)
    print(f"{args.id}: weight = estimate_h - sum(estimate_h of transitively blocked)")
    print(f"  estimate_h          = {task['estimate_h']:.2f}")
    if blocked:
        print(f"  transitively blocks ({len(blocked)} task(s)):")
        for bid, est in blocked.items():
            print(f"    {bid:<38} {est:>6.2f}")
        print(f"  blocked total       = {sum(blocked.values()):.2f}")
    else:
        print("  transitively blocks: nothing")
    print(f"  weight              = {weight:.2f}")
    print(f"  tier                = {tier_index(task['model'], tiers)} "
          f"(model {task['model'] or 'none'!r}; 0 = {list(tiers[0]) if tiers else 'n/a'})")
    print(f"  position in queue   = {position} of {len(ordered)} (ascending weight)")


def cmd_check(args, path: Path) -> None:
    data = load(path)
    tasks = validate(data)
    print(f"ok: {len(tasks)} task(s), priority_models={data['priority_models']}")


_TABLE_DELIM = re.compile(r"^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$")


def _table_cells(row: str) -> list[str]:
    """Split a table row the way GFM does: every unescaped `|` ends a cell.

    Deliberately blind to code spans — that is the trap, not an oversight: GFM
    splits the row before it parses inline markup, so a `|` written inside a
    code span still becomes a column break and the row renders ragged.
    """
    out: list[str] = []
    cur: list[str] = []
    i = 0
    while i < len(row):
        if row[i] == "\\" and i + 1 < len(row):
            cur.append(row[i:i + 2])
            i += 2
            continue
        if row[i] == "|":
            out.append("".join(cur))
            cur = []
        else:
            cur.append(row[i])
        i += 1
    out.append("".join(cur))
    if out and not out[0].strip():
        out.pop(0)
    if out and not out[-1].strip():
        out.pop()
    return out


def lint_markdown(text: str) -> list[tuple[int, str, str]]:
    """`(line, rule, detail)` for markdown that will not render as written.

    Fenced code is skipped. The rules are the defects a table actually dies of:
    a header with no delimiter row (GFM then renders every row as one paragraph
    of pipes — measured on `mad-science/STATUS.md`'s landed table, 2026-11-03),
    a row whose cell count disagrees with its header, a `|` inside a cell's code
    span, an odd backtick count in a cell, and a fence left open at EOF.
    """
    problems: list[tuple[int, str, str]] = []
    lines = text.split("\n")
    in_fence = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            i += 1
            continue
        if in_fence or not line.lstrip().startswith("|"):
            i += 1
            continue
        j = i
        while j < len(lines) and lines[j].lstrip().startswith("|"):
            j += 1
        block = lines[i:j]
        header = _table_cells(block[0])
        if len(block) < 2 or not _TABLE_DELIM.match(block[1]) or len(_table_cells(block[1])) != len(header):
            problems.append((i + 1, "table-missing-delimiter",
                             f"{len(block)} row(s) begin here but line {i + 2} is not a "
                             f"{len(header)}-column delimiter row (|---|---|); GFM renders the "
                             "whole block as one paragraph"))
        else:
            for k, row in enumerate(block[2:], start=i + 3):
                n = len(_table_cells(row))
                if n != len(header):
                    problems.append((k, "table-ragged", f"{n} cells, header has {len(header)}"))
        for k, row in enumerate(block, start=i + 1):
            bare = row.replace(r"\|", "\0")
            if any("|" in span for span in re.findall(r"`([^`]*)`", bare)):
                problems.append((k, "pipe-in-code-span",
                                 "a `|` inside a code span still splits the cell; escape it as \\|"))
            if any(cell.count("`") % 2 for cell in _table_cells(row)):
                problems.append((k, "unbalanced-backticks",
                                 "an odd number of ` in a cell renders literally"))
        i = j
    if in_fence:
        problems.append((len(lines), "unclosed-fence", "a ``` fence is never closed"))
    return problems


def _emit(lines: list[str], what: str) -> None:
    """Print generated markdown, refusing it if it will not render."""
    problems = lint_markdown("\n".join(lines))
    if problems:
        for line, rule, detail in problems:
            print(f"task-queue: {what}:{line}: {rule}: {detail}", file=sys.stderr)
        raise QueueError(f"refusing to emit {what}: {len(problems)} markdown problem(s) above")
    print("\n".join(lines))


def cmd_lint(args, path: Path) -> None:
    """Lint markdown files; the board is the default because it is hand-written."""
    paths = [Path(p) for p in (args.paths or [DEFAULT_BOARD])]
    total = 0
    for target in paths:
        try:
            problems = lint_markdown(target.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise QueueError(f"no such markdown file: {target}")
        for line, rule, detail in problems:
            print(f"{target}:{line}: {rule}: {detail}")
        total += len(problems)
    if total:
        raise QueueError(f"{total} markdown problem(s) in {len(paths)} file(s)")
    print(f"ok: {len(paths)} markdown file(s) render")


def cmd_render(args, path: Path) -> None:
    data = load(path)
    if getattr(args, "board", False):
        _emit(board_rows(data), "board table")
        return
    ordered = ordering(data)
    tasks = {t["id"]: t for t in data["tasks"]}
    tiers = _tiers(data["priority_models"])
    lines = ["| Tier | Weight | Est (h) | Blocked (h) | State | Model | Node | Task |",
             "|---|---|---|---|---|---|---|---|"]
    for tier, task in enumerate_tasks_with_tier(ordered, tiers):
        weight, blocked = compute_weight(task, list(tasks.values()))
        lines.append(
            f"| {tier} | {weight:.2f} | {task['estimate_h']:.2f} | {sum(blocked.values()):.2f} | "
            f"{task['state']} | {task['model'] or '—'} | {task['node_cost'] or '—'} | "
            f"**{task['id']}** — {_cell(task['title'])} |")
    _emit(lines, "weighted table")


def board_rows(data: dict) -> list[str]:
    """The STATUS.md `## Work queue` table, derived from the register.

    Columns are the board's own: job, node cost, holds, state.  `holds` is the task's
    `blocked_by` (what must clear first), and the state cell carries the task's notes,
    because that justification text IS the row's notes — a second copy in TODO.md is the
    drift this replaces, not a convenience.
    """
    ordered = ordering(data)
    tiers = _tiers(data["priority_models"])
    lines = ["| job | node cost | holds | state |", "|---|---|---|---|"]
    for _tier, task in enumerate_tasks_with_tier(ordered, tiers):
        state = task["state"]
        if task.get("notes"):
            state = f"{state} — {task['notes']}"
        if task.get("evidence"):
            state = f"{state} — evidence: `{task['evidence']}`"
        lines.append(f"| `{task['id']}` — {_cell(task['title'])} | {task['node_cost'] or '—'} "
                     f"| {_cell(', '.join(task['blocked_by']) or '—')} | {_cell(state)} |")
    return lines


def _cell(text: str) -> str:
    """One line, no cell breakers: notes are prose and carry newlines and pipes."""
    return " ".join(str(text).split()).replace("|", r"\|")


TODO_ITEM_RE = re.compile(r"^\s*- \[ \] \*\*(.+?)\*\*")
QUEUE_MARK_RE = re.compile(r"<!--\s*queue:\s*([A-Za-z0-9._-]+)\s*-->")
ARCHIVE_FROZEN_RE = re.compile(r"<!--\s*archive-frozen:\s*([0-9a-f]{7,40})\s*-->")


def todo_added_since(root: Path, todo: Path, rev: str) -> list[str]:
    """Text of every line added to `todo` since `rev`, as a synthetic document.

    The bound exists because the frozen archive keeps its pre-freeze items with no markers:
    scanning the whole file reports a wall of grandfathered orphans forever, which cannot
    gate anything.  `git diff --unified=0` answers the only question that matters — did a
    new open item land in the archive instead of the register?
    """
    proc = subprocess.run(["git", "-C", str(root), "diff", "--unified=0", rev, "--",
                           str(todo.relative_to(root))],
                          capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise QueueError(f"git diff {rev} -- {todo}: {proc.stderr.strip()[:200]}")
    return [line[1:] for line in proc.stdout.splitlines()
            if line.startswith("+") and not line.startswith("+++")]


def todo_orphans(text: str, tasks: list[dict], offset: int = 0) -> tuple[list[tuple[int, str]], list[tuple[int, str, str]]]:
    """`(line, title)` for open TODO items with no live marker; `(line, title, id)` for dead ones.

    Fail-closed in the direction that matters: an item counts as covered only by an explicit
    `<!-- queue: <id> -->` marker, on the item's line or the line after it, naming a task that
    exists.  A marker naming a dead id is reported separately — a renamed task must not
    silently orphan the text it used to cover.
    """
    known = {t["id"] for t in tasks}
    orphans: list[tuple[int, str]] = []
    dead: list[tuple[int, str, str]] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        match = TODO_ITEM_RE.match(line)
        if not match:
            continue
        marker = QUEUE_MARK_RE.search(line)
        if marker is None and i + 1 < len(lines):
            marker = QUEUE_MARK_RE.search(lines[i + 1])
        if marker is None:
            orphans.append((i + 1, match.group(1)))
        elif marker.group(1) not in known:
            dead.append((i + 1, match.group(1), marker.group(1)))
    return orphans, dead


def repo_root(path: Path) -> Path:
    proc = subprocess.run(["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise QueueError(f"not a git worktree: {path}")
    return Path(proc.stdout.strip())


def cmd_orphans(args, path: Path) -> None:
    data = load(path)
    tasks = validate(data)
    todo = Path(args.todo)
    try:
        text = todo.read_text(encoding="utf-8")
    except OSError as exc:
        raise QueueError(f"cannot read --todo {todo}: {exc}") from None
    since = getattr(args, "since", None)
    if since is None:
        marker = ARCHIVE_FROZEN_RE.search(text)
        since = marker.group(1) if marker else None
    if since:
        absolute = todo.resolve()
        text = "\n".join(todo_added_since(repo_root(absolute), absolute, since))
        allow = 0
    else:
        allow = max(0, getattr(args, "allow", 0))
    orphans, dead = todo_orphans(text, tasks)
    for line, title in orphans:
        print(f"{todo}:{line}: open item has no queue row — {title}")
    for line, title, ref in dead:
        print(f"{todo}:{line}: marker names unknown task {ref!r} — {title}")
    print(f"{todo}: {len(orphans)} orphan(s) (allowed {allow}), {len(dead)} dead marker(s), "
          f"{len(tasks)} task(s)")
    # The bound is the cutover: the archive carries its pre-freeze items with no marker, so the
    # gate is *growth*, not presence.  A dead marker always fails — a renamed task must not
    # silently orphan the text its old marker covered.
    if len(orphans) > allow or dead:
        raise QueueError(f"{todo}: {len(orphans)} orphan(s) exceeds the allowed {allow}" if dead == []
                         else f"{todo}: {len(dead)} marker(s) name an unknown task")


# ---------------------------------------------------------------- entry point

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="task-queue.py", description=__doc__.splitlines()[0])
    parser.add_argument("--file", default=str(DEFAULT_QUEUE), help=f"queue JSON (default {DEFAULT_QUEUE})")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="add a task")
    p_add.add_argument("--id", required=True)
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--estimate-h", type=float, required=True)
    p_add.add_argument("--blocks", default="", help="comma-separated ids this task blocks")
    p_add.add_argument("--model", default="")
    p_add.add_argument("--node-cost", default="")
    p_add.add_argument("--notes", default="")
    p_add.add_argument("--provenance", default="")
    p_add.add_argument("--evidence", default="", help="receipt path that proves the task landed")
    p_add.add_argument("--blocked-by", default="", help="comma-separated ids that block this task")
    p_add.set_defaults(fn=cmd_add)
    p_upd = sub.add_parser("update", help="update fields / claim (--claimed-by stamps claimed_at)")
    p_upd.add_argument("--id", required=True)
    p_upd.add_argument("--title")
    p_upd.add_argument("--estimate-h", type=float)
    p_upd.add_argument("--blocks", default=None, help="comma-separated ids this task blocks")
    p_upd.add_argument("--model")
    p_upd.add_argument("--node-cost")
    p_upd.add_argument("--notes")
    p_upd.add_argument("--provenance")
    p_upd.add_argument("--evidence", help="receipt path that proves the task landed")
    p_upd.add_argument("--claimed-by")
    p_upd.add_argument("--state", choices=STATES)
    p_upd.set_defaults(fn=cmd_update)
    for name, state in (("done", "done"), ("block", "blocked"), ("unblock", "queued")):
        p = sub.add_parser(name, help={"done": "mark done (drops out of the ordering)",
                                       "block": "flip state to blocked (external gate)",
                                       "unblock": "flip state back to queued"}[name])
        p.add_argument("--id", required=True)
        p.add_argument("--estimate-h", type=float)
        p.add_argument("--title")
        p.add_argument("--model")
        p.add_argument("--node-cost")
        p.add_argument("--notes")
        p.add_argument("--provenance")
        p.add_argument("--claimed-by")
        p.add_argument("--blocks", default=None, help="comma-separated ids this task blocks")
        p.set_defaults(fn=None, _fixed_state=state)
    sub.add_parser("render", help="markdown table for TODO/STATUS").set_defaults(fn=cmd_render)
    p_board = sub.choices["render"]
    p_board.add_argument("--board", action="store_true",
                         help="emit the STATUS.md `## Work queue` table instead of the weighted one")
    p_orph = sub.add_parser("orphans", help="open TODO items with no live queue row")
    p_orph.add_argument("--todo", default="mad-science/TODO.md", help="the archive to scan")
    p_orph.add_argument("--allow", type=int, default=0,
                        help="grandfathered orphans tolerated (the archive's frozen count, 52)")
    p_orph.add_argument("--since", default=None,
                        help="bound the scan at a rev: only items ADDED since it are orphans "
                             "(default: the archive-frozen marker in the file, else unbounded)")
    p_orph.set_defaults(fn=cmd_orphans)
    p_w = sub.add_parser("weight", help="explain one task's arithmetic")
    p_w.add_argument("--id", required=True)
    p_w.set_defaults(fn=cmd_weight)
    sub.add_parser("queue", help="print the ordered queue with computed weights").set_defaults(fn=cmd_queue)
    sub.add_parser("questions", help="open owner questions from the register").set_defaults(fn=cmd_questions)
    sub.add_parser("check", help="validate: ids, refs, cycles, estimates").set_defaults(fn=cmd_check)
    p_lint = sub.add_parser("lint", help="markdown that will not render (tables, fences)")
    p_lint.add_argument("paths", nargs="*", default=None,
                        help=f"markdown files (default {DEFAULT_BOARD})")
    p_lint.set_defaults(fn=cmd_lint)

    args = parser.parse_args(argv)
    path = Path(args.file)
    try:
        if getattr(args, "_fixed_state", None):
            args.state = args._fixed_state
            cmd_update(args, path)
        else:
            args.fn(args, path)
    except QueueError as exc:
        print(f"task-queue: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())