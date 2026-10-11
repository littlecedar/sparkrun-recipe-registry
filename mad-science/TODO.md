# DECISIONS — locked 2026-10-11 (questionnaire answered)

1. **Order/budget**: the lane order is advisory, not priority — any rational order; the 12 h budget stands. No lane is out of scope.
2. **Nodes**: both .NN and .NN are ours for the session; paired A/B boots on both are fine.
3. **glm5 images**: option (a) — attempt to build/verify a pinnable image for the Flash vLLM lane. For the EXL3 lane, no existing builds of `glm-dsa-tp4` are known → resolved by #13 (attempt a source build).
4. **DFlash2 license**: use the DFlash2 drafts — non-commercial cluster use satisfies CC BY-NC-ND (owner confirmed 2026-10-11, resolving the (a)/(b) label mismatch).
5. **qwen3 coder-next**: option (a) — measure it on a free node before the keep/de-ship call.
6. **qwen4 ranking doc**: commit a redacted tracked copy (e.g. `recipes/qwen4/SELECTION-RANKING.md`).
7. **ornith lead**: spend node time this session on the DFlash2 author's 114.2 t/s reference config A/B.
8. **Battery**: one shared stdlib battery tool for all lanes; survey existing standard benchmarks first — standard suites are preferred wherever they fit.
9. **decision lane**: the shortlist is mine to research; leads named by owner = Cloudflare/Clef and Jev distillations on HF. Nodes are at a premium → co-location with embed/rerank/tts is the core constraint.
10. **explore lane**: the 10-recipe cap is removed; emphasis follows the selection weighting.
11. **Weighting**: confirmed — node count > speed > accuracy > memory footprint.
12. **Attic**: moves only if warranted, folded into each lane's quality/selection pass — not a global end-of-session sweep.
13. **glm5 EXL3**: attempt a `glm-dsa-tp4` source build this session, budget-permitting, before Flash-lane work.
14. **explore cap**: none — build whatever fits the 12 h budget.
15. **Battery sources**: standard-first — RESOLVED 2026-10-11 by survey: **adopt `tool-eval-bench` as the shared suite via `sparkrun benchmark tools`** (already a registered sparkrun framework; covers tool-calling, GSM8K/MMLU/IFEval, needle, spec-decode metrics, and a decision-model benchmark on the Typed Decisions split), **promote `recipes/ds4/benchmarks/` as the shared hard tier** (ifm already scores with it), and keep only the four stdlib instruments nothing standard reaches (`quality-battery.py`, `qwen4-quality-eval.py`, `pooling-bench.py`, `gate-37111.py`; `needle-haystack.py` stays as the client). **No new battery tool is built.** Full survey receipt: agent://BenchmarkSurvey (2026-10-11).

# TODO list

Budget: 12 hours

WOPR sparkrun cluster nodes available for testing and benchmarking:
- .NN
- .NN

