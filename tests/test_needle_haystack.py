"""Guards for tools/needle-haystack.py.

Run:
    python3 -m unittest tests.test_needle_haystack -v

Stdlib-only, like the rest of tests/ and tools/ (AGENTS.md: "tools/ and tests/
are stdlib-only, on purpose").  The tool is a dash-named file, so it is imported
via importlib and registered in sys.modules before exec_module (a @dataclass in
a module that was never registered dies with a confusing NoneType error).

What this guards
----------------
The tool is a *measuring instrument*, and its failure modes are the ones the
repo's memory files keep recording: an empty window reported as success, a
scoring bug that makes every depth look fine, a "deterministic" prompt that is
not deterministic, and a needle that is not actually planted at the depth it
claims.  Each of those has a negative control here, because a guard that has
only ever passed proves nothing (self-check-your-own-tools.md).

The tool carries its own end-to-end control (--selftest: correct/wrong/truncating
mocks); test_selftest_passes asserts that control still runs and still refuses to
call a wrong server correct.  The rest of this file guards the pieces the selftest
does not isolate.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import threading
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL_PATH = REPO_ROOT / "tools" / "needle-haystack.py"


def load_tool():
    """Import tools/needle-haystack.py (dash-named, so via importlib)."""
    spec = importlib.util.spec_from_file_location("needle_haystack", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["needle_haystack"] = module  # before exec: @dataclass / __module__
    spec.loader.exec_module(module)
    return module


NH = load_tool()


class TestContextLengthParsing(unittest.TestCase):
    def test_accepts_suffixes_and_separators(self):
        for value, want in [
            (1000000, 1000000),
            ("1000000", 1000000),
            ("1m", 1000000),
            ("1M", 1000000),
            ("512k", 512000),
            ("1_000_000", 1000000),
            ("1,000,000", 1000000),
            ("65.5k", 65500),
        ]:
            self.assertEqual(NH.parse_context_length(value), want, value)

    def test_rejects_garbage(self):
        for bad in ["", "abc", "1x", "m", "-5", "0"]:
            with self.assertRaises(ValueError, msg=bad):
                NH.parse_context_length(bad)


class TestDepthParsing(unittest.TestCase):
    def test_default_is_every_tenth(self):
        depths = NH.parse_depths(",".join(str(d) for d in NH.DEFAULT_DEPTHS))
        self.assertEqual(depths, [10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
        self.assertEqual(len(depths), 10, "the objective specifies every 10%")

    def test_rejects_out_of_range_and_empty(self):
        for bad in ["0", "101", "-10", "", "  ,  "]:
            with self.assertRaises(ValueError, msg=bad):
                NH.parse_depths(bad)


class TestHaystackAndPrompt(unittest.TestCase):
    def test_prompt_is_deterministic_for_the_same_args(self):
        a, qa, na = NH.build_prompt(1000, 50, 1, 1234)
        b, qb, nb = NH.build_prompt(1000, 50, 1, 1234)
        self.assertEqual(a, b)
        self.assertEqual(na, nb)
        self.assertEqual(hashlib.sha256(a.encode()).hexdigest(),
                         hashlib.sha256(b.encode()).hexdigest())

    def test_different_depth_is_a_different_document(self):
        """A shared prefix across depths lets a radix cache serve the deep
        request from the shallow one and hide a real retrieval failure."""
        p10, _, _ = NH.build_prompt(1000, 10, 1, 1234)
        p90, _, _ = NH.build_prompt(1000, 90, 1, 1234)
        n = min(len(p10), len(p90))
        common = sum(1 for x, y in zip(p10[:n], p90[:n]) if x == y) / n
        self.assertLess(common, 0.5,
                        "the two depths share almost all their prefix; a radix "
                        "cache would make the deeper depth vacuous")

    def test_needle_and_question_are_both_present(self):
        prompt, questions, needles = NH.build_prompt(2000, 50, 1, 7)
        self.assertEqual(len(needles), 1)
        fact, question, key = needles[0]
        self.assertIn(fact, prompt)
        self.assertIn(question, prompt)
        self.assertIn(key, prompt)
        self.assertEqual(questions, [question])

    def test_needle_is_planted_near_the_requested_depth(self):
        """The depth number must describe where the needle actually is."""
        for depth in (10, 50, 90):
            prompt, _q, needles = NH.build_prompt(8000, depth, 1, 99)
            fact = needles[0][0]
            pos = prompt.index(fact) / len(prompt)
            self.assertLess(abs(pos - depth / 100), 0.06,
                            f"depth {depth}%: needle landed at {pos:.1%}")

    def test_needle_count_is_honoured(self):
        _p, questions, needles = NH.build_prompt(2000, 50, 3, 7)
        self.assertEqual(len(needles), 3)
        self.assertEqual(len(questions), 3)
        keys = {k for _f, _q, k in needles}
        self.assertEqual(len(keys), 3, "seeded needles must be distinct")

    def test_haystack_is_prose_not_one_repeated_token(self):
        """A repeated filler token is easier for a speculative decoder and hits
        one Engram row; it would flatter the measurement (history.md).

        The filler vocabulary is deliberately small (~64 words), so a low unique
        ratio is expected; what must not happen is one token dominating the
        document (the degenerate "fluff fluff fluff..." haystack this replaces).
        """
        import collections
        import random
        text = NH.build_haystack(20000, random.Random(1))
        words = text.split()
        self.assertGreater(len(set(words)), 40, "filler vocabulary collapsed")
        top = collections.Counter(words).most_common(1)[0][1]
        self.assertLess(top / len(words), 0.15,
                        "one word dominates the haystack; that is degenerate filler")


class TestScoring(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(NH.score("The access code is 7391-KESTREL.", "7391-KESTREL"))

    def test_punctuation_and_case_tolerated(self):
        for reply in ["7391 kestrel", "`7391-KESTREL`", "  \"7391KESTREL\"",
                      "The vault access code for record 10-0 is 7391-KESTREL."]:
            self.assertTrue(NH.score(reply, "7391-KESTREL"), reply)

    def test_wrong_answer_fails(self):
        self.assertFalse(NH.score("0000-WRONG", "7391-KESTREL"))
        self.assertFalse(NH.score("", "7391-KESTREL"))
        self.assertFalse(NH.score("I could not find it.", "7391-KESTREL"))

    def test_a_partial_code_is_not_a_hit(self):
        """Guards against a scorer that matches on a substring of the number."""
        self.assertFalse(NH.score("391-KESTREL", "7391-KESTREL"))


class TestLengthErrorDetection(unittest.TestCase):
    """The too-long retry must fire on real engine wording and not on noise."""

    def test_recognises_sglang_and_vllm_wording(self):
        for detail in [
            # VERIFIED live against SGLang on 10.0.4.30: the exact 400 body.
            "{\"object\":\"error\",\"message\":\"The input (1066900 tokens) is "
            "longer than the model's context length (1048576 tokens).\"}",
            "The input (1095000 tokens) is longer than the maximum model length (1048576)",
            "This model's maximum context length is 1048576 tokens",
            "prompt is too long",
            "input length 1200000 exceeds max_model_len",
        ]:
            self.assertTrue(NH.length_error(detail), detail)

    def test_does_not_fire_on_unrelated_errors(self):
        for detail in ["internal server error", "connection reset", "rate limited"]:
            self.assertFalse(NH.length_error(detail), detail)
        self.assertFalse(NH.length_error(""))

    def test_parses_input_and_window_token_counts(self):
        detail = ("{\"object\":\"error\",\"message\":\"The input (1066900 tokens) "
                  "is longer than the model's context length (1048576 tokens).\"}")
        self.assertEqual(NH.parse_length_error(detail), (1066900, 1048576))
        # A body with no counts must not invent them.
        self.assertEqual(NH.parse_length_error("prompt too long"), (None, None))


class TestFetchMaxModelLen(unittest.TestCase):
    """The tool must read the served window instead of blindly filling it."""

    def _server(self, data):
        from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_a):
                pass

            def do_GET(self):
                b = json.dumps(data).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

        s = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=s.serve_forever, daemon=True).start()
        self.addCleanup(s.server_close)
        self.addCleanup(s.shutdown)
        return f"http://127.0.0.1:{s.server_address[1]}"

    def test_reads_the_named_models_window(self):
        ep = self._server({"data": [{"id": "other", "max_model_len": 4096},
                                    {"id": "target", "max_model_len": 1048576}]})
        self.assertEqual(NH.fetch_max_model_len(ep, "target", None, 10), 1048576)

    def test_none_when_server_reports_nothing(self):
        ep = self._server({"data": [{"id": "m"}]})
        self.assertIsNone(NH.fetch_max_model_len(ep, "m", None, 10))


class TestClassify(unittest.TestCase):
    def _res(self, *statuses):
        return {"depths": [{"status": s, "hits": 1, "of": 1} for s in statuses]}

    def test_pass(self):
        self.assertEqual(NH.classify(self._res("PASS", "PASS")), ("PASS", 0))

    def test_fail_is_exit_3(self):
        self.assertEqual(NH.classify(self._res("PASS", "FAIL")), ("FAIL", 3))

    def test_truncated_is_exit_3(self):
        self.assertEqual(NH.classify(self._res("PASS", "TRUNCATED")), ("TRUNCATED", 3))

    def test_all_error_is_exit_1(self):
        self.assertEqual(NH.classify(self._res("ERROR", "ERROR")), ("ERROR", 1))

    def test_partial_error_is_exit_1(self):
        self.assertEqual(NH.classify(self._res("PASS", "ERROR")), ("PARTIAL-ERROR", 1))

    def test_empty_result_is_a_failure_not_a_vacuous_pass(self):
        self.assertEqual(NH.classify({"depths": []}), ("EMPTY", 1))
        self.assertEqual(NH.classify({}), ("EMPTY", 1))


class NegativeControls(unittest.TestCase):
    """Each guard above must be shown capable of failing.  In-memory only."""

    def test_control_empty_depths_cannot_pass(self):
        """The empty-window bug: [] must never map to exit 0."""
        verdict, code = NH.classify({"depths": []})
        with self.assertRaises(AssertionError):
            self.assertEqual(code, 0)

    def test_control_wrong_answer_would_fail_score(self):
        with self.assertRaises(AssertionError):
            self.assertTrue(NH.score("0000-WRONG", "7391-KESTREL"))

    def test_control_seed_is_not_python_str_hash(self):
        """The bug this tool had: str-hash seeding is per-process random, so the
        'deterministic' prompt would change run to run."""
        # _seed must be a pure integer mix, stable regardless of PYTHONHASHSEED.
        self.assertEqual(NH._seed(1234, 1, 50), NH._seed(1234, 1, 50))
        self.assertNotEqual(NH._seed(1234, 1, 50), NH._seed(1234, 1, 90))


class TestDeterminismAcrossProcesses(unittest.TestCase):
    """Prove the prompt is byte-identical across two processes with different
    hash seeds.  This is the end-to-end version of the _seed control: it would
    have failed before the str-hash seeding was replaced."""

    PROG = (
        "import importlib.util,sys,hashlib\n"
        "spec=importlib.util.spec_from_file_location('nh', %r)\n"
        "m=importlib.util.module_from_spec(spec); sys.modules['nh']=m\n"
        "spec.loader.exec_module(m)\n"
        "p,_,_=m.build_prompt(1000,50,1,1234)\n"
        "print(hashlib.sha256(p.encode()).hexdigest())\n"
    ) % str(TOOL_PATH)

    def _digest(self, hashseed: str) -> str:
        env = dict(os.environ, PYTHONHASHSEED=hashseed)
        r = subprocess.run([sys.executable, "-c", self.PROG],
                           capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def test_same_prompt_under_different_hash_seeds(self):
        self.assertEqual(self._digest("1"), self._digest("2"))


class TestSelftest(unittest.TestCase):
    """The tool's own three-way control must still run and still discriminate."""

    def test_selftest_passes(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = NH.selftest()
        self.assertEqual(rc, 0, buf.getvalue())
        self.assertIn("SELFTEST PASSED", buf.getvalue())

    def test_selftest_negative_control_is_real(self):
        """The selftest must refuse to call a wrong server correct.  Proven by
        pointing the classify path at a wrong-answer result directly."""
        wrong = {"depths": [{"status": "FAIL", "hits": 0, "of": 1}]}
        self.assertEqual(NH.classify(wrong), ("FAIL", 3))


class TestCalibrationSweep(unittest.TestCase):
    """The sweep must use a genuinely-at-scale ratio, not a biased small probe.

    A single small probe reads ~0.7% high on this fleet (chars/token drifts with
    size), which oversizes the deep prompt into a wasted multi-minute prefill.
    """

    def _server(self, ratio, window=None):
        import json as _json
        from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_a):
                pass

            def do_GET(self):
                b = _json.dumps({"data": [{"id": "m", "max_model_len": window or 10**9}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                payload = _json.loads(self.rfile.read(n) or b"{}")
                text = payload["messages"][-1]["content"]
                toks = int(len(text) / ratio)
                if window and toks > window:
                    b = _json.dumps({"error": {"message":
                        f"The input ({toks} tokens) is longer than the model's "
                        f"context length ({window} tokens)."}}).encode()
                    self.send_response(400)
                else:
                    b = _json.dumps({"choices": [{"message": {"content": "x"}}],
                                     "usage": {"prompt_tokens": toks}}).encode()
                    self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

        s = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=s.serve_forever, daemon=True).start()
        self.addCleanup(s.server_close)
        self.addCleanup(s.shutdown)
        return f"http://127.0.0.1:{s.server_address[1]}"

    def test_uses_the_largest_sized_probe_not_the_smallest(self):
        ep = self._server(ratio=4.0)
        ratio, rec = NH.calibrate(ep, "m", None, 30, NH.DEFAULT_CHARS_PER_TOKEN,
                                  targets=(32768, 8192))
        self.assertEqual(rec["probes"][0]["target"], 32768, "must sweep largest-first")
        self.assertEqual(rec["probes"][0]["tokens"], round(rec["probes"][0]["chars"] / 4.0),
                         "used value should come from a large probe")
        self.assertAlmostEqual(ratio, 4.0, delta=0.2)

    def test_probe_targets_are_capped_below_the_window(self):
        """No probe may be built near the window: the build overshoots ~15%, so a
        near-window probe would 400 instead of measuring."""
        ep = self._server(ratio=4.0, window=40000)
        _ratio, rec = NH.calibrate(ep, "m", None, 30, NH.DEFAULT_CHARS_PER_TOKEN,
                                   targets=(1000000, 32768, 8192), max_model_len=40000)
        cap = 40000 / NH.PROBE_SAFETY
        self.assertTrue(rec["targets"], "some probe must remain")
        self.assertLessEqual(max(rec["targets"]), cap)
        for p in rec["probes"]:
            self.assertNotIn("error", p, f"a probe was rejected: {p}")

    def test_out_of_band_probe_is_dropped(self):
        """A truncating server (reports 512 tokens) must not be trusted."""
        ep = self._server(ratio=4.0)
        # Force the small probe to be rejected by giving a huge first target that
        # the server reports as far below target (band check).
        orig = NH.build_prompt

        def small(target, *a, **k):
            p, q, n = orig(target, *a, **k)
            return p[:100], q, n  # tiny prompt => far below its target => dropped

        NH.build_prompt = small
        try:
            ratio, rec = NH.calibrate(ep, "m", None, 30, 4.6, targets=(8192,))
        finally:
            NH.build_prompt = orig
        # The one probe was recorded but flagged out of band, so nothing was used.
        self.assertIn("outside the trusted band", rec["probes"][0].get("note", ""))
        self.assertNotIn("basis", rec)
        self.assertEqual(ratio, 4.6, "no usable probe must keep the estimate")
        self.assertIn("no probe produced a usable", rec["note"])


class TestVerbose(unittest.TestCase):
    """--verbose must narrate progress on stderr and leave stdout clean.

    The report and the --json artifact live on stdout, so progress written there
    would corrupt a redirected artifact.  This drives a verbose run against a
    mock and asserts both halves: stderr got the narration, stdout got none of
    it.
    """

    def test_verbose_goes_to_stderr_only(self):
        import contextlib
        import io
        from http.server import ThreadingHTTPServer
        server = ThreadingHTTPServer(("127.0.0.1", 0),
                                     NH._make_handler({"mode": "correct"}))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        endpoint = f"http://127.0.0.1:{server.server_address[1]}"

        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            res = NH.run_needle_test(model="mock-model", context_length=4000,
                                     api_endpoint=endpoint, depths=[50],
                                     verbose=True)
        self.assertEqual(res["verdict"], "PASS")
        self.assertIn("[nh]", err.getvalue(), "verbose produced no progress")
        self.assertIn("depth 50%", err.getvalue())
        self.assertNotIn("[nh]", out.getvalue(), "verbose leaked into stdout")
        self.assertEqual(out.getvalue(), "", "verbose run wrote to stdout")

    def test_every_verbose_line_carries_a_timestamp(self):
        import contextlib
        import io
        import re
        from http.server import ThreadingHTTPServer
        server = ThreadingHTTPServer(("127.0.0.1", 0),
                                     NH._make_handler({"mode": "correct"}))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        endpoint = f"http://127.0.0.1:{server.server_address[1]}"
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            NH.run_needle_test(model="mock-model", context_length=4000,
                               api_endpoint=endpoint, depths=[50], verbose=True)
        lines = [ln for ln in err.getvalue().splitlines() if ln.strip()]
        self.assertTrue(lines, "no verbose output")
        for ln in lines:
            self.assertRegex(ln, r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] \[nh\] ",
                             f"timestamped line expected, got {ln!r}")

    def test_quiet_by_default(self):
        import contextlib
        import io
        from http.server import ThreadingHTTPServer
        server = ThreadingHTTPServer(("127.0.0.1", 0),
                                     NH._make_handler({"mode": "correct"}))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        endpoint = f"http://127.0.0.1:{server.server_address[1]}"
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            NH.run_needle_test(model="mock-model", context_length=4000,
                               api_endpoint=endpoint, depths=[50])
        self.assertEqual(err.getvalue(), "", "a non-verbose run must be silent")


class TestKeywordInterface(unittest.TestCase):
    """The objective asks for a function taking model / context length / API
    endpoint as keyword arguments; run_needle_test is that entry point."""

    def _endpoint(self, mode):
        from http.server import ThreadingHTTPServer
        server = ThreadingHTTPServer(("127.0.0.1", 0), NH._make_handler(mode))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def test_runs_with_keyword_arguments(self):
        res = NH.run_needle_test(
            model="mock-model",
            context_length="4k",
            api_endpoint=self._endpoint({"mode": "correct"}),
            depths=[50],
        )
        self.assertEqual(res["verdict"], "PASS")
        self.assertEqual(res["context_length"], 4000)
        self.assertEqual(len(res["depths"]), 1)

    def test_the_three_required_arguments_are_required(self):
        with self.assertRaises(TypeError):
            NH.run_needle_test("m", 1000)  # no api_endpoint


class TestTooLongRetry(unittest.TestCase):
    """The shrink-retry path must actually recover a too-long prompt.

    A retry that has only been reasoned about is a comment
    (self-check-your-own-tools.md).  This drives run_depth against a mock that
    rejects anything over a hard window, and asserts the depth still PASSes --
    which can only happen if the retry fired and succeeded.
    """

    def _serve(self, mode):
        from http.server import ThreadingHTTPServer
        server = ThreadingHTTPServer(("127.0.0.1", 0), NH._make_handler(mode))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def test_shrink_retry_recovers(self):
        # The server tokenizes at 4.0 chars/token while the client estimates 4.6,
        # so the first 65536-target prompt is really ~75k tokens and is rejected
        # by the 65536 window; one 0.85 target-shrink lands at ~64k, accepted and
        # within 5% of target.  This can only PASS if the retry fired and worked.
        endpoint = self._serve({"mode": "correct", "window": 65536, "ratio": 4.0})
        rec = NH.run_depth(endpoint, "mock", 65536, 50, 1, 1, 32, 30, None,
                           NH.DEFAULT_CHARS_PER_TOKEN)
        self.assertEqual(rec["status"], "PASS", rec)
        self.assertGreaterEqual(rec["attempts"], 2, "retry did not fire")
        self.assertEqual(rec["hits"], 1)

    def test_max_model_len_caps_the_target_instead_of_looping(self):
        """A window smaller than the request must be capped, not retried into a
        400 loop: the tool fills only what the server advertises."""
        endpoint = self._serve({"mode": "correct"})  # no server-side window
        rec = NH.run_depth(endpoint, "mock", 65536, 50, 1, 1, 32, 30, None,
                           NH.DEFAULT_CHARS_PER_TOKEN, max_model_len=1000)
        self.assertEqual(rec["attempts"], 1, "a capped request must not loop")
        self.assertLessEqual(rec["paced_target"], 1000)
        self.assertGreater(rec["paced_target"], 0)
        # 1000 tokens is far below a 65536 request, so the honest verdict is that
        # the requested window was not reached -- not a PASS and not an ERROR.
        self.assertEqual(rec["status"], "TRUNCATED", rec)

    def test_accepted_but_short_prompt_is_truncated_not_retried(self):
        """A prompt the server accepts but counts as short is a truncation
        finding.  Retrying it would hide exactly what the tool exists to catch."""
        endpoint = self._serve({"mode": "truncate"})  # reports 512 tokens, 200 OK
        rec = NH.run_depth(endpoint, "mock", 65536, 50, 1, 1, 32, 30, None,
                           NH.DEFAULT_CHARS_PER_TOKEN)
        self.assertEqual(rec["status"], "TRUNCATED", rec)
        self.assertEqual(rec["attempts"], 1, "a 200-OK short prompt must not retry")


if __name__ == "__main__":
    unittest.main()