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
  * the probe itself failed (ssh/exec error, no `LOGSIZE`)     -> no_probe: no evidence
    either way. Silence is never death: a loading boot's endpoint is *also* down, so
    reading a 30 s ssh timeout as a sighting would kill a healthy boot.
  * serve child alive (`pgrep` in the container)               -> loading
    (its `/proc/<pid>/io` deltas are logged so a 45-min GLM weight load is
    visibly progressing, never misread as dead)
  * child **gone after we watched it alive**, or its serve log ends on a fatal
    line (`Traceback`, `NotImplementedError`, `CUDA error`, `Received sigquit`,
    `Killed`, `out of memory`), on the 2nd consecutive *observed* absence
                                                               -> dead, stopped at once
  * child gone and endpoint dead but never seen alive (a serve-pid fingerprint
    miss)                                                      -> dead_candidate, timed
  * child alive, endpoint dead, no io and no log growth for
    `--stall` (600 s; 4x the worst silence measured on a healthy boot) -> stalled
  dead/stalled: `sparkrun stop <task-id>` (literal id), evidence to --log, exit 3.

Two floors, both cheap at `--interval 10`: the second observed check rides out one bad
sighting (a pgrep miss across a re-exec), and `no_probe` keeps a broken instrument out of
the count entirely. There is no `--grace`: the old 1800 s loading window gated verdicts
that only fire on evidence, and it cost 26 throttled minutes on 2026-11-03 (an arm whose
serve died at t=98 s, correctly called `dead` at t=123 s, held until t=1800 s), plus a
frozen 4B arm the same 40 minutes. Only "the child was never found" is ambiguous enough
to deserve a clock.

Stdlib only, no deps. Launch detached next to every boot:

    nohup python3 tools/boot-watchdog.py --endpoint http://<api-rank>:8000 \\
        --task-id sparkrun_<hash>_<hash> --node <host> \\
        --log ~/benchmarks/<window>/watchdog-<task-id>.log &