Lane order (advisory — any rational order, decisions #1):
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

## glm5
GLM 5.3
- [X] Research this: https://github.com/bertholomus/glm-5.3-tensorfold-tp4-4xgb10 — full assessment in the rewritten `recipes/glm/GLM-5.3-RECOMMENDATIONS.md` (repo A = runnable EXL3 3.0bpw TP4 recipe, 82 t/s aggregate measured, engine on the unreleased `glm-dsa-tp4` branch).
- [X] Research this: https://github.com/bertholomus/glm-5.3-flash-nvfp4-gb10-tp4 — repo B = validation/evidence package for GLM-5.3-Flash NVFP4 (qualified receipts, KV ladder, DFlash2 CC BY-NC-ND trap).
- [X] Update the recipe research — `recipes/glm/GLM-5.3-RECOMMENDATIONS.md` rewritten 2026-10-10: three refuted claims fixed (sizes ~3.2× off; no single-node fit; RadixArk mischaracterised), both model lines + four checkpoints + three engines + spec-decode + KV math covered.
- [X] Build out the recipes. **2026-10-11, done as far as this session can reach:**
  - **Flash image blocker RESOLVED:** `vllm/vllm-openai:glm53-flash` EXISTS on Docker Hub (pushed 2026-09-09; 8.7 GB). Pin = the digest docker resolved on a runner node, `sha256:819ec9c063412e5730d1b0e82046ba540d1bf991f3c4f661a849aae8a0c52374` (manifest-list digest; the Hub API's amd64-image digest `sha256:0674a3ea…` is inside it). Device-free engine inspection of that build (0.28.1rc1.dev580): `glm45`/`glm47` parsers registered, `method: dflash` native, Glm5Next*/GlmMoeDsa* arch classes present, `--moe-backend` is the flag this build wants.
  - **Recipe drafted:** `recipes/glm/glm-5.3-flash-nvfp4-dflash-vllm.yaml` (commit `c2b7be8`) — repo B's runtime-formula.json verbatim, checkpoint pinned to `36c184c6` (169B params, arch `Glm5NextForConditionalGeneration`). NOT boot-verified: TP4 needs 4 nodes, this session has 2 free.
  - **EXL3 "source build" resolved as no-build:** the engine is `bertholomus/TensorFold@glm-dsa-tp4` installed editable into `nvcr.io/nvidia/pytorch:26.07-py3` at container start (`tfrun.sh`) — no image exists to build. Engine branch cloned on the head run dir at exactly `ddfad35`. TP4 boot also needs 4 nodes → queued with the Flash boot for a 4-node window.
- [ ] Boot-verify both glm5 recipes when a 4-node window opens (Flash TP4 + EXL3 TensorFold TP4 via `scripts/tfrun.sh` in repo A's work dir).
- [X] DFlash2 draft usability: RESOLVED 2026-10-11 — use the DFlash2 drafts (non-commercial cluster use satisfies CC BY-NC-ND); the Flash spec-decode route may be built.
- [ ] Run quality benchmarking pass.
- [ ] Select the best recipes from all lanes and move the rest to the @attic.
- [ ] Update the appropriate README.md and AGENTS.md.

## ornith
Ornith 1.5
- [X] Check if there's any updated models, quantizations, or runtime improvements that could improve accuracy and throughput. **2026-10-10: nothing superseding** (scan recorded in `recipes/ornith/README.md`): ornith-ai quiet since 2026-08-29, jzinno DFlash2 unchanged; an SGLang 0.5.21 bump BREAKS the 35B serve line (Mamba/SWA radix-cache args removed upstream); one untested lead = the DFlash2 author's 114.2 t/s reference config (multi-knob confound, needs a same-node A/B).
  - **Operational fact (2026-10-11): `@littlecedar/<name>` resolves from the registry CLONE** at `~/.cache/sparkrun/registries/littlecedar` (registries.yaml → GitHub URL), not the local tree — local edits are invisible to cluster launches until pushed + `sparkrun registry update littlecedar`. The first control boot ran the pre-session recipe (upstream template, no pin) for exactly this reason; its numbers (106.8/97.5 t/s) are still a valid throughput control for the A/B (the clone recipe was identical modulo template), but the remaining ladder arms re-run against the pushed recipe so the honed template ships in every arm.
  - **Distribution-blocking incident (2026-10-11, fixed):** the runner caches' ornith `chat_template.jinja` was honed in place in September and sparkrun's model-preparation validator now rejects it against hub metadata (`wrong_size`) — every launch died at distribution. Fixed by restoring hub content in the caches and shipping the honed template via `@littlecedar/mods/ornith-honed-chat-template` + `--chat-template` (commit `2374fd7`, guards in `tests/test_ornith_honed_chat_template.py`, gate 379 tests OK). The checkpoint is now revision-pinned (`94e431d9` + `--revision`, commit `294e42a`).
- [X] If yes to the above, build and test the recipe upgrades. **No — nothing superseding, no upgrade built.** The lane ships unchanged.
- [X] Build testing and benchmarking battery tooling. **RESOLVED 2026-10-11 (survey + decision #15): no new tool.** `tool-eval-bench` verified installed on the head node (`uvx tool-eval-bench` resolves; `sparkrun benchmark tools` exists in the installed CLI) — first live run happens inside each lane's quality pass below. The four stdlib instruments nothing standard reaches stay as-is.
- [X] A/B the DFlash2 author's 114.2 t/s reference config same-node (multi-knob confound). **2026-10-11: CLOSED as a negative result with receipts — no knob is distinguishable from boot noise; the shipped config stands.** Ladder (d0 t/s): control 106.8 (old recipe) / 99.3 (honed control-2) / ① draft10 86.5 / ② marlin 108.9 and 103.4 (repeat) / ③ extra_buffer 103.2 / ④ float32 90.4 / ⑤ full author 84.6. Same-config spread on the node is 7.5% (106.8 vs 99.3); marlin's two runs straddle it, so it is not a win; the losers (① ⑤ ④) are outside the noise. One confirm cell was **voided**: the .35 boot lost spec decode (30.8 t/s) and was OOM-`Killed` — a memory-starved node, not a recipe cell. Files: `~/benchmarks/ornith-dflash2-ab-20261011/`; write-up in `recipes/ornith/README.md`.
- [ ] Run quality benchmarking pass. **Not run — the A/B above is throughput plus knobs only.** Queued: one ornith boot + `tools/quality-battery.py` so the lane has a quality number (the decision/explore lanes and the qwen3 pair already have theirs).
- [X] Update the appropriate README.md/AGENTS.md. **2026-10-11:** `recipes/ornith/README.md` carries the ladder table, the confirm/void analysis, the honed-template delivery story, and the revision pin. The lane has no `AGENTS.md` (unchanged); root index row unchanged (no config change).

## qwen3
Qwen 3.x
- [X] Check if there's any updated models, quantizations, or runtime improvements that could improve accuracy and throughput. **2026-10-10: checkpoint + DFlash2 draft unchanged; the headline is the NEW DSpark v2 draft** (SpecForge-trained for our exact NVFP4 target, card: +26% acceptance, beats EAGLE — on GB300/H200).
- [X] If yes to the above, build and test the recipe upgrades. **Built and measured — NOT an upgrade:** `qwen3.8-27b-nvfp4-dspark-sglang.yaml` boots (DSPARK path works on GB10) but measures 28.5 t/s vs DFlash2's 33.8 on the same decode-triage profile — a ~16% loss. Receipts in the recipe comment; the DFlash2 lane stays shipping.
- [X] Finish building and testing the recipes. The lane ships 4 recipes: DFlash2 (shipping, 33.8 t/s), nospec-control (12.6, control-only), DSpark arm (28.5, measured reference), coder-next (unmeasured — see the selection note).
- [ ] Select the best recipes from all lanes and move the rest to the @attic. **No move made — nothing is a clear loser.** 
- [ ] Measure `qwen3-coder-next-int4-autoround-vllm.yaml` (tracked, zero measured numbers anywhere). **2026-10-11 owner decision #5: measure before the keep/de-ship call.**
- [ ] Run quality benchmarking pass. **Not run: no battery tooling for this lane.** The C1 index figure (50) vs the lane's 33.8 conflict is SURFACED, not resolved — the index and the lane doc measure different windows.
- [ ] Clean up directory and artifacts. Nothing to clean: the lane dir holds shipped recipes + evidence docs; the untracked WIP docs are the second writer's.
- [X] Update the appropriate README.md and AGENTS.md. Lane README carries the DSpark row with the measured verdict; root index updated.

## qwen4
Qwen 4.x (and 3.8 Flash Next)
- [X] Check if there's any updated models, quantizations, or runtime improvements that could improve accuracy and throughput. **2026-10-10:** the labquant upgrade candidate (step-5500 QAD at main `6c01ac37`) has a **complete per-mod re-verification plan** — `attic/qwen4/status/W14-LABQUANT-5500-MOD-PLAN.md`: one mod breaks (fail-closed, fix direction known), one is obsolete (drop it), five survive; not built tonight (fail-closed mod surgery deserves fresh budget). NVIDIA's official NVFP4 quant: boot-answered **REJECTED on this engine** (per-layer quant map refused by the pinned SGLang loader; needs an engine patch or a vLLM route).
- [X] There is a confirmed by a trusted source solo DGX Spark node recipe somewhere on the internet for Qwen 3.8 Flash Next -- See if you can find it. **FOUND and ported two arms:** the SGLang cookbook's verified single-Spark cells (file-backed PLE) and the eugr registry's sparkrun-native solo recipe, plus hashd1ve/blazux/MiaAI third-party routes. The old "no TP=1 lane" conclusion had the wrong mechanism: the blocker is the ~47.7 GiB PLE table, not weights+KV.
- [X] If yes to either of the above, build and test the recipe upgrades. **2026-10-10: both solo arms built, BOOT-VERIFIED and W3-battery'd — SGLang route (pinned cookbook image, RadixArk checkpoint) 38/38; vLLM route (eugr port; local-inference-lab at main = step-5500 QAD) 38/38.** Operational constraint recorded: sparkrun model distribution to a node without the checkpoint fails at the 16 MiB safetensors-index inventory limit — serve on a node that holds it or set `distribution.model.file_selection: all` on the cluster.
- [X] Select the best recipes from all lanes and move the rest to the @attic. **No move made — nothing is a clear loser.** The full ranking with provenance is in `.local/SELECTION-RANKING-DRAFT.md` (git-ignored; ask for a tracked copy). NVIDIA arm went to attic with its boot verdict; all shipped arms are measured or role-separated.
- [X] Run quality benchmarking pass. **W3 battery on both new solo arms: 38/38 each (n=1, saturated — cannot discriminate checkpoints).** Receipts: `~/benchmarks/qwen4-solo-20261010/`.
- [ ] Update the appropriate README.md and AGENTS.md.
- [ ] Commit a redacted tracked copy of `.local/SELECTION-RANKING-DRAFT.md` as `recipes/qwen4/SELECTION-RANKING.md` (2026-10-11 decision #6). Mask internal addresses per the repo addressing convention.

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
- [X] Research decision models and find high-quality, fast, low-memory candidates that can co-locate with other small models (such a an embed, rerank, and tts model). **2026-10-11: DONE** — full report committed at `recipes/decision/DECISION-MODELS-RESEARCH.md` (both owner leads resolved: Cloudflare/clef(-flash) open-weight Apache-2.0 on `/v1/systemone` under SGLang; "Jev distillations" = the `autotrust/JEV-*` distilled-student family, KL ≈ 0.019 receipts, native vLLM). Shortlist of 8 + co-location budget vs the shipped embed+rerank pair.
- [ ] Build out the recipes. **2026-10-11: first recipe BOOT-VERIFIED** — `recipes/decision/jev-9b-decision-vllm.yaml` (commit `3ede10f`, then entrypoint + snapshot-path fixes): serves on one node, `/v1/models` lists `autotrust/JEV-9B` **and** the `jev-decision` LoRA adapter, and the scoring path returns processed `top_logprobs` (measured on .34). Received: `--logprobs-mode processed_logprobs` + `--enable-lora` + `--max-lora-rank 32` all accepted by the pinned image. Not yet exercised: a full `allowed_token_ids`-constrained decision round-trip (`allowed_token_ids` was rejected as a top-level chat field in this build — needs the card's exact request shape or the SystemOne path) and the `tool-eval-bench` decision plugin (its probe passes; the plugin's bench mode is keyed to a SystemOne endpoint). Next: clef-flash (SGLang route) and Decision-2.0-Kai-0.6B.
- [ ] Run quality benchmarking pass.
- [ ] Select the best recipes from all lanes and move the rest to the @attic.
- [ ] Update the appropriate README.md and AGENTS.md.

## explore
Any model with reasoning and tool-calling capabilities
- [X] Research available models and find high-quality, fast, low-memory candidates that push the frontier. **2026-10-11: DONE** — committed at `recipes/explore/EXPLORE-MODELS-RESEARCH.md` (8 families shortlisted; five claims in the Oct-10 `EXPLORE-CANDIDATES.md` corrected; top three = Nemotron-3.5-Lightning / Ling-3.0-flash / Kolibri-1).
- [ ] Build out recipes. **2026-10-11 decision #10: no recipe cap; build whatever fits the budget; emphasis follows the selection weighting.** First recipe **BOOT-VERIFIED** — `recipes/explore/nemotron-3.5-lightning-30b-nvfp4-dspark-vllm.yaml`: serves on one node (TP=1), and the DSpark draft engages — **acceptance length 3.67, acceptance rate 88.9%** (live decode-batch log). Three boot lessons baked in as fixes: `executor_config.entrypoint: ""` (the vLLM image's ENTRYPOINT), the spec config held in `defaults.speculative_config` (else the draft is never distributed), and `--default-chat-template-kwargs '{"enable_thinking": false}'` (short replies otherwise land in the reasoning channel with `content: null`). Standard-profile bench running; quality pass next.
- [ ] Run quality benchmarking pass.
- [ ] Select the best recipes from all lanes and move the rest to the @attic.
- [ ] Update the appropriate README.md and AGENTS.md.
