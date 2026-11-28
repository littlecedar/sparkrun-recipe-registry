# aneda-launcher

Pre-exec staging and the per-node launcher for the aneda arm — the picom (`dsgb10`)
stack forked for this registry's GLP steering patch series:
[`recipes/ds4/deepseek-v4.1-flash-1017-aneda-tp4-1m.yaml`](../../deepseek-v4.1-flash-1017-aneda-tp4-1m.yaml).

The engine is [Picom-code/pico-dgx-ds4](https://github.com/Picom-code/pico-dgx-ds4) at
`7c123ad4` (MIT): a from-scratch C++/CUDA TP=4 engine with its own Rust front-end
(`dsfront`) and its own RDMA ring. It is not an SGLang/vLLM server, one process runs per
node, and all four processes take the same argv except `--rank`.

## What runs where

`run.sh` (pre_exec, root, before the serve command) stages what is environment-shaped:

- resolves the fabric from sparkrun's own detection (devices, /24s, GID index), derives
  this node's rail tail from its RoCE GID, and publishes both to `fabric.env` for the
  serve phase;
- renders `/cache/runtime/aneda/fleet.conf` only when `ANEDA_RANK_TAILS` is supplied
  (the override path); otherwise `launch.sh` assembles the list first — the engine's own
  contract (`engine/comm/fleet.cpp` upstream): the four device names must exist by exact
  `ibv` name, one IPv4 per netdev (each device's GID at `GID_INDEX` must equal it), and
  all four ranks' `NEXT`/`PREV` addresses;
- creates the runtime directories, with no key: auth is off by default because the
  network's fronting proxy owns authentication, and `dsfront` serves keyless
  (`ANEDA_AUTH=1` restores the mode-600 key and `--api-key-file`);
- before it creates anything, refuses a `/cache/runtime` that is not sparkrun's
  runtime-cache bind mount (same filesystem as `/` = the container overlay): with the
  cache disabled (`SPARKRUN_NO_RUNTIME_CACHE`, `runtime_cache.enabled: false`) the
  130 GB/rank of converted artifacts would land in the overlay and vanish on exit.

`launch.sh` (the container command, one container per rank) is the launcher:

- rank 0: prepares rank 0's artifacts, starts the engine, waits for its socket, then
  runs `dsfront` in the foreground and stops the engine on `SIGTERM`;
- ranks 1-3: prepare their artifacts and `exec` the engine.

## The tail list assembles itself

`ANEDA_RANK_TAILS` is no longer an operator input, and supplying it is only an
override. sparkrun hands a recipe no host list (`sparkrun/core/env_templates.py:19`
`LAUNCH_FIELDS` is a closed set), but the pre_exec hook environment carries what the
exchange needs:

```python
# sparkrun/orchestration/hooks.py:110-125 (build_hook_env)
        "SPARKRUN_NODE_RANK": str(rank) if rank is not None else "",
        "SPARKRUN_NODE_HOST": "" if control else host,
        "SPARKRUN_HEAD_HOST": head_host,
        "SPARKRUN_CLUSTER_ID": context.cluster_id,
        "SPARKRUN_RUNTIME_CACHE_DIR": "" if control else cache_dir,
```

`run.sh` therefore derives only its **own** rail tail (from its RoCE GID at the index
sparkrun injects), validates an explicit `ANEDA_RANK_TAILS` against it when one is
given, and publishes `fabric.env` — fabric `/24`s, devices, GID index, this rank, its
tail, `SPARKRUN_HEAD_HOST`, and the exported `HF_HOME`. `launch.sh` runs concurrently on
all four nodes (sparkrun starts the head at step 6 and the workers at step 7 without a
gate here, because `native_rendezvous_port` is `None` at `tp` 1), so the exchange happens
there: rank 0 collects the three peers' tails over TCP on **port 19110** (8000 is
`dsfront`, 18620 the engine's ring bootstrap, 25000 sparkrun's torch gate) and answers
each with the assembled list. Containers run on the host network
(`orchestration/executors/docker.py:270`, `network: "host"`), so a bind on the
management address is reachable from the peers. A missing rank at the 300 s deadline
aborts with its name; the engine never starts on a partial list.

`--model`: sparkrun passes a prepared container path when model distribution ran, or the
repo id when a profile disabled it; the cache root is the exported `HF_HOME`, never a
guessed `/cache`.

It replaces upstream's `service.sh`, whose only irreplaceable job is starting ranks 1-3
over ssh — impossible when sparkrun owns one container per node. What it keeps from
`service.sh`: the page-cache drop before the engine starts (on GB10 a CUDA allocation
sees only free pages), the 100 GiB `MemAvailable` gate, and the same engine argv. What it
drops: the ring lock, restart supervision and kept sessions — a sparkrun arm is one
dedicated serve and sparkrun's lifecycle owns restarts.

Both paths also pass a fail-closed RDMA gate before the engine starts: `ibv_devices`
must list both devices the fleet file names, or the launcher dies naming the device
and the container's RDMA user space. That is the 2026-11-17 shape — an image with
`libibverbs` but no `ibverbs-providers` aborted on every rank with
`RDMA device <name> not found` after the one-time artifact work.

## First boot prepares the per-rank artifacts

The engine does not read the HF checkpoint. It reads a per-rank weight file
(`dsw_convert`, 72.38 GiB) and per-rank Engram shards (`engram_pack`, 50.7 GB) plus a
518,048-byte hash map. Those are built from the pinned checkpoint on first boot, in the
container, once per node, and reused afterwards from `/cache/runtime/aneda/` (node-local,
so each node keeps only its own rank's files, ~130 GB):

| artifact | producer | marker |
|---|---|---|
| `weights/rank<r>.dsw` | `dsw_convert --ckpt … --rank r --out …` | `rank<r>.dsw.ok` |
| `engram/engram-l1-r<r>of4.bin`, `engram-l14-r<r>of4.bin` | `engram_pack … r` | `engram/rank<r>.ok` |
| `engram/engram_hashmap.bin` | `make_hashmap_stdlib.py` | included in `rank<r>.ok` |

`ANEDA_VERIFY=1` additionally runs `dsw_verify` (every byte of the weight file un-tiled
and compared: ~200-400 s) before the marker is written. The readiness budget in the
recipe covers the first boot; later boots start in minutes.

A failed conversion exits non-zero, so sparkrun sees a dead arm instead of a serve that
silently used a stale artifact.

## Knobs

All are env (recipe `env:` or `-o env.KEY=value`):

| key | default | meaning |
|---|---|---|
| `ANEDA_AUTH` | `0` | `0` = `dsfront` runs keyless (`/v1/models` and `/v1/chat/completions` accept no bearer); `1` requires the generated key via `--api-key-file` |
| `ANEDA_RANK_TAILS` | empty (assembled) | override only. Empty = the launcher exchanges the four tails at serve time (see above) and renders `<ANEDA_FABRIC_A>.<tail>` / `<ANEDA_FABRIC_B>.<tail>`; an explicit list pins it and every node's own entry is checked against its rail GID, failing closed on a mismatch |
| `ANEDA_DEV_A` / `ANEDA_DEV_B` | sparkrun's `NCCL_IB_HCA` | the two RDMA devices, lower /24 first; derived from the active HCAs sparkrun detects, each device's netdev IPv4 taken from its own RoCE v2 GID |
| `ANEDA_FABRIC_A` / `ANEDA_FABRIC_B` | derived | the two f0 /24s, from the same GIDs; never stored in the tree |
| `ANEDA_GID_INDEX` | sparkrun's `NCCL_IB_GID_INDEX` under a non-`ring` topology, else derived | RoCEv2 GID index; sparkrun emits `NCCL_IB_GID_INDEX` only when cluster interconnect topology is not `ring` (the ring path emits its own overrides), so under `ring` the value is always derived from the device's first IPv4-mapped RoCE v2 GID and the mod's /24 check is the only guard; `-1`/absent falls back to that same GID, and both devices must carry the declared /24 at that index |
| `ANEDA_RING_DIRECT` | `2` | switch mode: every rank writes to all peers itself (no relay); `0` for a cabled ring |
| `ANEDA_ENGINE_ARGS` | upstream's production line | engine argv, minus `DSGB10_OEA` (see below). The engine parses strictly — an unknown token is `unknown argument <x>` and a start-time exit on every rank, and there is no `--help` |
| `ANEDA_OEA` | empty | opt-in lossy batch-aware MoE re-route (`4,12,9` upstream); empty = strictly lossless |
| `ANEDA_VISION` | `1` | upstream PR #15: run the checkpoint's ViT side encoder on rank 0 and give `dsfront` `--vision-addr`; `0` refuses images (400) |
| `ANEDA_VISION_PORT` | `18950` | encoder's loopback port (same address in `--vision-addr`) |
| `ANEDA_VISION_CMD` | the image's encoder | override the encoder command; `--host 127.0.0.1 --port <ANEDA_VISION_PORT>` is appended |
| `ANEDA_STREAM_TOOL_ARGS` | `1` | upstream PR #7: stream a tool call's name early and its arguments as they arrive; `0` is the pre-PR single chunk |
| `ANEDA_MAX_TOKENS` | `32768` | `dsfront --max-tokens`: the default *and* the hard cap on one reply's generated tokens (upstream clamps a larger request, never refuses it) |
| `ANEDA_FRONT_ARGS` | empty | extra `dsfront` args |
| `ANEDA_MIN_AVAIL_GIB` / `ANEDA_MIN_DISK_GIB` | `100` / `150` | fail-closed start gates |
| `ANEDA_ENGINE_READY_S` | `900` | rank 0's socket wait |

The log knobs are under [Log records](#log-records).

## Log records

The engine, the front-end, the vision encoder, the launcher and the mod write one record per
line (the logging patch, `recipes/ds4/aneda-structured-logging.patch`, applied by the image
build):

```
ts=<UTC ISO-8601 ms> level=<debug|info|warn|error|fatal> node=<host> rank=<0-3> src=<engine|front|vision|launcher|mod> event=<noun.verb> [key=value]... [msg="<text>"]
```

`msg=` is last, quoted and escaped, so a record never contains a raw newline. The one-time
artifact converters (`dsw_convert`, `engram_pack`) print bare progress text; the filtered
streams stamp every line.

**Sinks.** Container stdout is the live stream: sparkrun captures it to the node's
`/tmp/sparkrun_serve.log`, which `sparkrun logs`, the boot watchdog and the receipt tools
read. Each rank also keeps a copy under `/cache/runtime/aneda/logs/` — `rank.<r>.log` for the
engine and launcher lines, plus `front.log` (dsfront) and `vision.log` (the encoder) on
rank 0. Vision is a plain tee, unfiltered; the engine and front streams pass through the
filter first.

**The filter.** `logprefix.py` runs once per stream. A line that does not start with `ts=`
gets the envelope with `event=log.line` and its original text appended verbatim; a stamped
line passes through untouched, so the in-process records flow through the same pipe. A crash
restarts the filter after 0.2 s and loses only the gap's bytes; a closed downstream (the
container stopping) exits 0 and ends the loop. Launcher and mod lines are stamped in bash as
`event=launcher.log` and `event=mod.log`; the mod's own copy is
`/cache/runtime/modlogs/aneda-launcher.log`.

**Retention.** `rotate()` runs once at launch, before the streams open: `rank.<r>.log` and
rank 0's `front.log` shift to `.1`…`.KEEP`, and older generations are pruned. Each stream
file then has its own 60 s ticker calling `rotate_live()`: once the live file passes
`ANEDA_LOG_MIB`, it shifts the generations up, copies the live file to `.1`, and truncates it
in place — copy-then-truncate keeps the writer's append fd on the live inode, and a failed
copy retries on the next tick. The live filename never changes.

| knob | default | meaning |
|---|---|---|
| `ANEDA_LOG_MIB` | `16` | single-boot size cap (MiB), enforced by the 60 s `rotate_live()` ticker |
| `ANEDA_LOG_KEEP` | `3` | generations kept beside the live file |
| `DSGB10_LOG_LEVEL` / `DSFRONT_LOG_LEVEL` | `info` | engine / front record level; `req.plan`, `turn` and `batch` are the `debug` records |

**Events (closed set).** `src=engine`: `batch`, `comm.up`, `engine.mem`, `engine.start`,
`fatal`, `glp.load`, `glp.refused`, `metrics`, `model.cert`, `model.moe`, `model.slots`,
`moe.oea`, `prefill.buffers`, `req.cold`, `req.done`, `req.drafts`, `req.error`, `req.images`,
`req.restart`, `sample.relax`, `serve.connect`, `serve.disconnect`, `serve.evict`,
`serve.keep`, `serve.kept`, `serve.listen`, `serve.refused`, `serve.spill`, `serve.stop`,
`serve.unspill`, `spec.cfmlp`, `spec.graph`, `spec.head4`, `spec.sim`, `state.evict`,
`state.keep`, `state.kept`, `state.room`, `state.spill`, `state.unspill`, `stats`, `turn`,
`watchdog.abort`, `wave.priorities`, `wave.probe`. `src=front`: `front.admin`,
`front.config`, `front.dump`, `front.engine`, `front.gate`, `front.listen`, `front.sessions`,
`front.start`, `front.stop`, `req.done`, `req.plan`, `req.refused`, `req.stop`, `stats`.
`src=vision`: `vision.exit`, `vision.log`, `vision.start`. `src=launcher` / `src=mod` / the
filter: `launcher.log`, `mod.log`, `log.line`.

## Upstream PRs integrated (image side)

The image (see `recipes/ds4/Dockerfile.aneda-ds41f`) applies two open upstream PRs as a tracked
patch series over the source pin: #15 (service-owned vision encoder) and #7
(`--stream-tool-args`). The launcher implements this arm's half:

- **Vision (PR #15).** `launch.sh` starts the encoder on rank 0 *before* the engine, so its
  weights load while the engine does; it restarts on exit after 2/10/60/300/900 s and is never
  counted as a serve failure (text requests are unaffected); it lives through engine restarts and
  is stopped with the front-end on `SIGTERM`. `dsfront` gets `--vision-addr 127.0.0.1:18950`.
  Upstream's `service.sh` supervision is what this reproduces — this arm does not run
  `service.sh`.
- **Streamed tool arguments (PR #7).** `launch.sh` passes `--stream-tool-args` by default. The
  flag is opt-in upstream because a call that is cut off leaves its client with unfinished
  arguments; `ANEDA_STREAM_TOOL_ARGS=0` restores the single-chunk behaviour.

## Switched fabric: why `NEXT_DEV* == PREV_DEV*`

Upstream's reference fleet is a cabled ring: port f0 faces rank r+1, port f1 faces
rank r-1, two RDMA devices per port (one per PCI domain). On this fleet's ConnectX-7
both **f1 ports are down** and the fabric is one switch, so the ring's two directions
ride the same two f0 devices (`NEXT_DEV0 == PREV_DEV0`, `NEXT_DEV1 == PREV_DEV1`), and
each rank's `NEXT_IP* == PREV_IP*`. The
engine accepts that shape (one QP per role, the GID check passes because each address is
on the named device); the TCP 18620 bootstrap binds rank r's `PREV_IP0` and dials rank
r+1's `PREV_IP0`, which is the same /24, one L2 domain on the switch. `DSGB10_RING_DIRECT=2`
then removes the ring relay entirely.

This is the arm's open commissioning gate: upstream has no switched-fabric deployment, and
neither 2026-11-17 boot ran `ring_test` — the engine starting shows it accepts the shape, not
that every link and collective is clean.

## Ownership

`launch.sh` and the engine run as root in the container, so the artifacts under
`/cache/runtime/aneda` stay root-owned by design; the mod reowns only the log directory
it shares with sparkrun's mod harness. Nothing under the cache is read by a user process.
