#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""LTX-2.5 T2V launcher server: ComfyUI supervisor + expansion + one `/generate`.

`Lightricks/LTX-2.5` has no sglang/vLLM engine: the runtime is ComfyUI (a
subgraph workflow driven over the backend `/prompt` route). This script is the
arm's server, launched by the recipe as

    <RUNTIME_DIR>/venv/bin/python /workspace/mods/ltx-25-launcher/launcher.py \
        --comfy-dir <RUNTIME_DIR>/ComfyUI --host {host} --port {port}

Surface (this arm has no chat completions):

    GET  /health     -> liveness + which model/workflow is staged
    GET  /v1/models  -> the served repo id (sparkrun's readiness probe path)
    POST /generate   -> expand + patch + submit + poll; returns wall time,
                        peak unified memory, and the produced mp4 path(s)

POST /generate body (JSON), all optional except `prompt`:

    {"prompt": str, "width": 1344, "height": 768, "frames": 121,
     "fps": 24, "seed": 42, "timeout_s": 1800}

`frames` MUST satisfy `frames % 8 == 1` (the template's length is
`duration * fps + 1`; 5 s at 24 fps = 121). Width/height must be multiples of
32 and are applied to the primitive BEHIND each latent's `ComfyMathExpression
"a/2"` — a literal on `EmptyLTXVLatentVideo` bypasses the halving and silently
runs stage 1 at full resolution (receipt REPORT.md defect 4, two 410 s runs).

Traps re-checked here (receipt `~/benchmarks/ltx25-20261018/REPORT.md`):

  * `SaveVideo` is the output node; a graph without it "succeeds" in 0.01 s
    having generated nothing, so the prompt is garbage-collected from
    `SaveVideo` and its absence is a hard error.
  * The dead prompt-enhancer branch (ComfySwitchNode `on_false` +
    `gemma4_e2b_it_int8_convrot`) is aliased and collected, then asserted
    absent: the model is not downloaded and the node would fail validation.
  * ComfyUI's stdout is split on `\\r` as well as `\\n`, so tqdm sampler bars
    stay separable for a stage split.
  * Peak memory is MemTotal - MemAvailable (GB10 unified pool), the same
    metric the receipt's 1 Hz sampler used.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from expand2 import main as expand  # noqa: E402

STATE: dict = {
    "args": None,
    "backend": False,
    "started": time.time(),
    "lock": threading.Lock(),
    "requests": 0,
    "proc": None,
}


def log(msg: str) -> None:
    print("[ltx25] %s" % msg, flush=True)


def mem_used_gib() -> float | None:
    """Unified-memory used, the receipt's metric (MemTotal - MemAvailable)."""
    try:
        total = avail = None
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    avail = int(line.split()[1])
        if total is not None and avail is not None:
            return (total - avail) / (1024 * 1024)
    except OSError:
        pass
    return None


# ---------------------------------------------------------------------------
# Provisioning gate: the mod detaches a stage job (sparkrun's pre_exec hook
# has a hard 600 s SSH timeout, so a 36.9 GB fetch cannot block it). This
# process waits for that job and streams its log; a failed stage is fatal.
# ---------------------------------------------------------------------------

def _stage_state(path: str) -> tuple[str, str]:
    try:
        with open(path) as fh:
            fields = fh.read().split()
        return (fields[0], " ".join(fields[1:])) if fields else ("", "")
    except OSError:
        return ("", "")


def wait_for_stage(status_path: str, log_path: str, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    offset = 0
    last = None
    while True:
        state, detail = _stage_state(status_path)
        if state == "ok":
            log("stage job complete (%s)" % detail)
            return
        if state == "failed":
            _tail_from(log_path, offset)
            raise SystemExit("stage job FAILED (%s); see %s" % (detail, log_path))
        if not state and time.monotonic() > deadline:
            raise SystemExit(
                "no stage status at %s after %.0f s; the mod did not run or could not "
                "write its status" % (status_path, timeout_s)
            )
        if state and time.monotonic() > deadline:
            raise SystemExit("stage job still running after %.0f s (%s)" % (timeout_s, detail))
        offset = _tail_from(log_path, offset)
        if state != last:
            log("waiting for stage job: %s %s" % (state or "missing", detail))
            last = state
        time.sleep(5)


def _tail_from(path: str, offset: int) -> int:
    try:
        with open(path, "rb") as fh:
            fh.seek(offset)
            chunk = fh.read()
            new_offset = fh.tell()
    except OSError:
        return offset
    if chunk:
        for line in chunk.decode("utf-8", "replace").splitlines():
            log("stage: %s" % line)
    return new_offset


# ---------------------------------------------------------------------------
# ComfyUI supervision
# ---------------------------------------------------------------------------

def pump(stream) -> None:
    """Timestamp ComfyUI output, splitting on \\r as well as \\n (tqdm bars)."""
    buf = b""
    while True:
        ch = stream.read(1)
        if not ch:
            break
        buf += ch
        if ch in (b"\r", b"\n"):
            seg = buf.decode("utf-8", "replace").strip()
            if seg:
                log("comfy %.6f %s" % (time.time(), seg))
            buf = b""
        elif len(buf) > 8192:
            log("comfy %.6f PARTIAL %s" % (time.time(), buf.decode("utf-8", "replace")))
            buf = b""


def start_backend(args) -> subprocess.Popen:
    main_py = os.path.join(args.comfy_dir, "main.py")
    if not os.path.isfile(main_py):
        raise SystemExit("ComfyUI main.py not found at %s (mod staging failed)" % main_py)
    os.makedirs(args.output_dir, exist_ok=True)
    cmd = [
        sys.executable, "-u", "main.py",
        "--listen", "127.0.0.1",
        "--port", str(args.comfy_port),
        "--output-directory", os.path.abspath(args.output_dir),
        "--disable-auto-launch",
    ]
    log("starting ComfyUI: %s (cwd=%s)" % (" ".join(cmd), args.comfy_dir))
    proc = subprocess.Popen(
        cmd, cwd=args.comfy_dir,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0,
    )
    threading.Thread(target=pump, args=(proc.stdout,), daemon=True).start()
    return proc


def wait_backend(proc: subprocess.Popen, base: str, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise SystemExit("ComfyUI exited before it was ready (rc=%s)" % proc.returncode)
        try:
            with urllib.request.urlopen(base + "/object_info", timeout=10) as resp:
                info = json.loads(resp.read())
            if info:
                log("ComfyUI ready: %d node types" % len(info))
                STATE["backend"] = True
                return
        except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
            pass
        time.sleep(2)
    raise SystemExit("ComfyUI did not answer /object_info within %.0f s" % timeout_s)


# ---------------------------------------------------------------------------
# Workflow: locate, expand, patch
# ---------------------------------------------------------------------------

def find_workflow(explicit: str | None) -> str:
    if explicit:
        return explicit
    try:
        import importlib
        pkg = importlib.import_module("comfyui_workflow_templates_json")
    except ImportError as exc:
        raise SystemExit(
            "cannot locate the LTX workflow template: %s (comfyui-workflow-templates "
            "is part of the venv staged by this mod)" % exc
        )
    path = os.path.join(os.path.dirname(pkg.__file__), "templates",
                        "video_ltx2_5_t2v.json")
    if not os.path.isfile(path):
        raise SystemExit("workflow template missing from the installed package: %s" % path)
    return path


def _primitive_behind(prompt: dict, node_id: str, key: str):
    """The PrimitiveInt/ComfyMathExpression source feeding node_id.key, or None."""
    seen = set()
    ref = prompt[node_id]["inputs"].get(key)
    while isinstance(ref, list) and ref and ref[0] in prompt and ref[0] not in seen:
        seen.add(ref[0])
        node = prompt[ref[0]]
        if node["class_type"] == "ComfyMathExpression":
            ref = node["inputs"].get("values.a")
            continue
        if "value" in node["inputs"]:
            return node
        return None
    return None


def set_dim(prompt: dict, node_id: str, key: str, value: int) -> str:
    source = _primitive_behind(prompt, node_id, key)
    if source is not None:
        source["inputs"]["value"] = value
        return "%s.value = %d (via %s.%s)" % (node_id, value, node_id, key)
    prompt[node_id]["inputs"][key] = value
    return "%s.%s = %d (literal)" % (node_id, key, value)


def _find_text_encoder(prompt: dict, ref, depth: int = 0):
    """Follow a guider's `positive` link to its CLIPTextEncode.

    The template routes both guiders through `LTXVConditioning`, so a one-hop
    lookup would silently leave the template's default prompt in place.
    """
    if depth > 4 or not (isinstance(ref, list) and ref and ref[0] in prompt):
        return None
    node = prompt[ref[0]]
    if node["class_type"] == "CLIPTextEncode":
        return node
    for key in ("positive", "conditioning", "conditioning_1", "text"):
        found = _find_text_encoder(prompt, node["inputs"].get(key), depth + 1)
        if found is not None:
            return found
    return None


def _set_positive_prompt(prompt: dict, text: str) -> bool:
    for node in prompt.values():
        if node["class_type"] != "LTXVDualCFGGuider":
            continue
        target = _find_text_encoder(prompt, node["inputs"].get("positive"))
        if target is not None:
            target["inputs"]["text"] = text
    return any(
        n["class_type"] == "CLIPTextEncode" and n["inputs"].get("text") == text
        for n in prompt.values()
    )


def gc(prompt: dict, out_class: str = "SaveVideo") -> tuple[dict, list[str]]:
    outs = [k for k, v in prompt.items() if v["class_type"] == out_class]
    keep, stack = set(outs), list(outs)
    while stack:
        nid = stack.pop()
        for ref in prompt[nid]["inputs"].values():
            if (isinstance(ref, list) and len(ref) == 2 and isinstance(ref[0], str)
                    and ref[0] in prompt and ref[0] not in keep):
                keep.add(ref[0])
                stack.append(ref[0])
    return ({k: v for k, v in prompt.items() if k in keep},
            sorted(set(prompt) - keep, key=lambda x: (len(x), x)))


def build_prompt(workflow: str, base_url: str, req: dict) -> tuple[dict, list[str]]:
    prompt = expand(workflow, base_url)
    applied: list[str] = []

    if not _set_positive_prompt(prompt, req["prompt"]):
        raise RuntimeError("no CLIPTextEncode reachable from a guider's positive input")

    for nid in list(prompt):
        node = prompt[nid]
        ct = node["class_type"]
        if ct == "UNETLoader":
            node["inputs"]["unet_name"] = req["transformer"]
            applied.append("%s.unet_name = %s" % (nid, req["transformer"]))
        elif ct == "EmptyLTXVLatentVideo":
            applied.append(set_dim(prompt, nid, "width", req["width"]))
            applied.append(set_dim(prompt, nid, "height", req["height"]))
            node["inputs"]["length"] = req["frames"]
            applied.append("%s.length = %d" % (nid, req["frames"]))
        elif ct == "LTXVEmptyLatentAudio":
            node["inputs"]["frames_number"] = req["frames"]
            node["inputs"]["frame_rate"] = req["fps"]
            applied.append("%s frames=%d fps=%d" % (nid, req["frames"], req["fps"]))
        elif ct == "LTXVConditioning":
            node["inputs"]["frame_rate"] = req["fps"]
            applied.append("%s.frame_rate = %d" % (nid, req["fps"]))
        elif ct == "CreateVideo":
            node["inputs"]["fps"] = req["fps"]
            applied.append("%s.fps = %d" % (nid, req["fps"]))
        elif ct == "RandomNoise":
            node["inputs"]["noise_seed"] = req["seed"]
            applied.append("%s.noise_seed = %d" % (nid, req["seed"]))
        elif ct == "SaveVideo":
            node["inputs"]["filename_prefix"] = "ltx25/t2v_%d_%dx%d_%df" % (
                req["seed"], req["width"], req["height"], req["frames"])
            applied.append("%s.filename_prefix set" % nid)

    # Dead prompt-enhancer branch: switch off -> alias on_true to on_false, then
    # the reachability GC drops the branch (its CLIPLoader points at
    # gemma4_e2b, which this arm deliberately does not download).
    for nid, node in prompt.items():
        if node["class_type"] != "ComfySwitchNode" or "on_true" not in node["inputs"]:
            continue
        sw = node["inputs"].get("switch")
        off = sw is False
        if isinstance(sw, list) and sw and sw[0] in prompt:
            off = prompt[sw[0]]["inputs"].get("value") is False
        if off:
            node["inputs"]["on_true"] = node["inputs"]["on_false"]
            applied.append("%s switch off: on_true aliased to on_false" % nid)

    prompt, dead = gc(prompt)
    if dead:
        applied.append("gc dropped %s" % dead)

    if not any(n["class_type"] == "SaveVideo" for n in prompt.values()):
        raise RuntimeError(
            "SaveVideo is absent after expansion/GC; ComfyUI would 'succeed' in "
            "0.01 s having generated nothing"
        )
    if "gemma4_e2b" in json.dumps(prompt):
        raise RuntimeError(
            "dead prompt-enhancer branch survived GC (gemma4_e2b reference remains); "
            "ComfyUI validation would fail on the undownloaded model"
        )
    return prompt, applied


# ---------------------------------------------------------------------------
# Request handling helpers
# ---------------------------------------------------------------------------

def http_json(url: str, body: dict | None = None, timeout: float = 60):
    data = None if body is None else json.dumps(body).encode()
    headers = {} if body is None else {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            payload = {"raw": raw.decode("utf-8", "replace")[:4000]}
        return exc.code, payload


class _Sampler(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.peak = 0.0
        self.stop = threading.Event()

    def run(self) -> None:
        while not self.stop.is_set():
            used = mem_used_gib()
            if used is not None:
                self.peak = max(self.peak, used)
            self.stop.wait(1.0)


def generate(req: dict) -> tuple[int, dict]:
    args = STATE["args"]
    width, height = int(req["width"]), int(req["height"])
    frames = int(req["frames"])
    fps = float(req["fps"])
    if fps.is_integer():
        fps = int(fps)
    if frames % 8 != 1:
        return 400, {"error": "frames must satisfy frames %% 8 == 1 (got %d); 5 s at "
                              "24 fps is 121" % frames}
    if width % 32 or height % 32 or width <= 0 or height <= 0:
        return 400, {"error": "width/height must be positive multiples of 32"}

    with STATE["lock"]:
        prompt, applied = build_prompt(args.workflow, args.comfy_url, {
            "prompt": req["prompt"],
            "width": width, "height": height,
            "frames": frames, "fps": fps, "seed": int(req["seed"]),
            "transformer": args.transformer,
        })
        log("submit: %dx%d %d frames @ %g fps seed=%d nodes=%d"
            % (width, height, frames, fps, int(req["seed"]), len(prompt)))
        sampler = _Sampler()
        sampler.start()
        t0 = time.monotonic()
        try:
            code, body = http_json(args.comfy_url + "/prompt",
                                   {"prompt": prompt, "client_id": "sparkrun-ltx25"})
            if code != 200 or "prompt_id" not in body:
                return 502, {"error": "ComfyUI rejected the prompt", "status": code,
                             "detail": body, "applied": applied}
            pid = body["prompt_id"]
            timeout_s = min(float(req["timeout_s"]), float(args.max_timeout))
            entry: dict = {}
            while time.monotonic() - t0 < timeout_s:
                time.sleep(2)
                code, hist = http_json(args.comfy_url + "/history/" + pid)
                if code == 200 and pid in hist:
                    entry = hist[pid]
                    status = entry.get("status", {})
                    if status.get("completed") or status.get("status_str") == "error":
                        break
        finally:
            sampler.stop.set()
        wall = time.monotonic() - t0
        timed_out = not entry
        status = entry.get("status", {})
        outputs = []
        for node_id, node_out in (entry.get("outputs") or {}).items():
            for item in node_out.get("images", []):
                if not isinstance(item, dict) or "filename" not in item:
                    continue
                sub = item.get("subfolder") or ""
                outputs.append({
                    "node": node_id,
                    "filename": item["filename"],
                    "subfolder": sub,
                    "type": item.get("type", "output"),
                    "path": os.path.join(args.output_dir, sub, item["filename"]),
                })
        result = {
            "prompt_id": pid,
            "wall_s": round(wall, 2),
            "status": status.get("status_str"),
            "completed": bool(status.get("completed")),
            "timed_out": timed_out,
            "peak_gib": round(sampler.peak, 2) if sampler.peak else None,
            "seed": int(req["seed"]), "width": width, "height": height,
            "frames": frames, "fps": fps,
            "outputs": outputs,
            "applied": applied,
        }
        if timed_out:
            return 504, {"error": "prompt did not finish within the request timeout; "
                                  "ComfyUI may still be rendering it", **result}
        if status.get("status_str") == "error":
            return 502, {"error": "ComfyUI prompt failed", "detail": status, **result}
        if not outputs:
            return 502, {"error": "prompt completed with no output file (SaveVideo produced "
                                   "nothing)", **result}
        STATE["requests"] += 1
        log("done: %s wall=%.2fs peak=%s GiB files=%s"
            % (pid, wall, result["peak_gib"], [o["filename"] for o in outputs]))
        return 200, result


def handler_factory():
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def log_message(self, format, *args):  # route import-time noise to log()
            log("http %s %s" % (self.address_string(), format % args))

        def _send(self, code: int, payload: dict) -> None:
            raw = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            args = STATE["args"]
            if path == "/health":
                proc = STATE.get("proc")
                alive = proc is not None and proc.poll() is None
                self._send(200 if alive else 503, {
                    "status": "ok" if (STATE["backend"] and alive) else "degraded",
                    "backend": "comfyui" if alive else None,
                    "backend_rc": None if alive or proc is None else proc.returncode,
                    "model": args.model,
                    "revision": args.revision,
                    "served_model_name": args.served_model_name,
                    "workflow": os.path.basename(args.workflow),
                    "uptime_s": round(time.time() - STATE["started"], 1),
                    "requests": STATE["requests"],
                })
            elif path == "/v1/models":
                self._send(200, {"object": "list", "data": [{
                    "id": args.served_model_name,
                    "object": "model",
                    "created": int(STATE["started"]),
                    "owned_by": "littlecedar",
                }]})
            else:
                self._send(404, {"error": "no route %s" % path})

        def do_POST(self) -> None:
            path = self.path.split("?", 1)[0]
            if path != "/generate":
                self._send(404, {"error": "no route %s" % path})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                req = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, json.JSONDecodeError) as exc:
                self._send(400, {"error": "bad JSON body: %s" % exc})
                return
            req.setdefault("prompt", "")
            req.setdefault("width", 1344)
            req.setdefault("height", 768)
            req.setdefault("frames", 121)
            req.setdefault("fps", 24)
            req.setdefault("seed", 42)
            req.setdefault("timeout_s", 1800)
            if not isinstance(req["prompt"], str) or not req["prompt"].strip():
                self._send(400, {"error": "prompt must be a non-empty string"})
                return
            try:
                code, payload = generate(req)
            except (RuntimeError, SystemExit) as exc:
                self._send(500, {"error": str(exc)})
                return
            self._send(code, payload)

    return Handler


def selftest() -> None:
    """Guards the two receipt defects that cost real runs, with no ComfyUI.

    Run: launcher.py --selftest  (the repo's unittest suite cannot import this
    mod's venv-only expander; this is the runnable check for the patch logic).
    """
    p = {
        "1": {"class_type": "PrimitiveInt", "inputs": {"value": 1280}},
        "2": {"class_type": "ComfyMathExpression", "inputs": {"values.a": ["1", 0]}},
        "3": {"class_type": "EmptyLTXVLatentVideo",
              "inputs": {"width": ["2", 0], "height": ["2", 0], "length": 97}},
        "4": {"class_type": "ComfySwitchNode",
              "inputs": {"on_false": ["5", 0], "on_true": ["6", 0], "switch": ["7", 0]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": "negative"}},
        "6": {"class_type": "TextGenerateLTX2Prompt", "inputs": {"clip": ["8", 0]}},
        "7": {"class_type": "PrimitiveBoolean", "inputs": {"value": False}},
        "8": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": "gemma4_e2b_it_int8_convrot.safetensors"}},
        "9": {"class_type": "LTXVDualCFGGuider",
              "inputs": {"positive": ["11", 0], "negative": ["11", 1]}},
        "11": {"class_type": "LTXVConditioning",
               "inputs": {"positive": ["5", 0], "negative": ["5", 0], "frame_rate": 24}},
        "10": {"class_type": "SaveVideo", "inputs": {"video": ["9", 0],
                                                     "filename_prefix": "x"}},
    }
    # Defect 4: the dimension lives on the primitive behind `a/2`; a literal on
    # EmptyLTXVLatentVideo would bypass the halving.
    set_dim(p, "3", "width", 1344)
    assert p["1"]["inputs"]["value"] == 1344
    assert p["3"]["inputs"]["width"] == ["2", 0]

    assert _set_positive_prompt(p, "hello")
    # The real template routes guider.positive through LTXVConditioning; the
    # resolver must land on the CLIPTextEncode behind it.
    assert p["5"]["inputs"]["text"] == "hello"

    # Defect 3: switch off -> on_true aliased, dead branch collected, and the
    # undownloaded prompt-enhancer model cannot survive into the prompt.
    for nid, node in p.items():
        if node["class_type"] == "ComfySwitchNode":
            node["inputs"]["on_true"] = node["inputs"]["on_false"]
    kept, dropped = gc(p)
    assert {"6", "7", "8", "4"} <= set(dropped), dropped
    assert "10" in kept and "gemma4_e2b" not in json.dumps(kept)

    # Trap: a prompt without SaveVideo must not be accepted as a success.
    kept2, _ = gc({k: v for k, v in p.items() if k != "10"})
    assert not any(n["class_type"] == "SaveVideo" for n in kept2.values())

    assert 121 % 8 == 1 and 124 % 8 != 1
    print("selftest OK: set_dim walks /2, switch alias + GC, SaveVideo required, "
          "frames % 8 == 1")


def main() -> int:
    if "--selftest" in sys.argv:
        selftest()
        return 0
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--revision", default="")
    ap.add_argument("--served-model-name", default=None)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--comfy-dir", required=True)
    ap.add_argument("--workflow", default=None,
                    help="UI-format template; default: the installed "
                         "comfyui-workflow-templates copy of video_ltx2_5_t2v.json")
    ap.add_argument("--output-dir", default=None)
    ap.add_argument("--comfy-port", type=int, default=8188)
    ap.add_argument("--transformer",
                    default="ltx-2.5-22b-distilled-transformer-nvfp4.safetensors")
    ap.add_argument("--backend-timeout", type=float, default=900)
    ap.add_argument("--stage-status", default="/cache/runtime/ltx-25/stage.status")
    ap.add_argument("--stage-log", default="/cache/runtime/ltx-25/stage.log")
    ap.add_argument("--stage-timeout", type=float, default=7200)
    ap.add_argument("--no-wait-stage", action="store_true")
    ap.add_argument("--max-timeout", type=float, default=3600)
    args = ap.parse_args()
    args.served_model_name = args.served_model_name or args.model
    args.output_dir = args.output_dir or os.path.join(args.comfy_dir, "output")
    args.comfy_url = "http://127.0.0.1:%d" % args.comfy_port
    STATE["args"] = args

    if not args.no_wait_stage:
        wait_for_stage(args.stage_status, args.stage_log, args.stage_timeout)

    args.workflow = find_workflow(args.workflow)
    log("workflow: %s" % args.workflow)

    proc = start_backend(args)
    STATE["proc"] = proc
    try:
        wait_backend(proc, args.comfy_url, args.backend_timeout)
    except SystemExit:
        proc.terminate()
        raise

    server = ThreadingHTTPServer((args.host, args.port), handler_factory())
    server.daemon_threads = True
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log("serving on %s:%d (backend %s, model %s)" % (args.host, args.port,
                                                     args.comfy_url, args.model))
    stop.wait()
    log("shutting down")
    server.shutdown()
    proc.terminate()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())