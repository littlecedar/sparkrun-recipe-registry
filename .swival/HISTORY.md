---

**2026-09-06 21:58:59** — */init pass 1*

# Project Scan — `sparkrun-recipe-registry`

**Platform note:** Linux (x86_64). All discovered tooling is Linux-native (GNU coreutils `stat -c`, `taskset -c` CPU pinning, `chown -R`), so nothing was filtered. No macOS/Windows split exists anywhere.

---

## A) WORKFLOW

**The key fact:** this repo is **not a build/test project** — it's a **content/data registry**. The "source files" are hand-written **YAML inference recipes**, **bash "mod" scripts**, and **benchmark profiles**. There is no compiler, no test suite, no linter, and no CI pipeline in the repo.

Evidence:
- `pyproject.toml` is a bare 5-line marker — `[project] name/version`, `requires-python = ">=3.12"`, empty `dependencies = []`. **No `[build-system]`, no `[project.scripts]`, no `[tool.*]` sections.**
- No `Makefile`, `justfile`, `Taskfile.yml`, `CMakeLists.txt`, `.github/workflows/`, `tox.ini`, `Cargo.toml`, `configure*`, `package.json`, or `mise.toml` exist.

So every build step is **N/A / not applicable**:

| Step | Command | Notes |
|---|---|---|
| Install dependencies | *N/A* | No deps. `.venv/` present is a 3.14 virtualenv by-product, not a project toolchain. |
| Build | *N/A* | There's nothing to compile. |
| Run all tests | *N/A* | No test suite. |
| Run a single test file | *N/A* | — |
| Run a single test case | *N/A* | — |
| Lint | *N/A* | No linter configured. |
| Format | *N/A* | No formatter. (Docs/recipes use black-ish YAML + 2-space indent; no formatter enforces it.) |
| Type-check | *N/A* | No type checker; YAML is schema-v2 by hand. |
| **Canonical "after-every-edit" command** | *N/A — manual verification only* | See below |
| Debug setup | See recipe `env` + `sparkrun run <recipe>` | Runtime debugging is on the DGX Spark, see below |

### What "validating a change" actually means here
Because there is no validation tool, the real "after-every-edit" pass is **manual review against the recipe schema** (`recipe_version: "2"`), then shipping. The canonical workflow after editing a recipe/mod is:

```bash
sparkrun list @official          # list/confirm the recipe is present & named right
sparkrun show @official/<recipe> # VRAM/config sanity check on the new file
sparkrun run <recipe>            # launch on the DGX Spark hardware
```

Validation = **eyeballing the YAML** (field order, that `{defaults}` interpolate, that `mods:` list resolves to a real script) + **smoke-testing on hardware**. A recipe "passes" when it launches and serves tokens.

### Runtime / "debug" environment variables (discoverable)
The only env/flag surface is what lives in each recipe's `env:` + `defaults:` blocks, plus the `sparkrun tune` command. Useful ones (Linux/DGX Spark only):

- **Mod/compile tuning:** `MAX_JOBS` (default 4), `FLASHINFER_NVCC_THREADS`, `OMP_NUM_THREADS: 1`, `CUTE_DSL_ARCH: sm_121a`, `SAFETENSORS_FAST_GPU: 1`.
- **vLLM knobs:** `VLLM_SLEEP_WHEN_IDLE`, `VLLM_MARLIN_USE_ATOMIC_ADD`, `VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS`, `VLLM_TARGET_DEVICE: cuda`.
- **Per-launch flags:** the `command:` block uses `taskset -c 5-9,15-19` CPU pinning, `--gpu-memory-utilization`, `--max-model-len` (262144), `--load-format instanttensor`, and `--speculative-config` JSON for MTP/DFlash.
- **Debug a mod:** mods log to `${MOD_LOGDIR:-/cache/runtime/modlogs}/${MOD_NAME}.log` (gzip-rotated). Read `/cache/runtime/modlogs/<MOD_NAME>.log` + the `logger -t <MOD_NAME>` journald stream.
- **Tuning command:** `sparkrun tune <sglang|vllm> <recipe> -H <host>`.

