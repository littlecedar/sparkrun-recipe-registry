# Developer & Agent Guide (`AGENTS.md`)

This document provides technical reference and development instructions for the **Little Cedar Sparkrun Recipe Registry** (`sparkrun-recipe-registry`).

---

## Workflow

- install: `uv sync`. Prereq outside uv: `sparkrun --version` (v0.3.8+), else `uv tool install sparkrun`. No pytest/ruff/black/mypy/shellcheck/yamllint/pre-commit/CI anywhere; `pyproject.toml` has no `[tool.*]`.
- build: N/A — no Makefile/justfile/Taskfile/tox/CMake. Root `package-lock.json` is an empty stub: never run `npm`.
- test all: `uv run python -m unittest discover -s tests -v` (`uv run --offline python -m unittest discover -s tests` against the offline cache)
- test harness `discover` cannot see; takes a **required** positional path to a real `tokenizer_manager.py` (a bare run exits 2, which its own docstring warns is never a verdict on the patch). Exit 0=patched, 1=unpatched, 2=harness-failed: `uv run python mods/fix-sglang-spec-metrics-empty-verify/test_spec_metrics_guard.py <tokenizer_manager.py>`
- test file: `uv run python -m unittest tests.test_qwen3_vl_embeddings` (no `__init__.py`; path form also works: `uv run python -m unittest "tests/test_qwen3_vl_embeddings.py"`)
- test case: `uv run python -m unittest tests.test_qwen3_vl_embeddings.TestRecipeInvariants.test_json_defaults_survive_as_one_shell_word` (class-only form valid)
- lint: `for s in mods/*/*.sh; do bash -n "$s" || exit 1; done`; `for p in mods/*/*.py tools/*.py; do uv run python -m py_compile "$p" || exit 1; done`; `HOME="$PWD/.local/sparkrun-home" sparkrun recipe validate <recipe.yaml>`. `mods/*/*.py` misses `tools/`, so `tools/*.py` must be added. Use plain `validate` as the gate, **not** `--strict`: 6 of the 18 recipes already exit 1 under it on `deprecated-recipe-name`, `deprecated-brace-escape`, `unmapped-config-key`, `non-portable-mount`, `deprecated-topology` warnings that are accepted as-is. Do not "fix" a recipe to satisfy `--strict`, and never edit a recipe merely to clear a `suggestion` (e.g. `restated-managed-path` on `qwen3-vl-reranker-2b-vllm-b12x.yaml`, whose explicit `/cache/runtime` path is deliberate).
- format: no formatter or style checker exists. `command:` YAML style is machine-enforced by the guard suite — do not introduce one.
- after every edit:
  ```bash
  set -e
  H=$PWD/.local/sparkrun-home
  uv run python -m unittest discover -s tests
  for f in recipes/*/*.yaml; do HOME="$H" sparkrun recipe validate "$f" >/dev/null; done
  for s in mods/*/*.sh; do bash -n "$s"; done
  for p in mods/*/*.py tools/*.py; do uv run python -m py_compile "$p"; done
  ```
  `.local/sparkrun-home` is git-ignored — `mkdir -p .local/sparkrun-home` on a fresh clone. Without `HOME=$H` every `sparkrun` call dies on `PermissionError: ~/.config/sparkrun/registries.yaml` before reading a recipe. `py_compile` leaves untracked `__pycache__/` (not gitignored): `find mods tools -name __pycache__ -type d -exec rm -rf {} +`.
- debug: render before launching — `HOME="$H" sparkrun run <recipe> -H <node> -n`; `-n` alone errors `No hosts specified`. Grep the rendered line for the flag you just added. `-o key=value` overrides recipe defaults, `-b key=value` benchmark args (both repeatable); `-v`/`-vv`/`-vvv`, `-q` for scripting. `HOME="$H" sparkrun recipe vram <recipe>`; `sparkrun show <recipe>`. Lifecycle `sparkrun status` for task IDs, then `sparkrun logs <task-id>`, `sparkrun stop <task-id>`; **no `sparkrun stop all`**. `HOME="$H" sparkrun benchmark performance <recipe> -H <node> --profile decode-triage --output out.yaml` (`--solo --skip-run --no-stop --fresh --resume --timeout`; profiles in `benchmarking/`, list via `sparkrun registry list-benchmark-profiles`). `sparkrun tune sglang <recipe> -H <host>`, `sparkrun tune vllm <recipe> -H <host>`. `sparkrun arena login|status|benchmark`. `sparkrun registry list` shows this repo as `littlecedar` with `Trusted=yes` — recipe hooks (mods) auto-run unprompted at launch. Mod knobs are all `${VAR:-default}`: `MOD_TIMEOUT`, `MOD_CACHEDIR` (`/cache/runtime`), `MOD_LOGDIR` (`/cache/runtime/modlogs`; log `${LOGDIR}/${MOD_NAME}.log`, prior run gzipped), `MOD_MAX_JOBS`, `MOD_TENSOR_PARALLEL`, `MOD_MXFP8_FLOOR`, `MOD_LABQ_REPO`, `MOD_LABQ_REVISION`, `MOD_LABQ_OUT`, `MOD_LABQ_FORCE_REBUILD`, `MOD_DEMOTE_EXTRA_LEAVES`, `MOD_SKIP_VERIFY`. GPU work is remote SSH to `${WOPR_HEAD_NODE}` as `${WOPR_USERNAME}` (vars in git-ignored `.local/CONFIDENTIAL.md`); run `sparkrun` from `${WOPR_RUN_FROM_DIR}` with in-progress recipes symlinked from `${WOPR_SRC_DIR}`. There is no `/cache/models`, ever — HF cache is NFS at `${WOPR_USER_CACHE}/huggingface`, mounted into containers as `/cache`. Cluster mod delivery needs `--transfer-mode local`, else the node clones the registry itself and an unpushed mod is invisible. It is a `hidden=True` click option, so it never appears in `--help` — values `auto|local|push|delegated|pull`; set it persistently with `sparkrun cluster update <name> --transfer-mode local`. `.codex/hooks.json` pipes Bash output through `rtk hook codex`, so "green" output may be summarized.

