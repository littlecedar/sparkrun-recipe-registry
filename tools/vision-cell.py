#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Travis Wichert
# SPDX-License-Identifier: AGPL-3.0-or-later
"""vision-cell.py -- what an image costs and whether the answer is right, on any
OpenAI-compatible serve.

One boot, three byte-deterministic images rendered here (a shape, a two-object
layout, a text-bearing image) so two engines see identical input: per image a
graded question at temperature 0 (three runs, latency median) plus one short
description, and one text-only request of the same question per image whose
prompt-token count gives the image's token delta. Records status, wall time,
the whole ``usage`` object (image tokens included when the engine reports them),
the answer and the key match. Correctness is reported, never gated: a wrong
answer is a finding about the model, not a tool failure.

    tools/vision-cell.py --base-url http://HOST:8000 --api-key-env PICOM_API_KEY \
        --outdir ~/benchmarks/lc-vision-20261119/picom --image-id picom-prod
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
import zlib
from typing import Any

VERSION = "1.0"
SIZE = 512
WHITE = (255, 255, 255)

GLYPHS = {
    # 5x7, one string per row; only the letters the fixture needs.
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
}


class Canvas:
    def __init__(self, w: int, h: int, rgb=WHITE):
        self.w, self.h = w, h
        self.px = bytearray(bytes(rgb) * w * h)

    def _put(self, x: int, y: int, rgb) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = bytes(rgb)

    def rect(self, x0: int, y0: int, x1: int, y1: int, rgb) -> None:
        for y in range(y0, y1):
            for x in range(x0, x1):
                self._put(x, y, rgb)

    def circle(self, cx: int, cy: int, r: int, rgb) -> None:
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    self._put(x, y, rgb)

    def text(self, word: str, x0: int, y0: int, scale: int, rgb) -> None:
        for n, ch in enumerate(word):
            for ry, row in enumerate(GLYPHS[ch]):
                for rx, bit in enumerate(row):
                    if bit == "1":
                        self.rect(x0 + (n * 6 + rx) * scale, y0 + ry * scale,
                                  x0 + (n * 6 + rx + 1) * scale,
                                  y0 + (ry + 1) * scale, rgb)

    def png(self) -> bytes:
        def chunk(tag: bytes, data: bytes) -> bytes:
            return (len(data).to_bytes(4, "big") + tag + data
                    + zlib.crc32(tag + data).to_bytes(4, "big"))
        raw = b"".join(b"\x00" + bytes(self.px[y * self.w * 3:(y + 1) * self.w * 3])
                       for y in range(self.h))
        return (b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", self.w.to_bytes(4, "big") + self.h.to_bytes(4, "big")
                        + bytes((8, 2, 0, 0, 0)))
                + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def fixtures() -> list[dict[str, Any]]:
    """Three images with a graded key; bytes depend only on this source."""
    shape = Canvas(SIZE, SIZE)
    shape.circle(SIZE // 2, SIZE // 2, 140, (200, 30, 30))
    layout = Canvas(SIZE, SIZE)
    layout.rect(96, 176, 256, 336, (30, 60, 200))
    layout.circle(352, 256, 80, (240, 210, 30))
    text = Canvas(SIZE, SIZE)
    text.text("SPARK", (SIZE - 5 * 6 * 12 + 12) // 2, 212, 12, (10, 10, 10))
    return [
        {"name": "shape", "canvas": shape,
         "question": "How many shapes are in this image and what colour is it? "
                     "Answer exactly '<count> <colour>', for example '2 blue'.",
         "key": "1 red"},
        {"name": "layout", "canvas": layout,
         "question": "The image holds a blue square and a yellow circle. Is the "
                     "square to the left or to the right of the circle? "
                     "Answer 'left' or 'right' only.",
         "key": "left"},
        {"name": "text", "canvas": text,
         "question": "What word is written in this image? Answer the word only.",
         "key": "spark"},
    ]


def headers(api_key: str | None) -> dict[str, str]:
    out = {"Content-Type": "application/json"}
    if api_key:
        out["Authorization"] = "Bearer " + api_key
    return out


def url(base: str, path: str) -> str:
    return base.rstrip("/") + path


def served_id(base: str, api_key: str | None, timeout: float) -> str:
    req = urllib.request.Request(url(base, "/v1/models"), headers=headers(api_key))
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)["data"][0]["id"]


def _body(model: str, prompt: str, max_tokens: int,
          image_b64: str | None) -> dict[str, Any]:
    content: list[dict] = [{"type": "text", "text": prompt}]
    if image_b64:
        content.append({"type": "image_url",
                        "image_url": {"url": "data:image/png;base64," + image_b64}})
    return {"model": model, "messages": [{"role": "user", "content": content}],
            "temperature": 0, "max_tokens": max_tokens}


def ask(base: str, model: str, prompt: str, max_tokens: int, image_b64: str | None,
        api_key: str | None, timeout: float) -> dict[str, Any]:
    rec: dict[str, Any] = {"status": None, "wall_s": None, "usage": None, "answer": "",
                 "error": None}
    req = urllib.request.Request(
        url(base, "/v1/chat/completions"),
        data=json.dumps(_body(model, prompt, max_tokens, image_b64)).encode(),
        headers=headers(api_key))
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            rec["status"] = resp.status
            payload = json.load(resp)
    except urllib.error.HTTPError as exc:
        rec["status"] = exc.code
        rec["error"] = "HTTP %s: %s" % (exc.code, exc.read()[:300].decode("replace"))
        rec["wall_s"] = round(time.perf_counter() - started, 3)
        return rec
    except Exception as exc:  # noqa: BLE001 - the cell records, never raises
        rec["error"] = "%s: %s" % (type(exc).__name__, exc)
        rec["wall_s"] = round(time.perf_counter() - started, 3)
        return rec
    rec["wall_s"] = round(time.perf_counter() - started, 3)
    rec["usage"] = payload.get("usage")
    choices = payload.get("choices") or [{}]
    rec["answer"] = (choices[0].get("message") or {}).get("content") or ""
    rec["finish_reason"] = choices[0].get("finish_reason")
    return rec


def norm(text: str) -> str:
    keep = "".join(c.lower() if (c.isalnum() or c.isspace()) else " " for c in text)
    return " ".join(keep.split())


def matches(answer: str, key: str) -> bool:
    return norm(key) in norm(answer)


def report(base: str, model: str | None, outdir: str, api_key: str | None,
           runs: int, timeout: float, image_id: str | None) -> dict[str, Any]:
    os.makedirs(outdir, exist_ok=True)
    model = model or served_id(base, api_key, timeout)
    images = []
    for fx in fixtures():
        png = fx["canvas"].png()
        path = os.path.join(outdir, fx["name"] + ".png")
        with open(path, "wb") as fh:
            fh.write(png)
        images.append({**fx, "png": png,
                       "sha256": hashlib.sha256(png).hexdigest(), "path": path})
    rows = []
    for img in images:
        b64 = base64.b64encode(img["png"]).decode("ascii")
        text_only = ask(base, model, img["question"], 32, None, api_key, timeout)
        question_runs = [ask(base, model, img["question"], 32, b64, api_key, timeout)
                         for _ in range(runs)]
        describe = ask(base, model, "Describe this image in one short sentence.",
                       64, b64, api_key, timeout)
        walls = [r["wall_s"] for r in question_runs if r["wall_s"] is not None]
        first = question_runs[0]
        img_tokens = None
        if (first["usage"] or {}).get("prompt_tokens") and \
                (text_only["usage"] or {}).get("prompt_tokens"):
            img_tokens = (first["usage"]["prompt_tokens"]
                          - text_only["usage"]["prompt_tokens"])
        row: dict[str, Any] = {
            "image": img["name"], "sha256": img["sha256"], "question": img["question"],
            "key": img["key"],
            "answers": [r["answer"] for r in question_runs],
            "statuses": [r["status"] for r in question_runs],
            "key_match": matches(first["answer"], img["key"]),
            "latency_s": [r["wall_s"] for r in question_runs],
            "latency_median_s": round(statistics.median(walls), 3) if walls else None,
            "completion_tokens": [(r["usage"] or {}).get("completion_tokens")
                                  for r in question_runs],
            "finish_reasons": [r.get("finish_reason") for r in question_runs],
            "text_only_prompt_tokens": (text_only["usage"] or {}).get("prompt_tokens"),
            "image_prompt_tokens": (first["usage"] or {}).get("prompt_tokens"),
            "image_token_delta": img_tokens,
            "usage_full": first["usage"],
            "describe": {"answer": describe["answer"],
                         "wall_s": describe["wall_s"],
                         "completion_tokens": (describe["usage"] or {}).get(
                             "completion_tokens"),
                         "usage": describe["usage"],
                         "status": describe["status"]},
            "errors": [r["error"] for r in question_runs + [text_only, describe]
                       if r["error"]],
            "runs": question_runs,
            "text_only_run": text_only,
        }
        rows.append(row)
    out = {"tool_version": VERSION, "base_url": base, "model": model,
           "image_id": image_id, "runs": runs, "temperature": 0,
           "images": [{k: img[k] for k in ("name", "sha256", "key")} for img in images],
           "cells": rows}
    with open(os.path.join(outdir, "vision.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    return out


def selftest() -> int:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading

    a = fixtures()[2]["canvas"].png()
    assert a == fixtures()[2]["canvas"].png(), "fixture bytes are not deterministic"
    assert a.startswith(b"\x89PNG") and len(a) > 200, len(a)
    assert len({f["canvas"].png() for f in fixtures()[:2]}) == 2, "fixtures collide"
    assert matches("1 Red.", "1 red") and not matches("2 blue", "1 red")
    assert matches("The word is SPARK", "spark") and not matches("SPORK", "spark")
    assert norm("Left!") == "left"

    class Stub(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            pass

        def do_GET(self):
            body = json.dumps({"data": [{"id": "stub"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            has_image = any(p.get("type") == "image_url"
                            for p in req["messages"][0]["content"])
            text = req["messages"][0]["content"][0]["text"]
            answer = ("SPARK" if "word" in text else "1 red" if "colour" in text
                      else "left")
            if "Describe" in text:
                answer = "a picture"
            body = json.dumps({
                "choices": [{"message": {"content": answer}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 40 if has_image else 25,
                          "completion_tokens": 3}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

    srv = HTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        base = "http://127.0.0.1:%d" % srv.server_port
        out = report(base, None, os.path.join("/tmp", "vision-cell-selftest"), None,
                     2, 20.0, None)
        cells = out["cells"]
        assert [c["key_match"] for c in cells] == [True, True, True], cells
        assert cells[0]["image_token_delta"] == 15, cells[0]
        assert all(len(c["latency_s"]) == 2 for c in cells), cells
        bad = {**cells[0], "answers": ["2 blue"]}
        assert not matches(bad["answers"][0], bad["key"]), "a wrong answer must fail"
    finally:
        srv.shutdown()
    print("selftest: OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--base-url", help="serve root, e.g. http://HOST:8000")
    ap.add_argument("--model", default=None, help="served id; default reads /v1/models")
    ap.add_argument("--outdir", help="receipt directory for images and vision.json")
    ap.add_argument("--api-key", default=None, help="bearer token; never printed")
    ap.add_argument("--api-key-env", default=None,
                    help="read the bearer token from this variable (keeps it off argv)")
    ap.add_argument("--runs", type=int, default=3, help="question runs per image")
    ap.add_argument("--timeout", type=float, default=600.0)
    ap.add_argument("--image-id", default=None, help="served image digest/ref, echoed")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--version", action="version", version="vision-cell " + VERSION)
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.base_url or not args.outdir:
        print("--base-url and --outdir are required", file=sys.stderr)
        return 2
    key = args.api_key or (os.environ.get(args.api_key_env) if args.api_key_env else None)
    try:
        out = report(args.base_url, args.model, args.outdir, key, args.runs,
                     args.timeout, args.image_id)
    except Exception as exc:  # noqa: BLE001 - endpoint unreachable is an exit code
        print("endpoint unreachable: %s: %s" % (type(exc).__name__, exc),
              file=sys.stderr)
        return 1
    print("%-8s %8s %8s %6s %6s %s" % ("image", "median_s", "tok", "delta", "key?",
                                       "answer"))
    for c in out["cells"]:
        print("%-8s %8s %8s %6s %6s %s" % (
            c["image"], c["latency_median_s"],
            (c["completion_tokens"] or [None])[0] or "-",
            c["image_token_delta"] if c["image_token_delta"] is not None else "-",
            "yes" if c["key_match"] else "NO",
            (c["answers"][0] or "").replace("\n", " ")[:70]))
    bad = [c["image"] for c in out["cells"] if c["errors"]]
    if bad:
        print("errors: " + ", ".join(bad), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
