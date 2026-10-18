#!/usr/bin/env python3
"""Concurrent ladder for decision-model endpoints (``/v1/systemone`` or JEV's ``/v1/completions``).

The decision lane cannot use the registry's concurrency ladder: its arms are
prefill-only scorers that answer ``POST /v1/systemone``, so there is no chat
surface for llama-benchy to drive and no decode t/s to measure.  The lane's
published accuracy comes from ``tool-eval-bench --decision-bench-only``, which
is a *serial* instrument (one request out, next request in) unless it is given
``--parallel N``; that makes it a fine source for accuracy and a poor one for
throughput.  This tool is the concurrent harness the lane's C1/C2/C5/C10
columns need: it replays real Typed Decisions cases at a fixed concurrency and
reports, per cell,

* ``req/s`` - completed requests over wall time, first dispatch to last
  completion.  This is the lane's index unit (the decision table's C-columns
  are req/s, not decode t/s), so it stays the headline number.
* ``decisions/s`` (aggregate) and ``per-req`` (the decisions/s one request
  achieves at the cell's median latency).  Read the pair together: at c1 they
  agree; once the aggregate stops rising while ``per-req`` falls, the endpoint
  is queueing requests rather than scaling with them - the flat-ladder shape
  this lane's arms show, and the finding the C-columns must carry.
* TTFT p50/p95 and latency p50/p95, plus the decisions returned against the
  decisions the slice asked for.  A non-streaming JSON body arrives whole, so
  TTFT == latency on both lane APIs; both are reported because a streaming
  server would separate them and because a rate alone hides queueing.

Units: a *decision* is one answer.  On ``/v1/systemone`` one request carries a
whole case (five decisions in one forward pass); on ``/v1/completions`` one
request is one question (JEV-9B's card contract), so one decision.  Neither is
a token rate: a prefill-only scorer decodes nothing, and a ``t/s`` number here
would be a category error.

Cases come from the same vendored file the instrument scores
(``tool-eval-bench``'s ``plugins/decision/vendor/typed_decisions/test.jsonl.gz``,
Typed Decisions test split revision ``e039ebffcc28``, 400 cases) so the
workload is the published one rather than a synthetic prompt.  ``--limit``
takes a deterministic prefix and ``--runs`` repeats the slice (default 5, the
registry's five-run convention); both are identical across levels by
construction.

**A cell is verified, never merely timed.**  A 4xx, a transport failure, an
unparseable body, a body truncated short of its ``Content-Length``, a response
carrying fewer decisions than the case has questions, or zero decisions marks
the cell ``ok: false`` with its error counts, and the run exits 1.  A cell with
failures is never averaged into a rate: the rate it would report is the
survivors' rate, which is not the endpoint's.

stdlib only.  ``--selftest`` runs a self-contained stub server (no model, no
network) and exits 0.
"""

from __future__ import annotations

import argparse
import gzip
import http.client
import importlib.util
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
API_PATHS = {"systemone": "/v1/systemone", "completions": "/v1/completions"}


DEFAULT_CONCURRENCY = "1,2,5,10"
DEFAULT_RUNS = 5  # the registry's five-run convention, pooled into one rate

_JEV = None


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


def jev_module():
    """Load ``tools/jev-decision-bench.py`` by sibling path (the house idiom).

    The JEV wire shape lives there because that tool owns the card's contract;
    importing it keeps ``--api completions`` from becoming a lookalike.
    """
    global _JEV
    if _JEV is None:
        path = Path(__file__).resolve().parent / "jev-decision-bench.py"
        spec = importlib.util.spec_from_file_location("jev_decision_bench", path)
        assert spec and spec.loader, f"cannot load {path}"
        module = importlib.util.module_from_spec(spec)
        sys.modules["jev_decision_bench"] = module
        spec.loader.exec_module(module)
        _JEV = module
    return _JEV


def systemone_requests(cases: list[dict], model: str) -> list[tuple[dict, int]]:
    """-> [(body, decisions the response must carry)] for ``/v1/systemone``."""
    out: list[tuple[dict, int]] = []
    for case in cases:
        body: dict = {"state": case["state"], "questions": case["questions"]}
        if model:
            body["model"] = model
        out.append((body, len(case["questions"])))
    return out


