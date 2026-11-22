"""Guards tools/quality-battery.py -- held-out quality battery of one serve.

Run: uv run python -B -m unittest tests.test_quality_battery -v

Stdlib-only; the stub serve is a real loopback HTTP server, so the request
path (probe and every chat call) is exercised without a live endpoint.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL_PATH = REPO_ROOT / "tools" / "quality-battery.py"
KEY = "s3cret-battery-key"

SEEN: list[tuple[str, str, str | None]] = []
BODIES: list[dict] = []


def load_tool(path: Path = TOOL_PATH):
    spec = importlib.util.spec_from_file_location("quality_battery", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["quality_battery"] = module
    spec.loader.exec_module(module)
    return module


TOOL = load_tool()


class _Stub(BaseHTTPRequestHandler):
    """A serve that wants `Authorization: Bearer <KEY>`; `reject_all` answers 401
    and `open_access` answers 200 to anything (keyless-lane probe)."""

    reject_all: bool = False
    open_access: bool = False
    reasoning_only: bool = False

    def log_message(self, format: str, *args: object) -> None:
        pass

    def _record(self) -> str | None:
        auth = self.headers.get("Authorization")
        SEEN.append((self.command, self.path, auth))
        return auth

    def _reply(self, code: int, payload: dict | None = None) -> None:
        data = json.dumps(payload or {}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _allowed(self) -> bool:
        auth = self._record()
        if self.reject_all:
            return False
        if self.open_access:
            return True
        return auth == f"Bearer {KEY}"

    def do_GET(self) -> None:
        if self.path.rstrip("/") != "/v1/models":
            self.send_error(404)
            return
        if not self._allowed():
            self._reply(401, {"error": "unauthorized"})
            return
        self._reply(200, {"data": [{"id": "stub-model"}]})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        BODIES.append(json.loads(self.rfile.read(length) or b"{}"))
        if not self._allowed():
            self._reply(401, {"error": "unauthorized"})
            return
        if self.reasoning_only:
            self._reply(200, {"choices": [{"index": 0, "finish_reason": "length",
                                           "message": {"role": "assistant", "content": "",
                                                       "reasoning_content": "thinking " * 400}}],
                              "usage": {"prompt_tokens": 1, "completion_tokens": 4096}})
            return
        self._reply(200, {"choices": [{"index": 0, "finish_reason": "stop",
                                       "message": {"role": "assistant", "content": "42"}}],
                          "usage": {"prompt_tokens": 1, "completion_tokens": 1}})


class StubServe:
    def __init__(self, reject_all: bool = False, open_access: bool = False,
                 reasoning_only: bool = False):
        _Stub.reject_all = reject_all
        _Stub.open_access = open_access
        _Stub.reasoning_only = reasoning_only
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Stub)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> str:
        SEEN.clear()
        BODIES.clear()
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def __exit__(self, *_exc: object) -> bool:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        return False


def run_cli(*argv: str, env: dict[str, str] | None = None,
            tool: Path = TOOL_PATH) -> subprocess.CompletedProcess[str]:
    base_env = {k: v for k, v in os.environ.items() if k != "QB_TEST_KEY"}
    base_env.update(env or {})
    return subprocess.run([sys.executable, "-B", str(tool), *argv],
                          capture_output=True, text=True, env=base_env, timeout=120)


class Credential(unittest.TestCase):
    def test_header_on_probe_and_every_chat_call(self):
        with StubServe() as url:
            proc = run_cli(url, "--tier", "easy", "--max-tokens", "8",
                           "--api-key-env", "QB_TEST_KEY",
                           env={"QB_TEST_KEY": KEY})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        methods = [path for _verb, path, _auth in SEEN]
        self.assertEqual(methods.count("/v1/models"), 1, SEEN)
        chats = [entry for entry in SEEN if entry[1] == "/v1/chat/completions"]
        self.assertEqual(len(chats), 19, "one request per easy task")
        self.assertTrue(all(auth == f"Bearer {KEY}" for _v, _p, auth in SEEN), SEEN)
        self.assertNotIn(KEY, proc.stdout + proc.stderr, "key must never be echoed")

    def test_no_flag_sends_no_auth_header(self):
        with StubServe(open_access=True) as url:
            proc = run_cli(url, "--tier", "easy", "--max-tokens", "8", "--repeat", "1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual([a for _v, _p, a in SEEN], [None] * len(SEEN), SEEN)

    def test_401_on_chat_is_loud_not_a_score(self):
        with StubServe(reject_all=True) as url:
            proc = run_cli(url, "--model", "stub-model", "--tier", "easy",
                           "--api-key-env", "QB_TEST_KEY", env={"QB_TEST_KEY": KEY})
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("the serve rejected the credential", proc.stderr)
        self.assertNotIn("=", proc.stdout.splitlines()[-1] if proc.stdout else "",
                         "no score line on a rejected credential")
        self.assertNotIn("PASS", proc.stdout)
        self.assertNotIn("FAIL", proc.stdout)

    def test_401_on_models_probe_is_loud(self):
        with StubServe(reject_all=True) as url:
            proc = run_cli(url, "--tier", "easy",
                           "--api-key-env", "QB_TEST_KEY", env={"QB_TEST_KEY": KEY})
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("the serve rejected the credential", proc.stderr)
        self.assertEqual([p for _v, p, _a in SEEN], ["/v1/models"])

    def test_missing_env_var_fails_naming_it(self):
        proc = run_cli("http://127.0.0.1:1", "--api-key-env", "QB_UNSET_KEY")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("QB_UNSET_KEY", proc.stderr)
        self.assertIn("unset", proc.stderr)

    def test_empty_env_var_fails_naming_it(self):
        proc = run_cli("http://127.0.0.1:1", "--api-key-env", "QB_TEST_KEY",
                       env={"QB_TEST_KEY": ""})
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("QB_TEST_KEY", proc.stderr)
        self.assertIn("empty", proc.stderr)

    def test_run_tier_reraises_instead_of_scoring(self):
        with StubServe(reject_all=True) as url:
            with self.assertRaises(TOOL.CredentialRejected) as ctx:
                TOOL.run_tier("easy", TOOL.EASY, url, "stub-model", 1, 8, None, KEY)
        self.assertIn("rejected the credential", str(ctx.exception))


class Score(unittest.TestCase):
    """`kind=num` must read a sentence-final period as punctuation, not a number."""

    def test_bare_integer_passes(self):
        self.assertTrue(TOOL.score("num", "74", "74"))

    def test_trailing_period_passes(self):
        # The Ripple 2026-11-20 hard-arith-1 reply: "... 37 x 2 = 74."
        self.assertTrue(TOOL.score("num", "74", "7 * 6 = 42, 42 - 5 = 37, 37 x 2 = 74."))

    def test_decimal_control_still_passes(self):
        self.assertTrue(TOOL.score("num", "7.5", "The answer is 7.5."))

    def test_decimal_does_not_match_its_integer_prefix(self):
        self.assertFalse(TOOL.score("num", "74", "74.5"))


class Reasoning(unittest.TestCase):
    """A budget spent in the reasoning channel is its own outcome, not a dead serve."""

    TASK = [("trick-1", "reason", "Which weighs more?", "any", ["same"])]

    def test_reasoning_only_reports_as_reasoning_not_empty(self):
        with StubServe(reasoning_only=True) as url:
            result = TOOL.run_tier("hard", self.TASK, url, "stub-model", 1, 8, None, KEY)
        self.assertEqual(result["correct"], 0)
        self.assertEqual(result["reasoning"], ["trick-1"])
        self.assertEqual(result["outcomes"]["trick-1"],
                         [{"outcome": "reasoning", "finish_reason": "length"}])

    def test_case_pins_its_own_budget_and_thinking(self):
        pinned = ("trick-1", "reason", "Which weighs more?", "any", ["42"],
                  {"max_tokens": 8192, "thinking": "off"})
        with StubServe() as url:
            TOOL.run_tier("hard", [self.TASK[0], pinned], url, "stub-model", 1, 8,
                          "on", KEY)
        plain, own = BODIES
        self.assertEqual(plain["max_tokens"], 8)
        self.assertEqual(plain["chat_template_kwargs"], {"enable_thinking": True})
        self.assertEqual(own["max_tokens"], 8192)
        self.assertEqual(own["chat_template_kwargs"], {"enable_thinking": False})


if __name__ == "__main__":
    unittest.main()
