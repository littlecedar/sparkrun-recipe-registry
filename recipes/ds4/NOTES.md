# ds4 — TensorFold TP=2 lane work notes

**Goal:** consolidate BertholomusAI's TensorFold TP=2 research for DeepSeek-V4.1-Flash
into a sparkrun recipe: Dockerfile → build → push → recipe → README/AGENTS/guards.
**Target nodes:** trial on 10.0.4.34 / 10.0.4.35. Head = 10.0.4.30 (operate cluster;
NOT a workload node). Restricted: .30/.31/.32/.33.

## Deliverables — status

| Deliverable | State | Evidence |
|:--|:--|:--|
| Recon all 3 sources | DONE | NOTES "Source facts"; §12.14 refs |
| Dockerfile for the engine | DONE | `recipes/ds4/Dockerfile.tensorfold-dsv41` |
| Image built + pushed | DONE | digest below, on .30/.34/.35 |
| Recipe (house ds4 naming) | DONE | `deepseek-v4.1-flash-tensorfold-tp2-sglang.yaml` |
| README brief | DONE | README.md "TensorFold TP=2 lane" |
| AGENTS docs | DONE | AGENTS.md §12 (13 subsections) |
| Guard test | DONE | `tests/test_ds4_recipes.py::TensorfoldLaneContract` (21 tests, incl. negative controls) |
| Real trial boot | **DONE — boot-verified** | cold + warm, real inference; see "Trial boot" below |
| NOTES maintained | DONE | this file |

## Verified facts (this session, by direct inspection)

- **Image** `littlecedar/dgx-spark-dsv41:tensorfold-tp2`, id `788c36544f1e`, 33.8 GB,
  built 2026-10-05. `docker inspect` RepoDigest =
  `sha256:fabbe8615bb91c61fdde4a5f451f324a7449d7335fb85d453cc439985c525495`
  → **exactly matches** the recipe's `container:` pin. Present on .30, .34, .35.
  `tensorfold --version` = 0.6.3; importable at `/opt/sglang/.../tensorfold`.
- **Engine CLI** (`tensorfold serve --help`, read in the image) accepts every flag the
  shim emits: `--tp {1,2}`, `--rank {0,1}`, `--master`, `--master-port`, `--parallel`,
  `--mtp-drafts`, `--context`, `--temperature`, `--no-update-check`, `--name`.
- **Checkpoint** `Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw`: public, `quant_method:
  exl3`, 49 files, 196.2 GiB. **Fully present on both .34 and .35** (39 shards,
  210,600,939,078 bytes, `bad=0` structural check). NB the dir size reads as 6.5 MB
  because shards are symlinks into `~/.cache/huggingface/hub/blobs/XX/…`; measure with
  `find -L … -printf %s`, not `du` on the model dir.
- **Engram**: 189.1 GiB (203 GB) already staged at `~/.cache/huggingface/hub/dsv41-engram/` on
  both trial nodes (shards 47/48 of the official repo; 101.5 + 101.5 GB).
- **`sparkrun show`** parses the recipe; **`sparkrun run --dry-run`** renders the full
  serve command and a clean 2-node cluster plan; mods/image/model distribution all resolve.
- **Shim mapping** proven by executing `main()` with `os.execvp` stubbed:
  `--dist-init-addr 10.0.4.34:25000` → `--master 10.0.4.34 --master-port 25000`,
  `--node-rank 1` → `--rank 1`, plus TF_DS_REPLAY/… env.

## Source facts (from the three sources)

- Model: DeepSeek-V4.1-Flash 552B; 40 layers, d=5120, MoE 384 routed (top-6). Two Engram
  tables ≈ 203 GB (FP8 rows of 256, E8M0 scale/32).
- Bertholomus serves the EXL3 2.9bpw checkpoint (engine reads EXL3 only; `QUANT_METHODS
  = {"cuda": ("exl3",)}`). Engram comes from official shards 47/48.
- Engine: `bertholomus/TensorFold @ deepseek-v41-tp2`, fork of ashhart/TensorFold v0.6.3
  (Apache-2.0), family `deepseek_v41`. Pinned in the Dockerfile at
  `d5d7bb389ddf4325c1edf4a15dd1c23727040ea1`.
