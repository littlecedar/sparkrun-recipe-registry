#!/usr/bin/env python3
"""mem-floor-probe.py — record a boot's per-rank memory floor as a machine-readable cell.

A load-only probe (the Kimi `--load-format dummy` arm) answers a fit question by *diving*
through the parameter-set allocation and dying there: the answer is the minimum
`MemAvailable` each rank reached, and the boot never serves, so nothing else in the
executor ever writes a number. Measured 2026-11-10: three campaign attempts held four
ranks ~5 min each and every one filed `rc=4 "never ready — no marker and no
machine-readable artefact"` because the only floor evidence was the engine's console
text. The same boot's `oom-watchdog.txt` names earlyoom killing all four ranks at 4 % —
a real measurement with no artefact to carry it.

So this samples every rank at a fixed interval while the boot runs, keeps the minimum and
when it happened, folds any floor lines the launcher already printed, and writes the cell
`run-arm.sh`'s measured set accepts. It fails closed: a missing task id, an unreachable
rank, or a short sample set writes **no** artefact and exits non-zero, because a floor
file built on partial data is worse than none — the campaign would count it measured.

Run it under `run-arm.sh` as a pre-ready client (the hook must be sampling while the
engine loads; the post-ready `ARM_EXTRA_CLIENT` path cannot see a boot that dies during
load):

    ARM_EXTRA_CLIENT="python3 -B tools/mem-floor-probe.py --task-id-file $L/task-id.txt
        --hosts $HOSTS --image-id $ARM_IMAGE_ID --out $L/mem-floor.json"
    ARM_EXTRA_CLIENT_AT=pre-ready (one line in the row's `env`; the continuation above is
    only for reading)

Artefact (`--out`, default `mem-floor.json` in the receipt root): `task_id`, `image_id`,
`hosts`, `interval_s`, `sample_count`, per-rank `samples` / `min_kb` / `min_at_s` /
`min_gib` / `dive_gib`, `floor_lines` parsed from `--log`, and a `verdict`. The client also
writes the fixed `quality.json` envelope the measured set reads (`--measured`, disable
with `--no-measured`); the producer block names this command and the payload file.

Exit codes: 0 artefact written; 1 no artefact (probe/partial/missing-task); 2 bad flags.

Stdlib only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_INTERVAL = 5.0
DEFAULT_SAMPLES = 120
DEFAULT_MIN_SAMPLES = 3
DEFAULT_WAIT_TASK_ID = 120.0

#: Lines the launcher/engine already prints that carry the same fact this tool samples.
FLOOR_PATTERNS = (
    re.compile(r"available_bytes=\S+"),
    re.compile(r"full_token=\d+"),
    re.compile(r"MemAvailable:\s*\d+\s*kB"),
    re.compile(r"(?:low memory|earlyoom|oom[_-]kill)\b.*", re.IGNORECASE),
)


class ProbeError(Exception):
    """A sample, a rank or the task id is missing: never write an artefact."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Sample a boot's per-rank MemAvailable floor into a JSON cell.")
    p.add_argument("--task-id", default="", help="sparkrun task id (bare <intent>_<launch>)")
    p.add_argument("--task-id-file", default="",
                   help="file the executor writes the task id into once the launch resolves")
    p.add_argument("--wait-task-id", type=float, default=DEFAULT_WAIT_TASK_ID,
                   help="seconds to wait for --task-id-file (default %(default)s)")
    p.add_argument("--hosts", required=True,
                   help="comma-separated rank hosts, in rank order")
    p.add_argument("--interval", type=float, default=DEFAULT_INTERVAL,
                   help="seconds between rounds (default %(default)s)")
    p.add_argument("--samples", type=int, default=DEFAULT_SAMPLES,
                   help="rounds to sample before stopping (default %(default)s)")
    p.add_argument("--min-samples", type=int, default=DEFAULT_MIN_SAMPLES,
                   help="rounds every rank must have to count (default %(default)s)")
    p.add_argument("--out", default="mem-floor.json",
                   help="artefact path, usually in the receipt root (default %(default)s)")
    p.add_argument("--measured", default="",
                   help="quality.json path (default: beside --out)")
    p.add_argument("--no-measured", action="store_true",
                   help="write only --out, not the measured-set envelope")
    p.add_argument("--image-id", default="", help="container image id this boot ran")
    p.add_argument("--image-id-file", default="",
                   help="file the executor writes the image id into once the launch resolves")
    p.add_argument("--expect-dive-gib", type=float, default=None,
                   help="sanity gate: fall from the first sample each rank must reach")
    p.add_argument("--tolerance-pct", type=float, default=10.0,
                   help="how far below --expect-dive-gib still counts (default %(default)s)")
    p.add_argument("--probe-cmd", default="",
                   help="override the per-host probe; `{host}` is substituted, output must "
                        "carry `mem=<kB> ctns=<n>`")
    p.add_argument("--log", action="append", default=[],
                   help="file to scan for floor lines (repeatable)")
    return p.parse_args(argv)


