# ltx-25-launcher

Pre-launch mod + launcher server for the LTX-2.5 T2V arm
([`recipes/explore/ltx-2.5-22b-nvfp4-t2v-comfyui-script.yaml`](../../../recipes/explore/ltx-2.5-22b-nvfp4-t2v-comfyui-script.yaml)).
**Booted 2026-10-21 on `.35`**: the cold stage (ComfyUI + venv + 36.9 GB of gated
weights) completed inside the port budget, `/v1/models` answered, and the T2V cell
landed at 100.13 s cold / 78.1 s warm, peak 84.00 / 83.45 GiB — the runbook's own
cells (100.3 / 78.1 s, 83.6 GiB). Receipt `~/benchmarks/ltx25-recipe-20261021/`;
the arm's measured provenance is [`recipes/explore/ltx-2.5-runbook/`](../../ltx-2.5-runbook/).

## Why this exists

`Lightricks/LTX-2.5` has no sglang or vLLM engine: the runtime is **ComfyUI**
driving the official `video_ltx2_5_t2v.json` subgraph template over the backend
`/prompt` route. The recipe's `runtime: vllm` is only the family whose
distribution + single-node launcher contract the command satisfies; this mod
stages the engine and the weights, and `launcher.py` *is* the server:

```
/cache/runtime/ltx-25/venv/bin/python /workspace/mods/ltx-25-launcher/launcher.py \
  --comfy-dir /cache/runtime/ltx-25/ComfyUI --host 0.0.0.0 --port 8000
```

## The unit that is pinned

ComfyUI publishes no OCI image in this runbook, so the recipe pins the
media-gen lane's existing arm64 cu130 base **by digest**
(`vllm/vllm-openai:v0.30.0@sha256:8a69…`, the same image the Qwen-Image arm
uses) and this mod pins the measured ComfyUI unit by tag + exact versions:

- ComfyUI **v0.34.0** (GitHub tag; below 0.34 the refine step returns success
  with garbage frames),
- `comfy-kitchen==0.2.31`, `comfy-aimdo==0.4.15`,
  `comfyui-frontend-package==1.49.6`, `comfyui-workflow-templates==0.11.48`,
  `comfyui-embedded-docs==0.5.10` (the requirements file pins the four as one
  unit),
- `torch` cu130, unpinned as the runbook installs it (resolves to the measured
  2.14.1 + torchvision 0.29.1 + torchaudio 2.11.0 on cp312/aarch64).

The image supplies Python 3.12 **dev headers**: triton compiles a driver stub
at first kernel launch, and a missing `Python.h` fails the first sampler, not
the import.

## Two-phase staging (why it is detached)

sparkrun runs `pre_exec` mods under a **600 s SSH timeout**
(`orchestration/hooks.py`). A cold node needs a torch venv plus 36.9 GB of
weights, so `run.sh` only does the cheap, fail-closed gates synchronously and
detaches the heavy work:

1. **Synchronous gates** — `launcher.py`/`expand2.py` present,
   `/cache/huggingface/hub` present, `curl`/`tar`/`python3`/`hf`/`timeout` on
   PATH, the HF token present, and the gated repo readable.
2. **Detached stage** (`run.sh --stage`, `setsid nohup`) — install ComfyUI +
   venv if the content gate fails; `hf download` the five explicit filenames
   into the node's HF cache if any is absent; symlink them into
   `ComfyUI/models/`; write `stage.status`.
3. **Launcher** tails `stage.log`, waits for `stage.status`, and only then
   starts ComfyUI. A failed stage is fatal at readiness, with the failing tail
   in `sparkrun logs`.

`stage.status` is `running …`, `ok …`, or `failed <reason>`; it is written by
the same content gates that are re-checked on every launch, so a complete
runtime dir makes the mod a no-op.

**Trap (2026-10-21): sparkrun exports `HF_HUB_OFFLINE=1`** for its distribution
contract, and `hf download` under it fails with "offline mode is enabled" — the
first two boots died there after the engine stage had already passed. The stage
now exports `HF_HUB_OFFLINE=0`; an `unset` inside the `hf` CLI wrapper was not
enough.

## Gated weights: the exact prerequisite

The repo is `gated: auto`. The README route answers **200 anonymously** (the
card is public), so acceptance is proved on a *weight* blob: a 1-byte range
request against the audio VAE returns `206` only for an accepted token, `401`
otherwise. `run.sh` probes that before detaching.

