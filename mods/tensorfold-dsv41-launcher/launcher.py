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
checkpoint; TensorFold reads them from the original DeepSeek shards 47/48. The
shipped homes, in order: a combined checkpoint's own `engram/` subdir (what the
DS4 TP=2 lane serves), the same subdir of a stock pack named by `--stock-model`
(the cybersec abliterated arm serves a grafted tree and points back at the pack
it was grafted from, so both lanes read one copy per node), then
`/cache/huggingface/hub/dsv41-engram` (a hand pre-warm) and a
sparkrun-distributed Engram repo. If none is found the engine still loads and
serves, with a warning and degraded output -- the shim does not fail closed on
it, it just does not set TF_DS_ENGRAM so the engine can say so.

Vision. `--vision` (off by default) enables image input, which takes two parts:
the engine flag, and the MoE gates' VL routing bias that the EXL3 pack omitted
(all 43 `*.ffn.gate.bias_vl` tensors; without them image tokens route with the
text bias). `vl_bias.safetensors` ships beside this launcher, and
`TF_DS_VISION_EXTRA` is pointed at that FOLDER -- `attach_vl_bias()` globs
`*.safetensors` in it, so a file path reads 0 gates. Unlike Engram this DOES
fail closed: the engine only warns when the bias is missing, which would look
like working vision, so a `--vision` boot without the file aborts.

Vision also needs the chat template. The upstream DeepSeek-V4.1 template raises
on the placeholder the engine's own vision path inserts
(`families/deepseek_v41/cuda/app.py`, `DsVision.split`), so the server answered
HTTP 400 on every image request; a `--vision` boot therefore serves from a
symlink farm of the checkpoint (`RUNTIME_CACHE/model-overlay`) whose
`chat_template.jinja` is this mod's patched copy.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# In-container mount points (sparkrun's orchestration/primitives.py and
# core/runtime_cache.py fix these).
HF_HUB = "/cache/huggingface/hub"
RUNTIME_CACHE = "/cache/runtime/tensorfold"
ENGRAM_DIR = os.environ.get("TENSORFOLD_ENGRAM_DIR", "/cache/huggingface/hub/dsv41-engram")

#: The template served instead of the checkpoint's own (see "Vision" above).
#: sparkrun ships the mod directory, so this file travels with the launcher.
TEMPLATE_NAME = "chat_template.jinja"


def _engram_in(directory: str | None) -> str | None:
    """``<directory>/engram`` when it holds tables, else None."""
    if not directory:
        return None
    cand = Path(directory) / "engram"
    if cand.is_dir() and any(cand.glob("*.safetensors")):
        return str(cand)
    return None


def resolve_engram_dir(model_dir: str | None = None,
                       stock_dir: str | None = None) -> str | None:
    """The directory the engine should read the Engram tables from, or None.

    Four homes, in order:

    0. **The served checkpoint itself**, when it is a combined local repo
       (``tools/build-dsv41-combined.py``): one HF directory holding both the
       EXL3 weights and the two upstream Engram tables under an ``engram/``
       subdir -- no separate fetch, no pre-warm step. The subdir (not the root)
       is used on purpose: the engine globs ``*.safetensors`` non-recursively,
       so handing it the repo root would make it scan the 39 EXL3 shards.
    1. **The stock pack a graft was built from** (``--stock-model``): a grafted
       tree carries weights and tokenizer files but no ``engram/``, so the arm
       points back at the pack it grafted onto and every arm on the node reads
       the same ~189 GiB of tables instead of storing a second copy.
    2. ``TENSORFOLD_ENGRAM_DIR`` / the default
       ``/cache/huggingface/hub/dsv41-engram`` -- a hand pre-warm.
    3. A sparkrun-*distributed* Engram repo: when the recipe declares
       ``manateelazycat/DeepSeek-V4.1-Flash-TensorFold-Engram`` (or any repo
       carrying the tables) in ``distribution_config.models``, sparkrun
       downloads it on the head and rsyncs it to every worker, and it lands here
       as a normal HF-cache model dir. This is the cheap path on slow links: one
       download, many nodes. Its tensors sit under ``source/`` in that repo, so
       both the snapshot root and its ``source/`` subdir are accepted; the engine
       globs the directory non-recursively, so the dir handed to it must hold the
       ``*.safetensors`` directly.
    """
    for candidate in (model_dir, stock_dir):
        hit = _engram_in(candidate)
        if hit:
            return hit
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


def rank_cache_dir(model_dir: str) -> str:
    """The rank cache for one *served tree*: ``<RUNTIME_CACHE>/rank-cache/<tag>``.

    sparkrun keys its runtime cache on ``model@revision``, and TF writes ONE
    ~106 GiB weights file per rank into ``TF_DS_RANK_CACHE``. Two arms can share
    a runtime-cache key while serving different weights: the cybersec abliterated
    arm pins the same combined pack as the DS4 TP=2 arm (the ds4 recipe has an
    open TODO for that same pin) and grafts 24 rewritten shards over it. So this
    dir is keyed by the served tree -- the resolved ``--model`` directory, taken
    BEFORE the vision overlay reuses one shared ``model-overlay`` dir -- not by
    the runtime-cache key:

    * a snapshot dir keys on its hash (``48afcd1c…``), which follows the pin;
    * a grafted tree keys on its own name (``dsv41-ablit``).

    Not a correctness knob -- TF names each file with its own checkpoint key
    (``…/families/deepseek_v41/cuda/weights.py``: this file's bytes, rank/world,
    and every shard's ``name:size:mtime``), so one arm can never read the other's
    file. It is an eviction knob: that same code unlinks every other
    ``rank<rank>of<world>-*`` in the dir before writing, so in a shared dir the
    two arms would evict each other and every arm switch would re-pay the ~330 s
    cold write.
    """
    tag = re.sub(r"[^A-Za-z0-9._-]", "_", Path(model_dir).name) or "served"
    return str(Path(RUNTIME_CACHE) / "rank-cache" / tag)


