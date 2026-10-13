#!/usr/bin/env python3
"""Score autotrust/JEV-9B on the Typed Decisions test split through the card's
native System 1 contract: one ``/v1/completions`` request per question with
``logprobs`` + ``allowed_token_ids`` over the ``jev-decision`` LoRA, scored
client-side with the decision-head bias and per-kind calibration temperature.

Metric semantics mirror tool-eval-bench v2.8.0's decision plugin exactly
(same data, same gold, same formulas) so the result is comparable with the
clef-flash run recorded in recipes/decision/README.md.  Two deliberate
differences, both recorded here and in the lane README:

- **One request per question** (JEV's native contract — the card's ``decide``
  scores one typed question per call), while TEB sends all five questions of a
  case in one ``/v1/systemone`` request.  Same 400 cases / 2000 decisions, so
  the headline score is comparable; per-request latency is not.
- **Structured states** serialize as sorted-key compact JSON
  (``json.dumps(state, sort_keys=True, separators=(",", ":"))``) — the
  vendor's SystemOne structured-state convention.  The JEV card itself
  documents only plain-string states.

Question rendering from a dataset row (fields verified against the vendored
split): ``kind`` is the wire ``type``; ``choice`` options are
``list(criteria.keys())`` in dataset order with ``A) …`` prompt lines;
``score`` options are ``"0".."N-1"`` over the criteria list; ``noul`` options
are ``["false", "true"]``.  The question text is ``instructions`` plus the
descriptive criteria content the wire carries (the card template's only
free-text slot).  Prediction = argmax with tie → first-listed, in
tool-eval-bench's key order (noul keyed ``true`` first, matching its
``answer_distribution``); request or parse errors count as misses and are
tallied.  Rating: ★ at or below the 47.0% dataset prior, ★★ above it, ★★★ at
or above the 73.5% teacher self-agreement.

Stdlib only.  ``--selftest`` is offline and exits 0.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request

# The vendored manifest's jsonl_sha256 (tool-eval-bench v2.8.0,
# tool_eval_bench/plugins/decision/vendor/typed_decisions/manifest.json).
CASES_SHA256 = "78a228c8be4244389a9977f8bafa8068cadac20ba8879c94116c963e0902831f"
EXPECTED_ROWS = 400
QUESTIONS_PER_CASE = 5
EXPECTED_DECISIONS = EXPECTED_ROWS * QUESTIONS_PER_CASE

KL_FLOOR = 1e-12
PRIOR_ACCURACY = 0.470
TEACHER_CEILING_ACCURACY = 0.735
LETTERS = "ABCDEFGHIJKLMNOP"
KINDS = ("noul", "choice", "score")

EXIT_OK = 0
EXIT_TRANSPORT = 1
EXIT_BAD_FLAGS = 2


class CaseIntegrityError(ValueError):
    """The case file is not the vendored Typed Decisions test split."""


# ---------------------------------------------------------------- metrics


def softmax(z: list[float]) -> list[float]:
    m = max(z)
    e = [math.exp(x - m) for x in z]
    s = sum(e)
    return [x / s for x in e]


def argmax_first(dist: dict[str, float]) -> str:
    """The most likely answer; a tie goes to the answer listed first."""
    return max(dist, key=lambda k: dist[k])


def kl_divergence(gold: dict[str, float], pred: dict[str, float]) -> float:
    """KL(gold ‖ pred) in nats, over the answers gold supports.

    Gold-zero answers contribute nothing; a predicted probability below the
    floor (or a missing answer) counts as the floor.  Same semantics as
    tool-eval-bench's decision plugin (its KL_FLOOR is 1e-12).
    """
    return sum(
        g * math.log(g / max(pred.get(k, 0.0), KL_FLOOR)) for k, g in gold.items() if g > 0
    )


def brier_score(gold: dict[str, float], pred: dict[str, float]) -> float:
    """Squared distance over the union of keys, in [0, 2]."""
    return sum((pred.get(k, 0.0) - gold.get(k, 0.0)) ** 2 for k in gold.keys() | pred.keys())


def expected_calibration_error(confidences: list[float], corrects: list[bool]) -> float:
    """Top-label ECE over 10 equal-width bins, count-weighted mean gap."""
    members: list[list[int]] = [[] for _ in range(10)]
    for i, conf in enumerate(confidences):
        members[min(int(conf * 10), 9)].append(i)
    total = len(confidences)
    if total == 0:
        return 0.0
    ece = 0.0
    for idx in members:
        if not idx:
            continue
        mean_conf = sum(confidences[i] for i in idx) / len(idx)
        acc = sum(corrects[i] for i in idx) / len(idx)
        ece += len(idx) * abs(acc - mean_conf)
    return ece / total


def rating(accuracy_pct: float) -> str:
    """tool-eval-bench's rating: ★ at/below the prior, ★★ above, ★★★ at the ceiling."""
    if accuracy_pct >= TEACHER_CEILING_ACCURACY * 100:
        return "★★★"
    if accuracy_pct > PRIOR_ACCURACY * 100:
        return "★★"
    return "★"


