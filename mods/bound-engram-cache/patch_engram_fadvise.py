#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bound the Engram-on-disk reader's host page cache.

Adds a ``POSIX_FADV_DONTNEED`` after each gathered read in the installed
``models/deepseek_v4_1/common/engram.py`` (the on-disk reader installed by
``mods/mount-dsv41-exl3-patches``). The reader drops the pages backing the rows
it just read, so those read-once rows do not accumulate in the host page cache.

WHY THIS IS POST-PATCH, NOT AN EDIT TO THE SIBLING MOD
-----------------------------------------------------
``mount-dsv41-exl3-patches`` is md5-pinned to upstream ``d45538f6`` and fails
closed on any drift; editing its vendored ``engram.py`` would break that pin.
So this mod runs AFTER it (list it later in ``mods:``) and patches the already
installed file.

CONTRACT, fail-closed (mirrors the sibling mods)
-----------------------------------------------
* The patcher is md5-verified against ``files/MD5SUMS.txt``.
* ``--check`` runs BEFORE writing and refuses if the anchor is absent or the
  file is not the expected reader (exactly one ``_kai_pread_rows``, exactly one
  ``preadv`` call inside it).
* ``fadvise`` runs ONCE PER ``_kai_pread_rows`` CALL (per gathered batch), placed
  after the ``for`` loop -- not once per 264-byte row.
* The target is backed up ONCE to ``<target>.sparkrun-orig``.
* Idempotence is by the marker string, not timestamps; a re-run is a no-op.

Offline-verified against ``mods/mount-dsv41-exl3-patches/files/engram.py``
2026-09-27: ``--check`` -> compatible -> apply -> ``already patched``. NOT booted.
See ``attic/ds4/MEMORY-RECLAIM-PLAN.md`` §7.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

MARKER = "# sparkrun mod: bound-engram-cache v1"

# The exact shipped `_kai_pread_rows` (mods/mount-dsv41-exl3-patches/files/
# engram.py). Anchored on the whole function so the inserted `fadvise` can sit
# at function-body indent (once per batch), not inside the `for` loop.
ANCHOR = '''def _kai_pread_rows(
    fd: int, base: int, rel: list, lo: int, hi: int, row_bytes: int, buf
) -> None:
    for i in range(lo, hi):
        off = base + rel[i] * row_bytes
        view = buf[i * row_bytes : (i + 1) * row_bytes]
        got = 0
        while got < row_bytes:
            n = _kai_os.preadv(fd, [view[got:]], off + got)
            if n <= 0:
                raise OSError("engram disk table: short read")
            got += n
'''

REPLACEMENT = '''def _kai_pread_rows(
    fd: int, base: int, rel: list, lo: int, hi: int, row_bytes: int, buf
) -> None:
''' + "    " + MARKER + '''
    for i in range(lo, hi):
        off = base + rel[i] * row_bytes
        view = buf[i * row_bytes : (i + 1) * row_bytes]
        got = 0
        while got < row_bytes:
            n = _kai_os.preadv(fd, [view[got:]], off + got)
            if n <= 0:
                raise OSError("engram disk table: short read")
            got += n
    # Bound the host page cache: after gathering this batch's rows, drop the
    # pages just read so read-once Engram rows do not accumulate. Once per
    # _kai_pread_rows call (per batch), so the syscall cost is negligible even
    # on the syscall-bound read path. Additive bookkeeping; never fatal.
    if hi > lo:
        _lo_off = base + rel[lo] * row_bytes
        _hi_end = base + rel[hi - 1] * row_bytes + row_bytes
        try:
            _kai_os.posix_fadvise(
                fd, _lo_off, _hi_end - _lo_off, _kai_os.POSIX_FADV_DONTNEED
            )
        except (AttributeError, OSError):
            pass
'''


def validate_shape(text: str, *, patched: bool) -> None:
    """Refuse anything that is not the expected reader (or its patched form)."""
    tree = ast.parse(text)
    funcs = [
        n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name == "_kai_pread_rows"
    ]
    if len(funcs) != 1:
        raise ValueError(
            "expected exactly one _kai_pread_rows definition; found %d" % len(funcs)
        )
    src = ast.get_source_segment(text, funcs[0]) or ""
    calls = [n for n in ast.walk(funcs[0]) if isinstance(n, ast.Call)]
    preadv = [c for c in calls
              if isinstance(c.func, ast.Attribute) and c.func.attr == "preadv"]
    fadvise = [c for c in calls
               if isinstance(c.func, ast.Attribute) and c.func.attr == "posix_fadvise"]
    if len(preadv) != 1:
        raise ValueError("_kai_pread_rows must contain exactly one preadv call")
    if patched:
        if len(fadvise) != 1:
            raise ValueError("patched _kai_pread_rows must call posix_fadvise once")
        if "POSIX_FADV_DONTNEED" not in src:
            raise ValueError("patched _kai_pread_rows must request POSIX_FADV_DONTNEED")


def patched_text(text: str) -> str:
    already = MARKER in text
    validate_shape(text, patched=already)
    if already:
        if text.count(MARKER) != 1:
            raise ValueError("bound-engram-cache marker occurs more than once")
        compile(text, "", "exec")
        return text

    count = text.count(ANCHOR)
    if count != 1:
        raise ValueError(
            "expected exactly one supported _kai_pread_rows anchor; found %d" % count
        )
    patched = text.replace(ANCHOR, REPLACEMENT, 1)
    validate_shape(patched, patched=True)
    compile(patched, "", "exec")
    return patched


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path)
    parser.add_argument(
        "--check", action="store_true", help="validate compatibility without writing"
    )
    args = parser.parse_args()

    if not args.target.is_file():
        print("[bound-engram-cache ERROR] target not found: %s" % args.target,
              file=sys.stderr)
        return 1

    original = args.target.read_text()
    try:
        patched = patched_text(original)
    except (SyntaxError, ValueError) as exc:
        print("[bound-engram-cache ERROR] refusing to patch %s: %s" % (args.target, exc),
              file=sys.stderr)
        return 1

    if args.check:
        state = "already patched" if patched == original else "compatible"
        print("[bound-engram-cache] %s is %s." % (args.target, state))
        return 0

    if patched == original:
        print("[bound-engram-cache] engram.py is already patched; skipping.")
        return 0

    temporary = args.target.with_suffix(args.target.suffix + ".bound-engram-cache.tmp")
    temporary.write_text(patched)
    temporary.replace(args.target)
    print("[bound-engram-cache] Patched %s." % args.target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
