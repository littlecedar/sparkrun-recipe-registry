# ds4_NOTES — DeepSeek V4.1-Flash EXL3 lane: working record

Session log for `model_symbol=ds4`. Durable facts graduate into `AGENTS.md` and
`recipes/README.md`; this file is pruned. Read `AGENTS.md` first.

## Prior session (2026-09-27/28) — the `max_num_seqs=16` / `gmu 0.85` retune

Four recipes (`…exl3-{tp4,tp4-1m,tp6,tp6-1m}`) retuned to `max_num_seqs: 16`,
`gmu: 0.85`, capture ladder to 64; every arm booted as-shipped and measured.
Consolidated in **AGENTS.md §7.12** and the README table — **do not re-derive
here.** Headline: TP6-1M KV 15,034,010 tokens, C1/C4/C8/C16 = 43.4/72.7/110.2/149.1.

## Prior session (2026-10-01) — spark-arena-v2 long-context "collapse" — CLOSED

**Condensed:** the full chronological record is preserved in `PERF-ISSUES.md`
§§1–10 (the deliverable) and consolidated into `AGENTS.md` §11 + the README.
Do not re-derive here. Headline in one paragraph:

The recipe is healthy. The `spark-arena-v2` "collapse" at `depth>0, c≥2` is the
cost of a **cold deep prefill**, not decode starvation: warm long-context
concurrency is **51 t/s at d32768 c2** (bench reported 5.2). The decisive probe
was `warm_cold.py` (`.scratch/ds4/perf2/`); `disk_isolate.py` (`.scratch/ds4/perf3/`)
then showed the cold prefill is **compute-bound, not Engram-disk-bound** (ratio
0.99). `--long-prefill-token-threshold 2048` was a **mixed** result and was **not
shipped**. No throughput-motivated recipe change; envelope: cold deep prefill
~1300 t/s @TP4 and serialises under concurrency. Process notes that survive:
`sparkrun benchmark --profile` resolves from the **registry cache**, not the
working tree; the serve log is `/tmp/sparkrun_serve.log` **inside** the
container (`docker logs` is empty); containers are reaped after a run (use
`--no-rm` to keep one); `rtk ssh` breaks on multi-line commands with parens.


## Session 2026-10-02 — NEW SECOND LANE: knapcio DSV41 SGLang (TP=4, native MXFP4)

**Objective this session:** integrate
`github.com/knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4` (SGLang, native
checkpoint, DSpark, Engram-on-NVMe) into this registry. Full provenance/plan:
**`recipes/ds4/KNAPCIO-SGLANG-INTEGRATION.md`**. Recipe:
`deepseek-v4.1-flash-sglang-tp4-knapcio.yaml`; mod: `mods/dsv41-sglang-overlay/`.

Why a new lane at all: it runs the **official** checkpoint (comparator for the
EXL3 94.4% hard-tier question, AGENTS.md E5) and upstream measures **89.7 t/s
prose c1** (~2× our vLLM EXL3 lane) from the b12x kernels + DSpark.

**The old "SGLang is a dead end" verdict is superseded for a purpose-built image.**
The prior blockers were real *for published images*: no single image was both
V4.1 and b12x; the MXFP4-Cutlass MoE rejects `2304/4 = 576` (needs a multiple of
128). Both are solved here — the repo builds `dsv41-4x-spark:canary-roce`
(dsv4.1 branch + adapter overlay + b12x_next; built on all four nodes, internet
works), and **`EP_SIZE=2`** gives `2304/2 = 1152 = 9×128`. `EP_SIZE=1` is the
upstream production line (b12x_next), a follow-up A/B.

**Feasibility verified this session:**
- The **native checkpoints are already in the shared HF cache**: `deepseek-ai/DeepSeek-V4.1-Flash`
  (snapshot `dba1be0a40aa45a94ad051997016db3960a90277`, 510.30 GB, 48 shards) and
  `deepseek-ai/DeepSeek-V4-Flash-0731`. `lmsysorg/sglang:dev-dsv41` (33.2 GB) is present.
