# RESEARCH_LORE — what `.swival/` teaches about authoring sparkrun recipes

Status: research note, 2026-10-09. Not a recipe change; nothing here is shipped. Mined from the
git-ignored `.swival/` work corpus (a previous agent's recipe-authoring scratch tree) and written
down so it survives the corpus.

Read alongside [`../AGENTS.md`](../AGENTS.md) (the repo-wide authoring contract),
[`../recipes/README.md`](../recipes/README.md) (registry index), [`../benchmarking/README.md`](../benchmarking/README.md)
(benchmark read rules), and the per-lane `recipes/<family>/AGENTS.md` guides. Evidence vocabulary
follows [`CUSTOM_ALL_REDUCE_SM120_EXPERIMENTS.md`](CUSTOM_ALL_REDUCE_SM120_EXPERIMENTS.md) and
`recipes/ds4/AGENTS.md`: **VERIFIED** = read from a primary artifact or measured; **LIKELY** =
strong secondary evidence; **SPECULATIVE** = reasoning without a source.

> **Verdict up front.** `.swival/` is not a second rulebook; it is the long-form *evidence and scar
> tissue* behind the rules [`../AGENTS.md`](../AGENTS.md) states in one line. Its durable value is
> (1) trap catalogues that cost a boot each, (2) engine-semantics the repo's SGLang-centric docs do
> not cover (a vendored slice of upstream vLLM source plus a Knapcio/TensorFold lane post-mortem),
> and (3) a list of claims that were **true once and are now stale** — which is exactly the class of
> statement that silently corrupts a new recipe.

---

## 0. The corpus, and how to read citations here

`.swival/` is git-ignored (`/.swival/` in `.gitignore`), so every `src:` below points at a file that
does **not** ship. A citation is therefore a provenance record, not a clickable link; the durable
copy of each fact is this document. Treat a fact as it is labelled, not because of the file it came
from.

| artifact | what it is |
|---|---|
| `.swival/memory/*.md` | ~13 durable-lesson notes (recipe grammar, CLI mechanics, mod traps, measurement hygiene, GB10 hardware) + `MEMORY.md` index |
| `.swival/doc_*.md`, `.swival/serve_args.md` | unversioned upstream **vLLM** doc snapshots (serving API, LoRA, sleep mode, parallelism, memory conservation, serve args) |
| `.swival/envs.py`, `gpu_worker.py`, `worker_utils.py`, `mem_utils.py` | verbatim upstream **vLLM** modules (SPDX: vLLM) fetched as a source of truth for exact env-var names, KV/memory math, and worker lifecycle |
| `.swival/tree_main.json` | GitHub `git/trees` dump for `vllm-project/vllm` at commit `8a5cf5438728180210aea43897d6a717de4b46ec` |
| `.swival/ds41_tree.json` | Hugging Face tree for the DeepSeek-V4.1 checkpoint (48 shards, `inference/`, `encoding/`, tech report) |
| `.swival/HISTORY.md` | dated session log, 2026-09-12 → 2026-10-06; roughly a third is substantive, the rest is process narration |
| `.swival/trash/**` | two complete lane post-mortems (TensorFold TP=2; Knapcio DS4 TP=4 SGLang integration) — the densest artifacts in the tree |
| `.swival/bg/*.log` | quality-battery outputs (mostly empty; the two real ones corroborate the EXL3 quality results) |
| `.swival/repl_history` | user prompts only; near-zero technical yield |

Two rules for using this document: **cite the shipped repo doc** when one exists, and **re-verify any
number** before quoting it — this corpus was written on hardware over three weeks and its own
`HISTORY.md` confuses stale and current state in places (see §11).

---

## 1. Recipe grammar and placeholder resolution

- **A `defaults:` key is silently dead unless a `{placeholder}` in `command:` consumes it.** Adding
  the key alone renders nothing and the flag never reaches the engine; the `DefaultsAreConsumed`
  guard exists for exactly this. — src: `.swival/memory/MEMORY.md:907-910`. Root
  [`AGENTS.md`](../AGENTS.md) states the rule; here is the failure it prevents.
- **A `command:` template suppresses sparkrun's own flag emission for that key.** With a template
  present, sparkrun substitutes the placeholder instead of injecting the mapped flag (only the
  no-template `_build_base_command` consults the flag map, `runtimes/sglang.py`). A launcher shim
  that "ignores unknown args" then drops the value and the engine falls back to its own default
  (observed TP=3 on a 4-node cluster) — silently wrong, not an error. Every `defaults` key a
  template references needs a consumer, and the check is the rendered serve line *and* the
  launcher log that echoes the resolved value. — src: `.swival/memory/sparkrun-notes.md:502-516`.
- **Folded `>` commands turn JSON-shaped defaults into four bare words if the shell quotes are eaten
  by YAML.** `limit_mm_per_prompt: '{"image": 4, "video": 1}'` written as a plain scalar loses its
  quotes at parse time; written `>-` they survive as one shell word. `recipe validate` (even
  `--strict`) passes on the broken form — only the rendered command via
  `sparkrun run --dry-run --hosts 127.0.0.1` catches it. — src: `.swival/memory/sparkrun-notes.md:271-277`;
  root [`AGENTS.md`](../AGENTS.md) agrees.
- **Recipe version 2 collapses `{{`/`}}` and warns `deprecated-brace-escape`.** Write plain
  `'{"key": value}'`; a `{placeholder}` *inside* the JSON still resolves. — src:
  `.swival/memory/MEMORY.md:534-535`.
- **Every `{placeholder}` in `command:` needs a matching `defaults:` key**; an uncommented flag whose
  placeholder has no default renders as the flag alone and swallows the next token or errors at
  argparse. Same trap in reverse: `-o` for a key the recipe never declares is silently ignored
  (§2). — src: `.swival/memory/sparkrun-notes.md:213-215`.
- **A YAML scalar beginning with `@` must be quoted** (`mods: ["@littlecedar/mods/name"]`); unquoted
  it fails near column 1. Generating recipe YAML by string replacement requires quoting any value
  containing `: `, or `description: x: y` dies with `yaml.scanner.ScannerError`. — src:
  `.swival/memory/sparkrun-notes.md:211-212,366-369`.
- **Never transcribe a value you cannot see.** Some strings (for example a model class name inside
  `hf_overrides`) come back through the read layer as a placeholder token, so a hand-written new
  recipe ships the placeholder — and it can round-trip back to the real string on write, so nothing
  looks wrong. Lift it: read the sibling recipe in Python, splice the block verbatim, and `assert`
  the extracted value is unchanged. — src: `.swival/memory/sparkrun-notes.md:370-376`.
- **`env:` cannot carry a value derived from `{model}`.** For the cuda-exl3 lane the DSpark-drafter
  needs `CUDA_EXL3_MODEL_PATH`, and the only working route is a serve-line prefix
  (`CUDA_EXL3_MODEL_PATH=<path> vllm serve …`); without it the engine fails at init *after* a
  7-minute weight load. — src: `.swival/memory/MEMORY.md:574-585`.
- **An unknown top-level recipe key is silently absorbed into `runtime_config`.** That is why
  `revision:` is a dead pin and the correct spelling is top-level `model_revision:` (root
  [`AGENTS.md`](../AGENTS.md) documents the ban; this is the mechanism). Likewise a `name:` key is
  banned and `cluster_only:` is deprecated. — src: `.swival/memory/sparkrun-notes.md:206-215`;
  `.swival/HISTORY.md` (recipe-convention block).
- **A `recipe validate` suggestion can be pre-existing** — compare against a sibling before
  "fixing" it (for example `restated-managed-path` fires identically on a shipped recipe). — src:
  `.swival/memory/sparkrun-notes.md:377-379`; root [`AGENTS.md`](../AGENTS.md) agrees.
- **`recipe vram`'s "Model weights" line can be an invented number.** When the HF metadata fetch
  exceeds its 30 s budget it falls back to `param_count × dtype_bytes` with no marking; the tell is
  identical sizes for different models, and for a 4-bit checkpoint the fallback is ~1.9 GB
  optimistic, so the "fit: YES" verdict is computed from a made-up number. Take the real size from
  `model.safetensors.index.json` `metadata.total_size`. — src: `.swival/memory/sparkrun-notes.md:110-121`.
- **A recipe must not pin an HF `snapshots/<hash>` path** — it is ephemeral and vanishes when a
  shared cache re-resolves `<repo>/refs/main`. Pass the repo id and resolve at runtime. — src:
  `.swival/HISTORY.md` (checkpoint section §8 here for the mechanics).

### Pooling (embedding / reranker) recipes break chat-server assumptions

- **`metadata.native_apis` cannot express "embeddings".** It is validated as a subset of the runtime
  family's `native_api_options()`; for vLLM that set is exactly
  `["chat_completions", "responses", "messages"]`, so declaring `embeddings` fails `recipe validate`
  with `readiness-incompatible` — the honest-looking edit is the wrong one. Declare nothing and set
  `readiness: {inference: false}`. Consequence: no `sparkrun proxy` routing for `/v1/embeddings`. —
  src: `.swival/memory/sparkrun-notes.md:254-265`.
- **The default readiness probe fails a healthy pooling server** (it streams a chat completion and
  requires a token); `readiness.inference: false` keeps the port and `/health`. — src:
  `.swival/memory/sparkrun-notes.md:266-270`.
- **`sparkrun benchmarking/*.yaml` cannot measure a pooling recipe at all** — every profile drives
  `/chat/completions`, and the "no measured rows" path is a *skip*, not an error, so a run can look
  clean and have measured nothing. — src: `.swival/memory/sparkrun-notes.md:289-292`.
- **Multi-document YAML is not a way to colocate a pair** (`ComposerError: expected a single
  document`), and vLLM's `--gpu-memory-utilization` is an absolute cap on total device usage, so two
  engines that sum past the device fail at init. — src: `.swival/memory/sparkrun-notes.md:284-288`.

---

## 2. sparkrun CLI and launch mechanics

- **Every invocation on this working copy needs `HOME=$PWD/.local/sparkrun-home`** (else
  `PermissionError: ~/.config/sparkrun/registries.yaml` before a recipe is read); a fresh clone
  needs `mkdir -p .local/sparkrun-home`. A **fresh** home cannot resolve mods for `run -n` until the
  tree is registered: `HOME=$H sparkrun registry add file://$PWD` (`add` takes a URL, not a path). —
  src: `.swival/memory/MEMORY.md:1016-1020`; root [`AGENTS.md`](../AGENTS.md).
- **`-n`/`--dry-run` requires a host** (`-n` alone: `No hosts specified`), and it is **not inert** —
  it really executes `pre_exec`. It also **skips** two steps the real launch performs: the
  registry-sync step and the InfiniBand detection step. So a clean dry-run (a) does not predict a
  node-side clone failure, and (b) prints "No InfiniBand detected" and renders **no** `NCCL_IB_*`
  env — a false negative; judge comm env only in the live container. — src:
  `.swival/memory/sparkrun-notes.md:90-107,342-351,429-451`; root [`AGENTS.md`](../AGENTS.md).
- **A clean dry-run is not evidence a mod will resolve.** One observed recipe naming a nonexistent
  mod completed dry-run with exit 0 and printed nothing about mods. The trustworthy test is the real
  launch, which fails fast with `Could not resolve mod '<ref>'. Tried: <paths>`. — src:
  `.swival/memory/sparkrun-notes.md:60-72`.
- **`-o key=value` reaches `defaults:` only.** It cannot change a top-level key (there is no `-o`
  that swaps `model:` and no error is raised), and it is a silent no-op for a key the recipe does not
  route through a placeholder. To add a flag: either edit the recipe to route it, or
  `-o 'extra_args=…'` — and note `extra_args` **appends**, so a flag the recipe already sets lands
  twice (last wins, fragile); grep the rendered line for the flag *and* its duplicate. `-b key=value`
  overrides benchmark args. — src: `.swival/memory/sparkrun-notes.md:216,358-362,399-415`; root
  [`AGENTS.md`](../AGENTS.md).
- **`sparkrun benchmark -o unmapped_flag=…` warns, then completes normally and writes JSONs while
  recording the override in `state.yaml`** — it reads as a genuine null result for a flag that never
  reached the server. `sparkrun benchmark --dry-run` surfaces that warning in ~3 s and is the
  cheapest guard before any new override. — src: `.swival/memory/sparkrun-notes.md:8-16`.
- **Replication count is a benchmark-profile arg** (`-b runs=7`); there is no `--runs` flag. —
  src: `.swival/memory/sparkrun-notes.md:230-232`.
- **`--profile NAME` resolves against the cached registry clone, not the working tree**; a
  just-written profile is "not found". `--profile` accepts a path, so pass an absolute path. — src:
  `.swival/memory/sparkrun-notes.md:233-235`.
- **`--timeout` defaults to 14400 s and applies to a *hung* server**, so a wedged config holds the
  slot for hours; pass `--timeout 1800` on exploratory arms. — src:
  `.swival/memory/sparkrun-notes.md:236-238`.
- **Cluster mod delivery needs `transfer_mode: local`** or the node clones the registry itself and an
  unpushed local mod is invisible. Only `--cluster <name>` carries the ssh user and transfer mode;
  `--hosts <ip>` carries neither and still makes the node attempt a `file://` clone. Persist with
  `sparkrun cluster update <name> --transfer-mode local`. — src:
  `.swival/memory/sparkrun-notes.md:347-351`; root [`AGENTS.md`](../AGENTS.md).
- **Never identify a job to stop by parsing `sparkrun status`** — it lists the whole cluster, so "the
  first job id" can be somebody else's workload; a driver of ours nearly stopped an off-limits
  serving job this way. Derive the id from the container name on the node you measured (the id is
  embedded in it). Related: `sparkrun stop` can report success on the wrong containers when given a
  stale id, and can claim success while a container lives — `docker ps` the node. — src:
  `.swival/memory/sparkrun-notes.md:304-331`; root [`AGENTS.md`](../AGENTS.md).
- **`docker logs <sparkrun-container>` is empty** — serve output goes to `/tmp/sparkrun_serve.log`
  *inside* the container; read it with `docker exec <c> cat`. Containers auto-remove by default, so
  a post-mortem needs `sparkrun run --no-rm`. — src: `.swival/memory/MEMORY.md:942-946`;
  `.swival/memory/sparkrun-notes.md` (container section).
- **Leftover containers hold the serve port and fake a healthy boot** (a killed launch leaves
  `node_*` containers on workers; the next boot's readiness probe hits the *old* server and reports
  ready at ~74 s versus ~250 s). Check every node's `docker ps -aq --filter name=sparkrun`. — src:
  `.swival/HISTORY.md:3215`; `.swival/memory/measurement-hygiene.md:146-166`.
- **`recipe validate` does not check that mods exist** (a nonexistent mod validates clean), so a
  green gate does not mean the recipe will launch. — src: `.swival/memory/MEMORY.md:526`.
- **There is no `sparkrun up` and no `sparkrun stop all`**; launch and measure via
  `sparkrun benchmark performance --hosts a,b --profile <name> <recipe>`. A TP=2 recipe needs
  **both** nodes even for a *dry run* (a single host fails with a misleading `cluster has no free
  capacity`). sparkrun zips list args positionally, not as a cross product — confirm the cell count
  with `--dry-run`. — src: `.swival/memory/sparkrun-notes.md:227-229`;
  `.swival/HISTORY.md:4010`.
- **Benchmark result artifacts carry no provenance**: the `.json`/`.csv` hold only model and
  per-cell throughput, no recipe text and no serve command. Only the launcher's own stdout
  (`Serve command:` + `Pinned image SHA:`) records what ran, so **keep the per-arm log**. — src:
  `.swival/memory/sparkrun-notes.md:239-243`.
- **sparkrun is a uv tool with its own interpreter** (not a repo-venv dependency). Its flag maps,
  validation checks, and recipe grammar live under
  `~/.local/share/uv/tools/sparkrun/lib/python3.12/site-packages/sparkrun/`; a flag's presence in
  the recipe grammar and its presence in the runtime flag map are different questions, and
  `recipe validate` checks grammar, not engine semantics. — src:
  `.swival/memory/sparkrun-notes.md:385-395`.

---

## 3. Mod authoring mechanics and failure modes

- **Mods run as `pre_exec` in every container, sequentially, fail-fast**; a non-zero exit tears the
  whole launch down, so a patch must be idempotent and is re-applied on every launch (fresh
  container). — src: `.swival/HISTORY.md:236-238`; root [`AGENTS.md`](../AGENTS.md).
- **Mods run as root and cannot learn the real uid from the environment.** Infer ownership from a
  known path (`stat -c '%u' /cache/runtime`) and `reown()` anything created under `/cache/runtime`,
  or downstream user processes fail on root-owned leftovers. Content-based idempotence, not
  timestamps; `tmp` + `os.replace` restoring owner/mode. — src:
  `.swival/memory/sparkrun-notes.md:151-165`; `.swival/memory/gb10-notes.md:153`; root
  [`AGENTS.md`](../AGENTS.md).
- **NEVER import the inference engine (or any JIT-heavy library) from a `pre_exec` hook.** The
  highest-cost sparkrun gotcha in the corpus: `import sglang` triggers flashinfer JIT, which writes
  root-owned build artifacts under `/cache/runtime`; the uid-1000 server then dies at launch with
  `PermissionError`, **and every later launch of that recipe fails identically** because the
  poisoning persists. Recovery needs `sudo chown -R 1000:1000 <runtime-cache dir>`. `torch` +
  `safetensors` are safe for byte-level checkpoint rewriting. If an import is unavoidable,
  `chown -R` the **whole** runtime-cache mount (reowning only your subdirectory misses the JIT
  cache). — src: `.swival/memory/sparkrun-notes.md:167-204`; also
  `.swival/memory/container-probing.md:164-175`.
- **The mod harness is copy-pasted, not shared** — sparkrun ships only the mod's own directory, so
  `mods/common.sh` would not exist at launch. Copy `mods/mod-template/run.sh`. — src:
  `.swival/HISTORY.md:966`; root [`AGENTS.md`](../AGENTS.md).
- **Three ways a `pre_exec` mod passes dry-run and dies on the cluster**: a `python3 - <<'PY'`
  heredoc has its own scope (bash `warn`/`die` helpers are invisible to it → `NameError`); `find` on
  a nonexistent directory aborts the whole mod under `set -euo pipefail` (fires on a first boot —
  `mkdir -p` first, and comment it as load-bearing); and a **self-deleting** config-file workaround
  splits the group, because `pre_exec` runs once **per node** against one shared host-mounted dir —
  the first node gets the override and every later node the default, surfacing as a numerical
  mystery. — src: `.swival/memory/sparkrun-notes.md:134-156`.
- **A `pre_exec` hook is killed at a hard 600 s** (`pre_exec[2] failed … TIMEOUT after 600s`), and a
  mod's own `MOD_TIMEOUT` cannot extend it. A fetch or pack that can outlive the hook must detach
  (`setsid nohup`) and be resumable. — src: `.swival/HISTORY.md:4844,4859-4862`; root
  [`AGENTS.md`](../AGENTS.md).
- **Verify a mod's effect from the artifact it wrote in the runtime cache, never from its log or
  exit status.** A pidfile or a started loop reads as success while the actual write never happened.
  — src: `.swival/memory/sparkrun-notes.md:158-165`.
- **Fail closed, and assert numeric contracts.** Unknown state → `die`; refuse to patch when anchors
  are missing rather than guessing; a vendored patcher must prove its anchor byte-matches the **real**
  file extracted from the image (`--check` → compatible → apply → `--check` → already patched), md5
  the file, and back the target up once. Read a vendored mod's README for its **own no-op
  condition** before claiming it helps. — src: `.swival/memory/MEMORY.md:895-906`;
  `.swival/memory/container-probing.md:91-109`; root [`AGENTS.md`](../AGENTS.md).
- **A mod that looks alive can be doing nothing.** `drop_caches` failed twice over: sparkrun
  defaults `rootless=True`, so `/proc/sys` is read-only and the write errors while the loop keeps
  looking alive; and the line `echo 3 > /proc/sys/vm/drop_caches >> log 2>&1` applies redirects
  left-to-right with the last winning, so the `3` went to the log and the file got nothing. The
  right shape for cache hygiene is point-of-use `posix_fadvise(DONTNEED)`, not a node-wide drop. —
  src: `.swival/HISTORY.md:2086-2089,2482-2510`.
- **An unscoped mod reference resolves against the recipe's own directory, not the repo root**
  (the run-from directory's `mods` symlink participates, so repo-root `mods/` is reachable that
  way). The registry-scoped `@registry/mods/name` form resolves **only** from the node's registry
  git clone, so an uncommitted or unpushed mod is invisible. Order: write mod → `git add <dir> &&
  git commit` → `registry update <registry>` → re-render. — src:
  `.swival/memory/sparkrun-notes.md:29-59,42-48`; `.swival/memory/MEMORY.md:522-533`; root
  [`AGENTS.md`](../AGENTS.md).

---

## 4. Env, portability, and distribution

- **A recipe must not set any key in sparkrun's `MANAGED_COMM_ENV_KEYS`** (`NCCL_NET`, `NCCL_IB_HCA`,
  `NCCL_IB_GID_INDEX`, `NCCL_IB_DISABLE`, `NCCL_CROSS_NIC`, `NCCL_SOCKET_IFNAME`,
  `NCCL_IGNORE_CPU_AFFINITY`, `UCX_NET_DEVICES`, `NODE_IP`, …). Recipe `env` merges **last**, so it
  wins over the live InfiniBand probe and pins one machine's adapter naming; `validate` warns
  `managed-comm-env`. — src: `.swival/memory/sparkrun-notes.md:455-465`; root [`AGENTS.md`](../AGENTS.md).
