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

MXFP4_TP2 = RECIPE_DIR / "deepseek-v4-flash-0731-mxfp4-tp2-sglang.yaml"
NVFP4_TP2 = RECIPE_DIR / "deepseek-v4-flash-0731-nvfp4-tp2-sglang.yaml"
V41_TP4 = RECIPE_DIR / "deepseek-v4.1-flash-mxfp4-tp4-sglang.yaml"
V41_TP8 = RECIPE_DIR / "deepseek-v4.1-flash-mxfp4-tp8-sglang.yaml"

# vLLM + cuda-exl3 lane, added 2026-09-23 (work doc 4.5, 7.5). Third party's
# measured recipe on the EXL3 checkpoint; ours is the sparkrun port.
EXL3_TP4 = RECIPE_DIR / "deepseek-v4.1-flash-exl3-tp4-vllm.yaml"
EXL3_TP4_1M = RECIPE_DIR / "deepseek-v4.1-flash-exl3-tp4-1m-vllm.yaml"
EXL3_TP3 = RECIPE_DIR / "deepseek-v4.1-flash-exl3-tp3-vllm.yaml"

ALL = [MXFP4_TP2, NVFP4_TP2, V41_TP4, V41_TP8,
       EXL3_TP4, EXL3_TP4_1M, EXL3_TP3]
V4F_RECIPES = [MXFP4_TP2, NVFP4_TP2]   # the V4-Flash family
V41_RECIPES = [V41_TP4, V41_TP8]       # the V4.1-Flash SGLang family
EXL3_RECIPES = [EXL3_TP4, EXL3_TP4_1M, EXL3_TP3]  # the V4.1 vLLM/EXL3 lane

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


class B12xPrefillGate(unittest.TestCase):
    """SGLANG_B12X_MAX_TOKENS must equal --chunked-prefill-size.

    The b12x image-prefill gate is sized from this env var; if it is smaller
    than the chunk the server admits, prefill is silently clipped.

    sparkrun does NOT interpolate {placeholders} inside `env:` -- it passes the
    block through verbatim (checked 2026-09-19 with `sparkrun recipe show`; no
    recipe in this registry interpolates env either) -- so the two values are
    duplicated by hand and this test is the only thing keeping them equal.
    """

    def test_equal(self):
        for p in V4F_RECIPES:
            r = load(p)
            self.assertIn("SGLANG_B12X_MAX_TOKENS", r.env, p.name)
            chunk = r.flag_value("--chunked-prefill-size")
            self.assertIsNotNone(chunk, f"{p.name}: no --chunked-prefill-size")
            self.assertEqual(
                r.env["SGLANG_B12X_MAX_TOKENS"], chunk,
                f"{p.name}: SGLANG_B12X_MAX_TOKENS={r.env['SGLANG_B12X_MAX_TOKENS']} "
                f"but --chunked-prefill-size={chunk}",
            )

    def test_no_placeholder_in_env(self):
        """Re-assert the sparkrun behaviour the hand-duplication depends on.

        If a future sparkrun starts interpolating env:, the duplicated literal
        becomes a latent bug instead of a documented one. Fail here so the
        recipes get updated deliberately.
        """
        for p in ALL:
            for k, v in load(p).env.items():
                self.assertNotIn("{", v,
                                 f"{p.name}: env {k}={v!r} has a placeholder; "
                                 "sparkrun passes env verbatim")


