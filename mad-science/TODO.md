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

**Where things live:** completed items are archived in `../attic/DONE.md` (archived 2026-10-13); dated session records live in `SESSION-RECORD.md` (same directory).

# DECISIONS — nothing open (2026-10-13)

Three questions were answered in chat on 2026-10-13 and folded into the items they govern: the TP=4
window headline (shipped glm5 first) → the glm5 lane item; the spare-node allocation (TP≤2 work runs
concurrently) → the preamble; the flag-pass commit → done (session commit 1). A fourth was answered
**in-file** the same day: the glm5 Flash keep-vs-attic call → **archived to `attic/glm/`** (folded into
the glm5 lane item). The 2026-10-12 questions were folded earlier; the 2026-10-11 questionnaire register
is at `git show 8a98379:mad-science/TODO.md`. New owner questions land here, each with a `→ Answer:` line.

## explore rank-2 (answered in-file 2026-10-13)

The owner's answer: **switch the deciding factor to accuracy for explore models, with preference for
smaller and faster models.** Folded into the explore lane item and the lane docs — see the
*(Owner decision 2026-10-13 …)* note under `## explore`.

# TODO list

Budget: 8 hours

WOPR sparkrun cluster state (checked 2026-10-13, session start):
- **All six nodes `.30-.35` idle — no sparkrun containers.** The ds4 knapcio TP4 serve is down, so this is the owner-announced TP=4 exploration window (4-node jobs available). **If the ds4 serve comes back online, protect it — it may be serving this agent's own inference.**
- *(Owner decision 2026-10-13: DeepSeek is not running for the session; all six nodes are the session's, including TP=4; TP≤2 lane work runs on the spare nodes.)*
- *(Cache survey 2026-10-13 — the cache was read on ALL six nodes (`.30`-`.35`; the decision arms and several trial checkpoints live only on `.34`/`.35`) and the Hub API was queried for every shipped recipe's model and its spec-decode draft. Lanes below gained a re-pin + re-bench task where upstream `main` has moved. Confirmed still matching: `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4` (base), `ornith-ai/Ornith-1.5-35B-A3B-NVFP4`, `Intel/Qwen3-Coder-Next-int4-AutoRound`, `RadixArk/Qwen3.8-{27B,Flash-Next}-NVFP4` (+ its `-DSpark` draft), `nvidia/Qwen3.8-Flash-Next-NVFP4`, the four Qwen3-VL embed/rerank arms, `Cloudflare/clef-flash`, `autotrust/JEV-9B`, `Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw`, and `littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram`. **Floating (never pinned) — bindings whose revision can silently change a measured arm:** the drafts `inclusionAI/Ling-3.0-flash-dspark` (**moved `d60b0e12…` on 2026-10-12**) and `nvidia/…NVFP4-DSpark` (**moved `6d127b50…` on 2026-10-12**), plus `jzinno/Ornith-1.5-35B-A3B-DFlash2` (`9b4852c0…`), `incoai/Qwen3.8-27B-DFlash2` (`015e7956…`), `incoai/GLM-5.3-Flash-DFlash2` (`bf582e4e…`), and the unpinned bases `littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft` (`b4864e44…`) and the RadixArk/Qwen3.8 arms — a draft-pin task was added under explore.)*
- [ ] **Determine whether `model_revision:` actually pins the FETCH (cross-lane).** Observed 2026-10-13: each node cache holds exactly ONE snapshot per repo, and for arms whose pin differs from Hub `main` it is `main`, not the pin — Kolibri `258cae8f` (pin `35bc4d3b`), `local-inference-lab` `6c01ac37` (pin `7c4f1bc1`), K2 `383cb663`/`ea739ec8` (pins `9fa6faa5`/`59d47321`), RedHatAI-GLM-Flash `18d55bfd` (pin `36c184c6`); arms whose pin **==** main (ornith, Ling-int4, coder-next, nemotron, clef, JEV) hold their pin trivially. Two readings: sparkrun's prep resolves `{model}`/the restated snapshot path to `main`, or the caches were re-fetched unpinned after the boots. **Cheap decisive probe:** boot a pin≠main recipe (K2-Horizon-0.9B, 2 GB; pin `9fa6faa5` ≠ main `383cb663`; cache holds only main; `HF_HUB_OFFLINE=1`) and read the container cmdline (`docker inspect`) + the serve log's model path — a missing-revision failure means the pin IS honored and the cache needs a re-fetch; a healthy serve means `main` was used. If it is the latter, every `model_revision:` claim in a lane doc needs re-grounding.

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
- *(Owner decision 2026-10-13: the session headline is the two shipped glm5 TP4 boots, then the three MiaAI-Lab/DeepSeek trials; the spare two nodes run TP≤2 lane work concurrently.)*

## General Registry Maintenance
- **DONE 2026-10-13** — Move all completed TODO.md `- [ ]` items to @attic/DONE.md . *(Every completed item was archived verbatim to `attic/DONE.md`; this file is now `[X]`-free.)*
- **DONE 2026-10-13** — Move session records out of the TODO.md file -- keep it clean -- but add a reference to whichever file you put them in. *(The `## Session record` section moved verbatim to `mad-science/SESSION-RECORD.md`; reference added under `# Protocol`.)*

## ds4
DeepSeek V4.1
- [ ] **Check the DSV4.1 checkpoint revision.** No ds4 recipe pins a checkpoint revision — the knapcio TP4 image bakes it (`HF_REVISION`; the KNapcio memo records `fb2764a5` = `boot.py:24 REVISION`) — while Hub `main` for `deepseek-ai/DeepSeek-V4.1-Flash` is now `5254448103b6…` (2026-10-12) and **every node's cache already holds it**. Confirm what the live launcher actually serves, re-run the upstream-delta check against `52544481` (the 2026-10-10 memo found our then-pin *was* knapcio's v2.3 release commit — check whether this commit touches `boot.py`/kernels/overlay), then either pin `model_revision:` in the recipe or record why not, and re-run the ds4 suite (`needle-haystack` + `decode-triage` + the house battery). **Primary production lane — never disturb a live serve for this.**

## glm5
GLM 5.3
- [ ] **Runbook revision refresh (no recipes to pin).** Cache-vs-Hub: `Mia-AiLab/GLM-5.3-Flash-EXL3-4bpw-TensorFold` `main` is `76c0b517…` (2026-10-03; the TP=2/TP=4 trials used `078455ff`), `bertholomus/GLM-5.3-EXL3-3.0bpw` resolves to `7f057383…`, and `RedHatAI/GLM-5.3-Flash-NVFP4` `main` has moved to `18d55bfd…` (2026-09-18) past the archived recipe's `36c184c6` pin — **and the `.31-.33` caches hold ONLY `18d55bfd`: the pinned `36c184c6` snapshot is absent, so a relaunch would serve a checkpoint the recipe does not pin (sparkrun rewrites a restated snapshot path to whatever it prepared). Verify before any revive.** Record these in the `recipes/glm/README.md` runbooks and re-check the engine `bertholomus/TensorFold@glm-dsa-tp4` pin (`ddfad35`).
- **DONE 2026-10-13 — the glm5 TP=4 window ran; Flash archived, EXL3 verified.** *(Owner decision 2026-10-13: the Flash recipe is a proven-negative on the pinned public image → archived to `attic/glm/`.)* Flash TP4: boot-attempted, BLOCKED, root-caused — five boots on `.30-.33`, every failure in the container serve log: the pinned public image's SM120 sparse-MLA backend forces the `fp8_ds_mla` KV layout whose `concat_and_cache_mla` kernel needs a 64-dim RoPE tail, but `RedHatAI/GLM-5.3-Flash-NVFP4` is NoPE MLA (`qk_rope_head_dim 0`); `bfloat16`/`nvfp4_ds_mla` KV select no backend, `FLASHINFER_MLA_SPARSE` is unsupported on GB10, and the DFlash2 drafter needs the absent `SupportsEagle3`. Repo B qualified on a local unpublished image — the recipe is correct, the image is the blocker, and it never produced a C1/quality. Receipts: `~/benchmarks/glm53-flash-20261013/`.
  - **EXL3 TP4 BOOT-VERIFIED 2026-10-13**: 4 ranks on `.30-.33` (`tfrun-sglang.sh` + adapted `tp4_start.sh`, base `lmsysorg/sglang:dev-cu13` digest `aa878e8d`, engine `bertholomus/TensorFold@ddfad35`; `TF_GLM_KV=q5 TF_GLM_EMBED_SPLIT=1 TF_GLM_MTP_REUSE=2`, `--mtp-drafts 3 --parallel 4`, `startup estimate 88.58 GiB within 103.22 GiB`). Healthy serve (`GET /v1/models` → `GLM-5.3-EXL3-3.0bpw`; chat `27*43`→`1161`, finish `stop`). **C1 35.67 t/s @ d0 (σ 3.13, n=5) / 35.89 @ d8192**; **MTP-3 acceptance 63.4%**. Recorded as a **runbook, not a recipe** (the engine is an unreleased fork branch installed editable at container start; a recipe needs a baked image + a GLM variant of the TensorFold launcher mod) — runbook + recipe sketch in `recipes/glm/README.md`. Receipts: `~/benchmarks/glm53-exl3-20261013/`.
  - **MiaAI-Lab tp4 branch — recon done, TP=4 trial BOOT-VERIFIED 2026-10-13** (clone `~/src/MiaAI-GLM53-Flash-EXL3-tp4` @ `d220030`; reused the sibling's engine image and the 176 GB `Mia-AiLab/GLM-5.3-Flash-EXL3-4bpw-TensorFold` checkpoint — no build needed). Result in the archived `Trial a TP=4 recipe …` item in `../attic/DONE.md`.
  - **Window OPEN 2026-10-13**: owner reports DeepSeek down and all six nodes free; supersedes the 2026-10-12 deferral. Boot-verify the shipped glm5 recipes first, then the MiaAI-Lab trials.
- **DONE 2026-10-13** — Select the best recipes from all lanes and move the rest to the `@attic/`: the glm5 Flash recipe is a proven-negative on the pinned public image → **archived to `attic/glm/`** (owner decision 2026-10-13, `#DECISIONS`).

## ornith
Ornith 1.5
*(all items completed — archived in `../attic/DONE.md`)*

## qwen3
Qwen 3.x
*(all items completed — archived in `../attic/DONE.md`)*

## qwen4
Qwen 4.x (and 3.8 Flash Next)
*(the DeepSeek-V4-Flash TP=2 trial ran 2026-10-13 — archived in `../attic/DONE.md`)*
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
- [ ] **Re-pin Kolibri-1.** Hub `main` `258cae8ffffc…` (updated 2026-10-13) vs the recipe pin `35bc4d3be745…`; the `.35` cache holds **only** `258cae8f` — the pinned `35bc4d3b` snapshot is absent — so confirm what a relaunch actually serves (sparkrun rewrites the command's restated snapshot path to whatever it prepared). Diff the deltas (weights / tokenizer / chat template), re-pin `model_revision:`, re-run the house battery + `decode-triage`, and re-confirm the plugin / `kolibri1` parser contract on the new revision.
- *(Owner decision 2026-10-13: the deciding factor for explore models is **accuracy**, with preference for smaller and faster models — supersedes the node-count→speed default. Re-ranked: **Ling-3.0-flash** (rank 1, 37/37) and **Kolibri-1** (rank 2, 36/37 = 37/37 union, smaller + faster) are kept; Nemotron-262k and its 1M variant moved to `attic/explore/`.)*
- [ ] **Pin the DSPARK draft (Ling, rank 1).** `inclusionAI/Ling-3.0-flash-dspark` `main` moved to `d60b0e12…` on 2026-10-12 and the `.30` cache holds it, but the recipe's `speculative_draft_model` is a bare repo id (unpinned). Re-check DSPARK acceptance on the moved draft, pin the draft revision, and re-run `decode-triage` + the house battery — the shipped 45.5 t/s / 37/37 was measured on the 2026-10-11 draft.
- *(The archived Nemotron arms' `nvidia/…-NVFP4-DSpark` draft also moved to `6d127b50…` on 2026-10-12 and was never pinned, so the 2026-10-13 acceptance-length non-reproduction (3.67 → 1.66) may be a draft change and not only the suspected metric-window artifact — re-check if those arms are revived.)*

## Session follow-ons (restated 2026-10-12)
*(the sole remaining item — glm5 boot-verify — was exercised in the 2026-10-13 TP=4 window; see the glm5 lane item)*
