# DONE — completed items archived from `mad-science/TODO.md`

Archived 2026-10-13. Every completed item was copied here verbatim — nested sub-bullets included —
when `mad-science/TODO.md` was cleaned to hold only open work: the `[X]` sweep first, then the later
same-day sweep of the `**DONE 2026-10-13**` items (the glm5 TP=4 window and the TODO-file machinery).
A second sweep followed on 2026-10-14: that session's completed items (General Registry Maintenance,
ds4, glm5, ornith, qwen3, qwen4, ifm, decision, explore, cybersec) plus the session scaffolding were
archived here, copied verbatim — nested `*(Owner decision …)*` notes included.
A third sweep followed on 2026-10-15: that session's completed items (plus a second pass the same
night for the overnight slices) are archived under `# 2026-10-15 sweep` below, each copied verbatim
with a closing note where a follow-up re-measurement finished it.
A fourth sweep followed on 2026-10-18, twice: that session's completed items are archived under
`# 2026-10-18 sweep` and, at the owner's close-out request, the late TP>2 block (glm5, ornith, qwen4,
ifm) under `# 2026-10-18 sweep — late`, with items that were **dropped unrun** by owner policy marked
as such rather than as completed.
Live planning stays in `mad-science/TODO.md`; dated session records live in
`mad-science/SESSION-RECORD.md`.

