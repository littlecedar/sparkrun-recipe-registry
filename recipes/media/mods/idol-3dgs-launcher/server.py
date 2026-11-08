#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""idol image-to-3DGS sampler on the `runtime: vllm` contract (media lane, eval-only).

speridlabs/idol is served by the project's own SDK, not by sglang or vLLM, so
this script is the arm's entry point, in the shape of the lane's Kromoss and
Qwen-Image script arms. Launched by the recipe as

    <RUNTIME_DIR>/venv/bin/python /workspace/mods/idol-3dgs-launcher/server.py

with the venv staged by this mod's run.sh (idol SDK at a pinned commit on the
image's own torch).

The trial is one SDK invocation on the tracked fixture, and it runs **before the
port binds**: `python -m idol.sample` is exec'd with inherited stdio, so its
progress and any gate error land verbatim in the serve log, and a non-zero exit
takes the container down instead of leaving a server that cannot sample. Only
after a `.ply` exists does the process answer sparkrun's readiness probe:

    GET /health     -> {"status": "ok", "sample": {...}}   liveness + the cell
    GET /v1/models  -> the served repo id (sparkrun/run-arm probe this path)

There is no request surface: the product is the files in --sample-dir (a
`/cache/runtime` path, so the receipt reads them from the host), and the
`/health` body carries the measurement — wall seconds, `.ply` bytes, and the
Gaussian count parsed from the PLY header.

Weights: `--weights` must be the prepared snapshot directory (the recipe renders
`{model}`). A repo id is refused here rather than passed to the SDK, because the
SDK would then call `snapshot_download` at serve time and the container runs
`HF_HUB_OFFLINE=1`.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WEIGHT_FILES = ("config.json", "denoiser.safetensors", "decoder.safetensors",
                "decoder_gs.safetensors", "birefnet.safetensors")
# The 3DGS PLY property set a viewer needs; a `.ply` missing these is not the
# product the card promises (xyz/opacity/scaling/rotation/degree-0 SH).
PLY_PROPERTIES = ("x", "y", "z", "f_dc_0", "opacity", "scale_0", "rot_0")

STATE: dict = {"model_id": None, "sample": {}, "failed": 0}


def log(message: str) -> None:
    print("[idol] %s" % message, flush=True)


def ply_header(path: str) -> tuple[int, list[str]]:
    """Return (element vertex count, property names) from a binary PLY header."""
    count, props = 0, []
    with open(path, "rb") as handle:
        if handle.readline().strip() != b"ply":
            raise ValueError("%s is not a PLY file" % path)
        for raw in handle:
            line = raw.decode("ascii", "replace").strip()
            if line.startswith("element vertex "):
                count = int(line.split()[2])
            elif line.startswith("property "):
                props.append(line.split()[-1])
            elif line == "end_header":
                return count, props
    raise ValueError("%s has no PLY end_header" % path)


def check_weights(weights: str, revision: str) -> None:
    if not os.path.isdir(weights):
        sys.exit("error: --weights is not a directory (%r): the recipe must pass {model}, "
                 "the prepared snapshot, not a repo id — the container runs HF_HUB_OFFLINE=1" % weights)
    missing = [name for name in WEIGHT_FILES if not os.path.isfile(os.path.join(weights, name))]
    if missing:
        sys.exit("error: prepared weights %r are missing %s (idol needs all five files; "
                 "pin %s in the pool)" % (weights, ", ".join(missing), revision))
    log("weights: %s (revision %s)" % (weights, revision))


