---
name: sparkrun-recipe-boot-triage
description: "Boot fails, launch dies, unhealthy: reproduce, check sparkrun/container logs, boot gates."
---

# sparkrun recipe boot triage

Reproduce first, then classify by where the failure lands: orchestration goes to the sparkrun launch log, the actual failure to the container serve log on the node.

## Registry image distribution fails (OCI Relay stalls)

Symptom in the launch log:

```
OCI Relay: <node-ip>: receiving / decoding missing layers; 1.7 GiB received (up to 6.8 GiB needed), …
OCI Relay: <node-ip>: failed; 1.7 GiB transferred; 13 layers reused
Error: inference launch failed: launch_inference failed: Registry image distribution failed on: <node-ip>
```

Cause: the relay's registry download (here ghcr.io) stalls — throughput collapses to a few MiB/s mid-transfer.

Fix: seed the node's docker cache directly, then relaunch —

```bash
ssh <node> 'nohup docker pull <image:tag> > /tmp/pull.log 2>&1 &'
# when pull completes, rerun the same sparkrun command
```

The OCI Relay checks receiver caches first ("checking receiver caches and starting transfers", "13 layers reused"), so a pre-pulled image needs no registry download at distribution time. One-time cost per image per node.

## Other gates

- Launch log clean ≠ server up: the failure can be in the container serve log on a different machine.
- A recipe whose config "cannot boot" must still be boot-proven, not probe-proven, before shipping.
- Cluster mod delivery needs `--transfer-mode local` (persist via `sparkrun cluster update <name> --transfer-mode local`), else a node cloning the registry itself never sees an unpushed mod.
- `sparkrun` calls from the local clone need `HOME="$PWD/.local/sparkrun-home"`; on the head node plain `sparkrun` works from `${WOPR_RUN_FROM_DIR}`.
- Verify tree sync with md5sums (recipe + profile) between local and head before benchmarking edits.
