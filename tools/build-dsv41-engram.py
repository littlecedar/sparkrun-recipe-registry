#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build the DeepSeek-V4.1-Flash (``ds4``) Engram tables from an *online* Hugging
Face repo, without downloading or unpacking the model weights into a local HF
cache.

Why this exists
---------------
DeepSeek-V4.1-Flash carries two ~95 GiB Engram embedding tables (layers 1 and 14;
``engram.embed.weight`` F8_E4M3 x256 and ``engram.embed.scale`` F8_E8M0 x8 per
row).  The TensorFold TP=2 lane reads them as safetensors from ``TF_DS_ENGRAM``
(see ``tensorfold.families.deepseek_v41.cuda.model.Engram``: it globs
``*.safetensors`` and reads row ``i`` at ``8 + header_len + data_offsets[0] +
i*row_bytes``).  Those two tables live in the *official*
``deepseek-ai/DeepSeek-V4.1-Flash`` repo, shards 47 and 48 -- a ~285 GB repo.
Pulling it, or ``huggingface_hub``-snapshotting it, just to reach 189 GiB of
Engram means materializing the full checkpoint.

This tool instead speaks HTTP byte-range GETs straight to the HF CDN, reads only
the bytes it needs (the shard headers to locate the four tensors, then their
ranges), and writes a small self-contained safetensors directory that the TP=2
engine consumes verbatim.  Nothing is unpacked into the local HF cache, and the
output is byte-identical, row for row, to the checkpoint's tables.

What does *not* ship here: the ``engram.wkv`` / ``engram.q_weight`` /
``engram.k_weight`` tensors.  Those belong to the *quantized* weights and are
already present in the EXL3 checkpoint the TP=2 lane serves from.

Outputs
-------
``--format safetensors`` (default)  one ``engram-l<L>.safetensors`` per layer,
    each holding that layer's ``.engram.embed.weight`` and ``.engram.embed.scale``
    as two contiguous planes.  This is what TensorFold's ``Engram`` reader wants.

``--format packed``  the knapcio TP=4 lane's repacked shards,
    ``engram-l<L>-r<R>of<TP>.bin``: a 4096-byte header (``<6Q`` = magic
    ``DSV1EN41``, layer, lo, hi, rows, 264) then ``(rows/TP)`` records of
    264 bytes (weight[256] + scale[8]).  Provided for parity with
    ``knapcio/.../scripts/pack_engram.py`` when a packed table is what is wanted.

Both formats are resumable: re-run after an interruption and it continues where
it stopped instead of re-fetching.

Examples
--------
Pre-warm the TP=2 lane's Engram dir on one node (189 GiB, ~4-8 min over the CDN)::

    python3 build-dsv41-engram.py \\
        --out ~/.cache/huggingface/hub/dsv41-engram --workers 16

Fetch only the first layer, 4096 rows, for a smoke test::

    python3 build-dsv41-engram.py --layers 1 --limit-rows 4096 --out /tmp/engram

Build from an already-local snapshot (no network; also used by the tests)::

    python3 build-dsv41-engram.py --source-dir /path/to/snapshot --out /tmp/engram

Notes
-----
* Stdlib only (``urllib``), so it runs on a bare GB10 host or inside the serving
  image, which ships no ``huggingface_hub`` CLI guarantee but always has python3.
* Memory is bounded: each in-flight transfer holds at most ``--chunk-mb`` and the
  pool holds ``--workers`` of them; written pages are advised ``DONTNEED`` so a
  121 GB unified-memory node does not need 189 GB of page cache.
* ``--token`` / ``HF_TOKEN`` authenticate gated/private repos.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

MAGIC = 0x31344E4531565344  # "DSV41EN1", little-endian on disk
PACKED_HEADER_BYTES = 4096
WEIGHT_BYTES = 256
SCALE_BYTES = 8
PACKED_ROW_BYTES = WEIGHT_BYTES + SCALE_BYTES  # 264
DEFAULT_REPO = "deepseek-ai/DeepSeek-V4.1-Flash"
DEFAULT_ENDPOINT = "https://huggingface.co"
DEFAULT_LAYERS = (1, 14)
# The TensorFold TP=2 launcher's in-container ENGRAM_DIR default
# (mods/tensorfold-dsv41-launcher); writing here is what puts the tables on the
# lane's `TF_DS_ENGRAM` path inside the container.
DEFAULT_OUT = "/cache/huggingface/hub/dsv41-engram"
# The same location on a *host* (the container's /cache/huggingface is the host's
# ~/.cache/huggingface, bind-mounted).  A pre-warm run straight on a node wants
# this, not the container path.
HOST_OUT = "~/.cache/huggingface/hub/dsv41-engram"


def default_out() -> str:
    """The lane's Engram path, resolved for a container or a host run.

    ``TF_DS_ENGRAM`` wins; else the container path when ``/cache/huggingface`` is
    mounted; else the host's ``~/.cache/huggingface/hub/dsv41-engram`` -- the
    same bytes, reached without a container so a slow-link pre-warm can run
    detached from any recipe or launch lifecycle.
    """
    env = os.environ.get("TF_DS_ENGRAM")
    if env:
        return env
    if Path("/cache/huggingface/hub").is_dir():
        return DEFAULT_OUT
    return HOST_OUT
# The index names tensors; the reader matches on these suffixes.
WEIGHT_SUFFIX = "engram.embed.weight"
SCALE_SUFFIX = "engram.embed.scale"


# --------------------------------------------------------------------------- #
# Logging / errors
# --------------------------------------------------------------------------- #
_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(f"[engram] {msg}", flush=True)


