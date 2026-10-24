# BeeGFS as a hyperconverged HF cache — cost and performance assessment

**Status:** 2026-10-20, read-only **for §1–§9**. No package installed, nothing launched, stopped or
reconfigured in that pass: node figures come from `df` / `free` / `uname` / `mokutil` / `hf cache ls` /
`dpkg -l` / `lspci` / `ib_write_bw`, disk figures from `dd` and `O_DIRECT` read loops, and Engram figures
from `/proc/diskstats` read-sector and read-completion deltas around two short completions (128 and 512
tokens) served by the production arm already running on `.30`. **No BeeGFS number was measured in that
pass** — the pool's performance is bounded from the hardware it would run on.

**Addendum 2026-10-22:** §9 adds measured inter-node transfer throughput (control→node and
node→node, three shapes, two rails) and the fetch-once/fan-out rule that follows from it.

**Pilot addendum 2026-10-22 (round 2):** **§10 reports the two-node pilot that the owner authorized**
(`QUESTIONS.md` `#5`), run on `.34`/`.35` exclusively. It installed the official packages, ran the
BeeGFS server stack, measured the storage targets, and established that the **client** cannot load on
either node through **either official apt route** — those routes compile on the node and Secure Boot,
with only Canonical's certificate enrolled, refuses the result. The pilot carried **no
pre-registered pass/fail** (owner ruling, `TODO.md` `#52`), so §10 reports numbers and does not invent a
threshold. **§10 also carries the reconciliation, found after the pilot: the owner's earlier working
install was a source build on `.30`–`.33` against kernel `1031`, not an apt install** — so the bound is
the *official packaging routes on a Secure Boot pair*, not BeeGFS on this fleet, and the open question is
a source build for the cluster's then-current `1032` kernel.

**Owner install addendum 2026-10-22 (round 3):** **after the pilot was torn down, the owner ran the vendor
apt route — repo key, `beegfs-noble.list`, `apt install` of all nine packages — on every WOPR node and
rebooted with no Secure Boot or MOK issue.** Verified read-only the same evening: all six nodes now run
**`7.0.0-1019-nvidia`** — the fleet moved off `1032` — and each carries the nine `20:8.4.1` packages plus
an autobuilt, **unsigned** `beegfs.ko` at
`/lib/modules/7.0.0-1019-nvidia/updates/fs/beegfs_autobuild/beegfs.ko` (`modinfo`: no signer; it replaced
the 1031 module the reconciliation found in the same source tree), with `/opt/bgfs-meta` created as the
metadata directory. On every node `beegfs-client.service` is **failed** and its journal shows `modprobe:
ERROR: could not insert 'beegfs': Key was rejected by service`, with `dmesg` recording `Loading of
unsigned module is rejected`; the server units are installed but not configured or running; Secure Boot is
still enabled with one certificate enrolled. **The reboot succeeded and the client did not load** — both
are true and neither contradicts the other, because a failed client unit does not block boot. Round 3
therefore confirms the install and narrows the blocker to Secure Boot policy alone: the apt postinst
already builds against whatever kernel is running, so **no separate source build is needed** — the
remaining choices are a MOK enrollment at the console **plus a module signed with that key** (or
`beegfs-client-dkms`, which signs it), or Secure Boot off on the pilot pair. The "build for `1032`" step in
§10 is stale; `1032` is no longer the fleet's kernel.

**Question:** what would it cost, in resources and in boot/serve performance, to install and operate
BeeGFS across `.30`–`.35` as one shared Hugging Face cache — and is it worth doing.

**Answer:** **not now — and the pilot narrowed the reason to one route rather than the design.** The
pilot (§10) ran: the vendor repo installs, the **server** stack starts, registers both storage targets and
speaks RDMA on the rail, and the **client** cannot load on `.34`/`.35` through either official apt route
because both compile locally and the nodes' Secure Boot store holds only Canonical's certificate. That is
a statement about **packaging and firmware state**, not about BeeGFS on this hardware: `.30`–`.33` carry a
**source-built** client (kernel `1031`, unsigned) from the owner's earlier install, so a source build is
the path that has actually been used here — its **load** was unverified, and the cluster then ran
`1032`, which nothing on those hosts was built for. Round 3 has since moved the fleet to
`7.0.0-1019-nvidia`, rebuilt the module through the apt postinst and reproduced the refusal on all six
nodes, so the build question is answered and the next decidable step is Secure Boot policy — a MOK
enrollment plus a signed module at the console, or Secure Boot off on the pair (§10, round-3 addendum).
The capacity benefit
remains one the existing storage policy already reaches by pruning, and no pass/fail threshold was
pre-registered for the pilot (§10 reports numbers, `TODO.md` `#52`), so none is claimed: the verdict
stands on §6's four reasons, with its install-risk item now measured instead of predicted.

**Owner decision 2026-10-23 — wanted, deferred, and hands off the packages.** All eight BeeGFS questions
are answered, transcribed in `TODO.md` §"Settled questions" as `TP4-BGFS Q11`–`Q18`: the shared HF cache
**is** wanted, the Secure Boot fix is explicitly **"not now"** and stays a deferred programme item,
activation is eventual on **all six nodes** with the metadata service on **`.30`** and clients at
**`/mnt/beegfs`** over the **RoCE** interfaces, and **the nine vendor packages are trusted and must not be
touched** (`Q16`, `Q17`). The failed `beegfs-client.service` on every node is therefore owner-installed
state, not a defect for a later session to clean up — do not remove, purge or "repair" it. Nothing in
§1–§10 changes: its measurements stand, and the transport reading (the pilot's 564 MiB/s is an IP-stack
transfer, not the rail) is the owner's and belongs in the register, not in this section.

**Activation addendum 2026-10-24 (round 4) — the fleet was rebooted, Secure Boot is off, the pool
activated (five clients at the 01:33Z census; all six by the license fix below).**
The owner's fix was neither a MOK enrollment nor a signed module on an enabled store: `mokutil --sb-state`
reads **Secure Boot disabled on all six**, and the client is **`beegfs-client-dkms` 20:8.4.1**, DKMS-built
and signed with each node's own local key (signer `spark-<node> Secure Boot Module Signature key`,
vermagic `7.0.0-1019-nvidia` matching the running kernel). This overtakes `TP4-BGFS Q12`'s "not now"
posture — the six-node firmware change happened, by the owner's own hand, and is recorded here as dated
history, not as a recommendation anyone made. Primary source: the receipt
`~/benchmarks/beegfs-activate-20261024/SUMMARY-ACTIVATION.md` on the head (state as of
2026-10-24T01:33Z), with per-node logs beside it.

