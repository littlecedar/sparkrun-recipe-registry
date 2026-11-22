#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Read-only fleet census for the status board: one evidence document per tick.

Why this exists.  The board's numbers came from a throwaway probe script written into a
per-tick scratch directory and parsed by a compose script written in the same tick, so nothing
kept the probe set, the schema or the arithmetic: every hour re-derived them, and a
transcription slip could reach the board (a 60 000 B phantom delta, 2026-11-09).  This tool is
that probe, fixed.  It collects the same reads, writes them as one documented JSON document,
and computes the deltas against the previous document.

Usage:
    tools/board-census.py [--out DIR] [--prev FILE] [--node HOST ...] [--timeout S]

Read-only.  Nothing is started, stopped, claimed or evicted.  Every remote call is one
`ssh -n` with a short timeout, and the remote script is base64-fed on the command line because
`ssh -n host bash -s < script` discards the redirect: the remote runs an empty script and exits
0, which reads exactly like an idle fleet.

Evidence schema, version 1, at `<out>/<YYYY-MM-DDTHHMMSSZ>.json`:

    {
      "version": 1,
      "at":      "<ISO8601 Z, when the census was collected>",
      "base":    "<the previous census stamp, or null>",
      "nodes":   {"<label>": {                      # ".30" .. ".35" for the fleet
          "read": "<ISO8601 Z>", "host": "<hostname>",
          "containers_all": 0, "containers_running": 0, "volumes": 0,
          "listeners_8000": 0,
          "root": {"size": 0, "used": 0, "avail": 0},                       # bytes
          "mem":  {"MemTotal": 0, "MemAvailable": 0, "Cached": 0, "AnonPages": 0},  # kB
          "btime": 0, "uptime_s": 0,
          "ring": {"all": 0, "oldest": "...", "newest": "...",
                   "window": {"lifecycle": 0, "exec": 0}},
          "serve": {"models": 200, "health": 200},   # null where nothing listens on :8000
          "delta": {...}                             # null without a previous document
      }},
      "head": {                                     # the first --node
          "read": "...",
          "units": {"beegfs-mgmtd": {"active": "active", "result": "success", "restarts": 0}, ...},
          "campaign": {"active": "active", "sub": "running", "pid": 1, "restarts": 0},
          "window_lock": {"present": false} | {"present": true, "size": 0, "mtime": "..."},
          "lease_ledger": {"sha256": "...", "size": 0, "mtime": "...",
                           "leases": [{"id": ..., "hosts": [".31", ...], "expires_at": 0, ...}],
                           "fenced": [{"fenced_by": ..., "hosts": [".31", ...], ...}]},
          "register_sha256": "...",
          "delta": {"restarts": {"beegfs-meta": 0}, "campaign_restarts": 0}
      },
      "register": {"path": "mad-science/queue.json", "sha256": "...", "tasks": 0,
                   "done": 0, "queued": 0, "blocked": 0, "running": 0},
      "notes": ["..."]                              # partial reads, stated not hidden
    }

`delta` is `null` without a previous document.  Otherwise, per node, it carries the difference
from the previous document's node: `avail` and `used` (bytes), `mem` (kB, per field), `uptime_s`,
`containers_all`, `containers_running`, `volumes`, `listeners_8000`, and `ring` (`all`,
`window_lifecycle`, `window_exec`); the head carries `restarts` per unit and `campaign_restarts`.

A node that fails to answer is `{"error": "..."}` in its entry, never a crash.  The census exits
non-zero only when it cannot write the evidence file.

Stdlib only, no third-party imports.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shlex
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REGISTER = REPO / "mad-science" / "queue.json"
VERSION = 1
#: Built at run time on purpose: this file is tracked, and a cluster address must not be.
DEFAULT_NODES = [f"10.0.4.{octet}" for octet in range(30, 36)]
DEFAULT_TIMEOUT = 30

