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

import base64
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
# The 8B reranker is derived from the 2B one (same hf_overrides, same template mod), so it is
# held to the same invariants rather than to a separate standard.
RERANK_8B = RECIPE_DIR / "qwen3-vl-reranker-8b-vllm-b12x.yaml"
RECIPES = [EMBED_2B, EMBED_8B, RERANK_2B, RERANK_8B]

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


class TestSyntheticImageSalting(unittest.TestCase):
    """Per-DOCUMENT image variation, which is the only kind that defeats the KV cache here.

    Regression guard for a measurement that was wrong by 7.2x and looked fine. The first
    --synthetic-images implementation generated one distinct image per REQUEST and put it on
    all 10 documents of that request. Every (query, document) pair is scored as its own
    sequence, so those 10 pairs still shared the same query plus the same ~1240-token image
    placeholder run -- roughly 80% of each sequence -- and the run reported a 82.1%
    prefix-cache hit rate at 44.5 units/s. Varying the image per document took the hit rate
    to 2.3% and the honest throughput to 6.2 units/s.

    Also pins the two related facts that make this the right fix:
      * mutating an image URL does nothing, because vLLM's multimodal cache is keyed on
        CONTENT (450 distinct URLs of one photo still hit the cache, 81.5% -> 81.5%);
      * solid-colour PNGs are a legitimate stand-in, because what the encoder charges for is
        the patch grid, not image entropy.
    """

    @classmethod
    def setUpClass(cls):
        cls.pb = load_bench()
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "synthetic_png", REPO_ROOT / "tools" / "synthetic_png.py")
        cls.png = importlib.util.module_from_spec(spec)
        sys.modules["synthetic_png"] = cls.png
        spec.loader.exec_module(cls.png)

    def test_same_nonce_same_image_different_nonce_different_image(self):
        a = self.pb._synthetic_image_url(64, 64, "nonce-a")
        b = self.pb._synthetic_image_url(64, 64, "nonce-a")
        c = self.pb._synthetic_image_url(64, 64, "nonce-b")
        self.assertEqual(a, b, "a nonce must be reproducible or payloads cannot be re-derived")
        self.assertNotEqual(a, c, "distinct nonces must give distinct bytes, or the cache wins")
        self.assertTrue(a.startswith("data:image/png;base64,"))

    def test_per_document_urls_are_distinct_and_correct_count(self):
        cfg = {"synthetic_images": True, "synthetic_size": (64, 64), "image_url": None}
        urls = self.pb.effective_image_urls(cfg, 10)
        self.assertIsInstance(urls, list)
        self.assertEqual(len(urls), 10)
        self.assertEqual(len(set(urls)), 10, "shared images are the bug this class exists for")

    def test_without_synthetic_flag_single_url_is_returned(self):
        cfg = {"synthetic_images": False, "image_url": "https://example.invalid/x.jpg"}
        self.assertEqual(
            self.pb.effective_image_urls(cfg, 10), "https://example.invalid/x.jpg")
        cfg_none = {"synthetic_images": False, "image_url": None}
        self.assertIsNone(self.pb.effective_image_urls(cfg_none, 10))

    def test_score_request_gives_each_document_its_own_image(self):
        """The exact defect: one image repeated across documents leaves a huge shared prefix."""
        docs = [f"document number {i}" for i in range(4)]
        urls = [self.pb._synthetic_image_url(64, 64, f"n{i}") for i in range(4)]
        _, payload = self.pb.build_score_request("m", "the query", docs, urls)
        got = [
            part["image_url"]["url"]
            for doc in payload["documents"]
            for part in doc["content"] if part["type"] == "image_url"
        ]
        self.assertEqual(len(got), 4)
        self.assertEqual(len(set(got)), 4, "each document must carry its own image")
        texts = [
            part["text"] for doc in payload["documents"]
            for part in doc["content"] if part["type"] == "text"
        ]
        self.assertEqual(texts, docs, "document text must survive the content-part rewrite")

    def test_score_request_rejects_mismatched_image_count(self):
        """A silent zip() truncation here would quietly shrink the batch being measured."""
        with self.assertRaises(ValueError):
            self.pb.build_score_request("m", "q", ["a", "b", "c"], ["u1", "u2"])

    def test_single_image_url_still_applies_to_every_document(self):
        """Back-compat: a scalar URL must still fan out, not drop the image."""
        _, payload = self.pb.build_score_request(
            "m", "q", ["a", "b"], "https://example.invalid/x.jpg")
        urls = [
            part["image_url"]["url"] for doc in payload["documents"]
            for part in doc["content"] if part["type"] == "image_url"
        ]
        self.assertEqual(urls, ["https://example.invalid/x.jpg"] * 2)

    def test_text_only_path_unchanged(self):
        _, payload = self.pb.build_score_request("m", "q", ["a", "b"], None)
        self.assertEqual(payload["documents"], ["a", "b"], "no-image path must stay plain strings")

    def test_png_generator_produces_distinct_bytes_per_colour(self):
        a = self.png.solid_png_b64(32, 32, (255, 0, 0))
        b = self.png.solid_png_b64(32, 32, (0, 255, 0))
        self.assertNotEqual(a, b)
        self.assertEqual(self.png.solid_png_b64(32, 32, (255, 0, 0)), a)

    def test_png_generator_rejects_bad_input(self):
        for bad in ((0, 8, (0, 0, 0)), (8, 0, (0, 0, 0)), (8, 8, (0, 256, 0))):
            with self.assertRaises(ValueError):
                self.png.solid_png_b64(*bad)

    def test_png_walker_detects_corruption(self):
        """Non-vacuity for the walker the generator's own self-check relies on."""
        good = base64.b64decode(self.png.solid_png_b64(16, 16, (9, 9, 9)))
        broken = bytearray(good)
        broken[len(good) // 2] ^= 0x01
        with self.assertRaises(ValueError):
            for _ in self.png.iter_chunks(bytes(broken)):
                pass


class TestPrefixCacheCounterMatching(unittest.TestCase):
    """The /metrics parser must read the LOCAL prefix-cache counters, not the external ones.

    This is a regression guard for a bug that produced a confident wrong answer rather than
    an error, which is the class of defect this suite exists for. vLLM exports both
    `vllm:prefix_cache_hits_total` (the local KV radix cache) and
    `vllm:external_prefix_cache_hits_total` (a KV connector, 0.0 on a single node). A first
    implementation matched with `name.endswith("prefix_cache_hits_total")`, so the external
    zeroes overwrote the local values and the tool reported "0.0% of 0 token-chunks
    cache-served" for a server whose real hit rate was 68% -- exactly the situation the flag
    exists to warn about, silently disarmed. The exposition lines below are copied from a
    live reranker's /metrics.
    """

    @classmethod
    def setUpClass(cls):
        cls.pb = load_bench()

    # Real lines, live server, verbatim except for model-name truncation.
    LIVE = "\n".join([
        "# HELP vll:prefix_cache_hits_total Prefix cache hits",
        'vllm:prefix_cache_hits_total{engine="0",model_name="Qwen/Qwen3-VL-Reranker-2B"} 4.65408e+06',
        'vllm:prefix_cache_queries_total{engine="0",model_name="Qwen/Qwen3-VL-Reranker-2B"} 6.813608e+06',
        'vllm:external_prefix_cache_hits_total{engine="0",model_name="Q"} 0.0',
        'vllm:external_prefix_cache_queries_total{engine="0",model_name="Q"} 0.0',
        'vllm:prefix_cache_hits_created{engine="0",model_name="Q"} 1.7897922401741378e+09',
        'vllm:mm_cache_hits_total{engine="0",model_name="Q"} 0.0',
        'vllm:kv_cache_usage_perc{engine="0",model_name="Q"} 0.0',
    ])

    def _match(self, name: str):
        hits = bool(self.pb._LOCAL_PREFIX_HITS.match(name))
        queries = bool(self.pb._LOCAL_PREFIX_QUERIES.match(name))
        return hits, queries

    def test_local_counters_match(self):
        self.assertEqual(self._match("vllm:prefix_cache_hits_total"), (True, False))
        self.assertEqual(self._match("vllm:prefix_cache_queries_total"), (False, True))

    def test_external_counters_do_not_match(self):
        """The bug: `external_` shares the suffix, so suffix matching reads the wrong one."""
        self.assertEqual(self._match("vllm:external_prefix_cache_hits_total"), (False, False))
        self.assertEqual(self._match("vllm:external_prefix_cache_queries_total"), (False, False))

    def test_created_and_other_caches_do_not_match(self):
        self.assertEqual(self._match("vllm:prefix_cache_hits_created"), (False, False))
        self.assertEqual(self._match("vllm:mm_cache_hits_total"), (False, False))

    def test_other_namespaces_still_match(self):
        """Forks rename the namespace; the matcher must not hard-code `vllm`."""
        self.assertEqual(self._match("myfork:prefix_cache_hits_total"), (True, False))
        self.assertEqual(self._match("prefix_cache_hits_total"), (True, False))

    def test_parsing_live_exposition_yields_local_values(self):
        """End-to-end on real bytes: 4.65e6/6.81e6, not the external zeroes."""
        hits = queries = None
        for line in self.LIVE.splitlines():
            if line.startswith("#"):
                continue
            name = line.split("{", 1)[0].split(" ", 1)[0].strip()
            if self.pb._LOCAL_PREFIX_HITS.match(name):
                hits = self.pb._prom_val(line)
            elif self.pb._LOCAL_PREFIX_QUERIES.match(name):
                queries = self.pb._prom_val(line)
        self.assertEqual(hits, 4.65408e6)
        self.assertEqual(queries, 6.813608e6)
        self.assertGreater(hits, 0.0, "a 0.0 here means the external counter won again")

    def test_prom_val_survives_junk(self):
        self.assertIsNone(self.pb._prom_val("garbage"))
        self.assertIsNone(self.pb._prom_val("vllm:x_total not-a-number"))
        self.assertEqual(self.pb._prom_val("vllm:x_total 1.5e+03"), 1500.0)


class TestSaltDefeatsPrefixReuse(unittest.TestCase):
    """--salt must make payloads non-reproducible, or the A/B gate has no teeth.

    The gate in the work doc's §5 rests on salted traffic; if salt were a no-op (or merely
    reseated the same RNG), prefix caching would keep answering from KV and every mask/cap
    measurement would silently measure KV residency again. Determinism WITHOUT salt is
    asserted too, because the two modes must not be confused: same seed means comparable
    runs only when salt is off.
    """

    @classmethod
    def setUpClass(cls):
        cls.pb = load_bench()

    def test_unsalted_is_reproducible(self):
        a = self.pb.make_texts(1234, 6, 64, salt=False)
        b = self.pb.make_texts(1234, 6, 64, salt=False)
        self.assertEqual(a, b, "unsalted payloads must be reproducible or two runs cannot compare")
        self.assertEqual(len(set(a)), len(a))

    def test_salted_is_unique_within_and_across_runs(self):
        first = self.pb.make_texts(1234, 6, 64, salt=True)
        second = self.pb.make_texts(1234, 6, 64, salt=True)
        self.assertEqual(len(set(first)), len(first))
        self.assertNotEqual(first, second, "same seed + salt must NOT reproduce: that is the reuse we avoid")
        self.assertFalse(set(first) & set(second), "salted corpora must not overlap across runs")

    def test_rerank_jobs_are_salted(self):
        cfg = dict(seed=7, input_tokens=64, docs_per_query=3, model="m",
                   image_url=None, multimodal="off")
        for salt, expect_equal in ((False, True), (True, False)):
            a = [j[1] for j in self.pb.jobs_rerank(dict(cfg, salt=salt), 4)]
            b = [j[1] for j in self.pb.jobs_rerank(dict(cfg, salt=salt), 4)]
            self.assertEqual(a == b, expect_equal, f"salt={salt}")


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
        archs = {}
        for p in (RERANK_2B, RERANK_8B):
            text = self._text(p)
            m = re.search(r'"architectures":\s*\["([A-Za-z0-9_]+)"\]', text)
            self.assertIsNotNone(m, (p, "architectures rewrite not found"))
            arch = m.group(1)
            archs[p.name] = arch
            self.assertTrue(arch.startswith("Qwen3VLFor"), (p, arch))
            self.assertTrue(arch.endswith("ForSequenceClassification"), (p, arch))
            self.assertNotIn(" ", arch, p)
        # The 8B recipe was derived from the 2B one and the class name renders redacted in
        # some editors, so it is asserted against its sibling rather than against a literal:
        # a hand-typed copy that silently shipped the placeholder would fail here, and a
        # legitimate rename of the class would not.
        self.assertEqual(archs[RERANK_2B.name], archs[RERANK_8B.name])

    def test_b12x_block_size_is_legal(self):
        """b12x aborts at cache-config time unless --block-size is 64 or 128.

        This is F17, and it is the guard that should have existed from the start: the
        shipped pair could not boot at all because vLLM's default block size is 16 while
        b12x accepts only 64 or 128 (_B12X_PREFERRED_PAGE_SIZE in b12x.py). A day of reading
        the backend source missed it because the reading was aimed at the enum, not the
        cache config. Pinned here because the failure is loud but late — it costs a full
        container launch to discover.

        Non-vacuity is checked by injecting `block_size: 16`; see EMBED-JOURNAL.md.
        """
        legal = {"64", "128"}
        for p in RECIPES:
            text = self._text(p)
            backend = re.search(r"^  attention_backend: (\S+)$", text, re.M)
            self.assertIsNotNone(backend, p)
            if backend.group(1).upper() != "B12X":
                continue
            bs = re.search(r"^  block_size: (\S+)$", text, re.M)
            self.assertIsNotNone(bs, (p, "b12x without an explicit block_size"))
            self.assertIn(bs.group(1), legal, (p, bs.group(1)))
            # The default must actually reach the command line, not just sit in defaults:.
            self.assertIn("--block-size {block_size}", text, p)

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
