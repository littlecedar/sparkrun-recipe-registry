# `dsv41-vision-fallback` (experimental, trial-only)

Fallback arm (C) of the vision hard-set trial: the TensorFold DSV41 TP=2 lane
with `--vision` but **no VL bias staged**, so image tokens route with the text
bias. It is the control twin of `mods/dsv41-vision-overlay` (arm B).

- Identical to the overlay mod except `TF_DS_VISION_EXTRA` points at this mod
  directory, which deliberately contains no `*.safetensors`.
- `run.sh` asserts the absence of any `*.safetensors` here, so the arm cannot
  silently become arm B.
- Expected serve-log markers: the launcher's `FALLBACK ARM` line plus the
  engine's `no ffn.gate.bias_vl found … image tokens route with the text bias`
  warning and `VL bias for 0 gates`.

Protocol, bar, and decision rule: `.scratch/ds4/vision-hard/PREREGISTRATION.md`.
Not a shippable artifact; lives in the tree untracked during the trial.