# Explore-lane model research (2026-10-11; §5–§7 added 2026-10-13)

Frontier reasoning + tool-calling candidates for the `explore` lane. Supersedes
parts of `mad-science/EXPLORE-CANDIDATES.md` (2026-10-10): five of its claims
corrected (§3), four families added. Read-only research pass; fit arithmetic is
Hub blob-sums, NOT boots. Every number is `[measured]` (third party, on-GB10
unless stated) or `[card]` (vendor, different silicon). No candidate below has
been booted on our nodes.

Non-duplication: already served = ds4, glm5, ornith, qwen3/qwen4, embed/rerank.
`Cloudflare/clef`/`clef-flash` were found by this scan but belong to the
decision lane (see `../decision/DECISION-MODELS-RESEARCH.md`).

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

## 5. Poolside Laguna family — queued 2026-10-13 (owner directive)

Owner added the `poolside` Hub collections to this lane's queue (source: `hf.co/poolside/collections`,
four collections read 2026-10-13). Two members were already here — Laguna XS-2.1 (§1 row 7) and
Laguna S-2.1-NVFP4 (§1 2-node tail) — and the GB10 evidence found since **supersedes the 2-node
guess for S-2.1**: a single-Spark TP=1 sweep exists. Sizes below are Hub blob-sums (2026-10-13);
revisions are the Hub `sha` of that date; no recipe, mod, or tool in this registry references the
family yet, and none of its head repos is gated.

Family traits: text-to-text MoE on the `laguna` arch; interleaved thinking between tool calls with
per-request `enable_thinking` (vendor recommends preserved thinking); FP8 KV on the XS class;
first-party DFlash speculator drafts; parsers `poolside_v1` (tool + reasoning) on vLLM/SGLang
(`laguna` is the TRT-LLM reasoning-parser name).

| repo (Hub revision, last modified) | params (act.) | licence | size | ctx | GB10 evidence |
|---|---|---|---|---|---|
| `poolside/Laguna-XS-2.1` `c5f36269bb` 08-19 (+ `-NVFP4` `d32afde8b0` 07-29, `-FP8`, `-INT4`) | 33B (3B) | OpenMDW-1.1 | BF16 66.9 GB; **NVFP4 21.6 GB** | 262,144 | **Spark Arena**: TP=1, 1 node, **37.5 tok/s decode** [third-party], full vLLM recipe (262k, util 0.45, DFlash n=4, fp8 KV) — but its block also says `-tp 2 --nnodes 2`; read it as a sketch |
| `poolside/Laguna-XS-2.1-DFlash` `5c36361aab` 07-20 | 0.5B draft | OpenMDW-1.1 | 0.9 GB | — | `DFlashLagunaForCausalLM` (6 layers, block 16); vLLM `laguna_dflash`, SGLang `--speculative-algorithm DFLASH` |
| `poolside/Laguna-S-2.1` `0f57314083` 08-19 (+ `-NVFP4` `826aacdf6d`, `-FP8`, `-INT4`, `-GGUF`) | 118B (8B) | OpenMDW-1.1 | **NVFP4 99.7 GB download / 67.0 GiB resident** — the resident figure is **wrong**; measured **95.61 GiB** 2026-10-14 (see the sizing correction below) | 1,048,576 | **single-Spark TP=1 sweep** (fankserver, 2026-07-22, vLLM 0.25.1 — the *pre-August* checkpoint): util 0.85 → **1.37M-token KV**, decode 18.3 → 16.5 t/s over 0→65k (SWA), **DFlash n=3 best (25.5 t/s; ~2.35× on coding prompts)**, n=15 vendor default loses; TP=2 scales ~1.7× but unstable — **TP=1 recommended** |
| `poolside/Laguna-S-2.1-DFlash(-NVFP4)` `b3b5921a90` 07-31 | 1.1B draft | **the shipped `-NVFP4` draft declares no licence at all** (no `license` card field, no LICENSE file); the bf16 sibling is `license: other` with **no licence text in-repo** — read/recorded 2026-10-14 before distributing | 2.2 GB | — | forum: early acceptance ~8% at n=15; measured 2026-10-14 on one Spark: mean acceptance length 2.52 (1.36–3.40), mean Draft acceptance rate 50.8% (12.1–79.9%) at n=3 |
| `poolside/Laguna-XS.2` `a397bde045` 09-22 (+ `-NVFP4` `973ad427aa`, `-FP8`, `-INT4`) | 33B (3B) | Apache-2.0 | BF16 66.9; NVFP4 21.5; FP8 35.3; INT4 23.9 | 262,144 | none found (see the dating note) |
| `poolside/Laguna-XS.2-speculator.dflash` `6c936ca2a0` 05-19 | 0.6B draft | Apache-2.0 | 1.2 GB | — | card acceptance ≈ 2.65–3.07 avg (A100) |
| `poolside/Laguna-M.1` `2bf8a4ab6d` 07-14 (+ `-base`, `-NVFP4` `e4f3ba80ca`) | 226B (23B) | Apache-2.0 | BF16 451.6; NVFP4 139.3 | — | none; 2-node minimum at NVFP4 — ceiling reference only |

