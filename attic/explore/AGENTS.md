# `attic/explore/` — Explore-lane working notes

Lane working state, measured histories, selection receipts, serving traps and per-arm research for
the `explore` lane — everything that is not a shipped recipe. The shipped recipes (and this
directory's index) are documented in
[`recipes/explore/README.md`](../../recipes/explore/README.md).

## From recipes/explore/README.md (2026-10-14)

# Explore lane

Frontier reasoning + tool-calling models that push the frontier on DGX Spark, selected by the
owner's criterion for this lane (**accuracy decides; smaller and faster preferred**, 2026-10-13 —
supersedes the registry's node-count→speed default, which had decided this lane's earlier pass on a
1.8 t/s gap inside one arm's own σ). The lane ships the
**two selected models** (owner selection 2026-10-13; the 2026-10-11 "no recipe cap" round built
four and moved the rest to the attic). Full candidate research — 8 families, five corrections to the earlier
`mad-science/EXPLORE-CANDIDATES.md`, per-candidate verification checklists — is in
[`EXPLORE-MODELS-RESEARCH.md`](EXPLORE-MODELS-RESEARCH.md).

| recipe | runtime | model | nodes | C1 t/s | status |
|---|---|---|---|---|---|
| [`ling-3.0-flash-int4-dspark-sglang.yaml`](../../recipes/explore/ling-3.0-flash-int4-dspark-sglang.yaml) | SGLang | [inclusionAI/Ling-3.0-flash-int4][ling] + [DSpark draft][lingd] (draft pinned `d60b0e12`) | 1 | **45.5** | **BOOT-VERIFIED 2026-10-11** (quality 37/37; 262k needle-verified at 0.80) — **KEPT (rank 1, accuracy)**; draft re-pinned 2026-10-14 (re-verified 54.7 t/s, 37/37) |
| [`kolibri-1-78b-fp8-vllm.yaml`](../../recipes/explore/kolibri-1-78b-fp8-vllm.yaml) | vLLM 0.29 + plugin | [Aleph-Alpha/Kolibri-1][kol] (pinned `258cae8f`) | 1 | **47.3** | **BOOT-VERIFIED 2026-10-12** (quality 36/37 @4096; `kolibri1` parsers via the plugin mod) — **KEPT (rank 2, near-tie accuracy; smaller + faster)**; re-pinned 2026-10-14 (re-verified 47.4 t/s, 37/37 @4096) |

**Archived 2026-10-13** (measured but not selected; manifest [`attic/explore/ARMS-MANIFEST.md`](../../attic/explore/ARMS-MANIFEST.md)):
[`nemotron-3.5-lightning-30b-nvfp4-dspark-vllm.yaml`](../../attic/explore/nemotron-3.5-lightning-30b-nvfp4-dspark-vllm.yaml) and
[`nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm.yaml`](../../attic/explore/nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm.yaml).

## Measured

- **Nemotron-262k (archived 2026-10-13): 77.7 t/s @ d0** (σ 9.8, n=5) and 76.3 @ d8k (σ 26.0) on `benchmarking/decode-triage.yaml`, TP=1,
  20.8 GB NVFP4 weights. The DSpark draft engages: **acceptance length 3.67 at an 88.9% acceptance
  rate**. The 93–96 t/s third-party figure was not reproduced on our node — quote ours.
- **Quality: 33/37** (`tools/quality-battery.py`, one boot, 2026-10-11) — 18/19 easy + 15/18 hard.
  Misses: `wp-3`, `hard-arith-1`, `hard-arith-2`, `trick-3`. For scale against the other lanes in this
  pass: ornith 37/37 and qwen3.8-27B DFlash2 37/37 (both single-node, ~100 / 33.8 t/s), coder-next
  35/37 at 71.7 t/s. Nemotron is the fastest measured quality arm below ornith and pays ~4 tasks for it.

  **Checklist closure (2026-10-11):** (a) the `moe_backend: marlin` pin was found **inert** — an edit
  had dropped the `--moe-backend` line and sparkrun's validation stays silent for a flag-map key the
  template omits; the verified boot ran with `moe_backend='auto'` and vLLM auto-selected marlin anyway,
  so the numbers stand and the pin is restored. (b) `--tool-call-parser qwen3_coder` **verified**: a
  forced `tool_choice` produces well-formed structured tool_calls (`{"city": "Paris"}`-style
  arguments, `finish_reason: tool_calls`); in auto mode the model answers in prose, which is model
  behaviour, not a parser failure. (c) The card's 1M-context claim needs a different `max_model_len`
  and is a separate arm, not a checklist item.

- **TP=1 re-measure (2026-10-13)**: the DSpark **acceptance length did not reproduce** —
  1.53–1.72 (mean ≈1.66) at 17.6–24.0% acceptance vs the shipped 3.67 @ 88.9%, though the draft is
  still engaged (accept len > 1). C1 held: 70.10 t/s @ d0 (σ 14.11) vs the shipped 77.65 (σ 9.82)
  and 77.19 @ d8k vs 76.30 — inside σ and the lane's 7–25% noise floor. Quality 33/37 with the
  identical miss set. The acceptance drop is suspected a metric-window artifact (the depth-8k cells
  mix context loads into the acceptance window) but is **unproven**; the shipped acceptance figure
  stands. Receipts: `~/benchmarks/explore-tp1-20261013/` on the head node.

### Ling-3.0-flash-int4 (2026-10-11)

- **BOOT-VERIFIED** on one node: DSPARK configured with the external 1.36B draft and the KDA
  ReplaySSM verify path; answers correctly in `content` (`391` for 17×23, reasoning split cleanly by
  the `ling3` parser — no empty-content trap on this template).
  **Long context (needle-probed 2026-10-11):** the `rope_scaling missing 'factor'` boot warning is
  **benign** — the checkpoint declares no scaling at all (`rope_scaling: null`, native 262,144,
  rope_theta 6e6), so SGLang's 1.0 default is a no-op and the native window is real: a verbatim
  needle is retrieved at 8k, 64k (depths 10/50/100) and 150k tokens. At `mem-fraction-static 0.75`
  the KV pool held **176,203 tokens** and a 200k request auto-truncated then failed HTTP 500 OOM.
  **Closed 2026-10-12** (see the 262k subsection under Measured): the recipe now ships **0.80**
  (pool 313,752 tokens) and the full 262k window is servable and probed PASS. The third-party
  notebook's 0.87 rung (576,930-token pool) stays the documented OOM-risk ceiling and is not needed
  for 262k. Receipts: `~/benchmarks/ling-needle-20261011/` and `~/benchmarks/ling-262k-20261012/`
  on the head node.
- **Quality: 37/37** (`tools/quality-battery.py`, one boot) — 19/19 easy + 18/18 hard, **zero
  failures**. That ties ornith and qwen3.8-27B DFlash2 at the top of the pass.
- **Measured C1: 45.5 t/s @ d0** (σ 5.5, n=5) and 32.3 @ d8k (σ 8.2) on `decode-triage.yaml`.
  **DSPARK engagement CONFIRMED on a retained boot**: SGLang decode lines report
  `accept len: 2.73, accept rate: 0.22` — that is an **engagement proof** (accept len > 1 means the
  draft works), read off a single short decode request. **Steady state under real decode load**
  (4 concurrent ~400-token generations): **accept len 3.64–3.73, accept rate 0.29–0.34**, aggregate
  gen throughput up to 116.7 t/s. So the draft genuinely works, but steady-state acceptance sits
  below the third-party port's 5.2–6.4 — and that difference DOES arithmetically account for most
  of the C1 gap (45.5 × 5.8/3.5 ≈ 75, against their ~83): same recipe flags, different acceptance.
  Whether their higher acceptance is prompt-mix, engine build, or tuning is untested.
- Third-party (not reproduced here): ~83 t/s C1 with DSPARK, GPQA-D 83.65 on the INT4 column.

### Ling-3.0-flash-int4 — 262k closure (2026-10-12)

- **Ladder boot at `mem-fraction-static 0.80`** (one boot, node .35, task
  `87b149af…_64af2f7668b6`): KV pool **313,752 tokens** (`max_total_num_tokens`,
  fp8_e4m3, K+V 11.96 GB, `available_gpu_mem` 22.34 GB after allocation). The
  2026-10-11 0.75 boot measured 176,203; the third-party 0.87 rung reported
  576,930. 0.80 is the first rung tried — no 0.85/0.87 boot needed.
- **262k needle probe PASS**: full-window prompts (~256.9k tokens by the tool's
  2%-headroom cap, calibration ratio 4.0546 chars/token) retrieved verbatim at
  depths 10/50/90 — 256,554 / 256,595 / 256,059 prompt tokens, ~1310 s each
  (~196 t/s effective prefill-through-the-instrument). `needle-262144.json`
  verdict `PASS`.
- **4-way concurrency smoke clean**: 4 parallel 2k-token chat completions
  (max_tokens 128, temperature 0) all completed, 5.7 s wall; serve log shows
  zero `Out of memory` / retraction events across the whole boot (the only
  grep hit is `retraction_policy='length'` in the ServerArgs echo).
- **Shipped**: `gpu_memory_utilization: 0.80` in the recipe; 0.87 stays the
  documented ceiling. Receipts: `~/benchmarks/ling-262k-20261012/` on the head
  node (boot log, `max_total_num_tokens` lines, probe.py + probe.log,
  `needle-262144.json`, smoke4.py).

### Ling-3.0-flash-int4 — served-id fix (2026-10-13)

- The arm shipped `--served-model-name {model}`, and sparkrun rebinds every
  `{model}` occurrence to the prepared snapshot path on a real launch (`-n` still
  prints the repo id), so it advertised
  `/cache/huggingface/hub/models--inclusionAI--Ling-3.0-flash-int4/snapshots/7a27e9eb…`
  as its model id. It now declares `served_model_name: inclusionAI/Ling-3.0-flash-int4`
  and renders `--served-model-name {served_model_name}`.
- **Receipt**: boot `3effce2e30113dd9_64af2f7668b6` on `.35` — `GET /v1/models` →
  `inclusionAI/Ling-3.0-flash-int4` (262144 ctx); TTR port-open 224.1 s.

### Ling-3.0-flash-int4 — draft re-pin (2026-10-14)

- **The draft was floating and is now pinned.** `inclusionAI/Ling-3.0-flash-dspark` `main`
  moved to `d60b0e1291dacb256194c6d48154398730cf8986` on 2026-10-12 (the 2026-10-11 boot had
  followed `main` unpinned). File-level diff against the revision that boot used
  (`8e5d9988c9b0`): **README.md only** — `model.safetensors` LFS sha256 `0885659804b3…` and
  `config.json` blob `b6548106a7ab…` are identical at both revisions, so the move is a no-op
  for serving. `speculative_draft_model_revision: d60b0e12…` now lives in `defaults:`.
- **The pin is declared *and* rendered**: `--speculative-draft-model-revision
  {speculative_draft_model_revision}` in the command, not distribution-only. This image accepts
  the flag — the serve log's `ServerArgs` echo reads
  `speculative_draft_model_path='inclusionAI/Ling-3.0-flash-dspark',
  speculative_draft_model_revision='d60b0e1291dacb256194…'`. (The ornith 9B arm keeps its draft
  pin distribution-only because *that* pinned image is unproven on the flag; this one is proven,
  so the pin also governs what SGLang resolves.)
- **DSPARK engaged on the pinned draft.** 26 metric windows across the sweep + battery: accept
  len **2.60–5.78** (d0 windows 3.92–5.78, d8k 2.60–4.58), accept rate up to 0.59 — above the
  shipped single-request engagement proof (2.73) and reaching into the third-party 5.2–6.4 band.
- **decode-triage (same node .30, 2026-10-14)**: **54.7 t/s @ d0 c1** (σ 5.58, n=5) and **34.1**
  at d8k c1, against the shipped 45.5 (σ 5.5) / 32.3 (σ 8.2). The two are directly comparable —
  both are `decode-triage` through sparkrun, and the shipped receipt
  (`~/benchmarks/ling-20261011/decode-triage.yaml`) records the same
  `extra_body: return_token_ids=false` this window used (trap 6). The +20% at d0 is inter-boot
  variance, not a regime change: the shipped run's own five d0 samples span **39.1–55.6** and this
  window's span **44.2–60.8**, overlapping ranges whose means differ by about one sample spread,
  inside the lane's recorded 7–25% inter-boot floor. So the shipped 45.5 stands and this reading
  is recorded beside it (d8k is +5.6%, well inside).
- **House battery 37/37** (19/19 easy + 18/18 hard, zero failures) — reproduces the shipped score.
- Receipts: `~/benchmarks/explore-repin-20261014/` on `.30` (`ling-boot.log`,
  `ling-serve-live.log` with the acceptance series, `ling-decode-triage.{json,yaml,csv}`,
  `ling-battery.{json,log}`), plus `ling-boot-failed-homemismatch.log` (trap 5's failure).

### Nemotron-3.5-Lightning — 1M-context arm (2026-10-12)

Archived arm [`nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm.yaml`](../../attic/explore/nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm.yaml) (built 2026-10-12; moved to the attic 2026-10-13):
the (now-archived) 262k recipe verbatim with exactly two defaults changed —
`max_model_len: 1000000`, `gpu_memory_utilization: 0.91` — testing the card's
official GB10 numbers against the community warning that 0.91 "leaves ~1 GiB
free and swaps".

- **Boot**: clean on node .35, TTR port-open 233 s. KV cache at 0.91:
  **87.27 GiB → 21,344,213 tokens**, "maximum concurrency for 1,000,000 tokens
  per request: 21.34x". vLLM did not refuse the 1M window (it refuses when the
  pool cannot hold `max_model_len`) — the card's 1M claim **boots**.
- **1M needle probe PASS** (depths 10/50/90): run 2, calibrated ratio
  3.8590 chars/token (run 1 used Ling's 4.0546 and only reached 876k
  server-counted tokens — verdict TRUNCATED, needle still retrieved at all
  depths; ratio receipt kept). Run 2 prompts: 981,595 / 982,111 / 981,923
  server-counted tokens, needle retrieved verbatim at every depth, ~797 s each
  (~1,233 t/s effective prefill through the instrument). `needle-1000000.json`
  verdict `PASS`.
- **Swap pressure is real but did not bite**: during run-2 1M prefills the node
  sat at 119/121 GiB used with **~1 GiB free** (exactly the community
  warning) and 2.05 GiB of swap allocated, but vmstat showed **no active
  swap-in/out** (si/so 0/0) and the engine ran at 99% CPU. The 0.91 point is
  workable under this needle load; sustained multi-tenant load is untested.
- **Decode-triage**: **72.2 t/s @ d0** (σ 15.1, n=5) and 69.3 @ d8k (σ 10.7) —
  ~7% below the 262k/0.8 recipe's 77.7 on the same node/boot pattern; quote ours.
- Both this arm and its 262k parent were **archived 2026-10-13** (the owner's accuracy criterion placed
  them behind Ling-3.0-flash and Kolibri-1); the arm documents the measured servability of the card's 1M
  point. Receipts: `~/benchmarks/nemotron-1m-20261012/` on the head node (boot log, both probe runs,
  decode-triage triple).

### Kolibri-1 (2026-10-12)

New recipe [`kolibri-1-78b-fp8-vllm.yaml`](../../recipes/explore/kolibri-1-78b-fp8-vllm.yaml) +
[`recipes/explore/mods/install-kolibri-plugin`](../../recipes/explore/mods/install-kolibri-plugin): the vendor's
own container image is amd64-only, so the recipe serves on the **stock
multi-arch `vllm/vllm-openai:v0.29.0`** (digest-pinned) with Aleph Alpha's
pure-Python plugin installed by a sparkrun mod
(`pip install --no-deps aleph-alpha-inference==1.0.0`, per the plugin README —
the image's vLLM/torch/transformers are untouched; the mod fails closed on
import/entry-point failure and is idempotent via a content marker).

- **Boot**: clean on node .35, TTR port-open 647 s; weight load alone 500 s
  (the forum's 1,087 s figure not reproduced). `GET /v1/models` lists
  `Aleph-Alpha/Kolibri-1`; plugin verified in-container (`aleph-alpha-inference
  1.0.0`, `vllm.general_plugins` entry point present) — receipt
  `plugin-verify.log`. KV cache at util 0.78: **20.03 GiB → 1,961,775 tokens**,
  7.48× concurrency at the native 262,144 window.
- **Round-trips**: `enable_thinking: false` → clean `content` (`391` for
  17×23); thinking ON → reasoning split correctly (`reasoning` 661 tokens,
  content `**9** remain.` for the sheep trick). The `kolibri1` parsers work.
- **Decode-triage**: **47.3 t/s @ d0 c1** (σ 0.10, n=5) and 46.3 @ d8k c1
  (σ 0.12) — near the third-party sm121 build's 48 t/s and **2.3× the stock
  build's 20.4 t/s** the research doc expected. The recipe carries an
  unpublished mod, so `sparkrun benchmark performance` cannot take it yet
  (no `--transfer-mode local` on that subcommand): the same
  `uvx llama-benchy` invocation sparkrun would run was used directly against
  the live serve (identical profile args), receipt `decode-triage.json`.
- **Quality: 36/37** (`tools/quality-battery.py --tier both --max-tokens 4096`,
  2026-10-12, two runs, identical): 18/19 easy + 18/18 hard. The lone failure
  is `needle-1` — an **empty reply from truncated thinking** (it PASSES at the
  default 384 budget, where the model answers without thinking; the same
  384-budget run instead fails `code-big`/`big-1`, which need the thinking
  room). Union across the two budgets is 37/37, so quote "36/37 @ 4096, with
  `needle-1` a budget-dependent thinking truncation". This is why the battery
  gained an optional `--max-tokens` (default 384 — unchanged for every other
  lane).
- **Selected (2026-10-13, rank 2)**: **KEPT by the owner's criterion (accuracy decides; smaller and faster
  preferred).** Its 36/37 @4096 is a 37/37 union — the lone miss is a thinking-budget truncation — so it is
  a near-tie with Ling's 37/37 on the deciding factor, and it wins the stated preference (74 GB / util 0.78
  vs Ling's 154 GB / 0.80; 47.3 vs 45.5 t/s).
- Receipts: `~/benchmarks/kolibri-20261012/` on the head node.

- **TP=1 re-measure (2026-10-13)**: C1 −1.8% uniformly — 46.46 t/s @ d0 (σ 0.18) vs the shipped
  47.27, 45.41 @ d8k vs 46.31 — within the lane spread, no material change. Receipts:
  `~/benchmarks/explore-tp1-20261013/` on the head node.

### Kolibri-1 — re-pin to `258cae8f` (2026-10-14)

- **The pin was one upstream fix behind.** `main` moved to
  `258cae8ffffc8c12db670bdbc6ac01bcf8826c87` on 2026-10-13 ("fix: quantization config for
  transformers implementation"). File-level diff vs the pin (`35bc4d3be745…`) — **`config.json`
  only**: 3904 → 3921 bytes, one key added, `"lm_head"` in
  `quantization_config.modules_to_not_convert`. All 32 weight shards, `tokenizer.json`,
  `tokenizer_config.json` (the chat template), `model.safetensors.index.json` and
  `generation_config.json` are **blob-identical** across the two revisions (same LFS sha256 /
  blob ids), so the weights, tokenizer and template this lane measured are unchanged. The
  checkpoint's `lm_head.weight` is **BF16** (`[128000,2560]`, and there is no
  `lm_head.weight_scale_inv`) — the pre-fix config declared an fp8 quantization config claiming a
  tensor the repo ships unquantized, so the upstream fix aligns the declaration with the
  checkpoint. Re-pinned in all three places (`model_revision:`, the snapshot path in `command:`,
  `--revision=`).
- **Boot (node .30, 2026-10-14)**: task `2d49ec39cad5a528_2d38dfc4605e`, clean; TTR port-open
  **611.1 s** (HTTP-ready 611.1 s), weight load 500.0 s (73.48 GiB), KV pool at util 0.78
  **18.99 GiB → 1,859,922 tokens**. `GET /v1/models` → `Aleph-Alpha/Kolibri-1` (262144 ctx).
- **Plugin mod re-confirmed on the re-pinned revision**: `recipes/explore/mods/install-kolibri-plugin` installed
  `aleph-alpha-inference==1.0.0` and its live import + entry-point gate passed
  (`plugin OK: ['aleph_alpha_inference', …]`); the strict gate re-runs the install on every boot,
  so the 2026-10-13 stale-marker defect does not recur. `kolibri1` parsers re-verified end-to-end:
  `reasoning_effort: none` → clean `content` `"391"` (17×23); thinking ON → `content`
  `**9** remain.` with `reasoning` split out (3127 chars).
- **decode-triage (same node .30, 2026-10-14)**: **47.44 t/s @ d0 c1** (σ 0.10, n=5) and **46.62**
  at d8k (σ 0.06) — reproduces the shipped 47.27 / 46.31 at +0.4% / +0.7%.
- **House battery 37/37** at `--max-tokens 4096` (19/19 easy + 18/18 hard, **no misses**) — one
  better than the shipped 36/37: `needle-1`, previously an empty reply from truncated thinking,
  answered in this window, so the shipped 37/37 union is now a direct measurement.
- Receipts: `~/benchmarks/explore-repin-20261014/` on `.30` (`kolibri-boot.log`,
  `kolibri-decode-triage.json`, `kolibri-battery-4096.{json,log}`, `kolibri-parser-check.log`,
  `kolibri-arm.log`; the mod's log is in the vLLM runtime cache at
  `~/.cache/sparkrun/runtime-cache/vllm/Aleph-Alpha__Kolibri-1-*/modlogs/`).

### humanizer-12b-vllm — text-rewriting arm (2026-10-14)

New recipe [`humanizer-12b-vllm.yaml`](humanizer-12b-vllm.yaml) — the lane's first `/v1/completions`
arm: `jialinyyzz/humanizer`, a 12B `google/gemma-4-12B` finetune (Apache-2.0, ungated, 23.9 GB bf16)
that rewrites one AI-written draft so it reads human. **Not a chat model**: the working surface is
`/v1/completions` with a **byte-exact prompt** assembled from the repo's `prompt_format.json`
(`instr + "\n\n" + draft.strip() + sep`; fingerprint `cc51d66b4c593fbe`, asserted on every call), and
the recipe adds `--generation-config vllm` so the checkpoint's own `generation_config.json` `top_k 64`
never becomes a server default. The checkpoint ships **no chat template** at all — vLLM's
`/v1/chat/completions/render` 400s on it — so the completion endpoint is the only surface.
Sampling is per-request (temp 1.0, top_p 0.95, top_k off, min_p 0, rep 1.0, ≤2048 tokens, no stop
strings). Same digest-pinned `vllm/vllm-openai:v0.29.0` as Kolibri (moved to `v0.30.0` 2026-10-16 —
boot receipt in §Engine bump below).

- **Boot-verified on `.35`**: task `sparkrun_4bceadd734dbdb40_64af2f7668b6`; container start →
  **TTR port-open 277.9 s** (HTTP-ready 277.9 s), total launch 1082.9 s. The serve log resolves
  `Gemma4UnifiedForConditionalGeneration` on 0.29.0 (transformers 5.16.1 in-image) and echoes every
  recipe default (`generation_config: vllm`, `limit_mm_per_prompt {'image': 0, 'audio': 0,
  'video': 0}` → `running in text-only mode`). `GET /v1/models` → `jialinyyzz/humanizer` (8192 ctx);
  KV cache 370,597 tokens (45.2× at 8192); weights 22.68 GiB in 140.6 s. Heterogeneous head dims
  (256 sliding / 512 full) force `TRITON_ATTN` — FA4 is unavailable for this arch.
- **§7(c) measurement** (`~/benchmarks/humanizer-20261014/`, 20 drafts × 2 samples = 40 rewrites):
  **131.7 s per 1k output tokens** (936.2 s / 7,106 tokens; mean 23.4 s and 177.7 tokens per
  request), which the serve log's own `Avg generation throughput 7.5–7.7 t/s` reproduces. Fact check
  by lexical instrument: 20 number/date/name flags, **all 20 reviewed as the same value in another
  notation** (`214,000`→`214k`, `21:40`→`21.40h`, `September`→`14.09`, `degrees Celsius`→`°C`) — so
  **0 dropped facts**; **1 genuine defect** found outside that instrument (an invented `(104°F)` for
  `4 °C`, which is 39.2 °F). Formatting: 35 dropped elements, **all markdown markers** (`##` gone
  while the heading text stays; the changelog's bullets merge with ` * ` separators), content intact;
  29/40 rewrites dropped nothing. No Chinese-output regressions in 40 rewrites.
- **Card figures cited, not reproduced**: 95% judged human by Originality.ai at its strictest setting
  (11/210) and 376/420 English rewrites with no factual problem — both are the card's `Q8_0.gguf`
  llama.cpp numbers on one date with an external *paid* detector; this arm serves bf16 safetensors
  through vLLM, and that comparison is not drawn.
- **The whole repo is distributed — 87.6 GB, and not narrowable** (*corrected 2026-10-15*: the head's
  config (needed by Ling, trap 5) selects the full snapshot, so the node's cache holds 63.6 GB of
  GGUF quants this arm never loads — 796.1 s of distribution for a 23.9 GB checkpoint.
  `model_file_selection` is a sparkrun **config** key, not a recipe key, and with no
  `model.safetensors.index.json` both `auto` and `all` select the whole snapshot (`safetensors`
  errors), so the recipe cannot narrow it).
- **Verdict**: boots and rewrites faithfully at ~7.6 t/s single-stream (23 s per short draft). Off
  the lane's brief (no reasoning, no tool calls), so it competes with nothing in the selection.
- Receipts: `~/benchmarks/humanizer-20261014/` on the head (and on `.35`): `SUMMARY.md`, `boot.log`,
  `serve.log`, `measure.py` + `analyze.py` (stdlib), `results.json`, `analyze.log`.

### Poolside Laguna-XS-2.1-NVFP4 + DFlash (2026-10-14)

New recipe [`poolside-laguna-xs-2.1-nvfp4-dflash-vllm.yaml`](../../recipes/explore/poolside-laguna-xs-2.1-nvfp4-dflash-vllm.yaml)
— the queued rank-1 Poolside arm (research doc §5): `poolside/Laguna-XS-2.1-NVFP4` (33B total / 3B
active, 256 routed experts, 3:1 SWA on a 40-layer stack, 262,144 native, OpenMDW-1.1, 21.6 GB
download) plus the first-party `poolside/Laguna-XS-2.1-DFlash` draft (0.92 GB) on **one node
(TP=1)**, on the same digest-pinned `vllm/vllm-openai:v0.29.0` as Kolibri-1. Both repos are pinned
(`d32afde8…` / `5c36361a…`).

- **Boot receipt**: task `sparkrun_a20dad9f9e2c72ca_8ed3ce77d78f` on `.34`; `GET /v1/models` →
  `poolside/Laguna-XS-2.1-NVFP4` (262144 ctx). TTR port-open **189.4 s** on the shipped boot
  (188–300 s across the four boots), weight load 131.5 s + draft 5.6 s.
- **Checklist closure (a)–(f), all PASS:**
  - **(a) import check** on the pinned image: `LagunaForCausalLM`,
    `laguna_dflash.DFlashLagunaForCausalLM` and both `poolside_v1` parsers (reasoning + tool)
    resolve; the serve log agrees (`Resolved architecture: LagunaForCausalLM`, then
    `…: DFlashLagunaForCausalLM`).
  - **(b) NVFP4 engages on SM121 — the INT4 23.9 GB fallback was not needed.**
    `Using FlashInferCutlassNvFp4LinearKernel for NVFP4 GEMM` and
    `Using 'FLASHINFER_CUTLASS' NvFp4 MoE backend`.
  - **(c) the draft rides in `defaults.speculative_config`** with its own `revision` in the same
    JSON, so sparkrun both distributes the 0.92 GB blob (serve log:
    `Distributing model poolside/Laguna-XS-2.1-DFlash`) and pins it. Note the vendor
    `generation_config.json` names the **`-DFlash-NVFP4` sibling** as the draft; that repo is a
    *different* 0.92 GB checkpoint (same byte size, different LFS sha256), and the one shipped here
    is the bf16 draft the queue names. The CLI `--speculative-config` overrides the checkpoint's own
    `num_speculative_tokens: 15` — proven, since the metrics show exactly 3 draft tokens per draft.
  - **(d) draft-depth sweep n ∈ {3,4,7}** on `decode-triage`, one boot each, **thinking on and the
    shipped serving line otherwise identical** (see the table below) → **n=3 ships**.
  - **(e) house battery 36/37** at `--max-tokens 4096` (19/19 easy + 17/18 hard). The lone miss is
    `hard-rev` (`'nurkarps'` for `nurkraps`). **The same battery with thinking off scores 31/37**
    (extra misses `wp-1`, `hard-arith-1`, `hard-rev`, `trick-3`, `code-js`, `code-big`).
  - **(f) KV pool at the shipped util 0.55: 41.56 GiB → 1,403,263 tokens** (`Maximum concurrency
    5.35x` at the native 262,144 window). 262k is pool-verified, **not retrieval-verified** (see the
    rope caveat below).

**Draft-depth sweep** (`decode-triage`, c=1, n=5; accept len = `spec_decode_num_accepted_tokens_total`
/ `num_drafts_total` + 1, rate = accepted / draft tokens, both off `/metrics` after the sweep):

| n | d0 c1 t/s | d8k c1 t/s | accept len | accept rate |
|---|---|---|---|---|
| **3 (shipped)** | **57.4** (σ 3.4) | **55.1** (σ 3.6) | 1.89 | 29.5% |
| 4 | 54.8 (σ 3.0) | 52.4 (σ 4.8) | 1.90 | 22.6% |
| 7 | 49.1 (σ 2.4) | 51.0 (σ 6.7) | 1.92 | 13.1% |

n=3 wins both depths and has the tightest spread; throughput falls monotonically with n while the
**acceptance length plateaus near 1.9** and the acceptance *rate* collapses (29.5 → 13.1%) — the
drafter's first position is right about two-thirds of the time, deeper positions almost never. Same
shape as the S-2.1 sibling (there, n=3 beat the vendor default n=15). An earlier pass ran the same
ladder with the template's thinking-off default and scored lower but ordered identically: 52.8/51.5
(n3), 53.5/49.0 (n4), 48.4/41.1 (n7).

- **Thinking is not on by default despite the card.** The checkpoint's `generation_config.json`
  declares `default_chat_template_kwargs: {enable_thinking: true}`, and vLLM does **not** apply it
  (verified: a default request returns `content` with no `reasoning`). The serve line therefore
  passes `--default-chat-template-kwargs '{"enable_thinking": true}'`. With it, `poolside_v1` splits
  reasoning cleanly (1806 chars of `reasoning` for a 17×23, `content: '391'`, `finish_reason: stop`)
  and the tool parser returns a well-formed `tool_calls` (`get_weather{"city": "Paris"}`,
  `finish_reason: tool_calls`). Per-request `enable_thinking: false` still turns it off.
- **Caveat — rope.** The boot warns `Laguna config has sliding_attention layers but neither
  swa_rope_parameters nor a nested per-layer-type rope_parameters — SWA layers will reuse the global
  rope`, alongside transformers' `Unrecognized keys in rope_parameters`. The shipped config *does*
  carry the nested per-layer-type form and `AutoConfig` parses it correctly offline, so the warning
  is unexplained; the 262k window is therefore **pool-verified only**. A needle probe is the open
  follow-up; no long-context retrieval was measured here.
- **Against the lane's two kept arms** (accuracy decides): 36/37 @ d0 **57.4 t/s**, 21.6 GB + 0.92 GB
  draft, 1 node — faster and smaller than both, but its lone miss is a genuine reversal, where
  Kolibri's is a thinking-budget artifact (37/37 union). So it sits **just below** Kolibri on the
  deciding factor, not tied with it: Ling 37/37 @ 45.5 (154 GB), Kolibri 36/37 @4096 @ 47.3 (74 GB),
  Laguna 36/37 @4096 @ 57.4 (22.5 GB).
- Receipts: `~/benchmarks/explore-laguna-20261014/` on the head — `laguna-shipped.{log,yaml,json,csv}`
  (shipped n=3 boot + battery + round-trips), `laguna-shipped-n{4,7}-decode-triage.*` (ladder),
  `laguna-n{3,4,7}-decode-triage.*` (thinking-off pass), `laguna-battery-4096.json`,
  `rt-shipped-default.json`, `toolcheck-shipped.json`.

### Poolside Laguna-S-2.1-NVFP4 + DFlash (2026-10-14)

New recipe [`poolside-laguna-s-2.1-nvfp4-dflash-vllm.yaml`](../../recipes/explore/poolside-laguna-s-2.1-nvfp4-dflash-vllm.yaml)
— the queued rank-2 Poolside arm (research doc §5): `poolside/Laguna-S-2.1-NVFP4` (117.6B total / 8.5B
active MoE, 256 experts, 3:1 SWA, native 1,048,576 context, OpenMDW-1.1) on ONE Spark (TP=1) with the
quantization-matched `poolside/Laguna-S-2.1-DFlash-NVFP4` draft (2.2 GB BF16). Same digest-pinned
`vllm/vllm-openai:v0.29.0` as Kolibri and the XS sibling. The pinned image was import-verified before
the boot: `LagunaForCausalLM` + `DFlashLagunaForCausalLM`, the `laguna` / `laguna_dflash` modules, the
`v1.spec_decode.dflash` proposer and the `poolside_v1` reasoning + tool parsers all resolve.

**The research template's 262k window does not fit one Spark — and the reason is the checkpoint, not
the flags.** The template (util 0.85, 262k, DFlash n=3, "1.37M-token KV") came from the fankserver
TP=1 sweep of **2026-07-22**, i.e. the *pre-August* checkpoint. Poolside's card says the August-2026
release "supersedes the earlier version … the weights have changed": the pinned revision loads to
**95.61 GiB resident** (`Model loading took 95.61 GiB memory`, `Checkpoint size: 92.85 GiB`), not the
~67 GiB the research doc carried — the `quantization_config` ignores attention, the dense layer-0 MLP,
both shared experts **and layers 40-47's experts**, so a large fraction of the 99.7 GB download is
BF16. At the repo's 0.85 budget on a 121.7 GiB node that leaves **4.6 GiB of fp8 KV**. vLLM refused
the 262k window outright (`9.32 GiB KV cache is needed, which is larger than the available KV cache
memory (4.58 GiB) … estimated maximum model length is 124144`) and the launch died in
`EngineCore failed to start` — a **documented negative for the 262k template**, reproduced on two
boots (a third failed boot also caught the recipe sync race: the first relaunch ran the head's stale
copy — always md5 the head's file before a boot).

**Shipped: util 0.85, `max_model_len: 122880` (120k), DFlash `num_speculative_tokens: 3`.**

- **Boot-verified on `.35`** (task `e57eaed458e6b584_64af2f7668b6`): TTR port-open **841.9 s**
  (HTTP-ready 842.0 s); weight load 645.6 s. `GET /v1/models` → `poolside/Laguna-S-2.1-NVFP4`
  (122880 ctx). Engine settled on `FLASHINFER` attention, the native **`FLASHINFER_CUTLASS` NvFp4 MoE
  backend** on `sm121` (the FP4 path engages — no INT4 fallback needed) and `DFlashLagunaForCausalLM`
  for the draft, whose CUDA graphs capture cleanly.
- **KV pool at the shipped util: `GPU KV cache size: 125,796 tokens`** (4.64 GiB available,
  "maximum concurrency for 122,880 tokens per request: 1.02×"). At `--kv-cache-memory` the engine
  itself reports 96.76 GiB for weights + non-torch, 2.04 GiB peak activation, 0.61 GiB CUDA graph.
  The pool is one full-window request and change — this is a **single-tenant 120k** arm, not a
  co-tenancy workhorse.
- **C1 `decode-triage` (same boot, `--skip-run`)**: **20.49 t/s @ d0 c1** (σ 0.93, n=5) and **20.11**
  at d8k c1 (σ 1.71). Prefill 2188 t/s @ d0, 442 t/s at d8k. Compared with the sweep's pre-August
  18.3 → 16.5 t/s this is at or above it, but that is a different checkpoint — quote ours.
- **DFlash is engaged, and the Draft acceptance is strong**: 43 metric windows across the sweep +
  battery read **mean acceptance length 2.52 (1.36–3.40)**, **mean Draft acceptance rate 50.8%
  (12.1–79.9%)**. Near the card's TP=2 `num_speculative_tokens=15` acceptance (4.0–6.4 on MT-Bench)
  at a quarter of the draft depth on one node.
- **House battery 32/37** (`tools/quality-battery.py --tier both --max-tokens 4096`, one boot):
  **18/19 easy + 14/18 hard**. Misses: `fmt-2` (easy, format), `hard-rev`, `hard-upper`, `code-py`,
  `neg-1`. Thinking is on by default (replies carry `reasoning`), which is why the raised budget is
  used. Below both kept arms (Ling 37/37, Kolibri 36/37 @4096 / 37/37 union) and its XS sibling
  (36/37) on the lane's deciding factor.
- **Draft license (recorded as required):** the *shipped* draft `poolside/Laguna-S-2.1-DFlash-NVFP4`
  declares **no license at all** — no `license` field in its card data and no LICENSE file; the BF16
  sibling `poolside/Laguna-S-2.1-DFlash` is `license: other` with **no license text in the repo**, so
  "other" resolves only by implication to the target's OpenMDW-1.1 (`base_model: poolside/Laguna-S-2.1`).
  The target checkpoint is OpenMDW-1.1 (commercial + non-commercial). Recorded here, where the recipe
  is distributed, rather than assumed settled.
- **Verdict**: boots and serves 120k at ~20.5 t/s C1 on one Spark with the FP4 path native and DFlash
  accepting ~2.5 tokens/step, but the August-2026 checkpoint is a ~96 GiB model — its 262k headline
  window needs ~0.89 util and is out of reach at the repo's 0.85 ceiling, so the arm is a **capped-context
  single-tenant** entry, below the two kept arms on accuracy.
- Receipts: `~/benchmarks/laguna-s-20261014/` on the head (`launch.log` + `launch-120k.log` — the 262k
  negative, `laguna-s-decode-triage.{yaml,json,csv}`, `laguna-s-battery-4096.{json,log}`,
  `laguna-s-serve-live.log` with the acceptance series). Node `.35` left clear (0 containers).

### Qwen-Image-2.1-Turbo — media-gen arm (2026-10-14)

New recipe [`qwen-image-2.1-turbo-7b-bf16-diffusers-script.yaml`](../../recipes/media/qwen-image-2.1-turbo-7b-bf16-diffusers-script.yaml)
+ [`recipes/media/mods/qwen-image-2.1-turbo-launcher`](../../recipes/media/mods/qwen-image-2.1-turbo-launcher) — the lane's
first **non-`sglang`/vLLM** engine: `Qwen/Qwen-Image-2.1-Turbo` (pinned `fc13ba1986`; **qwen-research,
NON-COMMERCIAL ONLY**) served by diffusers' `QwenImage21Pipeline` on **one** node. `runtime: vllm` is
the family whose distribution + single-node launcher contract the command satisfies (the Decision
lane's `vllm-srun` precedent); `command:` runs a stdlib HTTP server (`POST /generate`, `GET /health`)
out of a `diffusers>=0.41` / `transformers>=5.17` venv the mod stages on the image's own torch
(`vllm/vllm-openai:v0.30.0` digest pin; the venv's own `transformers>=5.17` meets the card's floor —
the image's copy is unused; see the *Engine bump* note below).
License banner + policy note ship **in the recipe** (owner call 2026-10-14; MiniMax-M3 / S-2.1
precedent): a recipe ships a repo id, not weights, and the downloader accepts the license —
commercial use is still barred.

- **Boot-verified on `.34`** (task `sparkrun_d87820463a694961_8ed3ce77d78f`): TTR port-open
  **206.1 s** (pipeline load 188.0 s; engine `diffusers 0.41.0 / transformers 5.19.0 / torch
  2.13.0+cu130`). `GET /v1/models` → `Qwen/Qwen-Image-2.1-Turbo`.
- **§6 acceptance**: 1024² at the checkpoint's shipped **8-step** schedule, CFG=1 — **11.33 / 11.41 s**
  steady (first request 12.30 s; the doc's derived `54.1 × 8/40 ≈ 10.8 s` holds, +5%). First-step
  latency 1.87 s cold / ~0.71 s warm; peak **36.85 GiB** alloc / 37.68 GiB reserved (node
  `MemAvailable` 76.9 GiB during a request). A reference image fed back for editing cost **+3.5 s**
  (14.8 s) — not the base model's 62.5 s. Same prompt+seed repeat wrote a **byte-identical PNG**
  (1,116,690 B); all four images are 1024×1024 RGBA with no degenerate output. The eye-vs-vendor-gallery
  verdict is the owner's (PNGs under `samples/`); the recorded check is objective non-degeneracy.
- Two bring-up defects were found and fixed in the mod: the container's **non-root** user
  (`1000:1000`) broke `reown()` (now chowns only as root), and a heredoc piped into `log()` killed the
  pre-exec hook with **`rc=120`** after a successful install. Both patterns are fixed in
  `mods/mod-template/run.sh` too.
- **Verdict**: boots and serves text-to-image + editing on one GB10 at ~11.4 s per 1024²/8-step image
  and ~36.9 GiB peak — off the lane's reasoning/tool brief **and license-blocked for commerce**, so it
  competes with nothing in the selection and ships as the banner-marked **eval-only** entry.
- Receipts: `~/benchmarks/qwen-image-20261014/` on the head (`launch2.log`, `serve-tail.log`,
  `modlogs/`, `samples/`, `results.json`, `edit.json`, `measure.py`, `analyze.py`). Details:
  [`QWEN-IMAGE.md`](QWEN-IMAGE.md).

### LTX-2.5 — media-gen runbook (2026-10-14)

`Lightricks/LTX-2.5` (video+audio world model, 22B distilled DiT + Gemma-4-12B encoder) as a
**two-stage ComfyUI** run on one GB10 — shipped as a **runbook, not a recipe**
([`ltx-2.5-runbook/`](../../recipes/media/ltx-2.5-runbook/README.md)): the runtime is ComfyUI (no `sglang`/vLLM engine)
and the repo is `gated: auto`, so a per-node `HF_TOKEN` + accepted terms is a prerequisite sparkrun
cannot assume (owner decision 2026-10-14: ship gated arms with the documented prerequisite). The
cluster token (`twichert`) **has acceptance** (README resolve → HTTP 200), so the arm was measured
rather than blocked.

- **Booted on `.35`**, unit pinned as a whole: ComfyUI **v0.34.0** + comfy-kitchen 0.2.31 +
  frontend 1.49.6 + workflow-templates 0.11.48 + embedded-docs 0.5.10 (below 0.34 the refine
  silently emits garbage); torch 2.14.1+cu130; clock capped at **2200 MHz** (§6(e) sustained-load
  power-loss fix — all timings taken under the cap).
- Weights ≈ **36.9 GB**: nvfp4 distilled transformer 18.72 + video VAE bf16 1.47 + audio VAE bf16
  0.36 + x2 latent spatial upscaler 1.00 + Gemma-4-12B comfy int8 encoder 15.37. The `-nogemma`
  variant is H3-hybrid-graph-specific and is **not** used — the native T2V template needs the Gemma
  encoder. NVFP4 engages natively on `sm121` via comfy-kitchen.
- **Two-stage run** (seed 42): stage 1 distilled **8-step @ 672×384** → `LTXVLatentUpsampler` ×2 →
  **3-step refine @ 1344×768, 121 frames @ 24 fps** with audio muxed. **Cold wall 100.3 / 90.1 s**
  (two reps), **warm 80.1 s**; stage split 14.0 load / 16.7 stage 1 / 2.5 upscale / 20.8 refine /
  46.2 decode+mux; **peak 83.6 GiB** (0.69 util). Frames must satisfy `frames % 8 == 1` — the doc's
  "124 frames" is the MiniMax-H3 draft's count; LTX outputs **121**.
- **Output verified**: `ffprobe` → h264 1344×768 24 fps 121 frames + AAC (5.042 s, mean −43.6 dB /
  max −25.7 dB, non-silent), plus a decoded frame at t=2.5 s (mean 0.185, std 0.124 — not black,
  not noise).
- Traps paid for: `hf download --include` silently drops patterns (pass explicit filenames); missing
  `python3.12-dev` fails triton at the first kernel launch; subgraph workflow templates need
  frontend-side expansion (`expand_subgraph.py` flattens them for `/prompt`); dropping `SaveVideo`
  makes the graph "succeed" in 0.01 s having generated nothing.
- Receipts: `~/benchmarks/ltx25-20261014/` on the head (four MP4s, server log, `mem.tsv`, decoded
  frame, API prompt, `RESULTS.md` naming every command). Details: [`LTX-25.md`](LTX-25.md).

### LTX-2.5 — the three unrun cells + the expander defects (2026-10-18)

Filled the 2026-10-14 runbook's open cells on `.34` (clock cap 2200 MHz, seeds 42 then 44 — a
same-seed rerun is fully cached at 0.01 s, so the second seed is the first non-cached rep). Receipt
`~/benchmarks/ltx25-20261018/` (`REPORT.md`, 7 frames, 7 mp4s, per-rep `api/err/out`,
`receipts{,_warm}/{server.log,mem.tsv}`, and the fixed runner scripts `expand2.py` / `run_cell2.py`).

- **T2V warm 78.1 s / 83.70 GiB** — **−2.5 %** on the recorded 80.1 s (same cell, same cap). Stage
  split 11.6 s @ 1.45 s/it → 20.9 s @ 6.94 s/it → 43.5 s decode+mux.
- **I2V 84.3 s (+7.9 %) / 83.79 GiB**; frame 0 vs the start image MAD **4.1**, so the guide is applied.
- **FLF2V 120.2 s (+54 %) / 81.94 GiB**, and slower **by design**: that template has no
  `LTXVLatentUpsampler`, so the guides ride one full-res 8-step pass (76.9 s @ 9.6 s/it at 1344×768)
  instead of half-res 8-step + 3-step refine. Guides verified by MAD: frame 0 7.8 vs start / 59.5 vs
  end; frame 120 16.9 vs end / 59.1 vs start.
- **4K/50 (3840×2160, 249 f) is OOM — measured.** Stage 1 completed (8/8, 461.3 s @ 57.7 s/it), the
  process died at the ×2 latent upscale with 590 `NV_ERR_NO_MEMORY` kernel lines, unified pool peak
  **121.16 of 121 GiB**, no output. Not co-tenancy: weights-only baseline 78.4 GiB, 85.0 GiB steady in
  stage 1, `free` showed 4 GiB used just after. The node stayed up — a process kill, not a node loss.
  **Do not re-run this preset expecting a different result**; a smaller 4K cell is a different
  question.
- **Cold rep 204.3 s is an upper bound**, not a clean cold number: it overlapped a peer's sglang serve
  on `.34`. It decodes to the same frame hash as the resident-model seed-42 rep.

**The runbook's `expand_subgraph.py` is T2V-only.** Four defects had to be fixed before I2V/FLF2V
would validate — the fixed scripts are `expand2.py` / `run_cell2.py` in the receipt (the repo copy is
untouched):

1. **Subgraph widget alignment.** `widgets_values` on the subgraph instance consumes a value only for
   *widget-typed* slots; IMAGE/LATENT slots are links. The runbook's `iws[idx]` over all slots is
   silently right on T2V (every slot is a widget) and shifts every model path by one on I2V/FLF2V —
   the VAE name lands in the UNET loader.
2. **`ResizeImageMaskNode` dynamic combo.** `resize_type` spawns per-option sub-inputs
   (`resize_type.width/height/crop`); headless expansion turns those into garbage (`resize_type:
   1536`, `scale_method: 360`) and the node raises `missing 1 required positional argument:
   'resize_type'`. Pin `scale dimensions` at the cell size, `crop: center`, `scale_method: lanczos`.
3. **The prompt-enhancer branch is gated by `ComfySwitchNode.switch` → `PrimitiveBoolean`**, not a
   `value` input. Alias `on_true = on_false` and garbage-collect everything unreachable from
   `SaveVideo`, or validation fails on `gemma4_e2b_it_int8_convrot` (not downloaded) and on
   `TextGenerateLTX2Prompt.sampling_mode.*` (nested widget groups do not survive expansion).
4. **Sizing trap (cost two 410 s runs).** The latent width/height are `ComfyMathExpression "a/2"` over
   the width/height primitives. A literal on `EmptyLTXVLatentVideo` bypasses the halving: stage 1 runs
   at full res and stage 2 at 2688×1536. Set the primitive behind the `/2`; the mis-sized frames in
   `~/ComfyUI/output/bad_oversize/` are **not** measurements.

### Mellum2.1-12B-A2.5B-Thinking — boot-verified 2026-10-15

- **Owner-added, outside the ranking**: the `JetBrains/mellum21` collection was added to this lane
  directly (2026-10-15), so this arm has no §1 shortlist row and no selection record. Recipe:
  [`mellum2.1-12b-a2.5b-bf16-thinking-vllm.yaml`](../../recipes/explore/mellum2.1-12b-a2.5b-bf16-thinking-vllm.yaml).
- Pin `92ddae9fc7665e9f801d141d2e5a6b2caf2460c4` (`main`, 2026-10-07; ungated, Apache-2.0); 12B/2.5B-active
  MoE, 131,072 ctx, 24.3 GB bf16, TP=1, `gpu_memory_utilization: 0.55` (headroom choice — since measured: the arm scales cleanly to c10).
- **No mod needed**: vLLM 0.29 ships `MellumForCausalLM` (a Qwen3-MoE subclass with per-layer sliding
  window and per-layer `rope_parameters`) — this checkpoint's exact config shape. Thinking is ON by
  default; the card's parsers are `qwen3` + `hermes`.
- **The GGUF/llama.cpp route is recorded, not shipped** (no llama.cpp arm exists in this registry to copy).
- **Measured 2026-10-15** (one boot on `.35`, receipt `~/benchmarks/mellum-20261015/`): decode ladder
  @ d0 pp2048 tg128 n=5 → C1 42.3 / C2 67.2 / C5 99.9 / C10 135.6 t/s; house battery 36/37 (easy
  18/19 — the one miss is `needle-1`; hard 18/18); contract ok; index row present. Open in the
  receipt: the engine's KV-grant line (serve-log capture gap), the tool round trip, long-context
  correctness beyond the short `needle-1` probe, and the BFCL datapoint — the per-arm record's §6.
- Details, provenance and what the boot answered: [`MELLUM-21.md`](MELLUM-21.md).

### Muse-Glimmer-30B NVFP4 + DFlash — boot-verified 2026-10-21, **NOT selected**

- **The route works, and that is the result worth keeping.** `RadixArk/Muse-Glimmer-NVFP4` @
  `1416629950` (18.3 GiB, mixed NVFP4/MXFP8 modelopt) plus `meta-models/Muse-Glimmer-30B-assistant` @
  `c676cce9` (4.8 GiB DFlash drafter) serves on **one** Spark under the ornith lane's own
  `lmsysorg/sglang:v0.5.21` digest — no fork, no newer build, no new image. SGLang has the model, the
  `muse` reasoning and tool-call parsers, and the DFlash assistant path at that tag.
- **Contract PASS, including the tool call the model exists for**: the channel-scoped
  `to=functions.x<|message|>` framing converts through `--tool-call-parser muse` into
  `finish=tool_calls` with `get_weather({"location": "Paris", "unit": "celsius"})` — arguments
  populated, not empty. Greedy `27*43` → `1161`. This is the first arm in the lane whose native
  channel format needed no shim.
- **Engine facts.** `Use marlin as FP4 GEMM runner backend on SM120 for Muse Glimmer` fires on GB10
  (sm_121 satisfies `is_sm120`; the FlashInfer autotune path confirms `/sm121/`). DFLASH engages at
  block size 5 (`num_tokens_per_req=5` verify graphs), with `DFLASH draft greedy head kept eager
  (reason=quantized lm_head)`. `enable_multimodal: None` leaves it text-only, as the pack requires.
- **Boot cost.** Cold launch 318 s (316 s of it the 23.1 GiB distribution), `/v1/models` at 350 s;
  warm re-boot 35 s. KV pool **235,556 tokens** bf16 at `--mem-fraction-static 0.38` (the vendor's
  GB10-with-DFlash value), `max_running_requests=48` — **1.80x** the 131,072 window, so one
  full-window request and not two.
- **Quality: house 36/37** (easy 19/19, hard 17/18). The miss is `hard-rev`: "sparkrun" backwards
  comes out **`nurkrpas`**, four of four runs at temperature 0, every one `finish=stop` with no
  truncation — a genuine two-letter transposition, not a budget artifact. Other reversals are fine
  (`abcdef` → `fedcba`, `hello` → `olleh`).
- **Needle 10/10 at 32,768 and 10/10 at 131,072** (`--max-tokens 512`; the suite spells it
  `--needle-max-tokens`), 60–67 s per request at 32k and 237–242 s at 131k.
- **Ladder (d0, pp2048, tg128, n=5): C1 20.2 / C2 34.0 / C5 87.9 / C10 156.9 t/s**, prefill
  909.8 / 690.0 / 648.0 / 637.2 t/s, ttfr 2.25 / 5.80 / 15.63 / 30.03 s. Acceptance from the serve
  log: C1 mean **3.19** (max 4.60, rate 0.55), 2.57–2.94 above it. DFLASH is doing its job; the
  ceiling is single-stream decode.
- **Why it does not ship.** 37/37 is a tie-break here, not a gate — Kolibri-1 was kept at 36/37 as a
  37/37 union, and Laguna-XS was kept at 36/37 with a genuine reversal for its c10 slot. Muse Glimmer
  loses that tie-break from the wrong side: 36/37 genuine, like Laguna-XS, but at **20.2 t/s C1
  against 57.4** — the slowest single-node arm measured in this lane — and its 156.9 at c10 rides a
  48-request grant against Laguna-XS's 8, so it is not a like-for-like win. No BFCL number exists for
  it, and none is quoted.
- **Do not re-boot blind.** The recipe was removed rather than archived (its only novel content is
  the pin set and the flag line, both recorded here). The revisit it named — the **bf16 export** —
  has since run: it reproduces the `nurkrpas` slip verbatim, so the miss is the **checkpoint**, the
  pack is exonerated, and no repack is worth trying. See the next subsection.
- Receipt `~/benchmarks/explore-muse-glimmer-20261021/` (`REPORT.md`, `contract.{py,json}`,
  `house.json`, `needle-32k.json`, `needle-131k.json`, `ladder.{yaml,json,csv}`, two serve logs;
  ladder `bench_441193bb138b`).

### Muse-Glimmer-30B bf16 control — 2026-10-21, **the checkpoint is at fault**

- **The control.** `meta-models/Muse-Glimmer-30B` @ `7af58019` (open, 59.58 GB, 2 shards) plus the
  same drafter (`…-assistant` @ `c676cce9`), the same `lmsysorg/sglang:v0.5.21` digest and the same
  flag line as the NVFP4 arm, on `.35`. One deviation: `mem_fraction_static` 0.80 instead of 0.38,
  because 59.6 GB of bf16 weights cannot fit inside 0.38 of ~121 GiB.
- **Result: house 36/37, the miss is the same item and the same string** — `hard-rev` ->
  **`nurkrpas`**, easy 19/19, hard 17/18. Every other reversal passes. Both exports of the same
  weights therefore fail the same word deterministically, which makes the **checkpoint** the cause
  and the NVFP4 pack innocent; the Muse Glimmer line closes and no repack is worth trying.
- **The load was proven, not assumed:** `Load weight end. elapsed=340.21 s,
  type=MuseGlimmerForConditionalGeneration, avail mem=60.20 GB, mem usage=52.21 GB` from
  `model_path=…/models--meta-models--Muse-Glimmer-30B/snapshots/7af58019…`; engine runtime read
  from the container is the same trio the NVFP4 arm ran (`sglang 0.5.21 | torch 2.13.0+cu130 |
  cuda 13.0`), so the engine is not a confound.
- **Trap for later readers:** `Use marlin as FP4 GEMM runner backend on SM120 for Muse Glimmer` still
  prints on the bf16 load. It is an engine branch keyed on the model name; there are no FP4 tensors
  in this checkpoint. Do not read that line as evidence of a quantized boot — the `mem usage` figure
  and the `model_path` are the evidence.
- **DFLASH works on bf16** — the same `draft config block_size=16` mismatch warning, then the draft
  runner at block size 5 with the greedy head folded into the draft CUDA graph (no
  `reason=quantized lm_head` eager note), acceptance 2.27-4.47 through the C1 window.
- **C1 12.1 t/s** (prefill 1206.7 t/s, ttfr 1,700 ms, n=5, d0 pp2048 tg128) against the pack's 20.2:
  bf16 costs 8.1 t/s of single-stream decode, which is the bandwidth of 52 GB of weights, not a
  drafter failure. Boot 16.5 min (8.4 min of it the weight load at ~134 MB/s). KV: 513,943 full +
  411,154 SWA tokens bf16, `max_running_requests=48`.
- Recipe kept only in the receipt (`recipe.yaml`, git-ignored `.scratch` copy removed); receipt
  `~/benchmarks/explore-muse-glitter-bf16-20261021/` (`REPORT.md`, `serve.log`, `house.{json,log}`,
  `ladder.{yaml,json,csv}`, `download.log`), ladder `bench_d2ac5cf9ade0`.

## Engine bump — vLLM 0.30.0 (2026-10-16)

The 2026-10-15 advisory pass opened this: move the lane's six `vllm/vllm-openai:v0.29.0` arms to
`v0.30.0@sha256:8a69ffad…` (**0** OSV records, vs 23 at 0.29.0). Pin commit `0c41f18` moved five of the six (Kolibri held on its plugin); three pins
went back on `2a8243f` after the device-free preflight below.

**Preflight before booting (worth repeating on every engine bump):** run the new image's own config
loader against every pinned arm, on a node, with the **HF repo dir** mounted — never a
`snapshots/<sha>` dir, whose entries are `../../blobs` symlinks that dangle outside the repo dir:

    docker run --rm -i -v <hf-cache>/models--<org>--<name>:/repo:ro --entrypoint python3 <new-image> - <<'PY'
    from vllm.transformers_utils.config import get_config
    print(get_config('<repo>', False, revision='<pin>'))
    PY

Three of the five moved arms cannot load their config on 0.30.0 — both failures are in vLLM's own
config path, not the shipped transformers 5.17.0:

- **mellum2.1-12b** — vLLM 0.30.0 ships its own `MellumConfig`
  (`vllm/transformers_utils/configs/mellum.py`, a `Qwen3MoeConfig` subclass) and registers it for
  model_type `mellum` ahead of transformers' upstream class. The stub takes the generic
  `convert_rope_params_to_dict` path, which `setdefault`s a flat `rope_theta` / `rope_type` beside
  this checkpoint's nested per-layer `rope_parameters`; `patch_rope_parameters` then calls
  `validate_rope`, which iterates the dict's values and dies on the float
  (`AttributeError: 'float' object has no attribute 'get'`, `config.py:580` →
  `modeling_rope_utils.py:850`). Reproduced device-free and live (the first boot on `.35` died in
  the same frame, before any weight load). **Unblock probed:**
  `hf_overrides_kw={'rope_parameters': <the checkpoint's own dict>}` loads clean — a recipe could
  carry the values (duplicating the checkpoint's rope config) if the arm must move before upstream
  fixes the stub.
- **poolside-laguna-{s,xs}-2.1** — both pins fail in vLLM 0.30.0's *own* config path:
  `get_config(<repo>, False, revision=<pin>)` raises `AttributeError: 'str' object has no attribute
  'get'` (identical with `trust_remote_code` True — `preflight-configs{,2}.py` in the receipt). The
  actor is not transformers: probed 2026-10-17, `AutoConfig.from_pretrained` on the same snapshot
  builds `transformers.models.laguna.configuration_laguna.LagunaConfig` and
  `standardize_rope_params()` keeps the nested per-layer `rope_parameters` intact, while vLLM
  0.30.0 registers its own `LagunaConfig` (`vllm.transformers_utils.configs`) — the same shadowing
  family as the mellum bullet above. Unblock: a vLLM-side fix or a stub-compatible re-pin — a lane
  decision, since the arms' measured numbers belong to the old pin. Receipt:
  `~/benchmarks/bump-20261016/laguna-config-probe.txt`.

**Boot-verified on 0.30.0:** `humanizer-12b-vllm` — task `sparkrun_17678da2f7107eb2_a4bf874feb5a`
on `.35`: engine `vllm 0.30.0`, container `.Image` == the manifest list's arm64 config digest
(`91d9b077…`), TTR port-open 252.4 s, `GET /v1/models` → `jialinyyzz/humanizer` (8192 ctx), a
`/v1/completions` rewrite smoke with every number preserved (`system_fingerprint:
vllm-0.30.0-372a78a5`), KV **371,031 tokens / 45.29× at 8192** (0.29.0: 370,597 / 45.2×). Receipts:
`~/benchmarks/bump-20261016/`.

**Bumped, verification deferred to its own boot:** `qwen-image-2.1-turbo-…-diffusers-script` — the
mod's venv supplies its own `transformers>=5.17`, so the image's engine version does not gate it.

**Holds unchanged:** `kolibri-1-78b-fp8-vllm` (the vendor plugin pins vLLM 0.29).

## Engine bump — upstream llama.cpp (2026-10-22)

Every llama.cpp arm in the tree runs a third-party or fork build, and the publisher of the one
`scitrera` pin has stopped: Docker Hub's newest tag for `scitrera/dgx-spark-llama-cpp` is still
`b10549-cu131` — and `:latest` points at it, uploaded 2026-08-21, i.e. llama.cpp `b2e5e9b` (2026-08-21).
Upstream has since absorbed what the forks existed for. Feature by feature, read in source at the named
commit (not from release notes):

| need | who carried it | upstream now | landed |
|---|---|---|---|
| Mellum2.1 MTP (`nextn_flags`, `graph_mtp`, `-md` / `--spec-type draft-mtp`) | nobody — absent at `b2e5e9b` | **native**, `src/models/mellum.cpp` | `9a16f1dbe` 2026-10-16 (#30612) |
| Kolibri-1 (`kolibri1`) | `brywil/llama.cpp` @ `68fa28b` | **native**, `src/models/kolibri1.cpp` | `62318cd57` 2026-10-17 (#30673), then `9df0b73c7` 2026-10-20 (#30865) |
| Decision-2 | `Xunzhuo/llama.cpp` @ `c9f597487` | **fork-only in practice** — upstream's arch is `vllm-decision2` (`097cf33d9`, 2026-10-12, #30378) with its own converter; the shipped pack is a different contract (below) | — |
| CUDA 13 / sm_121 | the fork images' own flags | **native**, `121a-real` in `ggml/src/ggml-cuda/CMakeLists.txt` | present by `v0.7.0` |

No release tag carries all of it: the newest, `v0.7.0` (`620d2225cc`, 2026-10-15), predates Mellum MTP
and Kolibri-1 (verified: its `src/models/kolibri1.cpp` and its `mellum.cpp`'s `graph_mtp` are both
absent). The minimal feature-complete ref verified 2026-10-22 is
**`9df0b73c707900b7277a46b5ae52ff7e7e567d13`** (2026-10-20T12:58Z): `mellum.cpp` carries
`nextn_flags` / `graph_mtp` / `LLM_GRAPH_TYPE_DECODER_MTP`, `kolibri1.cpp` and `vllm-decision2.cpp` are
present, and the CUDA 121 entry is in the tree. Anything later also works — which is why the build
takes a required `--build-arg`, not a tag.

**Two pack-level facts decide what may move** (read from the packs' own GGUF headers, not assumed):
`Kolibri-1-APEX-2.4bpw.gguf` declares `general.architecture = kolibri1` *and*
`tokenizer.ggml.pre = qwen2`, so the fork's "accept `kolibri1` as a Qwen2 pre-tokenizer alias" patch is
not needed for the shipped packs (upstream has no such alias, and does not need one here). The decision
pack `Decision-2.0-Sol-2B-Q8_0.gguf` declares `general.architecture = qwen35` with **330** tensors — ten
more than upstream's qwen35 loader expects (320) — so upstream's `vllm-decision2` cannot substitute for
Xunzhuo's patched qwen35 loader; that arm stays on
`littlecedar/dgx-spark-llama-cpp-decision2:c9f5974`.

**What a stock-upstream image unlocks, one line per arm:**
- `mellum2.1-12b-a2.5b-q4km-thinking-llamacpp` (+ its `mmap` probe) — **stock image works, MTP rejected
  on it (2026-10-22)**: same-node A/B on `.30` gives `a37cc4610` **100.3 / 98.7 t/s** against the
  `scitrera` pin's **114.1 / 116.2**, and MTP on `a37cc4610` adds only **108.4 / 109.9** — short of the
  pre-registered 114 t/s bar, so the arm keeps no speculative decoding (acceptance 0.80, mean len 1.80 of
  a possible 2.0). The 8.4 t/s seen on the `9df0b73c7` build reproduces from a clean context, so it is a
  window in that tree, not a bad artifact; the earlier `+44 %` MTP figure was that slow baseline's
  artefact and must not be quoted. The ~15 % the stock image gives up is the **upstream ref era**, not the
  fork's build: the fork's own tree (`b2e5e9b`) built through our Dockerfile and flags measures 114.2 /
  113.9 on that node — so the pin stays for this arm's speed, and nothing about the fork needs adopting.
- `kolibri-1-apex-24bpw-llamacpp` (and the Q4_K sibling) — loadable on stock upstream; the fork image
  can retire after one boot proves it, and stays the fallback until then.
- `sol-2b-decision2-gguf-llamacpp` — **not** unlocked: different arch string and tensor contract, so
  the Xunzhuo fork image remains the only engine for that pack.

**Build — pre-registered; built 2026-10-22 (six builds, receipts below).** `recipes/explore/Dockerfile.llamacpp-upstream`
is arm64-only, `121a-real`, with `LLAMA_REF` **required** and no default, and fails closed on: a
non-arm64 host, a missing ref, a ref whose `git rev-parse HEAD` differs, a tree without the three model
sources or without `nextn_flags`/`graph_mtp` in `mellum.cpp`, a fatbin without `sm_121`, and a binary
without the three arch names. Build on the first node with `docker ps -aq` = 0 and **never** beside a
foreign container (`.30` only while the quartet is between boots); sibling builds took 184 s cold
(including the base pull) and 134 s for a rebuild, so expect ~200–250 s. Push to a NEW tag — never move
`scitrera`'s tag or either fork image:

    docker build -f recipes/explore/Dockerfile.llamacpp-upstream \
      --build-arg LLAMA_REF=9df0b73c707900b7277a46b5ae52ff7e7e567d13 \
      -t littlecedar/dgx-spark-llama-cpp:upstream-9df0b73-cu130 .
    docker push littlecedar/dgx-spark-llama-cpp:upstream-9df0b73-cu130
    docker inspect --format '{{index .RepoDigests 0}}' \
      littlecedar/dgx-spark-llama-cpp:upstream-9df0b73-cu130

**Mellum MTP A/B — pre-registered with its falsifier (ran 2026-10-22: FALSIFIER FIRED, see the measured
section; kept as written so the bar is on record).** The recipe
bytes stay as shipped except `container:` and the draft staging: sparkrun stages one repository per
recipe, and the head is a second file in the same repo
(`mtp-Mellum2.1-12B-A2.5B-Thinking-BF16.gguf`, 1.77 GB, `-md` → that path, plus
`--spec-type draft-mtp --spec-draft-n-max 1`), so it needs a mod or a second distribution step before
the serve line can name it — that staging, not the engine, is the work.

- Cell: **C1 @ d0 pp2048 tg128 n=5**, the baseline's own method and receipt shape.
- Baseline: **111.9 ± 0.3 t/s** (`~/benchmarks/mellum-gguf-20261017/`), with C2 151.1 / C5 208.0 /
  C10 146.4 and house 37/37, bfcl 88.3 %.
- Falsifier (pre-registered): C1 does **not** clear **114 t/s** (the baseline mean plus ~7× the
  ±0.3 sample spread) with `accepted / drafted` recorded per request, **or** any C2/C5 regression, **or**
  house drops off 37/37 / bfcl off 88.3 %. An accept rate of 0 is the expected failure mode if the
  Q4_K_M main's hidden states do not suit the BF16-trained head — quote accept-len, not just t/s.


### Measured on `.34`, 2026-10-22 — the `9df0b73c7` tree decodes 12× slower; `a37cc4610` is healthy

The build passed both gates (154.93 s; `features: … present`, `gate: sm_121 + kolibri1 + vllm-decision2 +
mellum present`) and pushed as `littlecedar/dgx-spark-llama-cpp:upstream-9df0b73-cu130`
(`sha256:31181fd3…`; a plain-`121` probe build `…-cu130-121` came out at `sha256:21a1b75e…`). One request
each, same node, same GGUF pin, same serve flags:

| boot | engine | decode t/s |
|---|---|---|
| old (control) | `scitrera` `b10549-cu131`, llama.cpp `b2e5e9b` (2026-08-21) | **120.0 / 122.1** |
| new, `--load-mode none` | this build | **8.4** |
| new, `--load-mode mmap` | this build | 8.6 |
| new, arch `121` | second build | 8.7 / 8.3 |

Not a launch defect, not a flag: the log shows `using device CUDA0`, `offloaded 29/29 layers to GPU`,
`CUDA0 model buffer size = 7572.50 MiB`; decode runs the GPU at ~46 % with the process at ~470 % CPU.
Two recipe-level facts this arm will need if the image is ever adopted: `executor_config: {entrypoint: ""}`
(the image keeps `llama-server` as ENTRYPOINT) and `--no-mmap` → `--load-mode none` (upstream removed the
old spelling).

**The MTP A/B ran on the healthy ref and the falsifier fires: MTP is not worth its place on this arm.**
Same node (`.31`), same GGUF pin, same serve flags, two 128-token greedy requests per side:

| side | decode t/s | draft acceptance |
|---|---|---|
| base, `a37cc4610` (`ef2d4bc8`) | **101.5 / 102.1** | — |
| `-md …BF16.gguf --spec-type draft-mtp --spec-draft-n-max 1` | **108.4 / 109.9** | 0.800 (56/70) and 0.789 (56/71), mean len 1.80 / 1.79 |

**+7.4 %**, against a pre-registered bar of C1 > 114 t/s (baseline 111.9 ± 0.3). Acceptance is near the
ceiling for `n-max 1` (mean len 1.80 of a possible 2.0) and it still buys only 7 %: the verify pass of a
2.5B-active MoE costs about what the saved decode step yields. On the crippled `9df0b73c7` build the same
head looked like +44 % (12.5 vs 8.4 t/s) — that number was an artefact of the slow baseline and must not
be quoted. Conclusion: no MTP in the arm, no recipe change.

The earlier paragraph on this head stands as mechanics (head lives at its own revision `4159d684…`, not
at the model pin `20b43942…`; main GGUF byte-identical at both), not as a speed claim.
Receipt: `~/benchmarks/mellum-mtp-20261022/` on the head (reachable from `.31`/`.33`) — `REPORT.md`, `build.log`, `build121.log`,
`probe.log`, `push*.log`, `control-ladder.{json,csv}`, `oldengine-boot.log`, `new-mmap-boot.log`,
`arch121-boot.log`, `mtp-boot.log`, `head-download.log`, `build-fa.log`, `flint-probe-boot.log`,
`fa-boot-33.log`, and the five variant recipes.
### The draft-length sweep — the rejection holds as a curve, and it was never the shipped engine (2026-10-22, same day)

The 03:18 verdict measured **one** draft length (`--spec-draft-n-max 1`), so it could not tell "that
setting is wrong" from "MTP is wrong". Re-tested as a curve on `.32` — same image digest (`ef2d4bc8…`),
same GGUF pin, same head bytes, same `--ctx-size 131072 --parallel 8 --kv-unified --load-mode none`
flags, three 128-token greedy requests per cell, one boot per cell, and the no-MTP baseline taken in the
**same window** before and after the sweep. Receipt: `~/benchmarks/mellum-mtp-draft-20261022/`
(`PRE-REGISTRATION.md` was written before the first boot; `cell.sh` + `summarize.py` regenerate
everything).

| `--spec-draft-n-max` | decode t/s (mean ± σ, 3 runs) | vs its own baseline | acceptance | mean accepted len | TTFT |
|--:|---|--:|--:|--:|--:|
| 0 (no MTP, open) | **102.03 ± 0.35** | — | — | — | 65 ms |
| 1 | **103.38 ± 2.83** | **+1.9 %** | 0.701 | 1.70 | 118 ms |
| 2 | 90.02 ± 9.00 | −11.3 % | 0.477 | 1.95 | 125 ms |
| 3 | 75.94 ± 9.00 | −25.2 % | 0.355 | 2.06 | 127 ms |
| 4 | 66.60 ± 10.66 | −34.4 % | 0.287 | 2.14 | 124 ms |
| 6 | 51.38 ± 8.70 | −49.4 % | 0.196 | 2.15 | 115 ms |
| 8 | 47.73 ± 5.07 | −53.0 % | 0.164 | 2.28 | 111 ms |
| 0 (no MTP, close) | **100.97 ± 0.57** | — | — | — | 62 ms |

Baseline pooled over both control cells: **101.50 ± 0.74 t/s**. The curve is **monotone decreasing from
`n=1`**, with no interior peak; `n=1` is the only cell that is not clearly worse than plain decoding and
its own range (100.38–106.00) brackets the baseline's (100.35–102.40). Every draft length ≥ 2 is slower
per prompt, all three prompts, every cell. Mean accepted length saturates at 2.0–2.3 while the drafted
count rises 8× (at `n=8`: 385 drafted, 77 accepted), so the 2.5B-active MoE pays a 9-token verify pass
for ~2.3 tokens of output — the same conclusion the vendor's card reached on Metal ("two or more drafted
tokens were slower than plain decoding in every configuration").

**Two corrections to how the rejection was recorded.** (1) `mad-science/STATUS.md` attributed
108.4/109.9 to "the shipped engine"; they came from the stock-upstream `a37cc4610` build (image
`littlecedar/dgx-spark-llama-cpp@sha256:ef2d4bc8…`). The shipped `scitrera b10549-cu131` pin is
`b2e5e9b`, whose `src/models/mellum.cpp` has no `nextn`/`graph_mtp` — it cannot load this head at all.
(2) The 114 bar is that pin's **111.9 ± 0.3**, a different ref that decodes the same GGUF ~10 % faster,
so the original was a cross-ref comparison. Scored against its own ref instead, MTP at the vendor's
setting is **+1.9 %, i.e. inside the noise**, and raising the draft length only loses throughput. The
rejection therefore stands — as a rejection of MTP on this model, peak **103.4 t/s < 114 bar**, measured
across draft lengths 1–8 — and no longer as a single-point verdict.

Probe arm kept as the reproducer: `recipes/explore/zz-mellum2.1-12b-a2.5b-q4km-thinking-llamacpp-mtp.yaml`
(`zz-` = not shippable; `-o spec_draft_n_max=<n>` selects the cell). The head is not distributed by
sparkrun (one repository per recipe) — stage it on the node at
`/cache/huggingface/hub/mellum-mtp-head/mtp-Mellum2.1-12B-A2.5B-Thinking-BF16.gguf`, sha256 `9c7b2c37…`.


### The ref floor moved to `a37cc4610`, and why (same day)

`src/models/flint.cpp` landed in **`a37cc46104eb50900d5ab4a9ba02a0abdac039db`** (2026-10-21T21:26Z,
#30928, 18 files incl. `conversion/flint.py`; arch string `flint`) — after `9df0b73c7`, so the first
build cannot serve a Flint pack. The eight commits after it are sycl / webgpu / opencl kernels, a dflash
optional FC-input scale, lora prism weights, two UI items and a jinja namespace fix: none adds a model
this lane would serve and none touches CUDA decode. **`a37cc4610` is therefore the earliest ref carrying
Mellum MTP + `kolibri1` + `vllm-decision2` + `flint` + `121a-real`, and the one the Dockerfile's gates
now require** (the source gate demands `src/models/flint.cpp`, so an older ref fails on purpose).

| build | ref | tag | digest | wall |
|---|---|---|---|---|
| Mellum-MTP image | `9df0b73c7` | `littlecedar/dgx-spark-llama-cpp:upstream-9df0b73-cu130` | `sha256:31181fd3105001f503136ff6a4cbbf5ac7d3ab53fd0c5d88a723a844826f94a1` | 154.93 s |
| same, plain `121` probe | `9df0b73c7` | `…:upstream-9df0b73-cu130-121` | `sha256:21a1b75e57414ab70a0fb04156867f9e73e74163c6f289efa4c0b86c6a6d8bd4` | 151.19 s |
| **Flint image** | `a37cc4610` | `…:upstream-a37cc46-cu130` | `sha256:ef2d4bc8983f1cfa5d097ec0c3d57e1a0214450ec7c2e2dd7bc454b5d6ca2d93` | **505.56 s** |
| same tree + `GGML_CUDA_FA_ALL_QUANTS` | `a37cc4610` | `…:upstream-a37cc46-cu130-fa` | `sha256:9c31e0f3fd3d57f5fef56bee013438732e96bdcafa61e4a53486787d7a1cb0af` | 216.51 s |
| same tree on a **CUDA 13.1.1** base | `a37cc4610` | `…:upstream-a37cc46-cu131` | `sha256:a6b47a2ca14db1ffa5d95e8026f3212c23666831536d72fc19f962955869f259` | 193.63 s |
| `9df0b73c7` clean-context rebuild (receipt only, local tag) | `9df0b73c7` | `…:upstream-9df0b73-cu130-clean` | image id `97c98b0d8b08`, not pushed | 737.70 s |
| `b2e5e9b` (fork's tree) + our Dockerfile/flags, gates off (local tag, not pushed) | `b2e5e9b` | `…:upstream-b10549-cu130-ourflags` | image id `5ab3a83d16ed` | 145.68 s |

Gate output at the flint ref, verbatim: `features: mellum MTP + kolibri1 + vllm-decision2 + flint
present`, then `gate: sm_121 + kolibri1 + vllm-decision2 + mellum + flint present`; the binary reports
`version: 0.7.0-dev (build 1, commit a37cc46)`. The 505 s is the full CUDA recompile a changed tree costs
(the first build's 155 s was partly reused layers).

**Measured, same day, on idle nodes — first the flint build's health, then what the slowness actually is:**
one boot each, two 128-token requests, same GGUF pin and serve flags as the table above:

| build | decode t/s |
|---|---|
| flint image (`ef2d4bc8`) on `.31` | **101.4 / 102.7** |
| + `-DGGML_CUDA_FA_ALL_QUANTS=ON` (`9c31e0f3`) on `.33` | 97.1 / 101.7 |

So the 14× gap is a property of the `9df0b73c7` **tree**, not of upstream llama.cpp on GB10 in general:
`a37cc4610`, 38 commits later, decodes at ~100 t/s through the same Dockerfile, arch flag and node family.
`GGML_CUDA_FA_ALL_QUANTS` — the one cmake difference in the `scitrera` build — buys nothing measurable,
so the residual ~15 % against its 120 t/s is not that flag.

**Reproduced from a clean context, so it is ref-level after all.** Rebuilt `9df0b73c7` from the pre-flint
`5ce1d02` Dockerfile in an empty build context on `.30` (737.70 s, image `97c98b0d8b08`, gate passed),
booted it on `.31`: **7.9 / 8.0 t/s** — the slow number again, so the 8.4 t/s image was not a bad artifact
and a bisect was the right next step. Its window is **38 commits** (an earlier note here said four, which
was wrong), and it does touch device code: `ggml-cuda.cu` (+6, new `GGML_OP_TOP_K_MASK` dispatch and
support check), `ggml-cuda/top-k-mask.{cu,cuh}` (new), `ggml-cuda/ssm-conv.cu` (k=7), `ggml-backend-meta.cpp`
(+12/-2), `ggml-cpu/vec.{h,cpp}` (`GGML_GELU_QUICK_FP16` dropped, `ggml_vec_gelu_quick_f32` de-inlined),
and `src/llama-graph.cpp` (+100/-24). **Bisect deferred deliberately:** it is the lowest-value of the three
experiments because the fix already ships in `a37cc4610`, which this lane can use; run it only if a future
ref has to be pinned below `a37cc4610` (method: one build per first-parent commit, ~12 min each, one
128-token greedy probe; suspect the graph/backend-meta and top-k-mask changes, not the model files).

**The residual ~15 % is the upstream ref era — not the node, not CUDA, not the fork's build.** Same node
(`.30`), same GGUF pin and serve flags, two 128-token greedy requests per side:

| image | tree | base / flags | decode t/s |
|---|---|---|---|
| `scitrera/dgx-spark-llama-cpp:b10549-cu131` (fork) | `b2e5e9b` | CUDA 13.1.1, `121`, RPC+CURL+FA_ALL_QUANTS | **114.1 / 116.2** |
| upstream `a37cc4610` (`ef2d4bc8`) | `a37cc4610` | CUDA 13.0.1, `121a-real`, ours | **100.3 / 98.7** |
| upstream `a37cc4610` on a CUDA 13.1.1 base (`a6b47a2c…`) | `a37cc4610` | CUDA 13.1.1, `121a-real`, ours | 99.4 / 100.6 |
| **`b2e5e9b` + our Dockerfile and flags** (local `5ab3a83d16ed`) | `b2e5e9b` | CUDA 13.0.1, `121a-real`, ours | **114.2 / 113.9** |

That fourth row closes the question: the fork's *tree* through *our* build is as fast as the fork's image,
so every flag difference (`GGML_RPC`, `LLAMA_CURL/OPENSSL`, `FA_ALL_QUANTS`, `-G Ninja`, `BUILD_JOBS`,
arch `121`) is irrelevant to decode, and so is the CUDA base. The fork is not a patched fork at all — its
`Dockerfile.llamacpp` clones `ggml-org/llama.cpp` at a `b<number>` tag with no patch step and
`llamacpp-release-tracker.yml` only bumps that number — so its speed is simply an older upstream:
`b2e5e9b` (2026-08-21) vs `a37cc4610` (2026-10-21), **1254 upstream commits** apart (GitHub compare).
Something in those two months costs this GGUF ~13 % decode; that is an upstream matter, not this lane's,
and chasing it is out of scope here.

**Image policy (measured):** the fork image is the fast route and nothing about it needs rebuilding — but
it is just "older upstream", reproducible by us (row 4), so an arm that tolerates an older ref should get
an older-ref build from our own Dockerfile rather than the fork tag. The current-ref image buys Mellum
MTP, Kolibri-1 and flint at a ~15 % decode cost; for `mellum2.1-12b` the pin therefore stays on the fork
image, because the MTP it would gain is rejected anyway.

Node attribution while these ran: `.34` was held by a peer's `humanizer-12b-q4km-llamacpp` job
(`082a4f322a793ea0_8ed3ce77d78f`, image `2dcf49ada913`, started 06:26:31Z), `.31`/`.32` by a peer's b12x
TP=2 (`6a76d7f90a79f4f4_6eb961eae222`), and `.33` by a peer's `probe-q6k` (`7b0a21d0dbeb323d_80fa71eb085e`);
the `vllm-omni:nightly` container named `sweet_rosalind` seen at 02:25:42Z carried no sparkrun task id and
was gone by 02:31. `sparkrun` refuses a reserved host with `ResourceBusy`; the reservation lives in
`~/.config/sparkrun/operations.sqlite3` (`reservations`), so a stale row names the owning pid — check that
pid before clearing anything, and never clear a live peer's row.

**Flint's other route is closed on this fleet**, so the engine is the only one: `RecursiveSI/flint`'s
SGLang kit imports `add_grammar_backend_choices` from `sglang.srt.server_args`, which exists at v0.5.16
and not at our v0.5.22 (ImportError at plugin load), its `install.sh` sha256-verifies a
`flash_fwd_sm100.py` anchored to the 0.5.16 image, and its README requires >= 141 GB per replica — a GB10
is outside that envelope regardless. No Flint arm exists or should: the register item stays research-only.

## Selection (2026-10-13)

The lane keeps **two** recipes. **Owner decision 2026-10-13: for the explore lane the deciding factor is
accuracy, with preference for smaller and faster models** — supersedes the registry's node-count→speed
default, which had decided this lane's earlier pass on a 1.8 t/s gap that sat inside Ling's own σ (5.5).

- **`ling-3.0-flash-int4-dspark-sglang`** — rank 1: the accuracy champion (37/37 — 19/19 easy + 18/18
  hard, zero failures) at 1 node; 45.5 t/s and 154 GB.
- **`kolibri-1-78b-fp8-vllm`** — rank 2: 36/37 @4096, which is a **37/37 union** (the lone miss is a
  thinking-budget truncation) — a near-tie with Ling on the deciding factor — and it wins the stated
  preference (74 GB vs 154 GB; 47.3 vs 45.5 t/s).

Archived to [`attic/explore/`](../../attic/explore/) with a manifest: **Nemotron-262k** (the fastest
measured arm, 77.7 t/s, and the smallest at 21 GB — but 33/37, the lane's lowest accuracy, paying ~4
quality tasks for speed) and the **Nemotron 1M arm** (a variant of it: 72.2 t/s, util 0.91).

**Queued 2026-10-13 (owner directives) — all built 2026-10-14:** the **Poolside Laguna family** —
`Laguna-XS-2.1-NVFP4` + its DFlash draft (33B-A3B, 1 node) and `Laguna-S-2.1-NVFP4` (118B-A8B, 1 node)
— shipped above, with `Laguna-M.1` left as an unbuilt 2-node ceiling reference; two
**media-generation arms that sit outside this lane's reasoning/tool-calling brief** —
`Qwen/Qwen-Image-2.1-Turbo` (image; **non-commercial license**, shipped banner-marked eval-only,
owner call 2026-10-14) and `Lightricks/LTX-2.5` (video+audio; gated repo, shipped as a runbook) — plus
a third off-brief arm, the text-rewriting helper `jialinyyzz/humanizer` (12B Gemma-4 finetune,
Apache-2.0, vLLM-servable via a byte-exact `/v1/completions` prompt).
Inventory, GB10 precedents, and per-arm checklists: [`EXPLORE-MODELS-RESEARCH.md`](EXPLORE-MODELS-RESEARCH.md)
§5–§7, plus **§8** — the 2026-10-16 owner-queued `tfwnotops/…ConstantKV` Kolibri-1M research entry
(high priority; code-only, PolyForm Noncommercial 1.0.0, no GB10 precedent, so it is an owner call
before anything of its runs). The other Kolibri follow-ups queued the same day — the MTP block
drafter, the 4-bit vLLM quant packs and the GGUF ladder — live in `mad-science/TODO.md` §explore, and
the llama.cpp/GGUF runtime question is registry-level there too. Otherwise nothing further remains by
the research ranking: `vllm-sr/d3-edge` is watch-only (zero boot history), and the reserve candidates
Muse-Glimmer-30B / Xing4.0-29B-A4B / Mistral-Small-4-119B are blocked or untested (see the research
doc's checklists). Single-node TP=1.

## Serving and measurement traps this lane hit (traps 1–4 are fixed in the recipe)

1. `vllm/vllm-openai` images declare `ENTRYPOINT ["vllm","serve"]` → `executor_config: {entrypoint: ""}`.
2. The speculative config must live in `defaults.speculative_config` (referenced `'{speculative_config}'`),
   or sparkrun never distributes the draft and the offline engine dies resolving it.
3. A thinking-on-by-default model needs reply budget: Kolibri-1 answers land empty
   (`content: null`) from truncated thinking unless the request disables thinking or
   gets a larger `max_tokens` (`tools/quality-battery.py --max-tokens`).
4. Vendor plugins behind arm64: `Aleph-Alpha` ships an amd64-only image — install the
   pure-Python plugin `--no-deps` on the stock image via a mod (Kolibri-1).
5. **The 16 MiB safetensors-index inventory cap blocks the Ling launch unless sparkrun's config
   says `model_file_selection: all`.** Launching under the checkout's HOME override
   (`HOME=$PWD/.local/sparkrun-home`) dies in distribution:
   `invalid authoritative weight index for inclusionAI/Ling-3.0-flash-int4: safetensors index …
   is 18442409 bytes (17.59 MiB), exceeding the 16 MiB inventory limit; use file selection all`.
   The cap is a sparkrun **config** key (cluster config `file_selection`, or `model_file_selection:
   all` in `config.yaml`) — *not* a recipe key, since a recipe's `cluster_config:` carries only
   `resolved_model_path`/`remote_cache_dir`/`local_cache_dir`. The head's own
   `~/.config/sparkrun/config.yaml` has it (which is why the earlier boots worked); the
   `.local/sparkrun-home` copy does not. Launch from the head's own HOME. (Env fix, not a recipe
   fix — this is the research doc's Ling checklist item (d).)
6. **A hand-run `llama-benchy` against this SGLang server writes an all-`null` result.** llama-benchy
   0.4.0 sends `stream` + `return_token_ids` together and SGLang's chat endpoint 400s every
   measurement (`return_token_ids is not supported with streaming on /v1/chat/completions`), while
   the warmup/coherence probes still pass — a sweep that looks healthy and measures nothing.
   sparkrun's llama-benchy plugin injects `--extra-body 'return_token_ids=false'` for the `sglang`
   family, so measure this arm through `sparkrun benchmark performance … --profile decode-triage`
   (with `--skip-run` against a live boot), or pass that `-b extra_body=…` equivalent by hand.

## Recipe comment archive (2026-10-14)

Comments moved out of the shipped recipes per the owner's comment-placement rule (keep only what an
operator gets wrong without; everything else lives here or in the recipe's README section). The kept
YAML comments are reported per recipe below; the moved text follows.

### qwen-image-2.1-turbo-7b-bf16-diffusers-script.yaml

- **Kept:** the LICENSE banner (compressed): the qwen-research NON-COMMERCIAL gate plus the
  operational directive that a commercial operator must swap the checkpoint (the serving path is
  checkpoint-agnostic). Also kept: `runtime: vllm` is the family whose distribution/launcher contract
  the diffusers script satisfies (no sglang/vLLM engine exists); "no chat surface → readiness is the
  port + `/health`, not an inference probe"; `served_model_name` is declared so the server advertises
  the repo id (sparkrun rebinds `{model}` to the snapshot path on a launch) and naming the flag stops
  the runtime's own `--served-model-name` append.
- **Moved:** banner history — the MiniMax-M3 blocker and the Poolside S-2.1 draft-license gap
  precedents, the owner call to ship with the banner, and the eval-only rationale (the lane's accuracy
  criterion has no axis for a text-to-image checkpoint). The full banner also lives verbatim in
  [`QWEN-IMAGE.md`](QWEN-IMAGE.md) and `recipes/media/README.md`.
- **Moved:** "The Hub revision of 2026-10-12; this arm was brought up and measured on it."
- **Moved:** container rationale — the digest-pinned image serves only as the arm64 CUDA torch base;
  the diffusers `QwenImage21Pipeline` venv is staged on top by the mod; the Kai vllm-srun arm in
  `recipes/decision/` is the precedent for the runtime-family contract.
- **Moved:** the mod's first-boot venv stage and ~32 GB weight load precede the port, hence the long
  readiness budget.

### poolside-laguna-s-2.1-nvfp4-dflash-vllm.yaml

- **Kept:** `entrypoint: ""` (image declares `ENTRYPOINT ["vllm","serve"]`); `MAX_JOBS=4` caps the
  cutlass/FP4 JIT fan-out (uncapped nvcc can exhaust the 128 GB unified pool — the card's warning);
  `served_model_name` never `{model}` (rebind footgun); 120k not 262k (KV math at util 0.85); 32
  `max_num_seqs` is required, not tuned (DFlash crashes vLLM at the default 256); util stays at the
  0.85 ceiling, don't raise it; the draft MUST live in `defaults.speculative_config` with the pin in
  its `"revision"` field and no nested `{placeholder}` (kills the launch).
- **Moved:** the import-verification block — same digest pin as Kolibri-1 and Laguna-XS-2.1;
  `LagunaForCausalLM`/`DFlashLagunaForCausalLM`, the `laguna`/`laguna_dflash` modules,
  `v1.spec_decode.dflash` and the `poolside_v1` parsers resolve; the card floor is vLLM >= 0.25 and
  this build is above it.
- **Moved:** "Cold start ~15 min (99.7 GB weight load from NVMe, FP4 JIT, graph capture); the port
  gate plus a generous timeout absorb it."
- **Moved:** the vLLM refusal quote for 262k: "9.32 GiB KV cache is needed, which is larger than the
  available KV cache memory (4.58 GiB)"; the card's native 262,144 window would need 9.32 GiB of KV.
- **Moved:** raising util "has wedged GB10 nodes — ds4/AGENTS.md §11".
- **Moved:** speculative-config mechanics — sparkrun's draft binding "adds the draft repo to the
  distribution set and injects its prepared revision" and reads the pin from the same object's
  "revision" field (vLLM's own draft-revision field); n=3 is the sweep winner over the vendor default
  n=15 (which loses on one Spark).
- **Moved:** the file-format note that comments must live OUTSIDE the folded `command:` block (a `>`
  scalar keeps them as literal text and sparkrun's shell-comment rule eats every flag after the first
  `#`).

### kolibri-1-78b-fp8-vllm.yaml

- **Kept:** stock image + `--no-deps` plugin because the vendor image is amd64-only (cannot run on
  arm64 GB10); bare `mods/install-kolibri-plugin` (unpublished-mod form; the scoped form fails) and
  `--transfer-mode local` required on launches; `entrypoint: ""`; util 0.78 with the CUDA
  `~11 GiB less than MemAvailable` headroom argument.
- **Moved:** the upstream config-fix note (2026-10-13): `quantization_config.modules_to_not_convert`
  gained "lm_head", whose weight is BF16 — the old pin let the fp8 config claim an unquantized tensor
  (the re-pin's weights/tokenizer/chat template are byte-identical).
- **Moved:** plugin details — the plugin pins vLLM 0.29 and installs `--no-deps` per its README,
  never touching the image's vLLM/torch/transformers.
- **Moved:** `OMP_NUM_THREADS=4` came from the measured GB10 boot (NVIDIA forum 2026-10-04);
  `PYTORCH_CUDA_ALLOC_CONF` is supplied by the platform tier for vllm on GB10.
- **Moved:** cold start includes the 73.5 GiB weight load (~1087 s measured on GB10) before the port
  opens; the /health gate plus generous timeouts absorb it.
- **Moved:** the file-format note on folded `command:` comments (as Laguna-S above).

### poolside-laguna-xs-2.1-nvfp4-dflash-vllm.yaml

- **Kept:** `entrypoint: ""`; `served_model_name` never `{model}`; the draft-in-`speculative_config`
  pairing and pin-revision mechanics (as Laguna-S).
- **Moved:** the import-verification block — same digest pin as the Kolibri-1 arm; `LagunaForCausalLM`
  + `laguna_dflash.DFlashLagunaForCausalLM` + the `poolside_v1` parsers resolve (card floor vLLM >=
  0.21; this build is above it).
- **Moved:** the util-0.55 rationale — weights are only ~21.6 GB of the ~121 GiB pool and the arch
  holds full KV on every 4th layer only (30 of 40 are SWA window 512), so 262k is cheap; a low util
  both fits and keeps the node's ~95 GB headroom.
- **Moved:** `num_speculative_tokens` 3 is the swept winner over {3,4,7} on decode-triage; the vendor
  `generation_config.json` ships 15, which loses here.
- **Moved:** the file-format note on folded `command:` comments (as Laguna-S above).

### humanizer-12b-vllm.yaml

- **Kept:** `entrypoint: ""`; `limit_mm_per_prompt` has no sparkrun flag-map entry so it reaches vLLM
  only via the `{placeholder}` (the `-o "unmapped"` warning still applies — do not delete it), and the
  folded block keeps the embedded single quotes so the JSON arrives as one shell word.
- **Moved:** "Pinned 2026-10-14 to the revision this arm was booted and measured on."
- **Moved:** container verification — same digest as the Kolibri-1 arm; vLLM 0.29.0 resolves
  `Gemma4UnifiedForConditionalGeneration` (checked in-container: transformers 5.16.1, arch present in
  `ModelRegistry.get_supported_archs()`).
- **Moved:** readiness measurement — port-open TTR 277.9 s on a warm cache (the container start is
  what the port timer covers); a cold node spends ~800 s of one-time distribution before the container
  starts, then another ~280 s.
- **Moved:** util rationale — only the KV pool depends on it; the weights are 22.7 GiB of the 121.7
  GiB budget and at 0.85 the pool measured 370,597 tokens (45.2× concurrency at an 8192 window).
- **Moved:** the file-format note on folded `command:` comments (as Laguna-S above).

### ling-3.0-flash-int4-dspark-sglang.yaml

- **Kept:** the official-LMSYS-image rationale (the third-party port's GHCR image predates the
  `dspark_components` / `--enable-linear-replayssm-spec` flags); `served_model_name` never `{model}`;
  0.87 stays the documented ceiling; the draft pin reaches SGLang as
  `--speculative-draft-model-revision` and the weights are byte-identical across the 2026-10-12 `main`
  move — the pin is determinism, not a change.
- **Moved:** the selection narrative — the explore lane's #2 by the research ranking (124B/5.1B
  hybrid-linear MoE, INT4, one Spark), first-party DGX Spark notebook in inclusionAI's ling-cookbook.
- **Moved:** GHCR `ling_v3_support` predates the DSPARK flags; digest pinned, first pull 2026-10-11.
- **Moved:** the util ladder receipts — 0.80 ships (2026-10-12): KV pool 313,752 tokens (0.75
  measured 176,203), 262k needle PASS at depths 10/50/90, 4-way smoke clean; the third-party 0.87 rung
  reported 576,930.
- **Moved:** draft-pin mechanics — sparkrun pre-syncs the draft at the revision AND passes it as
  `--speculative-draft-model-revision`, so the served draft is the one the lane measured (the repo's
  `main` moved 2026-10-12).

[nem]: https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4
[nemd]: https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4-DSpark
[ling]: https://huggingface.co/inclusionAI/Ling-3.0-flash-int4
[lingd]: https://huggingface.co/inclusionAI/Ling-3.0-flash-dspark
[kol]: https://huggingface.co/Aleph-Alpha/Kolibri-1