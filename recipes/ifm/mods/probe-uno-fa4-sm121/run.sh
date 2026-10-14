#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Purpose: probe whether SGLang's native UNO speculative-decoding path can run on
#          NVIDIA GB10 (DGX Spark, CC 12.1) by relaxing its attention-backend gate
#          from the literal string "fa3" to also accept "fa4".
# Origin: written from source reading, not from a hardware trial. See
#          recipes/ifm/K2-7B-MODEL-OPTIMIZATION-WORK.md section 6.
set -euo pipefail

#####################################################################
# README
#####################################################################
# WHY THIS MOD EXISTS
#
# IFM/K2-Horizon-7B-Uno is served by SGLang's in-tree UNO speculative algorithm
# (--speculative-algorithm UNO --uno-lora-path ...), which is present in
# v0.5.20. Two independent gates make it unreachable on a DGX Spark:
#
#   1. arg_groups/speculative_hook.py::_handle_uno ends with
#          if (prefill_backend, decode_backend) != ("fa3", "fa3"):
#              raise ValueError("UNO requires FA3 for both prefill and decode ...")
#   2. layers/attention/attention_registry.py::create_flashattention_v3_backend
#      asserts `(major == 8 and not use_mla) or major == 9`, i.e. SM80/SM90 only.
#      Its own message says: "Please use --attention-backend flashinfer".
#
# GB10 is compute capability (12, 1), so both refuse it. UNO is therefore
# unbootable on Spark as shipped.
#
# WHY "fa4" MIGHT BE THE RIGHT ANSWER
#
# create_flashattention_v4_backend builds *the same class*, FlashAttentionBackend,
# with fa_impl_ver=4, and has NO capability assert. Inside the backend
# (flashattention_backend.py:274-314) the version selects only the kernel import:
#
#     if self.fa_impl_ver == 3:  from sgl_kernel.flash_attn import (...)
#     elif self.fa_impl_ver == 4:
#         if device_capability[0] == 12:
#             from sglang.kernels.ops.attention.flash_attention_v4_sm120 import (...)
#
# So on any CC-12 device "fa4" resolves to a DEDICATED SM12x FlashAttention-4
# kernel, in the same backend class UNO asks for. Since UNO's requirement is a
# literal string comparison rather than a capability query, the most probable
# reading is that it means "needs FlashAttentionBackend" and was written as
# ("fa3","fa3") because upstream only validates on Hopper.
#
# THAT IS A HYPOTHESIS, NOT A FACT. This mod is a probe. It is expected to be
# wrong in one of two ways, and both are informative:
#   * FA4's CUTE package is absent from the image -> import error at backend
#     construction. The probe step below detects this BEFORE the launch.
#   * UNO depends on FA3-specific metadata somewhere this reading did not trace
#     -> failure inside the first decode step or during CUDA-graph capture.
#
# WHAT THIS MOD DELIBERATELY DOES NOT DO
#
# It does NOT touch the fa3 capability assert in attention_registry.py. If UNO
# can only run by neutering that assert, we want it to fail loudly rather than
# reach an uncompiled kernel. One variable changes: the UNO gate.
#
# SAFETY
#
# All edits are anchored and idempotent. If an anchor does not match EXACTLY once,
# the mod refuses to write and exits non-zero, rather than leaving a half-patched
# tree. It then re-imports the patched module to prove the file is still valid
# Python -- so a bad patch fails at hook time, not nine minutes into a weight load.
# Set UNO_FA4_GATE=0 to restore stock behaviour without rebuilding anything.
#
# Verify the anchor before trusting a new base image:
#   python3 -c "import sglang,pathlib,sys; \
#     p=pathlib.Path(sglang.__file__).parent/'srt/arg_groups/speculative_hook.py'; \
#     sys.exit(0 if p.read_text().count('!= (\"fa3\", \"fa3\")')==1 else 1)"
#####################################################################

#####################################################################
# Metadata
#####################################################################
MOD_NAME="probe-uno-fa4-sm121"
MOD_DESCRIPTION="Probe: allow UNO speculative decoding to use fa4 on GB10 (CC 12.1)"
MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

