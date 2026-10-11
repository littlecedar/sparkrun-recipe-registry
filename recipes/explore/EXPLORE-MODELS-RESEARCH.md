# Explore-lane model research (2026-10-11)

Frontier reasoning + tool-calling candidates for the `explore` lane. Supersedes
parts of `mad-science/EXPLORE-CANDIDATES.md` (2026-10-10): five of its claims
corrected (§3), four families added. Read-only research pass; fit arithmetic is
Hub blob-sums, NOT boots. Every number is `[measured]` (third party, on-GB10
unless stated) or `[card]` (vendor, different silicon). No candidate below has
been booted on our nodes.

Non-duplication: already served = ds4, glm5, ornith, qwen3/qwen4, embed/rerank.
`Cloudflare/clef`/`clef-flash` were found by this scan but belong to the
decision lane (see `recipes/decision/DECISION-MODELS-RESEARCH.md`).

Weighting: node count > speed > accuracy > memory (decisions #10/#11/#14).

## 1. Shortlist

| # | Model id | Params | Quant → size | Nodes | Licence | Runtime + GB10 status | Reasoning evidence | Tool-calling evidence |
|---|---|---|---|---|---|---|---|---|
| 1 | [`nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4`](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4) (+ [`-DSpark`](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4-DSpark)) | 30B / 3B (Mamba-2 + MoE + attn hybrid) | NVFP4 **20.8 GB** | **1** | OpenMDW-1.1 | vLLM. Official GB10 recipe on the card: `vllm/vllm-openai:v0.27.1`, `--moe-backend marlin`, `--mamba-backend flashinfer --mamba-cache-mode align`, parsers `nemotron_v3` + `qwen3_coder`. **GB10 has no native FP4 path** (W4A16 via Marlin) | GPQA-D 75.57, HLE 10.47, SciCode 31.38, MMLU-Pro 81.62 [card, NVFP4] | `--tool-call-parser qwen3_coder --enable-auto-tool-choice`; τ³-bank 9.48, T-Bench 2.1 23.46, SWE-bench V 52.80 [card] |
| 2 | [`inclusionAI/Ling-3.0-flash`](https://huggingface.co/inclusionAI/Ling-3.0-flash) + [`-int4`](https://huggingface.co/inclusionAI/Ling-3.0-flash-int4) + [`-dspark`](https://huggingface.co/inclusionAI/Ling-3.0-flash-dspark) | 124B / 5.1B (KDA 5:1 MLA hybrid-linear MoE) | INT4 **77.0 GB** + 2.7 GB draft | **1** | MIT | SGLang. First-party Spark notebook in `ling-cookbook`; public image `lmsysorg/sglang:dev-Ling-3.0-flash`; parsers `ling3` | GPQA-D **83.65**, IFBench 72.20, SciCode 39.35, ArcPrize 67.56 [INT4 card]; BF16 GPQA-D 84.97 | card cites SWE-Bench Pro/Multilingual, Tau3, **MCP-Atlas**, SkillsBench (chart images, not text) |
| 3 | [`Aleph-Alpha/Kolibri-1`](https://huggingface.co/Aleph-Alpha/Kolibri-1) | 78.1B / 3.46B (384 experts, 6 routed; SWA 512 + full every 5th) | FP8 **73.5 GiB** measured on-node (81.3 GB blob sum) | **1** | Apache-2.0 | vLLM + vendor plugin `aleph-alpha-inference` (pins vLLM 0.29; vendor image amd64-only — install the pure-Python plugin on `vllm/vllm-openai:v0.29.0`). Parsers `kolibri1` | AIME-2025 **96.9**, AIME-2026 96.0, GPQA-D **84.3**, LiveCodeBench v6 85.9, AA-LCR 68.3 [vendor blog] | BFCL v4 61.4, τ³-bank 38.1, τ² telecom 94.7 [vendor blog]; on-node `tool-eval-bench` short 100/100 (n=1) |
| 4 | [`meta-models/Muse-Glimmer-30B`](https://huggingface.co/meta-models/Muse-Glimmer-30B) | 29.6B dense + 1.8B ViT | NVFP4 W4A4 **25.4 GB** or FP8-block 32.8 GB; + 5.11 GB DFlash head | **1** | Apache-2.0 | vLLM 0.28+; **needs unmerged PR [vllm#51655](https://github.com/vllm-project/vllm/pull/51655)**; `sm_120a` cubins fail on SM121 (build arch plain `12.0`); `VLLM_USE_DEEP_GEMM=0` for fp8_block | GPQA-D 83.5, AIME-2026 94.7, AA-LCR 80.0 [card] | MCP-Atlas **75.5**, SWE-bench V **76.0** [card]; GB10 BFCL-MT 52.0 [third-party] — but **~10.3 tok/s single-stream NVFP4: the slowest serious candidate** |
| 5 | [`XingChen-AGI/Xing4.0-29B-A4B`](https://huggingface.co/XingChen-AGI/Xing4.0-29B-A4B) | 29B / 4B (mHC + MLA + MTP) | 4-bit GGUF **18.7 GiB**; BF16 ~58 GB | **1** | Apache-2.0 | Card claims vLLM/SGLang/KTransformers; **no GB10 precedent**; community: arch not in stock llama.cpp/Ollama | AIME-2026 **90.0**, AA-LCR 61.0 [card] | τ3 **64.63**, SWE-bench V **75.00**, T-Bench 2.1 **57.50** [card] |
| 6 | [`mistralai/Mistral-Small-4-119B-2603-NVFP4`](https://huggingface.co/mistralai/Mistral-Small-4-119B-2603-NVFP4) | 119B / 6.5B (MLA) | NVFP4 **70.8 GB**; +390 MB EAGLE head | **1 (tight)** | Apache-2.0 | MLA `head_size=320` has **no working vLLM backend on SM121** → `VLLM_MLA_DISABLE=1`, context caps ~40k (vLLM) / 64k (SGLang ~29 GB KV) | AA-LCR 0.72 [card]; no AIME/GPQA table | native function calling; `--tool-call-parser mistral` [card]; no BFCL figure |
| 7 | [`poolside/Laguna-XS-2.1`](https://huggingface.co/poolside/Laguna-XS-2.1) | 33B / 3B (256 routed, SWA 3:1) | BF16 **66.6 GB**; FP8/NVFP4/INT4 siblings | **1** | OpenMDW-1.1 | vLLM + SGLang + TRT-LLM + llama.cpp (poolside fork); DFlash draft; parsers `poolside_v1`/`laguna`; no GB10 precedent | SWE-bench V 70.9%, SWE-Pro 47.6% [card] | T-Bench 2.0 37.5%; interleaved thinking between tool calls [card] |
| 8 | [`XiaomiMiMo/MiMo-V2.6-Flash-RL`](https://huggingface.co/XiaomiMiMo/MiMo-V2.6-Flash-RL) (refreshed 2026-10-09) | 309B / 15B (sparse MoE, omni) | BF16 **~172 GB**; no in-repo FP8 (card now carries fp8/8-bit tags — sibling quant may exist) | **2** | MIT | Transformers/vLLM; own `dflash/`; no GB10 precedent | DeepSWE v1.1 67.9 [card] | Toolathlon 73.6, T-Bench 2.1 87.6, OSWorld 80.8 [card] |

**2-node tail:** `MiniMaxAI/MiniMax-M3` (428B/23B; **licence blocker** —
`minimax-community` non-commercial and this registry ships to third parties),
`thinkingmachines/Inkling-Small-NVFP4` (276B/12B, NVFP4 170.8 GB),
`poolside/Laguna-S-2.1-NVFP4` (118B/8B, 99.7 GB; T-Bench 2.1 70.2),
`IFM/K2-Horizon-375B` (belongs to the existing ifm lane), `moonshotai/Kimi-K3`
(ceiling reference only, 8–16 nodes).

## 2. Top 3 and how to sequence them on the two free nodes

All three top picks are 1 node, so priority 1 ties and SPEED decides:

| | Nemotron-3.5-Lightning | Ling-3.0-flash INT4 | Kolibri-1 FP8 |
|---|---|---|---|
| Speed | **93–96 tok/s** [measured] | 83 tok/s C1, 136 agg C6 [measured] | 48 tok/s C1, 101 agg C4 [measured] |
| Accuracy | GPQA-D 75.6 | GPQA-D 83.65 (INT4) | AIME25 96.9 / GPQA 84.3 |
| Memory | **20.8 GB** | 77.0 GB | 73.5 GiB |
| Context | 1M | 256K | ≤1M (262K native) |

Strict order: **Nemotron → Ling → Kolibri**. If accuracy is re-weighted above
speed (defensible — the repo's 1-node speed need is already met by ornith
~100 t/s), the order is **Ling → Kolibri → Xing4.0**, with Nemotron as the
co-location workhorse (21 GB leaves ~95 GB for KV/tenants). State the
weighting before building; do not let the two orderings silently merge.

Budget note: the binding cost is model download (~172 GB for all three) over
200 GbE into per-node HF caches, plus Kolibri's 10–25 min load. Suggested
order: Nemotron first (~21 GB, cheapest boot), Ling download alongside,
Kolibri only if 1–2 land early.

### Verification checklists (per candidate, before any recipe ships)

- **Nemotron-3.5-Lightning**: (a) `--moe-backend marlin` (W4A16 fallback)
  actually engages on our driver/CUDA stack; (b) DSpark draft blob size and
  whether `--speculative_config.method dspark` is accepted by the pinned vLLM
  tag; (c) `qwen3_coder` parser correctness against the tool battery (borrowed
  from Qwen, not native); (d) the "validated 1M context" claim with one needle
  probe; (e) the card's util 0.91 leaves ~1 GiB free and swaps — the community
  working point is 0.8 + 262k; do not ship 0.91/1M as default.
  Sources: card; https://github.com/sfxnz/Nemotron-3.5-Lightning-vLLM-DGX-Spark;
  https://forums.developer.nvidia.com/t/new-nemotron-3-5-lighting-30b-a3b/379832;
  https://github.com/chishiki37/muse-glimmer-benchmarks (three-way GB10 comparison:
  95.6 tok/s, GSM8K 100%, HumanEval 92%).
- **Ling-3.0-flash INT4**: (a) pin `lmsysorg/sglang:dev-Ling-3.0-flash` to a
  digest or verify our SGLang build carries `dspark_components` +
  `--enable-linear-replayssm-spec`; (b) NEXTN fallback speed/quality (the
  83-vs-37 t/s gap is entirely the external draft); (c) `ling3` parsers vs the
  tool battery; (d) 77 GB distribution vs `distribution.model.file_selection`
  (the 16 MiB safetensors-index inventory limit bit the qwen4 solo arm);
  (e) monitor host `MemAvailable` during load — this pick OOMs the node, not
  the container. On-node measured KV: util 0.87 → 23.2 GB KV = 576,930-token
  pool; safe default 0.75 → 237,922 tokens.
  Sources: https://huggingface.co/inclusionAI/Ling-3.0-flash-int4;
  ling-cookbook DGX Spark notebook;
  https://github.com/MiaAI-Lab/Ling-3.0-Flash-SGLang-DSpark-DGX-Spark;
  https://forums.developer.nvidia.com/t/ant-ling-3-0-flash-124b-a5b-new-fast-model-for-one-spark/377903.
- **Kolibri-1**: (a) whether `aleph-alpha-inference` installs into a pinnable
  image we control (exactly a `mods/`-shaped concern, but at image build, not
  pre_exec); (b) **cold start 10–25 min** (weight load alone 1087 s) —
  generous readiness timeout; (c) reasoning is ON by default and truncated
  thinking yields `content: null` — any harness must raise `max_tokens`;
  (d) one-time Triton `fused_moe` JIT delay; (e) whether the 48 tok/s figure
  depends on a non-pinnable sm121 build (floor: 20.4 tok/s on stock
  vllm-openai:v0.29.0 + plugin).
  Sources: https://aleph-alpha.com/en/blog/kolibri-has-landed-a-sovereign-open-weight-model/;
  https://forums.developer.nvidia.com/t/kolibri-1-aleph-alphas-78b-fp8-moe-runs-on-the-spark-setup-numbers-and-a-few-things-id-love-to-share/385048;
  https://github.com/Aleph-Alpha/aleph-alpha-inference.

## 3. Corrections to `mad-science/EXPLORE-CANDIDATES.md` (2026-10-10)

| Prior claim | Correction | Evidence |
|---|---|---|
| Muse-Glimmer "NVFP4 24.7 GB", ranked #2 as purpose-fit | Size is **25.42 GB**; GB10 reality **~10.3 tok/s single-stream NVFP4** (52.5 agg @c16) — the slowest serious candidate; needs unmerged vLLM PR #51655 | https://github.com/r0b0tlab/muse-glimmer-30b-nvfp4-vllm; https://recipes.vllm.ai/meta-models/Muse-Glimmer-30B; chishiki37 comparison (11.3 tok/s SGLang NVFP4) |
| Mistral-Small-4 "70.8 GB leaves ~30+ GB KV headroom" | Real single-Spark runs cap context at **40k (vLLM, MLA disabled)** or **64k (SGLang, ~29 GB KV)**; MLA head_size=320 has no SM121 backend | https://forums.developer.nvidia.com/t/running-mistral-small-4-119b-nvfp4-on-nvidia-dgx-spark-gb10/363863; https://forums.developer.nvidia.com/t/running-mistral-small-4-119b-moe-on-dgx-spark-with-sglang-full-setup-benchmarks/364763 |
| MiMo-V2.6-Flash-RL "BF16-only" | Still no in-repo FP8 (63 BF16 EP shards, ~172 GB) but refreshed 2026-10-09 with fp8/8-bit card tags — sibling quant may exist | HF file listing; card tags |
| Nemotron-3-Super-120B "VERIFIED" | True, but March-2026 vintage (outside the 90-day window) — a reference point, not a fresh candidate; Hub reports 67.2B params vs the 120B card — resolve from config.json before quoting either | https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4 |
| Inkling-Small "~265B SPECULATIVE" | Resolved: **276B total / 12B active**, 6-of-256 + 2 shared; NVFP4 blob sum 170.8 GB | https://huggingface.co/thinkingmachines/Inkling-Small |

Missing families the prior scan did not surface: Kolibri-1, Ling-3.0-flash,
Xing4.0-29B-A4B, Laguna-XS-2.1.

Also: the Hub `Parameters` field disagrees with two NVIDIA cards (Lightning
17.82B vs 30B card; Super 67.2B vs 120B card) — read `config.json`, never the
Hub field.

## 4. Battery note

Per the standard-first decision, this lane's natural standard suite is BFCL
(tool calling) — three of the shortlist entries publish BFCL numbers — plus the
already-adopted `tool-eval-bench` hard-mode/scenarios for on-node measurement.
`recipes/ds4/benchmarks/` covers the reasoning tier (HLE/GPQA/MATH/AIME are
already staged there).
