# `dsv41-vision-overlay` (archived trial — SHIPPED 2026-10-15)

The TensorFold DSV41 TP=2 lane **with image input**, staged as a trial artifact. **The trial
shipped on 2026-10-15** into `mods/tensorfold-dsv41-launcher`: that mod now carries the
launcher's opt-in `--vision` flag **and** the 43-gate `vl_bias.safetensors` beside
`launcher.py`, and the shipped recipe
`recipes/ds4/deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml` passes `--vision` and carries
the `vision` tag.

This copy is kept as **provenance** — the tree exactly as it booted on `.32`/`.33` on
2026-10-06. It is mounted by no recipe: its `run.sh`, its hardcoded
`TENSORFOLD_VISION_EXTRA` default (`/workspace/mods/dsv41-vision-overlay`) and its
warn-only bias check belong to the trial layout, not to the shipped launcher.

It existed to answer two questions, both resolved 2026-10-06 on `.32`/`.33`:

- *Does the shipped TP=2 lane do vision?* **No** — `image_url` → HTTP 400.
- *Can it?* **Yes**, with the two changes this mod made.

## What it changed (both now in the shipped launcher)

1. **Passes `--vision`** to `tensorfold serve`. The engine then loads the DeepSeek-ViT
   tower on rank 0 (`vision tower on rank 0: 0.90 GiB`) and enables the image path.
2. **Stages the VL routing bias.** The EXL3 checkpoint omits all 43
   `*.ffn.gate.bias_vl` tensors; without them the engine warns
   `no ffn.gate.bias_vl found … image tokens route with the text bias` and image
   quality degrades. `vl_bias.safetensors` (43 tensors, 66 736 bytes) is extracted
   from the official `deepseek-ai/DeepSeek-V4.1-Flash` checkpoint. The launcher sets
   `TF_DS_VISION_EXTRA` to the directory holding the bias file —
   `attach_vl_bias()` takes a folder and globs `*.safetensors`, so pointing it at the
   file yields `VL bias for 0 gates`.

Everything else (rendezvous port, rank, caches, Engram) is identical to
`mods/tensorfold-dsv41-launcher/`.

## Verified result

`VL bias for 43 gates`; three discriminating images answered correctly, including a
swapped-order one ("blue square on the left and a red circle on the right") and a
single-shape image where the model rejected the two-shape premise. Warm TTR 54.6 s.

## How it shipped

The two changes moved into `mods/tensorfold-dsv41-launcher/`: `--vision` as an opt-in flag
(a boot without it is byte-identical to the text-only serve line) and
`vl_bias.safetensors` in the mod directory, which the launcher points `TF_DS_VISION_EXTRA`
at — failing closed if the file is absent, because the engine only warns. The shipped
launcher is exported at `@littlecedar/mods/tensorfold-dsv41-launcher`. Rationale and
evidence: `attic/ds4/AGENTS.md` §12.14 and this directory's copy of the trial mod
(`.scratch/ds4/vision-trial/RESULTS.md` no longer exists — evidence store pruned; this
overlay copy and §12.14 carry the record).

## Regenerating `vl_bias.safetensors`

Extracted with a safetensors-only script from the official checkpoint snapshot
(`model.safetensors.index.json` → the 43 `*.ffn.gate.bias_vl` entries → one file).
See the extraction step in `.scratch/ds4/vision-trial/RESULTS.md` (pruned; the file itself
is 43 float32 `[384]` tensors, layers 0–39 plus mtp.0–2).