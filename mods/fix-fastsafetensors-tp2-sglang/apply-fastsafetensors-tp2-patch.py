#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fix fastsafetensors weight loading for 1-GPU-per-node tensor parallel.

Two independent defects live in
``sglang.srt.model_loader.weight_utils.fastsafetensors_weights_iterator``.
Both are invisible on the single-node, many-GPU machines upstream tests on,
and both are fatal on DGX Spark (one GPU per node, 128 GB of memory that
the GPU, CPU and OS all share).

Defect 1 -- wrong CUDA device under multi-node TP
-------------------------------------------------
The CUDA device for the fastsafetensors buffer pool is derived from the
*global* process-group rank:

    pg = torch.distributed.group.WORLD
    rank = pg.rank()
    device = torch.device(f"cuda:{rank}")

On one node with N GPUs, global rank and local device index coincide, so
the bug is invisible. DGX Spark is 1 GPU per node, so a TP=2 job spans two
hosts whose local device indices are both 0 while their world ranks are 0
and 1. The rank-1 process asks for ``cuda:1`` on a host that only has
``cuda:0`` and dies with "CUDA error: invalid device ordinal".

Fix: use the device this process was actually assigned.
``ModelRunner.__init__`` calls ``set_device(gpu_id)`` long before
``load_model()``, so ``torch.cuda.current_device()`` is already correct
here. ``rank`` still drives shard partitioning (``rank_file_map``); only
the device index was wrong.

