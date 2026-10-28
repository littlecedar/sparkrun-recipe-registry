#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""`vllm-omni serve` wrapper that republishes /metrics in the monitor's log shapes.

The sparkrun monitor scrapes a serve's *log* for four line shapes
(`sparkrun/cli/_monitor_metrics.py`: `Avg generation throughput: N tokens/s`,
`Avg prompt throughput: N tokens/s`, `Running: N reqs`, `Waiting: N reqs`) plus
the SGLang variants. A diffusion serve logs none of them, so this arm's cells are
blank in the monitor. This wrapper runs the recipe's own `vllm-omni` command
verbatim as a child and prints what `/metrics` carries in those shapes.

The metric NAMESPACE is not hardcoded, on purpose. This arm publishes `vllm_omni:`
families (`vllm_omni:peak_memory_mb{stage="0"}` — measured on the 2026-10-22
boots, recipes/media/README.md) while the vLLM engine underneath publishes `vllm:`
ones, and which of the wanted series a diffusion serve actually reports was never
observed before this wrapper shipped. So the parser matches the vLLM-family
SUFFIX and prints nothing for a series the body does not carry: an invented zero
would corrupt accounting, while a missing cell reads as "not reported", which is
the truth. The first `/metrics` body also logs the matched names — or, when none
matched, every family present — so this arm's next boot records the real naming
instead of a guess.

Fail-open by construction: the bridge never touches the serve. `OMNI_METRICS_BRIDGE=0`
disables it without a repo edit and `OMNI_METRICS_BRIDGE_DEADLINE_S` (default 3600)
bounds the pre-ready wait. The wrapper relays SIGTERM/SIGINT and exits with the
engine's code, so container stop semantics are unchanged.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading

TAG = "[vllm-omni-metrics-bridge]"
DEFAULT_PORT = 8000

# Wanted series suffix -> the canonical name the formatter reads. The suffixes are
# vLLM's own and have survived v0/v1 and the omni stages; only the prefix moves.
WANTED = {
    "num_requests_running": "running",
    "num_requests_waiting": "waiting",
    "prompt_tokens_total": "prompt_tokens",
    "generation_tokens_total": "gen_tokens",
}


def family(line: str) -> str:
    """`name{labels} value` -> `name`."""
    return line.partition(" ")[0].split("{", 1)[0]


def family_names(text: str) -> list[str]:
    """Every distinct series name in a prometheus body, sorted (pure, evidence-only)."""
    return sorted({family(ln) for ln in text.splitlines() if ln and not ln.startswith("#")})


def parse_metrics(text: str) -> dict[str, float]:
    """A prometheus body -> the wanted counters it carries, by canonical name (pure).

    A labelled series is stored under its family name, never shadowed by a label:
    `vllm_omni:num_requests_running{stage="0"} 2` -> running=2.
    """
    out: dict[str, float] = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        key = WANTED.get(family(line).rpartition(":")[2])
        if key is None:
            continue
        try:
            out[key] = float(line.split(" ", 1)[1].strip().split(" ", 1)[0])
        except (IndexError, ValueError):
            continue
    return out


def build_metric_lines(
    vals: dict[str, float],
    prev_gen: float | None,
    prev_t: float | None,
    now: float,
) -> tuple[list[str], float | None, float | None]:
    """Scraper-shaped lines for one /metrics sample and the next delta state (pure).

    Only what the sample actually carried is printed: a missing counter emits no
    line, never a placeholder zero. Throughput needs two samples of the
    generation counter. A diffusion serve usually has neither token counter, so
    it gets the two request gauges and nothing else.
    """
    lines: list[str] = []
    gen = vals.get("gen_tokens")
    if gen is not None and prev_gen is not None and prev_t is not None and now > prev_t:
        tps = (gen - prev_gen) / (now - prev_t)
        lines.append(f"Avg generation throughput: {tps:.2f} tokens/s")
        lines.append(f"gen throughput (token/s): {tps:.2f}")
    running = vals.get("running")
    if running is not None:
        lines.append(f"Running: {int(running)} reqs")
    waiting = vals.get("waiting")
    if waiting is not None:
        lines.append(f"Waiting: {int(waiting)} reqs")
    return lines, gen, now


