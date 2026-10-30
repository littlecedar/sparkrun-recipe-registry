#!/usr/bin/env python3
"""py-runtime-bench.py — how much of a serving loop is the interpreter?

Why this exists
---------------
A GPU-bound executor still runs Python per token and per request: detokenize, wrap the
delta in a JSON chunk, write it to a socket, and re-arm the event loop. Whether a newer
interpreter helps is therefore a question about *that* work first and about the engine
second — and an engine's own numbers cannot separate the two, because swapping the
interpreter behind vLLM or SGLang also changes torch, triton and the kernels.

So this measures the Python-side pieces in isolation, under whatever interpreter runs it.
Run it under each candidate and compare: whatever an engine could gain from a newer
interpreter is bounded by what the pieces here gain.

What it measures (each reported as ns/op plus total wall time):

  loop        a pure-Python arithmetic loop — the specializing interpreter and any JIT
              effect, with no allocation to hide behind
  json        `json.dumps` of a streaming delta chunk, the shape an SSE path writes per
              token
  detok       bytes -> str decode of a token piece, as the detokenizer does per token
  asyncio     1 000 concurrent coroutines each doing 20 awaits — the scheduler and
              event-loop wake-up cost that grows with concurrency
  httparse    parsing a small JSON request body, as the front end does per request

Python 3.14's free-threaded build (`3.14t`) is worth running too: a no-GIL interpreter
trades single-thread speed for concurrency, which is exactly the detokenizer/scheduler
contention shape a serving front end has.

Usage
-----
    python3.12 tools/py-runtime-bench.py --json out-312.json
    python3.14 tools/py-runtime-bench.py --json out-314.json
    uv run --python 3.14t python tools/py-runtime-bench.py --json out-314t.json

Stdlib only, no deps, no network, no GPU. Exit codes: 0 ran; 2 bad flags.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
import time

# Sizes chosen so one run is a few seconds per case: long enough for a stable mean,
# short enough that three interpreters is a coffee, not an afternoon.
LOOP_ITERS = 3_000_000
JSON_ITERS = 200_000
DETOK_ITERS = 200_000
ASYNCIO_TASKS = 1_000
ASYNCIO_AWAITS = 20
HTTPARSE_ITERS = 100_000

DELTA = {
    "id": "chatcmpl-8fJ2k",
    "object": "chat.completion.chunk",
    "created": 1793332400,
    "model": "ornith-ai/Ornith-1.5-35B-A3B-NVFP4",
    "choices": [{"index": 0, "delta": {"content": " token"}, "finish_reason": None}],
}
BODY = (
    b'{"model":"m","messages":[{"role":"user","content":"Name the capital of France."}],'
    b'"max_tokens":64,"temperature":0,"stream":true}'
)
PIECE = " tokenization".encode()


def _time(ns_per_op_fn, iters: int) -> float:
    """Run `ns_per_op_fn(iters)` and return ns/op."""
    t0 = time.perf_counter()
    ns_per_op_fn(iters)
    elapsed = time.perf_counter() - t0
    return elapsed * 1e9 / iters


def bench_loop(iters: int) -> None:
    x = 0
    for i in range(iters):
        x = (x + i) & 0xFFFF
    if x < 0:  # keep the loop from being provably dead
        raise AssertionError


def bench_json(iters: int) -> None:
    dumps = json.dumps
    for _ in range(iters):
        dumps(DELTA)


def bench_detok(iters: int) -> None:
    for _ in range(iters):
        PIECE.decode("utf-8", "replace")


def bench_httparse(iters: int) -> None:
    loads = json.loads
    for _ in range(iters):
        loads(BODY)


async def _one() -> None:
    for _ in range(ASYNCIO_AWAITS):
        await asyncio.sleep(0)


def bench_asyncio(tasks: int) -> None:
    async def run() -> None:
        await asyncio.gather(*(_one() for _ in range(tasks)))

    asyncio.run(run())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Python-side serving-overhead microbenchmark.")
    ap.add_argument("--json", help="write the measurements here")
    ap.add_argument("--repeat", type=int, default=3, help="runs per case; the best is kept")
    args = ap.parse_args(argv)
    if args.repeat < 1:
        print("--repeat must be >= 1", file=sys.stderr)
        return 2

    cases = [
        ("loop", lambda: _time(bench_loop, LOOP_ITERS), LOOP_ITERS),
        ("json", lambda: _time(bench_json, JSON_ITERS), JSON_ITERS),
        ("detok", lambda: _time(bench_detok, DETOK_ITERS), DETOK_ITERS),
        ("httparse", lambda: _time(bench_httparse, HTTPARSE_ITERS), HTTPARSE_ITERS),
        ("asyncio", lambda: _time(bench_asyncio, 1) * 1e3 / ASYNCIO_TASKS, ASYNCIO_TASKS * ASYNCIO_AWAITS),
    ]

    results: dict[str, float] = {}
    print(f"interpreter: {platform.python_implementation()} {platform.python_version()}"
          f"{' (free-threaded)' if sys.version_info >= (3, 13) and not getattr(sys, '_is_gil_enabled', lambda: True)() else ''}")
    for name, fn, _iters in cases:
        best = min(fn() for _ in range(args.repeat))
        results[name] = best
        print(f"  {name:10s} {best:10.2f} ns/op")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "python": platform.python_version(),
                    "implementation": platform.python_implementation(),
                    "gil_enabled": getattr(sys, "_is_gil_enabled", lambda: True)(),
                    "machine": platform.machine(),
                    "repeat": args.repeat,
                    "ns_per_op": results,
                },
                fh,
                indent=2,
            )
            fh.write("\n")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())