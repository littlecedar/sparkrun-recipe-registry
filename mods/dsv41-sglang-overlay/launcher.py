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

Engram shards. The overlay serves the two 203 GB Engram tables from node-local
packed shards, one per rank, under `$DSV41_PACKED_DIR` (the recipe points this at
`/cache/runtime/engram`, the sparkrun-managed runtime cache). Those shards are a
cacheable artifact -- ~47 GiB/rank, derived from the checkpoint -- and must not
live in a user's home directory. They are produced by the image's
`/opt/dsv41/scripts/pack_engram.py`. This shim materializes *this rank's* shards
before booting:

  * rank from `--node-rank` (sparkrun passes it to the head and every worker),
  * if both shards already exist -> nothing to do,
  * otherwise launch the packer **detached** (flock-guarded, one per node) and
    boot immediately. boot.py then reads Engram straight from the checkpoint for
    that boot; the packed shards are picked up on the next boot.

The pack is deliberately not synchronous: a cold pack is minutes long, and
sparkrun only waits ~150 s for the head to open its rendezvous port before it
declares the launch dead. Backgrounding keeps every boot inside that budget;
correctness is unaffected because the checkpoint fallback is exact (see
`adapter/engram_backend.py`: the packed shard is an optional acceleration, and
`row_store.cpp` fails closed if a shard does not match the rank's row range).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

BOOT = "/opt/dsv41/boot.py"
PACKER = "/opt/dsv41/scripts/pack_engram.py"
ENGRAM_LAYERS = (1, 14)


def _pack_env(env: dict[str, str]) -> dict[str, str]:
    """Environment for the background packer (inherit, but pin HOME)."""
    return dict(env, HOME=env.get("HOME") or "/tmp")


def ensure_engram_shards(env: dict[str, str], rank: int | None) -> None:
    """Materialize this rank's packed Engram shards, detached if absent.

    Never raises: a shard it cannot build costs the checkpoint fallback (correct,
    slower), while an exception here would cost the launch.
    """
    packed_dir = env.get("DSV41_PACKED_DIR", "").strip()
    if not packed_dir:
        return
    if rank is None:
        print("launcher: no --node-rank/NODE_RANK; skipping Engram pack "
              "(boot.py will read Engram from the checkpoint)", flush=True)
        return
    try:
        tp = int(env.get("TP_SIZE", "4"))
    except ValueError:
        tp = 4

    missing = [
        layer for layer in ENGRAM_LAYERS
        if not _shard_complete(os.path.join(packed_dir, "engram-l%d-r%dof%d.bin" % (layer, rank, tp)))
    ]
    if not missing:
        print("launcher: Engram shards present for rank %d/%d at %s" % (rank, tp, packed_dir), flush=True)
        return
    if not os.path.isfile(PACKER):
        print("launcher: packer %s missing; booting without packed Engram" % PACKER, flush=True)
        return

    os.makedirs(packed_dir, exist_ok=True)
    lock_path = os.path.join(packed_dir, ".pack.lock")
    log_path = os.path.join(env.get("STATE_PATH", packed_dir), "engram-pack.log")
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        log = open(log_path, "ab", buffering=0)
    except OSError:
        log = subprocess.DEVNULL

    # flock -n: if another pack is already running on this node, leave it alone.
    # nice/ionice: the pack is background work; keep it behind the cold boot's
    # weight load (both compete for the same NVMe and the unified memory pool).
    cmd = [
        "flock", "-n", lock_path,
        "nice", "-n", "10", "ionice", "-c", "3",
        sys.executable, PACKER,
        "--rank", str(rank), "--tp", str(tp), "--out", packed_dir,
    ]
    try:
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=_pack_env(env),
            cwd="/opt/dsv41",
        )
        print("launcher: Engram shards missing for rank %d/%d (layers %s); "
              "packing in the background -> %s (log: %s). Booting on the "
              "checkpoint fallback for this boot." % (rank, tp, missing, packed_dir, log_path), flush=True)
    except OSError as exc:
        print("launcher: could not start Engram packer (%r); booting on the "
              "checkpoint fallback" % (exc,), flush=True)


def _shard_complete(path: str) -> bool:
    """Cheap completeness test: the packer renames the finished file into place,
    so a non-empty target with no `.partial` sibling is the done state."""
    try:
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            return False
        return not os.path.exists(path.replace(".bin", ".partial"))
    except OSError:
        return False


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

    rank = env.get("NODE_RANK")
    ensure_engram_shards(env, int(rank) if rank is not None and str(rank).lstrip("-").isdigit() else None)

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