The `sparkrun` CLI lives at https://github.com/spark-arena/sparkrun and the recipe schema at https://sparkrun.dev/recipes/format/ — those are the source of truth for the format, not in-repo.

---

## B) CONVENTIONS

### 1. Recipe YAML schema (`recipe_version: "2"`), fixed field topology
Every recipe is a `sparkrun` recipe and follows a consistent field order. New recipes must mirror it:

```yaml
recipe_version: "2"      # quoted string "2" (not bare 2 — 2 of them quote it, 1 doesn't)
model: <org/Model>       # HuggingFace id, e.g. Qwen/Qwen3.6-27B-FP8
runtime: vllm|sglang     # runtime identifier
executor: docker         # present in some; omitted in others (inconsistent)
container: ghcr.io/spark-arena/dgx-vllm-eugr-nightly:latest
min_nodes: <int>         # DGX Spark node count; metadata key historically called cluster_only
metadata:                # description, maintainer, tags, model_url, dtype params
mods:                    # list of mod script names to run before serve
env:                     # key: value env vars exported to the container
defaults:                # interpolation placeholders consumed by command:
command: >                # the launch command (see §2)
```

### 2. Two competing `command:` block styles
This is the biggest **intra-file inconsistency** an agent should know about — both forms coexist:

- **Folded `>` style** (space-separated tokens, no backslashes) — used in the vLLM "Ornith"/"qwen3-coder" recipes:
  ```yaml
  command: >
    taskset -c 5-9,15-19 vllm serve {model}
    --host {host}
    --port {port}
  ```
