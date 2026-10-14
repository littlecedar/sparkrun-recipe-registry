---
name: sparkrun-lane-quality-measurement
description: "Re-measure a sparkrun recipe lane's accuracy and run single-knob perf arm sweeps on the DGX Spark cluster, then integrate the numbers with provenance."
---

# Measuring a sparkrun recipe lane (accuracy + perf arms)

For `sparkrun-recipe-registry`. Use when a lane's docs carry unmeasured or floor-quality
numbers, or when a recipe's knobs need an arm sweep. Sibling lanes (ornith, qwen3, qwen4)
carry `Run quality benchmarking pass` TODOs — same procedure.

## 0. Prerequisites
- `every sparkrun call needs the HOME override`: `HOME=$PWD/.local/sparkrun-home`.
- Nodes are named in `.local/CONFIDENTIAL.md` (git-ignored) / `COOP.md`. Bench on the two
  unrestricted Spark nodes; run `sparkrun` **from the head node**, never as a compute target.
- Check the cluster is free: `sparkrun status`. Stop what you start when done.

## 1. Accuracy: check the instrument before trusting any number
1. **Read the model's own `chat_template.jinja`** (in the node's HF snapshot) and find the
   knob that actually controls thinking. Do not assume `enable_thinking` is universal — a
   family keyed on `reasoning_effort` silently ignores it, and then every reply opens a
   reasoning block.
2. Use `recipes/ds4/benchmarks/run_benchmarks.py`: `--reasoning-effort {default,high,medium,low}`
   (additive; `default` sends no key), `--max-tokens-scale` (base caps house 1024 / gsm8k 2048
   / arc 1024), and read `finish_reasons` + `empty_replies` from each summary.
3. **Score `content` only**, and prefer the server default effort as the headline. At
   `reasoning_effort: low` some models return the answer inside `reasoning_content` with empty
   `content`, so a content scorer reads ~0 % on items the model answered.
4. **A `finish_reason: length` is a truncated response, not a wrong answer.** Check the
   histogram before believing a low score; 200/200 `length` with empty content is an
   instrument artifact, not a weak model.
5. Run each bench as its own concurrent process (`--bench house|gsm8k|arc` per invocation)
   against the same endpoint: distinct `_raw` files, and the server batches them.
6. Each invocation is capped at 1 h; every item is appended to `_raw/<slug>.<bench>.<thinking>.jsonl`
   as it completes, so a killed job resumes by re-running the identical command.

## 2. Perf arms: one boot per arm, never rank inside the noise band
1. Arm = `sparkrun benchmark performance <recipe> -H <host> --profile decode-triage \
   -o <override> --output <dir>/<tag>.yaml --fresh --no-stop`.
2. Override shape matters: a key that has a `{placeholder}` in `command:` takes `-o key=value`;
   anything else (e.g. `page_size`, `--cuda-graph-max-bs-decode`) must ride
   `-o "extra_args=--flag value"`, because `extra_args` is appended LAST and argparse keeps the
   last occurrence.
3. **Always run a same-window control boot.** The inter-boot noise floor on this hardware is
   7-25 % for byte-identical boots (`benchmarking/decode-triage.yaml` says so). One boot per arm
   cannot resolve anything under ~7 % — state that and do not rank.
4. Record provenance: each arm maps to a `bench_*` id, and the id's overrides are in
   `~/.cache/sparkrun/benchmarks/<bench_id>/state.yaml` under `extras.measurement_overrides`.
   A number without a bench id does not go in a table.
5. Before a long-context arm, read the checkpoint `config.json`: `max_position_embeddings` +
   `rope_parameters`. Models in one family may declare different ceilings (YaRN vs plain rope).

## 3. Spec arms need a boot each
Launch with `sparkrun run <recipe> -H <host> --transfer-mode local` (the `--transfer-mode local`
flag is REQUIRED when the recipe uses unpublished mods, or the node clones the registry and the
mod is invisible), wait for `/health` 200, score it with the accuracy harness, then stop it.

## 4. Integrate (this is the deliverable, not the numbers)
1. Every measured figure goes into the recipe header `MEASURED`/`ACCURACY` block, the lane
   `README.md` + `AGENTS.md` state table, and the lane `NOTES.md` session record — each with its
   `bench_*` id.
2. Annotate superseded claims; never delete a measured claim to replace it.
3. Keep numbers consistent across all prose (a stale baseline in a table is a defect).
4. Gate: `uv run python -B -m unittest discover -s tests`, then `sparkrun recipe validate` on
   every recipe, `bash -n` on `mods/*/*.sh` **and** `recipes/*/mods/*/*.sh`, `py_compile` on those
   mods plus `tools/*.py`, then remove `__pycache__` (under `mods/`, `recipes/`, `tools/`, `tests/`).
5. Commit with EXPLICIT pathspecs only (the tree has a live second writer) after reviewing
   `git diff --cached --stat`; never `git add -A`.

## 5. Report honestly
Hold open questions open in `NOTES.md` (e.g. quality across a full 512K span, an accuracy gate
not yet met). A speed win with no quality check is not a shipping result.
