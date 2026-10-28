# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Guard the vLLM-Omni metrics bridge on the media lane's Qwen-Image arm.

A diffusion serve logs none of the four shapes the sparkrun monitor scrapes
(`sparkrun/cli/_monitor_metrics.py`), so the arm's cells stayed blank while its
`/metrics` answered. `recipes/media/mods/vllm-omni-metrics-bridge/launcher.py`
runs the recipe's own `vllm-omni` command as a child and republishes `/metrics`
in those shapes. Two properties are silent when wrong and are pinned here:

  * the parser matches the vLLM-family SUFFIX, not a namespace: this arm
    publishes `vllm_omni:` families and the engine `vllm:` ones, and a hardcoded
    prefix would match one and silently match nothing on the other;
  * nothing is invented: a series the body does not carry emits no line, so the
    monitor shows "not reported" instead of a fabricated zero.

Arming is exercised against `subprocess.Popen`, `threading.Thread` and
`signal.signal` (all stdlib, and patched so the suite installs no handler and
leaves no thread), so no engine, container or network is touched.
"""
import importlib.util
import os
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
MOD = REPO_ROOT / "recipes" / "media" / "mods" / "vllm-omni-metrics-bridge"
LAUNCHER = MOD / "launcher.py"
RECIPE = REPO_ROOT / "recipes" / "media" / "qwen-image-2.1-turbo-7b-bf16-vllm-omni.yaml"

SAMPLE = """\
# HELP vllm:num_requests_running Number of requests in running state.
vllm:num_requests_running 2.0
vllm_omni:num_requests_waiting{stage="0"} 1.0
vllm:generation_tokens_total 207.0
vllm:prompt_tokens_total 182737.0
vllm_omni:peak_memory_mb{stage="0"} 35748.0
http_get_seconds 0.25
vllm:broken_line not-a-number
"""


def load_launcher():
    name = "qwen_image_omni_bridge_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, LAUNCHER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def code_only(src: str) -> str:
    """A module's code: whole-line comments and docstrings removed (prose is not code)."""
    text = "\n".join(ln for ln in src.splitlines() if not ln.strip().startswith("#"))
    return re.sub(r'""".*?"""', "", text, flags=re.DOTALL)


# --- source checks (functions, so NegativeControls can exercise them) --------

def launch_violations(launcher_src: str, recipe_src: str) -> list[str]:
    """What stops this arm's shadow lines from reaching the monitor."""
    bad: list[str] = []
    for marker in ("def parse_metrics", "def build_metric_lines", "def bridge_loop"):
        if marker not in launcher_src:
            bad.append(f"launcher missing {marker}")
    if 'os.environ.get("OMNI_METRICS_BRIDGE", "1")' not in launcher_src:
        bad.append("no OMNI_METRICS_BRIDGE gate (the bridge must be switchable off)")
    if "subprocess.Popen(cmd)" not in launcher_src:
        bad.append("engine is not a child process: a thread cannot be hosted")
    if re.search(r'"vllm:"', code_only(launcher_src)) or re.search(r"'vllm:'", code_only(launcher_src)):
        bad.append("a hardcoded `vllm:` namespace would match nothing on a vllm_omni: body")
    if "signal.signal(signal.SIGTERM, _forward)" not in launcher_src:
        bad.append("no SIGTERM relay: container stop would not reach the engine")
    if '- "mods/vllm-omni-metrics-bridge"' not in recipe_src:
        bad.append("recipe does not declare mods/vllm-omni-metrics-bridge")
    if "/workspace/mods/vllm-omni-metrics-bridge/launcher.py" not in recipe_src:
        bad.append("recipe command does not run the wrapper")
    for required in ("serve", "--omni", "{model}", "{served_model_name}"):
        if required not in recipe_src:
            bad.append(f"recipe command lost {required}")
    return bad


