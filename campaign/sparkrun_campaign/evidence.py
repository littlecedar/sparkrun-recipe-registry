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
#: `run-arm.sh`'s metrics scrape, written before teardown: one `metrics-status.txt` carrying a
#: `# runtime=… port=…` line then one `<status> host=… container=… url=… reason=…` line per host,
#: and one `metrics-<host>.txt` per host whose first line repeats that verdict and whose body is
#: the raw Prometheus exposition. Read directly, never through the marker: `marker_fields()` drops
#: every flat key of a `sparkrun_benchmark` sidecar, so a sidecar-shaped arm would lose the field.
METRICS_STATUS = "metrics-status.txt"
_METRICS_FILES = "metrics-*.txt"
_METRICS_LINE = re.compile(r"^(captured|absent|no_probe|wrong_port)\s+(.*)$")
#: Severity order `run-arm.sh` aggregates with: an unverifiable probe outranks a wrong listener,
#: which outranks a capture, which outranks "the engine exposes nothing".
_METRICS_RANK = {"absent": 0, "captured": 1, "wrong_port": 2, "no_probe": 3}
#: The flat marker's own keys. A house.yaml carrying only `sparkrun_benchmark` is sparkrun's nested
#: sidecar instead: it has no ladder/accuracy field, and reading one into existence would be a
#: fabricated verdict.
FLAT_KEYS = frozenset({"suite", "ladder", "accuracy_status"})
#: The nested sidecar sparkrun's benchmark writes: one top-level mapping, outcome under
#: `benchmark` / `results`.
SIDECAR = "sparkrun_benchmark"
#: `client/client.json`, the arm-scoped extra client's own receipt.
CLIENT = ("client", "client.json")
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


_NESTED_KEY = re.compile(r"^( +)([A-Za-z_][A-Za-z0-9_]*):[ \t]*(.*)$")


def _nested_scalars(lines: list[str]) -> dict[str, str]:
    """``a.b.c: value`` for scalar keys under a top-level mapping, keyed by their indent path."""
    out: dict[str, str] = {}
    stack: list[tuple[int, str]] = []
    for line in lines:
        found = _NESTED_KEY.match(line)
        if not found:
            continue
        indent, key, value = len(found.group(1)), found.group(2), found.group(3).strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        path = ".".join([name for _, name in stack] + [key])
        value = value.strip("'").strip()
        if value:
            out[path] = value
        else:
            stack.append((indent, key))
    return out


def marker_fields(arm_dir: str | Path) -> dict[str, str] | None:
    """Outcome fields of ``house.yaml``, plus the shape they were read from.

    Two shapes reach an arm directory and both are legitimate:

    * ``run-arm``'s flat marker -- ``suite`` / ``ladder`` / ``accuracy_status`` at column 0.
    * sparkrun's nested ``sparkrun_benchmark`` sidecar -- ``benchmark`` and ``results`` nested,
      with no ladder field at all. It is reported as ``house_score`` + ``suite`` and the reply says
      ``shape: sparkrun_benchmark``; inventing a ``ladder: ok`` for it would let a sidecar that
      records a failed run read as measured.

    An unreadable, contradictory, or third-shape marker raises: a guess of "measured" leaves an
    arm that must be re-run, and a guess of "not measured" re-boots an arm that has its numbers.
    """
    path = Path(arm_dir) / MARKER
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise EvidenceError(f"{path}: {exc}") from exc
    lines = text.splitlines()
    flat: dict[str, str] = {}
    for line in lines:
        found = _TOP_KEY.match(line)
        if not found:
            continue
        key, value = found.group(1), found.group(2).strip()
        if key in flat and flat[key] != value:
            raise EvidenceError(f"{path}: {key} appears twice ({flat[key]!r} and {value!r})")
        flat[key] = value
    if SIDECAR in flat:
        nested = _nested_scalars(lines)
        fields = {"shape": SIDECAR}
        if nested.get("benchmark.profile"):
            fields["suite"] = nested["benchmark.profile"]
        if nested.get("benchmark.framework"):
            fields["framework"] = nested["benchmark.framework"]
        if nested.get("results.json.final_score"):
            fields["house_score"] = nested["results.json.final_score"]
        return fields
    if not flat.keys() & FLAT_KEYS:
        raise EvidenceError(f"{path}: neither a run-arm marker nor a {SIDECAR} sidecar")
    flat["shape"] = "run-arm"
    return flat


