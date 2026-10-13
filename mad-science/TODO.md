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

# DECISIONS — nothing open (2026-10-12)

Both 2026-10-12 questions were answered in-file and folded: next-window scope/budget → the
preamble advisory; the glm5 TP4 window → deferred to an owner-announced window (glm5 lane item).
The 2026-10-11 questionnaire register: `git show 8a98379:mad-science/TODO.md`. New owner
questions land here, each with a `→ Answer:` line.

# TODO list

Budget: 12 hours — **extended by 5 h on 2026-10-11** (the session ran ~13 h to the first wrap, then continued). *(Owner decision 2026-10-12: **unlimited budget going forward; every TP=2/TP=1 lane gets nodes, in any order** — only the TP=4 glm5 lane waits for an owner-announced exploration window.)*

WOPR sparkrun cluster state (checked 2026-10-13):
- `.30-.33` — ds4 knapcio TP4 serve. This is the primary model we use; it is taken down during TP=4 exploration windows for your use. **When you see this model online, protect it from being taken offline — it could crash this agent's session.**
- `.34`, `.35` — idle; this session's JEV / Kai / Sol / Ling / Nemotron-1M / Kolibri serves are all stopped

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
- [X] If yes to either of the above, build and test the recipe upgrades. **2026-10-10: the one candidate (gamma 5→2) was built and A/B-tested — REJECTED.** Same-window paired boots: γ=2 loses at C4/C8 (−5.3%/−2.9%), ties C1, +4.5% at C16. Shipped value stays 5; receipts and mechanism in `mods/dsv41-sglang-overlay/launcher.py` (DSPARK_BLOCK_SIZE comment).
- [X] Update the appropriate README.md and AGENTS.md. **2026-10-10:** README carries the needle/stability verification and the γ A/B caveat; the launcher comment holds the full γ write-up with receipts (commit `6cea1ed`).
- [X] **2026-10-11 incident, recovered:** a cleanup loop in this session ran a broad `sparkrun status | grep` and stopped the 20-hour knapcio TP4 serve along with the session's own serves. The lane was relaunched on `.30-.33` and verified healthy (all four nodes, `deepseek-ai/DeepSeek-V4.1-Flash`, 1M context). Lesson recorded to long-term memory: never derive a stop list from a broad status pattern; filter to your own task IDs and review the list before stopping.

