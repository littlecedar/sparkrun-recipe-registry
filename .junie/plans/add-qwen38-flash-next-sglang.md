---
sessionId: session-260906-235639-vxj3
---

# Requirements

### Overview & Goals
Add a production-oriented Little Cedar SGLang recipe for `nvidia/Qwen3.8-Flash-Next-NVFP4` running across two DGX Spark GB10 nodes with the requested `lmsysorg/sglang:cu13-dev` container.

### Scope
#### In scope
- Add `experimental-recipes/littlecedar/qwen3.8-flash-next-nvfp4-sglang.yaml` using the repository’s v2 recipe schema and Little Cedar conventions.
- Configure the known deployment baseline from `qwen3.8-flash-next-nvfp4-vllm.yaml`: official NVIDIA checkpoint, two-node minimum, TP2, 262144 context starting point, FP8 KV cache, Qwen reasoning/tool parsers, and `modelopt`-compatible NVFP4 loading where SGLang supports it.
- Translate MTP/speculative decoding to the SGLang syntax supported by the selected image, without assuming that VLLM’s JSON speculative configuration or a separate draft checkpoint is valid.
- Include only mods that resolve through `.sparkrun/registry.yaml`, documenting any performance enhancement that remains blocked by registry or image support.

#### Out of scope
- Editing the existing VLLM recipe or changing registry roots.
- Claiming validated throughput, context capacity, or topology support before a real two-node DGX Spark launch.
- Adding an unverified separate draft model path or inventing SGLang flags not exposed by the selected container.

### Acceptance Criteria
- The recipe follows the quoted v2 field order and starts SGLang with the Little Cedar CPU affinity convention.
- `sparkrun show @experimental/qwen3.8-flash-next-nvfp4-sglang` resolves the recipe, interpolates all placeholders, and reports two nodes with TP2.
- All selected flags, model loading behavior, NVFP4/ModelOpt support, MTP syntax, and mods are demonstrated or resolved for the selected image.
- A real `sparkrun run` on two GB10/DGX Spark nodes starts successfully; performance claims remain absent until measured.

# Technical Design

### Current Implementation
- `experimental-recipes/littlecedar/qwen3.8-flash-next-nvfp4-vllm.yaml` is the source of truth for the official checkpoint, mixed NVFP4/BF16/FP8 metadata, `min_nodes: 2`, TP2, 262144 context, FP8 KV cache, and three speculative tokens.
- `experimental-recipes/littlecedar/qwen3.8-27b-nvfp4-dflash2-sglang.yaml` establishes the closest SGLang command pattern: `taskset -c 5-9,15-19 sglang serve`, `--model-path`, `--load-format fastsafetensors`, Qwen parsers, TP, context length, running-request limit, FlashInfer attention, and SGLang speculative options.
- `experimental-recipes/littlecedar/ornith-1.5-35b-a3b-nvfp4-dflash2-sglang.yaml` additionally demonstrates `--kv-cache-dtype`, `--moe-runner-backend flashinfer_cutlass`, and the longer-context environment override.
- `.sparkrun/registry.yaml` maps experimental recipes and mods to `experimental-recipes` and `experimental-mods`; the current tree resolves `cap-flashinfer-ninja-parallelism`, but not the recipe-referenced `drop-caches` or `pip-install-fastsafetensors` paths.

### Key Decisions
- **Dedicated recipe:** Add a new SGLang file rather than alter the VLLM recipe, preserving runtime-specific flags and allowing independent validation.
- **Two-node TP2 baseline:** Set `min_nodes: 2` and `tensor_parallel: 2` as the deployment starting point derived from the existing VLLM recipe; treat it as a tested deployment choice, not a model requirement.
- **Image-verified CLI:** Use `lmsysorg/sglang:cu13-dev` as requested, but inspect its `sglang serve --help` and installed model/quantization support before selecting MTP, FP4 backend, expert-parallel, or distributed-network flags.
- **No guessed draft checkpoint:** Prefer the model’s own MTP material if this SGLang build supports it; do not add a separate `--speculative-draft-model-path` without an independently verified compatible checkpoint.
- **Resolved mods only:** Start with `cap-flashinfer-ninja-parallelism` if its purpose is applicable and resolution succeeds; do not carry unresolved `drop-caches` or `pip-install-fastsafetensors` references into a production recipe unless their registry entries become available.

