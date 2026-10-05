# bound-engram-cache

Bound the **Engram-on-disk reader's host page cache**: add a
`POSIX_FADV_DONTNEED` after each gathered read in the installed
`models/deepseek_v4_1/common/engram.py`, so read-once Engram rows are dropped
from the host page cache instead of accumulating. Run it on every rank (sparkrun
applies mods per node).

| | |
|:--|:--|
| Kind | **Opt-in, post-patch** mod. It edits the file `@littlecedar/mods/mount-dsv41-exl3-patches` installs. |
| License | AGPL-3.0-or-later (this repo). |
| Verified against | the shipped reader `mods/mount-dsv41-exl3-patches/files/engram.py`, 2026-09-27 (offline: `--check` → compatible → apply → `already patched`); **and BOOTED live** on 4 Sparks `.32`–`.35` — mod applied, 48/48 weights, ready, KV 4.11M vs 3.97M baseline (noise), `27*43→1161`, ~33 t/s C1. |

## Why it exists — and why it is optional

On GB10 the page cache is the *same* 128 GB pool as the weights and KV. Engram
row reads are read-once random 264-byte rows, and the shipped reader leaves the
backing pages in the page cache. Measured on the real on-disk path (`model-00047`,
random 64 KiB reads): buffered reads retain **+0.50 GiB**, `fadvise(DONTNEED)`
per read **+0.01 GiB**, `O_DIRECT` **+0.00 GiB**, with identical throughput
(100–109 MiB/s). So bounding the reader is correct and free.

**It buys nothing for KV.** Two live boots showed the launch *weight load* — not
serving — fills 45–58 GiB/node, `MemAvailable` stayed ≥41 GiB throughout, and a
load-window flusher bought +0.9 % (noise). This mod addresses only the small
serving-time term. It is boot-verified safe and neutral, and is now **listed on all
five `attic/ds4` EXL3 recipes (after the patch mod), at the user's request.
See `attic/ds4/MEMORY-RECLAIM-PLAN.md` §7.

## Why a post-patch mod, not an edit to the sibling

`mount-dsv41-exl3-patches` is **md5-pinned to upstream `d45538f6`** and fails
closed on any drift. Editing its vendored `engram.py` would break that pin and
its own `MD5SUMS.txt`. This mod runs *after* it and patches the installed file,
refusing if the shipped anchor is absent.

## Mechanics (fail-closed)

1. `patch_engram_fadvise.py` is **md5-verified** against `files/MD5SUMS.txt`.
2. `--check` runs **before** writing: exactly one `_kai_pread_rows` definition,
   exactly one `preadv` call inside it, exactly one anchor match — else refuse.
3. The target is backed up **once** to `<target>.sparkrun-orig`.
4. Idempotence is by the marker string `# sparkrun mod: bound-engram-cache v1`,
   not timestamps; a re-run is a no-op.
5. The patched module is `compile()`d before write, and stale `__pycache__`
   beside the target is removed.
6. `run.sh` refuses if the target is missing or is not the on-disk reader
   (`DSV41_ENGRAM_DISK` absent) — i.e. if the sibling patch mod was not listed
   first.

## Usage

List it **after** the patch mod:

```yaml
mods:
  - "@eugr/mods/drop-caches"
  - "@littlecedar/mods/mount-dsv41-exl3-patches"
  - "@littlecedar/mods/bound-engram-cache"
```

Keep the shared read flags consistent with the sibling's defaults
(`DSV41_ENGRAM_DISK_THREADS: "32"`, `DSV41_ENGRAM_DISK_CHUNK: "16"`) so the
throughput comparison is like-for-like.

## What the patch adds

```python
def _kai_pread_rows(fd, base, rel, lo, hi, row_bytes, buf) -> None:
    # sparkrun mod: bound-engram-cache v1
    for i in range(lo, hi):
        ...                      # unchanged gather loop
    # Bound the host page cache: drop the pages for the rows just read in this
    # batch. Once per call (per batch), so the syscall cost is negligible.
    if hi > lo:
        _lo_off = base + rel[lo] * row_bytes
        _hi_end = base + rel[hi - 1] * row_bytes + row_bytes
        try:
            _kai_os.posix_fadvise(
                fd, _lo_off, _hi_end - _lo_off, _kai_os.POSIX_FADV_DONTNEED
            )
        except (AttributeError, OSError):
            pass
```

The `fadvise` is additive bookkeeping: if it is unavailable or fails for any
reason it is swallowed, and the read itself is never affected.