class SpeculativeDecoding(unittest.TestCase):
    """NEXTN crashes; EAGLE on a DSpark head silently accepts nothing."""

    def test_never_nextn(self):
        for p in ALL:
            r = load(p)
            self.assertNotEqual(
                r.flag_value("--speculative-algorithm"), "NEXTN",
                f"{p.name}: NEXTN crashes on DeepSeek-V4 (sgl#38236 -- the "
                "NEXTN->EAGLE alias resolves after the model hooks)",
            )
            if "speculative_config" in r.defaults:
                self.assertNotIn("nextn", r.default("speculative_config").lower(),
                                 f"{p.name}: NEXTN in the speculative-config")

    def test_allowed_algorithms(self):
        """SGLang names the algorithm in a flag; vLLM passes a JSON blob."""
        for p in ALL:
            r = load(p)
            val = r.flag_value("--speculative-algorithm")
            if val is not None:
                self.assertIn(val, ("DSPARK", "EAGLE"), f"{p.name}: unexpected {val=}")
            else:
                self.assertIn(
                    "dspark",
                    r.defaults.get("speculative_config", "").lower(),
                    f"{p.name}: neither --speculative-algorithm nor a dspark "
                    "speculative_config -- the recipe names no speculative method",
                )

    def test_eagle_only_on_non_dspark_head(self):
        """EAGLE against a DSpark head is the silent zero-acceptance case."""
        for p in ALL:
            r = load(p)
            if r.flag_value("--speculative-algorithm") != "EAGLE":
                continue
            self.assertIn("V4.1", r.model,
                          f"{p.name}: EAGLE on {r.model} -- if this checkpoint has "
                          "a DSpark head it starts, serves plausible output, and "
                          "accepts nothing (accept rate 0.00)")


class ExpandableSegments(unittest.TestCase):
    """V4-Flash ships it; V4.1 must not, until the NaN question is settled."""

    def test_absent_on_v41(self):
        for p in V41_RECIPES:
            val = load(p).env.get("PYTORCH_CUDA_ALLOC_CONF", "")
            self.assertNotIn(
                "expandable_segments", val,
                f"{p.name}: expandable_segments on V4.1 is reported to produce NaN "
                "logits above 64 prefill query tokens (work doc 6.3)",
            )

    def test_present_on_v4flash(self):
        """Positive control: prove the guard above can tell the two families apart.

        If this fails, the V4.1 assertion is vacuously passing because nothing
        sets the variable anywhere.
        """
        for p in V4F_RECIPES:
            self.assertIn("expandable_segments",
                          load(p).env.get("PYTORCH_CUDA_ALLOC_CONF", ""), p.name)


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


class Nvfp4RunnerOverrides(unittest.TestCase):
    """The three flags that make NVFP4 boot on SM121, and where they must not be.

    b12x's MoE is MXFP4-only and the trtllm-gen kernels are sm100-only, so NVFP4
    experts must go to cutlass; the DSpark draft's MTP experts are MXFP4 so the
    draft keeps b12x; HashTopK rejects fused shared experts under cutlass.
    Copying these onto an MXFP4 checkpoint is not harmless --
    --disable-shared-experts-fusion on the b12x path drops the shared expert out
    of the fused MoE for no reason.
    """

    def test_nvfp4_has_the_three(self):
        r = load(NVFP4_TP2)
        self.assertIn("--disable-shared-experts-fusion", r.flags())
        self.assertEqual(r.flag_value("--moe-runner-backend"), "flashinfer_cutlass")
        self.assertEqual(r.flag_value("--speculative-moe-runner-backend"), "b12x")

    def test_mxfp4_lacks_the_three(self):
        r = load(MXFP4_TP2)
        self.assertNotIn("--disable-shared-experts-fusion", r.flags(),
                         "MXFP4 + b12x accepts the fused shared expert")
        self.assertEqual(r.flag_value("--moe-runner-backend"), "b12x")

    def test_no_engine_backend_overrides_on_v41(self):
        """V4.1 auto-resolves; overriding costs most of bs=1 decode throughput."""
        forbidden = {"--attention-backend", "--fp8-gemm-backend",
                     "--moe-a2a-backend", "--moe-runner-backend"}
        for p in V41_RECIPES:
            hit = load(p).flags() & forbidden
            self.assertFalse(hit, f"{p.name}: {sorted(hit)} override the "
                             "auto-resolved backends and drop the 32-wide ue8m0 "
                             "blocks onto the Triton fallback")