- **Engram packs built on all four nodes**: `pack_engram.py --rank R --tp 4`,
  ~47 GiB/node at `/home/red/dsv41-engram/`. Mount the **whole `hub/` dir** — this
  cache uses the two-level `hub/blobs/<xx>/<sha>` layout, so mounting only the
  `models--…` dir leaves every blob symlink dangling.
- **Fabric is full-mesh, not a ring**: two RoCE planes (192.168.0.0/24 on
  `rocep1s0f0`, 192.168.1.0/24 on `roceP2p1s0f0`), all six pairwise pings OK,
  port 1 ACTIVE (port 2 DOWN — do not use `*s0f1`), **RoCEv2 GID index 3**.
  So the switchless-ring path is not needed.

**EP_SIZE: use 1, not 2.** EP=2 *loads* (2304/2 = 1152 = 9×128, clearing the
MXFP4-MoE `%128` check) but **dies at the first decode plan**:
`dsv41-moe-E192-N1152-k6-M5 failed to prepare … planned dynamic direct routing is
unsupported for this launch shape`. `adapter/moe_b12x_next.py` states it plainly:
"the production profile is EP_SIZE=1, EP>1 is an A/B setup". All measured numbers
below are EP=1.

**Sparkrun wiring (the load-bearing bits):**
- The image's entrypoint is `boot.py`, which builds the whole `sglang.launch_server`
  argv from env. sparkrun appends `--dist-init-addr/--nnodes/--node-rank` to the
  command assuming `sglang serve`. The mod's `launcher.py` consumes those and
  maps them onto `DIST_INIT_ADDR`/`NNODES`/`NODE_RANK`/`SERVER_PORT`, then execs
  `boot.py`. The recipe `command:` is a one-line call to the shim.
- A **local-only image is not distributable**: `sparkrun run` pulls it from a
  registry unless the recipe sets **`distribution_config.containers.enabled: false`**
  (the top-level key is `distribution_config`, NOT `distribution`). Also
  `executor_config.volumes` is a **list of `host:container` strings**, not a dict.
- `/state` must be bind-mounted writable (boot.py writes `launch.json`); the image's
  `/state` is not writable as the sparkrun user.
- Rootless sparkrun already grants `IPC_LOCK`, `memlock=-1`, `/dev/infiniband`,
  `shm_size 32gb` — so no `privileged`/`cap_add`/`user` override is needed.

**Measured (boot #4/#5 this session; bench `.scratch/ds4/knapcio/bench_sglang.py`,
two discarded warm-ups, non-streaming 200-token, distinct prompts, greedy):**

