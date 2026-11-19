# `attic/media/` — archived media-lane arms (provenance)

Nothing here is served by the registry; `recipes/media/` keeps the lane's shipped TTS, image and
video arms and indexes them from its own `README.md`. This directory holds retired probe arms that
already have a recorded verdict, kept tracked so the measurement is never lost and the restore is
one `git mv` away.

**Policy.** An arm lands here when its question is answered — measured cell or quoted refusal — and
the lane README row keeps the measured numbers (or this manifest carries them). Recipes here are
**frozen provenance**: do not retune them and do not clear a `sparkrun recipe validate` warning by
editing them, because `attic/` is outside the registry gate. To restore, `git mv` the file back to
`recipes/media/` and delete its row here.

## Manifest

| file | runtime | what it is | measured cell | receipt |
|---|---|---|---|---|
| `zz-minimax-h3-fl2va-t2va-tp4-sglang.yaml` | SGLang v0.5.22 (`lmsysorg/sglang:v0.5.22-cu130`) | MiniMax-H3 four-rank video cell (QUESTIONS #7, TP=4 over `.31`–`.34`): AdaLN-pruned FP8 DiT 19.52 GiB + NVFP4-AWQ Qwen3-VL-32B text encoder 14.61 GiB + fp16 video VAE + fp32 audio VAE, 13.94 GiB/node resident | **Measured negative, 2026-10-24:** the four-rank serve deadlocks in the first distributed video request — denoise exchange, all four GPUs 0 %, warmup frozen at `0/1`, zero errors. Walls 1–2 (auto-tuner device probe → `speed` mode; hub-shaped component overrides under offline mode → absolute pool paths) are fixed in-recipe; wall 3 is engine-side | `head:~/benchmarks/tp4-window-20261024/H3-TP4-CELL-RESULT.md` (boots 12/13/14/15) |

**Licence.** MiniMax H3 Community License — territorial: the Applicable Territory is worldwide minus
EU/UK/KR/US, so a boot is permitted at a non-US site and not at a US site. Read the in-file banner
before any restore.

*Archived 2026-11-19 by the TP≥4 probe retirement pass.*
