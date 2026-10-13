# Protocol — how this planning file works (owner ↔ agent)

This file is the interface for planning rounds:

1. **Questions for the owner live only under `# DECISIONS`**, one per item, each ending with a
   `→ Answer:` line. **To answer: edit that line** — a word is enough ("defer", "skip", or a full
   call; replacing the ask with the answer is fine). Replying in chat or a numbered questionnaire
   works too. No special format needed.
2. **The agent folds answered items** into the work item(s) they govern as advisory notes tagged
   *"(Owner decision YYYY-MM-DD: …)"*, removes them from `# DECISIONS`, and restates whatever is
   left. Verbatim history is always in git (`git log -- mad-science/TODO.md`).
3. **Everything outside `# DECISIONS` is agent-maintained** — statuses, measurements, lane scope,
   the session record. State claims carry dates or commit hashes.

**Where things live:** this file holds **open work only** — completed items are archived in `../attic/DONE.md` as they close; dated session records live in `SESSION-RECORD.md` (same directory).

# DECISIONS — nothing open (2026-10-13)

New owner questions land here, each with a `→ Answer:` line.

# TODO list

Budget: 8 hours

Lane order (advisory — any rational order, preference for subagent parallelization; strict ordering is not priority):
- ds4
- ornith
- qwen4
- qwen3
- embed
- rerank
- glm5
- explore

Selection priorities:
- Node count (lower is better)
- Speed (higher is better)
- Accuracy (higher is better)
- Memory footprint (lower is better)
- *(Owner decision 2026-10-11: this weighting is confirmed; attic moves only if warranted, folded into each lane's quality/selection pass — no global end-of-session sweep.)*

## General Registry Maintenance
- [ ] Build additional quality testing and benchmarking suites using established industry standard benchmarking tools where feasible.

## ds4
DeepSeek V4.1
- [ ] **Check the DSV4.1 checkpoint revision.** No ds4 recipe pins a checkpoint revision — the knapcio TP4 image bakes it (`HF_REVISION`; the KNapcio memo records `fb2764a5` = `boot.py:24 REVISION`) — while Hub `main` for `deepseek-ai/DeepSeek-V4.1-Flash` is now `5254448103b6…` (2026-10-12) and **every node's cache already holds it**. Confirm what the live launcher actually serves, re-run the upstream-delta check against `52544481` (the 2026-10-10 memo found our then-pin *was* knapcio's v2.3 release commit — check whether this commit touches `boot.py`/kernels/overlay), then either pin `model_revision:` in the recipe or record why not, and re-run the ds4 suite (`needle-haystack` + `decode-triage` + the house battery). **Primary production lane — never disturb a live serve for this.**
- [ ] Move the DSV4.1 checkpoint revision `HF_REVISION` into the recipe yaml instead of the TP4 image. Build and push the image.

## glm5
GLM 5.3
- [ ] **Runbook revision refresh (no recipes to pin).** Cache-vs-Hub: `Mia-AiLab/GLM-5.3-Flash-EXL3-4bpw-TensorFold` `main` is `76c0b517…` (2026-10-03; the TP=2/TP=4 trials used `078455ff`), `bertholomus/GLM-5.3-EXL3-3.0bpw` resolves to `7f057383…`, and `RedHatAI/GLM-5.3-Flash-NVFP4` `main` has moved to `18d55bfd…` (2026-09-18) past the archived recipe's `36c184c6` pin — the pin's snapshot is absent from every node, so a revive would re-fetch `36c184c6` (and fail if that commit no longer exists upstream). Record these in the `recipes/glm/README.md` runbooks and re-check the engine `bertholomus/TensorFold@glm-dsa-tp4` pin (`ddfad35`).

## ornith
Ornith 1.5
- [ ] We are not convinced of the quality of this model and were surprised that you could not replicate the looping behavior it falls into when performing long horizon agentic workloads.  Run additional experiments to confirm the quality of this model.