def build_model_overlay(model_dir: str) -> str:
    """Serve a model dir whose ``chat_template.jinja`` is this mod's patched one.

    ``cuda/chat_template.py`` reads ``<model_dir>/chat_template.jinja`` when it
    exists and only falls back to ``tokenizer_config.json["chat_template"]``, so
    the overlay is a symlink farm of the checkpoint with one real file: nothing
    is copied (a 197 GB checkpoint) and the node's HF snapshot stays untouched.
    The farm is rebuilt every boot: stale links from another checkpoint (this
    lane serves both the EXL3 pack and a 1017 refresh) are dropped.
    """
    src = Path(model_dir).absolute()
    overlay = Path(RUNTIME_CACHE) / "model-overlay"
    overlay.mkdir(parents=True, exist_ok=True)
    names: set[str] = set()
    for entry in src.iterdir():
        if entry.name == TEMPLATE_NAME:
            continue
        names.add(entry.name)
        link = overlay / entry.name
        if link.is_symlink() and os.readlink(link) == str(entry):
            continue
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(entry)
    for stale in overlay.iterdir():
        if stale.name != TEMPLATE_NAME and stale.name not in names:
            stale.unlink()
    template = Path(__file__).resolve().parent / TEMPLATE_NAME
    tmp = overlay / (TEMPLATE_NAME + ".tmp")
    tmp.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    os.replace(tmp, overlay / TEMPLATE_NAME)
    return str(overlay)


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
    # Image input. The VL routing bias this needs ships beside the launcher, so
    # the flag is the whole operator interface (see the docstring).
    parser.add_argument("--vision", action="store_true")
    # The stock pack a graft was built from (the cybersec abliterated arm serves a
    # grafted dir). Only the Engram resolver reads it; the served dir is --model.
    parser.add_argument("--stock-model", default="")
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
    # Keyed on the served tree, and taken BEFORE --vision may swap model_dir for
    # the shared `model-overlay` dir (see rank_cache_dir).
    rank_cache = rank_cache_dir(model_dir)
    Path(rank_cache).mkdir(parents=True, exist_ok=True)
    env["TF_DS_RANK_CACHE"] = rank_cache
    stock_dir = resolve_checkpoint(args.stock_model) if args.stock_model else None
    engram = resolve_engram_dir(model_dir, stock_dir)
    if engram:
        env["TF_DS_ENGRAM"] = engram
    else:
        print(
            f"[tensorfold-launcher] no Engram tables at {ENGRAM_DIR} (or a model dir's "
            "engram/ subdir, a --stock-model pack's, or a distributed Engram repo): "
            "serving degraded (see recipes/ds4/README.md for the pre-warm step)",
            flush=True,
        )
    if args.vision:
        # attach_vl_bias() takes a FOLDER and globs *.safetensors in it; sparkrun
        # copies this mod to /workspace/mods/tensorfold-dsv41-launcher, so the
        # file that ships in the mod dir is beside this script. Fail closed: the
        # engine only warns about a missing bias and degrades image quality, so
        # a silent miss would look like working vision.
        vision_dir = Path(__file__).resolve().parent
        if not any(vision_dir.glob("*.safetensors")):
            print(
                f"[tensorfold-launcher] --vision: no *.safetensors VL bias in {vision_dir} "
                "(vl_bias.safetensors ships beside this launcher); refusing to start, "
                "image tokens would route with the text bias",
                flush=True,
            )
            return 2
        env["TF_DS_VISION_EXTRA"] = str(vision_dir)
        template = vision_dir / TEMPLATE_NAME
        if not template.is_file():
            print(
                f"[tensorfold-launcher] --vision: {template} missing from the mod dir; "
                "the checkpoint's own template refuses the placeholder the vision path "
                "inserts, so every image request would 400 -- refusing to start",
                flush=True,
            )
            return 2
        if Path(model_dir).is_dir():
            model_dir = build_model_overlay(model_dir)
            print(
                f"[tensorfold-launcher] vision template: serving {model_dir} "
                f"({TEMPLATE_NAME} from the mod dir)",
                flush=True,
            )
        else:
            print(
                f"[tensorfold-launcher] --vision: {model_dir} is not a local directory "
                "(dry run or unresolved repo): the checkpoint's own template is served, "
                "image requests will 400",
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
    if args.vision:
        cmd += ["--vision"]
    if args.tp > 1:
        cmd += ["--master", master or "127.0.0.1", "--master-port", str(master_port)]

    if args.vision:
        print(
            f"[tensorfold-launcher] vision ON: vl_bias_dir={env['TF_DS_VISION_EXTRA']} "
            f"(43 gates; engine flag --vision)",
            flush=True,
        )
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