#: `$1` is the mode token, `$2` the label, `$3` the base census stamp (empty on a first run).
#: The in-window event read needs its window defined *inside* the remote script: a variable set
#: in a caller is unset here, and `grep -c` then reports 0 on a ring full of execs.
NODE_SCRIPT = r'''
L="$2"; BASE="$3"
NOW=$(date -u +%FT%TZ)
echo "node|$L|ts=$NOW"
echo "host|$L|$(hostname)"
echo "uptime|$L|$(awk '{print int($1)}' /proc/uptime)"
echo "btime|$L|$(awk '/^btime/{print $2}' /proc/stat)"
awk -v L="$L" '/^MemTotal:|^MemAvailable:|^Cached:|^AnonPages:/{k=$1; sub(":","",k); print "mem|" L "|" k "=" $2}' /proc/meminfo
echo "psaq|$L|$(docker ps -aq | wc -l)"
echo "psrun|$L|$(docker ps -q | wc -l)"
echo "vols|$L|$(docker volume ls -q | wc -l)"
L8000=$(ss -ltn 2>/dev/null | awk '$4 ~ /:8000$/ {c++} END{print c+0}')
echo "listeners|$L|$L8000"
echo "root|$L|$(df -B1 --output=size,used,avail / | awk 'NR==2{print $1","$2","$3}')"
T=$(mktemp); W=$(mktemp); : > "$W"
docker events --since 1970-01-01T00:00:00Z --until "$NOW" > "$T" 2>/dev/null
if [ -n "$BASE" ]; then docker events --since "$BASE" --until "$NOW" > "$W" 2>/dev/null; fi
echo "ring|$L|total=$(wc -l < "$T")"
echo "ring|$L|oldest=$(sed -n '1p' "$T" | cut -c1-60)"
echo "ring|$L|newest=$(sed -n '$p' "$T" | cut -c1-60)"
echo "win|$L|lifecycle=$(awk '$2=="container" && $3 ~ /^(create|start|kill|die|destroy|rename|oom|pause|unpause):/' "$W" | wc -l)"
echo "win|$L|exec=$(awk '$2=="container" && $3 ~ /^exec_/' "$W" | wc -l)"
rm -f "$T" "$W"
if [ "$(docker ps -q | wc -l)" -gt 0 ] && [ "$L8000" -gt 0 ]; then
  echo "serve|$L|models=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:8000/v1/models)"
  echo "serve|$L|health=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:8000/health)"
fi
'''

#: Head extras: unit states, the lease ledger and its summary, the campaign unit, the window
#: lock, and the head clone's register sha.  The lock is read because the board's `window` row
#: is a required key and must be derived, never remembered.
HEAD_SCRIPT = r'''
R="$HOME/src/sparkrun-recipe-registry"
echo "head|ts=$(date -u +%FT%TZ)"
# `systemctl show -p A,B,C --value` prints in the unit's own property order, not the requested
# one (measured: `Result NRestarts ActiveState`), so each property is asked for by name.
for u in beegfs-mgmtd beegfs-meta beegfs-storage; do
  printf 'unit|%s|%s,%s,%s\n' "$u" \
    "$(systemctl show -p ActiveState --value "$u")" \
    "$(systemctl show -p Result --value "$u")" \
    "$(systemctl show -p NRestarts --value "$u")"
done
echo "campaign|$(systemctl --user show -p ActiveState --value sparkrun-campaign),$(systemctl --user show -p SubState --value sparkrun-campaign),$(systemctl --user show -p MainPID --value sparkrun-campaign),$(systemctl --user show -p NRestarts --value sparkrun-campaign)"
LEDGER="$R/.local/fleet-leases.json"
echo "ledger_sha|$(sha256sum "$LEDGER" 2>/dev/null | awk '{print $1}')"
echo "ledger_stat|$(stat -c '%s %y' "$LEDGER" 2>/dev/null)"
echo "ledger_body|$(base64 -w0 "$LEDGER" 2>/dev/null)"
echo "register_sha|$(sha256sum "$R/mad-science/queue.json" 2>/dev/null | awk '{print $1}')"
LOCK="$R/.local/fleet-window.lock"
if [ -e "$LOCK" ]; then echo "window_lock|$(stat -c '%s|%y' "$LOCK")"; else echo "window_lock|absent"; fi
'''


