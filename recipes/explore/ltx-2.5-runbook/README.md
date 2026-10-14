# LTX-2.5 — ComfyUI runbook (DGX Spark / GB10, explore lane)

`Lightricks/LTX-2.5` (video+audio world model, 22B distilled DiT + Gemma-4-12B
text encoder) as a **two-stage** ComfyUI run on one GB10 node. This arm ships
as a runbook, not a sparkrun recipe: the runtime is ComfyUI (no
`sglang|vllm` engine), the repo is `gated: auto` (per-node `HF_TOKEN` +
accepted terms are a prerequisite sparkrun cannot assume), and the licence is
`ltx-2.x-community-license-agreement` (free below a $10M-revenue Commercial
Entity threshold; read the 2.x text before shipping to third parties —
`https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x`).

## Status

- Booted 2026-10-14 on `.35`, node idle, ComfyUI v0.34.0
  (torch 2.14.1+cu130), clock capped at 2200 MHz.
- Checkpoint pinned `49b093a39c` (2026-10-11); weights = the **nvfp4**
  distilled transformer + bf16 video/audio VAEs + x2 latent spatial upscaler +
  Gemma-4-12B Comfy int8 text encoder (≈ 36.9 GB; no `gemma4_e2b`
  prompt-enhancer model needed — ComfySwitchNode is lazy and the branch is
  pruned).
- Receipts on the head: `~/benchmarks/ltx25-20261014/` (flattener, runner,
  tstamp wrapper, API prompt, server log, memory samples, output MP4s,
  decoded frame).

## Measured (2026-10-14, .35, clock-capped at 2200 MHz)

Fixed cell: seed 42, 1344×768, 121 frames @ 24 fps, audio, nvfp4 transformer
(two cold reps + one warm rep, seed 44):

| quantity | value |
|---|---|
| cold wall (submission → file) | 100.3 s / 90.1 s |
| model load (nvfp4 17.8 GB + Gemma int8 14.6 GB) | 14.0 s |
| stage 1 sampling (8 steps @ 672×384) | 16.7 s wall (bar 12 s @ 1.52 s/it) |
| latent upscale (x2) | 2.5 s |
| stage 2 sampling (3 steps @ 1344×768) | 20.8 s wall (bar 20 s @ 6.93 s/it) |
| video+audio VAE decode + mux | 46.2 s |
| warm wall (same weights resident) | 80.1 s |
| peak unified memory | 83.6 GiB / 121 GiB (0.69 util) |
| output | h264 1344×768 24 fps 121 frames 5.04 s + AAC (max −25.7 dB) |

Stage split comes from `tstamp.py` splitting ComfyUI stdout on `\r` so each
tqdm sampler bar is a timestamped segment; brackets between consecutive
segments sum to the `Prompt executed in` total. The refine dominates sampling
(6.93 s/it at 1344×768); the tiled video VAE decode is the largest single
block (46 s).

## Prerequisites (per node)

1. Accept the gate and log in; **this is per-repo and per-user**:

   ```bash
   # browser: https://huggingface.co/Lightricks/LTX-2.5 -> "Agree and Access"
   hf auth login            # token must be for the user that accepted the repo
   hf auth whoami           # verify
   ```

2. Python dev headers (triton compiles a tiny driver stub at first kernel
   launch; missing `Python.h` fails the first sampler, not the import):

   ```bash
   sudo apt-get install -y python3.12-dev
   ```

## Install (once per node)

```bash
cd ~
curl -sL -o comfy.tar.gz https://codeload.github.com/comfyanonymous/ComfyUI/tar.gz/refs/tags/v0.34.0
mkdir -p ComfyUI && tar xzf comfy.tar.gz -C ComfyUI --strip-components=1
cd ComfyUI
python3 -m venv .venv && . .venv/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
grep -v -E '^(torch|torchvision|torchaudio)([<>=!~ ]|$)' requirements.txt > /tmp/req-notorch.txt
python -m pip install -r /tmp/req-notorch.txt
# the unit the 2026-09-14 write-up had to pin: on 0.30.x the refine step
# returns success with garbage frames. Take the four as one unit.
python -m pip install comfy-kitchen==0.2.31 comfy-aimdo==0.4.15 \
  comfyui-frontend-package==1.49.6 comfyui-workflow-templates==0.11.48 \
  comfyui-embedded-docs==0.5.10
```

## Weights

```bash
hf download Lightricks/LTX-2.5 \
  diffusion_models/ltx-2.5-22b-distilled-transformer-nvfp4.safetensors \
  vae/ltx-2.5-video-vae-bf16.safetensors \
  vae/ltx-2.5-audio-vae-bf16.safetensors \
  latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors \
  text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors \
  --local-dir ~/ComfyUI/models
```

