"""Guards for the DeepSeek V4 / V4.1-Flash Spark recipes.

Run:
    python3 -m unittest discover -s tests -v

Stdlib-only, and deliberately parses recipe TEXT with regex rather than
importing PyYAML: the repo declares jinja2 + netifaces and the offline cache has
no PyYAML, so a test that imports it cannot run on a head node, in a container,
or on a laptop. See AGENTS.md, "tools/ and tests/ are stdlib-only, on purpose".

Why these exist. Most of the checks below defend against a launch that boots,
serves, and returns HTTP 200 with plausible text while being silently wrong or
silently ~3x slower than intended. None of those failures are loud, so the only
defence that costs nothing is a check that runs without hardware.

Every guard has a negative control in NegativeControls, because a guard that
cannot fail proves nothing. The controls mutate strings in memory; nothing on
disk is touched.

F20, the trap this file is built to avoid: recipe prose *names* the flags it
explains the absence of ("--moe-runner-backend is deliberately NOT set...").
_parse() strips whole-line comments before anything reads a block, so the prose
cannot trip the guard that forbids it. CommentBlockProseStillParsed is the
regression test for that.

Sources for the invariants (attic/ds4/AGENTS.md, the archived EXL3-lane guide):
  SGLANG_B12X_MAX_TOKENS == --chunked-prefill-size ....... §9.1: the image's
      b12x prefill gate is sized from this env var
  never --speculative-algorithm NEXTN ..................... sgl#38236 -- crashes
      at arg validation on DeepSeek-V4, unfixed on main 2c05ed4e7
  never EAGLE on a DSpark head ............................ §9: starts, serves,
      accepts nothing, logs "accept rate: 0.00"
  no expandable_segments on V4.1 .......................... §6.4: the 4x Spark
      V4.1 deployment reports NaN logits above 64 prefill query tokens
  every defaults: key consumed by a placeholder ........... §8.3: a defaults
      key with no placeholder is silently not a setting, and this shipped an
      unbootable pair once in this registry
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPE_DIR = REPO_ROOT / "recipes" / "ds4"
# The EXL3 / vLLM lane was retired to the attic when the SGLang knapcio recipe
# was chosen for go-live (2026-10-03). The EXL3 recipes still exist on disk, so
# these guards are retained as frozen regression coverage over archived files;
# they are NOT shipped recipes. New work in recipes/ds4/ targets the SGLang lane
# (SglangLaneContract, below). See attic/ds4/README.md.
ATTIC_DIR = REPO_ROOT / "attic" / "ds4"

# vLLM + cuda-exl3 lane, added 2026-09-23. Third party's measured recipe on the
# EXL3 checkpoint; ours is the sparkrun port.
EXL3_TP4 = ATTIC_DIR / "deepseek-v4.1-flash-exl3-tp4-vllm.yaml"
EXL3_TP4_1M = ATTIC_DIR / "deepseek-v4.1-flash-exl3-tp4-1m-vllm.yaml"
EXL3_TP3 = ATTIC_DIR / "deepseek-v4.1-flash-exl3-tp3-vllm.yaml"
EXL3_TP6 = ATTIC_DIR / "deepseek-v4.1-flash-exl3-tp6-vllm.yaml"
EXL3_TP6_1M = ATTIC_DIR / "deepseek-v4.1-flash-exl3-tp6-1m-vllm.yaml"

ALL = [EXL3_TP4, EXL3_TP4_1M, EXL3_TP3, EXL3_TP6, EXL3_TP6_1M]
EXL3_RECIPES = [EXL3_TP4, EXL3_TP4_1M, EXL3_TP3, EXL3_TP6, EXL3_TP6_1M]  # archived V4.1 vLLM/EXL3 lane

# The mod whose config/speculative.py makes DSpark validate at TP=3/TP=6 by
# applying the recipe's virtual-heads dict overrides to the draft config
# (DSPARK-TP3-STUDY.md, AGENTS.md §10 E7/E8). Pruning this file silently
# reintroduces the "64 heads must be divisible by 3" SpeculativeConfig failure.
MOD_PATCH_DIR = REPO_ROOT / "mods" / "mount-dsv41-exl3-patches"
MOD_PATCH_MOUNTS = MOD_PATCH_DIR / "files" / "mounts.txt"
MOD_PATCH_MD5S = MOD_PATCH_DIR / "files" / "MD5SUMS.txt"
MOD_PATCH_FILE = MOD_PATCH_DIR / "files" / "config_speculative.py"

# Placeholders sparkrun fills from its own resolution rather than `defaults:`.
ENGINE_PLACEHOLDERS = {"model", "model_path", "host", "port"}


# --------------------------------------------------------------------------
# Parsing. Small on purpose: it understands exactly the YAML these recipes use
# (top-level scalars, one-level indented mappings, and `key: >` folded scalars)
# and refuses to guess at anything else.
# --------------------------------------------------------------------------

def _strip_comment_lines(text: str) -> str:
    """Drop whole-line comments. F20: prose documents the forbidden flag."""
    return "\n".join(
        ln for ln in text.splitlines() if not ln.lstrip().startswith("#")
    )


def _unquote(val: str) -> str:
    """Undo one level of YAML quoting.

    Without this, `SGLANG_B12X_MAX_TOKENS: "8192"` parses to the four characters
    `"8192"` and never equals the unquoted `8192` on the command line -- a guard
    that would fail on a correct recipe. Only double and single quotes that wrap
    the whole value are stripped; a bare `expandable_segments:True` must survive
    intact, since its colon is part of the value.
    """
    if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
        return val[1:-1]
    return val


def _block(body_lines: list[str]) -> dict[str, str]:
    """Parse one level of `key: value` mappings from already-dedented lines."""
    out: dict[str, str] = {}
    for ln in body_lines:
        m = re.match(r"^\s+([A-Za-z_][A-Za-z0-9_.]*):\s*(.*)$", ln)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val in (">", ">-", "|", "|-"):
            continue                      # folded; handled by _folded()
        out[key] = _unquote(val)
    return out


def _section(text: str, top_key: str) -> list[str]:
    """Lines belonging to a top-level block key, excluding its own header line.

    A block ends at the next line back at column 0, which is what keeps nested
    `metadata: >-` prose from leaking into `defaults:` and `env:`.
    """
    lines = text.splitlines()
    out: list[str] = []
    inside = False
    for ln in lines:
        if re.match(r"^%s:" % re.escape(top_key), ln):
            inside = True
            continue
        if not inside:
            continue
        if ln.strip() and not ln[0].isspace():
            break
        out.append(ln)
    return out


def _folded(text: str, top_key: str) -> str:
    """Join a `key: >` / `key: >-` folded scalar into one whitespace-normalised line."""
    body = _section(text, top_key)
    parts = []
    for ln in body:
        if not ln.strip():
            continue
        if ln[0].isspace():
            parts.append(ln.strip())
        else:
            break
    return " ".join(parts)


def _scalar(text: str, top_key: str) -> str | None:
    m = re.search(r"^%s:\s*(\S.*?)\s*$" % re.escape(top_key), text, re.M)
    return m.group(1) if m else None


class Recipe:
    """A parsed recipe. Immutable snapshot of one file's guarded surface."""

    def __init__(self, text: str, name: str = "<memory>"):
        self.name = name
        self.raw = text
        clean = _strip_comment_lines(text)
        self.model = _scalar(clean, "model") or ""
        self.runtime = _scalar(clean, "runtime") or ""
        self.container = _scalar(clean, "container") or ""
        mn = _scalar(clean, "min_nodes")
        self.min_nodes = int(mn) if mn and mn.isdigit() else None
        self.env = _block(_section(clean, "env"))
        self.defaults = _block(_section(clean, "defaults"))
        self.command_template = _folded(clean, "command")

    # -- rendering ---------------------------------------------------------
    def rendered(self) -> str:
        """Substitute `defaults:` into the command, the way sparkrun does.

        Guards read the RENDERED command, not the template. A flag hidden behind
        a placeholder is a flag that can be flipped by `--default foo=...` at
        launch, so checking the template would let
        `--speculative-algorithm {speculative_algorithm}` pass a "never NEXTN"
        test while `--default speculative_algorithm=NEXTN` shipped it.
        """
        keys = dict(self.defaults)
        keys.setdefault("model", self.model)
        for name in ENGINE_PLACEHOLDERS:
            keys.setdefault(name, "_")

        def sub(m: re.Match) -> str:
            return str(keys.get(m.group(1), m.group(0)))

        return " ".join(
            re.sub(r"\{([a-z_][a-z0-9_]*)\}", sub, self.command_template).split()
        )

    # -- accessors ---------------------------------------------------------
    def flags(self) -> set[str]:
        return set(re.findall(r"--[a-z0-9][a-z0-9-]*", self.rendered()))

    def flag_value(self, flag: str) -> str | None:
        m = re.search(re.escape(flag) + r"\s+(\S+)", self.rendered())
        return m.group(1) if m else None

    def tp_flag(self) -> str:
        """The tensor-parallel flag, which differs by runtime.

        SGLang spells it `--tp`; vLLM spells it `--tensor-parallel-size`. Both
        lanes are in this directory now, so a guard that hardcodes `--tp` is
        vacuously blind to the vLLM recipes (and vice versa).
        """
        return "--tensor-parallel-size" if self.runtime == "vllm" else "--tp"

    def default(self, key: str) -> str:
        assert key in self.defaults, f"{self.name}: no defaults key {key!r}"
        return self.defaults[key]


def load(path: Path) -> Recipe:
    assert path.exists(), f"missing shipped recipe {path.name}"
    return Recipe(path.read_text(), path.name)


# --------------------------------------------------------------------------
# Guards
# --------------------------------------------------------------------------

class RecipeStructure(unittest.TestCase):
    def test_recipes_exist(self):
        for p in ALL:
            self.assertTrue(p.exists(), f"missing shipped recipe {p.name}")

    def test_parse_and_required_keys(self):
        for p in ALL:
            r = load(p)
            self.assertTrue(r.model, f"{p.name}: no model")
            self.assertIn(r.runtime, ("sglang", "vllm"), p.name)
            self.assertTrue(r.container, f"{p.name}: no container")
            self.assertIsInstance(r.min_nodes, int, f"{p.name}: min_nodes")
            self.assertTrue(r.defaults, f"{p.name}: empty defaults")
            self.assertTrue(r.command_template.strip(), f"{p.name}: empty command")

    def test_parser_acted_on_real_content(self):
        """Empty parse results make every guard below vacuous. Assert otherwise."""
        for p in ALL:
            r = load(p)
            self.assertGreater(len(r.env), 3, f"{p.name}: env block barely parsed")
            self.assertGreater(len(r.defaults), 5, f"{p.name}: defaults barely parsed")
            self.assertIn(r.tp_flag(), r.rendered(), f"{p.name}: command barely parsed")

    def test_tp_matches_min_nodes(self):
        """One GPU per node on Spark, so --tp N needs at least N nodes.

        A TP value above the node count makes every rank open a device ordinal
        that does not exist -- the same failure mode as the fastsafetensors
        global-rank bug, and just as confusing at 3am.
        """
        for p in ALL:
            r = load(p)
            tp = int(r.default("tensor_parallel"))
            self.assertGreaterEqual(r.min_nodes, tp,
                                    f"{p.name}: --tp {tp} but min_nodes {r.min_nodes}")
            self.assertIn(f"{r.tp_flag()} {tp}", r.rendered(),
                          f"{p.name}: tensor-parallel not rendered from defaults")

    def test_no_placeholder_in_env(self):
        """sparkrun does NOT interpolate {placeholders} inside env:.

        If a future sparkrun starts interpolating env:, any literal that was
        written to match a placeholder becomes a latent bug instead of a
        documented one. Fail here so the recipes get updated deliberately.
        """
        for p in ALL:
            for k, v in load(p).env.items():
                self.assertNotIn("{", v,
                                 f"{p.name}: env {k}={v!r} has a placeholder; "
                                 "sparkrun passes env verbatim")


