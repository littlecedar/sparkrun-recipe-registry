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

Sources for the invariants (DS4-MODEL-OPTIMIZATION-WORK.md, same directory):
  SGLANG_B12X_MAX_TOKENS == --chunked-prefill-size ....... sec 4.1: the image's
      b12x prefill gate is sized from this env var
  never --speculative-algorithm NEXTN ..................... sgl#38236 -- crashes
      at arg validation on DeepSeek-V4, unfixed on main 2c05ed4e7
  never EAGLE on a DSpark head ............................ upstream cookbook:
      starts, serves, accepts nothing, logs "accept rate: 0.00"
  no expandable_segments on V4.1 .......................... sec 6.3: the 4x Spark
      V4.1 deployment reports NaN logits above 64 prefill query tokens
  every defaults: key consumed by a placeholder ........... sec 7.4: a defaults
      key with no placeholder is silently not a setting, and this shipped an
      unbootable pair once in this registry
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPE_DIR = REPO_ROOT / "recipes" / "ds4"

# vLLM + cuda-exl3 lane, added 2026-09-23 (work doc 4.5, 7.5). Third party's
# measured recipe on the EXL3 checkpoint; ours is the sparkrun port.
EXL3_TP4 = RECIPE_DIR / "deepseek-v4.1-flash-exl3-tp4-vllm.yaml"
EXL3_TP4_1M = RECIPE_DIR / "deepseek-v4.1-flash-exl3-tp4-1m-vllm.yaml"
EXL3_TP3 = RECIPE_DIR / "deepseek-v4.1-flash-exl3-tp3-vllm.yaml"
EXL3_TP6 = RECIPE_DIR / "deepseek-v4.1-flash-exl3-tp6-vllm.yaml"
EXL3_TP6_1M = RECIPE_DIR / "deepseek-v4.1-flash-exl3-tp6-1m-vllm.yaml"

