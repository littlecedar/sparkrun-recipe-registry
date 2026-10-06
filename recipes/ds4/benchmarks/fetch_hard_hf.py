#!/usr/bin/env python3
"""Stage the hard reasoning datasets via the `datasets` library (parquet path).

Why this exists as well as `fetch_hard.py`: the HuggingFace datasets-server
`rows` API (used by fetch_hard.py / fetch_data.py) begins rate-limiting (HTTP
429) once several datasets are pulled in a burst.  This script uses the
`datasets` library instead, which downloads the datasets-server *parquet* export
directly from huggingface.co -- a different limit -- so the two paths cover each
other.  Run it with the venv python that has `datasets`/`pyarrow`:

    recipes/ds4/benchmarks/.venv-qa/bin/python fetch_hard_hf.py [--force]

Output JSONL schemas are identical to fetch_hard.py, so the harness reads one
format regardless of which stager produced the file.
"""
from __future__ import annotations

import argparse
import json
import os

import datasets

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

# name -> (hf path, config, split, outfile, keep fn)
SPECS = {
    "hle": ("macabdul9/hle_text_only", None, "test", "hle_test.jsonl",
            lambda r: {"id": r["id"], "question": r["question"], "gold": r["answer"],
                       "answer_type": r.get("answer_type"), "category": r.get("category"),
                       "subject": r.get("raw_subject")}),
    "gpqa": ("hendrydong/gpqa_diamond_mc", None, "test", "gpqa_diamond_mc.jsonl",
             lambda r: {"question": r["problem"], "gold": r["solution"], "domain": r.get("domain")}),
    "mmlu_pro": ("TIGER-Lab/MMLU-Pro", None, "test", "mmlu_pro_test.jsonl",
                 lambda r: {"id": r["question_id"], "question": r["question"],
                            "options": r["options"], "gold": r["answer"], "category": r.get("category")}),
    "math_500": ("HuggingFaceH4/MATH-500", None, "test", "math500_test.jsonl",
                 lambda r: {"id": r["unique_id"], "question": r["problem"], "gold": r["answer"],
                            "subject": r.get("subject"), "level": r.get("level")}),
    "aime": ("AI-MO/aimo-validation-aime", None, "train", "aime.jsonl",
             lambda r: {"id": str(r["id"]), "question": r["problem"], "gold": str(r["answer"])}),
}


def stage(name, force):
    path, cfg, split, outfile, keep = SPECS[name]
    out = os.path.join(DATA, outfile)
    if os.path.exists(out) and not force:
        print(f"[skip] {out} exists")
        return
    ds = datasets.load_dataset(path, cfg, split=split)
    n = 0
    with open(out, "w") as f:
        for r in ds:
            f.write(json.dumps(keep(r), ensure_ascii=False) + "\n")
            n += 1
    print(f"[ok]   {out}: {n} rows")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only")
    a = ap.parse_args()
    os.makedirs(DATA, exist_ok=True)
    for name in SPECS:
        if a.only and name != a.only:
            continue
        stage(name, a.force)


if __name__ == "__main__":
    main()