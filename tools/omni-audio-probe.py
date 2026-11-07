#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Audio-input probe for an omni decision arm served at ``/v1/systemone``.

What it proves: the endpoint takes a spoken state (an ``input_audio`` content
part carrying a base64 WAV), answers with a schema-valid typed decision inside
the served window, and gives the same answer as the same statement typed out.

Cannot prove: transcription fidelity, word error rate, robustness to accent or
noise, or that a matching answer came from the speech language prior on the
question. One fixture sentence is not an audio benchmark.

Two cell shapes, because the endpoint answers them differently and a probe that
read only one would report a pass it never observed:

* ``choice`` — a label plus confidence (``{"choice": "yes", "confidence": 0.978}``).
  This is the acceptance cell: a label exists, so ``--expect`` can hold or miss.
* ``noul`` — a probability over ``true``/``false`` (``{"true": 0.944}``), never a
  label. The probe reads the distribution's direction and records the
  probability; it never invents a label for it.

A booted d1-Omni-2B on this image answered ``choice`` on text and refused the
spoken state at ``/v1/systemone`` (the WAV's base64 was tokenised as text —
364,286 tokens against an 8192 window), so the audio cell now carries the
endpoint's own body into the result and prints it on failure: a null label with
no endpoint text is the silent pass this probe must not produce.

Usage
-----
::

  python3 tools/omni-audio-probe.py --selftest            # offline stub, ~1 s
  python3 tools/omni-audio-probe.py \\
      --base-url http://<node>:8020 \\
      --wav ~/benchmarks/omni-repin-20261107/drama-weights/drama.wav \\
      --statement "The quarterly report is due on Thursday, so please finish it by noon." \\
      --question "Is the quarterly report due on Thursday?" --expect yes \\
      --json omni-audio.json

Exit codes: ``0`` both cells answered and agree (and ``--expect`` held, if
given), ``1`` a cell failed or the two cells disagree, ``2`` bad flags or an
unreadable fixture.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

TIMEOUT = 300.0
ACCEPT_QID = "accept-1"
NOUL_QID = "noul-1"


def _post(base: str, body: dict[str, Any], timeout: float = TIMEOUT) -> tuple[int, dict[str, Any] | str, float]:
    """-> (status, parsed body or raw text, wall seconds)."""
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


def _slot(body: dict[str, Any], question_id: str) -> tuple[dict[str, Any] | None, str]:
    answers = body.get("answers") if isinstance(body, dict) else None
    if not isinstance(answers, dict):
        return None, "response carries no answers map"
    slot = answers.get(question_id)
    if not isinstance(slot, dict):
        return None, f"answers has no {question_id!r}"
    return slot, ""


def _choice(slot: dict[str, Any]) -> tuple[str | None, float | None, str]:
    """-> (label, confidence, why) from a ``type:choice`` answer slot."""
    for key in ("choice", "answer", "label"):
        if isinstance(slot.get(key), str):
            conf = slot.get("confidence")
            return slot[key], (float(conf) if isinstance(conf, (int, float)) else None), ""
    return None, None, f"choice slot carries no label ({sorted(slot)})"


def _noul(slot: dict[str, Any]) -> tuple[bool | None, float | None, str]:
    """-> (direction, p_true, why) from a ``type:noul`` answer slot.

    The endpoint answers noul with a probability, so this reads the
    distribution — ``{"true": 0.944}``, or the same under ``probabilities`` —
    and reports the argmax direction. A slot holding an explicit ``noul``
    number is that probability (``p(true)``), read the same way.
    """
    dist = slot.get("probabilities") or slot.get("distribution") or slot.get("answer_distribution")
    if not isinstance(dist, dict):
        dist = {k: v for k, v in slot.items() if k in ("true", "false", "yes", "no")}
    if not dist and isinstance(slot.get("noul"), (int, float)):
        dist = {"true": float(slot["noul"]), "false": 1.0 - float(slot["noul"])}
    vals = {k: float(v) for k, v in dist.items() if isinstance(v, (int, float))}
    if not vals:
        return None, None, f"noul slot carries no probability ({sorted(slot)})"
    p_true = vals.get("true", vals.get("yes"))
    if p_true is None:
        return None, None, f"noul distribution is not true/false keyed ({sorted(vals)})"
    return p_true > 0.5, p_true, ""


def _wav_data_url(path: Path) -> str:
    raw = path.read_bytes()
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError(f"{path}: not a RIFF/WAVE file")
    return "data:audio/wav;base64," + base64.b64encode(raw).decode("ascii")


def _questions(question: str) -> dict[str, Any]:
    return {
        ACCEPT_QID: {
            "type": "choice",
            "instructions": question,
            "criteria": {"yes": "the statement is true", "no": "the statement is false"},
        },
        NOUL_QID: {"type": "noul", "instructions": question, "criteria": {}},
    }


def _audio_body(model: str, spoken: str, question: str) -> dict[str, Any]:
    return {
        "model": model,
        "state": [{"type": "input_audio", "input_audio": {"data": spoken}}],
        "questions": _questions(question),
    }


