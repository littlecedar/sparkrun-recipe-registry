# Archived DeepSeek V4.1-Flash material (`attic/ds4/`)

This directory holds **archived, not-for-production** DeepSeek V4.1-Flash
material for the `ds4` model family: the retired EXL3/vLLM lane and its
documentation. It was moved out of `recipes/ds4/` when the SGLang knapcio
recipe was chosen for go-live.

## Why it is archived

- **Superseded for go-live.** The shipped recipe is
  `recipes/ds4/deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml` (SGLang, TP=4,
  1M context). It serves the official `deepseek-ai/DeepSeek-V4.1-Flash`
  checkpoint and is faster single-stream than the EXL3 arms here
  (`recipes/README.md` records 46.5 t/s C1 against 40.7 for the EXL3 TP=4 1M
  arm).
- **Kept as load-bearing reference.** The material here is cited by the shipped
  lane and by later work: the measured per-topology numbers, the negative
  results (TP=2 closed, the retired `instanttensor` load path, the `drop-caches`
  and cache-flusher non-findings), the residency / memory analysis of the 203 GB
  Engram, and the DSpark draft-depth (k) sweep.
- **The move is reversible.** Everything was relocated with `git mv` / `git
  rename`; history is intact, so any file can be restored (see below).

## Contents

The retired **EXL3 / vLLM recipes** (all `runtime: vllm`, container
`littlecedar/dgx-spark-dsv41:exl3a`, checkpoint
`bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard`; all five booted and
served, measured 2026-09-24/25/26, retuned 2026-09-27):

- `deepseek-v4.1-flash-exl3-tp3-vllm.yaml` — TP=3, 300K context (3 nodes).
- `deepseek-v4.1-flash-exl3-tp4-vllm.yaml` — TP=4, 300K context (4 nodes).
- `deepseek-v4.1-flash-exl3-tp4-1m-vllm.yaml` — TP=4, 1M context (4 nodes).
- `deepseek-v4.1-flash-exl3-tp6-vllm.yaml` — TP=6, 300K context (6 nodes).
- `deepseek-v4.1-flash-exl3-tp6-1m-vllm.yaml` — TP=6, 1M context (6 nodes).

The documentation:

- `AGENTS.md` — the former consolidated agent/developer guide for the whole ds4
  family. Its EXL3/vLLM content is the bulk of it. Cross-cutting sections that
  are still referenced: the model anatomy (Engram, MXFP4 experts), the
  residency/memory analysis, the DSpark k-sweep, the SGLang lane section, and
  the References.
- `DSPARK-TP3-STUDY.md` — feasibility study for DSpark speculative decoding at
  TP=3 and TP=6, where the drafter's head and expert counts do not divide the TP
  degree. Verdict: feasible; implemented and booted 2026-09-27.
- `MEMORY-RECLAIM-PLAN.md` — host-memory reclaim recommendation. The
  `instanttensor` question is closed (incompatible with this checkpoint) and
  cache drops are not a mitigation.
- `PERF-ISSUES.md` — long-context performance triage of the EXL3 1M arms under
  `sparkrun benchmark performance --profile spark-arena-v2`. Resolved: the
  observed collapse is the cost of a cold deep prefill, not decode starvation.
- `ds4_NOTES.md` — the session working record for the EXL3 lane.

## Status

- Nothing here is wired into `recipes/` any more.
- These recipes are **not validated and not shipped from here**; the registry
  ships the SGLang knapcio recipe only.
- The ds4 guard suite, `tests/test_ds4_recipes.py`, still covers these files as
  frozen regression coverage: its EXL3-lane constants resolve under this
  directory (`ATTIC_DIR`), and the suite passes against them. Restoring a file
  above means editing those constants back to `recipes/ds4/`.

## Restoring a file

```bash
git mv attic/ds4/<file> recipes/ds4/<file>
```

The move is recorded in history; use `git log --follow -- attic/ds4/<file>` (or
`git log --diff-filter=R`) to find the rename and its prior path.