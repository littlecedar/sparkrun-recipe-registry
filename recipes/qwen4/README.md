# Qwen3.8-Flash-Next (`qwen4`) — serving recipes

Serving recipes for **Qwen3.8-Flash-Next**, a 180B MoE (48 decoder layers, 512 routed experts,
10 active per token) with hybrid Gated DeltaNet + Qwen Sparse Attention (QSA) plus PLE n-gram
tables, on DGX Spark (GB10). This directory is the `qwen4` model family (`model_symbol: qwen4`).

The lane ships **exactly two production recipes** after the 2026-10-14 cut: the fastest **TP=1** and
the fastest **TP=2** arm of the six that used to live here, both serving the same checkpoint,
[`local-inference-lab/Qwen3.8-Flash-Next-NVFP4`](https://huggingface.co/local-inference-lab/Qwen3.8-Flash-Next-NVFP4)
(a QAD NVFP4/MXFP8 export; **licence: Qwen Community License 1.0**, `qwen-community-1.0`). Everything
else — lane state, measurement histories, negative results, the archived arms and their provenance —
lives in [`../../attic/qwen4/`](../../attic/qwen4/) (see [Attic index](#attic-index)).

## Contents

- [TP=2 — labquant balanced base (SGLang, 2 nodes)](#tp2--labquant-balanced-base-sglang-2-nodes)
- [TP=1 — solo vLLM (1 node)](#tp1--solo-vllm-1-node)
- [Attic index](#attic-index)

## TP=2 — labquant balanced base (SGLang, 2 nodes)

| | |
|:--|:--|
| Recipe | `qwen3.8-flash-next-nvfp4-labquant-sglang.yaml` |
| Engine | SGLang — `lmsysorg/sglang:dev-cu13-qwen38-next-local` @ `sha256:9d2a843c…` (digest-pinned) |
| Model | [`local-inference-lab/Qwen3.8-Flash-Next-NVFP4`](https://huggingface.co/local-inference-lab/Qwen3.8-Flash-Next-NVFP4), MXFP8 attention/GDN + FP8 PLE |
| Checkpoint pin | `model_revision: 6c01ac378d22…` (step-5500 QAD revision, `main` since 2026-10-06) — 43 shards / ~106.3 GB |
| Nodes | 2 (TP=2) |
| Context | 262,144 tokens (`max_model_len`) |
| Spec decode | NEXTN — 3 steps / topk 1 / 4 draft tokens, `decode` attention mode |
| Memory | `gpu_memory_utilization: 0.80`, mamba pool 112 (`max_mamba_cache_size`), `max_num_seqs: 24` |
| Tags / vision | `lcg_favorite, fast, vision` — this export serves **text and vision** (BF16 vision tower) |
| Licence | Qwen Community License 1.0 (`qwen-community-1.0`) |

**Mod chain (6, ordered — `mods:` is a dependency chain, not a set).** Weights are served from the
mod-built `/cache/runtime/labq-patched` tree, not the raw HF snapshot.

1. `@eugr/mods/drop-caches` — frees page cache before load.
2. `recipes/qwen4/mods/fix-labquant-modelopt-mixed-flat-schema` — **must be first**: builds
   `/cache/runtime/labq-patched`, a symlink tree over the snapshot with one patched `config.json`, so
   SGLang's `modelopt_mixed` loader accepts the checkpoint.
3. `recipes/qwen4/mods/unpack-labquant-ple-nvfp4-to-fp8` — rewrites the 128 PLE n-gram shards in that tree from
   packed NVFP4 to plain fp8 e4m3 and sets `ple_embedding_dtype: float8_e4m3fn`, so the engine uses
   its own tested fp8 PLE path (cold cost 51.2 GB / ~50 s per node; pairs with
   `--no-ple-offload-embedding`).
4. `recipes/qwen4/mods/diag-qwen4-unplaced-scales` — **diagnostic only**: logs which `_scale` was unplaceable in
   front of the assert at `qwen4_exp.py:2136`; changes no control flow.
5. `recipes/qwen4/mods/fix-labquant-mxfp8-weight-scale-name` — renames the export's `<X>.weight_scale` to the
   engine's `weight_scale_inv` for the MXFP8 shared experts/attention indexer, so the load guard does
   not mistake a differently-suffixed scale for a dropped one.
6. `recipes/qwen4/mods/demote-labquant-narrow-mxfp8-to-bf16` — **must be last**: demotes the 72 narrow
   `in_proj_a`/`in_proj_b` MXFP8 tensors (n=96/rank, under CUTLASS's MXFP8 floor of 128) to BF16.

**Two mandatory engine flags** live in `defaults.extra_args`, not as tunables:
`--moe-runner-backend flashinfer_cutlass` (with `auto`, the NVFP4 MoE resolves to
FLASHINFER_TRTLLM, dead on SM121) and `--cuda-graph-backend-prefill disabled` (else prefill
CUDA-graph capture raises).

**Mod-tree mechanics.** `served_model_dir` points at `/cache/runtime/labq-patched` — the symlink tree
`fix-labquant-modelopt-mixed-flat-schema` builds over the HF snapshot on every node (the raw snapshot
is never modified). Bypassing the mod (`--skip-run` against a container that never ran it) leaves that
tree absent. Cold costs: the `unpack` mod rewrites the 128 PLE shards in that tree in ~50 s / 51.2 GB
per node; the `demote` mod adds +0.14 MB of weights per node. `extra_args` is the recipe's only escape
hatch — `sparkrun benchmark` silently drops trailing `EXTRA_ARGS`, so an un-parameterised flag cannot
be injected from the command line, which is why the two mandatory flags live in `defaults`.

The two `fastsafetensors` mods are **deliberately absent** even though the parent recipe lists them:
this recipe uses `load_format=safetensors`, so they accomplish nothing — and worse, they exec as root
and leave a root-owned `flashinfer_jit.log` in the persisted per-model runtime cache, making the first
launch of a new model key die as uid 1000 with a sticky `PermissionError`. Re-add them only if you set
`load_format=fastsafetensors` (mechanism + `reown` fix: `recipes/cybersec/mods/fix-fastsafetensors-tp2-sglang/run.sh`).

**Knobs that are answered — do not re-litigate.** `kv_dtype: fp8_e4m3` is a config-level NO (boots,
allocates, then dies in SM121 QSA decode). `chunked_prefill_size 8192` regresses k=8/k=16 on this
checkpoint; keep 4096. `max_num_seqs` must stay strictly above every served `k`, and the real
admission ceiling is the **mamba pool** (`max_mamba_cache_size // 4` on the lazy strategy: 112 → 28).
`skip-labquant-vision-tower` is deliberately absent on this revision (the step-5500 tower is BF16 and
already inside `quantization_config.ignore`), which is why this recipe serves vision.

Pin key trap: the pin key is `model_revision:`, **not** `revision:` — a bare `revision:` is silently
ignored. Do not unpin: `main` has moved under us twice.

## TP=1 — solo vLLM (1 node)

| | |
|:--|:--|
| Recipe | `qwen3.8-flash-next-nvfp4-solo-vllm-b12x.yaml` |
| Engine | vLLM — `ghcr.io/spark-arena/dgx-vllm-eugr-nightly-b12x:latest` (floating tag; the b12x build publishes no digest-pinnable alias, so a measured number is tied to whatever the tag resolved to) |
| Model | [`local-inference-lab/Qwen3.8-Flash-Next-NVFP4`](https://huggingface.co/local-inference-lab/Qwen3.8-Flash-Next-NVFP4) — same checkpoint as the TP=2 recipe |
| Checkpoint pin | none — serves `main` (the step-5500 QAD hybrid export) |
| Nodes | 1 (TP=1, `max_nodes: 1`) |
| Context | 262,144 tokens (`max_model_len`) |
| Spec decode | MTP — `num_speculative_tokens: 4` |
| Memory | `gpu_memory_utilization: 0.8`, `max_num_seqs: 8`, `kv_cache_dtype: fp8` |
| Tags / vision | `lcg_favorite` — no `vision` tag; metadata describes the text TP=1 route |
| Licence | Qwen Community License 1.0 (`qwen-community-1.0`) |

**The PLE knob.** The ~47.7 GiB FP8 PLE n-gram table — not weights + KV — is the component that does
not fit one Spark's unified pool, so this recipe keeps it **off the device** with
`env: VLLM_PLE_TABLE_MEMORY=disk` (mmap/pread per step); the rest of the server config is the TP=2
shape at `--tp 1`. SGLang's equivalent route (`--ple-offload-embedding --ple-offload-backend file`)
is archived.

**Couplings.** `max_num_seqs` stays at 8 because with MTP k=4 the GDN mamba state pool binds
concurrency (the eugr solo cell ships 8 too). `CUTE_DSL_ARCH` is omitted — the platform tier already
publishes `sm_121a` for vLLM on DGX Spark.

## Attic index

Everything below is under [`../../attic/qwen4/`](../../attic/qwen4/) and is the lane's evidence
record: lane state, constraints, guards, measurement histories, negative results and archived arms.
Cite it rather than the lane README for anything historical.

| entry | what it holds / what question it answers |
|---|---|
| [`AGENTS.md`](../../attic/qwen4/AGENTS.md) | The lane's condensed operating guide — mission and current state, where the evidence lives, hard constraints, the parallel workstream plan (W1–W15), coordination protocol, runbook, the traps that cost the most, sprawl policy, the validation ritual, and the recipe-comment evidence moved out of the YAMLs. Its `§N` numbering is kept so `§N` citations still resolve. Ends with the material cut from the lane README on the 2026-10-14 rewrite. |
| [`NOTES.md`](../../attic/qwen4/NOTES.md) | One-page, kept-current state-of-play: the two shipped recipes, the cut evidence, cache hygiene, the re-verified mod chain, open workstreams, the next-cheapest checks, and the do-not-re-derive list. |
| [`SELECTION-RANKING.md`](../../attic/qwen4/SELECTION-RANKING.md) | Tracked snapshot of the 2026-10-10 cross-lane selection-ranking draft plus the 2026-10-11 and 2026-10-14 deltas — how the six qwen4 arms ranked and why the cut kept these two. |
| [`ARMS-MANIFEST.md`](../../attic/qwen4/ARMS-MANIFEST.md) | Provenance table for every archived recipe under `arms/` (parent, one-line delta, why archived), grouped in harvest waves. |
| [`arms/`](../../attic/qwen4/arms/) | Every non-production qwen4 recipe (29 YAMLs): the other four cut-window arms (`…-highcon-`, `…-longctx-`, the RadixArk `…-nvfp4-sglang` and its `…-nvidia-sglang` sibling, the solo SGLang `…-solo-sglang`), contributor recipes (`eugr-`, `ursuciprian-`), the cross-runtime `…-vllm` recipe, the never-benchmarked TP=4 attempt, and the `zz-*` instrumented/bisect arms. |
| [`status/`](../../attic/qwen4/status/) | Status memos: `W3-QUALITY-EVAL-PLAN.md` / `W3-QUALITY-EVAL-STATUS.md` (the 38-task battery), `W4-GATE-STATUS.md` (#37111 silent-decode-corruption gate), `W8-UPSTREAM-DRAFTS.md` (unposted upstream drafts), `W14-LABQUANT-5500-MOD-PLAN.md` (the re-pin mod verification). |
| [`mods/fix-labquant-expert-input-scale/`](../../attic/qwen4/mods/fix-labquant-expert-input-scale/) | Archived mod variant kept with the lane record. |