class DefaultsAreConsumed(unittest.TestCase):
    """A defaults key with no placeholder is silently not a setting.

    Inverted from every other guard here, on purpose: this one reads the
    TEMPLATE, because after rendering the placeholders are gone and the question
    "does this key reach the command line at all?" is only answerable there.
    """

    def test_every_default_appears_in_command(self):
        for p in ALL:
            r = load(p)
            for key in r.defaults:
                if key in ENGINE_PLACEHOLDERS:
                    continue
                self.assertIn(
                    "{" + key + "}", r.command_template,
                    f"{p.name}: defaults key {key!r} is never referenced by a "
                    "{...} placeholder, so it configures nothing",
                )

    def test_no_unsatisfied_placeholder(self):
        for p in ALL:
            r = load(p)
            known = set(r.defaults) | ENGINE_PLACEHOLDERS
            for ph in re.findall(r"\{([a-z_][a-z0-9_]*)\}", r.command_template):
                self.assertIn(ph, known, f"{p.name}: {{{ph}}} has no default")


class MillionTokenContext(unittest.TestCase):
    """A 1M-context recipe must ship, and every 1M recipe must render 1M.

    Guarded as a shipped-artifact invariant so it cannot be silently dropped by
    a future retune. Only the recipes named 1M carry the long context; the others
    are deliberately 300K (context is traded for nothing below 1M once
    fresh-vs-fresh, upstream measured 500K free over 300K).
    """

    def test_a_recipe_ships_1m(self):
        million = [p for p in EXL3_RECIPES
                   if int(load(p).default("max_model_len")) >= 1000000]
        self.assertTrue(million, "no EXL3 recipe ships a 1M context")

    def test_every_1m_recipe_is_1m(self):
        """Every recipe whose filename says 1m must actually ask for 1M.

        Covers both the TP=4 and TP=6 1M arms. A copy-paste that forgot to change
        max_model_len would otherwise ship a "1M" recipe that serves 300K.
        """
        named_1m = [p for p in EXL3_RECIPES if "1m" in p.name]
        self.assertTrue(named_1m, "no filename contains 1m")
        for p in named_1m:
            r = load(p)
            self.assertGreaterEqual(
                int(r.default("max_model_len")), 1000000,
                f"{p.name}: filename says 1m but max_model_len is "
                f"{r.default('max_model_len')}",
            )
            self.assertIn("--max-model-len 1000000", r.rendered(), p.name)

    def test_each_1m_recipe_matches_its_300k_sibling_apart_from_context(self):
        """A 1M sibling must differ from its 300K twin in max_model_len ONLY.

        The whole point of shipping a -1m copy is that context is the single
        variable. If a sibling also differs in TP, hf_overrides, spec config or
        the capture sizes, the 1M-vs-300K comparison it exists to support is
        confounded, and the difference should be documented as a new recipe
        rather than hidden in a copy.
        """
        pairs = [
            (EXL3_TP4, EXL3_TP4_1M),
            (EXL3_TP6, EXL3_TP6_1M),
        ]
        # Keys that may legitimately differ (context is the intended one).
        allowed = {"max_model_len"}
        for base, one_m in pairs:
            b, m = load(base), load(one_m)
            self.assertEqual(b.default("tensor_parallel"), m.default("tensor_parallel"),
                             f"{one_m.name}: TP differs from {base.name}")
            shared = set(b.defaults) & set(m.defaults)
            for key in shared - allowed:
                self.assertEqual(
                    b.default(key), m.default(key),
                    f"{one_m.name}: defaults[{key!r}] differs from {base.name} "
                    "— a 1M copy must differ in context only",
                )


class Exl3LaneContract(unittest.TestCase):
    """The EXL3 vLLM lane's load-bearing invariants.

    Each of these, dropped, produces a boot that either OOMs ~25 minutes into a
    460 GB read (Engram on disk) or serves with wrong/absent padding (TP3), and
    none of them fails loudly.
    """

    def test_runtime_and_image_and_model(self):
        for p in EXL3_RECIPES:
            r = load(p)
            self.assertEqual(r.runtime, "vllm", p.name)
            self.assertEqual(r.container, "littlecedar/dgx-spark-dsv41:exl3a",
                             f"{p.name}: the EXL3 patch set and cuda-exl3 plugin "
                             "are only verified against this image")
            self.assertIn("bot-lab-21", r.model,
                          f"{p.name}: the EXL3 checkpoint is the point of the lane")

    def test_description_matches_spec_config(self):
        """`metadata.description` must not contradict the spec-config line.

        Caught in the field 2026-09-25: the TP=3 recipe's description advertised
        "DSpark k=5" while its own body ships NO --speculative-config (the
        drafter's 64 heads and 128 experts do not divide by 3), and three recipes
        still said "UNBOOTED" months after they booted and served. The
        description is prose, so no flag guard sees it; it drifted silently.
        Assert the two halves agree: a no-spec arm must not claim DSpark, a
        DSpark arm must not deny it, and a recipe that has booted must not say
        "UNBOOTED".
        """
        for p in EXL3_RECIPES:
            r = load(p)
            desc = _folded(r.raw, "metadata").lower()
            has_spec = "--speculative-config" in r.flags()
            if has_spec:
                self.assertNotIn(
                    "no dspark", desc,
                    f"{p.name}: ships --speculative-config but the description "
                    "says 'NO DSpark'",
                )
            else:
                self.assertNotIn(
                    "dspark k=", desc,
                    f"{p.name}: no --speculative-config but the description "
                    "advertises a DSpark k value",
                )
            self.assertNotIn(
                "unbooted", desc,
                f"{p.name}: description still says UNBOOTED; all five EXL3 "
                "recipes booted and served on 2026-09-24",
            )

    def test_engram_on_disk_env(self):
        """Without these the 203 GB Engram stays in RAM and the boot OOMs."""
        for p in EXL3_RECIPES:
            r = load(p)
            self.assertEqual(r.env.get("DSV41_ENGRAM_DISK"), "1",
                             f"{p.name}: Engram-on-disk reader must be enabled "
                             "(AGENTS.md §5, §6.5)")
            for key in ("DSV41_ENGRAM_DISK_THREADS", "DSV41_ENGRAM_DISK_CHUNK",
                        "DSV41_ENGRAM_DIR"):
                self.assertIn(key, r.env, f"{p.name}: missing {key}")

    def test_patch_mod_present(self):
        for p in EXL3_RECIPES:
            text = p.read_text()
            self.assertIn("mount-dsv41-exl3-patches", text,
                          f"{p.name}: the mod that installs tonyd2wild's "
                          "engram.py is what makes this boot fit")

    def test_bound_engram_cache_after_patch_mod(self):
        """Every EXL3 recipe must list bound-engram-cache AFTER mount-dsv41.

        `mods:` is an ORDERED chain. `bound-engram-cache` post-patches the engram.py
        that `mount-dsv41-exl3-patches` installs, so it MUST run after it -- reversed,
        it would fire on a missing/unpatched target and (fail-closed) abort the
        launch. It is listed now that it is boot-verified safe/neutral (AGENTS.md
        §7.8.1; MEMORY-RECLAIM-PLAN.md §7).
        """
        for p in EXL3_RECIPES:
            mods = re.findall(r'^\s*-\s*"(@[^"]+)"', p.read_text(), re.M)
            self.assertIn("@littlecedar/mods/bound-engram-cache", mods, p.name)
            self.assertLess(
                mods.index("@littlecedar/mods/mount-dsv41-exl3-patches"),
                mods.index("@littlecedar/mods/bound-engram-cache"),
                f"{p.name}: bound-engram-cache must follow the patch mod it patches",
            )

    def test_consuming_entrypoint_cleared(self):
        """The image's ENTRYPOINT ["vllm","serve"] swallows sparkrun's command.

        sparkrun refuses to launch when an image entrypoint is *confirmed*
        consuming (containers/entrypoint.py), and the fix is an empty
        `executor_config.entrypoint`. Without this key every launch of these
        recipes fails at the pre-launch check, before any GPU is touched.
        """
        for p in EXL3_RECIPES:
            self.assertRegex(
                _strip_comment_lines(p.read_text()),
                r"(?m)^executor_config:\s*\n\s+entrypoint:\s*(\"\"|''|)$",
                f"{p.name}: missing `executor_config: entrypoint: \"\"`; the "
                "exl3a image's entrypoint consumes the appended command",
            )

    def test_dspark_spec_config(self):
        """Every EXL3 recipe ships DSpark on the measured-optimal k, adaptive off.

        Until 2026-09-27 the TP=3 and TP=6 arms were no-spec: the DSpark drafter's
        own 64 attention heads and 128 experts do not divide by 3 or 6, and
        SpeculativeConfig validates the drafter at the target's TP. The fix
        (DSPARK-TP3-STUDY.md, AGENTS.md §10 E7/E8) is the mod's
        config_speculative.py, which applies the recipe's virtual-heads dict
        overrides to the DRAFT config. So all five arms are DSpark arms now;
        assert the positive contract instead of the retired negative one.
        """
        for p in EXL3_RECIPES:
            r = load(p)
            self.assertIn(
                "--speculative-config", r.flags(),
                f"{p.name}: every EXL3 arm ships DSpark since 2026-09-27 "
                "(DSPARK-TP3-STUDY.md); a no-spec arm is the old negative result",
            )
            spec = r.default("speculative_config")
            self.assertIn("dspark", spec, p.name)
            # Adaptive verification must stay off: padded spec batches hang
            # SM120 sparse MLA (FlashInfer #5015).
            self.assertIn('"enable_adaptive_verification":false',
                          spec.replace(" ", ""),
                          f"{p.name}: adaptive verification off is required")
            # A TP=3/TP=6 DSpark arm only validates because the drafter receives
            # the virtual-heads declaration; the recipe must carry it.
            if int(r.default("tensor_parallel")) in (3, 6):
                self.assertIn(
                    "virtual_heads_from", r.defaults.get("hf_overrides", ""),
                    f"{p.name}: TP={r.default('tensor_parallel')} + DSpark needs "
                    "the virtual_heads_from declaration for the drafter to see",
                )

    def test_graph_capture_covers_max_seqs(self):
        """Capture sizes must reach max_num_seqs*(k+1); a truncation cost -12%.

        k is read from the recipe's own speculative_config, NOT hardcoded: the
        measured optimum is k=3 (AGENTS.md §7.7) and the ladder MUST track k
        (k*n and (k+1)*n up to max_num_seqs*(k+1)). A hardcoded k=5 here would
        have silently validated a wrong ladder after the k change.
        """
        for p in EXL3_RECIPES:
            r = load(p)
            cc = r.default("compilation_config")
            self.assertIn("FULL_AND_PIECEWISE", cc, p.name)
            sizes = re.findall(r"\d+", cc.split("cudagraph_capture_sizes")[-1])
            self.assertTrue(sizes, f"{p.name}: no cudagraph_capture_sizes")
            if "--speculative-config" not in r.flags():
                continue  # no-spec arm (none today): k=0, any non-empty list is enough
            m = re.search(r"num_speculative_tokens\D+(\d+)",
                          r.default("speculative_config"))
            self.assertIsNotNone(
                m, f"{p.name}: dspark config has no num_speculative_tokens")
            k = int(m.group(1))
            need = int(r.default("max_num_seqs")) * (k + 1)
            self.assertGreaterEqual(
                max(int(s) for s in sizes), need,
                f"{p.name}: capture sizes top out at {max(map(int, sizes))} < "
                f"{need} = max_num_seqs*(k+1); requests above the max run eager",
            )

    def test_dspark_k_is_measured_optimum(self):
        """The DSpark arms must ship k in the measured-optimal set {1,2,3}.

        A 13-boot sweep (AGENTS.md §7.7, 2026-09-26) found every k in {1,2,3}
        beats the upstream-default k=5 at every concurrency >=4, with the best C1
        at k=3. k=4 is dominated; k=5 is the worst tested. k must also satisfy the
        drafter constraint (k<=5 or k%5==0) -- vLLM rejects k=6 with
        "must be divisible by n_predict=5".
        """
        for p in EXL3_RECIPES:
            r = load(p)
            if "--speculative-config" not in r.flags():
                continue  # no-spec arm (none today): no k to check
            m = re.search(r"num_speculative_tokens\D+(\d+)",
                          r.default("speculative_config"))
            self.assertIsNotNone(m, f"{p.name}: no num_speculative_tokens")
            k = int(m.group(1))
            self.assertIn(k, (1, 2, 3),
                          f"{p.name}: k={k} is not in the measured-optimal set "
                          "{1,2,3}; k=4 is dominated and k=5 is the worst tested "
                          "(AGENTS.md §7.7)")


