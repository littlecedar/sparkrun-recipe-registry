# What `flare agent` is, and why the APT install is not forced by container limits

**Status:** 2026-10-22, read-only. Nothing installed, no node contacted, no package executed: every
engine claim below comes from the upstream source and documentation, the `gb10` package card, the Local
Inference Lab APT index, and the arm64 `.deb` **downloaded and inspected** with `bsdtar`, `readelf`, and
`strings` — never installed. Registry-side facts are quoted from `mad-science/STATUS.md:17-19`,
`mad-science/TODO.md:405-458`, and `mad-science/QUESTIONS.md:23,25`. Handles such as `orbit.md:288` mean
the file in the upstream repository; the URL for each handle is in §8.

**Question:** what does `flare agent` do, and why can it not be folded into a Docker container instead of
the bare-metal APT install?

**Answer:** it can be, in principle. `flare agent` is a per-user, per-host control and
package-distribution daemon for a controller — it does not schedule, it does not carry the model's
tensor-parallel traffic, and it needs no kernel module, no root, and no capability an ordinary login
session lacks. The container is skipped because the vendor publishes one container shape (a single-host
*serve* image whose human tags are amd64-only), because the agent's documented lifecycle is a systemd
**user** unit with login lingering, and because this package's recommended disk-Engram mode needs
`io_uring`, which Docker's default seccomp profile blocks. Those are workarounds, not impossibilities;
§6 gives the verdict and the single fact that would flip it.

---

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
the runtime *format's* name, not a quantization scheme (`mad-science/TODO.md:419-422`).

## 2. What `flare agent` actually is

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
`loginctl enable-linger` so the service survives logout `[orbit.md:26, deb-strings]`. It copies the executable
to `~/.local/lib/flare-agent/flare` — which is why an APT upgrade alone does not update a running agent
`[debian.md:33-38]`, and why the `gb10` card's update recipe is `apt install --only-upgrade` **then**
`/usr/bin/flare agent install` on every host `[gb10:154-163]`.

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

**Privilege.** Unprivileged, by design and by documentation. Root appears exactly once in the whole
route: `sudo apt install flare-inference` to write `/usr/bin/flare`. The arm64 package is 6,455,036 B,
`Installed-Size: 26172`, depends on `libc6 (>= 2.39), libgcc-s1, libibverbs1 (>= 1.1.6), libstdc++6,
ibverbs-providers, ca-certificates`, and contains **no maintainer scripts** — `control.tar.xz` holds
`control` and `md5sums` only, so installation creates and restarts nothing `[Packages-arm64, deb-control,
deb-control-tar]`, which the vendor states in so many words `[debian.md:27]`. The payload is
`/usr/bin/flare` (20,476,184 B, stripped aarch64 PIE) plus `/usr/share/doc`; there is no kernel module,
no DKMS, no `modprobe`, and no system-wide unit anywhere in the archive `[deb-data-tar]`.

**What it touches on the host.** Because the same binary is both agent and rank, the process tree inherits
the serving requirements: `libcuda.so.1` and `libnvidia-ml.so.1` loaded dynamically (CUDA driver entries,
`nvmlInit_v2`, `nvmlDeviceGetCount_v2`) against the driver DGX OS installs; `libibverbs.so.1` as a hard
`DT_NEEDED` on arm64; `/sys/class/infiniband` and a RoCEv2 IPv4 GID (`no active RDMA device has a
RoCEv2 IPv4 GID`); `RLIMIT_MEMLOCK` (failure message `raise RLIMIT_MEMLOCK`); `io_uring` for disk-backed
Engram and prefix-cache offload; `/proc/meminfo`, `/proc/cpuinfo`, `/proc/self/mountinfo`. All of that is
observable in the shipped binary's strings and dynamic table `[deb-strings, deb-elf]`, and the same list
appears in the vendor's container notes `[container.md:39-72, 98-103]`. No `/dev/dri`, no `/dev/nvrm`, no custom
device node, no `CAP_SYS_ADMIN` requirement appears anywhere in either the binary or the documentation.

**Does it phone home?** The agent does not. The only outbound endpoint in the binary is
`https://huggingface.co`: on every load that is not `--offline`, Flare fetches `publisher.json` from the
package's signed official source to verify the publisher identity `[cli-design.md:733-740]`, and
`DOWNLOAD`/`flare run ORG/NAME` use the Hub. Metrics are local — Prometheus text and `?format=json` on
the serving rank — and the dashboard polls them over the network the operator already controls
`[orbit.md:499-521]`. There is no vendor telemetry, no license server, and no update check in the
binary's string table `[deb-strings]`.

## 3. Component / privilege / containerizability

