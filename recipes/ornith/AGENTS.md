# Ornith 1.5 — `recipes/ornith/` agent & developer guide

Serving recipes for **Ornith 1.5**, the self-improving agentic-coding family from the
[Ornith Team](https://ornith.ai/ornith_1_5.html), on NVIDIA DGX Spark (GB10, SM121, 128 GB
unified LPDDR5X per node, 200 GbE ConnectX-7 RoCE). Read this before touching a recipe, the mod,
or the guards in this directory. The prose summary lives in [`README.md`](README.md); this file
carries the state, the constraints, and the traps.

**No hostnames or addresses in tracked files.** This registry is distributed to third parties;
node state belongs in the git-ignored journal/ledger, never here. Lane work in this session ran on
the `.34`/`.35` shorthand.

**Scope of this directory.** Three shipped recipes, one per model scale:

| recipe | scale | runtime | nodes (TP) | role |
|---|---|---|---|---|
| `ornith-1.5-35b-a3b-nvfp4-dflash2-sglang.yaml` | 35B-A3B | SGLang | 1 (TP=1) | **shipping** — the fast single-Spark lane |
| `littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm.yaml` | 397B | vLLM | 4 (TP=4) | **flagship** — the 4-node lane |
| `ornith-1.5-9b-nvfp4-dflash-sglang.yaml` | 9B | SGLang | 1 (TP=1) | **booted + measured 2026-10-14** — C1 ≈ 52–59 t/s, battery 37/37, spec engaged; state in §1 and [`NOTES.md`](NOTES.md) §2 (closed) |

Three further Ornith recipes (a b12x `broken` 397B fork and two vLLM arms for the 35B) were moved
to [`attic/ornith/`](../../attic/ornith/) at commit `e0633ed`; they are provenance, not shipped
surface. All three shipped recipes are `sparkrun recipe validate`-clean, and the lane is guarded by
[`tests/test_ornith_recipes.py`](../../tests/test_ornith_recipes.py) (added 2026-10-14 — the lane
had no recipe guard before that).

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
- **First-party DFlash head A/B — CLOSED 2026-10-14** (`.31`, `benchmarking/decode-triage.yaml`, C1,
  n=5 per cell, decode-phase rows only, one boot per arm, same window). The vendor's own head
  (`ornith-ai/Ornith-1.5-35B-A3B-DFlash`, `942d20fe…`, plain `DFlashDraftModel`, 0.77 GB) against the
  shipped third-party `jzinno/…-DFlash2` (`9b4852c0…`, `DFlash2DraftModel`): both served (serve-log
  `accept len` mean 2.44 / 2.50, i.e. > 1) and the C1 cells straddle each other — jzinno n=4
  **95.9 (σ 10.9) / 101.3 (σ 2.6)** vs first-party n=4 **101.3 (σ 5.2) / 97.8 (σ 11.1)**, first-party
  n=8 **92.7 (σ 7.9) / 92.8 (σ 9.3)** (d0 / d8192). No delta clears the ~9 t/s d0 boot noise and n=8
  is *not* better (accept 2.75, the same shape as the 2026-10-11 draft-10 loss), so **the shipped
  jzinno DFlash2 stands — the null is the result, not a tie-break.** The shipped draft is now
  **pinned** (`speculative_draft_model_revision: 9b4852c0…`, distribution-only) with the `refs/main`
  seed the pin needs (§3.12); the winner's pinned boot scored the house battery **37/37** (19/19 +
  18/18). Receipts: `~/benchmarks/ornith-dflash-ab-20261014/` (`armA0-jzinno-n4`, `armA1-firstparty-n4`,
  `armA2-firstparty-n8`, `armP2-pinned-seeded`, `armP1-pinned-cold` + `*-serve.log`, `quality.json`).
- **Long-horizon agentic quality pass — 2026-10-14** (`.31`, one boot, the shipped surface): a
  multi-turn tool-calling scheduling agent (growing transcript, up to 48 assistant turns and a
  34,705-token prompt, 16k and 32k completion budgets, temp 0.6 and 1.0 ± `presence_penalty` 1.5)
  shows **no decode loop** — a 25-word-window repeat reaching ≥3 occurs only where the model
  re-lists the *provided* requirement set, and the reasoning grows with the task rather than
  collapsing. House battery re-scored **37/37**; needle ladder 32k 3/3, 128k 3/3, 262,144 2/3 (the
  miss a completion-budget artifact — the model emits reasoning at long context even under the
  served default). Detail and the detection limit are in §6 and [`README.md`](README.md); receipts
  `~/benchmarks/ornith-horizon-20261014/`.

