#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Scorer for probabilistic forecasts -- the instrument the Timestral arm is gated on.

Why this file exists
--------------------
`mad-science/TODO.md` (Timestral item, researched 2026-10-22) pre-registered this
scorer: the registry's instruments are chat cells (`tools/quality-battery.py`), decode
ladders, and a haystack needle, and none of them can score a forecast.  Timestral is
the first probabilistic forecaster in the registry, so the instrument is pre-registered
here rather than inherited.

Inputs
------
* fixtures JSON from `tools/forecast-fixtures.py` (six committed synthesised series;
  horizon = the LAST `horizon` steps of each series, context = everything before it);
* a predictions JSON: for every series name, 21 quantiles 0.01...0.99 for the horizon:

    {"meta": {...},
     "predictions": {"01-gaussian-random-walk": {"quantiles": {"0.01": [96 floats],
                                                               ..., "0.99": [96 floats]}}}}

Metrics (per series, then pooled)
---------------------------------
* **mean CRPS** from the quantile grid as `(2/K) * sum_tau mean pinball_tau`, K = 21
  (the quantile-grid CRPS approximation);
* mean pinball loss per quantile level;
* **MASE** against a seasonal-naive baseline (period 7: the last week of the context
  tiled over the horizon) on the same split;
* **PICP** at the 80 % interval: fraction of horizon steps whose actual falls inside
  [q_0.10, q_0.90];
* a **quantile-ordering check**: values non-decreasing across the 21 levels at every
  horizon step.

Hard fails (exit 3, pre-registered in the item)
-----------------------------------------------
* any **non-monotone quantile** -- the failure mode these models actually exhibit, it
  invalidates the whole 21-quantile claim;
* model CRPS **worse than the seasonal-naive baseline** on a series (scored through
  this same tool via `--emit-baseline`, whose degenerate grid makes CRPS = MAE).

The card's 0.446 GIFT-Eval CRPS figure belongs to the *runtime* cell, not the scorer:
on the analytic-oracle series the tool also prints the exact CRPS of the true law
(`oracle_crps`, closed form for a Gaussian), so a >25 % gap is visible without
re-deriving anything.

Stdlib only, on purpose -- head node, container, or laptop.  `--selftest` runs the
controls a guard needs: a perfect oracle scores ~the analytic CRPS on the walk, a
non-monotone grid fails, the baseline scores exactly its own MAE, and PICP bounds hold.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

WEEK = 7
QUANTILES = [0.01] + [round(0.05 * k, 2) for k in range(1, 20)] + [0.99]  # 21 levels


def pinball(tau, actual, predicted):
    """Pinball (quantile) loss for one level/step."""
    d = actual - predicted
    return d * tau if d >= 0 else (tau - 1.0) * d


def crps_from_quantiles(grid, actual):
    """(2/K) * sum_tau pinball_tau -- the quantile-grid CRPS over one step."""
    total = 0.0
    for tau, q in zip(QUANTILES, grid):
        total += pinball(tau, actual, q)
    return (2.0 / len(QUANTILES)) * total


def seasonal_naive(values, horizon, period=WEEK):
    """Point forecast: the last `period` observed values tiled over the horizon."""
    context = values[:len(values) - horizon] if horizon else values
    tail = context[-period:]
    return [tail[i % period] for i in range(horizon)]


def oracle_crps_gaussian(mean, sd, actual):
    """Exact CRPS of N(mean, sd) at `actual` (Gneiting & Raftery closed form)."""
    z = (actual - mean) / sd
    phi = math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)
    return sd * (z * (2 * _cdf(z) - 1) + 2 * phi - 1 / math.sqrt(math.pi))


