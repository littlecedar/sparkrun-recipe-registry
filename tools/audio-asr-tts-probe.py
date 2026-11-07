#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ASR + TTS probe for an audio arm served by llama-server.

Three cells against one boot, because this family's server-side audio support is
two endpoints, not one:

* ``asr`` — ``POST /v1/audio/transcriptions`` (OpenAI-compatible multipart) with
  a known-text clip; the transcript is scored against the text it is known to
  speak, giving a literal word error rate.
* ``tts`` — ``POST /tts`` with that same text; the reply is checked as audio
  (RIFF/WAVE, sample rate, duration, non-silence), not as an HTTP 200.
* ``roundtrip`` — the synthesised audio is fed back into the ASR endpoint and
  scored against the text it was asked to speak. Intelligibility, not
  naturalness.

What it proves: both endpoints accept this model, and on one known-text fixture
the transcript carries few wrong words while speech the model generated is
transcribable back to its own text. A transcript that ignores the audio scores
near 1.0; a TTS path that returns silence fails the audio check.

Cannot prove: ASR quality. One sentence on one fixture is not an ASR benchmark —
it has no accent, noise, overlap or long-form condition, and a low WER here says
nothing about another speaker. Round-trip WER is bounded by the same model on
both ends, so it measures mutual intelligibility of its own render and speech,
never a MOS or a human listener. The media lane's whistle chain
(``recipes/media/README.md``) is the reference instrument once renders have no
ground-truth text.

Usage
-----
::

  python3 tools/audio-asr-tts-probe.py --selftest            # offline stub, ~1 s
  python3 tools/audio-asr-tts-probe.py \\
      --base-url http://<node>:8022 \\
      --wav ~/benchmarks/omni-repin-20261107/drama-weights/drama.wav \\
      --statement "The quarterly report is due on Thursday, so please finish it by noon." \\
      --lang en --json asr-tts.json

Exit codes: ``0`` every cell ran and met its threshold, ``1`` a cell failed or
crossed a threshold, ``2`` bad flags or an unreadable fixture.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import struct
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

TIMEOUT = 600.0
_STRIP = re.compile(r"[^a-z0-9 ]+")


def normalize(text: str) -> list[str]:
    """Words as a scorer sees them: lowercased, punctuation dropped, spacing collapsed."""
    return _STRIP.sub(" ", text.lower()).split()


def wer(reference: str, hypothesis: str) -> float:
    """Literal word error rate: (substitutions + deletions + insertions) / len(reference)."""
    ref, hyp = normalize(reference), normalize(hypothesis)
    if not ref:
        raise ValueError("empty reference text")
    matcher = difflib.SequenceMatcher(a=ref, b=hyp, autojunk=False)
    errors = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            errors += max(i2 - i1, j2 - j1)
    return errors / len(ref)


def _post_json(url: str, body: dict[str, Any], timeout: float = TIMEOUT) -> tuple[int, Any, float]:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    return _do(req, timeout)


def _multipart(fields: dict[str, str], file_field: str, filename: str, blob: bytes,
               mime: str = "audio/wav") -> tuple[bytes, str]:
    boundary = "----audioarm" + str(time.time_ns())
    out = bytearray()
    for name, value in fields.items():
        if value == "":
            continue
        out += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
    out += (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; "
        f"filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n"
    ).encode()
    out += blob + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def _do(req: urllib.request.Request, timeout: float) -> tuple[int, Any, float]:
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            elapsed = time.time() - t0
            if raw[:4] == b"RIFF":
                return r.status, raw, elapsed
            try:
                return r.status, json.loads(raw), elapsed
            except json.JSONDecodeError:
                return r.status, raw.decode("utf-8", "replace"), elapsed
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), time.time() - t0
    except (urllib.error.URLError, OSError) as e:
        return 0, f"{type(e).__name__}: {e}", time.time() - t0


def _served_id(base: str, timeout: float = 30.0) -> str | None:
    try:
        with urllib.request.urlopen(base.rstrip("/") + "/v1/models", timeout=timeout) as r:
            return json.load(r)["data"][0]["id"]
    except Exception:  # noqa: BLE001 - any failure means "pass --model"
        return None


def transcribe(base: str, model: str, blob: bytes, filename: str, lang: str,
               timeout: float = TIMEOUT) -> tuple[int, Any, float]:
    body, ctype = _multipart(
        {"model": model, "language": lang, "response_format": "json", "temperature": "0"},
        "file", filename, blob)
    req = urllib.request.Request(
        base.rstrip("/") + "/v1/audio/transcriptions", data=body, headers={"Content-Type": ctype})
    return _do(req, timeout)