- **The portability rule is broader than the managed set: *any* env value naming a host device is
  forbidden.** The concrete case is a vendor `B12X_ROCE_HCA: rocep1s0f0,roceP2p1s0f0` — not
  sparkrun-managed, so it looked acceptable, but it takes a literal HCA list and b12x's RoCEnante
  falls back to the *detected* `NCCL_IB_HCA` when unset (`roce_oneshot.py` → `discover_hcas`), so
  setting it was contraindicated. Test by grepping env **values** for device patterns
  (`rocep|enp|ens|enP|eth` + digit/f). Levers that carry no device name and are fine to set:
  `NCCL_P2P_DISABLE`, `NCCL_SHM_DISABLE`, `NCCL_PROTO`, `NCCL_BUFFSIZE`, `NCCL_MAX_NCHANNELS`. — src:
  `.swival/memory/sparkrun-notes.md:466-474`; root [`AGENTS.md`](../AGENTS.md).
- **sparkrun fills NCCL/IB env from its live probe and it is *better* than a pin** — only the ACTIVE
  ports are included, where a hand-written `NCCL_IB_HCA` silently includes a DOWN port. — src:
  `.swival/memory/sparkrun-notes.md:437-451`.
- **`HF_HOME` is likewise overridden by sparkrun** (`overridden-cache-env`); check
  `recipe validate --json` codes before shipping a recipe that "validates clean". — src:
  `.swival/memory/MEMORY.md:536-541`.
