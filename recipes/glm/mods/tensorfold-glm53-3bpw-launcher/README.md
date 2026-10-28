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
| Image | built from [`../../Dockerfile.tensorfold-glm53-3bpw`](../../Dockerfile.tensorfold-glm53-3bpw) over `lmsysorg/sglang:dev-cu13` arm64 manifest `sha256:e9aa22adaad2b1fa30130d9d033f7f0d3e706e2780973eca849827d5aed983d6`. **Pushed 2026-10-18** to `littlecedar/dgx-spark-tensorfold-glm53-exl3-3bpw:0.6.0-ddfad35`, registry digest **`sha256:366c2d4e0d0a066f909650c4aa8df49c4a467b47a082a3cd177bef59d2b7f076`** — that is the pin the recipe carries, read back from the registry with `docker buildx imagetools inspect`. It is the tag's **second** push: the first (`sha256:25bb6806…`) shipped no `*.cu` — `pip install --no-deps .` carries no package data — and died at the first JIT kernel compile on `.../families/glm_moe_dsa/cuda/latent_rows.cu`. The Dockerfile now mirrors all 25 kernel sources from `/opt/tensorfold/src/tensorfold` onto the installed package root (verified: `find <pkg> -name '*.cu' | wc -l` → 25; receipt: `~/benchmarks/glm-3bpw-image-20261018/rebuild.log`). Never cite a local manifest id (`aabe1cac210f`, `44e478f1`) as the pin. |
| Verified | **Booted 2026-10-18**, TP=4 on `.30`–`.33` via `sparkrun run … --transfer-mode local`, image digest `sha256:366c2d4e…`. `/v1/models` answered **240 s** after launch (engine self-report `loaded in 308.7s`); four CUDA extensions compiled at first start; smoke completion 32 tokens / 1.66 s (`prefill_s 0.2471`, `decode_s 1.3909`, 19/34 drafts accepted). 397-token/128-output ladder: c1 24.2, c2 25.3, c4 40.6 aggregate output tok/s (per-request decode 31.7 / 14.5 / 11.4). Long-context TTFT 258.4 s at 100,559 prompt tokens. Receipt: `~/benchmarks/glm-3bpw-boot-20261018/RECEIPT.md`. One boot, one ladder — a repeat boot and the 1M-window rungs remain open (see [Boot-deferred claims](#boot-deferred-claims)). |

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
directory, and runs `tensorfold serve` as a child (rank 0 hosts the metrics
bridge). Everything else sparkrun does for a real recipe — image and weight
distribution to all four nodes, the InfiniBand/NCCL probe, the per-node runtime
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

## Claims the boot did and did not settle

The 2026-10-18 TP=4 boot on `.30`–`.33` (receipt: `~/benchmarks/glm-3bpw-boot-20261018/RECEIPT.md`):

1. **TP=4 NCCL/RoCE rendezvous — settled, without `spcx`.** Four ranks rendezvoused on
   `.30:25000` under sparkrun's own probe vars and the default `NCCL_NET_PLUGIN=none`; rank 0
   reports `decode all-gathers: RDMA writes over roceP2p1s0f0, rocep1s0f0` and serves at TP=4. No
   hand-set `NCCL_SOCKET_IFNAME`/`NCCL_IB_HCA`/`spcx` is needed.
2. **KV sizing at `TF_GLM_KV=q5` — fits, but the four-long-window case is untested.** This boot:
   `startup estimate 96.27 GiB within 103.38 GiB; native 1048576, allocated prompt/reply window
   1048576, cache slots 1048584`, and `up to 4 requests decode together, each with a
   1048576-token window (extents of one 1048584-row pool)`. Allocated, not proven: four concurrent
   1M windows were never filled.
3. **MTP-3 acceptance — still the trial's number only.** The 2026-10-13 trial measured 63.4 %
   (1,556/2,453). This boot's single 32-token smoke accepted 19 of 34 drafts (55.9 %) — one short
   greedy request is not that measurement; `TF_GLM_MTP_REUSE=2` is unset here (engine default),
   unlike the trial.
4. **First-boot sm_121 JIT — settled.** `tensorfold_rdma_gather_v6`,
   `tensorfold_exl3_linear_v3`, `tensorfold_glm_latent_rows_v1` and `tensorfold_exl3_experts_v20`
   compiled at first start for GB10; the engine reports `loaded in 308.7s`. Cold-boot cost is
   ~95 s of launch + ~5 min of first-start compile + weight load, far inside the 7200 s budget.
5. **Smaller ones — settled.** `--temperature 0` reaches the engine (argv in the receipt), and the
   ~273 GB checkpoint was already staged on all four nodes (model distribution took 34.9 s).

Still open: a second boot (cold-JIT cache reuse), any rung past 100,559 prompt tokens, and quality
either inside or outside sparkrun for this image.

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

- The image is **pulled**, not built: the recipe pins the registry digest of the image this
  Dockerfile produced, and that tag is published (`littlecedar/dgx-spark-tensorfold-glm53-exl3-3bpw:0.6.0-ddfad35`),
  so a launch on any node with registry access pulls it. A re-push of the same tag is *not*
  re-pulled unless the launch also passes `--rebuild` or the pin changes — the pin follows the
  digest, so bump it when the image changes.
- The ~273 GB checkpoint is distributed by sparkrun (`distribution_config` defaults to enabled
  for models and containers).
