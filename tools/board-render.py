#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Render the whole `mad-science/STATUS.md` from evidence, the register and `git log`.

Why this exists.  Half the board was already deterministic (`task-queue.py render --board`), and
the other half was re-derived by a model every hour from a 382 KB base: ~100 k tokens of existing
text to emit ~10 KB of cells, with the arithmetic done by hand (a hardcoded direction word came
out inverted against its own parsed deltas, 2026-11-17).  This tool derives every cell: the
`## In flight` rows from one census evidence document, the `## Work queue` block from the
register through `task-queue.py`'s own `board_rows`/`graph_body`, and the `## Landed session`
rows from `git log`, filtered to the rolling window the section states.

Landed is a rolling day, not history: the window starts at
`max(base census stamp, census − 24 h)`, so an hourly tick shows its own interval, a tick after a
gap shows the last day rather than replaying the gap, and the table's first line names the start
it used.  Older rows live in git and `SESSION-RECORD.md`.

Usage:
    tools/board-render.py --evidence .local/board-evidence/<ISO>.json \
        [--prev <previous evidence>] [--register mad-science/queue.json] [--repo .] [--out -]

`--prev` supplies the base for the deltas; without it the `delta` block recorded inside the
evidence document is used, so a lone evidence file still renders its measurements.

Every cell is derived: no count, direction word or sha is written into this file.  The output is
refused (exit 1) when it fails `lint_markdown`, `address_problems` or `inflight_problems`, the
guards `task-queue.py publish` applies, so a renderer defect cannot reach the board.

Stdlib only, no third-party imports; `task-queue.py` and `board-census.py` are imported by path,
the convention the other dash-named tools use.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOL = REPO / "tools" / "task-queue.py"

try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:  # no tzdata: a fixed EST stamp is still a clock, and the title says ET
    _ET = timezone(timedelta(hours=-5))

_FORBIDDEN_HOST = re.compile(r"spark-(?:head|0[0-9])")


