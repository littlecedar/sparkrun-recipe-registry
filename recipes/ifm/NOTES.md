# `recipes/ifm/` — working notes

Tracked working notes for the IFM K2-Horizon lane. The deep records the lane used to
keep beside this file — git-ignored `K2-*-MODEL-OPTIMIZATION-WORK.md` (the model,
numbers, derivations) and `K2-*-JOURNAL.md` (dated narrative) — are **absent from this
tree**; every number that matters has been folded into the sessions below, into
[`README.md`](README.md) / [`AGENTS.md`](AGENTS.md), and into `COOP.md` (the
cross-model ledger).

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

Nothing from this session: the accuracy floor closed on 2026-10-09 (below), and
both spec arms were then scored lossless on the same instrument. The 2026-10-09
session's own open items are listed at its end.

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

### 5. Context ceiling and the cuda-graph flag names

**The two models do not share a context ceiling.** 0.9B `max_position_embeddings` is
**131072** — YaRN (`factor 16` × `original_max_position_embeddings 8192`) lands exactly
there, so the recipe's 131072 default *is* the model's hard ceiling. 7B-FP8 declares
**524288** with `rope_type: default` (no YaRN) and `rope_theta 1e7`, so its 131072 default
is a choice, not a limit.

Probed the 7B at `-o max_model_len=524288`: it **boots and serves**. `--context-length
524288`, `max_total_num_tokens=618026`, KV `dtype bfloat16, K 42.44 GB + V 42.44 GB`
(84.88 GB) at `--mem-fraction-static 0.85`, served `max_model_len` 524288. Decode is
**unchanged** (21.1885 / 19.1298 t/s d0/d8192, `bench_6518bc429d05` vs the 21.209/19.156
baseline). A **176,045-token** prompt — 34 % past the old default — returned
`finish_reason: stop` with the **mid-context needle retrieved exactly**.

So 512K is reachable today on **bf16** KV: the fp8-KV arm that the lane treated as its
prerequisite is not one. Caveats: that run proves the window opens and retrieval works at
that depth; it does not establish quality across the whole span, and the pool holds 618026
tokens, so one full 524288 sequence leaves ~94k for everything else — concurrency at 512K
is effectively one stream.

Also settled: `--cuda-graph-max-bs` is **absent** at v0.5.20; `--cuda-graph-max-bs-decode`
/ `-prefill` are the real spellings. `--cuda-graph-max-bs-decode 32` boots and serves
(77.722 / 67.426 vs the 77.339 / 67.036 control, `bench_bf98a3f39ef5`) — inside noise.

### Still open

- `fp8_e4m3` KV cache **accuracy** gate (throughput measured, quality not).
- The `{8,16,32,64}` `max-running-requests` ladder proper (only c=1/4/8 swept).
- Quality across the *full* 512K span (one 176k-token request proves the window, not the
  whole range).

### Sources — perishable

`.scratch/ifm/acc-2026-10-09/` (accuracy, resumable `_raw` per item) and the arm-sweep
results on the head node under `ifm-runs/perf-2026-10-09/*.json` (`--output` of each
`sparkrun benchmark performance`). Every arm's `bench_*` id, with its overrides, is in
that bench's `~/.cache/sparkrun/benchmarks/<id>/state.yaml` under
`extras.measurement_overrides`.

## Session 2026-10-09 (continued) — the UNO campaign, and UNO promoted

Two nodes (.33/.34/.35 and the validation node .32), image unchanged, 24 boots.
Method: the driver in `.scratch/ifm/perf-2026-10-09/` runs a sequence of arms on
one node with `--fresh --no-stop` and copies each arm's `--output` JSON/YAML box
beside the logs. **One boot per arm cannot rank arms** (7-25 % inter-boot floor),
so every comparison below is same-window and the arms are means over 2-7 boots.

### Single-stream — `decode-triage` (tg=128, 5 runs, c=1), tg_throughput.mean

| arm | d0 | d8192 | accept len | boots |
|---|---|---|---|---|
| plain 7B (control) | 21.3 | 19.2 | — | 7 |
| UNO F=2 | 26.4 | 22.4 | 2.53 | 2 |
| UNO F=4 | 30.8 | 25.6 | 2.95 | 6 |
| **UNO F=8 (shipped)** | **32.4** | **27.1** | **3.10** | 6 |
| NGRAM | 27.9 | 28.6 | 1.37 | 4 |

