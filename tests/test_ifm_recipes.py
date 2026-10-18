"""Guards for the IFM K2-Horizon 0.9B Spark recipes.

Run:
    python3 -m unittest discover -s tests

Stdlib-only, and deliberately parses recipe TEXT with regex rather than
importing PyYAML, so the guards survive a sparkrun upgrade and run anywhere
(AGENTS.md: scripts must run on any lab machine).

Why these exist (sources: recipes/ifm/K2-09B-MODEL-OPTIMIZATION-WORK.md and the
family's coordination ledger, now a git-ignored working file; every invariant below was VERIFIED against sglang v0.5.20
source at a named file:line):

  I1  never `--attention-backend fa3` ............ layers/attention/
       attention_registry.py:227-235 asserts `(major==8 and !mla) or major==9`;
       GB10 reports (12,1) (utils/common.py:329-333 `is_sm121`), so fa3 raises
       AssertionError at backend construction -- after the weight load, before the
       port binds.  The HF model cards and the SGLang cookbook both say `fa3`
       because they were measured on H200.  Copying them is the single most
       likely way to ship a recipe that cannot boot.
  I2  no `--quantization` flag .................. config.json has no
       quantization_config and models/xllm.py has no packed-weight mapping beyond
       qkv/gate_up stacking (:1692-1695), so a quantized load fails inside weight
       loading with uninitialised parameters instead of refusing cleanly.  There
       is also no quantized 0.9B artifact to point it at.
  I3  no `--enable-auto-tool-choice` ............ vLLM flag; absent from sglang
       v0.5.20 server args entirely (not in arg_groups/fields/*.py,
       server_args.py, or arg_groups/speculative_hook.py).  It appears in the
       model card's vLLM block, which is what makes it tempting.
  I4  no `--hf-overrides` ....................... sglang spells it
       --json-model-override-args; and it is unnecessary here because the dense
       path accepts YaRN from config.json natively (models/xllm.py:330-334,
       :375-391).  The card's own version of this flag is not even valid JSON.
  I5  `--dtype bfloat16` spelled ................ config.json declares
       "dtype": "float32" (a K2Aurora->K2Horizon migration artifact;
       validation.json says the tensors are BF16), so `auto` resolves through a
       field that lies about the checkpoint.
  I6  no `--speculative-algorithm UNO` .......... arg_groups/speculative_hook.py
       :503-508 raises unless (prefill, decode) == ("fa3","fa3"), which SM121
       cannot construct (I1).  A UNO arm cannot exist on this chip yet, so a
       recipe that launches one is a recipe that cannot boot.
  I7  `model_revision` pinned AND reaching the engine .. sparkrun downloads a
       SHA-pinned repo into snapshots/<sha>/ and writes no refs/ entry, and the
       container runs HF_HUB_OFFLINE=1, so a pin that never reaches the engine
       dies with LocalEntryNotFoundError *after* distribution.
   I8  every `defaults:` key consumed by a placeholder .. a defaults key with no
        placeholder is silently not a setting — the value never reaches any flag,
        and nothing else in the launch path reads `defaults:`.
   I9  `command:` stays a folded scalar with no `#` .... a `#` inside the folded
        block is passed through to the shell, and a plain scalar collapses the
        multi-line command onto one line losing the fold.

F20 lesson (defined in recipes/qwen3/QWEN3-EMBED-OPTIMIZATION-WORK.md:641, carried
forward by tests/test_ds4_recipes.py:20): these guards read the *rendered command*,
not the file text, because recipe prose legitimately *names* the flags it
explains the absence of (I2/I3/I6 are all documented in comments).  Comments are
stripped before anything reads a block.
 """

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPE_DIR = REPO_ROOT / "recipes" / "ifm"

BASE_09B = RECIPE_DIR / "k2-horizon-0.9b-bf16-sglang.yaml"
UNO_09B = RECIPE_DIR / "k2-horizon-0.9b-bf16-uno-sglang.yaml"
ALL = [BASE_09B, UNO_09B]

# The UNO arm's second artifact is staged by a lane-local mod (bare `mods/<dir>`, the
# form that resolves before a push), because sparkrun distributes only `model:`.
MODS_DIR = RECIPE_DIR / "mods"
UNO_MOD = "provide-uno-lora-k2-horizon-0.9b"
UNO_GATE_MOD = "probe-uno-fa4-sm121"