- Per-rank ≈ 99 GiB (EXL3) + KV + workspace → fits 128 GB. Measured (upstream): C1 101
  code / 62 prose / 142 structured t/s; 4 streams 112 t/s; warm start-to-ready 36 s.

## Design decisions (settled)

- **Runtime:** `runtime: sglang` + a mod-shim (`tensorfold-dsv41-launcher`) that consumes
  sparkrun's `--dist-init-addr/--nnodes/--node-rank` and execs `tensorfold serve`. This is
  the house pattern (same as the knapcio lane). An unknown `runtime:` name is fatal at
  launch; a custom out-of-tree `RuntimePlugin` would need `plugins.paths` on every node.
- **Image:** base `lmsysorg/sglang:dev-cu13` (arm64); `pip install --no-deps` the pinned
  fork ref; digest-pinned in the recipe. arm64/GB10 only.
- **Two load-bearing shim behaviours:** pass `--dist-init-addr`'s port through to
  `--master-port` (else the head opens 29551 while sparkrun polls 25000 → dead launch);
  set `--rank` from `--node-rank` (the env carries no rank).

## Trial boot (VERIFIED 2026-10-05)

The recipe **booted and served**. `sparkrun run` on .34/.35 completed all 6 phases; both ranks
loaded and rank 0 served on `0.0.0.0:8000`. Boot gates observed, in order:

1. `[tensorfold-dsv41-launcher] overlay gate OK`, `tensorfold: /opt/sglang/bin/tensorfold 0.6.3`.
2. `Engram: 2 shard(s) at /cache/huggingface/hub/dsv41-engram` (the mod found them).
3. `[tensorfold] loading DeepSeek-V4.1-Flash … on CUDA, rank 0 of 2` / `rank 1 of 2` — ranks differ.
4. Per-rank weights: `rank 0: weights in 299 s (written to the rank cache)` (98.8 GiB);
   `rank 1: 312 s` (95.3 GiB → 98.8 GiB). Rank-cache files ~106 GB each.
5. `building CUDA extension tensorfold_rdma_gather_v5` … (first boot only).
6. `rank 0: allocator ceiling 107.1 GiB` / `rank 1: 107.8 GiB`.
7. `[tensorfold] DeepSeek-V4.1 engine ready: 2 rank(s), context 262144, DSpark 5 drafts`.
8. `serving DeepSeek-V4.1-Flash at http://0.0.0.0:8000/v1 … loaded in 511.3s` (rank 1 ready 507 s).

The serve command inside the container is exactly the designed mapping:

```
tensorfold serve <snapshot> --tp 2 --rank 0 --host 0.0.0.0 --port 8000 --context 262144
  --parallel 4 --mtp-drafts 5 --temperature 0 --no-update-check --name DeepSeek-V4.1-Flash
  --master 10.0.4.34 --master-port 25000
```

**Cold boot ≈ 511 s** engine-load (rank-cache write + first-boot CUDA-extension compile);
`/v1/models` returns the model and `/v1/chat/completions` returns real text. First-ever launch
additionally pays a one-time 510 s model sync head→worker (see block 5).

### Warm boot (rank-cache reuse) — VERIFIED

Restarting the same workload on the same nodes:

| | cold (first ever) | warm (rank cache present) |
|:--|--:|--:|
| rank 1 weight load | 312 s (wrote 106 GB cache) | **25 s (from the rank cache)** |
| rank 1 ready | 507 s | **43.3 s** |
| sparkrun TTR (port open) | ~511 s engine load | **51.4 s** |
| HTTP-ready / TTFT | — | 51.46 s / 51.63 s |

So the shipped shim's `TF_DS_RANK_CACHE` under `/cache/runtime/tensorfold/rank-cache` is doing
exactly what it is for: a warm boot is ~10× faster on the weight-load step. `/cache/runtime` is
sparkrun's managed runtime cache and survives container replacement, so the cache persists across
`sparkrun stop`/`run`.

### Our own measurement (not upstream's)

