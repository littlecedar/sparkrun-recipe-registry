# AGENTS.md — `recipes/ifm/` (IFM K2-Horizon family)

Lane guide for the IFM `K2-Horizon` recipes. Read this before working in this
directory; it carries the state, the constraints, and the guards. Prose summaries
live in [`README.md`](README.md); the durable research record is the three
`K2-*-MODEL-OPTIMIZATION-WORK.md` files (git-ignored) with their `K2-*-JOURNAL.md`
narratives, and cross-agent traffic is in `COOP.md`.

**No hostnames or addresses in tracked files.** This registry is distributed to
third parties. Internal node state belongs in the git-ignored `COOP.md`/journal,
never here.

---

## 1. Mission and state

Serve the IFM K2-Horizon family (dense `0.9B`, dense `7B-FP8`, gated-GQA MoE
`MoVA-36B-A4B` in BF16 and block-FP8) on GB10 with native SGLang, and keep the
recipes honest about what has actually been measured.

**Current state (2026-10-08, first hardware session — see §4):**

| model | recipe(s) | state |
|---|---|---|
| 0.9B | `k2-horizon-0.9b-bf16-sglang` | **MEASURED**, boots clean (77.3/67.0 t/s) |
| 7B-FP8 | `…-7b-fp8-sglang`, `…-ngram`, `…-uno` | **MEASURED** (21.0/19.0, 27.4/29.2, 37.7) |
| 36B-A4B | `…-36b-a4b-{bf16-tp1,fp8-tp1,fp8-tp2}` | **MEASURED** (BF16 15.6/14.1, FP8 TP1 18.3/16.3; TP2 in progress) |
| probe | `zz-k2-36b-a4b-fp8-unpatched-probe` | live pending re-run |

Before this session **every recipe was theory-only** — none had booted — and four
load-bearing claims turned out wrong (see §4). Treat the WORK docs as the model, not
as ground truth; the journal is where the falsifications are recorded.

## 2. Evidence locations

| question | where the answer lives |
|---|---|
| what a recipe *is* and why | the recipe file's own comment block (`command:` explainer) |
| the model / roofline / byte census | `K2-*-MODEL-OPTIMIZATION-WORK.md` |
| what happened, dated | `K2-*-JOURNAL.md` |
| cross-model findings, node state | `COOP.md` |
| the canonical 36B byte arithmetic | `tests/k2_36b_arith.py` (`selftest()` / `show()`) |
| guard tests | `tests/test_ifm_recipes.py`, `tests/test_ifm_36b_recipes.py`, `tests/test_k2_7b_recipes.py` |

## 3. Hard constraints (each earned on hardware or in source)

- **`--attention-backend flashinfer` on GB10.** `fa3` cannot be constructed
  (`create_flashattention_v3_backend` asserts major 8/9; GB10 is `(12,1)`).
  `flashinfer` is SGLang's own auto-default for major 12. The two cards and the
  cookbook all pass `fa3` because they were written on Hopper.
- **`--dtype bfloat16` spelled explicitly.** `auto` resolves through the *declared*
  config dtype and maps a declared `float32` onto float16 for non-gemma model types;
  the 0.9B declares `float32` while its tensors are BF16.
- **`--json-model-override-args '{"xllm_source_router_gemm_partitions": 2}'` on every
  36B MoVA recipe.** Mandatory; the engine dies at `xllm.py:204` without it. `2` is
  the MP2 contract (numerics, not speed). See §4.
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

## 4. Falsified claims (do not re-assert)

The 2026-10-08 session (JOURNAL, 36B journal) overturned four things the theory docs
argued confidently:

1. **"The 36B recipes boot as shipped."** False — every 36B-A4B recipe died before
   reading a weight at `xllm.py:204` (router provenance). The lane predicted a
   *different* gate (`:664`, compressed-tensors) and on the FP8 arm only. Fixed.
2. **"FP8's value is not established; the BF16 recipe may be the shipping config."**
   False — FP8 measured faster (18.3 vs 15.6 t/s, +17 %).
3. **"Uno is blocked by upstream at every size."** False — with the probe mod UNO
   boots and serves at 37.7 t/s, accept len 3.60 > the 2.07 break-even.
4. **"The 7B roofline gives ~25 t/s at c=1."** Optimistic — measured 21.0; the
   roofline counts only the weight read and ignores per-step overhead.

## 5. Guard suite

Three stdlib-`unittest` modules, no PyYAML (they parse recipe text and strip
whole-line comments first):

| module | count | scope |
|---|---|---|
| `tests/test_ifm_recipes.py` | — | 0.9B: no `fa3`, dtype, revision, container floor, flag map |
| `tests/test_ifm_36b_recipes.py` | 64 | 36B: fa3, mod wiring, dtype, TP ceiling, revision, flag map, arithmetic agreement, **`I17RouterProvenance`**, stale-claim controls |
| `tests/test_k2_7b_recipes.py` | — | 7B + Uno + NGRAM: banned flags for UNO, mod existence/order, declaration-stash trap |

**Every guard has a negative control** in a `NegativeControls` class. A guard that
cannot fail proves nothing; add a control with any new guard. `I17RouterProvenance`
is the newest: it asserts all four MoVA recipes carry the override as a literal (not
a `defaults:` key) and that the value is `2`, not `1`.

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
non-shippable probe arm. Nothing is retired to `attic/ifm/` yet.

## 8. Traps

- `sparkrun recipe validate` does **not** resolve mods (`mods:`, `--json-model-override-args`).
- `is_sm120_supported` (matches major 12) and `is_sm120` (demands exactly (12,0))
  disagree on GB10 — read the predicate, not the name.
- `--fp8-gemm-backend cutlass` is the explicitly blessed SM12x choice; DeepGEMM's
  UE8M0 path gates on `get_device_sm() == 120` exactly and excludes GB10.
- The card's `--revision` is an sglang commit-ish that 404s against every model repo —
  derive the pin from the HF API.
- A root-run engine import in *any* mod poisons the bind-mounted `/cache/runtime`
  cache for uid 1000 forever; mods must `reown()` what they create.

*Evidence over memory: if this file and a boot log disagree, the log wins — and this
file gets corrected.*