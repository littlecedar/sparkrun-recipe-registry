# attic/glm/ — archived GLM arms (provenance)

Archived 2026-10-13. Nothing here is served by the registry; `recipes/glm/` ships no recipe — its
TensorFold **runbook notes** live in [`AGENTS.md`](AGENTS.md) (moved there 2026-10-14), indexed from
`recipes/glm/README.md`.

| file | runtime | what it is | why archived |
|---|---|---|---|
| `glm-5.3-flash-nvfp4-dflash-vllm.yaml` | vLLM | repo B's GLM-5.3-Flash NVFP4 TP=4 formula, image digest-pinned (`vllm/vllm-openai:glm53-flash`), checkpoint `36c184c6` | **Proven-negative on the pinned public image.** Five boots on `.30-.33` (2026-10-13) all died in the container serve log: the pinned public image's SM120 sparse-MLA backend forces the `fp8_ds_mla` KV layout, whose `concat_and_cache_mla` kernel needs a 64-dim RoPE tail while the checkpoint is NoPE MLA (`qk_rope_head_dim 0`); `bfloat16`/`nvfp4_ds_mla` KV select no backend and `FLASHINFER_MLA_SPARSE` is unsupported on GB10; the DFlash2 drafter needs the absent `SupportsEagle3`. Repo B qualified it on a local, unpublished image (no public digest); the recipe is correct and the image is the blocker. It never produced a C1 or a quality score. |

**Owner decision 2026-10-13** (`mad-science/TODO.md` `#DECISIONS`): archived here as a proven-negative
arm. Receipts: `~/benchmarks/glm53-flash-20261013/` on the head (eight launch logs).

**Do not re-add it to `recipes/glm/`** without a public image that can serve this checkpoint. The lane's
boot-verified serving lines are the TensorFold runbooks in [`AGENTS.md`](AGENTS.md), indexed from
`recipes/glm/README.md`.

## Concurrency probes (measured 2026-11-08; retired 2026-11-19)

The shipped Flash arm's ladder peaks at C2 and falls at C5/C10 (`102.36 / 79.49 / 73.37` t/s). These
three probes isolate the mechanism; all three ran as one triad on one image id
(`sha256:7f8f1b38bcf1770e527bdc9ceacdc663063d2871e464f7693a8602e0efbd4a95`, each leg's `image.txt`),
so they are measured, not authored. `mods:` reaches back into the live lane
(`../../recipes/glm/mods/tensorfold-glm-exl3-launcher`) — the shim is still shipped for the two live arms.

| file | lever | measured cell | receipt |
|---|---|---|---|
| `zz-glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang-nodrafter.yaml` | DFlash2 removed: the shim maps `--drafter-repo none` onto the engine's `--no-drafts`, at the mod's `--parallel 8` | **53.20 / 74.29 / 76.47 / 71.25 t/s** C1/C2/C5/C10; C2→C10 **−4.1 %**, flat inside the C2 sigma, while losing 17.8–48.5 % per rung | `head:~/benchmarks/h2h-20261107/receipts/zz-glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang-nodrafter.json` (`measured: true`; ladder `…/tp12-window/zz-glm-…-nodrafter/ladder.json`) |
| `zz-glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang-parallel.yaml` | slot cap promoted to a recipe key: `--parallel {parallel}` (engine range 1–8) | **100.2 / 117.1 / 84.6 / 79.4 t/s** at the 4-slot cap, still falling past C2 | `head:~/benchmarks/h2h-20261107/receipts/zz-glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang-parallel.json` |
| `zz-glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang-dflash2k.yaml` | config-identical carrier for the k sweep (the queue plan refuses two rows on one path); the value rides the lease env `TF_GLM_DFLASH_POLICY` | same-window shipped control **103.25±5.46 / 109.41±31.29 / 94.18±2.62 / 86.65±1.31 t/s** and boot2 **105.90 / 120.46 / 96.80 / 86.87 t/s** (C2→C10 −20.8 %) bound the carrier's window | `head:~/benchmarks/h2h-20261107/receipts/zz-glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang-dflash2k.json` |

**Reading.** The C5→C10 fall survives with no DFlash2 at all, so the drafter is not the cause; the
4-slot leg still falls past C2, so the slot cap is not it either — the mechanism stays open. The
sweep hook (`recipe_env()` whitelisting `TF_GLM_DFLASH_POLICY` / `TF_GLM_MULTI_WINDOW`) stays in the
live shim, so a future k/window sweep still needs no per-value recipe.
