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

# DECISIONS — 5 open (2026-10-15)

New owner questions land here, each with a `→ Answer:` line. Numbered decisions cited elsewhere —
#6 in `attic/qwen4/SELECTION-RANKING.md`, #11 in `attic/decision/DECISION-MODELS-RESEARCH.md`,
#10/#11/#14 in `attic/explore/EXPLORE-MODELS-RESEARCH.md` — live in git history: the 2026-10-11
register is `git show 8a98379:mad-science/TODO.md`; the 2026-10-14 registers (#16–#23, #24–#27) are
the pre-fold states, `git show baecfa8:mad-science/TODO.md` and `git show c7c7a81:mad-science/TODO.md`;
the #28–#33 register is the pre-fold state `git show 0d8014d:mad-science/TODO.md`; the #34/#35 register
(2026-10-15, answered the same day) is `git show 043fbae:mad-science/TODO.md`.

**Q1 — the `🚀 fast` threshold vs the labquant arms.** The flag taxonomy (`recipes/README.md`
§Model Flags) defines `🚀 fast` as *C1 Fast (>= 50 t/s avg)*, but `…-labquant-sglang` carries `fast`
and its index row reads 40.3 (the revived highcon arm inherits the same tag). The threshold was
written for single-node arms; both these are TP=2, and a 180B MoE at 40 t/s across two nodes is a
judgement call, not a measurement. Re-word the taxonomy (e.g. per-node-count bands), retag the arms,
or leave `fast` as an owner's-eye call?

→ Answer:

**Q2 — the four warm-but-superseded DS4.1 runtime-cache lobes.** `.30`-`.33` carry
`deepseek-ai__DeepSeek-V4.1-Flash-9a74d993` trees (47.7/47.7/142.1/142.1 GB) whose leaf key no shipped
recipe can produce (the recipe pins `5254448103…`, producing `…-11826f49`); markers read
2026-10-13T11:13 and the four trees total **379.6 GB** (47.67 + 47.67 + 142.08 + 142.08 GiB, re-measured
2026-10-15). Two different gates hold them: this repo's 72 h in-use rule lets go on 2026-10-16 11:13,
while sparkrun's sweep is a marker-age-in-**days** test whose 30-day default would not reach them until
~2026-11-12 (`--older-than 3` would take them today). Take them now, wait for the 72 h rule, or wait
for the default sweep? (`mad-science/STORAGE-POLICY.md` §2/§5.)

→ Answer:

**Q3 — the AEON-7 clause, and whether the three 27B packs' licences get written into the docs.** All
three packs (RadixArk, AEON-ULTIMATE-UNCENSORED, orcarouter-Uncensored) declare Apache-2.0, but the
AEON repos ship **no LICENSE file** and upstream AEON-7 attaches a "User Responsibility & Arbitration
Clause" triggered by "merging, quantizing, distributing". We redistribute nothing today (pull-only).
Should the clause be carried into any future derivative we publish, and should each pack's licence
verdict be recorded in the lane docs / index rows?

→ Answer:

**Q4 — active-arm-only residency on `.34`, and which arm is the lane's active one.** The budget
position (`STORAGE-POLICY.md` §3) makes residency a per-node call: reclaim a lane's weights when its arm
is switched. On `.34` the decision lane holds 45.3 GB across four shipped arms with one servable
(active-arm-only frees 26.2-42.3 GB) and the embed/rerank tier switch costs +15.0 GB/node. Which arm
should stay resident on `.34` when nothing is running?

→ Answer:

**Q5 — should the registry ship a pooling ladder profile pair?** `plugins/pooling_bench_framework.py`
makes a pooling sweep runnable as `sparkrun benchmark pooling <recipe> --profile <file>`, but the
profile shape differs per arm (`kind`, `dimension_check` 2048 for the 2B vs 4096 for the 8B AWQ,
`docs_per_query`), so the contract is documented in `tools/README.md` and no profile was added. Ship
`benchmarking/pooling-ladder-embed.yaml` + `-rerank.yaml` (five lines each, shapes already recorded),
leave profiles per-lane, or fold the shape into the framework's defaults?

→ Answer:


# TODO list

*(2026-10-14 documentation sweep — six parallel lane/registry scouts over `recipes/**`, `attic/**`,
`benchmarking/`, `tools/`, and the `mad-science/` memos. Every item below carries `path:line` evidence
and an effort tag; boot-requiring work is the long tail. The per-lane "all items completed" stubs were
dropped where the sweep opened new work.)*

*(Owner decision 2026-10-15: the sweep runs with no timebox — multi-day, group by group, stopping
only at a gate; the register is the scope, not a plan.)*

**Resourcing (2026-10-15).** `.34`/`.35` only for this sweep *(Owner decision 2026-10-15: no TP=4 window
this session, so the multi-node items in the lanes below and the ornith 397B re-run stay deferred;
`.30`–`.33` are busy with the ds4 TP=4 job)*. Every `sparkrun` call runs from
the head with the HOME override and `--transfer-mode local`, and **the registry clone must be
refreshed first** (`sparkrun registry update littlecedar`) after any recipe or lane-mod change: the clone
sat two commits behind and carried no lane-local `mods/`, which made an `@littlecedar/…` launch of the
ornith 35B die with `Could not resolve mod 'mods/ornith-honed-chat-template'` (2026-10-15). It was
refreshed that day and now materializes the lane mod — re-check after each push. For the same reason, launch a recipe by its
real path — never a flattened `~/development/<name>.yaml` symlink. Only two orderings are asserted: the
RadixArk reclaim on `.34` is tagged *immediate* (126 GiB resident against the owner's cache policy), and
the ornith 35B is the first arm of the standard-suite sweep.

Selection priorities:
- Node count (lower is better)
- Accuracy (higher is better)
- Speed (higher is better)
- Memory footprint (lower is better)
- *(Owner decision 2026-10-11: this weighting is confirmed; attic moves only if warranted, folded into each lane's quality/selection pass — no global end-of-session sweep.)*

## ds4
DeepSeek V4.1
- [ ] **Ship TP=2 vision** *(2026-10-15: the Engram side of the vision boot is settled — the combined repo carries the tables at `<snapshot>/engram/` on both `.34` and `.35` (2 x 94.4 GiB each), which is the layout the launcher's resolver prefers (`launcher.py:101-104`), so the arm boots with engram, not the degraded configuration. The launcher mod's legacy-dir-only check that logged `Engram: none … (degraded)` on a fully staged node was fixed to report the real home (commit `a884dee`). Vision itself is fail-closed in the launcher, so only engram could have degraded silently.)* *(code shipped 2026-10-15 in commit `2374680`: opt-in `--vision` + `vl_bias.safetensors` inside `mods/tensorfold-dsv41-launcher`, recipe passes it; the deliberate boot receipt is pending — the "shipped = bootable" rule)* — proven on our hardware ("supported and now proven … but not shipped"): a two-part change (`--vision` + the 43-tensor `vl_bias.safetensors` folder); the recipe still refuses `image_url` with HTTP 400 (`attic/ds4/AGENTS.md`). *(Owner decision 2026-10-15: next-window scope, on the free `.34`/`.35`.)* *(effort: short)* *(in flight 2026-10-15: the pinned `littlecedar/dgx-spark-dsv41@sha256:fabbe861…` resolves in the registry and is being pulled to `.34` and `.35` now — pull logs in `~/benchmarks/_image-pulls-20261015/` on each node; boot queued behind the 27B TP=2 window.)*
- [ ] **Run the two KNAPCIO post-pin defer experiments as tracked A/Bs** — `DSV41_CACHE_GIB=0` (third-party +9% KV pool; shipped value is 4 GiB) and the `SGLANG_RUST_BUILD_MODE` cargo-probe boot-hang workaround (`mad-science/KNAPCIO-UPSTREAM-DELTA.md:49,56`; `recipes/ds4/mods/dsv41-sglang-overlay/launcher.py:116,162`). *(effort: short)*
- [ ] **RoCEnante coverage sweep + auto-crossover microbench** — the memo's §5 E3/E5 ("actually worth running"): do TP all-reduces/gathers >2 MiB silently fall back to NCCL (`SGLANG_ROCE_MAX_SIZE` 4/8 MiB vs shipped 2 MiB), and the 1 KB…2 MiB RoCEnante-vs-NCCL crossover curve (none measured) (`mad-science/CUSTOM_ALL_REDUCE_SM120_EXPERIMENTS.md:166-196`). *(effort: medium)*
- [ ] **Re-test `DSV41_CERT_HEAD` / `DSV41_ENGRAM_DRM_NODE`** — both named and deliberately off (CERT_HEAD −0.5 ms/step at c1 but slower from ~10 requests; ENGRAM_DRM_NODE needs a host display-reserve change) (`attic/ds4/AGENTS.md`). *(effort: medium)*
- [ ] **DSpark verify-window γ=3** — only γ=2 vs γ=5 was A/B'd; the fork's own baseline point (γ=3) was never measured on this lane (`recipes/ds4/mods/dsv41-sglang-overlay/launcher.py:140-158`). *(effort: short)*
- [ ] **[storage] Collapse the DS4.1 EXL3 duplication** — *(Owner decision 2026-10-15: combined repo everywhere — cybersec arm 5 grafts onto the combined `littlecedar/…-EXL3-2.9bpw-with-engram` pack and drops `dsv41-engram-fetch`; the changed arm needs a re-boot receipt.)*; per node serving both lanes the same ~197 GB weights + ~189 GiB Engram tables exist twice (`recipes/ds4/deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml`, `recipes/cybersec/README.md`, `recipes/cybersec/mods/graft-dsv41-ablit-wo-b/README.md:17-19`). *(effort: medium)*
- [ ] **Pin the TP=2 arm's checkpoint revision** — `recipes/ds4/deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml` carries **no** `model_revision` at all, so the arm serves whatever `littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram`'s `main` is at launch; today's snapshot on both `.34` and `.35` is `48afcd1c4f2d73594d9d496b9f7bbb4559ddb9e8` (measured 2026-10-15). Plain `validate` passes and `--strict` does **not** flag it (its only finding is the `metadata.model_dtype 'exl3'` suggestion), so the drift-prevention convention has no machine check here. Either pin the SHA the receipts actually ran against or state the reason the arm stays unpinned. *(effort: short)*

## glm5
GLM 5.3
- [ ] **Promote the GLM-5.3-Flash EXL3 4bpw TP=4 line to a recipe** — boot-verified 98.4 t/s @ d0 (2.7× the 3.0bpw route) with a pre-built engine image (`tensorfold-glm53:v0.6.0`); blocked only on the three-file deliverable (baked image + a `tensorfold-glm-exl3-launcher` mod + the `runtime: sglang` shim) (`recipes/glm/README.md` §runbook bullets 3–5; `attic/glm/GLM-5.3-RECOMMENDATIONS.md`). *(effort: medium)*
- [ ] **Promote the EXL3 3.0bpw full-753B lane to a recipe** — the only full-model option that fits TP=4 (35.67 t/s measured); same three-part blocker, needs a source image build first (`recipes/glm/README.md` §"Revision pins"). *(effort: medium)*
- [ ] **Measure the EXL3 3.0bpw 1M arm** — `TF_GLM_DCP=4` + `TF_GLM_EXTENTS=1` documented from repo A but never measured here (`attic/glm/GLM-5.3-RECOMMENDATIONS.md`). *(effort: medium)*

## ornith
Ornith 1.5
- [ ] **Build a YaRN long-context (~1M) arm** — both Ornith cards publish the factor-4 route and the shipped arms cap at 262,144, with no needle evidence **above** 262,144 (32k 3/3, 128k 3/3 and 262,144 2/3 are recorded) ("named work nobody did") (`recipes/ornith/README.md:195-202`; `attic/ornith/AGENTS.md:270-273`). *(effort: medium)*
- [ ] **Retry the 397B DFlash head with prefix caching intact (or fewer spec tokens)** — the recorded ~12% loss is partly a structural confound (vLLM treats every Mamba group as the draft group, disabling prefix caching); only n=8 was tried (`attic/ornith/AGENTS.md:324-328`; `recipes/ornith/README.md` §397B). *(Owner decision 2026-10-15: deferred — needs a TP=4 window on the restricted `.30`–`.33`.)* *(effort: medium)*
- [ ] **Re-verify the 35B serve line on the SGLang 0.5.18→0.5.21 bump** — a named perf lead (DFlash-reranker + GDN fusion wins) that currently breaks the lane (`attic/ornith/AGENTS.md:883-886`). *(effort: medium)*
- [ ] **`moe_runner_backend: marlin` under an interleaved paired control** — the ladder's best extra cell (108.9 t/s) collapsed into noise only because the control was ordered, not interleaved (`attic/ornith/AGENTS.md:497-513`). *(effort: short)*
- [ ] **Measure the r0b0tlab W4A16 NVFP4 35B + MTP head** — 63–77 t/s claimed with accuracy parity; rejected on a paper comparison, never measured on our stack (`attic/ornith/AGENTS.md:881-882`). *(effort: short)*

## qwen3
Qwen 3.x
- [ ] **Boot the 27B TP=2 arm with the now-shared `@littlecedar/mods/fix-fastsafetensors-tp2-sglang`** (promoted from the lane-local `recipes/cybersec/mods/` copy 2026-10-15) — the lane's self-declared "Highest value" open item (TP=2 halves weight-read time); the fix mod has never been run (`attic/qwen3/AGENTS.md:166-169`; `attic/qwen3/NOTES.md` §4 WP1). *(Owner decision 2026-10-15: next-window scope, on the free `.34`/`.35`.)* *(effort: medium)* *(in flight 2026-10-15: the first TP=2 attempt died on the fix mod's anchor drift against the then-current `lmsysorg/sglang:dev-cu13` — upstream moved the buffer-release anchor, so the mod failed closed; re-anchored with a candidate-per-shape mechanism and regression-tested in `37e5b00`, guard `tests/test_fix_fastsafetensors_tp2_mod.py`. A TP=1 headline boot of the promoted chain runs on `.35` (Qwen27Suite); the TP=2 boot is queued behind it on `.34`+`.35`.)* *(measured 2026-10-15, re-anchored chain, `.35`, image `lmsysorg/sglang:dev-cu13` `c802d7b6`: the buffer release is load-bearing at TP=1 -- target load 41.90 -> 20.59 GB, draft 7.41 -> 3.78 GB, mamba cache 161/163 -> 252 with the `capped to 40` clamp gone, granted concurrency 40 -> 48 (the literal, in full), fp8 KV pool 213-222k -> 497,878 tokens, and the 262,144 needle probe now 3/3 where both leaky boots truncated at ~209k counted prompt tokens; eval-suite on the same boot: hard arc 93.5 % / gsm8k 96.0 % (n=200 each), house 19/19 + 18/18, contract ok. Deltas recorded in the mod README `mods/fix-fastsafetensors-tp2-sglang/README.md` §Measured effect.)*

- [ ] **Re-check the 27B arm's mamba/knob tuning under the fixed loader** — the 2026-10-15 re-anchored boot moved every capacity number the arm's knobs were tuned against (KV pool 213k -> 497,878 tokens, no mamba clamp, 48 granted; `mamba_full_memory_ratio: 3.51` is stored as "the optimum is interior and MOVES with context length -- ask before changing" and was measured under the leaky loader). Also stale-as-written until the lane lands its re-measure: the recipe comment's `capped to 21` claim, `recipes/qwen3/README.md:29`'s "TP=1 only ... 262,144 ctx" line, and `attic/qwen3/AGENTS.md` §7's "`max_num_seqs: 48` — never granted" bullet. *(effort: short)*

## qwen4
Qwen 4.x (and 3.8 Flash Next)
- [ ] **Revive `…-labquant-highcon-…` in a k≥16 aggregate window** *(recipe revived 2026-10-15 in commit `a8b1dec` — `recipes/qwen4/qwen3.8-flash-next-nvfp4-labquant-highcon-sglang.yaml`, re-pinned `6c01ac37`, vision-tower mod dropped, validates + renders `--tp 2`; the k≥16 window boot is pending, on the free `.34`/`.35`)* — dominated on one axis only; it is the sole holder of the aggregate-throughput regime (`attic/qwen4/ARMS-MANIFEST.md:118`; `attic/qwen4/AGENTS.md`). *(Owner decision 2026-10-15: next-window scope, on the free `.34`/`.35`.)* *(effort: short)* *(in flight 2026-10-15: the pinned `lmsysorg/sglang:dev-cu13-qwen38-next-local@sha256:9d2a843c…` resolves in the registry and is pulling to `.34`/`.35` — the "image absent on nodes" blocker is cleared; the k≥16 window is queued behind the 27B TP=2 boot.)*
- [ ] **Pass the 1M needle gate for `…-labquant-longctx-…`** — the archived long-context route's missing prerequisite ("quality above 262k is still UNMEASURED") (`attic/qwen4/AGENTS.md`). *(effort: medium)*
- [ ] **Run the W4 `#37111` release soak (1–2 h / ~100k)** — only a short smoke ran, so the corruption gate is unproven (`attic/qwen4/AGENTS.md`). *(effort: medium)*
- [ ] **One-boot `--enable-linear-replayssm-spec` test** — the lane's "most promising un-measured memory lever" (`attic/qwen4/NOTES.md` Open questions). *(effort: short)*
- [ ] **Clear the remaining qwen4 measurement backlog** — TP=4 (W6) re-boot after the `port_timeout_s` fix; the W12 cross-runtime vLLM same-checkpoint bench; the `--fp4-gemm-backend` A/B (the shipped `flashinfer_cutlass` was inherited without justification); `--enable-int8-mamba-checkpoint`; and the bs>1 cost of `--cuda-graph-backend-prefill disabled` (`attic/qwen4/AGENTS.md` §10.1). *(effort: medium)*
- [ ] **Retire or resolve the shipping diagnostic** — `diag-qwen4-unplaced-scales` ships only because the shared-expert scale blocker is unexplained, and the `demote-labquant-narrow-mxfp8-to-bf16` `EXTRA_LEAVES` knob stays for an unresolved QSA-prefill CUDA-graph crash (`attic/qwen4/AGENTS.md` §10.1; `recipes/qwen4/mods/demote-labquant-narrow-mxfp8-to-bf16/README.md`). *(effort: medium)*

## ifm
IFM K2-Horizon
- [ ] **Pass the 7B `fp8_e4m3` KV accuracy gate** — throughput is measured, quality is not, so the ~+6% d8192 win is unusable (`attic/ifm/NOTES.md` "Still open"; `recipes/ifm/README.md:111`). *(effort: short)*
- [ ] **Re-open UNO on the 0.9B** — `IFM/K2-Horizon-0.9B-Uno` exists and the gate mod already works for the 7B; the register was falsified for the 7B only (`attic/ifm/AGENTS.md` §9). *(effort: medium)*
- [ ] **Attempt 7B tree-mode UNO (topk>1)** — a second UNO geometry, never booted (linear is shipped) (`attic/ifm/NOTES.md` "Still open"). *(effort: medium)*
- [ ] **Decide the withdrawn 36B-A4B sub-lane** — the D2 numerics gate (a precondition, never executed) plus the ranked, never-run E-series arms (E5 fp8-gemm-backend, E7 page-size, E8 value-expert quant mod, E10 fp8-KV+TP2) (`attic/ifm/K2-36B-A4B-MODEL-OPTIMIZATION-WORK.md:496-501`). *(effort: long)*

## embed
Any embed model
- [ ] **Boot-verify the three-way co-location** (decision + embed + rerank on one node) — asserted in the budget math and in the lane README, never receipted (`recipes/decision/README.md` §Operating constraints; `attic/decision/AGENTS.md`). *(effort: short)*
- [ ] **Ship or retire the unquantized 8B BF16 encoder tier** — measured within 1.2% prefill of the shipped AWQ 4-bit, ships nowhere (scratch recipe only) (`recipes/embed/README.md`; `attic/embed/AGENTS.md`). *(effort: short)*

## rerank
Any rerank model
- [ ] **8B reranker residency — DECIDED 2026-10-15: keep shipped, no pre-cache** — `qwen3-vl-reranker-8b-vllm-b12x` stays a shipped recipe (primary index + lane README) as the deliberate non-`fast` quality tier (~4× slower per scored document than the 2B) and is **not** pre-cached: the +16 GB/node is a cold-fetch cost, not a residency. Residual work: write that position into `recipes/rerank/README.md` and `attic/rerank/AGENTS.md` §8B so the question cannot reopen. *(Owner decision 2026-10-15: keep shipped, do not cache.)* (`recipes/rerank/README.md` §Shipped recipes; `attic/rerank/AGENTS.md` §8B reranker (quality tier)) *(effort: short)*

## decision
Any decision model
- [ ] **Build the named decision candidates** — `Decision-2.0-Nox-4B` (best-scoring 4B, never booted), `laya` (CPU-real, zero-GPU), `kev-0.8b`, `GLiNER2.5-Decide`, `d3-edge`, `JEV-27B`, and the Sol-2B GGUF/llama.cpp CPU path (avoids the vllm-srun kill-shim workaround) (`attic/decision/DECISION-MODELS-RESEARCH.md`). *(effort: medium)*
- [ ] **Build the TTS fourth co-tenant** (Kokoro-82M, 0.305 GiB on the A725 cores) — the co-location budget is quoted net of it, but it was never built (`attic/decision/DECISION-MODELS-RESEARCH.md`). *(effort: medium)*

## explore
Any model with reasoning and tool-calling capabilities
- [ ] **Build the top-ranked unbuilt reasoning candidates** — `Mistral-Small-4-119B-NVFP4` (rank 1; MLA backend question — `VLLM_MLA_DISABLE=1` caps ~40k/64k), `Muse-Glimmer-30B` (rank 2; blocked on unmerged vLLM PR #51655), `Nemotron-3-Super-120B-A12B-NVFP4` (rank 4); licence/availability-blocked: MiniMax-M3 (non-commercial), MiMo-V2.6-Flash-RL (no quant), Inkling-Small (unpublished active params); plus `IFM/K2-Horizon-375B-A23B` (`mad-science/EXPLORE-CANDIDATES.md:16-57`; `attic/explore/EXPLORE-MODELS-RESEARCH.md`). *(effort: long)*
- [ ] **Build the Laguna-M.1 2-node ceiling reference** — named then dropped; the family's only 2-node datapoint is third-party (`attic/explore/EXPLORE-MODELS-RESEARCH.md`). *(effort: medium)*
- [ ] **Exercise the media-gen cells left unrun** — LTX-2.5's I2V + FLF2V templates and the 4K/50 fps preset; Qwen-Image non-8-step schedules and 2048²; and the faster vLLM-OMNI engine route (40 vs 54 s on the base model) (`attic/explore/EXPLORE-MODELS-RESEARCH.md`). *(Owner decision 2026-10-15: next-window scope, on the free `.34`/`.35`.)* *(effort: medium)*

## cybersec
Cybersecurity-research (red-team) abliterated / uncensored models
- [ ] **Wire MTP spec decode onto the clean 27B arm** — its BF16 MTP head is preserved and the sibling lane measures 33.8 t/s vs this arm's 10.2 (`attic/cybersec/AGENTS.md`). *(Owner decision 2026-10-15: next-window scope, on the free `.34`/`.35`.)* *(effort: medium)*
- [ ] **Unblock the two cybersec negatives via their card-documented vLLM routes** *(2026-10-15: both routes now ship as recipes — `nex-n2.5-mini-uncensored-nvfp4-vllm.yaml` and `qwen3.8-flash-next-uncensored-nvfp4-vllm.yaml`, pinned `9f11be0e`/`cd56f6c1`, `--quantization compressed-tensors` on the resident `dgx-vllm-eugr-nightly@sha256:7717585a…`; commit `202f482`. The distribution gate that blocked them is superseded (direct pull measured 76–142 MB/s). Weights pre-staged on `.34`/`.35` 2026-10-15 (`~/benchmarks/_prefetch-20261015/`, 23.95 GB + 183.54 GB on **both** `.34` and `.35`, verified complete; index rows still gated on a boot receipt.)* — arm 3 (`nex-n2.5-mini-uncensored-nvfp4-sglang`; SGLang NaN sample-time logits) via its image-distribution route; arm 4 (`qwen3.8-flash-next-uncensored-nvfp4-sglang`; SGLang's compressed-tensors loader refuses the export's scheme) via the `qwen4_exp` route, whose sole measured obstacle is the ~0.3 MB/s OCI relay. **Their index rows return only on a boot receipt** — they were dropped on 2026-10-14 when the index adopted *shipped = bootable and usable*, while the files stayed in `recipes/cybersec/` *(Owner decision 2026-10-15: unblock both; retirement to `attic/cybersec/` rejected — the reconcile item folded in here.)* (`recipes/cybersec/README.md:86-122`; `attic/cybersec/AGENTS.md` §8; `recipes/README.md:109-113`; precedent `recipes/glm/README.md:18-24`) *(effort: long)*
- [ ] **[storage] Test whether the uncensored deltas are graftable as sidecars** *(2026-10-15: `STORAGE-POLICY.md` §4 answers the same question for the 27B trio — packs from different quantisers cannot be deltas of each other, the sidecar would be the whole pack — and arms 3/4 have the same shape. What this item actually wants is a same-quantiser delta export from the uploader, which is a work item, not a storage decision.)* over the cached bases instead of shipping ~184 GB / 25 GB full exports *(Owner decision 2026-10-15: case-by-case on licence — graft only where the base's licence clearly permits redistribution; keep the full export otherwise.)* (`recipes/cybersec/README.md:176-179`). *(effort: long)*

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
- [ ] **Fill C2/C5/C10 for the single-node text arms** *(ornith 35B done 2026-10-15: C2 158.2 / C5 220.4 / C10 249.9 t/s @ d0, σ 6.2/10.0/4.6, `bench_8c7486cad451`; 9B in flight)* — the 14 that fit one Spark (ornith 35B/9B, qwen3 dflash2/coder-next/mlx4bit-TensorFold, IFM 0.9B/7B, explore ling/kolibri/laguna-XS/laguna-S/humanizer, cybersec arms 1/2) on the free `.34`/`.35`; per cell quote the **decode** row of the `--output` file (never the printed table, which shows only that row and no header) and cite the receipt beside the number in `recipes/README.md` and the lane doc. *(effort: long)* *(progress 2026-10-15: IFM 0.9B (C1 80.4 / C2 181.6 / C5 317.6 / C10 503.9) and 7B (31.3 / 56.1 / 94.0 / 126.0) done — receipts `~/benchmarks/ifm-{09b,7b}-ladder-20261015/`, docs in `recipes/ifm/README.md` + `attic/ifm/NOTES.md` (commit `84aa52f`); remaining single-node arms: qwen3 ×3, explore ×5, cybersec ×2.)*
- [ ] **Fill C2/C5/C10 for the multi-node arms** — ds4 knapcio (TP=4) + ds4 tensorfold (TP=2), qwen4 labquant (TP=2), ornith 397B (TP=4), cybersec arm 5 (TP=2): needs a window on `.30`–`.33`, restricted today. *(effort: long)*
- [ ] **Re-measure the pooling lanes at the ladder points** *(2026-10-15: the runnable form is now `sparkrun benchmark pooling <recipe> --profile <pooling profile> [--skip-run]` (`benchmark run` also works; `benchmark performance` refuses — the category's framework is set before the profile is read); receipts are per-cell `runs/NNN_{kind}_c{k}.json`. `kind` is required. See `tools/README.md` §`plugins/pooling_bench_framework.py`.)* — embed/rerank publish `units/s` at C1/C4/C8/C16/C32 (`tools/pooling-bench.py`); re-run at c 1/2/5/10 and quote `units / wall_seconds` from the receipt. (`recipes/embed/README.md`; `recipes/rerank/README.md:69-70`; `.scratch/embed/csweep8b-order1-c*.json`) *(effort: medium)*
- [ ] **Give the two non-t/s lanes a ladder or a documented `—`** — the decision arms report `req/s` from a *serial* instrument (`tool-eval-bench`), so filling C2/C5/C10 there needs a concurrent harness; the image arm serves one request at a time, so its `—` should be written down as by-design in the lane doc. (`recipes/decision/README.md`; `recipes/explore/README.md`; `tools/README.md`) *(effort: medium)*

**Landed 2026-10-15 (parallel slices).** *(GLM 5.3 TP=4 arm `34a2a2f` — boot deferred to a `.30`–`.33`
window; cybersec arms 3/4 vLLM routes `202f482` — receipts owed; ornith 35B YaRN 1M arm `8bfb62d` —
gate pre-registered in `attic/ornith/NOTES.md` §8; pooling `BenchmarkingPlugin` + the silent-skip
correction `6801c41`; storage positions + `tools/cache-audit.py` `1d7d4ad`; the Engram log fix
`a884dee`. Still in flight at that hour: the decision lane's Kai-0.6B boot on `.34` with its
`decision-ensemble.py`/`decision-ladder.py` productization, the qwen3 27B re-anchored suite on `.35`,
and the two cybersec arms' weight prefetch (`.34` complete, `.35` running,
`~/benchmarks/_prefetch-20261015/`). Nothing is claimed done until its receipt or doc edit is
verified.)*

## Standard evaluation suite (registry-level)
- [ ] **Run the standard suite against every shipped arm** — the SOP pass (`tools/eval-suite.py`, then the `benchmarking/concurrency-ladder.yaml` leg `--skip-run` on the same boot, then `benchmarking/standard-suite.yaml` where the arm serves tool calls) for each shipped recipe; receipts under `~/benchmarks/<lane>-<date>/`, numbers into the lane docs and the index with their receipt/bench id. This is the sweep that fills the C2/C5/C10 cells above and each lane's unmeasured accuracy cells; start with the ornith 35B and work the free `.34`/`.35` window. *(effort: long)* *(progress 2026-10-15: ornith 35B done; IFM 0.9B/7B ladders measured; a decision-lane slice is in flight on `.34` (ensemble productization + the lane's ladder position); qwen3 27B headline pass running on `.35` by the qwen3 lane.)*

## Storage consolidation (registry-level)

## Node hygiene
