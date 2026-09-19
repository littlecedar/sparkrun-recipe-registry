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

import json
import os
import re
import shutil
import subprocess
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


class TestRecipeInvariants(unittest.TestCase):
    """Static properties of the three recipes that a boot would otherwise discover."""

    def _text(self, path: Path) -> str:
        self.assertTrue(path.exists(), path)
        return path.read_text()

    def _code(self, path: Path) -> str:
        """Recipe text with whole-line comments removed.

        These guards must not read prose. An earlier version regex-scanned the whole
        document including comments, and failed on a recipe that was correct: the comment
        explaining that "--async-scheduling is NOT set" contains the exact string the test
        was told to forbid. A comment that documents a fix must not be able to break the
        test that protects the fix.

        Deliberately stdlib-only. The repo declares jinja2 and netifaces and nothing else,
        so importing PyYAML here would make the suite depend on whatever happens to be
        installed; the checks below are narrow enough that line-oriented filtering is
        sufficient, and each one says which field it is looking at.
        """
        kept = [ln for ln in self._text(path).splitlines() if not ln.lstrip().startswith("#")]
        return "\n".join(kept)

    def test_async_scheduling_is_not_requested(self):
        """vLLM disables async scheduling for pooling runners; requesting it is a no-op or a hard failure."""
        for p in RECIPES:
            code = self._code(p)
            self.assertNotIn("--async-scheduling", code, (p, "command"))
            self.assertIsNone(
                re.search(r"(?m)^\s+async_scheduling\s*:", code),
                (p, "async_scheduling must not be a default"),
            )

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
        """Recover the string a `defaults:` scalar renders to, for the two JSON-bearing keys.

        Supports the two forms these recipes use and nothing else, which is the point: it
        fails loudly on a form it does not understand rather than guessing. Stdlib-only for
        the same reason as ``_code``.

        `key: >-` folded, value on following lines  ->  the YAML parser keeps whatever shell
        quotes are written inside it, so `'{"a": 1}'` survives to the command line intact.
        `key: "..."` double-quoted on one line      ->  YAML unquotes once; we then check
        what the shell would see.

        Returns None if the key is absent.
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
                # folded style joins continuation lines with a single space
                return " ".join(body)
            m = inline.match(line)
            if m:
                raw = m.group(2).strip()
                if raw.startswith('"') and raw.endswith('"') and len(raw) > 1:
                    return raw[1:-1].replace('\\"', '"').replace("\\\\", "\\")
                # Any other inline form (bare, single-quoted, block-literal) is either a
                # word-split hazard or a shape this helper refuses to interpret.
                raise AssertionError(
                    "cannot interpret inline form for %r: %r — use folded style (>-) with "
                    "embedded shell quotes, or fix this helper" % (key, raw)
                )
        return None

    def test_json_defaults_survive_as_one_shell_word(self):
        """YAML quoting is load-bearing: an unquoted JSON value word-splits at runtime.

        A single-quoted YAML scalar eats the quotes, so the shell then sees bare JSON and
        splits it on spaces. Folded style keeps the quotes, so the rendered placeholder is
        ONE shell word. Checked by reconstructing the rendered value and lexing it with
        shlex, which is the thing that actually decides word-splitting — the previous
        version of this test pattern-matched the source for `key: >-` and failed on the
        folded form it existed to bless.
        """
        import shlex

        for p in RECIPES:
            code = self._code(p)
            for key in ("limit_mm_per_prompt", "hf_overrides"):
                value = self._rendered_scalar(code, key)
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
                # And that one word must be the JSON we meant, not something the quoting
                # layer mangled into still-looking-like-JSON.
                try:
                    json.loads(tokens[0])
                except json.JSONDecodeError as exc:
                    self.fail("%s in %s is not valid JSON after one round of unquoting: "
                              "%s (%r)" % (key, p, exc, tokens[0]))


@unittest.skipUnless(shutil.which("sparkrun"), "sparkrun not on PATH")
class TestSparkrunValidation(unittest.TestCase):
    def test_recipes_validate(self):
        env = dict(os.environ)
        env.setdefault("HOME", str(Path.home()))
        for p in RECIPES:
            r = subprocess.run(
                ["sparkrun", "recipe", "validate", str(p)],
                capture_output=True,
                text=True,
                timeout=180,
                env=env,
            )
            self.assertEqual(r.returncode, 0, (p, r.stdout, r.stderr))
            self.assertNotIn("error", r.stdout.lower(), (p, r.stdout))


if __name__ == "__main__":
    unittest.main()
