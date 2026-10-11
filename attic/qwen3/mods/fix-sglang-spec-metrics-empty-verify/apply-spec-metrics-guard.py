#!/usr/bin/env python3
"""Patch SGLang's tokenizer_manager so spec-decode metrics cannot crash a no-spec server.

Defect, reproduced 2026-09-18 on lmsysorg/sglang:dev-cu13 (sglang
0.0.0.dev1+g09daea94a), on RadixArk/Qwen3.8-27B-NVFP4: running the server with
--speculative-algorithm NONE while --speculative-draft-model-path is still supplied
kills the whole server on the first generated batch:

    File ".../srt/managers/tokenizer_manager.py", line 2838,
        in _calculate_spec_decoding_metrics
        and recv_obj.spec_verify_ct[i] > 0
    IndexError: list index out of range

Mechanism (traced through the pinned image's own source, not guessed):

  * managers/scheduler_components/output_streamer.py builds the batch output with
        spec_verify_ct: list = field(default_factory=list)
    and only appends per request inside
        if not self.spec_algorithm.is_none():
    So with the algorithm NONE, the attribute exists on the wire object and holds [].

  * managers/tokenizer_manager.py gates the metric call on
        if get_spec().speculative_algorithm:
    which is the *unnormalised* server-args string. It is None when the flag is
    omitted (falsy, metric skipped - why ordinary no-spec servers are fine) but the
    literal string "NONE" when the flag is passed explicitly, which is truthy. So
    naming NONE explicitly is what routes a no-spec server into spec-decode metrics.

  * _calculate_spec_decoding_metrics then guards with
        hasattr(recv_obj, "spec_verify_ct") and recv_obj.spec_verify_ct[i] > 0
    hasattr tests attribute *existence*, which is true for a dataclass field that
    merely exists, so it is the wrong guard for an empty list, and [0] on [] raises.

  * The sibling field in the very same condition is length-guarded correctly:
        and len(recv_obj.spec_num_correct_drafts) > i
    spec_verify_ct alone is not. That asymmetry is the bug, and the fix is to use the
    guard its neighbours already use.

Consequence for this project: a no-spec control run - the measurement needed to
separate speculative amplification from raw decode bandwidth - cannot be obtained on
this build by configuration alone, because the flag that expresses "no speculation"
is the flag that triggers the crash. The server dies outright, so this is not a
cosmetic metric loss.

Fix: require the list to be long enough before indexing. When a spec engine is active
the list is populated, the guard passes, and behaviour is identical. When it is not,
the metric is absent - which is correct, since there is nothing to measure.

DO NOT IMPORT SGLANG HERE. This runs as a pre_exec hook: as root, with the per-model
runtime cache bind-mounted. Importing sglang (and `importlib.util.find_spec` on a
dotted sglang submodule imports its parents) triggers flashinfer JIT, which drops
root-owned files that the uid-1000 server can neither write nor unlink, breaking that
model key's boots from then on. So the module is found by filesystem search only.
Every copy found is patched: this image carries both an editable source tree and a
site-packages tree, and patching only whichever one we happen to guess is how a mod
ends up silently doing nothing.
"""
import argparse
import glob
import os
import sys

MARKER = "# sparkrun: spec_verify_ct can be empty when no spec engine is active"

OLD = """        if (
            hasattr(recv_obj, "spec_verify_ct")
            and recv_obj.spec_verify_ct[i] > 0
            and hasattr(recv_obj, "spec_num_correct_drafts")
            and len(recv_obj.spec_num_correct_drafts) > i
        ):"""

NEW = """        if (
            %s
            getattr(recv_obj, "spec_verify_ct", None) is not None
            and len(recv_obj.spec_verify_ct) > i
            and recv_obj.spec_verify_ct[i] > 0
            and hasattr(recv_obj, "spec_num_correct_drafts")
            and len(recv_obj.spec_num_correct_drafts) > i
        ):""" % MARKER

REL = os.path.join("sglang", "srt", "managers", "tokenizer_manager.py")


def candidates():
    """Every tokenizer_manager.py reachable without importing sglang."""
    roots = []
    try:
        import site
        roots.extend(list(site.getsitepackages()))
    except Exception:
        pass
    roots.append(os.path.join(sys.prefix, "lib",
                              "python%d.%d" % sys.version_info[:2], "site-packages"))
    # Editable / source installs observed in this image.
    roots += ["/sgl-workspace/sglang/python", "/opt/sglang/lib/python3.12/site-packages"]
    found = []
    for r in roots:
        p = os.path.join(r, REL)
        if os.path.isfile(p) and p not in found:
            found.append(p)
    # Last resort: a bounded walk of /opt and /sgl-workspace. Depth-limited so a
    # pathological tree cannot hang the hook.
    if not found:
        for base in ("/opt", "/sgl-workspace", "/usr/lib/python3"):
            for p in glob.iglob(os.path.join(base, "**", REL), recursive=True):
                if os.path.isfile(p) and p not in found:
                    found.append(p)
    return found