- **The HF cache is per-node: the checkpoint must be distributed to every runner node.** An omitted
  `distribution_config:` resolves to sparkrun's default (`models.enabled: true`,
  `containers.enabled: true`); a cluster profile's `distribution:` block **overrides** the recipe, so
  a stale `{enabled: false, skip_fan_out: true}` on a cluster silently strands every worker with a
  bare `missing …/config.json`. There is no CLI flag for `distribution` — hand-edit
  `~/.config/sparkrun/clusters/<name>.yaml`. — src:
  `.swival/memory/sparkrun-notes.md:476-496,417-428`; root [`AGENTS.md`](../AGENTS.md) and
  `recipes/ds4/AGENTS.md` §5 (omit the block; rely on the default).
- **`transfer_mode` semantics matter for arch and registry location**: `local` pulls the image on
  the control machine (fails for an arm64-only image when the control host is amd64, `no matching
  manifest`); `pull` had a sparkrun bug; `delegated` builds/pulls on the head node and works when
  architectures differ. — src: `.swival/memory/MEMORY.md:593-598`.
- **A recipe must not pin a `container:` without resolving the right digest.** A multi-arch image
  has an **index** digest and per-platform **manifest** digests, and Docker accepts both, so the
  wrong one looks plausible; the tag's `Docker-Content-Digest` header reports the index digest, which
  is what belongs in the pin. A mutable tag can resolve to a different commit than the pinned digest
  of the same tag — resolve the pin and compare `git log` inside each before treating two images as
  the same build. — src: `.swival/memory/sparkrun-notes.md:332-338`;
  `.swival/memory/remote-execution.md:75-94`.
