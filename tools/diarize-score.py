#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Diarization error rate (DER) and Jaccard error rate (JER) for diarization receipts.

Why this file exists
--------------------
`recipes/media/zz-pyannote-community-1-diarization-cpu.yaml` is a CPU arm whose
only product is "who spoke when".  Nothing in `tools/` scores that: the standard
suite (`eval-suite.py`) scores text, and a diarizer's output is a set of time
segments.  Without a scorer the arm's boot produces a transcript of boundaries and
a human squints at it, which is not a measurement.

The rules this scorer pins, all of them choices a reader has to be able to check:

* **Permutation mapping.**  A hypothesis labels speakers ``SPEAKER_00``... while
  the reference says ``A``/``B``; the two label spaces are unrelated, so scoring
  raw label equality would report a perfect diarization as 100% speaker error.
  The mapping maximises total overlap and is reported in the output so the caller
  can see which hypothesis label was called which reference speaker.
  Method: **exhaustive search over injections** (each reference speaker takes at
  most one hypothesis speaker and vice versa), capped at ``MAX_SPEAKERS = 8``.
  Diarization has single-digit speaker counts, so the search is exact and 8! is
  cheap; Hungarian would be ~60 lines of extra arithmetic for the same answer.
  Above the cap the tool *refuses* rather than returning a number it cannot
  vouch for.
* **Collar.**  ``--collar`` (default 0.25 s) excludes a band of +/-collar around
  every *reference* segment boundary, on both sides, from the reference and the
  hypothesis alike.  This is the classic NIST collar: the region where a
  boundary disagreement is not meaningful is not scored.  A reference segment
  shorter than ``2*collar`` is therefore not scored at all -- with the default
  collar that means a fixture turn must be longer than 0.5 s.
* **Overlap.**  ``--overlap score`` (default) accounts per active speaker label,
  so two simultaneous reference speakers contribute two units of reference time
  and a hypothesis that emits one of them is half right.  ``--overlap exclude``
  drops every interval with two or more active reference speakers from both the
  numerator and the denominator -- use it when the reference is single-speaker
  by construction and the fixture's overlap turn would otherwise be a trap.
* **Scored region.**  Without ``--uem`` the region is ``[0, max end]`` over
  reference *and* hypothesis, so a hypothesis that invents speech past the
  reference end is counted as false alarm instead of silently clipped away.
  ``--uem START END`` narrows it (the NIST un-partitioned evaluation map).

Three components are always reported separately (missed speech, false alarm,
speaker error) because their sum is a bad diagnostic: a threshold that over-merges
speakers mostly shows up in speaker error, and one that over-segments shows up in
false alarm.

Accounting rule for the three components, per elementary interval: reference
speech with no hypothesis speech is **missed**; hypothesis speech with no
reference speech is **false alarm**; where both are present, the error is the
**worse of the two sides** -- unmatched reference speakers on one side, hypothesis
labels attributed to the wrong (or to no) reference speaker on the other -- and
that is **speaker error**.  Charging both sides instead would make a merged
speaker cost twice what silence costs, which is a scoring artefact, not a
finding: one interval, one unit of error.

Inputs
------
Reference: a 10-field NIST RTTM (``SPEAKER <file> 1 <start> <dur> <NA> <NA>
<spk> <NA> <NA>``) or a plain ``start end speaker`` per line.  ``#`` starts a
comment.  Hypothesis: either of the above, or the JSON the arm's server returns
(``{"segments": [{"start": .., "end": .., "speaker": ..}]}``, a bare list of the
same objects, or the whole receipt JSON with a top-level ``segments``), so a
receipt drops straight in with no conversion step.

An empty file or a malformed line is an error (exit 2), never an empty segment
list: "the diarizer returned nothing" and "the diarizer agreed with an empty
reference" are different claims and only one of them is a pass.

Usage
-----
    uv run python -B tools/diarize-score.py ~/benchmarks/pyannote-*/fixtures/two-speaker.rttm \\
        ~/benchmarks/pyannote-*/receipt-diarize.json --json ~/benchmarks/pyannote-*/der.json

Positional arguments come in ``reference hypothesis`` pairs (repeat for several
files; the pooled row is the sum of components over the sum of reference speech).
Exit 1 if ``--fail-above`` is given and the pooled DER exceeds it.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

