#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Committed forecast fixtures for the Timestral probe (tools/forecast-bench.py).

Why this file exists
--------------------
The Timestral item (`mad-science/TODO.md`, researched 2026-10-22) pre-registered this
generator: the registry has no probabilistic-forecast instrument, no third-party series
is redistributed (GIFT-Eval / TIME / fev-bench licenses differ and their numbers are
leaderboard aggregates a handful of series cannot reproduce), and a committed generator
plus seed is byte-reproducible and yields an oracle the leaderboards cannot.

Six synthesised series, stdlib only, fixed seed, 4,096 steps each:

  1. `01-gaussian-random-walk`  -- the important one.  Its h-step predictive law is
     analytic (N(x_T, h*sigma^2)), so the scorer can compare a model's CRPS against
     the *exact* CRPS of the true law, which no real benchmark offers.
  2. `02-trend-weekly-ar1`      -- trend + weekly seasonality + AR(1) noise.
  3. `03-level-shift`           -- the same generator with a level shift mid-series
     (inside the context; tests whether the model adapts).
  4. `04-missing-block`         -- a NaN block inside the context, to exercise
     Timestral's `attend_missing_patches` path.
  5. `05-bivariate-covariate`   -- a 2-variate pair whose second variate is a
     known-future covariate (its horizon values are part of the fixture).
  6. `06-constant`              -- the degenerate case.

The context/horizon split is a scorer convention, not a fixture property: horizon is
the LAST `--horizon` (default 96) steps of every series; context is everything before
it.  The bivariate covariate is the one series whose horizon values are known inputs.

Determinism: one `random.Random(seed + series_index)` per series; the canonical JSON
dump is hashed and printed, so a receipt can pin the exact bytes (`REPORT.md` carries
the fixture hash per the item's pre-registration).

`--selftest` regenerates and asserts the properties the scorer relies on (a guard that
has only ever passed is not a guard).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys

DEFAULT_STEPS = 4096
DEFAULT_HORIZON = 96
DEFAULT_SEED = 20261024
WEEK = 7
LEVEL_SHIFT_AT = 3072
MISSING_BLOCK_AT = 1000
MISSING_BLOCK_LEN = 96


def _walk(steps, rng):
    """Pure Gaussian random walk, x_0 = 0, per-step N(0, 1)."""
    out, x = [], 0.0
    for _ in range(steps):
        x += rng.gauss(0.0, 1.0)
        out.append(x)
    return out


def _weekly_ar1(steps, rng):
    """Trend 0.01/step + weekly sinusoid (amplitude 3) + AR(1) noise (phi 0.7, sigma 1)."""
    out, e = [], 0.0
    for t in range(steps):
        e = 0.7 * e + rng.gauss(0.0, 1.0)
        out.append(0.01 * t + 3.0 * math.sin(2 * math.pi * t / WEEK) + e)
    return out


def _covariate(steps):
    """Known-future covariate: a deterministic weekly square wave (its horizon is knowable)."""
    return [1.0 if (t % WEEK) < 3 else 0.0 for t in range(steps)]


def build_series(steps, seed):
    """Return the six named series as a JSON-ready dict (insertion order = names)."""
    series = {}

    rng = random.Random(seed + 1)
    series["01-gaussian-random-walk"] = {"variates": 1, "values": _walk(steps, rng)}

    rng = random.Random(seed + 2)
    series["02-trend-weekly-ar1"] = {"variates": 1, "values": _weekly_ar1(steps, rng)}

    rng = random.Random(seed + 2)
    shifted = _weekly_ar1(steps, rng)
    for t in range(LEVEL_SHIFT_AT, steps):
        shifted[t] += 10.0
    series["03-level-shift"] = {"variates": 1, "values": shifted}

    missing = list(series["02-trend-weekly-ar1"]["values"])
    for t in range(MISSING_BLOCK_AT, min(MISSING_BLOCK_AT + MISSING_BLOCK_LEN, steps)):
        missing[t] = None
    series["04-missing-block"] = {"variates": 1, "values": missing}

    rng = random.Random(seed + 5)
    cov = _covariate(steps)
    y = [0.5 * cov[t] + rng.gauss(0.0, 0.25) for t in range(steps)]
    series["05-bivariate-covariate"] = {"variates": 2, "values": y, "covariate": cov}

    series["06-constant"] = {"variates": 1, "values": [5.0] * steps}
    return series


def build(steps, horizon, seed):
    return {
        "meta": {
            "generator": "tools/forecast-fixtures.py",
            "seed": seed,
            "steps": steps,
            "horizon": horizon,
            "series_count": 6,
        },
        "series": build_series(steps, seed),
    }


def canonical_bytes(doc):
    """Canonical dump: sort_keys, compact separators -- the bytes the hash pins."""
    return json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()


def selftest(steps, horizon, seed):
    a = build(steps, horizon, seed)
    b = build(steps, horizon, seed)
    assert canonical_bytes(a) == canonical_bytes(b), "fixtures not byte-deterministic"
    assert len(a["series"]) == 6
    for name, s in a["series"].items():
        assert len(s["values"]) == steps, name
    assert all(v == 5.0 for v in a["series"]["06-constant"]["values"])
    blk = a["series"]["04-missing-block"]["values"][MISSING_BLOCK_AT:MISSING_BLOCK_AT + MISSING_BLOCK_LEN]
    assert all(v is None for v in blk) and len(blk) == MISSING_BLOCK_LEN
    assert a["series"]["04-missing-block"]["values"][MISSING_BLOCK_AT - 1] is not None
    assert a["series"]["04-missing-block"]["values"][-horizon:] == \
        a["series"]["02-trend-weekly-ar1"]["values"][-horizon:], "missing block leaked into horizon"
    cov = a["series"]["05-bivariate-covariate"]["covariate"]
    assert all(v in (0.0, 1.0) for v in cov[-horizon:]), "covariate horizon not known-future"
    walk = a["series"]["01-gaussian-random-walk"]["values"]
    diffs = [walk[i + 1] - walk[i] for i in range(len(walk) - 1)]
    assert abs(sum(diffs) / len(diffs)) < 0.2 and abs(
        (sum(d * d for d in diffs) / len(diffs)) - 1.0) < 0.2, "walk step law drifted"
    return canonical_bytes(a)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default="forecast-fixtures.json", help="output JSON path")
    p.add_argument("--steps", type=int, default=DEFAULT_STEPS)
    p.add_argument("--horizon", type=int, default=DEFAULT_HORIZON)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--selftest", action="store_true", help="assert fixture properties and exit")
    args = p.parse_args(argv)

    digest = selftest(args.steps, args.horizon, args.seed)
    if args.selftest:
        print("selftest OK", hashlib.sha256(digest).hexdigest())
        return 0
    doc = build(args.steps, args.horizon, args.seed)
    data = canonical_bytes(doc)
    with open(args.out, "wb") as f:
        f.write(data + b"\n")
    print(json.dumps({"out": args.out, "sha256": hashlib.sha256(data).hexdigest(),
                      "steps": args.steps, "horizon": args.horizon, "seed": args.seed}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