# I6 as a pattern, so the scoped exemption below cannot drift from the rule.
UNO_FLAG = r"--speculative-algorithm\s+UNO\b"

# sglang's own flag names, as emitted by the recipe (sparkrun fills
# placeholders from `defaults:`, so guards match the *rendered* form).
ENGINE_PLACEHOLDERS = {"model", "model_path", "host", "port"}

# The first released tag containing python/sglang/srt/models/xllm.py.  Verified
# by tree listing: present at v0.5.20, absent at v0.5.19 and earlier.  Any image
# older than this does not know what K2HorizonForCausalLM is.
MIN_SGLANG = (0, 5, 20)

# VERIFIED from the HF API 2026-10-14.  The re-pin moved only the card and the
# two chat templates; the weight shard, tokenizer and config.json are
# byte-identical to the previous pin.  A recipe drifting from this value would be
# a different checkpoint than the one the lane re-measured against.
MODEL_REVISION = "383cb66347be4d361138e8157c2f8779b7440752"


# ---------------------------------------------------------------------------
# Parsing.  Understands exactly the YAML these recipes use (top-level scalars,
# one-level `defaults:` mapping, and `key: >` folded scalars) and refuses to
# guess at anything else.
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


def parse_text(raw: str) -> dict:
    """Parse recipe text.  {top, defaults, command, stripped, raw}.

    Takes TEXT so a negative control can feed the guard a mutated copy of a real
    recipe.  An empty parse raises: a guard over zero keys must fail loudly.
    """
    text = _strip_comment_lines(raw)
    top: dict[str, str] = {}
    defaults: dict[str, str] = {}
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
                section = key           # nested mapping, e.g. `defaults:`
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
        elif section == "command":
            command += " " + line.strip()
    if not top or not command:
        raise ValueError("recipe text did not parse: empty top-level or command block")
    return {"top": top, "defaults": defaults, "command": command.strip(),
            "stripped": text, "raw": raw}


def parse(path: Path) -> dict:
    return parse_text(path.read_text(encoding="utf-8"))


def mod_list(recipe: dict) -> list[str]:
    """The `mods:` entries, unquoted.  No block is an empty list, not an error."""
    block = re.search(r"(?m)^mods:\n((?:  - .*\n)+)", recipe["stripped"])
    return [_unquote(x) for x in re.findall(r"(?m)^  - (.+)$", block.group(1))] \
        if block else []


def render(recipe: dict) -> str:
    """Substitute placeholders the way sparkrun would: `defaults:` first, then
    the few values sparkrun fills from its own resolution."""
    out = recipe["command"]
    for k, v in recipe["defaults"].items():
        out = out.replace("{" + k + "}", v)
    for k in ("model", "model_path", "host", "port", "model_revision"):
        if k in recipe["top"]:
            out = out.replace("{" + k + "}", recipe["top"][k])
    return re.sub(r"\s+", " ", out)


# ---------------------------------------------------------------------------
# The UNO arm.  UNO is verify-based speculative decoding: the engine runs the
# target plus a conditional-LoRA draft, so the arm needs a SECOND artifact that
# sparkrun does not distribute and a backend the stock gate refuses.
#
#  U1  the adapter is staged by a lane mod at a fixed container path, and that
#      path is the one `--uno-lora-path` names .. a path nothing writes is a
#      launch that dies before the port binds.
#  U2  TP=PP=1 .. `_handle_uno` raises "UNO requires TP=PP=1."
#  U3  no --speculative-draft-model-path .. passing one to UNO is an outright error.
#  U4  I6 is waived only for an arm that mounts the fa4 gate .. the gate is what
#      makes UNO constructible on SM121 at all (see uno_waiver_violations).
# ---------------------------------------------------------------------------

