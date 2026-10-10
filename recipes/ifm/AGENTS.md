# AGENTS.md — `recipes/ifm/` (IFM K2-Horizon family)

Lane guide for the IFM `K2-Horizon` recipes. Read this before working in this
directory; it carries the state, the constraints, and the guards. Prose summaries
live in [`README.md`](README.md); the durable research record is the two
`K2-*-MODEL-OPTIMIZATION-WORK.md` files (git-ignored) with their `K2-*-JOURNAL.md`
narratives, and cross-agent traffic is in `COOP.md` — a git-ignored working
ledger, not registry content (see the root `AGENTS.md`).

**No hostnames or addresses in tracked files.** This registry is distributed to
third parties. Internal node state belongs in the git-ignored journal/ledger,
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
| 7B-FP8 | `k2-horizon-7b-fp8-uno-sglang` (the plain 7B and NGRAM arms are archived in `attic/ifm/arms/`) | **MEASURED** (**32.4/27.1** shipped; the archived arms measured 21.3/19.2 and 27.9/28.6) | 36/37 = 97.3 % / 188/200 = 94.0 % / 178/200 = 89.0 % |

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
exact 9fa6faa5 pin). SGLang native UNO: sglang#37667 "[Speculative Decoding]
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

**Mod design note (banner Q1).** `mods/probe-uno-fa4-sm121` replaces exactly
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