MAX_SPEAKERS = 8  # exhaustive injection search: 8! = 40320 leaves, exact above that is not worth it
EPS = 1e-9


def _parse_segments(text, origin):
    """`start end speaker` / 10-field RTTM -> [(start, end, label)], or error."""
    segments = []
    files = set()
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        try:
            if fields[0].upper() == "SPEAKER":
                if len(fields) != 10:
                    raise ValueError(
                        f"{origin}:{number}: SPEAKER line has {len(fields)} fields, want 10 "
                        "(NIST RTTM: SPEAKER <file> <chnl> <start> <dur> <ortho> <stype> <name> <conf> <slat>)"
                    )
                start, duration, label = float(fields[3]), float(fields[4]), fields[7]
                end = start + duration
                files.add(fields[1])
            else:
                if len(fields) != 3:
                    raise ValueError(
                        f"{origin}:{number}: expected 'start end speaker' or a 10-field SPEAKER "
                        f"line, got {len(fields)} fields: {line[:80]!r}"
                    )
                start, end, label = float(fields[0]), float(fields[1]), fields[2]
        except ValueError as exc:
            raise ValueError(f"{origin}:{number}: {exc}") from None
        if not (math.isfinite(start) and math.isfinite(end)):
            raise ValueError(f"{origin}:{number}: non-finite time")
        if end <= start:
            raise ValueError(f"{origin}:{number}: end {end} is not after start {start}")
        segments.append((start, end, label))
    if len(files) > 1:
        raise ValueError(
            f"{origin}: {len(files)} RTTM file ids ({', '.join(sorted(files))}); score one file per "
            "pair instead of pooling unrelated recordings behind one speaker mapping"
        )
    if not segments:
        raise ValueError(f"{origin}: no segments -- an empty file is not a perfect diarization")
    return segments


