# DS4 — `recipes/ds4/` agent & developer guide

DeepSeek V4.1-Flash on NVIDIA DGX Spark (GB10, SM121, 128 GB unified LPDDR5X
per node, 2× ConnectX-7 200 GbE RoCE). Read this before touching the recipe, the
mod, or the guards in this directory.

**Scope of this file.** This directory now ships **one** recipe — the SGLang
"knapcio" lane:

- `deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml` — SGLang, TP=4, 1M context,
  official MXFP4/F8 checkpoint, DSpark verify-all, Engram on node-local NVMe,
  RoCEnante RDMA.
- [`README.md`](README.md) — the user-facing guide (what it is, requirements,
  how to run, limits).

**The EXL3 / vLLM lane is archived.** Five vLLM recipes over
`bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard`, the former consolidated
agent guide, the DSpark TP=3/TP=6 study, the memory-reclaim plan, the
performance triage, and the session notes were moved to
[`attic/ds4/`](../../attic/ds4/) when this recipe was chosen for go-live. They
are not shipped and not covered by the guards here. The attic copy of the agent
guide still holds the load-bearing *model* analysis (anatomy, the residency
wall, the DSpark k-sweep) and is worth reading for background, with the caveat
that it is a frozen snapshot.

**Evidence vocabulary (repo convention).** **VERIFIED** — read from a primary
artifact (a boot log, a pinned image, source at a pinned commit) or measured on
our devices. **LIKELY** — strong secondary evidence. **SPECULATIVE** — reasoning
without a source; do not build on it. Numbers derived here say "computed here";
numbers someone else measured name who. Never promote `LIKELY` into unlabelled
fact.

---

## 1. The design in one paragraph

The checkpoint is 510 GB of native MXFP4/F8 weights. 203 GB of it is the two
Engram embedding tables, which cannot coexist with the weight shards in a
single node's 128 GB unified pool. The lane therefore runs on a purpose-built
SGLang image whose reader streams Engram rows from **node-local NVMe**, packed
one shard per rank. The image's `boot.py` builds the entire `sglang.launch_server`
argv from environment variables; sparkrun appends `--dist-init-addr/--nnodes/
--node-rank` assuming `sglang serve`. The mod's `launcher.py` is the adapter
between the two: it consumes sparkrun's flags, maps them onto boot.py's
environment, applies the production configuration, resolves the checkpoint, and
`execve`s `boot.py`.

Upstream: [`knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4`](https://github.com/knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4)
@ `58f2321`, a downstream of MiaAI-Lab's recipe. The launcher, adapters, b12x
kernels, and measurement design are theirs, kept under their licences.

---

## 2. Files and the call chain

```
recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml
  mods: "@littlecedar/mods/dsv41-sglang-overlay"
    run.sh            # fail-closed compatibility gate; creates + reowns cache dirs
    launcher.py       # RECIPE_ENV production config; rank handling; checkpoint resolution
      -> execve: /opt/dsv41/boot.py run     # builds the full sglang.launch_server argv
```

The recipe's `command:` is a one-line call to the shim:

```
python3 /workspace/mods/dsv41-sglang-overlay/launcher.py --boot
  --model {model} --port {port} --tp {tensor_parallel}
  --served-model-name {model} --context-length {max_model_len}
```

sparkrun appends the per-node distribution flags; the launcher consumes them.

---

## 3. Recipe invariants (all guarded)

These are load-bearing and each has a guard in
`tests/test_ds4_recipes.py::SglangLaneContract`.

1. **No `env:` block.** Everything — the production config *and* the checkpoint
   location — lives in the launcher, so it travels with the mod rather than with
   each recipe. The recipe passes the repo id via `{model}`; the launcher derives
   the snapshot path. Guarded by `test_recipe_env_is_empty`. Because the launcher
   applies `RECIPE_ENV` with `env.update`, this is also where every production
   switch lives: there is **no recipe-side knob** for e.g. `DSV41_FAST_LOAD`
   (§7.1) — flip it in the launcher, or not at all.
2. **TP flows through `defaults` → `command` → launcher.** sparkrun does **not**
   emit `--tp-size` when a `command:` template is present; it substitutes the
   placeholder. The template emits `--tp {tensor_parallel}` and the launcher maps
   it onto `TP_SIZE`. Without the mapping, boot.py silently falls back to TP=3 on
   a 4-node cluster. Guarded by `test_tp_flows_through_command_to_launcher`.
3. **Context length flows the same way.** `--context-length {max_model_len}` →
   `CONTEXT_LENGTH`, applied *after* `RECIPE_ENV` so the recipe (and `-o
   max_model_len=…`) wins. boot.py asserts `4096 ≤ CONTEXT_LENGTH ≤ 1048576`.
   Guarded by `test_context_length_wired_to_launcher`.
4. **The image is vendored and digest-pinned.**
   `littlecedar/dgx-spark-dsv41:canary-roce@sha256:4e5002ab…`. Guarded by
   `test_image_is_vendored_and_pinned`.
5. **No `distribution_config:` block.** sparkrun's default already distributes
   both the model and the container (`core/recipe.py:_default_distribution_config`).
   Omitting the block is behaviorally identical and one fewer thing to drift; a
   reintroduced `enabled: false` would strand workers. Guarded by
   `test_distribution_config_omitted`.
6. **No host bind mounts and no host device names.** No `volumes:`; no env value
   names a host adapter. Guarded by `test_no_host_bind_mounts`,
   `test_no_host_device_names_in_env`, `test_managed_comm_env_not_pinned`.
7. **The entrypoint is cleared** (`executor_config.entrypoint: ""`) so the
   recipe's `command:` runs instead of the image's ENTRYPOINT. Guarded by
   `test_entrypoint_cleared`.

`readiness.port_timeout_s: 7200` / `health_timeout_s: 3600` are deliberately
generous — a cold boot reads/packs a 510 GB checkpoint.

---

## 4. The mod (`mods/dsv41-sglang-overlay/`)

**`run.sh` is a fail-closed compatibility gate.** It asserts that boot.py, the
adapter `sitecustomize.py`, b12x_next, and the engine's `engram.py` all exist,
logs the overlay paths, creates the cache subdirectories, and `reown`s them (mods
run as root; the serve user must be able to write them). It modifies **no image
file** — the overlay is gated by the upstream repo's own in-image tests.

**`launcher.py` owns the production configuration** in `RECIPE_ENV`. It applies it
with `env.update(RECIPE_ENV)`, **not** `setdefault`: the image bakes
`STATE_PATH=/state`, `DSV41_CACHE_GIB=16`, `PYTORCH_CUDA_ALLOC_CONF=…True`,
`SGLANG_RUST_BUILD_MODE`, and `OFFLOAD_MODE` into its ENV, and `boot.py` is
`execve`'d from that process, so a `setdefault` would let the image win (that bug
was caught live: `launch.json` went to the unwritable `/state` and the allocator
reverted to the `expandable_segments:True` NaN-logits mode). `RECIPE_ENV` is
disjoint from the recipe-owned keys.

