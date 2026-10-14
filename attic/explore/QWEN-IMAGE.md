# Qwen-Image-2.1-Turbo arm (explore lane, media-gen) — bring-up notes

> **LICENCE — NON-COMMERCIAL ONLY.** `Qwen/Qwen-Image-2.1-Turbo` is under the
> **Qwen Research License Agreement** (card `license: other`,
> `license_name: qwen-research`; `LICENSE` in the repo): **FOR NON-COMMERCIAL
> PURPOSES ONLY**. This registry is distributed to third parties. A recipe ships
> a repo id, not weights — each downloader fetches from the Hub and accepts the
> licence there — but neither the weights nor images generated from them may be
> used commercially. Precedent: the MiniMax-M3 blocker and the Poolside S-2.1
> draft-licence gap. **Owner call 2026-10-14: ship the recipe with this banner.**
> An operator needing commercial use must swap the checkpoint; the serving path
> (`mods/qwen-image-2.1-turbo-launcher` + the recipe) is checkpoint-agnostic.

Arm queued 2026-10-13 (owner directive, media-gen — outside the lane's
reasoning/tool-calling brief); research and the per-arm verification checklist
are `EXPLORE-MODELS-RESEARCH.md` §6. This file is the lane's measurement record
for it.

## What shipped

| file | role |
|---|---|
| [`qwen-image-2.1-turbo-7b-bf16-diffusers-script.yaml`](../../recipes/explore/qwen-image-2.1-turbo-7b-bf16-diffusers-script.yaml) | the arm: `Qwen/Qwen-Image-2.1-Turbo` pinned `fc13ba1986`, 1 node, licence banner at the top |
| [`mods/qwen-image-2.1-turbo-launcher`](../../mods/qwen-image-2.1-turbo-launcher) | the engine: a diffusers>=0.41 / transformers>=5.17 venv staged on the image's torch, plus the HTTP server |

The engine is `diffusers`' `QwenImage21Pipeline`; **no `sglang`/`vLLM` runtime
serves this checkpoint**, so §6(b)'s "script-launcher/runbook-shaped arm" is the
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
  way (`@littlecedar/mods/qwen-image-2.1-turbo-launcher`), which resolves under
  the `littlecedar` registry's checkout on the head — a git clone that does not
  yet carry this mod. The boot therefore staged the mod directory into
  `~/.cache/sparkrun/registries/littlecedar/mods/qwen-image-2.1-turbo-launcher`
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

### §6 acceptance criterion, item by item

| §6 requirement | result |
|---|---|
| fixed prompt+seed set | 2 fixed prompts × fixed seeds, plus a same-seed repeat |
| one 1024² image at the shipped step count | 1024×1024 at **8 steps** (the checkpoint's saved `sample_sigmas`) |
| wall-clock per item | 11.3–11.4 s steady (table above) |
| peak unified memory | 36.85 GiB torch alloc; 76.9 GiB node `MemAvailable` during a request |
| quality judged by eye against the vendor gallery | **open** — images saved under `samples/`; objective non-degeneracy recorded above |

### Verdict

Boots and serves text-to-image and editing on **one** GB10 at ~11.4 s per
1024²/8-step image and ~36.9 GiB peak, at the low end of the lane's memory use.
Two bring-up defects were found and fixed in the mod (the container's non-root
user breaking `reown()`, and a heredoc piped into `log()` killing the hook with
`rc=120` after a successful install). Off the lane's brief (no reasoning, no
tool calls) **and licence-blocked for commercial use**, so it competes with
nothing in the selection and ships as the banner-marked eval-only entry.
