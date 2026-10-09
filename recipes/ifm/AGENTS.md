# AGENTS.md — `recipes/ifm/` (IFM K2-Horizon family)

Lane guide for the IFM `K2-Horizon` recipes. Read this before working in this
directory; it carries the state, the constraints, and the guards. Prose summaries
live in [`README.md`](README.md); the durable research record is the two
`K2-*-MODEL-OPTIMIZATION-WORK.md` files (git-ignored) with their `K2-*-JOURNAL.md`
narratives, and cross-agent traffic is in `COOP.md`.

**No hostnames or addresses in tracked files.** This registry is distributed to
third parties. Internal node state belongs in the git-ignored `COOP.md`/journal,
never here.

---

## 1. Mission and state

Serve the IFM K2-Horizon family (dense `0.9B`, dense `7B-FP8`, plus the `7B-Uno`
conditional-LoRA diffusion draft) on GB10 with native SGLang, and keep the recipes
honest about what has actually been measured.

**Current state (2026-10-08 hardware, 2026-10-09 accuracy re-measurement — see §4):**

| model | recipe(s) | state | accuracy (house / gsm8k / arc) |
|---|---|---|---|
| 0.9B | `k2-horizon-0.9b-bf16-sglang` | **MEASURED**, boots clean (77.6/67.3 t/s) | 31/37 = 83.8 % / 174/200 = 87.0 % / 133/200 = 66.5 % |
| 7B-FP8 | `…-7b-fp8-sglang`, `…-ngram`, `…-uno` | **MEASURED** (21.3/19.2, 27.9/28.6, **32.4/27.1**) | 36/37 = 97.3 % / 188/200 = 94.0 % / 178/200 = 89.0 % |

The accuracy column is greedy, `reasoning_effort` = the template default `high`, seed
1234, measured 2026-10-09; the 2026-10-08 figures (0.9B 72.97 / 63.50 / 0.00; 7B
89.19 / 87.50 / 0.00) were **floors, not measurements** — see §4.

The two 7B spec arms were scored on the same instrument and item sets: **NGRAM
(97.3 / 93.5 / 88.5) and Uno (97.3 / 95.0 / 87.5)** are each within ±3 items
(about one SE on n=200) of the plain 7B on every benchmark, so neither trades
accuracy for its speed win.

**UNO is now a shipped arm, not a probe (2026-10-09).** A 12-boot campaign
(`.scratch/ifm/perf-2026-10-09/`, git-ignored) promoted
`k2-horizon-7b-fp8-uno-sglang` from PROBE to the lane's fastest arm: F=8 with
`max_num_seqs: 32` measured **32.4/27.1 t/s** single-stream (d0/d8192) against
the plain 7B's 21.3/19.2 — +52 %/+41 % — and **145.5/90.2** aggregate at c=8,
the best figure in the lane. The campaign also found the arm's sharp edge:
`max_num_seqs` is load-bearing (at 8 it flatlines at c=8; at 32 it scales),
which `tests/test_k2_7b_recipes.UnoConcurrencyCap` now guards. Tables:
`README.md` §UNO arm and `NOTES.md` (2026-10-09 session).

Before this session **every recipe was theory-only** — none had booted — and two
load-bearing claims turned out wrong (see §4). Treat the WORK docs as the model, not
as ground truth; the journal is where the falsifications are recorded.

## 2. Evidence locations

| question | where the answer lives |
|---|---|
| what a recipe *is* and why | the recipe file's own comment block (`command:` explainer) |
| the model / roofline / byte census | `K2-*-MODEL-OPTIMIZATION-WORK.md` — **git-ignored and absent from this tree**; the surviving numbers are in `README.md`, `NOTES.md`, `COOP.md` and the recipe headers |
| what happened, dated | `K2-*-JOURNAL.md` (same: git-ignored by design, may be absent) |
| the measured UNO campaign artifacts (per-arm `--output` JSON) | `.scratch/ifm/perf-2026-10-09/` (git-ignored) |
| cross-model findings, node state | `COOP.md` |
| the withdrawn sub-lane: recipes, mod, guards, byte arithmetic | `attic/ifm/` (`ARMS-MANIFEST.md`) |
| guard tests | `tests/test_ifm_recipes.py`, `tests/test_k2_7b_recipes.py` |

