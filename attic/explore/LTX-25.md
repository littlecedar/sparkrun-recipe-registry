# LTX-25 lane notes (explore lane, 2026-10-14)

Arm: `Lightricks/LTX-2.5` `49b093a39c` (2026-10-11) — video+audio world model
(22B distilled DiT + Gemma-4-12B encoder), ComfyUI two-stage on **one GB10
node** (`.35`). Queued 2026-10-13 as media-gen; §6 acceptance
criterion confirmed by the owner 2026-10-14; gated arms ship with a
documented per-node `HF_TOKEN` + acceptance prerequisite (cybersec
precedent). **Shipped as a runbook** (no sparkrun recipe): runtime is ComfyUI
(no `sglang|vllm` engine) and access is per-user gated.

## Contents

- [Access](#access)
- [What was verified on hardware (2026-10-14, .35)](#what-was-verified-on-hardware-2026-10-14-35)
  - [Measured (receipts ~/benchmarks/ltx25-20261014/ on the head)](#measured-receipts-benchmarksltx25-20261014-on-the-head)
- [Traps re-learned (precedent for the next media arm)](#traps-re-learned-precedent-for-the-next-media-arm)
- [Deliverables](#deliverables)

## Access

`gated: auto`, license `ltx-2.x-community-license-agreement`. Token
`twichert` (org littlecedar) **has acceptance** — README resolve over the
token returned HTTP 200 on the head (`curl -H "Authorization: Bearer ..."`
against `Lightricks/LTX-2.5/resolve/main/README.md`). Per-repo: a fresh node
must re-accept + re-login before its first fetch. License: free commercial
use below a $10M-revenue Commercial Entity threshold (text read 2026-10-14
via the accepted token: 2.x follows the LTX-2 family pattern — confirm the
exact wording before shipping to third parties; the full text is
`https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x`).

## What was verified on hardware (2026-10-14, .35)

Unit pinned per §6(c): ComfyUI **v0.34.0** + comfy-kitchen 0.2.31 +
comfy-aimdo 0.4.15 + frontend 1.49.6 + workflows 0.11.48 + embedded-docs
0.5.10 (below 0.34 the refine silently emits garbage). torch 2.14.1+cu130
(aarch64 wheel, sm121). **Clock capped at 2200 MHz** (§6(e) sustained-load
fix) via `sudo nvidia-smi -lgc 0,2200`; all timings below were taken under
the cap.

Weights (≈36.9 GB): nvfp4 distilled transformer 18.72 GB, video VAE bf16
1.47 GB, audio VAE bf16 0.36 GB, x2 latent spatial upscaler 1.00 GB,
Gemma-4-12B comfy int8 encoder 15.37 GB. The `-nogemma`/`LoadConditioningT`
variant is H3-hybrid-graph-specific (muninn 2026-09-14) and NOT used here;
the native T2V template needs the Gemma encoder. Prompt-enhancer model
(`gemma4_e2b`) not needed (enhancer branch pruned; ComfySwitchNode is lazy).

### Measured (receipts `~/benchmarks/ltx25-20261014/` on the head)
Two-stage T2V, template `video_ltx2_5_t2v.json` (official), stage 1 = distilled
8-step @ 672×384 → `LTXVLatentUpsampler` ×2 → stage 2 = 3-step refine @
1344×768, 121 frames @ 24 fps (5.04 s), audio muxed, seed 42. Two cold
repetitions (receipts2 run7 / receipts run4) and one warm repetition
(run8, seed 44) with the clock capped:

| quantity | value |
|---|---|
| cold wall (prompt submission → file) | **100.3 s** / 90.1 s (two reps) |
| model load (nvfp4 17.8 GB + Gemma int8 14.6 GB) | 14.0 s (bracket) |
| stage 1 sampling wall (8 steps @ 672×384) | **16.7 s** (bar 12 s @ 1.52 s/it) |
| latent upscale (x2) | 2.5 s (bracket) |
| stage 2 sampling wall (3 steps @ 1344×768) | **20.8 s** (bar 20 s @ 6.93 s/it) |
| warm wall (seed 44, weights resident) | **80.1 s** (execute 79.35) |
| warm wall (re-take, 2026-10-18) | **78.1 s** — the number to compare against; the 80.1 above is 2.5 % pessimistic |
| peak unified memory | **83.6 GiB** / 121 GiB (0.69 util) |
| output | h264 1344×768, 24 fps, 121 frames, 5.042 s, AAC audio (mean −43.6 dB, max −25.7 dB, non-silent) |
| frame sanity (t=2.5 s) | mean 0.185, std 0.124 (not black, not noise) |

Timing method (repeat after the flattener): the server log is produced by
`tstamp.py`, which splits ComfyUI stdout on `\r` as well as `\n`, so the tqdm
sampler bars are timestamped segments; brackets are between consecutive
segment timestamps in `receipts2/server.log` and sum to `Prompt executed in
99.96 seconds`. The bar's own `00:12`/`00:20` are tqdm's per-step totals
(sampler-only, exclude the ~6 s model initialization inside each bar).

H3-hybrid comparison (third-party 2026-09-14 write-up, not our numbers): the
LTX refine stage there sits inside a 73.3 s warm H3+LTX cell; ours is an
LTX-only two-stage with an 8-step stage 1, so the total is not comparable —
the honest direct difference is the refine step cost (3 × 6.93 s/it @
1344×768). NVFP4 engages on sm121 through comfy-kitchen (no fallback to the
int8-convrot sibling was needed).

## Traps re-learned (precedent for the next media arm)

- `hf download --include` silently dropped the first pattern; explicit
  filename args work.
- Triton needs `python3.12-dev` on a bare node (`Python.h` missing → first
  kernel launch fails with a gcc `CalledProcessError`, not at import).
- Subgraph workflow templates need frontend-side expansion; the backend
  `/prompt` API only takes flat graphs. `expand_subgraph.py` (in
  `recipes/media/ltx-2.5-runbook/`) does it: widget order from
  `/object_info` INPUT_TYPES declaration order (multi-type `FLOAT,INT`
  widgets included — a naive filter mis-maps `LTXVEmptyLatentAudio`
  batch_size 25 vs 1), outer links parsed as arrays, dead lazy
  prompt-enhancer branch pruned, SaveVideo kept as the output node (drop it
  and the graph "succeeds" in 0.01 s having generated nothing).
- Same-seed rerun is fully cached (0.01 s) — a warm timing needs a different
  seed; the cache survives via ComfyUI's RAM-pressure cache but the
  transformer is "staged for dynamic VRAM loading" on each run, so warm
  saves the loader setup but not the sampler compute.

## Deliverables

- Runbook: `recipes/media/ltx-2.5-runbook/` (README + flattener + runner +
  server script).
- Receipts: `~/benchmarks/ltx25-20261014/` (scripts, API prompt, server log,
  mem.tsv, output MP4, decoded frame).
- Doc snippet for mad-science/TODO.md + EXPLORE-MODELS-RESEARCH.md §6
  (delivered in the session report; neither shared file was edited by this
  task).