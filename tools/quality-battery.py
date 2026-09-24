#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Held-out quality battery for chat LLMs behind an OpenAI-compatible endpoint.

Why this file exists
--------------------
`sparkrun`'s benchmarking path (`benchmarking/*.yaml`, `framework: llama-benchy`
and `tool-eval-bench`) measures *speed*.  Nothing in it measures *quality*, and a
quantized checkpoint can lose quality without losing a single token/s.  For the
DeepSeek-V4.1-Flash EXL3 work the only published quality numbers were the
checkpoint author's own in-domain calibration rows, which cannot tell us whether
the quantization hurt the model on inputs we care about.  This is the missing
instrument: a small, deterministic, exact-match battery whose answers are printed
raw so a reviewer audits the score instead of trusting it.

Two tiers, on purpose
---------------------
`easy` (19) is a smoke test -- it proves a server answers, is not degenerate, and
handles arithmetic, retrieval and formatting at all.  It saturates (a competent
model scores 100 %), so it CANNOT rank quality; do not quote its number as one.
`hard` (18) is built to fail: multi-step arithmetic with a required intermediate,
exact constraint-following, false-premise traps, in-prompt recall with a
distractor, and longer code comprehension.  A non-perfect `hard` score is the
informative outcome.

Why it is not just `curl`
-------------------------
Every failure that matters here returns HTTP 200 with plausible text.  So the
scoring is exact-match / regex, `temperature` is pinned to 0, prompts are unique
(no shared prefix, so a radix cache cannot flatter the run), and the raw reply of
every task -- pass or fail -- is kept and printed.  Two of the ground-truth bugs
found while writing it were only caught *because* the raw answers were visible.

Determinism caveat
------------------
DeepSeek-V4.1 is documented as not bitwise-stable across batch composition, so a
task can differ run-to-run at `temperature 0`.  Run the battery more than once and
treat a task that flips as "unstable", not as a score.  The `--json` output keeps
every reply so the flip is inspectable.

Usage
-----
    python3 quality-battery.py <base_url> [--tier easy|hard|both] [--json out.json]
                               [--model NAME] [--repeat N]

Single file, stdlib only, Python 3.12+.  Knows nothing about hostnames or cluster
nodes -- everything is a flag.  Exit code is always 0; the score is the artifact.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request

# ---------------------------------------------------------------------------
# easy tier -- (id, category, prompt, kind, expect); prompt None => generated
#   kind "num": last integer in the reply must equal expect
#   kind "any": reply must contain at least one accept string (case-insensitive)
#   kind "re" : reply must match the regex, multiline + ignorecase
# ---------------------------------------------------------------------------
EASY = [
    ("arith-1", "arith", "What is 27 * 43? Reply with just the number.", "num", "1161"),
    ("arith-2", "arith", "What is 144 / 12? Reply with just the number.", "num", "12"),
    ("arith-3", "arith", "What is 17 + 28 - 9? Reply with just the number.", "num", "36"),
    ("arith-4", "arith", "What is 13 squared? Reply with just the number.", "num", "169"),
    ("arith-5", "arith", "What is 1000 - 337? Reply with just the number.", "num", "663"),
    ("wp-1", "word", "A shop sells pens at 3 for $2. How many dollars do 12 pens cost? Reply with just the number.", "num", "8"),
    ("wp-2", "word", "A train travels 60 km per hour for 2.5 hours. How many km does it go? Reply with just the number.", "num", "150"),
    ("wp-3", "word", "There are 4 boxes with 9 apples each. 5 apples are eaten. How many remain? Reply with just the number.", "num", "31"),
    ("reason-1", "reason", "If all Bloops are Razzies and all Razzies are Lazzies, are all Bloops definitely Lazzies? Answer yes or no.", "any", ["yes"]),
    ("reason-2", "reason", "A is taller than B. B is taller than C. Who is shortest? Answer with one letter.", "re", r"\bC\b"),
    ("fact-1", "fact", "What is the chemical symbol for gold? Reply with just the symbol.", "any", ["au"]),
    ("fact-2", "fact", "Which planet is closest to the Sun? Reply with just the name.", "any", ["mercury"]),
    ("fact-3", "fact", "Who wrote the play Romeo and Juliet? Reply with just the surname.", "any", ["shakespeare"]),
    ("fmt-1", "format", "List the numbers 1 to 5 separated by commas, nothing else.", "re", r"1\s*,\s*2\s*,\s*3\s*,\s*4\s*,\s*5"),
    ("fmt-2", "format", "Output exactly the word BANANA in uppercase and nothing else.", "re", r"^\W*BANANA\W*$"),
    ("code-1", "code", "In Python, what keyword defines a function? Reply with just the keyword.", "any", ["def"]),
    ("code-2", "code", "In Python, what does len([1,2,3]) evaluate to? Reply with just the number.", "num", "3"),
    ("code-3", "code", "What data structure does Python's dict represent? One word: mapping or sequence?", "any", ["mapping"]),
    ("needle-1", "needle", None, "any", ["zorbulon"]),
]