def percentile(values: list[float], q: float) -> float:
    """Linear-interpolated percentile, q in [0, 100]; 0 for no values."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * q / 100
    lo, hi = math.floor(rank), math.ceil(rank)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (rank - lo)


# ------------------------------------------------------------- case loading


def load_cases(path: str) -> list[dict]:
    """Load the vendored test.jsonl.gz, verifying its decompressed sha256.

    Fails closed on any hash or shape mismatch: an accidental edit to the file
    must not quietly change every score.
    """
    try:
        with open(path, "rb") as fh:
            raw = gzip.decompress(fh.read())
    except (OSError, gzip.BadGzipFile) as exc:
        raise CaseIntegrityError(f"cannot read {path}: {exc}") from exc
    digest = hashlib.sha256(raw).hexdigest()
    if digest != CASES_SHA256:
        raise CaseIntegrityError(
            f"{path}: decompressed sha256 {digest} does not match the vendored "
            f"manifest ({CASES_SHA256}) — refusing to score a modified split"
        )
    rows = []
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        problems = []
        if set(row.get("questions", {})) != set(row.get("gold", {})):
            problems.append("questions and gold keys differ")
        elif len(row.get("questions", {})) != QUESTIONS_PER_CASE:
            problems.append(f"{len(row.get('questions', {}))} questions, expected {QUESTIONS_PER_CASE}")
        else:
            for name, q in row["questions"].items():
                kind = q.get("type")
                if kind not in KINDS:
                    problems.append(f"{name}: unknown type {kind!r}")
                crit = q.get("criteria")
                if kind == "choice" and (not isinstance(crit, dict) or not crit):
                    problems.append(f"{name}: choice criteria is not a non-empty object")
                if kind == "score" and (not isinstance(crit, list) or not crit):
                    problems.append(f"{name}: score criteria is not a non-empty list")
                gold = row["gold"][name]
                if not isinstance(gold, dict) or "label" not in gold or "probabilities" not in gold:
                    problems.append(f"{name}: gold lacks label/probabilities")
        if problems:
            raise CaseIntegrityError(f"{row.get('id', '?')}: " + "; ".join(problems))
        rows.append(row)
    if len(rows) != EXPECTED_ROWS:
        raise CaseIntegrityError(f"{len(rows)} rows, expected {EXPECTED_ROWS}")
    if len({r["id"] for r in rows}) != len(rows):
        raise CaseIntegrityError("duplicate case ids")
    return rows


def state_to_text(state) -> str:
    """Plain-string states pass through; structured states serialize per SystemOne."""
    if isinstance(state, str):
        return state
    return json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def render_question(question: dict) -> tuple[str, str, list[str]]:
    """Return ``(kind, question_text, options)`` for one dataset question."""
    kind = question["type"]
    criteria = question.get("criteria")
    instructions = question["instructions"]
    if kind == "choice":
        options = list(criteria.keys())
        text = instructions + "\n" + "\n".join(f"{k}: {v}" for k, v in criteria.items())
    elif kind == "score":
        options = [str(i) for i in range(len(criteria))]
        text = instructions + "\n" + "\n".join(f"{i}: {d}" for i, d in enumerate(criteria))
    elif kind == "noul":
        options = ["false", "true"]
        text = instructions
        if criteria:
            text += f"\ntrue: {criteria.get('true', '')}\nfalse: {criteria.get('false', '')}"
    else:  # load_cases already rejects other kinds; kept for direct callers
        raise ValueError(f"unknown question type {kind!r}")
    return kind, text, options


def render_prompt(kind: str, state: str, question: str, options: list[str]) -> str:
    """The card's System 1 prompt template, verbatim."""
    if kind == "choice":
        lines = [f"{LETTERS[i]}) {o}" for i, o in enumerate(options)]
    else:
        lines = list(options)
    return (
        f"[kind] {kind}\n[state] {state}\n[question] {question}\n[options]\n"
        + "\n".join(lines)
        + "\n[decision]:"
    )


