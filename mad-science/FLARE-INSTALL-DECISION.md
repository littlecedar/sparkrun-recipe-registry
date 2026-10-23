# FLARE `gb10` install — the authorization decision (`QUESTIONS.md` `#6`)

**Status:** 2026-10-23, read-only. Nothing installed, no node contacted, no package executed. This memo is
the decision surface for the one act the register leaves open; the analysis and its citations are in
[`FLARE-AGENT-BRIEF.md`](FLARE-AGENT-BRIEF.md) and are not repeated here except where the route choice
depends on them. Section handles below (`[debian.md:…]`, `[gb10:…]`) are the brief's own source table
(§8).

## The ask, in one sentence

Authorize `apt install flare-inference=<pinned version>` plus a per-user `flare agent` on **`.34`/`.35`
only** — version-pinned, key fingerprint confirmed out of band, agent paired by code — to collect the
supply-chain evidence; **not** on `.30`–`.33` while they serve.

That is the brief's §7 verdict restated as an authorization, not a new recommendation. The alternative
answers and their consequences are at the end.

**This is a narrower grant than `#6` as written, and the difference is deliberate.** The row asks whether
the repository and agent may be installed "on four nodes"; this memo asks for two. The reason is the
brief's own §5/§7 reading: `.30`–`.33` serve the fleet's production inference under the `#4` fence, the
agent's Orbit launch binds port 8000 on rank zero — the production serve's own port — and the APT key's
root grant would sit on the serving ranks. Two nodes settle the supply-chain question; four add no
supply-chain evidence and would put a root-capable source on the ranks that must not be disturbed. **A
yes to this memo should be recorded as a two-node authorization, not as an answer to the four-node
wording** — the row's scope needs that amendment when it closes.

## What authorizing it grants, per artifact

| artifact | signed by | what acceptance grants | blast radius |
|---|---|---|---|
| APT repository | Local Inference Lab's RSA-4096 key, uid "Local Inference Lab APT Signing", created 2026-10-20, expires 2028-10-19 | **root on every node that installs or later upgrades** — `dpkg` runs maintainer scripts as root; the current build has none | whole filesystem and every service on that node, including the production serve |
| `.deb` binary | same key; `build-info` records `Source-Commit: bb204798…` and rustc 1.94.1 | code as the **model user** | that user's GPUs, model cache, HF token, ssh keys, `~/.config/flare` |
| runtime package | Ed25519 key in `publisher.json`, namespace `local-inference-lab`, `development: false` | **the compiled kernels and captured graphs executed by the serving process**; the typed namespace is the decryption-key material | GPU and host memory of every serving rank |
| controller key | generated locally on first `flare orbit` | **code execution as the agent's user on every paired node**, and the right to add more controllers | every paired node's model user |
| node pairing | node key + code, or `--accept-first` | the controller's authority over that node | that node |

The two grants that are not recoverable by a container are the **root-capable APT source** and the
**controller key**. Neither is fixed by containerizing the agent, which is why the brief separates "the
supply-chain decision" from "the benchmark's".

## The three containerization frictions, and the route each implies

The brief established that `flare agent` is a per-user systemd *user* unit needing no kernel module, no
root and no capability — so a container is possible in principle. Three frictions decide whether it is
worth it. Each one resolves toward the **native install**:

1. **The arm64 tags are not pinned to the commit the `gb10` package needs.** The registry's x86 card
   names `flare:83d582e2-amd64`; `83d582e2-arm64` does not exist, and arm64 appears only in the
   multi-arch `latest` index and one human tag (`beta-5beb454-arm64`). Every executable must match the
   package's graph contract and RoCE proxy ABI, so a GB10 route through the image means a moving tag or
   building the image ourselves. The arm64 card installs everything, serving included, from APT.
2. **A container has no user manager, so `flare agent install` cannot run inside one.** The documented
   lifecycle is a user unit plus `loginctl enable-linger`; adopting the image means running the agent as
   PID 1 with a restart policy — a shape the vendor never documented or tested — and we would own that
   supervisor thereafter.
3. **`io_uring` is a container-only tax.** Docker's default seccomp profile may block
   `io_uring_setup/enter/register`, which disk-backed Engram needs; on the host there is no seccomp
   filter, so the native route removes the problem rather than mitigating it.

What a container would *not* buy: it is **not a privilege reduction**. `--executable PATH` lets a
controller upload and run code as the agent's user, and that stays true inside a container; the image
also loads the host's `libcuda.so.1`, so the driver coupling remains. The brief's conclusion stands: the
container is a packaging improvement we would own, to replace a systemd unit the vendor supports.

## Preconditions — all four must hold before the first `apt install`

1. **Pin the version.** The repository serves three arm64 builds and `apt` takes the newest, so install
   `flare-inference=0.1.0~git20261021004534.bb204798-1` explicitly. The project's landing page already
   advertises an older build (`5dd67695`) than its index serves, so "latest" is not a version.
2. **Confirm the key out of band.** The fingerprint `22C4 6BE0 A4C3 F708 F74C 1E75 213A 79D3 3E50 FC06`
   is published only on the same host that serves the key and the packages; first trust is otherwise
   trust-on-first-use. Check it through a second channel before accepting.
3. **Prove the build.** Rebuild from `Source-Commit: bb204798880424174143d72bd99648af960970d3` with
   `./scripts/build_deb.sh` and compare hashes — the only step that ties the binary to NVIDIA's source
   rather than to the signer.
4. **Pre-provision the trust store, or expect the prompt.** First use is interactive: the operator types
   the publisher namespace and that string decrypts the executables. A headless launch needs a prepared
   `trust.toml` or both `--dangerously-approve-key FINGERPRINT` and
   `--dangerously-accept-publisher NAMESPACE`.

## What "yes" buys, and what it does not

**Buys:** the acquisition blocker is removed. On two nodes we can settle that the repository, key and
package install and upgrade cleanly; that the agent pairs, survives a reboot under lingering, and
refuses an unauthorized controller; and — after `flare download --revision gb10` on `.34` — the
package's own metadata through `flare inspect PRIMARY --plain` plus a `--dry-run` that verifies
signatures and queries nodes without starting a rank.

**Does not buy:** the `gb10` TP4, c16 and 1M-context claims. The package fixes four ranks and Orbit
cannot re-cut it for fewer hosts, so that boot needs four eligible ranks and waits on the `#4` fence.
Accuracy is unmeasured by the vendor on any card. The node arithmetic leaves ~0.6 GiB before KV, and the
card's concurrency and context claims are "subject to available KV memory".

Authorizing the install therefore does **not** unblock the package's evaluation; it only removes one
step from the `#4` act.

## If the answer is no

`#6` closes negative and the `gb10` artifact stays research-only: no APT acceptance is made, no agent
pairs, and the four-rank cell authorized under `#7` remains unevaluable because its engine cannot be
acquired. The brief's "do not install" reason — refusing to carry a third-party root-capable APT source
on any fleet node — is not addressed by containerizing, so a no is a durable no for this artifact, not a
"later, in a container".

## What would change this recommendation

- **An arm64 image tag pinned to a commit that satisfies the `gb10` package's graph contract and RoCE
  proxy ABI.** That would move the route to the container and remove the APT-root grant.
- **Evidence that the APT build cannot load the `gb10` package at all**, which would send the route back
  through preparation and a self-built image.
