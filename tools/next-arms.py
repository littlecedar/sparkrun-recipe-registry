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
                                `house.json`, `house.transcribed.txt` or `quality.json` (the
                                normalised `ARM_EXTRA_CLIENT` cell, content-checked)
                                under `~/benchmarks/tp12-*/<arm>/`
  * what is runnable now     — the campaign manifest, filtered by `tp` (a TP=2 arm needs two
                                free nodes) and by an explicit `--skip` list for arms that are
                                known dead (a proven-negative, a broken upload)

and one thing more, because a node window is the scarce resource: the **recorded verdicts**, which
travel inside the recipe they refuse. A refused arm carries
`metadata.measured_rejected: "<date> — <reason> (<doc>:<line>)"`, so a rename or a retirement to
`attic/` carries the verdict with it and deleting the recipe deletes the hold. Such an arm is
never placed, and the plan prints `skip: <arm> (<verdict>, <doc>:<line>)` so the reason is
checkable without reading this tool: a lane doc already recording a negative is the whole
evidence, and re-booting it buys nothing. A marker that does not parse, or whose cited `path:line`
no longer resolves (a doc rewrite moved the line the verdict was recorded on), gates with exit 2
— the one failure the marker's own location cannot prevent.

Nodes come from `--nodes`/`$STAGE_NODES`: this file is tracked and the registry forbids cluster
addresses in tracked text.

    python3 tools/next-arms.py --nodes <a>,<b> --skip nex-n2.5-mini-uncensored-nvfp4-sglang

Exit codes: 0 printed a plan for every free node; 1 at least one free node has no runnable arm
(an honest "the queue is dry", not an error); 2 the tool could not run — including a verdict
marker that does not parse, repeats itself, or cites a `path:line` that no longer resolves.

Stdlib only.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys

MANIFEST = ".scratch/tp12-campaign/manifest.json"
RECEIPTS = "benchmarks/tp12-*"
#: The verdict lives in the recipe it refuses, as `metadata.measured_rejected: "<date> — <reason>
#: (<doc>:<line>)"` -- `metadata` and not a top-level key (sparkrun sweeps an unknown top-level key
#: into `runtime_config` and reports it) and not a recipe comment (`AGENTS.md` §Recipe comments bans
#: provenance there). The key is the recipe schema's snake_case; `VERDICT` is the word the plan
#: prints, the repo's hyphenated spelling of the same refusal.
REJECT_MARKER = "measured_rejected"
VERDICT = "measured-rejected"
#: `<date> — <reason> (<path>:<line>)`, the whole marker. The path may not contain a parenthesis,
#: because the marker itself is delimited by one.
CITATION = re.compile(r"^(\d{4}-\d{2}-\d{2}) — (.+?) \(([^()\s]+):(\d+)\)$")
#: Machine-readable artefacts only. The old `*.yaml` fallback counted ANY yaml in the receipt as a
#: measurement, and `run-arm.sh` writes `ladder.yaml` as soon as a benchmark starts -- so an arm
#: that died before its first cell could mark itself measured and never be retried (no receipt
#: carried a yaml-only artefact when this was tightened on 2026-10-30, on either the workstation
#: or the head).
MEASURED_ARTEFACTS = ("ladder.json", "ladder.transcribed.json", "house.json",
                      "house.transcribed.txt", "quality.json")
#: The executor's normalised client cell (`ARM_EXTRA_CLIENT`); see `quality_failure`.
QUALITY = "quality.json"
#: The marker `run-arm.sh` appends to: top-level `ladder:` / `accuracy_status:` fields whose value
#: carries the outcome. It is also a full benchmark document for the chat suite, so only the
#: unindented keys are outcome -- nested `ladder` keys are payload.
MARKER = "house.yaml"
LADDERS = ("ladder.json", "ladder.transcribed.json")
#: Cell tables the instruments write: the ladder's `benchmarks`, the decision ladder's `cells`,
#: and the pooling exporter's `runs`. A file that parses to none of these has no cell in it.
CELL_KEYS = ("benchmarks", "cells", "runs")
_TOP_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):[ \t]*(.*)$")
_LADDER_VALUE = re.compile(r"^(ok|failed \(rc=\d+\))")
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


