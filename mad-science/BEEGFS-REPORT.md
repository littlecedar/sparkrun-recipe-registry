# BeeGFS as a hyperconverged HF cache — cost and performance assessment

**Status:** 2026-10-20, read-only. No package installed, nothing launched, stopped or reconfigured: node
figures come from `df` / `free` / `uname` / `mokutil` / `hf cache ls` / `dpkg -l` / `lspci` /
`ib_write_bw`, disk figures from `dd` and `O_DIRECT` read loops, and Engram figures from `/proc/diskstats`
read-sector and read-completion deltas around two short completions (128 and 512 tokens) served by the
production arm already running on `.30`. Nothing here is booted hardware evidence for BeeGFS itself, and
no BeeGFS number was measured — the pool's performance is bounded from the hardware it would run on.

**Addendum 2026-10-22:** §9 adds measured inter-node transfer throughput (control→node and
node→node, three shapes, two rails) and the fetch-once/fan-out rule that follows from it.

**Question:** what would it cost, in resources and in boot/serve performance, to install and operate
BeeGFS across `.30`–`.35` as one shared Hugging Face cache — and is it worth doing.

**Answer:** not now — there is no measured performance upside to buy (§5), the capacity benefit is one the
existing storage policy already reaches by pruning, and the only license-free shape adds a fleet-wide,
unmirrored dependency through a kernel module this platform does not test (§6).

---

## 1. What the cache is today

Each node keeps its own HF cache. There has been no shared mount since 2026-10-03, when the NFS-over-RoCE
export was removed and `distribution.model.enabled` flipped to `true` so sparkrun fans a model out to
every runner node instead of serving it from one box (`attic/ds4/ds4_NOTES.md:331-345`). The budget is
the registry's, quoted rather than restated (`STORAGE-POLICY.md:380-381`):

> Runtime cache ≤ 0.5 TB per node. HF cache ≤ 2.2 TB per node. `df /home` free ≥ 1.0 TB at all times,
> on every node.

| node | repo entries | HF cache, logical | free on `/` | memory in use |
|---|---:|---:|---:|---:|
| `.30` | 48 | 2.63 TB | 591 GB | 106 GiB (serving) |
| `.31` | 11 | 1.98 TB | 1.20 TB | 107 GiB (serving) |
| `.32` | 12 | 2.11 TB | 996 GB | 107 GiB (serving) |
| `.33` | 10 | 2.06 TB | 967 GB | 106 GiB (serving) |
| `.34` | 32 | 1.82 TB | 751 GB | 4 GiB (idle) |
| `.35` | 23 | 1.96 TB | 600 GB | 4 GiB (idle) |
| **fleet** | **136 entries / 56 distinct ids** | **12.56 TB** | **5.1 TB** | |

Three facts follow, and they are the whole motivation:

- **12.56 TB of logical cache holds 3.59 TB of distinct content.** The other 8.97 TB — 71 % — is the
  same repos stored again on other nodes (`deepseek-ai/DeepSeek-V4.1-Flash` 510.3 GB on five nodes,
  `littlecedar/…-EXL3-2.9bpw-with-engram` 413.4 GB on three, and so on). `hf cache ls` sizes are an
  upper bound on real bytes wherever a repo is a symlink farm (`STORAGE-POLICY.md` measured 9.6 MB real
  against 78.9 GB reported for one repo), so treat 8.97 TB as the ceiling of what could be reclaimed.
- **Five of six nodes are already below the 1.0 TB free floor** — only `.31` is above it. That is why
  the question was asked.
- **One arm reads storage in the hot path.** The production `deepseek-ai/DeepSeek-V4.1-Flash-1017` serve
  on `.30`–`.33` (`--tp 4`) reads its packed Engram from each node's own NVMe on every decode step;
  everything else loads weights once at boot and then reads no storage at all. A separate 202.8 GB
  TP=2 Engram pack (`littlecedar/…-EXL3-2.9bpw-with-engram`, 2 × 101.38 GB, fully allocated) also sits in
  the cache; it was used below as a dense 101 GB test object for raw device measurements, not as the
  live job's data.

## 2. The design being costed

One management service on `.30`, one metadata target on `.34` (20 GB, directory-based on the existing
ext4 so no repartitioning), one storage target per node at 1.2 TB, six clients with RDMA on the existing
200 Gb/s port, a free Community license key installed on the management host because six mounts exceed
the unlicensed limit of five, and the pool mounted at `~/.cache/huggingface` — the path sparkrun binds
into `/cache/huggingface` (`sparkrun/orchestration/primitives.py:81-82`), so no recipe changes. The
cluster profile would move to `distribution.model.skip_fan_out: true` with `preserve_perms: false`.

