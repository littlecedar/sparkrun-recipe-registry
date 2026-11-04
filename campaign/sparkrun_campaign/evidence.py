"""The two things the campaign must know before it spends a window: what not to boot, what is done.

The skip source is the recipe's own `metadata.measured_rejected` marker, so the verdict travels
with the artifact it refuses (a rename or a move to `attic/` carries it; a deletion removes it).
The "done" predicate reads receipt FIELDS -- `house.yaml`'s top-level `ladder` / `accuracy_status`
plus the cell table inside `ladder.json` -- because a file that exists proves only that a command
started. The 2026-11-04 campaign re-booted two recorded negatives and four finished arms with
presence-only predicates; this module exists so neither is expressible here.

`tools/next-arms.py` owns the same two readers for the planner's CLI. This module reimplements
them rather than importing a dash-named script whose CLI is fleet-shaped (it ssh-probes nodes):
importing it would drag a probe into the director's decision path. `tests/test_evidence.py` pins
the two implementations to each other over the whole real tree, so they cannot drift silently.
"""

from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TypedDict

#: The verdict lives in the recipe it refuses: `metadata.measured_rejected: "<date> -- <reason>
#: (<doc>:<line>)"`. `metadata` and not a top-level key, because sparkrun sweeps an unknown
#: top-level key into `runtime_config`.
REJECT_MARKER = "measured_rejected"
VERDICT = "measured-rejected"
#: `<date> -- <reason> (<path>:<line>)`, the whole marker; the path may not contain a parenthesis.
CITATION = re.compile(r"^(\d{4}-\d{2}-\d{2}) \u2014 (.+?) \(([^()\s]+):(\d+)\)$")

#: Machine-readable artefacts only: `run-arm.sh` writes `ladder.yaml` as soon as a benchmark
#: starts, so a yaml-only receipt is an arm that may have died before its first cell.
MEASURED_ARTEFACTS = ("ladder.json", "ladder.transcribed.json", "house.json", "house.transcribed.txt")
#: The marker `run-arm.sh` appends outcome fields to; nested `ladder` keys are payload, so only the
#: unindented keys are read.
MARKER = "house.yaml"
LADDERS = ("ladder.json", "ladder.transcribed.json")
#: Cell tables the instruments write: the ladder's `benchmarks`, the decision ladder's `cells`, and
#: the pooling exporter's `runs`. A file that parses to none of these has no cell in it.
CELL_KEYS = ("benchmarks", "cells", "runs")
_TOP_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):[ \t]*(.*)$")
_LADDER_VALUE = re.compile(r"^(ok|failed \(rc=\d+\))")

#: Receipt windows the per-arm executor writes into, relative to the receipts root.
WINDOW = "tp12-*"


class Verdict(TypedDict):
    """One recorded measured negative, as the skip source carries it."""

    arm: str
    verdict: str
    doc: str
    since: str


class EvidenceError(RuntimeError):
    """A verdict or receipt could not be read, or contradicts itself. Never "done" on a guess."""


# --- skip source --------------------------------------------------------------------------------


def metadata_value(text: str, key: str) -> str | None:
    """The `key:` value inside a recipe's top-level `metadata:` block, or None.

    Hand-rolled YAML subset, like the guards in `tests/`: the block is the indented run after
    `metadata:` at column 0, a block-level key is indented exactly two spaces, and the value may be
    double-quoted. A key that appears twice raises -- two markers on one arm are a contradiction
    and neither is a safe default.
    """
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if re.fullmatch(r"metadata:[ \t]*", line)), None)
    if start is None:
        return None
    prefix = f"  {key}:"
    found: list[str] = []
    for line in lines[start + 1:]:
        if line.strip() and not line.startswith(" "):
            break
        if line.startswith(prefix):
            found.append(line[len(prefix):].strip().strip('"'))
    if len(found) > 1:
        raise EvidenceError(f"`metadata.{key}` appears twice ({found[0]!r} and {found[1]!r})")
    return found[0] if found else None