def _cdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def score_series(name, series, pred, horizon):
    """Score one series; returns (metrics, hard_fail_reasons)."""
    values = series["values"]
    n = len(values)
    target = values[n - horizon:]
    context = values[:n - horizon]
    qs = pred["quantiles"]
    grids = list(zip(*[qs[q] for q in map(str, QUANTILES)]))
    if len(grids) != horizon:
        raise SystemExit("%s: expected %d horizon steps in the grid, got %d"
                         % (name, horizon, len(grids)))

    fails = []
    for i, grid in enumerate(grids):
        for a, b in zip(grid, grid[1:]):
            if b < a:
                fails.append("%s step %d: quantiles not monotone (%s > %s)"
                             % (name, i, a, b))
                break

    pin_by_level = {}
    for tau, col in zip(QUANTILES, zip(*grids)):
        pin_by_level[tau] = round(statistics.fmean(pinball(tau, y, q)
                                                    for y, q in zip(target, col)), 6)
    crps = statistics.fmean(crps_from_quantiles(g, y) for g, y in zip(grids, target))

    base = seasonal_naive(values, horizon)
    base_mae = statistics.fmean(abs(y - b) for y, b in zip(target, base))
    model_mae = statistics.fmean(abs(y - q) for y, q in zip(target, grids[len(QUANTILES) // 2]))
    # MASE denominator: in-sample one-step seasonal-naive errors over the context (m = 7);
    # NaN context steps (the missing-block fixture) contribute no error term.
    ctx_errs = [abs(context[t] - context[t - WEEK]) for t in range(WEEK, len(context))
                if context[t] is not None and context[t - WEEK] is not None]
    mase = None if not ctx_errs or statistics.fmean(ctx_errs) == 0 \
        else model_mae / statistics.fmean(ctx_errs)

    lo = qs["0.1"] if "0.1" in qs else qs["0.10"]
    hi = qs["0.9"] if "0.9" in qs else qs["0.90"]
    picp = statistics.fmean(1.0 if lo[i] <= y <= hi[i] else 0.0
                            for i, y in enumerate(target))

    metrics = {
        "crps": round(crps, 6),
        "pinball_by_level": pin_by_level,
        "mase_vs_seasonal_naive": None if mase is None else round(mase, 6),
        "seasonal_naive_mae": round(base_mae, 6),
        "picp80": round(picp, 4),
        "monotone": not fails,
    }
    if name == "01-gaussian-random-walk":
        step_var = 1.0
        metrics["oracle_crps"] = round(statistics.fmean(
            oracle_crps_gaussian(context[-1], math.sqrt(h * step_var), y)
            for h, y in enumerate(target, start=1)), 6)
    return metrics, fails


def emit_baseline(fixtures, horizon):
    """Degenerate prediction grid (every quantile = the seasonal-naive point) so the
    baseline is scored through the same path; its CRPS equals its MAE."""
    preds = {}
    for name, series in fixtures["series"].items():
        point = seasonal_naive(series["values"], horizon)
        preds[name] = {"quantiles": {str(t): list(point) for t in QUANTILES}}
    return {"meta": {"baseline": "seasonal-naive(period 7)"}, "predictions": preds}


def score(fixtures, preds, horizon):
    rows, all_fails = {}, []
    for name, series in fixtures["series"].items():
        if name not in preds["predictions"]:
            all_fails.append("%s: no prediction row" % name)
            continue
        metrics, fails = score_series(name, series, preds["predictions"][name], horizon)
        rows[name] = metrics
        all_fails.extend(fails)
        if metrics["mase_vs_seasonal_naive"] is not None and \
                metrics["crps"] > metrics["seasonal_naive_mae"]:
            all_fails.append("%s: CRPS %s worse than seasonal-naive MAE %s"
                             % (name, metrics["crps"], metrics["seasonal_naive_mae"]))
    pooled = {"mean_crps": round(statistics.fmean(r["crps"] for r in rows.values()), 6)
              if rows else None,
              "series": len(rows)}
    return {"per_series": rows, "pooled": pooled}, all_fails


def selftest():
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("forecast_fixtures",
                                         str(Path(__file__).resolve().parent / "forecast-fixtures.py"))
    fx = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(fx)

    steps, horizon, seed = 512, 96, 7
    fixtures = fx.build(steps, horizon, seed)
    walk_name = "01-gaussian-random-walk"
    walk = fixtures["series"][walk_name]["values"]
    ctx = walk[:steps - horizon]

    def grid_from_cols(cols):
        return {"quantiles": {str(t): list(c) for t, c in zip(QUANTILES, cols)}}

    # 1. Perfect oracle on the random walk: model CRPS ~ the exact analytic CRPS.
    #    The other series carry baseline grids so score() sees a full row set.
    base = emit_baseline(fixtures, horizon)
    oracle_cols = [[ctx[-1] + math.sqrt(h) * _qinv(t) for h in range(1, horizon + 1)]
                   for t in QUANTILES]
    preds = {"meta": {}, "predictions": dict(base["predictions"])}
    preds["predictions"][walk_name] = grid_from_cols(oracle_cols)
    report, fails = score(fixtures, preds, horizon)
    assert not fails, fails
    m = report["per_series"][walk_name]
    assert abs(m["crps"] - m["oracle_crps"]) / m["oracle_crps"] < 0.15, (m["crps"], m["oracle_crps"])

    # 2. A non-monotone grid is a hard fail: swap the q=0.50 and q=0.55 level columns.
    bad = {"meta": {}, "predictions": dict(base["predictions"])}
    lvl = {k: list(v) for k, v in preds["predictions"][walk_name]["quantiles"].items()}
    lvl["0.5"], lvl["0.55"] = lvl["0.55"], lvl["0.5"]
    bad["predictions"][walk_name] = {"quantiles": lvl}
    rows, fails = score(fixtures, bad, horizon)
    assert any("not monotone" in f for f in fails), fails

    # 3. The degenerate baseline grid scores exactly its own MAE (CRPS == MAE for a
    #    point forecast), and the baseline never trips its own worse-than check.
    report, fails = score(fixtures, base, horizon)
    assert not fails, fails
    b = report["per_series"]["02-trend-weekly-ar1"]
    assert abs(b["crps"] - b["seasonal_naive_mae"]) < 1e-6, (b["crps"], b["seasonal_naive_mae"])

    # 4. A garbage forecast loses to the baseline; PICP is bounded in [0, 1].
    junk = {"meta": {}, "predictions": dict(base["predictions"])}
    junk["predictions"][walk_name] = grid_from_cols(
        [[ctx[-1] + 10.0] * horizon for _ in QUANTILES])
    report, fails = score(fixtures, junk, horizon)
    assert any("worse than seasonal-naive" in f for f in fails), fails
    assert 0.0 <= report["per_series"][walk_name]["picp80"] <= 1.0

    # 5. Constant series: MASE denominator zero is reported as null, not a crash.
    report, fails = score(fixtures, base, horizon)
    assert report["per_series"]["06-constant"]["mase_vs_seasonal_naive"] is None
    return True


def _qinv(tau):
    """Coarse inverse normal CDF, stdlib-only (good to ~0.01 for the selftest oracle)."""
    if tau == 0.5:
        return 0.0
    lo, hi = -8.0, 8.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if _cdf(mid) < tau:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--fixtures", help="fixtures JSON from tools/forecast-fixtures.py")
    p.add_argument("--preds", help="predictions JSON (21-quantile grids per series)")
    p.add_argument("--horizon", type=int, default=None, help="default: fixtures' horizon")
    p.add_argument("--emit-baseline", action="store_true",
                   help="write the seasonal-naive baseline prediction JSON and exit")
    p.add_argument("-o", "--out", default="-", help="output path for --emit-baseline or the report")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args(argv)

    if args.selftest:
        selftest()
        print("selftest OK")
        return 0
    if not args.fixtures:
        p.error("--fixtures is required (or --selftest)")

    with open(args.fixtures) as f:
        fixtures = json.load(f)
    horizon = args.horizon or fixtures["meta"]["horizon"]

    if args.emit_baseline:
        doc = json.dumps(emit_baseline(fixtures, horizon), indent=1)
        if args.out == "-":
            print(doc)
        else:
            with open(args.out, "w") as f:
                f.write(doc + "\n")
        return 0

    if not args.preds:
        p.error("--preds is required (or --emit-baseline / --selftest)")
    with open(args.preds) as f:
        preds = json.load(f)
    report, fails = score(fixtures, preds, horizon)
    report["hard_fails"] = fails
    text = json.dumps(report, indent=1, sort_keys=False)
    if args.out == "-":
        print(text)
    else:
        with open(args.out, "w") as f:
            f.write(text + "\n")
    return 3 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
