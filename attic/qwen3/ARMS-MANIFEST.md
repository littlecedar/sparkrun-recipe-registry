# `attic/qwen3/` — archived Qwen3 arms and records

Everything here left [`recipes/qwen3/`](../../recipes/qwen3/) on **2026-10-11**, when the lane was
consolidated down to the shipping recipe, the coder recipe, and its two guides (the spec-metrics
guard mod below came from `mods/` the same day). Nothing here is
served by the registry. **Do not re-add these to `recipes/qwen3/`** — run a recipe by path from here
if it is ever needed again. Paired with [`attic/qwen3/AGENTS.md`](AGENTS.md),
which is the maintained guide and holds the distilled findings.

> **2026-10-14.** `recipes/qwen3/AGENTS.md` was removed in the lane consolidation. It now lives here
> as [`attic/qwen3/AGENTS.md`](AGENTS.md) with its `§N` numbering unchanged, and the lane README's
> pre-consolidation body was appended to it verbatim (under `## From recipes/qwen3/README.md
> (2026-10-14)`). Cites of the old `recipes/qwen3/AGENTS.md` path elsewhere resolve to this file.

> **Tracking note.** The recipes, `DEPTH-COST.md`, `SSM-STATE-DTYPE.md`, `ANSWERED-QUEUES.md`, and
> this manifest are tracked and distributed with the registry. `QWEN3-MODEL-OPTIMIZATION-WORK.md`
> and `NOTES.md` match the repo-wide `**/*-WORK.md` ignore rule and stay uncommitted **by design**
> (they are internal working records); they are present in a working tree but absent from a fresh
> clone — `attic/qwen3/AGENTS.md` is the copy that ships. Internal addresses in all of them were
> masked before archiving (`[.NN]` node shorthand, `/home/<operator>/…`); the full addresses live in
> the untracked `.local/CONFIDENTIAL.md`.

## Contents

- [Recipes](#recipes)
- [Mods](#mods)
- [Research record (§N cite-targets; section numbers were not renumbered)](#research-record-n-cite-targets-section-numbers-were-not-renumbered)
- [Benchmarking profiles archived with the lane (2026-10-15)](#benchmarking-profiles-archived-with-the-lane-2026-10-15)

## Recipes

| file | why archived | where its facts now live |
|---|---|---|
| `qwen3.8-27b-nvfp4-nospec-control-sglang.yaml` | Retired 2026-10-10; the plain-decode denominator it exists to produce is measured (12.56 t/s at c=1, 48 granted). | `AGENTS.md` §6 (pairing rule: copy it back into the lane before a spec-vs-nospec run) |
| `qwen3.8-27b-nvfp4-dspark-sglang.yaml` | Measured 2026-10-10 and **rejected**: −16 % vs DFlash2 (28.46 vs 33.76 t/s, decode-triage, d=0/c=1, one free node). The DSpark path boots on GB10; the card's GB300/H200 numbers do not transfer to SM121. | `AGENTS.md` §7. Receipts: `~/benchmarks/qwen3-dspark-20261010/decode-triage.{json,yaml}` on the measuring host |

Both recipes are frozen provenance: do not retune them, and do not clear a `sparkrun recipe
validate` warning by editing them — `attic/` recipes are not part of the registry gate.

## Mods

| file | what it does | why archived |
|---|---|---|
| `mods/fix-sglang-spec-metrics-empty-verify/` | Anchored, idempotent SGLang patch (both sglang trees in the image) so `--speculative-algorithm NONE` cannot crash the server on an empty `spec_verify_ct`; carries its own negative-control harness (`test_spec_metrics_guard.py`) | Moved from `mods/` on 2026-10-11. It served this lane's no-spec control campaign, which is retired above, and the lane's conclusion is to *omit* the speculative flags rather than pass `NONE` (see the control's comments), so no recipe mounts it. It stays the repo's convention exemplar for mod-local guard harnesses (root `AGENTS.md`, Testing & QA) and the precedent cited by the `attic/ifm` K2 guard. |

If a future no-spec arm ever passes `speculative_algorithm: NONE` again, move the mod back to
`mods/` and remove this row; until then the honest no-spec route is omitting the flag entirely.

## Research record (`§N` cite-targets; section numbers were not renumbered)

| file | cite form | what it holds |
|---|---|---|
| `QWEN3-MODEL-OPTIMIZATION-WORK.md` | `WORK §N` | Decision record: the dense-hybrid bandwidth model, the block 4→8 campaign, the pool/clamp analysis, the mamba pool + dtype threads (§12), negative results, and the open-question queue at archive time |
| `DEPTH-COST.md` | `DEPTH-COST §12.NN` | The depth/ratio thread — the `usable = min(cap, #tokens//(depth+pp))` correction (§12.54), the c=8 vs c=4 depth-cost split, retractions marked inline |
| `SSM-STATE-DTYPE.md` | `SSM §12.NN` | The bf16-vs-fp32 recurrent-state probes, the positive control, and the resolution-threshold limits of the claim |
| `ANSWERED-QUEUES.md` | `AQ item N` | Every closed question with its verdict, cost, and why the wrong prediction looked right — **search by benchmark profile name before running anything** |
| `NOTES.md` | — | The lane's action-plan snapshot, drift list, and sprawl log at archive time |

**Archived-with-the-lane:** the two narrative journals (`JOURNAL.md`, `EMBED-JOURNAL.md`) and
`EMBED-*`/`QWEN3-EMBED-OPTIMIZATION-WORK.md` for the VL lanes were already absent from this tree
(git-ignored); their surviving content is in the `recipes/embed/` and `recipes/rerank/` guides.

## Benchmarking profiles archived with the lane (2026-10-15)

Three profiles of the depth-cost / prefill-attribution family in `benchmarking/` belong to the
thread this directory holds (`DEPTH-COST.md` §12) and are cited by no tracked doc, so they moved
(plain `mv`, still tracked) out of the curated library and the `benchmarking/README.md` index was
updated. Note the arm side: their arm of record is the 27B lane's
`qwen3.8-27b-nvfp4-dflash2-sglang` recipe, which is **still shipped** in `recipes/qwen3/` — what was
archived is this lane's records, not the arm.

- `peak-vs-depth.yaml`: moved from benchmarking/ 2026-10-15; served the archived depth-cost thread (no archived arm — the arm of record `qwen3.8-27b-nvfp4-dflash2-sglang` is still shipped).
- `iso-prompt.yaml`: moved from benchmarking/ 2026-10-15; served the archived depth-cost thread (no archived arm — the arm of record `qwen3.8-27b-nvfp4-dflash2-sglang` is still shipped).
- `pp-crossed-identifiability.yaml`: moved from benchmarking/ 2026-10-15; served the archived depth-cost thread (no archived arm — the arm of record `qwen3.8-27b-nvfp4-dflash2-sglang` is still shipped).

Their siblings `pp-slope.yaml`, `pp-vs-depth-acceptance.yaml`, `depth-slope-decode-metric.yaml` and
`iso-kv.yaml` **stayed** in `benchmarking/`: `DEPTH-COST.md` cites the first three by path and names
the `iso-KV` experiment in §12.27, so those paths must keep resolving.