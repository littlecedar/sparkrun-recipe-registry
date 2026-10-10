# ds4 work notes

## Combined local HF repo (EXL3 + upstream Engram + prompt) — BUILT

One local HF repo carrying **everything** the TensorFold TP=2 lane needs, so a
node no longer stitches three sources together. Built with
`tools/build-dsv41-combined.py` (stdlib) on `aphorism`, 2026-10-06.

### What ships in it
- EXL3 2.9bpw weights: `model-000NN-of-00039.safetensors` (39/39, 196.14 GiB),
  `config.json` + `quantization_config.json` (**EXL3 config stays authoritative**),
  index — from `Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw@64ba41b6`.
- Upstream updates: `chat_template.jinja` (**the updated prompt**, promoted to the
  repo root), `tokenizer.json`, `tokenizer_config.json`, and the whole upstream
  repo under `upstream/` (provenance) — from
  `deepseek-ai/DeepSeek-V4.1-Flash@2cba9e42`.
- Engram tables: `engram/engram-l{1,14}.safetensors`, 94.4 GiB each (188.8 GiB),
  built from upstream shards 47/48 by `tools/build-dsv41-engram.py`.
- `provenance/{SOURCES,MANIFEST}.json` (pinned revisions + per-file sha256) and
  the EXL3 conversion's original prompt as `chat_template.exl3.jinja`.

### Why the tables are in `engram/`, not the root
The engine globs `*.safetensors` **non-recursively** in `TF_DS_ENGRAM`; at the
repo root that glob would also walk the 39 EXL3 shards. So they live in a subdir
and `mods/tensorfold-dsv41-launcher` gained `resolve_engram_dir(model_dir)` which
prefers `<model_dir>/engram/` — `model: <this repo>` is then all a recipe needs.

### Wiring
- `tools/build-dsv41-combined.py` — builds the repo (~430 GiB free); default
  stages shards 47/48 for a **local** rebuild (ranged online reads were ~15 MiB/s
  vs ~170 MiB/s for a whole-file pull); `--engram-online` skips the staging.
- New recipe `recipes/ds4/deepseek-v4.1-flash-exl3-engram-tp2-1m-sglang.yaml`:
  the combined `model:`, **no** `dsv41-engram-fetch` mod (tables ship in the repo).
- Distribution: sparkrun distributes **by repo id into the node HF hub cache**
  (`huggingface-cli download <id> --cache-dir <cache>/hub`) — a local dir is NOT
  auto-distributed. Push to the org (`hf upload`) and set `model:` to that id, or
  pre-place `models--<org>--<name>/snapshots/<rev>` on each node.