#####################################################################
# Behaviour
#####################################################################
# Default ON, because this mod is only mounted by the Uno probe recipe.
# UNO_FA4_GATE=0 restores the stock FA3-only gate.
export UNO_FA4_GATE="${UNO_FA4_GATE:-1}"

# Single source of truth for the admitted backend set. Declared HERE, exported,
# and read by both the patch step and the post-patch check -- previously the two
# had independent defaults ("fa3,fa4,triton" vs "fa3,fa4"), so the checker could
# validate a subset and pass while the emitted gate admitted more. Whatever this
# is, the recipe's --attention-backend must match it.
export UNO_ATTN_BACKENDS="${UNO_ATTN_BACKENDS:-fa3,fa4,triton}"

CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
mkdir -p "${LOGDIR}"
LOG="${LOGDIR}/${MOD_NAME}.log"
log() { printf '%s [%s] %s\n' "$(date -Ins)" "${MOD_NAME}" "${*}" | tee -a "${LOG}"; }
# Mods run as ROOT. Everything this mod writes under the mount must be re-owned to
# the mount's real owner before the server starts as uid 1000, or the next launch
# of this model key fails with PermissionError. Derive the ids from the mount, the
# way AGENTS.md specifies -- hardcoding 1000:1000 is wrong on hosts that differ.
# See .swival/memory/sparkrun-notes.md ("A pre_exec mod runs as ROOT ...").
export USER_UID="${USER_UID:-$(stat -c '%u' "${CACHEDIR}" 2>/dev/null || echo 1000)}"
export USER_GID="${USER_GID:-$(stat -c '%g' "${CACHEDIR}" 2>/dev/null || echo 1000)}"
reown() { chown -R "${USER_UID}:${USER_GID}" "${@}" 2>/dev/null || true; }

#####################################################################
# Step 1 - probe the FA4 SM12x path BEFORE attempting to boot
#
# Cheap, read-only, and it is the single fact that decides whether the whole
# Uno arm is "one mod away" or "waiting on a dependency". Run it first and log
# it, so a boot failure downstream is attributable without re-running anything.
#####################################################################
log "probing FA4 availability (this does not modify anything)"
# Output is teed into the mod log, because the README tells the operator to read
# the anchor count and the CUTE result from that file -- previously the probe
# printed to stdout only and the log held none of it.
#
# The probe runs with `set +e` so a crash does not abort the launch (the patch is
# the point), but the pipeline exit status is captured and a crash is recorded as
# an explicit PROBE-CRASH line -- so the log distinguishes "probe ran and said
# FAIL" from "probe never ran". Output is captured with PIPESTATUS, not `|| true`,
# because `|| true` would also have hidden the crash.
set +e
python3 - <<'PY' 2>&1 | tee -a "${LOG}"
import importlib
import sys, torch

def probe(name, fn):
    try:
        detail = fn()
        print("PROBE %-42s OK   %s" % (name, detail))
    except Exception as exc:
        print("PROBE %-42s FAIL %s: %s" % (name, type(exc).__name__, exc))

def cc():
    if not torch.cuda.is_available():
        return "no CUDA device visible in this container"
    return "torch.cuda.get_device_capability() = %r" % (torch.cuda.get_device_capability(),)

def sm12x_module():
    m = importlib.import_module(
        "sglang.kernels.ops.attention.flash_attention_v4_sm120")
    names = [n for n in ("flash_attn_varlen_func", "flash_attn_with_kvcache",
                         "get_flash_attention_v4_sm120_runtime_policy")
             if hasattr(m, n)]
    return "imported; exports %s" % (names,)