Three launcher behaviours that are easy to get wrong:

- **Rank is learned from sparkrun's flags, never the container env.** sparkrun
  appends `--node-rank` to every node's serve command; the container env has no
  rank. Only the launcher sees it, so the launcher — not the mod — materializes
  this rank's Engram shards.
- **Checkpoint resolution self-heals.** `resolve_checkpoint()` derives
  `MODEL_PATH`/`DSV41_SOURCE` from the fixed in-container HF cache
  (`/cache/huggingface/hub/models--<org>--<name>` → `refs/main`, else any
  snapshot with `config.json` and `model.safetensors.index.json`). A cache
  re-resolving to a new hash cannot break the recipe, and no `snapshots/<hash>`
  appears in the recipe. (A host-side `MODEL_PATH` bind is left alone.)
- **Engram packing is detached.** When this rank's shards are absent, the
  launcher spawns the packer in the background so a cold boot never exceeds
  sparkrun's ~150 s head-rendezvous wait; the boot proceeds on the checkpoint
  fallback and the next boot uses the packed shards. `packed=False` on a first
  cold boot is expected.
- **It writes `/tmp/sparkrun_health_port`** as the rendezvous file the image's
  healthcheck reads (the image bakes `STATE_PATH=/state`, so a
  `$STATE_PATH`-relative path would not have round-tripped).

Cache locations (all under sparkrun's managed runtime cache, mounted at
`/cache/runtime`): `engram`, `state`, `b12x-compile`, `b12x-roce`. The host leaf
is computed by sparkrun (`core/runtime_cache.py`) and never spelled in the
recipe.

**Mod-reference resolution.** `@littlecedar/mods/…` resolves from the node's
**registry git clone**, not the synced working tree, so iterating on the mod
requires committing it (and pushing/refreshing the registry cache) before a
launch will see the new code. `sparkrun recipe validate` does **not** check mod
existence; only a real launch (or `-n`, which skips the registry sync) surfaces a
resolution failure.

---

## 5. The image

`littlecedar/dgx-spark-dsv41:canary-roce@sha256:4e5002ab58b5cca670e2624c6a0d0…`
(image `sha256:18e36391…`), arm64-only, 33.5 GB, base `lmsysorg/sglang:dev-dsv41`
+ SGLang `f80c91a4b` + the adapter overlay + b12x/b12x_next. Rebuilt 2026-10-03
for a **dynamic HEALTHCHECK**: `boot.py health` now discovers the served port at
runtime (env → the launcher's `/tmp/sparkrun_health_port` → the engine's own
`--port` from `/proc/<pid>/cmdline` → a LISTEN port from `/proc/net/tcp{,6}` →
image default). Before this, a server on any port other than 8888 reported
`Up … (unhealthy)` in `sparkrun status` while serving fine — Docker freezes
`Config.Env` at `docker run`, so a value set at runtime by the launcher is below
its view. The recipe's `readiness:` never played a part.

**Rebuilding the image.** It is arm64-only and reproducible from upstream's repo
at the pinned revision:

```bash
git clone https://github.com/knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4.git
cd DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4 && git checkout 58f232155917d388b6053eca079c617fd306c33c
bash scripts/fetch-sglang-canary.sh            # stages the dsv4.1 tree @ f80c91a4b
docker build -f Dockerfile.canary-roce -t dsv41-4x-spark:canary-roce .
```

To build locally instead of pulling, retag the result
`dsv41-4x-spark:canary-roce` and add
`distribution_config: { containers: { enabled: false } }` to the recipe.

| image attribute | value |
|:--|:--|
| Registry digest | `sha256:4e5002ab58b5cca670e2624c6a0d0799642914f04487ea130c71e7f525fa9c05` |
| Image ID | `sha256:18e36391488edb088cc70e2f8d9a3e16eb82f653496fa565526a6ffd6b7c6890` |
| Base | `lmsysorg/sglang:dev-dsv41` |
| Upstream overlay | knapcio `58f2321`, SGLang `dsv4.1` @ `f80c91a4b` |
| Built | 2026-10-03 on `10.0.4.30` (rebuilt for the dynamic HEALTHCHECK) |
| Size | 33.5 GB (arm64) |

The build reuses the base and overlay layers (Docker layer cache), so a
`boot.py`-only rebuild ran ~4–5 min despite the 33.5 GB size; the new digest
must then be redistributed to all four workers before a boot.

The image's torch is **2.13.0+cu130** (VERIFIED by probing the image). PyTorch
2.13 renamed `all_gather_into_tensor` → `all_gather_single` and
`reduce_scatter_tensor` → `reduce_scatter_single`; the image's SGLang tree and
vendored kernels still call the old names, so each call logs a once-per-callsite
`FutureWarning` via `torch/distributed/c10d_logger.py:83`. The launcher silences
**only** that re-emission with a **module-scoped** filter
(`PYTHONWARNINGS=ignore::FutureWarning:torch.distributed.c10d_logger`); a
message-scoped filter does not take (the leading backtick defeats `re.match`),
and a blanket `ignore::FutureWarning` would hide unrelated warnings. Guarded by
`test_torch_2_13_collective_rename_warning_suppressed`.

---

## 6. Fabric and NCCL

The fleet is two RoCE planes (`192.168.0.0/24` on `rocep1s0f0`,
`192.168.1.0/24` on `roceP2p1s0f0`), **full mesh** (a switched fabric, not a
ring), port 1 ACTIVE, port 2 DOWN, RoCEv2 GID index 3.

**No adapter/interface name is pinned anywhere.** `NCCL_NET`, `NCCL_IB_HCA`,
`NCCL_IB_GID_INDEX`, `NCCL_IB_DISABLE`, and `NCCL_CROSS_NIC` are filled by
sparkrun's own InfiniBand probe, which includes only the ACTIVE ports (dropping
the DOWN `*s0f1`). `B12X_ROCE_HCA` is deliberately unset: it takes a literal HCA
list (a host device name), and b12x's RoCEnante falls back to the detected
`NCCL_IB_HCA` when unset (`roce_oneshot.py:85,99` → `discover_hcas`). Verified
live: `RoCEnante ready: world=4 hcas=roceP2p1s0f0,rocep1s0f0 gid_index=3`.

The launcher keeps only device-free transport *tuning*:
`NCCL_P2P_DISABLE`, `NCCL_SHM_DISABLE`, `NCCL_CUMEM_ENABLE`, `NCCL_BUFFSIZE`,
`NCCL_LL128_BUFFSIZE`, `NCCL_PROTO`, `NCCL_MAX_NCHANNELS`, `NCCL_DEBUG`.

