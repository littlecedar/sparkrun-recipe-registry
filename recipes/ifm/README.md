# IFM K2-Horizon (IFM) — serving recipes

The IFM `K2-Horizon` family on NVIDIA DGX Spark (GB10, sm_121), served with native
SGLang. Three model sizes are covered: the dense `0.9B`, the dense `7B-FP8` (plus a
`7B-Uno` conditional-LoRA diffusion draft), and the gated-GQA MoE
`MoVA-36B-A4B` in both BF16 and block-FP8.

> **Read [`AGENTS.md`](AGENTS.md) before working in this directory.** It carries the
> constraints, the guards, and the measurement discipline. This file is the recipe
> summary; the durable research record is `K2-*-MODEL-OPTIMIZATION-WORK.md` beside it.

## Hard prerequisite: `--json-model-override-args` for every 36B MoVA recipe

SGLang refuses every checkpoint in this family that uses MoVA (`mova_num_experts > 0`)
unless the recipe passes `xllm_source_router_gemm_partitions`. The gate is in
`srt/models/xllm.py:204` (`_normalize_k2_horizon_config`) and fires **before a weight
is read**, for BF16 and FP8 alike:

```
ValueError: K2Horizon MoVA requires explicit source router GEMM provenance;
SGLang will not infer it from runtime tensor parallelism.
```

All four 36B-A4B recipes carry the fix as a literal in `command:`:
`--json-model-override-args '{"xllm_source_router_gemm_partitions": 2}'`. Value `2` is
the MP2 router contract the vendor card's own validated recipe passes, and `1` vs `2`
is a **numerics** choice, not a speed knob (`xllm.py:620-652`). See
`K2-36B-A4B-JOURNAL.md`, 2026-10-08 — this gate was missed by the entire first draft
of the lane.

## Checkpoints

| Model | repo | size | quant | notes |
|---|---|---|---|---|
| 0.9B | `IFM/K2-Horizon-0.9B` | 2.16 GB | BF16 | dense, 28 layers, 56 KiB KV/token |
| 7B | `IFM/K2-Horizon-7B-FP8` | 11.05 GB | block-FP8 (compressed-tensors) | dense, 36 layers, 144 KiB KV/token |
| 7B-Uno | `IFM/K2-Horizon-7B-Uno` | 1.40 GB adapter | — | conditional-LoRA diffusion draft for the 7B |
| 36B-A4B | `IFM/K2-Horizon-MoVA-36B-A4B` | 74.89 GB | BF16 | MoVA gated-GQA MoE, 100 experts, 192 KiB KV/token |
| 36B-A4B-FP8 | `IFM/K2-Horizon-MoVA-36B-A4B-FP8` | 48.35 GB | block-FP8 (fp8) routed experts only | needs `mods/patch-sglang-k2-horizon-fp8` |

All recipes pin the container to `lmsysorg/sglang:v0.5.20-cu130` by **digest** — v0.5.20
is the first release that ships `models/xllm.py` (which registers `K2HorizonForCausalLM`).

## Recipes

| # | recipe | regime | key knobs | measured C1 t/s (d0 / d8k) |
|---|---|---|---|---|
| 1 | `k2-horizon-0.9b-bf16-sglang` | single-node, TP=1, 131K | `flashinfer`, no mods | **77.3 / 67.0** |
| 2 | `k2-horizon-7b-fp8-sglang` | single-node, TP=1, 131K | `flashinfer`, no mods | **21.0 / 19.0** |
| 3 | `k2-horizon-7b-fp8-ngram-sglang` | single-node, TP=1 | `flashinfer`, NGRAM spec | **27.4 / 29.2** |
| 4 | `k2-horizon-7b-fp8-uno-sglang` | PROBE, TP=1 | `fa4`, UNO spec, 2 mods | **37.7 / —** |
| 5 | `k2-horizon-36b-a4b-fp8-tp1-sglang` | single-node, TP=1, 32K | `cutlass`, FP8 gate mod | **18.3 / 16.3** |
| 6 | `k2-horizon-36b-a4b-bf16-tp1-sglang` | single-node, TP=1, 32K | control, no gate mod | **15.6 / 14.1** |
| 7 | `k2-horizon-36b-a4b-fp8-tp2-sglang` | 2-node, TP=2, 131K | RoCE x-node, FP8 gate mod | *in progress* |
| — | `zz-k2-36b-a4b-fp8-unpatched-probe-sglang` | falsification arm | no mods | one boot, then delete |

C1 t/s is single-stream (concurrency 1) aggregate decode, read from
`benchmarking/decode-triage.yaml` per-cell JSON — not the printed sparkrun table.

## Why there is no TP>1 lane below 36B

The 0.9B and 7B artifacts are 2.16 and 11.05 GB against a 128 GB unified box. TP buys
no capacity, splits an 8-KV-head GQA layout across ranks, and adds an all-reduce per
layer over a memory subsystem that is already the bottleneck. TP=1 is the only shape
worth having. For the 36B, TP is bounded to `{1, 2}` by block-FP8 divisibility
(`moe_intermediate_size/TP % block_n == 0`; 768/4 and 768/8 fail at `block_n = 128`).

## Performance (measured)

First hardware session, 2026-10-08, two nodes. Four results each falsified a
lane claim that had been argued the other way in the theory documents:

- **FP8 beats BF16 on SM121** (18.3 vs 15.6 t/s, +17 %) — so the FP8 arm is the fast
  one, not merely the loadable one.
- **NGRAM speculative decoding pays on the dense 7B** (+30 % at d0, +54 % at d8k), and
  its rate *rises* with depth as n-gram matching improves.
- **UNO boots and serves at 37.7 t/s** with accept len 3.60 — clearing the modelled
  break-even of ~2.07, so the diffusion draft is a win, not "blocked at every size".
- The 7B measured **~16 % below** its modelled roofline at c=1 — the model counted only
  the weight read and ignored per-step overhead.

Full derivation and the guard arithmetic: `K2-36B-A4B-MODEL-OPTIMIZATION-WORK.md` and
`tests/k2_36b_arith.py`. Narrative: the three `K2-*-JOURNAL.md` files.

## Archived material

There is none yet — no IFM recipe or document has been retired to `attic/ifm/`. The
`zz-` falsification arm is the one non-shippable probe, still live pending its re-run.