def label_for(host: str) -> str:
    """`.NN` for an IPv4 host, the host itself otherwise (tests use names)."""
    parts = host.split(".")
    if len(parts) == 4 and parts[3].isdigit():
        return f".{parts[3]}"
    return host


def run_remote(host: str, script: str, args: list[str], timeout: float) -> str:
    """One `ssh -n` hop running `script` remotely; raises RuntimeError with the last stderr line."""
    remote = "printf %s {} | base64 -d | bash -s -- {}".format(
        base64.b64encode(script.encode()).decode(),
        " ".join(shlex.quote(arg) for arg in args))
    try:
        proc = subprocess.run(
            ["ssh", "-n", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={int(timeout)}",
             host, remote], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"{host}: no reply in {timeout} s") from None
    except OSError as exc:
        raise RuntimeError(f"{host}: {exc}") from None
    if proc.returncode != 0:
        lines = (proc.stderr or proc.stdout).strip().splitlines()
        raise RuntimeError(f"{host}: {lines[-1] if lines else f'exit {proc.returncode}'}")
    return proc.stdout


def _kv(value: str) -> tuple[str, str]:
    key, _, rest = value.partition("=")
    return key, rest


def parse_node(label: str, out: str) -> dict:
    """One node's probe reply -> its evidence entry; raises when the reply carries no stamp."""
    entry: dict = {
        "read": None, "host": None, "containers_all": 0, "containers_running": 0,
        "volumes": 0, "listeners_8000": 0, "root": {}, "mem": {}, "btime": None,
        "uptime_s": None, "ring": {"all": 0, "oldest": None, "newest": None,
                                   "window": {"lifecycle": 0, "exec": 0}},
        "serve": None,
    }
    for line in out.splitlines():
        kind, sep, rest = line.partition("|")
        if not sep:
            continue
        got_label, sep, value = rest.partition("|")
        if not sep or got_label != label:
            continue
        if kind == "node":
            entry["read"] = _kv(value)[1]
        elif kind == "host":
            entry["host"] = value.strip()
        elif kind == "uptime":
            entry["uptime_s"] = int(value)
        elif kind == "btime":
            entry["btime"] = int(value)
        elif kind == "mem":
            key, number = _kv(value)
            entry["mem"][key] = int(number)
        elif kind == "psaq":
            entry["containers_all"] = int(value)
        elif kind == "psrun":
            entry["containers_running"] = int(value)
        elif kind == "vols":
            entry["volumes"] = int(value)
        elif kind == "listeners":
            entry["listeners_8000"] = int(value)
        elif kind == "root":
            size, used, avail = (int(part) for part in value.split(","))
            entry["root"] = {"size": size, "used": used, "avail": avail}
        elif kind == "ring":
            key, number = _kv(value)
            key = "all" if key == "total" else key  # the probe's `total` is the ring's size
            entry["ring"][key] = number if key in ("oldest", "newest") else int(number)
        elif kind == "win":
            key, number = _kv(value)
            entry["ring"]["window"][key] = int(number)
        elif kind == "serve":
            key, number = _kv(value)
            entry["serve"] = entry["serve"] or {}
            entry["serve"][key] = int(number)
    if not entry["read"]:
        raise RuntimeError("reply carries no census stamp")
    return entry


