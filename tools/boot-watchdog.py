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


def serve_state(
    node: str, container: str, pattern: str
) -> tuple[bool, tuple[int, int] | None]:
    """(pid_alive, io) for the serve child inside the container, via ssh."""
    script = (
        f'docker exec {container} sh -c \'pid=$(pgrep -f "{pattern}" | head -1); '
        '[ -n \\"$pid\\" ] && cat /proc/$pid/io 2>/dev/null || echo NO-PID\''
    )
    try:
        out = subprocess.run(
            ["ssh", "-n", "-o", "BatchMode=yes", f"red@{node}", script],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return False, None
    if "NO-PID" in out or not out.strip():
        return False, None
    return True, parse_io(out)


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
        help="container name (default sparkrun_<task-id>_node_0)",
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

    container = args.container or f"sparkrun_{args.task_id}_node_0"
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
