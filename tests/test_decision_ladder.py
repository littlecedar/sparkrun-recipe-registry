"""Guards for tools/decision-ladder.py.

Run:
    python3 -m unittest tests.test_decision_ladder -v

Stdlib-only, like the rest of tests/ and tools/ (AGENTS.md).  The tool is a
dash-named file, so it is imported via importlib and registered in sys.modules
before exec_module (the house import idiom).

What this guards
----------------
The tool measures a *rate*, so the numbers it prints are only as good as the
bookkeeping behind them: which requests succeeded, how many decisions each one
actually returned, and how long the cell really took.  The failure that matters
is a cell that looks measured while it is not — a 500 counted as a slow request,
a short answer counted as a full case, a nominal `n / delay` printed instead of
a measured wall — because those numbers get copied into the registry's C-columns
as if they were the endpoint's.  So the tests drive real stub servers over
sockets (the tool's own `--selftest` also does, but a guard that shares its
instrument cannot catch a broken instrument) and the final class is the
negative-control ladder: each control asserts the property the tool would lose
if its accounting were faked.

Timing assertions use generous bands: they must survive a loaded machine and
still fail on the arithmetic bug they exist for (an order-of-magnitude gap, not
a scheduling jitter).
"""

from __future__ import annotations

import contextlib
import http.server
import importlib.util
import io
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL_PATH = REPO_ROOT / "tools" / "decision-ladder.py"

CELL_KEYS = (
    "concurrency",
    "requests",
    "ok_requests",
    "failed_requests",
    "decisions",
    "expected_decisions",
    "wall_s",
    "req_per_s",
    "decisions_per_s",
    "per_request_decisions_per_s",
    "ttft_ms_p50",
    "ttft_ms_p95",
    "latency_ms_p50",
    "latency_ms_p95",
    "errors",
    "ok",
)


def load_tool():
    """Import tools/decision-ladder.py (dash-named, so via importlib)."""
    spec = importlib.util.spec_from_file_location("decision_ladder", TOOL_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["decision_ladder"] = module
    spec.loader.exec_module(module)
    return module


DL = load_tool()


def _cases(count=4, questions=2):
    """A Typed Decisions-shaped slice: `count` cases x `questions` questions."""
    return [
        {
            "id": f"case{i}",
            "state": "the alarm rang twice",
            "questions": {
                f"q{j}": {"type": "choice", "instructions": "Which?", "criteria": {"a": "x", "b": "y"}}
                for j in range(questions)
            },
        }
        for i in range(count)
    ]


class _Stats:
    """What the stub saw: its behaviour knob, its delay, and the client's concurrency."""

    def __init__(self, mode: str, delay: float) -> None:
        self.mode = mode
        self.delay = delay
        self.hits = 0
        self.live = 0
        self.peak = 0


@contextlib.contextmanager
def _endpoint(mode="good", delay=0.02, admit=None):
    """A stub decision endpoint. Yields (base_url, stats).

    It records the peak number of requests the client had in flight, which is
    how a test proves the ladder really offered a concurrency level instead of
    running serially behind the scenes.
    """
    stats = _Stats(mode, delay)
    lock = threading.Lock()
    gate = threading.Semaphore(admit) if admit else None

    def answer(body, path):
        """-> (payload, status); the body of a well-behaved lane API."""
        if stats.mode == "http500":
            return b'{"error": "boom"}', 500
        if stats.mode == "malformed":
            return b'{"answers": ', 200
        if stats.mode == "empty":
            return b'{"answers": {}}', 200
        if stats.mode == "short":
            first = next(iter(body["questions"]), "q0")
            return json.dumps({"answers": {first: {"choice": "a"}}}).encode(), 200
        if path.endswith("/v1/completions"):
            if stats.mode == "nologprobs":
                return json.dumps({"choices": [{"text": ""}]}).encode(), 200
            return json.dumps({"choices": [{"logprobs": {"top_logprobs": [{"5": -0.1}]}}]}).encode(), 200
        answers = {name: {"choice": "a", "probabilities": {"a": 0.6, "b": 0.4}} for name in body["questions"]}
        return json.dumps({"answers": answers, "usage": {"input_tokens": 7}}).encode(), 200

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            body = json.loads(raw or b"{}")
            with lock:
                stats.hits += 1
                hit = stats.hits
                stats.live += 1
                stats.peak = max(stats.peak, stats.live)
            try:
                if gate:
                    gate.acquire()
                try:
                    time.sleep(stats.delay)
                finally:
                    if gate:
                        gate.release()
                if stats.mode == "flaky" and hit % 3 == 0:
                    return self._send(b'{"error": "boom"}', 500)
                if stats.mode == "truncated":
                    payload = b'{"answers": {}}'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload) + 64))
                    self.end_headers()
                    self.wfile.write(payload)
                    self.wfile.flush()
                    self.close_connection = True
                    return
                payload, status = answer(body, self.path)
                return self._send(payload, status)
            finally:
                with lock:
                    stats.live -= 1

        def _send(self, payload, status=200):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", stats
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _run(base, cases, concurrency, api="systemone", runs=1, timeout=30.0):
    requests = (
        DL.systemone_requests(cases, "stub")
        if api == "systemone"
        else DL.completions_requests(cases, "stub", _head())
    )
    return DL.cell(f"{base}/v1/{api}", requests, concurrency, api, timeout, runs)


