#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Deterministic speaker-diarization fixtures with known ground truth.

Why this file exists
--------------------
`tools/diarize-score.py` scores "who spoke when", and a scorer needs an input
whose answer is known before a model is in the loop.  This generates that input
in two tiers:

* **tier A -- synthetic tones, pure stdlib.**  Two fixed layouts (a two-speaker
  turn-taking dialogue and a three-speaker one that ends in a deliberate
  overlap) rendered with the ``wave`` module from closed-form arithmetic.
  *There is no random number generator anywhere in this file*: every sample is a
  function of (time, speaker, the tables below), so a reproducer on any machine
  and any Python 3 gets byte-identical WAVs.  ``--check`` proves that by
  regenerating and comparing sha256 against the manifest.
* **tier B -- spliced real speech.**  ``--splice a.wav b.wav`` alternates
  fixed-length chunks of two existing single-speaker recordings into one
  turn-taking fixture with an exact ground truth.  That is how a TTS pair
  (drama-3 voices) becomes a diarization fixture without hand-labelling.

Tier A proves the *plumbing* and the scorer; it says nothing about whether a
diarizer is any good on real speech, and neither tier says anything about
whether the speech is intelligible.  DER measures who spoke when, not whether
the words are right -- an intelligibility claim still needs an ASR pass or the
owner's ears.

Committed or generated?
-----------------------
Generated on demand.  A 30 s 16 kHz WAV is ~1 MB, and two of them in git is
weight nobody reads; the manifest carries the synthesis parameters and the
sha256, so ``--check`` re-derives the bytes instead of trusting a stored copy.
A boot should do::

    uv run python -B tools/diarize-fixture.py --out ~/benchmarks/pyannote-20261022/fixtures
    uv run python -B tools/diarize-fixture.py --out ~/benchmarks/pyannote-20261022/fixtures --check

Outputs per layout: ``<layout>.wav``, ``<layout>.rttm`` (NIST 10-field, so
``diarize-score.py`` reads it directly) and ``manifest.json`` (turns, synthesis
parameters, hashes, per-speaker speech seconds).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import struct
import sys
import wave
from pathlib import Path

SAMPLE_RATE = 16000
FADE_SECONDS = 0.01  # raised-cosine fade so turn edges do not click
PEAK = 0.25  # of full scale; leaves headroom for the overlap turn summing two voices

# (f0 Hz, harmonic weights, harmonic phases) -- fixed tables, no RNG.
VOICES = {
    "A": (110.0, (1.0, 0.50, 0.25, 0.12), (0.0, 0.4, 1.1, 2.0)),
    "B": (165.0, (1.0, 0.25, 0.50, 0.20), (0.7, 1.3, 0.2, 2.6)),
    "C": (220.0, (1.0, 0.35, 0.15, 0.35), (1.9, 0.3, 2.2, 1.0)),
}

LAYOUTS = {
    # 8 turns of 3 s with 0.75 s gaps: every turn is comfortably longer than 2*collar.
    "two-speaker": {
        "duration": 30.0,
        "turns": [
            (index * 3.75, index * 3.75 + 3.0, "AB"[index % 2]) for index in range(8)
        ],
        "note": "strict turn taking, one speaker at a time",
    },
    # 8 turns then a 2.5 s overlap of A and B: exercises --overlap score|exclude.
    "three-speaker": {
        "duration": 35.0,
        "turns": [
            (index * 4.0, index * 4.0 + 3.0, "ABC"[index % 3]) for index in range(8)
        ]
        + [(32.0, 34.5, "A"), (32.0, 34.5, "B")],
        "note": "A/B/C rotation ending in a 2.5 s A+B overlap",
    },
}


def _envelope(local_time, length):
    ramp = min(1.0, local_time / FADE_SECONDS, (length - local_time) / FADE_SECONDS)
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, ramp))


def _voice_value(label, time):
    f0, weights, phases = VOICES[label]
    total = sum(
        weight * math.sin(2.0 * math.pi * f0 * harmonic * time + phase)
        for harmonic, (weight, phase) in enumerate(zip(weights, phases), 1)
    )
    return total / sum(weights)


def render(turns, duration, sample_rate=SAMPLE_RATE):
    """turns -> little-endian PCM16 mono bytes. Closed form, no RNG."""
    frames = bytearray()
    for index in range(int(round(duration * sample_rate))):
        time = index / sample_rate
        value = 0.0
        for start, end, label in turns:
            if start <= time < end:
                value += _envelope(time - start, end - start) * _voice_value(label, time)
        frames += struct.pack("<h", max(-32767, min(32767, int(round(32767 * PEAK * value)))))
    return bytes(frames)


