---
sessionId: session-260906-232731-ufvv
---

# Requirements

### Overview & Goals
Implement the recipe specified by `experimental-recipes/littlecedar/qwen3.8-flash-next-nvfp4-specification.md` at `experimental-recipes/littlecedar/qwen3.8-flash-next-nvfp4-vllm.yaml`.

### Scope
**In scope**
- Add a v2 Little Cedar vLLM recipe for `nvidia/Qwen3.8-Flash-Next-NVFP4` with MTP.
- Configure mixed-precision metadata accurately, including distinct `kv_dtype`, `model_dtype`, and MTP dtype values.
- Add configurable serving defaults and command flags for tensor parallelism, context/batching, modelopt loading, reasoning parsing, and MTP.
- Resolve every final `mods:` entry through `.sparkrun/registry.yaml` and validate the resolved recipe.

**Out of scope**
- Modifying the specification, registry, existing mod scripts, or application/source code.
- Claiming performance, topology support, or successful startup without the target DGX Spark launch.
- Adding a separate draft model path unless the selected vLLM image explicitly requires and independently verifies it.

### Acceptance Criteria
- The new YAML follows the v2 field order and uses quoted `recipe_version: "2"`.
- The model URL, selected container tag, model revision/date, and resolved vLLM commit are recorded; the commit meets the NVIDIA floor `d4d703caf908786416585ceb1f369e2e0363358b` or later.
- Metadata describes the checkpoint as mixed NVFP4/BF16/FP8 rather than uniformly NVFP4, and does not conflate metadata `kv_dtype` with runtime `kv_cache_dtype`.
- All command placeholders have matching `defaults:` keys, except supported top-level `{model}` interpolation.
- The selected image’s actual MTP CLI syntax is used, expert parallelism and TP/min-node values are treated as tested deployment choices, and no unverified `--spec-model-path` is added.
- `sparkrun show @experimental/qwen3.8-flash-next-nvfp4-vllm` resolves the intended config and mods; `sparkrun run @experimental/qwen3.8-flash-next-nvfp4-vllm` starts on target hardware before the recipe is considered ready.

# Technical Design

### Current Implementation
- The target specification is `experimental-recipes/littlecedar/qwen3.8-flash-next-nvfp4-specification.md`.
- Use `experimental-recipes/littlecedar/littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm.yaml` for Little Cedar metadata, NVFP4 environment, long-form vLLM flags, JSON MTP configuration, and `--enable-expert-parallel` precedent.
- Use `official-recipes/qwen3.8/qwen3.8-27b-fp8-mtp-vllm.yaml` for Qwen MTP defaults and parser flags.
- Use `experimental-recipes/littlecedar/ornith-1.5-35b-a3b-nvfp4-vllm.yaml` for the NVFP4 FlashInfer/Marlin environment and CPU affinity convention.
- `.sparkrun/registry.yaml` maps the `experimental` registry to `experimental-recipes` and `experimental-mods`; the only locally present relevant mod in that namespace is `cap-flashinfer-ninja-parallelism`.

### Key Decisions
- Add only the recipe YAML; preserve the specification and existing mods as reference artifacts.
- Select the container only after checking its `vllm serve --help`, Qwen support, FP4 kernels, and resolved commit. Prefer the JSON `--speculative-config` form when supported, otherwise use the image’s legacy `--spec-method mtp`/`--spec-tokens` form and record that choice.
- Start from the specification’s proposed TP2/two-node deployment and expert parallelism as hypotheses, not model requirements; retain them only after the DGX Spark launch validates them.
- Include only registry-resolvable mods whose purpose is justified by the selected image/checkpoint. Do not copy the spec’s unresolved `drop-caches`, `instanttensor-hybrid-draft-loader`, or `pip-install-fastsafetensors` references without successful resolution.

### Proposed Changes
- Create `experimental-recipes/littlecedar/qwen3.8-flash-next-nvfp4-vllm.yaml` with `recipe_version`, model, runtime, container, `min_nodes`, metadata, mods, env, defaults, and folded `command` in the repository order.
- Set `model: nvidia/Qwen3.8-Flash-Next-NVFP4`, the model-card URL, Little Cedar maintainer, approximately `125B` model size, `nvfp4` model dtype, reconciled FP8 MTP dtype, and a separate KV metadata value.
- Carry forward only image-justified NVFP4 settings such as `OMP_NUM_THREADS`, `VLLM_TARGET_DEVICE`, `MAX_JOBS`, `CUTE_DSL_ARCH`, allocator settings, Marlin/FlashInfer options, and idle behavior.
- Define host, port, tensor parallelism, memory utilization, context length, batching, KV cache dtype, load format, and speculative token defaults; keep `load_format` interpolated rather than hardcoded.
- Start the command with `taskset -c 5-9,15-19 vllm serve {model}` and include supported `--quantization modelopt`, load format, parallelism, `--reasoning-parser qwen3`, `--trust-remote-code`, MTP, and expert-parallel flags.

