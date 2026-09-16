# Developer & Agent Guide (`AGENTS.md`)

This document provides technical reference and development instructions for the **Little Cedar Sparkrun Recipe Registry** (`sparkrun-recipe-registry`).

---

## 1. Project Overview & Architecture

The repository serves as a centralized registry for `sparkrun` deployment recipes, container mods, tuning configurations, and benchmark profiles tailored for NVIDIA DGX Spark clusters (Blackwell GB10 GPUs, 128 GB unified LPDDR5X memory per node, and 200 GbE ConnectX-7 RoCE networking).

Confidential information is kept in `.local/CONFIDENTIAL.md`.  References to confidential information are made using shell environment variables defined in `.local/CONFIDENTIAL.md`.

### Repository Structure

```
├── .sparkrun/
│   └── registry.yaml          # Registry manifest declaring components (recipes, tuning, benchmarks, mods)
├── recipes/                   # v2 Sparkrun recipe definitions (organized by model family)
│   ├── ornith/                # Ornith-1.5 model serving recipes (vLLM, SGLang)
│   ├── qwen3/                 # Qwen3 / Qwen3-Coder / Qwen3-VL recipes
│   └── qwen4/                 # Qwen3.8 Flash Next NVFP4 recipes
├── mods/                      # Pre-launch container customization hooks & scripts
│   ├── mod-template/          # Standard template for authoring new container mods
│   ├── make-roce-env/         # Auto-detects CX7 RoCE interfaces & generates .env.roce
│   ├── fix-qwen3.8-flash-next-vllm/ # Source patching for vLLM PLE layer
│   ├── cap-flashinfer-ninja-parallelism/
│   ├── pip-install-fastsafetensors/
│   ├── pip-install-orjson/
│   └── qwen-honed-chat-template/
├── tuning/                    # Pre-computed Triton fused MoE kernel tuning configs
├── benchmarking/              # Sparkrun benchmarking profiles (e.g. fast-smoke.yaml)
├── pyproject.toml             # Python project definition and dependencies
├── uv.lock                    # Dependency lockfile
└── AGENTS.md                  # This file
```

---

## 2. Build & Environment Configuration

The project uses Python (>=3.12) with `uv` as the package and environment manager, and relies on the `sparkrun` CLI tool.

### 2.1. Python Environment Setup

Install and sync dependencies:

```bash
# Sync virtual environment from uv.lock
uv sync

# Activate the virtual environment if needed
source .venv/bin/activate
```

Dependencies include:
- `jinja2 >= 3.1.6`: Template rendering for mod configurations (e.g. `.env.roce`).
- `netifaces >= 0.11.0`: Network interface inspection for RoCE/RDMA network discovery.

### 2.2. Sparkrun CLI Configuration

Ensure `sparkrun` (v0.3.8+) is installed and accessible in `PATH`:

```bash
# Verify sparkrun installation
sparkrun --version

# If installing standalone with uv
uv tool install sparkrun
```

The registry is recognized by `sparkrun` via `.sparkrun/registry.yaml`:
```yaml
registries:
  - name: littlecedar
    description: Little Cedar Group's registry for sparkrun recipes, tuning configs, and benchmark profiles
    recipes: recipes
    tuning: tuning
    benchmarks: benchmarking
    mods: mods
```

### 2.3: Remote Build & Work

If you need to run models, build aarch64 code, or pull docker containers, you can connect to `${WOPR_HEAD_NODE}` via `ssh` and use
`sparkrun status` to find idle nodes and then specify them with `-H <node1>,<node2>,<etc>` when running a recipe with `sparkrun run <recipename>`.
- You can stop a recipe with `sparkrun stop <task ID>`.
- You can get logs from `sparkrun logs <task ID>`.
- You can get <task ID> from `sparkrun status`.

### 2.4: Hugging Face Cache

There is no `/cache/models` directory and never will be.  The Hugging Face cache is an NFS mount on `${WOPR_USER_CACHE}/huggingface`.  When `sparkrun` executes a recipe, it mounts targets under `${WOPR_USER_CACHE}` into the Docker containers under `/cache`.

---

## 3. Recipe Specification & Standards (v2)

All recipes in `recipes/` must adhere to the **v2 recipe specification**:

### 3.1. Required Fields

