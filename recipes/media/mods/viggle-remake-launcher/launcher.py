#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""HTTP shim in front of ComfyUI for the Viggle-Remake v2v arm.

ComfyUI is the engine, but sparkrun's readiness wait probes `/v1/models` and a
caller needs a single verb, so this process owns the port: it waits for the
mod's detached stage, starts ComfyUI on a private port as a child, then serves

  GET  /health      liveness
  GET  /v1/models   the served id plus the two workflow tasks
  POST /generate    queue one render and return its mp4 path + wall seconds

and forwards anything else to ComfyUI unchanged, so `/prompt`, `/history`,
`/view` and the UI stay reachable.

The graph is the vendor's own API workflow (`workflows/remake_{swap,edit}_api.json`,
fetched from the model repo by run.sh). Two of its loaders name the FULL bf16
base, which is 124 GB and does not fit one GB10, so `--dit` and `--text-encoder`
repoint them at the AdaLN-pruned fp8 DiT and the NVFP4-AWQ encoder run.sh staged.
Nothing else in the graph is rewritten; the LoRA is selected by task.

Exit 2 means this shim could not reach the stage or ComfyUI - never a verdict
on the render.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DIT_PRUNED = "minimax_h3_fl2va_pruned_fp8_scaled.safetensors"
TEXT_ENCODER_NVFP4 = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
LORAS = {
    "swap": "viggle_remake_swap_comfyui.safetensors",
    "edit": "viggle_remake_edit_comfyui.safetensors",
}

ARGS: argparse.Namespace
COMFY: subprocess.Popen | None = None


def log(msg: str) -> None:
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} launcher: {msg}",
          file=sys.stderr, flush=True)


def http_json(url: str, payload: dict | None = None, timeout: float = 30.0) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def wait_for_stage() -> None:
    """Block until the mod's detached stage reports ok, or die on its message."""
    status_path = ARGS.stage_status
    log_path = ARGS.stage_log
    last = -1
    deadline = time.monotonic() + ARGS.stage_timeout
    while time.monotonic() < deadline:
        try:
            status = open(status_path, encoding="utf-8").read().strip()
        except FileNotFoundError:
            status = ""
        if status == "ok":
            log("stage ok")
            return
        if status.startswith("failed"):
            sys.stderr.write(f"stage failed: {status}\n")
            sys.stderr.write(_tail(log_path, 40))
            sys.exit(2)
        try:
            size = os.path.getsize(log_path)
        except OSError:
            size = 0
        if size != last:
            last = size
            log(f"staging ({size} bytes of log)")
        time.sleep(10)
    sys.stderr.write(f"stage did not finish in {ARGS.stage_timeout}s\n")
    sys.stderr.write(_tail(log_path, 40))
    sys.exit(2)


def _tail(path: str, lines: int) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return "".join(fh.readlines()[-lines:])
    except OSError:
        return ""


def assert_pin() -> None:
    """The mod records what it staged; a recipe pin that moved must not serve."""
    try:
        staged = dict(
            line.split("=", 1) for line in
            open(ARGS.staged_env, encoding="utf-8").read().splitlines() if "=" in line
        )
    except OSError:
        log("staged.env absent (older stage); skipping the pin check")
        return
    want = staged.get("MODEL_REVISION", "").strip()
    if want and want != ARGS.revision:
        sys.stderr.write(
            f"recipe pins revision {ARGS.revision} but the staged weights are {want}; "
            "re-run the stage (delete the runtime dir) or fix the recipe\n")
        sys.exit(2)


def start_comfy() -> None:
    global COMFY
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    cmd = [os.path.join(ARGS.venv_dir, "bin", "python"), "main.py",
           "--listen", "127.0.0.1", "--port", str(ARGS.comfy_port),
           "--output-directory", ARGS.output_dir,
           "--input-directory", ARGS.input_dir]
    log("starting ComfyUI: " + " ".join(cmd))
    COMFY = subprocess.Popen(cmd, cwd=ARGS.comfy_dir, env=env)
    base = f"http://127.0.0.1:{ARGS.comfy_port}"
    deadline = time.monotonic() + ARGS.boot_timeout
    while time.monotonic() < deadline:
        if COMFY.poll() is not None:
            sys.stderr.write(f"ComfyUI exited during start (rc={COMFY.returncode})\n")
            sys.exit(2)
        try:
            http_json(f"{base}/system_stats", timeout=5)
            log("ComfyUI answers /system_stats")
            return
        except (urllib.error.URLError, OSError, ValueError):
            time.sleep(2)
    sys.stderr.write(f"ComfyUI did not answer in {ARGS.boot_timeout}s\n")
    sys.exit(2)


