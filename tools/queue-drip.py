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

Four gates stand between a plan and a launch:

  * `.local/fleet-window.lock` — a declared window means hands off, no matter how idle a node looks.
    The legacy `.scratch/` path is still read: syncthing's `**/.scratch` ignore means a lock written
    there never leaves the clone that wrote it, which is how a window declared on the head was invisible
    to every other checkout (measured 2026-10-30).
  * an active campaign — the director (`campaign/sparkrun_campaign`) holds hosts through leases in
    `<CAMPAIGN_ROOT>/state.json` and never writes that lock, so a gate that honoured only the lock would
    plan a second boot onto a leased host. Roots come from `--campaign-root` and the head's
    `~/.config/sparkrun-campaign.env` (`CAMPAIGN_ROOT`); a host under a live lease or an outstanding reap
    is not free, and state that cannot be read is a refusal — "free" is a claim about state somebody read.
  * fleet lease ledger — `.local/fleet-leases.json`, written by the director and by `director lease`
    (a manual session's claim). A live, unexpired record holds its hosts and is refused with the holder's
    name; an expired one holds nothing. A `fenced` record holds its hosts permanently — a production
    serve's ranks, refused by name until the record is deleted. This tool reads the ledger and never
    writes it — the writer is the director. A ledger that cannot be read is a refusal, like state that cannot.
  * a receipt already carrying numbers — `next-arms.py` owns that predicate; this does not re-derive it.
  * this tool's own ledger (`.local/drip-state.json`) — an arm launched a minute ago has a receipt
    directory with no numbers in it yet, so the receipt predicate cannot see it.  Pids are checked
    with `kill(pid, 0)`: ESRCH is dead, EPERM is alive (a different user's process is not reclaimable).

Run it on the **head**, not a workstation: the receipt predicate reads `~/benchmarks/tp12-*`, and off
the head that set is empty, so every already-measured arm looks unmeasured.  A driver that dies
without its trap (SIGKILL) leaves its container running -- bash defers a TERM trap until the
foreground command returns, and a spinning instrument can hold it forever -- so after killing one by
hand, `sparkrun stop <task-id>` the container it left behind or the node never frees.

Usage
-----
    tools/queue-drip.py --once --dry-run     # what would launch now
    tools/queue-drip.py                      # loop forever
    tools/queue-drip.py --campaign-root ~/benchmarks/campaign-x --once --dry-run
    setsid nohup tools/queue-drip.py >/tmp/drip.log 2>&1 &

Exit codes: 0 pass (or dry run) completed, 2 unusable config (including campaign state or a lease
ledger that could not be read), 3 a declared window or a live lease holds the nodes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOL = REPO / "tools" / "next-arms.py"
#: Canonical first, legacy second. `.local/` is synced (git-ignored, so untracked) while `.scratch/`
#: is in syncthing's ignore list -- a lock there is host-local, and a coordination mechanism one host
#: can see is not a coordination mechanism.
LOCK_PATHS = (REPO / ".local" / "fleet-window.lock", REPO / ".scratch" / "fleet-window.lock")
#: The fleet lease ledger (`campaign/sparkrun_campaign/leases.py` owns the format and the writers).
LEDGER = REPO / ".local" / "fleet-leases.json"
STATE = REPO / ".local" / "drip-state.json"
LOGDIR = REPO / ".local" / "drip-logs"
#: The director's run definition on the head (`campaign/DESIGN.md` §Supervision): one
#: `CAMPAIGN_ROOT=<dir>` line among the manifest and host set. Untracked because it carries addresses,
#: so it is read for the root only; absent on a clone with no campaign installed, which is not an error.
CAMPAIGN_ENV = Path.home() / ".config" / "sparkrun-campaign.env"

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


#: `run-arm.sh <recipe> <node>` -- argv carries the recipe path, which is the exact key the plan
#: uses, so a match needs no name parsing.
_DRIVER = re.compile(r"run-arm\.sh\s+(\S+\.yaml)")


def pid_is_driver(pid: int, arm: str, path: str = "") -> bool:
    """A live pid is only ours if its command line still says so.

    A pid number alone is not identity: once a finished arm's pid is recycled by an unrelated head
    process, the entry reads "in flight" forever and that arm is never launched again -- a silent
    stall of exactly the kind the ledger exists to prevent.
    """
    if not pid_alive(pid):
        return False
    try:
        cmd = Path(f"/proc/{pid}/cmdline").read_bytes().decode("utf-8", "replace")
    except OSError:
        return False
    # argv elements, not a substring of the flattened cmdline: `arm in cmd` matches any arm whose
    # name is a prefix of another's, and the 2026-10-29 ledger kept two finished arms "in flight"
    # this way. `/proc/<pid>/cmdline` is NUL-separated, so split it instead of trusting the join.
    argv = [a for a in cmd.split("\0") if a]
    if not any(os.path.basename(a) == "run-arm.sh" for a in argv):
        return False
    if path:
        # The ledger recorded the recipe path, and that is what the driver's argv carries.
        return any(a == path or os.path.basename(a) == os.path.basename(path) for a in argv)
    # A ledger row written before `path` was recorded carries only the arm name, while the live
    # driver's argument is `recipes/<lane>/<arm>.yaml`. Compare stems, not substrings: exactness
    # was too strict here (a real driver read as dead on 2026-10-30 and its arm was nearly
    # re-planned onto the node already running it), and `in` was too loose.
    return any(os.path.splitext(os.path.basename(a))[0] == arm for a in argv)


def in_flight(state: dict) -> dict:
    return {
        arm: ent for arm, ent in state.items()
        if pid_is_driver(int(ent.get("pid") or 0), arm, ent.get("path") or "")
    }


def live_driver_paths() -> set:
    """Recipe paths with a driver process right now, whoever started it.

    The ledger only knows what this tool launched, and the receipt predicate only sees arms that
    already have numbers -- so an arm a human started a minute ago is invisible to both and would be
    launched a second time on the next free node. The processes are the truth; `ps` is cheap.
    """
    out = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True, check=False)
    return {m.group(1) for m in _DRIVER.finditer(out.stdout)}


def drop_in_flight(plan: list, running: dict, drivers: set = frozenset()) -> list:
    return [
        row for row in plan
        if row.get("arm") not in running and row.get("path") not in drivers
    ]


def in_flight_arms(drivers: set) -> set:
    """Arm names for every live driver, so the planner can pass over them and reach the next arm.

    Dropping an in-flight row after the fact leaves a free node idle: the plan holds one row per
    free node, so a dropped row is a lost slot. Excluding them at the planner instead lets the next
    queued arm take that slot, which is the whole point of the loop.
    """
    return {Path(path).stem for path in drivers}


def plan_pass(cfg: dict, busy: set = frozenset(), nodes: list | None = None) -> list:
    cmd = [sys.executable, str(TOOL), "--nodes", ",".join(nodes or cfg["research"]), "--json"]
    for arm in sorted(set(cfg["skip"]) | set(busy)):
        cmd += ["--skip", arm]
    out = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, check=False)
    if out.returncode == 2:
        raise ConfigError(out.stderr.strip() or "next-arms.py refused to plan")
    if out.returncode not in (0, 1):
        raise ConfigError(f"next-arms.py exited {out.returncode}: {out.stderr.strip()}")
    return json.loads(out.stdout).get("plan", [])


