#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Acceptance probe for the Haru-4B realtime duplex arm.

Drives one conversation on the serve's ``/v1/realtime?duplex=1`` WebSocket with
the client the serving wheel already ships -- ``haru.backends.VllmBackend`` --
prints a summary, and exits non-zero when the session delivers no output frame.
It runs inside the serve container, which is where ``haru``, ``aiohttp`` and
``numpy`` are:

    docker exec <container> python3 /workspace/mods/haru-4b-realtime-launcher/probe.py

Exit 0: frames delivered and at least one carried audio or text.
Exit 2: frames delivered, every one silent and textless (the wire works; the
        model did not speak).
Exit 1: no frame -- error, timeout, or the session closed.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import statistics
import time
from importlib import resources

import numpy as np

SAMPLE_RATE = 24_000
FRAME_SAMPLES = 3200  # 133 ms at 24 kHz: the protocol's frame
SILENT = 1e-4
SEED = 1234  # fixed, so a receipt reproduces the same frames


def voiced_clip(frames: int) -> np.ndarray:
    """A deterministic speech-like clip: a 110-130 Hz pulse train through two formants, syllabic.

    Not a recording. It is voiced rather than digital silence so the encoder path
    carries real energy; the words are not the point, the wire is.
    """
    if frames < 1:
        return np.zeros(0, dtype=np.float32)
    t = np.arange(frames * FRAME_SAMPLES) / SAMPLE_RATE
    phase = 2 * np.pi * np.cumsum(110.0 + 20.0 * np.sin(2 * np.pi * 0.7 * t)) / SAMPLE_RATE
    signal = sum(np.exp(-0.5 * ((k * 110.0 - 700.0) / 220.0) ** 2) * np.sin(k * phase) for k in range(1, 25))
    signal *= 0.5 - 0.5 * np.cos(2 * np.pi * 2.0 * t)  # about two syllables a second
    return (0.3 * signal / np.max(np.abs(signal))).astype(np.float32)


def card_prompt() -> str:
    """The wheel's English character card, rendered by the wheel's own renderer."""
    from haru.prompt import card_templates, render_card

    card = json.loads((resources.files("haru") / "assets" / "cards" / "en.json").read_text(encoding="utf-8"))
    return render_card(card["chat"], card_templates()["templates"]["en"])


async def run(args: argparse.Namespace) -> int:
    from haru.backends import SessionSettings, VllmBackend

    prompt = card_prompt()
    backend = VllmBackend(args.url)
    print(f"endpoint: {backend.url.replace('http', 'ws', 1)}/v1/realtime?duplex=1")
    print(f"card: {len(prompt)} chars, seed {SEED}, speak_first {not args.no_speak_first}, {args.frames} appends")

    print(f"phase health: waiting for /health (<= {args.timeout:g} s)")
    opened = time.perf_counter()
    await asyncio.wait_for(backend.load(), args.timeout)
    health_s = time.perf_counter() - opened
    conversation = await backend.open(
        SessionSettings(
            system_prompt=prompt,
            seed=SEED,
            speak_first=not args.no_speak_first,
            max_frames=args.frames + 1,
        )
    )

    print(f"phase session: session.update, then session.created and frame 0 (<= {args.timeout:g} s)")
    frames = []
    try:
        first = time.perf_counter()
        frames.append(await asyncio.wait_for(conversation.start(), args.timeout))
        opening_s = time.perf_counter() - first
        print(f"phase frames: {args.frames} appends, one output frame each (<= {args.step_timeout:g} s per frame)")
        clip = voiced_clip(args.frames)
        for index in range(args.frames):
            chunk = clip[index * FRAME_SAMPLES : (index + 1) * FRAME_SAMPLES]
            frames.append(await asyncio.wait_for(conversation.step(chunk), args.step_timeout))
    finally:
        with contextlib.suppress(Exception):
            await conversation.close()

    audio = np.concatenate([frame.audio.reshape(-1) for frame in frames])
    loud = sum(1 for frame in frames if float(np.max(np.abs(frame.audio))) > SILENT)
    text = "".join(frame.text for frame in frames)
    steps = [frame.seconds for frame in frames[1:]]
    print(f"health: /health answered after {health_s:.1f} s")
    print(f"frames: in {args.frames + 1} (the first opens the session), out {len(frames)}")
    print(f"audio: {len(audio)} samples at {SAMPLE_RATE} Hz, {loud} of {len(frames)} frames non-silent, peak {float(np.max(np.abs(audio))):.3f}")
    print(f"text: {len(text)} chars, first 160: {text[:160]!r}")
    if steps:
        print(f"timing: opening frame {opening_s:.2f} s; steps median {1000 * statistics.median(steps):.0f} ms, min {1000 * min(steps):.0f} ms, max {1000 * max(steps):.0f} ms")

    if not loud and not text.strip():
        print("probe silent: frames delivered, all silent and textless")
        return 2
    print("probe ok: the duplex session delivered output")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Acceptance probe for the Haru-4B realtime duplex arm.")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="serve base URL (default: %(default)s)")
    parser.add_argument("--frames", type=int, default=8, help="appends after the opening frame (default: %(default)s)")
    parser.add_argument("--timeout", type=float, default=600.0, help="seconds for /health and for frame 0 (default: %(default)s)")
    parser.add_argument("--step-timeout", type=float, default=60.0, help="seconds per output frame (default: %(default)s)")
    parser.add_argument("--no-speak-first", action="store_true", help="the model listens until the input sounds like speech")
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except Exception as error:  # the probe's verdict, not a crash
        print(f"probe failed: {type(error).__name__}: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