def _module(name: str, path: Path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module  # dash-named tool convention
        spec.loader.exec_module(module)
    return sys.modules[name]


def _task_queue():
    return _module("task_queue", TOOL)


def _census_tool():
    return _module("board_census", REPO / "tools" / "board-census.py")


def _cell(text) -> str:
    return " ".join(str(text).split()).replace("|", r"\|")


def _f(number) -> str:
    return "—" if number is None else f"{int(number):,}"


def _delta(number) -> str:
    return "no base" if number is None else f"{int(number):+,}"


def _direction(number) -> str:
    if number is None:
        return "unmeasured"
    return "rose" if number > 0 else "fell" if number < 0 else "unchanged"


def _parse(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def _interval(start, end) -> str:
    if not start or not end:
        return "no base"
    seconds = int((_parse(end) - _parse(start)).total_seconds())
    sign = "-" if seconds < 0 else ""
    seconds = abs(seconds)
    return f"{sign}{seconds // 3600} h {(seconds % 3600) // 60} min {seconds % 60} s"


def _stamp(epoch) -> str:
    return datetime.fromtimestamp(int(epoch), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _host(name) -> str:
    name = str(name or "?")
    return "—" if _FORBIDDEN_HOST.fullmatch(name) else name


def _fence_hosts(evidence: dict) -> set[str]:
    ledger = (evidence.get("head") or {}).get("lease_ledger") or {}
    return {host for fence in ledger.get("fenced") or [] for host in fence.get("hosts") or []}


def _node_reads(evidence: dict) -> tuple[str, str]:
    reads = sorted(node["read"] for node in (evidence.get("nodes") or {}).values()
                   if isinstance(node, dict) and node.get("read"))
    return (reads[0], reads[-1]) if reads else ("unknown", "unknown")


def _deltas(evidence: dict, prev: dict | None) -> dict:
    """Per-label deltas: recomputed from `--prev`, or the block the census recorded."""
    if prev is None:
        return {label: node.get("delta") or {}
                for label, node in (evidence.get("nodes") or {}).items()
                if isinstance(node, dict)}
    return _census_tool().deltas(evidence.get("nodes") or {}, prev.get("nodes") or {})


# ---------------------------------------------------------------- In flight rows

def census_row(evidence: dict) -> tuple[str, str]:
    nodes = {label: node for label, node in (evidence.get("nodes") or {}).items()
             if isinstance(node, dict)}
    good = {label: node for label, node in nodes.items() if "error" not in node}
    first, last = _node_reads(evidence)
    base = evidence.get("base")
    containers = sum(node.get("containers_all") or 0 for node in good.values())
    volumes = sum(node.get("volumes") or 0 for node in good.values())
    fenced = _fence_hosts(evidence)
    running = sorted(label for label, node in good.items() if node.get("containers_running"))
    research = [label for label in running if label not in fenced]
    held = [label for label in running if label in fenced]

    parts = [f"read `{first}`–`{last}` (each node's own `date -u`) on the base census "
             f"`{base or 'none'}`, **{_interval(base, first)}** after it: "
             f"**{_f(containers)} containers, {_f(volumes)} volumes** fleet-wide"]
    if research:
        parts.append("**research rank** on " + ", ".join(f"`{label}`" for label in research))
    else:
        parts.append("**no research rank**")
    if held:
        parts.append("the fenced hosts hold running containers on "
                     + ", ".join(f"`{label}`" for label in held)
                     + ", excluded from research accounting")
    served = [(label, node["serve"]) for label, node in sorted(good.items()) if node.get("serve")]
    if served:
        parts.append("; ".join(
            f"`/v1/models` **{serve.get('models')}**, `/health` **{serve.get('health')}** "
            f"on `{label}`" for label, serve in served))
    else:
        parts.append("no node probed a serve")
    missing = sorted(label for label, node in nodes.items() if "error" in node)
    if missing:
        parts.append("**no answer** from " + ", ".join(f"`{label}`" for label in missing))
    return ("read-only in tick — booted nothing, claimed nothing, stopped nothing, evicted nothing",
            "; ".join(parts))


def pool_row(evidence: dict) -> tuple[str, str]:
    head = evidence.get("head") or {}
    units = head.get("units") or {}
    if "error" in head or not units:
        return ("— (nobody drives it; head units re-proved each tick)",
                "**unread** — the head's unit states were not collected in this census")
    restarts = (head.get("delta") or {}).get("restarts") or {}
    cells = []
    for name in ("beegfs-mgmtd", "beegfs-meta", "beegfs-storage"):
        unit = units.get(name)
        if not unit:
            continue
        delta = restarts.get(name)
        tail = f", **{_delta(delta)}** on the base" if delta is not None else ""
        cells.append(f"`{name}` **{unit.get('active')}** (Result {unit.get('result')}, "
                     f"NRestarts {_f(unit.get('restarts'))}{tail})")
    what = ("head: " + " · ".join(cells) if cells else "**no unit state read**")
    what += ("; worker unit states and the pool's through-mount reads are not part of this "
             "census")
    return ("— (nobody drives it; head units re-proved each tick)", what)


def queue_row(evidence: dict) -> tuple[str, str]:
    register = evidence.get("register") or {}
    sha = register.get("sha256") or ""
    head_sha = (evidence.get("head") or {}).get("register_sha256")
    tasks = register.get("tasks") or 0
    done = register.get("done") or 0
    what = (f"`{register.get('path') or 'mad-science/queue.json'}` sha256 **`{sha or 'unread'}`** "
            f"read locally: **{_f(tasks)} tasks: {_f(done)} done, {_f(register.get('queued'))} "
            f"queued, {_f(register.get('blocked'))} blocked, {_f(register.get('running'))} "
            f"running — {_f(tasks - done)} open**")
    if head_sha:
        same = "identical" if head_sha == sha else "**differs**"
        what += f"; the head clone reads **`{head_sha[:8]}…`**, {same}"
    elif "error" in (evidence.get("head") or {}):
        what += "; the head clone's register was not read"
    return (f"register snapshot `{(sha or 'unread')[:8]}…`; both blocks below rendered from it",
            what)


def window_row(evidence: dict) -> tuple[str, str]:
    head = evidence.get("head") or {}
    lock = head.get("window_lock")
    if not lock:
        return ("**not collected** at this read",
                "`.local/fleet-window.lock` was not read in this census")
    if not lock.get("present"):
        return ("**no manual lock** at this read",
                "`.local/fleet-window.lock` is **absent** on the head"
                + (f" (read `{head['read']}`)" if head.get("read") else ""))
    return ("**manual lock held**",
            f"`.local/fleet-window.lock` is present on the head: **{_f(lock.get('size'))} B**, "
            f"mtime **`{lock.get('mtime')}`** local")


def campaign_row(evidence: dict) -> tuple[str, str]:
    head = evidence.get("head") or {}
    campaign = head.get("campaign")
    ledger = head.get("lease_ledger") or {}
    leases = ledger.get("leases") or []
    fences = ledger.get("fenced") or []
    if not campaign:
        return ("`sparkrun-campaign` — state not read",
                "the campaign unit's state was not collected in this census")
    delta = (head.get("delta") or {}).get("campaign_restarts")
    tail = f", **{_delta(delta)}** on the base" if delta is not None else ""
    fenced = ", ".join(f"`{fence.get('fenced_by')}`" for fence in fences if fence.get("fenced_by"))
    what = (f"head user unit `sparkrun-campaign` reads **`{campaign.get('active')}`** / "
            f"**`{campaign.get('sub')}`** (`MainPID` **{_f(campaign.get('pid'))}**, `NRestarts` "
            f"**{_f(campaign.get('restarts'))}**{tail}); the lease ledger holds "
            f"**{len(leases)} lease(s)**" + (f" and fence(s) {fenced}" if fenced else ""))
    return (f"`sparkrun-campaign` — {campaign.get('active')}, "
            f"{'no lease' if not leases else f'{len(leases)} lease(s)'}", what)


def lease_row(evidence: dict) -> tuple[str, str]:
    ledger = (evidence.get("head") or {}).get("lease_ledger") or {}
    leases = ledger.get("leases") or []
    fences = ledger.get("fenced") or []
    if not ledger:
        return ("**not collected** at this read",
                "the head's lease ledger was not read in this census")
    cells = []
    for fence in fences:
        hosts = ", ".join(f"`{host}`" for host in fence.get("hosts") or [])
        serve = fence.get("serve") or {}
        cells.append(f"fence **`{fence.get('fenced_by')}`** on {hosts or '—'} "
                     f"(`fenced_at` `{fence.get('fenced_at')}`, "
                     f"{fence.get('reason') or 'no reason recorded'}, serve "
                     f"`{serve.get('task_id')}` / image `{serve.get('image_id')}`)")
    what = (f"the head's repo ledger `.local/fleet-leases.json` "
            f"({_f(ledger.get('size'))} B, sha **`{(ledger.get('sha256') or 'unread')[:8]}…`**, "
            f"mtime **`{ledger.get('mtime')}`** local) holds "
            + ("; ".join(cells) if cells else "no fence")
            + f" and **{len(leases)} lease(s)**")
    return (f"**{len(fences)} fence(s), {len(leases)} lease(s)**", what)


def publication_row(evidence: dict, evidence_name: str) -> tuple[str, str]:
    first, last = _node_reads(evidence)
    register = evidence.get("register") or {}
    base = evidence.get("base")
    what = (f"fresh census (`{first}`–`{last}`) written to `{evidence_name}` and composed on the "
            f"base census `{base or 'none'}`; the queue blocks are rendered from "
            f"`{register.get('path') or 'mad-science/queue.json'}` sha "
            f"**`{(register.get('sha256') or 'unread')[:8]}…`**, and the landed rows from "
            f"`git log --since={base or 'none'}`")
    return ("tick", what)


def node_row(evidence: dict, label: str, delta: dict) -> str:
    node = (evidence.get("nodes") or {}).get(label) or {}
    if "error" in node:
        return f"| {label} | **unreachable** — census error | {_cell(node['error'])} |"
    running = node.get("containers_running") or 0
    if running and label in _fence_hosts(evidence):
        role = "**fenced serve** — excluded from the research census"
    elif running:
        role = f"**live containers** — {running} running, research accounting"
    else:
        role = "**nothing live (no reservation)** — idle"
    first = (f"`{node.get('read')}` (`{_host(node.get('host'))}`): `docker ps -aq` "
             f"**{_f(node.get('containers_all'))}**, running **{_f(running)}**, volumes "
             f"**{_f(node.get('volumes'))}**, `:8000` listeners "
             f"**{_f(node.get('listeners_8000'))}**")
    if node.get("serve"):
        first += (f", `/v1/models` **{node['serve'].get('models')}**, `/health` "
                  f"**{node['serve'].get('health')}**")
    segments = [first]
    root = node.get("root") or {}
    segments.append(f"root **{_f(root.get('avail'))} B avail** ({_delta(delta.get('avail'))}, "
                    f"{_direction(delta.get('avail'))}) · **{_f(root.get('used'))} B used** "
                    f"({_delta(delta.get('used'))}, {_direction(delta.get('used'))})")
    if node.get("btime") is not None:
        segments.append(f"boot **`{_stamp(node['btime'])}`** (`btime`), `uptime` "
                        f"**{_f(node.get('uptime_s'))} s**")
    mem = node.get("mem") or {}
    mem_delta = delta.get("mem") or {}
    segments.append(
        ", ".join(f"`{key}` **{_f(value)} kB** ({_delta(mem_delta.get(key))})"
                  for key, value in mem.items()))
    ring = node.get("ring") or {}
    window = ring.get("window") or {}
    ring_delta = delta.get("ring") or {}
    # Only the ring's size is comparable tick to tick: each tick's in-window count is taken over
    # its own window (this census's base to this read), so subtracting the previous document's
    # count compares two different intervals and would read as a fall that never happened.
    segments.append(
        f"ring **{_f(ring.get('all'))}** events all-types "
        f"({_delta(ring_delta.get('all'))}), **{_f(window.get('lifecycle'))}** in-window "
        f"lifecycle and **{_f(window.get('exec'))}** in-window `exec`, oldest "
        f"`{ring.get('oldest')}`, newest `{ring.get('newest')}`")
    return f"| {label} | {role} | {_cell('<br>'.join(segments))} |"


def live_lease_rows(evidence: dict) -> list[str]:
    ledger = (evidence.get("head") or {}).get("lease_ledger") or {}
    at = _parse(evidence["at"]).timestamp()
    rows = []
    for lease in ledger.get("leases") or []:
        try:
            live = float(lease.get("expires_at") or 0) > at
        except (TypeError, ValueError):
            live = False
        if not live:
            continue
        hosts = ", ".join(f"`{host}`" for host in lease.get("hosts") or []) or "—"
        rows.append(f"| `{lease.get('id') or 'lease'}` | {_cell(lease.get('holder') or '—')} | "
                    f"{hosts} leased"
                    + (f" for `{lease.get('window')}`" if lease.get("window") else "")
                    + f"; expires `{_stamp(lease['expires_at'])}` |")
    return rows


# ---------------------------------------------------------------- Work queue / Landed

#: The Landed table is a rolling day, not history: a tick after a long gap must not replay a week
#: of commits, and a normal hourly tick already covers the last hour.  The window starts at the
#: base census stamp when that is later, so an ordinary tick still shows exactly its own interval.
LANDED_WINDOW = timedelta(hours=24)


def landed_window(evidence: dict) -> tuple[datetime, str, datetime]:
    """(start, which rule won, the rolling start) for the Landed table.

    `max(base census stamp, census − 24 h)`: the base wins on a normal tick (it is the newer
    measurement), the rolling day wins after a gap or on a first run with no base.
    """
    at = _parse(evidence["at"])
    rolling = at - LANDED_WINDOW
    base = evidence.get("base")
    if base and _parse(base) > rolling:
        return _parse(base), "base", rolling
    return rolling, "24h", rolling


def landed_window_line(evidence: dict) -> str:
    """One derived line naming the window, so a reader can tell why older rows are absent."""
    start, rule, rolling = landed_window(evidence)
    stamp = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    if rule == "base":
        return (f"Window: commits since `{stamp}` — the base census stamp, later than the "
                f"24 h start `{rolling.strftime('%Y-%m-%dT%H:%M:%SZ')}`; older rows are not shown.")
    return f"Window: commits since `{stamp}` — the 24 h before this census."


def landed_rows(repo: Path, since: datetime) -> list[str]:
    """Rows for commits authored at or after `since`; the filter is on the date each row shows."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "log", "--format=%h %at %s"],
            capture_output=True, text=True)
    except OSError as exc:
        return [f"| — | — | `git log` unavailable: {_cell(exc)} |"]
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        return [f"| — | — | `git log` failed: {_cell(detail[-1] if detail else proc.returncode)} |"]
    rows = []
    for line in proc.stdout.splitlines():
        fields = line.split(" ", 2)
        if len(fields) != 3:
            continue
        sha, epoch, subject = fields
        if int(epoch) < since.timestamp():
            continue
        when = datetime.fromtimestamp(int(epoch), timezone.utc).astimezone(_ET)
        rows.append(f"| {when.strftime('%m-%d %H:%M')} | `{sha}` | {_cell(subject)} |")
    return list(reversed(rows))


def render(evidence: dict, prev: dict | None, register: Path, repo: Path,
           evidence_name: str) -> str:
    tq = _task_queue()
    data = tq.load(register)
    deltas = _deltas(evidence, prev)
    at = _parse(evidence["at"]).astimezone(_ET)
    title = f"# Board"
    subtitle = f"_Generated {at.strftime('%Y-%m-%d %H:%M')} ET_"

    cells = [census_row(evidence), pool_row(evidence), queue_row(evidence),
             window_row(evidence), campaign_row(evidence), lease_row(evidence),
             publication_row(evidence, evidence_name)]
    keys = ["census", "pool", "queue", "window", "campaign", "lease", "publication"]
    inflight = [f"| {key} | {_cell(owner)} | {_cell(what)} |"
                for key, (owner, what) in zip(keys, cells)]
    inflight += [node_row(evidence, label, deltas.get(label) or {})
                 for label in sorted(evidence.get("nodes") or {})]
    inflight += live_lease_rows(evidence)

    graph, warnings = tq.graph_body(data)
    for warning in warnings:
        print(f"board-render: graph: {warning}", file=sys.stderr)

    lines = [title, subtitle, "",
             "## In flight",
             "| where | owner | what |",
             "|---|---|---|", *inflight,
             "", "## Work Queue", "```mermaid", *graph, "```", "",
             *tq.board_rows(data, register),
             "", "## Completed Work", landed_window_line(evidence), "",
             "| time ET | commit | one clause |", "|---|---|---|",
             *landed_rows(repo, landed_window(evidence)[0])]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render STATUS.md from census evidence.")
    parser.add_argument("--evidence", required=True, help="census evidence JSON")
    parser.add_argument("--prev", help="previous evidence JSON, for the deltas")
    parser.add_argument("--register", default="mad-science/queue.json",
                        help="task register, relative to --repo")
    parser.add_argument("--repo", default=".", help="checkout the register and git log live in")
    parser.add_argument("--out", default="-", help="output path (default: stdout)")
    args = parser.parse_args(argv)

    repo = Path(args.repo)
    register = Path(args.register)
    if not register.is_absolute():
        register = repo / register
    try:
        evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
        prev = json.loads(Path(args.prev).read_text(encoding="utf-8")) if args.prev else None
    except (OSError, ValueError) as exc:
        print(f"board-render: cannot read its inputs: {exc}", file=sys.stderr)
        return 1
    try:
        text = render(evidence, prev, register, repo, Path(args.evidence).name)
    except Exception as exc:  # a QueueError from the register, or a malformed evidence document
        print(f"board-render: {exc}", file=sys.stderr)
        return 1

    tq = _task_queue()
    problems = ([(line, rule, detail) for line, rule, detail in tq.lint_markdown(text)]
                + [(line, "cluster-address", hit) for line, hit in tq.address_problems(text)]
                + list(tq.inflight_problems(text)))
    if problems:
        for line, rule, detail in problems:
            print(f"board-render:{line}: {rule}: {detail}", file=sys.stderr)
        return 1
    if args.out == "-":
        sys.stdout.write(text)
    else:
        Path(args.out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