`NCCL_BUFFSIZE` is a NCCL **connection-buffer byte size** (1 MiB here), **not** a
token count; it is deliberately not wired to `CONTEXT_LENGTH`. Upstream pairs
`NCCL_BUFFSIZE=1048576` with `CONTEXT_LENGTH=262144` in one profile and with
`1048576` in another, proving the two are independent. Guarded by
`test_nccl_buffsize_is_not_context_length`.

---

## 7. Deliberately off

- **`DSPARK_SPS_TABLE` / `DSPARK_STS_TABLE`** — the ragged-verify cost tables.
  Absent, boot.py stays on the verify-all schedule. Tested and rejected: with a
  fitted table the scheduler enables and the first mixed batch dies with
  `AssertionError: engram target-verify expects one equal block per request, got
  84 tokens for 16 requests of 6` → server never healthy. Upstream's own README
  lists it as not used. **Do not ship it** (guard: `test_sps_table_absent`).
- **`DSV41_FAST_LOAD=0` (shipped).** Upstream's eager loader is off: it buys
  ~220 s per boot and costs 3–13% of the KV pool. Mechanism and the A/B that
  would replace the number: §7.1 below.
- **`DSV41_CERT_HEAD`** — -0.5 ms/step at c1 but slower from ~10 requests.
- **`DSV41_ENGRAM_DRM_NODE`** — needs a host display-reserve change.

RoCEnante is **on** (`SGLANG_ROCE_ALLREDUCE=1`, `SGLANG_ROCE_MAX_SIZE`,
`DSV41_ROCE_GATHER`); rollback is one line.

### 7.1 Fast load (`DSV41_FAST_LOAD`) — shipped `0`

**Decision.** The launcher sets `"DSV41_FAST_LOAD": "0"`. The image does not set
the variable (`Dockerfile.canary-roce` `ENV` carries only `PYTHONPATH`,
`MODEL_PATH`, `STATE_PATH`, `OFFLOAD_MODE`, `DSV41_CACHE_GIB`), and
`adapter/fast_load.py:enabled()` defaults false, so `0` is the stock SGLang
safetensors loader. We set it explicitly to record a deliberate choice rather
than an inherited default.

**What it trades** (upstream's numbers, not ours — `VERIFIED` from the vendored
source's docs, `.scratch/ds4/knapcio/docs/history.md:121,127` and
`docs/fast-load.md`, which back the README caveat):

| at EP2, same image, same night (2026-09-18) | stock loader | `DSV41_FAST_LOAD=1` |
|:--|--:|--:|
| engine start (`scheduler_e2e`) | 343–354 s | 124–129 s |
| `max_total_num_tokens` | 7.47–7.82M | 6.71–7.27M |
| bytes reaching the model | — | bitwise identical |
| decode / prefill / needle | — | unchanged |

**Mechanism, not a leak.** SGLang sizes the pool from the head's
`psutil.virtual_memory().available` (`get_available_gpu_memory`, the integrated-GPU
branch — on GB10 "device memory" is system RAM). The fast loader reads each
rank's tensors eagerly into pinned host slabs and releases everything before the
pool is sized, but ~0.8–1.5 GB has still left `MemAvailable` at that instant, and
it shows in no counter (not shmem, not page cache, not the CUDA allocator —
upstream traced most of it to driver staging state from pageable buffers and made
the buffers pinned to close the gap). There is therefore no env knob that gets
the pool back while keeping the fast path; it is one or the other.

**Not our measurement.** The 3–13% is EP2 on the 2026-09-18 stack. This lane is
**EP1**, and upstream's later pinned-slab rework moved the pool **+0.73M tokens**
against its per-tensor precursor at EP1 (`docs/fast-load.md`), so the interval
here is probably smaller. `SPECULATIVE` on any specific EP1 delta — see the boot9
receipt below for the one EP1 number we hold.

**What our fleet actually measured.** One EP1 head log exists:
`.scratch/ds4/knapcio/logs/boot9-head-serve.log` (2026-10-02). It booted with
`DSV41_FAST_LOAD` **on**, so it is not the shipped config, but it is the only real
receipt we hold:

```
DSV4 memory calculation: … bytes_per_full_token=1670.75, available_bytes=11.71 GB, full_token=6786560
DSV4 pool sizes: full=6786560, …            # the budget derived from MemAvailable
DSV4 pool sizes: full=4000000, …            # after the MAX_TOTAL_TOKENS=4000000 pin
max_total_num_tokens=4000000, context_len=1048576, available_gpu_mem=21.18 GB
```

So on our hardware the fast loader left a **6.79M**-token budget (inside upstream's
6.71–7.27M fast-loader interval), and the server then **pinned the pool to 4,000,000**
regardless.

**Shipped-config ceiling, measured 2026-10-06 (`.30/.31/.32/.33`, stock loader, 0.80).** The
boot9 log above is fast-loader; these four boots are the shipped config:

```
DSV4 memory calculation: … bytes_per_full_token=1670.75, available_bytes≈15.9 GB, full_token=9493504..9589504
DSV4 pool sizes: full=<budget>   # what MemAvailable permits at 0.80
DSV4 pool sizes: full=<pin>      # what MAX_TOTAL_TOKENS selects, clamped to the budget
```

| `MAX_TOTAL_TOKENS` pin | served `max_total_num_tokens` | free mem after boot |
|--:|--:|--:|
| 4,000,000 (old shipped) | 4,000,000 | 25.10 GB |
| 9,000,000 | 8,999,936 | 14.39 GB |
| 9,400,000 (now shipped) | 9,399,808 | 13.68 GB |
| 10,000,000 | 9,589,504 (clamped) | 13.14 GB |

**The true ceiling is `full_token` ≈ 9.5–9.6M tokens**, stable to ~1% across boots; a larger pin
is clamped, never refused. The old 4M pin used **~58% of the ceiling**, so it was raised to
**9,400,000**. `mem_fraction_static` is `(weights + KV pool) / capacity` (SGLang
`memory_hook.py`), so any pin ≤ `full_token` sits inside the same 0.80 budget and leaves the same
~20% outside it for transients — raising the pin does not eat the reserve.

**Pool is page-shared, not extent-reserved.** Unlike the TensorFold lane, SGLang does not reserve
each stream's declared window: 16 concurrent 1M-claiming requests were all admitted and decoded
(`running-req` = the `MAX_RUNNING_REQUESTS=16` cap, zero errors, zero queue). Concurrent-1M-stream
count is bounded by `MAX_RUNNING_REQUESTS` and total *actual* tokens (<9.6M), not by per-stream
reservation. **`full token usage` reads 0.00 even under real draw in this build — do not use it.**

