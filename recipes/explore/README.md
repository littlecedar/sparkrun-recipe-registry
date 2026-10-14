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
| [`ling-3.0-flash-int4-dspark-sglang.yaml`](ling-3.0-flash-int4-dspark-sglang.yaml) | SGLang | [inclusionAI/Ling-3.0-flash-int4][ling] + [DSpark draft][lingd] (draft pinned `d60b0e12`) | 1 | **45.5** | **BOOT-VERIFIED 2026-10-11** (quality 37/37; 262k needle-verified at 0.80) — **KEPT (rank 1, accuracy)**; draft re-pinned 2026-10-14 (re-verified 54.7 t/s, 37/37) |
| [`kolibri-1-78b-fp8-vllm.yaml`](kolibri-1-78b-fp8-vllm.yaml) | vLLM 0.29 + plugin | [Aleph-Alpha/Kolibri-1][kol] (pinned `258cae8f`) | 1 | **47.3** | **BOOT-VERIFIED 2026-10-12** (quality 36/37 @4096; `kolibri1` parsers via the plugin mod) — **KEPT (rank 2, near-tie accuracy; smaller + faster)**; re-pinned 2026-10-14 (re-verified 47.4 t/s, 37/37 @4096) |

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

New recipe [`kolibri-1-78b-fp8-vllm.yaml`](kolibri-1-78b-fp8-vllm.yaml) +
[`mods/install-kolibri-plugin`](../../mods/install-kolibri-plugin): the vendor's
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
- **Plugin mod re-confirmed on the re-pinned revision**: `mods/install-kolibri-plugin` installed
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
strings). Same digest-pinned `vllm/vllm-openai:v0.29.0` as Kolibri.

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
- **`model_file_selection: all` makes this an 82 GB arm**: the head's config (needed by Ling, trap 5)
  distributes the whole repo, so the node's cache holds 62 GB of GGUF quants this arm never loads —
  796.1 s of distribution for a 23.9 GB checkpoint. The recipe is correct; the config key is
  cluster-level.
- **Verdict**: boots and rewrites faithfully at ~7.6 t/s single-stream (23 s per short draft). Off
  the lane's brief (no reasoning, no tool calls), so it competes with nothing in the selection.
- Receipts: `~/benchmarks/humanizer-20261014/` on the head (and on `.35`): `SUMMARY.md`, `boot.log`,
  `serve.log`, `measure.py` + `analyze.py` (stdlib), `results.json`, `analyze.log`.

### Poolside Laguna-XS-2.1-NVFP4 + DFlash (2026-10-14)

New recipe [`poolside-laguna-xs-2.1-nvfp4-dflash-vllm.yaml`](poolside-laguna-xs-2.1-nvfp4-dflash-vllm.yaml)
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

New recipe [`poolside-laguna-s-2.1-nvfp4-dflash-vllm.yaml`](poolside-laguna-s-2.1-nvfp4-dflash-vllm.yaml)
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
- **Draft licence (recorded as required):** the *shipped* draft `poolside/Laguna-S-2.1-DFlash-NVFP4`
  declares **no licence at all** — no `license` field in its card data and no LICENSE file; the BF16
  sibling `poolside/Laguna-S-2.1-DFlash` is `license: other` with **no licence text in the repo**, so
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

**Queued 2026-10-13 (owner directives):** the **Poolside Laguna family** — build
`Laguna-XS-2.1-NVFP4` + its DFlash draft first (33B-A3B, 1 node, 22.5 GB download, Spark Arena
precedent), then `Laguna-S-2.1-NVFP4` (118B-A8B, also 1 node per the single-Spark TP=1 sweep), with
`Laguna-M.1` as a 2-node ceiling reference; and two **media-generation arms that sit outside this
lane's reasoning/tool-calling brief** — `Qwen/Qwen-Image-2.1-Turbo` (image; **non-commercial licence,
owner call required before it can ship**) and `Lightricks/LTX-2.5` (video+audio; gated repo) — plus a
third off-brief arm, the text-rewriting helper `jialinyyzz/humanizer` (12B Gemma-4 finetune,
Apache-2.0, vLLM-servable via a byte-exact `/v1/completions` prompt).
Inventory, GB10 precedents, and per-arm checklists: [`EXPLORE-MODELS-RESEARCH.md`](EXPLORE-MODELS-RESEARCH.md)
§5–§7. Otherwise nothing further remains by the research ranking: `vllm-sr/d3-edge` is watch-only
(zero boot history), and the reserve candidates Muse-Glimmer-30B / Xing4.0-29B-A4B /
Mistral-Small-4-119B are blocked or untested (see the research doc's checklists). Single-node TP=1.

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

[nem]: https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4
[nemd]: https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4-DSpark
[ling]: https://huggingface.co/inclusionAI/Ling-3.0-flash-int4
[lingd]: https://huggingface.co/inclusionAI/Ling-3.0-flash-dspark
[kol]: https://huggingface.co/Aleph-Alpha/Kolibri-1