- `recipe_version: "2"`: String version indicator.
- `model`: Hugging Face repo ID or model identifier (e.g., `RadixArk/Qwen3.8-Flash-Next-NVFP4`).
- `runtime`: Serving runtime (`sglang`, `vllm`, `vllm-distributed`).
- `container`: Container image tag (e.g., `lmsysorg/sglang:dev-cu13-qwen38-next-local`).
- `min_nodes`: Minimum number of nodes required (e.g., `1`, `2`, `4`).
- `metadata`:
  - `model_params`: String param count (e.g., `"125B"`, `"397B"`).
  - `model_dtype`: Base weight precision (`nvfp4`, `bf16`, `int4`).
  - `kv_dtype`: KV cache format (`fp8_e4m3`, `fp8`, `bf16`).
  - `maintainer`: Maintainer contact / org.
  - `tags`: Tag list (`lcg_favorite`, `official`, `fast`, `slow`, `large_context`, etc.).
- `mods`: List of local mods or external mods to run before container starts (e.g. `mods/make-roce-env`).
- `defaults`: Default parameters exposed to CLI overrides (`port`, `host`, `tensor_parallel`, `gpu_memory_utilization`, `max_model_len`, `max_num_seqs`, `quantization`, `fp4_gemm_backend`, etc.).
- `command`: Launch command template. Must reference parameter placeholders with `{placeholder}` (e.g. `--model-path {model} --tp {tensor_parallel}`).

### 3.2. Deprecations & Anti-Patterns to Avoid

- **Do not use `name:`**: Recipe names are derived from filenames on disk.
- **Do not use `cluster_only:`**: Deprecated v1 setting. Use `min_nodes` / `max_nodes` instead.
- **Do not hardcode literal model IDs in `command:`**: Use `{model}` placeholder so sparkrun can rewrite paths for local caching and pre-synced weights.
- **Do not hardcode host machine paths in volumes**: Package patches as a `mods:` script instead of host bind mounts.

---

## 4. Container Mods (`mods/`) Architecture

Mods are modular pre-execution scripts injected into the container before starting the inference runtime.

### 4.1. Mod Directory Structure

Each mod lives in `mods/<mod-name>/`:
- `run.sh`: Main executable entry point. Must be executable (`chmod +x run.sh`) and include `set -euo pipefail`.
- Supporting scripts (e.g. `.py` or patch files).

### 4.2. Standard Mod Conventions

Follow the standard harness from `mods/mod-template/run.sh`:
- **Metadata Exports**:
  ```bash
  export MOD_NAME="my-mod"
  export MOD_DESCRIPTION="Short description of what the mod does"
  export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"
  ```
- **Directory Paths & Permissions**:
  - `CACHEDIR` defaults to `/cache/runtime`.
  - `LOGDIR` defaults to `/cache/runtime/modlogs`.
  - Mods execute as `root`. To avoid permission issues for downstream user processes, inspect `/cache/runtime` ownership:
    ```bash
    export USER_UID="$(stat -c '%u' /cache/runtime)"
    export USER_GID="$(stat -c '%g' /cache/runtime)"
    reown() { chown -R "${USER_UID}:${USER_GID}" "${@}"; }
    ```
- **Logging**: Use the provided `log`, `log_var`, and `log_cmd` functions which write timestamped logs to `${LOGDIR}/${MOD_NAME}.log` and `logger`.
- **Python Dependencies in Mods**: If external libraries are needed, install them into the container environment using `uv pip install ...` or `pip install ...` inside `run.sh`.

---

## 5. Testing & Verification

### 5.1. Validating Recipes with Sparkrun

Run `sparkrun recipe validate` to check recipe schemas and command interpolation:

```bash
# Validate a single recipe
sparkrun recipe validate recipes/qwen4/qwen3.8-flash-next-nvfp4-sglang.yaml

# Validate in strict mode (fails on warnings/suggestions)
sparkrun recipe validate --strict recipes/qwen4/qwen3.8-flash-next-nvfp4-sglang.yaml

# Validate all recipes in the registry
for f in recipes/*/*.yaml; do
  sparkrun recipe validate "$f"
done
```

### 5.2. Estimating VRAM & Hardware Fit

Check memory budget and token context feasibility against DGX Spark 128GB unified memory:

```bash
sparkrun recipe vram recipes/qwen4/qwen3.8-flash-next-nvfp4-sglang.yaml
```