def completions_requests(cases: list[dict], model: str, head: dict) -> list[tuple[dict, int]]:
    """-> one card-shaped ``/v1/completions`` body per question (one decision each)."""
    jev = jev_module()
    out: list[tuple[dict, int]] = []
    for case in cases:
        state = jev.state_to_text(case["state"])
        for question in case["questions"].values():
            kind, text, options = jev.render_question(question)
            ids, _bias = jev.head_slice(head, kind, len(options))
            prompt = jev.render_prompt(kind, state, text, options)
            out.append((jev.completion_body(model, prompt, ids), 1))
    return out


def one_request(url: str, body: dict, timeout: float) -> dict:
    """One POST -> ``{status, ttft_ms, total_ms, body, error}``.

    ``error`` is ``None`` on a clean 200 with a parseable body; anything else is
    the reason the request counts as a failure.  ``ttft_ms`` is the first
    response *byte*, not the first token: these APIs answer in one JSON body.
    """
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            first = resp.read(1)
            ttft_ms = (time.perf_counter() - started) * 1000.0
            raw = first + resp.read()
    except urllib.error.HTTPError as exc:  # 4xx/5xx: a data point, not a crash
        return _failure(f"HTTP {exc.code}", started)
    except http.client.IncompleteRead:  # Content-Length promised more than arrived
        return _failure("truncated", started)
    except Exception as exc:  # noqa: BLE001 - any transport failure is a data point
        return _failure(type(exc).__name__, started)
    total_ms = (time.perf_counter() - started) * 1000.0
    if status != 200:
        return _failure(f"HTTP {status}", started, ttft_ms, total_ms)
    try:
        parsed = json.loads(raw)
    except ValueError:
        return _failure("malformed-json", started, ttft_ms, total_ms)
    return {"status": status, "ttft_ms": ttft_ms, "total_ms": total_ms, "body": parsed, "error": None}


def _failure(error: str, started: float, ttft_ms: float | None = None, total_ms: float | None = None) -> dict:
    elapsed = (time.perf_counter() - started) * 1000.0
    return {
        "status": 0,
        "ttft_ms": elapsed if ttft_ms is None else ttft_ms,
        "total_ms": elapsed if total_ms is None else total_ms,
        "body": None,
        "error": error,
    }


def count_decisions(api: str, body) -> tuple[int, str | None]:
    """-> (decisions carried by this response, malformed-shape reason or None)."""
    if api == "systemone":
        answers = body.get("answers") if isinstance(body, dict) else None
        if not isinstance(answers, dict):
            return 0, "malformed-response"  # a 200 with no answers map is not a decision
        return len(answers), None
    try:
        top = body["choices"][0]["logprobs"]["top_logprobs"][0]
    except (KeyError, IndexError, TypeError):
        return 0, "malformed-response"
    return (1, None) if top else (0, "no-decisions")