class EngramError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# Source: an online HF repo (HTTP range GETs) or a local snapshot directory
# --------------------------------------------------------------------------- #
class HttpSource:
    """Byte-range reads against a Hugging Face repo over HTTP."""

    def __init__(self, repo: str, revision: str, endpoint: str, token: str | None,
                 retries: int = 8, timeout: int = 120) -> None:
        self.repo = repo
        self.revision = revision
        self.endpoint = endpoint.rstrip("/")
        self.token = token
        self.retries = retries
        self.timeout = timeout

    def url(self, filename: str) -> str:
        return f"{self.endpoint}/{self.repo}/resolve/{self.revision}/{filename}"

    def _request(self, url: str, lo: int | None, hi: int | None):
        headers = {"User-Agent": "sparkrun-dsv41-engram/1"}
        if lo is not None:
            headers["Range"] = f"bytes={lo}-{hi}"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return urllib.request.Request(url, headers=headers)

    def _open(self, url: str, lo: int | None, hi: int | None):
        last = None
        for attempt in range(self.retries):
            try:
                resp = urllib.request.urlopen(self._request(url, lo, hi), timeout=self.timeout)
                if lo is not None and resp.status != 206:
                    raise EngramError(
                        f"server ignored Range for {url} (status {resp.status}); "
                        "cannot do byte-range reads")
                return resp
            except urllib.error.HTTPError as exc:  # noqa: PERF203
                last = exc
                if exc.code in (401, 403, 404):
                    raise EngramError(
                        f"HTTP {exc.code} for {url}: check the repo id/revision"
                        + (" and --token" if exc.code in (401, 403) else "")) from exc
                if exc.code == 429:
                    # HF rate-limits sustained request *rates*. One request per
                    # segment (not per chunk) keeps the count low; when it still
                    # trips, back off hard and honour Retry-After.
                    delay = float(exc.headers.get("Retry-After") or 0) or min(5 * 2 ** attempt, 180)
                    log(f"HTTP 429 from HF; sleeping {delay:.0f}s "
                        f"(attempt {attempt + 1}/{self.retries})")
                    time.sleep(delay + 0.25 * attempt)
                    continue
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                last = exc
            time.sleep(min(2 ** attempt, 20) + 0.1 * attempt)
        raise EngramError(f"giving up on {url} ({lo}-{hi}): {last}")

    class _Range:
        """A bounded reader over one open response (or local file handle)."""

        def __init__(self, resp, remaining: int) -> None:
            self._resp = resp
            self._left = remaining

        def read(self, n: int = -1) -> bytes:
            if self._left <= 0:
                return b""
            if n < 0 or n > self._left:
                n = self._left
            data = self._resp.read(n)
            self._left -= len(data)
            return data

        def close(self) -> None:
            close = getattr(self._resp, "close", None)
            if close is not None:
                close()

        def __enter__(self):
            return self

        def __exit__(self, *exc) -> None:
            self.close()

    def open_range(self, filename: str, offset: int, length: int):
        """One HTTP request for exactly [offset, offset+length)."""
        if length <= 0:
            return HttpSource._Range(_EmptyReader(), 0)
        resp = self._open(self.url(filename), offset, offset + length - 1)
        return HttpSource._Range(resp, length)

    def read(self, filename: str, offset: int, length: int) -> bytes:
        with self.open_range(filename, offset, length) as r:
            data = r.read(length)
        if len(data) != length:
            raise EngramError(
                f"short read from {filename} at {offset}: got {len(data)} want {length}")
        return data

    def index(self, filename: str) -> dict:
        """A small whole-file fetch (the safetensors index json)."""
        resp = self._open(self.url(filename), None, None)
        try:
            data = resp.read()
        finally:
            resp.close()
        return json.loads(data)


class _EmptyReader:
    def read(self, n: int = -1) -> bytes:  # pragma: no cover - trivial
        return b""

    def close(self) -> None:
        pass


class LocalSource:
    """Reads a checkpoint from a local directory (offline / tests)."""

    def __init__(self, root: str) -> None:
        self.root = Path(root)
        if not self.root.is_dir():
            raise EngramError(f"--source-dir is not a directory: {self.root}")

    def _path(self, filename: str) -> Path:
        p = self.root / filename
        if not p.is_file():
            raise EngramError(f"missing in --source-dir: {p}")
        return p

    class _Range:
        def __init__(self, fh, remaining: int) -> None:
            self._fh = fh
            self._left = remaining

        def read(self, n: int = -1) -> bytes:
            if self._left <= 0:
                return b""
            if n < 0 or n > self._left:
                n = self._left
            data = self._fh.read(n)
            self._left -= len(data)
            return data

        def close(self) -> None:
            self._fh.close()

        def __enter__(self):
            return self

        def __exit__(self, *exc) -> None:
            self.close()

    def open_range(self, filename: str, offset: int, length: int):
        fh = self._path(filename).open("rb", buffering=0)
        fh.seek(offset)
        return LocalSource._Range(fh, max(0, length))

    def read(self, filename: str, offset: int, length: int) -> bytes:
        if length <= 0:
            return b""
        with self.open_range(filename, offset, length) as r:
            data = r.read(length)
        if len(data) != length:
            raise EngramError(f"short read from {filename} at {offset}")
        return data

    def index(self, filename: str) -> dict:
        return json.loads(self._path(filename).read_text())