def uno_waiver_violations(recipe: dict) -> list[str]:
    """I6's scoped exception: is this arm allowed to declare UNO?

    `_handle_uno` raises unless (prefill, decode) == ("fa3","fa3") and fa3 asserts
    SM80/90 (I1), so on GB10 the flag is fatal -- unless the arm mounts
    mods/probe-uno-fa4-sm121, which relaxes that literal to accept fa4, and
    declares attention_backend: fa4.  The exemption is keyed on that contract,
    not on a filename: lose the gate and the flag is I6 again.
    """
    if not re.search(UNO_FLAG, render(recipe)):
        return []
    bad = []
    if f"mods/{UNO_GATE_MOD}" not in mod_list(recipe):
        bad.append(f"UNO without mods/{UNO_GATE_MOD}: _handle_uno raises unless "
                   '(fa3,fa3), and fa3 cannot be constructed on GB10 (12,1)')
    if recipe["defaults"].get("attention_backend") != "fa4":
        bad.append("UNO with attention_backend "
                   f"{recipe['defaults'].get('attention_backend')!r}: the fa4 gate "
                   "mod admits fa4 only")
    return bad


def mod_reference_violations(recipe: dict) -> list[str]:
    """U1: the provide mod (and the gate it depends on) must be listed."""
    mods = mod_list(recipe)
    return [m for m in (f"mods/{UNO_MOD}", f"mods/{UNO_GATE_MOD}") if m not in mods]


def staging_violations(recipe: dict, script: str) -> list[str]:
    """U1: the path in --uno-lora-path is the path the provide mod writes."""
    path = recipe["defaults"].get("uno_lora_path", "")
    bad = []
    if not path.startswith("/cache/runtime/"):
        bad.append(f"uno_lora_path {path!r} is not under the persistent mod cache")
    if path not in script:
        bad.append(f"the provide mod never writes {path!r}, so --uno-lora-path "
                   "points at nothing")
    if "--uno-lora-path {uno_lora_path}" not in recipe["command"]:
        bad.append("uno_lora_path is declared but never passed to the engine")
    return bad


def single_device_violations(recipe: dict) -> list[str]:
    """U2: UNO requires TP=PP=1 -- a hard requirement, not a tuning choice."""
    keys = recipe["defaults"]
    bad = []
    if keys.get("tensor_parallel") != "1":
        bad.append(f'tensor_parallel {keys.get("tensor_parallel")!r}: '
                   '_handle_uno raises "UNO requires TP=PP=1."')
    if keys.get("pipeline_parallel", "1") != "1":
        bad.append(f'pipeline_parallel {keys.get("pipeline_parallel")!r}: same gate')
    if re.search(r"--(dp|data-parallel)\b", recipe["command"]):
        bad.append("data-parallel flag on a single-device UNO arm")
    return bad


class UnoArmShape(unittest.TestCase):
    """The 0.9B UNO arm: native UNO on a second, mod-staged LoRA adapter."""

    def setUp(self):
        self.r = parse(UNO_09B)
        self.script = (MODS_DIR / UNO_MOD / "run.sh").read_text(encoding="utf-8")

    def test_uno_is_the_declared_algorithm(self):
        self.assertEqual(self.r["defaults"].get("speculative_algorithm"), "UNO")
        self.assertIn("--speculative-algorithm UNO", render(self.r))

    def test_linear_uno_knobs(self):
        keys = self.r["defaults"]
        self.assertEqual(keys.get("speculative_eagle_topk"), "1",
                         "topk 1 is LINEAR UNO; tree mode adds avoidable constraints")
        width = int(keys["speculative_num_draft_tokens"])
        self.assertGreater(width, 0, "_handle_uno raises unless the width is positive")
        self.assertNotIn("--speculative-draft-model-path", self.r["command"],
                         "UNO reuses the target + a conditional LoRA; a draft path is "
                         "an outright error (U3)")

    def test_tp_and_pp_are_one(self):
        self.assertEqual(single_device_violations(self.r), [])
        self.assertIn("--tp 1", render(self.r))

    def test_adapter_is_staged_by_the_lane_mod(self):
        self.assertEqual(mod_reference_violations(self.r), [])

    def test_uno_lora_path_is_the_path_the_mod_writes(self):
        self.assertEqual(staging_violations(self.r, self.script), [])
        self.assertIn("--uno-lora-path {uno_lora_path}", self.r["command"])

    def test_mod_is_a_fail_closed_bash_script(self):
        self.assertTrue((MODS_DIR / UNO_MOD / "run.sh").is_file())
        self.assertIn("set -euo pipefail", self.script)
        self.assertIn("SPDX-License-Identifier: AGPL-3.0-or-later", self.script)
        self.assertIn(f'MOD_NAME="{UNO_MOD}"', self.script,
                      "MOD_NAME must match the directory it is mounted from")
        # Fail closed with an explicit non-zero exit, not a silent empty dir: the arm
        # cannot run without --uno-lora-path.
        self.assertIn("exit 1", self.script, "no fail-closed exit on the fetch path")
        self.assertIn("UNO_LORA_SHA256", self.script,
                      "the adapter is fetched: it must be pinned, not just sized")