**397B (`littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm`, 4 nodes, TP=4).** The flagship MoE,
served with `--enable-expert-parallel` and the checkpoint's own MTP head as the speculative method
(3 tokens). Registry records **235 GB per node** at `gpu_memory_utilization: 0.80` — which is why
it needs four nodes and cannot be a single-Spark recipe. The checkpoint is a Little Cedar derivative
that **grafts the BFP16 MTP MoE from the base model onto the NVFP4 quantization** (base
`ornith-ai/Ornith-1.5-397B`, ≈800 GB in bf16). Its model card reports **41.86 tok/s** on a 4× DGX
Spark vLLM run — that is the `C1 t/s` in the parent table; it is a **card figure**, tied to whatever
the `:latest` container tag resolved to when recorded (§3).
  **Booted + measured 2026-10-14** (`.30–.33`, TP=4, `benchmarking/decode-triage.yaml`, decode-phase
  rows only): MTP baseline **42.55 t/s @ d0 (σ 2.78)** / **38.48 t/s @ d8192 (σ 1.91)**, spec decode on
  (`Mean acceptance length` 2.68–3.06), `GET /v1/models` = repo id, cold TTR 590.7 s. The first house
  measurement of the 397B beside the card's 41.86. Receipts `~/benchmarks/ornith-397b-ab-20261014/`.
  It is now **digest-pinned** (`@sha256:b94ac8ac…`, `nightly-20260913`) — before the pin the four nodes
  held three different builds under `:latest` (§3.8). **DFlash-vs-MTP A/B — CLOSED 2026-10-14; MTP
  ships.** Same window, same four nodes, same pinned build, `benchmarking/decode-triage.yaml`:
  MTP (3 tok) **42.55 (σ 2.78) / 38.48 (σ 1.91)**, accept 2.68–3.06; the vendor DFlash head
  (`ornith-ai/Ornith-1.5-397B-DFlash`, `db9c35a0…`, 8 tok) **37.58 (σ 4.45) / 33.64 (σ 1.13)**, accept
  3.27. DFlash loses ~12% at both depths **despite the higher acceptance** — its speculator overhead
  exceeds the extra accepted tokens, and it **disables prefix-cache reuse** on this hybrid-Mamba target
  (serve-log warning, Mamba groups [0..44] treated as draft groups). The shipped MTP default stands; the
  DFlash head is a **documented one-knob alternative** (`-o speculative_config={...}`, §3.13), no recipe
  file. Receipts `~/benchmarks/ornith-397b-ab-20261014/`.

**9B (`ornith-1.5-9b-nvfp4-dflash-sglang`, 1 node, TP=1) — BOOTED 2026-10-14.** The official
`ornith-ai/Ornith-1.5-9B-NVFP4` (`155f200d…`, 8.8 GB of weights, dense ~9B, multimodal) with the
first-party `ornith-ai/Ornith-1.5-9B-DFlash` draft (plain `DFlashDraftModel`) and SGLang DFLASH at 8
draft tokens. **C1 ≈ 52–59 t/s** — two same-window sweeps on one boot (`.30`), n=5 per cell,
decode-phase rows: cold d0 **51.7** (σ 13.2) / d8192 **56.6** (σ 9.0), warm d0 **59.4** (σ 6.8) /
d8192 **54.1** (σ 16.4). Half the 35B's ~100 is **expected, not a defect**: the 35B-A3B activates ~3B
params/token as a MoE, this is a *dense* ~9B. **House battery 37/37** (19/19 + 18/18, zero flakes).
Spec engaged: serve-log `accept len` mean **3.35** (1.85–6.85) over 38 decode batches. The pinned
image **does** load the plain draft (`Load weight end. … type=DFlashDraftModel`), accepts the alias
spelling (block-size mismatch is warning-only), and the hybrid pool does **not** clamp
`max_num_seqs: 48` (`max_mamba_cache_size: 273`, `max_running_requests=48`). The draft is deliberately
**unpinned**: a SHA pin writes no `refs/` entry and the container's `HF_HUB_OFFLINE=1` draft-config
lookup resolves only `refs/main`, so a pinned draft never starts (see §3.12). Receipts:
[`README.md`](README.md); `~/benchmarks/ornith-9b-20261014/`.

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
| the staged plans (9B arm, the two A/Bs, the quality set) and their acceptance criteria | [`NOTES.md`](NOTES.md) — working state, moved here into `README.md`/this file when a plan runs |
| the honed-template delivery contract | [`mods/ornith-honed-chat-template/README.md`](../../mods/ornith-honed-chat-template/README.md) |
| why `@eugr/mods/drop-caches` is inert | [`mods/drop-caches/README.md`](../../mods/drop-caches/README.md) |
| engine-flag semantics (SGLang/vLLM) | [`mad-science/RESEARCH_LORE.md`](../../mad-science/RESEARCH_LORE.md) §5–§6 |
| guards | `tests/test_ornith_recipes.py`, `tests/test_ornith_honed_chat_template.py`, `tests/test_drop_caches_mod.py` |

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
8. **The 397B container tag floats — now digest-pinned, and the nodes disagreed.** Before the pin, the
   four serving nodes held **three different builds** under `ghcr.io/spark-arena/dgx-vllm-eugr-nightly:latest`
   (`.30` `nightly-20260913` vLLM `0.29.1rc1.dev17`; `.31` `nightly-20260826` `0.26.1rc1`; `.32`/`.33`
   `nightly-20260911`) — a TP=4 launch on the bare tag is not one engine. The registry `:latest` resolved
   to a *fourth* build (`sha256:364005b0…`, `nightly-20261013`, vLLM `0.32.0rc1.dev78`) that this cluster
   could not pull (the OCI relay registry download stalled at ~400 KiB/s and failed on all four nodes).
   The recipe now pins the head-resident build, distributed uniformly:
   `container: ghcr.io/spark-arena/dgx-vllm-eugr-nightly@sha256:b94ac8ac47603f9c3d14f88c12b90eacbc37c7a42f922631cb8c9ac80f7b37c3`
   (`nightly-20260913`; exposes `method: dflash`). Measured 41.86 t/s remains a card figure.