def tracked(root: str | Path = ".") -> set[str] | None:
    """Every tracked path under `root`, or None when `root` is not a checkout."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files"], capture_output=True, text=True, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return set(result.stdout.splitlines()) or None


def skips(root: str | Path = ".") -> dict[str, Verdict]:
    """Recorded measured negatives, keyed by arm, read from the recipes themselves."""
    out: dict[str, Verdict] = {}
    for path in sorted(glob.glob(os.path.join(str(root), "recipes", "*", "*.yaml"))):
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            raise EvidenceError(f"cannot read {path}: {exc}") from exc
        value = metadata_value(text, REJECT_MARKER)
        if value is None:
            continue
        found = CITATION.match(value)
        if not found:
            raise EvidenceError(
                f'{path}: metadata.{REJECT_MARKER} must read "<YYYY-MM-DD> \u2014 <reason>'
                f' (<path>:<line>)", not {value!r}'
            )
        arm = os.path.basename(path)[: -len(".yaml")]
        out[arm] = {
            "arm": arm,
            "verdict": VERDICT,
            "doc": f"{found.group(3)}:{found.group(4)}",
            "since": found.group(1),
        }
    return out


def citation_problems(verdicts: dict[str, Verdict], root: str | Path = ".") -> list[str]:
    """Markers whose cited `path:line` no longer resolves, as printable lines.

    A citation into an untracked scratch path is not evidence a clone can check, so it is refused
    when the root is a checkout.
    """
    known = tracked(root)
    problems: list[str] = []
    for arm, entry in sorted(verdicts.items()):
        doc, _, line = entry["doc"].rpartition(":")
        path = os.path.join(str(root), doc)
        if known is not None and doc not in known:
            problems.append(f"{arm} cites {entry['doc']}, which is not a tracked file")
        elif not os.path.isfile(path):
            problems.append(f"{arm} cites {entry['doc']}, which is not a file")
        else:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
            if len(text.splitlines()) < int(line):
                problems.append(f"{arm} cites {entry['doc']}, past the end of that file")
    return problems


def skip_line(entry: Verdict) -> str:
    """The one line a planner must print before any boot."""
    return f"skip: {entry['arm']} ({entry['verdict']}, {entry['doc']})"


# --- receipts -----------------------------------------------------------------------------------


def marker_fields(arm_dir: str | Path) -> dict[str, str] | None:
    """Top-level `key: value` fields of `house.yaml`, or None when there is no marker.

    Nested keys are payload, not outcome. An unreadable or self-contradicting marker raises: a
    guess of "measured" leaves an arm that must be re-run, and a guess of "not measured" re-boots
    an arm that already has its numbers, so neither is a safe default.
    """
    path = Path(arm_dir) / MARKER
    if not path.exists():
        return None
    fields: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise EvidenceError(f"{path}: {exc}") from exc
    for line in text.splitlines():
        found = _TOP_KEY.match(line)
        if not found:
            continue
        key, value = found.group(1), found.group(2).strip()
        if key in fields and fields[key] != value:
            raise EvidenceError(f"{path}: {key} appears twice ({fields[key]!r} and {value!r})")
        fields[key] = value
    return fields


def measurement_problem(arm_dir: str | Path) -> str | None:
    """Why the ladder artefact is not a measurement, or None when it parses with content."""
    for name in LADDERS:
        path = Path(arm_dir) / name
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return f"{name} does not parse ({exc.__class__.__name__})"
        if isinstance(data, dict):
            tables = [data[k] for k in CELL_KEYS if isinstance(data.get(k), list)]
            if tables and not any(tables):
                return f"{name} parses to no cell"
            if not data:
                return f"{name} parses to an empty object"
        elif isinstance(data, list):
            if not data:
                return f"{name} parses to an empty list"
        else:
            return f"{name} parses to a {type(data).__name__}, not a cell table"
    return None


def done(arm_dir: str | Path) -> tuple[bool, str]:
    """(measured, reason). A reason is always produced, so a non-receipt is visible in the log."""
    arm = Path(str(arm_dir).rstrip("/")).name
    try:
        fields = marker_fields(arm_dir)
    except EvidenceError as exc:
        return False, f"{arm}: marker unreadable, not measured: {exc}"
    problem = measurement_problem(arm_dir)
    verdict = (fields or {}).get("ladder", "")
    if verdict:
        found = _LADDER_VALUE.match(verdict)
        if not found:
            return False, (f"{arm}: {MARKER} ladder field {verdict!r} is neither 'ok' nor"
                           f" 'failed (rc=N)'; not measured")
        if found.group(1) != "ok":
            # The one state where re-attempting is right: the boot finished, the ladder did not.
            return False, f"{arm}: ladder failed, so the arm is unmeasured ({verdict})"
        if problem:
            # `ok` beside a broken artefact contradicts itself; the artefact loses the tie.
            return False, f"{arm}: ladder says ok but the artefact is not a measurement: {problem}"
        return True, ""
    if problem:
        return False, f"{arm}: {problem}; not measured"
    if any((Path(arm_dir) / name).exists() for name in MEASURED_ARTEFACTS):
        return True, ""
    return False, f"{arm}: no marker and no machine-readable artefact"


def window_dirs(root: str | Path, window: str = WINDOW) -> list[str]:
    """Receipt windows under `root`, newest first -- today's window is where a fresh arm lands."""
    return sorted(glob.glob(os.path.join(str(root), window)), reverse=True)


def find_measurement(root: str | Path, arm: str, window: str = WINDOW) -> tuple[bool, str, str]:
    """(measured, reason, dir) for one arm: the newest window that measured it, else the newest dir.

    Windows are searched newest first so a re-run's numbers win over an older one's; only a
    directory that is actually a measurement is preferred over a newer partial one, because the
    question being asked is "does this arm have numbers", and a later crash cannot un-measure an
    earlier measurement.
    """
    fallback: tuple[str, str] | None = None
    for win in window_dirs(root, window):
        arm_dir = os.path.join(win, arm)
        if not os.path.isdir(arm_dir):
            continue
        ok, reason = done(arm_dir)
        if ok:
            return True, "", arm_dir
        if fallback is None:
            fallback = (arm_dir, reason)
    if fallback:
        return False, fallback[1], fallback[0]
    return False, f"{arm}: no receipt directory", ""


def measured(root: str | Path, window: str = WINDOW) -> dict[str, str]:
    """Every arm with a measurement in any window -> the directory that carries it."""
    out: dict[str, str] = {}
    for win in window_dirs(root, window):
        for arm_dir in glob.glob(os.path.join(win, "*/")):
            arm = os.path.basename(arm_dir.rstrip("/"))
            if ".prev-" in arm or arm in out:
                continue
            ok, reason = done(arm_dir)
            if ok:
                out[arm] = arm_dir.rstrip("/")
            elif reason:
                print(f"unmeasured: {reason}", file=sys.stderr)
    return out