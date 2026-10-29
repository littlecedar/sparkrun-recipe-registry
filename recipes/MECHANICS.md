# Mechanics

Recipe-schema reference for the `littlecedar` registry, written against **sparkrun
0.4.2-alpha+g36d8a44**; the installed build is **0.4.3** (upgraded 2026-10-29), at
`/home/siv/.local/share/uv/tools/sparkrun/lib/python3.14/site-packages/sparkrun/`.
Every `file.py:line` cite is relative to that package tree, whose line numbers can move
between builds; re-derive a line before trusting it after an upgrade, and let
`sparkrun --version` name the build you have.

**Cite provenance.** The cites re-derived against 0.4.2 on 2026-10-21 are: every cite in
§[The one rule](#the-one-rule-that-decides-whether-a-knob-works), and in §Key reference
under *`sparkrun_version`*, *`recipe_version`*, *`description`*, *`metadata`*,
*`maintainer`* and *`model_revision`*, plus §[Notes](#notes). Every other cite still
carries 0.4.0 numbering — re-derive it with `grep -n` on the named symbol before trusting
it. The module paths themselves (`core/launcher.py`, `core/recipe.py`,
`core/validation.py`, `models/runtime.py`) are the same in both builds.

The format is v2 and the authoritative key set is `_KNOWN_KEYS`
(`core/recipe.py:80-122`): **41 keys**, counted from the literal set. A key outside
it is either plugin-owned or swept into `runtime_config`.

## Contents

- [The one rule that decides whether a knob works](#the-one-rule-that-decides-whether-a-knob-works)
- [Key reference (41)](#key-reference-41)
  - [Format and identity](#format-and-identity)
  - [Model and serving](#model-and-serving)
  - [Runtimes and what each consumes](#runtimes-and-what-each-consumes)
  - [Topology](#topology)
  - [Container and lifecycle](#container-and-lifecycle)
  - [Build, execution, placement](#build-execution-placement)
  - [Plugin-owned keys](#plugin-owned-keys)
- [Notes](#notes)
  - [0.4.0 binds {model} to the prepared path](#040-binds-model-to-the-prepared-path)
  - [The served model id](#the-served-model-id)
  - [Placeholders and JSON](#placeholders-and-json)
  - [What recipe validate can see](#what-recipe-validate-can-see)
  - [Pooling (embedding / reranker) recipes](#pooling-embedding--reranker-recipes)
  - [CLI mechanics](#cli-mechanics)
  - [Env, portability, and distribution](#env-portability-and-distribution)
  - [Engine flag semantics — SGLang/vLLM](#engine-flag-semantics--sglangvllm)
  - [Checkpoint and model-path mechanics](#checkpoint-and-model-path-mechanics)
- [Per-family agent guides](#per-family-agent-guides)

## The one rule that decides whether a knob works

`Recipe.build_config_chain` layers CLI overrides → user config → recipe `defaults`
(`core/recipe.py:1532-1538`). Declaring a default is not wiring it. A `defaults:` value
reaches the engine through exactly one of:

1. a `{placeholder}` of the same name in `command:`, in another default's value, or in
   an `env:` value (`core/launcher.py:798-818`);
2. the runtime's flag map, exposed as `known_config_keys()` (`runtimes/base.py:867-892`;
   per-runtime extras in the runtime table below);
3. a shared consumed key in `BASE_CONSUMED_CONFIG_KEYS` (`runtimes/base.py:41-86`) —
   parallelism dims, `max_model_len`, `gpu_memory_utilization`, `kv_cache_dtype`,
   `served_model_name`, `api_key`, `port`, `host`, executor and builder selectors, and the
   benchmark keys;
4. an internal `_`-prefixed or dotted key (`core/launcher.py:776-789`), or a key read only
   by an `overrides[].when.config` predicate (`core/launcher.py:994-998`).

Everything else is dropped silently. The only reporter is `report_unmapped_config_keys`,
a **warning** named `unmapped-config-key` (`core/launcher.py:1011-1029`, wired into
`recipe validate` at `core/validation.py:1842-1853`). It returns nothing when a runtime
declares `known_config_keys() is None` (`core/launcher.py:991-992`); `eugr-vllm` does
exactly that (`runtimes/eugr_vllm_ray.py:54-63`), so nothing warns there.

A top-level typo is the other half: an unknown top-level key is swept into
`runtime_config` (`core/recipe.py:1393-1400`), where only a by-name consumer reads it.
`check_unknown_top_level_keys` warns `misplaced-config-key` when the runtime would have
understood the key under `defaults:`, and suggests `unknown-top-level-key` otherwise
(`core/validation.py:1196-1275`). When a key is deliberately read by name, declare it
under `runtime_config:` so it reads as intentional.

## Key reference (41)

### Format and identity

- **`sparkrun_version`** — legacy v1 key, unread by `Recipe.__init__`. Only
  `resolve_builder` consults it as a fallback for version detection
  (`core/recipe.py:897`), and canonical export drops it (`core/recipe.py:2520-2530`).
  Omit it in v2.
- **`recipe_version`** — string, default `"2"` (`core/recipe.py:1297`). `"1"` runs the
  legacy migration: runtime inferred from the command, `builder: eugr` when the command or
  `mods:` imply it (`core/recipe.py:573-580`), plus a `deprecated-recipe-format` warning
  (`core/validation.py:1442-1460`). Omit it in v2 — the default is already `"2"`.
- **`min_sparkrun_version`** — optional version string, default unset. Parsed with
  `packaging.version.Version`; a range is rejected (`core/version.py:24-34`).
  `validate_structure` fails when the installed core is older
  (`core/version.py:38-60`; called from `core/recipe.py:1608-1611`).
- **`name`** — ignored. The name is the source filename stem (`core/recipe.py:1303-1306`);
  a declared `name:` in a v2 recipe draws `deprecated-recipe-name`, because the value is
  discarded rather than honored (`core/validation.py:1512-1525`). Rename the file to rename
  the recipe.
- **`description`** — string, default `""`, read from the top level (`core/recipe.py:1307`).
  When absent it falls back to `metadata.description` (`core/recipe.py:1385-1389`), and
  export folds it back into `metadata.description` (`core/recipe.py:2574-2576`).
  `recipe list` and `recipe search` read the top-level key **and** fall back to
  `metadata.description` (`core/recipe.py:2933-2936`), so both spellings list.
- **`metadata`** — mapping, default `{}`. Feeds VRAM estimation and display, never the
  serve command (`core/recipe.py:1362-1363`, `1638-1713`). Recognized labels include
  `model_params`, `model_dtype`, `kv_dtype`, `quantization`, `quant_bits`, `model_type`,
  `layer_types`, `description`, `maintainer`, and `spark_arena_benchmarks`. A malformed
  value is a **suggestion** (`recipe-metadata`), never a launch blocker
  (`core/validation.py:1784-1788`). Metadata is excluded from the workload fingerprint
  (`orchestration/job_metadata.py:340-350`).
- **`maintainer`** — no top-level form. The constructor reads `metadata.maintainer`
  only (`core/recipe.py:1392`) and export writes it back there
  (`core/recipe.py:2577-2578`); a top-level `maintainer:` is not in `_KNOWN_KEYS` and is
  swept into `runtime_config`.
- **`include`** — one base recipe: a sibling filename or `@registry/name`. The base is
  loaded recursively (depth cap 8), then merged: mappings merge key by key, scalars and
  lists replace, an explicit `null` deletes, values inside `defaults:` and `env:` are
  atomic, and `overrides:` appends with the includer last (`core/recipe_include.py:1-33`,
  `102-128`). A `Recipe` built straight from a dict rejects it; load through
  `Recipe.load()` (`core/recipe.py:1146-1150`, `1783-1786`).
- **`overrides`** — list of `{when, defaults|env|container}` layers, default `[]`. Keys in
  one `when` AND; matching layers apply in list order, later wins; precedence is runtime <
  platform < `defaults` < matched overrides < CLI `-o` (`core/recipe_overrides.py:1-52`).
  An unknown selector or operator makes the entry **not match**, with a warning; layer
  keys outside `defaults`/`env`/`container` are structural errors; `port`,
  `served_model_name`, and parallelism keys may not be set by a layer
  (`core/recipe_overrides.py:69-143`). Selector-only `when.config` keys count as consumed
  (`core/launcher.py:866-870`).

### Model and serving

- **`model`** — string, default `""`; required after resolution
  (`core/recipe.py:1626-1627`). A Hugging Face repo id, a GGUF `repo:quant` spec, or an
  absolute host path. An absolute path means pre-placed weights: no download or
  distribution, identity-mounted into the container (`core/recipe.py:1080-1098`).
- **`model_revision`** — string, default unset. Pins the served repo for distribution and
  is stamped onto the auto-generated distribution entry (`core/recipe.py:333-350`). It
  enters the template chain only when set (`core/recipe.py:1534-1535`). A pin that never
  reaches the engine as a revision flag warns `unpinned-model-revision`
  (`core/validation.py:866-935`) — eleven shipped arms carry that warning deliberately.
  A typo'd top-level `revision:` is a dead pin: it is not in `_KNOWN_KEYS`, so it is swept
  into `runtime_config` and never reaches the engine — the spelling is top-level
  `model_revision:`.
- **`runtime`** — string, default `""`; required after resolution
  (`core/recipe.py:1628-1629`). Omitted, it is inferred from the command prefix:
  `vllm serve` → `vllm`, `sglang serve` or `python -m sglang.launch_server` → `sglang`,
  `llama-server` → `llama-cpp`, `trtllm-serve` or `mpirun … trtllm` → `trtllm`
  (`core/recipe.py:52-55`, `509-534`). Bare `vllm` then resolves to `vllm-distributed`,
  or to `vllm-ray` when `defaults.distributed_executor_backend` is `ray` or the command
  contains `--distributed-executor-backend ray`; a CLI `-o` wins
  (`core/recipe.py:39`, `644-662`).
- **`runtime_version`** — string, default `""` (`core/recipe.py:1177`). Parsed, exported,
  and hashed into the workload fingerprint (`orchestration/job_metadata.py:378-382`);
  nothing in the installed 0.4.0 runtime tree reads it to change a command.
- **`command`** — folded string, default unset; any non-string is a load error
  (`core/recipe.py:676-678`). It is a template rendered against the config chain
  (`core/recipe.py:1540-1588`); see §Notes for the placeholder and vLLM/sglang traps.
- **`defaults`** — mapping, default `{}`; a non-mapping is a load error
  (`core/recipe.py:679-682`). The recipe tier of the config chain
  (`core/recipe.py:1532-1538`); read §The one rule before adding a key.
- **`runtime_config`** — mapping, default `{}`; a non-mapping is a load error
  (`core/recipe.py:679-682`). The v1 escape hatch and the sweep target for unknown
  top-level keys (`core/recipe.py:1264-1270`), read only by name — `build_args`, `mods`,
  `dashboard`, and `mmproj` are the consumers the checker names
  (`core/validation.py:1176-1194`). Export flattens it back to the top level
  (`core/recipe.py:2472-2474`).
- **`env`** — mapping of string to string, default `{}` (`core/recipe.py:1217`). Only
  reserved `{config.NAME}` and `{launch.NAME}` tokens are expanded, with no shell
  evaluation or host lookup (`core/env_templates.py:1-20`, `20-68`); `launch.NAME` must be
  one of the documented fields (`core/env_templates.py:20`). A top-level `env_templates:`
  key is rejected at load (`core/recipe.py:1218-1219`).
- **`capabilities`**, **`unsupported_capabilities`** — lists of strings, default `[]`.
  Gateway declarations of what the served model can do; sparkrun never infers them, and an
  undeclared capability is left to gateway policy (`core/recipe.py:1272-1284`). They are
  deliberately real attributes rather than swept keys so they stay **out of the workload
  fingerprint** (`core/recipe.py:1275-1279`; the hashed attribute list is
  `orchestration/job_metadata.py:371-382`).

### Runtimes and what each consumes

Every runtime also honors `BASE_CONSUMED_CONFIG_KEYS` (`runtimes/base.py:45-85`). The rows below add
the runtime's own `known_config_keys()`: flag-map keys plus the keys it reads outside the map.

| `runtime:` | Source | Additional consumed keys |
|---|---|---|
| `sglang` | `runtimes/sglang.py:153` | `_SGLANG_FLAG_MAP` plus `speculative_draft_model`, `speculative_draft_model_path`, `speculative_draft_model_revision` (`:281-292`) |
| `vllm-distributed` | `runtimes/vllm_distributed.py:32` | `VLLM_FLAG_MAP` plus `data_parallel_rpc_port` (`runtimes/_vllm_common.py:87-98`) |
| `vllm-ray` | `runtimes/vllm_ray.py:30` | the same vLLM map (`runtimes/_vllm_common.py:87-98`) |
| `trtllm` | `runtimes/trtllm.py:79` | flag map plus `backend`, `cuda_graph_max_batch_size`, `cuda_graph_padding`, `free_gpu_memory_fraction`, `kv_cache_enable_block_reuse`, `moe_backend`, `print_iter_log` (`:86-98`) |
| `atlas` | `runtimes/atlas.py:275` | `_ATLAS_FLAG_MAP` plus `_ATLAS_SPARKRUN_OWNED_KEYS` (`:250-262`, `:386-393`) |
| `modular-max` | `runtimes/modular_max.py:70` | `_MAX_FLAG_MAP` plus `devices` (`:73-79`) |
| `tokenary` | `runtimes/tokenary.py:72` | `_TOKENARY_FLAG_MAP` plus `command_binary` (`:78-84`) |
| `llama-cpp` | `runtimes/llama_cpp.py:100` | flag map + bool flags + `flash_attn`, `webui`, `mmap`, plus `mmproj` (`:103-114`) |
| `eugr-vllm` | `runtimes/eugr_vllm_ray.py:42` | none declared: it extends `vllm-ray` but returns `None` from `known_config_keys()`, which silences the unmapped-key report (`:55-63`). Deprecated; prefer `runtime: vllm-ray` with `builder: eugr`. |

### Topology

- **`min_nodes`** — integer, default `1`; must be ≥ 1 (`core/recipe.py:1184`,
  `1632-1633`).
- **`max_nodes`** — integer or null, default unset; must be ≥ `min_nodes`
  (`core/recipe.py:1634-1635`). `mode: solo` forces both to 1, and
  `max_nodes: 1` derives `mode: solo` (`core/recipe.py:1183-1190`).
- **`mode`** — string, default `"auto"`, derived from the node range (`core/recipe.py:1183-1190`).
  Deprecated to write: `mode: solo` migrates to `max_nodes: 1`, `mode: cluster` to
  `min_nodes: 2`, and `mode: auto` to nothing; declaring it draws `deprecated-topology`
  (`core/validation.py:1371-1385`, `1540-1572`).
- **`solo_only`** — deprecated boolean. Truthy sets `max_nodes: 1` and `mode: solo`;
  falsy constrains nothing (`core/recipe.py:1194-1196`; migration text at
  `core/validation.py:1371-1385`). Use `max_nodes: 1`.
- **`cluster_only`** — deprecated boolean. Truthy sets `min_nodes: max(min_nodes, 2)` and
  `mode: cluster`; falsy constrains nothing (`core/recipe.py:1191-1193`). Use
  `min_nodes: 2`: the boolean still only makes `run` print a one-host warning, whereas
  `min_nodes` is enforced by validation and placement (`core/validation.py:1558-1560`).

### Container and lifecycle

- **`container`** — string, default `""`. The fallback image for every host without a
  `containers:` entry; digest-pin it when the lane depends on exact upstream code.
- **`containers`** — list of `{host, image}`, default `[]`; `container` stays the
  fallback. Parsed permissively — entries missing either field are dropped with a warning —
  and validated against the cluster's host list only at launch
  (`core/images.py:54-72`, `26-32`; `core/recipe.py:1197-1206`).
- **`pre_exec`** — list of strings or `{copy: …, exec: …}` mappings, default `[]`; a
  scalar is coerced to one entry (`core/recipe.py:1286-1288`; `utils/text.py:101`).
  Runs before the serve command; `mods:` are resolved into this list.
- **`mods`** — list of mod references, default `[]` (`core/recipe.py:1298-1300`). A mod is
  a directory with `run.sh`; resolution order is scoped `@registry/<rel>`, adjacent to the
  recipe file (`<rel>` then `mods/<rel>`), the recipe's own registry, then the `eugr`
  fallback. Each mod becomes pre_exec entries: a `copy` and a `./run.sh` exec
  (`core/mods.py:1-33`).
- **`post_exec`** — list of strings, default `[]`. Runs **inside the head container** after
  readiness (`core/launcher.py:2653-2667`).
- **`post_commands`** — list of strings, default `[]`. Runs **on the control machine**
  after readiness (`core/launcher.py:2669-2672`).
- **`stop_after_post`** — boolean, default `false`. Stops the workload after post hooks
  and exits 0 (`core/launcher.py:2681-2690`; `core/recipe.py:1291`).
- **`readiness`** — mapping, default `{}`. Keys: `port_timeout_s` (1800 s),
  `health_timeout_s` (900 s), `inference` (true), `inference_style` (`auto`),
  `inference_timeout_s` (1200 s), and `inference_prompt`
  (`core/readiness.py:14-15`, `49-56`). Any other key is an error
  (`core/readiness.py:101-143`), raised at load (`core/recipe.py:1210-1213`).

### Build, execution, placement

- **`builder`** — string, default `""`. Explicit value wins; otherwise v1 and eugr
  signals infer `eugr` from `runtime_config.build_args` or a `container:` starting with
  `ghcr.io/spark-arena/dgx-vllm-eugr-nightly` (`core/recipe.py:76`, `617-642`, `732-763`).
  `mods:` is **not** a builder signal. A named builder that does not resolve is an error
  (`core/validation.py:1670-1697`); a silent inference is only a suggestion
  (`core/validation.py:1600-1668`).
- **`builder_config`** — mapping, default `{}`, consumed by the builder by name
  (`core/recipe.py:1304`).
- **`executor`** — string, default `""`: `""` selects the Docker executor, `"local"` the
  native-subprocess executor with no container (`core/recipe.py:1310-1313`). An
  unresolvable selector is an error (`core/validation.py:1705-1734`).
- **`executor_config`** — mapping, default `{}` of container-engine settings such as
  `auto_remove` and `restart_policy` (`core/recipe.py:1306-1308`).
- **`scheduler`** — string, default `""`; `""` selects greedy placement, and
  `occupancy-sparse` or `occupancy-dense` opt into occupancy placement with fractional GPU
  sharing (`core/recipe.py:1315-1319`). `--scheduler` overrides it.
- **`layout`** — mapping or null, default unset: `requires: [{capability}]` and
  `placements: [{host, ranks, local_gpus}]`. Parsed permissively at load and validated by
  the placement engine at apply time (`core/layout.py:22-40`, `86-140`;
  `core/recipe.py:1324-1328`).
- **`distribution_config`** — mapping or null. Default is one model entry `{model}` (with
  `model_revision` stamped on) and one container entry `{container}`. An omitted `models:`
  or `containers:` subkey keeps that default; a present subkey is honored literally,
  including `entries: []` and `enabled: false`. A model entry's `revision` is
  authoritative and never falls back to the recipe pin (`core/recipe.py:124-160`,
  `181-202`, `307-398`). Only a hand-written block is exported
  (`core/recipe.py:2480-2484`). A cluster profile's `distribution:` block **overrides** the
  recipe, so a stale `{enabled: false, skip_fan_out: true}` on a cluster silently strands
  every worker with a bare `missing …/config.json`; omit the block and rely on the default
  (`models.enabled: true`, `containers.enabled: true`) — there is no CLI flag for
  `distribution`, hand-edit `~/.config/sparkrun/clusters/<name>.yaml`. The HF cache is
  per-node: the checkpoint must be distributed to every runner node. — src:
  `.swival/memory/sparkrun-notes.md:476-496,417-428`.
- **`cluster_config`** — mapping or null; internal, undocumented per-recipe launch
  overrides: `remote_cache_dir`, `local_cache_dir`, `resolved_model_path`. Applied only for
  trusted recipes, because it can expose host paths to the container
  (`core/recipe.py:1023-1078`, `1331`).
- **`runtime_cache`** — boolean or mapping, default `{}`. `true` becomes `{enabled: true}`.
  Fields: `enabled`, `key_by_image`, `key_by_model`, `dir`, and `prune` (`enabled`,
  `max_age_days`). The recipe layer outranks CLI, cluster, and global config
  (`core/recipe.py:1333-1338`; `core/runtime_cache.py:199-300`).
- **`benchmark`** — embedded benchmark spec mapping, read from raw recipe data by
  `BenchmarkSpec.from_recipe`, never by the constructor
  (`core/benchmark_profiles.py:262-293`). Recognized keys: `framework` (required),
  `args`, `metadata`, `timeout`, `schedule`, `category`; extra keys are swept into `args`
  (`core/benchmark_profiles.py:13`, `266-276`).

### Plugin-owned keys

A plugin can claim a top-level key through `register_recipe_item`
(`core/recipe_items.py:69-139`). The key must not collide with `_KNOWN_KEYS`, uses
lowercase letters, digits, `_`, and `-`, and the handler owns `parse`, `validate`, and
`export`. Parsing happens before the unknown-key sweep, so a claimed key never lands in
`runtime_config` (`core/recipe.py:1231-1249`). `affects_fingerprint` decides whether the
item joins the workload identity (`core/recipe_items.py:85-113`;
`orchestration/job_metadata.py:352-355`). The installed 0.4.0 registers **no** recipe
items (`registered_recipe_items()` is empty), so any such key in this registry today is an
out-of-tree plugin contract, not a sparkrun field.

## Notes

Command-template rules and traps. These are the mechanics the lanes cite as
`recipes/MECHANICS.md §Notes`.

### 0.4.0 binds `{model}` to the prepared path

On a launch with a prepared model, `bind_runtime_models` writes operation-local overrides:
`model` → the prepared in-container snapshot path, `model_revision` →
`_prepared_model_revision`, `revision` → the manifest revision for vLLM and sglang, and
`_gguf_model_path` / `mmproj` when the artifact has them
(`models/runtime.py:44-60`). So in 0.4.2:

- `{model}` renders the **prepared path**, not the declared repo id. That is why
  `--served-model-name {model}` advertises
  `/cache/huggingface/hub/models--<org>--<name>/snapshots/<sha>`. This file said the
  opposite before 2026-10-19; that note was wrong for 0.4.0.
- `--revision` is **not** stripped from the template, and `{model_revision}` does resolve
  when the recipe pins one — to the prepared revision, because operation overrides outrank
  `defaults` in the chain (`core/recipe.py:1674-1682`).
- `validate_runtime_command` returns early when the prepared path appears as a token, or
  as `--flag=<path>` (`models/runtime.py:85-92`). Otherwise the command must name the
  declared repo id as a token and pass a revision flag with the **prepared** revision in
  the space or `=` spelling (`models/runtime.py:93-104`).
- A dry run (`-n`) can still print the repo id, because bindings exist only when a
  prepared model is present; a live `GET /v1/models` is the acceptance check for an
  advertised id.

The shipped arms that keep the literal-snapshot shape (the decision JEV pair, the Poolside Laguna
pair) satisfy the validator by the first clause above, and keep the engine's model argument
independent of binding. `tests/test_recipe_placeholder_resolution.py::LiteralShaConsistency`
requires every 40-hex token in such a command to equal the top-level `model_revision`, so a revision
bump cannot silently serve a stale snapshot. `{model}` is the equivalent and simpler spelling when the
arm does not need a literal; do not mix the two in one command.

### The served model id

An sglang or vLLM template that writes `--served-model-name {model}` serves the prepared
path as its model id — wrong for clients, the proxy, and benchmark targets. Declare the
literal and render the flag from it:

```yaml
defaults:
  served_model_name: <org>/<name>          # the upstream repo id
command: >
  --model-path {model}
  --served-model-name {served_model_name}
```

Both lines are required together: a declared key the command never references is
dropped from the rendered command (`core/launcher.py:939-1029`; 0.4.2 reports it as the
`unmapped-config-key` warning instead of dropping it silently), and the runtime's own append fires only when the flag is
absent, with fill policy leaving an existing value untouched
(`runtimes/base.py:925-981`; sglang call site `runtimes/sglang.py:370-374`). The two ds4
shim arms are the deliberate exception: their in-container launchers normalize the path
back to the repo id, and `tests/test_ds4_recipes.py` guards it. A fix is not verified until
a live boot's `GET /v1/models` returns the repo id.

### Placeholders and JSON

`render_template` iterates to a fixpoint, bounded by `_MAX_SUBSTITUTION_PASSES`, so a
default whose value is itself a template (`base_url: "http://localhost:{port}"`) resolves
too (`utils/text.py:186-229`). Literal braces are masked before substitution and restored
after, and a `{placeholder}` nested inside a JSON blob does resolve — quoted or not
(`core/recipe.py:1550-1582`). The `{{` / `}}` doubled-brace escape is the v1 spelling; in a
v2 recipe the convention is detected from `{{` and collapsed, but it draws
`deprecated-brace-escape` and is slated to stop working in v3
(`core/validation.py:1464-1499`).

Traps that remain:

- A `{key}` with no matching default renders as the literal and dies at the engine; an
  uncommented flag whose placeholder has no default renders as the flag alone and **swallows
  the next token** (or errors at argparse). `recipe validate` does not check placeholder
  resolvability, so `tests/test_recipe_placeholder_resolution.py` does.
- vLLM's speculative-config field is **`model`**, not `draft_model`; sparkrun's draft
  detection reads `speculative_config.model` and adds that repo to the distribution set
  with its **own** `revision` (`runtimes/_vllm_common.py:356-374`;
  `runtimes/vllm_distributed.py:125-128`). An inline JSON literal in `command:` never
  reaches the config chain, so the drafter is neither bound nor distributed. Put the JSON
  in `defaults:` and reference it as `'{speculative_config}'`.
- A leading `_`-prefixed key declared under `defaults:` warns `internal-config-key`: those
  names are injected mid-launch and the injection outranks the recipe, but it is skipped
  under `--dry-run`, for pre-placed weights, and when the model was not pre-synced
  (`core/validation.py:722-770`).
- Comments never go inside a folded `command:` block: a `>` scalar keeps them as literal
  text and the shell then treats the rest of the line as its own.

- **A `command:` template suppresses sparkrun's own flag emission for a key it references** —
  with a template present, sparkrun substitutes the placeholder instead of injecting the
  mapped flag (only the no-template `_build_base_command` consults the flag map,
  `runtimes/sglang.py`); a launcher shim that "ignores unknown args" then drops the value and
  the engine falls back to its own default (observed TP=3 on a 4-node cluster) — silently
  wrong, not an error. Check the rendered serve line *and* the launcher log that echoes the
  resolved value. — src: `.swival/memory/sparkrun-notes.md:502-516`.
- **Folded `>` commands turn JSON-shaped defaults into four bare words if the shell quotes
  are eaten by YAML**: `limit_mm_per_prompt: '{"image": 4, "video": 1}'` as a plain scalar
  loses its quotes at parse time; written `>-` they survive as one shell word. `recipe
  validate` (even `--strict`) passes on the broken form — only the rendered command via
  `sparkrun run --dry-run --hosts 127.0.0.1` catches it. — src:
  `.swival/memory/sparkrun-notes.md:271-277`.
- **YAML quoting traps**: a scalar beginning with `@` must be quoted
  (`mods: ["@littlecedar/mods/name"]`; unquoted it fails near column 1), and generated YAML
  must quote any value containing `: ` (`description: x: y` dies with
  `yaml.scanner.ScannerError`). — src: `.swival/memory/sparkrun-notes.md:211-212,366-369`.
- **Never transcribe a value you cannot see** — some strings (for example a model class name
  inside `hf_overrides`) come back through the read layer as a placeholder token, so a
  hand-written new recipe ships the placeholder — and it can round-trip back to the real
  string on write, so nothing looks wrong. Lift it: read the sibling recipe in Python, splice
  the block verbatim, and `assert` the extracted value is unchanged. — src:
  `.swival/memory/sparkrun-notes.md:370-376`.
- **`env:` cannot carry a value derived from `{model}`** — where a recipe needs a model-path
  env (observed: `CUDA_EXL3_MODEL_PATH` for a DSpark drafter), the only working route is a
  serve-line prefix (`CUDA_EXL3_MODEL_PATH=<path> vllm serve …`); without it the engine fails
  at init *after* a 7-minute weight load. — src: `.swival/memory/MEMORY.md:574-585`.

### What `recipe validate` can see

`recipe validate` reports three severities: errors that sparkrun cannot honor, warnings
that break or behave differently on another cluster or a later sparkrun, and suggestions
for the author (`core/validation.py:1-46`). Only errors fail by default;
`--strict` makes warnings fail, and `--fail-on none|error|warning|suggestion` sets the bar
explicitly (`core/validation.py:74-107`; `cli/_recipe.py:158-228`). `--json` emits
`valid`, `failed`, `fail_on`, per-severity counts, and the issue list
(`cli/_recipe.py:201-219`). `recipe show` prints the canonical `to_dict()` export and a
VRAM estimate (`cli/_recipe.py:128-155`); `recipe vram` estimates with `--tp`,
`--max-model-len`, and `--gpu-mem` overrides (`cli/_recipe.py:236-284`).

Findings that pass plain validate and still matter at boot — a missing placeholder
default, an unreferenced default, a path a managed mount owns, a hardcoded serve flag —
are exactly the ones the repo's guards enforce.

- **`recipe validate` does not check that mods exist** — a nonexistent mod validates clean, so
  a green gate does not mean the recipe will launch; the real launch fails fast with
  `Could not resolve mod '<ref>'. Tried: <paths>`. — src: `.swival/memory/MEMORY.md:526`;
  `.swival/memory/sparkrun-notes.md:60-72`.
- **A `recipe validate` suggestion can be pre-existing** — compare against a sibling before
  "fixing" it (`restated-managed-path` fires identically on a shipped recipe). — src:
  `.swival/memory/sparkrun-notes.md:377-379`.
- **`recipe vram`'s "Model weights" line can be an invented number** — when the HF metadata
  fetch exceeds its 30 s budget it falls back to `param_count × dtype_bytes` with no marking;
  the tell is identical sizes for different models, and for a 4-bit checkpoint the fallback is
  ~1.9 GB optimistic, so the "fit: YES" verdict is computed from a made-up number. Take the
  real size from `model.safetensors.index.json` `metadata.total_size`. — src:
  `.swival/memory/sparkrun-notes.md:110-121`.

### Pooling (embedding / reranker) recipes

- **`metadata.native_apis` cannot express "embeddings"** — it is validated as a subset of the
  runtime family's `native_api_options()`; for vLLM that set is exactly
  `["chat_completions", "responses", "messages"]`, so declaring `embeddings` fails
  `recipe validate` with `readiness-incompatible` — the honest-looking edit is the wrong one.
  Declare nothing and set `readiness: {inference: false}`; the consequence is no `sparkrun
  proxy` routing for `/v1/embeddings`. — src: `.swival/memory/sparkrun-notes.md:254-265`.
- **The default readiness probe fails a healthy pooling server** (it streams a chat
  completion and requires a token); `readiness.inference: false` keeps the port and
  `/health`. — src: `.swival/memory/sparkrun-notes.md:266-270`.
- **`sparkrun benchmarking/*.yaml` cannot measure a pooling recipe at all** — every profile
  drives `/chat/completions`, and the "no measured rows" path is a *skip*, not an error, so a
  run can look clean and have measured nothing. — src:
  `.swival/memory/sparkrun-notes.md:289-292`.
- **Multi-document YAML is not a way to colocate a pair** (`ComposerError: expected a single
  document`), and vLLM's `--gpu-memory-utilization` is an absolute cap on total device usage,
  so two engines that sum past the device fail at init. — src:
  `.swival/memory/sparkrun-notes.md:284-288`.

### CLI mechanics

Corpus-derived launch/CLI mechanics (2026-10-09); re-verify flag spellings against the
installed build before quoting one.

- **`-n`/`--dry-run` is not inert**: it really executes `pre_exec`, but **skips** the
  registry-sync step and the InfiniBand detection step — so a clean dry-run (a) does not
  predict a node-side clone failure, and (b) prints "No InfiniBand detected" and renders **no**
  `NCCL_IB_*` env, a false negative; judge comm env only in the live container. It requires a
  host (`-n` alone: `No hosts specified`), and a TP=2 recipe needs **both** nodes even for a
  dry run — a single host fails with a misleading `cluster has no free capacity`. — src:
  `.swival/memory/sparkrun-notes.md:90-107,342-351,429-451`; `.swival/HISTORY.md:4010`.
- **`-o key=value` reaches `defaults:` only.** It cannot change a top-level key (there is no
  `-o` that swaps `model:` and no error is raised), and it is a silent no-op for a key the
  recipe never declares. To add a flag: edit the recipe to route it, or `-o 'extra_args=…'` —
  and `extra_args` **appends**, so a flag the recipe already sets lands twice (last wins,
  fragile); grep the rendered line for the flag *and* its duplicate. `-b key=value` overrides
  benchmark args; replication count is a benchmark-profile arg (`-b runs=7`), there is no
  `--runs` flag. — src: `.swival/memory/sparkrun-notes.md:216,358-362,399-415,230-232`.
- **`sparkrun benchmark -o unmapped_flag=…` warns, then completes normally and writes JSONs
  while recording the override in `state.yaml`** — it reads as a genuine null result for a
  flag that never reached the server. `sparkrun benchmark --dry-run` surfaces that warning in
  ~3 s and is the cheapest guard before any new override. — src:
  `.swival/memory/sparkrun-notes.md:8-16`.
- **`--profile NAME` resolves against the cached registry clone, not the working tree** — a
  just-written profile is "not found". `--profile` accepts a path, so pass an absolute path.
  — src: `.swival/memory/sparkrun-notes.md:233-235`.
- **`--timeout` defaults to 14400 s and applies to a *hung* server** — a wedged config holds
  the slot for hours; pass `--timeout 1800` on exploratory arms. — src:
  `.swival/memory/sparkrun-notes.md:236-238`.
- **There is no `sparkrun up` and no `sparkrun stop all`**; launch and measure via
  `sparkrun benchmark performance --hosts a,b --profile <name> <recipe>`. List args **zip
  positionally**, not as a cross product — confirm the cell count with `--dry-run`. — src:
  `.swival/memory/sparkrun-notes.md:227-229`; `.swival/HISTORY.md:4010`.
- **Never identify a job to stop by parsing `sparkrun status`** — it lists the whole cluster,
  so "the first job id" can be somebody else's workload. Derive the id from the container name
  on the node you measured (the id is embedded in it); `sparkrun stop` can report success on
  the wrong containers when given a stale id, and can claim success while a container lives —
  `docker ps` the node. — src: `.swival/memory/sparkrun-notes.md:304-331`.
- **`docker logs <sparkrun-container>` is empty** — serve output goes to
  `/tmp/sparkrun_serve.log` *inside* the container; read it with `docker exec <c> cat`.
  Containers auto-remove by default, so a post-mortem needs `sparkrun run --no-rm`. — src:
  `.swival/memory/MEMORY.md:942-946`.
- **Leftover containers hold the serve port and fake a healthy boot** — a killed launch
  leaves `node_*` containers on workers, and the next boot's readiness probe hits the *old*
  server (ready at ~74 s versus ~250 s). Check every node's
  `docker ps -aq --filter name=sparkrun`. — src: `.swival/HISTORY.md:3215`;
  `.swival/memory/measurement-hygiene.md:146-166`.
- **Benchmark result artifacts carry no provenance** — the `.json`/`.csv` hold only model and
  per-cell throughput, no recipe text and no serve command; only the launcher's own stdout
  (`Serve command:` + `Pinned image SHA:`) records what ran, so **keep the per-arm log**. —
  src: `.swival/memory/sparkrun-notes.md:239-243`.
- **`runs/` is scratch and gets reaped; the `--output` file is the durable artifact** and
  carries the same records — read `runs/` while it exists, but cite the `--output` file for
  anything you may need later. — src: `.swival/memory/bench-artifact-metrics.md:28-39`.
- **sparkrun is a uv tool with its own interpreter** (not a repo-venv dependency); its flag
  maps, validation checks, and recipe grammar live under
  `~/.local/share/uv/tools/sparkrun/lib/python3.12/site-packages/sparkrun/`. A flag's presence
  in the recipe grammar and its presence in the runtime flag map are different questions:
  `recipe validate` checks grammar, not engine semantics. — src:
  `.swival/memory/sparkrun-notes.md:385-395`.

### Env, portability, and distribution

- **The portability rule is broader than the managed comm set: *any* env value naming a host
  device is forbidden.** The concrete case was a vendor `B12X_ROCE_HCA:
  rocep1s0f0,roceP2p1s0f0` — not sparkrun-managed, so it looked acceptable, but the engine
  takes a literal HCA list and falls back to the *detected* `NCCL_IB_HCA` when unset
  (`roce_oneshot.py` → `discover_hcas`), so setting it was contraindicated. Test by grepping
  env **values** for device patterns (`rocep|enp|ens|enP|eth` + digit/f). Levers that carry no
  device name and are fine to set: `NCCL_P2P_DISABLE`, `NCCL_SHM_DISABLE`, `NCCL_PROTO`,
  `NCCL_BUFFSIZE`, `NCCL_MAX_NCHANNELS`. — src:
  `.swival/memory/sparkrun-notes.md:466-474`.
- **sparkrun fills NCCL/IB env from its live probe and it is *better* than a pin** — only the
  ACTIVE ports are included, where a hand-written `NCCL_IB_HCA` silently includes a DOWN port.
  — src: `.swival/memory/sparkrun-notes.md:437-451`.
- **`HF_HOME` is likewise overridden by sparkrun** (`overridden-cache-env`); check
  `recipe validate --json` codes before shipping a recipe that "validates clean". — src:
  `.swival/memory/MEMORY.md:536-541`.
- **`transfer_mode` semantics matter for arch and registry location**: `local` pulls the image
  on the control machine (fails for an arm64-only image when the control host is amd64, `no
  matching manifest`); `pull` had a sparkrun bug; `delegated` builds/pulls on the head node
  and works when architectures differ. — src: `.swival/memory/MEMORY.md:593-598`.

### Engine flag semantics — SGLang/vLLM

The registry is mostly SGLang; the vLLM pins are mutable nightly tags, so treat these as
semantics, not as a fixed version — a recipe's version comes from its container image.
Several items are lane-specific; re-verify on the pinned image before trusting a spelling.
**Do not cross-apply flags across engines**: the SGLang UNO draft rejects `--enable-lora`, and
the vLLM memory model (`gpu-memory-utilization`, `compilation_config`) and multi-node flags
differ from SGLang's — pick the column that matches the recipe's `runtime:`. — src:
`.swival/doc_conserving_memory.md:39-75`.

SGLang column:

- **`--mamba-ssm-dtype` unset reads `config.json`'s `mamba_ssm_dtype`** (`float32` for
  Qwen3.8-Flash-Next, so the linear-attention/GDN state pool runs fp32 by default); setting
  `bfloat16` is the single biggest memory lever (~11–22 GB/node). — src:
  `.swival/HISTORY.md:139-158`.
- **`--linear-attn-decode-backend flashinfer` is a no-op on GB10**: the auto-enable gate
  requires `is_sm100_supported()` (False on SM121, silently) *and*
  `mamba_ssm_dtype == bfloat16`. An explicit-flag guard checking `capability[0] >= 10` passes
  on GB10 (12), so the flag is not *rejected* — it is just not auto-enabled, and no log line
  says so. — src: `.swival/HISTORY.md:292-316`; `.swival/memory/gb10-notes.md:41-55`.
- **`num_speculative_tokens` is validated against the drafter's fixed block size** (`must be
  divisible by n_predict=5`), so legal `k` is ≤5 or ×5 — read the constraint off the *error*,
  then design the sweep around it. — src: `.swival/memory/MEMORY.md:932-936`.
- **Accept length and throughput can point opposite ways** — `k=5` accepted more tokens/step
  than `k=3` and was still slower; the per-position acceptance curve shows why (tail slots
  accept at 12%/5% and still cost a verify pass). Read per-position, not just the mean: a
  speedup is a **profile**, not a scalar — the optimum moved with concurrency. — src:
  `.swival/memory/MEMORY.md:921-931`.
- **`draft_tensor_parallel_size` is a first-class `SpeculativeConfig` field** ("1 or the same
  as the target TP size") — pointing it at 1 under a TP=3/TP=6 target sidesteps the
  drafter-divisibility wall. — src: `.swival/HISTORY.md:2369-2371`.
- **The bare `--cuda-graph-max-bs` does not exist in this SGLang line** — only the `-decode`
  and `-prefill` variants. — src: `.swival/HISTORY.md` (ds4 flag bundle).
- **fp8 KV is not automatically worth it on a sparse-attention model** — the sparse-attention
  index dtype is hardcoded (`index_state_dtype = bfloat16`) and the bytes-per-token helper
  takes no dtype parameter, so fp8 only shrinks the full-attention layers. — src:
  `.swival/HISTORY.md:476`.
- **`--no-ple-offload-embedding` is the right default on GB10** — on unified memory the
  "offloaded" PLE table is a pinned host copy out of the same pool, so it frees nothing and
  costs a host gather per step. — src: `.swival/HISTORY.md:174`.
- **`--moe-runner-backend auto` can resolve to a backend that cannot run, per checkpoint** —
  two exports of "the same model" (same image digest) can disagree; `flashinfer_trtllm` is
  dead on this hardware (no SM121 cubins), so name `flashinfer_cutlass` explicitly; do not
  generalise a backend-resolution result across exports. — src:
  `.swival/memory/gb10-notes.md:56-76`.
- **`mem_fraction_static = (weights + KV pool) / capacity`, and on GB10 "available GPU
  memory" is `psutil.virtual_memory().available` (system RAM)** — it is relative to free
  memory at *each engine's own boot*, so stacking engines needs absolute-GiB budgeting, not
  summed caps; the precise pool pin is `--max-total-tokens`. Raising `MEM_FRACTION_STATIC`
  above ~0.80–0.85 wedges nodes on unified memory — a `0.90` probe wedged three of four nodes
  (ping alive, SSH banner timeout) and bricked one into a manual power cycle; on GB10 GPU
  memory *is* host memory. — src: `.swival/HISTORY.md:1792-1809,4469-4473`.
- **`/metrics` is served on `port_base + 3`, not the API port**, and only exists if the recipe
  sets `--enable-metrics` — check the recipe, not the node. — src:
  `.swival/memory/bench-artifact-metrics.md:88-91`.
- **`#queue-req` is informative only on `Prefill batch` lines; it is always 0 on `Decode
  batch` lines** (a false null indistinguishable from a real zero — contradict any all-zero
  parser column with a bare `re.findall`). Capacity claims read decode lines, admission claims
  read prefill lines; never a bare `grep '#running-req'` (the field order differs between line
  types); the `Decode`/`Prefill` label describes the batch, not the harness phase. — src:
  `.swival/memory/queue-metrics.md:7-39`.

vLLM column (from the vendored upstream corpus — upstream vLLM docs and verbatim upstream
modules under `.swival/`):

- **vLLM snapshots its environment after service init** (`enable_envs_cache()` wraps
  `__getattr__` in `functools.cache`): setting a `VLLM_*` var after the server has started has
  no effect. — src: `.swival/envs.py:2222-2240`.
- **The memory contract is `requested_memory = ceil(init_snapshot.total_memory ×
  gpu_memory_utilization)`**, and boot raises with "Decrease GPU memory utilization…" when
  free memory is short. On **integrated GPUs** (`MemorySnapshot.measure`) free memory is
  overridden with `psutil.virtual_memory().available`, because `cudaMemGetInfo` underreports
  on UMA — the upstream comment names GH200, **DGX Spark**, and Jetson Orin. — src:
  `.swival/worker_utils.py:533-550`; `.swival/mem_utils.py:143-151`.
- **The manual KV-pool pin is the flag `--kv-cache-memory=<bytes>`** (config field
  `kv_cache_memory_bytes`); setting it skips profiling and does **not** respect
  `--gpu-memory-utilization`. — src: `.swival/gpu_worker.py:884,547-563`.
- **Multi-node spelling differs from SGLang's**: vLLM uses `--nnodes --node-rank
  --master-addr --headless` plus `-e VLLM_HOST_IP=<node-ip>` and
  `--distributed-executor-backend ray|mp`; SGLang recipes here are driven with
  `--dist-init-addr`, so a vLLM recipe must not copy that. GPUDirect RDMA in a container needs
  `IPC_LOCK` and a `/dev/shm` mount (`--ipc=host --shm-size=16G`). — src:
  `.swival/doc_parallelism_scaling.md:146-158,174-200`.
- **Strategy rules**: fits one GPU → no distribution; fits one node → `tensor_parallel_size` =
  GPUs/node; too big → TP within a node plus `pipeline_parallel_size` = nodes. Nodes without
  NVLink should prefer PP over TP, and an uneven layer split also prefers PP. — src:
  `.swival/doc_parallelism_scaling.md:7-27`.
- **Sleep mode has a two-part online prerequisite** — the server must be started with
  `VLLM_SERVER_DEV_MODE=1` **and** `--enable-sleep-mode`; the endpoints only register in dev
  mode. Level 1 offloads weights to CPU RAM and discards KV; level 2 discards both. — src:
  `.swival/doc_sleep_mode.md:14-22,91-139`.
- **LoRA silent-corruption hazard**: under `--enable-mixed-moe-lora-format` vLLM trusts the
  caller's `is_3d_lora_weight` and does **not** verify the checkpoint — a wrong declaration
  loads into wrong buffers and emits garbage with no load-time error. `--max-lora-rank` must
  equal the maximum adapter rank in use (too high wastes memory and hurts performance). —
  src: `.swival/doc_lora.md:281-300,441-453`.
- **`limit_mm_per_prompt` sets multimodal input limits**; setting a modality to `0` allocates
  nothing for it (even a text-only run of a multimodal model). — src:
  `.swival/doc_conserving_memory.md:94-160`.

### Checkpoint and model-path mechanics

- **The HF cache is a two-level layout** (`blobs/<xx>/<sha>` written to, `snapshots/<hash>` as
  symlinks): any mount that exposes only a `models--…` or a snapshot directory leaves
  symlinks dangling — **mount the whole `hub/` directory**. `du` on a model directory lies
  because shards are symlinks into `blobs/`: measure with `find -L … -printf %s`. — src:
  `.swival/trash/…/KNAPCIO-SGLANG-INTEGRATION.md` (Engram packing);
  `.swival/trash/…/NOTES.md`; `.swival/memory/MEMORY.md:586-592`.
- **`cluster_config.resolved_model_path` is wrong for an HF snapshot dir** — a snapshot is a
  tree of symlinks into `../../blobs`, so mounting only the snapshot leaves `config.json`
  dangling and the engine rejects it (`Invalid repository ID or local directory`); the managed
  `/cache/huggingface` mount is the right surface. — src:
  `.swival/memory/MEMORY.md:586-592`.
- **A recipe must not pin a `container:` without resolving the right digest.** A multi-arch
  image has an **index** digest and per-platform **manifest** digests, and Docker accepts
  both, so the wrong one looks plausible; the tag's `Docker-Content-Digest` header reports the
  index digest, which is what belongs in the pin. A mutable tag can resolve to a different
  commit than the pinned digest of the same tag — resolve the pin and compare `git log` inside
  each before treating two images as the same build. — src:
  `.swival/memory/sparkrun-notes.md:332-338`; `.swival/memory/remote-execution.md:75-94`.
- **A launcher/mod that `execve`s the engine inherits the image's baked `ENV`**, so a
  `setdefault(...)` for a var the image already bakes is a **silent no-op** (the image wins) —
  use `env.update(MY_ENV)` and keep keys disjoint from the recipe-owned ones. Corollary:
  `docker exec <c> env` is **not** a valid probe for what the launcher sets (fresh shell from
  the container's *creation* env). — src: `.swival/memory/sparkrun-notes.md:518-534`;
  `.swival/memory/MEMORY.md:115-119`.
- **A consuming image `ENTRYPOINT` blocks a sparkrun launch, and the fix is a recipe key, not
  a flag**: `executor_config: entrypoint: ""` (or `-o entrypoint=''`). A good failure — it
  fires before any GPU work. — src: `.swival/memory/MEMORY.md:568-573`.

## Per-family agent guides

The Qwen3.8-Flash-Next lane carries its own
[`attic/qwen4/AGENTS.md`](../attic/qwen4/AGENTS.md) (state, constraints, workstream plan,
runbook) and [`qwen4/README.md`](qwen4/README.md) (the recipe/lane summary), with
`../attic/qwen4/NOTES.md` (working notes). Read those before starting work in that
directory. Archived arms and the lane's research record, journal, and coordination ledger
live under [`../attic/qwen4/`](../attic/qwen4/).

The DeepSeek V4.1-Flash lanes are documented in [`ds4/README.md`](ds4/README.md) (user
guide) and [`attic/ds4/AGENTS.md`](../attic/ds4/AGENTS.md) (design, boot gates, guards, and
measurement discipline for both the knapcio TP=4 and TensorFold TP=2 lanes); the retired
vLLM/EXL3 lane is under [`../attic/ds4/`](../attic/ds4/).

The IFM K2-Horizon lanes are documented in [`ifm/README.md`](ifm/README.md) (recipe
summary) and [`attic/ifm/AGENTS.md`](../attic/ifm/AGENTS.md) (constraints, falsified claims,
guards, and the validation ritual for the `0.9B` / `7B-FP8` set); the research record and
journals are git-ignored working files beside them.

The Ornith 1.5 lanes are documented in [`ornith/README.md`](ornith/README.md) (per-recipe
wiring, caveats, and the three archived arms) and
[`attic/ornith/AGENTS.md`](../attic/ornith/AGENTS.md) (lane state, constraints, the A/B
negative result, and the validation ritual); the lane's guards are in
`tests/test_ornith_recipes.py` (O1–O5).

The Qwen3 lane is documented in [`qwen3/README.md`](qwen3/README.md) (recipe summary) and
[`attic/qwen3/AGENTS.md`](../attic/qwen3/AGENTS.md) (model thesis, tunable rationale,
negative results, and the validation ritual); the lane's research record — including the
no-spec control recipe, the measured DSpark arm, and the depth/SSM/queue threads — moved to
[`../attic/qwen3/`](../attic/qwen3/) on 2026-10-11 with a manifest mapping its `§N` cite
forms.