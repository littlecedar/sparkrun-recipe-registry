#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""safe_text.py -- make token-bearing logs and chat templates safe to handle.

The DeepSeek-V4.1 serving endpoint (and the DeepSeek API behind it) rejects any
request whose ``message.content`` or ``reasoning_content`` carries the raw image
placeholder token with HTTP 400 ``reasoning_content contains image special
token``. The request is refused, not truncated, so an agent session that reads
one byte of such a token out of a file loses its whole context. The failure is
not recoverable in-session and there is no partial credit: the ingestion itself
is the outage.

The token is the five-part sequence

    U+003C  U+FF5C  "deepseek_image"  U+FF5C  U+003E

(U+FF5C is FULLWIDTH VERTICAL LINE, not the ASCII ``|``.)  It reaches a session
through three routes, all of them file reads: an image decoded by a harness that
serialises images as text, a raw HTTP-400 request dump under
``~/.omp/logs/http-400-requests/``, and a chat template whose content contains
the placeholder on purpose.  This tool is the one place that knows the spelling
of that sequence and the one place allowed to assemble or rewrite it:

* **escape (read)** -- every non-ASCII codepoint becomes ``\\uXXXX`` (or
  ``\\UXXXXXXXX``), every backslash is doubled, and bytes that are not valid
  UTF-8 come back as ``\\xNN``.  The result is guaranteed ASCII-only, so whatever
  the file held, the token cannot survive the transform.
* **unescape (write)** -- the exact inverse, used when a *chat template* has to
  be handed to a tokenizer or a server that needs the raw placeholder bytes.
* **check** -- reports the location of a raw token (or the count of non-ASCII
  codepoints) without ever printing the token, and exits 1 if one is present.

The token is never written literally in this file, in its guards, or in any
output it produces; it is assembled from codepoints by :func:`raw_token`.  Do
not add a literal copy anywhere and do not "simplify" the codepoint
construction.  Output is asserted ASCII-only inside :func:`escape`.

