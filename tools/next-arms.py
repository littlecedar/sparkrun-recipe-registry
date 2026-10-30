#!/usr/bin/env python3
"""next-arms.py — what should be on the free nodes right now?

An idle free node with a runnable arm in the queue is a defect, the same class as a node left
holding a finished container. Noticing it by hand is how it gets missed: on 2026-10-30 `.35`
sat empty for an hour while the queue held work, because the census step reported "nothing
live (no reservation)" and nobody turned that into a launch.

So this answers the question directly. It reads three things and prints one launch line per
free node:

  * which nodes are free      — container count 0 on each, over ssh
  * what is already measured  — a receipt carrying `ladder.json`, `ladder.transcribed.json`,
                                `house.json` or any `*.yaml` under `~/benchmarks/tp12-*/<arm>/`
  * what is runnable now     — the campaign manifest, filtered by `tp` (a TP=2 arm needs two
                                free nodes) and by an explicit `--skip` list for arms that are
                                known dead (a proven-negative, a broken upload)

Nodes come from `--nodes`/`$STAGE_NODES`: this file is tracked and the registry forbids cluster
addresses in tracked text.

    python3 tools/next-arms.py --nodes <a>,<b> --skip nex-n2.5-mini-uncensored-nvfp4-sglang

Exit codes: 0 printed a plan for every free node; 1 at least one free node has no runnable arm
(an honest "the queue is dry", not an error); 2 the tool could not run.

Stdlib only.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys

MANIFEST = ".scratch/tp12-campaign/manifest.json"
RECEIPTS = "benchmarks/tp12-*"
MEASURED_ARTEFACTS = ("ladder.json", "ladder.transcribed.json", "house.json", "house.transcribed.txt")
#: Arms whose recipes live under these paths are measured by instruments the runner now
#: supports end to end, so they are ordinary candidates.
ANY_TP = (1, 2)


def sh(argv: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except (subprocess.SubprocessError, OSError):
        return 2, ""
    return p.returncode, p.stdout.strip()


def free_nodes(nodes: list[str]) -> list[str]:
    """Nodes with no container at all. A node mid-teardown is not free."""
    free = []
    for node in nodes:
        rc, out = sh(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", f"red@{node}",
                      "docker ps -aq | wc -l"])
        if rc == 0 and out.strip() == "0":
            free.append(node)
    return free


def measured_arms(home: str, windows: tuple[str, ...] = (RECEIPTS,)) -> set[str]:
    """Arms whose receipt already carries a machine-readable artefact.

    `windows` exists so a test can point at a temp tree without globbing the real receipts.
    """
    done: set[str] = set()
    for win in (w for pattern in windows for w in glob.glob(os.path.join(home, pattern))):
        for arm_dir in glob.glob(os.path.join(win, "*/")):
            arm = os.path.basename(arm_dir.rstrip("/"))
            if ".prev-" in arm:
                continue
            if any(os.path.exists(os.path.join(arm_dir, f)) for f in MEASURED_ARTEFACTS):
                done.add(arm)
            elif glob.glob(os.path.join(arm_dir, "*.yaml")):
                done.add(arm)
    return done


def candidates(manifest: str, done: set[str], skip: set[str], free_count: int) -> list[dict]:
    try:
        entries = json.load(open(manifest))
    except (OSError, ValueError):
        return []
    if not isinstance(entries, list):
        return []
    out = []
    for entry in entries:
        arm = entry.get("arm") or ""
        if not arm or arm in skip:
            continue
        if any(d == arm or d in arm or arm in d for d in done):
            continue
        tp = entry.get("tp")
        if tp not in ANY_TP:
            continue
        if isinstance(tp, int) and tp > free_count:
            continue
        out.append(entry)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Print a launch line per free node.")
    ap.add_argument("--nodes", default=os.environ.get("STAGE_NODES", ""),
                    help="comma-separated free-node candidates (or $STAGE_NODES)")
    ap.add_argument("--manifest", default=MANIFEST)
    ap.add_argument("--home", default=os.path.expanduser("~"),
                    help="where the tp12-* receipt windows live (default: $HOME)")
    ap.add_argument("--skip", action="append", default=[],
                    help="arm to exclude (dead upload, proven negative); repeatable")
    ap.add_argument("--json", action="store_true", help="machine-readable plan")
    args = ap.parse_args(argv)

    nodes = [n.strip() for n in args.nodes.split(",") if n.strip()]
    if not nodes:
        print("no nodes: pass --nodes a,b or set $STAGE_NODES", file=sys.stderr)
        return 2

    free = free_nodes(nodes)
    done = measured_arms(args.home)
    # The queue is a property of the fleet, not of the moment: ask what is runnable at the
    # fleet's real capacity (two free nodes) and report that even when none is free, so an
    # idle node never hides a backlog and a full fleet still shows what comes next.
    todo = candidates(args.manifest, done, set(args.skip), max(len(nodes), 2))
    ready = [e for e in todo if isinstance(e.get("tp"), int) and e["tp"] <= len(free)] or []

    plan = []
    for node, entry in zip(free, ready):
        plan.append({
            "node": node,
            "arm": entry.get("arm"),
            "path": entry.get("path"),
            "tp": entry.get("tp"),
            "launch": f"./tools/run-arm.sh {entry.get('path')} {node}",
        })

    if args.json:
        print(json.dumps({"free_nodes": free, "measured": len(done), "plan": plan}, indent=2))
    else:
        print(f"free nodes: {', '.join(free) if free else 'none'}")
        print(f"measured arms on disk: {len(done)} | unmeasured in manifest: {len(todo)}"
              f" | runnable on {len(free)} free node(s): {len(ready)}")
        for row in plan:
            print(f"  {row['node']}  (TP={row['tp']})  {row['arm']}")
            print(f"      {row['launch']}")
        if len(free) > len(plan):
            for node in free[len(plan):]:
                print(f"  {node}  -- NOTHING RUNNABLE. The queue is dry for this node count,")
                print("            so either widen the manifest or record that fact on the board.")

    return 0 if len(plan) == len(free) else 1


if __name__ == "__main__":
    sys.exit(main())