## glm5
GLM 5.3
- [X] Research this: https://github.com/bertholomus/glm-5.3-tensorfold-tp4-4xgb10 — full assessment in the rewritten `recipes/glm/GLM-5.3-RECOMMENDATIONS.md` (repo A = runnable EXL3 3.0bpw TP4 recipe, 82 t/s aggregate measured, engine on the unreleased `glm-dsa-tp4` branch).
- [X] Research this: https://github.com/bertholomus/glm-5.3-flash-nvfp4-gb10-tp4 — repo B = validation/evidence package for GLM-5.3-Flash NVFP4 (qualified receipts, KV ladder, DFlash2 CC BY-NC-ND trap).
- [X] Update the recipe research — `recipes/glm/GLM-5.3-RECOMMENDATIONS.md` rewritten 2026-10-10; the reference-image claim corrected 2026-10-11 (the image exists — see below).
- [X] Build out the recipes. **2026-10-11: done as far as a 2-node session can reach.** *(Owner decisions 2026-10-11: attempt a pinnable Flash image — resolved below as the existing `glm53-flash` digest pin; attempt a `glm-dsa-tp4` source build for EXL3 — resolved below as no-build, editable install.)*
  - **Flash image blocker RESOLVED:** `vllm/vllm-openai:glm53-flash` EXISTS on Docker Hub (pushed 2026-09-09; 8.7 GB). Pin = the digest docker resolved on a runner node, `sha256:819ec9c063412e5730d1b0e82046ba540d1bf991f3c4f661a849aae8a0c52374` (manifest-list digest; the Hub API's amd64-image digest `sha256:0674a3ea…` is inside it). Device-free engine inspection of that build (0.28.1rc1.dev580): `glm45`/`glm47` parsers registered, `method: dflash` native, Glm5Next*/GlmMoeDsa* arch classes present, `--moe-backend` is the flag this build wants.
  - **Recipe drafted:** `recipes/glm/glm-5.3-flash-nvfp4-dflash-vllm.yaml` — repo B's runtime-formula.json verbatim, checkpoint pinned to `36c184c6` (169B params, arch `Glm5NextForConditionalGeneration`), plus the three vLLM boot fixes every new lane needed (cleared image entrypoint, snapshot-path pin, spec config held in `defaults.speculative_config`). **NOT boot-verified: TP4 needs 4 nodes.**
  - **EXL3 "source build" resolved as no-build:** the engine is `bertholomus/TensorFold@glm-dsa-tp4` installed editable into `nvcr.io/nvidia/pytorch:26.07-py3` at container start (`tfrun.sh`) — no image exists to build. Engine branch cloned on the head run dir at exactly `ddfad35`.
- [ ] Boot-verify both glm5 recipes when a 4-node window opens (Flash TP4 + EXL3 TensorFold TP4 via `scripts/tfrun.sh` in repo A's work dir). **DEFERRED — owner decision 2026-10-12:** wait for the next owner-announced TP=4 exploration window; do not take the ds4 serve down to make one (see the cluster block).
- [X] DFlash2 draft usability: **owner decision 2026-10-11** — use the DFlash2 drafts (non-commercial cluster use satisfies CC BY-NC-ND); the Flash spec-decode route may be built.
- [ ] Run quality benchmarking pass. Blocked with the boot (no server yet).
- [ ] Select the best recipes from all lanes and move the rest to the @attic. Nothing to select until the lanes boot.
- [X] Update the appropriate README.md/AGENTS.md. **2026-10-11:** `recipes/glm/README.md` written (both lines, the no-build engine path, the licence note) and root index rows added.

## ornith
Ornith 1.5
- [X] Check if there's any updated models, quantizations, or runtime improvements that could improve accuracy and throughput. **2026-10-10: nothing superseding** (scan recorded in `recipes/ornith/README.md`): ornith-ai quiet since 2026-08-29, jzinno DFlash2 unchanged; an SGLang 0.5.21 bump BREAKS the 35B serve line (Mamba/SWA radix-cache args removed upstream); one untested lead = the DFlash2 author's 114.2 t/s reference config (multi-knob confound, needs a same-node A/B).
  - **Operational fact (2026-10-11): `@littlecedar/<name>` resolves from the registry CLONE** at `~/.cache/sparkrun/registries/littlecedar` (registries.yaml → GitHub URL), not the local tree — local edits are invisible to cluster launches until pushed + `sparkrun registry update littlecedar`. The first control boot ran the pre-session recipe for exactly this reason.
  - **Distribution-blocking incident (2026-10-11, fixed):** the runner caches' ornith `chat_template.jinja` was honed in place in September and sparkrun's model-preparation validator now rejects it against hub metadata (`wrong_size`) — every launch died at distribution. Fixed by restoring hub content in the caches and shipping the honed template via `@littlecedar/mods/ornith-honed-chat-template` + `--chat-template` (guards in `tests/test_ornith_honed_chat_template.py`). The checkpoint is revision-pinned (`94e431d9` + `--revision`).
- [X] If yes to the above, build and test the recipe upgrades. **No — nothing superseding, no upgrade built.** The lane ships unchanged.
- [X] Build testing and benchmarking battery tooling. **RESOLVED 2026-10-11 by survey: no new tool is built.** *(Owner decisions 2026-10-11: standard suites first — adopt `tool-eval-bench` as the shared suite via `sparkrun benchmark tools` (verified on the head node), promote `recipes/ds4/benchmarks/` as the shared hard tier (ifm already scores with it), and keep only the four stdlib instruments no standard reaches: `quality-battery.py`, `qwen4-quality-eval.py`, `pooling-bench.py`, `gate-37111.py`; `needle-haystack.py` stays as the client. Survey receipt: `agent://BenchmarkSurvey`.)*
- [X] A/B the DFlash2 author's 114.2 t/s reference config same-node (multi-knob confound). *(Owner decision 2026-10-11: spend node time on this lead this session.)* **2026-10-11: CLOSED as a negative result with receipts — no knob is distinguishable from boot noise; the shipped config stands.** Ladder (d0 t/s): control 106.8 (old recipe) / 99.3 (honed control-2) / ① draft10 86.5 / ② marlin 108.9 and 103.4 (repeat) / ③ extra_buffer 103.2 / ④ float32 90.4 / ⑤ full author 84.6. Same-config spread on the node is 7.5%; marlin's two runs straddle it, so it is not a win; the losers (① ⑤ ④) are outside the noise. One confirm cell was **voided**: the `.35` boot lost spec decode (30.8 t/s) and was OOM-`Killed` — a memory-starved node, not a recipe cell. Files: `~/benchmarks/ornith-dflash2-ab-20261011/`; write-up in `recipes/ornith/README.md`.
- [X] Run quality benchmarking pass. **2026-10-11: 37/37 (19 easy + 18 hard, zero flakes)** on `tools/quality-battery.py`, one boot — the same perfect score as the qwen3.8-27B DFlash2 arm, at ~3× its C1. Recorded in `recipes/ornith/README.md`.
- [X] Update the appropriate README.md/AGENTS.md. **2026-10-11:** `recipes/ornith/README.md` carries the ladder table, the confirm/void analysis, the honed-template delivery story, the revision pin and the quality score. The lane has no `AGENTS.md` (unchanged).

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

## qwen4
Qwen 4.x (and 3.8 Flash Next)
- [X] Check if there's any updated models, quantizations, or runtime improvements that could improve accuracy and throughput. **2026-10-10:** the labquant upgrade candidate (step-5500 QAD at main `6c01ac37`) has a **complete per-mod re-verification plan** — `attic/qwen4/status/W14-LABQUANT-5500-MOD-PLAN.md`: one mod breaks (fail-closed, fix direction known), one is obsolete (drop it), five survive. NVIDIA's official NVFP4 quant: boot-answered **REJECTED on this engine**.
- [X] There is a confirmed by a trusted source solo DGX Spark node recipe somewhere on the internet for Qwen 3.8 Flash Next -- See if you can find it. **FOUND and ported two arms:** the SGLang cookbook's verified single-Spark cells (file-backed PLE) and the eugr registry's sparkrun-native solo recipe. The old "no TP=1 lane" conclusion had the wrong mechanism: the blocker is the ~47.7 GiB PLE table, not weights+KV.
- [X] If yes to either of the above, build and test the recipe upgrades. **2026-10-10: both solo arms built, BOOT-VERIFIED and W3-battery'd — SGLang route 38/38; vLLM route 38/38.** Operational constraint recorded: sparkrun model distribution to a node without the checkpoint fails at the 16 MiB safetensors-index inventory limit.
- [X] Select the best recipes from all lanes and move the rest to the @attic. **No move made — nothing is a clear loser.** The full ranking with provenance is now **tracked** at `recipes/qwen4/SELECTION-RANKING.md` (see below). NVIDIA arm went to attic with its boot verdict.
- [X] Run quality benchmarking pass. **W3 battery on both new solo arms: 38/38 each (n=1, saturated — cannot discriminate checkpoints).** Receipts: `~/benchmarks/qwen4-solo-20261010/`.
- [X] Update the appropriate README.md and AGENTS.md. *(Pre-existing item from the 2026-10-10 pass.)* **Closed 2026-10-12:** the lane docs already carry the solo arms — `recipes/qwen4/README.md` §"The TP=1 lane now exists" + its recipe table, `AGENTS.md` §10.5/§10.6 — no doc delta found in a review pass.
- [X] Commit a redacted tracked copy of `.local/SELECTION-RANKING-DRAFT.md` as `recipes/qwen4/SELECTION-RANKING.md`. *(Owner decision 2026-10-11.)* **DONE** (`d45f39c` + `1f17edd`): the snapshot plus a 2026-10-11 delta and a session-outcomes section covering every lane; addresses masked per the repo convention.

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
- [X] Research decision models and find high-quality, fast, low-memory candidates that can co-locate with other small models (such a an embed, rerank, and tts model). *(Owner decision 2026-10-11: leads named by the owner = Cloudflare/Clef and Jev distillations on HF; co-location with embed/rerank/tts is the core constraint; shortlist research was mine.)* **2026-10-11: DONE** — `recipes/decision/DECISION-MODELS-RESEARCH.md` (both owner leads resolved: Cloudflare/clef(-flash) open-weight Apache-2.0 on `/v1/systemone` under SGLang; "Jev distillations" = the `autotrust/JEV-*` distilled-student family, KL ≈ 0.019 receipts, native vLLM). Shortlist of 8 + co-location budget vs the shipped embed+rerank pair.
- [X] Build out the recipes. **2026-10-11: TWO recipes BOOT-VERIFIED.** `jev-9b-decision-vllm.yaml` (vLLM; `/v1/models` lists the base model **and** the `jev-decision` LoRA adapter, and the scoring path returns processed `top_logprobs`) and `clef-flash-decision-sglang.yaml` (digest-pinned `lmsysorg/sglang:dev-clef`; a real `/v1/systemone` round-trip with calibrated probabilities).
- [X] Build the next research-ranked candidate: `vllm-sr/Decision-2.0-Kai-0.6B` (+ the `Sol-2B` ladder arm) — the cheapest lane proof (4.9 ms, 1.4 GiB); costs a new runtime family (`vllm-srun`). **2026-10-13: BOTH BUILT AND BOOT-VERIFIED on `.34` (CPU, A725 pins).** `vllm-srun` ships inside the `vllm-sr` router image — `ghcr.io/vllm-project/semantic-router/vllm-sr` pinned by index digest `2c30eeb3…`, arm64 pull-verified (the plan's `model-runtime` image does not exist: 404 package; `vllm-srun` is not on PyPI); revisions are the runtime's own golden-checked pins (Kai `cd49ea38…`, Sol `64235bef…`). Boot blocker root-caused and fixed in-recipe: the image (python-slim) has no standalone `kill` binary, so sparkrun's `docker exec kill -0` liveness check exits 127 and misreports launch failure while the serve comes up healthy — the recipes install a bash-builtin kill shim and run as root. Kai TTR 8.1 s / HTTP-ready 10.1 s; Sol first-try; `/health` golden-ready; card-example `/v1/systemone` smokes pass on both. Lane doc: `recipes/decision/README.md` §"vllm-srun arms".
- [X] Run quality benchmarking pass. **2026-10-11: clef-flash DONE — official `tool-eval-bench` v2.8.0 `--decision-bench-only`: Decision Accuracy 70.3% (1406/2000)** on the Typed Decisions split, 400 cases in 81.5 s, zero request errors, ★★. **2026-10-12/13: the whole lane scored on the same instrument.** JEV-9B **67.0% (1340/2000), ★★, 0 errors** through the new `tools/jev-decision-bench.py` (the JEV-shaped harness this item asked for: card-verbatim `/v1/completions` System 1 contract, TEB-mirror metrics, `--selftest` exit 0; one request per question — comparability caveat recorded); Kai-0.6B **47.5% (949/2000), ★★** and Sol-2B **55.0% (1100/2000), ★★** via the tool itself (`--decision-bench-only` lives on the top-level parser; `--json-file` writes no file in v2.8.0 — the markdown report under `~/runs/` is the durable artifact, copied to receipts). Ladder: clef 70.3 > JEV 67.0 > Sol 55.0 > Kai 47.5. Receipts: `~/benchmarks/jev-decision-20261012/`, `~/benchmarks/kai-sol-20261012/`.
- [X] Select the best recipes from all lanes and move the rest to the @attic. **2026-10-11: no attic move — both recipes keep** (JEV-9B is the native-vLLM distilled student; clef-flash the only first-class SGLang decision model with a measured score).
- [X] Update the appropriate README.md and AGENTS.md. **2026-10-11:** `recipes/decision/README.md` (verified surfaces, the prefill-only scorer contract, the served-id wart, the co-location budget and core split) + root index rows.

## explore
Any model with reasoning and tool-calling capabilities
- [X] Research available models and find high-quality, fast, low-memory candidates that push the frontier. **2026-10-11: DONE** — `recipes/explore/EXPLORE-MODELS-RESEARCH.md` (8 families shortlisted; five claims in the Oct-10 `EXPLORE-CANDIDATES.md` corrected; top three = Nemotron-3.5-Lightning / Ling-3.0-flash / Kolibri-1).
- [X] Build out recipes. *(Owner decisions 2026-10-11: no recipe cap — build whatever fits the budget; emphasis follows the selection weighting.)* **2026-10-11: TWO recipes BOOT-VERIFIED, both measured.**
  - `nemotron-3.5-lightning-30b-nvfp4-dspark-vllm.yaml` — TP=1, **77.7 t/s @ d0** (σ 9.8, n=5), DSpark acceptance length 3.67 / 88.9% rate, house battery **33/37**. Below the third-party 93-96 t/s on this node, so quote ours.
  - `ling-3.0-flash-int4-dspark-sglang.yaml` — TP=1, **45.5 t/s @ d0** (σ 5.5, n=5), house battery **37/37** (ties the best in the pass). DSPARK engaged: steady-state accept len 3.64–3.73 under 4 concurrent generations (up to 116.7 t/s aggregate); the third-party ~83 t/s was NOT reproduced — the acceptance difference arithmetically accounts for most of the gap, and *why* theirs is higher is untested. The boot caveat is **resolved** (needle-probed 2026-10-11: the `rope_scaling` warning is benign, but 262k is not servable at the shipped mem-fraction — see the session follow-ons).
  - Three vLLM boot traps found and baked into the recipes (all documented in `recipes/README.md`): `executor_config.entrypoint: ""`, the spec config held in `defaults.speculative_config` (else the draft is never distributed), `--default-chat-template-kwargs '{"enable_thinking": false}'`.
- [X] Run quality benchmarking pass. **2026-10-11: both arms done** — Nemotron 33/37 (misses `wp-3`, `hard-arith-1/2`, `trick-3`), Ling 37/37.
- [X] Select the best recipes from all lanes and move the rest to the @attic. **2026-10-11: no attic move — both keep.** Ling is the quality/speed balance (37/37 at 45.5 t/s), Nemotron the speed arm (77.7 t/s at 33/37).
- [X] Update the appropriate README.md and AGENTS.md. **2026-10-11:** `recipes/explore/README.md` (both arms, measured + quality, the traps, the next candidates) + root index rows.
- [X] Next by the ranking: `Aleph-Alpha/Kolibri-1` **BUILT, BOOT-VERIFIED and MEASURED 2026-10-12 — kept.** `recipes/explore/kolibri-1-78b-fp8-vllm.yaml` on stock digest-pinned `vllm/vllm-openai:v0.29.0` + the vendor pure-Python plugin (`mods/install-kolibri-plugin`, fail-closed import/entry-point guard). KV 20.03 GiB → 1,961,775 tokens at 262k; chat round-trips verified both with and without thinking; C1 **47.3 t/s @ d0** (σ 0.10, n=5) / 46.3 @ d8k — 2.3× the stock-build floor 20.4, near the sm121 third-party 48; battery **36/37 @ `--max-tokens 4096`** (reproduced twice; 37/37 union with the default-384 run — the lone `needle-1` miss is thinking-budget truncation, and `--max-tokens` was added as an optional flag to `tools/quality-battery.py`, default 384, semantics unchanged). Keep rationale: accuracy-champion role at 1 node, not dominated (≥ Ling's 45.5). `vllm-sr/d3-edge` remains watch-only. Receipts: `~/benchmarks/kolibri-20261012/`.

## Session follow-ons (restated 2026-10-12)

- [X] **explore/Ling: 262k servability — RESOLVED 2026-10-12: 262k servable at `mem-fraction-static 0.80`; that rung SHIPPED.** Ladder first rung 0.80 booted clean on `.35`: `max_total_num_tokens=313,752` (0.75 measured 176,203; 0.85/0.87 rungs unneeded — 0.87 stays the documented ceiling). The 262k-window needle **PASS** at depths 10/50/90 (~256.6k server-counted tokens per prompt, the receipted 2026-10-11 probe instrument re-pointed at the new serve), and a 4-way concurrency smoke completed with zero OOM/retract events. Receipts: `~/benchmarks/ling-262k-20261012/`.
- [X] **explore/Nemotron: 1M-context arm — RESOLVED 2026-10-12: the card's 1M claim CONFIRMED on GB10.** `recipes/explore/nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm.yaml` (shipped recipe + exactly `max_model_len: 1000000`, `gpu_memory_utilization: 0.91`); vLLM did not refuse the window — KV 87.27 GiB → 21,344,213 tokens. 1M-window needle **PASS** at depths 10/50/90 (~982k server-counted tokens, Nemotron-calibrated 3.8590 chars/token; a first pass with Ling's 4.0546 ratio under-shot and is kept as the TRUNCATED receipt). Measured C1 **72.2 t/s @ d0** (σ 15.1, n=5) vs the 262k arm's 77.7. Swap caveat measured: ~1 GiB free + 2.05 GiB swap allocated during 1M prefills, zero swap-in/out under needle load; sustained multi-tenant load untested. The 262k/0.80 recipe remains the shipped default. Receipts: `~/benchmarks/nemotron-1m-20261012/`.
- [X] **explore/Nemotron: checklist leftovers** — CLOSED 2026-10-11 (`65ba1d7`, `1a234c4`): the `moe_backend: marlin` pin was found inert (an edit had dropped the `--moe-backend` line; sparkrun validation stays silent for a flag-map key the template omits) — restored; the verified boot ran `moe_backend='auto'` and vLLM auto-selected marlin anyway, so the numbers stand. `--tool-call-parser qwen3_coder` verified (forced `tool_choice` → structured `tool_calls`). The 1M-context claim was reclassified as a separate arm, not a checklist item.
- [X] **decision: a score for JEV-9B — RESOLVED 2026-10-12: Decision Accuracy 67.0% (1340/2000), ★★, 0 errors.** The JEV-shaped harness exists: `tools/jev-decision-bench.py` (stdlib-only, card-verbatim `/v1/completions` request + `z=(lp+bias)/T` softmax, TEB v2.8.0-mirror metrics, sha256 fail-closed case manifest, `--selftest` exit 0). Card-example smoke reproduced before scoring ({issue_warning 0.328, renegotiate 0.144, dual_source 0.528, maintain 0.001} vs card's ≈{0.33, 0.14, 0.53, 0.001}). Per kind: noul 79.3 / choice 67.2 / score 57.6. 132 ms median per decision (serial, one request per question); 3.3 pts behind clef's 70.3 on the shared instrument. Lane doc: `recipes/decision/README.md` §"JEV-9B official score". Receipts: `~/benchmarks/jev-decision-20261012/`.
- [ ] **glm5: boot-verify both TP4 recipes** — deferred to the next owner-announced TP=4 window; see the glm5 lane item.

## Session record

**2026-10-11 wrap (snapshot at 12:41 — superseded by the refresh below):** gate **384 tests OK** (skipped=1); all 23 shipped recipes validate plain; `bash -n` + `py_compile` clean. Independent audit of the day's recipe/mod/test changes: no blockers; all findings fixed (unconsumed `draft_model` removed, README typos, a negative control that proved nothing, stale `NOT boot-verified` prose in two recipe descriptions, raw node IPs masked to the `.34`/`.35` shorthand, plus a new `LiteralShaConsistency` guard). At that snapshot all work was committed and pushed.

**Landed after the wrap, same day (`882d463`–`0dfa881`):** the Ling needle probe and the Nemotron checklist closure folded into the lane docs; render-check fixes — the comment-inside-a-folded-command class and the inert-`defaults`-key class (which had shipped three times) are now guarded by `tests/test_recipe_placeholder_resolution.py`; the Nemotron `moe_backend` pin restored; coder-next `tensor_parallel` made to reach the command; glm inert defaults dropped.

**2026-10-12 refresh (verified in-tree):** gate re-run — **386 tests OK** (skipped=1), 23/23 recipes validate plain, `bash -n` + `py_compile` clean; working tree clean as of that check — this restatement is the only change on top of it (uncommitted as written). Push state before this edit: everything through 2026-10-11 is pushed, with one local-only commit, `5f3d83a` (README capability-icon row, 2026-10-12). The head node's registry clone sits at `9929e86` (2026-10-11 13:56) — its misses at writing are a guard test, recipe comment/doc edits, and that README row; run `sparkrun registry update littlecedar` before relying on the clone's shipped docs.

**2026-10-12 decision round (same day):** both open questions answered by the owner in-file and folded — next-window scope/budget into the preamble, the glm5 deferral into its lane item — and the `# Protocol` section added at the top of this file.

**2026-10-12/13 two-node completion pass:** all five remaining TP≤2 items closed on `.34`/`.35` in one
parallel two-queue round (`.34`: JEV + Kai/Sol; `.35`: Ling + Nemotron-1M + Kolibri). Ling 262k
servable at mem-fraction 0.80 (needle PASS, 4-way smoke clean); Nemotron 1M boots at the card's
0.91 and the 1M needle PASSES (C1 72.2); JEV scored **67.0% (1340/2000) ★★** with the new
`tools/jev-decision-bench.py`; Kai/Sol boot-verified on CPU and scored **47.5% / 55.0% ★★** via
tool-eval-bench v2.8.0; Kolibri-1 boot-verified + measured (47.3 t/s, battery 36/37 @4096, 37/37
union) and **kept**. One plan-fact correction: the `vllm-srun` runtime ships inside the
`vllm-sr` router image (no `model-runtime` image exists); its missing `kill` binary was root-caused
as the launch-failure misreport and fixed in-recipe. Receipts: `~/benchmarks/{ling-262k,
nemotron-1m,jev-decision,kai-sol,kolibri}-20261012/`. Production ds4 TP4 on `.30-.33` untouched
throughout; all six session serves stopped by explicit task ID. Gate re-run at integration (see the
next entry for numbers); commits per item, pushed, head registry clone updated.
