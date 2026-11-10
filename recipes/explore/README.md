# Explore lane

Frontier reasoning + tool-calling models for one DGX Spark node. **Selection 2026-10-19** (owner
directive): top candidates are optimized for **generation speed, concurrency, accuracy and small
size**; ties break on the owner's 2026-10-11 weighting — **node count (lower) → accuracy (higher) →
speed (higher) → memory (lower)**. Every measured arm in this lane is 1 node, so node count tied.

The lane now ships **seven measured arms** — the accuracy leader, the smallest 262k arm with
measured headroom, the best 262k aggregate at c10, the fastest/smallest GGUF arm, the
Nemotron-3.5-Lightning 30B-A3B NVFP4 arm booted 2026-10-21 (highest C1 of any single-node chat arm
here), and the Spark-X2.6 pair (FP8 fast tier + bf16 accuracy control, booted 2026-10-22) — plus the
other **ten** measured arms from the 2026-10-14…18 expansions are
archived with their receipts in [`attic/explore/`](../../attic/explore/) (manifest:
[`ARMS-MANIFEST.md`](../../attic/explore/ARMS-MANIFEST.md)). The 17-row decision table with one
receipt path per arm is [§Selection](#selection-2026-10-19); per-arm measured histories, serving traps
and the full candidate research live in [`attic/explore/AGENTS.md`](../../attic/explore/AGENTS.md) and
[`EXPLORE-MODELS-RESEARCH.md`](../../attic/explore/EXPLORE-MODELS-RESEARCH.md).

**Media and tooling arms moved to [`recipes/media/`](../media/)** on 2026-10-22 (owner directive):
drama TTS, LTX-2.5, Qwen-Image (shipped + 4-step probe), MiniMax-H3, humanizer Q6_K, Kokoro TTS and
the pyannote diarizer. Explore keeps the language and agentic/RAG arms.

## Contents

- [Easy-traffic selection (2026-10-22)](#easy-traffic-selection-2026-10-22)
- [Selection (2026-10-19)](#selection-2026-10-19)
- [ling-3.0-flash-int4-dspark-sglang](#ling-30-flash-int4-dspark-sglang)
- [kolibri-1-apex-24bpw-llamacpp](#kolibri-1-apex-24bpw-llamacpp)
- [poolside-laguna-xs-2.1-nvfp4-dflash-vllm](#poolside-laguna-xs-21-nvfp4-dflash-vllm)
- [poolside-laguna-m1-nvfp4-vllm-tp2](#poolside-laguna-m1-nvfp4-vllm-tp2)
- [flint-40b-a2.5b-ud-q3k-xl-llamacpp](#flint-40b-a25b-ud-q3k-xl-llamacpp)
- [mellum2.1-12b-a2.5b-q4km-thinking-llamacpp](#mellum21-12b-a25b-q4km-thinking-llamacpp)
- [zz-mellum2.1-12b-a2.5b-q4km-thinking-llamacpp-mmap](#zz-mellum21-12b-a25b-q4km-thinking-llamacpp-mmap)
- [zz-mellum2.1-12b-a2.5b-q4km-thinking-llamacpp-mtp](#zz-mellum21-12b-a25b-q4km-thinking-llamacpp-mtp)
- [nemotron-3.5-lightning-30b-a3b-nvfp4-vllm](#nemotron-35-lightning-30b-a3b-nvfp4-vllm)
- [Kolibri-1 1M constant-state (eval-only, not a recipe)](#kolibri-1-1m-constant-state-eval-only-not-a-recipe)
- [spark-x2.6-4b-bf16-sglang](#spark-x26-4b-bf16-sglang)
- [spark-x2.6-4b-fp8-sglang](#spark-x26-4b-fp8-sglang)
- [zz-spark-x2.6-4b-fp8-ngram-sglang](#zz-spark-x26-4b-fp8-ngram-sglang)
- [zz-spark-x2.6-4b-int8-sglang](#zz-spark-x26-4b-int8-sglang)
- [ternary-bonsai-2-9b-q2_0-llamacpp](#ternary-bonsai-2-9b-q2_0-llamacpp)
- [zz-beam-1.0-501b-a23b-nvfp4-tp4-vllm](#zz-beam-10-501b-a23b-nvfp4-tp4-vllm)
- [zz-sage-a1.5-35b-a3b-fp8-sglang](#zz-sage-a15-35b-a3b-fp8-sglang)
- [zz-sage-a1.5-35b-a3b-q4km-llamacpp](#zz-sage-a15-35b-a3b-q4km-llamacpp)
- [zz-kimi-k3.1-pro-superexpert-24b-q4p-ref-vllm](#zz-kimi-k31-pro-superexpert-24b-q4p-ref-vllm)
- [kimi-k3.1-pro-pruned75-mxfp4-vllm-tp4](#kimi-k31-pro-pruned75-mxfp4-vllm-tp4)
- [kimi-k3.1-pro-pruned75-mxfp4-dspark-vllm-tp4](#kimi-k31-pro-pruned75-mxfp4-dspark-vllm-tp4)
- [Kimi-K3.1-Pro spinoffs: REAPs, drafters and the EXL3 2-bit](#kimi-k31-pro-spinoffs-reaps-drafters-and-the-exl3-2-bit)
- [Ripple-65B Preview (2026-11-08 trial)](#ripple-65b-preview-2026-11-08-trial)
- [Attic index](#attic-index)

## Easy-traffic selection (2026-10-22)

**`mellum2.1-12b-a2.5b-q4km-thinking-llamacpp` is the selected single-node easy-traffic arm** — the
one Spark an easy traffic class is pointed at, as opposed to the four-node DeepSeek-v4 foundation.
Owner decision `mad-science/QUESTIONS.md` `#1`, recorded in `mad-science/TODO.md` `#49` and on the
`mad-science/STATUS.md` gate board. Nothing was re-measured for the promotion: every cell below is
the ten-slot window, already on file.

**The gate, as amended 2026-10-22.** A single-node arm qualifies only when, from one boot, (1) decode
is at least as fast as the knapcio TP=4 baseline — C1 **≥ 69.28 t/s** and C10 **≥ 116.27 t/s**;
(2) throughput at ten slots does not sag below that C10 bar — **leg (2) no longer requires
C10 ≥ C5**: a genuine peak at five streams is acceptable once the ten-slot C10 clears the absolute
bar, while a C10 **below 116.27** is still a capacity failure; (3) the house battery is **≥ 36/37**
at 4096 thinking-on, i.e. at least the baseline's own score. Missing a leg disqualifies.
`E = C10 / (C1 × 10)` is **reported, not gated** — it favours low-C1 arms: at this arm's own C1
110.52, E = 0.168 would need C10 ≥ 185.68, i.e. the ladder's five-stream peak.

| cell | measured | bar | verdict |
|---|---|---|---|
| C1 | **110.52 ± 1.77** t/s | ≥ 69.28 | pass, **+59 %** |
| C2 | 154.30 ± 1.6 t/s | — (diagnostic) | — |
| C5 | **208.29 ± 5.67** t/s | — (ladder peak) | — |
| C10 | **185.96 ± 2.31** t/s | ≥ 116.27 | pass, **+60 %** |
| E (`C10 / (C1 × 10)`) | 0.168 | reported only | — |
| house @4096 thinking-on | **36/37** | ≥ 36/37 | at the bar |
| TTR | 25 s | — | — |
| geometry | `n_slots = 10`, `n_ctx_slot = 131,072`, `kv_unified = true` | ≥ 10 real slots | pass |

**Provenance — all eight cells are the ten-slot window.** One boot on `.34`, 2026-10-22, receipt
`~/benchmarks/mellum-c10-20261022/REPORT.md`: the shipped recipe byte for byte except `parallel: 10`
and `-c 131072 -np 10 --kv-unified`, ladder @ d0 pp2048 tg128 n=5, decode rows only. C2 and C5 are
**that window's own measurements** (154.30, 208.29) — nothing between C1 and C10 is interpolated.
The **eight-slot** window is a different boot (`~/benchmarks/mellum-gguf-20261017/`, the shipped
`parallel: 8`) and reads 111.9 / 151.1 / 208.0 / **146.4**; the 39.6 t/s gap at c10 is the eight-slot
queue, not a different arm.

**What the C5 → C10 decline means.** 208.29 → 185.96 t/s is **−10.7 %**, and it is contention, not
queueing: per-stream decode falls **41.7 t/s at c5 → 18.6 t/s at c10** with the 8-slot queue removed.
This arm's throughput peak is genuinely five streams; streams past five cost total tokens/s. That is
the shape leg (2) was amended to accept, which is why the whole ladder is quoted here and not just
the two gated cells.

**Extras, not gate legs.** Thinking-off reads **31/37** and leaks raw `</think>` text into `content`.
The single thinking-on loss is `needle-1`: an empty reply in one of three repeats, `ZORBULON` in the
other two — a serving-side empty-content event, not a retrieval miss. The MTP draft-length rejection
is **unchanged and not reopened**; the sweep stays in
[§mellum2.1-12b-a2.5b-q4km-thinking-llamacpp](#mellum21-12b-a25b-q4km-thinking-llamacpp).

## Selection (2026-10-19)

The four scored axes are **generation speed** (C1 t/s and the ladder's shape), **concurrency** (KV
pool at the shipped window plus any `max_num_seqs` / `parallel` clamp), **accuracy** (house battery,
needle, ARC, GSM8K, BFCL, TEB — whichever the arm actually has), and **size / peak memory**. All 17
listed arms are measured; fifteen are scored on these axes, the archived bf16 humanizer is a retired
rewriter row, and the INT8 Spark tier was kernel-rejected. The verdict column is the selection.
Decode rows only (`is_context_prefill_phase: false`); `×` is the KV pool at the arm's shipped
`max_model_len`; a `max_num_seqs` / `parallel` clamp — not the pool — is the in-flight ceiling where
one is set.

| arm | C1 t/s (d0) | ladder c1 / c2 / c5 / c10 | concurrency ceiling | accuracy (house · needle · ARC · GSM8K · BFCL · TEB) | size · memory | receipt | verdict |
|---|---|---|---|---|---|---|---|
| `ling-3.0-flash-int4-dspark-sglang` | **49.7 ± 6.0** | 49.7 / 66.2 / 100.2 / 85.9 (peak c5, dip c10) | KV 313,248 tok = **1.20×** at 262,144 (ladder boot; 313,752 on the 2026-10-12 boot); `max_num_seqs: 6` | **37/37** · 3/3 @32k, 3/3 @131k, **2/3 @262k** · **94.5%** · **94.0%** · **88.0%** · — | 77 GB + 2.7 GB draft · util 0.80 · 154 GB distributed | `~/benchmarks/ladders-solo-20261018/ling-ladder.json`, `ling-boot.log`, `ling-suite/summary.md`, `ling-needle-262k-mt512/` | **KEEP — accuracy leader** |
| `kolibri-1-78b-fp8-vllm` | 47.2 ± 0.1 | 47.2 / 76.2 / 77.6 / 83.5 (flat past c2) | KV 1,859,922 tok = 7.1×; `max_num_seqs: 4` | 37/37 @8192 · — · — · — · — · — | 74 GB · util 0.78 | `~/benchmarks/ladders-solo-20261018/kolibri-ladder.json`, `kolibri-battery-8192.json`; pool `~/benchmarks/explore-repin-20261014/kolibri-boot.log` | **retire** — its 4-bit packs are smaller/faster; Ling has the deeper accuracy cells |
| `kolibri-1-apex-24bpw-llamacpp` | 63.24 ± 0.50 | 63.83 / 113.35 / 98.30 / 78.62 (peak c2) | 262,144 × `parallel: 4`, `kv_unified` = **4 slots**; c10 is 10 streams over 4 | 37/37 · **3/3 @32k, 3/3 @131k, 3/3 @262k** · 85.5% · 88.0% · **85.2%** · — | 22.7 GiB mmap · **79 GiB available** while serving 262k · TTR 22.2 s | `~/benchmarks/kolibri-gguf-20261018/apex24-ladder.json`, `apex24-triage.json`, `apex24-battery.json`; suite `~/benchmarks/kolibri-apex-suite-20261020/summary.json` | **KEEP — smallest 262k with measured headroom** |
| `kolibri-1-apex-q4k-llamacpp` | 57.67 ± 0.21 | 56.16 / 90.23 / 83.25 / 67.50 | same 4-slot ceiling | 37/37 · — · — · — · — · — | 41.89 GiB · 59 GiB available | `~/benchmarks/kolibri-gguf-20261018/q4k/` (`q4k-ladder.json`, `q4k-triage.json`, `q4k-battery.json`) | **retire** — 2.4bpw wins size and every ladder cell |
| `kolibri-1-78b-fp8-tensorfold-drafter-sglang` | 55.6 ± 5.9 (d8192 54.6) | — (C1 only; no ladder) | 4 streams @ 262,144 (22.7 GiB caches) | 37/37 @4096 · — · — · — · — · — | 79 GB + 0.8 GB drafter | `~/benchmarks/kolibri-mtp-20261018/mtp-triage.json`, `house/summary.json` | **retire** — no aggregate; 4-slot cap; fork JIT risk |
| `kolibri-1-nvfp4a16-fp8-vllm` | 52.48 ± 0.21 | 52.11 / 91.64 / 95.15 / 106.39 | KV 4,606,739 tok = 17.6×; cap 4 | **36/37** · — · — · — · — · — | 42.69 GiB · util 0.78 | `~/benchmarks/kolibri-quants-20261018/quantinine/` (`c2c5c10-ladder.json`, `triage.json`, `battery.json`) | **retire** — 36/37 loses the accuracy tie |
| `kolibri-1-nvfp4-experts-vllm` | 52.37 ± 0.05 | 52.00 / 91.58 / 95.03 / 105.58 | KV 4,618,726 tok = 17.6×; cap 4 | 37/37 · — · — · — · — · — | 42.6 GiB · util 0.78 | `~/benchmarks/kolibri-quants-20261018/iskye/` (`c2c5c10-ladder.json`, `triage.json`, `battery-4096.json`) | **retire** — APEX-24bpw wins speed+size at equal house accuracy |
| `kolibri-1-mxfp4-mxwave-vllm` | 51.60 ± 0.16 | 51.41 / 92.64 / 96.28 / 108.20 | KV 4,791,929 tok = 18.3×; cap 4 | 37/37 but **strict KL fail** (0.0551 > 0.030) · — · — · — · — · — | 40.93 GiB · util 0.78 | `~/benchmarks/kolibri-quants-20261018/kirill/` (`perf-ladder.json`, `decode-triage.json`, `quality-battery.json`) | **retire** — fails its own quality screen |
| `poolside-laguna-xs-2.1-nvfp4-dflash-vllm` | 55.3 ± 2.4 | 55.3 / 83.1 / 133.7 / **141.3** (still rising at c10) | KV 1,464,371 tok = **5.59×** at 262,144 (ladder boot; 1,403,263 on the 2026-10-14 boot); `max_num_seqs: 8` | 35/37 · 2/3 @32k, 2/3 @131k, **3/3 @262k** · 66.0% · 90.5% · 60.1% · **97** | 21.6 GB + 0.92 GB draft · util 0.55 → ~95 GB headroom | `~/benchmarks/explore-laguna-xs-20261017/perf-ladder.json`, `launch.log`, `house.json`, `needle-*.json`, `bfcl.json`, `teb.json` | **KEEP — best 262k aggregate at c10** |
| `nemotron-3.5-lightning-30b-a3b-nvfp4-vllm` | **63.27 ± 0.65** | 63.27 / 90.81 / 122.27 / **144.15** (still rising at c10) | KV 10,703,667 tok = **326.65×** at 32,768; no `max_num_seqs` clamp | **37/37 @2048** · — · — · — · — · — | **20.1 GiB** · util 0.85 (= 0.8263 effective under CUDA-graph profiling) | `~/benchmarks/reasoning-candidates-20261021/` (`house-2048.json`, `ladder.json`, `serve.log`) | **KEEP — fastest single-node C1 at the smallest weight footprint** |
| `poolside-laguna-s-2.1-nvfp4-dflash-vllm` | 20.26 ± 0.87 | 20.26 / 29.26 / 38.96 / 53.80 | KV 106,010 tok = **1.078×** at 98,304; `max_num_seqs: 32` | 33/37 · 3/3 @32k, 3/3 @98,304 · — · — · — | 95.61 GiB resident · util 0.85 | `~/benchmarks/sweep2-20261018/laguna-s-ladder.json`, `laguna-s-suite/summary.md` | **retire** — dominated by XS on every axis |
| `humanizer-12b-vllm` | 7.6 | — (chat endpoint 400s: the checkpoint defines **no chat template at all**, so vLLM refuses the chat route — not an engine fault; no chat route ⇒ no ladder) | KV 370,597 tok = 45.2× at 8,192 | — · — · — · — · — · — (off-brief; 0 fact losses / 40 rewrites) | 23.9 GB weights / **88 GB repo on disk** · util 0.85 | `~/benchmarks/humanizer-20261014/results.json`, `SUMMARY.md` | **retire** — off-brief, unscoreable on the axes |
| `mellum2.1-12b-a2.5b-bf16-thinking-vllm` | 42.3 ± 0.1 | 42.3 / 67.2 / 99.9 / 135.6 | util 0.55 (66.6 GiB budget); 131,072; KV grant not captured | 36/37 · — · — · — · — · — | 24.3 GB · util 0.55 | `~/benchmarks/mellum-20261015/perf-ladder.json`, `house.json` | **retire** — dominated by its own Q4_K_M sibling |
| `mellum2.1-12b-a2.5b-q4km-thinking-llamacpp` | **111.9 ± 0.3** | 111.9 / 151.1 / **208.0** / 146.4 (8 slots, peak c5); **ten slots 2026-10-22: 110.5 / 154.3 / 208.3 / 186.0** (peak still c5) | 131,072 × `parallel: 8` shipped; `parallel: 10` probe logs `n_slots = 10, n_ctx_slot = 131,072`, `kv_unified` | 37/37 · **36/37 battery @4096** (`needle-1` empty reply in 1 of 3) · 3/3 @131k (32k 3/3 by union) · 77.0% · 93.5% · **88.3%** · **97** | **8.07 GB** · no util (llama.cpp sizes its own pool) | `~/benchmarks/mellum-gguf-20261017/perf-ladder.json`, `summary.md`; ten-slot `~/benchmarks/mellum-c10-20261022/REPORT.md`; `~/benchmarks/mellum-gguf-tools4096-20261017/bfcl.json` | **KEEP — fastest decode + best aggregate peak + smallest**; **[§Easy-traffic selection](#easy-traffic-selection-2026-10-22): the SELECTED single-node easy-traffic arm (2026-10-22)** |
| `spark-x2.6-4b-bf16-sglang` | **20.38 ± 0.09** | 20.38 / 46.38 / 99.27 / **156.20** (still rising at c10) | KV 723,730 tok = **5.52×** at 131,072 (hybrid: 9 full + 27 sliding layers → 24.84 GB + 59.64 GB pools); `max_num_seqs: 32` | **37/37** thinking-on @4096 · **30/37** thinking-off · — · — · tool-call PASS · — | 8.22 GB bf16 loaded as 9.27 GB · util 0.85 (84.48 GB KV, 14.80 GB spare) · TTR 167.4 s port / 252.5 s HTTP | `~/benchmarks/spark-x26-20261022/` (`boot.log`, `serve.log`, `ladder.json`, `battery-thinking-{on,off}.json`) | **accuracy control — 37/37 at C1 20.38; the FP8 tier doubles C1 and ties it** |
| `spark-x2.6-4b-fp8-sglang` | **40.80 ± 0.09** | 40.80 / 77.06 / 146.63 / **217.58** (still rising at c10) | KV 779,390 tok = **5.95×** at 131,072 (hybrid: 26.76 GB + 64.22 GB pools); `max_num_seqs: 32` | **37/37** thinking-on @4096 on the rerun (111/111, no flaky) · — · — · tool-call not probed on this tier · — | 5.52 GB resident (4.47 GB checkpoint) · util 0.85 (90.98 GB KV, 11.38 GB spare) · TTR 129.5 s port / 136.4 s HTTP | `~/benchmarks/spark-x26-20261022/` (`boot-fp8*.log`, `serve-fp8*.log`, `ladder-fp8.json`, `battery-fp8-thinking-on.json`, `battery-fp8-rerun-4096.json`) | **KEEP — the fast tier: 2× the control's C1 at every rung, quality tied on the rerun** |
| `zz-spark-x2.6-4b-int8-sglang` | — (never served) | — (never served) | — | — | 5.47 GB resident (4.47 GB checkpoint) · loaded in 28.08 s, died 57 s in | `~/benchmarks/spark-x26-20261022/` (`boot-int8.log`, `serve-int8.log`) | **measured-rejected at the kernel level — `int8_scaled_mm` unimplemented for sm_121** |

**Memory column read-out:** for vLLM arms it is the shipped `gpu_memory_utilization` cap plus the
engine's own KV grant (a util is a cap, not a peak); for the llama.cpp arms it is the resident pack
plus the `free -g` available reading taken while serving; for the image arm it is the torch peak
alloc/reserved pair. Peak *host* RSS is not in every receipt, and none is invented here.

**The house bar, read correctly.** 37/37 in practice means **clears `hard-rev`**: the reverse-the-string
item is the near-universal discriminator — `nurkrpas` / `nurkraps` / `nrukraps` / `nurkrasp` on
Laguna-XS, both Muse-Glimmer exports, K2-Horizon-7B, the knapcio TP-4 and ds4 TP-2 lines, and more —
while the other 36 tasks are typically clean. A sub-37 house score is almost always this one item, and
it is a real capability miss there, not an instrument artifact; the bar itself is unchanged.

**Tie-break record.** Node count tied at 1 for all 14. Accuracy decided first: Ling is the accuracy
leader (ARC/GSM8K/BFCL all measured, house 37/37); the Mellum GGUF ties the house score and leads BFCL
(88.3 vs 88.0) while also leading speed and size. The `iSkye` 4-bit pack and APEX-24bpw both saturate
the house battery (37/37, no ranking power), so speed and memory decided: APEX-24bpw wins
**63.8 vs 52.4 t/s** and **22.7 vs 42.6 GiB**. Laguna-XS keeps the concurrency slot: its c10 cell
(141.3) is the highest of any 262k-window arm and its ladder is still rising; the Mellum GGUF's 146.4
was higher in absolute terms but measured 10 streams over an 8-slot grant — re-measured at ten real
slots (2026-10-22) it is **186.0 ± 2.3**, still below its own c5 208.3, so it is a genuine five-stream
peak at a 131,072 window and not a slot limit; Laguna-XS keeps the slot because its ladder rises to c10.

**Two arms with no index row:**

- `poolside-laguna-m1-nvfp4-vllm-tp2.yaml` — **booted and measured 2026-10-20 on the test pair** (TP=2,
  receipt `~/benchmarks/laguna-m1-20261020/`; suite + ladder in its own section below). It is still not
  a selection candidate — it is the family's two-node ceiling reference.
- `mistral-small-4-119b-nvfp4-vllm.yaml` — measured and **rejected** (C1 28.94 ± 0.03; 89,216-token
  servable ceiling at 1.01× concurrency; house 33/37 default, 36/37 ceiling). Archived 2026-10-19 as
  measured-rejected: see the manifest and `~/benchmarks/mistral-119b-20261018/REPORT.md`.

**Retired 2026-10-19** (10 arms; receipt paths and the tie-break reason per arm are in
[`attic/explore/ARMS-MANIFEST.md`](../../attic/explore/ARMS-MANIFEST.md)): the Kolibri FP8 base, its
TensorFold-drafter trial, the Q4_K APEX tier and all three 4-bit vLLM packs; Laguna-S;
`humanizer`; the Mellum BF16 parent; and Mistral-Small-4. The unrun Kolibri GGUF tiers
(`Hob-forge` / `webmp3` / `aparusel`) were never authored as recipes, so there is no file to move;
they are recorded as **unmeasured / not built** in the manifest.

## [ling-3.0-flash-int4-dspark-sglang](ling-3.0-flash-int4-dspark-sglang.yaml)

SGLang · **1 node (TP=1)** · **kept — accuracy leader (2026-10-19)**.

- **Model:** `inclusionAI/Ling-3.0-flash-int4` (MIT) + the DSpark draft `inclusionAI/Ling-3.0-flash-dspark`
  (pinned `d60b0e12…`).
- **Size / memory:** ~77 GB INT4 weights (+ 2.7 GB draft); 154 GB distributed (`model_file_selection: all`
  is required — the 17.59 MiB safetensors index exceeds the 16 MiB inventory cap).
- **Flags / non-obvious knobs:** `mem-fraction-static: 0.80` (KV pool 313,248 tokens on the
  2026-10-18 ladder boot; 313,752 on the 2026-10-12 boot — same util, inter-boot spread; 0.87 stays
  the documented OOM-risk ceiling); `served_model_name: inclusionAI/Ling-3.0-flash-int4` declared *and*
  rendered (sparkrun otherwise rewrites `{model}` to the snapshot path); the draft pin is rendered as
  `--speculative-draft-model-revision {speculative_draft_model_revision}` (not distribution-only). KDA
  ReplaySSM verify path.
- **Serving note:** the official LMSYS `sglang:dev-Ling-3.0-flash` image runs the arm — the
  third-party Spark port's GHCR image predates the `dspark_components` /
  `--enable-linear-replayssm-spec` flags this recipe needs (digest-pinned).
- **Measured:** ladder @ d0, pp 2048 / tg 128, n=5 — **C1 49.7 ± 6.0 · C2 66.2 ± 7.1 · C5 100.2 ±
  6.4 · C10 85.9 ± 3.1 t/s** (`bench_7c46291e9bbb`); the aggregate peaks at c5 and dips at c10, one
  window with no same-window control, so a plateau reading rather than a knee. The earlier boot's
  single points stand as history: C1 **45.5 t/s** (σ 5.5) / 32.3 @ d8k. Quality on the ladder's boot:
  contract ok; house **37/37**; arc **94.5 %** / gsm8k **94.0 %** (n=200 each); bfcl **88.0 %**
  (1091/1240); needle **3/3 @32k · 3/3 @131k · 2/3 @262k**. The 262k cell and its mechanisms: the
  suite's 900 s per-request cap (a 256k prefill plus reply measures 1,333–1,360 s) timed all three
  out, re-probing at needle-haystack's 64-token default cut all three at `finish_reason=length`
  (1/3), and at 512 tokens 2/3 retrieve — the remaining miss genuine: depth 90 returned
  `79不1-ALBATROSS` for `7901-ALBATROSS` in 96 tokens at `finish_reason` stop. **This supersedes the
  earlier "262k needle PASS".** Receipts `~/benchmarks/ladders-solo-20261018/` (`ling-suite/`,
  `ling-needle-262k-mt512/`).
- **Second ladder (2026-10-26, spares-lane, `.35`, pool-era route):** C1 **42.0 ± 3.3 · C2 65.3 ± 6.5 · C5 104.9 ± 4.8 · C10 86.9 ± 4.1 t/s** (`~/benchmarks/spares-20261026/ling-ladder/RECEIPT.md`, 5 runs) — reproduces the 2026-10-18 row (49.7/66.2/100.2/85.9) inside the 7-25 % inter-boot floor, same peak-at-c5 shape. Two tooling notes this boot proved: the arm needs **~13 min to ready** on a first pool read (24 shards at ~25 s/shard), which is past the benchmark runner's readiness give-up — the harness tears the boot down mid-load and the cell must be measured with the runner's own tool manually (`uvx llama-benchy --base-url http://<node>:8030/v1 … --extra-body return_token_ids=false`, the sglang streaming suppression the runner otherwise applies itself; the base URL must carry `/v1` or the warmup 404s). A `readiness:` block in the recipe would re-enable harness-driven ladders.
- **Campaign ladder (2026-11-03, tp12, `.30`):** C1 **47.30 ± 7.26** · C2 **67.73 ± 9.54** · C5
  **109.70 ± 4.40** · C10 **89.82 ± 2.95 t/s** @ d0, pp 2048 / tg 128, n=5 — reproduces the
  2026-10-18 row (49.7 / 66.2 / 100.2 / 85.9) inside the inter-boot floor and keeps its
  peak-at-c5, dip-at-c10 shape; standard suite **97**/100 (15/15, `tool-eval-bench` 2.6.0;
  deployability 89, responsiveness 69). Receipt
  `~/benchmarks/tp12-20261103/ling-3.0-flash-int4-dspark-sglang/` (`ladder.json`, `house.json`).
- **License:** MIT.

## [kolibri-1-apex-24bpw-llamacpp](kolibri-1-apex-24bpw-llamacpp.yaml)

llama.cpp, fork `kolibri1` build · **1 node (TP=1)** · **kept 2026-10-19 — smallest 262k arm with
measured headroom**.

- **Model:** `Myric/Kolibri-1-APEX-GGUF:APEX-2.4bpw` @ `ed6030d7…` — 24,374,307,840 B / 22.70 GiB,
  2.50 bits/weight (mixed: sliding-window projections Q3_K, experts IQ3_XXS/IQ2_S/IQ2_XXS, the
  sensitive tensors left Q8_0/Q6_K/F32). Public, ungated. `/v1/models` reports `ftype` "Q4_K - Medium"
  — that is the packer's `general.file_type` enum, **not** this pack's quant; do not quote it.
- **Engine:** fork image `littlecedar/dgx-spark-llama-cpp-kolibri1:0.4.0-68fa28b@sha256:1928661c…`
  (stock llama.cpp cannot load `kolibri1` at all); `ctx_size` 262,144 × `parallel: 4`, `kv_unified`;
  served id `Myric/Kolibri-1-APEX-GGUF`. mmap stays at the fork's `auto` (it has no `--no-mmap`).
- **Measured (one boot, `~/benchmarks/kolibri-gguf-20261018/`):** C1 **63.24 ± 0.50** @ d0
  (`bench_a0ecb791dfe6`) / **60.79 ± 0.43** @ d8192; ladder @ d0 pp2048 tg128 n=5 **63.83 · 113.35 ·
  98.30 · 78.62 t/s** (`bench_d165fa4b0bea`), decode rows only (the d8192 cell emits a second,
  context-prefill record — pooling it is the classic 2× artifact). House battery **37/37 @4096**,
  which is a saturation result, not a ranking. TTR **22.2 s** (container start → `listening`).
- **Memory:** while serving the full 262,144 window, `free -g` read used 42 / buff-cache 23 /
  **available 79 GiB** on a 121 GiB GB10; the pack is mmap'd, so its 22.70 GiB sits in page cache and
  the 262k unified KV adds the recipe's ~5 GiB. That is a **headroom** result measured solo — no
  second model was loaded — so it is *not* a co-residency measurement, and TTR is time-to-healthy,
  not time-to-fully-paged (cold-page first-token latency is paid by the first request).
- **Why this tier and not Q4_K:** the 2.4bpw pack wins on **both** measurable axes — −8.8 % at d0 and
  −11.3 % at d8192 for Q4_K, and −20 / −15 / −14 % at c2/c5/c10 — while nearly half the weight bytes.
  Q4_K's only claimed advantage is its uploader's KLD figure, which the house battery cannot see
  (both saturate 37/37), so it is uncorroborated by this registry.
- **Standard suite (2026-10-20, `~/benchmarks/kolibri-apex-suite-20261020/`):** all five legs `ok`,
  11,878 s total. contract `max_model_len=262144`, but its own readiness probe came back
  `ready=False finish=length` (the reply spent its budget in reasoning), so the leg's `ok` is the
  length check, not a readiness proof. house **37/37** (133.4 s), needle **3/3 at 32,768, 131,072 and
  262,144** (1,377.7 s) — a **real** top rung, the first arm measured here whose 262k cell is not
  truncated, because `n_ctx_slot` really is 262,144. hard **ARC 171/200 = 85.5 %** and **GSM8K
  176/200 = 88.0 %** (3,939.8 s), both **floor-limited**: 23 and 21 `length` finishes at the 512-token
  answer budget, so they understate the arm rather than rank it. tools **1056/1240 = 85.2 %**
  (6,425.7 s = 5.2 s/question). The serve's `/v1/models` advertises `capabilities: ["completion"]`
  only, yet the tools leg emits structured `tool_calls` — that field is cosmetic in llama-server and
  is not evidence of missing tool support.
- **Second ladder (2026-10-26, spares-lane, `.30`, pool-era route):** C1 **62.1 ± 0.8 · C2 113.0 ± 1.1 · C5 97.5 ± 1.1 · C10 77.9 ± 0.9 t/s** (`~/benchmarks/spares-20261026/kolibri-ladder/RECEIPT.md`, 5 runs) — reproduces the 2026-10-18 row (63.83/113.35/98.30/78.62) within 1-2 % on every cell; the peak-at-C2-then-fall shape (c5/c10 oversubscribe the 4 slots) reconfirms.
  **Battery second boot (2026-10-26, spares-lane): easy 19/19 + hard 18/18 = 37/37 again** — exact
  reproduction of the 2026-10-20 receipt on the same pin, so the battery score's boot variance is 0
  (`~/benchmarks/spares-20261026/kolibri-battery-b2/RECEIPT.md`; the saturation caveat stands).
- **License:** base `Aleph-Alpha/Kolibri-1` Apache-2.0; the GGUF pack's own terms are on its card.

## [poolside-laguna-xs-2.1-nvfp4-dflash-vllm](poolside-laguna-xs-2.1-nvfp4-dflash-vllm.yaml)

vLLM · **1 node (TP=1)** · **kept 2026-10-19 — best 262k aggregate at c10**.

*Engine re-pinned on 2026-10-22 to `vllm/vllm-openai:v0.32.0` (index `befccf0e…`, `linux/arm64`
child `6ff5ff0d…`); the `v0.29.0` digest that 23 OSV records / 16 CVEs sat on is gone. vLLM 0.30.0
could not construct this revision's config (its own `LagunaConfig` shadows the transformers 5.17
class that does) — 0.32.0 loads and serves it (below). 2026-10-16 engine-bump note in
[`attic/explore/AGENTS.md`](../../attic/explore/AGENTS.md).*

- **Model:** `poolside/Laguna-XS-2.1-NVFP4` (33B total / 3B active, 256 routed experts, 3:1 SWA,
  262,144 native; OpenMDW-1.1), pinned `d32afde8…` + the first-party draft `poolside/Laguna-XS-2.1-DFlash`
  (0.92 GB), pinned `5c36361a…`.
- **Size / memory:** 21.6 GB + 0.92 GB draft; `gpu_memory_utilization: 0.55` → KV 41.56 GiB → 1,403,263
  tokens on the 2026-10-14 boot (5.35× at the native window); the 2026-10-17 ladder boot granted
  43.37 GiB → **1,464,371 tokens (5.59×)**.
- **Flags / non-obvious knobs:** NVFP4 engages natively on sm121 (`FlashInferCutlassNvFp4LinearKernel` +
  `FLASHINFER_CUTLASS` NvFp4 MoE); the draft rides in `defaults.speculative_config` with its own
  `revision`, so sparkrun both distributes and pins the blob; `num_speculative_tokens: 3` ships (a
  `decode-triage` sweep of n ∈ {3,4,7} → n=3 wins both depths); **thinking is NOT on by default despite
  the card** → the serve line passes `--default-chat-template-kwargs '{"enable_thinking": true}'`.
  **Rope caveat:** a boot warning about SWA rope is unexplained; the 2026-10-17 needle probe answers
  **3/3 at 262,144** but only 2/3 at 32k/131k (n=3 each) — the long-window miss the caveat predicted
  did not appear, and the small-depth misses are unexplained.
- **Serving note:** util 0.55 is deliberate — the weights are only ~21.6 GB of the ~121 GiB pool and
  the SWA arch keeps 262k cheap, so the low util preserves ~95 GB of node headroom.
- **Engine contract at the `v0.32.0` pin — the reasoning fields moved.** vLLM 0.32.0 returns the
  thinking text at **`message.reasoning`**; `message.reasoning_content` is **absent**, and
  **`usage.completion_tokens_details.reasoning_tokens` reads 0** even while thousands of characters of
  reasoning are emitted. Every contract and needle check in this lane keys on the old shape, so a re-run
  reads an *all-empty reply* (`content` null, `reasoning_len` 0) while the text is present under the new
  key — that is the documented "empty-`content`" failure mode, now an artifact of the field name, not of
  the serve. The second half of the same contract: with thinking on, a **1,024-token budget** returns
  `finish_reason=length` on a one-line arithmetic prompt (this arm spent 1,933 completion tokens on
  "14:40 + 3h25m"), so `--max-tokens 4096` is the floor for any re-measure, and a `length` is a
  truncation, never a capability miss.
- **Re-pin boot (2026-10-22, `.34`, `sparkrun_7b22b626acd6a019_8ed3ce77d78f`):** `/v1/models` 200
  **282 s** after launch on the first v0.32.0 boot (cold flashinfer-JIT for the xqa/fused-MoE kernels,
  then CUDA-graph capture); served id `poolside/Laguna-XS-2.1-NVFP4`, `max_model_len` 262,144; engine
  reports vLLM **v0.32.0** with `speculative_config=SpeculativeConfig(method='dflash',
  num_spec_tokens=3, …)`; KV **41.87 GiB → 1,413,525 tokens (5.39×)** vs 0.29.0's 41.56 GiB /
  1,403,263. Thinking on: `finish_reason=stop`, 4,675 chars of reasoning, correct answer
  ("18:05", 1,933 completion tokens). The engine-contract change above is the load-bearing part for a
  re-run; measured facts here are `/v1/models` 200 at 282 s and the KV pool. Receipt
  `head:~/benchmarks/vllm-032-20261022/RECEIPT-xs.md`.
- **Measured:** C1 **57.4 t/s** @ d0 (σ 3.4) / 55.1 @ d8k; accept len 1.89 / 29.5%; quality 36/37 @4096.
- **Standard suite (2026-10-17, `bench_9b207347ec3b`):** ladder @ d0 pp2048 tg128 n=5 — C1 **55.3**
  (σ 2.4) / C2 83.1 (σ 2.1) / C5 133.7 (σ 8.4) / C10 141.3 (σ 3.3) t/s, the only ladder in the lane
  still rising at c10; `tools/eval-suite.py` 3 ok / 2 fail — house easy 19/19 + hard 16/18, needle
  2/3 @32k / 2/3 @131k / **3/3 @262k** (n=3 each), arc 66.0% (n=200) / gsm8k 90.5% (n=200), bfcl
  60.1% (745/1240); the two fails are **contract** (`finish=length`, all-empty reply at the 262,144
  window — the reasoning parser's empty-`content` shape, thinking burning `max_tokens`) and **needle**
  at the two smaller depths. TEB (`standard-suite.yaml`): 15 scenarios, 14 pass + 1 partial, score 97.
  Receipts `head:~/benchmarks/explore-laguna-xs-20261017/`; the tool's own per-scenario TEB report —
  the only copy — is `.scratch/explore/laguna-xs-teb-20261017/2026-10-17T06-02-24.493866Z_4070a159.md`.
- **Standard suite re-take (2026-10-20, `~/benchmarks/laguna-xs-suite-20261020/`), same boot, 3,273 s:**
  house **36/37** (easy 19/19, hard 17/18 — `hard-rev`), needle **3/3 at 32,768, 131,072 and 262,144**
  (683 s; the 2026-10-17 small-depth misses did not reproduce), hard **ARC 124/200 = 62.0 %** and
  **GSM8K 187/200 = 93.5 %** (694 s), tools **742/1240 = 59.8 %** (1,673 s, 0 transport errors).
  contract still fails with `finish=length`, `content_len 0`, `reasoning_len 0` over 64 completion
  tokens — the empty-`content` shape named above, reproduced on this boot.
- **Why the tools score is 59.8 %, and why it is not a re-run candidate.** The loss is concentrated and
  mechanical: **all 400 multi-call questions fail** — `parallel` 0/200 and `parallel_multiple` 0/200,
  every one `parallel_function_checker_no_order:wrong_count` — while `simple` is 369/400 and `multiple`
  189/200. The records show the cause is the **model**, not the harness: each of those 398 responses
  carries **exactly one** `calls` entry (call-count histogram over the two multi-call categories: 1 → 398,
  0 → 2) and `error: ['Wrong number of functions.']`, and the visible `content` acknowledges both
  requests ("I'll play songs from Taylor Swift and Maroon 5 on Spotify as requested") while emitting
  only the first call. Structured `tool_calls` do parse on this arm — 558 single-call questions passed —
  and the serve line carries the parsers (`--tool-call-parser poolside_v1`, `--reasoning-parser
  poolside_v1`, `--enable-auto-tool-choice`, `--default-chat-template-kwargs '{"enable_thinking":
  true}'`), so no flag is missing and a re-run would reproduce it. The remaining 98 failures are ordinary
  argument errors (`value_error:string` 7, `value_error:others` 9, `wrong_count` 6+3,
  `type_error:nested` 4) plus 56 `irrelevance_error:decoder_success` (it called where it should not).
  This is a capability result: the arm emits one tool call per turn.
- **Second ladder (2026-10-26, spares-lane, `.30`, pool-era route):** C1 **53.1 ± 2.3 · C2 81.1 ± 2.6 · C5 128.4 ± 1.0 · C10 131.4 ± 1.8 t/s** (`~/benchmarks/spares-20261026/laguna-xs-ladder/RECEIPT.md`, harness run, 5 rows of 5) — reproduces the 2026-10-17 suite ladder (55.3/83.1/133.7/141.3) within 1-7 %, still rising at c10. Logistics lesson from the first attempt: vLLM resolves `draft_model poolside/Laguna-XS-2.1-DFlash` by repo id and the drafter was absent from the pool — one governed prefill row (924,147,832 B, ledger `~/benchmarks/cache-prefill-20261026/QUEUE.md`) unblocked it. **A body preflight must `du`-check a recipe's draft/drafter repo too, not only the main model.**
- **License:** OpenMDW-1.1 (target and draft).

## [poolside-laguna-m1-nvfp4-vllm-tp2](poolside-laguna-m1-nvfp4-vllm-tp2.yaml)

vLLM · **2 nodes (TP=2)** · **the family's two-node ceiling reference**, booted 2026-10-20.

- **Model:** `poolside/Laguna-M.1-NVFP4` (225B total / 23B active agentic-coding MoE, 70 layers, 262,144
  native) pinned `e4f3ba80…`; engine pin **`vllm/vllm-openai:v0.32.0` (bumped 2026-10-22, not
  re-booted on it — see below); every measurement in this section is the 2026-10-20 `v0.29.0` boot.**
- **Engine pin: re-booted and verified 2026-10-30** on `.30`+`.35` under the `--fresh` runner — the
  outstanding item above is closed. Serve asserted before quoting: `/v1/models` = `poolside/Laguna-M.1-NVFP4`
  at `max_model_len` 262,144. Decode ladder **12.98 ± 0.03 · 22.18 ± 0.06 · 33.59 ± 0.78 · 34.96 ± 0.31 t/s**
  at c1/c2/c5/c10, i.e. within ~1.5 % of the `v0.29.0` row, so `v0.32.0` cost nothing measurable and the
  cells are quotable. Receipt `~/benchmarks/tp12-20261030/poolside-laguna-m1-nvfp4-vllm-tp2/`.
- **Engine pin (2026-10-22): BUMPED, NOT RE-BOOTED — the 2026-10-20 numbers remain `v0.29.0`
  measurements.** The recipe's `container:` moved to `vllm/vllm-openai:v0.32.0` (index `befccf0e…`)
  for the CVE reason only: 0.29.0 carried 23 OSV records / 16 CVEs, and the XS sibling boot-verifies
  0.32.0 on the same checkpoint family. The TP=2 boot on 0.32.0 is **outstanding** — no node pair was
  free on 2026-10-22 (`.30` is the production head, `.31`–`.33`/`.35` other workers' campaigns) — so
  nothing here was measured on the new engine. **Decision: keep the bump, labelled** (the recipe
  already ships an explicit engine caveat, so an unverified pin is in-convention *when stated*;
  reverting it would leave the CVE-bearing digest in the tree for an arm whose only blocker is a free
  pair). Verify first:
  `sparkrun run recipes/explore/poolside-laguna-m1-nvfp4-vllm-tp2.yaml -H <pair> --transfer-mode local`,
  then assert `/v1/models` = `poolside/Laguna-M.1-NVFP4` at `max_model_len` 262,144 before quoting
  any cell on 0.32.0.
- **Boot (2026-10-20, test pair):** 129.75 GiB downloaded at ~170 MiB/s and distributed as 259.51 GiB
  over four streams, then the TP=2 load — `/v1/models` **200 ≈43 min** after launch (sparkrun's own
  launch phase 1,076.6 s), served id `poolside/Laguna-M.1-NVFP4` with `max_model_len` 262,144.
- **Decode ladder (same boot, `bench_6ca06d393d60`):** **C1 12.85 ± 0.08 · C2 21.85 ± 0.26 ·
  C5 34.15 ± 0.20 · C10 34.64 ± 0.06 t/s** @ d0, pp 2048, tg 128, n=5, decode rows from the output file.
  It flattens past c5 — 2.7× from c1 to c10 on two GB10s.
- **Standard suite (same boot, 20,097 s):** house **37/37**; needle **3/3 at 32,768, 131,072 and
  262,144**; hard **ARC 178/200 (89.0 %)** and **GSM8K 188/200 (94.0 %)**, both with 0 empty replies;
  tools **750/1,240 = 60.5 %** with 0 transport errors. Suite verdict `fail` on **contract only**:
  `finish=length`, `ready=False`, all-empty reply — the same `enable_thinking` shape the XS sibling shows,
  not a serve failure.
- **Why the tools score is 60.5 %, and why it is not a parser bug.** The loss is one mechanical block:
  `parallel` **0/200** and `parallel_multiple` **0/200**, all 400 `parallel_function_checker_no_order:
  wrong_count`, while `simple` is 365/400 and `multiple` 189/200. The records show **one** captured call
  per response on those cells (`{1: 374, 0: 26}`) — the model names both requests in prose and emits the
  first call only. Structured calls parse fine (554 single-call questions passed), so this is a
  capability result for the arm, measured on the same instrument as every other lane arm.
- **License:** OpenMDW-1.1 (checkpoint family terms on its card).

## [flint-40b-a2.5b-ud-q3k-xl-llamacpp](flint-40b-a2.5b-ud-q3k-xl-llamacpp.yaml)

llama.cpp (registry build upstream `6023692`) · **1 node (TP=1)** · **shipped 2026-11-07 — passes the
easy-traffic gate** (C1 >= 69.28, C10 >= 116.27, house >= 36/37 all cleared); a gate-passing alternative,
not the selected arm — Mellum2.1 keeps the SELECTED row.

- **Gate result (2026-11-07, one `.30` boot):** `benchmarking/concurrency-ladder.yaml` @ d0, pp 2048,
  tg 128, n=5, ten real slots reads **C1 73.0 / C2 119.5 / C5 173.2 / C10 133.7 t/s** (prefill 2297-2386
  t/s, ttfr 781 / 1474 / 3268 / 5537 ms); house **37/37** (easy 19/19 + hard 18/18) at
  `--max-tokens 4096` thinking-on; contract ok — `max_model_len` 262,144, `finish_reason` stop, content
  head `READY`. `E = C10 / (C1 x 10)` = **0.183**, reported and never gated. The shape peaks at five
  streams (C5 above C10), which the amended gate leg (2) allows because the ten-slot C10 clears the
  absolute bar.
- **Two boots, not two verdicts.** The gate number is the boot above (ladder plus house/contract on the
  same serve). A second, independent `tools/run-arm.sh` boot read **C1 73.7 / C2 119.9 / C5 176.4 /
  C10 132.1** and tool-eval-bench **97** (15 scenarios: 14 pass, 1 partial, 0 fail) — every cell inside
  the first boot's spread, so the arm's shape is 73-74 C1 into ~130 C10 either way. TTR was not carried
  in the operator's report, and no needle leg was run; the served window is 262,144 if one is wanted.
- **Thinking is the model's default, not a switch.** The GGUF template exposes no `enable_thinking`
  variable and emits a bare `<|assistant|>`, so the model opens its own `<think>` block and
  `--reasoning-format deepseek` is what moves it into `reasoning_content` (contract recorded content
  head `READY`, content length 5). Do not add a thinking toggle to this arm; there is nothing to toggle.
- **Risks checked on the boot:** `--load-mode none` showed no cold-copy stall, `--kv-unified` shared one
  cache across the ten slots (`n_slots` 10), `--flash-attn auto` raised no errors.
- **Four-arm comparison** (queue row `flint-four-arm-comparison`, owner 2026-10-27): one instrument, one
  window per arm, engine named beside every cell. The two A2.5B-active arms are the like pair; the 122B
  is the capability ceiling.

| arm | active / total | C1 | C2 | C5 | C10 | house @4096 thinking-on | tools |
|:--|:--|--:|--:|--:|--:|:--|--:|
| Flint 40B-A2.5B, llama.cpp UD-Q3_K_XL | 2.5B / 39.8B | **73.0** | 119.5 | 173.2 | **133.7** | **37/37** | 97 |
| Mellum2.1 12B-A2.5B, llama.cpp Q4_K_M (ten-slot window) | 2.5B / 12B | 110.52 ± 1.77 | 154.30 | 208.29 | 185.96 ± 2.31 | 36/37 | — |
| Ornith-1.5-35B-A3B, SGLang NVFP4 + DFlash2 | 3B / 35B | 101.8 ± 8.7 | 153.1 | 217.4 | 244.2 | 37/37 | 100 |
| Ornith-1.5-122B, vLLM NVFP4 TP=1 | ~8.9B / 125B | 27.11 | — | — | 73.91 | 37/37 | — |

- **What the comparison says.** Flint sits at 66 % of Mellum's C1 and 72 % of its C10 while carrying
  3.3x the total body at the same 2.5B active per token, and it scores one item higher on the house
  battery (37/37 against 36/37) — the same quality band as the two Ornith arms at a third of the 122B's
  body. So on this instrument it buys quality per active parameter, not throughput per node-second; its
  decode sits below both Ornith arms. The house battery is a 37-item tripwire, not a capability
  benchmark: the card's SWE-bench and Terminal-Bench figures remain vendor claims with no in-tree
  instrument, so nothing here speaks to them.
- **One trap, inherited from the arm's ancestors:** launch against `--cluster WOPR`. A bare `-H` launch
  builds an anonymous cluster whose GGUF matcher sees every quant in the repo (`UD-Q3_K_XL` among nine
  tiers) and can refuse the selection.
- **Receipts:** `head:~/benchmarks/tp12-20261107/flint-40b-a2.5b-ud-q3k-xl-llamacpp/` (gate boot: ladder,
  house, contract) and `...-house/` (the run-arm ladder + tool-eval-bench boot). Artifact: pool
  `models--unsloth--flint-GGUF@20468edf`, `flint-UD-Q3_K_XL.gguf`, 18,494,977,472 B, sha256
  `91b8d85a…`. Repin survey rowed it 2026-11-07 as `no change` at that revision.

## [mellum2.1-12b-a2.5b-q4km-thinking-llamacpp](mellum2.1-12b-a2.5b-q4km-thinking-llamacpp.yaml)

llama.cpp · **1 node (TP=1)** · **kept 2026-10-19 — fastest decode, best aggregate peak, smallest
weights**.

- **Model:** `JetBrains/Mellum2.1-12B-A2.5B-Thinking-GGUF` (Apache-2.0, ungated), quant `Q4_K_M` —
  8,067,705,856 B / 12,149,923,072 params (`/v1/models` meta: `ftype` `Q4_K - Medium`).
- **Engine:** `scitrera/dgx-spark-llama-cpp:b10549-cu131@sha256:ad140554…` (digest-pinned; llama.cpp
  `b2e5e9b`, CUDA 13.1); `n_ctx` 131,072 × 8 slots `kv_unified`; `--load-mode none` (no mmap; GB10
  forces it unless opted back in — the deprecated `--no-mmap` spelling warns, and its
  `--load-mode mmap` hint is the opposite policy); `--jinja`; `--reasoning-format deepseek` splits
  thinking into `reasoning_content` while tool calls keep `finish_reason: tool_calls`.
- **Boot:** 2026-10-17 on `.34`, TTR ≈ 100 s (launch → `/v1/models` 200); served id = the HF repo id
  (`--alias` renders from its own `served_model_name` key, not `{model}` — sparkrun rewrites
  `{model}` to a checkpoint path).
- **Measured (one boot, receipt `~/benchmarks/mellum-gguf-20261017/`):** decode ladder @ d0 pp2048
  tg128 n=5 → **C1 111.9 ± 0.3 / C2 151.1 ± 2.6 / C5 208.0 ± 2.8 / C10 146.4 ± 1.5 t/s**
  (`perf-ladder.yaml`, decode rows; `bench_4247926b7b9a`). Shape: the aggregate peaks at c5 and falls
  at c10 because the arm grants 8 slots and the c10 cell runs 10 streams — per-request decode spreads
  to 32.9 ± 16.1 t/s at c10 (vs 111.9 at c1) while the engine's peak window still reaches 202.2 t/s.
  House battery **37/37** (easy 19/19, hard 18/18); hard arc 77.0% / gsm8k 93.5% (n=200 each);
  `standard-suite` profile (tool-eval-bench) **97** — 15 scenarios, 14 pass, 1 partial; deployability
  84, responsiveness 54 (report — the only copy — `.scratch/explore/mellum-teb-20261017/2026-10-17T07-52-40.740345Z_e604d040.md`); bfcl **88.3%** (1095/1240, no transport errors — audited) at
  `--bfcl-max-tokens 4096`, the suite's new default (`ecddfd4`). This arm is why that flag exists: its
  first leg ran at the old 512 default and scored **73.5%** (911/1240), where **179 of the two
  parallel categories' 400 questions returned `calls: []`** — bare `content: ''` plus a think block
  (median ~2.0k chars against the valid records' 826), a no-call reply being scored FAIL by design
  (`tools/bfcl-eval.py:55-56`). The budget was the mechanism, and it is now measured rather than
  inferred: at 4096 only **6** of those 400 come back with no call, every one of them
  `finish_reason: length` (the field `4f78018` added). The residual parallel-category loss is
  **multi-call shape**: of the 65 failures there, 34 emit exactly one call and 25 emit two or more
  with a wrong set. Category read-out at 4096 — `simple` 94.5%, `multiple` 94.0%, `parallel` 87.5%,
  `parallel_multiple` 80.0%, `irrelevance` 80.8% (46 of 240 called when no call was expected, the
  arm's other loss center). Receipts: 512 leg `~/benchmarks/mellum-gguf-20261017/`, 4096 leg
  `~/benchmarks/mellum-gguf-tools4096-20261017/` (+ its `NOTE-budget-probe.md`, the three-budget probe).
- **Needle:** 131k rung **3/3 PASS** at `paced_target` 128,451 (completions 123–186). 32k rung: 1/3 at
  the suite's 256-token default — the two empty cells are the thinking-budget class below, not
  retrieval; re-probes reach **3/3 by union** (depth 50 PASS at `--max-tokens 4096` — 722 completion
  tokens; depth 90 PASS with `chat_template_kwargs: {"enable_thinking": false}` — 9 tokens, 0.74 s).
- **Ten-slot re-measure (2026-10-22, `.34`; receipt `~/benchmarks/mellum-c10-20261022/`).** The shipped
  recipe byte for byte except `parallel: 10`, `-c 131072 -np 10 --kv-unified`, with the engine logging
  `n_slots = 10, n_ctx_slot = 131072, kv_unified = 'true'` — the unified pool keeps the full 131,072
  per-slot ceiling, so a pp2048+tg128 cell (10 × 2176 ≈ 21.8k tokens) cannot truncate. Ladder @ d0
  pp2048 tg128 n=5 → **C1 110.5 ± 1.8 / C2 154.3 ± 1.6 / C5 208.3 ± 5.7 / C10 186.0 ± 2.3 t/s**. Two
  things this settles. (a) The ten-slot c10 is **39.6 t/s above the 8-slot c10** (186.0 vs 146.4) —
  that is the queue the eight slots imposed, recovered. (b) The aggregate **still falls from c5 to
  c10, −10.7 %**, so the dip was contention and not queueing: per-stream decode runs **41.7 t/s at c5
  vs 18.6 t/s at c10**, i.e. this arm's aggregate peak is five streams and adding more costs total
  tokens/s. Both numbers are right and they measure different things; the 146.4 was slot-limited, the
  186.0 is the real ten-stream figure, and neither is a monotone ladder. House battery at 4096
  thinking-on: easy 56/57 · hard 54/54 = **stable 36/37 tasks** — the one non-stable cell, `needle-1`,
  returned an **empty reply** in one of three repeats and `ZORBULON` in the other two, a serving-side
  empty-content event, not a retrieval miss. Thinking-off, recorded as extra: easy 54/57 · hard 42/54
  = **stable 31/37**, and it leaks raw `</think>` text into `content` — a separate defect.
- **`--no-mmap` is verified, not assumed (2026-10-19).** (Measured under that spelling; shipped today
  as its exact successor `--load-mode none`, common/arg.cpp:2672.) A variant recipe with the flag
  removed (the flag-map key is inert on a template arm, so only a variant can test it) measured
  **C1 108.80 vs 110.64, C2 151.78 vs 151.87, C5 196.48 vs 208.28, C10 143.45 vs 144.82** in a
  same-window pair, mmap ON vs the shipped OFF — the platform's forced default wins, worst at the peak
  cell where a mapped GGUF faults its expert pages through the unified pool. Probe archived
  (`attic/explore/zz-mellum2.1-12b-a2.5b-q4km-thinking-llamacpp-mmap.yaml`); receipt
  `~/benchmarks/mellum-mmap-20261019/`.
  `n_ctx` 131,072 is honored end to end (contract check reads it after the fix below).
  SUPERSEDED 2026-10-29: a maintained copy also stands in this lane
  (`recipes/explore/zz-mellum2.1-12b-a2.5b-q4km-thinking-llamacpp-mmap.yaml`, updated 2026-10-27 for
  the `--load-mode none` spelling) and has its own section below.
- **MTP is measured-rejected across draft lengths (2026-10-22).** The checkpoint's own BF16 MTP head needs
  the stock-upstream `a37cc4610` build (the shipped `b2e5e9b` pin has no `graph_mtp` for `mellum`), so it
  was swept there: `--spec-type draft-mtp --spec-draft-n-max 1…8` gives **103.4 ± 2.8 t/s at `n-max 1`**
  — the vendor's own recommended value, and only **+1.9 %** over that ref's 101.5 ± 0.7 no-MTP baseline —
  then **90.0 / 75.9 / 66.6 / 51.4 / 47.7 t/s** at 2 / 3 / 4 / 6 / 8, i.e. every longer draft is slower
  than plain decoding, with mean accepted length saturating at 2.0–2.3. MTP also doubles prefill (TTFT
  65 → 111–127 ms) and adds ~2 s of load. Do not re-add it, and do not re-test it by raising the draft
  length — 2–4 is the steepest part of the loss. Probe arm
  `zz-mellum2.1-12b-a2.5b-q4km-thinking-llamacpp-mtp.yaml` (`-o spec_draft_n_max=<n>`); receipt
  `~/benchmarks/mellum-mtp-draft-20261022/`.
- **Disposition (owner, 2026-11-03): retained as the retest harness, not retired.** The mechanism
  stays measured-rejected — ~2-5 % at C1, a loss at every batched rung, across n=1…8, three
  quantised heads, KV quant and ubatch — but the arm is kept because its own contract is `-o
  spec_draft_n_max=<n>` plus a ladder at the next engine move, which is cheaper than re-authoring the
  harness. Two things a future retest must not repeat: the historical n-sweep was **single-stream
  only**, so draft length × concurrency was untested until the n=2/n=3 ladders run on 2026-11-03; and
  the c5→c10 fall is **not MTP's** — the plain Mellum GGUF arm shows the same shape with no drafter
  (c5 208.3, c10 186.0, measured 2026-10-22), so a retest that blames the drafter for it is measuring
  the model. Quality stays a standing refusal: 13 pass / 1 partial / 1 fail of 15 on the published
  pin (2026-11-03).
- **Draft length does NOT change the batched math (measured 2026-11-03, `.30`, published `a37cc46`
  engine, full ladders).** The historical n-sweep was single-stream only, so this axis was open; it
  is now closed. Decode `tg128` aggregate, n = 1 / 2 / 3: **c1 98.65 / 103.70 / 88.63**, c2 138.22 /
  134.18 / 113.57, c5 198.64 / 190.73 / 182.91, **c10 141.59 / 141.28 / 133.78**. The c5→c10 fall is
  −28.7 % / −25.9 % / −26.9 % — invariant in draft length — while n=3 is worst at every rung (c1
  −10 %), which matches the 2026-10-22 single-stream finding that longer drafts lose. n=1 (the recipe
  default and the vendor's recommended value) stays the setting.
  **The dip is mostly SLOT STARVATION, and with valid slots the drafter does steepen it.** Three recipes
  in this lane ship `parallel: 8`, so every c10 cell measured on them asks 10 streams of an 8-slot grant —
  the confound this lane already discarded once (146.4 at 8 slots → 186.0 at ten). Same engine, same arm
  pair, one hour apart, with the grant read back out of the serve log (`n_slots = 10`):

  | arm | c1 | c2 | c5 | c10 | c5→c10 | slots |
  |---|---|---|---|---|---|---|
  | plain (no drafter) | 95.30 | 137.02 | 185.13 | **176.30** | **−4.8 %** | 10 |
  | MTP n=1 | 106.90 | 143.61 | 194.85 | **169.85** | **−12.8 %** | 10 |
  | plain, earlier run | 97.48 | 136.32 | 188.40 | 135.97 | −27.8 % | **8** |
  | MTP n=1, earlier run | 98.65 | 138.22 | 198.64 | 141.59 | −28.7 % | **8** |

  Two corrections, and the second undoes the first. The 8-slot cells showed ~−28 % for both arms, which I
  read as the model dipping at concurrency; at ten real slots the plain arm falls only **−4.8 %**, so that
  reading was an artefact of the grant. But at ten slots the **drafter's fall is 2.7x the plain arm's**
  (−12.8 % against −4.8 %), so the amplification claim I had withdrawn is restored on valid cells. What the
  drafter buys on this build: +12.2 % at c1, +4.8 % at c2, +5.2 % at c5 and **−3.7 % at c10** — worth
  having at low concurrency, a loss at the top rung.

  With the grant valid, the draft-length axis closes on three rungs: MTP n=1 **−12.8 %**, n=2 **−13.2 %**,
  n=3 **−10.3 %** — invariant within noise, and all of them roughly double the plain arm's −4.8 %. So the
  earlier "invariant in draft length" reading survives the slot correction, but its *baseline* was wrong:
  the drafter is worth +12.2 % at c1 and costs 8 points of dip at c10, not the other way round.

  Owner decision the same session: **slots ≥ rung is the standard** (`mad-science/METHODOLOGY.md` §3), so
  every ladder containing c10 serves with `parallel >= 10` and states the grant beside the cell; an earlier
  c10 figure whose grant is unknown is treated as slot-limited, not as a concurrency cell.
  Repeatability datum from the same window: n=2 ran twice (17:21 and 17:33) and gave 97.53 vs 103.70
  at c1 — **5.9 % boot-to-boot at c1**, 2.9 % at c5 and 2.6 % at c10 — so single-stream cells on this
  arm carry several percent of noise and no ranking should rest on a <3 % difference at c1. Receipts
  `~/benchmarks/tp12-20261103/zz-mellum2.1-12b-a2.5b-q4km-thinking-llamacpp-mtp{,-n2,-n2.prev-173510,-n3}/`.
- **MTP n=1 retested on a current engine (2026-10-25, owner round-4 §7(c)): the rejection stands.**
  Upstream moved 86 commits past the swept `a37cc4610` (HEAD `d854d98bae`, 2026-10-25; touches
  `llama-graph`/`speculative`/ggml-cuda), so the probe arm was re-pinned *for the retest* to a fresh
  local build (`upstream-d854d98-cu130`, both gates green — never published, so the recipe cannot
  carry it: see the arm's own section for the pin it ships and the CI route that would publish this
  engine) and the n=1 cell re-run with the sweep's own geometry:
  **102.95 ± 3.20 t/s** against a same-window pooled baseline **98.44 ± 3.36** (+4.6 %) — and
  acceptance 0.701 / mean accepted length 1.70 byte-identical to the 2026-10-22 cell, i.e. the
  drafter behaves identically and n=1 remains the only non-worse length, still ~11 % under the
  shipped arm's 114 t/s class. n≥2 was not retested. Receipt
  `~/benchmarks/tp4-single-20261026/mellum-mtp-n1-retest/`. Logistics note: the main GGUF had to be
  re-fetched into the pool hub — the 2026-10-24 migration dedup dropped it fleet-wide (only the
  hand-staged mtp head survived).
- **Quantized MTP heads measured (2026-10-26, spares-lane, `.35`, current `d854d98bae` engine): the rejection stands; the family closes at Q8_0 n=1.** The checkpoint's own quantized heads (pool rev
  `4159d684`, bodies `du`-verified full) at the retest's geometry: Q8_0 n=1 **110.05 ± 3.31 t/s** (+6.9 % over the BF16 head's 102.95, +11.8 % over the same-window plain pooled baseline 98.44; acceptance
  0.701 byte-identical — the drafter behaves identically, only its verify-pass traffic shrank), Q6_K n=1 **107.28 ± 4.12** (less draft traffic is not monotone better — the Q6_K draft's own decode cost
  bites), Q8_0 n=2 **97.36 ± 8.43, acceptance 0.487** — at or below plain decoding, so **n=2 does not re-open with a quantized head** and the 2026-10-22 monotone decline stands at every quantization
  measured. Every cell remains ~9 % under the shipped arm's 121.27 class. Receipt
  `~/benchmarks/spares-20261026/mellum-mtp-head/RECEIPT.md` (receipt-local variants of the zz- probe arm serving the pool snapshot heads).
- **Lever-5 knobs all rejected (2026-10-26, spares-lane, `.35`, shipped arm, same window).** KV q5_1 (k+v) **111.35 ± 2.33** (−8.2 %; with q8_0's −5.3 % the KV-quant direction is monotone negative on this MoE decode — keep fp16); ubatch 2048 **118.12 ± 1.51** (−2.6 %, never above baseline in any run); flash-attn forced `on` **112.16 ± 1.78** (−7.5 % — `auto` does not resolve to the plain `on` path on this
  build, so do not pin it). The shipped configuration (fp16 KV, default ubatch, flash-attn auto) is the best measured configuration of this arm. Receipts `~/benchmarks/spares-20261026/mellum-{kv-q51,ubatch,fa}/`.
- **The thinking-budget trap, this engine's form:** with thinking on (the template's default) a hard
  32k prompt can spend an arbitrary budget inside the think block — empty `content` at
  `finish_reason: length`. Raise `max_tokens` or send `enable_thinking: false`. Found here: the needle
  leg scored that shape FAIL, and llama.cpp's window lives at `meta.n_ctx` (no top-level
  `max_model_len`), so the 2 % clamp never ran and the 131k rung overflowed the window. Both tool-side
  false-FAIL classes are fixed in `e13ccd5` (`tools/needle-haystack.py` records `finish_reason` and
  marks the shape TRUNCATED; both tools read the nested window) — receipt note
  `NOTE-needle-tool-fix.md`.
- **License:** Apache-2.0.
- **Details:** [`mad-science/LLAMACPP-GGUF.md`](../../mad-science/LLAMACPP-GGUF.md) §5 (bring-up +
  suite) and §4 (standing policy: a GGUF sibling must beat the lane battery, not the uploader's table).

## [zz-mellum2.1-12b-a2.5b-q4km-thinking-llamacpp-mmap](zz-mellum2.1-12b-a2.5b-q4km-thinking-llamacpp-mmap.yaml)

llama.cpp · **1 node (TP=1)** · **probe, not shippable — the A side of the GB10 mmap A/B**.

The shipped Q4_K_M Mellum arm with the shipped `--load-mode none` left off, so the GGUF stays mapped
at llama.cpp's default. What to watch: it exists only to price mmap against the shipped arm, so read
it as a same-window pair (the verdict and the receipt are in the parent section above) and never as a
solo number.

## [zz-mellum2.1-12b-a2.5b-q4km-thinking-llamacpp-mtp](zz-mellum2.1-12b-a2.5b-q4km-thinking-llamacpp-mtp.yaml)

llama.cpp (stock-upstream build) · **1 node (TP=1)** · **probe, not shippable — the MTP draft-length harness**.

The Mellum Q4_K_M arm plus the checkpoint's own MTP head — a full draft model in the same repo, served
from the pool snapshot — on the upstream build the shipped pin has no `graph_mtp` for. What to watch:
`-o spec_draft_n_max=<n>` is the knob under test, and the arm is measured-rejected at every draft
length and quantization tried (parent section); its standing use is the retest harness for the next
upstream move.

**Engine pin (re-pinned 2026-11-03).** `container:` is
`littlecedar/dgx-spark-llama-cpp:upstream-a37cc46-cu130@sha256:ef2d4bc8…` — the stock-upstream
`a37cc4610` build, the engine every 2026-10-22 cell in the parent section ran on, and the one image
the tree's other stock-upstream arms already share. The pin it replaces,
`…:upstream-d854d98-cu130`, resolved to no registry at all: unqualified (so Docker Hub) and that tag
is absent there (5 tags, all `a37cc46`/`9df0b73` — read 2026-11-03) *and* in
`ghcr.io/littlecedar/dgx-spark-llama-cpp`, whose only tag is `upstream-a37cc46` (`sha256:09f8ec22…`,
a build this lane has never booted). The `d854d98bae` build was made locally on `.35` and never
pushed; it still sits there as a tag-only image (`upstream-d854d98-cu130`, id `47d3efa2b076`, seen
2026-11-03). Consequences, stated rather than implied: **the 2026-10-26 retest and quantized-head
cells in the parent section are that unpublished engine's**, not this pin's, and the acceptance
number reproduces across both (0.701 / mean len 1.70 byte-identical), so the rejection verdict is
unaffected; and moving the pin **drops the prune protection** the old tag gave that `.35` image.

To pin `d854d98` again, publish it through the existing CI route — no node and no local registry
credentials needed (Actions → `llamacpp-engine` → Run workflow, `llama_ref`
`d854d98bae598388ecea1ed84396587e5edc326d`), which builds
`ghcr.io/littlecedar/dgx-spark-llama-cpp:upstream-d854d98` and prints the digest; pin it qualified,
`ghcr.io/littlecedar/dgx-spark-llama-cpp@sha256:…`, and flip the package public (the workflow's first
push starts private — `AGENTS.md` §"Published artifacts must be public"). The local equivalent is the
recorded build in `attic/explore/AGENTS.md` §"engine bump" with `LLAMA_REF=d854d98bae…`, pushed as
`ghcr.io/littlecedar/dgx-spark-llama-cpp:upstream-d854d98`.

- **Re-measured on the published pin (2026-11-03, `.35`, same recipe, no override).** The repin to
  `upstream-a37cc46-cu130@sha256:ef2d4bc8…` changed the *engine commit*, so the `d854d98` cells above
  are not carried forward and this is a new measurement, not a relabel. Decode `tg128`: **98.65 ± 6.50
  (c1) / 138.22 ± 2.84 (c2) / 198.64 ± 10.08 (c5) / 141.59 ± 0.75 (c10)**; prefill `pp2048`:
  **3458 / 3237 / 3134 / 2010** t/s. Effective streams (`aggregate / per-request`) are 1.93 / 4.23 /
  4.25 at c2/c5/c10, so unlike the 122B DFlash2 case this drafter *does* batch — and it still falls
  28 % from its own c5 peak at c10, which is the shape to explain before any of these numbers is
  called a setting. House: **13 pass / 1 partial / 1 fail** of 15 (`TC-13` did not adapt after an empty
  search response — `wrong_args`; `TC-14` recovered with `web_search` but did not acknowledge the
  error), so this arm is not shippable on quality regardless of its decode. Receipt
  `~/benchmarks/tp12-20261103/zz-mellum2.1-12b-a2.5b-q4km-thinking-llamacpp-mtp/` on the head.
  Engine identity verified from the image, not the tag: `sha256:a28fde60…` carries RepoDigest
  `…@sha256:ef2d4bc8…` with empty `RepoTags` (digest pulls store untagged) and was re-tagged
  `upstream-a37cc46-cu130` immediately, because an untagged image is what a peer's prune deletes.

## [nemotron-3.5-lightning-30b-a3b-nvfp4-vllm](nemotron-3.5-lightning-30b-a3b-nvfp4-vllm.yaml)

vLLM · **1 node (TP=1)** · **kept 2026-10-21 — fastest C1 of any single-node chat arm here**.

*Engine: the shipped `ghcr.io/spark-arena/dgx-vllm-eugr-nightly@sha256:cc47adc1…` (vLLM
0.32.0rc1.dev301+g1ac942555). No new image, no fork.*

- **Model:** `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4` — Nemotron-H hybrid (Mamba-2 + MoE +
  attention, 52 layers, 30B total / 3B active), **20.10 GiB** on the Hub, pinned `bee7596…`; OpenMDW-1.1,
  ungated. The checkpoint carries its own `quantization_config`, auto-detected as **`modelopt_mixed`**;
  NVFP4 GEMM runs on `MarlinNvFp4LinearKernel`, the MoE takes **MARLIN** out of the eight backends the
  engine offers, attention and the Mamba SSU both land on FlashInfer.
- **Boot:** TTR **≈ 6 min** including the 20.1 GiB first download (weights 17.82 GiB loaded in 228.6 s,
  51 piecewise + 2 full CUDA graphs). `/v1/models` → the repo id with **`max_model_len 32768`**, `/health`
  200. KV **10,703,667 tokens** (78.06 GiB at util 0.85) = 326.65× at the served window.
- **Serving traps (each costs an hour):** `--mamba-cache-mode align` from the vendor's flag line is
  **deprecated in this build and does nothing** — Mamba prefix caching follows `--enable-prefix-caching`,
  and the engine forces `mamba_ssm_cache_dtype=float32` for NemotronH itself. CUDA-graph memory profiling
  (default) makes `--gpu-memory-utilization 0.85` effectively **0.8263**; raise it to ~0.874 for a true
  0.85. `vllm/vllm-openai` images declare `ENTRYPOINT ["vllm","serve"]`; this one is NVIDIA's exec wrapper,
  but the recipe clears it so the serve line is the whole command.
- **Measured:** C1 **63.27 ± 0.65 t/s** (peak 65.67) at d0 pp2048/tg128, 3 runs/cell — above Laguna-XS-2.1
  (57.4), Kolibri-1 (47.3) and Laguna-M.1 TP=2 (12.85 C1) in this lane, at 20.1 GiB of weights.
  Ladder **63.27 / 90.81 / 122.27 / 144.15** t/s at c1/2/5/10 (still rising at c10); prefill flat
  **6,142 ± 34 → 6,235 ± 10** t/s; e2e ttft 335.8 → 2,048.3 ms.
- **Campaign ladder (2026-11-03, tp12, `.35`):** C1 **63.37 ± 1.60** · C2 **93.32 ± 1.83** · C5
  **122.71 ± 1.30** · C10 **145.01 ± 1.23 t/s** @ d0, pp2048/tg128, n=5 — reproduces the shipped
  row (63.27 / 90.81 / 122.27 / 144.15) within 3 %, still rising at c10; standard suite
  **87**/100 (15/15, `tool-eval-bench` 2.6.0; deployability 82, responsiveness 69). Receipt
  `~/benchmarks/tp12-20261103/nemotron-3.5-lightning-30b-a3b-nvfp4-vllm/` (`ladder.json`,
  `house.json`).
- **Quality:** house **37/37** (easy 19/19, hard 18/18) with `--max-tokens 2048`. **The budget is part of
  the result:** the first pass at 1024 scored 36/37, missing only `big-1` (`11111` for `1111111110`) —
  re-asked at 2048 the same greedy request answers correctly after **1018 reasoning tokens** with
  `finish=stop`, so that miss was a truncation, not a capability gap. Thinking is on, so budget **≥ 1536**
  completion tokens for any reasoning arm on this instrument.
- **Tool calling:** PASS — `finish_reason: tool_calls` with `get_weather({"location": "Paris",
  "unit": "celsius"})` (populated arguments) under `--tool-call-parser qwen3_coder` and
  `--reasoning-parser nemotron_v3`.
- **Thinking-off, measured — and the number above is thinking-on.** Decode rate and TTFT are
  **mode-independent**: 62.74 t/s thinking-on vs 62.73 off, and on the recipe serve 63.85 vs 63.49, all
  inside each other's spread. Quality is not: house **37/37 thinking-on vs 32/37 off**, the five losses
  being `wp-3`, all three `hard-arith` items and `trick-3`. So the shipped **63.27 t/s and the 37/37 are
  both thinking-on**, the default — and the reasoning channel is **load-bearing for arithmetic and the
  trap items**. A caller must not turn thinking off to save time on this arm; it buys no throughput and
  costs five quality items.
- **First-boot fragility, seen once:** the very first `sparkrun` boot died inside PIECEWISE CUDA-graph
  capture with `CUDA error: an illegal instruction`. It did **not** reproduce across five further
  boots/variants on the same node and image (repo-id with and without `--mamba-cache-mode align`,
  local-path + `--revision`, and a fresh boot). **Retry once before debugging it** — and it is not a
  reason to set the deprecated mamba flag.
- **Not measured here:** needle, ARC/GSM8K, BFCL/TEB, and the vendor's DSpark/DFlash drafters (separate
  repos + `--speculative-algorithm` + block size). The ladder cells spend their 128 generated tokens
  inside reasoning.
- **Receipt:** `head:~/benchmarks/reasoning-candidates-20261021/` (`REPORT.md`, `house.json` @1024 =
  36/37, `house-2048.json` = 37/37, `ladder.json`, `serve.log`).

## Kolibri-1 1M constant-state (eval-only, not a recipe)

**Non-shipped, and must stay that way.** The `tfwnotops/Kolibri-1-78B-…-1M-ConstantKV` release is
**PolyForm-Noncommercial-1.0.0**: it was run from a scratch clone outside the registry, and **no
recipe or mod exists for it**. Measured 2026-10-18, receipt `~/benchmarks/kolibri-state-20261018/`.
*(The shipped Kolibri-1 FP8 base was archived 2026-10-19 — this eval predates that call and stays as
lane history; nothing here is shippable.)*

- **The SM121 question is closed:** the plugin patches FlashInfer for fp8 KV on this chip cleanly —
  FlashInfer's own resolver logs `arch=sm121, kv_cache_dtype=torch.float8_e4m3fn` after the plugin
  swaps its impl, and the boot log carries zero tracebacks.
- **A 1M request is answered with the state active:** a **999,155-token** needle PASSES in **829.7 s**
  (depth 10, `finish_reason: stop`) while `GPU KV cache usage: 0.2 %` of a 10,631,939-token /
  16.15 GiB pool — a native fp8 cache would need 9.5 % of it for the same request.
- **The real cost is the host archive, not attention state:** one 1M request measured **10.44 GiB** of
  host memory (4.76 → 15.20 GiB cgroup peak; host `MemAvailable` fell 11.08 GiB), against the
  release's billed **0.208 GB** — **~54× under**. So on a 121 GiB GB10 the 1M concurrency of this arm
  is **1**, not the 4 `state.rows: auto` assumes (four rows would need ~43 GB, and one request left
  3.9 GiB free).

## [spark-x2.6-4b-bf16-sglang](spark-x2.6-4b-bf16-sglang.yaml)

SGLang · **1 node (TP=1)** · **measured control, 2026-10-22 — bf16 C1 20.38 fails its own ≥25 t/s bar**.

*Engine: no new image, no fork, no mod, nothing staged. `lmsysorg/sglang:v0.5.22-cu130@sha256:e3a4f060…`
ships `srt/models/spark2_5.py` (`Spark2_5ForCausalLM`, per-layer sliding-window RadixAttention, per-type
rope — full layers 5e6/0.25, sliding 1e4/1.0), registers the card's `--tool-call-parser spark25`, and the
checkpoint carries its own `chat_template.jinja`, so there is no `--chat-template` line.*

- **Model:** `XHToken/Spark-X2.6-4B` — 4.11B dense, 36 layers of which **9 full-attention / 27
  sliding-window (window 512)**, GQA 16 heads / 4 KV heads, `head_dim 256`, `hidden 2560`, tied
  embeddings, Apache-2.0, pinned `66e3ae7b…`. Card window 1,048,576; shipped window **131,072**.
- **Boot:** TTR **167.4 s port-open / 252.5 s HTTP-ready** after a 7.67 GiB distribution (288.4 s);
  `/v1/models` → the repo id with **`max_model_len 131072`**; `server_args` carries `--revision
  66e3ae7b…`, `qwen3` reasoning and `spark25` tool parsers, `mem_fraction_static 0.85`; weights 9.27 GB
  in 48.7 s; default `flashinfer` attention backend.
- **Memory — the number an operator gets wrong:** sparkrun's estimator prints "KV demand 18.0 GiB at
  131,072", which is the *all-36-layers-full* arithmetic. The hybrid split makes it **84.48 GB of pooled
  KV**: full pool **723,730 tok (24.84 GB)** + sliding pool **578,984 tok (59.64 GB)**, 14.80 GB spare
  under util 0.85. So the shipped window holds **5.52×** concurrency, and the vendor's 1,048,576 would
  need ~8× that — a multi-node artifact, not a flag.
- **Measured (d0, pp 2048 / tg 128, n=5, decode rows only):** C1 **20.38 ± 0.09** t/s (20.24–20.51); ladder
  **20.38 / 46.38 / 99.27 / 156.20** at c1/2/5/10, still rising at the cap, where the ceiling is
  `max_num_seqs: 32`, not the pool. Prefill 5,259 → 7,499 t/s; TTFR 403 → 1,891 ms.
- **Concurrency knob, one knob, same window:** `--max-running-requests` **96 vs this 32** gave c1
  20.75 ± 0.40 / c2 48.46 ± 1.22 / c5 96.31 ± 6.57 / c10 156.94 ± 0.47 t/s — every delta inside one
  sigma (c10 +0.5 %), so **32 stays**. Ten streams never approached the clamp; the pool at 96 was
  743,780 tokens (7.7k per sequence at full occupancy), so the ladder's ceiling was never the clamp.
- **Falsifier, fired:** the recipe pre-registered "bf16 C1 < 25 t/s demotes bf16 to a control" against the
  8.22 GB weight-traffic roofline (~33 t/s at ~273 GB/s). 20.38 is **61 % of it**, so bf16 is not the
  tier candidate — it is the control that the **FP8/INT8 tiers (4.45 GB each, ≈2× that ceiling)** have to
  beat. That A/B has since run: the FP8 tier doubles C1 at every rung and ties the house score on its
  rerun, so this file is the **accuracy control** and the FP8 arm is the fast tier.
- **Quality:** house **37/37** (19/19 easy, 18/18 hard, 111/111 requests, no flaky) at `--max-tokens 4096`
  on the served default, which is **thinking-on**. Same instrument with
  `chat_template_kwargs {"enable_thinking": false}`: **90/111 = 81.1 %**, **30/37** stable tasks — the
  reasoning channel is load-bearing here too, so a caller must not turn it off to save time.
- **Contract, confirmed on the wire:** default → `reasoning_content` populated (`reasoning_tokens: 18`);
  `enable_thinking: false` → zero reasoning tokens, 2 completion tokens; `reasoning_effort: "low"`
  accepted (not raised); one tool definition returns `finish_reason: tool_calls` with
  `get_weather({"city":"Lisbon"})` parsed by `spark25`.
- **Instrument change:** `tools/quality-battery.py` gained `--thinking on|off`, which sends
  `chat_template_kwargs {"enable_thinking": bool}`; unset sends nothing, so every earlier lane's request
  bytes are unchanged. The thinking-on row above predates the flag and is the served default.
- **Not measured:** needle, ARC/GSM8K, BFCL/TEB, the INT8/INT4 tiers, and any decode-side knob.
- **Receipt:** `head:~/benchmarks/spark-x26-20261022/` (`README.md`, `boot.log`, `serve.log`,
  `ladder.{yaml,json,csv}`, `battery-thinking-{on,off}.json`). Task
  `sparkrun_31a011c489646cf6_2d38dfc4605e` on `.30`, 0 containers before and after.

### The main-image gate (2026-10-25, window 3) — this arm is the instrument

`sglang-main-arm64:6563312` (sglang `main` @ `65633129…`, built on the head 2026-10-24, image
`fe903216cd88`) was boot-gated with this recipe at `-o container=…` — the arm is single-node,
pool-resident, and carries the 2026-10-22 `.30` control, so it is the cheapest like-for-like probe
of a candidate base image. Attempt 1 failed at tokenizer load: the **pool snapshot for
`XHToken/Spark-X2.6-4B` held only `config.json`** — the body did not survive the BeeGFS migration
dedup; one `hf download` (8,239,287,315 B, rc=0) restored it. Gate 1 (C1 n=3): 21.3 t/s. The owner
then raised the bar to the full breakfast (2026-10-25): ladder n=5 decode rows **C1 20.88 / C2
49.53 / C5 99.30 / C10 159.43** vs the control's 20.38 / 46.38 / 99.27 / 156.20 — every delta
inside the run-to-run band (+2.5 / +6.8 / +0.0 / +2.1 %) — and **house 37/37** (134.1 s). Verdict:
**the main image is indistinguishable from the v0.5.22 pin on this arm and passes the adoption
bar**; both `.30` measurements carry the controller-load caveat, but the control carries it too, so
the comparison holds. Receipts `head:~/benchmarks/tp4-window3-20261024/`
(`gate-main-image-launch{,2}.log`, `gate-c1.*`, `gate-full-ladder.*`, `suite-gate-full/`,
`gate-full-node30-serve.log`), tasks `…_57452cfd0e37` / `…_d250d3ad4a0c`, 0 containers after.

## `zz-spark-x26-main-image-sglang` — retired 2026-10-30

The main-image boot-gate probe is **closed and moved to `attic/explore/`**: the gate is answered
(the main-tree image carries the shape indistinguishably from the pinned one — every ladder cell
within 0.3 %, suite 87 both) and its `container:` is a fleet-local tag with no registry behind it, so
no fresh node can pull it. The measurements, both windows and the disposition are in
[`attic/explore/AGENTS.md`](../../attic/explore/AGENTS.md#zz-spark-x26-main-image-sglang--main-image-boot-gate-probe-closed-retired-2026-10-30).

The arm itself — `spark-x2.6-4b-bf16-sglang` — is untouched, and the gate section above stays as the
record of how the probe was run.

## [spark-x2.6-4b-fp8-sglang](spark-x2.6-4b-fp8-sglang.yaml)

SGLang · **1 node (TP=1)** · **shipped 2026-10-22 as the fast tier — 2× the control's C1 at equal house quality**.

The tier A/B the bf16 control was booted for: `XHToken/Spark-X2.6-4B-FP8` (4.47 GB, W8A8
compressed-tensors — weights per-channel symmetric, activations dynamic per-token, on
`q_k_v_proj` / `out_proj` / the MLP regexes; `self_attn.g_proj` stays bf16 per its `ignore` list),
same container, same knobs, **no `--quantization` flag** — the engine auto-detects it.

- **Boot:** quant=compressed-tensors on a hybrid-SWA stack is not a given, and here it works: weights
  **5.52 GB in 24.8 s**, TTR **130.8 s port / 145.6 s HTTP** counting the 4.47 GB distribution, and the
  pools grow to **779,390 full + 623,512 sliding tokens (5.95×)** with 11.38 GB spare.
- **Speed:** ladder **40.80 ± 0.09 / 77.06 ± 2.04 / 146.63 ± 0.15 / 217.58 ± 2.72** at c1/2/5/10 —
  **+100 / +66 / +48 / +39 %** on the bf16 control, i.e. exactly the halved weight traffic, with prefill
  +71 % (8,986 t/s) and TTFR 232 → 1,664 ms.
- **This is the lane's default arm** — boot this file for Spark-X2.6 and keep
  `spark-x2.6-4b-bf16-sglang.yaml` as the accuracy control to compare against. `max_num_seqs: 32` stays:
  the pool holds **779,390 tokens**, so 32 full-window (131,072-token) streams are arithmetically
  impossible — 32 streams of ≈24.4k tokens each is the real ceiling, the ladder was still rising at c10,
  and a clamp cell would have to sweep c 32/48/64/96 to justify anything higher.
- **Quality — and its one rated risk:** the `.33` boot scored house **109/111 = 98.2 %** (easy 19/19
  clean, hard 17/18 stable) with `trick-2` — the 5-machines/5-widgets item — empty on 2 of 3 reps,
  `finish_reason=length` at the 4,096 cap with `content: ''`. The answer is *there*: at
  `--max-tokens 8192` it returns **`5` 3/3**, `finish=stop`, after **159 / 177 / 177** reasoning
  tokens — **not a capability loss**. But it is **not a one-off**: at served defaults and a 4096 cap
  the item came back empty on **4 of 6** reps (.35) plus 2 of 3 (.33) and 0 of 3 (an earlier .35
  pass) — **6 of 12 empty** — against **0 of 3** at 8192, while the **full 37-item battery at 4096
  still scores 37/37 stable** (111/111, no flaky). No other item shows it.
- **Temperature 0 does not remove the runaway** (n=5, `temperature: 0`, 4096 cap, .35): **1 of 5
  empty** at the cap after 4,096 reasoning tokens, the other four answered `5` after **84**
  reasoning tokens each. Greedy *does* remove the wrong-answer mode — **0 of 5 wrong** against
  **2 of 5** at served defaults, which returned `0.25` twice (`finish=stop`, **3,482** and **394**
  reasoning tokens); the default run scored right/wrong/empty = **1 / 2 / 2** of 5. So the trigger
  is **not sampling alone** — the runaway survives greedy decoding (per-request nondeterminism in
  the engine/batch path), and default sampling additionally degrades this item's answer.
- **Retry guidance (ship this with the arm):** serve **`temperature: 0`** for math/single-answer
  prompts (4/5 right, 1/5 empty here); on `finish_reason=length` with empty content **retry once**;
  the stronger mitigation is `max_tokens >= 8192`, where 3 of 3 measured attempts answered and none
  were empty. One empty reply on a reasoning arm is a re-boot, not a verdict.
- **TTFT on its own instrument:** a trivial-prompt streaming TTFT on this tier is **96 ms cold,
  then 35–37 ms warm** (median **35.7 ms**, n=5). The 232 → 1,664 ms pair in the ladder is a
  **2,048-token-prefill first token**, so it is a prefill-inclusive figure — never quote it as a 7×
  per-request regression, and never quote it as measured TTFT.
- **Closed 2026-10-25 (tplt4, `.30`, both cells pre-registered):** the **tool-call contract passes** —
  3/3 reps return `finish_reason: tool_calls` with populated arguments
  (`get_weather({"city":"Lisbon"})`, `spark25` parser, `temperature: 0`, n=3), so the tier's
  agentic surface is proven, not just the bf16 control's. The **clamp cell closes negative**: the
  `--max-running-requests 96` sweep reads **c32 294.5 / c48 272.2 / c64 291.9 / c96 294.7** tg t/s
  (n=5, pp 2048 / tg 128, decode rows) — flat within ±4 % across the whole sweep, c96 +0.07 % on
  c32 — so the shipped `max_num_seqs: 32` stays; the pool arithmetic (779,390 ÷ 96 ≈ 8.1k tokens
  per sequence) never became the constraint because decode is compute-limited well below it.
  Node note: measured on `.30` as a normal worker node (it is a full cluster member; the
  paired-in-window plain control reproduced the 2026-10-22 `.33` numbers within 1.3 %, so the
  controller's mgmtd duties were not a factor at these rates).
- **Receipt:** `head:~/benchmarks/tplt4-20261024/sparkx26/` (`ladder-clamp30.yaml`,
  `tool-call-contract.json`, `ladder-ngram.yaml`, `ladder-plain-ctl30.yaml`, launch logs), 0
  containers after.

- **Not measured:** needle/ARC/GSM8K/BFCL/TEB, INT4. INT8 is answered: kernel-rejected, see the
  `zz-` row below. The tool-call contract and the clamp cell were the FP8 tier's last open cells
  (both closed 2026-10-25, above).
- **Receipt:** `head:~/benchmarks/spark-x26-20261022/` (`boot-fp8*.log`, `serve-fp8*.log`,
  `ladder-fp8.{json,yaml,csv}`, `battery-fp8-thinking-on.json`, `battery-fp8-rerun-4096.json`,
  `flaky-fp8-4096.json`, `flaky-fp8-8192.json`, `temp0-4096.json`,
  `temp-default-4096.json`, `ttft-fp8-repeats.json`, `probe_flaky.py`). Tasks
  `sparkrun_9c8e0fffc3be638_80fa71eb085e` on `.33` (ladder + first battery) and
  `sparkrun_9c8e0fffc3be638_64af2f7668b6` on `.35` (8192 re-ask, rerun, and the n=10 flakiness boot),
  0 containers after each.

## [zz-spark-x2.6-4b-fp8-ngram-sglang](zz-spark-x2.6-4b-fp8-ngram-sglang.yaml)

SGLang · **1 node (TP=1)** · **measured-rejected, 2026-10-25 — NGRAM spec decode is slower than
plain decoding at every rung**.

- **Why it existed:** the "Spark-X2.6 MTP" parked line has no MTP to test — the checkpoint carries
  no mtp/nextn/draft keys (config verified 2026-10-25) and the 16-repo family census has no
  drafter, so the Mellum MTP mechanism is unavailable and **NGRAM** (engine built-in, no draft
  weights, flag shape from the retired IFM K2-Horizon NGRAM arm: breadth 4, draft tokens 8,
  page_size 1) is the only spec route.
- **Measured (paired, same node `.30`, same window, n=5):** NGRAM **38.0 / 69.6 / 134.7 / 189.0**
  vs plain-in-window **40.3 / 75.7 / 143.8 / 214.8** at c1/2/5/10 — **−5.7 % C1 to −12.0 % C10**.
  The pre-registered falsifier fired (spec C1 ≤ plain C1): **NGRAM is measured-rejected for this
  arm, no breadth sweep** — verify cost grew faster than acceptance on a 4B dense whose plain
  decode is already at 5.3× its C1 by c10.
- **Receipt:** `head:~/benchmarks/tplt4-20261024/sparkx26/` (`ladder-ngram.yaml`,
  `ladder-plain-ctl30.yaml`), serve stopped by literal task id, 0 containers after.




## [zz-spark-x2.6-4b-int8-sglang](zz-spark-x2.6-4b-int8-sglang.yaml)

SGLang · **1 node (TP=1)** · **measured-rejected, 2026-10-22 — the engine has no INT8 GEMM kernel for GB10**.

The last untried Spark-X2.6 sibling: `XHToken/Spark-X2.6-4B-INT8` (4.47 GB, int-quantized W8A8 — weights
per-channel symmetric, activations dynamic per-token), same container and knobs as the shipped FP8 tier,
**no `--quantization` flag**. Its repo ships no `chat_template.jinja`, but the 4,766-char template
(`enable_thinking` + `reasoning_effort`) sits in `tokenizer_config.json`, so the chat route was never the
risk.

- **It loads:** quant **compressed-tensors auto-detected**, weights **5.47 GB in 28.08 s**, 107.82 GB free
  after — the same friendly boot the FP8 tier has.
- **Then it dies 57 s in, before serving one request:** during prefill CUDA-graph capture,
  `compressed_tensors_w8a8_int8.apply_weights` → `sgl_kernel/gemm.py::int8_scaled_mm` →
  **`NotImplementedError: No implemented int8_scaled_mm for current compute capability`**. GB10 is
  **sm_121** and the pinned SGLang build ships no INT8 GEMM kernel for it.
- **A hardware/build gate, not a quant-quality question:** no recipe knob reaches it, no quality or ladder
  cell was measurable, and the only unlock is a newer `sgl_kernel` carrying an sm_121 `int8_scaled_mm`.
  Do not re-boot INT8 on `v0.5.22-cu130`; the FP8 tier already gives the same 4.47 GB footprint with a
  working kernel at 2× the bf16 control's C1.
- **Re-booted anyway on 2026-11-03 (21:46:01, one free node) and failed identically** — serve died
  t=98 s on the same `NotImplementedError: No implemented int8_scaled_mm current compute capability`,
  so the verdict above still stands; the recipe now carries
  `metadata.measured_rejected` and the campaign planner prints this citation and plans nothing for it.
- **Receipt:** `head:~/benchmarks/spark-x26-20261022/` (`boot-int8.log`, `serve-int8.log`). Task
  `sparkrun_f30a2cdba68653a9_64af2f7668b6` on `.35`, container removed, 0 containers after.

## [ternary-bonsai-2-9b-q2_0-llamacpp](ternary-bonsai-2-9b-q2_0-llamacpp.yaml)

llama.cpp (upstream `9df0b73-cu130` image, full `prism.hadamard.*` loader) · **1 node (TP=1)** ·
**shipped 2026-10-25 — passes the easy-traffic gate** (C1 ≥ 69.28, C10 ≥ 116.27, house ≥ 36/37
all cleared); a gate-passing alternative, not the selected arm — Mellum2.1 keeps the SELECTED row.

- **Gate result (2026-10-24/25, two boots):** the first ladder/house ran on `.30` (controller-load
  caveat: C1 80.6 PASS / house 36/37 PASS / **C10 107.6, 7.5 % short**); the deciding confirm on a
  quiet `.35` (n=5, `--fresh`, parallel 10, same recipe/image/pin) cleared it —
  **C1 75.51 ± 1.38 / C2 129.24 ± 0.76 / C5 151.95 ± 1.21 / C10 129.79 ± 0.90**, house **36/37** @4096
  thinking-on (miss: `hard-rev`). Bars: C1 ≥ 69.28, C10 ≥ 116.27, house ≥ 36/37 — all three PASS,
  and the `.30` C10 deficit is attributed to controller/mgmtd host load, not the arm. The ladder
  shape **peaks at five streams** (C5 151.95 > C10 129.79 > C2 129.24) — the same genuine
  five-stream peak Mellum2.1 showed, acceptable under the amended gate leg (2) (`QUESTIONS.md #1`)
  because the ten-slot C10 clears the absolute bar.
- **Why it matters:** 2.38 GiB of ternary Q2_0 weights (~1/5 of Mellum's resident footprint) at
  70 % of Mellum's C10 and 68 % of its C1 — the smallest resident footprint of any gate-passing
  arm. Vision (mmproj Q8_0) round-trips (solid-red PNG → "Red"); base64 data-URI images fail in
  this build, use an http URL. Thinking defaults on — budget ≥ 8,192 tokens.
- **Launch trap (recorded 2026-10-25):** a bare `-H` launch builds an anonymous cluster and runs
  sparkrun's GGUF quant matcher at preparation, which dies on `ambiguous GGUF selection` (the
  `*Q2_0*` glob hits `PQ2_0`/`PQ2_0-MTP` too). Launch against `--cluster WOPR`
  (`distribution.model.enabled: false`) — consistent with the recipe's own matcher warning and
  `AGENTS.md`'s anonymous-cluster caveat.
- **Receipts:** `head:~/benchmarks/tp4-lane-20261024/bonsai/` (boot1 functional, ladder/house on
  `.30`), `head:~/benchmarks/tplt4-20261024/bonsai/` (quiet-node ladder + house). TODO item:
  `mad-science/TODO.md` §explore.

## [zz-beam-1.0-501b-a23b-nvfp4-tp4-vllm](zz-beam-1.0-501b-a23b-nvfp4-tp4-vllm.yaml)

`reflection/Beam-1.0-501B-A23B-NVFP4` (501.3B-total / 23.4B-active sparse MoE, 1M window) on
the quartet, engine `vllm/vllm-openai:reflection-beam` (a non-release vendor dev build — the
only published runtime for `BeamForCausalLM`). A capability arm, never the easy-traffic
candidate. Boot-gate PASSED window 3 (kernel falsifier never fired; record `DEEPSEEK.md`
§18.4); the window-4 screen ran the pre-registered cells:

- **Parser engagement PASS (2026-10-26):** the card's `--reasoning-parser beam` /
  `--tool-call-parser beam` are in the recipe (commit 5141c20); `server_args` carries all
  three flags with `--enable-auto-tool-choice`, the smoke content is clean (17×23=391, no
  `<|channel|>` markers), and `reasoning_tokens` populate — the Harmony analysis channel
  parses into `reasoning_content`.
- **Cell (b) PASS:** house **37/37 @4096 thinking-on** (easy 19/19, hard 18/18) on boot 1;
  needle **20/20** at 32,768 and 131,072 (10 depths each) at `--max-tokens 512`. The first
  needle run (0/3) was a **budget-truncation artifact**, not a miss: `finish_reason: length`
  with 61 of 64 completion tokens spent reasoning — the model reasons at max effort (~512
  tokens), so the needle needs the 512 budget (receipts `beam-b1-needle-*.json`).
- **Cell (c) BFCL (partial, tool_choice auto, `--max-tokens 4096`):** the tool-call contract
  works end to end — `finish_reason: tool_calls` with structured arguments on clean probes.
  Scored per-question: simple ~360/400, multiple 115/200 scored-in-run, parallel-family
  misses concentrate in `parallel_function_checker_no_order` (wrong_count /
  cannot_find_match — multi-call formatting), irrelevance 26/30 sampled. The eval-suite
  wrapper stalled 52 min on the tools leg (0 requests served) while direct probes answered
  in 5–18 s — an instrument finding (`bfcl-eval` serial + a 4096-token reasoning budget on a
  max-effort model), not a serve defect. Full-category completion deferred (~30 min per
  category on this arm); receipts `beam-b1-bfcl*.log/json`.
- **Cell (d) DFlash2 A/B:** boot 1 is the no-spec baseline — decode ladder C1 26.20 / C2
  40.66 / C5 63.96 / C10 69.80 t/s aggregate (`beam-b1-ladder.json`). The treatment boot
  carries the vendor's DFlash2 line with window-4 fixes recorded in the recipe history:
  JSON must be inline in the folded `command:` (sparkrun `-o` strips double quotes — dry-run
  proven); comment lines inside the fold become literal arguments; the drafter is named by
  its POOL SNAPSHOT PATH (vLLM's SpeculativeConfig cannot resolve a repo id under
  `HF_HUB_OFFLINE`); and the drafter attention backend is a three-way bind — FLASH_ATTN
  rejects the serve's fp8 KV, FLASHINFER only rejects adaptive verification's device-cpu
  query lens, and unset selects neither, so the shipped pairing is **FLASHINFER + adaptive
  verification OFF** (full 7-token draft verified every step, the vendor's documented
  alternative). **Owner drafter policy 2026-10-26:** the drafter stays attached regardless
  of the measured delta — drafters are optimistically included, exempt from the delta bar.

Receipts: `head:~/benchmarks/tp4-window4-20261026/` (preregistrations, per-attempt serve
  logs, ladder/BFCL/needle JSON). TODO item: `mad-science/TODO.md` §Retry queue window 4.

## [zz-sage-a1.5-35b-a3b-fp8-sglang](zz-sage-a1.5-35b-a3b-fp8-sglang.yaml)

SGLang `v0.5.22` · **1 node (TP=1)** · **DRAFT — not in the selection record**.

`InternScience/Sage-A1.5-FP8`, the vendor's W8A8 compressed-tensors export of the 35.95B-A3B hybrid
linear-attention MoE VLM, at its native 262,144-token window, vision tower left BF16 and the
in-checkpoint MTP head carried. What to watch: `max_num_seqs: 32` is an **unmeasured admission cap** —
the granted concurrency is the hybrid state pool, so read `max_mamba_cache_size` out of the serve log
instead of trusting the literal. The gate plan, the falsifiers and every number this arm has are in
the `mad-science/TODO.md` item **Probe `InternScience/Sage-A1.5`**.

## [zz-sage-a1.5-35b-a3b-q4km-llamacpp](zz-sage-a1.5-35b-a3b-q4km-llamacpp.yaml)

llama.cpp · **1 node (TP=1)** · **PROBE — measured once through the campaign driver, not in the
selection record**.

The vendor's own Q4_K_M GGUF of Sage-A1.5 — trunk plus the bundled vision projector, architecture
`qwen35moe` — on the resident scitrera pin. What to watch: `entrypoint: ""` is load-bearing (the image
keeps `llama-server` as its ENTRYPOINT, which would swallow sparkrun's appended command), and this arm
runs **without** speculative decode, so the in-GGUF MTP block is untested here.

**Campaign measurement (2026-11-07).** First boot through the new campaign driver, `.30`, no
recipe change: prefill `pp2048` **1986.1 ± 53.8** t/s at c1, **1854.5** at c2 (941.4 per stream),
**1032.3** at c5 (426.7), **1025.7** at c10 (271.9); decode `tg128` **73.98 ± 0.67** t/s at c1,
**102.19 ± 0.94** at c2, **85.70 ± 0.87** at c5, **73.77 ± 0.44** at c10; house **15/15
scenarios, score 100**. The c10 cells are slot-limited, not a model result: the recipe ships
`parallel: 4` and the executor refuses a c10 rung under ten slots, so this run waived that gate
with `ARM_ALLOW_FEW_SLOTS=1` — ten streams over four slots, which makes **c5 the aggregate peak**
(prefill 1032.3, decode 85.70). Receipt
`head:~/benchmarks/tp12-campaign-20261107/receipts/zz-sage-a1.5-35b-a3b-q4km-llamacpp.json`;
window `head:~/benchmarks/tp12-20261107/zz-sage-a1.5-35b-a3b-q4km-llamacpp/` (`ladder.json`,
`house.json`, `ladder.yaml`, `serve-solo.log`, `docker-10_0_4_30.log`).

## `zz-kimi-k3.1-pro-superexpert-24b-q4p-ref-vllm`

**Artifact probe, boot-verified and unmeasured (2026-11-08).** Model
`shashanth-27xA9/Kimi-K3.1-Pro-SuperExpert-12GB` pinned `b88a90e8`. No engine loads it:
`architectures: [KimiK31SuperExpertForCausalLM]` exists only in the repo's own `auto_map`, so
vLLM/SGLang resolution fails, and the `gguf` tag points at a 623 B GGUF (v3 magic,
`tensor_count` 0, 11 metadata pairs, arch `kimi_k31_moe`). The only constructible route is the
transformers reference loader under `trust_remote_code`, which is what the arm runs: the mod
`mods/kimi-superexpert-ref-launcher` serves a small OpenAI-compatible surface over it. Full
claim-by-claim probe in
[`mods/kimi-superexpert-ref-launcher/README.md`](mods/kimi-superexpert-ref-launcher/README.md).

**The staged snapshot is the whole artifact and it is dense.** Verified 2026-11-08 in the pool:
33 files, 12,012,326,348 B, `hf cache verify` rc=0 (33/33 checksums match). Its own files say:
- **Dense, not MoE.** 581 tensors with llama-style names (`self_attn.{q,k,v,o}_proj`,
  `mlp.{gate,up,down}_proj`, `embed_tokens`, `lm_head`) and **no** expert/router tensors; the
  modeling code builds one dense `KimiSuperExpertMLP` per layer. Roughly **24 B dense
  parameters** — 36 layers at hidden 7168, MLP 18432, vocab 163840 — not a 2.8 T MoE consolidated
  into 12 GB.
- **~4 bpw storage.** F16 compute plus U8 packed-nibble pairs with one F16 scale per tensor
  (`12,008,815,872` U8 elements); the card's `8-bit` tag and `float16` dtype describe neither.
- **Standard SDPA causal attention, and no positional scheme anywhere in the modeling code** — no
  RoPE, no position ids, while `config.json` declares `max_position_embeddings: 1048576`. NoPE is
  a legitimate long-context design (the Ripple arm in this tree is NoPE at 1M), so the correct
  finding is that **the advertised 1M context is unverifiable from the shipped artifacts**, not
  that it is impossible.
- **The config still advertises MoE the code does not contain:** `moe_intermediate_size: 3072` is
  declared while the MLP path uses `intermediate_size` only. That is the cleanest card/code gap in
  the artifact, independent of how one reads the missing positional scheme.
- **Metadata drift inside the repo:** the config class defaults `compressed_footprint_gb` to
  **9.2** where `config.json` and the card say **12.0**; the `Modelfile` names
  `kimi-k3.1-pro-superexpert-q4_k_m.gguf`, a file that does not exist (the real stub has `-12gb`
  in the name), and claims sub-10 GB.
- **Licence:** no LICENSE file ships. The card's front-matter claims `apache-2.0`; the base
  `moonshotai/Kimi-K3.1-Pro` (`d9e99b07`, 2.78 T params) is `license: other`
  (`kimi-k3.1-pro`), so the licence claim is defective. Quality claims (94.8 % retention, the
  benchmark table) have no harness, fixtures or receipt in the repo.

**Two argument-error attempts, then three healthy boots that could not be measured.** Both early
launches failed in the 2026-11-08 `campaign-queue` window, and the retained attempt's log names the
cause: `serve.py: error: unrecognized arguments: --served-model-name
shashanth-27xA9/Kimi-K3.1-Pro-SuperExpert-12GB`. sparkrun's vllm runtime appends that flag to any
vllm command it renders, and the launcher's argparse did not accept it. `serve.py` now parses it and
reports it from `/v1/models` (then `SERVED_MODEL_NAME`, then the default). The fix is **retested**:
receipts `…prev-074303`, `…prev-075452` and the live directory each reached watchdog
`verdict=healthy` with `/v1/models` 200 (TTR 117.0 / 118.4 / 118.4 s) — and each was then torn down
**without a measurement**, for the structural reason below.

**Acceptance contract: this arm cannot carry a marker, by construction.** Recorded 2026-11-08 so the
next reader does not read the absence as a model defect:
- **What runs after a healthy serve.** `run-arm.sh` runs llama-benchy against
  `benchmarking/concurrency-ladder.yaml` and tool-eval-bench against
  `benchmarking/standard-suite.yaml`, then stops the serve. On these boots the ladder read
  `[1/4] running d=0 c=1 → [1/4] FAILED (2.5–2.7 s)` and the suite `[1/1] FAILED (1.0 s)`, with the
  serve log showing `POST /v1/chat/completions … 400` — the launcher's designed refusal. No
  `ladder.json` and no `house.yaml` are written, so `evidence.done()` reports
  `no marker and no machine-readable artefact`.
- **Why no cell is possible.** llama-benchy 0.4.0 speaks `/chat/completions` only
  (`client.py:177,202,240,267,310`; `--extra-body` merges into chat requests), tool-eval-bench's
  standard suite is a chat/tool instrument, and every chat cell in `h2h-client` routes to
  `quality-battery.py`/`needle-haystack.py`/`bfcl-eval.py`, all chat-only. This serve answers chat
  with 400 **on purpose** (the checkpoint ships no template and the launcher will not fabricate
  one), so no shipped instrument can measure it. `llama-benchy` also probes `/metrics`, `/version`
  and `/props` (404 here); none of those is required for the ladder, the chat 400 is what fails it.
- **The recipe's `command:` shape does not bypass the ladder.** `run-arm.sh` launches through
  sparkrun and then runs both legs against the live serve; they fail on the endpoint's own 400, not
  on being skipped. The proof is the two failed leg logs beside a `serve-*.log` carrying the 400s.
- **`ARM_EXTRA_CLIENT` is supported, was proven here, and is deliberately absent from the row.**
  The hook runs after the cells and before the unconditional stop (the live attempt's
  `extra-client.log` shows it ran with `image=sha256:4ceb…`). It wrote `client/client.json` (cell
  `house4096`, `image_id`, `rc=2`) and `client/house.json` — and that house cell is **0/37 with 37
  HTTP 400 transport errors**: a chat cell against a completions-only serve is an instrument-gap
  artifact, never a quality score. Leaving the hook set would only manufacture that log on every
  boot, so it stays out of the row until a `/v1/completions` client cell exists — do not "restore"
  it as a fix. A markerless arm therefore *can* get a client measurement attempt, but with the
  current cells the result is always these 400s.
- **What acceptance is, then.** A boot-verified probe: watchdog `healthy` + `/v1/models` 200 with
  the served id + `image.txt` (image id) + the two failed instrument logs. The one run with the
  hook also left `client/client.json` with `image_id` and `rc` — the receipt shape a future
  completions cell should reuse. That receipt is the arm's result (the dequant path loads and
  serves); it is not a quality or throughput cell. To get one, a completions-speaking cell has to
  exist — the only shipped completions instrument is `humanizer-measure.py` (rewrite-integrity,
  off-brief here), so that is a tool change, not a recipe knob. Retrying unchanged reproduces
  healthy → no marker → stopped, forever; do not attribute that loop to the model.

**Read any future number as the dense ~24 B artifact's, never as a 2.8 T result.** The arm
registers `tp: 1` because the reference route is the only one constructible on one node; its
launch gate is the mod's `import transformers, fastapi, uvicorn, torch` check against the recipe's
pinned `vllm/vllm-openai:v0.32.0` image (the engine is a carrier for that Python stack, not a
loader for this checkpoint).

## `kimi-k3.1-pro-pruned75-mxfp4-vllm-tp4`

**Servable Kimi body, attempted and blocked at engine bootstrap (2026-11-08).**
`vllm-project/Kimi-K3.1-Pro-pruned75`
pinned `fc72e5a1`: 75 % of the routed experts removed per MoE layer (896 → 224, 92 layers, router
rows and `e_score_correction_bias` pruned with them), everything else the base
`moonshotai/Kimi-K3.1-Pro` ships — MLA attention with the DSA indexer on 24 layers, KDA on the rest,
2 shared experts, dense layer, vision tower, and the original MXFP4 routed-expert quantisation.

- **Size / fit.** 737,611,524,480 parameters = U8 680,685,207,552 MXFP4-packed elements (340.3 GB) +
  BF16 56,915,256,320 (113.8 GB) + F32 11,060,608 (0.04 GB) = **454.2 GB = 423.0 GiB**. Over TP=4
  that is 105.75 GiB per rank against ~121 GiB usable, i.e. 82.6 % of the 128 GB device before KV,
  so the arm ships 32k context at utilisation 0.92. An OOM at profile is sizing, not the checkpoint.
  The pinned `config.json` corroborates the pruning arithmetic: `num_experts: 224`,
  `num_experts_per_token: 16`, `num_shared_experts: 2`, 93 hidden layers with
  `first_k_dense_replace: 1` (so 92 MoE layers), `dsa_config.dsa_layers` listing the 24 full/DSA
  layers, `kda_layers` the other 69, and `quantization_config.format: mxfp4-pack-quantized`.
- **Engine gate: PASSED from the image itself, and now boot-proven.** I pulled the pinned nightly
  arm64 (`0.33.0rc1.dev1016+g06129ab02`, created 2026-11-07) and walked its filesystem: the module
  tree `vllm/models/kimi_k3/` is present and
  `vllm/model_executor/models/registry.py` maps `"KimiK31ForConditionalGeneration"` to it. The same
  image's `vllm/tool_parsers/__init__.py` registers `kimi_k3`, so the serve line's parsers exist.
  On the 2026-11-08 TP=4 attempt the engine printed `Resolved architecture:
  KimiK31ForConditionalGeneration` and `Defaulting to tokenizer_mode='kimi_k3'` — the class
  resolves end to end. Upstream context: the last release tag `v0.33.0rc3` does **not** carry the
  class, which is why this nightly is the earliest known pin rather than any release. Serving needs
  `--trust-remote-code` (config `auto_map`) and the card's `kimi_k3` reasoning/tool parsers. The
  pinned digest still resolves in GHCR, but no node held the image before this boot, which paid the
  pull; the checkpoint was not staged at that moment — the pool held one stub `config.json`, and
  the full body was pulled into it at 08:23–09:38 the same day (see the staging bullet below).
- **No `tokenizer.json` ships, by construction.** The repo carries `tokenization_kimi.py` (a slow
  `PreTrainedTokenizer` subclass), `tiktoken.model` and `tokenizer_class: TikTokenTokenizer` with an
  `auto_map`; that class builds a `tiktoken.Encoding` from the local BPE file. There is no
  `tokenizers` serialization to load, so "missing fast tokenizer" is the checkpoint's own shape,
  **not a defect** — do not file it as one.
- **First boot died on the pool's config-only stub, not on a missing dependency (2026-11-08
  07:47 UTC).** After printing `Resolved architecture: KimiK31ForConditionalGeneration` and
  `tokenizer_mode='kimi_k3'`, `VllmConfig` failed with `Couldn't instantiate the backend tokenizer …
  You need to have sentencepiece or tiktoken installed to convert a slow tokenizer to a fast one`.
  That message is vLLM's generic fallback when no tokenizer file is on disk, and the pinned nightly
  **already carries both backends** — `tiktoken 0.14.0` and `sentencepiece 0.2.3` on
  `/usr/bin/python3` 3.12.3, the only python in the image (verified `docker run --rm --entrypoint
  `python3 <pinned digest>` 2026-11-08). At 07:47 the staged pool snapshot `fc72e5a1` was a
  **config-only stub**: one entry, `config.json` (7,303 B), with `refs/main` beside it and no
  `tokenization_kimi.py`, `tiktoken.model`, `tokenizer_config.json` or weight files. That stub was
  then filled: the same snapshot now holds **112 entries, 96/96 safetensors shards, zero
  `.incomplete` blobs, 475,525,935,884 B = 442.87 GiB** by an inode-deduped `stat` walk,
  `hf cache verify` rc=0, no writer (2026-11-08 11:05 pool read). **Presence is no longer the
  block; fit is.** The shards measure 442.85 GiB, so TP=4 is **110.71 GiB/rank**, and the shipped
  `gpu_memory_utilization: 0.92` (111.95 GiB of the engine's 121.69 GiB total) leaves 1.24 GiB of
  slack before overhead and is **2.23 GiB short** once the measured 3.05 GiB of activation/graph
  overhead and the 0.42 GiB of KDA state are included. The envelope, its inputs and the one bootable
  point are worked out in
  [Fit arithmetic inside one GB10](#fit-arithmetic-inside-one-gb10-2026-11-08-tp4-accepts-16k-rejects-32k-and-the-drafter);
  the recipe shipped that point until the 2026-11-10 boot (below). The 423.0 GiB figure in
  [Size / fit](#kimik31-pro-pruned75-mxfp4-vllm-tp4) is nominal parameter arithmetic and stale for
  fit. An OOM on this arm is therefore a **sizing answer**, not an engine or checkpoint verdict —
  and 2026-11-10 supplied it: see the fit section's measured paragraph (the floor is the weights,
  not the overhead term).
  **Measure presence with `du -sL` or an inode-deduped `stat` walk:** `du -sb` reads 8,179 B even
  for the complete body because every snapshot entry is a symlink into the content-addressed store,
  so it describes a stub and a whole checkpoint identically. Receipt
  `~/benchmarks/h2h-20261107/kimi-k3.1-pro-pruned75-mxfp4-vllm-tp4/`
  (`serve-0.log` lines 13-14, 63-68; launch failed at 76.1 s).
- **Wheelhouse route: proven and kept as a template, unused on this arm.** Staged pinned wheels
  installed as uid 1000 with `pip install --no-index --find-links <dir> --no-deps` (rc=0), followed
  by a real round-trip through the checkpoint's `tiktoken.model`: 13 tokens, decoded text identical
  to input. It is not needed here because the image ships tiktoken; it stays in the record as the
  pattern for an image that does not. Pins: **tiktoken 0.14.0** (cp312
  `manylinux_2_28_aarch64`, sha256 `7db45b98e94adf4173a5cd7422b150999a7ee11ff847783a14f6e1b80cc38cb6`,
  1,186,355 B) plus **regex 2026.11.7** (same tag, sha256
  `c94b8f2fd73b419d5278b8d08d213d042b91edd5acf24ae7226388e9ef106fd4`, 806,351 B). Finding worth
  keeping: under `--no-index` tiktoken's `requests` dependency is invisible to the resolver, so the
  route needs either a staged `requests` wheel or `--no-deps`.
- **Quality, as the card states it.** GSM8K 5-shot 43.67 % on four B300s at TP=4, with "expect a large
  quality regression relative to the source model" in the card. Not a general-purpose candidate.
- **Chat template: none on the Hub.** The repo has no `chat_template.jinja` and
  `tokenizer_config.json` carries no `chat_template` key (the base does not either); formatting is a
  Python `TikTokenTokenizer.apply_chat_template` / `kimi_k3_processor` method that vLLM's Jinja
  path does not use. So the arm expects `/v1/chat/completions` to answer "chat template is not
  defined" and measures on `/v1/completions`; the chat endpoint is tested once as a diagnostic,
  and whichever way it settles is recorded rather than assumed. Code-level corroboration on vLLM
  main (2026-11-08): `renderers/hf.py` resolves the template from `--chat-template`, then an
  AutoProcessor `chat_template` (this repo's `kimi_k3_processor` defaults it to `None`), then the
  tokenizer, then `transformers_utils/chat_templates/registry.py` — a bundled-fallback map with
  only blip2/clip/colpali/ocr/minicpmv/openvla/paligemma/siglip entries and **no** `kimi_k31` or
  `kimi_linear` key. That is why the chat endpoint is expected to refuse.
- **Licence.** `other` / `kimi-k3.1-pro`, inherited with the base's LICENSE link — not Apache-2.0.
- **Acceptance.** Same markerless shape as the DSpark sibling below: no chat template means the chat
  instruments write no ladder and no `house.yaml`, so the serve itself is the evidence. Do not read a
  healthy boot with no marker as an engine failure.

## `kimi-k3.1-pro-pruned75-mxfp4-dspark-vllm-tp4`

**Drafter sibling of the arm above (attempted 2026-11-08; config bind proven; blocked on fit, not
staging).**
Same target and image, plus
`LithosAI/Kimi-K3.1-Pro-DSpark` pinned `d791d217` as a vLLM `dspark` speculator carried in
`defaults.speculative_config` (so sparkrun distributes the draft repo and its own revision). The
draft is a 2.25 B BF16 head (4.50 GB): 5 dense GQA layers, hidden 7168, SwiGLU 14336, reading target
hidden states of layers 7/23/67/83/91 through a `dspark` projector, a rank-256 Markov head and a
confidence head, sharing the target's embedding and LM head. `num_speculative_tokens: 4` is the
trained shape (1 current + 4 drafts against the exported `block_size: 5`), and the Omni-only
`n == block_size` equality check does not run for a Kimi target (bind bullet below); the card's
width-8 acceptance number needs block 8, which this config does not declare. Context is moot until
the fit is worked out: the plain arm's 442.85 GiB of shards is already 110.71 GiB/rank at TP=4,
and the drafter adds its 4.19 GiB on rank 0 (draft TP=1) — see the fit section below, which rejects
this arm at TP=4 outright.

The engine side is verified rather than assumed: the pinned image's `config/speculative.py` declares
`DSparkModelTypes = Literal["dspark"]` and its registry maps both `Qwen3DSparkModel` → `qwen3_dspark`
and a Kimi-native `K3DSparkModel` → `vllm/models/kimi_k3/nvidia/dspark_mla`. One question is
answered and one stays open:

1. **The drafter's config binding is proven (2026-11-08 15:21 UTC, no serve).** In an ephemeral
   container from the pinned nightly, `SpeculativeConfig(method="dspark",
   num_speculative_tokens=4)` accepted the staged target's `config.json` (93 layers, hidden 7168,
   vocab 163,840) and the staged LithosAI draft (`d791d217`): the resolved draft config reads
   `Qwen3DSparkModel`, 5 layers, hidden 7168, `num_target_layers: 93`, `block_size: 5`,
   `target_layer_ids [7, 23, 67, 83, 91]`, `draft_vocab_size: 163840`. Resolving
   `Qwen3DSparkForCausalLM` and constructing it inside `set_current_vllm_config(...)` with a
   one-rank gloo group succeeds: 4,598,107,009 parameters (8.56 GiB BF16 module tree including the
   full-vocab heads, against the 4.19 GiB on-disk pack), 5 decoder layers, `DSparkMarkovHead` +
   `DSparkConfidenceHead`, first layer name `model.layers.93.self_attn.attn` (its start layer id is
   the target's depth, 93), `target_vocab 163840`, `draft_vocab 163840`. The Omni-only
   `_validate_qwen3_omni_dspark` returns early for a non-Omni target, so its `n == block_size`
   equality check never runs here: n=4 with block 5 is accepted because 1 current + 4 drafts is the
   trained shape, not because the target is Omni. The construction needs a device only to pick an
   attention backend (`--gpus none` dies at `ValueError: Invalid attention backend for None`), no
   weights load. So the label is **"config bind proven, acceptance counters pending"**: what
   remains is a real serve — and before that, staging (below). At `max_num_batched_tokens: 2048`
   the engine also emits its speculative-aware advisory `max_num_scheduled_tokens is set to 2048 …
   suboptimal performance`; that is a tuning note, not a bind failure.
2. **Cross-checkpoint acceptance.** The draft was trained against the unpruned base (the card
   declares no base revision) while this target has 75 % of its experts pruned, so the card's 3.448
   mean acceptance length is not transferable to this body — a first-boot measurement, not an
   assumption.

**First boots died in `CacheConfig`, before any weight or draft loaded.** Both arms shipped
`kv_cache_dtype: bf16`, and the pinned nightly's vLLM rejects that spelling: `Value error, Invalid
kv_cache_dtype: 'bf16'. Valid values are: ['auto', 'float16', 'bfloat16', …]` (reaped serve logs
`serve-reaped-…_node_0.log` of the attempts on `.30`–`.33`, 2026-11-08 05:19–05:32 ET). The value
renders straight into `--kv-cache-dtype`, so the engine aborted in argument validation and neither
arm reached model load, let alone speculator init — the drafter-binding question above was therefore
**unproven at that point** (it is now answered at config level, bullet 1). Both recipes now pass
`bfloat16` (2026-11-08 06:05 ET); nothing else about them changed. **Corrected 2026-11-10:**
`bfloat16` only clears `CacheConfig` spelling validation — the SM121 sparse-MLA backend
(`FLASHINFER_MLA_SPARSE_SM120`) requires the packed `fp8_ds_mla` layout and rejects bfloat16 at
backend selection, so both recipes now ship `kv_cache_dtype: fp8_ds_mla`; see the fit section's
measured paragraph.

**Staging: both artifacts are present.** Checked 2026-11-08: the pool's
`vllm-project/Kimi-K3.1-Pro-pruned75` (snapshot `fc72e5a1`) holds the full body — 112 entries,
442.87 GiB by an inode-deduped stat walk, `hf cache verify` rc=0 — and
`models--LithosAI--Kimi-K3.1-Pro-DSpark` (`d791d217`) is staged on `.30`/`.31` with its 4.19 GiB
safetensors. Nothing here waits on a download any more: what blocks the pair is the TP=4 fit
(110.71 GiB/rank of target weights against a 121.69 GiB device, and the drafter's 4.19 GiB on
rank 0), worked out in the fit section below. Chat template is
confirmed absent at the pin: `tokenizer_config.json` has no `chat_template` key and the repo ships
no `chat_template.jinja`, so both arms measure on `/v1/completions`.

**The 07:46 boot's block was staging, not compatibility (2026-11-08).** That boot resolved the target
(`Resolved architecture: KimiK31ForConditionalGeneration`, `tokenizer_mode = 'kimi_k3'`) and then
failed `SpeculativeConfig` with `Invalid repository ID or local directory specified:
'LithosAI/Kimi-K3.1-Pro-DSpark'` — `HF_HUB_OFFLINE=1` with the drafter absent from the pool, so
nothing initialised. The plain arm's tokenizer message was the same kind of staging artifact (the
config-only stub), not an image dependency gap. With the drafter staged, the construction path is
clean: the falsifier at 15:21 UTC built `SpeculativeConfig` and instantiated
`Qwen3DSparkForCausalLM` against the target's `config.json` alone, so the remaining block is the
TP=4 fit (the target's weights alone exceed the util-0.92 budget by ~1 GiB/rank, and the draft adds
~4.5 GiB/rank on top). The label is **"config bind proven, acceptance counters pending; fit recut
needed"**.
Receipt `~/benchmarks/h2h-20261107/kimi-k3.1-pro-pruned75-mxfp4-dspark-vllm-tp4/` (`serve-0.log`
lines 10-71; launch failed at 76.9 s).

**What a successful serve can produce here — no marker.** No Jinja template exists anywhere on the
Hub for this family, so `/v1/chat/completions` refuses; every shipped instrument speaks chat
(llama-benchy 0.4.0, tool-eval-bench's standard suite, `quality-battery.py`), so a healthy vLLM boot
writes **no `ladder.json` and no `house.yaml`**, and an `ARM_EXTRA_CLIENT` house cell returns 37×400
exactly as the SuperExpert probe's does. Acceptance for this arm is therefore the serve itself and
the drafter evidence: `/v1/models` 200 with the served id, `max_model_len` as shipped, and the
DSpark acceptance counters in the serve log (drafts, accepted tokens, mean accepted length) that
settle the binding gate above. That is where the drafter's verdict is read — never from a marker.
"The serve is healthy and no marker appeared" is the expected shape for both Kimi arms (this one and
the plain `kimi-k3.1-pro-pruned75-mxfp4-vllm-tp4`); it is not an engine failure.

### Fit arithmetic inside one GB10 (2026-11-08): TP=4 accepts 16k, rejects 32k and the drafter

**Superseded by measurement 2026-11-10: the arm is rejected at weight-tensor allocation, before
any term this envelope can move — read the measured paragraph at the end of this section. The
envelope below stays as the 2026-11-08 arithmetic record.**

Every input below is checkable from the tree or the fleet.

- **Weights per rank.** The staged shards measure **442.85 GiB**; over TP=4 that is
  **442.85 / 4 = 110.71 GiB/rank**.
- **Device and free memory — two totals, not one.** The engine's own line
  `Free memory on device (…/121.69 GiB)` reports the **kernel-visible total, 121.69 GiB** (earlyoom's
  `mem total: 124608 MiB` is the same number), and `--gpu-memory-utilization` multiplies *that*.
  The other figure in the register rows, **119.21 GiB**, is the nominal `128 GB` label converted at
  2³⁰ (`128e9 / 2³⁰ = 119.209`): a conservative stand-in 2.48 GiB **below** the measured total, not
  a measured pool and not a reserved carve-out. What an engine can actually start in is neither —
  measured **free at startup is 112.33–115.02 GiB** across five boots (`gpu_worker.py` lines under
  `~/benchmarks/`).
- **Non-KV overhead, measured on the same boots.** Peak activation **1.41–2.81 GiB** and CUDAGraph
  **0.07–0.24 GiB**, i.e. **1.48–3.05 GiB/rank**. The arithmetic below uses the pessimistic 3.05;
  the optimistic column is noted only where it changes a verdict.
- **KV per token, from `config.json` (`text_config`).** **24 full-attention layers**
  (`dsa_config.dsa_layers`) with MLA latent `kv_lora_rank 512 + qk_rope_head_dim 64` at BF16, plus
  the DSA indexer key of `index_head_dim 128 + 4 B` scale (`indexer_cache_entry_bytes` returns
  `head_dim + 4` for the bf16/fp8 default):
  `24 × ((512 + 64) × 2 B + (128 + 4) B) = 24 × 1,284 B = 30,816 B = 30.1 KiB/token.`
- **KDA state, from `linear_attn_config`.** The other **69 layers** are linear attention
  (`num_heads 96`, `head_dim 128`, `short_conv_kernel_size 4`) and hold a **per-sequence** state,
  not a per-token cache: recurrent `96/4 × 128 × 128 × 4 B` plus conv
  `((96 × 128 + 2 × 96 × 128) / 4) × 3 × 2 B` per layer →
  `69 × (1,572,864 + 55,296) B = 0.105 GiB per sequence`. The recipe's `max_num_seqs: 4` therefore
  reserves **0.42 GiB**.

Envelope: `budget(U) = 121.69 × U` and
`KV(U) = budget(U) − 110.71 − 3.05 − 0.42`, giving `ctx = KV × 2³⁰ / 30,816`.

| util | budget | after weights + overhead + state | max ctx | free memory it requires |
|---|---|---|---|---|
| 0.92 (as previously authored) | 111.95 | **−2.23 GiB** | 0 | 111.95 |
| 0.935 | 113.78 | −0.40 | 0 | 113.78 |
| 0.94 | 114.39 | 0.21 | 7,200 | 114.39 |
| 0.945 (shipped now) | 115.00 | 0.82 | 28,400 | 115.00 |
| 0.946 | 115.12 | 0.94 | 32,700 | 115.12 — **above the best reading, 115.02** |
| 0.95 | 115.61 | 1.42 | 49,600 | 115.61 — no measured node reports it |

**Both readings of supply, and the verdict each gives.** Demand is 110.71 GiB of weights +
3.05 GiB overhead + 0.42 GiB state = **114.18 GiB**. Against the engine's total
(`0.92 × 121.69 = 111.95 GiB`) the arm has 1.24 GiB of slack before overhead and is 2.23 GiB short
after it; against the nominal label (`0.92 × 119.21 = 109.67 GiB`) it is 1.04 GiB short before
overhead and 4.51 GiB after. The shortfall differs by 2.28 GiB — which is the 2.48 GiB between the
totals scaled by 0.92, not a separate error — but **the verdict does not flip**: no KV
block, let alone a context, fits under either reading, and no measured free memory
(112.33–115.02 GiB) clears the 0.92 pair either way. The shipped point is computed on the engine's
total because that is the quantity `--gpu-memory-utilization` multiplies:
`0.945 × 121.69 = 115.00 GiB`.

Verdict, stated plainly: **32k is infeasible at TP=4.** The authored pair missed by 2.23 GiB once
overhead and state are counted (1.24 GiB of slack before them), and even at util 0.946 the 32k
KV+state (1.36 GiB) needs 115.12 GiB free, 0.10 GiB more than the best measured reading. The recipe
now ships the one point that holds the weights and
a usable context: **`gpu_memory_utilization: 0.945`, `max_model_len: 16384`** (needs 114.65 GiB
free, met by 3 of 5 readings, and leaves 0.35 GiB spare at the pessimistic overhead). A node that
reports less refuses at startup: sizing, not a checkpoint verdict.

**Measured 2026-11-10 — the floor is the weights, not the overhead term (the envelope above is
arithmetic only).** Two quartet boots on `.31`–`.34`, receipt
`head:~/benchmarks/fit-kimi-eager-20261110/`. (1) The shipped `kv_cache_dtype: bfloat16` selects
**no attention backend**: the only sparse-MLA backend this SM121 image carries is
`FLASHINFER_MLA_SPARSE_SM120`, whose constructor raises unless the cache is the packed
`fp8_ds_mla` layout (`flashinfer_mla_sparse_sm120.py:70-74`), so the boot died in 80 s with
`ValueError: No valid attention backend found` before any weight load. (2) With
`--kv-cache-dtype fp8_ds_mla --enforce-eager`, 8192 ctx, 2 seqs and 1024 batched tokens — the
reduced set the 3.05 GiB term would answer to — the boot reached model init and the **weight-tensor
allocation alone** took host `MemAvailable` from 117.4 GiB to **0.79 / 1.79 / 2.03 / 4.07 GiB**
(`.31/.32/.33/.34`, MemFree 0.98–2.16) within one 0.5 s sample, with the rank cgroup at ~11 GiB
and page tables ≤43 MiB — no KV cache, no graph pool, no prefill. The 6.0 GiB guard stopped the
task at its floor; zero kernel `oom-kill` and zero earlyoom lines. So the deciding term is
110.71 GiB of weights + ~8–10 GiB of engine host-side init, not the 3.05 GiB non-KV term: no
context/seqs/graph flag moves it, and the arm needs TP=8, a smaller pruned body or a larger
unified pool. `fp8_ds_mla`'s packed row is 656 B/layer/token (512 fp8 + 16 B scale + 128 B bf16
RoPE tail), so the shipped-dtype KV is 24 × (656 + 132) = **18,912 B/token**, not 30,816; the
table above is kept as the 2026-11-08 bf16 envelope.

**Boot safety, not just fit.** The recut makes this arm arithmetically bootable, not safe to boot:
a quartet attempt that overruns the unified pool takes the **host** down — the 2026-11-08 11:27
kernel OOM killed `ssh`, NetworkManager, syncthing and a dashboard service on a loading node while
earlyoom's swap term was unreachable. Until `QUESTIONS.md` **#67** (whether host memory policy may
change on all nodes) is answered, a TP=4 attempt on this arm is an operator decision with a named
risk, not a routine drain.

**Drafter variant: rejected at TP=4.** The drafter is loaded at its own TP=1, so `rank 0` carries
its **4.19 GiB** on top of the target's 110.71 GiB: 114.90 GiB of weights before any overhead, and
`114.90 + 3.05 + 0.42 = 118.37 GiB` for a no-KV boot at util 0.973 — **3.35 GiB above the best
measured free memory**, so it is impossible here regardless of context. What would make it
feasible: TP=8 (55.4 GiB/rank of target plus 4.19 GiB of draft on rank 0), a smaller pruned
checkpoint, or a host with a larger unified pool.

## Kimi-K3.1-Pro spinoffs: REAPs, drafters and the EXL3 2-bit

Surveyed 2026-11-08 through the Hub's tag filter
(`api/models?filter=base_model:finetune:moonshotai/Kimi-K3.1-Pro&sort=downloads`, 17 repos; the
free-text `other=` query returns unrelated popular models and was not used). Base for every row is
`moonshotai/Kimi-K3.1-Pro` at `d9e99b0792a5e93b78ea9bea62a68167e36ddd9e`, 2.78 T parameters,
licence `other` / `kimi-k3.1-pro`. "Base revision" is the revision the uploader declares it
finetuned/quantised from — a row that declares none was trained against whatever `main` was, which is
why the target pin matters.

| Repo | Revision | Size / dtype | Base revision declared | Format our runtime takes |
|---|---|---|---|---|
| `vllm-project/Kimi-K3.1-Pro-pruned75` | `fc72e5a1` | 737.6 B: 680.7 B U8 MXFP4 elements + 56.9 B BF16 + 11.1 M F32 = 423.0 GiB | none (repo only) | **Yes** — vLLM `KimiK31ForConditionalGeneration` + compressed-tensors `mxfp4-pack-quantized`; shipped as the TP=4 arm above |
| `DaoCloud/Kimi-K3.1-Pro-pruned75` | `8b81479c` | identical parameter map to the row above (737,611,524,480; same dtype split) | none (repo only) | Yes, same path — a mirror of the vllm-project conversion, not authored separately |
| `nota-ai/Kimi-K3.1-Pro-Global-Pruned-30` | `ad8de3c5` | 1.95 T: 1.896 T U8 MXFP4 elements (948.1 GB) + 57.2 B BF16 (114.4 GB) ≈ 1.06 TB / 990 GiB | none | Engine-wise yes, fit-wise no: 990 GiB exceeds 4×~121 GiB; no arm |
| `RadixArk/Kimi-K3.1-Dflash2-Preview` | `ea257b38` | draft 2.7848 B BF16 = 5.57 GB, `DFlash2DraftModel`, MLA 5 layers, block 5, target layers [7,23,51,67,83,91] | **`535833b1b6099ea85659e047561ed0f22ab38db1`** — *not* the base `main` | Yes — vLLM `dflash` method + `qwen3_dflash2` (`DFlash2DraftModel`); higher reported acceptance (GSM8K 5.780 at width 8) but a Preview trained on a different base commit and carded for SGLang |
| `LithosAI/Kimi-K3.1-Pro-DSpark` | `d791d217` | draft 2.2493 B BF16 = 4.50 GB, `Qwen3DSparkModel`, block 5, target layers [7,23,67,83,91], rank-256 Markov + confidence head | none | **Yes, chosen** — vLLM `dspark` method + `Qwen3DSparkModel` registry; used by the DSpark sibling above |
| `lightseekorg/kimi-k3.1-pro-eagle3.1-mla` | `f79e4721` | draft 3.0156 B BF16 = 6.03 GB, `Eagle3DeepseekV2ForCausalLM`, `_torchspec_version 0.1.0`, aux layers [2,46,90] | none | **No** — the card is a pre-release 1/4-epoch checkpoint and validates only its own "K3.1 build" of vLLM (TorchSpec); our image carries neither that build nor the EAGLE class |
| `audnai/penclaw-Kimi-K3.1-pro-unrestricted` | `4ea2457a` | full 2.78 T body (2.7227 T U8 MXFP4 elements + 57.36 B BF16), abliterated | none (base repo) | Engine-wise yes, fit-wise no — the unpruned body cannot fit TP≤4; no arm |

**Recommended drafter: DSpark.** Both DSpark and DFlash2 are taken by the tree's runtime
(`--speculative-config` with `method` `dspark`/`dflash`, pinned in `defaults`), but DSpark's card
declares no competing base revision, its head is the smaller of the two (4.50 GB vs 5.57 GB), and its
config's `block_size: 5` is what the arm ships; DFlash2 is the fallback if first-boot acceptance on
the pruned body disappoints, with its declared `base_model_revision` (`535833b1`, not the base
`main`) on record. Neither
card's acceptance number was measured on a 75 %-pruned target: that measurement is the arm's job.

**EXL3 2-bit: recorded as not bootable, no recipe file.** `local-inference-lab/Kimi-K3.1-Pro-EXL3-2bit`
is an `exl3-v1` (`lut_e4m3`) export: 82,432 routed experts uniformly 2-bit, the 2,748 tensors outside
routed experts at their source bytes, `quant_method: exl3`, `dense_format: bf16`, and — per its card —
**742.235 GiB ≈ 797 GB** of weights, converted from base revision `6d0a0202` (again not the base
`main`). Measured against the Hub tree 2026-11-08: **210 files, 796,971,801,399 B = 742.24 GiB =
796.97 GB**, and **none of it is staged** — the pool has no
`models--local-inference-lab--Kimi-K3.1-Pro-EXL3-2bit` directory, so the download is 0 bytes and the
fit arithmetic below is all that stands between it and an attempt. Two independent walls:

- **Fit, before any engine question.** The fleet's raw aggregate is 6 × 128 GB = 768 GB, and a
  TP=4 launch has 512 GB. Even at six ranks the raw sum is 16 GB short of 797 GB, before the usable
  discount (~121 GiB/node, i.e. ~726 GiB over six) and before KV/activations. No TP≤6
  configuration holds this checkpoint — arithmetic, not a scheduling preference, so it is
  authored-not-booted with that reason and gets no queue row.
- **Runtime.** The card requires an EXL3-aware runtime with Kimi-K3.1 architecture support and says
  Flare/FlashInfer integration "is being developed". Our tree has no such engine: the EXL3 route in
  this registry is TensorFold, whose only shipped family is `deepseek_v41`, and no vLLM/SGLang image
  here implements `quant_method: exl3` for `kimi_k31`. There is nothing to launch, so there is no
  `zz-` recipe pretending otherwise.

Licences in this section are the base's `kimi-k3.1-pro` (`other`) except `RadixArk`'s draft, which is
Apache-2.0, and `lightseekorg`'s, which is `other` with no licence name.

## Ripple-65B Preview (2026-11-08 trial)

`ricursiveAI/Ripple-65B-Preview` is a **65B dense** (not MoE) thin-and-deep model: 80 layers at
d_model 5120 / FFN 40960, 80 Q / 8 KV heads at head_dim 128, gated attention, value residuals,
global NoPE, **16 full-attention layers** among four 1024-token sliding ones, 2,097,152 positions,
vocab 100,352, Apache-2.0 and `gated: false`. The card claims 80.52 on TerminalBench 2.1 and that
it "can fit on consumer hardware such as the NVIDIA DGX Spark". Three `zz-` probes are authored;
**only the BF16 TP=2 cell has booted** (2026-11-08, campaign attempt 3 on two nodes) and it produced
no measurement, so no index row exists for any of them — "no row is given to an arm with no receipt"
holds here too.

**Engine decision, on evidence.** vLLM, and only its **nightly**: `ricursive` support is
[vllm-project/vllm#65745](https://github.com/vllm-project/vllm/pull/65745), which the official
[recipe index](https://recipes.vllm.ai/ricursiveAI/Ripple-65B-Preview) serves as
`vLLM >= 0.33.0 (unreleased — nightly wheel, cu130 only)`, including the `ripple` reasoning/tool
parsers and a native `dflash` speculative method. The fleet's release pin
(`vllm-openai:v0.32.0`) predates the PR and cannot load this architecture at all. All three probes
target one engine build. The two TP=1 cells pin the registry digest
`vllm/vllm-openai:nightly@sha256:390a656b…` (manifest list resolved 2026-11-08, linux/arm64 child
`sha256:0d69205f…`). The BF16 cell that actually booted pins the fleet-local relayed copy of that
same child instead, with the trade stated below — the engine bytes are identical, so a C1 on one
cell is still comparable with a C5 on another.

**Local-only image pin: a deliberate trade (2026-11-08).** No node holds the registry form
(`docker images --digests` on `.30`–`.35`: no `390a656b`, no `0d69205f`), so the only bootable copy
on the head is the one the serve ran: `oci-relay/pinned:4856ba8c07d52fa0…` (image ID
`sha256:e84c490d39a5…`, 26.96 GB, relayed 06:34 UTC). The arm pins that tag with
`distribution_config.containers.enabled: false`, the same shape the SM121 survey arms use, because
sparkrun's distribution would otherwise try to pull a local tag from a registry. **This buys
bootability on the head and gives up runnability from another host** until the image is published
with a RepoDigest: a third party cloning this registry cannot run the arm, and a repin by digest is
impossible while only the local ID exists. Publishing it to GHCR and repinning by the resulting
RepoDigest restores both. Identity is not lost meanwhile — the image ID equals the registry arm64
child's config digest (manifest `0d69205f…` → config `e84c490d…`), so a publish ships the
byte-identical artifact. Note the tag's suffix is the relay's full 64-hex name: there is no short
`:4856ba8c` tag (verified — `docker image inspect` answers no such image), which is exactly the
phantom-tag failure the llama.cpp arms already paid for. The recipe comment carries the tag chain,
the ID and the `docker save … | ssh red@<node> 'docker load'` carry command.

**The two `sleep infinity` containers seen in that window are not strays.** They were this arm's
oci-relay staging pair — the local image had to be relayed onto both rank nodes before the TP=2
boot — and they were gone after the run. Do not re-diagnose them as a leak.

The vendor's SGLang route is real but not servable here as-is: `inference/server/serve.py` pins
`sglang==0.5.19`, registers `RicursiveForCausalLM` into `ModelRegistry` from its own `model.py`,
and runs TRT-LLM attention at TP=2 on B200s; the GB10 path (`inference/local/spark.py`) is an
in-process `Engine` (no HTTP, no port) that monkey-patches the SGLang scheduler for sm_121, and the
fleet's SGLang pins are `v0.5.22` — a version the vendor's export does not claim. Serving that
would be a fork plus a mod, so vLLM wins on evidence, not on the card.

| cell | recipe | weights | TP | engine support | why |
|---|---|---|---|---|---|
| NVFP4 | `zz-ripple-65b-preview-nvfp4-tp1-vllm.yaml` | 57.2 GB (6 shards) → ~53.3 GiB | 1 | vLLM nightly, `modelopt` NVFP4 | the card's own local-serving suggestion; the smallest footprint that fits one Spark |
| NVFP4 + DFlash2 | `zz-ripple-65b-preview-nvfp4-tp1-dflash2-vllm.yaml` | 57.2 GB + 8.07 GB draft | 1 | same, `speculative_config.method: dflash` | drafting is where TP=1 bandwidth-bound decode can gain most |
| BF16 | `zz-ripple-65b-preview-bf16-tp2-vllm.yaml` | 129.57 GB → 120.67 GiB | 2 | same, no quant method | unquantized 6-month quality control, and the only cell that can hold 1M tokens |

**Staged bytes, verified 2026-11-08:** snapshot `da94cc01` holds **27 files, 129,572,840,679 B =
129.57 GB = 120.67 GiB** — the BF16 cell is fully pool-ready. The NVFP4 repos
(`ricursiveAI/Ripple-65B-Preview-NVFP4`, and its DFlash2 draft) are **absent** from the pool, which
is why the two TP=1 cells sit held rather than queued.

**Fit arithmetic** (not measurement). 129.57 GB of BF16 does not fit one GB10's ~109 GiB budget at
util 0.90, so **TP=2 is the floor for BF16**; NVFP4 fits TP=1, which is also the user's lower-TP
preference. KV is **64 KiB/token** — 16 global layers × 8 KV heads × 128 head_dim × 2 (K,V) × 2 B —
split to 32 KiB/rank at TP=2; the 64 sliding layers add only ~256 MiB total. At util 0.90 (108.9
GiB) minus 53.3 GiB of NVFP4 weights, ~55 GiB remains, i.e. ~880k tokens → the NVFP4 probe carries
`max_model_len 524288`; with the 7.5 GiB drafter, ~760k. The BF16 TP=2 arm at util 0.85 leaves ~42
GiB/rank → ~1.36M tokens, so it carries the card's `1048576`. **The card's 1M claim is therefore a
TP=2 cell, not a one-Spark one**, and TP=4 would only split 60 GiB into 30 GiB ranks for no
bandwidth gain past two nodes.

**Measured 2026-11-08, BF16 TP=2 boot** (engine `v0.33.0rc1.dev1030+gcf5cea2da` from the relayed
copy of the pinned nightly; source: the arm's `launch.log`): the card's 1M context is **real at TP=2** —
`Available KV cache memory: 41.3 GiB` on the TP0 worker, `GPU KV cache size: 1,281,286 tokens`,
`Maximum concurrency 1,048,576 tokens per request: 1.22x`, `kv cache group sizes (64, 64, 64, 64,
64)`. The ~1.36M estimate above was 6 % optimistic, not wrong. **The launcher's own fit block is a
false negative on this model**: it printed `KV demand 160.0 GiB bfloat16 at max_model_len
1,048,576`, `KV space 42.9 GiB ~281,208 tokens (0.3x max_model_len)`, `Fit … EXCEEDS` and
`Warning: max_model_len 1,048,576 exceeds KV space (27% fits)`, because it charges all 80 layers as
full attention while 64 of them are 1024-token sliding. Boot it anyway — the warning is not a
refusal, and the engine's own group sizing is what governs. Timings on that boot: containers at
05:32:47, `TTR HTTP-ready 409.948 s` inside a 749.2 s launch, `/v1/models` 200 naming
`max_model_len 1048576`. It measured no cell: the runner closed the arm `rc=1 no container
appeared` 26 s before its containers existed and the serve then ran unguarded and unleased until
~06:09, so the 1M cell still owes its first ladder.

**What the first boot must print to count** (the discriminators, in order): (1) the parser names are
accepted — `--reasoning-parser ripple` / `--tool-call-parser ripple` fail closed with "unknown
reasoning parser" if the nightly lost them; (2) architecture registration — no
`Unsupported model architecture: RicursiveForCausalLM` (nor a `KeyError: 'ricursive'`), and the
config resolves without `--trust-remote-code`; (3) the NVFP4 path — the quantisation log line naming
ModelOpt NVFP4 and the backend it chose (`cutlass_fp4`/`marlin`; a marlin fallback is valid and
slower, a "no kernel image is available for execution on the device" is the rejection); (4) the
drafter cell — `dflash` accepted, the draft's acceptance stats in the log, and the KV/positions
check passing at `max_model_len 131072` (the draft's configured cap).

**Unverified, named.** GB10/sm_121 is in none of the recipe index's hardware rows
(`b200`/`gb200`/`b300`/`gb300`), so the NVFP4 GEMM path on this arch is the single biggest unknown;
the TP=2 1M-token cell is now measured (1,281,286 tokens above), the NVFP4 cells' capacity is still
arithmetic; vLLM caps nothing on the draft's own position limit but the
drafter probe stays at 131072 rather than rely on an override the way the vendor's SGLang launcher
does (`SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN=1`); and the engine itself is a nightly pinned by
digest — a moving target we froze, not a release.

**Recommended pair.** Boot the NVFP4 TP=1 no-drafter cell first (one node, smallest bytes, the
card's own claim), then its DFlash2 twin on the same node to price the drafter; the BF16 TP=2 arm is
the quality control and the only long-context cell. That is three boots, two node-shapes, one
engine digest.

## Attic index

Everything that is not a shipped recipe lives in [`attic/explore/`](../../attic/explore/) — lane working
state, measured histories, selection receipts, serving traps, the candidate research, and the 13
archived recipes (3 Nemotron + 10 from the 2026-10-19 sweep).



| file | what it holds / the question it answers |
|---|---|
| [`AGENTS.md`](../../attic/explore/AGENTS.md) | The lane's working notes: the full previous README — per-arm measured histories (Ling, Kolibri, Nemotron, the Laguna pair, humanizer, Qwen-Image, LTX-2.5), the selection record, and the serving/measurement traps 1–6. Start here for "why did this lane pick what it picked?" |
| [`ARMS-MANIFEST.md`](../../attic/explore/ARMS-MANIFEST.md) | The 2026-10-19 Pareto selection, the 14-row tie-break record, the archived-arm manifest with one receipt per arm, the archived mods/Dockerfile, and the unmeasured-tier classification. |
| [`EXPLORE-MODELS-RESEARCH.md`](../../attic/explore/EXPLORE-MODELS-RESEARCH.md) | The read-only research pass: 8 candidate families (§1), top-3 sequencing (§2), corrections to `attic/explore/EXPLORE-CANDIDATES.md` (§3), the battery note (§4), per-arm GB10 evidence + verification checklists for the Laguna family (§5), the media-gen arms (§6) and `humanizer` (§7), and the 2026-10-16 `tfwnotops/…-ConstantKV` Kolibri-1M research queue entry (§8). Answers "what else could this lane serve, and on what precedent?" |
| [`LTX-25.md`](../../attic/explore/LTX-25.md) | LTX-2.5 bring-up notes: access/prerequisite, the pinned ComfyUI unit, weights, the two-stage measurement table, the traps re-learned. Answers "how was the LTX-2.5 runbook measured, and what did it cost?" |
| [`QWEN-IMAGE.md`](../../attic/explore/QWEN-IMAGE.md) | Qwen-Image-2.1-Turbo bring-up notes: the license banner, engine/venv design decisions, the §6 acceptance table, the two mod defects found, and the faster **vLLM-OMNI route** (measured, not shipped). Answers "how was the eval-only image arm built and verified, and what is the alternative?" |
| [`MELLUM-21.md`](../../attic/explore/MELLUM-21.md) | Mellum2.1-12B bring-up: the owner-added collection provenance, the checkpoint/chat-template facts read at the pin, why vLLM 0.29 needs no mod, the revision resolution, the **GGUF/llama.cpp route decision** and the six open boot questions. |
| [`mods/install-kolibri-plugin/`](../../attic/explore/mods/install-kolibri-plugin) | Archived with its only users (the FP8 base and three 4-bit packs); run an archived arm by path and it resolves adjacent to the recipe. |
| [`mods/kolibri-drafter-launcher/`](../../attic/explore/mods/kolibri-drafter-launcher) | Archived with the TensorFold drafter arm. |
| [`test_kolibri_plugin_mod.py`](../../attic/explore/test_kolibri_plugin_mod.py) | The archived mod's guard (no longer auto-discovered): `uv run python -B -m unittest attic.explore.test_kolibri_plugin_mod`. |
| [`kolibri-1-78b-fp8-vllm.yaml`](../../attic/explore/kolibri-1-78b-fp8-vllm.yaml) | Archived 2026-10-19 — the 2026-10-13 rank-2 pick; 47.2 t/s, 74 GB FP8, superseded by its 4-bit re-packs and Ling. Frozen provenance. |
| [`kolibri-1-nvfp4-experts-vllm.yaml`](../../attic/explore/kolibri-1-nvfp4-experts-vllm.yaml) | Archived 2026-10-19 — the best 4-bit pack (52.4 t/s, 105.6 c10, 37/37), lost the tie to APEX-24bpw on speed and size. |
| [`kolibri-1-nvfp4a16-fp8-vllm.yaml`](../../attic/explore/kolibri-1-nvfp4a16-fp8-vllm.yaml) | Archived 2026-10-19 — 36/37, same speed class as the other packs. |
| [`kolibri-1-mxfp4-mxwave-vllm.yaml`](../../attic/explore/kolibri-1-mxfp4-mxwave-vllm.yaml) | Archived 2026-10-19 — failed its own strict KL screen (0.0551 > 0.030). |
| [`kolibri-1-apex-q4k-llamacpp.yaml`](../../attic/explore/kolibri-1-apex-q4k-llamacpp.yaml) | Archived 2026-10-19 — the 4.50 bpw tier; the 2.4bpw pack wins size and every ladder cell. |
| [`kolibri-1-78b-fp8-tensorfold-drafter-sglang.yaml`](../../attic/explore/kolibri-1-78b-fp8-tensorfold-drafter-sglang.yaml) | Archived 2026-10-19 — +18 % C1 over FP8 but no ladder, a 4-slot cap and a fork JIT landmine. |
| [`poolside-laguna-s-2.1-nvfp4-dflash-vllm.yaml`](../../attic/explore/poolside-laguna-s-2.1-nvfp4-dflash-vllm.yaml) | Archived 2026-10-19 — 95.61 GiB, 20.3 t/s, 33/37; dominated by Laguna-XS on every axis. |
| [`humanizer-12b-vllm.yaml`](../../attic/explore/humanizer-12b-vllm.yaml) | Archived 2026-10-19 — off-brief `/v1/completions` rewriter; 7.6 t/s, no comparable accuracy cells. |
| [`mellum2.1-12b-a2.5b-bf16-thinking-vllm.yaml`](../../attic/explore/mellum2.1-12b-a2.5b-bf16-thinking-vllm.yaml) | Archived 2026-10-19 — the BF16 parent of the kept Q4_K_M arm; dominated on speed, size and measured accuracy. |
| [`mistral-small-4-119b-nvfp4-vllm.yaml`](../../attic/explore/mistral-small-4-119b-nvfp4-vllm.yaml) | Archived 2026-10-19 as measured-rejected — 28.94 t/s, 89,216-token ceiling at 1.01× concurrency. Frozen provenance. |
| [`Dockerfile.kolibri1-tensorfold-drafter`](../../attic/explore/Dockerfile.kolibri1-tensorfold-drafter) | Build provenance for the retired TensorFold drafter image. |
| [`nemotron-3.5-lightning-30b-nvfp4-dspark-vllm.yaml`](../../attic/explore/nemotron-3.5-lightning-30b-nvfp4-dspark-vllm.yaml) | Archived recipe — the lane's original shipped default (262k, util 0.80), the fastest measured arm of its day (77.7 t/s) and the smallest (21 GB), but the lane's lowest accuracy (33/37). Frozen provenance — do not retune. |
| [`nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm.yaml`](../../attic/explore/nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm.yaml) | Archived recipe — a variant of the 262k arm testing the card's 1M-context claim at util 0.91. Frozen provenance — do not retune. |
| [`nemotron-3-super-120b-a12b-nvfp4-vllm.yaml`](../../attic/explore/nemotron-3-super-120b-a12b-nvfp4-vllm.yaml) | Archived recipe — the 123.6B/12.2B-active NVFP4 trial: house 37/37 and a unique one-node 262k window, but 15.9 t/s C1. Boots only after deleting `--swap-space 0` (unrecognized in vLLM 0.29.0). Frozen provenance — do not retune. |