class ModDraftConfigContract(unittest.TestCase):
    """The mod must keep shipping the DSpark draft-config patch.

    `<mod>/files/config_speculative.py` is what makes DSpark validate at TP=3 and
    TP=6: it applies the recipe's virtual-heads dict overrides to the DRAFT
    config, which stock vLLM deliberately does not (dict hf_overrides are
    target-only). Delete or prune the file from the mod and every TP=3/TP=6
    DSpark arm silently reverts to the "64 heads must be divisible by 3" failure
    the recipes now depend on being fixed. See DSPARK-TP3-STUDY.md, AGENTS.md §10.
    """

    def test_patch_file_present(self):
        self.assertTrue(MOD_PATCH_FILE.is_file(),
                        "the mod's config_speculative.py is what makes TP=3/TP=6 "
                        "+ DSpark validate; it must ship with the mod")

    def test_patch_file_is_whole_file_replacement_with_marker(self):
        """The mod mounts whole files, so the image's own file + our block."""
        text = MOD_PATCH_FILE.read_text()
        self.assertIn("DSV41_DRAFT_VIRTUAL_HEADS", text,
                      "the toggle marker must be present (run.sh asserts it)")
        self.assertIn("compose_draft_hf_overrides", text,
                      "the wrap target must be present, else the patch is inert")
        self.assertIn("virtual_heads_from", text,
                      "the gate key must be present, else the patch is inert")

    def test_registered_in_mounts_and_md5(self):
        mounts = MOD_PATCH_MOUNTS.read_text()
        self.assertIn("config_speculative.py config/speculative.py", mounts,
                      "config_speculative.py must be mapped to config/speculative.py")
        md5s = MOD_PATCH_MD5S.read_text()
        self.assertRegex(
            md5s, r"(?m)^[0-9a-f]{8} +config_speculative\.py$",
            "config_speculative.py must have an md5 entry or the fail-closed "
            "gate does not cover it",
        )

    def test_run_sh_asserts_marker(self):
        run_sh = (MOD_PATCH_DIR / "run.sh").read_text()
        self.assertIn("DSV41_DRAFT_VIRTUAL_HEADS", run_sh,
                      "run.sh must fail closed if the draft-config patch is absent")


class NoHostBindMounts(unittest.TestCase):
    """The EXL3 lane must not ship host bind-mount paths.

    AGENTS.md: "Do not hardcode host machine paths in volumes -- Package patches
    as a `mods:` script instead of host bind mounts." `sparkrun recipe validate`
    warns `non-portable-mount` on any recipe that does, and a host path only the
    author has is a launch that dies on every other node.
    """

    def test_no_volumes_block(self):
        for p in EXL3_RECIPES:
            self.assertNotRegex(
                _strip_comment_lines(p.read_text()), r"^\s*volumes:",
                f"{p.name}: volumes: with host paths warns non-portable-mount; "
                "ship the patch tree as a mod instead",
            )


class BootReadiness(unittest.TestCase):
    """A cold boot reads hundreds of GB. A short timeout is a false bug."""

    def test_timeout_is_generous(self):
        minimum = 3600
        for p in ALL:
            text = p.read_text()
            m = re.search(r"^\s+port_timeout_s:\s*(\d+)\s*$",
                          _strip_comment_lines(text), re.M)
            self.assertIsNotNone(m, f"{p.name}: no readiness.port_timeout_s")
            got = int(m.group(1))
            self.assertGreaterEqual(
                got, minimum,
                f"{p.name}: port_timeout_s {got} < {minimum} -- a 460 GB read "
                "of checkpoint read takes ~10+ min before weights even start moving",
            )


class CommentBlockProseStillParsed(unittest.TestCase):
    """F20 regression: prose must not be mistaken for configuration.

    Recipes deliberately *name* flags they explain the absence of
    ("--speculative-config is deliberately NOT set..."), which is exactly the
    convention that broke an earlier guard in this repo ("``--async-scheduling``
    is deliberately NOT set" tripped the guard forbidding it). This asserts both
    halves on the EXL3 vLLM family: the prose is present, and the guard still
    sees nothing.

    Scoped to the vLLM family on purpose. These recipes legitimately omit
    --enable-expert-parallel and say so in prose; the check proves that prose
    never leaks into the rendered command.
    """

    FORBIDDEN = {"--enable-expert-parallel", "--quantization",
                 "--kv-cache-memory-bytes"}
    # Since 2026-09-27 every EXL3 arm ships DSpark (TP=3/TP=6 included), so this
    # set is empty today. It stays as a tripwire: if a future retune makes an arm
    # no-spec again, the prose that explains it ("--speculative-config is
    # deliberately NOT set") must still not leak into the command. Guarded by
    # Exl3LaneContract.test_dspark_spec_config.
    NO_SPEC_ABSENT = {"--speculative-config"}

    def test_prose_is_present_and_inert(self):
        mentioned = 0
        for p in EXL3_RECIPES:
            text = p.read_text()
            r = load(p)
            hit = r.flags() & self.FORBIDDEN
            self.assertFalse(hit,
                             f"{p.name}: {sorted(hit)} leaked from prose into flags")
            mentioned += len(self.FORBIDDEN & set(re.findall(r"--[a-z-]+", text)))
        self.assertGreater(mentioned, 3,
                           "prose-documented forbidden flags vanished; either the "
                           "recipes got thinner or this test stopped proving anything")

    def test_nospec_prose_does_not_leak_spec_flag(self):
        """If an arm says 'NO --speculative-config' in prose, prove it is inert.

        No arm is no-spec today (all five ship DSpark, 2026-09-27), so this is a
        tripwire for a future retune: an arm that documents the absence of the
        flag must not actually render it from that prose.
        """
        for p in EXL3_RECIPES:
            r = load(p)
            if "--speculative-config" in r.flags():
                continue  # DSpark arms set it for real
            self.assertNotIn(
                "--speculative-config", r.flags(),
                f"{p.name}: a no-spec arm leaked --speculative-config into its "
                "command (from prose or otherwise)",
            )

    def test_comment_only_flag_does_not_count(self):
        """Prove the stripper works, on a self-contained fixture.

        A forbidden flag named in top-level prose (the house convention, and
        precisely what F20 is about) must be invisible to the parser, while the
        same flag on a command line must be caught. Together they show the guard
        is sensitive to the exact thing it claims to be sensitive to, rather than
        passing because it parsed nothing.
        """
        head = ("model: bot-lab-21/DeepSeek-V4.1-Flash-EXL3-3.5bpw-Pollard\n"
                "runtime: vllm\ncontainer: x\nmin_nodes: 4\n"
                "defaults:\n  tensor_parallel: 4\n")
        prose = Recipe(
            head + "# the --speculative-config is deliberately NOT set here\n"
                   "command: >\n  vllm serve {model}\n"
                   "  --tensor-parallel-size {tensor_parallel}\n",
            "prose")
        live = Recipe(
            head + "command: >\n  vllm serve {model}\n"
                   "  --speculative-config '{\"method\":\"dspark\"}'\n"
                   "  --tensor-parallel-size {tensor_parallel}\n",
            "live")
        self.assertNotIn("--speculative-config", prose.flags(),
                         "a flag named only in prose leaked into the command")
        self.assertIn("--speculative-config", live.flags(),
                      "guard is blind: a live flag was not parsed at all")
        self.assertEqual(prose.rendered().split()[-2:],
                         ["--tensor-parallel-size", "4"])

    def test_no_hash_inside_command_block(self):
        """A `#` inside `command: >` is NOT a comment -- it is a shell word.

        YAML block scalars do not carry comments, so a `#` written in the folded
        command survives to the shell, where it silently truncates the rest of
        the launch line. That is a recipe footgun this family must not have, and
        it is why this check reads the RAW section rather than the stripped one
        the other guards use.
        """
        for p in ALL:
            body = _section(p.read_text(), "command")
            for ln in body:
                self.assertNotIn(
                    "#", ln,
                    f"{p.name}: '#' inside command: is passed to the shell, "
                    f"which will truncate the line at it: {ln.strip()!r}",
                )

    def test_control_hash_in_command_is_caught(self):
        fixture = Recipe(
            "model: x\nruntime: sglang\ncontainer: y\nmin_nodes: 1\n"
            "defaults:\n  tensor_parallel: 1\n"
            "command: >\n  sglang serve\n"
            "  # tighten the pool\n  --tp {tensor_parallel}\n",
            "fixture")
        body = _section(
            "command: >\n  sglang serve\n  # tighten the pool\n"
            "  --tp {tensor_parallel}\n", "command")
        self.assertTrue(any("#" in ln for ln in body))
        self.assertTrue(fixture.command_template)  # parse still succeeded