def cute_backend():
    # The CUTE FA4 package. Note there are TWO, and the default runtime path uses
    # the VENDORED one, not the pip one:
    #   flash_attention_v4.py imports `sglang.kernels.ops.attention.flash_attn.cute`
    #   unless SGLANG_INKLING_FA4_USE_PIP=1, in which case it imports
    #   `flash_attn.cute` (the pip flash-attn-4 dev stack). "FlashAttention-4 CUTE
    #   is not available. Install flash-attn-4 ..." fires when the import that
    #   this env selects fails, so the probe must check the SELECTED one or it
    #   can report a false negative. Verified 2026-09-21 with no GPU present: a
    #   locally-present sglang image ships the vendored package and both import,
    #   and the v0.5.20 source on GitHub has the same vendored-first logic.
    #   Report both so a mismatch (one present, the other not) is visible.
    import os
    use_pip = os.environ.get("SGLANG_INKLING_FA4_USE_PIP") == "1"
    primary = "flash_attn.cute" if use_pip else "sglang.kernels.ops.attention.flash_attn.cute"
    secondary = "sglang.kernels.ops.attention.flash_attn.cute" if use_pip else "flash_attn.cute"
    m = importlib.import_module(primary)
    try:
        importlib.import_module(secondary)
        other = "also OK"
    except Exception as exc:
        other = "absent (%s)" % type(exc).__name__
    return "selected=%s (%s) from %s; other path %s" % (
        primary, "pip" if use_pip else "vendored", getattr(m, "__file__", "?"), other)

def cute_varlen():
    # The actual symbol flash_attention_v4.py binds at import time. This is the
    # closest a no-GPU probe can get to "the FA4 path is wired", and it is the
    # symbol whose absence produces the "Install flash-attn-4" error.
    from sglang.kernels.ops.attention import flash_attention_v4 as f4
    ok = f4.is_flash_attention_v4_available()
    err = getattr(f4, "_flash_attn_import_error", None)
    return "is_flash_attention_v4_available()=%r%s" % (
        ok, "" if ok else " import_error=%r" % (err,))

def fa3_gate():
    # Locate the anchor the SAME way Step 2 locates its write target
    # (importlib.util.find_spec), so the probe's "anchor count" always describes
    # the file the patch will actually edit. Two locators can resolve to
    # different trees when a container carries both an editable and a
    # site-packages copy and only one is imported.
    import importlib.util, pathlib
    p = (pathlib.Path(importlib.util.find_spec("sglang").origin).parent
         / "srt" / "arg_groups" / "speculative_hook.py")
    n = p.read_text(encoding="utf-8").count('!= ("fa3", "fa3")')
    return "anchor count = %d at %s" % (n, p)

print("device_capability: %s" % (cc(),))
probe("sglang CC-12 FA4 shim", sm12x_module)
probe("CUTE package (selected path)", cute_backend)
probe("FA4 varlen available", cute_varlen)
probe("UNO fa3 gate anchor", fa3_gate)
print("PROBE NOTE a green FA4 shim import does NOT prove the kernels are "
      "compiled for sm_121; it proves the Python shim resolves. The Uno "
      "break-even acceptance (WORK section 6.6) is what decides whether it is "
      "worth running at all.")
PY
probe_rc=${PIPESTATUS[0]}
set -e
if [[ "${probe_rc}" != "0" ]]; then
  log "PROBE-CRASH: the FA4 probe exited ${probe_rc} (see output above). It did" \
      "NOT report PASS or FAIL for the CUTE package; do not read that as 'OK'." \
      "The gate patch below is still attempted."
fi
reown "${CACHEDIR}"

#####################################################################
# Step 2 - the patch
#####################################################################
if [[ "${UNO_FA4_GATE}" != "1" ]]; then
  log "UNO_FA4_GATE=${UNO_FA4_GATE} - leaving sglang unpatched (stock FA3-only gate)"
  log "Done (no-op)."
  exit 0
fi

python3 - <<'PY'
import ast, importlib.util, os, pathlib, re, sys

