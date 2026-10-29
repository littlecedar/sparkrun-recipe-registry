# Arch-gate brief — two questions, nothing else

Written 2026-10-29 by the documentation/board session, corrected the same hour
after review: an earlier draft asked you to choose a measurement base for the
flag-level survey arms. **That draft was wrong** — those arms already ran and
closed on 2026-10-26 (see the note at the bottom), so the only thing genuinely
waiting on you is one external kernel gate and one credential.

Answer inline under each question, or reply in chat. Please do not answer inside
a table — tables do not render in your editing mode.

## What is actually blocked

Three rows in `mad-science/queue.json` are `blocked`, and they are one gate plus
its two dependents:

- `arch-deepgemm-sm12x-paged-sparse` — the gate itself. DeepGEMM's paged-sparse
  MQA-logits kernels assert `arch_major == 10` in CUDA source
  (`csrc/apis/attention.hpp:301`), i.e. SM100. GB10 is SM121, so those kernels
  cannot run here at any configuration.
- `w4-survey-arm3-indexer-scoring` — SGLang PR #43401 candidate-only indexer
  scoring (upstream reports −17 % step time at 1M decode on 2×GB10).
- `w4-survey-arm5-trtllm-mla` — TRT-LLM sparse-MLA attention backend
  (`--dsv4-attn-backend trtllm`, 2.26× kernel geomean at C5/C10/128K on GB10).

Both arms ride the candidate-block lineage whose decode path calls that
DeepGEMM family, so neither can be built and measured until the gate lifts. The
lane's earlier c3 re-port verdict (2026-10-26) already failed on this same
assert, and the retained v1-fallback image `dsv41-c3-reconciled:103ad321@sha256:13f686b3…`
is the natural starting point if you want us to attack it rather than wait.

---

## Question 1 — How long does the DeepGEMM SM12x gate stay open?

These are the two highest-upside knobs left in the ds4 lane, and they are walled
behind someone else's kernel code. Options:

**(a)** **Status quo** — leave the three rows open and re-check upstream
releases. Zero work, but the queue carries three rows that look actionable and
are not; this is what has been happening.

**(b)** **Track upstream explicitly** — ask upstream for SM12x support (an issue
or a comment on their tracker), retire our three rows, and re-open from the
tracker when it lands. Closes the rows honestly and puts the request where the
fix would come from.

**(c)** **Build it ourselves** — patch DeepGEMM's arch assert and the sparse
kernels for SM121 in a fork image, starting from the retained v1-fallback build.
Day-scale image project with unknown risk: the assert may be guarding a real
hard-coded assumption (tile shapes, TMA descriptors), in which case patching the
assert becomes writing kernels for a new architecture.

**(d)** **Partial measurement** — run whatever either arm can do *without* the
paged-sparse path and record it as a partial result, explicitly not a survey arm.

**(e)** **Close both arms as not worth it.**

My read: **(b)**, with (c) only if the 17 % / 2.26× numbers justify a day of GPU
work to you. (a) is the worst of the five because it keeps promising work that
cannot start.

Answer:


Blank space for detail:


## Question 2 — The production image is not pullable by anyone outside the fleet

You already approved pushing it and making the package public; what is missing is
a credential, not a decision. `recipes/ds4/` ships
`littlecedar/dgx-spark-dsv41:canary-roce-aff52fa5@sha256:3f448081…`, and on the
fleet that image exists **only as a local tag** — `docker image inspect` reports
no `RepoDigests`, and an anonymous `docker manifest inspect` of the GHCR name
fails — so a third party cloning this registry, or a fresh node, cannot boot the
arm it ships.

The workstation's `gh` token carries `gist`, `read:org`, `repo`, `workflow` — no
`write:packages`. A device authorization is running now and the one-time code is
in this session's reply; entering it at <https://github.com/login/device> grants
the scope. After that the push, the digest pin in `container:`, and an anonymous
pull check from a clean node follow within the hour.

Answer (only if you want a different package name, or non-public visibility after
all):


## Note — why the flag-track arms are not in this brief

They were measured and closed on 2026-10-26 while the main-tree base was in
doubt: candidate 6 `reasoning_effort` high (2.96 % paired output-token saving,
below the 10.6 % precedent — knob wired, 10/10 both arms, no flips), S1
`--enable-cache-report` (FINDING: the radix cache was already reusing; the 8.4 s
revisit reading was a reporting gap), S2 `lpm` (NULL), S3
`--min-free-slots-delay 1` (NEGATIVE on same-line A/B, loses 7–11 %). Verdicts
are recorded at `mad-science/TODO.md:801` with receipts in the lane docs, and
the boots ran on the plain shipped `aff52fa5` arm — so the lineage question was
settled operationally rather than by ruling. If you ever want any of those four
re-measured against a main-tree base, say so and it becomes a new item; it is
not an open question today, and the S0 control boot proved a main-tree base
cannot serve the 1017 at TP=4 at all (MoE divisibility, then a triton-retry GPU
OOM; receipts `~/benchmarks/tp4-window4-20261026/s0-*`).