---
name: sparkrun-recipe-edit-to-boot
description: "Use when editing sparkrun recipes/mods and measuring lanes on the DGX Spark cluster: registry-clone staleness, placeholder/default traps, reasoning-channel empty content, A/B ladder hygiene."
---

# sparkrun: from recipe edit to a trustworthy measurement

Every step below exists because skipping it produced a plausible wrong answer or a
boot that died silently. Order matters.

## 1. Make the edit reach the cluster

Recipes resolve from the registry **clone**, not the working tree:

```sh
# the tree you edit is NOT what @littlecedar/<name> loads
cd ~/.cache/sparkrun/registries/littlecedar && git log --oneline -1
```

Loop: edit → `git add <explicit path>` → commit → `git push origin main` →
`sparkrun registry update littlecedar` → confirm the clone's md5 matches.
Do not benchmark an edit that has not been pushed; an md5 match against the head
tree proves nothing.

## 2. Check what validate cannot see

`sparkrun recipe validate` passes on:

- a `{placeholder}` whose `defaults:` key was deleted — it renders as the literal
  and dies at the engine (`Unknown speculative algorithm name: {SPECULATIVE_ALGORITHM}`).
  `uv run python -B -m unittest tests.test_recipe_placeholder_resolution` guards this;
  run it after any recipe edit, and re-read neighbouring keys after cutting comments.
- a model arg that the runtime will rewrite later (see §4).

## 3. Watch the distribution gate

Model preparation validates every cached file against a manifest built from hub
metadata. If a runner cache was hand-modified (e.g. a chat template honed in place),
validation fails `wrong_size` **before** mods run, and "one repair" re-copies the same
divergent files. Restore hub content in the cache and deliver the customisation
through a mod + an engine flag (worked example: `recipes/ornith/mods/ornith-honed-chat-template`
stages a template for sglang's `--chat-template`, which accepts a file path).

## 4. Custom command templates on vLLM

sparkrun's vLLM runtime rewrites the model argument to the declared repo id and strips
`--revision` from templates, then its own validator demands a path or a revision token.
Only the equals form survives:

```yaml
command: >
  vllm serve <repo-id>
  --revision=<prepared-sha>
```

Check the flag surface of a pinned image without a GPU:
`docker run --rm --entrypoint bash -v script.sh:/s:ro <img> /s` — arg parsers need a
device to build, so grep the installed package (`vllm/tool_parsers/__init__.py`,
`reasoning/__init__.py`, `model_executor/models/registry.py`) instead.

## 5. Reasoning models: content vs reasoning channel

With a reasoning parser active, short answers land in `reasoning` and `content` stays
`null`; a content-reading harness scores 0/N on empty strings while `/v1/completions`
is correct. Ship `--default-chat-template-kwargs '{"enable_thinking": false}'` and let
callers opt in per request. Record the `finish_reason`/`reasoning` histogram beside any
score.

## 6. Run a same-node ladder

```sh
# control first, then ONE knob per arm, same node, same profile
sparkrun benchmark performance @littlecedar/<recipe> -H <node> \
  --profile benchmarking/decode-triage.yaml \
  --output ~/benchmarks/<campaign>/<arm>.yaml --fresh
```

- Each cell emits a decode row AND a prefill row, both with `tg_throughput`; filter
  `is_context_prefill_phase`, and read `context_size` for depth.
- Inter-boot noise is 7-25% on this hardware: a single arm beating control by <10% is
  not a result — repeat it paired before shipping the knob.
- Bump `num_draft_tokens` up only with a paired measurement; a draft author's wider
  block lost ~19% here.

## 7. Quality pass

Prefer standard suites: `sparkrun benchmark tools` (`tool-eval-bench`) for tool-calling/
GSM8K/MMLU/IFEval, `recipes/ds4/benchmarks/` for the hard tier, `tools/quality-battery.py`
for the cheap shared tripwire (it reads `content` — see §5). Keep `tools/` and `tests/`
stdlib-only; external suites run as pinned external processes.

## 8. Record

Lane README row + root `README.md` index row + the number's provenance
(command, profile, node, date, n). A recipe is not shipped until a boot backs it; a
number without its bench/config provenance does not go in a table.