class MarkerError(RuntimeError):
    """A marker could not be read, or contradicts itself. Never "done" on a guess."""


def read_marker(arm_dir: str) -> dict[str, str] | None:
    """Top-level `key: value` fields of `house.yaml`, or None when there is no marker.

    Nested keys are payload, not outcome. An unreadable or self-contradicting marker raises:
    a guess of "measured" leaves an arm that must be re-run, and a guess of "not measured"
    re-boots an arm that already has its numbers, so neither is a safe default.
    """
    path = os.path.join(arm_dir, MARKER)
    if not os.path.exists(path):
        return None
    fields: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                found = _TOP_KEY.match(line)
                if not found:
                    continue
                key, value = found.group(1), found.group(2).strip()
                if key in fields and fields[key] != value:
                    raise MarkerError(f"{path}: {key} appears twice ({fields[key]!r} and {value!r})")
                fields[key] = value
    except OSError as exc:
        raise MarkerError(f"{path}: {exc}") from exc
    return fields


def ladder_failure(arm_dir: str) -> str | None:
    """Why the ladder artefact is not a measurement, or None when it parses with content.

    Presence alone was the defect: a ladder that dies partway leaves a truncated `ladder.json`
    behind, and the arm was counted measured and never retried. A `ladder.yaml` that starts a
    benchmark is exactly the same trap, which is why no yaml is evidence here.
    """
    for name in LADDERS:
        path = os.path.join(arm_dir, name)
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
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


def quality_failure(arm_dir: str) -> str | None:
    """Why the executor's client cell is not a measurement, or None when it carries one.

    Mirrors the campaign's `evidence.quality_problem`: presence alone was the ladder's defect and
    is this file's too. A hook killed mid-battery leaves a truncated JSON, and a client that wrote
    `{}` proves only that it started; the envelope needs at least one of the hook's own files to
    parse to a non-empty cell table or score object.
    """
    path = os.path.join(arm_dir, QUALITY)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        return f"{QUALITY} does not parse ({exc.__class__.__name__})"
    if not isinstance(data, dict):
        return f"{QUALITY} parses to a {type(data).__name__}, not an object"
    client = data.get("client")
    if not isinstance(client, dict) or not client:
        return f"{QUALITY} carries no client file"
    if not any(isinstance(value, (dict, list)) and value for value in client.values()):
        return f"{QUALITY} carries no cell or score"
    return None


def arm_measured(arm_dir: str) -> tuple[bool, str]:
    """(done, reason). A reason is always printed, so a non-receipt is visible in the plan log."""
    arm = os.path.basename(arm_dir.rstrip("/"))
    try:
        marker = read_marker(arm_dir)
    except MarkerError as exc:
        return False, f"{arm}: marker unreadable, not measured: {exc}"
    ladder = ladder_failure(arm_dir)
    verdict = (marker or {}).get("ladder", "")
    if verdict:
        found = _LADDER_VALUE.match(verdict)
        if not found:
            return False, (f"{arm}: {MARKER} ladder field {verdict!r} is neither 'ok' nor"
                           f" 'failed (rc=N)'; not measured")
        if found.group(1) != "ok":
            # The one state where re-attempting is right: the boot finished, the ladder did not.
            return False, f"{arm}: ladder failed, so the arm is unmeasured ({verdict})"
        if ladder:
            # `ok` beside a broken artefact contradicts itself; the artefact loses the tie.
            return False, f"{arm}: ladder says ok but the artefact is not a measurement: {ladder}"
        return True, ""
    if ladder:
        return False, f"{arm}: {ladder}; not measured"
    present = [name for name in MEASURED_ARTEFACTS
               if os.path.exists(os.path.join(arm_dir, name))]
    quality = quality_failure(arm_dir) if QUALITY in present else None
    if quality:
        # A truncated client file loses to any other artefact; on its own it is not a measurement.
        present = [name for name in present if name != QUALITY]
        if not present:
            return False, f"{arm}: {quality}; not measured"
    if present:
        return True, ""
    return False, ""


