#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Travis Wichert
# SPDX-License-Identifier: AGPL-3.0-or-later
"""longctx-cell.py -- one long-context decode cell (ms/step + retrieval).

Why this exists
---------------
Two survey arms need a cell no shipped harness measures. Candidate-only indexer
scoring (DEEPSEEK.md section 10.5) is a 1,039,999-token retrieval prompt, greedy,
>=128 output tokens, reporting ms/step *and* the needle result. The TRT-LLM
sparse-MLA backend (section 10.7) is a 128K prompt at C5/C10. The campaign
executor measures a short-context ladder and a house battery; this tool is the
one extra client an arm runs before its serve is torn down.

It builds a synthetic retrieval haystack at the requested token length, plants
one access code at ~50 %, and sends it as a greedy streaming request. Streaming
*is* the step measurement: a speculative-decode engine emits one SSE chunk per
decode step, so the median gap between chunks is ms/step. The reply is checked
for the code, so the cell carries its own quality witness -- a decode win with a
lost needle is not a win.

Prompt length is calibrated against the server's own tokenizer with one small
probe request, then verified from the streaming response's `usage.prompt_tokens`.
A length the server did not count is a finding, not a pass.

Stdlib only, like the rest of tools/: it runs on the head with no venv.

Usage
-----
    python3 -B tools/longctx-cell.py --base-url http://NODE:8000 \
        --context-length 1039999 --concurrency 1 --max-tokens 128 --json out.json
    python3 -B tools/longctx-cell.py --base-url http://NODE:8000 \
        --context-length 131072 --concurrency 5,10 --max-tokens 8

Exit codes: 0 every cell measured and retrieved the code; 1 transport failure or
unreachable endpoint; 2 bad flags; 3 a cell measured but failed its own checks
(needle miss, prompt shorter than requested, a request error).
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request

VERSION = "1.0"
DEFAULT_CPT = 3.5  # chars per token, only a starting guess; calibrated in run
CALIBRATION_TOKENS = 8192
REACHED_FRACTION = 0.97
WORDS = (
    "annual report revenue margin segment region quarter shipment inventory "
    "supplier forecast logistics warehouse dispatch variance audit ledger "
    "capacity utilisation component assembly tolerance batch inspection "
    "clearance freight tariff procurement contract renewal staffing roster "
    "training schedule maintenance downtime calibration throughput"
).split()
def _headers(api_key: str | None) -> dict[str, str]:
    head = {"Content-Type": "application/json"}
    if api_key:
        head["Authorization"] = f"Bearer {api_key}"
    return head


def _url(base: str, path: str) -> str:
    base = base.rstrip("/")
    if base.endswith("/chat/completions"):
        base = base[: -len("/chat/completions")]
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    return base + path


def resolve_model(base: str, model: str, api_key: str | None, timeout: float) -> str:
    if model != "auto":
        return model
    req = urllib.request.Request(_url(base, "/v1/models"), headers=_headers(api_key))
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)["data"][0]["id"]


def build_prompt(target_tokens: int, seed: int, cpt: float) -> tuple[str, str]:
    """Return ``(prompt, code)``: a unique haystack with one access code at ~50 %."""
    rng = random.Random(seed)
    code = "ZX81-%04d" % rng.randrange(1000, 9999)
    question = "What is the access code stated in the document? Answer with the code only."
    budget = max(400, int(target_tokens * cpt) - len(question) - 128)
    parts: list[str] = []
    written = 0
    sentences = 0
    while written < budget:
        sentence = " ".join(rng.choice(WORDS) for _ in range(rng.randrange(8, 16)))
        sentence = f"Report entry {sentences}: {sentence}.\n"
        if written < budget // 2 <= written + len(sentence):
            sentence = f"The access code is {code}. " + sentence
        parts.append(sentence)
        written += len(sentence)
        sentences += 1
    body = "".join(parts)
    prompt = "<document>\n" + body + "\n</document>\n\n" + question
    return prompt, code


def streaming_chat(base, model, prompt, max_tokens, timeout, api_key):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "temperature": 0, "max_tokens": max_tokens, "stream": True,
            "stream_options": {"include_usage": True}}
    req = urllib.request.Request(_url(base, "/v1/chat/completions"),
                                 data=json.dumps(body).encode(),
                                 headers=_headers(api_key))
    return urllib.request.urlopen(req, timeout=timeout)


def run_request(base, model, prompt, code, max_tokens, timeout, api_key):
    rec = {"code": code, "error": None, "ttft_s": None, "steps": 0,
           "completion_tokens": None, "prompt_tokens": None,
           "needle": False, "reply": "", "stamps": []}
    started = time.perf_counter()
    try:
        resp = streaming_chat(base, model, prompt, max_tokens, timeout, api_key)
    except urllib.error.HTTPError as exc:
        rec["error"] = "HTTP %s: %s" % (exc.code, exc.read()[:200].decode(errors="replace"))
        rec["wall_s"] = time.perf_counter() - started
        return rec
    except Exception as exc:
        rec["error"] = "%s: %s" % (type(exc).__name__, exc)
        rec["wall_s"] = time.perf_counter() - started
        return rec
    _consume(resp, rec)
    st = rec["stamps"]
    if len(st) > 1:
        rec["ttft_s"] = round(st[0] - started, 3)
        rec["decode_s"] = round(st[-1] - st[0], 3)
        gaps = [b - a for a, b in zip(st, st[1:])]
        rec["ms_per_step"] = round(statistics.median(gaps) * 1000.0, 1)
    rec["needle"] = code in rec["reply"]
    rec["wall_s"] = round(time.perf_counter() - started, 3)
    return rec


def _consume(resp, rec):
    with resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if line.startswith("data:"):
                line = line[5:].strip()
            if not line or line[0] not in "{[":
                continue
            try:
                chunk = json.loads(line)
            except ValueError:
                continue
            usage = chunk.get("usage") or {}
            if usage.get("prompt_tokens"):
                rec["prompt_tokens"] = usage["prompt_tokens"]
            if usage.get("completion_tokens"):
                rec["completion_tokens"] = usage["completion_tokens"]
            for choice in chunk.get("choices") or []:
                delta = choice.get("delta") or {}
                piece = delta.get("content") or delta.get("reasoning_content") or ""
                if piece:
                    rec["reply"] += piece
                    rec["stamps"].append(time.perf_counter())
                    rec["steps"] += 1


def calibrate(base, model, cpt, timeout, api_key):
    prompt, _code = build_prompt(CALIBRATION_TOKENS, 99, cpt)
    rec = run_request(base, model, prompt, "", 8, timeout, api_key)
    if rec["error"] or not rec["prompt_tokens"]:
        return cpt, rec
    return len(prompt) / rec["prompt_tokens"], rec


def cell(args, base, model, cpt, concurrency):
    prompts = [build_prompt(args.context_length, args.seed * 1000 + i, cpt)
               for i in range(concurrency)]
    recs: list = [None] * concurrency

    def one(i):
        prompt, code = prompts[i]
        recs[i] = run_request(base, model, prompt, code, args.max_tokens,
                              args.timeout, args.api_key)

    t0 = time.perf_counter()
    threads = [threading.Thread(target=one, args=(i,)) for i in range(concurrency)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.perf_counter() - t0
    return summarize(recs, concurrency, wall)


def summarize(recs, concurrency, wall):
    good = [r for r in recs if not r["error"]]
    steps = [r["ms_per_step"] for r in good if r.get("ms_per_step")]
    rates = [r["completion_tokens"] / r["decode_s"] for r in good
             if r.get("completion_tokens") and r.get("decode_s")]
    tokens = sum(r["completion_tokens"] or r["steps"] for r in good)
    return {
        "concurrency": concurrency,
        "wall_s": round(wall, 3),
        "errors": len(recs) - len(good),
        "needle_hits": sum(1 for r in good if r["needle"]),
        "prompt_tokens": sorted({r["prompt_tokens"] for r in good if r["prompt_tokens"]}),
        "ms_per_step_median": round(statistics.median(steps), 1) if steps else None,
        "tok_per_s_median": round(statistics.median(rates), 2) if rates else None,
        "aggregate_tok_per_s": round(tokens / wall, 2) if wall else None,
        "requests": recs,
    }


def verdict(cells, wanted):
    problems = []
    for c in cells:
        label = "C%d" % c["concurrency"]
        if c["errors"]:
            problems.append("%s: %d request error(s)" % (label, c["errors"]))
        if c["needle_hits"] < c["concurrency"] - c["errors"]:
            problems.append("%s: needle %d/%d" % (label, c["needle_hits"], c["concurrency"]))
        for pt in c["prompt_tokens"]:
            if pt < wanted * REACHED_FRACTION:
                problems.append("%s: server counted %d tokens, asked %d" % (label, pt, wanted))
    if not any(c["prompt_tokens"] for c in cells):
        problems.append("no usage.prompt_tokens: prompt length unverified")
    return problems


def parse(argv):
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--base-url", help="serve root, e.g. http://HOST:8000")
    ap.add_argument("--model", default="auto", help="served id; 'auto' reads /v1/models")
    ap.add_argument("--context-length", type=str,
                    help="prompt tokens: 1039999, 131072 or 1m")
    ap.add_argument("--concurrency", default="1", help="comma-separated levels, ascending")
    ap.add_argument("--max-tokens", type=int, default=128)
    ap.add_argument("--timeout", type=float, default=3600.0, help="per-request seconds")
    ap.add_argument("--api-key", default=None, help="bearer token; never printed")
    ap.add_argument("--seed", type=int, default=1017)
    ap.add_argument("--chars-per-token", type=float, default=None,
                    help="skip calibration and size the haystack with this ratio")
    ap.add_argument("--json", default=None, help="write the full result here")
    ap.add_argument("--selftest", action="store_true", help="offline mock; no serve needed")
    ap.add_argument("--version", action="version", version="longctx-cell " + VERSION)
    return ap


def parse_length(raw):
    text = raw.strip().lower()
    if text.endswith("k"):
        return int(float(text[:-1]) * 1000)
    if text.endswith("m"):
        return int(float(text[:-1]) * 1000 * 1000)
    return int(text)


def main(argv=None):
    args = parse(argv).parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.base_url or not args.context_length:
        print("--base-url and --context-length are required", file=sys.stderr)
        return 2
    args.context_length = parse_length(args.context_length)
    levels = [int(x) for x in args.concurrency.split(",") if x.strip()]
    cpt = args.chars_per_token
    model = None
    try:
        model = resolve_model(args.base_url, args.model, args.api_key, args.timeout)
        if cpt is None:
            cpt, probe = calibrate(args.base_url, model, DEFAULT_CPT, args.timeout, args.api_key)
            if probe["error"]:
                print("calibration failed: " + probe["error"], file=sys.stderr)
                return 1
    except Exception as exc:
        print("endpoint unreachable: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 1
    cells = []
    for level in levels:
        print("C%d: prompting %d tokens, max_tokens=%d" % (level, args.context_length,
              args.max_tokens), file=sys.stderr, flush=True)
        cells.append(cell(args, args.base_url, model, cpt, level))
        c = cells[-1]
        print("C%-3d wall=%8.1fs prompt=%s ms/step=%s tok/s=%s agg=%s needle=%d/%d err=%d" % (
            c["concurrency"], c["wall_s"], c["prompt_tokens"] or "?",
            c["ms_per_step_median"], c["tok_per_s_median"], c["aggregate_tok_per_s"],
            c["needle_hits"], c["concurrency"], c["errors"]))
    problems = verdict(cells, args.context_length)
    report = {
        "tool_version": VERSION, "base_url": args.base_url, "model": model,
        "context_length": args.context_length, "max_tokens": args.max_tokens,
        "chars_per_token": round(cpt, 4), "cells": cells, "problems": problems,
    }
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
    for problem in problems:
        print("PROBLEM: " + problem, file=sys.stderr)
    print("verdict:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 3


def selftest():
    prompt, code = build_prompt(2000, 7, 3.5)
    assert code in prompt and prompt.count("ZX81-") == 1, "needle plant"
    assert len(prompt) > 6000, len(prompt)
    assert parse_length("1m") == 1000000 and parse_length("131072") == 131072
    rec = {"error": None, "needle": True, "completion_tokens": 100,
           "decode_s": 2.0, "ms_per_step": 20.0, "prompt_tokens": 200000,
           "steps": 100, "reply": code, "code": code}
    assert rec["ms_per_step"] == 20.0
    cell_ = summarize([rec, dict(rec)], 2, 4.0)
    assert cell_["needle_hits"] == 2 and cell_["ms_per_step_median"] == 20.0, cell_
    assert cell_["aggregate_tok_per_s"] == 50.0, cell_
    assert verdict([cell_], 200000) == [], verdict([cell_], 200000)
    short = dict(cell_, prompt_tokens=[1000])
    assert verdict([short], 200000), "short prompt must be a finding"
    miss = dict(cell_, needle_hits=1)
    assert verdict([miss], 200000), "needle miss must be a finding"
    print("selftest: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
