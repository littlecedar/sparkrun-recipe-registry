# mods/

Shared `sparkrun` mods — pre-launch container hooks that patch or stage files inside the serving
image before the engine execs. A mod belongs here only when recipes in **two or more lanes** use it
(`mod-template/` is the exception: a scaffold no recipe references). A mod relevant to a single lane
lives at `recipes/<lane>/mods/<mod>/` and must be referenced **unscoped** as `mods/<name>` — sparkrun
resolves it adjacent to the recipe (`sparkrun/core/mods.py` rule 2), and `@littlecedar/mods/<name>` is
broken there. The shared set is asserted by `tests/test_mods_lane_locality.py`.

`mod-template/run.sh` is the **authoritative harness**: there is no shared library (sparkrun ships only
the mod's own directory, so a `mods/common.sh` would not exist at launch), so a new mod copies the
template. It carries the SPDX header (`AGPL-3.0-or-later`), `set -euo pipefail`, the
`MOD_NAME`/`MOD_DESCRIPTION`/`MOD_MAINTAINER` exports, `reown()` (mods run as root; the runtime-cache
mount owner is inferred from `stat`), `log`/`log_var`/`log_cmd`, and log rotation under
`/cache/runtime/modlogs`.

| mod | what it does | mounted by |
|---|---|---|
| `mod-template` | Authoritative hand-copy mod harness; not a runnable mod | no shipped recipe |
| `drop-caches` | Fail-closed HOST page-cache drop from a privileged mod | no shipped recipe (four lanes list eugr's inert copy) |
| `pip-install-fastsafetensors` | `pip install fastsafetensors` into the image | cybersec (4), ornith (2), qwen3 (1) |
| `pip-install-orjson` | `pip install orjson` for a fast `/v1/embeddings` | embed (2), rerank (2) |
| `fix-fastsafetensors-tp2-sglang` | Patch SGLang's fastsafetensors reader for multi-node TP: local-rank device selection + release the staged device buffer (`~26.9 GB` on GB10) | cybersec (1), qwen3 (1) |
| `tensorfold-dsv41-launcher` | Fail-closed pre-launch gate + runtime-cache setup for the TensorFold DSV41 TP=2 shim | ds4 (1), cybersec (1) |

## Contents

- [mod-template](#mod-template)
- [drop-caches](#drop-caches)
- [pip-install-fastsafetensors](#pip-install-fastsafetensors)
- [pip-install-orjson](#pip-install-orjson)
- [tensorfold-dsv41-launcher](#tensorfold-dsv41-launcher)
- [Unmounted mods](#unmounted-mods)

## mod-template

Not a CLI and not a runnable mod — a **scaffold**: copy `mod-template/run.sh` as the starting point for
any new mod. It ships the house harness (metadata exports, logging/rotation, `reown()`, `log_var`,
`log_cmd`, the config block, and a "main mod scripting zone"), and is the file every guard in `tests/`
checks other mods against for those harness bits. `mod-template` is exempt from the shared-only rule
because it is a scaffold, not something a recipe references.

## drop-caches

Drops the **host** kernel page cache from a privileged mod — and **refuses to pretend** when it cannot.
It reads `Cached:` from `/proc/meminfo`, `sync`s, writes `MOD_DROP_CACHES_LEVEL` (default `3`) to
`/proc/sys/vm/drop_caches` with a **single** stdout redirect, re-reads `Cached:`, and `die`s (exit 1) if
the write fails. It exists because `@eugr/mods/drop-caches`, which four lanes list, is **inert** for two
independent reasons reproduced 2026-09-27: sparkrun's default rootless launch mounts `/proc/sys` `ro`
(so the write is refused), and eugr's command has a redirection-order bug (`echo 3 > …drop_caches >>
log 2>&1` sends `3` to the log, not the target). This copy fixes both and fails closed.

**Caveat — rootful launch required.** `privileged` is trust-gated (`core/launcher.py:_TRUST_GATED_EXECUTOR_KEYS`),
so a cache drop only happens on a `--rootful` launch (or `-o privileged=true`) of a trusted recipe;
under the default rootless launch this mod correctly **fails the launch**. `/proc/sys` is not
namespaced, so the drop is **whole-node**, not per-container — it evicts every tenant's warm cache.
`MOD_DROP_CACHES_MODE` is `once` (default) or `loop` (eugr parity; prefer `once`). Knobs:
`MOD_DROP_CACHES_MODE`/`_INTERVAL`/`_LEVEL`/`_TARGET` (the last a test hook). Guarded by
`tests/test_drop_caches_mod.py`, which runs it against a stand-in target to prove both the writable
(`rc 0`, level written) and unwritable (`rc 1`, no silent success) paths.

## pip-install-fastsafetensors

`pip install --force --break-system-packages fastsafetensors` into the serving image, then `reown`s the
runtime cache. Mounted by the sglang lanes that load weights through the fastsafetensors reader
(cybersec, ornith, qwen3).

**Caveat — it only does anything with `load_format: fastsafetensors`.** The qwen4 labquant recipe
deliberately omits it because it runs `load_format: safetensors` — and worse, the two fastsafetensors
mods exec as root and leave a root-owned `flashinfer_jit.log` in the persisted per-model runtime cache,
making the first launch of a new model key die as uid 1000 with a sticky `PermissionError`; re-add them
only if you set `load_format=fastsafetensors`. The `reown` in this mod, and the TP=2 hard-memory case
(`load_format=fastsafetensors` retains ~26.9 GB more device memory than `safetensors`, tipping
`--mem-fraction-static 0.85` past the KV-pool fit), are handled by the shared
`fix-fastsafetensors-tp2-sglang` — which must be listed **after** this one, since mods resolve into
sequential `pre_exec` entries.

## pip-install-orjson

`pip install --force --break-system-packages orjson` into the serving image, then `reown`s the runtime
cache. orjson makes vLLM's `/v1/embeddings` response path fast. Mounted by every pooling recipe (embed,
rerank).

## tensorfold-dsv41-launcher

The pre-launch mod for the TensorFold DeepSeek-V4.1-Flash TP=2 shim. It is a **fail-closed gate**: it
asserts the `tensorfold` binary is on `PATH`, `launcher.py` and `/cache/huggingface/hub` exist, and
exits 1 if any is missing; it then creates and re-owns the managed runtime-cache directories the launcher
writes (`rank-cache/`, `torch-extensions/`) and reports the Engram shard state. It modifies no image
file. The recipe's command runs `launcher.py --boot`, which maps sparkrun's per-node rendezvous flags
onto `tensorfold serve`. Mounted by the ds4 TP=2 lane and the cybersec abliterated TP=2 lane (reused
unchanged, carrying `--stock-model` instead of `--revision`).

**Opt-in `--vision` (shipped 2026-10-15).** `launcher.py --vision` enables image input: the shim appends
`--vision` to `tensorfold serve` and points `TF_DS_VISION_EXTRA` at its own directory, where it ships
`vl_bias.safetensors` (the 43 `*.ffn.gate.bias_vl` tensors the EXL3 checkpoint omits; `attach_vl_bias()`
takes a folder, not a file). It **fails closed** if that file is absent — the engine only warns and
routes image tokens with the text bias, which would look like working vision. The ds4 TP=2 recipe passes
`--vision`; the cybersec arm does **not**, so its serve line and env are unchanged. Evidence:
`attic/ds4/AGENTS.md` §12.14.

**Caveat — Engram is out-of-band and never fails closed.** The tables are two ~95 GiB shards of the
*official* checkpoint, absent from the EXL3 repo. They now travel **with** the combined repo
(`littlecedar/…-with-engram`, `<snapshot>/engram/`), which the launcher's resolver prefers; the mod
**reports** which of the two homes is populated — the combined repo or the legacy flat
`TENSORFOLD_ENGRAM_DIR` (default `/cache/huggingface/hub/dsv41-engram`) — and says `degraded` only
when neither is, because the engine loads without them, with a warning. `@littlecedar/mods/…` resolves from the node's registry clone, so the
mod must be committed and pushed before the recipe launches. One AGPL-3.0-or-later port of upstream code
lives among these mods: the lane-local `fix-sglang-radix-chunked-insert` (Apache-2.0 headers retained).

## Unmounted mods

Three mods in this registry are mounted by **no shipped recipe**, plus one archived provenance copy
(the vision trial below, now folded into the launcher mod). Their dispositions are recorded here so they
are not lost to grep.

- **`drop-caches` (top-level, shared).** The fail-closed replacement for `@eugr/mods/drop-caches`. No
  shipped recipe mounts it — four lanes (qwen4, ds4, qwen3, ornith) list eugr's inert copy — but it stays
  in the shared set **by design** as the fixed counterpart of a mod those lanes name. See
  `mods/drop-caches/README.md`; the exception is recorded in root `AGENTS.md` and
  `tests/test_mods_lane_locality.py`.

- **`skip-labquant-vision-tower`** (`recipes/qwen4/mods/skip-labquant-vision-tower`). Set
  `language_model_only: true` in the patched `config.json` so SGLang can load the old labquant export
  whose vision tower was MXFP8-quantised (the scales had no destination under `quant_config=None`).
  **Dropped as obsolete** on the current step-5500 labquant revision: that revision ships the vision
  tower **BF16** and already lists `model.visual.*` in `quantization_config.ignore`, so the load failure
  is gone and the export **serves vision again** — the mod is now deliberately absent from the shipped
  recipe (it survives only in archived arms under `attic/qwen4/arms/`). Source: `attic/qwen4/AGENTS.md`
  (mods chain) and `recipes/qwen4/README.md`.

- **`fix-sglang-radix-chunked-insert`** (`recipes/qwen4/mods/fix-sglang-radix-chunked-insert`). Defers
  chunked-prefill radix-cache inserts to request completion, stopping the hybrid (Mamba/GDN) radix cache
  from referencing KV pages a retraction has freed — the corruption behind sglang#38319's `!!!!` decode
  loop. All four source anchors were re-verified against the pinned image, but it is **not mounted by any
  shipped recipe**. Disposition: a **correctness/quality fix, not a performance one** — deferring inserts
  gives up some prefix reuse within a long chunked prefill, so expect no tok/s change and treat any as
  noise; its value is removing a class of silent wrong-output failures. It is a **port of third-party
  code** (Apache-2.0 headers retained). Source:
  `recipes/qwen4/mods/fix-sglang-radix-chunked-insert/README.md`; `attic/qwen4/AGENTS.md` (records the
  stream as closed with anchors re-verified).

- **`dsv41-vision-overlay`** — **SHIPPED 2026-10-15, now archived as provenance.** The experimental
  trial that gave the TensorFold DSV41 TP=2 lane image input was folded into
  `mods/tensorfold-dsv41-launcher`: the launcher passes `--vision` (opt-in) and ships the 43
  `*.ffn.gate.bias_vl` routing-bias tensors the EXL3 checkpoint omits, failing closed if
  `vl_bias.safetensors` is missing. The trial copy — which demonstrated the mechanism (verified
  2026-10-06: `VL bias for 43 gates`, three discriminating images read correctly) — now lives at
  `attic/ds4/mods/dsv41-vision-overlay/` and mounts nothing. Source:
  `attic/ds4/mods/dsv41-vision-overlay/README.md`; `attic/ds4/AGENTS.md` §12.14.