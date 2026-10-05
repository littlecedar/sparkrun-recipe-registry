"""Guards for the IFM K2-Horizon MoVA-36B-A4B Spark recipes.

Run:
    python3 -m unittest discover -s tests

Stdlib-only, and parses recipe TEXT with regex rather than importing PyYAML, so the
guards survive a sparkrun upgrade and run on any lab machine (AGENTS.md).

These are the 36B-A4B lane's own guards. `tests/test_ifm_recipes.py` guards the
0.9B recipes and `tests/test_k2_7b_recipes.py` the 7B; the three files deliberately
do not share a parser, because a shared parser means one broken parser silently
disables three lanes' coverage.

Why each invariant exists. Every claim is VERIFIED against sglang source at a named
file:line at commit `95521da` (2026-09-20) and re-confirmed at release tag
`v0.5.20`, unless marked otherwise. Long-form reasoning lives in
`K2-36B-A4B-MODEL-OPTIMIZATION-WORK.md`; the citations here are self-contained
because that file is git-ignored and so is not available to a CI checkout.

  I1  never `--attention-backend fa3`
        `layers/attention/attention_registry.py:227-235` asserts
        `(major == 8 and not use_mla) or major == 9`. GB10 reports (12, 1)
        (`utils/common.py:332-333`, `is_sm121`). The HF model card and the SGLang
        cookbook both pass `fa3` because both were written on Hopper, so copying
        them is the single most likely way to ship a recipe that cannot boot.
        (Same invariant the 0.9B lane enforces for its own files; enforced here
        independently because the files are different.)
  I2  the FP8 recipes must mount the gate mod, and the BF16 recipe must not
        `models/xllm.py:664` raises unless the resolved quant method is
        "compressed_tensors" or (after the mod) "fp8", and `:1229` raises on any
        non-None quant_config on a MoVA layer. `IFM/K2-Horizon-MoVA-36B-A4B-FP8`
        announces `quant_method: "fp8"` (VERIFIED from the checkpoint), so the FP8
        arms cannot boot without the mod -- and a recipe that silently lost the mod
        would fail at launch with an engine error that looks like a model bug.
        Conversely the BF16 recipe must NOT mount it: it has no
        quantization_config, both gates pass on their own terms, and patching a
        runtime you do not need to patch is exactly what the `patched` tag exists to
        make visible.
  I3  the falsification arm must have an EMPTY mods list
        `zz-k2-36b-a4b-fp8-unpatched-probe-sglang.yaml` exists to observe the
        unpatched failure. The moment someone adds the mod to it, it stops being a
        falsification arm and becomes a misleading duplicate. `sparkrun recipe
        validate` does not resolve `mods:` entries at all (VERIFIED by the 7B agent
        by corrupting a mod ref: exit 0), so this can only be caught here.
  I4  `--dtype bfloat16` spelled, never `auto`
        `models/xllm.py:669-671` requires the runtime default dtype to be
        bfloat16. `configs/model_config.py:2078-2124` resolves `auto` from the
        *declared* config dtype and quietly maps a declared float32 onto float16 for
        any non-gemma model_type. This checkpoint declares bfloat16 honestly, so
        `auto` works here by luck -- which is precisely why it must not be relied
        on: the 0.9B sibling declares float32 and would be launched fp16.
  I5  TP on an FP8 arm is 1 or 2, never 4 or 8
        `Fp8MoEMethod.create_weights` (`layers/quantization/fp8.py:1368-1390`)
        requires `moe_intermediate_size / TP % block_n == 0` for block-quant.
        Here `moe_intermediate_size = 768` and `weight_block_size = [128, 128]`
        (both VERIFIED from the checkpoint), so 768/4 = 192 and 768/8 = 96 fail.
        It raises at model build, i.e. after a 48 GB sync to every node.
  I6  `--revision` reaches the engine, and is not the value from the model card
        sparkrun syncs a SHA-pinned model into `snapshots/<sha>/` and writes no
        `refs/` entry, while the container runs with `HF_HUB_OFFLINE=1`; an engine
        that resolves its own revision dies with LocalEntryNotFoundError after the
        full download. Separately, the card's `--revision 9b9ec1f7e17f...` is an
        *sglang* commit-ish and 404s against every `IFM/K2-Horizon-*` repo (whose
        refs are `pretrain_*`, `mid_1_*`, `mid_2_*`, `rl_*`, `main`) -- VERIFIED
        2026-09-21 by the 0.9B agent and independently here.
  I7  a digest-pinned container at or above the K2 support floor
        `models/xllm.py` does not exist before sglang `v0.5.20` (sglang#37654,
        merge `3bac084d4`, 2026-09-03; `v0.5.20` published 2026-09-18 with an
        arm64/linux manifest). A moving `dev-*` tag is not a version guarantee, so
        the digest is pinned as well as the tag.
  I8  the mod's version stamp, the recipes' declared pins, and this test agree
        A patch whose anchors no longer match the container is a silent no-op if
        nobody checks; the stamp triangle means bumping the mod without updating the
        recipes (or vice versa) fails here rather than on a node.
  I9  every `defaults:` key is consumed by a placeholder and vice versa
        sparkrun renders unmapped defaults silently and prints "unmapped" for a
        `-o key=...` that no placeholder consumes, while the substitution still
        happens. A default nothing reads is not a setting, and a placeholder nothing
        sets is a crash in the rendered command.
  I10 the `command:` block is a folded scalar with no `#` inside it
        A `#` inside the folded scalar is data, not a comment, and reaches the
        shell. A plain (non-folded) scalar folds the whole command onto one line and
        dies on YAML's line handling.
  I11 `extra_args` is LAST in the command
        argparse resolves a repeated flag in favour of the last occurrence, so an
        override placed before the templated flags is silently ignored.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import k2_36b_arith  # noqa: E402  canonical arithmetic, imported not duplicated
RECIPE_DIR = ROOT / "recipes" / "ifm"
MOD_DIR = ROOT / "mods" / "patch-sglang-k2-horizon-fp8"

FP8_TP1 = RECIPE_DIR / "k2-horizon-36b-a4b-fp8-tp1-sglang.yaml"
FP8_TP2 = RECIPE_DIR / "k2-horizon-36b-a4b-fp8-tp2-sglang.yaml"
BF16_TP1 = RECIPE_DIR / "k2-horizon-36b-a4b-bf16-tp1-sglang.yaml"
PROBE = RECIPE_DIR / "zz-k2-36b-a4b-fp8-unpatched-probe-sglang.yaml"

ALL = [FP8_TP1, FP8_TP2, BF16_TP1, PROBE]
FP8_ARMS = [FP8_TP1, FP8_TP2]

MOD_REF = "mods/patch-sglang-k2-horizon-fp8"
K2_FLOOR = (0, 5, 20)
EXPECTED_MOD_VERSION = "1.0.0"
EXPECTED_SGLANG_COMMIT = "95521da"


# ---------------------------------------------------------------------------
# minimal recipe reader (stdlib only, see module docstring)
# ---------------------------------------------------------------------------
def _strip(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


def parse(path: Path) -> dict:
    text = _strip(path.read_text(encoding="utf-8"))
    top, defaults, command, mods = {}, {}, "", []
    section = None
    for line in text.splitlines():
        if not line.strip():
            continue
        if not line.startswith(" ") and ":" in line:
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip()
            if val in (">", "|", ">-", "|-", "|+", ">-"):
                section = key
                continue
            if not val:
                section = key
                continue
            section = None
            top[key] = val.strip("'\"")
            continue
        if section == "defaults" and line.startswith("  ") and ":" in line:
            s = line.strip()
            if s.startswith("- "):
                continue
            key, _, val = s.partition(":")
            defaults[key.strip()] = val.strip().strip("'\"")
        elif section == "mods" and line.strip().startswith("- "):
            mods.append(line.strip()[2:].strip().strip("'\""))
        elif section == "command":
            command += " " + line.strip()
    return {"top": top, "defaults": defaults, "command": command.strip(),
            "mods": mods, "raw": path.read_text(encoding="utf-8"),
            "stripped": text}


def render(r: dict) -> str:
    out = r["command"]
    for k, v in r["defaults"].items():
        out = out.replace("{" + k + "}", v)
    for k in ("model", "model_revision", "host", "port"):
        if k in r["top"]:
            out = out.replace("{" + k + "}", r["top"][k])
    return re.sub(r"\s+", " ", out)


PARSED = {p: parse(p) for p in ALL}


# ---------------------------------------------------------------------------
class FilesExist(unittest.TestCase):
    def test_recipes_present(self):
        for p in ALL:
            self.assertTrue(p.is_file(), f"missing recipe {p}")

    def test_recipes_are_valid_yaml(self):
        """Every other guard in this file parses recipe TEXT with regex after
        stripping comments, so a guard suite can be fully green on a YAML file that
        does not parse -- which is exactly what happened here when an inserted
        comment block inherited 3-space indentation and desynchronised the
        `defaults:` mapping. The regex reader never noticed, because comments are
        removed before it looks. This test is the only thing between a stray indent
        and a recipe that fails at launch time on a node.

        No PyYAML dependency (AGENTS.md: stdlib-only, survive a sparkrun upgrade),
        so this is a structural check rather than a full parse: every line is either
        blank, a comment, or `key:`/`key: value` at an indent that is a multiple of
        two spaces, and the document has exactly one top-level mapping with no
        duplicate top-level keys. That catches the real failure class (bad indent,
        tab, duplicated key, stray text) without a parser.
        """
        for p in ALL:
            raw = p.read_text(encoding="utf-8")
            top = []
            for n, line in enumerate(raw.split("\n"), 1):
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                self.assertNotIn("\t", line[: len(line) - len(line.lstrip())],
                                 f"{p.name}:{n}: tab in indentation")
                indent = len(line) - len(line.lstrip())
                self.assertEqual(indent % 2, 0,
                                 f"{p.name}:{n}: indent {indent} is not a multiple of "
                                 "2 -- YAML will mis-nest this mapping")
                if indent == 0:
                    key = line.split(":", 1)[0].strip()
                    self.assertRegex(key, r"^[a-z_]+$",
                                     f"{p.name}:{n}: unexpected top-level token {line!r}")
                    top.append(key)
            dupes = {k for k in top if top.count(k) > 1}
            self.assertFalse(dupes, f"{p.name}: duplicate top-level keys {sorted(dupes)}")

    def test_defaults_block_is_uniformly_indented(self):
        """The specific shape of the mistake above: one key in `defaults:` sitting at
        a different indent from its siblings."""
        for p in ALL:
            raw = p.read_text(encoding="utf-8")
            m = re.search(r"(?m)^defaults:\n((?:[ \t].*\n?)+)", raw)
            self.assertIsNotNone(m, f"{p.name}: no defaults block")
            body = [l for l in m.group(1).split("\n") if l.strip()]
            keys = {len(l) - len(l.lstrip())
                    for l in body if not l.lstrip().startswith("#")}
            self.assertEqual(len(keys), 1,
                             f"{p.name}: defaults keys sit at multiple indents "
                             f"{sorted(keys)} -- this is a YAML parse error, not a style "
                             "question")

    def test_docs_present(self):
        for name in ("K2-36B-A4B-JOURNAL.md", "K2-36B-A4B-MODEL-OPTIMIZATION-WORK.md"):
            self.assertTrue((RECIPE_DIR / name).is_file(), f"missing {name}")

    def test_mod_files_present(self):
        for name in ("run.sh", "unpatch.sh", "README.md", "test_k2_fp8_guard.py"):
            self.assertTrue((MOD_DIR / name).is_file(), f"missing {MOD_DIR / name}")


# ---------------------------------------------------------------------------
class I1NoFa3(unittest.TestCase):
    def test_fa3_absent_from_rendered_commands(self):
        for p in ALL:
            cmd = render(PARSED[p])
            self.assertNotIn("--attention-backend fa3", cmd,
                             f"{p.name}: fa3 cannot be constructed on (12,1)")

    def test_no_backend_override_smuggles_fa3(self):
        for p in ALL:
            extra = PARSED[p]["defaults"].get("extra_args", "")
            self.assertNotIn("fa3", extra,
                             f"{p.name}: extra_args must not reintroduce fa3")

    def test_flashinfer_declared_where_we_set_a_backend(self):
        for p in ALL:
            ab = PARSED[p]["defaults"].get("attention_backend")
            if ab is not None:
                self.assertEqual(ab, "flashinfer",
                                 f"{p.name}: attention_backend={ab} on GB10 needs "
                                 "a stated reason in the recipe, and none of the "
                                 "36B arms has one")


# ---------------------------------------------------------------------------
class I2ModWiring(unittest.TestCase):
    def test_fp8_arms_mount_the_mod(self):
        for p in FP8_ARMS:
            self.assertIn(MOD_REF, PARSED[p]["mods"],
                          f"{p.name}: the FP8 checkpoint cannot boot without the "
                          "gate mod; a missing mod surfaces as an engine error")

    def test_bf16_arm_does_not_mount_the_mod(self):
        self.assertNotIn(MOD_REF, PARSED[BF16_TP1]["mods"],
                         "BF16 has no quantization_config; both gates pass, so "
                         "patching the runtime here is unneeded and would make the "
                         "`patched` tag a lie in the other direction")

    def test_patched_arms_are_tagged(self):
        for p in FP8_ARMS:
            raw = PARSED[p]["raw"]
            self.assertRegex(raw, r"tags:.*patched",
                             f"{p.name}: AGENTS.md requires a patched runtime to "
                             "declare itself in metadata.tags")

    def test_unpatched_arms_are_not_tagged_patched(self):
        for p in (BF16_TP1, PROBE):
            tags = re.search(r"^\s*tags:\s*(.+)$", PARSED[p]["raw"], re.M)
            self.assertIsNotNone(tags, f"{p.name}: no tags line")
            self.assertNotIn("patched", tags.group(1),
                             f"{p.name}: claims patched but mounts no patch mod")


# ---------------------------------------------------------------------------
class I3FalsificationArm(unittest.TestCase):
    def test_probe_has_empty_mods(self):
        self.assertEqual(PARSED[PROBE]["mods"], [],
                         "the falsification arm's whole value is that nothing is "
                         "patched; adding a mod makes it a misleading duplicate")

    def test_probe_declares_its_own_prediction(self):
        raw = PARSED[PROBE]["raw"]
        self.assertIn("compressed-tensors quantized model weights", raw,
                      "a falsification arm must state the message it expects, "
                      "written before the boot")

    def test_probe_is_small(self):
        d = PARSED[PROBE]["defaults"]
        self.assertLessEqual(int(d["max_model_len"]), 8192)
        self.assertLessEqual(int(d["max_num_seqs"]), 4)


# ---------------------------------------------------------------------------
class I4Dtype(unittest.TestCase):
    def test_bfloat16_everywhere(self):
        for p in ALL:
            self.assertEqual(PARSED[p]["defaults"].get("dtype"), "bfloat16",
                             f"{p.name}: --dtype auto resolves through the "
                             "declared config dtype and can land on float16")

    def test_dtype_reaches_the_engine(self):
        for p in ALL:
            self.assertIn("--dtype {dtype}", PARSED[p]["command"],
                          f"{p.name}: dtype is a default nobody reads")


# ---------------------------------------------------------------------------
class I5TpCeiling(unittest.TestCase):
    MOE_INTERMEDIATE = 768
    BLOCK_N = 128

    def test_fp8_tp_divides_blockwise(self):
        for p in FP8_ARMS:
            tp = int(PARSED[p]["defaults"]["tensor_parallel"])
            self.assertLessEqual(tp, 2,
                                 f"{p.name}: TP={tp} makes "
                                 f"{self.MOE_INTERMEDIATE}/{tp}="
                                 f"{self.MOE_INTERMEDIATE // tp}, not divisible by "
                                 f"block_n={self.BLOCK_N}; Fp8MoEMethod."
                                 "create_weights raises at model build, i.e. after "
                                 "48 GB has synced to every node")
            self.assertEqual(self.MOE_INTERMEDIATE % (self.BLOCK_N * tp), 0)

    def test_tp2_is_the_two_node_case(self):
        self.assertEqual(PARSED[FP8_TP2]["top"].get("min_nodes"), "2")
        self.assertEqual(PARSED[FP8_TP2]["top"].get("max_nodes"), "2")
        self.assertEqual(PARSED[FP8_TP1]["top"].get("max_nodes"), "1")

    def test_tp2_does_not_hardcode_interface_names(self):
        env = PARSED[FP8_TP2]["stripped"]
        # mods/make-roce-env renders these from host facts; a hardcoded name here
        # is both wrong on any box whose interface is not eth0 and prefixed wrong
        # besides (sglang/NCCL read the unprefixed name).
        self.assertNotIn("SGLANG_NCCL_SOCKET_IFNAME", env)
        self.assertNotRegex(env, r"NCCL_SOCKET_IFNAME:\s*[\"']?eth0")


# ---------------------------------------------------------------------------
class I6Revision(unittest.TestCase):
    def test_pinned_and_forwarded(self):
        for p in ALL:
            rev = PARSED[p]["top"].get("model_revision", "")
            self.assertRegex(rev, r"^[0-9a-f]{40}$",
                             f"{p.name}: model_revision must be a 40-char SHA")
            self.assertIn("--revision {model_revision}", PARSED[p]["command"],
                          f"{p.name}: a pinned revision the engine never sees is "
                          "not a pin")

    def test_no_foreign_revision_copied_from_card(self):
        for p in ALL:
            self.assertNotIn("9b9ec1f7", PARSED[p]["raw"],
                             f"{p.name}: that is the card's sglang commit-ish and "
                             "404s against IFM/K2-Horizon-* repos")

    def test_fp8_and_bf16_pin_different_repos_correctly(self):
        # the two checkpoints are different repos; a copy-paste that pins the FP8
        # SHA on the BF16 recipe would fail to resolve offline
        self.assertEqual(PARSED[FP8_TP1]["top"]["model"],
                         "IFM/K2-Horizon-MoVA-36B-A4B-FP8")
        self.assertEqual(PARSED[BF16_TP1]["top"]["model"],
                         "IFM/K2-Horizon-MoVA-36B-A4B")
        self.assertNotEqual(PARSED[FP8_TP1]["top"]["model_revision"],
                            PARSED[BF16_TP1]["top"]["model_revision"])
        self.assertEqual(PARSED[FP8_TP1]["top"]["model_revision"],
                         PARSED[FP8_TP2]["top"]["model_revision"],
                         "the matched pair must differ in exactly one variable")


# ---------------------------------------------------------------------------
class I7Container(unittest.TestCase):
    def test_digest_pinned(self):
        for p in ALL:
            c = PARSED[p]["top"].get("container", "")
            self.assertRegex(c, r"@sha256:[0-9a-f]{64}$",
                             f"{p.name}: tag-only pins are moving targets")

    def test_at_or_above_k2_support_floor(self):
        for p in ALL:
            m = re.search(r"sglang:v(\d+)\.(\d+)\.(\d+)",
                          PARSED[p]["top"]["container"])
            self.assertIsNotNone(m, f"{p.name}: cannot read a version")
            got = tuple(int(x) for x in m.groups())
            self.assertGreaterEqual(got, K2_FLOOR,
                                    f"{p.name}: models/xllm.py is absent below "
                                    f"v{K2_FLOOR[0]}.{K2_FLOOR[1]}.{K2_FLOOR[2]}")

    def test_one_image_across_the_family(self):
        imgs = {PARSED[p]["top"]["container"] for p in ALL}
        self.assertEqual(len(imgs), 1,
                         "different images across the pair make the comparison "
                         "worthless and double the sync cost")


# ---------------------------------------------------------------------------
class I8VersionStamp(unittest.TestCase):
    def mod_version(self):
        txt = (MOD_DIR / "run.sh").read_text(encoding="utf-8")
        m = re.search(r'^MOD_VERSION="([^"]+)"', txt, re.M)
        self.assertIsNotNone(m, "mod has no MOD_VERSION")
        return m.group(1)

    def mod_expected_sglang(self):
        txt = (MOD_DIR / "run.sh").read_text(encoding="utf-8")
        m = re.search(r'^EXPECTED_SGLANG="([^"]+)"', txt, re.M)
        self.assertIsNotNone(m, "mod has no EXPECTED_SGLANG")
        return m.group(1)

    def test_mod_version_matches_this_test(self):
        self.assertEqual(self.mod_version(), EXPECTED_MOD_VERSION,
                         "mod bumped without updating the guard triangle")

    def test_expected_sglang_matches_this_test(self):
        self.assertEqual(self.mod_expected_sglang(), EXPECTED_SGLANG_COMMIT)

    def test_recipes_declare_the_mod_version(self):
        v = self.mod_version()
        for p in FP8_ARMS:
            self.assertIn(f"patch-sglang-k2-horizon-fp8@{v}", PARSED[p]["raw"],
                          f"{p.name}: metadata must record WHICH mod version the "
                          "numbers came from, or a later mod edit silently "
                          "re-interprets them")

    def test_recipes_declare_the_engine_commit(self):
        for p in FP8_ARMS:
            self.assertIn(EXPECTED_SGLANG_COMMIT, PARSED[p]["raw"],
                          f"{p.name}: the patch is anchored to a commit; record it")

    def test_guard_test_covers_the_mod_verifier(self):
        # the verifier's exit-code contract is the mod's only automated evidence;
        # if it stops being executable the README's instructions silently rot
        guard = MOD_DIR / "test_k2_fp8_guard.py"
        self.assertIn("HARNESS_FAIL", guard.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
class I9PlaceholderHygiene(unittest.TestCase):
    def test_every_default_is_consumed(self):
        for p in ALL:
            r = PARSED[p]
            for k in r["defaults"]:
                self.assertIn("{" + k + "}", r["command"],
                              f"{p.name}: defaults.{k} is read by nobody -- "
                              "sparkrun renders unmapped defaults silently")

    def test_every_placeholder_has_a_source(self):
        for p in ALL:
            r = PARSED[p]
            for ph in set(re.findall(r"\{([a-z_]+)\}", r["command"])):
                ok = (ph in r["defaults"] or ph in r["top"]
                      or ph in ("model_path",))
                self.assertTrue(ok,
                                f"{p.name}: placeholder {{{ph}}} has no default and "
                                "no top-level key; it survives into the shell")

    def test_extra_args_defaults_empty(self):
        for p in ALL:
            self.assertEqual(PARSED[p]["defaults"].get("extra_args", ""), "")


# ---------------------------------------------------------------------------
class I10CommandShape(unittest.TestCase):
    def test_folded_scalar(self):
        for p in ALL:
            self.assertRegex(PARSED[p]["raw"], r"(?m)^command: >\s*$",
                             f"{p.name}: command must be a folded scalar")

    def test_no_hash_inside_command_block(self):
        for p in ALL:
            m = re.search(r"(?m)^command: >\n((?:[ \t].*\n?)+)",
                          PARSED[p]["raw"])
            self.assertIsNotNone(m, f"{p.name}: cannot locate command block")
            self.assertNotIn("#", m.group(1),
                             f"{p.name}: a '#' inside the folded scalar is data and "
                             "reaches the shell")

    def test_taskset_fast_core_mask(self):
        for p in ALL:
            self.assertIn("taskset -c 5-9,15-19", PARSED[p]["command"],
                          f"{p.name}: the GB10 big.LITTLE fast-core set is a "
                          "measured win elsewhere in the repo; see COOP")

    def test_launches_sglang_serve(self):
        for p in ALL:
            self.assertIn("sglang serve", PARSED[p]["command"])


class I11ExtraArgsLast(unittest.TestCase):
    def test_extra_args_is_last_token(self):
        for p in ALL:
            cmd = PARSED[p]["command"]
            self.assertTrue(cmd.rstrip().endswith("{extra_args}"),
                            f"{p.name}: argparse takes the LAST repeat of a flag, "
                            "so an override earlier in the line is ignored")


# ---------------------------------------------------------------------------
class I12NumericsHonesty(unittest.TestCase):
    """Everything here is theory. The recipes must say so, in prose a reader hits."""

    def test_unmeasured_declared(self):
        for p in ALL:
            raw = PARSED[p]["raw"]
            self.assertRegex(
                raw, r"(?i)(unmeasured|not measured|theory)",
                f"{p.name}: no throughput claim may be shipped without stating "
                "that it is unmeasured")

    def test_no_invented_throughput_number(self):
        # A t/s figure in a recipe is a promise. MODELLED ceilings belong in the
        # workdoc with their assumptions; a bare "18 t/s" in a YAML is folklore.
        for p in ALL:
            for m in re.finditer(r"\b(\d{2,3}(?:\.\d)?)\s*t/s\b",
                                 PARSED[p]["raw"]):
                ctx = PARSED[p]["raw"][max(0, m.start() - 500):m.start()]
                self.assertRegex(
                    ctx,
                    r"(?i)(modelled|estimate|prediction|ceiling|break-even"
                    r"|roofline|decode law|t = F|bytes/B|pure-bandwidth"
                    r"|bandwidth bound|bandwidth-bound|fitted)",
                    f"{p.name}: a bare t/s figure ({m.group(1)}) with no stated "
                    "provenance reads as a measurement")

    def test_d2_gate_advertised_where_the_mod_is_used(self):
        for p in FP8_ARMS:
            self.assertIn("D2", PARSED[p]["raw"],
                          f"{p.name}: the patched arms must name the numerics gate "
                          "that gates their own numbers")


class I13MetadataTokens(unittest.TestCase):
    """sparkrun checks three metadata fields against fixed vocabularies
    (`sparkrun/core/recipe.py:1439-1484`) and emits a `suggestion` for anything else.
    Suggestions do not block a launch, so this is hygiene rather than correctness --
    but it is free hygiene, and prose belongs in the comment above the key, where the
    next reader will actually find it.

    The sets are copied from sparkrun source on 2026-09-21 (installed under
    ~/.local/share/uv/tools/sparkrun). If sparkrun adds a token, add it here too; a
    false failure here is a two-line fix, whereas prose in the token field is a
    permanent smell on every `recipe validate` of a working recipe.
    """

    QUANT = {"awq", "gptq", "marlin", "fp8", "nvfp4", "mxfp4", "bitsandbytes",
             "compressed-tensors", "auto-round", "autoround", "auto_round", "gguf",
             "int4", "int8", "none"}
    # model_dtype must be parseable by sparkrun.models.vram.bytes_per_element; these
    # are the spellings used across this repo. Extend, do not relax to "anything".
    MODEL_DTYPES = {"fp8_e4m3", "fp8", "bf16", "bfloat16", "fp16", "fp4_e2m1", "nvfp4"}

    def _meta(self, p):
        raw = PARSED[p]["raw"]
        out = {}
        for key in ("model_params", "model_dtype", "kv_dtype", "quantization"):
            m = re.search(r"^  %s:\s*(.+?)\s*$" % key, raw, re.M)
            if m:
                out[key] = m.group(1).strip().strip("'\"")
        return out

    def test_quantization_is_a_known_token(self):
        for p in ALL:
            q = self._meta(p).get("quantization")
            self.assertIsNotNone(q, f"{p.name}: no metadata.quantization")
            self.assertIn(q.lower(), self.QUANT,
                          f"{p.name}: quantization={q!r} draws a validate suggestion; "
                          "use a recognised token and put the prose in the comment "
                          "above the key")

    def test_model_dtype_is_parseable(self):
        for p in ALL:
            md = self._meta(p).get("model_dtype")
            self.assertIsNotNone(md, f"{p.name}: no metadata.model_dtype")
            self.assertIn(md.lower(), self.MODEL_DTYPES,
                          f"{p.name}: model_dtype={md!r} is not a token the VRAM "
                          "estimator can price")

    def test_kv_dtype_is_bf16_or_fp8(self):
        for p in ALL:
            kd = self._meta(p).get("kv_dtype", "bf16")
            self.assertIn(kd.lower(), {"bf16", "bfloat16", "fp8_e4m3", "fp8"},
                          f"{p.name}: kv_dtype={kd!r}")

    def test_fp8_recipe_says_fp8_not_compressed_tensors(self):
        # The whole reason this lane has a mod is that the checkpoint says "fp8" and
        # sglang wants "compressed-tensors". If someone "tidies" this token to match
        # the 7B sibling, the recipe stops describing the artifact it patches.
        for p in FP8_ARMS:
            self.assertEqual(self._meta(p)["quantization"].lower(), "fp8",
                             f"{p.name}: this checkpoint's quant_method is literally "
                             "'fp8'; do not relabel it compressed-tensors")


# ---------------------------------------------------------------------------
class I14SparkrunFlagMap(unittest.TestCase):
    """Two defaults in these recipes are NOT in sparkrun's SGLang flag map and
    therefore reach the engine only as `{placeholder}` in `command:`.

    VERIFIED 2026-09-21 against sparkrun's own source
    (`runtimes/sglang.py:29-88` `_SGLANG_FLAG_MAP`, and
    `core/launcher.py:620-633` `_referenced_placeholders`). The map spells the
    prefill key `chunked_prefill`; these recipes use the family's conventional
    `chunked_prefill_size`, and `page_size` is absent from the map entirely.

    Why this is a test rather than a comment: a key absent from the map is
    *dropped with no error and no trace in the rendered command* (that function's
    own docstring calls out issue #276 for exactly this). The escape hatch is the
    placeholder. So the moment someone deletes a placeholder to silence a warning,
    the setting dies silently and the engine quietly reverts to its own default --
    and the recipe still validates.
    """

    NOT_IN_MAP = ("page_size", "chunked_prefill_size")

    def test_unmapped_defaults_stay_referenced(self):
        for p in ALL:
            r = PARSED[p]
            for k in self.NOT_IN_MAP:
                if k in r["defaults"]:
                    self.assertIn("{" + k + "}", r["command"],
                                  f"{p.name}: defaults.{k} is not in "
                                  "_SGLANG_FLAG_MAP, so without the placeholder it is "
                                  "silently dropped and the engine's own default wins")

    def test_unmapped_keys_are_documented_in_place(self):
        # the "why" must live next to the key, not only in this test
        for p in ALL:
            raw = PARSED[p]["raw"]
            if "page_size:" in raw:
                self.assertRegex(raw, r"(?i)_SGLANG_FLAG_MAP|flag map",
                                 f"{p.name}: carries a key sparkrun does not map; "
                                 "say so above the key")


class I15ArithmeticAgreement(unittest.TestCase):
    """The prose in these recipes quotes roofline numbers. This test makes the
    prose and the arithmetic module agree, because in drafting this lane I shipped
    a roofline that (a) omitted the KV read entirely and (b) dropped the fixed
    per-step cost from the TP=2 leg, producing a table that was wrong by 2x in the
    delta and pointed the TP decision at the wrong context. Nothing in a YAML file
    can tell you a model is wrong; this can at least tell you the model and the
    prose have drifted apart.
    """

    def test_module_selftest_passes(self):
        k2_36b_arith.selftest()

    def test_quoted_weight_total_matches(self):
        want = round(k2_36b_arith.gb(k2_36b_arith.bytes_per_token(True)), 3)
        self.assertEqual(want, 8.489)
        for p in (FP8_TP1, FP8_TP2, BF16_TP1):
            self.assertIn("8.489", PARSED[p]["raw"],
                          f"{p.name}: does not quote the canonical per-token figure")

    def test_quoted_kv_figure_matches(self):
        self.assertEqual(k2_36b_arith.KV_BYTES_PER_TOKEN, 196_608)
        self.assertEqual(round(k2_36b_arith.KV_BYTES_PER_TOKEN / 1024, 1), 192.0)
        for p in (FP8_TP1, FP8_TP2, BF16_TP1):
            raw = PARSED[p]["raw"]
            self.assertTrue("196,608" in raw or "192.0 KiB" in raw or "192 KiB" in raw,
                            f"{p.name}: no canonical KV figure quoted")

    def test_crossover_is_short_context(self):
        # 43 179 tokens: below this, weights dominate; above, KV does.
        self.assertAlmostEqual(k2_36b_arith.kv_crossover_context(), 43_179, delta=200)

    def test_default_context_is_kv_significant(self):
        """The shipped default is 32 768. Crossover is 43 179, so the default sits
        just BELOW crossover with KV already 43 % of the step -- which is the whole
        point: any claim that KV is a capacity-only knob is wrong at the context this
        recipe actually serves."""
        d = int(PARSED[FP8_TP1]["defaults"]["max_model_len"])
        xover = k2_36b_arith.kv_crossover_context()
        self.assertGreater(d, xover / 2, "default context must be in KV-significant range")
        kv = k2_36b_arith.kv_read_bytes(d)
        frac = kv / (kv + k2_36b_arith.bytes_per_token(True))
        self.assertGreater(frac, 0.40, "at the shipped context KV must be a major term")
        # and the TP=2 arm's 131K must be decisively past crossover
        d2 = int(PARSED[FP8_TP2]["defaults"]["max_model_len"])
        self.assertGreater(d2, 2 * xover)

    def test_tp2_break_even_is_context_dependent(self):
        short = k2_36b_arith.tp2_break_even_us(4096)
        long_ = k2_36b_arith.tp2_break_even_us(131_072)
        self.assertGreater(long_, 2 * short,
                           "TP=2 must afford a slower link at long context; if this "
                           "fails the KV term has been dropped from the TP=2 leg again")

    def test_tp2_recipe_quotes_context_dependent_breakeven(self):
        raw = PARSED[FP8_TP2]["raw"]
        self.assertIn("1225", raw.replace(",", ""),
                      f"{FP8_TP2.name}: must quote the 131K break-even, not only a "
                      "short-context one")
        self.assertRegex(raw, r"(?i)context[- ]dependent",
                         f"{FP8_TP2.name}: must state that break-even depends on context")

    def test_fp8_kv_claimed_as_throughput_lever(self):
        """fp8 KV at 32K is a MODELLED +25 %, not a rounding error. A recipe that
        files it as capacity-only is understating the biggest long-context lever
        this model has."""
        gain32 = (k2_36b_arith.decode(32_768, fp8_kv=True)
                  / k2_36b_arith.decode(32_768, fp8_kv=False) - 1)
        self.assertGreater(gain32, 0.20)
        raw = PARSED[FP8_TP1]["raw"]
        self.assertRegex(raw, r"(?i)fp8[- ]kv|kv-cache-dtype",
                         "the recipe must at least name fp8 KV")

    def test_no_stale_weights_only_planning_number(self):
        # "15.0 t/s" is only true for a zero-length context. If it appears as the
        # headline planning number without a context qualifier next to it, the
        # pre-correction model has crept back in.
        for p in ALL:
            for m in re.finditer(r"15\.0 t/s", PARSED[p]["raw"]):
                ctx = PARSED[p]["raw"][max(0, m.start() - 260):m.start()]
                self.assertRegex(
                    ctx, r"(?i)weights only|zero-length|below ~4k|short context",
                    f"{p.name}: '15.0 t/s' must be labelled as the weights-only figure")


# ---------------------------------------------------------------------------
class I16NoStaleClaim(unittest.TestCase):
    """Claims that were true of an earlier draft and are now false. Cheap to test,
    and each one is a real mistake that was actually made here."""

    def test_26_542_not_26_521(self):
        for p in ALL:
            self.assertNotIn("26.521", PARSED[p]["raw"],
                             "routed experts are 26.542 080 GB; 26.521 was a "
                             "transcription error")

    def test_195_not_219_attn_tensors(self):
        for p in ALL:
            self.assertNotRegex(PARSED[p]["raw"], r"\b219 (?:attention|BF16|tensors)")

    def test_mod_name_is_the_one_that_exists(self):
        for p in ALL:
            self.assertNotIn("rewrap-k2-horizon", PARSED[p]["raw"],
                             "that mod was abandoned; see COOP 2026-09-21 correction")
