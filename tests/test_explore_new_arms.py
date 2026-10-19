"""Guards for the eight explore arms added 2026-10-18.

Each arm is pinned by content identity, and each invariant below is silent when
broken:

  R  top-level `model_revision:` is a full 40-hex SHA. sparkrun distributes by
     that field; a tag or short SHA is a moving target.
  C  `container:` carries an `@sha256:` digest. A tag alone is replaced upstream
     without notice.
  D  every `defaults:` key reaches a `{placeholder}` in `command:`. A key with
     no placeholder is not a setting -- nothing else in the launch path reads it.
  M  the command consumes the pinned model identity through one of the three
     sanctioned forms: `{model}` (llama.cpp / sglang / mod launchers), the
     prepared snapshot path a vLLM template must hardcode
     (recipes/MECHANICS.md, "vLLM custom-command templates"), or the vllm-srun
     repo-id + `--revision=` pair its own CLI takes. Any other bare `org/name`
     in the command must be a model this arm declares -- a sibling's repo id is
     a copy-paste leak, never a setting.

Plus the lane-level invariants, each of which a sibling copy-paste breaks:

  G  the two GGUF arms declare `runtime: llama-cpp`, carry the `:quant` colon
     form on `model:`, and pin the fork image: stock llama.cpp has no `kolibri1`
     architecture at all.
  T  the TensorFold arm pins its fork digest, references the lane-local,
     UNSCOPED `mods/kolibri-drafter-launcher` (scoped, it resolves against the
     published clone, which has no lane dir), and pins the drafter repo and
     revision it hands the launcher.
  N  Laguna-M.1 is the ONLY two-node explore arm (min/max 2, TP=2); every other
     arm is 1/1/TP1. Asserted as an exception so a copy-paste cannot quietly
     make a solo arm two-node, or the two-node arm solo.
  E  all three 4-bit Kolibri arms pin the SAME vLLM 0.29.0 digest: the vendor
     plugin wheel pins vllm<0.30, so one arm drifting to another engine is
     silent at `validate` and dies at load.

Recipes are parsed as text (stdlib only, no PyYAML) by the parser the other
lane guards use; an empty parse RAISES rather than returning empty collections.
Every rule has a negative control that mutates the real recipe text.

Run:
    uv run python -B -m unittest tests.test_explore_new_arms -v
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.test_ornith_recipes import parse_text

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPLORE = REPO_ROOT / "recipes" / "explore"

ARMS = (
    "kolibri-1-nvfp4a16-fp8-vllm.yaml",
    "kolibri-1-nvfp4-experts-vllm.yaml",
    "kolibri-1-mxfp4-mxwave-vllm.yaml",
    "kolibri-1-78b-fp8-tensorfold-drafter-sglang.yaml",
    "kolibri-1-apex-q4k-llamacpp.yaml",
    "kolibri-1-apex-24bpw-llamacpp.yaml",
    "mistral-small-4-119b-nvfp4-vllm.yaml",
    "poolside-laguna-m1-nvfp4-vllm-tp2.yaml",
)

GGUF_ARMS = (
    "kolibri-1-apex-q4k-llamacpp.yaml",
    "kolibri-1-apex-24bpw-llamacpp.yaml",
)
KOLIBRI_4BIT_ARMS = (
    "kolibri-1-nvfp4a16-fp8-vllm.yaml",
    "kolibri-1-nvfp4-experts-vllm.yaml",
    "kolibri-1-mxfp4-mxwave-vllm.yaml",
)
TENSORFOLD_ARM = "kolibri-1-78b-fp8-tensorfold-drafter-sglang.yaml"
LAGUNA_M1 = "poolside-laguna-m1-nvfp4-vllm-tp2.yaml"

SHA40 = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}\b")
HUB_ID = re.compile(
    r"(?<![\w./-])([A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*)"
    r"(?![\w./-])"
)
GGUF_MODEL = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*:([A-Za-z0-9_.-]+)"
)

# Fork-built images: neither upstream project can serve these checkpoints.
LLAMACPP_IMAGE = "littlecedar/dgx-spark-llama-cpp-kolibri1"
LLAMACPP_DIGEST = "1928661c"
TENSORFOLD_IMAGE = "littlecedar/dgx-spark-tensorfold-kolibri1-drafter"
TENSORFOLD_DIGEST = "efcb7257"
# vLLM 0.29.0: the pin the aleph-alpha-inference 1.0.0 wheel allows.
VLLM_IMAGE = "vllm/vllm-openai:v0.29.0@sha256:"
VLLM_029_DIGEST = "c2914767605584b6d8f45686b82de173ecc99e781897aa3d0a66dacd72c51ae1"


def arm(name: str) -> dict:
    """Parse one arm of THIS lane; a missing file is a test failure, not a skip."""
    path = EXPLORE / name
    if not path.is_file():
        raise AssertionError(f"missing recipe: {path}")
    return parse_text(path.read_text(encoding="utf-8"))


def model_repo(r: dict) -> str:
    """The Hub repo id from `model:`, dropping llama.cpp's `:quant` suffix."""
    return r["top"]["model"].split(":", 1)[0]