# ---------------------------------------------------------------- scoring


def head_slice(dh: dict, kind: str, n_options: int) -> tuple[list[int], list[float]]:
    """The verbalizer token ids and bias slice for the first n options of a kind."""
    s = dh["slots"]["ranges"][kind][0]
    return dh["verbalizer_ids"][s : s + n_options], dh["bias"][s : s + n_options]


def distribution_from_logprobs(
    lps: dict[int, float], ids: list[int], bias: list[float], temperature: float, options: list[str]
) -> dict[str, float]:
    """The card's scoring: z_i = (lp[t_i] + bias[s+i]) / T[kind], softmax."""
    z = [(lps.get(t, -1e9) + b) / temperature for t, b in zip(ids, bias)]
    probs = softmax(z)
    return {o: p for o, p in zip(options, probs)}


def parse_top_logprobs(top: dict) -> dict[int, float]:
    """Parse vLLM's ``token_id:NNN`` keys verbatim, as the card's code does."""
    return {int(k.split(":")[1]): v for k, v in top.items()}


def post_completion(base_url: str, model: str, prompt: str, ids: list[int], timeout: float) -> dict:
    body = {
        "model": model,
        "prompt": prompt,
        "max_tokens": 1,
        "temperature": 1.0,
        "logprobs": len(ids),
        "allowed_token_ids": ids,
        "add_special_tokens": False,
        "return_tokens_as_token_ids": True,
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/v1/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def decide(
    kind: str,
    state: str,
    question: str,
    options: list[str],
    base_url: str,
    model: str,
    dh: dict,
    temperatures: dict,
    timeout: float = 60.0,
) -> dict[str, float]:
    """One typed decision through the card's exact request + scoring recipe."""
    ids, _bias = head_slice(dh, kind, len(options))
    prompt = render_prompt(kind, state, question, options)
    reply = post_completion(base_url, model, prompt, ids, timeout)
    top = reply["choices"][0]["logprobs"]["top_logprobs"][0]
    lps = parse_top_logprobs(top)
    return distribution_from_logprobs(lps, ids, _bias, temperatures[kind], options)


# The tool-eval-bench key order for the scored distribution: noul is keyed
# ``true`` first (its answer_distribution builds {"true":…, "false":…}); choice
# and score keep dataset/numeric order.
def scored_distribution(kind: str, dist: dict[str, float]) -> dict[str, float]:
    if kind == "noul":
        return {"true": dist["true"], "false": dist["false"]}
    return dict(dist)


# ------------------------------------------------------------------- run


def summarize(records: list[dict]) -> dict:
    answered = [r for r in records if not r["is_error"]]
    correct = [r for r in answered if r["correct"]]
    n = len(records)
    acc = len(correct) / n * 100 if n else 0.0
    return {
        "total": n,
        "answered": len(answered),
        "errors": n - len(answered),
        "correct": len(correct),
        "accuracy_pct": acc,
        "mean_kl": sum(r["kl"] for r in answered) / len(answered) if answered else 0.0,
        "mean_brier": sum(r["brier"] for r in answered) / len(answered) if answered else 0.0,
        "rating": rating(acc),
    }


def run(args: argparse.Namespace) -> int:
    dh = json.load(open(os.path.expanduser(args.decision_head), encoding="utf-8"))
    calibration = json.load(open(os.path.expanduser(args.calibration), encoding="utf-8"))
    temperatures = calibration["per_kind"]
    rows = load_cases(args.cases)
    if args.limit is not None:
        rows = rows[: args.limit]
    total_decisions = len(rows) * QUESTIONS_PER_CASE
    print(
        f"[jev] {len(rows)} cases / {total_decisions} decisions, base {args.base_url}, "
        f"model {args.model}",
        flush=True,
    )

    records: list[dict] = []
    tokens_in = 0
    latencies: list[float] = []
    transport_failures = 0
    started = time.time()
    for ri, row in enumerate(rows):
        state = state_to_text(row["state"])
        for name, question in row["questions"].items():
            kind, text, options = render_question(question)
            ids, _bias = head_slice(dh, kind, len(options))
            prompt = render_prompt(kind, state, text, options)
            rec = {
                "id": row["id"],
                "workflow": row["workflow"],
                "question": name,
                "kind": kind,
                "is_error": False,
                "predicted": None,
                "gold": row["gold"][name]["label"],
                "correct": False,
                "confidence": 0.0,
                "kl": 0.0,
                "brier": 0.0,
                "latency_ms": 0.0,
            }
            t0 = time.time()
            try:
                reply = post_completion(args.base_url, args.model, prompt, ids, args.timeout)
                latency = (time.time() - t0) * 1000.0
                top = reply["choices"][0]["logprobs"]["top_logprobs"][0]
                lps = parse_top_logprobs(top)
                dist = distribution_from_logprobs(
                    lps, ids, _bias, temperatures[kind], options
                )
                tokens_in += int(reply.get("usage", {}).get("prompt_tokens", 0))
            except (urllib.error.URLError, OSError, KeyError, IndexError, ValueError) as exc:
                rec["is_error"] = True
                rec["error"] = f"{type(exc).__name__}: {exc}"
                rec["latency_ms"] = (time.time() - t0) * 1000.0
                transport_failures += 1
                records.append(rec)
                continue
            gold = row["gold"][name]
            sdist = scored_distribution(kind, dist)
            predicted = argmax_first(sdist)
            rec.update(
                predicted=predicted,
                correct=predicted == gold["label"],
                confidence=sdist[predicted],
                kl=kl_divergence(gold["probabilities"], sdist),
                brier=brier_score(gold["probabilities"], sdist),
                distribution=sdist,
                latency_ms=latency,
            )
            latencies.append(latency)
            records.append(rec)
        if (ri + 1) % 25 == 0 or ri + 1 == len(rows):
            done = len(records)
            ok = sum(1 for r in records if not r["is_error"] and r["correct"])
            print(
                f"[jev] case {ri + 1}/{len(rows)}  correct {ok}/{done}"
                f" ({ok / done * 100:.1f}%)" if done else "[jev] case 0",
                flush=True,
            )

    overall = summarize(records)
    elapsed = time.time() - started
    confs = [r["confidence"] for r in records if not r["is_error"]]
    cors = [r["correct"] for r in records if not r["is_error"]]
    overall["ece"] = expected_calibration_error(confs, cors)
    overall["latency_ms_mean"] = sum(latencies) / len(latencies) if latencies else 0.0
    overall["latency_ms_p50"] = percentile(latencies, 50)
    overall["input_tokens"] = tokens_in
    overall["duration_s"] = elapsed

    print(
        f"\nDecision Accuracy {overall['correct']}/{overall['total']} = "
        f"{overall['accuracy_pct']:.1f}%   {overall['rating']}",
    )
    print(
        f"KL(gold‖pred) mean {overall['mean_kl']:.4f} nats · Brier mean "
        f"{overall['mean_brier']:.4f} · ECE {overall['ece']:.4f} · "
        f"errors {overall['errors']}"
    )
    print(
        f"latency mean {overall['latency_ms_mean']:.0f} ms · p50 "
        f"{overall['latency_ms_p50']:.0f} ms · input tokens {tokens_in:,} · "
        f"{elapsed:.1f} s"
    )
    print("\nBy kind:")
    for kind in KINDS:
        s = summarize([r for r in records if r["kind"] == kind])
        print(
            f"  {kind:6s} {s['correct']}/{s['total']} = {s['accuracy_pct']:.1f}%"
            f"  KL {s['mean_kl']:.4f}  Brier {s['mean_brier']:.4f}  errors {s['errors']}"
        )
    print("By workflow:")
    for wf in sorted({r["workflow"] for r in records}):
        s = summarize([r for r in records if r["workflow"] == wf])
        print(
            f"  {wf:28s} {s['correct']}/{s['total']} = {s['accuracy_pct']:.1f}%"
            f"  KL {s['mean_kl']:.4f}  Brier {s['mean_brier']:.4f}"
        )

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "base_url": args.base_url,
                    "model": args.model,
                    "cases_file": args.cases,
                    "cases_sha256": CASES_SHA256,
                    "limit": args.limit,
                    "overall": overall,
                    "by_kind": {k: summarize([r for r in records if r["kind"] == k]) for k in KINDS},
                    "by_workflow": {
                        wf: summarize([r for r in records if r["workflow"] == wf])
                        for wf in sorted({r["workflow"] for r in records})
                    },
                    "records": records,
                },
                fh,
                indent=1,
            )
        print(f"[jev] receipt written to {args.json_out}")

    if transport_failures == total_decisions:
        return EXIT_TRANSPORT
    return EXIT_OK


