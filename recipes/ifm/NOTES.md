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

### What broke, and what it taught

1. **`@littlecedar/mods/<name>` does not resolve** for these unpublished mods (it looks
   in the published registry clone). The 7B-Uno recipe used that form and failed to
   launch; switched to bare `mods/<name>`.
2. **UNO boots and serves** (37.7 t/s, accept 3.60 > the 2.07 break-even) — the
   "blocked at every size" theory was about the stock gate the probe mod relaxes.
3. **`tg` is not interchangeable**: a run on `reconcile-headline` (tg=32) read 32.8,
   which is not comparable to a `decode-triage` (tg=128) figure.

### Still open

- UNO's quality (the accept-len win is a speed result, not an accuracy result).

### Bench artifacts

All runs on `bench_*` ids under a node's `~/.cache/sparkrun/benchmarks/`; the durable
per-run JSON/YAML was written to the operator's scratch dir (`ifm-runs/`, not tracked).
Read `tg_req_throughput` and the decode-phase row from the JSON, never the printed
table.