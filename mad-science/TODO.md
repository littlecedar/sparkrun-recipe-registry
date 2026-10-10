# TODO list

Budget: 12 hours

Lane order:
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
- [X] Check if there's any updated models, quantizations, or runtime improvements that could improve accuracy and throughput. **2026-10-10: nothing directly usable for the TP=4 lane.** SGLang v0.5.21 shipped DSv4.1 fixes but the headline wins are SM100-only; vLLM v0.31.0's DSV4.1 stack defaults SM100; knapcio upstream moved well past our pin (v2.2/v2.3 throughput work + an explicit "do not use NVFP4 on GB10") — adopting it means an image rebuild, a separate decision. No new official checkpoint, no V4.2, no new draft head.
- [X] If yes to either of the above, build and test the recipe upgrades. **2026-10-10: the one candidate (gamma 5→2) was built and A/B-tested — REJECTED.** Same-window paired boots: γ=2 loses at C4/C8 (−5.3%/−2.9%), ties C1, +4.5% at C16. Shipped value stays 5; receipts and mechanism in `mods/dsv41-sglang-overlay/launcher.py` (DSPARK_BLOCK_SIZE comment).
- [X] Update the appropriate README.md and AGENTS.md. **2026-10-10:** README carries the needle/stability verification and the γ A/B caveat; the launcher comment holds the full γ write-up with receipts (commit `6cea1ed`).

## glm5
GLM 5.3
- [ ] Research this: https://github.com/bertholomus/glm-5.3-tensorfold-tp4-4xgb10
- [ ] Research this: https://github.com/bertholomus/glm-5.3-flash-nvfp4-gb10-tp4
- [ ] Update the recipe research
- [ ] Build out the recipes.
- [ ] Run quality benchmarking pass.
- [ ] Select the best recipes from all lanes and move the rest to the @attic.
- [ ] Update the appropriate README.md and AGENTS.md.

## ornith
Ornith 1.5
- [ ] Check if there's any updated models, quantizations, or runtime improvements that could improve accuracy and throughput.
- [ ] If yes to the above, build and test the recipe upgrades.
- [ ] Run quality benchmarking pass.
- [ ] Update the appropriate README.md and AGENTS.md.

## qwen3
Qwen 3.x
- [ ] Check if there's any updated models, quantizations, or runtime improvements that could improve accuracy and throughput.
- [ ] If yes to the above, build and test the recipe upgrades.
- [ ] Finish building and testing the recipes.
- [ ] Select the best recipes from all lanes and move the rest to the @attic.
- [ ] Run quality benchmarking pass.
- [ ] Clean up directory and artifacts.
- [ ] Update the appropriate README.md and AGENTS.md.

## qwen4
Qwen 4.x (and 3.8 Flash Next)
- [X] Check if there's any updated models, quantizations, or runtime improvements that could improve accuracy and throughput. **2026-10-10:** RadixArk Flash-Next unchanged since 26 Aug; Qwen4 itself still in training (no weights); NVIDIA's official NVFP4 quant is an accuracy-candidate arm (blazux head-to-head winner, archived in attic pending a boot); labquant main moved to step-5500 QAD (accuracy candidate, breaks the pinned 7-mod chain until re-verified); three proven TP=1 routes reopen the solo lane.
- [X] There is a confirmed by a trusted source solo DGX Spark node recipe somewhere on the internet for Qwen 3.8 Flash Next -- See if you can find it. **FOUND and ported two arms:** the SGLang cookbook's verified single-Spark cells (file-backed PLE) and the eugr registry's sparkrun-native solo recipe, plus hashd1ve/blazux/MiaAI third-party routes. The old "no TP=1 lane" conclusion had the wrong mechanism: the blocker is the ~47.7 GiB PLE table, not weights+KV.
- [X] If yes to either of the above, build and test the recipe upgrades. **2026-10-10: both solo arms built, BOOT-VERIFIED and W3-battery'd — SGLang route (pinned cookbook image, RadixArk checkpoint) 38/38; vLLM route (eugr port; local-inference-lab at main = step-5500 QAD) 38/38.** Operational constraint recorded: sparkrun model distribution to a node without the checkpoint fails at the 16 MiB safetensors-index inventory limit — serve on a node that holds it or set `distribution.model.file_selection: all` on the cluster.
- [ ] Select the best recipes from all lanes and move the rest to the @attic.
- [ ] Run quality benchmarking pass.
- [ ] Update the appropriate README.md and AGENTS.md.

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
- [ ] Research decision models and find high-quality, fast, low-memory candidates that can co-locate with other small models (such a an embed, rerank, and tts model)
- [ ] Build out the recipes.
- [ ] Run quality benchmarking pass.
- [ ] Select the best recipes from all lanes and move the rest to the @attic.
- [ ] Update the appropriate README.md and AGENTS.md.

## explore
Any model with reasoning and tool-calling capabilities
- [ ] Research available models and find high-quality, fast, low-memory candidates that push the frontier.
- [ ] Build out up to 10 recipes.
- [ ] Run quality benchmarking pass.
- [ ] Select the best recipes from all lanes and move the rest to the @attic.
- [ ] Update the appropriate README.md and AGENTS.md.
