#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Audio-input probe for an omni decision arm served at ``/v1/systemone``.

The decision lane's text arms are probed by ``decision-ladder.py``; an omni arm
adds a surface that tool has no cell for: a **spoken** state. This probe sends
the same statement twice — once as text, once as the fixture WAV — and asks the
same typed question about it, so the audio path is compared against its own text
control rather than against a number nobody measured.

What a PASS proves, and what it cannot
--------------------------------------
Proves: the endpoint accepts an ``input_audio`` part (base64 WAV, data URL or
bare), returns a schema-valid typed answer over it inside the served window, and
gives the same label as the same statement typed out. That last one is the real
falsifier — a decoder that ignored the audio would answer from the question text
alone, and a decoder that heard noise would answer differently from its own text
control.

Cannot prove: transcription fidelity, word error rate, robustness to accent or
noise, or that a matching label came from the speech rather than from a language
prior on the question. One fixture sentence is not an audio benchmark, and no
in-tree instrument scores audio understanding. A disagreement is a signal; an
agreement is not a certificate.

Request shape (llama.cpp ``server-decision.cpp`` at 6023692)
------------------------------------------------------------
A spoken state or question carries ``input_audio`` as a content part beside the
usual text parts, and the decision endpoint loads it through the same media
path it uses for images::

    {"model": "<served id>", "state": [{"type": "input_audio",
        "input_audio": {"data": "data:audio/wav;base64,..."}}],
     "questions": {"q1": {"type": "noul", "instructions": "<question>",
                          "criteria": {}}}}

Usage
-----
::

    python3 tools/omni-audio-probe.py \\
        --base-url http://<node>:8020 \\
        --wav ~/benchmarks/omni-repin-20261107/drama-weights/drama.wav \\
        --statement "The quarterly report is due on Thursday, so please finish it by noon." \\
        --question "Is the quarterly report due on Thursday?" --expect yes \\
        --json omni-audio.json

    python3 tools/omni-audio-probe.py --selftest     # offline, stub server, ~1 s

Exit codes: ``0`` both cells answered and agree (and ``--expect`` held, when
given), ``1`` a cell failed or the two cells disagree, ``2`` bad flags or an
unreadable fixture.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

TIMEOUT = 300.0


def _post(base: str, body: dict[str, Any], timeout: float = TIMEOUT) -> tuple[int, dict[str, Any] | str, float]:
    """-> (status, parsed body or raw text, wall seconds)."""
    import time

    url = base.rstrip("/") + "/v1/systemone"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            elapsed = time.time() - t0
            try:
                return r.status, json.loads(raw), elapsed
            except json.JSONDecodeError:
                return r.status, raw.decode("utf-8", "replace"), elapsed
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        return e.code, detail, time.time() - t0
    except (urllib.error.URLError, OSError) as e:
        return 0, f"{type(e).__name__}: {e}", time.time() - t0


def _served_id(base: str, timeout: float = 30.0) -> str | None:
    try:
        with urllib.request.urlopen(base.rstrip("/") + "/v1/models", timeout=timeout) as r:
            data = json.load(r)
        return data["data"][0]["id"]
    except Exception:  # noqa: BLE001 - any failure means "ask for it"
        return None


def _label(body: dict[str, Any], question_id: str) -> tuple[str | None, str]:
    """-> (label or None, why). Accepts the endpoint's answers map."""
    answers = body.get("answers") if isinstance(body, dict) else None
    if not isinstance(answers, dict):
        return None, "response carries no answers map"
    slot = answers.get(question_id)
    if not isinstance(slot, dict):
        return None, f"answers has no {question_id!r}"
    for key in ("noul", "answer", "choice", "label", "result"):
        if key in slot and isinstance(slot[key], (str, bool)):
            return str(slot[key]), ""
    return None, f"answers[{question_id!r}] carries no label ({sorted(slot)})"


def _wav_data_url(path: Path) -> str:
    raw = path.read_bytes()
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError(f"{path}: not a RIFF/WAVE file")
    return "data:audio/wav;base64," + base64.b64encode(raw).decode("ascii")


def _audio_body(model: str, spoken: str, question: str) -> dict[str, Any]:
    return {
        "model": model,
        "state": [{"type": "input_audio", "input_audio": {"data": spoken}}],
        "questions": {QID: {"type": "noul", "instructions": question, "criteria": {}}},
    }


def _text_body(model: str, statement: str, question: str) -> dict[str, Any]:
    return {
        "model": model,
        "state": statement,
        "questions": {QID: {"type": "noul", "instructions": question, "criteria": {}}},
    }


QID = "audio-1"


