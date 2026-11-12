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
silent defaults anywhere.  A *bootable* row (the optional `recipe`/`tp`/`env` fields a scheduler
reads) is held to the same rule: the recipe must be a tracked `recipes/<lane>/<arm>.yaml` in the
register's checkout, `tp` must be 1/2/4 and agree with `node_cost`, and `env` must be an object of
strings.  A row without those fields is authoring, docs or analysis work and no scheduler may boot
it.

Stdlib only.  Usage:

    uv run python -B tools/task-queue.py queue                 # the ordered queue
    uv run python -B tools/task-queue.py queue --json          # same ordering, for a scheduler
    uv run python -B tools/task-queue.py add --id X --title "..." --estimate-h 2 \
        --blocks A,B --model dsv4.1-1017 --node-cost quartet --provenance "TODO.md §ds4"
    uv run python -B tools/task-queue.py add --id Y --title "..." --estimate-h 3 \
        --node-cost pair --recipe recipes/3d/zz-arm.yaml --tp 2 --env ARM_OPTS=--tag=d4
    uv run python -B tools/task-queue.py update --id X --estimate-h 3 --state running \
        --claimed-by <session>                                  # claim: stamps claimed_at
    uv run python -B tools/task-queue.py done --id X           # recompute on next read
    uv run python -B tools/task-queue.py block --id X          # manual external block (state flip)
    uv run python -B tools/task-queue.py unblock --id X        # back to queued
    uv run python -B tools/task-queue.py weight --id X         # one task's arithmetic
    uv run python -B tools/task-queue.py render                # markdown table for TODO/STATUS
    uv run python -B tools/task-queue.py render --board        # the STATUS.md `## Work queue` table
    uv run python -B tools/task-queue.py graph                 # fenced mermaid: the connected rows
    #   only rows taking part in an edge (plus the questions they reach); `--all` draws every
    #   open row
    uv run python -B tools/task-queue.py orphans               # TODO items with no live queue row
    uv run python -B tools/task-queue.py lint [FILE ...]       # markdown that will not render (default: the board)
    uv run python -B tools/task-queue.py publish < new-board   # write the board unless the one on disk is newer
    # `--expect-sha <hex>`: refuse when the disk board moved since the composition read it
    # (an in-place peer edit keeps the title, so the stamp comparison cannot see it)

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
import fcntl
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_QUEUE = Path("mad-science/queue.json")
DEFAULT_BOARD = Path("mad-science/STATUS.md")
STATES = ("queued", "running", "blocked", "done")
NODE_COSTS = ("", "single", "pair", "quartet")
REQUIRED_STR = ("id", "title", "model", "node_cost", "notes", "provenance")
#: The optional machine-runnable fields: a row that names a recipe and its node count can be
#: launched by a scheduler (a campaign reads `queue --json`); a row without them is authoring,
#: docs or analysis work that no scheduler may boot. Present means all of `recipe`/`tp`
#: (`env` defaults to empty), and `tp` must agree with `node_cost`.
COST_NODES = {"single": 1, "pair": 2, "quartet": 4}
TP_VALUES = (1, 2, 4)
#: `load` stamps the bytes it read here; `_save` compares it with the file before replacing it.
SNAPSHOT = "_loaded_sha256"
#: Named in a stale-write refusal: with a syncthing-shared tree, "which host read this" is the clue.
HOST = socket.gethostname()


class QueueError(Exception):
    """A fail-closed queue-data defect; the message names the offending task."""

    exit_code = 1


class PeerWriteInFlight(QueueError):
    """A peer wrote the board between this publisher's read and its write: merge, don't regenerate."""

    exit_code = 3


# ---------------------------------------------------------------- loading / validation

def load(path: Path) -> dict:
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise QueueError(f"queue file not found: {path}") from None
    except OSError as exc:
        raise QueueError(f"queue file cannot be read: {path}: {exc}") from exc
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QueueError(f"queue file is not valid JSON: {path}: {exc}") from None
    if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
        raise QueueError(f"{path}: top level must be an object with a 'tasks' list")
    if not isinstance(data.get("priority_models"), list):
        raise QueueError(f"{path}: 'priority_models' must be a list of tiers")
    # The bytes this command read, so `_save` can refuse to replace a register a peer rewrote since.
    data[SNAPSHOT] = hashlib.sha256(raw).hexdigest()
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


def parse_env(pairs: list[str]) -> dict[str, str]:
    """`["KEY=VALUE", ...]` -> object. A pair without `=` is a usage defect, never a silent drop."""
    out: dict[str, str] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key.strip():
            raise QueueError(f"--env expects KEY=VALUE, got {pair!r}")
        out[key.strip()] = value
    return out


def parse_hosts(value: str) -> list[str]:
    """`"node-a,node-b"` -> host list. Empty entries are a usage defect, never a silent drop.

    The entries must be spelled exactly as the director's `--hosts`, so this tool never normalises
    them: an exclusion that does not match is a silent no-op, which is worse than a refusal.
    """
    hosts = [host.strip() for host in value.split(",")]
    if not hosts or any(not host for host in hosts):
        raise QueueError(f"--exclude-hosts expects comma-separated hosts, got {value!r}")
    return hosts


