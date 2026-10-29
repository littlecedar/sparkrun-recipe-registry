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
  (`README.md` records 46.5 t/s C1 against 40.7 for the EXL3 TP=4 1M
  arm).
- **Kept as load-bearing reference.** The material here is cited by the shipped
  lane and by later work: the measured per-topology numbers, the negative
  results (TP=2 closed, the retired `instanttensor` load path, the `drop-caches`
  and cache-flusher non-findings), the residency / memory analysis of the 203 GB
  Engram, and the DSpark draft-depth (k) sweep.
- **The move is reversible.** Everything was relocated with `git mv` / `git
  rename`; history is intact, so any file can be restored (see below).

## Contents

- [Why it is archived](#why-it-is-archived)
- [Status](#status)
- [Restoring a file](#restoring-a-file)

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