class EngramLayout(unittest.TestCase):
    """`shared` cannot work across Sparks, and the flag is not a memory fix."""

    def test_layout_is_per_rank(self):
        for p in V41_RECIPES:
            env = load(p).env
            if env.get("SGLANG_ENABLE_DSV41_ENGRAM_HOST_TABLE") != "1":
                continue
            self.assertEqual(
                env.get("SGLANG_DSV41_ENGRAM_HOST_TABLE_LAYOUT"), "per_rank",
                f"{p.name}: 'shared' hands rank 0's memfd through "
                "/proc/<pid>/fd/<fd> and hard-fails unless the TP ranks share a "
                "PID namespace (engram.py:605-611). Separate Sparks do not.",
            )

    def test_layout_values_are_the_two_upstream_accepts(self):
        """Anything else raises ValueError at load time (engram.py)."""
        for p in V41_RECIPES:
            val = load(p).env.get("SGLANG_DSV41_ENGRAM_HOST_TABLE_LAYOUT")
            if val is not None:
                self.assertIn(val, ("shared", "per_rank"),
                              f"{p.name}: {val!r} raises at load")


class TP2Feasibility(unittest.TestCase):
    """No V4.1-Flash recipe may claim TP=2. That is arithmetic, not tuning.

    Updated 2026-09-23: TP=3 is no longer a dead end (tonyd2wild's virtual-heads
    lane, work doc 4.5), so a V4.1 recipe below TP=4 is now legal *only* at
    exactly TP=3 and *only* with the virtual-heads declaration. TP=2 stays
    closed: neither the release nor the smaller EXL3 checkpoint fits on a pair
    (work doc 2.5, 3.4).
    """

    def test_no_v41_tp2(self):
        for p in ALL:
            r = load(p)
            if "V4.1" not in r.model:
                continue
            tp = int(r.default("tensor_parallel"))
            if tp >= 4:
                continue
            self.assertEqual(
                tp, 3,
                f"{p.name}: V4.1-Flash at TP={tp}. TP=2 is arithmetic, not "
                "tuning: even the 460 GB EXL3 checkpoint has ~257 GB of "
                "non-Engram weights against 2 x ~110 = 220 GB of usable RAM on "
                "a pair (work doc 2.5, 3.4).",
            )
            self.assertIn(
                "virtual_heads_from", r.rendered(),
                f"{p.name}: V4.1 at TP<4 without the virtual-heads declaration. "
                "64 heads / 8 o_groups do not divide by 3; without the padding "
                "the attention shard is wrong, not merely slow (work doc 4.5).",
            )


class MillionTokenContext(unittest.TestCase):
    """The objective requires at least one recipe at 1M context.

    Guarded as a shipped-artifact invariant so it cannot be silently dropped by
    a future retune. The 1M recipe is the only one that must exceed 1M; the
    others are deliberately 300K (context is traded for nothing below 1M once
    fresh-vs-fresh, upstream measured 500K free over 300K).
    """

    def test_a_recipe_ships_1m(self):
        million = [p for p in EXL3_RECIPES
                   if int(load(p).default("max_model_len")) >= 1000000]
        self.assertTrue(million, "no EXL3 recipe ships a 1M context")

    def test_the_1m_recipe_is_1m(self):
        r = load(EXL3_TP4_1M)
        self.assertGreaterEqual(int(r.default("max_model_len")), 1000000)
        self.assertIn("--max-model-len 1000000", r.rendered())


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
        for p in EXL3_RECIPES:
            r = load(p)
            self.assertIn("--speculative-config", r.flags(), p.name)
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
        expected = {MXFP4_TP2: 1800, NVFP4_TP2: 1800, V41_TP4: 7200, V41_TP8: 7200}
        for p, minimum in expected.items():
            text = p.read_text()
            m = re.search(r"^\s+port_timeout_s:\s*(\d+)\s*$",
                          _strip_comment_lines(text), re.M)
            self.assertIsNotNone(m, f"{p.name}: no readiness.port_timeout_s")
            got = int(m.group(1))
            self.assertGreaterEqual(
                got, minimum,
                f"{p.name}: port_timeout_s {got} < {minimum} -- 510 GB over NFS "
                "takes ~25 min to read before weights even start moving",
            )


