# Explore-lane candidates: frontier reasoning + tool-calling models for DGX Spark

**Scope:** research deliverable for the `explore` lane of `mad-science/TODO.md` — "any model with
reasoning and tool-calling capabilities… high-quality, fast, low-memory candidates that push the
frontier", to become up to 10 recipes on the 6-node GB10 cluster.
**Status:** researched 2026-10-10 (web + Hub scan). Nothing here has been booted on our nodes
except where a third-party precedent is cited. Existing lanes already serve DeepSeek V4.1 Flash,
GLM 5.3, Ornith 1.5, Qwen3.8-27B and Qwen3.8-Flash-Next — none of those are re-recommended.

Selection priorities (owner's order): node count ↓, speed ↑, accuracy ↑, memory ↓.

## Ranked candidates

| # | Model | Params (total/active) | Quant → size | Nodes | Licence | DGX-Spark precedent |
|---|---|---|---|---|---|---|
| 1 | [mistralai/Mistral-Small-4-119B-2603](https://huggingface.co/mistralai/Mistral-Small-4-119B-2603) | 119B / 6.5B | NVFP4 70.8 GB | **1** | Apache-2.0 | **VERIFIED** — NVIDIA forum single-Spark thread |
| 2 | [meta-models/Muse-Glimmer-30B](https://huggingface.co/meta-models/Muse-Glimmer-30B) | 29.6B dense | NVFP4 24.7 GB | **1** | Apache-2.0 | **VERIFIED** — Spark Arena benchmark + community repos |
| 3 | [nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4) | 30B / 3B (Mamba-2 hybrid) | NVFP4 21.6 GB | **1** | OpenMDW-1.1 | **VERIFIED** — forum, official ARM64 vLLM, + DSpark drafter |
| 4 | [nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4) | 120B / 12B | NVFP4 80.4 GB | **1** | OpenMDW-1.1 | **VERIFIED** — forum 23.45 tok/s + Spark Arena entry |
| 5 | [poolside/Laguna-S-2.1](https://huggingface.co/poolside/Laguna-S-2.1) | 118B / ~8B | NVFP4 99.7 GB | 1 (tight) | OpenMDW-1.1 | **VERIFIED** — Spark Arena, DFlash spec decode, 1 Spark |
| 6 | [MiniMaxAI/MiniMax-M3](https://huggingface.co/MiniMaxAI/MiniMax-M3) | ~428B / ~23B | MXFP4/REAP ~220 GB | 2 | **non-commercial** | **VERIFIED** — 2× Spark threads (14–15 t/s EAGLE3), 3×/4× arms |
| 7 | [XiaomiMiMo/MiMo-V2.6-Flash-RL](https://huggingface.co/XiaomiMiMo/MiMo-V2.6-Flash-RL) | ~310B / ~12B | BF16 177.8 GB | 2 | MIT | **VERIFIED** — 2× Spark, DFlash, ~80 tok/s peak (code) |
| 8 | [thinkingmachines/Inkling-Small](https://huggingface.co/thinkingmachines/Inkling-Small) | ~265B total [SPECULATIVE — active unknown] | NVFP4 170.8 GB | 2 | Apache-2.0 | **VERIFIED** — 2× Spark community recipe |
| 9 | [moonshotai/Kimi-K3](https://huggingface.co/moonshotai/Kimi-K3) | 2.8T / 104B | — realistic 8–16 nodes | 8+ | permissive-ish (`license:other`) | existence only (single-Spark streaming at 9.62 s/token is unusable) |
| 10 | [IFM/K2-Horizon-375B-A23B](https://huggingface.co/IFM/K2-Horizon-375B-A23B) | 375B / 23B | FP8 390.6 GB | 3–4 | Apache-2.0 | **none — first boot**; natural home is the existing `ifm` lane |

## Per-candidate notes

1. **Mistral-Small-4-119B-2603** — MoE, 128 experts top-4, 256K context, native function calling +
   JSON, card claims SWE-bench-class agentic (supersedes the Devstral family). NVFP4 70.8 GB leaves
   ~30+ GB KV headroom on one node. Official NVFP4 + EAGLE head. Best all-round 1-node frontier pick.
2. **Muse-Glimmer-30B** — purpose-built agentic model (DeepSearch QA, MCP-Atlas, tau3-Bench,
   SWE-Bench evals; tool schemas + failure recovery; ships its own DFlash drafter head). NVFP4
   24.7 GB is trivially 1-node with huge context headroom. Best purpose-fit for the agentic brief.
3. **Nemotron-3.5-Lightning-30B-A3B** — Mamba-2 + MoE + attention hybrid, configurable reasoning,
   NVIDIA ships a DSpark spec-decode drafter (the same algorithm our ds4 lane runs). 21.6 GB NVFP4
   is the **lowest-memory frontier-class pick**; ~95 GB left for long context / concurrency.
4. **Nemotron-3-Super-120B-A12B** — same family at 120B/12B; measured 23.45 tok/s single-Spark
   (third party). 1 node at ~35 GB KV headroom.
5. **Laguna-S-2.1** — 1M-context agentic-coding specialist with interleaved thinking between tool
   calls and a trained DFlash draft; SGLang cookbook cells exist. NVFP4 99.7 GB fits one node but
   tight (~15–20 GB KV) — modest context or 2 nodes. Sibling Laguna-XS-2.1 (33B-A3B) is a
   comfortable 1-node alternative if the big one is too tight.
6. **MiniMax-M3** — highest accuracy-per-node at 2 nodes with real measured Spark recipes
   (14–15 tok/s with EAGLE3). **Licence is the blocker**: MiniMax Community License is
   non-commercial restricted — the registry ships to third parties, so this needs an owner call.
7. **MiMo-V2.6-Flash-RL** — MIT, RL-scaled with environment+grader compute, DFlash draft, measured
   ~80 tok/s peak on 2 nodes. BF16-only today (no published quant found in the scan) — a quant
   decision is needed before a recipe.
8. **Inkling-Small** — Apache-2.0, native multimodal (text+image+audio in), agentic by design.
   NVFP4 170.8 GB → 2 nodes. Active-param count is not published — fit arithmetic is
   SPECULATIVE until the config is read from the checkpoint.
9. **Kimi-K3** — the frontier anchor (2.8T/104B, 1M ctx). Realistic floor is 8–16 nodes; included
   only as the accuracy ceiling reference, not as a servable lane on this cluster.
10. **K2-Horizon-375B-A23B** — the `ifm` lane's own family at frontier scale; Apache-2.0 with fully
    open training data. FP8 390.6 GB → 3–4 nodes. No DGX-Spark precedent anywhere — a first boot,
    but it extends a lane that already ships the 0.9B/7B siblings and their parsers.

## Fit arithmetic note

GB10 = 128 GB unified, ~119–122 GiB usable; node counts assume ~120 GB budget minus ~10–20 GB for
weights-adjacent buffers + KV. Weights sizes are Hub blob sums measured by the scan (BF16 unless
noted). **None of these fit-arithmetic numbers has been booted here.**

## What would need an owner decision before recipes

- MiniMax-M3's non-commercial licence (ships to third parties).
- MiMo-V2.6-Flash-RL has no published quant — which quant team to trust for a first export.
- How many of the 1-node picks (ranks 1–4) to build at once — they are mutually independent and
  could each boot on any free node.
