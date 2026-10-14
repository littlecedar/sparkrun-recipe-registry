"""Guards for tools/bfcl-eval.py.

Run:
    python3 -m unittest tests.test_bfcl_eval -v

Stdlib-only, like the rest of tests/ and tools/ (AGENTS.md).  The tool is a
dash-named file, so it is imported via importlib and registered in sys.modules
before exec_module (the house import idiom).

What this guards
----------------
The tool is a *scoring instrument*: it reimplements BFCL's official AST rule
(ShishirPatil/gorilla, AGPL-3.0) so the accuracy number is the leaderboard's
own rule rather than a lookalike.  The failure that matters is a scorer that is
too *lenient* — it turns a wrong tool call into a pass and every model looks
good — so nearly every test here is a negative control: a plausibly-wrong model
output that MUST be rejected.  A guard that has only ever passed proves nothing
(self-check-your-own-tools.md).

The tool carries its own end-to-end control (`--selftest`: correct /
wrong-name / wrong-value / empty / hallucinated mocks); test_selftest_all_controls
asserts that control still runs and still refuses to call a wrong server correct.
The rest of this file guards the pieces the selftest does not isolate (data
loading fail-closed, reply extraction, schema conversion).
"""

from __future__ import annotations

import contextlib
import http.server
import importlib.util
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL_PATH = REPO_ROOT / "tools" / "bfcl-eval.py"


