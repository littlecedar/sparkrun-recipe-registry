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
from unittest import mock

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
    """A minimal OpenAI-compatible serve: /v1/models, one chat reply, one completion, or a 400."""

    fail: bool = True
    text: object = "42"
    stream_pieces: tuple[str, ...] = ("4", " 2")

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
        body = self._body()
        if self.fail:
            data = b"rejected"
            self.send_response(400)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path.startswith("/v1/completions"):
            self._completion(body)
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

    def _stream(self, usage: dict[str, int]) -> None:
        """SSE completion chunks; with `text` None the stream carries usage and no text."""
        gap = chr(10) * 2
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for piece in self.stream_pieces:
            text = piece if self.text is not None else ""
            chunk = {"choices": [{"index": 0, "text": text}]}
            self.wfile.write(("data: " + json.dumps(chunk) + gap).encode())
        self.wfile.write(("data: " + json.dumps({"choices": [], "usage": usage}) + gap).encode())
        self.wfile.write(("data: " + json.dumps("done") + gap).encode())

    def _completion(self, body: dict[str, object]) -> None:
        """A /v1/completions reply; `text` is None on a serve that returns nothing."""
        usage = {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 9}
        if body.get("stream"):
            self._stream(usage)
            return
        data = json.dumps({
            "id": "stub", "object": "text_completion", "model": "stub-model",
            "choices": [{"index": 0, "text": self.text, "finish_reason": "length"}],
            "usage": usage,
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class StubServe:
    server: ThreadingHTTPServer
    thread: threading.Thread

    def __init__(self, fail: bool, text: object = "42"):
        _Stub.fail = fail
        _Stub.text = text
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


class CompletionsCell(unittest.TestCase):
    """The cell a base serve needs: /v1/completions, both modes, nothing-but-text is failure."""

    def _run(self, base: str, mode: str, prompts: list[object] | None = None,
             expect_rc: int = 0) -> tuple[int, Path, dict[str, object]]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        arm = Path(tmp.name) / "arm"
        argv = ["--cell", "completions", "--base-url", base, "--outdir", str(arm),
                "--mode", mode]
        if prompts is not None:
            path = Path(tmp.name) / "prompts.json"
            path.write_text(json.dumps(prompts))
            argv += ["--prompts", str(path)]
        rc = TOOL.main(argv)
        self.assertEqual(rc, expect_rc, (arm / "client" / "client.json").read_text())
        manifest = json.loads((arm / "client" / "client.json").read_text())
        self.assertEqual([s["step"] for s in manifest["steps"]], ["completions"])
        self.assertEqual(manifest["steps"][0]["rc"], expect_rc)
        self.assertIn("--cell", manifest["steps"][0]["argv"])
        return rc, arm, json.loads((arm / "client" / "completions.json").read_text())

    def test_non_streaming_parses_text_and_usage(self):
        with StubServe(fail=False, text="5\n") as base:
            _rc, _arm, report = self._run(base, "plain", ["Complete the sequence: 1 2 3 4"])
        plain = report["prompts"][0]["plain"]
        self.assertEqual(plain["text"], "5")
        self.assertEqual((plain["prompt_tokens"], plain["completion_tokens"]), (7, 2))
        # The rate and the wall are the runner's clock, not the stub's contract: assert the
        # shape, never that a rounded timing-derived rate is above zero.
        self.assertIsInstance(plain["wall_s"], float)
        self.assertIsInstance(plain["tok_per_s"], float)
        self.assertGreaterEqual(plain["tok_per_s"], 0)
        self.assertIsNone(plain["ttft_s"])
        self.assertEqual(report["verdict"], "PASS", report["problems"])

    def test_a_slow_request_keeps_its_rate_above_zero(self):
        # Pins the regression: two tokens over a nine-minute wall used to round to 0.0 and
        # read as "no throughput". The clock is faked so the assertion owns the timing.
        ticks = iter([0.0] + [900.0] * 8)
        with StubServe(fail=False, text="5") as base, \
                mock.patch.object(TOOL.time, "perf_counter", lambda: next(ticks)):
            _rc, _arm, report = self._run(base, "plain", ["Complete the sequence: 1 2 3 4"])
        plain = report["prompts"][0]["plain"]
        self.assertEqual(plain["completion_tokens"], 2)
        self.assertGreater(plain["tok_per_s"], 0, plain)
        self.assertLess(plain["tok_per_s"], 0.01, plain)

    def test_a_sub_millisecond_answer_still_reports_a_rate(self):
        # A load-starved runner answers the stub in 0.0002 s; rounding the window to three
        # decimals first collapsed it to 0.0 and left the rate None with two tokens counted.
        ticks = iter([0.0] + [0.0002] * 8)
        with StubServe(fail=False, text="5") as base, \
                mock.patch.object(TOOL.time, "perf_counter", lambda: next(ticks)):
            _rc, _arm, report = self._run(base, "plain", ["Complete the sequence: 1 2 3 4"])
        plain = report["prompts"][0]["plain"]
        self.assertEqual(plain["completion_tokens"], 2)
        self.assertIsInstance(plain["tok_per_s"], float, plain)
        self.assertGreater(plain["tok_per_s"], 0, plain)

    def test_negative_control_a_rounded_window_drops_the_rate(self):
        # The CI failure in arithmetic form: round(x, 3) turns that 0.0002 s wall into 0.0,
        # and a zero divisor used to leave tok_per_s None although tokens were counted.
        self.assertIsNone(TOOL.completion_rate(2, round(0.0002, 3)))
        self.assertEqual(TOOL.completion_rate(2, 0.0002), 10000.0)
        self.assertIsNone(TOOL.completion_rate(0, 0.5), "no tokens must mean no rate")

    def test_streaming_accumulates_text_and_yields_a_first_token_time(self):
        with StubServe(fail=False, text="42") as base:
            _rc, _arm, report = self._run(base, "stream", ["Complete the sequence: 1 2 3 4"])
        stream = report["prompts"][0]["stream"]
        self.assertEqual(stream["text"], "4 2", "chunks must accumulate, not overwrite")
        self.assertIsNotNone(stream["ttft_s"])
        self.assertLessEqual(stream["ttft_s"], stream["wall_s"])
        self.assertEqual((stream["prompt_tokens"], stream["completion_tokens"]), (7, 2))

    def test_empty_completion_is_a_failure_with_its_own_exit_status(self):
        with StubServe(fail=False, text=None) as base:
            _rc, _arm, report = self._run(base, "both", ["Complete the sequence: 1 2 3 4"],
                                          expect_rc=5)
        self.assertEqual(report["rc"], 5)
        self.assertEqual(report["summary"]["empty"], 2)
        self.assertEqual(report["summary"]["answered"], 0)
        self.assertEqual(report["verdict"], "FAIL")

    def test_a_rejecting_serve_surfaces_the_status_and_body(self):
        import contextlib
        import io
        with StubServe(fail=True) as base:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                _rc, _arm, report = self._run(base, "plain",
                                              ["Complete the sequence: 1 2 3 4"], expect_rc=4)
        self.assertIn("HTTP 400", err.getvalue())
        self.assertIn("rejected", err.getvalue())
        self.assertEqual(report["summary"]["http_errors"], 1)
        self.assertIn("HTTP 400", " ".join(report["problems"]))

    def test_negative_control_usage_without_text_is_still_empty(self):
        # The hazard this cell exists for: a stream that counts tokens and says nothing.
        with StubServe(fail=False, text=None) as base:
            _rc, _arm, report = self._run(base, "stream", ["Complete the sequence: 1 2 3 4"],
                                          expect_rc=5)
        stream = report["prompts"][0]["stream"]
        self.assertEqual(stream["completion_tokens"], 2, "usage still counts the tokens")
        self.assertEqual(stream["text"], "")
        self.assertTrue(any("empty completion" in p for p in report["problems"]))


if __name__ == "__main__":
    unittest.main()
