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

# ---------------------------------------------------------------------------
# Recipe-owned environment.
#
# The recipe's `env:` block is deliberately thin: it carries only the external
# checkpoint path and the TP degree. Everything else the engine needs is the
# production configuration for this stack, and it lives here so the recipe does
# not have to spell engine internals (and so the values travel with the mod
# rather than with each recipe that uses it). These OVERRIDE (not setdefault):
# the image bakes several of them into its ENV (STATE_PATH=/state,
# DSV41_CACHE_GIB=16, PYTORCH_CUDA_ALLOC_CONF=...True, SGLANG_RUST_BUILD_MODE,
# OFFLOAD_MODE), and those live in the launcher's process env, so a setdefault
# would let the image value win and silently undo the production config
# (unwritable /state, the NaN-logits allocator mode). The keys here are disjoint
# from the recipe-owned MODEL_PATH / DSV41_SOURCE / TP_SIZE, so those pass through.
#
# REDUNDANT vars (recipe value == runtime default) are NOT here and are NOT in
# the recipe: SKIP_SMOKE(0), WARMUP(1), HOST(0.0.0.0), SERVED_MODEL_NAME,
# SPARK_PREFILL_TP_MIN_CONTEXT(32768), SPARK_PREFILL_TP_MIN_ROWS(1024),
# DSV41_FAST_LOAD_TP_SLICE(auto), DSV41_FAST_LOAD_INFLIGHT_GB(6).
#
# NCCL_NET / NCCL_IB_HCA / NCCL_IB_GID_INDEX / NCCL_IB_DISABLE / NCCL_CROSS_NIC
# and B12X_ROCE_HCA are also absent on purpose: sparkrun's InfiniBand probe fills
# them per cluster, and b12x falls back to the detected NCCL_IB_HCA. Naming a
# host device here would break portability.
# ---------------------------------------------------------------------------
_CACHE = "/cache/runtime"
RECIPE_ENV: dict[str, str] = {
    # --- locations (all under the sparkrun-managed runtime cache) ----------
    "STATE_PATH": f"{_CACHE}/state",
    "DSV41_PACKED_DIR": f"{_CACHE}/engram",
    "B12X_ROCE_CACHE_DIR": f"{_CACHE}/b12x-roce",
    "B12X_COMPILE_CACHE_DIR": f"{_CACHE}/b12x-compile",
    # --- boot.py -----------------------------------------------------------
    "SKIP_PREPARE": "1",       # checkpoint pre-placed in the shared HF cache
    "SKIP_VERIFY": "1",
    "READY_TIMEOUT_S": "3600",
    "OFFLOAD_MODE": "nvme",    # Engram on NVMe (host = the GPU's unified memory)
    # --- Engram reader (adapter/engram_backend.py, row_store.cpp) ----------
    "DSV41_CACHE_GIB": "4",
    "DSV41_CACHE_WAYS": "16",
    "DSV41_IO_THREADS": "96",
    "DSV41_RESIDENT_SCALES": "0",
    "DSV41_STATS_SECONDS": "60",
    "DSV41_ENGRAM_PREFETCH": "1",
    # --- parallelism / serving (boot.py reads these) -----------------------
    "EP_SIZE": "1",            # b12x_next production line; EP>1 dies at decode
    "CONTEXT_LENGTH": "1048576",
    "MEM_FRACTION_STATIC": "0.80",
    "MAX_RUNNING_REQUESTS": "16",
    "CHUNKED_PREFILL_SIZE": "4096",
    "CUDA_GRAPH_MAX_BS_DECODE": "16",
    "MAX_TOTAL_TOKENS": "4000000",
    "SPEC_ALGO": "DSPARK",
    "DSPARK_BLOCK_SIZE": "5",
    # --- overlay adapters (the upstream production line) -------------------
    "DSV41_INDEXER_CHUNKED": "1",
    "SGLANG_DSPARK_FOLDED_SAMPLING": "2",
    "SGLANG_RUST_BUILD_MODE": "never",
    "SPARK_PREFILL_TP_SPLIT": "1",
    "DSV41_FAST_LOAD": "1",
    "DSV41_FAST_LOAD_N_EXPERTS": "384",
    "DSV41_SHARED_PAD_K": "1",
    "DSV41_WO_A_W8": "1",
    "DSV41_WO_A_W8_MID": "1",
    "DSV41_WO_A_W8_DROP": "1",
    "DSV41_DRAFT_TAU": "0.7",
    "DSV41_DRAFT_HEAD_FP8": "1",
    "DSV41_BLOCK_VERIFY": "1",
    "DSV41_FOLDED_FENCE": "1",
    "DSV41_VERIFY_CAP": "conf:0.1",
    "DSV41_AUTOTUNE_KEEP": "1",
    "DSV41_REPLICATED_SPLIT": "wqkv_a,engram.wkv",
    "DSV41_DRAFT_MAIN_PROJ_SPLIT": "1",
    "DSV41_SPLIT_COMPACT_GATHER": "1",
    "DSV41_ROUTER_LIVE": "1",
    "DSV41_MOE_B12X_NEXT": "1",
    "DSV41_MOE_B12X_NEXT_DETERMINISTIC": "1",
    "DSV41_HC_FUSED": "1",
    "DSV41_PREFILL_SP": "1",
    "DSV41_PREFILL_SP_FP8": "1",
    "DSV41_L2_PREFETCH": "1",
    "DSV41_L2_PREFETCH_WOA": "1",
    "DSV41_SPEC_SYNC_FREE": "all",
    "DSV41_EAGER_GLUE": "all",
    # NOTE: DSPARK_SPS_TABLE / DSPARK_STS_TABLE are deliberately NOT set --
    # upstream lists the SPS table under "Not used: crashes the Engram path".
    # --- RoCEnante + NCCL transport (device names come from detection) -----
    "SGLANG_ROCE_ALLREDUCE": "1",
    "SGLANG_ROCE_MAX_SIZE": "2097152",
    "DSV41_ROCE_GATHER": "2097152",
    "NCCL_P2P_DISABLE": "1",
    "NCCL_SHM_DISABLE": "1",
    "NCCL_CUMEM_ENABLE": "0",
    "NCCL_BUFFSIZE": "1048576",
    "NCCL_LL128_BUFFSIZE": "262144",
    "NCCL_PROTO": "^LL128",
    "NCCL_MAX_NCHANNELS": "8",
    "NCCL_DEBUG": "WARN",
    "NCCL_DEBUG_SUBSYS": "INIT,ENV",
    # expandable_segments False: the V4.1 SGLang lane reports NaN logits above 64
    # prefill query tokens with it on (ds4 AGENTS.md §6.4). boot.py's default too.
    "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:False",
}


