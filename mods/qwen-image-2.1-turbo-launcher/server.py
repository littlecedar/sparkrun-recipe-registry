#!/usr/bin/env python3
"""Qwen-Image-2.1-Turbo image-generation server (diffusers engine).

`QwenImage21Pipeline` has no serving runtime (it is neither sglang nor vLLM),
so this script *is* the server for the explore lane's media-gen arm. It is
launched by the recipe as

    <RUNTIME_DIR>/venv/bin/python /workspace/mods/qwen-image-2.1-turbo-launcher/server.py

with the venv staged by this mod's run.sh (diffusers >= 0.41 + transformers
>= 5.17 on the image's own torch).

Surface (this arm has no chat completions):

    GET  /health          -> {"status": "ok", ...}   liveness for sparkrun
    GET  /v1/models       -> the loaded repo id      convenience
    POST /generate        -> run the pipeline, save a PNG, return metrics

POST /generate body (JSON):
    {"prompt": str, "width": 1024, "height": 1024, "seed": 0,
     "num_inference_steps": null, "image_path": null, "use_kv_cache": true}

`num_inference_steps` is null by default: the checkpoint ships its **8-step
schedule** in model_index.json (`sample_sigmas`) and the card is explicit that
setting `num_inference_steps` alone does not override it. Passing a non-null
value would need an explicit `sigmas` list to mean anything, so this server
leaves the saved schedule alone.

Caching: `use_kv_cache=True` is the card's default and reuses the text and
reference-image context prefix across denoising steps.

Traps re-checked here (see recipes/explore/QWEN-IMAGE.md):
  * VAE tiling stays OFF (tiled decode produces a pink seam column).
  * `cpu_offload` stays OFF (sequential offload costs ~4x on a reference image).
  * the denoise loop is serialized behind one lock: this is a single-tenant arm.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATE: dict = {
    "pipe": None,
    "model_id": None,
    "model_path": None,
    "dtype": None,
    "device": "cuda",
    "load_s": None,
    "sample_dir": None,
    "requests": 0,
    "lock": threading.Lock(),
}


def mem_available_gib() -> float | None:
    """Node-level MemAvailable (unified memory on GB10)."""
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / (1024 * 1024)
    except OSError:
        pass
    return None


def log(msg: str) -> None:
    print("[qwen-image] %s" % msg, flush=True)


def load_pipeline(model: str, device: str):
    import torch
    from diffusers import QwenImage21Pipeline

    before = mem_available_gib()
    torch.cuda.reset_peak_memory_stats()
    log("loading pipeline from %s (MemAvailable %.1f GiB)" % (model, before or float("nan")))
    t0 = time.time()
    try:
        pipe = QwenImage21Pipeline.from_pretrained(model, dtype=torch.bfloat16)
    except TypeError:
        # diffusers < the dtype rename still spells it torch_dtype.
        pipe = QwenImage21Pipeline.from_pretrained(model, torch_dtype=torch.bfloat16)
    pipe.to(device)
    load_s = time.time() - t0
    alloc = torch.cuda.max_memory_allocated() / (2 ** 30)
    reserved = torch.cuda.max_memory_reserved() / (2 ** 30)
    after = mem_available_gib()
    log(
        "loaded in %.1f s; peak alloc %.2f GiB, reserved %.2f GiB; "
        "MemAvailable %.1f -> %.1f GiB"
        % (load_s, alloc, reserved, before or float("nan"), after or float("nan"))
    )
    return pipe, load_s


def run_generate(req: dict) -> dict:
    import torch

    pipe = STATE["pipe"]
    sample_dir = STATE["sample_dir"]
    prompt = req.get("prompt")
    if not prompt:
        raise ValueError("prompt is required")
    width = int(req.get("width", 1024))
    height = int(req.get("height", 1024))
    seed = int(req.get("seed", 0))
    use_kv_cache = bool(req.get("use_kv_cache", True))

    call: dict = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "use_kv_cache": use_kv_cache,
        "generator": torch.Generator("cpu").manual_seed(seed),
    }
    if req.get("num_inference_steps") is not None:
        call["num_inference_steps"] = int(req["num_inference_steps"])
    image_path = req.get("image_path")
    if image_path:
        from diffusers.utils import load_image

        call["image"] = load_image(image_path).convert("RGBA")

    step_times: list = []
    step_t0 = [None]

    def on_step_end(_pipe, _step, _timestep, kwargs):
        now = time.time()
        step_times.append(now)
        return kwargs

    call["callback_on_step_end"] = on_step_end

    torch.cuda.reset_peak_memory_stats()
    step_t0[0] = time.time()
    with STATE["lock"]:
        out = pipe(**call)
    elapsed = time.time() - step_t0[0]
    image = out.images[0]

    peak_alloc = torch.cuda.max_memory_allocated() / (2 ** 30)
    peak_reserved = torch.cuda.max_memory_reserved() / (2 ** 30)

    os.makedirs(sample_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    name = "t2i_%dx%d_seed%d_%s.png" % (width, height, seed, stamp)
    path = os.path.join(sample_dir, name)
    image.save(path)

    return {
        "elapsed_s": round(elapsed, 3),
        "steps": len(step_times),
        "first_step_s": round(step_times[0] - step_t0[0], 3) if step_times else None,
        "width": width,
        "height": height,
        "seed": seed,
        "use_kv_cache": use_kv_cache,
        "peak_alloc_gib": round(peak_alloc, 3),
        "peak_reserved_gib": round(peak_reserved, 3),
        "mem_available_gib_after": round(mem_available_gib() or -1, 3),
        "image_path": path,
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # route httpd noise through our logger
        log("http %s" % (format % args))

    def do_GET(self) -> None:
        if self.path.split("?")[0] in ("/health", "/healthz"):
            self._send(200, {
                "status": "ok",
                "model": STATE["model_id"],
                "loaded": STATE["pipe"] is not None,
                "load_s": STATE["load_s"],
                "requests": STATE["requests"],
                "mem_available_gib": round(mem_available_gib() or -1, 2),
            })
        elif self.path.split("?")[0] == "/v1/models":
            self._send(200, {"object": "list", "data": [
                {"id": STATE["model_id"], "object": "model", "owned_by": "qwen"}]})
        else:
            self._send(404, {"error": "unknown path %s" % self.path})

    def do_POST(self) -> None:
        if self.path.split("?")[0] != "/generate":
            self._send(404, {"error": "unknown path %s" % self.path})
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            req = json.loads(raw or b"{}")
            result = run_generate(req)
        except Exception as exc:  # surface the failure, keep the server up
            log("generate failed: %r" % (exc,))
            self._send(500, {"error": "%s: %s" % (type(exc).__name__, exc)})
            return
        STATE["requests"] += 1
        log("generate %s" % json.dumps(result))
        self._send(200, result)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", required=True, help="checkpoint path or repo id")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--device", default="cuda")
    # sparkrun's vllm runtime appends `--served-model-name <repo id>` to every
    # rendered command whose config chain declares the key, so the server MUST
    # accept it (this arm is a diffusers engine; there is no vLLM).
    parser.add_argument("--served-model-name", default=None,
                        help="id reported by /v1/models (sparkrun appends this)")
    # The recipe passes its `model_revision:` pin through as --revision. The
    # engine loads a snapshot *path*, so the pin is not needed to resolve the
    # checkpoint — it is asserted instead, which catches a stale node mirror.
    parser.add_argument("--revision", default=None)
    parser.add_argument(
        "--sample-dir",
        default=os.environ.get("QI_SAMPLE_DIR", "/cache/runtime/qwen-image/samples"),
    )
    args = parser.parse_args(argv)

    STATE["model_path"] = args.model
    STATE["model_id"] = args.served_model_name or os.path.basename(args.model.rstrip("/"))

    if args.revision and os.path.isdir(args.model) and args.revision not in args.model:
        raise SystemExit(
            "revision mismatch: --revision %s is not in the model path %s"
            % (args.revision, args.model)
        )
    STATE["sample_dir"] = args.sample_dir
    STATE["device"] = args.device

    pipe, load_s = load_pipeline(args.model, args.device)
    STATE["pipe"] = pipe
    STATE["load_s"] = load_s

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    log("serving on %s:%d, samples -> %s" % (args.host, args.port, args.sample_dir))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