Two properties of that shape decide the rest, and neither is a tuning choice:

- **It is unmirrored.** Buddy mirroring and HA are Enterprise features (license agreement §3.4.3), so the
  free design has one copy of every byte. A single node's disk loss takes its share of the pool with it,
  and the pool is then the only copy of that content — re-fetched from the internet at the measured
  6 MB/s for a large body (§9), i.e. ≈9.8 h for the 210.72 GB TensorFold body and ≈24 h for a 510 GB
  repo, per node. A mirrored variant (three buddy pairs, 3.6 TB usable) is costed in §3 and marked
  Enterprise-only throughout.
- **The default file pattern is one target.** A file lands on a single storage node, so aggregate read
  bandwidth needs `beegfs-ctl --setpattern --numtargets`; and because there is no mirror, striping
  multiplies per-file exposure to a target loss rather than reducing it.

## 3. Resource cost

| resource | cost of the six-node pool | basis |
|---|---|---|
| Pinned RAM, per client | ≈ 0.19 GB non-swappable | `[INFERENCE]` — 12 connections per peer × 7 peers (1 management + 6 storage) = **84 × 1.12 MB ≈ 94 MB** for the client, plus **84 ≈ 94 MB** for the local storage service it also runs ⇒ ≈ 188 MB |
| Pinned RAM, metadata node | ≈ 0.35 GB | `[INFERENCE]` — management daemon 12 × (6 storage + 6 clients) = 144 × 1.12 MB ≈ **161 MB**, plus that node's own storage service (94 MB) and client (94 MB) |
| Borrowable RAM | page cache only; the kernel reclaims it | — |
| CPU | negligible at load-only traffic | storage and metadata services idle between boots |
| Disk, pool | 1.2 TB per target, grown as duplicate copies are pruned | BeeGFS adds chunk files as a target fills; today a node has only 0.59–1.2 TB free |
| Disk, metadata | 20 GB | 0.3–0.5 % of capacity, or 500 GB ≈ 150 M files per the requirements page |
| Disk, steady state | ≈ 1.75 TB free/node unmirrored; ≈ 1.15 TB/node mirrored | 5.1 TB free + 8.97 TB reclaimed − 3.59 TB pool (mirrored: − 7.18 TB), both above the 1.0 TB floor |
| Fabric | 112 Gb/s measured over RDMA verbs, shared with NCCL/EP and with Engram reads; file transfers reach 2.05–6.6 GB/s (§9) | `ib_write_bw`, 4 MiB × 8 QP and 8 MiB × 16 QP |
| License | free for internal use; a key is required at six clients; mirroring/HA is Enterprise | licensing page, agreement §3.1–3.4; capacity caps (200 TB SSD) are far above a 3.6 TB pool |
| Operator | one working day for a first node, 2–3 h per remaining node, plus a reboot window | `[ESTIMATE]` |

The pinned RAM is small enough not to matter on an idle node and small enough to matter only at the
margin on a serving one: `.30`–`.33` keep 14–15 GiB available while a 106–107 GiB serve runs. The disk
arithmetic says the same thing more loudly: **after migration the fleet is comfortably above its own
floor**. Space is not the blocker. Sequencing is — a pool staged *beside* the current per-node copies
would need 16.1 TB and there are 5.1 TB, so migration has to be repo by repo with at most one repo
(≤ 510 GB) in flight.

## 4. What it would break or degrade

**Every boot depends on one filesystem.** Today a node's cache is isolated: a full disk or a wedged
network is one node's problem. With the pool, the management service becomes a precondition for every
launch on every node, and a metadata target failure is a fleet-wide outage of the ability to boot
anything — before any model has loaded.

**The hot path changes from local syscalls to network round trips.** Engram is the only per-token disk
read this fleet has (§5), and on a pool each gather becomes a client-to-storage RPC instead of a local
`pread`. The reader is not naive about this: one process-wide pool of 32 threads takes the whole step's
rows for both layers in a single submission — measured at C1 on the TP=2 arm as **7.7 ms serial versus
3.1 ms parallel** (`mount-dsv41-exl3-patches/files/engram.py:636-645`) — so a network round trip lands
once on the batch's wall time, not once per row. Bandwidth and IOPS are irrelevant at these volumes;
what changes is that batch's latency, and the size of the change is what the pilot measures.