## qwen3
Qwen 3.x
*(all items completed — archived in `../attic/DONE.md`)*

## qwen4
Qwen 4.x (and 3.8 Flash Next)
- [ ] **Re-pin (and re-verify the mods for) the labquant checkpoint.** `local-inference-lab/Qwen3.8-Flash-Next-NVFP4` `main` is `6c01ac378d22…` (2026-10-06 — the `step-5500 QAD` candidate the W14 plan already named) and the `.30` cache holds it, while the three `…labquant…` recipes pin `7c4f1bc1a2d6…`. Run the W14 per-mod re-verification plan against the new revision (one mod breaks, one is obsolete, five survive), then re-pin and re-bench the labquant arms (W3 battery + `decode-triage`).

## ifm
IFM K2-Horizon
- [ ] **Re-pin the K2-Horizon checkpoints.** Both reps have moved past the recipe pins and the `.30` cache holds the new revisions: `IFM/K2-Horizon-0.9B` `main` `383cb66347be…` (2026-10-06) vs pin `9fa6faa55fe1…`; `IFM/K2-Horizon-7B-FP8` `main` `ea739ec816e0…` (2026-10-03) vs pin `59d473210f0b…`. Diff the deltas, re-pin `model_revision:`, re-run the lane's benches + the dense accuracy set (`gsm8k`/arc/house), and re-confirm UNO spec-decode engagement on the 7B.

## embed
Any embed model
*(all items completed — archived in `../attic/DONE.md`)*

## rerank
Any rerank model
*(all items completed — archived in `../attic/DONE.md`)*

## decision
Any decision model
- [ ] **Evaluate the newer Decision-2.0 weights.** Hub `main` is `cc7f30cda9e7…` (Kai) / `df30237f9c1c…` (Sol), both 2026-10-10, while both recipes pin the `vllm-srun` runtime's own golden-checked revisions (`cd49ea38…` / `64235bef…`). Confirm whether the runtime's golden check accepts the newer revisions; if it pins its own, leave as-is and record why; otherwise re-pin and re-score both on `tool-eval-bench --decision-bench-only`.

