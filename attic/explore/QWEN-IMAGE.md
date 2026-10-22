# Qwen-Image-2.1-Turbo arm (explore lane, media-gen) — bring-up notes

> **LICENSE — NON-COMMERCIAL ONLY.** `Qwen/Qwen-Image-2.1-Turbo` is under the
> **Qwen Research License Agreement** (card `license: other`,
> `license_name: qwen-research`; `LICENSE` in the repo): **FOR NON-COMMERCIAL
> PURPOSES ONLY**. This registry is distributed to third parties. A recipe ships
> a repo id, not weights — each downloader fetches from the Hub and accepts the
> license there — but neither the weights nor images generated from them may be
> used commercially. Precedent: the MiniMax-M3 blocker and the Poolside S-2.1
> draft-license gap. **Owner call 2026-10-14: ship the recipe with this banner.**
> An operator needing commercial use must swap the checkpoint; the serving path
> (`recipes/explore/mods/qwen-image-2.1-turbo-launcher` + the recipe) is checkpoint-agnostic.

Arm queued 2026-10-13 (owner directive, media-gen — outside the lane's
reasoning/tool-calling brief); research and the per-arm verification checklist
are `EXPLORE-MODELS-RESEARCH.md` §6. This file is the lane's measurement record
for it.

## What shipped

| file | role |
|---|---|
| [`qwen-image-2.1-turbo-7b-bf16-diffusers-script.yaml`](../../recipes/explore/qwen-image-2.1-turbo-7b-bf16-diffusers-script.yaml) | the arm: `Qwen/Qwen-Image-2.1-Turbo` pinned `fc13ba1986`, 1 node, license banner at the top |
| [`recipes/explore/mods/qwen-image-2.1-turbo-launcher`](../../recipes/explore/mods/qwen-image-2.1-turbo-launcher) | the engine: a diffusers>=0.41 / transformers>=5.17 venv staged on the image's torch, plus the HTTP server |

The engine is `diffusers`' `QwenImage21Pipeline`; **no `sglang` runtime serves this
checkpoint** ([`vLLM-OMNI` does, measured 2026-10-21 — see "vLLM-OMNI route"
below, and it is a measured alternative rather than an arm](#vllm-omni-route-measured-2026-10-21)),
so §6(b)'s "script-launcher/runbook-shaped arm" is the
shape that shipped — the same mechanism as the TensorFold DSV41 shim and the
Decision lane's `vllm-srun` arms: `runtime: vllm` is the family whose
model-distribution and single-node launcher contract the command satisfies,
with the recipe's `command:` running the server directly.

## Design decisions worth not re-deriving

- **Image**: the lane's existing digest-pinned `vllm/vllm-openai:v0.29.0`
  (`sha256:c2914767…`), used only as an arm64 CUDA torch base. `nvcr.io/nvidia/vllm:26.06-py3`
  is also on the nodes and carries uv, but has **no `RepoDigests` entry** (it was
  `docker load`ed, not pulled), so it cannot be digest-pinned.
- **The venv is the version floor.** The image ships `transformers 5.16.1`;
  the card requires `>= 5.17`, and `QwenImage21Pipeline` first appears in
  `diffusers 0.41.0` (the checkpoint's `model_index.json` declares
  `_diffusers_version: 0.41.0.dev0`). The mod builds
  `/cache/runtime/qwen-image/venv` with `--system-site-packages`, so the image's
  arm64 CUDA torch is inherited and never re-downloaded; only `diffusers`,
  `transformers` and `accelerate` are installed (none of the three depends on
  torch). Measured install: ~27 s cold on one node.
- **The container is not root, so `reown()` must tolerate failure.** This
  image's container user is `1000:1000` (`docker inspect .Config.User`; `id`
  inside a `docker exec` agrees), while the docs' mod contract assumes root.
  A mod script run as uid 1000 cannot `chown` root-owned leftovers — observed
  directly as `chown: … Operation not permitted` on the staged venv — so
  `reown()` now chowns only when it is root and logs a skip otherwise.
- **The first boot's pre_exec exited `rc=120` right after the venv stage.** The
  mod's log ends at the `"${VENV_DIR}/bin/python" - <<'PY' | log` line (an empty
  line from the piped `log`), with the install already reported successful; the
  construct is gone — the mod captures the engine versions into a variable and
  logs that. The venv itself was correct (verified afterwards in-container:
  diffusers 0.41.0 / transformers 5.19.0 / torch 2.13.0+cu130, pipeline imports,
  CUDA on GB10).
