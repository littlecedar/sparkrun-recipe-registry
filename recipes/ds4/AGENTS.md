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
here is probably smaller. `SPECULATIVE` on any specific EP1 delta — it has not
been booted on our fleet.

**A/B if you want the real number** (mirrors §10's discipline; read the pool from
the boot log, never computed):

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

## 12. References

- Model: [deepseek-ai/DeepSeek-V4.1-Flash](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash)
- Upstream lane: [knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4](https://github.com/knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4) @ `58f2321` (downstream of [MiaAI-Lab](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-DGX-Sparks))
- SGLang: [V4.1 cookbook](https://github.com/sgl-project/sglang/blob/main/docs/cookbook/autoregressive/DeepSeek/DeepSeek-V4_1.mdx)
- Archived EXL3 / vLLM lane and model-anatomy analysis: [`attic/ds4/`](../../attic/ds4/)