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

Decode sample length is the other half. The stock needle question stops after
~6 tokens, so its ms/step median is a 3-step median, not steady state. With
`--min-answer-tokens N` the body also carries `ignore_eos: true` and
`min_tokens: N` (vllm and sglang both honour them; sglang rejects
`min_tokens > max_tokens`, so `--max-tokens` must cover N), the needle becomes a
prefix check over the first 200 characters of the reply, and the result records
`answer_tokens`, `decode_steps` and the flags used. `--task long-generation`
asks for the code followed by a long continuation instead of "code only", so a
server that ignores the lever still generates. A long sample costs wall time at
1M context; the lever is off by default and the default request body is unchanged.

A serve whose checkpoint ships no chat template answers `/v1/chat/completions` with
HTTP 400 `Cannot use chat template functions because tokenizer.chat_template is not
set`, so it cannot be measured at all. `--completions` (default off) posts the plain
prompt to `/v1/completions` instead of a `messages` array and calibrates against
that prompt, so the template never enters the path. The JSON report carries
`mode: completions` and the `endpoint` that answered, so a chat receipt and a
completions receipt cannot be confused; every other flag keeps its meaning, and with
the flag absent the request body is byte-identical to before.

Stdlib only, like the rest of tools/: it runs on the head with no venv.

Usage
-----
    python3 -B tools/longctx-cell.py --base-url http://NODE:8000 \
        --context-length 1039999 --concurrency 1 --max-tokens 128 --json out.json
    python3 -B tools/longctx-cell.py --base-url http://NODE:8000 \
        --context-length 131072 --concurrency 5,10 --max-tokens 8
    python3 -B tools/longctx-cell.py --base-url http://NODE:8000 \
        --context-length 1039999 --max-tokens 192 --min-answer-tokens 192
    python3 -B tools/longctx-cell.py --base-url http://NODE:8000 --completions \
        --context-length 1039999 --chars-per-token 6.65 \
        --max-tokens 64 --min-answer-tokens 64 --model baidu/ERNIE-5.5-Flash-Base

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

VERSION = "1.2"
DEFAULT_CPT = 3.5  # chars per token, only a starting guess; calibrated in run
CALIBRATION_TOKENS = 8192
REACHED_FRACTION = 0.97
PREFIX_CHARS = 200  # needle lives at the head of a long sample; tail is filler
QUESTIONS = {
    "retrieval":
        "What is the access code stated in the document? Answer with the code only.",
    "long-generation":
        "What is the access code stated in the document? Begin your reply with the "
        "code, then write a long, detailed continuation of the report in the same "
        "style, at least 300 words.",
}
LEVER_FIELDS = ("ignore_eos", "min_tokens")
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
    for suffix in ("/chat/completions", "/completions", "/v1"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    return base + path


def resolve_model(base: str, model: str, api_key: str | None, timeout: float) -> str:
    if model != "auto":
        return model
    req = urllib.request.Request(_url(base, "/v1/models"), headers=_headers(api_key))
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)["data"][0]["id"]


def build_prompt(target_tokens: int, seed: int, cpt: float,
                 task: str = "retrieval") -> tuple[str, str]:
    """Return ``(prompt, code)``: a unique haystack with one access code at ~50 %."""
    rng = random.Random(seed)
    code = "ZX81-%04d" % rng.randrange(1000, 9999)
    question = QUESTIONS[task]
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


def request_target(completions=False):
    """``(mode, endpoint)`` -- the one knob ``--completions`` turns, and the pair
    the report records so a chat receipt and a completions receipt cannot be
    confused."""
    if completions:
        return "completions", "/v1/completions"
    return "chat", "/v1/chat/completions"