**S-2.1 sizing correction (measured 2026-10-14; boot `e57eaed458e6b584_64af2f7668b6` on `.35`).** The
`67.0 GiB resident` figure above does not hold for the pinned August-2026 revision: it loads to
**95.61 GiB** (`Model loading took 95.61 GiB memory`, `Checkpoint size: 92.85 GiB`), because the
`quantization_config` ignores attention, the dense layer-0 MLP, the shared experts **and layers 40-47's
experts**, so a large fraction of the 99.7 GB download is BF16. At util 0.85 a single Spark therefore
grants only **4.6 GiB of fp8 KV**, and vLLM **refuses the 262k window**: `ValueError: To serve … max seq
len (262144), 9.32 GiB KV cache is needed, which is larger than the available KV cache memory
(4.58 GiB) … estimated maximum model length is 124144`. The shippable single-node window is **~120k**
(the lane ships `max_model_len: 122880`; KV pool 125,796 tokens, C1 20.49 t/s @ d0, DFlash acceptance
length 2.52). The 1.37M-token-KV number and the 262k / 1M templates below describe the *pre-August*
checkpoint and must not be quoted for the pinned revision.

**Naming/dating note.** The release blog (`poolside.ai/blog/introducing-laguna-xs-2-1`) calls
**XS 2.1 the upgrade of XS.2** (+5.4 SWE-bench Multilingual, "a more open license") even though
XS.2's repo was pushed later (09-22 vs 08-19) — build XS-2.1, keep XS.2 as the Apache-2.0 fallback.
Hub `safetensors.total` disagrees across quant siblings (XS.2-INT4 40.7B vs 33.4B) — read
`config.json`, as in §3. Version floors: the cards cite vLLM ≥ 0.21 for the arch + `dflash`;
community threads cite ≥ 0.25 for the S-2.1 NVFP4 path (0.25.1 in the sweep) — verify by import on a
digest-pinned image, not by tag (the lane's Kolibri pin, `vllm/vllm-openai:v0.29.0`, is above both).

### Verification checklist (before any Laguna recipe ships)

- **Laguna XS-2.1-NVFP4 + DFlash** (queue rank 1; 1 node; 22.5 GB download):
  (a) the pinned image resolves `LagunaForCausalLM` + `dflash` + `poolside_v1` (import check);
  (b) NVFP4 (`compressed-tensors`) engages on SM121 — the Muse-Glimmer lesson says fp4 kernels are
  where GB10 breaks; INT4 23.9 GB is the fallback;
  (c) the draft rides in `defaults.speculative_config` so sparkrun distributes the 0.9 GB blob;
  (d) sweep draft depth n ∈ {3,4,7} on `decode-triage` (on the S-2.1 sibling n=3 beat the vendor
  default n=15) and record acceptance length, comparable to the lane's DSpark/DFlash2 arms;
  (e) battery with `--max-tokens` (thinking defaults ON); (f) record the KV pool at the shipped util
  for any 262k claim.
- **Laguna S-2.1-NVFP4** (queue rank 2; also 1 node): template = the TP=1 sweep (util 0.85, 262k,
  DFlash n=3) plus its RC1 long-context variant (**no DFlash + `--max-num-scheduled-tokens 4096`** →
  4.52M-token KV = 4.31× at 1M); settle the DFlash-NVFP4 licence first; 99.7 GB per node to download.
  **Resolved 2026-10-14** (see the sizing correction above): at util 0.85 the servable window is ~120k,
  not 262k — the August-2026 checkpoint is a ~96 GiB model. The recipe ships `max_model_len: 122880`.
  Licence: the shipped draft `poolside/Laguna-S-2.1-DFlash-NVFP4` declares **no** licence (no
  `license` card field, no LICENSE file); the BF16 sibling `…-DFlash` is `license: other` with no
  licence text in-repo, so "other" resolves only by implication to the target's OpenMDW-1.1.

Sources: `hf.co/poolside/collections`; `forums.developer.nvidia.com/t/laguna-s-2-1-config-benchmarks/377663`
(TP=2: 21.0 t/s c1/d0 → 46.8 c4; tool-eval-bench 82/100 ★★★★ at 262k; "1M is not possible");
`github.com/fankserver/dgx-spark-laguna-s21-nvfp4-bench`; `spark-arena.com/benchmark/a46c30c7-aa57-4a25-8290-da60dce31b77`;
`poolside.ai/blog/introducing-laguna-xs-2-1`.

## 6. Media-generation arms — queued 2026-10-13 (owner directive)

Owner added two media-generation models to this lane's queue. Both sit **outside the lane's original
brief** ("reasoning + tool-calling"): they serve no chat completions, need a runtime class this
registry has never shipped (diffusers / vLLM-OMNI / ComfyUI under a script launcher — `runtime:
sglang|vllm` does not apply), and the lane's node-count/speed/accuracy/memory weighting has no
accuracy axis for images or video. Proposed acceptance criterion (owner to confirm or replace):
**a fixed prompt+seed set; one 1024² image at the checkpoint's shipped step count and one 5 s clip at
the shipped preset; wall-clock per item and peak unified memory; quality judged by eye against the
vendor gallery** — no house scorer exists (`tools/synthetic_png.py` is a fixture, not a metric).

| model | kind | weights | licence | GB10 evidence |
|---|---|---|---|---|
| `Qwen/Qwen-Image-2.1-Turbo` `fc13ba1986` 2026-10-12 (base `Qwen-Image-2.1` `d26bb61231` 09-30) | text-to-image + editing; **8-step distilled, CFG=1**, prefix-KV context caching | 32.5 GB bf16 (DiT 14.2 + text encoder 17.5 + VAE 0.68); `QwenImage21Pipeline` (diffusers) | **`qwen-research` — "FOR NON-COMMERCIAL PURPOSES ONLY"** (LICENSE read 2026-10-13) | base model on GB10 [third-party, 2026-09-30]: **54.1 s @ 1024²/40 steps** (28.3 @ 20), peak 31.6 GB, load ≈ 3 min; 2048² 4m16; 10 reference images 598 s; a vLLM-OMNI path measured **40 s @ 40 steps**/~30 GB (2026-10-08) |
| `Lightricks/LTX-2.5` `49b093a39c` 2026-10-11 | text/image→**video with synchronized audio**, audio-to-video, native multishot, up to 4K HDR/50 FPS | ComfyUI single-file set: transformer int8-convrot 21.5 GB (**nvfp4 18.7**), Gemma-4-12B encoder int8 15.4 / bf16 26.3, video+audio VAEs, x2 latent upscaler, LoRAs 8.9 | `ltx-2.x-community-license-agreement`; **repo gated (`gated: auto`)** — the LTX-2 text (ungated repo, read 2026-10-13) grants free commercial use below a $10M-revenue "Commercial Entity" threshold | **as a refine stage on a DGX Spark** [third-party, 2026-09-14]: nvfp4 transformer 17.44 GiB + VAEs + upscaler = 20.1 GiB, three refine steps to 1344×768×124 f/24 fps **with audio** inside a 73.3 s warm two-stage run (both stages resident: 104/121 GiB peak); engine quirks below |

### Verification checklist (before any media recipe ships)

- **Qwen-Image-2.1-Turbo** (cheaper of the two; best precedent):
  (a) **licence first** — non-commercial only; a registry distributed to third parties cannot ship it
  as-is, so this needs an owner call (the MiniMax-M3 precedent) and may stay an eval-only arm;
  (b) engine: diffusers ≥ PR #14950 (pipeline-configured sampling sigmas) + transformers ≥ 5.17 — no
  `sglang|vllm` runtime exists for it; the vLLM-OMNI route is faster (40 vs 54 s on the base model)
  but is a new runtime family. Either way this is a script-launcher/runbook-shaped arm (the glm5
  precedent) unless sparkrun's runtime list grows one — check before promising a recipe;
  (c) expected Turbo speed is **derived, not measured**: GB10 base-model time is linear in steps, so
  8 steps ≈ 54.1 × 8/40 ≈ **11 s @ 1024²** (≈ 26 s @ 2048²) — verify on our node, and keep warm-up
  separate (load ≈ 3 min);
  (d) re-check the base-model write-up's traps: VAE **tiling off** (tiled decode → a pink seam column;
  +15.9 GB at 2048×1152, +28.2 GB at 2048² — cheap on 120 GB), `cpu_offload` off (1-ref image 62.5 s →
  4m20 with it on), reference images cost hard (1 ref 62.5 s, 10 refs 598 s), a self-reference at the
  same seed copies the input back oversaturated.
