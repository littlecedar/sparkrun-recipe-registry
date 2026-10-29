# FLARE — the `gb10` package, the install decision, and the research record

**Status:** 2026-10-23, read-only. Nothing installed, no node contacted, no package executed: every
engine claim below comes from the upstream source and documentation, the `gb10` package card, the Local
Inference Lab APT index, and the arm64 `.deb` **downloaded and inspected** with `bsdtar`, `readelf`, and
`strings` — never installed. Handles such as `orbit.md:288` mean the file in the upstream repository; the
URL for each handle is in §11.

**Scope:** what `flare agent` is, what the `gb10` artifact is, why the APT install is not forced by
container limits, and whether installing it on the fleet should be authorized.

## Contents

- [Status & provenance](#status--provenance)
- [1. Which "FLARE"](#1-which-flare)
- [2. What flare agent actually is](#2-what-flare-agent-actually-is)
- [3. The gb10 package](#3-the-gb10-package)
- [4. Containerization: possible, and why it is still not the route](#4-containerization-possible-and-why-it-is-still-not-the-route)
- [5. The authorization ask (two nodes, not four)](#5-the-authorization-ask-two-nodes-not-four)
- [6. What acceptance grants](#6-what-acceptance-grants)
- [7. Preconditions before the first apt install](#7-preconditions-before-the-first-apt-install)
- [8. What a yes buys — and does not](#8-what-a-yes-buys--and-does-not)
- [9. If the answer is no](#9-if-the-answer-is-no)
- [10. What would change the recommendation](#10-what-would-change-the-recommendation)
- [11. Sources](#11-sources)
- [12. The container route, re-run as the primary option (owner-directed 2026-10-24)](#12-the-container-route-re-run-as-the-primary-option-owner-directed-2026-10-24)

## Status & provenance

This document replaces two notes that covered the same artifact from different angles — what
`flare agent` is (2026-10-22) and whether to authorize installing it (2026-10-23). Their content is
merged here, deduplicated, with the identity split, the grant table, the two-node narrowing and the
preconditions each stated once. The memo's analysis was cited from the brief's source table rather than
restated; that table is folded into §11, so every `[debian.md:…]` and `[gb10:…]` handle resolves.

| part | came from | receipt | what it contributes |
|---|---|---|---|
| mechanism brief (2026-10-22) | `mad-science/FLARE-AGENT-BRIEF.md` | `e1c32a2` | §1–§4, §6–§8, §10–§11 |
| authorization memo (2026-10-23) | `mad-science/FLARE-INSTALL-DECISION.md` | `1db2090` (scope-gap row `8a35e2e`) | §5, §9, §10, and the two-node narrowing |
| package research | `mad-science/TODO.md` §ds4 | — | §3.1 |
| owner question | `mad-science/QUESTIONS.md` `#6` (still open) | `e1c32a2` | what the ask amends |

Evidence words are the sources' own: `[INFERENCE]` marks reasoning rather than a primary source, and
"unverified" means nothing was executed to check it. Nothing in this document was measured on a GB10.

## 1. Which "FLARE"

Six unrelated things answer to the name. Only one matches the artifact in the register.

| Candidate | What it is | Matches? |
|---|---|---|
| **`NVIDIA/flare-local-inference`** | Apache-2.0 Rust inference server for SM120/SM121 GPUs; Rust runtime ("Helios") replaying CUDA graphs captured by a Python preparation stage ("Ignition"); explicitly "a research prototype" `[repo:7-13]` | **yes** — it ships the `flare` binary, the `flare agent`, and `flare orbit`, and the APT package's `Homepage` names this repository `[deb-control]` |
| **NVIDIA FLARE** (`nvflare`) | Federated Learning Application Runtime Environment, a Python SDK `[nvflare]` | no — same vendor and acronym, no GPU inference server, no `flare` binary, no packages |
| **`flarellm`** | WASM/WebGPU browser LLM engine in Rust `[flarellm]` | no — no server, no multi-host, no packages |
| Ubuntu's **`flare`** game package | a game | no — the vendor renames its package `flare-inference` specifically to avoid this collision `[debian.md:12-13]` |
| `flare-foundation/flare-ai-rag` | RAG template for a blockchain kit | no — application template |
| Academic FLARE (routing, diffusion, alignment) | paper acronyms | no — none is a runtime |

The identity split matters for the supply chain and is easy to get wrong: **the engine is NVIDIA's; the
packaged distribution is not.** Upstream publishes source and a `build_deb.sh` (`docs/debian.md:40-65`)
and its tree contains no reference at all to the APT repository host (a full-tree search for
`local-inference-lab.ai` returns nothing). The packages, the repository, and the weights come from Local
Inference Lab: HF namespace `local-inference-lab`, repository `Origin: Local Inference Lab`,
`Label: Flare` `[InRelease:10-11]`, `Maintainer: Local Inference Lab <jasonc@maxlyn.com>` `[deb-control]`.
The GitHub org `local-inference-lab` reports `is_verified: false` `[gh-org]`. "FLARE" is the engine's and
the runtime *format's* name, not a quantization scheme (§3.1).

**This split is the fact the install decision turns on:** the same artifact carries an NVIDIA-authored
engine and a third-party root-capable APT source, so "we trust NVIDIA's inference server" does not answer
"we trust the repository that owns `dpkg` on every node".

## 2. What `flare agent` actually is

`flare agent` is a per-user, per-host control and package-distribution daemon for a controller — it does
not schedule, it does not carry the model's tensor-parallel traffic, and it needs no kernel module, no
root, and no capability an ordinary login session lacks.

One process per host, **per user**, installed as a systemd user unit by `flare agent install` run "as the
user who owns its models" `[debian.md:27-32]`. The unit template embedded in the binary is:

```ini
[Unit]
Description=Flare agent: runs this host's rank of a orbit's serving group
After=network-online.target
[Service]
ExecStart=%h/.local/lib/flare-agent/flare agent --listen
Restart=on-failure
RestartSec=5
[Install]
WantedBy=default.target
```

The template carries no `KillMode`, so the unit inherits systemd's default `control-group`; the vendor
states that this stops a group's ranks when the service stops `[orbit.md:288-291]`. `install` also calls
`loginctl enable-linger` so the service survives logout `[orbit.md:26, deb-strings]`. It copies the
executable to `~/.local/lib/flare-agent/flare` — which is why an APT upgrade alone does not update a
running agent `[debian.md:33-38]`, and why the `gb10` card's update recipe is `apt install --only-upgrade`
**then** `/usr/bin/flare agent install` on every host `[gb10:154-163]`.

**Identity and pairing.** One Ed25519 node key at `~/.config/flare/agent/node.key`, mode `0600`, created
by `install` or the agent's first start; pairing is either a 20-byte one-time code, printed as eight
groups of four base32 characters and valid 24 hours, or `--accept-first`, which authorizes the first
controller to connect `[orbit.md:62-96]`. The node's fingerprint is what the operator compares by eye
before trusting it "for anything that moves executables" `[orbit.md:105-109]`.

**Protocol.** TCP 29900 on all interfaces by default, `--listen IP:PORT` changes it
`[multi-host.md:143]`; every connection is a mutually authenticated, encrypted session — X25519,
Ed25519, HKDF-SHA256, ChaCha20-Poly1305 with the handshake hash as channel binding
`[orbit.md:523-545]`. Verbs: `HELLO`, `PAIR`, `HAVE`, `PUT`,
`CONTROLLERS`, `TRANSFER`, `FETCH`, `FETCH_FABRIC`, `GET` (up to 256 MiB of a node-local file), `STAT`,
`DOWNLOAD`, `RUN`, `ATTACH`, `STOP`, `REMOVE` `[orbit.md:624-639]`.

**What it does for a distributed job.** Not placement: `flare orbit` chooses nodes and GPUs and issues a
signed grant; the agent verifies that grant against its authorized controllers, exposes exactly the
granted GPU UUIDs through `CUDA_VISIBLE_DEVICES`, and starts `flare run PACKAGE --rank R --rendezvous
ZERO:PORT` as a child process `[orbit.md:242-260, 321-323, 650-707]`. Grant expiry bounds launch, not
serving: ten minutes `[orbit.md:695-702]`. It also distributes package shards between peers over
**plain TCP** on the discovered CX7 rails (`--transfer-streams` 1..64, default 8) `[orbit.md:561-572]`,
can pre-stage a package (`orbit push`), can download a pinned HF revision on the node, and streams rank
logs back (`ATTACH`) `[orbit.md:482-486, 635-638]`. It does **not** carry the model's activations: the
tensor-parallel collectives run through a vendored C RoCE proxy, registered host memory plus ibverbs
queue pairs, with GPU kernels polling readiness words `[roce-ring.md:76-82]`. It does not proxy HTTP
either — clients reach rank zero directly `[orbit.md:766-770]`.

**Does it phone home?** The agent does not. The only outbound endpoint in the binary is
`https://huggingface.co`: on every load that is not `--offline`, Flare fetches `publisher.json` from the
package's signed official source to verify the publisher identity `[cli-design.md:733-740]`, and
`DOWNLOAD`/`flare run ORG/NAME` use the Hub. Metrics are local — Prometheus text and `?format=json` on
the serving rank — and the dashboard polls them over the network the operator already controls
`[orbit.md:499-521]`. There is no vendor telemetry, no license server, and no update check in the
binary's string table `[deb-strings]`.

## 3. The `gb10` package

### 3.1 The runtime package

The artifact is a publisher-signed Flare *runtime package*, not an HF checkpoint: weights plus compiled
kernels plus captured execution graphs. Open (`gated: false`), `license: mit` (the file is DeepSeek's own
MIT text), `publisher.json` carries Local Inference Lab's Ed25519 key with `"development": false`, and the
runtime enforces a `--trust-store` acceptance.

Three branches, three packages:

| branch | revision | bytes | shape |
|---|---|---|---|
| `main` | `5f4fd653…` | **4 files, 11,589 B** | card + license + publisher only, **no weights** |
| `gb202` | `30b3987c…` | **513.48 GB** | one host with four SM120 96 GB GPUs |
| `gb10` | `975f72da…` | **511.27 GB / 476.2 GiB** in 22 files | the DGX Spark target |

`gb10` is a 10,470,346 B metadata-only primary `deepseek-v41-flash-1017-tp4-c16-dspark5.safetensors`,
12 weight shards (eight of 58.6–63.9 GB, four of ~5.4 GB), and five graph/support shards (4 × ~490 MB
+ 6.4 MB); every shard is under 64 GB and named by its sha256. Repo `usedStorage`
**1,845,031,706,350 B** (all three revisions' LFS).

**No `config.json` at any branch**, so there is no `quantization_config` to read: the scheme is stated
only on the card — "MXFP4 expert weights retain losslessly compressed CSF scales, attention uses BF16
arithmetic, and KV storage uses FP8 compression" (frontmatter tags `flare`, `mxfp4`, `csf`, `gb10`,
`tensor-parallel`). "FLARE" is the engine's and the format's product name, never expanded on either card,
and **not a quantization scheme**. It does **not** follow the `local-inference-lab` labquant conventions
this registry already consumes: `local-inference-lab/Qwen3.8-Flash-Next-NVFP4` (pinned by
`recipes/qwen4/qwen3.8-flash-next-nvfp4-labquant-sglang.yaml`) is an ordinary sharded HF checkpoint —
`model-000NN-of-00041.safetensors` + a `config.json` carrying `quantization_config.quant_method:
modelopt` (plus `hf_quant_config.json`, `HYBRID.json`, `export-manifest.json`, `chat_template.jinja`) —
loaded by SGLang as `quantization: modelopt_mixed` behind four config-patching mods. FLARE ships no HF
checkpoint, no shard index and no template at any revision.

**Why it matters.** `gb10` is the first artifact this lane has seen whose target *is* four Sparks — "A
signed Flare package for four DGX Sparks", TP4, 16 concurrent requests, DSpark with up to five adaptive
draft tokens, 4096-token prefill chunks, a 1,048,576-token per-request context, and Engram read from disk
with `--embedding-table-cache-size 1GiB` plus ~1.4 GiB resident scales per host — the lane's own shape.
The loader answer is still no for both shipped arms, in the card's words: "It requires the Flare image
below; Transformers, vLLM, SGLang and llama.cpp cannot load this runtime format." Neither
`recipes/ds4/README.md:25` (SGLang) nor `:349` (TensorFold EXL3) reads it, and `gb10` serves from
`flare-inference` installed by `apt` on each host plus `flare orbit` pairing over RoCE (TCP 29900
host-to-host, 29800 on the controller) — a `runtime:` sparkrun does not ship (it has `sglang`, `vllm_ray`,
`vllm_distributed`, `trtllm`, `atlas`, `modular_max`, `tokenary`, `llama_cpp`). **APT is the only route
to a running package.**

**Node arithmetic.** 511.27 GB / 476.2 GiB against 4 × 128 GB = 512 GB nominal (476.8 GiB) leaves ~0.6 GiB
before KV, runtime reserve and the 1 GiB row cache, so the vendor's c16 and 1M-context claims rest on KV
headroom this cluster has not measured — the card itself defers to "subject to available KV memory"
`[gb10:15-18]`, and the `gb202` figure (21,160,832 logical KV tokens on 4 × 96 GB) does not transfer.
Disk is the easy part: "over 515 GB free on the first Spark" plus each rank's data on the peers.

### 3.2 The `.deb` and the APT repository

Unprivileged, by design and by documentation. Root appears exactly once in the whole route:
`sudo apt install flare-inference` to write `/usr/bin/flare`. The arm64 package is 6,455,036 B,
`Installed-Size: 26172`, depends on `libc6 (>= 2.39), libgcc-s1, libibverbs1 (>= 1.1.6), libstdc++6,
ibverbs-providers, ca-certificates`, and contains **no maintainer scripts** — `control.tar.xz` holds
`control` and `md5sums` only, so installation creates and restarts nothing `[Packages-arm64,
deb-control, deb-control-tar]`, which the vendor states in so many words `[debian.md:27]`. The payload is
`/usr/bin/flare` (20,476,184 B, stripped aarch64 PIE) plus `/usr/share/doc`; there is no kernel module,
no DKMS, no `modprobe`, and no system-wide unit anywhere in the archive `[deb-data-tar]`.

**What it touches on the host.** Because the same binary is both agent and rank, the process tree inherits
the serving requirements: `libcuda.so.1` and `libnvidia-ml.so.1` loaded dynamically (CUDA driver entries,
`nvmlInit_v2`, `nvmlDeviceGetCount_v2`) against the driver DGX OS installs; `libibverbs.so.1` as a hard
`DT_NEEDED` on arm64; `/sys/class/infiniband` and a RoCEv2 IPv4 GID (`no active RDMA device has a
RoCEv2 IPv4 GID`); `RLIMIT_MEMLOCK` (failure message `raise RLIMIT_MEMLOCK`); `io_uring` for disk-backed
Engram and prefix-cache offload; `/proc/meminfo`, `/proc/cpuinfo`, `/proc/self/mountinfo`. All of that is
observable in the shipped binary's strings and dynamic table `[deb-strings, deb-elf]`, and the same list
appears in the vendor's container notes `[container.md:39-72, 98-103]`. No `/dev/dri`, no `/dev/nvrm`, no
custom device node, no `CAP_SYS_ADMIN` requirement appears anywhere in either the binary or the
documentation.

### 3.3 Components

| Component | Runs where | Privilege needed | Containerizable? | Evidence |
|---|---|---|---|---|
| `flare-inference` package | **where the package's own shape puts it: one per rank, all four hosts** — the install authorized in §5 is `.34`/`.35` only | root once, for `dpkg` | n/a — it is a file | `[debian.md:27]`, `[deb-data-tar]` |
| `flare run` (one rank) | each Spark, one rank each | unprivileged user; NVIDIA driver, RDMA device, memlock, `io_uring` for disk Engram | **yes — the vendor ships this exact image** and its own x86 card runs it under `docker run` | `[container.md:1-12, 39-50]`, `[Dockerfile]`, `[card:34-50]`, `[ghcr]` |
| `flare agent` (`--listen`) | each host, per user | unprivileged; NVML for GPU facts, home dir, TCP 29900 | **yes in principle** (§4), unsupported in practice | `[debian.md:27-32]`, `[orbit.md:288,523]`, `[deb-strings]` |
| `flare orbit` (controller) | one operator host; needs no GPU | unprivileged; holds the controller private key | yes — a plain CLI with `~/.config` state | `[multi-host.md:16-18, 165-166]` |
| runtime package (weights, cubins, graphs) | cache on each host, mounted read-only | none — data | yes, a bind mount | `[container.md:45-48]`, `[gb10:167-173]` |
| Ignition (preparation) | not needed to serve | Python + CUDA toolkit | out of scope; the vendor keeps it out of both the image and the `.deb` | `[debian.md:7-10]`, `[container.md:3-7]` |

## 4. Containerization: possible, and why it is still not the route

The container is skipped for three reasons — the vendor publishes one container shape (a single-host
*serve* image whose human tags are amd64-only), the agent's documented lifecycle is a systemd **user**
unit with login lingering, and this package's recommended disk-Engram mode needs `io_uring`, which
Docker's default seccomp profile blocks. Those are workarounds, not impossibilities; this section tests
that claim honestly, and §10 gives the facts that would flip the answer.

The vendor never claims the agent cannot be containerized. `docs/container.md` is titled "Serving
container", its example is `flare run`, and its single multi-host sentence is that "Multi-host RoCE
deployment additionally requires the host's RDMA devices and network setup" `[container.md:1-12, 31-32]`.
The image is the same binary — `ENTRYPOINT ["/usr/local/bin/flare"]`, user `flare` UID 10001, no Python,
no CUDA toolkit, `libibverbs1` only on arm64 `[Dockerfile]` — so it contains `agent` too. The `gb10` card
simply never mentions an image `[gb10:29-57]`.

Host access the agent's whole tree needs, and whether Docker can grant it:

| Host access | Why it is needed | Docker grant | What breaks without it |
|---|---|---|---|
| NVIDIA driver libraries and device nodes | CUDA graph replay via `libcuda.so.1`; NVML for the GPU inventory and the once-a-second dashboard sample | `--gpus`, `capabilities=compute,utility` | start fails. Note the vendor's own example passes `capabilities=compute` only `[container.md:41]`; NVML is the `utility` capability `[nvct]`, so a *containerized agent* needs `utility` added — a serve-only container can skip it |
| RDMA verbs: `/dev/infiniband/uverbs*`, `/sys/class/infiniband`, an active RoCEv2 IPv4 GID | tensor-parallel collectives and fabric package transfer | `--device /dev/infiniband` plus `--net=host` | `ibv_open_device` fails; the grant's rail endpoints are unreachable from a bridge netns |
| `IPC_LOCK` / `RLIMIT_MEMLOCK` | registered host memory for the proxy (about 2 MiB per rank in ring mode) and pinned transfer buffers `[roce-ring.md:76-84]` | `--ulimit memlock=-1:-1` (documented) and `--cap-add IPC_LOCK` if a hard limit must be raised inside | "raise RLIMIT_MEMLOCK". **The container route documents this; the systemd user unit does not** — the native path inherits the user session's limits, so whichever route is used the limit should be checked, not assumed `[INFERENCE]` |
| `io_uring_setup/enter/register` | disk-backed Engram (`--embedding-table-storage disk`, the `gb10` card's recommendation `[gb10:134-141]`) and disk prefix-cache offload | a seccomp profile that permits the three syscalls; Docker's default profile may block them `[container.md:98-103]` | Engram reads fail. On the host there is no seccomp filter, so this is a container-only tax |
| TCP 29900 listener, 29800 rendezvous, 8000 API | pairing, agent-to-agent transfer, rank rendezvous, HTTP | `--net=host` (simplest; the grant names rail addresses) | peers and clients cannot reach the recorded addresses |
| `$HOME`: `~/.config/flare/agent/node.key` (0600), `~/.local/lib/flare-agent/flare`, `~/.cache/flare` | identity, the served executable, package cache | a named volume, or a bind of a real home | re-pair on every recreate; the agent's executable copy is lost |
| systemd **user** manager, `loginctl enable-linger` | the documented service lifecycle | none — containers have no user manager | `flare agent install` cannot work inside one; run `flare agent --listen` as the container's PID 1 and let `--restart=unless-stopped` be the supervisor |

Nothing in that table is a "cannot". Two entries are the real cost: the seccomp profile (one file, and
the vendor already tells you which syscalls) and the fact that the agent becomes the container's problem
instead of systemd's.

**The three frictions, each resolving toward the native install:**

1. **The arm64 tags are not pinned to the commit the `gb10` package needs.** The registry tag the x86 card
   uses, `ghcr.io/local-inference-lab/flare:83d582e2-amd64`, exists as an OCI manifest; `83d582e2-arm64`
   does not, and neither does `83d582e2` `[ghcr]`. arm64 appears in the multi-arch `latest` index and in
   one human tag, `beta-5beb454-arm64` `[ghcr]`. Since every executable must match the package's graph
   contract and RoCE proxy ABI `[multi-host.md:38-41]`, a GB10 route through the image means either a
   moving tag or building the image ourselves. `[INFERENCE]` That is the most likely reason the arm64 card
   installs everything, serving included, from APT.
2. **A container has no user manager, so `flare agent install` cannot run inside one, and the image is a
   serve image, not a service image.** It runs as UID 10001 with no unit, no linger, and no `agent
   install`; adopting it for the agent means running a first-class, per-user host service as PID 1 with a
   restart policy — a shape the vendor never documented or tested — and we would own that supervisor
   thereafter.
3. **`io_uring` is a container-only tax.** Docker's default seccomp profile may block
   `io_uring_setup/enter/register`, which disk-backed Engram needs; on the host there is no seccomp
   filter, so the native route removes the problem rather than mitigating it.

Of the three, (2) and (3) are the real costs named above; (1) is an unavailability, not a tax. And what a
container would not remove is the thing usually hoped for: **it is not a privilege reduction.** The agent
can be told to run a controller-supplied executable on every selected node (`--executable PATH` uploads it
and runs it as the agent's user) `[orbit.md:244-251, cli-design.md:153-155]`, and that stays true inside a
container. It also does not remove the driver coupling: the image loads the host's `libcuda.so.1`
`[container.md:5-7]`.

The container would be a packaging improvement we would own: an arm64 image built from a commit we have
verified, a seccomp profile for `io_uring`, `--device /dev/infiniband` and `--net=host` for the rails,
`utility` added to the driver capabilities, and a PID-1 agent with a restart policy — all of it to replace
a systemd user unit the vendor actually supports, with no privilege reduction as a reward.

## 5. The authorization ask (two nodes, not four)

`[INFERENCE]` **Install the `.deb` on `.34`/`.35` only, version-pinned, key fingerprint confirmed out of
band, agent paired by code — and do not install it on `.30`–`.33` while they serve.** That is the verdict
of this document restated as an authorization; the evidence for it is §6 and §7.

**This is a narrower grant than `QUESTIONS.md` `#6` as written, and the difference is deliberate.** The
row asks whether the repository and agent may be installed "on four nodes"; this document asks for two.
The three reasons, evidenced once in §6:

1. **The `#4` fence** — `.30`–`.33` serve the fleet's production inference, and no workload runs there
   until the serve is stood down.
2. **The port-8000 collision** — an Orbit launch binds port 8000 on rank zero, which is the production
   serve's own port on those ranks.
3. **The root-capable APT source** — the APT key's root grant would sit on the serving ranks.

Two nodes settle the supply-chain question; four add no supply-chain evidence and would put a
root-capable source on the ranks that must not be disturbed. **A yes should be recorded as a two-node
authorization, not as an answer to the four-node wording** — the row's scope needs that amendment when it
closes.

Pair by code on those two nodes, not `--accept-first`: the first controller to reach 29900 owns the node
`[gb10:55-57]`. Keep the controller key on one host.

## 6. What acceptance grants

| Artifact | Signed by | What accepting it gives the signer | Blast radius on one node |
|---|---|---|---|
| APT repository | RSA-4096 key `22C4 6BE0 A4C3 F708 F74C 1E75 213A 79D3 3E50 FC06`, uid "Local Inference Lab APT Signing", created 2026-10-20, expires 2028-10-19 `[apt-key]` | **root on every node that installs or later upgrades the package** — `dpkg` runs maintainer scripts as root and the repository may publish a build containing one at any time; the *current* build has none `[deb-control-tar]` | whole filesystem, every service, the fleet's production serve |
| The `.deb` binary itself | same key; `build-info` records `Source-Commit: bb204798880424174143d72bd99648af960970d3`, rustc 1.94.1 `[deb-build-info]`, so an operator can rebuild from that commit and compare | code running as the **model user**, not root | that user's GPUs, model cache, HF token, ssh keys, `~/.config/flare` |
| The runtime package | Ed25519 publisher key in `publisher.json`, namespace `local-inference-lab`, `development: false`, key fingerprint `937c0143f6856d3ee8ad164f62e3d804bd825d7a8750d0accb9a5849f703a8c1` `[publisher]` | **the compiled kernels and captured graphs that will execute in the serving process**; the typed namespace is the key material from which Helios derives executable decryption keys `[cli-design.md:750-753]` | GPU and host memory of every serving rank; the package cannot run without this acceptance |
| The controller key (`~/.config/flare/orbit/controller.key`) | generated locally on the first `flare orbit` command `[orbit.md:68]` | **code execution as the agent's user on every paired node**, and the right to add further controllers `[orbit.md:31, 244-251]` | every paired node's model user |
| Node pairing | node key + code or `--accept-first` | the controller's authority over that node | that node |

The two grants that are not recoverable by a container are the **root-capable APT source** and the
**controller key**. Neither is fixed by containerizing the agent, which is why "the supply-chain
decision" is separable from "the benchmark's".

Fleet-specific blast radius, per node class:

- **`.30`–`.33`** — production inference, fenced: no workload runs there until the serve is stood down
  *(superseded 2026-10-23/24: the `#4` fence lifted (`TP4-BGFS Q1`) and `.30` is a full cluster member
  (owner, 2026-10-24) — its controller + BeeGFS mgmtd/storage duties are additional, never a fence; the
  port-8000 concern below is the real remaining constraint)*
  (`STATUS.md` §Now; settled `#4` in `TODO.md` §"Settled questions"). Installing the *package* starts
  nothing and binds nothing (no maintainer scripts, no system unit), so the marginal risk today is
  supply-chain only: a third-party root-capable APT source that every future `apt upgrade` will exercise.
  Installing the *agent* additionally binds 29900 on all interfaces and leaves a linger-kept user
  process, and an Orbit launch binds 29800 (rendezvous, on the controller/rank zero) and 8000 for the API
  `[gb10:25-27]` — 8000 is the production serve's port there
  (`recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml:37`). The agent does not belong on a
  serving rank.
- **`.34`/`.35`** — free, and the honest place to run this. Install, pair by code, and keep the
  controller key on one host (§5).

## 7. Preconditions before the first `apt install`

All four must hold before the first install. The register's row does not itself fix any of them; the ask
in §5 does.

1. **Pin the version.** `apt install flare-inference=<version>`: the repository serves three arm64 builds
   already (`0.1.0~git20261020031126.8f32be2a-1`, `…20190729.5dd67695-1`, `…21004534.bb204798-1`)
   `[Packages-arm64]` and `apt` takes the newest, so the installed build can differ from what was
   reviewed. Install `flare-inference=0.1.0~git20261021004534.bb204798-1` explicitly. The project's own
   landing page is already behind its index — it advertises "Build 5dd67695" while the index serves
   `bb204798` `[ppa, Packages-arm64]` — so "latest" is not a version.
2. **Confirm the key out of band.** The fingerprint
   `22C4 6BE0 A4C3 F708 F74C 1E75 213A 79D3 3E50 FC06` is published only on the same host that serves
   the key and the packages `[ppa]`, so first trust is trust-on-first-use unless it is checked through
   another channel.
3. **Prove the build.** `build-info` names the source commit; rebuilding it with `./scripts/build_deb.sh`
   from that commit and comparing hashes is the only step that ties the binary to NVIDIA's source rather
   than to the signer.
4. **Pre-provision the trust store, or expect the prompt.** First use is interactive: the operator types
   the publisher namespace, and that string decrypts the package's executables `[cli-design.md:750-753]`.
   A headless launch needs either a prepared `trust.toml` or both
   `--dangerously-approve-key FINGERPRINT --dangerously-accept-publisher NAMESPACE`
   `[cli-design.md:417-419]`. That resolves the register's "interactive first run" blocker — the flags
   exist, and the name says what they are.

## 8. What a yes buys — and does not

**Buys:** the acquisition blocker is removed. On two nodes we can settle that the repository, key, and
package install and upgrade cleanly; that the agent pairs, survives a reboot under lingering, and refuses
an unauthorized controller; and — after `flare download --revision gb10` on `.34` — the package's own
metadata through `flare inspect PRIMARY --plain` `[cli-design.md:99]` plus a `--dry-run` that "reads the
package metadata, verifies its signatures, and queries nodes" without starting a rank
`[multi-host.md:335-336]`. That is the supply-chain decision's evidence, and it is separable from the
benchmark's.

**Does not buy:** the `gb10` TP4, c16, and 1M-context claims. The package fixes four ranks and Orbit
cannot re-cut it for fewer hosts `[multi-host.md:3-5, 35-37]`, so that boot needs four eligible ranks and
waits on the `#4` fence *(superseded 2026-10-23: the fence lifted — `.30`–`.33` are open)*. Accuracy is unmeasured by the vendor on any card — only the x86 card says
"Comprehensive model-accuracy evaluation has not been run" `[card:131]`. The node arithmetic (§3.1)
leaves almost no KV headroom, so the card's concurrency and context claims rest on memory no node here
has measured. GB10 behavior of either route needs a boot.

Authorizing the install therefore does **not** unblock the package's evaluation; it only removes the
acquisition blocker from the `#4` act. The `gb10` TP4 cell cannot be evaluated at all until its engine can
be acquired; it stays **research-only** *(the `#4` fence it sat behind lifted 2026-10-23; the remaining
gate is the owner's offsite switch and the `#6` container decision)*.
`QUESTIONS.md` `#6` is not closed by this document.

## 9. If the answer is no

`#6` closes negative and the `gb10` artifact stays research-only: no APT acceptance is made, no agent
pairs, and the cell remains unevaluable because its engine cannot be acquired. The "do not install"
reason — refusing to carry a third-party root-capable APT source on any fleet node — is not addressed by
containerizing, so a no is a durable no for this artifact, not a "later, in a container".

## 10. What would change the recommendation

- **An arm64 image tag pinned to a commit that satisfies the `gb10` package's graph contract and RoCE
  proxy ABI.** That would move the route to the container and remove the APT-root grant.
- **Evidence that the APT build cannot load the `gb10` package at all**, which would send the route back
  through preparation and a self-built image.
- A reason to flip to *do not install*: **refusal to carry a third-party root-capable APT source on any
  fleet node**, which no container would fix either — the `.deb` is not the only privileged artifact in
  that chain, and the controller key is equivalent to a shell as the model user on every paired node by
  design.

## 11. Sources

| Handle | URL |
|---|---|
| `[repo]` | https://github.com/NVIDIA/flare-local-inference (Apache-2.0, last push 2026-10-22) |
| `[debian.md]` | https://github.com/NVIDIA/flare-local-inference/blob/main/docs/debian.md |
| `[container.md]` | https://github.com/NVIDIA/flare-local-inference/blob/main/docs/container.md |
| `[multi-host.md]` | https://github.com/NVIDIA/flare-local-inference/blob/main/docs/multi-host.md |
| `[orbit.md]` | https://github.com/NVIDIA/flare-local-inference/blob/main/docs/orbit.md |
| `[roce-ring.md]` | https://github.com/NVIDIA/flare-local-inference/blob/main/docs/roce-ring.md |
| `[cli-design.md]` | https://github.com/NVIDIA/flare-local-inference/blob/main/docs/cli-design.md |
| `[Dockerfile]` | https://github.com/NVIDIA/flare-local-inference/blob/main/Dockerfile |
| `[gb10]` | https://huggingface.co/local-inference-lab/DeepSeek-V4.1-Flash-1017-FLARE/blob/gb10/README.md |
| `[card]` | https://huggingface.co/local-inference-lab/DeepSeek-V4.1-Flash-1017-FLARE/blob/main/README.md |
| `[publisher]` | https://huggingface.co/local-inference-lab/DeepSeek-V4.1-Flash-1017-FLARE/raw/main/publisher.json |
| `[ppa]` | https://ppa.local-inference-lab.ai/ |
| `[InRelease]` | https://ppa.local-inference-lab.ai/dists/noble/InRelease |
| `[Packages-arm64]` | https://ppa.local-inference-lab.ai/dists/noble/main/binary-arm64/Packages |
| `[apt-key]` | https://ppa.local-inference-lab.ai/lil-flare-archive.asc |
| `[deb]` | https://ppa.local-inference-lab.ai/pool/main/f/flare-inference/flare-inference_0.1.0~git20261021004534.bb204798-1_arm64.deb |
| `[deb-control]`, `[deb-control-tar]`, `[deb-data-tar]`, `[deb-build-info]`, `[deb-strings]`, `[deb-elf]` | the `[deb]` above, read locally: `bsdtar -xf`, `control.tar.xz`, `data.tar.xz`, `usr/share/doc/flare-inference/build-info`, `strings -a`, `readelf -d` |
| `[ghcr]` | `ghcr.io/local-inference-lab/flare` tag and manifest API (`/v2/local-inference-lab/flare/tags/list`, `manifests/<tag>`) |
| `[gh-org]` | https://api.github.com/orgs/local-inference-lab |
| `[nvct]` | https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html#driver-capabilities |
| `[nvflare]` | https://developer.nvidia.com/flare |
| `[flarellm]` | https://github.com/sauravpanda/flarellm |

## 12. The container route, re-run as the primary option (owner-directed 2026-10-24)

The owner's directive answering `QUESTIONS.md` `#6`: "Explore building our own container — we prefer to
avoid installing third-party APT repositories unless absolutely necessary." This section re-runs the
container analysis as the primary route rather than the ruled-out one, and it begins with a search the
directive did not originally call for and the owner then added explicitly: whether a usable arm64 image
already exists. **The search changed the answer — the vendor now publishes one.**

### 12.1 Pre-existing arm64 container search (exhaustive)

Since §4's GHCR snapshot (2026-10-23), the registry has grown CI `sha-<commit>` tags and, dated
2026-10-22, multi-arch `release-<commit>-…` indexes. Every candidate below was resolved through the
registry v2 API with an anonymous pull token; architecture comes from the manifest, never the tag name.
Fetched 2026-10-24.

| Source → probe | Result | Evidence |
|---|---|---|
| `ghcr.io/local-inference-lab/flare` → tags list | 40 tags. Multi-arch indexes (`latest`, `beta`, `release`, `release-947a5a6-k7-20261022`, `release-2193455-k7-20261022`, `release-2193455-k7-pf4096-20261022`, `sha-8f32be2a…-39362982142-2`, `sha-e7b8c016…-manual-20261020T182758Z-1`), each with a `linux/arm64` child | `[ghcr2]` [VERIFIED] |
| … `release-2193455-k7-20261022` index | arm64 child `sha256:1bda9d9129970f57af027e0e153c9766fa390cef559c602be3409d02b9db1fb2`; index annotation `org.opencontainers.image.revision: 2193455651794642debdaad0dda91e77ab675031` ("Show observed peaks in dashboard chart labels", 2026-10-22T23:06Z). `latest` and `release` resolve to the same children | `[ghcr2]` + GitHub commits API [VERIFIED] |
| … `release-947a5a6-k7-20261022` index | arm64 child `sha256:012e4ce8…`; revision `947a5a6dd17…` ("Allocate packed verification graphs with an independent count budget", 2026-10-22T18:37Z) | same [VERIFIED] |
| … `sha-8f32be2a…` index | arm64 child `sha256:8ee211dd…`; commit = APT build `0.1.0~git20261020031126.8f32be2a-1` | `[ghcr2]`, `[Packages-arm64]` [VERIFIED] |
| … `beta-5beb454-arm64` | a single-arch arm64 manifest — the one tag §4 already knew | `[ghcr2]` [VERIFIED] |
| … `release-2193455-k7-pf4096-20261022` index | arm64 child identical to the un-suffixed tag's — an alias, not a variant | `[ghcr2]` [VERIFIED] |
| Docker Hub: `local-inference-lab` namespace; search "flare-inference"/"flare-local-inference"; `nvidia/flare`, `nvidia/flare-inference` | empty namespace; only fuzzy non-vendor matches; both NVIDIA names 404 | Hub v2 API [VERIFIED negative] |
| NVIDIA NGC (`catalog.ngc.nvidia.com`) | catalog not queryable anonymously (JS app shell, no public search API answered); `nvcr.io/nvidia/flare` is the unrelated federated-learning product | [NEGATIVE UNPROVEN — LIKELY none; an NGC pull needs an account this fleet has not used] |
| Quay.io public search | no `local-inference-lab` or flare-inference image | Quay API [VERIFIED negative] |
| GitHub Packages (`orgs/local-inference-lab/packages`) | 401 unauthenticated — but this org's containers are exactly the GHCR listing above, enumerated directly | [VERIFIED by substitution] |
| GitHub Releases of `NVIDIA/flare-local-inference` | none — the releases list is empty; no binary tarball, no wheel, no image artifact | Releases API [VERIFIED negative] |
| PyPI `flare-inference` / `flare-local-inference`; npm `flare-inference` | 404 ×3 | [VERIFIED negative] |
| `local-inference-lab` org repos (`p2pmark`, `rtx6kpro`, `llm-inference-bench`, `quant-toolkit`) | none is a container or agent-packaging repo | org repos API [VERIFIED negative] |
| GitHub repo search: "flare-local-inference"; "flare dgx-spark" | upstream plus 67 plain forks, none repackaging the agent; closest community work is **source builds, not containers**: `sxuff/qwen38-flash-next-flare` builds Flare 0.1.0 from source (`1fd1f91`) and serves on one GB10 | `[gh-search]`, `[sxuff]` [VERIFIED as searched] |
| Web search for a community arm64 flare-agent container | none found; `MiaAI-Lab/sparkDash` only *monitors* Flare endpoints on arm64 Sparks | `[sparkdash]` [VERIFIED as searched] |

**Conclusion:** a vendor-published, commit-annotated `linux/arm64` image exists. The memo's flip
condition (§10, first bullet) is satisfied structurally. Two caveats keep the self-build sketch (§12.3)
alive as the fallback: (a) there is **no `sha-bb204798` tag** — the image commits (2026-10-22) are
*newer* than the `.deb` pin (`bb204798`, built 2026-10-21), and whether a newer binary satisfies the
`gb10` package's graph contract and RoCE proxy ABI (`[multi-host.md:38-41]`) is unverifiable without a
boot; (b) `k7` and `pf4096` are undocumented in the repo tree [SPECULATIVE: `pf4096` plausibly the
card's 4096-token prefill chunk, but its manifest children are byte-identical to the un-suffixed tag's,
so the tag is an alias either way].

### 12.2 What the APT route supplies, and what a container can supply

| Artifact | In the APT repo? | Container substitute | Status |
|---|---|---|---|
| the binary — agent, rank runner, and Helios engine in one stripped aarch64 PIE (`/usr/bin/flare`, 20.5 MB) | yes — the `.deb`'s only payload beyond docs (`[deb-data-tar]`) | the image's `/usr/local/bin/flare`, built from the same repo (`cargo build --locked --release`, rustc 1.94.1) | [VERIFIED] `[Dockerfile]` |
| engine runtime | same binary (Helios links in; no CUDA toolkit, no Python in the image) | same | [VERIFIED] `[Dockerfile]`, `container.md` (2193455) intro |
| runtime package — weights, cubins, graphs | **no — never in the repo**; fetched from the HF Hub (`flare download ORG/MODEL --revision gb10`) | same; bind-mount a Hub cache owned by UID 10001, or `--user` the host UID | [VERIFIED] `container.md` (2193455), "Downloading packages" |
| config — trust store, publisher key, HF token | no; operator-provisioned (`trust.toml`, `publisher.json`) | bind-mount + `--trust-store`; unattended approval via the §7.4 flags | [VERIFIED] `container.md` (2193455), "Run" |

The APT repository supplies exactly **one** needed artifact: the binary. Everything else already comes
from outside the repository. That is what makes the owner's preference actionable rather than symbolic.

### 12.3 Build recipe sketch — shrunk to the fallback delta

Because §12.1 found a usable arm64 image, the sketch below is what remains **if** the vendor image is
rejected (commit skew, or distrust of Local Inference Lab's build):

- **Base and toolchain.** Upstream's own `Dockerfile` already targets both architectures: `rust:1.94.1-slim-trixie`
  build stage, `debian:trixie-slim` runtime, `libibverbs1` + providers on arm64 only,
  `ENTRYPOINT ["/usr/local/bin/flare"]`, UID 10001, no CUDA toolkit and no Python — `libcuda.so.1` is
  loaded from the host through `--gpus` [VERIFIED, re-read 2026-10-24]. Build with
  `docker buildx build --platform linux/arm64 .` on a Spark; the rustc version matches the `.deb`'s
  `build-info`.
- **No third-party APT at any step.** The base images are official Docker Hub images and the runtime
  stage's `apt-get` lines hit only Debian's own repositories [VERIFIED, Dockerfile].
- **Provenance tie.** `cargo build --locked` from a chosen commit reproduces the build; comparing
  against the `.deb` binary (§7.3) extends to an image the same way [LIKELY — Lockfile pins crates;
  the aarch64 toolchain is pinned by the base image tag].
- **Lifecycle mapping.** `flare agent install` + `loginctl enable-linger` becomes `flare agent --listen`
  as PID 1 under `--restart=unless-stopped`; `Restart=on-failure, RestartSec=5` maps onto the restart
  policy. `$HOME` state — `node.key` (0600), the `~/.local/lib/flare-agent/flare` copy, `~/.cache/flare`
  — moves to a named volume or a bind so pairing survives recreation; pair by code, per §5 [LIKELY —
  spec'd, not tested; the agent-in-container shape remains undocumented, §4 friction 2].
- **Host grants.** `--net=host` (grant names rail addresses), `--device /dev/infiniband`,
  `--gpus …,capabilities=compute,utility` (a containerized agent needs NVML, so `utility`),
  `--ulimit memlock=-1:-1`.
- **Secrets.** `node.key`, pairing code, `trust.toml`, `publisher.json`, optional HF token — all
  mounted, none baked into the image.

### 12.4 The `io_uring` / seccomp question

- **Verified:** the engine's disk modes need `io_uring_setup`, `io_uring_enter`, `io_uring_register`,
  and the vendor says so plainly: "The container's seccomp policy must permit … Docker's default policy
  can block them; use a policy allowing those calls" (`container.md` at 2193455, closing paragraph).
- **Verified:** Docker's default profile denies all three. The engine's syscall table lists them as
  "Blocked due to security vulnerabilities that can be exploited to break out of containers. See
  moby/moby#46762"; moby's generated default profile is `SCMP_ACT_ERRNO` with no `io_uring_*` entry in
  its allowlist, so the syscalls are denied by absence (moby master, 2026-10-24; the block PR closed
  2023-11-02 and shipped in the Nov-2023 security releases [LIKELY — the version attribution was not
  re-confirmed]).
- **The unblock route:** start from the engine's own default profile JSON, add the three syscall names
  to the allowlist, pass `--security-opt seccomp=profile.json`. Do **not** use `seccomp=unconfined`.
  Residual risk: a custom profile freezes Docker's syscall protections at today's default and drifts
  as Docker updates — but the delta is three allowlist entries, reviewable in one glance, and the
  profile is ours to re-diff on engine upgrades. Kernel-side, a node with `kernel.io_uring_disabled`
  set would fail the probe too — this was settled on `.35` the same day (below); the kernel permits it.
- **If it cannot be permitted:** the container keeps only RAM-backed Engram modes, losing the card's
  recommended `--embedding-table-storage disk`. The honest phrasing of that outcome is "disk-Engram
  unavailable in container", not "container impossible" — and the probe decides it before any
  build work is spent. **It did: both probes ran on `.35` on 2026-10-24** (results in §12.5).

### 12.5 Probes executed, and the remaining go/no-go

Two of the three de-risking probes were executed on `.35` only (never `.34`, a quartet rank in the
declared window), seconds-long `docker run --rm` calls alongside the TP≤2 boots, on 2026-10-24,
Docker `29.6.2`; receipts and the generated seccomp profile in `~/benchmarks/flare-probe-20261024/`
on `.35` [VERIFIED, observed output]:

1. **The image runs from the pinned digest.**
   `docker run --rm ghcr.io/local-inference-lab/flare@sha256:1bda9d91… --version` pulled the arm64
   image by digest and printed **`flare 0.1.0`**. The arm64 route is real, not a tag-list inference.
2. **The `io_uring` block is confirmed and is unblocked exactly as designed.** A `ctypes` probe calling
   `io_uring_setup` (syscall 425) inside `python:3.13-slim` returned
   `io_uring_setup syscall 425 -> -1 errno 1` (EPERM) under Docker's *default* profile, and
   `io_uring_setup syscall 425 -> 3 errno 0` (an open fd) under the custom profile — moby's default
   `default.json` plus one allowlist group naming the three `io_uring_*` syscalls. The custom-profile
   route is proven, not just plausible.

Both images were removed again (`docker rmi`) so `.35` is left as found; the profile JSON stays in the
receipts directory.

**Reframed verdict: the two cheap probes passed; what remains is not cheap and does not go ahead in
this window's endgame.** Probe 3 — `flare agent --listen` as PID 1 with the §12.3 grants, pairing, and
then the actual `gb10` package trial — is the real container trial, and it is **not authorized inside
this window**; it goes to the owner together with the commit-skew question: is the `2193455` image
acceptable, or must the binary be exactly the `bb204798` `.deb` pin (§12.3 self-build, still
APT-free)? If the owner authorizes the trial and answers the skew question, the APT route is
unnecessary for everything the repository supplies, and `#6` is closable as "container route
authorized; APT never installed."

### 12.6 What this does not decide

Nothing was installed, no agent ran, no pairing was made, and no serving container was touched. The
only node contact was two seconds-long `docker run --rm` probes on `.35` — a `--version` call on the
digest-pinned image and the `io_uring` seccomp pair — with both pulled images removed afterward and
the profile JSON left in `~/benchmarks/flare-probe-20261024/` on `.35`. The APT route is not formally
declined — §5 remains the standing verdict for it, and this addendum shows the owner's preference is
satisfiable if the trial passes. Whether the `gb10` package loads and serves at all — accuracy, KV
headroom, the c16 and 1M-context claims — remains unmeasured by either route, and `QUESTIONS.md` `#6`
stays open until the owner rules.


Sources added by this section:

| Handle | URL / method |
|---|---|
| `[ghcr2]` | ghcr.io registry v2 API (`local-inference-lab/flare` tags list and manifests, anonymous pull token), fetched 2026-10-24 |
| `[moby-seccomp]` | docs.docker.com/engine/security/seccomp (syscall table) and moby master `vendor/github.com/moby/profiles/seccomp/{default.json,default_linux.go}`, 2026-10-24 |
| `[moby-46762]` | github.com/moby/moby/pull/46762 (closed 2023-11-02) |
| `[gh-search]` | api.github.com repo search: `flare-local-inference`, `flare dgx-spark`; upstream forks list (67) |
| `[sxuff]` | github.com/sxuff/qwen38-flash-next-flare (README, main) |
| `[sparkdash]` | github.com/MiaAI-Lab/sparkDash (README) |
