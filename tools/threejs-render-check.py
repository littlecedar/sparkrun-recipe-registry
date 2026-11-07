#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Render gate for single-file Three.js scenes: does the HTML actually draw?

The 3D lane's cell is not a chat score. The arm emits one self-contained HTML
file and the question is whether a browser loads it and puts geometry on the
screen, so this tool drives headless Chromium over the DevTools protocol —
stdlib only, no npm, no Puppeteer — and reports three things per document:

* **renders clean** — no page exception (``SyntaxError``/``ReferenceError`` are
  the dominant failure mode for generated code, usually a duplicated ``const``)
  and no ``console.error``.
* **non-empty geometry** — WebGL draw calls with a non-zero vertex count. The
  hook wraps ``drawElements``/``drawArrays`` before the page runs, so it does
  not care what the model named its renderer or scene.
* **delivery, recorded not scored** — a fenced reply is unwrapped (`stripped_fence`) and prose around
  the document is measured (`prose_chars`), because code models explain themselves; a reply with no
  `<html>`/`<!doctype>` at all is left as-is and fails the geometry cell.
* **import constraint** — every module specifier is the pinned core URL
  ``https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.module.min.js``.
  Addons, ``examples/js`` paths, other CDNs and bare specifiers fail: the card's
  system prompt is load-bearing and this is the cell that checks it was obeyed.

What it cannot measure: whether the scene matches the prompt. A cube where a
cathedral was asked for passes. Visual fidelity needs the reference renders and
some image comparison, which this registry does not have; the dataset
``ccore/ThreeJS-3D-Scenes`` (MIT) ships 213 validation prompts with complete
reference HTML, and this gate scores those replies on the three checks above —
never on looks.

Usage
-----
::

  python3 tools/threejs-render-check.py --selftest          # control pair, needs Chrome + network
  python3 tools/threejs-render-check.py --html scene.html --json scene.json
  python3 tools/threejs-render-check.py --jsonl threejs-validation.jsonl \\
      --html-field response --json threejs-gate.json

The dataset ships as parquet; convert it once with stdlib-only tooling absent
(pandas is the shortest path) before scoring:

    uv run --no-project --with pandas --with pyarrow python -c \\
      "import pandas as pd; pd.read_parquet('validation-00000.parquet') \\
         .to_json('threejs-validation.jsonl', orient='records', lines=True)"

Exit codes: ``0`` every document passed, ``1`` at least one failed, ``2`` bad
flags, no Chrome, or the fixture page could not be rendered at all.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

CORE_URL = "https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.module.min.js"
SPEC_RE = re.compile(r"""(?:\bimport\s+[^'"]*?from\s*|\bimport\s*\(\s*|\bimport\s*)(['"])([^'"]+)\1""")
BENIGN = re.compile(r"GL Driver Message|deprecat|Automatic fallback to software WebGL",
                    re.IGNORECASE)

HOOK = r"""
(() => {
  const st = window.__probe = {drawCalls: 0, vertices: 0, frames: 0, hookErrors: []};
  const wrap = (proto, name, count) => {
    if (!proto || !proto[name]) return;
    const orig = proto[name];
    proto[name] = function (...a) {
      try { st.drawCalls++; st.vertices += (count(a) || 0); } catch (e) { st.hookErrors.push(String(e)); }
      return orig.apply(this, a);
    };
  };
  for (const C of [window.WebGLRenderingContext, window.WebGL2RenderingContext]) {
    if (!C) continue;
    wrap(C.prototype, 'drawElements', a => a[1] || 0);
    wrap(C.prototype, 'drawArrays', a => a[2] || 0);
  }
  const raf = window.requestAnimationFrame;
  if (raf) window.requestAnimationFrame = function (cb) {
    return raf.call(window, t => { st.frames++; return cb(t); });
  };
})();
"""


class CDPError(RuntimeError):
    pass