Per node:

```bash
# 1. browser: https://huggingface.co/Lightricks/LTX-2.5 -> "Agree and Access"
# 2. log in with THAT account; the token lands in the mounted HF cache
hf auth login            # writes /cache/huggingface/token
hf auth whoami
# 3. relaunch
```

Missing token or an unaccepted account fails the launch with a message naming
these steps. `hf download --include` is buggy (silently drops the first
pattern), so the five files are passed explicitly:

```
diffusion_models/ltx-2.5-22b-distilled-transformer-nvfp4.safetensors
vae/ltx-2.5-video-vae-bf16.safetensors
vae/ltx-2.5-audio-vae-bf16.safetensors
latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors
text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors
```

Revision `49b093a39c19169a8a81721dcc541e07e945232f` (the runbook's 2026-10-11
pin). sparkrun's own model distribution is disabled in the recipe, so nothing
anonymous is ever attempted.

## Server surface

| route | meaning |
|---|---|
| `GET /health` | liveness, backend state, model/revision/workflow; 503 once the ComfyUI child dies |
| `GET /v1/models` | the served repo id — sparkrun's readiness probe asks this path even with `readiness.inference: false` |
| `POST /generate` | `{"prompt", "width", "height", "frames", "fps", "seed", "timeout_s"}` → expands, patches, submits, polls, returns `wall_s`, `peak_gib`, and the mp4 path(s) |

`frames` must satisfy `frames % 8 == 1` (5 s × 24 fps = 121); a bad count is a
400, not a shaped-wrong clip. Width/height must be multiples of 32, and the
launcher writes them to the primitive BEHIND each latent's
`ComfyMathExpression "a/2"` — a literal on `EmptyLTXVLatentVideo` bypasses the
halving and silently runs stage 1 at full resolution (receipt defect 4, two
410 s runs).

Graph safety carried from the receipt (`~/benchmarks/ltx25-20261018/`):

- `SaveVideo` is the output node; the prompt is reachability-GC'd from it and
  its absence is a hard error (a graph without it "succeeds" in 0.01 s having
  generated nothing).
- The dead prompt-enhancer branch (`ComfySwitchNode` off +
  `gemma4_e2b_it_int8_convrot`) is aliased and collected; a surviving reference
  is a hard error because that model is deliberately not downloaded.
- ComfyUI's stdout is split on `\r` as well as `\n`, so tqdm sampler bars stay
  timestamped for a stage split.

`expand2.py` is the receipt's fixed expander, verbatim: the runbook copy's
widget indexing is T2V-only and shifts every model path by one on I2V/FLF2V.

## Operational notes

- **Clock cap (host, not container).** Run `sudo nvidia-smi -lgc 0,2200` on the
  node before launch. It is the sustained-load power-loss fix; without it a
  second consecutive long generation can take the node down, and every measured
  LTX cell was taken under the cap (~20 % cost). The image has no `nvidia-smi`,
  so the mod logs this as a note, not a gate.
- **License.** `ltx-2.x-community-license-agreement`: free commercial use for a
  Commercial Entity below a $10M annual-revenue threshold. Read
  <https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x> before handing
  outputs to a third party.
- **Outputs** land in `/cache/runtime/ltx-25/output/ltx25/` (persistent
  runtime-cache mount). Peak memory is `MemTotal - MemAvailable`, the receipt's
  unified-pool metric.

## Checks

```bash
bash -n recipes/explore/mods/ltx-25-launcher/run.sh
python3 recipes/explore/mods/ltx-25-launcher/launcher.py --selftest
uv run python -m py_compile recipes/explore/mods/ltx-25-launcher/*.py
HOME=.local/sparkrun-home sparkrun recipe validate \
  recipes/explore/ltx-2.5-22b-nvfp4-t2v-comfyui-script.yaml
HOME=.local/sparkrun-home sparkrun run \
  recipes/explore/ltx-2.5-22b-nvfp4-t2v-comfyui-script.yaml -H <node> -n
```

The dry-run renders the command without launching. The 2026-10-21 boot answered
both open questions: torch resolved to the measured cu130 pair on cp312, ComfyUI
imported under the image, and the expanded graph passed `/object_info` — the cell
then ran at the runbook's wall and peak-memory figures.