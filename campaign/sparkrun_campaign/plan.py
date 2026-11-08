"""What runs next, and on which hosts.

Two plan sources, one placement rule. A **manifest** is a hand-written list whose order is the
plan. A **queue campaign** reads the register (`mad-science/queue.json`) instead: rows that name a
`recipe` and its `tp` are the work, ordered by the register's own weighted order, which is read from
`tools/task-queue.py queue --json` rather than re-derived here -- one implementation of the weight
arithmetic, not two. The declared host set is still the whole node set a campaign may use; the
director discovers *work*, never nodes.

Ordering is the manifest's order. There is no static partition of the plan into per-node slices:
the 2026-11-04 campaign lost 2.02 node-hours because one node's slice ended with a 132-minute arm
while the other node sat idle with nothing queued. A static slice cannot see its peer's queue; a
director that hands the next pending arm to whichever slot is free can, so that is the only
placement rule here.

Assignment is a pure function of (order, arm records, free hosts). It takes no clock and does no
I/O, which is what lets the placement rules -- a leaked host, an arm awaiting a reap, a TP=2 arm
with one host free -- be tested without a fleet.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .evidence import Verdict, skip_line
from .state import FAILED, LEASED, PENDING, SKIPPED

#: Runtime keys a recipe may carry. `tp` is the node count the arm was planned for; the manifest
#: is where that decision lives because it is a property of the arm, not of the run. A queue row
#: may ask for a quartet (`tp=4`), which `queue_entries` admits only when four hosts are declared.
TP_VALUES = (1, 2)
#: The register, relative to `--repo-root`, when `--queue` is given without a path.
DEFAULT_QUEUE = "mad-science/queue.json"


class PlanError(RuntimeError):
    """The plan cannot be issued as written. Never plan around a broken one."""


class RegisterError(RuntimeError):
    """The register refused a read or a write. Never read as "nothing to do"."""


class Register:
    """The queue register: plan source and the one writer of claims, via `tools/task-queue.py`.

    Shelled out, never imported: `tools/` is stdlib-only and dash-named, and the tool owns the
    register's atomic save -- a second writer here would race its own lock out of existence. The
    ordering, the tiering and the weight arithmetic are the tool's too, so this package carries no
    second copy to drift.
    """

    def __init__(self, tool: str | Path, queue: str | Path, session: str,
                 run: Callable[..., Any] = subprocess.run):
        self.tool = Path(tool)
        self.queue = Path(queue)
        self.session = session
        self._run = run

    def _call(self, *args: str) -> str:
        command = [sys.executable, "-B", str(self.tool), "--file", str(self.queue), *args]
        result = self._run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RegisterError(f"{' '.join(args)}: rc={result.returncode}: "
                                f"{(result.stderr or '').strip()[:300]}")
        return result.stdout

    def rows(self) -> list[dict[str, Any]]:
        """Every task, in the register's own weighted order."""
        try:
            rows = json.loads(self._call("queue", "--json"))
        except ValueError as exc:
            raise RegisterError(f"{self.queue}: queue --json is not JSON: {exc}") from exc
        if not isinstance(rows, list):
            raise RegisterError(f"{self.queue}: queue --json is not a list of tasks")
        return rows

    def update(self, task_id: str, **fields: Any) -> None:
        """The tool is the writer: `update` relinks, validates, then replaces the file atomically."""
        argv = ["update", "--id", task_id]
        for key, value in fields.items():
            argv += [f"--{key.replace('_', '-')}", str(value)]
        self._call(*argv)

    def note(self, task_id: str, why: str) -> str:
        """The row's notes with `why` appended, because `--notes` replaces the whole cell."""
        current = next((str(row.get("notes", "")) for row in self.rows()
                        if row.get("id") == task_id), "")
        return f"{current} — {why}" if current else why


