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

## Image (vendored — no local build)

The recipe uses the **published** image, pulled by sparkrun:

```
littlecedar/dgx-spark-dsv41:canary-roce@sha256:932dd8c2722b07d3f835cab0be3ce6a43e67fe987e904885876d97539e958825
```

It is arm64-only and rebuildable from knapcio's repo:

```bash
git clone https://github.com/knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4.git
cd DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4 && git checkout 58f232155917d388b6053eca079c617fd306c33c
bash scripts/fetch-sglang-canary.sh            # stages the dsv4.1 tree @ f80c91a4b
docker build -f Dockerfile.canary-roce -t dsv41-4x-spark:canary-roce .
```

`distribution_config.containers.enabled: true` makes sparkrun pull the digest on
each target host. Set it to `false` only when you build locally and retag the
result `dsv41-4x-spark:canary-roce` (the local-only path this lane originally
used). The pinned bytes:

| | |
|:--|:--|
| Registry digest | `sha256:932dd8c2722b07d3f835cab0be3ce6a43e67fe987e904885876d97539e958825` |
| Image ID | `sha256:a0e6d103002db3d2ea0f798b372bb356236acfe59458a5f9cbc9bb720ab2c9c5` |
| Base | `lmsysorg/sglang:dev-dsv41` |
| Upstream overlay | knapcio `58f2321`, SGLang `dsv4.1` @ `f80c91a4b` |
| Built | 2026-10-02 on `10.0.4.30` |
| Size | 33.5 GB (arm64) |

## Engram packing (required before any boot)

The two Engram tables are 202.76 GB of `F8_E4M3`; on a 128 GB unified Spark they
**cannot** live in RAM (AGENTS.md §3.1). The overlay serves them from
**node-local NVMe**, one packed shard per rank, under
`/cache/runtime/engram` (the sparkrun-managed runtime cache; see "Portability").
The image's own packer builds them:

```bash
# per node, rank = node_rank (0..3), run inside the serving image.
# Use the snapshot the cache actually serves ($repo/refs/main):
python3 /opt/dsv41/scripts/pack_engram.py \
  --model /cache/huggingface/hub/models--deepseek-ai--DeepSeek-V4.1-Flash/snapshots/$(cat /cache/huggingface/hub/models--deepseek-ai--DeepSeek-V4.1-Flash/refs/main) \
  --rank <R> --tp 4 --out /cache/runtime/engram
```

~47 GiB/node (two layers × ~23.6 GiB). **Mount the whole `hub/` dir**: this HF
cache uses the shared two-level `hub/blobs/<xx>/<sha>` layout, so mounting only
the `models--…` dir leaves every blob symlink dangling (that is what the first
attempt hit).

You do **not** have to run this by hand: `mods/dsv41-sglang-overlay/launcher.py`
packs this rank's shards automatically when they are absent (detached; the boot
proceeds on the checkpoint fallback and the packed shards are used next time).
The manual command is for pre-warming or debugging.

## Portability (`/cache/runtime`, no host bind mounts)

The recipe ships **no `executor_config.volumes`** — no `/home/red/...` path, and
`sparkrun recipe validate` no longer reports `non-portable-mount`. Every
non-model, non-image artifact lives under sparkrun's managed runtime cache:

| artifact | container path | host path |
|:--|:--|:--|
| per-rank Engram shards | `/cache/runtime/engram` | `~/.cache/sparkrun/runtime-cache/sglang/deepseek-ai__DeepSeek-V4.1-Flash-9a74d993/engram` |
| boot.py `launch.json` / `api-key` | `/cache/runtime/state` | `…/state` |
| b12x JIT caches | `/cache/runtime/b12x-compile`, `…/b12x-roce` | `…/b12x-compile`, `…/b12x-roce` |

`sparkrun` computes the leaf itself (`core/runtime_cache.py:model_key`, family
`sglang`), creates and chowns it per node, and mounts it at `/cache/runtime`; the
recipes and env never spell the host path. The leaf is node-local NVMe (not
NFS), so packed Engram reads stay local.

The two moving parts:

- `mods/dsv41-sglang-overlay/run.sh` creates and `reown`s the subdirs (it runs
  before the serve command), because mods run as root and the serve user must be
  able to write them.
- `mods/dsv41-sglang-overlay/launcher.py` is the only component that learns the
  node's rank (sparkrun appends `--node-rank` to the serve command on the head
  **and** every worker; the container env has no rank — verified in the
  `sparkrun -vvv run --dry-run` output). It materializes the rank's shards,
  backgrounding the pack when they are absent so a cold boot never exceeds
  sparkrun's ~150 s head-rendezvous wait. `packed=False` in the Engram boot line
  on a first cold boot is expected, not a failure.