def request_body(model, prompt, max_tokens, min_answer_tokens=0, completions=False):
    """The one body both the streaming request and the lever preflight send.

    ``completions`` sends the plain prompt to ``/v1/completions``, the only route
    a serve whose checkpoint ships no chat template answers at all.
    ``min_answer_tokens > 0`` is the opt-in decode-sample lever: both fields are
    standard OpenAI-compatible sampling fields (vllm: protocol.py; sglang maps
    ``min_tokens`` to ``min_new_tokens`` and rejects it above ``max_tokens``).
    """
    if completions:
        body = {"model": model, "prompt": prompt, "temperature": 0,
                "max_tokens": max_tokens, "stream": True,
                "stream_options": {"include_usage": True}}
    else:
        body = {"model": model, "messages": [{"role": "user", "content": prompt}],
                "temperature": 0, "max_tokens": max_tokens, "stream": True,
                "stream_options": {"include_usage": True}}
    if min_answer_tokens > 0:
        body["ignore_eos"] = True
        body["min_tokens"] = min_answer_tokens
    return body


def streaming_request(base, model, prompt, max_tokens, timeout, api_key,
                      min_answer_tokens=0, completions=False):
    body = request_body(model, prompt, max_tokens, min_answer_tokens, completions)
    req = urllib.request.Request(_url(base, request_target(completions)[1]),
                                 data=json.dumps(body).encode(),
                                 headers=_headers(api_key))
    return urllib.request.urlopen(req, timeout=timeout)


def run_request(base, model, prompt, code, max_tokens, timeout, api_key,
                min_answer_tokens=0, prefix=False, completions=False):
    rec = {"code": code, "error": None, "ttft_s": None, "steps": 0,
           "completion_tokens": None, "prompt_tokens": None,
           "needle": False, "reply": "", "stamps": [],
           "min_answer_tokens": min_answer_tokens, "needle_prefix": prefix}
    started = time.perf_counter()
    try:
        resp = streaming_request(base, model, prompt, max_tokens, timeout, api_key,
                                 min_answer_tokens, completions)
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
    rec["answer_tokens"] = rec["completion_tokens"] or rec["steps"]
    rec["decode_steps"] = rec["steps"]
    rec["needle"] = needle_hit(rec["reply"], code, prefix)
    rec["wall_s"] = round(time.perf_counter() - started, 3)
    return rec


def needle_hit(reply, code, prefix):
    """Default cells keep the old anywhere-check; a long sample checks its head."""
    return code in (reply[:PREFIX_CHARS] if prefix else reply)


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
                piece = (delta.get("content") or delta.get("reasoning_content")
                         or choice.get("text") or "")
                if piece:
                    rec["reply"] += piece
                    rec["stamps"].append(time.perf_counter())
                    rec["steps"] += 1


def calibrate(base, model, cpt, timeout, api_key, completions=False):
    prompt, _code = build_prompt(CALIBRATION_TOKENS, 99, cpt)
    rec = run_request(base, model, prompt, "", 8, timeout, api_key,
                      completions=completions)
    if rec["error"] or not rec["prompt_tokens"]:
        return cpt, rec
    return len(prompt) / rec["prompt_tokens"], rec


def probe_lever(base, model, min_answer_tokens, task, timeout, api_key,
                completions=False):
    """One short request proving the fields land; returns ``(task, fields, note)``.

    A 4xx means the server refuses the fields, and a short reply means it read
    them and ignored them. Either way the cell falls back to a prompt that does
    not stop early (``long-generation``), which still carries the needle.
    """
    prompt, code = build_prompt(256, 4242, DEFAULT_CPT, task)
    rec = run_request(base, model, prompt, code, min_answer_tokens,
                      timeout, api_key, min_answer_tokens, prefix=True,
                      completions=completions)
    if rec["error"]:
        return ("long-generation", (),
                "lever rejected (%s); falling back to a long-generation prompt" % rec["error"])
    if (rec["answer_tokens"] or 0) < min_answer_tokens:
        return ("long-generation", LEVER_FIELDS,
                "engine produced %d of %d requested tokens; long-generation prompt as fallback"
                % (rec["answer_tokens"] or 0, min_answer_tokens))
    return task, LEVER_FIELDS, None