- **LTX-2.5** (gated; no standalone single-model Spark timing found — the 73.3 s datum is the refine
  stage inside a two-stage run):
  (a) **access + token**: `gated: auto` → accept terms in a browser and provide `HF_TOKEN` per node;
  sparkrun distribution cannot assume either, so document the prerequisite or keep the arm a runbook;
  (b) licence: the 2.x agreement's text sits behind the gate — read it once access lands (the LTX-2
  text's $10M Commercial Entity threshold is the family pattern, not proof for 2.x);
  (c) engine: ComfyUI is the native path (three templates: T2V, I2V, FLF2V; int8-convrot set ≈ 40 GB →
  1 node). **Pin the unit** the third-party write-up had to pin: ComfyUI ≥ 0.34.0 + `comfy-kitchen`
  0.2.31 + the Spectrum pack at `4783a22` — at 0.30.x the refine returns success with garbage frames;
  on GB10 the `-nogemma` graph is required, `LoadConditioningT` must appear in `/object_info`, and
  stderr alone is not proof (decode a frame);
  (d) acceptance: fix the preset first (start 720p/5 s, not 4K/50 fps), record s/clip and peak memory,
  audio+video timed as the pair;
  (e) sustained-load caveat measured on this class of job: back-to-back long generations took a Spark
  node down (a 2200 MHz clock cap was the fix) — cap before any sweep.