def bridge_loop(
    port: int,
    period_s: float = 5.0,
    backoff_cap_s: float = 30.0,
    pre_ready_deadline_s: float = 3600.0,
) -> None:
    """Poll this serve's /metrics and emit scraper-shaped lines. Fail-soft.

    The omni HTTP listener binds only after the stage load (251 s cold on this
    arm), so connection refusals are the EXPECTED state for most of the boot:
    retry with backoff (5 s doubling to 30 s) until the port answers once. After
    first contact, three consecutive failures end the thread; before it, an
    env-configurable deadline bounds the wait. It never touches the serve.
    """
    import time
    import urllib.request

    deadline = time.time() + pre_ready_deadline_s
    prev_gen: float | None = None
    prev_t: float | None = None
    delay = period_s
    reached = False
    announced = False
    misses_after_reach = 0
    while True:
        time.sleep(delay)
        try:
            body = urllib.request.urlopen(
                f"http://127.0.0.1:{port}/metrics", timeout=5
            ).read().decode()
        except Exception as exc:  # noqa: BLE001 - fail-soft by design
            if reached:
                misses_after_reach += 1
                if misses_after_reach >= 3:
                    print(
                        f"{TAG} metrics bridge disabled after "
                        f"{misses_after_reach} post-contact failures: {exc}",
                        flush=True,
                    )
                    return
            elif time.time() > deadline:
                print(
                    f"{TAG} metrics bridge disabled: /metrics "
                    f"never answered before the deadline: {exc}",
                    flush=True,
                )
                return
            delay = min(delay * 2, backoff_cap_s)
            continue
        reached = True
        misses_after_reach = 0
        delay = period_s
        now = time.time()
        vals = parse_metrics(body)
        if not announced:
            # Once per boot, after the first body: the matched names are the
            # evidence, and an empty match names every family there is to map.
            seen = sorted(vals) or family_names(body)
            print(f"{TAG} metrics bridge: matched {sorted(vals)} families {seen}", flush=True)
            announced = True
        lines, prev_gen, prev_t = build_metric_lines(vals, prev_gen, prev_t, now)
        for line in lines:
            print(line, flush=True)


def _as_port(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return DEFAULT_PORT


def serve_port(argv: list[str]) -> int:
    """`--port N` / `--port=N` out of the forwarded command, else DEFAULT_PORT.

    Never raises: a port the bridge cannot read only means it never contacts
    anything, and a telemetry concern must not fail a launch.
    """
    for i, arg in enumerate(argv):
        if arg.startswith("--port="):
            return _as_port(arg.split("=", 1)[1])
        if arg == "--port" and i + 1 < len(argv):
            return _as_port(argv[i + 1])
    return DEFAULT_PORT


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        # Fail closed: an empty argv would start `vllm-omni` with no subcommand,
        # i.e. print help and exit, and the arm would look like a broken engine.
        print(f"{TAG} no vllm-omni arguments: the recipe's command: must pass them", flush=True)
        return 2
    cmd = ["vllm-omni", *argv]
    print(f"{TAG} boot: {' '.join(cmd)}", flush=True)
    proc = subprocess.Popen(cmd)
    if os.environ.get("OMNI_METRICS_BRIDGE", "1") != "0":
        threading.Thread(
            target=bridge_loop,
            kwargs={
                "port": serve_port(argv),
                "pre_ready_deadline_s": float(
                    os.environ.get("OMNI_METRICS_BRIDGE_DEADLINE_S", "3600")
                ),
            },
            daemon=True,
        ).start()

    def _forward(signum, _frame):
        proc.send_signal(signum)

    signal.signal(signal.SIGTERM, _forward)
    signal.signal(signal.SIGINT, _forward)
    return proc.wait()


if __name__ == "__main__":
    sys.exit(main())