---
name: sparkrun-lane-verification
description: "Step-by-step procedure for boot-verifying and measuring a new sparkrun recipe on the WOPR DGX Spark cluster: registry-clone refresh, launch patterns, retained serve-log inspection, per-runtime spec-decode metrics, decode-triage and house-battery measurement, recording discipline, and node etiquette."
---

# Sparkrun lane verification pass

Procedure for boot-verifying and measuring a new recipe on the WOPR DGX Spark cluster (GB10 nodes), learned 2026-10-11 across six lanes. Follow in order; each step names the failure it prevents.

## 0. Registry clone first
`sparkrun run/benchmark @littlecedar/<name>` resolves from `~/.cache/sparkrun/registries/littlecedar` on the head node (registries.yaml → GitHub URL), NOT the local tree. After editing a recipe: commit, `git push origin main`, then `HOME=/home/<operator> sparkrun registry update littlecedar` on the head. Verify the clone's md5 vs your local file before launching. Symptom if skipped: recipe edits have no effect and md5 checks against `${WOPR_SRC_DIR}` lie to you.

## 1. Recipe readiness
- Run the repo gate (unittest discover + recipe validate loop + bash -n + py_compile).
- `sparkrun recipe validate <file>` catches structure but NOT: unresolved `{placeholder}` (dies at the engine), a defaults key nothing consumes, or stale prose in `description:`. The repo guards (`test_recipe_placeholder_resolution.py`) cover the first; read the description yourself.
- vLLM recipes: image `ENTRYPOINT` must be cleared (`executor_config: {entrypoint: ""}`); the speculative config must live in `defaults.speculative_config` (JSON, referenced as `'{speculative_config}'`) or the draft is never distributed; hardcode the in-container snapshot path + `--revision=<sha>` + `--served-model-name <HF-id>` in the command template (the renderer rewrites `{model}` to the repo id and strips `--revision`).

## 2. Launch
- `sparkrun run @littlecedar/<name> -H <node>` (serve) or `sparkrun benchmark performance … --profile benchmarking/decode-triage.yaml --output <durable path> --fresh`.
- Always `--output` to a durable path (`~/benchmarks/<lane>-<date>/…`): `runs/` is scratch and gets reaped; the sidecars (.yaml/.json/.csv) carry the same records.
- Long remote commands: `nohup env PYTHONUNBUFFERED=1 stdbuf -oL -eL … &` so they survive the ssh. Local long runs: a TRACKED background job (`async: true, timeout: 0`), never a detached subshell — those get reaped silently (0-byte logs, no error).

## 3. Boot verification
- Readiness: `curl http://<node>:<port>/health`. Poll patiently; large checkpoints load for minutes (Ling: 52 shards; Kolibri: 10-25 min).
- Serve log is in-container at `/tmp/sparkrun_serve.log`: `docker exec <container> grep …`. It dies with the container — copy anything you need BEFORE a bench (`--fresh` replaces the container by intent id and destroys it; this cost one boot).
- Spec-decode engagement: grep the metric the RUNTIME actually emits — SGLang: `accept len:` on decode lines; vLLM: "Mean acceptance length"/acceptance-rate lines. A single short request's accept len is an engagement proof only (accept len > 1 = draft works); steady-state numbers need real concurrent decode load (4 concurrent generations is enough).

## 4. Measure
- Speed: `benchmarking/decode-triage.yaml` (C1, depths 0/8k, runs 5, noise floor 7-25% for byte-identical boots — anything inside that spread is not a win; a single arm vs control needs a same-window pair).
- Read the JSON sidecar, decode rows only (`is_context_prefill_phase: false`); the prefill row carries a bogus half-tg figure.
- Quality: `tools/quality-battery.py <base_url> --tier both --json <file>` (37 tasks: 19 easy + 18 hard, exact-match). Run it as a tracked background job. Watch the reasoning-channel trap: if the model thinks by default, add `--default-chat-template-kwargs '{"enable_thinking": false}'` to the recipe or the battery scores 0 on empty strings while `/v1/completions` answers fine.

## 5. Record
Numbers go in the lane README with σ and n, the index row, and `mad-science/TODO.md`. Always state what was NOT verified (acceptance evidence, context window, third-party figures) — a claim without its receipt is the failure mode this procedure exists to prevent.

## Node etiquette
Assign each subagent/worker ONE node and name the task it may stop. Never derive a `sparkrun stop` list from a broad `sparkrun status | grep` — that once stopped another session's 20-hour serve. Read the status list, pick your task by recipe name, review before stopping.