### Verified (2026-10-06)
- Engram: `--check` OK (384006168 / 384016682 rows × 264 B); 300/300 random rows
  byte-exact vs shards 47/48 (same check the mod's builder passes).
- EXL3: 39/39 shards, 196.14 GiB, index + quantization_config present.
- `sparkrun recipe validate` passes (1 pre-existing `exl3` dtype suggestion,
  identical to the sibling lane), full guard suite green.

### Boot-verified (2026-10-07, `.34`/`.35`) — cold boot from the combined repo

`sparkrun run recipes/ds4/deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml -H 10.0.4.34,10.0.4.35
--transfer-mode local` from spark-head; job `8ef9b6c9a550c389_3510a5e0d37d`, exit 0.

- Distribution: image already current on both hosts; model head→2 hosts in 867 s with
  `--copy-unsafe-links` (the hub-level xet blob store is materialised, node caches land
  self-contained at 388 G each, `du -shL`). Head cache `hf cache verify`: 96/96 checksums OK.
- Cold boot (new runtime-cache key for the new repo id; the old warm key was
  `Mia-AiLab__…-2db4d63c`): rank-0 weights 98.8 GiB in 324 s, rank-1 316 s, both written to
  the rank cache; CUDA extensions built; rank-0 warm-up 105.9 s; reserved 102.98 GiB;
  TTR port-open/HTTP-ready **530.6 s**, engine "loaded in 525.6 s"; rank 1 "ready in 521.3 s".
- Engram ACTIVE from the repo itself, both ranks:
  `TF_DS_ENGRAM=/cache/huggingface/hub/models--littlecedar--…-with-engram/snapshots/48afcd1c4f2d…/engram`
  (launcher boot line + `/proc/<tensorfold>/environ`), mmap FDs on `blobs/bb50b619…`
  (engram-l1) and `blobs/f9d5346f…` (engram-l14) on rank 0 **and** rank 1. No degradation
  warning; `dsv41-engram-fetch` absent and unused, `dsv41-engram/` on the nodes untouched.
- API: `/v1/models` → one model, `max_model_len 1048576`; `/health` ok, `context_length 1048576`;
  greedy chat completion returned `BOOT-OK` (thinking on by default — 20 reasoning tokens).
- Launcher shipped = worktree revision (`md5 df18e47a2ea4e517672f03e043d10f9a`) on both nodes,
  resolved from the head's `~/.cache/sparkrun/registries/littlecedar` clone. That clone was
  updated by file copy from the rsync'd tree — GitHub main still lacks the new mod, so a
  registry re-pull (or a fresh clone) reverts to the old 190-line launcher until the commits
  are pushed.
- Left running — `sparkrun stop 8ef9b6c9a550c389_3510a5e0d37d`. Head-side evidence:
  `/home/red/tf-tp2-boot.log`, `/home/red/hf-verify.log`.

### Adjacent fixes (2026-10-07, after the boot)

- The untracked sibling `deepseek-v4.1-flash-exl3-engram-tp2-1m-sglang.yaml` pointed at
  `littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-engram`, which **404s even with the org token**
  (only `-with-engram` exists on HF). `model:`/`model_url:` fixed to the real id; after that it
  is a functional duplicate of the TensorFold recipe — keep or attic it deliberately.
- Guards realigned to the new artifact: `test_runtime_image_model` and
  `test_control_official_mxfp4_checkpoint` re-pinned from `Mia-AiLab/…` to the combined id; the
  two obsolete fetch-wiring pins (`test_recipe_lists_engram_fetch_before_launcher`,
  `test_sibling_lane_keeps_its_fetch_mod`) deleted — the wiring they pinned is gone from every
  recipe. Suite: **386 tests green**; 24/24 recipes validate.
- `recipes/ds4/{README,AGENTS}.md` still describe `mods/dsv41-engram-fetch` as the TP=2 recipe's
  Engram path (§12.7 and the lane table) — flagged here, not rewritten (lane docs are mid-flight).

## Engram-from-HF builder (TP=2) — DONE, boot-verified

Builds the DSV41 Engram tables from the **online HF repo** (no local weight cache),
wired into the TensorFold TP=2 recipe. Trials on `.34`/`.35` only.

### Deliverables
- `tools/build-dsv41-engram.py` — canonical standalone CLI (stdlib, ranged GETs,
  resumable; `--detach`/`--status`/`--check`, host-aware `--out` default).
- `mods/dsv41-engram-fetch/` — pre-launch mod (never blocks; detached fetch).
- `mods/tensorfold-dsv41-launcher/launcher.py` — `resolve_engram_dir()` also reads a
  sparkrun-distributed Engram repo.
- Recipe lists the mod; a commented `distribution_config.models` block enables
  sparkrun-distributed tables.
- `tests/test_dsv41_engram_builder.py` — 21 guards incl. negative controls.
- Docs: `tools/README.md`, `recipes/ds4/{README,AGENTS}.md` §12.7, mod README.

### Timeout / slow-link changes (this round)
- The mod **never blocks**: it always launches the fetch detached (`setsid nohup`),
  returns in ~0.5 s, and ignores `MOD_ENGRAM_WAIT`. The 600 s pre-exec hook timeout
  can no longer kill a launch.
- `--detach` / `--status` make the tool usable outside the recipe for pre-warm; it
  resumes across interruptions (`.engram-progress.json`).
- Bare `--out` writes the **host** cache when run on a node (container path otherwise).

### Distribution (verified mechanism)
- `distribute_model_from_head` rsyncs `model_cache_path(model_id)` — the whole
  `models--<org>--<name>` dir — so a second `distribution_config.models.entries`
  entry is downloaded once on the head and rsynced to workers. Dry-run showed two
  `Distributing model … / synced from head to 1 worker(s)` lines. This is the
  cheap path on slow links (1× egress, not N×). Repo must exist + be vetted; shipped
  commented out, launcher resolves it.

### Boot verification (2026-10-06, engrams deleted first)
- Recipe fetched 189 GiB on-node (`.35`: 820 s, 236 MiB/s); fresh boot ready ~70 s;
  both ranks held `TF_DS_ENGRAM` + open `engram-l1/l14.safetensors`. Byte-identical to
  the official snapshot (full-file SHA256; 300/300 rows via engine `Shards`).
- Rank-0/rank-1 Engram mismatch **hangs at readiness** — all ranks must be provisioned.

### Open / notes
- `manateelazycat/DeepSeek-V4.1-Flash-TensorFold-Engram` exists on HF (203 GB, `source/`
  subdir) but is unvetted third-party — documented, not shipped as a dependency.
- Unrelated: the `tests/test_ifm_recipes.py` COOP.md check was dropped 2026-10-10, when
  coordination ledgers were removed from git (`**/COOP.md` is now git-ignored).