#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Image-input probe for a vision arm served by llama-server.

What it measures: what an image *costs* — its token count in the context
(difference between the same prompt sent with and without the picture), the
prefill and decode rates the engine itself reports for each shape, and the
context headroom that leaves at the served ``n_ctx``. Plus acceptance: the
endpoint took the image part and returned a non-blank reply.

What it cannot measure: whether the answer is *right*. No cell in this registry
scores image understanding (``benchmarking/standard-suite.yaml`` is
tool-eval-bench's text tool-calling set), so acceptance here means "the request
was served", never "the model saw the picture". A non-blank reply is compatible
with a model that ignored the image entirely; only a quality cell could tell
those apart.

Footprint is measured from the boot's own log rather than guessed: pass
``--serve-log`` and the tool reads llama.cpp's ``model size``, ``KV self size``
and ``model buffer size`` lines. Without it, the footprint cell reports
``not_provided`` instead of an estimate.

Usage
-----
::

  python3 tools/vl-arm-probe.py --selftest        # offline stub, ~1 s
  python3 tools/vl-arm-probe.py \\
      --base-url http://<node>:8023 \\
      --prompt "Describe this image in one sentence." \\
      --serve-log /tmp/vl-serve.log --json vl.json

The fixture is a synthetic solid-colour PNG (``tools/synthetic_png.py``, the same
generator the embed/rerank benches use) unless ``--png`` names a real one. Flat
pixels give the vision tower the same patch grid a photograph would; they are a
fair proxy for encoder and prefill cost and no proxy at all for answering about
photographic content.

Exit codes: ``0`` both cells served and the image was tokenised, ``1`` a cell
failed or the image cost nothing, ``2`` bad flags.
"""

from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

TIMEOUT = 600.0
FIXTURE_SIZE = (512, 512)
FIXTURE_RGB = (32, 96, 160)
_LOG_PATTERNS = {
    "model_size_mib": re.compile(r"print_info: model size\s*=\s*([\d.]+) MiB"),
    "kv_self_mib": re.compile(r"print_info: KV self size\s*=\s*([\d.]+) MiB"),
    "model_buffer_mib": re.compile(r"model buffer size\s*=\s*([\d.]+) MiB"),
    "load_seconds": re.compile(r"load time\s*=\s*([\d.]+) ms"),
}


def _synthetic_png_module():
    """Load tools/synthetic_png.py by sibling path, the way pooling-bench does."""
    path = Path(__file__).resolve().parent / "synthetic_png.py"
    if not path.exists():
        raise SystemExit(f"image synthesis needs {path}, missing")
    spec = importlib.util.spec_from_file_location("synthetic_png", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"{path}: not loadable as a module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_b64(png: Path | None) -> tuple[str, str]:
    """-> (base64 payload without prefix, where it came from)."""
    if png is not None:
        raw = png.read_bytes()
        if raw[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"{png}: not a PNG file")
        return base64.b64encode(raw).decode("ascii"), str(png)
    module = _synthetic_png_module()
    return module.solid_png_b64(*FIXTURE_SIZE, FIXTURE_RGB), (
        f"synthetic {FIXTURE_SIZE[0]}x{FIXTURE_SIZE[1]} rgb{FIXTURE_RGB}")


def _get_json(url: str, timeout: float = 60.0) -> tuple[int, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as e:
        return 0, f"{type(e).__name__}: {e}"


def _post(base: str, body: dict[str, Any], timeout: float = TIMEOUT) -> tuple[int, Any, float]:
    req = urllib.request.Request(
        base.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.load(r), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), time.time() - t0
    except (urllib.error.URLError, OSError) as e:
        return 0, f"{type(e).__name__}: {e}", time.time() - t0


def served_id(base: str) -> str | None:
    status, payload = _get_json(base.rstrip("/") + "/v1/models")
    if status != 200 or not isinstance(payload, dict):
        return None
    try:
        return payload["data"][0]["id"]
    except (KeyError, IndexError, TypeError):
        return None


def props(base: str) -> dict[str, Any]:
    """The serve's own description of itself: context, slots, modalities."""
    status, payload = _get_json(base.rstrip("/") + "/props")
    if status != 200 or not isinstance(payload, dict):
        return {}
    out = {"modalities": payload.get("modalities"), "total_slots": payload.get("total_slots"),
           "build_info": payload.get("build_info")}
    gen = payload.get("default_generation_settings") or {}
    n_ctx = gen.get("n_ctx") or payload.get("n_ctx")
    if isinstance(n_ctx, int):
        out["n_ctx"] = n_ctx
    return out


def footprint(serve_log: Path | None) -> dict[str, Any]:
    """Resident sizes, from llama.cpp's own load lines — never estimated."""
    if serve_log is None:
        return {"status": "not_provided"}
    text = serve_log.read_text(errors="replace")
    out: dict[str, Any] = {"status": "parsed", "source": str(serve_log)}
    for name, pattern in _LOG_PATTERNS.items():
        found = pattern.findall(text)
        if found:
            value = float(found[-1])
            out[name] = round(value / 1000.0, 3) if name == "load_seconds" else value
    if len(out) == 2:
        out["status"] = "no_memory_lines"
    return out


def _body(model: str, prompt: str, image_b64: str | None, max_tokens: int) -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    if image_b64 is not None:
        content.append({"type": "image_url",
                        "image_url": {"url": "data:image/png;base64," + image_b64}})
    content.append({"type": "text", "text": prompt})
    return {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0,
        "max_tokens": max_tokens,
        # an empty prompt cache: a re-run must measure prefill, not a hit
        "cache_prompt": False,
    }


def _cell(status: int, payload: Any, wall: float) -> dict[str, Any]:
    cell: dict[str, Any] = {"status": status, "wall_s": round(wall, 3)}
    if status != 200 or not isinstance(payload, dict):
        cell["problem"] = str(payload)
        return cell
    usage = payload.get("usage") or {}
    timings = payload.get("timings") or {}
    choices = payload.get("choices") or []
    reply = ""
    if choices and isinstance(choices[0], dict):
        reply = ((choices[0].get("message") or {}).get("content") or "").strip()
    cell["reply"] = reply
    cell["reply_chars"] = len(reply)
    if isinstance(usage.get("prompt_tokens"), int):
        cell["prompt_tokens"] = usage["prompt_tokens"]
    if isinstance(usage.get("completion_tokens"), int):
        cell["completion_tokens"] = usage["completion_tokens"]
    for src, dst in (("prompt_per_second", "pp_t_s"), ("predicted_per_second", "tg_t_s"),
                     ("prompt_n", "prompt_n"), ("predicted_n", "predicted_n")):
        if isinstance(timings.get(src), (int, float)):
            cell[dst] = round(float(timings[src]), 2)
    if not reply:
        cell["problem"] = f"empty reply ({sorted(payload)})"
    return cell


def probe(base: str, model: str, prompt: str, png: Path | None, max_tokens: int,
          serve_log: Path | None) -> dict[str, Any]:
    image_b64, fixture = fixture_b64(png)
    out: dict[str, Any] = {
        "base_url": base, "model": model, "prompt": prompt, "fixture": fixture,
        "props": props(base), "cells": {}, "footprint": footprint(serve_log),
    }
    for name, with_image in (("image", True), ("text", False)):
        status, payload, wall = _post(base, _body(model, prompt, image_b64 if with_image else None,
                                                 max_tokens))
        out["cells"][name] = _cell(status, payload, wall)

    img, txt = out["cells"]["image"], out["cells"]["text"]
    if "prompt_tokens" in img and "prompt_tokens" in txt:
        image_tokens = img["prompt_tokens"] - txt["prompt_tokens"]
        out["image_tokens"] = image_tokens
        n_ctx = out["props"].get("n_ctx")
        if isinstance(n_ctx, int) and n_ctx > 0:
            out["image_context_share"] = round(image_tokens / n_ctx, 4)
            out["images_that_fit"] = max(n_ctx // image_tokens, 0) if image_tokens > 0 else None
        if "pp_t_s" in img and "pp_t_s" in txt and img["pp_t_s"] > 0:
            out["prefill_cost"] = round(txt["pp_t_s"] / img["pp_t_s"], 3)
        if "tg_t_s" in img and "tg_t_s" in txt:
            out["decode_delta"] = round(img["tg_t_s"] - txt["tg_t_s"], 3)

    failures: list[str] = []
    for name in ("image", "text"):
        cell = out["cells"][name]
        if cell.get("status") != 200 or cell.get("problem"):
            failures.append(f"{name}: {cell.get('problem') or 'not 200'}")
    if "image_tokens" not in out:
        failures.append("prompt token counts were not reported, so the image cost is unmeasured")
    elif out["image_tokens"] <= 0:
        failures.append(f"image cost {out['image_tokens']} tokens — the image was not tokenised")
    out["failures"] = failures
    out["verdict"] = "ok" if not failures else "failed"
    return out


class _Stub(BaseHTTPRequestHandler):
    """Serves a chat endpoint whose image path costs tokens, a text path that does not."""

    mode = "good"  # good | blank | reject-image

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
        path = self.path.rstrip("/")
        if path == "/v1/models":
            return self._send({"data": [{"id": "stub/vl"}]})
        if path == "/props":
            return self._send({"modalities": {"vision": True, "audio": False},
                               "total_slots": 4, "build_info": "stub",
                               "default_generation_settings": {"n_ctx": 16384}})
        return self._send({"error": "not found"}, 404)

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
        content = (body.get("messages") or [{}])[0].get("content")
        with_image = isinstance(content, list) and any(
            isinstance(p, dict) and p.get("type") == "image_url" for p in content)
        if with_image and self.mode == "reject-image":
            return self._send({"error": {"message": "this model does not support images"}}, 400)
        prompt_tokens = 1500 if with_image else 40
        reply = "" if self.mode == "blank" else "a blue rectangle"
        return self._send({
            "choices": [{"message": {"content": reply}}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": 8},
            "timings": {"prompt_n": prompt_tokens, "predicted_n": 8,
                        "prompt_per_second": 900.0 if with_image else 2500.0,
                        "predicted_per_second": 60.0 if with_image else 62.0},
        })


def selftest() -> int:
    failures: list[str] = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Stub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    log = Path(__file__).with_name(".selftest-vl.log")
    log.write_text(
        "print_info: model size = 3467.61 MiB\n"
        "print_info: KV self size  =  512.00 MiB\n"
        "load_tensors: model buffer size = 3390.25 MiB\n"
        "load time = 4123.45 ms\n")
    try:
        if served_id(base) != "stub/vl":
            failures.append("served id resolution")
        p = props(base)
        if p.get("n_ctx") != 16384 or (p.get("modalities") or {}).get("vision") is not True:
            failures.append(f"props not read: {p}")

        _Stub.mode = "good"
        good = probe(base, "stub/vl", "describe this", None, 32, log)
        if good["verdict"] != "ok":
            failures.append(f"good run not ok: {good['failures']}")
        if good["image_tokens"] != 1460:
            failures.append(f"image token delta wrong: {good['image_tokens']}")
        if good["prefill_cost"] != round(2500.0 / 900.0, 3):
            failures.append(f"prefill cost ratio wrong: {good['prefill_cost']}")
        if good["images_that_fit"] != 11:
            failures.append(f"context headroom arithmetic wrong: {good['images_that_fit']}")
        if good["footprint"].get("model_size_mib") != 3467.61:
            failures.append(f"footprint not parsed: {good['footprint']}")
        if good["footprint"].get("kv_self_mib") != 512.0:
            failures.append("kv footprint not parsed")
        if good["footprint"].get("load_seconds") != 4.123:
            failures.append("load seconds not converted from ms")

        _Stub.mode = "blank"
        blank = probe(base, "stub/vl", "describe this", None, 32, None)
        if blank["verdict"] != "failed" or not any("empty reply" in f for f in blank["failures"]):
            failures.append(f"blank reply accepted: {blank['verdict']}")
        if blank["footprint"]["status"] != "not_provided":
            failures.append("absent serve log invented a footprint")

        _Stub.mode = "reject-image"
        dead = probe(base, "stub/vl", "describe this", None, 32, None)
        if dead["cells"]["image"]["status"] != 400:
            failures.append("image rejection not surfaced")
        if "does not support images" not in dead["cells"]["image"].get("problem", ""):
            failures.append("image rejection lost the endpoint's own text")

        _Stub.mode = "good"
        down = probe("http://127.0.0.1:1", "stub/vl", "describe this", None, 32, None)
        if down["verdict"] != "failed":
            failures.append("dead endpoint not failed")

        notpng = Path(__file__).with_name(".selftest-notpng.png")
        notpng.write_bytes(b"not a png")
        try:
            fixture_b64(notpng)
            failures.append("non-PNG fixture accepted")
        except ValueError:
            pass
        finally:
            notpng.unlink(missing_ok=True)
    finally:
        server.shutdown()
        log.unlink(missing_ok=True)
    for f in failures:
        print(f"FAIL {f}", file=sys.stderr)
    print("vl-arm-probe selftest:", "ok" if not failures else f"{len(failures)} failure(s)")
    return 0 if not failures else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--base-url")
    p.add_argument("--model", default="auto", help="served id; 'auto' reads /v1/models")
    p.add_argument("--prompt", default="Describe this image in one sentence.")
    p.add_argument("--png", default=None,
                   help="a real image; default is a synthetic solid-colour fixture")
    p.add_argument("--max-tokens", type=int, default=64)
    p.add_argument("--serve-log", default=None, help="the boot's serve log, for the footprint cell")
    p.add_argument("--json", help="write the full result here")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.base_url:
        p.error("required: --base-url (or --selftest)")

    model = args.model
    if model in ("", "auto", None):
        resolved = served_id(args.base_url)
        if not resolved:
            print("error: /v1/models did not answer; pass --model", file=sys.stderr)
            return 2
        model = resolved

    try:
        result = probe(args.base_url, model, args.prompt,
                       Path(args.png).expanduser() if args.png else None, args.max_tokens,
                       Path(args.serve_log).expanduser() if args.serve_log else None)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=1))
    for name, cell in result["cells"].items():
        bits = [f"status={cell.get('status')}"]
        for key in ("prompt_tokens", "pp_t_s", "tg_t_s", "reply_chars"):
            if key in cell:
                bits.append(f"{key}={cell[key]}")
        print(f"{name:5s} " + " ".join(bits)
              + (f" problem={cell['problem']}" if cell.get("problem") else ""))
        if cell.get("problem"):
            print(f"  endpoint said: {cell['problem']}", file=sys.stderr)
    if "image_tokens" in result:
        print(f"image cost: {result['image_tokens']} tokens"
              + (f" ({result['image_context_share']:.1%} of n_ctx, "
                 f"{result['images_that_fit']} fit)" if "image_context_share" in result else "")
              + (f"; prefill cost {result['prefill_cost']}x the text-only rate"
                 if "prefill_cost" in result else ""))
    print(f"footprint: {result['footprint']}")
    print(f"verdict: {result['verdict']}")
    return 0 if result["verdict"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())