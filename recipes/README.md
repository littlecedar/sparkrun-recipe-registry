# Little Cedar Sparkrun Recipes

_Brought to you by Little Cedar Group._

These are the recipes we are using in the office on our humble 6-node DGX Spark cluster.

# Recipes

## DeepSeek V4

| Recipe                                       | Flags  | C1 t/s |  Size |  Mem | TP | Model Cards                                                |
|:---------------------------------------------|:-------|-------:|------:|-----:|---:|:-----------------------------------------------------------|
| deepseek-v4.1-flash-knapcio-tp4-1m-sglang    | ✨🚚🌲👀 |   46.5 | 510GB | 0.80 |  4 | [Model][deepseek-ai/DeepSeek-V4.1-Flash]                   |
| deepseek-v4.1-flash-tensorfold-tp2-1m-sglang | 🚀🚚1  |   73.0 | 385GB |    — |  2 | [Model][littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram] |

## Ornith 1.5

| Recipe                                           | Flags  | C1 t/s |  Size |  Mem | TP | Model Cards                                                                            |
|:------------------------------------------------|:------|------:|-----:|----:|---:|:--------------------------------------------------------------------------------------|
| littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm | 🌲👀🧠🦾🔧 |  41.86 | 235GB | 0.80 |  4 | [Model][littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft]                                   |
| ornith-1.5-35b-a3b-nvfp4-dflash2-sglang          | ✨🚀🌲👀🧠🦾🔧 |    100 |  45GB | 0.85 |  1 | [Model][ornith-ai/Ornith-1.5-35B-A3B-NVFP4] [Draft][jzinno/Ornith-1.5-35B-A3B-DFlash2] |
| ornith-1.5-9b-nvfp4-dflash-sglang               | ✨🚀🤏👀🧠🦾🔧 |    55 |  11GB | 0.85 |  1 | [Model][ornith-ai/Ornith-1.5-9B-NVFP4] [Draft][ornith-ai/Ornith-1.5-9B-DFlash]        |

## Embed

| Recipe                                   | Flags    | C1 t/s | Size |  Mem | TP | Model Cards                                    |
|:----------------------------------------|:--------|------:|----:|----:|---:|:----------------------------------------------|
| qwen3-vl-embedding-2b-vllm-b12x          | 🚀🌲👀📶🤏 |      — |    — | 0.25 |  1 | [Model][Qwen/Qwen3-VL-Embedding-2B]            |
| qwen3-vl-embedding-8b-awq-4bit-vllm-b12x | 🚀🌲👀📶🤏 |      — |    — | 0.30 |  1 | [Model][gonuit/Qwen3-VL-Embedding-8B-AWQ-4bit] |

## Rerank

| Recipe                                   | Flags    | C1 t/s | Size |  Mem | TP | Model Cards                                    |
|:----------------------------------------|:--------|------:|----:|----:|---:|:----------------------------------------------|
| qwen3-vl-reranker-2b-vllm-b12x           | 🚀🌲👀🔃🤏 |      — |    — | 0.30 |  1 | [Model][Qwen/Qwen3-VL-Reranker-2B]             |
| qwen3-vl-reranker-8b-vllm-b12x           | 🌲👀🔃🤏 |      — |    — | 0.30 |  1 | [Model][Qwen/Qwen3-VL-Reranker-8B]             |

## Qwen 3x

The C1 column's `50` for dflash2 is the measured **c=2 aggregate** (tg=128, pp=256), not a
single-stream number — the recipe's own decode-only measurement is 33.8 t/s at c=1.

| Recipe                               | Flags  | C1 t/s | Size |  Mem | TP | Model Cards                                                             |
|:------------------------------------|:------|------:|----:|----:|---:|:-----------------------------------------------------------------------|
| qwen3.8-27b-nvfp4-dflash2-sglang     | 🌲🚀👀 |     50 | 21GB | 0.85 |  1 | [Model][RadixArk/Qwen3.8-27B-NVFP4] [Draft][incoai/Qwen3.8-27B-DFlash2] |
| qwen3-coder-next-int4-autoround-vllm | 🌲🚀   |    71.7 | 41GB | 0.85 |  1 | [Model][Intel/Qwen3-Coder-Next-int4-AutoRound] — vLLM; **measured 2026-10-11, 2.1× the DFlash2 C1; house battery 35/37** |
| qwen3.8-27b-mlx4bit-tensorfold-sglang | 👀     |   41.3 | 19GB |    — |  1 | [Model][TensorFold/Qwen3.8-27B-MLX-4bit] [Draft][z-lab/Qwen3.8-27B-DFlash2] — **TensorFold** engine (MiaAI-Lab); booted 2026-10-14, house battery 37/37 |