def cell(args, base, model, cpt, concurrency, sent_min=0):
    prompts = [build_prompt(args.context_length, args.seed * 1000 + i, cpt, args.task)
               for i in range(concurrency)]
    recs: list = [None] * concurrency

    def one(i):
        prompt, code = prompts[i]
        recs[i] = run_request(base, model, prompt, code, args.max_tokens,
                              args.timeout, args.api_key, sent_min,
                              prefix=args.min_answer_tokens > 0,
                              completions=args.completions)

    t0 = time.perf_counter()
    threads = [threading.Thread(target=one, args=(i,)) for i in range(concurrency)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.perf_counter() - t0
    return summarize(recs, concurrency, wall, args.min_answer_tokens, args.task,
                     sent_min)


def summarize(recs, concurrency, wall, min_answer_tokens=0, task="retrieval",
              sent_min=0):
    good = [r for r in recs if not r["error"]]
    steps = [r["ms_per_step"] for r in good if r.get("ms_per_step")]
    rates = [r["completion_tokens"] / r["decode_s"] for r in good
             if r.get("completion_tokens") and r.get("decode_s")]
    answers = [r["answer_tokens"] for r in good if r.get("answer_tokens")]
    decode_steps = [r["decode_steps"] for r in good if r.get("decode_steps")]
    tokens = sum(r["completion_tokens"] or r["steps"] for r in good)
    return {
        "concurrency": concurrency,
        "task": task,
        "min_answer_tokens": min_answer_tokens,
        "min_tokens_sent": sent_min,
        "answer_tokens_median": int(statistics.median(answers)) if answers else None,
        "decode_steps_median": int(statistics.median(decode_steps)) if decode_steps else None,
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
        want = c.get("min_answer_tokens") or 0
        for r in c["requests"]:
            if not r["error"] and (r.get("answer_tokens") or 0) < want:
                problems.append("%s: answer %d tokens < min_tokens %d (engine ignored the lever?)"
                                % (label, r.get("answer_tokens") or 0, want))
    if not any(c["prompt_tokens"] for c in cells):
        problems.append("no usage.prompt_tokens: prompt length unverified")
    return problems


def check_flags(args):
    if args.min_answer_tokens < 0:
        return "--min-answer-tokens must be >= 0"
    if args.min_answer_tokens > args.max_tokens:
        return ("--min-answer-tokens %d needs --max-tokens >= %d "
                "(sglang rejects min_tokens > max_tokens)"
                % (args.min_answer_tokens, args.min_answer_tokens))
    return None


def parse(argv):
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--base-url", help="serve root, e.g. http://HOST:8000")
    ap.add_argument("--model", default="auto", help="served id; 'auto' reads /v1/models")
    ap.add_argument("--context-length", type=str,
                    help="prompt tokens: 1039999, 131072 or 1m")
    ap.add_argument("--concurrency", default="1", help="comma-separated levels, ascending")
    ap.add_argument("--max-tokens", type=int, default=128)
    ap.add_argument("--min-answer-tokens", type=int, default=0,
                    help="decode-sample lever: 0 keeps today's body; >0 sends "
                         "ignore_eos + min_tokens so the sample is at least N steps")
    ap.add_argument("--task", choices=sorted(QUESTIONS), default="retrieval",
                    help="retrieval = 'code only' (stops early); long-generation = "
                         "code then a long continuation")
    ap.add_argument("--completions", action="store_true",
                    help="post the plain prompt to /v1/completions instead of a "
                         "messages array to /v1/chat/completions: the only route a "
                         "serve whose checkpoint ships no chat template answers")
    ap.add_argument("--timeout", type=float, default=3600.0, help="per-request seconds")
    ap.add_argument("--api-key", default=None, help="bearer token; never printed")
    ap.add_argument("--seed", type=int, default=1017)
    ap.add_argument("--chars-per-token", type=float, default=None,
                    help="skip calibration and size the haystack with this ratio")
    ap.add_argument("--json", default=None, help="write the full result here")
    ap.add_argument("--image-id", default=None,
                    help="served image id/ref, echoed into the report so a receipt "
                         "pins the image its cell ran on")
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
    bad = check_flags(args)
    if bad:
        print(bad, file=sys.stderr)
        return 2
    args.context_length = parse_length(args.context_length)
    levels = [int(x) for x in args.concurrency.split(",") if x.strip()]
    cpt = args.chars_per_token
    model = None
    try:
        model = resolve_model(args.base_url, args.model, args.api_key, args.timeout)
        if cpt is None:
            cpt, probe = calibrate(args.base_url, model, DEFAULT_CPT, args.timeout,
                                   args.api_key, args.completions)
            if probe["error"]:
                print("calibration failed: " + probe["error"], file=sys.stderr)
                return 1
    except Exception as exc:
        print("endpoint unreachable: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 1
    fields, note, sent_min = (), None, 0
    if args.min_answer_tokens:
        args.task, fields, note = probe_lever(args.base_url, model,
                                              args.min_answer_tokens, args.task,
                                              args.timeout, args.api_key,
                                              args.completions)
        sent_min = args.min_answer_tokens if fields else 0
        if note:
            print("lever: " + note, file=sys.stderr, flush=True)
    cells = []
    for level in levels:
        print("C%d: prompting %d tokens, max_tokens=%d min_tokens=%d task=%s" % (
            level, args.context_length, args.max_tokens, sent_min, args.task),
            file=sys.stderr, flush=True)
        cells.append(cell(args, args.base_url, model, cpt, level, sent_min))
        c = cells[-1]
        print("C%-3d wall=%8.1fs prompt=%s ms/step=%s ans=%s steps=%s tok/s=%s agg=%s "
              "needle=%d/%d err=%d" % (
                  c["concurrency"], c["wall_s"], c["prompt_tokens"] or "?",
                  c["ms_per_step_median"], c["answer_tokens_median"],
                  c["decode_steps_median"], c["tok_per_s_median"],
                  c["aggregate_tok_per_s"], c["needle_hits"], c["concurrency"],
                  c["errors"]))
    problems = verdict(cells, args.context_length)
    report = {
        "tool_version": VERSION, "base_url": args.base_url, "model": model,
        "mode": request_target(args.completions)[0],
        "endpoint": request_target(args.completions)[1],
        "context_length": args.context_length, "max_tokens": args.max_tokens,
        "chars_per_token": round(cpt, 4), "image_id": args.image_id,
        "task": args.task, "min_answer_tokens": args.min_answer_tokens,
        "sampling": {"fields_sent": list(fields), "note": note},
        "cells": cells, "problems": problems,
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
    plain = request_body("m", "p", 128)
    assert "ignore_eos" not in plain and "min_tokens" not in plain, plain
    assert plain["max_tokens"] == 128
    lever = request_body("m", "p", 192, 192)
    assert lever["ignore_eos"] is True and lever["min_tokens"] == 192, lever
    assert lever["max_tokens"] == 192, lever
    assert request_target() == ("chat", "/v1/chat/completions")
    assert request_target(True) == ("completions", "/v1/completions")
    comp = request_body("m", "p", 64, 64, completions=True)
    assert comp["prompt"] == "p" and "messages" not in comp, comp
    assert comp["model"] == "m" and comp["max_tokens"] == 64, comp
    assert comp["ignore_eos"] is True and comp["min_tokens"] == 64, comp
    long_prompt, long_code = build_prompt(2000, 7, 3.5, "long-generation")
    assert long_prompt.count("ZX81-") == 1 and long_code in long_prompt
    assert "continuation" in long_prompt
    assert needle_hit("the code is " + code + " then filler", code, True)
    assert not needle_hit("x" * 400 + code, code, True)
    assert needle_hit("x" * 400 + code, code, False)
    args = parse([]).parse_args(["--max-tokens", "8", "--min-answer-tokens", "8"])
    assert check_flags(args) is None
    args = parse([]).parse_args(["--max-tokens", "8", "--min-answer-tokens", "9"])
    assert check_flags(args), "min_tokens above max_tokens must be refused"
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