### 5.3. Shell & Python Static Syntax Checks

Verify syntax of all mod shell and Python scripts:

```bash
# Verify shell scripts
for script in mods/*/*.sh; do
  bash -n "$script" && echo "OK: $script"
done

# Verify python scripts
for py in mods/*/*.py; do
  uv run python -m py_compile "$py" && echo "OK: $py"
done
```

### 5.4. Unit Testing Framework & Guidelines

Unit tests can be written using Python's standard `unittest` module and executed with `uv run python -m unittest`.

#### How to Add New Tests
1. Create a test file in a `tests/` directory (e.g. `tests/test_mod_logic.py`).
2. Write test cases testing mod logic (regex parsing, template rendering, AST/source modifications) or recipe schema validation.
3. Run the test suite:
   ```bash
   uv run python -m unittest discover -s tests -v
   ```

#### Executable Test Demonstration
Below is an example test case demonstrating unit tests for mod logic (e.g. `make-roce-env` interface regex matching and Jinja2 rendering) and recipe validation:

```python
import os
import re
import subprocess
import unittest
from jinja2 import Template

class TestRegistryAndMods(unittest.TestCase):
    def test_roce_interface_regex(self):
        """Verify ConnectX-7 network interface regex matching in make-roce-env."""
        regex_ib = re.compile(r"^en(P2|)p[12]s0f[01]np[01]$")
        self.assertTrue(regex_ib.match("enp1s0f0np0"))
        self.assertTrue(regex_ib.match("enP2p1s0f1np1"))
        self.assertFalse(regex_ib.match("eth0"))

    def test_roce_device_name_conversion(self):
        """Verify interface to RoCE device name mapping."""
        def to_roce(name: str) -> str:
            return re.sub(r"np[01]$", "", re.sub(r"^en", "roce", name))

        self.assertEqual(to_roce("enp1s0f0np0"), "rocep1s0f0")
        self.assertEqual(to_roce("enP2p1s0f1np1"), "roceP2p1s0f1")

    def test_recipe_validation(self):
        """Verify that recipes pass sparkrun validation."""
        recipe_path = "recipes/qwen4/qwen3.8-flash-next-nvfp4-sglang.yaml"
        result = subprocess.run(
            ["sparkrun", "recipe", "validate", recipe_path],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("is valid", result.stdout)

if __name__ == "__main__":
    unittest.main()
```

### 5.5 Live Experiments
If you need to run models, aarch64 code, or pull docker containers, you can connect to `${WOPR_HEAD_NODE} via `ssh` and use
`sparkrun status` to find idle nodes and then specify them with `-H <node1>,<node2>,<etc>` when running a recipe with `sparkrun run <recipename>`.
- You can stop a recipe with `sparkrun stop <task ID>`.
- You can get logs from `sparkrun logs <task ID>`.
- You can get <task ID> from `sparkrun status`.

---

## 6. Development & Hardware Guidelines

### 6.1. DGX Spark Memory Management
- **Unified Memory Constraints**: DGX Spark nodes feature 128 GB of unified LPDDR5X memory shared between GPU, CPU, and OS.
- **GPU Memory Utilization**: Set `gpu_memory_utilization: 0.85` in recipe defaults. Values higher than `0.85-0.90` risk OOM panics when the system kernel or OS page cache requests memory.
- **KV Cache Sizing**: NVFP4 weights + FP8 KV cache (`kv_dtype: fp8_e4m3`) is the standard path to maximize context length within the 128 GB memory boundary.

### 6.2. Blackwell FP4 Execution Backends
- For **SGLang**: Use `quantization: modelopt_fp4` and `fp4_gemm_backend: flashinfer_cutlass`.
- For **vLLM**: Ensure FP8/FP4 MTP/PLE patches are loaded via mods when using experimental checkpoint architectures (e.g. `mods/fix-qwen3.8-flash-next-vllm`).

### 6.3. Multi-Node Communication
- Sparkrun handles multi-node tensor parallelism over 200 GbE RoCE by settings the required environment variables, such as `NCCL_NET=IB`, `NCCL_IB_ROCE_VERSION_NUM=2`, and proper `NCCL_IB_HCA` device list.  `mods/make-roce-env` is for compatibility patching with legacy and alternative runners, not Sparkrun.  Do not use `mods/make-roce-env` when building Sparkrun recipes.