ALL = [EXL3_TP4, EXL3_TP4_1M, EXL3_TP3, EXL3_TP6, EXL3_TP6_1M]
EXL3_RECIPES = [EXL3_TP4, EXL3_TP4_1M, EXL3_TP3, EXL3_TP6, EXL3_TP6_1M]  # the V4.1 vLLM/EXL3 lane

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
                             "(work doc 3.1, 6.5)")
            for key in ("DSV41_ENGRAM_DISK_THREADS", "DSV41_ENGRAM_DISK_CHUNK",
                        "DSV41_ENGRAM_DIR"):
                self.assertIn(key, r.env, f"{p.name}: missing {key}")

    def test_patch_mod_present(self):
        for p in EXL3_RECIPES:
            text = p.read_text()
            self.assertIn("mount-dsv41-exl3-patches", text,
                          f"{p.name}: the mod that installs tonyd2wild's "
                          "engram.py is what makes this boot fit")

    def test_drop_caches_mod_present(self):
        """Every EXL3 recipe must carry @eugr/mods/drop-caches.

        Listed for recipe-contract parity with the qwen4 GB10 recipes. VERIFIED
        INERT 2026-09-25 in every launch mode, for two independent reasons:
        (1) under rootless (sparkrun's default: privileged false, /proc/sys
        mounted `ro`) the write to drop_caches is refused; and (2) the mod's own
        line `echo 3 > /proc/sys/vm/drop_caches >> /tmp/drop_caches.log 2>&1` has
        a redirection-order bug -- the LAST redirect wins, so `3` goes to the log
        and never to drop_caches (reproduced: target 0 bytes, log "3"). `--rootful`
        does not fix it. This guard asserts the mod is LISTED, not that it works;
        a real cache drop must be host-level.
        """
        for p in EXL3_RECIPES:
            self.assertIn(
                "@eugr/mods/drop-caches", p.read_text(),
                f"{p.name}: missing @eugr/mods/drop-caches (listed for parity; "
                "inert, see docstring)",
            )

    def test_mod_order_drop_caches_before_patch(self):
        """drop-caches must come first in the mods: list.

        The `mods:` list is an ORDERED chain, not a set. drop-caches only starts a
        background flusher, so it has no dependency on the patch mod -- but the
        house convention (qwen4) puts it first, and keeping the order stable
        avoids a silent reordering becoming a confound between recipes.
        """
        for p in EXL3_RECIPES:
            mods = re.findall(r'^\s*-\s*"(@[^"]+)"', p.read_text(), re.M)
            self.assertIn("@eugr/mods/drop-caches", mods, p.name)
            self.assertIn("@littlecedar/mods/mount-dsv41-exl3-patches", mods, p.name)
            self.assertLess(
                mods.index("@eugr/mods/drop-caches"),
                mods.index("@littlecedar/mods/mount-dsv41-exl3-patches"),
                f"{p.name}: drop-caches must precede the patch mod (qwen4 order)",
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
        """DSpark requires a TP that divides the drafter's 128 experts and 64 heads.

        The DSpark drafter's own SpeculativeConfig validates its 64 attention
        heads against the TP size, and the drafter's 128 experts must divide too.
        Both hold at TP=2 and TP=4 (64%4==0, 128%4==0) but NOT at TP=3 or TP=6
        (64%3, 64%6, 128%3, 128%6 are all nonzero). Our virtual-heads override
        pads the MAIN model, not the drafter, so those arms are no-spec.
        Verified 2026-09-24. TP=3 and TP=6 are no-spec on purpose.
        """
        no_spec = {EXL3_TP3, EXL3_TP6, EXL3_TP6_1M}
        for p in EXL3_RECIPES:
            r = load(p)
            has_spec = "--speculative-config" in r.flags()
            if p in no_spec:
                self.assertFalse(
                    has_spec,
                    f"{p.name}: TP={r.default('tensor_parallel')} + DSpark fails "
                    "SpeculativeConfig validation on the drafter's 64 heads / 128 "
                    "experts; this arm is no-spec (see its header)",
                )
                continue
            self.assertTrue(has_spec, p.name)
            self.assertIn("dspark", r.default("speculative_config"), p.name)
            # Adaptive verification must stay off: padded spec batches hang
            # SM120 sparse MLA (FlashInfer #5015).
            self.assertIn('"enable_adaptive_verification":false',
                          r.default("speculative_config").replace(" ", ""),
                          f"{p.name}: adaptive verification off is required")

    def test_graph_capture_covers_max_seqs(self):
        """Capture sizes must reach max_num_seqs*(k+1); a truncation cost -12%."""
        for p in EXL3_RECIPES:
            r = load(p)
            cc = r.default("compilation_config")
            self.assertIn("FULL_AND_PIECEWISE", cc, p.name)
            sizes = re.findall(r"\d+", cc.split("cudagraph_capture_sizes")[-1])
            self.assertTrue(sizes, f"{p.name}: no cudagraph_capture_sizes")
            if "--speculative-config" not in r.flags():
                continue  # no-spec arm: k=0, any non-empty list is enough
            k = 5  # num_speculative_tokens in the dspark config
            need = int(r.default("max_num_seqs")) * (k + 1)
            self.assertGreaterEqual(
                max(int(s) for s in sizes), need,
                f"{p.name}: capture sizes top out at {max(map(int, sizes))} < "
                f"{need} = max_num_seqs*(k+1); requests above the max run eager",
            )


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
    """A cold boot reads hundreds of GB over NFS. A short timeout is a false bug."""

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
                "over NFS takes ~10+ min before weights even start moving",
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
    --speculative-config / --enable-expert-parallel and say so in prose; the
    check proves that prose never leaks into the rendered command.
    """

    FORBIDDEN = {"--enable-expert-parallel", "--quantization",
                 "--kv-cache-memory-bytes"}
    # These are deliberately absent on the no-spec arms (TP=3, TP=6) and present
    # on the DSpark arms (TP=4). Guarded by Exl3LaneContract.test_dspark_spec_config;
    # here they must never leak from prose on the arms that omit them.
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
        """The no-spec arms say 'NO --speculative-config' in prose; prove inert."""
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
        # Anchor on gpu_memory_utilization rather than a value that may be
        # retuned: a control whose anchor is a tunable number breaks the next
        # time someone tunes it, and then nobody trusts the control.
        r = self._mutated(EXL3_TP4, "gpu_memory_utilization: 0.80",
                          "gpu_memory_utilization: 0.80\n  kv_pin: 8388608")
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
        # A no-spec recipe (TP=3) whose description re-advertises DSpark k=5.
        r = self._mutated(
            EXL3_TP3,
            "Engram streamed from disk, NO DSpark",
            "Engram streamed from disk, DSpark k=5",
        )
        with self.assertRaises(AssertionError):
            self.assertNotIn("dspark k=", _folded(r.raw, "metadata").lower())

    def test_control_engram_disk_off(self):
        r = self._mutated(EXL3_TP4, "DSV41_ENGRAM_DISK: \"1\"",
                          "DSV41_ENGRAM_DISK: \"0\"")
        with self.assertRaises(AssertionError):
            self.assertEqual(r.env.get("DSV41_ENGRAM_DISK"), "1")

    def test_control_drop_caches_mod_removed(self):
        """Prove the drop-caches guard can fail."""
        r = self._mutated(EXL3_TP4, '  - "@eugr/mods/drop-caches"\n', "")
        with self.assertRaises(AssertionError):
            self.assertIn("@eugr/mods/drop-caches", r.raw)

    def test_control_drop_caches_wrong_order(self):
        """Prove the order guard can fail."""
        r = self._mutated(
            EXL3_TP4,
            '  - "@eugr/mods/drop-caches"\n'
            '  - "@littlecedar/mods/mount-dsv41-exl3-patches"',
            '  - "@littlecedar/mods/mount-dsv41-exl3-patches"\n'
            '  - "@eugr/mods/drop-caches"',
        )
        mods = re.findall(r'^\s*-\s*"(@[^"]+)"', r.raw, re.M)
        with self.assertRaises(AssertionError):
            self.assertLess(mods.index("@eugr/mods/drop-caches"),
                            mods.index("@littlecedar/mods/mount-dsv41-exl3-patches"))

    def test_control_no_1m_recipe(self):
        r = self._mutated(EXL3_TP4_1M, "max_model_len: 1000000",
                          "max_model_len: 300000")
        with self.assertRaises(AssertionError):
            self.assertGreaterEqual(int(r.default("max_model_len")), 1000000)

    def test_control_truncated_capture_sizes(self):
        r = self._mutated(EXL3_TP4,
                          "cudagraph_capture_sizes\":[5,6,10,12,15,18,20,24,25,30,35,36,40,42,48]",
                          "cudagraph_capture_sizes\":[5,6,10,12,15,18,20,24]")
        with self.assertRaises(AssertionError):
            cc = r.default("compilation_config")
            sizes = [int(s) for s in re.findall(r"\d+", cc.split("cudagraph_capture_sizes")[-1])]
            self.assertGreaterEqual(max(sizes), int(r.default("max_num_seqs")) * 6)


if __name__ == "__main__":
    unittest.main()
