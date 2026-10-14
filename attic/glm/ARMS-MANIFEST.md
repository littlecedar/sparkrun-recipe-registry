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
