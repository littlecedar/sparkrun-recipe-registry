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

  * endpoint answers each check and an inference surface returns 2xx
                                                              -> healthy
    Healthy means *served*, not *listening*: an authenticated `/v1/models` plus one tiny
    request answered 2xx on the engine's own surface — `/v1/chat/completions`, else
    `/v1/completions`, else `/v1/embeddings`, else `/v1/rerank` (the embedding and reranking
    lanes have no chat endpoint), and the check line names the one that answered
    (`inference=ok surface=embeddings`). A `/health` 200 with no surface answering is
    `loading`, never healthy, never exit 0: on picom `dsfront` binds `/health` ~90 s early and
    the receipt `head:~/benchmarks/picom-bareh-20261120-head/watchdog.log` shows the old
    keyless rule reporting `verdict=healthy` at t=1 s on a boot that could not answer.
    The bearer is read from `--api-key-file` on this host, else through `--node`'s container
    by `docker exec cat` (the picom arm writes it inside the container); a keyless engine
    (vLLM/SGLang with no bearer) answers `/v1/models` 200 and probes the same way. When no key
    reads *and* `/v1/models` refuses a keyless probe, the check is `no_probe` -- never
    `healthy`, never a silent `/health` fallback. `--no-require-inference` opts back into the
    plain endpoint rule for an arm whose only readiness signal really is `/health`.
  * serve pattern matched nothing while the container is up and inference
    answers                                                    -> loading (a fingerprint
    miss is not death; one log line names the miss)
  * the probe itself failed (ssh/exec error, no `LOGSIZE`)     -> no_probe: no evidence
    either way. Silence is never death: a loading boot's endpoint is *also* down, so
    reading a 30 s ssh timeout as a sighting would kill a healthy boot.
  * serve child alive (`pgrep` in the container)               -> loading
    (its `/proc/<pid>/io` deltas are logged so a 45-min GLM weight load is
    visibly progressing, never misread as dead. The crash edge arms only once a non-empty
    `/tmp/sparkrun_serve.log` says the SERVE is running: the pattern also matches plain
    `python`, and a mod's `pre_exec` hook is a short python process that would otherwise be
    watched alive and then read as a serve death — measured 2026-11-11, ERNIE attempt 1, a
    healthy boot stopped on `.35`)
  * child **gone after we watched it alive**, or its serve log ends on a fatal
    line (`Traceback`, `NotImplementedError`, `CUDA error`, `Received sigquit`,
    `Killed`, `out of memory`), on the 2nd consecutive *observed* absence
                                                               -> dead, stopped at once
  * child gone and endpoint dead but never seen alive (a serve-pid fingerprint
    miss)                                                      -> dead_candidate, timed
  * no rank in the lease shows io, log or memory progress for `--stall`
    (600 s; 4x the worst silence measured on a healthy boot)      -> stalled
    Group-scoped: any rank's progress resets the clock (a TP=4 rendezvous leaves rank 0
    quiet while peers stream shards), memory counts only past a 128 MiB floor (allocator
    jitter is sub-MB), and an unprobeable rank blocks the verdict rather than faking it.
  dead/stalled: the container's `/tmp/sparkrun_serve.log` is captured to
    `serve-reaped-<container>.log` beside --log FIRST (the stop destroys it, and a
    fast-reaped arm's crash text is the whole diagnosis), then `sparkrun stop <task-id>`
    (literal id); evidence to --log, exit 3.

Two floors, both cheap at `--interval 10`: the second observed check rides out one bad
sighting (a pgrep miss across a re-exec), and `no_probe` keeps a broken instrument out of
the count entirely. There is no `--grace`: the old 1800 s loading window gated verdicts
that only fire on evidence, and it cost 26 throttled minutes on 2026-11-03 (an arm whose
serve died at t=98 s, correctly called `dead` at t=123 s, held until t=1800 s), plus a
frozen 4B arm the same 40 minutes. Only "the child was never found" is ambiguous enough
to deserve a clock.

Stdlib only, no deps. Launch detached next to every boot:

    nohup python3 tools/boot-watchdog.py --endpoint http://<api-rank>:8000 \\
        --task-id <intent>_<launch> --node <host> \\
        --log ~/benchmarks/<window>/watchdog-<task-id>.log &

`--task-id` is the **bare** `<intent>_<launch>` id: this tool prepends `sparkrun_` itself, so the
string `sparkrun status` prints (`sparkrun_<intent>_<launch>`) doubles the prefix and resolves no
container. `--container` with the name `docker ps` shows is even safer. The tool prints the container
it resolved (`WATCHDOG arm: …`) and refuses to arm at all when the id is prefixed or the container is
not running — an armed watchdog that cannot see its container stops healthy loads (measured
2026-11-10: ERNIE TP=4 killed 120 s in at shard 13/128 with 37.3 GiB free).

Exit codes: 0 endpoint healthy; 3 dead and stopped; 4 watchdog's own error or a refused arm.
"""

import argparse
import http.client
import json
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SERVE_PATTERN = "dsgb10_rank|dsfront|tensorfold|llama-server|sglang|vllm|python3|python"


def http_status(url: str, timeout: float = 5.0) -> int | None:
    """HTTP status `GET url` returned, or None when nothing answered.

    A 4xx is an answer from a live server, which is why it is a status and not a
    failure here: the model path of a keyed front-end answers 401 to a keyless probe.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException):
        return None