def hosts_of(row: dict) -> list[str]:
    """Every node a plan row occupies. A TP=2 row carries `nodes`; older rows carry `node`."""
    return list(row.get("nodes") or ([row["node"]] if row.get("node") else []))


def launch(row: dict) -> int:
    LOGDIR.mkdir(parents=True, exist_ok=True)
    log = LOGDIR / f"{row['arm']}.log"
    with open(log, "ab") as fh:
        proc = subprocess.Popen(
            shlex.split(row["launch"]),
            cwd=REPO,
            env={**os.environ, **(row.get("env") or {})},
            stdout=fh,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    return proc.pid


def declared_window() -> Path | None:
    """The lock path that holds a declaration, or None."""
    return next((p for p in LOCK_PATHS if p.exists()), None)


def campaign_roots(env: Path, extra: list) -> list:
    """Every campaign root a pass must honour: `--campaign-root` first, then the head's env file.

    A missing env file is the truth -- this tool also runs on clones with no campaign installed -- while
    an unreadable one is an error: it may name a root, and refusing beats guessing whose hosts are free.
    """
    roots = list(extra)
    try:
        text = env.read_text(encoding="utf-8")
    except FileNotFoundError:
        return roots
    except OSError as exc:
        raise ConfigError(f"cannot read {env}: {exc}") from exc
    for raw in text.splitlines():
        if raw.strip().startswith("CAMPAIGN_ROOT="):
            value = raw.split("=", 1)[1].strip().strip("'\"")
            if value:
                roots.append(Path(value).expanduser())
    return roots


def campaign_holders(roots: list, now: float) -> dict:
    """host -> why it is held, read from each root's `state.json` without the director's lock.

    Two of the director's own records hold hosts: a lease that has not expired owns its declared hosts,
    and a record that still `needs_reap` owns the hosts its leftovers may sit on. An expired lease holds
    nothing -- the director's `expire()` clears it -- and a root with no `state.json` is absent, not
    broken. Anything else is a refusal: "free" is a claim about state somebody read.
    """
    held: dict = {}
    for root in roots:
        path = Path(root) / "state.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue
        except (OSError, ValueError) as exc:
            raise ConfigError(f"cannot read campaign state {path}: {exc}") from exc
        try:
            name = data.get("campaign") or str(root)
            arms = data["arms"]
            records = list(arms.items())
        except (AttributeError, KeyError, TypeError) as exc:
            raise ConfigError(f"{path} is not a campaign state document: {exc}") from exc
        for arm, record in records:
            lease = record.get("lease")
            if lease:
                expiry = float(lease.get("expires_at") or 0)
                if expiry > now:
                    when = time.strftime("%H:%M:%S", time.localtime(expiry))
                    for host in lease.get("hosts") or []:
                        held.setdefault(host, f"campaign {name} holds {host} -- {arm} attempt "
                                              f"{record.get('attempts')}, lease expires {when}")
            for host in record.get("needs_reap") or []:
                held.setdefault(host, f"campaign {name} holds {host} -- {arm} still needs a reap "
                                      f"({record.get('status')})")
    return held


def ledger_holders(path: Path, now: float) -> dict:
    """host -> why it is held, read from the fleet lease ledger without the writer's lock.

    The ledger is the current claim path (a campaign lease or `director lease`), and the declared-window
    lock it replaces holds every host the same way. A record that has not expired owns its hosts; an
    expired one holds nothing, and a missing ledger is absent, not broken. Anything else is a refusal:
    "free" is a claim about state somebody read.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise ConfigError(f"cannot read lease ledger {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("leases"), list):
        raise ConfigError(f"{path} is not a lease ledger (no `leases` list)")
    if not isinstance(data.get("fenced", []), list):
        raise ConfigError(f"{path}: `fenced` must be a list of fence records")
    held: dict = {}
    # A fence is a production serve's rank: permanent until its record is deleted, never expired.
    for fence in data.get("fenced") or []:
        if not isinstance(fence, dict):
            continue
        for host in fence.get("hosts") or ():
            held.setdefault(host, f"fence: {fence.get('reason') or 'no reason recorded'} "
                                  f"(fenced by {fence.get('fenced_by') or '?'} at "
                                  f"{fence.get('fenced_at') or '?'})")
    for record in data["leases"]:
        if not isinstance(record, dict):
            continue
        try:
            expiry = float(record.get("expires_at") or 0)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{path} carries a lease with an unreadable expiry: "
                              f"{record.get('id')!r}") from exc
        if expiry <= now:
            continue
        when = time.strftime("%H:%M:%S", time.localtime(expiry))
        for host in record.get("hosts") or ():
            held.setdefault(host, f"lease {record.get('id') or '?'} held by "
                                  f"{record.get('holder') or '?'}, until {when}")
    return held


def free_nodes(nodes: list, held: dict) -> list:
    """The nodes this session may use right now.

    Hosts are compared literally: `.local/fleet.yaml` and `CAMPAIGN_HOSTS` both carry the management-plane
    address form (verified 2026-11-07). A name on one side and an address on the other is a hole here, not
    a match -- so the fleet file is the wrong place to rename a node.
    """
    return [node for node in nodes if node not in held]


def drop_held(plan: list, held: dict) -> list:
    """Never launch onto a held host, even if the planner was handed the wrong node list."""
    return [row for row in plan if not set(hosts_of(row)) & set(held)]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=REPO / ".local" / "fleet.yaml")
    ap.add_argument("--state", type=Path, default=STATE)
    ap.add_argument("--once", action="store_true", help="one pass, then exit")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, launch nothing")
    ap.add_argument("--campaign-root", type=Path, action="append", default=[], metavar="ROOT",
                    help="campaign root whose state.json may hold hosts (repeatable); the root in "
                         "--campaign-env is always read too")
    ap.add_argument("--campaign-env", type=Path, default=CAMPAIGN_ENV, metavar="FILE",
                    help=f"file naming CAMPAIGN_ROOT (default {CAMPAIGN_ENV})")
    ap.add_argument("--ledger", type=Path, default=LEDGER, metavar="FILE",
                    help=f"fleet lease ledger whose live records hold hosts (default {LEDGER})")
    args = ap.parse_args(argv)

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"drip: {exc}", file=sys.stderr)
        return 2

    while True:
        declared = declared_window()
        if declared is not None:
            print(f"drip: {declared} is present -- a window is declared, hands off")
            return 3
        try:
            now = time.time()
            held = campaign_holders(campaign_roots(args.campaign_env, args.campaign_root), now)
            # The ledger is the current claim path and the state file the older one; a host either
            # holds is held, and the campaign's own reason wins where both name it.
            for host, why in ledger_holders(args.ledger, now).items():
                held.setdefault(host, why)
            free = free_nodes(cfg["research"], held)
            if not free:
                for why in sorted(set(held.values())):
                    print(f"drip: {why}")
                print("drip: every node this session may use is held -- hands off")
                return 3
            for node in cfg["research"]:
                if node in held:
                    print(f"drip: {held[node]}")
            state = read_state(args.state)
            running = in_flight(state)
            drivers = live_driver_paths()
            plan = drop_held(
                drop_in_flight(plan_pass(cfg, in_flight_arms(drivers), free), running, drivers), held)
        except ConfigError as exc:
            print(f"drip: {exc}", file=sys.stderr)
            return 2

        if not plan:
            print(f"drip: nothing to launch ({len(running)} arm(s) already in flight)")
        for row in plan:
            if args.dry_run:
                print(f"drip: would launch {row['arm']} on {','.join(hosts_of(row))}")
                continue
            pid = launch(row)
            state[row["arm"]] = {
                "pid": pid, "node": row["node"], "nodes": hosts_of(row),
                "path": row.get("path") or "",
                "started": int(time.time()),
            }
            args.state.parent.mkdir(parents=True, exist_ok=True)
            live = in_flight(state)
            args.state.write_text(json.dumps(live, indent=2) + "\n", encoding="utf-8")
            print(f"drip: launched {row['arm']} on {','.join(hosts_of(row))} pid={pid}")
        if args.once or args.dry_run:
            return 0
        time.sleep(cfg["poll_seconds"])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))