Sources: `hf.co/Qwen/Qwen-Image-2.1-Turbo` (+ its LICENSE); `forums.developer.nvidia.com/t/384774`
(base-model GB10 numbers) and `/t/383994` (vLLM-OMNI); `docs.comfy.org/tutorials/video/ltx/ltx-2-5`;
`hf.co/Lightricks/LTX-2.5`; `ai-muninn.com/en/blog/h3-ltx-two-stage-dgx-spark`.

## 7. Text-rewriting arm — `humanizer` 12B (queued 2026-10-13, owner directive)

A third arm outside the lane's brief: `jialinyyzz/humanizer` does not reason or call tools — it
rewrites one AI-written draft (email, essay, report, forum post; en + zh) so it reads human.
Apache-2.0, **ungated**, 54k downloads / 1.5k likes, last pushed 2026-10-08. A 12B fine-tune of
`google/gemma-4-12B`, arch `Gemma4UnifiedForConditionalGeneration` (multimodal config, used
text-only — vLLM needs `limit_mm_per_prompt {"image":0,"audio":0,"video":0}`); 8192 context.

| artefact | size | notes |
|---|---|---|
| `model.safetensors` (bf16) | 23.9 GB | the evaluation weights; 1 node, trivially |
| `humanizer-12b-Q8_0.gguf` | 12.7 GB | the file the card's fidelity numbers were measured on |
| Q6_K / Q4_K_M / Q3-QAT / IQ2_XS-QAT | 10.0 / 7.6 / 5.6 / 3.9 GB | the 2-bit/Q3/Q4 files are sensitivity-aware **and** QAT-distilled (card: 87% vs 70% top-1 agreement at 3.9 GB) |