**HF cache semantics are symlink- and lock-heavy.** Snapshot entries are relative symlinks into `blobs/`,
so the whole `hub/` tree must be mounted, not just a blobs directory. `filelock` — what `hf download`
uses to serialize concurrent fetches — relies on fcntl advisory locks, which BeeGFS supports; treat that
as advisory-only across six clients. The `xet` chunk cache (~56 MB per node today) becomes a shared
multi-writer tree with unverified behavior: `[UNVERIFIED]`, and the one thing to test before anyone
trusts it.

**Ownership is a non-issue for this design.** Only the host user writes the cache (with
`skip_fan_out: true`, on the head); containers mount it read-only — `/cache/huggingface` is listed in
`sparkrun/api/_materialize.py:135`'s `read_only_targets`. Mods write to `/cache/runtime`, not the HF tree.
BeeGFS does not root-squash by default, so no UID mapping is required.

**The storage tuning guide does not apply.** It prescribes THP `always`, `dirty_ratio` 5–20 and
`read_ahead_kb` 4096 for a dedicated storage node; on a node holding a 106 GiB serve with 14 GiB
available, that advice is actively hostile and this design does not adopt it.

## 5. Performance impact, measured

The ceiling comparison is blunt. A 200 Gb/s RoCE port measures 112 Gb/s (14 GB/s) over RDMA verbs —
that is not a file-transfer rate: measured file transfer is 5.1–6.6 GB/s with four plain TCP streams
and 2.05–2.25 GB/s with four ssh streams (§9) — both on a test blob addressed over the rails, whereas
the body copies that have actually run went over management at 247–250 MB/s per stream (§9). One
node's NVMe, on a PCIe Gen5 ×4 link, reads 6.2–8.0 GB/s sequentially from a fully allocated file,
and serves **102,969 random 4 KiB reads/s with 32 outstanding reads** (≈ 0.42 GB/s, implied ≈ 0.31 ms
per read) — 32 being the engine's own Engram reader width. The internet delivers **6 MB/s** for a
large body (§9).

- **Quantized and repacked loads are engine-bound, not storage-bound.** SGLang's repack load of a
  63.03 GB checkpoint took 407.20 s — **155 MB/s**. vLLM loading a 139.3 GB TP=2 checkpoint took 540.28 s
  — **258 MB/s aggregate, 129 MB/s per rank**. Against the aggregate the pair is 24–52× below the device
  and 54–90× below the fabric; per rank the vLLM figure widens that to 48–62× and 108×. A faster shared
  filesystem cannot shorten those boots; nothing on the storage side is the limiter.
- **One case is bandwidth-shaped.** A plain safetensors load ran at 4.07 GB/s (44.48 GB in 10.92 s, with
  page-cache state unknown). Four ranks loading concurrently need 16 GB/s, but with the default
  single-target pattern they share one target's 14 GB/s link, so a TP=4 plain load through one pool is
  **fabric-bound: neutral to roughly 10–15 % slower** than four independent disks
  (`[INFERENCE]`, from 16 GB/s demanded against 14 GB/s available, not measured). Striping helps, and
  also widens per-file exposure to a target loss.
- **The cold path saves fan-out, not download time.** Dedup replaces five copies with one fetch plus five
  reads from the pool, but the fetch is internet-bound at 6 MB/s (§9). The saving is the copies.
- **Metadata cost is real but unquantified here.** Every cache operation becomes one RPC to the metadata
  service instead of a local syscall. A boot touches a few hundred cache entries; an `hf cache ls` or a
  fresh download touches thousands. No latency number is claimed — the latter is the case to measure
  first if anyone pursues this.

### Engram demand, measured

The owner asked for the IOPS and throughput that Engram-bearing models actually require. Two views
agree, and they are different units:

- **Application view.** The reader issues one `pread` per row of **264 B** (256 B weight + 8 B scale);
  rows per step = tokens × local heads × 2 layers, and the whole step's rows for both layers go out as
  one batch over a 32-thread pool (`mount-dsv41-exl3-patches/files/engram.py:636-645`). At the TP=2
  arm's C1 shape that batch was measured at **3.1 ms parallel against 7.7 ms serial**. Application bytes
  are therefore a few KB per token — the tables are 384 M rows × 256 B (16 rows per 4 KiB page), but only
  a handful of rows are touched.
