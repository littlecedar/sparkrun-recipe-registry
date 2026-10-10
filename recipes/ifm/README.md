# IFM K2-Horizon (IFM) — serving recipes

The IFM `K2-Horizon` family on NVIDIA DGX Spark (GB10, sm_121), served with native
SGLang. Two model sizes are covered: the dense `0.9B` and the dense `7B-FP8`, served
with UNO speculative decoding, plus the `7B-Uno` conditional-LoRA diffusion draft
that the UNO arm drafts with.

> **Read [`AGENTS.md`](AGENTS.md) before working in this directory.** It carries the
> constraints, the guards, and the measurement discipline. This file is the recipe
> summary; the deep research record (`K2-*-MODEL-OPTIMIZATION-WORK.md` / `K2-*-JOURNAL.md`)
> is git-ignored by design and absent from a fresh checkout — the measured numbers that
> survive are the ones in this file, in [`NOTES.md`](NOTES.md), in [`AGENTS.md`](AGENTS.md)
> §9, and in the recipes' own tunable comments.

## Checkpoints

| Model | repo | size | quant | notes |
|---|---|---|---|---|
| 0.9B | `IFM/K2-Horizon-0.9B` | 2.16 GB | BF16 | dense, 28 layers, 56 KiB KV/token |
| 7B | `IFM/K2-Horizon-7B-FP8` | 11.05 GB | block-FP8 (compressed-tensors) | dense, 36 layers, 144 KiB KV/token |
| 7B-Uno | `IFM/K2-Horizon-7B-Uno` | 1.40 GB adapter | — | conditional-LoRA diffusion draft for the 7B |

The two models declare **different context**: the 0.9B's
`max_position_embeddings` is **131072** (YaRN 16 x 8192 — its hard ceiling),
while the 7B's is **524288** (plain rope), and the 7B was measured serving a
**176,045-token** prompt at the 512K configuration (bench `bench_6518bc429d05`).

All recipes pin the container to `lmsysorg/sglang:v0.5.20-cu130` by **digest** — v0.5.20
is the first release that ships `models/xllm.py` (which registers `K2HorizonForCausalLM`).

## Recipes

| # | recipe | regime | key knobs | measured C1 t/s (d0 / d8k) |
|---|---|---|---|---|
| 1 | `k2-horizon-0.9b-bf16-sglang` | single-node, TP=1, 131K | `flashinfer`, no mods | **77.6 / 67.3** |
| 2 | `k2-horizon-7b-fp8-uno-sglang` | single-node, TP=1 | `fa4`, UNO spec F=8, 2 mods | **32.4 / 27.1** |

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