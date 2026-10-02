# Knapcio DSV41 SGLang TP4 integration — provenance, plan, limits

**Recipe:** `recipes/ds4/deepseek-v4.1-flash-sglang-tp4-knapcio.yaml`
**Mod:** `mods/dsv41-sglang-overlay/`
**Upstream:** https://github.com/knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4
(pinned `58f232155917d388b6053eca079c617fd306c33c`, cloned to
`.scratch/ds4/knapcio/`).
**Image:** `dsv41-4x-spark:canary-roce`, built from that repo's
`Dockerfile.canary-roce` on every node (see §Build).
**Date:** 2026-10-02. **Status:** first boot in progress; treat every throughput
number as PENDING until the boot gates pass (§Boot gates) and a bench runs.

## What this is

A **second engine lane** for DeepSeek-V4.1-Flash on our four free Sparks
(`.32`–`.35`), from knapcio's downstream of MiaAI-Lab's recipe. It is
**SGLang + native MXFP4/F8 weights + DSpark**, orthogonal to the shipped
vLLM/EXL3 lane (`deepseek-v4.1-flash-exl3-*`). It exists to answer two questions
the vLLM lane cannot:

1. **Quality comparator (AGENTS.md E5).** Our EXL3 3.5 bpw lane has a 94.4%
   hard-tier score; this lane runs the *official* checkpoint, so an A/B of the
   same battery against it separates quantization damage from base-model limits.
2. **A better long-context throughput point.** Upstream measures **89.7 tok/s
   prose c1** (~2× our vLLM EXL3 38–44) and ~5.4k tok/s cold prefill, from the
   b12x kernels + DSpark + Engram-on-NVMe design.

## Why SGLang was previously a dead end, and what changed

AGENTS.md §9 recorded "serving V4.1-Flash on SGLang with any published image —
do not try", with three blockers:

- *no single published image is both V4.1 and b12x* — **solved**: the knapcio
  repo builds `canary-roce` = upstream `dsv41` branch `f80c91a4b` + the adapter
  overlay + b12x/b12x_next, and internet is available on the nodes to build it.
- *the MXFP4-Cutlass MoE rejects the TP=4 expert partition (2304/4 = 576, not a
  multiple of 128)* — **solved by `EP_SIZE=2`** (2304/2 = 1152 = 9×128), which is
  the base/canary image default; `EP_SIZE=1` (b12x_next) is the production line.
- *the DeepGEMM SM121 cliff* — the recipe's image carries the branch's kernels
  and the overlay's kernel adapters; the resolved backend must be read from the
  boot log (gate 3).

The old verdict was correct **for the images available at the time**; it was not
a claim about a purpose-built overlay build.

## Build

Per node (internet required; ~10 min each, includes the upstream in-image test
suite as the gate):

```bash
# from a checkout of the knapcio repo on the node
bash scripts/fetch-sglang-canary.sh          # stages the dsv4.1 tree @ f80c91a4b
docker build -f Dockerfile.canary-roce -t dsv41-4x-spark:canary-roce .
```

The image is **local-only** (not in a registry). `sparkrun`'s "Distributing
image" step is a no-op when it is already present on every node, so it must be
built on **all four** nodes before the launch. Driver:
`.scratch/ds4/knapcio/build_canary_roce.sh`.

## Engram packing (required before any boot)

The two Engram tables are 202.76 GB of `F8_E4M3`; on a 128 GB unified Spark they
**cannot** live in RAM (AGENTS.md §3.1). The overlay serves them from
**node-local NVMe**, one packed shard per rank:

```bash
# per node, rank = node_rank (0..3)
docker run --rm --entrypoint python3 \
  -v /home/red/.cache/huggingface/hub:/hf:ro \
  -v /home/red/dsv41-engram:/engram \
  dsv41-4x-spark:canary-roce /opt/dsv41/scripts/pack_engram.py \
  --model /hf/models--deepseek-ai--DeepSeek-V4.1-Flash/snapshots/dba1be0a40aa45a94ad051997016db3960a90277 \
  --rank <R> --tp 4 --out /engram
```

~47 GiB/node (two layers × ~23.6 GiB). **Mount the whole `hub/` dir**: this HF
cache uses the shared two-level `hub/blobs/<xx>/<sha>` layout, so mounting only
the `models--…` dir leaves every blob symlink dangling (that is what the first
attempt hit).

## Recipe wiring (how sparkrun drives boot.py)

The image's entrypoint is `python3 -u /opt/dsv41/boot.py run`, which builds the
**entire** `sglang.launch_server` argv from environment variables. sparkrun
instead assumes the command is `sglang serve …` and appends per-node
`--dist-init-addr H:P --nnodes N --node-rank R`.

`mods/dsv41-sglang-overlay/launcher.py` bridges the two: it consumes those flags,
maps them onto `DIST_INIT_ADDR`/`NNODES`/`NODE_RANK`/`SERVER_PORT` in the
environment, and `execve`s `boot.py`. The recipe's `command:` is therefore a
one-line call to that shim; all serve parameters ride in `env:`.

The mod's `run.sh` is a **fail-closed compatibility gate** (boot.py, the adapter
`sitecustomize.py`, b12x_next, and the engine's `engram.py` must all exist) plus
a log of the overlay paths. It modifies **no image file** — the upstream repo's
own in-image tests gate the overlay instead.

## Fabric (verified on our fleet)

