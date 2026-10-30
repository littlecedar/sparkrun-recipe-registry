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

Exit codes: 0 ok, 1 data/validation error (message on stderr), 2 usage error (argparse).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

DEFAULT_QUEUE = Path("mad-science/queue.json")
STATES = ("queued", "running", "blocked", "done")
NODE_COSTS = ("", "single", "quartet")
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
        "provenance": args.provenance or "", "claimed_by": "", "claimed_at": "",
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
    tasks = validate(data)
    task = _find(tasks, args.id)
    flips = {"state": args.state, "title": args.title, "model": args.model,
             "node_cost": args.node_cost, "notes": args.notes, "provenance": args.provenance}
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


def cmd_render(args, path: Path) -> None:
    data = load(path)
    ordered = ordering(data)
    tasks = {t["id"]: t for t in data["tasks"]}
    tiers = _tiers(data["priority_models"])
    print("| Tier | Weight | Est (h) | Blocked (h) | State | Model | Node | Task |")
    print("|---|---|---|---|---|---|---|---|")
    for tier, task in enumerate_tasks_with_tier(ordered, tiers):
        weight, blocked = compute_weight(task, list(tasks.values()))
        print(f"| {tier} | {weight:.2f} | {task['estimate_h']:.2f} | {sum(blocked.values()):.2f} | "
              f"{task['state']} | {task['model'] or '—'} | {task['node_cost'] or '—'} | "
              f"**{task['id']}** — {task['title']} |")


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
    p_w = sub.add_parser("weight", help="explain one task's arithmetic")
    p_w.add_argument("--id", required=True)
    p_w.set_defaults(fn=cmd_weight)
    sub.add_parser("queue", help="print the ordered queue with computed weights").set_defaults(fn=cmd_queue)
    sub.add_parser("check", help="validate: ids, refs, cycles, estimates").set_defaults(fn=cmd_check)

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