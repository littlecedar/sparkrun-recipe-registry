"""Guards tools/h2h-client.py -- the campaign's house/BFCL extra client.

Run: uv run python -B -m unittest tests.test_h2h_client -v
Stdlib-only, like the rest of tools/ and tests/; the stub serve is a real
loopback HTTP server so no fixture can leave the client's own contracts untested.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL_PATH = REPO_ROOT / "tools" / "h2h-client.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("h2h_client", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["h2h_client"] = module
    spec.loader.exec_module(module)
    return module


TOOL = load_tool()


class _Stub(BaseHTTPRequestHandler):
    """A minimal OpenAI-compatible serve: /v1/models plus one chat reply or a 400."""

    fail: bool = True

    def log_message(self, format: str, *args: object) -> None:
        pass

    def _body(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        if self.path.rstrip("/") != "/v1/models":
            self.send_error(404)
            return
        data = json.dumps({"data": [{"id": "stub-model"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        self._body()
        if self.fail:
            body = b"rejected"
            self.send_response(400)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        data = json.dumps({
            "id": "stub", "object": "chat.completion", "model": "stub-model",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": "42"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 1,
                      "total_tokens": 11},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class StubServe:
    server: ThreadingHTTPServer
    thread: threading.Thread

    def __init__(self, fail: bool):
        _Stub.fail = fail
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Stub)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def __exit__(self, *_exc: object) -> bool:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        return False


class Plan(unittest.TestCase):
    def test_lc_cells_carry_the_image_id(self):
        for cell in ("lc-1m", "lc-128k-c5c10"):
            steps = TOOL.plan(cell, "http://stub:8000", "m", "/r", "py",
                              house_max_tokens=4096, bfcl_data_dir="/d",
                              bfcl_max_tokens=4096, image_id="sha256:deadbeef")
            argv = steps[0][1]
            self.assertIn("--image-id", argv)
            self.assertIn("sha256:deadbeef", argv)

    def test_house_cells_do_not_invent_an_image_flag(self):
        steps = TOOL.plan("house4096", "http://stub:8000", "m", "/r", "py",
                          house_max_tokens=4096, bfcl_data_dir="/d",
                          bfcl_max_tokens=4096, image_id="sha256:deadbeef")
        self.assertNotIn("--image-id", steps[0][1])


class TransportErrorContract(unittest.TestCase):
    """quality-battery always exits 0; the dispatcher must not read that as success."""

    def test_every_house_reply_a_transport_error_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp, StubServe(fail=True) as base:
            outdir = Path(tmp) / "arm"
            rc = TOOL.main(["--cell", "house4096", "--base-url", base,
                            "--outdir", str(outdir)])
            manifest = json.loads((outdir / "client" / "client.json").read_text())
            house = json.loads((outdir / "client" / "house.json").read_text())
        self.assertEqual(rc, 2, manifest)
        self.assertEqual(manifest["rc"], 2)
        self.assertEqual([s["rc"] for s in manifest["steps"]], [2])
        replies = [reply for tier in house["tiers"].values()
                   for replies in tier["replies"].values() for reply in replies]
        self.assertTrue(replies)
        self.assertTrue(all(str(reply).startswith("<ERROR") for reply in replies), replies)

    def test_negative_control_a_healthy_serve_is_not_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp, StubServe(fail=False) as base:
            rc = TOOL.main(["--cell", "house4096", "--base-url", base,
                            "--outdir", str(Path(tmp) / "arm")])
        self.assertEqual(rc, 0)


class ReceiptLayout(unittest.TestCase):
    def test_receipts_land_in_client_and_never_clobber_the_standard_branch(self):
        with tempfile.TemporaryDirectory() as tmp, StubServe(fail=False) as base:
            arm = Path(tmp) / "arm"
            arm.mkdir()
            sentinel_house = b"suite: the standard branch's own house.yaml sidecar\n"
            sentinel_ladder = b'{"benchmarks": [{"cell": "c1"}]}\n'
            (arm / "house.json").write_bytes(sentinel_house)
            (arm / "ladder.json").write_bytes(sentinel_ladder)
            rc = TOOL.main(["--cell", "house4096", "--base-url", base,
                            "--outdir", str(arm)])
            self.assertFalse((arm / "house.json").read_bytes() != sentinel_house,
                             "the client overwrote the standard branch's house.json")
            self.assertEqual((arm / "ladder.json").read_bytes(), sentinel_ladder)
            self.assertTrue((arm / "client" / "house.json").is_file())
            manifest = json.loads((arm / "client" / "client.json").read_text())
        self.assertEqual(rc, 0, manifest)
        self.assertEqual(manifest["cell"], "house4096")
        self.assertEqual(manifest["model"], "stub-model")
        self.assertTrue(manifest["image_id"] == "" or manifest["image_id"].startswith("sha256:"))
        self.assertEqual(manifest["receipts_dir"], str(arm))


class ImageRecording(unittest.TestCase):
    def test_arm_image_id_wins_over_the_file_fallback(self):
        import os
        with tempfile.TemporaryDirectory() as tmp, StubServe(fail=False) as base:
            arm = Path(tmp) / "arm"
            arm.mkdir()
            (arm / "image.txt").write_text("sha256:fromfile\n")
            os.environ["ARM_IMAGE_ID"] = "sha256:fromenv"
            try:
                rc = TOOL.main(["--cell", "house4096", "--base-url", base,
                                "--outdir", str(arm)])
            finally:
                os.environ.pop("ARM_IMAGE_ID", None)
            manifest = json.loads((arm / "client" / "client.json").read_text())
        self.assertEqual(rc, 0)
        self.assertEqual(manifest["image_id"], "sha256:fromenv")


if __name__ == "__main__":
    unittest.main()