def load_segments(path):
    """Load a reference or hypothesis file (RTTM, `start end speaker`, or server JSON)."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ValueError(f"{path}: {exc.strerror or exc}") from None
    stripped = text.strip()
    if not stripped:
        raise ValueError(f"{path}: empty file -- an empty file is not a perfect diarization")
    if stripped[0] in "{[":
        return _segments_from_json(stripped, path)
    return _parse_segments(stripped, path)


def _segments_from_json(text, origin):
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{origin}: invalid JSON ({exc})") from None
    rows = doc.get("segments") if isinstance(doc, dict) else doc
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{origin}: no 'segments' list with entries -- nothing to score")
    segments = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"{origin}: segments[{index}] is {type(row).__name__}, want an object")
        label = row.get("speaker", row.get("label"))
        if label is None or row.get("start") is None or row.get("end") is None:
            raise ValueError(f"{origin}: segments[{index}] needs start, end and speaker: {row!r}")
        try:
            start, end = float(row["start"]), float(row["end"])
        except (TypeError, ValueError):
            raise ValueError(f"{origin}: segments[{index}] has a non-numeric time: {row!r}") from None
        if end <= start:
            raise ValueError(f"{origin}: segments[{index}] end {end} is not after start {start}")
        segments.append((start, end, str(label)))
    return segments


def _search_injection(n_ref, n_hyp, weights):
    """Exact best one-to-one assignment. Returns (value, {hyp_label: ref_label})."""
    if n_ref > MAX_SPEAKERS or n_hyp > MAX_SPEAKERS:
        raise ValueError(
            f"{max(n_ref, n_hyp)} speakers is above the exact-search cap of {MAX_SPEAKERS}; "
            "splitting the input (or writing the assignment) is the honest next step, not a guess"
        )
    best_value, best_assign = -1.0, {}

    def walk(ref, used, total, assign):
        nonlocal best_value, best_assign
        if ref == n_ref:
            if total > best_value:
                best_value, best_assign = total, dict(assign)
            return
        walk(ref + 1, used, total, assign)  # leave this reference speaker unmatched
        for hyp in range(n_hyp):
            if hyp in used:
                continue
            used.add(hyp)
            assign[hyp] = ref
            walk(ref + 1, used, total + weights.get((ref, hyp), 0.0), assign)
            del assign[hyp]
            used.discard(hyp)

    walk(0, set(), 0.0, {})
    return best_value, best_assign


def score_pair(reference, hypothesis, collar=0.25, overlap="score", uem=None):
    """Score one (reference, hypothesis) pair. All times in seconds."""
    if collar < 0:
        raise ValueError("collar must be non-negative")
    if overlap not in ("score", "exclude"):
        raise ValueError(f"overlap must be 'score' or 'exclude', got {overlap!r}")
    if uem is not None:
        region = (float(uem[0]), float(uem[1]))
        if region[1] <= region[0]:
            raise ValueError(f"UEM {region} has no duration")
    else:
        region = (0.0, max(end for _, end, _ in reference + hypothesis))

    # Elementary intervals: cut at every segment edge and every collar band edge.
    cuts = {region[0], region[1]}
    for start, end, _ in reference + hypothesis:
        cuts.add(min(max(start, region[0]), region[1]))
        cuts.add(min(max(end, region[0]), region[1]))
    bands = []
    if collar > 0:
        for start, end, _ in reference:
            for boundary in (start, end):
                bands.append(
                    (
                        min(max(boundary - collar, region[0]), region[1]),
                        min(max(boundary + collar, region[0]), region[1]),
                    )
                )
                cuts.add(bands[-1][0])
                cuts.add(bands[-1][1])
    cuts = sorted(cuts)

    ref_time, hyp_time, inter = {}, {}, {}
    intervals = []
    for start, end in zip(cuts, cuts[1:]):
        if end - start <= EPS:
            continue
        middle = 0.5 * (start + end)
        if any(low < middle < high for low, high in bands):
            continue  # inside a collar band
        active_ref = {label for s, e, label in reference if s < end and e > start}
        active_hyp = {label for s, e, label in hypothesis if s < end and e > start}
        if overlap == "exclude" and len(active_ref) >= 2:
            continue
        if not active_ref and not active_hyp:
            continue
        duration = end - start
        for label in active_ref:
            ref_time[label] = ref_time.get(label, 0.0) + duration
        for label in active_hyp:
            hyp_time[label] = hyp_time.get(label, 0.0) + duration
        for ref_label in active_ref:
            for hyp_label in active_hyp:
                inter[(ref_label, hyp_label)] = inter.get((ref_label, hyp_label), 0.0) + duration
        intervals.append((duration, active_ref, active_hyp))

    reference_speech = sum(ref_time.values())
    if reference_speech <= EPS:
        raise ValueError(
            "reference has no scored speech (empty after collar/overlap/UEM cropping): DER is "
            "undefined, and calling it 0 would make an unscorable fixture look perfect"
        )

    ref_labels = sorted(ref_time)
    hyp_labels = sorted(hyp_time)
    ref_index = {label: index for index, label in enumerate(ref_labels)}
    hyp_index = {label: index for index, label in enumerate(hyp_labels)}
    overlap_weights = {
        (ref_index[r], hyp_index[h]): value for (r, h), value in inter.items()
    }
    _, assignment = _search_injection(len(ref_labels), len(hyp_labels), overlap_weights)
    mapping = {hyp_labels[hyp]: ref_labels[ref] for hyp, ref in assignment.items()}

    correct = missed = false_alarm = speaker_error = 0.0
    for duration, active_ref, active_hyp in intervals:
        matched = {mapping[h] for h in active_hyp if h in mapping}
        correct += duration * len(active_ref & matched)
        if not active_hyp:
            missed += duration * len(active_ref)
            continue
        if not active_ref:
            false_alarm += duration * len(active_hyp)
            continue
        # Both sides active: one error per time unit per *side*, and the worse
        # side wins. Counting both sides would charge a merged speaker twice
        # (missed for the lost reference speaker *and* speaker error for the
        # hypothesis label), which makes merging score worse than being silent.
        missed_side = len(active_ref - matched)
        attributed_side = len([h for h in active_hyp if mapping.get(h) not in active_ref])
        speaker_error += duration * max(missed_side, attributed_side)

    hypothesis_speech = sum(hyp_time.values())

    if correct > min(reference_speech, sum(hyp_time.values())) + 1e-6:
        raise AssertionError(f"correct {correct} exceeds the shorter speech total")

    # JER: same scoring region and collar, matching chosen to maximise per-pair Jaccard.
    jaccard = {}
    for (ref_label, hyp_label), value in inter.items():
        union = ref_time[ref_label] + hyp_time[hyp_label] - value
        if union > EPS:
            jaccard[(ref_index[ref_label], hyp_index[hyp_label])] = value / union
    jaccard_total, _ = _search_injection(len(ref_labels), len(hyp_labels), jaccard)
    jer = 1.0 - jaccard_total / max(len(ref_labels), len(hyp_labels))

    return {
        "scored_region": [round(region[0], 6), round(region[1], 6)],
        "reference_speech": reference_speech,
        "hypothesis_speech": hypothesis_speech,
        "correct": correct,
        "missed": missed,
        "false_alarm": false_alarm,
        "speaker_error": speaker_error,
        "der": (missed + false_alarm + speaker_error) / reference_speech,
        "jer": jer,
        "mapping": {hyp: ref for hyp, ref in sorted(mapping.items())},
        "speakers": {"reference": len(ref_labels), "hypothesis": len(hyp_labels)},
        "collar": collar,
        "overlap": overlap,
    }


def pooled(results):
    """Sum components over the sum of reference speech; DER is not an average of DERs."""
    reference_speech = sum(r["reference_speech"] for r in results)
    if reference_speech <= EPS:
        raise ValueError("pooled reference speech is zero")
    numerator = sum(r["missed"] + r["false_alarm"] + r["speaker_error"] for r in results)
    return {
        "pairs": len(results),
        "reference_speech": reference_speech,
        "missed": sum(r["missed"] for r in results),
        "false_alarm": sum(r["false_alarm"] for r in results),
        "speaker_error": sum(r["speaker_error"] for r in results),
        "der": numerator / reference_speech,
        "jer": sum(r["jer"] for r in results) / len(results),
    }


def _print_table(results):
    header = f"{'#':>2}  {'ref':>7}  {'hyp':>7}  {'DER':>7}  {'missed':>7}  {'fa':>7}  {'spk-err':>7}  {'JER':>7}  mapping"
    print(header)
    print("-" * len(header))
    for index, result in enumerate(results, 1):
        print(
            f"{index:>2}  {result['reference_speech']:>7.2f}  {result['hypothesis_speech']:>7.2f}  "
            f"{result['der']:>7.4f}  {result['missed']:>7.2f}  {result['false_alarm']:>7.2f}  "
            f"{result['speaker_error']:>7.2f}  {result['jer']:>7.4f}  "
            + (", ".join(f"{h}->{r}" for h, r in result["mapping"].items()) or "(none)")
        )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "files",
        nargs="+",
        metavar="reference|hypothesis",
        help="alternating reference and hypothesis paths (one pair, or repeat for several)",
    )
    parser.add_argument("--collar", type=float, default=0.25, help="collar in seconds (default 0.25)")
    parser.add_argument(
        "--overlap",
        choices=("score", "exclude"),
        default="score",
        help="score simultaneous reference speakers per label, or drop those intervals (default score)",
    )
    parser.add_argument(
        "--uem",
        nargs=2,
        type=float,
        metavar=("START", "END"),
        help="scored region in seconds (default: 0 to the latest segment end)",
    )
    parser.add_argument("--json", metavar="PATH", help="write the full result as JSON")
    parser.add_argument(
        "--fail-above",
        type=float,
        metavar="DER",
        help="exit 1 if the pooled DER exceeds this (a pre-registered bar, not a default)",
    )
    args = parser.parse_args(argv)
    if len(args.files) % 2:
        parser.error("files must come in reference/hypothesis pairs")

    results = []
    try:
        for reference_path, hypothesis_path in zip(args.files[::2], args.files[1::2]):
            result = score_pair(
                load_segments(reference_path),
                load_segments(hypothesis_path),
                collar=args.collar,
                overlap=args.overlap,
                uem=args.uem,
            )
            result = {
                "reference": str(reference_path),
                "hypothesis": str(hypothesis_path),
                **result,
            }
            results.append(result)
        summary = pooled(results)
    except ValueError as exc:
        print(f"diarize-score: {exc}", file=sys.stderr)
        return 2

    _print_table(results)
    if len(results) > 1:
        print(
            f"pooled: {summary['pairs']} pairs, DER {summary['der']:.4f}, JER {summary['jer']:.4f} "
            f"(ref speech {summary['reference_speech']:.2f}s)"
        )
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"pairs": results, "pooled": summary}, indent=2) + "\n")
        print(f"wrote {out}")
    if args.fail_above is not None and summary["der"] > args.fail_above:
        print(
            f"FAIL: pooled DER {summary['der']:.4f} > {args.fail_above:.4f}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
