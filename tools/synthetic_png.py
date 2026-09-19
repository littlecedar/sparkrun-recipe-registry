"""Stdlib-only PNG generation, for synthetic image payloads in pooling-bench.

Why this exists: vLLM's multimodal cache is keyed on image *content*, not on URL. Proven on
hardware -- appending a random query parameter to every image URL left the run at an identical
81.5% prefix-cache hit rate and moved `mm_cache_hits_total` from 448 to 898, i.e. all 450 new
requests hit the cache despite 450 distinct URLs. So the only way to benchmark image-bearing
score traffic honestly is to send genuinely distinct pixels.

Solid-colour PNGs are the cheapest way to get that. A flat image compresses to a few hundred
bytes, so 400 distinct images cost less bandwidth than one photographic one, while still
presenting the vision encoder with the same number of patches -- the encoder's cost is driven
by the patch grid (sequence length), not by image entropy. That makes it a fair proxy for
encoder and prefill cost. It is NOT a proxy for realistic attention over real content, and a
flat image may be scored oddly; it measures capacity, not quality.
"""

import base64
import struct
import zlib


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def solid_png_b64(width: int, height: int, rgb: tuple[int, int, int]) -> str:
    """Return a base64-encoded, non-interlaced 8-bit RGB PNG of one flat colour.

    Each filter byte is 0 (None), so every scanline is stored raw and zlib collapses the
    whole image into a handful of bytes.
    """
    if not (0 < width < 2**31 and 0 < height < 2**31):
        raise ValueError(f"bad dimensions {width}x{height}")
    if any(not 0 <= c <= 255 for c in rgb):
        raise ValueError(f"bad rgb {rgb!r}")
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit, colour type 2
    row = b"\x00" + bytes(rgb) * width  # leading 0 = filter None
    raw = row * height
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(raw, 6))
        + _chunk(b"IEND", b"")
    )
    return base64.b64encode(png).decode("ascii")


def solid_data_url(width: int, height: int, rgb: tuple[int, int, int]) -> str:
    return f"data:image/png;base64,{solid_png_b64(width, height, rgb)}"


def iter_chunks(png: bytes):
    """Yield (tag, data) for each chunk of a PNG. Raises on structural damage.

    Used by the self-check below rather than index arithmetic, because hand-computing chunk
    offsets is exactly the kind of thing a self-check should not get wrong: an earlier version
    of this file's test read the IDAT *length* as data and failed with 'incorrect header
    check', which looked like a generator bug and was not one.
    """
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("missing PNG signature")
    pos = 8
    while pos + 8 <= len(png):
        (length,) = struct.unpack(">I", png[pos : pos + 4])
        tag = png[pos + 4 : pos + 8]
        data = png[pos + 8 : pos + 8 + length]
        if len(data) != length:
            raise ValueError(f"truncated {tag!r} chunk: want {length}, got {len(data)}")
        (stored_crc,) = struct.unpack(">I", png[pos + 8 + length : pos + 12 + length])
        if stored_crc != zlib.crc32(tag + data) & 0xFFFFFFFF:
            raise ValueError(f"CRC mismatch in {tag!r}")
        yield tag, data
        pos += 12 + length
        if tag == b"IEND":
            return
    raise ValueError("PNG ended without IEND")


if __name__ == "__main__":
    # Self-check: decode what we produced using nothing but stdlib, and confirm distinct
    # colours really do produce distinct bytes.
    import hashlib

    a = solid_png_b64(64, 64, (255, 0, 0))
    b = solid_png_b64(64, 64, (0, 255, 0))
    raw_a = base64.b64decode(a)

    chunks = dict(iter_chunks(raw_a))
    w, h, depth, ctype = struct.unpack(">IIBB", chunks[b"IHDR"][:10])
    print(f"decoded header: {w}x{h} depth={depth} colortype={ctype}")
    assert (w, h, depth, ctype) == (64, 64, 8, 2)
    assert b"IEND" in chunks, "IEND not seen by the walker"

    raw = zlib.decompress(chunks[b"IDAT"])
    assert len(raw) == h * (1 + w * 3), (len(raw), h * (1 + w * 3))
    for i in range(h):
        line = raw[i * (1 + w * 3) : (i + 1) * (1 + w * 3)]
        assert line[0] == 0, f"row {i} filter byte is {line[0]}, expected 0 (None)"
        assert line[1:] == bytes((255, 0, 0)) * w, f"row {i} is not flat red"
    print(f"pixel scan: {h} rows, filter=None, all flat red -- OK")

    print("distinct colours -> distinct bytes:",
          hashlib.md5(a.encode()).hexdigest()[:8], hashlib.md5(b.encode()).hexdigest()[:8],
          "differ" if a != b else "IDENTICAL (bad)")
    assert a != b
    # Corrupt one byte and confirm the walker's CRC check actually fires (non-vacuity).
    damaged = bytearray(raw_a)
    damaged[len(damaged) // 2] ^= 0x01
    try:
        for _ in iter_chunks(bytes(damaged)):
            pass
        print("NEGATIVE CONTROL FAILED: corrupted PNG parsed cleanly")
    except ValueError as exc:
        print(f"negative control: corrupted PNG rejected -> {exc}")
    print(f"payload size: {len(a)} base64 chars for 64x64")
    big = solid_png_b64(480, 640, (12, 34, 56))
    print(f"480x640 flat colour: {len(big)} base64 chars")