# --------------------------------------------------------------- selftest


def _selftest() -> int:
    # 1. Golden prompt rendering — the card's template, byte-exact.
    kind, text, options = render_question(
        {
            "type": "choice",
            "instructions": "Supplier response for this scenario.",
            "criteria": {"issue_warning": "warn", "renegotiate": "talk", "maintain": "hold"},
        }
    )
    prompt = render_prompt(kind, "SKU AX-330 stock at 8% of safety level.", text, options)
    expected = (
        "[kind] choice\n"
        "[state] SKU AX-330 stock at 8% of safety level.\n"
        "[question] Supplier response for this scenario.\n"
        "issue_warning: warn\nrenegotiate: talk\nmaintain: hold\n"
        "[options]\nA) issue_warning\nB) renegotiate\nC) maintain\n"
        "[decision]:"
    )
    assert prompt == expected, f"choice prompt mismatch:\n{prompt}"

    kind, text, options = render_question(
        {
            "type": "noul",
            "instructions": "Is the customer asking for a refund?",
            "criteria": {"false": "No refund wanted.", "true": "Refund wanted."},
        }
    )
    prompt = render_prompt(kind, "Parcel arrived damaged.", text, options)
    assert prompt == (
        "[kind] noul\n[state] Parcel arrived damaged.\n"
        "[question] Is the customer asking for a refund?\n"
        "true: Refund wanted.\nfalse: No refund wanted.\n"
        "[options]\nfalse\ntrue\n[decision]:"
    ), prompt

    # Scored-distribution key order mirrors tool-eval-bench (noul: true first).
    sd = scored_distribution("noul", {"false": 0.3, "true": 0.7})
    assert list(sd) == ["true", "false"] and sd["true"] == 0.7

    # 2. Hand-computed bias/temperature softmax.
    # z = (lp + bias)/T: lp {5: 1.0, 6: 0.0}, bias [0.0, 2.0], T 2.0
    #   → z = [0.5, 1.0]; softmax = [e^0.5, e^1.0]/(e^0.5+e^1.0).
    e_half, e_one = math.exp(0.5), math.exp(1.0)
    dist = distribution_from_logprobs(
        {5: 1.0, 6: 0.0}, [5, 6], [0.0, 2.0], 2.0, ["a", "b"]
    )
    assert abs(dist["a"] - e_half / (e_half + e_one)) < 1e-12
    assert abs(dist["b"] - e_one / (e_half + e_one)) < 1e-12
    # A missing logprob scores -1e9 before bias/temperature: effectively 0 while
    # the present option keeps its mass (both missing would softmax uniformly).
    dist = distribution_from_logprobs({6: 0.0}, [5, 6], [0.0, 0.0], 1.0, ["a", "b"])
    assert dist["a"] < 1e-6 and abs(dist["a"] + dist["b"] - 1.0) < 1e-12
    # 3. Hand-computed accuracy / KL / Brier / ECE / rating.
    gold = {"a": 0.5, "b": 0.5}
    # Tie case: a 50/50 prediction argmaxes to the first-listed key.
    assert argmax_first(scored_distribution("noul", {"true": 0.5, "false": 0.5})) == "true"
    # Floor case: gold 0.5 on an answer predicted at 0 → 0.5·ln(0.5/1e-12) per side.
    zero = {"a": 0.0, "b": 0.0}
    expected_kl = math.log(0.5 / KL_FLOOR)
    assert abs(kl_divergence(gold, zero) - expected_kl) < 1e-9
    # Perfect prediction: KL 0, Brier 0.
    assert kl_divergence(gold, {"a": 0.5, "b": 0.5}) < 1e-12
    assert brier_score(gold, {"a": 0.5, "b": 0.5}) < 1e-12
    # Brier over the union: pred carries a key gold does not.
    assert abs(brier_score({"a": 1.0}, {"a": 0.5, "c": 0.5}) - (0.25 + 0.25)) < 1e-12
    # KL ignores gold-zero answers.
    assert kl_divergence({"a": 1.0, "b": 0.0}, {"a": 1.0}) < 1e-12
    # ECE by hand: two predictions, conf 0.9 correct, conf 0.15 wrong.
    # Bins: [0.9] → bin 9 (n=1, conf .9, acc 1, gap .1); [0.15] → bin 1 (n=1, gap .15).
    assert abs(expected_calibration_error([0.9, 0.15], [True, False]) - (0.1 + 0.15) / 2) < 1e-12
    assert rating(46.9) == "★" and rating(47.1) == "★★" and rating(73.5) == "★★★"

    print("selftest OK")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score JEV-9B on the Typed Decisions test split via the card's "
        "/v1/completions System 1 contract."
    )
    parser.add_argument("--base-url", help="e.g. http://10.0.4.34:8000")
    parser.add_argument("--model", default="jev-decision", help="served LoRA id (default jev-decision)")
    parser.add_argument("--cases", help="path to the vendored test.jsonl.gz")
    parser.add_argument(
        "--decision-head",
        default="~/benchmarks/jev-card/adapter_vllm/decision_head.json",
        help="decision_head.json with slots/verbalizer_ids/bias",
    )
    parser.add_argument(
        "--calibration",
        default="~/benchmarks/jev-card/calibration.json",
        help="calibration.json with per_kind temperatures",
    )
    parser.add_argument("--limit", type=int, default=None, help="score only the first N cases")
    parser.add_argument("--json", dest="json_out", help="write the full receipt as JSON here")
    parser.add_argument("--timeout", type=float, default=120.0, help="per-request timeout, seconds")
    parser.add_argument("--selftest", action="store_true", help="offline self-check, exit 0")
    args = parser.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not args.base_url or not args.cases:
        parser.error("--base-url and --cases are required")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    try:
        return run(args)
    except CaseIntegrityError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_BAD_FLAGS


if __name__ == "__main__":
    sys.exit(main())
