# MEMORY-RECLAIM-PLAN — recommendation + action plan (handoff to the implementation agent)

**Status:** recommendation written 2026-09-27, after two live boots of
`…-exl3-tp4-vllm` on four idle Sparks and a one-node reproduction of the
InstantTensor failure (below). **Audience:** the agent who implements the next
change in this lane. Everything here is cited to a primary artifact or to
`recipes/ds4/AGENTS.md`; build on nothing labelled SPECULATIVE.

**TL;DR. The `instanttensor` question is now CLOSED (do not re-open it), and cache
drops are not a mitigation.** InstantTensor is **incompatible with this checkpoint
on this hardware**, reproduced on one node in seconds: it sizes a **GPU buffer to
the checkpoint's largest single tensor — the 91.56 GiB Engram table** (183 GiB by
its overlap heuristic across all 48 shards) — and then the native loader **aborts**
(`Failed to submit aio: Invalid argument` → SIGABRT) against the shared NFS cache.
A ≥91.56 GiB per-rank GPU buffer is **by itself fatal** on a 128 GB node, which is
the **LIKELY** mechanism of the six-node crash; there is **no version of this lever
to ship**. A load-window flusher is measured to buy **nothing** for KV.
So the only real finding left is that the launch weight load fills ~45–58 GiB/node
of clean, reclaimable page cache — which is **not** worth acting on. **The
implementation agent's action is: do nothing to the recipes for memory, and if a
cache change is ever wanted, the bounded reader fix (§3B) is the only viable one.**

---

## 1. What is settled (do not re-open)

- **`instanttensor` does not work here — CLOSED, with a boot-free repro.** The
  largest tensor in this checkpoint is `layers.14.engram.embed.weight` = **91.56
  GiB** (measured from the real safetensors headers). `instanttensor.safe_open`
  sizes its **GPU buffer** to the largest tensor and *refuses to go below it*
  (`_impl.py:593-620`, `_determine_buffer_size`), so a single-shard open is
  **91.55 GiB**, and the default overlap heuristic over all 48 shards is **183.11
  GiB** — larger than a 128 GB GB10 node. Reproduced on one node:
  `Failed to submit aio: Invalid argument` / `Loader thread exception:
  std::exception` / SIGABRT, on **both** `model-00001` (4.0 GiB buffer) and
  `model-00047` (91.55 GiB buffer). A ≥91.56 GiB per-rank GPU buffer is by itself
  fatal on a 128 GB node, which is the **LIKELY** mechanism of the 2026-09-25
  six-node crash (§7.9); the vendored hybrid-draft mod was a documented **no-op**,
  so the flag alone is sufficient. **No action — do not re-apply.**
- **The `drop-caches` mod is not useful here.** `@eugr/mods/drop-caches` is inert
  (two independent defects); `@littlecedar/mods/drop-caches` is mechanically correct
  but **fails closed**, so it would abort every default (rootless) launch. The
  recipes keep `@eugr` for parity and are **unchanged**. AGENTS.md §7.8. **No action.**
- **A load-window page-cache flusher does not buy KV.** Controlled A/B, same recipe,
  fresh nodes, host-side flusher dropping while `MemFree < 8 GiB`:
  available KV **32.2 GiB → 29.32 GiB**, pool **3,973,172 → 4,008,344 tokens
  (+0.9 %, within the ±6 % boot spread)**. The B1.3 "+55 % pool" did not reproduce;
  `.scratch/ds4/TUNING_BACKLOG.md` B1.3 is marked REFUTED and AGENTS.md §7.8.1 has
  the table. **No action** (do not build a flusher mod).
- **The reader-bounding idea works and is now IMPLEMENTED as an opt-in mod (§7).**
  Against the real `model-00047` over real NFS: buffered reads retain **+0.50 GiB**,
  `fadvise(DONTNEED)` per read **+0.01 GiB**, `O_DIRECT` **+0.00 GiB**, throughput
  identical (100–109 MiB/s). Serving-time Engram reads moved `Cached` by **≈0**. So
  bounding the reader is cheap and correct but bounds a negligible term. Shipped as
  `mods/bound-engram-cache` and **listed on all five EXL3 recipes** (after the patch
  mod; the user asked for it wired in). Low value, boot-verified neutral.

## 2. Where the host memory actually goes (the measured picture)

Two live boots, four nodes, `Cached`/`MemFree`/`MemAvailable` sampled every 30 s:

| phase | `Cached`/node | `MemFree`/node | `MemAvailable`/node |
|:--|--:|--:|--:|
| before launch (cache dropped) | ~0.2 GiB | ~118 GiB | ~118 GiB |
| 60 s into weight load | 10–13 GiB | 32–48 GiB | — |
| 90 s | 28–39 GiB | 6–29 GiB | — |
| ~2.5 min (peak, no plateau) | **45–58 GiB** | **~1 GiB** | 41–54 GiB |
| steady after readiness | 14–27 GiB | 2–6 GiB | — |
| +34 requests (30 short, 4×~95 K prefill) | **≈0 change** | dips ~2 GiB | — |

Reading: **the launch-time weight load, not serving, fills the cache**, it fills
45–58 GiB/node, and `MemFree` floor is ~1 GiB but `MemAvailable` never drops below
~41 GiB — so the allocator is not actually starved during the KV sizing (which is
why the flusher bought nothing). A serving-time drop jumps `MemFree` **2–6 → 15–28
GiB**, i.e. ~24 GiB/node of the load cache is clean and reclaimable. Full table and
caveats: AGENTS.md §7.8.1.

## 3. Recommendation

**(A) Do not change the recipes for memory.** Every lever examined is either
measured to do nothing (flusher), incompatible and unsafe (`instanttensor`), or
negligible (reader-bounding). The 24 GiB/node of reclaimable load cache is
harmless: `MemAvailable` stayed ≥41 GiB through the load, so it never starved the
allocator, and the KV pool was sized correctly *with* the cache present.

**(B) The only viable cache change, if one is ever wanted**, is to bound the reader
(`fadvise(DONTNEED)` per read, or `O_DIRECT`, in `engram.py`). It is proven
cache-neutral on the real NFS path and costs nothing measurable, but it addresses
only the small serving-time term. Treat it as a minor hygiene mod, not a fix.
**Implemented (§7) and listed.**

**(C) Do not** re-try `instanttensor`, do not build a load-window flusher mod, and
do not wire any drop-caches mod into the recipes.

## 4. Action plan for the implementation agent

Ordered. The `instanttensor` investigation that this plan once handed off as
"step 1" has **already been done** (see §1 and §6) and its answer is **no** — so the
plan is now short by design.

1. **Do nothing to the recipes for memory.** The finding that motivated a change —
   "the load fills 45–58 GiB/node of cache" — does not warrant one: `MemAvailable`
   stayed ≥41 GiB through the load, the KV pool sized correctly *with* the cache
   present, and every candidate lever is refuted, closed, or negligible. Record the
   negative results and move on.
2. **(Optional, low priority) reader-bounding mod — the only viable cache change.**
   If a serving-time cache bound is wanted for its own sake, add
   `POSIX_FADV_DONTNEED` per read (preferred over `O_DIRECT` on NFS) to a copy of the
   shipped `engram.py`; ship as a **new** mod, not an edit to
   `mount-dsv41-exl3-patches` (that mod is md5-pinned to upstream `d45538f6`;
   changing it breaks the pin and the fail-closed check). Add a stdlib guard that the
   installed file contains the `fadvise` call and none of the double-redirect
   anti-pattern, plus a proven negative control (AGENTS.md §8.1). This buys no KV.
   **DONE — `mods/bound-engram-cache` (§7), with guards, listed on all five EXL3 recipes.**
3. **Do not** re-try `instanttensor` (closed, §1), build a load-window flusher mod
   (refuted, §1), or wire a drop-caches mod into the recipes (aborts the launch, §1).