- **Device view.** What actually reaches the NVMe was measured on the live **TP=4** production serve by
  sampling `/proc/diskstats` around two greedy completions. Every row that misses page cache costs a
  4 KiB page, which is why the device sees more than the application asks for:

| quantity | measured |
|---|---|
| reads per token (4 KiB pages) | **5.1** (128 tokens) / **3.4** (512 tokens, warmer cache) |
| bytes per token | **22.9 KB** / **14.9 KB** |
| at the arm's benchmarked 67 t/s | **≈ 340 IOPS, ≈ 1.5 MB/s** |
| at the measured 120–125 t/s | **428–606 IOPS, 1.9–2.7 MB/s** |
| one node's device (4 KiB random, 32 threads) | **102,969 IOPS**, 6.2–8.0 GB/s sequential |
| headroom | **≈ 170–300×** on IOPS, ≈ 3,000× on sequential bandwidth |

The disk-observed figure is a **floor**: warm rows are served from page cache and generate no disk read,
so the true demand is at least this and plausibly higher. Even so, the conclusion is stable: the
requirement is real and tiny — hundreds of IOPS, a couple of MB/s — so **bandwidth and IOPS are not the
constraint**. The exposure is the batch's latency: because the 32-thread pool puts the whole step's rows
in flight at once, a pool adds roughly one round trip to that batch, not one per row. On the measured
3.1 ms batch, +50 µs is +1.6 % of the gather and **+0.3 % of a 14.9 ms step at 67 t/s**; +200 µs would
be +1.3 % of the step. Serial execution would be far worse — which is exactly what the pool exists to
prevent — so the pilot in §8 measures the batch on the pool rather than re-deriving it.

## 6. Verdict

**Not now**, for four reasons in order of weight, each with its number:

1. **The benefit is one policy already reaches.** The pool's entire capacity value is the 8.97 TB ceiling
   (upper bound, §1), and `STORAGE-POLICY.md`'s active-arm residency plus `hf cache rm` reaches the same
   material with no new dependency. BeeGFS converts a policy artifact — each node keeps what it last
   served — into infrastructure; nothing measured requires the infrastructure. The one honest difference:
   a pool re-materializes a model on any node on demand, where the policy needs a re-fetch.
2. **The license-free shape is unmirrored.** Today a node failure costs that node's cache. With a pool,
   one target loss costs a sixth of the fleet's only copy, re-fetched at 6 MB/s (§9).
3. **Install risk on this exact platform.** Secure Boot is enabled with only Canonical's key enrolled, so
   an out-of-tree client needs a MOK enrollment and a console reboot on each of six nodes. The headers for
   `6.17.0-1032-nvidia` are installed, so the DKMS build can start — but that kernel is not a combination
   BeeGFS tests, and every DGX OS update re-opens the build. The management service then sits in front of
   every boot.
4. **No measured performance upside.** The only hot-path reader needs 340–600 IOPS and 1.5–2.7 MB/s
   against 102,969 IOPS and 6.2–8.0 GB/s — 170–300× inside the device — so the pool neither fixes a
   bottleneck nor starves on bandwidth. Its only exposure is the Engram batch's latency, and the engine
   already batches that batch over 32 threads; a network round trip lands once per step, not once per
   row. That is not a reason to refuse the design, and not a reason to adopt it either.

## 7. When to revisit

- Fleet free space ≥ 16 TB, enough to hold the pool beside the existing caches (3.59 + 12.56 ≈ 16.2 TB)
  so every byte can be verified before anything is deleted. Today: 5.1 TB.
- An Enterprise relationship exists for mirroring/HA, *and* one namespace is wanted over six.
- A workload appears whose load path exceeds the measured file-transfer ceiling (§9). None measured:
  everything runs at 0.129–4 GB/s, and no transfer path exceeded 6.6 GB/s.
- The pain shifts from capacity to per-node cache *management* — operator time deciding what lives where —
  which is the one thing the pool genuinely removes.

Today's duplicates are a policy artifact, not an architectural limit of per-node caches.

## 8. What would overturn this verdict

A two-node pilot on `.34`/`.35` (idle, 107–112 GiB available), measuring:

1. a cold plain-safetensors load, local disk versus the pool;
2. ds4 decode with Engram on the pool versus NVMe, timing the Engram batch's wall time per step (the
   engine's 32-thread pool already parallelizes it, so the question is what one network round trip adds
   to that batch) alongside per-step throughput and `/proc/diskstats` on both paths;
