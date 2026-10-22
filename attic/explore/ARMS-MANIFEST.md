# `attic/explore/` — archived Explore-lane recipes

**What this is.** Every Explore recipe that is **not in the lane's 2026-10-19 Pareto set**, plus the
lane's earlier archives. Everything here is **tracked** (so it is never lost) because a `bench_*` id
is the provenance of a result and the recipe file is the convenience for reading what that id ran.
`recipes/explore/` is a shipped artifact (distributed over git to nodes and third parties); a
measured-but-not-selected arm or a closed-question variant there is clutter and a hazard to the next
reader, who cannot tell a live recipe from a dead one. See `attic/qwen4/ARMS-MANIFEST.md` for the same
policy stated at length.

## Selection 2026-10-19 (owner directive)

**Top candidates are optimized for generation speed, concurrency, accuracy and small size; the rest
moves here.** Ties break on the owner's 2026-10-11 weighting: **node count (lower) → accuracy
(higher) → speed (higher) → memory (lower)**. Every measured arm in this lane is 1 node, so node
count tied and the other three axes decided.

The shipped set after this pass — 5 measured arms plus 1 authored-unbooted arm:

| arm | axis it owns | C1 t/s | concurrency | accuracy (house / hard cells) | size |
|---|---|---|---|---|---|
| `ling-3.0-flash-int4-dspark-sglang` | **accuracy leader** | 49.7 | 100.2 @ c5, 85.9 @ c10; KV 1.20× at 262k, 6 seqs | 37/37 · ARC 94.5 · GSM8K 94.0 · BFCL 88.0 · needle 3/3/3/2 | 77 GB + 2.7 GB draft |
| `kolibri-1-apex-24bpw-llamacpp` | **smallest 262k with measured headroom** | 63.24 | 113.4 @ c2, 78.6 @ c10; 4 slots | 37/37 · no hard cells | 22.7 GiB, **79 GiB available** while serving 262k |
| `poolside-laguna-xs-2.1-nvfp4-dflash-vllm` | **best 262k aggregate at c10** | 55.3 | 141.3 @ c10, still rising; KV 5.59× at 262k, 8 seqs | 35/37 · ARC 66.0 · GSM8K 90.5 · BFCL 60.1 · TEB 97 · needle 2/2/3 | 21.6 GB + 0.92 GB draft |
| `mellum2.1-12b-a2.5b-q4km-thinking-llamacpp` | **fastest decode + best aggregate peak + smallest weights** | 111.9 | 208.0 @ c5, 146.4 @ c10; 8 slots | 37/37 · ARC 77.0 · GSM8K 93.5 · BFCL 88.3 · TEB 97 · needle 3/3 @131k | **8.07 GB** |
| `qwen-image-2.1-turbo-7b-bf16-diffusers-script` | **media-gen, cells closed** | 0.088 img/s (11.33–11.41 s @1024²; 53.24 s @2048²) | one request at a time | n/a (non-commercial eval arm) | 32.5 GB; peak 59.78 GiB @2048² |
| `poolside-laguna-m1-nvfp4-vllm-tp2` | authored, **unbooted** — stays | — | — | — | 139.3 GB / 2 nodes |

