# `recipes/ifm/` — working notes

Tracked working notes for the IFM K2-Horizon lane. The deep records are the
git-ignored `K2-*-MODEL-OPTIMIZATION-WORK.md` (the model, numbers, derivations) and
`K2-*-JOURNAL.md` (dated narrative) beside this file; `COOP.md` is the cross-model
ledger. Guides are [`README.md`](README.md) and [`AGENTS.md`](AGENTS.md).

**No hostnames or IPs here** — this registry ships to third parties.

## Session 2026-10-08 — first hardware run

Two idle nodes (a pair) on the GB10 cluster, image `lmsysorg/sglang:v0.5.20-cu130`
(digest `3ec36384…`). Models `IFM/K2-Horizon-0.9B` and `IFM/K2-Horizon-7B-FP8`
(hereafter 0.9B, 7B-FP8). Two profiles: `benchmarking/decode-triage.yaml` (tg=128,
5 runs, c=1) and `benchmarking/concurrency-sweep.yaml` (tg=256, 3 runs, c=1/4/8).

| arm | d0 | d8k | state | bench id |
|---|---|---|---|---|
| `k2-horizon-0.9b-bf16-sglang` | 77.6 | 67.3 | shipped, clean | `bench_ab57b6d3d164` |
| `k2-horizon-7b-fp8-sglang` | 21.2 | 19.2 | shipped baseline | `bench_baa8a8610893` |
| `k2-horizon-7b-fp8-ngram-sglang` | 27.4 | 29.2 | **+30 %, best single-stream** | `bench_62bc34a980db` |
| `k2-horizon-7b-fp8-uno-sglang` | 37.7 | — | probe; accept len 3.60 | `bench_74a69270d18c` |

`d0`/`d8k` are `decode-triage` single-stream aggregate decode; the bench-id table
below is the same measurement. The shipped 0.9B header and `README.md` quote 77.3 / 67.0
from the *first* session, whose artifacts are gone — the surviving rerun of the identical
profile reads 77.6 / 67.3. Do not read the 0.3 t/s gap as a regression.

### Decode throughput (t/s) — aggregate `tg_throughput.mean`

Decode-phase records only. Each cell also emits a prefill-phase record
(`is_context_prefill_phase: true`, `tg` at ~half and TTFT 2–3×), so pooling both
visibly doubles the row count and invents a bimodal boot.

| model | profile | d0 c1 | d8192 c1 | d0 c4 | d0 c8 | d8192 c4 | d8192 c8 |
|---|---|---|---|---|---|---|---|
| 0.9B | decode-triage | 77.599 | 67.277 | — | — | — | — |
| 0.9B | concurrency-sweep | 77.578 | 67.277 | 315.600 | 500.253 | 190.209 | 243.361 |
| 7B-FP8 | decode-triage | 21.209 | 19.156 | — | — | — | — |
| 7B-FP8 | concurrency-sweep | 21.172 | 19.155 | 78.816 | 119.089 | 51.085 | 69.611 |

### Same cells, per-request (t/s) — `tg_req_throughput.mean`

| model | profile | d0 c1 | d8192 c1 | d0 c4 | d0 c8 | d8192 c4 | d8192 c8 |
|---|---|---|---|---|---|---|---|
| 0.9B | decode-triage | 77.599 | 67.277 | — | — | — | — |
| 0.9B | concurrency-sweep | 77.578 | 67.277 | 82.233 | 67.448 | 50.053 | 32.678 |
| 7B-FP8 | decode-triage | 21.209 | 19.156 | — | — | — | — |
| 7B-FP8 | concurrency-sweep | 21.172 | 19.155 | 20.138 | 16.805 | 14.148 | 10.053 |

Aggregate scaling is already sub-linear at c=8 — 0.9B 4.07× at c=4 then 1.59× at c=8
(6.45× single-stream); 7B 3.72× then 1.51× (5.63×) — and per-request decode falls from
the first step up. That is the CPU/scheduler co-ceiling the 0.9B recipe comment
pre-registered (`k2-horizon-0.9b-bf16-sglang.yaml:73-76`); the 0.9B WORK doc's
">10× single-stream at bs=32" prediction was never run.