The third Qwen 3x arm, added 2026-10-14: `qwen3.8-27b-mlx4bit-tensorfold-sglang` is Mia's AI Lab's
**TensorFold** route — a foreign engine behind the `runtime: sglang` shim, one DGX Spark (TP=1),
MLX affine-4-bit weights plus the DFlash2 drafter, FP8 KV cache and vision — on a digest-pinned
public image. **Booted and measured 2026-10-14** on `.30` (`benchmarking/decode-triage.yaml`):
**41.3 ± 4.0 t/s @ d0** and 41.7 ± 2.4 @ d8192, house battery **37/37** — above the DFlash2 arm's
33.8 at the same c=1. There is no `Mem` knob (the engine sizes its own budget); upstream's own
numbers and the launch caveats are in [`qwen3/README.md`](qwen3/README.md). Upstream's pinned KV
pool is reachable at launch with `-e TENSORFOLD_KV_POOL_GIB=<n>`.

## Qwen 4x

| Recipe                                  | Flags   | C1 t/s |  Size |  Mem | TP | Model Cards                                                    |
|:----------------------------------------|:--------|-------:|------:|-----:|---:|:---------------------------------------------------------------|
| qwen3.8-flash-next-nvfp4-labquant-sglang | 🌲🚀👀 |   40.3 | 106GB | 0.80 |  2 | [Model][local-inference-lab/Qwen3.8-Flash-Next-NVFP4]          |
| qwen3.8-flash-next-nvfp4-solo-vllm-b12x | 🌲     |   33.9 | 135GB | 0.80 |  1 | [Model][local-inference-lab/Qwen3.8-Flash-Next-NVFP4] — **solo TP=1, PLE table streamed from disk** |

The lane ships **exactly two** production recipes — the fastest **TP=1** and the fastest **TP=2**,
both on the `local-inference-lab` export; the other four arms measured in the 2026-10-14 window were
archived to [`../attic/qwen4/arms/`](../attic/qwen4/arms/) with a manifest row (two labquant TP=2
variants tied with the survivor at C1 but carrying an unverified 1M seat or a larger pool; the slower
RadixArk reference; and the SGLang solo route, ~42% below the vLLM solo). See
[`qwen4/README.md`](qwen4/README.md) for the cut table, the receipts and the lane rationale.

_C1 t/s is single-stream (concurrency 1, depth 0) decode from the lane's measurement record: the
**TP=2** survivor (labquant balanced base, 262k context) reads **40.3 ± 1.9 @ d0 / 43.3 ± 2.7 @
d8192**; the **TP=1** survivor (solo vLLM, `VLLM_PLE_TABLE_MEMORY=disk`) reads **33.9 ± 1.7 @ d0 /
34.4 ± 1.3 @ d8192**. The TP=2 pair peaks at ~91 tok/s aggregate at k=16/d=8192 and falls ~38% at
k=24. **Read the labquant row with its caveat:** its checkpoint is more aggressively quantised (MXFP8
attention/GDN, FP8 PLE n-gram table unpacked to fp8 by a required mod) and its W3 battery reads
essentially equal to the RadixArk reference on the tasks both ran — but the battery is a
gross-regression instrument, not an accuracy certificate. **Vision now serves** on the re-pinned
step-5500 revision: the export ships the vision tower BF16 and lists `model.visual.*` in
`quantization_config.ignore`, so the TP=2 arm is no longer text-only._

## IFM K2-Horizon

| Recipe                                    | Flags  | C1 t/s |  Size |  Mem | TP | Model Cards                                                    |
|:------------------------------------------|:-------|-------:|------:|-----:|---:|:---------------------------------------------------------------|
| k2-horizon-0.9b-bf16-sglang               | ✨🚀🤏🧠🔧 |   77.6 |  2GB | 0.85 |  1 | [Model][IFM/K2-Horizon-0.9B]                                   |
| k2-horizon-7b-fp8-uno-sglang              | 🚀🤏🧠🔧🦾 |   32.4 | 11GB | 0.82 |  1 | [Model][IFM/K2-Horizon-7B-FP8] — **UNO spec decode, fastest** |

