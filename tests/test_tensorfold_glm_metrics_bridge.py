# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Guard for the tensorfold GLM 3bpw launcher's metrics bridge (window 4).

The TensorFold serve logs no line the sparkrun monitor scraper matches, so the
bridge reprints /metrics counters in sglang's own shapes. These tests pin the
pure parts: the parser accepts only `tensorfold:*` lines, and the formatter
emits the exact four shapes (throughput twice, Running, Waiting).

The mod is loaded by path (sparkrun ships the mod directory, so the launcher is
not an importable package member) — the house import idiom.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHIM = REPO_ROOT / "recipes" / "glm" / "mods" / "tensorfold-glm53-3bpw-launcher" / "launcher.py"


def load_shim():
    name = "glm_3bpw_launcher_bridge_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SHIM)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SAMPLE = """\
tensorfold:requests_running 1
tensorfold:requests_waiting 0
tensorfold:prompt_tokens_total 182737
tensorfold:generation_tokens_total 207
tensorfold:kv_cache_usage_ratio{pool="0"} 0.031113
# HELP tensorfold:requests_running running requests
http_get_seconds 0.25
tensorfold:broken_line not-a-number
"""


class ParseTensorfoldMetrics(unittest.TestCase):
    def setUp(self):
        self.mod = load_shim()

    def test_takes_tensorfold_names_only(self):
        vals = self.mod.parse_tensorfold_metrics(SAMPLE)
        self.assertEqual(vals.get("tensorfold:requests_running"), 1.0)
        self.assertEqual(vals.get("tensorfold:requests_waiting"), 0.0)
        self.assertEqual(vals.get("tensorfold:generation_tokens_total"), 207.0)

    def test_skips_labels_comments_and_foreign_names(self):
        vals = self.mod.parse_tensorfold_metrics(SAMPLE)
        # The labelled series is stored under its family name, never the raw label.
        self.assertNotIn('tensorfold:kv_cache_usage_ratio{pool="0"}', vals)
        self.assertEqual(vals.get("tensorfold:kv_cache_usage_ratio"), 0.031113)
        self.assertNotIn("http_get_seconds", vals)
        self.assertNotIn("tensorfold:broken_line", vals)
        self.assertEqual(len(vals), 5)

    def test_empty_body_is_empty_dict(self):
        self.assertEqual(self.mod.parse_tensorfold_metrics(""), {})


class BuildMetricLines(unittest.TestCase):
    def setUp(self):
        self.mod = load_shim()
        self.vals = self.mod.parse_tensorfold_metrics(SAMPLE)

    def test_exact_shapes_with_rate(self):
        lines, gen, now = self.mod.build_metric_lines(self.vals, 200.0, 100.0, 104.0)
        self.assertEqual(gen, 207.0)
        self.assertEqual(now, 104.0)
        self.assertEqual(lines, [
            "Avg generation throughput: 1.75 tokens/s",
            "gen throughput (token/s): 1.75",
            "Running: 1 reqs",
            "Waiting: 0 reqs",
        ])

    def test_first_sample_has_no_throughput_line(self):
        lines, _, _ = self.mod.build_metric_lines(self.vals, None, None, 100.0)
        self.assertEqual(lines, ["Running: 1 reqs", "Waiting: 0 reqs"])
        joined = "\n".join(lines)
        self.assertNotIn("tokens/s", joined)
        self.assertNotIn("token/s", joined)

    def test_missing_generation_counter_emits_no_throughput(self):
        # No fabricated zeros: a sample without the counter must not print a rate,
        # even when a previous sample makes a delta computable.
        vals = dict(self.vals)
        del vals["tensorfold:generation_tokens_total"]
        lines, gen, _ = self.mod.build_metric_lines(vals, 200.0, 100.0, 104.0)
        self.assertIsNone(gen)
        self.assertNotIn("tokens/s", "\n".join(lines))
        self.assertNotIn("token/s", "\n".join(lines))

    def test_missing_gauges_emit_no_lines(self):
        lines, _, _ = self.mod.build_metric_lines({}, 200.0, 100.0, 104.0)
        self.assertEqual(lines, [])

    def test_bridge_thread_starts_only_on_rank_zero_and_is_gated(self):
        # The gate is read from the environment at boot: default ON, TF_METRICS_BRIDGE=0 off.
        src = SHIM.read_text()
        self.assertIn('os.environ.get("TF_METRICS_BRIDGE", "1")', src)
        self.assertIn("args.node_rank == 0", src)
        self.assertIn("proc = subprocess.Popen(cmd)", src)
        self.assertNotIn("os.execvp", src)
        # Refusals before the listener binds are expected: backoff, not one-shot exit.
        self.assertIn("backoff_cap_s", src)
        self.assertIn("TF_METRICS_BRIDGE_DEADLINE_S", src)


if __name__ == "__main__":
    unittest.main()