# Which backends UNO's gate may admit. Default is the UNION of the two probe
# lanes, deliberately: this gate is a permission, not a selection -- what sglang
# actually builds is decided by --attention-backend, which a recipe can set with
# the verified `-o attention_backend=...`. Admitting triton costs nothing when
# the recipe asks for fa4, and it means both lanes are runnable with NO
# environment propagation, which is the one mechanism here that could not be
# confirmed from source. Narrow to a single lane with
# UNO_ATTN_BACKENDS=fa3,fa4 when you want the gate itself to be the constraint.
raw = os.environ.get("UNO_ATTN_BACKENDS", "fa3,fa4,triton")
allowed = tuple(b.strip() for b in raw.split(",") if b.strip())
if not allowed or any(not b.replace("_", "").isalnum() for b in allowed):
    print("uno-fa4-probe: refusing UNO_ATTN_BACKENDS=%r" % raw)
    sys.exit(1)
if "fa3" not in allowed:
    # Never narrow below what stock sglang already permits: a probe that makes
    # the gate stricter can produce a "UNO rejected my backend" failure that
    # looks like the finding when it is only the knob.
    allowed = ("fa3",) + allowed
print("uno-fa4-probe: gate will accept %s" % (allowed,))

target = pathlib.Path(importlib.util.find_spec("sglang").origin).parent / "srt/arg_groups/speculative_hook.py"
src = target.read_text(encoding="utf-8")

# Exact bytes from v0.5.20 (speculative_hook.py:503-508). Anchored on the
# comparison itself, not on the message, so a reworded message does not silently
# stop the patch from applying while still leaving the gate in place.
OLD = '''    prefill_backend, decode_backend = attention_backends_of(resolved_view(server_args))
    if (prefill_backend, decode_backend) != ("fa3", "fa3"):
        raise ValueError(
            "UNO requires FA3 for both prefill and decode attention; "
            f"got prefill={prefill_backend!r}, decode={decode_backend!r}."
        )
'''

NEW = '''    prefill_backend, decode_backend = attention_backends_of(resolved_view(server_args))
    # [probe-uno-fa4-sm121] GB10 (DGX Spark, CC 12.1) cannot construct the fa3
    # backend: create_flashattention_v3_backend asserts major in {8, 9}. Accept
    # a configured set instead, so the gate stops being an arch-blind string
    # comparison. Probe: recipes/ifm/K2-7B-MODEL-OPTIMIZATION-WORK.md section 6.
    # Revert with UNO_FA4_GATE=0.
    _UNO_ALLOWED_BACKENDS = {TUPLE}
    if (
        prefill_backend not in _UNO_ALLOWED_BACKENDS
        or decode_backend not in _UNO_ALLOWED_BACKENDS
        or prefill_backend != decode_backend
    ):
        raise ValueError(
            "UNO requires a matching backend from "
            f"{_UNO_ALLOWED_BACKENDS} for prefill and decode attention; "
            f"got prefill={prefill_backend!r}, decode={decode_backend!r}."
        )
'''.replace("{TUPLE}", repr(allowed))

if NEW in src:
    print("uno-fa4-probe: already patched for this backend set, nothing to do")
    sys.exit(0)

# Already patched, but for a DIFFERENT backend set? The OLD anchor is gone, so
# the naive path below would report "found 0 ... the base image has changed" --
# a false accusation against a healthy image that also aborts the launch. Detect
# it explicitly and rewrite just the tuple, keeping this mod idempotent across
# backend-set changes (e.g. a lane-B run after a lane-A run on the same node).
existing = re.search(
    r"^\s*_UNO_ALLOWED_BACKENDS = (\([^)]*\))\s*$", src, re.M)
if existing is not None and OLD not in src:
    try:
        current = tuple(ast.literal_eval(existing.group(1)))
    except (ValueError, SyntaxError):
        current = None
    if current == allowed:
        print("uno-fa4-probe: already patched for this backend set, nothing to do")
        sys.exit(0)
    src = src[:existing.start(1)] + repr(allowed) + src[existing.end(1):]
    target.write_text(src, encoding="utf-8")
    print("uno-fa4-probe: re-patched gate %r -> %r in %s"
          % (current, allowed, target))
    sys.exit(0)

count = src.count(OLD)
if count != 1:
    print("uno-fa4-probe: REFUSING TO WRITE - expected exactly 1 anchor, found %d "
          "in %s. The base image has changed; update this mod." % (count, target))
    sys.exit(1)

