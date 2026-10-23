# QUESTIONS — the register of owner questions (2026-10-22)

This file holds the **unresolved** questions only — `open` and `blocked on hardware` — one row each, with
the provenance that raises it. **Settled (answered) questions live in `TODO.md` §"Settled questions"**, which
carries the answer and the rationale verbatim; row numbers are stable across both files, so a citation such
as `QUESTIONS.md #9` still resolves through that record, and a settled question is never re-opened.

| summary | value |
|---|---|
| unanswered | **4** — 1 open (`#6`) and 3 blocked (`#2`, `#3`, `#7`); the three blocked rows wait on the `.30`–`.33` ranks the settled `#4` fenced, and all four are counted from the status column |
| settled | **12, moved to `TODO.md` §"Settled questions" on 2026-10-23** — `#1`, `#4`, `#5`, `#8`–`#16`, verbatim with their numbers, provenance and asked dates |
| blocks the most downstream work | **`#6`** — the only open question: the FLARE `gb10` supply-chain authorization is the one artifact whose target is this fleet's exact four-Spark shape, and its owner-requested mechanism brief (`e1c32a2`) and install memo (`1db2090`) are folded into **`mad-science/FLARE.md`**, so the one act left is the install authorization |

## Baseline & gate

| # | question | status | why it matters | provenance | asked |
|---|---|---|---|---|---|
| 2 | Is a quartet boot worth spending on a larger 1M prefill chunk than the shipped 8192? → **Answered 2026-10-22:** only after `#4` is settled — and `#4` settled the fence holding, so the experiment waits until the owner stands the production serve down | blocked on hardware | The measured 1.67× 1M penalty is chunk-launch-bound rather than compute- or bandwidth-bound, so the chunk size is the only lever left on 1M prefill throughput — and it needs four ranks, i.e. the `#4` act. | `mad-science/STATUS.md:33` | 2026-10-22 |
| 3 | Will a quartet window be scheduled for one engine booted at both TP=2 and TP=4 in interleaved A/B slots? → **Answered 2026-10-22:** **queue behind the fence** — the window is queued, and runs only after the owner stands the production serve down | blocked on hardware | Every published TP=2-vs-TP=4 ratio in the DeepSeek family compares two different engines and quants at once; without the window the family has no controlled topology number, and the answer makes it a queued item rather than an open scheduling ask. | `mad-science/DEEPSEEK-1017-DECODE-RESEARCH.md:234-236` (bound stated `:20-22`) | undated |

## Hardware & authorization

| # | question | status | why it matters | provenance | asked |
|---|---|---|---|---|---|
| 6 | May a third-party APT repository and a per-host `flare agent` service be installed on four nodes to evaluate the FLARE `gb10` package? → **Brief delivered 2026-10-22 (`e1c32a2`); the question stays open on the install, which is not decided.** `mad-science/FLARE.md` answers what `flare agent` is — a per-user systemd *user* unit that needs no kernel module, no root and no capability, so it is **containerizable in principle**, and TP collectives do not ride on it — and why the container is still not the route (§4): the vendor serve image's **amd64-only human tags**, the user-unit + lingering lifecycle, and disk-Engram's `io_uring`, which Docker's default seccomp profile blocks. It also splits the provenance the decision turns on: the **engine is NVIDIA's Apache-2.0 research prototype**, while the `.deb`, the APT repository and the weights are **Local Inference Lab's** — so the repository key is root on any node that later runs `apt upgrade`. Its §5 asks for **`.34`/`.35` only** — a two-node authorization, not the four-node wording, because `.30`–`.33` serve under the `#4` fence and an Orbit launch there would bind the production serve's own port 8000. No install and no node contact: the `.deb` was read, not executed, and GB10/arm64 behaviour plus the package's ABI match stay unverified | open — the install authorization is the remaining act | It is the only artifact seen whose target is this lane's exact shape (four Sparks, TP4, c16, 1M context), and it cannot be served at all without that supply-chain step; `mad-science/FLARE.md` §5 is the authorization the owner reads, and it is now available | `mad-science/FLARE.md` §5 (the authorization ask) and §4 (why a container is not the route), `mad-science/TODO.md` §ds4 | 2026-10-22 |
| 7 | Is a four-rank MiniMax-H3 video cell authorized on `.30`–`.33`? → **Answered 2026-10-22:** **authorize, fence-gated** — authorize it to be queued; it may displace the serving ranks only once the fence lifts | blocked on hardware | The 33.12 B DiT's per-step activation exchange may need TP=2 or TP=4, so the authorization is what lets the cell be planned, while the fence keeps it from displacing the fleet's production serve — the same one-act dependency as `#2` and `#3`. | `mad-science/TODO.md:2267` | 2026-10-22 |
