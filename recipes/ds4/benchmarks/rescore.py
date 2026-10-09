#!/usr/bin/env python3
"""Re-score stored benchmark replies without touching the endpoint again.

Scoring here is a *pure function of the recorded reply* plus the recorded gold,
and every reply run_benchmarks.py wrote to `results/_raw/*.jsonl` is kept.  So a
fix or a change to the scorer must be replayable: this tool rebuilds the item
list (same `--seed`/`--limit` as the run), re-applies the current scorer to each
stored reply, reports what changed, and rewrites `results/<model>.<bench>.<thinking>.json`.

It exists because the first GSM8K pass used the house numeric scorer, which
string-matched the value after `####`; a model that answered `#### 8.00` failed a
gold of `8`.  That is a harness bug, not a model difference.  Run this after any
scorer change; the numbers in the README come from the current scorer.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import types

import run_benchmarks as rb

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
RAW = os.path.join(RESULTS, "_raw")


def rebuild_items(bench, limit, seed):
    # max_tokens_scale is irrelevant to scoring (only the caps move), but
    # BENCHES reads it off the args object, so supply the no-op default.
    a = types.SimpleNamespace(limit=limit, seed=seed, max_tokens_scale=1.0)
    return {it["id"]: it for it in rb.BENCHES[bench](a)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1234)
    a = ap.parse_args()
    # house is always the full 37 items (limit ignored); gsm8k/arc are scored
    # straight from each record's stored reply + gold so a run with a different
    # sample size re-scores correctly.
    house_items = {it["id"]: it for it in rb.house_items(a.limit)}
    changed_total = 0
    for raw in sorted(glob.glob(os.path.join(RAW, "*.jsonl"))):
        base = os.path.basename(raw)[:-len(".jsonl")]
        model, bench, thinking = base.split(".", 2)
        if bench not in ("house", "gsm8k", "arc"):
            continue
        recs = [json.loads(l) for l in open(raw) if l.strip()]
        preceding = os.path.join(RESULTS, f"{base}.json")
        old = {}
        if os.path.exists(preceding):
            old = {r["id"]: r["correct"] for r in json.load(open(preceding))["items"]}
        flips = []
        for r in recs:
            if bench == "house":
                it = house_items.get(r["id"])
                new = bool(rb.qb.score(it["_kind"], it["_expect"], r["reply"])) if it else r["correct"]
            elif bench == "gsm8k":
                new = rb.score_gsm8k(r["reply"], r["gold"])
            else:
                new = rb.score_arc(r["reply"], r["gold"])[0]
            if old.get(r["id"]) is not None and old[r["id"]] != new:
                flips.append(r["id"])
            r["correct"] = new
        by_cat = {}
        for r in recs:
            by_cat.setdefault(r["category"], []).append(r["correct"])
        out = {"model": model, "bench": bench, "thinking": thinking, "n": len(recs),
               "correct": sum(1 for r in recs if r["correct"]),
               "pct": 100.0 * sum(1 for r in recs if r["correct"]) / len(recs) if recs else 0.0,
               "by_category": {c: {"n": len(v), "correct": sum(v)} for c, v in sorted(by_cat.items())},
               "errors": sum(1 for r in recs if r.get("error")), "items": recs}
        json.dump(out, open(preceding, "w"), indent=1)
        changed_total += len(flips)
        note = f"  (<- corrected {len(flips)}: {flips})" if flips else ""
        print(f"{base}: {out['correct']}/{out['n']} = {out['pct']:.1f}%{note}")
    print(f"\ntotal items whose correctness changed: {changed_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())