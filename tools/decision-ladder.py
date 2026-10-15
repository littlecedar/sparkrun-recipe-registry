#!/usr/bin/env python3
"""Concurrent request ladder for decision-model endpoints (``/v1/systemone``).

The decision lane cannot use the registry's concurrency ladder: its arms are
prefill-only scorers that answer ``POST /v1/systemone``, so there is no chat
surface for llama-benchy to drive and no decode t/s to measure.  The lane's
published accuracy comes from ``tool-eval-bench --decision-bench-only``, which
is a *serial* pass (one request out, next request in) unless it is given
``--parallel N``; the reported instrument is therefore a fine source for
accuracy and a poor one for throughput.  This tool is the concurrent harness
the C1/C2/C5/C10 columns need: it replays real Typed Decisions cases at a
fixed concurrency and reports **requests/s** (each request is one case = five
decisions in one forward pass, so ``decisions/s`` is the same number x5).

Unit discipline:

* ``req/s`` counts completed ``/v1/systemone`` case-requests over wall time
  from first dispatch to last completion; it is a closed-loop rate, not the
  server's internal step rate.
* It is **not** t/s.  A prefill-only scorer emits no tokens, and the index's
  C-columns are decode t/s, so a ladder here never fills those cells - it
  answers "does this arm serve more cases when offered more concurrency".
* Latencies are per request (p50/p95), reported beside the rate for the same
  reason the perf profiles report TTFT: a rate alone hides queueing.

Cases come from the same vendored file the instrument scores against
(``tool-eval-bench``'s ``plugins/decision/vendor/typed_decisions/test.jsonl.gz``,
Typed Decisions test split revision ``e039ebffcc28``, 400 cases) so the
workload is the published one rather than a synthetic prompt.  ``--limit``
takes a deterministic prefix, which is what makes a CPU arm's ladder
affordable; slices are identical across levels by construction.

stdlib only.  ``--selftest`` runs a self-contained stub server and exits 0.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def load_cases(path: str, limit: int | None, offset: int = 0) -> list[dict]:
    """Read Typed Decisions rows (jsonl or jsonl.gz) -> the slice to replay."""
    opener = gzip.open if path.endswith(".gz") else open
    out: list[dict] = []
    with opener(path, "rt", encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if i < offset:
                continue
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if "state" not in row or "questions" not in row:
                raise SystemExit(f"{path}:{i + 1}: row has no state/questions (not a Typed Decisions split?)")
            out.append(row)
            if limit is not None and len(out) >= limit:
                break
    if not out:
        raise SystemExit(f"{path}: no cases read (offset {offset}, limit {limit})")
    return out


def build_payload(case: dict, model: str) -> dict:
    body = {"state": case["state"], "questions": case["questions"]}
    if model:
        body["model"] = model
    return body


def one_request(url: str, body: dict, timeout: float) -> tuple[float, int, dict | None, str | None]:
    """-> (elapsed_ms, status, decoded_body_or_None, error_or_None)."""
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        return (time.perf_counter() - started) * 1000.0, exc.code, None, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001 - any transport failure is a data point, not a crash
        return (time.perf_counter() - started) * 1000.0, 0, None, type(exc).__name__
    try:
        parsed = json.loads(raw)
    except ValueError:
        parsed = None
    return (time.perf_counter() - started) * 1000.0, status, parsed, None


def percentile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return ordered[idx]


def ladder(url: str, cases: list[dict], concurrency: int, model: str, timeout: float) -> dict:
    """One rung: replay every case, at most *concurrency* requests in flight."""
    questions = sum(len(c["questions"]) for c in cases)
    wall0 = time.perf_counter()
    lat: list[float] = []
    errors: dict[str, int] = {}
    tokens = 0
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(one_request, url, build_payload(c, model), timeout) for c in cases]
        for fut in futures:
            ms, status, body, err = fut.result()
            lat.append(ms)
            if err or status != 200 or body is None:
                key = err or f"HTTP {status}"
                errors[key] = errors.get(key, 0) + 1
                continue
            usage = body.get("usage") if isinstance(body, dict) else None
            if isinstance(usage, dict) and isinstance(usage.get("input_tokens"), int):
                tokens += usage["input_tokens"]
    wall = time.perf_counter() - wall0
    ok = len(cases) - sum(errors.values())
    return {
        "concurrency": concurrency,
        "cases": len(cases),
        "questions": questions,
        "ok": ok,
        "errors": errors,
        "wall_s": wall,
        "req_per_s": ok / wall if wall > 0 else float("nan"),
        "decisions_per_s": (ok * (questions / len(cases))) / wall if wall > 0 and cases else float("nan"),
        "p50_ms": percentile(lat, 0.50),
        "p95_ms": percentile(lat, 0.95),
        "input_tokens_per_s": tokens / wall if wall > 0 else float("nan"),
    }


def warmup(url: str, cases: list[dict], count: int, model: str, timeout: float) -> None:
    for case in cases[:count]:
        one_request(url, build_payload(case, model), timeout)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", required=False, help="decision endpoint root, e.g. http://.NN:8020")
    ap.add_argument("--cases", help="Typed Decisions jsonl/.jsonl.gz (test split)")
    ap.add_argument("--limit", type=int, default=None, help="replay only the first N cases (deterministic slice)")
    ap.add_argument("--offset", type=int, default=0, help="skip the first N cases before --limit")
    ap.add_argument("--concurrency", default="1,2,5,10", help="comma-separated levels, ascending (default 1,2,5,10)")
    ap.add_argument("--model", default="", help="model id to send (required on a real run: both lane servers require the field, clef 422s without it)")
    ap.add_argument("--timeout", type=float, default=600.0, help="per-request seconds (default 600)")
    ap.add_argument("--warmup", type=int, default=2, help="unmeasured requests first (default 2)")
    ap.add_argument("--json", help="write the per-level result as JSON here")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not args.base_url or not args.cases:
        ap.error("--base-url and --cases are required (or --selftest)")
    if not args.model:
        # Not cosmetic: clef's /v1/systemone answers 422 {"loc":["body","model"]} without it.
        ap.error("--model is required: the lane's servers reject a request with no model field")
    levels = [int(x) for x in str(args.concurrency).split(",") if x.strip()]
    if not levels or any(c < 1 for c in levels):
        ap.error("--concurrency needs positive levels")

    url = args.base_url.rstrip("/") + "/v1/systemone"
    cases = load_cases(args.cases, args.limit, args.offset)
    if args.warmup:
        warmup(url, cases, args.warmup, args.model, args.timeout)

    rows = []
    for c in levels:
        row = ladder(url, cases, c, args.model, args.timeout)
        rows.append(row)
        err = "" if not row["errors"] else "  errors: " + ", ".join(f"{k}x{v}" for k, v in sorted(row["errors"].items()))
        print(
            f"c={row['concurrency']:<3d} n={row['cases']:<4d} wall={row['wall_s']:8.2f}s  "
            f"req/s={row['req_per_s']:7.3f}  decisions/s={row['decisions_per_s']:7.2f}  "
            f"p50={row['p50_ms']:8.1f}ms p95={row['p95_ms']:8.1f}ms{err}",
            flush=True,
        )

    if args.json:
        Path(args.json).write_text(
            json.dumps(
                {
                    "base_url": url,
                    "cases": args.cases,
                    "limit": args.limit,
                    "offset": args.offset,
                    "slice_cases": len(cases),
                    "levels": rows,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"wrote {args.json}")
    return 1 if any(r["ok"] == 0 for r in rows) else 0


def _selftest() -> int:
    """Stub server + a 3-level ladder; asserts the wiring, not the numbers."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Stub(BaseHTTPRequestHandler):
        delay = 0.05

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            time.sleep(self.delay)
            answers = {
                name: {"choice": "a", "probabilities": {"a": 0.6, "b": 0.4}}
                for name, q in body["questions"].items()
                if q["type"] == "choice"
            }
            payload = json.dumps({"answers": answers, "usage": {"input_tokens": 7}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):  # silence the stub
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/v1/systemone"

    cases = [
        {"id": f"c{i}", "state": "s", "questions": {"a": {"type": "choice", "instructions": "?", "criteria": {"a": "x"}}}}
        for i in range(8)
    ]
    warmup(url, cases, 1, "stub", 30)
    r1 = ladder(url, cases, 1, "stub", 30)
    r4 = ladder(url, cases, 4, "stub", 30)
    r9 = ladder(url, cases, 9, "stub", 30)
    server.shutdown()

    assert r1["cases"] == 8 and r1["questions"] == 8, r1
    assert r1["ok"] == 8 and not r1["errors"], r1
    assert abs(r1["wall_s"] - 8 * Stub.delay) < 0.5, r1  # serial: 8 x 50 ms
    assert r4["wall_s"] < r1["wall_s"], (r1, r4)  # concurrency must actually help
    assert abs(r4["req_per_s"] - 4 / Stub.delay) / (4 / Stub.delay) < 0.5, r4
    assert r9["wall_s"] < r1["wall_s"], (r1, r9)
    assert r1["p50_ms"] >= Stub.delay * 1000, r1
    assert abs(r1["input_tokens_per_s"] - 8 * 7 / r1["wall_s"]) < 0.01, r1
    # A dead endpoint is an error count, never an exception.
    dead = ladder("http://127.0.0.1:1/v1/systemone", cases[:2], 2, "stub", 5)
    assert dead["ok"] == 0 and sum(dead["errors"].values()) == 2, dead
    # Slice selection is deterministic and ordered.
    got = load_cases(_write_fixture(cases), 3)
    assert [c["id"] for c in got] == ["c0", "c1", "c2"], got
    assert [c["id"] for c in load_cases(_write_fixture(cases), 2, offset=6)] == ["c6", "c7"]
    print("selftest OK")
    return 0


def _write_fixture(cases: list[dict]) -> str:
    import os
    import tempfile

    fd, path = tempfile.mkstemp(suffix=".jsonl.gz")
    os.close(fd)
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for c in cases:
            fh.write(json.dumps(c) + "\n")
    return path


if __name__ == "__main__":
    sys.exit(main())