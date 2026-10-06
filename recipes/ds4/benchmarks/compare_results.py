#!/usr/bin/env python3
"""Aggregate per-model benchmark JSONs into a comparison table + markdown report.

Reads `results/<model>.<bench>.<thinking>.json` produced by run_benchmarks.py and
emits:
  * results/summary.json  -- machine-readable comparison
  * results/SUMMARY.md    -- the human table (same numbers, cited in the README)

It also does reply-level diffing between two models on the same bench, because
"same base model, different precision" means any *systematic* reply difference is
the quantisation (or the speculative-decoding config), not sampling noise at
temperature 0.  A score that ties but hides divergent reasoning is worth seeing.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")

BENCH_LABEL = {"house": "house battery", "gsm8k": "GSM8K (0-shot)", "arc": "ARC-Challenge (0-shot)"}


def load_all(thinking):
    out = {}
    for path in glob.glob(os.path.join(RESULTS, f"*.{thinking}.json")):
        name = os.path.basename(path)[: -len(f".{thinking}.json")]
        model, bench = name.split(".", 1)
        out.setdefault(model, {})[bench] = json.load(open(path))
    return out


def diff_replies(a, b, bench):
    """Return (identical, differing, only_one) task-id lists for two models."""
    ai = {it["id"]: it for it in a.get(bench, {}).get("items", [])}
    bi = {it["id"]: it for it in b.get(bench, {}).get("items", [])}
    same, diff, only = [], [], []
    for tid in sorted(set(ai) | set(bi)):
        if tid not in ai or tid not in bi:
            only.append(tid)
            continue
        ra = (ai[tid]["reply"] or "").strip()
        rb = (bi[tid]["reply"] or "").strip()
        if ra == rb:
            same.append(tid)
        else:
            diff.append(tid)
    return same, diff, only


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--thinking", default="off")
    ap.add_argument("--models", nargs="+", default=["deepseek", "deepseek-turbo"])
    a = ap.parse_args()
    data = load_all(a.thinking)
    models = [m for m in a.models if m in data]
    benches = sorted({b for m in models for b in data[m]})

    summary = {"thinking": a.thinking, "models": models, "results": {}, "diffs": {}}
    for m in models:
        summary["results"][m] = {}
        for b in benches:
            r = data[m].get(b)
            if not r:
                continue
            summary["results"][m][b] = {
                "n": r["n"], "correct": r["correct"], "pct": r["pct"],
                "errors": r.get("errors", 0), "by_category": r.get("by_category", {}),
            }
    if len(models) == 2:
        for b in benches:
            same, diff, only = diff_replies(data[models[0]], data[models[1]], b)
            summary["diffs"][b] = {"identical": len(same), "differing": len(diff),
                                   "one_sided": len(only), "differing_ids": diff + only}

    json.dump(summary, open(os.path.join(RESULTS, "summary.json"), "w"), indent=1)

    # markdown
    lines = [f"# DeepSeek quality comparison — thinking={a.thinking}", "",
             f"Endpoint: `http://spark-head.internal.littlecedar.net:4000/v1`", ""]
    lines.append("## Scores")
    lines.append("")
    header = "| benchmark | " + " | ".join(models) + " | delta |"
    sep = "|:--|" + "--:|" * len(models) + "--:|"
    lines += [header, sep]
    for b in benches:
        cells, vals = [], []
        for m in models:
            r = summary["results"][m].get(b)
            if r:
                cells.append(f"{r['correct']}/{r['n']} = {r['pct']:.1f}%")
                vals.append(r["pct"])
            else:
                cells.append("—")
                vals.append(None)
        delta = f"{vals[1]-vals[0]:+.1f} pp" if None not in vals else "—"
        lines.append(f"| {BENCH_LABEL.get(b, b)} | " + " | ".join(cells) + f" | {delta} |")
    lines.append("")
    if summary["diffs"]:
        lines.append("## Reply-level divergence (temperature 0)")
        lines.append("")
        lines.append("| benchmark | identical | differing | one-sided |")
        lines.append("|:--|--:|--:|--:|")
        for b in benches:
            d = summary["diffs"][b]
            lines.append(f"| {BENCH_LABEL.get(b, b)} | {d['identical']} | {d['differing']} | {d['one_sided']} |")
        lines.append("")
    open(os.path.join(RESULTS, "SUMMARY.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())