## explore
Any model with reasoning and tool-calling capabilities
- [ ] **Re-pin Kolibri-1 (main moved past the pin).** Hub `main` `258cae8ffffc…` (updated 2026-10-13) vs the recipe pin `35bc4d3be745…`; the `.35` cache holds only `main` (from an unrelated unpinned fetch) while sparkrun fetches the pin, so a relaunch still serves `35bc4d3b`. Diff the deltas (weights / tokenizer / chat template), decide whether to move the pin to `258cae8f`, re-run the house battery + `decode-triage`, and re-confirm the plugin / `kolibri1` parser contract.
- *(Owner decision 2026-10-13: the deciding factor for explore models is **accuracy**, with preference for smaller and faster models — supersedes the node-count→speed default. Re-ranked: **Ling-3.0-flash** (rank 1, 37/37) and **Kolibri-1** (rank 2, 36/37 = 37/37 union, smaller + faster) are kept; Nemotron-262k and its 1M variant moved to `attic/explore/`.)*
- [ ] **Pin the DSPARK draft (Ling, rank 1).** `inclusionAI/Ling-3.0-flash-dspark` `main` moved to `d60b0e12…` on 2026-10-12 and the `.30` cache holds it, but the recipe's `speculative_draft_model` is a bare repo id (unpinned). Re-check DSPARK acceptance on the moved draft, pin the draft revision, and re-run `decode-triage` + the house battery — the shipped 45.5 t/s / 37/37 was measured on the 2026-10-11 draft.
- *(The archived Nemotron arms' `nvidia/…NVFP4-DSpark` draft also moved to `6d127b50…` on 2026-10-12 and was never pinned, so the 2026-10-13 acceptance-length non-reproduction (3.67 → 1.66) may be a draft change and not only the suspected metric-window artifact — re-check if those arms are revived.)*
- [ ] **Poolside Laguna XS-2.1 arm (queued 2026-10-13 — queue rank 1).** `poolside/Laguna-XS-2.1-NVFP4` (33B-A3B, 262k, OpenMDW-1.1, 21.6 GB) + `poolside/Laguna-XS-2.1-DFlash` draft (0.9 GB, `method: dflash`) on 1 node. The family's only single-Spark datum is the Spark Arena entry (TP=1, 37.5 t/s decode, full vLLM recipe sketch); the TP=1 sweep below is on the S-2.1 sibling. Checklist in `recipes/explore/EXPLORE-MODELS-RESEARCH.md` §5: import-check the image for `LagunaForCausalLM` + `dflash` + `poolside_v1`, NVFP4-on-SM121 risk (INT4 23.9 GB fallback), draft-depth sweep n ∈ {3,4,7} (S-2.1's sweep: n=3 beats the vendor n=15), battery with raised `max_tokens`. Compare C1/quality against Ling 37/37 @ 45.5 and Kolibri 36/37 @4096 @ 47.3; pin `model_revision:` on both repos (no registry artifact references the family yet — expect a full per-node download).
- [ ] **Poolside Laguna S-2.1 arm (queued 2026-10-13 — queue rank 2, also 1 node).** `poolside/Laguna-S-2.1-NVFP4` (118B-A8B, 1M ctx, OpenMDW-1.1; 99.7 GB download / 67 GiB resident) + `Laguna-S-2.1-DFlash-NVFP4` (2.2 GB; licence `other` — read it before distributing). Template = the fankserver single-Spark TP=1 sweep (util 0.85, 262k, DFlash n=3, 1.37M-token KV, 18.3 → 25.5 t/s) and its RC1 long-context variant (no DFlash + `--max-num-scheduled-tokens 4096` → 4.52M tokens). `Laguna-M.1` (NVFP4 139.3 GB) stays a 2-node ceiling reference.
- [ ] **Qwen-Image-2.1-Turbo arm (queued 2026-10-13 — media-gen, outside the lane brief).** **Licence first:** `qwen-research` is non-commercial ("FOR NON-COMMERCIAL PURPOSES ONLY") — the MiniMax-M3 class of blocker, since this registry ships to third parties; needs an owner call, and may stay eval-only. Then serve via `QwenImage21Pipeline` (diffusers ≥ PR #14950, transformers ≥ 5.17) under a script launcher (no `sglang|vllm` runtime) — expected **≈ 11 s @ 1024²** derived from the base model's GB10 measurement (54.1 s @ 40 steps, linear in steps; 31.6 GB peak); the 8-step schedule and its quality are ours to measure. Traps to re-check: VAE tiling OFF (pink seam), `cpu_offload` OFF, reference-image cost. Details: `recipes/explore/EXPLORE-MODELS-RESEARCH.md` §6.
- [ ] **LTX-2.5 arm (queued 2026-10-13 — media-gen, outside the lane brief).** `Lightricks/LTX-2.5` (video+audio, 22B DiT + Gemma-4-12B encoder, ComfyUI-native): repo is gated (`gated: auto`) → per-node `HF_TOKEN` and accepted terms, which a distributed registry cannot assume; licence = `ltx-2.x-community-license-agreement` (the LTX-2 text carries a $10M-revenue Commercial Entity threshold — read the 2.x text once access lands). Spark evidence exists as a **refine stage** (nvfp4 transformer 17.44 GiB + VAEs + upscaler = 20.1 GiB, 3 steps → 1344×768×124 f/24 fps with audio inside a 73.3 s warm two-stage run). Traps: ComfyUI ≥ 0.34.0 (below it the refine silently emits garbage), the `-nogemma` graph on GB10, and the sustained-load power-loss fix (2200 MHz clock cap). Details: §6.