class ParseMetrics(unittest.TestCase):
    def setUp(self):
        self.mod = load_launcher()

    def test_matches_the_suffix_under_either_namespace(self):
        vals = self.mod.parse_metrics(SAMPLE)
        self.assertEqual(vals["running"], 2.0)
        self.assertEqual(vals["waiting"], 1.0)          # vllm_omni: prefix
        self.assertEqual(vals["gen_tokens"], 207.0)
        self.assertEqual(vals["prompt_tokens"], 182737.0)

    def test_skips_foreign_comments_labels_and_garbage(self):
        vals = self.mod.parse_metrics(SAMPLE)
        self.assertEqual(len(vals), 4)
        self.assertNotIn("peak_memory_mb", vals)         # not a wanted series
        self.assertNotIn("http_get_seconds", vals)
        self.assertNotIn('vllm_omni:num_requests_waiting{stage="0"}', vals)

    def test_empty_body_is_empty_dict(self):
        self.assertEqual({}, self.mod.parse_metrics(""))

    def test_family_names_lists_every_family_the_body_carries(self):
        # Evidence-only: this is what the boot line prints when nothing matched,
        # so it must include the foreign and engine-local families too.
        self.assertEqual(self.mod.family_names(SAMPLE), [
            "http_get_seconds",
            "vllm:broken_line",
            "vllm:generation_tokens_total",
            "vllm:num_requests_running",
            "vllm:prompt_tokens_total",
            "vllm_omni:num_requests_waiting",
            "vllm_omni:peak_memory_mb",
        ])

    def test_the_evidence_list_is_not_the_wanted_projection(self):
        # Control: a wanted-only list would hide the real naming, and the exact
        # comparison above can tell the two apart.
        self.assertNotEqual(sorted(self.mod.WANTED), self.mod.family_names(SAMPLE))


class BuildMetricLines(unittest.TestCase):
    def setUp(self):
        self.mod = load_launcher()
        self.vals = self.mod.parse_metrics(SAMPLE)

    def test_exact_shapes_with_rate(self):
        lines, gen, now = self.mod.build_metric_lines(self.vals, 200.0, 100.0, 104.0)
        self.assertEqual(gen, 207.0)
        self.assertEqual(now, 104.0)
        self.assertEqual(lines, [
            "Avg generation throughput: 1.75 tokens/s",
            "gen throughput (token/s): 1.75",
            "Running: 2 reqs",
            "Waiting: 1 reqs",
        ])

    def test_first_sample_has_no_throughput_line(self):
        lines, _, _ = self.mod.build_metric_lines(self.vals, None, None, 100.0)
        self.assertEqual(lines, ["Running: 2 reqs", "Waiting: 1 reqs"])

    def test_a_body_without_token_counters_reports_only_gauges(self):
        # The real risk on this arm: no generation counter at all. Silence, not 0.
        lines, gen, _ = self.mod.build_metric_lines({"running": 1.0, "waiting": 0.0},
                                                    200.0, 100.0, 104.0)
        self.assertIsNone(gen)
        self.assertEqual(lines, ["Running: 1 reqs", "Waiting: 0 reqs"])

    def test_missing_gauges_emit_no_lines(self):
        self.assertEqual([], self.mod.build_metric_lines({}, 200.0, 100.0, 104.0)[0])


class Assembly(unittest.TestCase):
    def setUp(self):
        self.mod = load_launcher()
        self.argv = ["serve", "Qwen/Qwen-Image-2.1-Turbo", "--omni", "--port", "8099"]

    def run_main(self, argv, env=None):
        """Run the wrapper with engine, thread and signal handler all captured."""
        popen = mock.Mock()
        popen.return_value.wait.return_value = 0
        with mock.patch.object(self.mod.subprocess, "Popen", popen), \
                mock.patch.object(self.mod.threading, "Thread") as thread, \
                mock.patch.object(self.mod.signal, "signal") as signals, \
                mock.patch.dict(os.environ, env or {}, clear=False):
            rc = self.mod.main(argv)
        return rc, popen, thread, signals

    def test_the_engine_command_is_forwarded_verbatim(self):
        _, popen, _, _ = self.run_main(self.argv)
        self.assertEqual(["vllm-omni", *self.argv], list(popen.call_args.args[0]))

    def test_the_bridge_reads_the_forwarded_port(self):
        _, _, thread, _ = self.run_main(self.argv)
        self.assertEqual(8099, thread.call_args.kwargs["kwargs"]["port"])
        self.assertEqual(3600.0, thread.call_args.kwargs["kwargs"]["pre_ready_deadline_s"])
        self.assertTrue(thread.call_args.kwargs["daemon"])

    def test_stop_signals_are_relayed_to_the_engine(self):
        _, _, _, signals = self.run_main(self.argv)
        installed = [call.args[0] for call in signals.call_args_list]
        self.assertEqual(2, len(installed))

    def test_the_bridge_is_off_when_the_gate_says_so(self):
        _, popen, thread, _ = self.run_main(self.argv, {"OMNI_METRICS_BRIDGE": "0"})
        self.assertTrue(popen.called)
        self.assertFalse(thread.called)

    def test_the_deadline_is_env_tunable(self):
        _, _, thread, _ = self.run_main(self.argv, {"OMNI_METRICS_BRIDGE_DEADLINE_S": "90"})
        self.assertEqual(90.0, thread.call_args.kwargs["kwargs"]["pre_ready_deadline_s"])

    def test_the_engine_exit_code_is_the_wrapper_exit_code(self):
        rc, _, _, _ = self.run_main(self.argv)
        self.assertEqual(0, rc)

    def test_empty_argv_fails_closed(self):
        _, popen, _, _ = self.run_main([])
        self.assertFalse(popen.called)


