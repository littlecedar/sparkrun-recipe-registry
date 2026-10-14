# Explore lane

Frontier reasoning + tool-calling models for one DGX Spark node, selected by the owner's criterion for
this lane (**accuracy decides; smaller and faster preferred**, 2026-10-13 — supersedes the registry's
node-count→speed default). Every arm here is single-node (TP=1). The lane ships the two selected
recipes (**Ling-3.0-flash-int4**, rank 1; **Kolibri-1**, rank 2) plus four measured arms added
2026-10-14 (the Poolside Laguna pair, `humanizer`, and the eval-only `Qwen-Image`); the LTX-2.5 video
arm ships as a runbook. Everything else — measured histories, selection receipts, serving traps and
the full candidate research — lives in [`attic/explore/`](../../attic/explore/) (index below).

## Contents

- [ling-3.0-flash-int4-dspark-sglang](#ling-30-flash-int4-dspark-sglang)
- [kolibri-1-78b-fp8-vllm](#kolibri-1-78b-fp8-vllm)
- [poolside-laguna-xs-2.1-nvfp4-dflash-vllm](#poolside-laguna-xs-21-nvfp4-dflash-vllm)
- [poolside-laguna-s-2.1-nvfp4-dflash-vllm](#poolside-laguna-s-21-nvfp4-dflash-vllm)
- [humanizer-12b-vllm](#humanizer-12b-vllm)
- [qwen-image-2.1-turbo-7b-bf16-diffusers-script](#qwen-image-21-turbo-7b-bf16-diffusers-script)
- [LTX-2.5 ComfyUI runbook (not a recipe)](#ltx-25-comfyui-runbook-not-a-recipe)
- [Attic index](#attic-index)

---

## [ling-3.0-flash-int4-dspark-sglang](ling-3.0-flash-int4-dspark-sglang.yaml)

SGLang · **1 node (TP=1)** · **rank 1 — kept (accuracy champion)**.

- **Model:** `inclusionAI/Ling-3.0-flash-int4` (MIT) + the DSpark draft `inclusionAI/Ling-3.0-flash-dspark`
  (pinned `d60b0e12…`).
- **Size / memory:** ~77 GB INT4 weights (+ 2.7 GB draft); 154 GB distributed (`model_file_selection: all`
  is required — the 17.59 MiB safetensors index exceeds the 16 MiB inventory cap).
- **Flags / non-obvious knobs:** `mem-fraction-static: 0.80` (KV pool 313,752 tokens; 0.87 stays the
  documented OOM-risk ceiling); `served_model_name: inclusionAI/Ling-3.0-flash-int4` declared *and*
  rendered (sparkrun otherwise rewrites `{model}` to the snapshot path); the draft pin is rendered as
  `--speculative-draft-model-revision {speculative_draft_model_revision}` (not distribution-only). KDA
  ReplaySSM verify path.
- **Measured:** C1 **45.5 t/s** @ d0 (σ 5.5, n=5) / 32.3 @ d8k; quality **37/37** (ties the top of the
  pass); 262k needle PASS at 0.80.
- **Licence:** MIT.

## [kolibri-1-78b-fp8-vllm](kolibri-1-78b-fp8-vllm.yaml)

vLLM 0.29 + vendor plugin [`mods/install-kolibri-plugin`](../../mods/install-kolibri-plugin) ·
**1 node (TP=1)** · **rank 2 — kept (near-tie accuracy; smaller + faster)**.

- **Model:** `Aleph-Alpha/Kolibri-1` (Apache-2.0), pinned `258cae8f…`.
- **Size / memory:** 74 GB FP8 (73.5 GiB); `gpu_memory_utilization: 0.78` → KV 18.99 GiB → 1,859,922 tokens.
- **Flags / non-obvious knobs:** the vendor image is amd64-only, so the recipe serves on the
  digest-pinned stock `vllm/vllm-openai:v0.29.0` with the pure-Python plugin installed `--no-deps` (the
  mod fails closed on import/entry-point failure, idempotent via a content marker);
  `executor_config: {entrypoint: ""}` (the image declares `ENTRYPOINT ["vllm","serve"]`); **thinking is
  ON by default** → callers need a larger `max_tokens` or thinking off, else truncated thinking yields an
  empty `content` (`tools/quality-battery.py --max-tokens`).
- **Measured:** C1 **47.3 t/s** @ d0 (σ 0.10) / 46.3 @ d8k; quality 36/37 @4096 (a **37/37 union** — the
  lone miss is a thinking-budget truncation).
- **Licence:** Apache-2.0.

## [poolside-laguna-xs-2.1-nvfp4-dflash-vllm](poolside-laguna-xs-2.1-nvfp4-dflash-vllm.yaml)

vLLM · **1 node (TP=1)** · measured 2026-10-14 · not selected.

- **Model:** `poolside/Laguna-XS-2.1-NVFP4` (33B total / 3B active, 256 routed experts, 3:1 SWA,
  262,144 native; OpenMDW-1.1), pinned `d32afde8…` + the first-party draft `poolside/Laguna-XS-2.1-DFlash`
  (0.92 GB), pinned `5c36361a…`.
- **Size / memory:** 21.6 GB + 0.92 GB draft; `gpu_memory_utilization: 0.55` → KV 41.56 GiB → 1,403,263
  tokens (5.35× at the native window).
- **Flags / non-obvious knobs:** NVFP4 engages natively on sm121 (`FlashInferCutlassNvFp4LinearKernel` +
  `FLASHINFER_CUTLASS` NvFp4 MoE); the draft rides in `defaults.speculative_config` with its own
  `revision`, so sparkrun both distributes and pins the blob; `num_speculative_tokens: 3` ships (a
  `decode-triage` sweep of n ∈ {3,4,7} → n=3 wins both depths); **thinking is NOT on by default despite
  the card** → the serve line passes `--default-chat-template-kwargs '{"enable_thinking": true}'`.
  **Rope caveat:** a boot warning about SWA rope is unexplained, so 262k is **pool-verified only** (a
  needle probe is the open follow-up).
- **Measured:** C1 **57.4 t/s** @ d0 (σ 3.4) / 55.1 @ d8k; accept len 1.89 / 29.5%; quality 36/37 @4096.
- **Licence:** OpenMDW-1.1 (target and draft).

## [poolside-laguna-s-2.1-nvfp4-dflash-vllm](poolside-laguna-s-2.1-nvfp4-dflash-vllm.yaml)

vLLM · **1 node (TP=1)** · measured 2026-10-14 · not selected (capped-context single-tenant).

- **Model:** `poolside/Laguna-S-2.1-NVFP4` (117.6B total / 8.5B active MoE, native 1,048,576 ctx;
  OpenMDW-1.1) + the quantization-matched draft `poolside/Laguna-S-2.1-DFlash-NVFP4` (2.2 GB).
- **Size / memory:** 99.7 GB download / **95.61 GiB resident** (the August-2026 checkpoint — the research
  doc's ~67 GiB figure does not hold); `gpu_memory_utilization: 0.85`, `max_model_len: 122880` (120k) →
  KV 4.64 GiB / 125,796 tokens (1.02× — a single-tenant 120k arm). The 262k window does **not** fit one
  Spark (vLLM refuses; it needs ~0.89 util, above the repo's 0.85 ceiling).
- **Flags / non-obvious knobs:** DFlash `num_speculative_tokens: 3`; native FP4 path
  (`FLASHINFER_CUTLASS` NvFp4 MoE on sm121) + `FLASHINFER` attention.
- **Licence (recorded as required):** the *shipped* draft `poolside/Laguna-S-2.1-DFlash-NVFP4` declares
  **no licence at all**; the BF16 sibling is `license: other` with no in-repo text — "other" resolves
  only by implication to the target's OpenMDW-1.1 (commercial + non-commercial).
- **Measured:** C1 **20.49 t/s** @ d0 (σ 0.93) / 20.11 @ d8k; accept len mean 2.52 / 50.8% rate; quality
  32/37.

## [humanizer-12b-vllm](humanizer-12b-vllm.yaml)

vLLM · **1 node** · the lane's first **`/v1/completions`** arm · not selected (off-brief).

- **Model:** `jialinyyzz/humanizer` — a 12B `google/gemma-4-12B` finetune (Apache-2.0, ungated), 23.9 GB
  bf16, 8192 ctx. **Not a chat model** — it rewrites one AI-written draft so it reads human.
- **Flags / non-obvious knobs:** the working surface is `/v1/completions` with a **byte-exact prompt**
  assembled from the repo's `prompt_format.json` (`instr + "\n\n" + draft.strip() + sep`; fingerprint
  `cc51d66b4c593fbe`, asserted on every call); the checkpoint ships **no chat template** (the chat
  endpoint 400s); `--generation-config vllm` so the checkpoint's own `top_k 64` never becomes a server
  default; `limit_mm_per_prompt {"image":0,"audio":0,"video":0}` → text-only; heterogeneous head dims
  (256 sliding / 512 full) force `TRITON_ATTN`. `model_file_selection: all` makes this an 82 GB arm
  (62 GB of GGUFs it never loads). Same digest-pinned `vllm/vllm-openai:v0.29.0` as Kolibri.
- **Measured:** ~7.6 t/s single-stream; 131.7 s per 1k output tokens; across 40 rewrites, 0 dropped facts
  (1 genuine defect found outside the instrument).
- **Licence:** Apache-2.0.

## [qwen-image-2.1-turbo-7b-bf16-diffusers-script](qwen-image-2.1-turbo-7b-bf16-diffusers-script.yaml)

diffusers engine (no `sglang`/vLLM serves it) + [`mods/qwen-image-2.1-turbo-launcher`](../../mods/qwen-image-2.1-turbo-launcher) ·
**1 node** · eval-only.

> **LICENCE — NON-COMMERCIAL ONLY.** `Qwen/Qwen-Image-2.1-Turbo` is under the **Qwen Research License
> Agreement** (card `license: other`, `license_name: qwen-research`): **FOR NON-COMMERCIAL PURPOSES
> ONLY**. This registry is distributed to third parties. A recipe ships a repo id, not weights — each
> downloader fetches from the Hub and accepts the licence there — but **neither the weights nor images
> generated from them may be used commercially**. An operator needing commercial use must swap the
> checkpoint; the serving path (`mods/qwen-image-2.1-turbo-launcher` + the recipe) is
> checkpoint-agnostic. **Owner call 2026-10-14: ship the recipe with this banner.**

- **Model:** `Qwen/Qwen-Image-2.1-Turbo` (pinned `fc13ba1986`), text-to-image + editing, 8-step distilled
  at CFG=1.
- **Size / memory:** 32.5 GB bf16 (DiT 14.2 + text encoder 17.5 + VAE 0.68); peak ~36.85 GiB torch alloc /
  37.68 GiB reserved.
- **Flags / non-obvious knobs:** `runtime: vllm` is the family whose distribution + single-node launcher
  contract the command satisfies; `command:` runs a stdlib HTTP server (`POST /generate`, `GET /health`)
  out of a `diffusers>=0.41` / `transformers>=5.17` venv the mod stages on the image's own torch
  (`vllm/vllm-openai:v0.29.0` — its transformers 5.16.1 is below the card's floor). **VAE tiling OFF**
  (tiled decode → a pink seam column) and **`cpu_offload` OFF** (costs ~4× on a reference image);
  `--served-model-name` is rendered explicitly.
- **Measured:** 1024² / 8-step CFG=1 → **11.3–11.4 s** steady; a reference image fed back for editing
  +3.5 s; same prompt+seed → a byte-identical PNG.
- **Details:** [`attic/explore/QWEN-IMAGE.md`](../../attic/explore/QWEN-IMAGE.md).

## LTX-2.5 ComfyUI runbook (not a recipe)

`Lightricks/LTX-2.5` (video+audio world model, 22B distilled DiT + Gemma-4-12B encoder) ships as a
**runbook, not a recipe** — the runtime is ComfyUI (no `sglang`/vLLM engine) and the repo is `gated: auto`
(a per-node `HF_TOKEN` + accepted terms is a prerequisite sparkrun cannot assume). See
[`ltx-2.5-runbook/README.md`](ltx-2.5-runbook/README.md). Weights ≈36.9 GB; two-stage T2V (8-step @
672×384 → upscale → 3-step refine @ 1344×768, 121 frames + audio): cold 90–100 s, warm 80 s, peak
83.6 GiB. Licence `ltx-2.x-community-license-agreement` (free below a $10M-revenue Commercial Entity
threshold). Lane notes: [`attic/explore/LTX-25.md`](../../attic/explore/LTX-25.md).

## Attic index

Everything that is not a shipped recipe lives in [`attic/explore/`](../../attic/explore/) — lane working
state, measured histories, selection receipts, serving traps, and the candidate research.

| file | what it holds / the question it answers |
|---|---|
| [`AGENTS.md`](../../attic/explore/AGENTS.md) | The lane's working notes: the full previous README — per-arm measured histories (Ling, Kolibri, Nemotron, the Laguna pair, humanizer, Qwen-Image, LTX-2.5), the selection record, and the serving/measurement traps 1–6. Start here for "why did this lane pick what it picked?" |
| [`EXPLORE-MODELS-RESEARCH.md`](../../attic/explore/EXPLORE-MODELS-RESEARCH.md) | The read-only research pass: 8 candidate families (§1), top-3 sequencing (§2), corrections to `mad-science/EXPLORE-CANDIDATES.md` (§3), the battery note (§4), and per-arm GB10 evidence + verification checklists for the Laguna family (§5), the media-gen arms (§6) and `humanizer` (§7). Answers "what else could this lane serve, and on what precedent?" |
| [`LTX-25.md`](../../attic/explore/LTX-25.md) | LTX-2.5 bring-up notes: access/prerequisite, the pinned ComfyUI unit, weights, the two-stage measurement table, the traps re-learned. Answers "how was the LTX-2.5 runbook measured, and what did it cost?" |
| [`QWEN-IMAGE.md`](../../attic/explore/QWEN-IMAGE.md) | Qwen-Image-2.1-Turbo bring-up notes: the licence banner, engine/venv design decisions, the §6 acceptance table, and the two mod defects found. Answers "how was the eval-only image arm built and verified?" |
| [`ARMS-MANIFEST.md`](../../attic/explore/ARMS-MANIFEST.md) | Manifest of the archived (measured-but-not-selected) Explore recipes with the selection ranking and the archive criterion/policy. |
| [`nemotron-3.5-lightning-30b-nvfp4-dspark-vllm.yaml`](../../attic/explore/nemotron-3.5-lightning-30b-nvfp4-dspark-vllm.yaml) | Archived recipe — the lane's original shipped default (262k, util 0.80), the fastest measured arm (77.7 t/s) and the smallest (21 GB), but the lane's lowest accuracy (33/37). Frozen provenance — do not retune. |
| [`nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm.yaml`](../../attic/explore/nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm.yaml) | Archived recipe — a variant of the 262k arm testing the card's 1M-context claim at util 0.91. Frozen provenance — do not retune. |