def measured_arms(home: str, windows: tuple[str, ...] = (RECEIPTS,)) -> set[str]:
    """Arms whose receipt says a ladder ran and that ladder carries cells.

    `windows` exists so a test can point at a temp tree without globbing the real receipts.
    """
    done: set[str] = set()
    for win in (w for pattern in windows for w in glob.glob(os.path.join(home, pattern))):
        for arm_dir in glob.glob(os.path.join(win, "*/")):
            arm = os.path.basename(arm_dir.rstrip("/"))
            if ".prev-" in arm:
                continue
            ok, reason = arm_measured(arm_dir)
            if ok:
                done.add(arm)
            elif reason:
                print(f"unmeasured: {reason}", file=sys.stderr)
    return done


class ManifestError(RuntimeError):
    """The manifest could not be read. Never silently "nothing to do"."""


class RejectError(RuntimeError):
    """The skip source could not be read. Never silently plan a recorded negative."""


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


def metadata_value(text: str, key: str) -> str | None:
    """The `key:` value inside a recipe's top-level `metadata:` block, or None.

    Hand-rolled YAML subset, like the guards in `tests/`: the block is the indented run after
    `metadata:` at column 0, a block-level key is indented exactly two spaces, and the value may
    be double-quoted. A key that appears twice raises -- two markers on one arm are a
    contradiction and neither is a safe default.
    """
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines)
                  if re.fullmatch(r"metadata:[ \t]*", line)), None)
    if start is None:
        return None
    prefix = f"  {key}:"
    found = []
    for line in lines[start + 1:]:
        if line.strip() and not line.startswith(" "):
            break
        if line.startswith(prefix):
            found.append(line[len(prefix):].strip().strip('"'))
    if len(found) > 1:
        raise RejectError(f"`metadata.{key}` appears twice ({found[0]!r} and {found[1]!r})")
    return found[0] if found else None


def tracked(root: str) -> set[str] | None:
    """Every tracked path under `root`, or None when `root` is not a checkout.

    A citation into an untracked scratch path is not evidence a clone can check, so it is
    refused -- but that question is only askable inside a git work tree, which a test fixture
    is not.
    """
    rc, out = sh(["git", "-C", root, "ls-files"])
    if rc != 0:
        return None
    return set(out.splitlines()) or None


def rejected_arms(root: str = ".") -> dict[str, dict]:
    """Recorded measured negatives, keyed by arm, read from the recipes themselves.

    An arm the tree already measured and refused is not a candidate: booting it spends node
    window and produces no new number. The verdict lives in the recipe it refuses, so a rename
    or a retirement to `attic/` carries it and a deletion removes it -- there is no separate
    file to go stale. The citation (`path:line` in a lane doc) is the evidence, not the code.
    """
    out: dict[str, dict] = {}
    for path in sorted(glob.glob(os.path.join(root, "recipes", "*", "*.yaml"))):
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            raise RejectError(f"cannot read {path}: {exc}") from exc
        value = metadata_value(text, REJECT_MARKER)
        if value is None:
            continue
        found = CITATION.match(value)
        if not found:
            raise RejectError(
                f'{path}: metadata.{REJECT_MARKER} must read "<YYYY-MM-DD> — <reason>'
                f' (<path>:<line>)", not {value!r}')
        arm = os.path.basename(path)[: -len(".yaml")]
        out[arm] = {
            "arm": arm,
            "verdict": VERDICT,
            "doc": f"{found.group(3)}:{found.group(4)}",
            "since": found.group(1),
        }
    return out