def _head():
    return {
        "verbalizer_ids": [10, 11, 12, 13],
        "bias": [0.0, 0.0, 0.0, 0.0],
        "slots": {"ranges": {"choice": [0], "score": [2], "noul": [2]}},
    }


def _cases_file(root, cases):
    path = Path(root) / "cases.jsonl"
    path.write_text("".join(json.dumps(case) + "\n" for case in cases), encoding="utf-8")
    return path


class TestCellAccounting(unittest.TestCase):
    """What a cell reports: decisions, rates, and per-request latency."""

    def test_happy_cell_returns_every_decision(self):
        with _endpoint() as (base, _stats):
            row = _run(base, _cases(4, 2), 2)
        self.assertTrue(row["ok"], row)
        self.assertEqual(row["requests"], 4)
        self.assertEqual(row["ok_requests"], 4)
        self.assertEqual(row["failed_requests"], 0)
        self.assertEqual(row["decisions"], 8)
        self.assertEqual(row["expected_decisions"], 8)
        self.assertEqual(row["errors"], {})

    def test_rates_are_derived_from_the_measured_wall(self):
        with _endpoint() as (base, _stats):
            row = _run(base, _cases(4, 2), 2)
        self.assertAlmostEqual(row["req_per_s"], row["ok_requests"] / row["wall_s"], places=9)
        self.assertAlmostEqual(row["decisions_per_s"], row["decisions"] / row["wall_s"], places=9)

    def test_serial_cell_agrees_with_its_own_per_request_rate(self):
        # One request in flight: the aggregate decisions/s IS the request's own
        # rate (2 decisions / latency), so any other arithmetic shows up here.
        with _endpoint(delay=0.03) as (base, _stats):
            row = _run(base, _cases(3, 2), 1)
        self.assertLess(abs(row["decisions_per_s"] - row["per_request_decisions_per_s"]),
                        0.3 * row["decisions_per_s"], row)
        self.assertGreater(row["per_request_decisions_per_s"], 20.0, row)

    def test_queueing_shows_up_as_a_per_request_rate_below_the_aggregate(self):
        # The stub admits one at a time: offered concurrency buys nothing, and
        # the per-request rate (at inflated latency) must fall below the aggregate.
        with _endpoint(delay=0.03, admit=1) as (base, _stats):
            row = _run(base, _cases(4, 2), 4)
        self.assertTrue(row["ok"], row)
        self.assertLess(row["per_request_decisions_per_s"], 0.9 * row["decisions_per_s"], row)

    def test_ttft_and_latency_are_per_request_never_the_wall(self):
        delay = 0.03
        with _endpoint(delay=delay) as (base, _stats):
            row = _run(base, _cases(5, 2), 1)
        self.assertGreaterEqual(row["ttft_ms_p50"], delay * 1000 * 0.8, row)
        self.assertGreaterEqual(row["latency_ms_p50"], row["ttft_ms_p50"], row)
        self.assertGreaterEqual(row["latency_ms_p95"], row["latency_ms_p50"], row)
        self.assertLess(row["ttft_ms_p50"], row["wall_s"] * 1000.0, row)

    def test_concurrency_is_actually_offered(self):
        with _endpoint(delay=0.03) as (base, stats):
            _run(base, _cases(8, 1), 4)
        self.assertGreaterEqual(stats.peak, 3, "the ladder ran requests serially")

    def test_runs_repeat_the_slice(self):
        with _endpoint() as (base, stats):
            row = _run(base, _cases(3, 2), 3, runs=2)
        self.assertEqual(row["requests"], 6)
        self.assertEqual(row["decisions"], 12)
        self.assertEqual(row["expected_decisions"], 12)
        self.assertEqual(stats.hits, 6)

    def test_a_stub_at_its_ceiling_saturates(self):
        # Offer 2 vs 4 to a server that admits 2: the extra concurrency must not
        # become throughput.  This is the shape the lane's arms show.
        with _endpoint(delay=0.03, admit=2) as (base, _stats):
            two = _run(base, _cases(6, 1), 2)
            four = _run(base, _cases(6, 1), 4)
        self.assertTrue(two["ok"] and four["ok"], (two, four))
        self.assertLess(four["decisions_per_s"], 1.4 * two["decisions_per_s"], (two, four))
        self.assertLess(four["per_request_decisions_per_s"], two["per_request_decisions_per_s"], (two, four))