**No fleet boot is required by this plan.** The one experiment it would have needed
was the instanttensor check, and that was answered on a **single** node without a
recipe boot (a container `safe_open` against the real NFS shards). Any future cache
change should be smoke-booted on one node first (§7.9's process lesson), never on
the fleet.

## 5. Guardrails the implementation agent should assume

- **Nothing here changes a recipe.** The recipes ship no `--load-format` and no
  hybrid-draft mod; that is the last known-good lane and it stays that way.
- **Use the repo ritual** (AGENTS.md §8.3) for any edit: `uv run python -m unittest
  discover -s tests`, `sparkrun recipe validate` (plain, not `--strict`) on every ds4
  recipe, then render with `sparkrun run … -n` and grep the *rendered* line.
- **Nodes:** `.32`–`.35` were used for the measurements here and are idle again;
  `.30`/`.31` are protected (§12). One boot at a time; stop with
  `sparkrun stop <id>`; cache-drop by `ssh <node> 'sync; sudo -n sh -c "echo 3 >
  /proc/sys/vm/drop_caches"'` (host-level only — the mod path cannot, §7.8).

## 6. Provenance

- Live boots and tables: AGENTS.md §7.8.1 (this lane, 2026-09-27).
- Mod inertness / fail-closed: AGENTS.md §7.8 and `mods/drop-caches/README.md`.
- InstantTensor crash and its process lesson: AGENTS.md §7.9.
- **InstantTensor incompatibility — the repro for §1.** Boot-free, one node
  (`.35`), 2026-09-27: real safetensors headers give
  `layers.14.engram.embed.weight = 91.56 GiB` (largest tensor); `safe_open` sizes
  its GPU buffer to that (`_impl.py:593-620`, `_determine_buffer_size` — will not go
  below `max(tensor_sizes)`); `instanttensor` 0.1.9 in image `exl3a` returns
  `buffer=91.55 GiB` (one Engram shard) and `183.11 GiB` (all 48 shards, default
  overlap heuristic), then aborts with `Failed to submit aio: Invalid argument` /
  `Loader thread exception: std::exception` (SIGABRT) on **both** a 4.0 GiB-buffer
  shard and the 91.55 GiB-buffer shard. Reproduce with `docker run --rm --gpus all
  -v <hf-cache>:/cache/huggingface:ro littlecedar/dgx-spark-dsv41:exl3a` + a 10-line
  `safe_open([shard], framework="pt", device="cuda:0")` script.
- Reader fs probe (buffered vs `fadvise` vs `O_DIRECT`): summarized §7.8.1; harness
  was a throwaway (`/tmp`, removed); re-run command in that section.
- Upstream lever source: `.scratch/ds4/TUNING_BACKLOG.md` B1.3 (now marked REFUTED).

## 7. Implementation (2026-09-27) — `mods/bound-engram-cache`

Action-plan step 2 was implemented as a new, **opt-in** mod. It is **not listed in
any recipe** — adding it is a deliberate, per-recipe choice, because it buys no KV
(§1) and its only measured effect is to keep the host page cache from filling with
read-once Engram rows.

- **What it does.** Adds a uniform `POSIX_FADV_DONTNEED` after each gathered read in
  the installed `models/deepseek_v4_1/common/engram.py`, so the pages backing the
  just-read rows are evicted from the host page cache. One `fadvise` per *batch*
  (not per 264-byte row — `_kai_parallel_read` calls `_kai_pread_rows` once per job
  *part*), so the syscall cost is negligible even on the syscall-bound read path.
- **Why a post-patch, not an edit to `mount-dsv41-exl3-patches`.** That mod is
  md5-pinned to upstream `d45538f6` and fails closed on any drift; editing it would
  break the pin. This mod runs **after** it (list it later in `mods:`) and patches
  the *installed* file, refusing if the anchor is absent.
- **Fail-closed, idempotent.** md5-verified patcher; `--check` before write;
  anchored on the exact shipped `_kai_pread_rows` body (count must be 1, and the
  count of `preadv` calls must be 1, else it refuses); one backup
  (`engram.py.sparkrun-orig`); idempotence by the marker string, not timestamps;
  drops stale `__pycache__`.
- **Verified offline and BOOTED** (2026-09-27). Offline: the patcher applies to the
  shipped `mods/mount-dsv41-exl3-patches/files/engram.py` (the same file the sibling
  mod installs), `--check` → compatible → apply → `already patched`, and the patched
  module compiles. **Live:** a variant recipe (`zz-…-bound-engram-tp4-vllm`, the
  shipped TP=4 300K recipe + this mod, since deleted) booted on four idle Sparks
  (`.32`–`.35`): the mod logged `compatible → Patched → already patched`, the
  installed `engram.py` carried the marker and one `POSIX_FADV_DONTNEED`, weights
  loaded 48/48 with **no traceback**, the server reached readiness (~13 min), KV pool
  **4,105,477 tok / 31.9 GiB** vs the no-mod baseline **3,973,172 / 32.2 GiB**
  (within boot spread), `27*43 → 1161` correct, 8 prefill-heavy requests served with
  the fadvise in the hot path, and C1 decode ~33 t/s (baseline ~36). So the patch is
  **safe and neutral on the live stack**; all five EXL3 recipes now list it (after the
  patch mod), at the user's request, even though it buys no KV (§1).
- **Guards:** `tests/test_bound_engram_cache.py` — the patcher position, the write
  with the marker, the `DONTNEED` call, fail-closed on a bad anchor, refusal when a
  second `preadv` appears, and idempotence; plus negative controls (moving the marker
  off the write position, dropping the fadvise call). Ordering in the recipes is
  guarded by `tests/test_ds4_recipes.py::test_bound_engram_cache_after_patch_mod`.

Listed on all five recipes, after the patch mod, with the shared read flags unchanged:

```yaml
mods:
  - "@eugr/mods/drop-caches"
  - "@littlecedar/mods/mount-dsv41-exl3-patches"
  - "@littlecedar/mods/bound-engram-cache"     # bounds the row page cache (listed on all five)
env:
  DSV41_ENGRAM_DISK_THREADS: "32"
  DSV41_ENGRAM_DISK_CHUNK: "16"
```
