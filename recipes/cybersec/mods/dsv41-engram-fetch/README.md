# `dsv41-engram-fetch`

Pre-launch mod for the DeepSeek-V4.1-Flash **TensorFold TP=2** lane. **Unmounted since 2026-10-17:**
the shipped `recipes/ds4/deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml` serves the 1017 EXL3
pack and reads its Engram tables from the node's `hub/dsv41-engram` dir (pre-warmed out of band by
this mod or `tools/build-dsv41-engram.py`; the recipe's `--require-engram` makes a missing set
fail the launch). The cybersec abliterated arm reads the V4.1 tables from the combined
`littlecedar` pack through the launcher's `--stock-model`. What remains here is the out-of-band
pre-warm path for a node that lacks either — and the Engram path the open 1017-refresh item names.

It builds the model's two Engram embedding tables on each runner node **from the
online Hugging Face repo**, so the lane no longer depends on someone having
copied 189 GiB of checkpoint shards (`model-00047/48-of-00048.safetensors`) into
the node's HF cache by hand.

## Contents

- [Why this exists](#why-this-exists)
- [What runs](#what-runs)
- [Knobs](#knobs)
- [Cost and verified behaviour](#cost-and-verified-behaviour)
- [Why the mod never blocks (and never fails the launch)](#why-the-mod-never-blocks-and-never-fails-the-launch)
- [Pre-warming outside the recipe (recommended on slow links)](#pre-warming-outside-the-recipe-recommended-on-slow-links)
- [Distributing instead of fetching (multi-node / slow links)](#distributing-instead-of-fetching-multi-node--slow-links)
- [Running it by hand](#running-it-by-hand)

## Why this exists

The EXL3 conversions carry **no Engram tables** — the quantizer dropped them — while the 1017
pack ships none either, which is why the standalone `hub/dsv41-engram` dir exists. Until the
2026-10-17 re-base the served repo was the combined pack, whose weight shards are the Mia ones
byte-for-byte and which carries the V4.1 tables inside the snapshot.
The tables are 189 GiB and live only in the *official* base repo — a ~475 GB
checkpoint. Pulling that repo just to reach the tables means materializing the
whole model, which is exactly what the TP=2 lane is designed to avoid. The
default source is the **1017** base pinned at `1bae0e10…`, because the shipped
arm serves the 1017 pack and the card forbids pairing its weights with the old
base's tables (PPL 1.87/6.43 -> 4.16/9.06 with lookups off); `MOD_ENGRAM_REPO` /
`MOD_ENGRAM_REVISION` still reach the superseded base for an A/B.

The engine (`tensorfold.families.deepseek_v41.cuda.model.Engram`) reads the
tables as **safetensors** from `TF_DS_ENGRAM`: it globs `*.safetensors` there and,
for each `*.engram.embed.weight` / `*.engram.embed.scale`, reads row `i` at
`8 + header_len + data_offsets[0] + i * row_bytes`. This mod produces a directory
that satisfies that contract byte-for-byte, using **HTTP byte-range reads**
against the HF CDN, so the full checkpoint is never downloaded.

## What runs

`build-dsv41-engram.py` (bundled; canonical copy in `tools/`):

1. fetches the repo's `model.safetensors.index.json` (~7 MB) to locate the four
   `engram.embed.{weight,scale}` tensors, and reads the two shard headers to
   confirm the data offsets;
2. ranged-copies each tensor (layer 1 → `engram-l1.safetensors`, layer 14 →
   `engram-l14.safetensors`) into `TF_DS_ENGRAM`, ~256 MiB per ranged request,
   resumable;
3. renames `.partial` files to their final names **only after every layer is
   complete**, so a glob never sees a half-written table.

The fetch is **detached and never blocks**: a first boot does not wait on the CDN
— the engine serves with the degraded warning and picks the tables up on the next
boot. There is no blocking mode; pre-warm out-of-band instead (see below).

## Knobs

| Variable | Default | Meaning |
|:--|:--|:--|
| `MOD_ENGRAM_DIR` | `/cache/huggingface/hub/dsv41-engram` | output dir; must match the launcher's `TENSORFOLD_ENGRAM_DIR` |
| `MOD_ENGRAM_WORKERS` | `16` | concurrent ranged transfers |
| `MOD_ENGRAM_SEGMENT_MB` | `256` | ranged-request size (larger = fewer requests, avoiding HF 429) |
| `MOD_ENGRAM_LAYERS` | `1,14` | layers to build (the checkpoint's `engram_layer_ids`) |
| `MOD_ENGRAM_LIMIT_ROWS` | — | build only the first N rows per table (smoke tests) |
| `MOD_ENGRAM_REPO` | `deepseek-ai/DeepSeek-V4.1-Flash-1017` | source repo (the old base still selects with this knob) |
| `MOD_ENGRAM_REVISION` | `1bae0e10…` (the 1017 base) | source revision; pinned because `--require-engram` cannot tell the two table generations apart |
| `MOD_ENGRAM_HF_TOKEN` | — | gated/private repos (else `HF_TOKEN` from the container env) |
| `MOD_TIMEOUT` | `180` | gate timeout (not the fetch; the fetch is detached) |

## Cost and verified behaviour

- ~189 GiB out; **~2-15 min on a fast link, but many hours on a slow one**. **Peak
  RSS ~0.6 GB**: the writer bounds each in-flight transfer and advises written pages
  `POSIX_FADV_DONTNEED`, so a 121 GB unified-memory node never needs 189 GB of page
  cache. Verified on `.34`/`.35` (2026-10-06).
- Output verified byte-exact against the on-node checkpoint shards: full-file
  SHA256 match on both planes, and 300/300 random rows read back through the
  engine's own `Shards` accessor (see `tools/README.md` and `tests/`).
- A **clean-room** run on an empty `HF_HOME` (no local model cache) produced
  output byte-identical to the node's snapshot (100/100 rows), confirming the
  builder needs the online repo and nothing else.
- Idempotent: `build-dsv41-engram.py --check --out <dir>` returns 0 when the
  tables are complete — including when the dir holds the *official* checkpoint
  shards themselves — and the mod then does nothing.

## Why the mod never blocks (and never fails the launch)

sparkrun runs a mod as a **pre-exec hook under a hard 600 s SSH timeout**
(`orchestration/hooks.py`). A synchronous fetch longer than that is killed and the
launch fails — observed on 2026-10-06 (`pre_exec[2] failed … TIMEOUT after 600s`).
Because a slow link can take hours, the mod **always launches the fetch detached**
and returns at once; `MOD_ENGRAM_WAIT` is accepted but ignored. The fetch also
**resumes**: if a launch is stopped mid-fetch, the `.partial` files and the
`.engram-progress.json` cursor let the next run continue instead of restarting.

## Pre-warming outside the recipe (recommended on slow links)

The fetch is a standalone tool and does not need a recipe, a container, or a
launch. On each node (writes to the host cache the container bind-mounts):

```bash
# start it detached; it survives logouts and ssh disconnects
python3 tools/build-dsv41-engram.py --detach          # prints pid + log path
python3 tools/build-dsv41-engram.py --status          # progress; exit 0 = complete
python3 tools/build-dsv41-engram.py --check           # offline completeness check

# or run it in the foreground / under nohup / in a tmux session
python3 tools/build-dsv41-engram.py --workers 24
```

A bare run with no `--out` writes `~/.cache/huggingface/hub/dsv41-engram` on a host
(the layout the container sees at `/cache/huggingface/hub/dsv41-engram`), or the
in-container path when run inside the serving image. Because the engine degrades
gracefully without the tables, you can pre-warm nodes while the cluster serves.

## Distributing instead of fetching (multi-node / slow links)

`sparkrun` distributes **per model repo**, so an Engram repo declared in the
recipe's `distribution_config.models` is downloaded **once on the head and rsynced
to the workers**, instead of every node pulling 189 GiB. Verified 2026-10-06: a
second `models.entries` entry is planned and synced head→worker
(`Distributing model … / Model '…' synced from head to 1 worker(s)`).

To use it, uncomment the `distribution_config` block in the recipe and point the
entry at a repo that carries the tables (pin a revision you have vetted — an
unvetted third-party repo is a supply-chain risk for weights read on every token).
The launcher (`mods/tensorfold-dsv41-launcher`) reads the tables from that repo's
cache dir when the mod's own directory is empty. Prefer this when nodes share no
cache and the Internet link is the bottleneck.

## Running it by hand

```bash
# on any node, offline check:
python3 build-dsv41-engram.py --check --out /cache/huggingface/hub/dsv41-engram

# synchronous pre-warm of one node:
python3 build-dsv41-engram.py --out /cache/huggingface/hub/dsv41-engram --workers 24

# smoke test: first layer, 5000 rows:
python3 build-dsv41-engram.py --layers 1 --limit-rows 5000 --out /tmp/engram-smoke
```

The same utility also emits knapcio's packed 264-B shards
(`--format packed --tensor-parallel 4 --rank R`) should another lane need them.