Card results [vendor, 2026-10-02]: **95% judged human by Originality.ai at its strictest setting**
(11/210 English drafts flagged, bf16; Q8_0 15/210, within noise) against 12% for its own v1 and
60/60 flagged for a 53k-star prompt-based baseline; **fact fidelity 376/420** English rewrites with
no factual problem (Q8_0; 28/420 dropped a formatting element; median overlap with the draft 0.165);
Chinese weaker (149/204 clean). A judge-strictness audit (a second judge re-reading 150 flagged
rewrites) rated 99 serious / 41 minor / 10 unchanged, so the flags over-count — the vendor still
advises reading every number, date and name before sending.

**Serving contract — the whole trap, because a wrong prompt degrades output silently:** this is a
**text-completion** model with a byte-exact prompt: `prompt_format.json` `instr` + `"\n\n"` + draft +
`sep` (`"\n\n### Rewritten:\n\n"`, fingerprint `cc51d66b4c593fbe`); sampling temp 1.0, top_p 0.95,
**top_k off**, min_p 0, repeat_penalty 1.0, `max_tokens` 2048, stop at EOS only; **use
`/v1/completions`, never `/v1/chat/completions`** (the safetensors carry no chat template; system
prompts and history are ignored); on `vllm serve`, pass `--generation-config vllm` or vLLM inherits
`top_k` 64 from `generation_config.json` and quality drops. Long documents are split (the vendor's
`hz` tool does prompt + split + check), and the card notes the server path was not tested by the vendor.

### Verification checklist

- (a) the first registry arm whose working API is `/v1/completions` with a byte-exact prompt: the
  recipe must not route through a chat template, and whatever calls it must assemble
  `instr + draft + sep` from the shipped `prompt_format.json` bytes (a re-typed instruction is a
  quality regression by the vendor's own account);
- (b) engine: verify `Gemma4UnifiedForConditionalGeneration` resolves on a digest-pinned image
  (the lane's current pin is `vllm/vllm-openai:v0.29.0`) and record `--generation-config vllm`;
- (c) acceptance criterion (owner to confirm or replace): a fixed 20-draft set across genres × 2
  samples, reporting **fact-diff count vs the source (numbers/dates/names), formatting-drop count,
  and wall-clock per 1k output tokens**; the card's detector figure is an external paid API on one
  date — cite it, do not try to reproduce it in-house;
- (d) co-location: 12–24 GB, so it fits beside the lane's 1-node arms; the GGUF/llama.cpp path is a
  runtime family this registry has never shipped — the vLLM path keeps the arm inside the existing
  recipe schema.
