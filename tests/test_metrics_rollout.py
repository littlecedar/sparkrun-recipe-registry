"""Guards for the shipped-recipe metrics rollout (owner decision 2026-11-08).

Every shipped recipe must either request the non-spammy metrics set for its
engine, or be a structural case whose surface is unconditional (tensorfold,
vLLM-Omni), or declare ``metadata.instrumented: false`` and carry no metric
flag at all.  The last rule is the contradiction check: a declared baseline
that also sets the flag is a recipe whose numbers have no provenance.

Why these exist.  A metrics boot is an *instrumented* boot: it may be compared
only with another instrumented boot of the identical recipe, never with the
pre-rollout baselines (`benchmarking/instr-cps4096-vs-2048-k16.yaml:29-35`).
Enabling the flag on a recipe is therefore a measurement decision, and the
family sets are the machine-readable form of the decision:

* sglang engine: ``--enable-metrics`` (``/metrics`` on the API port,
  ``srt/entrypoints/http_server.py:301-304`` in every pinned tree) plus
  ``--enable-cache-report`` (cached tokens in ``usage``).
* sglang ds4 overlay: the same flags ride ``env.EXTRA_SGLANG_ARGS`` because the
  launcher builds the engine argv itself (``recipes/ds4/README.md`` §"Run it";
  the marlin arm proves the path).
* vLLM ``vllm serve``: ``--enable-force-include-usage``,
  ``--enable-prompt-tokens-details``, ``--enable-per-request-metrics`` — all
  response-body fields, all default False; the Prometheus endpoint itself is
  unconditional and needs no flag.
* llama.cpp: ``--metrics`` (endpoint only).

Text parsing, never PyYAML, so the guard survives a sparkrun upgrade and runs
anywhere.  Whole-line comments are stripped before matching (AGENTS.md
§"Recipe comments"), and the omission of a flag from a *comment* is not a pass.
Every predicate takes TEXT so a negative control can feed it a mutated copy of
a real recipe; an empty parse raises rather than passing vacuously.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPE_GLOB = "recipes/*/*.yaml"

#: Families whose sweep has not landed yet (owner-approved staged rollout,
#: 2026-11-08).  Each family commit removes its own key; the last sweep commit
#: deletes this constant, after which every completeness assertion is armed.
#: Kept explicit rather than inferred from the tree: a half-swept family must
#: not read as complete because its flags happen to exist somewhere.
UNSWEPT = frozenset({"llama-cpp"})

SGLANG_FLAGS = ("--enable-metrics", "--enable-cache-report")
VLLM_FLAGS = (
    "--enable-force-include-usage",
    "--enable-prompt-tokens-details",
    "--enable-per-request-metrics",
)
LLAMA_FLAGS = ("--metrics",)

ENGINE_MARKERS = {
    "sglang": "sglang serve",
    "vllm": "vllm serve",
    "llama-cpp": "llama-server",
}

_NESTED_SECTIONS = {"metadata", "defaults", "env"}
_BLOCK_CHARS = (">", "|")


# ---------------------------------------------------------------------------
# Parsing.  Understands the YAML the shipped recipes use: top-level scalars,
# one-level mappings (``metadata:`` / ``defaults:`` / ``env:``), folded or
# literal blocks, and single-line quoted values.  Raises on an empty parse.
# ---------------------------------------------------------------------------

def strip_comments(text: str) -> str:
    """Drop whole-line comments; AGENTS.md says guards strip them before matching."""
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def parse_text(raw: str) -> dict[str, Any]:
    """Return {top, metadata, defaults, env, command}; empty parse raises."""
    lines = strip_comments(raw).splitlines()
    top: dict[str, str] = {}
    sections: dict[str, dict[str, str]] = {name: {} for name in _NESTED_SECTIONS}
    command: list[str] = []
    section: str | None = None
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if _indent(line) == 0:
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip()
            if value.startswith(_BLOCK_CHARS):
                section = "command" if key == "command" else None
                i += 1
                while i < len(lines) and (not lines[i].strip() or _indent(lines[i]) > 0):
                    if lines[i].strip():
                        command.append(lines[i].strip())
                    i += 1
                continue
            section = key if key in _NESTED_SECTIONS else None
            if value:
                top[key] = _unquote(value)
            i += 1
            continue
        # Indented line: belongs to the open nested section, or a folded value.
        if section in _NESTED_SECTIONS:
            key, _, value = line.strip().partition(":")
            key, value = key.strip(), value.strip()
            key_indent = _indent(line)
            if value.startswith(_BLOCK_CHARS):
                parts: list[str] = []
                i += 1
                while i < len(lines):
                    nxt = lines[i]
                    if nxt.strip() and _indent(nxt) <= key_indent:
                        break
                    if nxt.strip():
                        parts.append(nxt.strip())
                    i += 1
                sections[section][key] = " ".join(parts)
                continue
            if value:
                sections[section][key] = _unquote(value)
        i += 1
    if not top:
        raise ValueError("recipe text did not parse: no top-level keys")
    return {
        "top": top,
        "metadata": sections["metadata"],
        "defaults": sections["defaults"],
        "env": sections["env"],
        "command": " ".join(command).strip(),
    }


def parse(path: Path) -> dict[str, Any]:
    return parse_text(path.read_text(encoding="utf-8"))


def shipped_recipes() -> list[Path]:
    paths = sorted(REPO_ROOT.glob(RECIPE_GLOB))
    if not paths:
        raise ValueError(f"no recipes found under {RECIPE_GLOB}")
    return paths


# ---------------------------------------------------------------------------
# Predicates.  Every one takes recipe TEXT (or a parsed recipe) so the
# negative controls can mutate a real recipe in memory.
# ---------------------------------------------------------------------------

def runtime_of(recipe: dict[str, Any]) -> str:
    declared = recipe["top"].get("runtime", "")
    if declared:
        return declared
    # The one recipe that omits `runtime:` infers it from the command hint.
    for runtime, marker in ENGINE_MARKERS.items():
        if marker in recipe["command"]:
            return runtime
    raise ValueError("recipe declares no runtime and the command names no engine")


def shape_of(recipe: dict[str, Any]) -> str:
    """engine / overlay / tensorfold / omni / script."""
    command = recipe["command"]
    if "tensorfold" in command:
        return "tensorfold"
    if "vllm-omni" in command:
        return "omni"
    if "dsv41-sglang-overlay" in command:
        return "overlay"
    for marker in ENGINE_MARKERS.values():
        if marker in command:
            return "engine"
    return "script"


def metric_text(recipe: dict[str, Any]) -> str:
    """Every carrier a metric flag can reach the engine through."""
    return " ".join(
        (
            recipe["command"],
            recipe["defaults"].get("extra_args", ""),
            recipe["env"].get("EXTRA_SGLANG_ARGS", ""),
        )
    )


def declared_uninstrumented(recipe: dict[str, Any]) -> bool:
    value = recipe["metadata"].get("instrumented", "").strip().lower()
    return value in {"false", "no", "0", "off"}


def violations(recipe: dict[str, Any]) -> list[str]:
    """Reasons this recipe breaks the rollout contract; empty means compliant."""
    text = metric_text(recipe)
    problems: list[str] = []
    if declared_uninstrumented(recipe):
        present = [flag for flag in (*SGLANG_FLAGS, *VLLM_FLAGS, *LLAMA_FLAGS) if flag in text]
        if present:
            problems.append(
                "declares metadata.instrumented: false but carries "
                + ", ".join(present)
            )
        return problems
    runtime = runtime_of(recipe)
    shape = shape_of(recipe)
    if shape == "tensorfold":
        if recipe["env"].get("TF_METRICS_BRIDGE", "").strip().lower() in {"0", "false", "off"}:
            problems.append("tensorfold bridge disabled: /metrics is the only surface")
        return problems
    if shape == "omni":
        if recipe["env"].get("OMNI_METRICS_BRIDGE", "").strip().lower() in {"0", "false", "off"}:
            problems.append("vllm-omni bridge disabled: /metrics is the only surface")
        return problems
    if runtime == "sglang":
        required = SGLANG_FLAGS
        if shape == "overlay":
            required = ("--enable-metrics",)
    elif runtime == "vllm":
        required = VLLM_FLAGS
    elif runtime == "llama-cpp":
        required = LLAMA_FLAGS
    else:
        problems.append(f"unexpected runtime {runtime!r}")
        return problems
    if shape != "engine" and shape != "overlay":
        return problems
    missing = [flag for flag in required if flag not in text]
    if missing:
        problems.append("missing " + ", ".join(missing))
    return problems


def family_recipes(runtime: str, shape: str | None = None) -> Iterator[tuple[Path, dict[str, Any]]]:
    for path in shipped_recipes():
        recipe = parse(path)
        if runtime_of(recipe) != runtime:
            continue
        if shape is not None and shape_of(recipe) != shape:
            continue
        yield path, recipe


# ---------------------------------------------------------------------------
# Guards.
# ---------------------------------------------------------------------------

class ParseCoverage(unittest.TestCase):
    def test_every_shipped_recipe_parses_and_names_a_runtime(self):
        recipes = shipped_recipes()
        self.assertGreater(len(recipes), 100, "the recipe glob found almost nothing")
        for path in recipes:
            with self.subTest(recipe=path.name):
                recipe = parse(path)
                self.assertIn(runtime_of(recipe), {"sglang", "vllm", "llama-cpp"})
                self.assertTrue(recipe["command"], "recipe has no command block")

    def test_a_comment_naming_the_flag_is_not_a_pass(self):
        text = (
            "runtime: sglang\n"
            "# this arm used to pass --enable-metrics --enable-cache-report\n"
            "command: >\n"
            "  sglang serve --model-path {model}\n"
        )
        self.assertTrue(violations(parse_text(text)))


class SglangEngineMetrics(unittest.TestCase):
    def test_every_sglang_engine_recipe_requests_the_metrics_set(self):
        if "sglang-engine" in UNSWEPT:
            return
        paths = [p for p, _ in family_recipes("sglang", "engine")]
        self.assertTrue(paths, "no sglang engine recipes found")
        for path, recipe in family_recipes("sglang", "engine"):
            with self.subTest(recipe=path.name):
                self.assertEqual(violations(recipe), [], f"{path}: {violations(recipe)}")


class SglangOverlayMetrics(unittest.TestCase):
    def test_every_ds4_overlay_recipe_passes_metrics_through_env(self):
        if "sglang-overlay" in UNSWEPT:
            return
        paths = [p for p, _ in family_recipes("sglang", "overlay")]
        self.assertTrue(paths, "no ds4 overlay recipes found")
        for path, recipe in family_recipes("sglang", "overlay"):
            with self.subTest(recipe=path.name):
                self.assertEqual(violations(recipe), [], f"{path}: {violations(recipe)}")


class VllmMetrics(unittest.TestCase):
    def test_every_vllm_serve_recipe_requests_the_usage_and_metrics_set(self):
        if "vllm" in UNSWEPT:
            return
        paths = [p for p, _ in family_recipes("vllm", "engine")]
        self.assertTrue(paths, "no vllm engine recipes found")
        for path, recipe in family_recipes("vllm", "engine"):
            with self.subTest(recipe=path.name):
                self.assertEqual(violations(recipe), [], f"{path}: {violations(recipe)}")


class LlamaCppMetrics(unittest.TestCase):
    def test_every_llamacpp_recipe_requests_metrics(self):
        if "llama-cpp" in UNSWEPT:
            return
        paths = [p for p, _ in family_recipes("llama-cpp")]
        self.assertTrue(paths, "no llama-cpp recipes found")
        for path, recipe in family_recipes("llama-cpp"):
            with self.subTest(recipe=path.name):
                self.assertEqual(violations(recipe), [], f"{path}: {violations(recipe)}")


class StructuralSurfaces(unittest.TestCase):
    """Unconditional surfaces are asserted, not exempted silently."""

    def test_tensorfold_and_omni_arms_keep_their_unconditional_surface(self):
        seen = {"tensorfold": 0, "omni": 0}
        for path in shipped_recipes():
            recipe = parse(path)
            shape = shape_of(recipe)
            if shape not in seen:
                continue
            seen[shape] += 1
            with self.subTest(recipe=path.name):
                self.assertEqual(violations(recipe), [], f"{path}: {violations(recipe)}")
        self.assertGreater(seen["tensorfold"], 0, "the tensorfold arms vanished")


class DeclaredBaselines(unittest.TestCase):
    def test_a_declared_baseline_carries_no_metric_flag(self):
        declared = [(p, r) for p in shipped_recipes() for r in [parse(p)]
                    if declared_uninstrumented(r)]
        self.assertTrue(declared, "the rollout's declared baselines are missing")
        for path, recipe in declared:
            with self.subTest(recipe=path.name):
                self.assertEqual(violations(recipe), [], f"{path}: {violations(recipe)}")


class NegativeControls(unittest.TestCase):
    """Each control proves the predicate fires on the shape it claims to catch."""

    SGLANG: str = (
        "runtime: sglang\n"
        "command: >\n"
        "  sglang serve --model-path {model}\n"
        "  --enable-metrics\n"
        "  --enable-cache-report\n"
    )
    OVERLAY: str = (
        "runtime: sglang\n"
        "env:\n"
        '  EXTRA_SGLANG_ARGS: "--enable-metrics"\n'
        "command: >\n"
        "  python3 /workspace/mods/dsv41-sglang-overlay/launcher.py --boot\n"
    )
    TENSORFOLD: str = (
        "runtime: sglang\n"
        "env:\n"
        '  TF_METRICS_BRIDGE: "1"\n'
        "command: >\n"
        "  python3 /workspace/mods/tensorfold-glm-exl3-launcher/launcher.py\n"
    )
    VLLM: str = (
        "runtime: vllm\n"
        "command: >\n"
        "  vllm serve {model}\n"
        "  --enable-force-include-usage\n"
        "  --enable-prompt-tokens-details\n"
        "  --enable-per-request-metrics\n"
    )
    LLAMA: str = (
        "runtime: llama-cpp\n"
        "command: >\n"
        "  llama-server -m {model}\n"
        "  --metrics\n"
    )

    def test_the_compliant_fixtures_are_clean(self):
        for text in (self.SGLANG, self.OVERLAY, self.TENSORFOLD, self.VLLM, self.LLAMA):
            self.assertEqual(violations(parse_text(text)), [])

    def test_a_recipe_without_the_flags_is_reported(self):
        without = self.SGLANG.replace("  --enable-metrics\n", "").replace(
            "  --enable-cache-report\n", "")
        self.assertIn("missing", " ".join(violations(parse_text(without))))

    def test_an_instrumented_false_recipe_carrying_the_flag_is_a_contradiction(self):
        text = self.SGLANG.replace(
            "runtime: sglang\n", "runtime: sglang\nmetadata:\n  instrumented: false\n")
        self.assertIn("instrumented: false", " ".join(violations(parse_text(text))))

    def test_an_overlay_with_the_env_value_emptied_is_reported(self):
        text = self.OVERLAY.replace('EXTRA_SGLANG_ARGS: "--enable-metrics"',
                                    'EXTRA_SGLANG_ARGS: ""')
        self.assertIn("--enable-metrics", " ".join(violations(parse_text(text))))

    def test_a_tensorfold_arm_with_its_bridge_disabled_is_reported(self):
        text = self.TENSORFOLD.replace('TF_METRICS_BRIDGE: "1"',
                                       'TF_METRICS_BRIDGE: "0"')
        self.assertIn("tensorfold bridge disabled", " ".join(violations(parse_text(text))))


if __name__ == "__main__":
    unittest.main()
