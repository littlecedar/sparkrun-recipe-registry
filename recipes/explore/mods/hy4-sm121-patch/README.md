# `hy4-sm121-patch`

Stage atakann's six Hy4-flash Python files into the vendor `vllm/vllm-openai:hy4-flash`
image tree at pre-exec, so the `zz-hy4-flash-220b-nvfp4-tp2-vllm` arm can serve
`atakans/Hy4-flash-NVFP4` at TP=2 without building an image.

## Why a mod, not an image

The upstream recipe (`atakann/dgx-spark-recipes`, MIT) builds a local image
`dgx-spark-recipes/vllm-hy4-flash:77766db` with `--setup`, which is not published:
`ghcr.io/v2/atakann/vllm-hy4-flash/tags/list` answers **404** (anonymous token
included), and the Docker Hub user `atakann` has **no repositories**. There is no
digest to pin, so the vendor image the BF16 quartet arm already pins is used and
the six files ride this mod instead.

Every file is plain Python. Checked at the pinned commit: no
`cpp_extension`/`load_inline`/`ctypes`/`subprocess`/`os.system`/`importlib`, no
`if __name__` block, no module-level side effect beyond imports and class/def
bodies. Nothing here is a compiled extension or an import-time action, so a
pre-exec filesystem write is exactly what the Dockerfile's `COPY` did.

## Pinned upstream

