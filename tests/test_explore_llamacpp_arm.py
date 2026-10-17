"""Guard for the registry's first llama.cpp arm (explore lane).

Run:
    python3 -m unittest discover -s tests -v

Stdlib-only, recipe parsed as TEXT (see AGENTS.md: tests/ never gains a
dependency). The repo-wide rules for this recipe live in
`tests/test_recipe_placeholder_resolution.py` (inert defaults, served-name
rebinding); this module owns what is specific to `runtime: llama-cpp`.

Why this one exists. `mellum2.1-12b-a2.5b-q4km-thinking-llamacpp.yaml` is the
first arm on a runtime the registry has never shipped, so nothing else in the
suite would notice these failures, and each one is silent until the boot:

  * `container:` omitted or tag-only ...... sparkrun's GB10 tier maps
      `llama-cpp -> scitrera/dgx-spark-llama-cpp:latest` (platforms/dgx_spark.py)
      and that tag is retagged per build (458 tags); the arm's whole premise is
      that a *named build* (llama.cpp 0.1.2-dev commit b2e5e9b) is pinned, so
      both the tag and the digest are load-bearing.
  * `model:` without `:Q4_K_M` ........... sparkrun's GGUF path errors on a repo
      whose files do not identify exactly one model; the repo has five quants.
  * `--kv-unified` dropped ................ with an explicit `--parallel N` the
      engine's default flips to *divided* slots, so c1 would no longer see the
      full `--ctx-size` and the C2/C5/C10 cells would mean something else than
      the boot they were measured on.
  * `--alias {model}` ..................... sparkrun rebinds `{model}` to the
      staged GGUF path on a launch (models/runtime.py::bind_runtime_models), so
      the served id would be the cache path, not the repo id.

Every guard has a negative control in NegativeControls; controls mutate strings
in memory and touch nothing on disk.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPE = (REPO_ROOT / "recipes" / "explore"
          / "mellum2.1-12b-a2.5b-q4km-thinking-llamacpp.yaml")

# The GGUF sibling of the lane's bf16 arm. Revision read from the Hub 2026-10-16
# (attic/explore/MELLUM-21.md §5); `general.architecture = mellum` re-verified by
# a Range-read of the Q4_K_M header 2026-10-17 (mad-science/LLAMACPP-GGUF.md §2).
MODEL = "JetBrains/Mellum2.1-12B-A2.5B-Thinking-GGUF"
QUANT = "Q4_K_M"
MODEL_REVISION = "20b439426f1e997ba575eaccaf4856ac0f76f5d5"

# Tag AND digest: `b10549-cu131` is what the digest contains, `:latest` is the
# same bytes today and not tomorrow.
CONTAINER = ("scitrera/dgx-spark-llama-cpp:b10549-cu131"
             "@sha256:ad14055470c2bd5c2b4c088dc5727d950da00f62408f438f4f3833c704af0dca")
SERVED_ID = MODEL

_COMMENT_LINE = re.compile(r"(?m)^\s*#.*$")


def strip_comment_lines(text: str) -> str:
    """Drop whole-line `#` comments so prose quoting a flag is inert."""
    return _COMMENT_LINE.sub("", text)


def top_level(text: str, key: str) -> str | None:
    match = re.search(r"^%s: *(.*)$" % re.escape(key), text, re.M)
    return match.group(1).strip() if match else None


def command_block(text: str) -> str:
    match = re.search(r"^command: *>(?:\n(.*?))?(?=^[a-z0-9_]+:|\Z)", text, re.M | re.S)
    return (match.group(1) or "") if match else ""


def defaults_keys(text: str) -> dict[str, str]:
    block = re.search(r"^defaults:\n((?:  .*\n|\n)*)", text, re.M)
    return dict(re.findall(r"^  ([a-z0-9_]+): *(.*)$", block.group(1), re.M)) if block else {}


class LlamaCppArm(unittest.TestCase):
    """The arm ships a runtime the registry has not exercised before."""

    @classmethod
    def setUpClass(cls):
        cls.raw = RECIPE.read_text(encoding="utf-8")
        cls.text = strip_comment_lines(cls.raw)
        cls.command = command_block(cls.text)
        cls.keys = defaults_keys(cls.text)

    def test_recipe_exists_and_is_pinned(self):
        self.assertTrue(RECIPE.is_file(), RECIPE)
        self.assertEqual(top_level(self.text, "model"), "%s:%s" % (MODEL, QUANT))
        self.assertEqual(top_level(self.text, "model_revision"), MODEL_REVISION)
        self.assertRegex(MODEL_REVISION, r"^[0-9a-f]{40}$")

    def test_command_is_the_llamacpp_engine(self):
        self.assertEqual(top_level(self.text, "runtime"), "llama-cpp")
        self.assertRegex(self.command, r"(?m)^\s*llama-server -hf \{model\}$")
        self.assertNotIn("vllm serve", self.command)
        self.assertNotIn("sglang serve", self.command)

    def test_container_pins_tag_and_digest(self):
        self.assertEqual(top_level(self.text, "container"), CONTAINER)
        self.assertNotIn(":latest", top_level(self.text, "container") or "")

    def test_quant_selects_a_file_and_selection_is_not_narrowed(self):
        model = top_level(self.text, "model") or ""
        self.assertRegex(model, r":Q[0-9]_K_M$", "the :quant suffix is what picks the file")
        self.assertNotIn("model_file_selection", self.text,
                         "sparkrun errors on GGUF when file selection is set")

    def test_kv_unified_survives_the_explicit_parallel(self):
        self.assertRegex(self.keys.get("parallel", ""), r"^[0-9]+$")
        self.assertIn("--kv-unified", self.command)

    def test_flag_map_keys_are_literals_not_defaults(self):
        # The template path never runs the runtime's flag map (see
        # tests/test_recipe_placeholder_resolution.py ::InertDefaults
        # .test_flag_map_keys_are_inert_in_a_template_recipe), so anything the
        # engine needs must be named in the command itself.
        for key in ("jinja", "webui", "mmap", "cont_batching", "no_webui"):
            self.assertNotIn(key, self.keys, "%s must be a literal, not a defaults key" % key)
        for flag in ("--jinja", "--no-webui", "--no-mmap", "--cont-batching"):
            self.assertIn(flag, self.command)

    def test_served_id_is_a_literal_rendered_from_its_own_key(self):
        self.assertEqual(self.keys.get("served_model_name"), SERVED_ID)
        self.assertIn("--alias {served_model_name}", self.command)
        self.assertNotIn("--alias {model}", self.command)


class NegativeControls(unittest.TestCase):
    """Each guard above must fail on the mutation it exists for."""

    def setUp(self):
        self.text = strip_comment_lines(RECIPE.read_text(encoding="utf-8"))

    def test_tag_only_pin_would_pass_the_digest_guard(self):
        stripped = re.sub(r"@sha256:[0-9a-f]{64}", "", self.text)
        self.assertNotEqual(top_level(stripped, "container"), CONTAINER)

    def test_quantless_model_would_pass_the_file_selection_guard(self):
        quantless = self.text.replace("%s:%s" % (MODEL, QUANT), MODEL)
        self.assertNotRegex(top_level(quantless, "model") or "", r":Q[0-9]_K_M$")

    def test_dropped_kv_unified_would_pass_the_slot_guard(self):
        without = command_block(self.text).replace("--kv-unified", "")
        self.assertNotIn("--kv-unified", without)

    def test_default_named_flag_would_pass_the_literal_guard(self):
        with_default = self.text.replace("  top_k: 20\n", "  top_k: 20\n  jinja: true\n", 1)
        self.assertIn("jinja", defaults_keys(with_default))

    def test_dropped_no_mmap_would_pass_the_literal_guard(self):
        without = command_block(self.text).replace("--no-mmap", "")
        self.assertNotIn("--no-mmap", without)

    def test_served_name_from_model_would_pass_the_rebinding_guard(self):
        rebound = command_block(self.text).replace("--alias {served_model_name}",
                                                   "--alias {model}")
        self.assertIn("--alias {model}", rebound)

    def test_comment_lines_do_not_count_as_command_text(self):
        self.assertNotIn("--kv-unified", strip_comment_lines("# --kv-unified\n"))


if __name__ == "__main__":
    unittest.main()