Activation: management **and** metadata on `.30` — a fresh `beegfs-mgmtd --init` after backing the legacy
2026-08-21 database to `mgmtd.sqlite.legacy-20261024.bak`, plus a self-signed TLS pair because 8.4's gRPC
refuses to start without one — one directory-based storage target per node on the existing ext4
(`s:1`–`s:6`), clients configured on all six with `sysMgmtdHost` = the `.30` **rail** address (plane A,
per Q15), `conn-interfaces = enp1s0f0np0`, `tuneRemoteFSync=false` per Q18, an fstab
`_netdev,nofail` line and a `network-online` + rail-wait drop-in. **Boot-time persistence is UNVERIFIED —
no reboot was performed in the window.** Five clients registered and mounted at `/mnt/beegfs`
(`.30`–`.34`), file write/read verified.

**Blocker: the unlicensed 5-client cap.** The mgmtd log reads `Number of licensed clients (5) exhausted.
Client registration denied.`; `.35` is fully configured (storage target `s:6` live and serving, fstab and
client config in place) but cannot mount until a BeeGFS license is installed on the management host. **No
license file exists anywhere**; obtaining the free Community key is an owner action (`QUESTIONS.md` `#19`).
**Resolved the same day — see the license paragraph below; this paragraph is the 01:33Z state, not the
current one.**

**Capacity.** Pool 4.6 TiB free of 23 TiB; the two `Low`-pool targets are the controller's (`.30`: 294G
free with its root 92 % full) and a pilot node's (`.34`: 422G) — the pair to look at before any HF-cache
migration (`QUESTIONS.md` `#20`).

**Throughput probe (client `.31`; the kernel log shows `protocol: RDMA` on every server connection, i.e.
the rail, not the management plane):** single-stream write **1.2 GB/s** / read **1.3 GB/s** (4 GiB
O_DIRECT), 4-stream write **3.90** / read **4.68 GiB/s**, metadata create **8.0–14.2 ms** (mean of 100).
That is ~2× the owner's NFS-over-RoCE recollection and ~2.3× the pilot's 564.1 MiB/s single-stream,
confirming Q15's suspicion that earlier tests rode the IP stack. One early create reading of **0.026 ms is
recorded as suspect and non-reproducible** (isolated re-runs on the same mount give 8–14 ms); the 8–14 ms
row is the honest metadata price, and it is the number that matters for bulk `hf download` ingest.

Housekeeping: vendor packages untouched; `docker ps -aq` = 0 on all six before and after; the window lock
removed; no HF-cache migration started. The fleet reboot also cleared the RDMA-wedge state, but **no
quartet boot ran in this window**, so the wedge is cleared-by-reboot and unproven until the next boot; the
owner's standing instruction is that GB10's onboard ConnectX-7 needs an occasional **power-cycle** — warm
reboots only clear it temporarily (recorded in `AGENTS.md` §Node hygiene).

**Continuation — the mgmtd TLS certificate (2026-10-24, later the same day).** The owner's
`sudo beegfs license` against `.30` failed with `x509: cannot validate certificate … because it doesn't
contain any IP SANs`. Cause: the activation generated the pair with
`openssl req -x509 … -subj /CN=$(hostname)` and no `-addext`, so the certificate carried **no
subjectAltName at all** (`openssl x509 -ext subjectAltName` → *No extensions in certificate*). It was
regenerated with SANs for the `.30` rail and management addresses, the loopback address, and the
controller's own hostname plus `localhost` (365 d); the old pair is backed up under
`~/benchmarks/beegfs-activate-20261024/cert-backup-20261024/`, and the restart cost one ~3 s mgmtd
outage. The public certificate was copied to `/etc/beegfs/cert.pem` on the other five nodes — public
only, no key, no remount — so a CLI run on any node now verifies mgmtd. The architectural point that made
this safe: **TLS is only the gRPC control channel (CLI↔mgmtd, port 8010); the mounts ride BeeMsg on
8008/8005/8003 with `conn.auth` + RDMA and never touch the certificate** — which is why five live mounts
were unaffected and why no client had held a cert copy before. Maintenance obligation: the certificate
expires in **365 days**, and the five clients' trust copies must be refreshed then; mounts keep working
regardless, because expiry only breaks management commands.

**Continuation — the license and the sixth client (2026-10-24).** The owner installed the BeeGFS
Community license **`COM-1504544369`** at `/etc/beegfs/license.pem` on `.30` (Little Cedar Group,
**unlimited licensed machines**, 1.1 PiB, valid 2026-10-24 → 2031-10-24) and ran `beegfs license
--reload`. `.35` **joined on the first plain mount attempt** — no service restart, no retry — so the
fleet is complete: **six clients (`c:31`–`c:36`), `m:1` meta, `s:1`–`s:6` storage, all six mounted at
`/mnt/beegfs`**, 4.6 TiB free of 23 TiB (18 TiB used, 80 %). `.35`'s kernel log shows `protocol: RDMA` to
all six servers (meta on `.30` plus storage on all six; evidence
`~/benchmarks/beegfs-activate-20261024/logs/node-5-rdma-evidence.log`), write+read on `.35` verified, and
the mgmtd journal has no registration-denied line after the reload. The capacity caveat is unchanged:
`.30` (294G, root 92 % full) and `.34` (422G) are still `Low`.

**Completion addendum 2026-10-24 (round 5) — the HF-cache migration ran to the owner's stated end
state.** The owner reports the Hugging Face cache is **entirely on the pool**: all models
deduplicated and live on BeeGFS, per-node duplicates deleted, executed under the owner's quoted
instruction (`QUESTIONS.md` `#20`, now settled) and §11's gates. Receipts:
`~/benchmarks/beegfs-migrate-20261024/` on the head. What an operator plans with now:

- **Boots read weights over the pool**, so boot times may be longer than the node-local NVMe era.
  §5's load-rate table and §10's NFS stand-in rows are the pre-migration baselines, not the current
  path; the first boot from the pool is the cell that prices the new path.
- **The head is out of the staging business.** §9's "bodies above 60 GB are node-local" rule existed
  because the control's root disk had to hold a staged body; with the cache shared on the pool that
  reason is gone. The rule itself lives in `AGENTS.md` §Node hygiene and should be revisited after
  the first boot from the pool.
- **§1–§10 stand as dated history.** The "not now" verdict was overtaken by the owner's own acts —
  the round-4 activation, then this migration — not by any new measurement in this report.
- **Boot-time persistence is still unverified.** No post-migration reboot is recorded; the fstab
  `_netdev,nofail` risk (a slow mount leaves containers seeing an empty `/cache`) predates the
  migration and stays open — see §"Activation addendum".
- **The WOPR cluster profile is configured for the shared cache (2026-10-24, later the same day).**
  The head's `~/.config/sparkrun/clusters/WOPR.yaml` sets `distribution.model` = `enabled: false`,
  `skip_fan_out: true`, `preserve_perms: false` (backup `WOPR.yaml.bak-pre-shared-cache-20261024`),
  so sparkrun neither downloads nor rsyncs models at launch. **Tuning is deliberately excluded:** the
  Triton tuning cache is node-local (`~/.cache/sparkrun/tuning`, per-node divergent contents), so an
  explicit `distribution.tuning` block restores the default fan-out — an inheritance-first version of
  the edit silently disabled it (corrected the same day, second backup
  `WOPR.yaml.bak-pre-tuning-explicit-20261024`). Dry-run verified on sparkrun `0.4.2-alpha+g7f0acf0`:
  named-cluster launches
  (default cluster or `--cluster WOPR`) show no "Distributing model" phase; a bare `-H <node>` launch
  builds an anonymous cluster with the safe defaults and still fans out. The sharing prerequisite was
  verified read-only: `~/.cache/huggingface` is a symlink to `/mnt/beegfs/huggingface` on `.30` and
  `.34`, identical 56-repo listings.

