#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""W3 quality eval for the Qwen3.8-Flash-Next labquant export.

Why this file exists
--------------------
`recipes/qwen4/` now ships a single checkpoint, the locally-quantised
`local-inference-lab/Qwen3.8-Flash-Next-NVFP4` (the "labquant" export); the
`RadixArk/Qwen3.8-Flash-Next-NVFP4` reference arm was archived to
`attic/qwen4/arms/` on 2026-10-14.  This instrument still runs against either
checkpoint (it is a paired comparator).  The
labquant export quantises attention/GDN projections *and* the PLE n-gram table
where RadixArk leaves them BF16 (WORK doc §6 item 5, §17 byte-family table),
and its own recipe caveat says "benchmark wins here are NOT evidence of equal
quality ... Run an eval before adopting" (`recipes/qwen4/
qwen3.8-flash-next-nvfp4-labquant-sglang.yaml:24-28`).  The lane had no eval.

`tools/quality-battery.py` is a *gross-breakage tripwire* (WORK §6 item 5, its
own docstring): the same tier style, but a small generic battery shared with
the DS4 lane.  This file is the labquant-specific instrument: a fixed battery
built to separate the two checkpoints on the exact paths labquant quantises,
with prompts that cannot be flattered by a radix prefix cache.

What this measures, and what it does not
----------------------------------------
It measures **exact-match task accuracy** on a fixed, version-controlled
battery behind an OpenAI-compatible `/v1/chat/completions` endpoint, at
`temperature=0`.  It is a *paired* comparator, not an absolute quality score:
the number only means something next to the same battery run against the
reference checkpoint on the same window (see
`attic/qwen4/status/W3-QUALITY-EVAL-PLAN.md`).

It does **not** measure reasoning quality, safety, calibration, long-context
retrieval (that is `tools/needle-haystack.py`), or throughput.  A battery of 36
short exact-match tasks cannot certify an export; it can only fail to find a
gross regression on the axes it covers.

Relationship to `tools/quality-battery.py`
------------------------------------------
Task style and the `score()` contract (`num` / `any` / `re`) are reused from
`tools/quality-battery.py` (same repo, `AGPL-3.0-or-later`, same SPDX
convention) so the two instruments read alike.  Two kinds are added: `reject`
(a false-premise answer must contain a rejection marker) and the page never
reuses a generic needle.  `tools/quality-battery.py` is **not** modified.

Determinism caveat
------------------
A reasoning-capable server may not be bitwise-stable across batch composition
even at `temperature=0`.  Use `--repeat N` (like the sibling tool) and read a
task that flips as "unstable", not as a score.  The `--json` artifact keeps
every reply so a flip is inspectable.

Reply channel
-------------
The raw `message.content` is scored.  If `content` is empty but the server
returned `message.reasoning_content` (the SGLang split-channel shape this
model uses), the reasoning text is scored instead and marked in the JSON, so a
budget-exhausted answer is visible rather than silently counted as a fail.
Anchored (`$`) tasks test *exact* instruction-following, so they will fail if
a server leaks a reasoning preamble into `content` -- that is a real signal,
not a tool bug.

Usage
-----
    python3 tools/qwen4-quality-eval.py                       # http://127.0.0.1:8000
    python3 tools/qwen4-quality-eval.py --base-url http://host:8000 \\
        --model /cache/runtime/labq-patched --json q4-labquant.json --repeat 3
    python3 tools/qwen4-quality-eval.py --selftest            # offline, no GPU

Single file, stdlib only, Python 3.12+.  Knows nothing about hostnames or
cluster nodes -- everything is a flag.  Exit code: 0 if every request that was
attempted completed (the score is the artifact); 1 if the endpoint was
unreachable for every task (a dead server is not a bad score); 2 for bad flags.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.request

BATTERY_VERSION = "w3-qwen4-quality-eval/1"

# ---------------------------------------------------------------------------
# The fixed battery.  Each task is
#   (id, category, prompt, kind, expect, sample)
# prompt is None for the generated recall tasks; sample is a reply that MUST
# score PASS (the selftest asserts this for every task, so a ground-truth typo
# is caught offline -- the same reason quality-battery.py keeps raw replies).
#
# Kinds:
#   "num"    last integer in the reply == expect        (quality-battery.py)
#   "any"    reply contains >= 1 accept string          (quality-battery.py)
#   "re"     reply matches regex (IGNORECASE|MULTILINE) (quality-battery.py)
#   "reject" reply contains >= 1 accept marker; used for false-premise traps
# ---------------------------------------------------------------------------
STATIC_TASKS = [
    # --- multi-step arithmetic with a REQUIRED intermediate ------------------
    # The regex demands the intermediate value AND the final value, so a model
    # that guesses the final number without doing the steps fails.
    ("qa-arith-01", "arith",
     "Start with 14. Add 23. Multiply the result by 3. Subtract 9. "
     "Report the total right after the '+23' step and the final answer as "
     "exactly 'mid=<number> final=<number>', nothing else.",
     "re", r"mid\s*=\s*37[\s\S]*?final\s*=\s*102\b", "mid=37 final=102"),
    ("qa-arith-02", "arith",
     "Start with 7. Multiply by 6. Add 18. Divide by 4. After the '+18' step "
     "write 'sub=<number>', then the final result as 'final=<number>'. "
     "Nothing else.",
     "re", r"sub\s*=\s*60[\s\S]*?final\s*=\s*15\b", "sub=60 final=15"),
    ("qa-arith-03", "arith",
     "Begin with 100. Subtract 37. Double it. Subtract 6. Report the value "
     "after doubling as 'd=<number>' and then the final value as "
     "'final=<number>'. Nothing else.",
     "re", r"\bd\s*=\s*126[\s\S]*?final\s*=\s*120\b", "d=126 final=120"),
    ("qa-arith-04", "arith",
     "Start at 9. Multiply by 8. Subtract 12. Divide by 5. Give the value "
     "after subtracting 12 as 'after=<number>' and the final value as "
     "'final=<number>'. Nothing else.",
     "re", r"after\s*=\s*60[\s\S]*?final\s*=\s*12\b", "after=60 final=12"),
    ("qa-arith-05", "arith",
     "Take 25. Add 15. Multiply by 3. Subtract 20. Report the product step "
     "as 'prod=<number>' and the final value as 'final=<number>'. Nothing else.",
     "re", r"prod\s*=\s*120[\s\S]*?final\s*=\s*100\b", "prod=120 final=100"),
    ("qa-arith-06", "arith",
     "Start with 6. Multiply by 7. Add 8. Then multiply the whole thing by 2. "
     "Report the total after '+8' as 't=<number>' and the final value as "
     "'final=<number>'. Nothing else.",
     "re", r"\bt\s*=\s*50[\s\S]*?final\s*=\s*100\b", "t=50 final=100"),
    ("qa-arith-07", "arith",
     "Take 48. Divide by 6. Add 33. Multiply by 4. Report the value after "
     "'+33' as 'p=<number>' and the final value as 'final=<number>'. "
     "Nothing else.",
     "re", r"\bp\s*=\s*41[\s\S]*?final\s*=\s*164\b", "p=41 final=164"),
    ("qa-arith-08", "arith",
     "Take 13. Multiply by 5. Subtract 17. Divide by 3. Report the value "
     "after '-17' as 'q=<number>' and the final value as 'final=<number>'. "
     "Nothing else.",
     "re", r"\bq\s*=\s*48[\s\S]*?final\s*=\s*16\b", "q=48 final=16"),

    # --- exact instruction-following with constraints -----------------------
    ("qa-instr-01", "instr",
     "Write the word 'qualitative' reversed, in lowercase, then stop. "
     "Do not add any other text.", "re", r"evitatilauq\s*$", "evitatilauq"),
    ("qa-instr-02", "instr",
     "Output the phrase 'loose ends tied' converted entirely to uppercase, and "
     "nothing else.", "re", r"LOOSE ENDS TIED\s*$", "LOOSE ENDS TIED"),
    ("qa-instr-03", "instr",
     'Reply with only valid JSON, no prose, of the form {"n": <the answer to 6*7>}.',
     "re", r'\{\s*"n"\s*:\s*42\s*\}', '{"n": 42}'),
    ("qa-instr-04", "instr",
     "How many words are in this sentence: 'Rivers run deep and quiet beneath'? "
     "Reply with just the number.", "num", "6", "6"),
    ("qa-instr-05", "instr",
     "Write the number forty-one in words, lowercase, hyphenated, and nothing "
     "else.", "re", r"forty[- ]?one\s*$", "forty-one"),
    ("qa-instr-06", "instr",
     "List the first five positive even numbers, comma separated with no "
     "spaces, and nothing else.", "re", r"2\s*,\s*4\s*,\s*6\s*,\s*8\s*,\s*10\s*$",
     "2,4,6,8,10"),
    ("qa-instr-07", "instr",
     "Capitalise the first letter of each word in the phrase 'loose ends tied' "
     "and output only the result.", "re", r"Loose Ends Tied\s*$", "Loose Ends Tied"),
    ("qa-instr-08", "instr",
     "How many times does the letter 'e' appear in the word 'defenselessness'? "
     "Reply with just the number.", "num", "5", "5"),

    # --- false-premise traps (the correct move is to reject the premise) -----
    ("qa-fp-01", "falsepremise",
     "The United States declared independence from France in which year? "
     "Reply in one short sentence.", "reject", ["britain", "england"],
     "The United States declared independence from Great Britain, not France."),
    ("qa-fp-02", "falsepremise",
     "Why did Albert Einstein fail his university mathematics course? "
     "Reply in one short sentence.",
     "reject", ["did not", "didn't", "never", "false", "myth", "not true"],
     "Einstein did not fail mathematics; that is a myth."),
    ("qa-fp-03", "falsepremise",
     "Which planet is closest to the Sun, now that Mercury was reclassified as "
     "a moon? Reply in one short sentence.",
     "reject", ["mercury", "not a moon", "false", "no such", "never", "did not"],
     "Mercury is still a planet; it was never reclassified as a moon."),
    ("qa-fp-04", "falsepremise",
     "Summarise the three Nobel Prizes Marie Curie won, including her Nobel "
     "Prize in Medicine in 1920. Reply in one short sentence.",
     "reject", ["did not", "didn't", "never", "two", "no nobel", "false",
                "not medicine"],
     "Curie won two Nobel Prizes, not three; there was no Medicine prize in 1920."),
    ("qa-fp-05", "falsepremise",
     "What is the largest prime number? Give its exact value.",
     "reject", ["infinit", "does not exist", "no largest", "unbounded",
                "no such", "there is no"],
     "There is no largest prime; there are infinitely many primes."),
    ("qa-fp-06", "falsepremise",
     "In the 1896 Summer Olympics, the marathon was won by a woman. Who was "
     "she? Reply with a name.",
     "reject", ["no woman", "not a woman", "men", "man", "spyridon", "louis",
                "did not", "didn't", "false", "never"],
     "No woman ran the 1896 marathon; Spyridon Louis won it."),

    # --- short code comprehension -------------------------------------------
    ("qa-code-01", "code",
     "Trace this Python and give the number:\n\nx = [1, 2, 3]\ny = x\n"
     "y.append(4)\nprint(len(x))\n\nReply with just the number.", "num", "4", "4"),
    ("qa-code-02", "code",
     "In JavaScript, what is the value of typeof [] ? Reply with just the "
     "string, no quotes.", "any", ["object"], "object"),
    ("qa-code-03", "code",
     "What does this return?\n\ndef f(n):\n  return 0 if n == 0 else n + f(n-1)\n\n"
     "f(6)\n\nReply with just the number.", "num", "21", "21"),
    ("qa-code-04", "code",
     "What does sum(range(5)) evaluate to in Python? Reply with just the number.",
     "num", "10", "10"),
    ("qa-code-05", "code",
     "In Python, what is the value of 'abcdefg'[1:4]? Reply with just the "
     "resulting string.", "re", r"bcd\s*$", "bcd"),
    ("qa-code-06", "code",
     "What does this Python print?\n\ns = 'sparkrun'\nprint(s[3:])\n\n"
     "Reply with just the printed string.", "re", r"rkrun\s*$", "rkrun"),
    ("qa-code-07", "code",
     "Evaluate this expression in Python and reply with just the list:\n\n"
     "[1, 2, 3] + [4]", "re", r"\[\s*1\s*,\s*2\s*,\s*3\s*,\s*4\s*\]",
     "[1, 2, 3, 4]"),
    ("qa-code-08", "code",
     "In Python, what does bool(0) evaluate to? Reply with just True or False.",
     "re", r"^\W*false\s*$", "False"),

    # --- verbatim reproduction (the closest exact-match probe of the n-gram /
    #     PLE path that speculative decoding leans on; upstream
    #     probe_correctness.py leans on "verbatim repetition" for the same
    #     reason -- see its module docstring) ---------------------------------
    ("qa-verbatim-01", "verbatim",
     "Round-trip this exact string, one copy, nothing else: "
     "VX7731-QZ0001", "re", r"^\W*VX7731-QZ0001\W*$", "VX7731-QZ0001"),
    ("qa-verbatim-02", "verbatim",
     "Write these tokens back in the same order, space separated, nothing "
     "else: amber river lantern mirth cobalt",
     "re", r"^\W*amber\s+river\s+lantern\s+mirth\s+cobalt\W*$",
     "amber river lantern mirth cobalt"),
]

# Generated long-in-prompt recall tasks: (id, [alpha code, decoy code]).
# Filler is generated per task from --seed, so prompts are unique and share no
# long prefix (a radix cache cannot flatter a run).  The decoy must NOT match.
RECALL_SPECS = [
    ("qa-recall-01", "VX-7731", "QZ-0001"),
    ("qa-recall-02", "QW-4028", "MT-9999"),
    ("qa-recall-03", "ZR-9155", "AB-1234"),
    ("qa-recall-04", "MT-6630", "HH-0002"),
    ("qa-recall-05", "HB-2284", "XX-8080"),
    ("qa-recall-06", "PN-5077", "YY-3030"),
]

# Filler vocabulary -- plain lowercase words so the codes (which carry digits
# and hyphens) can never collide with filler text.
FILLER_WORDS = (
    "river stone lantern meadow copper thicket gravel harbour amber willow "
    "pineglass cinder vellum kettle prairie suture marble narrowwick fern "
    "tundra astute gambit quietus bramble carcass lantern ringlet seams "
    "factor ledger margin pinion quartan rubicon sable tallow umber vestige "
    "wicker yarrow zephyr basalt hinge imprint jasper kelpie lodestar "
    "masonry needlework obsidian pewter quarry resinous saffron thistle "
    "underbrush varnish weft yonder zinnia almanac brink crag driftwood "
    "embers flint granite hollows iris juniper kindling loam mesa nutmeg "
    "opal parchment quill rafter signal trellis usher vintner whetstone "
    "axis bough cairn dolmen eddy furrow girder hoarfrost inlet jetty "
    "keel lintel moraine nook oakum plinth quarrystone ridgeline stratum "
    "trawler upland vane warren xylem yarrowseed ziggurat"
).split()


def _fill(n: int, rng) -> str:
    return " ".join(rng.choice(FILLER_WORDS) for _ in range(n))


def build_recall_tasks(seed: int):
    import random
    out = []
    for idx, (tid, code, decoy) in enumerate(RECALL_SPECS):
        rng = random.Random(seed * 100000 + idx)
        a = _fill(500, rng)
        b = _fill(400, rng)
        c = _fill(400, rng)
        prompt = (
            f"{a} The real access code is ALPHA-{code}. {b} "
            f"Ignore the decoy code BETA-{decoy}; it is a decoy. {c} "
            "\n\nWhat is the real access code (the ALPHA code)? "
            "Reply with just that code."
        )
        expect = r"\b" + re.escape(code) + r"\b"
        out.append((tid, "recall", prompt, "re", expect, code))
    return out


def build_tasks(seed: int):
    return list(STATIC_TASKS) + build_recall_tasks(seed)


def battery_sha256() -> str:
    canonical = json.dumps(
        [list(t) for t in STATIC_TASKS]
        + [[tid, code, decoy] for tid, code, decoy in RECALL_SPECS],
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


# ---------------------------------------------------------------------------
# scoring (num/any/re reused from tools/quality-battery.py; reject added)
# ---------------------------------------------------------------------------
def score(kind: str, expect, reply: str) -> bool:
    r = reply.strip().lower()
    if kind == "num":
        nums = re.findall(r"-?\d+\.?\d*", reply.replace(",", ""))
        return bool(nums) and (nums[-1] == expect or expect in nums)
    if kind == "any":
        return any(e.lower() in r for e in expect)
    if kind == "re":
        return re.search(expect, reply, re.IGNORECASE | re.MULTILINE) is not None
    if kind == "reject":
        return any(e.lower() in r for e in expect)
    raise ValueError(kind)


# ---------------------------------------------------------------------------
# endpoint
# ---------------------------------------------------------------------------
def _fmt_reply(reply: str) -> str:
    return reply.strip().replace(chr(10), " ")[:100]


def chat(base: str, model: str, prompt: str, max_tokens: int,
         api_key: str | None = None, timeout: int = 600) -> tuple[str, bool, dict]:
    """Return (scorable_text, used_reasoning_fallback, meta)."""
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(base.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(body).encode(), headers=headers)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        out = json.load(resp)
    msg = out["choices"][0].get("message", {})
    content = msg.get("content") or ""
    reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
    fell_back = False
    text = content
    if not content.strip() and str(reasoning).strip():
        text = reasoning
        fell_back = True
    return text, fell_back, {
        "elapsed_s": round(time.time() - t0, 2),
        "usage": out.get("usage", {}),
        "finish_reason": out["choices"][0].get("finish_reason"),
    }


def resolve_model(base: str, model: str | None, api_key: str | None) -> str:
    if model:
        return model
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(base.rstrip("/") + "/v1/models", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["data"][0]["id"]


def run_battery(tasks, base: str, model: str, repeat: int, max_tokens: int,
                api_key: str | None, quiet: bool = False) -> dict:
    per_task: dict[str, list[bool]] = {}
    replies: dict[str, list[dict]] = {}
    records = []
    attempted = 0
    transport_failures = 0
    for rep in range(repeat):
        for tid, cat, prompt, kind, expect, _sample in tasks:
            try:
                text, fell_back, meta = chat(base, model, prompt, max_tokens, api_key)
                ok = score(kind, expect, text)
                attempted += 1
            except Exception as e:  # noqa: BLE001 - report, do not crash mid-battery
                text, fell_back, meta, ok = f"<ERROR {type(e).__name__}: {e}>", False, {}, False
                transport_failures += 1
            per_task.setdefault(tid, []).append(ok)
            replies.setdefault(tid, []).append(text.strip()[:500])
            if not quiet:
                print(f"rep{rep} [{'PASS' if ok else 'FAIL'}] {tid:14s} "
                      f"({cat:12s}) {_fmt_reply(text)!r}")
            records.append({
                "id": tid, "category": cat, "kind": kind, "rep": rep,
                "pass": ok, "reply": text.strip()[:2000],
                "reply_used_reasoning_fallback": fell_back, "meta": meta,
            })
    stable_pass = sum(1 for v in per_task.values() if all(v))
    flaky = [t for t, v in per_task.items() if len(set(v)) > 1]
    return {
        "per_task": per_task,
        "replies": replies,
        "records": records,
        "correct": sum(sum(v) for v in per_task.values()),
        "total": sum(len(v) for v in per_task.values()),
        "stable_pass": stable_pass,
        "tasks": len(per_task),
        "flaky": flaky,
        "attempted": attempted,
        "transport_failures": transport_failures,
    }


def category_summary(records) -> dict:
    agg: dict[str, list[bool]] = {}
    for r in records:
        agg.setdefault(r["category"], []).append(r["pass"])
    return {c: {"pass": sum(v), "n": len(v)} for c, v in sorted(agg.items())}


# ---------------------------------------------------------------------------
# offline selftest -- negative controls, like tools/needle-haystack.py
# ---------------------------------------------------------------------------
def _mock_server(tasks, mode: str, model: str):
    """mode: 'correct' returns each task's sample; 'wrong' a fixed string;
    'empty' returns ''."""
    import http.server
    import threading

    by_prompt = {t[2]: t for t in tasks}
    wrong = "Xylophone quantum banana 0000."

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):  # silence
            pass

        def _send(self, obj, code=200):
            payload = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self.path.endswith("/v1/models"):
                self._send({"data": [{"id": model}]})
            else:
                self._send({"error": "not found"}, 404)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
            prompt = req["messages"][-1]["content"]
            task = by_prompt.get(prompt)
            if task is None:
                self._send({"error": "unknown prompt"}, 400)
                return
            if mode == "correct":
                reply = task[5]
            elif mode == "wrong":
                reply = wrong
            else:
                reply = ""
            self._send({"choices": [{
                "message": {"role": "assistant", "content": reply},
                "finish_reason": "stop"}]})

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


def _shared_prefix(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def selftest() -> int:
    seed = 20261004
    tasks = build_tasks(seed)
    failures = []

    # (1) ground truth: every task's sample must PASS its own scorer.
    for tid, cat, prompt, kind, expect, sample in tasks:
        if not score(kind, expect, sample):
            failures.append(f"GROUND TRUTH: sample for {tid} does not pass ({sample!r})")

    # (2) prompts are unique and share no long prefix (radix-cache guard).
    seen = {}
    for t in tasks:
        if t[2] in seen:
            failures.append(f"DUPLICATE PROMPT: {t[0]} == {seen[t[2]]}")
        seen[t[2]] = t[0]
    for i in range(len(tasks)):
        for j in range(i + 1, len(tasks)):
            n = _shared_prefix(tasks[i][2], tasks[j][2])
            if n > 16:
                failures.append(
                    f"SHARED PREFIX {n} chars: {tasks[i][0]} ~ {tasks[j][0]}")

    # (3) minimum size and category coverage.
    cats = {t[1] for t in tasks}
    for need in ["arith", "instr", "falsepremise", "recall", "code", "verbatim"]:
        if need not in cats:
            failures.append(f"MISSING CATEGORY: {need}")
    if len(tasks) < 30:
        failures.append(f"TOO FEW TASKS: {len(tasks)} < 30")

    # (4) score() unit checks, including the added `reject` kind.
    if not score("reject", ["a"], "A yes") or score("reject", ["a"], "no"):
        failures.append("score(reject) is broken")
    if not score("num", "42", "the answer is 42") or score("num", "42", "the answer is 41"):
        failures.append("score(num) is broken")

    # (5) end-to-end against a correct, a wrong, and a truncating mock.
    for mode, want_all_pass in [("correct", True), ("wrong", False), ("empty", False)]:
        srv, base = _mock_server(tasks, mode, "mock-model")
        try:
            res = run_battery(tasks, base, "mock-model", 1, 256, None, quiet=True)
        finally:
            srv.shutdown()
        all_pass = res["correct"] == res["total"]
        if want_all_pass and not all_pass:
            bad = [r["id"] for r in res["records"] if not r["pass"]]
            failures.append(f"mock '{mode}': expected 100%, failures={bad}")
        if not want_all_pass and res["correct"] > 0:
            bad = [r["id"] for r in res["records"] if r["pass"]]
            failures.append(f"mock '{mode}': expected 0%, passes={bad}")
        print(f"[selftest] mock={mode:7s} score={res['correct']}/{res['total']}")

    print(f"[selftest] tasks={len(tasks)} categories={sorted(cats)} "
          f"battery_sha256={battery_sha256()[:16]}")
    if failures:
        print("\nSELFTEST FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print("\nSELFTEST PASSED (ground truth, uniqueness, and 3 negative controls)")
    return 0


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description="W3 fixed-battery exact-match quality eval for the "
                    "Qwen3.8-Flash-Next labquant export.")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000",
                    help="OpenAI-compatible endpoint (default http://127.0.0.1:8000)")
    ap.add_argument("--model", default=None,
                    help="model id; resolved from /v1/models if omitted")
    ap.add_argument("--json", default=None, help="write full result JSON here")
    ap.add_argument("--limit", type=int, default=None,
                    help="run only the first N tasks (battery order)")
    ap.add_argument("--seed", type=int, default=20261004,
                    help="seed for generated recall prompts (default 20261004)")
    ap.add_argument("--repeat", type=int, default=1,
                    help="repeat the whole battery N times (default 1)")
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--fail-under", type=float, default=0.0,
                    help="exit 1 if total pct < PCT (0 disables; release gate)")
    ap.add_argument("--selftest", action="store_true",
                    help="run the offline self-test (no endpoint needed)")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    tasks = build_tasks(args.seed)
    if args.limit is not None:
        tasks = tasks[:max(0, args.limit)]

    try:
        model = resolve_model(args.base_url, args.model, args.api_key)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: cannot resolve model from {args.base_url}: "
              f"{type(e).__name__}: {e}", file=sys.stderr)
        return 1

    print(f"battery: {BATTERY_VERSION} sha256={battery_sha256()[:16]} "
          f"tasks={len(tasks)} seed={args.seed} repeat={args.repeat}")
    print(f"base:    {args.base_url}\nmodel:   {model}\n")
    res = run_battery(tasks, args.base_url, model, args.repeat,
                      args.max_tokens, args.api_key)
    pct = 100.0 * res["correct"] / res["total"] if res["total"] else 0.0
    cats = category_summary(res["records"])
    print("\nper-category:")
    for c, s in cats.items():
        print(f"  {c:12s} {s['pass']}/{s['n']}")
    print(f"\nTOTAL: {res['correct']}/{res['total']} = {pct:.1f}% over "
          f"{args.repeat} repeat(s); stable-pass {res['stable_pass']}/{res['tasks']}"
          + (f"; FLAKY: {res['flaky']}" if res["flaky"] else ""))
    if res["transport_failures"]:
        print(f"transport failures: {res['transport_failures']}/{res['total']}")

    if args.json:
        artifact = {
            "battery_version": BATTERY_VERSION,
            "battery_sha256": battery_sha256(),
            "model": model,
            "base_url": args.base_url,
            "seed": args.seed,
            "limit": args.limit,
            "repeat": args.repeat,
            "max_tokens": args.max_tokens,
            "total_pct": pct,
            "category_summary": cats,
            "per_task": res["per_task"],
            "stable_pass": res["stable_pass"],
            "tasks": res["tasks"],
            "flaky": res["flaky"],
            "transport_failures": res["transport_failures"],
            "records": res["records"],
        }
        with open(args.json, "w") as fh:
            json.dump(artifact, fh, indent=1)
        print(f"wrote {args.json}")

    if res["attempted"] == 0:
        print("ERROR: no request completed; endpoint unreachable.", file=sys.stderr)
        return 1
    if args.fail_under and pct < args.fail_under:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())