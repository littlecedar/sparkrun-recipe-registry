# picom-launcher

Pre-exec staging and the per-node launcher for the picom (`dsgb10`) arm —
[`recipes/ds4/zz-deepseek-v4.1-flash-1017-picom-tp4-1m.yaml`](../../zz-deepseek-v4.1-flash-1017-picom-tp4-1m.yaml).

The engine is [Picom-code/pico-dgx-ds4](https://github.com/Picom-code/pico-dgx-ds4) at
`7c123ad4` (MIT): a from-scratch C++/CUDA TP=4 engine with its own Rust front-end
(`dsfront`) and its own RDMA ring. It is not an SGLang/vLLM server, one process runs per
node, and all four processes take the same argv except `--rank`.

## What runs where

`run.sh` (pre_exec, root, before the serve command) stages what is environment-shaped:

- renders `/cache/runtime/picom/fleet.conf` from `PICOM_RANK_TAILS` +
  `PICOM_FABRIC_A/B` + `PICOM_DEV_A/B` + `PICOM_GID_INDEX` — the engine's own contract
  (`engine/comm/fleet.cpp` upstream): four device names that must exist by exact `ibv`
  name, one IPv4 per netdev (each device's GID at `GID_INDEX` must equal it), and all
  four ranks' `NEXT`/`PREV` addresses;
- creates the runtime directories and a mode-600 API key (`dsfront` refuses to start
  without one).

`launch.sh` (the container command, one container per rank) is the launcher:

- rank 0: prepares rank 0's artifacts, starts the engine, waits for its socket, then
  runs `dsfront` in the foreground and stops the engine on `SIGTERM`;
- ranks 1-3: prepare their artifacts and `exec` the engine.

It replaces upstream's `service.sh`, whose only irreplaceable job is starting ranks 1-3
over ssh — impossible when sparkrun owns one container per node. What it keeps from
`service.sh`: the page-cache drop before the engine starts (on GB10 a CUDA allocation
sees only free pages), the 100 GiB `MemAvailable` gate, and the same engine argv. What it
drops: the ring lock, restart supervision and kept sessions — a sparkrun arm is one
dedicated serve and sparkrun's lifecycle owns restarts.

Both paths also pass a fail-closed RDMA gate before the engine starts: `ibv_devices`
must list both `PICOM_DEV_A` and `PICOM_DEV_B`, or the launcher dies naming the device
and the container's RDMA user space. That is the 2026-11-17 shape — an image with
`libibverbs` but no `ibverbs-providers` aborted on every rank with
`RDMA device rocep1s0f0 not found` after the one-time artifact work.

## First boot prepares the per-rank artifacts

The engine does not read the HF checkpoint. It reads a per-rank weight file
(`dsw_convert`, 72.38 GiB) and per-rank Engram shards (`engram_pack`, 50.7 GB) plus a
518,048-byte hash map. Those are built from the pinned checkpoint on first boot, in the
container, once per node, and reused afterwards from `/cache/runtime/picom/` (node-local,
so each node keeps only its own rank's files, ~130 GB):

| artifact | producer | marker |
|---|---|---|
| `weights/rank<r>.dsw` | `dsw_convert --ckpt … --rank r --out …` | `rank<r>.dsw.ok` |
| `engram/engram-l1-r<r>of4.bin`, `engram-l14-r<r>of4.bin` | `engram_pack … r` | `engram/rank<r>.ok` |
| `engram/engram_hashmap.bin` | `make_hashmap_stdlib.py` | included in `rank<r>.ok` |

`PICOM_VERIFY=1` additionally runs `dsw_verify` (every byte of the weight file un-tiled
and compared: ~200-400 s) before the marker is written. The readiness budget in the
recipe covers the first boot; later boots start in minutes.

A failed conversion exits non-zero, so sparkrun sees a dead arm instead of a serve that
silently used a stale artifact.

## Knobs

All are env (recipe `env:` or `-o env.KEY=value`):

| key | default | meaning |
|---|---|---|
| `PICOM_RANK_TAILS` | — (required) | fabric address tails, rank 0-3, comma-separated; rendered as `<PICOM_FABRIC_A>.<tail>` / `<PICOM_FABRIC_B>.<tail>` |
| `PICOM_FABRIC_A` / `PICOM_FABRIC_B` | `192.168.0` / `192.168.1` | the two f0 /24s (cluster-internal values are never committed) |
| `PICOM_DEV_A` / `PICOM_DEV_B` | `rocep1s0f0` / `roceP2p1s0f0` | the two RDMA devices (PCI domains 0 and 2, port f0) |
| `PICOM_GID_INDEX` | `3` | RoCEv2 GID index, must match every device |
| `PICOM_RING_DIRECT` | `2` | switch mode: every rank writes to all peers itself (no relay); `0` for a cabled ring |
| `PICOM_ENGINE_ARGS` | upstream's production line | engine argv, minus `DSGB10_OEA` (see below). The engine parses strictly — an unknown token is `unknown argument <x>` and a start-time exit on every rank, and there is no `--help` |
| `PICOM_OEA` | empty | opt-in lossy batch-aware MoE re-route (`4,12,9` upstream); empty = strictly lossless |
| `PICOM_VISION` | `1` | upstream PR #15: run the checkpoint's ViT side encoder on rank 0 and give `dsfront` `--vision-addr`; `0` refuses images (400) |
| `PICOM_VISION_PORT` | `18950` | encoder's loopback port (same address in `--vision-addr`) |
| `PICOM_VISION_CMD` | the image's encoder | override the encoder command; `--host 127.0.0.1 --port <PICOM_VISION_PORT>` is appended |
| `PICOM_STREAM_TOOL_ARGS` | `1` | upstream PR #7: stream a tool call's name early and its arguments as they arrive; `0` is the pre-PR single chunk |
| `PICOM_MAX_TOKENS` | `32768` | `dsfront --max-tokens`: the default *and* the hard cap on one reply's generated tokens (upstream clamps a larger request, never refuses it) |
| `PICOM_FRONT_ARGS` | empty | extra `dsfront` args |
| `PICOM_MIN_AVAIL_GIB` / `PICOM_MIN_DISK_GIB` | `100` / `150` | fail-closed start gates |
| `PICOM_ENGINE_READY_S` | `900` | rank 0's socket wait |

## Upstream PRs integrated (image side)

The image (see `recipes/ds4/Dockerfile.picom-ds41f`) applies two open upstream PRs as a tracked
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
  arguments; `PICOM_STREAM_TOOL_ARGS=0` restores the single-chunk behaviour.

## Switched fabric: why `NEXT_DEV* == PREV_DEV*`

Upstream's reference fleet is a cabled ring: port f0 faces rank r+1, port f1 faces
rank r-1, two RDMA devices per port (one per PCI domain). On this fleet's ConnectX-7
both **f1 ports are down** and the fabric is one switch, so the ring's two directions
ride the same two f0 devices: `NEXT_DEV0 == PREV_DEV0 == rocep1s0f0`,
`NEXT_DEV1 == PREV_DEV1 == roceP2p1s0f0`, and each rank's `NEXT_IP* == PREV_IP*`. The
engine accepts that shape (one QP per role, the GID check passes because each address is
on the named device); the TCP 18620 bootstrap binds rank r's `PREV_IP0` and dials rank
r+1's `PREV_IP0`, which is the same /24, one L2 domain on the switch. `DSGB10_RING_DIRECT=2`
then removes the ring relay entirely.

This is the arm's open commissioning gate: upstream has no switched-fabric deployment, and
neither 2026-11-17 boot ran `ring_test` — the engine starting shows it accepts the shape, not
that every link and collective is clean.

## Ownership

`launch.sh` and the engine run as root in the container, so the artifacts under
`/cache/runtime/picom` stay root-owned by design; the mod reowns only the log directory
it shares with sparkrun's mod harness. Nothing under the cache is read by a user process.