3. `hf cache ls` plus one `hf download` to price the metadata path.

Those three numbers are the prerequisites for any adoption decision. None was taken here, and none should
be taken on a node that is serving.

## 9. Getting a body onto a node: fetch once, fan out on the fabric (measured 2026-10-22)

**Status:** measured `[VERIFIED]` for every shape in the table; the RDMA link capacity remains
`[LIKELY]` because no file path reaches it. Taken on an existing 5.42 GiB / 5.818 GB safetensors
blob already resident in two nodes' HF caches
(`littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram`), so no bytes were written to measure it.
Nothing was booted, stopped or reconfigured; every test file and tmpfs destination was removed
afterwards and the container count on each node touched is unchanged.
Receipts: `.scratch/beegfs/xfer-head-cx7-20261022.log`, `xfer-n4n5-cx7-20261022.log`,
`xfer-head-mgmt-20261022.log`.

**One correction is recorded below and it changes the policy, not the table.** Every rail figure here
was taken on a 5.818 GB test blob addressed by rail address. The multi-hundred-GB body copies that
actually ran on this fleet were addressed by management hostnames and therefore crossed the 2.5 GbE
management NIC, never the rails (§"The copy that actually ran", below). The rails are what a fan-out
*should* use; they are not the path any large copy has yet taken.

**The asymmetry that decides placement policy.** A 210.72 GB body fetched from the Hub over the
WAN ran at **6 MB/s effective** (`bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard`, 210.72 GB),
because the throttle is per-IP: two nodes fetching in parallel split that budget rather than
doubling it. That is **≈9.8 h per node**, ≈49 h to place the same body on five. The same bytes
move node-to-node in **≈1.5–2 min** (measured, below). Inter-node transfer is therefore the default
path for any large body, not an optimisation.

### Throughput per path and shape, 2026-10-22

Node roles only; "CX7 rail 1/2" are the two 200 GbE NIC ports (both `Speed: 200000Mb/s`), and
"management" is the 2.5 GbE link. `nc` is a plain TCP pipe with no ssh; `rsync`/`scp` are
ssh-over-CX7, i.e. what the fan-out commands actually use. Repeat runs are listed `a / b / …`;
the single-stream file is 5.818 GB, the 4-shard shapes 20.87 GB.

| path | shape (what it measures) | MiB/s | GB/s |
|---|---|---:|---:|
| control → compute node, CX7 rail 1 | `nc` 1 stream (link, no ssh) | 1739 / 1837 / 1904 / 2130 | 1.82–2.23 |
| control → compute node, CX7 rail 1 | `nc` 4 streams, disjoint ranges (link aggregate) | 5345 / 4896 / 5767 / 6296 | 5.13–6.60 |
| control → compute node, CX7 rail 1 | `rsync` 1 stream (**the staging path**) | 540 / 552 | 0.566 / 0.579 |
| control → compute node, CX7 rail 1 | `scp` 1 stream | 593 / 589 | 0.622 / 0.618 |
| control → compute node, CX7 rail 1 | `rsync` 4 streams, 4 shards | 2150 / 1954 / 2076 | 2.05–2.25 |
| control → compute node, CX7 rail 1 | `scp` 4 streams, 4 shards | 2130 / 1978 / 2074 | 2.07–2.23 |
| compute node → compute node, CX7 rail 1 | `nc` 1 stream | 1543 / 1741 | 1.62 / 1.83 |
| compute node → compute node, CX7 rail 1 | `nc` 4 streams | 3911 / 4705 | 4.10 / 4.93 |
| compute node → compute node, CX7 rail 1 | `rsync` 1 stream | 304 / 281 | 0.319 / 0.295 |
| compute node → compute node, CX7 rail 1 | `scp` 1 stream | 351 / 324 | 0.368 / 0.340 |
| compute node → compute node, CX7 rail 1 | `rsync` 4 streams, 4 shards | 934 | 0.980 |
| compute node → compute node, CX7 rail 1 | `scp` 4 streams, 4 shards | 2151 | 2.255 |
| compute node → compute node, CX7 rail 2 | `nc` 1 stream / 4 streams | 560 / 3749 | 0.587 / 3.93 |
| control → compute node, management | `nc` 1 / `nc` 4 / `rsync` 1 / `scp` 1 / `rsync` 4 | 33–56 | 0.03–0.06 |
| control → compute node, **management** (`enP7s7`) | `rsync` 1 stream, **an actual body copy** (not the test blob) | 236–238 | 0.247–0.250 |

