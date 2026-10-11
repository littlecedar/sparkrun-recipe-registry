# `attic/qwen3/` — archived Qwen3 arms and records

Everything here left [`recipes/qwen3/`](../../recipes/qwen3/) on **2026-10-11**, when the lane was
consolidated down to the shipping recipe, the coder recipe, and its two guides. Nothing here is
served by the registry. **Do not re-add these to `recipes/qwen3/`** — run a recipe by path from here
if it is ever needed again. Paired with [`recipes/qwen3/AGENTS.md`](../../recipes/qwen3/AGENTS.md),
which is the maintained guide and holds the distilled findings.

> **Tracking note.** The recipes, `DEPTH-COST.md`, `SSM-STATE-DTYPE.md`, `ANSWERED-QUEUES.md`, and
> this manifest are tracked and distributed with the registry. `QWEN3-MODEL-OPTIMIZATION-WORK.md`
> and `NOTES.md` match the repo-wide `**/*-WORK.md` ignore rule and stay uncommitted **by design**
> (they are internal working records); they are present in a working tree but absent from a fresh
> clone — `recipes/qwen3/AGENTS.md` is the copy that ships. Internal addresses in all of them were
> masked before archiving (`[.NN]` node shorthand, `/home/<operator>/…`); the full addresses live in
> the untracked `.local/CONFIDENTIAL.md`.

## Recipes

| file | why archived | where its facts now live |
|---|---|---|
| `qwen3.8-27b-nvfp4-nospec-control-sglang.yaml` | Retired 2026-10-10; the plain-decode denominator it exists to produce is measured (12.56 t/s at c=1, 48 granted). | `AGENTS.md` §6 (pairing rule: copy it back into the lane before a spec-vs-nospec run) |
| `qwen3.8-27b-nvfp4-dspark-sglang.yaml` | Measured 2026-10-10 and **rejected**: −16 % vs DFlash2 (28.46 vs 33.76 t/s, decode-triage, d=0/c=1, one free node). The DSpark path boots on GB10; the card's GB300/H200 numbers do not transfer to SM121. | `AGENTS.md` §7. Receipts: `~/benchmarks/qwen3-dspark-20261010/decode-triage.{json,yaml}` on the measuring host |

Both recipes are frozen provenance: do not retune them, and do not clear a `sparkrun recipe
validate` warning by editing them — `attic/` recipes are not part of the registry gate.

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