# ---------------------------------------------------------------------------
# Contract predicates.  Negative controls call these same functions on mutated
# copies of the real text, so a control cannot pass by testing something else.
# ---------------------------------------------------------------------------

def revision_violations(r: dict) -> list[str]:
    rev = r["top"].get("model_revision", "")
    return [] if SHA40.match(rev) else [f"model_revision {rev!r} is not a 40-hex SHA"]


def digest_violations(r: dict) -> list[str]:
    container = r["top"].get("container", "")
    return [] if DIGEST.search(container) else [
        f"container {container!r} is not @sha256 digest-pinned"
    ]


def unconsumed(r: dict) -> list[str]:
    """Defaults keys no placeholder reads: silently not a setting."""
    return [k for k in r["defaults"] if "{" + k + "}" not in r["command"]]


def model_consumption_violations(r: dict) -> list[str]:
    cmd, repo = r["command"], model_repo(r)
    rev = r["top"].get("model_revision", "")
    snapshot = f"models--{repo.replace('/', '--')}/snapshots/{rev}"
    forms = {
        "{model}": "{model}" in cmd,
        "prepared snapshot path": snapshot in cmd,
        "vllm-srun repo id + --revision=": repo in cmd and "--revision=" + rev in cmd,
    }
    return [] if any(forms.values()) else [
        f"command consumes no pinned model form (checked {sorted(forms)})"
    ]


def foreign_repo_violations(r: dict) -> list[str]:
    """Bare `org/name` literals in the command must be this arm's own models."""
    declared = {model_repo(r)}
    for value in r["defaults"].values():
        if HUB_ID.fullmatch(value.strip()):
            declared.add(value.strip())
    found = {m.group(0) for m in HUB_ID.finditer(r["command"])}
    return sorted(found - declared)


def gguf_violations(r: dict) -> list[str]:
    bad: list[str] = []
    if r["top"].get("runtime") != "llama-cpp":
        bad.append(f"runtime {r['top'].get('runtime')!r} is not llama-cpp")
    match = GGUF_MODEL.fullmatch(r["top"].get("model", ""))
    if not match:
        bad.append(f"model {r['top'].get('model')!r} is not the <repo>:<quant> form")
    elif SHA40.match(match.group(1)):
        bad.append(f"quant {match.group(1)!r} is a revision, not a quant tag")
    if "{model}" not in r["command"]:
        bad.append("command does not hand {model} to llama-server")
    if LLAMACPP_IMAGE not in r["top"].get("container", ""):
        bad.append("container is not the fork-built llama.cpp image")
    if LLAMACPP_DIGEST not in r["top"].get("container", ""):
        bad.append("container does not pin the fork image digest")
    return bad


def drafter_violations(r: dict) -> list[str]:
    bad: list[str] = []
    container = r["top"].get("container", "")
    if TENSORFOLD_IMAGE not in container or TENSORFOLD_DIGEST not in container:
        bad.append("container is not the pinned TensorFold drafter fork")
    if r["mods"] != ["mods/kolibri-drafter-launcher"]:
        bad.append(
            f"mods {r['mods']!r} is not the lane-local unscoped "
            "'mods/kolibri-drafter-launcher'"
        )
    elif not (EXPLORE / "mods" / "kolibri-drafter-launcher").is_dir():
        bad.append("mods/kolibri-drafter-launcher does not exist beside the lane")
    defaults = r["defaults"]
    if not HUB_ID.fullmatch(defaults.get("speculative_draft_model", "")):
        bad.append("speculative_draft_model is not a Hub repo id")
    if not SHA40.match(defaults.get("speculative_draft_model_revision", "")):
        bad.append("speculative_draft_model_revision is not a 40-hex SHA")
    for flag in (
        "--drafter {speculative_draft_model}",
        "--drafter-revision {speculative_draft_model_revision}",
    ):
        if flag not in r["command"]:
            bad.append(f"command does not pass {flag!r}")
    return bad


