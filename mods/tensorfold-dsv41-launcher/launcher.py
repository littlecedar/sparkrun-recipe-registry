#!/usr/bin/env python3
"""sparkrun -> TensorFold launcher shim for the DSV41 TP=2 lane.

`tensorfold serve` is TensorFold's own command. sparkrun's cluster launch is
built around `sglang serve`: it renders the recipe's `command:` template, then
appends the per-node rendezvous flags

    --dist-init-addr HOST:PORT --nnodes N --node-rank R

(see sparkrun `runtimes/sglang.py:generate_node_command`, which appends exactly
those three). TensorFold knows none of them: it wants

    tensorfold serve <MODEL_DIR> --tp 2 --rank R --master HOST --master-port PORT

This shim is the adapter. It consumes sparkrun's three flags, maps them onto
TensorFold's spelling, applies the production configuration, resolves the
checkpoint, and `execve`s `tensorfold serve`.

Why this is the shipped mechanism (not a custom sparkrun runtime plugin): the
knapcio DSV41 lane in this directory already established the pattern -- a
`runtime: sglang` recipe whose `command:` is a Python shim that consumes
sparkrun's node flags and execs a foreign engine. It needs no out-of-tree
sparkrun plugin, and it inherits sparkrun's model distribution, RDMA/NCCL env
probe, runtime cache and readiness machinery for free. See AGENTS.md.

Two things this shim is load-bearing for:

* **The rendezvous port.** sparkrun's native-cluster launch waits for the head
  to open the rendezvous port before it starts the workers, and the port it
  gates on is the one in `--dist-init-addr` (default 25000). TensorFold's
  TCPStore binds `--master-port` (its own default is 29551), so the address's
  port MUST be passed through as `--master-port`, or the head opens 29551 while
  sparkrun polls 25000 and the launch is declared dead.
* **The rank.** sparkrun passes `--node-rank` to the head and every worker; the
  container environment carries no rank. Only this shim sees it, so only this
  shim can set `--rank`. Getting it wrong makes both ranks think they are rank 0.

Cache locations. TensorFold compiles its CUDA extensions on first start and can
keep each rank's loaded weights in a single file (`TF_DS_RANK_CACHE`, ~106 GiB a
rank). Both are cacheable and belong under sparkrun's managed runtime cache,
mounted at `/cache/runtime`, not in the container's (ephemeral) home. This shim
points TORCH_EXTENSIONS_DIR, the rank cache, and the token-map cache there.

Engram. The two Engram embedding tables are ~95 GiB each and are NOT in the EXL3
checkpoint; TensorFold reads them from the original DeepSeek shards 47/48. They
live alongside the HF cache at `/cache/huggingface/hub/dsv41-engram` (see the
recipe README's pre-warm step). If that directory is absent the engine still
loads and serves, with a warning and degraded output -- the shim does not fail
closed on it, it just does not set TF_DS_ENGRAM so the engine can say so.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# In-container mount points (sparkrun's orchestration/primitives.py and
# core/runtime_cache.py fix these).
HF_HUB = "/cache/huggingface/hub"
RUNTIME_CACHE = "/cache/runtime/tensorfold"
ENGRAM_DIR = os.environ.get("TENSORFOLD_ENGRAM_DIR", "/cache/huggingface/hub/dsv41-engram")


def resolve_engram_dir(model_dir: str | None = None) -> str | None:
    """The directory the engine should read the Engram tables from, or None.

    Three homes, in order:

    0. **A combined local repo** (``tools/build-dsv41-combined.py``): a single HF
       directory holding both the EXL3 weights and the two upstream Engram
       tables under an ``engram/`` subdir. When ``--model`` points at such a
       repo, the tables live at ``<model_dir>/engram`` and are found here -- no
       separate fetch, no pre-warm step. The subdir (not the root) is used on
       purpose: the engine globs ``*.safetensors`` non-recursively, so handing it
       the repo root would make it scan the 39 EXL3 shards.
    1. ``TENSORFOLD_ENGRAM_DIR`` / the default ``/cache/huggingface/hub/dsv41-engram``
       -- where ``mods/dsv41-engram-fetch`` (or a hand pre-warm) writes.
    2. A sparkrun-*distributed* Engram repo: when the recipe declares
       ``manateelazycat/DeepSeek-V4.1-Flash-TensorFold-Engram`` (or any repo
       carrying the tables) in ``distribution_config.models``, sparkrun
       downloads it on the head and rsyncs it to every worker, and it lands here
       as a normal HF-cache model dir. This is the cheap path on slow links: one
       download, many nodes. Its tensors sit under ``source/`` in that repo, so
       both the snapshot root and its ``source/`` subdir are accepted; the engine
       globs the directory non-recursively, so the dir handed to it must hold the
       ``*.safetensors`` directly.
    """
    if model_dir:
        cand = Path(model_dir) / "engram"
        if cand.is_dir() and any(cand.glob("*.safetensors")):
            return str(cand)
    if Path(ENGRAM_DIR).is_dir() and any(Path(ENGRAM_DIR).glob("*.safetensors")):
        return ENGRAM_DIR
    root = Path(HF_HUB) / "models--manateelazycat--DeepSeek-V4.1-Flash-TensorFold-Engram"
    ref = root / "refs" / "main"
    snapshots = []
    if ref.is_file():
        snapshots.append(root / "snapshots" / ref.read_text().strip())
    if (root / "snapshots").is_dir():
        snapshots += sorted((root / "snapshots").glob("*"), reverse=True)
    for snap in snapshots:
        for cand in (snap / "source", snap):
            if cand.is_dir() and any(cand.glob("*.safetensors")):
                return str(cand)
    return None

# The engine reads EXL3 only (family `deepseek_v41`: QUANT_METHODS = {"cuda":
# ("exl3",)}), so this is the Mia-AiLab EXL3 2.9bpw conversion, not the official
# MXFP4 checkpoint.
MODEL_ORG, MODEL_NAME = "Mia-AiLab", "DeepSeek-V4.1-Flash-EXL3-2.9bpw"

# Production configuration for this lane, matching the upstream served line
# (TensorFold tools/dsv41/REPORT.md section 7). Env is set with assignment (not
# setdefault): the image bakes nothing, but the point is that the recipe, not an
# ambient shell, decides these.
RECIPE_ENV = {
    # Bounded decoder replay (DeepSeek's deployment mode; the engine's own
    # default is exact prefill, which is slower and can OOM at 128K).
    "TF_DS_REPLAY": "1",
    # Prefill chunk, 2048 rows: upstream's served value.
    "TF_DS_PREFILL_CHUNK": "2048",
    # The per-rank weight cache: written on the first boot (~106 GiB a rank,
    # ~330 s), read on every later boot. Under the managed runtime cache.
    "TF_DS_RANK_CACHE": str(Path(RUNTIME_CACHE) / "rank-cache"),
    "TF_DS_RANK_CACHE_READERS": "32",
    # Warm the CUDA graphs at the served sequence lengths (upstream's list).
    "TF_DS_WARM_LENGTHS": "1,17,33,131,514,1024,2113",
    # JIT build directory: persistent, so the ~minutes-long first compile is paid
    # once per host, not once per container.
    "TORCH_EXTENSIONS_DIR": str(Path(RUNTIME_CACHE) / "torch-extensions"),
    # Host-side token map for Engram hashing (built once from tokenizer.json).
    "TF_DS_TOKEN_MAP": str(Path(RUNTIME_CACHE) / "token_map.json"),
    # The container runs as the ssh user (sparkrun `--user`), which may have no
    # writable home. Point HOME at the managed cache so the engine's update-check
    # cache and snapshot dir do not land in a read-only `/`.
    "HOME": RUNTIME_CACHE,
}


def resolve_checkpoint(repo: str) -> str:
    """Resolve the EXL3 checkpoint to a local snapshot directory.

    `{model}` reaches this process as the **prepared on-disk snapshot path** on a
    real launch -- sparkrun rewrites the placeholder for any recipe with a
    `command:` template (`models/runtime.py::bind_runtime_models`), so the
    `is_dir` passthrough below is what carries it; a dry run still prints the repo
    id. A repo id (manual invocation, or `-o model=...`) is resolved in the HF
    cache mounted at /cache/huggingface: derive
    `models--<org>--<name>/snapshots/<hash>` here rather than spelling a snapshot
    hash in the recipe, so a cache re-resolving to a new hash cannot break the
    recipe. An absolute path (a pre-placed model) is used as-is.
    """
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
    # Nothing local: hand the id back and let the engine try its own resolution.
    return repo


def prepare_runtime_cache() -> None:
    for sub in ("", "rank-cache", "torch-extensions"):
        Path(RUNTIME_CACHE, sub).mkdir(parents=True, exist_ok=True)


def served_model_name(value: str) -> str:
    """Normalize a `--served-model-name` that arrived as a filesystem path.

    sparkrun rewrites `{model}` -- and a `--served-model-name {model}` rendered
    from the same placeholder -- to the prepared on-disk snapshot path on any real
    launch of a recipe with a `command:` template
    (`models/runtime.py::bind_runtime_models`), so the engine would otherwise
    advertise a path as the served model id. Recover the repo id from the HF cache
    layout, else fall back to the directory basename. A non-path value is returned
    unchanged.
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
    parser.add_argument("--boot", action="store_true", help="accepted for parity with the knapcio shim")
    parser.add_argument("--model", default=f"{MODEL_ORG}/{MODEL_NAME}")
    parser.add_argument("--port", type=int, default=18891)
    parser.add_argument("--tp", type=int, default=2)
    parser.add_argument("--context", type=int, default=262144)
    parser.add_argument("--served-model-name", default="deepseek-v4.1-flash")
    # sparkrun appends its rendezvous flags; capture them here so the shim owns
    # the mapping, and tolerate anything else the runtime may add.
    parser.add_argument("--dist-init-addr", default="")
    parser.add_argument("--nnodes", type=int, default=1)
    parser.add_argument("--node-rank", type=int, default=0)
    args, extra = parser.parse_known_args(argv)
    if extra:
        print(f"[tensorfold-launcher] ignoring unrecognized args: {extra}", flush=True)

    prepare_runtime_cache()
    env = dict(RECIPE_ENV)
    # The checkpoint must be resolved before the Engram tables, because a
    # combined local repo carries the tables in a subdir of the model dir.
    model_dir = resolve_checkpoint(args.model)
    engram = resolve_engram_dir(model_dir)
    if engram:
        env["TF_DS_ENGRAM"] = engram
    else:
        print(
            f"[tensorfold-launcher] no Engram tables at {ENGRAM_DIR} (or a combined "
            "repo's engram/ subdir, or a distributed Engram repo): serving degraded "
            "(see recipes/ds4/README.md for the pre-warm step)",
            flush=True,
        )
    os.environ.update(env)

    master, _, master_port = args.dist_init_addr.partition(":")
    master_port = int(master_port) if master_port else 29551

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
        # No outbound version check at boot: the container has no reason to phone
        # home, and the flag avoids a write into HOME on the serve path.
        "--no-update-check",
        "--name", served_model_name(args.served_model_name),
    ]
    if args.tp > 1:
        cmd += ["--master", master or "127.0.0.1", "--master-port", str(master_port)]

    print(
        f"[tensorfold-launcher] boot: node_rank={args.node_rank}/{args.tp} "
        f"rendezvous={master or '127.0.0.1'}:{master_port} model={model_dir} "
        f"serving=0.0.0.0:{args.port} context={args.context} engram={env.get('TF_DS_ENGRAM', 'OFF')}",
        flush=True,
    )
    os.execvp(cmd[0], cmd)
    return 0  # unreachable


if __name__ == "__main__":
    sys.exit(main())