9. **`VLLM_ALLOW_LONG_MAX_MODEL_LEN: 1` does not extend context.** The 397B sets it but
   `max_model_len` is **262144** (the native window). The env var only lifts vLLM's refusal to
   exceed the checkpoint's declared maximum.
10. **`recipe validate` does not resolve `mods:`.** A typo'd mod name still validates and only fails
    at launch (or with `-n` when a `command:` template is present).
11. **Never write `--served-model-name {model}` (35B).** sparkrun binds every `{model}` occurrence —
    including one inside `--served-model-name` — to the prepared snapshot path on a real launch
    (`models/runtime.py::bind_runtime_models`, quoted at
    `mods/tensorfold-dsv41-launcher/launcher.py:176-182`), so the server advertises
    `/cache/huggingface/hub/…` as its model id while `-n` still prints the repo id. The 35B recipe
    declares `served_model_name: ornith-ai/Ornith-1.5-35B-A3B-NVFP4` and passes
    `--served-model-name {served_model_name}`; the declared key also feeds the job metadata/proxy
    resolver (`resolve_served_model_name`). Fixed and live-verified 2026-10-13 (boot
    `dadfb04b5145d956_8ed3ce77d78f`, `.34`: `GET /v1/models` → repo id); regression guard in
    `tests/test_ornith_honed_chat_template.py`.
12. **A draft pin is distribution-only — it MUST be paired with a `refs/main` seed, or the arm dies.**
    `speculative_draft_model_revision` never reaches the serve line (SGLang has no lookup there;
    `runtimes/sglang.py::_detect_speculative_draft_revision` adds it to distribution only), and
    sparkrun's SHA-keyed fetch writes `snapshots/<sha>/` with **no `refs/` entry** (its own
    `models/preparation.py` writes `refs/<ref>` only for a *non-SHA* ref). The container runs
    `HF_HUB_OFFLINE=1`, so SGLang's startup draft-config lookup
    (`srt/arg_groups/speculative_hook.py::_resolve_speculative_algorithm_alias` → `get_config` on the
    draft repo id; the surrounding resolution hook does not pass the revision) resolves only
    `refs/main` and dies with `LocalEntryNotFoundError` at `resolve_once`. **Corrected 2026-10-14:**
    the 35B recipe pins the draft *and* seeds the ref — `defaults.speculative_draft_model_revision:
    9b4852c0…` plus a `pre_exec` hook that writes `<draft cache>/refs/main` = that SHA before serve.
    Boot-verified 2026-10-14 on `.31` (35B, jzinno draft): with `refs/main` removed from *both* the
    head and the node cache the pinned recipe serves (TTR 97 s, accept 2.50, `GET /v1/models` = repo
    id) via the hook's write; the *same* pin without the hook crashes at `speculative_hook.py:53`.
    The 9B arm's first-party draft stays deliberately unpinned — its unpinned fetch resolves
    `refs/main` itself (boot-verified 2026-10-14, `.30`). Do not copy a draft pin into a new arm
    without the same seed.