HARD = [
    ("hard-arith-1", "arith",
     "Start with 7. Multiply by 6. Subtract 5. Multiply that result by 2. "
     "What is the final number? Reply with just the number.", "num", "74"),
    ("hard-arith-2", "arith",
     "A shirt costs $18. It is discounted 25%, then 10% tax is added to the "
     "discounted price. What is the final price in dollars? Reply with just the number.",
     "num", "14.85"),
    ("hard-arith-3", "arith",
     "How many minutes are there in 2 days and 3 hours? Reply with just the number.",
     "num", "3060"),
    ("hard-count", "format",
     "How many words are in this sentence: 'the quick brown fox jumps over the lazy dog'? "
     "Reply with just the number.", "num", "9"),
    ("hard-rev", "format",
     "Write the word 'sparkrun' backwards. Reply with just that string.", "re", r"^\W*nurkraps\W*$"),
    ("hard-upper", "format",
     "Take the phrase 'hold the line' and make only the first letter of each word "
     "uppercase, keep the rest lowercase. Reply with just the result.",
     "re", r"^\W*Hold The Line\W*$"),
    ("hard-json", "format",
     "Reply with only valid JSON, no prose, of the form {\"a\": <the answer to 6*7>}. "
     "Nothing else.", "re", r'\{\s*"a"\s*:\s*42\s*\}'),
    ("trick-1", "reason",
     "Which weighs more: a kilogram of feathers or a kilogram of steel? "
     "Reply in one short sentence.", "any", ["same", "equal", "both weigh", "weigh the same"]),
    ("trick-2", "reason",
     "If it takes 5 machines 5 minutes to make 5 widgets, how long would 100 machines "
     "take to make 100 widgets (in minutes)? Reply with just the number.", "num", "5"),
    ("trick-3", "reason",
     "A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. "
     "How many cents does the ball cost? Reply with just the number.", "num", "5"),
    ("code-recall", "recall",
     "Remember the token QWX17. Now ignore the token ZZZ99. What was the FIRST token? "
     "Reply with just that token.", "re", r"QWX17"),
    ("order-1", "recall",
     "Here are three items: gamma, alpha, beta. Reply with them in alphabetical order, "
     "comma separated, lowercase.", "re", r"alpha\s*,\s*beta\s*,\s*gamma"),
    ("code-py", "code",
     "What does this Python print?\n\nx = [1, 2, 3]\ny = x\ny.append(4)\nprint(len(x))\n\n"
     "Reply with just the number.", "num", "4"),
    ("code-js", "code",
     "In JavaScript, what is the value of typeof [] ? Reply with just the string "
     "(no quotes).", "any", ["object"]),
    ("code-big", "code",
     "What does this return?\n\ndef f(n):\n  return 0 if n == 0 else n + f(n-1)\n\nf(10)\n\n"
     "Reply with just the number.", "num", "55"),
    ("frac-1", "arith",
     "What is 3/8 expressed as a decimal? Reply with just the number.", "num", "0.375"),
    ("big-1", "arith",
     "What is 123456789 + 987654321? Reply with just the number.", "num", "1111111110"),
    ("neg-1", "reason",
     "Do not answer 'yes'. Do not answer 'no'. Reply with the single word MAYBE.",
     "re", r"^\W*MAYBE\W*$"),
]