Exit codes: 0 endpoint healthy; 3 dead and stopped; 4 watchdog's own error.
"""

import argparse
import http.client
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
    except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException):
        # A serve that answers with something un-HTTP (measured 2026-10-30: a vLLM
        # pooling arm raised `BadStatusLine`) is DOWN, not a reason to kill the
        # monitor -- an uncaught HTTPException ends the watchdog and the boot loses
        # its only liveness evidence.
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


def decide(
    endpoint_ok: bool,
    pid_alive: bool | None,
    consecutive_dead: int,
    seen_alive: bool = False,
    fatal: str | None = None,
) -> str:
    """One check's classification (pure).

    healthy        : endpoint 200.
    no_probe       : the probe itself failed (ssh / docker-exec error), so this check has
                     no evidence either way. Silence is never death — a 30 s ssh timeout on
                     a healthy but still-loading boot is exactly when the endpoint is also
                     down, so reading it as a sighting would kill a good boot.
    loading        : serve child alive (progress is reported separately via io).
    dead           : the child is gone **and** we watched it alive or its serve log ends on
                     a fatal line, on the second consecutive *observed* absence. Two checks
                     survive one bad sighting (a pgrep miss across a re-exec); the count is
                     of observations, never of probe failures. Death is an edge, not a
                     duration: on 2026-11-03 an arm whose serve died at t=98 s was classified
                     correctly at t=123 s and then held another 1677 s by a grace window
                     meant for loading.
    dead_candidate : child gone and endpoint dead and we never saw it alive — the serve-pid
                     fingerprint miss. Nothing here is evidence of a crash, so it stays
                     timed by `--dead-grace`.
    """
    if endpoint_ok:
        return "healthy"
    if pid_alive is None:
        return "no_probe"
    if pid_alive:
        return "loading"
    if (seen_alive or fatal) and consecutive_dead >= 2:
        return "dead"
    return "dead_candidate"


def is_stalled(endpoint_ok: bool, pid_alive: bool, idle: float, stall: float) -> bool:
    """A live child that has made no progress at all is stuck, not loading (pure).

    The `21e5ec6` defect masks a *dead* serve with a keep-alive; this is its sibling and it cost a
    node for 30 minutes on 2026-10-30: a vLLM boot froze at `Capturing CUDA graphs 0/102` with
    `io_delta=0` and `log_delta=0` for half an hour. `pid_alive` kept the verdict at `loading`, so
    the dead-candidate path never fired and nothing ever stopped it.

    Both deltas must be zero for the whole stall window — a slow 45-minute weight load logs or
    reads something. No loading clock gates this: measured across 46 boots that reached healthy
    (2026-11-03, every watchdog receipt on the head), the longest silent stretch was **150 s**, so
    `--stall 600` carries a 4x margin and an `elapsed >= grace` gate on top decided nothing but
    delay. A frozen 4B arm is stopped in ~10 minutes instead of 40.
    """
    if endpoint_ok or not pid_alive:
        return False
    return idle >= stall


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
) -> tuple[bool | None, tuple[int, int] | None, int | None, int | None, str | None]:
    """(pid_alive, io, serve_log_size, container_memory, fatal_line) for the serve child.

    `pid_alive is None` means the probe failed — ssh or the container exec errored, or the
    node went away mid-flight. It is deliberately distinct from `False` (probed, and there
    is no serve child): the caller must never read its own broken instrument as a death.
    """
    # The script is fed on stdin so neither the pattern nor its own quotes need
    # escaping through ssh's argument passing.
    # The probe's own `sh -c` command line CONTAINS the pattern, so `pgrep -f` matches
    # itself; the busiest-reader rule then flips between the serve and a transient
    # wrapper every sample and `io_delta` becomes meaningless. Measured 2026-10-30 on a
    # 122B load: io_delta=0 for five minutes while shards loaded at 80 s each.
    script = (
        "PAT=" + shlex.quote(pattern) + "\n"
        "for p in $(pgrep -f \"$PAT\"); do\n"
        "  case \"$(tr \\0 ' ' < /proc/$p/cmdline 2>/dev/null)\" in\n"
        "    *pgrep*|*boot-watchdog*|*\"sh -c\"*|*\"sh -s\"*) continue ;;\n"
        "  esac\n"
        "  echo \"PID $p\"; cat /proc/$p/io 2>/dev/null\n"
        "done\n"
        "echo \"LOGSIZE $(wc -c < /tmp/sparkrun_serve.log 2>/dev/null || echo 0)\"\n"
        "echo \"MEM $(cat /sys/fs/cgroup/memory.current 2>/dev/null || cat /sys/fs/cgroup/memory/memory.usage_in_bytes 2>/dev/null || echo 0)\"\n"
        # The serve log ends on the reason a crash happened. Only the LAST lines count:
        # an engine that logged a warning and carried on is not dead.
        "echo \"FATAL $(tail -n 5 /tmp/sparkrun_serve.log 2>/dev/null | grep -oiE 'traceback \\(most recent|notimplementederror|cuda error|received sigquit|killed|runtimeerror|assertionerror|segmentation fault|out of memory' | head -1)\"\n"
    )
    try:
        proc = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", f"red@{node}", f"docker exec -i {container} sh -s"],
            input=script,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return None, None, None, None, None
    out, err = proc.stdout, proc.stderr or ""
    if "No such container" in err or "is not running" in err:
        # Docker names the absence on stderr: the container is gone, so there is nothing to
        # serve. That is observed absence (evidence), not a broken instrument.
        return False, None, None, None, None
    if "LOGSIZE" not in out:
        # Our script never ran (ssh failed, or docker refused): no evidence either way.
        return None, None, None, None, None
    alive, io = pick_io(out)
    return alive, io, parse_logsize(out), parse_mem(out), parse_fatal(out)


def parse_mem(text: str) -> int | None:
    """`MEM <bytes>` from the sample -> int, or None.

    vLLM loads shards through a child whose command line does not match the serve
    pattern, so `/proc/<pid>/io` can read zero while 70 GB lands in RAM (measured
    2026-10-30 on a 122B load at 4/8 shards: io_delta and log_delta both 0 for five
    minutes). Container memory moves for any loader, which is what makes it the third
    signal rather than a fourth way to be wrong.
    """
    for line in text.splitlines():
        if line.startswith("MEM "):
            try:
                return int(line.split()[1])
            except (IndexError, ValueError):
                return None
    return None


def parse_fatal(text: str) -> str | None:
    """The engine's own last word on how it died -> the matched text, or None.

    The child going quiet is a transition the watchdog can see but not explain; the serve
    log names the cause in its last lines (`NotImplementedError: No implemented
    int8_scaled_mm for current compute capability`, 2026-11-03). Reading it from the probe
    that already runs keeps this at one round trip per check, and matching only the log's
    tail keeps a recovered warning from reading as a death.
    """
    for line in text.splitlines():
        if line.startswith("FATAL "):
            value = line[len("FATAL ") :].strip()
            return value or None
    return None


def parse_logsize(text: str) -> int | None:
    """`LOGSIZE <bytes>` from the sample -> int, or None when absent.

    `/proc/<pid>/io` reads 0 delta through phases that do no file IO, notably
    sglang's CUDA-graph capture, so a zero delta is ambiguous: initializing, or
    wedged. The serve log grows during real progress and stops when the child
    stops, which is the discriminator this supplies.
    """
    for line in text.splitlines():
        if line.startswith("LOGSIZE "):
            try:
                return int(line.split()[1])
            except (IndexError, ValueError):
                return None
    return None


def pick_container(names: list[str], task_id: str) -> str:
    """The task's container from `docker ps` names; falls back to the multi-rank default.

    A TP=1 task names its single container `<prefix>_solo`, so the old
    `sparkrun_<task-id>_node_0` default read "serve_pid=gone" on every solo boot
    (the container simply did not exist under that name) and could stop a
    slow-loading solo serve on a sighting that was the resolver's own bug.
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


