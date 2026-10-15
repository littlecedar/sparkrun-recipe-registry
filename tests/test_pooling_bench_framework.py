"""Guards for plugins/pooling_bench_framework.py.

Run:
    python3 -m unittest tests.test_pooling_bench_framework -v

Stdlib-only, like the rest of tests/ and tools/ (AGENTS.md).

What this guards
----------------
The plugin is the adapter between sparkrun's benchmark scheduler and
``tools/pooling-bench.py``, the pooling lanes' instrument.  Three things in it
can break *silently*, so each has a negative control here:

* **The cell identity.**  ``task_coverage_key`` and
  ``consolidated_coverage_keys`` must agree exactly, or the scheduler's gap pass
  re-queues every task (or none) — the failure looks like a slow run, not a bug.
  The agreement is asserted against a *real* instrument payload, not a
  hand-written dict.
* **The command line.**  A wrong flag name or a missing ``--json-out`` is not
  visible until a 40-minute sweep produces nothing.
* **"Measured nothing" cannot pass.**  ``measured_nothing`` is the last line of
  defence; the e2e negative control runs the instrument against a 404 stub and
  asserts the payload it writes in that case is rejected.

The repo venv has no ``sparkrun`` installed (tools/ and tests/ are stdlib-only, and tests
must not *require* sparkrun), so the plugin's sparkrun imports are satisfied with minimal
stubs *unless* the real package is importable — in which case the real one is used and the
stubbed path is not exercised at all.  The plugin itself lives in ``plugins/``, the one tree
that imports sparkrun by definition: it is loaded *inside* a sparkrun process, never as a
standalone tool.
"""

from __future__ import annotations

import dataclasses
import hashlib
import http.server
import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_PATH = REPO_ROOT / "plugins" / "pooling_bench_framework.py"
INSTRUMENT = REPO_ROOT / "tools" / "pooling-bench.py"

try:  # a sparkrun install may or may not be present; both must work
    import sparkrun.benchmarking.base  # noqa: F401

    STUBBED = False
except ImportError:
    STUBBED = True


def _stub_sparkrun() -> None:
    """Install the minimum surface the plugin imports, under the real names."""

    @dataclasses.dataclass
    class BenchTask:
        index: int
        label: str
        run_args: dict = dataclasses.field(default_factory=dict)
        schedule_entry: dict = dataclasses.field(default_factory=dict)

    @dataclasses.dataclass(frozen=True)
    class ProgressColumn:
        name: str
        justify: str = "right"
        style: str | None = None

    @dataclasses.dataclass(frozen=True)
    class ProgressTableSpec:
        columns: list
        rows_from_consolidated: object
        row_key: object = None
        format_cell: object = None

    class BenchmarkingPlugin:
        framework_name = ""
        categories: tuple = ()
        model_argument_is_model_id = False
        default_args: dict = {}
        passthrough_args: set = set()

    class BenchmarkError(Exception):
        pass

    def module(name):
        mod = types.ModuleType(name)
        sys.modules[name] = mod
        return mod

    sparkrun = module("sparkrun")
    benchmarking = module("sparkrun.benchmarking")
    core = module("sparkrun.core")
    base = module("sparkrun.benchmarking.base")
    scheduler = module("sparkrun.benchmarking.scheduler")
    profiles = module("sparkrun.core.benchmark_profiles")

    base.BenchmarkingPlugin = BenchmarkingPlugin
    base.ProgressColumn = ProgressColumn
    base.ProgressTableSpec = ProgressTableSpec
    scheduler.BenchTask = BenchTask
    profiles.BenchmarkError = BenchmarkError

    sparkrun.benchmarking = benchmarking
    sparkrun.core = core
    benchmarking.base = base
    benchmarking.scheduler = scheduler
    core.benchmark_profiles = profiles


if STUBBED:
    _stub_sparkrun()