TIERS = {"easy": EASY, "hard": HARD}


def make_needle(n_words: int = 3000) -> str:
    words = [f"fluff{i}" for i in range(n_words)]
    words.insert(n_words // 2, "The secret access code is ZORBULON.")
    return (" ".join(words) + "\n\nWhat is the secret access code? Reply with just the code word.")


def chat(base: str, model: str, prompt: str, max_tokens: int = 384) -> tuple[str, dict]:
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "temperature": 0, "max_tokens": max_tokens}
    req = urllib.request.Request(base.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        out = json.load(r)
    txt = out["choices"][0]["message"]["content"] or ""
    return txt, {"elapsed_s": round(time.time() - t0, 2), "usage": out.get("usage", {})}


def score(kind: str, expect, reply: str) -> bool:
    r = reply.strip().lower()
    if kind == "num":
        nums = re.findall(r"-?\d+\.?\d*", reply.replace(",", ""))
        return bool(nums) and (nums[-1] == expect or expect in nums)
    if kind == "any":
        return any(e.lower() in r for e in expect)
    if kind == "re":
        return re.search(expect, reply, re.IGNORECASE | re.MULTILINE) is not None
    raise ValueError(kind)


def run_tier(name, tasks, base, model, repeat):
    per_task: dict[str, list[bool]] = {}
    replies: dict[str, list[str]] = {}
    for rep in range(repeat):
        for tid, cat, prompt, kind, expect in tasks:
            if prompt is None:
                prompt = make_needle()
            try:
                reply, meta = chat(base, model, prompt)
                ok = score(kind, expect, reply)
            except Exception as e:
                reply, meta, ok = f"<ERROR {type(e).__name__}: {e}>", {}, False
            per_task.setdefault(tid, []).append(ok)
            replies.setdefault(tid, []).append(reply.strip()[:500])
            print(f"[{name}] rep{rep} [{'PASS' if ok else 'FAIL'}] {tid:14s} ({cat:6s}) "
                  f"{reply.strip().replace(chr(10), ' ')[:80]!r}")
    stable_pass = sum(1 for v in per_task.values() if all(v))
    flaky = [t for t, v in per_task.items() if len(set(v)) > 1]
    total = len(per_task) * repeat
    correct = sum(sum(v) for v in per_task.values())
    print(f"\n{name.upper()}: {correct}/{total} = {100.0*correct/total:.1f}% "
          f"over {repeat} repeat(s); stable-pass {stable_pass}/{len(per_task)} tasks"
          + (f"; FLAKY: {flaky}" if flaky else ""))
    return {"tier": name, "correct": correct, "total": total,
            "pct": 100.0 * correct / total if total else 0.0,
            "stable_pass": stable_pass, "tasks": len(per_task), "flaky": flaky,
            "per_task": per_task, "replies": replies}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("base_url")
    ap.add_argument("--tier", default="both", choices=["easy", "hard", "both"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    model = args.model
    if not model:
        with urllib.request.urlopen(args.base_url.rstrip("/") + "/v1/models", timeout=30) as r:
            model = json.load(r)["data"][0]["id"]
    print(f"model: {model}\nbase:  {args.base_url}\ntier: {args.tier} repeats: {args.repeat}\n")

    names = ["easy", "hard"] if args.tier == "both" else [args.tier]
    out = {"model": model, "base_url": args.base_url, "tiers": {}}
    for n in names:
        out["tiers"][n] = run_tier(n, TIERS[n], args.base_url, model, args.repeat)
        print()
    if args.json:
        json.dump(out, open(args.json, "w"), indent=1)
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
