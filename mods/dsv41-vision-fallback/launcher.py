#!/usr/bin/env python3
"""sparkrun -> TensorFold launcher shim for the DSV41 TP=2 lane, WITH VISION,
FALLBACK ARM (C): `--vision` is passed, but no VL bias is staged.

Trial variant of `mods/dsv41-vision-overlay/`: identical except that
`TF_DS_VISION_EXTRA` points at this mod's own directory, which deliberately
contains no *.safetensors. The engine then warns
`no ffn.gate.bias_vl found ... image tokens route with the text bias` and image
tokens route with the text bias -- that is the arm being measured (see
`.scratch/ds4/vision-hard/PREREGISTRATION.md`). `run.sh` fails closed if a
safetensors file ever appears here, so this arm cannot silently become arm B.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HF_HUB = "/cache/huggingface/hub"
RUNTIME_CACHE = "/cache/runtime/tensorfold"
ENGRAM_DIR = os.environ.get("TENSORFOLD_ENGRAM_DIR", "/cache/huggingface/hub/dsv41-engram")

# Fallback arm: this folder intentionally holds no VL-bias safetensors.
# attach_vl_bias() globs *.safetensors here, finds none, and its fallback chain
# (model dir, Engram dir) holds none either -- so image tokens route with the
# text bias, by design.
VISION_EXTRA = os.environ.get(
    "TENSORFOLD_VISION_EXTRA", "/workspace/mods/dsv41-vision-fallback"
)

MODEL_ORG, MODEL_NAME = "Mia-AiLab", "DeepSeek-V4.1-Flash-EXL3-2.9bpw"

RECIPE_ENV = {
    "TF_DS_REPLAY": "1",
    "TF_DS_PREFILL_CHUNK": "2048",
    "TF_DS_RANK_CACHE": str(Path(RUNTIME_CACHE) / "rank-cache"),
    "TF_DS_RANK_CACHE_READERS": "32",
    "TF_DS_WARM_LENGTHS": "1,17,33,131,514,1024,2113",
    "TORCH_EXTENSIONS_DIR": str(Path(RUNTIME_CACHE) / "torch-extensions"),
    "TF_DS_TOKEN_MAP": str(Path(RUNTIME_CACHE) / "token_map.json"),
    "HOME": RUNTIME_CACHE,
    # --- the vision delta (no bias staged; fallback arm) --------------------
    "TF_DS_VISION_EXTRA": VISION_EXTRA,
}


def resolve_checkpoint(repo: str) -> str:
    direct = Path(repo)
    if direct.is_dir():
        return str(direct)
    root = Path(HF_HUB) / ("models--" + repo.replace("/", "--"))
    ref = root / "refs" / "main"
    if ref.is_file():
        snap = root / "snapshots" / ref.read_text().strip()
        if (snap / "config.json").is_file():
            return str(snap)
    snapshots = sorted((root / "snapshots").glob("*")) if (root / "snapshots").is_dir() else []
    for snap in reversed(snapshots):
        if (snap / "config.json").is_file():
            return str(snap)
    return repo


def prepare_runtime_cache() -> None:
    for sub in ("", "rank-cache", "torch-extensions"):
        Path(RUNTIME_CACHE, sub).mkdir(parents=True, exist_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--boot", action="store_true")
    parser.add_argument("--model", default=f"{MODEL_ORG}/{MODEL_NAME}")
    parser.add_argument("--port", type=int, default=18891)
    parser.add_argument("--tp", type=int, default=2)
    parser.add_argument("--context", type=int, default=262144)
    parser.add_argument("--served-model-name", default="deepseek-v4.1-flash")
    parser.add_argument("--dist-init-addr", default="")
    parser.add_argument("--nnodes", type=int, default=1)
    parser.add_argument("--node-rank", type=int, default=0)
    args, extra = parser.parse_known_args(argv)
    if extra:
        print(f"[tensorfold-vision-fallback] ignoring unrecognized args: {extra}", flush=True)

    prepare_runtime_cache()
    env = dict(RECIPE_ENV)
    if Path(ENGRAM_DIR).is_dir() and any(Path(ENGRAM_DIR).glob("*.safetensors")):
        env["TF_DS_ENGRAM"] = ENGRAM_DIR
    else:
        print(f"[tensorfold-vision-fallback] no Engram tables at {ENGRAM_DIR}: serving degraded",
              flush=True)
    # By design: no VL bias in this arm. Print the expected state loudly so the
    # arm's identity is visible in the serve log next to the engine's own
    # "image tokens route with the text bias" warning.
    _vd = Path(VISION_EXTRA)
    if not (_vd.is_dir() and any(_vd.glob("*.safetensors"))):
        print(f"[tensorfold-vision-fallback] FALLBACK ARM: no VL bias dir at {VISION_EXTRA}; "
              "image tokens will route with the text bias (expected for this arm)",
              flush=True)
    os.environ.update(env)

    master, _, master_port = args.dist_init_addr.partition(":")
    master_port = int(master_port) if master_port else 29551
    model_dir = resolve_checkpoint(args.model)

    cmd = [
        "tensorfold", "serve", model_dir,
        "--tp", str(args.tp),
        "--rank", str(args.node_rank),
        "--host", "0.0.0.0",
        "--port", str(args.port),
        "--context", str(args.context),
        "--parallel", "4",
        "--mtp-drafts", "5",
        "--temperature", "0",
        # Vision is enabled for this arm too; only the routing bias differs.
        "--vision",
        "--no-update-check",
        "--name", args.served_model_name,
    ]
    if args.tp > 1:
        cmd += ["--master", master or "127.0.0.1", "--master-port", str(master_port)]

    print(
        f"[tensorfold-vision-fallback] boot: node_rank={args.node_rank}/{args.tp} "
        f"rendezvous={master or '127.0.0.1'}:{master_port} model={model_dir} "
        f"serving=0.0.0.0:{args.port} context={args.context} engram={env.get('TF_DS_ENGRAM', 'OFF')} "
        f"vision=ON vl_bias={VISION_EXTRA} (fallback arm)",
        flush=True,
    )
    os.execvp(cmd[0], cmd)
    return 0  # unreachable


if __name__ == "__main__":
    sys.exit(main())