def client_receipt(arm_dir: str | Path) -> dict[str, object] | None:
    """The arm-scoped extra client's own receipt (``client/client.json``), or None."""
    path = Path(arm_dir).joinpath(*CLIENT)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EvidenceError(f"{path}: {exc.__class__.__name__}") from exc
    if not isinstance(data, dict):
        raise EvidenceError(f"{path}: a {type(data).__name__}, not a client receipt")
    return {
        "cell": str(data.get("cell") or ""),
        "image_id": str(data.get("image_id") or ""),
        "rc": data.get("rc"),
    }


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


def _ladder_rows(path: Path) -> int | None:
    """Rows in a ladder artefact's first cell table, or None when the file is not one."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for key in CELL_KEYS:
            table = data.get(key)
            if isinstance(table, list) and table:
                return len(table)
    return None


def ladder_status(arm_dir: str | Path) -> str:
    """The receipt's ``ladder`` field: the marker's verdict, or the artefact's own truth.

    A ``sparkrun_benchmark`` sidecar has no ladder field, so a receipt that copied only the marker
    left ``ladder: ""`` beside ``measured: true`` while ``ladder.json`` held seven rows -- real
    numbers the receipt looked like it had lost (2026-11-08, the 753B second boot; the cells were
    recovered from the CSV). So the field is never a blank: the artefact carrying the cells is
    named with its row count, and a missing or broken artefact says so in the field. This is a
    receipt field, not the verdict -- ``done()`` still decides measurability, and a sidecar's own
    house score can measure an arm whose ladder is absent without the ladder reading as ``ok``.
    """
    fields = marker_fields(arm_dir) or {}
    verdict = fields.get("ladder", "")
    if verdict:
        return verdict
    for name in LADDERS:
        path = Path(arm_dir) / name
        if not path.exists():
            continue
        problem = measurement_problem(arm_dir)
        if problem:
            return f"not a measurement — {problem}"
        rows = _ladder_rows(path)
        return f"measured — {name} ({rows} rows)" if rows is not None else f"measured — {name}"
    return "absent — no ladder artefact in this receipt"


def _metrics_verdict(line: str) -> dict[str, str] | None:
    """One scrape line as ``{status, host, url, reason}``, or None for a comment/other line."""
    found = _METRICS_LINE.match(line.strip())
    if not found:
        return None
    rest = found.group(2)
    host = re.search(r"\bhost=(\S+)", rest)
    url = re.search(r"\burl=(\S+)", rest)
    reason = re.search(r"\breason=(.*)$", rest)
    return {
        "status": found.group(1),
        "host": host.group(1) if host else "",
        "url": url.group(1) if url else "",
        "reason": reason.group(1).strip() if reason else "",
    }


def _metrics_body(arm_dir: str | Path, host: str) -> bool:
    """Did this host's own artifact carry anything beyond its verdict line?"""
    if not host:
        return False
    path = Path(arm_dir) / f"metrics-{host}.txt"
    try:
        _, _, body = path.read_text(encoding="utf-8", errors="replace").partition("\n")
    except OSError:
        return False
    return bool(body.strip())


