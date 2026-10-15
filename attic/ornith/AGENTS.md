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
| the honed-template delivery contract | [`recipes/ornith/mods/ornith-honed-chat-template/README.md`](../../recipes/ornith/mods/ornith-honed-chat-template/README.md) |
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
   `recipes/ornith/mods/ornith-honed-chat-template` under
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
[`NOTES.md`](NOTES.md) §5 C2 named was **not configured in this registry when this pass ran** (it is
now: `benchmarking/standard-suite.yaml`, added 2026-10-15), so the house battery is the suite score
recorded here.

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
house battery only (the named `tool-eval-bench` suite is now configured as
`benchmarking/standard-suite.yaml` but was not run for this pass); C5 (9B cross-scale) is
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

---

## From recipes/ornith/README.md (2026-10-14)

# Ornith 1.5 on DGX Spark — `ornith`

Serving recipes for **Ornith 1.5**, the self-improving agentic-coding model family from the
[Ornith Team](https://ornith.ai/ornith_1_5.html), on NVIDIA DGX Spark (GB10, SM121, 128 GB
unified LPDDR5X per node, 200 GbE ConnectX-7 RoCE). This directory is the `ornith` lane; it
ships **three** recipes, one per model scale:

| Recipe                                            | Scale | Runtime | Nodes (TP) | C1 t/s |  Size |  Mem | Flags  | Model Cards                                                                                 |
|:--------------------------------------------------|:------|:--------|:-----------|-------:|------:|-----:|:-------|:--------------------------------------------------------------------------------------------|
| `ornith-1.5-35b-a3b-nvfp4-dflash2-sglang.yaml`    | 35B-A3B | SGLang | 1 (TP=1) |    100 |  45GB | 0.85 | ✨🚀🌲👀🧠🦾🔧 | [Model][model-35b] · [Draft][draft-dflash2]                                                 |
| `littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm.yaml` | 397B | vLLM | 4 (TP=4) |  41.86 | 235GB | 0.80 | 🌲👀🧠🦾🔧     | [Model][model-397b-graft]                                                                   |
| `ornith-1.5-9b-nvfp4-dflash-sglang.yaml`          | 9B | SGLang | 1 (TP=1) |     55 |  11GB | 0.85 | ✨🚀🤏👀🧠🦾🔧     | [Model][model-9b] · [Draft][draft-9b]                                                       |