def tracked_recipes(root: Path) -> set[str]:
    """Every tracked path under `recipes/` in the checkout at `root`."""
    proc = subprocess.run(["git", "-C", str(root), "ls-files", "--", "recipes"],
                          capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise QueueError(f"{root}: not a git checkout — a 'recipe' field must resolve to a tracked file")
    return set(proc.stdout.splitlines())


def _bootable(task: dict, root: Path | None, tracked: set[str] | None) -> None:
    """Validate the optional machine-runnable fields; absence means the row cannot be launched."""
    tid = task["id"]
    recipe, tp, env = task.get("recipe"), task.get("tp"), task.get("env")
    if recipe is None and tp is None and env is None:
        return
    if recipe is None:
        raise QueueError(f"{tid}: 'tp'/'env' without 'recipe' — a bootable row names the recipe it launches")
    if tp is None:
        raise QueueError(f"{tid}: 'recipe' without 'tp' — the scheduler will not guess a node count")
    if not isinstance(recipe, str) or not recipe.startswith("recipes/") or not recipe.endswith(".yaml"):
        raise QueueError(f"{tid}: 'recipe' must be a `recipes/<lane>/<arm>.yaml` path relative to the "
                         f"repo root, got {recipe!r}")
    if isinstance(tp, bool) or tp not in TP_VALUES:
        raise QueueError(f"{tid}: 'tp' must be one of {TP_VALUES}, got {tp!r}")
    nodes = COST_NODES.get(task.get("node_cost"))
    if nodes != tp:
        raise QueueError(f"{tid}: tp={tp} disagrees with node_cost={task.get('node_cost')!r} "
                         f"({nodes or 'no'} node(s))")
    if env is not None and (not isinstance(env, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in env.items()
    )):
        raise QueueError(f"{tid}: 'env' must be an object of string values, got {env!r}")
    if recipe not in (tracked if tracked is not None else tracked_recipes(root)):
        raise QueueError(f"{tid}: recipe {recipe} is not a tracked file under {root}")
    if not (root / recipe).is_file():
        raise QueueError(f"{tid}: recipe {recipe} is tracked but not in the worktree")


def validate(data: dict, path: Path | None = None) -> list[dict]:
    """Fail closed: every defect exits with a message naming the task.  Returns tasks.

    `path` is the register file: a row that names a `recipe` must resolve against the checkout that
    file lives in, so the scheduler-shaped fields are verified where they are read. Without it the
    tool's own checkout is the reference — a library caller handing over live register data gets
    the same resolution the CLI does, and only a register *outside* any worktree fails.
    """
    tasks = data["tasks"]
    seen: set[str] = set()
    root: Path | None = None
    tracked: set[str] | None = None
    resolved = False
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
        # Optional placement classification, read by the scheduler (campaign/plan.memory_risky):
        # tri-state on purpose -- absent is not `false`, so a row that never declared it keeps the
        # derivation from `node_cost` instead of silently claiming to be safe. The writer that
        # builds this register had no way to set it until 2026-11-10, which made the documented
        # `memory_risky: false` override unreachable; a bad hand-edit now fails here, not at lease.
        risky = task.get("memory_risky")
        if risky is not None and not isinstance(risky, bool):
            raise QueueError(f"{tid}: 'memory_risky' must be true or false when present, got {risky!r}")
        excluded = task.get("exclude_hosts")
        if excluded is not None and (not isinstance(excluded, list) or not all(
            isinstance(host, str) and host.strip() for host in excluded
        )):
            raise QueueError(f"{tid}: 'exclude_hosts' must be a list of host strings when present, "
                             f"got {excluded!r}")
        evidence = task.get("evidence")
        if evidence is not None and not isinstance(evidence, str):
            raise QueueError(f"{tid}: 'evidence' must be a receipt path (string) when present")
        for field in ("blocks", "blocked_by"):
            value = task.get(field)
            if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                raise QueueError(f"{tid}: '{field}' must be a list of task ids")
        if task["state"] != "running" and (task.get("claimed_by") or task.get("claimed_at")):
            # A claim is the running row's record, and nothing else's. A queued (or blocked, or
            # done) row that still carries one reads as another session's work and never runs, so
            # `update` clears the pair on every transition out of `running` and this refuses a
            # hand-edited file that skipped that.
            raise QueueError(f"{tid}: a claim exists only on a running row; state={task['state']!r} "
                             f"still carries claimed_by/claimed_at — rerun update")
        if not resolved and any(task.get(key) is not None for key in ("recipe", "tp", "env")):
            resolved = True
            root = repo_root(path if path is not None else Path(__file__).resolve())
            tracked = tracked_recipes(root)
        _bootable(task, root, tracked)

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


def ordering(data: dict, path: Path | None = None) -> list[dict]:
    tasks = validate(data, path)
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

def _save(path: Path, data: dict, tasks: list[dict], *, row: str = "") -> None:
    """Write the register atomically: compare-and-swap, then tmp file, then `os.replace`.

    This file is syncthing-shared with a live second writer, and a torn write here does NOT read as
    corruption -- JSON stays syntactically valid while task rows silently vanish, which is the one
    failure mode nobody notices. `write_text` truncates first, so a sync in that window publishes a
    half file; rename is atomic on the same filesystem, so a reader (or syncthing) sees either the old
    register or the new one.

    Atomic replace is not enough with a second writer: a command that read the register and then spent
    time on a ladder of `update` calls would replace the whole file from its stale snapshot, taking a
    peer's new row or claim with it (measured 2026-11-11: three machine-runnable fields reverted this
    way). So the bytes `load` read are compared with the file immediately before the replace; any
    difference is a peer write and this writer loses loudly, with nothing written.
    """
    snapshot = data.pop(SNAPSHOT, None)
    if snapshot is None:
        # Only a caller that never loaded the file: refuse rather than write without a comparison, so
        # the CAS cannot be skipped by accident (an internal misuse, not a queue-data defect).
        raise QueueError(f"{row or path}: refusing to save without the snapshot load() took")
    try:
        current = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise QueueError(f"{row or path}: cannot re-read {path} to check for a peer write: {exc}") from exc
    if current != snapshot:
        raise QueueError(
            f"{row}: {path} changed on disk since this command read it on {HOST} -- a peer wrote "
            "the register; nothing written. Re-read it and rerun; the peer's rows and claims are "
            "intact."
        )
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
    tasks = validate(data, path)
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
    if getattr(args, "recipe", None):
        task["recipe"] = args.recipe
    if getattr(args, "tp", None) is not None:
        task["tp"] = args.tp
    if getattr(args, "env", None):
        task["env"] = parse_env(args.env)
    if getattr(args, "memory_risky", None) is not None:
        task["memory_risky"] = bool(args.memory_risky)
    if getattr(args, "exclude_hosts", None) is not None:
        task["exclude_hosts"] = parse_hosts(args.exclude_hosts)
    for b in (args.blocked_by.split(",") if args.blocked_by else []):
        _find(tasks, b)["blocks"].append(args.id)
    tasks.append(task)
    _relink(tasks)
    validate({"tasks": tasks, "priority_models": data["priority_models"]}, path)
    _save(path, data, tasks, row=args.id)
    print(f"added {args.id} (weight recomputed on next `queue`)")


def _relink(tasks: list[dict]) -> None:
    mirror = derived_blocked_by(tasks)
    for t in tasks:
        t["blocked_by"] = sorted(mirror.get(t["id"], set()))


def _release_stale_claim(tasks: list[dict], task_id: str) -> None:
    """Clear a claim a non-running *target* row still carries, so `update` can repair it.

    The second instance of the relink defect: validation refuses a claim outside `running`, so a
    row a peer's pre-fix `update` left claimed failed on the line before its repair and the
    advertised repair (`rerun update`) was unreachable. Only the row `update` was asked about is
    excused; every other row stays fail-closed, and `check`/`queue` still refuse the file.
    """
    for task in tasks:
        if isinstance(task, dict) and task.get("id") == task_id and task.get("state") != "running":
            task["claimed_by"] = task["claimed_at"] = ""


def cmd_update(args, path: Path) -> None:
    data = load(path)
    # Relink BEFORE validating: `blocked_by` is derived from `blocks`, so a register whose mirror
    # drifted (the state `check` reports as "rerun update") failed validation on the very line
    # before the repair, and every rerun died identically. Measured 2026-10-30: three attempts.
    tasks = data.get("tasks")
    if isinstance(tasks, list):
        _relink(tasks)
        _release_stale_claim(tasks, args.id)
    tasks = validate(data, path)
    task = _find(tasks, args.id)
    flips = {"state": args.state, "title": args.title, "model": args.model,
             "node_cost": args.node_cost, "notes": args.notes, "provenance": args.provenance,
             "evidence": getattr(args, "evidence", None), "recipe": getattr(args, "recipe", None),
             "tp": getattr(args, "tp", None)}
    for field, value in flips.items():
        if value is not None:
            task[field] = value
    if getattr(args, "env", None):
        task["env"] = {**task.get("env", {}), **parse_env(args.env)}
    # None means "leave it": the flags are tri-state (`--memory-risky` / `--no-memory-risky`), and
    # an exclusion list is replaced wholesale because merging host lists has no obvious order.
    if getattr(args, "memory_risky", None) is not None:
        task["memory_risky"] = bool(args.memory_risky)
    if getattr(args, "exclude_hosts", None) is not None:
        task["exclude_hosts"] = parse_hosts(args.exclude_hosts)
    if args.estimate_h is not None:
        task["estimate_h"] = args.estimate_h
    if args.blocks is not None:
        task["blocks"] = args.blocks.split(",") if args.blocks else []
    if args.claimed_by is not None:
        if task["state"] != "running":
            raise QueueError(f"{args.id}: '--claimed-by' needs '--state running' — a claim exists "
                             f"only on a running row")
        task["claimed_by"] = args.claimed_by
        task["claimed_at"] = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if task["state"] != "running":
        # Every exit from `running` releases the claim: a stale one on a queued/blocked/done row
        # is exactly the drift that makes a scheduler skip its own work.
        task["claimed_by"] = task["claimed_at"] = ""
    _relink(tasks)
    validate(data, path)
    _save(path, data, tasks, row=args.id)
    print(f"updated {args.id}: state={task['state']} estimate_h={task['estimate_h']}")





def cmd_queue(args, path: Path) -> None:
    data = load(path)
    ordered = ordering(data, path)
    if getattr(args, "json", False):
        # The scheduler-shaped read: the same ordering, machine-readable, so a plan source
        # (the campaign director) never re-derives the weight arithmetic in a second place.
        print(json.dumps(ordered, indent=1, ensure_ascii=False))
        return
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
    validate(data, path)
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
    tasks = validate(data, path)
    task = _find(tasks, args.id)
    weight, blocked = compute_weight(task, tasks)
    tiers = _tiers(data["priority_models"])
    ordered = ordering(data, path)
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
    tasks = validate(data, path)
    print(f"ok: {len(tasks)} task(s), priority_models={data['priority_models']}")


_TABLE_DELIM = re.compile(r"^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$")
#: A tick that captures `graph` through a shell captures the harness's own stderr too: the
#: `--- stderr ---` banner and uv's `VIRTUAL_ENV` warning then sit between two blocks as prose.
#: Measured 2026-11-09 12:10-12:12 ET: publish exited 0 and lint said `ok` on both, and the
#: banner reached the clone's board, so neither door looked at a line that is not markdown.
HARNESS_ECHO = re.compile(r"^--- stderr ---\s*$|^warning:.*\bVIRTUAL_ENV\b")


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
    span, an odd backtick count in a cell, and a fence left open at EOF.  A harness
    transcript line outside a fence is the same class: it renders as prose between blocks.
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
        if not in_fence and HARNESS_ECHO.match(line.lstrip()):
            problems.append((i + 1, "harness-transcript",
                             "the eval harness's own stderr was echoed into the document; it "
                             "renders as prose between blocks — capture stdout alone"))
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


def address_problems(text: str) -> list[tuple[int, str]]:
    """`(line, hit)` for cluster addresses or the head hostname in board prose.

    Same per-branch octet counts as `tests/test_tracked_address_hygiene.py`: masked forms
    (`.30`, `192.168.0.x`) are the convention and stay legal. Checked at publish so a tick
    cannot push a literal that reds CI for every session after it.
    """
    out: list[tuple[int, str]] = []
    for n, line in enumerate(text.split("\n"), 1):
        for m in _ADDRESS_LITERAL.finditer(line):
            out.append((n, m.group(0)))
        for m in _HEAD_HOST.finditer(line):
            out.append((n, m.group(0)))
    return out


_ADDRESS_LITERAL = re.compile(r"\b(10\.\d+|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d+\.\d+\b")
_HEAD_HOST = re.compile(r"\bspark-(?:head|0[0-9])\b")


def lint_addresses(text: str) -> list[tuple[int, str, str]]:
    """`(line, rule, detail)` for a raw cluster address or head/fleet hostname in prose.

    The board ships to third parties, so the leak is a review and a CI problem, not a
    rendering one: `tests/test_tracked_address_hygiene.py` reds the pushed tip for it.
    The patterns are mirrored from that file (this tool is stdlib-only and may not import
    the test suite); `tests/test_task_queue_tool.py` pins one sample set tripping both.
    `.30`-`.35` is the allowed shorthand in this tree: a prose host reference is rewritten
    to it, never exempted.
    """
    return [(line, "cluster-address", f"{hit!r} is a raw cluster address or hostname; write the "
             "`.NN` shorthand instead")
            for line, hit in address_problems(text)]


_INFLIGHT_REQUIRED = ("census", "pool", "queue", "window", "campaign", "publication")


def inflight_keys(text: str) -> set[str]:
    """First-cell keys of the board's `## In flight` table; empty when the section is absent.

    Nodes and the quartet row are keys too (`.30`, `quartet`), but only `_INFLIGHT_REQUIRED` is
    checked: that set is the format's, while which nodes carry a rank belongs to the census.
    """
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines) if line.strip() == "## In flight"), None)
    if start is None:
        return set()
    keys: set[str] = set()
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        if not line.lstrip().startswith("|"):
            continue
        cells = _table_cells(line)
        if cells and cells[0].strip():
            keys.add(cells[0].strip().strip("`").split()[0].lower())
    return keys