Source of every row: `.scratch/beegfs/xfer-*-20261022.log`; disk baselines from the same script.

**What is the bottleneck, per shape.**

- **One ssh stream is crypto-bound, not fabric-bound.** Every `rsync`/`scp` single stream landed in
  0.28–0.62 GB/s while one plain TCP stream on the same pair carried 1.62–2.23 GB/s. A single
  `rsync` is one ssh channel in one core: it reports the cipher and per-core throughput, not the
  link. **`iperf3` is not installed on any node** (checked), so the clean-link figures here are
  TCP-based (`nc`), not RDMA; the link's RDMA capacity is the earlier `ib_write_bw` 112 Gb/s
  (14 GB/s) figure and remains `[LIKELY]` for file transfer because no file path comes near it.
- **Parallel ssh streams scale linearly until CPU runs out, then flat.** 4 streams gave 2.05–2.25
  GB/s on the control → node path (3.6–3.9× one stream) and 0.98–2.26 GB/s on the node → node path,
  while 4 plain TCP streams on the same links gave 4.1–6.6 GB/s. So the extra ~2.5–4 GB/s is there
  and unreachable through ssh; ~2.2 GB/s is the practical fan-out ceiling with 4 streams, and it is
  the same on both paths — stream count, not node pair, is what moves.
- **Disk is not the limit at these volumes.** Local reads of the same file: `O_DIRECT` 4 MiB reads
  5.50–6.28 GB/s on three nodes; a warm cached read 21.6 GB/s (two other warm reads of the same file
  on a busy node returned 0.84–1.26 GB/s, so the cached-read figure is not load-bearing). Cold disk
  and 4-stream TCP are the same order (5.5–6.6 GB/s), so the 4-stream `nc` figure is at the
  disk/link boundary and the ssh shapes sit far below both.
- **The management network is the wrong path for staging.** 33–56 MiB/s, and `nc` did not scale
  across streams — measured while the fleet was fetching over the WAN through the same uplink, so
  treat it as *shared and contended*, not as a clean 2.5 GbE number. The cluster profile already
  routes transfers over CX7 (`transfer_interface: cx7`); this is why that setting matters, and a
  fallback to management hostnames would make a 210 GB fan-out a 1-day operation instead of a
  2-minute one.

### The copy that actually ran, 2026-10-22: management, not the rails

A cross-node body copy of several hundred GB from `.31` to `.34` — exactly the fan-out the rule
below exists for — was launched against **management hostnames**, so every byte crossed the 2.5 GbE
management NIC and the rails were never exercised. The evidence is routing and socket state, not a
stopwatch:

- `ip route get .NN` from the sender resolved to **`dev enP7s7`**, the management port, not a
  CX7 rail port;
- the copy's own ssh socket read `.NN:44468 -> .NN:22` in `ss -tnp` — both ends
  management;
- the single stream held **247–250 MB/s**, ≈80 % of the 2.5 GbE line rate (2.0 of 2.5 Gbit/s), which
  is what a *clean* management link does and is nowhere near a rail's 0.55–0.62 GB/s ssh shape.

**This does not contradict the 33–56 MiB/s row.** That row was `nc`/`rsync` against a node whose
uplink the fleet was saturating with a concurrent WAN fetch; it measures a *contended* management
link. The body copy ran when nothing else was competing. Both numbers are real — they describe
different load — and the pair is the reason management must be sized from the copy that is
competing with it, never from a single sample.

**What the mistake cost.** At 247–250 MB/s a 210 GB body takes ≈14 min on one management stream.
The same bytes take ≈1.6–1.8 min across four rail ssh streams at 2.05–2.25 GB/s, and ≈35 s across
four plain-TCP streams at 5.1–6.6 GB/s *(both divisions arithmetic on this section's own numbers,
not separately timed)*. On management the port, not the cipher, is the ceiling, so extra streams buy
almost nothing and the rail advantage grows with body size.

**The rail measurement taken after the copy was re-addressed.** Two parallel ssh streams on the
`the CX7 plane-A subnet` rail measured **646–751 MB/s aggregate** (≈323–375 MB/s per stream). That is less
than twice the single-stream rail `rsync` figure (0.57–0.58 GB/s), so the second stream's gain on
this pair is partial: the "4 streams scale 3.6–3.9× one stream" result above was measured
control→node, and node→node did not scale the same way.

