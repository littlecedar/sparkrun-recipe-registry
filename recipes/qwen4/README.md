# Qwen3.8-Flash-Next (`qwen4`) — serving recipes

Serving recipes for **Qwen3.8-Flash-Next**, a 180B MoE (48 decoder layers, 512 routed experts,
10 active per token) with hybrid Gated DeltaNet + Qwen Sparse Attention (QSA) plus PLE n-gram
tables, on DGX Spark (GB10). This directory is the `qwen4` model family (`model_symbol: qwen4`).

The lane ships **two production recipes** after the 2026-10-14 cut: the fastest **TP=1** and
the fastest **TP=2** arm of the six that used to live here, both serving the same checkpoint,
[`local-inference-lab/Qwen3.8-Flash-Next-NVFP4`](https://huggingface.co/local-inference-lab/Qwen3.8-Flash-Next-NVFP4)
(a QAD NVFP4/MXFP8 export; **license: Qwen Community License 1.0**, `qwen-community-1.0`) — plus one
**revived, not-yet-measured** TP=2 high-concurrency arm (2026-10-15) that holds the
aggregate-throughput regime the cut left in the attic. Everything else — lane state, measurement
histories, negative results, the archived arms and their provenance — lives in
[`../../attic/qwen4/`](../../attic/qwen4/) (see [Attic index](#attic-index)).

## Contents

- [TP=2 — labquant balanced base (SGLang, 2 nodes)](#tp2--labquant-balanced-base-sglang-2-nodes)
- [TP=2 — labquant high-concurrency arm (SGLang, 2 nodes, unmeasured)](#tp2--labquant-high-concurrency-arm-sglang-2-nodes-unmeasured)
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
| Decode ladder (2026-10-18) | **C1 39.90 ± 1.48 · C2 69.45 ± 7.85 · C5 94.98 ± 8.97 · C10 104.45 ± 3.00 t/s** @ d0, pp 2048, tg 128, n=5 per cell, decode rows read from the `--output` file — `bench_684c21a7cd8a`, receipt `~/benchmarks/qwen4-tp2-20261018/b1-cutlass-concurrency-ladder.{yaml,json}`. C1 reproduces the 2026-10-14 baseline (40.32 ± 1.94) inside the cell σ; per-request decode falls to 36.93 / 25.34 / 15.78 t/s at c2/c5/c10 while the aggregate rises, so the arm's value is concurrency, not single-stream. A same-boot d0 k8 cell reads 121.21 ± 3.82 t/s aggregate. Not measured on that boot: d8192 (the `depth8k-c8` twin was wired for the paused arms) |
| Tags / vision | `lcg_favorite, vision` — this export serves **text and vision** (BF16 vision tower) |
| Suite (2026-10-19 boot) | eval-suite `ok`: contract ok (`max_model_len=262144`, ready, `finish=stop`) · house 19/19 + 18/18 · needle 3/3 at 32k, 128k, 262k · hard ARC 95.5 % (n=200) / GSM8K 95.5 % (n=200) — `suite/` in receipt `~/benchmarks/qwen4-labq-suite-20261018/` |
| Tool calling (2026-10-19 boot) | `tool-eval-bench` v2.6.0 `standard-suite`: **score 100 — 15/15 scenarios pass, 0 partial, 0 fail** (91.6 s) — `teb.yaml` (`bench_eff75293e461`) in the same receipt |
| W4 release soak (`#37111`, 2026-10-19) | **PASS** — 90 min at 100k depth, 708 turns: **0 degeneration / 0 truncation findings, 0 transport errors**; the warm==cold canary agrees (4183) after a cache flush. The gate sends `enable_thinking: false` (its client contract on this thinking-default template), `max_tokens` 512, essay 2048. Wall 5,491 s; `gate-37111.json` + `gate-37111.log` in the same receipt. A PASS is a negative result — read `tools/gate-37111-design.md` §"what a PASS proves" |
| License | Qwen Community License 1.0 (`qwen-community-1.0`) |

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

**Two engine flags** live in `defaults.extra_args`, not as tunables:
`--moe-runner-backend flashinfer_cutlass` (with `auto`, the NVFP4 MoE resolves to
FLASHINFER_TRTLLM, dead on SM121) and `--cuda-graph-backend-prefill disabled`. The second is redundant
on this image but harmless: the vision tower makes the engine disable prefill graphs itself
(`cuda_graph_config` resolves `prefill.backend='disabled'`), so removing the flag does not enable them
and there is no bs>1 cost to recover
(`~/benchmarks/qwen4-knobs-20261019/b3-prefillgraph/`).

**One knob is answered negative:** `--enable-int8-mamba-checkpoint` cannot boot this export. The
default 224-slot pool needs 3.24 GB against 2.15 GB free at `gpu_memory_utilization: 0.80`, and a
112-slot retry raises `ValueError: --enable-int8-mamba-checkpoint is incompatible with Qwen4-Exp PLE
side states` (`memory_pool.py:1337`) — no size fits. Receipts
`~/benchmarks/qwen4-knobs-20261019/b2-int8mamba/` and `b2b-int8mamba-112/`.

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
`load_format=fastsafetensors` (mechanism + `reown` fix: `mods/fix-fastsafetensors-tp2-sglang/run.sh`).

**Knobs that are answered — do not re-litigate.** `kv_dtype: fp8_e4m3` is a config-level NO (boots,
allocates, then dies in SM121 QSA decode). `chunked_prefill_size 8192` regresses k=8/k=16 on this
checkpoint; keep 4096. `max_num_seqs` must stay strictly above every served `k`, and the real
admission ceiling is the **mamba pool** (`max_mamba_cache_size // 4` on the lazy strategy: 112 → 28).
`skip-labquant-vision-tower` is deliberately absent on this revision (the step-5500 tower is BF16 and
already inside `quantization_config.ignore`), which is why this recipe serves vision.

Pin key trap: the pin key is `model_revision:`, **not** `revision:` — a bare `revision:` is silently
ignored. Do not unpin: `main` has moved under us twice.

## TP=2 — labquant high-concurrency arm (SGLang, 2 nodes, unmeasured)

| | |
|:--|:--|
| Recipe | `qwen3.8-flash-next-nvfp4-labquant-highcon-sglang.yaml` |
| Engine | SGLang — `lmsysorg/sglang:dev-cu13-qwen38-next-local` @ `sha256:9d2a843c…` (digest-pinned) |
| Model | [`local-inference-lab/Qwen3.8-Flash-Next-NVFP4`](https://huggingface.co/local-inference-lab/Qwen3.8-Flash-Next-NVFP4) — same checkpoint, mod chain and engine as the balanced base |
| Checkpoint pin | `model_revision: 6c01ac378d22…` (step-5500 QAD revision, `main` since 2026-10-06) |
| Nodes | 2 (TP=2) |
| Context | 262,144 tokens (`max_model_len`) |
| Spec decode | NEXTN — 3 steps / topk 1 / 4 draft tokens, `decode` attention mode |
| Memory | `max_mamba_cache_size: 128` + `max_num_seqs: 32` (base: 112 / 24) — ~+0.85 GB/rank, ~−4.55% KV |
| Tags / vision | `lcg_favorite, vision` |
| License | Qwen Community License 1.0 (`qwen-community-1.0`) |

Revived 2026-10-15 from [`../../attic/qwen4/arms/…-highcon-sglang.yaml`](../../attic/qwen4/arms/) —
the only archived arm holding the **aggregate-throughput regime**. It differs from the balanced base
in exactly two defaults: the mamba pool (112 → 128) and `max_num_seqs` (24 → 32), which lifts the real
admission ceiling from 28 to 32 (`max_mamba_cache_size // 4` on the lazy strategy). `max_num_seqs` must
stay strictly above every served `k` — at `k == cap` the batch saturates at `cap − 1` with one request
queued and per-request decode loses ~6%. Aggregate decode peaks at **k=16** and cliffs at k=24
(measured 89.1 → 72.9 t/s, the paragraph below), so use this arm to serve batches, not to chase
single-stream latency. Everything else is the base: same pin, same six-mod chain (the archived arm's
`skip-labquant-vision-tower` is dropped — the step-5500 tower is BF16 and already inside
`quantization_config.ignore`, which is why this recipe serves vision), same two mandatory flags in
`defaults.extra_args`.

```bash
sparkrun run recipes/qwen4/qwen3.8-flash-next-nvfp4-labquant-highcon-sglang.yaml -H <node-a>,<node-b>
```

**Measured 2026-10-15** on the pinned engine, one boot, `llama-benchy` at d=8192 / 128 output
tokens / 7 samples per cell (`~/benchmarks/qwen4-highcon-20261015/`, job
`1895030211ea0500_3510a5e0d37d`): aggregate **decode 84.9 / 89.1 / 89.1 / 72.9 t/s at k=8 / 12 / 16 /
24** — flat from k=12 to k=16, then −18 % at k=24 — with time-to-first-response 5.8 / 7.7 / 9.8 /
15.6 s and ~3.05–3.06 k t/s in the prefill phase at every k. The engine admitted it without clamping
(`max_total_num_tokens=1,567,360`, `max_running_requests=32`, `context_len=262144`, mamba pool 128
slots), so the k=24 fall-off is not a pool or request cap. Not measured: the standard ladder's C1–C10
cells (this sweep is one depth), and any comparison against the balanced base at this depth — the
archived arm's C1 cells (40.10 ± 2.44 d=0, 41.92 ± 5.28 d=8192) were taken on the superseded
`7c4f1bc1` revision and stay history. If the launch dies in `alloc_memory_pool`, fall back to the
balanced base (pool 112 / cap 24).

## TP=1 — solo vLLM (1 node)

| | |
|:--|:--|
| Recipe | `qwen3.8-flash-next-nvfp4-solo-vllm-b12x.yaml` |
| Engine | vLLM — `ghcr.io/spark-arena/dgx-vllm-eugr-nightly-b12x@sha256:cf5a2a53…` (**digest-pinned 2026-10-16**; the earlier note here said the b12x build published no digest-pinnable alias — that was wrong: the tag is a single-platform manifest whose digest resolves, verified by `docker manifest inspect <ref>@<digest>` and by matching the manifest's config digest to the container's image ID. The relay-imported image carries no `RepoDigests`, which is why `docker images --digests` showed `<none>` and the digest had to come from `docker buildx imagetools inspect`) |
| Model | [`local-inference-lab/Qwen3.8-Flash-Next-NVFP4`](https://huggingface.co/local-inference-lab/Qwen3.8-Flash-Next-NVFP4) — same checkpoint as the TP=2 recipe |
| Checkpoint pin | `model_revision: 6c01ac378d22f6652c9f392c87700496eca8e5dc` — the `main` SHA on 2026-10-18, uploaded 2026-10-06, i.e. the step-5500 QAD hybrid export. Sparkrun downloads by SHA and rebinds `{model}` to `…/snapshots/6c01ac37…` (the launch's `_prepared_model_path`), so nothing resolves through `refs/`; `command:` still passes no `--revision` |
| Nodes | 1 (TP=1, `max_nodes: 1`) |
| Context | 262,144 tokens (`max_model_len`) |
| Spec decode | MTP — `num_speculative_tokens: 4` |
| Memory | `gpu_memory_utilization: 0.8`, `max_num_seqs: 8`, `kv_cache_dtype: fp8` |
| Tags / vision | `lcg_favorite` — no `vision` tag; metadata describes the text TP=1 route |
| Decode ladder (2026-10-18) | **C1 34.04 ± 2.84 · C2 55.49 ± 1.88 · C5 64.61 ± 1.92 · C10 62.04 ± 1.00 t/s** @ d0, pp 2048, tg 128, n=5, decode rows read from the `--output` file — `bench_6b35f675861a`, receipt `~/benchmarks/ladders-solo-20261018/qwen4-solo-ladder.yaml` |
| Suite (same boot) | eval-suite `ok`: contract ok (`max_model_len=262144`, ready, `finish=stop`) · house 19/19 + 18/18 · needle 3/3 at 32k, 128k, 262k · hard ARC 95.5 % (n=200) / GSM8K 94.5 % (n=200) — `qwen4-solo-suite/` in the same receipt |
| License | Qwen Community License 1.0 (`qwen-community-1.0`) |

**The PLE knob.** The ~47.7 GiB FP8 PLE n-gram table — not weights + KV — is the component that does
not fit one Spark's unified pool, so this recipe keeps it **off the device** with
`env: VLLM_PLE_TABLE_MEMORY=disk` (mmap/pread per step); the rest of the server config is the TP=2
shape at `--tp 1`. SGLang's equivalent route (`--ple-offload-embedding --ple-offload-backend file`)
is archived.

**Couplings.** `max_num_seqs` stays at 8 because with MTP k=4 the GDN mamba state pool binds
concurrency (the eugr solo cell ships 8 too). `CUTE_DSL_ARCH` is omitted — the platform tier already
publishes `sm_121a` for vLLM on DGX Spark.

**Ladder shape.** C10's aggregate lands below C5 because `max_num_seqs: 8` binds at ten streams — the
serve log shows `Running: 8 reqs, Waiting: 2 reqs` — not because the pool is short: the engine
granted `14.48 GiB` of KV = `770,455` tokens = `2.94x` at 262,144. The boot was cold, TTR 784.6 s
port-open (`init engine … 689.80 s` under b12x autotune).

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