_Native SGLang on GB10. C1 t/s measured at concurrency 1, depth 0
(`benchmarking/decode-triage.yaml`); the 7B figure is the mean over several clean
boots from the 2026-10-09 campaign. The shipped 7B arm is **UNO spec decode
(32.4 t/s, +52 % over plain)** — the lane's fastest at single-stream and, once
`max_num_seqs` is raised off the old 8, at aggregate concurrency too (145.5 t/s at
c=8). It needs two mods — one fetches the `K2-Horizon-7B-Uno` draft adapter, one
relaxes SGLang's `fa3`-only UNO gate so `--attention-backend fa4` can serve on
GB10 — and it is accuracy-lossless on the shared instrument. The plain 7B and
NGRAM arms were retired to [`../attic/ifm/arms/`](../attic/ifm/arms/) (plain is
dominated by both spec arms; NGRAM is slower at d0 and at c=8, its only edge, at
d8k, falling inside the lane's inter-boot noise floor). The lane also carries
**measured accuracy** for both dense models (house / gsm8k / arc) and a
`page-size` / `fa4` / cuda-graph arm sweep — see [`ifm/README.md`](ifm/README.md).
The withdrawn 36B-A4B sub-lane (4 arms + the `patch-sglang-k2-horizon-fp8` gate mod)
is archived under [`../attic/ifm/`](../attic/ifm/)._

## GLM 5.3

**No shipped recipe** — the lane ships TensorFold **runbook notes** ([`glm/README.md`](glm/README.md)). Its one recipe, `glm-5.3-flash-nvfp4-dflash-vllm`, was **archived to [`../attic/glm/`](../attic/glm/ARMS-MANIFEST.md) 2026-10-13** (owner decision) as a **proven-negative on the pinned public image**: five boots on `.30-.33` all died in the container serve log (the image's SM120 sparse-MLA backend forces the `fp8_ds_mla` KV layout, whose `concat_and_cache_mla` needs a 64-dim RoPE tail while the checkpoint is NoPE MLA; DFlash2 also needs an absent `SupportsEagle3`). The boot-verified serving lines are our `bertholomus` EXL3 3.0bpw TP4 (C1 35.7 t/s @ d0, MTP-3 acceptance 63.4 %) and the MiaAI-Lab Flash EXL3 4bpw launcher at TP=2 (C1 58.5/60.5, quality 37/37, needle 2/2 at 1M), TP=3 (C1 65.4/65.1) and TP=4 (C1 98.4 t/s @ d0, DFlash2 acceptance 76.6 %). The DFlash2 drafter is CC BY-NC-ND (acceptable for this non-commercial cluster).

## Decision

| Recipe                      | Flags | Accuracy | Size |             API | TP | Model Cards                            |
|:----------------------------|:------|---------:|-----:|----------------:|---:|:---------------------------------------|
| jev-9b-decision-vllm        | 🤏🚮    |    67.0% | 18GB | /v1/completions |  1 | [Model][autotrust/JEV-9B]              |
| clef-flash-decision-sglang  | 🤏🚮    |    70.3% | 19GB |   /v1/systemone |  1 | [Model][Cloudflare/clef-flash]         |
| kai-0.6b-decision-vllm-srun | 🤏🖥🚮  |    47.5% |  2GB |   /v1/systemone |  1 | [Model][vllm-sr/Decision-2.0-Kai-0.6B] |
| sol-2b-decision-vllm-srun   | 🤏🖥🚮  |      55% |  5GB |   /v1/systemone |  1 | [Model][vllm-sr/Decision-2.0-Sol-2B]   |

## Explore

| Recipe                                          | Flags | C1 t/s |  Size |  Mem | TP | Model Cards                                                                 |
|:------------------------------------------------|:------|-------:|------:|-----:|---:|:----------------------------------------------------------------------------|
| ling-3.0-flash-int4-dspark-sglang                | 🧠    |   45.5 | 154GB | 0.80 |  1 | [Model][inclusionAI/Ling-3.0-flash-int4] [Draft][inclusionAI/Ling-3.0-flash-dspark] — **boot-verified, house battery 37/37; 262k needle-verified at mem-fraction 0.80** |
| kolibri-1-78b-fp8-vllm                           | ✨🧠🔧 |   47.3 |  74GB | 0.78 |  1 | [Model][Aleph-Alpha/Kolibri-1] — **boot-verified, house battery 36/37 (37/37 union across token budgets)** |
| poolside-laguna-xs-2.1-nvfp4-dflash-vllm        | ✨🧠🔧 |   57.4 | 22.5GB | 0.55 |  1 | [Model][poolside/Laguna-XS-2.1-NVFP4] [Draft][poolside/Laguna-XS-2.1-DFlash] — **boot-verified 2026-10-14, house battery 36/37; 262k pool-verified, needle probe open** |
| poolside-laguna-s-2.1-nvfp4-dflash-vllm         | ✨🧠🔧 |   20.5 |  96GB | 0.85 |  1 | [Model][poolside/Laguna-S-2.1-NVFP4] [Draft][poolside/Laguna-S-2.1-DFlash-NVFP4] — **boot-verified; 120k capped-context single-tenant arm, battery 32/37** |
| humanizer-12b-vllm                              | 🐢     |      — |  24GB | 0.85 |  1 | [Model][jialinyyzz/humanizer] — **text-rewriting arm, `/v1/completions` only (no chat template), off the lane's reasoning/tool brief** |
| qwen-image-2.1-turbo-7b-bf16-diffusers-script             | 🐢     |      — |  33GB |    — |  1 | [Model][Qwen/Qwen-Image-2.1-Turbo] — **text-to-image + editing** under a diffusers script launcher (no sglang/vLLM engine); **NON-COMMERCIAL licence, banner-marked eval-only**; boot-verified 2026-10-14, ~11.4 s/image @1024²/8-step |

Two selected 2026-10-13 by the **owner's criterion for this lane — accuracy decides, with preference for smaller and faster models** (supersedes the registry's node-count→speed default, which had ranked this lane on speed). Rank 1 is **Ling** (37/37, the accuracy champion); rank 2 is **Kolibri** (36/37 @4096, a 37/37 union — the lone miss is a thinking-budget truncation — so a near-tie on the deciding factor, and it wins the stated preference: 74 GB vs Ling's 154 GB, 47.3 vs 45.5 t/s). **Archived** to [`attic/explore/`](../attic/explore/ARMS-MANIFEST.md): `nemotron-3.5-lightning-30b-nvfp4-dspark-vllm` (the fastest measured arm, 77.7 t/s, and the smallest at 21 GB — but 33/37, the lane's lowest accuracy) and `nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm` (a variant of it: 72.2 t/s, util 0.91).

_Five further arms were built on 2026-10-14 and are recorded here without joining that two-arm
selection: the queued **Poolside Laguna-XS-2.1** (faster and smaller than both kept arms but one
genuine battery miss below Kolibri), **Laguna-S-2.1** (a capped-context 120k single-tenant entry),
the off-brief **humanizer-12b** text-rewriting arm, and the two **media-gen** arms outside the lane's
brief — **Qwen-Image-2.1-Turbo** (image; non-commercial licence, shipped banner-marked eval-only) and
**LTX-2.5** (video+audio; gated, shipped as a [runbook](explore/ltx-2.5-runbook/README.md)). Their
receipts are in [`explore/README.md`](explore/README.md)._

_Nemotron-262k (archived 2026-10-13): 1 node, 20.8 GB NVFP4 weights. **BOOT-VERIFIED 2026-10-11** (TP=1) with the
DSpark draft engaged (acceptance length 3.67, 88.9% rate). **Measured C1: 77.7 t/s @ d0** (σ 9.8, n=5)
and 76.3 @ d8k (σ 26.0) on `benchmarking/decode-triage.yaml` — below the 93-96 t/s third-party figure on
this node, so quote ours. Quality: **33/37** house battery. Lane research:
[`explore/EXPLORE-MODELS-RESEARCH.md`](explore/EXPLORE-MODELS-RESEARCH.md)._

**Nemotron 1M arm (2026-10-12 — archived 2026-10-13):** the card's 1M-context claim confirmed on GB10 — boots at the
card's util 0.91 (KV 87.27 GiB → 21.3M tokens), 1M-window needle **PASS** at depths 10/50/90
(~982k-token server-counted prompts, Nemotron-calibrated 3.8590 chars/token). Measured C1
**72.2 t/s @ d0** (σ 15.1, n=5) vs the 262k recipe's 77.7. Swap-risk caveat: ~1 GiB free with
2.05 GiB swap allocated during 1M prefills but zero swap-in/out under needle load; sustained
multi-tenant load untested.

**Ling 262k closure (2026-10-12):** mem-fraction ladder boots 0.80 first rung — KV pool
313,752 tokens (0.75 measured 176,203); 262k-window needle **PASS** at depths 10/50/90
(~256.6k-token prompts); 4-way concurrency smoke clean, zero OOM/retract. 0.87 stays the
documented ceiling.

**Kolibri-1 (2026-10-12):** first boot of the 78.1B/3.46B MoE on stock vLLM 0.29 + the vendor
pure-Python plugin (`mods/install-kolibri-plugin`). C1 **47.3 t/s @ d0** (σ 0.10, n=5), battery
**36/37** at `--max-tokens 4096` reproduced twice, 37/37 union with the default-384 run — the
lone `needle-1` failure is thinking-budget truncation, not knowledge. **KEPT**: near-tie accuracy
(37/37 union) and it wins the owner's stated preference (74 GB, 47.3 t/s).

## Cybersec

Red-team / security-research arms — **abliterated (refusal-removed) and cybersecurity-unlocked**
checkpoints. A *capability* lane: every arm answers prompts its base model refuses, and the operator
supplies the guardrails. **All five are gated on the Hub (`gated: auto`)** — each runner node needs an
`HF_TOKEN` whose user has accepted that repo's release (arms 2 and 5 pull two gated repos each; both
are *overlays* that ship a chat template / sidecar and no weights). Lane guide:
[`cybersec/README.md`](cybersec/README.md) + [`cybersec/AGENTS.md`](cybersec/AGENTS.md).