upstream: https://github.com/sgl-project/sglang/issues/29272
          (open, unmerged; duplicate PRs #26597/#29717)

Defect 2 -- the device staging buffer is never released
-------------------------------------------------------
Per chunk of shards the iterator does:

    fb = loader.copy_files_to_device()
    try:
        keys = list(fb.key_to_rank_lidx.keys())
        for k in keys:
            yield k, t = fb.get_tensor(k) ...
    finally:
        pass                      # <-- nothing releases fb
    finally:
        loader.close()

``loader.close()`` only resets file-level bookkeeping. The GPU memory is
owned by the ``FilesBufferOnDevice`` returned by ``copy_files_to_device()``,
and fastsafetensors is explicit about that::

    "The returned FilesBufferOnDevice owns the backing storage for tensors
    created from it. Clone/copy those tensors before
    FilesBufferOnDevice.close() if the tensor data must outlive the buffer."

``FilesBufferOnDevice.close()`` is the documented release path (it calls
``free_dev_ptrs()`` on every loader). The ``finally: pass`` means it is
never called, so a chunk's staging buffer survives until Python happens to
collect ``fb`` -- and ``fb`` stays bound in the generator frame, so the
final chunk's buffer survives to the end of weight loading regardless.

On a discrete GPU this is merely wasteful. On a GB10 the staging buffer is
carved out of the same 128 GB pool as weights and the KV cache, so the
retention lands directly on the KV budget. Measured on this recipe with the
two load formats, same weights, same container:

    load_format=safetensors      avail after weights: 47.54 GB
    load_format=fastsafetensors  avail after weights: 20.78 GB

The ~26.9 GB difference is consistent with the last staged chunk still
holding its device buffers (103 progress ticks at tp=2; the two largest
shards on disk are 10.73 GB and 3.68 GB). Exact attribution of the
remainder is LIKELY rather than proven, but the total is a direct log
observation. That shortfall pushed ``--mem-fraction-static 0.85`` past the
point where any KV pool fits -- ``_profile_available_bytes`` computes
``available - pre*(1 - mem_fraction_static) - mm_reservation``, which falls
from +28.24 GB on safetensors to +1.48 GB here -- and the scheduler died
with "Loaded weights leave no GPU memory for the KV cache". Releasing the
buffer per chunk
restores the safetensors figure.

Fix: call ``fb.close()`` once every key in the chunk has been yielded and
consumed. That is safe because sglang's weight loaders copy into the
already-allocated parameter -- ``BasevLLMParameter._assert_and_load`` in
``srt/layers/parameter.py`` does ``self.data.copy_(loaded_weight)``, and the
parallel-load entry points (``load_row_parallel_weight``,
``load_column_parallel_weight``, ``load_merged_column_weight``,
``load_qkv_weight``) all route through it -- and the generator only resumes
after the consumer has returned from that copy.

Safety
------
Anchored, idempotent and fail-closed: each patch must match its anchor
exactly once or the script exits non-zero with an actionable message,
rather than silently launching unpatched and reproducing a crash someone
already debugged by hand. Candidates are compiled before being written
back, so a bad edit can never leave an unparseable module behind.

Set ``SPARKRUN_ALLOW_PARTIAL_FASTSAFETENSORS_PATCH=1`` to downgrade a
missed anchor to a warning when you deliberately want only one of the two
fixes (for example to A/B them against each other).
"""

import importlib.util
import os
import sys

# Anchor/marker pairs applied to weight_utils.py, in order. Each is applied
# independently so one already-upstream fix does not block the other.
MARKER_DEVICE = "sparkrun: global rank is not a local CUDA device index"
MARKER_BUFFER = "sparkrun: release the device staging buffer once consumed"

OLD_DEVICE = '    device = torch.device(f"cuda:{rank}")'
NEW_DEVICE = (
    "    # sparkrun: global rank is not a local CUDA device index on\n"
    "    # 1-GPU-per-node hosts such as DGX Spark (TP=2 spans two hosts,\n"
    "    # both with only cuda:0). Use the device assigned to this process.\n"
    "    # Upstream sgl-project/sglang#29272.\n"
    '    device = torch.device(f"cuda:{torch.cuda.current_device()}")'
)

# The `finally: pass` that strands the FilesBufferOnDevice. The surrounding
# lines are included so the anchor cannot accidentally match an unrelated
# try/finally elsewhere in this large module.
OLD_BUFFER = (
    "            try:\n"
    "                keys = list(fb.key_to_rank_lidx.keys())\n"
    "                for k in keys:\n"
    "                    t = fb.get_tensor(k)\n"
    "                    yield k, t\n"
    "            finally:\n"
    "                pass\n"
)
NEW_BUFFER = (
    "            try:\n"
    "                keys = list(fb.key_to_rank_lidx.keys())\n"
    "                for k in keys:\n"
    "                    t = fb.get_tensor(k)\n"
    "                    yield k, t\n"
    "            finally:\n"
    "                # sparkrun: release the device staging buffer once consumed\n"
    "                # (upstream leaves this as `pass`). On unified-memory hosts\n"
    "                # (GB10) the retained buffer comes straight out of the KV\n"
    "                # budget -- roughly 26.9 GB on this model at TP=2.\n"
    "                #\n"
    "                # The consumer's self.data.copy_() only *enqueues* a CUDA\n"
    "                # copy, so drain the stream first: freeing the source\n"
    "                # buffer under an in-flight copy would corrupt weights.\n"
    "                try:\n"
    "                    torch.cuda.synchronize()\n"
    "                except Exception:\n"
    "                    pass\n"
    "                try:\n"
    "                    fb.close()\n"
    "                except Exception:\n"
    "                    pass\n"
)

PATCHES = (
    ("device-selection", MARKER_DEVICE, OLD_DEVICE, NEW_DEVICE),
    ("staging-buffer-release", MARKER_BUFFER, OLD_BUFFER, NEW_BUFFER),
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

    partial_ok = (
        os.environ.get("SPARKRUN_ALLOW_PARTIAL_FASTSAFETENSORS_PATCH", "") == "1"
    )

    candidate = src
    applied: list[str] = []
    skipped: list[str] = []
    missed: list[str] = []

    for name, marker, old, new in PATCHES:
        # Idempotent: mods re-run on every launch against a fresh container,
        # and a hand-patched tree must not trip over itself.
        if marker in candidate or new in candidate:
            skipped.append(name)
            print(f"[{name}] already patched; skipping")
            continue

        hits = candidate.count(old)
        if hits != 1:
            missed.append(name)
            print(
                f"[{name}] anchor found {hits} time(s), expected exactly 1; "
                "skipping this patch"
            )
            continue

        before = candidate
        candidate = candidate.replace(old, new)
        try:
            # Never let a bad substitution land on disk, even transiently.
            compile(candidate, path, "exec")
        except SyntaxError as exc:
            candidate = before
            die(f"[{name}] patched source failed to compile: {exc}")

        applied.append(name)
        print(f"[{name}] patch staged")

    if not applied and not skipped:
        die(
            "no patch applied; every anchor missed.\n"
            f"  missed: {', '.join(missed)}\n"
            "The upstream code has moved, or this container predates/postdates\n"
            "the pinned build. Inspect manually:\n"
            f"  grep -n 'cuda:{{\\|finally:' {path}\n"
            "and re-check https://github.com/sgl-project/sglang/issues/29272\n"
            "before adapting the anchors. Refusing to launch unpatched."
        )

    if missed and not partial_ok:
        die(
            "incomplete patch; refusing to launch half-fixed.\n"
            f"  applied: {', '.join(applied) or 'none'}\n"
            f"  skipped: {', '.join(skipped) or 'none'}\n"
            f"  missed:  {', '.join(missed)}\n"
            "A partial fix can mask the failure you are trying to chase: keeping\n"
            "the staging-buffer leak while losing the device fix reproduces the\n"
            "'invalid device ordinal' crash, and the reverse reproduces the KV\n"
            "OOM. Fix the anchor, or set\n"
            "  SPARKRUN_ALLOW_PARTIAL_FASTSAFETENSORS_PATCH=1\n"
            "to proceed deliberately (for example to A/B the two fixes)."
        )

    if missed and partial_ok:
        print(
            f"WARNING: partial patch allowed by environment; missed: {', '.join(missed)}"
        )

    if candidate == src:
        print("nothing to write (all patches already present)")
        return 0

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
        "patched: %s%s | uid=%d gid=%d mode=%s"
        % (
            ", ".join(applied),
            f" (already present: {', '.join(skipped)})" if skipped else "",
            after.st_uid,
            after.st_gid,
            oct(after.st_mode & 0o7777),
        )
    )
    if (after.st_uid, after.st_gid) != (before.st_uid, before.st_gid):
        die("failed to preserve file ownership after patch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