### File Structure
- **Added:** `experimental-recipes/littlecedar/qwen3.8-flash-next-nvfp4-vllm.yaml`
- **Referenced without modification:** `experimental-recipes/littlecedar/qwen3.8-flash-next-nvfp4-specification.md`, `AGENTS.md`, `.sparkrun/registry.yaml`, the sibling recipes, and `experimental-mods/littlecedar/cap-flashinfer-ninja-parallelism/run.sh`.

### Risks
- A nightly image may not support the JSON MTP syntax, `modelopt`, expert parallelism, or the proposed TP/min-node topology; block or adjust the recipe based on the image help output and launch result rather than guessing.
- Bare mod names and `mods/...` paths can resolve differently; validate the exact final spelling with `sparkrun show`.
- The model-card eight-GPU example does not prove the proposed two-node DGX Spark layout; do not document it as a requirement without runtime evidence.

# Testing

### Validation Approach
- Confirm YAML field order, quoted recipe version, metadata separation, and command/default placeholder completeness by inspecting the new recipe against `AGENTS.md` and sibling recipes.
- Inspect the selected container’s vLLM help/version and record the image tag and resolved commit before finalizing MTP and expert-parallel flags.
- Run `sparkrun show @experimental/qwen3.8-flash-next-nvfp4-vllm` and verify interpolation, container, node count, VRAM, command flags, and every resolved mod.
- Run `sparkrun run @experimental/qwen3.8-flash-next-nvfp4-vllm` on target DGX Spark hardware; inspect `/cache/runtime/modlogs/<MOD_NAME>.log` or journald if startup fails.

### Key Scenarios
- The recipe resolves under the experimental registry and renders the intended model, container, defaults, command, and mods.
- JSON MTP configuration launches when supported; otherwise the legacy syntax is used exactly as exposed by the selected image.
- The model starts with the selected TP/min-node and expert-parallel settings without an unsupported draft-model path.

### Edge Cases
- Missing or unresolved mods remain an explicit blocker; do not silently substitute local paths.
- Missing command defaults, invalid JSON speculative configuration, unsupported flags, or a vLLM commit below the required floor fail validation.
- A failed hardware launch is reported as an unvalidated recipe, with mod logs and runtime errors used to guide any subsequent adjustment.

### Test Changes
- No automated tests are added because this repository is a recipe/content registry with no test framework; `sparkrun show` and the real `sparkrun run` are the applicable validation gates.

# Delivery Steps

### ✓ Step 1: Inspect image and resolve runtime contracts
The selected container, vLLM revision, MTP syntax, and usable mods are recorded before recipe values are finalized.

- Check candidate image tags for Qwen3.8 support, FP4 kernels, `modelopt`, expert parallelism, and the commit floor from the specification.
- Inspect `vllm serve --help` in the selected image to choose JSON `--speculative-config` or legacy MTP flags.
- Resolve candidate mod names and paths through `.sparkrun/registry.yaml`; exclude unresolved references.

### ✓ Step 2: Create the Little Cedar vLLM recipe
`experimental-recipes/littlecedar/qwen3.8-flash-next-nvfp4-vllm.yaml` contains the complete v2 recipe with validated contracts.

- Add the model, runtime, container, min-node hypothesis, metadata, and only resolved mods in canonical field order.
- Add image-justified NVFP4 environment variables and configurable serving defaults, keeping metadata `kv_dtype` separate from `kv_cache_dtype`.
- Add the affinity-prefixed vLLM command with supported modelopt, load-format, parallelism, parser, MTP, trust, and expert-parallel flags.
- Ensure every defaults-derived placeholder is defined and avoid adding `--spec-model-path` unless explicitly required and verified.

### ✓ Step 3: Validate resolution and DGX Spark startup
The recipe either passes the resolved-config and hardware startup gates or remains explicitly blocked with the failing contract identified.

- Run `sparkrun show @experimental/qwen3.8-flash-next-nvfp4-vllm` and verify rendered values, VRAM, flags, and mods.
- Run `sparkrun run @experimental/qwen3.8-flash-next-nvfp4-vllm` on the target DGX Spark topology.
- Inspect mod logs or journald on failure, and only record TP/min-node, expert-parallel, and MTP behavior as validated choices after successful startup.