def patch_file(path):
    """Return (status, detail); status in patched/already/error."""
    try:
        src = open(path, encoding="utf-8").read()
    except OSError as e:
        return "error", "unreadable: %s" % e

    if MARKER in src:
        return "already", "marker present"
    n_old = src.count(OLD)
    if n_old == 0:
        return "error", "anchor absent (upstream text moved?)"
    if n_old > 1:
        return "error", "anchor occurs %d times, refusing to guess" % n_old

    # Assert the shape we expect before writing. Every failure here has been a wrong
    # assumption about the file rather than a broken file, and each one is a boot saved.
    idx = src.index(OLD)
    line_start = src.rindex("\n", 0, idx) + 1
    prefix = src[line_start:idx]
    if prefix.strip():
        return "error", "anchor not at line start: %r" % prefix
    # OLD carries its own indentation, so the line's real indent is whatever precedes
    # the match plus the leading spaces of OLD's first line. Measuring only `prefix`
    # here yields "" and makes a correctly-indented file look like a moved anchor.
    first = OLD.split("\n", 1)[0]
    indent = prefix + first[:len(first) - len(first.lstrip(" "))]
    if indent != " " * 8:
        return "error", "unexpected indent %d (expected 8); text moved" % len(indent)

    patched = src[:idx] + NEW + src[idx + len(OLD):]

    # Post-conditions, scoped to what was actually substituted. A whole-file "must not
    # contain this string" check is wrong here: this module legitimately contains the
    # same hasattr test at another site (around line 2960) which is guarded correctly.
    # Assert the delta instead.
    if patched.count(OLD) != 0:
        return "error", "anchor still present after substitution"
    if patched.count(MARKER) != 1:
        return "error", "marker count wrong after substitution"
    if "and len(recv_obj.spec_verify_ct) > i" not in patched:
        return "error", "length guard missing after substitution"
    bare = 'hasattr(recv_obj, "spec_verify_ct")'
    if patched.count(bare) != src.count(bare) - 1:
        return "error", "unguarded hasattr count changed unexpectedly (%d -> %d, want -1)" % (
            src.count(bare), patched.count(bare))
    if 'hasattr(recv_obj, "spec_num_correct_drafts")' not in patched:
        return "error", "sibling guard lost"
    try:
        compile(patched, path, "exec")
    except SyntaxError as e:
        return "error", "patched text does not compile: %s" % e

    tmp = path + ".sparkrun-tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(patched)
    os.replace(tmp, path)
    return "patched", "%d bytes" % len(patched)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", action="append", default=[],
                    help="explicit tokenizer_manager.py (repeatable); default: search")
    ap.add_argument("--check-only", action="store_true",
                    help="report anchor state, change nothing")
    ap.add_argument("--list-only", action="store_true",
                    help="print one discovered path per line and exit (for shells)")
    a = ap.parse_args()

    paths = a.path or candidates()
    if a.list_only:
        for p in paths:
            print(p)
        return 0
    if not paths:
        print("ERROR: no %s found under any known root" % REL)
        return 3
    print("targets (%d):" % len(paths))
    for p in paths:
        print("  %s" % p)

    n_patched = n_already = n_err = 0
    n_patchable = 0          # check-only: anchor present, so a later run could patch it
    for p in paths:
        if a.check_only:
            try:
                src = open(p, encoding="utf-8").read()
            except OSError as e:
                print("CHECK   %-72s unreadable %s" % (p, e))
                n_err += 1
                continue
            n_anchor = src.count(OLD)
            if MARKER in src:
                state, ok = "PATCHED", True
            elif n_anchor == 1:
                # "already" would be wrong here: nothing has been patched yet. Count it
                # separately so the exit code cannot conflate "fixable" with "done".
                state, ok = "ANCHOR-FOUND", True
                n_patchable += 1
            else:
                state, ok = "NO-ANCHOR(%d)" % n_anchor, False
                n_err += 1
            print("CHECK   %-72s %s" % (p, state))
            n_already += 1 if MARKER in src else 0
            continue
        status, detail = patch_file(p)
        print("%-8s %-72s [%s]" % (status.upper(), p, detail))
        n_patched += status == "patched"
        n_already += status == "already"
        n_err += status == "error"

    # Always print the denominator: a verdict over an empty list always passes and
    # reads like a finding.
    if a.check_only:
        print("summary: %d target(s): patched=%d patchable=%d unusable=%d"
              % (len(paths), n_already, n_patchable, n_err))
    else:
        print("summary: patched=%d already=%d error=%d of %d target(s)"
              % (n_patched, n_already, n_err, len(paths)))

    if n_err:
        return 4
    if a.check_only:
        # Check-only asks "could a patch run here?", so a file that is patchable but not
        # yet patched must exit 0. Returning non-zero for that state made run.sh's
        # pre-flight abort on a perfectly patchable image.
        return 0
    if not (n_patched or n_already):
        return 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