| t/s aggregate | C1 | C4 | C8 | C16 |
|:--|--:|--:|--:|--:|
| NCCL only (boot #4) | 27.4 | 62.5 | 73.2 | 155.0 |
| **+ RoCEnante (boot #5, SHIPPED)** | **46.6** | **105.6** | **132.5** | **191.0** |
| upstream v2.3 (their fabric/clock) | 89.7 | 165.9 | 244.6 | 357.2 |

**RoCEnante is the single biggest win this session: 1.70×/1.69×/1.81×/1.23× over
NCCL**, far beyond the 7–25% GB10 inter-boot spread. **C1 46.6 beats our shipped
vLLM/EXL3 TP=4 lane (40.7) on the same four nodes.** Boot log:
`RoCEnante ready: world=4 hcas=rocep1s0f0,roceP2p1s0f0 gid_index=3
max_size=2097152`. Correctness smoke `27*43 -> 1161`, planets correct; DSpark
acceptance 2.4–2.8 unchanged. Rollback is one env line (`SGLANG_ROCE_ALLREDUCE=0`).

**Remaining gap to upstream 89.7 c1 — resolved as "no knob left".** The SPS
ragged-verify table **crashes the Engram path** (upstream's own README lists it
under "Not used"; our fit → `AssertionError: engram target-verify expects one
equal block per request, got 84 tokens for 16 requests of 6`), so **upstream
production is verify-all** and our recipe is already the production line. The
200+ MHz clock-cap convention and fabric differ. **89.7 remains their number.**

**Boot #9 (recipe exactly as shipped) reproduced the numbers within 2 %:**
46.3/106.8/132.7/194.6 t/s at C1/C4/C8/C16 — the lane is stable across boots.

**E5 CLOSED — the headline result.** `quality_hard_sglang.py` (the hard 18-task
tier) against the release checkpoint, two runs: **17/18 = 94.4 %, the same score
and the same single failure (`hard-rev`) as the EXL3 lane** (§7.6). Verdict: the
EXL3 3.5 bpw quantization costs nothing measurable on that battery; the one
failure is a base-model limitation. Artifacts:
`.scratch/ds4/knapcio/quality_hard_sglang{,_rep2}.json`.

**Verdict for the recipes:** the SGLang lane is a working, measured **second
engine** — `deepseek-v4.1-flash-sglang-tp4-knapcio.yaml`, shipped with RoCEnante
ON and no SPS table — and the EXL3/vLLM lane remains the default. Full details,
boot gates, provenance and limits: `KNAPCIO-SGLANG-INTEGRATION.md`; durable
summary: `AGENTS.md` §7.13.

## Session 2026-10-02 (cont.) — PORTABILITY: no host bind mounts

**Objective:** the recipe's `executor_config.volumes` (`/home/red/dsv41-engram`,
`/home/red/dsv41-state`) was flagged `non-portable-mount`; it must place cacheable
artifacts only in the sparkrun-managed runtime cache and put everything else in
the image.

**Shipped (VERIFIED booting, see below):**
- **No `volumes:` block.** `sparkrun recipe validate` → **clean, zero warnings**
  (`non-portable-mount` gone; `managed-comm-env` also cleared — see below).
- Cacheables moved under `/cache/runtime/engram`, `/cache/runtime/state`,
  `/cache/runtime/b12x-compile`, `/cache/runtime/b12x-roce` (the sparkrun leaf
  `~/.cache/sparkrun/runtime-cache/sglang/deepseek-ai__DeepSeek-V4.1-Flash-9a74d993`,
  computed by sparkrun; the recipe never spells the host path).
- `mods/dsv41-sglang-overlay/run.sh` creates + `reown`s the subdirs;
  `launcher.py` is the only rank-aware component (sparkrun appends `--node-rank`
  to every node; the container env has no rank — VERIFIED in the dry run) and
  packs this rank's Engram shards when absent, **detached**, so a cold boot never
  exceeds sparkrun's ~150 s head-rendezvous wait.
- Cold-cache path: first boot runs Engram from the checkpoint; next boot is
  packed. Pre-warm by copying shards into the leaf (fast local copy).

**Evidence / artifacts:** `KNAPCIO-SGLANG-INTEGRATION.md` ("Portability"),
`mods/dsv41-sglang-overlay/README.md`, design note
`.scratch/ds4/knapcio/PORTABILITY-DESIGN.md`; guards in
`tests/test_ds4_recipes.py` (SglangLaneContract + negative controls).

**Boot-verified 2026-10-02** (4 Sparks `.32`–`.35`, dry-run-identical recipe with
the mod ref swapped to the bare form for the uncommitted mod): all gates pass —
`overlay gate OK`, `cache dir ready` × 4, launcher `NNODES=4 NODE_RANK=0`,
`Exact nvme Engram … packed=True`, `moe_b12x_next armed`, `RoCEnante ready`,
`fired up and ready`. TTR 270 s; rendered `docker run` has **no `-v /home/red/…`**
(only the HF cache + the sparkrun runtime-cache leaf). The `replicated_split …
slice failed` lines are the adapter's normal try-then-OFF probe, not a defect
(final state: `armed for ['wqkv_a','engram.wkv']`).

**Mechanic that cost a boot:** `@littlecedar/mods/…` resolves from the node's
**registry git clone**, not the synced working tree; iterating on a mod needs the
`~/development` symlink layout + a bare ref (see QWEN4-WORK §16). The shipped
recipe keeps the `@littlecedar/…` form.

**Cold-cache self-heal VERIFIED in-image** (idle `.32`, throwaway container):
`ensure_engram_shards(env, rank=0)` with no shards spawned
`flock -n …/engram/.pack.lock nice -n 10 ionice -c 3 python3 pack_engram.py
--rank 0 --tp 4 --out …` detached and booted on the fallback; the packer wrote
`engram-l1-r0of4.partial` at ~498 MiB/s. First cold boot = checkpoint Engram
(correct, slower); next boot = packed. **Still required of the host:** the shared
HF checkpoint — **not** the image, which is now vendored (below). Commit/push the
mod so `@littlecedar/mods/dsv41-sglang-overlay` resolves to the new code.

## Session 2026-10-03 (cont.) — `env:` slimmed: redundant dropped, rest migrated to the launcher

**Directive (user):** remove redundant `env:` vars; migrate the non-redundant
ones into the launcher.

**Result:** the recipe's `env:` is now **3 lines** — `MODEL_PATH`, `DSV41_SOURCE`
(the external checkpoint path) and `TP_SIZE` (the launcher gets `--nnodes`, not
the TP degree). Everything else moved into
`mods/dsv41-sglang-overlay/launcher.py`'s `RECIPE_ENV`.

- **Dropped as redundant** (recipe value == runtime default): `SKIP_SMOKE=0`,
  `WARMUP=1`, `HOST=0.0.0.0`, `SERVED_MODEL_NAME`, `SPARK_PREFILL_TP_MIN_CONTEXT`,
  `SPARK_PREFILL_TP_MIN_ROWS`, `DSV41_FAST_LOAD_TP_SLICE=auto`,
  `DSV41_FAST_LOAD_INFLIGHT_GB=6`.
- **Migrated** (adapter flags default OFF, so the recipe sets were the production
  *enablement*): all `DSV41_*`, `SGLANG_*`, `OFFLOAD_MODE`, `EP_SIZE`, the
  parallelism/serving flags, `READY_TIMEOUT_S`, `SKIP_PREPARE`/`SKIP_VERIFY`, the
  locations, RoCEnante, the NCCL transport tuning, `PYTORCH_CUDA_ALLOC_CONF`.
  Full inventory: `.scratch/ds4/knapcio/ENV-MIGRATION.md`.

**Bug caught live (why the launcher must OVERRIDE, not `setdefault`):** the image
bakes `STATE_PATH=/state`, `DSV41_CACHE_GIB=16`, `PYTORCH_CUDA_ALLOC_CONF=…True`,
`SGLANG_RUST_BUILD_MODE`, `OFFLOAD_MODE` into its **ENV**, and those populate the
launcher's process env (`boot.py` is `execve`'d from it). A first cut used
`setdefault`, so the image won: `launch.json` went to the unwritable `/state` and
the allocator mode reverted to `expandable_segments:True` (the NaN-logits mode).
Fix: `env.update(RECIPE_ENV)`. It is disjoint from the recipe-owned
`MODEL_PATH`/`DSV41_SOURCE`/`TP_SIZE`, so those still pass through.

