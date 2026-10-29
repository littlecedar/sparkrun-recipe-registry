# AGENTS.md — `recipes/ifm/` (IFM K2-Horizon family)

Lane guide for the IFM `K2-Horizon` recipes. Read this before working in this
directory; it carries the state, the constraints, and the guards. Prose summaries
live in [`recipes/ifm/README.md`](../../recipes/ifm/README.md); the durable research record is the two
`K2-*-MODEL-OPTIMIZATION-WORK.md` files (git-ignored) with their `K2-*-JOURNAL.md`
narratives, and cross-agent traffic is in `COOP.md` — a git-ignored working
ledger, not registry content (see the root `AGENTS.md`).

**No hostnames or addresses in tracked files.** This registry is distributed to
third parties. Internal node state belongs in the git-ignored journal/ledger,
never here.

---

## Contents

- [1. Mission and state](#1-mission-and-state)
- [2. Evidence locations](#2-evidence-locations)
- [3. Hard constraints (each earned on hardware or in source)](#3-hard-constraints-each-earned-on-hardware-or-in-source)
- [4. Falsified claims (do not re-assert)](#4-falsified-claims-do-not-re-assert)
- [5. Guard suite](#5-guard-suite)
- [6. Validation ritual](#6-validation-ritual)
- [7. Sprawl policy](#7-sprawl-policy)
- [8. Traps](#8-traps)
- [9. Recipe research record (moved from recipe comments, 2026-10-10)](#9-recipe-research-record-moved-from-recipe-comments-2026-10-10)
- [From recipes/ifm/README.md (2026-10-14)](#from-recipesifmreadmemd-2026-10-14)
- [Why every lane is TP=1](#why-every-lane-is-tp1)
- [Performance (measured)](#performance-measured)
- [Accuracy (measured)](#accuracy-measured)
- [Archived material](#archived-material)
- [Recipe comment archive (2026-10-14)](#recipe-comment-archive-2026-10-14)
- [Session 2026-10-18 — the 36B-A4B D2 + E6 gate run, and the decision it hands back](#session-2026-10-18--the-36b-a4b-d2--e6-gate-run-and-the-decision-it-hands-back)
- [Engine-bump adjudication — SGLang 0.5.20 → 0.5.22 (2026-10-22, on hardware)](#engine-bump-adjudication--sglang-0520--0522-2026-10-22-on-hardware)

## 1. Mission and state

Serve the IFM K2-Horizon family (dense `0.9B`, dense `7B-FP8`, plus the `7B-Uno`
conditional-LoRA diffusion draft) on GB10 with native SGLang, and keep the recipes
honest about what has actually been measured.

**Current state (2026-10-08 hardware, 2026-10-09 accuracy re-measurement — see §4):**

| model | recipe(s) | state | accuracy (house / gsm8k / arc) |
|---|---|---|---|
| 0.9B | `k2-horizon-0.9b-bf16-sglang` | **MEASURED**, boots clean (77.6/67.3 t/s) | 31/37 = 83.8 % / 174/200 = 87.0 % / 133/200 = 66.5 % |
| 7B-FP8 | `k2-horizon-7b-fp8-uno-sglang` (the plain 7B and NGRAM arms are archived in `attic/ifm/arms/`) | **MEASURED** (**32.4/27.1** shipped; the archived arms measured 21.3/19.2 and 27.9/28.6) | 36/37 = 97.3 % / 188/200 = 94.0 % / 178/200 = 89.0 % |

The accuracy column is greedy, `reasoning_effort` = the template default `high`, seed
1234, measured 2026-10-09; the 2026-10-08 figures (0.9B 72.97 / 63.50 / 0.00; 7B
89.19 / 87.50 / 0.00) were **floors, not measurements** — see §4.

The two 7B spec arms were scored on the same instrument and item sets: **NGRAM
(97.3 / 93.5 / 88.5) and Uno (97.3 / 95.0 / 87.5)** are each within ±3 items
(about one SE on n=200) of the plain 7B on every benchmark, so neither trades
accuracy for its speed win.

**Re-pinned to main 2026-10-14** (`IFM/K2-Horizon-0.9B` → `383cb66347be…`,
`IFM/K2-Horizon-7B-FP8` → `ea739ec816e0…`), both again SHA-pinned in the two
recipes, and honoured by the guards. The 7B delta is the model card only; the
0.9B delta is the card plus the two chat templates (PR #10: OpenAI content-part
lists), which render byte-identical to the old templates for plain-string
conversations. Re-benchmarked + re-scored on `.31` on the same lanes: every perf
cell inside the lane's 7-25 % noise floor and every accuracy cell within ~±2
items (0.9B 83.8/86.0/68.5; 7B-Uno 97.3/94.5/90.5; UNO accept len 4.15 mean).
Details: `NOTES.md` (2026-10-14 session).

**UNO is now a shipped arm, not a probe (2026-10-09).** A 12-boot campaign
(`.scratch/ifm/perf-2026-10-09/`, git-ignored) promoted
`k2-horizon-7b-fp8-uno-sglang` from PROBE to the lane's fastest arm: F=8 with
`max_num_seqs: 32` measured **32.4/27.1 t/s** single-stream (d0/d8192) against
the plain 7B's 21.3/19.2 — +52 %/+41 % — and **145.5/90.2** aggregate at c=8,
the best figure in the lane. The campaign also found the arm's sharp edge:
`max_num_seqs` is load-bearing (at 8 it flatlines at c=8; at 32 it scales),
which `tests/test_k2_7b_recipes.UnoConcurrencyCap` now guards. Tables:
`README.md` §UNO arm and `NOTES.md` (2026-10-09 session).

**The lane was consolidated to one 7B recipe on 2026-10-09.** `k2-horizon-7b-fp8-uno-sglang`
is the single shipped 7B arm: it is fastest in the lane single-stream at d0 (32.4 vs the
plain 7B's 21.3 and NGRAM's 27.9) and at aggregate c=8 (145.5/90.2 vs plain 120.1/68.8 and
NGRAM 123.9/88.3), and accuracy-lossless on the shared instrument (all gaps within ±3
items ≈ one SE on n=200). NGRAM's only edge — single-stream d8k 28.6 vs 27.1 — is inside
the lane's own 7-25 % inter-boot noise floor. Both siblings, `k2-horizon-7b-fp8-sglang`
and `k2-horizon-7b-fp8-ngram-sglang`, moved to `attic/ifm/arms/` with their contents
unchanged.

Before this session **every recipe was theory-only** — none had booted — and two
load-bearing claims turned out wrong (see §4). Treat the WORK docs as the model, not
as ground truth; the journal is where the falsifications are recorded.

## 2. Evidence locations

| question | where the answer lives |
|---|---|
| what a recipe *is* and why | §9 (the research record the recipe comments used to carry) plus the recipes' own short tunable comments |
| the model / roofline / byte census | `K2-*-MODEL-OPTIMIZATION-WORK.md` — **git-ignored and absent from this tree**; the surviving numbers are in `README.md`, `NOTES.md`, `AGENTS.md` §9 and the recipes' own tunable comments |
| what happened, dated | `K2-*-JOURNAL.md` (same: git-ignored by design, may be absent) |
| the measured UNO campaign artifacts (per-arm `--output` JSON) | `.scratch/ifm/perf-2026-10-09/` (git-ignored) |
| cross-model findings, node state | the lane's `COOP.md` — a git-ignored working ledger that is **not tracked** (removed from the tree 2026-10-10) |
| the withdrawn sub-lane (recipes, mod, guards, byte arithmetic) and the two retired 7B arms (recipes) | `attic/ifm/` (`ARMS-MANIFEST.md`) |
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
- **`--served-model-name` must not be `{model}` (fixed 2026-10-13).** Both K2 arms
  carried NO `--served-model-name`, so sglang defaulted the id to the `--model-path`
  value — the prepared snapshot path on a launch. Both now declare `served_model_name`
  (`IFM/K2-Horizon-0.9B`, `IFM/K2-Horizon-7B-FP8`) and pass
  `--served-model-name {served_model_name}`. Receipts: 0.9B boot
  `e2b91b75cf01d3ab_8ed3ce77d78f` on `.34` (`GET /v1/models` → `IFM/K2-Horizon-0.9B`,
  131072 ctx, TTR 71.1 s); 7B-Uno boot `ff7c9715c406eee7_64af2f7668b6` on `.35`
  (→ `IFM/K2-Horizon-7B-FP8`, 131072 ctx, TTR 170.2 s). The 7B's UNO adapter is an
  internal draft LoRA, not a second served id.

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
   JSON; a `length` is a truncated response, not a wrong answer.** See §8 traps.
5. **"UNO needs a second attention backend + second CUDA-graph pool, hence
   `gpu_memory_utilization` 0.82."** Wrong for this recipe — that is TREE UNO.
   In LINEAR mode (`eagle_topk` 1) `uno_worker_v2.py` gates both on tree_mode:
   `init_attention_backends()` builds the F-wide backend only under
   `if self.tree_mode:`, and `init_cuda_graphs()` (`if not self.tree_mode ...
   return None`) captures no private graph. Likewise "two extra buffers per
   request" was wrong — linear mode has ONE proposal workspace, not a
   per-request private backend. The 0.82 headroom is still right, for the
   resident LoRA slots (pool capacity 2) and the [batch, F, 250624] draft/verify
   logits.

## 5. Guard suite

Two stdlib-`unittest` modules, no PyYAML (they parse recipe text and strip
whole-line comments first):

| module | count | scope |
|---|---|---|
| `tests/test_ifm_recipes.py` | 18 | 0.9B: no `fa3`, dtype, revision, container floor, flag map |
| `tests/test_k2_7b_recipes.py` | 61 | 7B + Uno + NGRAM: banned flags for UNO, mod existence/order, declaration-stash trap |
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

A **second archival criterion** joined the first on 2026-10-09: an **arm that loses the
best-overall comparison** is retired even though nothing is wrong with it — the plain 7B
and NGRAM arms moved to `attic/ifm/arms/` because UNO beat them at every measured point
outside the noise floor, not because their question closed. Both criteria send the file to
`attic/ifm/` with a manifest row. The `zz-` prefix convention is unaffected: it still marks
a non-shippable probe arm, and says nothing about which criterion archived a file.

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

## 9. Recipe research record (moved from recipe comments, 2026-10-10)

The root `AGENTS.md` "Recipe comments" rule took effect 2026-10-10: a recipe's
comments explain only non-obvious tunables; measurement history, receipts,
retraction registers and provenance essays live in the lane docs. Both recipe
comment blocks were moved here on that date. Content already carried by
`README.md` / `NOTES.md` / §1 was **not** duplicated — the tables below are the
index (line numbers are pre-edit YAML lines), and the subsections carry what
had no other durable home.

### Mapping — `k2-horizon-0.9b-bf16-sglang.yaml`

| was (lines) | content | lives at |
|---|---|---|
| 3–10 | SHA-pin mechanism | kept (trimmed) in the recipe; §3 |
| 17–33 | MEASURED banner: 77.599/67.277 (cv 0.10/0.07 % over 5 runs, `bench_ab57b6d3d164`, decode-triage); accuracy 83.8/87.0/66.5; the 2026-10-08 instrument artifact | `NOTES.md` 2026-10-08 session + bench table; accuracy §1 / `README.md` §Accuracy; instrument §4.4; cv figures below (Checkpoint census) |
| 38–39 | model_params = body 0.98B + lm_head 98.7M | kept verbatim in the recipe |
| 50–68 | gpu_memory_utilization rationale | kept (trimmed) in the recipe; census + f=0.10 floor below |
| 71–83 | max_num_seqs KV arithmetic + scheduler ceiling | kept (trimmed) in the recipe; vram cross-check below |
| 85–91 | dtype spelled, not `auto` | kept (trimmed) in the recipe; migration provenance below |
| 93–128 | attention_backend fa3/flashinfer verification | kept (trimmed) in the recipe; full source verification below |
| 130–138 | kv_cache_dtype | kept (trimmed) in the recipe; fp8-KV coupling receipt below |
| 140–144 | chunked_prefill_size flag-map note | kept (trimmed) in the recipe; §3 |
| 146–164 | extra_args probe arms (5 arms + bench ids) | `README.md` §Arm sweep (all five rows); `--cuda-graph-max-bs` absence §8 |
| 186–341 | "WHY THIS FILE LOOKS THE WAY IT DOES" §§1–6 | below (Engine support history; No quantization flag; Dense path; 0.9B roofline; UNO-on-0.9B register; BOS/EOS negative result) |

### Mapping — `k2-horizon-7b-fp8-uno-sglang.yaml`

| was (lines) | content | lives at |
|---|---|---|
| 1–53 | MEASURED ARM banner: 12-boot campaign, F=8 32.4/27.1 (+52/+41 %), 145.5/90.2 at c8, max_num_seqs load-bearing, accuracy-lossless, "what is not established", evidence paths | §1 (promotion + consolidation), `README.md` §UNO arm (tables + honest limits), `NOTES.md` 2026-10-09 campaign + Sources |
| 56–61 | FP8 base vs vendor-validated BF16 pairing | kept (trimmed) in the recipe; below (The Uno adapter artifact) |
| 68–74 | adapter as second artifact + pin 669f041a… | kept (trimmed) in the recipe; adapter receipt below |
| 76–83 | bare `mods/NAME` form + order | kept (trimmed) in the recipe; §3 |
| 90–94 | model_params 9.0B = base + 0.35B adapter | kept (trimmed) in the recipe; adapter byte census below |
| 105–107 | UNO requires TP=PP=1 | kept verbatim in the recipe |
| 109–121 | 0.82 rationale; falsified "second backend + second graph pool" | kept (trimmed) in the recipe; register §4 item 5 |
| 124–133 | max_num_seqs 32 load-bearing | kept (trimmed) in the recipe; §3; falsified "two extra buffers" §4 item 5 |
| 136–148 | fa4 vs fa3 gate + mod | kept (trimmed) in the recipe; mod design note below |
| 151–155 | page_size 1 vs 128 | kept verbatim in the recipe |
| 157–158 | chunked_prefill_size modest | kept verbatim in the recipe |
| 160–187 | speculative block (builtin, linear vs tree, F=8, mandatory) | kept (trimmed) in the recipe; break-even derivation `NOTES.md` 2026-10-09 |
| 215–301 | Q0–Q4 + "THINGS THAT WILL LOOK LIKE BUGS" | below (FA4 importability; Mod design note; Linear boot requirements; FP8+Uno pairing; Break-even; Looks-like-bugs) |

### 0.9B — record with no other home

**Checkpoint census (was the `gpu_memory_utilization` comment).** VERIFIED from
the artifact rather than the card: `model.safetensors.index.json`
`metadata.total_size` = 2,156,571,648 B; 255 tensors; one shard; BF16 only
(`validation.json` `"dtypes": ["BF16"]`). The whole engine (2.16 GB weights +
full-length 131k KV pool of 7.0 GiB + runtime) floors out near f = 0.10
(`K2-09B-MODEL-OPTIMIZATION-WORK.md` §4.1, read from the v0.5.20 tree —
git-ignored), so dropping to 0.10–0.30 stacks several 0.9B engines on one box.
`--max-total-tokens` (not in sparkrun's flag map; ride `extra_args`) pins the
pool exactly, e.g. `--max-total-tokens 262144` for a deterministic 2×131k
(14 GiB) pool per engine. The MEASURED banner's per-run cv figures: 77.599 t/s
at cv 0.10 % and 67.277 t/s at cv 0.07 % over 5 runs each
(`bench_ab57b6d3d164`, re-derived 2026-10-09 from the surviving artifact).

**VRAM cross-check (was the `max_num_seqs` comment).** `sparkrun recipe vram`
independently agrees from the checkpoint's own config: 100.8 left for KV at
f = 0.85, max context 1,888,154 tokens, a 14.4× multiplier (1,888,154 /
131,072 = 14.41, i.e. ~14 concurrent 131k sequences or ~57 concurrent 32k
sequences; the GiB-vs-GB question is a non-issue: the ratio is 14.40 either
way). With `hidden_size` 1536 the per-step GPU work is tiny, which makes
decode-step time launch- and sample-bound and leaves the single
scheduler/tokenizer process on the 10 fast cores (`taskset -c 5-9,15-19`) as
the real ceiling.

**dtype provenance.** The `float32` declaration is an artifact of the
K2Aurora→K2Horizon schema migration (`migration_manifest.json` weight_mode
"copy", `weights_reencoded` false; `validation.json` says the tensors are
BF16), so `auto` resolves through the "BF16 precision for BF16 models" rule on
a float32 declaration and can load 6.5 GB where 2.16 GB was intended. The
card's own recipe spells `--dtype bfloat16`.

**Attention-backend verification (full).** VERIFIED at v0.5.20 (identical on
main as of 2026-09-20). `layers/attention/attention_registry.py:227-235`
asserts `(major == 8 and not runner.use_mla_backend) or major == 9`; GB10
reports (12, 1), so the assert fires at backend construction — after weight
load, before the port binds. `utils/common.py:329-333` names this chip
explicitly (`is_sm121()` … "GB10 (DGX Spark and OEM equivalents)"); the qwen4
lane records three separate SM121 dead-ends of exactly this shape (fa3-style
hard gates, and `auto` resolving to a kernel SM121 cannot run — qwen4
§7g/§12). The cards' "BF16, TP=1, FlashAttention-3" is H100/H200 guidance; the
model card reports its own numbers on Hopper-class hardware, so it is not
wrong, it is just not a Spark. flashinfer is what sglang's own auto-default
picks: `arg_groups/model_override_base.py:347-352` returns "flashinfer" for a
non-MLA model whenever flashinfer imports and the model has no attention
sinks (this one has none), because the fa3 branch is gated on
`is_hopper_with_cuda_12_3` and the trtllm_mha branch on `is_sm100` — both
False on major 12. The explicit value agrees with the default instead of
fighting it. Deliberately NOT `auto`: qwen4 §12 found the auto-default
silently landing on a dead/slow backend with "no warning or log line" on this
exact chip. fa4: FlashAttentionBackend supports `fa_impl_ver=4` and at v0.5.20
`flashattention_backend.py:284-291` imports the dedicated SM12x kernel
(`kernels/ops/attention/flash_attention_v4_sm120.py`) when
`device_capability[0] == 12`; the `page_size=128` forcing in
`overrides.py:_fa4_page_constraint` is gated on is_sm100 (major 10) so it does
NOT fire here. Measured 2026-10-09: boots and serves, inside the 7-25 % noise
floor (`README.md` §Arm sweep) — a viable alternative, not a speed win.

**fp8-KV coupling.** `fp8_e4m3` is a legal value in this image
(`arg_groups/fields/model.py:196-214`) and would halve KV to 28 KiB/token; the
only fp8-KV/attention interaction sglang encodes explicitly is
fa3 + fp8_e5m2 → triton (`overrides.py:1324-1331`), i.e. the two axes are
coupled and each new combination is its own kernel path.

**Engine support history (banner §1).** sglang#37654 "[Model] Add native IFM
K2 Horizon serving support" merged 2026-09-03T08:39:44Z (merge commit
3bac084d4e49); first released tag v0.5.20, published 2026-09-18T22:41:33Z.
VERIFIED by git-tree listing: `python/sglang/srt/models/xllm.py` exists at
v0.5.20 and is ABSENT at v0.5.19 and every earlier tag — so this lane must
never pin an older image, and a moving `dev-cu13` tag is not a version
guarantee. `EntryClass = [XllmForCausalLM, K2HorizonForCausalLM]`
(xllm.py:1914). vLLM is not available: the card's vLLM quickstart cites PR
#53806 and "commit d9fd5f11"; that PR is CLOSED UNMERGED (state=closed,
merged=false, last updated 2026-09-03, 10 files / 2611 additions), so the
cited commit lives in a fork and no image in this registry serves this model
with vLLM. The card's vLLM block is additionally not valid JSON — the cited
`--hf-overrides '{"rope_parameters":{rope_type: yarn, ...}'` has unquoted
inner keys and is missing a closing brace (json.loads fails at char 20). Both
parsers exist in the pinned image under one name:
`parser/reasoning_parser.py:2174` and
`function_call/function_call_parser.py:84` both map "k2_horizon" →
K2V3Detector; the card's SGLang block names only the reasoning parser, its
best-practices item 5 asks for both, so both are set. There is deliberately NO
`--enable-auto-tool-choice`: it is a vLLM flag, and sglang v0.5.20 has no such
server arg (absent from `arg_groups/fields/*.py`, `server_args.py`,
`arg_groups/speculative_hook.py`) — copying the card's vLLM block verbatim
gives an "unrecognized arguments" launch failure. Same verdict for
`--hf-overrides`, which sglang spells `--json-model-override-args`. Tool-call
format and reasoning depth are CLIENT-side, not server flags:
`chat_template_kwargs` `{"tool_call_format": "json"|"xml"|"xml_typed"}`
(default xml) and `{"reasoning_effort": "high"}` per request. The card is
emphatic that every reported number uses high effort and that at least 32,768
output tokens must be allowed — "truncated reasoning is a failed response, not
a shorter one". A benchmark capped at 1k output tokens measures this model
wrong, not fast.

**No quantization flag (banner §2).** The checkpoint carries no
`quantization_config` and sglang has no packed-weight mapping for this family
beyond qkv/gate_up stacking (`xllm.py:1692-1695` plus
`_xllm_stacked_params_mapping` at :791), so a quantized load fails inside
weight loading rather than with a clean refusal. It is also the wrong lever at
2.16 GB. VERIFIED there is no quantized 0.9B to reach for: the family's -FP8
repos cover 7B, 32B, MoVA-36B-A4B and 375B-A23B only, and
`IFM/K2-Horizon-0.9B-GGUF` holds one file, K2-Horizon-1B-BF16.gguf at
2,159,424,896 B, "stored in their original BF16 precision", with llama.cpp
support "in progress" behind the MBZUAI-IFM fork. sglang#39509 "[Model] Add
native block FP8 loading for K2 Horizon MoVA" (open 2026-09-17) is the
family's first real quant path and is MoVA-only.

**Dense path (banner §3).** The dense branch asserts exactly what this
checkpoint declares: `mova_num_experts_per_tok == 0` and `num_experts` /
`num_experts_per_tok` / `num_shared_experts` == 0 (xllm.py:238-275),
`query_key_norm` false (:276-280), `sliding_window` null and
`use_sliding_window` false (:281-286), no attention gate (:287-298). Passing
all of them routes to XllmAttention, which uses QKVParallelLinear +
RowParallelLinear with the real quant_config and one fused qkv GEMM
(:1113-1134). The MoVA/gated branches instead allocate q/k/gate/o as four
separate ColumnParallelLinears with quant_config hard-set to None
(:1264-1300) and raise on any quant_config at :1229-1232 — same family, very
different kernel path, which is why the 36B-A4B MoVA work must not be used to
predict this recipe's numbers. `rope_head_dim` (64) == `head_dim` (64), so
`use_xllm_partial_rope` is False and the permute/split/cat partial-RoPE branch
(:1160-1197) is dead code for this checkpoint. YaRN is accepted natively: the
dense path allows `rope_type` in {default, yarn} (:330-334) and the
checkpoint's `rope_parameters` keys are a subset of the supported set
(:375-391 — attention_factor, beta_fast, beta_slow, factor,
original_max_position_embeddings, rope_theta, rope_type, truncate). Values:
rope_type yarn, factor 16, original_max_position_embeddings 8192
(16 × 8192 == 131072), attention_factor 1.2772588722239782, beta_fast 128,
beta_slow 4, truncate true, rope_theta 1e6 — so 128k needs NO
`--json-model-override-args`, retiring the risk the card's vLLM block invites.
The card's SGLang block passes `--revision 9b9ec1f7e17f…`, an *sglang*
commit-ish rather than a revision of IFM/K2-Horizon-0.9B (that repo's refs are
pretrain_*, mid_1_*, mid_2_*, rl_*, main); copying it offline yields
LocalEntryNotFoundError (also §8). `--trust-remote-code` is kept although the
engine ships its own thin K2HorizonConfig ("Keeping these classes
intentionally thin lets SGLang select its native runtime without importing
checkpoint-provided Python code", configs/k2_horizon.py docstring; registered
at configs/__init__.py:37), so the checkpoint's auto_map is never imported; it
costs nothing and may matter to the tokenizer path.

**0.9B roofline (banner §4).** NVIDIA publishes 273 GB/s for the GB10's
256-bit LPDDR5X. At 2.157 GB of weights the single-stream decode ceiling is
273 / 2.157 = 126.6 tok/s, and KV only matches the weight read at ~37.6k
tokens of context (56 KiB/token × L == W). Computed ceilings, one stream, bf16
KV: 123 t/s @ 1k, 114 @ 4k, 88 @ 16k, 63 @ 37.6k, 46 @ 64k, 28 @ 128k (fp8 KV:
68 @ 64k, 46 @ 128k). Arithmetic intensity at batch 1 is 1.0 flop/byte against
a bf16 ridge near 900 — memory-bound by three orders of magnitude; prefill and
aggregate batch throughput are the only places compute matters. Pre-registered
expectation: 60-80 % of those ceilings (the qwen4 journal's measured MoE
decode reached only ~30 % of peak on a far larger model). Script:
`.scratch/ifm/k2_09b_model.py` (git-ignored).

**UNO-on-0.9B register (banner §5; premise falsified for the 7B).** The
historical claim — "UNO cannot run on this chip yet, and there is no UNO
recipe to write" — is FALSIFIED for the 7B (§4 item 1: the probe mod relaxes
the gate) but was never re-opened for the 0.9B. Kept because the details shape
a recipe *when* the gate lifts at this size. IFM/K2-Horizon-0.9B-Uno is a PEFT
conditional-LoRA diffusion drafter (adapter_config.json: r=128, lora_alpha
2048, dropout 0.05, targets q/k/v/o plus gate/up/down; conversion_summary.json:
392 tensors, bf16, base_weight_matches_public_repository true — pairs with the
0.9B base at the pre-2026-10-14-re-pin SHA 9fa6faa5). SGLang native UNO: sglang#37667 "[Speculative Decoding]
Add native UNO serving support" merged 2026-09-03T12:08:42Z; `UNO` is a
builtin speculative_algorithm in v0.5.20 (arg_groups/fields/spec.py:37-41)
with --uno-lora-path, --speculative-num-draft-tokens = verify width Q,
--speculative-eagle-topk = candidate K (>1 selects tree mode) and
--speculative-num-steps (draft width F = steps + 1). Stock gate:
`arg_groups/speculative_hook.py:503-508` raises unless (prefill, decode) ==
("fa3","fa3") — unsatisfiable on GB10 (§3). Refusals that shape a UNO recipe
whenever the gate lifts: (tp,pp) != (1,1); DP attention or context parallel;
public Multi-LoRA; any attention backend other than fa3 for BOTH prefill and
decode; --speculative-draft-model-path; --enable-deterministic-inference;
--enable-strict-thinking; --speculative-use-rejection-sampling; and in tree
mode PDMux, two-batch overlap, non-1.0 accept thresholds, Q > 128, Q*K > 2048,
and Q beyond EAGLE's parent-list ABI cap Q-1 <= K*(F-2)+1.
--enable-mixed-chunk is force-disabled with a warning. Per request
(speculative/uno_validation.py) it rejects min_p, any grammar / structured
output, returned logprobs, return_hidden_states, penalties, logit_bias,
custom logit processors and request-selectable LoRA — a second, independent
constraint even on Hopper: Uno and schema-constrained tool calling cannot
coexist, and this model's card actively pushes tool calling. The usable
lossless arm on this chip is `--speculative-algorithm NGRAM`:
`_handle_ngram` (spec_hook.py:999-1085) imposes NO attention-backend
requirement and only restricts eagle_topk>1 + page_size>1 to flashinfer.
(NGRAM was measured on the 7B and retired — `README.md` §UNO arm.)

**Negative result: tokenizer BOS/EOS (banner §6).** The tokenizer's bos/eos
render as `"<|begin_of_text|>"` with invisible padding when the raw JSON is
displayed through some tools, which reads as zero-width spaces (U+200B) inside
the special-token strings and would break engine-side special-token matching.
A per-codepoint dump of `tokenizer_config.json` `added_tokens_decoder` entries
0 and 1 and of `special_tokens_map.json` REFUTES it: every codepoint is plain
ASCII; the characters came from the display path, not the repo. The real chat
markers in this vocab are ids 64018/64019 `<|ifm|im_start|>` /
`<|ifm|im_end|>`; ids 0/1 are the base-model BOS/EOS.

### 7B — record with no other home

**The Uno adapter artifact.** IFM/K2-Horizon-7B-Uno @
669f041aab04fad836e757ede9a028058b064996; `adapter_model.safetensors` =
1,396,763,616 B (0.35B params); VERIFIED via HF API 2026-09-20.
`adapter_config.json` declares `base_model_name_or_path` IFM/K2-Horizon-7B
(BF16), so the vendor-validated pairing is BF16+Uno; the FP8+Uno substitution
is the second thing the probe validated (on a bandwidth-bound box the base's
per-step read dominates and BF16 doubles it).

**FA4 importability (banner Q0).** ANSWERED YES (2026-09-21, no GPU). The
default path imports the VENDORED
`sglang.kernels.ops.attention.flash_attn.cute` (pip `flash_attn.cute` only
under `SGLANG_INKLING_FA4_USE_PIP=1`); in a real sglang image both import and
`is_flash_attention_v4_available()` is True. `flash_attention_v4.py` raises
"FlashAttention-4 CUTE is not available. Install flash-attn-4 …" when the
selected CUTE package is absent; the mounted mod probes this first and logs
it, so the answer is in the mod log whether or not the server starts. Whether
the FA4 kernels are COMPILED for sm_121 was the open runtime question —
answered: they run (`README.md` §Arm sweep).

**Mod design note (banner Q1).** `recipes/ifm/mods/probe-uno-fa4-sm121` replaces exactly
the literal `("fa3","fa3")` comparison in `_handle_uno` and nothing else. It
deliberately does NOT touch the fa3 capability assert in
`attention_registry.py`, so that if UNO truly needs FA3 it fails loudly rather
than reaching an uncompiled kernel.

**Linear boot requirements (banner Q2).** `_handle_uno`'s other requirements
are all satisfied by the recipe: CUDA, TP=PP=1, no draft-model-path, no public
LoRA, no deterministic inference, no strict thinking, no rejection sampling;
mixed chunk is forced off by the handler itself. Linear mode builds NO second
attention backend and captures NO second CUDA-graph pool (both gated on
tree_mode in `uno_worker_v2.py`: init_attention_backends, init_cuda_graphs).
Passing `--speculative-num-steps`: linear mode forces it to 1; a passed value
gets a warning and an override.

**FP8+Uno pairing (banner Q3).** Source basis: neither `uno_lora.py` nor
`uno_validation.py` contains any dtype or quantization check; `uno_lora.py`
builds `LoRAManager(..., dtype=model_runner.dtype, lora_backend="uno_cublas")`
with pool capacity 2 — slot None = base, slot `__uno_draft__` = base + LoRA;
`lora/layers.py` computes the base via `base_layer.quant_method.apply(...)`
and adds the low-rank term afterwards, so an FP8 base with a bf16 LoRA is
structurally coherent. "Nothing forbids it" was NOT "it works" at write time —
the 2026-10-09 campaign then measured it working (accuracy-lossless,
`README.md` §UNO arm). Contingency retained: if a future pairing fails, the
correct conclusion is "Uno needs the BF16 base", and the recipe swaps `model:`
to IFM/K2-Horizon-7B @ eca6bb608969151ffa45b10e1955d39aa73baf27 — which
roughly doubles the per-step weight read and moves break-even accept to about
3.6 tokens, making Uno much harder to justify on Spark.

**Break-even and the card figure (banner Q4).** Break-even mean accept is 2.07
tokens/step on the FP8 base (plain 9.00 GB/token; UNO step 2×9.00 + 0.698 LoRA
= 18.70 GB); measured accept length 2.53 (F=2) / 2.95 (F=4) / 3.10 (F=8) —
above break-even (tables: `README.md` §UNO arm, `NOTES.md`). The card's
5,255 tok/s system figure is an H200 number on a box that is not
bandwidth-bound at 7B and was never the transferable quantity — acceptance
was, and it survived the move to GB10.

**Things that will look like bugs and are not (banner list).**

- No `--enable-lora`: UNO rejects public Multi-LoRA ("UNO does not support
  public Multi-LoRA serving"); it loads its own private adapter internally and
  pins both slots resident. Adding `--enable-lora` to expose the LoRA API
  breaks it.
- No `--enable-deterministic-inference`, no `--enable-strict-thinking`, no
  `--speculative-use-rejection-sampling`: each is an explicit ValueError in
  `_handle_uno`. The rejection-sampling one is the trap: it is the usual way to
  make spec decode "lossless", but UNO "manages its own stochastic
  verification" and refuses the flag.
- A 250,624-token vocabulary makes the draft/verify logit tensors large: the
  draft pass materializes [batch, F, vocab] logits — at F=8, batch 32 that is
  ~257 MB of fp32 logits per step (F=4, batch 8 was ~32 MB) — well within the
  0.82 pool, but it is why UNO's memory behaviour does not look like EAGLE's,
  and why a wider F or a lower pool headroom is a real cost.
- Per-request features UNO refuses (`uno_validation.py`): min_p,
  grammar/structured output, returned logprobs, returned hidden states,
  sampling penalties, logit_bias, custom logit processors, request-selectable
  LoRA. An eval harness setting any of these gets the request rejected at
  admission, which looks like a server error and is a harness problem.


*Evidence over memory: if this file and a boot log disagree, the log wins — and this
file gets corrected.*

---

## From recipes/ifm/README.md (2026-10-14)

The lane README was reduced to a shipped-recipes-only summary on 2026-10-14.
Everything cut from it — the read-this-first banner, the re-pin narrative, the
TP=1 rationale, the 2026-10-08/09 measurement histories, the arm sweeps, the UNO
promotion campaign, the accuracy runs and the archived-material prose — is kept
verbatim below.

> **Read [`AGENTS.md`](AGENTS.md) before working in this directory.** It carries the
> constraints, the guards, and the measurement discipline. This file is the recipe
> summary; the deep research record (`K2-*-MODEL-OPTIMIZATION-WORK.md` / `K2-*-JOURNAL.md`)
> is git-ignored by design and absent from a fresh checkout — the measured numbers that
> survive are the ones in this file, in [`NOTES.md`](NOTES.md), in [`AGENTS.md`](AGENTS.md)
> §9, and in the recipes' own tunable comments.

Both `model_revision:` pins were refreshed to `main` on 2026-10-14 — `0.9B` →
`383cb66347be…`, `7B-FP8` → `ea739ec816e0…`. The 7B delta is the model card
only; the 0.9B delta is the card plus the two chat templates, and every
behavioural cell (perf and accuracy) reproduced within the lane's noise floor
on the same lanes (`NOTES.md`, 2026-10-14 session).

**Retired 7B arms.** The plain 7B (`k2-horizon-7b-fp8-sglang`) and the NGRAM arm
(`k2-horizon-7b-fp8-ngram-sglang`) were retired on 2026-10-09 and now live in
[`attic/ifm/arms/`](../../attic/ifm/ARMS-MANIFEST.md) — see §Archived material and
`attic/ifm/ARMS-MANIFEST.md`. Their measured numbers below are kept as the provenance
for why the UNO arm was selected.

C1 t/s is single-stream (concurrency 1) aggregate decode, read from
`benchmarking/decode-triage.yaml` per-cell JSON — not the printed sparkrun table.

## Why every lane is TP=1

The 0.9B and 7B artifacts are 2.16 and 11.05 GB against a 128 GB unified box. TP buys
no capacity, splits an 8-KV-head GQA layout across ranks, and adds an all-reduce per
layer over a memory subsystem that is already the bottleneck. TP=1 is the only shape
worth having.

## Performance (measured)

First hardware session, 2026-10-08. Three results each falsified a lane claim that had
been argued the other way in the theory documents:

- **NGRAM speculative decoding pays on the dense 7B** (+31 % at d0, +49 % at d8k in the
  2026-10-09 remeasure), and its rate *rises* with depth as n-gram matching improves.
- **UNO boots and serves** with accept len 3.60 on its first probe — clearing the
  modelled break-even of ~2.07, so the diffusion draft is a win, not "blocked at every
  size". (That early 37.7 t/s figure was one run on the tg=32 `reconcile-headline`
  profile and is **not** comparable to the tg=128 numbers below; the 2026-10-09
  campaign replaced it with the table in §UNO arm.)
- The 7B measured **~16 % below** its modelled roofline at c=1 — the model counted only
  the weight read and ignored per-step overhead.

The `K2-*-MODEL-OPTIMIZATION-WORK.md` / `K2-*-JOURNAL.md` docs these sections once cited
are git-ignored and **not present in this tree**; where their numbers matter they have
been folded into the sections above, `NOTES.md`, and `AGENTS.md`.

### Arm sweep (2026-10-09)

A second session swept single-knob decode arms on the same `decode-triage.yaml`
profile (tg=128, 5 runs, c=1), one boot per arm, all in the same window. **One boot
per arm cannot rank arms:** the registry's own profile metadata puts the inter-boot
noise floor on this hardware at **7-25 %** for byte-identical boots, so a gap under
~7 % carries no information. Every arm below lands inside that floor.

0.9B (BF16), d0 / d8192:

| arm | d0 t/s | d8192 t/s | bench id |
|:--|--:|--:|:--|
| control (no overrides) | 77.339 | 67.036 | `bench_66937856b7bb` |
| `--page-size 64` | 77.652 | 67.376 | `bench_ddccb2bb32d1` |
| `--page-size 128` | 77.623 | 67.282 | `bench_f511e9d7fba3` |
| `--attention-backend fa4` | 78.371 | 67.735 | `bench_8ec5a1920280` |
| `--cuda-graph-max-bs 32` | FAILED TO START | — | `bench_62b814092b29` |
| `--cuda-graph-max-bs-decode 32` | 77.722 | 67.426 | `bench_bf98a3f39ef5` |

`--attention-backend fa4` is the notable arm: it **boots and serves** — the SM120 FA4
kernel runs on this chip. `--cuda-graph-max-bs` **does not exist** in sglang v0.5.20
(argparse rejects it and the server never binds its port); the real flags are
`--cuda-graph-max-bs-decode` / `--cuda-graph-max-bs-prefill`.

7B-FP8, same profile and window, one node, d0 / d8192:

| arm | d0 t/s | d8192 t/s | bench id |
|:--|--:|--:|:--|
| cutlass (2026-10-08) | 21.209 | 19.156 | `bench_baa8a8610893` |
| `--fp8-gemm-backend auto` | 21.170 | 19.104 | `bench_83c087620bb9` |
| `--fp8-gemm-backend triton` | 20.609 | 18.628 | `bench_913796c734d4` |
| `--page-size 64` | 21.171 | 19.106 | `bench_16e4daa54660` |
| `--kv-cache-dtype fp8_e4m3` | 21.362 | 20.262 | `bench_0993e4379274` |
| 512K (`max_model_len=524288`) | 21.1885 | 19.1298 | `bench_6518bc429d05` |

Every 7B arm is inside the same 7-25 % floor; the widest single gap (kv-cache fp8 at
d8k, 20.262 against cutlass 19.156) is ~5.8 % and is not resolvable by one boot per
arm, so no arm is ranked.

### UNO arm (2026-10-09)

`k2-horizon-7b-fp8-uno-sglang` was **promoted from probe to a shipped arm** on
2026-10-09 after a 12-boot campaign. It is the fastest arm in the lane: native
SGLang UNO speculative decoding (the 7B target plus the `K2-Horizon-7B-Uno`
conditional-LoRA diffusion draft), verified by the target, so it is lossless by
construction. It needs **two mods** — `provide-uno-lora-k2-horizon-7b` (fetches
the draft adapter, a second artifact `model:` cannot carry) and
`probe-uno-fa4-sm121` (relaxes UNO's literal `("fa3","fa3")` gate, since GB10
cannot build `fa3`) — and runs `--attention-backend fa4`.

Single-stream (`decode-triage.yaml`, tg=128, c=1; means over clean boots, same
window; noise floor 7-25 %):

| arm | d0 t/s | d8192 t/s | accept len | boots |
|:--|--:|--:|--:|--:|
| plain 7B (control) | 21.3 | 19.2 | — | 7 |
| UNO F=2 | 26.4 | 22.4 | 2.53 | 2 |
| UNO F=4 | 30.8 | 25.6 | 2.95 | 6 |
| UNO **F=8** (shipped) | 32.4 | 27.1 | 3.10 | 6 |
| NGRAM | 27.9 | 28.6 | 1.37 | 4 |

The `plain 7B (control)` and `NGRAM` rows are the two arms retired on 2026-10-09 (now
`attic/ifm/arms/`); they are kept here as the comparison that selected UNO.

So UNO F=8 is **+52 % / +41 %** over the plain 7B. Accept length (2.53 → 3.10)
clears the ~2.07 break-even of the weight-read model and saturates by F=8.

Aggregate (`concurrency-sweep.yaml`, tg=256):

| arm | c1 d0/d8 | c4 d0/d8 | c8 d0/d8 |
|:--|--:|--:|--:|
| plain | 21.2 / 19.1 | 79.6 / 51.0 | 120.1 / 68.8 |
| NGRAM | 27.8 / 31.2 | 88.4 / 65.5 | 123.9 / 88.3 |
| UNO F=4, `max_num_seqs 8` | 29.7 / 25.0 | 98.6 / 72.1 | **97.5 / 70.5** |
| UNO F=8, `max_num_seqs 32` (shipped) | 32.7 / 27.2 | 96.7 / 71.3 | **145.5 / 90.2** |

**`max_num_seqs` is load-bearing here.** At 8 the arm flattens at c=8 (97.5,
below its own c=4) while plain reaches 120; at 32 it scales to 145.5, the best
c8 figure in the lane. The cap is a scheduler admission limit, not memory — and
a guard (`tests/test_k2_7b_recipes.UnoConcurrencyCap`) now refuses to let it be
lowered. At c=1 the two depths NGRAM still leads (31.2 vs 27.2 at d8192).

**Honest limits.** Accuracy was scored at F=4/seq=8; F=8/seq=32 change the draft
geometry, not the verification, so quality is expected to hold but was not
re-scored. The 512K window was proven on the plain recipe, not on this arm.
One boot each for the concurrency cells — the shape is clear, the exact number
is not.

## Accuracy (measured)

Re-measured 2026-10-09 after the harness was fixed (see §4 of [`AGENTS.md`](AGENTS.md)):
greedy (temperature 0), `reasoning_effort` = the template default `high`, seed 1234,
one item set per benchmark.

| Benchmark (0-shot) | 0.9B (BF16) | 7B-FP8 | 7B-FP8 NGRAM | 7B-FP8 Uno |
|:--|--:|--:|--:|--:|
| House battery — total (n=37) | 31/37 = 83.8 % | 36/37 = 97.3 % | 36/37 = 97.3 % | 36/37 = 97.3 % |
| GSM8K (n=200) | 174/200 = 87.0 % | 188/200 = 94.0 % | 187/200 = 93.5 % | 190/200 = 95.0 % |
| ARC-Challenge (n=200) | 133/200 = 66.5 % | 178/200 = 89.0 % | 177/200 = 88.5 % | 175/200 = 87.5 % |

The `7B-FP8` and `7B-FP8 NGRAM` columns come from the two arms now in `attic/ifm/arms/`.
The two 7B spec arms were scored on the same instrument and item sets: **NGRAM and
Uno are each within ±3 items (about one SE on n=200) of the plain 7B on every
benchmark**, so neither trades accuracy for its speed win — both are lossless, not
a quality trade. That closes the lane's last quality gap.

These **replace** the 2026-10-08 run (0.9B 72.97 / 63.50 / 0.00; 7B 89.19 / 87.50 /
0.00). Those figures were **floors, not measurements**: the harness sent
`chat_template_kwargs={"enable_thinking": false}`, but neither K2-Horizon template
contains `enable_thinking` — both key reasoning on `reasoning_effort` — so the key was
ignored and every reply opened a reasoning block. ARC's cap was 16 tokens, so all 200
ARC items returned `finish_reason: length` with empty content: 0.00 % by construction.
The harness now has an additive `--reasoning-effort` flag and sized caps (house 1024 /
gsm8k 2048 / arc 1024), and records a `finish_reasons` histogram plus an
`empty_replies` count in every summary. **A `finish_reason: length` record is a
truncated response, not a wrong answer** — read the histogram before quoting any
figure.

## Archived material

Two things live in [`attic/ifm/`](../../attic/ifm/ARMS-MANIFEST.md), each with a
manifest row:

- The `MoVA-36B-A4B` sub-lane was withdrawn on 2026-10-08 — measured working on
  hardware, but too slow to justify the compute — and everything of it lives there:
  the four recipes, their FP8 gate mod, the guards and the byte-arithmetic helper,
  plus the measured numbers.
- The two retired 7B arms — `k2-horizon-7b-fp8-sglang` and
  `k2-horizon-7b-fp8-ngram-sglang` — were retired on 2026-10-09: UNO is faster at both
  d0 and c=8 and accuracy-lossless on the shared instrument, and NGRAM's only edge
  (single-stream d8k) is inside the lane's 7-25 % inter-boot noise floor. Their recipe
  files moved to `attic/ifm/arms/` with their contents unchanged; their measured
  numbers above are the evidence for the selection.

## Recipe comment archive (2026-10-14)

The root `AGENTS.md` "Recipe comments" rule was applied to the two shipped IFM
recipes on 2026-10-14: a `#` comment stays in the YAML only when an operator who
knows sparkrun but not this model would get the value wrong without it. Everything
else — provenance, byte arithmetic, measured numbers, arm narratives, cross-lane
references — is archived below, verbatim, per recipe filename. The comments that
**stayed** in each YAML are marked `[kept]`; the rest were removed from the file
and are reproduced here in full.

### `k2-horizon-0.9b-bf16-sglang.yaml`

**`model_revision`** (SHA-pin mechanism):

```
# SHA pin, not a branch (AGENTS.md §3). The offline container resolves `revision:`
# itself over a snapshots/<sha>/ cache with no refs/ entry, so an unpinned engine
# dies with LocalEntryNotFoundError *after* the weights synced to every host --
# exactly the pin-reaches-distribution-but-not-the-engine case the
# unpinned-model-revision warning exists to catch.
```

**`metadata.model_params`** (byte census):

```
# Total incl. lm_head; the body alone (what the card calls "0.9B-class") is
# 0.98B, lm_head being 64256 x 1536 = 98.7M of the 1,078,285,824 params.
```

**`defaults.served_model_name`** `[kept, trimmed]`:

```
# Never {model}: on a real launch sparkrun rebinds it to the prepared snapshot
# path, so the served model id would be the cache path (-n does not show this).
```

**`defaults.gpu_memory_utilization`** `[kept, trimmed]`:

```
# Not a residency requirement (weights 2.16 GB): buys CUDA-graph headroom. 0.85 is
# the GB10 SOLO ceiling (AGENTS.md); past ~0.85-0.90 a kernel or page-cache
# allocation OOM-panics the launch on unified memory; the engine floors near
# f=0.10 (AGENTS.md §9). sglang's cap is relative to FREE memory at THIS engine's
# boot, so budget absolute GiB per engine, or pin the pool exactly with
# extra_args: "--max-total-tokens 262144" (2x131k = 14 GiB). Overridable: -o
# gpu_memory_utilization=0.30.
```

**`defaults.max_num_seqs`**:

```
# KV = 56 KiB/token (2*8*64*2*28, bf16), so a full 131k sequence is ~7.0 GiB and
# the f=0.85 pool spans ~14 of them: 64 is a CPU/scheduler limit, NOT a memory
# one. Aggregate t/s climbs near-linearly with concurrency while per-request t/s
# falls (NOTES.md, 2026-10-08) -- measure both before raising.
```

**`defaults.dtype`** `[kept, trimmed]`:

```
# Spelled exactly as upstream validates it, NOT `auto`: config.json declares
# "dtype": "float32" (schema-migration artifact, AGENTS.md §9), so `auto` can load
# 6.5 GB where 2.16 GB was intended. The card's own recipe spells --dtype
# bfloat16. Do not "simplify" this to auto.
```

**`defaults.attention_backend`** `[kept, trimmed]`:

```
# flashinfer, NOT the fa3 the cards and the cookbook tell you to pass: FA3
# requires SM 8/9 (attention_registry.py:227-235) and GB10 reports (12,1), so fa3
# cannot be constructed (AGENTS.md §3 -- the cards are Hopper guidance).
# flashinfer is also sglang's own auto-default for major 12
# (model_override_base.py:347-352), but is spelled anyway: `auto` has silently
# landed on a dead/slow backend on this exact chip (qwen4 §12). fa4 is the
# alternative arm -- it boots and serves, inside the 7-25% noise floor (README.md
# arm sweep).
```

**`defaults.kv_cache_dtype`**:

```
# `auto` == model dtype == bf16. fp8_e4m3 is legal and would halve KV to 28
# KiB/token, but its accuracy gate is unmet (README.md arm sweep) -- treat fp8 KV
# as an arm whose gate is accuracy, not throughput. KV/attention combos are
# coupled kernel paths (AGENTS.md §9).
```

**`defaults.chunked_prefill_size`**:

```
# NOT in sparkrun's _SGLANG_FLAG_MAP (only `chunked_prefill` ->
# --chunked-prefill-size is), so it reaches sglang only through the placeholder
# below; `-o chunked_prefill_size=...` prints "unmapped" while still taking
# effect (AGENTS.md §3). Scheduler token budget per prefill batch; unrelated to
# any draft width.
```

**`defaults.extra_args`**:

```
# Escape hatch for one-off experimentation. Appended last so argparse resolves a
# repeated flag in favour of the override. Empty string is the no-op default;
# quoted so YAML keeps a str. Probe arms and measured results: README.md §Arm
# sweep; --cuda-graph flag spellings: AGENTS.md §8.
```

### `k2-horizon-7b-fp8-uno-sglang.yaml`

**`model_revision`** (FP8-vs-BF16 pairing):

```
# The FP8 checkpoint, deliberately: the Uno adapter's own adapter_config.json
# declares base IFM/K2-Horizon-7B (BF16), so the vendor-validated pairing is
# BF16+Uno -- on a bandwidth-bound box the base read dominates and BF16 doubles
# it, so the FP8+Uno pairing is itself part of what this arm validates (AGENTS.md §9).
```

**`mods:` header** `[kept, trimmed]` (adapter is a second artifact):

```
# The Uno adapter is a SECOND artifact: not a model, so `model:` cannot carry it
# and sparkrun's model sync only fetches `model:` -- the mod below lands it at a
# fixed container path. The pin lives in the mod's UNO_LORA_REVISION default
# (AGENTS.md §9): IFM/K2-Horizon-7B-Uno @ 669f041aab04fad836e757ede9a028058b064996.
```

**`mods:` entries** `[kept, trimmed]` (bare form + ordering):

```
  # Bare `mods/NAME`, NOT the scoped `@littlecedar/mods/NAME` form: the scoped form
  # resolves against the published registry clone, which does not carry these
  # unpublished mods (failed on the first real boot, 2026-10-08 -- AGENTS.md §3).
  # Order matters: the provide mod must land the adapter on disk before the server
  # starts, and both must run before sglang reads --uno-lora-path.
```

**`metadata.model_params`** (adapter byte census):

```
  # `model:` is the BASE model, so metadata describes the base: the estimator sizes
  # what it is told to serve. The Uno adapter adds 0.35B parameters (BF16-width
  # weights, AGENTS.md §9), which is why model_params is 9.0B and not 9.35B --
  # naming the adapter here would make the VRAM estimate claim FP8 width for them.
```

**`defaults.tensor_parallel`** `[kept, trimmed]`:

```
  # Hard requirement, not a tuning choice: _handle_uno raises
  # "UNO requires TP=PP=1." So tp>1 is a launch failure and there is no
  # multi-node variant of this recipe to write.
```

**`defaults.served_model_name`** `[kept, trimmed]`:

```
  # Never {model}: on a real launch sparkrun rebinds it to the prepared snapshot
  # path, so the served model id would be the cache path (-n does not show this).
```

**`defaults.gpu_memory_utilization`** `[kept, trimmed]`:

```
  # 0.82, three points under the 0.85 GB10 ceiling. Headroom for UNO's resident
  # target+draft LoRA slots (pool capacity 2) and the [batch, F, 250624] draft/verify
  # logits. In LINEAR mode UNO allocates NO second backend and NO second CUDA-graph
  # pool (both gated on tree_mode in uno_worker_v2.py) -- do not raise this to 0.85
  # on the theory that "UNO needs it"; measure first. The earlier "second backend +
  # second graph pool" justification was wrong for this file (AGENTS.md §4).
```

**`defaults.max_num_seqs`** `[kept, trimmed]` (the load-bearing admission cap):

```
  # *** max_num_seqs IS LOAD-BEARING FOR UNO. *** A scheduler admission cap, not a
  # memory limit: at 8 the arm FLATLINES at c8 (below its own c4) while the plain
  # 7B reaches 120; at 32 it scales to 145.5, the best c8 figure in the lane
  # (README.md §UNO arm). At c=1 the cap is immaterial. Do not lower it -- a guard
  # (tests/test_k2_7b_recipes.UnoConcurrencyCap) enforces a floor.
```

**`defaults.attention_backend`** `[kept, trimmed]` (the fa4 gate relaxation):

```
  # *** THE POINT OF THIS FILE. *** `fa3` -- what the UNO gate and the HF card ask
  # for -- cannot be constructed on GB10 (asserts major in {8,9}); `fa4` builds the
  # SAME FlashAttentionBackend class with fa_impl_ver=4 and the SM12x FA4 kernels,
  # and the mounted mod relaxes _handle_uno's literal ("fa3","fa3") gate to also
  # accept ("fa4","fa4"). If the mod is removed, this recipe fails at argument
  # validation with "UNO requires FA3 ..." -- intended stock behaviour. The mod's
  # default also admits `triton` (AGENTS.md §3), so lane B needs no env
  # propagation: sparkrun run --recipe k2-horizon-7b-fp8-uno-sglang -o
  # attention_backend=triton.
```

**`defaults.page_size`**:

```
  # page_size 1, and deliberately not 128. _fa4_page_constraint auto-forces 128
  # only when is_sm100, so on GB10 nothing forces it. At page_size 1 the
  # EAGLE topk>1 two-pass page-tree cascade is never reached -- and this recipe
  # uses linear UNO (topk 1) anyway, so that constraint does not bind either.
```

**`defaults.chunked_prefill_size`**:

```
  # Kept modest: UNO force-disables mixed chunked prefill, so prefill runs
  # alone; a large chunk here competes with the draft workspace for the same pool.
```

**`defaults.speculative_algorithm`** `[kept, trimmed]` — the `# ---- speculative: UNO ---` divider was dropped, the body kept:

```
  # ---- speculative: UNO ---------------------------------------------------
  # UNO is a builtin in this image. It reuses the TARGET model plus a
  # conditional-LoRA draft, so there is NO --speculative-draft-model-path; passing
  # one is an outright error ("UNO reuses the target model and does not accept
  # --speculative-draft-model-path").
```

**`defaults.speculative_eagle_topk`** `[kept, trimmed]` (linear, not tree):

```
  # LINEAR UNO, not tree: topk=1 makes _handle_uno force speculative_num_steps=1
  # (a passed value gets a warning and an override) and makes
  # --speculative-num-draft-tokens the LINEAR DRAFT WIDTH rather than a tree verify
  # width. Tree mode (topk>1) additionally demands Q>=F, Q<=128, Q*K<=2048, accept
  # thresholds exactly 1.0, no PDMux, no two-batch overlap, and a second CUDA-graph
  # backend -- all avoidable, and unmeasured here (AGENTS.md §9).
```

**`defaults.speculative_num_draft_tokens`** `[kept, trimmed]` (mandatory, draft width F):

```
  # Draft width F = tokens proposed per UNO step = the linear forward width. 8 is
  # the measured best of {2,4,8} on decode-triage (README.md §UNO arm); it
  # SATURATES by F=8 and a wider verify costs KV and graph memory. MANDATORY:
  # _handle_uno raises unless speculative_num_draft_tokens is a positive integer,
  # so this cannot be left to a default.
```

## Session 2026-10-18 — the 36B-A4B D2 + E6 gate run, and the decision it hands back

Owner decision #38 revived the withdrawn 36B sub-lane **bounded**: run the D2 numerics
gate and E6 (fp8-KV, scored), and nothing else from the E-series. Both ran. Four boots,
one GB10, serial, 32K context, TP=1, `--mem-fraction-static 0.85`,
`lmsysorg/sglang:v0.5.20-cu130` at the archive's own digest. `attic/ifm/arms/` was not
edited — work copies lived in `~/benchmarks/ifm-36b-20261018/arms/` with the gate mod
beside them. Full tables: `NOTES.md` (2026-10-18).

| gate | result |
|---|---|
| patch present in the container | `test_k2_fp8_guard.py` on the running container's `xllm.py` → `state=C`, `VERDICT: patched, invariants intact.`, exit **0** |
| **D2** numerics | **PASS** — BF16, FP8+bf16-KV and FP8+fp8-KV all answer `15:52 \| 5h 50m \| 12%`, with all six intermediate values agreeing; prose differs (expected), no degeneration |
| **E6** capacity | **pool 267,440 → 535,513 tokens (2.00×)** at an identical 52.6 GB footprint — the only unambiguous win |
| **E6** throughput at 32K | **+8.1 % at d28,672, −4.6 % at d8,192** (c1, n=3, paired control). The modelled +25 % does not survive measurement |
| **E6** quality | house battery **36/37 = 97.3 %** (easy 19/19, hard 17/18; the miss is `hard-rev` → `nurkrap`) — ties the lane's best; no control battery landed, so the KV-only delta is unmeasured |
| **E6** ladder d0 | C1 18.36 / C2 33.28 / C5 48.51 / C10 66.73 t/s vs the bf16-KV arm's 18.21 / 32.67 / 47.31 / 62.92 |

**What the owner now has to decide — ship, or stay withdrawn.** The evidence cuts both
ways and the numbers are these:

* *For shipping something*: the FP8 path is **sound** (D2 passed on a fixed prompt with an
  exact arithmetic answer, and the patch's static argument is now backed by a read) and the
  model is **competent** (36/37, the lane's joint best). At 18.2 t/s C1 it reproduces the
  2026-10-08 figure to 0.5 %, so the withdrawal was never about a broken recipe.
* *For staying withdrawn*: it is still **18.2 t/s single-stream** (62.9 t/s at c10) for a
  **48 GB checkpoint per node**, against 32.4 t/s for the shipped 7B and 80 t/s for the
  0.9B. E6 — the one lever that could have changed that — is **+8 % at 28.7K, not +25 %**,
  and negative at 8K; its real product is *capacity* (16 resident 32K sequences, or a
  reachable 131K on TP=2), which is only worth paying for if someone actually wants this
  model at long context.
* The middle option the numbers now support: **keep the arm archived, and treat E6 as a
  capacity result rather than a throughput one** — i.e. do not re-open the sub-lane for
  speed, but if a 131K-context need appears, E10 (fp8-KV + TP=2, 1 boot) is the only
  experiment worth spending on, and the pool arithmetic for it is already checked.

Do not quote E6's modelled +25 %/+57 % any more: 28,672 measured +8.1 %, and the mechanism
is the fp8-KV read running at 151 GB/s against bf16's 237 GB/s effective. The measurement
that settles it, and the run records: `~/benchmarks/ifm-36b-20261018/`.

## Engine-bump adjudication — SGLang 0.5.20 → 0.5.22 (2026-10-22, on hardware)

**Why this lane's bump is a different risk class from the Ornith one.** The two UNO arms mount
[`mods/probe-uno-fa4-sm121`](../../recipes/ifm/mods/probe-uno-fa4-sm121), which patches
`arg_groups/speculative_hook.py` by exact-anchor text and **refuses to write** unless it finds
`!= ("fa3", "fa3")` exactly once. A base image that moved that code fails the launch at hook time,
by design. So a re-pin here is a claim about that anchor, and it has to be measured, not inferred.

| claim | source | date | label |
|---|---|---|---|
| The lane pinned `lmsysorg/sglang:v0.5.20-cu130@sha256:06e4f2ed…` in all three shipped recipes | `recipes/ifm/*.yaml:5` | 2026-10-18 | **VERIFIED** |
| v0.5.22 index `sha256:e3a4f060…` carries a `linux/arm64` child `sha256:06441be3…`; `v0.5.22-cu130` resolves to the same index digest | `docker manifest inspect` on `.31` and `.35` | 2026-10-22 | **VERIFIED** |
| 0.5.22 still declares the UNO fields the recipes pass (`--speculative-algorithm UNO`, `--uno-lora-path`, `--speculative-eagle-topk`, `--speculative-num-draft-tokens`) | boots below reached a serving engine | 2026-10-22 | **VERIFIED** on hardware |
| The FA4 anchor still matches: `anchor count = 1 at …/srt/arg_groups/speculative_hook.py` | the mod's own probe, `/cache/runtime/modlogs/probe-uno-fa4-sm121.log` in each UNO boot | 2026-10-22 | **VERIFIED** |
| The patch is in force, not merely applicable: the arms served `--attention-backend fa4` + `UNO`, which stock 0.5.22 refuses with `"UNO requires FA3 for both prefill and decode"` | 0.9B-UNO and 7B-UNO boot logs | 2026-10-22 | **VERIFIED** (behavioural) |
| House batteries reproduce the lane's recorded scores item for item: 0.9B 32/37, 0.9B-UNO 33/37, 7B-UNO 36/37 | `~/benchmarks/sglang-0522-20261022/arm-{d,e,f}*/suite/house.json` | 2026-10-22 | **VERIFIED** |

**Verdict: not blocked; the pins are applied.** No mod edit was needed, no anchor moved, and no
work-around was taken. The engine moved torch `2.13.0+cu130 → 2.14.1+cu130` and python `3.12.x →
3.12.15`; the arms' boot shapes, admission (`max_running_requests` 64/64/32, none clamped) and pool
grants landed within 0.5 % of their 0.5.20 readings (1,764,610 vs 1,773,893; 1,690,881 vs 1,695,086;
574,698 vs 577,994). Zero `WARNING`/`ERROR`/`Traceback` lines in all three serve logs.

**The bar.** The bump's gate for this lane is *no regression against the arm's own recorded score and
miss list*, not 37/37 — this family has never scored 37/37 (its recorded bars are 32/37, 33/37 and
36/37, and the misses are the same items: `fmt-2`, `needle-1`, `hard-rev`, `trick-1`, `trick-2`). A
37/37 requirement would have failed every arm on its own baseline.

**Measured 2026-10-22, one serve per arm, sequential on `.35`** (receipts
`~/benchmarks/sglang-0522-20261022/`): 0.9B HTTP-ready **94 s** (on file 90.1), pool 1,764,610,
12.24 GB free; 0.9B-UNO **94 s** (on file 102.75), pool 1,690,881, 16.30 GB free; 7B-UNO **240 s**
(on file 255.7), pool 574,698, 15.38 GB free. No ladder was re-taken on this pass: the recipe bytes
changed in exactly one line (`container:`), so throughput is not a new question, and the lane's
recorded ladders stand as the reference for the same flags.

**Ops traps, both new to this lane.**

- `sparkrun run @littlecedar/<name>` resolves the **published** registry, not the worktree: with the
  worktree already at `v0.5.22-cu130`, the first launch booted `v0.5.21` — caught only because the boot
  log's `Image:` line and the versions block were read. Bump boots pass the **recipe file path**.
- A peer's `git pull`/checkout of the shared head reverted an uncommitted `container:` edit
  mid-campaign, and the next boot silently launched the previous engine. Guard before every boot:
  `grep -q <new digest> <recipe> || exit 3`. Also: `docker pull repo:tag@sha256:…` stores the image
  **untagged**, so it is prune-able by anyone on the fleet — re-tag it immediately.