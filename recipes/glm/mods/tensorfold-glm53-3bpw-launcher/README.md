# tensorfold-glm53-3bpw-launcher

Compatibility gate + launcher shim for the **GLM-5.3 EXL3 3.0bpw (full 753B) TP=4 lane**,
used by [`glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang.yaml`](../../glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang.yaml)
(`recipes/glm/`). The name carries no `flash`: this is the full 753B checkpoint, not the Flash
line the lane's other recipe serves.

| | |
|:--|:--|
| Kind | Pre-exec mod (gate + cache dirs) **and** the serve command (the shim). Modifies no image file. |
| License | AGPL-3.0-or-later (this repo). |
| Engine | [`bertholomus/TensorFold`](https://github.com/bertholomus/TensorFold) branch `glm-dsa-tp4` @ **`ddfad356dc16f4d6bed9cfcc9d60cd0ebc0a3595`** (2026-10-04), TensorFold **0.6.0**, Apache-2.0. No patch set — the commit is the whole provenance anchor. |
| Image | built from [`../../Dockerfile.tensorfold-glm53-3bpw`](../../Dockerfile.tensorfold-glm53-3bpw) over `lmsysorg/sglang:dev-cu13` arm64 manifest `sha256:e9aa22adaad2b1fa30130d9d033f7f0d3e706e2780973eca849827d5aed983d6`. **Pushed 2026-10-18** to `littlecedar/dgx-spark-tensorfold-glm53-exl3-3bpw:0.6.0-ddfad35`, registry digest **`sha256:25bb6806aa28bc2f7031a70417123398bb02d87cb2276bcb10d23d6525867237`** — that is the pin the recipe carries. A local-registry derivation had produced `44e478f1`, which is the image's local manifest, not the pulled one; never cite it as the pin (receipt: `~/benchmarks/glm-3bpw-image-20261018/REPORT.md`). |
| Verified | **Not booted.** The engine commit, checkpoint and serve line are the ones the lane boot-verified outside sparkrun on `.30`–`.33` 2026-10-13 (`attic/glm/AGENTS.md` §"EXL3 3.0bpw"); the image is pullable now. A sparkrun boot is the open item — see [Boot-deferred claims](#boot-deferred-claims). |

## Why it exists

The 3.0bpw line was a runbook: repo A's
[`bertholomus/glm-5.3-tensorfold-tp4-4xgb10`](https://github.com/bertholomus/glm-5.3-tensorfold-tp4-4xgb10)
ssh's into four Sparks, installs the fork editable at container start, and runs one
`tensorfold serve` per node. sparkrun's SGLang runtime instead assumes the command is
`sglang serve …` and appends the per-node rendezvous flags

    --dist-init-addr HOST:PORT --nnodes N --node-rank R

(`sparkrun/runtimes/sglang.py:generate_node_command`). This engine knows none of them; it wants

    tensorfold serve <MODEL_DIR> --tp 4 --rank R --master HOST --master-port PORT
        --context 1048576 --parallel 4 --mtp-drafts 3 --drafter none

`launcher.py` is the adapter. It consumes those three flags, maps them onto TensorFold's
spelling, applies the lane's configuration, resolves the checkpoint to its prepared snapshot
directory, and `execve`s `tensorfold serve`. Everything else sparkrun does for a real recipe —
image and weight distribution to all four nodes, the InfiniBand/NCCL probe, the per-node runtime
cache, readiness — is inherited unchanged.

Same pattern as [`../tensorfold-glm-exl3-launcher`](../tensorfold-glm-exl3-launcher/README.md)
(the 4bpw lane) and `mods/tensorfold-dsv41-launcher` (the DSV41 lane): a `runtime: sglang`
recipe whose command is a Python shim, no out-of-tree sparkrun plugin.

## The CLI surface actually mapped

Taken from the built image's own `tensorfold serve --help` (a device-free probe on the head:
`docker run --rm --entrypoint bash <image> -lc "tensorfold serve --help"`), not from the fork's
README. The flags this shim emits, and why each one:

| flag | value | why it is emitted |
|:--|:--|:--|
| `model` (positional) | prepared snapshot dir | `{model}` reaches the shim as sparkrun's on-disk snapshot path; the engine takes a directory or a repo id |
| `--tp` | 4 | the CLI accepts `{1,2,4,6}`; this family refuses 6 (`cuda_engine`: "splits over 1, 2 or 4 GPUs"), so the shim's choices are `1,2,4` |
| `--rank` | `--node-rank` | the container env carries no rank; only the shim sees it |
| `--master` / `--master-port` | `--dist-init-addr` host / **its port** | the port is the load-bearing one: sparkrun gates the launch on 25000, the engine's own default is 29551 |
| `--context` | 1048576 | the checkpoint's own `max_position_embeddings`; passing it makes `context_explicit` true, so the engine sizes the pool for the stated window instead of a derived one |
| `--parallel` | 4 | the lane's serve line. Default is `auto`, which on CUDA is *one stream at a time* |
| `--mtp-drafts` | 3 | GLM-5.3's own MTP head, depth 3 — the lane's drafting path (63.4 % acceptance on the trial) |
| `--drafter` | `none` | this family declares `DRAFTER = ""`; `none` states that drafting is in-checkpoint, not a second model |
| `--name` / `--host` / `--port` | served id / bind / port | **rank 0 only**, as the lane's `tp4_start.sh` does (workers stop at `--master-port`) |
| `--temperature` | 0 | rank 0 only: the lane's serve line pins greedy sampling |
| `--kv-dtype` | *not passed* | a different axis (bf16/int8/int4 cache mantissas). The lane quantizes with `TF_GLM_KV`; leaving this at `bf16` is the measured configuration |

Env the shim sets (`lane_env`), on every rank:

| var | value | notes |
|:--|:--|:--|
| `TF_GLM_KV` | `q5` (recipe `defaults.kv_format`) | 5-bit latent + fp8 indexer keys; 40,824 B/slot at TP4 |
| `TF_GLM_DCP` | `4` (recipe `defaults.dcp`) | decode context parallelism: the cache's positions interleave over the four ranks. **Must equal the TP world**; the shim fails closed on a mismatch before the weight load |
| `TF_GLM_EXTENTS` | `1` (recipe `defaults.extents`) | the pool becomes one span of the window that streams take extents of — the other half of the 1M configuration |
| `TF_GLM_EMBED_SPLIT` | `1` | the tree's own default; stated because every rank must agree (the engine raises on a mismatch) |
| `TF_GLM_MTP_REUSE` | `2` | **non-default** (tree default `0`): the lane's value for the MTP-3 chain |
| `TENSORFOLD_NO_UPDATE_CHECK` | `1` | no GitHub round-trip inside the readiness window |
| `TORCH_EXTENSIONS_DIR`, `TRITON_CACHE_DIR`, `HOME` | under `/cache/runtime` | see Mechanics |

The four recipe-owned values arrive as `defaults:` → `command:` placeholders → shim arguments,
not as mod constants, so `-o kv_format=…` / `-o dcp=…` can retune them. A launcher's own
`RECIPE_ENV` clobbers an env override — see the ds4 lane's receipt for that trap — so a knob
that lived only in the mod's constant table would be unreachable from the command line.

## Mechanics

`run.sh` is a gate and a cache setup, not a patch. It refuses to proceed unless the container
really is this fork, then creates and `reown`s `/cache/runtime/{torch-extensions,triton}`, which
`launcher.py` points `TORCH_EXTENSIONS_DIR` / `TRITON_CACHE_DIR` at (this image's `ENV` sets
neither, unlike the 4bpw image).

The gate is fail-closed because **TensorFold silently ignores a switch its build does not
know**: a swap to another TensorFold image would still start a server, serving a different
configuration than the one this lane measured. In-container, it asserts:

- `tensorfold --version` is the v0.6.0 line;
- `tensorfold/cli_args.py` has `choices=(1, 2, 4, 6)` for `--tp` (upstream v0.6.0 is 1–2; the
  4bpw build is 1–4);
- `families/glm_moe_dsa/__init__.py` declares `bertholomus/GLM-5.3-EXL3-3.0bpw` **and**
  `DRAFTER = ""`;
- `kv8.py`, `dcp.py`, `multi.py`, `mtp.py` read `TF_GLM_KV`, `TF_GLM_DCP`, `TF_GLM_EXTENTS`,
  `TF_GLM_MTP_REUSE` respectively;
- the **4bpw-only** files are absent — `cuda/roce.py`, `cuda/roce_proxy.c`,
  `families/glm5_next/cuda/own_front.py`, `families/glm5_next/cuda/microbatch.py`;
- `tensorfold.cuda.server`, the `glm_moe_dsa` engine and `dcp` import (CPU-safe).

**What the gate does not prove:** the commit. There is no patch hash to recompute on a branch;
that is the recipe's image digest, and `org.opencontainers.image.revision = ddfad35…` is
readable only from the host (`docker image inspect`).

## What the 4bpw mod does that this one must not

The sibling [`tensorfold-glm-exl3-launcher`](../tensorfold-glm-exl3-launcher/README.md) targets
the 106-patch `tp4` build — a different TP engine. Copying its behaviour here would be silently
wrong, so this shim deliberately does none of it:

| 4bpw mod | this fork | consequence |
|:--|:--|:--|
| gates on `choices=(1, 2, 3, 4)` and requires `cuda/roce.py`, `roce_proxy.c`, `own_front.py`, `microbatch.py` | requires `(1, 2, 4, 6)` and requires those four files to be **absent** | each gate fails closed on the other's image |
| `TF_GLM_COMM=roce`, `TF_ROCE_HCA` copied from `NCCL_IB_HCA`, `TF_ROCE_MAX_KB`/`TF_ROCE_WAIT_S` | no `TF_GLM_COMM`, no `TF_ROCE_*` — this fork's transport is plain NCCL (`TF_TP_WORLD` + `--rank/--master/--master-port`), configured by sparkrun's probe | naming a RoCE switch here would be a silent no-op |
| resolves and requires a DFlash2 drafter snapshot, `--drafter <dir>` | no drafter at all; `--drafter none`, `--mtp-drafts 3` | drafting is the checkpoint's own MTP head |
| `RECIPE_ENV` = upstream `config.sh` at TP=4 (44 `TF_GLM_*` switches: `TF_GLM_SIDE`, `TF_GLM_PROMPT_MICROBATCH`, `TF_GLM_MULTI_WINDOW=64`, `TF_GLM_CACHE_ENTRIES=32`, …) | five switches, four of them from the recipe's `defaults:` | the patch build's production tuning has no counterpart here; porting it would set ~40 vars this tree ignores |
| `--vision` (VISION=1), `--max-tokens 32768`, `--parallel 8` | no `--vision` (this line has no vision tower), no `--max-tokens` (engine default 4096), `--parallel 4` | each of those is the other lane's measured choice |
| `TF_GLM_MTP=auto` (MTP head *not* loaded) | MTP-3 drafting, `TF_GLM_MTP_REUSE=2` | opposite drafting mechanisms |

## Boot-deferred claims

A TP=4 window on `.30`–`.33` with this image settles these; none is settled by the build:

1. **TP=4 NCCL/RoCE rendezvous.** The trial set `NCCL_SOCKET_IFNAME`, `NCCL_IB_HCA` (per-node
   device lists) and `NCCL_NET_PLUGIN=spcx` by hand in `tp4_start.sh`. sparkrun's probe supplies
   `NCCL_IB_HCA`/`NCCL_SOCKET_IFNAME`/`NCCL_IB_GID_INDEX` per node and defaults
   `NCCL_NET_PLUGIN=none` — the recipe names no device, by the lane's own guard rule. Whether
   the all-gathers come up on the same rails without `spcx` needs a boot; a failure shows as a
   rendezvous/all-gather stall, and the gate logs the two vars the diagnosis needs.
2. **KV sizing at `TF_GLM_KV=q5`.** The pool is sized from free memory at start (the lane's
   Flash sibling showed the README figure is best-case), so the token count is per-boot, not a
   constant. Also unproven: that `--context 1048576` + `TF_GLM_DCP=4` + `--parallel 4` leaves a
   pool that fits four concurrent long windows in the rank's KV headroom (69.86 GiB/rank of the
   121 GiB is weights).
3. **MTP-3 acceptance.** 63.4 % (1,556/2,453 draft tokens) is the 2026-10-13 trial's number on
   an editable install of the same commit; it is not this image's, and `TF_GLM_MTP_REUSE=2` is
   what that measurement ran with.
4. **First-boot sm_121 JIT.** The engine compiles its CUDA extensions at first start for the
   local device (`cuda/build.py::arch_flags` → `-gencode=arch=compute_121,code=sm_121`). A build
   under qemu proves the Python tree imports, not that nvcc + torch in this image compile those
   kernels for GB10; the compile is also where cold-boot time hides. It is why the recipe's
   readiness budget is 7200 s and why the cache dirs exist.
5. Two smaller ones: `--temperature 0` on rank 0 assumes the trial's sampling (it does —
   `tp4_start.sh` passes it), and the checkpoint must be staged on all four nodes (~273 GB per
   node; the 2026-10-14 hygiene pass reclaimed it).

## Not in this mod

- The image is **pulled**, not built: the recipe pins the manifest digest of the image this
  build produced. It is **unpushed** at the time of writing — a launch before publishing needs
  the local tag on every node (the receipt's publish target is
  `littlecedar/dgx-spark-tensorfold-glm53-exl3-3bpw:0.6.0-ddfad35`).
- The ~273 GB checkpoint is distributed by sparkrun (`distribution_config` defaults to enabled
  for models and containers).
