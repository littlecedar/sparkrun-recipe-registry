# dsv41-sglang-overlay

Compatibility gate and launcher shim for the **knapcio DSV41 SGLang image**
(vendored as `littlecedar/dgx-spark-dsv41:canary-roce`, natively
`dsv41-4x-spark:canary-roce`), used by
`recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml`.

| | |
|:--|:--|
| Kind | Pre-exec mod; **modifies no image file**. |
| License | AGPL-3.0-or-later (this repo). |
| Verified | Booted live on 4 Sparks (`.32`–`.35`) 2026-10-02; ~12 healthy boots. Portability rewrite (no host mounts; `/cache/runtime` Engram) booted 2026-10-02. See `recipes/ds4/KNAPCIO-SGLANG-INTEGRATION.md`. |

The image is **vendored**: `littlecedar/dgx-spark-dsv41:canary-roce` on Docker Hub
(digest-pinned), so sparkrun pulls it and no node builds it. The recipe's
`distribution_config.containers.enabled: true` drives that pull.

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

It then logs the resolved paths and creates + `reown`s the cacheable-object
directories under the sparkrun-managed runtime cache (`/cache/runtime/engram`,
`/cache/runtime/state`, `/cache/runtime/b12x-compile`, `/cache/runtime/b12x-roce`)
so the non-root serve user can write them. Nothing in the image is modified —
the upstream repo's own in-image test suite gates the overlay instead.

## Portability (the whole point of the `/cache/runtime` wiring)

The recipe carries **no host bind mounts**. Everything that is not the model and
not image content — the two per-rank Engram shards, boot.py's `launch.json` /
`api-key`, and the b12x JIT caches — lives under sparkrun's managed runtime
cache: `<host> ~/.cache/sparkrun/runtime-cache/sglang/<model_dir>/`, mounted at
`/cache/runtime`. sparkrun creates and chowns that leaf per node; the recipe
never spells the host path and the container path is constant.

The two pieces that make this work:

- **`run.sh`** creates and `reown`s the subdirectories (it runs before the serve
  command), so the non-root user can write them.
- **`launcher.py`** is the only component that learns the node's rank (sparkrun
  appends `--node-rank` to the serve command on the head *and* every worker; the
  container env carries no rank). It materializes *this rank's*
  `engram-l{1,14}-r{rank}of{tp}.bin` under `/cache/runtime/engram`:
  - present → no-op;
  - missing → it starts the image's `/opt/dsv41/scripts/pack_engram.py`
    **detached** (`flock`-guarded, one per node) and boots immediately on the
    checkpoint Engram fallback. The packed shards are used from the next boot.
    Synchronicity would blow sparkrun's ~150 s head-rendezvous wait on a cold
    node; backgrounding keeps every boot inside budget and correctness is
    unaffected (`adapter/engram_backend.py` treats the packed shard as optional
    acceleration; `row_store.cpp` fails closed on a range mismatch).

It also **locates the checkpoint**. The recipe passes the repo id
(`--model {model}`); `launcher.py:resolve_checkpoint()` finds it in the fixed
in-container HF cache (`/cache/huggingface/hub/models--<org>--<name>`) and sets
`MODEL_PATH` / `DSV41_SOURCE` — preferring `refs/main`, else the newest snapshot
carrying both `config.json` and `model.safetensors.index.json`. So the recipe
spells **no snapshot path** (a hardcoded `snapshots/<hash>` is not portable and
reads as a path a user must maintain), and a cache that re-resolves to a
new hash cannot break the boot (each node's cache is independent now — there is
no shared mount). A container bind supplied as `MODEL_PATH` is left
alone (it is read-only, which is all the `SKIP_PREPARE` existence check needs).

## The production env lives here, not in the recipe

`launcher.py`'s `RECIPE_ENV` carries the whole production configuration —
locations under `/cache/runtime`, the boot.py read flags, the Engram reader
tuning, the engine/serving flags, the overlay-adapter enablement, RoCEnante and
the device-free NCCL transport tuning (`mods/dsv41-sglang-overlay/launcher.py`,
inventoried in `.scratch/ds4/knapcio/ENV-MIGRATION.md`). It is applied with
`env.update(RECIPE_ENV)`, i.e. it **overrides** the launcher's process env —
necessary because the image bakes `STATE_PATH=/state`, `DSV41_CACHE_GIB=16`,
`PYTORCH_CUDA_ALLOC_CONF=…True`, `SGLANG_RUST_BUILD_MODE` and `OFFLOAD_MODE`, and
a `setdefault` would let those win (silently redirecting boot.py state to an
unwritable `/state`, and re-arming the allocator mode that NaNs above 64 prefill
query tokens). `TP_SIZE` is the one thing the launcher cannot derive (sparkrun
passes `--nnodes`, not the TP degree), so it is the only key the recipe sets.

The recipe's own `env:` is therefore a **single line, `TP_SIZE`**, and carries no
host device names and no snapshot path. `RECIPE_ENV` values that the runtime
already defaults to (SKIP_SMOKE, WARMUP, HOST, SERVED_MODEL_NAME, the prefill
thresholds, the fast-load slice/inflight defaults) are **not** set anywhere.

`/cache/runtime` sits on node-local NVMe (`/dev/nvme0n1p2` here), so the packed
Engram reads never traverse the network — the same property the old
`/home/red/dsv41-engram` bind mount gave, without the machine-specific path.

## Not in this mod (and why)

- The image itself is **vendored** (`littlecedar/dgx-spark-dsv41:canary-roce`,
  digest-pinned) and pulled by sparkrun with
  `distribution_config.containers.enabled: true`. A local-only build is the opt
  out: retag it `dsv41-4x-spark:canary-roce` and set `containers.enabled: false`.
- The checkpoint is **distributed to every node** by sparkrun (the HF cache is
  per-node, not shared — there is no NFS export). See the recipe's
  `distribution_config.models`. The image itself is vendored (pulled, not built).