Stdlib only, Python 3.12+, runnable as a script, a library, or a pipe.

    tools/safe_text.py suspicious.log              # escape to stdout
    tools/safe_text.py --check ~/.omp/logs/http-400-requests/*.json
    tools/safe_text.py --unescape tpl.esc -o tpl.jinja   # write the raw token back
    tools/safe_text.py --in-place --check-nonascii f

Exit codes: ``0`` clean, ``1`` ``--check`` found a raw token, ``2`` the tool
could not run (bad flags, unreadable file) -- never a verdict on the content.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

__all__ = [
    "TOKEN_NAME",
    "raw_token",
    "escaped_token",
    "escape",
    "unescape",
    "escape_bytes",
    "unescape_bytes",
    "save_template",
    "load_template",
    "find_raw_token",
    "contains_raw_token",
    "non_ascii_spans",
    "scan_text",
    "scan_file",
    "ScanResult",
]

# --- the token ---------------------------------------------------------------
# Spelled as codepoints on purpose.  A literal copy of the token anywhere in
# this tree (source, docs, fixtures, output) is a bug: it is the exact byte
# sequence that kills an API request.  U+003C U+003E are '<' and '>'; U+FF5C is
# the fullwidth vertical line DeepSeek uses as the placeholder delimiter.
TOKEN_NAME = "deepseek_image"
_TOKEN_OPEN = 0x003C
_TOKEN_BAR = 0xFF5C
_TOKEN_CLOSE = 0x003E

#: Codepoints of the raw placeholder, in order.
TOKEN_CODEPOINTS: tuple[int, ...] = (
    _TOKEN_OPEN,
    _TOKEN_BAR,
    *(ord(c) for c in TOKEN_NAME),
    _TOKEN_BAR,
    _TOKEN_CLOSE,
)


def raw_token() -> str:
    """Return the raw placeholder token, assembled from codepoints.

    Callers that need the literal (an HTTP body, a tokenizer input, a fixture)
    must go through this function so the bytes are never typed by hand.
    """
    return "".join(chr(cp) for cp in TOKEN_CODEPOINTS)


def escaped_token() -> str:
    """The ASCII escape of the token: the safe rendering this tool prints."""
    return escape(raw_token())


_RAW_TOKEN_RE = re.compile(re.escape(raw_token()))


# --- escape / unescape -------------------------------------------------------
# Scheme (fully reversible for text produced by escape()):
#   '\\'                  -> '\\\\'
#   codepoint < 0x80      -> itself
#   surrogateescape byte  -> '\\xNN'   (U+DC80..U+DCFF from errors="surrogateescape")
#   codepoint <= 0xFFFF   -> '\\uXXXX' (lowercase hex, 4 digits)
#   codepoint > 0xFFFF    -> '\\UXXXXXXXX'
# The raw token's two U+FF5C bars therefore come back as '\\uff5c', which is why
# an escaped document can never contain the token.
_SURR_LO, _SURR_HI = 0xDC80, 0xDCFF
# One alternative per escape this tool emits, so a malformed \u123 or \xZZZ
# fails to match and raises rather than being "repaired" into a wrong value.
_ESCAPE_RE = re.compile(r"\\(\\|x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8})")


def escape(text: str) -> str:
    """Escape *text* to ASCII-only text that cannot contain the raw token.

    Inverse of :func:`unescape`.  Guarantees the result has no byte above 0x7F.
    """
    out: list[str] = []
    for ch in text:
        cp = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif cp < 0x80:
            out.append(ch)
        elif _SURR_LO <= cp <= _SURR_HI:  # undecodable byte from surrogateescape
            out.append("\\x%02x" % (cp - 0xDC00))
        elif cp <= 0xFFFF:
            out.append("\\u%04x" % cp)
        else:
            out.append("\\U%08x" % cp)
    result = "".join(out)
    # Fail closed: the whole point of the tool is this invariant.
    if max((ord(c) for c in result), default=0) > 0x7F:  # pragma: no cover
        raise AssertionError("escape() produced non-ASCII output")
    return result


def unescape(text: str) -> str:
    """Invert :func:`escape`: recover the original text, token and all.

    Any backslash that does not begin a ``\\\\``, ``\\xNN``, ``\\uXXXX`` or
    ``\\UXXXXXXXX`` escape raises ``ValueError`` -- an unrecognised backslash
    means the input was not produced by :func:`escape` (hand-edited template,
    already-unescaped file), and guessing would silently corrupt it.  So does
    any non-ASCII codepoint: :func:`escape` output is ASCII-only by
    construction, so a byte above 0x7F proves the caller is holding a raw file.
    """
    for ch in text:
        if ord(ch) > 0x7F:
            raise ValueError(
                "unescape: input contains non-ASCII U+%04X -- it was not produced "
                "by escape() (refusing to guess)" % ord(ch)
            )
    out: list[str] = []
    pos = 0
    n = len(text)
    while pos < n:
        ch = text[pos]
        if ch != "\\":
            out.append(ch)
            pos += 1
            continue
        m = _ESCAPE_RE.match(text, pos)
        if m is None:
            raise ValueError(
                "unescape: unrecognised backslash escape at offset %d "
                "(input was not produced by escape())" % pos
            )
        body = m.group(1)
        if body == "\\":
            out.append("\\")
        else:
            kind, digits = body[0], body[1:]
            cp = int(digits, 16)
            if kind == "x":
                out.append(chr(0xDC00 + cp))  # back to a surrogateescape byte
            elif cp > 0x10FFFF or 0xD800 <= cp <= 0xDFFF:
                raise ValueError("unescape: \\%s is not a valid codepoint" % body)
            else:
                out.append(chr(cp))
        pos = m.end()
    return "".join(out)


def escape_bytes(data: bytes) -> str:
    """Escape raw *data*; undecodable bytes become ``\\xNN`` rather than raising."""
    return escape(data.decode("utf-8", "surrogateescape"))


def unescape_bytes(text: str) -> bytes:
    """Invert :func:`escape_bytes`, recovering the original bytes."""
    return unescape(text).encode("utf-8", "surrogateescape")


# --- escaped-at-rest templates ----------------------------------------------
# A chat template that must contain the raw placeholder (a VL request body, a
# fixture for a tokenizer) should be *stored* escaped and unescaped only at the
# call site.  That keeps every checkout of this tree free of the literal token
# (see tests/test_safe_text.py::ShippedTreeIsClean) while the request still
# carries the real bytes.
def save_template(path: str | os.PathLike[str], text: str) -> None:
    """Write *text* to *path* in escaped form (ASCII-only, token inert)."""
    _write_bytes(os.fspath(path), escape(text).encode("ascii"))


def load_template(path: str | os.PathLike[str]) -> str:
    """Read an escaped template from *path* and restore the raw placeholder.

    Use the result immediately (an HTTP body, a tokenizer call); do not print
    it, log it, or stash it in a tracked file.
    """
    data = Path(path).read_bytes()
    return unescape(data.decode("utf-8", "surrogateescape"))


# --- detection ---------------------------------------------------------------
def find_raw_token(text: str) -> list[tuple[int, int]]:
    """Return 1-based ``(line, column)`` for every raw token in *text*.

    Columns are counted in codepoints.  The text is never echoed, so callers
    can report locations of a token they must not reproduce.
    """
    hits: list[tuple[int, int]] = []
    for m in _RAW_TOKEN_RE.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        col = m.start() - (text.rfind("\n", 0, m.start()) + 1) + 1
        hits.append((line, col))
    return hits


def contains_raw_token(text: str) -> bool:
    """True if *text* holds at least one raw token."""
    return _RAW_TOKEN_RE.search(text) is not None


def non_ascii_spans(text: str, limit: int = 8) -> list[tuple[int, int, str]]:
    """Up to *limit* non-ASCII codepoints as ``(line, column, 'U+XXXX')``.

    Non-ASCII alone is not fatal -- it is the *route* the token takes into a
    session (image decode, JSON dump) and a red flag on a chat template -- so it
    is reported as advisory detail, never as a verdict.
    """
    spans: list[tuple[int, int, str]] = []
    line = col = 1
    for ch in text:
        cp = ord(ch)
        if cp == 0x0A:
            line, col = line + 1, 1
            continue
        if cp > 0x7F:
            spans.append((line, col, "U+%04X" % cp))
            if len(spans) >= limit:
                break
        col += 1
    return spans


# --- file scanning -----------------------------------------------------------
class ScanResult:
    """Outcome of one file scan; ``hits`` are line/column pairs."""

    __slots__ = ("path", "hits", "non_ascii", "size")

    def __init__(self, path: str, hits: list[tuple[int, int]], non_ascii: int, size: int):
        self.path = path
        self.hits = hits
        self.non_ascii = non_ascii
        self.size = size

    @property
    def clean(self) -> bool:
        return not self.hits

    def describe(self) -> str:
        lines = ["%s: %d byte(s)" % (self.path, self.size)]
        if self.hits:
            locations = ", ".join("%d:%d" % (ln, col) for ln, col in self.hits)
            lines.append(
                "  RAW TOKEN x%d at %s -- do not read this file into a model "
                "context; escape it first (escaped form: %s)"
                % (len(self.hits), locations, escaped_token())
            )
        else:
            lines.append("  no raw token")
        if self.non_ascii:
            lines.append("  %d non-ASCII codepoint(s)" % self.non_ascii)
        return "\n".join(lines)


def scan_text(text: str, path: str = "<text>", size: int | None = None) -> ScanResult:
    """Scan decoded *text* for the raw token and count non-ASCII codepoints."""
    hits = find_raw_token(text)
    non_ascii = sum(1 for ch in text if ord(ch) > 0x7F)
    if size is None:
        size = len(text.encode("utf-8", "surrogateescape"))
    return ScanResult(path, hits, non_ascii, size)


def scan_file(path: str | os.PathLike[str]) -> ScanResult:
    """Read *path* as bytes and scan it.

    Raises on an unreadable or missing file -- a scan that cannot read its
    target is not a clean scan, and the caller must not treat it as one.
    """
    data = Path(path).read_bytes()
    text = data.decode("utf-8", "surrogateescape")
    return scan_text(text, os.fspath(path), size=len(data))


# --- I/O ---------------------------------------------------------------------
def _read_source(path: str | None) -> bytes:
    if path is None or path == "-":
        return sys.stdin.buffer.read()
    return Path(path).read_bytes()


def _write_bytes(path: str | None, data: bytes) -> None:
    if path is None or path == "-":
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
        return
    target = Path(path)
    # tmp + os.replace: a crash mid-write must not leave a half-rewritten
    # template, and writing through a symlink would rewrite the link target.
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=".safe_text-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        # Preserve mode/owner of an existing regular file.  A symlink is left
        # alone: os.replace() swaps the *link*, so the node's real file (e.g. a
        # chat template inside an HF snapshot) is never written through.
        if target.exists() and not target.is_symlink():
            st = target.stat()
            os.chmod(tmp, st.st_mode & 0o7777)
            if os.geteuid() == 0:
                os.chown(tmp, st.st_uid, st.st_gid)
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="safe_text.py",
        description="Escape the raw image placeholder token out of logs and chat "
        "templates (default), or put it back (--unescape), or report it (--check).",
        epilog="Exit codes: 0 clean, 1 --check found the raw token, 2 could not run.",
    )
    parser.add_argument("paths", nargs="*", help="files (default: stdin)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="report raw-token locations; never prints the token; exit 1 if found",
    )
    mode.add_argument(
        "--unescape",
        action="store_true",
        help="inverse transform: write the raw token back (for chat templates)",
    )
    parser.add_argument(
        "--check-nonascii",
        action="store_true",
        help="advisory: also list non-ASCII codepoint locations (implies --check)",
    )
    parser.add_argument("-o", "--output", help="write to this file instead of stdout")
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="rewrite each input file instead of printing (single file per run in --check mode)",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="only the exit code")
    args = parser.parse_args(argv)

    if args.in_place and (not args.paths or args.paths == ["-"]):
        print("safe_text.py: --in-place needs at least one real file", file=sys.stderr)
        return 2
    if args.output and args.in_place:
        print("safe_text.py: --output and --in-place are exclusive", file=sys.stderr)
        return 2
    if args.output and len(args.paths) > 1:
        print("safe_text.py: --output takes at most one input", file=sys.stderr)
        return 2

    if args.check or args.check_nonascii:
        if args.in_place:
            print("safe_text.py: --check does not modify files", file=sys.stderr)
            return 2
        targets: list[str | None] = list(args.paths) or [None]
        found = False
        try:
            for target in targets:
                data = _read_source(target)
                text = data.decode("utf-8", "surrogateescape")
                result = scan_text(text, "stdin" if target is None else target, size=len(data))
                found = found or not result.clean
                if not args.quiet:
                    print(result.describe())
                    if args.check_nonascii:
                        for ln, col, kind in non_ascii_spans(text):
                            print("  non-ASCII at %d:%d (%s)" % (ln, col, kind))
        except OSError as exc:
            print("safe_text.py: %s" % exc, file=sys.stderr)
            return 2
        return 1 if found else 0

    try:
        if args.in_place:
            for path in args.paths:
                data = _read_source(path)
                out = unescape_bytes(data.decode("utf-8", "surrogateescape")) if args.unescape else escape_bytes(data).encode("ascii")
                _write_bytes(path, out)
        else:
            data = _read_source(args.paths[0] if args.paths else None)
            text = data.decode("utf-8", "surrogateescape")
            out = unescape_bytes(text) if args.unescape else escape_bytes(data).encode("ascii")
            _write_bytes(args.output, out)
    except OSError as exc:
        print("safe_text.py: %s" % exc, file=sys.stderr)
        return 2
    except ValueError as exc:
        print("safe_text.py: %s" % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())