#!/usr/bin/env python3
"""Negative control for the tokenizer_manager spec-metrics guard.

Extracts _calculate_spec_decoding_metrics from a REAL tokenizer_manager.py and
executes it with stubbed module globals. No sglang import, so it is safe to run
anywhere, and it cannot pass by testing a copy of the function I typed myself: the
source text is read from the very file the patcher edits.

The failure under test is a batch-output object whose spec_verify_ct EXISTS but is
EMPTY - exactly what the scheduler emits when the spec algorithm is NONE - while the
completion fields are populated. Unguarded code does [][0] and raises IndexError.

Exit codes:
  0  the file as it stands does not crash on that input (patched, or fixed upstream)
  1  it does crash (unpatched)
  2  the harness could not run - which must never be read as a result about the patch
"""
import argparse
import os
import re
import sys
import textwrap
import typing

FN = "_calculate_spec_decoding_metrics"
HARNESS_FAIL = 2
# The exact unguarded conjunct this mod replaces. If this text is absent the file has
# moved and every conclusion below is void, so we refuse rather than guess.
UNGUARDED = 'hasattr(recv_obj, "spec_verify_ct")'


class Bag:
    """Stand-in for a dataclass batch output / config bag."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def extract_function(path):
    lines = open(path, encoding="utf-8").read().splitlines()
    start = None
    for i, l in enumerate(lines):
        if l.startswith("    def %s(" % FN):
            start = i
            break
    if start is None:
        raise RuntimeError("%s not found in %s" % (FN, path))
    end = len(lines)
    for j in range(start + 1, len(lines)):
        s = lines[j]
        if not s.strip():
            continue
        if re.match(r"^    (def |@|class )", s) or not s.startswith("    "):
            end = j
            break
    body = textwrap.dedent("\n".join(lines[start:end]))
    if "spec_verify_ct" not in body:
        raise RuntimeError("extracted body lacks spec_verify_ct; extraction is wrong")
    if ("def %s" % FN) not in body:
        raise RuntimeError("dedent destroyed the def line")
    return body, start + 1, end


def build_env(num_draft_tokens=4):
    """Globals for exec'ing the extracted def.

    These MUST be real typing constructs, not object/list stand-ins. A def statement
    evaluates its annotations at definition time on Python < 3.14, so `Union[...]` with
    Union=object raises "type 'object' is not subscriptable" - which made this harness
    pass on the 3.14 dev box and fail inside the 3.12 container. The image runtime is
    3.12, so the harness has to work there; using typing makes it version-independent.
    """
    return {
        "get_spec": lambda: Bag(speculative_num_draft_tokens=num_draft_tokens),
        "_ragged_verify_cap_accept": lambda: False,
        "Dict": typing.Dict, "Any": typing.Any, "Union": typing.Union,
        "Optional": typing.Optional, "List": typing.List,
        "BatchStrOutput": type("BatchStrOutput", (), {}),
        "BatchEmbeddingOutput": type("BatchEmbeddingOutput", (), {}),
        "BatchTokenIDOutput": type("BatchTokenIDOutput", (), {}),
    }


def make_recv(spec_verify_ct, n=1, correct=None, complete=None):
    """A batch output as the wire dataclasses declare it: every spec field exists, and
    holds [] when the scheduler ran with algorithm NONE. Field list taken from
    scheduler_components/output_streamer.py, which defaults each one with
    default_factory=list; the one accessed without a getattr guard
    (spec_correct_drafts_histogram) is included deliberately, because a stub that
    omits it would raise AttributeError and look like a finding."""
    return Bag(
        spec_verify_ct=spec_verify_ct,
        spec_num_correct_drafts=correct if correct is not None else [3] * n,
        completion_tokens=complete if complete is not None else [7] * n,
        spec_num_cap_tokens=[],
        spec_num_block_accept_tokens=[],
        spec_correct_drafts_histogram=[],
        spec_cap_lens_histogram=[],
    )


def compile_fn(body):
    """Execute the extracted def in a stubbed module namespace and return the function.
    The index argument the function takes is a per-request offset, supplied per case."""
    ns = {}
    exec(body, build_env(), ns)
    if FN not in ns:
        raise RuntimeError("exec did not bind %s; extraction is malformed" % FN)
    return ns[FN]


def run_case(fn, name, recv, i, expect, require_metrics=False):
    """Returns (passed, crashed). `crashed` is the observation; `passed` is only the
    verdict relative to `expect`. Callers must decide on `crashed`, never on `passed`,
    because a correctly-patched file passes by NOT crashing and an unpatched one passes
    by crashing - the two are indistinguishable through `passed` alone."""
    meta = {}
    try:
        fn(None, meta, recv, i)
    except IndexError as e:
        outcome = "IndexError: %s" % e
        ok, crashed = (expect == "crash"), True
    except Exception as e:
        print("  %-36s UNEXPECTED %s: %s" % (name, type(e).__name__, e))
        return (None, None)
    else:
        got = sorted(k for k in meta if k.startswith("spec"))
        outcome = "ok, %d spec keys%s" % (len(got), "" if got else " (metrics absent)")
        ok, crashed = (expect == "ok"), False
        if ok and require_metrics and not got:
            ok = False
            outcome += " - but metrics were REQUIRED (guard stubbed the metric out)"
    print("  %-36s %-52s %s" % (name, outcome, "pass" if ok else "**FAIL**"))
    return (ok, crashed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="tokenizer_manager.py to examine")
    a = ap.parse_args()
    if not os.path.isfile(a.path):
        print("harness error: no such file: %s" % a.path)
        return HARNESS_FAIL

    try:
        body, ln0, ln1 = extract_function(a.path)
    except RuntimeError as e:
        print("harness error: %s" % e)
        return HARNESS_FAIL
    print("extracted %s from %s lines %d-%d"
          % (FN, os.path.basename(a.path), ln0, ln1))

    results = {}
    crashed = {}
    # What case A should expect depends on the file: unguarded files crash, guarded
    # ones must not. Expecting "crash" unconditionally would print **FAIL** on a
    # correctly patched file, which reads like a broken mod.
    expect_a = "crash" if UNGUARDED in body else "ok"
    print("\nA  the defect: spec_verify_ct exists but is [] (what NONE emits)")
    print("   file is %s, so expecting %s"
          % ("UNGUARDED" if UNGUARDED in body else "already GUARDED",
             "IndexError" if expect_a == "crash" else "no crash"))
    results["A"], crashed["A"] = run_case(compile_fn(body), "empty list, i=0",
                                          make_recv([]), 0, expect_a)

    print("\nB  healthy spec path must still compute metrics (guards against 'fixed' = disabled)")
    results["B"], crashed["B"] = run_case(compile_fn(body), "populated list, i=0",
                                          make_recv([5], correct=[15], complete=[20]),
                                          0, "ok", require_metrics=True)

    print("\nC  positive control: substitute a correct guard, same input, must NOT crash")
    if UNGUARDED not in body:
        print("  the unguarded conjunct is absent, so this file is already guarded")
        results["C"], crashed["C"] = True, False
    else:
        fixed = body.replace(UNGUARDED,
                             '(recv_obj.spec_verify_ct is not None '
                             'and len(recv_obj.spec_verify_ct) > i)')
        if fixed == body:
            print("  harness error: could not synthesize the guarded variant")
            return HARNESS_FAIL
        results["C"], crashed["C"] = run_case(compile_fn(fixed),
                                              "guarded variant, empty list",
                                              make_recv([]), 0, "ok")

    if any(v is None for v in results.values()):
        print("\nHARNESS INVALID: a case raised an unexpected exception type")
        return HARNESS_FAIL
    if crashed["C"]:
        print("\nHARNESS INVALID: the positive control still crashed, so 'no crash' "
              "in case A would mean nothing")
        return HARNESS_FAIL
    if crashed["B"] or not results["B"]:
        print("\nHARNESS INVALID: the healthy path did not produce metrics, so the "
              "stubs are wrong")
        return HARNESS_FAIL

    # Decisive observation, not pass/fail: did the real file crash on an empty list?
    patched = not crashed["A"]
    print("\nVERDICT: this file %s guard empty spec_verify_ct"
          % ("DOES" if patched else "does NOT"))
    print("(healthy path still emits metrics, so a pass is not the metric being stubbed out)")
    return 0 if patched else 1


if __name__ == "__main__":
    sys.exit(main())