- **Mod resolution during bring-up.** The recipe references the mod the normal
  way (`mods/qwen-image-2.1-turbo-launcher`), which resolves under
  the `littlecedar` registry's checkout on the head — a git clone that does not
  yet carry this mod. The boot therefore staged the mod directory into
  `~/.cache/sparkrun/registries/littlecedar/recipes/explore/mods/qwen-image-2.1-turbo-launcher`
  on the head first (a plain copy into the cache; removed afterwards). Once the
  mod is committed and `registry update` fetches it, that step disappears.
  The launch itself used `--transfer-mode local` for the same reason.

## Traps re-checked (§6(d))

- **VAE tiling stays OFF** — nothing in the server enables it; tiled decode
  produces a pink seam column on this checkpoint.
- **`cpu_offload` stays OFF** — nothing enables it; the base-model write-up
  measured 62.5 s → 4m20 on one reference image with it on.
- **Reference-image cost re-measured on our node** (see Measurement): +3.5 s
  over text-to-image at 1024², not the base model's 62.5 s — that figure came
  from a different resolution / step count.
- **`{model}` reaches the engine as a snapshot path**, not the repo id, so the
  server loads a path (offline-safe: sparkrun's SHA download writes no
  `refs/`). `--served-model-name` is rendered explicitly in the recipe, which
  also suppresses the runtime's own append (the Ling trap).

## Measurement — booted and measured 2026-10-14

Boot on `.34`, task `sparkrun_d87820463a694961_8ed3ce77d78f`. Receipts under
`~/benchmarks/qwen-image-20261014/` on the head (`launch2.log`, `serve-tail.log`,
`modlogs/`, `samples/`, `results.json`, `edit.json`, `measure.py`, `analyze.py`).

- **Boot**: container start → port open **206.1 s** (HTTP-ready 206.1 s), total
  launch 214.9 s. Of that, pipeline load **188.0 s**; the engine venv gate
  passes on every later boot (cold stage ~27 s, measured on the first boot).
  `MemAvailable` 116.8 GiB before load → **85.6 GiB** after (≈31 GiB resident
  for a 32.5 GB bf16 checkpoint).
