# viggle-remake-launcher

Pre-launch stage and HTTP shim for
[`recipes/media/viggle-remake-h3-lora-v2v-comfyui-script.yaml`](../../viggle-remake-h3-lora-v2v-comfyui-script.yaml).

ComfyUI is the engine; this mod owns what the recipe's `command:` needs to
exist and nothing above it:

| piece | what it is |
|---|---|
| `run.sh` | gates fast, then detaches the stage: ComfyUI `v0.42.0` in a cu130 venv, the repo's own node pack (`comfyui/ComfyUI-Viggle-Remake`), the MiniMax-H3 single-file repack the graph loads, and both Remake LoRA repacks |
| `launcher.py` | waits for the stage, starts ComfyUI on a private port, and serves `/health`, `/v1/models`, `POST /generate`; every other path is proxied to ComfyUI unchanged |
| `workflows/remake_{swap,edit}_api.json` | the vendor's API graphs, verbatim from `Viggle/Viggle-Remake@7e5be143` (`comfyui/workflows/`), Apache-2.0 |

## Why the base is repointed

The vendor graph loads `minimax_h3_fl2va_bf16.safetensors` and
`qwen3vl_32b_minimax_h3_bf16.safetensors` — 61.73 GiB and 47.97 GiB, ~110 GiB
resident before the VAE and the LoRA, against ~109 GB of usable unified memory
on one GB10. `launcher.py` rewrites exactly those two loader inputs to the
AdaLN-pruned fp8 DiT (19.52 GiB) and the NVFP4-AWQ text encoder (14.61 GiB)
from `Comfy-Org/MiniMax-H3@e5eb578a`, the pair the shipped H3 arm measured at
39.54 GiB resident with both VAEs. Nothing else in the graph is rewritten.

## Stage protocol

`stage.status` holds `pending`, `ok` or `failed <why>`; the detached stage
writes it last, and `launcher.py` exits 2 on `failed` after printing the tail
of `stage.log`. A complete runtime dir makes `run.sh` a no-op, so a second
launch pays only the gate. `staged.env` records the repo ids and revisions the
weights came from, and the launcher refuses to serve when the recipe's
`model_revision:` and that record disagree.

## Interface

```bash
curl -s localhost:8000/v1/models | jq .
curl -s -XPOST localhost:8000/generate -H 'content-type: application/json' -d '{
  "task": "swap",
  "source": "remake_swap_source.mp4",
  "refs": ["remake_swap_ref1.png", "remake_swap_ref2.png"],
  "prompt": "subject_definitions: ...",
  "seed": 0 }'
```

`source` and `refs` are filenames already in the container's input directory
(`/cache/runtime/viggle-remake/input`); the vendor's example inputs are
`examples/inputs/*` in the model repo and are NOT staged by this mod. `prompt`
and `seed` are optional: omitted, the graph keeps its own prompt and seed 0.
The response names the written mp4 and the wall seconds.

## Knobs

`MOD_FETCH_TIMEOUT`, `MOD_STAGE_TIMEOUT`, `MOD_CACHEDIR`, `MOD_LOGDIR`,
`VIGGLE_RUNTIME_DIR`, `HF_HOME`, `HF_TOKEN`. `COMFY_TAG` and the base
repo/revision are constants in `run.sh` because they are staging inputs, not
per-launch choices.

## Licences

Viggle Remake is a Model Derivative of MiniMax H3, distributed under the
MiniMax H3 COMMUNITY LICENSE AGREEMENT: not usable in the EU, the UK, the
Republic of Korea or the USA; NOTICE carriage; "Powered by Viggle Remake"
credit. The node pack, the workflows and the Python under `comfyui/` are
Apache-2.0 (`LICENSE-CODE` in the model repo). This mod ships a fetcher, not
weights.

## Unverified

Authored 2026-11-16, never booted. The open first-boot questions are named in
the recipe's description: whether the Remake LoRA keys match the pruned DiT,
and whether `ComfyUI 0.42.0` plus this node pack starts under the pinned image.