#!/usr/bin/env python3
"""Quality benchmark runner for the ds4 endpoint comparison.

Compares two OpenAI-compatible chat endpoints serving the *same* base model at
different precisions -- `deepseek` (baseline) vs `deepseek-turbo` (EXL3 2.9bpw,
served by TensorFold) -- on held-out quality tasks.  Quality is a property of the
weights, so the interesting question is whether the ~2.9 bpw quantisation costs
accuracy on tasks we care about.  Speed is *not* the subject here; see the
recipe's performance lane for that.

Three instruments
-----------------
* house   -- `tools/quality-battery.py` verbatim (imported, so the easy/hard
             tiers are scored by exactly the same code as earlier ds4 runs).
             Small, exact-match; the `hard` tier is the informative one.
* gsm8k   -- 0-shot GSM8K, official test split, last-number-is-gold scoring.
             Comparable to the model card's 8-shot 93.0 EM (ours is 0-shot).
* arc     -- 0-shot ARC-Challenge, official 1172-row test split, letter match.

Everything is greedy (`temperature=0`) and stdlib-only.  A fixed `--seed` makes
the item sample reproducible; results are appended to `_raw/*.jsonl` after every
item so a interrupted run resumes instead of restarting.

Control for the thinking-default trap
-------------------------------------
The two deployments default to opposite thinking modes (baseline answers
immediately; turbo emits a hidden `reasoning_content` block).  A like-for-like
comparison therefore forces `chat_template_kwargs={"enable_thinking": false}` on
both (`--thinking off`, the default).  `--thinking on` exists only to diagnose
the divergence; it is not the headline config.

Usage
-----
    python3 run_benchmarks.py --base-url http://host:4000 --model deepseek \
        --bench all --thinking off --limit 200 --seed 1234 --outdir results
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
# The house battery lives at <repo>/tools/quality-battery.py.  Load it so the
# house tier's tasks AND scoring are literally the house code, not a copy.
# (Hyphenated filename -> load by path, not by module name.)
import importlib.util  # noqa: E402

_QB_PATH = os.path.abspath(os.path.join(HERE, "..", "..", "..", "tools", "quality-battery.py"))
_spec = importlib.util.spec_from_file_location("quality_battery", _QB_PATH)
qb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qb)

DATA = os.path.join(HERE, "data")


# --------------------------------------------------------------------------
# transport
# --------------------------------------------------------------------------
def chat(base, model, prompt, max_tokens, thinking):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "temperature": 0, "max_tokens": max_tokens}
    if thinking in ("on", "off"):
        body["chat_template_kwargs"] = {"enable_thinking": thinking == "on"}
    req = urllib.request.Request(base.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        out = json.load(r)
    msg = out["choices"][0]["message"]
    usage = out.get("usage", {}) or {}
    reason = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
    if reason is None:
        reason = usage.get("reasoning_tokens")  # SGLang reports it top-level
    return (msg.get("content") or ""), {
        "elapsed_s": round(time.time() - t0, 2),
        "completion_tokens": usage.get("completion_tokens"),
        "reasoning_tokens": reason,
        "finish_reason": out["choices"][0].get("finish_reason"),
        "tensorfold": out.get("tensorfold"),
    }


# --------------------------------------------------------------------------
# scorers
# --------------------------------------------------------------------------
def score_arc(reply, gold):
    """Return (correct, extracted_letter, how).  gold is a letter A-E."""
    s = reply.strip()
    m = re.fullmatch(r"\W*([A-Ea-e])\W*", s)
    if m:
        return m.group(1).upper() == gold.upper(), m.group(1).upper(), "whole"
    m = re.search(r"(?:answer|option|choice|correct)\D{0,12}?([A-E])\b", reply, re.IGNORECASE)
    if m:
        return m.group(1).upper() == gold.upper(), m.group(1).upper(), "phrase"
    m = re.search(r"\b([A-E])\b", reply)
    if m:
        return m.group(1).upper() == gold.upper(), m.group(1).upper(), "first"
    return False, None, "none"


# --------------------------------------------------------------------------
# item builders  ->  (id, prompt, max_tokens, scorer(reply)->bool)
# --------------------------------------------------------------------------
def load_jsonl(path):
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def sample(rows, limit, seed):
    if limit is None or limit >= len(rows):
        return list(enumerate(rows))
    idx = sorted(random.Random(seed).sample(range(len(rows)), limit))
    return [(i, rows[i]) for i in idx]


def house_items(limit):
    items = []
    for tier, tasks in (("easy", qb.EASY), ("hard", qb.HARD)):
        for tid, cat, prompt, kind, expect in tasks:
            if prompt is None:
                prompt = qb.make_needle()
            items.append({"id": f"{tier}/{tid}", "tier": tier, "category": cat,
                          "prompt": prompt, "max_tokens": 384,
                          "_kind": kind, "_expect": expect})
    return items


def gsm8k_items(limit, seed):
    rows = load_jsonl(os.path.join(DATA, "gsm8k_test.jsonl"))
    items = []
    for i, r in sample(rows, limit, seed):
        items.append({"id": f"gsm8k/{i}", "tier": "gsm8k", "category": "math",
                      "prompt": r["question"] + "\n\nShow your reasoning, then end with "
                      "'#### <final number>'.",
                      "max_tokens": 700, "_gold": r["gold"]})
    return items


def arc_items(limit, seed):
    rows = load_jsonl(os.path.join(DATA, "arc_challenge_test.jsonl"))
    items = []
    for i, r in sample(rows, limit, seed):
        labels = r["labels"]
        opts = "\n".join(f"{lbl}. {txt}" for lbl, txt in zip(labels, r["choices"]))
        items.append({"id": f"arc/{i}", "tier": "arc", "category": "science",
                      "prompt": f"Question: {r['question']}\n\n{opts}\n\n"
                                "Answer with just the letter.",
                      "max_tokens": 16, "_gold": r["gold"]})
    return items


def _trailing_number(s):
    """Last number in a string, commas stripped.  Handles 8, 8.00, -3.5, 1,234."""
    nums = re.findall(r"-?\d[\d,]*\.?\d*", s.replace(",", ""))
    return nums[-1] if nums else None


def score_gsm8k(reply, gold):
    """GSM8K: both models are asked to end with '#### <number>'.  Take the last
    number after the last #### and compare NUMERICALLY -- 8 and 8.00 are the same
    answer, and the naive string match wrongly fails one of them."""
    tail = reply.split("####")[-1]
    cand = _trailing_number(tail) or _trailing_number(reply)
    if cand is None:
        return False
    try:
        return abs(float(cand) - float(gold)) < 1e-6
    except ValueError:
        return False


BENCHES = {"house": lambda a: house_items(a.limit),
           "gsm8k": lambda a: gsm8k_items(a.limit, a.seed),
           "arc": lambda a: arc_items(a.limit, a.seed)}


def score_item(bench, item, reply):
    if bench == "house":
        return bool(qb.score(item["_kind"], item["_expect"], reply))
    if bench == "gsm8k":
        return score_gsm8k(reply, item["_gold"])
    if bench == "arc":
        return score_arc(reply, item["_gold"])[0]
    raise ValueError(bench)


# --------------------------------------------------------------------------
# run loop
# --------------------------------------------------------------------------
def run_bench(a, bench, model):
    rawdir = os.path.join(a.outdir, "_raw")
    os.makedirs(rawdir, exist_ok=True)
    suffix = f".{a.tag}" if a.tag else ""
    raw = os.path.join(rawdir, f"{model}.{bench}.{a.thinking}{suffix}.jsonl")
    done = {}
    if os.path.exists(raw):
        for line in open(raw):
            try:
                rec = json.loads(line)
                done[rec["id"]] = rec
            except Exception:
                pass
    items = BENCHES[bench](a)
    if not items:
        return None
    print(f"\n=== {bench} | model={model} | thinking={a.thinking} | "
          f"{len(items)} items ({len(done)} cached) ===", flush=True)
    if done:
        print(f"    resuming, {len(done)} already recorded", flush=True)

    with open(raw, "a") as rawf:
        for item in items:
            if item["id"] in done:
                continue
            try:
                reply, meta = chat(a.base_url, model, item["prompt"],
                                   item["max_tokens"], a.thinking)
                ok = score_item(bench, item, reply)
                err = None
            except Exception as e:  # noqa: BLE001
                reply, meta, ok, err = f"<ERROR {type(e).__name__}: {e}>", {}, False, str(e)
            rec = {"id": item["id"], "tier": item["tier"], "category": item["category"],
                   "gold": item.get("_gold", item.get("_expect")), "reply": reply.strip()[:1500],
                   "correct": ok, "error": err, **meta}
            done[item["id"]] = rec
            rawf.write(json.dumps(rec) + "\n")
            rawf.flush()
            mark = "PASS" if ok else "FAIL"
            rc = "" if meta.get("reasoning_tokens") in (None, 0) else f" rt={meta['reasoning_tokens']}"
            print(f"  [{mark}] {item['id']:14s} {reply.strip()[:70]!r}{rc}", flush=True)

    recs = [done[i["id"]] for i in items if i["id"] in done]
    n = len(recs)
    correct = sum(1 for r in recs if r["correct"])
    by_cat = {}
    for r in recs:
        by_cat.setdefault(r["category"], []).append(r["correct"])
    out = {"model": model, "bench": bench, "thinking": a.thinking, "n": n,
           "correct": correct, "pct": 100.0 * correct / n if n else 0.0,
           "by_category": {c: {"n": len(v), "correct": sum(v)} for c, v in sorted(by_cat.items())},
           "errors": sum(1 for r in recs if r.get("error")),
           "items": recs}
    tag = f".{a.tag}" if a.tag else ""
    dest = os.path.join(a.outdir, f"{model}.{bench}.{a.thinking}{tag}.json")
    json.dump(out, open(dest, "w"), indent=1)
    print(f"  => {bench}: {correct}/{n} = {out['pct']:.1f}%   wrote {dest}", flush=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--bench", default="all",
                    choices=["house", "gsm8k", "arc", "all"])
    ap.add_argument("--thinking", default="off", choices=["off", "on", "default"])
    ap.add_argument("--limit", type=int, default=200,
                    help="items per dataset benchmark (house is always full)")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--tag", default="", help="extra suffix for output files, e.g. run2")
    ap.add_argument("--outdir", default=os.path.join(HERE, "results"))
    a = ap.parse_args()

    benches = ["house", "gsm8k", "arc"] if a.bench == "all" else [a.bench]
    for b in benches:
        run_bench(a, b, a.model)
    return 0


if __name__ == "__main__":
    sys.exit(main())