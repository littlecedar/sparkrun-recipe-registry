#!/usr/bin/env python3
"""sparkrun -> boot.py launcher shim for the knapcio DSV41 SGLang stack.

The `dsv41-4x-spark:canary-roce` image is built from knapcio's
DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4 repo. Its normal entrypoint is
`python3 -u /opt/dsv41/boot.py run`, which reads every serve parameter from
environment variables (MODEL_PATH, NNODES, NODE_RANK, DIST_INIT_ADDR, ...) and
builds the full `sglang.launch_server` argv itself.

sparkrun's SGLang runtime appends the per-node rendezvous flags
`--dist-init-addr HOST:PORT --nnodes N --node-rank R` to the recipe's serve
command (it assumes the command is `sglang serve ...`). This shim consumes those
flags, maps them onto boot.py's environment, and execs boot.py unchanged -- so
the recipe stays a normal sparkrun recipe and the vendored overlay is untouched.

Usage (rendered by the recipe's `command:` template, with sparkrun's node args
appended):

    python3 /workspace/mods/dsv41-sglang-overlay/launcher.py --boot --port 8888 \
        [--dist-init-addr H:P] [--nnodes N] [--node-rank R]

`--health` forwards to boot.py's health probe (used for a manual check).
"""
from __future__ import annotations

import argparse
import os
import sys

BOOT = "/opt/dsv41/boot.py"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--boot", action="store_true", help="start the engine (default)")
    parser.add_argument("--health", action="store_true", help="run boot.py health probe")
    parser.add_argument("--dist-init-addr", default=None)
    parser.add_argument("--nnodes", default=None)
    parser.add_argument("--node-rank", default=None)
    parser.add_argument("--port", default=None)
    parser.add_argument("--served-model-name", default=None)
    parser.add_argument("--model-path", default=None)
    # Everything else (unused sglang flags, the recipe's own args) is ignored.
    args, _unknown = parser.parse_known_args(argv)

    env = dict(os.environ)
    if args.dist_init_addr:
        env["DIST_INIT_ADDR"] = args.dist_init_addr
    if args.nnodes:
        env["NNODES"] = args.nnodes
    if args.node_rank is not None:
        env["NODE_RANK"] = args.node_rank
    if args.port:
        env["SERVER_PORT"] = args.port
    if args.served_model_name:
        env["SERVED_MODEL_NAME"] = args.served_model_name
    if args.model_path:
        env["MODEL_PATH"] = args.model_path

    if not os.path.isfile(BOOT):
        print(f"launcher: boot.py not found at {BOOT}; is the image dsv41-4x-spark:canary-roce?", file=sys.stderr)
        return 2

    if args.health:
        os.execve(sys.executable, [sys.executable, BOOT, "health"], env)

    print(
        "launcher: boot.py run "
        f"NNODES={env.get('NNODES')} NODE_RANK={env.get('NODE_RANK')} "
        f"DIST_INIT_ADDR={env.get('DIST_INIT_ADDR')} TP={env.get('TP_SIZE')} "
        f"EP={env.get('EP_SIZE')} PORT={env.get('SERVER_PORT')}",
        flush=True,
    )
    os.execve(sys.executable, [sys.executable, "-u", BOOT, "run"], env)
    return 1  # unreachable


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
