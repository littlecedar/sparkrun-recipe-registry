# GLM-5.3 / GLM-5.3-Flash on DGX Spark: checkpoint, engine & topology selection

**Scope:** the GLM-5.3 lane of this registry — which checkpoints, engines, node counts, context and
draft strategy to build for the 4× NVIDIA DGX Spark (GB10) cluster.
**Status:** rewritten 2026-10-10. Supersedes the 2026-09-12 version, which compared only two 753B
NVFP4 checkpoints and got three load-bearing facts wrong (see [What changed](#what-changed)).

**Evidence vocabulary (house rule).** **VERIFIED** — read from a primary artifact (a pinned repo
file, a live Hub listing, a boot log) or measured. **LIKELY** — strong secondary evidence.
**SPECULATIVE** — reasoning without a source; do not build on it. Every claim below that came from
an external repo carries a pin; nothing here has been measured on our hardware.

---

## What changed

| 2026-09-12 claim | Reality (VERIFIED 2026-10-10) |
|---|---|
| incoai ≈142 GB, RadixArk ≈134 GB, "listing estimates" | incoai is **87 safetensors ≈ 463 GB**; RadixArk is **47 shards ≈ 465 GB**. Not estimates — wrong by ~3.2×. |
| "Both fit comfortably within a single DGX Spark (128 GB)" | 433–465 GB cannot fit 128 GB unified. The 753B NVFP4 lane is **TP4-only on our nodes**, and the vendor card publishes **TP=8**. |
| RadixArk = "llama.cpp / Ollama / GGUF, community fork, local prototyping" | RadixArk is an **NVFP4 W4A4 export in NVIDIA Model-Optimizer format, SGLang-served**, validated on B300. The "backend" differentiator collapses. |

Everything else the old doc asserted about kernels, KV size and licence text is folded in below or
replaced. The new material (a second model line, two more checkpoints, a third engine, spec-decode,
KV math, receipt discipline) comes from two `bertholomus/*` sources pinned at the bottom.

---

## The two model lines

Both are Z.ai MoE models at 1M native context. They are **different families with different
licences** — do not pool them.

| | **GLM-5.3** (full) | **GLM-5.3-Flash** |
|---|---|---|
| HF class | `GlmMoeDsaForCausalLM` | `Glm5NextForConditionalGeneration` |
| Params / layers | 753B, 78 layers + MTP | smaller; hybrid `linear_attention` + `deepseek_sparse_attention` |
| `hidden_size` | 6144 | 4096 |
| Modalities | text-only | **multimodal** (`image_token_id` 154854) |
| MTP | bf16 | kept **FP8** |
| Licence | **Z.AI GLM-5.3 Licence** (permissive; MaaS >$10B security-review clause) | **MIT** |

Base releases for the full model: `zai-org/GLM-5.3` (FP8, 141 shards ≈ 756 GB — what the NVFP4
quants compare against) and `zai-org/GLM-5.3-BF16` (1,507 GB).

---

## The four checkpoints

| Checkpoint | Model | Quant | Size | Engine | Licence | Pin |
|---|---|---|---|---|---|---|
| [`incoai/GLM-5.3-NVFP4`](https://huggingface.co/incoai/GLM-5.3-NVFP4) | 5.3 full | NVFP4 | 87 files ≈ **463 GB** | vLLM / SGLang | Z.AI | — |
| [`RadixArk/GLM-5.3-NVFP4`](https://huggingface.co/RadixArk/GLM-5.3-NVFP4) | 5.3 full | NVFP4 W4A4 (Model-Optimizer) | 47 shards ≈ **465 GB** | SGLang | Z.AI | — |
| [`RedHatAI/GLM-5.3-Flash-NVFP4`](https://huggingface.co/RedHatAI/GLM-5.3-Flash-NVFP4) | 5.3-Flash | NVFP4 experts + FP8 MTP | 21 files / **197,881,157,135 B** | vLLM (SM121/GB10) | MIT card / no repo licence metadata | rev `36c184c6` |
| [`bertholomus/GLM-5.3-EXL3-3.0bpw`](https://huggingface.co/bertholomus/GLM-5.3-EXL3-3.0bpw) | 5.3 full | EXL3 3.0 bpw (exllamav3 1.5.3) | 39 shards ≈ **292.7 GB** | TensorFold | Z.AI | — |

`incoai`'s own accuracy table (FP8 vs NVFP4): GPQA 91.1/91.2, AIME-2025 94.3/95.1, MATH-500
95.6/95.2, HLE 35.9/35.2, AA-LCR 73.6/73.0 — **near-parity**, the honest counterweight to "FP4 is the
native fast path, not a compromise" (that "native" claim is a kernel statement, not a measured
accuracy one).

---

## Topology arithmetic (why node count decides the lane)

Weights must share the 128 GB unified pool with KV, activations and OS.

| Checkpoint | TP4 | TP8 | Verdict on our 4 nodes |
|---|---|---|---|
| incoai / RadixArk 753B NVFP4 | ~108–116 GiB weights/rank | ~54–58 GiB/rank | **TP8 per vendor**; a TP4 run leaves ~12–20 GB — tiny KV, low concurrency |
| GLM-5.3-Flash NVFP4 | **~49.5 GiB/rank** | — | **fits TP4 with real KV headroom** (repo B qualified it at 24 GiB/rank KV) |
| GLM-5.3 EXL3 3.0bpw | **69.86 GiB weights/rank** | — | TP4 works (~258K-token cache at 96,640 B/slot); the full-model lane that fits today |

So: the **Flash line is the only family we can serve well on 4 nodes at 1M with usable concurrency**;
the full-model quants want 8 nodes unless you accept a small KV. This is the opposite of the old
doc's conclusion.

---

## Engines and spec-decode

| Lane | Engine | Draft | Licence trap |
|---|---|---|---|
| EXL3 (repo A) | TensorFold 0.6.0 + branch `glm-dsa-tp4` @ `ddfad35` | GLM-5.3's **own MTP, depth 3** (`--mtp-drafts 3`) | none — no external drafter |
| Flash NVFP4 (repo B) | vLLM (SM121/GB10) | **DFlash2 depth 7** (`incoai/GLM-5.3-Flash-DFlash2`, 2.3 GB) | **CC BY-NC-ND 4.0** — non-commercial |
| incoai 753B | vLLM / SGLang | DFlash2 (`incoai/GLM-5.3-DFlash2`) | DFlash2 terms |
| RadixArk 753B | SGLang | EAGLE from the BF16 MTP layer | — |

The full-model DFlash2 drafter is CC BY-NC-ND: **a commercially-shipped lane must use MTP/EAGLE or
accept non-commercial terms.** Both upstream sources flag this independently.

---

## Two concrete serving configurations (to write a recipe from)

**A — EXL3 3.0 bpw on TensorFold, TP4** (repo A). Env: `TF_GLM_KV=q5`, `TF_GLM_EMBED_SPLIT=1`,
`TF_GLM_MTP_REUSE=2`, and for the 1M arm `TF_GLM_DCP=4` + `TF_GLM_EXTENTS=1`. Serve line:
`tensorfold serve … --tp 4 --rank R --master … --master-port 29661 --context <ctx> --mtp-drafts 3
`--parallel 4`. Measured: **82 t/s aggregate** (4 code streams, replicated cache), **~64 t/s** (1M window, DCP4), single-stream **33–39 t/s**, **needle found at 1,039,064 tokens**, prefill ~400 t/s at
32K, TTFT ~76 s at ~31K. Quality: KL 0.109 vs BF16, top-1 90.2 %, ppl +5.9 %. No vision.

**B — GLM-5.3-Flash NVFP4 on vLLM, TP4** (repo B, machine-readable in its `runtime-formula.json`):
`--tensor-parallel-size 4`, `max_model_len 1,048,576`, `max_num_seqs 6`, `max_num_batched_tokens
8,192`, **block size 2,304**, KV `fp8_e4m3` at `25,769,803,776` B/rank (24 GiB), `gpu_memory_utilization
0.85`, **eager**, MoE `marlin`, `--tool-call-parser glm47 --reasoning-parser glm45`, spec `dflash`
depth 7. Receipt: 21 files / 197,881,157,135 B; **strongest exact retrieval 260,066 tokens**, 2×
240,073 concurrent exact, 6 bounded concurrent generations.

**KV ladder (repo B, one variable):** 16 / 20 / 24 GiB per rank → 2,622,494 / 3,245,990 / 3,895,606
reported KV tokens → 2.5 / 3.1 / 3.72× max-length concurrency; **only the 24 GiB rung passed every
gate** (the reasoning gate is sampling-sensitive and explicitly not attributable to KV size).

---

## Recommendations

| Goal | Pick | Why |
|---|---|---|
| **4-node GLM serving, today-shippable** | **GLM-5.3-Flash NVFP4 @ TP4 (repo B formula)** | only line that fits 4 nodes with real KV headroom; qualified receipts exist |
| 4-node full 753B | EXL3 3.0 bpw on TensorFold | the only full-model option that fits TP4; distinct engine, distinct licence surface |
| 8-node full 753B NVFP4 | incoai or RadixArk @ TP8 | vendor-published topology; no GB10 measurement exists |
| Commercial use, clean licence | Flash line (MIT) with **MTP/EAGLE**, not DFlash2 | DFlash2 is CC BY-NC-ND |

**What we can and cannot ship tonight:** the Flash vLLM lane is the near-term buildable one, but repo
B's *reference image has no public digest* (`public_image_digest_available: false`) — a shipped recipe
needs a pinnable image (the RedHat card names `vllm/vllm-openai:glm53-flash`, existence unverified
here). The EXL3 lane's engine is an **unreleased fork branch** — it needs an image build before a

**Guard constraints for any GLM recipe here** (ds4 lane precedent, `recipes/ds4/AGENTS.md` §6, guarded
by `tests/test_ds4_recipes.py`): no host device names in `env` (`NCCL_IB_HCA`, `NCCL_SOCKET_IFNAME`);
the sparkrun IB probe supplies them (ACTIVE ports only, GID 3). Repo A's per-node HCA pinning and its
default `NCCL_IB_GID_INDEX=5` must **not** be copied.

---

## Licensing map

- **Full 753B line and every derivative** (`zai-org/GLM-5.3`, `incoai`, `RadixArk`,
  `bertholomus/GLM-5.3-EXL3-3.0bpw`): the **Z.AI GLM-5.3 Licence**, byte-identical text; permissive
  with the MaaS >$10B security-review clause. RadixArk's card still says "MIT-style" — its LICENSE
  file is the Z.AI text.
- **GLM-5.3-Flash**: **MIT** (`zai-org/GLM-5.3-Flash/LICENSE` is plain MIT) — the cleanest for
  commercial use.
- **`RedHatAI/GLM-5.3-Flash-NVFP4`**: card front-matter declares `license: mit` but the repo exposes
  **no explicit licence metadata**; link, do not mirror.
- **DFlash2 drafters**: **CC BY-NC-ND 4.0** (both the full-model and Flash variants).

---

## Platform risks

- Flash lane: reference image has **no public digest** → not byte-reproducible yet.
- EXL3 lane: engine pinned to an **unreleased fork branch** (`glm-dsa-tp4`) → maintenance/pin risk;
  cold-boot time unpublished (our DSV41 TensorFold lane boots ~511 s cold).
- Thermals: repo A saw **86 °C** on one node in the 1M config — airflow matters.
- Repo B ships **eager** execution; our own ds4 measurement recorded eager at a ~4× decode penalty
  with graphs working, and repo A's engine precaptures 50 CUDA graphs for that reason. Treat "eager"
  as a candidate to re-test, not to copy.

---

## What these sources do **not** give us (do not infer)

- **No measured GLM-5.3 (753B) NVFP4 number on GB10 from anyone.** Repo B measures Flash; repo A
  measures EXL3. The incoai/RadixArk pair remains unvalidated on our hardware and their only
  published serving line is TP=8.
- **No cold-boot time** for either GLM lane.
- **No EXL3-vs-NVFP4 head-to-head on the same hardware** — any "EXL3 is better/smaller" claim is
  inference from size, not a measurement.
- **No guard suite and no recipe** exist for this lane yet; this file is research only.

---

## Sources

- `bertholomus/glm-5.3-tensorfold-tp4-4xgb10` @ `9a5c1100c68cd8ea832803c120ee63313049fc21` (recipe:
  quant formula, launch scripts, measured numbers).
- `bertholomus/TensorFold` branch `glm-dsa-tp4` @ `ddfad356dc16f4d6bed9cfcc9d60cd0ebc0a3595`
  (engine fork).
- `bertholomus/glm-5.3-flash-nvfp4-gb10-tp4` @ `709740dc8b5942358bf55d9fa49d01c9cc3ee459`
  (validation package: `config/runtime-formula.json`, `evidence/{checkpoint-manifest,kv-ladder,qualification}.json`,
  `scripts/probe_openai.py`).
- Checkpoints: the four HF links above; `zai-org/GLM-5.3`, `zai-org/GLM-5.3-BF16`,
  `zai-org/GLM-5.3-Flash`.
- DGX Spark specs: <https://www.nvidia.com/en-us/products/workstations/dgx-spark/>.