- **Text-to-image, 1024², the checkpoint's shipped 8-step schedule at CFG=1**
  (the server reports `steps: 8`; the pipeline's own bar is 8/8):

  | item | wall | server `elapsed_s` | first step | peak alloc | peak reserved |
  |---|---|---|---|---|---|
  | poster-typography (first request, warm-up) | 12.55 s | 12.304 | 1.874 s | 36.85 GiB | 37.68 GiB |
  | photo-marina | 11.68 s | 11.332 | 0.702 s | 36.83 GiB | 37.68 GiB |
  | poster-typography (repeat) | 11.64 s | 11.408 | 0.729 s | 36.85 GiB | 37.68 GiB |

  **Steady-state ≈ 11.3–11.4 s at 1024² / 8 steps.** The research doc's derived
  expectation was 54.1 × 8/40 ≈ **10.8 s** from the base model's measured
  54.1 s @ 40 steps; measured is +5% on that, so the steps-linear model holds on
  this checkpoint. First-step latency (the image analogue of TTFT) is **1.87 s**
  on the first request and **~0.71 s** warm — the delta is one-time
  kernel/allocator warm-up.
- **Peak unified memory**: torch reports **36.85 GiB allocated / 37.68 GiB
  reserved**; node `MemAvailable` falls from 85.6 GiB idle-loaded to **76.9 GiB**
  during a request, i.e. ≈8.7 GiB of transient working set on top of the
  resident weights. Well inside the 0.85 budget of the 121.7 GiB node.
- **Determinism**: the repeat item — same prompt, same seed, same size — wrote a
  **byte-identical PNG** (1,116,690 bytes; identical objective stats). The §6
  "fixed prompt+seed set" is reproducible on this arm.
- **Reference-image (editing) path exercised**: one of the generated PNGs fed
  back as the reference at 1024² took **14.8 s** (peak alloc 38.84 GiB) against
  11.3 s for the same-size text-to-image — a **+3.5 s / +2 GiB** reference cost,
  and proof the `image=` path works end to end.
- **Objective output check** (`analyze.py`, Pillow in the engine venv — the PNGs
  are never read as text): all four images are 1024×1024 **RGBA** (the
  checkpoint emits an alpha channel), 255–256 distinct gray levels, extrema
  spanning 0–254/255, stddev 65–88 — no degenerate (flat, all-black or
  noise-only) output. The bright, low-dark-fraction profile of the two poster
  items matches the prompted white poster; the marina is mid-toned. **The visual
  verdict against the vendor gallery is the owner's**, from the saved PNGs —
  this is an objective non-degeneracy check, not an eye.

### Step count and custom schedules (measured 2026-10-21)

`num_inference_steps` alone does nothing on this checkpoint: `12` returned the
**byte-identical PNG** in the same 11.47 s as the 8-step control, because the pipeline
force-loads `sample_sigmas`. The server now takes an explicit `sigmas` list or resamples
the saved curve when `num_inference_steps` names a *different* count, and reports
`sigmas_used` so a cell can prove it took the new path. One serve on `.34`, seed 42,
1024², CFG=1, one cell per schedule:

| schedule | server `steps` | `elapsed_s` | peak alloc |
|---|---|---|---|
| shipped (control) | 8 | 12.64 (cold) / 11.5 steady | 36.82 GiB |
| `num_inference_steps: 4` | 4 | 6.38 | 36.82 GiB |
| `num_inference_steps: 12` | 12 | 17.01 | 36.82 GiB |
| explicit `sigmas` (4 pt) | 4 | 6.39 | 36.82 GiB |

The step count is ~0.63 s per extra step at CFG=1 and **peak memory does not move** —
a shorter schedule buys latency, not headroom. The 8-step control stayed byte-identical
after the mod, so the default path is untouched. Quality is not judged by these cells:
the §6 by-eye item stays open, and 4 steps is proven reproducible, not recommended.
Receipt: `~/benchmarks/media-gen-20261021/REPORT.md` on `.NN`.

## vLLM-OMNI route (measured 2026-10-21)

`vllm/vllm-omni:nightly` serves this checkpoint natively and beats the shipped Diffusers launcher by
**~24 % warm at the same step count and the same peak memory**. It is **recorded as a measured
alternative, not as an arm**: it has no recipe, and the same seed does not give the same picture (below).
Both routes' 8-step images were inspected for defects and are clean — the remaining choice between the two
looks is the owner's, not this measurement's. One boot on `.34`, one serve each route, same prompt, seed 42, 1024², CFG=1
(`guidance_scale: 1.0`), shipped 8-step schedule.

| route | 8-step cold | 8-step warm | peak GPU memory | per step (warm) | engine |
|---|---:|---:|---:|---:|---|
| Diffusers mod (`server.py`) | 12.64 s | **11.49 s** | 36.82 GiB alloc / 37.65 GiB reserved | 1.43 s | diffusers 0.41 venv |
| **vLLM-OMNI** | **11.19 s** | **8.66–8.75 s** | **36.84 GiB** (`vllm_omni:peak_memory_mb{stage="0"}` = 37,726 MB) | **1.08 s** | vllm-omni 0.32.0rc2.dev29 / vllm 0.32.0, torch 2.13 cu130, transformers 5.19.0 |

The 2.79 s warm delta is all denoise: no venv is staged and nothing is loaded twice — OMNI ships its
own `QwenImage21Pipeline` under `vllm_omni/diffusion/models/qwen_image_21/`, so the checkpoint needs
nothing from the mod. Boot: `docker run -d --name omni-qwen --network host --gpus all -v
/<home-dir>/.cache/huggingface:/root/.cache/huggingface -e HF_HUB_OFFLINE=1 vllm/vllm-omni:nightly vllm
serve <snapshot>/fc13ba19… --omni --served-model-name Qwen/Qwen-Image-2.1-Turbo --port 8000`; the
endpoint for a diffusion model is `POST /v1/images/generations` (`/health` → `{"status":"healthy"}`).

| boot fact | value |
|---|---|
| TTR | container start 01:12:37Z → `Application startup complete` **≈ 4 min** (weights 30.22 GiB in 225 s; 750 tensors, 2 shards) |
| resolved pipeline | `QwenImage21Pipeline`, `final_output_type='image'` |
| attention backend | **`CUDNN_ATTN`** auto-selected for "Blackwell sm_121, cuDNN 92000, head_dim 128" |
| memory after load | 30.44 GiB process-scoped GPU memory |

### The two probes that saved a dead boot

Both were run before the serve, and each one alone would have been a boot that could not start:

- **`:latest` cannot load this checkpoint.** `vllm/vllm-omni:latest` is vllm-omni **0.31.0rc1**
  (diffusers 0.40.0) and its diffusion registry has **`QwenImagePipeline` only — no
  `QwenImage21Pipeline`**, while `model_index.json` declares `_class_name: QwenImage21Pipeline`. The
  **nightly** (0.32.0rc2.dev29) carries it. Anyone re-running this: pin the nightly digest, not
  `:latest`.
- **GB10's kernel arch is not a blocker.** `torch.cuda.get_device_capability()` → **(12, 1)**, i.e.
  sm_121, and torch's `arch_flags` list sm_80…sm_120 with **no sm_121 cubin**, so a `no kernel image is
  available` failure looked likely; a bf16 512² matmul on `--gpus all` runs anyway through PTX JIT, and
  the full serve then ran. Arch is a risk to check, not a reason to skip the route.

### The step knob lies harder here than in the Diffusers mod

`num_inference_steps` is inert on this endpoint exactly as it is in the mod — the checkpoint's saved
`sample_sigmas` still wins — **and the engine reports the fiction instead of dropping the field**.
Three requests differing only in that field, same seed, all three wrote the **byte-identical PNG**
(`sha256 38ce554a1ccb4e85…45704690`, 4,196,804 B):

| requested steps | wall (`stage_gen_time_ms`) | server's `denoise_step_latency_ms` |
|---:|---:|---:|
| 4 | 8.73 s (8,655) | 2,164 |
| 8 | 8.75 s (8,686) | 1,086 |
| 12 | 8.72 s (8,651) | 721 |

It accepts the field, ignores it, then **divides the same total by the requested count** — so asking for
more steps makes it *claim each step was faster*. Anyone benchmarking this endpoint on its reported
per-step latency is quoting fiction; the mod at least echoed `steps: 8` honestly. The 4 and 12 rows are
therefore provenance, not schedules: there is no working 4-step OMNI cell to set against the Diffusers
4-step 6.38 s.

### Operator review of both 8-step images (2026-10-21)

Both PNGs were opened at full resolution (the copies in `koder/omni-pngs` on the workstation) and read
deliberately for defects:

- **Diffusers — clean.** A two-line poster, **`SPARK` / `RUN`**, blue over orange on cream, heavy
  grotesque, correct spelling, crisp edges.
- **OMNI — clean.** A single-line **`SPARKRUN`** in a rainbow run of letters on white, correct spelling,
  clean edges.
- **No gross defect in either**: no smearing, no blended or doubled glyphs, no gibberish letterforms, no
  step-count starvation artifacts. So the OMNI route's ~24 % warm win is **not bought with visible quality
  loss at 8 steps**.
- **They differ in composition, not merely palette** — two-line vs single-line, different weight and
  colour logic — which is what the hash mismatch already implied: the same seed does not mean the same
  picture across routes. Do **not** describe OMNI as "the same image, faster".

**The limit of this review:** it is a **defect inspection, not the owner's aesthetic choice**. The §6 item
therefore moves from *"nobody has looked"* to *"inspected for defects; which look ships is the owner's
call"* — and it applies to both routes, so the shipped Diffusers arm is not validated by it either.

### Why it is not an arm

- **The two routes disagree on composition, not just pixels.** Same prompt and seed give visibly
  *different* images — two-line `SPARK`/`RUN` (Diffusers, `e24f6e3a…24ee24a`) vs single-line rainbow
  `SPARKRUN` (OMNI, `38ce554a…45704690`) — which is expected across different sampler/VAE code paths.
  Both inspected clean (above), so neither route can be preferred on defects, and **which look ships is
  the owner's call**; latency alone does not decide it.
- **No recipe was written.** Shipping it would need a script/burst recipe plus a decision about the inert
  step knob; that is the lane owner's call, not this measurement's.

Both 8-step PNGs are named by route in the receipt for that eye:
`~/benchmarks/media-gen-20261021/eight-step-diffusers.png` (`e24f6e3aa694fbcc566367fb9590f5f4f9fbaa483c65f594594aa4a2724ee24a`)
and `~/benchmarks/media-gen-20261021/eight-step-omni.png` (`38ce554a1ccb4e85789f590121bc545fb7ae69bc3d7f9fb4b75f86db45704690`);
the measurement itself is `~/benchmarks/media-gen-20261021/vllm-omni/REPORT.md` + `omni.json`,
`omni-warm8.json`, `serve.log.gz`.

### §6 acceptance criterion, item by item

| §6 requirement | result |
|---|---|
| fixed prompt+seed set | 2 fixed prompts × fixed seeds, plus a same-seed repeat |
| one 1024² image at the shipped step count | 1024×1024 at **8 steps** (the checkpoint's saved `sample_sigmas`) |
| wall-clock per item | 11.3–11.4 s steady (table above) |
| peak unified memory | 36.85 GiB torch alloc; 76.9 GiB node `MemAvailable` during a request |
| quality judged by eye against the vendor gallery | **open — but no longer unlooked-at.** An operator defect review of the 8-step images (both routes, full resolution) found clean typographic posters with correct spelling and crisp edges, no smearing or blended glyphs, and no step-starvation artifacts. Which *look* ships is the owner's aesthetic call |

### Verdict

Boots and serves text-to-image and editing on **one** GB10 at ~11.4 s per
1024²/8-step image and ~36.9 GiB peak, at the low end of the lane's memory use.
Two bring-up defects were found and fixed in the mod (the container's non-root
user breaking `reown()`, and a heredoc piped into `log()` killing the hook with
`rc=120` after a successful install). Off the lane's brief (no reasoning, no
tool calls) **and license-blocked for commercial use**, so it competes with
nothing in the selection and ships as the banner-marked eval-only entry.
