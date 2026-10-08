# `dsv41-vision-overlay` (experimental)

The TensorFold DSV41 TP=2 lane **with image input**. This is a trial artifact, not
the shipped recipe: `recipes/ds4/deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml`
uses `mods/tensorfold-dsv41-launcher/`, which serves text only.

It exists to answer two questions, both resolved 2026-10-06 on `.32`/`.33`:

- *Does the shipped TP=2 lane do vision?* **No** — `image_url` → HTTP 400.
- *Can it?* **Yes**, with the two changes this mod makes.

## What it changes vs. the shipped launcher

1. **Passes `--vision`** to `tensorfold serve`. The engine then loads the DeepSeek-ViT
   tower on rank 0 (`vision tower on rank 0: 0.90 GiB`) and enables the image path.
2. **Stages the VL routing bias.** The EXL3 checkpoint omits all 43
   `*.ffn.gate.bias_vl` tensors; without them the engine warns
   `no ffn.gate.bias_vl found … image tokens route with the text bias` and image
   quality degrades. `vl_bias.safetensors` (43 tensors, 66 736 bytes) is extracted
   from the official `deepseek-ai/DeepSeek-V4.1-Flash` checkpoint. The launcher sets
   `TF_DS_VISION_EXTRA` to **this mod directory** — `attach_vl_bias()` takes a folder
   and globs `*.safetensors`, so pointing it at the file yields `VL bias for 0 gates`.

Everything else (rendezvous port, rank, caches, Engram) is identical to
`mods/tensorfold-dsv41-launcher/`.

## Verified result

`VL bias for 43 gates`; three discriminating images answered correctly, including a
swapped-order one ("blue square on the left and a red circle on the right") and a
single-shape image where the model rejected the two-shape premise. Warm TTR 54.6 s.

## To ship this

Move the `--vision` flag and the `TF_DS_VISION_EXTRA` default into
`mods/tensorfold-dsv41-launcher/launcher.py`, ship `vl_bias.safetensors` there (or via
a dedicated staging step), and add `vision` to the recipe's `metadata.tags`. Full
rationale and evidence: `recipes/ds4/AGENTS.md` §12.14 and
`.scratch/ds4/vision-trial/RESULTS.md`.

## Regenerating `vl_bias.safetensors`

Extracted with a safetensors-only script from the official checkpoint snapshot
(`model.safetensors.index.json` → the 43 `*.ffn.gate.bias_vl` entries → one file).
See the extraction step in `.scratch/ds4/vision-trial/RESULTS.md`.
