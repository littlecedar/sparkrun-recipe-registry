# COOP — `recipes/ifm/` (IFM K2-Horizon family: 0.9B / 7B-FP8)

Cross-agent coordination ledger for the K2-Horizon lanes. Its job, per
`K2-09B-MODEL-OPTIMIZATION-WORK.md`: hold the **family-wide findings the 0.9B and 7B agents
need**, so two agents never spend a boot answering the same question. Narrative belongs in the
`K2-*-JOURNAL.md` files; durable evidence belongs in the `K2-*-MODEL-OPTIMIZATION-WORK.md` files.

> **This file is a 2026-10-07 reconstruction.** The original was lost from the working tree — it is
> cited by the archived sub-lane's recipes as "COOP item 3/8/9", by `tests/test_ifm_recipes.py`
> as a source, and by that sub-lane's guard ("see COOP 2026-09-21 correction"), and no copy
> survived anywhere on disk. Everything below is transcribed from those citations and from the
> lane's own documents; nothing is invented. Items whose numbers are cited nowhere were not
> recoverable — **do not renumber the anchors**; add new items at the next free numbers.
>
> Keep hostnames and addresses out of anything tracked.

## Live state — update every session

| field | value |
|---|---|
| Session date | *(no session claimed in this tree)* |
| Assigned pair | node assignment lives node-side; resolve hostnames before acting |
| Bench lock | none — write `BENCH LOCK: <agent> <arm> <nodes> <eta>` here before launching, remove it when the job ends |

## Items cited by name elsewhere in this lane

- **Item 3 — `--attention-backend fa3` cannot be constructed on GB10.**
  `create_flashattention_v3_backend` asserts `(major == 8 and not use_mla) or major == 9`
  (`layers/attention/attention_registry.py:227-235`, VERIFIED at v0.5.20); GB10 reports `(12, 1)`
  (`utils/common.py:332-333`, `is_sm121`). Both the HF cards and the SGLang cookbook pass `fa3`
  because both were written on Hopper — copying them is the single most likely way to ship a recipe
  that cannot boot. `flashinfer` is sglang's own auto-default for major 12; name it explicitly.
  Citing sites: `tests/test_ifm_recipes.py` I1; every recipe here names `flashinfer` (the
  UNO probe deliberately names `fa4`, `k2-horizon-7b-fp8-uno-sglang.yaml:110`).
- **Item 8 — a declared `dtype` in `config.json` is not the tensor dtype.**
  `--dtype auto` resolves through the *declared* config dtype
  (`configs/model_config.py:2078-2124`) and quietly maps a declared `float32` onto float16 for any
  non-gemma `model_type`; the 0.9B checkpoint declares `float32` while `validation.json` says its
  tensors are BF16, so `auto` can load 6.5 GB where 2.16 GB was intended
  (`k2-horizon-0.9b-bf16-sglang.yaml:78-85`). Every recipe here pins `dtype: bfloat16`.
- **Item 9 — the vendor card's `--revision` is an sglang commit-ish and 404s.**
  The cards pass `--revision 9b9ec1f7e17f…`, which does not exist in any `IFM/K2-Horizon-*` repo;
  each recipe pins the checkpoint SHA the analysis was done against instead.
  Citing sites: `k2-horizon-0.9b-bf16-sglang.yaml:246-249`; guard
  `tests/test_ifm_recipes.py::test_no_foreign_revision_copied_from_card`.

## Family-wide findings (each with its source)

- **SGLang >= v0.5.20 or nothing.** `models/xllm.py` (which registers `K2HorizonForCausalLM`) does
  not exist at v0.5.19, and vLLM's support PR is closed-unmerged, so vLLM is not a fallback.
  (`K2-09B-MODEL-OPTIMIZATION-WORK.md` TL;DR 1; `tests/test_k2_7b_recipes.py` header.)
- **The model cards' launch snippets do not boot on a Spark, for three independent reasons:** fa3
  (item 3), `--revision` (item 9), and a vLLM block that is not valid JSON. Both cards also serve
  the BF16 model rather than the FP8 one they document.
  (`K2-09B-MODEL-OPTIMIZATION-WORK.md` TL;DR 2; `tests/test_k2_7b_recipes.py` header.)