def load_tool():
    """Import tools/bfcl-eval.py (dash-named, so via importlib)."""
    spec = importlib.util.spec_from_file_location("bfcl_eval", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["bfcl_eval"] = module
    spec.loader.exec_module(module)
    return module


BFCL = load_tool()


# A minimal BFCL-shaped record, used by the loading tests.  Two functions so
# the `multiple` category has something to choose between.
_QUESTION = {
    "id": "simple_0",
    "question": [[{"role": "user", "content": "Triangle area, base 10, height 5."}]],
    "function": [{
        "name": "calculate_triangle_area",
        "description": "Area of a triangle.",
        "parameters": {"type": "dict", "properties": {
            "base": {"type": "integer"}, "height": {"type": "integer"},
            "unit": {"type": "string"}}, "required": ["base", "height"]},
    }],
}
_ANSWER = {"id": "simple_0", "ground_truth": [
    {"calculate_triangle_area": {"base": [10], "height": [5], "unit": ["units", ""]}}]}


def _check(calls, possible_answers=None, category="simple", funcs=None):
    funcs = funcs or BFCL.sanitize_func(_QUESTION["function"][0])
    checker_funcs = funcs if isinstance(funcs, list) else [funcs]
    answers = possible_answers or BFCL.sanitize_answer(_ANSWER["ground_truth"])
    valid, error_type, error = BFCL.score_entry(category, checker_funcs, answers, calls)
    return valid, error_type, error


class TestAstChecker(unittest.TestCase):
    """The ported official rule: exact name, exact parameters, exact types."""

    def test_correct_call_passes(self):
        valid, _, _ = _check([{"calculate_triangle_area": {"base": 10, "height": 5}}])
        self.assertTrue(valid, "a correct call must pass")

    def test_optional_parameter_omitted_passes(self):
        # `unit` allows "" (optional), so leaving it out is a pass.
        valid, _, _ = _check([{"calculate_triangle_area": {"base": 10, "height": 5}}])
        self.assertTrue(valid)

    def test_optional_parameter_provided_passes(self):
        valid, _, _ = _check([{"calculate_triangle_area": {"base": 10, "height": 5, "unit": "units"}}])
        self.assertTrue(valid)

    def test_wrong_function_name_fails(self):
        valid, error_type, _ = _check([{"area_of_triangle": {"base": 10, "height": 5}}])
        self.assertFalse(valid)
        self.assertEqual(error_type, "simple_function_checker:wrong_func_name")

    def test_wrong_value_fails(self):
        valid, error_type, _ = _check([{"calculate_triangle_area": {"base": 11, "height": 5}}])
        self.assertFalse(valid)
        self.assertEqual(error_type, "value_error:others")

    def test_missing_required_parameter_fails(self):
        valid, error_type, _ = _check([{"calculate_triangle_area": {"base": 10}}])
        self.assertFalse(valid)
        self.assertEqual(error_type, "simple_function_checker:missing_required")

    def test_unexpected_parameter_fails(self):
        valid, error_type, _ = _check(
            [{"calculate_triangle_area": {"base": 10, "height": 5, "colour": "red"}}])
        self.assertFalse(valid)
        self.assertEqual(error_type, "simple_function_checker:unexpected_param")

    def test_string_where_integer_required_fails(self):
        # A model that stringifies its numbers must not be scored as correct.
        valid, error_type, _ = _check([{"calculate_triangle_area": {"base": "10", "height": 5}}])
        self.assertFalse(valid)
        self.assertEqual(error_type, "type_error:simple")

    def test_int_accepted_where_float_required_passes(self):
        # BFCL's stated int->float coercion: an integer for a float parameter passes.
        funcs = [{"name": "wait", "description": "", "parameters": {
            "type": "dict", "properties": {"seconds": {"type": "float"}}, "required": ["seconds"]}}]
        answers = [{"wait": {"seconds": [1.0]}}]
        self.assertTrue(BFCL.score_entry("simple", funcs, answers, [{"wait": {"seconds": 1}}])[0])

    def test_float_where_integer_required_fails(self):
        # ...but the reverse is not coerced: 10.0 for an integer parameter is a type error.
        valid, error_type, _ = _check([{"calculate_triangle_area": {"base": 10.0, "height": 5}}])
        self.assertFalse(valid)
        self.assertEqual(error_type, "type_error:simple")

    def test_wrong_arity_fails(self):
        valid, error_type, _ = _check([
            {"calculate_triangle_area": {"base": 10, "height": 5}},
            {"calculate_triangle_area": {"base": 1, "height": 1}},
        ])
        self.assertFalse(valid)
        self.assertEqual(error_type, "simple_function_checker:wrong_count")


class TestParallelAndMultiple(unittest.TestCase):
    FUNCS = [
        {"name": "play_music", "description": "Play.", "parameters": {
            "type": "dict", "properties": {"artist": {"type": "string"}, "duration": {"type": "integer"}},
            "required": ["artist", "duration"]}},
    ]
    ANSWERS = [{"play_music": {"artist": ["Taylor Swift", "taylor swift"], "duration": [20]}},
               {"play_music": {"artist": ["Maroon 5"], "duration": [15]}}]

    def test_parallel_order_independent(self):
        valid, _, _ = BFCL.score_entry("parallel", self.FUNCS, self.ANSWERS, [
            {"play_music": {"artist": "Maroon 5", "duration": 15}},
            {"play_music": {"artist": "Taylor Swift", "duration": 20}},
        ])
        self.assertTrue(valid, "parallel scoring must not depend on call order")

    def test_parallel_wrong_count_fails(self):
        valid, error_type, _ = BFCL.score_entry("parallel", self.FUNCS, self.ANSWERS, [
            {"play_music": {"artist": "Taylor Swift", "duration": 20}}])
        self.assertFalse(valid)
        self.assertIn("wrong_count", error_type)

    def test_parallel_one_wrong_value_fails(self):
        valid, _, _ = BFCL.score_entry("parallel", self.FUNCS, self.ANSWERS, [
            {"play_music": {"artist": "Taylor Swift", "duration": 20}},
            {"play_music": {"artist": "Maroon 5", "duration": 99}},
        ])
        self.assertFalse(valid)

    def test_multiple_picks_wrong_function_fails(self):
        funcs = [
            {"name": "get_weather", "description": "", "parameters": {
                "type": "dict", "properties": {"city": {"type": "string"}}, "required": ["city"]}},
            {"name": "get_stock_price", "description": "", "parameters": {
                "type": "dict", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]}},
        ]
        answers = [{"get_weather": {"city": ["Paris"]}}]
        self.assertTrue(BFCL.score_entry("multiple", funcs, answers, [{"get_weather": {"city": "Paris"}}])[0])
        valid, _, _ = BFCL.score_entry("multiple", funcs, answers, [{"get_stock_price": {"ticker": "AAPL"}}])
        self.assertFalse(valid, "the wrong function of several must be rejected")


