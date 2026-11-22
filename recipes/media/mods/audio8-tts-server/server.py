#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Edge0/Audio8-TTS-Realistic-Air speech server (custom Transformers code).

No serving runtime ships this checkpoint: `ArkttsModel` lives in the repo and
loads through `auto_map` + `trust_remote_code`, and the card's SGLang Omni
adapter is not in the fleet pins. So this script *is* the server, in the
kromoss/phonon shape. Launched by the recipe as

    <RUNTIME_DIR>/venv/bin/python /workspace/mods/audio8-tts-server/server.py

with the venv staged by this mod's run.sh (transformers 4.57.x on the image's
own torch).

Card loading shape:
    processor = AutoProcessor.from_pretrained(repo, trust_remote_code=True)
    model = AutoModel.from_pretrained(repo, trust_remote_code=True,
                                      dtype=torch.bfloat16).eval().to("cuda")
    out = model.generate(**inputs, max_new_tokens=1024, temperature=0.8,
                         top_p=0.95, top_k=50, do_sample=True,
                         return_dict_in_generate=True)
    waveforms, lengths = model.decode_audio(out.codes)   # 44.1 kHz mono

Surface:

    GET  /health           -> {"status": "ok", ...}   liveness for sparkrun
    GET  /v1/models        -> the loaded repo id      convenience
    POST /v1/audio/speech  -> audio/wav

POST /v1/audio/speech body (JSON):
    {"input": str, "seed": 42, "max_new_tokens": 1024, "temperature": 0.8,
     "top_p": 0.95, "top_k": 50,
     "reference_audio": "/abs/path.wav", "reference_text": "exact transcript"}