- **Archived sub-lane.** The family's third lane was withdrawn 2026-10-08 as too slow to justify
  the compute — measured working on hardware first. Its recipes, mod and guards are in
  `attic/ifm/` with a manifest.
- **`fp8_gemm_backend` is `cutlass`, spelled.** `auto` prefers DeepGEMM, whose scale layout gates on
  `get_device_sm() == 120` exactly and so excludes SM121.
  (`tests/test_k2_7b_recipes.py` header, sec 4.3.)
- **7B UNO cannot boot on SM121**: `_handle_uno` requires the `(fa3, fa3)` pair, so the Uno arm is a
  probe (`mods/probe-uno-fa4-sm121` + `mods/provide-uno-lora-k2-horizon-7b`), not a production
  recipe. (`tests/test_k2_7b_recipes.py` header, sec 6.7.)
- **Pin the fast-core mask.** `taskset -c 5-9,15-19` (the X925 clusters; A725 is 0-4 and 10-14) is a
  measured win carried into every command here (`k2-horizon-0.9b-bf16-sglang.yaml:147`,
  `k2-horizon-7b-fp8-sglang.yaml:151`).
- **KV sizing is the binding constraint on this family.** 7B FP8 is 144 KiB/token, so a 512K
  sequence would be 72 GiB of bf16 KV and leave the box no room for a second request
  (`k2-horizon-7b-fp8-sglang.yaml:71-75`). Size by bytes, not by parameter count.
  (`K2-7B-MODEL-OPTIMIZATION-WORK.md` section 5.)
- **`enable_thinking` is a no-op for this family — the template keys on `reasoning_effort`.**
  Both checkpoints' `chat_template.jinja` (0.9B 51,155 B / 7B 51,034 B) contain
  `reasoning_effort` and **no `enable_thinking` at all**, so a harness that passes
  `chat_template_kwargs={"enable_thinking": false}` (e.g. `recipes/ds4/benchmarks/run_benchmarks.py`
  `--thinking off`) is **silently ignored** and every reply opens a reasoning block.
  VERIFIED live 2026-10-09 by key-comparison on the two serving nodes: `enable_thinking` and
  `reasoning_effort: high` returned byte-identical completions.
  Two consequences for any scorer here: (1) a small `max_tokens` (the shipped ARC cap was **16**)
  is consumed by the reasoning block and the item returns `finish_reason: length`, `content: ""` —
  the model never gets to answer, and the score is a measurement of the cap, not of the model;
  (2) at `reasoning_effort: low` the 7B puts its answer in `reasoning_content` and leaves
  `content` **empty** (`effort: medium` does the same on the 0.9B), so a content-only scorer reads
  ~0 % on items the model answered correctly. Score the default (`high`) effort with an adequate
  cap. Use `--reasoning-effort` / `--max-tokens-scale` on the harness (`run_benchmarks.py`), which
  were added for exactly this; prefer `--reasoning-effort default` (server default = high).
  (`recipes/ds4/benchmarks/run_benchmarks.py` docstring; `recipes/ifm/NOTES.md`.)

## Dated corrections

- **2026-09-20 (late)** — a cross-agent fetch overwrote `config.json` in the shared scratch cache
  (`.scratch/ifm/`, parent of the per-model `09b/` directory). Keep each model in its own
  subdirectory and re-verify `total_size` before trusting a local copy.
  (`K2-09B-MODEL-OPTIMIZATION-WORK.md` header.)
- **2026-09-21** — the `rewrap-k2-horizon` mod was **abandoned**; do not resurrect it.
  (Recorded in the guard for the sub-lane, archived to `attic/ifm/`.)

## Protocol

1. **Claim before you work** — add a row with your agent id, workstream and date. One owner per
   workstream per session; the deliverable is a committed file, a `bench_*` id, or a `§N` section —
   never a chat sentence.
2. **One bench job at a time** — the assigned pair supports exactly one arm; put a `BENCH LOCK:` line
   in Live state before launching and remove it when the job ends.
3. **Post failures too** — a boot that dies, a flag that does not reach the server, a node with low
   `MemAvailable`: one line here saves the next agent a boot.
4. **Every entry carries an evidence pointer** — a `bench_*` id, a `§N` cite, or `file:line`.