def node_violations(name: str, r: dict) -> list[str]:
    """Laguna-M.1 is the ONE 2/2/TP2 arm; every other arm is 1/1/TP1."""
    want = "2" if name == LAGUNA_M1 else "1"
    bad: list[str] = []
    for key in ("min_nodes", "max_nodes"):
        got = r["top"].get(key)
        if got != want:
            bad.append(f"{key} is {got!r}, expected {want!r}")
    if "tensor_parallel" in r["defaults"]:
        got = r["defaults"]["tensor_parallel"]
        if got != want:
            bad.append(f"tensor_parallel is {got!r}, expected {want!r}")
    if want == "2" and "{tensor_parallel}" not in r["command"]:
        bad.append("command does not pass {tensor_parallel}")
    return bad


def kolibri_engine_violations(items) -> list[str]:
    """The three 4-bit Kolibri arms share one engine pin."""
    bad: list[str] = []
    containers = set()
    for name, r in items:
        container = r["top"].get("container", "")
        containers.add(container)
        if not container.startswith(VLLM_IMAGE) or VLLM_029_DIGEST not in container:
            bad.append(f"{name}: container is not the vLLM 0.29.0 pin")
    if len(containers) != 1:
        bad.append(f"4-bit Kolibri arms disagree on the engine: {sorted(containers)}")
    return bad


# ---------------------------------------------------------------------------


class LaneArms(unittest.TestCase):
    """The eight arms are present and each parses to the shape the guards need."""

    def test_lane_has_the_eight_arms(self):
        for name in ARMS:
            self.assertTrue((EXPLORE / name).is_file(), name)

    def test_every_arm_parses_non_empty(self):
        for name in ARMS:
            with self.subTest(arm=name):
                r = arm(name)
                self.assertTrue(r["top"], "top-level mapping parsed empty")
                self.assertTrue(r["defaults"], "defaults parsed empty")
                self.assertTrue(r["command"], "command parsed empty")

    def test_empty_or_missing_parse_raises(self):
        for raw in ("", "# only a comment\n", "\n\n", "model: x\n"):
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
            with self.subTest(arm=name):
                self.assertEqual(model_consumption_violations(arm(name)), [])

    def test_no_sibling_repo_id_in_the_command(self):
        for name in ARMS:
            with self.subTest(arm=name):
                self.assertEqual(foreign_repo_violations(arm(name)), [])


class GgufArms(unittest.TestCase):
    def test_both_gguf_arms_hold(self):
        for name in GGUF_ARMS:
            with self.subTest(arm=name):
                self.assertEqual(gguf_violations(arm(name)), [])

    def test_the_two_arms_serve_different_quants(self):
        quants = set()
        for name in GGUF_ARMS:
            match = GGUF_MODEL.fullmatch(arm(name)["top"]["model"])
            self.assertIsNotNone(match, name)
            quants.add(match.group(1))
        self.assertEqual(len(quants), 2, f"both GGUF arms serve {quants}")


class TensorFoldDrafterArm(unittest.TestCase):
    def test_drafter_arm_holds(self):
        self.assertEqual(drafter_violations(arm(TENSORFOLD_ARM)), [])

    def test_drafter_repo_is_the_learned_block_drafter(self):
        self.assertEqual(
            arm(TENSORFOLD_ARM)["defaults"]["speculative_draft_model"],
            "josch15366/Kolibri-1-block-drafter",
        )


class NodeShape(unittest.TestCase):
    def test_laguna_m1_is_the_only_two_node_arm(self):
        for name in ARMS:
            with self.subTest(arm=name):
                self.assertEqual(node_violations(name, arm(name)), [])

    def test_exactly_one_arm_is_two_node(self):
        two_node = [n for n in ARMS if arm(n)["top"]["min_nodes"] != "1"]
        self.assertEqual(two_node, [LAGUNA_M1])


class KolibriFourBitEngines(unittest.TestCase):
    def test_all_three_pin_the_same_vllm_029(self):
        items = [(n, arm(n)) for n in KOLIBRI_4BIT_ARMS]
        self.assertEqual(kolibri_engine_violations(items), [])


# ---------------------------------------------------------------------------
# Negative controls: each guard above must reject the mutation it exists for.
# Every mutation is applied to the REAL recipe text.
# ---------------------------------------------------------------------------

def mutate(raw: str, old: str, new: str) -> str:
    if old not in raw:
        raise AssertionError(f"mutation target not found in recipe text: {old!r}")
    return raw.replace(old, new, 1)


