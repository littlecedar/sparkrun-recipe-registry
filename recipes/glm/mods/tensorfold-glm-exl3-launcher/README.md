# tensorfold-glm-exl3-launcher

Compatibility gate + launcher shim for the **GLM-5.3-Flash EXL3 TP=4 lane**'s
engine image (MiaAI-Lab's `tp4`-branch build of TensorFold v0.6.0 with 106
patches), used by
`recipes/glm/glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang.yaml`.

| | |
|:--|:--|
| Kind | Pre-exec mod (gate + cache dirs) **and** the serve command (the shim). Modifies no image file. |
| License | AGPL-3.0-or-later (this repo). |
| Verified | **Not yet booted as a sparkrun recipe.** The engine, checkpoint, drafter and configuration are the ones the lane boot-verified outside sparkrun on `.30`–`.33` 2026-10-13 (`recipes/glm/README.md`, `attic/glm/AGENTS.md`); the recipe path needs a TP=4 window. Boot-deferred claims are listed below. |

## Why it exists

The upstream launcher
([`MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks-TensorFold`](https://github.com/MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks-TensorFold),
`tp4` @ `d220030`) is a four-node script: it ssh-probes the fabric, prepares
every Spark, mounts a kernel cache under `$HOME`, and starts one
`tensorfold serve` per node. sparkrun's SGLang runtime instead assumes the
command is `sglang serve …` and appends the per-node rendezvous flags

    --dist-init-addr HOST:PORT --nnodes N --node-rank R

(`sparkrun/runtimes/sglang.py:generate_node_command`). TensorFold knows none of
them: it wants

    tensorfold serve <MODEL_DIR> --tp 4 --rank R --master HOST --master-port PORT

`launcher.py` is the adapter. It consumes those three flags, maps them onto
TensorFold's spelling, applies the lane's production configuration and the
rank-local RoCE device list, resolves the checkpoint and the DFlash2 drafter to
their snapshot directories, and runs `tensorfold serve` as a child (rank 0 hosts
the metrics bridge). The recipe's `command:` is a one-line call to it. Everything
else sparkrun does for a real recipe — image and weight distribution to all four
nodes, the InfiniBand probe, the per-node runtime cache, readiness — is inherited
unchanged.

Same pattern, same authors, as `mods/tensorfold-dsv41-launcher` (the DSV41
TensorFold lane) and `recipes/ds4/mods/dsv41-sglang-overlay` (the knapcio lane):
a `runtime: sglang` recipe whose command is a Python shim, no out-of-tree
sparkrun plugin.

## Mechanics

`run.sh` is a gate and a cache setup, not a patch. It refuses to proceed unless
the container really is the patched GLM build, and then creates + `reown`s
`/cache/runtime/{torch-extensions,triton}`, which `launcher.py` points
`TORCH_EXTENSIONS_DIR` / `TRITON_CACHE_DIR` at so the CUDA extension compile is
paid once per host instead of once per container (the image's own `ENV` points
both at `/cache/…`, which nothing mounts under sparkrun).

The gate is fail-closed because **TensorFold silently ignores a `TF_GLM_*`
switch its build does not know**: an image swap that still starts a server
would serve a different configuration than the one this lane measured. It
checks, inside the container:

- `tensorfold --version` is the v0.6.0 line, and the package imports
  (`tensorfold.cuda.server`, the `glm5_next` engine, `tensorfold.vision.glm` —
  the image's own build-time assertion);
- `cli_args.py` carries `choices=(1, 2, 3, 4)` for `--tp` (patch 0066, the
  TP-N engine: upstream v0.6.0 accepts tp 1–2 only);
- `cuda/roce.py`, `cuda/roce_proxy.c`, `families/glm5_next/cuda/own_front.py`,
  `.../microbatch.py` and `vision/glm.py` exist — files only the patch set
  adds;
- the patched tree reads the TP=4 switches `launcher.py` exports
  (`TF_GLM_SIDE`, `TF_GLM_PROMPT_OWN_FRONT`, `TF_GLM_PROMPT_MICROBATCH`).

**What the gate does not prove:** the exact patch bytes. That is the recipe's
**digest pin** — `ghcr.io/miaai-lab/…@sha256:eb17e092…`, resolved from the
upstream tag `v0.6.0-7a37454d3238`. Three independent checks agree on it: the
tag and the digest return the same manifest (`docker manifest inspect` on the
head), its config blob carries `tf.patches=7a37454d3238`, and upstream's own
`image_hash()` — `sha256` over `patches/*.patch` in glob order plus
`IMAGE_EXTRAS`, truncated to 12 hex — recomputes to that same `7a37454d3238`
from the 106 files at `d220030`. Upstream's `prepare.sh` pulls this digest and
`docker tag`s it `tensorfold-glm53:v0.6.0`, the local name the TP=4 trial
recorded. The in-container gate is defence in depth for a launch that overrides
`container:`. `/opt/tf-patches` is logged, not gated.

A guard *test* for these claims would assert, against a fixture directory: each
marker file absent → the gate dies; the `--tp` choices line reverted to
`(1, 2)` → the gate dies. `tests/test_glm_launcher_shim.py` guards the shim's
half of the contract (rendezvous mapping, rank, artifacts, fail-closed paths).

## The shim's three load-bearing behaviours

- **The rendezvous port.** sparkrun's cluster launch gates on the port it puts
  in `--dist-init-addr`; TensorFold's TCPStore binds `--master-port`, whose own
  default is 29551. The shim passes the address's port through, or the head
  opens 29551 while sparkrun polls 25000 and the launch is declared dead.
- **The rank.** Only the shim sees `--node-rank` (the container env carries no
  rank), and only the shim can set `--rank`. Rank 0 alone gets
  `--name/--host/--port` — the workers' command stops at `--master-port`, as
  upstream's does.
- **Artifacts.** `{model}` arrives as the prepared snapshot path (sparkrun
  rewrites it for any recipe with a `command:` template); the shim accepts it,
  or resolves a repo id from the node's own HF cache. The drafter is handed to
  the engine as a **snapshot directory** (upstream does the same), and a pinned
  revision that is not on disk **fails closed** rather than serving whatever
  `refs/main` happens to name.

## Environment

`RECIPE_ENV` in `launcher.py` is the upstream launcher's `scripts/config.sh` @
`d220030` `export` set as it resolves for `./start-tp4.sh` (TP=4, COMM=roce,
KV=fp8, DENSE=q4, VISION=1, PARALLEL=8), verbatim apart from `TF_GLM_MAX_QUEUED`
— upstream leaves it empty precisely so as *not* to set it, and the trial's own
`scripts/local.sh` may have set a small value there; this lane leaves the
scheduler's stock queueing. `TF_GLM_MTP=auto` keeps DFlash2 drafting every
request (the checkpoint's MTP head is not loaded).

Two values are rank-local and are **not** in `RECIPE_ENV`:

- `TF_ROCE_HCA` is copied from the process env's `NCCL_IB_HCA`, which sparkrun's
  InfiniBand probe fills per node. Upstream does the same thing by hand: at TP>2
  it passes the node's active RoCE devices as *both* `NCCL_IB_HCA` and
  `TF_ROCE_HCA` (`scripts/nodes.sh`). Naming a host device in the recipe would
  break portability, and sparkrun's probe already supplies the same list.
  Unset is a legal state (the engine derives its own devices); the gate logs it.
- The checkpoint, the drafter and the port arrive through the `command:`
  template from `defaults`.

`NCCL_*` is deliberately absent for the same reason (the probe owns it).

## Metrics bridge

The sparkrun monitor scrapes a serve's log for four shapes (`Avg generation throughput: N tokens/s`,
`Avg prompt throughput: N tokens/s`, `Running: N reqs`, `Waiting: N reqs`). The TensorFold serve logs
none of them, so the shim runs `tensorfold serve` as a **child** and, on rank 0, hosts a daemon thread
that reprints this rank's `/metrics` counters in those shapes.

- Gated by `TF_METRICS_BRIDGE` (default on; `0` disables it without a repo edit) and
  `TF_METRICS_BRIDGE_DEADLINE_S` (default 3600 s for the post-load wait).
- Fail-open: it never touches the serve, and a counter the body does not carry prints **no line** —
  never a zero.
- The first `/metrics` body of a boot prints `metrics bridge: matched [...]`, the evidence that the
  `tensorfold:*` scrape keys fit that arm's engine image.
- The two GLM mods carry **bundled copies** of the same block (there is no shared library: sparkrun
  ships only a mod's own directory). `tests/test_tensorfold_glm_metrics_bridge.py` pins them
  byte-identical, so a fix must land in both.

Status: shipped, **not yet observed printing on either arm** — the live 3.0bpw boot predates the
bridge, and this build's `/metrics` names are unverified on the 4bpw patch tree.

## Not in this mod

- The engine image is **pulled** (digest-pinned, `builder: docker-pull`), not
  built: the digest is byte-identical to the build the lane measured, and
  rebuilding 106 patches would produce a *different* image under the same
  name. Upstream's `scripts/publish-image.sh` builds a fresh tag when the patch
  set moves — that is a lane-level decision, not a recipe edit.
- The ~176 GB checkpoint and the DFlash2 drafter are distributed by sparkrun
  (`distribution_config` defaults to enabled for models and containers). The
  drafter is declared in the recipe's `defaults.speculative_draft_model`, which
  the SGLang runtime reads to add it to the distribution set; nothing else
  fetches it.

## Boot-deferred claims (a TP=4 window settles these)

1. The image's `tensorfold serve` accepts this exact argv (copied from
   upstream `start.sh:341/356` + `config.sh` at TP=4; `--tp 4`/`--rank 3`
   additionally depend on patch 0066, which the gate checks by source).
2. The engine's RoCE all-gathers come up with `TF_ROCE_HCA=NCCL_IB_HCA` on this
   cluster's fabric (`TF_GLM_COMM=roce`). Same bits either way; a failure shows
   as an all-gather stall, and `TF_GLM_COMM=nccl` is the fallback — but the
   98.4 t/s figure is the RoCE one.
3. `--vision` (upstream `VISION=1`) loads the tower on rank 0 from this
   checkpoint without the Ablit/vision extras, and the KV pool still sizes to
   the trial's 5,834,752 tokens on a node with a display disabled.
4. Cold-boot time fits the recipe's readiness budget (`port_timeout_s: 7200`,
   `health_timeout_s: 3600`): the first boot pays the CUDA extension compile,
   later boots read `/cache/runtime/torch-extensions`.
5. `earlyoom`/`sparkrun` memory policy: upstream disabled `earlyoom` on all four
   Sparks before launching and re-enabled it after. Nothing in sparkrun does
   that; `TENSORFOLD_MEMORY_RESERVE_GIB=19.6` is the engine's own guard.