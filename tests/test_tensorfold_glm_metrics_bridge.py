# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Guard the metrics bridge in BOTH GLM TensorFold launchers (window 4).

The TensorFold serve logs no line the sparkrun monitor scraper matches
(`sparkrun/cli/_monitor_metrics.py` wants `Avg generation throughput: N tokens/s`,
`Running: N reqs`, …), so each launcher hosts a thread that reprints its
`/metrics` counters in those shapes. Two arms carry it and there is no shared
library across mods (sparkrun ships only a mod's own directory), so this file
pins three things:

  P  the pure parts: the parser accepts only `tensorfold:*` names and the
     formatter emits the exact four shapes (throughput twice, Running, Waiting);
  A  the arming: engine-as-child, rank-0-only, the `TF_METRICS_BRIDGE` gate, the
     SIGTERM relay, and no `execvp` — a shim that execve()s can host no thread;
  C  the bundled copies are byte-identical, so a fix cannot land in one arm only.

Every check is a function over source text so `NegativeControls` can feed it the
mutation it exists for and watch it fire. The mods are loaded by path (they are
not importable package members) — the house import idiom.
"""
import importlib.util
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LAUNCHERS = {
    "glm53-3bpw": REPO_ROOT / "recipes" / "glm" / "mods"
    / "tensorfold-glm53-3bpw-launcher" / "launcher.py",
    "glm-exl3-4bpw": REPO_ROOT / "recipes" / "glm" / "mods"
    / "tensorfold-glm-exl3-launcher" / "launcher.py",
}
RECIPES = {
    "glm53-3bpw": REPO_ROOT / "recipes" / "glm"
    / "glm-5.3-exl3-3bpw-tp4-1m-tensorfold-sglang.yaml",
    "glm-exl3-4bpw": REPO_ROOT / "recipes" / "glm"
    / "glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang.yaml",
}


def load_shim(name):
    module_name = "glm_bridge_test_" + name.replace("-", "_")
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, LAUNCHERS[name])
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


SAMPLE = """\
# HELP tensorfold:requests_running running requests
tensorfold:requests_running 1
tensorfold:requests_waiting 0
tensorfold:prompt_tokens_total 182737
tensorfold:generation_tokens_total 207
tensorfold:kv_cache_usage_ratio{pool="0"} 0.031113
http_get_seconds 0.25
tensorfold:broken_line not-a-number
"""


# --- source checks (functions, so NegativeControls can exercise them) --------

def bridge_region(src: str) -> str:
    """The bridge block: `def parse_tensorfold_metrics` up to the next top-level def."""
    start = src.index("def parse_tensorfold_metrics")
    end = src.index("\ndef ", src.index("def bridge_loop"))
    return src[start:end]


def bridge_violations(src: str) -> list[str]:
    """What stops this launcher's shadow lines from reaching the monitor."""
    bad: list[str] = []
    for marker in ("def parse_tensorfold_metrics", "def build_metric_lines", "def bridge_loop"):
        if marker not in src:
            bad.append(f"missing {marker}")
    if 'os.environ.get("TF_METRICS_BRIDGE", "1")' not in src:
        bad.append("no TF_METRICS_BRIDGE gate (the bridge must be switchable off)")
    if 'os.environ.get("TF_METRICS_BRIDGE_DEADLINE_S", "3600")' not in src:
        bad.append("no TF_METRICS_BRIDGE_DEADLINE_S (the pre-ready wait must be boundable)")
    if 'args.node_rank == 0 and os.environ.get("TF_METRICS_BRIDGE", "1") != "0":' not in src:
        bad.append("bridge not restricted to the rank that serves HTTP")
    if "subprocess.Popen(cmd)" not in src:
        bad.append("engine is not a child process: a thread cannot be hosted")
    if "os.execvp" in src:
        bad.append("the shim execve()s its engine, so no rank can host the bridge")
    if "signal.signal(signal.SIGTERM, _forward)" not in src:
        bad.append("no SIGTERM relay: container stop would not reach the engine")
    if not re.search(r'(?m)^TAG = "\[', src):
        bad.append("no TAG constant: the bridge's log lines would be unattributed")
    return bad


class ParseTensorfoldMetrics(unittest.TestCase):
    def test_takes_tensorfold_names_only(self):
        for name in LAUNCHERS:
            with self.subTest(launcher=name):
                vals = load_shim(name).parse_tensorfold_metrics(SAMPLE)
                self.assertEqual(vals.get("tensorfold:requests_running"), 1.0)
                self.assertEqual(vals.get("tensorfold:requests_waiting"), 0.0)
                self.assertEqual(vals.get("tensorfold:generation_tokens_total"), 207.0)

    def test_skips_labels_comments_and_foreign_names(self):
        for name in LAUNCHERS:
            with self.subTest(launcher=name):
                vals = load_shim(name).parse_tensorfold_metrics(SAMPLE)
                # Labelled series are stored under the family name, never the raw label.
                self.assertNotIn('tensorfold:kv_cache_usage_ratio{pool="0"}', vals)
                self.assertEqual(vals.get("tensorfold:kv_cache_usage_ratio"), 0.031113)
                self.assertNotIn("http_get_seconds", vals)
                self.assertNotIn("tensorfold:broken_line", vals)
                self.assertEqual(len(vals), 5)

    def test_empty_body_is_empty_dict(self):
        for name in LAUNCHERS:
            with self.subTest(launcher=name):
                self.assertEqual(load_shim(name).parse_tensorfold_metrics(""), {})


class BuildMetricLines(unittest.TestCase):
    def test_exact_shapes_with_rate(self):
        for name in LAUNCHERS:
            with self.subTest(launcher=name):
                mod = load_shim(name)
                vals = mod.parse_tensorfold_metrics(SAMPLE)
                lines, gen, now = mod.build_metric_lines(vals, 200.0, 100.0, 104.0)
                self.assertEqual(gen, 207.0)
                self.assertEqual(now, 104.0)
                self.assertEqual(lines, [
                    "Avg generation throughput: 1.75 tokens/s",
                    "gen throughput (token/s): 1.75",
                    "Running: 1 reqs",
                    "Waiting: 0 reqs",
                ])

    def test_first_sample_has_no_throughput_line(self):
        for name in LAUNCHERS:
            with self.subTest(launcher=name):
                mod = load_shim(name)
                lines, _, _ = mod.build_metric_lines(
                    mod.parse_tensorfold_metrics(SAMPLE), None, None, 100.0)
                self.assertEqual(lines, ["Running: 1 reqs", "Waiting: 0 reqs"])
                self.assertNotIn("tokens/s", "\n".join(lines))

    def test_missing_generation_counter_emits_no_throughput(self):
        for name in LAUNCHERS:
            with self.subTest(launcher=name):
                mod = load_shim(name)
                vals = mod.parse_tensorfold_metrics(SAMPLE)
                del vals["tensorfold:generation_tokens_total"]
                lines, gen, _ = mod.build_metric_lines(vals, 200.0, 100.0, 104.0)
                self.assertIsNone(gen)
                self.assertNotIn("tokens/s", "\n".join(lines))
                self.assertNotIn("token/s", "\n".join(lines))

    def test_missing_gauges_emit_no_lines(self):
        for name in LAUNCHERS:
            with self.subTest(launcher=name):
                self.assertEqual(
                    [], load_shim(name).build_metric_lines({}, 200.0, 100.0, 104.0)[0])


class Arming(unittest.TestCase):
    def test_every_glm_launcher_arms_the_bridge(self):
        for name, launcher in LAUNCHERS.items():
            with self.subTest(launcher=name):
                self.assertEqual([], bridge_violations(launcher.read_text()))

    def test_the_two_copies_are_byte_identical(self):
        # Bundled copies (no shared library: sparkrun ships only the mod's own
        # directory), so a fix must land in both arms or this fails.
        a, b = (bridge_region(launcher.read_text()) for launcher in LAUNCHERS.values())
        self.assertEqual(a, b)

    def test_the_first_sample_reports_what_it_matched(self):
        # Fail-open telemetry needs evidence: the announcement line is what tells
        # the next boot whether the scrape keys fit that arm's engine image.
        for name, launcher in LAUNCHERS.items():
            with self.subTest(launcher=name):
                self.assertIn("metrics bridge: matched {sorted(vals)}",
                              bridge_region(launcher.read_text()))

    def test_each_recipe_runs_the_launcher_it_ships(self):
        for name, recipe in RECIPES.items():
            with self.subTest(recipe=recipe.name):
                body = recipe.read_text()
                mod = LAUNCHERS[name].parent.name
                self.assertIn(f'"mods/{mod}"', body)
                self.assertIn(f"/workspace/mods/{mod}/launcher.py", body)


class NegativeControls(unittest.TestCase):
    """Each guard must fire on the mutation it exists for."""

    def setUp(self):
        self.src = LAUNCHERS["glm-exl3-4bpw"].read_text()

    def test_the_intact_source_passes(self):
        self.assertEqual([], bridge_violations(self.src))

    def test_a_launcher_without_the_bridge_is_caught(self):
        stripped = self.src.replace(bridge_region(self.src), "")
        self.assertNotEqual(self.src, stripped)
        self.assertIn("missing def bridge_loop", bridge_violations(stripped))

    def test_a_launcher_that_execs_its_engine_is_caught(self):
        mutated = self.src.replace("subprocess.Popen(cmd)", "os.execvp(cmd[0], cmd)")
        self.assertNotEqual(self.src, mutated)
        self.assertIn("the shim execve()s its engine, so no rank can host the bridge",
                      bridge_violations(mutated))

    def test_a_launcher_without_the_gate_is_caught(self):
        mutated = self.src.replace('os.environ.get("TF_METRICS_BRIDGE", "1")', '"1"')
        self.assertNotEqual(self.src, mutated)
        self.assertTrue(any("TF_METRICS_BRIDGE gate" in b
                            for b in bridge_violations(mutated)))

    def test_a_bridge_on_every_rank_is_caught(self):
        mutated = self.src.replace(
            'if args.node_rank == 0 and os.environ.get("TF_METRICS_BRIDGE", "1") != "0":',
            'if os.environ.get("TF_METRICS_BRIDGE", "1") != "0":',
        )
        self.assertNotEqual(self.src, mutated)
        self.assertTrue(any("rank that serves HTTP" in b
                            for b in bridge_violations(mutated)))

    def test_a_diverged_copy_is_caught(self):
        a = bridge_region(self.src)
        b = a.replace("period_s: float = 5.0", "period_s: float = 6.0")
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
