#!/usr/bin/env python3
"""Stage the held-out quality datasets for the ds4 endpoint comparison.

Everything is fetched over plain HTTPS with the standard library so the harness
has no third-party dependencies and can run anywhere the endpoint is reachable.

Sources (all public, pinned by the upstream project that owns the data):

  * GSM8K test  -- openai/gsm8k `main`/`test`, the canonical `test.jsonl`
    (1319 rows) from the OpenAI grade-school-math repo.  Used by the DeepSeek
    V4.1 model card (8-shot, 93.0 EM) so our number is directly comparable.
  * ARC-Challenge test -- allenai/ai2_arc `ARC-Challenge`/`test` (1172 rows),
    pulled through the HuggingFace datasets-server `rows` API (no `datasets`
    dependency, no parquet reader needed).

Output: data/gsm8k_test.jsonl  {"question", "answer", "gold"}
        data/arc_challenge_test.jsonl  {"id", "question", "choices", "labels", "gold"}

Idempotent: skips a file that already exists unless --force.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

GSM8K_URL = "https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/test.jsonl"
ROWS_API = "https://datasets-server.huggingface.co/rows"


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "ds4-quality-bench/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def gold_number(answer: str) -> str:
    """GSM8K answers end with `#### <number>`; that is the graded value."""
    tail = answer.strip().split("####")[-1].strip()
    return tail.replace(",", "")


def stage_gsm8k(force: bool) -> int:
    out = os.path.join(DATA, "gsm8k_test.jsonl")
    if os.path.exists(out) and not force:
        print(f"[skip] {out} exists")
        return 0
    raw = _get(GSM8K_URL).decode("utf-8")
    n = 0
    with open(out, "w") as f:
        for line in raw.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            rec = {"question": row["question"], "answer": row["answer"],
                   "gold": gold_number(row["answer"])}
            f.write(json.dumps(rec) + "\n")
            n += 1
    print(f"[ok]   {out}: {n} rows")
    return n


def stage_arc(force: bool) -> int:
    out = os.path.join(DATA, "arc_challenge_test.jsonl")
    if os.path.exists(out) and not force:
        print(f"[skip] {out} exists")
        return 0
    total = None
    offset = 0
    n = 0
    with open(out, "w") as f:
        while True:
            url = (f"{ROWS_API}?dataset=allenai%2Fai2_arc&config=ARC-Challenge"
                   f"&split=test&offset={offset}&length=100")
            d = json.loads(_get(url))
            if total is None:
                total = d["num_rows_total"]
            rows = d["rows"]
            if not rows:
                break
            for r in rows:
                row = r["row"]
                rec = {"id": row["id"], "question": row["question"],
                       "choices": row["choices"]["text"],
                       "labels": row["choices"]["label"],
                       "gold": row["answerKey"]}
                f.write(json.dumps(rec) + "\n")
                n += 1
            offset += len(rows)
            if offset >= total:
                break
    print(f"[ok]   {out}: {n} rows (expected {total})")
    return n


def main() -> int:
    force = "--force" in sys.argv
    os.makedirs(DATA, exist_ok=True)
    stage_gsm8k(force)
    stage_arc(force)
    return 0


if __name__ == "__main__":
    sys.exit(main())