- **Block `|` style** (explicit shell line continuations `\`) — used in the vLLM "qwen3.8"/"qwen3.6-dflash" recipes:
  ```yaml
  command: |
    vllm serve {model} \
      --host {host} \
      --port {port}
  ```
  The `|` recipes also use **short/long CLI arg mix** (`-tp`/`--tensor-parallel-size`, `-pp`) while the `>` recipes use only long form. **No hard rule either way** — match the sibling recipes for the same runtime.
- Placeholders are **YAML-brace interpolations** (`{host}`, `{max_model_len}`) that sparkrun fills from `defaults:`.

### 3. Mod scripts (`run.sh`) use a rigid boilerplate
Every mod script is byte-for-byte the same skeleton until the "Main mod scripting zone". A new mod **must** follow it:

```bash
#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

##### ######### ######### ######### ######### ######### #########   README
##### ######### ######### ######### ######### ######### #########   Metadata  -> MOD_NAME/DESCRIPTION/MAINTAINER
##### ######### ######### ######### ######### ######### #########   Config    -> ${VAR:-default} overridables
##### ######### ######### ######### ######### ######### #########   Helpers   -> reown(), log(), log_var(), log_cmd()
##### ######### ######### ######### ######### ######### #########   Log rotation + reown(LOGDIR)
##### ######### ######### ######### ######### ######### #########   Main (the actual work)
```

Conventions baked into the skeleton:
- **SPDX header** on every script: `SPDX-FileCopyrightText: 2026 Travis Wichert` + `SPDX-License-Identifier: AGPL-3.0-or-later`.
- **`set -euo pipefail`** immediately after the header.
- **Config vars are env-overridable** via `${MOD_VAR:-default}` (e.g. `TIMEOUT="${MOD_TIMEOUT:-180}"`, `LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"`, `MAX_JOBS="${MOD_MAX_JOBS:-4}"`).
- **`reown()` helper** chowns to the runtime owner's uid/gid because mods run as root:
  ```bash
  USER_UID="$(stat -c '%u' /cache/runtime)"   # GNU coreutils, Linux-only
  reown() { chown -R "${USER_UID}:${USER_GID}" "${@}"; }
  ```
- **`log()` / `log_var()` / `log_cmd()`** helpers write timestamped lines to `${LOGDIR}/${MOD_NAME}.log` AND to journald via `logger -t "${MOD_NAME}"`. `log_cmd` prefixes output with `=== <cmd> ===`.
- **`MOD_NAME`/`MOD_DESCRIPTION`/`MOD_MAINTAINER`** always set; `MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"` everywhere.

### 4. Mod references resolve via the registry
In `mods:` lists, entries are sometimes **bare names** (`- drop-caches`, `- pip-install-orjson`) and sometimes **paths** (`- mods/fix-qwen3-next-autoround`). Resolution comes from `.sparkrun/registry.yaml`, which maps registry → directories. Note the **asymmetry**: the `official` registry mounts its mods at top-level `mods:` while `experimental` mounts at `experimental-mods:` — so bare names resolve differently depending on which registry the recipe belongs to.

### 5. `.sparkrun/registry.yaml`
Single registry file mapping named registries to dirs. The `official` registry is `visible: true` (default); `experimental` sets `visible: false` (hidden from listings). Naming: `official-recipes/`, `experimental-recipes/`, `tuning/`, `benchmarking/`, `official-mods/`, `experimental-mods/`.

### 6. File naming
Recipe files: `lowercase-hyphen` and usually embed model + variant + runtime, e.g. `qwen3-coder-next-int4-autoround-vllm.yaml`, `qwen3.6-27b-fp8-dflash-vllm.yaml`. **Naming is still evolving** — recent commits rename to *simplify* (`qwen3-coder-next-int4-autoround-1m-vllm.yaml` → `qwen3-coder-next-int4-autoround-vllm.yaml`) and drop `-b12x` suffixes. Don't assume stable stems.

### 7. YAML comment conventions
Inline `# comments` are used to justify non-obvious values, e.g.
```yaml
load_format: fastsafetensors  # instanttensor may crash dflash drafter loading
kv_cache_dtype: auto          # flash_attn cannot do fp8 kv cache
```
Keys are quoted when they might collide with YAML types: `recipe_version: "2"`.

### 8. `metadata.tags` is a comma list (no spaces)
`tags: lcg_favorite, fast` / `tags: official, fast, lcg_favorite`. The flag legend (✨ 🌲 🚀 🐢 🚚 🏴 💀 🚩) lives in the per-group `README.md`, not in recipes.

### 9. Distrotribary
- `maintainer` field = `Little Cedar Group <sparkrun@littlecedar.net>`.
- LICENSE = **MIT**.
- DGX Spark hardware is pinned everywhere via `taskset -c 5-9,15-19`.

---

## C) COMMIT & PR STYLE

**Source:** `git log -20` — single-author, single-committer (Travis Wichert <travis@padthaitofuhot.com>), no merge commits, no tags/branches visible.

- **Tense:** present-tense **imperative** ("Adjust", "Update", "Set", "Remove", "Rename", "Reduce", "Switch", "Add", "Comment out").
- **Length:** terse, **one line each**.
- **Prefixes/scopes:** **no conventional-commit prefixes or `scope:` parens.** Scope is expressed in prose with the phrase **"in <recipe or file>"** and **backtick-quoting the affected identifier or config key**.
- **Quoting:** backticks wrap the config key or file being changed so the subject reads as the actual thing touched.

Real examples:
```
Adjust GPU memory utilization, comment out `kv_cache_dtype`, and update CLI arguments in Qwen3.8-27B and Ornith-1.5...
Update `cluster_only` to `min_nodes` in Qwen3-Coder-Next and Ornith-1.5 recipes for consistency.
Reduce `max_num_batched_tokens` to 8192 in qwen3-coder-next-int4-autoround-vllm.yaml for better configuration...
Set `VLLM_SLEEP_WHEN_IDLE` to 0 in littlecedar-ornith-1.5-35b-a3b-nvfp4-vllm.yaml
Rename and simplify `qwen3-coder-next-int4-autoround-1m-vllm.yaml` to `qwen3-coder-next-int4-autoround-vllm.yaml`
Remove `VLLM_ALLOW_LONG_MAX_MODEL_LEN` from configuration files in littlecedar ornith-1.5 recipes.
Comment out `kv_cache_dtype`, `attention_backend`, and `linear_backend`, update environmental variables, and ...
```

**PR template:** none present. No `.github/` directory at all, so **no PR template, no code-review checklist, no contribution guidelines in-repo.** Contributions are by direct push.

### Match-conventions checklist for an agent
- One-line imperative subject; if it needs detail, append `in <file/recipe>` and wrap touched keys in backticks.
- Keep it a single line; the log has never used a body.
- When editing a recipe, keep `recipe_version` quoted and mirror the sibling runtime's `command:` block style and CLI arg length.
- When adding a mod, start from `experimental-recipes/littlecedar/mods/mod-template/run.sh` and preserve the SPDX header, `set -euo pipefail`, `MOD_*` metadata, `${VAR:-default}` config, and the `reown`/`log` helpers.
- Prefer adding a sibling/renaming to *simplify* (drop redundant suffixes) rather than introduce new ones.

---

### One-line summary
This is a **schema-v2 YAML recipe + bash-mod registry**, not a code project: there is **no build/test/lint/type-check tooling** (all those commands are N/A); the only runnable surface is the **Linux/DGX Spark `sparkrun` CLI** and the mods; validate by **re-reading the recipe against `recipe_version: "2"`** and smoke-testing on hardware; commit with **one-line imperative subjects** that name the touched key/file in backticks, in **no scope prefix**; there is **no PR template**.

---

**2026-09-06 22:00:16** — */init pass 2*

Confirmed via `git ls-files` (100 tracked files): no `Makefile`, `justfile`, `Taskfile.yml`, `.github/`, `setup.cfg`, `.flake8`, `ruff.toml`, `pre-commit-config.yaml`, `tox.ini`, `Dockerfile`, `Dockerfile`, or `*.yml` CI anywhere. The only non-recipe files are `pyproject.toml` (bare marker), `LICENSE`, READMEs, `.sparkrun/registry.yaml`, and the bash `run.sh` mods. So my core conclusions hold — but let me tighten, and importantly, stop dismissing workflow commands when the real command surface **does** exist.

---

## A) WORKFLOW — the real, copy-pasteable command surface

**Truth first:** there is **no local build / test / lint / format / type-check target** in this repo. It's a *content registry*, not software — so a Makefile/`npm run validate`/pytest suite simply does not exist. (Signal: a `.ruff_cache/` sits on disk, meaning ruff has been run at some point, but there is **no** `ruff.toml`/`.flake8`/`[tool.ruff]`/pre-commit config, so there is no lint command to invoke.) Those five columns are genuinely not runnable — but everything else is actionable.

### Install dependencies
```bash
# nothing to install for the repo itself.
# The only tool is the sparkrun CLI (from https://github.com/spark-arena/sparkrun),
# which ships/uses the .venv at the repo root:
.venv/bin/python --version   # 3.14 venv already present
```
Recipe "dependencies" (models, tuning configs) are pulled at runtime by `sparkrun`, not by pip.

### Build
`N/A` — nothing in the repo compiles. (A mod's `run.sh` can *trigger* kernel compilation on target hardware — e.g. `cap-flashinfer-ninja-parallelism` patches a flashinfer `build_backend.py` — but that runs on the DGX Spark, not locally.)

### Run all tests / single file / single case
`N/A` — no test framework, no test files, no runner.

### Lint / Format
`N/A` — no lint/formatter wired up (see the `.ruff_cache` note above). There is no `format` command to call.

### The canonical after-every-edit command
There is no tooling, so validation is the **manual schema-check + launch** sequence. This is the true after-edit loop:

```bash
# 1) Confirm the recipe is registered and named right
sparkrun list @official
sparkrun run @official/our-awesome-recipe          # also: bare name works

# 2) Inspect the edited recipe's resolved config / VRAM before launch
sparkrun show @official/our-awesome-recipe

# 3) Launch it on the DGX Spark — this is the real "does it work?" test
sparkrun run our-awesome-recipe
```
A recipe "passes" when `sparkrun show` renders it correctly and `sparkrun run` serves tokens. There is no faster in-repo check.

### Debug setup (discoverable, actionable)
- **Launch / inspect:** `sparkrun run <recipe>`, `sparkrun show @official/<recipe>`.
- **Kernel/config tuning:**
  ```bash
  sparkrun tune vllm <recipe> -H <host>
  sparkrun tune sglang <recipe> -H <host>
  ```
- **Read a mod's output:** logs rotate to `${MOD_LOGDIR:-/cache/runtime/modlogs}/${MOD_NAME}.log` and are also journaled:
  ```bash
  journalctl -t <MOD_NAME>            # e.g. journalctl -t pip-install-orjson
  cat /cache/runtime/modlogs/<MOD_NAME>.log
  ```
- **Env knobs** (from recipe `env:`/`defaults:`) — the on-hardware debug levers:
  - Compile/perf: `MAX_JOBS` (default 4), `FLASHINFER_NVCC_THREADS`, `OMP_NUM_THREADS: 1`, `CUTE_DSL_ARCH: sm_121a`, `SAFETENSORS_FAST_GPU: 1`.
  - vLLM: `VLLM_SLEEP_WHEN_IDLE`, `VLLM_MARLIN_USE_ATOMIC_ADD`, `VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS`, `VLLM_TARGET_DEVICE: cuda`.
  - Every vLLM recipe pins CPUs with the prefix `taskset -c 5-9,15-19` before the `vllm serve`/`sglang serve` command.

---

## B) CONVENTIONS — only cross-cutting, non-obvious, surprising ones

*(Cut: single-file details, generic YAML/comment habits, "naming is evolving" one-offs, the tag-legend table, and fixed values like the maintainer string.)*

### 1. Mod references are ambiguous to write, and resolve differently per registry
In `mods:` lists you'll see **both** bare names and paths, and the resolution differs by registry — an agent cannot know a priori which to use:

```yaml
# in experimental-recipes/littlecedar/...   (bare name → resolves under experimental-mods/)
mods:
  - drop-caches
  - pip-install-fastsafetensors

# in experimental-recipes/littlecedar/...    (path → mods/<name>)
mods:
  - mods/drop-caches
  - mods/instanttensor-hybrid-draft-loader
```

Resolution is driven by `.sparkrun/registry.yaml` (registry `official` mounts `mods`/`official-mods`; registry `experimental` mounts `experimental-mods` and is `visible: false`). Because the same bare name can mean different physical paths depending on which registry the recipe belongs to, **verify a mod reference actually resolves before shipping** — do not assume `drops-caches` and `mods/drop-caches` are interchangeable.

### 2. New `run.sh` mods must use the fixed boilerplate template
Every mod script shares one skeleton (see `experimental-recipes/littlecedar/mods/mod-template/run.sh`). A new mod must mirror it exactly, or it won't fit the runtime:

```bash
#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail
```
then, in order, fixed sections: `README` comment → `Metadata` (`MOD_NAME`/`MOD_DESCRIPTION`/`MOD_MAINTAINER`) → `Config` (`${VAR:-default}` env-overridables) → `Helpers` → log-rotation + `reown(LOGDIR)` → `Main` (the actual work).

Three helpers are non-obvious and every script uses them:
- **`reown()`** chowns to the runtime owner because **mods run as root** and can't see the real uid:gid — it infers it from `/cache/runtime`:
  ```bash
  USER_UID="$(stat -c '%u' /cache/runtime)"   # GNU coreutils, Linux-only
  reown() { chown -R "${USER_UID}:${USER_GID}" "${@}"; }
  ```
- **`log()` / `log_var()` / `log_cmd()`** write timestamped lines to `${LOGDIR}/${MOD_NAME}.log` **and** to journald via `logger -t "${MOD_NAME}"`. `log_cmd` wraps output in `=== <cmd> ===`.
- Config values are **env-overridable** by convention: `TIMEOUT="${MOD_TIMEOUT:-180}"`, `LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"`, `MAX_JOBS="${MOD_MAX_JOBS:-4}"`.

### 3. Recipes follow the `sparkrun` v2 schema with brace-interpolated commands
A valid recipe uses this field topology, and `command:` pulls values from `defaults:` via **YAML-brace interpolation** `{host}`, `{max_model_len}` — which an agent would not know without reading a recipe:

```yaml
recipe_version: "2"
model: <HF repo id>            # e.g. Qwen/Qwen3.6-27B-FP8
runtime: vllm | sglang
container: ghcr.io/spark-arena/dgx-vllm-eugr-nightly:latest
min_nodes: <int>               # historically named cluster_only, now min_nodes
metadata: { description, maintainer, tags, model_url }
mods: [<mod refs>]
env: { KEY: value }
defaults: { host: 0.0.0.0, port: 8000, ... }   # interpolation sources
command: taskset -c 5-9,15-19 vllm serve {model} --host {host} ...
```
`recipe_version` is **always quoted** (`"2"`) because `2` is otherwise an integer — keep it quoted to match the schema.

### 4. Two competing `command:` block styles (an inconsistency to detect and pick consistently within a group)
Both are present and an agent must pick one and stay consistent per runtime:
- **Folded `>`** — space-separated tokens, no backslashes (vLLM Ornith/coder recipes).
- **Block `|`** — explicit `\` continuations with tabs/indentation (qwen3.8/qwen3.6-dflash).
The `|` recipes also **mix short/long vLLM flags** (`-tp` and `--tensor-parallel-size`); the `>` recipes use only long form. Match the sibling recipes of the same runtime.

---

## C) COMMIT & PR STYLE — unchanged, fully actionable

`git log -20` → single author (Travis Wichert), no merges, no tags.
- **Tense:** present-tense **imperative**.
- **Length:** one line.
- **Prefixes/scope:** none. Scope is expressed in prose via `in <file/recipe>` with the touched key/file **wrapped in backticks**.

Examples:
```
Reduce `max_num_batched_tokens` to 8192 in qwen3-coder-next-int4-autoround-vllm.yaml for better configuration...
Set `VLLM_SLEEP_WHEN_IDLE` to 0 in littlecedar-ornith-1.5-35b-a3b-nvfp4-vllm.yaml
Rename and simplify `qwen3-coder-next-int4-autoround-1m-vllm.yaml` to `qwen3-coder-next-int4-autoround-vllm.yaml`
Comment out `kv_cache_dtype`, `attention_backend`, and `linear_backend`, update environmental variables, and ...
```
**PR template:** none — there is no `.github/` directory at all, so there is no template, checklist, or review process in-repo. Contributions are by direct push.

**Match checklist:** one-line imperative subject naming the touched key/file in backticks after `in <file/recipe>`; no scope prefix; when adding a recipe, use the `recipe_version: "2"` topology above; when adding a mod, copy `mods/mod-template/run.sh` verbatim and only edit the `Main` zone.

---

**2026-09-06 22:00:33** — */init pass 3*

`AGENTS.md` written — 2675 characters (well under the 3000 limit), **`## Workflow` is the first section**, and all required fields are present:

- **Workflow** — every field present; the `N/A` columns keep their required lines (test all/file/case, lint, format, typecheck) with exact `N/A` rather than being dropped; the actionable ones (`install`, `after every edit`, `debug`) carry exact copy-pasteable commands.
- **Conventions** — 7 terse, cross-cutting bullets (v2 schema topology, brace interpolation + mod-ref resolution, `>` vs `|` command blocks, mod-template boilerplate, root+`reown`, env-overridable config/logs, bare vs path mod refs). Single- and multi-sentence, 2 sentences max each.
- **Commit & PR** — one paragraph (imperative, one-line, backtick-quoting, `in <file>` scope with 3 real example subjects) plus one paragraph documenting the **absence** of a PR template.

Workflow was prioritized and the commit/PR section was kept brief to fit — well within budget.

---

**2026-09-06 22:10:07** — */goal based on the stylings of the other `sparkrun` recipes in the littlecedar directory, build a specification checklist for an AI agent to create a new `sparkrun` recipe for running the highest qual...*

Goal completed.

---

**2026-09-06 22:22:13** — */learn*

I reviewed the session. The only action taken so far was a single `list_files` call (pattern `**/MEMORY.md`) that returned no matches. I did not encounter any mistakes, confusions, or surprises with tools, commands, APIs, or syntax — and there were no durable lessons learned.

There is nothing worth persisting to `.swival/memory/MEMORY.md`. I'm intentionally not creating an empty memory file.

---

**2026-09-06 22:26:59** — */goal review qwen3.8-flash-next-nvfp4-specification.md for consistency*

Goal completed.

---

**2026-09-06 22:30:59** — */goal update the spec with your findings.*

Goal completed.

---

**2026-09-07 00:27:40** — */goal update experimental-recipes/littlecedar/README.md to include all model recipes in the littlecedar directory.  Be sure to get the metadata: tags: from each recipe and update the flags using the t...*

Goal completed.

