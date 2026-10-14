# GLM 5.3 lane

**This lane ships no recipe.** It is a **runbook + research archive**: two GLM-5.3 serving lines were
boot-verified on this cluster, and a third was attempted and archived as a proven-negative — but none
is a registry recipe, so nothing here is served by sparkrun. Its one recipe was archived 2026-10-13.

## Contents

- [Status](#status)
- [Boot-verified serving lines](#boot-verified-serving-lines)
- [Licence](#licence)
- [Runbook notes and revision pins](#runbook-notes-and-revision-pins)
- [Revision pins](#revision-pins)
- [Attic index](#attic-index)

## Status

- **No shipped recipe.** The lane's single recipe, `glm-5.3-flash-nvfp4-dflash-vllm.yaml`, was
  **archived 2026-10-13** to [`attic/glm/`](../../attic/glm/ARMS-MANIFEST.md) as a proven-negative
  arm (owner decision): it is repo B's independently validated TP=4 formula, image- and
  checkpoint-pinned, but the pinned public image blocks it (its SM120 sparse-MLA backend forces an
  `fp8_ds_mla` KV layout the NoPE-MLA checkpoint cannot use). Do not re-add it without a public image
  that can serve this checkpoint. Full rationale: [`attic/glm/ARMS-MANIFEST.md`](../../attic/glm/ARMS-MANIFEST.md),
  [`attic/glm/AGENTS.md`](../../attic/glm/AGENTS.md#from-recipesglmreadmemd-2026-10-14).
- **Runbook-only serving lines.** Both live lines below are external launchers, not sparkrun recipes:
  the multi-node prepare/ssh/topology logic is not expressible in the recipe schema, and one engine is
  an unreleased fork branch installed editable at container start.
- **Research** (checkpoint/engine/topology selection, measured numbers, licence traps) is in
  [`attic/glm/GLM-5.3-RECOMMENDATIONS.md`](../../attic/glm/GLM-5.3-RECOMMENDATIONS.md).

## Boot-verified serving lines

One line each; full operator detail (serve commands, host overrides, receipts) is in
[`attic/glm/AGENTS.md`](../../attic/glm/AGENTS.md).

- **EXL3 3.0bpw / TensorFold, TP=4 (full 753B)** — **BOOT-VERIFIED 2026-10-13** on `.30`–`.33`; repo
  A's `bertholomus/glm-5.3-tensorfold-tp4-4xgb10` scripts over `bertholomus/TensorFold@glm-dsa-tp4`
  (`ddfad35`, TensorFold 0.6.0); **C1 decode 35.7 t/s @ d0 / 35.9 @ d8k**, MTP-3 acceptance 63.4 %.
  Receipts: `~/benchmarks/glm53-exl3-20261013/`.
- **GLM-5.3-Flash EXL3 4bpw / TensorFold, TP=2 / TP=3 / TP=4** — **all BOOT-VERIFIED 2026-10-13**;
  `MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks-TensorFold` launcher (`main` `3fd60df`, `tp4` `d220030`),
  checkpoint `Mia-AiLab/GLM-5.3-Flash-EXL3-4bpw-TensorFold@078455ff`, drafter
  `incoai/GLM-5.3-Flash-DFlash2@bf582e4e`; TP=4 **C1 decode 98.4 t/s @ d0 / 99.4 @ d8k**, DFlash2
  acceptance 76.6 %, quality 37/37 on the house battery. Receipts:
  `~/benchmarks/glm53-flash-exl3-tp4-trial-20261013/` (TP=2/TP=3 siblings).
- **Flash NVFP4 / vLLM** — **ARCHIVED 2026-10-13**, proven-negative on the pinned public image; see
  [`attic/glm/ARMS-MANIFEST.md`](../../attic/glm/ARMS-MANIFEST.md).

## Licence

The **Flash** line is **MIT**; the **DFlash2 drafter is CC BY-NC-ND** — acceptable for this
non-commercial cluster (owner decision 2026-10-11), not for commercial resale. The full 753B line and
its derivatives carry the **Z.AI GLM-5.3 Licence** (permissive, with the MaaS >$10B security-review
clause). Full map: [`attic/glm/GLM-5.3-RECOMMENDATIONS.md`](../../attic/glm/GLM-5.3-RECOMMENDATIONS.md#licensing-map).

## Runbook notes and revision pins

The runbook bullets and the revision pins below move with the lane's research. The live copy is in
[`attic/glm/AGENTS.md`](../../attic/glm/AGENTS.md) — **nothing in this lane is pinned into a recipe**,
so a revive must re-stage weights (see the re-fetch costs under revision pins).

## Revision pins

**Moved to [`attic/glm/AGENTS.md`](../../attic/glm/AGENTS.md#revision-pins-verified-2026-10-14-hub-api--every-nodes-hf-cache)
§"Revision pins" (verified 2026-10-14, Hub API + every node's HF cache).** Summary: the Flash EXL3 4bpw
checkpoint pins `078455ff` (`main` `76c0b517`), the EXL3 3.0bpw checkpoint is `7f057383` (`main`,
~273 GB/node re-fetch after the 2026-10-14 reclamation), the archived Flash NVFP4 pin `36c184c6` is
gone from all nodes (`main` has moved to `18d55bfd`), and the TensorFold engine pin is `ddfad356`.

## Attic index

Everything below lives in [`attic/glm/`](../../attic/glm/) and answers a question the lane README no
longer carries. Nothing in it is served by the registry.

| File | What it holds | Question it answers |
|---|---|---|
| [`ARMS-MANIFEST.md`](../../attic/glm/ARMS-MANIFEST.md) | Provenance table for the one archived arm (`glm-5.3-flash-nvfp4-dflash-vllm.yaml`), the owner decision, and the "do not re-add" rule | Why was the Flash NVFP4 recipe archived, and what would it take to revive it? |
| [`AGENTS.md`](../../attic/glm/AGENTS.md) | Runbook notes for the boot-verified serving lines (serve commands, host overrides, topologies, metrics, receipts) + the moved revision pins | How do I re-run a GLM-5.3 serving line on this cluster, and which Hub revisions does each pin? |
| [`GLM-5.3-RECOMMENDATIONS.md`](../../attic/glm/GLM-5.3-RECOMMENDATIONS.md) | Research: the two model lines, four checkpoints, topology arithmetic, engines/spec-decode, two concrete serving configs, licensing map, platform risks, sources | Which GLM-5.3 checkpoint/engine/node-count should a future GLM recipe be built from, and why? |
| [`glm-5.3-flash-nvfp4-dflash-vllm.yaml`](../../attic/glm/glm-5.3-flash-nvfp4-dflash-vllm.yaml) | The archived vLLM arm itself (repo B's runtime-formula.json, image- and checkpoint-pinned) | What did the archived recipe actually configure? |
