# Mellum2.1 speedup search — ranked candidate list (owner 2026-10-26 directive)

tp4-single, 2026-10-26, window 4. Format: the gguf-triage one — per-candidate viability +
expected-benefit, each with a trial-boot plan; the boots/conversions themselves are separate later
tasks. Baseline facts this list stands on: shipped arm (scitrera `b2e5e9b`, Q4_K_M) **121.27 ± 0.90 t/s**
on `.35` this window (114.1/116.2 on 2026-10-22); current-upstream `d854d98bae` plain **98.44 ± 3.36**
pooled; MTP n=1 **102.95 ± 3.20** (acceptance 0.701, mean len 1.70 — rejection stands, +4.6 % vs own
baseline only). Receipts: `~/benchmarks/tp4-single-20261026/mellum-mtp-n1-retest/`,
`~/benchmarks/tp4-single-20261026/gguf-triage/RECEIPT-mellum-plain.md`.

## Ranked candidates

| # | candidate | expected benefit | evidence | trial-boot plan |
|---|---|---|---|---|
| 1 | **Engine lineage: bisect the decode regression in the upstream tree** — first `a37cc4610..d854d98bae` (86 commits), then the deferred `b2e5e9b..a37cc4610` bisect (`attic/explore/AGENTS.md` names the suspects: graph/backend-meta and top-k-mask changes, not model files) | recovering the fork lineage's ~15-19 % (98.4→114-121 class) dwarfs every drafter win; a 1.5 h one-boot-per-first-parent-commit protocol already exists | `b2e5e9b` through OUR Dockerfile/flags reproduces 114.2/113.9 (the delta is the tree, not the build — 2026-10-22, `attic/explore/AGENTS.md`); `a37cc4610` healthy at ~100; `d854d98bae` 98.4 (this window) | one build per first-parent commit over the suspect files' commits (llama-graph.cpp, common/speculative.cpp, ggml-cuda — the 86-commit census), 128-token greedy probe each, same node; ~12 min/build |
| 2 | **Quantized MTP draft head** — the repo ships `mtp/Mellum2.1-...-MTP-Q8_0/Q6_K/Q4_K_M/MXFP4_MOE.gguf`; the 2026-10-22 sweep and the retest both used the **BF16** head (1.77 GB) | a Q8_0 head halves the draft-pass weight traffic per verify step; at n=1-2 the verify pass eats ~38 % of the step rate (measured) — a smaller head attacks exactly that term; could move n=1 from +4.6 % toward the ~+40 % acceptance ceiling, and re-open n=2 | HEAD repo listing (verified this session): the mtp/ quantized set exists; nothing in the repo docs says it is unsupported — the BF16 choice in both sweeps was availability-at-the-time, not a measurement | one boot: `-md .../mtp/...-MTP-Q8_0.gguf --spec-type draft-mtp --spec-draft-n-max 1` (then 2), sweep geometry, against the same-window plain baseline; ~30 min |
| 3 | **MXFP4_MOE main GGUF** — official, alongside Q4_K_M | if MXFP4 MoE kernels are faster than Q4_K_M's on Blackwell/sm_121 (plausible: native 4-bit MoE path), a same-quality-class decode win; size likely smaller → more KV headroom | repo listing (verified); unmeasured here | one boot, same ladder geometry, quality spot-check vs Q4_K_M (the arm's thinking-budget trap applies) |
| 4 | **Quant tier ladder Q5_K_M/Q6_K/Q8_0** (+ bartowski's full ladder incl. imatrix `i1` variants — `bartowski/Mellum2.1-12B-A2.5B-Thinking-GGUF`, verified on the Hub) | Q6_K/Q8_0 cost decode speed for quality; only worth it if a use-case needs the quality — the decode/quality trade is the measurement | repo listings verified; Q6_K exists in the official repo | one boot per tier that matters, same geometry; pair with the house battery if quality is the question |
| 5 | **llama.cpp knobs on the shipped arm**: KV cache type (`--cache-type q8_0/q5_1` — bandwidth-bound MoE decode is KV-bandwidth-sensitive), `ubatch`, flash-attention variant | modest single-digit %; zero-risk knobs on an already-shipped arm | unmeasured here; the 2026-10-19 mmap A/B already showed the platform default wins at peak (mmap OFF shipped) | one boot per knob, same geometry, A/B against the shipped config in one window |
| 6 | **Drafter alternatives (DFlash/DSpark-class)** — conditional | would need per-checkpoint drafter weights for Mellum; none exist on the Hub (searched: no DFlash/DSpark/Medusa Mellum packs; the only drafter is JetBrains' own MTP head family) | HF search this window (verified null) | no boot; re-check when upstream/Modal/Z-Lab publish Mellum drafter weights (`DRAFTER-ALTERNATIVES-1026.md` watch item) |

## Reading

The order is by expected-benefit-per-effort: #1 is a diagnosis that lifts every llama.cpp arm on the
fleet (not just Mellum); #2 is the only untested drafter lever with artifacts already published; #3-#5
are cheap single-boot measurements; #6 is blocked on artifacts that do not exist. The MTP rejection
stands for the BF16 head at n≥1 — it does not cover the quantized-head cells (#2), which is a
different point in the same cost model.

## Provenance

- Hub listings: `JetBrains/Mellum2.1-12B-A2.5B-Thinking-GGUF` (main + mtp/ files, listed above),
  `bartowski/Mellum2.1-12B-A2.5B-Thinking-GGUF`, HF search `mellum` (40 results, no drafter packs) —
  all verified 2026-10-26 via the Hub API.
- Measured baselines: the receipts under `~/benchmarks/tp4-single-20261026/` (mellum-mtp-n1-retest,
  gguf-triage) and `~/benchmarks/mellum-mtp-draft-20261022/` (the sweep).
- Queue: `mellum-speedup-search` (this file is its deliverable; boots/conversions are separate tasks).