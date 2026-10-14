---
name: sparkrun-recipe-launch-debugging
description: "Use when a sparkrun recipe launch on the DGX Spark cluster fails or measures the wrong thing: distribution validation errors, serve-command validation refusal, unresolved placeholders, silent empty replies, wrong advertised model id, or edits that appear to have no effect."
---

Diagnostic ladder for `sparkrun run` / `sparkrun benchmark performance` failures on the sparkrun-recipe-registry cluster. Each rung cost a session to find once; check them in order.

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

vLLM only, template `command:` only (sglang is unaffected). The vllm-distributed render resolves `{model}` to the **declared repo id** and strips `--revision` from the template — even a literal `--revision <sha>` pair disappears, and so does `{model_revision}`. The validator then demands a path or `--revision=<sha>` token.

Fix pattern (verified booting):

```yaml
model_revision: <sha>
command: >
  vllm serve
  /cache/huggingface/hub/models--<org>--<name>/snapshots/<sha>
  --served-model-name <org>/<name>
  --revision=<sha>
```

The `=` spelling survives; the space spelling does not. To see the exact rendered command, monkeypatch and run the launch in-process:

```python
import sparkrun.models.runtime as rt
orig = rt.validate_runtime_command
rt.validate_runtime_command = lambda recipe, overrides, runtime, command: (
    print("prepared:", overrides.get("_prepared_model_path")),
    print("cmd:", command[:300]), orig(recipe, overrides, runtime, command))[2]
# then set sys.argv and call sparkrun.application.main()
```

Related: `--speculative-config` field is `"model"` (sparkrun's draft distribution keys off the same name); `"draft_model"` leaves the drafter undistributed and absent from the offline engine's path.

## 3. Serve dies instantly after "Executing serve command: done"

Read the in-container serve log; the orchestration log never shows it:

```bash
ssh <node> 'C=$(docker ps -q | head -1); docker cp $C:/tmp/sparkrun_serve.log /tmp/s.log; cat /tmp/s.log'
ssh <node> "docker cp $C:/tmp/sparkrun_serve.sh /tmp/s.sh; grep -oE 'taskset.*' /tmp/s.sh"
```

`Unknown speculative algorithm name: {SPECULATIVE_ALGORITHM}` means a `defaults:` key referenced by the command is missing: **the unresolved literal flows into the serve line verbatim, and `sparkrun recipe validate` passes anyway.** Every `{token}` in a `command:` must exist in `defaults:` (or be `{model}` / `{model_revision}` / `{extra_args}`) — guarded repo-side by `tests/test_recipe_placeholder_resolution.py`.

## 4. The server is up but the benchmark scores 0% on empty strings

The reply is in the `reasoning` channel with `content: null` (the reasoning parser never sees a closing think tag), so any client reading `content` sees nothing. Confirm with a raw curl, then:

```bash
# chat route: content None, reasoning '391'   -> that is the trap
# /v1/completions on the same prompt: correct  -> the model is fine
```

Ship `--default-chat-template-kwargs '{"enable_thinking": false}'` (verify the pinned engine has the flag: grep `entrypoints/launchers/cli_args.py`), and let callers opt back in per request. Compare against `/v1/completions` before blaming the model.

## 5. The server serves, but `/v1/models` advertises the snapshot path as its `model` id

A templated `command:` with `--served-model-name {model}` is wrong: sparkrun rebinds **every** `{model}` occurrence — including inside that flag — to the prepared snapshot path on a real launch (`models/runtime.py::bind_runtime_models` sets `overrides["model"]=path`; only `model`/`model_revision`/`_prepared_model_path`/`revision` are touched). **`-n` still prints the repo id** (dry runs return before bindings exist), so only a live boot plus `GET /v1/models` (or `sparkrun cluster check --check-http-models`) reveals it.

Fix shape — declare the key **and** keep the flag pointing at it (sparkrun's prescribed spelling, `core/validation.py`'s hardcoded-flag suggestion):

```yaml
defaults:
  served_model_name: <org>/<name>
command: >
  ...
  --served-model-name {served_model_name}
```

Notes:
- Do **not** just add the key while leaving `{model}` in the flag: fill policy leaves an existing flag intact (`runtimes/base.py:931-933`), so that is a silent non-fix.
- Deleting the flag entirely also works (the sglang runtime appends `--served-model-name <key>` when absent, `runtimes/base.py:976-981`), but it fails the repo's `InertDefaults` guard (`tests/test_recipe_placeholder_resolution.py`) unless the key is added to `ALLOWED_UNREFERENCED`.
- The declarative key enters the job intent hash (`orchestration/job_metadata.py`, `name=<served>`), so a serve started before the edit no longer matches by cluster id.
- Post-fix, `-n` does show the literal (the augmentation is not gated on dry_run), but the acceptance check is still the live `GET /v1/models`.
- Props: the served id also feeds job metadata/labels/proxy (`resolve_served_model_name`, which **rejects** placeholder values), so leaving the defect also makes observers disagree with the server.

## 6. Reading the numbers

- `benchmarking/README.md`: a cell emits **two** records (prefill + decode) and both carry `tg_throughput`; filter `is_context_prefill_phase`. `pp_req_throughput × e2e_ttft == prompt_size`, so it is not a prefill speed.
- Inter-boot noise on these nodes is **7–25%** for byte-identical boots. A single-arm win under ~10% is not a result: run the paired confirm in the same window (one node per arm), and prefer same-arm repeats over same-window singles before shipping a knob.
- Cite the `--output` file, not the `run` id: relaunching an id empties its earlier `runs/`.
- Control records are created at first launch; a control built before a recipe change can be stale — check what recipe a control actually ran before comparing against it.