def apply_recipe_env(env: dict[str, str]) -> None:
    """Apply the production config, overriding the image's baked ENV.

    Override, not setdefault: the image bakes several of these (STATE_PATH,
    DSV41_CACHE_GIB, PYTORCH_CUDA_ALLOC_CONF, ...) and those values are in the
    launcher's process env, so setdefault would let the image win. The keys here
    never include the recipe-owned MODEL_PATH / DSV41_SOURCE / TP_SIZE.
    """
    env.update(RECIPE_ENV)


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


def _resolve_checkpoint(model_path: str) -> str | None:
    """Resolve a hardcoded HF snapshot path to one that exists locally.

    The recipe pins a literal snapshot directory because a bare assignment does
    not glob and a symlinked snapshot tree must be mounted whole. But a shared
    HF cache is re-resolved whenever the upstream repo moves: the local
    `snapshots/<hash>` the recipe names can vanish while the model is still
    fully present under a new hash — the failure is `missing .../config.json`.

    We only need the directory *inside* the container, where the cache is at a
    fixed mount; the path components are taken from the recipe's literal path so
    the fallback works for any mount, not just ours. Candidates are picked by
    the two independent completeness signals HF uses: `refs/main` (what the
    cache actually resolves to today) and `model.safetensors.index.json` (a
    complete checkpoint names every shard). First hit wins; ``None`` means "no
    candidate is complete", and the caller keeps the original path so the
    engine's own error is the one seen.
    """
    import glob

    parts = model_path.rstrip("/").split("/")
    if "snapshots" not in parts:
        return None
    idx = parts.index("snapshots")
    repo = "/".join(parts[:idx])
    if not os.path.isdir(repo):
        return None

    candidates: list[str] = []
    ref_main = os.path.join(repo, "refs", "main")
    try:
        with open(ref_main) as handle:
            revision = handle.read().strip()
        if revision:
            candidates.append(os.path.join(repo, "snapshots", revision))
    except OSError:
        pass
    # Any snapshot dir that carries the shard index, newest first.
    for snap in sorted(glob.glob(os.path.join(repo, "snapshots", "*")), reverse=True):
        candidates.append(snap)

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if os.path.isfile(os.path.join(candidate, "config.json")) and \
           os.path.isfile(os.path.join(candidate, "model.safetensors.index.json")):
            return candidate
    return None


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

    # Fill the production env (locations, engine flags, adapter enablement,
    # RoCEnante, NCCL tuning). Anything already in the container env wins.
    apply_recipe_env(env)

    if args.health:
        os.execve(sys.executable, [sys.executable, BOOT, "health"], env)

    # Heal a stale hardcoded snapshot: if the recipe's literal checkpoint path is
    # not a complete local snapshot, switch MODEL_PATH/DSV41_SOURCE to the one
    # the cache resolves to. boot.py reads both from the env it is exec'd with.
    requested = env.get("MODEL_PATH", "")
    if requested and not os.path.isfile(os.path.join(requested, "config.json")):
        resolved = _resolve_checkpoint(requested)
        if resolved and resolved != requested:
            print(f"launcher: checkpoint {requested} is not present; resolved to {resolved}", flush=True)
            env["MODEL_PATH"] = resolved
            env["DSV41_SOURCE"] = resolved

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