def patch_graph(task: str, body: dict, staged_dir: str) -> dict:
    path = os.path.join(staged_dir, f"remake_{task}_api.json")
    graph = json.load(open(path, encoding="utf-8"))
    seed = int(body.get("seed", 0))
    prompt = body.get("prompt")
    source = body.get("source")
    refs = body.get("refs") or []
    if not source:
        raise ValueError("source is required (a filename already in the ComfyUI input dir)")
    if len(refs) != 2:
        raise ValueError("refs must be exactly two filenames (both pinned as keyframes)")
    images = []
    for node_id, node in graph.items():
        ct = node.get("class_type")
        if ct == "UNETLoader":
            node["inputs"]["unet_name"] = DIT_PRUNED
        elif ct == "CLIPLoader":
            node["inputs"]["clip_name"] = TEXT_ENCODER_NVFP4
        elif ct == "LoraLoaderBypassModelOnly":
            node["inputs"]["lora_name"] = LORAS[task]
        elif ct == "LoadVideo":
            node["inputs"]["file"] = source
        elif ct == "LoadImage":
            images.append(node_id)
        elif ct == "RemakeConditioning" and prompt:
            node["inputs"]["prompt"] = prompt
        elif ct == "RemakeNoise":
            node["inputs"]["seed"] = seed
    for node_id, ref in zip(sorted(images, key=int), refs):
        graph[node_id]["inputs"]["image"] = ref
    return graph


def run_render(task: str, body: dict) -> dict:
    base = f"http://127.0.0.1:{ARGS.comfy_port}"
    graph = patch_graph(task, body, ARGS.workflows_dir)
    started = time.time()
    queued = http_json(f"{base}/prompt", {"prompt": graph, "client_id": "sparkrun-viggle"})
    pid = queued.get("prompt_id")
    if not pid:
        raise ValueError(f"ComfyUI refused the graph: {json.dumps(queued)[:400]}")
    log(f"queued {task} prompt {pid}")
    deadline = time.monotonic() + ARGS.render_timeout
    while time.monotonic() < deadline:
        hist = http_json(f"{base}/history/{pid}")
        entry = hist.get(pid)
        if entry:
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                raise RuntimeError(f"render failed: {json.dumps(status)[:600]}")
            out = _first_video(entry.get("outputs") or {})
            if out:
                src = os.path.join(ARGS.output_dir, out)
                dst = os.path.join(ARGS.output_dir, f"{task}-{pid[:8]}.mp4")
                if os.path.exists(src):
                    shutil.copyfile(src, dst)
                    src = dst
                return {"video": src, "prompt_id": pid,
                        "wall_s": round(time.time() - started, 1)}
        time.sleep(3)
    raise TimeoutError(f"render {pid} did not finish in {ARGS.render_timeout}s")


def _first_video(outputs: dict) -> str | None:
    for node_out in outputs.values():
        for key in ("images", "gifs", "videos"):
            for item in node_out.get(key) or []:
                name = item.get("filename", "")
                if name.endswith(".mp4"):
                    sub = item.get("subfolder") or ""
                    return os.path.join(sub, name) if sub else name
    return None


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):  # keep the serve log readable
        log("%s %s" % (self.command, fmt % a))

    def _send(self, code: int, payload: dict) -> None:
        raw = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/health"):
            return self._send(200, {"status": "ok", "comfyui": f"127.0.0.1:{ARGS.comfy_port}"})
        if self.path.startswith("/v1/models"):
            return self._send(200, {"object": "list", "data": [{
                "id": ARGS.served_model_name, "object": "model",
                "meta": {"tasks": sorted(LORAS), "workflows": os.listdir(ARGS.workflows_dir),
                         "dit": DIT_PRUNED, "text_encoder": TEXT_ENCODER_NVFP4}}]})
        return self._proxy("GET", b"")

    def do_POST(self):  # noqa: N802
        body = self._read_body()
        if self.path.startswith("/generate"):
            try:
                req = json.loads(body or b"{}")
                task = req.get("task", "swap")
                if task not in LORAS:
                    raise ValueError(f"task must be one of {sorted(LORAS)}")
                return self._send(200, run_render(task, req))
            except (ValueError, TimeoutError) as exc:
                return self._send(400, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001 - surface the engine's own words
                return self._send(500, {"error": repr(exc)})
        return self._proxy("POST", body)

    def _proxy(self, method: str, body: bytes):
        url = f"http://127.0.0.1:{ARGS.comfy_port}{self.path}"
        req = urllib.request.Request(url, data=body or None, method=method,
                                     headers={"Content-Type": self.headers.get(
                                         "Content-Type", "application/json")})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                raw = r.read()
                self.send_response(r.status)
                for k, v in r.headers.items():
                    if k.lower() not in ("transfer-encoding", "content-length"):
                        self.send_header(k, v)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            self.send_response(exc.code)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)


def main() -> int:
    global ARGS
    p = argparse.ArgumentParser()
    p.add_argument("--comfy-dir", required=True)
    p.add_argument("--venv-dir", required=True)
    p.add_argument("--workflows-dir", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--input-dir", required=True)
    p.add_argument("--stage-status", required=True)
    p.add_argument("--stage-log", required=True)
    p.add_argument("--staged-env", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--revision", required=True)
    p.add_argument("--served-model-name", required=True)
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--comfy-port", type=int, default=8188)
    p.add_argument("--stage-timeout", type=int, default=5400)
    p.add_argument("--boot-timeout", type=int, default=900)
    p.add_argument("--render-timeout", type=int, default=3600)
    ARGS = p.parse_args()

    wait_for_stage()
    assert_pin()
    start_comfy()
    srv = ThreadingHTTPServer((ARGS.host, ARGS.port), Handler)
    log(f"serving on {ARGS.host}:{ARGS.port} (engine {ARGS.model}@{ARGS.revision[:12]})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if COMFY and COMFY.poll() is None:
            COMFY.terminate()
            try:
                COMFY.wait(timeout=30)
            except subprocess.TimeoutExpired:
                COMFY.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())