`hf download --include` is buggy (silently drops the first pattern) — pass
explicit filenames as above. Rationale: nvfp4 transformer (18.7 GB) fits one
GB10 with the Gemma encoder; the bf16/int8-convrot transformer siblings
(42/21.5 GB) exist for other engines. Video uses the diff VAE
(`video-vae-bf16`, slower, better); `video-vae-conv-bf16` is the lighter
alternative.

## Graph

The two-stage graph is ComfyUI's official `LTX-2.5 T2V` workflow template
(`comfyui-workflow-templates`, `video_ltx2_5_t2v.json`):

- stage 1 — distilled 8-step schedule (`1.0, 0.99375, … 0.0`, euler_ancestral)
  at **half resolution** (1344×768 → 672×384);
- `LTXVLatentUpsampler` ×2 (spatial upscaler);
- stage 2 — **3-step refine** (`0.85, 0.7250, 0.4219, 0.0`) at 1344×768;
- video VAE decode (tiled) + audio VAE decode, muxed by `CreateVideo`.

Constraints: frames must satisfy `frames % 8 == 1` (the template's
`length = duration × fps + 1`; 5 s × 24 fps → **121** frames). The
"124 frames" figure in the third-party write-up is the MiniMax-H3 draft's
count; LTX outputs 121. Both stages use the **nvfp4** transformer; the
`-nogemma`/`LoadConditioningT` variant is specific to the H3+LTX hybrid
graph from the 2026-09-14 write-up and is NOT used here — the native T2V
template needs the Gemma-4-12B encoder (int8, 15.4 GB).

Templates with subgraphs only exist in the frontend; the backend `/prompt`
route needs a flat API graph. `expand_subgraph.py` does that expansion
headlessly (widget order from `/object_info`; multi-type `FLOAT,INT` widgets
included; `ComfySwitchNode` on_false aliased to on_true and the dead
prompt-enhancer branch pruned). See the file header.

## Run (one node, clock-capped)

```bash
cd ~/ltx25   # scripts live here; or use recipes/explore/ltx-2.5-runbook/
# sustained-load power-loss fix (see ../../../attic/explore/EXPLORE-MODELS-RESEARCH.md §6(e)):
# without the cap, a second consecutive long generation can take the node
# down. Costs ~20% per run; all timings above were taken capped.
sudo nvidia-smi -lgc 0,2200

bash serve_ltx25.sh > serve.out 2>&1 &   # ComfyUI on 127.0.0.1:8188
                                         # + 1 Hz unified-memory sampler -> receipts2/mem.tsv
                                         # + \r-splitting timestamped log -> receipts2/server.log

source ~/ComfyUI/.venv/bin/activate
python3 run_ltx25.py ltx_t2v.json \
  --transformer ltx-2.5-22b-distilled-transformer-nvfp4.safetensors \
  --seed 42 --width 1344 --height 768 --duration 5 --fps 24 \
  --timeout 3600            # prints wall_s + status; video in ComfyUI/output/video/
```

Peak unified memory: `awk '{if($2>m)m=$2}END{print m}' receipts2/mem.tsv`.
Stage split: grep the `100%|…| 8/8` and `3/3` segments in
`receipts2/server.log`; bracket timestamps are the wall start/end of each
sampler. A same-seed rerun is fully cached (0.01 s) — use a different seed
for a warm timing.

## Traps (paid for on 2026-10-14)

- `hf download --include` drops patterns; pass explicit filenames.
- Missing `python3.12-dev` → triton driver compile fails at first kernel
  launch (`Python.h: No such file`), not at import.
- Subgraph templates: posting the UI JSON to `/prompt` gives
  `prompt_outputs_failed_validation`; the frontend's graphToPrompt does the
  expansion, or use `expand_subgraph.py` here.
- `SaveVideo` is the output node; if it is missing from the API prompt the
  graph "succeeds" in 0.01 s having done nothing (only the preview node ran).
- Widget order follows the node's INPUT_TYPES declaration order, including
  multi-type widgets (`FLOAT,INT`); a naive primitive-only filter mis-maps
  `LTXVEmptyLatentAudio.batch_size` (25 vs 1) and crashes the stage-1
  sampler on a latent-shape mismatch.
- Reading the log through a newline-based `read` loop merges all tqdm `\r`
  updates into one line (useless for timing); the wrapper must split on `\r`.
- stderr alone is not proof: decode a frame (see §6 checklist (c)).