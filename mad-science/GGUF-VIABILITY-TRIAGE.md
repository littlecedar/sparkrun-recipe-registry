# GGUF viability triage — per-candidate viability + expected-benefit (owner round-5 §5)

tp4-single, 2026-10-26, window 4. Conversions are separate later tasks; this file only answers
"would a GGUF route work, and what would it buy?" Case-by-case, evidence cited, baselines booted
where cheap. Baseline serve boots this window (receipts
`~/benchmarks/tp4-single-20261026/gguf-triage/`): Sol-2B decision2 GGUF Q8_0 — c1 5.121 / c2 5.433 /
c5 5.411 / c10 5.419 req/s, flat (queues, does not batch), reproducing the 2026-10-20 receipt
within 2 %; Ternary-Bonsai-2-9B Q2_0 — 77.70 ± 0.85 t/s over three 128-token greedy rows, first
decode rows for that arm.

## Standing lessons this triage inherits

1. **Pool-residency is a logistics line, not a compute one.** The 2026-10-24 migration dedup dropped
   large GGUF bodies fleet-wide: Mellum2.1 main GGUF (re-fetched this window, 8,071,295,264 B) and
   fishaudio/drama-3 (68 GB stub; re-fetch owned by tp4-recovery). Any conversion task must budget
   the re-fetch before its first cell.
2. **The llama.cpp ref floor is `a37cc4610`** (below it the tree decodes ~8 t/s; bisect deferred,
   `attic/explore/AGENTS.md`). Current engine `d854d98bae` decodes healthy (Mellum retest, same
   window: 98.44 ± 3.36 plain baseline). Engine availability per candidate is checked against the
   Dockerfile's feature gates (mellum MTP + kolibri1 + vllm-decision2 + flint + sm_121).
3. **The control-cache distribution route is dead in the pool era** — boots go through real-HOME +
   `--cluster WOPR -H <rail-IP>` with the `-hf`→`-m` pool rewrite (`recipes/ds4/README.md` caveat).

## Candidates

| candidate | engine gate | viability | expected benefit | verdict |
|---|---|---|---|---|
| **qwen3.8 GGUF trial** | two distinct artifacts, do not conflate (2026-10-26 correction): **Qwen3.8-27B (dense, arch `qwen35` — verified in the unsloth UD-Q4_K_M header by range-read)** 16,464,440,224 B — fits, `qwen35` present at both pins; **Qwen3.8-Flash-Next (arch `qwen4exp` — verified in its UD-Q4_K_XL header)** is a much larger model than the name suggests — measured `du -sbL` **111,334,654,784 B** for the 4-shard UD-Q4_K_XL, which **does not fit** the 108.8 GB budget; its viable tiers are Q3-and-below. Both archs are present at `d854d98bae` (`src/llama-arch.cpp:47` `qwen4exp`, `:158` `spark2_5`) — the earlier "official Q4_K_M = spark2_5" record conflated the checkpoint and the arch name | **27B dense TRIAL-BOOTED 2026-10-26 (.35, current engine): 12.77 ± 0.01 t/s** over three 128-token greedy rows (receipt `~/benchmarks/tp4-single-20261026/gguf-triage/RECEIPT-qwen38-27b.md`) — ~10× slower than the 12B-A2.5B MoE's 121 t/s on the same engine/node; real but slow | a single-node dense-27B serve is real but slow; the MoE checkpoints remain the single-node winners | **27B measured; Flash-Next deferred to a Q3-tier fit pass** |
| **JEV-9B decision clone (qwen35 + decision-head LoRA)** | `qwen35` arch present at both pins; llama.cpp supports LoRA at inference; but the decision lane's JEV contract is `/v1/completions` + logprobs + `allowed_token_ids` — llama.cpp has `logprobs` but **no `allowed_token_ids`** sampling constraint | **not viable as a drop-in** — the scoring surface cannot be reproduced faithfully without engine work; the Sol-2B decision2 fork arm already covers the lane's typed-decision need at 5.2-5.4 req/s | none beyond what Sol-2B GGUF already provides | **no conversion**; revisit only if upstream grows token-id constraints |
| **Ornith-1.5-122B Unsloth UD-Q3_K_XL** | engine fine (`a37cc4610`) | **measured-rejected** (window 2/3): **27.94 ± 0.07 t/s** vs the 69.28 bar, C5 < C2 — a capability arm, not the easy-traffic one; 59.76 GB body also a pool-residency risk | would be negative | **no conversion** (already recorded) |
| **GLM-5.3 / GLM-5.3-Flash / ds4 1017** | no GGUF exists at useful tiers; 176-475 GB bodies exceed the single-node frame even quantized to fit | **not viable** — the value of these arms is the TP=4 aggregate; a 1-node GGUF would be a different, much slower product | negative | **no conversion** |
| **Mellum2.1 / Bonsai / Sol-2B / Kolibri-1** | already GGUF, shipped or probed | n/a | n/a | **already served** — this window's boots are their baselines |

## Where the boot-half evidence lands

- `RECEIPT.md` (Sol-2B ladder + launch finding), `RECEIPT-bonsai.md` (first bonsai decode rows +
  the pool-stub logistics finding), `boot-*.log` — all under `~/benchmarks/tp4-single-20261026/gguf-triage/`.
- Launch finding (load-bearing, recorded in `recipes/ds4/README.md`): pool-era single-node boots need
  real HOME + `--cluster WOPR -H <rail-IP>`; the `$PWD/.local/sparkrun-home` override fails with
  `prepared model is not visible through the workload mounts`.