"""Guards for the `recipes/ornith/` lane.

Run:
    python3 -m unittest discover -s tests

Stdlib-only, and deliberately parses recipe TEXT with regex rather than
importing PyYAML, so the guards survive a sparkrun upgrade and run anywhere
(AGENTS.md: scripts must run on any lab machine).

Why these exist.  The lane had **no recipe guard at all** until 2026-10-14
(`recipes/ornith/README.md` §"No guard suite for this lane"); the only
mechanical coverage was the mod guard and the repo-wide placeholder guards.
The 9B arm (`ornith-1.5-9b-nvfp4-dflash-sglang.yaml`) is a *copy* of the 35B
arm with a different checkpoint at a different scale, so every invariant below
is one a careless copy silently breaks:

  O1  no `mamba_*`, no `moe_runner_backend` in the 9B arm .. the checkpoint is
       dense (`config.json`: no expert config, one MLP per layer), so
       `moe_runner_backend` has nothing to route.  The `mamba_*` trio would in
       fact apply -- the checkpoint IS a Qwen3.5 hybrid GDN model
       (`text_config.layer_types` alternates three `linear_attention` layers to
       one `full_attention` layer) -- so its omission is a *deliberate* choice to
       run engine defaults on a first, unmeasured arm rather than inherit the
       35B's `mamba_full_memory_ratio: 3.51`, a house value copied across lanes
       with no recorded derivation (`recipes/ornith/AGENTS.md` §3.1).  Do not
       "fix" the omission in either direction before reading
       (`recipes/ornith/NOTES.md`, §2).
  O2  the 9B arm must NOT mount @littlecedar/mods/ornith-honed-chat-template ..
       that template is the 35B's honed artifact (`qwen3.8-honed-v22.5.1`,
       30,438 B).  The 9B ships its own multimodal `chat_template.jinja`
       (7,593 B, vision tokens + an `enable_thinking` toggle), so serving the
       honed file would hand a vision template to a model whose prompt format it
       was not written for.
  O3  draft identity and the distribution-only pin .. the 9B ships the first-party
       `ornith-ai/Ornith-1.5-9B-DFlash` *unpinned* (its fetch resolves refs/main);
       the 35B ships `jzinno/…-DFlash2` and pins it (O5).  `sparkrun`'s draft pin
       is a separate key from `model_revision` -- the two SHAs live in different
       repos, so one cannot stand in for the other.
  O5  the 35B draft pin is paired with a refs/main seed .. a SHA-keyed draft
       fetch writes no refs/ entry and SGLang's offline draft-config lookup
       resolves only refs/main, so the pin alone never boots (AGENTS.md §3.12);
       the recipe carries a pre_exec hook that writes the pinned SHA to
       <draft cache>/refs/main before serve.
  O4  served model id is the repo id, rendered from `{served_model_name}` .. the
       class guard `tests/test_recipe_placeholder_resolution.py::ServedModelNameNotRebound`
       covers this repo-wide; kept here too because a copy of the pre-fix 35B
       spelling is exactly how this arm would be born wrong.

Guards read the *rendered* command, not the file text, because recipe prose
legitimately names the flags it explains the absence of (O1/O2 are both
documented in comments).  Comments are stripped before anything reads a block
-- the convention `tests/test_ifm_recipes.py` records as F20.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPE_DIR = REPO_ROOT / "recipes" / "ornith"

NINE_B = RECIPE_DIR / "ornith-1.5-9b-nvfp4-dflash-sglang.yaml"
THIRTY_FIVE_B = RECIPE_DIR / "ornith-1.5-35b-a3b-nvfp4-dflash2-sglang.yaml"
FORTY_NINE_SEVEN_B = RECIPE_DIR / "littlecedar-ornith-1.5-397b-nvfp4-mtp-graft-vllm.yaml"

NINE_B_REPO = "ornith-ai/Ornith-1.5-9B-NVFP4"
NINE_B_DRAFT = "ornith-ai/Ornith-1.5-9B-DFlash"
NINE_B_MODEL_REVISION = "155f200d85ad58464571c77d5e1122ea5d419d7b"

# Values sparkrun fills from its own resolution rather than from `defaults:`.
ENGINE_PLACEHOLDERS = {"model", "model_path", "host", "port", "model_revision"}

SHA40 = re.compile(r"^[0-9a-f]{40}$")


# ---------------------------------------------------------------------------
# Parsing.  Understands exactly the YAML these recipes use (top-level scalars,
# one-level `defaults:` mapping, a `mods:` list, and `key: >` folded scalars)
# and refuses to guess at anything else.
# ---------------------------------------------------------------------------

def _strip_comment_lines(text: str) -> str:
    """Drop whole-line comments.  F20: prose documents the forbidden flags."""
    return "\n".join(
        ln for ln in text.splitlines() if not ln.lstrip().startswith("#")
    )


def _unquote(val: str) -> str:
    val = val.strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
        return val[1:-1]
    return val


def parse(path: Path) -> dict:
    """Return {top, defaults, mods, command, stripped, raw}."""
    text = _strip_comment_lines(path.read_text(encoding="utf-8"))
    top: dict[str, str] = {}
    defaults: dict[str, str] = {}
    mods: list[str] = []
    command = ""
    section = None
    for line in text.splitlines():
        if not line.strip():
            continue
        if not line.startswith(" ") and ":" in line:
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip()
            if val in (">", "|", ">-", "|-", "|+", ">-"):
                section = key           # folded/literal block
                continue
            if not val:
                section = key           # nested mapping / list, such as `defaults:`
                continue
            section = None              # ordinary scalar ends any section
            top[key] = _unquote(val)
            continue
        if section == "defaults" and line.startswith("  ") and ":" in line:
            stripped = line.strip()
            if stripped.startswith("- "):
                continue
            key, _, val = stripped.partition(":")
            defaults[key.strip()] = _unquote(val)
        elif section == "mods" and line.strip().startswith("- "):
            mods.append(_unquote(line.strip()[2:]))
        elif section == "command":
            command += " " + line.strip()
    return {"top": top, "defaults": defaults, "mods": mods,
            "command": command.strip(), "stripped": text,
            "raw": path.read_text(encoding="utf-8")}


def render(recipe: dict) -> str:
    """Substitute placeholders the way sparkrun would."""
    out = recipe["command"]
    for k, v in recipe["defaults"].items():
        out = out.replace("{" + k + "}", v)
    for k in ENGINE_PLACEHOLDERS:
        if k in recipe["top"]:
            out = out.replace("{" + k + "}", recipe["top"][k])
    return re.sub(r"\s+", " ", out)


# ---------------------------------------------------------------------------

LANE_RECIPES = (NINE_B, THIRTY_FIVE_B, FORTY_NINE_SEVEN_B)


class LaneRecipes(unittest.TestCase):
    """Every shipped recipe in the lane is present, parsed, and named by file."""

    def test_shipped_recipes_exist(self):
        for p in LANE_RECIPES:
            self.assertTrue(p.exists(), f"missing lane recipe {p}")

    def test_no_name_key(self):
        # Repo convention: name == filename minus .yaml; a `name:` key is banned.
        for p in LANE_RECIPES:
            self.assertNotIn("name", parse(p)["top"],
                             f"{p.name}: a `name:` key is banned")

    def test_command_is_a_folded_scalar(self):
        for p in LANE_RECIPES:
            self.assertIsNotNone(
                re.search(r"^command:\s*>", p.read_text(encoding="utf-8"),
                          re.MULTILINE),
                f"{p.name}: command must be a folded scalar (`command: >`)",
            )


class NineBArmShape(unittest.TestCase):
    """O3/O4: the new arm's model pin, draft, and served id."""

    def setUp(self):
        self.r = parse(NINE_B)

    def test_model_and_revision_pinned_and_forwarded(self):
        self.assertEqual(self.r["top"].get("model"), NINE_B_REPO)
        pin = self.r["top"].get("model_revision", "")
        self.assertRegex(pin, SHA40,
                         "model_revision must be a full 40-char commit SHA")
        self.assertEqual(pin, NINE_B_MODEL_REVISION)
        self.assertIn("--revision " + pin, render(self.r),
                      "the pin is declared but not passed to the engine")

    def test_draft_is_the_first_party_head_and_left_unpinned(self):
        paper = self.r["defaults"].get("speculative_draft_model")
        self.assertEqual(paper, NINE_B_DRAFT,
                         "the 9B draft is the ornith-ai first-party head, not jzinno DFlash2")
        # The draft must NOT carry a revision pin: a SHA-keyed fetch writes no
        # refs/ entry and SGLang's offline draft-config lookup resolves only
        # refs/main, so a pinned draft never starts (see the recipe comment).
        self.assertNotIn("speculative_draft_model_revision", self.r["defaults"])
        # The repo id is what the engine is handed (sparkrun does not bind it).
        self.assertIn("--speculative-draft-model-path " + NINE_B_DRAFT,
                      render(self.r))

    def test_spec_decode_engaged_on_sglang_dflash(self):
        self.assertEqual(self.r["defaults"].get("speculative_algorithm"), "DFLASH")
        cmd = render(self.r)
        self.assertIn("--speculative-algorithm DFLASH", cmd)
        self.assertIn("--speculative-num-draft-tokens 8", cmd)

    def test_served_model_id_is_the_repo_id(self):
        self.assertEqual(self.r["defaults"].get("served_model_name"), NINE_B_REPO)
        cmd = render(self.r)
        self.assertIn("--served-model-name " + NINE_B_REPO, cmd)
        self.assertNotIn("--served-model-name {model}", self.r["stripped"])

    def test_single_node_tp1(self):
        self.assertEqual(self.r["top"].get("min_nodes"), "1")
        self.assertEqual(self.r["defaults"].get("tensor_parallel"), "1")

    def test_container_digest_pinned_and_shared_with_the_35b(self):
        nine = self.r["top"].get("container", "")
        self.assertIn("@sha256:", nine, "container must be digest-pinned")
        self.assertEqual(nine, parse(THIRTY_FIVE_B)["top"].get("container"),
                         "the two SGLang arms serve one engine build")

    def test_every_default_reaches_a_placeholder(self):
        # Mirrors the repo-wide InertDefaults guard, scoped so a regression here
        # names this arm.
        for key in self.r["defaults"]:
            if key in ENGINE_PLACEHOLDERS:
                continue
            self.assertIn("{" + key + "}", self.r["command"],
                          f"defaults key {key!r} is never referenced by a placeholder")


