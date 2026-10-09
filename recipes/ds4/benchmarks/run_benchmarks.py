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

`enable_thinking` is not universal.  The IFM K2-Horizon chat templates key
thinking on `reasoning_effort` (high|medium|low, default high) and contain no
`enable_thinking` at all, so `--thinking off` is *silently ignored* there.
`--reasoning-effort {default,high,medium,low}` is the additive knob for those
models: it merges `reasoning_effort` into the same `chat_template_kwargs`
*alongside* whatever `--thinking` set, and the default value `default` sends no
such key at all.  It is deliberately NOT a substitute for `--thinking` -- the
ds4 lane's models genuinely honour `enable_thinking` and that control is
load-bearing there, so `--thinking off` keeps emitting `enable_thinking: false`
exactly as it did before this flag existed.

Truncation is not a wrong answer
--------------------------------
A template that always opens a reasoning block spends its first tokens thinking,
so a cap too small to reach the visible answer records a truncation as a miss
(ARC's old `max_tokens=16` bought six words of thinking and nothing else: every
record came back `finish_reason: length`, empty content).  The base caps are
sized for that (house 1024, gsm8k 2048, arc 1024) and `--max-tokens-scale`
multiplies each of them, so a caller can re-size budgets without editing code.
Every summary records the `finish_reasons` histogram and `empty_replies` count,
which is how a truncation is told apart from a real answer, and every record
carries the effort it was run at so a `_raw/*.jsonl` resume is self-describing.

Usage
-----
    python3 run_benchmarks.py --base-url http://host:4000 --model deepseek \
        --bench all --thinking off --limit 200 --seed 1234 --outdir results

    # a reasoning_effort-keyed family (enable_thinking is a no-op there); with
    # no --thinking, the resolved default is to send reasoning_effort and NOT
    # enable_thinking:
    python3 run_benchmarks.py --base-url http://host:4000 --model k2 \
        --bench all --reasoning-effort low --max-tokens-scale 2 --limit 200
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
from collections import Counter

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
def chat(base, model, prompt, max_tokens, thinking, reasoning_effort="default"):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "temperature": 0, "max_tokens": max_tokens}
    # Both keys ride in the SAME chat_template_kwargs: --thinking and
    # --reasoning-effort are additive controls for different model families
    # (see the docstring), not alternatives.  Key order is irrelevant to the
    # server, but the no-new-flags path must stay byte-identical to the old
    # body, so a default effort adds no key here.
    kwargs = {"enable_thinking": thinking == "on"} if thinking in ("on", "off") else {}
    if reasoning_effort != "default":
        kwargs["reasoning_effort"] = reasoning_effort
    if kwargs:
        body["chat_template_kwargs"] = kwargs
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


def _cap(base, scale):
    """Scale a benchmark's base token cap.  Zero/negative would make every item
    a guaranteed truncation, so the floor is 1 rather than 0."""
    return max(1, int(round(base * scale)))


# Base caps are sized so a template that ALWAYS opens a reasoning block still
# reaches the visible answer inside the budget (see the docstring).  The old
# values (house 384, gsm8k 700, arc 16) predate the reasoning-block templates
# and silently scored truncation as a wrong answer.  --max-tokens-scale
# multiplies these without an edit here.
BASE_CAPS = {"house": 1024, "gsm8k": 2048, "arc": 1024}


def house_items(limit, scale=1.0):
    items = []
    for tier, tasks in (("easy", qb.EASY), ("hard", qb.HARD)):
        for tid, cat, prompt, kind, expect in tasks:
            if prompt is None:
                prompt = qb.make_needle()
            items.append({"id": f"{tier}/{tid}", "tier": tier, "category": cat,
                          "prompt": prompt,
                          "max_tokens": _cap(BASE_CAPS["house"], scale),
                          "_kind": kind, "_expect": expect})
    return items


def gsm8k_items(limit, seed, scale=1.0):
    rows = load_jsonl(os.path.join(DATA, "gsm8k_test.jsonl"))
    items = []
    for i, r in sample(rows, limit, seed):
        items.append({"id": f"gsm8k/{i}", "tier": "gsm8k", "category": "math",
                      "prompt": r["question"] + "\n\nShow your reasoning, then end with "
                      "'#### <final number>'.",
                      "max_tokens": _cap(BASE_CAPS["gsm8k"], scale), "_gold": r["gold"]})
    return items


def arc_items(limit, seed, scale=1.0):
    rows = load_jsonl(os.path.join(DATA, "arc_challenge_test.jsonl"))
    items = []
    for i, r in sample(rows, limit, seed):
        labels = r["labels"]
        opts = "\n".join(f"{lbl}. {txt}" for lbl, txt in zip(labels, r["choices"]))
        items.append({"id": f"arc/{i}", "tier": "arc", "category": "science",
                      "prompt": f"Question: {r['question']}\n\n{opts}\n\n"
                                "Answer with just the letter.",
                      "max_tokens": _cap(BASE_CAPS["arc"], scale), "_gold": r["gold"]})
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


