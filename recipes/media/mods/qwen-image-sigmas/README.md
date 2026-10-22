# qwen-image-sigmas

Pre-launch mod that makes a **non-8-step schedule** expressible on the media
lane's Qwen-Image-2.1-Turbo arm. Companion to
[`qwen-image-2.1-turbo-launcher`](../qwen-image-2.1-turbo-launcher/) (which
stages the diffusers venv and ships the server) and to the probe recipe
[`zz-qwen-image-2.1-turbo-4step-diffusers-script.yaml`](../../zz-qwen-image-2.1-turbo-4step-diffusers-script.yaml).

## Why this exists

The launcher's `/generate` already forwards `num_inference_steps` into
`pipe(**call)`, and diffusers ignores it. `QwenImage21Pipeline.__call__`
(diffusers 0.41.0) reads:

```python
if sigmas is None:
    sigmas = self.config.sample_sigmas
    if sigmas is None:
        sigmas = np.linspace(1.0, 1 / num_inference_steps, num_inference_steps)
```

The checkpoint's `model_index.json` carries `sample_sigmas` (8 values), so the
configured grid always wins. Measured on a live serve (2026-10-18): a request
with `"num_inference_steps": 12` returned `"steps": 8` at the same 11.231 s —
accepted silently, not refused. `sigmas` is the only argument that overrides
the config, and `retrieve_timesteps` passes it to the scheduler, whose length
sets the step count. The launcher's server has no such field.

## What the mod does

Writes `<RUNTIME_DIR>/sigmas-server.py` (default
`/cache/runtime/qwen-image/sigmas-server.py`) from the launcher's `server.py`:
the same server plus a step-schedule block. The probe recipe's `command:` runs
the generated file; **the shipped launcher is never modified**.

- **Fail-closed anchors.** The patch is anchored on the launcher's exact
  step-plumbing block and its single `out = pipe(**call)` call site. If either
  is missing or ambiguous, the mod logs `ANCHOR ...` and exits non-zero — a
  launch never proceeds with a `sigmas` field that does not reach the pipeline.
- **Idempotent from content.** The target is regenerated from the launcher's
  source on every launch (write to `.tmp`, then `os.replace`), so a re-run
  cannot double-patch, and a changed launcher produces a changed target.
- **Ordered dependency.** The launcher mod must run first; this mod dies if
  `/cache/runtime/qwen-image/venv/bin/python` is absent. Both mods are in the
  probe recipe's `mods:` list in that order.
- Runs the generated file through `py_compile`, `chmod 755`, and `reown()` on
  the cache mount.

## API contract (`POST /generate`)

Everything the launcher accepts, plus exactly one schedule field (the two are
mutually exclusive; `sigmas` wins if both are sent):

| field | type | meaning |
|---|---|---|
| `sigmas` | `list[float]`, 1–256 entries | Sampling sigmas **excluding the terminal 0**, strictly decreasing, `0 < last <= first <= 1.0`. Overrides the checkpoint's `sample_sigmas`; **the list length is the step count**. Invalid input returns 500 with the reason, never a silent 8-step render. |
| `num_inference_steps` | `int`, 1–256 | Resamples the loaded pipeline's own `config.sample_sigmas` to N steps with both endpoints kept (nearest-index; for the shipped grid, 4 → `[1.0, 0.95418, 0.845148, 0.414568]`). When `N > len(saved)`, falls back to the pipeline's linear grid `[(N-i)/N]`. No longer silently ignored. |

Response is unchanged, and its `steps` field is the ground truth: it counts
`callback_on_step_end` invocations, so it reports the number of steps the
scheduler actually ran.

## Boot check (the falsifier)

The point of the mod is that the schedule landed, not that the server started.
On a boot of the probe recipe, same prompt, seed, size and `use_kv_cache`:

```bash
# control: the checkpoint's saved 8-step grid
curl -s :8000/generate -H 'content-type: application/json' \
  -d '{"prompt":"poster-typography: a bold sans-serif poster reading SPARKRUN, two-color screenprint, centered","width":1024,"height":1024,"seed":42}'
# probe: 4 steps via the new field
curl -s :8000/generate -H 'content-type: application/json' \
  -d '{"prompt":"poster-typography: a bold sans-serif poster reading SPARKRUN, two-color screenprint, centered","width":1024,"height":1024,"seed":42,"num_inference_steps":4}'
```

- **Landed:** the probe response says `"steps": 4`, its PNG differs from the
  8-step control at the same seed (compare `sha256sum`, not size), and wall
  clock drops roughly in proportion (≈6 s expected against the measured
  11.24 s at 8 steps; the ~0.7 s first-step cost does not scale).
- **Still ignored:** the probe response says `"steps": 8`, the PNGs are
  byte-identical, and the wall clock matches 11.24 s. That means the field did
  not reach the pipeline — stop and read the mod log, do not record a 4-step
  cell.
- **Invalid schedule is loud:** posting `{"sigmas": [0.9, 0.5, 0.6]}` must
  return 500 `sigmas must be strictly decreasing`, and `{"sigmas": []}` must
  return 500, never a render.

Explicit-schedule form, same contract:

```json
{"prompt": "...", "seed": 42, "sigmas": [1.0, 0.95418, 0.845148, 0.414568]}
```

## Logs and paths

- mod log: `~/.cache/sparkrun/runtime-cache/vllm/Qwen__Qwen-Image-2.1-Turbo-*/modlogs/qwen-image-sigmas.log`
  on the node (sparkrun's runtime-cache mount, `MOD_LOGDIR`).
- generated server: `/cache/runtime/qwen-image/sigmas-server.py` in the
  container (the node's runtime-cache directory).
- serve log / PNGs: as the launcher documents (`sparkrun logs <id>`;
  `/cache/runtime/qwen-image/samples`).