A single greedy request, mixed code/prose prompt, `temperature=0`:

| Metric | Value |
|:--|:--|
| prompt / completion | 288 / 256 tokens |
| decode | **73.0 tok/s** (`completion_tokens / decode_s`, 3.51 s) |
| prefill | 305 tok/s — a 288-token prompt is overhead-dominated; NOT a prefill benchmark |
| DSpark | 95 rounds, drafted 262, accepted 160 → **mean 2.76 tokens/round** (healthy, >1) |
| finish | `length` (hit max_tokens) |

73 tok/s sits inside upstream's 62 (prose) – 101 (code) t/s band, as a mixed prompt should. The
DSpark mean acceptance of 2.76 is the "speculation is working" signal the boot gate asks for.

### Blocks and their fixes, learned the hard way

1. `sparkrun status`/`metrics` need `-H`. Use `-H 10.0.4.34,10.0.4.35`.
2. `@littlecedar/mods/...` (an **explicit-scoped** ref) resolves ONLY via the registry cache on
   the head — the adjacent-to-recipe rule is *skipped* for explicit scoped refs, and there is no
   CLI override. Consequences:
   - Until the repo is pushed, `sparkrun run recipes/ds4/…` fails on the head with
     "Could not resolve mod" — a **ship-order** requirement, not a recipe bug (documented §4).
   - Local trials must NOT use the `@littlecedar/` form.
3. Trial mechanism that works: a scratch copy of the recipe in
   `.scratch/ds4/boot_tf2x/recipe.yaml` with the mod ref changed to relative
   (`tensorfold-dsv41-launcher`) + a `mods/` symlink beside it → adjacent resolution succeeds →
   sparkrun rsyncs the mod to the head's staging dir.
4. Launch must be `setsid nohup … &` (a tool-timed-out `sparkrun run` gets killed).
5. sparkrun syncs the model head→worker even though both already had it, over 192.168.1.x
   (management net) at ~400 MiB/s: **510 s for the 196 GiB checkpoint**. It is a one-time cost
   per (head,worker) pair but it is real, and it is the dominant cost of the FIRST launch.
   `--copy-unsafe-links` materializes the blob symlinks, so measure with `find -type f -printf %s`.

## Context window and concurrency (measured 2026-10-05)

**The recipe ships at the maximum: `max_model_len: 1048576`** (changed from 262144 on request,
2026-10-05). Since TensorFold has no pool knob, this sets the largest possible KV cache too. No
compelling reason to cap lower was found; the change is strictly better (see the table below).

**Ceiling: `--context` ≤ 1,048,576, hard-enforced.** `cli.py:355` refuses `context > native_context`
("`--context 4194304 exceeds this model's 1048576-token window`") before weights load;
`native_context` = `config.json` `max_position_embeddings` = 1048576. Verified boundary on .34:
`1048577` refused, `1048576` loads. This family never calls `cuda.capacity.admit`, so the ceiling is
that CLI check — there is no memory-based clamp below it (`self.limit = context`, engine.py:112).