| Recipe                                                     | Flags     | C1 t/s |  Size |  Mem | TP | Model Cards                                                     |
|:-----------------------------------------------------------|:----------|-------:|------:|-----:|---:|:----------------------------------------------------------------|
| qwen3.8-27b-uncensored-nvfp4-sglang                        | 🚀👀🏴    |   10.2 |  25GB | 0.85 |  1 | [Model][orcarouter/Qwen3.8-27B-Uncensored-NVFP4] — **positive**, boots, battery 37/37 |
| qwen3.8-27b-ablit-cyber-unlock-nvfp4-dflash2-sglang        | 🚀👀🏴    |   33.3 |  21GB | 0.85 |  1 | [Model][sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4] [Draft][incoai/Qwen3.8-27B-DFlash2] — **positive** (AEON body + drowzeys cyber template), battery 37/37 |
| deepseek-v4.1-flash-abliterated-cyber-tp2-tensorfold-sglang | 🚀🚚1🏴  |   63.7 | 197GB |    — |  2 | [Model][drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed] — **positive** (stock Mia EXL3 pack + `attn.wo_b` sidecar graft), battery 36/37, 1M ctx |
| nex-n2.5-mini-uncensored-nvfp4-sglang                      | 🚀👀🏴💀  |      — |  24GB | 0.85 |  1 | [Model][orcarouter/Nex-N2.5-mini-Uncensored-NVFP4] — **negative**: NaN sample-time logits under SGLang; vLLM route blocked on image distribution |
| qwen3.8-flash-next-uncensored-nvfp4-sglang                 | 🚀👀🏴💀  |      — | 184GB | 0.85 |  2 | [Model][orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4] — **negative**: SGLang's compressed-tensors loader refuses the export's scheme; vLLM is the next step |