## 11. The migration plan — one canonical body per repo on the pool, read-only per-node mounts
**(2026-10-24; census run this day, nothing moved, nothing deleted, no recipe changed at the time of
writing. The plan was **executed later the same day — see the round-5 completion addendum above**;
the owner decision that authorized it was `QUESTIONS.md` `#20`, now settled.)**

**The chosen shape (director's proposal, verified against the census below).** Not a fleet-wide
`HF_HOME=/mnt/beegfs`. The hub cache is a concurrent-write protocol — `refs/`, `.locks/` (fcntl),
relative-symlinked snapshots, `.no_exist` bookkeeping — and N nodes writing one repo directory over the
fabric is the fragile part of any shared-cache design. The shape instead: **one canonical copy of each
model repo on the pool** at `/mnt/beegfs/hf-canonical/`, and per-repo **read-only bind-mounts** into
each node's existing hub directory (`mount -o bind,ro /mnt/beegfs/hf-canonical/models--<org>--<name>`
onto `<node>:/home/red/.cache/huggingface/hub/models--<org>--<name>`). Consequences: the container path
`/cache` is byte-for-byte unchanged (sparkrun binds the host hub at `/cache/huggingface` and sets
`HF_HOME` there — §2), no client ever writes a shared repo dir, every write stays node-local or is an
explicit single-writer ingest, and rollback is one `umount` per repo per node.

### The census (2026-10-24, read-only; `du -s` per repo, per node; no file touched)

| node | hub `du -sh` | `models--*` dirs | free `/` |
|---|---:|---:|---:|
| `.30` | 2.9 TB | 62 | 104 GB |
| `.31` | 2.3 TB | 16 | 743 GB |
| `.32` | 2.1 TB | 15 | 981 GB |
| `.33` | 2.1 TB | 15 | 906 GB |
| `.34` | 2.1 TB | 42 | 232 GB |
| `.35` | 1.9 TB | 38 | 583 GB |
| **fleet** | **≈13.4 TB** | | **≈3.5 TB** |

`HF_HOME` is unset in the login environment on every node; the cache root is the huggingface_hub default
`/home/red/.cache/huggingface/hub` everywhere (read from the live shells, not from a config file).

**Dedupe is real and byte-verified.** Sample hash: `model-00001-of-00048.safetensors`
(970,533,624 B) of `deepseek-ai/DeepSeek-V4.1-Flash-1017` has sha256 `13bd121075f0b68cb7e8e802…` on
`.30`, `.31` and `.34` **across two different cache layouts** — `.30` holds the stock symlinked
`blobs/` farm, `.31`/`.34` hold real-file trees with no `blobs/` (the 2026-10-22 rsync copies, whose
57 snapshot entries were already size-verified identical, `recipes/ds4/README.md:281-293`). Within the
25 largest repos per node (8.3 TB of the 13.4 TB), the per-node instances hold **3,139 GB of distinct
content across 45 repos — ≈5.2 TB of those instances is duplicate** (arithmetic over the census
tables; the arithmetic is VERIFIED, the small-repo tail beneath it is not separately hashed).
Canonicalizing **the live set alone** reclaims ≈5.5–5.9 TB of duplicate bytes while adding ≈2.5–2.6 TB
of canonical copy — a net fleet gain of ≈+3 TB for one-copy-per-model (arithmetic over the presence
matrix below; the per-repo `(copies−1)×size` column is LIKELY where a repo's per-node copies differ in
completeness, e.g. `bot-lab-21/…-EXL3-3.5bpw-Pollard` 9 GB on `.32` vs 20 GB on `.33`).

### The live set (candidate canonical list)

