#!/usr/bin/env python3
"""lodestones/Kromoss image-generation server (diffusers custom pipeline).

`MOSSImagePipeline` (shipped as the repo's own `pipeline_moss_image.py`, loaded
via `custom_pipeline="pipeline_moss_image"` + `trust_remote_code=True`) has no
serving runtime, so this script *is* the server for the media lane's Kromoss
probe arm, in the shape of the Qwen-Image-2.1-Turbo launcher
(`recipes/media/mods/qwen-image-2.1-turbo-launcher/server.py`). Launched by the
recipe as

    <RUNTIME_DIR>/venv/bin/python /workspace/mods/kromoss-launcher/server.py

with the venv staged by this mod's run.sh (diffusers >= 0.41 + transformers
>= 5.17 on the image's own torch — the card's floor is diffusers>=0.38 /
transformers>=5.3, so the staged floor satisfies it).

Card loading shape (Kromoss README Quick start):
    DiffusionPipeline.from_pretrained(repo, custom_pipeline="pipeline_moss_image",
                                      trust_remote_code=True,
                                      torch_dtype={"default": bf16, "vae": fp32})
    pipe.scheduler = type(pipe.scheduler).from_config(pipe.scheduler.config)
    pipe.to("cuda")
and the generation call carries `uncond_skip_layers=[22]` at 50 steps / CFG 3
(CFG 1 with a turbo LoRA runs without the negative branch).

The 8-steps-dmd2 LoRA is applied UNMERGED (the card is explicit: never merge it
into the bf16 weights) via the card's own forward-hook recipe on the fused
`proj.qkv` slices, selected with `--lora <path>` and scaled with `--lora-strength`.

Surface (this arm has no chat completions):

    GET  /health          -> {"status": "ok", ...}   liveness for sparkrun
    GET  /v1/models       -> the loaded repo id      convenience
    POST /generate        -> run the pipeline, save a PNG, return metrics

Errors follow the Qwen launcher convention: a bad request is **400** with
`{"error": …}`; a server fault is **500** with its traceback in the log only.

POST /generate body (JSON):
    {"prompt": str, "width": 1024, "height": 1024, "seed": 42,
     "num_inference_steps": 50, "guidance_scale": 3.0,
     "uncond_skip_layers": [22]}

Step-knob honesty: this checkpoint's scheduler is the repo's own euler/simple
flow-matching schedule driven by `num_inference_steps` (no shipped `sample_sigmas`
override), so the steps knob is expected to be LIVE — but the lane's recorded
trap (`num_inference_steps` silently inert when a scheduler's sigmas win) still
applies, so the arm's step-knob cell hashes outputs across step counts rather
than trusting the wall time. `steps_used` in the response records what ran.
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATE: dict = {
    "pipe": None,
    "model_id": None,
    "sample_dir": None,
    "requests": 0,
    "attempts": 0,
    "failed": 0,
    "lora": None,
    "lock": threading.Lock(),
}


def mem_available_gib() -> float | None:
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / (1024 * 1024)
    except OSError:
        pass
    return None


def log(msg: str) -> None:
    print("[kromoss] %s" % msg, flush=True)


def apply_lora(transformer, path: str, strength: float = 1.0) -> int:
    """The card's unmerged-LoRA recipe: kohya keys onto the fused qkv slices.

    Returns the number of hooked modules so the log can prove the LoRA bound.
    """
    import torch
    from safetensors.torch import load_file

    state = load_file(path, device="cuda")
    modules = dict(transformer.named_modules())
    hooked = 0
    for key in [k for k in state if k.endswith(".lora_down.weight")]:
        name = key[len("diffusion_model."):-len(".lora_down.weight")]
        down = state[key].float()
        up = state[key.replace("lora_down", "lora_up")].float()
        scale = strength * state[f"diffusion_model.{name}.alpha"].item() / down.shape[0]

        def hook(module, args, out, down=down, up=up, scale=scale):
            return out + (scale * (args[0].float() @ down.T) @ up.T).to(out.dtype)

        modules[name].register_forward_hook(hook)
        hooked += 1
    assert hooked, "no lora_down keys bound from %s" % path
    _ = torch
    return hooked

def resolve_snapshot_dir(model: str) -> str:
    """Map a repo id to its local HF snapshot dir; pass a path through untouched.

    The recipe's `{model}` renders to the prepared snapshot path on a real
    sparkrun launch, so this is mostly a guard for manual runs: a repo id is
    resolved through the in-container cache (refs/main, else the newest snapshot
    with a model_index.json), never the Hub.
    """
    if os.path.isdir(model):
        return model
    cache_root = os.environ.get("HF_HUB_CACHE", "/cache/huggingface/hub")
    repo_dir = os.path.join(cache_root, "models--" + model.replace("/", "--"))
    if not os.path.isdir(repo_dir):
        return model  # let diffusers raise its own error for an unknown id
    refs_main = os.path.join(repo_dir, "refs", "main")
    if os.path.isfile(refs_main):
        with open(refs_main) as fh:
            pin = fh.read().strip()
        snapshot = os.path.join(repo_dir, "snapshots", pin)
        if os.path.isfile(os.path.join(snapshot, "model_index.json")):
            return snapshot
    candidates = []
    snap_root = os.path.join(repo_dir, "snapshots")
    for name in sorted(os.listdir(snap_root)) if os.path.isdir(snap_root) else []:
        if os.path.isfile(os.path.join(snap_root, name, "model_index.json")):
            candidates.append(os.path.join(snap_root, name))
    if candidates:
        return candidates[-1]
    return model


def load_pipeline(model: str, device: str, lora: str | None, lora_strength: float):
    import torch
    from diffusers import DiffusionPipeline

    before = mem_available_gib()
    torch.cuda.reset_peak_memory_stats()
    log("loading pipeline from %s (MemAvailable %.1f GiB)" % (model, before or float("nan")))
    t0 = time.time()
    dtype_kw = {"torch_dtype": {"default": torch.bfloat16, "vae": torch.float32}}
    # diffusers' custom_pipeline loader hits `model_info()` (a Hub API call)
    # when given a repo id, even with the repo fully cached — dead under
    # HF_HUB_OFFLINE. A local snapshot path takes the file-copy branch instead.
    snapshot = resolve_snapshot_dir(model)
    log("resolving %s -> snapshot %s" % (model, snapshot))
    try:
        pipe = DiffusionPipeline.from_pretrained(
            snapshot, custom_pipeline="pipeline_moss_image", trust_remote_code=True, **dtype_kw)
    except TypeError:
        # diffusers < the torch_dtype rename spells the per-module map differently.
        pipe = DiffusionPipeline.from_pretrained(
            snapshot, custom_pipeline="pipeline_moss_image", trust_remote_code=True,
            torch_dtype=torch.bfloat16)
    # The card rebuilds the scheduler from its own config (fresh Euler state).
    pipe.scheduler = type(pipe.scheduler).from_config(pipe.scheduler.config)
    pipe.to(device)
    hooked = 0
    if lora:
        hooked = apply_lora(pipe.transformer, lora, lora_strength)
        log("lora applied unmerged: %s strength %s (%d modules)" % (lora, lora_strength, hooked))
    load_s = time.time() - t0
    alloc = torch.cuda.max_memory_allocated() / (2 ** 30)
    reserved = torch.cuda.max_memory_reserved() / (2 ** 30)
    log("loaded in %.1f s; peak alloc %.2f GiB, reserved %.2f GiB; MemAvailable %.1f -> %.1f GiB"
        % (load_s, alloc, reserved, before or float("nan"), mem_available_gib() or float("nan")))
    return pipe, load_s


def run_generate(req: dict) -> dict:
    import torch

    pipe = STATE["pipe"]
    prompt = req.get("prompt")
    if not isinstance(prompt, str) or not prompt:
        raise ClientError("prompt is required and must be a non-empty string")
    try:
        width = int(req.get("width", 1024))
        height = int(req.get("height", 1024))
        seed = int(req.get("seed", 42))
        steps = int(req.get("num_inference_steps", 50))
    except (TypeError, ValueError):
        raise ClientError("width, height, seed and num_inference_steps must be integers")
    try:
        guidance = float(req.get("guidance_scale", 3.0))
    except (TypeError, ValueError):
        raise ClientError("guidance_scale must be a float")
    skip_layers = req.get("uncond_skip_layers", [22])
    if not isinstance(skip_layers, list) or not all(isinstance(x, int) for x in skip_layers):
        raise ClientError("uncond_skip_layers must be a list of ints")

    call: dict = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_inference_steps": steps,
        "guidance_scale": guidance,
        "generator": torch.Generator("cpu").manual_seed(seed),
    }
    if guidance != 1.0:
        # The card's control cell: the negative branch runs, with block 22 skipped.
        call["uncond_skip_layers"] = skip_layers

    torch.cuda.reset_peak_memory_stats()
    t0 = time.time()
    with STATE["lock"]:
        out = pipe(**call)
    elapsed = time.time() - t0
    image = out.images[0]
    if image is None:
        raise RuntimeError("pipeline returned no image")
    sample_dir = STATE["sample_dir"]
    os.makedirs(sample_dir, exist_ok=True)
    name = "kromoss-%dx%d-s%d-steps%d-cfg%s-%d.png" % (
        width, height, seed, steps, guidance, int(time.time() * 1000))
    path = os.path.join(sample_dir, name)
    image.save(path)
    alloc = torch.cuda.max_memory_allocated() / (2 ** 30)
    return {
        "png": path,
        "wall_s": round(elapsed, 3),
        "steps_used": steps,
        "guidance_scale": guidance,
        "uncond_skip_layers": call.get("uncond_skip_layers"),
        "seed": seed,
        "width": width,
        "height": height,
        "peak_alloc_gib": round(alloc, 2),
        "mem_available_gib": round(mem_available_gib() or float("nan"), 1),
    }


class ClientError(ValueError):
    """A request the client got wrong: answered 400, never 500."""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        pass

    def _send(self, code: int, payload: dict):
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
                             "attempts": STATE["attempts"], "failed": STATE["failed"],
                             "lora": STATE["lora"]})
        elif self.path == "/v1/models":
            self._send(200, {"object": "list", "data": [{"id": STATE["model_id"]}]})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/generate":
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
            result = run_generate(req)
            STATE["requests"] += 1
            self._send(200, result)
        except ClientError as exc:
            STATE["failed"] += 1
            self._send(400, {"error": str(exc)})
        except Exception:  # noqa: BLE001 - server fault: 500, traceback to the log
            STATE["failed"] += 1
            log("generate failed:\n%s" % traceback.format_exc())
            self._send(500, {"error": "internal error; see the serve log"})


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--model", required=True)
    p.add_argument("--served-model-name", required=True)
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--sample-dir", required=True)
    p.add_argument("--lora", default=None, help="path to a kohya-key LoRA .safetensors (applied unmerged)")
    p.add_argument("--lora-strength", type=float, default=1.0)
    args = p.parse_args()

    STATE["sample_dir"] = args.sample_dir
    STATE["model_id"] = args.served_model_name
    # `--lora none` (the recipe default) means no LoRA; a real path applies it unmerged.
    STATE["lora"] = None if (args.lora or "").strip().lower() in ("", "none") else args.lora
    STATE["lora_strength"] = args.lora_strength
    pipe, load_s = load_pipeline(args.model, "cuda", STATE["lora"], args.lora_strength)
    STATE["pipe"] = pipe
    log("ready: %s (load %.1f s) on %s:%d" % (args.served_model_name, load_s, args.host, args.port))
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
