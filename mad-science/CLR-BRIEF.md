# Control-lineage and arch-gate brief — answers wanted

Written 2026-10-29 by the documentation/board session. Five tasks in
`mad-science/queue.json` are `blocked`, and all five are blocked on a decision
rather than on work: two need you to choose a measurement lineage, three wait on
someone else's kernel code. Nothing below is a request to spend node time today —
each answer only unblocks a queue row.

Answer inline under each question, or reply in chat; either is fine. Please do
not answer inside a table — tables do not render in your editing mode.

## Background, in one paragraph

The ds4 lane's remaining work is a **flag-level survey** of the 1017 checkpoint:
three cheap knobs (candidate 1 `--min-free-slots-delay`, candidate 2 prefix-cache
truth via `--enable-cache-report` + `lpm`, candidate 6 `reasoning_effort` high)
and two builds (candidate 3 indexer scoring from SGLang PR #43401, candidate 5
the TRT-LLM sparse-MLA backend). The survey's whole design was to measure those
knobs on a **main-tree base image** and compare against the shipped arm's control
numbers, so a delta could be attributed to the knob rather than to the base.

That design died on 2026-10-26: the control boot of the stock main tree
(`recipes/ds4/zz-ds4-1017-main-tree-sglang.yaml`) **ran NEGATIVE** — the stock
tree cannot serve the 1017 checkpoint on GB10 at TP=4 with any in-arm MoE backend
(the default `Mxfp4FlashinferCutlassMoEMethod` rejects the per-partition expert
width, 2304/TP4 = 576, not a multiple of 128), and the authorized one-shot retry
with `--moe-runner-backend triton` died 16 s into weight load with an NVRM GPU
OOM. Receipts: `~/benchmarks/tp4-window4-20261026/s0-stock-tree-rank0-serve.log`,
`s0-retry-node{1..4}-serve.log`, `s0-launch.log`, `s0-retry-launch.log`. This
matches the shipped lane's own finding that the vendored pad/adapter set is
load-bearing for boot, not a convenience (`recipes/ds4/README.md`).

The other three rows are the arch gate: the candidate-3 and candidate-5 decode
paths both call DeepGEMM's paged-sparse logits family, whose CUDA source asserts
`arch_major == 10` (`csrc/apis/attention.hpp:301`). GB10 is SM121, so those
kernels cannot run here at all until upstream DeepGEMM ships SM12x support.

---

## Question 1 — Which base line should the flag-level arms measure against?

The three flag-level arms (candidates 1, 2, 6) are unbuildable on main-tree, so
they need a base the fleet can actually boot. Options as I see them:

**(a)** Fall back to the **shipped knapcio canary image** and compare against its
own shipped control numbers. Cheapest — the image is already on every node and
the numbers exist (`recipes/ds4/README.md` §Measured) — but the control and the
arm would come from different windows, so a small delta is arguable.

**(b)** Same fallback, but **re-measure the control in the same window** as each
arm (a same-build A/B/A/B). Honest attribution, costs roughly one extra
knapcio-class boot per arm (~45–60 min TTR each) on the quartet.

**(c)** **Hold the survey** until a main-tree base can boot the 1017, which means
re-porting the pad/adapter set into a main-tree build — a build project, not a
flag test, and it re-opens the adapter chain that the owner closed as terminal.

**(d)** **Drop the flag-level survey** entirely; ship the arm as-is.

My read: (b) if the knobs are worth the node time, (d) if they are not. (a) is
the tempting one and the one I would not choose — it invites a lineage argument
over every percentage point.

Answer:


Blank space for detail:


## Question 2 — How long does the DeepGEMM SM12x gate stay open?

Candidate 3 (indexer scoring, upstream −17 % step time at 1M decode on 2×GB10)
and candidate 5 (TRT-LLM sparse-MLA, 2.26× kernel geomean at C5/C10/128K on GB10)
are the two highest-upside knobs left in the lane, and both are walled behind a
kernel that asserts SM100 in CUDA source. Options:

**(a)** **Status quo** — leave all three rows open and re-check upstream releases.
Zero work, but the queue carries three dead-looking rows indefinitely.

**(b)** **Track upstream explicitly** — ask upstream for SM12x support (an issue
or a comment on their tracker) and retire our rows until it lands; re-open from
the tracker when it ships. Closes the rows honestly and puts the ask where the
fix would come from.

**(c)** **Build it ourselves** — patch DeepGEMM's arch assert and the sparse
kernels for SM121 in a fork image, starting from the retained v1-fallback build
(`dsv41-c3-reconciled:103ad321@sha256:13f686b3…`). This is a day-scale image
project with unknown risk: the assert may be catching a real hard-coded
assumption (tile shapes, TMA descriptors), in which case "patching the assert"
turns into writing kernels for a new architecture.

**(d)** **Partial measurement** — run whatever of the two arms works without the
paged-sparse path, and record it as a partial result rather than a survey arm.

My read: (b), with (c) only if the 17 %/2.26× numbers are worth a day of GPU work
to you. (a) is what we have been doing and it is the worst of the three because
the rows keep looking actionable.

Answer:


Blank space for detail:


## Question 3 — The production image is not pullable by anyone outside the fleet

Not a choice about work, but it needs your hands. `recipes/ds4/` ships
`littlecedar/dgx-spark-dsv41:canary-roce-aff52fa5@sha256:3f448081…`, and that
image exists **only** as a local tag on fleet nodes: `docker image inspect`
reports no `RepoDigests`, and an anonymous `docker manifest inspect` of the GHCR
name fails. So a third party cloning this registry, or a fresh node, cannot boot
the arm it ships.

You approved pushing it and making the package public. That needs a GitHub token
with `write:packages`, which the workstation's `gh` token does not have
(`gist`, `read:org`, `repo`, `workflow`). A device authorization is running now;
the one-time code is in this session's reply. Entering it at
<https://github.com/login/device> completes the grant, and the push, the digest
pin in the recipe, and an anonymous pull check from a clean node follow
immediately.

Answer (only if you want a different package name or non-public visibility):


## What each answer unblocks

Question 1 governs `w4-candidate6`, `w4-s1`, `w4-s2`, `w4-s3` (all currently
`blocked` with the control-lineage reason). Question 2 governs
`arch-deepgemm-sm12x-paged-sparse` plus `w4-survey-arm3-indexer-scoring` and
`w4-survey-arm5-trtllm-mla`. Question 3 governs nothing in the queue except
`ds4-shipped-container-digest-pin`, which is 0.5 h of work once the credential
exists.