## Conventions

- **A `defaults:` key no `{placeholder}` in `command:` consumes is not a setting** — sparkrun renders unmapped defaults silently, which shipped an unbootable recipe pair. After touching `defaults:`, read the rendered line from `sparkrun run -n` and grep for your flag.
- **Unmapped knobs reach the engine only via their placeholder.** `convert` and `limit_mm_per_prompt` are absent from sparkrun's `VLLM_FLAG_MAP`, so `-o limit_mm_per_prompt=…` warns "unmapped" *while still working* — never delete a placeholder to silence it.
- **`command:` uses folded `>` (17/18 recipes), and any JSON-shaped default must be folded with its shell quotes inside**: `limit_mm_per_prompt: >-\n  '{"image": 4, "video": 1}'`. A plain quoted scalar eats the quotes and the engine gets four arguments.
- **Recipe name is the filename minus `.yaml`; `name:` is forbidden.** Also banned: `cluster_only:` (use `min_nodes`/`max_nodes`), a literal model ID in `command:` (always `{model}` so paths get rewritten), host bind-mount paths in volumes (ship a mod). Grammar: `<model>-<size>-<quant>-<feature>-<runtime>[-<backend>].yaml`.
- **File by model family, not model name** — `qwen3.8-flash-next-*` lives in `recipes/qwen4/`; match the siblings. Contributor recipes carry the author's handle prefix (`eugr-`, `ursuciprian-`).
- **Unrecognized top-level recipe keys are silently absorbed into `runtime_config` and do nothing** unless a runtime asks for them by name (`VERIFIED`: `recipes/qwen4/qwen3.8-flash-next-nvfp4-labquant-sglang.yaml` carries a top-level `revision:` pin that `sparkrun recipe validate` reports as unknown, and nothing in sparkrun consumes it generically — the actual pin is the mod's `MOD_LABQ_REVISION` default, `LIKELY` unenforced elsewhere). Never assume a new top-level key works; check `validate` output for `unknown-top-level-key`.
- **The mod harness is copy-pasted, not shared.** All 17 `mods/*/run.sh` independently duplicate `MOD_*` metadata, `TIMEOUT`/`CACHEDIR`/`LOGDIR`, `stat -c '%u' /cache/runtime` uid inference, `reown()`, `log()`, `log_var()`, `log_cmd()`, log rotation, under `set -euo pipefail`. There is no library and sparkrun ships only the mod's own directory, so a `mods/common.sh` would break at launch; copy `mods/mod-template/run.sh`, keep its SPDX header (`AGPL-3.0-or-later`), add a `README.md`.
- **Mods run as root and must hand ownership back** — pass every path you create under `/cache/runtime` to `reown`, or downstream user processes fail on root-owned leftovers. `UV_LINK_MODE=copy` because uv symlinking breaks across that boundary.
- **The `mods:` list is an ordered dependency chain, not a set** (`ORDER MATTERS`, `keep the config mod first`, `Must run LAST` in `recipes/qwen4/qwen3.8-flash-next-nvfp4-labquant-sglang.yaml`). Reordering yields a checkpoint tree that boots, answers, and is numerically wrong.
- **Mods fail closed.** Unknown state → `die`, never a quiet default; contract counts are asserted (`EXPECTED_NARROW = 72`) and mismatches warn loudly; idempotence comes from reading existing output headers, not timestamps; writes go `tmp` + `os.replace`; symlinks are `unlink`ed first, since writing through one rewrites the shared HF snapshot on NFS.
- **`tools/` and `tests/` are stdlib-only, on purpose** — the tool must run on a head node, in a container, and on a laptop with no venv, and `tests/` parses YAML without PyYAML. Never add a dependency there. `tools/pooling-bench.py` is dash-named: import via `importlib.util.spec_from_file_location` and register in `sys.modules` **before** `exec_module`, or `@dataclass` fails.
- **Tests are guards over shipped artifacts, not unit tests** — they slice the `<<'TPL'` heredoc out of a mod, execute a mod to assert it *refuses* a bad config, and parse recipe text. **Every guard needs a proven negative control** (unquoted JSON → "word-splits into 4 shell words"; a real `--async-scheduling` in `command:` → fail), and an empty or missing result must raise rather than return `[]` or every downstream check passes vacuously.
- **Guards scan executable lines only, because recipe prose documents the forbidden string** — "``--async-scheduling`` is deliberately NOT set" broke the guard forbidding it (F20). Never "fix" a failing guard by rewording a recipe comment; any new text-scanning guard must strip whole-line comments first.
- **Comments carry evidence and the vocabulary is fixed:** `VERIFIED`/`LIKELY`/`SPECULATIVE`, upstream citations at `file.py:line` against a pinned commit, dates on hardware claims, measured numbers with provenance, negative results kept rather than deleted. Tidying these as noise, or writing a confident comment with no citation, violates the main convention.
- **Journal and work docs are git-ignored by design** (`**/*JOURNAL.md`, `**/*-WORK.md`, `**/*-WORK-ARCHIVE.md`, `.local/`) because this registry is git-distributed to nodes and third parties and those files hold internal IPs. **Never `git add -f` them**, keep hostnames/IPs out of anything tracked, and leave committed files' dangling section references alone.
- **This working tree is syncthing-shared with a live second writer.** `git add -A`, directory adds, and bare globs are prohibited — use explicit pathspecs and review `git diff --cached --stat` first. `tests/*.sync-conflict-*.py` (22 tests) is intentionally untracked, not importable by `discover`, and must not be deleted; the suite is 31 tests, not 22.

- The repo is synchronized to ${WOPR_HEAD_NODE} and backed up out-of-band. Do not worry about losing load-bearing documentation.
- Always offload safe parallel tasks onto subagents to keep the main agent free for managing subagents and long-horizong planning.
- Prefix shell commands with `rtk` [Rust Token Killer](https://github.com/rtk-ai/rtk) to dramatically reduce token bloat from shell command output!
## Commit & Pull Request Guidelines

Imperative mood, capitalized, no trailing period (`Add` 8x, `Update` 7x in the last 60). No Conventional Commits — zero `feat:`/`fix:`/`chore:` prefixes; a lowercase scope marks follow-ups (`demote mod:`, `qwen3-vl pooling:`). Subjects run 60-90 chars with backticks around identifiers; the log's 176-char subjects and throwaways (`checkpointing`, `cripes`) are outliers, not models. Bodies are multi-paragraph prose (~72 col wrap) in a fixed shape: what broke -> mechanism cited to `file.py:line` or a boot ID -> what changed -> what is and is not verified -> pointer to the evidence doc. No `Signed-off-by` or `Co-authored-by` trailers. Examples: `qwen3-vl pooling: block-size fix, pooling-bench tool, recipe guards`, `demote mod: index_qk_proj control was negative, so it defaults off`, `Add labquant MXFP8->BF16 demote mod; wire labquant recipes to the mod chain`.

PRs target `main` from `<contributor>/<kebab-topic>` branches on forks (merged as `Merge pull request #NN from spark-arena/glm-5.3`); upstream syncs land as `Merge branch 'spark-arena:main' into main`. **There is no PR template and no CI**, so the description carries the review context itself: symptom, mechanism cited to pinned upstream `file.py:line`, which knobs changed and why, the node/date a claim was `VERIFIED` on (or an explicit "unmeasured"), the exact validation run, and anything deliberately omitted. Link issues when a defect traces to an upstream engine bug and name the pinned container commit you read; state negative controls for any guard added. Do not invent a checklist or template convention this repo does not use.

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
- The username is `${WOPR_USERNAME}`
- You can stop a recipe with `sparkrun stop <task ID>`.
- You can get logs from `sparkrun logs <task ID>`.
- You can get <task ID> from `sparkrun status`.
- This repo is automatically synchronized to `${WOPR_HEAD_NODE}` in `${WOPR_SRC_DIR}`.
- To run recipes under development, symlink them from `${WOPR_SRC_DIR}` into `${WOPR_RUN_FROM_DIR}` and run `sparkrun` from `${WOPR_RUN_FROM_DIR}`.  The `mods` directory in `${WOPR_SRC_DIR}` is symlinked into `${WOPR_RUN_FROM_DIR}` so mods under development are reachable by `sparkrun`.

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
Refer to the info in **§2.3: Remote Build & Work**

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
