#!/usr/bin/env python3
"""Combine two decision models' per-question distributions into one ensemble
and score it against each model alone on the shared Typed Decisions split.

Input is the ``### Full Trace`` section of a tool-eval-bench v2.8.0
``--decision-bench-only`` markdown report (the durable artifact of a decision
run): one block per case id, five question lines, each carrying the tool's own
``pred``/``gold`` labels, KL and Brier, followed by the predicted and gold
distributions.  clef-flash, Kai-0.6B and Sol-2B all emit this shape through
the tool's native ``/v1/systemone`` path; JEV-9B does NOT (its card contract
is ``/v1/completions``, one request per question, scored by
``tools/jev-decision-bench.py``) and its trace is not accepted here.

Ensemble rules:

* ``linear``  — equal-weight arithmetic mean of the two per-question
  distributions, renormalised.  The simplest honest pooler.
* ``loglinear`` — equal-weight geometric mean (log-linear pooling), the
  standard product-of-experts form; sharper than the mean when the models
  agree and better calibrated.

Accuracy is ``argmax(pooled) == gold label`` using the tool's own gold label,
so a model's alone-accuracy reproduced here matches the report exactly.
Significance of the ensemble-vs-alone accuracy delta is an exact two-sided
McNemar test over the paired per-question outcomes.

stdlib only.  ``--selftest`` runs a self-contained fixture and exits 0.

NOTE: ``tools/decision-ensemble.py`` imports ``linear`` / ``normalise`` / ``argmax`` from this
module, so the *served* clef+Kai ensemble and the *analysed* one are the same rule.  Changing
them here changes what the proxy answers — verify against the lane's receipts
(`recipes/decision/README.md` §"The clef + Kai ensemble") before changing them.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from math import comb

CASE_RE = re.compile(r"^(\S+_\d{6})\s+\{")
Q_RE = re.compile(
    r"^\s+(\w+) \((noul|choice|score)\)\s+([✓✗])\s+"
    r"pred\s+(\S+)\s+gold\s+(\S+)\s+KL\s+([\d.]+)\s+Brier\s+([\d.]+)"
)
PAIR_RE = re.compile(r"^\s+(pred|gold)\s+(.*)$")
KINDS = ("noul", "choice", "score")
EPS = 1e-12


def parse_report(path: str) -> dict:
    """Return {(case_id, question): record} for one TEB decision report."""
    out: dict[tuple[str, str], dict] = {}
    cid = None
    cur = None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if m := CASE_RE.match(line):
            cid = m.group(1)
            cur = None
            continue
        if cid is None:
            continue
        m = Q_RE.match(line)
        if m:
            cur = (cid, m.group(1))
            out[cur] = {
                "kind": m.group(2),
                "ok": m.group(3) == "✓",
                "plab": m.group(4),
                "glab": m.group(5),
                "kl": float(m.group(6)),
                "brier": float(m.group(7)),
                "pred": {},
                "gold": {},
            }
            continue
        m = PAIR_RE.match(line)
        if m and cur is not None:
            out[cur][m.group(1)] = {
                k: float(v) for k, v in (p.split("=") for p in m.group(2).split())
            }
    return out


def argmax(dist: dict[str, float]) -> str:
    return max(dist, key=lambda k: (dist[k], k))


def normalise(dist: dict[str, float]) -> dict[str, float]:
    s = sum(dist.values())
    return {k: v / s for k, v in dist.items()}


def linear(a: dict, b: dict) -> dict:
    keys = set(a) | set(b)
    return normalise({k: 0.5 * a.get(k, 0.0) + 0.5 * b.get(k, 0.0) for k in keys})


def loglinear(a: dict, b: dict) -> dict:
    keys = set(a) | set(b)
    z = {k: 0.5 * math.log(max(a.get(k, 0.0), EPS)) + 0.5 * math.log(max(b.get(k, 0.0), EPS)) for k in keys}
    m = max(z.values())
    return normalise({k: math.exp(v - m) for k, v in z.items()})


def kl(gold: dict, pred: dict) -> float:
    return sum(g * math.log(g / max(pred.get(k, 0.0), EPS)) for k, g in gold.items() if g > 0)


def brier(gold: dict, pred: dict) -> float:
    return sum((pred.get(k, 0.0) - gold.get(k, 0.0)) ** 2 for k in set(gold) | set(pred))


def score(records: list[dict], pool) -> dict:
    correct = 0
    kls, brs = [], []
    for r in records:
        p = pool(r)
        correct += argmax(p) == r["glab"]
        kls.append(kl(r["gold"], p))
        brs.append(brier(r["gold"], p))
    n = len(records)
    return {
        "accuracy_pct": 100.0 * correct / n,
        "correct": correct,
        "n": n,
        "kl_mean": sum(kls) / n,
        "brier_mean": sum(brs) / n,
    }


def mcnemar_p(records: list[dict], pool) -> tuple[int, int, float]:
    """(ensemble_fixes, ensemble_breaks, exact two-sided McNemar p) vs model A."""
    b = c = 0
    for r in records:
        alone = argmax(r["pred"]) == r["glab"]
        ens = argmax(pool(r)) == r["glab"]
        if alone and not ens:
            c += 1
        elif not alone and ens:
            b += 1
    n = b + c
    if n == 0:
        return b, c, 1.0
    k = min(b, c)
    p = 2.0 * sum(comb(n, i) for i in range(k + 1)) / (2 ** n)
    return b, c, min(p, 1.0)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report_a", nargs="?", help="markdown report for model A (the GPU arm)")
    ap.add_argument("report_b", nargs="?", help="markdown report for model B (the CPU arm)")
    ap.add_argument("--a-name", default="A")
    ap.add_argument("--b-name", default="B")
    ap.add_argument("--json", help="write the full result as JSON here")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not args.report_a or not args.report_b:
        ap.error("two report paths are required (or --selftest)")

    A = parse_report(args.report_a)
    B = parse_report(args.report_b)
    keys = sorted(set(A) & set(B))
    if not keys:
        print("no shared (case, question) keys between the two reports", file=sys.stderr)
        return 2
    # Paired records: A's gold/kind drive correctness (gold is identical in B).
    records = [
        {"key": k, "gold": A[k]["gold"], "pred": A[k]["pred"], "pred_b": B[k]["pred"],
         "glab": A[k]["glab"], "kind": A[k]["kind"]}
        for k in keys
    ]

    alone_a = score(records, lambda r: r["pred"])
    alone_b = score([{**r, "pred": r["pred_b"]} for r in records], lambda r: r["pred"])
    pool_lin = lambda r: linear(r["pred"], r["pred_b"])  # noqa: E731
    pool_geo = lambda r: loglinear(r["pred"], r["pred_b"])  # noqa: E731

    ens_lin = score(records, pool_lin)
    ens_geo = score(records, pool_geo)
    mb, mc, mp = mcnemar_p(records, pool_lin)
    gb, gc, gp = mcnemar_p(records, pool_geo)


    result = {
        "n_decisions": len(keys),
        "a_name": args.a_name,
        "b_name": args.b_name,
        "alone": {args.a_name: alone_a, args.b_name: alone_b},
        "ensemble_linear": {**ens_lin, "mcnemar_fixes": mb, "mcnemar_breaks": mc, "p": mp},
        "ensemble_loglinear": {**ens_geo, "mcnemar_fixes": gb, "mcnemar_breaks": gc, "p": gp},
        "per_kind": {},
    }
    for kind in KINDS:
        rs = [r for r in records if r["kind"] == kind]
        result["per_kind"][kind] = {
            "n": len(rs),
            args.a_name: score(rs, lambda r: r["pred"])["accuracy_pct"],
            args.b_name: score([{**r, "pred": r["pred_b"]} for r in rs], lambda r: r["pred"])["accuracy_pct"],
            "ensemble_linear": score(rs, pool_lin)["accuracy_pct"],
            "ensemble_loglinear": score(rs, pool_geo)["accuracy_pct"],
        }

    print(f"{args.a_name} alone     : {alone_a['accuracy_pct']:.1f}%  KL {alone_a['kl_mean']:.4f}  Brier {alone_a['brier_mean']:.4f}")
    print(f"{args.b_name} alone     : {alone_b['accuracy_pct']:.1f}%  KL {alone_b['kl_mean']:.4f}  Brier {alone_b['brier_mean']:.4f}")
    print(f"ensemble linear  : {ens_lin['accuracy_pct']:.1f}%  KL {ens_lin['kl_mean']:.4f}  Brier {ens_lin['brier_mean']:.4f}  "
          f"(McNemar vs {args.a_name}: +{mb}/-{mc}, p={mp:.4f})")
    print(f"ensemble loglin  : {ens_geo['accuracy_pct']:.1f}%  KL {ens_geo['kl_mean']:.4f}  Brier {ens_geo['brier_mean']:.4f}  "
          f"(McNemar vs {args.a_name}: +{gb}/-{gc}, p={gp:.4f})")
    print(f"{'kind':8s} {'n':>5s} {args.a_name:>8s} {args.b_name:>8s} {'lin':>6s} {'loglin':>7s}")
    for kind in KINDS:
        row = result["per_kind"][kind]
        print(f"{kind:8s} {row['n']:5d} {row[args.a_name]:7.1f}% {row[args.b_name]:7.1f}% {row['ensemble_linear']:5.1f}% {row['ensemble_loglinear']:6.1f}%")

    if args.json:
        json.dump(result, open(args.json, "w", encoding="utf-8"), indent=2)
        print(f"wrote {args.json}")
    return 0


def _render_case(cid: str, questions: list[tuple]) -> str:
    """Synthetic report block. questions = [(name, kind, glab, pred_dist, gold_dist, plab, kl, brier)]."""
    lines = [f"{cid}  {{}}"]
    for name, kind, glab, pred, gold, plab, k, b in questions:
        lines.append(f"  {name} ({kind})  {'✓' if plab == glab else '✗'}  pred {plab}  gold {glab}  KL {k:.3f}  Brier {b:.3f}")
        lines.append("      pred  " + " ".join(f"{x}={v:.3f}" for x, v in pred.items()))
        lines.append("      gold  " + " ".join(f"{x}={v:.3f}" for x, v in gold.items()))
    return "\n".join(lines)


def _selftest() -> int:
    import tempfile, os
    # Case 1: A right, B wrong -> ensemble must keep A right (both poolers).
    # Case 2: A wrong, B right -> linear mean of {1,0}/{0,1} is a tie; with a
    #         biased split the ensemble may recover B.  Assert the mechanics.
    a_q = [
        ("action", "choice", "keep", {"keep": 0.9, "stop": 0.1}, {"keep": 1.0, "stop": 0.0}, "keep", 0.02, 0.02),
        ("risk", "score", "0", {"0": 0.4, "1": 0.6}, {"0": 1.0, "1": 0.0}, "1", 0.3, 0.3),
    ]
    b_q = [
        ("action", "choice", "keep", {"keep": 0.3, "stop": 0.7}, {"keep": 1.0, "stop": 0.0}, "stop", 0.5, 0.5),
        ("risk", "score", "0", {"0": 0.9, "1": 0.1}, {"0": 1.0, "1": 0.0}, "0", 0.01, 0.01),
    ]
    ta = _render_case("wf_000001", a_q)
    tb = _render_case("wf_000001", b_q)
    with tempfile.TemporaryDirectory() as d:
        pa, pb = os.path.join(d, "a.md"), os.path.join(d, "b.md")

        open(pa, "w", encoding="utf-8").write(ta + "\n")
        open(pb, "w", encoding="utf-8").write(tb + "\n")
        A = parse_report(pa)
        B = parse_report(pb)
        assert len(A) == 2 and len(B) == 2, (len(A), len(B))
        assert A[("wf_000001", "action")]["glab"] == "keep"
        assert A[("wf_000001", "risk")]["pred"] == {"0": 0.4, "1": 0.6}
        # Alone accuracies: A 1/2, B 1/2.
        assert score([{"gold": A[k]["gold"], "pred": A[k]["pred"], "glab": A[k]["glab"]} for k in A], lambda r: r["pred"])["correct"] == 1
        # Ensemble must get BOTH right: choice->keep (0.6/0.4), score->0 (0.65/0.35).
        Bp = {k: B[k]["pred"] for k in A}
        ens = score([{"gold": A[k]["gold"], "pred": linear(A[k]["pred"], Bp[k]), "glab": A[k]["glab"]} for k in A],
                    lambda r: r["pred"])
        assert ens["correct"] == 2, ens
        # log-linear also recovers both.
        ensl = score([{"gold": A[k]["gold"], "pred": loglinear(A[k]["pred"], Bp[k]), "glab": A[k]["glab"]} for k in A],
                     lambda r: r["pred"])
        assert ensl["correct"] == 2, ensl
        # normalise / kl sanity
        assert abs(sum(normalise({"a": 1, "b": 3}).values()) - 1.0) < 1e-12
        assert kl({"a": 1.0}, {"a": 1.0}) < 1e-9
    print("selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