| | |
|---|---|
| repo | <https://github.com/atakann/dgx-spark-recipes> (MIT) |
| commit | `e764efa3efed3e21fe543c3fffc927eb6a00bff8` (2026-11-18) |
| directory | `images/vllm-hy4-flash` |
| base image | `vllm/vllm-openai@sha256:5e2c1badbca60595d6591c60feb4b8547f59da96e7a91710d40239250e721aba` (the arm64 child of the recipe's `hy4-flash` pin) |
| base vLLM | `77766db` + the Hy4-flash PR, FlashInfer 0.7.4 |

## File map

`$V` is `sysconfig.get_paths()["purelib"]/vllm` — `/usr/local/lib/python3.12/dist-packages/vllm`
in this image. `sm120.py` is new; the other five replace the image's file at the
Dockerfile's `COPY` destination.

| vendored | blob (git) | sha256 | target | mode |
|---|---|---|---|---|
| `patch/sm120.py` | `a8dd1d7efde8a4b4f6b9aa7f827be9a02d1d4375` | `b260fc169c926b5f026081a993650bfe43cce6cd53b8b80fdcabbc6e4ec0f5df` | `$V/models/hy_v4_flash/nvidia/sm120.py` | new |
| `patch/attention.py` | `c3a63eea10bc45a251039bc2217437bf2079d93f` | `b67afe0ff16b384261dec87338c559ae089843ad8bcc094f26671661c119f8b2` | `$V/models/hy_v4_flash/nvidia/attention.py` | replace |
| `patch/model.py` | `1ca97b69493b7aa548eb4f6ff899af3137f51e98` | `69865a097d847d446fdcdfb81672249a426a8abfea4bc8da278efb2e79fa2716` | `$V/models/hy_v4_flash/nvidia/model.py` | replace |
| `patch/hy_v4_attention.py` | `96814ef8b53a70985e266cb8e2211f59897ab42a` | `269d390eeaec8a6cf5f85c014542ce4426f4d62e904c82499d6d34633c1938dd` | `$V/models/hy_v4/nvidia/attention.py` | replace |
| `patch/dfly_config.py` | `7820a3f945a3e49988694a31d34b7dc5224e91a7` | `9513efde31a50279fe892ba01d27a546dc15b494fcd7b628639e8f82b26dafe8` | `$V/models/hy_v4/dfly_config.py` | replace |
| `patch/mla_attention.py` | `b760381da02a29824f5fc7dc90cece3863d699e3` | `9540ec2427fe3d747944165a2d416812f2a8e64c74c062e24c9e1b44e96aec67` | `$V/model_executor/layers/attention/mla_attention.py` | replace |

The name change is deliberate: upstream's `hy_v4_attention.py` is the patched
`vllm/models/hy_v4/nvidia/attention.py` that the patched `hy_v4_flash/attention.py`
imports as `HYV4MLAAttention`.

What the six do, per the upstream Dockerfile:

- `sm120.py` — Hy4's per-head learnable attention sink through FlashInfer's SM120
  sparse-MLA kernel (stock SM120 impl does not forward a sink).
- `attention.py` — Hy4-flash layers pick that backend on compute capability 12
  (sparse and sliding-window); `major == 9/10` keeps upstream.
- `hy_v4_attention.py` — the same choice for the DFly drafter's layers.
- `mla_attention.py` — `fp8_ds_mla` KV cache on sliding-window MLA (vllm#68365).
- `model.py` — ModelOpt NVFP4 experts: weight, block scale, global scale and
  input scale per expert.
- `dfly_config.py` — DFly accepts a ModelOpt NVFP4 target (the drafter's own
  layers stay BF16).

## Runtime knobs are the recipe's, not the mod's

The Dockerfile's two `ENV`s live in the recipe's `env:` so the config chain can
see them:

```yaml
env:
  CUTE_DSL_ARCH: sm_121a
  VLLM_WORKER_MULTIPROC_METHOD: spawn
```

`HOME=/cache` is the Dockerfile's third `ENV`; sparkrun's cache mount already
provides the compile cache, so the recipe does not restate it.

## Anchors (fail closed)

Nothing is written until every one of these holds; any miss aborts the launch:

- `$V/models/hy_v4_flash/nvidia/` and `$V/models/hy_v4/nvidia/` exist — the image
  is the Hy4-flash build.
- Siblings the patched files import exist: `hy_v4_flash/configs.py`,
  `hy_v4_flash/nvidia/{compressed_indexer,swa,moe}.py`, `hy_v4/nvidia/hc.py`.
- `hy_v4/nvidia/attention.py` contains `class HYV4MLAAttention`;
  `hy_v4/nvidia/model.py` contains `HYV4ForCausalLM`.
- `v1/worker/gpu/spec_decode/dfly/config.py` contains `DFlySpeculatorConfig`.
- `v1/attention/backends/mla/flashinfer_mla_sparse.py` contains
  `FlashInferMLASparseSM120Backend` and `_get_workspace_buffer`;
  `flashinfer_mla_sparse_sm120.py` contains `FlashInferMLASparseSM120Impl`.
- `model_executor/layers/attention/mla_attention.py` contains `class MLACommonImpl`.
- The three replace targets exist.
- `sha256sum -c patch/SHA256SUMS` passes (registry checkout intact).

After staging, each target's sha256 is re-read and compared, and all six are
compiled with `compile()` in-process (`python3 -B`, no imports, no `__pycache__`
left for a uid-1000 serve). Re-running the mod on a restarted container is a
no-op: a target already carrying the vendored digest is logged and skipped.

## Known limit

`mla_attention.py` is a whole-file replacement of a core vLLM module, vendored
against the image digest the recipe pins. A container digest bump must re-vendor
the six files from a newer atakann commit; the anchor on `class MLACommonImpl`
catches a moved/renamed core module but cannot detect a newer upstream
`mla_attention.py` that this copy would shadow.

## Reference measurement (upstream, 2026-11-18)

Two DGX Sparks, TP=2 + expert parallel, DFly k=5, `fp8_ds_mla`, 262,144 context,
`--kv-cache-memory-bytes 6G`: JSON 38.3 / code 36.5 / rewrite 36.1 / explain 25.0 /
story 17.3 tok/s; prefill 1,110 t/s at 4K, 1,461 at 32K; 15 tok/s without the
drafter; lowest free memory 12.8 GiB. Thinking is on by default; disable with
`chat_template_kwargs {"reasoning_effort":"no_think"}`.