def should_stop(verdict: str, dead_grace: float, dead_for: float | None) -> bool:
    """Whether a check may act (pure). Every window is now evidence-backed, not a load clock.

    `dead`       — two consecutive observed absences with a witness (seen alive or a fatal
                   line): act on the check that reaches the second.
    `stalled`    — `is_stalled` already required the whole stall window of zero io AND zero
                   log growth (4x the worst silence measured on a healthy boot).
    `dead_candidate` — never seen alive, which is also what a serve-pid fingerprint miss
                   looks like, so it alone keeps a clock (`--dead-grace`, 120 s).

    There is no `--grace` any more: a 1800 s loading window was gating a verdict that only
    fires on evidence, and it cost 26 throttled minutes on 2026-11-03 (an arm whose serve
    died at t=98 s, declared `dead` at t=123 s and held to t=1800 s).
    """
    if verdict == "dead":
        return True
    if verdict == "dead_candidate":
        return dead_for is not None and dead_for >= dead_grace
    if verdict == "stalled":
        return True
    return False


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
        "--dead-grace",
        type=float,
        default=120.0,
        help="seconds a never-seen-alive `dead_candidate` must persist before stopping; "
        "a `dead` verdict (child we watched go, or one whose log ends on a fatal line) "
        "acts on the check that completes its second observation",
    )
    ap.add_argument(
        "--stall",
        type=float,
        default=600.0,
        help="seconds of zero io AND zero log growth after which a live child is declared "
             "stuck and stopped; 600 is 4x the 150 s worst case measured across 46 healthy "
             "boots (2026-11-03)",
    )
    ap.add_argument("--serve-pattern", default=SERVE_PATTERN)
    ap.add_argument("--log", default="")
    args = ap.parse_args(argv)

    container = args.container or resolve_container(args.node, args.task_id)
    log = open(args.log, "a", encoding="utf-8") if args.log else sys.stdout  # noqa: SIM115 (whole-run handle)
    started = time.time()
    consecutive_dead = 0
    prev_io: tuple[int, int] | None = None
    prev_logsize: int | None = None
    prev_mem: int | None = None
    last_progress = time.monotonic()
    dead_since: float | None = None
    # `seen_alive` is what makes a crash a transition instead of a timer: a child we
    # watched working and then lost is dead, full stop. Only a child we never found
    # (the fingerprint miss) needs a confirmation window.
    seen_alive = False
    while True:
        ok = http_ok(args.endpoint + "/v1/models")
        alive, io, logsize, mem, fatal = serve_state(args.node, container, args.serve_pattern)
        if alive:
            seen_alive = True
        delta = -1
        if io is not None and prev_io is not None:
            delta = (io[0] - prev_io[0]) + (io[1] - prev_io[1])
        prev_io = io
        log_delta = -1
        if logsize is not None and prev_logsize is not None:
            log_delta = logsize - prev_logsize
        prev_logsize = logsize
        mem_delta = -1
        if mem is not None and prev_mem is not None:
            mem_delta = mem - prev_mem
        prev_mem = mem
        # Only an *observed* absence counts. `alive is None` is a broken probe, and
        # `not None` would be True here — a killed boot is the one mistake this cannot make.
        if alive is False and not ok:
            consecutive_dead += 1
        else:
            consecutive_dead = 0
        verdict = decide(ok, alive, consecutive_dead, seen_alive=seen_alive, fatal=fatal)
        elapsed = int(time.time() - started)
        if ok or delta > 0 or log_delta > 0:
            last_progress = time.monotonic()
        idle = time.monotonic() - last_progress
        stalled = is_stalled(ok, alive, idle, args.stall)
        if stalled:
            verdict = "stalled"
        print(
            f"WATCHDOG t={elapsed}s verdict={verdict} endpoint={'ok' if ok else 'down'} "
            f"serve_pid={('alive' if alive else 'gone') if alive is not None else 'unprobed'} io_delta={delta} "
            f"log_delta={log_delta} "
            f"mem_delta={mem_delta} idle={int(idle)}s" + (f" cause={fatal!r}" if fatal else ""),
            file=log,
            flush=True,
        )
        if verdict == "dead_candidate":
            if dead_since is None:
                dead_since = time.monotonic()
        else:
            dead_since = None
        dead_for = None if dead_since is None else time.monotonic() - dead_since
        if verdict == "healthy":
            return 0
        if should_stop(verdict, args.dead_grace, dead_for):
            stop_task(args.task_id, log)
            return 3
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
