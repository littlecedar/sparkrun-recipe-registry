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

#: Receipt directories are usually named after the recipe, but a few were hand-named earlier in
#: the campaign. Exact matching plus this table is deliberate: substring matching once let
#: `zz-ornith-1.5-122b-nvfp4-sglang` mask `zz-ornith-1.5-122b-nvfp4-dflash2-sglang` and report
#: "nothing runnable", which is the failure this tool exists to prevent.
ALIASES = {
    "aeon-cyber": "qwen3.8-27b-aeon-ultimate-nvfp4-sglang",
    "ling-3.0": "ling-3.0-flash-int4-dspark-sglang",
    "nemotron": "nemotron-3.5-lightning-30b-a3b-nvfp4-vllm",
    "ornith-122b-mtp": "zz-ornith-1.5-122b-nvfp4-mtp-vllm",
    "qwen3-coder-next": "qwen3-coder-next-int4-autoround-vllm",
    "qwen38-27b-dflash2": "qwen3.8-27b-nvfp4-dflash2-sglang",
    "qwen38-27b-uncensored": "qwen3.8-27b-uncensored-nvfp4-sglang",
}
#: The table reads receipt-dir -> recipe arm, because that is how the dirs were named; the check
#: needs the other direction.
RECEIPT_FOR = {recipe: directory for directory, recipe in ALIASES.items()}


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
        # No pipe: `docker ps -aq | wc -l` turns a docker failure -- daemon down, socket permission,
        # anything -- into a confident "0 containers", and a node the probe cannot inspect would be
        # handed a launch. Reading docker's own exit status fails closed instead.
        rc, out = sh(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", f"red@{node}",
                      "docker ps -aq"])
        if rc == 0 and not out.strip():
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


class ManifestError(RuntimeError):
    """The manifest could not be read. Never silently "nothing to do"."""


def place(free: list[str], todo: list[dict]) -> tuple[list[dict], list[dict]]:
    """Place arms on the free nodes, pairs included.

    A TP=2 arm takes TWO nodes and is launched once with both hosts, so a plan can be shorter
    than the node list without anything being idle. Leaving pairs unplaceable made every
    free-node report read "NOTHING RUNNABLE" while seven TP=2 arms waited -- the direction is
    to keep unfenced nodes busy, not to keep them busy with TP=1 work only.

    Order matters: whichever arm sorts first takes the nodes it needs, so a pair that fits the
    remaining nodes is placed before a single-node arm can strand one of them.
    """
    remaining = list(free)
    rows: list[dict] = []
    pairs_unplaced: list[dict] = []
    for entry in todo:
        tp = entry.get("tp")
        need = 2 if tp == 2 else 1
        if tp not in (1, 2):
            continue
        if len(remaining) < need:
            if tp == 2:
                pairs_unplaced.append(entry)
            continue
        hosts = remaining[:need]
        del remaining[:need]
        rows.append({
            "nodes": hosts,
            "node": hosts[0],
            "arm": entry.get("arm"),
            "path": entry.get("path"),
            "tp": tp,
            "launch": f"./tools/run-arm.sh {entry.get('path')} {','.join(hosts)}",
            # Per-arm instrument env travels with the arm: `run-arm.sh` reads these from its own
            # environment, and a JEV arm's decision head differs per model.
            "env": entry.get("env") or {},
        })
    return rows, pairs_unplaced


def candidates(manifest: str, done: set[str], skip: set[str], free_count: int) -> list[dict]:
    try:
        with open(manifest, encoding="utf-8") as fh:
            entries = json.load(fh)
    except OSError as exc:
        raise ManifestError(f"cannot read {manifest}: {exc}") from exc
    except ValueError as exc:
        raise ManifestError(f"{manifest} is not valid JSON: {exc}") from exc
    if not isinstance(entries, list):
        raise ManifestError(f"{manifest} must hold a list of arms")
    out = []
    for entry in entries:
        arm = entry.get("arm") or ""
        if not arm or arm in skip:
            continue
        if arm in done or RECEIPT_FOR.get(arm) in done:
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
    try:
        todo = candidates(args.manifest, done, set(args.skip), max(len(nodes), 2))
    except ManifestError as exc:
        print(f"cannot plan: {exc}", file=sys.stderr)
        return 2
    # Placement is one arm per free node, so only TP=1 is placeable here. A TP=2 arm handed a
    # single host would either refuse or silently serve at TP=1 -- a wrong measurement, not a
    # wrong guess -- so those are reported as a pair backlog instead of being planned.
    plan, pairs = place(free, todo)

    # Computed before the branch, not inside it: the exit status depends on it and `--json` is
    # how queue-drip calls this tool, so a value defined only for humans fails every drip pass
    # with an UnboundLocalError that reads like a planner refusal.
    placed = {n for row in plan for n in row["nodes"]}
    stranded = [n for n in free if n not in placed]

    if args.json:
        print(json.dumps({"free_nodes": free, "measured": len(done), "plan": plan}, indent=2))
    else:
        print(f"free nodes: {', '.join(free) if free else 'none'}")
        print(f"measured arms on disk: {len(done)} | unmeasured in manifest: {len(todo)}"
              f" | runnable on {len(free)} free node(s): {len(plan)}")
        # Exclusion accounting: "nothing runnable" must be explainable.
        if args.skip:
            print(f"  excluded by --skip: {', '.join(sorted(args.skip))}")
        if pairs:
            print(f"  TP=2 waiting: {len(pairs)} arm(s) need two free nodes together, and")
            print("               fewer than two were free:")
            for entry in pairs[:4]:
                print(f"                 {entry.get('arm')}")
        for row in plan:
            label = ",".join(row["nodes"]) if row["tp"] == 2 else row["node"]
            print(f"  {label}  (TP={row['tp']})  {row['arm']}")
            print(f"      {row['launch']}")
        for node in stranded:
            print(f"  {node}  -- NOTHING RUNNABLE. The queue is dry for this node count,")
            print("            so either widen the manifest or record that fact on the board.")

    return 0 if not stranded else 1


if __name__ == "__main__":
    sys.exit(main())