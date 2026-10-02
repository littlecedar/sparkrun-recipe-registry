# dsv41-sglang-overlay

Compatibility gate and launcher shim for the **knapcio DSV41 SGLang image**
(`dsv41-4x-spark:canary-roce`), used by
`recipes/ds4/deepseek-v4.1-flash-sglang-tp4-knapcio.yaml`.

| | |
|:--|:--|
| Kind | Pre-exec mod; **modifies no image file**. |
| License | AGPL-3.0-or-later (this repo). |
| Verified | Booted live on 4 Sparks (`.32`–`.35`) 2026-10-02; ~12 healthy boots. See `recipes/ds4/KNAPCIO-SGLANG-INTEGRATION.md`. |

## Why it exists

The image is built from
[`knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4`](https://github.com/knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4)
via its `Dockerfile.canary-roce`. It bakes the full adapter overlay at
`/opt/dsv41/adapter` (on `PYTHONPATH` via the image `ENV`), the `b12x` /
`b12x_next` kernels, and `/opt/dsv41/boot.py`. Its entrypoint is
`python3 -u /opt/dsv41/boot.py run`, and **boot.py builds the entire
`sglang.launch_server` argv from environment variables**.

sparkrun's SGLang runtime instead assumes the command is `sglang serve …` and
appends the per-node rendezvous flags `--dist-init-addr HOST:PORT --nnodes N
--node-rank R`. `launcher.py` bridges the two: it consumes those three flags,
maps them onto boot.py's `DIST_INIT_ADDR` / `NNODES` / `NODE_RANK`, and execs
`boot.py`. The recipe's `command:` is a one-line call to it; every serve
parameter rides in the recipe's `env:`.

## Mechanics (fail-closed)

`run.sh` is a gate, not a patch. It refuses to proceed unless the container
really is the overlay build:

- `/opt/dsv41/boot.py` exists,
- `/opt/dsv41/adapter/sitecustomize.py` exists and contains `EngramLoader`,
- `/opt/b12x_next/b12x_next` exists,
- the engine's `engram.py` exists.

It then logs the resolved paths. Nothing in the image is modified — the upstream
repo's own in-image test suite gates the overlay instead.

## Not in this mod (and why)

The Engram NVMe shards, the node-local image, and the writable `/state` are all
**host-side wiring in the recipe**, not mod content:

- `/home/red/dsv41-engram:/engram-local` — per-rank packed Engram shards, built
  with the image's `/opt/dsv41/scripts/pack_engram.py`.
- `/home/red/dsv41-state:/state` — boot.py writes `launch.json` / `api-key` there.
- `distribution_config.containers.enabled: false` — the image is node-local and
  must not be pulled from a registry.