# --------------------------------------------------------------------------
# Negative controls
# --------------------------------------------------------------------------

class NegativeControls(unittest.TestCase):
    """Each guard must be capable of failing. Proven on in-memory strings.

    Nothing here touches disk. Every case rewrites one line of a recipe's text,
    re-parses, and asserts the corresponding invariant now breaks. If a control
    ever stops raising, the guard above it is decoration.
    """

    @staticmethod
    def _mutated(path: Path, old: str, new: str) -> Recipe:
        text = path.read_text()
        assert old in text, f"{path.name}: control anchor {old!r} vanished"
        return Recipe(text.replace(old, new, 1), path.name)

    def test_control_unconsumed_default(self):
        # Anchor on tensor_parallel (a structural property of this recipe, not a
        # tunable number): a control whose anchor is a tunable value breaks the
        # next time someone tunes it, and then nobody trusts the control. (The
        # old anchor, `gpu_memory_utilization: 0.80`, duly broke on the
        # 2026-09-27 retune to 0.85.)
        r = self._mutated(EXL3_TP4, "tensor_parallel: 4",
                          "tensor_parallel: 4\n  kv_pin: 8388608")
        with self.assertRaises(AssertionError):
            for key in r.defaults:
                if key in ENGINE_PLACEHOLDERS:
                    continue
                self.assertIn("{" + key + "}", r.command_template)

    def test_control_parser_refuses_emptiness(self):
        """An empty parse must not look like a passing recipe."""
        with self.assertRaises(AssertionError):
            self.assertGreater(len(Recipe("").env), 3)

    # -- EXL3 vLLM lane (added 2026-09-23) ---------------------------------

    def test_control_exl3_tp2(self):
        """TP=2 must still fail, now via the tp==3-or-4 branch."""
        r = self._mutated(EXL3_TP3, "tensor_parallel: 3", "tensor_parallel: 2")
        with self.assertRaises(AssertionError):
            for p_model in ALL:
                pass
            tp = int(r.default("tensor_parallel"))
            self.assertIn(tp, (3, 4))

    def test_control_exl3_tp3_without_virtual_heads(self):
        """TP=3 without the 72-head declaration is the silent-wrong-shard case."""
        r = self._mutated(
            EXL3_TP3,
            "  hf_overrides: '{\"num_attention_heads\":72,\"o_groups\":9,"
            "\"virtual_heads_from\":{\"num_attention_heads\":64,\"o_groups\":8}}'",
            "  hf_overrides: '{\"num_attention_heads\":64,\"o_groups\":8}'",
        )
        with self.assertRaises(AssertionError):
            self.assertIn("virtual_heads_from", r.rendered())

    def test_control_description_spec_drift(self):
        """Prove the description/spec-config guard can fail."""
        # A DSpark recipe whose description denies it (the inverse of the
        # 2026-09-25 field bug, where a no-spec arm advertised DSpark).
        r = self._mutated(
            EXL3_TP3,
            "Engram streamed from disk, DSpark k=3 (the measured optimum)",
            "Engram streamed from disk, NO DSpark",
        )
        with self.assertRaises(AssertionError):
            has_spec = "--speculative-config" in r.flags()
            self.assertTrue(has_spec)
            self.assertNotIn("no dspark", _folded(r.raw, "metadata").lower())

    def test_control_dspark_spec_config_missing_on_tp3(self):
        """Prove the positive DSpark contract can fail: drop the spec line."""
        r = self._mutated(EXL3_TP3, "  --speculative-config '{speculative_config}'\n", "")
        with self.assertRaises(AssertionError):
            self.assertIn("--speculative-config", r.flags())

    def test_control_tp3_dspark_without_virtual_heads_decl(self):
        """A TP=3 DSpark arm needs virtual_heads_from for the drafter to validate."""
        r = self._mutated(
            EXL3_TP3,
            ",\"virtual_heads_from\":{\"num_attention_heads\":64,\"o_groups\":8}",
            "",
        )
        with self.assertRaises(AssertionError):
            self.assertIn("virtual_heads_from", r.defaults.get("hf_overrides", ""))

    def test_control_mod_patch_file_removed(self):
        """Prove the mod-contract guard can fail: drop the config_speculative line."""
        r = self._mutated(
            MOD_PATCH_MOUNTS,
            "config_speculative.py config/speculative.py",
            "",
        )
        with self.assertRaises(AssertionError):
            self.assertIn("config_speculative.py", r.raw)

    def test_control_mod_md5_entry_removed(self):
        """Prove the md5-table guard can fail."""
        r = self._mutated(
            MOD_PATCH_MD5S,
            "c542580c config_speculative.py",
            "",
        )
        with self.assertRaises(AssertionError):
            self.assertIn("config_speculative.py", r.raw)

    def test_control_engram_disk_off(self):
        r = self._mutated(EXL3_TP4, "DSV41_ENGRAM_DISK: \"1\"",
                          "DSV41_ENGRAM_DISK: \"0\"")
        with self.assertRaises(AssertionError):
            self.assertEqual(r.env.get("DSV41_ENGRAM_DISK"), "1")

    def test_control_bound_engram_cache_before_patch_mod(self):
        """Prove the bound-engram-cache ordering guard can fail.

        Reorders the two entries (the comment block moves with bound-engram-cache)
        so bound-engram-cache precedes the patch mod it post-patches.
        """
        r = self._mutated(
            EXL3_TP4,
            '  - "@littlecedar/mods/mount-dsv41-exl3-patches"\n'
            '  # Bounds the Engram reader\'s host page cache (POSIX_FADV_DONTNEED per batch).\n'
            '  # POST-PATCH: must come AFTER mount-dsv41-exl3-patches. Booted safe/neutral\n'
            '  # 2026-09-27 (KV 4.11M vs 3.97M baseline, 27*43->1161). See AGENTS.md §7.8.1,\n'
            '  # MEMORY-RECLAIM-PLAN.md §7.\n'
            '  - "@littlecedar/mods/bound-engram-cache"',
            '  # Bounds the Engram reader\'s host page cache (POSIX_FADV_DONTNEED per batch).\n'
            '  - "@littlecedar/mods/bound-engram-cache"\n'
            '  - "@littlecedar/mods/mount-dsv41-exl3-patches"',
        )
        mods = re.findall(r'^\s*-\s*"(@[^"]+)"', r.raw, re.M)
        with self.assertRaises(AssertionError):
            self.assertLess(mods.index("@littlecedar/mods/mount-dsv41-exl3-patches"),
                            mods.index("@littlecedar/mods/bound-engram-cache"))

    def test_control_no_1m_recipe(self):
        r = self._mutated(EXL3_TP4_1M, "max_model_len: 1000000",
                          "max_model_len: 300000")
        with self.assertRaises(AssertionError):
            self.assertGreaterEqual(int(r.default("max_model_len")), 1000000)

    def test_control_truncated_capture_sizes(self):
        r = self._mutated(EXL3_TP4,
                          "cudagraph_capture_sizes\":[3,4,6,8,9,12,15,16,18,20,21,24,28,32,36,40,44,48,52,56,60,64]",
                          "cudagraph_capture_sizes\":[3,4,6,8,9,12,15,16]")
        with self.assertRaises(AssertionError):
            cc = r.default("compilation_config")
            sizes = [int(s) for s in re.findall(r"\d+", cc.split("cudagraph_capture_sizes")[-1])]
            # must reach max_num_seqs*(k+1); for the shipped k=3, max_num_seqs=16
            # that is 64
            self.assertGreaterEqual(max(sizes), int(r.default("max_num_seqs")) * 4)


# --------------------------------------------------------------------------
# The SGLang lane: knapcio's native-checkpoint overlay (AGENTS.md §§1-12).
# Separate file + separate assumptions from the
# EXL3 lane: this recipe drives boot.py through a mod shim, needs a node-local
# image, and must NOT enable the SPS ragged-verify table (it crashes the Engram
# path). This lane is ALSO the portability reference: it carries no host bind
# mounts at all -- every cacheable artifact lives under sparkrun's managed
# runtime cache (mounted at /cache/runtime), materialized by the mod and the
# launcher shim.
# --------------------------------------------------------------------------

SGLANG_RECIPE = RECIPE_DIR / "deepseek-v4.1-flash-knapcio-tp4-1m-sglang.yaml"
SGLANG_MOD_DIR = REPO_ROOT / "mods" / "dsv41-sglang-overlay"


def _clean(path: Path) -> str:
    return _strip_comment_lines(path.read_text())