**VERIFIED live (boot of the slimmed recipe, TTR 183 s):** `fired up and ready`;
RoCEnante `hcas=roceP2p1s0f0,rocep1s0f0` (detection); `moe_b12x_next armed`;
Engram `packed=True io_threads=96`; `state/launch.json` written under
`/cache/runtime` (image `/state` overridden) — i.e. every migrated value took
effect. `recipe validate` clean; `docker exec env` is the WRONG probe (the
launcher rewrites its own env before `execve`) — read the tools, not the container
env. Guards: `test_recipe_env_is_thin`, `test_nccl_transport_tuning_present`,
`_resolved_env()` (launcher `RECIPE_ENV` overlaid by the recipe) + updated
negative controls; 28 lane tests green.

**Follow-up fix — `run.sh` used the image's baked `STATE_PATH`.** The mod runs as
root BEFORE the launcher, so it cannot see the launcher's `RECIPE_ENV`, and the
image bakes `STATE_PATH=/state`: `${STATE_PATH:-…}` made the mod `reown` the wrong
directory. Switched `run.sh` to the same **literal** `${CACHE}/{engram,state,
b12x-compile,b12x-roce}` paths the launcher uses (both in the mod, so they move
together). Verified `/cache/runtime/state` is `red:red` and holds boot.py's
`launch.json` + smoke artifacts (nothing leaked to `/state`). Guard updated:
`test_mod_creates_and_reowns_cache_dirs` now asserts the literal subdirs and their
agreement with `RECIPE_ENV`.