def _text_body(model: str, statement: str, question: str) -> dict[str, Any]:
    return {"model": model, "state": statement, "questions": _questions(question)}


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
    for name, body in checks:
        status, payload, elapsed = _post(base, body)
        cell: dict[str, Any] = {"status": status, "wall_s": round(elapsed, 3)}
        if status == 200 and isinstance(payload, dict):
            slot, why = _slot(payload, ACCEPT_QID)
            if slot is not None:
                label, conf, why = _choice(slot)
                cell["label"] = label
                if conf is not None:
                    cell["confidence"] = conf
            noul_slot, _ = _slot(payload, NOUL_QID)
            if noul_slot is not None:
                direction, p_true, _ = _noul(noul_slot)
                cell["noul_true"] = direction
                if p_true is not None:
                    cell["noul_p_true"] = round(p_true, 4)
            cell["answers"] = payload.get("answers")
            cell["usage"] = payload.get("usage")
            if "label" not in cell:
                cell["problem"] = why
        else:
            # Loud, not silent: the endpoint's own body is the finding.
            cell["problem"] = str(payload)
        out["cells"][name] = cell

    ok = all(c.get("status") == 200 and c.get("label") is not None for c in out["cells"].values())
    audio_label = out["cells"]["audio"].get("label")
    agree = audio_label is not None and audio_label == out["cells"]["text"].get("label")
    out["verdict"] = "ok" if ok and agree else ("disagree" if ok else "failed")
    if expect is not None:
        out["expect_held"] = audio_label == expect
        if not out["expect_held"]:
            out["verdict"] = "expect-missed"
    return out


class _Stub(BaseHTTPRequestHandler):
    mode = "good"  # good | disagree | audio-400 | audio-tokenflood

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
        if spoken and self.mode == "audio-tokenflood":
            return self._send(
                {"error": {"message": "the prompt is too long: 364286 tokens > 8192 n_ctx"}}, 500
            )
        label = "yes"
        p_true = 0.944
        if spoken and self.mode == "disagree":
            label, p_true = "no", 0.05
        return self._send(
            {
                "answers": {
                    ACCEPT_QID: {"choice": label, "confidence": 0.978},
                    NOUL_QID: {"true": p_true, "false": round(1.0 - p_true, 4)},
                }
            }
        )


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
        if good["cells"]["text"].get("noul_true") is not True:
            failures.append("noul probability direction not read as true")
        if good["cells"]["text"].get("label") != "yes":
            failures.append("choice label not read from a choice slot")

        _Stub.mode = "disagree"
        bad = probe(base, "stub/omni", wav, "a statement", "a question", None)
        if bad["verdict"] != "disagree":
            failures.append(f"disagreement not detected: {bad['verdict']}")

        _Stub.mode = "audio-400"
        dead = probe(base, "stub/omni", wav, "a statement", "a question", None)
        if dead["verdict"] != "failed" or dead["cells"]["audio"]["status"] != 400:
            failures.append(f"audio 400 not surfaced: {dead['verdict']}")
        if "no audio input" not in dead["cells"]["audio"].get("problem", ""):
            failures.append("audio 400 lost the endpoint's own text")

        _Stub.mode = "audio-tokenflood"
        flood = probe(base, "stub/omni", wav, "a statement", "a question", None)
        if "364286 tokens" not in flood["cells"]["audio"].get("problem", ""):
            failures.append("audio 500 lost the endpoint's token-count text")
        if flood["cells"]["audio"].get("label") is not None:
            failures.append("failed audio cell produced a label")

        _Stub.mode = "good"
        missed = probe(base, "stub/omni", wav, "a statement", "a question", "no")
        if missed["verdict"] != "expect-missed":
            failures.append(f"expect miss not flagged: {missed['verdict']}")

        if _noul({"true": 0.9, "false": 0.1})[:2] != (True, 0.9):
            failures.append("noul distribution shape not read")
        if _noul({"noul": 0.2})[:2] != (False, 0.2):
            failures.append("noul scalar shape not read")
        if _noul({"probabilities": {"true": 0.6, "false": 0.4}})[0] is not True:
            failures.append("noul under probabilities not read")
        if _noul({"unrelated": 1.0})[0] is not None:
            failures.append("noul invented a direction from an unreadable slot")

        bad_wav = Path(__file__).with_name(".selftest-notwav.wav")
        bad_wav.write_bytes(b"not a wav")
        try:
            probe(base, "stub/omni", bad_wav, "s", "q", None)
            failures.append("non-WAV fixture accepted")
        except ValueError:
            pass
        finally:
            bad_wav.unlink(missing_ok=True)

        down = probe("http://127.0.0.1:1", "stub/omni", wav, "s", "q", None)
        if down["verdict"] != "failed":
            failures.append(f"dead endpoint not failed: {down['verdict']}")
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
        line = (f"{name:5s} status={cell['status']} label={cell.get('label')!r} "
                f"noul_true={cell.get('noul_true')} p_true={cell.get('noul_p_true')} "
                f"wall={cell['wall_s']}s")
        print(line + (f" problem={cell['problem']}" if cell.get("problem") else ""))
        if cell.get("problem") and cell["status"] != 200:
            print(f"  endpoint said: {cell['problem']}", file=sys.stderr)
    print(f"verdict: {result['verdict']}"
          + (f" (expect {result['expect']} → {result.get('expect_held')})" if args.expect else ""))
    return 0 if result["verdict"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())