13. **The 397B `speculative_config` must stay a declared default, not inline JSON.** sparkrun reads the
    speculative **draft model+revision out of the `speculative_config` *default***
    (`runtimes/_vllm_common.py::detect_spec_config_draft` → `recipe._effective_default("speculative_config")`
    → `json.loads`), and `-o speculative_config={...}` only reaches a *declared* default. So inline JSON in
    `command:` does two silent things: the MTP↔DFlash method swap becomes a no-op, and a DFlash draft is
    never distributed to the four nodes (`Revision Not Found` at serve). The recipe therefore declares
    `defaults.speculative_config` and renders `--speculative-config '{speculative_config}'`. Nested
    placeholders inside a default's value are **not** substituted (the render is a single pass over
    `command:`), so the default's JSON carries literal values. The draft's revision lives **inside that
    JSON** (vLLM's `revision` field), never via `model_revision:` (that SHA is not in the target repo).
    Guards: `tests/test_ornith_recipes.py::FlagshipSpeculativeConfigIsSwappable`.

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

**Needle-in-a-haystack — measured 2026-10-14 (35B, `.31`): 32k 3/3, 128k 3/3, 262,144 2/3.** The
one 262k miss is a completion-budget artifact, not a retrieval failure (§5). The model cards
describe a YaRN factor-4.0 override to ~1M tokens, but **neither recipe enables it** — it is new,
quality-unverified territory here (open-source runtimes apply YaRN statically for every request, so
it can erode ordinary-length quality).

**The long-horizon agentic looping report — NOT REPRODUCED (2026-10-14); do not re-run the
single-turn battery expecting it.** Five long-horizon tool-using arms (16k and 32k budgets, temp 0.6
and 1.0 ± `presence_penalty` 1.5, up to 48 turns and a 34,705-token prompt) show no decode loop; the
windows that repeat ≥3 times are the model re-listing the *provided* requirement set, and the
reasoning grows with the task. A null beside its detection limit is the result (§5, §6); receipts
`~/benchmarks/ornith-horizon-20261014/`.

## 5. Quality

**House battery, 2026-10-11, `tools/quality-battery.py`, one boot: 37/37 — 19/19 easy + 18/18 hard,
zero flakes.** The same perfect score the qwen3.8-27B DFlash2 arm returns, at ~3× its C1. The lane
previously had no quality number.

- **The battery must run with the served default `enable_thinking: false` semantics.** The honed
  template's reasoning toggle is `enable_thinking` per the boot log's `ReasoningToggleConfig`, and a
  content-reading client sees **empty replies** when short answers stay in the reasoning channel.
- The 397B lane has **no measured house score** in this registry.

**Long-horizon agentic pass, 2026-10-14 (`.31`, one boot): no loop; house battery 37/37; needle
32k 3/3, 128k 3/3, 262,144 2/3.** The 35B re-scores **37/37** (19/19 + 18/18, zero flakes) on this
boot — parity with §1, no regression. Needle retrieval is intact at ~256k prompt tokens; the single
262k miss is a **client-budget artifact**: at the native window the model emits ~150–200 characters
of reasoning before the answer even under the served default, so a 64-token completion budget
truncates the visible answer (a short-`max_tokens`, `content`-reading client sees empty or partial
replies) — re-probing that depth at 256 tokens passes. The `tool-eval-bench` suite that
[`NOTES.md`](NOTES.md) §5 C2 named is **not configured in this registry**, so the house battery is
the lane's only suite score.

## 6. Open items (deliberately not closed)

- **Reasoning loop — NOT REPRODUCED on the long-horizon workload either (2026-10-14, `.31`); the
  owner ratifies the bar.** The 2026-10-13 nine-prompt *single-turn* battery on `.35` found zero
  repeated-window runs; the owner did not accept a null from an instrument that never exercised the
  reported workload. The purpose-built long-horizon probe (multi-turn tool-using scheduling agent,
  growing transcript, 16k/32k budgets, temp 0.6/1.0 ± `presence_penalty` 1.5) **also returns a
  null**: no decode loop, ≥3-repeat windows only where the model re-lists the provided requirement
  set, reasoning growing with the task, and valid plans submitted. **Detection limit** — ~35k-token
  transcripts, 48 turns, 16k and 32k budgets, a 25-word-window metric firing at ≥3 repeats. C3
  (sampling) is discriminated (no sampling-dependent loop); C4 (context) passes at two of three
  windows, the third a client-budget artifact and reproduced at the 9B scale; C2 is met by the
  house battery only (the named `tool-eval-bench` suite is unavailable here); C5 (9B cross-scale) is
  run — same null, plus a worse empty-reply rate (0/3 needle hits at a 64-token budget, a
  reasoning-budget artifact, not lost retrieval). Full method, arm table, result, and the
  pre-registered bar are in
  [`README.md`](README.md) §"Long-horizon agentic re-investigation (2026-10-14)" and
  [`NOTES.md`](NOTES.md) §5; receipts `~/benchmarks/ornith-horizon-20261014/`.
- **The 35B C1 re-measurement — CLOSED 2026-10-13.** Measured on `.35` with the pinned
  `benchmarking/decode-triage.yaml` (C1, n=5 per cell, decode-phase rows only): **99.6 t/s @ d0
  (σ 9.1)** / **100.2 t/s @ d8192 (σ 3.9)**; the `~100 t/s` headline holds. See §1.
- **The 397B container digest pin — CLOSED 2026-10-14.** Pinned to `@sha256:b94ac8ac…`
  (`nightly-20260913`) after the four nodes were found holding three different builds under `:latest`
  (§3.8); registry `:latest` resolved to an unpullable fourth build. **MTP-vs-DFlash spec-decode A/B —
  CLOSED 2026-10-14: MTP wins** (42.55/38.48 vs 37.58/33.64 t/s; DFlash's higher acceptance does not
  transfer and it disables prefix caching). See §1 and [`NOTES.md`](NOTES.md) §4.
- **The house `mamba_full_memory_ratio: 3.51`** — picked to match precedent, not derived; a change
  is a traffic-shape decision.
- **The 9B arm — CLOSED 2026-10-14.** Booted and measured (see §1); the two open boot questions
  (plain `DFlashDraftModel` load, alias spelling) are answered yes.
- **The 35B first-party DFlash head — CLOSED 2026-10-14.** A null A/B (indistinguishable from the
  shipped jzinno DFlash2 at n=4; n=8 no better), so the shipped draft stands and is now pinned with
  its `refs/main` seed. See §1 and [`NOTES.md`](NOTES.md) §3.

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
failure, and `tests/test_ornith_honed_chat_template.py` covers the staged-template wiring. The lane's
recipe guards live in `tests/test_ornith_recipes.py` (added 2026-10-14): the arm shapes, the
model-revision pins (and the 9B draft's deliberate *absence* of one — see §3.12), the 35B draft's
distribution-only pin **and** its `refs/main` seed hook (O5), the mamba/moe
omission on the 9B arm, and the served-model-id spelling. Before that the
lane had no recipe guard at all.

Two 397B guards were added with the spec-decode A/B: `FlagshipSpeculativeConfigIsSwappable` (§3.13 — the
`{speculative_config}` placeholder must stay a declared default and stay out of `command:`) and
`FlagshipContainerIsDigestPinned` (§3.8).

## 8. References

- Announcement: <https://ornith.ai/ornith_1_5.html>
- 35B checkpoint: [ornith-ai/Ornith-1.5-35B-A3B-NVFP4](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B-NVFP4)
- 35B draft (DFlash2): [jzinno/Ornith-1.5-35B-A3B-DFlash2](https://huggingface.co/jzinno/Ornith-1.5-35B-A3B-DFlash2)
- 35B draft (first-party; A/B null 2026-10-14): [ornith-ai/Ornith-1.5-35B-A3B-DFlash](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B-DFlash)
- 9B checkpoint: [ornith-ai/Ornith-1.5-9B-NVFP4](https://huggingface.co/ornith-ai/Ornith-1.5-9B-NVFP4)
- 9B draft: [ornith-ai/Ornith-1.5-9B-DFlash](https://huggingface.co/ornith-ai/Ornith-1.5-9B-DFlash)
- 397B checkpoint: [littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft](https://huggingface.co/littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft)
- 397B base: [ornith-ai/Ornith-1.5-397B](https://huggingface.co/ornith-ai/Ornith-1.5-397B)
- DFlash 2: [Keep Drafting Parallel](https://inco.ai/blog/dflash2/) · [arxiv 2602.06036](https://arxiv.org/abs/2602.06036)
- Archived recipes: [`attic/ornith/`](../../attic/ornith/) (moved at `e0633ed`)

*Evidence over memory: if this file and a boot log disagree, the log wins — and this file gets
corrected.*