def inflight_problems(text: str) -> list[tuple[int, str, str]]:
    """`(line, rule, detail)` for a board whose `## In flight` table is missing a state row.

    Measured 2026-11-11 03:14-03:25 ET: the 03:14 board carried a `| queue |` row, the 03:17 board
    did not, and the next tick — which keeps its base's body verbatim — published without it through
    `publish` rc=0, `lint` ok and a green push gate. Every other guard compares bytes against a base
    that was itself missing the row, so a fixed key set is the only way to notice an absence. A
    board with no `## In flight` section returns nothing: this rule reports a loss, not a shape.
    """
    keys = inflight_keys(text)
    if not keys:
        return []
    missing = [key for key in _INFLIGHT_REQUIRED if key not in keys]
    if not missing:
        return []
    return [(1, "inflight-row-missing",
             "In flight lacks " + ", ".join(f"`{key}`" for key in missing) +
             ": the table is state, and a row absent from the base is inherited by any tick that "
             "keeps that body verbatim")]


def _emit(lines: list[str], what: str) -> None:
    """Print generated markdown, refusing it if it will not render."""
    problems = lint_markdown("\n".join(lines))
    if problems:
        for line, rule, detail in problems:
            print(f"task-queue: {what}:{line}: {rule}: {detail}", file=sys.stderr)
        raise QueueError(f"refusing to emit {what}: {len(problems)} markdown problem(s) above")
    print("\n".join(lines))


