# Explore lane

Frontier reasoning + tool-calling models for one DGX Spark node. **Selection 2026-10-19** (owner
directive): top candidates are optimized for **generation speed, concurrency, accuracy and small
size**; ties break on the owner's 2026-10-11 weighting — **node count (lower) → accuracy (higher) →
speed (higher) → memory (lower)**. Every measured arm in this lane is 1 node, so node count tied.

The lane now ships **seven measured arms** — the accuracy leader, the smallest 262k arm with
measured headroom, the best 262k aggregate at c10, the fastest/smallest GGUF arm, the media-gen arm
whose cells are closed, the LTX-2.5 video+audio arm booted 2026-10-21, and the Nemotron-3.5-Lightning
30B-A3B NVFP4 arm booted 2026-10-21 (highest C1 of any single-node chat arm here) — plus one
authored-unbooted 2-node arm (`Laguna-M.1`, owned by its own boot item, not a selection candidate). The other **ten** measured arms from the 2026-10-14…18 expansions are
archived with their receipts in [`attic/explore/`](../../attic/explore/) (manifest:
[`ARMS-MANIFEST.md`](../../attic/explore/ARMS-MANIFEST.md)). The 14-row decision table with one
receipt path per arm is [§Selection](#selection-2026-10-19); per-arm measured histories, serving traps
and the full candidate research live in [`attic/explore/AGENTS.md`](../../attic/explore/AGENTS.md) and
[`EXPLORE-MODELS-RESEARCH.md`](../../attic/explore/EXPLORE-MODELS-RESEARCH.md).

## Contents

- [Selection (2026-10-19)](#selection-2026-10-19)
- [ling-3.0-flash-int4-dspark-sglang](#ling-30-flash-int4-dspark-sglang)
- [kolibri-1-apex-24bpw-llamacpp](#kolibri-1-apex-24bpw-llamacpp)
- [poolside-laguna-xs-2.1-nvfp4-dflash-vllm](#poolside-laguna-xs-21-nvfp4-dflash-vllm)
- [qwen-image-2.1-turbo-7b-bf16-diffusers-script](#qwen-image-21-turbo-7b-bf16-diffusers-script)
- [ltx-2.5-22b-nvfp4-t2v-comfyui-script](#ltx-25-22b-nvfp4-t2v-comfyui-script)
- [mellum2.1-12b-a2.5b-q4km-thinking-llamacpp](#mellum21-12b-a25b-q4km-thinking-llamacpp)
- [nemotron-3.5-lightning-30b-a3b-nvfp4-vllm](#nemotron-35-lightning-30b-a3b-nvfp4-vllm)
- [Kolibri-1 1M constant-state (eval-only, not a recipe)](#kolibri-1-1m-constant-state-eval-only-not-a-recipe)
- [LTX-2.5 measured cells (runbook)](#ltx-25-measured-cells-runbook)
- [Attic index](#attic-index)

---

## Selection (2026-10-19)

The four scored axes are **generation speed** (C1 t/s and the ladder's shape), **concurrency** (KV
pool at the shipped window plus any `max_num_seqs` / `parallel` clamp), **accuracy** (house battery,
needle, ARC, GSM8K, BFCL, TEB — whichever the arm actually has), and **size / peak memory**. All 15
measured arms are scored; the verdict column is the selection. Decode rows only
(`is_context_prefill_phase: false`); `×` is the KV pool at the arm's shipped `max_model_len`; a
`max_num_seqs` / `parallel` clamp — not the pool — is the in-flight ceiling where one is set.

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
| `humanizer-12b-vllm` | 7.6 | — (chat endpoint 400s; no ladder) | KV 370,597 tok = 45.2× at 8,192; no chat surface | — · — · — · — · — · — (off-brief; 0 fact losses / 40 rewrites) | 23.9 GB weights / **88 GB repo on disk** · util 0.85 | `~/benchmarks/humanizer-20261014/results.json`, `SUMMARY.md` | **retire** — off-brief, unscoreable on the axes |
| `qwen-image-2.1-turbo-7b-bf16-diffusers-script` | 0.088 img/s (11.33–11.41 s @1024²; **53.24 s @2048²**) | — (one request at a time) | single denoise lock | n/a (non-commercial eval arm; 8-step CFG=1, byte-identical same-seed PNG) | 32.5 GB · peak 36.85/37.68 GiB @1024², **56.51/59.78 GiB @2048²** | `~/benchmarks/qwen-image-20261014/results.json`, `~/benchmarks/media-gen-20261018/REPORT.md` | **KEEP — media-gen cells closed** |
| `mellum2.1-12b-a2.5b-bf16-thinking-vllm` | 42.3 ± 0.1 | 42.3 / 67.2 / 99.9 / 135.6 | util 0.55 (66.6 GiB budget); 131,072; KV grant not captured | 36/37 · — · — · — · — · — | 24.3 GB · util 0.55 | `~/benchmarks/mellum-20261015/perf-ladder.json`, `house.json` | **retire** — dominated by its own Q4_K_M sibling |
| `mellum2.1-12b-a2.5b-q4km-thinking-llamacpp` | **111.9 ± 0.3** | 111.9 / 151.1 / **208.0** / 146.4 (peak c5; c10 exceeds 8 slots) | 131,072 × `parallel: 8`, `kv_unified` = **8 slots** | 37/37 · 3/3 @131k (32k 3/3 by union) · 77.0% · 93.5% · **88.3%** · **97** | **8.07 GB** · no util (llama.cpp sizes its own pool) | `~/benchmarks/mellum-gguf-20261017/perf-ladder.json`, `summary.md`; `~/benchmarks/mellum-gguf-tools4096-20261017/bfcl.json` | **KEEP — fastest decode + best aggregate peak + smallest** |

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
is higher in absolute terms but is 10 streams over an 8-slot grant (its peak is c5) at a 131,072 window.

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
- **License:** base `Aleph-Alpha/Kolibri-1` Apache-2.0; the GGUF pack's own terms are on its card.

## [poolside-laguna-xs-2.1-nvfp4-dflash-vllm](poolside-laguna-xs-2.1-nvfp4-dflash-vllm.yaml)

vLLM · **1 node (TP=1)** · **kept 2026-10-19 — best 262k aggregate at c10**.

*Engine held at digest-pinned `vllm/vllm-openai:v0.29.0` — vLLM 0.30.0 cannot construct this
revision's config (its own `LagunaConfig` shadows the transformers 5.17 class that does); 2026-10-16
engine-bump note in [`attic/explore/AGENTS.md`](../../attic/explore/AGENTS.md).*

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
- **Measured:** C1 **57.4 t/s** @ d0 (σ 3.4) / 55.1 @ d8k; accept len 1.89 / 29.5%; quality 36/37 @4096.
- **Standard suite (2026-10-17, `bench_9b207347ec3b`):** ladder @ d0 pp2048 tg128 n=5 — C1 **55.3**
  (σ 2.4) / C2 83.1 (σ 2.1) / C5 133.7 (σ 8.4) / C10 141.3 (σ 3.3) t/s, the only ladder in the lane
  still rising at c10; `tools/eval-suite.py` 3 ok / 2 fail — house easy 19/19 + hard 16/18, needle
  2/3 @32k / 2/3 @131k / **3/3 @262k** (n=3 each), arc 66.0% (n=200) / gsm8k 90.5% (n=200), bfcl
  60.1% (745/1240); the two fails are **contract** (`finish=length`, all-empty reply at the 262,144
  window — the reasoning parser's empty-`content` shape, thinking burning `max_tokens`) and **needle**
  at the two smaller depths. TEB (`standard-suite.yaml`): 15 scenarios, 14 pass + 1 partial, score 97.
  Receipts `head:~/benchmarks/explore-laguna-xs-20261017/`.
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
- **License:** OpenMDW-1.1 (target and draft).

## [poolside-laguna-m1-nvfp4-vllm-tp2](poolside-laguna-m1-nvfp4-vllm-tp2.yaml)

vLLM · **2 nodes (TP=2)** · **the family's two-node ceiling reference**, booted 2026-10-20.

- **Model:** `poolside/Laguna-M.1-NVFP4` (225B total / 23B active agentic-coding MoE, 70 layers, 262,144
  native) pinned `e4f3ba80…`, engine `vllm/vllm-openai:v0.29.0` by digest.
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

## [qwen-image-2.1-turbo-7b-bf16-diffusers-script](qwen-image-2.1-turbo-7b-bf16-diffusers-script.yaml)

diffusers engine (no `sglang`/vLLM serves it) + [`recipes/explore/mods/qwen-image-2.1-turbo-launcher`](mods/qwen-image-2.1-turbo-launcher) ·
**1 node** · eval-only · **kept 2026-10-19 — media-gen arm whose cells are closed**.

> **LICENSE — NON-COMMERCIAL ONLY.** `Qwen/Qwen-Image-2.1-Turbo` is under the **Qwen Research License
> Agreement** (card `license: other`, `license_name: qwen-research`): **FOR NON-COMMERCIAL PURPOSES
> ONLY**. This registry is distributed to third parties. A recipe ships a repo id, not weights — each
> downloader fetches from the Hub and accepts the license there — but **neither the weights nor images
> generated from them may be used commercially**. An operator needing commercial use must swap the
> checkpoint; the serving path (`recipes/explore/mods/qwen-image-2.1-turbo-launcher` + the recipe) is
> checkpoint-agnostic. **Owner call 2026-10-14: ship the recipe with this banner.**

- **Model:** `Qwen/Qwen-Image-2.1-Turbo` (pinned `fc13ba1986`), text-to-image + editing, 8-step distilled
  at CFG=1.
- **Size / memory:** 32.5 GB bf16 (DiT 14.2 + text encoder 17.5 + VAE 0.68); peak ~36.85 GiB torch alloc /
  37.68 GiB reserved at 1024².
- **Flags / non-obvious knobs:** `runtime: vllm` is the family whose distribution + single-node launcher
  contract the command satisfies; `command:` runs a stdlib HTTP server (`POST /generate`, `GET /health`)
  out of a `diffusers>=0.41` / `transformers>=5.17` venv the mod stages on the image's own torch
  (`vllm/vllm-openai:v0.30.0`; the venv's own `transformers>=5.17` satisfies the card's floor — the
  image's copy is unused). **VAE tiling OFF** (tiled decode → a pink seam column) and **`cpu_offload`
  OFF** (costs ~4× on a reference image); `--served-model-name` is rendered explicitly.
- **Measured:** 1024² / 8-step CFG=1 → **11.3–11.4 s** steady (a same-boot control on the 2048² run read
  11.240 s ± 0.008); a reference image fed back for editing +3.5 s; same prompt+seed → a byte-identical
  PNG. **2048² cell closed 2026-10-18**: **53.24 s/image** (mean of 3, σ 0.20) — 4× the pixels for
  4.74× the time — peak **56.51 GiB** alloc / 59.78 GiB reserved, node `MemAvailable` floor 53.8 GiB;
  the lane's ~26 s prediction is falsified 2.04×. A non-null `num_inference_steps` is accepted silently
  and ignored (`12` still returned `steps: 8`: the pipeline is configured from the checkpoint's saved
  8-step `sample_sigmas`) — since 2026-10-21 an explicit `sigmas` list does take, which is what makes
  the other schedules reachable at all. Receipts `~/benchmarks/qwen-image-20261014/results.json` and
  `~/benchmarks/media-gen-20261021/REPORT.md`.
- **A faster route exists and is not shipped:** `vllm/vllm-omni:nightly` serves this checkpoint
  natively (its own `QwenImage21Pipeline`) at **8.66–8.75 s warm / 11.19 s cold** for the same
  1024² 8-step image, **~24 % faster** than this arm's 11.49 s at *the same* peak memory (36.84 vs
  36.82 GiB) — measured 2026-10-21 on `.34`, one serve per route. It is a **measured alternative, not
  an arm**: it has no recipe, its `num_inference_steps` is inert *and* its own
  `denoise_step_latency_ms` divides one total by the requested count (4/8/12 → the byte-identical PNG
  at 8.7 s while claiming 2164/1086/721 ms per step), and same seed ≠ same image (`38ce554a…` vs this
  arm's `e24f6e3a…`). **Both 8-step images were inspected at full resolution against the prompt**, whose
  string is identical in both recorded bodies (`cells-premod.json` cells 0–1 vs `vllm-omni/omni.json`
  cells 0–3: same `prompt`, 1024×1024, seed 42 — only the CFG spelling differs, `guidance_scale: 1.0`
  in the OMNI request vs CFG=1 from this arm's serve config, plus `use_kv_cache`, which is a
  launcher-only knob), so the divergence is a route property and not a request artifact; and it says
  `two-color screenprint`: this arm honors it — two inks, blue over orange on cream, correct
  spelling, crisp edges — and OMNI **violates** it, rendering `SPARKRUN` as a rainbow of many hues on
  white (correctly spelled and crisply edged, but not two inks). No blended glyphs or step-starvation
  artifacts in either, so the ~24 % win is real and defect-free; it is simply spent on the wrong
  instruction. **That is a prompt-adherence defect, not a style difference** — and it is scoped to one
  prompt, one seed, one image per route, so it is evidence against swapping on latency alone, **not** a
  measured general quality gap. **This arm stays the default**; an OMNI variant would be a *different
  look* the owner likes, i.e. an opt-in arm — **which the owner declined on 2026-10-21: this arm is the
  only route the registry ships, and the OMNI numbers stay in the attic note as a measurement.**
  The §6 "quality judged by eye" item stays open for both routes. Notes:
  [`attic/explore/QWEN-IMAGE.md`](../../attic/explore/QWEN-IMAGE.md) §"vLLM-OMNI route".
- **Details:** [`attic/explore/QWEN-IMAGE.md`](../../attic/explore/QWEN-IMAGE.md).

## [ltx-2.5-22b-nvfp4-t2v-comfyui-script](ltx-2.5-22b-nvfp4-t2v-comfyui-script.yaml)

ComfyUI v0.34.0 (no `sglang`/vLLM engine serves it) + [`recipes/explore/mods/ltx-25-launcher`](mods/ltx-25-launcher) ·
**1 node** · **booted 2026-10-21 on `.35` — first receipt**.

> **LICENSE — read before shipping outputs.** `Lightricks/LTX-2.5` is under the
> **ltx-2.x-community-license-agreement** (card `license: other`): free commercial use for a
> Commercial Entity below a $10M annual-revenue threshold — read
> <https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x>. The repo is **`gated: auto`**: each
> node needs an `HF_TOKEN` whose account accepted the release. A recipe ships a repo id, not weights.

- **Model:** `Lightricks/LTX-2.5` (pinned `49b093a3`) — 22B distilled DiT (nvfp4) + Gemma-4-12B text
  encoder (comfy-int8) + video/audio VAEs + x2 latent upscaler, **36.9 GB**.
- **Engine / staging:** the recipe pins the media-gen lane's arm64 cu130 base
  (`vllm/vllm-openai:v0.30.0@sha256:8a69…`) and the mod stages ComfyUI v0.34.0 plus its exact
  package set and a torch venv (resolved `torch 2.14.1+cu130`, `comfy-kitchen 0.2.31`), then the five
  gated weight files — detached, because the 600 s `pre_exec` hook cannot hold a 36.9 GB fetch.
  `runtime: vllm` is only the launcher/distribution contract.
- **Flags / non-obvious knobs:** `distribution_config.models.enabled: false` (sparkrun's anonymous
  distribution cannot fetch a gated repo); `readiness.inference: false`, `port_timeout_s: 3600` (cold
  stage); `entrypoint: ""` clears the image's `vllm serve`; `--served-model-name` rendered explicitly
  so `/v1/models` answers the repo id. **sparkrun injects `HF_HUB_OFFLINE=1`** — the mod sets it to 0
  for its own fetch (an `unset` inside the `hf` CLI wrapper was not enough).
- **Measured 2026-10-21, `.35`, clock-capped at 2200 MHz**, one boot, seeds 42 then 44 (a same-seed
  rerun is fully cached at 0.01 s), prompt = the template's own positive text, 1344×768 / 121 frames /
  24 fps:

  | cell | wall | peak GiB | output |
  |---|---|---|---|
  | cold (model load in) | **100.13 s** | 84.00 | h264 1344×768, 121 f, 5.0417 s + AAC 5.010 s, 848 KB |
  | warm (seed 44) | **78.1 s** | 83.45 | same container, 1.09 MB |

  Both land on the runbook's own cells (cold 100.3 s, warm 78.1 s, peak 83.6 GiB). The frames are
  real content (luma 96.6 / 166.5 / 164.3 at f0/f60/f120; frame-to-frame Δ 0 / 79.6 / 14.3) and the
  audio is not silent (max −26 dB, RMS −43.8 dB). Cold stage: ComfyUI + venv in 121 s, then 36.9 GB
  of weights in 148 s. Receipt `~/benchmarks/ltx25-recipe-20261021/`.
- **Details:** [`ltx-2.5-runbook/README.md`](ltx-2.5-runbook/README.md),
  [`mods/ltx-25-launcher/README.md`](mods/ltx-25-launcher/README.md).

## [mellum2.1-12b-a2.5b-q4km-thinking-llamacpp](mellum2.1-12b-a2.5b-q4km-thinking-llamacpp.yaml)

llama.cpp · **1 node (TP=1)** · **kept 2026-10-19 — fastest decode, best aggregate peak, smallest
weights**.

- **Model:** `JetBrains/Mellum2.1-12B-A2.5B-Thinking-GGUF` (Apache-2.0, ungated), quant `Q4_K_M` —
  8,067,705,856 B / 12,149,923,072 params (`/v1/models` meta: `ftype` `Q4_K - Medium`).
- **Engine:** `scitrera/dgx-spark-llama-cpp:b10549-cu131@sha256:ad140554…` (digest-pinned; llama.cpp
  `b2e5e9b`, CUDA 13.1); `n_ctx` 131,072 × 8 slots `kv_unified`; `--no-mmap` (GB10 forces it unless
  opted back in); `--jinja`; `--reasoning-format deepseek` splits thinking into `reasoning_content`
  while tool calls keep `finish_reason: tool_calls`.
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
  84, responsiveness 54; bfcl **88.3%** (1095/1240, no transport errors — audited) at
  `--bfcl-max-tokens 4096`, the suite's new default (`3ac9581`). This arm is why that flag exists: its
  first leg ran at the old 512 default and scored **73.5%** (911/1240), where **179 of the two
  parallel categories' 400 questions returned `calls: []`** — bare `content: ''` plus a think block
  (median ~2.0k chars against the valid records' 826), a no-call reply being scored FAIL by design
  (`tools/bfcl-eval.py:55-56`). The budget was the mechanism, and it is now measured rather than
  inferred: at 4096 only **6** of those 400 come back with no call, every one of them
  `finish_reason: length` (the field `c232be0` added). The residual parallel-category loss is
  **multi-call shape**: of the 65 failures there, 34 emit exactly one call and 25 emit two or more
  with a wrong set. Category read-out at 4096 — `simple` 94.5%, `multiple` 94.0%, `parallel` 87.5%,
  `parallel_multiple` 80.0%, `irrelevance` 80.8% (46 of 240 called when no call was expected, the
  arm's other loss center). Receipts: 512 leg `~/benchmarks/mellum-gguf-20261017/`, 4096 leg
  `~/benchmarks/mellum-gguf-tools4096-20261017/` (+ its `NOTE-budget-probe.md`, the three-budget probe).
- **Needle:** 131k rung **3/3 PASS** at `paced_target` 128,451 (completions 123–186). 32k rung: 1/3 at
  the suite's 256-token default — the two empty cells are the thinking-budget class below, not
  retrieval; re-probes reach **3/3 by union** (depth 50 PASS at `--max-tokens 4096` — 722 completion
  tokens; depth 90 PASS with `chat_template_kwargs: {"enable_thinking": false}` — 9 tokens, 0.74 s).
- **`--no-mmap` is verified, not assumed (2026-10-19).** A variant recipe with the flag removed (the
  flag-map key is inert on a template arm, so only a variant can test it) measured **C1 108.80 vs
  110.64, C2 151.78 vs 151.87, C5 196.48 vs 208.28, C10 143.45 vs 144.82** in a same-window pair,
  mmap ON vs the shipped OFF — the platform's forced default wins, worst at the peak cell where a
  mapped GGUF faults its expert pages through the unified pool. Probe archived
  (`attic/explore/zz-mellum2.1-12b-a2.5b-q4km-thinking-llamacpp-mmap.yaml`); receipt
  `~/benchmarks/mellum-mmap-20261019/`.
  `n_ctx` 131,072 is honored end to end (contract check reads it after the fix below).
- **The thinking-budget trap, this engine's form:** with thinking on (the template's default) a hard
  32k prompt can spend an arbitrary budget inside the think block — empty `content` at
  `finish_reason: length`. Raise `max_tokens` or send `enable_thinking: false`. Found here: the needle
  leg scored that shape FAIL, and llama.cpp's window lives at `meta.n_ctx` (no top-level
  `max_model_len`), so the 2 % clamp never ran and the 131k rung overflowed the window. Both tool-side
  false-FAIL classes are fixed in `590b9b2` (`tools/needle-haystack.py` records `finish_reason` and
  marks the shape TRUNCATED; both tools read the nested window) — receipt note
  `NOTE-needle-tool-fix.md`.
- **License:** Apache-2.0.
- **Details:** [`mad-science/LLAMACPP-GGUF.md`](../../mad-science/LLAMACPP-GGUF.md) §5 (bring-up +
  suite) and §4 (standing policy: a GGUF sibling must beat the lane battery, not the uploader's table).

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

## LTX-2.5 measured cells (runbook)

`Lightricks/LTX-2.5` (video+audio world model, 22B distilled DiT + Gemma-4-12B encoder) is measured in
the runbook at [`ltx-2.5-runbook/README.md`](ltx-2.5-runbook/README.md); its T2V cell now ships as the
recipe above — the I2V and FLF2V templates and the 4K/50 preset are measured on the **runbook only**,
not on the recipe, which serves T2V. Weights ≈36.9 GB; T2V/I2V run the two-stage shape (8-step @ 672×384 →
`LTXVLatentUpsampler` ×2 → 3-step refine @ 1344×768); license `ltx-2.x-community-license-agreement`
(free below a $10M-revenue Commercial Entity threshold).
Lane notes: [`attic/explore/LTX-25.md`](../../attic/explore/LTX-25.md).

**Cells measured 2026-10-18** on `.34` (clock cap 2200 MHz; seeds 42 then 44 — a same-seed rerun is
fully cached at 0.01 s, so the second seed is the first non-cached rep). 1344×768 / 121 frames / 24 fps
unless noted. Receipt `~/benchmarks/ltx25-20261018/REPORT.md`.

| cell | template | warm s/clip | peak GiB | what the output actually decodes to |
|---|---|---|---|---|
| T2V control | `video_ltx2_5_t2v.json` | **78.1** | 83.70 | h264 1344×768, 121 frames, 5.0417 s + AAC 5.010 s; frame at t=1.0 s decodes to a PNG (`4da91f2a…`) |
| I2V | `video_ltx2_5_i2v.json` | **84.3** (**+7.9 %**) | 83.79 | same container; frame 0 vs the start image MAD **4.1** (0–255) → the guide is applied, not merely "it decoded" |
| FLF2V | `video_ltx2_5_flf2v.json` | **120.2** (**+54 %**) | 81.94 | same container; frame 0 MAD **7.8** vs start / 59.5 vs end, frame 120 MAD **16.9** vs end / 59.1 vs start → both guides land |
| 4K / 50 fps | `video_ltx2_5_t2v.json`, 3840×2160, 249 f | **OOM** | **121.16 of 121** | **no output** — killed at the ×2 latent upscale |

- **The T2V baseline is 78.1 s, not the recorded 80.1 s** — same cell, same cap, resident weights:
  **−2.5 %** on the 2026-10-14 `.35` figure, so 78.1 is the number to compare against.
- **FLF2V is slower by mechanism, not regression:** that template has no `LTXVLatentUpsampler`, so the
  guides ride one full-res 8-step pass (76.9 s @ 9.6 s/it at 1344×768) instead of half-res 8-step +
  3-step refine — ~1.5× the T2V wall for the same output size.
- **4K/50 is a measured ceiling, not an untried preset:** stage 1 completed (8/8, 461.3 s @ 57.7 s/it
  at the 1920×1080 latent, 249 f) and the process died right after `Requested to load LatentUpsampler`
  with 590 `NV_ERR_NO_MEMORY` kernel lines, at **121.16 GiB of 121** (85.0 GiB steady in stage 1,
  weights-only baseline 78.4 → not a two-tenant artifact). The node stayed up: a process kill, not a
  node loss. 3840×2160×249 does not fit one GB10 with this template.
- **Cold rep = 204.3 s is an upper bound** (it overlapped a peer's serve; model load 25 s, first
  sampler step 12 s, cold tiled VAE decode 82.7 s vs 43.5 s warm). It decodes to the same frame hash
  as the resident-model seed-42 rep — content is seed-deterministic, the h264 mux is not.

## Attic index

Everything that is not a shipped recipe lives in [`attic/explore/`](../../attic/explore/) — lane working
state, measured histories, selection receipts, serving traps, the candidate research, and the 13
archived recipes (3 Nemotron + 10 from the 2026-10-19 sweep).

| file | what it holds / the question it answers |
|---|---|
| [`AGENTS.md`](../../attic/explore/AGENTS.md) | The lane's working notes: the full previous README — per-arm measured histories (Ling, Kolibri, Nemotron, the Laguna pair, humanizer, Qwen-Image, LTX-2.5), the selection record, and the serving/measurement traps 1–6. Start here for "why did this lane pick what it picked?" |
| [`ARMS-MANIFEST.md`](../../attic/explore/ARMS-MANIFEST.md) | The 2026-10-19 Pareto selection, the 14-row tie-break record, the archived-arm manifest with one receipt per arm, the archived mods/Dockerfile, and the unmeasured-tier classification. |
| [`EXPLORE-MODELS-RESEARCH.md`](../../attic/explore/EXPLORE-MODELS-RESEARCH.md) | The read-only research pass: 8 candidate families (§1), top-3 sequencing (§2), corrections to `mad-science/EXPLORE-CANDIDATES.md` (§3), the battery note (§4), per-arm GB10 evidence + verification checklists for the Laguna family (§5), the media-gen arms (§6) and `humanizer` (§7), and the 2026-10-16 `tfwnotops/…-ConstantKV` Kolibri-1M research queue entry (§8). Answers "what else could this lane serve, and on what precedent?" |
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