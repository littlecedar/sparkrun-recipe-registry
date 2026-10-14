# Primary README archive

Registry-level archive of the research and lane-state prose removed from [`../recipes/README.md`](../recipes/README.md) on 2026-10-14 when that file was reduced to a pure index of shipped recipes; per-lane detail now lives in each lane's own `README.md` and `attic/` directory (the command-template rules and the per-family agent-guide paragraphs moved to [`../recipes/MECHANICS.md`](../recipes/MECHANICS.md) instead).

**Link note.** The quoted blocks below were written for `recipes/README.md`, so their relative links
are `recipes/`-relative (e.g. `qwen4/README.md`) and do not resolve from this file's location. Paths
have been swapped where a target moved to an `attic/` directory; for the rest, resolve them from
`recipes/`.

## Qwen 3x

The C1 column's `50` for dflash2 is the measured **c=2 aggregate** (tg=128, pp=256), not a
single-stream number — the recipe's own decode-only measurement is 33.8 t/s at c=1.

The third Qwen 3x arm, added 2026-10-14: `qwen3.8-27b-mlx4bit-tensorfold-sglang` is Mia's AI Lab's
**TensorFold** route — a foreign engine behind the `runtime: sglang` shim, one DGX Spark (TP=1),
MLX affine-4-bit weights plus the DFlash2 drafter, FP8 KV cache and vision — on a digest-pinned
public image. **Booted and measured 2026-10-14** on `.30` (`benchmarking/decode-triage.yaml`):
**41.3 ± 4.0 t/s @ d0** and 41.7 ± 2.4 @ d8192, house battery **37/37** — above the DFlash2 arm's
33.8 at the same c=1. There is no `Mem` knob (the engine sizes its own budget); upstream's own
numbers and the launch caveats are in [`qwen3/README.md`](qwen3/README.md). Upstream's pinned KV
pool is reachable at launch with `-e TENSORFOLD_KV_POOL_GIB=<n>`.

## Qwen 4x

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

## Explore

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
[`attic/explore/EXPLORE-MODELS-RESEARCH.md`](attic/explore/EXPLORE-MODELS-RESEARCH.md)._

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
pure-Python plugin (`recipes/explore/mods/install-kolibri-plugin`). C1 **47.3 t/s @ d0** (σ 0.10, n=5), battery
**36/37** at `--max-tokens 4096` reproduced twice, 37/37 union with the default-384 run — the
lone `needle-1` failure is thinking-budget truncation, not knowledge. **KEPT**: near-tie accuracy
(37/37 union) and it wins the owner's stated preference (74 GB, 47.3 t/s).

## Cybersec

Red-team / security-research arms — **abliterated (refusal-removed) and cybersecurity-unlocked**
checkpoints. A *capability* lane: every arm answers prompts its base model refuses, and the operator
supplies the guardrails. **All five are gated on the Hub (`gated: auto`)** — each runner node needs an
`HF_TOKEN` whose user has accepted that repo's release (arms 2 and 5 pull two gated repos each; both
are *overlays* that ship a chat template / sidecar and no weights). Lane guide:
[`cybersec/README.md`](cybersec/README.md) + [`attic/cybersec/AGENTS.md`](../attic/cybersec/AGENTS.md).

_C1 t/s is single-stream (concurrency 1, depth 0) decode from `benchmarking/decode-triage.yaml`. The
three positives serve their repo id at `GET /v1/models`; the two negatives are documented SGLang engine
gaps, not memory or distribution failures — see [`attic/cybersec/AGENTS.md`](../attic/cybersec/AGENTS.md) §8. Sizes are
measured on-disk weight bytes (arm 5 = the stock pack; its 682 MB sidecar is grafted on at launch). No
weights are redistributed by this registry._
