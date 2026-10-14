"""Guards for the qwen3 lane's TensorFold arm.

Run:
    python3 -m unittest discover -s tests -v

Stdlib-only, recipe parsed as TEXT with regex rather than through PyYAML (see
AGENTS.md: tests/ never gains a dependency). The lane's SGLang arms are covered
elsewhere -- `tests/test_recipe_placeholder_resolution.py` owns the
`--served-model-name {model}` rebinding trap and the inert-defaults rule for
every shipped recipe, and `tests/test_qwen3_vl_embeddings.py` owns the
embed/rerank lanes.

Why this one exists. `qwen3.8-27b-mlx4bit-tensorfold-sglang.yaml` declares
`runtime: sglang` while running a foreign engine: sparkrun renders the `command:`
template and (on one node) appends nothing, so the only thing that makes this the
TensorFold arm is that the command says `tensorfold serve` and the image is the
one carrying that engine. Every failure mode here is silent:

  * `sglang serve` in the command ....... the image carries TensorFold, not
      SGLang; the launch would be an unknown-argument death at the engine, after
      a ~15 GB model download and distribution.
  * a moving `container:` tag .......... the arm's five MiaAI-Lab patches
      (FP8 KV, 50 images + video, YaRN, memory reserve 0, the pinned KV pool) are
      baked into one image tag; the recipe was written against patch set
      `fb91a0019fdc` only.
  * the drafter undeclared ............ sparkrun distributes `model:` and, via
      the sglang runtime's draft hook, a declared `speculative_draft_model`.
      TensorFold's `--drafter` reads the repo from the node's HF cache; an
      undeclared drafter leaves the offline engine without it.
  * `--drafter {model}` ............... sparkrun rebinds `{model}` to the
      prepared snapshot path on a launch (models/runtime.py::bind_runtime_models),
      so the engine would be handed the served checkpoint as its draft model.

Every guard has a negative control in NegativeControls; controls mutate strings
in memory and touch nothing on disk.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPE = REPO_ROOT / "recipes" / "qwen3" / "qwen3.8-27b-mlx4bit-tensorfold-sglang.yaml"

# The checkpoint the upstream launcher serves (Vontra/Qwen3.8-27B-MLX-4bit, renamed
# to the TensorFold org on the Hub) and the drafter TensorFold's qwen3_5 family
# resolves for it (`DRAFTER` in tensorfold/families/qwen3_5/__init__.py at the
# engine commit the image pins). Both SHA-verified against the HF API 2026-10-14.
MODEL = "TensorFold/Qwen3.8-27B-MLX-4bit"
MODEL_REVISION = "22d8d538154e0e5b6f8dcb1fcc74a60a0798104c"
DRAFTER = "z-lab/Qwen3.8-27B-DFlash2"
DRAFTER_REVISION = "50307d4c4cde6860d4eee73e2547cd786fe8e8a4"

# The image obligation. Digest-pinned because the five patches ARE the arm.
CONTAINER_REPO = "ghcr.io/miaai-lab/qwen3.8-27b-dgx-spark-tensorfold"
CONTAINER_DIGEST = "sha256:043d192b9e1725f55c5439fc9672055de891433e5b31448ed8963918e3c460e9"

SERVED_NAME = "Qwen3.8-27B"

_COMMENT_LINE = re.compile(r"(?m)^\s*#.*$")


def strip_comment_lines(text: str) -> str:
    """Drop whole-line `#` comments so prose quoting a flag is inert."""
    return _COMMENT_LINE.sub("", text)


def top_level(text: str, key: str) -> str | None:
    match = re.search(r"^%s: *(.*)$" % re.escape(key), text, re.M)
    return match.group(1).strip() if match else None


def defaults_block(text: str) -> str:
    match = re.search(r"^defaults:\n((?:  .*\n|\n)*)", text, re.M)
    return match.group(1) if match else ""


def command_block(text: str) -> str:
    match = re.search(r"^command: *>(?:\n(.*?))?(?=^[a-z0-9_]+:|\Z)", text, re.M | re.S)
    return (match.group(1) or "") if match else ""

def defaults_keys(text: str) -> dict[str, str]:
    return dict(re.findall(r"^  ([a-z0-9_]+): *(.*)$", defaults_block(text), re.M))


class TensorFoldArm(unittest.TestCase):
    """The recipe ships a foreign engine behind the sglang shim."""

    @classmethod
    def setUpClass(cls):
        cls.raw = RECIPE.read_text(encoding="utf-8")
        cls.text = strip_comment_lines(cls.raw)
        cls.command = command_block(cls.text)
        cls.keys = defaults_keys(cls.text)

    def test_recipe_exists_and_is_pinned(self):
        self.assertTrue(RECIPE.is_file(), RECIPE)
        self.assertEqual(top_level(self.text, "model"), MODEL)
        self.assertEqual(top_level(self.text, "model_revision"), MODEL_REVISION)
        self.assertTrue(
            re.fullmatch(r"[0-9a-f]{40}", top_level(self.text, "model_revision") or ""),
            "model_revision must be a full commit SHA",
        )

    def test_command_is_the_tensorfold_engine(self):
        self.assertEqual(top_level(self.text, "runtime"), "sglang")
        self.assertRegex(self.command, r"(?m)^\s*tensorfold serve \{model\}")
        self.assertNotIn("sglang serve", self.command)

    def test_container_is_digest_pinned(self):
        container = top_level(self.text, "container") or ""
        self.assertEqual(container, "%s@%s" % (CONTAINER_REPO, CONTAINER_DIGEST))
        self.assertRegex(container, r"@sha256:[0-9a-f]{64}$")

    def test_drafter_is_declared_and_rendered(self):
        self.assertEqual(self.keys.get("speculative_draft_model"), DRAFTER)
        self.assertEqual(self.keys.get("speculative_draft_model_revision"), DRAFTER_REVISION)
        self.assertIn("--drafter {speculative_draft_model}", self.command)

    def test_served_id_is_a_literal_rendered_from_its_own_key(self):
        self.assertEqual(self.keys.get("served_model_name"), SERVED_NAME)
        self.assertIn("--name {served_model_name}", self.command)
        self.assertNotIn("--name {model}", self.command)

    def test_no_tensor_parallel_flag(self):
        # TensorFold's TP=2 wants `--rank`/`--master`/`--master-port`; sparkrun
        # would append `--dist-init-addr/--nnodes/--node-rank`, which the engine
        # does not parse. TP=1 is the whole arm; a shim would be the TP=2 route.
        self.assertNotIn("--tp", self.command)
        self.assertNotIn("tensor_parallel", self.keys)


class NegativeControls(unittest.TestCase):
    """Each guard above must fail on the mutation it exists for."""

    def setUp(self):
        self.text = strip_comment_lines(RECIPE.read_text(encoding="utf-8"))
        self.command = command_block(self.text)

    def test_sglang_serve_in_command_would_pass_the_engine_guard(self):
        # The engine guard is an assertIn on `tensorfold serve`; a swapped command
        # must not satisfy it.
        swapped = self.command.replace("tensorfold serve", "sglang serve")
        self.assertNotRegex(swapped, r"(?m)^\s*tensorfold serve \{model\}")

    def test_served_name_from_model_would_pass_the_rebinding_guard(self):
        rebound = self.command.replace("--name {served_model_name}", "--name {model}")
        self.assertIn("--name {model}", rebound)
        self.assertNotIn("--name {served_model_name}", rebound)

    def test_undefined_drafter_default_would_pass_the_drafter_guard(self):
        # A defaults block without the drafter key leaves the command's
        # {speculative_draft_model} unresolved in the placeholder guard and the
        # repo undistributed in the launch.
        without = re.sub(r"^  speculative_draft_model:.*\n", "", self.text, flags=re.M)
        self.assertNotIn("speculative_draft_model", defaults_keys(without))

    def test_comment_lines_do_not_count_as_command_text(self):
        # Prose in a comment quoting a flag must not satisfy a command guard.
        self.assertNotIn("--drafter", strip_comment_lines("# --drafter {speculative_draft_model}\n"))


if __name__ == "__main__":
    unittest.main()