BOARD_TITLE = re.compile(r"^#\s+Board\s+—\s+generated\s+(\d{4}-\d\d-\d\d \d\d:\d\d) ET", re.M)


def board_title(text: str) -> str | None:
    """The board's own generation stamp as `YYYY-MM-DD HH:MM` (sorts chronologically)."""
    m = BOARD_TITLE.search(text)
    return m.group(1) if m else None


def ref_text(path: Path, ref: str) -> str | None:
    """The file as `ref` has it, or `None` when untracked, outside a repository, or absent there."""
    top = subprocess.run(
        ["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"],
        capture_output=True, text=True)
    if top.returncode:
        return None
    repo = Path(top.stdout.strip())
    try:
        rel = path.resolve().relative_to(repo)
    except ValueError:
        return None
    show = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{rel}"],
                          capture_output=True, text=True)
    return show.stdout if show.returncode == 0 else None


def committed_text(path: Path) -> str | None:
    """The file as HEAD has it, or `None` when it is untracked or outside a repository."""
    return ref_text(path, "HEAD")


def cmd_lint(args, path: Path) -> None:
    """Lint markdown files; the board is the default because it is hand-written."""
    paths = [Path(p) for p in (args.paths or [DEFAULT_BOARD])]
    total = 0
    for target in paths:
        try:
            text = target.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise QueueError(f"no such markdown file: {target}")
        problems = lint_markdown(text)
        for line, rule, detail in problems:
            print(f"{target}:{line}: {rule}: {detail}")
        total += len(problems)
        # A concurrent tick fixes its census before taking the board lock, so it can publish a
        # whole-file rewrite whose title is older than the one already committed.  Three such
        # regressions landed on 2026-11-06 (15:00 -> 13:56, 15:49 -> 15:28); refusing them here
        # is the only check that runs before the commit, since lint is the tick's own last step.
        prior = board_title(committed_text(target) or "")
        mine = board_title(text)
        if mine and prior and mine < prior:
            print(f"{target}:1: title-regression: title says {mine}, HEAD says {prior} — a stale "
                  "full-file write replaced a fresher board; re-read it and regenerate")
            total += 1
        # The mirror defect, and the reason the rule above needs it: a stamp *ahead* of the clock
        # wedges every tick, because title-regression then refuses any honest title until wall time
        # passes the bogus one. Measured 2026-11-07: a board committed 17:10 carried `generated
        # 17:20 ET`, and the next tick lost nine minutes waiting rather than lying about the time.
        # Resolution is the minute, so a legitimately stamped title is never ahead of the clock.
        clock = dt.datetime.now()
        if mine and _stamp(mine) > clock.replace(second=0, microsecond=0):
            print(f"{target}:1: future-stamp: title says {mine}, clock says "
                  f"{clock:%Y-%m-%d %H:%M} — a stamp ahead of the clock wedges every tick's "
                  "title-regression check until wall time passes it; stamp the real time")
            total += 1
        # A raw address or hostname in the board reds the pushed tip (test_tracked_address_hygiene),
        # so lint refuses it the same way publish does — this is the check that runs before commit.
        addresses = lint_addresses(text)
        for line, rule, detail in addresses:
            print(f"{target}:{line}: {rule}: {detail}")
        total += len(addresses)
        # A board's In flight table is state: a missing row is a lost fact, and publish cannot see it
        # when the base it composed from was already missing it (measured 2026-11-11 03:17).
        if board_title(text):
            rows = inflight_problems(text)
            for line, rule, detail in rows:
                print(f"{target}:{line}: {rule}: {detail}")
            total += len(rows)
    if total:
        raise QueueError(f"{total} markdown problem(s) in {len(paths)} file(s)")
    print(f"ok: {len(paths)} markdown file(s) render")