_C1 t/s is single-stream (concurrency 1, depth 0) decode from `benchmarking/decode-triage.yaml`. The
three positives serve their repo id at `GET /v1/models`; the two negatives are documented SGLang engine
gaps, not memory or distribution failures — see [`cybersec/AGENTS.md`](cybersec/AGENTS.md) §8. Sizes are
measured on-disk weight bytes (arm 5 = the stock pack; its 682 MB sidecar is grafted on at launch). No
weights are redistributed by this registry._

# Model Flags

| Flag | Tag           | Description                              |
|:-----|:--------------|:-----------------------------------------|
| ✨   | official      | Uses official weights                    |
| 🌲   | lcg_favorite  | Little Cedar Group:tm: Favorite          |
| 🚀   | fast          | C1 Fast (>= 50t/s avg)                   |
| 🐢   | slow          | C1 Slow (< 40t/s avg)                    |
| 🚚   | large_context | Large context (>= 512k tokens)           |
| 🔧   | tools         | Excellent tool use                       |
| 🧠   | reasoning     | Excellent reasoning capability           |
| 🦾   | agent         | Excellent agentic capability             |
| ⚖   | judge         | Judgement model                          |
| 🚮   | classifier    | Classification model                     |
| 🖥   | cpu           | CPU-only runtime model                   |
| 🤏   | smol          | Small model                              |
| 1    | single_user   | Low concurrency, single-user recommended |
| 👀   | vision        | Model has vision capability              |
| 👂   | listening     | Model has listening capability           |
| 🗺   | world         | Model has world-aware capability         |
| 👄   | speech        | Model has speech generation capability   |
| 📸   | image         | Model has image generation capability    |
| 🎥   | video         | Model has video generation capability    |
| 🎼   | audio         | Model has audio generation capability    |
| 📶   | embedding     | Model has embedding capability           |
| 🔃   | reranking     | Model has reranking capability           |
| 🏴   | uncensored    | Uncensored model                         |
| 🚩   | dangerous     | Dangerous and may crash your Sparks!     |    
| 💀   | broken        | Currently broken                         |

