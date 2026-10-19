---
name: sparkrun-recipe-launch-debugging
description: "Use when a sparkrun recipe launch on the DGX Spark cluster fails or measures the wrong thing: distribution validation errors, serve-command validation refusal, unresolved placeholders, silent empty replies, wrong advertised model id, or edits that appear to have no effect."
---

Diagnostic ladder for `sparkrun run` / `sparkrun benchmark performance` failures on the sparkrun-recipe-registry cluster. Each rung cost a session to find once; check them in order.

## Schema facts that decide the diagnosis (sparkrun 0.4.0)

Verified against the installed `sparkrun 0.4.0-alpha+g29f53fb`; full key rules in
`recipes/MECHANICS.md`.

- `{model}` in a `command:` template renders the **prepared in-container snapshot path** on a real
  launch (`models/runtime.py:45-46`). Bindings exist only when a prepared model is present, so a dry
  run can still print the repo id.
- `--revision` is not stripped from a template, and `{model_revision}` renders the prepared revision
  when the recipe pins one (`models/runtime.py:40`; chain precedence `core/recipe.py:1532-1538`).
- A `defaults:` value reaches the engine only through a `{placeholder}`, a runtime flag map /
  `BASE_CONSUMED_CONFIG_KEYS` key, or an internal (`_`-prefixed) / `overrides[].when.config` key.
  Anything else is dropped; the only diagnostic is the `unmapped-config-key` warning
  (`core/launcher.py:814-899`).
- An unknown top-level key is swept into `runtime_config` (`core/recipe.py:1264-1270`), where it does
  nothing unless a consumer reads it by name. `misplaced-config-key` (warning) and
  `unknown-top-level-key` (suggestion) are the only reports (`core/validation.py:1176-1272`).
- The recipe name is the filename stem (`core/recipe.py:1174-1175`); `description:` must be
  top-level (`core/recipe.py:2744`), `maintainer:` is metadata-only (`core/recipe.py:1261-1262`),
  `recipe_version` defaults to `"2"` (`core/recipe.py:1165`), and `mode` / `solo_only` /
  `cluster_only` are deprecated (`core/validation.py:1370-1385`).

## 0. Did your edit even reach the cluster?

`@littlecedar/<name>` resolves from the **registry clone** at `~/.cache/sparkrun/registries/littlecedar` (registries.yaml points at the GitHub URL), NOT from the syncthing-shared tree at `${WOPR_SRC_DIR}`. If a recipe edit seems inert, md5-checking the working tree proves nothing.

```bash
git push origin main
ssh <head> 'HOME=~ sparkrun registry update littlecedar'
ssh <head> 'cd ~/.cache/sparkrun/registries/littlecedar && git log --oneline -1 && md5sum <recipe>'
```

To trial an unpushed edit without pushing: symlink it into `/home/<operator>/development` and run the local file (`cd /home/<operator>/development && sparkrun run ./<recipe>.yaml -H <node> --transfer-mode local`).

## 1. Model distribution fails: `wrong_size` / "still invalid after one repair"

sparkrun validates every cached model file against a manifest built from **hub metadata**. Symptoms: `chat_template.jinja: wrong_size`, and "one repair" re-copies the same divergent files from the head host, failing identically.

- Locate the manifest: `~/.cache/huggingface/.sparkrun-model-artifacts/*.json` (hash-named; `python3 -c` grep for the repo id and print `revision` + file sizes).
- Compare manifest sizes to what the cache actually holds, then to what the hub serves **at that revision**: `curl -sL https://huggingface.co/<repo>/raw/<sha>/<file> | wc -c`.
- If someone hand-modified the snapshot (tell-tale: `.bak` / `.dist` siblings beside a symlink), the caches and hub disagree permanently. Restore hub content in the caches and deliver the customisation by **mod + flag**, never by writing into the snapshot.

## 2. Launch refuses: "serve command does not consume the validated model"

vLLM only, template `command:` only (sglang is unaffected). What 0.4.0 actually does:
`bind_runtime_models` writes `model` = the prepared in-container snapshot path and
`model_revision` = the prepared revision as **operation overrides**, so `{model}` renders the path and
`{model_revision}` renders the prepared SHA (`models/runtime.py:40-46`). It does not strip the
template's flags.

`validate_runtime_command` (`models/runtime.py:80-99`) then accepts either a token equal to the
prepared path (also as `--flag=<path>`), or the declared repo id as a token **plus** a revision flag
carrying the prepared revision. When neither holds it raises this error, after the model has already
been distributed.

Fix patterns (both pass the launcher's artifact check; the literal shape is the boot-proven one in
this repo):

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

The literal path must equal the prepared path exactly. A recipe that mixes a literal path with a
stale `--revision=<sha>` still fails, because the validator compares against the prepared revision;
`tests/test_recipe_placeholder_resolution.py::LiteralShaConsistency` keeps every 40-hex token equal to
`model_revision`.

To see the exact rendered command, monkeypatch and run the launch in-process:

```python
import sparkrun.models.runtime as rt
orig = rt.validate_runtime_command
rt.validate_runtime_command = lambda recipe, overrides, runtime, command: (
    print("prepared:", overrides.get("_prepared_model_path")),
    print("prepared rev:", overrides.get("_prepared_model_revision")),
    print("cmd:", command[:300]), orig(recipe, overrides, runtime, command))[2]
# then set sys.argv and call sparkrun.application.main()
```

Related: `--speculative-config` field is `"model"` (sparkrun's draft detection reads that key and adds
the draft repo with its **own** `revision` — `runtimes/_vllm_common.py:356-374`); `"draft_model"`
leaves the drafter undistributed and absent from the offline engine's path. The JSON must live in
`defaults:`, because an inline command literal never reaches the config chain that binds it
(`models/runtime.py:70-77`).

## 3. Serve dies instantly after "Executing serve command: done"

Read the in-container serve log; the orchestration log never shows it:

```bash
ssh <node> 'C=$(docker ps -q | head -1); docker cp $C:/tmp/sparkrun_serve.log /tmp/s.log; cat /tmp/s.log'
ssh <node> "docker cp $C:/tmp/sparkrun_serve.sh /tmp/s.sh; grep -oE 'taskset.*' /tmp/s.sh"
```

`Unknown speculative algorithm name: {SPECULATIVE_ALGORITHM}` means a `defaults:` key referenced by the command is missing: **the unresolved literal flows into the serve line verbatim, and `sparkrun recipe validate` passes anyway.** Every `{token}` in a `command:` must exist in `defaults:` or be one sparkrun injects: `{model}` (the prepared path on a launch), `{model_revision}` (only when the recipe pins one), `{resolved_model_path}` (pre-placed weights or the model), and, for artifacts that carry them, `{_gguf_model_path}` and `{mmproj}` (`core/recipe.py:1532-1538`; `models/runtime.py:40-55`). `{extra_args}` is this repo's documented escape hatch, not a sparkrun key. The repo guard is `tests/test_recipe_placeholder_resolution.py`.

## 4. The server is up but the benchmark scores 0% on empty strings

The reply is in the `reasoning` channel with `content: null` (the reasoning parser never sees a closing think tag), so any client reading `content` sees nothing. Confirm with a raw curl, then:

```bash
# chat route: content None, reasoning '391'   -> that is the trap
# /v1/completions on the same prompt: correct  -> the model is fine
```

Ship `--default-chat-template-kwargs '{"enable_thinking": false}'` (verify the pinned engine has the flag: grep `entrypoints/launchers/cli_args.py`), and let callers opt back in per request. Compare against `/v1/completions` before blaming the model.

## 5. The server serves, but `/v1/models` advertises the snapshot path as its `model` id

A templated `command:` with `--served-model-name {model}` is wrong: sparkrun rebinds **every** `{model}` occurrence — including inside that flag — to the prepared snapshot path on a real launch (`models/runtime.py:40-55` sets `model`, `model_revision`, `_prepared_model_path`, `_prepared_model_revision`, `revision`, and the GGUF/`mmproj` paths). **`-n` still prints the repo id** because bindings exist only when a prepared model is present, so only a live boot plus `GET /v1/models` (or `sparkrun cluster check --check-http-models`) reveals it.

Fix shape — declare the key **and** keep the flag pointing at it (sparkrun's prescribed spelling, `core/validation.py`'s hardcoded-flag suggestion):

```yaml
defaults:
  served_model_name: <org>/<name>
command: >
  ...
  --served-model-name {served_model_name}
```

Notes:
- Do **not** just add the key while leaving `{model}` in the flag: fill policy leaves an existing flag intact (`runtimes/base.py:943-949`), so that is a silent non-fix.
- Deleting the flag entirely also works (the runtime appends `--served-model-name <key>` when absent and a value exists, `runtimes/base.py:952-981`; sglang call site `runtimes/sglang.py:370-374`), but it fails the repo's `InertDefaults` guard (`tests/test_recipe_placeholder_resolution.py`) unless the key is added to `ALLOWED_UNREFERENCED`.
- The declarative key enters the job intent hash (`orchestration/job_metadata.py`, `name=<served>`), so a serve started before the edit no longer matches by cluster id.
- Post-fix, `-n` does show the literal (the augmentation is not gated on dry_run), but the acceptance check is still the live `GET /v1/models`.
- Props: the served id also feeds job metadata/labels/proxy. `resolve_served_model_name` takes the declared value first, then a literal flag in the command, and rejects a `{placeholder}` there by falling back to `model` — so leaving the defect makes observers disagree with the server (`core/recipe.py:450-506`).

## 6. Reading the numbers

- `benchmarking/README.md`: a cell emits **two** records (prefill + decode) and both carry `tg_throughput`; filter `is_context_prefill_phase`. `pp_req_throughput × e2e_ttft == prompt_size`, so it is not a prefill speed.
- Inter-boot noise on these nodes is **7–25%** for byte-identical boots. A single-arm win under ~10% is not a result: run the paired confirm in the same window (one node per arm), and prefer same-arm repeats over same-window singles before shipping a knob.
- Cite the `--output` file, not the `run` id: relaunching an id empties its earlier `runs/`.
- Control records are created at first launch; a control built before a recipe change can be stale — check what recipe a control actually ran before comparing against it.