_STAMP = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?) ET")


def _stamp(text: str) -> dt.datetime:
    return dt.datetime.strptime(text, "%Y-%m-%d %H:%M:%S" if text.count(":") == 2 else "%Y-%m-%d %H:%M")


def board_stamp(text: str) -> dt.datetime:
    """The board's own measurement time: newest `| census |` row stamp, the title as fallback.

    Census first, deliberately: the title is when the tick wrote and the census is what it measured, so
    a board can carry a fresh title over a stale read (measured 2026-11-06, three ticks inside 50 minutes).
    """
    stamps = [_stamp(m.group(1)) for line in text.splitlines() if line.startswith("| census |")
              for m in _STAMP.finditer(line)]
    if not stamps:
        title = board_title(text)
        if not title:
            raise QueueError("no census or title timestamp: cannot tell which board is newer")
        stamps.append(_stamp(title))
    return max(stamps)


def dropped_peer_lines(disk_text: str, base_text: str, incoming: str) -> list[str]:
    """Non-blank lines a peer added on disk after the publisher's read that the incoming body drops.

    Measured against the base the publisher composed from, not the whole disk: retirement is
    legitimate (a tick clears the landed table and closes work-queue rows), so only lines that
    appeared on disk *after* that read are peer additions that must survive into the new body.
    `--expect-sha` catches the same window from the other side (any move at all, exit 1); this one
    says which lines would be lost and asks for a merge (exit 3).
    """
    base = {line for line in base_text.splitlines() if line.strip()}
    have = {line for line in incoming.splitlines() if line.strip()}
    return [line for line in disk_text.splitlines()
            if line.strip() and line not in base and line not in have]


def _lock(handle, seconds: float) -> None:
    """Bounded exclusive flock: a wedged holder is reported, never waited on.

    Measured 2026-11-06: an eval kernel inherited the lock fd and held `.local/status-board.lock` for
    more than an hour, every later writer timed out, and one tick that gave up instead committed a
    stale board.  A blocked publish says so and exits; the operator inspects `fuser -v`.
    """
    deadline = time.monotonic() + seconds
    while True:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise QueueError(
                    f"{handle.name} still locked after {seconds:g}s — a holder is wedged; inspect "
                    f"with `fuser -v {handle.name}` and do not publish on a stale read")
            time.sleep(0.5)


