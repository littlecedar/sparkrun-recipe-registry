#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""sparkrun -> TensorFold launcher shim for the GLM-5.3-Flash EXL3 TP=4 lane.

`tensorfold serve` is TensorFold's own command. sparkrun's cluster launch is
built around `sglang serve`: it renders the recipe's `command:` template, then
appends the per-node rendezvous flags

    --dist-init-addr HOST:PORT --nnodes N --node-rank R

(sparkrun `runtimes/sglang.py:generate_node_command`, which appends exactly
those three). TensorFold knows none of them: it wants

    tensorfold serve <MODEL_DIR> --tp 4 --rank R --master HOST --master-port PORT

This shim is the adapter: it consumes sparkrun's three flags, maps them onto
TensorFold's spelling, applies the lane's production configuration (taken from
the upstream launcher this lane was boot-verified with, MiaAI-Lab's
`GLM-5.3-Flash-EXL3-2x-DGX-Sparks-TensorFold` branch `tp4` @ `d220030`,
`scripts/config.sh` resolved at TP=4 / KV=fp8 / DENSE=q4 / VISION=1), resolves
the checkpoint and the DFlash2 drafter, and runs it as a child so rank 0 can
host the metrics bridge.

Why this is the shipped mechanism (not a custom sparkrun runtime plugin): the
TensorFold DSV41 lane (`mods/tensorfold-dsv41-launcher`) established the
pattern -- a `runtime: sglang` recipe whose `command:` is a Python shim that
consumes sparkrun's node flags and execs a foreign engine. It needs no
out-of-tree sparkrun plugin, and it inherits sparkrun's model distribution,
RDMA/NCCL env probe, runtime cache and readiness machinery for free.

Three things this shim is load-bearing for:

