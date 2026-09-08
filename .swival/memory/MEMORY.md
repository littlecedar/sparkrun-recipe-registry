# Memory — Little Cedar sparkrun recipe review

Durable conventions learned while reviewing `experimental-recipes/littlecedar/` recipes.

## Recipe authoring / review conventions

- The cache-clearing mod is `drop-caches` (has a `p`, no `s`). Docs that say `drops-caches` (e.g. parts of AGENTS.md, the qwen3.8-flash-next-nvfp4 spec) are WRONG. Actual recipes use `- drop-caches` / `- mods/drop-caches`.
- The parallel-pip env var is `MAX_JOBS` (siblings set `MAX_JOBS: 2`), NOT `JOBS`. `JOBS` is the wrong key.
- The MTP sibling recipe names the draft dtype `model_mtp_dtype: bfp16` (note `bfp16`, not `bf16`). A draft spec's `model_draft_dtype` field name does not match — confirm the real field name before authoring.
- In vLLM recipes, `defaults.load_format` is `instanttensor` (the draft loader). Do NOT hardcode `--load-format fastsafetensors` in the command — that contradicts the default and the draft-loader flow. Use `--load-format {load_format}`.
- Two MTP flag styles exist across siblings: (a) JSON `--speculative-config '{...mtp...}'` + `--enable-expert-parallel` (used by the 397B MTP recipe), and (b) short-form `--spec-method mtp --spec-tokens N` (used by the 35B b12x recipes). MTP uses the model's own MTP experts, so a separate `--spec-model-path` is likely unnecessary for pure MTP.
- Mod refs are ambiguous: bare names resolve under the experimental-mods mount, path refs (`mods/...`) resolve literally. Verify each ref resolves; don't assume `drop-caches` and `mods/drop-caches` are interchangeable across registries.
- Mod name spelling and env-var keys are the two most likely silent breakers to catch in a review. See detailed findings below.

See `specs/qwen3-8-flash-next-nvfp4-review.md` for the full per-line review of that spec.