**Still owed:** a 1M cold-prefill after the raise. With `DSV41_INDEXER_CHUNKED=1` the per-chunk
transient is bounded (~2 GB logits) and upstream measured head low-water 6.6–7.7 GB during cold
262k–1M prefills; the 9.4M pin leaves 13.68 GB at boot, so it should hold — but it was not re-run.

**1M cold prefill VERIFIED 2026-10-06 (after a fleet reset).** A ~1M-token cold prompt ingested at
**2909 tok/s** and replied correctly at the 9.4M pin. Host available dipped to ~5 GB low-water
during the prefill (the indexer transient draws ~9 GB on top of the 13.7 GB pool) then recovered
to 10 GB — so 9.4M leaves enough but the head is near its floor during a 1M prefill. The pin is
now boot- and long-prefill-verified on all four nodes.

**Do not raise `MEM_FRACTION_STATIC`.** A 0.90 probe wedged three of four nodes on 2026-10-06
(GPU pool *is* host memory on GB10; userspace/SSH dead while ping alive). Keep **0.80**: it is what
caps the pool and keeps the transient reserve. See NOTES.md "INCIDENT".

**A/B if you want the shipped-config number** (mirrors §10's discipline; read the pool
from the boot log, never computed):

1. Boot the shipped recipe; record `DSV4 memory calculation: … full_token=<N>`
   from `/tmp/sparkrun_serve.log` inside the container.
2. Flip `"DSV41_FAST_LOAD": "1"` in the launcher, commit it (mod references
   resolve from the registry git clone, §4), boot again, record the same line.
3. Three boots each. `full_token` varies boot to boot (upstream saw 6.71–7.27M
   across fast-loader boots alone); a same-config control on either side is part
   of the protocol, and a single pair of boots resolves nothing.
4. `DSV41_FAST_LOAD_N_EXPERTS` was dropped with the gate: it is a fallback for
   expert-count detection that only `fast_load` reads, and it defaults from
   `config.json`'s `n_routed_experts` (384) when absent. Restoring the gate needs
   no restore of this key.

---

## 8. Boot gates (in order) and timings

Read these before believing any number. A boot that reaches ready but fails a
gate is not a win.

1. `[dsv41-sglang-overlay] overlay gate OK` and `launcher: boot.py run NNODES=4
   NODE_RANK=<r> …` — rank must differ per node.
2. `Exact nvme Engram layer=… rows=[a,b)` — row range must **differ per rank**;
   `packed=` names the `/cache/runtime/engram` shard. Missing or identical: stop.
3. `[moe_b12x_next] armed` — routed MoE on the b12x_next kernel, not a Triton
   fallback.
4. `DSV4 memory calculation: … full_token=<N>` — the granted KV pool. With the
   stock loader shipped, expect the larger pool (7.47–7.82M on upstream's EP2
   stack, §7.1); a 6.71–7.27M reading means `DSV41_FAST_LOAD` is on.
5. `Mean acceptance length > 1` on `Decode batch` lines (DSpark working).

**Timings:** boot to ready **~9 min cold**; TTR observed 171–270 s once the
checkpoint and image are resident. A first cold boot also packs Engram in the
background. **Both of those were observed with the fast loader on**, which is not
what ships: the stock loader's weight read is the slow one (~220 s more), so a
fresh boot on the shipped config will land above these figures. They are kept as
the fast-loader reference, not as the shipped recipe's boot time (§7.1).

**Cluster hygiene before any boot test:** a killed/abandoned `sparkrun run`
leaves containers holding the serve port. Because sparkrun uses `--network=host`,
the next boot's healthcheck can pass against the **old** server while the new one
fails to bind — a false "healthy". Check `sparkrun status` /
`docker ps -a | grep sparkrun` on every node first.

---

## 9. Guards and the verification ritual

`tests/test_ds4_recipes.py` is stdlib-only and parses recipe **text** with a
~60-line regex parser (no PyYAML — `tests/` and `tools/` must run on a head node,
in a container, and on a laptop with no venv). It has its own `render()`; guards
inspect the rendered command, not the template. Every guard has a proven
**negative control** (in `SglangLaneNegativeControls`), and controls mutate
strings in memory so nothing on disk is touched. Guards strip whole-line comments
before reading a block, because the recipes' prose *names* the flags it explains
the absence of.

**This guard suite no longer covers the EXL3 / vLLM lane** — those recipes and
their `Exl3LaneContract` guards moved to `attic/ds4/` with them. If the lane is
ever restored, its guards come back with it.

Ritual before any hardware claim:

```bash
set -e
H=$PWD/.local/sparkrun-home; mkdir -p "$H"
uv run python -m unittest discover -s tests
for f in recipes/*/*.yaml; do HOME="$H" sparkrun recipe validate "$f"; done
HOME="$H" sparkrun run recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml -H <node> -n
for s in mods/*/*.sh; do bash -n "$s"; done
for p in mods/*/*.py tools/*.py; do uv run python -m py_compile "$p"; done
find mods tools -name __pycache__ -type d -exec rm -rf {} +
```

`sparkrun recipe validate` **plain** (not `--strict`): several recipes in the
registry legitimately fail `--strict` on accepted warnings, and a `suggestion`
is not a defect. A clean `validate` is not evidence a recipe boots — read the
rendered line and the boot log.

---

## 10. Measurement discipline (this lane)

- **Quote the harness with the number.** The short-prompt harness (~17-token
  prompts) and the standardized `sparkrun benchmark` profile (2048-token prompts)
  agree at c1 and diverge ~1.9× at c16, because the concurrency cell is then
  dominated by 16×2048 tokens of prefill. The README's `C1 t/s` contract is the
  short-prompt number.
- **C1 is completion-length sensitive.** The bench requests 200 tokens but the
  varied short-answer prompts often stop early, so wall time includes prefill and
  dilutes the effective decode rate. The steady-state C4/C8/C16 columns are the
  robust ones.
- **GB10 inter-boot scatter is 7–25%.** Three runs resolve nothing under ~15%;
  run a same-config control before calling an arm a win.
- **DSpark acceptance is workload-dependent** (~3/step on prose, ~6 on code). A
  DSpark number without an accept length is not a number; state the
  reasoning-effort budget too (`chat_template_kwargs {"thinking": false}` here).
- **Read the served pool from the boot log**, never computed. The loader setting
  is part of the boot's identity: quote `DSV41_FAST_LOAD` with any pool number,
  because it moves the pool 3–13% (§7.1). The fast path logs
  `DSV41 fast load ARMED: …` when it is on and nothing when it is off, so a
  missing ARMED line is the only in-log hint — a bare pool figure does not
  identify which loader produced it. (The launcher's env is also invisible to
  `docker exec env`, §11.)
- **`sparkrun benchmark --profile` resolves from the registry cache**, not the
  working tree. The serve log is `/tmp/sparkrun_serve.log` **inside** the
  container (`docker logs` is empty). Containers are reaped after a run; use
  `--no-rm` to keep one.

