#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Boot watchdog: distinguish a slow-booting serve from a dead one, and stop the dead.

Why this exists (the `21e5ec6` defect class). sparkrun keeps a boot's container
alive after its in-container serve child has died, so `docker ps` reads "Up"
while the endpoint never returns — a keep-alive that MASKS a dead serve. A
session then sits on a boot that will never be ready. This watchdog makes the
distinction explicit and acts on it:

  * endpoint answers (`GET /v1/models` 200)                    -> healthy
  * serve child alive (`pgrep` in the container)               -> loading
    (its `/proc/<pid>/io` deltas are logged so a 45-min GLM weight load is
    visibly progressing, never misread as dead)
  * child gone AND endpoint dead for 2 consecutive checks      -> dead:
    `sparkrun stop <task-id>` (literal id), evidence to --log, exit 3.

Stdlib only, no deps. Launch detached next to every boot:

    nohup python3 tools/boot-watchdog.py --endpoint http://<api-rank>:8000 \\
        --task-id sparkrun_<hash>_<hash> --node <host> \\
        --log ~/benchmarks/<window>/watchdog-<task-id>.log &

Exit codes: 0 endpoint healthy; 3 dead and stopped; 4 watchdog's own error.
"""

import argparse
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request

SERVE_PATTERN = "tensorfold|llama-server|sglang|vllm|python3|python"


def http_ok(url: str, timeout: float = 5.0) -> bool:
    """True when GET url returns 2xx."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, ValueError):
        return False


def parse_io(text: str) -> tuple[int, int] | None:
    """`/proc/<pid>/io` body -> (rchar, wchar); None when unparsable."""
    vals: dict[str, int] = {}
    for line in text.splitlines():
        key, _, raw = line.partition(":")
        try:
            vals[key.strip()] = int(raw.strip())
        except ValueError:
            continue
    if "rchar" in vals and "wchar" in vals:
        return vals["rchar"], vals["wchar"]
    return None


def decide(endpoint_ok: bool, pid_alive: bool, consecutive_dead: int) -> str:
    """One check's classification (pure).

    healthy        : endpoint 200.
    loading        : serve child alive (progress is reported separately via io).
    dead           : child gone, endpoint dead, and this is the >=2nd such check.
    dead_candidate : child gone and endpoint dead, first sighting.
    """
    if endpoint_ok:
        return "healthy"
    if pid_alive:
        return "loading"
    return "dead" if consecutive_dead >= 2 else "dead_candidate"


def pick_io(text: str) -> tuple[bool, tuple[int, int] | None]:
    """Sampled `PID <n>` + `/proc/<n>/io` blocks -> (alive, io of the busiest reader).

    The serve process is not always the one reading: a vLLM serve keeps its
    `EngineCore` in a child, so `pgrep | head -1` reported the parent and logged
    `io_delta=0` through a 52-shard weight load. Take the pid with the largest
    `rchar` instead — it is the reader, and it is the same pid on the next
    sample, so the delta stays a delta.
    """
    best: tuple[int, int] | None = None
    alive = False
    for chunk in text.split("PID ")[1:]:
        pid_text, _, body = chunk.partition("\n")
        if pid_text.strip():
            # pgrep matched it, so the serve is up even if /proc io is unreadable
            # (the process exited between the two reads) — never report gone.
            alive = True
        io = parse_io(body)
        if io is None:
            continue
        if best is None or io[0] > best[0]:
            best = io
    return alive, best


def serve_state(
    node: str, container: str, pattern: str
) -> tuple[bool, tuple[int, int] | None]:
    """(pid_alive, io) for the serve child inside the container, via ssh."""
    # The script is fed on stdin so neither the pattern nor its own quotes need
    # escaping through ssh's argument passing.
    script = (
        "PAT=" + shlex.quote(pattern) + "\n"
        "for p in $(pgrep -f \"$PAT\"); do echo \"PID $p\"; cat /proc/$p/io 2>/dev/null; done\n"
    )
    try:
        out = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", f"red@{node}", f"docker exec -i {container} sh -s"],
            input=script,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return False, None
    return pick_io(out)


def pick_container(names: list[str], task_id: str) -> str:
    """The task's container from `docker ps` names; falls back to the multi-rank default.

    A TP=1 task names its single container `<prefix>_solo`, so the old
    `sparkrun_<task-id>_node_0` default read "serve_pid=gone" on every solo boot
    (the container simply did not exist under that name) and could stop a
    slow-loading solo serve at grace expiry.
    """
    for name in names:
        if task_id in name and name.endswith("_node_0"):
            return name
    for name in names:
        if task_id in name:
            return name
    return f"sparkrun_{task_id}_node_0"


def resolve_container(node: str, task_id: str) -> str:
    """Ask the node which container the task is running as (ssh)."""
    try:
        out = subprocess.run(
            [
                "ssh", "-n", "-o", "BatchMode=yes", f"red@{node}",
                f"docker ps --filter name=sparkrun_{task_id} --format '{{{{.Names}}}}'",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        out = ""
    return pick_container([n.strip() for n in out.splitlines() if n.strip()], task_id)


def stop_task(task_id: str, log) -> None:
    subprocess.run(
        ["sparkrun", "stop", task_id],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    print(f"WATCHDOG: sparkrun stop {task_id}", file=log, flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Boot watchdog (endpoint + serve-child liveness)."
    )
    ap.add_argument(
        "--endpoint",
        required=True,
        help="API-rank base URL, e.g. http://<api-rank-host>:8000",
    )
    ap.add_argument(
        "--task-id", required=True, help="sparkrun task/cluster id (literal stop id)"
    )
    ap.add_argument("--node", required=True, help="host running node_0 of that task")
    ap.add_argument(
        "--container",
        default="",
        help="container name (default: resolved on the node; `_solo` for TP=1, `_node_0` multi-rank)",
    )
    ap.add_argument("--interval", type=float, default=30.0)
    ap.add_argument(
        "--grace",
        type=float,
        default=600.0,
        help="seconds after which a dead candidate may be stopped (2 checks still required)",
    )
    ap.add_argument("--serve-pattern", default=SERVE_PATTERN)
    ap.add_argument("--log", default="")
    args = ap.parse_args(argv)

    container = args.container or resolve_container(args.node, args.task_id)
    log = open(args.log, "a", encoding="utf-8") if args.log else sys.stdout  # noqa: SIM115 (whole-run handle)
    started = time.time()
    consecutive_dead = 0
    prev_io: tuple[int, int] | None = None
    while True:
        ok = http_ok(args.endpoint + "/v1/models")
        alive, io = serve_state(args.node, container, args.serve_pattern)
        delta = -1
        if io is not None and prev_io is not None:
            delta = (io[0] - prev_io[0]) + (io[1] - prev_io[1])
        prev_io = io
        if not alive and not ok:
            consecutive_dead += 1
        else:
            consecutive_dead = 0
        verdict = decide(ok, alive, consecutive_dead)
        elapsed = int(time.time() - started)
        print(
            f"WATCHDOG t={elapsed}s verdict={verdict} endpoint={'ok' if ok else 'down'} "
            f"serve_pid={'alive' if alive else 'gone'} io_delta={delta}",
            file=log,
            flush=True,
        )
        if verdict == "healthy":
            return 0
        if verdict == "dead" and elapsed >= args.grace:
            stop_task(args.task_id, log)
            return 3
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