class CommentBlockProseStillParsed(unittest.TestCase):
    """F20 regression: prose must not be mistaken for configuration.

    V4.1 recipes deliberately *name* the backend flags they explain the absence
    of ("--moe-runner-backend is deliberately NOT set..."), which is exactly the
    convention that broke an earlier guard in this repo ("``--async-scheduling``
    is deliberately NOT set" tripped the guard forbidding it). This asserts both
    halves on the V4.1 family: the prose is present, and the guard still sees
    nothing.

    Scoped to V4.1 on purpose. The V4-Flash recipes legitimately set
    --moe-runner-backend, so applying the V4.1-forbidden set to them would fail
    on a correct recipe -- the same class of mistake as a guard that only passes
    because it is looking at the wrong thing.
    """

    FORBIDDEN = {"--attention-backend", "--fp8-gemm-backend",
                 "--moe-a2a-backend", "--moe-runner-backend"}

    def test_prose_is_present_and_inert(self):
        mentioned = 0
        for p in V41_RECIPES:
            text = p.read_text()
            r = load(p)
            hit = r.flags() & self.FORBIDDEN
            self.assertFalse(hit,
                             f"{p.name}: {sorted(hit)} leaked from prose into flags")
            mentioned += len(self.FORBIDDEN & set(re.findall(r"--[a-z-]+", text)))
        self.assertGreater(mentioned, 3,
                           "prose-documented forbidden flags vanished; either the "
                           "recipes got thinner or this test stopped proving anything")

    def test_comment_only_flag_does_not_count(self):
        """Prove the stripper works, on a self-contained fixture.

        A forbidden flag named in top-level prose (the house convention, and
        precisely what F20 is about) must be invisible to the parser, while the
        same flag on a command line must be caught. Together they show the guard
        is sensitive to the exact thing it claims to be sensitive to, rather than
        passing because it parsed nothing.
        """
        head = ("model: deepseek-ai/DeepSeek-V4.1-Flash\n"
                "runtime: sglang\ncontainer: x\nmin_nodes: 4\n"
                "defaults:\n  tensor_parallel: 4\n")
        prose = Recipe(
            head + "# the --attention-backend is deliberately NOT set here\n"
                   "command: >\n  sglang serve\n  --tp {tensor_parallel}\n",
            "prose")
        live = Recipe(
            head + "command: >\n  sglang serve\n"
                   "  --attention-backend fa3\n  --tp {tensor_parallel}\n",
            "live")
        self.assertNotIn("--attention-backend", prose.flags(),
                         "a flag named only in prose leaked into the command")
        self.assertIn("--attention-backend", live.flags(),
                      "guard is blind: a live flag was not parsed at all")
        self.assertEqual(prose.rendered().split()[-2:], ["--tp", "4"])

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

    def test_control_b12x_gate_mismatch(self):
        r = self._mutated(MXFP4_TP2, "SGLANG_B12X_MAX_TOKENS: \"8192\"",
                          "SGLANG_B12X_MAX_TOKENS: \"4096\"")
        with self.assertRaises(AssertionError):
            self.assertEqual(r.env["SGLANG_B12X_MAX_TOKENS"],
                             r.flag_value("--chunked-prefill-size"))

    def test_control_nextn_via_default_override(self):
        """The reason guards render: the template only ever holds the placeholder."""
        r = self._mutated(NVFP4_TP2, "speculative_algorithm: DSPARK",
                          "speculative_algorithm: NEXTN")
        with self.assertRaises(AssertionError):
            self.assertNotEqual(r.flag_value("--speculative-algorithm"), "NEXTN")
        # and prove the template itself never said NEXTN
        self.assertNotIn("NEXTN", r.command_template)

    def test_control_expandable_segments_on_v41(self):
        r = self._mutated(
            V41_TP4,
            "SGLANG_ENABLE_DSV41_ENGRAM_HOST_TABLE: \"1\"",
            "PYTORCH_CUDA_ALLOC_CONF: expandable_segments:True\n"
            "  SGLANG_ENABLE_DSV41_ENGRAM_HOST_TABLE: \"1\"",
        )
        with self.assertRaises(AssertionError):
            self.assertNotIn("expandable_segments",
                             r.env.get("PYTORCH_CUDA_ALLOC_CONF", ""))

    def test_control_unconsumed_default(self):
        # Anchor on gpu_memory_utilization rather than a value that may be
        # retuned: a control whose anchor is a tunable number breaks the next
        # time someone tunes it, and then nobody trusts the control.
        r = self._mutated(V41_TP4, "gpu_memory_utilization: 0.80",
                          "gpu_memory_utilization: 0.80\n  kv_pin: 8388608")
        with self.assertRaises(AssertionError):
            for key in r.defaults:
                if key in ENGINE_PLACEHOLDERS:
                    continue
                self.assertIn("{" + key + "}", r.command_template)

    def test_control_nvfp4_flags_copied_to_mxfp4(self):
        r = self._mutated(
            MXFP4_TP2,
            "--speculative-algorithm {speculative_algorithm}",
            "--disable-shared-experts-fusion\n  --speculative-algorithm "
            "{speculative_algorithm}",
        )
        with self.assertRaises(AssertionError):
            self.assertNotIn("--disable-shared-experts-fusion", r.flags())

    def test_control_v41_tp2(self):
        r = self._mutated(V41_TP4, "tensor_parallel: 4", "tensor_parallel: 2")
        with self.assertRaises(AssertionError):
            self.assertGreaterEqual(int(r.default("tensor_parallel")), 4)

    def test_control_shared_engram_layout(self):
        r = self._mutated(V41_TP4, "ENGRAM_HOST_TABLE_LAYOUT: per_rank",
                          "ENGRAM_HOST_TABLE_LAYOUT: shared")
        with self.assertRaises(AssertionError):
            self.assertEqual(r.env["SGLANG_DSV41_ENGRAM_HOST_TABLE_LAYOUT"],
                             "per_rank")

    def test_control_backend_override_on_v41(self):
        r = self._mutated(
            V41_TP4,
            "--speculative-algorithm {speculative_algorithm}",
            "--moe-runner-backend flashinfer_mxfp4\n  --speculative-algorithm "
            "{speculative_algorithm}",
        )
        with self.assertRaises(AssertionError):
            self.assertFalse(r.flags() & {"--moe-runner-backend",
                                         "--attention-backend"})

    def test_control_short_boot_timeout(self):
        text = V41_TP8.read_text().replace("port_timeout_s: 7200",
                                           "port_timeout_s: 600", 1)
        with self.assertRaises(AssertionError):
            self.assertGreaterEqual(int(re.search(
                r"port_timeout_s:\s*(\d+)", _strip_comment_lines(text)).group(1)), 7200)

    def test_control_tp_above_node_count(self):
        r = self._mutated(V41_TP8, "min_nodes: 8", "min_nodes: 2")
        with self.assertRaises(AssertionError):
            self.assertGreaterEqual(r.min_nodes, int(r.default("tensor_parallel")))

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

    def test_control_engram_disk_off(self):
        r = self._mutated(EXL3_TP4, "DSV41_ENGRAM_DISK: \"1\"",
                          "DSV41_ENGRAM_DISK: \"0\"")
        with self.assertRaises(AssertionError):
            self.assertEqual(r.env.get("DSV41_ENGRAM_DISK"), "1")

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
