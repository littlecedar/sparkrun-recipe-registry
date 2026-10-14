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

# DECISIONS — nothing open (2026-10-14)

New owner questions land here, each with a `→ Answer:` line. Numbered decisions cited elsewhere —
#6 in `recipes/qwen4/SELECTION-RANKING.md`, #11 in `recipes/decision/DECISION-MODELS-RESEARCH.md`,
#10/#11/#14 in `recipes/explore/EXPLORE-MODELS-RESEARCH.md` — live in git history: the 2026-10-11
register is `git show 8a98379:mad-science/TODO.md`; the 2026-10-14 registers (#16–#23, #24–#27) are
the pre-fold states, `git show baecfa8:mad-science/TODO.md` and `git show c7c7a81:mad-science/TODO.md`.

# TODO list

Session end: 10:00 US/Eastern (2026-10-14)
*(Owner decision 2026-10-14: all six nodes — `.30–.35` — are ours this session; the 4-node/TP=4 items
(ornith 397B A/B, ds4 TP=4, glm5) are runnable.)*
*(Owner decision 2026-10-14: must-do by the 10:00 ET end — the qwen4 re-pin + cut, the five cybersec
arms, and the ifm/decision/explore re-pin sweep; the ornith 397B A/B and everything else spill.)*

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
- [x] **Build additional quality testing and benchmarking suites using established industry standard benchmarking tools where feasible — DONE 2026-10-14.** Shipped `tools/bfcl-eval.py`, a BFCL (Berkeley Function-Calling Leaderboard) **v3** scorer for a live OpenAI-compatible endpoint: it ports the official AST checker so the accuracy number is the leaderboard's rule rather than a lookalike, plus the relevance call/no-call categories. Guarded by `tests/test_bfcl_eval.py` (46 tests); offline against the real BFCL v3 AST split the ported checker scores **1000/1000** on a correct model's output. This is the standard the explore lane needed — three of its shortlist models publish BFCL.
  *(Owner decision 2026-10-14: decision #15 ("no new battery tool") was REOPENED; this is the suite built in response. Done as called.)*
- [x] **Serve every sglang arm under the upstream repo id, not the snapshot path (owner report 2026-10-13).** `ornith-1.5-35b-a3b-nvfp4-dflash2-sglang` currently advertises `/cache/huggingface/hub/models--ornith-ai--Ornith-1.5-35B-A3B-NVFP4/snapshots/94e431d9…` as its `model` id — wrong for clients, the proxy and any benchmark that sends the model id. Audit (13 shipped sglang recipes): **11 write `--served-model-name {model}`** (clef, Ling, ornith, qwen3.8-27B DFlash2, all five qwen3.8-flash-next arms, both ds4 shim arms) and **2 write no flag at all** (both IFM K2 arms — SGLang then defaults the id to the model path anyway) — nine of the eleven picked the spelling up in `0f41394` ("Add `--served-model-name` argument to all relevant recipes"): right intent, wrong operand, because `{model}` is the placeholder that gets rebound, so those nine lines must be *deleted* (not kept "for safety") when the declarative key goes in. Mechanism, already recorded in-repo: on a real launch sparkrun rewrites `{model}` *and a `--served-model-name {model}` rendered from the same placeholder* to the prepared on-disk path (`models/runtime.py::bind_runtime_models`, quoted at `mods/tensorfold-dsv41-launcher/launcher.py:176-182` and `tests/test_ds4_recipes.py:1290`), so the flag faithfully advertises the path. **`-n` does not show this** — it still prints the repo id; only a real launch rewrites the flag. **Fix pattern:** drop the hardcoded flag and declare `served_model_name: <upstream repo id>` in `defaults:` — the sglang runtime maps that key to `--served-model-name` and appends it when *absent* (`runtimes/sglang.py:47,372-376`; fill policy `runtimes/base.py:952-981` leaves an existing value intact, which is why the `{model}` spelling wins today). The vLLM lanes already use the declarative key (`explore/kolibri-1-78b-fp8-vllm.yaml`) and the root README documents the repo-id convention; the command-less path in `runtimes/sglang.py:533-535` already serves under `recipe.model`. **Per recipe:** drop/declare, then verify on a real launch — `GET /v1/models` (or `sparkrun cluster check --check-http-models`) must return the repo id; the CLI `--served-model-name` override can probe it live, but override *files* cannot set that key (`core/recipe_overrides.py:90`). Leave the two ds4 shim arms alone if their launcher path→repo-id normalization stays green (guarded today). Also correct the decision lane's "Served-id wart" note (`recipes/decision/README.md:45`) — it blames a missing flag, but the arm boots *with* the flag, so the value is the rebinding; and re-check any lane doc that quotes a path id. Done when every shipped sglang arm reports its repo id in `/v1/models` and no recipe carries the `{model}` spelling of the flag. **2026-10-13 progress (ornith):** `ornith-1.5-35b-a3b-nvfp4-dflash2-sglang` fixed + live-verified (boot `dadfb04b5145d956_8ed3ce77d78f` on `.34`: `/v1/models` → `ornith-ai/Ornith-1.5-35B-A3B-NVFP4`, chat addressed to that id 200; warm TTR port-open 94.7 s). It uses the declarative key **plus** `--served-model-name {served_model_name}` — sparkrun's prescribed spelling (`core/validation.py`'s hardcoded-flag suggestion: "Move the value to defaults.%s and reference it as {%s}") rather than delete-and-let-append: identical final argv (the append no-ops when the flag is present, `runtimes/base.py:931-933`), and it keeps the repo's `InertDefaults` guard green with no exemption. Recipe comment + lane `README.md`/`AGENTS.md` + a lane guard (`tests/test_ornith_honed_chat_template.py`) carry the fix. Remaining: ten `{model}`-spelling arms + the two no-flag IFM K2 arms (SGLang defaults those to the model path; `runtimes/base.py:979-980` makes the append conditional on the key existing). **2026-10-13 sweep complete (all ten + both IFM arms):** every shipped sglang arm now has live `GET /v1/models` evidence of its repo id — clef (`625b43fd997e4d5b_8ed3ce77d78f`, `.34`), Ling (`3effce2e30113dd9_64af2f7668b6`, `.35`), K2 0.9B (`e2b91b75cf01d3ab_8ed3ce77d78f`, `.34`), K2 7B-Uno (`ff7c9715c406eee7_64af2f7668b6`, `.35`), qwen3.8-27B (`3b78f3ef7df2980b_64af2f7668b6`, `.35`), flash-next ×2 (`1753bbfdf3f0a50e_3510a5e0d37d` TP2, `15adecfd945cac5c_8ed3ce77d78f` solo), labquant ×3 (`1895030211ea0500_3510a5e0d37d` TP2), tensorfold (`8ef9b6c9a550c389_3510a5e0d37d`; recipe unchanged — its launcher normalizes the path), knapcio (production serve `a4c699c1299bbbdf_8296561cc1cb` on `.30` answers the repo id; recipe unchanged). The three labquant arms also gained `--revision {model_revision}`: after the fix their only identity tokens are the declared literal and that revision flag — `validate_runtime_command` (branch 1 no longer fires: `--model-path` is the mod-built tree) needs both, boot-proven on `.34+.35`. Observed consequence: the three labquant arms share one cluster id (`name=<served>` folds into the intent hash), so `stop <id>` addresses whichever is current. Class guard `tests/test_recipe_placeholder_resolution.py::ServedModelNameNotRebound` (ds4 arms allowed by name, with the launcher reason); shape documented in `recipes/README.md` §Notes; lane receipts in each lane's docs.

## ds4
DeepSeek V4.1
- [x] **Check the DSV4.1 checkpoint revision — DONE 2026-10-14.** The recipe now pins
  `model_revision: 5254448103b6254fc646dacbca1cbbf20e9216c1` (`main`, 2026-10-12), **not** the
  image's baked `fb2764a5…`. Both are Hub-resolvable; the A→B delta touches no weights (all 48
  shards byte-identical) — only docs, the reference `inference/`/`encoding/` trees, and the added
  `chat_template.jinja` — so it cannot move a served number. `main` is what every node cache holds
  and what the dated receipts were served from (`2cba9e42…`, its template-carrying ancestor);
  `fb2764a5…` is in no cache, so keeping it would re-distribute and serve a snapshot lacking the
  template the receipts ran with. Re-ran the lane suite on 4 nodes: boot receipt (`GET /v1/models`
  = `deepseek-ai/DeepSeek-V4.1-Flash`; launcher serving `snapshots/5254448103b6…`), C1
  `decode-triage` 38.3 (d0) / 42.5 (d8192) t/s, house battery 19/19 easy + 17/18 hard (same
  `hard-rev`). Decision + receipts: `recipes/ds4/AGENTS.md` §5/§5.1; artifacts
  `.scratch/ds4/knapcio-tp4-boot-20261014/`. All four nodes left clear.
- [x] Move the DSV4.1 checkpoint revision into the recipe yaml instead of the TP4 image. Build and push the image.
  *(Owner decision 2026-10-14: build + push + boot-verify this session. Image built+pushed by the
  owner; boot-verified 2026-10-14. The pin landed on the cached `main`, not the baked `fb2764a5…`:
  see the item above and `recipes/ds4/AGENTS.md` §5.)*

## glm5
GLM 5.3
- [x] **Runbook revision refresh (no recipes to pin) — DONE 2026-10-14.** Verified against the HF API and every node's live cache, recorded in `recipes/glm/README.md` §"Revision pins": `Mia-AiLab/GLM-5.3-Flash-EXL3-4bpw-TensorFold` `main` `76c0b517…` (2026-10-03; the TP=2/TP=4 trials' launcher pins `078455ff…`, still resolvable), `bertholomus/GLM-5.3-EXL3-3.0bpw` = `7f057383…` (cached on `.30` until the 2026-10-14 cache reclamation; a revive re-fetches ~273 GB/node), `RedHatAI/GLM-5.3-Flash-NVFP4` `main` `18d55bfd…` (2026-09-18) past the archived `36c184c6…` pin (still resolvable; snapshot absent from every node → a revive re-fetches ~198 GB), engine `bertholomus/TensorFold@glm-dsa-tp4` = `ddfad35…` (matches the head checkout + GitHub branch tip).

## ornith
Ornith 1.5
- [x] **Run additional experiments to confirm this model's quality (owner report 2026-10-13) — DONE 2026-10-14 (bounded null).** A long-horizon agentic re-investigation (`.31`, one boot, the shipped 35B recipe) drove the workload the report is about — a multi-turn tool-calling scheduling session with a growing transcript over near-duplicate work items (`agentic_horizon_probe.py`, scoreable `submit_plan` validation). Detector: per-message and whole-session 25-word-window repeats, session repeats *excluding* quoted input, cross-turn 8-word shingle overlap, and `finish_reason`. Result: **no decode loop** (per-message repeat ≤2, never ≥3; session repeats only from input echoed back; clean terminations) — **not reproduced** on the long-horizon workload either. The 2026-10-13 single-turn null is recorded as such. The owner ratifies the bar. Details: `recipes/ornith/README.md` §"Reasoning-loop investigation"; `recipes/ornith/NOTES.md` §5; receipts `.scratch/ornith-horizon-20261014/`.
  *(Owner decision 2026-10-14: the agent proposed the experiment set and the bar; the owner ratifies the result.)*
- [x] **A/B the first-party DFlash draft against the shipped jzinno DFlash2 draft — DONE 2026-10-14 (null; shipped draft now pinned).** Same-node A/B on the shipped 35B arm (`.31`, one boot per arm, decode-phase rows only, n ∈ {4, 8}, `benchmarking/decode-triage.yaml`): the vendor head ([`ornith-ai/Ornith-1.5-35B-A3B-DFlash`](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B-DFlash), `942d20fe…`, plain `DFlashDraftModel`, 0.77 GB) is **indistinguishable from the shipped third-party `jzinno/…-DFlash2`** at n=4 and no better at n=8, so the jzinno draft stands — the null is the result, not a tie-break. The shipped draft is now **pinned** (`speculative_draft_model_revision: 9b4852c0…`, distribution-only) with the `pre_exec` **`refs/main` seed** the pin requires (a SHA-keyed fetch writes no `refs/`, and the container's offline draft-config lookup resolves only `refs/main`) — see `recipes/ornith/AGENTS.md` §3.12. The pinned winner's boot scored the house battery **37/37**. Receipts: `~/benchmarks/ornith-dflash-ab-20261014/`.
- [x] **Scope and measure a `9B-NVFP4 + DFlash` arm — DONE 2026-10-14 (shipped + measured).** New recipe `recipes/ornith/ornith-1.5-9b-nvfp4-dflash-sglang.yaml`: target `ornith-ai/Ornith-1.5-9B-NVFP4` (`155f200d…`, dense ~9B, multimodal) + first-party head `ornith-ai/Ornith-1.5-9B-DFlash` (`21be3446…`), 1 node / TP=1 / SGLang DFLASH, no `mamba_*`/`moe_runner_backend`, serving the checkpoint's own multimodal template rather than the 35B's honed one. **Booted + measured 2026-10-14** (`.30`): C1 ≈55 t/s (registry row), `GET /v1/models` = repo id, serve-log `Mean acceptance length > 1`. The first-party draft stays **deliberately unpinned** — an unpinned fetch resolves `refs/main` itself, which a SHA pin would not (an authoring question the boot answered: the pinned SGLang image *does* load a plain `DFlashDraftModel`). Lane guards added (`tests/test_ornith_recipes.py`). Receipts: `~/benchmarks/ornith-9b-20261014/`.
- [x] **A/B the first-party 397B DFlash head against the checkpoint's own MTP head (flagship 4-node arm — queued 2026-10-13) — DONE 2026-10-14 (MTP ships).** The shipped arm specs with the grafted MTP head (`method: mtp`, 3 tokens) and carries only a **card figure** (41.86 t/s, tied to the floating `:latest` tag — the lane has no house measurement; §3.8 wants a digest pin anyway). The third collection head is `ornith-ai/Ornith-1.5-397B-DFlash` (`db9c35a0…`, 2.58 GB, `DFlashDraftModel`, taps 1/9/…/57 of a 60-layer target, MIT, ungated, no published numbers). Keep the target constant — the shipped graft tree (`littlecedar/…-MTP-Graft` = the NVFP4 quant + bf16 MTP MoE) carries both methods; reach for the upstream plain quant `ornith-ai/Ornith-1.5-397B-NVFP4` (`fcefb8b2…`, 241.8 GB, 25 shards) only if the graft's packaging fights `method: dflash`. Swap one knob: `--speculative-config '{"method":"dflash","model":"…","revision":"db9c35a0…","num_speculative_tokens":8}'` (card shape; the MTP config's `max_model_len`/`attention_backend`/`moe_backend` keys are MTP-specific — start minimal) — sparkrun reads draft + revision out of that JSON to distribute the draft to all 4 nodes (`runtimes/_vllm_common.py:357-372`, `vllm_ray.py:61-63`), and the revision must be pinned **there**, never via `model_revision:` (that SHA does not exist in the draft repo → `Revision Not Found`, per the docstring). Traps: (1) `--load-format instanttensor` + `@eugr/mods/instanttensor-hybrid-draft-loader` were built for the MTP head — read that external mod and check the plain-safetensors draft loads (the draft may need the standard loader); (2) first confirm the floating nightly's vLLM exposes `method: dflash` (card: ≥0.20.2, tested 0.28.0) and record the resolved digest for both arms; (3) this is the registry's most expensive arm (235 GB/node, TP=4): one boot per arm, C1 `decode-triage` d0/d8192 + serve-log acceptance, and **re-measure the MTP baseline in the same window** rather than comparing to the 41.86 card figure; the draft adds +2.6 GB/node — watch the util-0.80 budget. **Done 2026-10-14 (extension session, owner-approved spend):** same-window A/B on `.30`–`.33` (one boot per arm, TP=4, decode-phase rows, n ∈ {4, 8}, `decode-triage`) — **MTP ships**: 42.55 ± 2.78 / 38.48 ± 1.91 t/s vs the DFlash head's 37.58 ± 4.45 / 33.64 ± 1.13 (−11.7/−12.6%). The loser's rationale is recorded: no measurable win at the added complexity for this engine, so it stays a one-knob `-o` alternative, not a shipped arm (its higher draft acceptance is a speculator-overhead confound, not a throughput win). §3.8's digest pin landed — the floating `:latest` was **three different builds across the four nodes**; now pinned (`b94ac8ac…`), and the recipe declares + renders the speculative config (the prior `-o`-only knobs never reached the engine). First house numbers beside the card's 41.86. Details: `recipes/ornith/AGENTS.md` §3.8, `README.md` §"A/B results"; receipts `~/benchmarks/ornith-397b-ab-20261014/` (commit `3524dca`).

**Session result 2026-10-14:** all four staged plans in `recipes/ornith/NOTES.md` §2–§5 ran and closed this session (the 397B A/B in the owner-approved extension pass) — the 9B arm (§2), the 35B first-party-DFlash A/B (§3, null), the 397B DFlash-vs-MTP A/B (§4, **MTP ships**), and the long-horizon quality re-investigation (§5, bounded null); each plan's result moved into `README.md`/`AGENTS.md`. The lane had no recipe guard before this session; `tests/test_ornith_recipes.py` covers all three arms now.

## qwen3
Qwen 3.x
- [x] **Build a recipe from [`MiaAI-Lab/Qwen3.8-27B-DGX-Spark-TensorFold`](https://github.com/MiaAI-Lab/Qwen3.8-27B-DGX-Spark-TensorFold) — DONE 2026-10-14 (shipped + measured).** New recipe `recipes/qwen3/qwen3.8-27b-mlx4bit-tensorfold-sglang.yaml`: TensorFold v0.6.0 (its own engine behind the `runtime: sglang` shim — the ds4 lane's pattern) over `TensorFold/Qwen3.8-27B-MLX-4bit` (MLX affine-4-bit, ~15 GB) + `z-lab/Qwen3.8-27B-DFlash2` drafter, one node / TP=1 / 262k / FP8 KV / image+video input. **Booted + measured** on `.30` (boot `fe3054ad67464c54_2d38dfc4605e`): decode-triage d0 **41.3 ± 4.0** / d8192 **41.7 ± 2.4** t/s, `GET /v1/models` → `Qwen3.8-27B`, house battery **37/37**. Guarded by `tests/test_qwen3_recipes.py`. Details: `recipes/qwen3/README.md`.

## qwen4
Qwen 4.x (and 3.8 Flash Next)
- [x] **Re-pin (and re-verify the mods for) the labquant checkpoint — DONE 2026-10-14.** Cut first (owner call): of the six arms measured in one 2026-10-14 window, the two survivors were re-verified/re-pinned against `local-inference-lab/Qwen3.8-Flash-Next-NVFP4` `main` `6c01ac378d22…` (the `step-5500 QAD` candidate the W14 plan named). The mod chain is now **6 mods** (one dropped as obsolete, one fixed) and **vision is restored**; the TP=2 survivor (the labquant balanced base) re-pinned to `6c01ac37` and re-benched: **40.32 ± 1.94 @ d0 / 43.29 ± 2.68 @ d8192** t/s. Details: `recipes/qwen4/AGENTS.md`, `recipes/qwen4/SELECTION-RANKING.md`; receipts `~/benchmarks/q4-*-triage_1014_*`.
  *(Owner decision 2026-10-14: cut first — measure the six arms, pick the two, then re-verify/re-pin only the survivors against `6c01ac37`. Done as called.)*
- [x] **Cut the lane to two arms — DONE 2026-10-14.** `recipes/qwen4/` now ships **exactly two** production recipes: the fastest **TP=1** (`qwen3.8-flash-next-nvfp4-solo-vllm-b12x`) and the fastest **TP=2** (`qwen3.8-flash-next-nvfp4-labquant-sglang`, the balanced base). The other four (`…-labquant-longctx-sglang`, `…-labquant-highcon-sglang`, the RadixArk `…-nvfp4-sglang`, and the sixth arm `…-solo-sglang`, re-measured after a readiness failure) were `git mv`'d to `attic/qwen4/arms/` with a provenance row in `attic/qwen4/ARMS-MANIFEST.md`; 1M context dropped. Details: `recipes/qwen4/README.md` §"What was measured, and the cut".
  *(Owner decision 2026-10-14: confirmed — exactly two shipped arms (fastest TP=1 + fastest TP=2), the rest swept to `attic/`; 1M context droppable. Done as called.)*

## ifm
IFM K2-Horizon
- [x] **Re-pin the K2-Horizon checkpoints.** Both reps have moved past the recipe pins and the `.30` cache holds the new revisions: `IFM/K2-Horizon-0.9B` `main` `383cb66347be…` (2026-10-06) vs pin `9fa6faa55fe1…`; `IFM/K2-Horizon-7B-FP8` `main` `ea739ec816e0…` (2026-10-03) vs pin `59d473210f0b…`. Diff the deltas, re-pin `model_revision:`, re-run the lane's benches + the dense accuracy set (`gsm8k`/arc/house), and re-confirm UNO spec-decode engagement on the 7B. — **DONE 2026-10-14**: both re-pinned + guards updated; deltas = card-only (7B) and card+templates (0.9B); re-bench + accuracy on `.31` reproduce every cell inside the lane noise floor; UNO accept len mean 4.15 over 838 samples. Details: `recipes/ifm/NOTES.md` 2026-10-14 session.

## embed
Any embed model
*(all items completed — archived in `../attic/DONE.md`)*

## rerank
Any rerank model
*(all items completed — archived in `../attic/DONE.md`)*

## decision
Any decision model
- *(Resolved 2026-10-14: the `vllm-srun` runtime pins its own validation revisions — its golden
  reference answers attach to, and are looked up by, content identity for the image's pinned
  revision, so a newer revision is served but golden-`unverified`, never `matched`; both recipes
  left as-is. The Hub drift is cosmetic anyway — pin vs `main` differs by `assets/banner.png`
  alone. Determination + inspecting-command evidence: `recipes/decision/README.md` § "Revision-drift
  determination"; receipts `~/benchmarks/decision-revision-20261014/`.)*

## explore
Any model with reasoning and tool-calling capabilities
- [x] **Re-pin Kolibri-1 (main moved past the pin) — DONE 2026-10-14.** Diffed the deltas (weights / tokenizer / chat template), moved the pin to `258cae8ffffc…`, re-ran the house battery + `decode-triage` (re-verified **47.4 t/s, 37/37 @4096**) and re-confirmed the plugin / `kolibri1` parser contract. Details: `recipes/explore/README.md`.
- *(Owner decision 2026-10-13: the deciding factor for explore models is **accuracy**, with preference for smaller and faster models — supersedes the node-count→speed default. Re-ranked: **Ling-3.0-flash** (rank 1, 37/37) and **Kolibri-1** (rank 2, 36/37 = 37/37 union, smaller + faster) are kept; Nemotron-262k and its 1M variant moved to `attic/explore/`.)*
- [x] **Pin the DSPARK draft (Ling, rank 1) — DONE 2026-10-14.** The draft moved to `d60b0e12…`; DSPARK acceptance was re-checked on the moved draft, the draft revision **pinned**, and `decode-triage` + the house battery re-run — re-verified **54.7 t/s, 37/37** (the shipped 45.5 was measured on the 2026-10-11 draft). Details: `recipes/explore/README.md`.
- *(The archived Nemotron arms' `nvidia/…NVFP4-DSpark` draft also moved to `6d127b50…` on 2026-10-12 and was never pinned, so the 2026-10-13 acceptance-length non-reproduction (3.67 → 1.66) may be a draft change and not only the suspected metric-window artifact — re-check if those arms are revived.)*
- [x] **Poolside Laguna XS-2.1 arm (queued 2026-10-13 — queue rank 1) — DONE 2026-10-14 (shipped + measured).** New recipe `recipes/explore/poolside-laguna-xs-2.1-nvfp4-dflash-vllm.yaml`: `poolside/Laguna-XS-2.1-NVFP4` (33B-A3B, 262k, OpenMDW-1.1, 21.6 GB) + the first-party `Laguna-XS-2.1-DFlash` draft, 1 node / TP=1; both repos pinned (`d32afde8…` / `5c36361a…`). Checklist (a)–(f) all PASS — import check (`LagunaForCausalLM` + `laguna_dflash` + both `poolside_v1` parsers), **NVFP4 engages on SM121** (the INT4 23.9 GB fallback was not needed), draft distributes, depth sweep n=3, battery **36/37 @4096 @ 57.4** t/s. Details: `recipes/explore/README.md`; receipts `~/benchmarks/explore-laguna-20261014/`.
- [x] **Poolside Laguna S-2.1 arm (queued 2026-10-13 — queue rank 2, also 1 node) — DONE 2026-10-14 (shipped + measured).** New recipe `recipes/explore/poolside-laguna-s-2.1-nvfp4-dflash-vllm.yaml`: `poolside/Laguna-S-2.1-NVFP4` (118B-A8B, 1M ctx, OpenMDW-1.1) + the quant-matched `Laguna-S-2.1-DFlash-NVFP4` draft, 1 node / TP=1. **Boot-verified on `.35`** (task `e57eaed458e6b584_64af2f7668b6`): `GET /v1/models` → repo id, **FP4 path native on `sm121`**, KV pool 125,796 tokens, battery **32/37** @ ~20.5 t/s C1. The research template's 262k window does **not** fit one Spark — the pinned August-2026 checkpoint loads **95.61 GiB**, not the ~67 GiB the older pre-August sweep carried. Draft-licence gap recorded in the recipe (the shipped draft declares no licence). Details: `recipes/explore/README.md`.
  *(Owner decision 2026-10-14: ship the recipe — a recipe ships a repo id, not weights; the downloader accepts the licence. Done as called.)*
- [x] **Qwen-Image-2.1-Turbo arm — DONE 2026-10-14 (shipped + measured; owner un-deferred).** New recipe `recipes/explore/qwen-image-2.1-turbo-7b-bf16-diffusers-script.yaml` + `mods/qwen-image-2.1-turbo-launcher` — the lane's first non-`sglang`/vLLM engine: `Qwen/Qwen-Image-2.1-Turbo` (pinned `fc13ba1986`) served by diffusers' `QwenImage21Pipeline` out of a venv the mod stages on the image's own torch, one node. **Boot-verified on `.34`** (TTR 206.1 s, pipeline load 188.0 s; `GET /v1/models` → repo id): 1024² at the checkpoint's shipped 8-step schedule, CFG=1 → **11.33 / 11.41 s** steady (first request 12.30 s; the derived `54.1 × 8/40 ≈ 10.8 s` holds, +5%); peak 36.85 GiB alloc / 37.68 GiB reserved; reference-image edit +3.5 s; same prompt+seed repeat wrote a **byte-identical PNG**. Two bring-up defects found and fixed in the mod (the container's non-root user breaking `reown()`, and a heredoc piped into `log()` killing the hook with `rc=120`). **Licence: `qwen-research` — NON-COMMERCIAL ONLY**; ships as a banner-marked **eval-only** entry. Details: `recipes/explore/QWEN-IMAGE.md`; receipts `~/benchmarks/qwen-image-20261014/`.
  *(Owner decision 2026-10-14: media-gen arms deferred to a separate pass; when built, ship the recipe (licence policy) and use the confirmed §6 acceptance criterion. Owner un-deferred 2026-10-14; done as called.)*
- [x] **LTX-2.5 arm — DONE 2026-10-14 (shipped as a runbook, not a recipe).** Access: repo is `gated: auto`; the cluster token (`twichert`) **has acceptance** (README resolve → HTTP 200), so the arm was measured rather than blocked — a fresh node still needs the per-repo accept + `hf auth login` (documented prerequisite, cybersec precedent). ComfyUI **v0.34.0** pinned as a unit, torch 2.14.1+cu130, clock capped at 2200 MHz (§6(e) sustained-load fix). Two-stage nvfp4 run on `.35`: stage 1 distilled 8-step @ 672×384 → `LTXVLatentUpsampler` ×2 → 3-step refine @ **1344×768, 121 frames @ 24 fps with audio**; **cold 100.3 / 90.1 s** (two reps), **warm 80.1 s**; stage split 14.0 load / 16.7 stage 1 / 2.5 upscale / 20.8 refine / 46.2 decode+mux; **peak 83.6 GiB**; output verified by `ffprobe` (h264 1344×768 24 fps 121 frames + AAC) and a decoded frame (not garbage). NVFP4 native on `sm121` via comfy-kitchen. Runbook `recipes/explore/ltx-2.5-runbook/` + lane notes `recipes/explore/LTX-25.md`; receipts `~/benchmarks/ltx25-20261014/`.
  *(Owner decision 2026-10-14: deferred to a separate pass; ship gated arms with a documented per-node `HF_TOKEN` + acceptance prerequisite; the §6 acceptance criterion is confirmed. Owner un-deferred 2026-10-14; done as called.)*
- [x] **Humanizer-12B arm (queued 2026-10-13 — text-rewriting helper, outside the lane brief) — DONE 2026-10-14 (shipped + measured).** New recipe `recipes/explore/humanizer-12b-vllm.yaml`: `jialinyyzz/humanizer` (12B `google/gemma-4-12B` finetune, Apache-2.0, 1 node) served as the lane's first **`/v1/completions`** arm with the byte-exact `instr + draft + sep` prompt from `prompt_format.json`. Boot-verified (`GET /v1/models` → `jialinyyzz/humanizer`, 8192 ctx); §7(c) measurement: 131.7 s per 1k output tokens, 20 number/date/name flags all reviewed as the same value. Details: `recipes/explore/README.md`; receipts `~/benchmarks/humanizer-20261014/`.
  *(Owner decision 2026-10-14: in scope this session; the §7 acceptance criterion is confirmed. Done as called.)*

## cybersec
Cybersecurity-research (red-team) abliterated / uncensored models
*(queued 2026-10-14 — owner directive; sources scanned `hf.co/drowzeys` and `hf.co/orcarouter/collections`.)*

Five arms, all **abliterated/uncensored** and all **gated** (`gated: auto` — a responsible-use agreement
plus a per-node `HF_TOKEN`; releases accepted 2026-10-14). **Owner decision 2026-10-14: ship gated arms
with a documented per-node token + acceptance prerequisite.**
Sizes below are **measured on-disk weight bytes** (Hub `files_metadata`, 2026-10-14), not the Hub
`Parameters` field (explore research doc §3); 1 node = ≤ ~108 GB at 0.85 util.

**Result 2026-10-14: all five arms built; three boot-verified positive (1, 2, 5 — C1 + battery) and two are documented negatives (3, 4).** Arm table + receipts: `recipes/cybersec/README.md` / `AGENTS.md`.

- [x] **Solo (TP=1): `orcarouter/Qwen3.8-27B-Uncensored-NVFP4` — DONE 2026-10-14 (positive).** 1 node / 24.7 GB measured. Recipe `recipes/cybersec/qwen3.8-27b-uncensored-nvfp4-sglang.yaml`; boots, `GET /v1/models` = repo id; C1 **10.2 / 9.7** t/s (d0 / d8192); house battery **37/37**.
- [x] **Solo (TP=1): `drowzeys/keys-Qwen3.8-27B-NVFP4-DFlash2-Ablit-Cybersecurity-Unlock-1M-Context-YARN-Single-DGXSpark` — DONE 2026-10-14 (positive).** Overlay (ships no weights) via `mods/provide-uncensored-chat-template`, over the AEON-ULTIMATE-UNCENSORED body + an `incoai/Qwen3.8-27B-DFlash2` draft, 1 node. Recipe `qwen3.8-27b-ablit-cyber-unlock-nvfp4-dflash2-sglang.yaml`; boots, `GET /v1/models` = repo id, uncensored template confirmed in the serve log; C1 **33.3 / 26.2** t/s; battery **37/37**.
- [x] **Solo (TP=1): `orcarouter/Nex-N2.5-mini-Uncensored-NVFP4` — DONE 2026-10-14 (documented negative).** Recipe `nex-n2.5-mini-uncensored-nvfp4-sglang.yaml`: NaN sample-time logits → CUDA device-side assert under SGLang; the card's documented vLLM route is blocked on image distribution. Recorded negative, not a shipped serve.
- [x] **Dual (TP=2): `orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4` — DONE 2026-10-14 (documented negative).** Recipe `qwen3.8-flash-next-uncensored-nvfp4-sglang.yaml`: SGLang's compressed-tensors loader refuses the export's `CompressedTensorsW4A16Sparse24` scheme; the card's vLLM route is the next step. Recorded negative.
- [x] **Dual (TP=2): `drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed` — DONE 2026-10-14 (positive).** Overlay via `mods/graft-dsv41-ablit-wo-b` over the Mia 2× Spark EXL3 2.9 bpw base, 2 nodes. Recipe `deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang.yaml`; boots, `GET /v1/models` = the overlay repo id (1M ctx); C1 **63.7 / 67.7** t/s; battery **36/37**; graft 269 s / 284 s per node (inside the 600 s hook budget); refusal probe 0/8 explicit refusals (1/8 completed, 7/8 truncated-empty at the 900-token cap). Table + receipts: `recipes/cybersec/README.md` / `AGENTS.md`.

**Other surfaced arms (not queued):** `orcarouter/GLM-5.3-Flash-Uncensored-NVFP4` (321B, **205.1 GB** —
2-node-heavy/3-node; inherits the archived glm5 Flash serve blocker),
`orcarouter/DeepSeek-V4-Flash-Vision-Uncensored` (304B, `deepseek_v4`),
`drowzeys/keys-Qwen3.8-Flash-Next-NVFP4-dual-ablit-house-qsa-L3-47` (dual 180B ablit, **132.7 GB**; base
`nvidia/…` → licence `other`), `drowzeys/keys-GLM-5.3-Flash-NVFP4-ablit-l15-43-mtp-l45` (169B, MIT),
`drowzeys/MiMo-V2.6-Flash-RL-Abliterated` (310B, FP8/MXFP4). **Over the 1–2-node bar, so recorded but NOT
queued:** `drowzeys/keys-MiMo-V2.6-Pro-RL-Jarrelscy-ARVQ-Abliterated` (`nvfp4_arvq_hybrid`, MIT, gated —
**315.7 GB** on-disk ⇒ ≥3 nodes; owner asked to add it only if it fit 1–2).