The reference pair is optional (zero-shot cloning); without it the model
generates a fresh voice. A reference clip must be **44.1 kHz mono** — the
repo's processor only reaches for torchaudio to resample a different rate,
and this venv deliberately does not install torchaudio (it would pull its own
torch build over the image's cu130 stack).
"""
from __future__ import annotations

import argparse
import importlib.metadata as md
import io
import json
import os
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATE: dict = {
    "model": None,
    "processor": None,
    "model_id": None,
    "revision": "unknown",
    "device": "cuda",
    "requests": 0,
    "attempts": 0,
    "failed": 0,
    "lock": threading.Lock(),
}


def log(msg: str) -> None:
    print("[audio8] %s" % msg, flush=True)


def engine_versions() -> str:
    try:
        return "transformers %s torch %s" % (md.version("transformers"), md.version("torch"))
    except Exception:
        return "unknown"


def resolve_snapshot_dir(model: str) -> str:
    """Map a repo id to its local HF snapshot dir; pass a path through untouched.

    The recipe's `{model}` renders to the prepared snapshot path on a real
    sparkrun launch; a repo id is resolved through the in-container cache
    (refs/main, else the newest snapshot carrying `config.json`), never the Hub.
    """
    if os.path.isdir(model):
        return model
    cache_root = os.environ.get("HF_HUB_CACHE", "/cache/huggingface/hub")
    repo_dir = os.path.join(cache_root, "models--" + model.replace("/", "--"))
    if not os.path.isdir(repo_dir):
        return model
    refs_main = os.path.join(repo_dir, "refs", "main")
    if os.path.isfile(refs_main):
        with open(refs_main) as fh:
            pin = fh.read().strip()
        snapshot = os.path.join(repo_dir, "snapshots", pin)
        if os.path.isfile(os.path.join(snapshot, "config.json")):
            return snapshot
    snap_root = os.path.join(repo_dir, "snapshots")
    candidates = []
    for name in sorted(os.listdir(snap_root)) if os.path.isdir(snap_root) else []:
        if os.path.isfile(os.path.join(snap_root, name, "config.json")):
            candidates.append(os.path.join(snap_root, name))
    return candidates[-1] if candidates else model


def load_model(model: str, device: str):
    import torch
    from transformers import AutoModel, AutoProcessor

    snapshot = resolve_snapshot_dir(model)
    log("loading from %s" % snapshot)
    t0 = time.time()
    processor = AutoProcessor.from_pretrained(snapshot, trust_remote_code=True)
    net = AutoModel.from_pretrained(
        snapshot, trust_remote_code=True, dtype=torch.bfloat16
    ).eval().to(device)
    # The codec is a sidecar `codec.pth`; the model resolves it from its own
    # `_name_or_path`, so a local snapshot directory is what keeps this offline.
    if not Path(net._codec_path()).is_file():
        raise RuntimeError("codec sidecar missing: %s" % net._codec_path())
    log("loaded in %.1f s on %s; codec %s" % (time.time() - t0, device, net._codec_path()))
    return net, processor


class ClientError(ValueError):
    """A request the client got wrong: answered 400, never 500."""


def _int(req: dict, key: str, default: int) -> int:
    try:
        return int(req.get(key, default))
    except (TypeError, ValueError):
        raise ClientError("%s must be an integer" % key)


def _float(req: dict, key: str, default: float) -> float:
    try:
        return float(req.get(key, default))
    except (TypeError, ValueError):
        raise ClientError("%s must be a number" % key)


def render(req: dict) -> bytes:
    import soundfile as sf
    import torch

    text = req.get("input") or req.get("text") or ""
    if not isinstance(text, str) or not text.strip():
        raise ClientError("input is required and must be a non-empty string")
    seed = _int(req, "seed", 42)
    max_new_tokens = _int(req, "max_new_tokens", 1024)
    temperature = _float(req, "temperature", 0.8)
    top_p = _float(req, "top_p", 0.95)
    top_k = _int(req, "top_k", 50)
    reference_audio = req.get("reference_audio")
    reference_text = req.get("reference_text")
    if reference_audio is not None and not isinstance(reference_audio, str):
        raise ClientError("reference_audio must be a path string")
    if reference_text is not None and not isinstance(reference_text, str):
        raise ClientError("reference_text must be a string")
    if reference_audio is None and reference_text is not None:
        raise ClientError("reference_text is meaningless without reference_audio")

    processor = STATE["processor"]
    model = STATE["model"]
    kwargs: dict = {"text": [text]}
    if reference_audio is not None:
        if not os.path.isfile(reference_audio):
            raise ClientError("reference_audio not found: %s" % reference_audio)
        kwargs["reference_audio"] = [reference_audio]
        kwargs["reference_text"] = [reference_text or ""]
        kwargs["sampling_rate"] = [44100]
    inputs = processor(**kwargs)
    inputs = {name: value.to(STATE["device"]) for name, value in inputs.items()}

    torch.manual_seed(seed)
    t0 = time.time()
    with STATE["lock"]:
        out = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            do_sample=True,
            return_dict_in_generate=True,
        )
        waveforms, lengths = model.decode_audio(out.codes)
    elapsed = time.time() - t0
    audio = waveforms[0, : int(lengths[0])].float().cpu().numpy()
    buffer = io.BytesIO()
    sf.write(buffer, audio, int(model.config.codec_sample_rate), format="WAV", subtype="PCM_16")
    log("rendered %d chars -> %.2f s audio in %.2f s (seed %d)"
        % (len(text), len(audio) / float(model.config.codec_sample_rate), elapsed, seed))
    return buffer.getvalue()


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
        if self.path in ("/health", "/healthz"):
            STATE["attempts"] += 1
            self._json(200, {
                "status": "ok",
                "model": STATE["model_id"],
                "revision": STATE["revision"],
                "engine": engine_versions(),
                "device": STATE["device"],
                "requests": STATE["requests"],
                "attempts": STATE["attempts"],
                "failed": STATE["failed"],
            })
        elif self.path == "/v1/models":
            self._json(200, {"object": "list", "data": [{"id": STATE["model_id"]}]})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/v1/audio/speech":
            self._json(404, {"error": "not found"})
            return
        STATE["attempts"] += 1
        try:
            length = int(self.headers.get("Content-Length", "0"))
            req = json.loads(self.rfile.read(length) or b"{}")
        except (TypeError, ValueError, UnicodeDecodeError) as exc:
            STATE["failed"] += 1
            self._json(400, {"error": "bad JSON body: %s" % exc})
            return
        if not isinstance(req, dict):
            STATE["failed"] += 1
            self._json(400, {"error": "body must be a JSON object"})
            return
        try:
            wav = render(req)
        except ClientError as exc:
            STATE["failed"] += 1
            self._json(400, {"error": str(exc)})
            return
        except Exception:  # noqa: BLE001 - server fault: 500, traceback to the log
            STATE["failed"] += 1
            log("render failed:\n%s" % traceback.format_exc())
            self._json(500, {"error": "internal error; see the serve log"})
            return
        STATE["requests"] += 1
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(wav)))
        self.end_headers()
        self.wfile.write(wav)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", required=True)
    ap.add_argument("--served-model-name", required=True)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8900)
    ap.add_argument("--revision", default=None)
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    STATE["model_id"] = args.served_model_name
    if args.revision is not None:
        STATE["revision"] = args.revision
    STATE["device"] = args.device
    model, processor = load_model(args.model, args.device)
    STATE["model"] = model
    STATE["processor"] = processor
    log("ready: %s on %s:%d (%s)" % (args.served_model_name, args.host, args.port, engine_versions()))
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