def metrics_status(arm_dir: str | Path) -> dict[str, object] | None:
    """The receipt's ``metrics_status`` field: the arm's metrics scrape, or None when it left none.

    A sibling reader to ``client_receipt`` for a sibling artifact: it reads
    ``metrics-status.txt`` (a ``# runtime=… port=…`` line, then one
    ``<status> host=<h> container=<c> url=<u> reason=<r>`` line per host) plus the matching
    ``metrics-<host>.txt`` files, whose first line repeats the verdict and whose body is the raw
    Prometheus exposition. ``run-arm.sh`` writes it before teardown, from inside the arm's own
    container, because ``--rm`` takes the socket with the container.

    Never through the marker: ``marker_fields()`` returns only a synthesised ``shape``/``suite``/
    ``framework``/``house_score`` dict for a ``sparkrun_benchmark`` sidecar, so a flat metrics key
    beside it would be discarded and that arm would read metrics-less.

    Statuses are ``captured`` / ``absent`` / ``no_probe`` / ``wrong_port``; the aggregate is the
    highest-severity host verdict (``no_probe`` > ``wrong_port`` > ``captured`` > ``absent``), the
    same ranking the scrape uses. A ``captured`` verdict is only reported as captured when the
    host's own artifact actually carries a body: the aggregate over empty bodies is the one shape
    a later reader would take for data, so it reads ``disagrees`` with both sides named instead.
    ``None`` means *no artifact* -- not ``absent``, which is an engine that exposed nothing.
    """
    only = Path(arm_dir) / METRICS_STATUS
    source = only.name
    try:
        if only.exists():
            lines = only.read_text(encoding="utf-8", errors="replace").splitlines()
        else:
            source = _METRICS_FILES
            lines = []
            for path in sorted(Path(arm_dir).glob(_METRICS_FILES)):
                if path.name == METRICS_STATUS:
                    continue
                lines.append(path.read_text(encoding="utf-8", errors="replace").split("\n", 1)[0])
    except OSError as exc:
        return {"status": "", "reason": f"unreadable metrics artifact: {exc}",
                "hosts": 0, "captured": 0}
    verdicts = [verdict for verdict in map(_metrics_verdict, lines) if verdict]
    if not verdicts:
        if not only.exists() and source == _METRICS_FILES:
            return None
        return {"status": "", "reason": f"no host verdict in {source}", "hosts": 0, "captured": 0}
    top = max(verdicts, key=lambda verdict: _METRICS_RANK[verdict["status"]])
    declared = [verdict for verdict in verdicts if verdict["status"] == "captured"]
    witnessed = sum(1 for verdict in declared if _metrics_body(arm_dir, verdict["host"]))
    if declared and witnessed < len(declared):
        return {"status": "disagrees",
                "reason": (f"{source} records captured on {len(declared)} host(s), but "
                           f"{witnessed} of {len(verdicts)} host artifacts carried a body"),
                "hosts": len(verdicts), "captured": witnessed}
    detail = " ".join(part for part in (top["url"], top["reason"]) if part and part != "-")
    return {"status": top["status"], "reason": detail or "no reason",
            "hosts": len(verdicts), "captured": witnessed}


def done(arm_dir: str | Path) -> tuple[bool, str]:
    """(measured, reason). A reason is always produced, so a non-receipt is visible in the log."""
    arm = Path(str(arm_dir).rstrip("/")).name
    try:
        fields = marker_fields(arm_dir)
    except EvidenceError as exc:
        return False, f"{arm}: marker unreadable, not measured: {exc}"
    problem = measurement_problem(arm_dir)
    if (fields or {}).get("shape") == SIDECAR:
        # No ladder field exists in this shape; the score or a non-empty cell table is the
        # witness. Never synthesise one -- the receipt keeps ladder/accuracy empty and says
        # which shape it read.
        if problem:
            return False, f"{arm}: {SIDECAR} sidecar, but the ladder artefact is not a measurement: {problem}"
        if any((Path(arm_dir) / name).exists() for name in LADDERS) or (fields or {}).get("house_score"):
            return True, ""
        return False, f"{arm}: {SIDECAR} sidecar carries no house score and no ladder cell; not measured"
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