target.write_text(src.replace(OLD, NEW, 1), encoding="utf-8")
print("uno-fa4-probe: patched %s" % target)
PY

#####################################################################
# Step 3 - post-patch import smoke test
#
# Proves the patched file still parses and that _handle_uno is still reachable.
# Without this, a syntax error costs a full image start plus a weight load
# before it surfaces.
#
# THE CHECK MUST NOT ASSUME A QUOTE STYLE. Step 2 emits the tuple through
# repr(), i.e. `('fa3', 'fa4', 'triton')` with SINGLE quotes. An earlier version
# of this step searched the patched source for `"fa3"` (double-quoted) and so
# failed its own check on a perfectly good patch -- then `set -e` aborted the
# launch, and the log said "patched gate is missing backends", pointing at the
# patch instead of at the checker. So this step now parses the literal back out
# of the patched source with ast, which is quote-agnostic and also proves the
# emitted text is a real tuple rather than a string that happens to contain the
# backend names.
#####################################################################
python3 - <<'PY'
import ast, importlib, inspect, os, re, sys

try:
    m = importlib.import_module("sglang.srt.arg_groups.speculative_hook")
    fn = getattr(m, "_handle_uno", None)
    assert fn is not None and callable(fn), "_handle_uno missing or not callable"
    src = inspect.getsource(fn)
    # Check the mechanism landed, not a brand name: grepping for "FA4" would pass
    # on a stale patch and fail on a triton-only one.
    if "_UNO_ALLOWED_BACKENDS" not in src:
        print("uno-fa4-probe: post-patch source lacks _UNO_ALLOWED_BACKENDS")
        sys.exit(1)
    mm = re.search(r"_UNO_ALLOWED_BACKENDS\s*=\s*(\([^)]*\))", src)
    if not mm:
        print("uno-fa4-probe: could not parse _UNO_ALLOWED_BACKENDS assignment")
        sys.exit(1)
    try:
        installed = tuple(ast.literal_eval(mm.group(1)))
    except (ValueError, SyntaxError) as exc:
        print("uno-fa4-probe: _UNO_ALLOWED_BACKENDS is not a literal tuple: %s" % exc)
        sys.exit(1)
    if not installed or not all(isinstance(b, str) for b in installed):
        print("uno-fa4-probe: _UNO_ALLOWED_BACKENDS is not a non-empty tuple of str")
        sys.exit(1)
    # The gate must keep fa3 (never narrow below stock) and admit at least one
    # GB10-capable lane. Fail closed if the patch that landed is not the one the
    # operator asked for.
    want = tuple(b.strip() for b in
                 os.environ.get("UNO_ATTN_BACKENDS", "fa3,fa4,triton").split(",")
                 if b.strip())
    if "fa3" not in installed:
        print("uno-fa4-probe: installed gate dropped fa3: %r" % (installed,))
        sys.exit(1)
    missing = [b for b in want if b not in installed]
    if missing:
        print("uno-fa4-probe: patched gate is missing requested backends %s "
              "(installed %r)" % (missing, installed))
        sys.exit(1)
except Exception as exc:
    print("uno-fa4-probe: post-patch import FAILED: %s: %s" % (type(exc).__name__, exc))
    sys.exit(1)
print("uno-fa4-probe: post-patch import OK, gate=%r" % (installed,))
PY

# Step 1 and Step 3 both IMPORT the engine (that is how the anchor is located and
# the patch is proven), and a root-run `import sglang` triggers flashinfer's JIT
# against this bind-mounted cache, dropping root-owned files uid 1000 can then
# neither write nor unlink -- poisoning every later launch of this model key.
# Re-own the WHOLE mount, not just the log dir, after the imports. This is
# .swival/memory/sparkrun-notes.md's "most expensive sparkrun gotcha".
reown "${CACHEDIR}"
log "Done. Launch with --attention-backend matching UNO_ATTN_BACKENDS (this recipe uses fa4)."
log "Expect either a clean boot or a decode-time failure; both are results."