class UnoNegativeControls(unittest.TestCase):
    """Each UNO guard must fire on a mutation of the real files."""

    def setUp(self):
        self.raw = UNO_09B.read_text(encoding="utf-8")
        self.script = (MODS_DIR / UNO_MOD / "run.sh").read_text(encoding="utf-8")
        assert parse_text(self.raw)

    def test_broken_mod_reference_is_caught(self):
        mutated = parse_text(self.raw.replace(f"mods/{UNO_MOD}",
                                              "mods/provide-uno-lora-k2-horizon-7b"))
        self.assertEqual(mod_reference_violations(mutated), [f"mods/{UNO_MOD}"])

    def test_uno_without_the_fa4_gate_is_caught(self):
        # The scoped I6 waiver: drop the gate mod and the UNO flag is forbidden again.
        mutated = parse_text(self.raw.replace(f'  - "mods/{UNO_GATE_MOD}"\n', ""))
        self.assertNotIn(f"mods/{UNO_GATE_MOD}", mod_list(mutated))
        self.assertTrue(uno_waiver_violations(mutated))

    def test_tp2_is_caught(self):
        mutated = parse_text(self.raw.replace("tensor_parallel: 1", "tensor_parallel: 2"))
        self.assertTrue(single_device_violations(mutated))

    def test_wrong_adapter_path_is_caught(self):
        mutated = parse_text(self.raw.replace(
            "uno_lora_path: /cache/runtime/uno-lora/K2-Horizon-0.9B-Uno",
            "uno_lora_path: /cache/runtime/uno-lora/7B-Uno"))
        self.assertTrue(staging_violations(mutated, self.script))

    def test_unpinned_adapter_is_caught(self):
        self.assertTrue(re.search(r"UNO_LORA_SHA256.*[0-9a-f]{64}", self.script))
        self.assertNotRegex(self.script.replace("5a499229d19ef4a69eb0b21884819d1b67cd983ba02b7ee2031ba8567dedfe4e",
                                                ""),
                            r"UNO_LORA_SHA256.*[0-9a-f]{64}")


# ---------------------------------------------------------------------------

class FilesExist(unittest.TestCase):
    def test_recipes_present(self):
        for p in ALL:
            self.assertTrue(p.exists(), f"missing recipe {p}")

    def test_research_docs_present_when_available(self):
        # The two research docs are git-ignored by design (root AGENTS.md: they
        # hold internal node state), so on a fresh clone they are absent by
        # construction -- skip rather than fail there, but still require them
        # when they are present. COOP.md is no longer tracked at all (removed
        # 2026-10-10: coordination ledgers are temporary, not checked in), so
        # it is not asserted here.
        missing = [n for n in ("K2-09B-JOURNAL.md",
                               "K2-09B-MODEL-OPTIMIZATION-WORK.md")
                   if not (RECIPE_DIR / n).exists()]
        if missing:
            self.skipTest("git-ignored research docs absent (fresh clone): "
                          + ", ".join(missing))