_Flags indicate characteristics of the model and are set in the recipe metadata._

# Notes

## vLLM custom-command templates: hardcode the snapshot path (sparkrun 0.4.0-alpha)

For a vLLM recipe whose `command:` is a template, sparkrun's render resolves `{model}` to the
**declared repo id** (not the prepared snapshot path) and **strips `--revision`** from the template —
then its own serve-command validator demands a path or `--revision=<prepared-sha>` token and refuses
the launch (`serve command does not consume the validated model`) after the model has already been
distributed. `{model_revision}` does not survive either. The pattern that boots (used by the qwen3
coder, decision, explore and glm5 lanes):

```yaml
model_revision: <sha>                      # keeps distribution pinned
command: >
  vllm serve
  /cache/huggingface/hub/models--<org>--<name>/snapshots/<sha>
  --served-model-name <org>/<name>         # so clients keep the HF id
  --revision=<sha>                         # the `=` spelling is the one the validator accepts
```

The in-container path is deterministic: `${HF_HUB_CACHE}/models--<org>--<name>/snapshots/<sha>` with
`--` for `/` in the repo id. The sglang runtime is unaffected (it renders the path and keeps
`--revision`). Three related traps:

1. A `defaults:` key referenced by the command but **missing** renders as a literal into the serve
   line and only dies at the engine — guarded by `tests/test_recipe_placeholder_resolution.py`.
2. vLLM's speculative-config field is **`model`**, not `draft_model` — sparkrun's draft binding reads
   the same key.
3. The speculative config must live in **`defaults:`** (`speculative_config: '<json>'`, referenced as
   `'{speculative_config}'` in the command), not inline: only then does sparkrun add the draft repo to
   the distribution set and inject the prepared revision. An inline literal leaves the drafter
   undistributed and the offline engine dies resolving it — measured on the Nemotron boot 2026-10-11.
   Inside that JSON, use **literals**: two placeholder behaviours were observed — inside a defaults
   VALUE nothing resolves (the raw token survives into sparkrun's own `json.loads` and kills the
   launch), and inside the command template an *unquoted* placeholder resolves but a *quoted* one
   does not (braces inside quoted JSON blobs are masked). The boot-proven form is literals in the
   defaults JSON; comments never go inside a folded `command:` block (a `>` scalar keeps them as
   literal text and the shell-comment rule then eats every following flag).
   sglang is again unaffected (`speculative_draft_model` in defaults is the shipped pattern).

## sglang custom-command templates: declare the served model id

An sglang recipe whose `command:` template writes `--served-model-name {model}` does **not** serve
the repo id on a real launch: sparkrun rebinds every `{model}` occurrence to the prepared on-disk
snapshot path (`models/runtime.py::bind_runtime_models`), so the engine advertises
`/cache/huggingface/hub/models--<org>--<name>/snapshots/<sha>` as its `model` id — wrong for every
client, the proxy and any benchmark that sends the HF id. `-n` still prints the repo id (bindings
exist only on a launch), so a dry run cannot show this. The same defect with the flag omitted: a
`command:`-templated arm with no `--served-model-name` at all serves the `--model-path` value.