class TestRelevanceRule(unittest.TestCase):
    def test_irrelevance_rejects_any_call(self):
        valid, error_type, _ = BFCL.score_entry("irrelevance", [], [], [{"anything": {"a": 1}}])
        self.assertFalse(valid)
        self.assertEqual(error_type, "irrelevance_error:decoder_success")

    def test_irrelevance_passes_on_silence(self):
        self.assertTrue(BFCL.score_entry("irrelevance", [], [], [])[0])

    def test_relevance_requires_a_call(self):
        self.assertTrue(BFCL.score_entry("live_relevance", [], [], [{"anything": {"a": 1}}])[0])
        valid, error_type, _ = BFCL.score_entry("live_relevance", [], [], [])
        self.assertFalse(valid)
        self.assertEqual(error_type, "relevance_error:decoder_failed")


class TestObjectiveStringStandardization(unittest.TestCase):
    def test_punctuation_and_case_ignored(self):
        self.assertEqual(BFCL.standardize_string("April 1, 2024"),
                         BFCL.standardize_string("april1 2024"))
        self.assertEqual(BFCL.standardize_string("San Diego, CA"),
                         BFCL.standardize_string("san diego ca"))

    def test_different_values_still_differ(self):
        self.assertNotEqual(BFCL.standardize_string("sparkrun"), BFCL.standardize_string("sparkrum"))


class TestExtraction(unittest.TestCase):
    def test_native_tool_calls(self):
        calls = BFCL.extract_calls({"tool_calls": [
            {"function": {"name": "a.b", "arguments": '{"x": 1}'}},
            {"function": {"name": "c", "arguments": ""}},
        ]})
        self.assertEqual(calls, [{"a_b": {"x": 1}}, {"c": {}}])

    def test_content_json_object(self):
        calls = BFCL.extract_calls({"content": '{"name": "f", "arguments": {"k": 2}}'})
        self.assertEqual(calls, [{"f": {"k": 2}}])

    def test_content_plain_name_to_args(self):
        self.assertEqual(BFCL.extract_calls({"content": '{"f": {"k": 2}}'}), [{"f": {"k": 2}}])

    def test_content_json_list(self):
        calls = BFCL.extract_calls(
            {"content": '[{"name": "f", "arguments": {"k": 1}}, {"g": {"m": 2}}]'})
        self.assertEqual(calls, [{"f": {"k": 1}}, {"g": {"m": 2}}])

    def test_fenced_json_is_unwrapped(self):
        calls = BFCL.extract_calls({"content": '```json\n{"f": {"k": 2}}\n```'})
        self.assertEqual(calls, [{"f": {"k": 2}}])

    def test_prose_reply_is_no_call(self):
        self.assertEqual(BFCL.extract_calls({"content": "The answer is 42."}), [])

    def test_empty_message_is_no_call(self):
        self.assertEqual(BFCL.extract_calls({}), [])

    def test_unparseable_arguments_raise(self):
        # A malformed call is a finding, not silently "no call".
        with self.assertRaises(BFCL.CallParseError):
            BFCL.extract_calls({"tool_calls": [{"function": {"name": "f", "arguments": "{not json"}}]})

    def test_non_object_arguments_raise(self):
        with self.assertRaises(BFCL.CallParseError):
            BFCL.extract_calls({"tool_calls": [{"function": {"name": "f", "arguments": "[1, 2]"}}]})