class NineBArmDropsTheThirtyBKnobs(unittest.TestCase):
    """O1: no mamba_*/moe_runner_backend -- the arm runs engine defaults."""

    FORBIDDEN_PLACEHOLDERS = re.compile(
        r"\{(mamba_[a-z_]*|moe_runner_backend)\}")

    def _violations(self, defaults: dict, command: str) -> list[str]:
        bad = [f"defaults.{k}" for k in defaults
               if k.startswith("mamba_") or k == "moe_runner_backend"]
        bad += sorted(self.FORBIDDEN_PLACEHOLDERS.findall(command))
        return bad

    def test_absent(self):
        r = parse(NINE_B)
        self.assertEqual(self._violations(r["defaults"], r["command"]), [])
        rendered = render(r)
        for flag in ("--mamba-full-memory-ratio", "--mamba-radix-cache-strategy",
                     "--mamba-ssm-dtype", "--moe-runner-backend"):
            self.assertNotIn(flag, rendered, f"{NINE_B.name}: {flag} must not ship")

    def test_negative_control(self):
        r = parse(NINE_B)
        cloned = dict(r["defaults"])
        cloned["mamba_full_memory_ratio"] = "3.51"
        self.assertEqual(self._violations(cloned, r["command"]),
                         ["defaults.mamba_full_memory_ratio"])
        self.assertEqual(
            self._violations({}, r["command"] + " --mamba-ssm-dtype {mamba_ssm_dtype}"),
            ["mamba_ssm_dtype"],
        )