| | |
|:--|:--|
| Planes | `192.168.0.0/24` (`rocep1s0f0`) and `192.168.1.0/24` (`roceP2p1s0f0`) |
| Topology | **full mesh on both planes** (ping `.32↔.33/.34/.35`, `.34↔.35` all OK) |
| Port state | `ACTIVE` on port 1 of both HCAs; port 2 DOWN (use `rocep1s0f0`, not `rocep1s0f1`) |
| RoCEv2 GID | **index 3** (IPv4 entry `…ffff:c0a8:00xx`); index 1 is the link-local IPv6 entry |

Full mesh ⇒ **switched, not a ring**: the `NCCL_SWITCHLESS_RING_ONLY` path
(patched NCCL, `NFS_SHARE=0`, local weights per node) is **not** needed.

## Deliberately off on the first boot

- **RoCEnante** (`SGLANG_ROCE_ALLREDUCE` / `DSV41_ROCE_GATHER`). Upstream's
  production line routes TP all-reduces *and* 2 MiB all-gathers over a one-shot
  RDMA kernel. It is the piece with b12x's open **#313** wedge report. First boot
  uses plain NCCL; RoCEnante is a follow-up A/B (`SGLANG_ROCE_MAX_SIZE=2097152`,
  `DSV41_ROCE_GATHER=2097152`, `B12X_ROCE_HCA=rocep1s0f0,roceP2p1s0f0`).
- **`DSPARK_SPS_TABLE` / `DSPARK_STS_TABLE`** — ragged-verify cost tables. Absent,
  `boot.py` stays on the verify-all schedule (correct, slower). Generating them
  needs `python -m sglang.benchmark.dspark_sps_profiler` against a live server.
- **`DSV41_CERT_HEAD`** (v2.3) — -0.5 ms/step at c1, slower from ~10 requests.
- **`DSV41_ENGRAM_DRM_NODE`** — needs a host display-reserve change.

## Boot gates (read before believing any number)

1. `[dsv41-sglang-overlay] overlay gate OK` and
   `launcher: boot.py run NNODES=4 NODE_RANK=<r> …` — the rank must differ per node.
2. `Exact nvme Engram layer=… rows=[a,b)` — the range must **differ per rank**;
   `packed=` must name the `/engram-local` shard. Missing/identical = stop.
3. Resolved backends in the startup log — the kernel path must not be the Triton
   fallback (gate: `[moe_b12x_next] armed`).
4. `DSV4 memory calculation: … full_token=<N>` — the granted KV pool.
5. `Mean acceptance length > 1` on `Decode batch` lines (DSpark working).

## Known limits (from upstream)

- **Prompt-token logprobs unavailable** and late layers run only over the last
  128 rows of a prefill (`--enable-decoder-swa-bounded-replay`); such requests
  get HTTP 400. Output logprobs and cache hits work. **Correctness caveat for a
  quality battery:** greedy text is identical run to run (deterministic MoE
  reduction), so a task battery is comparable, but "bitwise vs the release
  checkpoint" is not available through this path.
- The fast loader costs **3–13% of the KV pool**.
- Greedy text equality is **not** a prefill-correctness gate: ~70k-token cold
  prompts diverge run to run.
- Single-stream prose is bounded by DSpark acceptance (~3 accepted/step on
  prose, ~6 on code).


## First measured result (2026-10-02) — boot OK, decode below upstream

Boot #4 (recipe as shipped with `EP_SIZE=1`) reached **healthy in ~9 min**, all
gates passed: `[moe_b12x_next] armed: routed MoE on b12x_next a7d7d29b (W4A8,
in-place repack)`, `Exact nvme Engram layer=1/14 rank=0..3 rows=[a,b)` **differing
per rank** with `packed=True` (rank 3 fixed after a re-pack), DSpark acceptance
**2.40–2.77**, `max_total_num_tokens=4000000` (KV room `full_token=6907904`),
`context_len=1048576`, `available_gpu_mem=19.79 GB`.

Correctness smoke (off-head, greedy, thinking off): `27*43 -> 1161`,
planets `Mercury/Venus/Earth/Mars`. PASS.

Our bench (`.scratch/ds4/knapcio/bench_sglang.py`, non-streaming decode rate):

| | C1 | C4 | C8 | C16 |
|:--|--:|--:|--:|--:|
| this recipe (NCCL, no SPS table) | 27.4 | 62.5 | 73.2 | 155.0 |
| engine's own `gen throughput` c16 | — | — | — | 174 |
| upstream v2.3 (their fabric/clock) | **89.7** | 165.9 | 244.6 | 357.2 |

**C1 is ~3.3× below upstream and below our own vLLM EXL3 lane (40.7).** The
engine's aggregate in this work-conserving bench agrees with the engine log, so
this is real, not a client artifact. Two known levers are missing and are the
next A/Bs (in priority order):

1. **`DSPARK_SPS_TABLE`** (ragged/compact verify). Upstream: "without [the
   profiled table] the planner falls back to verify-all and the whole thing is a
   no-op." Our run is on verify-all. The table is built with
   `python3 -m sglang.benchmark.dspark_sps_profiler all --out /state/dspark_sps.json`
   against the live server; it must then be present on **every** node.
2. **RoCEnante** (`SGLANG_ROCE_ALLREDUCE=1`, `SGLANG_ROCE_MAX_SIZE=2097152`,
   `DSV41_ROCE_GATHER=2097152`, `B12X_ROCE_HCA=rocep1s0f0,roceP2p1s0f0`,
   `B12X_ROCE_CACHE_DIR=/state/b12x-roce`, `B12X_COMPILE_CACHE_DIR=/state/b12x-compile`).
   Our fabric is switched (RoCEnante-capable). This is the RDMA one-shot
   all-reduce/all-gather — the b12x#313 wedge piece, but upstream's production
   line and a large part of the c1 gap.

Either or both may be needed to reach README-class numbers; state them as PENDING.