| Component | Runs where | Privilege needed | Containerizable? | Evidence |
|---|---|---|---|---|
| `flare-inference` package | all four hosts | root once, for `dpkg` | n/a — it is a file | `[debian.md:27]`, `[deb-data-tar]` |
| `flare run` (one rank) | each Spark, one rank each | unprivileged user; NVIDIA driver, RDMA device, memlock, `io_uring` for disk Engram | **yes — the vendor ships this exact image** and its own x86 card runs it under `docker run` | `[container.md:1-12, 39-50]`, `[Dockerfile]`, `[card:34-50]`, `[ghcr]` |
| `flare agent` (`--listen`) | each host, per user | unprivileged; NVML for GPU facts, home dir, TCP 29900 | **yes in principle** (§4), unsupported in practice | `[debian.md:27-32]`, `[orbit.md:288,523]`, `[deb-strings]` |
| `flare orbit` (controller) | one operator host; needs no GPU | unprivileged; holds the controller private key | yes — a plain CLI with `~/.config` state | `[multi-host.md:16-18, 165-166]` |
| runtime package (weights, cubins, graphs) | cache on each host, mounted read-only | none — data | yes, a bind mount | `[container.md:45-48]`, `[gb10:167-173]` |
| Ignition (preparation) | not needed to serve | Python + CUDA toolkit | out of scope; the vendor keeps it out of both the image and the `.deb` | `[debian.md:7-10]`, `[container.md:3-7]` |

## 4. Testing the containerization claim honestly

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

Two further asymmetries, both checkable and both currently against the container for *this* package:

1. **There is no arm64 image pinned to the commit the cards name.** The registry tag the x86 card uses,
   `ghcr.io/local-inference-lab/flare:83d582e2-amd64`, exists as an OCI manifest; `83d582e2-arm64` does
   not, and neither does `83d582e2` `[ghcr]`. arm64 appears in the multi-arch `latest` index and in one
   human tag, `beta-5beb454-arm64` `[ghcr]`. Since every executable must match the package's graph
   contract and RoCE proxy ABI `[multi-host.md:38-41]`, a GB10 route through the image means either a
   moving tag or building the image ourselves. `[INFERENCE]` That is the most likely reason the arm64 card
   installs everything, serving included, from APT.
2. **The image is a serve image, not a service image.** It runs as UID 10001 with no unit, no linger, and
   no `agent install`; adopting it for the agent means running a first-class, per-user host service in a
   shape the vendor never documented or tested.