## 3. Hard constraints (each earned on hardware or in source)

- **`--attention-backend flashinfer` on GB10.** `fa3` cannot be constructed
  (`create_flashattention_v3_backend` asserts major 8/9; GB10 is `(12,1)`).
  `flashinfer` is SGLang's own auto-default for major 12. The two cards and the
  cookbook all pass `fa3` because they were written on Hopper.
- **`--dtype bfloat16` spelled explicitly.** `auto` resolves through the *declared*
  config dtype and maps a declared `float32` onto float16 for non-gemma model types;
  the 0.9B declares `float32` while its tensors are BF16.
- **`model_revision:` (top-level), pinned to a SHA** — never a branch and never
  `revision:`. The container runs `HF_HUB_OFFLINE=1` over a `snapshots/<sha>/` cache
  with no `refs/` entry, so an unpinned engine dies *after* the weights synced.
- **Digest-pin `container:`** — v0.5.20 is the version floor (`models/xllm.py` is
  absent at v0.5.19). A moving `dev-*` tag is not a guarantee.
- **`defaults:` reaches the engine only through a `{placeholder}`.** `page_size` and
  `chunked_prefill_size` are *not* in sparkrun's `_SGLANG_FLAG_MAP`; a key absent from
  the map is dropped with no error. Never delete a placeholder to silence a warning.
- **Mods are an ordered chain.** The 7B-Uno recipe's provide→probe order is
  load-bearing. Use bare `mods/<name>` references (the scoped `@littlecedar/mods/<name>`
  form resolves against the published registry clone, which does not carry these
  unpublished mods).
- **`max_num_seqs` is load-bearing on the UNO arm.** It is a scheduler *admission*
  limit, not a memory limit: at 8 the arm flatlines at c=8 (97.5 aggregate, below
  its own c=4 of 98.6) while the plain 7B reaches 120; at 32 it scales to 145.5.
  Do not lower it — `tests/test_k2_7b_recipes.UnoConcurrencyCap` enforces a floor.

## 4. Falsified claims (do not re-assert)

Four claims the theory docs (and one probe run) argued confidently, and what the
devices answered:

1. **"Uno is blocked by upstream at every size."** False — the probe mod relaxes
   UNO's literal `("fa3","fa3")` gate, after which UNO boots, serves, and is the
   lane's **fastest** arm. 2026-10-09: F=8 32.4/27.1 t/s single-stream (+52 %/+41 %
   over the plain 7B) and 145.5/90.2 aggregate at c=8, accuracy-lossless.
2. **"The 7B roofline gives ~25 t/s at c=1."** Optimistic — measured 21.3; the
   roofline counts only the weight read and ignores per-step overhead.
3. **"UNO's linear draft cannot scale to high concurrency."** False — it looked true
   only because the probe ran with `max_num_seqs: 8`. That cap, not the algorithm,
   was the flatline; at 32 the arm has the best c=8 aggregate in the lane.

4. **"ARC-Challenge (and the rest of the battery) shows the model is weak."** False — the
   2026-10-08 numbers were an *instrument* artifact, not a model property. Both
   templates key reasoning on `reasoning_effort` (default `high`) and carry **no
   `enable_thinking`**, so the harness's `--thinking off` was silently ignored and every
   reply opened a reasoning block; ARC's `max_tokens=16` was then consumed by that block,
   so all 200 items returned `finish_reason: length` and empty content — a 0.00 % score by
   construction. Re-measured 2026-10-09 through the fixed harness (`--reasoning-effort
   default`, caps 1024/2048/1024) the models answer ARC normally. **Before quoting any
   accuracy figure from the 2026-10-08 session, check `finish_reasons` in its summary
   JSON; a `length` is a truncated response, not a wrong answer.** See §8 traps and
   `COOP.md`.

