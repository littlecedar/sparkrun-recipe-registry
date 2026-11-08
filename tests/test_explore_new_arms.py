"""Guards for the two explore arms that survived the 2026-10-19 selection.

The lane's eight 2026-10-18 arms were scored against the owner's
speed / concurrency / accuracy / size directive; six were retired to
`attic/explore/` (see `attic/explore/ARMS-MANIFEST.md`) and their guards went
with them. What remains here is what the shipped lane still needs:

  * `kolibri-1-apex-24bpw-llamacpp.yaml` — the kept GGUF tier on the fork image.
  * `poolside-laguna-m1-nvfp4-vllm-tp2.yaml` — the lane's only two-node arm, booted
    2026-10-20 on `v0.29.0` (not a selection candidate; its `v0.32.0` pin is not
    re-booted yet).

Each invariant below is silent when broken:

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
  G  the GGUF arm declares `runtime: llama-cpp`, carries the `:quant` colon form
     on `model:`, and pins the fork image: stock llama.cpp has no `kolibri1`
     architecture at all.
  N  the two-node arms are exactly the declared set (Laguna-M.1 and the BF16
     TP=2 Ripple probe, min/max 2, TP=2); every other arm is 1/1/TP1. Asserted as
     an explicit map so a copy-paste cannot quietly make a solo arm two-node, or
     a two-node arm solo.

Recipes are parsed as text (stdlib only, no PyYAML) by the parser the other
lane guards use; an empty parse RAISES rather than returning empty collections.
Every rule has a negative control that mutates the real recipe text.

Run:
    uv run python -B -m unittest tests.test_explore_new_arms -v
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from tests.test_ornith_recipes import parse_text

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPLORE = REPO_ROOT / "recipes" / "explore"

ARMS = (
    "kolibri-1-apex-24bpw-llamacpp.yaml",
    "poolside-laguna-m1-nvfp4-vllm-tp2.yaml",
    "zz-ripple-65b-preview-nvfp4-tp1-vllm.yaml",
    "zz-ripple-65b-preview-nvfp4-tp1-dflash2-vllm.yaml",
    "zz-ripple-65b-preview-bf16-tp2-vllm.yaml",
)

GGUF_ARMS = ("kolibri-1-apex-24bpw-llamacpp.yaml",)
GGUF_QUANT = "APEX-2.4bpw"
LAGUNA_M1 = "poolside-laguna-m1-nvfp4-vllm-tp2.yaml"

# The 2026-11-08 Ripple probes (authored, not booted). An architecture newer
# than every release in the fleet needs one engine pin shared by all three
# cells, or a C1 on one build cannot be compared with a C5 on another.
RIPPLE_ARMS = (
    "zz-ripple-65b-preview-nvfp4-tp1-vllm.yaml",
    "zz-ripple-65b-preview-nvfp4-tp1-dflash2-vllm.yaml",
    "zz-ripple-65b-preview-bf16-tp2-vllm.yaml",
)
RIPPLE_DFLASH = "zz-ripple-65b-preview-nvfp4-tp1-dflash2-vllm.yaml"
RIPPLE_BF16 = "zz-ripple-65b-preview-bf16-tp2-vllm.yaml"
RIPPLE_DRAFT = "ricursiveAI/Ripple-65B-Preview-DFlash2"
RIPPLE_ENGINE = "sha256:390a656b54e12144ad15ff32244c6e848408b0ee94f2c4c5a84451e7430f1aa7"
# The BF16 cell booted the fleet-local relayed copy of the same arm64 child
# (image id == that child's config digest), pinned by its full relay tag with
# distribution disabled: deliberate, not an unpinned pull (lane README trade).
RIPPLE_LOCAL_TAG = (
    "oci-relay/pinned:"
    "4856ba8c07d52fa0df316413a70d8a14ea8e75a9e9590962bd80a71c4cc7d16f"
)

# The arms allowed to declare two nodes (min/max 2, TP=2).
TWO_NODE = (LAGUNA_M1, "zz-ripple-65b-preview-bf16-tp2-vllm.yaml")

SHA40 = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}\b")
LOCAL_ONLY = re.compile(r"(?m)^distribution_config:\n  containers:\n    enabled: false$")
HUB_ID = re.compile(
    r"(?<![\w./-])([A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*)"
    r"(?![\w./-])"
)
GGUF_MODEL = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*:([A-Za-z0-9_.-]+)"
)

# Fork-built image: upstream llama.cpp cannot load `kolibri1` at all.
LLAMACPP_IMAGE = "littlecedar/dgx-spark-llama-cpp-kolibri1"
LLAMACPP_DIGEST = "1928661c"


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
    """Digest-pinned, or explicitly local-only.

    `distribution_config.containers.enabled: false` is the SM121 survey arms'
    shape: sparkrun will not pull the tag, so a fleet-local image is deliberate
    rather than an unpinned pull.  Anything else must carry a digest.
    """
    container = r["top"].get("container", "")
    if DIGEST.search(container) or LOCAL_ONLY.search(r.get("stripped", "")):
        return []
    return [f"container {container!r} is not @sha256 digest-pinned"]


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


def dflash_violations(r: dict) -> list[str]:
    """A drafter cell must pin method dflash, the draft repo and its 40-hex revision.

    sparkrun's vLLM draft binding rewrites the object's `revision` from the
    prepared draft manifest, so an absent revision silently serves the repo's
    `main` — the pin is the only thing that makes the cell reproducible.
    """
    raw = r["defaults"].get("speculative_config")
    if not raw:
        return ["no speculative_config"]
    try:
        spec = json.loads(raw)
    except ValueError:
        return [f"speculative_config is not JSON: {raw!r}"]
    bad: list[str] = []
    if spec.get("method") != "dflash":
        bad.append(f"method {spec.get('method')!r} is not dflash")
    if spec.get("model") != RIPPLE_DRAFT:
        bad.append(f"model {spec.get('model')!r} is not {RIPPLE_DRAFT}")
    if not SHA40.match(str(spec.get("revision", ""))):
        bad.append(f"revision {spec.get('revision')!r} not 40-hex SHA")
    if "{speculative_config}" not in r["command"]:
        bad.append("command does not pass {speculative_config}")
    return bad


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


def node_violations(name: str, r: dict) -> list[str]:
    """The two-node arms are exactly TWO_NODE; every other arm is 1/1/TP1."""
    want = "2" if name in TWO_NODE else "1"
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


# ---------------------------------------------------------------------------


class LaneArms(unittest.TestCase):
    """Both surviving arms are present and parse to the shape the guards need."""

    def test_lane_has_the_two_arms(self):
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


class GgufArm(unittest.TestCase):
    def test_gguf_arm_holds(self):
        for name in GGUF_ARMS:
            with self.subTest(arm=name):
                self.assertEqual(gguf_violations(arm(name)), [])

    def test_the_gguf_arm_is_the_kept_apex_tier(self):
        self.assertRegex(
            arm(GGUF_ARMS[0])["top"]["model"],
            r":%s$" % re.escape(GGUF_QUANT),
        )


class RippleArms(unittest.TestCase):
    """The 2026-11-08 Ripple probes stay comparable to each other."""

    def test_engine_pin_is_shared_by_all_three_cells(self):
        # The two TP=1 cells pin the registry digest; the BF16 cell that booted
        # pins the relayed copy of that digest's arm64 child, distribution off.
        registry = {arm(n)["top"]["container"]
                    for n in RIPPLE_ARMS if n != RIPPLE_BF16}
        self.assertEqual(registry, {"vllm/vllm-openai:nightly@" + RIPPLE_ENGINE})
        bf16 = arm(RIPPLE_BF16)
        self.assertEqual(bf16["top"]["container"], RIPPLE_LOCAL_TAG)
        self.assertTrue(LOCAL_ONLY.search(bf16["stripped"]))
        # The relay tag's suffix is its full 64-hex name; a short form does not
        # resolve, so a "tidy" `:4856ba8c` tag would be a phantom pin.
        self.assertRegex(RIPPLE_LOCAL_TAG, r":[0-9a-f]{64}$")

    def test_the_drafter_cell_pins_the_draft(self):
        self.assertEqual(dflash_violations(arm(RIPPLE_DFLASH)), [])

    def test_no_other_ripple_arm_carries_a_drafter(self):
        for name in RIPPLE_ARMS:
            if name == RIPPLE_DFLASH:
                continue
            self.assertNotIn("speculative_config", arm(name)["defaults"], name)


class NodeShape(unittest.TestCase):
    def test_node_shapes_match_the_declared_map(self):
        for name in ARMS:
            with self.subTest(arm=name):
                self.assertEqual(node_violations(name, arm(name)), [])

    def test_two_node_arms_are_the_declared_pair(self):
        two_node = [n for n in ARMS if arm(n)["top"]["min_nodes"] != "1"]
        self.assertEqual(sorted(two_node), sorted(TWO_NODE))


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

    def test_local_tag_without_distribution_disabled_fails_the_guard(self):
        # The local-only exemption is the explicit block, not the tag shape:
        # drop the block and the same local tag becomes a violation.
        raw = (EXPLORE / RIPPLE_BF16).read_text(encoding="utf-8")
        raw = mutate(raw, "distribution_config:", "distribution_disabled:")
        self.assertTrue(digest_violations(parse_text(raw)))

    def test_solo_shape_on_the_two_node_arm_fails_the_node_guard(self):
        # The copy-paste a solo arm onto this file would make.
        raw = mutate(self.raw, "min_nodes: 2", "min_nodes: 1")
        self.assertIn("min_nodes is '1', expected '2'",
                      node_violations(LAGUNA_M1, parse_text(raw)))

    def test_second_two_node_arm_fails_the_exception_guard(self):
        solo = GGUF_ARMS[0]
        raw = (EXPLORE / solo).read_text(encoding="utf-8")
        raw = mutate(raw, "min_nodes: 1", "min_nodes: 2")
        self.assertTrue(node_violations(solo, parse_text(raw)))

    def test_unreferenced_default_fails_the_consumed_guard(self):
        raw = mutate(self.raw, "  --port {port}\n", "")
        self.assertIn("port", unconsumed(parse_text(raw)))

    def test_snapshot_path_for_a_different_model_fails_the_identity_guard(self):
        # The shipped recipe hands {model} to vllm, so the guard's target is a
        # literal prepared path for some other checkpoint: inject one.
        foreign = ("/cache/huggingface/hub/models--poolside--Laguna-S-2.1-NVFP4/"
                   "snapshots/" + "0" * 40)
        raw = mutate(self.raw, "  {model}\n", "  " + foreign + "\n")
        self.assertTrue(model_consumption_violations(parse_text(raw)))

    def test_sibling_repo_id_in_command_fails_the_foreign_id_guard(self):
        raw = mutate(self.raw, "--enable-prefix-caching",
                     "--tokenizer mistralai/Mistral-Small-4-119B-2603-NVFP4")
        self.assertEqual(
            foreign_repo_violations(parse_text(raw)),
            ["mistralai/Mistral-Small-4-119B-2603-NVFP4"],
        )

    def test_unpinned_draft_fails_the_drafter_guard(self):
        raw = (EXPLORE / RIPPLE_DFLASH).read_text(encoding="utf-8")
        raw = mutate(raw, '"revision": "35609b3b', '"rev": "35609b3b')
        self.assertTrue(dflash_violations(parse_text(raw)))

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
        raw = mutate(raw, "model: Myric/Kolibri-1-APEX-GGUF:APEX-2.4bpw",
                     "model: Myric/Kolibri-1-APEX-GGUF")
        self.assertTrue(gguf_violations(parse_text(raw)))


if __name__ == "__main__":
    unittest.main()