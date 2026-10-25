"""Guards for the forecast instrument (tools/forecast-fixtures.py, tools/forecast-bench.py).

Run:
    uv run python -B -m unittest tests.test_forecast_bench -v

Stdlib-only, like the rest of tests/ and tools/.  Both tools are dash-named, so they
are imported via importlib and registered in sys.modules before exec_module (the
house idiom).

What this guards
----------------
The Timestral item (`mad-science/TODO.md`) pre-registers falsifiers that this scorer
decides, so every decision path needs a control here, because a guard that has only
ever passed proves nothing:

  * the fixtures are byte-deterministic (regenerated, not remembered) and the NaN
    block sits inside the context, never inside the scored horizon;
  * a perfect Gaussian oracle scores ~the exact analytic CRPS on the random walk
    (the fixture the >25 %-above-card falsifier reads);
  * a *non-monotone* quantile grid is a hard fail -- the pre-registered invalidator;
  * the seasonal-naive baseline's degenerate grid scores exactly its own MAE and
    never trips the worse-than-baseline check against itself;
  * a garbage forecast DOES trip it (the check has a direction);
  * PICP stays in [0, 1] and the constant series reports MASE null instead of
    dividing by zero;
  * both CLIs' --selftest exit 0, and --emit-baseline round-trips through the
    scorer with zero hard fails.
"""

from __future__ import annotations

import importlib.util
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_PATH = REPO_ROOT / "tools" / "forecast-fixtures.py"
BENCH_PATH = REPO_ROOT / "tools" / "forecast-bench.py"


def load_tool(name, path):
    """Import a dash-named tool (importlib; register before exec_module)."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fixtures_tool = load_tool("forecast_fixtures_tool", FIXTURES_PATH)
bench_tool = load_tool("forecast_bench_tool", BENCH_PATH)

STEPS, HORIZON, SEED = 512, 96, 7
WALK = "01-gaussian-random-walk"


def small_fixtures():
    return fixtures_tool.build(STEPS, HORIZON, SEED)


def oracle_preds(fixtures):
    """The true random-walk law (N(x_T, h)) plus baseline grids for the other series."""
    base = bench_tool.emit_baseline(fixtures, HORIZON)
    walk = fixtures["series"][WALK]["values"]
    ctx = walk[:STEPS - HORIZON]
    cols = [[ctx[-1] + math.sqrt(h) * bench_tool._qinv(t) for h in range(1, HORIZON + 1)]
            for t in bench_tool.QUANTILES]
    preds = {"meta": {}, "predictions": dict(base["predictions"])}
    preds["predictions"][WALK] = {"quantiles": {str(t): list(c)
                                                for t, c in zip(bench_tool.QUANTILES, cols)}}
    return preds


class FixtureTests(unittest.TestCase):
    def test_byte_deterministic(self):
        a = fixtures_tool.canonical_bytes(small_fixtures())
        b = fixtures_tool.canonical_bytes(fixtures_tool.build(STEPS, HORIZON, SEED))
        self.assertEqual(a, b)

    def test_nan_block_inside_context_only(self):
        fx = fixtures_tool.build(fixtures_tool.DEFAULT_STEPS, HORIZON, SEED)
        s = fx["series"]["04-missing-block"]["values"]
        blk = s[fixtures_tool.MISSING_BLOCK_AT:
                fixtures_tool.MISSING_BLOCK_AT + fixtures_tool.MISSING_BLOCK_LEN]
        self.assertTrue(all(v is None for v in blk))
        self.assertIsNotNone(s[fixtures_tool.MISSING_BLOCK_AT - 1])
        plain = fx["series"]["02-trend-weekly-ar1"]["values"][-HORIZON:]
        self.assertEqual(s[-HORIZON:], plain, "NaN block leaked into the scored horizon")

    def test_constant_and_covariate(self):
        fx = small_fixtures()
        self.assertTrue(all(v == 5.0 for v in fx["series"]["06-constant"]["values"]))
        cov = fx["series"]["05-bivariate-covariate"]["covariate"]
        self.assertTrue(all(v in (0.0, 1.0) for v in cov[-HORIZON:]),
                        "covariate horizon must be known-future")


class ScorerTests(unittest.TestCase):
    def setUp(self):
        self.fixtures = small_fixtures()

    def score(self, preds):
        return bench_tool.score(self.fixtures, preds, HORIZON)

    def test_oracle_matches_analytic_crps(self):
        report, fails = self.score(oracle_preds(self.fixtures))
        self.assertEqual(fails, [])
        m = report["per_series"][WALK]
        self.assertLess(abs(m["crps"] - m["oracle_crps"]) / m["oracle_crps"], 0.15)

    def test_non_monotone_grid_is_a_hard_fail(self):
        preds = oracle_preds(self.fixtures)
        lvl = {k: list(v) for k, v in preds["predictions"][WALK]["quantiles"].items()}
        lvl["0.5"], lvl["0.55"] = lvl["0.55"], lvl["0.5"]
        preds["predictions"][WALK] = {"quantiles": lvl}
        _, fails = self.score(preds)
        self.assertTrue(any("not monotone" in f for f in fails))

    def test_baseline_scores_its_own_mae_and_never_fails(self):
        base = bench_tool.emit_baseline(self.fixtures, HORIZON)
        report, fails = self.score(base)
        self.assertEqual(fails, [])
        b = report["per_series"]["02-trend-weekly-ar1"]
        self.assertLess(abs(b["crps"] - b["seasonal_naive_mae"]), 1e-6)

    def test_garbage_forecast_trips_worse_than_baseline(self):
        preds = oracle_preds(self.fixtures)
        walk = self.fixtures["series"][WALK]["values"]
        junk = {"quantiles": {str(t): [walk[STEPS - HORIZON - 1] + 10.0] * HORIZON
                              for t in bench_tool.QUANTILES}}
        preds["predictions"][WALK] = junk
        _, fails = self.score(preds)
        self.assertTrue(any("worse than seasonal-naive" in f for f in fails))

    def test_picp_bounds_and_constant_mase_null(self):
        base = bench_tool.emit_baseline(self.fixtures, HORIZON)
        report, _ = self.score(base)
        picp = report["per_series"][WALK]["picp80"]
        self.assertGreaterEqual(picp, 0.0)
        self.assertLessEqual(picp, 1.0)
        self.assertIsNone(report["per_series"]["06-constant"]["mase_vs_seasonal_naive"])


class CliTests(unittest.TestCase):
    def run_tool(self, *args):
        return subprocess.run([sys.executable, "-B", *args], capture_output=True,
                              text=True, cwd=str(REPO_ROOT))

    def test_selftests_exit_zero(self):
        for tool in (FIXTURES_PATH, BENCH_PATH):
            r = self.run_tool(str(tool), "--selftest")
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_emit_baseline_round_trips_clean(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            fx = str(Path(d) / "fx.json")
            self.assertEqual(self.run_tool(str(FIXTURES_PATH), "--out", fx).returncode, 0)
            bp = str(Path(d) / "base.json")
            self.assertEqual(self.run_tool(str(BENCH_PATH), "--fixtures", fx,
                                           "--emit-baseline", "-o", bp).returncode, 0)
            rep = str(Path(d) / "report.json")
            r = self.run_tool(str(BENCH_PATH), "--fixtures", fx, "--preds", bp, "-o", rep)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            report = json.loads(Path(rep).read_text())
            self.assertEqual(report["hard_fails"], [])
            self.assertEqual(report["pooled"]["series"], 6)


if __name__ == "__main__":
    unittest.main()
