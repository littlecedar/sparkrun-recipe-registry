#!/usr/bin/env python3
"""Sizing probe: tokens/seconds per hard item with thinking on and off.

Reads the already-staged local datasets (data/), NOT the network, so it is immune
to the datasets-server rate limit.  This is a capacity check to size the
overnight battery, not a benchmark.  Hits the gateway only.
"""
import json, os, time, urllib.request

BASE = "http://spark-head.internal.littlecedar.net:4000/v1/chat/completions"
HERE = os.path.dirname(os.path.abspath(__file__))


def load(f):
    return [json.loads(l) for l in open(os.path.join(HERE, "data", f)) if l.strip()]


def chat(model, prompt, max_tokens=16000, thinking=True):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "temperature": 0, "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": thinking}}
    req = urllib.request.Request(BASE, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    out = json.load(urllib.request.urlopen(req, timeout=2400))
    m = out["choices"][0]["message"]
    u = out.get("usage", {})
    return {"elapsed": round(time.time() - t0, 1),
            "completion_tokens": u.get("completion_tokens"),
            "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
            "finish": out["choices"][0].get("finish_reason"),
            "content": (m.get("content") or ""),
            "reasoning_len": len(m.get("reasoning_content") or "")}


if __name__ == "__main__":
    hle = load("hle_test.jsonl")[:2]
    gpqa = load("gpqa_diamond_mc.jsonl")[:1]
    math = load("math500_test.jsonl")[:1]
    aime = load("aime.jsonl")[:1]
    tests = [("HLE", hle[0]["question"]), ("HLE", hle[1]["question"]),
             ("GPQA", gpqa[0]["question"]), ("MATH500", math[0]["question"]),
             ("AIME", aime[0]["question"])]
    for label, q in tests:
        print(f"\n##### {label}: {q[:90]!r}...", flush=True)
        for model in ["deepseek", "deepseek-turbo"]:
            for thinking in [True, False]:
                try:
                    r = chat(model, q, thinking=thinking)
                    print(f"  {model:16s} think={str(thinking):5s} {r['elapsed']:7.1f}s "
                          f"ct={r['completion_tokens']} rt={r['reasoning_tokens']} "
                          f"finish={r['finish']} clen={len(r['content'])} "
                          f"tail={r['content'][-60:]!r}", flush=True)
                except Exception as e:
                    print(f"  {model:16s} think={thinking} ERROR {type(e).__name__}: {e}", flush=True)