* **The rendezvous port.** sparkrun's native-cluster launch waits for the head
  to open the rendezvous port before it starts the workers, and the port it
  gates on is the one in `--dist-init-addr` (sglang's 25000). TensorFold's
  TCPStore binds `--master-port` (its own default 29551), so the address's port
  MUST be passed through as `--master-port`, or the head opens 29551 while
  sparkrun polls 25000 and the launch is declared dead.
* **The rank.** sparkrun passes `--node-rank` to the head and every worker; the
  container environment carries no rank. Only this shim sees it, so only this
  shim can set `--rank`. Getting it wrong makes every rank think it is rank 0.
* **What is writable.** The image's ENV points TORCH_EXTENSIONS_DIR at
  `/cache/torch_extensions` and TRITON_CACHE_DIR at `/cache/triton` -- paths the
  upstream launcher bind-mounted from the host's per-patch kernel cache, and
  which nothing mounts under sparkrun. Both are redirected under sparkrun's
  managed runtime cache (`/cache/runtime`), so the ~minutes-long CUDA extension
  compile is paid once per host instead of once per container -- or, if the
  directory is unwritable, at all.

Environment. `TF_ROCE_HCA` is the one rank-local value: at TP>2 the upstream
launcher derives it per node (`scripts/nodes.sh` passes the node's active RoCE
devices as *both* `NCCL_IB_HCA` and `TF_ROCE_HCA`), and sparkrun's InfiniBand
probe fills `NCCL_IB_HCA` per node for us -- so the shim copies it rather than
naming a host device. Everything else is cluster-wide and lives in RECIPE_ENV.
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

# In-container mount points (sparkrun's orchestration/primitives.py and
# core/runtime_cache.py fix these).
HF_HUB = "/cache/huggingface/hub"
RUNTIME_CACHE = "/cache/runtime"

SERVED_NAME = "GLM-5.3-Flash-EXL3"
DFLASH2_REPO = "incoai/GLM-5.3-Flash-DFlash2"

# The lane's DFlash2 drafter repo, pinned by the upstream launcher (config.sh
# `DFLASH2_REVISION`) at the revision the boot-verified TP=4 trial served.
DFLASH2_REVISION = "bf582e4eacc1810f76656d1811693ff6c6737d2a"

# Production configuration for this lane: the `export` set of the upstream
# launcher's `scripts/config.sh` @ `d220030` as it resolves for `./start-tp4.sh`
# (TP=4, COMM=roce, KV=fp8, DENSE=q4, VISION=1, PARALLEL=8), verbatim apart from
# `TF_GLM_MAX_QUEUED`, which upstream leaves empty so as *not* to set it (an
# empty value and an unset one are not the same request) -- the trial's own
# `scripts/local.sh` may have set a small value there; this lane leaves the
# scheduler's stock queueing.
#
# Set with assignment (not setdefault): the image bakes nothing here, but the
# point is that the mod, not an ambient shell, decides these. Several change
# what a *default* boot does (TF_GLM_MULTI_WINDOW=64 with TF_ROCE_MAX_KB=1024,
# TF_GLM_CACHE_ENTRIES=32, the TP=4-only prompt split/microbatch/side-stream
# switches), and the memory budget keys (TENSORFOLD_MEMORY_RESERVE_GIB,
# TF_GLM_CACHE_GIB) are what sized the trial's 5,834,752-token KV pool.
RECIPE_ENV = {
    "TENSORFOLD_MEMORY_RESERVE_GIB": "19.6",
    "TENSORFOLD_NO_UPDATE_CHECK": "1",
    "TENSORFOLD_NUCLEUS_UNION": "1",
    "TF_GLM_CACHE_ENTRIES": "32",
    "TF_GLM_CACHE_GIB": "32",
    "TF_GLM_CACHE_SHARE_PCT": "0",
    "TF_GLM_CLEAR_THINKING": "0",
    "TF_GLM_COMM": "roce",
    "TF_GLM_COPY_DRAFTS": "1",
    "TF_GLM_COPY_MAX": "15",
    "TF_GLM_COPY_REPLY_MATCH": "16",
    "TF_GLM_DENSE": "q4",
    "TF_GLM_DFLASH_POLICY": "fnc7:0.3",
    "TF_GLM_DISPLAY_KV_BACKEND": "drm",
    "TF_GLM_DISPLAY_KV_MIB": "0",
    "TF_GLM_EFFORT_TAIL": "0",
    "TF_GLM_EXL3_DEC_ORDER": "0",
    "TF_GLM_EXL3_LOADS": "nc",
    "TF_GLM_FILL_BUDGET_MS": "200",
    "TF_GLM_FILL_DRAFTS": "1",
    "TF_GLM_HC_SPLIT": "1",
    "TF_GLM_KDA_CHUNKED": "1",
    "TF_GLM_KEEP_PER_CHAT": "0",
    "TF_GLM_KEPT_BYTES_GIB": "0",
    "TF_GLM_KV": "fp8",
    "TF_GLM_L2PF": "1",
    "TF_GLM_MSA": "0",
    "TF_GLM_MTP": "auto",
    "TF_GLM_MULTI_LONE": "0",
    "TF_GLM_MULTI_PREFILL": "1",
    "TF_GLM_MULTI_WINDOW": "64",
    "TF_GLM_PREFILL_OVERLAP": "2",
    "TF_GLM_PREFILL_ROWS": "4096",
    "TF_GLM_PROMPT_MICROBATCH": "1",
    "TF_GLM_PROMPT_OWN_FRONT": "1",
    "TF_GLM_PROMPT_PARTIALS": "fp32",
    "TF_GLM_SHARED_PREFIX": "1",
    "TF_GLM_SIDE": "1",
    "TF_GLM_STREAM_SMOOTH": "1",
    "TF_GLM_STREAM_SMOOTH_MS": "400",
    "TF_GLM_WIDE_GRAPHS": "16",
    "TF_ROCE_MAX_KB": "1024",
    "TF_ROCE_WAIT_S": "300",
    # Cache locations under sparkrun's managed runtime cache (see the docstring).
    "TORCH_EXTENSIONS_DIR": str(Path(RUNTIME_CACHE) / "torch-extensions"),
    "TRITON_CACHE_DIR": str(Path(RUNTIME_CACHE) / "triton"),
    # The container runs as the ssh user (sparkrun `--user`), which may have no
    # writable home. Point HOME at the managed cache so nothing the engine
    # touches on the serve path lands in a read-only `/`.
    "HOME": RUNTIME_CACHE,
}


def recipe_env(process_env: dict[str, str]) -> dict[str, str]:
    """RECIPE_ENV plus the one per-node value: `TF_ROCE_HCA` from the probe.

    At TP>2 the upstream launcher passes the node's active RoCE devices to the
    engine as `TF_ROCE_HCA`, and to NCCL as `NCCL_IB_HCA` -- the same string
    (`scripts/nodes.sh`, `nccl_env_n`). sparkrun's InfiniBand probe fills
    `NCCL_IB_HCA` per node, so it is the portable source; a recipe must never
    name a host device (`recipes/glm/README.md`). Unset when the probe found
    nothing: the engine then derives its own device list, which is what an
    unprobed host would do anyway.
    """
    env = dict(RECIPE_ENV)
    hcas = process_env.get("NCCL_IB_HCA", "").strip()
    if hcas:
        env["TF_ROCE_HCA"] = hcas
    return env


def resolve_model_dir(model: str) -> str | None:
    """Resolve `--model` to a local checkpoint directory, or None.

    `{model}` reaches this process as the **prepared on-disk snapshot path** on a
    real launch -- sparkrun rewrites the placeholder for any recipe with a
    `command:` template (`models/runtime.py::bind_runtime_models`), so the
    `is_dir` passthrough below is what carries it; a dry run still prints the repo
    id. A repo id (manual invocation, or `-o model=...`) is resolved in the HF
    cache mounted at /cache/huggingface: derive
    `models--<org>--<name>/snapshots/<hash>` here rather than spelling a snapshot
    hash in the recipe, so a cache re-resolving to a new hash cannot break the
    recipe.
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


def resolve_drafter(repo: str, revision: str = "") -> str | None:
    """Resolve the drafter repo to a local snapshot directory, or None.

    `--drafter` takes a repo id or a directory, but the boot-verified line hands
    the engine the *snapshot directory* (upstream `start.sh:snapshot()`, checked
    on every Spark): the rank reads it offline, whatever the Hub's `main` is now.
    An explicit *revision* is required to be present -- falling back to another
    snapshot would serve a different drafter than the one the recipe pinned, and
    the acceptance figures are per-drafter. Without one, `refs/main` (which a
    SHA-keyed fetch does not write) and then the newest snapshot are used, so a
    cache populated by a plain `hf download` still resolves.
    """
    direct = Path(repo)
    if (direct / "config.json").is_file():
        return str(direct)
    root = Path(HF_HUB) / ("models--" + repo.replace("/", "--"))
    snapshots = sorted((root / "snapshots").glob("*"), reverse=True) if (root / "snapshots").is_dir() else []
    ref = root / "refs" / "main"
    if revision:
        wanted = [root / "snapshots" / revision]
    else:
        wanted = [root / "snapshots" / ref.read_text().strip()] if ref.is_file() else []
    for snap in wanted + ([] if revision else snapshots):
        if (snap / "config.json").is_file():
            return str(snap)
    return None


def served_model_name(value: str) -> str:
    """Normalize a `--served-model-name` that arrived as a filesystem path.

    sparkrun rewrites `{model}` -- and a `--served-model-name {model}` rendered
    from the same placeholder -- to the prepared on-disk snapshot path on any
    real launch of a recipe with a `command:` template, so the engine would
    otherwise advertise a path as the served model id. Recover the repo id from
    the HF cache layout, else fall back to the directory basename. A non-path
    value is returned unchanged.
    """
    if not os.path.isabs(value):
        return value
    for segment in os.path.normpath(value).split(os.sep):
        if segment.startswith("models--"):
            org, _, name = segment[len("models--"):].partition("--")
            if org and name:
                return org + "/" + name
    return os.path.basename(value.rstrip("/")) or value


# The bridge's log lines below; the boot lines keep their own literal.
TAG = "[tensorfold-glm-launcher]"


def parse_tensorfold_metrics(text: str) -> dict[str, float]:
    """`tensorfold:*` lines of a /metrics body -> name -> float (pure)."""
    out: dict[str, float] = {}
    for line in text.splitlines():
        if not line.startswith("tensorfold:"):
            continue
        name, _, raw = line.partition(" ")
        try:
            # Labels dropped: the bridge reads unlabeled counters, and a
            # labelled series must not shadow its family name.
            out[name.split("{", 1)[0]] = float(raw)
        except ValueError:
            pass
    return out


def build_metric_lines(
    vals: dict[str, float],
    prev_gen: float | None,
    prev_t: float | None,
    now: float,
) -> tuple[list[str], float | None, float | None]:
    """Scraper-shaped lines for one /metrics sample and the next delta state (pure).

    Only what the sample actually carried is printed: a missing counter emits no
    line, never a placeholder zero — invented zeros would corrupt accounting.
    Throughput needs two samples of `tensorfold:generation_tokens_total`.
    """
    lines: list[str] = []
    gen = vals.get("tensorfold:generation_tokens_total")
    if gen is not None and prev_gen is not None and prev_t is not None and now > prev_t:
        tps = (gen - prev_gen) / (now - prev_t)
        lines.append(f"Avg generation throughput: {tps:.2f} tokens/s")
        lines.append(f"gen throughput (token/s): {tps:.2f}")
    running = vals.get("tensorfold:requests_running")
    if running is not None:
        lines.append(f"Running: {int(running)} reqs")
    waiting = vals.get("tensorfold:requests_waiting")
    if waiting is not None:
        lines.append(f"Waiting: {int(waiting)} reqs")
    return lines, gen, now


def bridge_loop(
    port: int,
    period_s: float = 5.0,
    backoff_cap_s: float = 30.0,
    pre_ready_deadline_s: float = 3600.0,
) -> None:
    """Poll this rank's /metrics and emit scraper-shaped lines. Fail-soft.

    The engine's HTTP listener binds only after the weight load (2715 s on the
    GLM-5.3-Flash 4bpw arm), so connection refusals are the EXPECTED state for
    most of the boot: retry with backoff (5 s doubling to 30 s) until the port
    answers once. After first contact, N consecutive failures end the thread;
    before it, an env-configurable deadline (TF_METRICS_BRIDGE_DEADLINE_S,
    default 3600 s) bounds the wait. It never touches the serve.
    """
    import time
    import urllib.request

    deadline = time.time() + pre_ready_deadline_s
    prev_gen: float | None = None
    prev_t: float | None = None
    delay = period_s
    reached = False
    announced = False
    misses_after_reach = 0
    while True:
        time.sleep(delay)
        try:
            body = urllib.request.urlopen(
                f"http://127.0.0.1:{port}/metrics", timeout=5
            ).read().decode()
        except Exception as exc:  # noqa: BLE001 - fail-soft by design
            if reached:
                misses_after_reach += 1
                if misses_after_reach >= 3:
                    print(
                        f"{TAG} metrics bridge disabled after "
                        f"{misses_after_reach} post-contact failures: {exc}",
                        flush=True,
                    )
                    return
            elif time.time() > deadline:
                print(
                    f"{TAG} metrics bridge disabled: /metrics "
                    f"never answered before the deadline: {exc}",
                    flush=True,
                )
                return
            delay = min(delay * 2, backoff_cap_s)
            continue
        reached = True
        misses_after_reach = 0
        delay = period_s
        now = time.time()
        vals = parse_tensorfold_metrics(body)
        if not announced:
            # Once per boot, after the first body: the matched names are the only
            # evidence the scrape keys fit this engine image. An empty list means
            # this image publishes no `tensorfold:*` series, and the bridge's cells
            # stay blank rather than inventing zeros.
            print(f"{TAG} metrics bridge: matched {sorted(vals)}", flush=True)
            announced = True
        lines, prev_gen, prev_t = build_metric_lines(vals, prev_gen, prev_t, now)
        for line in lines:
            print(line, flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--boot", action="store_true", help="accepted for parity with the other lane shims")
    parser.add_argument("--model", default="Mia-AiLab/GLM-5.3-Flash-EXL3-4bpw-TensorFold")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--tp", type=int, default=4)
    parser.add_argument("--context", type=int, default=1048576)
    parser.add_argument("--max-tokens", type=int, default=32768,
                        help="reply budget when a request sets none (upstream MAX_TOKENS)")
    parser.add_argument("--parallel", type=int, default=8,
                        help="requests decoded together (upstream: 8 at TP>2 with DFlash2)")
    parser.add_argument("--vision", type=int, default=1, choices=(0, 1),
                        help="1 enables image input (upstream VISION=1, the boot-verified default)")
    parser.add_argument("--served-model-name", default=SERVED_NAME)
    parser.add_argument("--drafter-repo", default=DFLASH2_REPO,
                        help="DFlash2 repo id or directory ('none': no drafter)")
    parser.add_argument("--drafter-revision", default="")
    # sparkrun appends its rendezvous flags; capture them here so the shim owns
    # the mapping, and tolerate anything else the runtime may add.
    parser.add_argument("--dist-init-addr", default="")
    parser.add_argument("--nnodes", type=int, default=1)
    parser.add_argument("--node-rank", type=int, default=0)
    args, extra = parser.parse_known_args(argv)
    if extra:
        print(f"[tensorfold-glm-launcher] ignoring unrecognized args: {extra}", flush=True)

    os.environ.update(recipe_env(dict(os.environ)))

    model_dir = resolve_model_dir(args.model)
    if model_dir is None:
        # Fail closed: an unresolvable checkpoint would have the engine guess,
        # and a boot that serves the wrong weights looks like a working server.
        print(
            f"[tensorfold-glm-launcher] cannot resolve the checkpoint {args.model!r}: not a "
            f"directory with config.json, and no snapshot under {HF_HUB}/models--"
            f"{args.model.replace('/', '--')}. sparkrun prepares {{{{model}}}} for a recipe "
            "with a command: template; a manual run needs a snapshot in the cache.",
            flush=True,
        )
        return 2

    drafter = "auto"
    if args.drafter_repo and args.drafter_repo != "none":
        resolved = resolve_drafter(args.drafter_repo, args.drafter_revision)
        if resolved is None:
            # Fail closed: the boot-verified numbers are DFlash2's (76.6 %
            # acceptance); serving without it is a different, unmeasured arm.
            print(
                f"[tensorfold-glm-launcher] no snapshot for the drafter {args.drafter_repo!r}"
                f"{' @ ' + args.drafter_revision if args.drafter_revision else ''} under {HF_HUB}: "
                "the recipe declares it in defaults (speculative_draft_model) so sparkrun "
                "distributes it to every node -- pass --drafter-repo none to serve without it.",
                flush=True,
            )
            return 2
        drafter = resolved

    master, _, master_port = args.dist_init_addr.partition(":")
    master_port = int(master_port) if master_port else 29551

    cmd = ["tensorfold", "serve", model_dir, "--tp", str(args.tp), "--rank", str(args.node_rank)]
    if args.tp > 1:
        cmd += ["--master", master or "127.0.0.1", "--master-port", str(master_port)]
    if args.node_rank == 0:
        # Only rank 0 serves HTTP (upstream start.sh: the workers' command stops
        # at --master-port; no --name/--host/--port).
        cmd += ["--name", served_model_name(args.served_model_name), "--host", args.host, "--port", str(args.port)]
    cmd += [
        "--drafter", drafter,
        "--context", str(args.context),
        "--parallel", str(args.parallel),
        "--max-tokens", str(args.max_tokens),
    ]
    if args.vision:
        cmd.append("--vision")

    print(
        f"[tensorfold-glm-launcher] boot: node_rank={args.node_rank}/{args.tp} "
        f"rendezvous={master or '127.0.0.1'}:{master_port} model={model_dir} drafter={drafter} "
        f"serving={'0.0.0.0:' + str(args.port) if args.node_rank == 0 else 'no (worker rank)'} "
        f"context={args.context} parallel={args.parallel} kv={RECIPE_ENV['TF_GLM_KV']} "
        f"comm={RECIPE_ENV['TF_GLM_COMM']} roce_hca={os.environ.get('TF_ROCE_HCA', 'engine default')}",
        flush=True,
    )
    # The engine runs as a CHILD (not execve) so rank 0 can host the metrics
    # bridge thread: /metrics carries the tensorfold:* counters the sparkrun
    # monitor scraper wants, but the engine logs no line shapes it matches.
    # TF_METRICS_BRIDGE=0 disables the bridge without a repo edit. The shim
    # relays SIGTERM/SIGINT and exits with the engine's code, so container
    # stop semantics are unchanged.
    proc = subprocess.Popen(cmd)
    if args.node_rank == 0 and os.environ.get("TF_METRICS_BRIDGE", "1") != "0":
        threading.Thread(
            target=bridge_loop,
            kwargs={
                "port": args.port,
                "pre_ready_deadline_s": float(
                    os.environ.get("TF_METRICS_BRIDGE_DEADLINE_S", "3600")
                ),
            },
            daemon=True,
        ).start()

    def _forward(signum, _frame):
        proc.send_signal(signum)

    signal.signal(signal.SIGTERM, _forward)
    signal.signal(signal.SIGINT, _forward)
    return proc.wait()


if __name__ == "__main__":
    sys.exit(main())