- **A launcher/mod that `execve`s the engine inherits the image's baked `ENV`,** so a
  `setdefault(...)` for a var the image already bakes is a **silent no-op** (the image wins). Use
  `env.update(MY_ENV)` and keep keys disjoint from the recipe-owned ones. Corollary:
  `docker exec <c> env` is **not** a valid probe for what the launcher sets (fresh shell from the
  container's *creation* env). — src: `.swival/memory/sparkrun-notes.md:518-534`;
  `.swival/memory/MEMORY.md:115-119`.
- **A consuming image `ENTRYPOINT` blocks a sparkrun launch, and the fix is a recipe key, not a
  flag**: `executor_config: entrypoint: ""` (or `-o entrypoint=''`). A good failure — it fires
  before any GPU work. — src: `.swival/memory/MEMORY.md:568-573`.
- **`cluster_config.resolved_model_path` is wrong for an HF snapshot dir.** A snapshot is a tree of
  symlinks into `../../blobs`, so mounting only the snapshot leaves `config.json` dangling and the
  engine rejects it (`Invalid repository ID or local directory`); the managed `/cache/huggingface`
  mount is the right surface. — src: `.swival/memory/MEMORY.md:586-592`.

---

## 5. Engine flag semantics — SGLang column

The registry is mostly SGLang; these are the semantics the corpus measured, cited to the file that
recorded them. Several are lane-specific — re-verify on the pinned image before trusting a spelling.

- **`--mamba-ssm-dtype` unset reads `config.json`'s `mamba_ssm_dtype`**, which is `float32` for
  Qwen3.8-Flash-Next, so the linear-attention/GDN state pool runs fp32 by default; setting
  `bfloat16` is the single biggest memory lever (~11–22 GB/node). — src:
  `.swival/HISTORY.md:139-158`.
- **`--linear-attn-decode-backend flashinfer` is a no-op on GB10**: the auto-enable gate requires
  `is_sm100_supported()` (False on SM121, silently) **and** `mamba_ssm_dtype == bfloat16`. An
  explicit-flag guard that checks `capability[0] >= 10` passes on GB10 (12), so the flag is not
  *rejected* — it is just not auto-enabled, and no log line says so. — src:
  `.swival/HISTORY.md:292-316`; `.swival/memory/gb10-notes.md:41-55`.
- **`num_speculative_tokens` is validated against the drafter's fixed block size** (`must be
  divisible by n_predict=5`), so legal `k` is ≤5 or ×5 — which is why public DSpark sweeps show
  {2,3,5,7} and never 4 or 6. Read the constraint off the *error*, then design the sweep around it.
  — src: `.swival/memory/MEMORY.md:932-936`.
- **Accept length and throughput can point opposite ways.** `k=5` accepted more tokens/step than
  `k=3` and was still slower; the per-position acceptance curve is what shows *why* (the tail slots
  accept at 12%/5% and still cost a verify pass). Read per-position, not just the mean, and remember
  a speedup is a **profile**, not a scalar — the optimum moved with concurrency. — src:
  `.swival/memory/MEMORY.md:921-931`; `.swival/HISTORY.md` (session block).
- **`draft_tensor_parallel_size` is a first-class `SpeculativeConfig` field** ("1 or the same as the
  target TP size") — pointing it at 1 under a TP=3/TP=6 target sidesteps the drafter-divisibility
  wall. — src: `.swival/HISTORY.md:2369-2371`.
- **The bare `--cuda-graph-max-bs` does not exist in this SGLang line** — only the `-decode` and
  `-prefill` variants. — src: `.swival/HISTORY.md` (ds4 flag bundle); corroborated in the learn
  corpus.
- **fp8 KV is not automatically worth it on a sparse-attention model**: the sparse-attention index
  dtype is hardcoded (`index_state_dtype = bfloat16`) and the bytes-per-token helper takes no dtype
  parameter, so fp8 only shrinks the full-attention layers. — src: `.swival/HISTORY.md:476`.
- **`--no-ple-offload-embedding` is the right default on GB10**: on unified memory the "offloaded"
  PLE table is a pinned host copy out of the same pool, so it frees nothing and costs a host gather
  per step. — src: `.swival/HISTORY.md:174`.
- **`--moe-runner-backend auto` can resolve to a backend that cannot run, per checkpoint.** Two
  exports of "the same model" (same image digest) can disagree; `flashinfer_trtllm` is dead on this
  hardware (no SM121 cubins), so name `flashinfer_cutlass` explicitly. Do not generalise a
  backend-resolution result across exports. — src: `.swival/memory/gb10-notes.md:56-76`.
- **`mem_fraction_static = (weights + KV pool) / capacity`**, and on GB10 "available GPU memory" is
  `psutil.virtual_memory().available` (system RAM). It is relative to free memory at *each engine's
  own boot*, so stacking engines needs absolute-GiB budgeting, not summed caps; the precise pool pin
  is `--max-total-tokens`. — src: `.swival/HISTORY.md:1792-1809`.
- **Raising `MEM_FRACTION_STATIC` above ~0.80–0.85 wedges nodes on unified memory.** A `0.90` probe
  wedged three of four nodes (ping alive, SSH banner timeout) and bricked one into a manual power
  cycle. On GB10, GPU memory *is* host memory — a too-aggressive static fraction exhausts the host
  and wedges userspace. — src: `.swival/HISTORY.md:4469-4473`; `.swival/trash/…/NOTES.md` (incident).
- **`/metrics` is served on `port_base + 3`, not the API port**, and only exists if the recipe sets
  `--enable-metrics` — check the recipe, not the node. — src:
  `.swival/memory/bench-artifact-metrics.md:88-91`.
- **`#queue-req` is informative only on `Prefill batch` lines; it is always 0 on `Decode batch`
  lines** (a false null indistinguishable from a real zero — contradict any all-zero parser column
  with a bare `re.findall`). Capacity claims read decode lines, admission claims read prefill lines;
  never a bare `grep '#running-req'` (the field order differs between line types). The
  `Decode`/`Prefill` label describes the batch, not the harness phase. — src:
  `.swival/memory/queue-metrics.md:7-39`.

---

## 6. Engine flag semantics — vLLM column (from the vendored upstream corpus)

The registry runs vLLM only on a few lanes (one Ornith recipe, the Qwen3-VL embeddings/rerankers),
and those pins are **mutable nightly** tags, so treat the following as semantics, not as a fixed
version — the version for a recipe comes from its container image. Sources are upstream vLLM docs
and verbatim upstream modules under `.swival/`.

- **vLLM snapshots its environment after service init** (`enable_envs_cache()` wraps `__getattr__`
  in `functools.cache`): setting a `VLLM_*` var after the server has started has no effect. —
  src: `.swival/envs.py:2222-2240`.
- **The memory contract is `requested_memory = ceil(init_snapshot.total_memory ×
  gpu_memory_utilization)`**, and boot raises with "Decrease GPU memory utilization…" when free
  memory is short. On **integrated GPUs** (`MemorySnapshot.measure`) free memory is overridden with
  `psutil.virtual_memory().available`, because `cudaMemGetInfo` underreports on UMA — the comment
  names GH200, **DGX Spark**, and Jetson Orin, so a GB10 node's profiler sees host-available memory,
  not `cudaMemGetInfo`. — src: `.swival/worker_utils.py:533-550`; `.swival/mem_utils.py:143-151`.
- **The manual KV-pool pin is the flag `--kv-cache-memory=<bytes>`** (config field
  `kv_cache_memory_bytes`); setting it skips profiling and does **not** respect
  `--gpu-memory-utilization`. — src: `.swival/gpu_worker.py:884,547-563`.
- **Multi-node spelling differs from SGLang's.** vLLM uses `--nnodes --node-rank --master-addr
  --headless` plus `-e VLLM_HOST_IP=<node-ip>` and `--distributed-executor-backend ray|mp`; SGLang
  recipes here are driven with `--dist-init-addr`, so a vLLM recipe must not copy that. GPUDirect
  RDMA in a container needs `IPC_LOCK` and a `/dev/shm` mount (`--ipc=host --shm-size=16G`). — src:
  `.swival/doc_parallelism_scaling.md:146-158,174-200`.
- **Strategy rules**: fits one GPU → no distribution; fits one node → `tensor_parallel_size` =
  GPUs/node; too big → TP within a node plus `pipeline_parallel_size` = nodes. Nodes without NVLink
  should prefer PP over TP, and an uneven layer split also prefers PP. — src:
  `.swival/doc_parallelism_scaling.md:7-27`.
- **Sleep mode has a two-part online prerequisite** — the server must be started with
  `VLLM_SERVER_DEV_MODE=1` **and** `--enable-sleep-mode`; the endpoints only register in dev mode.
  Level 1 offloads weights to CPU RAM and discards KV; level 2 discards both. — src:
  `.swival/doc_sleep_mode.md:14-22,91-139`.
- **LoRA silent-corruption hazard**: under `--enable-mixed-moe-lora-format` vLLM trusts the caller's
  `is_3d_lora_weight` and does **not** verify the checkpoint — a wrong declaration loads into wrong
  buffers and emits garbage with no load-time error. `--max-lora-rank` must equal the maximum
  adapter rank in use (too high wastes memory and hurts performance). — src:
  `.swival/doc_lora.md:281-300,441-453`.
- **Do not cross-apply flags across engines.** The SGLang UNO draft **rejects** `--enable-lora`, and
  the vLLM memory model (`gpu-memory-utilization`, `compilation_config`) and multi-node flags differ
  from SGLang's. Pick the column that matches the recipe's `runtime:`. — src:
  `.swival/doc_conserving_memory.md:39-75`; `.swival/doc_README.md`; cross-check
  `recipes/ifm/AGENTS.md:172-175`.
- **`limit_mm_per_prompt` sets multimodal input limits**; setting a modality to `0` allocates
  nothing for it (even a text-only run of a multimodal model). — src:
  `.swival/doc_conserving_memory.md:94-160`.

---

## 7. Checkpoint and model-path mechanics

- **An HF `snapshots/<hash>` path is ephemeral** — resolve via `<repo>/refs/main` (or the newest
  snapshot carrying `model.safetensors.index.json`) and pass the repo id, never a hash. — src:
  `.swival/HISTORY.md:3184-3185,3372-3378`.
- **The HF cache is a two-level layout** (`blobs/<xx>/<sha>` written to, `snapshots/<hash>` as
  symlinks). Any mount that exposes only a `models--…` or a snapshot directory leaves symlinks
  dangling — mount the whole `hub/` directory (as the Engram packer learned). — src:
  `.swival/trash/…/KNAPCIO-SGLANG-INTEGRATION.md` (Engram packing);
  `.swival/memory/MEMORY.md:586-592`.
- **`du` on a model directory lies** because shards are symlinks into `blobs/`: measure with
  `find -L … -printf %s`. — src: `.swival/trash/…/NOTES.md`.
- **The DS4.1 checkpoint is 48 sharded safetensors plus an index**, a `config.json`, a chat
  template, and a bundled `inference/` reference runtime (with `engram.py`, `vision.py`, and image
  examples) — evidence DS4.1 is multimodal with its own reference implementation. — src:
  `.swival/ds41_tree.json`.

---

## 8. Measurement discipline before shipping a default change

Every item here is a rule the corpus learned by publishing a wrong number; [`../benchmarking/README.md`](../benchmarking/README.md)
and `recipes/qwen3/DEPTH-COST.md` carry the same doctrine in shipped form.

- **One boot cannot rank arms.** The GB10 inter-boot scatter is 7–25% (3–25% across cells); a
  `+12.6%` that looked real at `runs=3` collapsed at `runs=7`. Use ≥3 boots, a same-config control
  boot in the same window, and medians. — src: `.swival/HISTORY.md:216,618,2869`;
  `.swival/memory/measurement-hygiene.md:84-110`.
- **A noise floor belongs to a (configuration, cell) pair, never to "the boot",** and it must not be
  inferred from a comparison you already decided is null. — src:
  `.swival/memory/measurement-hygiene.md:247-264`.
- **A bench cell emits TWO records and both carry `tg_throughput`** (a context-prefill record and a
  decode record). Grouping by concurrency alone doubles the cell count and fakes bimodal boots; skip
  `is_context_prefill_phase`. Print the record count per cell before interpreting any table. — src:
  `.swival/memory/bench-artifact-metrics.md:7-26`; root [`AGENTS.md`](../AGENTS.md).
- **`pp_req_throughput` is prompt-size ÷ TTFT, not a prefill speed** (verified numerically:
  `pp_req_throughput × e2e_ttft == prompt_size`). The aggregate `pp_/tg_throughput` columns are
  windows opening at submission, so they charge scheduler queueing to a phase; use per-request
  columns for any "this phase got slower" claim. — src:
  `.swival/memory/bench-artifact-metrics.md:41-62`.
- **Prometheus gauge dicts are keyed by label set, not metric name**, so the obvious nested lookup
  returns `None` for every row; assert a nonzero before believing a zero. `spec_accept_length` is
  last-written, not a window mean; `cache_hit_rate` is 0 during pure decode. — src:
  `.swival/memory/bench-artifact-metrics.md:65-111`.
- **Provenance of an arm is several separate facts.** A run's recipe comes from *that run's*
  `recipe_qualified_name` (the `measurement_recipe_state` field is often `None`); a `declared_hash`
  is a registry-declaration hash, **not** the executed configuration; and a cross-recipe throughput
  comparison is not a knob comparison. Derive any output-file→bench-id mapping by hashing
  (`sha256(output.json) == sha256(bench_<id>/consolidated.json)`), not by recollection. — src:
  `.swival/memory/bench-artifact-metrics.md:122-146`.
- **Pass `--fresh` for any intended new measurement** (a complete bench id is re-emitted with no
  requests and exits 0 — grep the log for `re-emitting`), and give every citable run an explicit
  `--output` name (the derived filename is overwritten by the next run of the same recipe+profile).
  `runs/` is scratch and gets reaped; the `--output` file is the durable artifact and carries the
  same records. — src: `.swival/memory/measurement-hygiene.md:11-56`;
  `.swival/memory/bench-artifact-metrics.md:28-39`.
- **An `-o` override that changes nothing reads as a null result** — read the launched serve command
  and the *resolved* value of the default it is meant to beat before calling an arm neutral. — src:
  `.swival/memory/measurement-hygiene.md:111-137`.
- **Do not benchmark on a node that still has your probe containers**, and **the corpus is part of
  the measurement**: synthetic/repetitive prompts measured +25% higher speculative acceptance over
  natural ones. — src: `.swival/memory/measurement-hygiene.md:139-166`.
- **C1 is completion-length sensitive** — a varied short-answer prompt dilutes the decode rate;
  quote the steady-state C4/C8/C16 columns, and read the granted KV pool from the boot log, never
  from a computed estimate. — src: `.swival/trash/…/KNAPCIO-SGLANG-INTEGRATION.md`;
  `recipes/ds4/AGENTS.md` §10.
- **A deep prefill looks like a wedge.** A ~799K-token prompt at ~600 t/s takes 20–23 minutes,
  `/health` returns 200 while generation times out, and killing the client does not cancel the
  in-flight prefill. Distinguish busy from wedged by worker CPU ticks (`/proc/<pid>/stat`), serve-log
  progress, and load average — not by a second request. — src: `.swival/HISTORY.md:2951`;
  `.swival/memory/gb10-notes.md:187-208`.
- **A fix recorded only in prose has no guard.** A launch-killing `block_size` constraint had a
  recipe comment and a findings entry and no test; when you extend a test loop to a new input,
  inject a defect and watch the suite go red. — src: `.swival/memory/verification-discipline.md:658-675`.
- **The completion gate is "is there a boot/run behind it?", not "does the reasoning hold?"** — a
  device-free probe is necessary but not sufficient; a fix is not done until the motivating gate is
  observed closing on real hardware. — src: `.swival/memory/verification-discipline.md:817-834`.
- **Quality-battery artifacts**: thinking-ON makes reasoning models emit empty `content` on hard
  items (a max-token artifact), so run thinking-OFF; and greedy text equality is not a
  prefill-correctness gate (cold long prompts diverge run to run under bounded replay). — src:
  `.swival/trash/…/NOTES.md`; `.swival/bg/bg_bea268b2fd0d.log`.

---

## 9. Guard, test, and harness conventions

Root [`AGENTS.md`](../AGENTS.md) owns these; the corpus is where they were learned, and the
remeasurements are worth keeping:

- **The suite is plain `unittest`, not pytest**, and `tests/`/`tools/` are stdlib-only on purpose
  (they must run on a head node, in a container, or on a laptop with no venv). Dash-named tools are
  imported with `importlib.util.spec_from_file_location` and **registered in `sys.modules` before
  `exec_module`**, or `@dataclass` fails. — src: `.swival/memory/shell-command-gotchas.md:183-186`;
  `.swival/HISTORY.md` (/init block); root [`AGENTS.md`](../AGENTS.md).
- **Guard suites silently cover only the files in a roster constant.** The ds4 suite had
  `ALL = [4 sglang recipes]`, so three spelling guards passed vacuously on a new vLLM recipe;
  adding the file surfaced all three at once. When a suite grows a lane, add the lane's files to
  every roster constant and expect new failures — that is the point. — src:
  `.swival/memory/MEMORY.md:542-549`.
- **Every guard needs a proven negative control**, and a guard that has never failed a
  deliberately-broken input is untested. Mutation-verification found one guard vacuous (placeholder
  never substituted) and one firing on the recipe's own comment — guards read the *rendered*
  artifact, with whole-line comments stripped first. A negative-control anchor must be a stable key
  name, never a tunable value (`gpu_memory_utilization: 0.80` broke at the next retune). — src:
  `.swival/memory/self-check-your-own-tools.md:171-224`; root [`AGENTS.md`](../AGENTS.md).
- **Mod-local harnesses exit 2 for "harness could not run"**, so exit 2 is never a verdict on the
  patch. — src: `.swival/HISTORY.md` (/init block); root [`AGENTS.md`](../AGENTS.md).
- **No Makefile, linter, or CI**: the repo gate is `unittest discover` + `sparkrun recipe validate`
  (plain, not `--strict`) + `bash -n` on mods + `py_compile`, then remove `__pycache__`. — src:
  `.swival/HISTORY.md:856-925`; root [`AGENTS.md`](../AGENTS.md).

---

## 10. Read the corpus critically — stale claims and contradictions

This section exists because a remembered fact is the most dangerous kind. Each item was true at
some point and is now superseded, or conflicts with a shipped doc. Trust the shipped doc.

- **"The HF cache is a shared NFS mount" is stale.** Each runner node now has its own node-local
  cache and sparkrun distributes every model to each node (the cutover is dated 2026-10-03 in the
  corpus itself). Any doc or comment that still says "shared HF cache" / "NFS cache" is wrong. —
  src: `.swival/HISTORY.md` (early `/init` vs later entry); `.swival/memory/sparkrun-notes.md:498-500`;
  root [`AGENTS.md`](../AGENTS.md).
- **A flat "cap `gpu_memory_utilization` at 0.85" is superseded** by a per-lane, per-engine rule:
  the fraction is relative to free memory at that engine's boot, and on GB10 the value is a
  unified-memory hazard (§5). — src: `.swival/HISTORY.md:630,4473`; root [`AGENTS.md`](../AGENTS.md).
- **The K2-Horizon MoVA-36B sub-lane is withdrawn.** The corpus treats it as an active shipped lane;
  the current tree carries it under `attic/ifm/` and it is no longer auto-discovered. Any "ship it"
  framing is stale. — src: `.swival/HISTORY.md:1724-1811`; root [`AGENTS.md`](../AGENTS.md).
- **A mod's `MOD_TIMEOUT` does not bound the hook** — the runtime enforces a hard 600 s pre-exec
  timeout on top, which `MOD_TIMEOUT` cannot extend (§3). — src: `.swival/HISTORY.md:933,4844`.
- **`distribution_config.models.enabled: true` (memory) vs "omit the `distribution_config:` block"
  (recipes/ds4/AGENTS.md §5) name opposite actions but are behaviourally equivalent** when relying
  on sparkrun's default. Prefer the shipped doc's "omit the block". — src:
  `.swival/memory/MEMORY.md:110-113` vs `recipes/ds4/AGENTS.md`.
- **`runs/*.json` vs the `--output` file**: [`../benchmarking/README.md`](../benchmarking/README.md)
  says to read `runs/*.json`; the corpus says `runs/` is scratch and reaped, and the durable
  citation is the `--output` file (which carries the same records). Hold both: read `runs/` while it
  exists, but cite the `--output` file for anything you may need later. — src:
  `.swival/memory/bench-artifact-metrics.md:28-39`.
- **`recipe validate` as the gate does not prove a recipe launches** — it does not resolve mods
  (§2). A green gate plus a clean dry-run is still not a boot. — src: `.swival/memory/MEMORY.md:526`.
- **Recipe counts in the corpus are stale.** `HISTORY.md` records the ds4 set changing repeatedly
  (EXL3 removal, TP=6 additions, SGLang removals, then new Knapcio/TensorFold lanes). Re-list
  `recipes/*/*.yaml` before trusting a count. — src: `.swival/HISTORY.md` (multiple session blocks);
  root [`AGENTS.md`](../AGENTS.md).
- **`sparkrun-notes.md:208-210` says recipe v2 top-level keys are `name`, `defaults`, `environment`,
  `command`, `mods`** — this conflicts with the shipped grammar, where `name:` is banned and the env
  block is top-level `env:`. The specific line is stale; the surrounding placeholder/defaults rules
  in that file are correct. — src: `.swival/memory/sparkrun-notes.md:208-210` vs root
  [`AGENTS.md`](../AGENTS.md).

---

## 11. How to update this document

- The corpus is git-ignored, so nothing here is re-derivable by a reader; if a fact changes, change
  it **here** rather than re-mining `.swival/`.
- Before publishing a number from §4, §5, or §8, re-read the artifact that contains it in the same
  turn (the corpus's own verification rule). Absence of a result is a result and gets written down
  as one.
- When a lane ships a new rule, add it to the lane `AGENTS.md` first; this document is the
  long-form evidence and the cross-engine (vLLM) reference, not the place for a new invariant.
- Keep hostnames and internal addresses out of this file — it is tracked and the registry is
  distributed to third parties.

### Provenance

Compiled 2026-10-09 by orchestrating parallel reads of the whole `.swival/` tree
(`memory/*.md`, `doc_*.md`, `serve_args.md`, `envs.py`/`gpu_worker.py`/`worker_utils.py`/`mem_utils.py`,
`tree_main.json`, `ds41_tree.json`, `HISTORY.md`, `trash/**`, `bg/*.log`). Spot-checked citations
against the corpus at write time; facts that disagree with a shipped doc are flagged in §10 rather
than silently reconciled.