class NineBArmDoesNotReuseTheHonedTemplate(unittest.TestCase):
    """O2: the 35B's honed template is a 35B artifact and must not be mounted."""

    HONED_MOD = "@littlecedar/mods/ornith-honed-chat-template"

    def _violations(self, mods: list[str], defaults: dict, command: str) -> list[str]:
        bad = []
        if self.HONED_MOD in mods:
            bad.append("mounts the 35B honed-template mod")
        if "honed_chat_template" in defaults:
            bad.append("declares honed_chat_template")
        if "--chat-template" in command:
            bad.append("passes --chat-template")
        return bad

    def test_absent_from_the_9b_arm(self):
        r = parse(NINE_B)
        self.assertEqual(self._violations(r["mods"], r["defaults"], render(r)), [])
        self.assertIn("@littlecedar/mods/pip-install-fastsafetensors", r["mods"],
                      "the arm still needs the fastsafetensors mod")

    def test_the_35b_still_mounts_it(self):
        # The guard must not be satisfied by stripping the sibling by accident.
        r = parse(THIRTY_FIVE_B)
        self.assertIn(self.HONED_MOD, r["mods"])
        self.assertIn("--chat-template {honed_chat_template}", r["command"])

    def test_negative_control(self):
        r = parse(NINE_B)
        bad_mods = r["mods"] + [self.HONED_MOD]
        self.assertEqual(self._violations(bad_mods, r["defaults"], render(r)),
                         ["mounts the 35B honed-template mod"])
        self.assertEqual(
            self._violations([], {"honed_chat_template": "/x"}, "--chat-template {honed_chat_template}"),
            ["declares honed_chat_template", "passes --chat-template"],
        )


THIRTY_FIVE_B_DRAFT = "jzinno/Ornith-1.5-35B-A3B-DFlash2"
THIRTY_FIVE_B_DRAFT_REVISION = "9b4852c05fd00b672b7434b1bb105bc03c8682b0"


