# IFM K2-Horizon (IFM) — serving recipes

The IFM `K2-Horizon` family on NVIDIA DGX Spark (GB10, sm_121), served with native
SGLang. Two model sizes are covered: the dense `0.9B` and the dense `7B-FP8`, plus a
`7B-Uno` conditional-LoRA diffusion draft.

> **Read [`AGENTS.md`](AGENTS.md) before working in this directory.** It carries the
> constraints, the guards, and the measurement discipline. This file is the recipe
> summary; the durable research record is `K2-*-MODEL-OPTIMIZATION-WORK.md` beside it.

## Checkpoints

| Model | repo | size | quant | notes |
|---|---|---|---|---|
| 0.9B | `IFM/K2-Horizon-0.9B` | 2.16 GB | BF16 | dense, 28 layers, 56 KiB KV/token |
| 7B | `IFM/K2-Horizon-7B-FP8` | 11.05 GB | block-FP8 (compressed-tensors) | dense, 36 layers, 144 KiB KV/token |
| 7B-Uno | `IFM/K2-Horizon-7B-Uno` | 1.40 GB adapter | — | conditional-LoRA diffusion draft for the 7B |

All recipes pin the container to `lmsysorg/sglang:v0.5.20-cu130` by **digest** — v0.5.20
is the first release that ships `models/xllm.py` (which registers `K2HorizonForCausalLM`).

## Recipes

| # | recipe | regime | key knobs | measured C1 t/s (d0 / d8k) |
|---|---|---|---|---|
| 1 | `k2-horizon-0.9b-bf16-sglang` | single-node, TP=1, 131K | `flashinfer`, no mods | **77.3 / 67.0** |
| 2 | `k2-horizon-7b-fp8-sglang` | single-node, TP=1, 131K | `flashinfer`, no mods | **21.0 / 19.0** |
| 3 | `k2-horizon-7b-fp8-ngram-sglang` | single-node, TP=1 | `flashinfer`, NGRAM spec | **27.4 / 29.2** |
| 4 | `k2-horizon-7b-fp8-uno-sglang` | PROBE, TP=1 | `fa4`, UNO spec, 2 mods | **37.7 / —** |

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

- **NGRAM speculative decoding pays on the dense 7B** (+30 % at d0, +54 % at d8k), and
  its rate *rises* with depth as n-gram matching improves.
- **UNO boots and serves at 37.7 t/s** with accept len 3.60 — clearing the modelled
  break-even of ~2.07, so the diffusion draft is a win, not "blocked at every size".
- The 7B measured **~16 % below** its modelled roofline at c=1 — the model counted only
  the weight read and ignored per-step overhead.

Full derivation: `K2-09B-MODEL-OPTIMIZATION-WORK.md` and
`K2-7B-MODEL-OPTIMIZATION-WORK.md`. Narrative: `K2-09B-JOURNAL.md` and
`K2-7B-JOURNAL.md`.

## Archived material

The `MoVA-36B-A4B` sub-lane was withdrawn on 2026-10-08 — measured working on hardware,
but too slow to justify the compute — and everything of it lives in
[`attic/ifm/`](../../attic/ifm/ARMS-MANIFEST.md): the four recipes, their FP8 gate mod,
the guards and the byte-arithmetic helper, plus the measured numbers.