### Accuracy — **LOWER BOUNDS, truncated instrument**

| model | house (n=37) | gsm8k (n=200) | arc (n=200) |
|---|---|---|---|
| 0.9B | 27 = 72.97 % | 127 = 63.50 % | 0 = 0.00 % |
| 7B-FP8 | 33 = 89.19 % | 175 = 87.50 % | 0 = 0.00 % |

| model | truncated `finish_reason: length` (house / gsm8k / arc) | empty replies (same order) |
|---|---|---|
| 0.9B | 9 / 37 · 70 / 200 · 200 / 200 | 9 · 56 · 200 |
| 7B-FP8 | 3 / 37 · 25 / 200 · 200 / 200 | 3 · 20 · 200 |

Caps live in the harness (`recipes/ds4/benchmarks/run_benchmarks.py:130,142,155`):
house 384, gsm8k 700, arc 16. ARC's 16 tokens buy six words of thinking and no answer —
every ARC record is `finish_reason: length`, `reply: ""`, `error: null`, so the ARC
column carries no signal about the model at all. Both templates key reasoning on
`reasoning_effort` (default `high`) and contain no `enable_thinking`, so the harness's
`--thinking off` is silently ignored and every reply opens a reasoning block. Even the
house/gsm8k cells are capped mid-thought (191 / 453 mean reasoning tokens on the 0.9B),
so every score here is a **floor**, not a measurement.

### Bench ids

| bench id | model | d0 c1 | d8192 c1 |
|---|---|---|---|
| `bench_ab57b6d3d164` | 0.9B | 77.599 | 67.277 |
| `bench_baa8a8610893` | 7B-FP8 | 21.209 | 19.156 |
| `bench_62bc34a980db` | 7B-FP8, NGRAM arm | 27.384 | 29.151 |
| `bench_74a69270d18c` | 7B-FP8, UNO probe (1 run, tg=32) | 37.686 | — |
| `bench_12be50967300` | 0.9B, concurrency-sweep (c1/4/8) | 77.578 | 67.277 |
| `bench_67d531df69b6` | 7B-FP8, concurrency-sweep (c1/4/8) | 21.172 | 19.155 |
| `bench_12d689448876` | 36B-FP8 TP1, withdrawn | 18.339 | 16.299 |
| `bench_41bdb93678cc` | 36B BF16 TP1, withdrawn | 15.635 | 14.139 |
| `bench_f4c73abd8d96` | 36B-FP8 TP2, withdrawn | 29.953 | 27.043 |
| `bench_8fdc54519b69` | 36B-FP8 TP2 `reconcile-headline`, withdrawn (d0 c1/c2 only) | 32.804 | — (c2 53.697) |

The `consolidated.json` files carry only the HF base model id and the raw cells —
no recipe or arm name, and no `parallel`/TP field. So:

- NGRAM and baseline both read `IFM/K2-Horizon-7B-FP8` (same weights, different spec
  config); the NGRAM/UNO split of `bench_62bc34a980db` / `bench_74a69270d18c` is by
  value match to the arm table above.
- the three 36B ids are distinguishable only as FP8 (`12d6`, `f4c7`), BF16 (`41bd`)
  and the c=2 `reconcile-headline` run (`8fdc`); the TP=1/TP=2 split of the two FP8
  ids is **not** in the artifact. Verify against the node's `state.yaml` before
  quoting it.
- `response_size` differs by profile (128 decode-triage, 256 concurrency-sweep, 32 in
  the UNO probe) — never compare a `tg` across profiles.

### What broke, and what it taught

1. **`@littlecedar/mods/<name>` does not resolve** for these unpublished mods (it looks
   in the published registry clone). The 7B-Uno recipe used that form and failed to
   launch; switched to bare `mods/<name>`.
