# qwen-image-2.1-turbo-launcher

Pre-launch mod for the explore lane's Qwen-Image-2.1-Turbo arm
([`recipes/explore/qwen-image-2.1-turbo-7b-bf16-diffusers-script.yaml`](../../recipes/explore/qwen-image-2.1-turbo-7b-bf16-diffusers-script.yaml)).

## Why this exists

`Qwen/Qwen-Image-2.1-Turbo` is a diffusers checkpoint (`QwenImage21Pipeline`).
Neither `sglang` nor `vLLM` can serve it, so there is no engine on PATH to
exec and no runtime flag set to render. The arm therefore ships the *server*:
this mod stages the Python environment and the recipe's `command:` runs

```
/cache/runtime/qwen-image/venv/bin/python /workspace/mods/qwen-image-2.1-turbo-launcher/server.py --model {model} --host {host} --port {port}
```

`runtime: vllm` in the recipe is the family whose model-distribution and
single-node launcher contract that command satisfies — the same pattern the
Decision lane's `vllm-srun` arms use (a `runtime: vllm` recipe whose command
runs a foreign engine). No sparkrun runtime plugin is needed.

## What the mod does

1. Creates `/cache/runtime/qwen-image/{venv,samples}` and re-owns it to the
   cache-mount UID/GID (mods run as root).
2. **Fail-closed engine gate** — if
   `/cache/runtime/qwen-image/venv/bin/python` cannot import
   `diffusers.QwenImage21Pipeline` *and* assert `diffusers >= 0.41.0`,
   `transformers >= 5.17.0`, the venv is rebuilt. A failed rebuild stops the
   launch: a server that cannot import its engine is not a degraded arm, it is
   a broken one.
3. The venv is created with `--system-site-packages`, so the image's arm64
   CUDA **torch is inherited and never re-downloaded** — only `diffusers`,
   `transformers` and `accelerate` (and their light pure-Python deps) are
   installed. `torch` is not a dependency of any of the three.
4. Idempotent **from content**: the gate is the real import + version
   assertion, not a marker file or a timestamp, so a venv that exists but is
   stale or broken is rebuilt.

## Version floor

`diffusers >= 0.41.0` is the first release carrying `QwenImage21Pipeline`
(the checkpoint's `model_index.json` declares `_diffusers_version:
0.41.0.dev0` and relies on pipeline-configured sampling sigmas, diffusers PR
#14950). `transformers >= 5.17.0` is the model card's stated floor for the
Qwen3-VL text encoder. The image's own `transformers 5.16.1` is below it,
which is exactly why the venv exists.

## Server surface

`server.py` is a stdlib `http.server` (single-tenant, one lock around the
denoise loop):

| route | meaning |
|---|---|
| `GET /health` | liveness + load state; what a port/health readiness probe sees |
| `GET /v1/models` | the loaded repo id (convenience) |
| `POST /generate` | `{"prompt", "width", "height", "seed", "num_inference_steps", "image_path", "use_kv_cache"}` → runs the pipeline, saves a PNG under `--sample-dir`, returns timing and peak-memory metrics as JSON |

`num_inference_steps` is **null by default**: the checkpoint ships its 8-step
schedule in `model_index.json` (`sample_sigmas`) and the card is explicit that
setting `num_inference_steps` alone does not override it.

## Logs

- mod log: `~/.cache/sparkrun/runtime-cache/vllm/Qwen__Qwen-Image-2.1-Turbo-*/modlogs/qwen-image-2.1-turbo-launcher.log`
  on the node (sparkrun's runtime-cache mount, `MOD_LOGDIR`).
- serve log: sparkrun's container log for the task (`sparkrun logs <id>`); the
  server prints one JSON metrics line per request.
- generated PNGs: `/cache/runtime/qwen-image/samples` in the container =
  the vLLM runtime cache on the node.

## Traps (re-checked in server.py)

VAE tiling stays **off** (tiled decode produces a pink seam column on this
checkpoint) and `cpu_offload` stays **off** (sequential offload roughly
quadruples a reference-image edit). Neither is enabled anywhere in this mod;
they are listed here because the base-model write-up in
`recipes/explore/EXPLORE-MODELS-RESEARCH.md` §6 flags them.
