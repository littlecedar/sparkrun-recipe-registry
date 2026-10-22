"""Guard for the humanizer §7(c) acceptance instruments (tools/humanizer-*.py).

Run:
    python3 -m unittest discover -s tests -v

Stdlib-only, like the rest of tests/ and tools/ (AGENTS.md).  Both tools are
dash-named, so they are imported via importlib and registered in sys.modules
before exec_module (the house import idiom).

What this guards
----------------
`tools/humanizer-measure.py` + `tools/humanizer-analyze.py` are the reproduced
quality instrument of the archived bf16 arm (receipt
`~/benchmarks/humanizer-20261014/`, 2026-10-14): 20 fixed drafts x 2 samples
through `/v1/completions` with a byte-exact prompt whose sha256 prefix is
asserted (`cc51d66b4c593fbe`), scored by a lexical numbers/dates/names
instrument.  The 2026-10-22 quant round compares against that baseline (0 fact
losses / 40 rewrites), so a drifted prompt format or a broken lexer would
invalidate the whole comparison.

Failure modes this guard exists for:

  * the prompt format (instr / sep) drifts, silently changing every rewrite's
    input — fingerprint assert catches it at measurement time, and the guard
    pins the fingerprint up front;
  * the draft set shrinks or duplicates a genre — the arm is scored on 20
    drafts, and a shorter set is a smaller sample, not a different result;
  * the lexer stops seeing a number, date or heading (over-lenient: every
    rewrite looks fact-clean).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
import tempfile
import unittest
import io
import contextlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MEASURE = REPO_ROOT / "tools" / "humanizer-measure.py"
ANALYZE = REPO_ROOT / "tools" / "humanizer-analyze.py"

FINGERPRINT = "cc51d66b4c593fbe"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # before exec: module-level objects resolve
    spec.loader.exec_module(module)
    return module


class PromptIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.measure = _load("humanizer_measure_guard", MEASURE)

    def test_prompt_fingerprint_is_pinned(self):
        prompt = self.measure.build_prompt(self.measure.PROMPT_FORMAT, "X")
        self.assertEqual(
            hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
            FINGERPRINT,
            "the byte-exact prompt format drifted — every rewrite input changed",
        )

    def test_fingerprint_negative_control(self):
        # A mutated instr must change the fingerprint: the pin is real.
        pf = dict(self.measure.PROMPT_FORMAT)
        pf["instr"] = pf["instr"].replace("Vary sentence length", "Vary length")
        prompt = self.measure.build_prompt(pf, "X")
        self.assertNotEqual(
            hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
            FINGERPRINT,
        )

    def test_draft_set_is_20_unique_genres(self):
        self.assertEqual(len(self.measure.DRAFTS), 20)
        self.assertEqual(len({g for g, _ in self.measure.DRAFTS}), 20)

    def test_lexer_is_not_over_lenient(self):
        # Draft 3 (report) has known dense facts and structure; a number
        # dropped from the rewrite must be seen as missing.
        report = self.measure.DRAFTS[2][1]
        nums, _dates, _names = self.measure.fact_tokens(report)
        self.assertIn("99.94", nums)
        self.assertIn("214000", nums)
        self.assertEqual(self.measure.fmt_counts(report), (9, 2, 5))
        stripped = self.measure.numbers(report.replace("99.94", "X.XX"))
        self.assertNotIn("99.94", stripped)


class Analyzer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analyze = _load("humanizer_analyze_guard", ANALYZE)

    def _run(self, rows):
        with tempfile.NamedTemporaryFile(
                "w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({"rewrites": rows}, f, ensure_ascii=False)
            path = f.name
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.analyze.main(path)
            return buf.getvalue()
        finally:
            Path(path).unlink()

    def test_number_drop_is_flagged(self):
        measure = _load("humanizer_measure_guard_reuse", MEASURE)
        report = measure.DRAFTS[2][1]
        out = self._run([
            {"n": 3, "genre": "report", "sample": 1,
             "output": report.replace("99.94", "X.XX")},
        ])
        self.assertIn("== number: 1 flags", out)
        self.assertIn("99.94", out)
        self.assertIn("TOTAL flags: 1", out)

    def test_marker_drop_is_not_a_fact_flag(self):
        measure = _load("humanizer_measure_guard_reuse2", MEASURE)
        report = measure.DRAFTS[2][1]
        marker_only = re.sub(r"^#+ ", "", report, flags=re.M)
        out = self._run([
            {"n": 3, "genre": "report", "sample": 1, "output": marker_only},
        ])
        self.assertIn("== number: 0 flags", out)
        self.assertNotIn("99.94", out)



RECIPE = (Path(__file__).resolve().parent.parent / "recipes" / "explore"
          / "humanizer-12b-q6k-llamacpp.yaml")


def _recipe_text(text=None):
    text = RECIPE.read_text(encoding="utf-8") if text is None else text
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


class Recipe(unittest.TestCase):
    """The shipped tier's load-bearing literals — each is silent until a boot.

    Q6_K is the only tier that passed the bar above, so a silent drift back to
    Q4_K_M (or to a floating container tag) would re-ship the measured-rejected
    weights while the lane README still cites the Q6_K cells.
    """

    def test_pins_the_q6k_file_and_revision(self):
        text = _recipe_text()
        self.assertIn("model: jialinyyzz/humanizer-GGUF:humanizer-12b-Q6_K.gguf", text)
        self.assertIn("model_revision: d9c6be435fe29e6e96dc42f4c3cc185e06ae3eac", text)

    def test_container_is_tag_and_digest(self):
        self.assertIn(
            "scitrera/dgx-spark-llama-cpp:b10549-cu131"
            "@sha256:ad14055470c2bd5c2b4c088dc5727d950da00f62408f438f4f3833c704af0dca",
            _recipe_text())

    def test_alias_is_the_served_name_not_the_model_placeholder(self):
        text = _recipe_text()
        self.assertIn("--alias {served_model_name}", text)
        self.assertNotIn("--alias {model}", text)

    def test_kv_unified_and_window(self):
        text = _recipe_text()
        self.assertIn("--kv-unified", text)
        self.assertIn("ctx_size: 8192", text)
        self.assertIn("parallel: 2", text)

    def test_commented_pins_do_not_satisfy_the_guards(self):
        # Prose quoting a pin must not pass: a re-pin that landed in a comment
        # would otherwise read as still pinned.
        self.assertEqual(_recipe_text("model: x\n# model_revision: y\n"), "model: x")



if __name__ == "__main__":
    unittest.main()