def run_sample(args: argparse.Namespace, out: str) -> dict:
    os.makedirs(out, exist_ok=True)
    name = os.path.splitext(os.path.basename(args.image))[0]
    cmd = [sys.executable, "-m", "idol.sample",
           "--image", args.image, "--weights", args.weights, "--out", out,
           "--mode", args.mode, "--seed", str(args.seed), "--steps", str(args.steps),
           "--cfg_strength", str(args.cfg_strength), "--rescale_t", str(args.rescale_t),
           "--num_gaussians", str(args.num_gaussians), "--dinov3_dtype", args.dinov3_dtype]
    if not args.optimize:
        cmd.append("--no_optimize")
    log("sample: %s" % " ".join(cmd[1:]))
    started = time.time()
    # Inherited stdio: the SDK's own progress and gate errors are the log record.
    rc = subprocess.call(cmd)
    wall = time.time() - started
    if rc != 0:
        STATE["failed"] += 1
        sys.exit("error: idol.sample exited %d after %.1fs (stdout above names the cause; "
                 "a gated encoder or missing weights fail before any work)" % (rc, wall))

    ply = os.path.join(out, "%s.ply" % name)
    input_png = os.path.join(out, "%s_input.png" % name)
    camera_json = os.path.join(out, "%s_camera.json" % name)
    absent_outputs = [p for p in (ply, input_png, camera_json) if not os.path.isfile(p)]
    if absent_outputs:
        sys.exit("error: idol.sample exited 0 but wrote no %s" % ", ".join(absent_outputs))
    vertex_count, props = ply_header(ply)
    absent = [p for p in PLY_PROPERTIES if p not in props]
    if absent:
        sys.exit("error: %s is not a 3DGS PLY (missing properties %s)" % (ply, ", ".join(absent)))
    sample = {
        "mode": args.mode, "seed": args.seed, "steps": args.steps,
        "cfg_strength": args.cfg_strength, "rescale_t": args.rescale_t,
        "num_gaussians": args.num_gaussians, "dinov3_dtype": args.dinov3_dtype,
        "optimize": args.optimize, "wall_s": round(wall, 3),
        "ply": ply, "ply_bytes": os.path.getsize(ply), "gaussians": vertex_count,
        "input_png": input_png, "input_png_bytes": os.path.getsize(input_png),
        "camera_json": camera_json, "camera_json_bytes": os.path.getsize(camera_json),
    }
    log("sample done in %.3fs: %s (%d gaussians, %d bytes)"
        % (wall, ply, vertex_count, sample["ply_bytes"]))
    return sample


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        pass

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/health", "/healthz"):
            self._send(200, {"status": "ok", "model": STATE["model_id"],
                             "sample": STATE["sample"], "failed": STATE["failed"]})
        elif path == "/v1/models":
            self._send(200, {"object": "list", "data": [{"id": STATE["model_id"]}]})
        else:
            self._send(404, {"error": "not found; this arm's only surface is the sample in"
                                      " /health and the files in the sample dir"})


def main() -> None:
    p = argparse.ArgumentParser(description="idol image-to-3DGS sampler")
    p.add_argument("--weights", required=True, help="prepared weights directory (the recipe's {model})")
    p.add_argument("--revision", default="", help="the recipe's model_revision pin (logged)")
    p.add_argument("--image", required=True, help="input image (the tracked fixture)")
    p.add_argument("--sample-dir", required=True, help="output dir for .ply/_input.png/_camera.json")
    p.add_argument("--served-model-name", required=True)
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--mode", choices=["synthetic", "real"], default="synthetic",
                   help="'synthetic' for renders/generated images, 'real' for photographs")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--steps", type=int, default=50)
    p.add_argument("--cfg-strength", type=float, default=3.0)
    p.add_argument("--rescale-t", type=float, default=3.0)
    p.add_argument("--num-gaussians", type=int, default=262144)
    p.add_argument("--dinov3-dtype", choices=["bf16", "fp32"], default="bf16")
    p.add_argument("--optimize", type=int, choices=[0, 1], default=1,
                   help="1 = the SDK's faster sampling (torch.compile + cuDNN attn + TF32); 0 passes --no_optimize")
    args = p.parse_args()

    STATE["model_id"] = args.served_model_name
    check_weights(args.weights, args.revision)
    STATE["sample"] = run_sample(args, os.path.abspath(args.sample_dir))
    log("serving %s on %s:%d" % (args.served_model_name, args.host, args.port))
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