**Provenance gap, stated rather than filled.** Neither the 247–250 MB/s body-copy rate nor the
646–751 MB/s two-stream figure has a log in `.scratch/beegfs/`; the three receipts there are the
synthetic test-blob runs. Both numbers come from the running copies' own progress plus `ip route
get` and `ss -tnp` taken on the sender at the time, so they are `[VERIFIED]` observations with no
archived artifact. If either becomes load-bearing for a plan, re-measure it and keep the log.

### The rule

A model body above roughly **100 GB** is fetched **once** over the WAN, on a node, and fanned out
node-to-node **by rail address** (`the CX7 plane-A subnet` / `plane-B subnet`), never by management
hostname — the section above is what the hostname form costs. Below that the arithmetic no longer
favours the extra hop strongly (a 30 GB body is ~1.4 h of WAN against ~15 s of fan-out — the
fan-out still wins, but it is a convenience, not a rescue). Never fetch the same body N times: the
WAN throttle is per-IP, so N parallel fetches cost N × 9.8 h of the *same* budget.

### The procedure

```bash
# 1. fetch once, on a compute node with room — not on the control
hf download <org>/<name> --revision <pin>
du -s ~/.cache/huggingface/hub/models--<org>--<name>     # record; compare against the Hub file sum

# 2. fan out, 4 streams at a time (one per peer), over the CX7 addresses
for p in <peer-a> <peer-b> <peer-c> <peer-d>; do
  rsync -a --copy-unsafe-links --ignore-times \
    ~/.cache/huggingface/hub/models--ORG--NAME/ \
    ${WOPR_USERNAME}@$p:~/.cache/huggingface/hub/models--ORG--NAME/ &
done; wait

