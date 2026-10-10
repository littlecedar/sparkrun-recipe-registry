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
ALL = [BASE_09B]

# sglang's own flag names, as emitted by the recipe (sparkrun fills
# placeholders from `defaults:`, so guards match the *rendered* form).
ENGINE_PLACEHOLDERS = {"model", "model_path", "host", "port"}

# The first released tag containing python/sglang/srt/models/xllm.py.  Verified
# by tree listing: present at v0.5.20, absent at v0.5.19 and earlier.  Any image
# older than this does not know what K2HorizonForCausalLM is.
MIN_SGLANG = (0, 5, 20)


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


def parse(path: Path) -> dict:
    """Return {top: str, defaults: {k: v}, command: str, stripped: str}."""
    text = _strip_comment_lines(path.read_text(encoding="utf-8"))
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
    return {"top": top, "defaults": defaults, "command": command.strip(),
            "stripped": text, "raw": path.read_text(encoding="utf-8")}


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
        (r"--speculative-algorithm\s+UNO\b", "I6: UNO requires (fa3,fa3); cannot boot on SM121"),
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
        """I1 corollary: whatever we do declare must be buildable on SM121."""
        for path in ALL:
            r = parse(path)
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
