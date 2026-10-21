# Mechanics

Recipe-schema reference for the `littlecedar` registry, written against **sparkrun
0.4.2-alpha+g36d8a44** — the installed build at
`/home/siv/.local/share/uv/tools/sparkrun/lib/python3.12/site-packages/sparkrun/`.
Every `file.py:line` cite is relative to that package tree. Re-derive a line before
trusting it after an upgrade; `sparkrun --version` names the build you have.

**Cite provenance.** The cites re-derived against 0.4.2 on 2026-10-21 are: every cite in
§[The one rule](#the-one-rule-that-decides-whether-a-knob-works), and in §Key reference
under *`sparkrun_version`*, *`recipe_version`*, *`description`*, *`metadata`*,
*`maintainer`* and *`model_revision`*, plus §[Notes](#notes). Every other cite still
carries 0.4.0 numbering — re-derive it with `grep -n` on the named symbol before trusting
it. The module paths themselves (`core/launcher.py`, `core/recipe.py`,
`core/validation.py`, `models/runtime.py`) are the same in both builds.

The format is v2 and the authoritative key set is `_KNOWN_KEYS`
(`core/recipe.py:78-120`): **41 keys**, counted from the literal set. A key outside
it is either plugin-owned or swept into `runtime_config`.

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
  (`core/recipe.py:2480-2484`).
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

- A `{key}` with no matching default renders as the literal and dies at the engine;
  `recipe validate` does not check placeholder resolvability, so
  `tests/test_recipe_placeholder_resolution.py` does.
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