class ServePort(unittest.TestCase):
    def setUp(self):
        self.mod = load_launcher()

    def test_reads_both_spellings(self):
        self.assertEqual(9001, self.mod.serve_port(["--port", "9001"]))
        self.assertEqual(9002, self.mod.serve_port(["--port=9002"]))

    def test_defaults_and_never_raises(self):
        self.assertEqual(8000, self.mod.serve_port(["serve", "m", "--omni"]))
        self.assertEqual(8000, self.mod.serve_port(["--port", "not-a-port"]))
        self.assertEqual(8000, self.mod.serve_port(["--port"]))


class Wiring(unittest.TestCase):
    def test_the_arm_arms_the_bridge(self):
        self.assertEqual([], launch_violations(LAUNCHER.read_text(), RECIPE.read_text()))

    def test_the_mod_ships_the_fail_closed_harness(self):
        gate = (MOD / "run.sh").read_text()
        self.assertIn("vllm-omni is not on PATH", gate)
        self.assertIn('[[ -f "${MOD_DIR}/launcher.py" ]]', gate)
        self.assertIn("ast.parse", gate)
        self.assertIn("die", gate)


class NegativeControls(unittest.TestCase):
    """Each guard must fire on the mutation it exists for."""

    def setUp(self):
        self.launcher = LAUNCHER.read_text()
        self.recipe = RECIPE.read_text()

    def test_the_intact_arm_passes(self):
        self.assertEqual([], launch_violations(self.launcher, self.recipe))

    def test_a_recipe_without_the_mod_is_caught(self):
        mutated = self.recipe.replace('  - "mods/vllm-omni-metrics-bridge"\n', "")
        self.assertNotEqual(self.recipe, mutated)
        self.assertTrue(any("does not declare" in b
                            for b in launch_violations(self.launcher, mutated)))

    def test_a_recipe_that_bypasses_the_wrapper_is_caught(self):
        mutated = re.sub(r"(?m)^  python3 /workspace/mods/vllm-omni-metrics-bridge/launcher\.py\n",
                         "", self.recipe)
        self.assertNotEqual(self.recipe, mutated)
        self.assertTrue(any("does not run the wrapper" in b
                            for b in launch_violations(self.launcher, mutated)))

    def test_a_wrapper_that_execs_its_engine_is_caught(self):
        mutated = self.launcher.replace("subprocess.Popen(cmd)", "os.execvp(cmd[0], cmd)")
        self.assertNotEqual(self.launcher, mutated)
        self.assertTrue(any("cannot be hosted" in b
                            for b in launch_violations(mutated, self.recipe)))

    def test_a_hardcoded_namespace_is_caught(self):
        mutated = self.launcher.replace(
            'WANTED.get(family(line).rpartition(":")[2])',
            'WANTED.get(family(line).removeprefix("vllm:"))',
        )
        self.assertNotEqual(self.launcher, mutated)
        self.assertTrue(any("hardcoded `vllm:` namespace" in b
                            for b in launch_violations(mutated, self.recipe)))

    def test_a_wrapper_without_the_gate_is_caught(self):
        mutated = self.launcher.replace('os.environ.get("OMNI_METRICS_BRIDGE", "1")', '"1"')
        self.assertNotEqual(self.launcher, mutated)
        self.assertTrue(any("OMNI_METRICS_BRIDGE gate" in b
                            for b in launch_violations(mutated, self.recipe)))


if __name__ == "__main__":
    unittest.main()