class ForbiddenFlags(unittest.TestCase):
    """I1-I4, I6: flags that make this recipe unable to boot on GB10."""

    FORBIDDEN = [
        (r"--attention-backend\s+fa3\b", "I1: fa3 asserts SM80/90; GB10 is (12,1)"),
        (r"--quantization(\s|=)", "I2: no quant path for this family; fails in weight load"),
        (r"--enable-auto-tool-choice", "I3: vLLM flag, absent from sglang v0.5.20"),
        (r"--hf-overrides", "I4: wrong flag name; YaRN is read from config.json"),
        (UNO_FLAG, "I6: UNO requires (fa3,fa3); cannot boot on SM121"),
    ]
    # fa4 is deliberately NOT in FORBIDDEN: work doc §3.3/§9 arm 2 keeps it as a
    # measurement arm (flashattention_backend.py:284-292 imports an SM12x FA4
    # kernel).  What is not allowed is shipping it as the default -- see
    # test_flashinfer_is_the_declared_backend, which is the binding constraint.

    def test_absent_from_rendered_command(self):
        for path in ALL:
            r = parse(path)
            cmd = render(r)
            for pat, why in self.FORBIDDEN:
                if pat == UNO_FLAG and not uno_waiver_violations(r):
                    # I6 EXCEPTION, scoped not deleted: this arm mounts
                    # mods/probe-uno-fa4-sm121, whose whole purpose is to relax
                    # _handle_uno's ("fa3","fa3") literal to accept the SM12x fa4
                    # backend that GB10 can actually construct (see I1). Without
                    # both the gate mod and attention_backend: fa4, the waiver
                    # reports a violation and this assertion fires on the UNO flag.
                    continue
                self.assertIsNone(
                    re.search(pat, cmd),
                    f"{path.name}: rendered command contains {pat!r} ({why})",
                )

    def test_no_backend_override_hiding_fa3(self):
        """A split backend flag could smuggle fa3 past the I1 check above."""
        for path in ALL:
            cmd = render(parse(path))
            for flag in ("--prefill-attention-backend", "--decode-attention-backend"):
                m = re.search(re.escape(flag) + r"\s+(\S+)", cmd)
                if m:
                    self.assertNotEqual(
                        m.group(1), "fa3",
                        f"{path.name}: {flag} fa3 is still the SM80/90 assert",
                    )

    def test_flashinfer_is_the_declared_backend(self):
        """I1 corollary: whatever we do declare must be buildable on SM121.

        SCOPED, not relaxed: an arm that declares UNO cannot declare flashinfer --
        _handle_uno raises unless the (prefill, decode) pair is ("fa3","fa3"), and
        fa3 is the SM80/90 assert of I1. Its backend must be fa4 (the SM12x kernel
        flashattention_backend.py:284-292 imports), which is legitimate ONLY because
        the arm mounts mods/probe-uno-fa4-sm121 to relax that literal. An UNO arm
        that loses the gate mod fails here via uno_waiver_violations, so the
        exception cannot be inherited by a copy-paste.
        """
        for path in ALL:
            r = parse(path)
            if re.search(UNO_FLAG, render(r)):
                self.assertEqual(
                    uno_waiver_violations(r), [],
                    f"{path.name}: UNO's fa4 waiver needs mods/{UNO_GATE_MOD} and "
                    "attention_backend: fa4 -- _handle_uno's (fa3,fa3) gate is "
                    "unconstructible on GB10",
                )
                continue
            self.assertEqual(r["defaults"].get("attention_backend"), "flashinfer",
                             f"{path.name}: attention_backend must be flashinfer")


class DtypeSpelled(unittest.TestCase):
    def test_bfloat16_not_auto(self):
        for path in ALL:
            r = parse(path)
            self.assertEqual(
                r["defaults"].get("dtype"), "bfloat16",
                "I5: config.json says float32; --dtype auto trusts a lying field",
            )
            self.assertIn("--dtype bfloat16", render(r))


class RevisionReachesEngine(unittest.TestCase):
    def test_pinned_and_forwarded(self):
        for path in ALL:
            r = parse(path)
            pin = r["top"].get("model_revision", "")
            self.assertRegex(
                pin, r"^[0-9a-f]{40}$",
                "I7: model_revision must be a full 40-char commit SHA",
            )
            self.assertIn("--revision " + pin, render(r),
                          "I7: pin declared but not passed to the engine")

    def test_pin_matches_the_remeasured_checkpoint(self):
        for path in ALL:
            self.assertEqual(
                parse(path)["top"].get("model_revision"), MODEL_REVISION,
                f"{path.name} drifts from the re-pinned checkpoint",
            )

    def test_no_foreign_revision_copied_from_card(self):
        """The cards pass --revision 9b9ec1f7e17f..., an sglang commit-ish.

        Checks the *stripped* text: prose in a comment may quote the wrong value
        to explain why it is wrong (F20), but a rendered command may not.
        """
        for path in ALL:
            self.assertIsNone(
                re.search(r"9b9ec1f", parse(path)["stripped"]),
                f"{path.name}: the card's --revision value is from the wrong repo",
            )


