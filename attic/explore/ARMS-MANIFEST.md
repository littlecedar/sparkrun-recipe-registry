# `attic/explore/` — archived Explore-lane recipes

**What this is.** Every Explore recipe that is **not one of the lane's two selected models**, archived
2026-10-13. `recipes/explore/` now ships exactly two recipes —
`ling-3.0-flash-int4-dspark-sglang.yaml` (rank-1 accuracy) and `kolibri-1-78b-fp8-vllm.yaml` (rank-2,
near-tie accuracy, smaller + faster) — plus its guides, the same production-surface convention the
`ds4`/`qwen4` lanes use. Everything else lives here, **tracked** (so it is never lost) because a
`bench_*` id is the provenance of a result and the recipe file is the convenience for reading what
that id ran.

**Why they are here, not in `recipes/explore/`.** `recipes/explore/` is a shipped artifact (distributed
over git to nodes and third parties). The lane's open TODO item ("pick the two overall best models …
and put the rest in the attic") is now resolved: the two selected arms stay, and a measured-but-not-
selected arm or a closed-question variant is clutter there and a hazard to the next reader, who cannot
tell a live recipe from a dead one. See `attic/qwen4/ARMS-MANIFEST.md` for the same policy stated at
length.

**Selection criterion (owner decision 2026-10-13, `mad-science/TODO.md` `#DECISIONS`).** For the explore
lane the deciding factor is **accuracy, with preference for smaller and faster models** — supersedes the
registry's node-count→speed default, which had ranked this lane on speed and had decided the earlier
pass's rank-2 call on a 1.8 t/s gap that sat inside Ling's own σ (5.5). Ranking the four arms by it:

| rank | arm | accuracy | memory | C1 t/s | outcome |
|---|---|---|---|---|---|
| 1 | `ling-3.0-flash-int4-dspark-sglang` | **37/37** | 154 GB | 45.5 | **KEPT** — accuracy champion |
| 2 | `kolibri-1-78b-fp8-vllm` | 36/37 (**37/37 union** — the lone miss is a thinking-budget truncation) | 74 GB | 47.3 | **KEPT** — near-tie on the deciding factor, and it wins the stated preference (smaller and faster) |
| 3 | `nemotron-3.5-lightning-30b-nvfp4-dspark-vllm` | 33/37 | 21 GB | 77.7 | archived — the fastest measured arm and the smallest, but the lane's **lowest accuracy** |
| — | `nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm` | 33/37 | 21 GB / 0.91 | 72.2 | archived — a variant of the 262k recipe (same checkpoint, image and DSpark draft); its question (the card's 1M claim) is closed |

**Archive criterion.** A recipe came here if it was **measured but not selected** by the ranking above.
Nothing in `recipes/`, `benchmarking/`, `tools/`, or `tests/` names the moved files (checked by literal
grep), and no test pins either path — `tests/test_recipe_placeholder_resolution.py` and the repo gate
glob `recipes/*/*.yaml`, which a move simply shrinks. **Do not re-add these to `recipes/explore/`; run
them by path from here.**

## Manifest

| file | runtime | one-line delta | why archived | where its facts now live |
|---|---|---|---|---|
| `nemotron-3.5-lightning-30b-nvfp4-dspark-vllm.yaml` | vLLM | the lane's original shipped default; the fastest measured Explore arm (77.7 t/s @ d0) and the smallest (21 GB / 0.80) | **Lowest accuracy in the lane (33/37, identical miss set reproduced 2026-10-13)** — it pays ~4 quality tasks for its speed, and the owner's criterion makes accuracy the deciding factor. | `recipes/explore/README.md` §"Measured" (the Nemotron bullets); root `recipes/README.md` Explore note. Receipts: `~/benchmarks/explore-tp1-20261013/`. |
| `nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm.yaml` | vLLM | the 262k recipe verbatim with exactly `max_model_len: 1000000`, `gpu_memory_utilization: 0.91` | A **variant of the now-archived 262k arm** (same checkpoint, image and DSpark draft); slower (72.2 t/s), memory-heavier (0.91), and its question (the card's 1M claim) is closed. | `recipes/explore/README.md` §"Nemotron-3.5-Lightning — 1M-context arm". Receipts: `~/benchmarks/nemotron-1m-20261012/`. |

The archived recipes are **frozen provenance**: do not retune them, and do not clear a
`sparkrun recipe validate` warning by editing them — `attic/` recipes are not part of the registry
gate.

> **Tracking note.** Both recipes and this manifest are tracked and distributed with the registry.
> If a future ranking reverses the call, move the recipe back to `recipes/explore/` and delete its
> row here.

*Archived 2026-10-13 by the Explore selection pass (TODO item "Pick the two overall best models from
the explore lane and put the rest in the `@attic/`"); re-ranked 2026-10-13 by the owner's accuracy
decision.*