---

## 11. Negative results and do-not-retry

- **EP_SIZE=2 does not work.** It loads (clears the MXFP4 MoE `%128` check) but
  dies at the first decode plan: `planned dynamic direct routing is unsupported
  for this launch shape`. The production profile is **EP_SIZE=1**.
- **The SPS ragged-verify table crashes the Engram path** (section 7).
- **Pinning a host adapter or a `snapshots/<hash>` path breaks portability.** The
  former pins one machine's adapter naming; the latter breaks when the cache
  re-resolves (the launcher self-heals it).
- **`docker exec <c> env` is not a valid probe** for anything the launcher sets —
  the launcher rewrites its own environment before `execve`, so `docker exec`
  (a fresh shell) shows the image's baked values. Read the launcher's log and the
  tools' output instead.
- **`sparkrun run --dry-run` skips the InfiniBand detection step**, so it prints
  "No InfiniBand detected" and renders no `NCCL_IB_*` env — a false negative. Do
  not conclude anything about detection from a dry run.
- **The old "SGLang cannot serve V4.1-Flash" verdict is superseded** for this
  purpose-built image. It was correct for the published images available at the
  time (no single image was both V4.1 and b12x; the MXFP4-Cutlass MoE rejected
  the TP=4 partition).

---

## 12. TensorFold TP=2 lane (`deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml`)

A second, independent lane in this directory: DeepSeek-V4.1-Flash on **two**
GB10 nodes, served by the TensorFold `deepseek_v41` engine over the Mia-AiLab
**EXL3 2.9bpw** checkpoint. It does not share code with the knapcio SGLang lane
above; read this section before touching it.

### 12.1 What it is

- Engine: [`bertholomus/TensorFold`](https://github.com/bertholomus/TensorFold),
  branch `deepseek-v41-tp2`, a fork of [ashhart/TensorFold](https://github.com/ashhart/TensorFold)
  v0.6.3 (Apache-2.0). The `deepseek_v41` family is a clean-room re-implementation of DeepSeek's
  MIT inference code; the fork's `tools/dsv41/ATTRIBUTION.md` records every source.
- Checkpoint: `Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw` (~197 GB, 39 shards, MIT).
  TensorFold's CUDA engine reads **EXL3 only** (`families/deepseek_v41/__init__.py`:
  `QUANT_METHODS = {"cuda": ("exl3",)}`, `check()` refuses any other `quant_method`), so the
  official MXFP4 checkpoint will not load here. The EXL3 repo's `config.json` has
  `model_type: deepseek_v41`, which is what `families.detect()` keys on.
- Engram: the EXL3 quant left the two FP8 Engram tables native; they are **not** in the EXL3
  repo. The engine reads them from DeepSeek's original shards **47 and 48** (~95 GB each), which
  carry `layers.{1,14}.engram.embed.{weight,scale}` and the `q_weight`/`k_weight` linears.
- Context: the served command ships the model's **full 1,048,576-token window** (see 12.13 for why
  the maximum context and the maximum KV cache are the same change here). Upstream measured its lane
  at 262,144 and found a needle at 1,039,833; the ceiling the engine enforces is 1,048,576.

### 12.2 Files and the call chain

```
recipes/ds4/deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml   (runtime: sglang -- the shim path)
  mods: "@littlecedar/mods/tensorfold-dsv41-launcher"
    run.sh        # fail-closed gate: tensorfold on PATH, launcher.py + HF cache present;
                  #   creates + re-owns /cache/runtime/tensorfold/{rank-cache,torch-extensions}
    launcher.py   # RECIPE_ENV production config; --dist-init-addr/--nnodes/--node-rank -> TensorFold flags
      -> execvp: tensorfold serve <MODEL_DIR> --tp 2 --rank R --master HOST --master-port PORT ...
```

The recipe's `command:` is a one-line call to the shim:

```
python3 /workspace/mods/tensorfold-dsv41-launcher/launcher.py --boot
  --model {model} --port {port} --tp {tensor_parallel}
  --served-model-name {served_model_name} --context {max_model_len}
```

sparkrun appends `--dist-init-addr HOST:PORT --nnodes N --node-rank R` to every node's serve
command; the shim consumes all three.

### 12.3 Why `runtime: sglang` and a shim (not a custom runtime plugin)

sparkrun's runtime vocabulary is a fixed set of in-tree `RuntimePlugin`s plus feature-gated
external plugins (`core/bootstrap.py`, `core/external_plugins.py`); an unknown `runtime:` name is
fatal at launch, and there is no YAML-only way to define one. The established house pattern — used
by the knapcio lane just above — is to declare `runtime: sglang`, give the recipe an explicit
`command:` template, and let a mod's Python shim consume sparkrun's appended node flags and exec a
foreign engine. This lane does the same, and inherits sparkrun's model/image distribution, the
InfiniBand/NCCL env probe, the managed runtime cache, and the readiness watcher for free. A custom
`RuntimePlugin` would be cleaner in the abstract, but it requires an out-of-tree plugin on every
node's `plugins.paths`, which is a bigger deployment surface than one mod.

### 12.4 The two load-bearing shim behaviours

1. **The rendezvous port must be passed through.** sparkrun's native-cluster launch waits for the
   head to open the rendezvous port before it starts the workers, and the port it gates on is the
   one in `--dist-init-addr` (`runtimes/_cluster_ops.py` `gate_port`; default 25000). TensorFold's
   `TCPStore` binds `--master-port` (its own default is **29551**). The shim therefore parses
   `--dist-init-addr HOST:PORT` and emits `--master-port PORT`; if it did not, the head would open
   29551 while sparkrun polls 25000 and declare the launch dead.
2. **The rank comes only from `--node-rank`.** sparkrun passes it to the head (0) and the worker
   (1); the container environment carries no rank. Only the shim sees it, so the shim sets
   `--rank`. Getting it wrong makes both ranks act as rank 0 (the `TCPStore` then has a duplicate
   server and the NCCL unique-id handoff breaks).

TensorFold's rank 0 serves HTTP and drives the rounds; rank 1 follows it (`engine.follow()`).
sparkrun launches the head first and waits for the rendezvous port, then starts the worker in
parallel; because TensorFold's rank 1 blocks in `TCPStore(...)` until rank 0 opens the store, the
head-first order is the one that works (do not be misled by upstream's "start rank 1 first" — that
advice is for starting the *processes* by hand, where the worker must be listening before the head
connects its `Link`/`Watchdog` sockets).

### 12.5 The mod (`mods/tensorfold-dsv41-launcher/`)

`run.sh` is a fail-closed pre-serve gate. It asserts `tensorfold` is on PATH, `launcher.py` exists,
and `/cache/huggingface/hub` is mounted; it creates and `reown`s the managed runtime cache
subdirectories the launcher writes. It modifies no image file and does not fail closed on a missing
Engram directory (the engine loads without them and only prints a warning — see 12.7).

