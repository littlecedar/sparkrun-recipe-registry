"""Guards for the diarization instruments (tools/diarize-score.py, tools/diarize-fixture.py).

Run:
    uv run python -B -m unittest tests.test_diarize_score -v

Stdlib-only, like the rest of tests/ and tools/ (AGENTS.md: "tools/ and tests/ are
stdlib-only, on purpose").  Both tools are dash-named, so they are imported via
importlib and registered in sys.modules before exec_module (the house idiom).

What this guards
----------------
`recipes/media/zz-pyannote-community-1-diarization-cpu.yaml` is scored by DER,
and DER is the kind of number that is easy to compute wrongly in a direction that
flatters the arm.  Every claim the scorer's docstring makes has a control here,
because a guard that has only ever passed proves nothing:

  * a perfect hypothesis scores exactly 0 (not "small");
  * a *relabelled* perfect hypothesis also scores 0 -- the permutation mapping is
    what makes speaker ids comparable at all, and the mapping it chose is asserted;
  * the collar is applied at both reference boundaries and on both sides, shown by
    the same pair scoring 0.6 with no collar and 0.1 with a 0.25 s collar;
  * missed speech, false alarm and speaker error land in their own components
    (a false-alarm-only hypothesis is DER 2.0, not 0 and not 1);
  * an empty *file* is an error while an empty *in-memory* hypothesis is DER 1.0 --
    the two claims differ, and parsing must not turn one into the other;
  * the fixtures are byte-deterministic (regenerated, not remembered), and the
    fixture builder's `--check` goes red on a tampered WAV.

DER>10% is the arm's pre-registered falsifier; this file guards the scorer that
decides it, not the model.
"""

from __future__ import annotations

import importlib.util
import json
import statistics
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCORE_PATH = REPO_ROOT / "tools" / "diarize-score.py"
FIXTURE_PATH = REPO_ROOT / "tools" / "diarize-fixture.py"