class DevTools:
    """The smallest CDP client that can drive one page: handshake, frames, events."""

    def __init__(self, ws_url: str, timeout: float = 30.0):
        parsed = urlparse(ws_url)
        if parsed.scheme != "ws":
            raise CDPError(f"not a ws url: {ws_url}")
        self._sock = socket.create_connection((parsed.hostname or "127.0.0.1",
                                               parsed.port or 80), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        path = parsed.path or "/"
        self._sock.sendall(
            f"GET {path} HTTP/1.1\r\nHost: {parsed.hostname}:{parsed.port}\r\n"
            f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n".encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise CDPError("devtools closed during handshake")
            head += chunk
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise CDPError(f"devtools upgrade refused: {head.split(chr(13).encode())[0]!r}")
        self._buf = b""
        self._next_id = 0
        self._events: list[dict[str, Any]] = []

    def _send_frame(self, payload: bytes, opcode: int = 1) -> None:
        header = bytearray([0x80 | opcode])
        mask = os.urandom(4)
        n = len(payload)
        if n < 126:
            header.append(0x80 | n)
        elif n < (1 << 16):
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        header += mask
        self._sock.sendall(bytes(header) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def _recv_exact(self, n: int, deadline: float) -> bytes:
        while len(self._buf) < n:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError("devtools read timed out")
            self._sock.settimeout(max(0.05, remaining))
            chunk = self._sock.recv(65536)
            if not chunk:
                raise CDPError("devtools closed the socket")
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def _read_message(self, deadline: float) -> dict[str, Any]:
        while True:
            b1, b2 = self._recv_exact(2, deadline)
            opcode = b1 & 0x0F
            length = b2 & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._recv_exact(2, deadline))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._recv_exact(8, deadline))[0]
            payload = self._recv_exact(length, deadline) if length else b""
            if opcode == 0x9:
                self._send_frame(payload, opcode=0xA)
                continue
            if opcode == 0x8:
                raise CDPError("devtools closed the session")
            if opcode in (0x1, 0x2):
                return json.loads(payload.decode())

    def call(self, method: str, params: dict[str, Any] | None = None,
             session: str | None = None, timeout: float = 60.0) -> dict[str, Any]:
        self._next_id += 1
        msg: dict[str, Any] = {"id": self._next_id, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        self._send_frame(json.dumps(msg).encode())
        deadline = time.time() + timeout
        while True:
            reply = self._read_message(deadline)
            if reply.get("id") == self._next_id:
                if "error" in reply:
                    raise CDPError(f"{method}: {reply['error']}")
                return reply.get("result", {})
            self._events.append(reply)

    def pump(self, seconds: float) -> None:
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                self._events.append(self._read_message(deadline))
            except (TimeoutError, CDPError):
                return

    def take_events(self) -> list[dict[str, Any]]:
        out, self._events = self._events, []
        return out

    def saw_event(self, method: str) -> bool:
        return any(e.get("method") == method for e in self._events)

    def close(self) -> None:
        try:
            self._send_frame(b"", opcode=0x8)
        except OSError:
            pass
        self._sock.close()


def find_chrome(explicit: str | None) -> str | None:
    if explicit:
        return explicit if Path(explicit).exists() else None
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    roots = [Path.home() / ".cache/ms-playwright", Path.home() / ".cache/puppeteer"]
    for root in roots:
        if not root.exists():
            continue
        for candidate in sorted(root.glob("chromium-*/chrome-linux*/chrome"), reverse=True):
            return str(candidate)
        for candidate in sorted(root.glob("chromium_headless_shell-*/chrome-linux*/headless_shell"),
                                reverse=True):
            return str(candidate)
    return None


class Browser:
    """One headless Chromium, reused across documents."""

    def __init__(self, chrome: str, workdir: Path):
        self.workdir = workdir
        self._profile = workdir / "profile"
        self._profile.mkdir(parents=True, exist_ok=True)
        self._log = workdir / "chrome.log"
        self._proc = subprocess.Popen(
            [chrome, "--headless=new", "--no-sandbox", "--disable-gpu",
             "--enable-unsafe-swiftshader", "--use-gl=swiftshader",
             "--no-first-run", "--no-default-browser-check", "--disable-extensions",
             "--mute-audio", "--remote-debugging-port=0",
             f"--user-data-dir={self._profile}", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=open(self._log, "w"), start_new_session=True)
        self._ws_url = self._await_ws(20.0)
        self.cdp = DevTools(self._ws_url)

    def _await_ws(self, timeout: float) -> str:
        deadline = time.time() + timeout
        while time.time() < deadline:
            text = self._log.read_text(errors="replace") if self._log.exists() else ""
            match = re.search(r"DevTools listening on (ws://\S+)", text)
            if match:
                return match.group(1)
            if self._proc.poll() is not None:
                raise CDPError(f"chrome exited early: {text[-400:]}")
            time.sleep(0.1)
        raise CDPError("chrome never announced a devtools socket")

    def render(self, html: str, settle: float, timeout: float) -> dict[str, Any]:
        target = self.cdp.call("Target.createTarget", {"url": "about:blank"})["targetId"]
        session = self.cdp.call("Target.attachToTarget",
                                {"targetId": target, "flatten": True})["sessionId"]
        try:
            for method in ("Page.enable", "Runtime.enable", "Log.enable"):
                self.cdp.call(method, session=session)
            self.cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": HOOK}, session=session)
            page = self.workdir / "doc.html"
            page.write_text(html)
            self.cdp.call("Page.navigate", {"url": page.as_uri()}, session=session)
            deadline = time.time() + timeout
            while time.time() < deadline and not self.cdp.saw_event("Page.loadEventFired"):
                self.cdp.pump(0.2)
            loaded = self.cdp.saw_event("Page.loadEventFired")
            settle_until = time.time() + settle
            while time.time() < settle_until:
                self.cdp.pump(0.2)
            probe = self.cdp.call(
                "Runtime.evaluate",
                {"expression": "JSON.stringify(window.__probe || null)", "returnByValue": True},
                session=session)
            events = self.cdp.take_events()
            stats = None
            raw = (probe.get("result") or {}).get("value")
            if isinstance(raw, str) and raw not in ("null", ""):
                try:
                    stats = json.loads(raw)
                except json.JSONDecodeError:
                    stats = None
            return {"loaded": loaded, "stats": stats, "events": events}
        finally:
            try:
                self.cdp.call("Target.closeTarget", {"targetId": target})
            except CDPError:
                pass

    def close(self) -> None:
        try:
            self.cdp.close()
        finally:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()


FENCE = re.compile(r"```[a-zA-Z]*\s*\n(.*?)```", re.S)
DOC_START = re.compile(r"<(!doctype\s+html|html)[^>]*>", re.I)


def extract_document(text: str) -> tuple[str, dict[str, Any]]:
    """Unwrap the delivery habits a code model actually has, and record them.

    A fenced reply (`````html <!doctype html>… `````) is still a scene, and prose around it is
    still a scene with a broken delivery, so both are unwrapped here and the wrapper is
    reported as ``stripped_fence`` / ``prose_chars`` — a receipt must never imply the model
    emitted a clean file when it explained itself instead. A reply with no ``<html>`` or
    ``<!doctype>`` at all is returned unchanged: the page then renders nothing and fails the
    geometry cell, which is the correct verdict for prose.
    """
    notes: dict[str, Any] = {"stripped_fence": False, "prose_chars": 0}
    body = text
    fence = FENCE.search(body)
    if fence and "<" in fence.group(1):
        body = fence.group(1)
        notes["stripped_fence"] = True
    start = DOC_START.search(body)
    if start:
        notes["prose_chars"] = len(body[:start.start()].strip())
        body = body[start.start():]
    return body, notes


def import_violations(html: str) -> tuple[list[str], list[str]]:
    """-> (specifiers, violations). Only the pinned core module may be imported."""
    specifiers = [m.group(2) for m in SPEC_RE.finditer(html)]
    bad = []
    for spec in specifiers:
        if spec == CORE_URL:
            continue
        if "/addons/" in spec or "examples/js" in spec:
            bad.append(f"{spec} (addons are forbidden)")
        elif spec.startswith(("http://", "https://")):
            bad.append(f"{spec} (not the pinned cdnjs core url)")
        elif spec.startswith(("./", "../")):
            bad.append(f"{spec} (relative module: not a single-file scene)")
        else:
            bad.append(f"{spec} (bare specifier: no import map may be assumed)")
    return specifiers, bad


def failures_from_events(events: list[dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    for event in events:
        method = event.get("method")
        params = event.get("params") or {}
        if method == "Runtime.exceptionThrown":
            details = params.get("exceptionDetails") or {}
            text = (details.get("exception") or {}).get("description") or details.get("text") or "exception"
            problems.append(f"{_first_line(text)}")
        elif method == "Runtime.consoleAPICalled" and params.get("type") in ("error", "assert"):
            text = " ".join(str(a.get("value", a.get("description", ""))) for a in
                            params.get("args") or [])
            if text and not BENIGN.search(text):
                problems.append(f"console.error: {_first_line(text)}")
        elif method == "Log.entryAdded":
            entry = params.get("entry") or {}
            if entry.get("level") == "error":
                text = f"{entry.get('text', '')} {entry.get('url', '')}".strip()
                if text and not BENIGN.search(text):
                    problems.append(f"log error: {_first_line(text)}")
    return problems


def _first_line(text: str, limit: int = 200) -> str:
    return text.strip().splitlines()[0][:limit] if text.strip() else ""


def check_document(browser: Browser, html: str, settle: float, timeout: float) -> dict[str, Any]:
    clean_html, delivery = extract_document(html)
    specifiers, bad_imports = import_violations(clean_html)
    rendered = browser.render(clean_html, settle, timeout)
    stats = rendered["stats"] or {}
    errors = failures_from_events(rendered["events"])
    draw_calls = int(stats.get("drawCalls") or 0)
    vertices = int(stats.get("vertices") or 0)
    result: dict[str, Any] = {
        "loaded": rendered["loaded"],
        "draw_calls": draw_calls,
        "vertices": vertices,
        "frames": int(stats.get("frames") or 0),
        "specifiers": specifiers,
        "renders_clean": not errors,
        "non_empty_geometry": draw_calls > 0 and vertices > 0,
        "import_constraint": not bad_imports,
        "errors": errors,
        "import_violations": bad_imports,
        **delivery,
    }
    result["verdict"] = "pass" if (result["renders_clean"] and result["non_empty_geometry"]
                                  and result["import_constraint"] and result["loaded"]) else "fail"
    return result


FIXTURES = {
    "good": f"""<!doctype html><html><body><canvas id="c" width="200" height="200"></canvas>
<script type="module">
import * as THREE from "{CORE_URL}";
const r = new THREE.WebGLRenderer({{canvas: document.getElementById("c")}});
const s = new THREE.Scene();
const cam = new THREE.PerspectiveCamera(60, 1, 0.1, 100); cam.position.z = 3;
s.add(new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial({{color: 0xff8800}})));
r.render(s, cam);
</script></body></html>""",
    "duplicate_const": f"""<!doctype html><html><body><canvas id="c"></canvas>
<script type="module">
import * as THREE from "{CORE_URL}";
const scene = new THREE.Scene();
const scene = new THREE.Scene();
</script></body></html>""",
    "no_geometry": f"""<!doctype html><html><body><canvas id="c" width="100" height="100"></canvas>
<script type="module">
import * as THREE from "{CORE_URL}";
const r = new THREE.WebGLRenderer({{canvas: document.getElementById("c")}});
const s = new THREE.Scene();
r.render(s, new THREE.PerspectiveCamera(60, 1, 0.1, 100));
</script></body></html>""",
    "addons": f"""<!doctype html><html><body><canvas id="c"></canvas>
<script type="module">
import * as THREE from "{CORE_URL}";
import {{ OrbitControls }} from
  "https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/examples/jsm/controls/OrbitControls.js";
</script></body></html>""",
}


def selftest(chrome: str | None) -> int:
    binary = find_chrome(chrome)
    if not binary:
        print("selftest needs Chrome (set CHROME or install one); none found", file=sys.stderr)
        return 2
    FIXTURES["fenced"] = "Here is the scene:\n```html\n" + FIXTURES["good"] + "\n```\n"
    FIXTURES["prose_only"] = ("Save this as index.html and open it in a browser.\n"
                              "The scene uses a cube, a camera and a renderer.\n")
    expectations = {"good": "pass", "duplicate_const": "fail", "no_geometry": "fail",
                    "addons": "fail", "fenced": "pass", "prose_only": "fail"}
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="threejs-gate-", ignore_cleanup_errors=True) as tmp:
        browser = Browser(binary, Path(tmp))
        try:
            for name, html in FIXTURES.items():
                result = check_document(browser, html, settle=1.5, timeout=30.0)
                if result["verdict"] != expectations[name]:
                    failures.append(f"{name}: expected {expectations[name]}, got "
                                    f"{result['verdict']} ({result['errors']}, draws="
                                    f"{result['draw_calls']}, imports={result['import_violations']})")
                if name == "good" and not result["non_empty_geometry"]:
                    failures.append("good fixture drew no geometry — the hook or WebGL is broken")
                if name == "duplicate_const" and not result["errors"]:
                    failures.append("duplicate const produced no exception")
                if name == "no_geometry" and result["non_empty_geometry"]:
                    failures.append("empty scene counted as geometry")
                if name == "addons" and result["import_constraint"]:
                    failures.append("addon import not flagged")
                if name == "fenced" and not result.get("stripped_fence"):
                    failures.append("fenced reply was not unwrapped (or not recorded)")
                if name == "fenced" and not result["non_empty_geometry"]:
                    failures.append("fenced scene drew no geometry")
                if name == "prose_only" and result["non_empty_geometry"]:
                    failures.append("a prose reply was scored as geometry")
        finally:
            browser.close()
    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)
    print("threejs-render-check selftest:", "ok" if not failures else f"{len(failures)} failure(s)")
    return 0 if not failures else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--html", help="one HTML document ('-' reads stdin)")
    p.add_argument("--jsonl", help="batch: JSONL records carrying the model's HTML")
    p.add_argument("--html-field", default="response",
                   help="JSONL field holding the HTML (default: response)")
    p.add_argument("--id-field", default=None, help="JSONL field naming the record")
    p.add_argument("--limit", type=int, default=0, help="first N records only (0 = all)")
    p.add_argument("--json", help="write the full result JSON here")
    p.add_argument("--chrome", default=os.environ.get("CHROME"), help="Chrome binary (default: search)")
    p.add_argument("--settle", type=float, default=2.0,
                   help="seconds to let the scene animate before reading the counters")
    p.add_argument("--timeout", type=float, default=45.0)
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args(argv)

    if args.selftest:
        return selftest(args.chrome)
    if not args.html and not args.jsonl:
        p.error("required: --html or --jsonl (or --selftest)")

    binary = find_chrome(args.chrome)
    if not binary:
        print("error: no Chrome found; set CHROME=<binary>", file=sys.stderr)
        return 2

    docs: list[tuple[str, str]] = []
    if args.html:
        html = sys.stdin.read() if args.html == "-" else Path(args.html).expanduser().read_text()
        docs.append((args.html, html))
    if args.jsonl:
        for line in Path(args.jsonl).expanduser().read_text().splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            html = record.get(args.html_field)
            if not isinstance(html, str) or not html.strip():
                continue
            name = str(record.get(args.id_field)) if args.id_field else str(len(docs))
            docs.append((name, html))
        if args.limit:
            docs = docs[:args.limit]
    if not docs:
        print("error: no documents to check", file=sys.stderr)
        return 2

    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="threejs-gate-", ignore_cleanup_errors=True) as tmp:
        browser = Browser(binary, Path(tmp))
        try:
            for name, html in docs:
                result = check_document(browser, html, args.settle, args.timeout)
                result["id"] = name
                results.append(result)
                print(f"{name:>28s} {result['verdict']:4s} clean={result['renders_clean']} "
                      f"draws={result['draw_calls']} vertices={result['vertices']} "
                      f"imports={result['import_constraint']}")
        finally:
            browser.close()

    passed = sum(1 for r in results if r["verdict"] == "pass")
    summary = {
        "documents": len(results),
        "passed": passed,
        "renders_clean": sum(1 for r in results if r["renders_clean"]),
        "non_empty_geometry": sum(1 for r in results if r["non_empty_geometry"]),
        "import_constraint": sum(1 for r in results if r["import_constraint"]),
        "core_url": CORE_URL,
        "does_not_measure": "visual fidelity to the prompt — only clean render, geometry presence "
                            "and the import rule; a cube passes a cathedral prompt",
        "results": results,
    }
    if args.json:
        Path(args.json).write_text(json.dumps(summary, indent=1))
    print(f"{passed}/{len(results)} passed "
          f"(clean {summary['renders_clean']}, geometry {summary['non_empty_geometry']}, "
          f"imports {summary['import_constraint']})")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())