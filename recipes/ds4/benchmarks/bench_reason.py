#!/usr/bin/env python3
"""Hard reasoning / knowledge battery for the ds4 endpoint comparison.

Companion to `run_benchmarks.py` (easy/mid tier) and `bench_code.py` (execution
graded).  This is the *hard* generative tier: benchmarks whose published numbers
exist for the unquantized model, so a local run can be sanity-checked against
them.  It measures the same two endpoints -- `deepseek` (official weights) and
`deepseek-turbo` (EXL3 2.9 bpw) -- and asks the same question as the rest of this
directory: does the quantisation cost accuracy?

Benchmarks (all read from the staged JSONL in data/, no network at run time)
--------------------------------------------------------------------------
  hle        Humanity's Last Exam (text-only), short-answer + MCQ
  gpqa       GPQA Diamond, multiple-choice
  mmlu_pro   MMLU-Pro, 10-way multiple-choice
  math500    MATH-500, boxed final answer
  aime       AIME 2022-2024, integer final answer

Thinking configuration (IMPORTANT)
----------------------------------
The sizing probe (`_probe_size.py`) showed that on genuinely hard items this
endpoint, with thinking ON, streams hidden reasoning for the ENTIRE max_tokens
budget and returns `finish_reason: length` with EMPTY visible content -- for both
models (e.g. deepseek 16000 tok / 307 s / empty).  So the default and primary
config here is `--thinking off`: it is the only one that actually produces graded
answers on HLE-class prompts.  The config is recorded with every result.

Math grading
------------
MATH-500 and (partly) HLE need equivalence, not string equality.  When run under
the QA venv (`.venv-qa/bin/python`, which has `math_verify` + `sympy`) the harness
parses the model's `\\boxed{...}` and the gold and checks symbolic equivalence; it
falls back to a normalized string comparison if that fails or the libraries are
absent.  The grader actually used is recorded per item.

Usage
-----
    .venv-qa/bin/python bench_reason.py --base-url http://host:4000 \
        --model deepseek --bench all --thinking off [--limit N] [--only hle] ...
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
RESULTS = os.path.join(HERE, "results")

try:
    from math_verify import parse as mv_parse, verify as mv_verify  # type: ignore
    HAVE_MV = True
except Exception:  # noqa: BLE001
    HAVE_MV = False

# bench -> (file, prompt builder, max_tokens, grader)
DEFAULT_LIMIT = 0  # 0 = all items in the file


def load_jsonl(name):
    return [json.loads(l) for l in open(os.path.join(DATA, name), encoding="utf-8") if l.strip()]


def sample(rows, limit, seed):
    if not limit or limit >= len(rows):
        return list(rows)
    import random
    return [rows[i] for i in sorted(random.Random(seed).sample(range(len(rows)), limit))]


# --------------------------- prompts ---------------------------
def p_hle(r):
    return (r["question"] + "\n\nGive your final answer on the last line as "
            "\"Answer: <answer>\" (for a multiple-choice item, the letter only).")


def p_gpqa(r):
    return r["question"] + "\n\nEnd with your final answer as \"Answer: <letter>\"."


def p_mmlu(r):
    letters = "ABCDEFGHIJ"
    opts = "\n".join(f"{letters[i]}. {t}" for i, t in enumerate(r["options"]))
    return (r["question"] + "\n\n" + opts +
            "\n\nEnd with your final answer as \"Answer: <letter>\".")


def p_math(r):
    return r["question"] + "\n\nPut your final answer in \\boxed{}."


def p_aime(r):
    return r["question"] + "\n\nPut your final answer in \\boxed{}."


# --------------------------- extraction + grading ---------------------------
def last_boxed(text):
    i = text.rfind("\\boxed{")
    if i < 0:
        # allow \boxed without braces
        m = list(re.finditer(r"\\boxed\s*", text))
        if not m:
            return None
        return text[m[-1].end():].strip().splitlines()[0] if text[m[-1].end():].strip() else None
    j = i + len("\\boxed{")
    depth = 1
    k = j
    while k < len(text) and depth:
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
        k += 1
    return text[j:k-1]


def last_answer_line(text):
    m = list(re.finditer(r"answer\s*[:\-]\s*(.+)", text, re.IGNORECASE))
    if m:
        return m[-1].group(1).strip()
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    return lines[-1] if lines else ""


def norm_letter(s):
    if s is None:
        return None
    m = re.search(r"\b([A-J])\b", s.strip().upper())
    if m:
        return m.group(1)
    m = re.fullmatch(r"\(?([A-J])\)?[.\s]*", s.strip().upper())
    return m.group(1) if m else None


def latex_light(s):
    """Cheap LaTeX cleanup for the string fallback (math_verify does the real work)."""
    if s is None:
        return ""
    s = s.strip()
    for a in ("\\left", "\\right", "\\,", "\\!", "\\;", "\\ ", "$"):
        s = s.replace(a, "")
    s = re.sub(r"\\[dt]frac", r"\\frac", s)
    s = re.sub(r"\\frac\s*(\d)\s*(\d)", r"\\frac{\1}{\2}", s)   # \frac14 -> \frac{1}{4}
    s = re.sub(r"\\text\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\mbox\{([^}]*)\}", r"\1", s)
    return s.strip()


def norm_text(s):
    s = latex_light(s).lower()
    s = re.sub(r"^(the|a|an)\s+", "", s)
    s = s.strip().strip(".!?,;: \t\n\"'")
    return re.sub(r"\s+", " ", s)


def as_number(s):
    """Return a float if the string is a plain (possibly LaTeX-stripped) number."""
    if s is None:
        return None
    t = latex_light(s).replace(",", "").replace("$", "").strip()
    t = t.strip("()[] ")
    try:
        return float(t)
    except ValueError:
        return None


def grade_letter(reply, gold_letter):
    got = norm_letter(last_answer_line(reply)) or norm_letter(last_boxed(reply) or "")
    if got is None:
        got = norm_letter(reply[-40:])
    return got == norm_letter(gold_letter), got, "letter"


def grade_math(reply, gold):
    pred = last_boxed(reply)
    if pred is None:
        pred = last_answer_line(reply)
    if HAVE_MV and pred:
        for wrap in (lambda s: f"${s}$", lambda s: s):
            try:
                if mv_verify(mv_parse(wrap(gold)), mv_parse(wrap(pred))):
                    return True, pred, "math_verify"
            except Exception:  # noqa: BLE001
                continue
    a, b = as_number(pred), as_number(gold)
    if a is not None and b is not None:
        return abs(a - b) < 1e-9, pred, "number"
    na, nb = norm_text(pred), norm_text(gold)
    if na == nb and nb != "":
        return True, pred, "string"
    # lenient fallback: a short prose gold (e.g. a name) stated anywhere in the
    # tail.  Guarded to non-numeric, length>=4 tokens so "3" cannot match freely.
    tail = norm_text(reply[-240:])
    if len(nb) >= 4 and not nb.replace(".", "").replace("-", "").isdigit() and nb in tail:
        return True, pred, "contains"
    return False, pred, "string"


def grade_aime(reply, gold):
    nums = re.findall(r"-?\d[\d,]*", reply.replace(",", ""))
    got = nums[-1].lstrip("-") if nums else None
    try:
        return int(got) == int(gold) if got is not None else False, got, "int"
    except ValueError:
        return False, got, "int"


def grade_hle(reply, gold, answer_type):
    # Multiple-choice rows (and any row whose gold is a single option letter):
    # grade as a letter.
    if answer_type == "multipleChoice" or re.fullmatch(r"[A-J]", str(gold).strip()):
        return grade_letter(reply, gold)
    # exactMatch: ~45% of HLE is Math, so try symbolic/numeric equivalence first,
    # then fall back to a strict text comparison.  (grade_math already applies its
    # own guards against matching a short gold by accident.)
    ok, got, gr = grade_math(reply, gold)
    if ok:
        return True, got, "hle_" + gr
    g = norm_text(gold)
    cand = last_answer_line(reply)
    c = norm_text(cand)
    b = norm_text(last_boxed(reply) or "")
    ok2 = bool(g) and (c == g or b == g)
    if not ok2 and len(g) >= 4:
        ok2 = norm_text(reply[-(len(g) + 40):]).endswith(g)
    return ok2, cand, "hle_norm"


BENCH_SPECS = {
    "hle": (lambda r: {"id": r.get("id", r["question"][:40]), "question": r["question"],
                       "gold": r["gold"], "category": r.get("category")},
            "hle_test.jsonl", p_hle, 2000),
    "gpqa": (lambda r: {"id": r["question"][:40], "question": r["question"], "gold": r["gold"]},
             "gpqa_diamond_mc.jsonl", p_gpqa, 2000),
    "mmlu_pro": (lambda r: {"id": str(r["id"]), "question": r["question"], "gold": r["gold"],
                            "options": r["options"], "category": r.get("category")},
                 "mmlu_pro_test.jsonl", p_mmlu, 1500),
    "math500": (lambda r: {"id": r["id"], "question": r["question"], "gold": r["gold"],
                           "subject": r.get("subject")},
                "math500_test.jsonl", p_math, 2500),
    "aime": (lambda r: {"id": r["id"], "question": r["question"], "gold": r["gold"]},
             "aime.jsonl", p_aime, 3000),
}


def score_one(bench, item, reply):
    if bench == "hle":
        return grade_hle(reply, item["gold"], item.get("answer_type"))
    if bench == "gpqa":
        return grade_letter(reply, item["gold"])
    if bench == "mmlu_pro":
        return grade_letter(reply, item["gold"])
    if bench == "math500":
        return grade_math(reply, item["gold"])
    if bench == "aime":
        return grade_aime(reply, item["gold"])
    raise ValueError(bench)


def chat(base, model, prompt, max_tokens, thinking):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "temperature": 0, "max_tokens": max_tokens}
    if thinking in ("on", "off"):
        body["chat_template_kwargs"] = {"enable_thinking": thinking == "on"}
    req = urllib.request.Request(base.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1800) as r:
        out = json.load(r)
    msg = out["choices"][0]["message"]
    u = out.get("usage", {}) or {}
    rt = (u.get("completion_tokens_details") or {}).get("reasoning_tokens")
    if rt is None:
        rt = u.get("reasoning_tokens")
    # HLE injects an "answer_type" we need for grading; carry it through
    return (msg.get("content") or ""), {
        "elapsed_s": round(time.time() - t0, 2),
        "completion_tokens": u.get("completion_tokens"),
        "reasoning_tokens": rt,
        "finish_reason": out["choices"][0].get("finish_reason"),
    }


def run(a, bench):
    make, fname, prompt_fn, max_tok = BENCH_SPECS[bench]
    rows = [make(r) if bench != "hle" else {**make(r), "answer_type": r.get("answer_type")}
            for r in load_jsonl(fname)]
    items = sample(rows, a.limit, a.seed)
    rawdir = os.path.join(RESULTS, "_raw")
    os.makedirs(rawdir, exist_ok=True)
    raw = os.path.join(rawdir, f"{a.model}.{bench}.{a.thinking}.jsonl")
    done = {}
    if os.path.exists(raw):
        for line in open(raw, encoding="utf-8"):
            try:
                r = json.loads(line)
                done[r["id"]] = r
            except Exception:  # noqa: BLE001
                pass
    print(f"\n=== {bench} | {a.model} | thinking={a.thinking} | {len(items)} items "
          f"({len(done)} cached) ===", flush=True)
    with open(raw, "a", encoding="utf-8") as f:
        for it in items:
            if it["id"] in done:
                continue
            prompt = prompt_fn(it)
            try:
                reply, meta = chat(a.base_url, a.model, prompt, max_tok, a.thinking)
                ok, got, grader = score_one(bench, it, reply)
                err = None
            except Exception as e:  # noqa: BLE001
                reply, meta, ok, got, grader, err = f"<ERR {e}>", {}, False, None, "err", str(e)
            rec = {"id": it["id"], "gold": it["gold"], "reply": (reply or "").strip()[:4000],
                   "correct": ok, "extracted": got, "grader": grader, "error": err, **meta}
            done[it["id"]] = rec
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            print(f"  [{'PASS' if ok else 'FAIL'}] {str(it['id'])[:34]:34s} "
                  f"got={str(got)[:24]!r:26s} gold={str(it['gold'])[:24]!r} "
                  f"({grader})", flush=True)
    recs = [done[i["id"]] for i in items if i["id"] in done]
    n = len(recs)
    correct = sum(1 for r in recs if r["correct"])
    byc = {}
    for r in recs:
        byc.setdefault(r.get("grader", "?"), []).append(r["correct"])
    out = {"model": a.model, "bench": bench, "thinking": a.thinking, "n": n,
           "correct": correct, "pct": 100.0 * correct / n if n else 0.0,
           "errors": sum(1 for r in recs if r.get("error")),
           "graders": {k: {"n": len(v), "correct": sum(v)} for k, v in sorted(byc.items())},
           "items": recs}
    json.dump(out, open(os.path.join(RESULTS, f"{a.model}.{bench}.{a.thinking}.json"), "w"), indent=1)
    print(f"  => {bench}: {correct}/{n} = {out['pct']:.1f}%", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--bench", default="all", choices=list(BENCH_SPECS) + ["all"])
    ap.add_argument("--thinking", default="off", choices=["off", "on", "default"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=1234)
    a = ap.parse_args()
    benches = list(BENCH_SPECS) if a.bench == "all" else [a.bench]
    for b in benches:
        run(a, b)
    return 0


if __name__ == "__main__":
    sys.exit(main())