# 3. verify on every node, then launch from the node-local copy
du -s ~/.cache/huggingface/hub/models--ORG--NAME   # before/after; equal size = complete
sparkrun run recipes/<lane>/<recipe>.yaml -H <nodes> --offline
```

- Copy the repo **directory**, never a snapshot entry: `rsync -a` of a single snapshot file copies the
  76 B symlink and exits 0, which reads as a successful transfer of nothing (measured while setting
  this up). `-L` would dereference and double the tree's disk use; `--copy-unsafe-links` keeps
  `blobs/` single and the snapshot symlinks relative. The 4-shard rows above used `-aL` and were
  size-verified at 20,874,597,228 B on the destination.
- 4 streams, not 8: 4 is where scaling was measured linear (2.05–2.25 GB/s). More streams buy CPU
  exhaustion, not bandwidth.
- Every `<peer-*>` in step 2 must be a **rail** address (`the CX7 plane-A subnet` / `plane-B subnet`), never a
  management hostname. A management-addressed loop still exits 0, still moves the bytes, and runs at
  ~250 MB/s per stream — and it is the mistake §"The copy that actually ran" records, whose rate was
  then quoted for a whole window as if it were a fabric number.
- `du -s` equality is necessary but not sufficient for completeness; verify `blobs/` against the
  Hub's own LFS `sha256` before a multi-rank boot rather than trusting the size.
- `--offline` at launch is what makes the node-local fetch authoritative; sparkrun otherwise stages
  through the control, which does not fit a body of this size (§ Capacity note below).

### Caveats this cluster has already been bitten by

- **A partial download must never be pruned.** Interrupted `hf download`s leave incomplete `blobs/`;
  deleting the tree discards hours of a 6 MB/s fetch.
- **`du -shL snapshots/*` reports sparse apparent size** (a partial cache once read 207 GB at 8 %
  complete). Completeness is `du -s` on the repo directory, per node, before and after.
- **A digest-pulled image is stored untagged**, so a peer's `docker image prune` deletes the build
  that was just pulled; re-tag immediately, and check dangling images with `docker images -a`.
- **`dsv41-engram` is not a `models--*` tree.** An `hf cache` prune empties it and the launch then
  fails `--require-engram`; the documented recovery was a re-fetch. Copy it by path like a model
  (step 2 above) and keep it out of any prune.

### Capacity note that decides staging vs node-local

The control's root filesystem holds a 141 GB free margin at the time of writing, and a 210.72 GB
TensorFold body plus its Engram tables does not fit in it. Practical rule: **bodies above ~130 GB
are node-local** (`hf download` on the node, `--offline` at launch); bodies below that may stage
through the control. This is the decision that shaped the 2026-10-22 cross-node body copy: a body
far above the ~130 GB line, so it was fetched once on a node and fanned out node-to-node — and, per
§"The copy that actually ran", over the management NIC because the copy was addressed by management
hostnames.

### Claims this measurement corrects

- §2, §5 and §6 quoted the internet fetch as 76–142 MB/s. That figure came from a 2026-10-15
  prefetch of two smaller repos, and it does not hold for a 210 GB body today: **6 MB/s, ≈9.8 h**
  is the number to plan with. (The cited `mad-science/TODO.md:519` no longer resolves — that file
  has been rewritten since.) The conclusion is unchanged and strengthened: a pool cannot save a
  fetch, and neither can a policy; only fetching once can.
- §3's "112 Gb/s measured" and §5's "14 GB/s" are **RDMA verbs**, not file transfer. The measured
  file-transfer ceiling is 5.1–6.6 GB/s with 4 plain TCP streams and 2.05–2.25 GB/s with 4 ssh
  streams; read those numbers wherever a boot or fan-out time is being derived.
- §7's revisit trigger "a workload whose load path exceeds the fabric's ~14 GB/s" is restated: no
  measured load path exceeds 4 GB/s, and no file-transfer path exceeds 6.6 GB/s.
- **Any statement that the cross-node body copies ran "on the fabric" is wrong, this report's own
  framing included.** They were addressed by management hostnames, so `ip route get` resolved them
  to `dev enP7s7` and the socket was `.NN:44468 -> .NN:22` — the 2.5 GbE management
  NIC, at 247–250 MB/s per ssh stream. The CX7 rows above measure what the rails do with a test
  blob between rail addresses; no large copy has yet used them, and the 112 Gb/s RDMA figure has
  still never been exercised by a file transfer at all.

---

## How these numbers were taken

- Cache census: `hf cache ls`, `df -h /home`, `free -g` on `.30`–`.35`, 2026-10-20; receipt
  `.scratch/beegfs/hf-cache-census-20261020.txt`. Fleet figures are decimal GB from `hf cache ls`.
- Fabric, verbs: `ib_write_bw` between two idle nodes, 4 MiB × 8 QP and 8 MiB × 16 QP, 4 s. RDMA
  verbs only; the file-transfer numbers in §9 were measured separately.
- Disk: `dd iflag=direct bs=4M count=256` at three offsets of a fully allocated 101.38 GB Engram blob,
  and a threaded 4 KiB `O_DIRECT` random-read probe over the same file (`os.preadv`, aligned buffer).
  Link geometry from `current_link_speed` / `current_link_width` (32 GT/s, ×4).
- Engram demand: `/proc/diskstats` read counters on the node's NVMe around two `POST /v1/chat/completions`
  calls (128 and 512 generated tokens, greedy) on the live TP=2 arm; reads and sectors divided by
  completion tokens. Disk-observed values are a floor because warm rows never reach the device.
- Load rates: the `Loading weights took` / `Load weight end` lines of the arms' own boot logs.
- Inter-node transfer (§9), 2026-10-22: a 5,817,580,796 B safetensors blob already resident in two
  nodes' HF caches, so the measurement wrote no source data. `nc` 1 and 4 streams (`dd bs=4M` piped
  to `nc -N`, 4 streams over disjoint byte ranges), `rsync -aL --ignore-times` and `scp` at 1 and 4
  concurrent streams, each shape twice (the 4-stream shapes three times); the 4-shard destination was
  size-verified at 20,874,597,228 B with `stat`. Local `dd iflag=direct bs=4M` and a warm cached read
  give the disk/memory baseline. `iperf3` is installed on none of the nodes, so every link figure is
  TCP, not RDMA. Receipts: `.scratch/beegfs/xfer-{head-cx7,n4n5-cx7,head-mgmt}-20261022.log`.
- WAN baseline (§9): 6 MB/s effective on `bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard`
  (210.72 GB), 2026-10-22; per-IP throttled, since two parallel node fetches split the budget.
- BeeGFS facts, read 2026-10-20 (the Community license agreement §3.1–3.4 supplies the client,
  capacity and Enterprise-feature limits):
  - <https://doc.beegfs.io/latest/system_design/system_requirements.html>
  - <https://doc.beegfs.io/latest/release_notes.html>
  - <https://doc.beegfs.io/latest/advanced_topics/rdma_support.html>
  - <https://doc.beegfs.io/latest/advanced_topics/storage_tuning.html>
  - <https://doc.beegfs.io/latest/advanced_topics/licensing.html>