What is still required of the host: **the shared HF checkpoint** at
`/cache/huggingface` (never a recipe bind mount). The image is no longer a host
prerequisite — it is vendored at
`littlecedar/dgx-spark-dsv41:canary-roce@sha256:932dd8c2…` and sparkrun pulls it
(`distribution_config.containers.enabled: true`). If you prefer to build it
locally, retag the result `dsv41-4x-spark:canary-roce` and set
`containers.enabled: false`.

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
   `packed=` must name the `/cache/runtime/engram` shard. Missing/identical = stop.
   (`packed=False` on a first cold boot is expected: the launcher packs in the
   background and the next boot reports `packed=True`.)
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


## RoCEnante A/B (2026-10-02) — the single biggest win, VERIFIED

Both arms: same recipe, same boot shape, SPS table absent (verify-all), only
`SGLANG_ROCE_ALLREDUCE`/`DSV41_ROCE_GATHER`/`B12X_ROCE_HCA` flipped. Bench after
two discarded warm-ups, non-streaming, 200 tokens, distinct prompts, greedy.
Boot #5 log: `RoCEnante ready: world=4 hcas=rocep1s0f0,roceP2p1s0f0 gid_index=3
max_size=2097152`.

| t/s (aggregate) | C1 | C4 | C8 | C16 |
|:--|--:|--:|--:|--:|
| NCCL (boot #4) | 27.4 | 62.5 | 73.2 | 155.0 |
| **RoCEnante (boot #5)** | **46.6** | **105.6** | **132.5** | **191.0** |
| ratio | **1.70×** | **1.69×** | **1.81×** | **1.23×** |

The effect is far outside the 7–25% GB10 boot-to-boot spread, so it is real.
**C1 46.6 now exceeds our shipped vLLM/EXL3 TP=4 lane (40.7)** on the same four
nodes. Upstream's 89.7 c1 is still ~2× away; the remaining lever is the SPS
table and their 2200 MHz clock cap convention (ours is uncapped).

**Decision: RoCEnante is shipped in the recipe** (`SGLANG_ROCE_ALLREDUCE=1`).
Rollback is one env line (`SGLANG_ROCE_ALLREDUCE=0`). Correctness smoke still
`27*43 -> 1161`, planets correct; DSpark acceptance unchanged.


## SPS ragged-verify table — TESTED, crashes the Engram path (do not ship)

The SPS table is the one remaining lever below upstream's 89.7 c1, and upstream
itself lists it under **"Not used: … `DSPARK_SPS_TABLE` (crashes the Engram
path)"**. Confirmed here end to end:

1. Generated it in-image against a server booted
   `SGLANG_RAGGED_VERIFY_MODE=static SGLANG_DSPARK_ENABLE_SPS_RECORD=1
   SGLANG_SIMULATE_ACC_LEN=1.0` (the profiler requires all three).
   `--max-batch-size 16` was needed because the default sweep reaches bs=256
   while our graphs capture to 16 ("steps beyond it run eager and poison the
   table"). Result: a 178-byte table, self-check passed.
2. Copied it to `/state/dspark_sps.json` on all four nodes and booted normally
   (RoCEnante on, no record env). boot.py then enabled the scheduler:
   `DSpark ragged-verify scheduler enabled (mode=compact, lag=2, relay_lag=2,
   sps_table=/state/dspark_sps.json, graph_tier=dynamic)`, **and the first mixed
   batch died**:
   `AssertionError: engram target-verify expects one equal block per request, got
   84 tokens for 16 requests of 6` → `Scheduler hit an exception` → server never
   healthy.

So **upstream's production line is verify-all**, and our boot #5 (RoCEnante on,
no SPS table) *is* the production line, not a degraded one. Remove the table
(and the two `DSPARK_*_TABLE` env vars) to reproduce.

**Caveat on the profiler effort:** the table also needed `SKIP_SMOKE=1` — with
`SGLANG_SIMULATE_ACC_LEN=1.0` boot.py's own smoke checks the completion equals
`42`, and simulated decoding returns `42!;`. That is a boot.py-independent
artifact of record mode, not a recipe defect.


## E5 CLOSED — the official checkpoint scores 94.4% too, same failure

AGENTS.md E5 was open because we could not separate EXL3 quantization damage from
base-model limits without running the **release** checkpoint on our own hard
battery. This lane runs the release checkpoint (`deepseek-ai/DeepSeek-V4.1-Flash`,
native MXFP4/F8), so the comparator now exists.

`.scratch/ds4/knapcio/quality_hard_sglang.py` (the hard 18-task tier, adapted to
send `chat_template_kwargs {"thinking": false}`), two independent runs on boot #9:

| arm | hard score | failure |
|:--|:--|:--|
| **EXL3 3.5 bpw (vLLM, shipped lane)** | **17/18 = 94.4%** | `hard-rev` |
| **release checkpoint (SGLang, this lane)** | **17/18 = 94.4%** (run 1 and run 2) | `hard-rev` |

Both miss **the same single task**, `hard-rev` (print a word reversed): EXL3
returned `nurknaps`/`nrukreps`/`nurcraps`; the release checkpoint returns
`nrukrkaps` — wrong the same way. Categories are identical (arith 5/5, code 3/3,
format 3/4, reason 4/4, recall 2/2).

**Verdict: the EXL3 3.5 bpw quantization costs nothing measurable on this
battery — the one failure is a base-model limitation, not quantization damage.**
This is stronger than the earlier "we have NOT shown EXL3 causes it" hedge in
AGENTS.md §7.6: the release checkpoint, independently quantized and served by a
different engine, reproduces the failure at the same task and rate. It also
re-confirms the EXL3 lane as safe to ship as the default-quality lane.

**Caveat:** this is the 18-task hard tier (a discriminating but small battery),
and the SGLang path runs with decoder SWA bounded replay, so prompt-token
logprobs are unavailable and "bitwise vs the release checkpoint" is not
measurable through it. The comparator is exact-match behavior, which is the right
grain for this question.


## Two honesty caveats on the measured numbers

1. **The C1 number is completion-length sensitive.** Our bench requests 200
   tokens but the varied short-answer prompts often `finish_reason=stop` well
   before 200, so wall time includes prefill/TTFT and dilutes the effective
   decode rate. On a single long-generation prompt, three same-boot c1 reps were
   **36.9 / 39.6 / 39.8 t/s**; the varied-prompt aggregate was 46.3–46.6. The
   steady-state **C4/C8/C16** columns (106/133/193) are the robust numbers and
   are what should be compared. Upstream's 89.7 prose c1 is a single 256-token
   sparkDash prompt, so it is not directly comparable to our varied-prompt C1.

2. **The 1M context is *configured and served*, not needle-tested here.** The
   server reports `context_len=1048576`, `max_model_len: 1048576` on
   `/v1/models`, and `full_token=6907904` (KV room for ~6.6 full-length
   requests). A 1M-token needle retrieval is **NOT measured on our cluster**;
   upstream reports needle PASS at 1M on their fleet. Do not claim our lane has a
   verified 1M retrieval until it is run (`bench_needle.py` /
   `scripts/verify/needle*.py` in the upstream repo).


## Standardized `sparkrun benchmark` cross-check (2026-10-02)

Ran the repo's own tool against the live boot, to have an auditable artifact
alongside the custom bench. New profile
`benchmarking/ds4-sglang-depth0-ladder.yaml` (llama-benchy, `depth: [0]`,
`pp: [2048]`, `tg: [128]`, `concurrency: [1,4,8,16]`, `runs: 3`), invoked as

```bash
sparkrun benchmark --cluster ds4tp4v2   --profile benchmarking/ds4-sglang-depth0-ladder.yaml   --skip-run --output .scratch/ds4/knapcio/bench-sglang-depth0   recipes/ds4/deepseek-v4.1-flash-sglang-tp4-knapcio.yaml
```

Artifact: `.scratch/ds4/knapcio/bench-sglang-depth0.json`.
(`--skip-run` needed the *head* pinned to `.32`; sparkrun's stale-deployment
lookup pointed at a worker, which 404s — and `--skip-run`'s host detection
resolves `ssh_user` from config, so `~/.ssh/config` must pin `User red` for
`.32/.33` too.)

| t/s (decode-phase `tg_throughput`, mean of 3) | c1 | c4 | c8 | c16 |
|:--|--:|--:|--:|--:|
| **standardized profile** (pp=2048 prompts) | 43.6 | 91.3 | 99.4 | 102.1 |
| per-stream (`tg_req_throughput`) | 43.6 | 29.1 | 16.6 | 10.7 |
| short-prompt harness (README C1 contract) | 46.6 | 105.6 | 132.5 | 191.0 |

**The harnesses diverge, and the reason is prompt length.** llama-benchy's
depth-0 cell uses 2048-token prompts; the short-prompt harness uses ~17-token
prompts. At c1 they agree (43.6 vs 46.6, well inside llama-benchy's own c1 run
spread of 35.7–48.4); at c16 they diverge 1.9× because the concurrency cell in
the standardized profile is dominated by 16×2048 tokens of prefill. **So quote the
concurrency ladder only with its prompt length attached.** The README's `C1 t/s`
column keeps the short-prompt number (matching the column's contract); the
standardized profile is the auditable cross-check.

Also visible in the artifact: `tg_req_throughput` at c16 is bimodal (7.4–20.5),
i.e. the same per-request scheduling scatter the EXL3 lane documents (§11) — read
the JSON's `tg_req_*`, not the aggregate column, when comparing configurations.