2. **UNO boots and serves** (37.7 t/s, accept 3.60 > the 2.07 break-even) — the
   "blocked at every size" theory was about the stock gate the probe mod relaxes.
3. **`tg` is not interchangeable**: a run on `reconcile-headline` (tg=32) read 32.8,
   which is not comparable to a `decode-triage` (tg=128) figure.

### Still open

- Accuracy: **CLOSED 2026-10-09** — the floor above was an instrument artifact, not
  a model result. See the 2026-10-09 session below.
- UNO's and NGRAM's quality — **still open**: both wins are speed results. NGRAM is
  being measured 2026-10-09; UNO's has no accuracy number yet.

### Sources — perishable

Everything above is recomputed from `.scratch/ifm/recovery-2026-10-08/` (git-ignored, on
one laptop): `headnode/09b-perf.json`, `headnode/09b-conc.json`, `headnode/7b-perf.json`,
`headnode/7b-conc.json` for both decode tables; `headnode/acc09b/IFM/*.json` and
`headnode/acc7b/IFM/*.json` for the scores, with `_raw/IFM/*.jsonl` for the
`finish_reason` histograms; `bench-ids/bench_*.json` for the ids. Read `tg_throughput` /
`tg_req_throughput` and the decode-phase record from the JSON, never the printed table.

## Session 2026-10-09 — instrument repair, accuracy re-measure, arm sweep

Two nodes, image `lmsysorg/sglang:v0.5.20-cu130` (digest `3ec36384…`), the two base
recipes relaunched through `sparkrun` from the head node. Three workstreams.

### 1. The accuracy numbers above were an instrument artifact — now fixed

`recipes/ds4/benchmarks/run_benchmarks.py` sent
`chat_template_kwargs={"enable_thinking": false}`. **Neither K2-Horizon template has
that key** — both key reasoning on `reasoning_effort` (default `high`) — so the flag
was ignored and every reply opened a reasoning block. ARC's cap was **16 tokens**, so
the block ate all 16 and all 200 items came back `finish_reason: length` with empty
content: **0.00 % by construction, not a property of the model.**

The harness gained an additive `--reasoning-effort {default,high,medium,low}` (merges
into the same `chat_template_kwargs`, leaves `--thinking off` byte-identical for the
ds4 lane), sized base caps (house 1024 / gsm8k 2048 / arc 1024) with a
`--max-tokens-scale` multiplier, a `finish_reasons` histogram + `empty_replies` in
every summary, and a slugged model id in output paths.

Re-measured (greedy, effort = server default `high`, seed 1234, same item sets):

| model | house (n=37) | gsm8k (n=200) | arc (n=200) |
|---|---|---|---|
| 0.9B | 31 = **83.8 %** | 174 = **87.0 %** | 133 = **66.5 %** |
| 7B-FP8 | 36 = **97.3 %** | 188 = **94.0 %** | 178 = **89.0 %** |

Against floors of 72.97 / 63.50 / 0.00 (0.9B) and 89.19 / 87.50 / 0.00 (7B). Residual
truncation is small and is reported, not hidden: 0.9B finish reasons are
house {stop 34, length 3}, gsm8k {stop 192, length 8}, arc {stop 189, length 11}; 7B
house {stop 37}, gsm8k {stop 193, length 7}, arc {stop 189, length 11}. **A `length`
record is a truncated response, not a wrong answer — read the histogram before
quoting any of this.**

Raw, resumable, one record per item: `.scratch/ifm/acc-2026-10-09/{09b,7b}/_raw/*.jsonl`
(git-ignored, on one laptop). Summaries sit beside them.

### 2. Arm sweep — 0.9B (`decode-triage`, one boot per arm, same window)

