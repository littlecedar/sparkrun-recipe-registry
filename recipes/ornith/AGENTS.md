# Ornith 1.5 — `recipes/ornith/` agent & developer guide

Serving recipes for **Ornith 1.5**, the self-improving agentic-coding family from the
[Ornith Team](https://ornith.ai/ornith_1_5.html), on NVIDIA DGX Spark (GB10, SM121, 128 GB
unified LPDDR5X per node, 200 GbE ConnectX-7 RoCE). Read this before touching a recipe, the mod,
or the guards in this directory. The prose summary lives in [`README.md`](README.md); this file
carries the state, the constraints, and the traps.

**No hostnames or addresses in tracked files.** This registry is distributed to third parties;
node state belongs in the git-ignored journal/ledger, never here. Lane work in this session ran on
the `.34`/`.35` shorthand.

**Scope of this directory.** Two shipped recipes, one per scale:

| recipe | scale | runtime | nodes (TP) | role |
|---|---|---|---|---|
| `ornith-1.5-35b-a3b-nvfp4-dflash2-sglang.yaml` | 35B-A3B | SGLang | 1 (TP=1) | **shipping** — the fast single-Spark lane |
| `littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm.yaml` | 397B | vLLM | 4 (TP=4) | **flagship** — the 4-node lane |

Three further Ornith recipes (a b12x `broken` 397B fork and two vLLM arms for the 35B) were moved
to [`attic/ornith/`](../../attic/ornith/) at commit `e0633ed`; they are provenance, not shipped
surface. Both shipped recipes are `sparkrun recipe validate`-clean.

**Evidence vocabulary (repo convention).** **VERIFIED** — read from a primary artifact (a boot log,
a pinned image, source at a pinned commit) or measured on our devices. **LIKELY** — strong
secondary evidence. **SPECULATIVE** — reasoning without a source; do not build on it. Never promote
`LIKELY` into unlabelled fact. A number without a receipt is a claim, not a measurement.

---

## 1. Lane state

**35B-A3B (`ornith-1.5-35b-a3b-nvfp4-dflash2-sglang`, 1 node, TP=1).** The official NVFP4
checkpoint (`ornith-ai/Ornith-1.5-35B-A3B-NVFP4`, `model_type: qwen3_5_moe`, full attention every
4th layer, 256 experts top-8, `max_position_embeddings: 262144`) with the
`jzinno/Ornith-1.5-35B-A3B-DFlash2` draft, DFlash2 spec decode (4 draft tokens). Registry footprint
45 GB at `gpu_memory_utilization: 0.85`. Published C1 ≈ **100 t/s** (parent `recipes/README.md`).

- **Boot-verified** in the 2026-10-11 pass: the boot surface serves, spec decode is on, the honed
  template loads, and the house quality battery passes (§5). The `~100 t/s` C1 headline sits between the
  DFlash2 author's AR (79.3) and DFlash2 (114.2) figures, consistent with the shipped recipe.
- **C1 re-measured 2026-10-13** (`.35`, `benchmarking/decode-triage.yaml`, C1, n=5 per cell,
  decode-phase rows only): **99.6 t/s @ d0 (σ 9.1)** and **100.2 t/s @ d8192 (σ 3.9)** — the ~100 t/s
  headline holds and is now a measurement, not an inheritance. Spec decode engaged (serve-log mean
  `accept len` 2.54 over 23 decode batches); warm-cache TTR port-open 95.1 s / HTTP-ready 97.8 s.
  Receipts: `~/benchmarks/ornith-c1-20261013/`.
- The independent DFlash2 draft numbers (**79.3 AR / 114.2 DFlash2, accept 4.02, 236.5 aggregate at
  C8**) are the author's measurement on a **different engine configuration** (their reference run
  uses `--moe-runner-backend marlin`, `--mamba-radix-cache-strategy extra_buffer`,
  `--mamba-ssm-dtype float32`, and 10 draft tokens) — a corroborating reference point, not this
  recipe's number. See §4 for the A/B that decomposed it.

