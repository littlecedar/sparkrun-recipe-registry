# Upstream memo — knapcio/DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4, delta after our pin

**Date:** 2026-10-10 · **Scope:** everything after pin `58f2321` · **Method:** fresh `git clone` of
upstream (HEAD readout `fa13563`), full `git log`/`git diff 58f2321..HEAD`, plus GitHub API
corroboration (`/commits`, `/releases`).

## Headline (corrects the earlier scan's premise)

**Our pin `58f2321` IS the v2.3 release commit** — `docs: v2.3 results (fresh-clone gate, 2200 MHz
cap)`, 2026-09-29T15:09:02Z, whose parent is the v2.3 candidate **code** commit `5f11a97`
(`adapter/cert_head.py`, `replay_guard.py`, gates). The v2.2/v2.3 "throughput work" and the
"do not use NVFP4 on GB10" verdict are therefore **already at (or before) our pin**, not past it.

**Only TWO commits exist after the pin, both 2026-10-09, both documentation-only.** There is
**no v2.4**, **no tag**, **no GitHub release** (`/releases` → `[]`), and history is linear (API
confirms `4e70a6c.parent = 58f2321`, `fa13563.parent = 4e70a6c`) — no force-push, no rewrite.

`git diff --stat 58f2321..HEAD` touches exactly five files:

```
.env.tp4.example               |  43 ++++++++--
README.md                      |  24 ++++++-
docs/chunked-prefill-memory.md |   5 ++
docs/community-results.md      |  16 ++
docs/switchless-ring.md        | 123 ++++++++++++++++++--
```

`git diff --stat 58f2321..HEAD -- Dockerfile.canary-roce Dockerfile scripts/ adapter/ boot.py
runtime/` is **empty**. Zero changes to `boot.py`, the adapter overlay, the b12x/b12x_next
kernels, the Dockerfile, or the SGLang-pin script (`scripts/fetch-sglang-canary.sh`, still stages
`dsv4.1 @ f80c91a4b`). **Nothing in the delta can change a served number.**

## The two post-pin commits

| SHA | Date | Subject | Files |
|---|---|---|---|
| `4e70a6c` | 2026-10-09 | docs: host prerequisites, download step, patched NCCL and ring addressing | `.env.tp4.example`, `README.md`, `docs/chunked-prefill-memory.md`, `docs/switchless-ring.md` |
| `fa13563` | 2026-10-09 | docs: bring-up pitfalls, ring recovery notes, results from other fleets | `.env.tp4.example`, `README.md`, `docs/community-results.md` (new), `docs/switchless-ring.md` |

Both are prose ports of Saolence's first-deployer review (#3/#4, closed unmerged) and other
fleets' field reports.

## Per-change adopt / reject / defer

| # | Change | Verdict | Why |
|---|---|---|---|
| 1 | `.env.tp4.example` — example `IB_HCA` value corrected to `rocep1s0f0,roceP2p1s0f0`, "names are host-specific" | **Reject** (already covered, better) | Our launcher deliberately sets no `NCCL_IB_HCA`/`B12X_ROCE_HCA`; sparkrun's IB probe fills them (ds4 `AGENTS.md` §6) |
| 2 | `.env.tp4.example` — documents `EP_SIZE=4` does not boot with `DSV41_MOE_B12X_NEXT` | **Reject** (corroboration only) | We ship `EP_SIZE=1`; §11 already records EP>1 dies at decode |
| 3 | `.env.tp4.example` — `DSV41_CACHE_GIB=0` trade-off note: "one ring fleet reported +9% KV pool and +1.5 GiB MemAvailable… not re-measured here" | **Defer** | Testable idea, third-party report only; would need our own A/B |
| 4 | `.env.tp4.example` — `HF_REPO`/`HF_REVISION`/`EXPECTED_SHARDS=48` documented | **Reject** (no delta) | `HF_REVISION=fb2764a5…` matches `boot.py:24 REVISION` already at our pin |
| 5 | `.env.tp4.example` — Engram pack size "~68 → ~48 GiB/node at TP4 (measured)" | **Reject** (cosmetic) | Size figure correction; no config impact |
| 6 | `.env.tp4.example` — `SGLANG_RUST_BUILD_MODE=never` cargo-probe hang workaround vars | **Defer** | Keep in back pocket for a boot hang; not our boot path |
| 7 | `README.md` — host prerequisites + `./start-tp4.sh download` step | **Reject** (not applicable) | sparkrun owns distribution; MiaAI-Lab `start.sh` is not our launcher |
| 8 | `docs/*` — ring recovery notes, community results | **Informational** | Field reports from other fleets; useful context, nothing to adopt |

## Recommendation

**No rebuild, no re-pin.** The shipped lane is already at the upstream code frontier; the delta
cannot change a served number. The two *defer* items are independent experiments (a `CACHE_GIB=0`
A/B and a cargo-hang workaround), not reasons to bump the image.