## General Registry Maintenance
- **DONE 2026-10-13** — Move all completed TODO.md `- [ ]` items to @attic/DONE.md . *(Every completed item was archived verbatim to `attic/DONE.md`; this file is now `[X]`-free.)*
- **DONE 2026-10-13** — Move session records out of the TODO.md file -- keep it clean -- but add a reference to whichever file you put them in. *(The `## Session record` section moved verbatim to `mad-science/SESSION-RECORD.md`; reference added under `# Protocol`.)*
- [X] **Build additional quality testing and benchmarking suites using established industry standard benchmarking tools where feasible — DONE 2026-10-14.** Shipped `tools/bfcl-eval.py`, a BFCL (Berkeley Function-Calling Leaderboard) **v3** scorer for a live OpenAI-compatible endpoint: it ports the official AST checker so the accuracy number is the leaderboard's rule rather than a lookalike, plus the relevance call/no-call categories. Guarded by `tests/test_bfcl_eval.py` (46 tests); offline against the real BFCL v3 AST split the ported checker scores **1000/1000** on a correct model's output. This is the standard the explore lane needed — three of its shortlist models publish BFCL.
  *(Owner decision 2026-10-14: decision #15 ("no new battery tool") was REOPENED; this is the suite built in response. Done as called.)*
- [X] **Serve every sglang arm under the upstream repo id, not the snapshot path (owner report 2026-10-13).** `ornith-1.5-35b-a3b-nvfp4-dflash2-sglang` currently advertises `/cache/huggingface/hub/models--ornith-ai--Ornith-1.5-35B-A3B-NVFP4/snapshots/94e431d9…` as its `model` id — wrong for clients, the proxy and any benchmark that sends the model id. Audit (13 shipped sglang recipes): **11 write `--served-model-name {model}`** (clef, Ling, ornith, qwen3.8-27B DFlash2, all five qwen3.8-flash-next arms, both ds4 shim arms) and **2 write no flag at all** (both IFM K2 arms — SGLang then defaults the id to the model path anyway) — nine of the eleven picked the spelling up in `a60593e` ("Add `--served-model-name` argument to all relevant recipes"): right intent, wrong operand, because `{model}` is the placeholder that gets rebound, so those nine lines must be *deleted* (not kept "for safety") when the declarative key goes in. Mechanism, already recorded in-repo: on a real launch sparkrun rewrites `{model}` *and a `--served-model-name {model}` rendered from the same placeholder* to the prepared on-disk path (`models/runtime.py::bind_runtime_models`, quoted at `mods/tensorfold-dsv41-launcher/launcher.py:176-182` and `tests/test_ds4_recipes.py:1290`), so the flag faithfully advertises the path. **`-n` does not show this** — it still prints the repo id; only a real launch rewrites the flag. **Fix pattern:** drop the hardcoded flag and declare `served_model_name: <upstream repo id>` in `defaults:` — the sglang runtime maps that key to `--served-model-name` and appends it when *absent* (`runtimes/sglang.py:47,372-376`; fill policy `runtimes/base.py:952-981` leaves an existing value intact, which is why the `{model}` spelling wins today). The vLLM lanes already use the declarative key (`explore/kolibri-1-78b-fp8-vllm.yaml`) and the root README documents the repo-id convention; the command-less path in `runtimes/sglang.py:533-535` already serves under `recipe.model`. **Per recipe:** drop/declare, then verify on a real launch — `GET /v1/models` (or `sparkrun cluster check --check-http-models`) must return the repo id; the CLI `--served-model-name` override can probe it live, but override *files* cannot set that key (`core/recipe_overrides.py:90`). Leave the two ds4 shim arms alone if their launcher path→repo-id normalization stays green (guarded today). Also correct the decision lane's "Served-id wart" note (`recipes/decision/README.md:45`) — it blames a missing flag, but the arm boots *with* the flag, so the value is the rebinding; and re-check any lane doc that quotes a path id. Done when every shipped sglang arm reports its repo id in `/v1/models` and no recipe carries the `{model}` spelling of the flag. **2026-10-13 progress (ornith):** `ornith-1.5-35b-a3b-nvfp4-dflash2-sglang` fixed + live-verified (boot `dadfb04b5145d956_8ed3ce77d78f` on `.34`: `/v1/models` → `ornith-ai/Ornith-1.5-35B-A3B-NVFP4`, chat addressed to that id 200; warm TTR port-open 94.7 s). It uses the declarative key **plus** `--served-model-name {served_model_name}` — sparkrun's prescribed spelling (`core/validation.py`'s hardcoded-flag suggestion: "Move the value to defaults.%s and reference it as {%s}") rather than delete-and-let-append: identical final argv (the append no-ops when the flag is present, `runtimes/base.py:931-933`), and it keeps the repo's `InertDefaults` guard green with no exemption. Recipe comment + lane `README.md`/`AGENTS.md` + a lane guard (`tests/test_ornith_honed_chat_template.py`) carry the fix. Remaining: ten `{model}`-spelling arms + the two no-flag IFM K2 arms (SGLang defaults those to the model path; `runtimes/base.py:979-980` makes the append conditional on the key existing). **2026-10-13 sweep complete (all ten + both IFM arms):** every shipped sglang arm now has live `GET /v1/models` evidence of its repo id — clef (`625b43fd997e4d5b_8ed3ce77d78f`, `.34`), Ling (`3effce2e30113dd9_64af2f7668b6`, `.35`), K2 0.9B (`e2b91b75cf01d3ab_8ed3ce77d78f`, `.34`), K2 7B-Uno (`ff7c9715c406eee7_64af2f7668b6`, `.35`), qwen3.8-27B (`3b78f3ef7df2980b_64af2f7668b6`, `.35`), flash-next ×2 (`1753bbfdf3f0a50e_3510a5e0d37d` TP2, `15adecfd945cac5c_8ed3ce77d78f` solo), labquant ×3 (`1895030211ea0500_3510a5e0d37d` TP2), tensorfold (`8ef9b6c9a550c389_3510a5e0d37d`; recipe unchanged — its launcher normalizes the path), knapcio (production serve `a4c699c1299bbbdf_8296561cc1cb` on `.30` answers the repo id; recipe unchanged). The three labquant arms also gained `--revision {model_revision}`: after the fix their only identity tokens are the declared literal and that revision flag — `validate_runtime_command` (branch 1 no longer fires: `--model-path` is the mod-built tree) needs both, boot-proven on `.34+.35`. Observed consequence: the three labquant arms share one cluster id (`name=<served>` folds into the intent hash), so `stop <id>` addresses whichever is current. Class guard `tests/test_recipe_placeholder_resolution.py::ServedModelNameNotRebound` (ds4 arms allowed by name, with the launcher reason); shape documented in `recipes/MECHANICS.md` §Notes; lane receipts in each lane's docs.

## ds4
DeepSeek V4.1
- [X] TP=2 recipe vision head yes or no? no 
- [X] Can it be enabled? yes
- [X] Run a harder image set to quantify the VL-bias effect
- [X] Engram Table builder directly from HF instead of depending on the full model weights present in the local HF cache.
- [X] TP=2 needle-haystack test **2026-10-10: PASS.** 262k sweep 3/3 (depths 10/50/90%, prefill 190–364 s per probe) AND a single ~960k probe at depth 50: 1/1 at 958,919 prompt tokens, 1226.7 s prefill (~782 tok/s). Full record in `/tmp/ds4tp2-needle-{262k,960k}.json`.
- [X] TP=2 stability test since it seems to collapse into looping output while reasoning quite often -- Is there anything that can be done to improve it? **2026-10-10: NOT REPRODUCED.** 9 reasoning-heavy prompts at the served config (temperature 0), then the 3 worst with an 8k token budget: no repeated-window runs in any reply (loop score 1 throughout); two prompts exhaust any budget in non-repetitive reasoning (18,000 chars of fresh reasoning, finish=length — a thinking-budget problem, not a loop). One actionable finding: the serve line ignores REQUEST-level temperature/repetition_penalty (byte-identical replies across override arms), so any future mitigation must go through the TensorFold launcher, not the client.
- [X] Is there anything useful in https://github.com/bertholomus/deepseek-v4.1-flash-dspark-tp4-4xgb10 for our TP=4 recipe? **2026-10-10: one candidate.** The fork is a sibling downstream of MiaAI-Lab (not of our knapcio pin), AGPL — findings usable, code not copied. Only transplantable item: `DSPARK_BLOCK_SIZE` γ 5→2 (+6–12% vs bracketed γ=3 controls at 8k/32k/96k, pre-registered window @ 90cf3a2b), corroborated in direction by our retired EXL3 k-sweep. Being A/B'd on our stack tonight; everything else in the fork is already matched, already rejected for the same reason, or inapplicable (their EP=2 / 0.90 / 8M pool / MRR=8 are all wrong for our lane per §7/§11).
- [X] Check if there's any updated models, quantizations, or runtime improvements that could improve accuracy and throughput. **2026-10-10, CORRECTED:** our pin `58f2321` **IS** knapcio's v2.3 release commit — only two docs-only commits exist after it (2026-10-09), zero touching boot.py/kernels/Dockerfile. **No image rebuild is warranted** (memo: adopt/reject table per hunk; two defer-able ideas: `DSV41_CACHE_GIB=0` third-party KV report, cargo-probe hang workaround). The earlier "upstream moved well past our pin" claim was wrong.
- [X] If yes to either of the above, build and test the recipe upgrades. **2026-10-10: the one candidate (gamma 5→2) was built and A/B-tested — REJECTED.** Same-window paired boots: γ=2 loses at C4/C8 (−5.3%/−2.9%), ties C1, +4.5% at C16. Shipped value stays 5; receipts and mechanism in `recipes/ds4/mods/dsv41-sglang-overlay/launcher.py` (DSPARK_BLOCK_SIZE comment).
- [X] Update the appropriate README.md and AGENTS.md. **2026-10-10:** README carries the needle/stability verification and the γ A/B caveat; the launcher comment holds the full γ write-up with receipts (commit `93d7b5d`).
- [X] **2026-10-11 incident, recovered:** a cleanup loop in this session ran a broad `sparkrun status | grep` and stopped the 20-hour knapcio TP4 serve along with the session's own serves. The lane was relaunched on `.30-.33` and verified healthy (all four nodes, `deepseek-ai/DeepSeek-V4.1-Flash`, 1M context). Lesson recorded to long-term memory: never derive a stop list from a broad status pattern; filter to your own task IDs and review the list before stopping.
- [X] **Check the DSV4.1 checkpoint revision — DONE 2026-10-14.** The recipe now pins
  `model_revision: 5254448103b6254fc646dacbca1cbbf20e9216c1` (`main`, 2026-10-12), **not** the
  image's baked `fb2764a5…`. Both are Hub-resolvable; the A→B delta touches no weights (all 48
  shards byte-identical) — only docs, the reference `inference/`/`encoding/` trees, and the added
  `chat_template.jinja` — so it cannot move a served number. `main` is what every node cache holds
  and what the dated receipts were served from (`2cba9e42…`, its template-carrying ancestor);
  `fb2764a5…` is in no cache, so keeping it would re-distribute and serve a snapshot lacking the
  template the receipts ran with. Re-ran the lane suite on 4 nodes: boot receipt (`GET /v1/models`
  = `deepseek-ai/DeepSeek-V4.1-Flash`; launcher serving `snapshots/5254448103b6…`), C1
  `decode-triage` 38.3 (d0) / 42.5 (d8192) t/s, house battery 19/19 easy + 17/18 hard (same
  `hard-rev`). Decision + receipts: `attic/ds4/AGENTS.md` §5/§5.1; artifacts
  `.scratch/ds4/knapcio-tp4-boot-20261014/`. All four nodes left clear.
- [X] Move the DSV4.1 checkpoint revision into the recipe yaml instead of the TP4 image. Build and push the image.
  *(Owner decision 2026-10-14: build + push + boot-verify this session. Image built+pushed by the
  owner; boot-verified 2026-10-14. The pin landed on the cached `main`, not the baked `fb2764a5…`:
  see the item above and `attic/ds4/AGENTS.md` §5.)*

## glm5
GLM 5.3
- [X] Research this: https://github.com/bertholomus/glm-5.3-tensorfold-tp4-4xgb10 — full assessment in the rewritten `attic/glm/GLM-5.3-RECOMMENDATIONS.md` (repo A = runnable EXL3 3.0bpw TP4 recipe, 82 t/s aggregate measured, engine on the unreleased `glm-dsa-tp4` branch).
- [X] Research this: https://github.com/bertholomus/glm-5.3-flash-nvfp4-gb10-tp4 — repo B = validation/evidence package for GLM-5.3-Flash NVFP4 (qualified receipts, KV ladder, DFlash2 CC BY-NC-ND trap).
- [X] Update the recipe research — `attic/glm/GLM-5.3-RECOMMENDATIONS.md` rewritten 2026-10-10; the reference-image claim corrected 2026-10-11 (the image exists — see below).
- [X] Build out the recipes. **2026-10-11: done as far as a 2-node session can reach.** *(Owner decisions 2026-10-11: attempt a pinnable Flash image — resolved below as the existing `glm53-flash` digest pin; attempt a `glm-dsa-tp4` source build for EXL3 — resolved below as no-build, editable install.)*
  - **Flash image blocker RESOLVED:** `vllm/vllm-openai:glm53-flash` EXISTS on Docker Hub (pushed 2026-09-09; 8.7 GB). Pin = the digest docker resolved on a runner node, `sha256:819ec9c063412e5730d1b0e82046ba540d1bf991f3c4f661a849aae8a0c52374` (manifest-list digest; the Hub API's amd64-image digest `sha256:0674a3ea…` is inside it). Device-free engine inspection of that build (0.28.1rc1.dev580): `glm45`/`glm47` parsers registered, `method: dflash` native, Glm5Next*/GlmMoeDsa* arch classes present, `--moe-backend` is the flag this build wants.
  - **Recipe drafted:** `recipes/glm/glm-5.3-flash-nvfp4-dflash-vllm.yaml` — repo B's runtime-formula.json verbatim, checkpoint pinned to `36c184c6` (169B params, arch `Glm5NextForConditionalGeneration`), plus the three vLLM boot fixes every new lane needed (cleared image entrypoint, snapshot-path pin, spec config held in `defaults.speculative_config`). **NOT boot-verified: TP4 needs 4 nodes.**
  - **EXL3 "source build" resolved as no-build:** the engine is `bertholomus/TensorFold@glm-dsa-tp4` installed editable into `nvcr.io/nvidia/pytorch:26.07-py3` at container start (`tfrun.sh`) — no image exists to build. Engine branch cloned on the head run dir at exactly `ddfad35`.
- [X] DFlash2 draft usability: **owner decision 2026-10-11** — use the DFlash2 drafts (non-commercial cluster use satisfies CC BY-NC-ND); the Flash spec-decode route may be built.
- [X] Run quality benchmarking pass. **2026-10-13: MiaAI-Lab GLM-5.3-Flash EXL3 4bpw TP=2 → 37/37 (19/19 easy + 18/18 hard, 0 misses) on the house battery (`tools/quality-battery.py --tier both --max-tokens 4096`), needle 2/2 PASS at ~1M, DFlash2 acceptance 78.1% over the battery run.** The shipped Flash recipe has no score (never a healthy serve — image blocker above).
- [X] Update the appropriate README.md/AGENTS.md. **2026-10-11:** `recipes/glm/README.md` written (both lines, the no-build engine path, the license note) and root index rows added.
- [X] Trial a TP=4 recipe from the `tp4` branch of this repo (MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks-TensorFold): **2026-10-13 — TP=4 BOOT-VERIFIED on `.30-.33`.** Reused the sibling's engine image (`tensorfold-glm53:v0.6.0`, 106 patches, byte-identical to the public GHCR digest `eb17e092…`) + checkpoint (`Mia-AiLab/GLM-5.3-Flash-EXL3-4bpw-TensorFold` @ `078455ff`, 175.7 GB) — no duplicate build/download. Healthy serve `GLM-5.3-Flash-EXL3` (`--parallel 8`, KV pool **5,834,752 tokens**, fp8 KV); **C1 98.43 ± 5.89 t/s @ d0 / 99.38 ± 10.91 @ d8192**; **DFlash2 acceptance 76.6%**. Runbook bullet in `recipes/glm/README.md` (launcher topology not expressible in the recipe schema). Receipts: `~/benchmarks/glm53-flash-exl3-tp4-trial-20261013/`.
- [X] Trial a TP=2 and TP=3 recipe from the `main` branch of this repo (MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks-TensorFold). **2026-10-13: TP=2 BOOT-VERIFIED** (script launcher on `.34`+`.35`; `/v1/models` → `GLM-5.3-Flash-EXL3`; KV pool 1,875,968–2,289,664 tokens across two boots at the 1M window; DFlash2 acceptance 87.0% mixed / **78.1% over the quality run**; **C1 58.51 ± 4.53 t/s @ d0 / 60.46 ± 3.77 @ d8192**; **quality 37/37**, needle 2/2 at 1M). **TP=3 BOOT-VERIFIED** on `.31`-`.33` (`./start-tp3.sh`, KV pool **4,841,472 tokens**, `--parallel 8`; **C1 65.39 ± 6.65 t/s @ d0 / 65.12 ± 8.88 @ d8192**, DFlash2 acceptance 71.2%). Recorded in `recipes/glm/README.md`. Receipts: `~/benchmarks/glm53-exl3-tp2-trial-20261013/`, `~/benchmarks/glm53-exl3-tp3-trial-20261013/`.
- **DONE 2026-10-13 — the glm5 TP=4 window ran; Flash archived, EXL3 verified.** *(Owner decision 2026-10-13: the Flash recipe is a proven-negative on the pinned public image → archived to `attic/glm/`.)* Flash TP4: boot-attempted, BLOCKED, root-caused — five boots on `.30-.33`, every failure in the container serve log: the pinned public image's SM120 sparse-MLA backend forces the `fp8_ds_mla` KV layout whose `concat_and_cache_mla` kernel needs a 64-dim RoPE tail, but `RedHatAI/GLM-5.3-Flash-NVFP4` is NoPE MLA (`qk_rope_head_dim 0`); `bfloat16`/`nvfp4_ds_mla` KV select no backend, `FLASHINFER_MLA_SPARSE` is unsupported on GB10, and the DFlash2 drafter needs the absent `SupportsEagle3`. Repo B qualified on a local unpublished image — the recipe is correct, the image is the blocker, and it never produced a C1/quality. Receipts: `~/benchmarks/glm53-flash-20261013/`.
  - **EXL3 TP4 BOOT-VERIFIED 2026-10-13**: 4 ranks on `.30-.33` (`tfrun-sglang.sh` + adapted `tp4_start.sh`, base `lmsysorg/sglang:dev-cu13` digest `aa878e8d`, engine `bertholomus/TensorFold@ddfad35`; `TF_GLM_KV=q5 TF_GLM_EMBED_SPLIT=1 TF_GLM_MTP_REUSE=2`, `--mtp-drafts 3 --parallel 4`, `startup estimate 88.58 GiB within 103.22 GiB`). Healthy serve (`GET /v1/models` → `GLM-5.3-EXL3-3.0bpw`; chat `27*43`→`1161`, finish `stop`). **C1 35.67 t/s @ d0 (σ 3.13, n=5) / 35.89 @ d8192**; **MTP-3 acceptance 63.4%**. Recorded as a **runbook, not a recipe** (the engine is an unreleased fork branch installed editable at container start; a recipe needs a baked image + a GLM variant of the TensorFold launcher mod) — runbook + recipe sketch in `recipes/glm/README.md`. Receipts: `~/benchmarks/glm53-exl3-20261013/`.
  - **MiaAI-Lab tp4 branch — recon done, TP=4 trial BOOT-VERIFIED 2026-10-13** (clone `~/src/MiaAI-GLM53-Flash-EXL3-tp4` @ `d220030`; reused the sibling's engine image and the 176 GB `Mia-AiLab/GLM-5.3-Flash-EXL3-4bpw-TensorFold` checkpoint — no build needed). Result in the `Trial a TP=4 recipe …` item above.
- **DONE 2026-10-13** — Select the best recipes from all lanes and move the rest to the `@attic/`: the glm5 Flash recipe is a proven-negative on the pinned public image → **archived to `attic/glm/`** (owner decision 2026-10-13, `#DECISIONS`).
- [X] **Runbook revision refresh (no recipes to pin) — DONE 2026-10-14.** Verified against the HF API and every node's live cache, recorded in `recipes/glm/README.md` §"Revision pins": `Mia-AiLab/GLM-5.3-Flash-EXL3-4bpw-TensorFold` `main` `76c0b517…` (2026-10-03; the TP=2/TP=4 trials' launcher pins `078455ff…`, still resolvable), `bertholomus/GLM-5.3-EXL3-3.0bpw` = `7f057383…` (cached on `.30` until the 2026-10-14 cache reclamation; a revive re-fetches ~273 GB/node), `RedHatAI/GLM-5.3-Flash-NVFP4` `main` `18d55bfd…` (2026-09-18) past the archived `36c184c6…` pin (still resolvable; snapshot absent from every node → a revive re-fetches ~198 GB), engine `bertholomus/TensorFold@glm-dsa-tp4` = `ddfad35…` (matches the head checkout + GitHub branch tip).

## ornith
Ornith 1.5
- [X] Check if there's any updated models, quantizations, or runtime improvements that could improve accuracy and throughput. **2026-10-10: nothing superseding** (scan recorded in `recipes/ornith/README.md`): ornith-ai quiet since 2026-08-29, jzinno DFlash2 unchanged; an SGLang 0.5.21 bump BREAKS the 35B serve line (Mamba/SWA radix-cache args removed upstream); one untested lead = the DFlash2 author's 114.2 t/s reference config (multi-knob confound, needs a same-node A/B).
  - **Operational fact (2026-10-11): `@littlecedar/<name>` resolves from the registry CLONE** at `~/.cache/sparkrun/registries/littlecedar` (registries.yaml → GitHub URL), not the local tree — local edits are invisible to cluster launches until pushed + `sparkrun registry update littlecedar`. The first control boot ran the pre-session recipe for exactly this reason.
  - **Distribution-blocking incident (2026-10-11, fixed):** the runner caches' ornith `chat_template.jinja` was honed in place in September and sparkrun's model-preparation validator now rejects it against hub metadata (`wrong_size`) — every launch died at distribution. Fixed by restoring hub content in the caches and shipping the honed template via `recipes/ornith/mods/ornith-honed-chat-template` + `--chat-template` (guards in `tests/test_ornith_honed_chat_template.py`). The checkpoint is revision-pinned (`94e431d9` + `--revision`).
- [X] If yes to the above, build and test the recipe upgrades. **No — nothing superseding, no upgrade built.** The lane ships unchanged.
- [X] Build testing and benchmarking battery tooling. **RESOLVED 2026-10-11 by survey: no new tool is built.** *(Owner decisions 2026-10-11: standard suites first — adopt `tool-eval-bench` as the shared suite via `sparkrun benchmark tools` (verified on the head node), promote `recipes/ds4/benchmarks/` as the shared hard tier (ifm already scores with it), and keep only the four stdlib instruments no standard reaches: `quality-battery.py`, `qwen4-quality-eval.py`, `pooling-bench.py`, `gate-37111.py`; `needle-haystack.py` stays as the client. Survey receipt: `agent://BenchmarkSurvey`.)*
- [X] A/B the DFlash2 author's 114.2 t/s reference config same-node (multi-knob confound). *(Owner decision 2026-10-11: spend node time on this lead this session.)* **2026-10-11: CLOSED as a negative result with receipts — no knob is distinguishable from boot noise; the shipped config stands.** Ladder (d0 t/s): control 106.8 (old recipe) / 99.3 (honed control-2) / ① draft10 86.5 / ② marlin 108.9 and 103.4 (repeat) / ③ extra_buffer 103.2 / ④ float32 90.4 / ⑤ full author 84.6. Same-config spread on the node is 7.5%; marlin's two runs straddle it, so it is not a win; the losers (① ⑤ ④) are outside the noise. One confirm cell was **voided**: the `.35` boot lost spec decode (30.8 t/s) and was OOM-`Killed` — a memory-starved node, not a recipe cell. Files: `~/benchmarks/ornith-dflash2-ab-20261011/`; write-up in `recipes/ornith/README.md`.
- [X] Run quality benchmarking pass. **2026-10-11: 37/37 (19 easy + 18 hard, zero flakes)** on `tools/quality-battery.py`, one boot — the same perfect score as the qwen3.8-27B DFlash2 arm, at ~3× its C1. Recorded in `recipes/ornith/README.md`.
- [X] Update the appropriate README.md/AGENTS.md. **2026-10-11:** `recipes/ornith/README.md` carries the ladder table, the confirm/void analysis, the honed-template delivery story, the revision pin and the quality score. (The lane had no `AGENTS.md` at that time; one was added 2026-10-13 — see the next item.)
- [X] This model often starts looping while reasoning. Troubleshoot and address the issue. **2026-10-13: NOT REPRODUCED as a decode loop.** A 9-prompt reasoning battery × {temp 0, temp 0.6} × {4096, 8192} on `.35` found zero repeated-window runs (loop score 1 in every arm); the symptom is thinking-budget exhaustion — fresh reasoning ending at `finish_reason=length` — and this SGLang serve line *honors* request-level sampling (unlike the ds4 serve). No recipe knob change; the client-side remedy is `max_tokens`. Recorded in `recipes/ornith/README.md` §"Reasoning-loop investigation"; receipts `~/benchmarks/ornith-loop-20261013/`.
- [X] Add AGENTS.md to this lane. **2026-10-13:** `attic/ornith/AGENTS.md` written (lane state, constraints/traps, the 114.2 A/B negative result, the loop verdict, the validation ritual); the root `README.md` cross-reference updated.
- [X] Re-measure the 35B C1 with a pinned harness. *(Owner directive 2026-10-13: run a TP=1 test on `.35`.)* **2026-10-13: DONE — 99.6 t/s @ d0 (σ 9.1, n=5) and 100.2 t/s @ d8192 (σ 3.9) on `benchmarking/decode-triage.yaml` (decode phase); the prior `~100 t/s` headline holds as measured.** Spec decode engaged (serve-log accept len mean 2.54, well >1); TTR port-open 95 s (warm cache). Recorded in `recipes/ornith/README.md` ("C1 re-measurement") and `attic/ornith/AGENTS.md` §1/§6; receipts `~/benchmarks/ornith-c1-20261013/`.
- [X] **Run additional experiments to confirm this model's quality (owner report 2026-10-13) — DONE 2026-10-14 (bounded null).** A long-horizon agentic re-investigation (`.31`, one boot, the shipped 35B recipe) drove the workload the report is about — a multi-turn tool-calling scheduling session with a growing transcript over near-duplicate work items (`agentic_horizon_probe.py`, scoreable `submit_plan` validation). Detector: per-message and whole-session 25-word-window repeats, session repeats *excluding* quoted input, cross-turn 8-word shingle overlap, and `finish_reason`. Result: **no decode loop** (per-message repeat ≤2, never ≥3; session repeats only from input echoed back; clean terminations) — **not reproduced** on the long-horizon workload either. The 2026-10-13 single-turn null is recorded as such. The owner ratifies the bar. Details: `recipes/ornith/README.md` §"Reasoning-loop investigation"; `attic/ornith/NOTES.md` §5; receipts `.scratch/ornith-horizon-20261014/`.
  *(Owner decision 2026-10-14: the agent proposed the experiment set and the bar; the owner ratifies the result.)*
- [X] **A/B the first-party DFlash draft against the shipped jzinno DFlash2 draft — DONE 2026-10-14 (null; shipped draft now pinned).** Same-node A/B on the shipped 35B arm (`.31`, one boot per arm, decode-phase rows only, n ∈ {4, 8}, `benchmarking/decode-triage.yaml`): the vendor head ([`ornith-ai/Ornith-1.5-35B-A3B-DFlash`](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B-DFlash), `942d20fe…`, plain `DFlashDraftModel`, 0.77 GB) is **indistinguishable from the shipped third-party `jzinno/…-DFlash2`** at n=4 and no better at n=8, so the jzinno draft stands — the null is the result, not a tie-break. The shipped draft is now **pinned** (`speculative_draft_model_revision: 9b4852c0…`, distribution-only) with the `pre_exec` **`refs/main` seed** the pin requires (a SHA-keyed fetch writes no `refs/`, and the container's offline draft-config lookup resolves only `refs/main`) — see `attic/ornith/AGENTS.md` §3.12. The pinned winner's boot scored the house battery **37/37**. Receipts: `~/benchmarks/ornith-dflash-ab-20261014/`.
- [X] **Scope and measure a `9B-NVFP4 + DFlash` arm — DONE 2026-10-14 (shipped + measured).** New recipe `recipes/ornith/ornith-1.5-9b-nvfp4-dflash-sglang.yaml`: target `ornith-ai/Ornith-1.5-9B-NVFP4` (`155f200d…`, dense ~9B, multimodal) + first-party head `ornith-ai/Ornith-1.5-9B-DFlash` (`21be3446…`), 1 node / TP=1 / SGLang DFLASH, no `mamba_*`/`moe_runner_backend`, serving the checkpoint's own multimodal template rather than the 35B's honed one. **Booted + measured 2026-10-14** (`.30`): C1 ≈55 t/s (registry row), `GET /v1/models` = repo id, serve-log `Mean acceptance length > 1`. The first-party draft stays **deliberately unpinned** — an unpinned fetch resolves `refs/main` itself, which a SHA pin would not (an authoring question the boot answered: the pinned SGLang image *does* load a plain `DFlashDraftModel`). Lane guards added (`tests/test_ornith_recipes.py`). Receipts: `~/benchmarks/ornith-9b-20261014/`.
- [X] **A/B the first-party 397B DFlash head against the checkpoint's own MTP head (flagship 4-node arm — queued 2026-10-13) — DONE 2026-10-14 (MTP ships).** The shipped arm specs with the grafted MTP head (`method: mtp`, 3 tokens) and carries only a **card figure** (41.86 t/s, tied to the floating `:latest` tag — the lane has no house measurement; §3.8 wants a digest pin anyway). The third collection head is `ornith-ai/Ornith-1.5-397B-DFlash` (`db9c35a0…`, 2.58 GB, `DFlashDraftModel`, taps 1/9/…/57 of a 60-layer target, MIT, ungated, no published numbers). Keep the target constant — the shipped graft tree (`littlecedar/…-MTP-Graft` = the NVFP4 quant + bf16 MTP MoE) carries both methods; reach for the upstream plain quant `ornith-ai/Ornith-1.5-397B-NVFP4` (`fcefb8b2…`, 241.8 GB, 25 shards) only if the graft's packaging fights `method: dflash`. Swap one knob: `--speculative-config '{"method":"dflash","model":"…","revision":"db9c35a0…","num_speculative_tokens":8}'` (card shape; the MTP config's `max_model_len`/`attention_backend`/`moe_backend` keys are MTP-specific — start minimal) — sparkrun reads draft + revision out of that JSON to distribute the draft to all 4 nodes (`runtimes/_vllm_common.py:357-372`, `vllm_ray.py:61-63`), and the revision must be pinned **there**, never via `model_revision:` (that SHA does not exist in the draft repo → `Revision Not Found`, per the docstring). Traps: (1) `--load-format instanttensor` + `@eugr/mods/instanttensor-hybrid-draft-loader` were built for the MTP head — read that external mod and check the plain-safetensors draft loads (the draft may need the standard loader); (2) first confirm the floating nightly's vLLM exposes `method: dflash` (card: ≥0.20.2, tested 0.28.0) and record the resolved digest for both arms; (3) this is the registry's most expensive arm (235 GB/node, TP=4): one boot per arm, C1 `decode-triage` d0/d8192 + serve-log acceptance, and **re-measure the MTP baseline in the same window** rather than comparing to the 41.86 card figure; the draft adds +2.6 GB/node — watch the util-0.80 budget. **Done 2026-10-14 (extension session, owner-approved spend):** same-window A/B on `.30`–`.33` (one boot per arm, TP=4, decode-phase rows, n ∈ {4, 8}, `decode-triage`) — **MTP ships**: 42.55 ± 2.78 / 38.48 ± 1.91 t/s vs the DFlash head's 37.58 ± 4.45 / 33.64 ± 1.13 (−11.7/−12.6%). The loser's rationale is recorded: no measurable win at the added complexity for this engine, so it stays a one-knob `-o` alternative, not a shipped arm (its higher draft acceptance is a speculator-overhead confound, not a throughput win). §3.8's digest pin landed — the floating `:latest` was **three different builds across the four nodes**; now pinned (`b94ac8ac…`), and the recipe declares + renders the speculative config (the prior `-o`-only knobs never reached the engine). First house numbers beside the card's 41.86. Details: `attic/ornith/AGENTS.md` §3.8, `README.md` §"A/B results"; receipts `~/benchmarks/ornith-397b-ab-20261014/` (commit `e176395`).

**Session result 2026-10-14:** all four staged plans in `attic/ornith/NOTES.md` §2–§5 ran and closed this session (the 397B A/B in the owner-approved extension pass) — the 9B arm (§2), the 35B first-party-DFlash A/B (§3, null), the 397B DFlash-vs-MTP A/B (§4, **MTP ships**), and the long-horizon quality re-investigation (§5, bounded null); each plan's result moved into `README.md`/`AGENTS.md`. The lane had no recipe guard before this session; `tests/test_ornith_recipes.py` covers all three arms now.

## qwen3
Qwen 3.x
- [X] Check if there's any updated models, quantizations, or runtime improvements that could improve accuracy and throughput. **2026-10-10: checkpoint + DFlash2 draft unchanged; the headline is the NEW DSpark v2 draft** (SpecForge-trained for our exact NVFP4 target, card: +26% acceptance, beats EAGLE — on GB300/H200).
- [X] If yes to the above, build and test the recipe upgrades. **Built and measured — NOT an upgrade:** `qwen3.8-27b-nvfp4-dspark-sglang.yaml` boots (DSPARK path works on GB10) but measures 28.5 t/s vs DFlash2's 33.8 on the same decode-triage profile — a ~16% loss. Receipts in the recipe comment; the DFlash2 lane stays shipping.
- [X] Finish building and testing the recipes. The lane ships DFlash2 (shipping, 33.8 t/s) and coder-next (**measured 2026-10-11: 71.7 t/s @ d0**, σ 0.2). The nospec-control and DSpark arms live in `attic/qwen3/`.
- [X] Select the best recipes from all lanes and move the rest to the @attic. **2026-10-11: no move warranted — nothing is dominated on both axes.** coder-next is 2.1× the DFlash2 C1 for two arithmetic hard tasks (35/37 vs 37/37): a role split, not a loser.
- [X] Measure `qwen3-coder-next-int4-autoround-vllm.yaml` (tracked, zero measured numbers anywhere). *(Owner decision 2026-10-11: measure on a free node before the keep/de-ship call — this item is that measurement.)* **2026-10-11: DONE — 71.7 t/s @ d0 (σ 0.2, n=5) and 67.8 @ d8k; the lane's fastest decode, 2.1× the DFlash2 arm.** Serve line pinned to the prepared snapshot; also needed `--default-chat-template-kwargs '{"enable_thinking": false}'` (short replies otherwise land in the reasoning channel with `content: null`). Receipt: `~/benchmarks/qwen3-coder-next-20261011/decode-triage.json`.
- [X] Run quality benchmarking pass. **2026-10-11: paired house battery, same instrument, same window** — DFlash2 **37/37**, coder-next **35/37** (misses `hard-arith-1/2` only). Recorded in `recipes/qwen3/README.md`. The C1 index figure (50 = c=2 aggregate) vs the lane's 33.8 (c=1) conflict remains *surfaced* — they measure different windows; the lane doc says so.
- [X] Clean up directory and artifacts. **2026-10-11: nothing to clean** — the lane dir holds shipped recipes + evidence docs.
- [X] Update the appropriate README.md and AGENTS.md. Lane README carries the DSpark row, the coder-next row (measured + 35/37) and the empty-content trap section; root index updated.
- [X] **Build a recipe from [`MiaAI-Lab/Qwen3.8-27B-DGX-Spark-TensorFold`](https://github.com/MiaAI-Lab/Qwen3.8-27B-DGX-Spark-TensorFold) — DONE 2026-10-14 (shipped + measured).** New recipe `recipes/qwen3/qwen3.8-27b-mlx4bit-tensorfold-sglang.yaml`: TensorFold v0.6.0 (its own engine behind the `runtime: sglang` shim — the ds4 lane's pattern) over `TensorFold/Qwen3.8-27B-MLX-4bit` (MLX affine-4-bit, ~15 GB) + `z-lab/Qwen3.8-27B-DFlash2` drafter, one node / TP=1 / 262k / FP8 KV / image+video input. **Booted + measured** on `.30` (boot `fe3054ad67464c54_2d38dfc4605e`): decode-triage d0 **41.3 ± 4.0** / d8192 **41.7 ± 2.4** t/s, `GET /v1/models` → `Qwen3.8-27B`, house battery **37/37**. Guarded by `tests/test_qwen3_recipes.py`. Details: `recipes/qwen3/README.md`.

## qwen4
Qwen 4.x (and 3.8 Flash Next)
- [X] Check if there's any updated models, quantizations, or runtime improvements that could improve accuracy and throughput. **2026-10-10:** the labquant upgrade candidate (step-5500 QAD at main `6c01ac37`) has a **complete per-mod re-verification plan** — `attic/qwen4/status/W14-LABQUANT-5500-MOD-PLAN.md`: one mod breaks (fail-closed, fix direction known), one is obsolete (drop it), five survive. NVIDIA's official NVFP4 quant: boot-answered **REJECTED on this engine**.
- [X] There is a confirmed by a trusted source solo DGX Spark node recipe somewhere on the internet for Qwen 3.8 Flash Next -- See if you can find it. **FOUND and ported two arms:** the SGLang cookbook's verified single-Spark cells (file-backed PLE) and the eugr registry's sparkrun-native solo recipe. The old "no TP=1 lane" conclusion had the wrong mechanism: the blocker is the ~47.7 GiB PLE table, not weights+KV.
- [X] If yes to either of the above, build and test the recipe upgrades. **2026-10-10: both solo arms built, BOOT-VERIFIED and W3-battery'd — SGLang route 38/38; vLLM route 38/38.** Operational constraint recorded: sparkrun model distribution to a node without the checkpoint fails at the 16 MiB safetensors-index inventory limit.
- [X] Select the best recipes from all lanes and move the rest to the @attic. **No move made — nothing is a clear loser.** The full ranking with provenance is now **tracked** at `attic/qwen4/SELECTION-RANKING.md` (see below). NVIDIA arm went to attic with its boot verdict.
- [X] Run quality benchmarking pass. **W3 battery on both new solo arms: 38/38 each (n=1, saturated — cannot discriminate checkpoints).** Receipts: `~/benchmarks/qwen4-solo-20261010/`.
- [X] Update the appropriate README.md and AGENTS.md. *(Pre-existing item from the 2026-10-10 pass.)* **Closed 2026-10-12:** the lane docs already carry the solo arms — `recipes/qwen4/README.md` §"The TP=1 lane now exists" + its recipe table, `AGENTS.md` §10.5/§10.6 — no doc delta found in a review pass.
- [X] Commit a redacted tracked copy of `.local/SELECTION-RANKING-DRAFT.md` as `attic/qwen4/SELECTION-RANKING.md`. *(Owner decision 2026-10-11.)* **DONE** (`0a9421e` + `0d3d0e6`): the snapshot plus a 2026-10-11 delta and a session-outcomes section covering every lane; addresses masked per the repo convention.
- [X] Trial a TP=2 recipe from this repo: https://github.com/MiaAI-Lab/DeepSeek-v4-Flash-DSpark-2x-DGX-Spark **2026-10-13: DONE — boot-verified via the repo's own docker-compose launcher on `.34`+`.35` (rank 0 = `.34`, serves `:8888`). Checkpoint `deepseek-ai/DeepSeek-V4-Flash-Vision-Exp` @ `86f746b3` (157 GB ×2), image `ghcr.io/anemll/dspark-vllm-gx10:0.1.1` (18.8 GB); healthy serve, `/v1/models` → `deepseek-v4-flash-vision-exp`, `max_model_len 1048576`, KV **17.27 GiB / 2,512,188 tokens**; **C1 44.85 t/s @ d0 (cv 9.4%) / 40.53 @ d8k**, DSpark accept length ~2.6–3.6. No sparkrun recipe added — the compose's ~1500-line runtime-hotfix command (40+ bind-mounted patch files + bind mounts) is not expressible in the recipe schema. Fabric: the repo default points at the DOWN `f1`; the working env mirrors the live sparkrun job (`NCCL_SOCKET_IFNAME=enP7s7,enP2p1s0f0np0,enp1s0f0np0`, Gloo/TP/MASTER on `enP7s7`/the management subnet). Receipts: `~/benchmarks/deepseek-v4-flash-tp2-20261013/`.**
- [X] **Re-pin (and re-verify the mods for) the labquant checkpoint — DONE 2026-10-14.** Cut first (owner call): of the six arms measured in one 2026-10-14 window, the two survivors were re-verified/re-pinned against `local-inference-lab/Qwen3.8-Flash-Next-NVFP4` `main` `6c01ac378d22…` (the `step-5500 QAD` candidate the W14 plan named). The mod chain is now **6 mods** (one dropped as obsolete, one fixed) and **vision is restored**; the TP=2 survivor (the labquant balanced base) re-pinned to `6c01ac37` and re-benched: **40.32 ± 1.94 @ d0 / 43.29 ± 2.68 @ d8192** t/s. Details: `attic/qwen4/AGENTS.md`, `attic/qwen4/SELECTION-RANKING.md`; receipts `~/benchmarks/q4-*-triage_1014_*`.
  *(Owner decision 2026-10-14: cut first — measure the six arms, pick the two, then re-verify/re-pin only the survivors against `6c01ac37`. Done as called.)*
- [X] **Cut the lane to two arms — DONE 2026-10-14.** `recipes/qwen4/` now ships **exactly two** production recipes: the fastest **TP=1** (`qwen3.8-flash-next-nvfp4-solo-vllm-b12x`) and the fastest **TP=2** (`qwen3.8-flash-next-nvfp4-labquant-sglang`, the balanced base). The other four (`…-labquant-longctx-sglang`, `…-labquant-highcon-sglang`, the RadixArk `…-nvfp4-sglang`, and the sixth arm `…-solo-sglang`, re-measured after a readiness failure) were `git mv`'d to `attic/qwen4/arms/` with a provenance row in `attic/qwen4/ARMS-MANIFEST.md`; 1M context dropped. Details: `recipes/qwen4/README.md` §"What was measured, and the cut".
  *(Owner decision 2026-10-14: confirmed — exactly two shipped arms (fastest TP=1 + fastest TP=2), the rest swept to `attic/`; 1M context droppable. Done as called.)*

## embed
Any embed model
- [X] Move all embedding recipes to @recipes/embed
- [X] Update the appropriate README.md and AGENTS.md.

## rerank
Any rerank model
- [X] Move all rerank recipes to @recipes/rerank
- [X] Update the appropriate README.md and AGENTS.md.

## decision
Any decision model
- [X] Research decision models and find high-quality, fast, low-memory candidates that can co-locate with other small models (such a an embed, rerank, and tts model). *(Owner decision 2026-10-11: leads named by the owner = Cloudflare/Clef and Jev distillations on HF; co-location with embed/rerank/tts is the core constraint; shortlist research was mine.)* **2026-10-11: DONE** — `attic/decision/DECISION-MODELS-RESEARCH.md` (both owner leads resolved: Cloudflare/clef(-flash) open-weight Apache-2.0 on `/v1/systemone` under SGLang; "Jev distillations" = the `autotrust/JEV-*` distilled-student family, KL ≈ 0.019 receipts, native vLLM). Shortlist of 8 + co-location budget vs the shipped embed+rerank pair.
- [X] Build out the recipes. **2026-10-11: TWO recipes BOOT-VERIFIED.** `jev-9b-decision-vllm.yaml` (vLLM; `/v1/models` lists the base model **and** the `jev-decision` LoRA adapter, and the scoring path returns processed `top_logprobs`) and `clef-flash-decision-sglang.yaml` (digest-pinned `lmsysorg/sglang:dev-clef`; a real `/v1/systemone` round-trip with calibrated probabilities).
- [X] Build the next research-ranked candidate: `vllm-sr/Decision-2.0-Kai-0.6B` (+ the `Sol-2B` ladder arm) — the cheapest lane proof (4.9 ms, 1.4 GiB); costs a new runtime family (`vllm-srun`). **2026-10-13: BOTH BUILT AND BOOT-VERIFIED on `.34` (CPU, A725 pins).** `vllm-srun` ships inside the `vllm-sr` router image — `ghcr.io/vllm-project/semantic-router/vllm-sr` pinned by index digest `2c30eeb3…`, arm64 pull-verified (the plan's `model-runtime` image does not exist: 404 package; `vllm-srun` is not on PyPI); revisions are the runtime's own golden-checked pins (Kai `cd49ea38…`, Sol `64235bef…`). Boot blocker root-caused and fixed in-recipe: the image (python-slim) has no standalone `kill` binary, so sparkrun's `docker exec kill -0` liveness check exits 127 and misreports launch failure while the serve comes up healthy — the recipes install a bash-builtin kill shim and run as root. Kai TTR 8.1 s / HTTP-ready 10.1 s; Sol first-try; `/health` golden-ready; card-example `/v1/systemone` smokes pass on both. Lane doc: `recipes/decision/README.md` §"vllm-srun arms".
- [X] Run quality benchmarking pass. **2026-10-11: clef-flash DONE — official `tool-eval-bench` v2.8.0 `--decision-bench-only`: Decision Accuracy 70.3% (1406/2000)** on the Typed Decisions split, 400 cases in 81.5 s, zero request errors, ★★. **2026-10-12/13: the whole lane scored on the same instrument.** JEV-9B **67.0% (1340/2000), ★★, 0 errors** through the new `tools/jev-decision-bench.py` (the JEV-shaped harness this item asked for: card-verbatim `/v1/completions` System 1 contract, TEB-mirror metrics, `--selftest` exit 0; one request per question — comparability caveat recorded); Kai-0.6B **47.5% (949/2000), ★★** and Sol-2B **55.0% (1100/2000), ★★** via the tool itself (`--decision-bench-only` lives on the top-level parser; `--json-file` writes no file in v2.8.0 — the markdown report under `~/runs/` is the durable artifact, copied to receipts). Ladder: clef 70.3 > JEV 67.0 > Sol 55.0 > Kai 47.5. Receipts: `~/benchmarks/jev-decision-20261012/`, `~/benchmarks/kai-sol-20261012/`.
- [X] Select the best recipes from all lanes and move the rest to the @attic. **2026-10-11: no attic move — both recipes keep** (JEV-9B is the native-vLLM distilled student; clef-flash the only first-class SGLang decision model with a measured score).
- [X] Update the appropriate README.md and AGENTS.md. **2026-10-11:** `recipes/decision/README.md` (verified surfaces, the prefill-only scorer contract, the served-id wart, the co-location budget and core split) + root index rows.
- [X] Check if a CPU and GPU model can be run in tandem to increase the overall decision accuracy. **2026-10-13: YES, but marginally, and only for the right pairing.** clef-flash (GPU, SGLang :8020) + Kai-0.6B (CPU, vllm-srun :8000) co-served on `.34`, pooled by an equal-weight **linear mean** of their per-question `/v1/systemone` distributions on the same 400-case/2000-decision split: **71.6% vs clef's 70.3% alone (+1.3 pts, McNemar p=0.012, bootstrap 95% CI [0.35, 2.20])**; the log-linear (geometric-mean) pool is 71.3% with better calibration (KL −20%, Brier −22%). Gain concentrated in the `score` kind (+2.6). **Pairing-specific, not a CPU+GPU property:** clef+Sol-2B is a small net loss (69.9%) and a 3-way pool dilutes (69.6%) — Kai is the more complementary partner (argmax agreement with clef 46.3% vs Sol 58.7%). **Co-serve is clean but asymmetric:** no OOM and both accuracies bit-reproducible, the GPU model unaffected (p50 205→210 ms), the CPU model ~45% slower under co-residency (p50 5699→8253 ms; 2100→3087 s per full bench) — an isolation probe shows Kai's p50 **856→1800 ms** with clef merely *resident*, so the tax is the GPU model's residency, not its traffic (both serve processes ship pinned to the SAME `0-4,10-14` cluster; clef holds ~90 GiB → node available 121→16 GiB). New `tools/decision-tandem.py` (stdlib-only, `--selftest` exit 0). Lane doc: `recipes/decision/README.md` §"CPU+GPU tandem probe". Receipts: `~/benchmarks/decision-tandem-20261013/`.
- *(Resolved 2026-10-14: the `vllm-srun` runtime pins its own validation revisions — its golden
  reference answers attach to, and are looked up by, content identity for the image's pinned
  revision, so a newer revision is served but golden-`unverified`, never `matched`; both recipes
  left as-is. The Hub drift is cosmetic anyway — pin vs `main` differs by `assets/banner.png`
  alone. Determination + inspecting-command evidence: `recipes/decision/README.md` § "Revision-drift
  determination"; receipts `~/benchmarks/decision-revision-20261014/`.)*

## explore
Any model with reasoning and tool-calling capabilities
- [X] Research available models and find high-quality, fast, low-memory candidates that push the frontier. **2026-10-11: DONE** — `attic/explore/EXPLORE-MODELS-RESEARCH.md` (8 families shortlisted; five claims in the Oct-10 `EXPLORE-CANDIDATES.md` corrected; top three = Nemotron-3.5-Lightning / Ling-3.0-flash / Kolibri-1).
- [X] Build out recipes. *(Owner decisions 2026-10-11: no recipe cap — build whatever fits the budget; emphasis follows the selection weighting.)* **2026-10-11: TWO recipes BOOT-VERIFIED, both measured.**
  - `nemotron-3.5-lightning-30b-nvfp4-dspark-vllm.yaml` — TP=1, **77.7 t/s @ d0** (σ 9.8, n=5), DSpark acceptance length 3.67 / 88.9% rate, house battery **33/37**. Below the third-party 93-96 t/s on this node, so quote ours.
  - `ling-3.0-flash-int4-dspark-sglang.yaml` — TP=1, **45.5 t/s @ d0** (σ 5.5, n=5), house battery **37/37** (ties the best in the pass). DSPARK engaged: steady-state accept len 3.64–3.73 under 4 concurrent generations (up to 116.7 t/s aggregate); the third-party ~83 t/s was NOT reproduced — the acceptance difference arithmetically accounts for most of the gap, and *why* theirs is higher is untested. The boot caveat is **resolved** (needle-probed 2026-10-11: the `rope_scaling` warning is benign, but 262k is not servable at the shipped mem-fraction — see the session follow-ons).
  - Three vLLM boot traps found and baked into the recipes (all documented in `README.md`): `executor_config.entrypoint: ""`, the spec config held in `defaults.speculative_config` (else the draft is never distributed), `--default-chat-template-kwargs '{"enable_thinking": false}'`.
- [X] Run quality benchmarking pass. **2026-10-11: both arms done** — Nemotron 33/37 (misses `wp-3`, `hard-arith-1/2`, `trick-3`), Ling 37/37.
- [X] Select the best recipes from all lanes and move the rest to the @attic. **2026-10-11: no attic move — both keep.** Ling is the quality/speed balance (37/37 at 45.5 t/s), Nemotron the speed arm (77.7 t/s at 33/37).
- [X] Update the appropriate README.md and AGENTS.md. **2026-10-11:** `recipes/explore/README.md` (both arms, measured + quality, the traps, the next candidates) + root index rows.
- [X] Next by the ranking: `Aleph-Alpha/Kolibri-1` **BUILT, BOOT-VERIFIED and MEASURED 2026-10-12 — kept.** `recipes/explore/kolibri-1-78b-fp8-vllm.yaml` on stock digest-pinned `vllm/vllm-openai:v0.29.0` + the vendor pure-Python plugin (`recipes/explore/mods/install-kolibri-plugin`, fail-closed import/entry-point guard). KV 20.03 GiB → 1,961,775 tokens at 262k; chat round-trips verified both with and without thinking; C1 **47.3 t/s @ d0** (σ 0.10, n=5) / 46.3 @ d8k — 2.3× the stock-build floor 20.4, near the sm121 third-party 48; battery **36/37 @ `--max-tokens 4096`** (reproduced twice; 37/37 union with the default-384 run — the lone `needle-1` miss is thinking-budget truncation, and `--max-tokens` was added as an optional flag to `tools/quality-battery.py`, default 384, semantics unchanged). Keep rationale: accuracy-champion role at 1 node, not dominated (≥ Ling's 45.5). `vllm-sr/d3-edge` remains watch-only. Receipts: `~/benchmarks/kolibri-20261012/`.
  - [X] Pick the two overall best models from the explore lane and put the rest in the @attic/ . **2026-10-13: DONE — kept Nemotron-262k (rank 1, 77.7 t/s) and Kolibri-1 (rank 2, 47.3 t/s); all four arms were single-node, so the weighting's speed criterion decided.** Moved to `attic/explore/` with `ARMS-MANIFEST.md`: `ling-3.0-flash-int4-dspark-sglang` (45.5 t/s, below Kolibri, and the memory-heaviest arm) and `nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm` (a variant of the kept 262k recipe: 72.2 t/s, util 0.91). Pure `git mv` renames; no test/guard/doc referenced the moved paths.
  - [X] Update all relevant README.md files. **2026-10-13:** `recipes/explore/README.md` (the two keepers + selection rationale + archived pointers) and the root `README.md` Explore table (two rows + the selection note) updated; root `AGENTS.md` exploration/attic rows corrected to `(2)`.
- [X] **Re-pin Kolibri-1 (main moved past the pin) — DONE 2026-10-14.** Diffed the deltas (weights / tokenizer / chat template), moved the pin to `258cae8ffffc…`, re-ran the house battery + `decode-triage` (re-verified **47.4 t/s, 37/37 @4096**) and re-confirmed the plugin / `kolibri1` parser contract. Details: `recipes/explore/README.md`.
- *(Owner decision 2026-10-13: the deciding factor for explore models is **accuracy**, with preference for smaller and faster models — supersedes the node-count→speed default. Re-ranked: **Ling-3.0-flash** (rank 1, 37/37) and **Kolibri-1** (rank 2, 36/37 = 37/37 union, smaller + faster) are kept; Nemotron-262k and its 1M variant moved to `attic/explore/`.)*
- [X] **Pin the DSPARK draft (Ling, rank 1) — DONE 2026-10-14.** The draft moved to `d60b0e12…`; DSPARK acceptance was re-checked on the moved draft, the draft revision **pinned**, and `decode-triage` + the house battery re-run — re-verified **54.7 t/s, 37/37** (the shipped 45.5 was measured on the 2026-10-11 draft). Details: `recipes/explore/README.md`.
- *(The archived Nemotron arms' `nvidia/…NVFP4-DSpark` draft also moved to `6d127b50…` on 2026-10-12 and was never pinned, so the 2026-10-13 acceptance-length non-reproduction (3.67 → 1.66) may be a draft change and not only the suspected metric-window artifact — re-check if those arms are revived.)*
- [X] **Poolside Laguna XS-2.1 arm (queued 2026-10-13 — queue rank 1) — DONE 2026-10-14 (shipped + measured).** New recipe `recipes/explore/poolside-laguna-xs-2.1-nvfp4-dflash-vllm.yaml`: `poolside/Laguna-XS-2.1-NVFP4` (33B-A3B, 262k, OpenMDW-1.1, 21.6 GB) + the first-party `Laguna-XS-2.1-DFlash` draft, 1 node / TP=1; both repos pinned (`d32afde8…` / `5c36361a…`). Checklist (a)–(f) all PASS — import check (`LagunaForCausalLM` + `laguna_dflash` + both `poolside_v1` parsers), **NVFP4 engages on SM121** (the INT4 23.9 GB fallback was not needed), draft distributes, depth sweep n=3, battery **36/37 @4096 @ 57.4** t/s. Details: `recipes/explore/README.md`; receipts `~/benchmarks/explore-laguna-20261014/`.
- [X] **Poolside Laguna S-2.1 arm (queued 2026-10-13 — queue rank 2, also 1 node) — DONE 2026-10-14 (shipped + measured).** New recipe `recipes/explore/poolside-laguna-s-2.1-nvfp4-dflash-vllm.yaml`: `poolside/Laguna-S-2.1-NVFP4` (118B-A8B, 1M ctx, OpenMDW-1.1) + the quant-matched `Laguna-S-2.1-DFlash-NVFP4` draft, 1 node / TP=1. **Boot-verified on `.35`** (task `e57eaed458e6b584_64af2f7668b6`): `GET /v1/models` → repo id, **FP4 path native on `sm121`**, KV pool 125,796 tokens, battery **32/37** @ ~20.5 t/s C1. The research template's 262k window does **not** fit one Spark — the pinned August-2026 checkpoint loads **95.61 GiB**, not the ~67 GiB the older pre-August sweep carried. Draft-license gap recorded in the recipe (the shipped draft declares no license). Details: `recipes/explore/README.md`.
  *(Owner decision 2026-10-14: ship the recipe — a recipe ships a repo id, not weights; the downloader accepts the license. Done as called.)*
- [X] **Qwen-Image-2.1-Turbo arm — DONE 2026-10-14 (shipped + measured; owner un-deferred).** New recipe `recipes/explore/qwen-image-2.1-turbo-7b-bf16-diffusers-script.yaml` + `recipes/explore/mods/qwen-image-2.1-turbo-launcher` — the lane's first non-`sglang`/vLLM engine: `Qwen/Qwen-Image-2.1-Turbo` (pinned `fc13ba1986`) served by diffusers' `QwenImage21Pipeline` out of a venv the mod stages on the image's own torch, one node. **Boot-verified on `.34`** (TTR 206.1 s, pipeline load 188.0 s; `GET /v1/models` → repo id): 1024² at the checkpoint's shipped 8-step schedule, CFG=1 → **11.33 / 11.41 s** steady (first request 12.30 s; the derived `54.1 × 8/40 ≈ 10.8 s` holds, +5%); peak 36.85 GiB alloc / 37.68 GiB reserved; reference-image edit +3.5 s; same prompt+seed repeat wrote a **byte-identical PNG**. Two bring-up defects found and fixed in the mod (the container's non-root user breaking `reown()`, and a heredoc piped into `log()` killing the hook with `rc=120`). **License: `qwen-research` — NON-COMMERCIAL ONLY**; ships as a banner-marked **eval-only** entry. Details: `attic/explore/QWEN-IMAGE.md`; receipts `~/benchmarks/qwen-image-20261014/`.
  *(Owner decision 2026-10-14: media-gen arms deferred to a separate pass; when built, ship the recipe (license policy) and use the confirmed §6 acceptance criterion. Owner un-deferred 2026-10-14; done as called.)*
- [X] **LTX-2.5 arm — DONE 2026-10-14 (shipped as a runbook, not a recipe).** Access: repo is `gated: auto`; the cluster token (`twichert`) **has acceptance** (README resolve → HTTP 200), so the arm was measured rather than blocked — a fresh node still needs the per-repo accept + `hf auth login` (documented prerequisite, cybersec precedent). ComfyUI **v0.34.0** pinned as a unit, torch 2.14.1+cu130, clock capped at 2200 MHz (§6(e) sustained-load fix). Two-stage nvfp4 run on `.35`: stage 1 distilled 8-step @ 672×384 → `LTXVLatentUpsampler` ×2 → 3-step refine @ **1344×768, 121 frames @ 24 fps with audio**; **cold 100.3 / 90.1 s** (two reps), **warm 80.1 s**; stage split 14.0 load / 16.7 stage 1 / 2.5 upscale / 20.8 refine / 46.2 decode+mux; **peak 83.6 GiB**; output verified by `ffprobe` (h264 1344×768 24 fps 121 frames + AAC) and a decoded frame (not garbage). NVFP4 native on `sm121` via comfy-kitchen. Runbook `recipes/explore/ltx-2.5-runbook/` + lane notes `attic/explore/LTX-25.md`; receipts `~/benchmarks/ltx25-20261014/`.
  *(Owner decision 2026-10-14: deferred to a separate pass; ship gated arms with a documented per-node `HF_TOKEN` + acceptance prerequisite; the §6 acceptance criterion is confirmed. Owner un-deferred 2026-10-14; done as called.)*
- [X] **Humanizer-12B arm (queued 2026-10-13 — text-rewriting helper, outside the lane brief) — DONE 2026-10-14 (shipped + measured).** New recipe `recipes/explore/humanizer-12b-vllm.yaml`: `jialinyyzz/humanizer` (12B `google/gemma-4-12B` finetune, Apache-2.0, 1 node) served as the lane's first **`/v1/completions`** arm with the byte-exact `instr + draft + sep` prompt from `prompt_format.json`. Boot-verified (`GET /v1/models` → `jialinyyzz/humanizer`, 8192 ctx); §7(c) measurement: 131.7 s per 1k output tokens, 20 number/date/name flags all reviewed as the same value. Details: `recipes/explore/README.md`; receipts `~/benchmarks/humanizer-20261014/`.
  *(Owner decision 2026-10-14: in scope this session; the §7 acceptance criterion is confirmed. Done as called.)*

## Session follow-ons (restated 2026-10-12)
- [X] **explore/Ling: needle-probe the 262k window** — RESOLVED 2026-10-11 (`27c96d5`): the `rope_scaling` warning is benign (the checkpoint declares no scaling at all; native 262,144) and a verbatim needle is retrieved at 8k/64k/150k. **But 262k is not servable on this boot** — at `mem-fraction-static 0.75` the KV pool holds 176,203 tokens; a 200k request truncates and then OOMs.
- [X] **explore/Ling: 262k servability — RESOLVED 2026-10-12: 262k servable at `mem-fraction-static 0.80`; that rung SHIPPED.** Ladder first rung 0.80 booted clean on `.35`: `max_total_num_tokens=313,752` (0.75 measured 176,203; 0.85/0.87 rungs unneeded — 0.87 stays the documented ceiling). The 262k-window needle **PASS** at depths 10/50/90 (~256.6k server-counted tokens per prompt, the receipted 2026-10-11 probe instrument re-pointed at the new serve), and a 4-way concurrency smoke completed with zero OOM/retract events. Receipts: `~/benchmarks/ling-262k-20261012/`.
- [X] **explore/Nemotron: 1M-context arm — RESOLVED 2026-10-12: the card's 1M claim CONFIRMED on GB10.** `recipes/explore/nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm.yaml` (shipped recipe + exactly `max_model_len: 1000000`, `gpu_memory_utilization: 0.91`); vLLM did not refuse the window — KV 87.27 GiB → 21,344,213 tokens. 1M-window needle **PASS** at depths 10/50/90 (~982k server-counted tokens, Nemotron-calibrated 3.8590 chars/token; a first pass with Ling's 4.0546 ratio under-shot and is kept as the TRUNCATED receipt). Measured C1 **72.2 t/s @ d0** (σ 15.1, n=5) vs the 262k arm's 77.7. Swap caveat measured: ~1 GiB free + 2.05 GiB swap allocated during 1M prefills, zero swap-in/out under needle load; sustained multi-tenant load untested. The 262k/0.80 recipe remains the shipped default. Receipts: `~/benchmarks/nemotron-1m-20261012/`.
- [X] **explore/Nemotron: checklist leftovers** — CLOSED 2026-10-11 (`b9a2c35`, `53290ee`): the `moe_backend: marlin` pin was found inert (an edit had dropped the `--moe-backend` line; sparkrun validation stays silent for a flag-map key the template omits) — restored; the verified boot ran `moe_backend='auto'` and vLLM auto-selected marlin anyway, so the numbers stand. `--tool-call-parser qwen3_coder` verified (forced `tool_choice` → structured `tool_calls`). The 1M-context claim was reclassified as a separate arm, not a checklist item.
- [X] **decision: a score for JEV-9B — RESOLVED 2026-10-12: Decision Accuracy 67.0% (1340/2000), ★★, 0 errors.** The JEV-shaped harness exists: `tools/jev-decision-bench.py` (stdlib-only, card-verbatim `/v1/completions` request + `z=(lp+bias)/T` softmax, TEB v2.8.0-mirror metrics, sha256 fail-closed case manifest, `--selftest` exit 0). Card-example smoke reproduced before scoring ({issue_warning 0.328, renegotiate 0.144, dual_source 0.528, maintain 0.001} vs card's ≈{0.33, 0.14, 0.53, 0.001}). Per kind: noul 79.3 / choice 67.2 / score 57.6. 132 ms median per decision (serial, one request per question); 3.3 pts behind clef's 70.3 on the shared instrument. Lane doc: `recipes/decision/README.md` §"JEV-9B official score". Receipts: `~/benchmarks/jev-decision-20261012/`.

## ifm
IFM K2-Horizon
- [X] **Re-pin the K2-Horizon checkpoints.** Both reps have moved past the recipe pins and the `.30` cache holds the new revisions: `IFM/K2-Horizon-0.9B` `main` `383cb66347be…` (2026-10-06) vs pin `9fa6faa55fe1…`; `IFM/K2-Horizon-7B-FP8` `main` `ea739ec816e0…` (2026-10-03) vs pin `59d473210f0b…`. Diff the deltas, re-pin `model_revision:`, re-run the lane's benches + the dense accuracy set (`gsm8k`/arc/house), and re-confirm UNO spec-decode engagement on the 7B. — **DONE 2026-10-14**: both re-pinned + guards updated; deltas = card-only (7B) and card+templates (0.9B); re-bench + accuracy on `.31` reproduce every cell inside the lane noise floor; UNO accept len mean 4.15 over 838 samples. Details: `attic/ifm/NOTES.md` 2026-10-14 session.

## cybersec
Cybersecurity-research (red-team) abliterated / uncensored models
*(queued 2026-10-14 — owner directive; sources scanned `hf.co/drowzeys` and `hf.co/orcarouter/collections`.)*

Five arms, all **abliterated/uncensored** and all **gated** (`gated: auto` — a responsible-use agreement
plus a per-node `HF_TOKEN`; releases accepted 2026-10-14). **Owner decision 2026-10-14: ship gated arms
with a documented per-node token + acceptance prerequisite.**
Sizes below are **measured on-disk weight bytes** (Hub `files_metadata`, 2026-10-14), not the Hub
`Parameters` field (explore research doc §3); 1 node = ≤ ~108 GB at 0.85 util.

**Result 2026-10-14: all five arms built; three boot-verified positive (1, 2, 5 — C1 + battery) and two are documented negatives (3, 4).** Arm table + receipts: `recipes/cybersec/README.md` / `AGENTS.md`.

- [X] **Solo (TP=1): `orcarouter/Qwen3.8-27B-Uncensored-NVFP4` — DONE 2026-10-14 (positive).** 1 node / 24.7 GB measured. Recipe `recipes/cybersec/qwen3.8-27b-uncensored-nvfp4-sglang.yaml`; boots, `GET /v1/models` = repo id; C1 **10.2 / 9.7** t/s (d0 / d8192); house battery **37/37**.
- [X] **Solo (TP=1): `drowzeys/keys-Qwen3.8-27B-NVFP4-DFlash2-Ablit-Cybersecurity-Unlock-1M-Context-YARN-Single-DGXSpark` — DONE 2026-10-14 (positive).** Overlay (ships no weights) via `recipes/cybersec/mods/provide-uncensored-chat-template`, over the AEON-ULTIMATE-UNCENSORED body + an `incoai/Qwen3.8-27B-DFlash2` draft, 1 node. Recipe `qwen3.8-27b-ablit-cyber-unlock-nvfp4-dflash2-sglang.yaml`; boots, `GET /v1/models` = repo id, uncensored template confirmed in the serve log; C1 **33.3 / 26.2** t/s; battery **37/37**.
- [X] **Solo (TP=1): `orcarouter/Nex-N2.5-mini-Uncensored-NVFP4` — DONE 2026-10-14 (documented negative).** Recipe `nex-n2.5-mini-uncensored-nvfp4-sglang.yaml`: NaN sample-time logits → CUDA device-side assert under SGLang; the card's documented vLLM route is blocked on image distribution. Recorded negative, not a shipped serve.
- [X] **Dual (TP=2): `orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4` — DONE 2026-10-14 (documented negative).** Recipe `qwen3.8-flash-next-uncensored-nvfp4-sglang.yaml`: SGLang's compressed-tensors loader refuses the export's `CompressedTensorsW4A16Sparse24` scheme; the card's vLLM route is the next step. Recorded negative.
- [X] **Dual (TP=2): `drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed` — DONE 2026-10-14 (positive).** Overlay via `recipes/cybersec/mods/graft-dsv41-ablit-wo-b` over the Mia 2× Spark EXL3 2.9 bpw base, 2 nodes. Recipe `deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang.yaml`; boots, `GET /v1/models` = the overlay repo id (1M ctx); C1 **63.7 / 67.7** t/s; battery **36/37**; graft 269 s / 284 s per node (inside the 600 s hook budget); refusal probe 0/8 explicit refusals (1/8 completed, 7/8 truncated-empty at the 900-token cap). Table + receipts: `recipes/cybersec/README.md` / `AGENTS.md`.

## Concurrency ladder (registry-level)
- [X] **Add the ladder profile the columns are named for** — a tracked `benchmarking/concurrency-ladder.yaml` at depth 0, c 1/2/5/10 (the spark-arena-v2 shape the one existing v2 receipt used), decode phase only; keep it distinct from `deep-smoke` (c 1/2/5) so a profile name never implies a different ladder, and name it in `benchmarking/README.md`. (`benchmarking/README.md`; `~/benchmarks/benchmark_deepseek-v4.1-flash-exl3-tp6-1m-vllm_spark-arena-v2_tp6.yaml`) *(effort: short)* — **DONE 2026-10-15:** `benchmarking/concurrency-ladder.yaml` shipped (llama-benchy, depth 0, c 1/2/5/10, 5 runs) and is named in `benchmarking/README.md` §Capacity / concurrency. The sweep's remaining half is the registry-level *Run the standard suite against every shipped arm* item in `mad-science/TODO.md`.

## Session scaffolding (archived 2026-10-14)
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

# 2026-10-15 sweep

Archived 2026-10-15 from `mad-science/TODO.md`, copied verbatim (one closing note per item where a
follow-up re-measurement completed it). Verification performed before archiving: every item's stated
deliverable was re-checked against the tree or the node — doc quotes re-read, counts re-measured, the
27B drafter's consumers re-grepped, `.34`'s HF cache re-listed. A second pass the same night archived the overnight slices — the pooling
plugin, the decision ensemble, the Mellum boot and the three storage decisions —
under the same per-lane headings.

## General Registry Maintenance
- [x] **Reconcile the stale counts in root `AGENTS.md`** — *partially closed 2026-10-15:* the `tools/` count (12 → 15, trio named) and the `benchmarking/` count (43 → 45, 44 llama-benchy + `standard-suite.yaml`) were corrected when the standard-suite trio landed, and the item's own premise no longer holds — `AGENTS.md:14` carries "31 files in 11 family dirs" and `:59` lists `recipes/explore/ (6)`. Remaining drift to re-measure before the next edit: `tests/` (19 guard modules), the `attic/` arm counts, `mods/` (4 + `mod-template`). (`mad-science/RESEARCH_LORE.md` §10 already warns of stale counts.) *(effort: short)* **Closed 2026-10-15:** the remaining drift was re-measured from the tree — recipes 32, `tests/` 20 importable modules, 539 tests passing, `mods/` 5 + `mod-template`, `attic/` arm counts (5 ds4 / 2 explore / 1 glm / 6 ifm / 3 ornith / 2 qwen3 / 29 qwen4, plus 12 archived profiles) all match root `AGENTS.md`; committed as `8fc6f2d`.
- [x] **Add `mods/README.md`** with a disposition table (mirroring `tools/README.md`'s) — four mods are mounted by no shipped recipe: `drop-caches`, `skip-labquant-vision-tower`, `fix-sglang-radix-chunked-insert`, `dsv41-vision-overlay` (their dispositions are scattered across lane docs, recoverable today only by grep). *(effort: short)*
- [x] **Sweep `benchmarking/` profiles stranded by the lane cuts** — the qwen4 `bs-*` cliff family and the qwen3 depth-cost family serve arms since archived; three name the archived `zz-rk-moebackend.yaml` (`benchmarking/README.md` §cliff family). *(effort: short)*
- [x] **Fix the ds4 README TP=2 table's model id** — it says stock `Mia-AiLab/…EXL3-2.9bpw`; the shipped recipe declares `littlecedar/…-with-engram` (`recipes/ds4/README.md` vs `recipes/ds4/deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml`). *(effort: short)*
- [x] **Write the license policy line and give the index a license marker** — a root-docs paragraph on what the registry may carry (non-commercial, gated, derivatives of third-party bases) and what "third-party-downloadable" means, plus a license flag in the `README.md` taxonomy. *(Owner decision 2026-10-15: written policy line + index marker; per-recipe banners stay.)* *(effort: short)*
## ornith
- [x] **Run the standard evaluation suite (SOP) against the shipped 35B arm** *(done 2026-10-15: one boot on `.34`, job `dadfb04b5145d956_8ed3ce77d78f`, receipts `~/benchmarks/ornith-35b-suite-20261015/`; numbers in `recipes/ornith/README.md` + `attic/ornith/AGENTS.md`; the suite's `hard` axis hit the instrument flag defect fixed in `70ed70c`, backfilled by hand on the same boot)* — the first arm of the registry-wide sweep: `tools/eval-suite.py` (contract/house/needle/hard/tools) + the `benchmarking/concurrency-ladder.yaml` perf leg on the same boot + `benchmarking/standard-suite.yaml` (the Plan C C2 clause), receipts `~/benchmarks/ornith-35b-suite-20261015/`, numbers into `recipes/ornith/README.md` + `attic/ornith/AGENTS.md` with bench ids. **Launch it by the recipe's real path, never the flattened `/<home-dir>/development/<name>.yaml` symlink**: the lane-local `mods/ornith-honed-chat-template` resolves against `dirname(recipe.source_path)` (`sparkrun/core/mods.py` rule 2), so the symlink fails at launch with "Could not resolve mod" (measured 2026-10-15 on `.35`). *(effort: medium)*
- [x] **Measure the 9B arm at C>1** — only C1 is recorded; the lane names the pool-split concurrency question itself ("untested at C>1") (`attic/ornith/AGENTS.md:674-676`). *(effort: short)* **Closed 2026-10-15:** one fresh boot on `.34`, bench `bench_92725c90d298`, receipts `~/benchmarks/ornith-9b-ladder-20261015/` (`launch.log`, `perf-ladder.yaml|json|csv`); decode d0 n=5 C1 58.0 (σ 8.8) / C2 101.1 (σ 8.3) / C5 159.0 (σ 7.8) / C10 148.9 (σ 4.8) t/s — the ~6 % c10 inversion is inside the profile's 7-25 % inter-boot noise floor with no same-window control, so the honest reading is a plateau at c5-c10, not a knee. Two receipt caveats recorded in `recipes/ornith/README.md`: a benchmark-owned launch stops its own serve on completion, so this boot's admission/mamba grants are not in the receipt (the arm's grant record stays the 2026-10-14 48/273 reading), and a re-run needs `--fresh` or it re-emits the recorded numbers. Docs landed in `recipes/ornith/README.md` + `attic/ornith/AGENTS.md` (`0e4e40e`).
## qwen3
- [x] **Boot the 27B TP=2 arm with the now-shared `@littlecedar/mods/fix-fastsafetensors-tp2-sglang`** *(done 2026-10-15: it boots and serves. `-o tensor_parallel=2` on `.34`+`.35` with the shipped fix: ladder `bench_a09eb0ce2b85` d0 pp2048 tg128 n=5 → C1 46.8 / C2 79.2 / C5 117.7 / C10 120.3 t/s (TP=1 the same night: 31.7 / 54.3 / 95.5 / 94.5), task `b418e031e70d3b0a_3510a5e0d37d`, receipt `~/benchmarks/qwen3-27b-tp2-20261015/`; the "cannot boot" claim belonged to the *unfixed* loader. Gap: the engine's admission/KV lines were not captured — the container's in-container `/tmp` log was gone by then; a next TP=2 boot should capture it first, and the clamp question at TP=2 is therefore still unread.)* (promoted from the lane-local `recipes/cybersec/mods/` copy 2026-10-15) — the lane's self-declared "Highest value" open item (TP=2 halves weight-read time); the fix mod has never been run (`attic/qwen3/AGENTS.md:166-169`; `attic/qwen3/NOTES.md` §4 WP1). *(Owner decision 2026-10-15: next-window scope, on the free `.34`/`.35`.)* *(effort: medium)* *(in flight 2026-10-15: the first TP=2 attempt died on the fix mod's anchor drift against the then-current `lmsysorg/sglang:dev-cu13` — upstream moved the buffer-release anchor, so the mod failed closed; re-anchored with a candidate-per-shape mechanism and regression-tested in `3447bcd`, guard `tests/test_fix_fastsafetensors_tp2_mod.py`. A TP=1 headline boot of the promoted chain runs on `.35` (Qwen27Suite); the TP=2 boot is queued behind it on `.34`+`.35`.)* *(measured 2026-10-15, re-anchored chain, `.35`, image `lmsysorg/sglang:dev-cu13` `c802d7b6`: the buffer release is load-bearing at TP=1 -- target load 41.90 -> 20.59 GB, draft 7.41 -> 3.78 GB, mamba cache 161/163 -> 252 with the `capped to 40` clamp gone, granted concurrency 40 -> 48 (the literal, in full), fp8 KV pool 213-222k -> 497,878 tokens, and the 262,144 needle probe now 3/3 where both leaky boots truncated at ~209k counted prompt tokens; eval-suite on the same boot: hard arc 93.5 % / gsm8k 96.0 % (n=200 each), house 19/19 + 18/18, contract ok. Deltas recorded in the mod README `mods/fix-fastsafetensors-tp2-sglang/README.md` §Measured effect.)*
- [x] **Pin the 27B arm's checkpoint and its `incoai` DFlash2 draft** — the only unpinned shipped arm in these lanes; both SHAs are already recorded (`recipes/qwen3/qwen3.8-27b-nvfp4-dflash2-sglang.yaml`; `mad-science/SESSION-RECORD.md:104`). *(effort: short)*
- [x] **[storage] Consolidate the DFlash2 drafter on one repo id** — `incoai` and `z-lab` are the same blob hash; three arms fetch it (27B DFlash2, MLX-4bit TensorFold, cybersec arm 2) and the `incoai` copy is unpinned (silent drift between consumers) (`attic/qwen3/AGENTS.md:106`). *(effort: short)* **Closed 2026-10-15:** the recipes already read `z-lab` (27B DFlash2, MLX-4bit TensorFold, cybersec arm 2); the last `incoai` references — the two `README.md` index rows and the qwen3 lane README's draft row — now point at `z-lab`, definitions deduplicated, and the same-blob note at `recipes/qwen3/README.md:46` keeps the provenance.
## qwen4
- [x] **Revive `…-labquant-highcon-…` in a k≥16 aggregate window** *(recipe revived 2026-10-15 in commit `3a5042d` — `recipes/qwen4/qwen3.8-flash-next-nvfp4-labquant-highcon-sglang.yaml`, re-pinned `6c01ac37`, vision-tower mod dropped, validates + renders `--tp 2`; the k≥16 window boot is pending, on the free `.34`/`.35`)* — dominated on one axis only; it is the sole holder of the aggregate-throughput regime (`attic/qwen4/ARMS-MANIFEST.md:118`; `attic/qwen4/AGENTS.md`). *(Owner decision 2026-10-15: next-window scope, on the free `.34`/`.35`.)* *(effort: short)* *(in flight 2026-10-15: the pinned `lmsysorg/sglang:dev-cu13-qwen38-next-local@sha256:9d2a843c…` resolves in the registry and is pulling to `.34`/`.35` — the "image absent on nodes" blocker is cleared; the k≥16 window is queued behind the 27B TP=2 boot.)* *(done 2026-10-15: one boot on `.34`+`.35`, job `1895030211ea0500_3510a5e0d37d`, receipt `~/benchmarks/qwen4-highcon-20261015/` — d8192 / 128 output tokens / n=7 per cell: aggregate decode 84.9 / 89.1 / 89.1 / 72.9 t/s at k=8 / 12 / 16 / 24 (flat 12-16, −18 % at 24), ttfr 5.8 / 7.7 / 9.8 / 15.6 s, prefill phase ~3.05-3.06 k t/s at every k; engine admitted unclamped (`max_total_num_tokens=1,567,360`, `max_running_requests=32`, mamba pool 128). The `tg` field was checked against the printed table before citing (means 84.93/89.06/89.08/72.91, n=7 each), and the prefill-phase records were excluded as a separate phase. Not measured: the standard ladder's C1-C10, and any base-arm comparison at this depth.)*
- [x] **[storage] Reclaim the re-populated RadixArk snapshot on `.34`** — 126 GiB of the archived arm's checkpoint is resident again, against the owner's cache policy (`attic/qwen4/NOTES.md:33-35`). *(effort: immediate)* **Closed 2026-10-15:** `.34` carries no RadixArk entry (verified). The RadixArk pack is load-bearing on `.35`, not litter: the shipped `qwen3.8-27b-nvfp4-dflash2-sglang` names `RadixArk/Qwen3.8-27B-NVFP4` as its model.
## explore
- [x] **[storage] Narrow humanizer's `model_file_selection`** — *premise falsified 2026-10-15: `model_file_selection` is a sparkrun config key, not a weight set, and `all` is exactly what the arm needs; `recipes/explore/README.md` corrected to the measured 87.6 GB* — `all` makes it an 82 GB arm with 62 GB of GGUFs it never loads (`recipes/explore/README.md:284-287`). *(effort: short)*
- [x] **Build the `JetBrains/Mellum2.1-12B-A2.5B-Thinking` arm (Mellum2.1 collection)** *(done 2026-10-15: built, boot-verified on `.35`, ladder C1 42.3 / C2 67.2 / C5 99.9 / C10 135.6 t/s @ d0 and house 36/37 (easy 18/19 — `needle-1`; hard 18/18), receipt `~/benchmarks/mellum-20261015/`; index row restored with the ladder filling C2/C5/C10, lane README + `attic/explore/MELLUM-21.md` carry the numbers. No serve log — capture gap noted.)* *(2026-10-15: built, **not booted** — its `README.md` index row was removed to keep the index to booted arms; the row returns with a boot receipt, and the build facts stay in the lane README + `attic/explore/MELLUM-21.md`. Its boot is queued behind the TP=2 window, not skipped.)* — owner added the collection directly, so it sits above the ranked list; nothing here has been booted. A 12B/2.5B-active MoE thinking/agentic model (64 experts, 8 active; 131k ctx, SW 1024 on 3 of 4 layers), Apache-2.0. BF16 24.3 GB fits one node with headroom, and the sibling GGUF repo carries a 7.0 GB MXFP4_MOE / 8.1 GB Q4_K_M route for llama.cpp; the card ships a vLLM recipe (`--reasoning-parser qwen3`, `--tool-call-parser hermes` for tool choice) and names an MTP head "coming soon" ([collection](https://huggingface.co/collections/JetBrains/mellum21); [card](https://huggingface.co/JetBrains/Mellum2.1-12B-A2.5B-Thinking); [GGUF card](https://huggingface.co/JetBrains/Mellum2.1-12B-A2.5B-Thinking-GGUF)). No DGX-Spark precedent; not yet in `mad-science/EXPLORE-CANDIDATES.md`. *(effort: short)* *(built 2026-10-15: `recipes/explore/mellum2.1-12b-a2.5b-bf16-thinking-vllm.yaml`, revision `92ddae9f…` resolved from the Hub, validate 0 warnings / 1 `restated-managed-path` suggestion, renders on `-n`; record in `attic/explore/MELLUM-21.md`, lane README + index row landed. The recipe carries the literal snapshot path + `--revision=<sha>` shape because MECHANICS.md's vLLM trap strips `{model}`/`--revision` and the validator then refuses the launch, and `tests/test_recipe_placeholder_resolution.py::LiteralShaConsistency` requires the three places to agree. GGUF/llama.cpp route recorded but not shipped: sparkrun's `llama-cpp` runtime is used by zero recipes here, so it would invent the registry's first such contract with nothing to diff against. **Boot pending — needs a node**; vLLM 0.29 registers `MellumForCausalLM` (`vllm/.../mellum.py`, a `Qwen3Moe` subclass reading `config.layer_types` + `rope_parameters`), which is the evidence a boot would confirm.)*
## Storage consolidation (registry-level)
- [x] **[storage] Census and reconcile the unrecorded attic weight packs** — attic/ds4 Pollard EXL3 3.5bpw (552B), attic/ifm 36B-A4B ("48 GB synced to every node"), attic/explore Nemotron-30B NVFP4 + its DSpark draft: the 2026-10-14 reclaim record names none of them (`attic/ds4/README.md:25-30`; `attic/ifm/ARMS-MANIFEST.md:52`; `attic/explore/ARMS-MANIFEST.md:40-41`; `mad-science/SESSION-RECORD.md:171-173`). *(Owner decision 2026-10-15: census first, then reclaim archived-lane weights — keep shipped-arm weights and anything a doc cites; covers the explore weights in the item below.)* *(effort: short)*
- [x] **[storage] Verify the un-recorded explore weights that are plausibly still cached** — Nemotron NVFP4 + draft, Qwen-Image 32.5 GB, LTX-25 36.9 GB on `.35`, Ling 154 GB, Kolibri 74 GB: no doc states their cache state (`attic/explore/QWEN-IMAGE.md`; `attic/explore/LTX-25.md`; `README.md` Explore table). *(effort: short)*
- [x] **[storage] Evaluate the Qwen3.8-27B "same model, three packs" consolidation** *(Closed 2026-10-15: answered in `STORAGE-POLICY.md` §4 — three different quantisations, so the sidecar is the whole pack; all three Apache-2.0 (AEON ships no LICENSE file; its clause is Q3); recommendation: keep all three full exports. The `incoai` cache copy (≈10.7 GiB) is reclaimable.)* *(Premise corrected and answered 2026-10-15: the three packs are three different quantisations (ModelOpt mixed NVFP4+FP8 / llm-compressor uniform NVFP4 / compressed-tensors NVFP4+FP8), so a tensor-level delta over the RadixArk base is the whole pack — **not graftable**; the only small sidecar in this family is the already-built KB-scale chat-template overlay. All three are Apache-2.0 (AEON ships no LICENSE file; owner Q3 covers its arbitration clause). Recommendation: keep all three full exports, 0 GB saved; a ~45 GB/node consolidation would need a same-quantiser delta export plus a boot receipt — a work item, not a storage decision. Separately reclaimable: the retired `incoai/Qwen3.8-27B-DFlash2` HF copy, 3.58 GiB/node on `.30`/`.32`/`.35` ≈ 10.7 GiB, no live consumer — `hf cache rm model/incoai/Qwen3.8-27B-DFlash2`.)* — RadixArk / AEON-ULTIMATE-UNCENSORED / orcarouter-Uncensored are 21–25 GB each; the latter two are the natural sidecar candidates *(Owner decision 2026-10-15: case-by-case on license — graft only where the base's license clearly permits redistribution; keep the full export otherwise.)* (`README.md` Qwen 3x + Cybersec tables). *(effort: medium)*
- [x] **[storage] Define a per-node cache budget and its enforcement** *(Closed 2026-10-15: budget + enforcement in `STORAGE-POLICY.md` §3 and `tools/cache-audit.py` (+22 tests), which emits a per-tree cutoff it can actually match. `.32`/`.33` breach today; the residual call — which arm stays resident on `.34` — is Q4.)* *(Position written 2026-10-15 in `mad-science/STORAGE-POLICY.md` §3: runtime cache <= 0.5 TB/node, HF cache <= 2.2 TB/node, `df /home` free >= 1.0 TB always — derived from the 510.3 GB ds4 checkpoint plus a 295.9 GB lobe download. Enforcement built: `tools/cache-audit.py` (+21 tests, exits 1 on an over-budget node — `.32`/`.33` breach today at 734.8/732.1 GB), the product's own age sweep, and active-arm-only residency as written procedure. Owner Q4 decides `.34`'s resident arm.)* — decision-lane four arms ~44 GB/node with one servable; embed/rerank variants +16 GB/node; no mechanism keeps only the active arm resident *(Owner decision 2026-10-15: active-arm-only residency — reclaim a lane's weights when its arm is switched; the archived-pack census sets the reclaim list.)* (`attic/decision/DECISION-MODELS-RESEARCH.md`; `recipes/embed/README.md:98-124`). *(effort: long)*
- [x] **[storage] Decide the fleet runtime-cache position** *(Closed 2026-10-15: the position and the vehicle are written in `mad-science/STORAGE-POLICY.md` §1–§2 — sparkrun's own sweep, with `--older-than` *in days* (`--older-than 3` reaches the §2 set; the 30-day default never would) and the leaf key, not `modlogs/`, as the live/stale splitter. The reclaim itself is owner-timed: Q2.)* *(Resolved 2026-10-15: the prune path is sparkrun's own — `sparkrun setup prune-runtime-cache [--dry-run|--older-than N|--all]` plus the per-launch sweep — demonstrated, not read (`--all --dry-run`: "Would remove 98 tree(s), 2550.4 GB", which ignores the marker). The leaf key `sanitize(model)[:48]-sha256("<model>@<revision>")[:8]`, not `modlogs/`, splits live from stale — the two DS4 lobes share a mod set. Position + reclaim handoff: `mad-science/STORAGE-POLICY.md` §1–§2 — 616.8 GB reclaimable today (one unmarked tree on `.34` included), 996.4 GB from 2026-10-16 11:13; execution deferred to the owner/next session, owner Q2.)* — `~/.cache/sparkrun/runtime-cache` holds ~3.1 TB of prepared model trees across the six nodes (`.30` 294 GB, `.31` 248 GB, `.32` 787 GB, `.33` 787 GB, `.34` 546 GB, `.35` 450 GB). It is a sparkrun-managed cache rebuilt on the next boot, and the directory suffix is derived by sparkrun core, so the three same-model `deepseek-ai/DeepSeek-V4.1-Flash-*` trees on the head (95 GB + 48 GB) and the `Mia-AiLab/…EXL3-2.9bpw` tree (100 GB) cannot be split live-vs-stale from the docs alone (`9a74d993` is cited; the Mia-AiLab trees back cybersec arm 5). Either find sparkrun's prune path or accept a cold-boot rebuild, then reclaim. *(effort: medium)*
## embed
- [x] **Add a pooling `BenchmarkingPlugin`** *(done 2026-10-15: `plugins/pooling_bench_framework.py` + `tests/test_pooling_bench_framework.py` (21 tests, mutation-checked), shipped via the documented `plugins.paths` opt-in because no registry field can point at a plugin (`sparkrun/core/registry.py:168-178`). Premise corrected by measurement: a standard profile against a pooling endpoint fails loudly (`Benchmark incomplete`, exit 1), not silently; the silent shape is an all-null metrics file, which `measured_nothing` rejects. Owner Q5.)* — pooling engines have no `/chat/completions`, so the standard profiles "silent skip"; the lanes' numbers rest on hand-run scratch scripts ("a plugin, not a script, is the correct long-term home") (`tools/README.md:102-105`). *(effort: medium)*

## decision
- [x] **Productize the clef+Kai ensemble (+1.3 pt, McNemar p=0.012)** *(done 2026-10-15: `tools/decision-ensemble.py` serves the rule as one `/v1/systemone` model (one advertised id — the two-id version sent tool-eval-bench into an interactive loop and a 3.7 GB log) and `tools/decision-ladder.py` gives the lane its concurrent `req/s` ladder; offline 71.6 % (1432/2000, +63/−37, p=0.012) reproduced on fresh boots and served end-to-end 71.7 % (1433/2000, the +1 an exact tie); clef 4.89/5.11/5.16/5.51 and Kai 0.187/0.186/0.156/0.128 req/s — both arms serial. No profile by mechanism (`tool-eval-bench modes do not provide scheduled JSON artifacts`) and no ensemble recipe (one model per launch). Receipts `~/benchmarks/decision-ensemble-20261015/`; commit `b6bf449`.)* — a statistically real gain that exists only as a one-off analysis: no ensemble recipe/server and no benchmarking profile to reproduce it (`recipes/decision/README.md:199-241`). *(effort: medium)*

## rerank
- [X] **8B reranker residency — DECIDED 2026-10-15: keep shipped, no pre-cache** — `qwen3-vl-reranker-8b-vllm-b12x` stays a shipped recipe (primary index + lane README) as the deliberate non-`fast` quality tier (~4× slower per scored document than the 2B) and is **not** pre-cached: the +16 GB/node is a cold-fetch cost, not a residency. Residual work: write that position into `recipes/rerank/README.md` and `attic/rerank/AGENTS.md` §8B so the question cannot reopen. *(Owner decision 2026-10-15: keep shipped, do not cache.)* (`recipes/rerank/README.md` §Shipped recipes; `attic/rerank/AGENTS.md` §8B reranker (quality tier)) *(effort: short)* **Closed 2026-10-15:** the position is now recorded in `recipes/rerank/README.md` (the 8B recipe's residency bullet) and `attic/rerank/AGENTS.md` §8B, so nothing is left open.


# 2026-10-16 sweep

## Model Flags
- [x] **Rewrite `🚀 fast` as per-node-count bands (was DECISIONS Q1)** — the taxonomy (`README.md` §Model Flags) defined `🚀 fast` as *C1 Fast (>= 50 t/s avg)*, but `…-labquant-sglang` carries `fast` at an index C1 of 40.3 (the revived highcon arm inherits the same tag) and both are TP=2, where a 180B MoE at 40 t/s is a judgement call, not a measurement. *(Answered 2026-10-16: bands — `🚀` at >= 50 t/s on one node and >= 40 t/s on two, higher TP an explicit owner call; `🐢` stays < 40 t/s at any node count. Landed in `README.md` (both rows + the footnote), so both TP=2 arms keep the tag on a stated rule.)*

## Benchmarking
- [x] **Ship the pooling ladder profile pair (was DECISIONS Q5)** — `plugins/pooling_bench_framework.py` makes a pooling sweep runnable as `sparkrun benchmark pooling <recipe> --profile <file>`, but the profile shape differs per arm (`kind`, `dimension_check` 2048 for the 2B vs 4096 for the 8B AWQ, `docs_per_query`), so the contract was documented in `tools/README.md` and no profile shipped. *(Answered 2026-10-16: ship it — `benchmarking/pooling-ladder-embed.yaml` and `-rerank.yaml`, both `framework: pooling-bench` at c 1/2/5/10, 100 requests, ~256-token inputs, 5 warmups, salted; `dimension_check: 4096` for the 8B AWQ with `-b dimension_check=2048` documented for the 2B. Verified by loading both through sparkrun's own `BenchmarkSpec.load` (no `metadata` leak into `args`) and rendering their flags; index rows in `benchmarking/README.md`, command form in `tools/README.md`.)*

## cybersec
- [x] **[storage] Test whether the uncensored deltas are graftable as sidecars over the cached bases instead of shipping ~184 GB / 25 GB full exports (dropped)** — `recipes/cybersec/README.md:176-179`. *(Answered 2026-10-16: dropped — keep the full exports. `STORAGE-POLICY.md` §4 already answered the storage side (packs from different quantisers cannot be deltas of each other, so the sidecar would be the whole pack), and this item's real ask was an uploader-side same-quantiser delta export, which the owner declined to pursue. Recorded in `STORAGE-POLICY.md` §4.)*

## Image pins (registry-level)
- [X] **Pin the six recipes that ride `:latest`, and the three cybersec sglang arms that ride `dev-cu13`** *(done 2026-10-16; nine recipes, three boots, one shared digest per tag).* Original item: *(from the 2026-10-15 advisory pass; the qwen3 27B arm was already done — `@sha256:0a1ba33a…`, commit `16896e1`.)* Unpinned: `…-b12x:latest` in the four embed/rerank b12x arms and `recipes/qwen4/qwen3.8-flash-next-nvfp4-solo-vllm-b12x.yaml`; `dgx-vllm-eugr-nightly:latest` in `recipes/qwen3/qwen3-coder-next-int4-autoround-vllm.yaml`; `lmsysorg/sglang:dev-cu13` in the three cybersec sglang arms. **Pinned, each to the digest its boot resolved:**
  - `ghcr.io/spark-arena/dgx-vllm-eugr-nightly-b12x@sha256:cf5a2a53…` (single-platform manifest; its config digest `e90182b5…` is exactly the running container's `.Image`) → the five b12x recipes. Boot: the 2B embed arm on `.34`, which also ran the shipped `benchmarking/pooling-ladder-embed.yaml` (c1 38.2 / c2 45.5 / c5 85.2 / c10 102.4 units/s, 100/100 ok per cell; receipt `~/benchmarks/pins-20261016/embed2b-ladder.{yaml,json}`).
  - `ghcr.io/spark-arena/dgx-vllm-eugr-nightly@sha256:cc47adc1…` (manifest; config `9a876c39…`) → `qwen3-coder-next-int4-autoround-vllm`. **The tag had moved since 2026-10-15** — the advisory pass read `@sha256:7717585a…`; today's boot resolved `cc47adc1…`.
  - `lmsysorg/sglang:dev-cu13@sha256:0b3e3970…` (OCI index; arm64 manifest `35206090…`, config `b43b2772…`, engine `0.0.0.dev1+gc15edf314`) → the three cybersec sglang arms. **The tag had moved again**: `.34`/`.35` held `@sha256:0a1ba33a…`, so an arm booted today silently runs a different engine than the 2026-10-13/14 receipts describe — the drift this pin freezes. The same boot produced the nex-arm re-measure in `attic/cybersec/AGENTS.md` (assert gone, generation still degenerates: the checkpoint, not the engine).
  - Method worth keeping: relay-imported images carry **no** `RepoDigests`, so `docker images --digests` prints `<none>`. Use `docker buildx imagetools inspect <ref>` for the top-level digest, match its **config digest** to the container's `docker inspect .Image`, then confirm the pinned ref resolves via `docker manifest inspect <ref>@<digest>`. Evidence: `head:~/benchmarks/pins-20261016/` (`embed2b-evidence.txt`, `nex-sglang-evidence.txt`, `qwen3coder-evidence.txt`).
  - Verified after the change: **no `container:` line under `recipes/` is tag-only any more** (repo-wide regex check, 2026-10-16).
- [x] **Move the six vLLM v0.29.0 explore arms to 0.30.0.** *(closed 2026-10-16 — two arms moved, three held after a device-free config preflight, one rides its own boot.)* Original item: *(2026-10-15 advisory pass; bump is not verified by any boot yet.)* `vllm/vllm-openai:v0.29.0@sha256:c2914767…` ships in `recipes/explore/humanizer-12b-vllm.yaml`, `…/kolibri-1-78b-fp8-vllm.yaml`, `…/mellum2.1-12b-a2.5b-bf16-thinking-vllm.yaml`, `…/poolside-laguna-s-2.1-nvfp4-dflash-vllm.yaml`, `…/poolside-laguna-xs-2.1-nvfp4-dflash-vllm.yaml` and `…/qwen-image-2.1-turbo-7b-bf16-diffusers-script.yaml`. OSV reports **23 advisory records / 16 distinct CVEs** for 0.29.0 (no HIGH/CRITICAL) against **0 for 0.30.0**; action: bump to `v0.30.0@<digest>`, boot one arm, and give `recipes/decision/jev-9b-decision-vllm.yaml` (`vllm-openai:glm53-flash@sha256:819ec9c0…`, a custom tag whose base version is unrecorded) the same look. **Outcome:** the pin resolved to the Docker Hub top-level manifest-list digest `sha256:8a69ffad…` and `7e6bf2b` moved five of the six, holding Kolibri in the same commit (its vendor plugin pins vLLM 0.29); a device-free **config-load preflight** (the new image's own `get_config()` per pin, HF repo dir mounted) then showed three cannot load on 0.30.0 (vLLM-side in each case) — **mellum2.1-12b** (vLLM 0.30.0 registers its own `MellumConfig`, a `Qwen3MoeConfig` subclass, ahead of transformers' upstream class; the stub flattens the checkpoint's nested per-layer `rope_parameters` → `AttributeError: 'float' object has no attribute 'get'` at config load, before any weight load; unblock probed: an `hf_overrides_kw={'rope_parameters': …}` override loads clean) and the **laguna-{s,xs}-2.1** pair (vLLM 0.30.0's own `LagunaConfig` stub shadows the transformers class — `'str' object has no attribute 'get'` out of `get_config`; a 2026-10-17 probe shows plain transformers 5.17 builds those pins, so the unblock is a vLLM-side fix or a stub-compatible re-pin, a lane decision) — so `27e4563` put those three back on 0.29.0 with the mechanism in-recipe. **humanizer-12b** is boot-verified on 0.30.0 (task `sparkrun_17678da2f7107eb2_a4bf874feb5a` on `.35`; engine `vllm 0.30.0`, container `.Image` == the manifest list's arm64 config digest `91d9b077…`, `/v1/models` → `jialinyyzz/humanizer`, a `/v1/completions` rewrite smoke clean, KV 371,031 tokens / 45.29×; receipt `~/benchmarks/bump-20261016/`); **qwen-image** keeps the bump (its mod stages its own `transformers>=5.17` venv on the image's torch — its media-gen boot is the check); **kolibri** holds as before (plugin pins 0.29). **jev-9b look:** `vllm/vllm-openai:glm53-flash@sha256:819ec9c0…` = vLLM **0.28.1rc1.dev580+g385dce36b** (already recorded in `attic/glm/`), **24 OSV records** — the delta against 0.29.0 being **CVE-2026-93840 / PYSEC-2026-3998** (cross-request logits corruption via `allowed_token_ids`, fixed in 0.29.0); the Hub tag still resolves to the pinned manifest-list digest (checked 2026-10-16), so moving the arm needs a new build from the tag's author and stays as-found. Lane detail: `attic/explore/AGENTS.md` §Engine bump — vLLM 0.30.0 (2026-10-16).

# 2026-10-17 sweep

The 2026-10-17 session's completed items, copied verbatim from `mad-science/TODO.md` (nested
`*(Owner decision …)*` notes included). Two ds4 items closed: the TP=2 vision ship (the template
gate was located and fixed in a lane mod, then a boot receipt taken) and the EXL3/Engram duplication
collapse (the abliterated arm moved onto the combined pack, and the graft was stopped from copying
the tables). The 1017 refresh item stays open on the owner's adoption decision.

## ds4
- [ ] **Ship TP=2 vision** *(2026-10-15: the Engram side of the vision boot is settled — the combined repo carries the tables at `<snapshot>/engram/` on both `.34` and `.35` (2 x 94.4 GiB each), which is the layout the launcher's resolver prefers (`launcher.py:101-104`), so the arm boots with engram, not the degraded configuration. The launcher mod's legacy-dir-only check that logged `Engram: none … (degraded)` on a fully staged node was fixed to report the real home (commit `7f80802`). Vision itself is fail-closed in the launcher, so only engram could have degraded silently. **Boot receipt taken 2026-10-15** (task `8ef9b6c9a550c389_3510a5e0d37d`, receipt `~/benchmarks/ds4-vision-20261015/`): the arm boots and serves text at TP=2 in ~80 s with the Engram tables loaded; the engine runs the vision path (`vision ON … 43 gates`, tower 0.90 GiB, real-image warm-up 431 ms) — but an `image_url` part on `/v1/chat/completions` is still refused with **HTTP 400 from the chat template** ("Message content contains image…"), while the text control passes. So the remaining gate is the served template / request contract, not the launcher or the bias; the 2026-10-06 trial that proved the mechanism answered image requests, so the delta is the serving contract.)* *(code shipped 2026-10-15 in commit `70ed70c`: opt-in `--vision` + `vl_bias.safetensors` inside `mods/tensorfold-dsv41-launcher`, recipe passes it; the deliberate boot receipt is still pending — the "shipped = bootable and usable" rule)* — proven on our hardware ("supported and now proven … but not shipped"): a two-part change (`--vision` + the 43-tensor `vl_bias.safetensors` folder); the recipe still refuses `image_url` with HTTP 400 (`attic/ds4/AGENTS.md`). *(Owner decision 2026-10-15: next-window scope, on the free `.34`/`.35`.)* *(effort: short)*
  *(Owner decision 2026-10-16: close the gate by patching the served chat template from a lane mod — the engine's vision path already runs — then take the deliberate boot receipt; the `vision` tag and the index 👀 return with that receipt.)*
  *(closed 2026-10-17 — the gate was the served template and it is fixed: `mods/tensorfold-dsv41-launcher/chat_template.jinja` (the two placeholder guards neutered, the token assembled from pieces so no shipped file carries it) served through a `--vision`-gated overlay model dir. Receipt: task `8ef9b6c9a550c389_948390812ad5` on `.34`+`.35`, 3/3 solid-colour probes PASS with a clean text control and HTTP 200 where it used to be 400; `~/benchmarks/ds4-vision-20261017/`, record `attic/ds4/AGENTS.md` §12.14.1.)*
- [ ] **[storage] Collapse the DS4.1 EXL3 duplication** — *(Owner decision 2026-10-15: combined repo everywhere — cybersec arm 5 grafts onto the combined `littlecedar/…-EXL3-2.9bpw-with-engram` pack and drops `dsv41-engram-fetch`; the changed arm needs a re-boot receipt.)*; per node serving both lanes the same ~197 GB weights + ~189 GiB Engram tables exist twice (`recipes/ds4/deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml`, `recipes/cybersec/README.md`, `recipes/cybersec/mods/graft-dsv41-ablit-wo-b/README.md:17-19`). *(effort: medium)*
  *(closed 2026-10-17 — arm 5 grafts from the combined pack and no longer mounts `dsv41-engram-fetch`; the graft itself stopped copying the tables (the author's script `shutil.copytree`s the `engram/` directory — ~189 GiB dereferenced — and `os.link`s the shards it does not edit, which over the snapshot's own relative `blobs/…` links yields links that cannot resolve; the first attempt produced a 386 GiB tree), so the mod hands it a `--src` view without `engram/` and symlinks `${STOCK}/engram` into the graft tree: graft **148 s / 137 s** per node and a **119 GiB** tree (the rewritten shards only). Re-boot receipt task `2f9a8f3e60a51ee4_948390812ad5`, `~/benchmarks/cybersec-arm5-20261017/`; the stale Mia trees and `dsv41-engram` pre-warms were removed from `.32`/`.33`.)*

# 2026-10-18 sweep

The 2026-10-18 session's completed ds4 items, archived with the closure evidence as it shipped —
digests, receipts and mechanism sentences kept verbatim. The original item prose of the two big items
is not re-transcribed: the pre-fold register is `git show f6eb2d3:mad-science/TODO.md`, which also
carries the `#36`–`#42` decisions answered the same day.

## ds4 — closed 2026-10-18
- **(a) Bring the TP=4 knapcio arm up to upstream v2.4 — shipped.** The original item prose is in
  `git show f6eb2d3:mad-science/TODO.md`. The four experiments this boot closed —
  `DSV41_CACHE_GIB=0`, `SGLANG_RUST_BUILD_MODE=auto`, the RoCE coverage sweep with its E5 crossover
  microbench, and the `DSV41_CERT_HEAD` / `DSV41_ENGRAM_DRM_NODE` re-test — are the (c)/(d)/(e)
  entries below; their numbers are in this closure paragraph.
  *(**Closed 2026-10-18 — v2.4 is the shipped image.** Built from `27616bec` with the vendored
  `boot.py.health-port.patch` (apply-check clean), base pinned by digest, in-image gate PASS, pushed as
  `littlecedar/dgx-spark-dsv41:canary-roce@sha256:acfc331a…` (image id `1db2155f…`); the recipe
  re-pins it and `Dockerfile.knapcio-dsv41` is re-vendored byte-identical to upstream. TP=4 boot receipt
  task `f0f09c470f181a68_7afff0589a33`: `/v1/models` and chat OK,
  `ROCE_TP8_READY {world_size: 4, max_size: 2097152}`, ladder C1 59.21 / C4 110.85 / C8 111.38 /
  C16 112.80, 119k prefill 27.93 s, 231k 66.02 s, pool 9,386,240
  (`~/benchmarks/ds4-knapcio-v24-20261017/`; `NOTES.md` carries the per-arm launcher sha and argv/env).
  Experiments closed with it, one boot each against that baseline: `DSV41_CACHE_GIB=0` gives pool
  9,381,376 (−0.05 %), so the claimed +9 % third-party PV does not reproduce; `SGLANG_RUST_BUILD_MODE=auto`
  does not hang (532 s) because the Rust image processor is unavailable in the image (the log's
  `failed to query the Rust toolchain`), so `never` is harmless but unnecessary; RoCE 4/8 MiB is a null
  (`bytes_posted_per_hca` 3,356,777,472 and `ops_posted` 7475 identical at 2/4/8 MiB, prefill inside the
  ±10 % cross-boot spread, and 8 MiB costs 0.96 % of the KV pool), so the 2 MiB cap is not too high —
  the E5 crossover measured 8→16 KiB with RoCEnante 3.1–5.4× over default-NCCL from 512 KiB to 2 MiB;
  `DSV41_CERT_HEAD` certifies and its ladder sits inside drift at −4.5 % KV pool, so it stays off;
  `DSV41_ENGRAM_DRM_NODE` is a null with **no host change**, because the container is unprivileged and
  gets no `/dev/dri`, so the node is invisible inside it. Hygiene: stops by task id, `docker ps -aq` 0
  on `.30`–`.33`, bench containers and `/tmp/roce-out-*` removed.)*
- **(b) Assess the DeepSeek-V4.1-Flash-1017 refresh and its same-day quants — shipped.** Served, measured (the interleaved re-take), then adopted: the base is the 1017 EXL3 pack pinned `c178a012…` with its Engram pre-warmed, and `littlecedar/…-with-engram` stays as the cybersec arm's stock.
  - **Trial receipt 2026-10-17** (`.34`+`.35`, task `5959b937d06087c6_948390812ad5`, receipt `~/benchmarks/ds4-1017-20261017/`): **(a) served** — the pack boots on the shipped TensorFold launcher via an untracked trial recipe (`-o model=` is ignored by a real launch; the dry run honours it), with the 1017 Engram built from shards 47/48 into `<snapshot>/engram` (188.8 GiB, 2978 s), `/v1/models` = the 1017 repo id at 530 s cold, and vision **3/3** — the pack ships no chat template at all, so the launcher's `--vision` overlay is what makes it boot. **(b) measured** — same-window A/B against the shipped arm, same profile and suite: ladder **C1 61.5 vs 68.0 / C4 48.9 vs 48.0 / C8 49.3 vs 43.3 / C16 48.2 vs 43.4** t/s — means of 3 runs whose **runs overlap on every cell** (shipped spreads 1.56–5.85 t/s against the 1017 arm's 0.07–0.57), so the ladder establishes that arm's *consistency*, not a speed win; the C8/C16 deltas it first suggested are not established — TEB **100 vs 100** (15/15). **(c) decision pending (owner)**: adoption costs ~385 GB per node re-download plus a 330 s rank-cache write per node, so the call should rest on the card's published gains against that cost, not on this ladder (one boot per arm; ladder order and boot warmth are unremoved confounds, and the C1 cell wants an interleaved re-take). Full record: `attic/ds4/AGENTS.md` §12.16.
  - **Pack sha correction (2026-10-17, ship pass):** the EXL3 pack resolves to
    `c178a01284fc5c0e859d8668cffaac81ca8f4042` — the Hub's `sha`, and both `.34`/`.35` hold
    `snapshots/c178a012…` — so the `afc7aa0a…` in the quant bullet above was a superseded read. The
    shipped recipe pins `c178a012…`.
  *(**Closed 2026-10-18 — shipped.** (a) served and (b) measured: the interleaved re-take
  (`~/benchmarks/ds4-1017-ab-interleaved-20261018/`, 3 alternating boots per arm, 5 runs/cell) makes
  the two arms indistinguishable on every ladder cell — c1 66.37 vs 66.43, c4 47.83 vs 48.82, c8
  44.80 vs 42.44, c16 48.39 vs 48.78 t/s, all ranges overlapping — so the earlier +13.9 %/+11.1 %
  C8/C16 and −9.6 % C1 were boot-slot artifacts and adoption rests on the card's published gains,
  per the owner's 2026-10-17 directive. (c) decided: the base is the 1017 pack pinned `c178a012…`
  with its Engram pre-warmed into `hub/dsv41-engram` (`--require-engram` fails a miss);
  `littlecedar/…-with-engram` stays as the cybersec arm's stock. Receipts: ship
  `~/benchmarks/ds4-1017-ship-20261017/` (TTR 62 s, vision 3/3, tag-verified rank cache). One
  sub-item stays open and blocks nothing on the fleet: the publication route for third-party parity
  (combined repo ≈385 GiB vs an Engram-only repo ≈189 GiB plus a launcher change) is the owner's call.)*
  *(Owner decision 2026-10-18 — the last open sub-item, the publication route for third-party parity: publish the Engram-only repo (~189 GiB) plus the launcher change; do not ship a combined ~385 GiB repo.)*
  - **TP=4 half (2026-10-18):** the knapcio arm now serves the same refresh,
    `deepseek-ai/DeepSeek-V4.1-Flash-1017@1bae0e10…`. It needed a template source — 1017 ships none
    and this SGLang reads `<model_dir>/chat_template.jinja` — so the mod serves a symlink farm
    (`ensure_template_overlay`; exit 2 when it cannot stage one) and the image re-packs Engram per
    rank on the first boot (2 × 23.6 GiB/rank, 57-73 s). Boot `a2e141223b52793c_7afff0589a33`: warm
    relaunch 545.9 s, `/v1/models` = the 1017 id, vision 3/3 + text control, pool 9,273,856. Ladder
    C1 81.0 / C4 118.9 / C8 107.5 / C16 115.9 — parity on C4/C8/C16 inside spread, and the +36.7 %
    C1 is one boot against one boot, **not established** (`attic/ds4/AGENTS.md` §12.17;
    `~/benchmarks/ds4-knapcio-1017-20261018/`).
  - **Prompt format, known limitation (2026-10-18):** both arms serve 1017 on the lane's patched
    **V4.1** template — 1017 ships none and its `encoding/encoding.py` grew (37,316 → 37,962 B),
    while `test_encoding.py` grew 19,371 → 22,449 B — so the served format is a port of the older
    encoder. Empirically adequate: vision 3/3 on both arms and TEB 15/15 on the TP=2 arm's 1017
    ladder. A port of 1017's `encoding.py` was never measured and no shipped path requires it.
- [ ] **Run the two KNAPCIO post-pin defer experiments as tracked A/Bs** — `DSV41_CACHE_GIB=0` (third-party +9% KV pool; shipped value is 4 GiB) and the `SGLANG_RUST_BUILD_MODE` cargo-probe boot-hang workaround (`mad-science/KNAPCIO-UPSTREAM-DELTA.md:49,56`; `recipes/ds4/mods/dsv41-sglang-overlay/launcher.py:116,162`). *(effort: short)*
  *(c) — closed 2026-10-18 by the v2.4 boot in (a); the results are in its closure paragraph.*
- [ ] **RoCEnante coverage sweep + auto-crossover microbench** — the memo's §5 E3/E5 ("actually worth running"): do TP all-reduces/gathers >2 MiB silently fall back to NCCL (`SGLANG_ROCE_MAX_SIZE` 4/8 MiB vs shipped 2 MiB), and the 1 KB…2 MiB RoCEnante-vs-NCCL crossover curve (none measured) (`mad-science/CUSTOM_ALL_REDUCE_SM120_EXPERIMENTS.md:166-196`). *(effort: medium)*
  *(d) — closed 2026-10-18 by the v2.4 boot in (a); the results are in its closure paragraph.*
- [ ] **Re-test `DSV41_CERT_HEAD` / `DSV41_ENGRAM_DRM_NODE`** — both named and deliberately off (CERT_HEAD −0.5 ms/step at c1 but slower from ~10 requests; ENGRAM_DRM_NODE needs a host display-reserve change) (`attic/ds4/AGENTS.md`). *(effort: medium)*
  *(Owner decision 2026-10-16: the host display-reserve change on the free nodes is authorized for this re-test — revert or document it afterwards.)*
  *(Correction 2026-10-18: both are **knapcio/SGLang adapter** knobs (`/opt/dsv41/adapter/…`), listed with the RoCE set at `attic/ds4/AGENTS.md:1793-1797` — the TensorFold TP=2 image reads only `TF_DS_*`, so a boot on `.34`/`.35` measures nothing. The re-test belongs to the TP=4 lane and now rides the v2.4 boot; the host display-reserve change is **not** applied without evidence the knob acts without it, because the reboot alone moves the first KV pool 5.9–6.4M → 7.48M tokens and would confound its own comparison.)*
  *(e) — closed 2026-10-18 by the v2.4 boot in (a); the results are in its closure paragraph.*
- [X] **Pin the TP=2 arm's checkpoint revision** — **closed 2026-10-18.** The arm now serves `LibertAIDAI/DeepSeek-V4.1-Flash-1017-EXL3-2.9bpw` pinned at `c178a01284fc5c0e859d8668cffaac81ca8f4042` via top-level `model_revision:`, and the `littlecedar/…-with-engram` question is moot (it stays only as the cybersec arm's stock). `--strict` now flags this recipe as the lane's known launcher false positive — the engine receives the prepared snapshot path, not `--revision`.
- [ ] **DSpark verify-window γ=3** — only γ=2 vs γ=5 was A/B'd; the fork's own baseline point (γ=3) was never measured on this lane (`recipes/ds4/mods/dsv41-sglang-overlay/launcher.py:140-158`). *(effort: short)*
  *(Owner decision 2026-10-18 [#42]: deferred while `.30`–`.33` carried the peer TP=4 job; that deferral was lifted mid-session when the owner released the nodes, so this is in scope on `.30`–`.33`.)*
  *(**Closed 2026-10-18 — proven negative: γ=3 cannot boot on this arm, and only the checkpoint's block size 5 is coherent.** Interleaved C1 pair on `.30`–`.33`, each arm its own boot and its own `--fresh` output, `-o dspark_block_size=5` (shipped) vs `=3`. The γ=5 arm serves — C1 **64.16 ± 7.97 t/s** (n=5, 56.4–76.4), TTFT 587 ms — and the knob proves it landed end to end (`… CONTEXT=1048576 DSPARK_BLOCK_SIZE=5` on all four ranks; engine `'speculative_dspark_block_size': 5`). The γ=3 arm never opens the port: weight loads and ROCE init both succeed, then all four ranks die identically at decode CUDA-graph capture (~8 min in, 15:58:15 UTC) — the engine's own `DSpark gamma mismatch: using gamma=3 (from speculative_num_draft_tokens=4) but draft config block_size=5`, then `decode_cuda_graph_runner.py:1044 capture` → `verify_cap.py:308 compute_confidence_tensor` → `dspark_planner.py:267`, `RuntimeError: Sizes of tensors must match except in dimension 2. Expected size 5 but got size 4`. Mechanism: `DSPARK_BLOCK_SIZE` sets only the *requested* window (the engine derives `speculative_num_draft_tokens = gamma + 1 = 4`), while the DSpark draft head's `block_size = 5` comes from the checkpoint, so the shipped `DSV41_VERIFY_CAP=conf:0.1` adapter builds a size-5 confidence tensor against the runner's 4 verify tokens and the capture aborts. No γ=3 C1 exists, so there is no delta to compare; the reference spread is the pooled C1 **67.18 ± 6.97 t/s** (n=25, CV 10.4 %). **The knob is now reachable:** `-o env.DSPARK_BLOCK_SIZE` was silently clobbered by the launcher's `RECIPE_ENV`, so `--dspark-block-size` was added to `launcher.py` (applied after `apply_recipe_env`, like `--context-length`), `defaults.dspark_block_size: 5` + `--dspark-block-size {dspark_block_size}` to the recipe, and the effective value is printed in the boot line. Receipts `~/benchmarks/tp4-20261018/`: `REPORT.md` §3, `serve-p1-g5.log`, `gamma-p1-g5.{yaml,json}`, `bench-p1-g5.log`, `serve-p1-g3.log` (the failing boot, all four ranks), `gamma_pairs.py`.)*

## glm5 — closed 2026-10-18
- [ ] **Promote the GLM-5.3-Flash EXL3 4bpw TP=4 line to a recipe** — boot-verified 98.4 t/s @ d0 (2.7× the 3.0bpw route) with a pre-built engine image (`tensorfold-glm53:v0.6.0`); blocked only on the three-file deliverable (baked image + a `tensorfold-glm-exl3-launcher` mod + the `runtime: sglang` shim) (`recipes/glm/README.md` §runbook bullets 3–5; `attic/glm/GLM-5.3-RECOMMENDATIONS.md`). *(effort: medium)*
  *(**Closed 2026-10-18 — the three-file deliverable exists and now carries its first boot receipt.** `recipes/glm/glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang.yaml` + `recipes/glm/mods/tensorfold-glm-exl3-launcher` serve on `ghcr.io/miaai-lab/glm-5.3-flash-exl3-2x-dgx-sparks-tensorfold@sha256:eb17e092…` (task `b55c050475ff4b3a_7afff0589a33`): **TTR port-open 309.637 s** / HTTP-ready 309.653 s from container start, launch total 1,720.3 s including the 175.7 GB checkpoint + 2.3 GB drafter distribution; context **1,048,576** (`engine context: 1048576; loaded in 297.8s`); KV pool **5,834,752 tokens** ("up to 8 requests decode together"); rank-0 startup estimate 52.03 GiB within 90.04 GiB, workers ready in 291.5–291.6 s; `/v1/models` id `GLM-5.3-Flash-EXL3`, `owned_by: tensorfold`. Ladder on the same live serve: C1 **83.03 ± 17.74** t/s (the first run, 111.3, is warm-up; without it 75.9 ± 7.9), C2 102.36 / C5 79.49 / C10 73.37 — the `--parallel 8` DFlash2 verify-window shape, not a throughput claim. **The earlier 98.4 t/s single-stream figure does not reproduce** on the recipe path (83.0 / 75.9): same image patch set, different invocation (that trial ran upstream's scripts under a local tag). Both smokes clean on that boot — chat `17 × 23 = 391.` (`finish: stop`, 41 reasoning tokens) and a tool call `get_temperature{"city":"Reykjavik","unit":"c"}` (`finish: tool_calls`). Docs in `recipes/glm/README.md`; receipt `~/benchmarks/tp4-20261018/` §2 (`REPORT.md`, `glm-serve.log`, `glm-launch.log`, `glm-models.json`, `glm-smoke.json`, `glm-ladder.{yaml,json,csv}`).)*

## ifm — closed 2026-10-18
- [ ] **Pass the 7B `fp8_e4m3` KV accuracy gate** — throughput is measured, quality is not, so the ~+6% d8192 win is unusable (`attic/ifm/NOTES.md` §"Still open", the `fp8_e4m3` KV accuracy bullet). *(effort: short)*
  *(**Closed 2026-10-18 — the gate PASSES on triton, and `fa4` cannot carry fp8 KV at all.** Boot 1 (the recipe's `fa4` + `-o kv_cache_dtype=fp8_e4m3`) allocates the pool fine (`KV Cache is allocated. dtype: torch.float8_e4m3fn, #tokens: 1150989`) and then dies in warmup: `AssertionError: q.dtype torch.bfloat16 != k.dtype torch.float8_e4m3fn` out of the flash-attn cute interface (`present[a].dtype == present[b].dtype`) — a kernel-capability constraint (a bf16 query into an fp8 KV cache), not a flag typo, and nothing makes `fa4` accept it here. Boot 2, the sanctioned non-fa4 leg (`-o attention_backend=triton`, the route the recipe comment at `recipes/ifm/k2-horizon-7b-fp8-uno-sglang.yaml:41` names): TTR port 170.2 s / HTTP 173.7 s, `#tokens 1,151,086`, `max_running_requests=32` (not clamped). Accuracy against a same-backend bf16-KV control (200-item caps, seed 1234): house **36/37 = 97.3 %** (baseline 36/37), GSM8K **188/200 = 94.0 %** (baseline 188/200), ARC-Challenge **179/200 = 89.5 %** (baseline 178/200; control on the same backend 175/200) — 0 / 0 / +1 items, all inside ±3. **No length inflation in the fp8 direction:** capped items 22 (fp8) vs 19 (control) of 400, discordant pairs near-symmetric (GSM8K 7 fp8-only / 7 control-only; ARC 6 / 10), and every `length` item is an **empty reply** (the thinking block consumed the 1024/2048-token budget) — an item property, not a KV-precision one. Caveat stated: the fp8 leg runs on **triton**, not the shipped `fa4`, so this closes the *accuracy* question and leaves the shipped recipe (fa4, bf16 KV) unchanged; no throughput number was taken, because a triton figure has no peer on this arm. Receipt `~/benchmarks/sweep2-20261018/`: `REPORT.md` §2, `ifm-7b-fp8kv-fa4-serve.log` (the failure), `ifm-7b-fp8kv-triton-serve.log`, `ifm-7b-ctl*` (the control), `ifm-7b-fp8kv/`.)*

## embed — closed 2026-10-18
- [ ] **Ship or retire the unquantized 8B BF16 encoder tier** — measured within 1.2% prefill of the shipped AWQ 4-bit, ships nowhere (scratch recipe only) (`recipes/embed/README.md`; `attic/embed/AGENTS.md`). *(effort: short)*
  *(Owner decision 2026-10-18 [#39]: retire it to the attic: no measured advantage and no instrument in the lane to argue quality; delete the scratch script and record the negative.)*
  *(**Closed 2026-10-18 — retired as decided; the doc edit is the record, no boot receipt is owed.** `attic/embed/AGENTS.md` §"Retired 8B BF16 tier (measured, never shipped) — owner decision 2026-10-18" carries the negative and the deletion: the unquantized `Qwen/Qwen3-VL-Embedding-8B` prefilled within **1.2 %** of the shipped AWQ 4-bit at its own best concurrency while consuming **108 % more memory** and leaving **41 % less KV** at an identical `gpu_memory_utilization`, and the lane has no embedding-quality instrument, so there was no axis on which it could win. Scratch script `.scratch/embed/bf16ab.sh` (port 8013, same flag set as the shipped pair incl. `--block-size 128` and `cpu_mask=5-9,15-19`) deleted; its boot log `.scratch/embed/bf16-8b-35.log` and bench output `.scratch/embed/cmp8b-bf16-c8.{txt,json}` are kept as the receipt. `recipes/embed/` ships only the 2B and the 8B-AWQ tiers.)*

## explore — closed 2026-10-18
- [ ] **[research — high priority] Assess the Kolibri-1M constant-state release** *(Owner directive 2026-10-16: high research priority.)* — `tfwnotops/Kolibri-1-78B-A3B-Full-MoE-1M-ConstantKV-SOTA-GEFERTIGT-IN-DEUTSCHLAND` (`a91858f3…`, 2026-10-07) is a third-party **code + paper repo — it ships no weights**: it runs our already-shipped, unchanged `Aleph-Alpha/Kolibri-1` under a claimed constant-KV attention state (band + int3 store; 0.208 GB per request at 1M, RULER-1M 13-task mean 93.9 self-reported) plus an "M-Rail" answer gate/rules/map. Assess (a) whether even a **non-shipped eval arm** is acceptable — its `kolibri_state`/`kolibri_mrail`/`mrail` code is **PolyForm Noncommercial 1.0.0**, the MiniMax-M3 precedent, and it is installed as arbitrary third-party code inside the serve container; and (b) whether the state has any SM121 path (every measured cell is RTX PRO 6000 / 2×H100, Triton kernels; no GB10 precedent, no third-party eval, 0 Hub downloads). No new weights to stage — the lane's Kolibri-1 snapshot is already cached. Facts + checklist: `attic/explore/EXPLORE-MODELS-RESEARCH.md` §8. *(effort: medium)*
  *(Owner decision 2026-10-16: **our use is noncommercial, so PolyForm Noncommercial 1.0.0 does not exclude it** — the premise is this use class, not a general reading of the license; a non-shipped eval arm is therefore acceptable. This covers eval arms only and does not lift the bar on the license-blocked entries in the ranking below (MiniMax-M3 is barred as a *shipped* arm). The SM121 question still decides whether there is anything to run.)*
  *(SM121 verdict 2026-10-18 [§8.1]: **a non-shipped eval arm is runnable** — the release carries no arch guard at all, its two Triton kernels compile to real `sm_121a` cubins and vLLM 0.29's FlashInfer gate admits compute capability (12.1) inside our pinned image; but neither headline claim holds — **93.9 is the 131k items-0-7 gate mean printed as 1M** (the repo's own 1M aggregate is 90.4), **the 79.4 unseen-items row has no artifact behind it**, and the real per-request cost at 1M is ≈10.7 GB of host archive on GB10's unified pool beside the 0.18 GB state. Evidence, the boot probe and the arm shape: `attic/explore/EXPLORE-MODELS-RESEARCH.md` §8.1.)*
- [ ] **Trial an MTP-drafted Kolibri arm (TensorFold + the block drafter)** — `josch15366/Kolibri-1-block-drafter` (`4d6cf7be…`, 2026-10-10, ungated, Apache-2.0; 391.3M params bf16 → 782.6 MB `model.safetensors` + `config.json` + a 60,614-id `draft_vocab.json`) is a published block drafter for our shipped `Aleph-Alpha/Kolibri-1` (Kolibri ships no MTP head; the drafter taps layers 44/47/49 and reuses Kolibri's frozen embed/LM head). The author measured it **on one GB10, Kolibri-1 FP8**: **1.31–1.40× greedy** decode over copy drafting (65.0 SWE / 62.1 chat / 70.9 German tok/s; **1.10× at 4 streams**), 1.49/1.27/1.24× sampled as served, acceptance 1.94/1.32/1.13 per round of 3, and lossless output (0 mismatches, greedy + sampled). **It is not a vLLM flag** — it needs the TensorFold fork branch `jschmied/TensorFold:kolibri1-drafter` @ `8ea05aa` (`TENSORFOLD_KOLIBRI_DRAFTER=<dir>`; serving defaults depth 2 / fp8 body / nvfp4 head from `config.json`; overrides `TENSORFOLD_KOLIBRI_DRAFTER_DEPTH`, `TENSORFOLD_KOLIBRI_BLOCK_QUANT`, `TENSORFOLD_KOLIBRI_BLOCK_HEAD`), so this is a **second Kolibri arm** beside `recipes/explore/kolibri-1-78b-fp8-vllm.yaml` (C1 **47.3 t/s** @ d0 — the baseline its copy-drafting-only control matches at 46.6–50.8, so the 1.4× is measured against our own shape). Build it as: (a) a vendored, commit-pinned TensorFold image for that fork (pattern: `recipes/ds4/Dockerfile.tensorfold-dsv41`) + a launcher mod mapping sparkrun's rendered command onto `tensorfold serve` and injecting the drafter env — sparkrun delivers `defaults:` only through `{placeholder}`s, so the env contract rides the launcher (`mods/tensorfold-dsv41-launcher` is the template; `recipes/glm/mods/tensorfold-glm-exl3-launcher` is the prebuilt-image variant); (b) the 1.57 GB drafter as a `defaults:` draft entry so sparkrun distributes **and pins** it (the Laguna draft pattern); (c) one free node: `benchmarking/decode-triage.yaml` over depth ∈ {2,3,4} plus the C1/C4 cells and the house battery, and record acceptance length beside the t/s. Caveats to carry: the card's numbers are development slices with no held-out pool (its SWE slice shares repositories with the training recordings, so treat that one as optimistic), one GB10 measured only, German drafts worst (position-1 agreement 0.63 vs 0.85 SWE); the lane's thinking-on-default trap (empty `content` unless `max_tokens` is raised) applies here too. License: drafter and fork Apache-2.0 — no blocker (unlike §8's item). *(effort: medium)*
- [ ] **Trial the 4-bit vLLM Kolibri quants (the ~31 GiB they free is the prize)** — the Hub's `base_model:quantized:Aleph-Alpha/Kolibri-1` list (24 repos, read 2026-10-16) holds five CUDA/vLLM-family 4-bit packs that cut the shipped arm's 73.5 GiB to ~41–44 GiB, all weight-only on the routed experts and none of them needing an engine fork: **`Quantinine/Kolibri-1-NVFP4A16-FP8`** (42.69 GiB; the best-verified card of the set — 10,692 matched agentic episodes, 24 rows of the official card's benchmark table, six eval tasks, mean KL 0.0718 nats/token with 95 % intervals ≈ 1.5× the model's own batching noise, tool-call parser failures +1.3 pts; **tested on our exact stack**, `vllm/vllm-openai:v0.29.0` + `aleph-alpha-inference==1.0.0`, one GPU at util 0.95), **`iSkye/Kolibri-1-NVFP4-Experts`** (42.68 GiB; **built and measured on a GB10** — 52.1 / 93.5 / 162.6 / **265.9** t/s at c1/2/4/8 against the FP8 original's 48.1 / 80.4 / 127.2 / 179.3, needle PASS 21k→978k, PPL +1.2…+5.3 %; its card's GB10 recipe runs **vLLM 0.30.0** with the plugin installed `--no-deps` + `VLLM_USE_DEEP_GEMM=0` + `--kv-cache-dtype fp8`, while **0.29.0 is declared-compatible but author-untested** — the wheel pins `vllm<0.30` — so try 0.29.0 first and bump only if it refuses; third-party GB10 serving recipe at `github.com/15ky3/Kolibri-1-DGX-Spark`), **`kirillbilchenko/Kolibri-1-MXFP4-MxWave`** (40.93 GiB; also GB10/SM121-measured, on vLLM **0.29.0** — 49.62 / 136.37 t/s c1/c4 against 43.61 / 113.18, PPL +1.53 % — but it **missed its own strict KL gate**, 0.055 vs 0.030, and is tagged experimental: judge it on the gate, not the throughput); two negatives not to re-run blind: `audreyt/Kolibri-1-NVFP4-W4A16` (44.18 GiB; inference **never validated** — CUDA OOM in the post-load Marlin expert repack on an RTX 5090) and `Padakovec/Kolibri-1-W4A16-GPTQ` (41.17 GiB; A100-80GB only, no GB10 precedent). Order: Quantinine (our image + best evidence) → iSkye (GB10-proven speed) → kirill. One kernel gate applies to all three: their experts are FP4-family (NVFP4/MXFP4) and **GB10 has no native FP4 path — they ride W4A16 on Marlin**, so what to watch on SM121 is the *Marlin MoE* variant, not the quant's provenance (the lane's §1 row 4 / Muse-Glimmer lesson); both GB10-measured packs report Marlin NVFP4/W4A16 MoE engaging, and `audreyt`'s failure *was* the post-load repack. Measure on one free node against the shipped arm: C1/C4 (plus the registry-level C2/C5/C10 ladder), the house battery with `tools/quality-battery.py --max-tokens` (the thinking-on trap), and the KV pool at util 0.78 — the freed 30.8 GiB is ≈ **2.6 M more tokens** (≈ 10 more 262k requests), which is the actual point. Checks: every pack here that names its source (`Quantinine`, `kirill`, `audreyt`) was cut from base revision **`e52eb462…`** (2026-10-03), *not* our pin **`258cae8f…`** — that pin is the "fix: quantization config for transformers implementation", whose entire diff is adding `lm_head` to `modules_to_not_convert`, so read each pack's own `config.json` before assuming the omission is harmless; `iSkye` states no source revision at all, so resolve it from its own files; and all three trial arms are new Hub repos, so pin each revision at boot. *(effort: medium)*
- [ ] **Trial the GGUF Kolibri ladder on a forked llama.cpp build** — upstream llama.cpp cannot load `kolibri1` at all (0 hits for the arch in `llama-model.cpp` / `llama-arch.cpp` / `convert_hf_to_gguf.py` on master, re-checked 2026-10-16; the packs say the same for master `b86d2f075`), so the stock first-party `llama-cpp` image cannot serve it and this arm needs `brywil/llama.cpp` branch `kolibri1` @ `68fa28b56` built into its own image (CUDA and CPU-only builds both documented). It would be the registry's first arm on sparkrun's `llama-cpp` runtime — the runtime ships in sparkrun, but no recipe here uses it (runtime facts, first-party images and the GGUF distribution contract: the registry-level *Runtimes* item; precedent for the deferral: `attic/explore/MELLUM-21.md` §5). The list's GGUF packs carry a full size/quality ladder: `Myric/Kolibri-1-APEX-GGUF` Q4_K 41.89 GiB (wiki KLD 0.076 / top-1 89.7 %) → uniform-IQ3_S 32.55 (0.103 / 88.4 %) → APEX-i-mini 25.30 (0.170 / 84.1 %) → APEX-2.4bpw 22.70 GiB (0.212 / 81.1 %), all cut from one shipped imatrix and with **~51 t/s @ 4.6 bpw reported on a GB10**; `webmp3/Sakura-MicroQuality-…` IQ4_XS 38.07 / IQ3_XXS 28.75 / IQ2_XS 20.94 GiB (mixed-quant, `SHA256SUMS` shipped); `Hob-forge/Kolibri-1-GGUF` (the most-downloaded entry on the list, 44.9k) Q2_K 26.67 → Q4_K_M 44.20 → Q5_K_M 51.8 → Q6_K 59.8 → Q8_0 77.4 GiB, plus its `kolibri1-llama.cpp.patch`; `aparusel/ds4-kolibri-1-gguf` Q2 22.78 / Q4 42.56; `kirillbilchenko/Kolibri-1-MXFP4-GGUF-MxWave` 42.30 GiB (stock llama.cpp compatibility explicitly **not** established). Why it may earn the new runtime: only the ten full-attention layers scale with context (~20 KiB/token at f16 ⇒ 262k ≈ 5 GiB), so the two smallest tiers at 20.9–25.3 GiB leave ~90 GiB of a 119 GiB budget free — the first Kolibri able to co-locate with another lane's arm. Score the tiers on the lane's own battery rather than the authors' KLD tables (the vendor `llama-server` sampling differs from the shipped arm's). MLX 3–4-bit packs (`velaia/Kolibri-1-MLX-4bit` 41.30 GiB, `here-be-dragons-ai/Kolibri-1-MLX-3bit` 32.80, `tobiasoberrauch/Kolibri-1-mlx-4bit` 40.99, `eins78/Kolibri-1-mlx-mixed-4-8-bit` 42.18) are **not** a GB10 route without an engine that reads MLX — the qwen3 lane's `TensorFold/Qwen3.8-27B-MLX-4bit` arm is the only precedent — so they stay untrialled until that loader is exercised. *(effort: medium)*
- **Constant-state release — closed 2026-10-18: assessed AND executed (non-shipped eval arm only).** The plugin installs into the pin `vllm/vllm-openai:v0.29.0@sha256:c2914767…` (`aleph-alpha-inference==1.0.0` + `/opt/k1v`, both `--no-deps`) and patches FlashInfer for fp8 KV on SM121 — a boot-observable, not an inference: the resolver logs `arch=sm121` with `kv_cache_dtype=torch.float8_e4m3fn` *after* the swap. A **999,155-token** request answers correctly (depth 10 %, key `5052-NARWHAL`, `PASS 1/1`) in **829.69 s** (≈1,230 t/s prefill, 11.4 t/s decode) and the engine logs **`GPU KV cache usage: 0.2 %`** on it, so the attention state is genuinely constant. The per-request cost is not the state but the **host archive: 10.44 GiB measured** (container cgroup peak − baseline, 4.76 → 15.20 GiB) against the release's billed **0.208 GB** (~54× under), so `rows: auto` = 4 would need ~43 GB and one 1M request leaves 3.9 GiB of the node's 15.5 GiB available: **1M concurrency on GB10 is 1**. One forced deviation: `gpu_memory_utilization` 0.93 → 0.78 (vLLM admits only when `mem_get_info().free >= 0.93 × total`; 113.2 > 97.1 GiB free at start). Nothing entered `recipes/` or `mods/` (PolyForm Noncommercial 1.0.0, eval arm only per the 2026-10-16 owner decision). Receipt `${WOPR_USERNAME}@.35:~/benchmarks/kolibri-state-20261018/` (node-local: `REPORT.md`, `serve.log`, `vllm_cmd.txt`, `mem_during_needle.txt`, `boot_evidence.txt`, `metrics*.txt`).
- **MTP-drafted Kolibri arm — closed 2026-10-18: it boots and engages, and the shipped recipe was fixed to 4 streams.** TensorFold + `josch15366/Kolibri-1-block-drafter` on `.35`: C1 **55.6 ± 5.9 t/s** (+18 % over the shipped arm's 47.2), acceptance length **1.91** at the release default depth 2, house battery **37/37**. The as-shipped `max_num_seqs: 6` pair is **unbootable** (34.0 GiB of caches against 25.9 GiB free), so the recipe now runs **4 streams** (22.7 GiB of caches, full 262,144 window). **Depth 2 beats depth 4**: 44.5 ± 3.5 t/s and acceptance 1.79 at depth 4 — double the drafts per round for slightly fewer accepted tokens — so the release default stays. Acceptance is read from the server (`rounds=N accepted=X/Y`, length `1 + X/rounds`; cross-checked against `tokens/rounds` to ±0.02) because llama-benchy 0.4.0 emits no acceptance field. Traps carried forward: a fresh boot needs one successful completion before it is benchable (the first-start `tensorfold_experts_v7` JIT build failed once, then succeeded on retry and linked in place), and `readiness.inference: false` hides an engine that dies at init. Note the receipt's suite verdict is `fail` only because the *contract* leg returns 404 on this server — house passed 37/37 (`house/summary.json`). Receipt `~/benchmarks/kolibri-mtp-20261018/` (`REPORT.md`, `mtp-triage.*` `bench_f667f0a32253`, `mtp-depth4.*`, `house/`, `depth4-serve-excerpt.log`).
- **4-bit vLLM Kolibri quants — closed 2026-10-18: all three boot-bench against the shipped FP8 arm.** **Quantinine `NVFP4A16-FP8`** (42.69 GiB, our own image `vllm/vllm-openai:v0.29.0`): C1 **52.48 ± 0.21** t/s d0 (+11.2 %) / 51.11 d8192 (+10.4 %), KV **4,606,739 tokens** (47.03 GiB) vs FP8's 1,859,922, battery **36/37** (same failing task as FP8). **iSkye `NVFP4-Experts`** (42.68 GiB): C1 **52.37 ± 0.05** triage / 52.0 ladder, KV **4,618,726 tokens**, **37/37**, and **+10.2 / +20.2 / +22.4 / +26.5 %** over FP8 at c1/2/5/10 — but **the card's 265.9 t/s at c8 does not reproduce**: at the shipped `max_num_seqs: 4` the 8-stream cell runs 4 sequences for 136.1 ± 8.7 t/s, and at 8 slots it reaches 198.6 ± 6.9, still 25 % under (the 0.30.0-vs-0.29.0 engine hypothesis is untested). **kirill `MXFP4-MxWave`** (40.93 GiB): C1 **51.60 ± 0.16**, KV **4,791,929 tokens**, **37/37** with `MarlinExperts` as the live W4A16 path — the behaviour bar held where its own strict KL gate failed (0.055 vs 0.030), and the battery has no resolution to see that miss. Receipts `~/benchmarks/kolibri-quants-20261018/{quantinine,iskye,kirill}/` (`REPORT.md` + ladder/battery JSON per arm).
- **GGUF Kolibri ladder — closed 2026-10-18 for the two tiers measured; three tiers remain unrun.** Both authored tiers boot on the fork image `littlecedar/dgx-spark-llama-cpp-kolibri1:0.4.0-68fa28b@sha256:1928661c…`. **APEX-2.4bpw** (22.70 GiB, `.35`): TTR **22.2 s**, d0 **63.24 ± 0.50** / d8192 **60.79 ± 0.43** t/s, ladder c1 63.83 / c2 113.35 / c5 98.30 / c10 78.62, battery **37/37**, and **79 GiB available** while serving the full 262,144 window (mmap'd weights sit in page cache) — the first Kolibri able to co-locate. **APEX-Q4_K** (41.89 GiB, head-local): TTR **42.2 s**, **57.67 ± 0.21** / **53.94 ± 0.55** t/s, battery **37/37**, ~59 GiB available. **Verdict: 2.4bpw wins on size and speed** (+9.7 / +12.7 % over Q4_K at d0/d8192) and Q4_K's claimed KLD advantage is uncorroborated — 37/37 is saturation, the battery cannot rank either pack, so the cards' KLD (0.212 vs 0.076) stays the only quality signal and prose degrades first. Two reading notes: `ftype` is packer metadata (`general.file_type = 15` on both), not the quantization; and the d8192 cell emits a prefill record beside the decode record. **Unrun tiers:** Hob-forge `Q2_K…Q8_0`, webmp3 `Sakura-MicroQuality`, aparusel `ds4-kolibri-1-gguf` (and kirill's MXFP4-GGUF) — the remaining ladder, not a gap in this receipt. Receipts `~/benchmarks/kolibri-gguf-20261018/` (`REPORT.md` + `apex24-*`) and its `q4k/` subdir (`REPORT.md` + `q4k-*`).

- **Qwen-Image-2.1-Turbo 2048² cell — closed 2026-10-18; the media-gen item stays open for LTX and vLLM-OMNI.**
  One boot on `.30` (task `fc8ff3ca5b23fd3a_2d38dfc4605e`, `recipes/explore/qwen-image-2.1-turbo-7b-bf16-diffusers-script.yaml`,
  TTR 213.6 s after a cold 30.26 GiB download): **2048² = 53.24 s/image** (mean of 3, σ 0.20) against a
  same-boot 1024² control of **11.240 s** (σ 0.008) that reproduces the shipped 11.33–11.41 s. Tiling stayed
  off (no `enable_vae_tiling` in `server.py`/`run.sh`, no seam column in the decoded frame). The three 2048²
  PNGs are **byte-identical** (`sha256 86973bfb…`, 3,337,057 B each), decode at 2048×2048 with 46,995 unique
  RGB, and were viewed: a legible two-tone SPARKRUN poster. Peak **56.505 GiB** torch alloc / 59.779 GiB
  reserved, node `MemAvailable` floor 53.8 GiB. **The lane's ~26 s prediction is falsified 2.04×** — 4× the
  pixels costs 4.74× the time (+18.4 % per pixel). A non-null `num_inference_steps` is **accepted silently and
  ignored**: `12` returned `steps: 8` at the same 11.231 s, because the pipeline is configured from the
  checkpoint's saved 8-step `sample_sigmas`; a non-8-step schedule needs a `sigmas`-accepting mod, not a knob.
  Receipt `~/benchmarks/media-gen-20261018/` (`REPORT.md`, `cells.json`, `proof.json`, PNGs + `sha256.txt`).

## cybersec — closed 2026-10-18
- [ ] **Wire MTP spec decode onto the clean 27B arm** — its BF16 MTP head is preserved and the sibling lane measures 33.8 t/s vs this arm's 10.2 (`attic/cybersec/AGENTS.md`). *(Owner decision 2026-10-15: next-window scope, on the free `.34`/`.35`.)* *(effort: medium)*
  *(**Closed 2026-10-18 — SGLang accepts the checkpoint's own MTP head as a NEXTN draft and spec decode is productive.** `recipes/cybersec/qwen3.8-27b-uncensored-nvfp4-nextn-sglang.yaml` on `.35` (job `aefb625955c32638_64af2f7668b6`): C1 **14.72 t/s at d0 / 14.59 at d8192** against the plain-decode control's 10.21 / 9.66 (**+44.1 % / +51.0 %**), mean acceptance length **2.774** at c=1 (all 40 logged batches > 1, min 1.80), quality battery **37/37**, non-degenerate greedy reply with `enable_thinking:false`. No `--speculative-draft-model-path` was needed — the engine rewrote NEXTN → EAGLE and loaded `Qwen3_5ForCausalLMMTP` from the checkpoint itself. TTR port 149.0 s / HTTP 162.9 s. **New fact: `max_total_num_tokens` = 167,985**, i.e. the served context is really below the advertised `262,144` — attribution unverified because the control's boot log was not retained. Receipt `~/benchmarks/cybersec-nextn-20261018/` (`REPORT.md`, `serve-full.log`, `serve-bench.log`, `cells.{yaml,json,csv}` `bench_cab845506821`, `battery.json`).)*

## qwen3 — closed 2026-10-18
- [ ] **Re-check the 27B arm's mamba/knob tuning under the fixed loader** — the 2026-10-15 re-anchored boot moved every capacity number the arm's knobs were tuned against (KV pool 213k -> 497,878 tokens, no mamba clamp, 48 granted; `mamba_full_memory_ratio: 3.51` is stored as "the optimum is interior and MOVES with context length -- ask before changing" and was measured under the leaky loader). Also stale-as-written until the lane lands its re-measure: the recipe comment's `capped to 21` claim, `recipes/qwen3/README.md:29`'s "TP=1 only ... 262,144 ctx" line, and `attic/qwen3/AGENTS.md` §7's "`max_num_seqs: 48` — never granted" bullet. *(effort: short)*
  *(Owner decision 2026-10-16: re-sweep `mamba_full_memory_ratio` at the shipped 262,144 context and change the stored 3.51 only on a >= 2 % win; the moving-optimum caveat stays.)*
  *(**Closed 2026-10-18 — keep 3.51: nothing clears the ≥2 % bar.** Interleaved ring A-B-C-A-B-C (A = 3.51 control, B = 2.3, C = 1.2) at the shipped 262,144 window, `benchmarking/ratio-at-depth.yaml` (depth 8192, pp 2048, tg 256, c ∈ {8, 16}, 5 runs/cell), two takes per ratio, `--fresh` boot per arm on `.35` solo. Grants (the engine's own startup line, not the recipe literal): **493,436 / 532,703 / 663,496 tokens** for 3.51 / 2.3 / 1.2, slots **48 / 48 / 43** (1.2 clamps — `max_running_requests is capped to 43 by the mamba state cache (max_mamba_cache_size=174, 4 state slots per request)`), no clamp on 3.51/2.3. Decode cells **81.2 / 82.9 / 80.5 t/s at c8** and **105.1 / 104.5 / 102.7 at c16**; the only positive is r=2.3's pooled +2.0 % at c8, which rests on one take (+3.2 % then +0.9 %, inside its own ±3.6/±5.4 sd) and is negative at c16, while r=1.2 is negative at c16 in both takes. **Mechanism: with the fixed loader the slots bind before the pool** — 48 slots × 8,192 = 393,216 tokens needed at the slot ceiling against a 493,436-token pool at 3.51, peak pool use never above **0.34** — so pool size stops mattering at this window and the ratio can only redistribute headroom; the tested cells (c16) sit below both ceilings, so they cannot discriminate. The stored value keeps its moving-optimum caveat: a shorter window or offered concurrency above 48 makes the split decide admission and needs a re-take. Control reproduced: 493,436 / 492,535 tokens (−0.9 / −1.1 % vs 497,878), 48 slots, no clamp; ladder within the 7–25 % inter-boot noise floor (C1 30.5 / C2 53.3 / C5 95.6 / C10 101.5 vs 29.6 / 57.4 / 89.5 / 100.9). The three stale doc claims are corrected in the tree (recipe comment now frames `capped to 21` as history, README says TP=1+TP=2 both measured, AGENTS §7 says 48 is granted under the fix). Receipt `~/benchmarks/qwen3-ratio-20261018/` — `REPORT.md`, `r{3.51,2.3,1.2}-p{1,2}.{yaml,json,csv}` (the `--output` copies are the arm data), `serve-*.log`; bench ids `bench_80f352785674` / `bench_dba0d9306c5e` / `bench_d8894091e3d1`.)*

## Concurrency ladder (registry-level) — closed 2026-10-18
- [ ] **Re-measure the pooling lanes at the ladder points** *(2026-10-15: the runnable form is now `sparkrun benchmark pooling <recipe> --profile <pooling profile> [--skip-run]` (`benchmark run` also works; `benchmark performance` refuses — the category's framework is set before the profile is read); receipts are per-cell `runs/NNN_{kind}_c{k}.json`. `kind` is required. See `tools/README.md` §`plugins/pooling_bench_framework.py`.)* — embed/rerank publish `units/s` at C1/C4/C8/C16/C32 (`tools/pooling-bench.py`); re-run at c 1/2/5/10 and quote `units / wall_seconds` from the receipt. (`recipes/embed/README.md`; `recipes/rerank/README.md:69-70`; `.scratch/embed/csweep8b-order1-c*.json`) *(effort: medium)*
  *(**Closed 2026-10-18 — all four arms measured at c1/2/5/10, `units / wall_seconds` read from each stage's `runs/NNN_{kind}_c{k}.json`.** Solo cells, in each arm's co-location config: **embed-8B AWQ 16.39 / 18.10 / 21.54 / 23.01**; **rerank-8B 18.03 / 18.58 / 21.24 / 21.23** (first cells on record); **embed-2B 38.82 / 46.51 / 85.63 / 104.07** (reproduces the register's 38.2 / 45.5 / 85.2 / 102.4 on the same request shape); **rerank-2B 74.06 / 81.57 / 85.08 / 85.00** — lower than the register's 100.6 at c1 only because the register point is 128-token documents and this profile is 256-token (the ~26 % is document prefill, not a regression), so **no ladder cell is pooled with any published c1/4/8/16/32 cell**. The co-location finding: an **idle co-resident engine is free** — every idle-neighbour cell is within **1.7 %** of solo (8B embed +0.7 % at c1, 2B rerank +0.3 %, 2B embed ±1.7 %) — while a **busy neighbour costs ~2× on the encoder**: 8B 16.39 → 7.48 at c1 (**2.19×**) and 23.01 → 10.37 at c10 (2.22×), 2B 38.82 → 18.28 (**2.12×**) and 104.07 → 54.71 (1.90×); the rerankers lose less at matched concurrency (1.43× 8B, 1.51× 2B at c1) and nothing at c2+ because they are prefill-bound. This independently reproduces the embed lane's 8B+8B 22.52 → 9.89 units/s (2.28×) finding. Method: `sparkrun run` + `benchmark pooling --skip-run --no-stop --fresh` (the boot must not be the benchmark's own), `--fresh` mandatory because sparkrun 0.4.0 re-emits recorded cells from a COMPLETE prior state (`api/_benchmark.py:920`), request shapes `embed-v1-chat` 100 req / 256-token (sha `75cc6e2323da`) and `/v1/score` 1 query × 10 × 256-token documents (sha `8cd47129f79e`). Bench ids `bench_dee7fa255a15` (embed-8B), `bench_f17776e035b6` (rerank-8B), `bench_716ce7478433` (embed-2B), `bench_32092dfc7d47` (rerank-2B). Receipt `~/benchmarks/sweep3-20261018/` — `REPORT.md` §1, per-arm `*-{solo,colo,coloload}.{yaml,json}` and their `-runs/` copies.)*

## embed/rerank — closed 2026-10-18
- **Both shipped 8B arms were unbootable and are fixed — closed 2026-10-18.** One-line fixes, engine-log-verified, with `sparkrun recipe validate` clean: the **embed-8B** recipe moved `load_format: instanttensor` → **`auto`**, because the 8B AWQ pack is sharded behind a `model.safetensors.index.json` and this image's InstantTensor has no index-aware metadata layout — vLLM's `_restrict_instanttensor_to_selected_ranges` raised `RuntimeError: Installed InstantTensor does not expose the metadata layout needed for index-aware loading` before reading a weight; `auto` takes the ordinary safetensors path, while the 2B encoder keeps InstantTensor (one 3.96 GB file). The **rerank-8B** recipe added a nested `"text_config": {"tie_word_embeddings": false}` to its `--hf-overrides`, because `Qwen/Qwen3-VL-Reranker-8B` declares the flag only at the top level (`false`) while vLLM's `seq_cls_model_loader` reads `config.text_config.tie_word_embeddings` unconditionally → `AttributeError: 'Qwen3VLTextConfig' object has no attribute 'tie_word_embeddings'` at engine init (the 2B checkpoint declares `true` inside `text_config`, which is why only the 8B failed; the override must be nested — a top-level key does not reach the text config). Both boot from the **shipped recipe with no `-o` overrides** (health 200 at 260 s / 280 s; embed `/v1/embeddings` 200, dim 4096, L2 norm 1.000000; rerank `/v1/score` 200 with the mod-provided chat template resolved), and their c1 cells are unchanged: embed **16.25 vs 16.39 u/s** (−0.9 %, knob-and-noise: the pre-fix cell used `gpu_memory_utilization=0.25` / `cpu_mask=5-9`) and rerank **17.94 vs 18.03 u/s** (−0.5 %, noise alone). The fix changed the load path, not the served shape. Residual: one pre-existing non-blocking `restated-managed-path` validator suggestion on `reranker_chat_template`. Receipt `~/benchmarks/embed-fix-20261018/` (`REPORT.md`, `{embed,rerank}-{boot.log,dryrun.log,c1.yaml,c1-runs/}`, `{embed,rerank}-request.json`).*

## decision — closed 2026-10-18
- **`convaiinnovations/laya` built, scored and ladded (sub-item of the named-candidates item, which stays open for the other six) — closed 2026-10-18.** Score `tool-eval-bench` v2.8.0 `--decision-bench-only`, same 400-case split as the ladder (cases sha256 `78a228c8…`): **Decision Accuracy 36.1 % (723/2000)**, KL 0.576, Brier 0.316, ECE 0.175, 12 confident disagreements, p50 **4290 ms** / p95 6099 ms, 0 request errors — the vendor's **near-chance expectation** (its zero-shot typed-decisions figure is 0.362 against a 0.461 majority baseline; the card's 0.766 belongs to the separate `laya-typed-decisions` checkpoint), per type noul 48.7 % / choice 28.8 % / score 32.2 %. It runs CPU-only on 5 A725 cores (`/health` `device: cpu`), 421M fp32 params, 1.6 GiB, **no GPU**; TTR port 26.392 s / HTTP 26.420 s. **The shipped recipe did not launch** — `launch_inference failed: serve command does not identify the validated model`, because the snapshot path reached sparkrun's `validate_runtime_command` as `<path>)` inside a `printf` substitution; the recipe now does `export LAYA_MODEL_PATH='{model}'` and builds the JSON from that variable, so the guard sees `LAYA_MODEL_PATH=<path>` as a whole token, with a guard test (`test_model_path_is_a_whole_token_or_key_value`, including the pre-fix shape as the negative). Provenance note: the score and ladder above were taken on the **override boot** (`--served-model-name <path>`); the edited recipe has not been re-booted. Ladder (`tools/decision-ladder.py`, 30 cases, `--runs 1`): **c1 0.449 req/s / 2.25 decisions/s**, c2 **0.447 / 2.24** at doubled p50 (2218.7 → 4462.8 ms) — `/v1/systemone` is serial and does not batch, the same shape as Kai-0.6B. `kev-0.8b` and `d3-edge` were not booted (window closed; queued, not failures). Receipt `~/benchmarks/decision-arms-20261018/` (`REPORT.md`, `reports/laya-teb-report.md`, `logs/`, `ladder-laya-c1c2.json`, `cases/`).*

# 2026-10-18 sweep — late (the TP>2 close and the `.34`/`.35` block)

Archived from `mad-science/TODO.md` when the session was wrapped at the owner's request, copied
verbatim with nested notes. The closures below are measured unless the item says otherwise — the GLM
≥1M probe and the four-way 1M window never ran — and what each leaves open is named inside it.
What the 19:15 policy dropped — the GLM ≥1M probe, the ornith 397B retry, the ds4 C1 re-take — is
recorded here as **dropped, not deferred**, and is not carried as register work; the two questions
that do stay open in the register are the ornith d90 crash mechanism and the qwen4 accuracy coverage.

## ds4
- [x] **Settle the carried upstream v2.4 serve line (IN FLIGHT, not closed)** — the line the launcher now carries (`MEM_FRACTION_STATIC` 0.78 / `CHUNKED_PREFILL_SIZE` 8192 / `MAX_TOTAL_TOKENS` 7,500,000 / `--swa-prefix-tails 128` / `--prefill-decode-interval 2`, all launcher-owned in `recipes/ds4/mods/dsv41-sglang-overlay/launcher.py`) measured **C1 60.2 / C2 73.2 / C5 95.1 / C10 101.5** t/s @ d0 on one TP=4 boot (house 36/37 on the same serve) against the v2.3 line's **67.2 / 88 / 111 / 116** — slower on every cell, so it does not ship on this evidence. The knob-isolation boot (`--prefill-decode-interval` off, `pd-off/` still empty) is queued and the launcher env is **uncommitted**. Receipt `~/benchmarks/ds4-v24-line-20261018/` (`bench.log`, `ladder.{yaml,json,csv}`, `house/`, `serve-evidence.txt`).
  *(**Settled and archived: the numbers above are the interval-ON arm.** The isolation boot then ran and the launcher moved with it — `ba38d13` carries `PREFILL_DECODE_INTERVAL: "0"` and a re-derived `MAX_TOTAL_TOKENS: "6850000"` (a 7.5M pin was silently clamped to the profiled 6,993,408), so nothing is uncommitted. With the flag off the line measures **C2 88.35 / C5 131.83 / C10 123.49** against v2.3's 88 / 111 / 116 — **+18.7 % at C5, +6.6 % at C10, parity at best at C2** — so the "slower on every cell" verdict belonged to the flag, not the line (`recipes/ds4/README.md` §(b)-(d); the launcher's own comment records the same pair at `launcher.py:238-247`). The C1 cells are cold-contaminated on every ladder, so the pooled **67.18 ± 6.97** (n=25) stays the reference and an **interleaved C1 re-take on the shipped line** is the one cell never taken: it needs `.30`–`.33`, which the 19:15 policy took back — **dropped, not deferred**.)*

## glm5
- [x] **Promote the EXL3 3.0bpw full-753B lane to a recipe** — **booted and served 2026-10-18** on `.30`–`.33`
  as `recipes/glm/glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang.yaml` on a source-built image
  (`littlecedar/dgx-spark-tensorfold-glm53-exl3-3bpw:0.6.0-ddfad35@sha256:366c2d4e…`, pushed and pinned):
  `/v1/models` 200 at 240 s, engine load 308.7 s, c1 **31.7 t/s** / c2 25.3 agg (14.5 per req) / c4 40.6 agg
  (11.4 per req), 100,559-token prompt TTFT **258.4 s**, TF_GLM_KV=q5 with DCP over 4 ranks, 96.27 of
  102.86 GiB startup estimate. Two boot blockers found and fixed: an absent `TF_TP_WORLD` (defaults to 2 →
  `NCCL error 4 Invalid rank requested: 3/2`; now set from `--tp` in the launcher) and a wheel that shipped
  no CUDA sources (the JIT died on `latent_rows.cu`; the Dockerfile now mirrors 25 `*.cu`/`*.cuh` onto the
  package). Receipt `~/benchmarks/glm-3bpw-boot-20261018/` (`RECEIPT.md`, `NCCL-DEBUG.md`). *(commit `099a547`)*
- [x] **Measure the EXL3 3.0bpw 1M arm** — the 1M configuration (`TF_GLM_DCP=4`, `TF_GLM_EXTENTS=1`,
  1,048,576-token window, 1,048,584 cache slots) is what the 2026-10-18 boot ran; a 100,559-token probe
  measured 258.4 s TTFT. A true ≥1M-token probe and four concurrent 1M windows were **never run**: the
  four-node window closed first and the owner **dropped them unrun, not deferred** (policy, 19:15). The
  arm's shipped envelope is therefore the 100,559-token measurement, and the mod README names the
  unprobed claims.

## ornith
- [x] **Boot the YaRN long-context (~1M) arm and run its pre-registered needle gate** — **booted and measured 2026-10-18 on `.34`, retry included.** The arm serves (`GET /v1/models` `max_model_len` **1,000,000**, served id `ornith-ai/Ornith-1.5-35B-A3B-NVFP4`, KV pool `max_total_num_tokens` **1,203,041** first boot / **1,202,898** retry, `max_running_requests` 48), and the gate is **5 of 6 rungs**: 262,144 control **PASS 3/3** (99.66–99.86 % fill), 512k **PASS 3/3**, 768k **PASS 3/3** (99.7–99.8 %), 1M d10 **PASS** (977,427 tok, 1,737 s), 1M d50 **PASS** (977,487 tok = 97.75 %, 1,886 s, key `3881-RAVEN`), 1M **d90 ERROR ×2** — `RemoteDisconnected` after 1,246 s (first attempt, container gone) and after 398 s (retry, log captured). **The arm ships at its measured envelope: ≤768k workloads, 1M supported to depth 50 %**; d90 caps the documented depth, not the arm, and stays unmeasured. Receipt `~/benchmarks/ornith-yarn-1m-20261018/` (`needle-1m-d50.json`, `needle-1m-d90.json`, `needle-1m-d90-retry.json`, `serve.log`, `diag-d90-retry/`; table in `recipes/ornith/README.md` §"The YaRN 1M arm" and `attic/ornith/AGENTS.md` §9.1). *(effort: medium)* *(commit `6a5d7c3`)*
  *(Two traps cost launches here: (1) a co-tenant ComfyUI process on `.34` holding ~9.9–13.6 GiB of the unified pool starved the boot to `max_total_num_tokens` 282,227 and then 69,281 — at 69,281 the instrument's 978k prompt is refused with HTTP 400 and every 1M rung reads `TRUNCATED`, so read the grant before starting a ladder; (2) sparkrun's readiness probe killed a healthy serve ~8 s after uvicorn came up, so launch with `--no-ready-wait` and verify `/v1/models` yourself.)*
- [x] **Run the missing 1M depth-90 % needle rung — ran; CLOSED as unmeasurable, re-scoped to a depth cap.** On a clean boot (`max_total_num_tokens` 1,202,898, `available_gpu_mem` 12.55 GB) the retry admitted the 980,633-token prompt and prefilled **43.7 %** (551,863 tokens pending, 592 t/s) when the serve process exited; `RemoteDisconnected` at 398 s against a 3,000 s timeout. Excluded by evidence: **host OOM** (`earlyoom` at 1 Hz never below 11.3 GiB available, no kill line, no `dmesg` OOM record), **driver fault** (no `Xid`/`NVRM`/Oops in that second), and **client timeout**. Named: **serve-side process exit mid-prefill**, mechanism unlogged — ~109 GiB released within 2 s, container deleted 2 s later, last serve line a normal prefill chunk. `--no-rm` did **not** preserve the container (`auto_remove: false` is recorded in the job file yet dockerd handled a task-delete), so the exit code and final stderr died with it. Re-opening needs the serve log **streamed** to the host for the whole request plus the container's exit code/`OOMKilled`, or a `docker events` capture. *(effort: short)*

## qwen4
- [x] **One-boot `--enable-linear-replayssm-spec` test** — **measured 2026-10-18 on `.34`/`.35`.** A capacity lever, not a speed one: the spec-verify's per-draft state snapshots go away (`intermediate_ssm_state_cache` **2.64 GB → 0.00 GB**) and the allocator hands it to KV — `max_total_num_tokens` **1,689,024 → 1,882,944 (+193,920 tokens, +11.5 %)** at an unchanged mamba pool 112 / `max_num_seqs` 24 / 262,144 context; decode ladder 41.99 / 71.20 / 91.86 / 105.22 t/s at k=1/2/5/10 against the shipped arm's 39.90 / 69.45 / 94.98 / 104.45 (k=10 cell n=2, cross-boot control) — **flat within the cell σ**, so it buys headroom, not throughput. Not shipped: no accuracy coverage here and no W4 gate on it. Receipts `~/benchmarks/qwen4-block-20261018/REPORT.md` + `lrs-ladder-1018.{yaml,json}` (`bench_c19a168838eb`) vs `~/benchmarks/qwen4-tp2-20261018/b1-cutlass-…` (`bench_684c21a7cd8a`); recorded in `attic/qwen4/AGENTS.md` §10.1 and `attic/qwen4/NOTES.md`. *(commit `0fd9608`)*

## ifm
- [x] **Decide the withdrawn 36B-A4B sub-lane** — both bounded gates ran on a single node, 2026-10-18 (owner #38: D2 + E6 only; E5/E7/E8/E10 stay unrun). **D2 numerics: PASS** — BF16, FP8+bf16-KV and FP8+fp8-KV all greedy-answer `15:52 | 5h 50m | 12%` with all six intermediate values agreeing, and the patch scores `state=C` exit 0 against the running container's own `xllm.py`. **E6 (fp8-KV): capacity is the win, the throughput claim is not** — KV pool **267,440 → 535,513 tokens (2.00×)** at an identical 52.6 GB footprint; house battery **36/37 = 97.3 %** (easy 19/19, hard 17/18, miss `hard-rev` → `nurkrap`), the lane's joint best; d0 ladder C1 **18.36** / C2 33.28 / C5 48.51 / C10 **66.73** t/s against the bf16-KV arm's 18.21 / 32.67 / 47.31 / 62.92; at long context only **+8.1 % at d28,672** and **−4.6 % at d8,192** (c1, n=3, paired control) — the WORK doc's modelled **+25 % at 32K is falsified**. `attic/ifm/AGENTS.md` + `NOTES.md` (2026-10-18); receipts `~/benchmarks/ifm-36b-20261018/`. *(effort: long)* *(commit `2a260a6`)*
  *(Owner decision 2026-10-18 [#38], now answered: the bounded run happened. The ship/stay-withdrawn call the numbers support is **stay withdrawn** on speed — 18.2 t/s C1 for a 48 GB checkpoint per node, against 32.4 for the shipped 7B — with E6 re-filed as a **capacity** result (16 resident 32K sequences; 131K only via E10 fp8-KV+TP=2), which is worth one boot only if a long-context need appears.)*

# 2026-10-19 (early) — closed during the qwen4 TP=2 campaign

## ifm
- [ ] **Re-open UNO on the 0.9B** — `IFM/K2-Horizon-0.9B-Uno` exists and the gate mod already works for the 7B; the register was falsified for the 7B only (`attic/ifm/AGENTS.md` §9). *(effort: medium)*
  *(**Closed 2026-10-18/19 — the 0.9B UNO arm was booted and measured** (`recipes/ifm/README.md` §`k2-horizon-0.9b-bf16-uno-sglang`; receipt `~/benchmarks/ifm-09b-uno-20261018/`): C1 **123.2 ± 13.2** t/s @ d0 / **90.5 ± 3.6** @ d8192 against a same-recipe fa4 control's 79.0; house **33/37**, GSM8K 173/200, ARC 144/200 with the +11 ARC delta **open and not claimed**. The shipped recipe now carries the `fast` tag on that C1, and its `metadata.caveats` — stale at "Unmeasured arm" — was corrected to the measured state on 2026-10-19. Removed from `mad-science/TODO.md`; the 7B tree-mode item stays open there.)*

## qwen4
- [x] **Run the W4 `#37111` release soak (1–2 h / ~100k)** — only a short smoke ran, so the corruption gate is unproven (`attic/qwen4/AGENTS.md`). *(progress 2026-10-19 00:00 ET — **the soak is running** on the shipped labquant TP=2 boot (`1895030211ea0500_3510a5e0d37d`, `.34`/`.35`), 90 min at 100k depth, started 23:48:10 ET, JSON → `~/benchmarks/qwen4-labq-suite-20261018/gate-37111.json` (the `qwen4-block-20261018` path quoted here earlier does not exist). The first smoke **failed on the harness, not the server**: `gate-37111.py --thinking` documented "default off" but omitted `chat_template_kwargs`, so this thinking-default template spent all 2048 essay tokens inside `reasoning_content` and returned `content: ""` → four false degeneration/truncation findings. Fixed to always send `{"enable_thinking": bool(thinking)}` (`5eca6ba`; the selftest now guards both directions). Raw control: `enable_thinking: false` → 758-word essay, `stop`, 0 reasoning tokens; `true` with 8192 tokens → still all reasoning, content "". Smoke then **PASS**, canary warm==cold.)* *(effort: medium)*
  *(**CLOSED 2026-10-19 01:20 ET — PASS.** 708 turns over 90 min at 100k depth, `max_tokens` 512
  (essay 2048), thinking off: **0 degeneration / 0 truncation findings, 0 transport errors**;
  warm==cold canary `4183`; wall 5,491.33 s, exit 0. `gate-37111.json` + `.log` in
  `~/benchmarks/qwen4-labq-suite-20261018/`; the same receipt carries the boot
  (`max_total_num_tokens` 1,678,528, `scheduler_e2e` 563.75 s), a same-boot ladder (41.22 ± 1.92 /
  72.88 ± 3.08 / 95.18 ± 1.28 / 108.13 ± 1.75 t/s) and `REPORT.md`. Lane row added to
  `recipes/qwen4/README.md`; the serve was stopped and `.34`/`.35` verified idle. A PASS is a
  negative result — `tools/gate-37111-design.md` §"what a PASS proves".)*

## Concurrency ladder
- [x] **Fill C2/C5/C10 for the multi-node arms** — *2026-10-18: the ds4 half is measured; the item stays open only for qwen4 labquant (TP=2), ornith 397B (TP=4) and cybersec arm 5 (TP=2), which still need a window on `.30`–`.33`* — **ds4 knapcio TP=4** (`deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml`, 1017 @ `1bae0e10`): C2 **89.89 ± 3.19** / C5 **113.44 ± 6.12** / C10 **115.36 ± 5.92** t/s @ d0, a second boot reproducing them (C2 86.40, C5 108.78, C10 116.27), and the C1 column written as **pooled 67.18 ± 6.97 t/s (n=25; four same-config takes 69.65/66.40/64.16/69.28, CV 10.4 %, range 56.4–87.9)** because a single 5-run C1 cannot separate the boots or the earlier 81.0; **ds4 TensorFold TP=2** (`deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml`, cold TTR 516.5 s, contract + house 37/37 on the same serve): C1 **68.6 ± 3.39** / C2 **48.1 ± 2.20** / C5 **44.6 ± 1.56** / C10 **42.1 ± 3.54** t/s @ d0. Receipts `~/benchmarks/tp4-20261018/` §1 (`REPORT.md`, `knapcio-ladder*.{yaml,json,csv}`) and `~/benchmarks/ds4-tp2-ladder-20261018/` (`REPORT.md`, decode rows of the `--output` ladders). *(effort: long)*
  *(Correction 2026-10-18, 21:45 — ornith 397B is **dropped** (four-node item, 19:15 policy) and
  `.30`–`.33` are again occupied by an owner TP=4 job, so the two remaining fills — qwen4 labquant
  (TP=2) and cybersec arm 5 (TP=2) — are `.34`/`.35` work.)*
  *(Progress 2026-10-18, late — **qwen4 labquant TP=2 is filled**: 39.90 ± 1.48 / 69.45 ± 7.85 /
  94.98 ± 8.97 / 104.45 ± 3.00 t/s @ d0, n=5 per cell, decode rows of `bench_684c21a7cd8a`'s
  `--output` file (`~/benchmarks/qwen4-tp2-20261018/b1-cutlass-concurrency-ladder.{yaml,json}`); the
  same boot's d0 k8 cell reads 121.21 ± 3.82 aggregate. The boot was a TP=2 job on `.32`/`.33` with
  the shipped config (control for the linear-replayssm A/B), so topology is the recipe's own TP=2,
  not a four-node shape. Index row + `recipes/qwen4/README.md` now carry all four cells. **Only
  cybersec arm 5 (TP=2, `deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang`) remains.**)*
  *(**CLOSED 2026-10-19 — the cybersec arm 5 fill was the last one.** TP=2, shipped chain, engram
  ON, job `2f9a8f3e60a51ee4_3510a5e0d37d`: C1 **67.02 ± 3.19** / C2 **52.95 ± 1.49** / C5 **47.75 ±
  0.53** / C10 **46.78 ± 0.33** t/s @ d0, n=5, `bench_484eb77839b4`, receipt
  `~/benchmarks/cybersec-arm5-ladder-20261019/`; index row and lane README updated. ornith 397B
  stays dropped by the 19:15 policy, so every multi-node arm on the standard d0 ladder now carries
  C2/C5/C10 (the labquant-highcon arm stays `—` by design — its aggregate regime is measured at d8192
  k=16/24).)*

## ornith
- [x] **`moe_runner_backend: marlin` under an interleaved paired control** — the ladder's best extra cell (108.9 t/s) collapsed into noise only because the control was ordered, not interleaved (`attic/ornith/AGENTS.md:497-513`). *(effort: short)*

  *(**CLOSED 2026-10-19 — the interleaved pair ran and the shipped backend stands.** Four alternating
  boots on `.34` (control, marlin, control, marlin; `--fresh` each): C1 **94.1-95.0** control vs
  **102.0-104.6** marlin (+9.3 % means), C2 +3.6 %, C5 217.3-223.2 vs 198.7-209.9 (-7.2 %), C10
  240.1-244.6 vs 218.6-219.1 (-9.7 %) — marlin shifts the curve toward single-stream; no C1-only trade
  justifies losing ~10 % at c10. Receipt `~/benchmarks/ornith-marlin-20261019/`; the detail is in
  `attic/ornith/AGENTS.md`.)*
- [x] **Measure the r0b0tlab W4A16 NVFP4 35B + MTP head** — 63–77 t/s claimed with accuracy parity; rejected on a paper comparison, never measured on our stack (`attic/ornith/AGENTS.md:881-882`). *(effort: short)*

  *(**CLOSED 2026-10-19 — measured; the pack is not adopted.** One boot on `.34` (22 GiB download
  plus first-use FP4 JIT, ready in ~9 min): ladder C1 **58.9 ± 1.65** / C2 88.9 ± 0.98 / C5 143.5 ±
  3.13 / C10 158.4 ± 0.95 t/s @ d0, n=5 (`bench_08a4ac98212b`); house **37/37**. That is ~40 % below
  the official export (100/153/217/244), with the card's 63-77 C1 claim at the measured low end. The
  recipe's caveat now records the measurement; it carries no index row. Receipt
  `~/benchmarks/ornith-r0b0t-20261019/`.)*

# 2026-10-19 (later) — embed co-location boot-verified
## embed
- [x] **Boot-verify the three-way co-location** (decision + embed + rerank on one node) — asserted in the budget math and in the lane README, never receipted (`recipes/decision/README.md` §Operating constraints; `attic/decision/AGENTS.md`). *(effort: short)*
  *(closed sub-item 2026-10-18 — the shipped 8B encoder was **unbootable** and is fixed: `load_format: instanttensor` → `auto`, because the 8B AWQ pack is sharded behind a `model.safetensors.index.json` and this image's InstantTensor has no index-aware metadata layout (`RuntimeError: Installed InstantTensor does not expose the metadata layout needed for index-aware loading`); `auto` takes the ordinary safetensors path, while the 2B encoder keeps `instanttensor` (one 3.96 GB file). Boots from the shipped recipe with no overrides (health 200 at 260 s) and its c1 cell is unchanged: **16.25 vs 16.39 u/s**. Receipt `~/benchmarks/embed-fix-20261018/`; full record in `../attic/DONE.md`.)*

  *(**CLOSED 2026-10-19 — the three-way ran on `.34`.** embed (`qwen3-vl-embedding-2b-vllm-b12x`, 0.25, 8010) + rerank (`qwen3-vl-reranker-2b-vllm-b12x`, 0.30, 8011) + JEV-9B (`jev-9b-decision-vllm`, **0.20 + `max_num_seqs: 32`**, 8000): all three `sparkrun run` rc=0, probes 200 (2048-dim embedding; model list; chat completion), node 104 GiB used / 16 GiB available. The measured budget corrects the lane's cap arithmetic: the pair's runtime hold is 74 GiB (caps 66.93 + ~7 GiB of kernel overhead), leaving **~42 GiB (0.345)**, and JEV's working floor is 0.20 — 0.16 profiles a negative KV cache (−1.66 GiB), 0.35 is refused with free 40.86 vs 42.59 GiB. Receipts `~/benchmarks/embed-coloc30-20261019/REPORT.md` (campaign) and `embed-coloc-final2-20261019/` (shipped config); failed arms kept in `embed-coloc-035fail-20261019/`, `embed-coloc-warm-20261019/` and `embed-coloc-final-20261019/`.)*

# 2026-10-19 (register sync) — dropped by owner policy

## ornith
- [ ] **Retry the 397B DFlash head with prefix caching intact (or fewer spec tokens)** — the recorded ~12% loss is partly a structural confound (vLLM treats every Mamba group as the draft group, disabling prefix caching); only n=8 was tried (`attic/ornith/AGENTS.md:324-328`; `recipes/ornith/README.md` §397B). *(Owner decision 2026-10-15: deferred — needs a TP=4 window on the restricted `.30`–`.33`. **Superseded 2026-10-18, 19:15: dropped, not deferred** — re-file only if `.30`–`.33` return to this work.)* *(effort: medium)*
  *(**CLOSED 2026-10-19 — dropped, not deferred.** The 2026-10-18 19:15 owner policy froze
  `.30`–`.33` and dropped every four-node item; this was one of the three named (with the ds4 C1
  re-take and the GLM 1M arm). It is archived rather than carried because it cannot run without that
  window, and the lane README still documents the 397B arm and its structural confound. Re-file only
  if `.30`–`.33` return to registry work.)*

# 2026-10-19 (ds4 search) — closed

## ds4
- [ ] **Deep web search for unexplored DeepSeek-V4.1-Flash-1017 speedups on GB10** *(Owner directive
  2026-10-19.)* — survey what the lane has not tried: upstream SGLang/vLLM release notes and PRs that
  touch Blackwell/sm_121 (attention and MLA kernels, MoE GEMM paths, graph capture, DCP/DP),
  FlashInfer/CUTLASS/DeepGEMM/DeepEP builds and their GB10 support, NVFP4/FP8/EXL3 releases of the
  1017 base, MTP/DSpark/spec-decode work, prefix-cache and scheduler features, CUDA 13.x image
  builds, and any published DeepSeek-V4.1 tuning or DGX Spark benchmark. Deliverable: a shortlist
  where each candidate names the mechanism, the expected effect, the flag or artifact that carries
  it, and a same-boot A/B plan the `.34`/`.35` pair can actually run — the TensorFold TP=2 arm is the
  runnable shape, plus one-node probes; a TP=4-only find is written into `recipes/ds4/README.md` as
  an upgrade candidate, not queued as a boot (the 19:15 policy froze `.30`–`.33`). Exclude the knobs
  the lane already measured
  (`--prefill-decode-interval`, `--swa-prefix-tails`, `DSV41_FAST_LOAD`, the DSpark block size, the
  KV/token pins; `recipes/ds4/README.md` §(b)–(d) and the launcher-knob bullets), and re-derive any
  claimed win with its own receipt under `~/benchmarks/`. *(effort: medium)*
  *(**CLOSED 2026-10-19 — the shortlist is delivered.** `mad-science/DS4-SPEEDUPS.md` (631 lines,
  34 dated primary sources, 15 explicit UNVERIFIED markers) ranks 11 candidates plus a precondition,
  each with mechanism, expected effect, the carrying flag/artifact, a GB10 evidence label, and a
  pre-registered interleaved A/B with a falsifier. The lane README now carries the upgrade-candidate
  section. No boot was run — the item's deliverable was the plan, not the measurement — and the
  eight TP=4-only findings are recorded as upgrade candidates per the 19:15 policy. The runnable
  subset (clock audit, TensorFold v0.6, `reasoning_effort`) is queued as its own item.)*

# 2026-10-19 (registry docs + explore sweep) — two no-boot items closed

## Recipe schema & documentation (registry-level)
- [ ] **Update the recipe-schema docs for sparkrun 0.4.0** *(Owner directive 2026-10-19; priority:
  high.)* — the authority is the installed 0.4.0 package, cited at `file.py:line`, never these docs
  themselves: `_KNOWN_KEYS` (41 accepted top-level keys) and the `Recipe` constructor in
  `sparkrun/core/recipe.py`, `core/validation.py`, `sparkrun recipe validate/show/vram`, and the
  runtime modules under `sparkrun/runtimes/` (`sglang`, `vllm_ray`, `vllm_distributed`, `trtllm`,
  `atlas`, `modular_max`, `tokenary`, `llama_cpp`, plus the `eugr_vllm_ray` alias). Schema facts to
  record: name from the filename, `recipe_version` default `"2"`, top-level `description:`,
  metadata-only `maintainer:`, unknown keys swept into `runtime_config`, plugin-owned keys,
  `capabilities`/`unsupported_capabilities` outside the workload fingerprint, `readiness`,
  `distribution_config`, `layout`, `include`/`overrides`, `solo_only`, and `cluster_only` (deprecated
  for v2). Bring
  `recipes/MECHANICS.md` in line first (the full key set and the per-key rules, especially "a
  `defaults:` value reaches the engine only through a `{placeholder}`, a runtime flag map or an
  internal key"), then the root `AGENTS.md` (the same rules, plus the stale facts re-measured
  2026-10-19: 58 recipes after the W4A16 archive, 780 tests, `recipes/glm` now two arms — re-measure
  the module and strict-validate counts instead of carrying the 38/648 snapshot), then the schema
  rules restated in `.omp/skills/sparkrun-recipe-edit-to-boot/` and
  `.omp/skills/sparkrun-recipe-launch-debugging/`; keep `attic/` frozen. Verify every shipped recipe
  validates and the repo gate passes. *(effort: medium)*
  *(**CLOSED 2026-10-19 — `recipes/MECHANICS.md` rewritten as the 0.4.0 key reference** (391 lines,
  all 41 `_KNOWN_KEYS` AST-counted from `core/recipe.py:78-120`, with the placeholder/flag-map/
  internal-key wiring rule and a runtime-consumption table), root `AGENTS.md` corrected (snapshot
  counts, lane table, `launcher.py:683`->`814`, `{model}` semantics, `model_revision` count,
  description/maintainer rules, strict-failure table), and both recipe skills updated. Three
  corrections carried: 0.4.0 binds `{model}` to the prepared snapshot path (`models/runtime.py:40-46`),
  does not strip `--revision`, and renders `{model_revision}` from the prepared revision — the old
  text claimed the opposite. Nested/quoted placeholders in `defaults` do resolve
  (`utils/text.py:186-229`, probe-verified). `sparkrun/commands/` does not exist in 0.4.0; the
  `recipe validate/show/vram` surface lives in `cli/_recipe.py`. Unverified: no live boot for the
  `{model}` template shape (code-derived); the "no consumer of `runtime_version`" claim is a
  grep-absence over the installed tree. Gate: 752 tests OK, 48/48 plain validate, 12/48 strict.)*

## explore
- [ ] **Select the lane's keepers and sweep the rest to `attic/explore/`** *(Owner directive 2026-10-19:
  top candidates optimized for generation speed, concurrency, accuracy and small size; the remainder
  moves to the attic.)* — score the **14 measured root-index rows** on those axes from their own
  receipts: C1 and the ladder shape (decode and aggregate), the concurrency ceiling (KV pool,
  `max_num_seqs` clamps), the accuracy cells (house / needle / ARC / GSM8K / BFCL / TEB), and size
  plus peak memory. Keep the Pareto set — fastest decode, best aggregate at high concurrency, the
  accuracy leaders, the smallest arm with real headroom, and any media-gen arm whose own cells are
  closed — and retire the rest with `attic/explore/ARMS-MANIFEST.md`, the lane `README.md` section,
  the root index row, the `tests/test_explore_new_arms.py` / `tests/test_explore_llamacpp_arm.py`
  assertions, any lane-only mod, and a re-measured recipe count
  (`retire-sparkrun-recipe-to-attic`). The two YAMLs with no index row are **not** sweep candidates:
  `mistral-small-4-119b-nvfp4-vllm` is measured-rejected at **28.9 t/s C1** in
  `attic/explore/ARMS-MANIFEST.md` (archive it as measured-rejected after re-reading its receipt),
  and `poolside-laguna-m1-nvfp4-vllm-tp2` is authored but unbooted, so the Laguna-M.1 item above
  governs it until its TP=2 boot produces a receipt; classify both from artifact state, not from the
  stale "unbuilt" label in the build item. The three unrun Kolibri GGUF tiers (`Hob-forge` /
  `webmp3` / `aparusel`) cannot win on measurement; build them first or archive them as unmeasured
  with the reason. The owner's 2026-10-11 weighting (node count, accuracy, speed, memory) governs
  ties. *(effort: medium)*
  *(**CLOSED 2026-10-19 — keepers selected, 10 arms retired to `attic/explore/`.** Keepers: Ling-3.0
  (accuracy leader), Kolibri APEX-2.4bpw GGUF (smallest 262k with measured headroom), Laguna-XS
  (best 262k aggregate at c10), Mellum Q4_K_M GGUF (fastest decode 111.9 / best peak 208.0), the
  Qwen-Image media-gen arm, plus the authored Laguna-M.1 TP=2 pair. Retired: Kolibri FP8 base,
  TensorFold drafter, Q4_K APEX, all three 4-bit packs, Laguna-S, humanizer, Mellum BF16, and
  Mistral-Small-4 (measured-rejected: C1 28.94 +/- 0.03, 89,216-token ceiling at 1.01x). The three
  unrun Kolibri GGUF tiers had no recipe files in the tree and are recorded as unmeasured/not built
  in the manifest. Lane README carries the 14-row decision table (speed/ladder, concurrency,
  accuracy, size/memory, receipt, verdict) and the tie-break record; the root index dropped nine
  rows and nine dead link defs; the orphaned Kolibri mod guard moved to `attic/explore/` beside its
  mods. Gate: 752 tests OK, 48 remaining + 13 archived recipes validate.)*

# 2026-10-19 (Kokoro TTS) — the fourth co-tenant boots

## decision
- [ ] **Boot-verify the TTS fourth co-tenant** (Kokoro-82M, 0.305 GiB on the A725 cores) — the
  recipe **ships** (`recipes/decision/kokoro-82m-tts-cpu.yaml`, tracked since `acf01db`: digest-pinned
  image, `readiness` block, `distribution_config`, taskset command), so the co-location budget's
  fourth slot is authored but has **no boot receipt** — the register's "never built" label was
  stale. Remaining work: one CPU boot, a wav that decodes and plays, and a real-time-factor
  measurement on the A725 cores, then the co-location arithmetic can count it
  (`attic/decision/DECISION-MODELS-RESEARCH.md`). *(effort: short)*
  *(**CLOSED 2026-10-19 — boot-verified on `.34`.** `sparkrun run` as shipped, no overrides
  (`2b9d589b15c3af46_8ed3ce77d78f`): container-start TTR HTTP-ready **14.4 s**, `/health` 200 in
  21 ms. `POST /v1/audio/speech` returned decodable 24 kHz mono 16-bit wavs at RTF **0.588-0.601**
  (1.66-1.70x realtime) over 77- and 1,062-char inputs, two measured repeats each, on the
  `taskset -c 0-4,10-14` A725 set (server observed at 317 % CPU). The budget's "0.305 GiB" is the
  ONNX weights only: `docker stats` measured **1.552 GiB** container / **1.41 GiB** server RSS, and
  the co-location section now counts that. Client caveat recorded: the streamed wav carries
  `data` size `0xFFFFFFFF`, so decode by byte length. Serve stopped, `.34` verified idle, `.30`-`.33`
  untouched. Receipt `~/benchmarks/kokoro-tts-20261019/` (`REPORT.md`, `probe.json`, four wavs);
  lane section `recipes/decision/README.md` §kokoro-82m-tts-cpu; root index row added.)*

# 2026-10-19 (IFM UNO tree mode) — the second geometry is measured-rejected

## ifm
- [ ] **Attempt 7B tree-mode UNO (topk>1)** — a second UNO geometry, never booted (linear is shipped) (`attic/ifm/NOTES.md` "Still open"). *(effort: medium)*
  *(**CLOSED 2026-10-19 — booted and rejected.** The probe (`attic/ifm/arms/zz-k2-horizon-7b-uno-tree-sglang.yaml`,
  K=2 / steps=3 / F=4 / Q=6 — the widest legal tree for that shape) booted on `.34` at TTR 177 s with
  the tree draft CUDA graph captured (0.61 GB). Same-window paired screen against the shipped linear
  arm: **C1 28.3 vs 32.3 (-12.4 %), C2 54.8 vs 57.8, C5 94.9 vs 97.9, C10 127.4 vs 126.6**; accept
  length **2.878 vs 3.058**. Tree mode costs a second graph and accepts less, so the linear arm
  stands and the probe is archived. Receipt `~/benchmarks/ifm-uno-tree-20261019/`; lane note in
  `recipes/ifm/README.md`; manifest row in `attic/ifm/ARMS-MANIFEST.md`.)*

# 2026-10-19 (lane documentation) — the non-t/s lanes carry a documented close

## Concurrency ladder (registry-level)
- [ ] **Give the two non-t/s lanes a ladder or a documented `—`** — the decision arms report `req/s` from a *serial* instrument (`tool-eval-bench`), so filling C2/C5/C10 there needs a concurrent harness; the image arm serves one request at a time, so its `—` should be written down as by-design in the lane doc. (`recipes/decision/README.md`; `recipes/explore/README.md`; `tools/README.md`) *(effort: medium)*
  *(**CLOSED 2026-10-19 — documented, not laddered.** `recipes/decision/README.md` §"A `req/s`
  ladder, not a `t/s` ladder" measures the decision arms on their own instrument
  (`tools/decision-ladder.py`, and the instrument's full-split numbers) and states the close:
  a `t/s`-shaped number here would be a category error, so the cells carry `req/s` or stay `—` with
  the reason. §Concurrency ladder adds "**The image arm's `—` is not a missing measurement**": the
  media arm holds a single denoise lock, so a ladder there would time its own queue and its C2/C5/C10
  stay `—` by design. The explore lane's decision table now records each arm's measured cells or its
  own documented reason (2026-10-19 sweep). Nothing was launched for this item — the documentation it
  asked for already existed and was verified section by section.)*

# 2026-10-19 (llama.cpp runtime) — pin, arch map, policy and the mmap A/B closed

## Runtimes (registry-level)
- [ ] **Explore sparkrun's llama.cpp runtime on GB10, and the viability of GGUF arms** *(Owner directive 2026-10-16.)* — the runtime is first-class and **its GB10 tier already exists**; what has never happened is a pull on our nodes, a digest pin, or a recipe that uses it. Facts read from the installed 0.4.0 tree (2026-10-16): `LlamaCppRuntime`, `runtime_name = "llama-cpp"`, `default_image_prefix = scitrera/dgx-spark-llama-cpp`; `runtime:` is even **auto-inferred** from a `command:` beginning with `llama-server` (`core/recipe.py:54` `_CMD_LLAMA_CPP_RE`, `_infer_runtime`); **`platforms/dgx_spark.py` maps `llama-cpp → scitrera/dgx-spark-llama-cpp:latest`** (beside sglang/trtllm/modular-max/atlas) **and forces `{"mmap": False}` on GB10** — memory-mapped GGUF loading performs poorly on unified memory — unless a recipe opts back in with `mmap: true`, while the generic-NVIDIA tier maps `ghcr.io/ggerganov/llama.cpp:server-cuda`. Both first-party images float: `scitrera/dgx-spark-llama-cpp:latest` (Docker Hub: **458 tags**, `latest` = 2026-08-21, digest `sha256:ad14055470c2b…`, 1.69 GB) and `ghcr.io/spark-arena/dgx-llama-cpp:b<build>-cu131` — and **the runtime source carries a TODO to pin them**. What it already gives us (so this is bring-up + pinning, not invention): `-hf <repo>:<quant>` or `-m <file>`, automatic `max_model_len → --ctx-size` translation, a flag map (`n_gpu_layers`, `parallel`, `threads`, `chat_template`, `reasoning_format`, `split_mode`, `--alias`, sampling, valued `flash_attn` on/off/auto, bools `cont_batching`/`--jinja`/`--no-webui`, inverted `webui`/`mmap`, `mmproj` for vision), and **experimental multi-node RPC** (`cluster_strategy() == "native"`; `rpc-server` workers on :50052, head `llama-server --rpc ip:port,…`, preferring IB IPs for the data path, model distributed to the head only, heterogeneous images allowed, TP→`--split-mode row` / PP→`layer` and mutually exclusive, `data_parallel > 1` rejected). GGUF distribution is a real pipeline, not an afterthought: `repo:quant` colon syntax, a selective `model_sync_gguf.sh` fetch that checks multipart shard completeness, a `gguf-v1:<quant>:<selector>` manifest selection, an `mmproj` auto-selection with a `projector:` override, a remote GGUF header reader for quant detection, and a GGUF bytes-per-weight table in the VRAM estimator. Deliverables: (a) **verify that tier end to end and pin it** — digest *and* per-build tag — recording what the image actually contains (`llama-server --version` + build number, CUDA arch support incl. sm_121, whether RPC is compiled in, whether `--jinja` is present), since the platform layer picks it for us silently; (b) the **arch-level viability map**, measured today by reading each wrapper's GGUF header and matching upstream master's `LLM_ARCH_NAMES` (160 archs): a **stock** first-party image can load `mellum` (`JetBrains/Mellum2.1-12B-A2.5B-Thinking-GGUF` — Q4_K_M 7.52 GiB, MXFP4_MOE 6.55 — i.e. the very route `attic/explore/MELLUM-21.md` §5 deferred), `gemma4` (`humanizer-12b` Q4_K_M 7.10 GiB) and **`laguna`** (`poolside/Laguna-XS-2.1-GGUF` Q4_K_M 18.88 GiB — `EXPLORE-MODELS-RESEARCH.md` assumed a poolside fork; upstream now carries the arch), while `kolibri1` (Myric/Kolibri APEX) and `k2-horizon` (IFM 0.9B) need a fork-built image — upstream master has no such arch (0 hits in `llama-model.cpp` / `llama-arch.cpp` / `convert_hf_to_gguf.py`, checked 2026-10-16), which is the boundary the Kolibri and IFM GGUF items run into; (c) the **standing policy for GGUF arms** — when a GGUF sibling should replace a safetensors arm, how its numbers may be compared to the arm it shadows (llama.cpp sampler defaults and `n_ctx` are not vLLM's, so the lane battery is the arbiter, not the uploader's KLD table), and how 7–80 GiB single-file downloads ride the 200 GbE fabric and the per-node HF cache (sparkrun's GGUF path ignores `auto`/`all`/`safetensors` and errors on any repo whose files do not identify exactly one model, so a `:quant` suffix is mandatory). First-boot questions to answer rather than guess: does `--jinja` carry our checkpoints' own `chat_template.jinja`; how does `reasoning_format` map onto each lane's parser habit (`qwen3`, `deepseek`, `kolibri1`); does the forced `mmap: false` cost anything at load time on unified memory; what do `--parallel`/`--cont-batching` really grant on one Spark (the C2/C5/C10 cells of the ladder section are exactly this); and the **CPU-only build** is the route `## decision` already wants for the Sol-2B GGUF path. Note the images are ~8 weeks old at write time, so re-check the upstream build number for arch coverage before pinning. *(effort: medium)*
  *(Correction 2026-10-18: the `mmap: true` opt-back-in above does not work on a `command:`-template arm — a `defaults:` flag-map key is silently dropped there (`build_flags_from_map` / `_special_flags` run only on the command-less path), and the shipped arm proves it by passing `--no-mmap` literally, so an mmap A/B needs a variant recipe rather than a key (`mad-science/LLAMACPP-GGUF.md` §3). The image pin is **DONE 2026-10-17**: `scitrera/dgx-spark-llama-cpp:b10549-cu131@sha256:ad14055470c2bd5c2b4c088dc5727d950da00f62408f438f4f3833c704af0dca` — build `b2e5e9b`, CUDA 13.1.1, `llama-server` only (**no `rpc-server`**, so the experimental RPC path cannot be exercised on this tier); tier contents in `mad-science/LLAMACPP-GGUF.md` §1.)*
  *(Owner decision 2026-10-16: also ship one stock-image GGUF arm this window, so the runtime is proven by an index row rather than by a pin alone. **Done 2026-10-17:** `recipes/explore/mellum2.1-12b-a2.5b-q4km-thinking-llamacpp.yaml` — booted on `.34` (TTR ≈ 100 s, `--alias` intact), full suite landed (house 37/37, needle 3/3 @32k+131k, arc 77.0% / gsm8k 93.5%, TEB 97, bfcl **73.5 % at the 512 default → 88.3 % at 4096** once `tools/eval-suite.py` learned `--bfcl-max-tokens` (`ecddfd4`); the split — 179 of the parallel categories' 400 questions cut to no call at 512 vs 6 at 4096, the residual loss multi-call shape — is measured in the second receipt), index row + `recipes/explore/README.md` + `mad-science/LLAMACPP-GGUF.md` §5; receipts `~/benchmarks/mellum-gguf-20261017/` and `~/benchmarks/mellum-gguf-tools4096-20261017/`. The remaining GGUF routes for other lanes (Kolibri fork build, humanizer/laguna siblings) stay live in their own lane items.)*
  *(**CLOSED 2026-10-19.** All three deliverables landed. (a) **Pin:** the GB10 tier is
  `scitrera/dgx-spark-llama-cpp:b10549-cu131@sha256:ad140554…`, build `b2e5e9b`, CUDA 13.1.1,
  `llama-server` only — no `rpc-server`, so the experimental RPC path is not exercisable on this
  tier (`mad-science/LLAMACPP-GGUF.md` §1). (b) **Arch map:** measured from each wrapper's GGUF
  header against upstream `LLM_ARCH_NAMES`; `mellum`, `gemma4` and `laguna` load on stock, while
  `kolibri1` and `k2-horizon` need fork-built images (§2). (c) **Policy:** §4 now carries the
  standing rules, and §4.5 records the mmap A/B measured today — a variant recipe (the flag-map key
  is inert on a template arm) put mmap ON at or below OFF at every cell, worst **C5 196.48 vs
  208.28 (-5.7 %)**, so the platform's forced `mmap: false` stands. The first shipped arm
  (`mellum2.1-12b-a2.5b-q4km-thinking-llamacpp`) was boot-verified 2026-10-17 and is a lane keeper.
  Receipts `~/benchmarks/{mellum-gguf-20261017,mellum-mmap-20261019}/`. The CPU-only build remains a
  separate question inside the decision lane's Sol-2B GGUF item.)*

# 2026-10-20 (explore ceiling reference) — the two-node Laguna-M.1 arm is built and measured

## explore
- [x] **Build the Laguna-M.1 2-node ceiling reference** — named then dropped; the family's only 2-node datapoint is third-party (`attic/explore/EXPLORE-MODELS-RESEARCH.md`). *(effort: medium)*
  *(Owner decision 2026-10-18 [#41]: build it this window (the `.34`/`.35` pair is the right shape for a TP=2 boot).)*
  *(2026-10-18, 21:45: the window closed at 19:15 without it. It needs only the `.34`/`.35` pair, which
  stayed idle, so the directive carries to the next window rather than expiring.)*
  *(progress 2026-10-19 — **boot attempted, blocked on head disk.** The recipe's command was corrected
  first (it hard-coded the prepared snapshot path; it now hands `{model}` + `--revision
  {model_revision}`, and the lane's identity negative control was rewritten because it depended on
  that literal). The launch then died during distribution with `No space left on device` at 92.14 of
  129.75 GiB: the head was at 100 % (1.7 GB free), so it cannot stage a 130 GiB checkpoint. The
  partial repo was removed with `hf cache rm` (freed 97.2 GB), nodes verified clean. *Owner decision
  2026-10-19: prune the six attic-only caches* — done, 430 GB freed, head now **493 GB free**, so the
  retry is unblocked and is the next pair-bound boot. Receipt
  `~/benchmarks/laguna-m1-20261019/REPORT.md`.)*
  *(progress 2026-10-20 — **booted on the second attempt, and the disk blocker is gone.** TP=2 on the
  `.34`/`.35` pair (job `poolside-laguna-m1-nvfp4-vllm-tp2`, vLLM 0.29.0 by digest): the 129.75 GiB
  checkpoint downloaded to the head at ~170 MiB/s (682 GB free throughout) and distributed as 259.51
  GiB across four streams, then the 225B TP=2 load; `/v1/models` **200 at 07:53:48**, **≈43 min** after
  the 07:10 launch (sparkrun's own launch phase 1,076.6 s), served id `poolside/Laguna-M.1-NVFP4` with
  `max_model_len` **262,144**. The standard suite (contract/house/needle/hard/tools, needle 512,
  `--job-timeout 21600`) started 07:55:55 into `~/benchmarks/laguna-m1-20261020/`; the ladder follows
  on the same boot.)*
  *(results 2026-10-20 — **the two-node ceiling reference is measured.** Suite 20,097 s, verdict `fail` on
  **contract only** (`finish=length`, `ready=False`, all-empty reply — the same `enable_thinking` shape the
  XS sibling shows): house **37/37**, needle **3/3 at 32,768 / 131,072 / 262,144**, hard **ARC 178/200
  (89.0 %)** and **GSM8K 188/200 (94.0 %)** with 0 empty replies, tools **750/1240 = 60.5 %** (0 transport
  errors). Ladder `bench_6ca06d393d60`: **C1 12.85 ± 0.08 · C2 21.85 ± 0.26 · C5 34.15 ± 0.20 · C10
  34.64 ± 0.06 t/s** @ d0, n=5 — flat past c5, 2.7× from c1 to c10 on two GB10s. **Tools triaged as
  capability, not a parser bug:** `parallel` 0/200 and `parallel_multiple` 0/200, all 400 `wrong_count`,
  call histogram **{1: 374, 0: 26}** — one call emitted where the gold needs several, while 554
  single-call questions passed, so calls do parse. Receipt `~/benchmarks/laguna-m1-20261020/`; lane section
  added to `recipes/explore/README.md`.)*
  *(**CLOSED 2026-10-20 — suite and ladder landed, so the reference needs no further boot.** Ladder
  `bench_6ca06d393d60` C1 **12.85** / C2 **21.85** / C5 **34.15** / C10 **34.64 t/s** @ d0, n=5; tools
  **750/1240 = 60.5 %** triaged as a capability limit (`parallel`/`parallel_multiple` 0/200 on
  `wrong_count`, call histogram `{1: 374, 0: 26}`), not a parser or harness fault. Boot receipts
  `~/benchmarks/laguna-m1-20261019/` and `~/benchmarks/laguna-m1-20261020/`; lane section in
  `recipes/explore/README.md`.)*

# 2026-10-21 (cybersec arm 5 suite) — the tools leg closes the arm

Archived from `mad-science/TODO.md`, copied verbatim: the last open standard-suite leg was re-run on a
fresh boot and the arm now has all five legs.

## cybersec
- [ ] **Finish cybersec arm 5's tools leg** — the TP=2 abliterated graft was drained mid-leg on
  2026-10-20 (session wind-down for an agent update) with four of five legs landed: contract ok, house
  **37/37**, needle **3/3 at 32,768 / 131,072 / 262,144**, hard **ARC 188/200 (94.0 %)** and **GSM8K
  197/200 (98.5 %)**. The tools leg stopped at **107/1,240 questions (101 pass / 6 fail)** and BFCL is
  not resumable, so it has **no score** — this is a partial arm, not a result. Receipt
  `~/benchmarks/cybersec-arm5-20261020/` (`boot.log`, `house.json`, `needle-*.json`, `hard-*.log`,
  truncated `bfcl.log`). Re-run: boot the same recipe on the pair and start tools-only cap-free, or rerun
  the full suite. *(effort: short)*
  *(**CLOSED 2026-10-21 — the tools leg landed and the arm is 5/5.** Fresh boot of the same recipe on
  `.34`/`.35` (task `2f9a8f3e60a51ee4_3510a5e0d37d`, TTR HTTP-ready **59.407 s**, `GET /v1/models` =
  the graft repo id, `max_model_len` 1,048,576), then a cap-free tools-only run: **1037/1240 = 83.6 %**
  in 3,887 s with **0 transport errors** — simple **376/400**, multiple **188/200**, parallel
  **181/200**, parallel_multiple **177/200**, irrelevance **115/240** (all 125 misses
  `irrelevance_error:decoder_success`, a capability shape: the AST categories all finish
  `tool_calls`). **3.133 s/question**; the interrupted run's 1.546 s/q `simple` rate projected 32 min
  and under-counted the non-simple categories. Receipt
  `~/benchmarks/cybersec-arm5-tools-20261021/` (`REPORT.md` merges the four 2026-10-20 legs with this
  one, `bfcl.json`); the 2026-10-20 receipt stays as the interruption record. Suite paragraph in
  `recipes/cybersec/README.md`.)*

# 2026-10-21 (explore — the LTX-2.5 runbook ships as a recipe)

Archived from `mad-science/TODO.md`, copied verbatim: the item was written to land only on a boot
receipt carrying the measured cells, and that receipt exists.

## explore
- [ ] **Ship the LTX-2.5 runbook as a sparkrun recipe** *(Owner directive 2026-10-19.)* — convert
  `recipes/explore/ltx-2.5-runbook/` (ComfyUI v0.34.0, `Lightricks/LTX-2.5`, ~36.9 GB of explicit
  files) into a shipped arm on the qwen-image pattern: `runtime: vllm` only as the
  distribution/launcher contract, `executor_config.entrypoint: ""`, `readiness.inference: false`, and
  a `recipes/explore/mods/ltx-25-launcher` mod that stages the ComfyUI venv, expands the native T2V
  graph headlessly and serves `POST /generate` + `GET /health`. Resolve the gated-distribution
  question first: sparkrun's anonymous distribution cannot fetch a `gated: auto` repo, so either the
  mod downloads with the node's accepted `HF_TOKEN` (documented prerequisite, as the 2026-10-14 owner
  call allows) or the launch refuses with a clear message — do not ship a recipe that hangs on
  distribution. Use the fixed `expand2.py` / `run_cell2.py` from `~/benchmarks/ltx25-20261018/` — the
  repo expander has four defects (`attic/explore/AGENTS.md` §"the three unrun cells + the expander
  defects", 2026-10-18) — keep `frames % 8 == 1`, the `SaveVideo` output node, the explicit-filename
  download rule and the 2200 MHz clock cap as documented prerequisites; carry the
  `ltx-2.x-community-license-agreement` banner (free below the $10M threshold; third parties read the
  text). Land the recipe, root index row and lane section only on a boot receipt with the measured
  cells (T2V 78.1 s / I2V 84.3 s / FLF2V 120.2 s; 4K/50 OOM at 121.16 GiB). *(effort: long)*
  *(**CLOSED 2026-10-21 — shipped and boot-verified, `3dd62d0`.** `recipes/explore/ltx-2.5-22b-nvfp4-t2v-comfyui-script.yaml`
  + `recipes/explore/mods/ltx-25-launcher` on `.35`, one boot, clock-capped at 2200 MHz: cold
  **100.13 s / 84.00 GiB** (ComfyUI + venv 121 s, 36.9 GB of weights 148 s), warm (seed 44)
  **78.1 s / 83.45 GiB**, both on the runbook's own cells; outputs are real content and the audio is
  not silent. Receipt `~/benchmarks/ltx25-recipe-20261021/`; index row + lane section landed with it.
  The gated-distribution question was answered by `distribution_config.models.enabled: false` plus a
  mod-side fetch that sets `HF_HUB_OFFLINE=0` (sparkrun injects 1), with `HF_TOKEN` a documented
  prerequisite. I2V, FLF2V and the 4K/50 preset remain measured on the **runbook** (2026-10-18 cells),
  not on the recipe; the recipe serves T2V.)*


# 2026-10-24 sweep

Archived 2026-10-24 from `mad-science/TODO.md`, copied verbatim: the completed `- [x]` items
and the one self-closing item (the qwen4 diagnostic retirement), with nested notes included.
Live planning stays in `mad-science/TODO.md`; dated session records live in
`mad-science/SESSION-RECORD.md`.

## ds4

- [x] **Try a larger 1M prefill chunk than the shipped 8192 — MEASURED AND SHIPPED 2026-10-24.**
  `CHUNKED_PREFILL_SIZE=16384` on the shipped line (`-o env.CHUNKED_PREFILL_SIZE=16384`, quartet
  `.31`–`.34`, task `a2e141223b52793c_e2c160f10849`): five cold ~999k prefills at **235.3–269.8 s
  (mean 245.0 s, ~4.09k t/s) vs the 8192 control's mean ~576 s / 1738 t/s — 2.35×**, per-chunk mean
  4179 t/s (n=299) vs the control's saturated ~1500, and needle **5/5 PASS** at ~999k so accuracy
  is intact. Shipped as the default under the 2026-10-18 `[#36]` rule (`06ca895`: launcher
  `RECIPE_ENV`, recipe comment, guard updated). Accounting and comparison: `DEEPSEEK.md` §9;
  receipts `~/benchmarks/tp4-window-20261024/`. *(effort: none — done; one boot.)*

- [X] **The two runnable shortlist arms, measured and closed 2026-10-21.** Six interleaved boots on
  `.34`/`.35` (A/B/A/B/A/B, `--fresh`, `/v1/models` + the container's own `tensorfold --version`
  asserted per boot) settled the **TensorFold v0.6 engine bump**: control `fabbe861…` is engine
  `0.6.3` (built 2026-10-05 from `d5d7bb3`), treatment `d6e4c10d…` is `0.6.6` at `3825f62`, and on
  the depth-0 ladder (3 runs/cell, n=9/cell) the treatment reads c1 64.47 (flat), c4 51.15
  (+10.9 %, ranges overlap), c8 **52.45 (+26.5 %)**, c16 **53.21 (+25.7 %)**, with cold prefill
  **2,077 t/s @ 32k (+24.6 %)** and **2,073 @ 131k (+39.5 %)**. The treatment's worst single run
  beats the control's best at c8 and c16, so the falsifier is not met: **adopted**, and the shipped
  recipe now pins `d6e4c10d…` (one-time 264 s JIT on the first v0.6 start; later launches 80.3-80.9 s
  vs the control's 80.1-81.5 s). **`reasoning_effort: high`** was measured request-level on that
  serve: paired same-task A/B (10 tasks × 2 rounds × 2 arms, arm order flipped per round) gives a
  **10.6 % reasoning-token saving** at house 37/37 on both arms with no pass→fail flip — but
  `hard-rev` (128 → 43) carries most of it and the bar is cleared by 0.6 points, so it is recorded
  as "clears, not a headline". Receipts `~/benchmarks/ds4-v06-ab-20261021/` (`REPORT.md`) and
  `~/benchmarks/ds4-v06-build-20261021/` (build log, digest); `mad-science/DEEPSEEK.md` §11.3/§11.4 carry the tables.

- [x] **`DSV41_TP_PAD=0` — FALSIFIED and closed 2026-10-23: the split was already ON, and the treatment
  never booted.** The control boot of the shipped arm (image `acfc331a` + 1017 body, pad at its default) on
  `.30`–`.33` logged `split ON, window GEMMs (no pad)` with `split OFF` 0 and `slice failed` 0, and the
  2026-10-22 baseline serve log shows the same — so the canary-era 42/42 `split OFF` did **not** carry to
  the shipped pair despite byte-identical adapters (`DEEPSEEK.md` §18.1). All three
  `-o env.DSV41_TP_PAD=0` launches died before weights load at `ncclCommInitRank`
  (`ibv_reg_mr_iova2`, Cannot allocate memory); their logs carry `DSV41 TP pad installed` **0** times
  against 5/4 in control, so the override does reach the adapter but no knob result exists. **Do not ship
  the `RECIPE_ENV` line** — the owner's ship-if-passes permission was conditional on a passing treatment.
  Receipts `~/benchmarks/tp4-pad-20261023/`. *(effort: none.)*

- [x] **KV pool regression: 3,424,000 tokens with the 6.85M pin inert — SETTLED 2026-10-24: the fast
  loader is the cause.** The owed control ran on `.31`–`.34` (shared-cache pool, image `acfc331a`,
  same serve line): `-o env.DSV41_FAST_LOAD=0` first **did not reach the engine** — `DSV41_FAST_LOAD`
  was a `RECIPE_ENV` override and the launcher clobbered it (the §6.2 trap, third instance); the key
  joined `AB_ENV` (`49471a2`) and the relaunched control profiled **6,999,040** full tokens at
  `available_bytes=12.77 GB` with zero `fast load ARMED` lines, clamping the pin to
  **6,849,792 — identical to the 2026-10-22 baseline**. FAST_LOAD=1 boots profile 3.42–4.36M,
  variable with page-cache timing (four observations: 3,424,000 / 3,846,656 / 4,238,080 /
  4,355,584), so no fast-loader figure is pinnable; the shipped 6.85M pin is correct as shipped at
  FAST_LOAD=0 and inert-but-harmless at FAST_LOAD=1, and the per-mode pin choice is the owner's
  (`QUESTIONS.md` `#21`). Cost side: stock loader `load_weight=583.97 s` vs 71–138 s eager.
  Full triad table: `DEEPSEEK.md` §18.2; receipts `~/benchmarks/tp4-window-20261024/`
  (`boot1-baseline.launch.log`, `boot3-fastload0*`). *(effort: none — done; three boots.)*
  *(Owner decision 2026-10-24 (SURVEY row 1 / `QUESTIONS.md` `#21`) — the per-mode choice is settled:
  **"Any pins should be accurate, even if a wrong pin would be harmless."** The single 6.85M pin is correct
  at FAST_LOAD=0 and stays; FAST_LOAD=1 gets its own accurate pin (or an explicit no-pin) — the inert
  6.85M clamp must not stand for the fast-load mode, and the launcher's `AB_ENV` makes the per-mode pin
  expressible. This closes `#21` (moved to `TODO.md` §"Settled questions").)*

- [x] **RDMA registration wedge — root cause found and fixed 2026-10-24: `kho=off`.** The wedge was never
  a hardware state needing a power-cycle: kernel `7.0.0-1019-nvidia` enables Kexec HandOver, whose
  ~9.3 GiB scratch area is donated to the allocator as `MIGRATE_CMA` pageblocks; with `MemFree` low the
  allocator hands them to NCCL's host buffers and the NIC's long-term pin fails (`ibv_reg_mr_iova2`
  ENOMEM → `ncclCommInitRank` system error), which is why every warm reboot "fixed" it temporarily — a
  reboot empties page cache, the mechanism, not the cure. The tell is **`CmaFree > CmaTotal`**
  (`CmaTotal: 0 kB`, `CmaFree: ~9.3 GiB` on every node). Fix: `kho=off` via
  `/etc/default/grub.d/99-zz-kho-off.cfg` (grub.d prefix + `$GRUB_CMDLINE_LINUX_DEFAULT` expansion
  both load-bearing), applied to `.31`–`.34` and verified across two reboot cycles: **CmaFree 0**,
  `nr_free_cma 0`, and the quartet boot that died at `ncclCommInitRank` 38 s in got past init
  (`ROCE_TP8_READY` with zero errors). Sources: NVIDIA forum 383023;
  `MiaAI-Lab/DeepSeek-v4-Flash-DSpark-2x-DGX-Spark#259` (ftrace proof + two independent `kho=off`
  confirmations). **Fleet-wide by owner instruction the same hour** (`.30`/`.35` patched and rebooted;
  `beegfs-mgmtd` back active on `.30`); power-cycle stays the fallback for a genuinely wedged HCA.
  *(effort: none — done.)*

- [ ] **First quartet boot under the shared-cache WOPR profile** — created 2026-10-24 when
  `distribution.model.enabled: false` landed on the cluster profile (`960e164`): it is the only event
  that exercises the shared-cache launch path end-to-end and the cell that prices the pool load path
  (§5's load-rate table is the pre-migration baseline). It is also the boot-time-persistence proof the
  migration left open — if the fstab `_netdev,nofail` mount is slow, containers see an empty `/cache`,
  so the launch must assert the prepared model path exists before the engine execs. Boot the shipped
  knapcio line, read `max_total_num_tokens` and the load-time line, and record both against the
  node-local era. *(effort: one boot; pairs naturally with the KV-pool pricing boots above.)*
  *(progress 2026-10-24 — boot 1 **crashed at `ncclCommInitRank`** on the KHO/CMA wedge (see the closed
  item above). **Boot 2 is the result**: post-`kho=off`, the quartet served healthy —
  launch→ready ≈251 s, `load_weight=71.15 s` for the fp8 body (**≈6.7 GB/s from the pool** — the
  "boot times may be longer" worry is refuted; faster than the node-local era), `/v1/models` answers
  with `max_model_len` 1,048,576, and **`max_total_num_tokens=4,238,080`** — the 6.85M pin again inert
  ("larger than the profiled value ... use the profiled value"), between the 3,424,000 regression boot
  with 18.82 GB free at pool sizing; the `DSV41_FAST_LOAD=0` control boot ran later the same day and
  **settled the item** (6,999,040 profiled / 6,849,792 clamped — see the KV-pool item above).
  The reboot cycles en route also **proved boot-time persistence on all six nodes** — after fixing two
  real fstab defects: the rail-wait drop-in was written with a `[Service]` section on the `.mount`
  unit (invalid, ignored — systemd warned) so the mount raced the rail address, and the client's mount
  sanity check (`sysMountSanityCheckMS`, was 11000) canceled three of four simultaneous
  re-registrations; fixed with a `rail-wait.service` + `[Unit]`-only drop-in and
  `sysMountSanityCheckMS = 0` fleet-wide. Receipts `~/benchmarks/pool-boot-20261024/`.)*


## ornith

- [x] **Re-verify the 35B serve line on the SGLang 0.5.18→0.5.21 bump** — a named perf lead (DFlash-reranker + GDN fusion wins) that was recorded as breaking the lane (blocker text at `attic/ornith/AGENTS.md:1203-1206`; the `:883-886` pointer carried here was stale). *(effort: medium)* *(Owner decision 2026-10-19: **approved** — test the bump; it changes the engine
image/digest, so validate the other ornith arms on the new digest before shipping.)*
  *(progress 2026-10-21 — **the recorded blocker is refuted at the target tag: the bump is testable, not blocked.** "The Mamba/SWA radix-cache args were removed upstream" is false. `mamba_radix_cache_strategy` and `mamba_full_memory_ratio` are still declared fields at v0.5.21 (`python/sglang/srt/arg_groups/fields/exec_.py:450-457`, `arg_groups/fields/schedule.py:214-218`), still register as `--mamba-radix-cache-strategy` / `--mamba-full-memory-ratio` (`arg_groups/arg_utils.py:290`), and `extra_buffer_lazy` remains a legal choice with the DFLASH lazy-verify hook wired (`arg_groups/mamba_hook.py:113-120`). sglang#40313 (merged 2026-09-20, shipped in v0.5.21) removed the `MambaRadixCache` and `SWARadixCache` *classes*, which no recipe or mod imports; the LIKELY origin of the misread is the v0.5.20 move of every field declaration out of `server_args.py` into `arg_groups/fields/`, so a grep of the old file finds nothing. Of the two named wins only one reaches this lane: the DFlash reranker (LiLiCorr, sglang#37462) engages only for a draft checkpoint carrying `lilicorr_*` geometry, which the `jzinno` DFlash2 and first-party DFlash heads do not, while the GDN QKV materialization removal (sglang#33778, also v0.5.21) applies on the Triton linear-attention verify path these arms resolve to. **Target:** `lmsysorg/sglang:v0.5.21@sha256:b1259f3e…` (tag 2026-10-01, release 2026-10-02), a multi-arch index with a native `linux/arm64` manifest (`sha256:1f176b3a…`, 14.8 GB); the current pin is a 2026-09-08 arm64 nightly whose serve log reports `0.0.0.dev1+g20ca564bf`. **The change:** one-line digest edits in the three SGLang arms (`tests/test_ornith_recipes.py` asserts a shared digest-pinned container, not a literal). **Pass bar per arm:** contract ok, house **37/37**, needle **3/3** at 32k / 131k / 262k, and the on-file ladder bands — 35B C1 100.8-101.8 · C2 153.1-158.2 · C5 217.4-220.4 · C10 244.2-249.9 t/s at d0, 9B C1 52-59 · C2 101.1 · C5 159.0 · C10 148.9 — with the YaRN arm gated on its needle rungs (262k / 512k / 768k 3/3, 1M at depths 10/50/90 % each at ≥95 % fill, d90 retry rule declared before the run) and on reading its `max_total_num_tokens` grant first. **Estimated 3.5-5.5 h** against this item's 6-9 h; BFCL is out of the bar and would add ~2.5 h per arm. Evidence table with commit-level citations in `attic/ornith/AGENTS.md` §"Engine-bump adjudication — SGLang 0.5.18 → 0.5.21 (2026-10-21, repo-side)"; operator plan, staged diff, and pass-bar table in `recipes/ornith/README.md` §"Engine bump to SGLang 0.5.21". Note for the run: `sparkrun` is not on PATH on the local workstation — validate and render on the head node.)*
  *(CLOSED 2026-10-21 — **all three arms validated on the new digest; the bump ships.** The pins are
  applied to all three SGLang ornith recipes
  (`lmsysorg/sglang:v0.5.21@sha256:b1259f3e…`, a multi-arch index with a native `linux/arm64`
  manifest; the container labels record upstream build commit `e00930c5…`), `tests/test_ornith_recipes`
  passes 29/29, and the pass ran on a free `.34`/`.35` pair in ~4 h against this item's 6-9 h. 35B on
  `.34`: contract ok, house **37/37**, needle **3/3** at 32k/131k/262k, ladder d0 n=5 **C1 96.5 / C2
  148.3 / C5 213.9 / C10 244.1** — every cell inside the on-file band's σ; accept len 2.52-2.64. 9B on
  `.35`: house **37/37**, needle **3/3** ×3; its ladder read C2 89.6 (11.4 % low), then a ladder-only
  re-boot **on `.34`** — the node the on-file band was measured on — read **C1 60.6 / C2 97.8 / C5
  156.1 / C10 147.8**, so the dip was a cross-node artifact, not an engine shift. YaRN on `.34`:
  pool 1,192,993 tokens, needle gate **6/6 rungs PASS** (1M depths 10/50/90 at fills 97.74/97.75/97.80
  %), **the d90 intermittent did not reproduce — first-attempt pass, retry rule unused, no die event**
  (streamed serve-log capture + `docker events` armed throughout; 4 of 4 d90 passes now, on two
  builds). Of the two named wins, LiLiCorr (#37462) is unreachable for this lane (no `lilicorr_*`
  draft exists) and the GDN target-verify change (#33778) produced **no measured gain** — the ladders
  read at or slightly below the prior bands; the bump's value is escaping the dead-end 2026-09-08
  nightly plus 0.5.21's fixes. Receipts `~/benchmarks/ornith-0.5.21-bump-20261021/`; the full
  evidence table is `attic/ornith/AGENTS.md` §"Engine-bump adjudication — SGLang 0.5.18 → 0.5.21
  (2026-10-21, repo-side)", the operator summary is `recipes/ornith/README.md` §"Engine bump to
  SGLang 0.5.21". Ops learned: render/launch from `/<home-dir>/src/sparkrun-recipe-registry`, not
  `/<home-dir>/development` (the lane-local mod resolves relative to the symlink and fails); stop with
  `sparkrun stop <cluster-id> -H <node>` and `docker cp` the serve log first — `stop --all` deleted
  the `--no-rm` 9B container on `.35` and its serve log.)*

- [x] **Re-pin all six SGLang arms to `v0.5.22` and re-validate each on the new digest** — one patch past the ornith lane's 0.5.21, two past the ifm lane's 0.5.20, so the ifm UNO arms put the FA4 anchor patch on trial as well. *(effort: medium)*
  *(CLOSED 2026-10-22 — **all six arms booted and held their bars on the new digest; the pins ship**
  (commit `0f74bc3`). Pin: `lmsysorg/sglang:v0.5.22@sha256:e3a4f06001a29542fc4a8638536d9ffc5eb9c9942b08603c09b19a56eae4a1ae`
  — a published multi-arch index (`docker buildx imagetools inspect`, not a local image id) with a
  native `linux/arm64` child `06441be3…`; `v0.5.22-cu130` and `latest` resolve to the same index. The
  three ifm arms are pinned to the `-cu130` spelling of that digest. Runtime moved to torch
  `2.14.1+cu130`, python `3.12.15`, cuDNN `9.14.0.64`, `nccl_torch 2.30.7`. **OSV: 0 vulns** for PyPI
  `sglang` 0.5.22. Six sequential single-node serves on `.35` (receipts
  `~/benchmarks/sglang-0522-20261022/`), `TTR / pool / house`: 35B DFlash2 **238 s / 1,133,804 /
  37/37** (needle 3/3 at 32k/131k/262k, mamba 614, mrr 48); 9B DFlash **251 s / 1,531,959 / 37/37**
  (mamba 273); YaRN 1M **129 s / 1,187,727** with `max_model_len` 1000000 confirmed in `/v1/models`
  (mamba 1293, 11.11 GB free); 0.9B **94 s / 1,764,610 / 32/37**; 0.9B-UNO **94 s / 1,690,881 /
  33/37**; 7B-FP8-UNO **240 s / 574,698 / 36/37**. The ifm scores reproduce their on-file baselines
  **item for item** (`fmt-2`, `needle-1` / `hard-rev`, `trick-1`, `trick-2`) — 37/37 is the ornith
  lane's ceiling, not this one's, so the gate was no regression against each arm's own recorded score.
  The FA4+UNO mod still applies: its probe logged `anchor count = 1` on 0.5.22 and the arms served
  `--attention-backend fa4` + `UNO`, which stock 0.5.22 refuses at argument validation. **Arm A's
  ladder, n=5 (the recorded reading — the `runs=3` triage read 94.3/146.0/207.1/247.7): C1 97.6 ± 8.8
  / C2 152.1 ± 7.4 / C5 228.7 ± 16.0 / C10 242.3 ± 5.0**, every cell inside the on-file band's σ
  (100.8-101.8 / 153.1-158.2 / 217.4-220.4 / 244.2-249.9) with the direction stated: C1 −3.2 %,
  C2 −0.7 %, C5 +3.8 %, C10 −0.8 %; against the 0.5.21 n=5 readings +1.1 / +2.6 / +6.9 / −0.7 %. Zero
  `WARNING`/`ERROR` lines in all six serve logs, same as the 0.5.20/0.5.21 boots. Gate: 894 tests OK
  (2 skipped); `sparkrun recipe validate` clean on all six (suggestions only). Lane records:
  `recipes/ornith/README.md` §"Engine bump to SGLang 0.5.22", `recipes/ifm/README.md` §"Engine bump to
  SGLang 0.5.22", evidence tables `attic/ornith/AGENTS.md` + `attic/ifm/AGENTS.md` §"Engine-bump
  adjudication". **Registry trap found and recorded:** `@littlecedar/<name>` resolves the *published*
  registry, so a bump boot through it silently served the previous pin (it booted v0.5.21 while the
  worktree was at v0.5.22) — boot by recipe **file path**, and `grep -q <new digest> <recipe> || exit 3`
  before each boot after a shared-tree checkout. **Not done, deliberately:** no ladder re-take for arms
  B-F (only the `container:` line changed, the recorded ladders stand), no 1M needle on the YaRN arm
  (the pass's bar was boot + grant; the 6-rung ladder is ~3.5 h), and 0.9B / 0.9B-UNO were run as
  **probes** of the lane baseline and the FA4 mod rather than as candidates.)*
  *(follow-up 2026-10-22 — the only verification this pass left unspent: a **1M needle on the YaRN arm
  at the 0.5.22 pin**, ~3.5 h, worth doing only if a long-context need appears; the 0.5.21 pass's 6/6
  rungs and its non-reproducing d90 exit are the standing evidence. Re-take it before quoting a 1M
  quality claim on 0.5.22.)*


## qwen4

- [ ] **Retire the restored highcon diagnostic** — `diag-qwen4-unplaced-scales` is mounted in the **highcon** labquant arm only, as insurance now that the shared-expert scale blocker is explained (the rename mod fixes it, and the diagnostic changes no control flow). The `demote-labquant-narrow-mxfp8-to-bf16` `EXTRA_LEAVES` knob is **not shipping**: it was removed 2026-10-19 once its only stated purpose — the QSA-prefill CUDA-graph crash — was falsified, machinery deleted rather than shipped empty (`recipes/qwen4/mods/demote-labquant-narrow-mxfp8-to-bf16/README.md` §2; `mad-science/QWEN4-DIAGNOSTICS.md`; `attic/qwen4/AGENTS.md` §10.1). Only open work: the highcon boot that retires the diagnostic. *(effort: medium)*
  *(Owner decision 2026-10-18 [#40]: chase both explanations — root-cause the shared-expert scale blocker and the QSA-prefill crash rather than declaring the workarounds permanent.)*
  *(**Both are root-caused 2026-10-19** — `mad-science/QWEN4-DIAGNOSTICS.md` carries the mechanism
  with `file.py:line`. The shared-expert blocker is the checkpoint's `.weight_scale` suffix vs the
  engine's `.weight_scale_inv` registration plus gate/up stacking; the rename mod fixes it and the diag
  is now insurance, not a workaround. The QSA-prefill crash is `get_prefill_mqa_inputs`' host sync and
  data-dependent buffer shape during capture; `EXTRA_LEAVES` is **falsified** (the demoted-projection
  boot crashed identically) and the path is unreachable today because the engine disables prefill
  graphs for this multimodal checkpoint. Remaining work shrank to: boot `zz-labq-no-diag` (retire the
  diag control) and delete `EXTRA_LEAVES` (code + docs, no boot). **Correction 2026-10-21: both of
  those are done** — the balanced probe booted clean (next bullet) and `EXTRA_LEAVES` was removed
  2026-10-19, machinery deleted rather than shipped empty (`recipes/qwen4/mods/demote-labquant-narrow-mxfp8-to-bf16/README.md`
  §2; `run.sh` says the same at the floor test). What is left of this item is one boot: the **highcon**
  arm, where the diagnostic is now restored and re-mounted, retiring it only if that boot is clean.)*
  *(progress 2026-10-20 — **`zz-labq-no-diag` booted clean, so the diag control can be retired.** TP=2 on
  the `.34`/`.35` pair (job `1895030211ea0500_3510a5e0d37d`), ready at `/v1/models` 200 in **≈670 s**
  from launch (mods + a 6 m 37 s sharded load), a `/v1/chat/completions` 200, and the house battery
  **37/37** (easy 19/19, hard 18/18). The serve log's only `_scale` activity is the *other* mods' benign
  `[remap] …weight_scale -> …weight_scale_inv` lines — **no `unplaced`/`AssertionError`** — so the assert
  the diagnostic was insuring against does not fire without it. Receipt
  `~/benchmarks/qwen4-nodiag-20261020/` (`boot.log`, `house.log`, `house.json`). **Scope correction
  (same hour):** the first pass deleted the mod outright and stripped it from both labquant recipes; the
  probe proves only the **balanced** config, so the mod is restored and re-mounted in **highcon only**,
  with the recipe comment naming the pending boot. The balanced arm stays diag-free (probe = its own
  receipt). **What the mod does, read from its own README/run.sh:** it is logging-only — it inserts a
  `_log.error(...)` statement as the first branch of the `_scale` check and changes no control flow (the
  assert still fires; it deliberately does not relax it), plus it reowns the runtime cache because
  importing sglang as root triggers flashinfer's JIT. So keeping it in highcon costs one anchored patch
  and a cache reown, no engine behaviour — which is why it stays as insurance rather than as a
  workaround. The item stays open until the **highcon arm boots clean without it**; that boot is the
  queued retirer.)*
  *(**CLOSED 2026-10-21 — the highcon arm booted clean without it, and the mod is retired.** The
  control boot ran the mod with its payload never firing (`[diag] UNPLACED _scale` = 0 on both ranks)
  and every bs-sweep cell inside 3.4 % of its control — **86.8 / 87.5 / 89.5 / 75.4 t/s** at
  k=8/12/16/24 against 84.9 / 89.1 / 89.1 / 72.9, TTR **9.6 min** (`scheduler_e2e=571.22`),
  admission unclamped (`max_total_num_tokens=1587072`, `max_running_requests=32`, mamba 128) — so the
  restore moved nothing and the mod had no work left. It then came out of the recipe's `mods:` chain
  and the two "pending boot" comment lines, moved to `attic/qwen4/mods/diag-qwen4-unplaced-scales/`
  (directory and README kept as provenance), and the recipe was re-booted diag-free to prove the
  edit: `/v1/models` 200 at 262144, `max_total_num_tokens=1597376`, no `AssertionError`, and
  `_diag_unplaced_scales` **absent** from the patched engine file. The `_scale` failure mode it
  watched for is preserved in `recipes/qwen4/README.md` rather than lost with the comment lines.
  Receipts `~/benchmarks/qwen4-highcon-20261021/{REPORT.md,serve-*.log.gz}`.)*


## explore

- [x] **Ship the humanizer-12B rewrite arm at Q6_K, the smallest tier that passes its own instrument** — measured 2026-10-22 on `.33` (`sparkrun_7b0a21d0dbeb323d_80fa71eb085e`), commit **`8282f91`**: C1 **17.92 ± 0.04 t/s** @ d0 and 17.87 ± 0.05 @ d8192 (pp 999 / 1,366 t/s) — **2.36× the archived bf16 arm's 7.6** at 10 GB instead of an 88 GB repo; TTR **10.8 s**; **`/v1/completions` only**, because the checkpoint defines no chat template; **0 genuine fact errors across 40 rewrites vs the bf16 baseline's 1** (69 flags, all notation). Q4_K_M is recorded **measured-rejected**: 23.18 ± 0.19 t/s but 2 genuine fact errors ("about 90 minutes" → "A couple hours"; year 2026 → 2006), so it lost the only variable under test. Receipt `~/benchmarks/humanizer-20261022-q6k/`; lane row + tier reasoning `recipes/explore/README.md`. *(no ladder by design — a single-request rewriter has no C2/C5/C10 cell.)*


## Recipe schema & documentation (registry-level)

- [X] **Give the llama.cpp build job a runner — closed 2026-10-22 as a GitHub-hosted arm64 job**
  (`QUESTIONS.md` `#8`: "GitHub-hosted arm64 — confirmed"). The self-hosted ask above is **retired, not
  kept as a fallback**: `0976a1e` puts the build job on `runs-on: ubuntu-24.04-arm`, deletes the
  `vars.ARM64_RUNNER_ENABLED` gate and its guard, adds a 20 GB disk preflight (the hosted `/` is the
  constraint, and a failed build under it is reported with `::error::` rather than an ENOSPC link
  failure), and moves the guard suite to **931 tests**. What this unblocks is unchanged: the
  stock-upstream image work (`recipes/explore/Dockerfile.llamacpp-upstream`, `f1b458d`) and the
  Mellum MTP A/B, whose pre-registration is recorded in the lane item above — the first hosted run,
  not the landing, is what proves the build.


## Shared storage (registry-level)

- [x] **Run the two-node BeeGFS pilot on `.34`/`.35`** — ran 2026-10-22, `13:26–13:46:41` ET, with the
  pair exclusive to it (owner condition: no lane serve, no transfer and no benchmark cell beside it).
  End state on teardown: 0 beegfs packages, 0 failed units, **0 containers**, `/` back to 279 GB free on
  `.34` and 615 GB on `.35`. Numbers, the source-build reconciliation and the round-3 install that
  followed: `mad-science/BEEGFS-REPORT.md` §10; receipts `~/benchmarks/beegfs-pilot-20261022/`.
  *(effort: medium)*

- [x] **Execute the HF-cache migration onto BeeGFS (owner-authorized 2026-10-24)** — the owner's
  instruction, quoted: *"We want to move the entire head node's cache into beegfs, delete duplicates from
  the other nodes, and then repeat that process for each node until all models are deduplicated and live
  in beegfs."* Execution followed `mad-science/BEEGFS-REPORT.md` §11 (`9c96975`) under the gates recorded
  here (hash parity and the `bind,ro` mount before any local disposal, a trash-rename before any `rm`,
  the pool free floor 500 GB). **Boot-time persistence is STILL UNVERIFIED** — no post-migration reboot
  is recorded, and the fstab `_netdev,nofail` + rail-wait risk (a slow mount leaves containers seeing an
  empty `/cache`) stays open under the activation item's (a).
  **Done 2026-10-24:** the owner reports the cache is **entirely on the pool** — all models deduplicated
  and live on BeeGFS, per-node duplicates deleted — closing `QUESTIONS.md` `#20`. The completion state
  is the owner's report; the receipts above are the execution record. Consequences:
  **boots read weights over the pool, so boot times may be longer** (no pool boot has priced the new
  path yet); and the head no longer stages or fans out bodies, so `AGENTS.md` §Node hygiene's >60 GB
  node-local rule has lost its reason and should be revisited after the first boot from the pool.
  Receipts: `~/benchmarks/beegfs-migrate-20261024/`. *(effort: large, multi-window — executed.)*


## Image pins and advisories (registry-level)

- [x] **Sanitize cluster-internal addresses out of tracked files** — a history-wide audit on 2026-10-20
  scanned `git log -p --all` and `git log --all --format='%h %s%n%b'` for fabric IPs, the CX7 RoCE
  subnets and `spark-*.<internal-domain>` names. It found **221 patch-body lines across history and 8
  commit-message lines**, and confirmed the two by-design-ignored paths (`mad-science/REPORT.md`,
  `.local/`) were **never tracked**. The live exposure is the *current tree*, not only history: attic
  lane docs, the ds4 benchmark harness under `recipes/ds4/benchmarks/`, one glm launcher README, and
  fixture/docstring uses in `tests/`+`tools/`. The 2026-10-20 pass took **the tree only** and left the
  history to a separate owner decision; **that decision was taken and executed on 2026-10-22** — the
  history is rewritten as well (`QUESTIONS.md` `#16`, tip `240ecd6`; the `history-purge` item below
  carries the execution record), and `tests/test_tracked_address_hygiene.py` now walks `git ls-files`
  on every gate run. *(effort: short)*
  *(progress 2026-10-20 — **the tree is clean; the history was left to the owner.** Masked with the
  repo's own rule (`.omp/skills/sparkrun-tracked-file-ip-hygiene/SKILL.md`): RFC1918 literals become the
  `.30`-`.35` node shorthand, fabric words become "the CX7 plane-A/B subnet", the internal head hostname
  becomes `<head-node>`, upstream-template placeholders become `<master-ip>`, and the four hostnames in
  the identity map and in a tuning `metadata.json` become their shorthand nodes. **71 lines across 22
  tracked files held a literal; 0 do now** (per file: the two ds4 benchmark raw logs 12 each, the ds4
  lane AGENTS.md 5, `tests/test_cache_audit.py` 10, `tools/cache-audit.py` 5,
  `tests/test_glm_launcher_shim.py` 5, the ds4 benchmark README 4, and one to three each in 15 further
  files: attic lane docs, a glm launcher README, the ds4 harness scripts, `tools/decision-ladder.py`).
  **One exemption, decided by evidence:** `recipes/ds4/benchmarks/data/hle_test.jsonl:121` is a
  benchmark question that happens to discuss a private network in its prompt — it is data, not our
  fabric, and masking it would corrupt the eval. **Two coupled fixture changes:** the census fixtures in
  `tests/test_cache_audit.py` + `tools/cache-audit.py` could not take the `.NN` shorthand because the
  parser rejects a leading-dot token as a host (the merge test then produced 3 rows instead of 2), so
  they carry `host-30`-style names instead, assertion and fixture changed together; the glm shim fixture
  takes `.30:25000` unchanged in behaviour. Gate after the change: **752 tests OK** (2 skipped), **51/51**
  plain validate, `bash -n` clean. **History:** the earliest commit that already carried a literal is
  `d8f38a3` (2026-09-18, "Close labquant blocker (e)…", first management-subnet literal); the CX7 subnet form enters at
  `3c518d1` (2026-10-02, ds4 knapcio). Both were published under the pre-rewrite history; the owner
  elected the rewrite on 2026-10-22 (`QUESTIONS.md` `#16`) and it is **executed** — every SHA in this
  file is now a rewritten one, and the `history-purge` item below carries the pre-rewrite tip.)*

- [x] **`history-purge` — rewrite git history to remove the cluster-internal addresses** —
  **authorized 2026-10-22** (`mad-science/QUESTIONS.md` `#16`) and **executed the same day**. Scope was
  the 221 patch-body lines and 8 commit-message lines the 2026-10-20 audit counted (the item above
  carries the audit); the working tree was already masked, so this was history only, and a rewritten
  history was the accepted cost.
  *(progress 2026-10-22 — **done: `aac85ec` → `240ecd6`, force-pushed.** `git filter-repo
  --replace-text` over one substitution file built from the same masking map the tree sweep used;
  **849 commits preserved**, **one ref** (`refs/heads/main`, with `origin/main` and the remote HEAD on
  the same commit), **0 tags**; the push was `--force-with-lease`. **Verification at the new tip:** the
  audit's own scanner re-run over `git log -p --all` reports **7 address lines, all inside the three
  exempt files** — the published HLE question (`recipes/ds4/benchmarks/data/hle_test.jsonl:121`), the
  CI detector's planted control, and the hygiene guard's own pattern plus four controls — and
  `git log --all --format='%h %s%n%b'` reports **0** commit-message hits; the tracked-tree guard
  (`tests/test_tracked_address_hygiene.py`) is green. **Signatures: 10 `E` + 839 `N` before, 849 `N`
  after** — a consequence, not a loss: filter-repo strips `gpgsig`, so the rewrite drops commit
  signatures while every commit object survives. **Every commit SHA changed**, so every citation in the
  tree was re-pointed through filter-repo's own `.git/filter-repo/commit-map` — **298 citations across
  26 tracked files**, and a pre-rewrite SHA in an older copy of any doc no longer resolves here.
  **Backups:** `/tmp/purge-backup/pre-purge-20261022-141525.git` is a `git bundle` (13.8 MB,
  `git bundle verify` reports a **complete history** at `aac85ec`), and
  `/tmp/purge-backup/pre-purge-mirror.git` is the mirror clone. **Clones:** the workstation cache and the
  `.34`/`.35` registry caches were re-cloned at the new tip so no cache still carries the old objects;
  `.30`–`.33` were left untouched. **`origin` is the only remote — there is no `spark-arena` remote**,
  and re-adding one later would need the same care about which history it fetches. Gate at the new tip:
  **940 tests OK** (2 skipped), **67/67** plain validate, **49/67** strict (the same 18 accepted
  findings).)* *(effort: medium)*

