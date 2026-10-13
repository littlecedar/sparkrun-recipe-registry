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
*(all items completed — archived in `../attic/DONE.md`)*

## glm5
GLM 5.3
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

## embed
Any embed model
*(all items completed — archived in `../attic/DONE.md`)*

## rerank
Any rerank model
*(all items completed — archived in `../attic/DONE.md`)*

## decision
Any decision model
*(all items completed — archived in `../attic/DONE.md`)*

## explore
Any model with reasoning and tool-calling capabilities
*(all items completed — archived in `../attic/DONE.md`)*
- *(Owner decision 2026-10-13: the deciding factor for explore models is **accuracy**, with preference for smaller and faster models — supersedes the node-count→speed default. Re-ranked: **Ling-3.0-flash** (rank 1, 37/37) and **Kolibri-1** (rank 2, 36/37 = 37/37 union, smaller + faster) are kept; Nemotron-262k and its 1M variant moved to `attic/explore/`.)*

## Session follow-ons (restated 2026-10-12)
*(the sole remaining item — glm5 boot-verify — was exercised in the 2026-10-13 TP=4 window; see the glm5 lane item)*
