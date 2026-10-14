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

# DECISIONS — 8 open (2026-10-14)

New owner questions land here, each with a `→ Answer:` line. Numbered decisions cited elsewhere —
#6 in `recipes/qwen4/SELECTION-RANKING.md`, #11 in `recipes/decision/DECISION-MODELS-RESEARCH.md`,
#10/#11/#14 in `recipes/explore/EXPLORE-MODELS-RESEARCH.md` — live in git history: the 2026-10-11
register is `git show 8a98379:mad-science/TODO.md`. New items continue that register's numbering
(from #16) so those historical references stay unambiguous.

16. **Session nodes.** Which nodes are ours this session? The backlog assumes up to four: the 397B
    DFlash-vs-MTP A/B (4 nodes), the ds4 TP=4 revision/build items, and any glm5 revival need
    `.30-.33`, which host the production ds4 TP4 serve; only `.34`/`.35` are free while that serve
    is up. Confirm whether `.30-.33` are free again (the 2026-10-13 window had all six idle) or
    whether this session is `.34`/`.35` only — so the 4-node/TP4 items are marked blocked vs runnable.
    → Answer:

17. **Off-brief / new-runtime arms — in scope this session?** The queued `Qwen-Image-2.1-Turbo`,
    `LTX-2.5` (media-gen) and `humanizer-12B` arms sit **outside the explore lane's reasoning/
    tool-calling brief**, and each needs a runtime class sparkrun has never shipped (diffusers /
    ComfyUI script launcher; a byte-exact `/v1/completions` prompt). Pursue them in this session
    (each will consume a large slice of it), or defer to a separate research pass?
    → Answer:

18. **Non-commercial / `other` licences.** This registry ships to third parties.
    `Qwen/Qwen-Image-2.1-Turbo` is `qwen-research` ("FOR NON-COMMERCIAL PURPOSES ONLY") and
    `poolside/Laguna-S-2.1-DFlash(-NVFP4)` carries `license: other` (text unread). Decision #4
    (2026-10-11) allowed the CC BY-NC-ND DFlash2 drafts on "non-commercial cluster use" grounds.
    For these arms: ship the recipe (a recipe ships a repo id, not weights — the downloader accepts
    the licence), keep it runbook/eval-only, or exclude it entirely?
    → Answer:

19. **Gated / red-team arms.** `Lightricks/LTX-2.5` (`gated: auto`, needs a browser terms-acceptance and
    a per-node `HF_TOKEN`) **and all five `cybersec`-lane arms** (`drowzeys/*` and `orcarouter/*` are
    `gated: auto` behind responsible-use agreements) cannot be assumed downloadable in a registry
    distributed to third parties. Ship gated arms as runbook/eval-only with a documented per-node token
    + acceptance prerequisite, or exclude gated arms from the shipped tree?
    → Answer:

20. **Media-arm acceptance criterion.** `EXPLORE-MODELS-RESEARCH.md` §6 proposes: a fixed prompt+seed
    set; one 1024² image at the checkpoint's shipped step count and one 5 s clip at the shipped
    preset; wall-clock per item + peak unified memory; quality judged by eye against the vendor
    gallery (no house scorer exists — `tools/synthetic_png.py` is a fixture). Confirm or replace.
    → Answer:

21. **Humanizer acceptance criterion.** §7 proposes: a fixed 20-draft set across genres × 2 samples,
    reporting fact-diff count vs the source (numbers/dates/names), formatting-drop count, and
    wall-clock per 1k output tokens; the card's Originality.ai figure cited, not reproduced in-house.
    Confirm or replace.
    → Answer:

22. **Ornith quality bar.** You are not convinced of Ornith 1.5's quality and want further
    experiments. What would confirm (or fail) it — a named long-horizon agentic workload, a peer
    comparison, or a threshold on the house battery? The 2026-10-13 logic-loop ticket was **NOT
    reproduced** (it was thinking-budget exhaustion, not a loop), so the target workload matters.
    → Answer:

23. **qwen4 lane cut.** Confirm the target is exactly two shipped arms — fastest single-node (the two
    TP=1 solo arms) and fastest two-node (the TP=2 set) — with the rest swept to `attic/`. Read
    literally, "1M context optional" means the Lane-B longctx arm may go even though it is the only
    1M route, and the RadixArk quality reference is swept if it is not the fastest. Confirm, or name
    any arm to keep regardless of speed.
    → Answer:

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
- cybersec

Selection priorities:
- Node count (lower is better)
- Accuracy (higher is better)
- Speed (higher is better)
- Memory footprint (lower is better)
- *(Owner decision 2026-10-11: this weighting is confirmed; attic moves only if warranted, folded into each lane's quality/selection pass — no global end-of-session sweep.)*

## General Registry Maintenance
- [ ] Build additional quality testing and benchmarking suites using established industry standard benchmarking tools where feasible.
- [x] **Serve every sglang arm under the upstream repo id, not the snapshot path (owner report 2026-10-13).** `ornith-1.5-35b-a3b-nvfp4-dflash2-sglang` currently advertises `/cache/huggingface/hub/models--ornith-ai--Ornith-1.5-35B-A3B-NVFP4/snapshots/94e431d9…` as its `model` id — wrong for clients, the proxy and any benchmark that sends the model id. Audit (13 shipped sglang recipes): **11 write `--served-model-name {model}`** (clef, Ling, ornith, qwen3.8-27B DFlash2, all five qwen3.8-flash-next arms, both ds4 shim arms) and **2 write no flag at all** (both IFM K2 arms — SGLang then defaults the id to the model path anyway) — nine of the eleven picked the spelling up in `0f41394` ("Add `--served-model-name` argument to all relevant recipes"): right intent, wrong operand, because `{model}` is the placeholder that gets rebound, so those nine lines must be *deleted* (not kept "for safety") when the declarative key goes in. Mechanism, already recorded in-repo: on a real launch sparkrun rewrites `{model}` *and a `--served-model-name {model}` rendered from the same placeholder* to the prepared on-disk path (`models/runtime.py::bind_runtime_models`, quoted at `mods/tensorfold-dsv41-launcher/launcher.py:176-182` and `tests/test_ds4_recipes.py:1290`), so the flag faithfully advertises the path. **`-n` does not show this** — it still prints the repo id; only a real launch rewrites the flag. **Fix pattern:** drop the hardcoded flag and declare `served_model_name: <upstream repo id>` in `defaults:` — the sglang runtime maps that key to `--served-model-name` and appends it when *absent* (`runtimes/sglang.py:47,372-376`; fill policy `runtimes/base.py:952-981` leaves an existing value intact, which is why the `{model}` spelling wins today). The vLLM lanes already use the declarative key (`explore/kolibri-1-78b-fp8-vllm.yaml`) and the root README documents the repo-id convention; the command-less path in `runtimes/sglang.py:533-535` already serves under `recipe.model`. **Per recipe:** drop/declare, then verify on a real launch — `GET /v1/models` (or `sparkrun cluster check --check-http-models`) must return the repo id; the CLI `--served-model-name` override can probe it live, but override *files* cannot set that key (`core/recipe_overrides.py:90`). Leave the two ds4 shim arms alone if their launcher path→repo-id normalization stays green (guarded today). Also correct the decision lane's "Served-id wart" note (`recipes/decision/README.md:45`) — it blames a missing flag, but the arm boots *with* the flag, so the value is the rebinding; and re-check any lane doc that quotes a path id. Done when every shipped sglang arm reports its repo id in `/v1/models` and no recipe carries the `{model}` spelling of the flag. **2026-10-13 progress (ornith):** `ornith-1.5-35b-a3b-nvfp4-dflash2-sglang` fixed + live-verified (boot `dadfb04b5145d956_8ed3ce77d78f` on `.34`: `/v1/models` → `ornith-ai/Ornith-1.5-35B-A3B-NVFP4`, chat addressed to that id 200; warm TTR port-open 94.7 s). It uses the declarative key **plus** `--served-model-name {served_model_name}` — sparkrun's prescribed spelling (`core/validation.py`'s hardcoded-flag suggestion: "Move the value to defaults.%s and reference it as {%s}") rather than delete-and-let-append: identical final argv (the append no-ops when the flag is present, `runtimes/base.py:931-933`), and it keeps the repo's `InertDefaults` guard green with no exemption. Recipe comment + lane `README.md`/`AGENTS.md` + a lane guard (`tests/test_ornith_honed_chat_template.py`) carry the fix. Remaining: ten `{model}`-spelling arms + the two no-flag IFM K2 arms (SGLang defaults those to the model path; `runtimes/base.py:979-980` makes the append conditional on the key existing). **2026-10-13 sweep complete (all ten + both IFM arms):** every shipped sglang arm now has live `GET /v1/models` evidence of its repo id — clef (`625b43fd997e4d5b_8ed3ce77d78f`, `.34`), Ling (`3effce2e30113dd9_64af2f7668b6`, `.35`), K2 0.9B (`e2b91b75cf01d3ab_8ed3ce77d78f`, `.34`), K2 7B-Uno (`ff7c9715c406eee7_64af2f7668b6`, `.35`), qwen3.8-27B (`3b78f3ef7df2980b_64af2f7668b6`, `.35`), flash-next ×2 (`1753bbfdf3f0a50e_3510a5e0d37d` TP2, `15adecfd945cac5c_8ed3ce77d78f` solo), labquant ×3 (`1895030211ea0500_3510a5e0d37d` TP2), tensorfold (`8ef9b6c9a550c389_3510a5e0d37d`; recipe unchanged — its launcher normalizes the path), knapcio (production serve `a4c699c1299bbbdf_8296561cc1cb` on `.30` answers the repo id; recipe unchanged). The three labquant arms also gained `--revision {model_revision}`: after the fix their only identity tokens are the declared literal and that revision flag — `validate_runtime_command` (branch 1 no longer fires: `--model-path` is the mod-built tree) needs both, boot-proven on `.34+.35`. Observed consequence: the three labquant arms share one cluster id (`name=<served>` folds into the intent hash), so `stop <id>` addresses whichever is current. Class guard `tests/test_recipe_placeholder_resolution.py::ServedModelNameNotRebound` (ds4 arms allowed by name, with the launcher reason); shape documented in `recipes/README.md` §Notes; lane receipts in each lane's docs.

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
- [ ] **A/B the first-party DFlash draft against the shipped jzinno DFlash2 draft (queued 2026-10-13).** The shipped draft is third-party — `jzinno/Ornith-1.5-35B-A3B-DFlash2` (`9b4852c0…`, 2026-08-23, Apache-2.0, `DFlash2DraftModel`, 1.05 GB, unpinned) — and the vendor published its own two weeks ago: [`ornith-ai/Ornith-1.5-35B-A3B-DFlash`](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B-DFlash) (`942d20fe…`, created 2026-09-20 / last pushed 2026-09-28, MIT, ungated, plain `DFlashDraftModel`, 0.77 GB) with **no published numbers**, so the lane's "unmeasured candidate" note (`recipes/ornith/README.md:246-248`) becomes a measurement. Same-node A/B on the shipped arm, one boot per arm, decode-phase rows only, n=5 per cell; baseline is the 2026-10-13 `decode-triage.yaml` C1 re-measure — **99.6 t/s @ d0 (σ 9.1), 100.2 t/s @ d8192 (σ 3.9)**, `.35`, receipts `~/benchmarks/ornith-c1-20261013/`. The card's SGLang snippet pairs the draft with `--speculative-dflash-block-size 8` — a flag sparkrun has no mapped key for (only `speculative_dspark_block_size` exists; write a literal only after confirming the pinned image's sglang accepts it) — and the card pins SGLang **= 0.5.18** exactly, so the lane's upstream-0.5.21 mamba-arg warning applies (`recipes/ornith/README.md:253-256`). Sweep n ∈ {4 = shipped default, 8} on the official draft one knob per arm (the jzinno draft already lost ~19% at n=10 in the 2026-10-11 ladder), not the full card config. Ship only a delta that clears boot noise (d0 σ ≈ 9 t/s) and run the house battery once on the winner (jzinno arm: 37/37). Either way **pin the winner's draft**: `speculative_draft_model_revision: <sha>` in `defaults:` (`942d20fe…` official / `9b4852c0…` jzinno) — distribution-only, read by `runtimes/sglang.py::_detect_speculative_draft_revision` (sparkrun's pin audit carries a separate draft-revision check, `api/_pin.py:164`, for the vLLM spelling) — and the 2026-10-13 floating-pins audit lists the draft (`SESSION-RECORD.md:104`). Boot hygiene per arm: node cleared (`docker ps -q | wc -l == 0`) and serve log asserts `Mean acceptance length > 1` — an accept ≈ 1 boot is a misconfiguration, not a loss. Update `recipes/ornith/README.md`/`AGENTS.md` + the recipe comment (draft snapshot line) with the numbers. Done when one draft is pinned and the C1 delta is a receipt.
- [ ] **Scope and measure a `9B-NVFP4 + DFlash` arm (new arm — queued 2026-10-13).** The collection (`ornith-ai/ornith-15-dflash`, last updated 2026-09-29) ships three first-party heads; the 9B pair is unshipped and unmeasured anywhere in the registry (no 9B recipe, no lane mention): target `ornith-ai/Ornith-1.5-9B-NVFP4` (`155f200d…` main, 2026-08-26, MIT, ungated, **8.8 GB** of weights) + head `ornith-ai/Ornith-1.5-9B-DFlash` (`21be3446…`, 2.58 GB, `DFlashDraftModel`, hidden-state taps 1/5/9/13/…/29 of a 32-layer target, MIT, ungated, **no published numbers**). The card calls the target a **dense ~9B** (≈19 GB bf16) and it is **multimodal** (`preprocessor_config.json` in the repo), so the arm is 1 node / TP=1 with no MoE or Mamba knobs — drop every `mamba_*`/`moe_runner_backend` line when copying the 35B arm, and **do not** reuse `@littlecedar/mods/ornith-honed-chat-template` (that template is the 35B's honed artifact; check what the 9B ships and whether it needs its own). Card launch: SGLang = 0.5.18 `--speculative-algorithm DFLASH --speculative-draft-model-path <dir> --speculative-dflash-block-size 8` (flag existence in our pinned image is the same open question as the 35B A/B above), or vLLM ≥0.20.2 `--speculative-config '{"method":"dflash","model":…,"num_speculative_tokens":8}'` — pick SGLang to match the shipped DFlash arm unless the image blocks it. Pin both repos (`model_revision: 155f200d…`; draft via `speculative_draft_model_revision: 21be3446…`, distribution-only), follow the standard hygiene (node cleared, serve-log `Mean acceptance length > 1`, `/v1/models` = repo id — the class guard `ServedModelNameNotRebound` polices the new sglang arm), then record C1 (`decode-triage` d0/d8192) + the house battery and compare against the 35B (99.6/100.2 t/s, 37/37) to decide whether a 9B slot is worth shipping. Done when the arm has a boot receipt + numbers, or a recorded negative.
- [ ] **A/B the first-party 397B DFlash head against the checkpoint's own MTP head (flagship 4-node arm — queued 2026-10-13).** The shipped arm specs with the grafted MTP head (`method: mtp`, 3 tokens) and carries only a **card figure** (41.86 t/s, tied to the floating `:latest` tag — the lane has no house measurement; §3.8 wants a digest pin anyway). The third collection head is `ornith-ai/Ornith-1.5-397B-DFlash` (`db9c35a0…`, 2.58 GB, `DFlashDraftModel`, taps 1/9/…/57 of a 60-layer target, MIT, ungated, no published numbers). Keep the target constant — the shipped graft tree (`littlecedar/…-MTP-Graft` = the NVFP4 quant + bf16 MTP MoE) carries both methods; reach for the upstream plain quant `ornith-ai/Ornith-1.5-397B-NVFP4` (`fcefb8b2…`, 241.8 GB, 25 shards) only if the graft's packaging fights `method: dflash`. Swap one knob: `--speculative-config '{"method":"dflash","model":"…","revision":"db9c35a0…","num_speculative_tokens":8}'` (card shape; the MTP config's `max_model_len`/`attention_backend`/`moe_backend` keys are MTP-specific — start minimal) — sparkrun reads draft + revision out of that JSON to distribute the draft to all 4 nodes (`runtimes/_vllm_common.py:357-372`, `vllm_ray.py:61-63`), and the revision must be pinned **there**, never via `model_revision:` (that SHA does not exist in the draft repo → `Revision Not Found`, per the docstring). Traps: (1) `--load-format instanttensor` + `@eugr/mods/instanttensor-hybrid-draft-loader` were built for the MTP head — read that external mod and check the plain-safetensors draft loads (the draft may need the standard loader); (2) first confirm the floating nightly's vLLM exposes `method: dflash` (card: ≥0.20.2, tested 0.28.0) and record the resolved digest for both arms; (3) this is the registry's most expensive arm (235 GB/node, TP=4): one boot per arm, C1 `decode-triage` d0/d8192 + serve-log acceptance, and **re-measure the MTP baseline in the same window** rather than comparing to the 41.86 card figure; the draft adds +2.6 GB/node — watch the util-0.80 budget. Done when both arms have same-window receipts, the winner is recorded (with the loser's rationale) in the lane docs, and §3.8's digest pin lands with the numbers.

## qwen3
Qwen 3.x
- [ ] Build a recipe from this and try it out, if it hasn't already been done, in our registry: https://github.com/MiaAI-Lab/Qwen3.8-27B-DGX-Spark-TensorFold

## qwen4
Qwen 4.x (and 3.8 Flash Next)
- [ ] **Re-pin (and re-verify the mods for) the labquant checkpoint.** `local-inference-lab/Qwen3.8-Flash-Next-NVFP4` `main` is `6c01ac378d22…` (2026-10-06 — the `step-5500 QAD` candidate the W14 plan already named) and the `.30` cache holds it, while the three `…labquant…` recipes pin `7c4f1bc1a2d6…`. Run the W14 per-mod re-verification plan against the new revision (one mod breaks, one is obsolete, five survive), then re-pin and re-bench the labquant arms (W3 battery + `decode-triage`).
- [ ] There are at least six Qwen3.8-Flash-Next-NVFP4 recipes in the registry at the time I'm writing this. This is too many. Select the fastest single node recipe and two-node recipe and then sweep the rest to the @attic. 1M context length is optional for this lane.   

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
- [ ] **Humanizer-12B arm (queued 2026-10-13 — text-rewriting helper, outside the lane brief).** `jialinyyzz/humanizer` (12B `google/gemma-4-12B` finetune, Apache-2.0, ungated, 1 node: 23.9 GB bf16 / 12.7 GB Q8_0 / 3.9–10 GB QAT quants) rewrites one AI-written draft so it reads human (en+zh); card: 95% judged human by Originality.ai strictest (11/210 bf16) and 376/420 English rewrites with no factual problem — still read numbers/dates/names. vLLM-servable via the vendor's own path (`--dtype bfloat16 --max-model-len 8192 --generation-config vllm`), but the contract is **`/v1/completions` with the byte-exact `instr + draft + sep` prompt from `prompt_format.json`, never a chat template**, top_k off. Checklist + acceptance proposal: `recipes/explore/EXPLORE-MODELS-RESEARCH.md` §7.

## cybersec
Cybersecurity-research (red-team) abliterated / uncensored models
*(queued 2026-10-14 — owner directive; sources scanned `hf.co/drowzeys` and `hf.co/orcarouter/collections`.)*

Five arms, all **abliterated/uncensored** and all **gated** (`gated: auto` — a responsible-use agreement
plus a per-node `HF_TOKEN`, the same third-party-distribution problem as `LTX-2.5`; owner call in `# DECISIONS` #19).
Sizes below are **measured on-disk weight bytes** (Hub `files_metadata`, 2026-10-14), not the Hub
`Parameters` field (explore research doc §3); 1 node = ≤ ~108 GB at 0.85 util.

- [ ] **Solo (TP=1): `orcarouter/Qwen3.8-27B-Uncensored-NVFP4`.** 21.2B params, NVFP4, arch `qwen3_5`,
  Apache-2.0, gated; 186.8K dl / 308 likes; tags `ai-red-team`, `red-teaming`, `function-calling`,
  `reasoning`, `mtp`. 1 node / **24.7 GB** measured. Base `Qwen/Qwen3.8-27B`; its clean sibling ships in
  `recipes/qwen3/`, so reuse that lane's SGLang scaffold. FP8 / INT8 / GGUF siblings exist. Done when
  booted (`GET /v1/models` = repo id) with C1 (`decode-triage` d0/d8192) + the house battery.
- [ ] **Solo (TP=1): `drowzeys/keys-Qwen3.8-27B-NVFP4-DFlash2-Ablit-Cybersecurity-Unlock-1M-Context-YARN-Single-DGXSpark`.**
  **Overlay / community compile — ships no weights** (0 GB safetensors; Apache-2.0, gated): a DFlash2
  YaRN-1M config + an uncensored chat template (`chat_template_b5_uncensored.jinja`) + a `one-shot.sh`
  over AEON-7's `aeon-vllm-ultimate` image and a stock `Qwen/Qwen3.8-27B` NVFP4 + DFlash2 pack; **1 node**;
  tags `cybersecurity`, `abliterated`, `uncensored`, `dflash2`. `raw/` holds the receipts
  (`cyber-refusal32.json`, YaRN probes to 1M). Structurally copies the shipped
  `qwen3.8-27b-nvfp4-dflash2-sglang` arm (add the YaRN long-ctx route + the `served_model_name` key) over
  the overlay's chat template. Done when a boot receipt + C1 + battery, or a recorded negative.
- [ ] **Solo (TP=1): `orcarouter/Nex-N2.5-mini-Uncensored-NVFP4`.** 35.1B params, NVFP4, arch
  `qwen3_5_moe` (hybrid GDN + MoE), Apache-2.0, gated; collection note "Abliterated … BF16 66 GB, 122 /
  1026 tensors edited. **Research use only**"; tags `ai-red-team`, `agentic`, `computer-use`.
  24.0 GB measured. New family (no Nex arm in the registry) — read the arch + parser needs off the base
  card first.
- [ ] **Dual (TP=2): `orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4`.** 180B, NVFP4, arch `qwen4_exp`,
  183.5 GB measured. The abliterated twin of the `recipes/qwen4/` checkpoint — reuse that lane's TP=2 recipe (the
  7-mod chain minus the labquant-specific mods). Done when boot + C1 + battery, plus a refusal probe
  (report the bypass rate; keep the source card's format so it is comparable).
- [ ] **Dual (TP=2): `drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed`.** **Overlay, not
  a checkpoint:** two `attn.wo_b` L10–35 sidecars (FP8 `wo_b_l10_35.safetensors` ~1.1 GB; EXL3-mul1-K=5
  `mia_exl3_wo_b_l10_35.safetensors` ~682 MB) grafted onto a stock pack via `apply_wo_b_graft.py`; MIT,
  **`gated: auto`**; card claims Refusal32 **32/32** + Cyber **22/22** bypass. Dual path = the **Mia 2×
  Spark EXL3 2.9 bpw** base (`Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw` + its 2× kit); the native base is
  the ds4 lane's TP4 production checkpoint. Needs a mod to fetch + graft (never write the stock pack in
  place), GPU util **≤ 0.85**. **Never disturb the live ds4 TP4 serve.** Done when the graft is
  boot-verified on 2 nodes with C1 + a cyber-refusal probe, or a recorded negative.

**Other surfaced arms (not queued):** `orcarouter/GLM-5.3-Flash-Uncensored-NVFP4` (321B, **205.1 GB** —
2-node-heavy/3-node; inherits the archived glm5 Flash serve blocker),
`orcarouter/DeepSeek-V4-Flash-Vision-Uncensored` (304B, `deepseek_v4`),
`drowzeys/keys-Qwen3.8-Flash-Next-NVFP4-dual-ablit-house-qsa-L3-47` (dual 180B ablit, **132.7 GB**; base
`nvidia/…` → licence `other`), `drowzeys/keys-GLM-5.3-Flash-NVFP4-ablit-l15-43-mtp-l45` (169B, MIT),
`drowzeys/MiMo-V2.6-Flash-RL-Abliterated` (310B, FP8/MXFP4). **Over the 1–2-node bar, so recorded but NOT
queued:** `drowzeys/keys-MiMo-V2.6-Pro-RL-Jarrelscy-ARVQ-Abliterated` (`nvfp4_arvq_hybrid`, MIT, gated —
**315.7 GB** on-disk ⇒ ≥3 nodes; owner asked to add it only if it fit 1–2).
