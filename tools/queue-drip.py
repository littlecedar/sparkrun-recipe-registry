#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Keep a free research node busy without a human in the loop.

Why this file exists
--------------------
`tools/run-arm.sh` owns one arm end to end (boot, cells, stop) and
`tools/next-arms.py` answers "what should be on the free nodes now?".  Neither keeps the queue
moving: between arms the nodes idle until somebody notices, which is how `.35` once sat empty for an
hour with a full manifest.  This is that missing loop.

It never decides *which* nodes it may use.  That is a config file of this session's own
(`.local/fleet.yaml`, untracked by design, so it can hold addresses and the tracked tree cannot), and
it must be explicit: an empty or unreadable `research:` list is an error, never "nothing to do".

Three gates stand between a plan and a launch:

  * `.scratch/fleet-window.lock` — a declared window means hands off, no matter how idle a node looks.
  * a receipt already carrying numbers — `next-arms.py` owns that predicate; this does not re-derive it.
  * this tool's own ledger (`.local/drip-state.json`) — an arm launched a minute ago has a receipt
    directory with no numbers in it yet, so the receipt predicate cannot see it.  Pids are checked
    with `kill(pid, 0)`: ESRCH is dead, EPERM is alive (a different user's process is not reclaimable).

Usage
-----
    tools/queue-drip.py --once --dry-run     # what would launch now
    tools/queue-drip.py                      # loop forever
    setsid nohup tools/queue-drip.py >/tmp/drip.log 2>&1 &

Exit codes: 0 pass (or dry run) completed, 2 unusable config, 3 a declared window is open.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOL = REPO / "tools" / "next-arms.py"
LOCK = REPO / ".scratch" / "fleet-window.lock"
STATE = REPO / ".local" / "drip-state.json"
LOGDIR = REPO / ".local" / "drip-logs"

#: Fail closed on an unknown key: a typo such as `reseearch:` would otherwise parse as no nodes at
#: all and read exactly like a fleet with nothing to do.
KNOWN_KEYS = {"research", "skip", "poll_seconds"}


class ConfigError(RuntimeError):
    """The config cannot be used. Never degrade to an empty node list."""


def load_config(path: Path) -> dict:
    """Parse the small YAML subset a fleet file is: `key: value`, `key:` + `- item` lists."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    cfg: dict = {}
    key = None
    for raw in text.splitlines():
        line = "" if raw.lstrip().startswith("#") else raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.lstrip().startswith("- "):
            if key is None:
                raise ConfigError(f"{path}: list item before any key: {raw!r}")
            if not isinstance(cfg.get(key), list):
                raise ConfigError(f"{path}: {key} is a scalar, not a list: {raw!r}")
            cfg[key].append(line.lstrip()[2:].strip())
            continue
        if ":" not in line:
            raise ConfigError(f"{path}: not `key: value`: {raw!r}")
        key, value = line.split(":", 1)
        key = key.strip()
        if key in cfg:
            raise ConfigError(f"{path}: {key} appears twice")
        cfg[key] = value.strip() if value.strip() else []
    unknown = set(cfg) - KNOWN_KEYS
    if unknown:
        raise ConfigError(f"{path}: unknown key(s) {sorted(unknown)}; known: {sorted(KNOWN_KEYS)}")
    nodes = cfg.get("research")
    if not isinstance(nodes, list) or not nodes:
        raise ConfigError(f"{path}: `research:` must list at least one node this session may use")
    cfg["research"] = [n for n in nodes if n]
    cfg.setdefault("skip", [])
    cfg["poll_seconds"] = int(cfg.get("poll_seconds") or 300)
    return cfg


def pid_alive(pid: int) -> bool:
    """ESRCH means gone; EPERM means someone else's process, which is alive and none of our business.

    pid 0 and 1 are never an arm: `os.kill(0, 0)` signals the whole process GROUP and succeeds, so a
    ledger entry with no recorded pid would otherwise block its arm forever.
    """
    if pid <= 1:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except ValueError as exc:
        raise ConfigError(f"{path} is not valid JSON: {exc}") from exc


def in_flight(state: dict) -> dict:
    return {arm: ent for arm, ent in state.items() if pid_alive(int(ent.get("pid") or 0))}


def drop_in_flight(plan: list, running: dict) -> list:
    return [row for row in plan if row.get("arm") not in running]


def plan_pass(cfg: dict) -> list:
    cmd = [sys.executable, str(TOOL), "--nodes", ",".join(cfg["research"]), "--json"]
    for arm in cfg["skip"]:
        cmd += ["--skip", arm]
    out = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, check=False)
    if out.returncode == 2:
        raise ConfigError(out.stderr.strip() or "next-arms.py refused to plan")
    if out.returncode not in (0, 1):
        raise ConfigError(f"next-arms.py exited {out.returncode}: {out.stderr.strip()}")
    return json.loads(out.stdout).get("plan", [])


def launch(row: dict) -> int:
    LOGDIR.mkdir(parents=True, exist_ok=True)
    log = LOGDIR / f"{row['arm']}.log"
    with open(log, "ab") as fh:
        proc = subprocess.Popen(
            shlex.split(row["launch"]),
            cwd=REPO,
            stdout=fh,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    return proc.pid


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=REPO / ".local" / "fleet.yaml")
    ap.add_argument("--state", type=Path, default=STATE)
    ap.add_argument("--once", action="store_true", help="one pass, then exit")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, launch nothing")
    args = ap.parse_args(argv)

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"drip: {exc}", file=sys.stderr)
        return 2

    while True:
        if LOCK.exists():
            print(f"drip: {LOCK} is present -- a window is declared, hands off")
            return 3
        try:
            state = read_state(args.state)
            running = in_flight(state)
            plan = drop_in_flight(plan_pass(cfg), running)
        except ConfigError as exc:
            print(f"drip: {exc}", file=sys.stderr)
            return 2

        if not plan:
            print(f"drip: nothing to launch ({len(running)} arm(s) already in flight)")
        for row in plan:
            if args.dry_run:
                print(f"drip: would launch {row['arm']} on {row['node']}")
                continue
            pid = launch(row)
            state[row["arm"]] = {"pid": pid, "node": row["node"], "started": int(time.time())}
            args.state.parent.mkdir(parents=True, exist_ok=True)
            args.state.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
            print(f"drip: launched {row['arm']} on {row['node']} pid={pid}")
        if args.once or args.dry_run:
            return 0
        time.sleep(cfg["poll_seconds"])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))