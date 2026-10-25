#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""CPU TTS server for gradium/phonon-31m-en (the kokoro arm's shape).

stdlib http.server only: the engine is the `ptts` CLI (PyPI ptts, the vendor
Rust runtime) run as a subprocess per request, writing a 24 kHz mono 16-bit
RIFF WAV that is streamed back. Endpoints:

    GET  /health            -> {"model": ..., "revision": ..., "engine": "ptts ..."}
    POST /v1/audio/speech   -> {"input": text, "seed": int?, "lang": str?} -> audio/wav

Contract notes the operators need:
  - `ptts` is NOT byte-deterministic per invocation (measured 2026-10-24/25:
    same seed and text produce identical length, different PCM), so clients
    must not cache by content hash; A/Bs score at the transcript/metric level.
  - `-m` takes the model DIRECTORY (a bare .gguf path fails its checkpoint
    check); the directory must hold real files, not a symlinked snapshot
    (the mod resolves and copies the snapshot precisely for this).
  - One render at a time (a lock) — phonon is a ~31M CPU model, concurrency
    beyond one stream buys nothing on the A725 cores.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CFG = {
    "model_dir": Path(__file__).parent.parent / "model",
    "revision": "unknown",
    "seed": 1234,
    "lang": "en",
}
LOCK = threading.Lock()


def engine_version() -> str:
    try:
        out = subprocess.run(
            ["ptts", "--version"], capture_output=True, text=True, timeout=30, check=False
        ).stdout
        return out.strip() or "unknown"
    except Exception:
        return "unknown"


def render(text: str, seed: int, lang: str) -> bytes:
    if not text.strip():
        raise ValueError("input is empty")
    if len(text) > 4000:
        raise ValueError("input exceeds 4000 chars")
    with tempfile.TemporaryDirectory(dir=str(Path(CFG["model_dir"]).parent)) as td:
        out = Path(td) / "out.wav"
        cmd = [
            CFG.get("ptts", "ptts"), "-l", lang, "-m", str(CFG["model_dir"]), "-s", str(seed),
            "-o", str(out), text,
        ]
        with LOCK:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0 or not out.exists():
            raise RuntimeError("ptts failed rc=%d: %s" % (proc.returncode, proc.stderr[-400:]))
        return out.read_bytes()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        pass

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {
                "model": "gradium/phonon-31m-en",
                "revision": CFG["revision"],
                "engine": "ptts %s" % engine_version(),
                "model_dir": str(CFG["model_dir"]),
            })
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/v1/audio/speech":
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            req = json.loads(self.rfile.read(length) or b"{}")
            text = req.get("input") or req.get("text") or ""
            seed = int(req.get("seed", CFG["seed"]))
            lang = str(req.get("lang", CFG["lang"]))
            wav = render(text, seed, lang)
        except ValueError as error:
            self._json(400, {"error": str(error)})
            return
        except subprocess.TimeoutExpired:
            self._json(504, {"error": "render timed out"})
            return
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--model-dir", default=str(CFG["model_dir"]))
    ap.add_argument("--revision", default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--lang", default=None)
    ap.add_argument("--ptts", default="ptts")
    # Accepted and ignored: the runtime appends it to satisfy its model-binding check.
    ap.add_argument("--served-model-name", default=None)
    args = ap.parse_args()
    CFG["model_dir"] = Path(args.model_dir)
    CFG["ptts"] = args.ptts
    if args.revision is not None:
        CFG["revision"] = args.revision
    if args.seed is not None:
        CFG["seed"] = args.seed
    if args.lang is not None:
        CFG["lang"] = args.lang
    if not (Path(args.model_dir) / "model.q8.gguf").exists():
        raise SystemExit("phonon model.q8.gguf missing under %s" % args.model_dir)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
