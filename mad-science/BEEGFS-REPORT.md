# BeeGFS as a hyperconverged HF cache — cost and performance assessment

**Status:** 2026-10-20, read-only. No package installed, nothing launched, stopped or reconfigured: node
figures come from `df` / `free` / `uname` / `mokutil` / `hf cache ls` / `dpkg -l` / `lspci` /
`ib_write_bw`, disk figures from `dd` and `O_DIRECT` read loops, and Engram figures from `/proc/diskstats`
read-sector and read-completion deltas around two short completions (128 and 512 tokens) served by the
production arm already running on `.30`. Nothing here is booted hardware evidence for BeeGFS itself, and
no BeeGFS number was measured — the pool's performance is bounded from the hardware it would run on.

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
  and the pool is then the only copy of that content — re-fetched from the internet at 76–142 MB/s
  (`mad-science/TODO.md:519`), i.e. 1.0–1.9 h for a 510 GB repo. A mirrored variant (three buddy pairs,
  3.6 TB usable) is costed in §3 and marked Enterprise-only throughout.
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
| Fabric | 112 Gb/s measured, shared with NCCL/EP and with Engram reads | `ib_write_bw`, 4 MiB × 8 QP and 8 MiB × 16 QP |
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

The ceiling comparison is blunt. A 200 Gb/s RoCE port measures 112 Gb/s (14 GB/s). One node's NVMe,
on a PCIe Gen5 ×4 link, reads 6.2–8.0 GB/s sequentially from a fully allocated file, and serves
**102,969 random 4 KiB reads/s with 32 outstanding reads** (≈ 0.42 GB/s, implied ≈ 0.31 ms per read) —
32 being the engine's own Engram reader width. The internet delivers 76–142 MB/s.

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
  reads from the pool, but the fetch is internet-bound at 76–142 MB/s. The saving is the copies.
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
   one target loss costs a sixth of the fleet's only copy, re-fetched at 76–142 MB/s.
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
- A workload appears whose load path exceeds the fabric's ~14 GB/s. None measured: everything runs at
  0.129–4 GB/s.
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

---

## How these numbers were taken

- Cache census: `hf cache ls`, `df -h /home`, `free -g` on `.30`–`.35`, 2026-10-20; receipt
  `.scratch/beegfs/hf-cache-census-20261020.txt`. Fleet figures are decimal GB from `hf cache ls`.
- Fabric: `ib_write_bw` between two idle nodes, 4 MiB × 8 QP and 8 MiB × 16 QP, 4 s.
- Disk: `dd iflag=direct bs=4M count=256` at three offsets of a fully allocated 101.38 GB Engram blob,
  and a threaded 4 KiB `O_DIRECT` random-read probe over the same file (`os.preadv`, aligned buffer).
  Link geometry from `current_link_speed` / `current_link_width` (32 GT/s, ×4).
- Engram demand: `/proc/diskstats` read counters on the node's NVMe around two `POST /v1/chat/completions`
  calls (128 and 512 generated tokens, greedy) on the live TP=2 arm; reads and sectors divided by
  completion tokens. Disk-observed values are a floor because warm rows never reach the device.
- Load rates: the `Loading weights took` / `Load weight end` lines of the arms' own boot logs.
- BeeGFS facts, read 2026-10-20 (the Community license agreement §3.1–3.4 supplies the client,
  capacity and Enterprise-feature limits):
  - <https://doc.beegfs.io/latest/system_design/system_requirements.html>
  - <https://doc.beegfs.io/latest/release_notes.html>
  - <https://doc.beegfs.io/latest/advanced_topics/rdma_support.html>
  - <https://doc.beegfs.io/latest/advanced_topics/storage_tuning.html>
  - <https://doc.beegfs.io/latest/advanced_topics/licensing.html>