class TestFailuresAreCellsNotRates(unittest.TestCase):
    """Every failure mode marks the cell failed; nothing is averaged in."""

    def _assert_failed(self, row, expected_decisions=4):
        self.assertFalse(row["ok"], row)
        self.assertGreater(row["failed_requests"], 0, row)
        self.assertLess(row["decisions"], expected_decisions, row)
        self.assertTrue(row["errors"], row)
        self.assertEqual(DL.verdict([row]), 1, row)

    def test_http_4xx_or_5xx(self):
        with _endpoint("http500") as (base, _stats):
            row = _run(base, _cases(2, 2), 2)
        self._assert_failed(row)
        self.assertEqual(row["errors"], {"HTTP 500": 2}, row)

    def test_malformed_json(self):
        with _endpoint("malformed") as (base, _stats):
            row = _run(base, _cases(2, 2), 2)
        self._assert_failed(row)
        self.assertEqual(row["errors"], {"malformed-json": 2}, row)

    def test_truncated_body(self):
        with _endpoint("truncated") as (base, _stats):
            row = _run(base, _cases(2, 2), 2)
        self._assert_failed(row)
        self.assertEqual(row["errors"], {"truncated": 2}, row)

    def test_zero_decisions(self):
        with _endpoint("empty") as (base, _stats):
            row = _run(base, _cases(2, 2), 2)
        self._assert_failed(row)
        self.assertEqual(row["errors"], {"no-decisions": 2}, row)

    def test_short_answer_is_not_a_full_case(self):
        with _endpoint("short") as (base, _stats):
            row = _run(base, _cases(2, 2), 2)
        self._assert_failed(row)
        self.assertEqual(row["errors"], {"short-answer 1/2": 2}, row)

    def test_one_bad_request_fails_the_whole_cell(self):
        with _endpoint("flaky") as (base, _stats):
            row = _run(base, _cases(6, 2), 2)
        self.assertFalse(row["ok"], row)
        self.assertEqual(row["ok_requests"] + row["failed_requests"], row["requests"])
        self.assertLess(row["decisions"], row["expected_decisions"], row)
        self.assertEqual(DL.verdict([row]), 1)

    def test_dead_endpoint_is_an_error_count(self):
        row = DL.cell("http://127.0.0.1:1/v1/systemone", DL.systemone_requests(_cases(2, 2), "stub"),
                      2, "systemone", 5.0, 1)
        self.assertFalse(row["ok"], row)
        self.assertEqual(row["ok_requests"], 0)
        self.assertEqual(row["decisions"], 0)
        self.assertIsNone(row["per_request_decisions_per_s"])
        self.assertEqual(DL.verdict([row]), 1)

    def test_verdict_needs_a_measured_cell(self):
        self.assertEqual(DL.verdict([]), 1)


