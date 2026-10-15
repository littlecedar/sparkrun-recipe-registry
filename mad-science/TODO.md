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

# DECISIONS — 2 open (2026-10-15)

### #34 — The shipped 8B reranker: keep its residency, or demote it to `attic/`?
`qwen3-vl-reranker-8b-vllm-b12x` is a shipped recipe (primary index + lane README) and the
deliberate non-`fast` quality tier (~4× slower per scored document than the 2B), but its checkpoint
costs +16 GB/node with no recorded cache state, and the 2B is the measured default. Keep it resident,
or retire it to `attic/rerank/` the way the GLM Flash arm was?
→ Answer:

### #35 — The two cybersec negatives: unblock them, or retire them to `attic/cybersec/`?
Arm 3 (`nex-n2.5-mini-uncensored-nvfp4-sglang`) and arm 4
(`qwen3.8-flash-next-uncensored-nvfp4-sglang`) are documented negatives that lost their index rows on
2026-10-14 while their recipe files stayed in `recipes/cybersec/`, so the tree and the distributed index
disagree. Unblock them via their card-documented vLLM routes (a boot receipt re-adds the rows), or
retire both (recipe + manifest row + a do-not-re-add note)?
→ Answer:

New owner questions land here, each with a `→ Answer:` line. Numbered decisions cited elsewhere —
#6 in `attic/qwen4/SELECTION-RANKING.md`, #11 in `attic/decision/DECISION-MODELS-RESEARCH.md`,
#10/#11/#14 in `attic/explore/EXPLORE-MODELS-RESEARCH.md` — live in git history: the 2026-10-11
register is `git show 8a98379:mad-science/TODO.md`; the 2026-10-14 registers (#16–#23, #24–#27) are
the pre-fold states, `git show baecfa8:mad-science/TODO.md` and `git show c7c7a81:mad-science/TODO.md`;
the #28–#33 register is the pre-fold state `git show 0d8014d:mad-science/TODO.md`.

# TODO list

*(2026-10-14 documentation sweep — six parallel lane/registry scouts over `recipes/**`, `attic/**`,
`benchmarking/`, `tools/`, and the `mad-science/` memos. Every item below carries `path:line` evidence
and an effort tag; boot-requiring work is the long tail. The per-lane "all items completed" stubs were
dropped where the sweep opened new work.)*

*(Owner decision 2026-10-15: the sweep runs with no timebox — multi-day, group by group, stopping
only at a gate; the register is the scope, not a plan.)*

**Resourcing (2026-10-15).** Single-node work runs on the free `.34`/`.35`; `.30`–`.33` are busy with
the ds4 TP=4 job and the multi-node items in the lanes below wait for that window. Every `sparkrun` call runs from
the head with the HOME override and `--transfer-mode local`, and **the registry clone must be
refreshed first** (`sparkrun registry update littlecedar`): it is behind the tree today and carries no
lane-local `mods/`, so an `@littlecedar/…` launch of the ornith 35B dies with `Could not resolve mod
'mods/ornith-honed-chat-template'` (measured 2026-10-15). For the same reason, launch a recipe by its
real path — never a flattened `~/development/<name>.yaml` symlink. Only two orderings are asserted: the
RadixArk reclaim on `.34` is tagged *immediate* (126 GiB resident against the owner's cache policy), and
the ornith 35B is the first arm of the standard-suite sweep.

Selection priorities:
- Node count (lower is better)
- Accuracy (higher is better)
- Speed (higher is better)
- Memory footprint (lower is better)
- *(Owner decision 2026-10-11: this weighting is confirmed; attic moves only if warranted, folded into each lane's quality/selection pass — no global end-of-session sweep.)*

## General Registry Maintenance
- [ ] **Reconcile the stale counts in root `AGENTS.md`** — *partially closed 2026-10-15:* the `tools/` count (12 → 15, trio named) and the `benchmarking/` count (43 → 45, 44 llama-benchy + `standard-suite.yaml`) were corrected when the standard-suite trio landed, and the item's own premise no longer holds — `AGENTS.md:14` carries "31 files in 11 family dirs" and `:59` lists `recipes/explore/ (6)`. Remaining drift to re-measure before the next edit: `tests/` (19 guard modules), the `attic/` arm counts, `mods/` (4 + `mod-template`). (`mad-science/RESEARCH_LORE.md` §10 already warns of stale counts.) *(effort: short)*
- [ ] **Add `mods/README.md`** with a disposition table (mirroring `tools/README.md`'s) — four mods are mounted by no shipped recipe: `drop-caches`, `skip-labquant-vision-tower`, `fix-sglang-radix-chunked-insert`, `dsv41-vision-overlay` (their dispositions are scattered across lane docs, recoverable today only by grep). *(effort: short)*
- [ ] **Sweep `benchmarking/` profiles stranded by the lane cuts** — the qwen4 `bs-*` cliff family and the qwen3 depth-cost family serve arms since archived; three name the archived `zz-rk-moebackend.yaml` (`benchmarking/README.md` §cliff family). *(effort: short)*
- [ ] **Fix the ds4 README TP=2 table's model id** — it says stock `Mia-AiLab/…EXL3-2.9bpw`; the shipped recipe declares `littlecedar/…-with-engram` (`recipes/ds4/README.md` vs `recipes/ds4/deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml`). *(effort: short)*
- [ ] **Write the licence policy line and give the index a licence marker** — a root-docs paragraph on what the registry may carry (non-commercial, gated, derivatives of third-party bases) and what "third-party-downloadable" means, plus a licence flag in the `recipes/README.md` taxonomy. *(Owner decision 2026-10-15: written policy line + index marker; per-recipe banners stay.)* *(effort: short)*

## ds4
DeepSeek V4.1
- [ ] **Ship TP=2 vision** — proven on our hardware ("supported and now proven … but not shipped"): a two-part change (`--vision` + the 43-tensor `vl_bias.safetensors` folder); the recipe still refuses `image_url` with HTTP 400 (`attic/ds4/AGENTS.md`). *(Owner decision 2026-10-15: next-window scope, on the free `.34`/`.35`.)* *(effort: short)*
- [ ] **Run the two KNAPCIO post-pin defer experiments as tracked A/Bs** — `DSV41_CACHE_GIB=0` (third-party +9% KV pool; shipped value is 4 GiB) and the `SGLANG_RUST_BUILD_MODE` cargo-probe boot-hang workaround (`mad-science/KNAPCIO-UPSTREAM-DELTA.md:49,56`; `recipes/ds4/mods/dsv41-sglang-overlay/launcher.py:116,162`). *(effort: short)*
- [ ] **RoCEnante coverage sweep + auto-crossover microbench** — the memo's §5 E3/E5 ("actually worth running"): do TP all-reduces/gathers >2 MiB silently fall back to NCCL (`SGLANG_ROCE_MAX_SIZE` 4/8 MiB vs shipped 2 MiB), and the 1 KB…2 MiB RoCEnante-vs-NCCL crossover curve (none measured) (`mad-science/CUSTOM_ALL_REDUCE_SM120_EXPERIMENTS.md:166-196`). *(effort: medium)*
- [ ] **Re-test `DSV41_CERT_HEAD` / `DSV41_ENGRAM_DRM_NODE`** — both named and deliberately off (CERT_HEAD −0.5 ms/step at c1 but slower from ~10 requests; ENGRAM_DRM_NODE needs a host display-reserve change) (`attic/ds4/AGENTS.md`). *(effort: medium)*
- [ ] **DSpark verify-window γ=3** — only γ=2 vs γ=5 was A/B'd; the fork's own baseline point (γ=3) was never measured on this lane (`recipes/ds4/mods/dsv41-sglang-overlay/launcher.py:140-158`). *(effort: short)*
- [ ] **[storage] Collapse the DS4.1 EXL3 duplication** — *(Owner decision 2026-10-15: combined repo everywhere — cybersec arm 5 grafts onto the combined `littlecedar/…-EXL3-2.9bpw-with-engram` pack and drops `dsv41-engram-fetch`; the changed arm needs a re-boot receipt.)*; per node serving both lanes the same ~197 GB weights + ~189 GiB Engram tables exist twice (`recipes/ds4/deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml`, `recipes/cybersec/README.md`, `recipes/cybersec/mods/graft-dsv41-ablit-wo-b/README.md:17-19`). *(effort: medium)*

## glm5
GLM 5.3
- [ ] **Promote the GLM-5.3-Flash EXL3 4bpw TP=4 line to a recipe** — boot-verified 98.4 t/s @ d0 (2.7× the 3.0bpw route) with a pre-built engine image (`tensorfold-glm53:v0.6.0`); blocked only on the three-file deliverable (baked image + a `tensorfold-glm-exl3-launcher` mod + the `runtime: sglang` shim) (`recipes/glm/README.md` §runbook bullets 3–5; `attic/glm/GLM-5.3-RECOMMENDATIONS.md`). *(effort: medium)*
- [ ] **Promote the EXL3 3.0bpw full-753B lane to a recipe** — the only full-model option that fits TP=4 (35.67 t/s measured); same three-part blocker, needs a source image build first (`recipes/glm/README.md` §"Revision pins"). *(effort: medium)*
- [ ] **Measure the EXL3 3.0bpw 1M arm** — `TF_GLM_DCP=4` + `TF_GLM_EXTENTS=1` documented from repo A but never measured here (`attic/glm/GLM-5.3-RECOMMENDATIONS.md`). *(effort: medium)*

## ornith
Ornith 1.5
- [ ] **Build a YaRN long-context (~1M) arm** — both Ornith cards publish the factor-4 route and the shipped arms cap at 262,144, with no needle evidence **above** 262,144 (32k 3/3, 128k 3/3 and 262,144 2/3 are recorded) ("named work nobody did") (`recipes/ornith/README.md:195-202`; `attic/ornith/AGENTS.md:270-273`). *(effort: medium)*
- [ ] **Retry the 397B DFlash head with prefix caching intact (or fewer spec tokens)** — the recorded ~12% loss is partly a structural confound (vLLM treats every Mamba group as the draft group, disabling prefix caching); only n=8 was tried (`attic/ornith/AGENTS.md:324-328`; `recipes/ornith/README.md` §397B). *(Owner decision 2026-10-15: deferred — needs a TP=4 window on the restricted `.30`–`.33`.)* *(effort: medium)*
- [ ] **Measure the 9B arm at C>1** — only C1 is recorded; the lane names the pool-split concurrency question itself ("untested at C>1") (`attic/ornith/AGENTS.md:674-676`). *(effort: short)*
- [ ] **Re-verify the 35B serve line on the SGLang 0.5.18→0.5.21 bump** — a named perf lead (DFlash-reranker + GDN fusion wins) that currently breaks the lane (`attic/ornith/AGENTS.md:883-886`). *(effort: medium)*
- [ ] **`moe_runner_backend: marlin` under an interleaved paired control** — the ladder's best extra cell (108.9 t/s) collapsed into noise only because the control was ordered, not interleaved (`attic/ornith/AGENTS.md:497-513`). *(effort: short)*
- [ ] **Measure the r0b0tlab W4A16 NVFP4 35B + MTP head** — 63–77 t/s claimed with accuracy parity; rejected on a paper comparison, never measured on our stack (`attic/ornith/AGENTS.md:881-882`). *(effort: short)*
- [ ] **Run the standard evaluation suite (SOP) against the shipped 35B arm** — the first arm of the registry-wide sweep: `tools/eval-suite.py` (contract/house/needle/hard/tools) + the `benchmarking/concurrency-ladder.yaml` perf leg on the same boot + `benchmarking/standard-suite.yaml` (the Plan C C2 clause), receipts `~/benchmarks/ornith-35b-suite-20261015/`, numbers into `recipes/ornith/README.md` + `attic/ornith/AGENTS.md` with bench ids. **Launch it by the recipe's real path, never the flattened `/<home-dir>/development/<name>.yaml` symlink**: the lane-local `mods/ornith-honed-chat-template` resolves against `dirname(recipe.source_path)` (`sparkrun/core/mods.py` rule 2), so the symlink fails at launch with "Could not resolve mod" (measured 2026-10-15 on `.35`). *(effort: medium)*

## qwen3
Qwen 3.x
- [ ] **Boot the 27B TP=2 arm with `recipes/cybersec/mods/fix-fastsafetensors-tp2-sglang`** — the lane's self-declared "Highest value" open item (TP=2 halves weight-read time); the fix mod exists and has never been run (`attic/qwen3/AGENTS.md:166-169`; `attic/qwen3/NOTES.md` §4 WP1). *(Owner decision 2026-10-15: next-window scope, on the free `.34`/`.35`.)* *(effort: medium)*
- [ ] **Pin the 27B arm's checkpoint and its `incoai` DFlash2 draft** — the only unpinned shipped arm in these lanes; both SHAs are already recorded (`recipes/qwen3/qwen3.8-27b-nvfp4-dflash2-sglang.yaml`; `mad-science/SESSION-RECORD.md:104`). *(effort: short)*
- [ ] **[storage] Consolidate the DFlash2 drafter on one repo id** — `incoai` and `z-lab` are the same blob hash; three arms fetch it (27B DFlash2, MLX-4bit TensorFold, cybersec arm 2) and the `incoai` copy is unpinned (silent drift between consumers) (`attic/qwen3/AGENTS.md:106`). *(effort: short)*

## qwen4
Qwen 4.x (and 3.8 Flash Next)
- [ ] **Revive `…-labquant-highcon-…` in a k≥16 aggregate window** — dominated on one axis only; it is the sole holder of the aggregate-throughput regime (`attic/qwen4/ARMS-MANIFEST.md:118`; `attic/qwen4/AGENTS.md`). *(Owner decision 2026-10-15: next-window scope, on the free `.34`/`.35`.)* *(effort: short)*
- [ ] **Pass the 1M needle gate for `…-labquant-longctx-…`** — the archived long-context route's missing prerequisite ("quality above 262k is still UNMEASURED") (`attic/qwen4/AGENTS.md`). *(effort: medium)*
- [ ] **Run the W4 `#37111` release soak (1–2 h / ~100k)** — only a short smoke ran, so the corruption gate is unproven (`attic/qwen4/AGENTS.md`). *(effort: medium)*
- [ ] **One-boot `--enable-linear-replayssm-spec` test** — the lane's "most promising un-measured memory lever" (`attic/qwen4/NOTES.md` Open questions). *(effort: short)*
- [ ] **Clear the remaining qwen4 measurement backlog** — TP=4 (W6) re-boot after the `port_timeout_s` fix; the W12 cross-runtime vLLM same-checkpoint bench; the `--fp4-gemm-backend` A/B (the shipped `flashinfer_cutlass` was inherited without justification); `--enable-int8-mamba-checkpoint`; and the bs>1 cost of `--cuda-graph-backend-prefill disabled` (`attic/qwen4/AGENTS.md` §10.1). *(effort: medium)*
- [ ] **Retire or resolve the shipping diagnostic** — `diag-qwen4-unplaced-scales` ships only because the shared-expert scale blocker is unexplained, and the `demote-labquant-narrow-mxfp8-to-bf16` `EXTRA_LEAVES` knob stays for an unresolved QSA-prefill CUDA-graph crash (`attic/qwen4/AGENTS.md` §10.1; `recipes/qwen4/mods/demote-labquant-narrow-mxfp8-to-bf16/README.md`). *(effort: medium)*
- [ ] **[storage] Reclaim the re-populated RadixArk snapshot on `.34`** — 126 GiB of the archived arm's checkpoint is resident again, against the owner's cache policy (`attic/qwen4/NOTES.md:33-35`). *(effort: immediate)*

## ifm
IFM K2-Horizon
- [ ] **Pass the 7B `fp8_e4m3` KV accuracy gate** — throughput is measured, quality is not, so the ~+6% d8192 win is unusable (`attic/ifm/NOTES.md` "Still open"; `recipes/ifm/README.md:111`). *(effort: short)*
- [ ] **Re-open UNO on the 0.9B** — `IFM/K2-Horizon-0.9B-Uno` exists and the gate mod already works for the 7B; the register was falsified for the 7B only (`attic/ifm/AGENTS.md` §9). *(effort: medium)*
- [ ] **Attempt 7B tree-mode UNO (topk>1)** — a second UNO geometry, never booted (linear is shipped) (`attic/ifm/NOTES.md` "Still open"). *(effort: medium)*
- [ ] **Decide the withdrawn 36B-A4B sub-lane** — the D2 numerics gate (a precondition, never executed) plus the ranked, never-run E-series arms (E5 fp8-gemm-backend, E7 page-size, E8 value-expert quant mod, E10 fp8-KV+TP2) (`attic/ifm/K2-36B-A4B-MODEL-OPTIMIZATION-WORK.md:496-501`). *(effort: long)*

## embed
Any embed model
- [ ] **Add a pooling `BenchmarkingPlugin`** — pooling engines have no `/chat/completions`, so the standard profiles "silent skip"; the lanes' numbers rest on hand-run scratch scripts ("a plugin, not a script, is the correct long-term home") (`tools/README.md:102-105`). *(effort: medium)*
- [ ] **Boot-verify the three-way co-location** (decision + embed + rerank on one node) — asserted in the budget math and in the lane README, never receipted (`recipes/decision/README.md` §Operating constraints; `attic/decision/AGENTS.md`). *(effort: short)*
- [ ] **Ship or retire the unquantized 8B BF16 encoder tier** — measured within 1.2% prefill of the shipped AWQ 4-bit, ships nowhere (scratch recipe only) (`recipes/embed/README.md`; `attic/embed/AGENTS.md`). *(effort: short)*

## rerank
Any rerank model
- [ ] **Decide whether the shipped 8B reranker earns its residency** — `qwen3-vl-reranker-8b-vllm-b12x` **is** a shipped recipe (primary index + lane README), so the earlier "backed by no shipped recipe" framing was wrong; it is the deliberate non-`fast` quality tier (~4× slower per scored document than the 2B) and its checkpoint costs +16 GB/node with no recorded cache state — keep-and-cache, or demote to `attic/`? (`recipes/rerank/README.md` §Shipped recipes; `attic/rerank/AGENTS.md` §8B reranker (quality tier)). *(effort: short)*

## decision
Any decision model
- [ ] **Productize the clef+Kai ensemble (+1.3 pt, McNemar p=0.012)** — a statistically real gain that exists only as a one-off analysis: no ensemble recipe/server and no benchmarking profile to reproduce it (`recipes/decision/README.md:199-241`). *(effort: medium)*
- [ ] **Build the named decision candidates** — `Decision-2.0-Nox-4B` (best-scoring 4B, never booted), `laya` (CPU-real, zero-GPU), `kev-0.8b`, `GLiNER2.5-Decide`, `d3-edge`, `JEV-27B`, and the Sol-2B GGUF/llama.cpp CPU path (avoids the vllm-srun kill-shim workaround) (`attic/decision/DECISION-MODELS-RESEARCH.md`). *(effort: medium)*
- [ ] **Build the TTS fourth co-tenant** (Kokoro-82M, 0.305 GiB on the A725 cores) — the co-location budget is quoted net of it, but it was never built (`attic/decision/DECISION-MODELS-RESEARCH.md`). *(effort: medium)*

## explore
Any model with reasoning and tool-calling capabilities
- [ ] **Build the top-ranked unbuilt reasoning candidates** — `Mistral-Small-4-119B-NVFP4` (rank 1; MLA backend question — `VLLM_MLA_DISABLE=1` caps ~40k/64k), `Muse-Glimmer-30B` (rank 2; blocked on unmerged vLLM PR #51655), `Nemotron-3-Super-120B-A12B-NVFP4` (rank 4); licence/availability-blocked: MiniMax-M3 (non-commercial), MiMo-V2.6-Flash-RL (no quant), Inkling-Small (unpublished active params); plus `IFM/K2-Horizon-375B-A23B` (`mad-science/EXPLORE-CANDIDATES.md:16-57`; `attic/explore/EXPLORE-MODELS-RESEARCH.md`). *(effort: long)*
- [ ] **Build the `JetBrains/Mellum2.1-12B-A2.5B-Thinking` arm (Mellum2.1 collection)** — owner added the collection directly, so it sits above the ranked list; nothing here has been booted. A 12B/2.5B-active MoE thinking/agentic model (64 experts, 8 active; 131k ctx, SW 1024 on 3 of 4 layers), Apache-2.0. BF16 24.3 GB fits one node with headroom, and the sibling GGUF repo carries a 7.0 GB MXFP4_MOE / 8.1 GB Q4_K_M route for llama.cpp; the card ships a vLLM recipe (`--reasoning-parser qwen3`, `--tool-call-parser hermes` for tool choice) and names an MTP head "coming soon" ([collection](https://huggingface.co/collections/JetBrains/mellum21); [card](https://huggingface.co/JetBrains/Mellum2.1-12B-A2.5B-Thinking); [GGUF card](https://huggingface.co/JetBrains/Mellum2.1-12B-A2.5B-Thinking-GGUF)). No DGX-Spark precedent; not yet in `mad-science/EXPLORE-CANDIDATES.md`. *(effort: short)*
- [ ] **Build the Laguna-M.1 2-node ceiling reference** — named then dropped; the family's only 2-node datapoint is third-party (`attic/explore/EXPLORE-MODELS-RESEARCH.md`). *(effort: medium)*
- [ ] **Exercise the media-gen cells left unrun** — LTX-2.5's I2V + FLF2V templates and the 4K/50 fps preset; Qwen-Image non-8-step schedules and 2048²; and the faster vLLM-OMNI engine route (40 vs 54 s on the base model) (`attic/explore/EXPLORE-MODELS-RESEARCH.md`). *(Owner decision 2026-10-15: next-window scope, on the free `.34`/`.35`.)* *(effort: medium)*
- [ ] **[storage] Narrow humanizer's `model_file_selection`** — `all` makes it an 82 GB arm with 62 GB of GGUFs it never loads (`recipes/explore/README.md:284-287`). *(effort: short)*

## cybersec
Cybersecurity-research (red-team) abliterated / uncensored models
- [ ] **Wire MTP spec decode onto the clean 27B arm** — its BF16 MTP head is preserved and the sibling lane measures 33.8 t/s vs this arm's 10.2 (`attic/cybersec/AGENTS.md`). *(Owner decision 2026-10-15: next-window scope, on the free `.34`/`.35`.)* *(effort: medium)*
- [ ] **Unblock the two negatives via their card-documented vLLM routes** — arm 4 (`qwen4_exp` route; the sole measured obstacle is the ~0.3 MB/s OCI relay) and arm 3 (image distribution) (`attic/cybersec/AGENTS.md`). *(effort: long)*
- [ ] **Reconcile the index and the tree for the two cybersec negatives** — on 2026-10-14 the primary index adopted *shipped = bootable and usable*, so arm 3 (`nex-n2.5-mini-uncensored-nvfp4-sglang` — NaN sample-time logits under SGLang) and arm 4 (`qwen3.8-flash-next-uncensored-nvfp4-sglang` — SGLang's compressed-tensors loader refuses the export's scheme) lost their rows **while their recipe files stay in `recipes/cybersec/`**: the tree and the index disagree, and neither arm is visible to a reader of the distributed index until one of the two exits closes. Either **unblock via the card-documented vLLM routes** (the item above) and re-add the rows on a boot receipt, or **retire both to `attic/cybersec/`** the way the GLM Flash arm was (recipe + manifest row + a do-not-re-add note) so `recipes/` and the index tell the same story again. (`recipes/README.md:109-113`; `recipes/cybersec/README.md:86-122`; `attic/cybersec/AGENTS.md` §8; precedent `recipes/glm/README.md:18-24`, `attic/glm/ARMS-MANIFEST.md`) *(effort: short)*
- [ ] **[storage] Test whether the uncensored deltas are graftable as sidecars** over the cached bases instead of shipping ~184 GB / 25 GB full exports *(Owner decision 2026-10-15: case-by-case on licence — graft only where the base's licence clearly permits redistribution; keep the full export otherwise.)* (`recipes/cybersec/README.md:176-179`). *(effort: long)*

**Other surfaced arms (not queued):** `orcarouter/GLM-5.3-Flash-Uncensored-NVFP4` (321B, **205.1 GB** —
2-node-heavy/3-node; inherits the archived glm5 Flash serve blocker),
`orcarouter/DeepSeek-V4-Flash-Vision-Uncensored` (304B, `deepseek_v4`),
`drowzeys/keys-Qwen3.8-Flash-Next-NVFP4-dual-ablit-house-qsa-L3-47` (dual 180B ablit, **132.7 GB**; base
`nvidia/…` → licence `other`), `drowzeys/keys-GLM-5.3-Flash-NVFP4-ablit-l15-43-mtp-l45` (169B, MIT),
`drowzeys/MiMo-V2.6-Flash-RL-Abliterated` (310B, FP8/MXFP4). **Over the 1–2-node bar, so recorded but NOT
queued:** `drowzeys/keys-MiMo-V2.6-Pro-RL-Jarrelscy-ARVQ-Abliterated` (`nvfp4_arvq_hybrid`, MIT, gated —
**315.7 GB** on-disk ⇒ ≥3 nodes; owner asked to add it only if it fit 1–2).

## Concurrency ladder (registry-level)
No shipped arm has a measured `C2`/`C5`/`C10`: a census of the `~/benchmarks/**` and `.scratch/**` receipts (509 decode-phase cells) finds C1 only for most arms, C1/C4/C8/C16 for ds4 and C1/C4/C8 for IFM, and C1/C4/C8/C16/C32 for the pooling lanes — which is why those three columns are `—` in `recipes/README.md`. **Do not fill them from the wrong receipt:** `attic/ds4/PERF-ISSUES.md:49-52`'s c1/c2/c5/c10 table is a cold-prefill triage on a different harness (its d0 c1 is 36.2, not the index's 46.5) and `attic/ifm/NOTES.md`'s c=2 53.697 belongs to the withdrawn 36B arm.
- [ ] **Fill C2/C5/C10 for the single-node text arms** — the 14 that fit one Spark (ornith 35B/9B, qwen3 dflash2/coder-next/mlx4bit-TensorFold, IFM 0.9B/7B, explore ling/kolibri/laguna-XS/laguna-S/humanizer, cybersec arms 1/2) on the free `.34`/`.35`; per cell quote the **decode** row of the `--output` file (never the printed table, which shows only that row and no header) and cite the receipt beside the number in `recipes/README.md` and the lane doc. *(effort: long)*
- [ ] **Fill C2/C5/C10 for the multi-node arms** — ds4 knapcio (TP=4) + ds4 tensorfold (TP=2), qwen4 labquant (TP=2), ornith 397B (TP=4), cybersec arm 5 (TP=2): needs a window on `.30`–`.33`, restricted today. *(effort: long)*
- [ ] **Re-measure the pooling lanes at the ladder points** — embed/rerank publish `units/s` at C1/C4/C8/C16/C32 (`tools/pooling-bench.py`); re-run at c 1/2/5/10 and quote `units / wall_seconds` from the receipt. (`recipes/embed/README.md`; `recipes/rerank/README.md:69-70`; `.scratch/embed/csweep8b-order1-c*.json`) *(effort: medium)*
- [ ] **Give the two non-t/s lanes a ladder or a documented `—`** — the decision arms report `req/s` from a *serial* instrument (`tool-eval-bench`), so filling C2/C5/C10 there needs a concurrent harness; the image arm serves one request at a time, so its `—` should be written down as by-design in the lane doc. (`recipes/decision/README.md`; `recipes/explore/README.md`; `tools/README.md`) *(effort: medium)*

## Standard evaluation suite (registry-level)
- [ ] **Run the standard suite against every shipped arm** — the SOP pass (`tools/eval-suite.py`, then the `benchmarking/concurrency-ladder.yaml` leg `--skip-run` on the same boot, then `benchmarking/standard-suite.yaml` where the arm serves tool calls) for each shipped recipe; receipts under `~/benchmarks/<lane>-<date>/`, numbers into the lane docs and the index with their receipt/bench id. This is the sweep that fills the C2/C5/C10 cells above and each lane's unmeasured accuracy cells; start with the ornith 35B and work the free `.34`/`.35` window. *(effort: long)*

## Storage consolidation (registry-level)
- [ ] **[storage] Census and reconcile the unrecorded attic weight packs** — attic/ds4 Pollard EXL3 3.5bpw (552B), attic/ifm 36B-A4B ("48 GB synced to every node"), attic/explore Nemotron-30B NVFP4 + its DSpark draft: the 2026-10-14 reclaim record names none of them (`attic/ds4/README.md:25-30`; `attic/ifm/ARMS-MANIFEST.md:52`; `attic/explore/ARMS-MANIFEST.md:40-41`; `mad-science/SESSION-RECORD.md:171-173`). *(Owner decision 2026-10-15: census first, then reclaim archived-lane weights — keep shipped-arm weights and anything a doc cites; covers the explore weights in the item below.)* *(effort: short)*
- [ ] **[storage] Verify the un-recorded explore weights that are plausibly still cached** — Nemotron NVFP4 + draft, Qwen-Image 32.5 GB, LTX-25 36.9 GB on `.35`, Ling 154 GB, Kolibri 74 GB: no doc states their cache state (`attic/explore/QWEN-IMAGE.md`; `attic/explore/LTX-25.md`; `recipes/README.md` Explore table). *(effort: short)*
- [ ] **[storage] Evaluate the Qwen3.8-27B "same model, three packs" consolidation** — RadixArk / AEON-ULTIMATE-UNCENSORED / orcarouter-Uncensored are 21–25 GB each; the latter two are the natural sidecar candidates *(Owner decision 2026-10-15: case-by-case on licence — graft only where the base's licence clearly permits redistribution; keep the full export otherwise.)* (`recipes/README.md` Qwen 3x + Cybersec tables). *(effort: medium)*
- [ ] **[storage] Define a per-node cache budget and its enforcement** — decision-lane four arms ~44 GB/node with one servable; embed/rerank variants +16 GB/node; no mechanism keeps only the active arm resident *(Owner decision 2026-10-15: active-arm-only residency — reclaim a lane's weights when its arm is switched; the archived-pack census sets the reclaim list.)* (`attic/decision/DECISION-MODELS-RESEARCH.md`; `recipes/embed/README.md:98-124`). *(effort: long)*

## Node hygiene
- [ ] **[storage] Decide the fleet runtime-cache position** — `~/.cache/sparkrun/runtime-cache` holds ~3.1 TB of prepared model trees across the six nodes (`.30` 294 GB, `.31` 248 GB, `.32` 787 GB, `.33` 787 GB, `.34` 546 GB, `.35` 450 GB). It is a sparkrun-managed cache rebuilt on the next boot, and the directory suffix is derived by sparkrun core, so the three same-model `deepseek-ai/DeepSeek-V4.1-Flash-*` trees on the head (95 GB + 48 GB) and the `Mia-AiLab/…EXL3-2.9bpw` tree (100 GB) cannot be split live-vs-stale from the docs alone (`9a74d993` is cited; the Mia-AiLab trees back cybersec arm 5). Either find sparkrun's prune path or accept a cold-boot rebuild, then reclaim. *(effort: medium)*