def load_tool(name, path):
    """Import a dash-named tool (importlib; register before exec_module)."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # before exec: @dataclass / __module__
    spec.loader.exec_module(module)
    return module


DS = load_tool("diarize_score", SCORE_PATH)
DF = load_tool("diarize_fixture", FIXTURE_PATH)

RTTM = "SPEAKER meet 1 {start:.3f} {dur:.3f} <NA> <NA> {label} <NA> <NA>\n"


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, name, text):
        path = self.dir / name
        path.write_text(text)
        return path


class TestParsing(TempDirCase):
    def test_rttm_and_plain_formats_agree(self):
        rttm = self.write("a.rttm", RTTM.format(start=1.0, dur=2.0, label="A"))
        plain = self.write("a.txt", "1.0 3.0 A\n")
        self.assertEqual(DS.load_segments(rttm), [(1.0, 3.0, "A")])
        self.assertEqual(DS.load_segments(plain), [(1.0, 3.0, "A")])

    def test_json_receipt_shapes(self):
        rows = [{"start": 0.0, "end": 1.5, "speaker": "SPEAKER_00"}]
        for name, payload in [
            ("bare.json", json.dumps(rows)),
            ("list.json", json.dumps({"segments": rows})),
            ("receipt.json", json.dumps({"model": "pyannote", "segments": rows})),
            ("label.json", json.dumps({"segments": [{"start": 0, "end": 1.5, "label": "S0"}]})),
        ]:
            loaded = DS.load_segments(self.write(name, payload))
            self.assertEqual(loaded[0][:2], (0.0, 1.5), name)
            self.assertIsInstance(loaded[0][2], str, name)

    def test_empty_file_is_an_error_not_an_empty_segmentation(self):
        for name, text in [("empty.txt", ""), ("blank.rttm", "   \n\n"), ("empty.json", "[]"),
                           ("noseg.json", '{"segments": []}')]:
            with self.assertRaises(ValueError, msg=name):
                DS.load_segments(self.write(name, text))

    def test_malformed_lines_raise(self):
        for name, text in [
            ("short.txt", "0.0 1.0\n"),
            ("extra.txt", "0.0 1.0 A B\n"),
            ("rttm9.rttm", "SPEAKER f 1 0.0 1.0 <NA> <NA> A <NA>\n"),
            ("backwards.txt", "3.0 1.0 A\n"),
            ("nan.txt", "0.0 nan A\n"),
            ("badjson.json", '{"segments": [{"start": "x", "end": 1, "speaker": "A"}]}'),
        ]:
            with self.assertRaises(ValueError, msg=name):
                DS.load_segments(self.write(name, text))

    def test_multi_file_rttm_refuses_to_pool(self):
        text = RTTM.format(start=0.0, dur=1.0, label="A") + RTTM.format(start=0.0, dur=1.0, label="B")
        text = text.replace("meet", "one", 1)  # two distinct file ids
        with self.assertRaises(ValueError):
            DS.load_segments(self.write("two.rttm", text))


class TestPerfectAndMapping(unittest.TestCase):
    REF = [(0.0, 2.0, "A"), (3.0, 5.0, "B"), (6.0, 8.0, "A")]

    def test_perfect_hypothesis_is_exactly_zero(self):
        result = DS.score_pair(self.REF, list(self.REF))
        self.assertEqual(result["der"], 0.0)
        self.assertEqual(result["jer"], 0.0)
        for component in ("missed", "false_alarm", "speaker_error"):
            self.assertEqual(result[component], 0.0, component)
        self.assertEqual(result["mapping"], {"A": "A", "B": "B"})

    def test_relabelled_hypothesis_is_also_zero(self):
        swapped = [(start, end, {"A": "SPEAKER_01", "B": "SPEAKER_00"}[label])
                   for start, end, label in self.REF]
        result = DS.score_pair(swapped, self.REF)
        # reversed roles on purpose: the mapping is keyed by reference label here
        self.assertEqual(result["der"], 0.0, result)
        self.assertEqual(
            DS.score_pair(self.REF, swapped)["mapping"],
            {"SPEAKER_00": "B", "SPEAKER_01": "A"},
        )
        self.assertEqual(DS.score_pair(self.REF, swapped)["der"], 0.0)


class TestCollar(unittest.TestCase):
    REF = [(1.0, 2.0, "A")]
    HYP = [(1.3, 2.3, "A")]  # 0.3 s late start, 0.3 s late end

    def test_no_collar_counts_both_errors(self):
        # 0.3 missed + 0.3 false alarm over 1.0 s of reference speech
        self.assertAlmostEqual(DS.score_pair(self.REF, self.HYP, collar=0.0)["der"], 0.6, places=9)

    def test_collar_removes_both_boundary_bands(self):
        result = DS.score_pair(self.REF, self.HYP, collar=0.25)
        # scored reference is [1.25, 1.75]; the hypothesis covers [1.3, 1.75] of it
        self.assertAlmostEqual(result["reference_speech"], 0.5, places=9)
        self.assertAlmostEqual(result["correct"], 0.45, places=9)
        self.assertAlmostEqual(result["missed"], 0.05, places=9)
        # the collar does not excuse speech past the band: the trailing 0.05 s of
        # the hypothesis [2.25, 2.3] is still a false alarm
        self.assertAlmostEqual(result["false_alarm"], 0.05, places=9)
        self.assertAlmostEqual(result["der"], 0.2, places=9)

    def test_collar_wider_than_the_segment_unscorable(self):
        # a 0.4 s reference segment with a 0.25 s collar is entirely collar band
        with self.assertRaises(ValueError):
            DS.score_pair([(0.0, 0.4, "A")], [(0.0, 0.4, "A")], collar=0.25)


class TestComponents(unittest.TestCase):
    def test_false_alarm_only(self):
        result = DS.score_pair([(0.0, 1.0, "A")], [(5.0, 6.0, "A")], collar=0.0)
        self.assertAlmostEqual(result["missed"], 1.0, places=9)
        self.assertAlmostEqual(result["false_alarm"], 1.0, places=9)
        self.assertAlmostEqual(result["speaker_error"], 0.0, places=9)
        self.assertAlmostEqual(result["der"], 2.0, places=9)  # DER is not bounded by 1

    def test_empty_hypothesis_scores_one(self):
        result = DS.score_pair([(0.0, 2.0, "A")], [], collar=0.0)
        self.assertAlmostEqual(result["der"], 1.0, places=9)
        self.assertAlmostEqual(result["missed"], 2.0, places=9)
        self.assertEqual(result["mapping"], {})

    def test_speaker_error_not_false_alarm(self):
        # one hypothesis speaker covering both reference speakers: everything is
        # in the right place in time, so only the speaker attribution is wrong
        result = DS.score_pair(
            [(0.0, 1.0, "A"), (2.0, 3.0, "B")],
            [(0.0, 1.0, "X"), (2.0, 3.0, "X")],
            collar=0.0,
        )
        self.assertAlmostEqual(result["correct"], 1.0, places=9)
        self.assertAlmostEqual(result["speaker_error"], 1.0, places=9)
        self.assertAlmostEqual(result["false_alarm"], 0.0, places=9)
        self.assertAlmostEqual(result["missed"], 0.0, places=9)
        self.assertAlmostEqual(result["der"], 0.5, places=9)
        # JER normalises by the larger speaker count: one hypothesis speaker
        # matched against two reference speakers is 1 - (0.5 / 2)
        self.assertAlmostEqual(result["jer"], 0.75, places=9)

    def test_simultaneous_speech_is_counted_per_label(self):
        result = DS.score_pair(
            [(0.0, 1.0, "A"), (0.0, 1.0, "B")],
            [(0.0, 1.0, "X"), (0.0, 1.0, "Y")],
            collar=0.0,
        )
        self.assertAlmostEqual(result["reference_speech"], 2.0, places=9)
        self.assertAlmostEqual(result["correct"], 2.0, places=9)
        self.assertEqual(result["der"], 0.0)

    def test_overlap_exclude_drops_both_labels(self):
        reference = [(0.0, 1.0, "A"), (0.0, 1.0, "B")]
        scored = DS.score_pair(reference, [(0.0, 1.0, "A")], collar=0.0)
        self.assertAlmostEqual(scored["reference_speech"], 2.0, places=9)
        self.assertAlmostEqual(scored["der"], 0.5, places=9)  # B's 1 s is missed
        with self.assertRaises(ValueError):
            # everything is overlap: excluding it leaves nothing to score, so the
            # arm must error rather than report a DER over a zero denominator
            DS.score_pair(reference, [(0.0, 1.0, "A")], collar=0.0, overlap="exclude")

    def test_speaker_cap_refuses_instead_of_guessing(self):
        reference = [(float(i), float(i) + 0.5, f"S{i}") for i in range(9)]
        with self.assertRaises(ValueError):
            DS.score_pair(reference, reference, collar=0.0)

    def test_pooled_is_components_over_reference(self):
        # DER does not average: a 3 s perfect recording and a 1 s total miss pool
        # to 1/4, not to the mean of 0 and 1
        good = DS.score_pair([(0.0, 3.0, "A")], [(0.0, 3.0, "A")], collar=0.0)
        bad = DS.score_pair([(0.0, 1.0, "A")], [], collar=0.0)
        total = DS.pooled([good, bad])
        self.assertAlmostEqual(total["der"], 0.25, places=9)
        self.assertNotAlmostEqual(total["der"], statistics.mean([good["der"], bad["der"]]), places=9)


class TestCli(TempDirCase):
    def test_cli_json_and_fail_above(self):
        ref = self.write("ref.rttm", RTTM.format(start=0.0, dur=2.0, label="A"))
        hyp = self.write("hyp.json", json.dumps({"segments": [{"start": 0.0, "end": 2.0, "speaker": "S0"}]}))
        out = self.dir / "der.json"
        run = subprocess.run(
            [sys.executable, "-B", str(SCORE_PATH), str(ref), str(hyp), "--json", str(out)],
            capture_output=True, text=True,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(out.read_text())["pooled"]["der"], 0.0)
        failed = subprocess.run(
            [sys.executable, "-B", str(SCORE_PATH), str(ref), str(hyp), "--fail-above", "-1"],
            capture_output=True, text=True,
        )
        self.assertEqual(failed.returncode, 1, failed.stderr)

    def test_cli_exits_two_on_empty_input(self):
        ref = self.write("ref.rttm", RTTM.format(start=0.0, dur=2.0, label="A"))
        empty = self.write("empty.json", "[]")
        run = subprocess.run(
            [sys.executable, "-B", str(SCORE_PATH), str(ref), str(empty)], capture_output=True, text=True
        )
        self.assertEqual(run.returncode, 2)
        self.assertIn("no 'segments'", run.stderr)


class TestFixtures(TempDirCase):
    def test_render_is_byte_deterministic(self):
        turns = [(0.0, 0.2, "A"), (0.25, 0.4, "B")]
        self.assertEqual(DF.render(turns, 0.5), DF.render(turns, 0.5))
        self.assertNotEqual(DF.render(turns, 0.5), DF.render([(0.0, 0.4, "C")], 0.5))


    def test_cli_emits_fixtures_that_parse_and_score_zero(self):
        run = subprocess.run(
            [sys.executable, "-B", str(FIXTURE_PATH), "--out", str(self.dir)],
            capture_output=True, text=True,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        manifest = json.loads((self.dir / "manifest.json").read_text())
        self.assertEqual([row["layout"] for row in manifest["layouts"]], sorted(DF.LAYOUTS))
        for row in manifest["layouts"]:
            reference = DS.load_segments(self.dir / f"{row['layout']}.rttm")
            self.assertAlmostEqual(
                sum(end - start for start, end, _ in reference),
                sum(row["speech_seconds"].values()),
                places=6,
            )
            # every fixture turn must survive the default collar
            self.assertEqual(DS.score_pair(reference, reference)["der"], 0.0, row["layout"])

    def test_check_is_green_then_red_on_a_tampered_wav(self):
        entry = DF.emit(self.dir, DF.build_layout("two-speaker"))
        (self.dir / "manifest.json").write_text(
            json.dumps({"sample_rate": DF.SAMPLE_RATE, "layouts": [entry]})
        )
        self.assertEqual(DF.check(self.dir), "")
        wav = self.dir / "two-speaker.wav"
        data = bytearray(wav.read_bytes())
        data[-1] ^= 0xFF
        wav.write_bytes(bytes(data))
        self.assertIn("on disk differs", DF.check(self.dir))

    def test_splice_builds_a_dialogue_that_scores_zero(self):
        a, b = self.dir / "a.wav", self.dir / "b.wav"
        DF.write_wav(a, DF.render([(0.0, 3.0, "A")], 3.0))
        DF.write_wav(b, DF.render([(0.0, 3.0, "B")], 3.0))
        built = DF.build_splice("spliced", a, b, chunk=2.0, gap=0.5, turns_wanted=4)
        self.assertEqual(len(built["meta"]["turns"]), 4)
        self.assertEqual({turn[2] for turn in built["meta"]["turns"]}, {"A", "B"})
        reference = [tuple(turn) for turn in built["meta"]["turns"]]
        self.assertEqual(DS.score_pair(reference, reference)["der"], 0.0)
        with self.assertRaises(ValueError):
            DF.build_splice("short", a, b, chunk=10.0, gap=0.5, turns_wanted=4)


if __name__ == "__main__":
    unittest.main()