UNO F=8 is **+52 % / +41 %** over the plain 7B. Accept length clears the ~2.07
break-even (plain 9.00 GB/token; UNO step 2*9.00 + 0.698 LoRA = 18.70 GB) and
**saturates** by F=8 — the F=4→F=8 gain (~5 %) is inside the noise floor, so F=8
is chosen on six boots, not one. NGRAM still leads UNO at d8192 (28.6 vs 27.1).

### Aggregate — `concurrency-sweep` (tg=256)

| arm | c1 d0/d8 | c4 d0/d8 | c8 d0/d8 |
|---|---|---|---|
| plain | 21.2/19.1 | 79.6/51.0 | 120.1/68.8 |
| NGRAM | 27.8/31.2 | 88.4/65.5 | 123.9/88.3 |
| UNO F=4, `max_num_seqs 8` | 29.7/25.0 | 98.6/72.1 | **97.5/70.5** |
| UNO F=8, `max_num_seqs 32` (shipped) | 32.7/27.2 | 96.7/71.3 | **145.5/90.2** |

**The finding that mattered:** the arm looked like it collapsed at c=8 (97.5,
below its own c=4) — but that flatline was `max_num_seqs: 8`, a *scheduler
admission* cap, not the draft algorithm. Lifted to 32, the same arm scales to
145.5/90.2, the best c8 figure in the lane, and the shipped recipe now sets 32.
One boot each, so the shape is firm and the exact number is not.

### What else the sweep said (all inside the noise floor — not ranked)

- `max_num_seqs` 8 vs 32 at c=1: a wash (±5 %, opposite signs across nodes); 64
  read lower once (one boot). 32 ships because of c≥4, not c=1.
- `--page-size`, `--fp8-gemm-backend`, `--cuda-graph-max-bs-decode`,
  `--attention-backend fa4`: unchanged from the earlier session's sweep.
- Every arm booted clean: 24/24 launches, so the mod chain is reliable, not lucky.

### Decision

**Promoted.** `k2-horizon-7b-fp8-uno-sglang` leaves PROBE status: F=8,
`max_num_seqs: 32`, `tags: experimental, fast`, banner rewritten with the tables,
`tests/test_k2_7b_recipes.UnoConcurrencyCap` guarding the cap. It is the lane's
fastest arm and accuracy-lossless; its two costs are the two mods (one of which
patches sglang's UNO gate) and a single-stream-at-depth edge to NGRAM.

### Still open (this session)

- UNO accuracy at the **shipped** F=8/seq=32 geometry (scored at F=4/seq=8; the
  verification path is unchanged, so quality is expected to hold — expected, not
  measured).
- Tree-mode UNO (topk>1) — never attempted; linear is shipped.
- The `bench_*` id collision between concurrent campaigns (now an `AGENTS.md`
  trap): the `--output` files are per-arm and correct, the ids are not unique.

### Sources

`.scratch/ifm/perf-2026-10-09/` — `<tag>.json` (per-arm result), `<tag>.log`
(bench stdout + the authoritative `Benchmark ID:`), `<tag>.serve.log` (sglang
log: the `accept len:` lines). Tags are `a*` (pairwise .33), `b*` (F sweep .34),
`c1-c5` (concurrency/seq .35), `d*` (knob factorial .34), `e*` (replicate .33),
`v1-*` (validation .32). Git-ignored; on one laptop.

## Session 2026-10-09 (continued) — the lane consolidated to one 7B recipe

Documentation-only continuation of the same day; no boots. `recipes/ifm/` now ships a
**single 7B recipe**, `k2-horizon-7b-fp8-uno-sglang`, alongside the `0.9B`.

**Kept** because it is the best-overall arm: fastest in the lane single-stream at d0
(32.4 vs the plain 7B's 21.3 and NGRAM's 27.9) and at aggregate c=8 (145.5/90.2 vs
plain 120.1/68.8 and NGRAM 123.9/88.3), and accuracy-lossless on the shared instrument
(the spec-arm gaps in §4 above are all within ±3 items ≈ one SE on n=200). NGRAM's only
edge — single-stream d8k 28.6 vs 27.1 — is inside the lane's own 7-25 % inter-boot noise
floor.

**Retired:** `k2-horizon-7b-fp8-sglang` (plain) and `k2-horizon-7b-fp8-ngram-sglang`.
Both were moved, contents **unedited**, to `attic/ifm/arms/` (`ARMS-MANIFEST.md`). The
measured tables above — this session's and 2026-10-08's — are the justification for the
selection and are kept as written.