class ContainerFloor(unittest.TestCase):
    def test_digest_pinned(self):
        for path in ALL:
            self.assertIn(
                "@sha256:", parse(path)["top"].get("container", ""),
                f"{path.name}: container must be digest-pinned",
            )

    def test_new_enough_to_have_k2_support(self):
        for path in ALL:
            c = parse(path)["top"].get("container", "")
            m = re.search(r"sglang:v(\d+)\.(\d+)\.(\d+)", c)
            self.assertIsNotNone(m, f"{path.name}: cannot read sglang version from {c!r}")
            got = tuple(int(x) for x in m.groups()[:3])
            self.assertGreaterEqual(
                got, MIN_SGLANG,
                f"{path.name}: sglang {got} predates models/xllm.py; "
                "K2HorizonForCausalLM is not registered there",
            )


class ParserFlagsPresent(unittest.TestCase):
    """The card's best-practices item 5 asks for both parsers; its own SGLang
    block names only the reasoning one.  Both are registered in v0.5.20."""

    def test_both_k2_horizon_parsers(self):
        for path in ALL:
            cmd = render(parse(path))
            self.assertIn("--reasoning-parser k2_horizon", cmd)
            self.assertIn("--tool-call-parser k2_horizon", cmd)


class DefaultsAreConsumed(unittest.TestCase):
    """I8: a defaults key with no placeholder is silently not a setting."""

    def test_every_default_used_by_a_placeholder(self):
        for path in ALL:
            r = parse(path)
            for key in r["defaults"]:
                if key in ENGINE_PLACEHOLDERS:
                    continue
                self.assertIn(
                    "{" + key + "}", r["command"],
                    f"{path.name}: defaults key {key!r} is never referenced by "
                    "a placeholder, so it is not a setting",
                )

    def test_every_placeholder_has_a_default(self):
        for path in ALL:
            r = parse(path)
            for ph in re.findall(r"\{([a-z0-9_]+)\}", r["command"]):
                if ph in ENGINE_PLACEHOLDERS or ph == "model_revision":
                    continue
                self.assertIn(
                    ph, r["defaults"],
                    f"{path.name}: placeholder {{{ph}}} has no defaults: entry",
                )


class CommandShape(unittest.TestCase):
    """I9: folded scalar, no `#` inside the block, no plain quoted scalar."""

    def test_no_hash_inside_command_block(self):
        for path in ALL:
            lines = path.read_text(encoding="utf-8").splitlines()
            in_cmd = False
            for i, line in enumerate(lines, 1):
                if re.match(r"^command:\s*>", line):
                    in_cmd = True
                    continue
                if in_cmd:
                    if line and not line.startswith(" "):
                        break
                    self.assertNotIn(
                        "#", line,
                        f"{path.name}:{i}: '#' inside command: is passed to the shell",
                    )

    def test_folded_not_plain_scalar(self):
        for path in ALL:
            self.assertIsNotNone(
                re.search(r"^command:\s*>", path.read_text(encoding="utf-8"), re.M),
                f"{path.name}: command must be a folded scalar (`command: >`)",
            )

    def test_extra_args_last(self):
        for path in ALL:
            r = parse(path)
            self.assertTrue(
                r["command"].rstrip().endswith("{extra_args}"),
                f"{path.name}: escape hatch must be appended last so argparse "
                "resolves a repeated flag in favour of the override",
            )


class NegativeControls(unittest.TestCase):
    """A guard that cannot fail proves nothing (AGENTS.md §5)."""

    def test_drifted_revision_would_be_detected(self):
        mutated = BASE_09B.read_text(encoding="utf-8").replace(
            MODEL_REVISION, "9fa6faa55fe1c9eb008bb241cc6fb7e4536d0e91")
        pin = re.search(r"^model_revision:\s*(\S+)", mutated, re.M).group(1)
        self.assertNotEqual(pin, MODEL_REVISION)