> **2026-10-22 correction — the history above is kept as written.** The
> `poolside-laguna-m1-nvfp4-vllm-tp2` row says "authored, **unbooted**", which was true on
> 2026-10-19 and false from **2026-10-20**, when the arm booted on a test pair: `/v1/models` 200
> ≈43 min after launch, then a decode ladder and the standard suite (both in
> [`recipes/explore/README.md` §Laguna-M.1](../../recipes/explore/README.md#poolside-laguna-m1-nvfp4-vllm-tp2)).
> On 2026-10-22 its `container:` pin moved to `vllm/vllm-openai:v0.32.0` for the CVE reason **without**
> a re-boot, so every number quoted for this arm remains a `v0.29.0` measurement.

The full 14-row decision table, with one receipt path per row, is
[`recipes/explore/README.md` §Selection](../../recipes/explore/README.md#selection-2026-10-19).

## Why these and not the rest

- **Kolibri-1 FP8 was the 2026-10-13 rank-2 pick** (37/37 union, 47.2 t/s, 74 GB). Its own 4-bit
  re-packs cut the weights to ~42.6 GiB, lift C1 to 52.4 and c10 to 105.6 at the same 4-slot cap and
  the same house score, and Ling carries the deeper accuracy evidence (ARC/GSM8K/BFCL). The FP8 base
  leads no axis. The best pack (`iSkye/Kolibri-1-NVFP4-Experts`) then loses the tie to the APEX-24bpw
  tier: equal house accuracy (37/37, a saturated battery), **63.8 vs 52.4 t/s** and **22.7 vs 42.6 GiB**.
  The other two packs are 36/37 (budget artifact) and a failed strict-KL screen respectively.
- **The other Mellum arm is the Q4_K_M GGUF's parent.** Same checkpoint, same 131,072 window:
  the GGUF is 111.9 vs 42.3 t/s, 208.0 vs 135.6 aggregate, 8.07 vs 24.3 GB, and carries the
  ARC/GSM8K/BFCL/TEB cells the BF16 arm never measured.
- **Laguna-S is dominated by Laguna-XS** on every axis that is comparable: house 35 vs 33 (of 37),
  C1 55.3 vs 20.3, 21.6 GB vs 95.61 GiB resident, 262,144 vs 98,304 window — and the S draft declares
  no license.
- **Mistral-Small-4 is measured-rejected, not merely unselected:** the authored 262,144 window does not
  boot (72.0 GiB KV needed, 24.51 GiB available), the servable ceiling is **89,216 tokens at 1.01×
  concurrency**, and C1 **28.94** is below every keeper. Its 33/37 default / 36/37 thinking ceiling is
  matched by smaller arms.
- **Humanizer is off-brief** (no reasoning or tool-calling), the slowest measured arm (7.6 t/s), and
  serves only `/v1/completions` — no ladder, no house/needle/ARC/GSM8K/BFCL/TEB cell, so it cannot be
  scored on any of the four axes.

## Unmeasured tiers — recorded, no file to move

The three unrun Kolibri GGUF tiers named by the 2026-10-19 directive — `Hob-forge/Kolibri-1-GGUF`
(`Q2_K … Q8_0`), `webmp3/Sakura-MicroQuality-*` (`IQ4_XS` / `IQ3_XXS` / `IQ2_XS`) and
`aparusel/ds4-kolibri-1-gguf` (plus kirill's MXFP4-GGUF) — were **never authored as recipes**: no such
YAML exists in the tree, so there is nothing to archive. They are classified **unmeasured / not
built**, and cannot win on measurement without a boot. The measured tier ladder already answers their
question in the direction that matters: APEX-2.4bpw (22.70 GiB) beats the 44.98 GiB Q4_K on size **and**
every ladder cell, and the house battery saturates 37/37 for both, so a further tier would have to
produce hard-cell evidence (ARC/GSM8K/BFCL), not another 37/37.

## Selection history (2026-10-13)

The first pass kept two arms under the owner's accuracy-first criterion:

| rank | arm | accuracy | memory | C1 t/s | outcome |
|---|---|---|---|---|---|
| 1 | `ling-3.0-flash-int4-dspark-sglang` | **37/37** | 154 GB | 45.5 | **KEPT** — accuracy champion (still kept 2026-10-19) |
| 2 | `kolibri-1-78b-fp8-vllm` | 36/37 (**37/37 union** — the lone miss is a thinking-budget truncation) | 74 GB | 47.3 | kept then; archived 2026-10-19 (its 4-bit re-packs and Ling supersede it) |
| 3 | `nemotron-3.5-lightning-30b-nvfp4-dspark-vllm` | 33/37 | 21 GB | 77.7 | archived — fastest then, but the lane's **lowest accuracy** |
| — | `nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm` | 33/37 | 21 GB / 0.91 | 72.2 | archived — a variant of the 262k recipe; its question (the card's 1M claim) is closed |

**Added 2026-10-18 — `nemotron-3-super-120b-a12b-nvfp4-vllm`.** Trial complete, no lane slot. It ranks
below `mistral-small-4-119b-nvfp4-vllm` (itself rejected at 28.9 t/s C1): 15.9 t/s against 28.9 at
equal-or-better accuracy (house 37/37). Full numbers, the params correction and the two boot defects are
in its manifest row below.

## Manifest

| file | runtime | one-line delta | why archived | where its facts now live |
|---|---|---|---|---|
| `kolibri-1-78b-fp8-vllm.yaml` | vLLM 0.29 + plugin | the 2026-10-13 rank-2 pick; 74 GB FP8; C1 **47.2 ± 0.1**, ladder 47.2 / 76.2 / 77.6 / 83.5; KV 1,859,922 tok; house 37/37 | **No axis lead.** Its own 4-bit packs are 42.6 GiB at 52.4 t/s / 105.6 c10 / 37/37, and Ling carries the deeper accuracy evidence (ARC 94.5 / GSM8K 94.0 / BFCL 88.0). Not fastest, not best aggregate, not smallest, not accuracy leader. | Ladder `~/benchmarks/ladders-solo-20261018/kolibri-ladder.json`, battery `kolibri-battery-8192.json`; history in [`AGENTS.md`](AGENTS.md) §Kolibri-1. |
| `kolibri-1-apex-q4k-llamacpp.yaml` | llama.cpp (fork) | uniform 4.50 bpw; C1 **57.67 ± 0.21**; ladder 56.16 / 90.23 / 83.25 / 67.50; 41.89 GiB; house 37/37 | The 2.4bpw tier wins both measurable axes (−8.8 % d0, −11.3 % d8192, −20/−15/−14 % at c2/c5/c10 for nearly double the weight bytes). Q4_K's only claimed edge is the uploader's KLD figure, which the house battery cannot see — 37/37 has **zero ranking power**. | `~/benchmarks/kolibri-gguf-20261018/q4k/` (`q4k-ladder.json`, `q4k-triage.json`, `q4k-battery.json`). |
| `kolibri-1-78b-fp8-tensorfold-drafter-sglang.yaml` | SGLang shim + TensorFold fork | C1 **55.6 ± 5.9** (d8192 54.6) at acceptance 1.91; house 37/37; 4 streams @ 262,144 | +18 % C1 over FP8, but **no ladder** (aggregate unmeasured), a 4-slot cap, and it loses the tie to APEX-24bpw (63.8 C1, 22.7 GiB) and to the packs (105.6 c10 at the same cap). The fork also needs one successful completion before it is benchable — a fresh boot can serve 500s behind a ready port. | `~/benchmarks/kolibri-mtp-20261018/mtp-triage.json` + `house/summary.json` + `REPORT.md`. |
| `kolibri-1-nvfp4a16-fp8-vllm.yaml` | vLLM 0.29 + plugin | 42.69 GiB NVFP4-A16; C1 **52.48 ± 0.21**; ladder 52.11 / 91.64 / 95.15 / 106.39; KV 4,606,739 tok; house **36/37** | Loses the accuracy tie to iSkye's 37/37 (its miss is a needle-budget artifact, but the other pack does not have one), same speed class as the other two packs, no axis lead. | `~/benchmarks/kolibri-quants-20261018/quantinine/` (`c2c5c10-ladder.json`, `triage.json`, `battery.json`). |
| `kolibri-1-nvfp4-experts-vllm.yaml` | vLLM 0.29 + plugin | 42.6 GiB; C1 **52.37 ± 0.05**; ladder 52.00 / 91.58 / 95.03 / 105.58; KV 4,618,726 tok; house 37/37 | The best of the three packs, but the tie-break decides against it: **APEX-24bpw is faster (63.8 vs 52.4) and smaller (22.7 vs 42.6 GiB) at equal house accuracy**, and Laguna-XS owns high-concurrency 262k with 10 real in-flight requests. The card's 265.9 t/s at c8 does not reproduce (198.6 at 8 slots, 136.1 at the shipped 4). | `~/benchmarks/kolibri-quants-20261018/iskye/` (`c2c5c10-ladder.json`, `triage.json`, `battery-4096.json`). |
| `kolibri-1-mxfp4-mxwave-vllm.yaml` | vLLM 0.29 + plugin (`--moe-backend marlin`) | 40.93 GiB; C1 **51.60 ± 0.16**; ladder 51.41 / 92.64 / 96.28 / 108.20; house 37/37 | **Failed its own strict KL screen** — 0.0551 nats against a 0.030 threshold (PPL +1.53 %, German +2.20 %, code +3.24 %), so its 37/37 is not quality parity. No axis lead. | `~/benchmarks/kolibri-quants-20261018/kirill/` (`perf-ladder.json`, `decode-triage.json`, `quality-battery.json`). |
| `poolside-laguna-s-2.1-nvfp4-dflash-vllm.yaml` | vLLM 0.29 | 95.61 GiB resident; 98,304 window; C1 **20.26 ± 0.87**; ladder 20.26 / 29.26 / 38.96 / 53.80; house 33/37 | **Dominated by Laguna-XS on every axis**: accuracy 35 vs 33 (of 37), C1 55.3 vs 20.3, 21.6 GB vs 95.61 GiB, 262,144 vs 98,304 window. The shipped S draft also declares no license. | `~/benchmarks/sweep2-20261018/laguna-s-ladder.json` + `laguna-s-suite/summary.md`. |
| `humanizer-12b-vllm.yaml` | vLLM 0.30 | `/v1/completions` text rewriter; 7.6 t/s; 0 fact losses across 40 rewrites (1 genuine defect outside the instrument); 88 GB repo on disk | **Off-brief**: no reasoning or tool-calling. Slowest measured arm, and the checkpoint ships **no chat template at all** — vLLM's `/v1/chat/completions` 400s on it (a property of the checkpoint, not an engine fault), so the chat route exists for no arm here ⇒ **no ladder** and no house/needle/ARC/GSM8K/BFCL/TEB cell; it cannot be scored on any of the four axes. | `~/benchmarks/humanizer-20261014/results.json` + `SUMMARY.md`. |
| `mellum2.1-12b-a2.5b-bf16-thinking-vllm.yaml` | vLLM 0.29 | 24.3 GB; C1 **42.3 ± 0.1**; ladder 42.3 / 67.2 / 99.9 / 135.6; house 36/37 | **Dominated by its own Q4_K_M sibling** (same checkpoint and 131,072 window): 111.9 vs 42.3 t/s, 208.0 vs 135.6 aggregate, 8.07 vs 24.3 GB, 37/37 and the ARC/GSM8K/BFCL/TEB cells this arm never measured. | `~/benchmarks/mellum-20261015/perf-ladder.json` + `house.json`; [`MELLUM-21.md`](MELLUM-21.md). |
| `mistral-small-4-119b-nvfp4-vllm.yaml` | vLLM 0.29 (`VLLM_MLA_DISABLE=1`) | 66.06 GiB weights; **89,216-token** servable ceiling; C1 **28.94 ± 0.03**; ladder 28.94 / 43.00 / 61.00 / 75.57; house 33/37 default, 36/37 ceiling | **Measured-rejected.** The 262,144 window it carried at measurement does not boot (72.0 GiB KV needed vs 24.51 GiB available); at the ceiling one full-window request takes the whole pool (**1.01×**); C1 is 42 % below Ling (49.7) and 74 % below the fastest arm (111.9); its 36/37 thinking ceiling is matched by smaller arms. | `~/benchmarks/mistral-119b-20261018/REPORT.md`, `c1-decode-triage.json`, `ladder-d0.json`, `suite/summary.md`. |
| `nemotron-3.5-lightning-30b-nvfp4-dspark-vllm.yaml` | vLLM | the lane's original shipped default; 77.7 t/s @ d0; 21 GB / 0.80 | **Lowest accuracy (33/37, identical miss set reproduced 2026-10-13)** — it pays ~4 quality tasks for its speed. | [`AGENTS.md`](AGENTS.md) §"Measured" (the Nemotron bullets); receipts `~/benchmarks/explore-tp1-20261013/`. |
| `nemotron-3.5-lightning-30b-nvfp4-dspark-1m-vllm.yaml` | vLLM | the 262k recipe with exactly `max_model_len: 1000000`, `gpu_memory_utilization: 0.91` | A variant of the archived 262k arm; slower (72.2 t/s), memory-heavier (0.91); its question (the card's 1M claim) is closed. | [`AGENTS.md`](AGENTS.md) §"Nemotron-3.5-Lightning — 1M-context arm"; receipts `~/benchmarks/nemotron-1m-20261012/`. |
| `nemotron-3-super-120b-a12b-nvfp4-vllm.yaml` | vLLM 0.29.0 | true **123.6B total / ≈12.2B active**; 80.30 GB / 74.83 GiB; unique single-node 262,144 window (7,659,632-token pool, 29.22×) | **Ranks below the rejected Mistral-Small-4:** C1 **15.83 ± 0.19** @ d0 is 45 % below Mistral and 66 % below Kolibri-1, and batching does not close it (1.93× for 10×). Quality is 37/37, so speed alone disqualifies it. Also records two boot defects: `--swap-space 0` and the two NVFP4 env vars are unrecognized in vLLM 0.29.0. | Receipt `~/benchmarks/nemotron-120b-20261018/REPORT.md`. |

## Archived mods and build files

The vLLM Kolibri plugin mod and the TensorFold launcher are **lane-local mods with no shipped user**
after this pass. They moved beside the archived recipes so the archived arms still resolve
`mods/<name>` adjacent to themselves:

| moved item | from | why |
|---|---|---|
| `mods/install-kolibri-plugin/` | `recipes/explore/mods/` | every user (FP8 base + the three 4-bit packs) is archived |
| `mods/kolibri-drafter-launcher/` | `recipes/explore/mods/` | its only user (the TensorFold drafter arm) is archived |
| `Dockerfile.kolibri1-tensorfold-drafter` | `recipes/explore/` | build provenance for the retired drafter image; `Dockerfile.kolibri1-llamacpp` stays for the kept APEX arm |
| `test_kolibri_plugin_mod.py` | `tests/` | the mod is no longer shipped, so its guard is no longer auto-discovered; run it manually as `uv run python -B -m unittest attic.explore.test_kolibri_plugin_mod` |

The archived recipes are **frozen provenance**: do not retune them, and do not clear a
`sparkrun recipe validate` warning by editing them — `attic/` recipes are not part of the registry
gate.

> **Tracking note.** The recipes, mods and this manifest are tracked and distributed with the registry.
> If a future ranking reverses a call, move the recipe back to `recipes/explore/` and delete its row
> here (and move its mod back if it has one).

*Archived 2026-10-13 by the first Explore selection pass; extended 2026-10-18 (Nemotron-Super) and
2026-10-19 (the 10-arm Pareto sweep under the owner's speed / concurrency / accuracy / size directive).*

# Probes

| file | status |
|:--|:--|
| [`zz-mellum2.1-12b-a2.5b-q4km-thinking-llamacpp-mmap.yaml`](zz-mellum2.1-12b-a2.5b-q4km-thinking-llamacpp-mmap.yaml) | Archived 2026-10-19 as a measured probe — the shipped Mellum GGUF with `--no-mmap` removed; mmap ON lost C1/C2/C5/C10 in a same-window pair (worst C5 -5.7 %), so the platform default stands. Receipt `~/benchmarks/mellum-mmap-20261019/`. |
