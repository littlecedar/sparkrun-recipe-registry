#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""sparkrun -> TensorFold launcher shim for the GLM-5.3 EXL3 3.0bpw TP=4 lane.

`tensorfold serve` is TensorFold's own command. sparkrun's cluster launch is
built around `sglang serve`: it renders the recipe's `command:` template, then
appends the per-node rendezvous flags

    --dist-init-addr HOST:PORT --nnodes N --node-rank R

(sparkrun `runtimes/sglang.py:generate_node_command`). This engine knows none of
them; it wants

    tensorfold serve <MODEL_DIR> --tp 4 --rank R --master HOST --master-port PORT
        --context 1048576 --parallel 4 --mtp-drafts 3 --drafter none

This shim is the adapter. It consumes sparkrun's three flags, maps them onto
TensorFold's spelling, applies the lane's boot-verified configuration
(`attic/glm/AGENTS.md` §"EXL3 3.0bpw", `attic/glm/GLM-5.3-RECOMMENDATIONS.md`
§"A"), resolves the checkpoint, and `execve`s `tensorfold serve`.

The engine is `bertholomus/TensorFold` branch `glm-dsa-tp4` @ `ddfad35`
(TensorFold 0.6.0) — a *different tree* from the 4bpw lane's 106-patch build:
no `cuda/roce.py`, no `--tp 3`, `TF_GLM_COMM`/`TF_ROCE_HCA` do not exist here,
and its transport is plain NCCL (`TF_TP_WORLD` + `--rank/--master/--master-port`,
which sparkrun's environment already configures). `run.sh` gates on that.

Three things this shim is load-bearing for, as in the 4bpw sibling:

* **The rendezvous port.** sparkrun gates the launch on the port it put in
  `--dist-init-addr` (sglang's 25000). This engine's TCPStore binds
  `--master-port` (its own default 29551), so the address's port MUST be passed
  through, or the head opens 29551 while sparkrun polls 25000.
* **The rank.** sparkrun passes `--node-rank` to the head and every worker; the
  container environment carries no rank, so only this shim can set `--rank`.
* **What is writable.** The image sets no cache dirs, so torch's JIT build
  (the sm_121 CUDA extension compile on first start) would land in `~/.cache`
  under a home the container may not be able to write. Both are redirected
  under sparkrun's managed runtime cache so the compile is paid once per host,
  not once per container.

The 1M switches. `TF_GLM_DCP=4` interleaves the cache's positions over the four
ranks (each holds a quarter of every plane), and `TF_GLM_EXTENTS=1` turns the
pool into one span of the window that streams take extents of — together the
documented 1M configuration (needle found at 1,039,064 tokens). DCP must equal
the TP world; that is checked here so a mismatch fails before 273 GB of weights
load, not in the engine after it.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# In-container mount points (sparkrun's orchestration/primitives.py and
# core/runtime_cache.py fix these).
HF_HUB = "/cache/huggingface/hub"
RUNTIME_CACHE = "/cache/runtime"

SERVED_NAME = "GLM-5.3-EXL3-3.0bpw"
MODEL = "bertholomus/GLM-5.3-EXL3-3.0bpw"

# The lane's cluster-wide switches, set with assignment: the image bakes none of
# them, and the mod — not an ambient shell — decides these.
#
# Every rank must agree on TF_GLM_EMBED_SPLIT (engine.py raises on a mismatch
# across ranks). The 1M switches (TF_GLM_KV / TF_GLM_DCP / TF_GLM_EXTENTS) are
# the same class of value but arrive as recipe `defaults:` so `-o` can retune
# them; an env-only switch cannot be overridden once this shim owns the process.
CONSTANT_ENV = {
    "TF_GLM_EMBED_SPLIT": "1",   # the tree's default, stated because the set must be explicit
    "TF_GLM_MTP_REUSE": "2",     # non-default (tree default 0): the lane's value for the MTP-3 chain
    "TENSORFOLD_NO_UPDATE_CHECK": "1",   # no GitHub round-trip during the readiness window
    # Cache locations under sparkrun's managed runtime cache (see the docstring).
    "TORCH_EXTENSIONS_DIR": str(Path(RUNTIME_CACHE) / "torch-extensions"),
    "TRITON_CACHE_DIR": str(Path(RUNTIME_CACHE) / "triton"),
    # The container runs as the ssh user (sparkrun `--user`), which may have no
    # writable home. `--snapshot-dir`'s default is `~/.cache/tensorfold/...`
    # (cli_args.py), expanded in this process, so HOME covers it too.
    "HOME": RUNTIME_CACHE,
}


def lane_env(args: argparse.Namespace) -> dict[str, str]:
    """CONSTANT_ENV plus the four values the recipe's `defaults:` own."""
    env = dict(CONSTANT_ENV)
    env["TF_GLM_KV"] = args.kv
    env["TF_GLM_DCP"] = str(args.dcp)
    env["TF_GLM_EXTENTS"] = str(args.extents)
    return env


def resolve_model_dir(model: str) -> str | None:
    """Resolve `--model` to a local checkpoint directory, or None.

    `{model}` reaches this process as the **prepared on-disk snapshot path** on a
    real launch -- sparkrun rewrites the placeholder for any recipe with a
    `command:` template (`models/runtime.py::bind_runtime_models`), so the
    `is_dir` passthrough below is what carries it; a dry run still prints the
    repo id. A repo id (manual invocation) is resolved in the HF cache mounted
    at /cache/huggingface: derive `models--<org>--<name>/snapshots/<hash>` here
    rather than spelling a snapshot hash in the recipe, so a cache
    re-resolving to a new hash cannot break the recipe.
    """
    direct = Path(model)
    if (direct / "config.json").is_file():
        return str(direct)
    root = Path(HF_HUB) / ("models--" + model.replace("/", "--"))
    ref = root / "refs" / "main"
    if ref.is_file():
        snap = root / "snapshots" / ref.read_text().strip()
        if (snap / "config.json").is_file():
            return str(snap)
    snapshots = sorted((root / "snapshots").glob("*")) if (root / "snapshots").is_dir() else []
    for snap in reversed(snapshots):
        if (snap / "config.json").is_file():
            return str(snap)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--boot", action="store_true", help="accepted for parity with the other lane shims")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--served-model-name", default=SERVED_NAME,
                        help="the id the boot-verified line advertised (`--name GLM-5.3-EXL3-3.0bpw`)")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    # The CLI also accepts 6; this family refuses it (cuda_engine: "splits over
    # 1, 2 or 4 GPUs"), so 6 would only fail after the image/weights are in place.
    parser.add_argument("--tp", type=int, default=4, choices=(1, 2, 4))
    parser.add_argument("--context", type=int, default=1048576,
                        help="prompt plus reply window; the checkpoint's own max_position_embeddings is 1048576")
    parser.add_argument("--parallel", type=int, default=4,
                        help="requests decoded together (the lane's serve line: --parallel 4)")
    parser.add_argument("--mtp-drafts", type=int, default=3,
                        help="MTP drafts a round: the checkpoint's own MTP head, depth 3 (no external drafter)")
    parser.add_argument("--kv", default="q5",
                        help="TF_GLM_KV: q5 = 5-bit latent + fp8 indexer keys (40,824 B/slot at TP4)")
    parser.add_argument("--dcp", type=int, default=4,
                        help="TF_GLM_DCP: decode context parallelism; must equal --tp when > 1")
    parser.add_argument("--extents", type=int, default=1, choices=(0, 1),
                        help="TF_GLM_EXTENTS: 1 = one pool span streams take extents of (the 1M arm)")
    # sparkrun appends its rendezvous flags; capture them here so the shim owns
    # the mapping, and tolerate anything else the runtime may add.
    parser.add_argument("--dist-init-addr", default="")
    parser.add_argument("--nnodes", type=int, default=1)
    parser.add_argument("--node-rank", type=int, default=0)
    args, extra = parser.parse_known_args(argv)
    if extra:
        print(f"[tensorfold-glm53-3bpw-launcher] ignoring unrecognized args: {extra}", flush=True)

    if args.dcp > 1 and args.dcp != args.tp:
        # engine.py: "TF_GLM_DCP=G: decode context parallelism interleaves the
        # cache over every rank, so it must equal the N ranks". Fail before the
        # weight load rather than after it.
        print(
            f"[tensorfold-glm53-3bpw-launcher] TF_GLM_DCP={args.dcp} needs --tp {args.dcp}: "
            f"decode context parallelism interleaves the cache over every rank. "
            f"Set -o dcp={args.tp} (or dcp=1) for this TP world.",
            flush=True,
        )
        return 2

    model_dir = resolve_model_dir(args.model)
    if model_dir is None:
        # Fail closed: an unresolvable checkpoint would have the engine guess,
        # and a boot that serves the wrong weights looks like a working server.
        print(
            f"[tensorfold-glm53-3bpw-launcher] cannot resolve the checkpoint {args.model!r}: not a "
            f"directory with config.json, and no snapshot under {HF_HUB}/models--"
            f"{args.model.replace('/', '--')}. sparkrun prepares {{{{model}}}} for a recipe "
            "with a command: template; a manual run needs a snapshot in the cache.",
            flush=True,
        )
        return 2

    os.environ.update(lane_env(args))

    master, _, master_port = args.dist_init_addr.partition(":")
    master_port = int(master_port) if master_port else 29551

    cmd = ["tensorfold", "serve", model_dir, "--tp", str(args.tp), "--rank", str(args.node_rank)]
    if args.tp > 1:
        cmd += ["--master", master or "127.0.0.1", "--master-port", str(master_port)]
    if args.node_rank == 0:
        # Only rank 0 serves HTTP (the lane's tp4_start.sh: the workers' command
        # stops at --master-port), and it pins greedy sampling, as it did.
        cmd += ["--name", args.served_model_name, "--host", args.host, "--port", str(args.port),
                "--temperature", "0"]
    cmd += [
        "--context", str(args.context),
        "--parallel", str(args.parallel),
        "--mtp-drafts", str(args.mtp_drafts),
        # This family declares no DRAFTER; `none` states that the drafting path
        # is the checkpoint's own MTP head, not a second model.
        "--drafter", "none",
    ]

    print(
        f"[tensorfold-glm53-3bpw-launcher] boot: node_rank={args.node_rank}/{args.tp} "
        f"rendezvous={master or '127.0.0.1'}:{master_port} model={model_dir} "
        f"serving={args.host + ':' + str(args.port) if args.node_rank == 0 else 'no (worker rank)'} "
        f"context={args.context} parallel={args.parallel} mtp_drafts={args.mtp_drafts} "
        f"kv={args.kv} dcp={args.dcp} extents={args.extents}",
        flush=True,
    )
    os.execvp(cmd[0], cmd)
    return 0  # unreachable


if __name__ == "__main__":
    sys.exit(main())