### Proposed Changes
- Create `experimental-recipes/littlecedar/qwen3.8-flash-next-nvfp4-sglang.yaml` with:
  - `recipe_version: "2"`, model `nvidia/Qwen3.8-Flash-Next-NVFP4`, runtime `sglang`, requested container, and `min_nodes: 2`.
  - Metadata matching the VLLM recipe: model URL, 125B parameter size, mixed NVFP4 model dtype, FP8 MTP dtype, FP8 KV dtype, Little Cedar maintainer, and conservative performance tags.
  - Environment values only after image verification, likely including the existing CPU/thread affinity and CUDA allocator/FlashInfer tuning where supported by SGLang rather than copying VLLM-only variables.
  - Defaults for host, port, TP2, memory fraction around the VLLM baseline, 262144 context, request/batching limits, FP8 KV cache, FlashInfer attention, fastsafetensors loading, and configurable speculative token count.
  - A folded SGLang command with `taskset`, `sglang serve`, model path, trust-remote-code, Qwen parsers, load format, host/port, TP, context, request limits, memory fraction, KV cache, attention/MoE backends, and image-supported MTP flags.
- Keep every command placeholder backed by `defaults:` and avoid VLLM-only options such as `--quantization` unless the SGLang image explicitly exposes an equivalent accepted setting for this checkpoint.
- If SGLang requires an explicit ModelOpt/FP4 backend or distributed expert-parallel flag, add it as a configurable default only after confirming the image help and model startup path.

### File Structure
- **Add:** `experimental-recipes/littlecedar/qwen3.8-flash-next-nvfp4-sglang.yaml`
- **Reference without modification:** `experimental-recipes/littlecedar/qwen3.8-flash-next-nvfp4-vllm.yaml`, `qwen3.8-27b-nvfp4-dflash2-sglang.yaml`, `ornith-1.5-35b-a3b-nvfp4-dflash2-sglang.yaml`
- **Validate against:** `.sparkrun/registry.yaml` and `experimental-mods/littlecedar/cap-flashinfer-ninja-parallelism`

### Risks
- `cu13-dev` may expose different speculative-decoding, FP4, or distributed flags than the existing `dev-cu13` examples; unsupported flags must be removed or replaced rather than guessed.
- The NVIDIA checkpoint’s VLLM `modelopt` setting may be auto-detected or represented differently by SGLang; startup validation must confirm the actual loader path.
- 262144 context, FP8 KV cache, and TP2 across two GB10 nodes are starting values and may require tuning for memory or interconnect behavior.

# Testing

### Validation Approach
- Confirm the new YAML parses under the SGLang recipe schema and that every `{placeholder}` resolves.
- Inspect the selected image’s SGLang CLI and model-loading behavior before finalizing runtime-specific flags.
- Run `sparkrun show @experimental/qwen3.8-flash-next-nvfp4-sglang` and verify the resolved container, node count, TP2, context, memory settings, parsers, speculative configuration, and mods.
- Run `sparkrun run @experimental/qwen3.8-flash-next-nvfp4-sglang` on two DGX Sparks and inspect startup/mod logs if it fails.

### Key Scenarios
- Recipe discovery succeeds through the hidden experimental registry using the intended short name.
- SGLang starts the official NVIDIA checkpoint with the selected NVFP4/ModelOpt-compatible loader and exposes the configured OpenAI-compatible endpoint.
- Qwen reasoning and tool-call parsing initialize without requiring an unverified draft model.
- Two-node TP2 initialization completes and the configured FP8 KV cache and long-context settings fit the available GB10 memory.

### Edge Cases
- Reject or revise any speculative/MTP flag absent from `sglang serve --help` in `cu13-dev`.
- Detect unresolved mods before launch; keep the recipe blocked or remove the reference rather than relying on local-only files.
- If the image cannot load the checkpoint or the topology cannot initialize, record the exact image/flag failure and do not describe the recipe as production-ready.

# Delivery Steps

### ✓ Step 1: Define the SGLang recipe from the validated VLLM baseline
Create the dedicated Qwen3.8 Flash-Next SGLang recipe with the model identity, two-node/TP2 topology, metadata, conservative memory/context defaults, and Little Cedar command structure.

- Add `experimental-recipes/littlecedar/qwen3.8-flash-next-nvfp4-sglang.yaml`.
- Translate known VLLM settings into SGLang-native placeholders and flags.
- Preserve mixed-precision metadata and avoid unsupported VLLM-only options.

### ✓ Step 2: Integrate image-supported performance and MTP settings
Make the recipe’s loading, FlashInfer/MoE, KV-cache, distributed, and speculative-decoding settings match the actual `lmsysorg/sglang:cu13-dev` interface.

- Check the image’s `sglang serve --help` and checkpoint support.
- Select supported fastsafetensors, FP4/ModelOpt, attention/MoE, and MTP options.
- Resolve or remove mods through `.sparkrun/registry.yaml` so no local-only reference ships.

### ! Step 3: Validate registry resolution and two-node launch
Demonstrate that the recipe resolves and starts on the target DGX Spark deployment.

- Run `sparkrun show @experimental/qwen3.8-flash-next-nvfp4-sglang` and inspect interpolation and VRAM output.
- Run the recipe on two GB10/DGX Spark nodes.
- Inspect runtime/mod logs for startup, parser, memory, distributed, and speculative-decoding failures; tune only from observed launch results.