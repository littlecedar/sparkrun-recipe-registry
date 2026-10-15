#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Summarise agentic_horizon_probe JSONL arms into the degradation table.

Usage: python3 horizon-analyze.py horizon-*.jsonl
Prints one block per arm; each block is the evidence row for the lane docs.
"""
from __future__ import annotations

import json
import sys
from statistics import mean


def pct(xs, p):
    if not xs:
        return 0.0
    xs = sorted(xs)
    k = min(len(xs) - 1, int(round((p / 100) * (len(xs) - 1))))
    return xs[k]


def arm(path: str) -> dict:
    rows = [json.loads(l) for l in open(path) if l.strip()]
    valid = [r for r in rows if "loop" in r]
    reason_words = [r["loop"]["words"] for r in valid]
    repeats = [r["loop"]["max_window_repeat"] for r in valid]
    overlaps = [r["prior_shingle_overlap"] for r in valid
                if r.get("prior_shingle_overlap") is not None]
    rchars = [r["reasoning_chars"] for r in valid]
    finishes = {}
    for r in valid:
        finishes[r["finish_reason"]] = finishes.get(r["finish_reason"], 0) + 1
    try:
        summ = json.load(open(path + ".summary.json"))
    except FileNotFoundError:
        summ = {}
    valid_submits = invalid_submits = 0
    for r in valid:
        for tr in r.get("tool_results", []):
            if tr.get("name") == "submit_plan":
                if str(tr.get("result", "")).startswith("VALID"):
                    valid_submits += 1
                else:
                    invalid_submits += 1
    n = len(valid)
    third = max(1, n // 3)
    early = reason_words[:third]
    late = reason_words[-third:]
    return {
        "file": path.split("/")[-1], "family": summ.get("family"),
        "sampling": summ.get("sampling"), "calls": len(valid),
        "errors": len(rows) - len(valid),
        "max_prompt_tokens": summ.get("max_prompt_tokens"),
        "total_completion_tokens": summ.get("total_completion_tokens"),
        "session_max_window_repeat": summ.get("session", {}).get("max_window_repeat"),
        "session_words": summ.get("session", {}).get("words"),
        "session_max_repeat_excl_input": summ.get("session", {}).get(
            "max_window_repeat_excl_input"),
        "per_msg_repeat_max": max(repeats) if repeats else None,
        "msgs_repeat_ge2": sum(1 for x in repeats if x >= 2),
        "msgs_repeat_ge3": sum(1 for x in repeats if x >= 3),
        "overlap_max": max(overlaps) if overlaps else None,
        "overlap_mean": round(mean(overlaps), 3) if overlaps else None,
        "reason_words_early_mean": round(mean(early), 1) if early else None,
        "reason_words_late_mean": round(mean(late), 1) if late else None,
        "reason_chars_p50": pct(rchars, 50), "reason_chars_p95": pct(rchars, 95),
        "finish_reasons": finishes,
        "plan_valid_submits": valid_submits,
        "plan_invalid_submits": invalid_submits,
        "plan": summ.get("plan"),
        "elapsed_s": summ.get("elapsed_s"),
    }


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("jsonl", nargs="+",
                    help="agentic-horizon-probe JSONL arm(s) to summarise")
    for p in ap.parse_args().jsonl:
        a = arm(p)
        print("=" * 72)
        print(f"{a['file']}  family={a['family']}  sampling={a['sampling']}")
        print(f"  calls={a['calls']} errors={a['errors']} elapsed={a['elapsed_s']}s "
              f"max_prompt_tokens={a['max_prompt_tokens']} "
              f"total_completion_tokens={a['total_completion_tokens']}")
        print(f"  SESSION max_window_repeat={a['session_max_window_repeat']} "
              f"(excl-input {a['session_max_repeat_excl_input']}; {a['session_words']} words)")
        print(f"  per-msg repeat: max={a['per_msg_repeat_max']} "
              f">=2:{a['msgs_repeat_ge2']} >=3:{a['msgs_repeat_ge3']}")
        print(f"  cross-turn shingle overlap: max={a['overlap_max']} mean={a['overlap_mean']}")
        print(f"  reasoning words early/late mean: {a['reason_words_early_mean']} / "
              f"{a['reason_words_late_mean']}")
        print(f"  reasoning chars p50={a['reason_chars_p50']} p95={a['reason_chars_p95']}")
        print(f"  finish_reasons={a['finish_reasons']}")
        print(f"  final plan valid-order={bool(a['plan'])} "
              f"submit_plan valid/invalid={a['plan_valid_submits']}/{a['plan_invalid_submits']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