def wav_bytes(frames, sample_rate=SAMPLE_RATE):
    """Raw PCM16 mono -> a complete RIFF/WAVE container."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(frames)
    return buffer.getvalue()


def write_wav(path, frames, sample_rate=SAMPLE_RATE):
    """Raw PCM16 mono -> a WAV file on disk."""
    Path(path).write_bytes(wav_bytes(frames, sample_rate))


def read_wav(path):
    """PCM16 mono at SAMPLE_RATE, or a ValueError naming what is wrong."""
    try:
        with wave.open(str(path), "rb") as handle:
            if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
                raise ValueError(
                    f"{path}: need mono 16-bit PCM, got {handle.getnchannels()} channel(s) "
                    f"{8 * handle.getsampwidth()}-bit"
                )
            if handle.getframerate() != SAMPLE_RATE:
                raise ValueError(f"{path}: need {SAMPLE_RATE} Hz, got {handle.getframerate()} Hz")
            return handle.readframes(handle.getnframes())
    except (wave.Error, EOFError) as exc:
        raise ValueError(f"{path}: not a readable PCM WAV ({exc})") from None
    except OSError as exc:
        raise ValueError(f"{path}: {exc.strerror or exc}") from None


def rttm_text(name, turns):
    lines = [
        f"SPEAKER {name} 1 {start:.3f} {end - start:.3f} <NA> <NA> {label} <NA> <NA>"
        for start, end, label in sorted(turns)
    ]
    return "\n".join(lines) + "\n"


def speech_seconds(turns):
    totals = {}
    for start, end, label in turns:
        totals[label] = totals.get(label, 0.0) + (end - start)
    return {label: round(value, 3) for label, value in sorted(totals.items())}


def build_layout(name):
    layout = LAYOUTS[name]
    frames = render(layout["turns"], layout["duration"])
    synthesis = {
        "kind": "sum of harmonics with raised-cosine turn envelopes; no RNG",
        "sample_rate": SAMPLE_RATE,
        "peak": PEAK,
        "fade_seconds": FADE_SECONDS,
        "voices": {
            label: {"f0": f0, "weights": list(weights), "phases": list(phases)}
            for label, (f0, weights, phases) in VOICES.items()
            if label in {turn[2] for turn in layout["turns"]}
        },
    }
    return {
        "wav": frames,
        "rttm": rttm_text(name, layout["turns"]),
        "meta": {
            "layout": name,
            "note": layout["note"],
            "duration": layout["duration"],
            "turns": [list(turn) for turn in layout["turns"]],
            "speech_seconds": speech_seconds(layout["turns"]),
            "synthesis": synthesis,
        },
    }


def build_splice(name, first, second, chunk, gap, turns_wanted):
    """Alternate fixed chunks of two single-speaker recordings into one dialogue."""
    if chunk <= 0 or gap < 0 or turns_wanted < 2:
        raise ValueError("--chunk must be > 0, --gap >= 0, --turns >= 2")
    sources = [read_wav(first), read_wav(second)]
    chunk_bytes = int(round(chunk * SAMPLE_RATE)) * 2
    usable = min(len(frames) // chunk_bytes for frames in sources)
    if usable < 1:
        raise ValueError(
            f"a spliced input is shorter than one {chunk}s chunk ({min(len(f) for f in sources)} bytes)"
        )
    # A turn whose chunk offset starts at or past a source's end comes out zero-length,
    # and no scorer accepts that: refuse instead of writing unscoreable ground truth.
    # A trailing partial chunk is fine -- it is real audio, just shorter.
    last_offset = ((turns_wanted - 1) // 2) * chunk_bytes
    shortest = min(len(frames) for frames in sources)
    if last_offset >= shortest:
        raise ValueError(
            f"--turns {turns_wanted} needs chunk {((turns_wanted - 1) // 2) + 1} of both "
            f"inputs, but the shorter one holds {shortest / 2 / SAMPLE_RATE:.3f}s -- "
            f"lower --turns or --chunk"
        )
    gaps = b"\x00\x00" * int(round(gap * SAMPLE_RATE))
    frames = bytearray(gaps)
    truth = []
    for index in range(turns_wanted):
        source = index % 2
        take = sources[source][(index // 2) * chunk_bytes : (index // 2 + 1) * chunk_bytes]
        start = len(frames) // 2 / SAMPLE_RATE
        frames += take + gaps
        truth.append((round(start, 3), round(start + len(take) // 2 / SAMPLE_RATE, 3), "AB"[source]))
    meta = {
        "layout": name,
        "note": f"spliced {chunk}s chunks of two recordings, {gap}s gaps, {turns_wanted} turns",
        "duration": round(len(frames) / 2 / SAMPLE_RATE, 3),
        "turns": [list(turn) for turn in truth],
        "speech_seconds": speech_seconds(truth),
        "synthesis": {
            "kind": "splice",
            "inputs": [
                {
                    "path": str(path),
                    "sha256": hashlib.sha256(frames).hexdigest(),
                    "chunk_seconds": chunk,
                    "chunks_used": min(usable, (turns_wanted + 1) // 2),
                }
                for path, frames in ((first, sources[0]), (second, sources[1]))
            ],
            "gap_seconds": gap,
            "sample_rate": SAMPLE_RATE,
        },
    }
    return {"wav": bytes(frames), "rttm": rttm_text(name, truth), "meta": meta}


def emit(out_dir, built):
    out_dir.mkdir(parents=True, exist_ok=True)
    wav_path = out_dir / f"{built['meta']['layout']}.wav"
    rttm_path = out_dir / f"{built['meta']['layout']}.rttm"
    data = wav_bytes(built["wav"])
    wav_path.write_bytes(data)
    rttm_path.write_text(built["rttm"])
    built["meta"]["wav_sha256"] = hashlib.sha256(data).hexdigest()
    built["meta"]["wav_bytes"] = len(data)
    built["meta"]["rttm_sha256"] = hashlib.sha256(built["rttm"].encode()).hexdigest()
    return built["meta"]


def check(out_dir):
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.is_file():
        return f"{manifest_path}: missing, nothing to check against"
    manifest = json.loads(manifest_path.read_text())
    problems = []
    for entry in manifest["layouts"]:
        name = entry["layout"]
        if entry["synthesis"]["kind"] == "splice":
            continue  # inputs are not in the manifest; --check covers tier A only
        rebuilt = build_layout(name)
        if hashlib.sha256(wav_bytes(rebuilt["wav"])).hexdigest() != entry["wav_sha256"]:
            problems.append(f"{name}.wav: rebuilt bytes differ from the manifest sha256")
        if hashlib.sha256(rebuilt["rttm"].encode()).hexdigest() != entry["rttm_sha256"]:
            problems.append(f"{name}.rttm: rebuilt ground truth differs from the manifest sha256")
        on_disk = out_dir / f"{name}.wav"
        if not on_disk.is_file():
            problems.append(f"{name}.wav: missing from {out_dir}")
            continue
        if hashlib.sha256(on_disk.read_bytes()).hexdigest() != entry["wav_sha256"]:
            problems.append(f"{name}.wav: on disk differs from the manifest sha256")
        # A byte-stable file can still be headerless raw PCM (sha256 cannot see a format
        # defect); only decoding proves the container is there.
        try:
            read_wav(on_disk)
        except ValueError as exc:
            problems.append(str(exc))
    return "; ".join(problems)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--out", required=True, metavar="DIR", help="fixture directory")
    parser.add_argument(
        "--layout",
        choices=(*sorted(LAYOUTS), "all"),
        default="all",
        help="which tier-A layout to render (default all)",
    )
    parser.add_argument("--check", action="store_true", help="re-verify existing tier-A fixtures")
    parser.add_argument(
        "--splice",
        nargs=2,
        metavar=("A.wav", "B.wav"),
        help="tier B: build a dialogue from two single-speaker 16 kHz mono recordings",
    )
    parser.add_argument("--name", default="spliced", help="layout name for --splice (default spliced)")
    parser.add_argument("--chunk", type=float, default=2.5, help="splice chunk seconds (default 2.5)")
    parser.add_argument("--gap", type=float, default=0.5, help="splice gap seconds (default 0.5)")
    parser.add_argument("--turns", type=int, default=8, help="splice turn count (default 8)")
    args = parser.parse_args(argv)
    out_dir = Path(args.out).expanduser()

    if args.check:
        problem = check(out_dir)
        if problem:
            print(f"diarize-fixture: CHECK FAILED -- {problem}", file=sys.stderr)
            return 1
        print(f"diarize-fixture: {out_dir} matches its manifest")
        return 0

    layouts = []
    manifest_path = out_dir / "manifest.json"
    if manifest_path.is_file():
        layouts = json.loads(manifest_path.read_text()).get("layouts", [])

    try:
        if args.splice:
            built = build_splice(
                args.name, args.splice[0], args.splice[1], args.chunk, args.gap, args.turns
            )
            entry = emit(out_dir, built)
            layouts = [row for row in layouts if row["layout"] != entry["layout"]] + [entry]
            print(
                f"diarize-fixture: {entry['layout']} -- {entry['duration']}s, "
                f"{len(entry['turns'])} turns, {entry['speech_seconds']}"
            )
        else:
            names = sorted(LAYOUTS) if args.layout == "all" else [args.layout]
            for name in names:
                entry = emit(out_dir, build_layout(name))
                layouts = [row for row in layouts if row["layout"] != entry["layout"]] + [entry]
                print(
                    f"diarize-fixture: {entry['layout']} -- {entry['wav_bytes']} bytes, "
                    f"sha256 {entry['wav_sha256'][:16]}, {entry['speech_seconds']}"
                )
    except ValueError as exc:
        print(f"diarize-fixture: {exc}", file=sys.stderr)
        return 2

    manifest_path.write_text(
        json.dumps({"sample_rate": SAMPLE_RATE, "layouts": layouts}, indent=2) + "\n"
    )
    print(f"wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
