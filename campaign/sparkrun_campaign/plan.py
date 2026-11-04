"""What runs next, and on which hosts.

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
from pathlib import Path
from typing import Any

from .evidence import Verdict, skip_line
from .state import FAILED, LEASED, PENDING, SKIPPED

#: Runtime keys a recipe may carry. `tp` is the node count the arm was planned for; the manifest
#: is where that decision lives because it is a property of the arm, not of the run.
TP_VALUES = (1, 2)


class PlanError(RuntimeError):
    """The manifest cannot be planned as written. Never plan around a broken one."""


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
        need = 2 if record["tp"] == 2 else 1
        if len(free) < need:
            continue
        return arm, tuple(free[:need])
    return None