def _load_plugin():
    spec = importlib.util.spec_from_file_location("pooling_bench_framework", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["pooling_bench_framework"] = module
    spec.loader.exec_module(module)
    return module


PLUGIN = _load_plugin()
BenchmarkError = PLUGIN.BenchmarkError


def _vector(seed: str) -> list[float]:
    """Deterministic vector: different seeds differ, the same seed repeats.

    The instrument's own checks (distinct-inputs, stability) are the reason this
    must be a function of the *request*, not of a message inside it: the chat
    form's first message is the shared instruction, so a per-message answer would
    report two different inputs as identical.
    """
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return [digest[i] / 255.0 for i in range(8)]


class _StubHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    fail = False

    def log_message(self, format, *args):  # keep unittest output clean
        pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send(404, {"error": {"message": "Not Found", "code": 404}})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        if self.fail:
            self._send(404, {"error": {"message": "pooling engine says no", "code": 404}})
            return
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            body = {}
        # A pooling engine answers one vector per request for the chat form and
        # /v2/embed; only the plain list form returns one per text.
        inputs = body.get("input")
        if isinstance(inputs, list) and all(isinstance(item, str) for item in inputs):
            seeds = inputs
        else:
            seeds = [json.dumps(body, sort_keys=True)]
        data = [{"object": "embedding", "index": i, "embedding": _vector(seed)} for i, seed in enumerate(seeds)]
        self._send(200, {"object": "list", "data": data, "model": "stub", "usage": {"prompt_tokens": 4, "total_tokens": 4}})


class _StubServer:
    """Context manager around a threaded HTTP stub on an ephemeral port."""

    def __init__(self, *, fail: bool):
        handler = type("_Handler", (_StubHandler,), {"fail": fail})
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        return False


#: The smallest real measurement the stub can serve: three requests at one cell.
#: ``dimension_check`` is stated because the stub's vectors are 8-dimensional —
#: the tool's default expectation is the 2B encoder's 2048.
_STUB_ARGS = {"kind": "embed", "concurrency": [1], "requests": 3, "warmup": 0, "input_tokens": 8, "dimension_check": 8}


def _run_instrument(payload_args: dict, *, fail: bool, tmpdir: str) -> tuple[list[str], subprocess.CompletedProcess, Path]:
    """Build the command through the plugin, run it, return (cmd, proc, result path).

    The caller owns *tmpdir*: the result artifact has to outlive the run, or the
    assertions would be reading a deleted file and passing for the wrong reason.
    """
    fw = PLUGIN.PoolingBenchFramework()
    tasks = fw.build_task_list(payload_args, None)
    result_file = Path(tmpdir) / "out.json"
    with _StubServer(fail=fail) as stub:
        cmd = fw.build_benchmark_command(
            f"http://127.0.0.1:{stub.port}/v1", "stub-model", tasks[0].run_args, result_file=str(result_file)
        )
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    return cmd, proc, result_file


class CommandLineTest(unittest.TestCase):
    def setUp(self):
        self.fw = PLUGIN.PoolingBenchFramework()

    def test_instrument_ships_beside_the_plugin(self):
        """The adapter without the instrument is a misconfigured plugins.paths."""
        self.assertTrue(INSTRUMENT.is_file(), INSTRUMENT)
        self.assertEqual(self.fw.check_prerequisites(), [])
        self.assertEqual(PLUGIN.INSTRUMENT, INSTRUMENT)

    def test_command_shape(self):
        cmd = self.fw.build_benchmark_command(
            "http://node:8010/v1",
            "Qwen/Qwen3-VL-Embedding-2B",
            {"kind": "embed", "mode": "embed-v1-chat", "concurrency": [8], "requests": 100, "synthetic_images": False},
            result_file="/tmp/r.json",
        )
        # Asserted by position rather than as one literal, because flag order
        # follows the args mapping (the tool's argparse does not care).
        self.assertEqual(cmd[:2], [sys.executable, str(INSTRUMENT)])
        self.assertEqual(cmd[2], "embed")
        self.assertIn("--json-out", cmd)
        self.assertEqual(cmd[cmd.index("--json-out") + 1], "/tmp/r.json")
        self.assertEqual(cmd[cmd.index("--base-url") + 1], "http://node:8010/v1")
        self.assertEqual(cmd[cmd.index("--model") + 1], "Qwen/Qwen3-VL-Embedding-2B")
        # list args are rendered single-valued (the task list already expanded them)
        self.assertEqual(cmd[cmd.index("--concurrency") + 1], "8")
        # booleans are bare flags, and a False one is absent
        self.assertNotIn("--synthetic-images", cmd)

    def test_user_json_out_is_ignored(self):
        """The scheduler owns the result file; a user path would be written and dropped."""
        cmd = self.fw.build_benchmark_command("http://h:1/v1", "m", {"kind": "embed", "json_out": "/tmp/other.json"}, result_file="/tmp/real.json")
        self.assertEqual(cmd.count("--json-out"), 1)
        self.assertNotIn("/tmp/other.json", cmd)

    def test_unexpanded_list_is_rejected(self):
        with self.assertRaises(BenchmarkError):
            self.fw.build_benchmark_command("http://h:1/v1", "m", {"kind": "embed", "concurrency": [1, 2]}, result_file=None)


class TaskListTest(unittest.TestCase):
    def setUp(self):
        self.fw = PLUGIN.PoolingBenchFramework()

    def test_kind_is_required_negative_control(self):
        """No safe default exists: the two kinds answer on different routes."""
        with self.assertRaises(BenchmarkError):
            self.fw.build_task_list({"concurrency": [1]}, None)
        with self.assertRaises(BenchmarkError):
            self.fw.build_task_list({"kind": "smoke", "concurrency": [1]}, None)

    def test_concurrency_is_the_ladder_axis(self):
        tasks = self.fw.build_task_list({"kind": "embed", "concurrency": [1, 2, 5], "requests": 10}, None)
        self.assertEqual([t.index for t in tasks], [0, 1, 2])
        self.assertEqual([t.run_args["concurrency"] for t in tasks], [[1], [2], [5]])
        self.assertEqual([t.label for t in tasks], ["concurrency=1", "concurrency=2", "concurrency=5"])
        self.assertEqual(tasks[1].schedule_entry, {"concurrency": 2})
        # artifact names carry the kind and the cell, so two lanes cannot collide
        self.assertEqual([self.fw.result_filename_suffix(t) for t in tasks], ["_embed_c1", "_embed_c2", "_embed_c5"])

    def test_estimate_test_count_matches_the_task_list(self):
        args = {"kind": "embed", "concurrency": [1, 4, 8], "requests": 10}
        self.assertEqual(self.fw.estimate_test_count(args), len(self.fw.build_task_list(args, None)))
        self.assertIsNone(self.fw.estimate_test_count({"concurrency": [1]}))

    def test_schedule_entry_is_one_task(self):
        tasks = self.fw.build_task_list({"kind": "rerank", "concurrency": [1]}, [{"concurrency": 4}, {"concurrency": 8, "docs_per_query": 20}])
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[1].run_args["docs_per_query"], 20)
        self.assertEqual(tasks[1].run_args["concurrency"], [8])

    def test_schedule_entry_cannot_expand_negative_control(self):
        with self.assertRaises(BenchmarkError):
            self.fw.build_task_list({"kind": "embed"}, [{"concurrency": 4, "requests": [10, 20]}])