What containerizing would *not* buy, and the brief is explicit about this because it is the usual reason
to reach for a container: it is not a privilege reduction. The agent can be told to run a
controller-supplied executable on every selected node (`--executable PATH` uploads it and runs it as the
agent's user) `[orbit.md:244-251, cli-design.md:153-155]`, and that stays true inside a container. It also
does not remove the driver coupling: the image loads the host's `libcuda.so.1` `[container.md:5-7]`.

## 5. Supply chain: what each acceptance actually grants

| Artifact | Signed by | What accepting it gives the signer | Blast radius on one node |
|---|---|---|---|
| APT repository | RSA-4096 key `22C4 6BE0 A4C3 F708 F74C 1E75 213A 79D3 3E50 FC06`, uid "Local Inference Lab APT Signing", created 2026-10-20, expires 2028-10-19 `[apt-key]` | **root on every node that installs or later upgrades the package** — `dpkg` runs maintainer scripts as root and the repository may publish a build containing one at any time; the *current* build has none `[deb-control-tar]` | whole filesystem, every service, the fleet's production serve |
| The `.deb` binary itself | same key; `build-info` records `Source-Commit: bb204798880424174143d72bd99648af960970d3`, rustc 1.94.1 `[deb-build-info]`, so an operator can rebuild from that commit and compare | code running as the **model user**, not root | that user's GPUs, model cache, HF token, ssh keys, `~/.config/flare` |
| The runtime package | Ed25519 publisher key in `publisher.json`, namespace `local-inference-lab`, `development: false`, key fingerprint `937c0143f6856d3ee8ad164f62e3d804bd825d7a8750d0accb9a5849f703a8c1` `[publisher]` | **the compiled kernels and captured graphs that will execute in the serving process**; the typed namespace is the key material Helios derives executable decryption keys from `[cli-design.md:750-753]` | GPU and host memory of every serving rank; the package cannot run without this acceptance |
| The controller key (`~/.config/flare/orbit/controller.key`) | generated locally on the first `flare orbit` command `[orbit.md:68]` | **code execution as the agent's user on every paired node**, and the right to add further controllers `[orbit.md:31, 244-251]` | every paired node's model user |
| Node pairing | node key + code or `--accept-first` | the controller's authority over that node | that node |

Fleet-specific blast radius, per node class:

- **`.30`–`.33`** — production inference, fenced: no workload runs there until the serve is stood down
  (`mad-science/STATUS.md:19`, `mad-science/QUESTIONS.md:23`). Installing the *package* starts nothing and
  binds nothing (no maintainer scripts, no system unit), so the marginal risk today is supply-chain only:
  a third-party root-capable APT source that every future `apt upgrade` will exercise. Installing the
  *agent* additionally binds 29900 on all interfaces and leaves a linger-kept user process, and an Orbit
  launch binds 29800 on rank zero and 8000 for the API `[gb10:25-27]` — 8000 is the production serve's port
  there (`recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml:37`). The agent does not belong on a
  serving rank.
- **`.34`/`.35`** — free, and the honest place to run this. Install, pair by code (not `--accept-first`:
  the first controller to reach 29900 owns the node `[gb10:55-57]`), and keep the controller key on one
  host.

Four prerequisites before any install, none of which the register's question currently fixes:

1. **Pin the version.** `apt install flare-inference=<version>`: the repository serves three arm64 builds
   already (`0.1.0~git20261020031126.8f32be2a-1`, `…20190729.5dd67695-1`, `…21004534.bb204798-1`)
   `[Packages-arm64]` and `apt` takes the newest, so the installed build can differ from what was
   reviewed. The project's own landing page is already behind its index — it advertises "Build 5dd67695"
   while the index serves `bb204798` `[ppa, Packages-arm64]`.
2. **Confirm the key out of band.** The fingerprint is published only on the same host that serves the key
   and the packages `[ppa]`, so first trust is trust-on-first-use unless it is checked through another
   channel.
3. **Prove the build.** `build-info` names the source commit; rebuilding it with `./scripts/build_deb.sh`
   from that commit and comparing hashes is the only step that ties the binary to NVIDIA's source rather
   than to the signer.
4. **Pre-provision the trust store, or expect the prompt.** First use is interactive: the operator types
   the publisher namespace, and that string decrypts the package's executables `[cli-design.md:750-753]`.
   A headless launch needs either a prepared `trust.toml` or both
   `--dangerously-approve-key FINGERPRINT --dangerously-accept-publisher NAMESPACE`
   `[cli-design.md:417-419]`. That resolves the register's "interactive first run" blocker
   (`mad-science/TODO.md:453-454`) — the flags exist, and the name says what they are.

## 6. What an install on `.34`/`.35` would and would not buy

The `gb10` package fixes four ranks and Orbit cannot re-cut it for fewer hosts
`[multi-host.md:3-5, 35-37]`, so a two-node install **cannot** measure the TP4, c16, or 1M-context claims: that
boot needs four eligible ranks and waits on `#4` (`mad-science/QUESTIONS.md:23`). What two nodes can
settle without a fence change: that the repository, key, and package install and upgrade cleanly; that the
agent pairs, survives a reboot under lingering, and refuses an unauthorized controller; and — after
`flare download --revision gb10` on `.34` — the package's own metadata through `flare inspect PRIMARY
--plain` `[cli-design.md:99]` plus a `--dry-run` that "reads the package metadata, verifies its signatures,
and queries nodes" without starting a rank `[multi-host.md:335-336]`. That is the supply-chain decision's
evidence, and it is separable from the benchmark's. Authorizing the install therefore does **not** by
itself unblock the package's evaluation; it only removes the acquisition blocker from the `#4` act.

## 7. Verdict

`[INFERENCE]` **Install the `.deb` on `.34`/`.35` only, version-pinned, key confirmed out of band, agent
paired by code — and do not install it on `.30`–`.33` while they serve.** The container would be a
packaging improvement we would own: an arm64 image built from a commit we have verified, a seccomp profile
for `io_uring`, `--device /dev/infiniband` and `--net=host` for the rails, `utility` added to the driver
capabilities, and a PID-1 agent with a restart policy — all of it to replace a systemd user unit the
vendor actually supports, with no privilege reduction as a reward.

The one fact that would change the verdict: **an arm64 image tag pinned to the commit that satisfies the
`gb10` package's graph contract and RoCE proxy ABI** (or, equivalently, the discovery that the APT build
cannot load that package at all, which would send the route back through preparation and a self-built
image). A reason to flip to *do not install*: refusal to carry a third-party root-capable APT source on
any fleet node, which no container would fix either — the `.deb` is not the only privileged artifact in
that chain, and the controller key is equivalent to a shell as the model user on every paired node by
design.

What this brief does **not** settle: whether the `gb10` package fits at all (the node arithmetic in
`mad-science/TODO.md:441-445` leaves ~0.6 GiB before KV, and the card's c16 and 1M-context claims are
"subject to available KV memory" `[gb10:15-18]`); accuracy, since the `gb10` card states none and only the
x86 card says "Comprehensive model-accuracy evaluation has not been run" `[card:131]`; and GB10 behavior
of either route, which needs a boot. The row `QUESTIONS.md` `#6` is not closed by this brief
(`mad-science/TODO.md:455-458`).

## 8. Sources

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