# `attic/explore/` — archived Explore-lane recipes

**What this is.** Every Explore recipe that is **not one of the lane's two selected models**, archived
2026-10-13. `recipes/explore/` now ships exactly two recipes —
`nemotron-3.5-lightning-30b-nvfp4-dspark-vllm.yaml` (rank-1 speed) and `kolibri-1-78b-fp8-vllm.yaml`
(rank-2) — plus its guides, the same production-surface convention the `ds4`/`qwen4` lanes use.
Everything else lives here, **tracked** (so it is never lost) because a `bench_*` id is the provenance
of a result and the recipe file is the convenience for reading what that id ran.

**Why they are here, not in `recipes/explore/`.** `recipes/explore/` is a shipped artifact (distributed
over git to nodes and third parties). The lane's open TODO item ("pick the two overall best models …
and put the rest in the attic") is now resolved: the two selected arms stay, and a measured-but-not-
selected arm or a closed-question variant is clutter there and a hazard to the next reader, who cannot
tell a live recipe from a dead one. See `attic/qwen4/ARMS-MANIFEST.md` for the same policy stated at
length.

**Selection criterion (registry weighting: node count → speed → accuracy → memory).** All four
Explore arms were single-node, so the weighting resolved on speed. Chosen: the fastest arm
(77.7 t/s) and, of the remaining distinct models, the faster one (47.3 t/s ≫ 45.5 t/s) — speed
precedes accuracy, and 47.3 also wins the memory tiebreak (74 GB / util 0.78 vs 154 GB / 0.80).

**Archive criterion.** A recipe came here if it was **measured but not selected** by the ranking above.
Nothing in `recipes/`, `benchmarking/`, `tools/`, or `tests/` names either moved file (checked by
literal grep: the only mentions were the lane docs updated alongside this move), and no test pins
either path — `tests/test_recipe_placeholder_resolution.py` and the repo gate glob `recipes/*/*.yaml`,
which a move simply shrinks. **Do not re-add these to `recipes/explore/`; run them by path from
here.**

## Manifest

| file | runtime | one-line delta | why archived | where its facts now live |
|---|---|---|---|---|
| `nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm.yaml` | vLLM | the shipped 262k recipe verbatim with exactly `max_model_len: 1000000`, `gpu_memory_utilization: 0.91` | A **variant of the kept parent** — same checkpoint, same image, same DSpark draft. Slower (72.2 vs 77.7 t/s) and memory-heavier (util 0.91) than the recipe it duplicates, and its own doc declares "the 262k/0.80 recipe remains the shipped default". Its question (the card's 1M claim) is **closed** and measured. | `recipes/explore/README.md` §"Nemotron-3.5-Lightning — 1M-context arm"; root `recipes/README.md` Explore note. Receipts: `~/benchmarks/nemotron-1m-20261012/` on the head node. |
| `ling-3.0-flash-int4-dspark-sglang.yaml` | SGLang | the Ling-3.0-flash-int4 DSPARK serving recipe (mem-fraction 0.80, 262k window) | **Dominated on the weighting's deciding criterion**: 45.5 t/s vs Kolibri's 47.3 (speed ranks above accuracy), and it is the memory-heaviest Explore arm (154 GB vs 74 GB) — it loses speed *and* memory. Its accuracy edge (37/37 vs 36/37) is carried by Kolibri at its 37/37 union. | `recipes/explore/README.md` §"Ling-3.0-flash-int4" and §"Ling-3.0-flash-int4 — 262k closure". Receipts: `~/benchmarks/ling-needle-20261011/` and `~/benchmarks/ling-262k-20261012/` on the head node. |

Both recipes are **frozen provenance**: do not retune them, and do not clear a
`sparkrun recipe validate` warning by editing them — `attic/` recipes are not part of the registry
gate.

> **Tracking note.** Both recipes and this manifest are tracked and distributed with the registry.
> If a future ranking reverses the call, move the recipe back to `recipes/explore/` and delete its
> row here.

*Archived 2026-10-13 by the Explore selection pass (TODO item "Pick the two overall best models from
the explore lane and put the rest in the `@attic/`").*