Declare the literal and render the flag from it (sparkrun's own prescription —
`core/validation.py` suggests exactly this when it sees a hardcoded flag):

```yaml
defaults:
  served_model_name: <org>/<name>          # the upstream repo id
command: >
  --model-path {model}
  --served-model-name {served_model_name}
```

Both lines are required together: a declared key the command never references is rejected by
`tests/test_recipe_placeholder_resolution.py::InertDefaults`, and the runtime's own append only
fires when the flag is absent (`runtimes/base.py`). An arm whose `--model-path` is a mod-built tree
rather than the snapshot (labquant) also needs `--revision {model_revision}` — the launch validator
requires a revision token once the prepared path no longer appears in the command. The two ds4 arms
are the deliberate exception: their in-container launchers normalize a path back to the repo id
(`tests/test_ds4_recipes.py` guards it). A fix is not verified until a live boot's `GET /v1/models`
returns the repo id.

The knapcio TP4 arm pins `model_revision:` without spelling `--revision`, so `validate` warns
`unpinned-model-revision` there: its launcher is handed the prepared snapshot path through `{model}`
and never resolves a ref itself. That warning is expected for that arm, not a defect — the mechanism
is in `ds4/AGENTS.md` §5.

Per-family agent guides: the Qwen3.8-Flash-Next lane carries its own
[`qwen4/AGENTS.md`](qwen4/AGENTS.md) (state, constraints, workstream plan, runbook) and
[`qwen4/README.md`](qwen4/README.md) (the recipe/lane summary), with `../attic/qwen4/NOTES.md` (working notes).
Read those before starting work in that directory. Archived arms and the lane's research record,
journal, and coordination ledger live under [`../attic/qwen4/`](../attic/qwen4/).

The DeepSeek V4.1-Flash lanes are documented in [`ds4/README.md`](ds4/README.md) (user guide)
and [`ds4/AGENTS.md`](ds4/AGENTS.md) (design, boot gates, guards, and measurement discipline for
both the knapcio TP=4 and TensorFold TP=2 lanes); the retired vLLM/EXL3 lane is under
[`../attic/ds4/`](../attic/ds4/).


The IFM K2-Horizon lanes are documented in [`ifm/README.md`](ifm/README.md) (recipe
summary) and [`ifm/AGENTS.md`](ifm/AGENTS.md) (constraints, falsified claims, guards,
and the validation ritual for the `0.9B` / `7B-FP8` set); the
research record and journals are git-ignored working files beside them.

The Ornith 1.5 lanes are documented in [`ornith/README.md`](ornith/README.md) (per-recipe wiring,
caveats, and the three archived arms) and [`ornith/AGENTS.md`](ornith/AGENTS.md) (lane state,
constraints, the A/B negative result, and the validation ritual); the lane's guards are in
`tests/test_ornith_recipes.py` (O1–O5).

The Qwen3 lane is documented in [`qwen3/README.md`](qwen3/README.md) (recipe summary) and
[`qwen3/AGENTS.md`](qwen3/AGENTS.md) (model thesis, tunable rationale, negative results, and the
validation ritual); the lane's research record — including the no-spec control recipe, the measured
DSpark arm, and the depth/SSM/queue threads — moved to [`../attic/qwen3/`](../attic/qwen3/) on
2026-10-11 with a manifest mapping its `§N` cite forms.

# References

* https://spark-arena.com