## Session 2026-10-03 (cont.) — comm env fully un-pinned (portability)

**Rule (user, 2026-10-03): all recipes must be portable and rely on sparkrun's
detections. A stanza naming a host device (`B12X_ROCE_HCA: rocep1s0f0,…`) is not
portable.**

**Change:** removed from `env:` the `managed-comm-env` keys (`NCCL_NET`,
`NCCL_IB_DISABLE`, `NCCL_IB_HCA`, `NCCL_IB_GID_INDEX`, `NCCL_CROSS_NIC`) **and
`B12X_ROCE_HCA`** (not sparkrun-managed, but a literal host device list — and it
falls back to the detected `NCCL_IB_HCA`, so pinning it was contraindicated).
Kept only transport *tuning* with no device names: `NCCL_P2P_DISABLE`,
`NCCL_SHM_DISABLE`, `NCCL_CUMEM_ENABLE`, `NCCL_BUFFSIZE`, `NCCL_LL128_BUFFSIZE`,
`NCCL_PROTO`, `NCCL_MAX_NCHANNELS`, `NCCL_DEBUG`, `NCCL_DEBUG_SUBSYS`.
`recipe validate` is **clean**, and no `env:` value names a host device.

**Why safe + strictly better (VERIFIED on live boots):**

| var | recipe pin (old) | detected (live) |
|:--|:--|:--|
| `NCCL_IB_HCA` | `rocep1s0f0,roceP2p1s0f0` | **`roceP2p1s0f0,rocep1s0f0`** — only the **ACTIVE** ports, so it drops the DOWN `*s0f1` |
| `NCCL_NET` / `NCCL_IB_DISABLE` / `NCCL_CROSS_NIC` | `IB` / `0` / `1` | same |
| `NCCL_IB_GID_INDEX` | `3` | `3` |
| (added by detection) | — | `NCCL_IGNORE_CPU_AFFINITY=1`, `NCCL_SOCKET_IFNAME=…` |

Booted to **`fired up and ready`** with `B12X_ROCE_HCA` **absent**: `RoCEnante
ready: world=4 hcas=roceP2p1s0f0,rocep1s0f0 gid_index=3` — the detected list.
b12x's RoCEnante reads `B12X_ROCE_HCA` → else `NCCL_IB_HCA` → else 3
(`roce_oneshot.py:85,99`), so the fallback is what makes the unset form correct.
Engram `packed=True`, TTR 183 s.
Guards: `test_managed_comm_env_not_pinned`, `test_no_host_device_names_in_env`,
`test_roce_nante_on` (asserts `B12X_ROCE_HCA` absent) + two negative controls.

**`docker exec env` is not a valid probe for anything the launcher sets** — the
launcher rewrites `os.environ` in-process and `execve`s boot.py; `docker exec`
starts a FRESH shell from the container's creation env, so it shows the image's
baked values (`/state`, `expandable_segments:True`), not the launcher's override.
Read the launcher's own log line and the tools' output (`launch.json` location,
the Engram line) instead.

**Trap that cost a wrong first reading:** `sparkrun run --dry-run` *skips* the IB
detection step (`Step 2/7: Detecting InfiniBand` runs in ~0.0 s), so it prints
`No InfiniBand detected, using default networking` and renders **no NCCL_IB_* env
at all** — which reads as "detection is broken here". It is not: detection runs on
the real launch, and `ib_detect.sh` standalone returns `IB_DETECTED=1` with the
HCA list. Do not conclude anything about detection from a dry run.

## Session 2026-10-02 (cont.) — VENDORED IMAGE (build + push to Docker Hub)

**Objective:** build the container on `.30` and push it to the littlecedar repos
so it is vendored instead of built locally.

**Done (VERIFIED):** cloned `knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4` @
`58f232155917d388b6053eca079c617fd306c33c` to `/home/red/dsv41-knapcio` on
`.30`, `fetch-sglang-canary.sh` (sglang `f80c91a4b`), `docker build -f
Dockerfile.canary-roce` → exit 0, image `a0e6d103002d` (33.5 GB, arm64). Pushed:

```
littlecedar/dgx-spark-dsv41:canary-roce
  digest sha256:932dd8c2722b07d3f835cab0be3ce6a43e67fe987e904885876d97539e958825
  image  sha256:a0e6d103002db3d2ea0f798b372bb356236acfe59458a5f9cbc9bb720ab2c9c5
```

Recipe now uses that digest-pinned ref and `distribution_config.containers.enabled:
true`, so a host **pulls** the exact bytes. Rollback to local build = retag
`dsv41-4x-spark:canary-roce` + `enabled: false`. Docs: `KNAPCIO-SGLANG-INTEGRATION.md`
§Image; guards: `test_image_is_vendored_and_pinned` + `test_control_image_unpinned`.
The `.docker/config.json` on `.30` already carried the `littlecedar` Hub auth.

**Vendored-boot VERIFIED (2026-10-02, clean cluster):** `sparkrun run` on
`.32`–`.35` pulled `littlecedar/dgx-spark-dsv41@sha256:932dd8c2…`, launched, and
reached **`fired up and ready`** — `RoCEnante ready: world=4`, `[moe_b12x_next]
armed`, Engram `packed=True`, no host bind mounts, TTR 244 s (cold). A worker
(`.33`) also pulled the digest and resolved it to image `a0e6d103002d`, the same
bytes built on `.30`. **Cluster-cleanliness lesson:** the *first* vendored boot
falsely reported ready at 74 s because the earlier portable-boot containers were
never reaped (sparkrun `--rm` removes on clean exit, but a killed/abandoned run
leaves them) and the head's 8888 was served by the stale container. Always
`sparkrun status` / `docker ps -a | grep sparkrun` before a boot test.

## Session 2026-10-02 (cont.) — CHECKPOINT MOVED (`dba1be0a` → `2cba9e42`)

**Symptom:** `boot.py:45 AssertionError: missing /cache/huggingface/hub/
models--deepseek-ai--DeepSeek-V4.1-Flash/snapshots/dba1be0a…/config.json`.

**Cause (VERIFIED on all six nodes):** the shared HF cache was re-downloaded and
`main` now points at snapshot `2cba9e42aa026125f3ed06c6d98c1db82f7ca027`; the
old `dba1be0a…` is **gone from every node**. The recipe hardcoded the old hash
(and could not glob: a bare `X=/path/*` assignment stays literal — §6.1). The
cache itself is fine: the new snapshot is complete (60 entries, 476 GB, 48
shards, index present). The checkout's `deepseek_v41` / 40-layer / 384-expert /
`engram_num_embeddings [384006168, 384016682]` shapes are **identical**, so the
packed Engram shards remain valid and no measured number changes.

**Fix (two layers):**
1. Recipe literal updated to `2cba9e42…` (the current snapshot).
2. `mods/dsv41-sglang-overlay/launcher.py` now **self-heals**: if the recipe's
   `MODEL_PATH` is not a complete local snapshot, it resolves the served one from
   `<repo>/refs/main` (else the newest snapshot carrying
   `model.safetensors.index.json`) and rewrites `MODEL_PATH`/`DSV41_SOURCE`
   before `execve(boot.py)`. The literal encodes a *preference*, not a hard pin;
   the recipe no longer breaks when the shared cache moves again. Guards:
   `test_launcher_resolves_stale_checkpoint`; resolver unit-tested offline and
   against the live cache in-image (stale → `2cba9e42…`).

**Live-boot VERIFIED (2026-10-03):** two clean boots on `.32`–`.35` — (1) recipe
as shipped (literal `2cba9e42…`) → `fired up and ready`, TTR 191 s; (2) recipe
edited to force the STALE `dba1be0a…` → launcher logged `checkpoint …dba1be0a…
is not present; resolved to …2cba9e42…` and booted normally (TTR 181 s), Engram
`packed=True`, no `missing config.json`. The self-heal works.

**Coordination note:** commit `fd0fb21` (external) captured most of the
portability+vendoring work but **dropped the `distribution_config:` block** from
the recipe (the portability rework was written over a base that predated it).
Re-added it; the recipe now carries `containers.enabled: true` + the digest pin.
If a later sync/merge clobbers it again, `test_image_is_vendored_and_pinned` and
`test_control_image_distribution_disabled` will catch it.