**397B (`littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm`, 4 nodes, TP=4).** The flagship MoE,
served with `--enable-expert-parallel` and the checkpoint's own MTP head as the speculative method
(3 tokens). Registry records **235 GB per node** at `gpu_memory_utilization: 0.80` — which is why
it needs four nodes and cannot be a single-Spark recipe. The checkpoint is a Little Cedar derivative
that **grafts the BFP16 MTP MoE from the base model onto the NVFP4 quantization** (base
`ornith-ai/Ornith-1.5-397B`, ≈800 GB in bf16). Its model card reports **41.86 tok/s** on a 4× DGX
Spark vLLM run — that is the `C1 t/s` in the parent table; it is a **card figure**, tied to whatever
the `:latest` container tag resolved to when recorded (§3).

**Runtime split.** The 35B is SGLang and the 397B is vLLM; do not carry a Roofline or KV number
across the two — they are different engines. The lane wires the `qwen3` reasoning parser and a Qwen
tool-call parser (`qwen3_coder` on SGLang, `qwen3_xml` on vLLM) so CoT surfaces as
`reasoning_content` and tool calls as OpenAI `tool_calls`.

**Recommended sampling (model card):** `temperature=0.6`, `top_p=0.95`, `top_k=20`; `temperature=1.0`
to reproduce reported benchmarks.

## 2. Evidence locations

| question | where the answer lives |
|---|---|
| what a recipe *is* and why | §3 (constraints) plus the recipes' own short tunable comments |
| the A/B ladder, confirm/void analysis, quality score | [`README.md`](README.md) — the durable record |
| the honed-template delivery contract | [`mods/ornith-honed-chat-template/README.md`](../../mods/ornith-honed-chat-template/README.md) |
| why `@eugr/mods/drop-caches` is inert | [`mods/drop-caches/README.md`](../../mods/drop-caches/README.md) |
| engine-flag semantics (SGLang/vLLM) | [`mad-science/RESEARCH_LORE.md`](../../mad-science/RESEARCH_LORE.md) §5–§6 |
| guards | `tests/test_ornith_honed_chat_template.py`, `tests/test_drop_caches_mod.py` |

Receipt pointers for §4/§5 live on the head at `~/benchmarks/ornith-dflash2-ab-20261011/` (arms:
`control`, `control2-honed`, `arm1-draft10`, `arm2-marlin`, `arm3-extrabuf`, `arm4-ssmfloat32`,
`arm5-fullauthor`). The `sparkrun --output` JSON is the durable artifact; `runs/` is reaped.

## 3. Hard constraints and traps