def cmd_publish(args, path: Path) -> None:
    """Write a regenerated board from stdin, refusing one older than the board already on disk.

    A peer tick that takes its census early and writes late has twice replaced a newer board with an
    older one (2026-11-06: a 13:56 ET census landed over a 15:15 ET title).  `flock` serializes writers
    but cannot stop a slow one, so the freshness comparison has to happen inside the lock.

    The stamp comparison cannot see an in-place peer edit that keeps the title: measured 2026-11-08
    11:13, a tick composed from the 11:08 board and published five minutes later over a peer's edit
    carrying that same 11:08 title, which the equal stamp passed in both directions and the whole
    file replaced — bytes that no commit and no `/tmp` copy held.  `--expect-sha` is that gate: the
    caller passes the sha256 it composed from and the write is refused when the disk file moved.
    Both checks are local, so neither can see a peer who *pushed* while the composition ran: a commit
    built on the fresh remote tip then replaces their rows with every local check green (measured
    2026-11-08 23:13).  `--expect-remote-sha` is the same gate against `--remote-ref`.
    """
    text = sys.stdin.read()
    problems = lint_markdown(text)
    for line, rule, detail in problems:
        print(f"stdin:{line}: {rule}: {detail}", file=sys.stderr)
    if problems:
        raise QueueError(f"refusing publish: {len(problems)} markdown problem(s) above")
    leaks = address_problems(text)
    for line, hit in leaks[:5]:
        print(f"stdin:{line}: cluster-address: {hit}", file=sys.stderr)
    if leaks:
        # Board ships to third parties; the gate reds CI after the push, so refuse here instead.
        raise QueueError(
            f"refusing publish: {len(leaks)} cluster address(es) in board text — mask to "
            "`.30`–`.33`-style shorthand")
    rows = inflight_problems(text)
    for line, rule, detail in rows:
        print(f"stdin:{line}: {rule}: {detail}", file=sys.stderr)
    if rows:
        raise QueueError(f"refusing publish: {len(rows)} In flight problem(s) above")
    use_base = bool(getattr(args, "base", ""))
    if not use_base and not args.expect_sha:
        # Fail closed: with neither the sha nor the bytes it read, no check can catch a peer write.
        raise QueueError(
            "refusing publish: pass --expect-sha <sha256 you read> (exit 1 on a move) or "
            "--base <file you read> (exit 3 on a dropped peer line), so the write is not unchecked")
    base_text = Path(args.base).read_text(encoding="utf-8") if use_base else ""
    incoming = board_stamp(text)
    board = Path(args.board)
    lock = Path(args.lock)
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as handle:
        _lock(handle, args.lock_wait)
        disk_text = board.read_text(encoding="utf-8") if board.exists() else ""
        disk = board_stamp(disk_text) if disk_text else None
        if disk is not None and disk > incoming:
            raise QueueError(
                f"refusing publish: {board} on disk carries {disk} ET, newer than this read's "
                f"{incoming} ET — re-read the census, do not overwrite it")
        if args.expect_sha:
            # Fail closed when the board is gone too: an absent file cannot be proved unmoved.
            moved = (hashlib.sha256(board.read_bytes()).hexdigest()
                     if board.exists() else "(absent)")
            if moved != args.expect_sha:
                raise QueueError(
                    f"refusing publish: {board} on disk is sha256 {moved[:12]}, not the "
                    f"{args.expect_sha[:12]} this board was composed from — a peer wrote it in "
                    "between; re-read and re-compose, do not replace their rows")
        if args.expect_remote_sha:
            # The disk checks above are local, so they cannot see a peer who pushed while this
            # composition ran: a commit built on the fresh remote tip then replaces their rows
            # while every local check passed (measured 2026-11-08 23:13).
            remote = ref_text(board, args.remote_ref)
            moved = hashlib.sha256(remote.encode()).hexdigest() if remote is not None else "(absent)"
            if moved != args.expect_remote_sha:
                raise QueueError(
                    f"refusing publish: {args.remote_ref} carries board sha256 {moved[:12]}, not the "
                    f"{args.expect_remote_sha[:12]} this board was composed from — a peer published "
                    "in between; re-derive over theirs, do not push on their tip")
        if use_base:
            peer = dropped_peer_lines(disk_text, base_text, text)
            if peer:
                raise PeerWriteInFlight(
                    f"refusing publish: {len(peer)} line(s) a peer wrote after your read are "
                    "absent from this body — merge them in, do not regenerate; first missing: "
                    + " | ".join(peer[:5])[:400])
        tmp = board.with_name(board.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, board)
    print(f"published {board}: {incoming} ET" + (f" (disk was {disk} ET)" if disk else ""))


def cmd_render(args, path: Path) -> None:
    data = load(path)
    if getattr(args, "board", False):
        _emit(board_rows(data, path), "board table")
        return
    ordered = ordering(data, path)
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


#: The state cell quotes this much of a row's note.  Whole notes prose measured 75 821 B across
#: the 23 open rows — an 82 136 B board — and every hourly tick read it before writing one census
#: row (2026-11-08).  The register keeps the full text, so the cell points at it instead of
#: copying it; `graph`'s `GRAPH_LABEL` truncates its own label the same way.
NOTE_BUDGET = 240


def board_rows(data: dict, path: Path | None = None) -> list[str]:
    """The STATUS.md `## Work queue` table, derived from the register.

    Columns are the board's own: job, node cost, holds, state.  `holds` is the task's
    `blocked_by` (what must clear first), and the state cell carries the note's opening —
    `NOTE_BUDGET` characters, then a pointer to `queue.json` — because the note lives in exactly
    one place and a second whole copy is what made the board 82 KB.
    """
    ordered = ordering(data, path)
    tiers = _tiers(data["priority_models"])
    lines = ["| job | node cost | holds | state |", "|---|---|---|---|"]
    for _tier, task in enumerate_tasks_with_tier(ordered, tiers):
        state = task["state"]
        if task.get("notes"):
            note = task["notes"]
            if len(note) > NOTE_BUDGET:
                note = note[:NOTE_BUDGET]
                if note.count("`") % 2:  # cut inside a code span: drop the stub, not the pair count
                    note = note[:note.rindex("`")]
                note += "… (full note: queue.json)"
            state = f"{state} — {note}"
        if task.get("evidence"):
            state = f"{state} — evidence: `{task['evidence']}`"
        lines.append(f"| `{task['id']}` — {_cell(task['title'])} | {task['node_cost'] or '—'} "
                     f"| {_cell(', '.join(task['blocked_by']) or '—')} | {_cell(state)} |")
    return lines


def _cell(text: str) -> str:
    """One line, no cell breakers: notes are prose and carry newlines and pipes."""
    return " ".join(str(text).split()).replace("|", r"\|")


# ---------------------------------------------------------------- dependency graph

#: Node budget for `graph`: a 100-box diagram is unreadable, and it lands in an ~80 KB board.
GRAPH_BUDGET = 30
#: Hyphenated ids are long; with the connected view at ~9 nodes there is room for most of one.
GRAPH_LABEL = 60
#: The three ways a row cites an owner question: `QUESTIONS.md #67`, `questions [67]`, a bare `#67`.
QUESTION_CITE = re.compile(r"#(\d+)|questions\s*\[\s*(\d+)\s*\]")

#: One style-only rule, and not a colour: the renderer's theme owns fill and text, so the block
#: reads on light and dark alike. State is in the label text; the dashed stroke is a non-colour
#: channel (it also works for colour-blind readers) marking the owner-gated rows.
GRAPH_STYLE = ("no-recorded-edge", "stroke-dasharray: 4 3")


def _graph_label(text: str) -> str:
    text = " ".join(str(text).split()).replace('"', "'")
    return text if len(text) <= GRAPH_LABEL else text[:GRAPH_LABEL] + "…"


def question_citations(task: dict, known: set[int]) -> list[int]:
    """The open question ids a row cites in its prose, sorted; ids outside `known` are dropped."""
    text = " ".join(str(task.get(key) or "") for key in ("notes", "provenance"))
    found = {int(a or b) for a, b in QUESTION_CITE.findall(text)}
    return sorted(found & known)


