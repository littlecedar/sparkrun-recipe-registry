# `recipes/ifm/` — working notes

Tracked working notes for the IFM K2-Horizon lane. The deep records are the
git-ignored `K2-*-MODEL-OPTIMIZATION-WORK.md` (the model, numbers, derivations) and
`K2-*-JOURNAL.md` (dated narrative) beside this file; `COOP.md` is the cross-model
ledger. Guides are [`README.md`](README.md) and [`AGENTS.md`](AGENTS.md).

**No hostnames or IPs here** — this registry ships to third parties.

## Session 2026-10-08 — first hardware run

Two idle nodes (a pair) on the GB10 cluster, image `lmsysorg/sglang:v0.5.20-cu130`
(digest `3ec36384…`), profile `benchmarking/decode-triage.yaml`, c=1.

| arm | d0 | d8k | state |
|---|---|---|---|
| `k2-horizon-0.9b-bf16-sglang` | 77.3 | 67.0 | shipped, clean |
| `k2-horizon-7b-fp8-sglang` | 21.0 | 19.0 | shipped baseline |
| `k2-horizon-7b-fp8-ngram-sglang` | 27.4 | 29.2 | **+30 %, best single-stream** |
| `k2-horizon-7b-fp8-uno-sglang` | 37.7 | — | probe; accept len 3.60 |
| `k2-horizon-36b-a4b-fp8-tp2-sglang` | 30.0 | 27.0 | **1.64× the TP=1 arm** |
| `k2-horizon-36b-a4b-fp8-tp1-sglang` | 18.3 | 16.3 | FP8 wins over BF16 |
| `k2-horizon-36b-a4b-bf16-tp1-sglang` | 15.6 | 14.1 | control |

### What broke, and what it taught

1. **All four 36B-A4B recipes were unbootable as shipped.** They die at
   `srt/models/xllm.py:204` (`_normalize_k2_horizon_config`) — SGLang demands
   `xllm_source_router_gemm_partitions` and refuses to infer it. The lane's documents
   predicted a *different* gate, on the FP8 arms only. **Fixed**: all four now pass
   `--json-model-override-args '{"xllm_source_router_gemm_partitions": 2}'` as a literal
   in `command:` (not a `defaults:` key — sparkrun does not map that flag).
2. **The FP8 checkpoint is refused at `xllm.py:665`** ("supports only compressed-tensors
   quantized model weights") — confirmed by the falsification probe's re-run, whose
   *message* prediction was right and whose *line* was off by one. So
   `mods/patch-sglang-k2-horizon-fp8` is justified, and the FP8 boots only because of it.
3. **The falsification probe missed its prediction on the first run** — it hit gate #1
   (router) before reaching the compressed-tensors gate it was written to test. Once the
   router override was added, it hit the predicted gate. Predictions written before a
   boot are only useful if you report when they miss.
4. **`@littlecedar/mods/<name>` does not resolve** for these unpublished mods (it looks
   in the published registry clone). The 7B-Uno recipe used that form and failed to
   launch; switched to bare `mods/<name>`, matching the 36B arms.
5. **FP8 beats BF16 on SM121** (18.3 vs 15.6): E5, the lane's "highest-value thing",
   answered yes. **UNO boots and serves** (37.7, accept 3.60 > the 2.07 break-even) —
   the "blocked at every size" theory was about the stock gate the probe mod relaxes.
6. **`tg` is not interchangeable**: a TP=2 run on `reconcile-headline` (tg=32) read 32.8,
   which is not comparable to a `decode-triage` (tg=128) figure. Re-run matched.

### Still open

- **TP=2 transport**: NCCL came up via the InfiniBand-detecting path, but no
  `NCCL_DEBUG=INFO` banner has confirmed `NET/IB` vs a silent TCP fallback. Confirm
  before quoting the TP=2 number as a RoCE result.
- The `zz-` probe's question is now closed; its own header says delete it.
- UNO's quality (the accept-len win is a speed result, not an accuracy result).

### Bench artifacts

All runs on `bench_*` ids under a node's `~/.cache/sparkrun/benchmarks/`; the durable
per-run JSON/YAML was written to the operator's scratch dir (`ifm-runs/`, not tracked).
Read `tg_req_throughput` and the decode-phase row from the JSON, never the printed
table.