class TestCompletionsContract(unittest.TestCase):
    """JEV-9B's `/v1/completions` path: one question per request, one decision."""

    def test_body_is_the_card_shape(self):
        cases = _cases(1, 3)
        jobs = DL.completions_requests(cases, "autotrust/JEV-9B", _head())
        self.assertEqual(len(jobs), 3, "one request per question, not per case")
        for body, want in jobs:
            self.assertEqual(want, 1)
            self.assertEqual(body["model"], "autotrust/JEV-9B")
            self.assertEqual(body["max_tokens"], 1)
            self.assertEqual(body["add_special_tokens"], False)
            self.assertEqual(body["return_tokens_as_token_ids"], True)
            self.assertEqual(body["logprobs"], len(body["allowed_token_ids"]))
            self.assertIn("[decision]:", body["prompt"])

    def test_completions_cell_counts_one_decision_per_request(self):
        with _endpoint() as (base, _stats):
            row = _run(base, _cases(2, 2), 2, api="completions")
        self.assertTrue(row["ok"], row)
        self.assertEqual(row["requests"], 4)
        self.assertEqual(row["decisions"], 4)
        self.assertEqual(row["expected_decisions"], 4)

    def test_a_reply_without_logprobs_is_not_a_decision(self):
        with _endpoint("nologprobs") as (base, _stats):
            row = _run(base, _cases(2, 2), 2, api="completions")
        self.assertFalse(row["ok"], row)
        self.assertEqual(row["decisions"], 0)
        self.assertEqual(row["errors"], {"malformed-response": 4}, row)