def graph_body(data: dict, max_nodes: int = GRAPH_BUDGET,
               all_rows: bool = False) -> tuple[list[str], list[str]]:
    """(the mermaid lines above the closing fence, warnings) for the open rows in `data`.

    Edge tiers, because a `blocked_by`-only graph would be a lie: measured 2026-11-08, every
    open blocked row stores `blocked_by: []` while its gate is a citation of an owner question.
    So: `blocks` pairs between open rows, `q<n> --> row` for every row whose notes or provenance
    cite an open question, and nothing for the rest -- which `--all` draws dashed
    `no-recorded-edge`, "gated by prose, not by a row".

    The default view draws the connected set only: rows taking part in an edge, in either
    direction, plus the questions they reach. On the 2026-11-08 register that is 9 nodes and
    6 edges instead of 27 boxes with 18 isolated -- a box wall reads as "nothing depends on
    anything", which is the failure this drawing exists to prevent. `--all` draws every open
    row, and the counts comment names how many the default left out, so an omission is visible
    in the raw markdown.

    Edges come from the blocking row's `blocks` only: `blocked_by` is a mirror `_relink`
    rewrites from it, and `validate` refuses one that disagrees -- so a mismatch is a register
    mid-edit, and it is warned about rather than drawn. A tick that records real edges moves
    `edges` in the counts line, which is how a sparse graph and a wrong one are told apart.
    """
    max_nodes = max(1, max_nodes)
    tasks = sorted((t for t in data.get("tasks") or []
                    if isinstance(t, dict) and t.get("state") != "done"),
                   key=lambda t: str(t.get("id")))
    open_ids = {str(t.get("id")) for t in tasks}
    questions = {int(q["id"]): q for q in data.get("questions") or []
                 if isinstance(q, dict) and isinstance(q.get("id"), int)}
    warnings: list[str] = []

    row_edges: set[tuple[str, str]] = set()
    mirror: dict[str, set[str]] = {}
    for t in tasks:
        for child in t.get("blocks") or []:
            mirror.setdefault(child, set()).add(str(t.get("id")))
    for t in tasks:
        tid = str(t.get("id"))
        for child in t.get("blocks") or []:
            if child in open_ids:
                row_edges.add((tid, child))
    for t in tasks:
        tid = str(t.get("id"))
        stored = set(t.get("blocked_by") or []) & open_ids
        derived = mirror.get(tid, set()) & open_ids
        for parent in sorted(stored - derived):
            warnings.append(f"{parent} -> {tid}: in blocked_by, but {parent}.blocks does not name it")
        for parent in sorted(derived - stored):
            warnings.append(f"{parent} -> {tid}: in {parent}.blocks, but blocked_by does not name it")

    cited = {str(t.get("id")): question_citations(t, set(questions)) for t in tasks}
    question_nodes = sorted({q for ids in cited.values() for q in ids})
    question_edges = {("q:%d" % q, tid) for tid, qs in cited.items() for q in qs}
    incoming = {target for _source, target in row_edges}
    blocked_ids = [str(t.get("id")) for t in tasks if t.get("state") == "blocked"]
    question_gated = [tid for tid in blocked_ids if tid not in incoming and cited[tid]]
    prose_gated = [tid for tid in blocked_ids if tid not in incoming and not cited[tid]]

    participants = {tid for edge in row_edges for tid in edge}
    participants |= {tid for _q, tid in question_edges}
    drawn = tasks if all_rows else [t for t in tasks if str(t.get("id")) in participants]
    omitted = len(tasks) - len(drawn)
    counts = (f"{len(blocked_ids)} blocked, {len(row_edges)} edges, "
              f"{len(prose_gated)} prose-gated, {len(question_gated)} question-gated, "
              f"{len(question_nodes)} question")
    if omitted:
        counts += f", {omitted} rows not drawn (--all)"

    classdef = f"  classDef {GRAPH_STYLE[0]} {GRAPH_STYLE[1]}"
    if not tasks:
        # A fence with only a classDef says nothing; the reader gets a node that says it.
        return (["flowchart LR", "  %% " + counts,
                 '  empty["no open rows in the register"]', classdef], warnings)
    if not drawn and not question_nodes:
        return (["flowchart LR", "  %% " + counts,
                 '  empty["no edge recorded among the open rows; --all draws every row"]',
                 classdef], warnings)

    nodes = [("q:%d" % q, questions[q], "question") for q in question_nodes]
    nodes += [(str(t.get("id")), t, "task") for t in drawn]
    truncated = len(nodes) > max_nodes
    shown = nodes[: max_nodes - 1] if truncated else nodes
    hidden = nodes[len(shown):]
    hidden_tasks = [n for n in hidden if n[2] == "task"]
    hidden_questions = [n for n in hidden if n[2] == "question"]

    name: dict[str, str] = {}
    task_number = 0
    for key, _payload, kind in shown:
        if kind == "question":
            name[key] = "q" + key.split(":", 1)[1]
        else:
            task_number += 1
            name[key] = "t%d" % task_number
    lines = ["flowchart LR", "  %% " + counts]
    if truncated:
        lines.append(f"  %% truncated: {len(shown)} shown of {len(nodes)}")
    for key, payload, kind in shown:
        if kind == "question":
            lines.append(f'  {name[key]}["Q{payload["id"]} · '
                         f'{_graph_label(payload.get("summary"))}"]')
            continue
        tid = str(payload.get("id"))
        gated = tid in prose_gated
        owner = " · owner" if gated else ""
        suffix = ":::" + GRAPH_STYLE[0] if gated else ""
        lines.append(f'  {name[key]}["{_graph_label(tid)} · {payload.get("state")}{owner}"]{suffix}')
    if truncated:
        more = []
        if hidden_tasks:
            more.append(f"{len(hidden_tasks)} more open rows")
        if hidden_questions:
            more.append(f"{len(hidden_questions)} more question(s)")
        lines.append(f'  tn["… {" + ".join(more)} (see the table)"]')
    edges = sorted({(name[a], name[b]) for a, b in row_edges | question_edges
                    if a in name and b in name},
                   key=lambda e: (e[0][0], int(e[0][1:]), e[1][0], int(e[1][1:])))
    for source, target in edges:
        lines.append(f"  {source} --> {target}")
    lines.append(classdef)
    return lines, warnings