def default_probe(host: str, task_id: str) -> str:
    """One ssh per rank per round: MemAvailable plus this task's container count."""
    pattern = f"^sparkrun_{task_id}_(solo|node_)"
    remote = (
        "printf 'mem=%s ctns=%s\\n' "
        "\"$(awk '/MemAvailable:/{print $2}' /proc/meminfo)\" "
        "\"$(docker ps --format '{{.Names}}' | grep -cE "
        + shlex.quote(pattern) + " || true)\""
    )
    return " ".join(["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
                     f"red@{host}", shlex.quote(remote)])


def run_probe(command: str, host: str) -> tuple[int, int]:
    """(memavailable_kb, container_count) for one rank, or ProbeError."""
    rendered = command.replace("{host}", host)
    try:
        proc = subprocess.run(rendered, shell=True, capture_output=True, text=True,
                              timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProbeError(f"{host}: probe did not run ({exc.__class__.__name__})") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise ProbeError(f"{host}: probe exited {proc.returncode}"
                         + (f" ({detail[-1]})" if detail else ""))
    found = dict(re.findall(r"\b(mem|ctns)=(\S+)", proc.stdout))
    try:
        return int(found["mem"]), int(found["ctns"])
    except (KeyError, ValueError) as exc:
        raise ProbeError(f"{host}: probe printed no mem=/ctns= pair") from exc


def wait_for_value(path: Path, seconds: float, what: str) -> str:
    """A value the executor writes into its receipt, or a fatal timeout."""
    deadline = time.monotonic() + max(0.0, seconds)
    while True:
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError:
            value = ""
        if value:
            return value
        if time.monotonic() >= deadline:
            raise ProbeError(f"{what} file {path} never carried a value "
                             f"(waited {seconds:.0f}s)")
        time.sleep(1.0)


def wait_for_task_id(args: argparse.Namespace) -> str:
    """The task id, from the flag or the executor's file; missing id is fatal."""
    if args.task_id.strip():
        return args.task_id.strip()
    if not args.task_id_file:
        raise ProbeError("no task id: pass --task-id or --task-id-file")
    return wait_for_value(Path(args.task_id_file), args.wait_task_id, "task id")


def floor_lines(paths: list[str]) -> list[str]:
    """Floor-ish lines the launcher already printed, capped and provenance-tagged."""
    found: list[str] = []
    for raw in paths:
        path = Path(raw)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if not stripped:
                continue
            if any(pattern.search(stripped) for pattern in FLOOR_PATTERNS):
                found.append(f"{path.name}:{number}: {stripped[:400]}")
    return found[:200]


def sample(args: argparse.Namespace, hosts: list[str], task_id: str) -> dict[str, object]:
    """Sample every rank until the task disappears; a gap aborts the whole artefact."""
    probe = args.probe_cmd or ""
    if not probe:
        probe = default_probe("{host}", task_id)
    ranks: dict[str, dict[str, object]] = {
        host: {"samples": [], "min_kb": None, "min_at_s": None} for host in hosts}
    started = dt.datetime.now(dt.UTC)
    started_at = time.monotonic()
    seen_task = False
    empty_rounds = 0
    rounds = 0
    for _ in range(max(1, args.samples)):
        elapsed = time.monotonic() - started_at
        live = 0
        for host in hosts:
            try:
                mem_kb, ctns = run_probe(probe, host)
            except ProbeError as exc:
                raise ProbeError(f"round {rounds + 1} lost a rank: {exc}") from exc
            live += 1 if ctns else 0
            samples = ranks[host]["samples"]
            samples.append([round(elapsed, 3), mem_kb])
            if ranks[host]["min_kb"] is None or mem_kb < ranks[host]["min_kb"]:
                ranks[host]["min_kb"] = mem_kb
                ranks[host]["min_at_s"] = round(elapsed, 3)
        rounds += 1
        seen_task = seen_task or live > 0
        empty_rounds = empty_rounds + 1 if live == 0 else 0
        if empty_rounds >= 2:
            break                                  # the boot ended; the floor is behind us
        if rounds < args.samples:
            time.sleep(max(0.0, args.interval))
    if not seen_task:
        raise ProbeError(f"task {task_id} never appeared on {','.join(hosts)}")
    short = [host for host, rank in ranks.items()
             if len(rank["samples"]) < max(1, args.min_samples)]
    if short:
        raise ProbeError(f"short sample set on {','.join(short)} "
                         f"(<{args.min_samples} rounds): no artefact")
    for rank in ranks.values():
        first = rank["samples"][0][1]
        rank["min_gib"] = round(rank["min_kb"] / 1048576, 3)
        rank["first_gib"] = round(first / 1048576, 3)
        rank["dive_gib"] = round((first - rank["min_kb"]) / 1048576, 3)
    verdict = "measured"
    if args.expect_dive_gib is not None:
        floor_dive = args.expect_dive_gib * (1.0 - max(0.0, args.tolerance_pct) / 100.0)
        short_dive = [host for host, rank in ranks.items() if rank["dive_gib"] < floor_dive]
        if short_dive:
            verdict = "dive-short"
    return {
        "tool": "mem-floor-probe",
        "version": 1,
        "task_id": task_id,
        "image_id": args.image_id,
        "hosts": hosts,
        "interval_s": args.interval,
        "sample_count": rounds,
        "started": started.isoformat(),
        "ended": dt.datetime.now(dt.UTC).isoformat(),
        "expect_dive_gib": args.expect_dive_gib,
        "tolerance_pct": args.tolerance_pct,
        "ranks": ranks,
        "floor_lines": floor_lines(args.log),
        "verdict": verdict,
    }


def write_json(path: Path, payload: dict[str, object]) -> None:
    """Atomic: a reader sees the old file or the whole new one, never half."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.hosts.strip():
        print("mem-floor-probe: --hosts is empty", file=sys.stderr)
        return 2
    hosts = [host.strip() for host in args.hosts.split(",") if host.strip()]
    if len(hosts) != len(args.hosts.split(",")):
        print("mem-floor-probe: --hosts carries an empty rank", file=sys.stderr)
        return 2
    if args.interval < 0 or args.samples < 1 or args.min_samples < 1:
        print("mem-floor-probe: --interval/--samples/--min-samples out of range",
              file=sys.stderr)
        return 2
    out = Path(args.out)
    try:
        task_id = wait_for_task_id(args)
        if not args.image_id and args.image_id_file:
            args.image_id = wait_for_value(Path(args.image_id_file), args.wait_task_id,
                                           "image id")
        payload = sample(args, hosts, task_id)
    except ProbeError as exc:
        print(f"mem-floor-probe: ERROR {exc}; no artefact written", file=sys.stderr)
        return 1
    write_json(out, payload)
    measured = "" if args.no_measured else (args.measured
                                            or str(out.with_name("quality.json")))
    if measured:
        write_json(Path(measured), {
            "producer": {"component": "mem-floor-probe",
                         "command": " ".join([Path(sys.argv[0]).name] + (argv or sys.argv[1:])),
                         "rc": 0, "source": "tools/mem-floor-probe.py",
                         "files": [out.name]},
            "client": {out.name: payload},
        })
    floor = min(rank["min_gib"] for rank in payload["ranks"].values())
    print(f"mem-floor-probe: {payload['verdict']} task={task_id} ranks={len(hosts)} "
          f"rounds={payload['sample_count']} lowest={floor} GiB artefact={out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
