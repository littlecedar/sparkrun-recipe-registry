"""Guards for the Qwen3-VL embedding/reranking recipes and their chat template.

Run:
    uv run python -m unittest discover -s tests -v

Why these tests exist (see recipes/qwen3/QWEN3-EMBED-OPTIMIZATION-WORK.md §2 F7-F8b):
the Qwen3-VL reranker can be served in a configuration that returns HTTP 200 and
plausible-looking scores while computing them the wrong way. Nothing about such a
launch is loud, so the checks that matter are the ones we can run without hardware:
does the template we ship actually read the roles vLLM's score endpoint synthesizes,
and does it survive multimodal content without leaking a Python repr.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import jinja2

REPO_ROOT = Path(__file__).resolve().parent.parent
MOD_SCRIPT = REPO_ROOT / "mods" / "provide-qwen3-vl-rerank-template" / "run.sh"
RECIPE_DIR = REPO_ROOT / "recipes" / "qwen3"

EMBED_2B = RECIPE_DIR / "qwen3-vl-embedding-2b-vllm-b12x.yaml"
EMBED_8B = RECIPE_DIR / "qwen3-vl-embedding-8b-awq-4bit-vllm-b12x.yaml"
RERANK_2B = RECIPE_DIR / "qwen3-vl-reranker-2b-vllm-b12x.yaml"
RECIPES = [EMBED_2B, EMBED_8B, RERANK_2B]

# Assembled rather than written as one literal, so a redacting tool in the pipeline
# cannot silently rewrite it and so a reader can check it character by character.
IMG_START = "<" + "|im_" + "start|" + ">"
IMG_END = "<" + "|im_" + "end|" + ">"
IMAGE_PAD = "<" + "|image_" + "pad|" + ">"
VISION_START = "<" + "|vision_" + "start|" + ">"


def bundled_template() -> str:
    """Extract the heredoc'd template from the mod, with markers normalized.

    The mod writes the template through a quoted heredoc, so what is in the file is
    exactly what lands on disk in the container — that is the artifact under test.
    """
    text = MOD_SCRIPT.read_text()
    start = text.index("<<'TPL'\n") + len("<<'TPL'\n")
    end = text.index("\nTPL\n", start)
    return text[start:end]


def render(**kwargs) -> str:
    return jinja2.Environment().from_string(bundled_template()).render(**kwargs)


def active_lines(text: str) -> list[str]:
    """Whole-line comments stripped; inline `#` inside a scalar left alone.

    These recipes document their own omissions ("--async-scheduling is deliberately NOT
    set"), so a guard that greps the raw file would fail on the explanation rather than on
    the defect. Comments-only lines are the ones that carry prose.
    """
    return [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]


def instruction_of(rendered: str) -> str:
    return rendered.split("<Instruct>: ")[1].split("<Query>:")[0]


class TestRerankChatTemplate(unittest.TestCase):
    """The template must read query/document roles and survive multimodal content."""

    def test_reads_synthesized_roles(self):
        tpl = bundled_template()
        self.assertIn('role == "query"', tpl)
        self.assertIn('role == "document"', tpl)

    def test_string_content_renders_both_anchors(self):
        out = render(
            messages=[
                {"role": "query", "content": "what is a cat?"},
                {"role": "document", "content": "a cat is a small carnivorous mammal."},
            ],
            add_generation_prompt=True,
        )
        self.assertIn("<Query>:", out)
        self.assertIn("<Document>:", out)
        self.assertIn("what is a cat?", out)
        self.assertIn("a cat is a small carnivorous mammal.", out)
        self.assertTrue(out.startswith(IMG_START + "system"))
        self.assertTrue(out.endswith(IMG_START + "assistant\n"))

    def test_multimodal_content_emits_placeholder_not_python_repr(self):
        """Regression: vLLM's own example template renders a Python repr here.

        examples/pooling/score/template/qwen3_vl_reranker.jinja uses
        `map(attribute="content") | first`, so a list-valued content (what the score
        endpoint builds for an image document) stringifies into the prompt. A
        vision-language reranker must never see that.
        """
        out = render(
            messages=[
                {"role": "query", "content": [{"type": "text", "text": "a woman with her dog"}]},
                {
                    "role": "document",
                    "content": [
                        {"type": "text", "text": "a woman and a dog"},
                        {"type": "image_url", "image_url": {"url": "http://example.invalid/x.jpg"}},
                    ],
                },
            ],
            add_generation_prompt=True,
        )
        self.assertIn(IMAGE_PAD, out, "no image placeholder: the document cannot be seen")
        self.assertIn(VISION_START, out)
        self.assertIn("a woman and a dog", out)
        # The failure mode is a dict repr reaching the prompt.
        for leak in ("{'type'", "image_url", "example.invalid"):
            self.assertNotIn(leak, out, f"python repr/URL leaked into the prompt: {leak}")

    def test_instruction_precedence(self):
        msgs = [
            {"role": "system", "content": "system task."},
            {"role": "query", "content": "q"},
            {"role": "document", "content": "d"},
        ]
        self.assertEqual(instruction_of(render(messages=msgs, add_generation_prompt=True)), "system task.")
        self.assertEqual(instruction_of(render(messages=msgs, add_generation_prompt=True, instruction="a.")), "a.")
        self.assertEqual(instruction_of(render(messages=msgs, add_generation_prompt=True, instruct="b.")), "b.")
        # explicit instruction beats a system message
        self.assertEqual(instruction_of(render(messages=msgs, add_generation_prompt=True, instruction="c.")), "c.")
        no_sys = [{"role": "query", "content": "q"}, {"role": "document", "content": "d"}]
        self.assertIn("Given a search query", instruction_of(render(messages=no_sys, add_generation_prompt=True)))

    def test_mod_guard_rejects_a_role_blind_template(self):
        """The mod must refuse to publish a template that cannot read the roles."""
        text = MOD_SCRIPT.read_text()
        self.assertIn("FATAL", text)
        # The guard is a regex over the rendered file, not a filename check.
        self.assertIn("query_role_re=", text)
        role_blind = IMG_START + "user\n" + "{{ messages | first }}\n"
        pattern = re.search(r"query_role_re='([^']+)'", text)
        self.assertIsNotNone(pattern, "guard regex not found in mod")
        self.assertIsNone(
            re.search(pattern.group(1), role_blind),
            "role-blind template must not satisfy the guard",
        )
        self.assertIsNotNone(re.search(pattern.group(1), bundled_template()))


class TestModRuntimeRoot(unittest.TestCase):
    """The mod and the recipe must agree on where the template lands.

    The recipe names its path as ${XDG_CACHE_HOME:-/cache/runtime}/... and a mod cannot
    export variables into the serve command, so a MOD_CACHEDIR that points elsewhere would
    make the mod publish a template nobody reads — vLLM then silently falls back to the
    checkpoint's query/document-blind template, the exact failure the mod exists to prevent.
    So the mod must refuse that configuration. Executed for real rather than grepped.
    """

    def _run_mod(self, env_extra: dict[str, str], root: Path) -> subprocess.CompletedProcess:
        workdir = root / "mod"
        workdir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MOD_SCRIPT, workdir / "run.sh")
        env = dict(os.environ)
        env.pop("MOD_CACHEDIR", None)
        env.pop("XDG_CACHE_HOME", None)
        env.update(env_extra)
        return subprocess.run(
            ["bash", str(workdir / "run.sh")],
            capture_output=True, text=True, timeout=120, env=env, cwd=str(workdir),
        )

    def test_default_root_writes_template(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "cache"
            cache.mkdir()
            r = self._run_mod({"XDG_CACHE_HOME": str(cache)}, root)
            self.assertEqual(r.returncode, 0, (r.stdout, r.stderr))
            self.assertTrue((cache / "templates" / "qwen3-vl-reranker-query-document.jinja").exists())

    def test_drift_between_mod_cachedir_and_recipe_root_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a, b = root / "a", root / "b"
            a.mkdir(); b.mkdir()
            r = self._run_mod({"MOD_CACHEDIR": str(a), "XDG_CACHE_HOME": str(b)}, root)
            self.assertEqual(r.returncode, 1, "silent drift would boot a wrong-prompt reranker")
            self.assertIn("differs from XDG_CACHE_HOME", r.stderr)
            self.assertFalse((b / "templates").exists())

    def test_agreeing_roots_are_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            same = root / "cache"
            same.mkdir()
            r = self._run_mod({"MOD_CACHEDIR": str(same), "XDG_CACHE_HOME": str(same)}, root)
            self.assertEqual(r.returncode, 0, (r.stdout, r.stderr))


def load_bench():
    """Import tools/pooling-bench.py (a dash-named file, so via importlib).

    Registered in sys.modules before exec: the module uses @dataclass, whose metaclass
    resolves annotations through sys.modules[cls.__module__] and raises AttributeError on
    a module that was never registered.
    """
    import importlib.util

    path = REPO_ROOT / "tools" / "pooling-bench.py"
    spec = importlib.util.spec_from_file_location("pooling_bench", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["pooling_bench"] = module
    spec.loader.exec_module(module)
    return module


class TestPoolingBenchParsers(unittest.TestCase):
    """The score parser must accept both legal vLLM shapes and reject a third.

    VERIFIED against vllm/entrypoints/pooling/scoring/protocol.py: /v1/score answers
    ScoreResponse {"data": [{"index","score"}]} while /v1/rerank answers RerankResponse
    {"results": [{"index","relevance_score"}]}. A parser that only knows one of them
    reports a healthy server as broken, which is the failure this guards.
    """

    @classmethod
    def setUpClass(cls):
        cls.pb = load_bench()

    def test_score_endpoint_shape(self):
        obj = {"data": [{"index": 1, "score": 0.2}, {"index": 0, "score": 0.9}], "usage": {}}
        scores, _ = self.pb.parse_scores(obj, "/v1/score")
        self.assertEqual(scores, [0.9, 0.2])  # re-sorted into request order

    def test_rerank_endpoint_shape(self):
        obj = {
            "id": "r", "model": "m", "usage": {"prompt_tokens": 4, "total_tokens": 4},
            "results": [
                {"index": 0, "document": {"text": "a"}, "relevance_score": 0.75},
                {"index": 1, "document": {"text": "b"}, "relevance_score": 0.11},
            ],
        }
        scores, tokens = self.pb.parse_scores(obj, "/v1/rerank")
        self.assertEqual(scores, [0.75, 0.11])
        self.assertEqual(tokens, 4)

    def test_missing_both_shapes_is_an_error_not_an_empty_list(self):
        with self.assertRaises(ValueError):
            self.pb.parse_scores({"foo": []}, "/v1/score")
        # An empty list is NOT a score list; silently returning [] would make every
        # downstream check vacuously pass.
        with self.assertRaises(ValueError):
            self.pb.parse_scores({"data": []}, "/v1/score")


class TestSymmetryCheck(unittest.TestCase):
    """check_symmetry is the only guard that catches F7 without ground truth.

    A bi-encoder's score is a dot product of independently-encoded vectors, so
    score(A,B) == score(B,A) exactly; a cross-encoder reads an ordered prompt and cannot
    be symmetric. Both directions are asserted here, and the mock in §2 F14 of the work
    doc shows the symmetric case passing every other check -- so a vacuous version of
    this guard would hide the real bug.
    """

    @classmethod
    def setUpClass(cls):
        cls.pb = load_bench()

    def test_symmetric_scores_fail(self):
        check = self.pb.check_symmetry([(0.9, 0.9), (0.4, 0.4)], 1e-4)
        self.assertFalse(check.ok)
        self.assertTrue(check.fatal)
        self.assertIn("bi-encoder", check.detail)

    def test_asymmetric_scores_pass(self):
        check = self.pb.check_symmetry([(0.9, 0.31), (0.42, 0.77)], 1e-4)
        self.assertTrue(check.ok)
        self.assertIn("asymmetric", check.detail)

    def test_empty_probe_fails_rather_than_passing(self):
        """No completed probes must never read as 'the reranker is fine'."""
        check = self.pb.check_symmetry([], 1e-4)
        self.assertFalse(check.ok)
        self.assertTrue(check.fatal)

    def test_float_noise_does_not_count_as_asymmetry(self):
        check = self.pb.check_symmetry([(0.5, 0.5 + 1e-9)], 1e-4)
        self.assertFalse(check.ok, "float noise must not be read as a cross-encoder")


class TestRecipeInvariants(unittest.TestCase):
    """Static properties of the three recipes that a boot would otherwise discover."""

    def _text(self, path: Path) -> str:
        self.assertTrue(path.exists(), path)
        return path.read_text()

    def test_async_scheduling_is_not_requested(self):
        """vLLM disables async scheduling for pooling runners; requesting it is a no-op or a hard failure.

        Checked on the *executable* lines only — the recipes deliberately carry comments
        explaining why the flag is absent, and those comments must not trip this guard.
        """
        for p in RECIPES:
            active = active_lines(self._text(p))
            joined = "\n".join(active)
            self.assertNotIn("async_scheduling", joined, p)
            self.assertNotIn("--async-scheduling", joined, p)

    def test_attention_backend_is_a_real_enum_member(self):
        """--attention-backend resolves via AttentionBackendEnum[value.upper()]."""
        valid = {"B12X", "FLASHINFER", "TRITON_ATTN", "FLASH_ATTN", "TORCH_SDPA"}
        for p in RECIPES:
            for m in re.finditer(r"^  attention_backend: (\S+)", self._text(p), re.M):
                self.assertIn(m.group(1).upper(), valid, (p, m.group(1)))

    def test_readiness_inference_probe_disabled(self):
        """A pooling engine has no chat endpoint; the default probe would fail a healthy server."""
        for p in RECIPES:
            self.assertRegex(self._text(p), r"(?m)^readiness:\s*\n\s+inference:\s*false", p)

    def test_cpu_masks_are_disjoint_and_fast_only(self):
        """Colocated engines must not share cores and must not land on the A725 cluster.

        GB10: X925 (3.9 GHz) = 5-9 and 15-19; A725 (2.8 GHz) = 0-4 and 10-14.
        """
        fast = set(range(5, 10)) | set(range(15, 20))

        def parse(mask: str) -> set[int]:
            cpus: set[int] = set()
            for part in mask.split(","):
                if "-" in part:
                    a, b = part.split("-")
                    cpus |= set(range(int(a), int(b) + 1))
                else:
                    cpus.add(int(part))
            return cpus

        masks = {}
        for p in (EMBED_2B, RERANK_2B):
            m = re.search(r"^  cpu_mask: (\S+)$", self._text(p), re.M)
            self.assertIsNotNone(m, p)
            masks[p.name] = parse(m.group(1))
        self.assertFalse(masks[EMBED_2B.name] & masks[RERANK_2B.name], "engines share cores")
        for name, cpus in masks.items():
            self.assertTrue(cpus <= fast, (name, sorted(cpus)))

    def test_hf_overrides_arch_is_a_single_token(self):
        """Structural check on the value that selects both the model class and the pooler hook."""
        text = self._text(RERANK_2B)
        m = re.search(r'"architectures":\s*\["([A-Za-z0-9_]+)"\]', text)
        self.assertIsNotNone(m, "architectures rewrite not found")
        arch = m.group(1)
        self.assertTrue(arch.startswith("Qwen3VLFor"), arch)
        self.assertTrue(arch.endswith("ForSequenceClassification"), arch)
        self.assertNotIn(" ", arch)

    @staticmethod
    def _rendered_scalar(text: str, key: str):
        """Recover the string a `defaults:` scalar renders to, for the JSON-bearing keys.

        Supports the two forms these recipes use and refuses anything else, which is the
        point: guessing here would make the guard below vacuous. Stdlib-only, because the
        repo declares jinja2 + netifaces and the offline cache has no PyYAML.

        `key: >-` folded, value on following lines  ->  YAML keeps whatever shell quotes are
        written *inside* the value, so `'{"a": 1}'` survives to the command line intact.
        `key: "..."` double-quoted on one line      ->  YAML unquotes once.
        """
        lines = text.splitlines()
        inline = re.compile(r"^(\s+)%s:\s*(\S.*)$" % re.escape(key))
        folded = re.compile(r"^(\s+)%s:\s*(?:>|>-)(\s*)$" % re.escape(key))
        for i, line in enumerate(lines):
            m = folded.match(line)
            if m:
                indent = len(m.group(1))
                body = []
                for nxt in lines[i + 1:]:
                    if not nxt.strip():
                        continue
                    if len(nxt) - len(nxt.lstrip()) <= indent:
                        break
                    body.append(nxt.strip())
                return " ".join(body)  # folded style joins continuation lines with a space
            m = inline.match(line)
            if m:
                raw = m.group(2).strip()
                if raw.startswith('"') and raw.endswith('"') and len(raw) > 1:
                    return raw[1:-1].replace('\\"', '"').replace("\\\\", "\\")
                raise AssertionError(
                    "cannot interpret inline form for %r: %r — use folded style (>-) with "
                    "embedded shell quotes, or extend this helper" % (key, raw)
                )
        return None

    def test_json_defaults_survive_as_one_shell_word(self):
        """YAML quoting is load-bearing: an unquoted JSON value word-splits at runtime.

        Checking the *style marker* is not enough. `key: >-` is the right style, but a
        folded value with no shell quotes inside it still word-splits once substituted into
        the command, and a guard that only inspects `>-` blesses it. So reconstruct the
        rendered value and lex it with shlex — the thing that actually decides
        word-splitting — then require the single resulting token to be the JSON we meant.

        Negative controls, each run deliberately and each caught: folded value with the
        embedded quotes removed -> "word-splits into 4 shell words"; folded ->
        single-quoted -> refused by the helper as an uninterpretable inline form.
        """
        import json
        import shlex

        for p in RECIPES:
            text = "\n".join(active_lines(self._text(p)))
            for key in ("limit_mm_per_prompt", "hf_overrides"):
                value = self._rendered_scalar(text, key)
                if value is None:
                    continue
                try:
                    tokens = shlex.split(value)
                except ValueError as exc:  # unbalanced quote
                    self.fail("%s in %s does not even lex: %s (%r)" % (key, p, exc, value))
                self.assertEqual(
                    len(tokens), 1,
                    "%s in %s word-splits into %d shell words: %r" % (key, p, len(tokens), value),
                )
                try:
                    json.loads(tokens[0])
                except json.JSONDecodeError as exc:
                    self.fail("%s in %s is not valid JSON after one round of unquoting: "
                              "%s (%r)" % (key, p, exc, tokens[0]))


@unittest.skipUnless(shutil.which("sparkrun"), "sparkrun not on PATH")
class TestSparkrunValidation(unittest.TestCase):
    """`sparkrun recipe validate` under an isolated HOME.

    Deliberately hermetic: the operator's real ~/.config/sparkrun may be unreadable or
    carry unrelated state, and a recipe test that fails because of that is noise. Registry
    resolution is not exercised here (mods resolve at launch, not at validate).
    """

    def test_recipes_validate(self):
        env = dict(os.environ)
        with tempfile.TemporaryDirectory(prefix="sparkrun-home-") as home:
            env["HOME"] = home
            for p in RECIPES:
                r = subprocess.run(
                    ["sparkrun", "recipe", "validate", str(p)],
                    capture_output=True,
                    text=True,
                    timeout=180,
                    env=env,
                    cwd=str(REPO_ROOT),
                )
                self.assertEqual(r.returncode, 0, (p, r.stdout, r.stderr))
                self.assertNotIn("error", r.stdout.lower(), (p, r.stdout))


if __name__ == "__main__":
    unittest.main()