`C1 t/s` is single-stream decode as recorded in the parent [`recipes/README.md`](../README.md);
`Size` is the per-node footprint the registry records and `Mem` is the recipe's
`gpu_memory_utilization`. Flags are defined in [Model Flags](../README.md#model-flags). A dash is
an **unmeasured** arm, not a zero. All three recipes are `sparkrun recipe validate`-clean.

## About the model

Ornith 1.5 extends Ornith 1.0 (itself a continued-pretraining of Qwen3.5 and Gemma 4) by expanding
the self-scaffolding loop into end-to-end self-improvement: the model proposes tasks, builds the
evaluation harness, and produces solution rollouts. It is an **agentic coding** family — Terminal-Bench,
SWE-bench, MCP-Atlas, Toolathlon — and it is a **reasoning model**: assistant turns open with a
` thinking … </think>` block, and tool calls are emitted as Qwen-style XML. Both recipes therefore wire
the `qwen3` reasoning parser and a Qwen tool-call parser (`qwen3_coder` on SGLang, `qwen3_xml` on vLLM) so
the chain-of-thought surfaces as `reasoning_content` and tool calls as OpenAI `tool_calls` — matching the
launch parameters the [upstream model cards](https://ornith.ai/ornith_1_5.html) publish. The 262,144-token
native context is served as-is; the model card's YaRN long-context override is **not** in either shipped
recipe (see [Caveats](#caveats)).

Recommended sampling (model card): `temperature=0.6`, `top_p=0.95`, `top_k=20` for general use,
`temperature=1.0` to reproduce the reported benchmark numbers.

## `ornith-1.5-35b-a3b-nvfp4-dflash2-sglang.yaml` — the fast single-Spark lane

The 35B-A3B is a MoE that activates ~3B parameters per token, so it fits and serves on **one** Spark
(the registry records a 45 GB footprint at `gpu_memory_utilization: 0.85`). The recipe pairs the official
NVFP4 checkpoint with the [`jzinno/Ornith-1.5-35B-A3B-DFlash2`][draft-dflash2] speculative draft and
turns on DFlash2 (`--speculative-algorithm DFLASH`, 4 draft tokens) — the recipe behind the ~100 t/s C1
row in the parent table.

Wiring worth knowing:

- **Model:** [`ornith-ai/Ornith-1.5-35B-A3B-NVFP4`][model-35b] — NVFP4 (`modelopt`, mixed precision: FP8
  on attention / linear-attention projections, W4A16_NVFP4 on the routed and shared experts and `lm_head`).
  `config.json` reports `model_type: qwen3_5_moe`, 40 layers with full attention every 4th layer
  (`full_attention_interval: 4`), 256 experts with top-8 routing, `max_position_embeddings: 262144`. The
  NF4/NVFP4 checkpoint is MIT-licensed.
- **Runtime:** SGLang, container `lmsysorg/sglang:dev-cu13@sha256:9a352a35…` (digest-pinned).
- **Hybrid-mamba memory:** `mamba_full_memory_ratio: 3.51` with `mamba_ssm_dtype: bfloat16` and
  `mamba_radix_cache_strategy: extra_buffer_lazy`. 3.51 is a **house value copied across lanes, not a
  value derived from this checkpoint** — the same trio appears in the Qwen3.8-27B dflash2 recipe, and the
  qwen3 lane's worklog flags it as a shared default with no recorded rationale. It reallocates the
  leftover pool heavily toward linear-attention (GDN) state; the concurrency consequences are the
  `max_mamba_cache_size` question, not a source-reading question.
- **`max_num_seqs: 48`** with `--max-running-requests 48`. Note this is the admission cap, and on this
  stack the *effective* ceiling can be the mamba state pool, not `max_num_seqs`.
- **Spec decode is user-visible in the log:** check `Mean acceptance length > 1` on `Decode batch` lines.
  A DFlash2 boot that serves but accepts ≈1 token/step is a misconfiguration, not a win.
- **`--load-format fastsafetensors`** is supplied by the `@littlecedar/mods/pip-install-fastsafetensors`
  mod; `@eugr/mods/drop-caches` is inert here (see [Caveats](#caveats)).

**Independent evidence for the draft.** The DFlash2 model card reports a held-out serving evaluation on
one DGX Spark: autoregressive serving at C1 = **79.3 tok/s**, and the DFlash2 draft at C1 = **114.2 tok/s
(+44%)** with mean accepted length **4.02**, rising to 236.5 tok/s aggregate at C8. Those numbers were
measured by the draft author on a **different engine configuration** than ours (their reference run uses
`--moe-runner-backend marlin`, `--mamba-radix-cache-strategy extra_buffer`, `--mamba-ssm-dtype float32`,
and 10 draft tokens; we ship `flashinfer_cutlass`, `extra_buffer_lazy`, `bfloat16`, and 4 draft tokens),
so treat 114.2 as a **corroborating reference point, not this recipe's measured number**. Our published
C1 of ~100 t/s sits between the author's AR and DFlash2 figures, consistent with the shipped recipe.

**First-party DFlash head A/B — null, and the shipped draft is now pinned (2026-10-14, `.31`,
`benchmarking/decode-triage.yaml`, C1, n=5 per cell, decode-phase rows only, one boot per arm, same
window).** The vendor published its own head two weeks after the third-party one —
[`ornith-ai/Ornith-1.5-35B-A3B-DFlash`](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B-DFlash)
(`942d20fe…`, a plain `DFlashDraftModel`, 0.77 GB) — so it was measured against the shipped jzinno
`DFlash2DraftModel` (`9b4852c0…`). Both served (serve-log `accept len` mean 2.44 / 2.50, i.e. > 1),
and the C1 cells straddle each other: shipped jzinno n=4 **95.9 t/s @ d0 (σ 10.9) / 101.3 @ d8192
(σ 2.6)**, first-party n=4 **101.3 (σ 5.2) / 97.8 (σ 11.1)**, first-party n=8 **92.7 (σ 7.9) / 92.8
(σ 9.3)**. No delta clears the ~9 t/s d0 boot noise, and n=8 is *not* better (accept 2.75 — the same
shape as the 2026-10-11 draft-10 loss), so **the shipped jzinno DFlash2 stands; the null is the
result.** The shipped draft is now **pinned** (`speculative_draft_model_revision: 9b4852c0…`, a
distribution-only key — SGLang has no drafter-revision flag) and the recipe carries a `pre_exec` hook
that seeds the draft's `refs/main`, which the pin otherwise omits and the offline engine's
draft-config lookup requires ([`AGENTS.md`](AGENTS.md) §3.12). Receipts:
`~/benchmarks/ornith-dflash-ab-20261014/`.

**C1 re-measurement (2026-10-13, `.35`, `benchmarking/decode-triage.yaml`, C1, n=5 per cell,
decode-phase rows only).** The headline is now a measurement, not an inheritance: **99.6 t/s @ d0
(σ 9.1)** and **100.2 t/s @ d8192 (σ 3.9)** — the prior `~100 t/s` header is superseded by these
figures. Spec decode was engaged (serve-log mean `accept len` **2.54** across 23 decode batches, min
2.27 / max 2.83), and the warm-cache boot reached port-open **95.1 s** / HTTP-ready **97.8 s** / TTFT
`98.0 s`. Receipts: `~/benchmarks/ornith-c1-20261013/` (`c1-decode-triage.json`, `serve.log`).

**Served model id fixed (2026-10-13, `.34`, job `dadfb04b5145d956_8ed3ce77d78f`).** The arm answered
with the engine's filesystem path as its model id (`/cache/huggingface/hub/models--ornith-ai--…/
snapshots/94e431d9…`) because `--served-model-name {model}` renders from the one placeholder sparkrun
rebinds to the prepared snapshot path on a real launch — a rewrite `-n` does not show. The recipe now
declares `served_model_name: ornith-ai/Ornith-1.5-35B-A3B-NVFP4` in `defaults:` and passes
`--served-model-name {served_model_name}`; on the fixed boot `GET /v1/models` returned the repo id
(`max_model_len` 262144) and a chat completion addressed to that id returned 200. Warm TTR: port-open
**94.7 s** / HTTP-ready **100.6 s** / TTFT **100.7 s**. (The registry-wide sweep landed the same day: every shipped sglang arm now serves its repo id — the
ten remaining `{model}` spellings were re-pointed and live-verified, and the two ds4 arms keep
`{model}` because their in-container launchers normalize the path, guarded in `tests/test_ds4_recipes.py`;
class guard `tests/test_recipe_placeholder_resolution.py::ServedModelNameNotRebound`.)

**Measured A/B against the author's reference config (2026-10-11, `benchmarking/decode-triage.yaml`,
C1, n=5 per cell, one node per arm, same window where paired).** The author's 114.2 knob set was
decomposed one knob at a time; every cell is a real boot, and the full author config is the *worst*
arm — their numbers came from their engine build, not from the knobs alone:

| arm (Δ from shipped) | d0 t/s (σ) | d8192 t/s (σ) | verdict |
|---|---|---|---|
| ② `moe_runner_backend` → `marlin` | **108.9** (5.3) | **109.0** (4.1) | best; ~+10% over the shipped-config control, unconfirmed at first measurement |
| ③ `mamba_radix_cache_strategy` → `extra_buffer` | 103.2 (5.1) | 93.2 (14.1) | d0 neutral, d8192 noisier/worse |
| control (shipped config, honed template) | 99.3 (8.8) | 99.2 (4.7) | the shipped surface, re-measured |
| ④ `mamba_ssm_dtype` → `float32` | 90.4 (4.5) | 98.2 (6.5) | rejected |
| ① `speculative_draft_tokens` 4 → 10 | 86.5 (8.5) | 85.5 (6.2) | rejected (~19% loss) |
| ⑤ full author config (①+②+③+④) | 84.6 (6.7) | 78.5 (10.7) | worst — the author's combination does not transfer |

Receipts: `~/benchmarks/ornith-dflash2-ab-20261011/` (control, control2-honed, arm1-draft10,
arm2-marlin, arm3-extrabuf, arm4-ssmfloat32, arm5-fullauthor).

**Confirm runs and the honest verdict (same node, `.34`).** Marlin repeated at **103.4 (5.4) /
113.5 (13.5)**. The shipped-config control reproduced at 99.3, and the pre-session control boots at
106.8. So the same-config spread on this node is **106.8 vs 99.3 (7.5%)**, while marlin's two runs
(108.9, 103.4) straddle it. **Verdict: no knob in the author's set is distinguishable from boot noise
on our stack; the shipped config stands.** What *is* outside the noise are the losers: draft-10
(−13%), float32 (−9%), and the author's full combination (−15%, the worst arm). The author's 114.2
comes from their engine build, not from these knobs.

**A voided pair, and the failure it exposed.** The `.35` confirm boot served at **30.8 t/s** — plain-decode
speed, spec decode effectively absent — and its serve log ends in `Killed` (OOM) after decode crawled at
~2.4 t/s in the last batches. That node had just re-imported a 10 GiB image and carried other lanes'
cached weights; a memory-starved boot is not a recipe cell and was excluded rather than averaged. Two
operational rules fall out: **check node memory state(`MemAvailable` / page cache / other containers)
before benching**, and note that `@eugr/mods/drop-caches` — the mod every Ornith recipe lists first — is
inert, so nothing in the pipeline actually clears the page cache for you.

**Quality (house battery, 2026-10-11, `tools/quality-battery.py`, one boot).** **37/37 — 19/19 easy +
18/18 hard, zero flakes** — the same perfect score the qwen3.8-27B DFlash2 arm returns, at ~3× its C1.
The lane previously had no quality number. (The battery must run with the served default
`enable_thinking: false` semantics; the honed template's reasoning toggle is
`enable_thinking` per the boot log's `ReasoningToggleConfig`, and a content-reading client sees empty
replies when short answers stay in the reasoning channel.)

**Re-confirmed on the pinned winner boot (2026-10-14, `.31`).** The house battery re-scored **37/37**
(19/19 easy + 18/18 hard, zero flakes) on the pinned jzinno boot, alongside the C1 cells above —
parity with the 2026-10-11 run.

**Honed chat template (2026-10-11).** The lane's verified boot surface serves a community-honed chat
template (`qwen3.8-honed-v22.5.1`, 30,438 B) rather than the checkpoint's upstream template. It is
delivered by `recipes/ornith/mods/ornith-honed-chat-template`, which stages the file under
`/cache/runtime/ornith-honed-chat-template/` (content-idempotent, fail-closed on size + marker) and the
recipe points `--chat-template` at it. Never inject it into the HF snapshot: sparkrun validates every
cached model file against a hub manifest, and an injected snapshot fails `wrong_size` at distribution
(that failure cost this lane a session — the `.bak`/`.dist` siblings the injection left behind are the
tell). The checkpoint is revision-pinned (`94e431d9…` at the time of writing) and the command passes
`--revision {model_revision}`, which the offline engine needs because a SHA download writes no
`refs/` entry.

## Reasoning-loop investigation (2026-10-13)

Ticket text: the served model *often starts looping while reasoning*. **Verdict: NOT REPRODUCED as a
decode loop; the user-visible symptom is thinking-budget exhaustion.** Method follows the ds4 lane
([`recipes/ds4/README.md`](../ds4/README.md) §"Stability"): a battery of reasoning-heavy prompts at
served sampling, the `reasoning_content` scored for repeated-window runs (max count of any 25-word
window; `1` = every window unique), and `finish_reason` read to separate a true loop from a budget
truncation.

One boot on `.35` (SGLang `0.0.0.dev1+g20ca564bf`, model @ `94e431d9…`, `/v1/models` healthy ~210 s
after launch). **9 prompts × {temperature 0, temperature 0.6 (recommended)} × {4096, 8192 tokens} →
zero repeated-window runs in every arm** (loop score 1). The one `max_window_repeat=2` observed (temp
0.6, 8k, `schedule-constraint`) was a stochastic re-read inside a 4293-word enumeration — a re-run of
the identical cell gave 0 repeats. Truncations are *fresh* reasoning (`finish_reason=length`, loop
score 1): temp-0 `counterfactual-chain` runs 5164 words and ends mid-thought. The behaviour reads as a
loop because the reasoning is verbose and self-scaffolding — a 5-item ordering problem reasons for
3902–4293 words at `distinct_word_ratio` 0.22–0.27 with repeated `let me…` openings — but it is not
token repetition, and it *exhausts* a token budget rather than repeating inside one.

Contrast with the ds4 lane: **this SGLang serve line honors request-level sampling** (temp 0 vs temp
0.6 give different replies for all 9 prompts; `repetition_penalty 1.1` changes a temp-0 reply), so a
client-side mitigation *would* act here — but there is nothing to cap away. No recipe knob change was
warranted; the remedy for the observed behaviour is a thinking budget (`max_tokens`) on the client.
Receipts: `~/benchmarks/ornith-loop-20261013/` (`loop_probe.py`, six battery JSONLs, `README.md`).

## Long-horizon agentic re-investigation (2026-10-14) — also a null, on the workload the ticket is about

The owner was unconvinced of the model's quality and surprised the 2026-10-13 battery could not
reproduce the looping: that battery drove nine *single-turn* prompts, and a workload it never
exercised is a limit of the instrument, not a refutation. This pass drives the workload the report
is about. Arms C1–C4 ran on `.31` in one boot of the shipped 35B surface (honed template,
`enable_thinking` per request; serve-log `accept len` mean **3.267** over 702 decode batches — spec
decode engaged); C5 is a second boot of the 9B arm.

**Method** (`~/benchmarks/ornith-horizon-20261014/agentic_horizon_probe.py`). The model is a
scheduling agent in one growing transcript: turn *i* adds requirement *i* to a growing set and asks
it to re-derive a valid total order over jobs J0..Ji, using tools (`list_jobs`, `get_requirements`,
`submit_plan`). The harness validates each submitted order against the accumulated constraints, so
the task is *scoreable*, not merely generative — and constraint enumeration is the shape that made
this model reason 3900+ words in the single-turn probe, so it is the family that exercises long CoT
with a growing context. Detector: (a) the ds4 metric — the max repeat of any **25-word window** in
`reasoning_content` (≥3 = a decode loop); (b) the same over the whole session's reasoning
concatenated in turn order; (c) that session metric over windows that are **not** the model
re-listing the provided requirement set; (d) cross-turn **8-word shingle overlap** (≈1 = verbatim
self-replay); and (e) `finish_reason`, so a budget truncation is separable.

| arm | sampling | budget | calls | max prompt tok | per-msg repeat max (≥3) | cross-turn overlap max | reasoning words early→late | finish (tool_calls / stop) | plans valid / invalid |
|---|---|---|---|---|---|---|---|---|---|
| H1 | temp 0.6 (served) | 16k | 47 | 34,705 | 2 (0) | 0.38 | 63 → 638 | 41 / 6 | solved |
| H1b (repeat of H1) | temp 0.6 | 16k | 48 | 17,482 | 2 (0) | 0.52 | 35 → 212 | 35 / 13 | 15 / 3 |
| H2 | temp 1.0 + `presence_penalty` 1.5 (card general) | 16k | 42 | 22,441 | 3 (1) | 0.42 | 150 → 419 | 30 / 12 | 17 / 2 |
| H3 | temp 0.6 | 32k | 36 | 14,226 | 5 (1) | 0.71 | 23 → 165 | 28 / 8 | 15 / 1 |
| H4 | temp 1.0, `presence_penalty` 0 | 16k | 36 | 8,000 | 2 (0) | 0.40 | 26 → 188 | 24 / 12 | 12 / 0 |
| H0 (control: trivial repo tool loop) | temp 0.6 | 16k | 60 | — | 1 (0) | — | 17 → 7 | 60 / 0 | — |

**Result: NOT REPRODUCED — a bounded null.** No arm produced a decode loop. The per-message 25-word
repeat never exceeded 5, and in every case where it reached ≥3 the repeated window is the model
**re-listing the provided requirement set** (for example `- J1 after J0 - J2 after J0 - J3 after
J1 …`, shown verbatim in the receipts) — not a replay of its own reasoning. Cross-turn shingle
overlap never approached 1 (max 0.71, and the shared shingles are that same requirement list); the
reasoning **grows** with the task rather than collapsing (63 → 638 words, early → late); no arm hit
`finish_reason=length`; and the model converges on *valid* plans (15/3, 17/2, 15/1, and 12/0
valid/invalid). The verbose, self-scaffolding style the ticket calls "looping" is real — 182
`let me…` openings in one session, and long constraint-enumeration turns of 500–6,000 characters —
and it is what a reader sees; it is not token repetition. **Detection limit:** ~35k-token agentic
transcripts, 48 assistant turns, 16k and 32k completion budgets, temp 0.6 and 1.0 ± a
`presence_penalty` of 1.5, with the 25-word-window metric firing at ≥3 repeats. A loop outside that
envelope is not excluded.

**Sampling (C3).** The endpoint honours request-level sampling: temp 0, temp 0.6, and temp 1.0 +
`presence_penalty` 1.5 give distinct `reasoning_content` hashes for one prompt. The card's *general*
recipe — temp 1.0 plus `presence_penalty 1.5`, an anti-repetition knob this endpoint had never
served — produces the same shape as the served coding sampling (H2: no loop, more but shorter
reasoning turns; 17/2 valid plans). **No sampling-dependent loop, so no client-side mitigation is
indicated.**

**Context (C4).** `tools/needle-haystack.py` at 32k, 128k, and the native 262,144 gives **32k 3/3,
128k 3/3, 262,144 2/3** at the tool's 64-token budget. The 262k miss is a **budget artifact, not a
retrieval failure**: at the native window the model emits ~150–200 characters of reasoning before
the answer even under the served default, so a 64-token completion budget truncates the visible
answer (`finish_reason=length`, content empty or partial); re-probing that depth at 256 tokens
passes, and six repeats at 64 tokens give a mix of full answers (`finish=stop`) and truncated ones.
Retrieval itself is intact at ~256k prompt tokens — every probe that produced a full answer
returned the correct codeword. **Client-facing caveat:** at long context the served default does not
suppress reasoning, so a client with a short `max_tokens` that reads `content` sees empty or
partial replies.

**Cross-scale (C5) — the 9B arm, on `.31` (second boot; `/v1/models` ready ~280 s).** The same
long-horizon probe (temp 0.6, 16k, 12 turns) gives the same shape: **no decode loop** (per-message
25-word repeat max 2, none ≥3; the ≥3 windows are again the re-cited requirement list, and the one
1.0 cross-turn overlap is a 13-word stock opening line), reasoning growing 29 → 423 words, and 9/5
valid/invalid plans — the task is solved. Its needle ladder at 32k is **0/3 at a 64-token budget,
every reply empty**, but this is the *same* artifact, worse: a direct probe shows the 9B spends
250+ characters of reasoning before answering, so `max_tokens=64` (`finish_reason=length`) yields
empty content while `max_tokens=512` recovers the correct codeword in 2 of 3 tries (the third kept
reasoning past 512). **Retrieval is intact at both scales; the 9B is simply more prone to the
reasoning-before-answer behaviour than the 35B (0/3 versus 2/3 at 64 tokens).** So the same
client-side remedy applies at both scales — raise `max_tokens` — and this is a client-usage caveat,
not a decode loop.

**House battery, this boot: 37/37** (19/19 easy + 18/18 hard, zero flakes) — parity with the
2026-10-11 and 2026-10-14 runs, no regression. This is the lane's suite score: the
`tool-eval-bench` framework that Plan C's C2 named was **not configured in this registry** at the
time (no profile for `sparkrun benchmark tools`; one exists now, `benchmarking/standard-suite.yaml`,
added 2026-10-15), so C2 is met only by the house battery. Receipts: `~/benchmarks/ornith-horizon-20261014/`.

## `ornith-1.5-9b-nvfp4-dflash-sglang.yaml` — the small single-Spark arm

**Booted and measured 2026-10-14** (`.30`, one node, TP=1). This arm is the same SGLang DFLASH shape
as the 35B lane at a smaller scale: the official [`ornith-ai/Ornith-1.5-9B-NVFP4`][model-9b]
checkpoint (8.8 GB of weights, dense ~9B, multimodal) paired with the first-party
[`ornith-ai/Ornith-1.5-9B-DFlash`][draft-9b] draft (plain `DFlashDraftModel`, hidden-state taps
1/5/9/…/29 of the 32-layer target), one node, TP=1, 8 draft tokens.

**C1 (2026-10-14, `.30`, `benchmarking/decode-triage.yaml`, C1, n=5 per cell, decode-phase rows
only).** Two same-window sweeps on one boot: first (cold) **51.7 t/s @ d0 (σ 13.2)** / **56.6 t/s @
d8192 (σ 9.0)**, then warm **59.4 t/s @ d0 (σ 6.8)** / **54.1 t/s @ d8192 (σ 16.4)**. The signal is
**~52–59 t/s** — about half the 35B-A3B's ~100, which is expected rather than a defect: the 35B-A3B
activates ~3B params/token as a MoE, while this is a *dense* ~9B, so it is not a "smaller therefore
faster" arm. Do not pool the two sweeps (the cold d0 sweep carries one 26 t/s first-run outlier).
Spec decode was **engaged**: serve-log `accept len` mean **3.35** (min 1.85 / max 6.85) over 38
decode batches. Cold-cache boot reached port-open 200.5 s / HTTP-ready 218.3 s.

**House battery, same boot: 37/37** — 19/19 easy + 18/18 hard, zero flakes, at the served default
semantics (`tools/quality-battery.py --tier both --max-tokens 4096`); parity with the 35B's 37/37.

**Granted concurrency.** `max_num_seqs: 48` is *not* clamped on this arm: the serve log grants
`max_running_requests=48` and allocates a hybrid state pool of `max_mamba_cache_size: 273`, so the pool
is not the ceiling here (contrast the qwen3 lane's 48-requested/21-granted). The deliberate omission
of the `mamba_*` trio therefore costs nothing visible at C1; the pool split remains a
concurrency-scaling question, untested at C>1.

Receipts: `~/benchmarks/ornith-9b-20261014/` (`launch2.log`, `serve.log`, `c1-decode-triage*.json`,
`quality.{json,log}`, `bench-state/`).

Decisions a reader will question:

- **No `mamba_*` keys and no `moe_runner_backend`**, unlike the 35B arm. The MoE knob is inert (the
  checkpoint is dense). The `mamba_*` trio is a deliberate omission rather than an inference that the
  model lacks linear attention — this checkpoint *is* a Qwen3.5 hybrid (`text_config.layer_types`
  alternates three `linear_attention` layers to one `full_attention` layer, and `mamba_ssm_dtype` is
  declared `float32`), so the flags would apply. They are left to the engine defaults because the
  35B's `mamba_full_memory_ratio: 3.51` is a house value copied across lanes with no recorded
  derivation, and this first arm should not inherit an unmeasured traffic assumption. The
  granted concurrency is recorded above.
- **It does not mount the 35B's honed chat template.** That template is `qwen3.8-honed-v22.5.1`, a
  35B artifact. The 9B ships its own multimodal `chat_template.jinja` (vision tokens plus an
  `enable_thinking` toggle) and is served with it.
- **The card's `--speculative-dflash-block-size 8` is spelled as its upstream alias**
  (`--speculative-num-draft-tokens`), the spelling the shipped 35B arm is boot-proven on; sparkrun has
  no map key for the dflash spelling. The serve log confirms the mismatch against the draft's
  `block_size: 16` is warning-only: `DFLASH block size mismatch: using
  speculative_num_draft_tokens=8 but draft config block_size=16`.
- **The draft repo is deliberately left unpinned** (the 35B sibling's jzinno draft is too). A SHA pin
  is not a free reproducibility win here: a SHA-keyed fetch writes no `refs/` entry, and SGLang's
  offline draft-config lookup (`speculative_hook.py::_resolve_speculative_algorithm_alias` →
  `get_config`, with the container's `HF_HUB_OFFLINE=1`) resolves only `refs/main`, so a pinned draft
  dies at startup with `LocalEntryNotFoundError` before the server binds. Pin, if ever, only after
  re-checking this. See the recipe comment for the mechanism.

The pinned image **does** load the plain `DFlashDraftModel` (serve log: `Load weight end. …
type=DFlashDraftModel`), and accepts the alias spelling — both open boot questions are answered.

## `littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm.yaml` — the flagship 4-node lane

The 397B is the flagship MoE. It is served on **four** Sparks with vLLM at TP=4, `--enable-expert-parallel`,
and the checkpoint's own MTP head as the speculative method (3 tokens). The registry records a **235 GB
per-node** footprint at `gpu_memory_utilization: 0.80`, which is why it needs four nodes and cannot be a
single-Spark recipe.

**Booted + measured 2026-10-14** (`.30–.33`, TP=4, the pinned build, `benchmarking/decode-triage.yaml`,
decode-phase rows only): the MTP baseline serves **42.55 t/s @ d0 (σ 2.78)** and **38.48 t/s @ d8192
(σ 1.91)** — the first house number for the 397B, beside the card's 41.86 t/s. Spec decode engaged
(`Mean acceptance length` 2.68–3.06), `GET /v1/models` = the repo id, cold TTR 590.7 s. Receipts
`~/benchmarks/ornith-397b-ab-20261014/`.

**MTP vs first-party DFlash head — A/B closed 2026-10-14; MTP ships.** Both arms on the pinned build,
same window, same four nodes, `benchmarking/decode-triage.yaml`, decode-phase rows only (n=5 per cell):

| arm | speculative config | d0 t/s (σ) | d8192 t/s (σ) | `Mean acceptance length` |
|---|---|---|---|---|
| **MTP (shipped)** | `{"method":"mtp","num_speculative_tokens":3,…}` | **42.55** (2.78) | **38.48** (1.91) | 2.68–3.06 |
| DFlash | `{"method":"dflash","model":"ornith-ai/Ornith-1.5-397B-DFlash","revision":"db9c35a0…","num_speculative_tokens":8}` | 37.58 (4.45) | 33.64 (1.13) | 3.27 |

The vendor's own DFlash head (`ornith-ai/Ornith-1.5-397B-DFlash`, `db9c35a0…`, 2.58 GB, plain
`DFlashDraftModel`) **loses ~12% at both depths** — despite a *higher* acceptance length (3.27 vs ~2.9):
the extra accepted tokens do not clear the speculator's overhead. It also disables prefix-cache reuse on
this hybrid-Mamba target (vLLM, serve log: *"...every group — including Mamba groups [0..44] — will be
treated as a draft group … prefix-cache reuse across requests will be disabled"*). **The shipped MTP
default stands; the DFlash head is a documented one-knob alternative**, not a recipe
(`-o speculative_config={...}`, see *Caveats*). Receipts `~/benchmarks/ornith-397b-ab-20261014/`
(`armA-mtp.json*`, `armB-dflash.json*`, `armB-serve.log`, `armA-state/`, `armB-state/`).

- **Model:** [`littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft`][model-397b-graft] — a Little Cedar derivative
  that **grafts the BFP16 MTP MoE from the base model onto the NVFP4 quantization** (the base is
  `ornith-ai/Ornith-1.5-397B`, ≈800 GB in bf16). Its model card reports **41.86 tok/s** on a 4× DGX Spark
  vLLM run and links the full [Spark Arena benchmark](https://spark-arena.com/benchmark/c41b9f16-d269-4dd4-a179-cd2890b5f07c);
  that figure is the `C1 t/s` in our parent table. MIT-licensed, same as the family.
- **Runtime:** vLLM, container `ghcr.io/spark-arena/dgx-vllm-eugr-nightly`, now **digest-pinned**
  (`@sha256:b94ac8ac…`, tag `nightly-20260913`, vLLM `0.29.1rc1.dev17+gd2d649e67`) — see *Caveats: the
  397B container tag floats* below for why the pin exists and what it resolves.
- **Loader / engines:** `--load-format instanttensor` via `@eugr/mods/instanttensor-hybrid-draft-loader`,
  `moe_backend: marlin`, `linear_backend: flashinfer_cutlass`, `attention_backend: flashinfer`,
  `kv_cache_dtype: fp8_e4m3`, `performance_mode: throughput`, `mm_encoder_tp_mode: data`.
  `instanttensor` is **not** a separate on-disk format: vLLM maps it to the default loader with an
  InstantTensor safetensors iterator (`config/load.py`: *"load the Safetensors weights on CUDA devices"*;
  `model_loader/__init__.py`: `"instanttensor": DefaultModelLoader`), so a plain-safetensors speculative
  draft loads under it. The hybrid-draft mod's `auto` mode only rewrites the draft loader when the draft
  and target are the *same repo+revision* (the MTP case); for the DFlash A/B — a different draft repo — it
  returns the run's loader unchanged, i.e. the standard path. See *Caveats*, below.
- **Long context flag:** `VLLM_ALLOW_LONG_MAX_MODEL_LEN: 1` is set, but `max_model_len` is **262144** — the
  native window. The env var only lifts vLLM's refusal to exceed the checkpoint's declared maximum; it does
  not by itself extend context.

## Caveats

### The YaRN long-context route is documented upstream but not shipped here

Both model cards describe extending the native 262,144-token window with **YaRN RoPE scaling** — factor
4.0 → roughly 1M tokens — via either the checkpoint's `config.json` or a launch-time override
(`--hf-overrides` on vLLM, `--json-model-override-args` on SGLang, each gated by the engine's
"allow longer context" env var). **Neither recipe in this directory enables it.** The upstream caveat is
worth repeating: open-source runtimes apply YaRN *statically*, so the factor is in force for every request
and can erode quality on ordinary-length inputs — enable it only when a workload genuinely needs the
window, and size the factor to it. If you add YaRN here, that is new, quality-unverified territory; there
is no needle-in-a-haystack evidence for Ornith in this registry.

### `@eugr/mods/drop-caches` is inert under a default launch

Every Ornith recipe — the two shipped here and the three archived — lists `@eugr/mods/drop-caches`. Per
[`mods/drop-caches/README.md`](../../mods/drop-caches/README.md) that upstream mod **silently does nothing**:
its background loop keeps the process "alive" so it reads as success, but under sparkrun's default rootless
launch `/proc/sys` is mounted read-only (the write fails), and its command has a redirect-order bug that
sends the value to its log file instead of `/proc/sys/vm/drop_caches`. It has been left in place rather than
silently rewritten; the fixed, fail-closed replacement is the in-registry
[`@littlecedar/mods/drop-caches`](../../mods/drop-caches/README.md), which additionally requires a
`--rootful` (privileged) launch to work at all.

### The 397B container tag floats — now digest-pinned, and the nodes disagreed

`ghcr.io/spark-arena/dgx-vllm-eugr-nightly:latest` was the one unpinned container in the Ornith lane,
and the pin was **load-bearing in a way the card figure hid**: on 2026-10-14 the four serving nodes
held **three different builds** under that tag —

| node | image id | `dev.sparkrun.source-tag` | vLLM |
|---|---|---|---|
| `.30` (head) | `1e6901494c15` | `nightly-20260913` | `0.29.1rc1.dev17+gd2d649e67` |
| `.31` | `8af109d2db48` | `nightly-20260826` | `0.26.1rc1.dev1231+…` |
| `.32`,`.33` | `87e57cafa670` | `nightly-20260911` | `0.1.1.dev7+…` |

A four-node TP=4 launch on the bare tag is therefore **not one engine** — a same-window A/B on it
would compare builds. The registry's `:latest` meanwhile resolved to a *fourth* build
(`sha256:364005b0…`, `nightly-20261013`, vLLM `0.32.0rc1.dev78+gd96f1aa34`), which this cluster could
not pull (the OCI relay's registry download stalled at ~400 KiB/s and failed on all four nodes). The
recipe is now pinned to the build the head already held, distributed uniformly to all four nodes:

```
container: ghcr.io/spark-arena/dgx-vllm-eugr-nightly@sha256:b94ac8ac47603f9c3d14f88c12b90eacbc37c7a42f922631cb8c9ac80f7b37c3
```

That build (`nightly-20260913`) exposes `method: dflash` (`config/speculative.py`: `DFlashModelTypes =
Literal["dflash"]`, `use_dflash()`), so it is a valid engine for the DFlash-vs-MTP A/B — which closed on
it 2026-10-14 (MTP 42.55/38.48 vs DFlash 37.58/33.64 t/s; MTP ships). The card's 41.86 t/s is now backed
by a house measurement of the same family. The registry `:latest` seen on 2026-10-14 is
`sha256:364005b0…` (`nightly-20261013`) — left unpinned here because this cluster could not pull it.

### The 397B speculative config is a placeholder, so the method is a one-knob swap

`defaults.speculative_config` holds the whole `--speculative-config` JSON and `command:` renders it as
`--speculative-config '{speculative_config}'`. Two things depend on it **not** being inlined back into
`command:`: (a) `-o speculative_config={...}` only reaches a *declared* default, so inline JSON makes the
method swap a silent no-op; and (b) sparkrun reads the draft model+revision **out of that default**
(`runtimes/_vllm_common.py::detect_spec_config_draft`) to distribute the draft to all four nodes, so an
inline JSON leaves a DFlash draft undistributed (`Revision Not Found` at serve). The MTP arm renders
byte-identically to the old inline JSON. The DFlash arm is then exactly:

```bash
sparkrun benchmark performance <recipe> -H <4 nodes> --profile benchmarking/decode-triage.yaml \
  --output ~/benchmarks/ornith-397b-ab-<date>/armDFlash.json \
  -o 'speculative_config={"method":"dflash","model":"ornith-ai/Ornith-1.5-397B-DFlash","revision":"db9c35a091e89f942c609880f98bb385019dc4f8","num_speculative_tokens":8}'
```

The draft revision is pinned **inside that JSON** (vLLM's own `revision` field), never via
`model_revision:` — that SHA does not exist in the target repo. Verified against sparkrun 0.4.0: the
render distributes `ornith-ai/Ornith-1.5-397B-DFlash` alongside the target and emits the exact JSON above.

### The loader mod is inert for a DFlash draft (and needs no change)

`@eugr/mods/instanttensor-hybrid-draft-loader` (auto mode) rewrites the *draft* loader to lazy
safetensors only when the draft and target share a repo+revision — the MTP case. For the DFlash A/B the
draft is a different repo, so the mod returns the run's own loader (`instanttensor`), which is the
standard `DefaultModelLoader` safetensors path — a plain-safetensors `DFlashDraftModel` loads under it.
The mod is therefore left in place: a no-op for this arm, not a second knob.

### Guards (added 2026-10-14)

Until 2026-10-14 this lane had **no** `tests/test_<lane>_recipes.py` — the registry convention every
other lane follows — and nothing here was mechanically enforced beyond `sparkrun recipe validate`.
That gap is closed: [`tests/test_ornith_recipes.py`](../../tests/test_ornith_recipes.py) now guards the
three arms' shapes, the model-revision pins (and the 9B draft's deliberate *absence* of one), the 35B
draft's distribution-only pin together with its `refs/main` seed hook, the 9B
arm's deliberate `mamba_*`/`moe_runner_backend`
omission, its refusal to mount the 35B's honed template, and the served-model-id spelling (the repo-wide
class guard `tests/test_recipe_placeholder_resolution.py::ServedModelNameNotRebound` covers the last of
those across every lane as well). `tests/test_ornith_honed_chat_template.py` still covers the mod.

Two 397B guards were added with the spec-decode A/B: `FlagshipSpeculativeConfigIsSwappable` (the
`{speculative_config}` placeholder must stay a declared default and stay out of `command:` — the two
silent failures above) and `FlagshipContainerIsDigestPinned` (§3.8).

## Archived recipes

Three Ornith recipes were moved to [`attic/ornith/`](../../attic/ornith/) (commit `e0633ed`) and are **not**
part of the shipped surface:

- A `littlecedar-ornith-1.5-397b-*` b12x fork of the 397B vLLM recipe — an earlier variant carrying
  `CUTE_DSL_ARCH` and other b12x env switches, tagged `broken` in its metadata.
- `ornith-1.5-35b-a3b-nvfp4-vllm.yaml` and `ornith-1.5-35b-a3b-nvfp4-vllm-b12x.yaml` — vLLM arms for the
  35B. The registry carries **no measured figure** for either, and the DFlash2 draft is an
  SGLang-targeted artifact (its card only documents SGLang usage), so the shipped 35B recipe is the
  SGLang one; the vLLM arms are retained as provenance, not as a benchmarked comparison.

They are kept as provenance; the b12x API surfaces they referenced are not covered by any current guard.

## 2026-10-10 update scan (no recipe changes)

A model/runtime scan for this lane found **no superseding checkpoint**: `ornith-ai` has published no
new base/quant revision since 2026-08-29, and the `jzinno` DFlash2 draft is unchanged since
2026-08-23 (it remains the only Ornith DFlash2 drafter). What exists and what it means here:

- **First-party plain-DFlash drafts for all three scales** (`ornith-ai/*-DFlash`, 2026-09-28) —
  plain `DFlashDraftModel`, not DFlash2, with **no published numbers**. Candidate only as the 397B
  vLLM lane's spec-decode counterpart; unmeasured.
- **A third-party vLLM-only NVFP4 MoE DFlash2 drafter** (DaoCloud, 2026-09-10) needs three
  unreleased vLLM PRs — not actionable on our pins.
- **A DGX-Spark W4A16 NVFP4 quant with an MTP head** (r0b0tlab, 2026-08-21) claims accuracy parity
  at 63–77 t/s — **slower than this lane's ~100 t/s C1**; not adopted.
- **Upstream SGLang 0.5.18→0.5.21** adds DFlash-reranker and GDN fusion wins, but also **breaks this
  lane**: the Mamba/SWA radix-cache args our 35B recipe passes (`mamba_radix_cache_strategy`,
  `mamba_full_memory_ratio`) were removed upstream. Any container bump must re-verify the serve
  line first.
- **A known lead, not yet tested:** the DFlash2 author's own reference run measured **114.2 tok/s**
  with `moe_runner_backend marlin`, `mamba_radix_cache_strategy extra_buffer`, `mamba_ssm_dtype
  float32`, and **10 draft tokens** — we ship `flashinfer_cutlass` / `extra_buffer_lazy` /
  `bfloat16` / 4. That is a multi-knob confound (see the caveats section above), so a same-node
  A/B is the only honest way to chase it.

## Validation

```bash
H="$PWD/.local/sparkrun-home"
for f in recipes/ornith/*.yaml; do HOME="$H" sparkrun recipe validate "$f"; done
uv run python -B -m unittest tests.test_ornith_recipes
```

All three recipes validate clean. See [`AGENTS.md`](../../AGENTS.md) for the full
run/lint/benchmark workflow.

## Recipe comment archive (2026-10-14)

Prose moved out of the three shipped recipes when the lane adopted the repo rule that a shipped
recipe's `#` comments carry only facts an operator could get *wrong* without (a silent-failure
footgun, a required ordering/pairing, a client contract). Everything below was deleted from the YAML
and is kept here verbatim; anything still model- or config-relevant for running an arm was also
folded into [`recipes/ornith/README.md`](../../recipes/ornith/README.md).

### `ornith-1.5-9b-nvfp4-dflash-sglang.yaml`

- (`model_revision`) "2026-10-14: pins the snapshot the runner caches hold. The offline engine needs
  the explicit --revision: a SHA-keyed download writes no refs/ entry. This is the 9B arm of the same
  family block as the 35B sibling recipe; the two differ by engine knobs, not by model, so read that
  recipe's comments too — but note the divergences called out below."
- (`metadata`) "vision: the checkpoint is Qwen3.5 multimodal (image-text-to-text; config carries a
  vision_config and image/video token ids), served with no --limit-mm-per-prompt cap."
- (`mods`) "The drop-caches mod is inert under a default rootless launch (see the 35B sibling's
  comment and mods/drop-caches/README.md); it is listed for lane consistency, not because it clears
  the page cache for you." — and "Supplies --load-format fastsafetensors below."
- (`max_num_seqs`) "Admission cap only. This checkpoint is a Qwen3.5 hybrid (GDN linear-attention
  layers every 3rd of 4), so the effective ceiling can be the hybrid state pool, not this literal —
  read the grant ("capped to N") from the serve log."
- (`kv_cache_dtype`) "Safe to spell: this hf_quant_config ships kv_cache_quant_algo FP8, so the
  literal and the checkpoint agree (unlike an `auto` whose resolution is silent)."
- (`mamba_*` / `moe_runner_backend` absence) "moe_runner_backend is meaningless here (dense MLP, no
  experts). The mamba trio is deliberately omitted rather than imported: the 35B's
  `mamba_full_memory_ratio: 3.51` is a house value copied across lanes with no derivation, so the
  engine's own defaults run. Measured 2026-10-14: the pool does not clamp the admission cap
  (max_running_requests=48 with max_mamba_cache_size=273); see AGENTS.md §1."
- (`speculative_draft_model`) "First-party DFlash draft (plain DFlashDraftModel, taps 1/5/9/13/…/29
  of the 32-layer target) — NOT the third-party dflash2 draft the 35B sibling ships."
- (draft left unpinned) "Left unpinned on purpose, like the 35B sibling's jzinno draft. A SHA pin
  here is not a free reproducibility win: a SHA-keyed fetch writes no refs/ entry, and SGLang's
  offline draft-config lookup (speculative_hook.py::_resolve_speculative_algorithm_alias →
  get_config, HF_HUB_OFFLINE=1 in-container) resolves only refs/main — a pinned draft dies at startup
  with LocalEntryNotFoundError. Boot receipt: AGENTS.md §1."
- (`speculative_draft_tokens`) "8, the author card's value. The card spells it
  --speculative-dflash-block-size, which upstream is an alias of --speculative-num-draft-tokens for
  DFLASH (SGLang v0.5.18 server_args.py:2115-2117); sparkrun has no map key for the dflash spelling,
  so this uses the alias the shipped 35B arm is boot-proven on. The draft's own
  dflash_config.block_size is 16: 8 is <= it (the 35B runs 4 against a 16 block), and the DFLASH
  worker only warns on the mismatch."

### `ornith-1.5-35b-a3b-nvfp4-dflash2-sglang.yaml`

- (`model_revision`) "2026-10-11: pins the snapshot the runner caches hold. The caches' chat template
  was honed in place in September (qwen3.8-honed-v22.5.1), which sparkrun's model-preparation
  validator now rejects against the hub's current metadata at this same revision (hub sizes changed
  under it). Fix: caches carry hub content again, and the honed template ships via `--chat-template`
  below, staged by recipes/ornith/mods/ornith-honed-chat-template. The pin also keeps the offline
  engine on this exact snapshot (--revision is required: a SHA download writes no refs/ entry). Draft
  jzinno snapshot 9b4852c05fd00b672b7434b1bb105bc03c8682b0, pinned in `defaults:` below as a
  distribution-only key; the pre_exec hook seeds the refs/main that the offline draft-config lookup
  needs (AGENTS.md §3.12)."
- (`metadata`) "vision: the checkpoint is Qwen3.5-MoE multimodal (image-text-to-text; config carries
  a vision_config and image/video token ids), served with no --limit-mm-per-prompt cap."

### `littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm.yaml`

- (`metadata`) "vision: multimodal checkpoint (image-text-to-text); the serve line carries a vision
  encoder flag (--mm-encoder-tp-mode data)."
- (`speculative_config`) "The speculative config is a placeholder rather than inline JSON for two
  reasons: `-o speculative_config={...}` is then the whole one-knob method swap (MTP vs DFlash), and
  sparkrun reads the draft model+revision *out of this default* to distribute the draft
  (`runtimes/_vllm_common.py::detect_spec_config_draft`) -- an inline JSON leaves a DFlash draft
  undistributed. Values are literal: a nested `{max_model_len}` here is NOT substituted (the render
  is a single pass over `command:`). Keep the shell single quotes: the JSON holds double quotes."

## References

- Ornith 1.5 announcement — <https://ornith.ai/ornith_1_5.html>
- DFlash 2 — [Keep Drafting Parallel](https://inco.ai/blog/dflash2/) · [DFlash: Block Diffusion for Flash Speculative Decoding](https://arxiv.org/abs/2602.06036)

<!-- Links -->
[model-35b]: https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B-NVFP4
[model-397b-graft]: https://huggingface.co/littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft
[model-9b]: https://huggingface.co/ornith-ai/Ornith-1.5-9B-NVFP4
[draft-dflash2]: https://huggingface.co/jzinno/Ornith-1.5-35B-A3B-DFlash2
[draft-9b]: https://huggingface.co/ornith-ai/Ornith-1.5-9B-DFlash