class NegativeControls(unittest.TestCase):
    def setUp(self):
        self.raw = (EXPLORE / LAGUNA_M1).read_text(encoding="utf-8")

    def test_dropped_revision_fails_the_pin_guard(self):
        raw = re.sub(r"(?m)^model_revision:.*\n", "", self.raw)
        self.assertNotIn("model_revision:", raw)
        self.assertTrue(revision_violations(parse_text(raw)))

    def test_unquoted_digest_fails_the_container_guard(self):
        raw = mutate(self.raw, "@sha256:", ":sha256:")
        self.assertTrue(digest_violations(parse_text(raw)))

    def test_solo_shape_on_the_two_node_arm_fails_the_node_guard(self):
        # The copy-paste a solo arm onto this file would make.
        raw = mutate(self.raw, "min_nodes: 2", "min_nodes: 1")
        self.assertIn("min_nodes is '1', expected '2'",
                      node_violations(LAGUNA_M1, parse_text(raw)))

    def test_second_two_node_arm_fails_the_exception_guard(self):
        solo = "kolibri-1-nvfp4a16-fp8-vllm.yaml"
        raw = (EXPLORE / solo).read_text(encoding="utf-8")
        raw = mutate(raw, "min_nodes: 1", "min_nodes: 2")
        self.assertTrue(node_violations(solo, parse_text(raw)))

    def test_unreferenced_default_fails_the_consumed_guard(self):
        raw = mutate(self.raw, "  --port {port}\n", "")
        self.assertIn("port", unconsumed(parse_text(raw)))

    def test_snapshot_path_for_a_different_model_fails_the_identity_guard(self):
        raw = mutate(self.raw, "model: poolside/Laguna-M.1-NVFP4",
                     "model: poolside/Laguna-S-2.1-NVFP4")
        self.assertTrue(model_consumption_violations(parse_text(raw)))

    def test_sibling_repo_id_in_command_fails_the_foreign_id_guard(self):
        raw = mutate(self.raw, "--enable-prefix-caching",
                     "--tokenizer mistralai/Mistral-Small-4-119B-2603-NVFP4")
        self.assertEqual(
            foreign_repo_violations(parse_text(raw)),
            ["mistralai/Mistral-Small-4-119B-2603-NVFP4"],
        )

    def test_stock_runtime_on_a_gguf_arm_fails(self):
        name = GGUF_ARMS[0]
        raw = (EXPLORE / name).read_text(encoding="utf-8")
        raw = mutate(raw, "runtime: llama-cpp", "runtime: vllm")
        self.assertTrue(gguf_violations(parse_text(raw)))

    def test_stock_llamacpp_digest_fails_the_fork_pin(self):
        name = GGUF_ARMS[0]
        raw = (EXPLORE / name).read_text(encoding="utf-8")
        raw = mutate(raw, LLAMACPP_DIGEST, "0" * 8)
        self.assertIn("container does not pin the fork image digest",
                      gguf_violations(parse_text(raw)))

    def test_quant_less_model_on_a_gguf_arm_fails(self):
        name = GGUF_ARMS[0]
        raw = (EXPLORE / name).read_text(encoding="utf-8")
        raw = mutate(raw, "model: Myric/Kolibri-1-APEX-GGUF:Q4_K",
                     "model: Myric/Kolibri-1-APEX-GGUF")
        self.assertTrue(gguf_violations(parse_text(raw)))

    def test_scoped_drafter_mod_fails_the_locality_guard(self):
        raw = (EXPLORE / TENSORFOLD_ARM).read_text(encoding="utf-8")
        raw = mutate(raw, '"mods/kolibri-drafter-launcher"',
                     '"@littlecedar/mods/kolibri-drafter-launcher"')
        self.assertTrue(drafter_violations(parse_text(raw)))

    def test_unpinned_drafter_digest_fails_the_drafter_guard(self):
        raw = (EXPLORE / TENSORFOLD_ARM).read_text(encoding="utf-8")
        raw = mutate(raw, TENSORFOLD_DIGEST, "0" * 8)
        self.assertTrue(drafter_violations(parse_text(raw)))

    def test_one_arm_drifting_off_the_engine_pin_fails(self):
        items = []
        for name in KOLIBRI_4BIT_ARMS:
            raw = (EXPLORE / name).read_text(encoding="utf-8")
            if name == KOLIBRI_4BIT_ARMS[0]:
                raw = mutate(raw, VLLM_029_DIGEST, "c" * 64)
            items.append((name, parse_text(raw)))
        self.assertTrue(kolibri_engine_violations(items))


if __name__ == "__main__":
    unittest.main()