def transcript_text(payload: Any) -> tuple[str | None, str]:
    """-> (transcript, why) from an OpenAI transcription reply, or raw-text body."""
    if isinstance(payload, str):
        return payload.strip(), ""
    if isinstance(payload, dict):
        for key in ("text", "transcription", "content"):
            if isinstance(payload.get(key), str):
                return payload[key].strip(), ""
        return None, f"reply carries no text ({sorted(payload)})"
    return None, f"reply is {type(payload).__name__}"


def wav_info(blob: bytes) -> tuple[dict[str, Any], str]:
    """-> (info, why). Reads the fmt and data chunks; refuses non-RIFF."""
    if len(blob) < 44 or blob[:4] != b"RIFF" or blob[8:12] != b"WAVE":
        return {}, "not a RIFF/WAVE file"
    info: dict[str, Any] = {"bytes": len(blob)}
    pos, fmt, data_bytes = 12, None, 0
    while pos + 8 <= len(blob):
        cid, size = blob[pos:pos + 4], struct.unpack_from("<I", blob, pos + 4)[0]
        body = blob[pos + 8:pos + 8 + size]
        if cid == b"fmt " and len(body) >= 16:
            fmt = {
                "format": struct.unpack_from("<H", body, 0)[0],
                "channels": struct.unpack_from("<H", body, 2)[0],
                "sample_rate": struct.unpack_from("<I", body, 4)[0],
                "bits": struct.unpack_from("<H", body, 14)[0],
            }
        elif cid == b"data":
            data_bytes = min(size, len(body))
            info["peak"] = _peak(body[:data_bytes], fmt)
        pos += 8 + size + (size & 1)
    if not fmt:
        return info, "no fmt chunk"
    if fmt["format"] not in (1, 3):
        return info, f"unsupported wav format tag {fmt['format']}"
    info.update(fmt)
    info["seconds"] = round(data_bytes / (fmt["sample_rate"] * fmt["channels"]
                                          * max(fmt["bits"] // 8, 1)), 3)
    if info["seconds"] <= 0.05:
        return info, f"audio is {info['seconds']} s long"
    if info.get("peak", 0.0) <= 1e-4:
        return info, "audio is silent"
    return info, ""


def _peak(pcm: bytes, fmt: dict[str, Any] | None) -> float:
    if not fmt or not pcm:
        return 0.0
    if fmt["bits"] == 16:
        n = len(pcm) // 2
        if not n:
            return 0.0
        samples = struct.unpack_from(f"<{n}h", pcm, 0)
        return max(abs(s) for s in samples) / 32768.0
    if fmt["bits"] == 32 and fmt["format"] == 3:
        n = len(pcm) // 4
        if not n:
            return 0.0
        samples = struct.unpack_from(f"<{n}f", pcm, 0)
        return max(abs(s) for s in samples)
    return 1.0  # unmeasured width: do not claim silence we cannot see


def probe(base: str, model: str, wav: Path, statement: str, lang: str, tts_text: str,
          voice: str, tts_out: Path | None, asr_max: float, rt_max: float) -> dict[str, Any]:
    out: dict[str, Any] = {
        "base_url": base, "model": model, "wav": str(wav), "lang": lang,
        "ground_truth": statement, "tts_text": tts_text, "cells": {},
    }

    # 1. ASR on a clip whose text is known.
    blob = wav.read_bytes()
    status, payload, elapsed = transcribe(base, model, blob, wav.name, lang)
    cell: dict[str, Any] = {"status": status, "wall_s": round(elapsed, 3)}
    if status == 200:
        text, why = transcript_text(payload)
        if text is not None:
            cell["transcript"] = text
            cell["wer"] = round(wer(statement, text), 4)
            cell["threshold"] = asr_max
        else:
            cell["problem"] = why
    else:
        cell["problem"] = str(payload)
    out["cells"]["asr"] = cell

    # 2. TTS with the same text.
    tts_body = {"input": tts_text, "lang": lang, "response_format": "wav",
                "temperature": 0}
    if voice:
        tts_body["voice"] = voice
    status, payload, elapsed = _post_json(base.rstrip("/") + "/tts", tts_body)
    tts: dict[str, Any] = {"status": status, "wall_s": round(elapsed, 3)}
    audio: bytes | None = None
    if status == 200 and isinstance(payload, (bytes, bytearray)):
        audio = bytes(payload)
        info, why = wav_info(audio)
        tts.update({k: v for k, v in info.items()})
        if why:
            tts["problem"] = why
            audio = None
        if tts_out is not None:
            tts_out.parent.mkdir(parents=True, exist_ok=True)
            tts_out.write_bytes(audio if audio is not None else bytes(payload))
            tts["saved"] = str(tts_out)
    else:
        tts["problem"] = str(payload)
    out["cells"]["tts"] = tts

    # 3. Round trip: speak it back and score what the ASR hears.
    rt: dict[str, Any] = {}
    if audio is not None:
        status, payload, elapsed = transcribe(base, model, audio, "tts.wav", lang)
        rt = {"status": status, "wall_s": round(elapsed, 3)}
        if status == 200:
            text, why = transcript_text(payload)
            if text is not None:
                rt["transcript"] = text
                rt["wer"] = round(wer(tts_text, text), 4)
                rt["threshold"] = rt_max
            else:
                rt["problem"] = why
        else:
            rt["problem"] = str(payload)
    else:
        rt = {"status": 0, "problem": "tts cell produced no audio to transcribe"}
    out["cells"]["roundtrip"] = rt

    failures = []
    for name in ("asr", "tts", "roundtrip"):
        c = out["cells"][name]
        if c.get("status") != 200 or c.get("problem"):
            failures.append(f"{name}: {c.get('problem') or 'not 200'}")
        elif "wer" in c and c["wer"] > c["threshold"]:
            failures.append(f"{name}: word error rate {c['wer']} > {c['threshold']}")
    out["failures"] = failures
    out["verdict"] = "ok" if not failures else "failed"
    return out


class _Stub(BaseHTTPRequestHandler):
    """Serves the two endpoints; mode picks what the round trip hears."""

    mode = "clean"  # clean | garbled | no-tts
    asr_text = "The quarterly report is due on Thursday so please finish it by noon."
    rt_text = "The quarterly report is due on Thursday so please finish it by noon."

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - base signature
        return

    def _send(self, raw: bytes, ctype: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):  # noqa: N802
        if self.path.rstrip("/") == "/v1/models":
            return self._send(json.dumps({"data": [{"id": "stub/audio"}]}).encode(),
                              "application/json")
        return self._send(b"{}", "application/json", 404)

    def do_POST(self):  # noqa: N802
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0)
        path = self.path.rstrip("/")
        if path == "/v1/audio/transcriptions":
            # the round-trip fixture arrives as a file literally named tts.wav
            text = self.rt_text if b'filename="tts.wav"' in raw else self.asr_text
            return self._send(json.dumps({"text": text}).encode(), "application/json")
        if path == "/tts":
            if self.mode == "no-tts":
                return self._send(
                    json.dumps({"error": {"message": "this server does not support audio "
                                                     "generation"}}).encode(),
                    "application/json", 501)
            return self._send(_stub_wav(), "audio/wav")
        return self._send(b"{}", "application/json", 404)


def _stub_wav(seconds: float = 0.4, rate: int = 16000) -> bytes:
    n = int(seconds * rate)
    pcm = b"".join(struct.pack("<h", 8000 if (i // 40) % 2 else -8000) for i in range(n))
    fmt = struct.pack("<HHIIHH", 1, 1, rate, rate * 2, 2, 16)
    return (b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVE" + b"fmt "
            + struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", len(pcm)) + pcm)


def selftest() -> int:
    failures: list[str] = []
    if wer("a b c", "a b c") != 0.0:
        failures.append("identical text did not score 0")
    if abs(wer("the cat sat", "the cat sit") - 1 / 3) > 1e-9:
        failures.append("one substitution in three did not score 1/3")
    if wer("the cat sat", "the cat sat down") != 1 / 3:
        failures.append("one insertion did not score 1/3")
    if wer("The quarterly report, due Thursday.", "the quarterly report due thursday") != 0.0:
        failures.append("case and punctuation were not normalised away")
    if wer("a b c d", "x y z w") != 1.0:
        failures.append("total mismatch did not score 1.0")

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Stub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    wav = Path(__file__).with_name(".selftest-asr.wav")
    wav.write_bytes(_stub_wav())
    try:
        if _served_id(base) != "stub/audio":
            failures.append("served id resolution")

        _Stub.mode = "clean"
        good = probe(base, "stub/audio", wav, _Stub.asr_text, "en", _Stub.asr_text, "",
                     None, 0.25, 0.40)
        if good["verdict"] != "ok":
            failures.append(f"clean run not ok: {good['failures']}")
        if good["cells"]["tts"].get("seconds", 0) <= 0:
            failures.append("tts cell did not read the wav's duration")
        if good["cells"]["roundtrip"].get("wer") != 0.0:
            failures.append("round trip did not score 0 on identical text")

        _Stub.mode = "clean"
        _Stub.rt_text = "the quarterly report is due on thursday so please finish it"
        garbled = probe(base, "stub/audio", wav, _Stub.asr_text, "en", _Stub.asr_text, "",
                        None, 0.25, 0.04)
        if garbled["verdict"] != "failed" or not any("roundtrip" in f for f in garbled["failures"]):
            failures.append(f"round-trip threshold not enforced: {garbled['verdict']}")
        _Stub.rt_text = _Stub.asr_text

        _Stub.mode = "clean"
        wrong = probe(base, "stub/audio", wav, "completely different words here", "en",
                      _Stub.asr_text, "", None, 0.25, 0.40)
        if wrong["verdict"] != "failed":
            failures.append("a transcript that ignores the audio still passed")

        _Stub.mode = "no-tts"
        dead = probe(base, "stub/audio", wav, _Stub.asr_text, "en", _Stub.asr_text, "",
                     None, 0.25, 0.40)
        if dead["cells"]["tts"]["status"] != 501 or not dead["cells"]["tts"].get("problem"):
            failures.append("501 from /tts not surfaced")
        if dead["cells"]["roundtrip"].get("status") != 0:
            failures.append("round trip ran without audio")
        if "does not support audio generation" not in dead["cells"]["tts"]["problem"]:
            failures.append("501 lost the endpoint's own text")

        bad = probe("http://127.0.0.1:1", "stub/audio", wav, _Stub.asr_text, "en",
                    _Stub.asr_text, "", None, 0.25, 0.40)
        if bad["verdict"] != "failed":
            failures.append("dead endpoint not failed")

        info, why = wav_info(b"")
        if why != "not a RIFF/WAVE file":
            failures.append("non-wav blob accepted as audio")
        silent = _stub_wav()
        silent = silent[:44] + b"\x00" * (len(silent) - 44)
        if "silent" not in wav_info(silent)[1]:
            failures.append("silence accepted as speech")
    finally:
        server.shutdown()
        wav.unlink(missing_ok=True)
    for f in failures:
        print(f"FAIL {f}", file=sys.stderr)
    print("audio-asr-tts-probe selftest:", "ok" if not failures else f"{len(failures)} failure(s)")
    return 0 if not failures else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--base-url")
    p.add_argument("--model", default="auto", help="served id; 'auto' reads /v1/models")
    p.add_argument("--wav", help="known-text clip: the ASR fixture")
    p.add_argument("--statement", help="the text --wav is known to speak")
    p.add_argument("--lang", default="en", help="ISO 639-1 code for both cells")
    p.add_argument("--tts-text", default=None,
                   help="text to synthesise (default: --statement)")
    p.add_argument("--voice", default="", help="server voice name; empty uses its default")
    p.add_argument("--tts-out", default=None, help="where to keep the synthesised wav")
    p.add_argument("--asr-max", type=float, default=0.25,
                   help="word error rate ceiling for the ASR cell (default 0.25)")
    p.add_argument("--rt-max", type=float, default=0.40,
                   help="word error rate ceiling for the round trip (default 0.40)")
    p.add_argument("--json", help="write the full result here")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args(argv)

    if args.selftest:
        return selftest()
    missing = [n for n, v in (("--base-url", args.base_url), ("--wav", args.wav),
                              ("--statement", args.statement)) if not v]
    if missing:
        p.error("required: " + ", ".join(missing) + " (or --selftest)")

    model = args.model
    if model in ("", "auto", None):
        resolved = _served_id(args.base_url)
        if not resolved:
            print("error: /v1/models did not answer; pass --model", file=sys.stderr)
            return 2
        model = resolved

    wav = Path(args.wav).expanduser()
    try:
        wav.read_bytes()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    tts_out = Path(args.tts_out).expanduser() if args.tts_out else (
        Path(args.json).with_suffix(".tts.wav") if args.json else None)

    try:
        result = probe(args.base_url, model, wav, args.statement, args.lang,
                       args.tts_text or args.statement, args.voice, tts_out,
                       args.asr_max, args.rt_max)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=1))
    for name, cell in result["cells"].items():
        bits = [f"status={cell.get('status')}"]
        if "wer" in cell:
            bits.append(f"wer={cell['wer']} (max {cell['threshold']})")
        if "seconds" in cell:
            bits.append(f"{cell['seconds']} s @ {cell.get('sample_rate')} Hz")
        if cell.get("transcript"):
            bits.append(f"transcript={cell['transcript']!r}")
        print(f"{name:9s} " + " ".join(bits)
              + (f" problem={cell['problem']}" if cell.get("problem") else ""))
        if cell.get("problem"):
            print(f"  endpoint said: {cell['problem']}", file=sys.stderr)
    print(f"verdict: {result['verdict']}")
    return 0 if result["verdict"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())