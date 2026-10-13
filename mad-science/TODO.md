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

# DECISIONS — 1 open (2026-10-13)

Three questions were answered in chat on 2026-10-13 and folded into the items they govern: the TP=4
window headline (shipped glm5 first) → the glm5 lane item; the spare-node allocation (TP≤2 work runs
concurrently) → the preamble; the flag-pass commit → done (session commit 1). The 2026-10-12
questions were folded earlier (preamble + glm5 item); the 2026-10-11 questionnaire register is at
`git show 8a98379:mad-science/TODO.md`. New owner questions land here, each with a `→ Answer:` line.

## glm5 Flash recipe: keep it shipped under the BLOCKED banner, or move it to `attic/glm/`?

`glm-5.3-flash-nvfp4-dflash-vllm.yaml` is repo B's validated formula, digest-pinned, checkpoint pinned — but 2026-10-13 (five boots on `.30-.33`) proved the **public** `glm53-flash` image cannot serve this checkpoint on GB10: its SM120 sparse-MLA backend forces the `fp8_ds_mla` KV layout, whose `concat_and_cache_mla` kernel needs a 64-dim RoPE tail while the checkpoint is NoPE MLA (`qk_rope_head_dim 0`); `bfloat16`/`nvfp4_ds_mla` KV select no backend and `FLASHINFER_MLA_SPARSE` is unsupported on GB10; the DFlash2 drafter needs the absent `SupportsEagle3`. Repo B qualified on a **local, unpublished** image (no public digest). The recipe is correct — the pinned image is the blocker — and it has never produced a C1 or a quality score.
→ Answer: (keep shipped under the BLOCKED banner, or move to `attic/glm/` as a proven-negative arm?)

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
- [ ] Boot-verify both glm5 recipes when a 4-node window opens (Flash TP4 + EXL3 TensorFold TP4 via `scripts/tfrun.sh` in repo A's work dir). **2026-10-13 (TP=4 window): Flash TP4 BOOT-ATTEMPTED — BLOCKED, root-caused; EXL3 TP4 staged, boot in progress.** Flash: five boots on `.30-.33`, every failure in the container serve log (not the launcher) — the pinned public image's SM120 sparse-MLA backend forces the `fp8_ds_mla` KV layout whose `concat_and_cache_mla` kernel needs a 64-dim RoPE tail, but `RedHatAI/GLM-5.3-Flash-NVFP4` (and the official `zai-org/GLM-5.3-Flash`) is NoPE MLA (`qk_rope_head_dim 0`); `bfloat16`/`nvfp4_ds_mla` KV select no backend, non-SM120 `FLASHINFER_MLA_SPARSE` is unsupported on GB10, and the DFlash2 drafter needs the absent `SupportsEagle3`. Repo B qualified on a local unpublished image (`local_image_id 1e9709af…`, `public_image_digest_available: false`). **No C1 / no quality — there was never a healthy serve.** A page-cache drop is required before any launch of the 198 GB checkpoint (the read fills host page cache; `MemFree` 70 GB vs `MemAvailable` 122 GB). EXL3: checkpoint (39 shards, 292.65 GB) distributed to `.30-.33`, engine `ddfad35` synced, `tfrun-sglang.sh` + adapted `tp4_start.sh` staged in `~/glm53-tf/`; boot attempt in progress. Receipts: `~/benchmarks/glm53-flash-20261013/`, `~/benchmarks/glm53-exl3-20261013/`.
  - **EXL3 TP4 BOOT-VERIFIED 2026-10-13**: 4 ranks on `.30-.33` (`tfrun-sglang.sh` + adapted `tp4_start.sh`, base `lmsysorg/sglang:dev-cu13` digest `aa878e8d`, engine `bertholomus/TensorFold@ddfad35`; `TF_GLM_KV=q5 TF_GLM_EMBED_SPLIT=1 TF_GLM_MTP_REUSE=2`, `--mtp-drafts 3 --parallel 4`, `startup estimate 88.58 GiB within 103.22 GiB`). Healthy serve (`GET /v1/models` → `GLM-5.3-EXL3-3.0bpw`; chat `27*43`→`1161`, finish `stop`). **C1 35.67 t/s @ d0 (σ 3.13, n=5) / 35.89 @ d8192**; **MTP-3 acceptance 63.4%**. Recorded as a **runbook, not a recipe** (the engine is an unreleased fork branch installed editable at container start; a recipe needs a baked image + a GLM variant of the TensorFold launcher mod) — runbook + recipe sketch in `recipes/glm/README.md`. Receipts: `~/benchmarks/glm53-exl3-20261013/`.
  - **MiaAI-Lab tp4 branch — recon done, trial in progress 2026-10-13** (clone `~/src/MiaAI-GLM53-Flash-EXL3-tp4` @ `d220030`). Prereqs are heavy: its own `Mia-AiLab/GLM-5.3-Flash-EXL3-4bpw-TensorFold` checkpoint (~176 GB, cold) + an engine image that must be built/published (`scripts/publish-image.sh`, 106 patches).
  - **Window OPEN 2026-10-13**: owner reports DeepSeek down and all six nodes free; supersedes the 2026-10-12 deferral. Boot-verify the shipped glm5 recipes first, then the MiaAI-Lab trials.
- [ ] Select the best recipes from all lanes and move the rest to the @attic. **2026-10-13: the glm5 Flash recipe is a proven-negative on the pinned public image — keep-shipped-blocked vs `attic/glm/` is an open owner call (see `#DECISIONS`).**

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

## Session follow-ons (restated 2026-10-12)
*(the sole remaining item — glm5 boot-verify — was exercised in the 2026-10-13 TP=4 window; see the glm5 lane item)*