def parse_head(out: str) -> dict:
    """The head probe reply -> the evidence `head` object."""
    head: dict = {"read": None, "units": {}, "campaign": None, "window_lock": None,
                  "lease_ledger": None, "register_sha256": None}
    ledger_sha = ledger_stat = ledger_body = None
    for line in out.splitlines():
        kind, sep, value = line.partition("|")
        if not sep:
            continue
        value = value.strip()
        if kind == "head":
            head["read"] = _kv(value)[1]
        elif kind == "unit":
            name, _, fields = value.partition("|")
            active, result, restarts = (fields.split(",") + ["", "", ""])[:3]
            head["units"][name] = {"active": active, "result": result,
                                   "restarts": int(restarts or 0)}
        elif kind == "campaign":
            active, sub, pid, restarts = (value.split(",") + ["", "", "", ""])[:4]
            head["campaign"] = {"active": active, "sub": sub, "pid": int(pid or 0),
                                "restarts": int(restarts or 0)}
        elif kind == "ledger_sha":
            ledger_sha = value or None
        elif kind == "ledger_stat":
            ledger_stat = value
        elif kind == "ledger_body":
            ledger_body = value
        elif kind == "register_sha":
            head["register_sha256"] = value or None
        elif kind == "window_lock":
            if value == "absent" or not value:
                head["window_lock"] = {"present": False}
            else:
                size, _, mtime = value.partition("|")
                head["window_lock"] = {"present": True, "size": int(size or 0),
                                       "mtime": mtime}
    if ledger_sha or ledger_stat:
        ledger: dict = {"sha256": ledger_sha, "size": None, "mtime": None,
                        "leases": [], "fenced": []}
        if ledger_stat:
            size, _, mtime = ledger_stat.partition(" ")
            ledger["size"], ledger["mtime"] = int(size or 0), mtime
        if ledger_body:
            try:
                data = json.loads(base64.b64decode(ledger_body))
            except (ValueError, TypeError):
                data = {}
            ledger["leases"] = [_lease(record) for record in data.get("leases") or []
                                if isinstance(record, dict)]
            ledger["fenced"] = [_fence(record) for record in data.get("fenced") or []
                                if isinstance(record, dict)]
        head["lease_ledger"] = ledger
    if not head["read"]:
        raise RuntimeError("reply carries no head stamp")
    return head


def _labels(hosts) -> list[str]:
    return [label_for(str(host)) for host in hosts or ()]


def _lease(record: dict) -> dict:
    out = {key: record.get(key) for key in
           ("id", "holder", "window", "expires_at", "claimed_at", "arm", "recipe")}
    out["hosts"] = _labels(record.get("hosts"))
    return out


def _fence(record: dict) -> dict:
    out = {key: record.get(key) for key in ("fenced_by", "fenced_at", "reason", "serve")}
    out["hosts"] = _labels(record.get("hosts"))
    return out


def _diff(now, was):
    if isinstance(now, bool) or isinstance(was, bool):
        return None
    if isinstance(now, (int, float)) and isinstance(was, (int, float)):
        return now - was
    return None


def deltas(nodes: dict, prev_nodes: dict) -> dict:
    """Per-label difference from the previous evidence's nodes; `None` where a side is missing."""
    out: dict = {}
    for label, now in nodes.items():
        was = (prev_nodes or {}).get(label)
        if not isinstance(now, dict) or "error" in now or not isinstance(was, dict) or "error" in was:
            out[label] = None
            continue
        now_root, was_root = now.get("root") or {}, was.get("root") or {}
        now_ring, was_ring = now.get("ring") or {}, was.get("ring") or {}
        now_win, was_win = now_ring.get("window") or {}, was_ring.get("window") or {}
        out[label] = {
            "containers_all": _diff(now.get("containers_all"), was.get("containers_all")),
            "containers_running": _diff(now.get("containers_running"), was.get("containers_running")),
            "volumes": _diff(now.get("volumes"), was.get("volumes")),
            "listeners_8000": _diff(now.get("listeners_8000"), was.get("listeners_8000")),
            "avail": _diff(now_root.get("avail"), was_root.get("avail")),
            "used": _diff(now_root.get("used"), was_root.get("used")),
            "uptime_s": _diff(now.get("uptime_s"), was.get("uptime_s")),
            "mem": {key: _diff(value, (was.get("mem") or {}).get(key))
                    for key, value in (now.get("mem") or {}).items()},
            "ring": {
                "all": _diff(now_ring.get("all"), was_ring.get("all")),
                "window_lifecycle": _diff(now_win.get("lifecycle"), was_win.get("lifecycle")),
                "window_exec": _diff(now_win.get("exec"), was_win.get("exec")),
            },
        }
    return out


