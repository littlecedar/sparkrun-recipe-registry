#!/usr/bin/env python3
"""sparkrun -> TensorFold launcher shim for the Kolibri-1 block-drafter arm.

`tensorfold serve` is TensorFold's own command. sparkrun's launch is built
around `sglang serve`: it renders the recipe's `command:` template and, on a
multi-node launch, appends the per-node rendezvous flags

    --dist-init-addr HOST:PORT --nnodes N --node-rank R

This shim consumes them and maps them onto TensorFold's spelling
(`--tp/--rank/--master/--master-port`), then execs `tensorfold serve`. Same
mechanism as `mods/tensorfold-dsv41-launcher` (the shipped ds4 TP=2 lane): a
`runtime: sglang` recipe whose command is a shim gets sparkrun's distribution,
runtime cache and readiness for free, with no out-of-tree runtime plugin.

Why this arm needs a shim at all: the drafter is not an engine flag named in
the model card. TensorFold reads it from `TENSORFOLD_KOLIBRI_DRAFTER`, a
directory of a *separate* HF repo, so something has to resolve that repo's
prepared snapshot on the node and export it before the engine starts. Doing it
here also makes a missing drafter a hard failure instead of a silent
no-speculation serve that still answers correctly at half the speed.

sparkrun's `speculative_draft_model` defaults reach this process as the repo id
(only `{model}` itself is rebound to a prepared path), and
`speculative_draft_model_revision` reaches it as the pin sparkrun actually
distributed -- so the pair is resolved against that revision and never against
the repo's moving `main`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# In-container mount points (sparkrun's orchestration/primitives.py and
# core/runtime_cache.py fix these).
HF_HUB = "/cache/huggingface/hub"
RUNTIME_CACHE = "/cache/runtime/kolibri-tensorfold"


def resolve_snapshot(spec: str, revision: str = "") -> str | None:
    """A local directory for *spec* (a prepared path or a repo id), or None.

    `{model}` arrives here as the prepared snapshot path on a real launch, so
    the `is_dir` passthrough is what carries it; a repo id (a dry run, or an
    `-o model=...` override) is resolved in the HF cache. A pinned revision is
    tried *alone*: a SHA-keyed download writes no `refs/` entry, and falling
    back to another snapshot would serve a checkpoint the recipe never pinned.
    """
    direct = Path(spec)
    if direct.is_dir():
        return str(direct)
    root = Path(HF_HUB) / ("models--" + spec.replace("/", "--"))
    candidates: list[Path] = []
    if revision:
        candidates.append(root / "snapshots" / revision)
    else:
        ref = root / "refs" / "main"
        if ref.is_file():
            candidates.append(root / "snapshots" / ref.read_text().strip())
        if (root / "snapshots").is_dir():
            candidates.extend(sorted((root / "snapshots").glob("*"), reverse=True))
    for snap in candidates:
        if (snap / "config.json").is_file():
            return str(snap)
    return None


def is_block_drafter(path: str) -> bool:
    """True when *path* is a block-drafter release: `config.json` names `drafter.block`.

    The engine's own test is the same shape
    (`families/kolibri1/cuda/block_drafter.py::is_block`); anything else is
    loaded as a plain chain drafter or not at all, so this arm would then serve
    without the drafter it exists for.
    """
    try:
        data = json.loads((Path(path) / "config.json").read_text())
    except (OSError, ValueError):
        return False
    return isinstance(data.get("drafter"), dict) and "block" in data["drafter"]


def served_model_name(value: str) -> str:
    """Recover the repo id from a `--served-model-name` that arrived as a path.

    sparkrun rebinds `{model}` -- and a flag rendered from that placeholder --
    to the prepared on-disk snapshot path on a real launch, so the engine would
    otherwise advertise a cache path as its model id.
    """
    if not os.path.isabs(value):
        return value
    for segment in os.path.normpath(value).split(os.sep):
        if segment.startswith("models--"):
            org, _, name = segment[len("models--"):].partition("--")
            if org and name:
                return org + "/" + name
    return os.path.basename(value.rstrip("/")) or value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default="Aleph-Alpha/Kolibri-1")
    parser.add_argument("--port", type=int, default=8000)
    # sparkrun warns unless the command spends the model_revision pin, and the
    # engine has no --revision: the pin is spent here instead, as a check that
    # the prepared path IS the pinned snapshot (it arrives as {model}).
    parser.add_argument("--revision", default="")
    parser.add_argument("--tp", type=int, default=1)
    parser.add_argument("--served-model-name", default="Aleph-Alpha/Kolibri-1")
    # Prompt + reply window; unset leaves the engine its own config cap.
    parser.add_argument("--context", type=int, default=None)
    # The drafter repo id + the revision sparkrun distributed with it.
    parser.add_argument("--drafter", required=True)
    parser.add_argument("--drafter-revision", default="")
    # GB10 working point from the Myric/sglang precedent: few slots, one pool.
    parser.add_argument("--parallel", type=int, default=6)
    # sparkrun appends its rendezvous flags; capture them here so the shim owns
    # the mapping, and tolerate anything else the runtime may add.
    parser.add_argument("--dist-init-addr", default="")
    parser.add_argument("--nnodes", type=int, default=1)
    parser.add_argument("--node-rank", type=int, default=0)
    args, extra = parser.parse_known_args(argv)
    if extra:
        print(f"[kolibri-drafter] ignoring unrecognized args: {extra}", flush=True)

    model_dir = resolve_snapshot(args.model)
    if model_dir is None:
        print(f"[kolibri-drafter] cannot resolve model {args.model!r} in {HF_HUB}; "
              "refusing to start", flush=True)
        return 2
    if args.revision and Path(model_dir).name != args.revision:
        print(f"[kolibri-drafter] model dir {model_dir} is not the pinned "
              f"revision {args.revision}; refusing to serve a different "
              "checkpoint than the recipe pins", flush=True)
        return 2
    drafter_dir = resolve_snapshot(args.drafter, args.drafter_revision)
    if drafter_dir is None:
        print(f"[kolibri-drafter] cannot resolve drafter {args.drafter!r} "
              f"@{args.drafter_revision or 'main'} in {HF_HUB}; this arm exists "
              "only with a drafter, refusing to serve without one", flush=True)
        return 2
    if not is_block_drafter(drafter_dir):
        print(f"[kolibri-drafter] {drafter_dir} is not a block-drafter release "
              "(config.json has no drafter.block); refusing to start", flush=True)
        return 2

    for sub in ("", "torch-extensions"):
        Path(RUNTIME_CACHE, sub).mkdir(parents=True, exist_ok=True)

    env = {
        "TENSORFOLD_KOLIBRI_DRAFTER": drafter_dir,
        "TORCH_EXTENSIONS_DIR": str(Path(RUNTIME_CACHE) / "torch-extensions"),
        # The container runs as the ssh user, which may have no writable home;
        # keep the engine's own caches off a read-only `/`.
        "HOME": RUNTIME_CACHE,
    }
    os.environ.update(env)

    master, _, master_port = args.dist_init_addr.partition(":")
    cmd = [
        "tensorfold", "serve", model_dir,
        "--name", served_model_name(args.served_model_name),
        "--host", "0.0.0.0",
        "--port", str(args.port),
        "--parallel", str(args.parallel),
        "--tp", str(args.tp),
        "--rank", str(args.node_rank),
        # No outbound version check at boot: the container has no reason to
        # phone home, and the flag avoids a write into HOME on the serve path.
        "--no-update-check",
    ]
    if args.tp > 1:
        cmd += ["--master", master or "127.0.0.1",
                "--master-port", str(int(master_port) if master_port else 29551)]
    if args.context:
        cmd += ["--context", str(args.context)]

    print(f"[kolibri-drafter] boot: node_rank={args.node_rank}/{args.tp} "
          f"model={model_dir} drafter={drafter_dir} serving=0.0.0.0:{args.port} "
          f"parallel={args.parallel}", flush=True)
    os.execvp(cmd[0], cmd)
    return 0  # unreachable


if __name__ == "__main__":
    sys.exit(main())