| arm | override | bench id | d0 c1 | d8192 c1 |
|---|---|---|---|---|
| control | — | `bench_66937856b7bb` | 77.339 | 67.036 |
| page-size 64 | `--page-size 64` | `bench_ddccb2bb32d1` | 77.652 | 67.376 |
| page-size 128 | `--page-size 128` | `bench_f511e9d7fba3` | 77.623 | 67.282 |
| fa4 | `--attention-backend fa4` | `bench_8ec5a1920280` | 78.371 | 67.735 |
| cuda-graph-max-bs 32 | `--cuda-graph-max-bs 32` | `bench_62b814092b29` | **never started** | — |

The profile's own metadata puts the inter-boot noise floor at **7-25 % for byte-identical
boots**, so nothing here is separable from noise and nothing is ranked. Two real results:

- **`--attention-backend fa4` boots and serves** — the SM120 FA4 kernel
  (`flash_attention_v4_sm120.py`, selected when capability major == 12) does run at
  `(12,1)`. A viable alternative backend, not a speed win; `flashinfer` stays the default.
- **`--cuda-graph-max-bs` does not exist in v0.5.20.** `sglang serve --help` lists only
  `--cuda-graph-max-bs-decode` / `--cuda-graph-max-bs-prefill`, so argparse rejects the
  launch and the server never binds the port. The 0.9B recipe comment that named the bare
  flag is corrected.

### 3. Arm sweep — 7B-FP8 (`decode-triage`, one node, same window)

| arm | bench id | d0 c1 | d8192 c1 |
|---|---|---|---|
| `cutlass` (shipped, 2026-10-08) | `bench_baa8a8610893` | 21.209 | 19.156 |
| `fp8_gemm_backend=auto` | `bench_83c087620bb9` | 21.170 | 19.104 |
| `fp8_gemm_backend=triton` | `bench_913796c734d4` | 20.609 | 18.628 |
| `page_size=64` | `bench_16e4daa54660` | 21.171 | 19.106 |
| `kv_cache_dtype=fp8_e4m3` | `bench_0993e4379274` | 21.362 | 20.262 |

Same noise-floor caveat. `auto` is indistinguishable from the pinned `cutlass`, so the
DeepGEMM-on-SM121 worry is not visible in throughput. `triton` is the only arm that sits
visibly lower (still inside the band). **`fp8_e4m3` KV is flat at d0 and ~+6 % at d8192**
— the byte model's shape — but its **accuracy gate is still unmet**, so it stays an arm.

### 4. Spec-arm accuracy — both arms are lossless

Scored on the same instrument and item sets as the base models:

| arm | house (n=37) | gsm8k (n=200) | arc (n=200) |
|---|---|---|---|
| plain 7B-FP8 (reference) | 36/37 = 97.3 % | 188/200 = 94.0 % | 178/200 = 89.0 % |
| NGRAM | 36/37 = 97.3 % | 187/200 = 93.5 % | 177/200 = 88.5 % |
| Uno | 36/37 = 97.3 % | 190/200 = 95.0 % | 175/200 = 87.5 % |

Every gap is within ±3 items — about one SE on n=200 — so **neither spec arm trades
accuracy for its speed win**. This closes the lane's last quality gap: NGRAM's
+29 %/+52 % and Uno's 37.7 t/s at accept-len 3.60 are lossless, not a trade.
Raw: `.scratch/ifm/acc-2026-10-09/7b-ngram/` and `.../7b-uno/`.

### Still open

- `fp8_e4m3` KV cache **accuracy** gate (throughput measured, quality not).
- The `{8,16,32,64}` `max-running-requests` ladder proper (only c=1/4/8 swept).
- The 512K-context ceiling question (`COOP.md`), and the `-decode`/`-prefill`
  cuda-graph flags that the absent bare `--cuda-graph-max-bs` was reaching for.

### Sources — perishable

`.scratch/ifm/acc-2026-10-09/` (accuracy, resumable `_raw` per item) and the arm-sweep
results on the head node under `ifm-runs/perf-2026-10-09/*.json` (`--output` of each
`sparkrun benchmark performance`). Every arm's `bench_*` id, with its overrides, is in
that bench's `~/.cache/sparkrun/benchmarks/<id>/state.yaml` under
`extras.measurement_overrides`.