def head_delta(head: dict, prev_head: dict) -> dict | None:
    if not isinstance(head, dict) or "error" in head or not isinstance(prev_head, dict):
        return None
    prev_units = prev_head.get("units") or {}
    restarts = {}
    for name, unit in (head.get("units") or {}).items():
        was = (prev_units.get(name) or {}).get("restarts")
        restarts[name] = _diff(unit.get("restarts"), was)
    prev_campaign = (prev_head.get("campaign") or {}).get("restarts")
    return {"restarts": restarts,
            "campaign_restarts": _diff((head.get("campaign") or {}).get("restarts"),
                                       prev_campaign)}


def register_summary(path: Path) -> dict:
    """sha256 and state counts of the local register; an unreadable one is an error, not a crash."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return {"path": str(path), "error": str(exc)}
    try:
        data = json.loads(raw)
    except ValueError as exc:
        return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "error": str(exc)}
    tasks = [task for task in data.get("tasks") or [] if isinstance(task, dict)]
    counts = Counter(task.get("state") for task in tasks)
    try:
        shown = str(path.relative_to(REPO))
    except ValueError:
        shown = str(path)
    return {"path": shown, "sha256": hashlib.sha256(raw).hexdigest(), "tasks": len(tasks),
            "done": counts.get("done", 0), "queued": counts.get("queued", 0),
            "blocked": counts.get("blocked", 0), "running": counts.get("running", 0)}


def newest_before(directory: Path, name: str) -> Path | None:
    """The newest `*.json` in `directory` whose name sorts before `name` (names are ISO stamps)."""
    try:
        names = sorted(entry.name for entry in directory.glob("*.json") if entry.name < name)
    except OSError:
        return None
    return directory / names[-1] if names else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only fleet census for the status board.")
    parser.add_argument("--out", default=str(REPO / ".local" / "board-evidence"),
                        help="evidence directory (default: .local/board-evidence)")
    parser.add_argument("--prev", help="previous evidence file (default: newest older one)")
    parser.add_argument("--node", action="append", help="fleet host, repeatable")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                        help=f"per-hop ssh ceiling in seconds (default {DEFAULT_TIMEOUT})")
    args = parser.parse_args(argv)

    hosts = args.node or DEFAULT_NODES
    out_dir = Path(args.out)
    at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    name = at.replace(":", "") + ".json"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"board-census: cannot create {out_dir}: {exc}", file=sys.stderr)
        return 1
    target = out_dir / name

    notes: list[str] = []
    prev_path = Path(args.prev) if args.prev else newest_before(out_dir, name)
    prev: dict | None = None
    if prev_path:
        try:
            prev = json.loads(prev_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            notes.append(f"previous evidence {prev_path} unreadable: {exc}")
    base = None
    if isinstance(prev, dict):
        reads = [node.get("read") for node in (prev.get("nodes") or {}).values()
                 if isinstance(node, dict) and node.get("read")]
        base = min(reads) if reads else prev.get("at")

    nodes: dict = {}
    for host in hosts:
        label = label_for(host)
        try:
            nodes[label] = parse_node(
                label, run_remote(host, NODE_SCRIPT, ["node", label, base or ""], args.timeout))
        except Exception as exc:  # a node that cannot answer is one row, never the census
            nodes[label] = {"error": str(exc)}
            notes.append(str(exc))

    try:
        head = parse_head(run_remote(hosts[0], HEAD_SCRIPT, ["head"], args.timeout))
    except Exception as exc:
        head = {"error": str(exc)}
        notes.append(str(exc))

    if isinstance(prev, dict):
        for label, delta in deltas(nodes, prev.get("nodes") or {}).items():
            if label in nodes and isinstance(nodes[label], dict):
                nodes[label]["delta"] = delta
        if "error" not in head:
            head["delta"] = head_delta(head, prev.get("head") or {})

    document = {"version": VERSION, "at": at, "base": base, "nodes": nodes, "head": head,
                "register": register_summary(REGISTER), "notes": notes}
    try:
        target.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"board-census: cannot write {target}: {exc}", file=sys.stderr)
        return 1
    print(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