class TestSchemaConversion(unittest.TestCase):
    def test_bfcl_dict_type_becomes_object_recursively(self):
        converted = BFCL.to_json_schema({
            "type": "dict",
            "properties": {"inner": {"type": "dict", "properties": {"x": {"type": "tuple"}}}},
        })
        self.assertEqual(converted["type"], "object")
        self.assertEqual(converted["properties"]["inner"]["type"], "object")
        self.assertEqual(converted["properties"]["inner"]["properties"]["x"]["type"], "array")

    def test_input_is_not_mutated(self):
        source = {"type": "dict", "properties": {"x": {"type": "integer"}}}
        BFCL.to_json_schema(source)
        self.assertEqual(source["type"], "dict", "conversion must not mutate BFCL data")

    def test_tools_payload_sanitizes_names(self):
        tools = BFCL.to_openai_tools([{"name": "math.factorial", "description": "",
                                       "parameters": {"type": "dict", "properties": {}}}])
        self.assertEqual(tools[0]["function"]["name"], "math_factorial")
        self.assertEqual(tools[0]["function"]["parameters"]["type"], "object")


class TestDataLoadingFailsClosed(unittest.TestCase):
    def test_missing_file_raises(self):
        with self.assertRaises(BFCL.DataError):
            BFCL.load_jsonl(Path("/nonexistent/bfcl/BFCL_v3_simple.json"))

    def test_empty_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.json"
            path.write_text("\n\n", encoding="utf-8")
            with self.assertRaises(BFCL.DataError):
                BFCL.load_jsonl(path)

    def test_malformed_json_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{not json}\n", encoding="utf-8")
            with self.assertRaises(BFCL.DataError):
                BFCL.load_jsonl(path)

    def test_load_category_missing_question_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(BFCL.DataError):
                BFCL.load_category(Path(tmp), "simple")

    def test_load_category_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "possible_answer").mkdir()
            (root / "BFCL_v3_simple.json").write_text(json.dumps(_QUESTION) + "\n", encoding="utf-8")
            (root / "possible_answer" / "BFCL_v3_simple.json").write_text(
                json.dumps(_ANSWER) + "\n", encoding="utf-8")
            entries = BFCL.load_category(root, "simple")
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["id"], "simple_0")
            self.assertIsNotNone(entries[0]["answer"])
            # and the loaded record scores a correct call as a pass
            funcs = [BFCL.sanitize_func(f) for f in entries[0]["question"]["function"]]
            answers = BFCL.sanitize_answer(entries[0]["answer"]["ground_truth"])
            self.assertTrue(BFCL.score_entry("simple", funcs, answers,
                                             [{"calculate_triangle_area": {"base": 10, "height": 5}}])[0])

    def test_irrelevance_needs_no_answer_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "BFCL_v3_irrelevance.json").write_text(
                json.dumps({"id": "irrelevance_0", "question": _QUESTION["question"],
                            "function": _QUESTION["function"]}) + "\n", encoding="utf-8")
            entries = BFCL.load_category(root, "irrelevance")
            self.assertIsNone(entries[0]["answer"])
            self.assertTrue(BFCL.score_entry("irrelevance", [], [], [])[0])


class TestRunnerAccounting(unittest.TestCase):
    """A transport error must not be counted as a pass or as a scored miss."""

    def test_transport_error_is_excluded_from_the_score(self):
        def boom(messages, tools):
            raise OSError("connection refused")

        entries = [{"category": "simple", "id": "simple_0",
                    "question": _QUESTION, "answer": _ANSWER}]
        result = BFCL.run(entries, "", "", quiet=True, ask_fn=boom)
        self.assertEqual(result["completed"], 0)
        self.assertEqual(result["records"][0]["error_type"], "transport_error")
        summary = BFCL.category_summary(result["records"])
        self.assertEqual(summary["simple"]["accuracy"], 0.0)

    def test_unsupported_content_is_skipped_not_scored(self):
        question = dict(_QUESTION)
        question["question"] = [[{"role": "user", "content": [{"type": "image_url", "image_url": {}}]}]]
        entries = [{"category": "simple", "id": "simple_0", "question": question, "answer": _ANSWER}]
        result = BFCL.run(entries, "", "", quiet=True, ask_fn=lambda m, t: {"content": ""})
        self.assertEqual(result["records"][0]["error_type"], "unsupported_content")
        self.assertEqual(result["completed"], 0)