BENCHES = {"house": lambda a: house_items(a.limit, a.max_tokens_scale),
           "gsm8k": lambda a: gsm8k_items(a.limit, a.seed, a.max_tokens_scale),
           "arc": lambda a: arc_items(a.limit, a.seed, a.max_tokens_scale)}


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
def slug_model(model):
    """Make a served model id safe as a single path segment.

    Model ids are not filenames: the IFM lanes serve ids like
    `IFM/K2-Horizon-0.9B`, and `os.path.join(outdir, f"{model}.{bench}...")` then
    points at a subdirectory that does not exist -- a fresh --outdir dies with
    FileNotFoundError before the first item is scored.  Replace every separator
    (and the Windows/alt separators) with '_' so ONE id maps to ONE stable name;
    the raw id is still what goes in the JSON payloads and on the wire.
    """
    return re.sub(r"[/\\]", "_", model)


def run_bench(a, bench, model):
    rawdir = os.path.join(a.outdir, "_raw")
    os.makedirs(rawdir, exist_ok=True)
    suffix = f".{a.tag}" if a.tag else ""
    # The requested effort is in the filename as well as the thinking tag: a
    # resume under a different effort must never read another effort's records.
    eff = "" if a.reasoning_effort == "default" else f".{a.reasoning_effort}"
    stem = f"{slug_model(model)}.{bench}.{a.thinking}{eff}{suffix}"
    raw = os.path.join(rawdir, stem + ".jsonl")
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
          f"effort={a.reasoning_effort} | {len(items)} items ({len(done)} cached) ===",
          flush=True)
    if done:
        print(f"    resuming, {len(done)} already recorded", flush=True)

    with open(raw, "a") as rawf:
        for item in items:
            if item["id"] in done:
                continue
            try:
                reply, meta = chat(a.base_url, model, item["prompt"],
                                   item["max_tokens"], a.thinking, a.reasoning_effort)
                ok = score_item(bench, item, reply)
                err = None
            except Exception as e:  # noqa: BLE001
                reply, meta, ok, err = f"<ERROR {type(e).__name__}: {e}>", {}, False, str(e)
            rec = {"id": item["id"], "tier": item["tier"], "category": item["category"],
                   "gold": item.get("_gold", item.get("_expect")), "reply": reply.strip()[:1500],
                   "correct": ok, "error": err,
                   # Per-record so a _raw resume is self-describing: the filename
                   # carries the effort too, but a record read in isolation (or
                   # copied beside another run's) must not need it.
                   "reasoning_effort": a.reasoning_effort, **meta}
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
    # finish_reasons + empty_replies are the truncation instrument: a cap too
    # small to reach the visible answer shows up here as "length" and "" before
    # it shows up as a wrong answer.
    finishes = Counter(str(r.get("finish_reason")) for r in recs)
    out = {"model": model, "bench": bench, "thinking": a.thinking, "n": n,
           "reasoning_effort": a.reasoning_effort,
           "correct": correct, "pct": 100.0 * correct / n if n else 0.0,
           "by_category": {c: {"n": len(v), "correct": sum(v)} for c, v in sorted(by_cat.items())},
           "errors": sum(1 for r in recs if r.get("error")),
           "finish_reasons": dict(finishes),
           "empty_replies": sum(1 for r in recs if not (r.get("reply") or "").strip()),
           "items": recs}
    dest = os.path.join(a.outdir, stem + ".json")
    json.dump(out, open(dest, "w"), indent=1)
    print(f"  => {bench}: {correct}/{n} = {out['pct']:.1f}%   "
          f"finish={dict(finishes)} empty={out['empty_replies']}   wrote {dest}", flush=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--bench", default="all",
                    choices=["house", "gsm8k", "arc", "all"])
    # Default is the sentinel None, NOT "off": the ds4 lane's primary config is
    # thinking off (enable_thinking: false) and must stay the on-wire default,
    # but a caller who passes only --reasoning-effort is targeting an
    # `reasoning_effort`-keyed family where enable_thinking is a no-op -- so the
    # resolved default depends on whether --thinking was actually stated (below).
    ap.add_argument("--thinking", default=None, choices=["off", "on", "default"],
                    help="forced thinking mode; default resolves to off unless "
                         "--reasoning-effort is given (then: neither key)")
    # Additive knob for families whose chat template keys thinking on
    # `reasoning_effort` and has no `enable_thinking` at all (see the docstring):
    # `default` sends no such key, so the flag is inert unless asked for.
    ap.add_argument("--reasoning-effort", default="default",
                    choices=["default", "high", "medium", "low"])
    # Multiplies each benchmark's base token cap (BASE_CAPS) so a caller can
    # size budgets without editing code.  1.0 is a no-op.
    ap.add_argument("--max-tokens-scale", type=float, default=1.0)
    ap.add_argument("--limit", type=int, default=200,
                    help="items per dataset benchmark (house is always full)")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--tag", default="", help="extra suffix for output files, e.g. run2")
    ap.add_argument("--outdir", default=os.path.join(HERE, "results"))
    a = ap.parse_args()

    # Back-compat resolution.  Both new flags are inert when unset, so a bare
    # invocation reproduces the old request body exactly (thinking off ->
    # enable_thinking: false, no reasoning_effort key).  The only behaviour that
    # moves is the --reasoning-effort-only case, which is the intent of the flag.
    if a.thinking is None:
        a.thinking = "default" if a.reasoning_effort != "default" else "off"

    benches = ["house", "gsm8k", "arc"] if a.bench == "all" else [a.bench]
    for b in benches:
        run_bench(a, b, a.model)
    return 0


if __name__ == "__main__":
    sys.exit(main())