def _launcher_recipe_env() -> dict:
    """The env the mod launcher fills into the container (its RECIPE_ENV).

    The recipe's `env:` is deliberately thin (checkpoint path + TP_SIZE); the
    production configuration lives in mods/dsv41-sglang-overlay/launcher.py so it
    travels with the mod instead of each recipe. The launcher is stdlib-only, so
    importing it here keeps tests/ stdlib-only too.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("dsv41_launcher", SGLANG_MOD_DIR / "launcher.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return dict(mod.RECIPE_ENV)


def _resolved_env(r: "Recipe") -> dict:
    """Guard-side view: launcher RECIPE_ENV overlaid by the recipe's own env.

    This is the union the guards inspect for forbidden keys (host device names,
    managed comm env, DSPARK tables). Note the launcher itself applies RECIPE_ENV
    with ``env.update`` (launcher value wins over a recipe value for launcher-owned
    keys), whereas here the recipe is overlaid last so a *bogus* recipe value is
    visible and the guards can fail on it -- that is the direction these negative
    controls need.
    """
    env = _launcher_recipe_env()
    env.update(r.env or {})
    return env


# Keys sparkrun's InfiniBand probe fills; a recipe/launcher value wins over the
# detected one and pins the adapter naming. Mirrors
# orchestration/infiniband.py:MANAGED_COMM_ENV_KEYS (tests are stdlib-only and
# must not import sparkrun).
MANAGED_COMM_ENV = frozenset({
    "NCCL_NET", "NCCL_IB_HCA", "NCCL_IB_GID_INDEX", "NCCL_IB_DISABLE",
    "NCCL_CROSS_NIC", "NCCL_SOCKET_IFNAME", "NCCL_IGNORE_CPU_AFFINITY",
    "UCX_NET_DEVICES", "NODE_IP",
})
# A literal host adapter/interface name in any env VALUE (the portability trap).
_HOST_DEVICE_RE = re.compile(r"\b(roce|enp|ens|enP|eth)\d?\w*s?\d*f\d", re.I)


class SglangLaneContract(unittest.TestCase):
    """The knapcio SGLang recipe's invariants, all of them boot-learned."""

    def setUp(self):
        self.text = SGLANG_RECIPE.read_text()
        self.r = Recipe(self.text, SGLANG_RECIPE.name)
        self.clean = _strip_comment_lines(self.text)
        self.ec = "\n".join(_section(self.clean, "executor_config"))
        self.dc = "\n".join(_section(self.clean, "distribution_config"))
        self.eff = _resolved_env(self.r)

    def test_runtime_image_model(self):
        self.assertEqual(self.r.runtime, "sglang")
        # Vendored, digest-pinned image (built from knapcio's Dockerfile and
        # pushed to littlecedar); sparkrun pulls it instead of building locally.
        # This digest (4e5002ab…) is the 2026-10-03 rebuild whose baked
        # HEALTHCHECK discovers the served port at runtime.
        self.assertEqual(
            self.r.container,
            "littlecedar/dgx-spark-dsv41:canary-roce"
            "@sha256:4e5002ab58b5cca670e2624c6a0d0799642914f04487ea130c71e7f525fa9c05",
        )
        self.assertEqual(self.r.model, "deepseek-ai/DeepSeek-V4.1-Flash")
        self.assertEqual(self.r.min_nodes, 4)

    def test_recipe_env_is_empty(self):
        # The recipe's env: is EMPTY. Everything -- the production config AND the
        # checkpoint location -- lives in mods/dsv41-sglang-overlay/launcher.py, and
        # the serve parameters (model, tp, context, port) ride in the command
        # template from defaults. In particular SERVER_PORT is NOT set here: the
        # serve port (8000, the recipes' default base port) rides in via the
        # command template and the rebuilt image HEALTHCHECK discovers it at
        # runtime, so no container-level env is needed at all.
        self.assertEqual(self.r.env, {})
        for key in ("MODEL_PATH", "DSV41_SOURCE", "TP_SIZE", "CONTEXT_LENGTH", "SERVER_PORT"):
            self.assertNotIn(key, self.r.env)

    def test_healthcheck_discovers_port_so_no_env_needed(self):
        # The image's baked HEALTHCHECK runs `boot.py health`. The ORIGINAL image
        # probed 127.0.0.1:$SERVER_PORT/health with SERVER_PORT absent from the
        # container's creation env, so it fell back to 8888 and mis-reported a
        # server on any other port as "(unhealthy)". sparkrun cannot template env
        # values, excludes fast healthchecks, and has no recipe-level healthcheck
        # override, so the fix is in the IMAGE: the 2026-10-03 rebuild (digest
        # 4e5002ab…) makes `boot.py health` DISCOVER the served port at runtime
        # (env override -> persisted port file -> the engine's own --port -> a
        # LISTEN port from /proc/net/tcp). Guard the recipe-side half: no env, and
        # the launcher persists the port for the probe.
        self.assertEqual(self.r.env, {})
        launcher = (SGLANG_MOD_DIR / "launcher.py").read_text()
        self.assertIn("HEALTH_PORT_FILE", launcher)
        self.assertIn("/tmp/sparkrun_health_port", launcher)

    def test_port_is_consumed(self):
        # The port is no longer pinned to the image's healthcheck default -- the
        # rebuilt healthcheck follows --port wherever it goes. It still must be
        # carried to boot.py through the command template. 8000 is our recipes'
        # default base port (every ds4 recipe ships it).
        self.assertIn("{port}", self.r.command_template)
        self.assertEqual(self.r.default("port"), "8000")

    def test_context_length_wired_to_launcher(self):
        # `--context-length {max_model_len}` must reach boot.py's CONTEXT_LENGTH.
        # boot.py builds the whole sglang.launch_server argv from the environment,
        # so an unparsed flag would leave CONTEXT_LENGTH at the launcher default
        # and the server would advertise the wrong context (silently).
        self.assertIn("--context-length {max_model_len}", self.r.command_template)
        launcher = (SGLANG_MOD_DIR / "launcher.py").read_text()
        self.assertIn('add_argument("--context-length"', launcher)
        self.assertIn('env["CONTEXT_LENGTH"] = args.context_length', launcher)

    def test_nccl_buffsize_is_not_context_length(self):
        # NCCL_BUFFSIZE is a NCCL *connection buffer* size (pinned memory per
        # connection), unrelated to the token context length; it is a fixed byte
        # count, not derived from the context. Upstream proves independence:
        # .env.example ships NCCL_BUFFSIZE=1048576 with CONTEXT_LENGTH=262144.
        # 1048576 is coincidentally a plausible context length too, which is why
        # this guards against someone "simplifying" it into a context-derived
        # value (or wiring it to --context-length).
        self.assertEqual(self.eff["NCCL_BUFFSIZE"], "1048576")
        self.assertEqual(self.eff["NCCL_LL128_BUFFSIZE"], "262144")
        self.assertNotIn("NCCL_BUFFSIZE", self.r.env)   # owned by the launcher, fixed
        self.assertNotIn("CONTEXT_LENGTH", self.r.env)  # wired via --context-length
        launcher = (SGLANG_MOD_DIR / "launcher.py").read_text()
        self.assertIn('"NCCL_BUFFSIZE": "1048576"', launcher)

    def test_tp_flows_through_command_to_launcher(self):
        # TP must reach boot.py: the template emits --tp {tensor_parallel} and the
        # launcher maps --tp -> TP_SIZE (sparkrun does NOT emit --tp-size when a
        # command template is present, so without the mapping boot.py would
        # silently fall back to its default TP=3).
        self.assertIn("--tp {tensor_parallel}", self.r.command_template)
        self.assertEqual(self.r.default("tensor_parallel"), "4")
        launcher = (SGLANG_MOD_DIR / "launcher.py").read_text()
        self.assertIn('add_argument("--tp"', launcher)
        self.assertIn('env["TP_SIZE"] = args.tp', launcher)

    def test_launcher_resolves_checkpoint(self):
        # The recipe must pass the repo id and the launcher must derive
        # MODEL_PATH/DSV41_SOURCE from the fixed HF hub cache (refs/main, else any
        # complete snapshot), so a moved checkpoint cannot break the recipe.
        self.assertIn("--model {model}", self.r.command_template)
        launcher = (SGLANG_MOD_DIR / "launcher.py").read_text()
        for needle in ("resolve_checkpoint", "HF_HUB", "refs", "model.safetensors.index.json"):
            self.assertIn(needle, launcher)

    def test_ep_size_is_one(self):
        # EP=2 loads but dies at the first decode plan under b12x_next.
        self.assertEqual(self.eff["EP_SIZE"], "1")

    def test_launcher_shim_invoked(self):
        self.assertIn("launcher.py", self.r.command_template)
        self.assertIn("/workspace/mods/dsv41-sglang-overlay", self.r.command_template)

    def test_image_is_vendored_and_pinned(self):
        # The image is published to littlecedar and pinned by digest, so a node
        # pulls the exact bytes rather than building or resolving a mutable tag.
        self.assertRegex(self.r.container, r"^littlecedar/dgx-spark-dsv41:canary-roce@sha256:[0-9a-f]{64}$")

    def test_distribution_config_omitted(self):
        # The block was development-only (it flipped containers/models during
        # bring-up). It is gone: sparkrun's default is models AND containers
        # enabled: true with auto {model}/{container} entries
        # (core/recipe.py:_default_distribution_config), so omitting it is
        # behaviorally identical and one less thing to drift. Asserted absent so a
        # reintroduced `enabled: false` cannot silently strand the workers without
        # the checkpoint or stop the image pull.
        self.assertEqual(self.dc.strip(), "",
                         "distribution_config must stay omitted; the default "
                         "already distributes both model and container")

    def test_no_host_bind_mounts(self):
        # Portability: the recipe must carry no machine-specific host path. Every
        # cacheable artifact lives under the sparkrun-managed runtime cache
        # (mounted at /cache/runtime), not a home directory and not a bind mount.
        # `sparkrun recipe validate` warns `non-portable-mount` on the latter.
        # (?m) matters: a plain `^` would only anchor to the string start, which
        # made this guard vacuously pass on an indented `volumes:`.
        self.assertIsNone(re.search(r"(?m)^\s*volumes:", self.clean),
                          "volumes: with host paths warns non-portable-mount")
        self.assertNotIn("/home/red", self.clean)

    def test_cache_lives_under_runtime_mount(self):
        # The cacheables (Engram shards, boot.py state, b12x JIT caches) must be
        # spelled under /cache/runtime so sparkrun's managed leaf is the only
        # host directory involved -- see core/runtime_cache.py. Set by the mod.
        rt = "/cache/runtime"
        self.assertEqual(self.eff["DSV41_PACKED_DIR"], f"{rt}/engram")
        self.assertEqual(self.eff["STATE_PATH"], f"{rt}/state")
        self.assertEqual(self.eff["B12X_COMPILE_CACHE_DIR"], f"{rt}/b12x-compile")
        self.assertEqual(self.eff["B12X_ROCE_CACHE_DIR"], f"{rt}/b12x-roce")

    def test_entrypoint_cleared(self):
        self.assertIn('entrypoint: ""', self.ec)

    def test_engram_nvme_env(self):
        self.assertEqual(self.eff["OFFLOAD_MODE"], "nvme")

    def test_sps_table_absent(self):
        # A fitted SPS table arms the ragged scheduler and crashes the Engram path.
        # Must be absent from BOTH the recipe and the launcher defaults.
        for src in (self.r.env, self.eff):
            self.assertNotIn("DSPARK_SPS_TABLE", src)
            self.assertNotIn("DSPARK_STS_TABLE", src)

    def test_roce_nante_on(self):
        self.assertEqual(self.eff["SGLANG_ROCE_ALLREDUCE"], "1")
        self.assertEqual(self.eff["DSV41_ROCE_GATHER"], "2097152")
        # B12X_ROCE_HCA is deliberately NOT set (recipe or launcher): it takes a
        # literal HCA list (a host device name) and b12x falls back to the
        # detected NCCL_IB_HCA when unset, so pinning it would break portability.
        self.assertNotIn("B12X_ROCE_HCA", self.eff)

    def test_no_host_device_names_in_env(self):
        # Portability: no env value (recipe or launcher) may name a host
        # adapter/interface -- a list like `rocep1s0f0,roceP2p1s0f0` was the
        # pre-2026-10-03 failure. Those are exactly what sparkrun's probe fills.
        for name, src in (("recipe", self.r.env), ("launcher", self.eff)):
            host_named = [k for k, v in (src or {}).items() if _HOST_DEVICE_RE.search(str(v))]
            self.assertEqual(host_named, [], f"{name} env pins host device names: {host_named}")

    def test_managed_comm_env_not_pinned(self):
        # The generic NCCL transport vars are filled per cluster by sparkrun's
        # InfiniBand probe (which correctly excludes the DOWN *s0f1 ports). A
        # recipe or launcher value wins over detection, pins the adapter naming,
        # and would trigger the `managed-comm-env` validate warning.
        for name, src in (("recipe", self.r.env), ("launcher", self.eff)):
            pinned = sorted(k for k in (src or {}) if k in MANAGED_COMM_ENV)
            self.assertEqual(pinned, [], f"{name} pins sparkrun-managed comm env: {pinned}")

    def test_nccl_transport_tuning_present(self):
        # The non-managed, device-free levers stay (they are the upstream profile's
        # tuning, not sparkrun-managed, and name no host device).
        self.assertEqual(self.eff["NCCL_P2P_DISABLE"], "1")
        self.assertEqual(self.eff["NCCL_SHM_DISABLE"], "1")
        self.assertEqual(self.eff["NCCL_PROTO"], "^LL128")
        self.assertEqual(self.eff["NCCL_MAX_NCHANNELS"], "8")

    def test_no_expandable_segments(self):
        self.assertIn("expandable_segments:False", self.eff["PYTORCH_CUDA_ALLOC_CONF"])

    def test_torch_2_13_collective_rename_warning_suppressed(self):
        # The image's torch is 2.13.0+cu130 (VERIFIED by probing the pinned
        # image), which renamed the collectives all_gather_into_tensor ->
        # all_gather_single and reduce_scatter_tensor -> reduce_scatter_single
        # (PyTorch 2.13; the old names remain as aliases behind a FutureWarning).
        # The image's sglang tree and its vendored kernels still call the old
        # names, so each call logs, via the _exception_logger wrapper at
        # torch/distributed/c10d_logger.py:83, a once-per-callsite notice:
        #   FutureWarning: `torch.distributed.all_gather_into_tensor` is deprecated.
        #   Please use `torch.distributed.all_gather_single` instead.
        # (observed in the live boot log .scratch/ds4/knapcio/logs/boot9-head-serve.log).
        # The launcher silences ONLY that c10d_logger re-emission. The filter is
        # MODULE-scoped and empirically verified against the pinned image: a bare
        # `message='is deprecated'` filter does NOT take, because
        # warnings.filterwarnings() anchors the message with re.match and the
        # leading backtick defeats it; a module filter is also robust to torch
        # rewording the message. Assert the scope, so "silence it" cannot later
        # be "fixed" into a blanket `ignore::FutureWarning` that hides unrelated
        # torch warnings.
        pw = self.eff.get("PYTHONWARNINGS", "")
        self.assertIn("ignore::FutureWarning:torch.distributed.c10d_logger", pw)
        self.assertNotIn("ignore::FutureWarning\n", pw + "\n",
                         "PYTHONWARNINGS must stay module-scoped, not a blanket "
                         "ignore::FutureWarning")
        launcher = (SGLANG_MOD_DIR / "launcher.py").read_text()
        self.assertIn("PYTHONWARNINGS", launcher)
        self.assertIn("torch.distributed.c10d_logger", launcher)

    def test_mod_present_and_gates_on_boot_py(self):
        run_sh = (SGLANG_MOD_DIR / "run.sh").read_text()
        self.assertIn("/opt/dsv41/boot.py", run_sh)
        self.assertIn("die", run_sh)
        launcher = (SGLANG_MOD_DIR / "launcher.py").read_text()
        for flag in ("--dist-init-addr", "--nnodes", "--node-rank"):
            self.assertIn(flag, launcher)

    def test_mod_creates_and_reowns_cache_dirs(self):
        # A mod runs as root; the cache subdirs it creates must be handed back or
        # the non-root serve user cannot write the Engram shards / state. run.sh
        # uses LITERAL ${CACHE}/<sub> paths (it runs before the launcher and so
        # cannot read the launcher's RECIPE_ENV; the image bakes STATE_PATH=/state),
        # and those must agree with the launcher's RECIPE_ENV.
        run_sh = (SGLANG_MOD_DIR / "run.sh").read_text()
        for sub in ("engram", "state", "b12x-compile", "b12x-roce"):
            self.assertIn(f"${{CACHE}}/{sub}", run_sh)
        self.assertIn("reown", run_sh)
        # Agreement: every path run.sh chowns is a RECIPE_ENV location.
        eff = _launcher_recipe_env()
        for key in ("DSV41_PACKED_DIR", "STATE_PATH",
                    "B12X_COMPILE_CACHE_DIR", "B12X_ROCE_CACHE_DIR"):
            self.assertIn(eff[key], {f"/cache/runtime/{s}" for s in
                          ("engram", "state", "b12x-compile", "b12x-roce")})

    def test_launcher_materializes_engram_shards(self):
        # The launcher is the only place that learns the node's rank (sparkrun
        # passes --node-rank to every node), so it -- not the mod -- is what
        # places the per-rank shards under the managed cache.
        launcher = (SGLANG_MOD_DIR / "launcher.py").read_text()
        self.assertIn("pack_engram.py", launcher)
        self.assertIn("ensure_engram_shards", launcher)

    def test_launcher_flag_to_env_mapping(self):
        """`main()` must map --tp/--context-length/--port onto boot.py's env.

        Executes launcher.main() with os.execve stubbed, so the mapping is proven
        end to end (argparse -> env) without a container. This is the decisive
        check for the context-length wiring: the recipe's
        `--context-length {max_model_len}` only matters if the flag lands in
        CONTEXT_LENGTH, applied after RECIPE_ENV so the recipe wins.
        """
        import importlib.util
        import os as _os
        import tempfile

        spec = importlib.util.spec_from_file_location(
            "dsv41_launcher_map", SGLANG_MOD_DIR / "launcher.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        captured: dict = {}

        def fake_execve(path, argv, env):  # pragma: no cover - records and stops
            captured["argv"] = argv
            captured["env"] = env
            raise SystemExit(0)

        with tempfile.NamedTemporaryFile("w", suffix=".py") as boot:
            boot.write("# stub\n")
            boot.flush()
            orig_boot, orig_execve = mod.BOOT, _os.execve
            mod.BOOT = boot.name
            _os.execve = fake_execve
            try:
                with self.assertRaises(SystemExit):
                    mod.main([
                        "--boot", "--model", "deepseek-ai/DeepSeek-V4.1-Flash",
                        "--port", "8000", "--tp", "4",
                        "--served-model-name", "deepseek-ai/DeepSeek-V4.1-Flash",
                        "--context-length", "524288",
                        "--nnodes", "4", "--node-rank", "0",
                        "--dist-init-addr", "10.0.4.32:25000",
                    ])
            finally:
                _os.execve = orig_execve
                mod.BOOT = orig_boot

        env = captured["env"]
        self.assertEqual(env["CONTEXT_LENGTH"], "524288",
                         "the recipe's --context-length must reach boot.py's env")
        self.assertEqual(env["TP_SIZE"], "4")
        self.assertEqual(env["SERVER_PORT"], "8000")
        self.assertEqual(env["NNODES"], "4")
        self.assertEqual(env["NODE_RANK"], "0")
        self.assertEqual(env["MODEL_ID"], "deepseek-ai/DeepSeek-V4.1-Flash")


class SglangLaneNegativeControls(unittest.TestCase):
    """Mutation controls: each must fail if the guarded invariant is broken."""

    def _mutated(self, old, new):
        text = SGLANG_RECIPE.read_text()
        assert old in text, "anchor %r not in recipe" % old
        return Recipe(text.replace(old, new, 1), SGLANG_RECIPE.name)

    # Anchor for controls that inject an env: key. The recipe now carries NO env:
    # block, so a control prepends one rather than splicing into an existing map.
    _ENV_ANCHOR = "defaults:"

    def _inject_env(self, old, line):
        return self._mutated(old, "env:\n  " + line + "\n\n" + old)

    def test_control_ep_size_two(self):
        # Inject EP_SIZE=2 via the env: block; it overrides the launcher default
        # (env.update) so the resolved env no longer satisfies the guard.
        r = self._inject_env(self._ENV_ANCHOR, 'EP_SIZE: "2"')
        with self.assertRaises(AssertionError):
            self.assertEqual(_resolved_env(r)["EP_SIZE"], "1")

    def test_control_image_distribution_disabled(self):
        # The guard requires the distribution_config block to stay ABSENT. Inject
        # an `enabled: false` block (the dev-time trap that would strand workers
        # without the checkpoint) and the guard must fail. Anchor on the real
        # `executor_config:` header so the injected block lands at top level.
        r = self._mutated(
            "executor_config:",
            'distribution_config:\n  models:\n    enabled: false\n\n'
            "executor_config:",
        )
        dc = "\n".join(_section(_strip_comment_lines(r.raw), "distribution_config"))
        with self.assertRaises(AssertionError):
            self.assertEqual(dc.strip(), "")

    def test_control_image_unpinned(self):
        # A mutable tag (no digest) must fail the vendored-and-pinned guard.
        r = self._mutated(
            "container: littlecedar/dgx-spark-dsv41:canary-roce"
            "@sha256:4e5002ab58b5cca670e2624c6a0d0799642914f04487ea130c71e7f525fa9c05",
            "container: littlecedar/dgx-spark-dsv41:canary-roce",
        )
        with self.assertRaises(AssertionError):
            self.assertRegex(
                r.container,
                r"^littlecedar/dgx-spark-dsv41:canary-roce@sha256:[0-9a-f]{64}$",
            )

    def test_control_sps_table_set(self):
        r = self._inject_env(self._ENV_ANCHOR, 'DSPARK_SPS_TABLE: /cache/runtime/state/dspark_sps.json')
        with self.assertRaises(AssertionError):
            self.assertNotIn("DSPARK_SPS_TABLE", _resolved_env(r))

    def test_control_volume_dict_form(self):
        # A host bind mount of any form must fail the no-host-mount guard.
        r = self._mutated(
            'shm_size: 32gb',
            'shm_size: 32gb\n  volumes:\n    /home/red/dsv41-engram: /engram-local',
        )
        clean = _strip_comment_lines(r.raw)
        with self.assertRaises(AssertionError):
            self.assertIsNone(re.search(r"(?m)^\s*volumes:", clean))

    def test_control_cache_outside_runtime_mount(self):
        # Injecting a non-/cache/runtime packed dir overrides the launcher default.
        r = self._inject_env(self._ENV_ANCHOR, "DSV41_PACKED_DIR: /engram-local")
        with self.assertRaises(AssertionError):
            self.assertEqual(_resolved_env(r)["DSV41_PACKED_DIR"], "/cache/runtime/engram")

    def test_control_managed_comm_env_pinned(self):
        # Re-adding a managed NCCL var (recipe or launcher) must fail the guard.
        r = self._inject_env(self._ENV_ANCHOR, "NCCL_IB_HCA: rocep1s0f0")
        with self.assertRaises(AssertionError):
            self.assertEqual(sorted(k for k in _resolved_env(r) if k in MANAGED_COMM_ENV), [])

    def test_control_b12x_hca_pinned(self):
        # Re-adding B12X_ROCE_HCA (a host device list) must fail both the
        # absence check and the host-name check.
        r = self._inject_env(self._ENV_ANCHOR, "B12X_ROCE_HCA: rocep1s0f0,roceP2p1s0f0")
        eff = _resolved_env(r)
        with self.assertRaises(AssertionError):
            self.assertNotIn("B12X_ROCE_HCA", eff)
        host_named = [k for k, v in eff.items() if _HOST_DEVICE_RE.search(str(v))]
        with self.assertRaises(AssertionError):
            self.assertEqual(host_named, [])

    def test_control_server_port_env_reintroduced(self):
        # The env-free design is the fix. Re-adding a container-level SERVER_PORT
        # (the redundant form the user removed) must fail the env-empty guard.
        r = self._inject_env(self._ENV_ANCHOR, 'SERVER_PORT: "8000"')
        with self.assertRaises(AssertionError):
            self.assertEqual(r.env, {})

    def test_control_port_moved_off_recipe_default(self):
        # The shipped recipes serve on 8000 (our default base port). Prove the
        # guard is sensitive: move the port off it and the expected-default
        # assertion must fail.
        r = self._mutated("  port: 8000", "  port: 8888")
        with self.assertRaises(AssertionError):
            self.assertEqual(r.default("port"), "8000")

    def test_control_context_length_unwired(self):
        # Dropping the placeholder (or the launcher parse) must fail the guard.
        r = self._mutated("  --context-length {max_model_len}\n", "")
        with self.assertRaises(AssertionError):
            self.assertIn("--context-length {max_model_len}", r.command_template)

    def test_control_blanket_futurewarning_suppression(self):
        # A blanket `ignore::FutureWarning` would hide unrelated torch warnings;
        # a recipe env that replaces the launcher's module-scoped filter with it
        # must fail the rename-warning guard (both the module-scope assertion and
        # the not-blanket assertion).
        r = self._inject_env(self._ENV_ANCHOR,
                             'PYTHONWARNINGS: "ignore::FutureWarning"')
        pw = _resolved_env(r).get("PYTHONWARNINGS", "")
        with self.assertRaises(AssertionError):
            self.assertIn("ignore::FutureWarning:torch.distributed.c10d_logger", pw)
        with self.assertRaises(AssertionError):
            self.assertNotIn("ignore::FutureWarning\n", pw + "\n")



# --------------------------------------------------------------------------
# The TensorFold TP=2 lane: bertholomus' deepseek_v41 engine over the Mia-AiLab
# EXL3 checkpoint (AGENTS.md §12). A separate engine and a separate mod, sharing
# only the shim pattern with the knapcio lane above: `runtime: sglang` carries no
# SGLang maths here, it is the rendezvous-flag bus, and the whole launch hinges on
# the shim mapping --dist-init-addr/--nnodes/--node-rank onto `tensorfold serve`.
# --------------------------------------------------------------------------

TF_RECIPE = RECIPE_DIR / "deepseek-v4.1-flash-tensorfold-tp2-1m-sglang.yaml"
TF_MOD_DIR = REPO_ROOT / "mods" / "tensorfold-dsv41-launcher"
TF_IMAGE = ("littlecedar/dgx-spark-dsv41@sha256:fabbe8615bb91c61fdde4a5f451f324a"
            "7449d7335fb85d453cc439985c525495")
TF_MOD_REF = "@littlecedar/mods/tensorfold-dsv41-launcher"
# The two TensorFold flags the shim MUST emit, and where their values come from.
TF_RENDEZVOUS_FLAGS = ("--master", "--master-port", "--rank")


def _tf_launcher():
    """Import the shim module. Stdlib-only (imports argparse/os/sys/pathlib)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "tf_dsv41_launcher", TF_MOD_DIR / "launcher.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_tf_launcher(argv, checkpoint_dir, cache_dir, engram_dir=None):
    """Execute launcher.main() with os.execvp stubbed; return (argv, env).

    Proves the argparse -> argv/env mapping end to end without a container. The
    module constants are redirected onto a temp dir first: prepare_runtime_cache()
    mkdirs RUNTIME_CACHE, which is /cache/runtime in a real container and
    unwritable here.
    """
    import os as _os
    import tempfile  # noqa: F401  (kept for parity with the SGLang control)

    mod = _tf_launcher()
    mod.RUNTIME_CACHE = cache_dir
    mod.ENGRAM_DIR = engram_dir if engram_dir is not None else str(Path(cache_dir) / "engram")
    mod.RECIPE_ENV = dict(mod.RECIPE_ENV)
    mod.RECIPE_ENV["TF_DS_RANK_CACHE"] = str(Path(cache_dir) / "rank-cache")
    mod.RECIPE_ENV["TORCH_EXTENSIONS_DIR"] = str(Path(cache_dir) / "torch-extensions")
    mod.RECIPE_ENV["TF_DS_TOKEN_MAP"] = str(Path(cache_dir) / "token_map.json")
    mod.RECIPE_ENV["HOME"] = str(cache_dir)

    captured: dict = {}

    def fake_execvp(prog, args):  # pragma: no cover - records and stops
        captured["prog"] = prog
        captured["argv"] = list(args)
        captured["env"] = dict(_os.environ)
        raise SystemExit(0)

    # The launcher does `os.environ.update(env)` and then execs; in production it
    # never returns to observe that. Here it does, so the mutation would leak into
    # the NEXT test's env snapshot (and did: an earlier TF_DS_ENGRAM leaked into
    # the degraded-mode test). Snapshot and restore this process's environment.
    before = dict(_os.environ)
    orig = _os.execvp
    _os.execvp = fake_execvp
    try:
        try:
            mod.main(argv)
        except SystemExit:
            pass
        else:  # pragma: no cover - execvp always raises here
            raise AssertionError("launcher.main() returned without exec")
    finally:
        _os.execvp = orig
        _os.environ.clear()
        _os.environ.update(before)
    return captured["prog"], captured["argv"], captured["env"]


class TensorfoldLaneContract(unittest.TestCase):
    """The TensorFold TP=2 lane's invariants. Each one, dropped, produces a
    launch that dies at the rendezvous gate or a boot that serves the wrong model
    -- neither of which is loud."""

    def setUp(self):
        self.text = TF_RECIPE.read_text()
        self.r = Recipe(self.text, TF_RECIPE.name)
        self.clean = _strip_comment_lines(self.text)
        self.dc = "\n".join(_section(self.clean, "distribution_config"))

    # -- recipe surface ----------------------------------------------------
    def test_runtime_image_model(self):
        self.assertEqual(self.r.runtime, "sglang")
        # Vendored + digest-pinned: the shebang image whose `tensorfold` we built.
        self.assertEqual(self.r.container, TF_IMAGE)
        # The engine reads EXL3 ONLY (families/deepseek_v41 QUANT_METHODS); the
        # official MXFP4 checkpoint would be rejected by family.check().
        self.assertEqual(self.r.model, "Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw")

    def test_image_is_vendored_and_pinned(self):
        self.assertRegex(
            self.r.container,
            r"^littlecedar/dgx-spark-dsv41@sha256:[0-9a-f]{64}$",
        )

    def test_builder_is_docker_pull(self):
        # The image is published to littlecedar and pulled by digest; nothing is
        # built at launch. A builder that transforms the image would forbid the
        # per-machine containers: this lane does not use, but the invariant is
        # that distribution, not a local build, supplies the bytes.
        self.assertEqual(_scalar(self.clean, "builder"), "docker-pull")

    def test_two_nodes_tp2(self):
        # TP=2 == min_nodes == max_nodes == 2: one GB10 per rank, and exactly two.
        self.assertEqual(self.r.min_nodes, 2)
        self.assertEqual(_scalar(self.clean, "max_nodes"), "2")
        self.assertEqual(self.r.default("tensor_parallel"), "2")
        self.assertIn("--tp {tensor_parallel}", self.r.command_template)

    def test_context_and_port_are_wired(self):
        # The lane ships at the model's full 1M window. It is not a taste choice:
        # `--context` IS the KV pool here (no separate pool knob), so the maximum
        # context and the maximum cache are the same change, and 1M is the wall the
        # engine enforces (`cli.py`: `context > native_context` is refused before any
        # weight loads). Pinned so a future "smaller is safer" retune has to argue
        # with a test rather than a comment. See AGENTS.md §12.13.
        self.assertEqual(self.r.default("max_model_len"), "1048576")
        self.assertIn("--context {max_model_len}", self.r.command_template)
        self.assertEqual(self.r.default("port"), "8000")
        self.assertIn("--port {port}", self.r.command_template)

    def test_context_is_capped_at_the_model_window(self):
        """The shipped context must not exceed the model's trained window (1,048,576).

        The offline half of the engine's `cli.py` check: `context > native_context` is
        refused before any weight loads. Exceeding it does not degrade gracefully --
        the launch dies -- so a retune that raises it (e.g. round 1M up to 2M) must
        fail here rather than at the node. See AGENTS.md 12.13.
        """
        MODEL_WINDOW = 1048576
        shipped = int(self.r.default("max_model_len"))
        self.assertLessEqual(
            shipped, MODEL_WINDOW,
            f"max_model_len {shipped} exceeds the model's {MODEL_WINDOW}-token "
            "window; the engine refuses the launch",
        )
        # And it should be the ceiling, not below it: with no separate pool knob,
        # any value below the ceiling needlessly shrinks both cache and context.
        self.assertEqual(
            shipped, MODEL_WINDOW,
            "the lane should ship at the model's full window (no separate pool knob)",
        )

    def test_mod_reference(self):
        self.assertIn(TF_MOD_REF, self.text)

    def test_no_host_bind_mounts(self):
        # (?m): a bare ^ anchors to string start and would pass vacuously on an
        # indented volumes:. Cache lives under /cache/runtime, set by the launcher.
        self.assertIsNone(re.search(r"(?m)^\s*volumes:", self.clean),
                          "volumes: warns non-portable-mount; the shim owns the cache")
        self.assertNotIn("/home/red", self.clean)

    def test_entrypoint_cleared_and_shm(self):
        ec = "\n".join(_section(self.clean, "executor_config"))
        self.assertIn('entrypoint: ""', ec)
        self.assertIn("shm_size: 32gb", ec)

    def test_distribution_config_omitted(self):
        # sparkrun's default distributes both model and container; an explicit
        # `enabled: false` would strand the workers without either.
        self.assertEqual(self.dc.strip(), "")

    def test_readiness_timeouts_generous(self):
        # A cold boot compiles the CUDA extensions and writes a ~106 GiB/rank
        # weight cache before the serve port opens. A short timeout is a false bug.
        self.assertRegex(self.clean, r"(?m)^\s+port_timeout_s:\s*(\d+)\s*$")
        self.assertGreaterEqual(
            int(re.search(r"(?m)^\s+port_timeout_s:\s*(\d+)\s*$", self.clean).group(1)),
            3600,
        )

    def test_every_default_consumed(self):
        # The same invariant DefaultsAreConsumed enforces for the attic lane, pin
        # here too so the TensorFold recipe cannot ship a dead defaults key.
        for key in self.r.defaults:
            if key in ENGINE_PLACEHOLDERS:
                continue
            self.assertIn("{" + key + "}", self.r.command_template,
                          f"defaults key {key!r} is referenced by no placeholder")

    # -- the mod -----------------------------------------------------------
    def test_mod_gates_and_reowns(self):
        run_sh = (TF_MOD_DIR / "run.sh").read_text()
        self.assertIn("launcher.py", run_sh)
        self.assertIn("tensorfold", run_sh)          # gates on the engine on PATH
        self.assertIn("reown", run_sh)               # hands cache back to the serve uid
        for sub in ("rank-cache", "torch-extensions"):
            self.assertIn(sub, run_sh)
        # The launcher's RECIPE_ENV must agree with the two dirs run.sh creates.
        eff = dict(_tf_launcher().RECIPE_ENV)
        self.assertEqual(eff["TF_DS_RANK_CACHE"], "/cache/runtime/tensorfold/rank-cache")
        self.assertEqual(eff["TORCH_EXTENSIONS_DIR"],
                         "/cache/runtime/tensorfold/torch-extensions")

    def test_no_host_device_names_in_recipe_env(self):
        # No env value may name a host adapter; sparkrun's InfiniBand probe fills
        # the transport vars per cluster and a pinned name breaks portability.
        for k, v in self.r.env.items():
            self.assertIsNone(_HOST_DEVICE_RE.search(str(v)),
                              f"recipe env {k}={v!r} pins a host device name")
        pinned = sorted(k for k in self.r.env if k in MANAGED_COMM_ENV)
        self.assertEqual(pinned, [], f"recipe pins sparkrun-managed comm env: {pinned}")

    # -- the shim's load-bearing mapping (executed, not read) --------------
    def test_shim_maps_rendezvous_flags(self):
        """--dist-init-addr HOST:PORT -> --master HOST --master-port PORT.

        sparkrun's native-cluster launch waits for the head to open the port in
        --dist-init-addr (default 25000). TensorFold's TCPStore binds
        --master-port (its own default is 29551). If the shim drops the mapping
        the head opens 29551 while sparkrun polls 25000 and the launch is
        declared dead. Asserted by EXECUTING the shim's main().
        """
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            model = Path(d) / "model"
            model.mkdir()
            (model / "config.json").write_text("{}")
            prog, argv, env = _run_tf_launcher(
                ["--boot", "--model", str(model), "--port", "8000", "--tp", "2",
                 "--served-model-name", "DeepSeek-V4.1-Flash", "--context", "262144",
                 "--nnodes", "2", "--node-rank", "1",
                 "--dist-init-addr", "10.0.4.34:25000"],
                checkpoint_dir=str(model), cache_dir=str(Path(d) / "runtime"),
            )
        # argv is passed to execvp; prog is the resolved binary ("tensorfold").
        self.assertEqual(prog, "tensorfold")
        self.assertEqual(argv[:2], ["tensorfold", "serve"])
        for flag in TF_RENDEZVOUS_FLAGS:
            self.assertIn(flag, argv, f"shim must emit {flag}")
        self.assertEqual(argv[argv.index("--master") + 1], "10.0.4.34")
        self.assertEqual(argv[argv.index("--master-port") + 1], "25000",
                         "the --dist-init-addr port must reach --master-port, "
                         "not the engine's 29551 default")
        self.assertEqual(argv[argv.index("--rank") + 1], "1",
                         "the rank comes only from --node-rank")
        # The upstream served line.
        self.assertEqual(argv[argv.index("--mtp-drafts") + 1], "5")
        self.assertEqual(argv[argv.index("--parallel") + 1], "4")

    def test_shim_sets_recipe_env_and_degrades_without_engram(self):
        """RECIPE_ENV reaches the child, and a missing Engram dir does NOT fail.

        The engine loads and serves without the two Engram shards (degraded,
        one warning). The shim must therefore leave TF_DS_ENGRAM UNSET rather
        than point it at an absent dir or abort.
        """
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            model = Path(d) / "model"
            model.mkdir()
            (model / "config.json").write_text("{}")
            _prog, _argv, env = _run_tf_launcher(
                ["--boot", "--model", str(model), "--port", "8000", "--tp", "2",
                 "--served-model-name", "DeepSeek-V4.1-Flash", "--context", "262144"],
                checkpoint_dir=str(model), cache_dir=str(Path(d) / "runtime"),
                engram_dir=str(Path(d) / "absent-engram"),
            )
        self.assertEqual(env.get("TF_DS_REPLAY"), "1")
        self.assertEqual(env.get("TF_DS_PREFILL_CHUNK"), "2048")
        self.assertEqual(env.get("TF_DS_RANK_CACHE_READERS"), "32")
        self.assertNotIn("TF_DS_ENGRAM", env,
                         "a missing Engram dir must leave TF_DS_ENGRAM unset, "
                         "not point it at something absent")

    def test_shim_sets_engram_when_present(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            model = Path(d) / "model"
            model.mkdir()
            (model / "config.json").write_text("{}")
            engram = Path(d) / "dsv41-engram"
            engram.mkdir()
            (engram / "model-00047-of-00048.safetensors").write_bytes(b"")
            _prog, _argv, env = _run_tf_launcher(
                ["--boot", "--model", str(model), "--port", "8000", "--tp", "2",
                 "--served-model-name", "DeepSeek-V4.1-Flash", "--context", "262144"],
                checkpoint_dir=str(model), cache_dir=str(Path(d) / "runtime"),
                engram_dir=str(engram),
            )
        self.assertEqual(env.get("TF_DS_ENGRAM"), str(engram))


class TensorfoldLaneNegativeControls(unittest.TestCase):
    """Mutation controls: each must fail if the guarded invariant is broken."""

    def _mutated(self, old, new):
        text = TF_RECIPE.read_text()
        assert old in text, "anchor %r not in recipe" % old
        return Recipe(text.replace(old, new, 1), TF_RECIPE.name)

    def test_control_context_above_model_window(self):
        """Prove the ceiling guard can fail: a context past 1,048,576 must be caught.

        This is the mutation the guard exists for -- someone "rounding up" the
        window to 2M would otherwise ship a recipe whose every launch dies at
        `cli.py`'s native-window check.
        """
        r = self._mutated("max_model_len: 1048576", "max_model_len: 2097152")
        with self.assertRaises(AssertionError):
            self.assertLessEqual(int(r.default("max_model_len")), 1048576)

    def test_control_context_below_ceiling(self):
        """The old 262144 value must fail the "ship at the ceiling" half.

        Pins the decision: with no separate pool knob, a smaller context is a
        needlessly smaller cache and less concurrency, so a silent regression
        back to 262K should be a test failure.
        """
        r = self._mutated("max_model_len: 1048576", "max_model_len: 262144")
        with self.assertRaises(AssertionError):
            self.assertEqual(int(r.default("max_model_len")), 1048576)

    def test_control_image_unpinned(self):
        r = self._mutated(TF_IMAGE, "littlecedar/dgx-spark-dsv41:tensorfold-tp2")
        with self.assertRaises(AssertionError):
            self.assertRegex(r.container, r"^littlecedar/dgx-spark-dsv41@sha256:[0-9a-f]{64}$")

    def test_control_official_mxfp4_checkpoint(self):
        # Swapping in the official (MXFP4) checkpoint must fail the model guard:
        # the engine's family.check() refuses any quant_method != exl3.
        r = self._mutated("model: Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw",
                          "model: deepseek-ai/DeepSeek-V4.1-Flash")
        with self.assertRaises(AssertionError):
            self.assertEqual(r.model, "Mia-AiLab/DeepSeek-V4.1-Flash-EXL3-2.9bpw")

    def test_control_tp3(self):
        r = self._mutated("  tensor_parallel: 2", "  tensor_parallel: 3")
        with self.assertRaises(AssertionError):
            self.assertEqual(r.default("tensor_parallel"), "2")

    def test_control_mod_reference_dropped(self):
        r = self._mutated(TF_MOD_REF, "@littlecedar/mods/not-the-launcher")
        with self.assertRaises(AssertionError):
            self.assertIn(TF_MOD_REF, r.raw)

    def test_control_volume_dict_form(self):
        r = self._mutated(
            "shm_size: 32gb",
            "shm_size: 32gb\n  volumes:\n    /home/red/dsv41-engram: /engram-local",
        )
        with self.assertRaises(AssertionError):
            self.assertIsNone(
                re.search(r"(?m)^\s*volumes:", _strip_comment_lines(r.raw)))

    def test_control_rendezvous_port_not_mapped(self):
        """Prove the shim's port mapping is load-bearing: the guard must fail if
        the shim stops emitting --master-port.

        Simulated by running the shim with a --dist-init-addr whose port we then
        check is actually threaded; the mutation is applied to the shim source in
        memory and the module re-executed."""
        import os as _os
        import tempfile
        import types

        src = (TF_MOD_DIR / "launcher.py").read_text()
        # Break the mapping: emit the engine's own default instead of the passed port.
        broken = src.replace(
            'cmd += ["--master", master or "127.0.0.1", "--master-port", str(master_port)]',
            'cmd += ["--master", master or "127.0.0.1"]',
        )
        self.assertNotEqual(broken, src, "mapping line vanished; update the control")
        with tempfile.TemporaryDirectory() as d:
            module = types.ModuleType("tf_broken")
            module.__file__ = str(TF_MOD_DIR / "launcher.py")
            exec(compile(broken, module.__file__, "exec"), module.__dict__)
            module.RUNTIME_CACHE = str(Path(d) / "runtime")
            module.ENGRAM_DIR = str(Path(d) / "engram")
            module.RECIPE_ENV = dict(module.RECIPE_ENV)
            module.RECIPE_ENV["HOME"] = str(Path(d) / "runtime")
            model = Path(d) / "model"
            model.mkdir()
            (model / "config.json").write_text("{}")
            captured = {}

            def fake_execvp(prog, args):
                captured["argv"] = list(args)
                raise SystemExit(0)

            orig = _os.execvp
            _os.execvp = fake_execvp
            try:
                try:
                    module.main(["--boot", "--model", str(model), "--port", "8000",
                                 "--tp", "2", "--served-model-name", "x",
                                 "--context", "262144", "--node-rank", "0",
                                 "--dist-init-addr", "10.0.4.34:25000"])
                except SystemExit:
                    pass
            finally:
                _os.execvp = orig
        with self.assertRaises(AssertionError):
            self.assertIn("--master-port", captured["argv"])


if __name__ == "__main__":
    unittest.main()