def percentile(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile, q in [0, 1]; None for no values (never NaN in JSON)."""
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return ordered[idx]


def cell(
    url: str, requests: list[tuple[dict, int]], concurrency: int, api: str, timeout: float, runs: int = 1
) -> dict:
    """One rung: every request, ``runs`` times, at most *concurrency* in flight."""
    tasks = requests * runs
    expected = sum(want for _, want in tasks)
    lat: list[float] = []
    ttft: list[float] = []
    served: list[int] = []
    errors: dict[str, int] = {}
    decisions = ok = 0

    wall0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(one_request, url, body, timeout) for body, _ in tasks]
        results = [(fut.result(), want) for fut, (_, want) in zip(futures, tasks)]
    wall = time.perf_counter() - wall0

    for result, want in results:
        lat.append(result["total_ms"])
        ttft.append(result["ttft_ms"])
        error = result["error"]
        got = 0
        if error is None:
            got, error = count_decisions(api, result["body"])
            if error is None and got < want:
                error = "no-decisions" if got == 0 else f"short-answer {got}/{want}"
        if error:
            errors[error] = errors.get(error, 0) + 1
            continue
        ok += 1
        decisions += got
        served.append(got)

    p50_ms = percentile(lat, 0.50)
    decisions_per_s = decisions / wall if wall > 0 else None
    # One request's own rate at the cell's median latency: at c1 this equals
    # the aggregate; when it falls while the aggregate stalls, requests are
    # queueing rather than batching.
    per_request_rate = (
        (sum(served) / len(served)) / (p50_ms / 1000.0) if served and p50_ms else None
    )
    return {
        "concurrency": concurrency,
        "requests": len(tasks),
        "ok_requests": ok,
        "failed_requests": len(tasks) - ok,
        "decisions": decisions,
        "expected_decisions": expected,
        "wall_s": wall,
        "req_per_s": ok / wall if wall > 0 else None,
        "decisions_per_s": decisions_per_s,
        "per_request_decisions_per_s": per_request_rate,
        "ttft_ms_p50": percentile(ttft, 0.50),
        "ttft_ms_p95": percentile(ttft, 0.95),
        "latency_ms_p50": p50_ms,
        "latency_ms_p95": percentile(lat, 0.95),
        "errors": errors,
        "ok": ok == len(tasks) and decisions == expected and decisions > 0,
    }


def verdict(rows: list[dict]) -> int:
    """0 only if every cell was verified; a failed cell is a failed run."""
    return 0 if rows and all(row["ok"] for row in rows) else 1


def warmup(url: str, requests: list[tuple[dict, int]], count: int, timeout: float) -> None:
    for body, _ in requests[:count]:
        one_request(url, body, timeout)


def _fmt(value: float | None, spec: str) -> str:
    return "-" if value is None else format(value, spec)


def report(rows: list[dict]) -> None:
    for row in rows:
        line = (
            f"c={row['concurrency']:<3d} n={row['ok_requests']}/{row['requests']:<4d}"
            f" req/s={_fmt(row['req_per_s'], '7.3f')}"
            f" decisions/s={_fmt(row['decisions_per_s'], '8.2f')}"
            f" per-req={_fmt(row['per_request_decisions_per_s'], '7.2f')}"
            f" dec={row['decisions']}/{row['expected_decisions']}"
            f"  ttft p50={_fmt(row['ttft_ms_p50'], '8.1f')} p95={_fmt(row['ttft_ms_p95'], '8.1f')} ms"
            f"  lat p50={_fmt(row['latency_ms_p50'], '8.1f')} p95={_fmt(row['latency_ms_p95'], '8.1f')} ms"
        )
        if not row["ok"]:
            line += "  FAILED: " + ", ".join(f"{k}x{v}" for k, v in sorted(row["errors"].items()))
        print(line, flush=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", required=False, help="decision endpoint root, e.g. http://.NN:8020")
    ap.add_argument("--cases", help="Typed Decisions jsonl/.jsonl.gz (test split)")
    ap.add_argument("--api", choices=sorted(API_PATHS), default="systemone",
                    help="systemone (clef/Kai/Sol, one case per request) or completions (JEV-9B, one question)")
    ap.add_argument("--decision-head", help="JEV decision-head json; required by --api completions for its token ids")
    ap.add_argument("--limit", type=int, default=None, help="replay only the first N cases (deterministic slice)")
    ap.add_argument("--offset", type=int, default=0, help="skip the first N cases before --limit")
    ap.add_argument("--concurrency", default=DEFAULT_CONCURRENCY,
                    help=f"comma-separated levels, ascending (default {DEFAULT_CONCURRENCY})")
    ap.add_argument("--runs", type=int, default=DEFAULT_RUNS,
                    help=f"closed-loop passes over the slice per cell (default {DEFAULT_RUNS}; 1 = one pass)")
    ap.add_argument("--model", default="", help="model id to send (required on a real run: both lane servers reject a request with no model field)")
    ap.add_argument("--timeout", type=float, default=600.0, help="per-request seconds (default 600)")
    ap.add_argument("--warmup", type=int, default=2, help="unmeasured requests first (default 2)")
    ap.add_argument("--json", help="write the per-cell result as JSON here")
    ap.add_argument("--selftest", action="store_true")
    try:
        args = ap.parse_args(argv)
        try:
            levels = [int(x) for x in str(args.concurrency).split(",") if x.strip()]
        except ValueError:
            ap.error("--concurrency takes integers, e.g. 1,2,5,10")
        if not args.selftest:
            if not args.base_url or not args.cases:
                ap.error("--base-url and --cases are required (or --selftest)")
            if not args.model:
                # Not cosmetic: clef's /v1/systemone answers 422 {"loc":["body","model"]} without it.
                ap.error("--model is required: the lane's servers reject a request with no model field")
            if not levels or any(c < 1 for c in levels):
                ap.error("--concurrency needs positive levels")
            if args.runs < 1:
                ap.error("--runs needs a positive count")
            if args.api == "completions" and not args.decision_head:
                ap.error("--api completions needs --decision-head: the card's option-token ids live there")
    except SystemExit as exc:  # a bad flag returns, so callers and tests get the code
        return int(exc.code or 0)

    if args.selftest:
        return _selftest()

    url = args.base_url.rstrip("/") + API_PATHS[args.api]
    cases = load_cases(args.cases, args.limit, args.offset)
    if args.api == "systemone":
        requests = systemone_requests(cases, args.model)
    else:
        head = json.loads(Path(args.decision_head).expanduser().read_text(encoding="utf-8"))
        requests = completions_requests(cases, args.model, head)
    if args.warmup:
        warmup(url, requests, args.warmup, args.timeout)

    rows = []
    for concurrency in levels:
        row = cell(url, requests, concurrency, args.api, args.timeout, args.runs)
        rows.append(row)
        report([row])

    if args.json:
        Path(args.json).write_text(
            json.dumps(
                {
                    "base_url": url,
                    "api": args.api,
                    "cases": args.cases,
                    "limit": args.limit,
                    "offset": args.offset,
                    "slice_cases": len(cases),
                    "requests_per_run": len(requests),
                    "runs": args.runs,
                    "cells": rows,
                    "ok": all(row["ok"] for row in rows),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"wrote {args.json}")
    return verdict(rows)


def _selftest() -> int:
    """Stub server + a ladder; asserts the wiring AND the reported numbers."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    delay = 0.04

    class Stub(BaseHTTPRequestHandler):
        mode = "good"
        admit = threading.Semaphore(2)  # the stub's own ceiling: proves saturation
        lock = threading.Lock()
        hits = 0

        def log_message(self, format, *args):  # silence the stub
            pass

        def _send(self, payload: bytes, code: int = 200) -> None:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            body = json.loads(raw or b"{}")
            with Stub.lock:
                Stub.hits += 1
                hit = Stub.hits
            with Stub.admit:
                time.sleep(delay)
            if Stub.mode == "http500":
                return self._send(b'{"error": "boom"}', 500)
            if Stub.mode == "malformed":
                return self._send(b'{"answers": ', 200)
            if Stub.mode == "truncated":
                payload = json.dumps({"answers": {}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload) + 64))
                self.end_headers()
                self.wfile.write(payload)
                self.wfile.flush()
                self.close_connection = True
                return
            if Stub.mode == "empty":
                return self._send(b'{"answers": {}}', 200)
            if Stub.mode == "flaky" and hit % 3 == 0:
                return self._send(b'{"error": "boom"}', 500)
            if self.path.endswith("/v1/completions"):
                reply = {"choices": [{"logprobs": {"top_logprobs": [{"5": -0.1}]}}]}
                return self._send(json.dumps(reply).encode(), 200)
            answers = {name: {"choice": "a", "probabilities": {"a": 0.6, "b": 0.4}} for name in body["questions"]}
            return self._send(json.dumps({"answers": answers, "usage": {"input_tokens": 7}}).encode(), 200)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"

    cases = [
        {
            "id": f"c{i}",
            "state": "s",
            "questions": {
                "q1": {"type": "choice", "instructions": "?", "criteria": {"a": "x", "b": "y"}},
                "q2": {"type": "noul", "instructions": "?", "criteria": {}},
            },
        }
        for i in range(6)
    ]
    requests = systemone_requests(cases, "stub")
    assert len(requests) == 6 and all(want == 2 for _, want in requests), requests
    url = base + "/v1/systemone"

    r1 = cell(url, requests, 1, "systemone", 30.0, 1)
    r2 = cell(url, requests, 2, "systemone", 30.0, 1)
    r6 = cell(url, requests, 6, "systemone", 30.0, 1)

    # Every cell verified: 6 requests, 2 decisions each.
    for row in (r1, r2, r6):
        assert row["ok"] and row["failed_requests"] == 0, row
        assert row["requests"] == 6 and row["decisions"] == 12, row
        assert row["expected_decisions"] == 12, row
        assert row["ttft_ms_p50"] >= delay * 1000 * 0.9, row
        assert row["ttft_ms_p95"] >= row["ttft_ms_p50"], row
    # Serial at c1: 6 x 40 ms, one request carrying two decisions.
    assert 0.15 <= r1["wall_s"] <= 0.60, r1
    assert 20.0 <= r1["decisions_per_s"] <= 80.0, r1
    assert 20.0 <= r1["per_request_decisions_per_s"] <= 80.0, r1
    # At c1 the aggregate IS the per-request rate (one request in flight).
    assert abs(r1["decisions_per_s"] - r1["per_request_decisions_per_s"]) < 0.3 * r1["decisions_per_s"], r1
    assert r1["ttft_ms_p50"] < r1["wall_s"] * 1000.0, r1  # TTFT is per request, never the wall
    assert abs(r1["req_per_s"] - 6 / r1["wall_s"]) < 1e-9, r1
    # Concurrency helps up to the stub's ceiling of 2, then saturates: the c6
    # rung must NOT report 6x the c1 rate, and queueing must show up as a
    # per-request rate below the aggregate.
    assert r6["decisions_per_s"] > 1.5 * r1["decisions_per_s"], (r1, r6)
    assert r2["decisions_per_s"] > 1.4 * r1["decisions_per_s"], (r1, r2)
    assert r6["decisions_per_s"] < 1.4 * r2["decisions_per_s"], (r2, r6)
    assert r6["per_request_decisions_per_s"] < 0.75 * r6["decisions_per_s"], r6

    # Failure modes: each is a FAILED cell, never a rate over the survivors.
    bad = requests[:2]
    for mode in ("http500", "malformed", "truncated", "empty"):
        Stub.mode = mode
        row = cell(url, bad, 2, "systemone", 30.0, 1)
        assert not row["ok"] and row["decisions"] == 0 and row["errors"], (mode, row)
        assert verdict([r1, row]) == 1, (mode, row)
    Stub.mode = "flaky"
    partial = cell(url, requests, 2, "systemone", 30.0, 1)
    assert not partial["ok"] and 0 < partial["decisions"] < partial["expected_decisions"], partial
    assert verdict([partial]) == 1, partial
    Stub.mode = "good"

    # --runs repeats the slice; the verdict stays a verdict.
    Stub.hits = 0
    ran = cell(url, requests, 3, "systemone", 30.0, 2)
    assert ran["requests"] == 12 and ran["decisions"] == 24 == ran["expected_decisions"], ran
    assert verdict([r1, r2, r6]) == 0

    # JEV's contract: one question per request, one decision per reply.
    head = {"verbalizer_ids": [10, 11, 12, 13], "bias": [0.0, 0.0, 0.0, 0.0],
            "slots": {"ranges": {"choice": [0], "score": [2], "noul": [2]}}}
    jobs = completions_requests(cases[:2], "stub", head)
    assert len(jobs) == 4 and all(want == 1 for _, want in jobs), jobs
    assert "allowed_token_ids" in jobs[0][0] and jobs[0][0]["max_tokens"] == 1, jobs[0][0]
    comp = cell(base + "/v1/completions", jobs, 2, "completions", 30.0, 1)
    assert comp["ok"] and comp["decisions"] == 4 == comp["expected_decisions"], comp

    # A dead endpoint is an error count, never an exception.
    dead = cell("http://127.0.0.1:1/v1/systemone", bad, 2, "systemone", 5.0, 1)
    assert not dead["ok"] and dead["ok_requests"] == 0, dead

    # Slice selection is deterministic and ordered.
    got = load_cases(_write_fixture(cases), 3)
    assert [c["id"] for c in got] == ["c0", "c1", "c2"], got
    assert [c["id"] for c in load_cases(_write_fixture(cases), 2, offset=5)] == ["c5"], got

    server.shutdown()
    server.server_close()
    print("selftest OK")
    return 0


def _write_fixture(cases: list[dict]) -> str:
    import os
    import tempfile

    fd, path = tempfile.mkstemp(suffix=".jsonl.gz")
    os.close(fd)
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for case in cases:
            fh.write(json.dumps(case) + "\n")
    return path


if __name__ == "__main__":
    sys.exit(main())
