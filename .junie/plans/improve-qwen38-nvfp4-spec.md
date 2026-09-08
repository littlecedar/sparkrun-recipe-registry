---
sessionId: session-260906-225927-kepe
---

# Requirements

### Overview & Goals
Improve `experimental-recipes/littlecedar/qwen3.8-flash-next-nvfp4-specification.md` into an accurate, implementation-ready plan for a Qwen3.8-Flash-Next NVFP4 vLLM recipe with MTP, while clearly separating repository-verified conventions from upstream and hardware assumptions.

### Scope
**In scope**
- Correct factual and internal inconsistencies in the target checkpoint, MTP provenance, vLLM minimum revision, parallelism, metadata, environment, defaults, command, and mod guidance.
- Replace unresolved or nonexistent local references with registry-aware guidance grounded in `.sparkrun/registry.yaml` and the actual Little Cedar recipe/mod tree.
- Make acceptance criteria explicit for the eventual recipe and its launch validation.

**Out of scope**
- Creating the YAML recipe itself.
- Adding or changing mod scripts, registry entries, or source code.
- Claiming successful hardware performance without a real `sparkrun` launch.

### Expected Outcome
A reader can use the specification to create the recipe without guessing which facts are confirmed, which values are recommended starting points, and which items must be verified against the selected container, vLLM revision, registry, and DGX Spark hardware.

# Technical Design

### Current Implementation
- The target document is a checklist/specification at `experimental-recipes/littlecedar/qwen3.8-flash-next-nvfp4-specification.md`.
- Local conventions come from `AGENTS.md`, `.sparkrun/registry.yaml`, `official-recipes/qwen3.8/qwen3.8-27b-fp8-mtp-vllm.yaml`, `experimental-recipes/littlecedar/ornith-1.5-35b-a3b-nvfp4-vllm.yaml`, and `experimental-recipes/littlecedar/littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm.yaml`.
- The current spec mixes the official v2 topology with an `executor` field that is not used by the closest MTP recipe, alternates between `kv_dtype` and `kv_cache_dtype`, cites mod paths that are not all present in this checkout, and presents TP2/min-nodes assumptions as requirements.

### Key Decisions
- Keep the document as an implementation spec, not a recipe patch; preserve the eventual recipe’s v2 field order and Little Cedar styling.
- Use a three-way evidence classification for each important value: repository convention, upstream/model-card requirement, or hardware/container validation hypothesis.
- Treat the NVIDIA model-card vLLM commit `d4d703caf908786416585ceb1f369e2e0363358b` or later as the upstream compatibility floor, while retaining PR #55513 only as historical context if still relevant to the selected image.
- Document that the model’s MTP module and FP8 source are byte-compatible according to the model card, and avoid recommending a separate `--spec-model-path` unless the selected vLLM implementation explicitly requires it.
- Preserve runtime launch validation as the final authority: resolved config via `sparkrun show`, mod resolution through `.sparkrun/registry.yaml`, and hardware startup via `sparkrun run`.

### Proposed Changes
- Rewrite the target model section with sourced facts: mixed NVFP4/FP8/BF16 composition, MTP source relationship, documented baseline parallelism, and the distinction between model-card defaults and DGX Spark TP2 experimentation.
- Normalize the recipe checklist to the actual schema and sibling patterns, including whether `executor` is supported/needed rather than asserting it unconditionally.
- Split MTP guidance into: model-provided MTP behavior, required expert-parallel capability, supported vLLM syntax for the selected image, and fallback/rollback if the JSON `--speculative-config` form is unavailable.
- Replace the current broad mod list with a registry-resolution table naming each intended reference, its actual location, and the reason it is required; explicitly flag `instanttensor-hybrid-draft-loader` and `pip-install-fastsafetensors` for existence/resolution verification before use.
- Consolidate environment/default recommendations from the NVFP4 sibling recipe, removing speculative or commented settings unless they are justified for this checkpoint/container.
- Add acceptance criteria for YAML structure, placeholder interpolation, metadata naming, MTP/EP flags, model revision, registry resolution, and launch behavior.
- Retain the repository limitations note, but make external verification steps concrete and remove contradictory wording such as calling a draft path both a placeholder and unnecessary.