def cmd_graph(args, path: Path) -> None:
    """Print one fenced mermaid block, derived from the register (never from the board)."""
    data = load(path)
    body, warnings = graph_body(data, args.max_nodes, getattr(args, "all", False))
    for warning in warnings:
        print(f"task-queue: graph: blocked_by/blocks disagree — {warning}", file=sys.stderr)
    print("```mermaid")
    for line in body:
        print(line)
    print("```")



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
    tasks = validate(data, path)
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
    p_add.add_argument("--recipe", help="bootable row: tracked `recipes/<lane>/<arm>.yaml` path")
    p_add.add_argument("--tp", type=int, help="bootable row: nodes the arm takes (1/2/4), must match --node-cost")
    p_add.add_argument("--memory-risky", dest="memory_risky", action="store_true", default=None,
                       help="placement: this shape is memory-risky (default: derived from --node-cost)")
    p_add.add_argument("--no-memory-risky", dest="memory_risky", action="store_false",
                       help="placement: this shape is safe even on a risky node")
    p_add.add_argument("--exclude-hosts", metavar="HOST[,HOST]",
                       help="placement: nodes a lease must not use")
    p_add.add_argument("--env", action="append", metavar="KEY=VALUE",
                       help="bootable row: environment override for the launch (repeatable)")
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
    p_upd.add_argument("--recipe")
    p_upd.add_argument("--tp", type=int)
    p_upd.add_argument("--env", action="append", metavar="KEY=VALUE",
                       help="bootable row: merge KEY=VALUE pairs into `env` (repeatable)")
    p_upd.add_argument("--memory-risky", dest="memory_risky", action="store_true", default=None,
                       help="placement: mark the shape memory-risky (tri-state; unset leaves it)")
    p_upd.add_argument("--no-memory-risky", dest="memory_risky", action="store_false",
                       help="placement: mark the shape safe on a risky node")
    p_upd.add_argument("--exclude-hosts", metavar="HOST[,HOST]",
                       help="placement: replace the row's excluded-host list")
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
    p_graph = sub.add_parser("graph", help="fenced mermaid diagram of the open work, from the register")
    # SUPPRESS, not None: the subparser parses into the same namespace, so a plain default
    # here overwrites the value the parent already parsed from `--file X graph` -- measured
    # 2026-11-08: that order silently read the default register and drew a plausible diagram
    # from the wrong file.
    p_graph.add_argument("--file", default=argparse.SUPPRESS,
                         help=f"queue JSON (default {DEFAULT_QUEUE}); the global --file works too")
    p_graph.add_argument("--all", action="store_true",
                         help="draw every open row, not only the rows taking part in an edge")
    p_graph.add_argument("--max-nodes", type=int, default=GRAPH_BUDGET,
                         help=f"node budget; the remainder collapses into one node "
                              f"(default {GRAPH_BUDGET})")
    p_graph.set_defaults(fn=cmd_graph)
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
    p_queue = sub.add_parser("queue", help="print the ordered queue with computed weights")
    p_queue.add_argument("--json", action="store_true",
                         help="the same ordering as JSON (a scheduler's plan source)")
    p_queue.set_defaults(fn=cmd_queue)
    sub.add_parser("questions", help="open owner questions from the register").set_defaults(fn=cmd_questions)
    sub.add_parser("check", help="validate: ids, refs, cycles, estimates").set_defaults(fn=cmd_check)
    p_lint = sub.add_parser("lint", help="markdown that will not render (tables, fences)")
    p_lint.add_argument("paths", nargs="*", default=None,
                        help=f"markdown files (default {DEFAULT_BOARD})")
    p_lint.set_defaults(fn=cmd_lint)
    p_pub = sub.add_parser("publish", help="write a board from stdin unless the one on disk is newer")
    p_pub.add_argument("--board", default=str(DEFAULT_BOARD), help=f"board file (default {DEFAULT_BOARD})")
    p_pub.add_argument("--expect-sha", default=None,
                       help="sha256 of the board this composition was read from; refuse when the file "
                            "on disk moved (guards a peer's in-place edit carrying the same title)")
    p_pub.add_argument("--expect-remote-sha", default=None,
                       help="sha256 of the board at --remote-ref; refuse when a peer published after "
                            "your read — the disk sha above cannot see that (fetch first)")
    p_pub.add_argument("--remote-ref", default="origin/main",
                       help="ref the remote board is read from (default origin/main)")
    p_pub.add_argument("--base", default="",
                       help="board file you read before composing: a non-blank line a peer added "
                            "after it must survive into stdin, or the publish exits 3")
    p_pub.add_argument("--lock", default=".local/status-board.lock",
                       help="lock file shared with every other board writer (default .local/status-board.lock)")
    p_pub.add_argument("--lock-wait", type=float, default=90.0,
                       help="seconds to wait for the lock before refusing (default 90)")
    p_pub.set_defaults(fn=cmd_publish)

    args = parser.parse_args(argv)
    # A subparser that redefines `--file` (graph) overwrites the global value with its default.
    path = Path(args.file or DEFAULT_QUEUE)
    try:
        if getattr(args, "_fixed_state", None):
            args.state = args._fixed_state
            cmd_update(args, path)
        else:
            args.fn(args, path)
    except QueueError as exc:
        print(f"task-queue: {exc}", file=sys.stderr)
        return exc.exit_code
    return 0


if __name__ == "__main__":
    sys.exit(main())