# --------------------------------------------------------------------------- #
# Locating the engram tensors
# --------------------------------------------------------------------------- #
def find_engram_tensors(source, repo_index: str, layers: list[int]) -> dict:
    """{tensor_name: (shard, data_offset, dtype, shape)} for the wanted layers.

    Prefers the repo's ``model.safetensors.index.json`` (one small fetch); falls
    back to reading each ``*.safetensors`` header, which is what the online
    reader does anyway.  Only the four ``engram.embed.{weight,scale}`` tensors
    are returned: the sibling ``engram.wkv`` / ``engram.q_weight`` /
    ``engram.k_weight`` belong to the quantized weights, not the tables.
    """
    wanted: dict[str, str] = {}
    for layer in layers:
        wanted[f"layers.{layer}.{WEIGHT_SUFFIX}"] = f"layers.{layer}.{WEIGHT_SUFFIX}"
        wanted[f"layers.{layer}.{SCALE_SUFFIX}"] = f"layers.{layer}.{SCALE_SUFFIX}"
    wanted = set(wanted)

    weight_map: dict[str, str] | None = None
    try:
        idx = source.index(repo_index)
        weight_map = idx.get("weight_map") or {}
        log(f"index: {repo_index} ({len(weight_map)} tensors)")
    except (EngramError, ValueError) as exc:
        log(f"index unavailable ({exc}); scanning shard headers")

    if weight_map is not None:
        if wanted <= set(weight_map):
            shards = sorted({weight_map[n] for n in wanted})
        else:
            # A wanted tensor is absent from the index: read every shard's
            # header so the error names the real miss instead of the fallback.
            shards = sorted(set(weight_map.values()))
    else:
        shards = _discover_shards(source, repo_index)

    out: dict[str, tuple[str, int, str, list[int]]] = {}
    # group by shard so each header is read once
    by_shard: dict[str, list[str]] = {}
    if weight_map is not None:
        for name in wanted:
            if name in weight_map:
                by_shard.setdefault(weight_map[name], []).append(name)
    for shard in shards:
        header_len, header = _read_shard_header(source, shard)
        base = 8 + header_len
        names = by_shard.get(shard) or sorted(header)
        for name in names:
            if name not in wanted or name not in header:
                continue
            e = header[name]
            lo, _hi = e["data_offsets"]
            out[name] = (shard, base + lo, e["dtype"], list(e["shape"]))
            if len(out) == len(wanted):
                break
        if len(out) == len(wanted):
            break

    missing = wanted - set(out)
    if missing:
        raise EngramError(
            "could not locate " + ", ".join(sorted(missing))
            + " (is this the right repo/revision, and are the layers correct?)")
    return out


def _discover_shards(source, repo_index: str) -> list[str]:
    """Candidate shard names when there is no usable index.

    A local directory is globbed; an HTTP source is asked for its file tree.
    """
    if isinstance(source, LocalSource):
        shards = sorted(p.name for p in source.root.glob("*.safetensors"))
        if shards:
            log(f"local dir: {len(shards)} safetensors shards")
            return shards
    if isinstance(source, HttpSource):
        try:
            url = f"{source.endpoint}/api/models/{source.repo}/tree/{source.revision}?recursive=1"
            req = urllib.request.Request(url, headers={"User-Agent": "sparkrun-dsv41-engram/1"})
            if source.token:
                req.add_header("Authorization", f"Bearer {source.token}")
            with urllib.request.urlopen(req, timeout=source.timeout) as resp:
                tree = json.loads(resp.read())
            shards = sorted(e["path"] for e in tree
                            if e.get("type") == "file" and e["path"].endswith(".safetensors"))
            if shards:
                log(f"tree API: {len(shards)} safetensors shards")
                return shards
        except (urllib.error.URLError, ValueError, KeyError) as exc:
            log(f"tree API unavailable ({exc}); scanning known shard names")
    raise EngramError(
        "no model.safetensors.index.json and no shard list: pass a repo with the "
        "index, or --shards explicitly")


def _read_shard_header(source, shard: str) -> tuple[int, dict]:
    raw = source.read(shard, 0, 8)
    (header_len,) = struct.unpack("<Q", raw)
    header = source.read(shard, 8, header_len)
    return header_len, json.loads(header)


# --------------------------------------------------------------------------- #
# safetensors writer (multi-region parallel ranged copy)
# --------------------------------------------------------------------------- #
def build_safetensors_header(entries: list[tuple[str, str, list[int], int]]) -> bytes:
    """entries: (name, dtype, shape, byte_length) in output plane order."""
    d: dict[str, dict] = {}
    off = 0
    for name, dtype, shape, length in entries:
        d[name] = {"dtype": dtype, "shape": list(shape), "data_offsets": [off, off + length]}
        off += length
    body = json.dumps(d, separators=(",", ":"), sort_keys=True).encode()
    body += b" " * ((-len(body)) % 8)  # pad so data starts 8-byte aligned
    return struct.pack("<Q", len(body)) + body


def copy_range(source, filename: str, src_off: int, dst_fd: int, dst_off: int,
               length: int, advisory_dontneed: bool = True) -> None:
    """Stream one source range to the destination at dst_off.

    One open/request for the whole segment (a low request count is what keeps
    Hugging Face from rate-limiting, 429); the bytes are pulled in bounded ticks
    so the resident set stays small on a unified-memory node.
    """
    if length <= 0:
        return
    tick = 4 << 20
    with source.open_range(filename, src_off, length) as r:
        pos = 0
        while pos < length:
            piece = r.read(min(tick, length - pos))
            if not piece:
                raise EngramError(f"short read from {filename} at {src_off + pos}")
            os.pwrite(dst_fd, piece, dst_off + pos)
            pos += len(piece)
    if advisory_dontneed:
        try:
            os.posix_fadvise(dst_fd, dst_off, length, os.POSIX_FADV_DONTNEED)
        except (AttributeError, OSError):
            pass