`launcher.py` owns the production configuration (`RECIPE_ENV`), resolves the checkpoint, and execs
`tensorfold serve`. The env it sets:

| Env | Value | Why |
|:--|:--|:--|
| `TF_DS_REPLAY` | `1` | bounded decoder replay (DeepSeek's deployment mode); the engine default is exact prefill, which is slower and can OOM at 128K |
| `TF_DS_PREFILL_CHUNK` | `2048` | upstream's served chunk |
| `TF_DS_RANK_CACHE` | `/cache/runtime/tensorfold/rank-cache` | ~106 GiB/rank weight cache; paid once per host |
| `TF_DS_RANK_CACHE_READERS` | `32` | upstream's value |
| `TF_DS_WARM_LENGTHS` | `1,17,33,131,514,1024,2113` | upstream's warm-up lengths |
| `TORCH_EXTENSIONS_DIR` | `/cache/runtime/tensorfold/torch-extensions` | persist the first-start CUDA-extension compile |
| `TF_DS_TOKEN_MAP` | `/cache/runtime/tensorfold/token_map.json` | Engram hash table, built once from `tokenizer.json` |
| `TF_DS_ENGRAM` | `/cache/huggingface/hub/dsv41-engram` | only when shards 47/48 are present |
| `HOME` | `/cache/runtime/tensorfold` | the container runs as the ssh user, who may lack a writable home |

`serve` always runs with `--parallel 4 --mtp-drafts 5 --temperature 0 --no-update-check`. The first
three are upstream's served line; `--no-update-check` keeps the boot off the network.

### 12.6 Checkpoint resolution

The recipe passes the repo id in `{model}` (sparkrun does not rewrite it for a custom command). The
shim derives the in-container snapshot from the fixed HF cache mount:
`/cache/huggingface/hub/models--Mia-AiLab--DeepSeek-V4.1-Flash-EXL3-2.9bpw/snapshots/<hash>` via
`refs/main`, else the newest config-bearing snapshot. An absolute path (a pre-placed model, or
`-o model=...`) is used as-is. No `snapshots/<hash>` appears in the recipe, so a cache re-resolving
to a new hash cannot break it.

### 12.7 Engram is distributed out-of-band

The two Engram shards are **not** distributed by sparkrun: they belong to the *official*
`deepseek-ai/DeepSeek-V4.1-Flash` repo, and pulling that whole repo just to fetch shards 47/48 ships
~285 GB of weights the engine never reads. Instead the shards live alongside the HF cache at
`/cache/huggingface/hub/dsv41-engram` on each node. To pre-warm a node:

```bash
# on the head (which already has the official checkpoint cached), copy the two
# shards from the snapshot (rsync -L follows the symlinks into real files):
D=~/.cache/huggingface/hub/models--deepseek-ai--DeepSeek-V4.1-Flash/snapshots/<hash>
rsync -aL "$D"/model-0004{7,8}-of-00048.safetensors \
  red@<node>:/home/red/.cache/huggingface/hub/dsv41-engram/
```

If the directory is absent, the engine still boots and serves, with
`[tensorfold] WARNING: no Engram tables (TF_DS_ENGRAM): output will be degraded`; the mod and shim
both report the state without failing. `_default_engram()` also looks for a `*Engram*` sibling of
the model directory, but that location is inside the HF cache and would be wiped by a cache re-sync.

### 12.8 The image

`littlecedar/dgx-spark-dsv41@sha256:fabbe8615bb91c61fdde4a5f451f324a7449d7335fb85d453cc439985c525495`
(tag `tensorfold-tp2`), arm64-only, 33.8 GB. Source: `recipes/ds4/Dockerfile.tensorfold-dsv41`.

Base: `lmsysorg/sglang:dev-cu13` (digest `sha256:aa878e8d…`). It already carries everything the
engine compiles and links against — nvcc 13.0 + ninja, torch 2.13.0+cu130, triton 3.7.1,
libibverbs + headers (`<infiniband/verbs.h>`), libnccl.so.2, and the Python deps (numpy,
safetensors, tokenizers, huggingface-hub, jinja2, and also transformers/Pillow/xgrammar for the
vision and grammar paths). The build therefore does exactly one thing: `git clone` the fork at the
pinned commit and `pip install --no-deps .`. `--no-deps` is deliberate; installing with deps drags
a second torch and an `nvidia-nccl-cu13` wheel over the base's own, and the engine links the base's
libnccl by name (`cuda/comm.py`). The build ends with a gate that imports the engine, registers the
family, imports every runtime dep, and runs `tensorfold --version`.

Rebuild:

```bash
# on the arm64 head node, from a clone of the fork (the Dockerfile needs the repo context only
# if you COPY it; it git-clones the pinned ref itself, so build from an empty dir is fine)
docker build -f Dockerfile.tensorfold-dsv41 -t littlecedar/dgx-spark-dsv41:tensorfold-tp2 .
docker push littlecedar/dgx-spark-dsv41:tensorfold-tp2
# then pin the returned digest in the recipe's container: line
```

Bumping the engine is one `ARG TENSORFOLD_REF=...` change.

### 12.9 Boot gates and a healthy boot

1. `[tensorfold-dsv41-launcher] overlay gate OK` and `tensorfold: /…/tensorfold 0.6.3`.
2. `[tensorfold] loading DeepSeek-V4.1-Flash … on CUDA, rank R of 2`.
3. First boot only: `building CUDA extension …` (torch JIT; subsequent boots reuse
   `/cache/runtime/tensorfold/torch-extensions`) and the ~106 GiB/rank rank-cache write.
4. `[tensorfold] rank R: allocator ceiling …`.
5. `[tensorfold] DeepSeek-V4.1 engine ready: 2 rank(s), context 1048576, DSpark 5 drafts`.
6. `[tensorfold] rank 0 serving … at http://0.0.0.0:8000/v1` and `Mean acceptance length > 1` on
   decode (DSpark working). A boot that serves but accepts nothing is a failure.

With no Engram shards, expect the degraded warning from 12.7 between 2 and 5.

### 12.10 Guards

`tests/test_ds4_recipes.py` pins this lane with **`TensorfoldLaneContract`** (and
`TensorfoldLaneNegativeControls` for the mutations). It is stdlib-only and imports the shim
module directly, so it runs on a head node, in a container, or on a laptop. It pins:

- the image digest (`fabbe861…`) and `builder: docker-pull`;
- `runtime: sglang` over the **EXL3** checkpoint (`Mia-AiLab/…-EXL3-2.9bpw`) — swapping in the
  official MXFP4 repo must fail, since the engine's `family.check()` refuses a non-`exl3`
  `quant_method`;
- TP=2 = `min_nodes` = `max_nodes` = 2, and every `defaults:` key consumed by a `{placeholder}`;
- the `@littlecedar/mods/tensorfold-dsv41-launcher` reference, no host bind mounts, no pinned
  adapter names / sparkrun-managed comm env;
- the shim's two load-bearing behaviours **by executing `main()`** with `os.execvp` stubbed:
  `--dist-init-addr HOST:25000` → `--master HOST --master-port 25000` (not the engine's 29551
  default), and `--node-rank R` → `--rank R`; plus RECIPE_ENV reaching the child and a missing
  Engram dir leaving `TF_DS_ENGRAM` unset rather than failing.

What the guard **cannot** see is a real boot: the CUDA-extension compile, the rank-cache write, the
DSpark acceptance rate, and the rendezvous actually meeting. Those still need a render
(`sparkrun run … -n`) plus a launch and a reading of the boot log. Note that a launch from the
repo also needs the mod **committed and pushed** first (the `@littlecedar/` form resolves from the
node's registry clone, §4) — a local trial that must not wait on the push can copy the recipe to a
scratch dir and use the relative mod ref beside a `mods/` symlink.

### 12.11 Measurement discipline

- Upstream's numbers (2× GB10, greedy, DSpark k=5, 384-token prompts): C1 code 101 / prose 62 /
  structured 142 t/s; 4 concurrent 112 t/s; prefill 1.7–2.0k t/s at 8K–128K; start-to-ready 36 s
  warm. These are **upstream's**, measured on their nodes, not ours. Quote them as such.
- **Our own measurement (2026-10-05, .34/.35).** One greedy request, a mixed code/prose prompt,
  288 prompt / 256 completion tokens: **73.0 tok/s** decode (`completion_tokens / decode_s`), DSpark
  95 rounds, 262 drafted / 160 accepted → **mean acceptance 2.76 tokens/round**. 73 t/s sits inside
  upstream's 62–101 band, as a mixed prompt should. Note the engine's own `tensorfold.prefill_s`
  (0.94 s for 288 tokens ≈ 305 tok/s) is overhead-dominated at this prompt size — do **not** quote it
  as a prefill figure; a prefill number needs the 8K–128K shape.
- **Boot timings, ours.** Cold (first ever): rank-1 weight load 312 s while writing a ~106 GB
  rank cache, rank-1 ready 507 s, engine `loaded in 511.3 s`. Warm (rank cache present): rank-1
  weight load **25 s**, rank-1 ready **43.3 s**, sparkrun TTR (port open) **51.4 s**. A first-ever
  launch also pays a one-time ~510 s head→worker model sync (see 12.12). The rank cache persists
  across `sparkrun stop`/`run` because it lives under the managed `/cache/runtime`.
- The EXL3 checkpoint is a lossy quant: its quality on this project's hard tier is **unmeasured**.
  Do not imply parity with the knapcio lane's 17/18. (The lane now *boots and serves* — the boot
  is verified; the quality battery is not.)
- `--parallel 4` shares one 1M window; concurrency and per-stream context-length trade off (12.13).
- The rank cache is a boot-time optimization only; its first write is not part of a warm boot.

### 12.12 Negative results / gotchas

- **The official MXFP4 checkpoint will not load**: `check()` rejects `quant_method != "exl3"`.
- **`--dist-init-addr`'s port is not decorative**: see 12.4; drop the mapping and sparkrun declares
  the head dead.
- **sparkrun launches the head first**, not rank 1; see 12.4.
- **Engram is not sparkrun-distributed**; a fresh node without the shards serves degraded, silently
  except for one log line. Pre-warm per 12.7.
- **sparkrun re-syncs the model head→worker on launch even when both nodes already hold it**, over
  the management net (`192.168.1.x`) at ~400 MiB/s — 510 s for the 196 GiB checkpoint. It is a
  one-time cost per (head, worker) pair, but it dominates the first launch and is easy to misread
  as a hang during `[3/6] Distributing resources`. The rsync uses `--copy-unsafe-links`, which
  materializes the blob symlinks, so on the receiving node the model directory's real bytes must be
  measured with `find -type f -printf %s`, not `du` on the model dir (which sees only symlinks).
- **`docker exec <c> env` will not show `RECIPE_ENV`**: the shim rewrites its own environment before
  `execvp`, so a fresh shell shows the image's env, not the launcher's. Read the launcher's log line.

### 12.13 Context window and concurrency (measured 2026-10-05)

**Hard ceiling: `--context` ≤ 1,048,576 — the model's trained window. Not one token more.** The
recipe **ships at this ceiling** (`max_model_len: 1048576`), because `--context` *is* the KV pool
here, so the largest possible context and the largest possible cache are the same change. The
engine refuses anything larger *before it loads a weight* (`cli.py:355`):

```python
if native_context and context > native_context:
    raise ValueError(f"--context {context} exceeds this model's {native_context}-token window")
```

`native_context` is `config.json`'s `max_position_embeddings` (= `1048576` here). Verified on the
trial node: `--context 1048577` → refused with that exact message; `--context 1048576` → loads.
Note this family does **not** call `cuda.capacity.admit` (which clamps to `min(target, native)`) —
the ceiling is the CLI check, and below it the window is simply `self.limit = context` with no
memory-based reduction.

**So yes — the shared KV pool is capped at 1,048,576, and it is not a memory cap.** Two things to
hold together:

1. *The pool size IS `context`.* `new_pool(cap=context + max_rows + 8)`. There is no separate,
   larger pool the window is merely a slice of.
2. *`context` cannot exceed the model's trained window.* `config.json` shows why 1,048,576 is not
   arbitrary: `rope_scaling` is YaRN with `original_max_position_embeddings: 65536, factor: 16`, and
   65,536 × 16 = 1,048,576. Past that the model has no valid positions, so the engine refuses to
   start rather than emit nonsense.

Memory is nowhere near binding. The KV cache is MLA — one shared latent KV head
(`num_key_value_heads: 1`, `head_dim: 512`) — so the marginal cost is only **~2.9 KiB/token**.
Measured: rank 0's warm-up `reserved` is **100.82 GiB at context 262144** and **102.98 GiB at
1048576** — i.e. the entire extra 786,432 tokens of window costs **2.16 GiB** per rank. Tens of
millions of tokens would fit in 128 GB; the model simply has no positions for them. So the cap is
the architecture's position range, not the hardware.

Because it is *one* pool, that 1,048,576 figure is the **sum** of all concurrent streams' extents,
not a per-stream allowance — hence "shared". Four streams can only coexist if their extents sum to
≤ 1,048,576.

**Do not carry the knapcio lane's KV numbers over to this one.** They are different engines with
different KV models, and the mistake is easy because both are `runtime: sglang` and both serve the
same model:

| | knapcio TP=4 (README "Caveats" §) | TensorFold TP=2 (this section) |
|:--|:--|:--|
| Engine | real `sglang.launch_server` + `dsv41-sglang-overlay` | `tensorfold serve` (shim) |
| Pool control | `MAX_TOTAL_TOKENS` → sglang's `--max-total-tokens`, **pinned at 9400000** in `mods/dsv41-sglang-overlay/launcher.py` | **`--context` itself**; no pool flag exists |
| Window vs pool | `CONTEXT_LENGTH` (per-request, clamped 4096..1048576) **separate** from the pool | same number — `cap = context + max_rows + 8` |
| B/token/rank | ~1,670 (TP4: ~77 GiB of weights/rank leaves room) | ~2,900 marginal, and only ~2.1 GiB nominal |
| Pool capacity | `MAX_TOTAL_TOKENS=9400000` pinned (ceiling ≈9.5–9.6M); the boot line's `full_token` is the *budget* the host allows | 1,048,576 total, ever |

Confirmations run 2026-10-05: TensorFold exposes **no** pool/total-tokens flag
(`serve --help` has none) and **no** env that sets one (grep of `families/deepseek_v41` for
`environ` shows only `TF_DS_TOKEN_MAP` and tunables). Both lanes therefore reject
`--context`/`context_length` above 1,048,576 for the *same* reason — the YaRN position range — but
knapcio *can* hold many 1M streams while TensorFold cannot hold more than one.

The `full_token=` figure in knapcio's boot line is the **maximum budget the host memory allows**,
not tokens the server holds. The server pins `MAX_TOTAL_TOKENS` under it (9,400,000 as of
2026-10-06, up from 4,000,000). Crucially the pool is **page-shared, not extent-reserved**, so a
"how many 1M streams fit" question is not `pin ÷ 1M`: 16 concurrent 1M-claiming requests all ran.
The bound is `MAX_RUNNING_REQUESTS` and total *actual* tokens. Our measured receipts are in §7.1;
the "~7.5M → 6.6 streams" pair once quoted in the README mixed a budget figure with arithmetic and
ignored the page-shared model. Corrected there and in §7.1.

**`--context` is the shared KV pool, not a per-request allowance.** At startup rank 0 prints

```
[tensorfold] --parallel 4: 4 streams share one window of <context> tokens (an extent each)
```

`families/deepseek_v41/cuda/model.py::new_pool` implements it literally — "One window of `cap`
positions that up to `slots` streams share by extents" — and `engine.py:130` sets
`cap = context + max_rows + 8`. So `--context N` means: *the whole KV cache is N tokens, and every
concurrent stream carves its extent out of it.* A stream's extent is `prompt + its max_tokens +
draft rows` (`MultiDecoder._need`), and `extents.take` first-fits it into the one window. A request
whose prompt+reply exceeds `context` is rejected up front with `context_length_exceeded`.

**Consequence — you cannot have 4 full-1M streams.** One 1M stream consumes the entire window, so a
second cannot be admitted until the first frees its extent. Total concurrent tokens ≈ `context`,
not `4 × context`.

Measured on the trial pair (`.34`/`.35`), 4 concurrent requests each declaring its own reply length,
reading `streams.decoding` from `/health`. The recipe now ships at 1,048,576; the 262,144 column is
kept because vendoring all cache in one shared pool makes the difference stark and load-bearing:

| 4 concurrent requests, each `max_tokens` | context 1,048,576 (shipped) | context 262,144 (the old value) |
|:--|:--|:--|
| 2,000 | **4** | **4** |
| 200,000 | **4** | — |
| 250,000 | **4** | **1** |
| 300,000 | **3** | — |
| 500,000 | **2** | — |
| 900,000 | **1** | — |

So, exactly:

- **Full 1M trained context: yes, shipped.** The recipe boots at `max_model_len: 1048576` (verified:
  `/v1/models` reports it, `context 1048576` in the ready line); it is needle-tested upstream to
  1,039,833 tokens. A single stream may use the whole 1M window.
- **Maximum concurrency (4) holds up to `max_tokens ≈ 250K`** at context 1M (measured: 4 at 250K,
  3 at 300K). `4 × 250K = 1M` is the budget.
- **Raising 262,144 → 1,048,576 strictly improves concurrency.** At 262K, four requests each
  declaring a 250K reply collapsed to **concurrency 1**; at 1M the same four give **4**. The larger
  pool is a superset — it can always serve anything 262K could, plus more.
- **Decode speed is unchanged by the larger pool** (measured, median of 3, same 288/256 prompt as
  the 73 tok/s figure in 12.11): **72.5 tok/s at context 1,048,576** vs 73.0 at 262,144, identical
  `drafted=262 accepted=160`. Pool pages are touched only as used, so an idle 1M window costs
  nothing at decode time.
- `--parallel 4` is a **hard cap**: 8 tiny concurrent requests still peaked at
  `streams.decoding = 4` (the other 4 waited).

Practical guidance: the largest per-request window that still keeps C concurrent streams is about
`context / C`, minus the prompt and draft rows. Shipping 1M therefore sets the widest possible
operating envelope; a client that declares a smaller `max_tokens` gets more concurrency, and one
that declares a huge one gets the whole window. Memory is *not* the limit — the window is a fixed
allocation made at admission, and the `--parallel` lanes share one forward pass rather than
multiplying the cache.

Caveat: the concurrency numbers come from the engine's `/health` `streams.decoding` counter, not a
tokens/sec benchmark; they establish the admission law. The decode figure is a real measurement
(median of 3) but of one prompt shape.

### 12.14 References

- Engine: [bertholomus/TensorFold, branch `deepseek-v41-tp2`](https://github.com/bertholomus/TensorFold/tree/deepseek-v41-tp2)
- Design/report: the fork's `tools/dsv41/DESIGN.md`, `REPORT.md`, `ATTRIBUTION.md`
- Checkpoint: [Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw](https://huggingface.co/Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw)
- Upstream recipe: [bertholomus/deepseek-v4.1-tensorfold-tp2-2xgb10](https://github.com/bertholomus/deepseek-v4.1-tensorfold-tp2-2xgb10)
- Base image: [`lmsysorg/sglang:dev-cu13`](https://hub.docker.com/r/lmsysorg/sglang)

## 13. References

- Model: [deepseek-ai/DeepSeek-V4.1-Flash](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash)
- Upstream lane: [knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4](https://github.com/knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4) @ `58f2321` (downstream of [MiaAI-Lab](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-DGX-Sparks))
- SGLang: [V4.1 cookbook](https://github.com/sgl-project/sglang/blob/main/docs/cookbook/autoregressive/DeepSeek/DeepSeek-V4_1.mdx)
- Archived EXL3 / vLLM lane and model-anatomy analysis: [`attic/ds4/`](../../attic/ds4/)