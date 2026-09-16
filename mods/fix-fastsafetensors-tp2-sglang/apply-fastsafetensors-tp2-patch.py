#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fix fastsafetensors weight loading for 1-GPU-per-node tensor parallel.

The bug
-------
``sglang.srt.model_loader.weight_utils.fastsafetensors_weights_iterator``
derives the CUDA device for the fastsafetensors from_blob pool from the
*global* process-group rank:

    pg = torch.distributed.group.WORLD
    rank = pg.rank()
    device = torch.device(f"cuda:{rank}")

On a single node with N GPUs (the topology upstream tests on) global rank
and local device index coincide, so the bug is invisible. DGX Spark is
1 GPU per node, so a TP=2 job spans two hosts whose local device indices
are both 0 while their world ranks are 0 and 1. The rank-1 process asks
for ``cuda:1`` on a host that has only ``cuda:0`` and dies with

    RuntimeError: CUDA error: invalid device ordinal

upstream: https://github.com/sgl-project/sglang/issues/29272
          (open, unmerged as of 2026-09-15; duplicate PRs #26597/#29717)

The fix
-------
Use the device the process was actually assigned. ``ModelRunner.__init__``
calls ``set_device(gpu_id)`` long before ``load_model()``, so
``torch.cuda.current_device()`` is already correct by the time this
iterator runs. ``rank`` itself stays in play for shard partitioning
(``rank_file_map``); only the device index was wrong.

Safety
------
Anchored, idempotent, and fail-closed: if the anchor text is not found
exactly once the script exits non-zero with an actionable message rather
than silently running unpatched. Candidates are compiled before being
written back, so a bad edit can never leave an unparseable module behind.
"""

import importlib.util
import os
import sys

MARKER = "sparkrun: global rank is not a local CUDA device index"

OLD = '    device = torch.device(f"cuda:{rank}")'
NEW = (
    "    # sparkrun: global rank is not a local CUDA device index on\n"
    "    # 1-GPU-per-node hosts such as DGX Spark (TP=2 spans two hosts,\n"
    "    # both with only cuda:0). Use the device assigned to this process.\n"
    "    # Upstream sgl-project/sglang#29272.\n"
    '    device = torch.device(f"cuda:{torch.cuda.current_device()}")'
)


def die(msg: str) -> "NoReturn":
    print(f"apply-fastsafetensors-tp2-patch: ERROR: {msg}")
    sys.exit(1)


def locate_weight_utils() -> str:
    """Resolve weight_utils.py from the installed sglang, not a hardcoded path.

    The pinned image installs sglang from /sgl-workspace/sglang, but other
    containers put it in site-packages. Derive it rather than assume.
    """
    spec = importlib.util.find_spec("sglang.srt.model_loader.weight_utils")
    if spec is None or not spec.origin:
        die(
            "cannot import sglang.srt.model_loader.weight_utils; is sglang "
            "installed and importable in this container?"
        )
    path = spec.origin
    if not os.path.isfile(path):
        die(f"weight_utils resolved to a non-file path: {path}")
    return os.path.realpath(path)


def main() -> int:
    path = locate_weight_utils()
    print(f"target: {path}")

    with open(path, encoding="utf-8") as fh:
        src = fh.read()

    # Idempotent: mods re-run on every launch against a fresh container,
    # and hand-patched trees must not trip over themselves.
    if MARKER in src:
        print("already patched; nothing to do")
        return 0
    if NEW in src:
        print("already patched (device line replaced); nothing to do")
        return 0

    hits = src.count(OLD)
    if hits != 1:
        die(
            f"expected the device anchor exactly once, found {hits}.\n"
            f"  anchor: {OLD}\n"
            f"The upstream code has moved or this container predates/postdates\n"
            f"the pinned build. Inspect manually:\n"
            f"  grep -n 'cuda:{{' {path}\n"
            f"and re-check https://github.com/sgl-project/sglang/issues/29272\n"
            f"before adapting the anchor. Refusing to run unpatched."
        )

    candidate = src.replace(OLD, NEW)

    # Never let a bad substitution land on disk.
    try:
        compile(candidate, path, "exec")
    except SyntaxError as exc:
        die(f"patched source failed to compile: {exc}")

    if MARKER not in candidate:
        die("substitution produced no marker; refusing to write")

    # Sanity check the two things we depend on staying correct.
    if "torch.cuda.current_device()" not in candidate:
        die("patched source is missing current_device()")

    # Mods run as root. os.replace() would hand the module to root, which can
    # break a container whose serve process runs as another uid. Capture the
    # original owner/mode and put them back.
    before = os.stat(path)

    tmp = f"{path}.sparkrun.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(candidate)
    os.chown(tmp, before.st_uid, before.st_gid)
    os.chmod(tmp, before.st_mode & 0o7777)
    os.replace(tmp, path)

    after = os.stat(path)
    print(
        "patched fastsafetensors device selection "
        f"(uid={after.st_uid} gid={after.st_gid} mode={oct(after.st_mode & 0o7777)})"
    )
    if (after.st_uid, after.st_gid) != (before.st_uid, before.st_gid):
        die("failed to preserve file ownership after patch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
