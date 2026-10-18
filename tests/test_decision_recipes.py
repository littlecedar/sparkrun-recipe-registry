"""Guards for the six decision arms added 2026-10-18.

Content identity is the same contract as every other lane (full-SHA revision,
@sha256 container, every `defaults:` key consumed by a placeholder, the command
consumes the pinned model). On top of that, this lane has four surfaces that are
silent when broken:

  S  the two `vllm-srun` arms carry the runtime shim the shipped Kai/Sol
     siblings carry: `executor_config.user: root` (the shim writes
     /usr/local/bin), `entrypoint: ""` (the image's router entrypoint would
     swallow the appended command), and the bash-builtin `kill` shim ahead of
     the serve line (sparkrun's detached-launch liveness check runs
     `docker exec <c> kill -0`; the python:*-slim base has no /bin/kill, so
     without the shim a healthy serve is declared failed).
  N  laya / kev / kokoro declare `served_model_name: ""` and reference it, so
     sparkrun appends nothing. A non-empty value makes sparkrun append
     `--served-model-name <id>`, and each of these servers exits in argparse on
     the unknown flag. The key must be empty AND live (referenced), or the
     recipe is either dead on arrival or carrying an inert default.
  J  JEV-27B is solo (min/max 1) and runs `--logprobs-mode processed_logprobs`:
     its SystemOne surface is completions logprobs, and the lane's instrument
     reads processed (post-sampling-transform) probabilities.
  X  CPU or GPU is explicit: the five CPU arms declare no
     `gpu_memory_utilization` (and no `--gpu-memory-utilization` flag); the GPU
     arm runs no CPU pin and either declares a consumed
     `gpu_memory_utilization` or bounds residency with a consumed
     `max_model_len`. JEV-27B takes the second form deliberately -- it follows
     its boot-verified 9B sibling and leaves vLLM's own default budget, bounded
     by a 32768 window.

The command-side identity rule is the shared one from
`tests/test_explore_new_arms.py`: `{model}` (laya / kev), a hardcoded prepared
snapshot path (JEV-27B, per recipes/MECHANICS.md's vLLM template rule), or the
vllm-srun repo-id + `--revision=` pair (Nox / d3-edge). Kokoro-82M has no such
form: its model set is baked into the digest-pinned image, so the arm's
identity is the image digest itself and is asserted as that.
No PyYAML: the recipes are parsed as text by the parser the lane guards use, and
an empty parse RAISES rather than passing vacuously.

Run:
    uv run python -B -m unittest tests.test_decision_recipes -v
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.test_explore_new_arms import (
    digest_violations,
    foreign_repo_violations,
    model_consumption_violations,
    revision_violations,
    unconsumed,
)
from tests.test_ornith_recipes import _unquote, parse_text

REPO_ROOT = Path(__file__).resolve().parent.parent
DECISION = REPO_ROOT / "recipes" / "decision"

ARMS = (
    "nox-4b-decision-vllm-srun.yaml",
    "d3-edge-decision-vllm-srun.yaml",
    "laya-decision-serve.yaml",
    "kev-0.8b-decision-serve.yaml",
    "jev-27b-decision-vllm.yaml",
    "kokoro-82m-tts-cpu.yaml",
)
SRUN_ARMS = ("nox-4b-decision-vllm-srun.yaml", "d3-edge-decision-vllm-srun.yaml")
SHIPPED_SRUN = ("kai-0.6b-decision-vllm-srun.yaml",
                "sol-2b-decision-vllm-srun.yaml")
SUPPRESS_ARMS = ("laya-decision-serve.yaml",
                 "kev-0.8b-decision-serve.yaml",
                 "kokoro-82m-tts-cpu.yaml")
JEV = "jev-27b-decision-vllm.yaml"
KOKORO = "kokoro-82m-tts-cpu.yaml"
CPU_ARMS = tuple(n for n in ARMS if n != JEV)

# The shim the shipped siblings carry, character for character (a folded
# `command:` keeps the backslash-n literals that the shell's printf expands).
KILL_SHIM = "printf '#!/bin/bash\\nbuiltin kill \"$@\"\\n' > /usr/local/bin/kill"
CHMOD = "chmod 755 /usr/local/bin/kill"


def arm(name: str) -> dict:
    path = DECISION / name
    if not path.is_file():
        raise AssertionError(f"missing recipe: {path}")
    return parse_text(path.read_text(encoding="utf-8"))


def executor_map(r: dict, section: str = "executor_config") -> dict[str, str]:
    """The one-level `key: value` pairs of a top-level mapping section."""
    block = re.search(rf"(?m)^{re.escape(section)}:\n((?:  [^\n]*(?:\n|$))*)",
                      r["stripped"])
    if not block:
        return {}
    return {k: _unquote(v)
            for k, v in re.findall(r"(?m)^  ([a-z0-9_]+): *(.*)$", block.group(1))}


# ---------------------------------------------------------------------------
# Predicates (negative controls feed these the same mutated text).
# ---------------------------------------------------------------------------

def shim_violations(r: dict) -> list[str]:
    bad: list[str] = []
    executor = executor_map(r)
    if executor.get("user") != "root":
        bad.append(f"executor user is {executor.get('user')!r}, not 'root'")
    if executor.get("entrypoint") != "":
        bad.append("executor entrypoint is not cleared")
    command = r["command"]
    if KILL_SHIM not in command:
        bad.append("bash-builtin kill shim is missing")
        return bad
    if CHMOD not in command:
        bad.append("kill shim is written without chmod 755")
    if CHMOD in command and command.index(CHMOD) > command.index("vllm-srun serve"):
        bad.append("kill shim is written after the serve line starts")
    return bad


def suppression_violations(r: dict) -> list[str]:
    defaults, command = r["defaults"], r["command"]
    bad: list[str] = []
    if "served_model_name" not in defaults:
        bad.append("no served_model_name key to suppress sparkrun's append")
    elif defaults["served_model_name"] != "":
        bad.append(
            f"served_model_name is {defaults['served_model_name']!r}, not empty: "
            "sparkrun appends --served-model-name and the server's argparse exits"
        )
    if "{served_model_name}" not in command:
        bad.append("command never references {served_model_name}: inert default")
    if "--served-model-name" in command:
        bad.append("command spells --served-model-name itself")
    return bad


def jev_violations(r: dict) -> list[str]:
    bad: list[str] = []
    for key in ("min_nodes", "max_nodes"):
        if r["top"].get(key) != "1":
            bad.append(f"{key} is {r['top'].get(key)!r}, JEV-27B is solo")
    if "--logprobs-mode processed_logprobs" not in r["command"]:
        bad.append("command does not run --logprobs-mode processed_logprobs")
    if "--device cpu" in r["command"] or "taskset" in r["command"]:
        bad.append("GPU arm runs a CPU execution path")
    return bad


def cpu_violations(r: dict) -> list[str]:
    bad: list[str] = []
    if "gpu_memory_utilization" in r["defaults"]:
        bad.append("CPU arm declares gpu_memory_utilization")
    if "--gpu-memory-utilization" in r["command"]:
        bad.append("CPU arm passes --gpu-memory-utilization")
    return bad


def gpu_violations(r: dict) -> list[str]:
    defaults, command = r["defaults"], r["command"]
    bad: list[str] = []
    if "vllm serve" not in command:
        bad.append("GPU arm does not run vllm serve")
    if "gpu_memory_utilization" in defaults:
        if "{gpu_memory_utilization}" not in command:
            bad.append("declared gpu_memory_utilization is inert")
    elif not (defaults.get("max_model_len") == "32768"
              and "--max-model-len {max_model_len}" in command):
        bad.append(
            "no gpu_memory_utilization and no consumed max_model_len bound: "
            "GPU residency is not deliberate"
        )
    return bad


# ---------------------------------------------------------------------------


class LaneArms(unittest.TestCase):
    def test_lane_has_the_six_arms(self):
        for name in ARMS:
            self.assertTrue((DECISION / name).is_file(), name)

    def test_every_arm_parses_non_empty(self):
        for name in ARMS:
            with self.subTest(arm=name):
                r = arm(name)
                self.assertTrue(r["top"])
                self.assertTrue(r["defaults"])
                self.assertTrue(r["command"])

    def test_empty_parse_raises(self):
        for raw in ("", "# comment only\n", "model: x\n"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_text(raw)


class ContentIdentity(unittest.TestCase):
    def test_revision_is_a_full_sha(self):
        for name in ARMS:
            with self.subTest(arm=name):
                self.assertEqual(revision_violations(arm(name)), [])

    def test_container_is_digest_pinned(self):
        for name in ARMS:
            with self.subTest(arm=name):
                self.assertEqual(digest_violations(arm(name)), [])

    def test_every_defaults_key_is_consumed(self):
        for name in ARMS:
            with self.subTest(arm=name):
                self.assertEqual(unconsumed(arm(name)), [])

    def test_command_consumes_the_pinned_model(self):
        for name in ARMS:
            if name == KOKORO:
                continue  # the model set is baked into the image; see below
            with self.subTest(arm=name):
                self.assertEqual(model_consumption_violations(arm(name)), [])

    def test_no_sibling_repo_id_in_the_command(self):
        for name in ARMS:
            with self.subTest(arm=name):
                self.assertEqual(foreign_repo_violations(arm(name)), [])

    def test_kokoro_identity_is_the_baked_image(self):
        r = arm(KOKORO)
        self.assertNotIn("{model}", r["command"])
        self.assertIn("/kokoro-fastapi-cpu@sha256:", r["top"]["container"])


class VllmSrunShim(unittest.TestCase):
    def test_new_arms_hold_the_shim(self):
        for name in SRUN_ARMS:
            with self.subTest(arm=name):
                self.assertEqual(shim_violations(arm(name)), [])

    def test_shim_is_the_one_the_shipped_siblings_carry(self):
        for name in SHIPPED_SRUN:
            with self.subTest(arm=name):
                self.assertEqual(shim_violations(arm(name)), [])


class ServedModelNameSuppressed(unittest.TestCase):
    def test_suppression_arms_hold(self):
        for name in SUPPRESS_ARMS:
            with self.subTest(arm=name):
                self.assertEqual(suppression_violations(arm(name)), [])


class JevIsSoloAndScoresCompletions(unittest.TestCase):
    def test_jev_holds(self):
        self.assertEqual(jev_violations(arm(JEV)), [])


class CpuOrGpuIsExplicit(unittest.TestCase):
    def test_cpu_arms_declare_no_gpu_memory(self):
        for name in CPU_ARMS:
            with self.subTest(arm=name):
                self.assertEqual(cpu_violations(arm(name)), [])

    def test_gpu_arm_bounds_gpu_residency(self):
        self.assertEqual(gpu_violations(arm(JEV)), [])


# ---------------------------------------------------------------------------
# Negative controls: each guard above must reject the mutation it exists for.
# Every mutation is applied to the REAL recipe text.
# ---------------------------------------------------------------------------

def mutate(raw: str, old: str, new: str) -> str:
    if old not in raw:
        raise AssertionError(f"mutation target not found in recipe text: {old!r}")
    return raw.replace(old, new, 1)


class NegativeControls(unittest.TestCase):
    def test_dropped_revision_fails_the_pin_guard(self):
        raw = (DECISION / JEV).read_text(encoding="utf-8")
        raw = re.sub(r"(?m)^model_revision:.*\n", "", raw)
        self.assertTrue(revision_violations(parse_text(raw)))

    def test_unquoted_digest_fails_the_container_guard(self):
        raw = (DECISION / "laya-decision-serve.yaml").read_text(encoding="utf-8")
        raw = mutate(raw, "@sha256:", ":sha256:")
        self.assertTrue(digest_violations(parse_text(raw)))

    def test_missing_user_fails_the_shim_guard(self):
        raw = (DECISION / SRUN_ARMS[0]).read_text(encoding="utf-8")
        raw = re.sub(r'(?m)^  user: "root"\n', "", raw)
        self.assertIn("executor user is None, not 'root'",
                      shim_violations(parse_text(raw)))

    def test_removed_kill_shim_fails_the_shim_guard(self):
        raw = (DECISION / SRUN_ARMS[0]).read_text(encoding="utf-8")
        raw = mutate(raw, KILL_SHIM + "\n  && ", "")
        self.assertIn("bash-builtin kill shim is missing",
                      shim_violations(parse_text(raw)))

    def test_uncleared_entrypoint_fails_the_shim_guard(self):
        raw = (DECISION / SRUN_ARMS[0]).read_text(encoding="utf-8")
        raw = mutate(raw, '  entrypoint: ""', "  entrypoint: /router")
        self.assertTrue(shim_violations(parse_text(raw)))

    def test_non_empty_served_model_name_fails_the_suppression_guard(self):
        # The mutation the comment beside the empty key warns about.
        raw = (DECISION / "kev-0.8b-decision-serve.yaml").read_text(encoding="utf-8")
        raw = mutate(raw, '  served_model_name: ""',
                     "  served_model_name: jaredpalmer/kev-0.8b")
        self.assertIn("not empty", " ".join(suppression_violations(parse_text(raw))))

    def test_two_node_jev_fails_the_solo_guard(self):
        raw = (DECISION / JEV).read_text(encoding="utf-8")
        raw = mutate(raw, "min_nodes: 1", "min_nodes: 2")
        self.assertIn("min_nodes is '2', JEV-27B is solo",
                      jev_violations(parse_text(raw)))

    def test_missing_logprobs_mode_fails_the_jev_guard(self):
        raw = (DECISION / JEV).read_text(encoding="utf-8")
        raw = mutate(raw, "\n  --logprobs-mode processed_logprobs", "")
        self.assertIn("--logprobs-mode processed_logprobs",
                      " ".join(jev_violations(parse_text(raw))))

    def test_gpu_memory_on_a_cpu_arm_fails_the_cpu_guard(self):
        raw = (DECISION / "laya-decision-serve.yaml").read_text(encoding="utf-8")
        raw = mutate(raw, "  served_model_name:", "  gpu_memory_utilization: 0.5\n"
                                                 "  served_model_name:")
        self.assertIn("CPU arm declares gpu_memory_utilization",
                      cpu_violations(parse_text(raw)))

    def test_unbounded_gpu_arm_fails_the_gpu_guard(self):
        raw = (DECISION / JEV).read_text(encoding="utf-8")
        raw = mutate(raw, "  max_model_len: 32768", "  max_model_len: 262144")
        self.assertIn("GPU residency is not deliberate",
                      " ".join(gpu_violations(parse_text(raw))))

    def test_unreferenced_default_fails_the_consumed_guard(self):
        raw = (DECISION / JEV).read_text(encoding="utf-8")
        raw = mutate(raw, "  --port {port}\n", "")
        self.assertIn("port", unconsumed(parse_text(raw)))

    def test_sibling_model_fails_the_identity_and_foreign_id_guards(self):
        raw = (DECISION / SRUN_ARMS[0]).read_text(encoding="utf-8")
        raw = mutate(raw, "model: vllm-sr/Decision-2.0-Nox-4B",
                     "model: vllm-sr/Decision-2.0-Sol-2B")
        r = parse_text(raw)
        self.assertTrue(model_consumption_violations(r))
        self.assertEqual(foreign_repo_violations(r), ["vllm-sr/Decision-2.0-Nox-4B"])


if __name__ == "__main__":
    unittest.main()