def probe(base: str, model: str, wav: Path, statement: str, question: str, expect: str | None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "base_url": base,
        "model": model,
        "wav": str(wav),
        "question": question,
        "expect": expect,
        "cells": {},
    }
    data_url = _wav_data_url(wav)
    out["wav_bytes"] = len(base64.b64decode(data_url.split(",", 1)[1]))

    checks = (
        ("audio", _audio_body(model, data_url, question)),
        ("text", _text_body(model, statement, question)),
    )
    labels: dict[str, str | None] = {}
    for name, body in checks:
        status, payload, elapsed = _post(base, body)
        cell: dict[str, Any] = {"status": status, "wall_s": round(elapsed, 3)}
        if status == 200 and isinstance(payload, dict):
            label, why = _label(payload, QID)
            cell["label"] = label
            cell["answers"] = payload.get("answers")
            cell["usage"] = payload.get("usage")
            if why:
                cell["problem"] = why
        else:
            cell["problem"] = str(payload)[:400]
        labels[name] = cell.get("label")
        out["cells"][name] = cell

    ok = all(c.get("status") == 200 and c.get("label") is not None for c in out["cells"].values())
    agree = labels.get("audio") is not None and labels.get("audio") == labels.get("text")
    out["verdict"] = "ok" if ok and agree else ("disagree" if ok else "failed")
    if expect is not None:
        out["expect_held"] = labels.get("audio") == expect
        if not out["expect_held"]:
            out["verdict"] = "expect-missed"
    return out


class _Stub(BaseHTTPRequestHandler):
    mode = "good"  # good | disagree | audio-400

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - base signature
        return

    def _send(self, payload: dict[str, Any], status: int = 200) -> None:
        raw = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):  # noqa: N802
        if self.path.rstrip("/") == "/v1/models":
            return self._send({"data": [{"id": "stub/omni"}]})
        return self._send({"error": "not found"}, 404)

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        state = body.get("state")
        spoken = isinstance(state, list) and any(
            isinstance(p, dict) and p.get("type") == "input_audio" for p in state
        )
        if spoken and self.mode == "audio-400":
            return self._send({"error": {"message": "this model has no audio input"}}, 400)
        label = "yes"
        if spoken and self.mode == "disagree":
            label = "no"
        return self._send({"answers": {QID: {"noul": label, "probabilities": {"yes": 0.9, "no": 0.1}}}})


def selftest() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Stub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    wav = Path(__file__).with_name(".selftest-omni.wav")
    wav.write_bytes(b"RIFF" + (36).to_bytes(4, "little") + b"WAVE" + b"fmt " + (16).to_bytes(4, "little"))
    failures: list[str] = []
    try:
        assert _served_id(base) == "stub/omni", "served id resolution"

        _Stub.mode = "good"
        good = probe(base, "stub/omni", wav, "a statement", "a question", "yes")
        if good["verdict"] != "ok" or not good.get("expect_held"):
            failures.append(f"good run not ok: {good['verdict']}")

        _Stub.mode = "disagree"
        bad = probe(base, "stub/omni", wav, "a statement", "a question", None)
        if bad["verdict"] != "disagree":
            failures.append(f"disagreement not detected: {bad['verdict']}")

        _Stub.mode = "audio-400"
        dead = probe(base, "stub/omni", wav, "a statement", "a question", None)
        if dead["verdict"] != "failed" or dead["cells"]["audio"]["status"] != 400:
            failures.append(f"audio 400 not surfaced: {dead['verdict']}")

        _Stub.mode = "good"
        missed = probe(base, "stub/omni", wav, "a statement", "a question", "no")
        if missed["verdict"] != "expect-missed":
            failures.append(f"expect miss not flagged: {missed['verdict']}")

        bad_wav = Path(__file__).with_name(".selftest-notwav.wav")
        bad_wav.write_bytes(b"not a wav")
        try:
            probe(base, "stub/omni", bad_wav, "s", "q", None)
            failures.append("non-WAV fixture accepted")
        except ValueError:
            pass
        finally:
            bad_wav.unlink(missing_ok=True)

        empty = Path(__file__).with_name(".selftest-dead.wav")
        empty.write_bytes(wav.read_bytes())
        try:
            _Stub.mode = "good"
            down = probe("http://127.0.0.1:1", "stub/omni", empty, "s", "q", None)
            if down["verdict"] != "failed":
                failures.append(f"dead endpoint not failed: {down['verdict']}")
        finally:
            empty.unlink(missing_ok=True)
    finally:
        server.shutdown()
        wav.unlink(missing_ok=True)
    for f in failures:
        print(f"FAIL {f}", file=sys.stderr)
    print("omni-audio-probe selftest:", "ok" if not failures else f"{len(failures)} failure(s)")
    return 0 if not failures else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--base-url")
    p.add_argument("--model", default="auto", help="served id; 'auto' reads /v1/models")
    p.add_argument("--wav", help="fixture WAV that speaks --statement")
    p.add_argument("--statement", help="the same sentence typed out, for the text control")
    p.add_argument("--question", default="Is the statement true?",
                   help="typed question asked of both cells")
    p.add_argument("--expect", default=None, help="expected label; a miss is reported, not hidden")
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

    try:
        result = probe(args.base_url, model, Path(args.wav).expanduser(),
                       args.statement, args.question, args.expect)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=1))
    for name, cell in result["cells"].items():
        print(f"{name:5s} status={cell['status']} label={cell.get('label')!r} "
              f"wall={cell['wall_s']}s" + (f" problem={cell['problem']}" if cell.get("problem") else ""))
    print(f"verdict: {result['verdict']}"
          + (f" (expect {result['expect']} → {result.get('expect_held')})" if args.expect else ""))
    return 0 if result["verdict"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())