## 5. Guard suite

Two stdlib-`unittest` modules, no PyYAML (they parse recipe text and strip
whole-line comments first):

| module | count | scope |
|---|---|---|
| `tests/test_ifm_recipes.py` | 16 | 0.9B: no `fa3`, dtype, revision, container floor, flag map |
| `tests/test_k2_7b_recipes.py` | 60 | 7B + Uno + NGRAM: banned flags for UNO, mod existence/order, declaration-stash trap |
| `attic/ifm/test_ifm_36b_recipes.py` | 64 | withdrawn 36B sub-lane; no longer auto-discovered |

**Every guard has a negative control** in a `NegativeControls` class. A guard that
cannot fail proves nothing; add a control with any new guard.

## 6. Validation ritual

There is no CI and no linter. Before considering a change done:

```bash
uv run python -B -m unittest discover -s tests            # full suite
HOME=$PWD/.local/sparkrun-home sparkrun recipe validate recipes/ifm/*.yaml
for s in mods/*/*.sh; do bash -n "$s"; done
uv run python -m py_compile mods/*/*.py tools/*.py         # then rm __pycache__
```

`sparkrun recipe validate` is the gate, **not `--strict`**. It does **not** resolve
`mods:` entries — a typo'd mod name still validates and only fails at launch. The
guard suite covers that gap.

## 7. Sprawl policy

`recipes/ifm/` is a shipped artifact (distributed over git). Keep it to shipped
recipes + guides. A dead arm, a closed-question variant, or a probe moves to
`attic/ifm/` with a manifest row when its question closes. The `zz-` prefix marks a
non-shippable probe arm. The `MoVA-36B-A4B` sub-lane was withdrawn 2026-10-08 and now
lives in `attic/ifm/` — see `attic/ifm/ARMS-MANIFEST.md`. The 7B-Uno **probe** closed
its question the other way (2026-10-09): it was promoted to a shipped arm in place,
because the answer was "yes, and it is the fastest one" rather than "no".

## 8. Traps

- `sparkrun recipe validate` does **not** resolve mods (`mods:` entries).
- `is_sm120_supported` (matches major 12) and `is_sm120` (demands exactly (12,0))
  disagree on GB10 — read the predicate, not the name.
- `--fp8-gemm-backend cutlass` is the explicitly blessed SM12x choice; DeepGEMM's
  UE8M0 path gates on `get_device_sm() == 120` exactly and excludes GB10.
- The card's `--revision` is an sglang commit-ish that 404s against every model repo —
  derive the pin from the HF API.
- A root-run engine import in *any* mod poisons the bind-mounted `/cache/runtime`
  cache for uid 1000 forever; mods must `reown()` what they create.
- **The two models do NOT share a context ceiling.** The 0.9B is
  `max_position_embeddings=131072` **with YaRN** (`factor: 16` x
  `original_max_position_embeddings` 8192), so 131072 is its hard ceiling; the
  7B-FP8 is **524288** with `rope_type: default` (no YaRN), so its 131072
  default is a choice, not a limit. Read the checkpoint before quoting a context
  length.
- **`--cuda-graph-max-bs` is absent at sglang v0.5.20.** argparse rejects it and
  the server never binds its port; the only working spellings are
  `--cuda-graph-max-bs-decode` / `--cuda-graph-max-bs-prefill` (a `-decode 32`
  boot serves, bench `bench_bf98a3f39ef5`).
- **A `bench_*` id is not unique when benchmarks run concurrently.** Two campaigns
  started in the same window can drive the same bench id and share
  `~/.cache/sparkrun/benchmarks/<id>/`, so a `consolidated.json` copied afterward can
  hold the wrong arm's cells. The `--output` JSON/YAML is written per run and is the
  durable artifact (this is why `.scratch/ifm/perf-2026-10-09/` keeps them per tag);
  the bench id is provenance, not identity.

*Evidence over memory: if this file and a boot log disagree, the log wins — and this
file gets corrected.*