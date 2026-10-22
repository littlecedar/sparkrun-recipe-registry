#!/usr/bin/env python3
r"""Re-analysis of stored §7(c) rewrites with a tighter, documented instrument.

Recovered verbatim from the 2026-10-14 receipt `~/benchmarks/humanizer-20261014/`
(analyze.py) so the 2026-10-22 quant round is apples-to-apples with the archived
bf16 arm. Reads a results.json produced by tools/humanizer-measure.py — no model
calls. The instrument is lexical, not the card's LLM judge:

  numbers  \b\d[\d,]*(?:\.\d+)?%?\b           normalised by stripping ","
                                              and a trailing "%"; a draft
                                              number is MISSING iff its
                                              normalised form never appears in
                                              the rewrite.
  dates    English month + weekday names, plus `M/D` and `Month D` forms
                                              canonicalised to (month, day) pairs;
                                              a draft date is MISSING iff neither
                                              its month word nor its canonical
                                              (month, day) / (month) form appears.
  names    capitalised multi-word sequences, plus mid-sentence capitalised
                                              words not in a common-word list; a
                                              draft name is MISSING iff none of
                                              its capitalised tokens appears
                                              (case-insensitive) in the rewrite.

Every flag is printed with its draft and rewrite context so it can be reviewed
by hand — the deliverable reports both the raw flag count and the reviewed
serious/minor/reformatted split.
"""
import json
import re
import sys

MONTHS = {m: i for i, m in enumerate(
    "january february march april may june july august september october "
    "november december".split(), 1)}
WEEKDAYS = set("monday tuesday wednesday thursday friday saturday sunday".split())

# No trailing \b: rewrites glue the unit to the number ("340 GB" -> "340GB").
NUM = re.compile(r"(?<!\d)\d[\d,]*(?:\.\d+)?")
# Case-SENSITIVE: lowercase "may" is a modal verb, not a date.
MONTH_RE = re.compile(r"\b(%s)\w*\b" % "|".join(m.capitalize() for m in MONTHS))
WEEKDAY_RE = re.compile(r"\b(%s)\b" % "|".join(w.capitalize() for w in WEEKDAYS))
DATE_NUM = re.compile(r"\b(\d{1,2})/(\d{1,2})\b")
YEAR = re.compile(r"\b(19|20)\d{2}\b")
CAP_SEQ = re.compile(r"\b(?:[A-Z][a-z]+\s+){1,2}[A-Z][a-z]+\b")
MID_CAP = re.compile(r"[A-Z][a-z]{2,}")
STOP = set("""The This That There They Then These Those We You Your Our It Its If In On At By For From
With And But Or So As Is Are Was Were Not No Do Does Did Can Will Would Should Must May Might All Any
Some Each Every Both One Two Three Four Five Six Seven Eight Nine Ten Half Most More Other Out Over
After Before When Where What Which Who Why How Here Now Just Only Also Still Even Much Many Very Same
First Second Third Last Next Number Query Routing Home Since Round Routine Retention Report Review
Warranty Cost Impact Duration Detected Resolved Timeline Root Breaking Added Changed Fixed Bursts
Limits Clients Requests Applications Equipment Core Effective Remove Pull Fit Take Thread Grease
Drive Proposal Problem Remote Design Decisions Open Ports Available Dear Sincerely Attendees Date
Purpose Monday Tuesday Wednesday Thursday Friday Summary Incidents Actions Posted Release Native
Days Hours Minutes Seconds Today Tomorrow Yesterday""".split()) | set(MONTHS) | WEEKDAYS | {
    m.capitalize() for m in MONTHS}


def nums(text):
    return {(lambda s: s.lstrip("0") or "0")(m.group(0).rstrip("%").replace(",", ""))
            for m in NUM.finditer(text)}


def dates(text):
    out = set()
    for m in MONTH_RE.finditer(text):
        out.add(("month", MONTHS[m.group(1).lower()]))
    for m in DATE_NUM.finditer(text):
        out.add(("md", int(m.group(1)), int(m.group(2))))
    for m in WEEKDAY_RE.finditer(text):
        out.add(("day", m.group(1).lower()))
    return out


def _sentence_start(text, pos):
    pre = text[:pos]
    return (not pre) or pre[-1] == "\n" or pre[-1] in ".!?:;" or (
        len(pre) > 1 and pre[-2] in ".!?" and pre[-1] == " ")


def names(text):
    out = set()
    for m in CAP_SEQ.finditer(text):
        if m.group(0).split()[0] in STOP:
            continue
        out.add(m.group(0))
    for m in MID_CAP.finditer(text):
        if m.group(0) in STOP or _sentence_start(text, m.start()):
            continue
        out.add(m.group(0))
    return out


def _import_measure():
    """tools/humanizer-measure.py is dash-named, so the house importlib idiom."""
    import importlib.util
    import os

    spec = importlib.util.spec_from_file_location(
        "humanizer_measure",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "humanizer-measure.py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["humanizer_measure"] = module
    spec.loader.exec_module(module)
    return module


def main(path):
    d = json.load(open(path, encoding="utf-8"))
    # humanizer-measure.py does not store the drafts; re-import them from it
    # (the receipt's analyze.py imported the sibling `measure` module).
    drafts = {i: (g, t) for i, (g, t)
              in enumerate(_import_measure().DRAFTS, 1)}

    flags = {"number": [], "date": [], "name": [], "added_number": []}
    for r in d["rewrites"]:
        genre, draft = drafts[r["n"]]
        low = r["output"].lower()
        dn, on = nums(draft), nums(r["output"])
        dd, od = dates(draft), dates(r["output"])
        dnm = names(draft)
        for x in sorted(dn - on):
            flags["number"].append((r["n"], genre, r["sample"], x))
        for x in sorted(dd - od):
            if x[0] == "month":
                # accepted if the month survives as a word OR as a numeric date
                word = [k for k, v in MONTHS.items() if v == x[1]][0]
                ok = any(w in low for w in (word, word[:3]))
                if not ok and not DATE_NUM.search(r["output"]):
                    flags["date"].append((r["n"], genre, r["sample"], word))
            else:
                flags["date"].append((r["n"], genre, r["sample"], repr(x)))
        for x in sorted(on - dn):
            flags["added_number"].append((r["n"], genre, r["sample"], x))
        for x in sorted(dnm):
            toks = [t.lower() for t in x.split()]
            if not any(t in low for t in toks):
                flags["name"].append((r["n"], genre, r["sample"], x))
    for k, v in flags.items():
        print("== %s: %d flags" % (k, len(v)))
        for row in v:
            print("   n=%d %s s%d  %s" % row)
    print("TOTAL flags:", sum(len(v) for v in flags.values()))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results.json")