class CoverageKeysTest(unittest.TestCase):
    def test_keys_agree_with_a_real_payload(self):
        """The gap pass re-queues on mismatch, so the two halves are compared
        against an artifact the instrument really wrote."""
        fw = PLUGIN.PoolingBenchFramework()
        with tempfile.TemporaryDirectory() as tmp:
            cmd, proc, result_file = _run_instrument(_STUB_ARGS, fail=False, tmpdir=tmp)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            task = fw.build_task_list(_STUB_ARGS, None)[0]
            parsed = fw.parse_results(proc.stdout, proc.stderr, result_file=str(result_file))
            self.assertFalse(fw.measured_nothing(parsed))
            self.assertGreater(parsed["json"]["result"]["requests_ok"], 0)
            consolidated = {"runs": [parsed["json"]]}
            self.assertEqual(fw.consolidated_coverage_keys(consolidated), {fw.task_coverage_key(task)})
            # and the row the progress table would render, which must reconcile with the artifact
            rows = PLUGIN._rows_from_consolidated(consolidated)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "embed")
        self.assertEqual(rows[0][1], 1)
        self.assertTrue(rows[0][2].startswith(f"{parsed['json']['result']['requests_ok']}/"))
        self.assertIsNotNone(rows[0][3])

    def test_mismatched_kind_is_not_coverage(self):
        """A rerank result cannot cover an embed cell (the reason kind is in the key)."""
        fw = PLUGIN.PoolingBenchFramework()
        task = fw.build_task_list({"kind": "embed", "concurrency": [4]}, None)[0]
        consolidated = {"runs": [{"config": {"kind": "rerank", "concurrency": 4}, "result": {"requests_ok": 5}}]}
        self.assertNotIn(fw.task_coverage_key(task), fw.consolidated_coverage_keys(consolidated))

    def test_task_without_concurrency_is_a_gap(self):
        fw = PLUGIN.PoolingBenchFramework()
        task = fw.build_task_list({"kind": "embed", "concurrency": [4]}, None)[0]
        task.run_args.pop("concurrency")
        self.assertIn(None, fw.task_coverage_key(task))


