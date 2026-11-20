#!/usr/bin/env python3
"""inworld/voice-isolator voice-isolation server (vendor SDK, CPU).

The checkpoint is a plain torch state dict (embedded config, `library_name:
inworld-voice-isolation`), so no serving engine loads it: this is the lane's
script arm, `runtime: vllm` being only the launcher/distribution contract.

Contract:
  GET  /health            -> {"status":"ok","model","revision","device","mode",
                              "requests","failed","last_audio_s","last_rtf"}
  GET  /v1/models         -> {"object":"list","data":[{"id": <served id>}]}
  POST /v1/audio/isolate  -> body is a WAV (any rate, mono or multi-channel);
                             answers 48 kHz mono float32 WAV of the isolated
                             voice. `?background=1` answers what was removed
                             (input - voice) instead. X-Audio-Seconds and
                             X-RTF carry the last chunk's cost.

Startup runs the tracked fixture (fixture-noisy.wav, beside this file) once
before the port binds: a serve that cannot isolate is dead, not ready.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import soundfile as sf
import torch

from inworld import voice_isolation

STATE: dict = {
    "model": None,
    "model_id": None,
    "revision": None,
    "device": "cpu",
    "mode": "offline",
    "sample_rate": 48000,
    "isolator": None,
    "requests": 0,
    "failed": 0,
    "last_audio_s": None,
    "last_rtf": None,
    "lock": threading.Lock(),
}


def log(msg: str) -> None:
    print("[voice-isolator] %s" % msg, flush=True)


def resolve_checkpoint(model: str, mode: str) -> str:
    """A prepared snapshot dir holds both checkpoints; the mode picks the file."""
    if not os.path.isdir(model):
        return model
    name = ("denoiser_realtime.safetensors" if mode == "streaming"
            else "denoiser.safetensors")
    path = os.path.join(model, name)
    if not os.path.exists(path):
        raise SystemExit("%s has no %s (mode=%s)" % (model, name, mode))
    return path


def isolate_bytes(body: bytes, background: bool) -> tuple[bytes, float, float]:
    """Isolates the WAV in ``body``; returns (wav bytes, audio seconds, rtf)."""
    x, sr = sf.read(io.BytesIO(body), dtype="float32", always_2d=True)
    wav = torch.from_numpy(x.mean(axis=1))
    out_sr = STATE["sample_rate"]
    t0 = time.time()
    with STATE["lock"]:
        voice = STATE["isolator"].isolate(wav, sr, output_sample_rate=out_sr)
    wall = time.time() - t0
    voice = torch.as_tensor(voice, dtype=torch.float32).reshape(-1).cpu()
    ref = voice_isolation.resample(wav, sr, out_sr) if sr != out_sr else wav
    n = min(ref.shape[-1], voice.shape[-1])
    out = ref[:n] - voice[:n] if background else voice
    buf = io.BytesIO()
    sf.write(buf, out.numpy(), out_sr, format="WAV", subtype="FLOAT")
    return buf.getvalue(), n / out_sr, (wall / (n / out_sr) if n else 0.0)


class ClientError(ValueError):
    """A request the client got wrong: answered 400, never 500."""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        pass

    def _send(self, code: int, body: bytes, ctype: str,
              headers: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload).encode(), "application/json")

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/health", "/healthz"):
            self._json(200, {
                "status": "ok",
                "model": STATE["model_id"],
                "revision": STATE["revision"],
                "device": STATE["device"],
                "mode": STATE["mode"],
                "sample_rate": STATE["sample_rate"],
                "requests": STATE["requests"],
                "failed": STATE["failed"],
                "last_audio_s": STATE["last_audio_s"],
                "last_rtf": STATE["last_rtf"],
            })
        elif path == "/v1/models":
            self._json(200, {"object": "list",
                             "data": [{"id": STATE["model_id"]}]})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        path, _, query = self.path.partition("?")
        if path != "/v1/audio/isolate":
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self._json(400, {"error": "bad Content-Length"})
            return
        body = self.rfile.read(length)
        if len(body) < 12 or body[:4] not in (b"RIFF", b"RIFX", b"RF64"):
            self._json(400, {"error": "body must be a WAV (RIFF/WAVE)"})
            return
        background = "background=1" in query or "background=true" in query
        try:
            body, seconds, rtf = isolate_bytes(body, background)
        except (ClientError, sf.LibsndfileError, RuntimeError) as exc:
            STATE["failed"] += 1
            self._json(400, {"error": str(exc)})
            return
        except Exception:  # noqa: BLE001 - server fault: 500, traceback to the log
            STATE["failed"] += 1
            log("isolate failed:\n%s" % traceback.format_exc())
            self._json(500, {"error": "internal error; see the serve log"})
            return
        STATE["requests"] += 1
        STATE["last_audio_s"] = round(seconds, 3)
        STATE["last_rtf"] = round(rtf, 4)
        self._send(200, body, "audio/wav", {
            "X-Audio-Seconds": "%.3f" % seconds,
            "X-RTF": "%.4f" % rtf,
            "X-Background": "1" if background else "0",
        })


def run_fixture(isolator, sample_rate: int) -> None:
    """One isolate over the tracked fixture, before the port binds."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "fixture-noisy.wav")
    wav, sr = voice_isolation.load_audio(path)
    t0 = time.time()
    voice = isolator.isolate(wav, sr, output_sample_rate=sample_rate)
    wall = time.time() - t0
    voice = torch.as_tensor(voice, dtype=torch.float32).reshape(-1)
    ref = voice_isolation.resample(wav, sr, sample_rate)
    if voice.shape[-1] != ref.shape[-1]:
        raise SystemExit("fixture: %d samples in, %d out"
                         % (ref.shape[-1], voice.shape[-1]))
    if not torch.isfinite(voice).all():
        raise SystemExit("fixture: non-finite output")
    ref_rms = float(ref.pow(2).mean().sqrt())
    voice_rms = float(voice.pow(2).mean().sqrt())
    log("fixture OK: %.3f s audio in %.3f s (RTF %.4f), rms %.3f -> %.3f"
        % (ref.shape[-1] / sample_rate, wall, wall / (ref.shape[-1] / sample_rate),
           ref_rms, voice_rms))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--model", required=True,
                   help="prepared snapshot dir or a single .safetensors file")
    p.add_argument("--served-model-name", default="inworld/voice-isolator")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--device", default="cuda",
                   help="cuda (default) or cpu; the CPU route is ~25x realtime")
    p.add_argument("--mode", default="offline", choices=("offline", "streaming"))
    p.add_argument("--lookahead-frames", type=int, default=2,
                   help="streaming look-ahead: 0, 2 or 4 frames (20/40 ms)")
    p.add_argument("--revision", default=None)
    args = p.parse_args()

    if args.device.startswith("cuda") and not torch.cuda.is_available():
        raise SystemExit("--device %s but torch.cuda.is_available() is false "
                         "(torch %s)" % (args.device, torch.__version__))
    checkpoint = resolve_checkpoint(args.model, args.mode)
    STATE["model"] = checkpoint
    STATE["model_id"] = args.served_model_name
    STATE["revision"] = args.revision
    STATE["device"] = args.device
    STATE["mode"] = args.mode
    t0 = time.time()
    STATE["isolator"] = voice_isolation.VoiceIsolator(
        checkpoint, device=args.device, mode=args.mode,
        lookahead_frames=args.lookahead_frames)
    log("loaded %s (%s, %s) in %.2f s"
        % (checkpoint, args.mode, args.device, time.time() - t0))
    run_fixture(STATE["isolator"], STATE["sample_rate"])
    log("ready: %s on %s:%d" % (args.served_model_name, args.host, args.port))
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    sys.exit(main())