class TestCli(unittest.TestCase):
    """Drive the whole CLI over a socket: flags, artifact, exit code."""

    def _main(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = DL.main(argv)
        return code, out.getvalue()

    def test_writes_the_artifact_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp, _endpoint() as (base, _stats):
            cases = _cases_file(tmp, _cases(3, 2))
            artifact = Path(tmp) / "ladder.json"
            code, printed = self._main([
                "--base-url", base, "--cases", str(cases), "--model", "m",
                "--concurrency", "1,3", "--runs", "1", "--warmup", "0", "--json", str(artifact),
            ])
            self.assertEqual(code, 0)
            doc = json.loads(artifact.read_text(encoding="utf-8"))
        self.assertTrue(doc["ok"])
        self.assertEqual(doc["api"], "systemone")
        self.assertEqual([cell["concurrency"] for cell in doc["cells"]], [1, 3])
        for cell in doc["cells"]:
            self.assertEqual(set(CELL_KEYS) - set(cell), set(), cell)
            self.assertEqual(cell["decisions"], 6, cell)
        for needle in ("req/s=", "decisions/s=", "per-req=", "ttft p50=", "dec="):
            self.assertIn(needle, printed)

    def test_a_failing_endpoint_exits_one_and_still_writes_the_artifact(self):
        with tempfile.TemporaryDirectory() as tmp, _endpoint("http500") as (base, _stats):
            cases = _cases_file(tmp, _cases(2, 2))
            artifact = Path(tmp) / "ladder.json"
            code, printed = self._main([
                "--base-url", base, "--cases", str(cases), "--model", "m",
                "--concurrency", "2", "--runs", "1", "--warmup", "0", "--json", str(artifact),
            ])
            doc = json.loads(artifact.read_text(encoding="utf-8"))
        self.assertEqual(code, 1)
        self.assertFalse(doc["ok"])
        self.assertFalse(doc["cells"][0]["ok"])
        self.assertIn("FAILED", printed)

    def test_completions_run(self):
        with tempfile.TemporaryDirectory() as tmp, _endpoint() as (base, _stats):
            cases = _cases_file(tmp, _cases(2, 2))
            head = Path(tmp) / "head.json"
            head.write_text(json.dumps(_head()), encoding="utf-8")
            code, _printed = self._main([
                "--base-url", base, "--cases", str(cases), "--model", "m", "--api", "completions",
                "--decision-head", str(head), "--concurrency", "2", "--runs", "2", "--warmup", "0",
            ])
        self.assertEqual(code, 0)

    def test_completions_without_a_decision_head_is_a_bad_flag(self):
        out = io.StringIO()
        with contextlib.redirect_stderr(out):
            code = DL.main([
                "--base-url", "http://127.0.0.1:1", "--cases", "/tmp/x.jsonl",
                "--model", "m", "--api", "completions",
            ])
        self.assertEqual(code, 2)
        self.assertIn("--decision-head", out.getvalue())

    def test_missing_model_is_a_bad_flag(self):
        with contextlib.redirect_stderr(io.StringIO()):
            code = DL.main(["--base-url", "http://127.0.0.1:1", "--cases", "/tmp/x.jsonl"])
        self.assertEqual(code, 2)

    def test_bad_concurrency_and_runs_are_bad_flags(self):
        for argv in (
            ["--base-url", "http://127.0.0.1:1", "--cases", "/tmp/x.jsonl", "--model", "m", "--concurrency", "0"],
            ["--base-url", "http://127.0.0.1:1", "--cases", "/tmp/x.jsonl", "--model", "m", "--runs", "0"],
        ):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(DL.main(argv), 2, argv)


class NegativeControls(unittest.TestCase):
    """Each control fails if the accounting it guards is replaced by a proxy.

    These are the tests that must go red if someone "simplifies" the tool into
    printing `len(cases) / delay` or treating any 200 as a measured request.
    """

    def test_same_fixture_gives_opposite_verdicts(self):
        # If `ok` were hard-coded True, the good half of this pair would still
        # pass — so the pair is the evidence, not either half.
        cases = _cases(2, 2)
        with _endpoint() as (base, _stats):
            good = _run(base, cases, 2)
        with _endpoint("http500") as (base, _stats):
            bad = _run(base, cases, 2)
        self.assertTrue(good["ok"])
        self.assertFalse(bad["ok"])

    def test_decisions_come_from_the_wire_not_from_the_case_count(self):
        with _endpoint("short") as (base, _stats):
            row = _run(base, _cases(4, 2), 2)
        self.assertEqual(row["requests"], 4)
        self.assertEqual(row["decisions"], 0)  # a short answer is a failure...
        self.assertEqual(row["expected_decisions"], 8)  # ...not a partial decision
        self.assertEqual(row["errors"], {"short-answer 1/2": 4}, row)

    def test_a_faster_server_reports_a_faster_rate(self):
        # A nominal rate (n / an assumed delay) cannot move with the server.
        with _endpoint(delay=0.02) as (base, _stats):
            fast = _run(base, _cases(4, 1), 1)
        with _endpoint(delay=0.06) as (base, _stats):
            slow = _run(base, _cases(4, 1), 1)
        self.assertLess(slow["decisions_per_s"], 0.65 * fast["decisions_per_s"], (fast, slow))

    def test_ttft_is_not_the_cell_wall(self):
        with _endpoint(delay=0.02) as (base, _stats):
            row = _run(base, _cases(6, 1), 1)
        # Serial: the wall is 6 requests, one TTFT is one request.
        self.assertLess(row["ttft_ms_p50"], row["wall_s"] * 1000.0 / 3.0, row)

    def test_per_request_rate_is_not_the_aggregate_under_load(self):
        # At c=4 with a one-at-a-time server, aggregate/4 is queueing, not speed.
        with _endpoint(delay=0.03, admit=1) as (base, _stats):
            row = _run(base, _cases(6, 1), 4)
        self.assertGreater(row["wall_s"], 6 * 0.03 * 0.8, row)
        self.assertLess(row["per_request_decisions_per_s"], 0.5 * row["decisions_per_s"], row)

    def test_an_error_is_counted_even_when_other_requests_succeed(self):
        with _endpoint("flaky") as (base, _stats):
            row = _run(base, _cases(6, 1), 3)
        self.assertGreater(row["ok_requests"], 0)
        self.assertGreater(row["failed_requests"], 0)
        self.assertFalse(row["ok"])
        self.assertEqual(sum(row["errors"].values()), row["failed_requests"])


if __name__ == "__main__":
    unittest.main()