class MeasuredNothingTest(unittest.TestCase):
    def test_all_null_payload_is_rejected_negative_control(self):
        """A run that reached nothing must not be exportable as a measurement."""
        fw = PLUGIN.PoolingBenchFramework()
        self.assertTrue(fw.measured_nothing({}))
        self.assertTrue(fw.measured_nothing({"json": {}}))
        self.assertTrue(fw.measured_nothing({"json": {"result": {"requests_ok": 0, "requests_total": 5}}}))
        self.assertFalse(fw.measured_nothing({"json": {"result": {"requests_ok": 1, "requests_total": 5}}}))

    def test_consolidated_payload_is_read_too(self):
        """The export parses the consolidated dict, not one task's artifact.

        A reader that only understood the per-task shape rejected a real sweep
        as "measured nothing" (found by running the framework, not by unit test).
        """
        fw = PLUGIN.PoolingBenchFramework()
        self.assertTrue(fw.measured_nothing({"json": {"runs": [{"result": {"requests_ok": 0}}]}}))
        self.assertTrue(fw.measured_nothing({"json": {"runs": []}}))
        self.assertFalse(fw.measured_nothing({"json": {"runs": [{"result": {"requests_ok": 0}}, {"result": {"requests_ok": 5}}]}}))

    def test_a_404_target_yields_a_rejected_payload(self):
        """End-to-end negative control: the instrument really writes that shape.

        The tool writes its JSON even when every request failed, so the failure
        is caught by ``measured_nothing`` (/ the non-zero exit) rather than by a
        missing file alone.
        """
        fw = PLUGIN.PoolingBenchFramework()
        with tempfile.TemporaryDirectory() as tmp:
            cmd, proc, result_file = _run_instrument(_STUB_ARGS, fail=True, tmpdir=tmp)
            self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual(cmd[2], "embed")
            parsed = fw.parse_results(proc.stdout, proc.stderr, result_file=str(result_file))
            if result_file.is_file():  # the tool's normal shape writes the artifact anyway
                self.assertEqual(parsed["json"]["result"]["requests_ok"], 0)
            self.assertTrue(fw.measured_nothing(parsed))

    def test_missing_result_file_is_a_rejection(self):
        fw = PLUGIN.PoolingBenchFramework()
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "absent.json"
            self.assertTrue(fw.measured_nothing(fw.parse_results("", "", result_file=str(missing))))
            malformed = Path(tmp) / "bad.json"
            malformed.write_text("{not json")
            self.assertTrue(fw.measured_nothing(fw.parse_results("", "", result_file=str(malformed))))


class ProgressSpecTest(unittest.TestCase):
    def test_table_spec_matches_the_consolidated_schema(self):
        fw = PLUGIN.PoolingBenchFramework()
        spec = fw.progress_table_spec()
        self.assertEqual([c.name for c in spec.columns], list(PLUGIN._COLUMNS))
        rows = spec.rows_from_consolidated({"runs": [{"config": {"kind": "embed", "concurrency": 8}, "result": {"units": 100, "wall_seconds": 2.0, "requests_ok": 50, "requests_total": 50, "latency_ms": {"p50": 12.5}}}]})
        self.assertEqual(rows, [("embed", 8, "50/50", 50.0, 12.5)])
        self.assertEqual(spec.row_key(rows[0]), ("embed", 8))
        cells = [spec.format_cell(value, column) for value, column in zip(rows[0], spec.columns)]
        self.assertEqual(cells, ["embed", "8", "50/50", "50.0", "12"])

    def test_row_formatting_survives_missing_numbers(self):
        fw = PLUGIN.PoolingBenchFramework()
        spec = fw.progress_table_spec()
        rows = spec.rows_from_consolidated({"runs": [{"config": {"kind": "rerank", "concurrency": 2}, "result": {}}]})
        self.assertEqual(rows, [("rerank", 2, "?/?", None, None)])
        cells = [spec.format_cell(value, column) for value, column in zip(rows[0], spec.columns)]
        self.assertEqual(cells, ["rerank", "2", "?/?", "…", "…"])


class PluginSurfaceTest(unittest.TestCase):
    def test_framework_identity(self):
        fw = PLUGIN.PoolingBenchFramework()
        self.assertEqual(fw.framework_name, "pooling-bench")
        self.assertEqual(fw.categories, ("pooling",))
        # the instrument sends the *served* name, so the model-identity contract
        # must stay the base default (see base.resolve_request_model)
        self.assertFalse(fw.model_argument_is_model_id)
        self.assertEqual(PLUGIN.KINDS, ("embed", "rerank"))

    def test_api_declaration_is_present(self):
        """Without it the loader skips the module: "missing API declaration"."""
        self.assertEqual(PLUGIN.SPARKRUN_PLUGIN_API_VERSION, 1)
        self.assertEqual(type(PLUGIN.SPARKRUN_PLUGIN_API_VERSION), int)

    def test_module_imports_against_a_real_sparkrun_when_present(self):
        if STUBBED:
            self.skipTest("sparkrun not importable here; stub base exercised instead")
        import sparkrun.benchmarking.base as real_base

        self.assertTrue(issubclass(PLUGIN.PoolingBenchFramework, real_base.BenchmarkingPlugin))


if __name__ == "__main__":
    unittest.main()