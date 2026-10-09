# `attic/ifm/` — archived IFM K2-Horizon material

**What this is.** The withdrawn and retired pieces of the `recipes/ifm/` lane, kept
here. **Wave 1** is the withdrawn `MoVA-36B-A4B` sub-lane: its four recipes (`arms/`),
the SGLang gate mod they need (`mods/patch-sglang-k2-horizon-fp8/`), the sub-lane's own
guard suite and byte-arithmetic helper (this directory), and the sub-lane's git-ignored
research record (`K2-36B-A4B-JOURNAL.md`, `K2-36B-A4B-MODEL-OPTIMIZATION-WORK.md`).
**Wave 2** is the retired 7B spec-decode arms (`arms/k2-horizon-7b-fp8-sglang.yaml`,
`arms/k2-horizon-7b-fp8-ngram-sglang.yaml`) — a selection archive, not a withdrawal
(see below). The lane's production surface in `recipes/ifm/` is now the `0.9B` and the
single shipped 7B arm `k2-horizon-7b-fp8-uno-sglang` — the same convention `attic/ds4/`
and `attic/qwen4/` follow. The arms and the mod are **tracked** (so a `bench_*` id's
provenance is never lost); the two Wave 1 research docs are git-ignored by design
(`**/*JOURNAL.md`, `**/*-WORK.md`), as they are in every other lane, and are carried
here only on disk.

**Why the Wave 1 material is here, not in `recipes/ifm/`.** This is a **resourcing decision, not a
failure.** The four recipes and the mod were **measured working on hardware on
2026-10-08** (see provenance below) before the owner withdrew the whole sub-lane: at
**18.3 t/s FP8 / 15.6 t/s BF16 single-stream (TP=1)** the 36B is too slow to justify
the compute it consumes — a 48 GB checkpoint synced to every node, and two Sparks per
request for the TP=2 arm — so the feature request was to stop spending nodes on
slow-movers. `recipes/ifm/` is a shipped artifact (distributed over git to nodes and
third parties); a sub-lane nobody runs is clutter there and a hazard to the next
reader, who cannot tell a live recipe from a withdrawn one. The lane's own sprawl
policy already named this outcome (`recipes/ifm/AGENTS.md` §7).

**Archive criterion.** A piece came here if it is **not part of the shipped production
surface**: Wave 1 was withdrawn by the owner, Wave 2 lost a selection comparison
(below). The `zz-` arm is the other, smaller case: a non-shippable falsification probe
whose question closed. `tests/test_ifm_recipes.py` guards the 0.9B recipe;
`tests/test_k2_7b_recipes.py` **does** resolve `recipes/ifm/*.yaml` (it globs that
directory and names the 7B arm paths), so the 2026-10-09 move required repointing it
to read the two Wave 2 arms by path from here; `benchmarking/` and `tools/` reference
nothing under `recipes/ifm/`.
**Do not re-add these to `recipes/ifm/`; run them by path from here** (`sparkrun` runs a
recipe by path — `AGENTS.md` §6 shows the by-path invocation), and note that the FP8
arms' bare `mods/patch-sglang-k2-horizon-fp8` reference only resolves once the mod is
restored beside them (§ recovery footer).

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

### Wave 2 — the IFM 7B consolidation (archived 2026-10-09)

`recipes/ifm/` was consolidated to a single shipped 7B arm. These two were live
shippable arms through the 2026-10-09 hardware session and lost the best-overall
comparison against the kept UNO arm (`recipes/ifm/k2-horizon-7b-fp8-uno-sglang.yaml`) —
so this is a **selection** archive, not a withdrawal for cost like Wave 1. Each row
records its measured numbers and why it did not win.

| file | parent | one-line delta | why archived |
|---|---|---|---|
| `arms/k2-horizon-7b-fp8-sglang.yaml` | — (plain dense 7B baseline) | TP=1, 131K, `flashinfer`, **no mods**; measured 21.2 / 19.2 t/s C1 d0/d8k; carries the 512K BF16-KV proof `bench_6518bc429d05` | dominated by both spec arms — same API and checkpoint, +31 %/+49 % given away to NGRAM and +52 %/+41 % to the kept UNO arm |
| `arms/k2-horizon-7b-fp8-ngram-sglang.yaml` | k2-horizon-7b-fp8-sglang | NGRAM spec decode, **no draft weights**; measured 27.9 / 28.6 t/s C1 d0/d8k | slower than the kept arm at d0 (27.9 vs 32.4) and at c=8 aggregate (123.9/88.3 vs 145.5/90.2); its only edge, single-stream d8k 28.6 vs 27.1, sits inside the lane's own 7-25 % inter-boot noise floor |

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
- **What stays shipped.** `recipes/ifm/` now holds `k2-horizon-0.9b-bf16-sglang.yaml`
  and the single 7B arm `k2-horizon-7b-fp8-uno-sglang.yaml`, guarded by
  `tests/test_ifm_recipes.py` and `tests/test_k2_7b_recipes.py` respectively. The other
  two `k2-horizon-7b-fp8-*` arms moved here in Wave 2; the 36B sub-lane moved in Wave 1.
- **Path constants inside the moved files were repointed** to `attic/ifm/`
  (`RECIPE_DIR`, `MOD_DIR`, the module docstrings, the docs-present check), and
  `tests/test_k2_7b_recipes.py` was repointed to read the Wave 2 arms by path here. The
  archived recipes and the mod still carry the pre-move `recipes/ifm/…` and
  `mods/…` comments — that is deliberate, because they are only runnable again after
  being moved back. The two Wave 2 arms likewise keep their pre-move comments verbatim
  (sibling filenames, `AGENTS.md`, `WORK §` and lane-doc cross-references) for the same
  reason.

- **The 2026-10-09 crash-recovery handoff** (`IFM-RECOVERY-2026-10-09-WORK.md`)
  was a *session* handoff, explicitly **not** lane documentation, and its plan has
  closed: the instrument repair, the accuracy re-measure, the arm sweep and the UNO
  promotion all landed, and its durable content lives in `recipes/ifm/NOTES.md` and
  `recipes/ifm/COOP.md`. Per its own header it has been removed from the tree
  (kept only in the author's git-ignored `.local/`), so this manifest no longer
  points at an absent file.

*Archived 2026-10-08 (Wave 1 withdrawal) and 2026-10-09 (Wave 2 selection). If you
resurrect any of this, move the recipes back to `recipes/ifm/` **and**
`attic/ifm/mods/patch-sglang-k2-horizon-fp8/` back to `mods/`, restore the path
constants above, and remove the row here.*