class TestSelftestControls(unittest.TestCase):
    def test_selftest_all_controls_pass(self):
        # The tool's own end-to-end ladder (correct=100%; wrong-name, wrong-value,
        # empty, hallucinated = rejected).  If the scorer ever regresses into
        # passing a wrong call, this raises.
        self.assertEqual(BFCL.selftest(), 0)


class TestNegativeControlIsReal(unittest.TestCase):
    """A meta-control: the guard's own fixture must be able to fail.

    If the scorer were replaced by `lambda *a: True`, every test above would
    pass.  This asserts the *same* fixture that passes a correct call rejects a
    tampered one, so the pass above is evidence and not a tautology.
    """

    def test_same_fixture_fails_on_a_tampered_call(self):
        good = [{"calculate_triangle_area": {"base": 10, "height": 5}}]
        bad = [{"calculate_triangle_area": {"base": 10, "height": 6}}]
        self.assertTrue(_check(good)[0])
        self.assertFalse(_check(bad)[0])


@contextlib.contextmanager
def _mock_endpoint(mode="correct"):
    """A tiny OpenAI-compatible endpoint that returns the gold call, or a tampered one."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, obj, code=200):
            payload = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self.path == "/v1/models":
                self._send({"data": [{"id": "mock-model"}]})
            else:
                self._send({"error": "not found"}, 404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            text = body["messages"][-1]["content"]
            tool_calls = []
            if text.startswith("Triangle"):
                params = {"base": 10, "height": 5 if mode == "correct" else 6}
                tool_calls = [{"id": "call_0", "type": "function", "function": {
                    "name": "calculate_triangle_area", "arguments": json.dumps(params)}}]
            self._send({"choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                "role": "assistant", "content": "", "tool_calls": tool_calls}}]})

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _write_data(root: Path):
    (root / "possible_answer").mkdir()
    (root / "BFCL_v3_simple.json").write_text(json.dumps(_QUESTION) + "\n", encoding="utf-8")
    (root / "possible_answer" / "BFCL_v3_simple.json").write_text(
        json.dumps(_ANSWER) + "\n", encoding="utf-8")


class TestEndToEnd(unittest.TestCase):
    """Run the CLI against a real (mock) HTTP endpoint: the runnable proof.

    The selftest injects the reply as a callable; this drives the whole path —
    argument parsing, `/v1/models` resolution, the POST, reply extraction,
    scoring, and the `--json` artifact — over a socket.
    """

    def test_run_scores_a_correct_endpoint_and_writes_the_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_data(root)
            artifact_path = root / "bfcl.json"
            with _mock_endpoint("correct") as base, contextlib.redirect_stdout(_NullWriter()):
                code = BFCL.main(["--base-url", base, "--data-dir", str(root),
                                  "--categories", "simple", "--json", str(artifact_path)])
            self.assertEqual(code, 0)
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(artifact["model"], "mock-model")
            self.assertEqual(artifact["overall"]["pct"], 100.0)
            self.assertEqual(
                artifact["records"][0]["calls"],
                [{"calculate_triangle_area": {"base": 10, "height": 5}}])

    def test_run_rejects_a_wrong_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_data(root)
            artifact_path = root / "bfcl.json"
            with _mock_endpoint("wrong") as base, contextlib.redirect_stdout(_NullWriter()):
                code = BFCL.main(["--base-url", base, "--data-dir", str(root),
                                  "--categories", "simple", "--json", str(artifact_path)])
            self.assertEqual(code, 0)  # a score is the artifact, not an error
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(artifact["overall"]["pct"], 0.0)

    def test_unknown_category_is_a_bad_flag(self):
        with contextlib.redirect_stderr(_NullWriter()):
            code = BFCL.main(["--data-dir", "/tmp", "--categories", "sql"])
        self.assertEqual(code, 2)

    def test_missing_data_dir_is_a_bad_flag(self):
        with contextlib.redirect_stderr(_NullWriter()):
            code = BFCL.main(["--categories", "simple"])
        self.assertEqual(code, 2)


class _NullWriter:
    def write(self, _text):
        return len(_text)

    def flush(self):
        pass

if __name__ == "__main__":
    unittest.main()