1. **Hybrid-mamba memory trio (35B).** `mamba_full_memory_ratio: 3.51` with
   `mamba_ssm_dtype: bfloat16` and `mamba_radix_cache_strategy: extra_buffer_lazy`. The `3.51` is a
   **house value copied across lanes, not derived from this checkpoint** — the same trio appears in
   the Qwen3.8-27B dflash2 recipe, and the qwen3 lane's worklog flags it as a shared default with no
   recorded rationale. It reallocates the pool heavily toward linear-attention (GDN) state; the
   concurrency consequences are a `max_mamba_cache_size` question, not a source-reading one. **Do
   not silently "tune" it here** — a value change is a claim about expected traffic shape (see the
   qwen3 lane's ratio table for why the optimum is interior).
2. **`max_num_seqs` is an admission cap, and the mamba state pool can be the real ceiling.** The 35B
   ships `max_num_seqs: 48` with `--max-running-requests 48`. On this stack the *effective* ceiling
   can be the mamba state pool, not `max_num_seqs` — read the grant from the engine's own log, not
   from the flag. (The qwen3 lane sees exactly this shape: 48 requested, 21 granted.)
3. **The honed chat template is delivered by a mod, never injected into the HF snapshot.** The lane
   serves a community-honed template (`qwen3.8-honed-v22.5.1`, 30,438 B) staged by
   `@littlecedar/mods/ornith-honed-chat-template` under
   `/cache/runtime/ornith-honed-chat-template/` and pointed at with `--chat-template
   {honed_chat_template}`. **Never rewrite `chat_template.jinja` inside the HF snapshot:**
   sparkrun validates every cached model file against a hub manifest, and an injected snapshot fails
   `wrong_size` at distribution — a failure that cost this lane a session (the `.bak`/`.dist`
   siblings the injection left behind are the tell). The mod is idempotent by content and
   **fail-closed** on size + version marker. The recipe runs it **last**, after
   `pip-install-fastsafetensors`.
4. **Revision pin + `--revision` (35B).** The checkpoint is revision-pinned
   (`model_revision: 94e431d9cc47fa1986a7a1a4e9a80f7f118b03aa`) and the command passes
   `--revision {model_revision}`. The offline engine needs the explicit `--revision`: a SHA-keyed
   download writes no `refs/` entry, so an unpinned engine dies after the weights synced. (The
   draft snapshot `9b4852c0…` is currently left unpinned.)
5. **`@eugr/mods/drop-caches` is inert under a default launch.** Every Ornith recipe lists it; per
   [`mods/drop-caches/README.md`](../../mods/drop-caches/README.md) it **silently does nothing**
   (rootless `/proc/sys` is `ro`, plus a redirect-order bug). It is left in place rather than
   silently rewritten; the fixed, fail-closed replacement is the in-registry
   `@littlecedar/mods/drop-caches`, which requires a `--rootful` launch. **Consequence for
   benchmarking:** nothing in the pipeline clears the page cache for you — check node memory state
   (`MemAvailable` / page cache / other containers) before a boot (§4).
6. **`@littlecedar/<name>` resolves from the registry clone, not the local tree.**
   `~/.cache/sparkrun/registries/littlecedar` (GitHub URL) is what a cluster launch reads; local
   edits are invisible until pushed + `sparkrun registry update littlecedar`. The first A/B control
   boot ran the pre-session recipe for exactly this reason.
7. **Spec decode is user-visible in the log.** Check `Mean acceptance length > 1` on `Decode batch`
   lines. A DFlash2 boot that serves but accepts ≈1 token/step is a misconfiguration, not a win.
8. **The 397B container tag floats.** `ghcr.io/spark-arena/dgx-vllm-eugr-nightly:latest` is the one
   unpinned container in the lane — a moving tag, so a future pull can change the engine underneath
   the recipe. Treat the measured 41.86 t/s as tied to whatever the tag resolved to. A digest pin
   would make it reproducible.
9. **`VLLM_ALLOW_LONG_MAX_MODEL_LEN: 1` does not extend context.** The 397B sets it but
   `max_model_len` is **262144** (the native window). The env var only lifts vLLM's refusal to
   exceed the checkpoint's declared maximum.
10. **`recipe validate` does not resolve `mods:`.** A typo'd mod name still validates and only fails
    at launch (or with `-n` when a `command:` template is present).

## 4. Negative results — do not re-derive / re-run

**The 114.2 t/s author-config A/B ladder (2026-10-11, `benchmarking/decode-triage.yaml`, C1, n=5 per
cell, one node per arm).** The DFlash2 author's knob set was decomposed one knob at a time; every
cell is a real boot. The full author config is the **worst** arm — their 114.2 came from their engine
build, not from the knobs alone:

| arm (Δ from shipped) | d0 t/s (σ) | d8192 t/s (σ) | verdict |
|---|---|---|---|
| ② `moe_runner_backend` → `marlin` | **108.9** (5.3) | **109.0** (4.1) | best at first measurement; repeat 103.4 (5.4)/113.5 (13.5) straddles the noise |
| ③ `mamba_radix_cache_strategy` → `extra_buffer` | 103.2 (5.1) | 93.2 (14.1) | d0 neutral, d8192 noisier/worse |
| control (shipped config, honed template) | 99.3 (8.8) | 99.2 (4.7) | the shipped surface, re-measured |
| ④ `mamba_ssm_dtype` → `float32` | 90.4 (4.5) | 98.2 (6.5) | rejected |
| ① `speculative_draft_tokens` 4 → 10 | 86.5 (8.5) | 85.5 (6.2) | rejected (~19 % loss) |
| ⑤ full author config (①+②+③+④) | 84.6 (6.7) | 78.5 (10.7) | worst — the author's combination does not transfer |

**Verdict: no knob in the author's set is distinguishable from boot noise; the shipped config
stands.** Same-config spread on the node is **106.8 (pre-session control) vs 99.3 (honed control) =
7.5 %**, and marlin's two runs (108.9, 103.4) straddle it. What *is* outside the noise are the
losers: draft-10 (−13 %), float32 (−9 %), and the author's full combination (−15 %, the worst arm).
**A repeat of any arm here needs the same node and an interleaved control, or it measures boot
noise, not the knob.**

**The voided `.35` OOM boot — do not pool it.** The `.35` confirm boot served at **30.8 t/s**
(plain-decode speed, spec decode effectively absent) and its serve log ends in `Killed` (OOM) after
decode crawled at ~2.4 t/s in the last batches. That node had just re-imported a 10 GiB image and
carried other lanes' cached weights; a memory-starved boot **is not a recipe cell** and was excluded
rather than averaged. Operational rule: check node memory state before benching, and note that
nothing drops the page cache for you (§3.5).

**The 35B vLLM arms and the b12x 397B fork** are archived in `attic/ornith/` — the registry carries
no measured figure for the vLLM arms, and the DFlash2 draft is an SGLang-targeted artifact. Do not
treat them as benchmarked comparisons.

**No needle-in-a-haystack evidence for Ornith exists in this registry.** The model cards describe a
YaRN factor-4.0 override to ~1M tokens, but **neither recipe enables it** — it is new,
quality-unverified territory here (open-source runtimes apply YaRN statically for every request, so
it can erode ordinary-length quality).

## 5. Quality

**House battery, 2026-10-11, `tools/quality-battery.py`, one boot: 37/37 — 19/19 easy + 18/18 hard,
zero flakes.** The same perfect score the qwen3.8-27B DFlash2 arm returns, at ~3× its C1. The lane
previously had no quality number.

- **The battery must run with the served default `enable_thinking: false` semantics.** The honed
  template's reasoning toggle is `enable_thinking` per the boot log's `ReasoningToggleConfig`, and a
  content-reading client sees **empty replies** when short answers stay in the reasoning channel.
- The 397B lane has **no measured house score** in this registry.

## 6. Open items (deliberately not closed)

- **Reasoning loop — RESOLVED 2026-10-13: NOT REPRODUCED.** A reasoning-heavy probe battery on `.35`
  found zero repeated-window runs; the symptom is thinking-budget exhaustion, not a decode loop, and
  the SGLang serve line *honors* request-level sampling. No recipe change. Full method + table in
  [`README.md`](README.md) §"Reasoning-loop investigation"; receipts `~/benchmarks/ornith-loop-20261013/`.
- **The 35B C1 re-measurement — CLOSED 2026-10-13.** Measured on `.35` with the pinned
  `benchmarking/decode-triage.yaml` (C1, n=5 per cell, decode-phase rows only): **99.6 t/s @ d0
  (σ 9.1)** / **100.2 t/s @ d8192 (σ 3.9)**; the `~100 t/s` headline holds. See §1.
- **The 397B container digest pin** (see §3.8).
- **The house `mamba_full_memory_ratio: 3.51`** — picked to match precedent, not derived; a change
  is a traffic-shape decision.

## 7. Validation ritual

There is no CI and no linter. Before considering a change done:

```bash
set -e
H=$PWD/.local/sparkrun-home
uv run python -B -m unittest discover -s tests
for f in recipes/ornith/*.yaml; do HOME="$H" sparkrun recipe validate "$f" >/dev/null; done
for s in mods/*/*.sh; do bash -n "$s"; done
for p in mods/*/*.py tools/*.py; do uv run python -m py_compile "$p"; done
find mods tools tests -name __pycache__ -type d -exec rm -rf {} +
```

Use **plain** `validate`, not `--strict` (accepted warnings exist on shipped recipes).
`recipe validate` does **not** resolve `mods:` — only a real launch (or `-n`) surfaces a resolution
failure, and `tests/test_ornith_honed_chat_template.py` covers the staged-template wiring. The
lane has **no `tests/test_ornith_recipes.py`** — nothing else here is mechanically enforced.

## 8. References

- Announcement: <https://ornith.ai/ornith_1_5.html>
- 35B checkpoint: [ornith-ai/Ornith-1.5-35B-A3B-NVFP4](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B-NVFP4)
- 35B draft (DFlash2): [jzinno/Ornith-1.5-35B-A3B-DFlash2](https://huggingface.co/jzinno/Ornith-1.5-35B-A3B-DFlash2)
- 397B checkpoint: [littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft](https://huggingface.co/littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft)
- 397B base: [ornith-ai/Ornith-1.5-397B](https://huggingface.co/ornith-ai/Ornith-1.5-397B)
- DFlash 2: [Keep Drafting Parallel](https://inco.ai/blog/dflash2/) · [arxiv 2602.06036](https://arxiv.org/abs/2602.06036)
- Archived recipes: [`attic/ornith/`](../../attic/ornith/) (moved at `e0633ed`)

*Evidence over memory: if this file and a boot log disagree, the log wins — and this file gets
corrected.*
