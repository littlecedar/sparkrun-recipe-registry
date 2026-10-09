"""Guards for the IFM/K2-Horizon-7B-FP8 + Uno Spark recipes.

Run:
    python3 -m unittest discover -s tests -v

Stdlib-only, and deliberately parses recipe TEXT with regex rather than importing
PyYAML: the repo declares jinja2 + netifaces and the offline cache has no PyYAML,
so a test that imports it cannot run on a head node, in a container, or on a
laptop. See AGENTS.md, "tools/ and tests/ are stdlib-only, on purpose".

Where the recipes live. The lane now ships ONE 7B recipe -- the Uno arm at
recipes/ifm/k2-horizon-7b-fp8-uno-sglang.yaml. The plain and NGRAM arms were
retired to attic/ifm/arms/ (see attic/ifm/ARMS-MANIFEST.md for the retire
rationale); they are still guarded here, read by explicit path from ATTIC_DIR,
so their pins and measured numbers stay honest without re-shipping them.

Why these exist. The failure modes here are quiet ones: a recipe that boots,
serves, and returns HTTP 200 while being silently 2x slower than intended, or one
that dies nine minutes into a weight load. Several are regressions waiting to
happen, because the IFM model cards actively recommend values that are wrong on
GB10 -- they pass --attention-backend fa3, which cannot be constructed on compute
capability 12.1, and both of their launch snippets serve the BF16 model rather
than the FP8 one the card documents.

Every guard has a negative control in NegativeControls, because a guard that
cannot fail proves nothing. Controls mutate strings in memory; nothing on disk is
touched.

Sources for the invariants (see K2-7B-MODEL-OPTIMIZATION-WORK.md, same directory):
  container >= v0.5.20 ............. sec 3: models/xllm.py registers
      K2HorizonForCausalLM and is ABSENT at v0.5.19, so an older image refuses the
      architecture outright
  --dtype bfloat16, never auto ..... sec 4.1: _validate_mova_config() raises for
      model_type "k2_horizon" unless torch.get_default_dtype() is bfloat16
  never attention_backend fa3 ...... sec 6.3: create_flashattention_v3_backend
      asserts major in {8,9}; its own message says "use flashinfer"
  fp8_gemm_backend cutlass ......... sec 4.3: `auto` prefers DeepGEMM, whose scale
      layout gates on get_device_sm()==120 exactly and so excludes SM121
  no --quantization flag ........... sec 2.3: config.json carries a self-describing
      quantization_config; naming it again is at best a no-op
  no --speculative-draft-model-path  sec 6.7: _handle_uno raises ("UNO reuses the
      target model") -- likeliest copy-paste from a neighbouring DFLASH recipe
  UNO needs --speculative-num-draft-tokens  sec 6.7: raises unless set explicitly
  every knob reaches command: ........ sec 7.4 of the DS4 doc: a defaults key with
      no placeholder is silently not a setting
  KV fits the pool .................. sec 5: 144 KiB/token; a context that cannot
      hold a few concurrent sequences makes the recipe unusable
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPE_DIR = REPO_ROOT / "recipes" / "ifm"
ATTIC_DIR = REPO_ROOT / "attic" / "ifm" / "arms"

# Only the Uno arm ships. The other two are archived (attic/ifm/arms/) and still
# guarded, so their pins and measured numbers stay verifiable at their new paths.
BASE = ATTIC_DIR / "k2-horizon-7b-fp8-sglang.yaml"
NGRAM = ATTIC_DIR / "k2-horizon-7b-fp8-ngram-sglang.yaml"
UNO = RECIPE_DIR / "k2-horizon-7b-fp8-uno-sglang.yaml"

ALL = [BASE, NGRAM, UNO]

# VERIFIED 2026-09-20 from the HF API. A recipe drifting from these pins is
# serving a different checkpoint than the one the analysis was done against.
MODEL = "IFM/K2-Horizon-7B-FP8"
MODEL_REVISION = "59d473210f0b9ee3ea559a867fc23e7059473944"
# v0.5.20 is the first release containing models/xllm.py (PR #37654).
MIN_SGLANG_TAG = "v0.5.20"
CONTAINER_DIGEST = (
    "sha256:06e4f2ed21afde4ff513cda65070124e727ba23ccaeff7712b8c40e1097d611f"
)

# Flags sglang does not accept at all.
BANNED_ALWAYS = [
    "--enable-auto-tool-choice",   # vLLM-only; not an sglang server arg
    "--hf-overrides",              # sglang spells this --json-model-override-args
]
# Flags _handle_uno rejects with a ValueError.
BANNED_FOR_UNO = [
    "--speculative-draft-model-path",
    "--enable-lora",
    "--enable-deterministic-inference",
    "--enable-strict-thinking",
    "--speculative-use-rejection-sampling",
]

# Model facts behind the memory guard.
#   2 (K and V) * 36 layers * 8 kv_heads * 128 head_dim * 2 bytes (bf16)
KV_BYTES_PER_TOKEN = 2 * 36 * 8 * 128 * 2          # 147,456 B = 144 KiB/token
WEIGHT_BYTES = 11_075_959_853                      # HF API, single shard
DEVICE_BYTES = 128 * (1000 ** 3)                   # GB10 unified, as advertised
MIN_CONCURRENT_FULL_CTX = 4                        # a recipe must admit this many


# ---------------------------------------------------------------------------
# Tiny recipe reader
# ---------------------------------------------------------------------------
def read(path: Path) -> str:
    return path.read_text()


def strip_comments(text: str) -> str:
    """Drop whole-line comments.

    This is the whole point of parsing text rather than YAML. Recipe prose *names*
    the flags it explains the absence of ("--enable-lora is rejected, so it is not
    passed"), and without stripping, every banned-flag guard fires on its own
    documentation.
    """
    return "\n".join(
        ln for ln in text.splitlines() if not ln.lstrip().startswith("#")
    )


def _block(text: str, name: str) -> str:
    m = re.search(r"^%s:\n((?:[ \t].*\n?)+)" % re.escape(name), text, re.M)
    return m.group(1) if m else ""


def top_level(text: str, name: str) -> str | None:
    m = re.search(r"^%s:\s*(.+?)\s*$" % re.escape(name), text, re.M)
    return m.group(1).strip("'\"") if m else None


def knobs(text: str) -> dict[str, str]:
    """Everything recipe render() can substitute: top-level scalars + defaults:.

    sparkrun renders ``render(self.command, {**asdict(self), **self.defaults})``,
    so a command may legitimately consume a top-level key. In practice these
    recipes consume ``{model}`` and ``{model_revision}`` from the top level and
    everything else from ``defaults:``, so both are in scope here.
    """
    out: dict[str, str] = {}
    for line in _block(text, "defaults").splitlines():
        m = re.match(r"^  ([A-Za-z0-9_]+):\s*(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip("'\"")
    for key in ("model", "model_revision"):
        val = top_level(text, key)
        if val is not None:
            out.setdefault(key, val)
    return out


# Top-level keys sparkrun consumes itself, never via a command placeholder.
NOT_PLACEHOLDERS = {"model", "model_revision", "runtime", "container",
                    "min_nodes", "max_nodes"}


def command(text: str) -> str:
    """The `command:` value folded to one line. Handles `>` blocks and quoting."""
    m = re.search(r"^command:\s*[>|]?\s*\n((?:[ \t]+.*\n?)+)", text, re.M)
    if m:
        return " ".join(m.group(1).split())
    m = re.search(r"^command:\s*['\"]?(.*?)['\"]?\s*$", text, re.M)
    return " ".join(m.group(1).split()) if m else ""


def placeholders(text: str) -> set[str]:
    return set(re.findall(r"\{([A-Za-z0-9_]+)\}", command(text)))


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------
class RecipeExistence(unittest.TestCase):
    def test_all_recipes_present(self):
        for p in ALL:
            self.assertTrue(p.is_file(), "missing recipe %s" % p)

    def test_shipped_set_is_exactly_uno_with_siblings_archived(self):
        """Catch an orphaned or un-retired 7B-FP8 file before it forks the lineage."""
        found = sorted(p.name for p in RECIPE_DIR.glob("*7b-fp8*.yaml"))
        self.assertEqual(
            found,
            ["k2-horizon-7b-fp8-uno-sglang.yaml"],
            "recipes/ifm/ ships the Uno arm only",
        )
        # Hard existence check on the archived siblings, NOT a glob equality:
        # attic/ifm/arms/ already holds the 36B arms, so name the 7B ones directly.
        for p in (BASE, NGRAM):
            self.assertTrue(p.is_file(), "archived recipe missing %s" % p)


class ContainerPin(unittest.TestCase):
    def test_tag_is_new_enough_for_xllm(self):
        for p in ALL:
            c = strip_comments(read(p))
            self.assertIn(MIN_SGLANG_TAG, c,
                          "%s does not pin >= %s, the first release with "
                          "models/xllm.py" % (p.name, MIN_SGLANG_TAG))

    def test_digest_pinned_not_moving_tag(self):
        for p in ALL:
            self.assertIn(CONTAINER_DIGEST, strip_comments(read(p)),
                          "%s is not digest-pinned" % p.name)

    def test_no_dev_tag(self):
        for p in ALL:
            self.assertNotIn("sglang:dev", strip_comments(read(p)),
                             "%s uses a moving dev tag" % p.name)


class ModelPin(unittest.TestCase):
    def test_revision_pin_matches_the_analysed_checkpoint(self):
        for p in ALL:
            self.assertEqual(knobs(strip_comments(read(p))).get("model_revision"),
                             MODEL_REVISION,
                             "%s drifts from the analysed checkpoint" % p.name)

    def test_revision_reaches_the_engine(self):
        """A pin that never reaches --revision is not a pin: the offline cache
        has snapshots/<sha>/ but no refs/, so the engine cannot re-resolve it."""
        for p in ALL:
            self.assertIn("--revision", command(strip_comments(read(p))),
                          "%s pins a revision but never passes it" % p.name)

    def test_model_field_is_the_fp8_repo(self):
        """Both IFM cards serve the BF16 repo from their snippets. Do not import
        that mistake into a recipe whose whole point is the FP8 artifact."""
        for p in ALL:
            self.assertEqual(top_level(read(p), "model"), MODEL,
                             "%s serves something other than %s" % (p.name, MODEL))

    def test_trust_remote_code_present(self):
        """The checkpoint carries auto_map. sglang ships a thin native
        K2HorizonConfig, but the flag keeps the launch robust to which side wins."""
        for p in ALL:
            self.assertIn("--trust-remote-code", command(strip_comments(read(p))))


class DtypeIsSpelled(unittest.TestCase):
    def test_dtype_is_bfloat16_everywhere(self):
        for p in ALL:
            t = strip_comments(read(p))
            self.assertEqual(knobs(t).get("dtype"), "bfloat16",
                             "%s: --dtype must be bfloat16, not auto" % p.name)
            self.assertIn("--dtype {dtype}", command(t))

    def test_auto_dtype_never_appears(self):
        """Anchored on the KEY, not a substring: `kv_cache_dtype: auto` is a
        legitimate and expected line, and a naive substring check flags it."""
        for p in ALL:
            t = strip_comments(read(p))
            self.assertIsNone(re.search(r"^\s*dtype:\s*auto\s*$", t, re.M),
                              "%s sets dtype: auto" % p.name)
            self.assertEqual(knobs(t).get("dtype"), "bfloat16")


class AttentionBackend(unittest.TestCase):
    def test_no_recipe_asks_for_fa3(self):
        """fa3 asserts major in {8,9}. Its own error says 'use flashinfer'."""
        for p in ALL:
            t = strip_comments(read(p))
            self.assertNotEqual(knobs(t).get("attention_backend"), "fa3",
                                "%s: fa3 cannot be constructed on GB10" % p.name)
            self.assertNotIn("--attention-backend fa3", command(t))

    def test_baseline_and_ngram_use_flashinfer(self):
        for p in (BASE, NGRAM):
            self.assertEqual(knobs(strip_comments(read(p)))["attention_backend"],
                             "flashinfer")

    def test_uno_uses_fa4_and_mounts_both_mods(self):
        t = strip_comments(read(UNO))
        self.assertEqual(knobs(t).get("attention_backend"), "fa4",
                         "the Uno probe is only meaningful with fa4")
        self.assertIn("probe-uno-fa4-sm121", t)
        self.assertIn("provide-uno-lora-k2-horizon-7b", t)


class Fp8GemmBackend(unittest.TestCase):
    def test_cutlass_pinned(self):
        for p in (BASE, NGRAM):
            t = strip_comments(read(p))
            self.assertEqual(knobs(t).get("fp8_gemm_backend"), "cutlass",
                             "%s: `auto` prefers DeepGEMM, whose scale layout "
                             "excludes SM121" % p.name)
            self.assertIn("--fp8-gemm-backend {fp8_gemm_backend}", command(t))


class NoRedundantQuantization(unittest.TestCase):
    def test_no_quantization_flag(self):
        for p in ALL:
            self.assertNotIn("--quantization", command(strip_comments(read(p))),
                             "%s: config.json self-describes; a second opinion "
                             "can only conflict" % p.name)


class BannedFlags(unittest.TestCase):
    def test_vllm_only_flags_absent(self):
        for p in ALL:
            c = command(strip_comments(read(p)))
            for flag in BANNED_ALWAYS:
                self.assertNotIn(flag, c, "%s passes vLLM-only %s" % (p.name, flag))

    def test_uno_rejections_absent(self):
        c = command(strip_comments(read(UNO)))
        for flag in BANNED_FOR_UNO:
            self.assertNotIn(flag, c, "_handle_uno raises on %s" % flag)

    def test_uno_contract(self):
        t = strip_comments(read(UNO))
        self.assertIn("--speculative-num-draft-tokens", command(t),
                      "UNO raises unless this is set explicitly")
        self.assertEqual(knobs(t).get("tensor_parallel"), "1",
                         "UNO requires TP=PP=1")
        self.assertEqual(knobs(t).get("speculative_algorithm"), "UNO")
        self.assertIn("--uno-lora-path {uno_lora_path}", command(t))
        # Linear mode: topk 1 makes num-draft-tokens the draft WIDTH.
        self.assertEqual(knobs(t).get("speculative_eagle_topk"), "1")

    def test_uno_recipe_does_not_claim_a_second_backend_for_linear_mode(self):
        """The Uno recipe is LINEAR (topk 1). In linear mode UNO builds NO
        second attention backend and NO second CUDA-graph pool -- both are gated
        on tree_mode in uno_worker_v2.py. An earlier revision justified
        gpu_memory_utilization: 0.82 with "a second backend + second graph pool",
        which is a tree-mode fact and would mislead a later owner into the wrong
        knob move. Guard the prose against the mistake returning.

        The check is on the *assertive* phrasing, not the substring: the
        corrected comment mentions "second backend" only to deny it, and a guard
        that cannot tell a claim from its refutation would just fail on the fix.
        """
        t = read(UNO)
        # The original wrong justification, verbatim.
        self.assertNotIn("UNO allocates a SECOND attention", t,
                         "linear Uno does not build a second attention backend")
        self.assertNotIn("on top of the target's", t,
                         "that clause belonged to the wrong (tree-mode) rationale")
        # And the corrected reason must be present, so nobody 'simplifies' 0.82
        # back to an unexplained number.
        self.assertIn("tree_mode", t,
                      "the correction cites the tree_mode gate; keep it")
        self.assertIn("NO second backend", t,
                      "the correction should state the linear-mode fact")

    def test_ngram_needs_no_draft_weights(self):
        """No trained draft exists for this family; naming one 404s at sync time
        on every node, after the distribution has already succeeded."""
        t = strip_comments(read(NGRAM))
        self.assertNotIn("--speculative-draft-model-path", command(t))
        self.assertEqual(knobs(t).get("speculative_algorithm"), "NGRAM")
        self.assertIn("--speculative-num-draft-tokens", command(t))

    def test_ngram_drives_breadth_not_eagle_topk(self):
        """NGRAM must set breadth via --speculative-ngram-max-bfs-breadth.

        _handle_ngram declares, unconditionally (no `is None` guard):
            speculative_eagle_topk = cfg.speculative_ngram_max_bfs_breadth
        and resolution_result() (arg_groups/overrides.py:248-272 at v0.5.20)
        consults the declaration stash BEFORE _raw_input -- i.e. before whatever
        the operator typed. So `--speculative-eagle-topk 4` on an NGRAM launch is
        at best redundant and at worst silently replaced by the breadth default
        (10). A recipe that "sets" breadth that way benchmarks a different width
        than it advertises, and the log will not say so.

        num-draft-tokens is NOT affected: _handle_ngram declares it only when it
        is None, so passing it is honoured. That asymmetry is the whole trap.
        """
        t = strip_comments(read(NGRAM))
        self.assertNotIn("--speculative-eagle-topk", command(t),
                         "NGRAM breadth must be set via --speculative-ngram-max-bfs-breadth; "
                         "eagle_topk is overwritten by _handle_ngram")
        self.assertIn("--speculative-ngram-max-bfs-breadth", command(t))
        breadth = knobs(t).get("speculative_ngram_max_bfs_breadth")
        self.assertIsNotNone(breadth, "breadth must be an explicit knob")
        self.assertLessEqual(int(breadth), 10, "breadth is the sglang ceiling")
        # num_steps is derived as draft_tokens // topk, so a breadth that does
        # not divide the verify width silently floors the derivation to 1.
        self.assertEqual(int(knobs(t)["speculative_num_draft_tokens"]) % int(breadth), 0,
                         "num_draft_tokens must be a multiple of breadth")


class KnobsAreConsumed(unittest.TestCase):
    def test_every_knob_reaches_command(self):
        """A defaults key with no placeholder is silently not a setting."""
        for p in ALL:
            t = strip_comments(read(p))
            ph = placeholders(t)
            for key in knobs(t):
                if key in ph or key in NOT_PLACEHOLDERS:
                    continue
                self.fail("%s: %s is defined but never referenced by command:"
                          % (p.name, key))

    def test_no_phantom_placeholders(self):
        """A placeholder with no definition renders literally or fails."""
        for p in ALL:
            t = strip_comments(read(p))
            missing = placeholders(t) - set(knobs(t))
            self.assertFalse(missing, "%s: unresolved placeholders %s"
                             % (p.name, sorted(missing)))


class MemoryFit(unittest.TestCase):
    def test_context_fits_the_pool(self):
        """A full-length sequence must not be able to eat the pool by itself."""
        for p in ALL:
            t = strip_comments(read(p))
            d = knobs(t)
            ctx = int(d["max_model_len"])
            frac = float(d["gpu_memory_utilization"])
            pool = DEVICE_BYTES * frac - WEIGHT_BYTES
            need = ctx * KV_BYTES_PER_TOKEN
            self.assertGreater(
                pool / need, MIN_CONCURRENT_FULL_CTX,
                "%s: ctx=%d needs %.1f GB of bf16 KV, pool ~%.1f GB admits only "
                "%.1f concurrent full-length sequences"
                % (p.name, ctx, need / 1e9, pool / 1e9, pool / need),
            )

    def test_kv_dtype_left_at_model_dtype(self):
        """fp8 KV halves the KV term but is unscored for this family: an arm, not
        a default. If it becomes the default, update this with a citation."""
        for p in ALL:
            self.assertEqual(knobs(strip_comments(read(p)))["kv_cache_dtype"], "auto")

    def test_gb10_memory_ceiling_respected(self):
        for p in ALL:
            frac = float(knobs(strip_comments(read(p)))["gpu_memory_utilization"])
            self.assertLessEqual(frac, 0.85, "AGENTS.md GB10 ceiling is ~0.85")

    def test_single_node(self):
        """The artifact is 11 GB on a 128 GB box. TP>1 splits 8 KV heads and adds
        an all-reduce per layer over the subsystem that is already the limit."""
        for p in ALL:
            t = strip_comments(read(p))
            self.assertEqual(top_level(t, "min_nodes"), "1")
            self.assertEqual(knobs(t).get("tensor_parallel"), "1")


class Parsers(unittest.TestCase):
    def test_both_k2_horizon_parsers(self):
        for p in ALL:
            c = command(strip_comments(read(p)))
            self.assertIn("--reasoning-parser k2_horizon", c)
            self.assertIn("--tool-call-parser k2_horizon", c)


class UnoConcurrencyCap(unittest.TestCase):
    def test_admission_cap_clears_the_measured_flatline(self):
        """UNO flatlines at c=8 when --max-running-requests is 8.

        Measured 2026-10-09 (`benchmarking/concurrency-sweep.yaml`, tg=256,
        aggregate decode): at max_num_seqs 8 the arm sits at 97.5 at c=8 --
        BELOW its own c=4 of 98.6 -- while the plain 7B reaches 120. At 32 the
        same arm scales to 145.5, the best c8 figure in the lane. The cap is a
        scheduler admission limit, not memory, so a "tidy" lowering of this
        number silently converts the fastest arm in the lane into one that does
        not scale. 16 is a floor, not the measured value; the recipe ships 32.
        """
        t = strip_comments(read(UNO))
        self.assertGreaterEqual(
            int(knobs(t)["max_num_seqs"]), 16,
            "UNO needs an admission cap above the c=8 flatline (see the banner)")


class ModHygiene(unittest.TestCase):
    def test_mods_exist_and_are_executable(self):
        for name in ("probe-uno-fa4-sm121", "provide-uno-lora-k2-horizon-7b"):
            run = REPO_ROOT / "mods" / name / "run.sh"
            self.assertTrue(run.is_file(), "missing %s" % run)
            self.assertTrue(run.stat().st_mode & 0o111, "%s not executable" % run)

    def test_probe_patch_is_anchored_and_single_shot(self):
        src = (REPO_ROOT / "mods" / "probe-uno-fa4-sm121" / "run.sh").read_text()
        self.assertIn("count != 1", src,
                      "patch must refuse when the anchor count is not exactly 1")
        self.assertIn("sys.exit(1)", src)

    @staticmethod
    def _mod_literal(src: str, name: str) -> str:
        """Extract a `NAME = '''...'''` literal from the mod, honouring any
        trailing same-line expression such as `.replace("{TUPLE}", repr(allowed))`.

        The trailing-expression support is deliberate: the mod builds its
        replacement text from an env var, so the literal is not the whole right
        hand side. A guard that only copes with a bare literal would silently
        stop checking the text that actually gets written -- which is the exact
        case worth guarding.
        """
        m = re.search(r"^%s = ('''.*?''')" % re.escape(name), src, re.M | re.S)
        assert m, "mod must define a %s literal" % name
        tail = src[m.end():].split("\n", 1)[0]
        if tail.strip():
            # Placeholder for the mod's `allowed` tuple. Kept in sync with the
            # mod's real UNO_ATTN_BACKENDS default by
            # test_probe_default_gate_admits_both_lanes.
            return eval("(" + m.group(1) + ")" + tail,
                        {"allowed": ("fa3", "fa4", "triton")})
        return eval(m.group(1))

    @staticmethod
    def _step3_checker(src: str) -> str:
        """Extract the Step-3 post-patch checker heredoc from the mod.

        Step 3 is the block that re-imports speculative_hook after patching and
        asserts the gate landed. It once contained a launch-killing bug (searched
        the patched source for double-quoted backend names while Step 2 emits
        single quotes via repr()), so it is worth executing in a test rather than
        only pattern-matching.
        """
        marker = "# Step 3 - post-patch import smoke test"
        body = src.split(marker, 1)[1]
        # The first python heredoc after the marker.
        m = re.search(r"python3 - <<'PY'\n(.*?)\nPY\n", body, re.S)
        assert m, "mod must contain a Step-3 python heredoc"
        return m.group(1)

    def test_probe_default_gate_admits_both_lanes(self):
        """The gate's default must admit every lane the README documents.

        If UNO_ATTN_BACKENDS defaults to a strict subset, a lane-B run needs env
        propagation that was never confirmed to reach mod scripts -- so the lane
        silently can't run. Keep the default the union of the documented lanes.
        """
        src = (REPO_ROOT / "mods" / "probe-uno-fa4-sm121" / "run.sh").read_text()
        m = re.search(r'export UNO_ATTN_BACKENDS="\$\{UNO_ATTN_BACKENDS:-([^}]*)\}"',
                      src)
        self.assertIsNotNone(m, "mod must export a single-source UNO_ATTN_BACKENDS")
        admitted = tuple(b.strip() for b in m.group(1).split(",") if b.strip())
        self.assertIn("fa3", admitted, "stock fa3 must never be dropped")
        self.assertIn("fa4", admitted, "fa4 lane must be admitted by default")
        self.assertIn("triton", admitted, "triton lane must be admitted by default")

    def test_probe_checks_the_vendored_cute_path(self):
        """The mod's FA4 probe must check the path the engine actually imports.

        flash_attention_v4.py imports the VENDORED
        `sglang.kernels.ops.attention.flash_attn.cute` unless
        SGLANG_INKLING_FA4_USE_PIP=1, in which case it imports the pip
        `flash_attn.cute`. An earlier probe checked only the pip
        `flash_attn.cute.interface`, so on a stock image it could report FAIL and
        send the whole Uno arm down a "blocked on a dependency" path that was not
        true. Pin the module name this repo's probe uses.
        """
        src = (REPO_ROOT / "mods" / "probe-uno-fa4-sm121" / "run.sh").read_text()
        # Step 1 tees its output into the mod log, so the heredoc opener carries a
        # pipe rather than a bare `|| true`. Match the heredoc itself.
        step1 = re.search(r"python3 - <<'PY'[^\n]*\n(.*?)\nPY\n", src, re.S)
        self.assertIsNotNone(step1, "Step 1 must be a python heredoc")
        body = step1.group(1)
        self.assertIn("SGLANG_INKLING_FA4_USE_PIP", body,
                      "probe must honour the pip/vendored switch the engine uses")
        self.assertIn("sglang.kernels.ops.attention.flash_attn.cute", body,
                      "probe must import the vendored CUTE package by default")

    def test_probe_reowns_the_whole_cache_mount(self):
        """Importing the engine as root poisons the bind-mounted runtime cache.

        A root-run `import sglang` triggers flashinfer JIT against /cache/runtime,
        dropping root-owned files uid 1000 can neither write nor unlink, and every
        later launch of that model key then fails with PermissionError. Both Step 1
        and Step 3 import the engine, so the mod must re-own the WHOLE mount, not
        just the log directory. See .swival/memory/sparkrun-notes.md.
        """
        src = (REPO_ROOT / "mods" / "probe-uno-fa4-sm121" / "run.sh").read_text()
        self.assertIn("reown \"${CACHEDIR}\"", src,
                      "mod must re-own /cache/runtime after importing the engine")
        # The old, insufficient form re-owned only the log dir.
        self.assertNotIn('reown "${LOGDIR}"\n', src,
                         "re-owning only the log dir misses the JIT cache")
        # ids must be derived from the mount, not hardcoded.
        self.assertIn("USER_UID", src)
        self.assertIn("stat -c '%u'", src)

    def test_probe_output_reaches_the_mod_log(self):
        """The README tells operators to read the probe result from the mod log.

        The probe heredoc prints the anchor count and the CUTE result; if it only
        goes to stdout, `${LOGDIR}/probe-uno-fa4-sm121.log` does not contain the
        thing the failure-mode table says to check.
        """
        src = (REPO_ROOT / "mods" / "probe-uno-fa4-sm121" / "run.sh").read_text()
        step1_open = re.search(r"python3 - <<'PY'([^\n]*)\n", src)
        self.assertIsNotNone(step1_open)
        self.assertIn("tee", step1_open.group(1),
                      "Step 1 output must be teed into the mod log")

    def test_probe_repatch_handles_a_changed_backend_set(self):
        """Changing UNO_ATTN_BACKENDS after a patch must not accuse the image.

        Once patched, the OLD anchor is gone; a naive re-run with a different set
        hit `count != 1` and printed "the base image has changed" -- a false
        accusation that also aborts the launch. The mod must detect the existing
        assignment and rewrite just the tuple.
        """
        src = (REPO_ROOT / "mods" / "probe-uno-fa4-sm121" / "run.sh").read_text()
        self.assertIn("re-patched gate", src,
                      "mod must have an explicit re-patch path")
        self.assertIn("ast.literal_eval", src)

    def test_step3_check_is_quote_agnostic(self):
        """Regression: the post-patch check must not assume a quote style.

        Step 2 emits `_UNO_ALLOWED_BACKENDS = ('fa3', 'fa4', 'triton')` through
        repr(), i.e. single quotes. An earlier Step 3 searched for `"fa3"`
        (double-quoted), always concluded the gate was missing backends, and --
        under `set -e` -- aborted the launch with a message that blamed the patch.
        Guard both the absence of that trap and the presence of a real parse.
        """
        src = (REPO_ROOT / "mods" / "probe-uno-fa4-sm121" / "run.sh").read_text()
        checker = self._step3_checker(src)
        self.assertNotIn("'\"%s\"' % b", checker,
                         "checker must not grep for double-quoted names")
        self.assertIn("ast.literal_eval", checker,
                      "checker must parse the emitted tuple, not grep it")

    def test_patched_message_interpolates_its_fields(self):
        """Regression: NOT a .format() template, so no doubled braces.

        The replacement text is inserted with str.replace(), not str.format().
        An earlier version doubled the braces (`{{prefill_backend!r}}`) out of
        format-string habit, so the patched gate raised a message reading
        "got prefill={prefill_backend!r}" -- the interpolation never happened.
        A wrong-but-raise-only path is low-severity, but it is the kind of error
        that survives every parse check because the file is still valid Python.
        """
        src = (REPO_ROOT / "mods" / "probe-uno-fa4-sm121" / "run.sh").read_text()
        new_v = self._mod_literal(src, "NEW")
        self.assertNotIn("{{", new_v,
                         "NEW is str.replace()d, not .format()ted; braces must be "
                         "single")
        self.assertIn("prefill={prefill_backend!r}", new_v)
        # Compile the emitted block as a function body and prove it interpolates.
        ns: dict = {}
        ns["attention_backends_of"] = lambda _s: ("flashinfer", "triton")
        ns["resolved_view"] = lambda s: s
        exec(compile("def _handle_uno(server_args):\n" + new_v, "<msg>", "exec"), ns)
        with self.assertRaises(ValueError) as ctx:
            ns["_handle_uno"](None)
        msg = str(ctx.exception)
        self.assertIn("'flashinfer'", msg)
        self.assertIn("'triton'", msg)
        self.assertNotIn("prefill_backend!r", msg,
                         "message must interpolate, not print the field name")

    @staticmethod
    def _run_step3(checker: str, handle_uno_src: str, env: dict) -> tuple:
        """Execute the mod's real Step-3 checker against a synthetic _handle_uno.

        Returns (exit_code, captured_stdout). Uses a stub `sglang...speculative_hook`
        module whose `_handle_uno` is compiled from `handle_uno_src`, so the
        checker's `inspect.getsource` sees exactly the patched text under test.
        """
        import contextlib
        import io
        import linecache
        import os
        import sys
        import types

        # inspect.getsource (used by the checker) reads from linecache, which
        # only knows real files by default. Register the synthetic patched source
        # under a fake filename so getsource sees exactly the text under test.
        fake_path = "<patched_handle_uno>"
        linecache.cache[fake_path] = (
            len(handle_uno_src), None, handle_uno_src.splitlines(True), fake_path)
        ns: dict = {"__file__": fake_path}
        exec(compile(handle_uno_src, fake_path, "exec"), ns)
        fake = types.ModuleType("sglang.srt.arg_groups.speculative_hook")
        fake.__file__ = fake_path
        fake._handle_uno = ns["_handle_uno"]

        module_names = ("sglang", "sglang.srt", "sglang.srt.arg_groups",
                        "sglang.srt.arg_groups.speculative_hook")
        saved = {k: sys.modules.get(k) for k in module_names}
        made = []
        for name in module_names[:-1]:
            if name not in sys.modules:
                sys.modules[name] = types.ModuleType(name)
                made.append(name)
        sys.modules[module_names[-1]] = fake

        saved_env = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        rc = 0
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                exec(compile(checker, "<step3>", "exec"), {"__name__": "__main__"})
        except SystemExit as e:
            rc = e.code or 0
        finally:
            for name in made:
                sys.modules.pop(name, None)
            for k, v in saved.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v
            for k, v in saved_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        return rc, buf.getvalue()

    @staticmethod
    def _patched_handle_uno(allowed: tuple) -> str:
        return (
            "def _handle_uno(server_args):\n"
            "    prefill_backend, decode_backend = "
            "attention_backends_of(resolved_view(server_args))\n"
            "    _UNO_ALLOWED_BACKENDS = %s\n" % (repr(allowed),) +
            "    if (prefill_backend not in _UNO_ALLOWED_BACKENDS\n"
            "        or decode_backend not in _UNO_ALLOWED_BACKENDS\n"
            "        or prefill_backend != decode_backend):\n"
            "        raise ValueError('x')\n"
        )

    def test_step3_check_passes_on_a_correct_patch(self):
        """Execute the real Step-3 checker against a faithfully patched source.

        A check that cannot pass on the output its own sibling produces is worse
        than no check: it fails the launch while pointing at the wrong cause.
        """
        src = (REPO_ROOT / "mods" / "probe-uno-fa4-sm121" / "run.sh").read_text()
        checker = self._step3_checker(src)
        rc, out = self._run_step3(
            checker, self._patched_handle_uno(("fa3", "fa4", "triton")),
            {"UNO_ATTN_BACKENDS": "fa3,fa4,triton"})
        self.assertEqual(rc, 0, "Step-3 checker failed on a correct patch: %s" % out)
        self.assertIn("post-patch import OK", out)

    def test_step3_check_still_catches_a_narrowed_gate(self):
        """Negative control for the above: a gate that dropped a requested
        backend must still make the checker exit non-zero, or the fix traded a
        false failure for a false pass."""
        src = (REPO_ROOT / "mods" / "probe-uno-fa4-sm121" / "run.sh").read_text()
        checker = self._step3_checker(src)
        rc, out = self._run_step3(
            checker, self._patched_handle_uno(("fa3", "fa4")),
            {"UNO_ATTN_BACKENDS": "fa3,fa4,triton"})
        self.assertNotEqual(rc, 0,
                            "checker must fail when a requested backend is missing")
        self.assertIn("missing requested backends", out)

    def test_step3_check_catches_a_dropped_fa3(self):
        """The gate must never be narrower than stock. Dropping fa3 is the one
        narrowing that must fail even when the caller asked for it."""
        src = (REPO_ROOT / "mods" / "probe-uno-fa4-sm121" / "run.sh").read_text()
        checker = self._step3_checker(src)
        rc, out = self._run_step3(
            checker, self._patched_handle_uno(("fa4", "triton")),
            {"UNO_ATTN_BACKENDS": "fa4,triton"})
        self.assertNotEqual(rc, 0, "checker must reject a gate that dropped fa3")
        self.assertIn("dropped fa3", out)

    def test_probe_replacement_is_valid_python(self):
        """The replacement block is a string inside a shell heredoc inside a
        YAML-adjacent mod. Four layers in which a stray indent survives every
        other check here and only shows up as a crash at server start.

        So: extract OLD and NEW, require them to be distinct, and compile NEW as
        the body of a function. This is the cheap half of the verification. The
        expensive half -- confirming OLD matches the real v0.5.20
        speculative_hook.py exactly once -- was done out-of-band on 2026-09-21:
        the anchor was tested against the v0.5.20 source fetched from GitHub
        (count == 1) and against the engine inside a real sglang image
        (count == 1). It is not asserted here because it needs the network or the
        image; re-run those two checks when bumping the pin.
        """
        src = (REPO_ROOT / "mods" / "probe-uno-fa4-sm121" / "run.sh").read_text()
        old_v = self._mod_literal(src, "OLD")
        new_v = self._mod_literal(src, "NEW")
        self.assertNotEqual(old_v, new_v)
        # Anchor is a whole `if` block ending in the raise; sanity-check its shape.
        self.assertIn('!= ("fa3", "fa3")', old_v)
        self.assertIn("raise ValueError", old_v)
        # The replacement must be valid Python as a function body, at the same
        # 4-space indentation it will land at inside _handle_uno.
        compile("def _gate(server_args):\n" + new_v, "<patch>", "exec")
        self.assertIn("_UNO_ALLOWED_BACKENDS = (", new_v)
        # and it must still reject a mismatched pair, not just accept everything
        self.assertIn("prefill_backend != decode_backend", new_v)

    def test_probe_still_rejects_mismatched_backends(self):
        """Behaviour check, not just a parse check: fa3 prefill + fa4 decode must
        raise. Accepting any pair would silently change what UNO validates."""
        src = (REPO_ROOT / "mods" / "probe-uno-fa4-sm121" / "run.sh").read_text()
        new_v = self._mod_literal(src, "NEW")
        ns: dict = {}
        state: dict = {}
        ns["attention_backends_of"] = lambda _s: state["pair"]
        ns["resolved_view"] = lambda s: s
        exec(compile("def gate(server_args):\n" + new_v, "<g>", "exec"), ns)
        for pair, should_raise in (
                (("fa3", "fa3"), False), (("fa4", "fa4"), False),
                (("fa3", "fa4"), True), (("fa4", "fa3"), True),
                (("flashinfer", "flashinfer"), True), (("fa4", "triton"), True)):
            state["pair"] = pair
            if should_raise:
                with self.assertRaises(ValueError, msg="%s must be rejected" % (pair,)):
                    ns["gate"](None)
            else:
                try:
                    ns["gate"](None)
                except ValueError as exc:               # pragma: no cover
                    self.fail("%s must be accepted, got: %s" % (pair, exc))

    def test_probe_gate_is_env_configurable_without_narrowing(self):
        """UNO_ATTN_BACKENDS must widen, never narrow below stock fa3.

        A probe knob that can make the gate *stricter* manufactures a "UNO
        rejected my backend" failure that looks like a result and is only the
        knob. The mod prepends fa3 for that reason; this asserts it does.
        """
        src = (REPO_ROOT / "mods" / "probe-uno-fa4-sm121" / "run.sh").read_text()
        self.assertIn('if "fa3" not in allowed:', src)
        self.assertIn('allowed = ("fa3",) + allowed', src)

    def test_probe_leaves_the_fa3_capability_assert_alone(self):
        """One variable only. Neutering the registry assert converts an honest
        'this backend does not exist here' into an illegal-instruction crash.

        Checked on executable lines: the mod *documents* the registry assert in
        comments, and a mod that does not explain what it declined to patch is
        worse than one that does.
        """
        src = strip_comments(
            (REPO_ROOT / "mods" / "probe-uno-fa4-sm121" / "run.sh").read_text())
        self.assertNotIn("attention_registry", src,
                         "mod must not patch attention_registry.py")
        # ...and everything it writes must go to the one speculative-gate file.
        # There are two write_text() calls (initial patch, and re-patch when the
        # backend set changes), but both must target the same `target` path.
        targets = re.findall(r'target\s*=\s*.+', src)
        self.assertTrue(targets, "mod should locate its target explicitly")
        for line in targets:
            self.assertIn("arg_groups/speculative_hook.py", line)
        writes = re.findall(r"([A-Za-z_][\w.]*)\.write_text\(", src)
        self.assertEqual(set(writes), {"target"},
                         "every write must go through `target`, not a new path")

    def test_lora_mod_verifies_by_digest(self):
        src = (REPO_ROOT / "mods" / "provide-uno-lora-k2-horizon-7b"
               / "run.sh").read_text()
        self.assertIn("sha256sum", src)
        self.assertIn("1396763616", src, "adapter size pin is load-bearing")

    def test_every_mod_named_by_a_recipe_exists(self):
        """`sparkrun recipe validate` does NOT resolve `mods:` entries.

        VERIFIED 2026-09-21 by validating a copy whose mod name was corrupted: it
        exits 0 with one unrelated suggestion. So a typo here ships silently and
        surfaces at launch -- for the Uno recipe that means sglang starts with no
        gate patch and dies on "UNO requires FA3", which reads like a model or
        engine problem rather than a broken recipe. This is the guard validate
        will not do for us.
        """
        for p in ALL:
            body = _block(strip_comments(read(p)), "mods")
            # Accept both the registry-scoped "@littlecedar/mods/<name>" and the
            # bare "mods/<name>" form: this lane switched to bare on 2026-10-08
            # because the scoped form resolves against the published registry
            # clone, which does not carry these unpublished mods.
            for entry in re.findall(r"-\s*[\"']?(@?[\w./-]+)[\"']?", body):
                name = entry.split("/")[-1]
                run = REPO_ROOT / "mods" / name / "run.sh"
                self.assertTrue(run.is_file(),
                                "%s references %s but %s does not exist"
                                % (p.name, entry, run))

    def test_mod_order_puts_the_fetch_first(self):
        """The `mods:` list is an ordered dependency chain, not a set (AGENTS.md).

        The adapter must exist on disk before sglang reads --uno-lora-path, so
        provide-* has to precede probe-*; and the gate patch must be applied
        before the server starts either way.
        """
        body = _block(strip_comments(read(UNO)), "mods")
        names = [e.split("/")[-1]
                 for e in re.findall(r"-\s*[\"']?(@?[\w./-]+)[\"']?", body)]
        self.assertIn("provide-uno-lora-k2-horizon-7b", names)
        self.assertIn("probe-uno-fa4-sm121", names)
        self.assertLess(names.index("provide-uno-lora-k2-horizon-7b"),
                        names.index("probe-uno-fa4-sm121"),
                        "adapter must be fetched before the gate is patched")


# ---------------------------------------------------------------------------
# Negative controls: each proves its guard can actually fail
# ---------------------------------------------------------------------------
class NegativeControls(unittest.TestCase):
    def test_comment_prose_cannot_trip_the_banned_flag_guard(self):
        t = read(UNO) + "\n# --enable-lora is rejected by _handle_uno, so absent\n"
        self.assertNotIn("--enable-lora", command(strip_comments(t)))

    def test_fa3_would_be_detected(self):
        mutated = read(BASE).replace("attention_backend: flashinfer",
                                     "attention_backend: fa3")
        self.assertEqual(knobs(strip_comments(mutated))["attention_backend"], "fa3")

    def test_drifted_revision_would_be_detected(self):
        mutated = read(BASE).replace(MODEL_REVISION, "main")
        self.assertNotEqual(knobs(strip_comments(mutated))["model_revision"],
                            MODEL_REVISION)

    def test_old_image_would_be_detected(self):
        mutated = read(BASE).replace(MIN_SGLANG_TAG, "v0.5.19")
        self.assertNotIn(MIN_SGLANG_TAG, strip_comments(mutated))

    def test_auto_dtype_would_be_detected(self):
        mutated = read(BASE).replace("dtype: bfloat16", "dtype: auto")
        self.assertNotEqual(knobs(strip_comments(mutated))["dtype"], "bfloat16")

    def test_oversized_context_would_be_rejected(self):
        """512K of bf16 KV is 72 GiB. The guard must refuse it at 0.85."""
        mutated = read(BASE).replace("max_model_len: 131072", "max_model_len: 524288")
        d = knobs(strip_comments(mutated))
        pool = DEVICE_BYTES * float(d["gpu_memory_utilization"]) - WEIGHT_BYTES
        self.assertLess(pool / (int(d["max_model_len"]) * KV_BYTES_PER_TOKEN),
                        MIN_CONCURRENT_FULL_CTX)

    def test_orphaned_knob_would_be_detected(self):
        mutated = read(BASE).replace("  page_size: 1",
                                     "  page_size: 1\n  temperature: 1.0")
        t = strip_comments(mutated)
        self.assertIn("temperature", knobs(t))
        self.assertNotIn("temperature", placeholders(t))

    def test_draft_model_path_would_be_detected(self):
        mutated = command(strip_comments(read(UNO))) + " --speculative-draft-model-path x"
        self.assertIn("--speculative-draft-model-path", mutated)

    def test_the_arithmetic_itself(self):
        """If this fails, the memory guard is comparing against wrong constants."""
        self.assertEqual(KV_BYTES_PER_TOKEN, 147_456)
        self.assertEqual(KV_BYTES_PER_TOKEN * 524_288 / 1024 ** 3, 72.0)

    def test_typo_in_a_mod_reference_would_be_detected(self):
        """The corollary, because `sparkrun recipe validate` cannot tell us.

        Proven necessary: validating a copy with `probe-uno-fa4-sm121` corrupted to
        `probe-uno-fa4-TYPO` exits 0. Only this guard notices.
        """
        mutated = read(UNO).replace("probe-uno-fa4-sm121", "probe-uno-fa4-TYPO")
        body = _block(strip_comments(mutated), "mods")
        names = [e.split("/")[-1]
                 for e in re.findall(r"-\s*[\"']?(@?[\w./-]+)[\"']?", body)]
        self.assertIn("probe-uno-fa4-TYPO", names)
        self.assertFalse((REPO_ROOT / "mods" / "probe-uno-fa4-TYPO" / "run.sh")
                         .exists())

    def test_lowered_uno_cap_would_be_detected(self):
        mutated = read(UNO).replace("max_num_seqs: 32", "max_num_seqs: 8")
        self.assertLess(
            int(knobs(strip_comments(mutated))["max_num_seqs"]), 16,
            "control: the replaced 8 must read back below the floor")


if __name__ == "__main__":
    unittest.main()