def queue_entries(rows: list[dict[str, Any]], hosts: list[str],
                  session: str) -> tuple[list[dict[str, Any]], list[str], dict[str, str]]:
    """(entries, explanation lines, arm -> why it is not runnable) from the register's ordering.

    Only `queued` rows that name a `recipe` and `tp` are work: `blocked`/`done` are somebody else's
    answer, `running` is another session's claim (a claim of *ours* from a previous life is left to
    the campaign's own record), and a row whose `tp` exceeds the declared host count is skipped by
    name rather than truncated onto fewer nodes. An authoring row is counted, not listed: the
    register is mostly prose work and a line per row would bury the exclusions that matter.
    """
    entries: list[dict[str, Any]] = []
    lines: list[str] = []
    excluded: dict[str, str] = {}
    owner: dict[str, str] = {}
    authoring = 0
    for row in rows:
        task = str(row.get("id", "?"))
        state = row.get("state")
        recipe, tp = row.get("recipe"), row.get("tp")
        if not recipe or not tp:
            if state == "queued":
                authoring += 1      # queued prose/work rows: counted, because that is the queue
            continue
        arm = Path(str(recipe)).stem
        if state != "queued":
            if state == "running" and row.get("claimed_by") == session:
                continue
            reason = (f"claimed running by {row.get('claimed_by') or 'another session'}"
                      if state == "running" else f"register state {state}")
            lines.append(f"queue-skip: {task} ({reason})")
            excluded[arm] = reason
            continue
        if tp > len(hosts):
            reason = f"tp={tp} needs {tp} hosts, {len(hosts)} declared"
            lines.append(f"queue-skip: {task} ({reason})")
            excluded[arm] = reason
            continue
        if arm in owner:
            raise PlanError(f"{task} and {owner[arm]} both name recipe {recipe}")
        owner[arm] = task
        entries.append({"arm": arm, "path": recipe, "tp": int(tp),
                        "env": dict(row.get("env") or {}), "task": task})
    if authoring:
        lines.append(f"queue: {authoring} row(s) queued without a recipe (authoring, not bootable)")
    return entries, lines, excluded


def load_manifest(path: str | Path) -> list[dict[str, Any]]:
    """Read and validate a campaign manifest: a JSON list of {arm, path, tp, env?}."""
    path = Path(path)
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PlanError(f"cannot read {path}: {exc}") from exc
    except ValueError as exc:
        raise PlanError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(entries, list):
        raise PlanError(f"{path} must hold a list of arms")
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise PlanError(f"{path}: entry {index} is a {type(entry).__name__}, not an object")
        arm = entry.get("arm")
        recipe = entry.get("path")
        if not isinstance(arm, str) or not arm:
            raise PlanError(f"{path}: entry {index} has no `arm` string")
        if not isinstance(recipe, str) or not recipe:
            raise PlanError(f"{path}: {arm} has no `path` string")
        if arm in seen:
            raise PlanError(f"{path}: {arm} appears twice")
        seen.add(arm)
        tp = entry.get("tp", 1)
        if tp not in TP_VALUES:
            raise PlanError(f"{path}: {arm} has tp={tp!r}; expected one of {TP_VALUES}")
        env = entry.get("env") or {}
        if not isinstance(env, dict):
            raise PlanError(f"{path}: {arm} has a non-object `env`")
        out.append({"arm": arm, "path": recipe, "tp": int(tp), "env": dict(env)})
    return out


def build(
    entries: list[dict[str, Any]],
    verdicts: dict[str, Verdict],
    measured: dict[str, str],
    root: str | Path = ".",
) -> tuple[list[str], list[str]]:
    """(arm order, explanation lines). Every exclusion is named, so "not planned" is checkable.

    A recipe the tree records as a measured negative is excluded by the skip source, never by a
    remembered list -- that is what printed `skip:` lines are for. An arm with a measurement
    already on disk is excluded too, and says where its numbers are.
    """
    order: list[str] = []
    lines: list[str] = []
    for entry in entries:
        arm = entry["arm"]
        missing = Path(root) / entry["path"]
        if not missing.is_file():
            raise PlanError(f"{arm}: {entry['path']} does not exist under {root}")
        order.append(arm)
        if arm in verdicts:
            lines.append(skip_line(verdicts[arm]))
        elif arm in measured:
            lines.append(f"measured: {arm} ({measured[arm]})")
    return order, lines


def next_assignment(
    order: list[str],
    arms: dict[str, dict[str, Any]],
    free_hosts: list[str],
    retries: int = 0,
) -> tuple[str, tuple[str, ...]] | None:
    """The next arm and the hosts it takes, or None when no pending arm fits.

    An arm is eligible while it is pending, or failed with retries left. It must have no reap
    outstanding: a host may still be running the arm's own container, and handing the arm out
    again while that is unverified is how a second boot lands on a held port. A TP=2 arm takes two
    hosts in one lease -- `tools/run-arm.sh` is launched once with both, so one worker owns the pair.
    """
    free = list(free_hosts)
    for arm in order:
        record = arms.get(arm)
        if record is None:
            raise PlanError(f"{arm} is in the plan order but has no arm record")
        status = record["status"]
        eligible = status == PENDING or (status == FAILED and record["failures"] <= retries)
        if not eligible or status == SKIPPED or status == LEASED:
            continue
        if record["needs_reap"]:
            continue
        need = int(record["tp"])
        if len(free) < need:
            continue
        return arm, tuple(free[:need])
    return None