**Yes: the shared KV pool is capped at 1048576 — and it is a *model* cap, not a memory cap.** The
pool *is* `context` (`new_pool(cap=context + max_rows + 8)`); there is no larger pool it slices.
1,048,576 is the model's trained window: `rope_scaling = {yarn, original_max_position_embeddings:
65536, factor: 16, …}`, and 65536 × 16 = 1,048,576 — past it there are no valid positions, so the
engine refuses rather than serve nonsense. Memory is not binding: MLA means one latent KV head
(`num_key_value_heads: 1`, `head_dim: 512`) ⇒ **~2.9 KiB/token**; measured warm-up `reserved`
**100.82 GiB @ 262144 vs 102.98 GiB @ 1048576** - the whole extra 786,432 tokens cost **2.16 GiB**
per rank. Tens of millions of tokens would fit in 128 GB; the model has no positions for them.

**Raising 262144 → 1048576 is strictly better (verified 2026-10-05):**
- Decode speed unchanged: **72.5 tok/s @ 1M** vs 73.0 @ 262K (median of 3, same 288/256 prompt,
  same `drafted=262 accepted=160`).
- Concurrency improved: 4 concurrent requests each declaring 250K → **1 concurrent @ 262K, 4 @ 1M**.
- Cost: +2.16 GiB/rank (fits; ceiling ~107 GiB), and nothing at decode time (pages touched as used).
- A slow prefill is the only real cost, and only for genuinely huge prompts (~10% on a fresh 1M
  prefill, per upstream) — not a reason to deny that capability.

**Do not conflate the two lanes' KV numbers.** They are different engines (both `runtime: sglang`,
but knapcio runs real `sglang.launch_server` via `dsv41-sglang-overlay`; TensorFold runs
`tensorfold serve` via the shim):

- knapcio: `MAX_TOTAL_TOKENS=4000000` → sglang `--max-total-tokens`, a **separately pinned** KV
  pool (`mods/dsv41-sglang-overlay/launcher.py:129`), with `CONTEXT_LENGTH` a separate per-request
  limit. 4M pool ≈ 6.6 × 1M streams. Its boot line `full_token≈7.5M` is the *budget*, not held
  tokens; upstream's TP4 `.env` pins 8,000,000. README "1M Context / ~6.6 concurrent" describes
  THIS lane — now scope-labelled in the README.
- TensorFold: **no pool flag exists** (`serve --help` has none; no env sets one). `--context` *is*
  the pool, so max total = 1,048,576, ever. Different mechanism, different ceiling.

`--context`/`max_model_len` is the **whole KV pool**, shared by the `--parallel` lanes — the engine
logs `--parallel 4: 4 streams share one window of <context> tokens (an extent each)`, and
`model.py::new_pool` docstring says "One window of `cap` positions that up to `slots` streams share
by extents", with `cap = context + max_rows + 8` (engine.py:130). Each stream takes an extent of
`prompt + max_tokens + draft rows` out of that one window; `prompt+reply > context` is rejected as
`context_length_exceeded`.

Measured (4 concurrent requests, each declaring its own reply length; `streams.decoding` from
`/health`):

| max_tokens each | context 1048576 (shipped) | context 262144 (old) |
|:--|:--|:--|
| 2000 | 4 | 4 |
| 200000 | 4 | — |
| 250000 | 4 | 1 |
| 300000 | 3 | — |
| 500000 | 2 | — |
| 900000 | 1 | — |

- **1M full context: YES, shipped.** One stream may use the whole window (then it is the only
  decoder). Wire 1M at boot, report it in `/v1/models`.
- **Max concurrency 4** at context 1M holds up to a ~250K per-request window.
- **1M strictly dominates the old 262K**: four 250K requests go from concurrency 1 to 4, decode
  speed is unchanged, and 1M can serve anything 262K could plus more.
- `--parallel 4` is a hard cap (8 tiny requests still peak at 4 decoding).
- Memory is not the limit; the window is a fixed admission-time allocation.

Documented in AGENTS §12.13 and README "Context window and concurrency". The recipe now ships
`max_model_len: 1048576`; the guard `TensorfoldLaneContract.test_context_and_port_are_wired` pins it.

## Shipped state / remaining risks

- **Boot-verified 2026-10-05** (cold + warm + real inference). The image digest, checkpoint,
  Engram, shim mapping, guard suite, and both boot paths are all verified.
- **Context raised to 1,048,576** (the model's max, = the max KV cache here) on 2026-10-05, and
  re-booted + re-measured after the change: 72.5 tok/s decode, 4-way concurrency at 250K/request,
  `/v1/models` reports `max_model_len: 1048576`.
- **Ship-order:** pushing the repo is required before `sparkrun run recipes/ds4/<recipe>` works on
  the head (the `@littlecedar/` mod resolves from the node's registry clone). AGENTS §4 / §12.10.
- The EXL3 checkpoint's **quality** on this project's hard tier is unmeasured. Do not imply parity
  with the knapcio lane's 17/18. The *boot* is verified; the *quality battery* is not.
- First-launch cost: a one-time ~510 s head→worker model sync even when both nodes already hold the
  checkpoint (block 5). Not a bug, but budget for it.