def http_ok(url: str, timeout: float = 5.0) -> bool:
    """True when GET url returns 2xx."""
    status = http_status(url, timeout)
    return status is not None and 200 <= status < 300


def endpoint_reachable(endpoint: str, timeout: float = 5.0) -> bool:
    """Whether the serve is demonstrably answering (reachable, not necessarily 200).

    `/health` is keyless and is the honest 200 test where the engine has one; on a
    keyed front-end `/v1/models` answers 401/403 to this probe, which is a live server
    and must not read as `endpoint=down`. Any HTTP answer below 500 counts as reachable.
    """
    for path in ("/health", "/v1/models"):
        status = http_status(endpoint + path, timeout=timeout)
        if status is None:
            continue
        if path == "/health" and 200 <= status < 300:
            return True
        if path == "/v1/models" and 200 <= status < 500:
            return True
    return False


def read_api_key(path: str) -> str:
    """Bearer key from the file the arm writes; empty when unreadable (fail closed)."""
    try:
        return Path(path).expanduser().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def resolve_api_key(path: str, node: str, container: str) -> tuple[str, list[str]]:
    """(key, attempted locations): the host path, else the same path inside `node`'s container.

    `/cache/runtime/picom/run/api-key` is written inside the container, while the watchdog
    runs on the control machine, so a host-readable copy is not guaranteed. Reading it through
    `docker exec` on the rank container is the operator's own route. Two failed attempts are
    reported by the caller as `no_probe` -- never a silent keyless probe.
    """
    tried = [path]
    key = read_api_key(path)
    if key or not node or not container:
        return key, tried
    remote = f"{node}:{container}:{path}"
    tried.append(remote)
    try:
        proc = subprocess.run(
            [
                "ssh", "-o", "BatchMode=yes", f"red@{node}",
                f"docker exec {shlex.quote(container)} cat {shlex.quote(path)}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return "", tried
    if proc.returncode != 0:
        return "", tried
    return proc.stdout.strip(), tried


def http_call(
    url: str,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> tuple[int, bytes] | None:
    """(status, body) of a request, or None when nothing answered. Never prints the key."""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json", **(headers or {})}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(1 << 16)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(1 << 16)
        except (OSError, http.client.HTTPException):
            body = b""
        finally:
            exc.close()
        return exc.code, body
    except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException):
        return None


# `input` shapes that are one input for a chat surface, a completion, an embedding and a
# rerank: the embedding and reranking lanes have no chat endpoint at all (`recipes/embed/`,
# `recipes/rerank/`), so the surface is what decides health, never `/health`.
INFERENCE_SURFACES = (
    ("chat", "/v1/chat/completions",
     {"max_tokens": 1, "messages": [{"role": "user", "content": "ping"}]}),
    ("completions", "/v1/completions",
     {"prompt": "ping", "max_tokens": 1}),
    ("embeddings", "/v1/embeddings", {"input": "ping"}),
    ("rerank", "/v1/rerank", {"query": "ping", "documents": ["ping"]}),
)


def probe_inference(endpoint: str, api_key: str, timeout: float = 10.0) -> tuple[str, str | None]:
    """(verdict, surface): does the engine really serve inference?

    `ok`       : `/v1/models` answered and one of `INFERENCE_SURFACES` returned 2xx; the
                 surface is named (`chat`, `completions`, `embeddings`, `rerank`).
    `down`     : no surface answers yet (a boot in progress), or a key we hold is refused.
    `unprobed` : `/v1/models` refuses us without a bearer and no key was readable, so this
                 instrument cannot tell a served boot from a dead one -- never `ok`, and the
                 caller never strengthens it into a `/health` fallback.

    `/health` is not readiness. On the picom arm `dsfront` binds `/health` ~90 s before
    the engine exists (`head:~/benchmarks/picom-bareh-20261120-head/watchdog.log`: verdict
    healthy at t=1 s on a boot that could not answer), and a keyless 200 proves only that
    the front-end process is listening. Fail closed: anything short of a served surface
    is `loading`, never `healthy`.
    """
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    models = http_call(endpoint + "/v1/models", headers=headers, timeout=timeout)
    if models is not None and models[0] in (401, 403) and not api_key:
        return "unprobed", None
    if models is None or not 200 <= models[0] < 300:
        return "down", None
    try:
        model = json.loads(models[1])["data"][0]["id"]
    except (ValueError, KeyError, IndexError, TypeError):
        return "down", None
    # Any non-2xx that is not an auth refusal means this engine has no such surface (a
    # pooling engine answers 404 or 400 to chat completions), so the next one is tried.
    # Only a 2xx on a real inference surface counts, so trying them all can never make a
    # boot healthier than it is; a 401/403 is the engine refusing us, not a routing miss.
    for name, path, body in INFERENCE_SURFACES:
        answer = http_call(endpoint + path, {"model": model, **body}, headers, timeout)
        if answer is None:
            return "down", None
        if 200 <= answer[0] < 300:
            return "ok", name
        if answer[0] in (401, 403):
            return "down", None
    return "down", None


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


def container_up(pid_alive: bool | None, logsize: int | None) -> bool | None:
    """Whether the sample proved the container exists (pure).

    `LOGSIZE` is emitted by the probe only after its own `sh` ran inside the
    container, so a number means the container is up even when the serve pattern
    matched nothing. The "No such container"/"not running" branch returns no
    LOGSIZE, and a broken probe returns `pid_alive=None`; both are not container-up.
    """
    if pid_alive is None:
        return None
    return logsize is not None


def decide(
    endpoint_ok: bool,
    pid_alive: bool | None,
    consecutive_dead: int,
    seen_alive: bool = False,
    fatal: str | None = None,
    container_up: bool | None = None,
) -> str:
    """One check's classification (pure).

    healthy        : endpoint answers and, if the child was never found, the container is not
                     up. A reachable endpoint is proof of a live server (401 counts: keyed
                     front-ends answer the keyless probe that way).
    no_probe       : the probe itself failed (ssh / docker-exec error), so this check has
                     no evidence either way. Silence is never death — a 30 s ssh timeout on
                     a healthy but still-loading boot is exactly when the endpoint is also
                     down, so reading it as a sighting would kill a good boot.
    loading        : serve child alive (progress is reported separately via io); or the
                     pattern matched nothing while the container is up and the endpoint
                     answers — a fingerprint miss is not a death signal.
    dead           : the child is gone **and** we watched it alive or its serve log ends on
                     a fatal line, on the second consecutive *observed* absence. Two checks
                     survive one bad sighting (a pgrep miss across a re-exec); the count is
                     of observations, never of probe failures. Death is an edge, not a
                     duration: on 2026-11-03 an arm whose serve died at t=98 s was classified
                     correctly at t=123 s and then held another 1677 s by a grace window
                     meant for loading.
    dead_candidate : child gone and endpoint dead and we never saw it alive — the serve-pid
                     fingerprint miss. Nothing here is evidence of a crash, so it stays
                     timed by `--dead-grace`. This is what still reaps a container kept
                     alive around a dead child when nothing answers.
    """
    if endpoint_ok:
        if pid_alive is False and container_up and not seen_alive:
            return "loading"
        return "healthy"
    if pid_alive is None:
        return "no_probe"
    if pid_alive:
        return "loading"
    if (seen_alive or fatal) and consecutive_dead >= 2:
        return "dead"
    return "dead_candidate"


MEM_PROGRESS_FLOOR = 128 << 20  # 128 MiB


def progressed(ok: bool, io_delta: int, log_delta: int, mem_delta: int) -> bool:
    """Whether this check saw the load move (pure).

    Memory counts for the reason `parse_mem` samples it: a vLLM mmap load can read and log
    nothing for minutes while tens of GiB land in RAM — and a 753B boot was declared `stalled`
    at t≈2532 s against a documented 2538.9 s TTR while its memory was moving. But a bare
    nonzero test resets the stall clock on allocator jitter (that same boot moved +548K, -598K,
    +1.29M and one -90M outlier per check) and would re-open the 2026-10-30 frozen-boot class
    (`is_stalled`). So memory counts only past `MEM_PROGRESS_FLOOR` (128 MiB): above that boot's
    whole jitter envelope, including the -90 MiB outlier, and below a real load's per-check
    movement (70 GB over the 2538.9 s TTR is ~282 MB per 10 s check). Any one counter past its
    floor is progress; all flat is the frozen shape.
    """
    return ok or io_delta > 0 or log_delta > 0 or abs(mem_delta) >= MEM_PROGRESS_FLOOR


def group_stalled(endpoint_ok: bool, alives: list[bool | None], idle: float, stall: float) -> bool:
    """No probed rank has progressed for the whole stall window (pure).

    The `21e5ec6` defect masks a *dead* serve with a keep-alive; this is its sibling and it cost a
    node for 30 minutes on 2026-10-30: a vLLM boot froze at `Capturing CUDA graphs 0/102` with
    `io_delta=0` and `log_delta=0` for half an hour. `pid_alive` kept the verdict at `loading`, so
    the dead-candidate path never fired and nothing ever stopped it.

    The test is group-scoped, not rank-0-scoped: on a TP=4 rendezvous a quiet rank 0 while its peers
    stream shards is normal, and no rank-0 threshold tells "waiting on a peer" from "dead". So the
    idle clock resets on any rank's progress, and a stall needs *every* rank alive and flat. Fails
    closed on an unprobeable rank (`None`): a broken probe is `no_probe`, never evidence of a stall.

    No loading clock gates this: measured across 46 boots that reached healthy (2026-11-03, every
    watchdog receipt on the head), the longest silent stretch was **150 s**, so `--stall 600` carries
    a 4x margin and an `elapsed >= grace` gate on top decided nothing but delay. A frozen 4B arm is
    stopped in ~10 minutes instead of 40.
    """
    if endpoint_ok or not alives or any(a is not True for a in alives):
        return False
    return idle >= stall


def is_stalled(endpoint_ok: bool, pid_alive: bool, idle: float, stall: float) -> bool:
    """`group_stalled` for the single-rank shape, kept for the arms that run one container."""
    return group_stalled(endpoint_ok, [pid_alive], idle, stall)


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


def parse_rank(spec: str) -> tuple[str, str]:
    """`NODE:CONTAINER` -> (node, container). Neither a hostname nor a container name has a colon."""
    node, sep, ctn = spec.partition(":")
    if not sep or not node or not ctn:
        raise SystemExit(f"--rank wants NODE:CONTAINER, got {spec!r}")
    return node, ctn


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


def list_containers(node: str) -> list[str]:
    """Container names running on the node (ssh); `[]` when the probe itself fails."""
    try:
        out = subprocess.run(
            [
                "ssh", "-n", "-o", "BatchMode=yes", f"red@{node}",
                "docker ps --format '{{.Names}}'",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        out = ""
    return [n.strip() for n in out.splitlines() if n.strip()]


def container_arm_refusal(task_id: str, container: str, running: list[str]) -> str | None:
    """Why this watchdog must not arm, or `None` when it may.

    Measured 2026-11-10 (the ERNIE TP=4 arm): the caller passed the id `sparkrun status` prints,
    which already carries the `sparkrun_` prefix. `resolve_container` prepends the prefix again,
    resolves nothing, and the tool armed against a container that did not exist; its
    `--dead-grace` then fired 120 s into a healthy load (shard 13/128, 37.3 GiB free) and stopped
    a boot that was never dead. A watchdog that cannot name the container it is watching has no
    evidence to act on, so it must refuse to arm rather than arm blind: no stop path, exit 4.
    """
    if task_id.startswith("sparkrun_"):
        return (
            f"task id {task_id!r} already carries the 'sparkrun_' prefix this tool adds; pass "
            "the bare `<intent>_<launch>` id (or --container explicitly)"
        )
    if container not in running:
        shown = ", ".join(running[:5]) if running else "none"
        return (
            f"no running container named {container!r} on the node at arm time "
            f"(running: {shown}); pass --container with the name `docker ps` shows"
        )
    return None


def capture_serve_log(node: str, container: str, out_dir: Path, log) -> Path | None:
    """Copy the serve log out of the container before the stop makes it unreachable.

    `run-arm.sh` harvests `/tmp/sparkrun_serve.log` after readiness, but a watchdog-driven
    stop removes the container first, so the arms that die fastest -- exactly the ones whose
    log names the cause -- arrived as `serve logs harvested: 0 (0 means the log was gone)`
    (measured 2026-11-04: a negative arm booted, died at t=32 s, was stopped at t=43 s, and
    its rank-0 crash text was lost). Written beside this watchdog's own `--log` as
    `serve-reaped-<container>.log`, first line carrying the log's size and mtime, so the
    receipt can say whether the capture happened. Best-effort by construction: every failure
    is logged and returns None, and it must never delay or prevent the stop that follows.

    LIMIT: this captures the one node the probe runs against. A TP=2 arm's rank-1 container
    lives on the other host, so its serve log is still lost -- `--node` names a single host
    and probing a second one is out of scope here.
    """
    script = (
        "f=/tmp/sparkrun_serve.log\n"
        'if [ -r "$f" ]; then\n'
        '  echo "META $(wc -c < "$f") $(stat -c %Y "$f")"\n'
        '  cat "$f"\n'
        "else\n"
        '  echo "MISSING"\n'
        "fi\n"
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
    except (subprocess.SubprocessError, OSError) as exc:
        print(f"WATCHDOG: serve-log capture for {container} failed: {exc}", file=log, flush=True)
        return None
    out = proc.stdout or ""
    if not out.startswith("META "):
        detail = (
            "serve log absent in the container"
            if out.startswith("MISSING")
            else (proc.stderr or "").strip()[:160] or "no output from docker exec"
        )
        print(
            f"WATCHDOG: serve-log capture for {container}: nothing captured ({detail})",
            file=log,
            flush=True,
        )
        return None
    dest = out_dir / f"serve-reaped-{container}.log"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        dest.write_text(out, encoding="utf-8")
    except OSError as exc:
        print(
            f"WATCHDOG: serve-log capture for {container} could not write {dest}: {exc}",
            file=log,
            flush=True,
        )
        return None
    meta = " ".join(out.splitlines()[0][len("META ") :].split())
    print(
        f"WATCHDOG: serve log captured for {container}: {dest} (size/mtime={meta})",
        file=log,
        flush=True,
    )
    return dest


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
    `stalled`    — `is_stalled` already required the whole stall window of zero io, log AND
                   memory growth (4x the worst silence measured on a healthy boot).
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
        help="seconds of zero io, log AND memory growth after which a live child is declared "
             "stuck and stopped; 600 is 4x the 150 s worst case measured across 46 healthy "
             "boots (2026-11-03)",
    )
    ap.add_argument(
        "--rank",
        action="append",
        default=[],
        metavar="NODE:CONTAINER",
        help="another rank in the same lease (repeatable). Rank 0 is --node/--container and owns "
        "the endpoint and the death evidence; peers widen the progress/stall test, so a TP=4 "
        "rendezvous is judged on the whole group rather than a quiet rank 0",
    )
    ap.add_argument("--serve-pattern", default=SERVE_PATTERN)
    ap.add_argument(
        "--require-inference",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="default: healthy needs a served inference surface (an authenticated "
        "`/v1/models` plus one 2xx completion, or `/v1/embeddings` / `/v1/rerank` where the "
        "engine has no chat surface), never just a `/health` 200. `--no-require-inference` "
        "opts out for an arm whose only readiness signal really is `/health`",
    )
    ap.add_argument(
        "--api-key-file",
        default="/cache/runtime/picom/run/api-key",
        help="bearer key for the inference probe: the host path is tried first, then the same "
        "path inside --node's container (`docker exec cat`, where the picom arm writes it). "
        "Neither readable is `no_probe`: never healthy, never a keyless fallback",
    )
    ap.add_argument("--log", default="")
    args = ap.parse_args(argv)

    running = list_containers(args.node)
    container = args.container or resolve_container(args.node, args.task_id)
    log = open(args.log, "a", encoding="utf-8") if args.log else sys.stdout  # noqa: SIM115 (whole-run handle)
    # Name the container the tool resolved, so a doubled prefix or a typo is visible in the log
    # rather than inferred from a stop 120 s later.
    print(
        f"WATCHDOG arm: task={args.task_id} container={container} "
        f"({('explicit' if args.container else 'resolved via docker ps')}) node={args.node}",
        file=log,
        flush=True,
    )
    refusal = container_arm_refusal(args.task_id, container, running)
    if refusal:
        print(f"WATCHDOG: refusing to arm -- {refusal}", file=log, flush=True)
        return 4
    # A stop tears the container down, so a serve log captured after it does not exist:
    # the evidence file lands beside this watchdog's own log (cwd when --log is unset).
    log_dir = Path(args.log).expanduser().resolve().parent if args.log else Path.cwd()
    started = time.time()
    consecutive_dead = 0
    ranks = [(args.node, container)] + [parse_rank(spec) for spec in args.rank]
    # Per rank: (io, log size, memory) of the previous check, so each delta stays a delta.
    prev_rank: dict[tuple[str, str], tuple[tuple[int, int] | None, int | None, int | None]] = {}
    last_progress = time.monotonic()
    dead_since: float | None = None
    # `seen_alive` is what makes a crash a transition instead of a timer: a child we
    # watched working and then lost is dead, full stop. Only a child we never found
    # (the fingerprint miss) needs a confirmation window.
    seen_alive = False
    pattern_miss_logged = False
    api_key = ""
    key_tried: list[str] = []
    if args.require_inference:
        api_key, key_tried = resolve_api_key(args.api_key_file, args.node, container)
        if not api_key:
            print(
                "WATCHDOG: no key readable at "
                f"{' or '.join(key_tried)}; probing keyless, and a front-end that refuses a "
                "keyless /v1/models is no_probe (never healthy, never a /health fallback)",
                file=log,
                flush=True,
            )
    unprobed = False
    surface: str | None = None
    health_only_logged = False
    while True:
        if args.require_inference:
            inferred, surface = probe_inference(args.endpoint, api_key)
            unprobed = inferred == "unprobed"
            infer = inferred == "ok"
            ok = infer
        else:
            ok = infer = endpoint_reachable(args.endpoint)
        health_ok = ok
        if args.require_inference and not ok and not unprobed:
            health_ok = endpoint_reachable(args.endpoint)
        # `/health` 200 is not readiness: name the gap once so the receipt says which surface
        # was missing, and keep the verdict at loading until a completion is served.
        if health_ok and not infer and not health_only_logged:
            print(
                f"WATCHDOG: /health answers but no inference yet (authenticated /v1/models + "
                "one completion); holding at loading",
                file=log,
                flush=True,
            )
            health_only_logged = True
        samples = [serve_state(node, ctn, args.serve_pattern) for node, ctn in ranks]
        alive, _io, _logsize, _mem, fatal = samples[0]
        cup = container_up(alive, _logsize)
        # A fingerprint miss is not a death signal when the container is up and the
        # server answers; say it once so the next diagnosis starts from the pattern.
        if alive is False and cup and health_ok and not seen_alive and not pattern_miss_logged:
            print(
                f"WATCHDOG: serve pattern {args.serve_pattern!r} matched nothing in "
                f"{container}; container is up and the endpoint answers -- holding at loading",
                file=log,
                flush=True,
            )
            pattern_miss_logged = True
        # Arming is evidence the SERVE exists, never just that some matched process does: the pattern
        # includes plain `python`/`python3` (2026-10-26 ruling), and a mod's `pre_exec` hook is a
        # python process that matches, runs, and exits. Measured 2026-11-11 on ERNIE attempt 1: the
        # hook's exit was read as a serve death and a healthy boot was stopped on `.35` before the
        # engine started. A serve writes `/tmp/sparkrun_serve.log`; a hook does not, so only a match
        # with a non-empty serve log arms the crash edge. A serve that never logs is still covered by
        # the never-seen-alive candidate path and its --dead-grace timer.
        if alive and _logsize:
            seen_alive = True
        delta = log_delta = mem_delta = -1
        peer_moved = 0
        unprobeable = 0
        moved = ok
        # Every rank in the lease: any rank's progress is the group loading (a TP=4 rendezvous
        # leaves rank 0 quiet while its peers stream shards), and an unprobeable rank is
        # `no_probe` — it contributes no progress and blocks the stall verdict below.
        for i, ((node, ctn), (rank_alive, rank_io, rank_log, rank_mem, _f)) in enumerate(
            zip(ranks, samples)
        ):
            if rank_alive is None:
                unprobeable += 1
            prev = prev_rank.get((node, ctn))
            rd = rl = rm = -1
            if prev is not None:
                if rank_io is not None and prev[0] is not None:
                    rd = (rank_io[0] - prev[0][0]) + (rank_io[1] - prev[0][1])
                if rank_log is not None and prev[1] is not None:
                    rl = rank_log - prev[1]
                if rank_mem is not None and prev[2] is not None:
                    rm = rank_mem - prev[2]
            prev_rank[(node, ctn)] = (rank_io, rank_log, rank_mem)
            if progressed(False, rd, rl, rm):
                moved = True
                if i:
                    peer_moved += 1
            if i == 0:
                delta, log_delta, mem_delta = rd, rl, rm
        # Only an *observed* absence counts. `alive is None` is a broken probe, and
        # `not None` would be True here — a killed boot is the one mistake this cannot make.
        if alive is False and not ok:
            consecutive_dead += 1
        else:
            consecutive_dead = 0
        verdict = decide(ok, alive, consecutive_dead, seen_alive=seen_alive, fatal=fatal,
                         container_up=cup)
        # A pattern miss with the container up and the endpoint answering is not death: the
        # server is there even though the pattern cannot name it. `/health` alone still never
        # proves health -- the verdict holds at loading until an inference surface answers.
        if verdict == "dead_candidate" and alive is False and cup and health_ok and not seen_alive:
            verdict = "loading"
        elapsed = int(time.time() - started)
        if moved:
            last_progress = time.monotonic()
        idle = time.monotonic() - last_progress
        stalled = group_stalled(ok, [sample[0] for sample in samples], idle, args.stall)
        if stalled:
            verdict = "stalled"
        # Without a key this instrument cannot tell a keyed serve that cannot answer from one
        # that can: that is a broken probe, so it never contributes health or a stop decision.
        if unprobed:
            verdict = "no_probe"
        print(
            f"WATCHDOG t={elapsed}s verdict={verdict} "
            f"endpoint={('unprobed' if unprobed else 'ok' if ok else 'down')} "
            f"serve_pid={('alive' if alive else 'gone') if alive is not None else 'unprobed'} io_delta={delta} "
            f"log_delta={log_delta} "
            f"mem_delta={mem_delta} idle={int(idle)}s ranks={len(ranks)} "
            f"peer_moved={peer_moved} unprobeable={unprobeable}"
            + (f" cause={fatal!r}" if fatal else "")
            + (
                f" inference={'unprobed' if unprobed else 'ok' if infer else 'down'}"
                + (f" surface={surface}" if infer and surface else "")
                if args.require_inference
                else ""
            ),
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
            capture_serve_log(args.node, container, log_dir, log)
            stop_task(args.task_id, log)
            return 3
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
