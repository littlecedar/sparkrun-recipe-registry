# Explore lane

Frontier reasoning + tool-calling models that push the frontier on DGX Spark, chosen by the
registry's selection weighting (**node count → speed → accuracy → memory**). No recipe cap (owner
decision 2026-10-11). Full candidate research — 8 families, five corrections to the earlier
`mad-science/EXPLORE-CANDIDATES.md`, per-candidate verification checklists — is in
[`EXPLORE-MODELS-RESEARCH.md`](EXPLORE-MODELS-RESEARCH.md).

| recipe | runtime | model | nodes | C1 t/s | status |
|---|---|---|---|---|---|
| [`nemotron-3.5-lightning-30b-nvfp4-dspark-vllm.yaml`](nemotron-3.5-lightning-30b-nvfp4-dspark-vllm.yaml) | vLLM | [nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4][nem] + [DSpark draft][nemd] | 1 | **77.7** | **BOOT-VERIFIED 2026-10-11** |
| [`nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm.yaml`](nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm.yaml) | vLLM | [nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4][nem] + [DSpark draft][nemd] — **1M arm** | 1 | **72.2** | **BOOT-VERIFIED 2026-10-12** (card's 0.91/1M claim confirmed; shipped default stays 262k/0.8) |
| [`kolibri-1-78b-fp8-vllm.yaml`](kolibri-1-78b-fp8-vllm.yaml) | vLLM 0.29 + plugin | [Aleph-Alpha/Kolibri-1][kol] | 1 | **47.3** | **BOOT-VERIFIED 2026-10-12** (quality 36/37 @4096; `kolibri1` parsers via unpushed mod) |

## Measured

- **77.7 t/s @ d0** (σ 9.8, n=5) and 76.3 @ d8k (σ 26.0) on `benchmarking/decode-triage.yaml`, TP=1,
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

### Nemotron-3.5-Lightning — 1M-context arm (2026-10-12)

New recipe [`nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm.yaml`](nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm.yaml):
the shipped 262k recipe verbatim with exactly two defaults changed —
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
- The **shipped default remains the 262k/0.8 recipe**; this arm documents the
  measured servability of the card's 1M point. Receipts:
  `~/benchmarks/nemotron-1m-20261012/` on the head node (boot log, both probe
  runs, decode-triage triple).

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
- **Keep**: not dominated. 47.3 t/s ≥ Ling's 45.5 at 36/37 quality (Ling 37/37),
  one node, and the accuracy-champion role by the vendor's AIME/GPQA numbers —
  at the cost of 73.5 GiB weights (the memory-heaviest explore arm).
- Receipts: `~/benchmarks/kolibri-20261012/` on the head node.

## Next by the ranking

Ling and Kolibri-1 are **built and measured** (above). What remains by the
research ranking: `vllm-sr/d3-edge` — watch only (zero boot history); and the
reserve candidates Muse-Glimmer-30B / Xing4.0-29B-A4B / Mistral-Small-4-119B,
all blocked or untested (see the research doc's checklists). Single-node TP=1.

## Serving traps this lane hit (all fixed in the recipe)

1. `vllm/vllm-openai` images declare `ENTRYPOINT ["vllm","serve"]` → `executor_config: {entrypoint: ""}`.
2. The speculative config must live in `defaults.speculative_config` (referenced `'{speculative_config}'`),
   or sparkrun never distributes the draft and the offline engine dies resolving it.
3. A thinking-on-by-default model needs reply budget: Kolibri-1 answers land empty
   (`content: null`) from truncated thinking unless the request disables thinking or
   gets a larger `max_tokens` (`tools/quality-battery.py --max-tokens`).
4. Vendor plugins behind arm64: `Aleph-Alpha` ships an amd64-only image — install the
   pure-Python plugin `--no-deps` on the stock image via a mod (Kolibri-1).

[nem]: https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4
[nemd]: https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4-DSpark
[ling]: https://huggingface.co/inclusionAI/Ling-3.0-flash-int4
[lingd]: https://huggingface.co/inclusionAI/Ling-3.0-flash-dspark
[kol]: https://huggingface.co/Aleph-Alpha/Kolibri-1