def _load_progress(path: Path) -> set[int]:
    if path.is_file():
        try:
            return set(json.loads(path.read_text()).get("done", []))
        except (ValueError, OSError):
            pass
    return set()


def _save_progress(path: Path, done: set[int]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps({"done": sorted(done)}))
    os.replace(tmp, path)


def build_safetensors(source, tensors: dict, out_dir: Path, layers: list[int],
                      workers: int, segment: int, limit_rows: int | None,
                      resume: bool) -> list[Path]:
    produced: list[Path] = []
    tasks = []
    for layer in layers:
        wname = f"layers.{layer}.{WEIGHT_SUFFIX}"
        sname = f"layers.{layer}.{SCALE_SUFFIX}"
        wshard, woff, wdtype, wshape = tensors[wname]
        sshard, soff, sdtype, sshape = tensors[sname]
        if wshape[0] != sshape[0]:
            raise EngramError(f"layer {layer}: weight/scale row count differs "
                              f"({wshape[0]} vs {sshape[0]})")
        rows = wshape[0] if limit_rows is None else min(limit_rows, wshape[0])
        wrow = _row_bytes(wshape)
        srow = _row_bytes(sshape)
        if wrow != WEIGHT_BYTES or srow != SCALE_BYTES:
            raise EngramError(
                f"layer {layer}: unexpected row sizes {wrow}/{srow} "
                f"(want {WEIGHT_BYTES}/{SCALE_BYTES}); is this a different checkpoint?")
        wlen, slen = rows * wrow, rows * srow
        header = build_safetensors_header([
            (wname, wdtype, [rows, wrow], wlen),
            (sname, sdtype, [rows, srow], slen),
        ])
        dst = out_dir / f"engram-l{layer}.safetensors"
        partial = dst.with_suffix(".partial")
        data_off = len(header)
        total = data_off + wlen + slen
        # regions: (label, src_shard, src_off, dst_off, length)
        regions = [
            (f"l{layer}.weight", wshard, woff, data_off, wlen),
            (f"l{layer}.scale", sshard, soff, data_off + wlen, slen),
        ]
        tasks.append((layer, dst, partial, header, total, regions))

    # Idempotent: a layer whose final file already passes the offline check is
    # left untouched, so a re-run fetches nothing.
    if resume:
        kept = []
        for task in tasks:
            if check_output(out_dir, [task[0]], "safetensors", 1, 0):
                log(f"layer {task[0]}: already complete; skipping")
                produced.append(task[1])
            else:
                kept.append(task)
        tasks = kept
    if not tasks:
        return produced

    # A global segment list across all output files, one pool draining it.
    segments: list[tuple[Path, str, int, int, int]] = []  # (partial, shard, src_off, dst_off, length)
    seg_index: dict[Path, list[int]] = {}
    for _layer, _dst, partial, _header, _total, regions in tasks:
        idxs = []
        for _label, shard, src_off, dst_off, length in regions:
            start = 0
            while start < length:
                n = min(segment, length - start)
                idxs.append(len(segments))
                segments.append((partial, shard, src_off + start, dst_off + start, n))
                start += n
        seg_index[partial] = idxs

    # Prepare the output files: reserve the header + full size up front so every
    # segment has a fixed destination offset, and the resume cursors stay valid.
    for _layer, dst, partial, header, total, _regions in tasks:
        if not resume:
            partial.unlink(missing_ok=True)
            partial.with_suffix(".partial.progress").unlink(missing_ok=True)
        fd = os.open(partial, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            os.ftruncate(fd, total)
            if len(header) and _needs_header(fd):
                os.pwrite(fd, header, 0)
        finally:
            os.close(fd)

    progress_path = out_dir / ".engram-progress.json"
    done = _load_progress(progress_path) if resume else set()
    todo = [i for i in range(len(segments)) if i not in done]
    log(f"safetensors: {len(tasks)} file(s), {len(segments)} segments, "
        f"{len(todo)} to fetch, {workers} workers")
    if todo:
        _run_segments(source, segments, todo, done, progress_path, workers)

    # Publish only once every file is complete: the engine globs the output dir,
    # and it must never see layer 1 present while layer 14 is still a partial.
    for _layer, dst, partial, _header, total, _regions in tasks:
        if partial.stat().st_size != total:
            raise EngramError(f"{partial} size {partial.stat().st_size} != expected {total}")
    for _layer, dst, partial, _header, _total, _regions in tasks:
        os.replace(partial, dst)
        produced.append(dst)
        log(f"wrote {dst} ({dst.stat().st_size / 2**30:.1f} GiB)")
    progress_path.unlink(missing_ok=True)
    return produced


def _needs_header(fd: int) -> bool:
    """False if the reserved header slot is already populated (resume)."""
    first8 = os.pread(fd, 8, 0)
    return len(first8) < 8 or struct.unpack("<Q", first8)[0] == 0


def _run_segments(source, segments, todo, done, progress_path, workers) -> None:
    lock = threading.Lock()
    failures: list[BaseException] = []

    def work(i: int) -> None:
        partial, shard, src_off, dst_off, length = segments[i]
        fd = os.open(partial, os.O_RDWR)
        try:
            copy_range(source, shard, src_off, fd, dst_off, length)
        finally:
            os.close(fd)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futs = {pool.submit(work, i): i for i in todo}
        for fut in as_completed(futs):
            try:
                fut.result()
            except BaseException as exc:  # noqa: BLE001 - recorded, re-raised below
                failures.append(exc)
                continue
            with lock:
                done.add(futs[fut])
                _save_progress(progress_path, done)
    if failures:
        raise EngramError(f"{len(failures)} segment(s) failed; re-run to resume: {failures[0]}")


def _row_bytes(shape: list[int]) -> int:
    n = 1
    for d in shape[1:]:
        n *= d
    return n


# --------------------------------------------------------------------------- #
# packed 264-B writer (knapcio TP=4 layout)
# --------------------------------------------------------------------------- #
def build_packed(source, tensors: dict, out_dir: Path, layers: list[int],
                 tp: int, rank: int, limit_rows: int | None, chunk: int) -> list[Path]:
    if not 0 <= rank < tp:
        raise EngramError(f"--rank {rank} out of range for --tensor-parallel {tp}")
    produced = []
    for layer in layers:
        wname = f"layers.{layer}.{WEIGHT_SUFFIX}"
        sname = f"layers.{layer}.{SCALE_SUFFIX}"
        wshard, woff, _wdtype, wshape = tensors[wname]
        sshard, soff, _sdtype, sshape = tensors[sname]
        rows = wshape[0]
        wrow, srow = _row_bytes(wshape), _row_bytes(sshape)
        lo, hi = rows * rank // tp, rows * (rank + 1) // tp
        if limit_rows is not None:
            hi = min(hi, lo + limit_rows)
        count = hi - lo
        dst = out_dir / f"engram-l{layer}-r{rank}of{tp}.bin"
        partial = dst.with_suffix(".partial")
        expected = PACKED_HEADER_BYTES + count * PACKED_ROW_BYTES
        have_rows = 0
        if partial.is_file():
            have_rows = max(0, (partial.stat().st_size - PACKED_HEADER_BYTES) // PACKED_ROW_BYTES)
            if have_rows > count:
                have_rows = 0
        header = bytearray(PACKED_HEADER_BYTES)
        struct.pack_into("<6Q", header, 0, MAGIC, layer, lo, lo + count, rows, PACKED_ROW_BYTES)
        mode = "r+b" if have_rows else "wb"
        log(f"packed layer {layer} rank {rank}/{tp}: rows [{lo},{lo + count}), "
            f"resume at {have_rows}, {expected / 2**30:.1f} GiB")
        with partial.open(mode, buffering=0) as f:
            if not have_rows:
                f.write(header)
            else:
                f.seek(PACKED_HEADER_BYTES + have_rows * PACKED_ROW_BYTES)
            block_rows = max(1, min(count - have_rows, max(1, chunk // PACKED_ROW_BYTES)))
            for start in range(have_rows, count, block_rows):
                n = min(block_rows, count - start)
                src_row = lo + start
                weight = source.read(wshard, woff + src_row * wrow, n * wrow)
                scale = source.read(sshard, soff + src_row * srow, n * srow)
                block = bytearray(n * PACKED_ROW_BYTES)
                for i in range(n):
                    o = i * PACKED_ROW_BYTES
                    block[o:o + wrow] = weight[i * wrow:(i + 1) * wrow]
                    block[o + wrow:o + PACKED_ROW_BYTES] = scale[i * srow:(i + 1) * srow]
                f.write(block)
                if (start // block_rows) % 64 == 0:
                    log(f"packed layer {layer}: {start + n}/{count} rows")
            f.flush()
            os.fsync(f.fileno())
        if partial.stat().st_size != expected:
            raise EngramError(f"{partial} size {partial.stat().st_size} != {expected}")
        os.replace(partial, dst)
        produced.append(dst)
        log(f"wrote {dst} ({expected / 2**30:.1f} GiB)")
    return produced


# --------------------------------------------------------------------------- #
# Verification: compare random rows of the output against the source
# --------------------------------------------------------------------------- #
def verify_rows(source, tensors: dict, out_dir: Path, layers: list[int], fmt: str,
                tp: int, rank: int, limit_rows: int | None, samples: int) -> None:
    import random
    rng = random.Random(0xD5A41)
    for layer in layers:
        wname = f"layers.{layer}.{WEIGHT_SUFFIX}"
        sname = f"layers.{layer}.{SCALE_SUFFIX}"
        wshard, woff, _wd, wshape = tensors[wname]
        sshard, soff, _sd, sshape = tensors[sname]
        rows = wshape[0]
        wrow, srow = _row_bytes(wshape), _row_bytes(sshape)
        if fmt == "safetensors":
            path = out_dir / f"engram-l{layer}.safetensors"
            with path.open("rb") as f:
                hlen = struct.unpack("<Q", f.read(8))[0]
                header = json.loads(f.read(hlen))
                base = 8 + hlen
                we = header[wname]
                se = header[sname]
                hi = we["shape"][0]
                lo = 0
                for _ in range(samples):
                    r = rng.randrange(lo, hi)
                    want_w = source.read(wshard, woff + r * wrow, wrow)
                    want_s = source.read(sshard, soff + r * srow, srow)
                    f.seek(base + we["data_offsets"][0] + r * wrow)
                    got_w = f.read(wrow)
                    f.seek(base + se["data_offsets"][0] + r * srow)
                    got_s = f.read(srow)
                    if got_w != want_w or got_s != want_s:
                        raise EngramError(f"verify failed: {path} row {r}")
            log(f"verified {path.name}: {samples} random rows byte-exact")
        else:
            path = out_dir / f"engram-l{layer}-r{rank}of{tp}.bin"
            lo, hi = rows * rank // tp, rows * (rank + 1) // tp
            if limit_rows is not None:
                hi = min(hi, lo + limit_rows)
            with path.open("rb") as f:
                hdr = f.read(PACKED_HEADER_BYTES)
                magic, hlayer, hlo, hhi, hrows, hrowb = struct.unpack_from("<6Q", hdr, 0)
                if (magic != MAGIC or hlayer != layer or hlo != lo or hhi != hi
                        or hrows != rows or hrowb != PACKED_ROW_BYTES):
                    raise EngramError(f"{path}: packed header mismatch")
                for _ in range(samples):
                    r = rng.randrange(lo, hi)
                    want_w = source.read(wshard, woff + r * wrow, wrow)
                    want_s = source.read(sshard, soff + r * srow, srow)
                    f.seek(PACKED_HEADER_BYTES + (r - lo) * PACKED_ROW_BYTES)
                    got = f.read(PACKED_ROW_BYTES)
                    if got != want_w + want_s:
                        raise EngramError(f"verify failed: {path} row {r}")
            log(f"verified {path.name}: {samples} random rows byte-exact")


def _write_synthetic(root: Path, rows: int = 5000) -> dict:
    """A tiny stand-in for the official checkpoint, for tests.

    Two shards, one per engram layer, each holding ``engram.embed.weight``
    (F8_E4M3 x256) and ``engram.embed.scale`` (F8_E8M0 x8), plus an unrelated
    ``engram.wkv.weight`` that the builder must ignore.  Byte values are a
    deterministic function of (layer, row, col) so the test can recompute an
    expected row independently of the builder.
    """
    import random as _random
    rng = _random.Random(1234)
    index: dict[str, str] = {}
    for layer, shard in ((1, "model-00047-of-00048.safetensors"),
                         (14, "model-00048-of-00048.safetensors")):
        wname = f"layers.{layer}.{WEIGHT_SUFFIX}"
        sname = f"layers.{layer}.{SCALE_SUFFIX}"
        other = f"layers.{layer}.engram.wkv.weight"
        wdata = bytes(rng.randrange(256) for _ in range(rows * WEIGHT_BYTES))
        sdata = bytes(rng.randrange(256) for _ in range(rows * SCALE_BYTES))
        odata = bytes(rng.randrange(256) for _ in range(16))
        entries = [
            (wname, "F8_E4M3", [rows, WEIGHT_BYTES], wdata),
            (sname, "F8_E8M0", [rows, SCALE_BYTES], sdata),
            (other, "F8_E4M3", [16, 1], odata),
        ]
        header: dict[str, dict] = {}
        off = 0
        for name, dtype, shape, data in entries:
            header[name] = {"dtype": dtype, "shape": shape,
                            "data_offsets": [off, off + len(data)]}
            off += len(data)
        body = json.dumps(header, separators=(",", ":")).encode()
        body += b" " * ((-len(body)) % 8)
        blob = struct.pack("<Q", len(body)) + body + b"".join(d[3] for d in entries)
        (root / shard).write_bytes(blob)
        for name, _dt, _sh, _d in entries:
            index[name] = shard
    (root / "model.safetensors.index.json").write_text(
        json.dumps({"metadata": {}, "weight_map": index}))
    return index


def _expected_row(root: Path, layer: int, row: int) -> tuple[bytes, bytes]:
    """The (weight, scale) bytes the synthetic checkpoint holds for a row."""
    shard = "model-00047-of-00048.safetensors" if layer == 1 else "model-00048-of-00048.safetensors"
    blob = (root / shard).read_bytes()
    hlen = struct.unpack("<Q", blob[:8])[0]
    header = json.loads(blob[8:8 + hlen])
    base = 8 + hlen
    w = header[f"layers.{layer}.{WEIGHT_SUFFIX}"]
    s = header[f"layers.{layer}.{SCALE_SUFFIX}"]
    wo = base + w["data_offsets"][0] + row * WEIGHT_BYTES
    so = base + s["data_offsets"][0] + row * SCALE_BYTES
    return blob[wo:wo + WEIGHT_BYTES], blob[so:so + SCALE_BYTES]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _safetensors_entry_ok(header: dict, layer: int) -> tuple[bool, str]:
    """Whether a safetensors header provides layer ``layer``'s embed tensors."""
    wkey = f"layers.{layer}.{WEIGHT_SUFFIX}"
    skey = f"layers.{layer}.{SCALE_SUFFIX}"
    if wkey not in header or skey not in header:
        return False, f"no {wkey}/{skey}"
    w, s = header[wkey], header[skey]
    wrow, srow = _row_bytes(w["shape"]), _row_bytes(s["shape"])
    if (wrow, srow) != (WEIGHT_BYTES, SCALE_BYTES):
        return False, f"row sizes {wrow}/{srow} (want {WEIGHT_BYTES}/{SCALE_BYTES})"
    if w["shape"][0] != s["shape"][0]:
        return False, "weight/scale row count differs"
    return True, f"{w['shape'][0]} rows x {wrow + srow} B"


def check_output(out_dir: Path, layers: list[int], fmt: str, tp: int, rank: int) -> bool:
    """Offline completeness/format check of a previously built output dir.

    Returns True when every expected artifact is present and well-formed (no
    network, no source needed).  Used by the recipe's pre-launch mod to decide
    whether a fetch is required, and by operators to sanity-check a directory.

    ``--format safetensors`` accepts **any** safetensors file in the directory
    that provides a wanted layer's tensors -- including the official checkpoint
    shards themselves (``model-00047/48-of-00048.safetensors``), which is what a
    node that was pre-warmed by hand holds.  The engine globs the directory the
    same way, so "the engine can read it" is the correct readiness test.
    """
    ok = True
    if fmt == "safetensors":
        found: dict[int, str] = {}
        for path in sorted(out_dir.glob("*.safetensors")):
            try:
                size = path.stat().st_size
                with path.open("rb") as f:
                    hlen = struct.unpack("<Q", f.read(8))[0]
                    header = json.loads(f.read(hlen))
                    base = 8 + hlen
            except (OSError, ValueError, struct.error) as exc:
                log(f"check: unreadable {path.name}: {exc}")
                ok = False
                continue
            for layer in layers:
                if layer in found:
                    continue
                good, why = _safetensors_entry_ok(header, layer)
                if not good:
                    continue
                w = header[f"layers.{layer}.{WEIGHT_SUFFIX}"]
                s = header[f"layers.{layer}.{SCALE_SUFFIX}"]
                need = base + w["data_offsets"][1] + (s["data_offsets"][1] - s["data_offsets"][0])
                if size < need:
                    log(f"check: BAD {path.name}: truncated ({size} < {need})")
                    ok = False
                    continue
                found[layer] = f"{path.name} [{why}]"
        for layer in layers:
            if layer in found:
                log(f"check: OK layer {layer} in {found[layer]}")
            else:
                log(f"check: MISSING layer {layer} (no safetensors here provides it)")
                ok = False
    else:
        for layer in layers:
            path = out_dir / f"engram-l{layer}-r{rank}of{tp}.bin"
            if not path.is_file():
                log(f"check: MISSING {path}")
                ok = False
                continue
            try:
                with path.open("rb") as f:
                    hdr = f.read(PACKED_HEADER_BYTES)
                magic, hlayer, lo, hi, _rows, rowb = struct.unpack_from("<6Q", hdr, 0)
                if magic != MAGIC or hlayer != layer or rowb != PACKED_ROW_BYTES:
                    raise EngramError("header magic/layer/row-bytes wrong")
                if path.stat().st_size != PACKED_HEADER_BYTES + (hi - lo) * PACKED_ROW_BYTES:
                    raise EngramError("size does not match header")
                log(f"check: OK {path.name} (rows [{lo},{hi}) x {PACKED_ROW_BYTES} B)")
            except (EngramError, struct.error) as exc:
                log(f"check: BAD {path}: {exc}")
                ok = False
    if ok:
        for stray in out_dir.glob("*.partial"):
            log(f"check: stray partial {stray.name} (incomplete build)")
            ok = False
    return ok


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo", default=DEFAULT_REPO, help="HF repo id (default: %(default)s)")
    p.add_argument("--revision", default="main", help="HF revision (default: %(default)s)")
    p.add_argument("--endpoint", default=os.environ.get("HF_ENDPOINT", DEFAULT_ENDPOINT),
                   help="HF endpoint (default: %(default)s)")
    p.add_argument("--token", default=os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"),
                   help="HF token for gated/private repos (default: $HF_TOKEN)")
    p.add_argument("--source-dir", default=None,
                   help="read from a local checkpoint dir instead of the network "
                        "(offline mode; used by the tests)")
    p.add_argument("--index", default="model.safetensors.index.json",
                   help="safetensors index filename (default: %(default)s)")
    p.add_argument("--layers", default=",".join(str(x) for x in DEFAULT_LAYERS),
                   help="comma-separated engram layer ids (default: %(default)s)")
    p.add_argument("--out", default=default_out(),
                   help="output directory (default: $TF_DS_ENGRAM, else the lane's "
                        "in-container path, else the host's ~/.cache/huggingface/hub/dsv41-engram)")
    p.add_argument("--format", choices=("safetensors", "packed"), default="safetensors",
                   help="output format (default: %(default)s)")
    p.add_argument("--tensor-parallel", type=int, default=1,
                   help="TP degree for --format packed (default: %(default)s)")
    p.add_argument("--rank", type=int, default=0,
                   help="this rank for --format packed (default: %(default)s)")
    p.add_argument("--workers", type=int, default=16, help="concurrent transfers (default: %(default)s)")
    p.add_argument("--chunk-mb", type=int, default=8,
                   help="read/write tick MiB (default: %(default)s)")
    p.add_argument("--segment-mb", type=int, default=256,
                   help="resume-segment MiB; also the ranged-request size, so larger "
                        "means fewer requests to Hugging Face (default: %(default)s)")
    p.add_argument("--limit-rows", type=int, default=None,
                   help="fetch only this many rows per table (testing)")
    p.add_argument("--no-resume", dest="resume", action="store_false", default=True,
                   help="discard partial output and restart (default: resume)")
    p.add_argument("--verify-rows", type=int, default=0,
                   help="after writing, re-fetch N random rows from the source and compare")
    p.add_argument("--dry-run", action="store_true", help="resolve and report, fetch no table bytes")
    p.add_argument("--check", action="store_true",
                   help="offline: verify --out already holds complete, well-formed tables and exit; "
                        "no network, no source (exit 0 = complete, 1 = incomplete)")
    p.add_argument("--detach", action="store_true",
                   help="run the fetch in the background, fully detached (survives a "
                        "closed terminal, ssh session, or launcher), and return at once. "
                        "For slow links / unattended pre-warm. Progress: --status.")
    p.add_argument("--status", action="store_true",
                   help="report progress of a detached fetch (reads the progress file) and exit; "
                        "exit 0 = complete, 1 = in progress or incomplete")
    p.add_argument("--pid-file", default=None,
                   help="where --detach records its pid (default: /tmp/dsv41-engram-<hash>.pid)")
    p.add_argument("--log-file", default=None,
                   help="where --detach sends the child's output (default: /tmp/dsv41-engram-<hash>.log)")
    return p.parse_args(argv)


def _runtime_files(args) -> tuple[str, str]:
    """Per-output pid/log paths so concurrent builds never collide."""
    tag = hashlib.sha1(os.path.abspath(os.path.expanduser(args.out)).encode()).hexdigest()[:10]
    pid = args.pid_file or os.path.join(tempfile.gettempdir(), f"dsv41-engram-{tag}.pid")
    logf = args.log_file or os.path.join(tempfile.gettempdir(), f"dsv41-engram-{tag}.log")
    return pid, logf


def _progress_summary(out_dir: Path, layers: list[int]) -> tuple[int, int]:
    """(segments done, segments total-ish) for a safetensors build, best effort.

    \"Total\" is not recorded ahead of time; report done count and the per-layer
    partial sizes so `--status` is useful without the source.
    """
    p = out_dir / ".engram-progress.json"
    done = 0
    if p.is_file():
        try:
            done = len(json.loads(p.read_text()).get("done", []))
        except (ValueError, OSError):
            done = 0
    return done, len(layers)


def _status(args, out_dir: Path, layers: list[int]) -> int:
    """Report a build's state without touching the network."""
    done, _ = _progress_summary(out_dir, layers)
    part = sorted(out_dir.glob("*.partial"))
    final = sorted(out_dir.glob("*.safetensors")) + sorted(out_dir.glob("*.bin"))
    pid_file, _log_file = _runtime_files(args)
    pid = None
    if os.path.exists(pid_file):
        try:
            pid = int(Path(pid_file).read_text().strip())
        except (ValueError, OSError):
            pid = None
    running = False
    if pid:
        try:
            os.kill(pid, 0)
            running = True
        except (ProcessLookupError, PermissionError):
            running = False
    if check_output(out_dir, layers, args.format, args.tensor_parallel, args.rank):
        log(f"status: COMPLETE at {out_dir} ({len(final)} file(s))")
        return 0
    log(f"status: INCOMPLETE at {out_dir}")
    log(f"  segments done: {done}")
    log(f"  partials: {[p.name for p in part] or 'none'}")
    log(f"  finished files: {[p.name for p in final] or 'none'}")
    log(f"  detached pid: {pid if pid else 'none'} ({'running' if running else 'not running'})")
    if running:
        log("  a detached fetch is still running; re-run --status later")
    else:
        log("  no live fetcher: re-run the build (resumes) or --detach")
    return 1


def _detach(args) -> int:
    """Re-exec this build as a detached child and return immediately."""
    pid_file, log_file = _runtime_files(args)
    child_argv = [a for a in sys.argv[1:] if a not in ("--detach",)]
    logf = open(log_file, "ab", buffering=0)
    proc = subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), *child_argv],
        stdin=subprocess.DEVNULL, stdout=logf, stderr=logf, start_new_session=True)
    Path(pid_file).write_text(str(proc.pid))
    log(f"detached fetch pid {proc.pid}")
    log(f"  log:    {log_file}")
    log(f"  out:    {os.path.expanduser(args.out)}")
    log(f"  status: {os.path.abspath(__file__)} --status --out {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    layers = [int(x) for x in args.layers.split(",") if x.strip()]
    if not layers:
        raise EngramError("no layers selected")
    chunk = max(1, args.chunk_mb) * 2**20
    segment = max(chunk, args.segment_mb * 2**20)
    out_dir = Path(args.out).expanduser()

    if args.check:
        return 0 if check_output(out_dir, layers, args.format,
                                  args.tensor_parallel, args.rank) else 1
    if args.status:
        return _status(args, out_dir, layers)
    if args.detach:
        return _detach(args)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.source_dir:
        source = LocalSource(os.path.expanduser(args.source_dir))
        log(f"source: local {args.source_dir}")
    else:
        source = HttpSource(args.repo, args.revision, args.endpoint, args.token)
        log(f"source: {source.url('')} (range GETs)")

    t0 = time.monotonic()
    tensors = find_engram_tensors(source, args.index, layers)
    for name in sorted(tensors):
        shard, off, dtype, shape = tensors[name]
        log(f"  {name}: {shard} @ {off} {dtype} {shape}")
    if args.dry_run:
        log("dry run: nothing fetched")
        return 0

    if args.format == "safetensors":
        produced = build_safetensors(source, tensors, out_dir, layers, args.workers,
                                     segment, args.limit_rows, args.resume)
    else:
        produced = build_packed(source, tensors, out_dir, layers, args.tensor_parallel,
                                args.rank, args.limit_rows, chunk)

    if args.verify_rows:
        verify_rows(source, tensors, out_dir, layers, args.format, args.tensor_parallel,
                    args.rank, args.limit_rows, args.verify_rows)

    elapsed = time.monotonic() - t0
    total = sum(p.stat().st_size for p in produced)
    log(f"done: {len(produced)} file(s), {total / 2**30:.1f} GiB in {elapsed:.0f}s "
        f"({total / max(elapsed, 1e-6) / 2**20:.0f} MiB/s)")
    log(f"set TF_DS_ENGRAM={out_dir} for the TensorFold TP=2 lane")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except EngramError as exc:
        print(f"[engram] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)