54 repo ids are named by the 67 tracked recipes (`model:` / `speculative_draft_model:` / `command:`
model args; extracted from the worktree at `a5c5843` with a stdlib scan, method recorded under "How
these numbers were taken" below). Presence matrix, per node (VERIFIED, `ls -d` per hub):

| id | copies | nodes |
|---|---:|---|
| `deepseek-ai/DeepSeek-V4.1-Flash-1017` | 5 | .30 .31 .32 .33 .34 |
| `local-inference-lab/Qwen3.8-Flash-Next-NVFP4` | 6 | all six |
| `littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram` | 3 | .30 .34 .35 |
| `bertholomus/GLM-5.3-EXL3-3.0bpw` | 4 | .30 .31 .32 .33 |
| `littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft` | 4 | .30 .31 .32 .33 |
| `LibertAIDAI/DeepSeek-V4.1-Flash-1017-EXL3-2.9bpw` | 4 | .30 .31 .34 .35 |
| `Mia-AiLab/GLM-5.3-Flash-EXL3-4bpw-TensorFold` | 4 | .30 .31 .32 .33 |
| `poolside/Laguna-M.1-NVFP4` | 3 | .30 .34 .35 |
| `orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4` | 3 | .30 .34 .35 |
| `inclusionAI/Ling-3.0-flash-int4` | 2 | .30 .35 |
| `autotrust/JEV-27B` | 2 | .30 .35 |
| `Intel/Qwen3-Coder-Next-int4-AutoRound` | 2 | .30 .35 |
| `InternScience/Sage-A1.5-FP8` | 2 | .32 .34 |
| `Qwen/Qwen-Image-2.1-Turbo` | 3 | .30 .34 .35 |
| `orcarouter/Qwen3.8-27B-Uncensored-NVFP4` | 4 | .30 .32 .34 .35 |
| `sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4` | 4 | .30 .32 .34 .35 |
| `Myric/Kolibri-1-APEX-GGUF` | 2 | .30 .35 |
| `ornith-ai/Ornith-1.5-35B-A3B-NVFP4` | 3 | .30 .34 .35 |
| `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4` | 3 | .30 .34 .35 |
| `autotrust/JEV-9B` | 3 | .30 .34 .35 |
| `ornith-ai/Ornith-1.5-9B-NVFP4` | 3 | .30 .34 .35 |
| `orcarouter/Nex-N2.5-mini-Uncensored-NVFP4` | 3 | .30 .34 .35 |
| `Qwen/Qwen3-VL-Embedding-2B` | 3 | .30 .34 .35 |
| `Qwen/Qwen3-VL-Reranker-2B` | 3 | .30 .34 .35 |
| `Qwen/Qwen3-VL-Reranker-8B` | 2 | .30 .34 |
| `Lightricks/LTX-2.5` | 3 | .30 .34 .35 |
| `TensorFold/Qwen3.8-27B-MLX-4bit` | 2 | .30 .35 |
| `poolside/Laguna-XS-2.1-NVFP4` | 2 | .30 .34 |
| `Cloudflare/clef-flash` | 2 | .30 .34 |
| `gonuit/Qwen3-VL-Embedding-8B-AWQ-4bit` | 2 | .30 .34 |
| `vllm-sr/Decision-2.0-Nox-4B` | 2 | .30 .34 |
| `vllm-sr/Decision-2.0-Kai-0.6B` | 2 | .30 .34 |
| `jialinyyzz/humanizer-GGUF` | 3 | .30 .33 .34 |
| `IFM/K2-Horizon-0.9B` | 5 | .30 .31 .33 .34 .35 |
| `IFM/K2-Horizon-7B-FP8` | 3 | .30 .34 .35 |
| `RadixArk/Qwen3.8-27B-NVFP4` | 4 | .30 .31 .34 .35 |
| `RadixArk/Qwen3.8-Flash-Next-NVFP4` | 4 | .30 .31 .32 .33 |
| `JetBrains/Mellum2.1-12B-A2.5B-Thinking-GGUF` | 5 | .30 .31 .32 .33 .34 |
| `vllm-sr/d3-edge` | 4 | .30 .31 .34 .35 |
| `orcarouter/OrcaCyber-Nano-1.0` | 2 | .31 .35 |
| `ornith-ai/Ornith-1.5-122B-NVFP4` | 2 | .33 .35 |
| `XHToken/Spark-X2.6-4B-FP8` | 2 | .33 .35 |
| `XHToken/Spark-X2.6-4B` | 1 | .30 |
| `XHToken/Spark-X2.6-4B-INT8` | 1 | .35 |
| `unsloth/Ornith-1.5-122B-GGUF` | 1 | .34 |
| `vllm-sr/Decision-2.0-Sol-2B` | 1 | .34 |
| `vllm-sr/Decision-2.0-Sol-2B-GGUF` | 1 | .34 |
| `fishaudio/drama-3` | 1 | .34 |
| `pyannote/speaker-diarization-community-1` | 2 | .30 .35 |
| `hexgrad/Kokoro-82M` | 1 | .30 |
| `jaredpalmer/kev-0.8b` | 2 | .30 .34 |
| `convaiinnovations/laya` | 2 | .30 .32 |

**Three live-set ids exist nowhere in any node cache**: `InternScience/Sage-A1.5-Q4_K_M-GGUF`,
`MiniMaxAI/MiniMax-H3`, and (in its repo form) `hexgrad/Kokoro-82M`'s siblings — Kokoro is served from
the image's baked model set, and the decision-lane CPU arms pass their model through `command:`, so
the canonical-set rule for them is "fetch on first need", not "copy from a node".

### Fit verdict against the ACTUAL pool budget

**The pool is not 23 TiB of new space; it is the six nodes' root disks seen through one namespace, and
the 18 T "used" is largely the per-node caches this plan wants to consolidate** — `df /mnt/beegfs`
(23 T / 18 T used / 4.6 T avail) is the sum of the six underlying ext4 root filesystems' `statfs`
(2.9 + 2.3 + 2.1 + 2.1 + 2.1 + 1.9 TB of hub alone, plus each node's runtime cache, 202–681 GB by
`du` on `.30`/`.34`, plus everything else on those disks). **The fit verdict is therefore:
unique-set bytes vs 4.6 TiB free, growing with each evicted local copy** — migration is physical
dedupe: ingest the unique body once into the pool, delete the duplicate local copies, and the backing
filesystems free up by ≈(N−1)× the duplicate bytes per repo, so pool free rises from today's ≈3.5 TB
of per-node room toward ≈9 TB as the live-set cutover completes (unique set ≈2.5–2.6 TB; duplicates
reclaimed ≈5.5–5.9 TB). Today's true free is ≈**3.5 TB summed** (104 + 743 + 981 + 906 + 232 + 583 GB),
and the house floor (`df` free ≥ 1.0 TB per node, `STORAGE-POLICY.md:380-381`) is already violated on
`.30` (104 GB) and `.34` (232 GB) before anything moves. Consequences:

- **The live set fits only if the migration is strictly repo-by-repo and self-funding**: ingest the
  canonical copy of one repo, cut its binds over, then delete the node-local duplicates **of that
  repo** before ingesting the next. Each big repo is net-positive the moment its duplicates go
  (the 1017 body: +476 GB canonical, −1.9 TB of duplicates).
- **The first ingest is the binding constraint, not the total**: the largest body (476 GB) must land
  on targets with room — `.31`/`.32`/`.33`/`.35` (0.7–1.0 TB free each); `.30` and `.34` cannot
  receive it. BeeGFS 8.4 exposes exactly the lever needed and it is **not configured** (read-only
  finding): `beegfs pool create` / `beegfs pool assign` put a chosen target set into a storage pool,
  and a directory's storage-pool assignment directs new files into it — so an `hf-canonical` pool
  containing only `.31`/`.32`/`.33`/`.35`'s targets keeps the controller's 92 %-full root and the
  88 %-full `.34` out of the write path. Recorded as the mechanism; configuring it is part of
  execution, not of this census.
- **The `.30` metadata target shares the controller's root disk.** A pool full of HF bodies on `.30`
  would squeeze the metadata service that every boot of every arm depends on — one more reason the
  `hf-canonical` pool must exclude `s:1`.

### Ingest procedure

Canonical root `/mnt/beegfs/hf-canonical/`, owner `red:red`, one subdirectory per repo in hub naming
(`models--<org>--<name>`). Ingest is `cp -a` from a node that holds the **complete** body, one repo at
a time, **single writer** — never two ingests concurrently, never an `hf download` against the
canonical tree. `cp -a` preserves the symlink farm; relative `blobs/<sha>` links resolve inside the
copied directory, so the canonical copy is mount-ready without re-linking. The one repo whose copies
are real-file trees with no `blobs/` (`DeepSeek-V4.1-Flash-1017` on `.31`/`.34`) should be ingested
**from `.30`'s stock-layout copy**, so every canonical repo has the same shape.

Throughput reference: the activation probe measured **1.2 GB/s single-stream write** over the mount
(§"Activation addendum"), i.e. a 476 GB body is ≈7 min of streaming plus per-file overhead at shard
granularity. The measured metadata **create cost of 8–14 ms** is irrelevant at safetensors-shard
granularity (48 files for the flagship, ~60 for most repos) and relevant only if anyone ever
bulk-downloads many small files into the pool — do not. Verify before any bind: file count + byte
sizes against the source, plus one sha256 spot-check (the method that caught `.33`'s
size-matched-wrong-bytes Engram set, §10's "Pre-launch gate", is the precedent: **size alone passes;
a hash is the only cheap discriminator**).

### Mount procedure and the two hard invariants

Every mount is read-only from day one: `mount -o bind,ro …`, and the fstab bind entries carry `ro`,
so a client physically cannot write into a canonical repo even by accident.

- **Invariant (a) — a canonical repo dir is immutable.** Nobody writes it; `hf download` must never
  target `/mnt/beegfs/hf-canonical` (it would either fail on the read-only bind or, worse, run against
  the pool directly and fork the one true copy). The only writer is the single-stream ingest.
- **Invariant (b) — no recipe cut-over until boot-time persistence is proven.** The fstab mount is
  `_netdev,nofail`: if the pool is slow or absent at boot, the mount silently does not appear and the
  bind target is then an ordinary **empty** directory — a container sees an empty
  `/cache/huggingface/hub/models--X` rather than an error. The concrete checks this plan requires
  before any recipe relies on a canonical body: (i) a reboot of one client node with the fstab bind
  entries in place, after which `mountpoint -q` and `test -f <repo>/snapshots/<pin>/config.json` are
  asserted per mounted repo; and (ii) a **launch-path assertion** — a pre-serve check (mod or
  pre_exec hook, one `test -d`) that the recipe's prepared snapshot path exists before the engine
  execs, so the failure mode is a loud launch refusal, not a silent wrong-state. Both are proposed
  here and neither exists yet; (ii) is a recipe/mod change and belongs to its own reviewed change,
  not to this plan.

### Rollout order and rollback

1. Canonical ingest, biggest dedupe winners first (`DeepSeek-V4.1-Flash-1017`, `…-with-engram`,
   `GLM-5.3-EXL3-3.0bpw`, `Ornith-1.5-397B`, the EXL3/GLM TP=4 set), hash-verified per body.
2. Bind-mount **one node** (`.31` — the most room and the richest cache), verify with a boot of the
   owning recipe, including invariant (b)'s reboot check.
3. Then the remaining nodes, one at a time, deleting the node-local duplicate only after that node's
   bind is verified.
4. Rollback: `umount` the bind (restores the underlying node-local directory — but once a node's local
   copy has been deleted, rollback for that node means re-downloading at the measured ≈6 MB/s internet
   rate, ≈24 h for the 1017 body, or copying back from another node while one still holds it). **Do
   not delete the last node-local copy of a repo until at least one full boot has served from the
   canonical copy**; the fleet stays one `umount` from node-local state until then.

### Explicitly not decided by this document

- **When** to migrate (owner's `QUESTIONS.md` `#20`) — this is the how, not the when.
- Whether **retired/attic-arm bodies** ever get canonical copies — default **no**: the canonical set
  is the live set above; anything else (e.g. `deepseek-ai/DeepSeek-V4.1-Flash` the builder input, the
  drowzeys/Muse-Glimmer/Kolibri-state bodies) stays subject to the existing pruning/hygiene decisions,
  not to this plan.

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
3. **Install risk on this exact platform — measured 2026-10-22, and it is a route problem, not a platform
   one.** Secure Boot is enabled on `.34`/`.35` with **one** certificate enrolled (Canonical Ltd. Master
   CA), and both official apt routes compile on the node: `beegfs-client` leaves `beegfs.ko` unsigned
   (`modinfo` shows no signer, refused with `Key was rejected by service`) and `beegfs-client-dkms` signs
   with the local `spark-324e` MOK, which is not enrolled (refused the same way). **No official index
   ships a prebuilt module** for any kernel, so neither route can load without a `mokutil --import` plus a
   MokManager confirmation **at a physical console**. That is a real cost, but it is **not the only
   route**: `.30`–`.33` carry a **source-built** `beegfs.ko` from the owner's earlier install (§10), so
   the build itself is known to work on this fleet; whether a source build for the then-current
   `6.17.0-1032-nvidia` loads on a Secure Boot node was **unverified** — round 3 has since rebuilt it for
   `7.0.0-1019-nvidia` and measured the refusal on all six nodes. The standing risk is the same either
   way: that kernel is not a combination BeeGFS tests, and every DGX OS update re-opens the build. The management service then sits in front of every
   boot. Full evidence in §10.
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

**Outcome, 2026-10-22:** **the pilot ran, and it overturned nothing — because two of the three cells
cannot be measured on these nodes.** (2) is unreachable: it needs a BeeGFS **client** mount, and the
client module cannot load on `.34`/`.35` through either official apt route under this pair's Secure
Boot/MOK state (§10). (1) and (3) therefore fall back to the NFS-over-rail stand-in that the same pair can
mount — a single-stream read of **564.1 MiB/s** against **6,358.3 MiB/s** local NVMe, **3,055.7 MiB/s** at
eight streams, metadata create **9.28 ms** on a `sync` export against **0.67 ms** `async` and
**0.0097 ms** local (§10). Those NFS rows stay labelled as the stand-in; they are not BeeGFS numbers. The
pilot pre-registered no pass/fail threshold, so these are reported as measurements, not as a scored test;
the verdict stays "not now" with §6's install-risk item now measured rather than predicted.

**Superseding route, 2026-10-22 (same day, after the pilot):** the client cell is not closed — it was
being attempted on the wrong route. `.30`–`.33` carry a **source-built** `beegfs.ko` (kernel `1031`,
unsigned, built 2026-08-21) from the owner's earlier install, so board the next attempt through a source
build for the then-current `1032` kernel and one `modprobe` (§10 "The reconciliation"), which was cheaper
than either apt route plus a console enrollment. **Superseded 2026-10-22 (round 3):** the fleet moved to
`7.0.0-1019-nvidia`, the apt postinst rebuilt the module for it and the refusal was reproduced on all six
nodes — the build is answered; only the load remains.

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

- `ip route get <node-ip>` from the sender resolved to **`dev enP7s7`**, the management port, not a
  CX7 rail port;
- the copy's own ssh socket read `.31:44468 -> .34:22` in `ss -tnp` — both ends
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
CX7 plane-A subnet measured **646–751 MB/s aggregate** (≈323–375 MB/s per stream). That is less
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
node-to-node **by rail address** (CX7 plane-A / plane-B subnets), never by management
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
- Every `<peer-*>` in step 2 must be a **rail** address (plane-A / plane-B subnet), never a
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

The control's root filesystem held a 141 GB free margin at the time of writing, and a 210.72 GB
TensorFold body plus its Engram tables does not fit in it. The staging rule is not this report's to set:
`AGENTS.md` §Node hygiene says **bodies above 60 GB are node-local, never staged on the head**, and that
is the shipped rule. The ~130 GB figure this section originally derived is a 2026-10-22 observation of
that day's free margin, **not a threshold**. The cross-node body copy of the same day was shaped by the
shipped rule: a body far above 60 GB, so it was fetched once on a node and fanned out node-to-node —
and, per §"The copy that actually ran", over the management NIC because the copy was addressed by
management hostnames.

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
  to `dev enP7s7` and the socket was `.31:44468 -> .34:22` — the 2.5 GbE management
  NIC, at 247–250 MB/s per ssh stream. The CX7 rows above measure what the rails do with a test
  blob between rail addresses; no large copy has yet used them, and the 112 Gb/s RDMA figure has
  still never been exercised by a file transfer at all.

## 10. The two-node pilot, `.34`/`.35` (run 2026-10-22)

**Status:** installed, run, measured, torn down; the pilot ran **13:26–13:46:41 ET**. Both nodes were
**exclusive** to it for its duration (no lane serve, no transfer, no benchmark cell); `.30`–`.33` were
not touched and kept serving throughout, and nothing was measured on them. Receipts:
`~/benchmarks/beegfs-pilot-20261022/` (`SUMMARY-BEEGFS.md` for the BeeGFS round, `SUMMARY.md` for the
NFS/control round, `logs/` for the install, reboot, Secure Boot and teardown captures, `raw/` for the
benchmark and `/proc` counters). **No pass/fail threshold was pre-registered for this pilot** (owner
ruling, `TODO.md` `#52`), so nothing below is scored — it is measurements plus the one gate that
blocked the third.

### The gate: Secure Boot and the MOK store

| item | `.34` (`spark-324e`) | `.35` (`spark-383f`) |
|---|---|---|
| kernel | `6.17.0-1032-nvidia` | idem |
| `mokutil --sb-state` | **SecureBoot enabled** | **SecureBoot enabled** |
| `/sys/kernel/security/lockdown` | `none [integrity] confidentiality` | idem (`logs/sb-state-round2.txt`) |
| `mokutil --list-enrolled` | **1 certificate**: Canonical Ltd. Master CA (SHA1 `76:a0:92:06:58:00:bf:37:69:01:c3:72:cd:55:a9:0e:1f:de:d2:e0`) | idem |
| `mokutil --list-new` | empty — nothing pending | idem |
| loader X.509 certs (`dmesg`) | 8 × "Canonical Ltd. Secure Boot Signing" | idem |
| `nvidia.ko` signer | Canonical Ltd. Kernel Module Signing → loads | idem |

The machine trusts **Canonical and nothing else**. A module built on the node is therefore either
unsigned — refused, `modprobe` answering **`Key was rejected by service`** with dmesg
`Loading of unsigned module is rejected` — or signed with the local shim MOK key, which is **not
enrolled** — refused with the same message plus dmesg `Loading of module with unavailable key is
rejected`. Nothing in the store explains a previously accepted third-party module, and nothing is
pending now.

### The vendor-APT-repo route the owner named

| step | result |
|---|---|
| repo key `https://www.beegfs.io/release/beegfs_8.4/gpg/GPG-KEY-beegfs` | RSA-4096, fingerprint **`0683 AF2B 9AC5 BC7D 59B2 D623 40CE 4E24 3CD5 0804`**, uid `BeeGFS Maintainers <support@thinkparq.com>`, expires 2030-03-10 |
| `dists/noble/Release.gpg` | **Good signature** against the key |
| source line | `deb [signed-by=/usr/share/keyrings/beegfs.gpg] https://www.beegfs.io/release/beegfs_8.4/ noble non-free` — the URI is the repo root, **not** `…/dists/noble` |
| index | `Components: non-free`, `Architectures: amd64 arm64`; `non-free/binary-arm64/Packages` lists **24 packages**, none kernel-version-specific |
| module delivery | **none prebuilt, ever**: `beegfs-client` builds `/opt/beegfs/src/client/client_module_8/source/beegfs.ko` in its postinst and leaves it **unsigned**; `beegfs-client-dkms` builds and signs with `/var/lib/shim-signed/mok/MOK.priv`. No `kmod-beegfs` / `beegfs-client-<kver>` package exists on **noble, jammy or bookworm**; the Ubuntu archive itself ships nothing (`apt-cache policy beegfs-client` had no candidate before the vendor repo was added) |

So **neither official apt route is the discriminator**: `apt-get install` succeeds and version `20:8.4.1`
installs from the vendor repo, the postinst builds a 76 MB `beegfs.ko`, and `modprobe beegfs` then fails
as above; `beegfs-client.service` (installed and enabled by the package) ends `status=1/FAILURE` on the
same error. The DKMS route reaches the identical end with a **signed-but-unenrolled** module. The next
subsection is the route that has actually worked on this fleet — a plain source build, which is what the
owner's install turns out to have been.

### The reconciliation: the owner's install was a **source build on `.30`–`.33`**, not an apt install

**The owner reports a prior working install on these nodes, from official packages, which survived a
reboot.** Round 1 and the pilot both read that as an apt client install and could not reproduce it on
`.34`/`.35`. **Read-only inspection of `.30`–`.33` on 2026-10-22 found it — and it was never on the pilot
pair.** Nothing was stopped, restarted or deleted to look; the reads are `ls`, `dpkg -l`, `modinfo`,
`systemctl is-enabled`, `sha256sum` and `mokutil`.

| what the production four carry | evidence |
|---|---|
| a **source-built client tree** at `/opt/beegfs/src/client/client_module_8/source/` | `beegfs.ko` **76,105,072 B**, built **2026-08-21 21:27**, `vermagic 6.17.0-1031-nvidia`; `.beegfs.ko.cmd` names the `1031` headers, which are still under `/usr/src` on `.30` |
| that module is **unsigned and not loaded** | `modinfo` returns no signer; `lsmod` shows no `beegfs`; `.30`'s build hashes `230ff15216a023f3bc45bb9c8ef3dc8dc3ecd214c725f716e4dc61dfd339236c` |
| **no client/daemon package** — a source install, not apt | `dpkg -l` on `.30` lists exactly two BeeGFS packages, the userspace libraries `libbeegfs-ib` and `libbeegfs-license` (`20:8.4.1`); no `beegfs-client`, `-mgmtd`, `-meta` or `-storage` row exists in any retained archive |
| a management daemon **ran** on `.30` | `/var/lib/beegfs/mgmtd.sqlite` (**151,552 B**, 2026-08-21 21:31) and an enable symlink for `beegfs-mgmtd` (2026-08-07 23:21) |
| `.34`/`.35` never had any of it | `/opt/beegfs`, `/etc/beegfs` and `/mnt/beegfs` are **absent** on `.34`; its `/lib/modules/6.17.0-1032-nvidia/updates/fs` exists but is **empty**, so nothing was ever `make install`ed there either; every retained Secure Boot record on the pair back to 2026-10-18 shows Secure Boot enabled with only Canonical's CA |

**What that changes, in four steps:**

1. **The source build path is proven to build on this fleet** — out-of-tree module, `1031` headers,
   `-j8`-style build, no MOK ceremony recorded in any surviving artefact. It is the route the owner
   actually used, and it is not blocked by packaging at all.
2. **It does not prove the load under today's firmware.** The surviving artifact is **unsigned**, and
   `.30` itself reports **Secure Boot enabled**; on that state an unsigned module is refused with
   `Key was rejected by service`. So the earlier install's *load* is **unverified** — it cannot be
   reconstructed from the artefacts, and the report records the owner's account beside this measurement
   rather than correcting it.
3. **Nothing from that install could load as-is:** the cluster then ran
   `6.17.0-1032-nvidia` while the module is vermagic `1031`, and the `1031` module tree is no longer
   under `/lib/modules` on `.30` (only its headers remain), so a rebuild is required either way.
4. **The open, testable question is therefore a source build for `1032`.** One build and one
   `modprobe` answers whether the route the owner used still works under the firmware state this fleet
   runs now — and it supersedes the NFS-over-rail stand-in as the path to a real client mount, which is
   what §8 cell (2) needs. That is a cheaper next step than either apt route plus a console enrollment.
   **Superseded 2026-10-22 (round 3):** the fleet moved to `7.0.0-1019-nvidia`, the round-3 apt install
   rebuilt and replaced this module in place, and the refusal was reproduced on all six nodes — so the
   build question is answered and only the load remains.

### Unverified legacy state on the production four

**Superseded in part 2026-10-22 (round 3):** the owner installed the apt package set on all six nodes and
rebooted, so these leftovers now sit beside a fresh `20:8.4.1` install, and the surviving 1031 module at
`/opt/beegfs/src/client/client_module_8/source/beegfs.ko` was overwritten in place by the round-3
autobuild for `7.0.0-1019-nvidia` (76,732,736 B, 19:56–19:57). The paths below were not cleaned up or
restarted; the 1031 artefact is a historical read.

These are **documented leftovers, not a working install**: until round 3, nobody had deleted, restarted or
rebuilt them, and they sit on fenced production hosts, so their disposition is the owner's call. Recorded
because a future "BeeGFS was never on this fleet" claim would be false, and because two of them are
security-relevant.

| leftover | where | state |
|---|---|---|
| stale module source tree (`beegfs.ko` + `.beegfs.ko.cmd` + `beegfs.mod`, …) | `/opt/beegfs/src/client/client_module_8/source/` on all four | built 2026-08-21 for kernel `1031`, **unsigned**, **not loaded**; nothing maintains it |
| `conn.auth` — a 32-hex cluster secret, **the only file in `/etc/beegfs`** on `.30` | `/etc/beegfs/conn.auth` (175 B, 2026-08-07 23:37) | orphaned: there is no client config, no client unit and no loaded module to use it |
| an empty mount point | `/mnt/beegfs` (2026-08-08 00:00) | empty, not mounted, not in `/etc/fstab` |
| a management database | `/var/lib/beegfs/mgmtd.sqlite` on `.30` (151,552 B, 2026-08-21 21:31) | no `beegfs-mgmtd` binary or unit to read it |
| a **dangling unit enable symlink** | `/etc/systemd/system/multi-user.target.wants/beegfs-mgmtd.service` → `/usr/lib/systemd/system/beegfs-mgmtd.service` (2026-08-07 23:21) | `systemctl is-enabled beegfs-mgmtd` answers **`not-found`** — the unit file is gone, so the symlink points at nothing and nothing starts |
| two userspace libraries | `libbeegfs-ib`, `libbeegfs-license` (`20:8.4.1`) in dpkg on `.30` | installed, unused by anything running |

The server half (§"The part that does work") needs no module at all, and is very likely the install the
owner remembers; the client tree above was what survived of the rest until round 3 replaced its module.

### The part that does work: the server stack, and the drop-in it needs to survive a reboot

`beegfs-mgmtd`, `beegfs-meta` and `beegfs-storage` are plain userspace services. On 8.4:
`beegfs-mgmtd --init` creates a SQLite database at `/var/lib/beegfs/mgmtd.sqlite`; `conn.auth` (32 hex
chars) is required; **8.4 refuses to start without a TLS cert**, so a 30-day self-signed
`cert.pem`/`key.pem` was generated; targets come from `/opt/beegfs/sbin/beegfs-setup-meta|storage`
(there is no `beegfs-setup-mgmtd` in 8.4). With `connInterfacesFile = enp1s0f0np0`, `beegfs-storage` logs
`+ enp1s0f0np0[ip addr: the `.35` rail address; type: RDMA]` — BeeMsg rides the **rail**, which matters because
this kernel has `rpcrdma` but no `svcrdma`, so NFS-over-RDMA could not be the client (`raw/svcrdma-absence.txt`).

**First simultaneous reboot:** `beegfs-mgmtd` came back active, but `beegfs-meta` and both
`beegfs-storage` units **failed** with `Error: Couldn't find any usable NIC` — they start before
`enp1s0f0np0` holds its `192.168.0.x` address, so `connInterfacesFile` matches nothing. One drop-in per
node fixed it, and a second simultaneous reboot brought every unit up active:

```ini
# /etc/systemd/system/beegfs-{storage,meta}.service.d/10-rail-wait.conf
[Unit]
After=network-online.target
Wants=network-online.target
[Service]
ExecStartPre=/bin/sh -c 'for i in $(seq 1 60); do ip -4 -o addr show dev enp1s0f0np0 | grep -q "192.168.0." && exit 0; sleep 1; done; exit 1'
```

**`node list` is not a liveness test.** The mgmtd database still lists the targets after a failed start,
so `beegfs --mgmtd-addr … node list` reported `m:34 / s:34 / s:35` **while both storage targets were
down**; only `beegfs health capacity` plus `systemctl status` distinguished the two states. Recorded
because that output is the first thing an operator reads.

**One adoption-relevant side effect:** every command prints `WARNING: This system does not have a valid
license installed… Licensed features will be unavailable`, and mgmtd logs the same on start. The
community build runs without a certificate, but the 8.4 license gate exists and is §6's license
question, not a pilot defect.

### Measurements

**No client-side BeeGFS number exists** — a mount needs the module, and the module cannot load. What
BeeGFS can report without a client is its **storage-target** benchmark, whose own help states it runs
"directly to their target(s) without any data transfer to or from client nodes… independent of network
performance". It is a disk number for the storage nodes, and is reported as one:

| run (O_DIRECT, 1 MiB requests) | per target (`.34` / `.35`) | aggregate | note |
|---|---|---|---|
| write, 1 task × 4 GiB | **307.16 / 311.51 MiB/s** | 618.67 MiB/s | storage-local disk, serialized per task |
| read, 1 task × 4 GiB | **327.84 / 306.66 MiB/s** | 634.49 MiB/s | same files, `O_DIRECT` |
| write, 4 tasks × 1 GiB | **1.49 / 1.57 GiB/s** | **3.06 GiB/s** | 5.0× the 1-task write |

These line up with the local controls from the read-only round (a 1 MiB `O_DIRECT` write at ~259–309
MiB/s per stream on this 93 %-full QLC device) and show the BeeGFS storage service allocates chunk files
and drives device I/O correctly on both nodes — they say nothing about the rail.

The only **fabric-level** pool numbers remain the NFS-over-rail control, which is the honest stand-in for
"a shared mount on the same rail": it is the shape BeeGFS would fill, measured on the same pair and the
same `enp1s0f0np0`.

| NFS-over-rail control (same pair, same rail) | measured | local NVMe control |
|---|---|---|
| read, single stream | **564.1 MiB/s** | **6,358.3 MiB/s** |
| read, 4 streams / 8 streams | 2,051.8 / **3,055.7 MiB/s** | — |
| metadata per op, `sync` export | **9.28** / 1.79 / 9.95 ms (create / stat / delete) | **0.0097** / 0.0011 / 0.0055 ms |
| metadata per op, `async` export | **0.67** / 0.50 / 0.98 ms | idem |

Read that as the price of putting one shared namespace on the rail at all: **~11×** less single-stream
read throughput than local NVMe, and metadata `sync` costing ~1,000× the local create. A pool cannot beat
its own transport, so this bounds what a BeeGFS pool could deliver for loads and `hf cache ls`-shaped
metadata traversal on this fleet.

### End state

**Superseded 2026-10-22 (round 3):** the owner reinstalled the apt package set on all six nodes after this
teardown — the clean state below describes the pilot's end, not the fleet's current state (round-3
addendum at the top).

The client cannot mount, so per the brief the nodes were left **clean** rather than carrying a service
nobody can use: `beegfs-{client,mgmtd,meta,storage,tools,utils}` + `libbeegfs-ib` + `libbeegfs-license`
purged (and only those — `logs/apt-history.txt`; `build-essential` was already present), `/etc/beegfs`,
`/srv/beegfs`, `/var/lib/beegfs`, `/opt/beegfs`, both unit drop-ins, the `beegfs.list` source and the
keyring deleted, `apt-get update` re-run. `/etc/fstab` was **not** touched (the earlier round's entry was
already removed and verified — `logs/final-state.txt` shows the post-pilot fstab identical to its
pre-pilot backup). Final state on both nodes: `dpkg -l | grep beegfs` = 0, no DKMS profile,
`systemctl --failed` = 0 units, **`docker ps -aq` = 0**, no `beegfs` mount, `/` back to **279 GB free
(93 % used) on `.34`** and **615 GB free (83 % used) on `.35`**.

### What finishing it would take, cheapest first

1. **A source build for `6.17.0-1032-nvidia`, then one `modprobe`** — no console, no key ceremony, and it
   is the route the owner's install already used (§"The reconciliation"). Build the 8.4 client tree
   against the current kernel *on the pair*, `insmod`/`modprobe` the result, and read the answer off
   `lsmod` plus `dmesg`: **loads** ⇒ mount and take §8 cells (1) and (2) on a real client; **refused**
   (`Key was rejected by service`) ⇒ the module needs signing, which is step 2. This is the test that
   turns the pilot's NFS stand-in into a measured pool.
   **Superseded 2026-10-22 (round 3):** the fleet now runs `7.0.0-1019-nvidia`, not `1032`, and the apt
   postinst already autobuilt an unsigned `beegfs.ko` for it on every node — so the build half of this
   step is answered and needs no separate source build. Only the load remains, and its refusal is
   already measured on all six nodes (round-3 addendum at the top).
2. **Only if step 1 is refused:** at the **physical console** of each node that should mount,
   `sudo mokutil --import /var/lib/shim-signed/mok/MOK.der` (or a fresh key the module is signed with),
   reboot, confirm at the MokManager screen. `mokutil --list-enrolled` must then show **2** certificates.
   Then install `beegfs-client beegfs-client-dkms`, set `sysMgmtdHost`, start `beegfs-client`; the
   round's harness (`~/benchmarks/beegfs-pilot-20261022/bench.py`) runs unchanged against `/mnt/beegfs`.
3. Alternatively, Secure Boot may be turned off in firmware on the pilot pair, and the same package set
   works with no console key work at all — but that is a fleet-wide security posture change, i.e. an
   owner decision, not a pilot step.

Before any of that, the **legacy state on the production four** (§"Unverified legacy state") needs an
owner decision of its own: a stale 1031 module tree, an orphaned `conn.auth`, an empty `/mnt/beegfs`, a
management database and a dangling `beegfs-mgmtd` symlink are sitting on fenced hosts and nothing has
been removed or restarted.

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
- BeeGFS pilot (§10), 2026-10-22, `.34`/`.35` exclusive: the official vendor APT repo (key fingerprint
  `0683 AF2B 9AC5 BC7D 59B2 D623 40CE 4E24 3CD5 0804`, `Release.gpg` verified) installed through
  `apt-get`; the Secure Boot state was read with `mokutil --sb-state`, `--list-enrolled`, `--list-new`,
  `/sys/kernel/security/lockdown`, the loader certificates in `dmesg`, and `modinfo beegfs` for the
  signer; the load attempts are `modprobe beegfs` plus the packaged `beegfs-client.service` status, both
  captured with their `dmesg` lines. Storage-target throughput is BeeGFS 8.4's own
  `beegfs benchmark --mgmtd-addr …`, `O_DIRECT`, 1 MiB requests, 1 task × 4 GiB (write and read) then
  4 tasks × 1 GiB per target — its help states no client nodes are involved. Reboot behaviour was taken
  from two simultaneous reboots, before and after the `10-rail-wait.conf` drop-in. Logs:
  `~/benchmarks/beegfs-pilot-20261022/logs/{sb-state-round2,beegfs-install-attempt,apt-history,beegfs-benchmark-write,beegfs-reboot-survival,final-state,teardown-round2}.txt`.
- NFS-over-rail control (§10, §8): an export on `.34` mounted on `.35` over `enp1s0f0np0`, read with
  `dd`/`O_DIRECT` at 1, 4 and 8 concurrent streams, and per-op metadata timings on a `sync` export, an
  `async` export and the local filesystem; harness and summary `~/benchmarks/beegfs-pilot-20261022/`
  (`bench.py`, `summarize.py`, `SUMMARY.md`). Same pair, same rail, so it is the shape a BeeGFS mount
  would fill — it is **not** a BeeGFS number.
- The owner's prior working install was located, not re-measured: read-only inspection of `.30`–`.33` on
  2026-10-22 (`ls`, `dpkg -l`, `modinfo -F signer`, `modinfo -F vermagic`, `lsmod`, `systemctl is-enabled`,
  `sha256sum`, `mokutil --list-enrolled`) — nothing stopped, restarted or deleted on those fenced hosts.
  The `1031`-built module, its `.beegfs.ko.cmd`, the `/etc/beegfs` and `/var/lib/beegfs` contents and the
  dangling unit symlink are recorded in §"The reconciliation" and §"Unverified legacy state" with the
  sizes and timestamps those reads returned.
- BeeGFS facts, read 2026-10-20 (the Community license agreement §3.1–3.4 supplies the client,
  capacity and Enterprise-feature limits):
  - <https://doc.beegfs.io/latest/system_design/system_requirements.html>
  - <https://doc.beegfs.io/latest/release_notes.html>
  - <https://doc.beegfs.io/latest/advanced_topics/rdma_support.html>
  - <https://doc.beegfs.io/latest/advanced_topics/storage_tuning.html>
  - <https://doc.beegfs.io/latest/advanced_topics/licensing.html>