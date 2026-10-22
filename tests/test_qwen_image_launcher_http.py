# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Guard the HTTP surface of the qwen-image launcher: 400 for a bad request, 500
only for a fault of the server itself.

The 2026-10-22 defect here was not one branch but a class: a blanket
`except Exception -> 500` made `prompt is required`, a non-numeric `width` and
every `schedule_kwargs()` refusal indistinguishable from a broken serve by status
alone, `int(headers["Content-Length"])` sat outside that try (a malformed header
dropped the connection with no response at all), and a JSON body of `[]`/`3`
reached `run_generate` and died on `req.get` with AttributeError.

Each case below is a real request against a real `ThreadingHTTPServer` bound to
127.0.0.1:0, with the pipeline and torch stubbed (no GPU, no diffusers, no
network) — the same `_FakePipeline` / `_stub_torch` the schedule guard uses.
"""
from __future__ import annotations

import http.client
import json
import socket
import sys
import tempfile
import threading
import types
import unittest
from http.server import ThreadingHTTPServer
from typing import ClassVar
from unittest import mock

from tests.test_qwen_image_sigmas_resample import BASE, _stub_torch, server


class _EmptyPipeline:
    """A pipeline that runs but returns nothing: the 500 path."""

    def __call__(self, **call):
        callback = call.get("callback_on_step_end")
        if callback is not None:
            callback(self, 0, None, call)
        return types.SimpleNamespace(images=[])


def _fake_diffusers(load_image):
    module = types.ModuleType("diffusers")
    utils = types.ModuleType("diffusers.utils")
    setattr(utils, "load_image", load_image)
    setattr(module, "utils", utils)
    return {"diffusers": module, "diffusers.utils": utils}


class LauncherHttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.samples = tempfile.TemporaryDirectory()
        server.STATE["model_id"] = "Qwen/Qwen-Image-2.1-Turbo"
        server.STATE["load_s"] = 12.5
        server.STATE["sample_dir"] = cls.samples.name
        server.STATE["shipped_sigmas"] = list(BASE)
        # torch is imported inside run_generate, so the patch must stay live for
        # the whole test class, not just around the request.
        cls.torch_patch = mock.patch.dict(sys.modules, {"torch": _stub_torch()})
        cls.torch_patch.start()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.torch_patch.stop()
        cls.samples.cleanup()

    def setUp(self):
        # A working pipeline for every case unless the case swaps it.
        from tests.test_qwen_image_sigmas_resample import _FakePipeline

        server.STATE["pipe"] = _FakePipeline(len(BASE))

    # -- request helpers ---------------------------------------------------
    def post(self, body, headers=None):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            conn.request("POST", "/generate", body=raw,
                         headers=headers or {"Content-Type": "application/json"})
            response = conn.getresponse()
            payload = response.read()
            return response.status, payload
        finally:
            conn.close()

    def raw_request(self, request: bytes) -> bytes:
        """Bypass http.client so a malformed Content-Length can be sent."""
        with socket.create_connection(("127.0.0.1", self.port), timeout=30) as sock:
            sock.sendall(request)
            data = b""
            sock.settimeout(10)
            while b"\r\n\r\n" not in data:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
            return data

    def get(self, path: str):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            conn.request("GET", path)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    # -- the table ---------------------------------------------------------
    CASES: ClassVar[list[tuple[str, object, int]]] = [
        ("happy text-to-image", {"prompt": "poster"}, 200),
        ("missing prompt", {"width": 1024}, 400),
        ("prompt not a string", {"prompt": 7}, 400),
        ("non-numeric width", {"prompt": "x", "width": "wide"}, 400),
        ("non-integer seed", {"prompt": "x", "seed": "seed"}, 400),
        ("empty sigmas", {"prompt": "x", "sigmas": []}, 400),
        ("one-point sigmas", {"prompt": "x", "sigmas": [1.0]}, 400),
        ("sigmas not a list", {"prompt": "x", "sigmas": 3}, 400),
        ("sigmas not numeric", {"prompt": "x", "sigmas": [1.0, "b"]}, 400),
        ("non-integer num_inference_steps", {"prompt": "x", "num_inference_steps": "four"}, 400),
        ("body is an array", [], 400),
        ("body is a number", 3, 400),
        ("body is a string", "x", 400),
    ]

    def test_status_table(self):
        for name, body, expected in self.CASES:
            with self.subTest(name):
                status, payload = self.post(body)
                self.assertEqual(status, expected, (name, payload[:200]))
                if expected == 400:
                    self.assertIn("error", json.loads(payload))
                else:
                    result = json.loads(payload)
                    self.assertIsNone(result["sigmas_used"])
                    self.assertEqual(result["steps"], len(BASE))

    def test_malformed_json_is_400(self):
        status, payload = self.post(b"{not json")
        self.assertEqual(status, 400)
        self.assertIn("not valid JSON", json.loads(payload)["error"])

    def test_malformed_content_length_is_400_not_a_dropped_connection(self):
        response = self.raw_request(
            b"POST /generate HTTP/1.1\r\nHost: t\r\nContent-Length: abc\r\n"
            b"Content-Type: application/json\r\n\r\n")
        self.assertTrue(response, "no response at all: the header read still sits outside the try")
        self.assertIn(b" 400 ", response.split(b"\r\n", 1)[0])

    def test_pipeline_returning_no_images_is_500_without_a_traceback(self):
        server.STATE["pipe"] = _EmptyPipeline()
        status, payload = self.post({"prompt": "x"})
        self.assertEqual(status, 500)
        body = payload.decode()
        self.assertIn("no images", body)
        self.assertNotIn("Traceback", body)
        self.assertNotIn("File \"", body)

    def test_unreadable_image_path_is_400(self):
        def load_image(path):
            raise OSError(2, "No such file or directory")

        with mock.patch.dict(sys.modules, _fake_diffusers(load_image)):
            status, payload = self.post({"prompt": "x", "image_path": "/nope.png"})
        self.assertEqual(status, 400)
        self.assertIn("image_path", json.loads(payload)["error"])

    def test_reference_image_path_still_runs(self):
        def load_image(path):
            return types.SimpleNamespace(convert=lambda mode: "RGBA-IMAGE")

        with mock.patch.dict(sys.modules, _fake_diffusers(load_image)):
            status, payload = self.post({"prompt": "x", "image_path": "/ref.png"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(payload)["steps"], len(BASE))

    def test_health_counts_attempts_and_failures(self):
        before = self.get("/health")[1]
        self.post({"prompt": "x"})          # 200
        self.post({"width": 1024})          # 400
        after = self.get("/health")[1]
        self.assertEqual(after["attempts"] - before["attempts"], 2)
        self.assertEqual(after["failed"] - before["failed"], 1)
        self.assertEqual(after["requests"] - before["requests"], 1)
        self.assertGreaterEqual(after["failed"], 1)


if __name__ == "__main__":
    unittest.main()
