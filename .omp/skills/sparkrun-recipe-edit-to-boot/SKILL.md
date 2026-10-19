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

Schema rules as of sparkrun 0.4.0-alpha+g29f53fb (the installed build; the full 41-key reference is
`recipes/MECHANICS.md`):

- A `defaults:` value reaches the engine only through a `{placeholder}` in `command:` (or in another
  default, or `env:`), a runtime flag map / `BASE_CONSUMED_CONFIG_KEYS` key, or an internal
  (`_`-prefixed) / `overrides[].when.config` key. Anything else is dropped silently;
  `unmapped-config-key` is only a warning (`core/launcher.py:814-899`).
- An unknown **top-level** key is worse than a dead default: it is swept into `runtime_config`
  (`core/recipe.py:1264-1270`) and only a by-name consumer reads it. `recipe validate` gives
  `misplaced-config-key` (warning) when the runtime would have understood it under `defaults:`, else
  `unknown-top-level-key` (suggestion) — both easy to miss (`core/validation.py:1176-1272`).
- `name:` is ignored: the name is the filename stem (`core/recipe.py:1174-1175`), and declaring the
  key draws a deprecation warning (`core/validation.py:1512-1525`). `description:` must be top-level —
  `recipe list` and `recipe search` read only that form, so a nested one lists as empty
  (`core/recipe.py:2744`); `maintainer:` is metadata-only (`core/recipe.py:1261-1262`).
- `recipe_version` defaults to `"2"` (`core/recipe.py:1165`). `mode`, `solo_only`, and `cluster_only`
  are deprecated v1 topology spellings; use `min_nodes` / `max_nodes`
  (`core/validation.py:1371-1385`).
- `capabilities:` / `unsupported_capabilities:` are gateway declarations and are deliberately outside
  the workload fingerprint (`core/recipe.py:1272-1284`); editing them does not change identity.

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

0.4.0 changed what `{model}` means. On a launch with a prepared model, `bind_runtime_models` sets the
operation-local override `model` to the prepared in-container snapshot path
(`models/runtime.py:45-46`), so a template renders the **path**, not the repo id. `--revision` is no
longer stripped, and `{model_revision}` resolves to the prepared revision because operation overrides
outrank `defaults` in the chain (`models/runtime.py:40`; `core/recipe.py:1532-1538`). The pre-0.4 note
this section used to carry described the opposite behaviour; do not debug from memory of it.

`validate_runtime_command` (`models/runtime.py:80-99`) accepts a templated command that either:

- names the prepared path as a token, or as `--flag=<path>`, or
- names the declared repo id as a token **and** passes a revision flag with the prepared revision,
  space- or `=`-separated.

So both shapes boot:

```yaml
model_revision: <sha>
command: >
  vllm serve {model}
  --served-model-name {served_model_name}
```

```yaml
model_revision: <sha>
command: >
  vllm serve /cache/huggingface/hub/models--<org>--<name>/snapshots/<sha>
  --served-model-name <org>/<name>
  --revision=<sha>
```

The literal form must match the prepared path byte-for-byte; the repo guard
`LiteralShaConsistency` also requires every 40-hex token in the command to equal `model_revision`.
`serve command does not consume the validated model` now fires only when neither clause matches.

A dry run may still show the repo id, because bindings exist only when a prepared model is present;
the acceptance check remains a live `GET /v1/models`.

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