def citation_problems(rejected: dict[str, dict], root: str = ".") -> list[str]:
    """Markers whose cited `path:line` no longer resolves, as printable lines.

    The `stale-skip` check is gone because it is now structurally impossible: the marker travels
    inside the recipe, so nothing can suppress an arm the tree no longer carries. What can still
    rot is the citation, which a doc rewrite moves out from under the verdict it records.
    """
    known = tracked(root)
    problems = []
    for arm, entry in sorted(rejected.items()):
        doc, _, line = entry["doc"].rpartition(":")
        path = os.path.join(root, doc)
        if known is not None and doc not in known:
            problems.append(f"{arm} cites {entry['doc']}, which is not a tracked file")
        elif not os.path.isfile(path):
            problems.append(f"{arm} cites {entry['doc']}, which is not a file")
        else:
            with open(path, encoding="utf-8", errors="replace") as fh:
                if len(fh.read().splitlines()) < int(line):
                    problems.append(f"{arm} cites {entry['doc']}, past the end of that file")
    return problems


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
    ap.add_argument("--root", default=".",
                    help="tree whose recipes carry the verdict markers (default: %(default)s)")
    ap.add_argument("--json", action="store_true", help="machine-readable plan")
    args = ap.parse_args(argv)

    nodes = [n.strip() for n in args.nodes.split(",") if n.strip()]
    if not nodes:
        print("no nodes: pass --nodes a,b or set $STAGE_NODES", file=sys.stderr)
        return 2

    # Read before the fleet probe: a marker that does not parse, or a citation that no longer
    # resolves, is a config defect, and failing here costs no ssh -- the plan would otherwise be
    # built without the very exclusions that keep a measured negative off a node.
    try:
        rejected = rejected_arms(args.root)
    except RejectError as exc:
        print(f"cannot plan: {exc}", file=sys.stderr)
        return 2
    problems = citation_problems(rejected, args.root)
    if problems:
        for problem in problems:
            # Names the arm, the doc and the marker's home: re-pointing a citation is one edit in
            # the recipe, and a drip log should say which one without a grep.
            print(f"stale-citation: {problem}; the verdict line has moved or the doc is gone, so"
                  f" re-point metadata.{REJECT_MARKER} in the recipe", file=sys.stderr)
        return 2

    free = free_nodes(nodes)
    done = measured_arms(args.home)
    # The queue is a property of the fleet, not of the moment: ask what is runnable at the
    # fleet's real capacity (two free nodes) and report that even when none is free, so an
    # idle node never hides a backlog and a full fleet still shows what comes next.
    try:
        todo = candidates(args.manifest, done, set(args.skip) | set(rejected), max(len(nodes), 2))
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

    skipped = [{"arm": arm, "verdict": e["verdict"], "doc": e["doc"]}
               for arm, e in sorted(rejected.items())]

    if args.json:
        print(json.dumps({"free_nodes": free, "measured": len(done), "skipped": skipped,
                          "plan": plan}, indent=2))
    else:
        print(f"free nodes: {', '.join(free) if free else 'none'}")
        print(f"measured arms on disk: {len(done)} | unmeasured in manifest: {len(todo)}"
              f" | runnable on {len(free)} free node(s): {len(plan)}")
        # Printed even when nothing else is: the reason an arm is absent must be checkable
        # without reading this tool, and a boot that spends a window to learn nothing is the
        # defect this list exists to prevent.
        for entry in skipped:
            print(f"skip: {entry['arm']} ({entry['verdict']}, {entry['doc']})")
        # Exclusion accounting: "nothing runnable" must be explainable.
        if args.skip:
            print(f"  excluded by --skip: {', '.join(sorted(args.skip))}")
        if pairs:
            # No claim about why: an arm lands here when the remaining node budget cannot fit it,
            # which may be zero nodes or one -- and the old wording asserted "fewer than two were
            # free" in runs that had just placed a pair on exactly two.
            print(f"  TP=2 not placed: {len(pairs)} arm(s) did not fit the remaining node budget:")
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