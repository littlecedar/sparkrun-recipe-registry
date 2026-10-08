# `attic/ifm/` — archived IFM K2-Horizon MoVA-36B-A4B material

**What this is.** The withdrawn `MoVA-36B-A4B` sub-lane of `recipes/ifm/`: its four
recipes (`arms/`), the SGLang gate mod they need (`mods/patch-sglang-k2-horizon-fp8/`),
the lane's own guard suite and byte-arithmetic helper (this directory), and the
sub-lane's git-ignored research record (`K2-36B-A4B-JOURNAL.md`,
`K2-36B-A4B-MODEL-OPTIMIZATION-WORK.md`). The lane's production surface in
`recipes/ifm/` is now the two small dense models only — the `0.9B` and the `7B-FP8`
(plus its NGRAM and Uno arms) — the same convention `attic/ds4/` and `attic/qwen4/`
follow. The arms and the mod are **tracked** (so a `bench_*` id's provenance is never
lost); the two research docs are git-ignored by design (`**/*JOURNAL.md`,
`**/*-WORK.md`), as they are in every other lane, and are carried here only on disk.

**Why they are here, not in `recipes/ifm/`.** This is a **resourcing decision, not a
failure.** The four recipes and the mod were **measured working on hardware on
2026-10-08** (see provenance below) before the owner withdrew the whole sub-lane: at
**18.3 t/s FP8 / 15.6 t/s BF16 single-stream (TP=1)** the 36B is too slow to justify
the compute it consumes — a 48 GB checkpoint synced to every node, and two Sparks per
request for the TP=2 arm — so the feature request was to stop spending nodes on
slow-movers. `recipes/ifm/` is a shipped artifact (distributed over git to nodes and
third parties); a sub-lane nobody runs is clutter there and a hazard to the next
reader, who cannot tell a live recipe from a withdrawn one. The lane's own sprawl
policy already named this outcome (`recipes/ifm/AGENTS.md` §7).

**Archive criterion.** A sub-lane came here if it is **not part of the shipped
production surface** and the owner has withdrawn it. The `zz-` arm is the other,
smaller case: a non-shippable falsification probe whose question closed. Nothing in
`recipes/`, `benchmarking/`, `tools/`, or `tests/` globs `recipes/ifm/*.yaml` in a way
a move breaks; `tests/test_ifm_recipes.py` and `tests/test_k2_7b_recipes.py` guard the
0.9B and 7B recipes and are untouched. **Do not re-add these to `recipes/ifm/`; run
them by path from here** (`sparkrun` runs a recipe by path — `AGENTS.md` §6 shows the
by-path invocation), and note that the FP8 arms' bare `mods/patch-sglang-k2-horizon-fp8`
reference only resolves once the mod is restored beside them (§ recovery footer).

## Manifest

### Wave 1 — the 36B-A4B sub-lane withdrawal (archived 2026-10-08)

All four recipes were live shippable arms in `recipes/ifm/` through the 2026-10-08
hardware session. They are archived now because the owner withdrew the sub-lane as too
slow to justify the compute, *after* they were measured — so their rows record the
numbers, not a failure.

| file | parent | one-line delta | why archived |
|---|---|---|---|
| `arms/k2-horizon-36b-a4b-fp8-tp1-sglang.yaml` | — (default 36B arm) | single-node TP=1, 32K, `--fp8-gemm-backend cutlass` + gate mod | sub-lane withdrawn as too slow for the compute: 18.3 t/s C1 FP8, against a 48 GB sync per node |
| `arms/k2-horizon-36b-a4b-fp8-tp2-sglang.yaml` | fp8-tp1 | 2-node TP=2, 131K, RoCE cross-node allreduce | withdrawn with the sub-lane; also the most expensive arm — two Sparks per request (30.0 t/s) |
| `arms/k2-horizon-36b-a4b-bf16-tp1-sglang.yaml` | fp8-tp1 | BF16 control, **no** gate mod | withdrawn with the sub-lane; and the slower of the two single-node arms (15.6 vs 18.3 t/s) |
| `arms/zz-k2-36b-a4b-fp8-unpatched-probe-sglang.yaml` | fp8-tp1 | falsification arm: `mods: []`, observes the unpatched refusal | **question CLOSED 2026-10-08** — the probe reached the compressed-tensors gate it was written to test and died there; its own header says "record the log line and delete this file" |
| `mods/patch-sglang-k2-horizon-fp8/` | — | relaxes SGLang's two native-K2-Horizon quant gates | exists **only** for this withdrawn FP8 checkpoint; no other recipe mounts it |
| `test_ifm_36b_recipes.py` | — | the 36B lane's guard suite (invariants I1–I17) | guards the archived arms; kept so the invariants still resolve, no longer auto-discovered by `unittest discover -s tests` |
| `k2_36b_arith.py` | — | exact byte census + roofline arithmetic the arms' prose quotes | imported by the guard above; kept beside it so the import stays self-consistent |

## Provenance notes

- **Measured working on hardware, 2026-10-08** (first 36B boots, two nodes,
  `lmsysorg/sglang:v0.5.20-cu130` digest-pinned), at c=1 via
  `benchmarking/decode-triage.yaml` (tg=128, 5 runs), `tg t/s` read from the per-cell
  JSON and not the printed table: **FP8 TP=1 18.3 / 16.3; BF16 TP=1 15.6 / 14.1;
  FP8 TP=2 30.0 / 27.0** (d0 / d8k). The withdrawal is about the number, not a broken
  recipe. Full narrative: `K2-36B-A4B-JOURNAL.md`, 2026-10-08.
- **These arms were unbootable as shipped until the same session.** Every MoVA
  checkpoint is refused at `srt/models/xllm.py:204` unless the recipe passes
  `--json-model-override-args '{"xllm_source_router_gemm_partitions": 2}'` as a
  **literal** in `command:`; the four archived recipes all carry it, and guard `I17`
  pins it. Do not "simplify" it back into a `defaults:` key — `json_model_override_args`
  is absent from sparkrun's `_SGLANG_FLAG_MAP`, so it would be dropped silently.
- **The mod is justified, not speculative.** On 2026-10-08 the probe's re-run died at
  the gate `mods/patch-sglang-k2-horizon-fp8` relaxes (`xllm.py:665`), and the FP8 arm
  boots *only* because of it. It is archived because it serves no live recipe now, not
  because it was wrong.
- **The lane's research record is here too**, on disk only: the two docs above are
  git-ignored (`**/*JOURNAL.md`, `**/*-WORK.md`) exactly as the 0.9B/7B lane keeps
  theirs, so they are **never** `git add`ed. The guard's `FilesExist.test_docs_present`
  skips when they are absent (fresh clone) and requires them when present.
- **The lane keeps its small models.** `k2-horizon-0.9b-bf16-sglang.yaml` and the three
  `k2-horizon-7b-fp8-*` recipes stay in `recipes/ifm/` with their own guards
  (`tests/test_ifm_recipes.py`, `tests/test_k2_7b_recipes.py`). Only the 36B sub-lane
  moved.
- **Path constants inside the moved files were repointed** to `attic/ifm/`
  (`RECIPE_DIR`, `MOD_DIR`, the module docstrings, the docs-present check). The
  archived recipes and the mod still carry the pre-move `recipes/ifm/…` and
  `mods/…` comments — that is deliberate, because they are only runnable again after
  being moved back.

*Archived 2026-10-08 by the withdrawal session. If you resurrect any of this, move the
recipes back to `recipes/ifm/` **and** `attic/ifm/mods/patch-sglang-k2-horizon-fp8/`
back to `mods/`, restore the path constants above, and remove the row here.*