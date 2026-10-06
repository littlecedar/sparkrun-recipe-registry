#!/usr/bin/env python3
"""Stage the *hard* held-out datasets for the overnight reasoning battery.

Companion to `fetch_data.py` (which stages GSM8K + ARC).  Everything is pulled
through the HuggingFace datasets-server `rows` API with the standard library only,
so there is no `datasets`/`pyarrow` dependency.  Each source is pinned to the
config/split that is the canonical test set for that benchmark.

Sources and provenance
----------------------
  hle        macabdul9/hle_text_only        = Humanity's Last Exam, text-only
             (the gated upstream is cais/hle; this mirror carries the same 2370
             text rows incl. answer_type and category).  Short-answer + MCQ.
  gpqa       hendrydong/gpqa_diamond_mc     = GPQA Diamond, multiple-choice form
             (198 rows; the gated upstream is Idavidrein/gpqa).  letter gold.
  mmlu_pro   TIGER-Lab/MMLU-Pro             = MMLU-Pro test (12032), 10-way MCQ.
  math_500   HuggingFaceH4/MATH-500         = the standard 500-item MATH test
             subset used for MATH-500 reporting.  boxed/numeric gold.
  aime       AI-MO/aimo-validation-aime     = 90 AIME problems (2022-2024), integer gold.

Output:  data/hle_test.jsonl, data/gpqa_diamond_mc.jsonl, data/mmlu_pro_test.jsonl,
         data/math500_test.jsonl, data/aime.jsonl

Idempotent: skips a file that already exists unless --force.  `--only NAME` stages
one dataset.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
ROWS_API = "https://datasets-server.huggingface.co/rows"

# name -> (dataset, config, split, keep-fields fn)
SPECS = {
    "hle": ("macabdul9/hle_text_only", "default", "test",
            lambda r: {"id": r["id"], "question": r["question"], "gold": r["answer"],
                       "answer_type": r.get("answer_type"), "category": r.get("category"),
                       "subject": r.get("raw_subject")}),
    "gpqa": ("hendrydong/gpqa_diamond_mc", "default", "test",
             lambda r: {"question": r["problem"], "gold": r["solution"], "domain": r.get("domain")}),
    "mmlu_pro": ("TIGER-Lab/MMLU-Pro", "default", "test",
                 lambda r: {"id": r["question_id"], "question": r["question"],
                            "options": r["options"], "gold": r["answer"], "category": r.get("category")}),
    "math_500": ("HuggingFaceH4/MATH-500", "default", "test",
                 lambda r: {"id": r["unique_id"], "question": r["problem"], "gold": r["answer"],
                            "subject": r.get("subject"), "level": r.get("level")}),
    "aime": ("AI-MO/aimo-validation-aime", "default", "train",
             lambda r: {"id": str(r["id"]), "question": r["problem"], "gold": str(r["answer"])}),
}


def _get(url: str) -> bytes:
    import time
    req = urllib.request.Request(url, headers={"User-Agent": "ds4-hard-bench/1.0"})
    last = None
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(2 * (attempt + 1))
                continue
            raise
    raise last


def stage(name: str, force: bool) -> int:
    ds, cfg, split, keep = SPECS[name]
    out = os.path.join(DATA, f"{name}_test.jsonl" if name != "aime" else "aime.jsonl")
    if os.path.exists(out) and not force:
        print(f"[skip] {out} exists")
        return 0
    total = None
    offset = 0
    n = 0
    with open(out, "w") as f:
        while True:
            url = (f"{ROWS_API}?dataset={urllib.parse.quote(ds)}&config={cfg}"
                   f"&split={split}&offset={offset}&length=100")
            d = json.loads(_get(url))
            if total is None:
                total = d["num_rows_total"]
            rows = d["rows"]
            if not rows:
                break
            for x in rows:
                f.write(json.dumps(keep(x["row"]), ensure_ascii=False) + "\n")
                n += 1
            offset += len(rows)
            if total is not None and offset >= total:
                break
    print(f"[ok]   {out}: {n} rows (expected {total})")
    return n


def main() -> int:
    force = "--force" in sys.argv
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]
    os.makedirs(DATA, exist_ok=True)
    for name in SPECS:
        if only and name != only:
            continue
        stage(name, force)
    return 0


if __name__ == "__main__":
    sys.exit(main())