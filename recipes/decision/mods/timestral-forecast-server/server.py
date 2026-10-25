#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Timestral forecasting server (stdlib, behind the `runtime: vllm` contract).

Timestral is not an LLM and no engine serves it: this script *is* the server for
the decision lane's CPU forecast arm, in the shape of the pyannote CPU serve.
It is launched by the recipe as

    taskset -c <cores> python3 /cache/runtime/timestral/forecast_server.py ...

Surface (this arm has no chat completions):

    GET  /health      -> {"status": "ok", ...}   liveness for sparkrun
    GET  /v1/models   -> the loaded repo id      (sparkrun's readiness asks this path)
    POST /forecast    -> run the forecaster, return the 21-quantile grids

POST /forecast body (JSON):
    {"series": [[float|None, ...], ...],      # (series, time); NaN -> null
     "horizon": 96,
     "known": [[...], ...],                   # optional known-future covariates, (series, T + horizon)
     "past": [[...], ...]}                    # optional past-only covariates, (series, T)

Response: per-series {"median": [h], "quantiles": {"0.01": [h], ..., "0.99": [h]},
"quantile_levels": [21]}, plus wall/peak-RSS metadata. Quantile keys spell the
21 levels 0.01, 0.05, ... 0.95, 0.99 — the grid tools/forecast-bench.py scores.

Errors follow the pyannote convention: a bad request is 400 with {"error": ...};
a server fault is 500 with its traceback in the log only.
"""
from __future__ import annotations

import argparse
import json
import os
import resource
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATE: dict = {
    "forecaster": None,
    "model_id": None,
    "requests": 0,
    "attempts": 0,
    "failed": 0,
    "lock": threading.Lock(),
}

QUANTILE_KEYS = ["0.01", "0.05", "0.1", "0.15", "0.2", "0.25", "0.3", "0.35", "0.4",
                 "0.45", "0.5", "0.55", "0.6", "0.65", "0.7", "0.75", "0.8",
                 "0.85", "0.9", "0.95", "0.99"]


def log(msg):
    print("[timestral] %s" % msg, flush=True)


def peak_rss_gib():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)


def resolve_snapshot_dir(model: str) -> str:
    """Map a repo id to its local HF snapshot dir; pass a path through untouched.

    The upstream `load_model` routes a repo id through `snapshot_download`, which
    under HF_HUB_OFFLINE dies with LocalEntryNotFoundError when the snapshot is
    not keyed by the requested revision — and the staged pool snapshot is. A
    local path skips the Hub entirely (the card's own "local directory with
    config.json and model.safetensors" loading option).
    """
    if os.path.isdir(model):
        return model
    cache_root = os.environ.get("HF_HUB_CACHE", "/cache/huggingface/hub")
    repo_dir = os.path.join(cache_root, "models--" + model.replace("/", "--"))
    if not os.path.isdir(repo_dir):
        return model  # let timestral raise its own error for an unknown id
    refs_main = os.path.join(repo_dir, "refs", "main")
    if os.path.isfile(refs_main):
        with open(refs_main) as fh:
            pin = fh.read().strip()
        snapshot = os.path.join(repo_dir, "snapshots", pin)
        if os.path.isfile(os.path.join(snapshot, "config.json")):
            return snapshot
    return model


def load_forecaster(model: str, revision: str):
    from timestral import TimestralForecaster
 
    t0 = time.time()
    model = resolve_snapshot_dir(model)
    # A local snapshot path never touches the Hub (the checkpoint is staged);
    # from_pretrained also takes local dirs per the card's Loading options.
    fc = TimestralForecaster.from_pretrained(model, local_files_only=True)
    load_s = time.time() - t0
    log("loaded %s (rev %s) in %.1f s; peak RSS %.2f GiB" % (model, revision, load_s, peak_rss_gib()))
    return fc, load_s


def _matrix(rows, name, expect_time=None):
    """Validate a (series, time) matrix of floats; None becomes NaN."""
    import math

    if not isinstance(rows, list) or not rows:
        raise ClientError("%s must be a non-empty list of series rows" % name)
    out = []
    width = None
    for r in rows:
        if not isinstance(r, list):
            raise ClientError("%s rows must be lists" % name)
        if width is None:
            width = len(r)
        elif len(r) != width:
            raise ClientError("%s rows must have equal length" % name)
        out.append([math.nan if v is None else float(v) for v in r])
    if expect_time is not None and width != expect_time:
        raise ClientError("%s must have %d steps, got %d" % (name, expect_time, width))
    return out


def run_forecast(req: dict) -> dict:
    import numpy as np

    context = _matrix(req.get("series"), "series")
    try:
        horizon = int(req.get("horizon", 96))
    except (TypeError, ValueError):
        raise ClientError("horizon must be an integer")
    if not 1 <= horizon <= 1024:
        raise ClientError("horizon must be in [1, 1024] (one decode block)")

    ctx = np.asarray(context, dtype=float)          # (S, T)
    known = req.get("known")
    past = req.get("past")
    kwargs = {"prediction_length": horizon}
    if known is not None:
        kn = np.asarray(_matrix(known, "known"), dtype=float)   # (C, T + h)
        if kn.shape[1] != ctx.shape[1] + horizon:
            raise ClientError("known must have T + horizon steps (%d), got %d"
                              % (ctx.shape[1] + horizon, kn.shape[1]))
        kwargs["known_covariates"] = kn
    if past is not None:
        pa = np.asarray(_matrix(past, "past"), dtype=float)     # (C, T)
        if pa.shape[1] != ctx.shape[1]:
            raise ClientError("past must have T steps (%d), got %d" % (ctx.shape[1], pa.shape[1]))
        kwargs["past_covariates"] = pa

    t0 = time.time()
    with STATE["lock"]:
        fc = STATE["forecaster"].forecast(ctx, **kwargs)
    elapsed = time.time() - t0

    q = fc.quantiles          # (S, 1, h, 21) — univariate rows here
    per_series = []
    for s in range(q.shape[0]):
        levels = {k: [round(float(x), 8) for x in q[s, 0, :, i]]
                  for i, k in enumerate(QUANTILE_KEYS)}
        per_series.append({
            "median": [round(float(x), 8) for x in fc.median[s, 0]],
            "quantiles": levels,
        })
    return {
        "horizon": horizon,
        "series": per_series,
        "wall_s": round(elapsed, 3),
        "peak_rss_gib": round(peak_rss_gib(), 2),
    }


class ClientError(ValueError):
    """A request the client got wrong: answered 400, never 500."""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/health", "/healthz"):
            STATE["attempts"] += 1
            self._send(200, {"status": "ok", "requests": STATE["requests"],
                             "attempts": STATE["attempts"], "failed": STATE["failed"]})
        elif self.path == "/v1/models":
            self._send(200, {"object": "list", "data": [{"id": STATE["model_id"]}]})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/forecast":
            self._send(404, {"error": "not found"})
            return
        STATE["attempts"] += 1
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self._send(400, {"error": "bad Content-Length"})
            return
        try:
            req = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError) as exc:
            self._send(400, {"error": "body is not valid JSON: %s" % exc})
            return
        if not isinstance(req, dict):
            self._send(400, {"error": "body must be a JSON object"})
            return
        try:
            result = run_forecast(req)
            STATE["requests"] += 1
            self._send(200, result)
        except ClientError as exc:
            STATE["failed"] += 1
            self._send(400, {"error": str(exc)})
        except Exception:  # noqa: BLE001 - server fault: 500, traceback to the log
            STATE["failed"] += 1
            log("forecast failed:\n%s" % traceback.format_exc())
            self._send(500, {"error": "internal error; see the serve log"})


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--model", required=True, help="local snapshot dir (never a Hub fetch)")
    p.add_argument("--revision", default="")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8895)
    args = p.parse_args()

    STATE["model_id"] = os.path.basename(args.model.rstrip("/")) or args.model
    fc, load_s = load_forecaster(args.model, args.revision)
    STATE["forecaster"] = fc
    log("ready on %s:%d (load %.1f s)" % (args.host, args.port, load_s))
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