<!-- Links -->
[RadixArk/Qwen3.8-27B-NVFP4]: https://huggingface.co/RadixArk/Qwen3.8-27B-NVFP4
[local-inference-lab/Qwen3.8-Flash-Next-NVFP4]: https://huggingface.co/local-inference-lab/Qwen3.8-Flash-Next-NVFP4
[incoai/Qwen3.8-27B-DFlash2]: https://huggingface.co/incoai/Qwen3.8-27B-DFlash2
[Qwen/Qwen3-VL-Embedding-2B]: https://huggingface.co/Qwen/Qwen3-VL-Embedding-2B
[gonuit/Qwen3-VL-Embedding-8B-AWQ-4bit]: https://huggingface.co/gonuit/Qwen3-VL-Embedding-8B-AWQ-4bit
[Qwen/Qwen3-VL-Reranker-2B]: https://huggingface.co/Qwen/Qwen3-VL-Reranker-2B
[Qwen/Qwen3-VL-Reranker-8B]: https://huggingface.co/Qwen/Qwen3-VL-Reranker-8B
[littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft]: https://huggingface.co/littlecedar/Ornith-1.5-397B-NVFP4-MTP-Graft
[ornith-ai/Ornith-1.5-35B-A3B-NVFP4]: https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B-NVFP4
[jzinno/Ornith-1.5-35B-A3B-DFlash2]: https://huggingface.co/jzinno/Ornith-1.5-35B-A3B-DFlash2
[IFM/K2-Horizon-0.9B]: https://huggingface.co/IFM/K2-Horizon-0.9B
[IFM/K2-Horizon-7B-FP8]: https://huggingface.co/IFM/K2-Horizon-7B-FP8
[Intel/Qwen3-Coder-Next-int4-AutoRound]: https://huggingface.co/Intel/Qwen3-Coder-Next-int4-AutoRound
[littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram]: https://huggingface.co/littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram
[autotrust/JEV-9B]: https://huggingface.co/autotrust/JEV-9B
[Cloudflare/clef-flash]: https://huggingface.co/Cloudflare/clef-flash
[inclusionAI/Ling-3.0-flash-int4]: https://huggingface.co/inclusionAI/Ling-3.0-flash-int4
[inclusionAI/Ling-3.0-flash-dspark]: https://huggingface.co/inclusionAI/Ling-3.0-flash-dspark
[vllm-sr/Decision-2.0-Kai-0.6B]: https://huggingface.co/vllm-sr/Decision-2.0-Kai-0.6B
[vllm-sr/Decision-2.0-Sol-2B]: https://huggingface.co/vllm-sr/Decision-2.0-Sol-2B
[Aleph-Alpha/Kolibri-1]: https://huggingface.co/Aleph-Alpha/Kolibri-1
[deepseek-ai/DeepSeek-V4.1-Flash]: https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash
[orcarouter/Qwen3.8-27B-Uncensored-NVFP4]: https://huggingface.co/orcarouter/Qwen3.8-27B-Uncensored-NVFP4
[sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4]: https://huggingface.co/sakamakismile/Qwen3.8-27B-AEON-ULTIMATE-UNCENSORED-NVFP4
[orcarouter/Nex-N2.5-mini-Uncensored-NVFP4]: https://huggingface.co/orcarouter/Nex-N2.5-mini-Uncensored-NVFP4
[orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4]: https://huggingface.co/orcarouter/Qwen3.8-Flash-Next-Uncensored-NVFP4
[drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed]: https://huggingface.co/drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed
[poolside/Laguna-XS-2.1-NVFP4]: https://huggingface.co/poolside/Laguna-XS-2.1-NVFP4
[poolside/Laguna-XS-2.1-DFlash]: https://huggingface.co/poolside/Laguna-XS-2.1-DFlash
[poolside/Laguna-S-2.1-NVFP4]: https://huggingface.co/poolside/Laguna-S-2.1-NVFP4
[poolside/Laguna-S-2.1-DFlash-NVFP4]: https://huggingface.co/poolside/Laguna-S-2.1-DFlash-NVFP4
[jialinyyzz/humanizer]: https://huggingface.co/jialinyyzz/humanizer
[Qwen/Qwen-Image-2.1-Turbo]: https://huggingface.co/Qwen/Qwen-Image-2.1-Turbo
[ornith-ai/Ornith-1.5-9B-NVFP4]: https://huggingface.co/ornith-ai/Ornith-1.5-9B-NVFP4
[ornith-ai/Ornith-1.5-9B-DFlash]: https://huggingface.co/ornith-ai/Ornith-1.5-9B-DFlash

[TensorFold/Qwen3.8-27B-MLX-4bit]: https://huggingface.co/TensorFold/Qwen3.8-27B-MLX-4bit
[z-lab/Qwen3.8-27B-DFlash2]: https://huggingface.co/z-lab/Qwen3.8-27B-DFlash2