#!/usr/bin/env python3
"""Serve the decision ensemble: one ``/v1/systemone`` endpoint pooling two models.

The clef-flash + Kai-0.6B ensemble is a *client-side* rule over per-question
distributions, which is exactly the kind of thing a third party re-implements
slightly differently (mean-then-argmax, argmax-then-vote, log-linear, a
different tie-break) and then cannot reproduce the published number with.
This proxy is the reference implementation: point it at two live decision
servers and it answers the same wire shape both of them answer, with each
question's distribution pooled by ``tools/decision-tandem.py``'s rule - an
equal-weight **linear mean**, renormalised, argmax with labels as the
tie-break.  The pooling functions are *imported from* that analysis tool, so
the served ensemble and the analysed ensemble cannot drift apart.

Measured 2026-10-15 (`.34`): clef-flash ``:8020`` + Kai-0.6B ``:8000`` behind
this proxy scores 71.6% (1432/2000) on the Typed Decisions test split against
clef's 70.3% alone - the same number the offline pooling of the two reports
gives (see `recipes/decision/README.md`).

Usage:

    python3 tools/decision-ensemble.py --a http://node:8020 --b http://node:8000 \
        --a-model Cloudflare/clef-flash --b-model vllm-sr/Decision-2.0-Kai-0.6B --port 8021
    uvx tool-eval-bench@2.8.0 --base-url http://node:8021 --decision-bench-only

Notes: a request is only answered when **both** members answer (502 otherwise,
so a half-live pool is an infrastructure failure rather than a silent
pass-through).  ``usage.input_tokens`` is the sum of the two members' usage -
the ensemble's actual compute bill.  noul questions pool their ``noul``
scalar; choice/score questions pool ``probabilities`` over the union of both
label spaces.

stdlib only.  ``--selftest`` runs two stub members and exits 0.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

_RULE = importlib.util.spec_from_file_location("decision_tandem", Path(__file__).with_name("decision-tandem.py"))
assert _RULE and _RULE.loader
tandem = importlib.util.module_from_spec(_RULE)
_RULE.loader.exec_module(tandem)


def pooled_answers(questions: dict, a: dict, b: dict) -> dict:
    """Pool two ``answers`` objects question-by-question (raises on shape drift)."""
    out: dict = {}
    for name, question in questions.items():
        qa, qb = (a or {}).get(name), (b or {}).get(name)
        if not isinstance(qa, dict) or not isinstance(qb, dict):
            raise ValueError(f"both members must answer {name!r}")
        if question.get("type") == "noul":
            out[name] = {"noul": 0.5 * float(qa["noul"]) + 0.5 * float(qb["noul"])}
            continue
        pa = {str(k): float(v) for k, v in qa["probabilities"].items()}
        pb = {str(k): float(v) for k, v in qb["probabilities"].items()}
        pooled = tandem.normalise(tandem.linear(pa, pb))
        label = tandem.argmax(pooled)
        answer = {"probabilities": pooled}
        if question.get("type") == "score":
            answer["score"] = float(label)
        else:
            answer["choice"] = label
        out[name] = answer
    return out


def post(url: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def get(url: str, timeout: float) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except Exception:  # noqa: BLE001 - an unreachable member is "not ready", not a crash
        return 0, b""


class Handler(BaseHTTPRequestHandler):
    server_version = "decision-ensemble"
    a_url = ""
    b_url = ""
    a_model = ""
    b_model = ""
    as_model = "decision-ensemble"
    # Not `timeout`: socketserver's BaseRequestHandler already defines that as
    # ``float | None`` (the socket timeout), and shadowing it invites confusion.
    member_timeout: float = 600.0

    def _send(self, status: int, payload: bytes, ctype: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path.rstrip("/") in ("/health", ""):
            codes = [get(u.rstrip("/") + "/health", 10)[0] for u in (self.a_url, self.b_url)]
            body = json.dumps({"members": codes, "ok": all(c == 200 for c in codes)}).encode()
            return self._send(200 if all(c == 200 for c in codes) else 503, body)
        if self.path.rstrip("/") == "/v1/models":
            # Exactly ONE model. A merged list from both members reads as an
            # ambiguous choice to a client that auto-detects the model and then
            # prompts for a number interactively (observed with tool-eval-bench
            # v2.8.0: 3.7 GB of "Select model [1-2]:" into a log before the run
            # was killed). The proxy is one endpoint serving one ensemble, and
            # the per-member model names are set by --a-model/--b-model, so the
            # client's model string never reaches a member anyway.
            body = json.dumps(
                {"object": "list", "data": [{"id": self.as_model, "object": "model", "owned_by": "decision-ensemble"}]}
            ).encode()
            return self._send(200, body)
        return self._send(404, b'{"error":"only /v1/systemone, /v1/models and /health are served"}')

    def do_POST(self):
        if self.path.rstrip("/") != "/v1/systemone":
            return self._send(404, b'{"error":"only /v1/systemone is served"}')
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            questions = body["questions"]
        except (ValueError, KeyError, TypeError) as exc:
            return self._send(400, json.dumps({"error": f"bad request body: {exc}"}).encode())

        # One pair of threads per client request, not a shared pool: the proxy must
        # never be the concurrency ceiling for the ensemble it serves (a fixed pool
        # of two would serialize every client, capping the served ensemble at one
        # request in flight).
        members: dict[str, dict] = {}
        failures: list[Exception] = []

        def send(key: str, member_url: str, model: str) -> None:
            payload = dict(body)
            if model:
                payload["model"] = model
            try:
                members[key] = post(member_url.rstrip("/") + "/v1/systemone", payload, self.member_timeout)
            except Exception as exc:  # noqa: BLE001 - either member failing means "no answer"
                failures.append(exc)

        threads = [
            threading.Thread(target=send, args=(k, u, m), daemon=True)
            for k, u, m in (("a", self.a_url, self.a_model), ("b", self.b_url, self.b_model))
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        if failures or len(members) != 2:
            exc = failures[0] if failures else RuntimeError("a member did not answer")
            return self._send(502, json.dumps({"error": f"member failed: {type(exc).__name__}: {exc}"}).encode())
        ra, rb = members["a"], members["b"]

        try:
            answers = pooled_answers(questions, ra.get("answers") or {}, rb.get("answers") or {})
        except (ValueError, KeyError, TypeError) as exc:
            return self._send(502, json.dumps({"error": f"pooling failed: {exc}"}).encode())
        tokens = 0
        for r in (ra, rb):
            usage = r.get("usage") if isinstance(r, dict) else None
            if isinstance(usage, dict) and isinstance(usage.get("input_tokens"), int):
                tokens += usage["input_tokens"]
        return self._send(200, json.dumps({"answers": answers, "usage": {"input_tokens": tokens}}).encode())

    def log_message(self, format, *args):
        print("[ensemble] " + format % args, file=sys.stderr, flush=True)


def serve(
    a_url: str, b_url: str, port: int, host: str, a_model: str, b_model: str, timeout: float, as_model: str
) -> int:
    Handler.a_url, Handler.b_url = a_url, b_url
    Handler.a_model, Handler.b_model = a_model, b_model
    Handler.as_model = as_model
    Handler.member_timeout = float(timeout)
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"ensemble on http://{host}:{port}/v1/systemone  =  {a_url} + {b_url}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", help="first member base url (the GPU arm), e.g. http://node:8020")
    ap.add_argument("--b", help="second member base url (the CPU arm), e.g. http://node:8000")
    ap.add_argument("--a-model", default="", help="model name to send to A (default: whatever the client sent)")
    ap.add_argument("--b-model", default="", help="model name to send to B (default: whatever the client sent)")
    ap.add_argument("--as-model", default="decision-ensemble", help="model id this proxy advertises")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8021)
    ap.add_argument("--timeout", type=float, default=600.0)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()
    if not args.a or not args.b:
        ap.error("--a and --b are required (or --selftest)")
    return serve(args.a, args.b, args.port, args.host, args.a_model, args.b_model, args.timeout, args.as_model)


def _selftest() -> int:
    """Two stub members (deliberately disagreeing) + the proxy; asserts the rule."""
    class Member(BaseHTTPRequestHandler):
        choice_dist: ClassVar[dict] = {}
        score_dist: ClassVar[dict] = {"0": 0.5, "1": 0.5}
        noul: ClassVar[float] = 0.0
        delay: ClassVar[float] = 0.25  # so the concurrency assertion below can measure overlap

        def do_GET(self):
            if self.path.rstrip("/") == "/health":
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"ok")
                return
            self.send_response(404)
            self.end_headers()

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            time.sleep(self.delay)
            answers = {}
            for name, q in body["questions"].items():
                if q["type"] == "noul":
                    answers[name] = {"noul": self.noul}
                elif q["type"] == "score":
                    answers[name] = {"score": 0.0, "probabilities": dict(self.score_dist)}
                else:
                    answers[name] = {"choice": tandem.argmax(self.choice_dist), "probabilities": dict(self.choice_dist)}
            payload = json.dumps({"answers": answers, "usage": {"input_tokens": 3}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):
            pass

    class A(Member):
        choice_dist = {"keep": 0.8, "stop": 0.2}
        score_dist = {"0": 0.6, "1": 0.4}
        noul = 0.9

    class B(Member):
        choice_dist = {"keep": 0.2, "stop": 0.8, "hold": 0.0}
        score_dist = {"0": 0.4, "1": 0.6}
        noul = 0.1

    servers = []
    for cls in (A, B):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), cls)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)

    questions = {
        "action": {"type": "choice", "instructions": "?", "criteria": {"keep": "k", "stop": "s"}},
        "risk": {"type": "score", "instructions": "?", "criteria": ["0", "1"]},
        "urgent": {"type": "noul", "instructions": "?"},
    }
    a = {"action": {"choice": "keep", "probabilities": {"keep": 0.8, "stop": 0.2}},
         "risk": {"score": 0.0, "probabilities": {"0": 0.6, "1": 0.4}},
         "urgent": {"noul": 0.9}}
    b = {"action": {"choice": "stop", "probabilities": {"keep": 0.2, "stop": 0.8, "hold": 0.0}},
         "risk": {"score": 1.0, "probabilities": {"0": 0.4, "1": 0.6}},
         "urgent": {"noul": 0.1}}
    pooled = pooled_answers(questions, a, b)
    # Linear mean over the union, renormalised: keep .5 / stop .5 / hold 0 -> tie
    # broken by label (decision-tandem.py's argmax maximises (p, label), i.e. the
    # *greater* label wins a tie: "stop" > "keep", "1" > "0").
    assert pooled["action"]["probabilities"] == {"hold": 0.0, "keep": 0.5, "stop": 0.5}, pooled
    assert pooled["action"]["choice"] == "stop", pooled
    assert pooled["risk"]["probabilities"] == {"0": 0.5, "1": 0.5}, pooled
    assert pooled["risk"]["score"] == 1.0, pooled
    assert abs(pooled["urgent"]["noul"] - 0.5) < 1e-12, pooled
    # Drift guard: the proxy must pool exactly what the analysis tool pools.
    ref = tandem.linear(a["action"]["probabilities"], b["action"]["probabilities"])
    assert {k: round(v, 12) for k, v in ref.items()} == pooled["action"]["probabilities"], (ref, pooled)
    # A missing answer is an error, not a silent zero.
    try:
        pooled_answers(questions, a, {"action": b["action"]})
    except ValueError:
        pass
    else:
        raise AssertionError("missing answer must raise")

    port_server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    Handler.a_url = f"http://127.0.0.1:{servers[0].server_port}"
    Handler.b_url = f"http://127.0.0.1:{servers[1].server_port}"
    Handler.a_model = Handler.b_model = "stub"
    threading.Thread(target=port_server.serve_forever, daemon=True).start()
    live = f"http://127.0.0.1:{port_server.server_port}"
    status, raw = get(live + "/health", 10)
    assert status == 200 and json.loads(raw)["ok"] is True, (status, raw)
    got = post(live + "/v1/systemone", {"state": "s", "questions": questions}, 30)
    assert got["answers"]["action"]["choice"] == "stop", got  # tie -> greater label, the analysed rule
    assert got["usage"]["input_tokens"] == 6, got  # members bill 3 each
    # Concurrency: the proxy must not be the ensemble's ceiling. Four clients at
    # 0.25 s of stub work overlap (~0.3 s) if the fan-out is per request; a shared
    # 2-slot pool would serialize them (~1.0 s+).
    from concurrent.futures import ThreadPoolExecutor as _Pool

    started = time.perf_counter()
    with _Pool(max_workers=4) as pool:
        outs = list(pool.map(lambda _: post(live + "/v1/systemone", {"state": "s", "questions": questions}, 30), range(4)))
    elapsed = time.perf_counter() - started
    assert all(o["answers"]["action"]["choice"] == "stop" for o in outs), outs
    assert elapsed < 0.8, f"proxy serialized concurrent clients: {elapsed:.2f}s for 4 x {Member.delay}s of member work"
    status, raw = get(live + "/v1/models", 10)
    assert status == 200, status
    # Exactly one advertised model: two entries make an auto-detecting client prompt
    # interactively for which one to use (tool-eval-bench v2.8.0 did, into a log).
    listed = json.loads(raw)["data"]
    assert len(listed) == 1 and listed[0]["id"] == "decision-ensemble", listed
    # Member down -> 503 health, 502 on the decision path (never a pass-through).
    servers[1].shutdown()
    servers[1].server_close()
    status, raw = get(live + "/health", 10)
    assert status == 503 and json.loads(raw)["ok"] is False, (status, raw)
    port_server.shutdown()
    servers[0].shutdown()
    print("selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())