### File Structure
- Modify only `experimental-recipes/littlecedar/qwen3.8-flash-next-nvfp4-specification.md`.
- Reference, without modifying, `.sparkrun/registry.yaml`, `AGENTS.md`, the three sibling recipe YAMLs above, and the existing mod directories under `experimental-recipes/littlecedar/mods/`.

# Testing

### Validation Approach
- Re-read the revised specification against the v2 conventions in `AGENTS.md` and the actual field/layout patterns in the sibling recipes.
- Verify every named mod and registry form against `.sparkrun/registry.yaml` and the repository tree; unresolved references remain explicit blockers rather than silently becoming recipe entries.
- Check that every placeholder mentioned in `command:` has a corresponding `defaults:` value and that metadata keys use one consistent naming convention.
- Cross-check external claims against the NVIDIA model card and the selected vLLM/container compatibility requirement, recording source/revision and date-sensitive assumptions.

### Key Scenarios
- A recipe author can determine the intended model, runtime, container floor, parallelism starting point, MTP configuration, and required mods from the document.
- A reviewer can distinguish a confirmed local convention from a value that requires DGX Spark launch validation.
- A failed mod lookup or unsupported MTP flag is identified before the recipe is considered ready.

### Edge Cases
- The selected nightly image may use legacy `--spec-method`/`--spec-tokens` flags instead of JSON `--speculative-config`; the spec must require checking the actual image CLI.
- TP2 across two DGX Spark nodes may differ from the model card’s TP8 example; the document must not call either universally required without evidence.
- `kv_dtype` metadata and `kv_cache_dtype` runtime defaults serve different purposes and must not be conflated.
- The registry may resolve bare mod names differently from `mods/...` paths; both forms must be tested against the configured registry before shipping.

# Delivery Steps

### ✓ Step 1: Audit and classify specification claims
The specification has a source-backed inventory of confirmed facts, local conventions, hypotheses, and blockers.

- Reconcile the target document with `AGENTS.md` and `.sparkrun/registry.yaml`.
- Compare model/runtime choices with `official-recipes/qwen3.8/qwen3.8-27b-fp8-mtp-vllm.yaml`, `ornith-1.5-35b-a3b-nvfp4-vllm.yaml`, and the grafted MTP recipe.
- Cross-check model-card facts including the vLLM commit floor, MTP byte-compatibility, and documented parallelism.
- Identify contradictory fields, stale PR assumptions, and unresolved mod references.

### ✓ Step 2: Rewrite the recipe implementation checklist
`qwen3.8-flash-next-nvfp4-specification.md` provides a coherent, registry-aware recipe plan.

- Normalize the v2 schema, field ordering, metadata terminology, env/default guidance, and command interpolation requirements.
- Define MTP and expert-parallel behavior using syntax supported by the selected vLLM image, with explicit fallback checks.
- Separate model-card requirements from DGX Spark TP2 deployment hypotheses.
- Add a mod-resolution table and remove or qualify references not present in the repository.
- Add concrete acceptance criteria for the eventual YAML recipe.

### ✓ Step 3: Validate the improved specification
The revised spec is internally consistent and ready to guide recipe creation without pretending unverified runtime behavior is proven.

- Verify all referenced files, fields, mod paths, and registry namespaces against the repository.
- Check command/default placeholder completeness and distinguish metadata keys from runtime flags.
- Re-read the document for contradictions around draft models, KV cache naming, executor usage, and MTP flag formats.
- Preserve explicit `sparkrun show`/`sparkrun run` hardware validation as the final gate for any later recipe implementation.