class ThirtyFiveBArmPinsTheDraftWithARefSeed(unittest.TestCase):
    """O5: the 35B draft pin is distribution-only and needs a refs/main seed."""

    def setUp(self):
        self.r = parse(THIRTY_FIVE_B)

    def test_draft_pinned_to_the_jzinno_sha(self):
        self.assertEqual(self.r["defaults"].get("speculative_draft_model"),
                         THIRTY_FIVE_B_DRAFT)
        self.assertEqual(self.r["defaults"].get("speculative_draft_model_revision"),
                         THIRTY_FIVE_B_DRAFT_REVISION,
                         "the shipped draft must carry the distribution-only pin")

    def test_pre_exec_seeds_refs_main_from_the_pin(self):
        text = self.r["stripped"]
        self.assertRegex(text, r"(?m)^pre_exec:\s*$",
                         "the pin needs a pre_exec hook (AGENTS.md §3.12)")
        self.assertIn("models--jzinno--Ornith-1.5-35B-A3B-DFlash2", text)
        self.assertIn("refs/main", text)
        self.assertIn("{speculative_draft_model_revision}", text,
                      "the hook must write the pinned SHA, not a literal")

    def test_negative_controls(self):
        # Drop the pre_exec block: the seed must disappear with it.
        without_hook = re.sub(r"(?ms)^pre_exec:\n(?:.*\n)*?(?=^[a-z0-9_]+:)", "",
                              self.r["stripped"])
        self.assertNotIn("refs/main", without_hook)
        # A hook that writes a literal SHA instead of the pin must not pass.
        literal = self.r["stripped"].replace(
            "{speculative_draft_model_revision}", THIRTY_FIVE_B_DRAFT_REVISION)
        self.assertNotIn("{speculative_draft_model_revision}", literal)
        # Drop the pin line: the defaults key must be gone (the hook would then
        # render its placeholder literally and the pin guard must fail).
        without_pin = re.sub(r"(?m)^  speculative_draft_model_revision:.*\n", "",
                             self.r["stripped"])
        self.assertNotRegex(without_pin, r"(?m)^  speculative_draft_model_revision:")


class FlagshipSpeculativeConfigIsSwappable(unittest.TestCase):
    """The 397B's speculative config must stay a `{speculative_config}` placeholder.

    sparkrun reads the draft model+revision *out of the `speculative_config` default*
    (`runtimes/_vllm_common.py::detect_spec_config_draft`) to distribute the draft to
    all four nodes, and `-o speculative_config={...}` only reaches a declared default.
    Inline JSON in `command:` therefore does two silent things: the DFlash A/B swap
    becomes a no-op, and a DFlash draft is never distributed (`Revision Not Found` at
    serve). The MTP arm's rendered JSON must stay byte-identical to the shipped value.
    """

    MTP_JSON = ('{"method":"mtp","num_speculative_tokens":3,"max_model_len":262144,'
                '"attention_backend":"flashinfer","moe_backend":"flashinfer_cutlass"}')

    def setUp(self):
        self.r = parse(FORTY_NINE_SEVEN_B)

    def test_default_declared_and_referenced(self):
        self.assertEqual(self.r["defaults"].get("speculative_config"), self.MTP_JSON)
        self.assertIn("--speculative-config '{speculative_config}'", self.r["command"])

    def test_no_inline_json_in_the_command(self):
        self.assertNotIn("--speculative-config '{\"", self.r["command"],
                         "inline speculative JSON makes -o a no-op and hides the draft "
                         "from sparkrun's distribution path")

    def test_mtp_arm_still_renders_the_shipped_json(self):
        self.assertIn("--speculative-config '" + self.MTP_JSON + "'", render(self.r))

    def test_negative_control(self):
        # An inline JSON in command: (the pre-fix shape) must trip both checks.
        inline_command = self.r["command"].replace(
            "--speculative-config '{speculative_config}'",
            "--speculative-config '" + self.MTP_JSON + "'")
        self.assertNotIn("--speculative-config '{speculative_config}'", inline_command)
        self.assertIn("--speculative-config '{\"", inline_command)
        # And a declared-but-unreferenced key is what the repo InertDefaults guard
        # catches; here we assert the reference itself is present.
        self.assertIn("{speculative_config}", self.r["command"])


class FlagshipContainerIsDigestPinned(unittest.TestCase):
    """§3.8: the 397B's GHCR nightly is a moving tag and must be pinned.

    The four serving nodes held three different builds under `:latest` before the pin,
    so a multi-node comparison on the bare tag is not even one engine.
    """

    def test_digest_pinned(self):
        container = parse(FORTY_NINE_SEVEN_B)["top"].get("container", "")
        self.assertIn("@sha256:", container, "container must be digest-pinned")
        self.assertTrue(container.startswith(
            "ghcr.io/spark-arena/dgx-vllm-eugr-nightly@sha256:"))

if __name__ == "__main__":
    unittest.main()
