# TODO list

## ds4
DeepSeek V4.1
- [X] TP=2 recipe vision head yes or no? no 
- [X] Can it be enabled? yes
- [X] Run a harder image set to quantify the VL-bias effect
- [X] Engram Table builder directly from HF instead of depending on the full model weights present in the local HF cache.
- [ ] TP=2 needle-haystack test
- [ ] TP=2 stability test since it seems to collapse into looping output while reasoning quite often -- Is there anything that can be done to improve it?
- [ ] Is there anything useful in https://github.com/bertholomus/deepseek-v4.1-flash-dspark-tp4-4xgb10 for our TP=4 recipe?
- [ ] Check if there's any updated models, quantizations, or runtime improvements that could improve accuracy and throughput.
- [ ] If yes to either of the above, build and test the recipe upgrades.
- [ ] Update the appropriate README.md and AGENTS.md.

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
- [ ] Check if there's any updated models, quantizations, or runtime improvements that could improve accuracy and throughput.
- [ ] TP=1 flash next recipe is out there for us to figure out
- [ ] If yes to either of the above, build and test the recipe upgrades.
- [ ] Select the best recipes from all lanes and move the rest to the @attic.
- [ ] Run quality benchmarking pass.
- [ ] Update the appropriate README.md and AGENTS.md.

## embed
Any embed model
- [ ] Move all embedding recipes to @recipes/embed
- [ ] Update the appropriate README.md and AGENTS.md.

## rerank
Any rerank model
- [ ] Move all rerank recipes to @recipes/rerank
- [ ] Update the appropriate README.md and AGENTS.md.

## decision
Any decision model
- [ ] Research decision models and find high-quality, fast, low-memory candidates that can co-locate with other small models (such a an embed, rerank, and tts model)
- [ ] Build out the recipes.
- [ ] Run quality benchmarking pass.
- [ ] Select the best recipes from all lanes and move the rest to the @attic.
- [ ] Update the appropriate README.md and AGENTS.md.

