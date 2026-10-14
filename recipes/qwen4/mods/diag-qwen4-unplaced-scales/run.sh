#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Make the Qwen4-Exp weight loader explain *why* it cannot place a `_scale`
# tensor, instead of dying on an assert that cannot even print the name.
#
# See README.md. Short version: qwen4_exp.py has
#     if name.endswith("_scale") and name not in params_dict:
#         assert abs(loaded_weight.item() - 1.0) < 1e-6, f"... in skipped {name}"
# and `.item()` raises while BUILDING that f-string, so the failing tensor name
# never reaches the log. The assert is right to fire (a non-scalar _scale is a
# real quantisation scale being dropped) but it is a dead end for diagnosis.
#
# This mod inserts a logging call as the first statement of that branch. It
# does NOT change control flow: the assert still fires and the load still
# fails. It deliberately does not relax the assert -- silently skipping real
# scales would load a model that serves plausible garbage, which is worse.
#
# Anchored: refuses to write unless the anchor matches exactly once, and the
# patched module must still import. Reowns the whole runtime cache at the end
# because importing sglang here triggers flashinfer's JIT as root, leaving a
# file uid 1000 cannot open -- the failure this recipe already documents for
# the fastsafetensors mods.
#####################################################################

MOD_NAME="diag-qwen4-unplaced-scales"
MOD_DESCRIPTION="Dump loader state when a _scale tensor cannot be placed (diagnostic only)"
MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

TIMEOUT="${MOD_TIMEOUT:-300}"
LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
USER_UID="$(stat -c '%u' /cache/runtime)"
USER_GID="$(stat -c '%g' /cache/runtime)"

log() { echo "[mod:${MOD_NAME}] $*"; }
mkdir -p "${LOGDIR}" 2>/dev/null || true

python3 - <<'PY'
import importlib.util
import os
import pathlib
import sys

FUNC = "_diag_unplaced_scales"
MARK = "# [" + "diag-unplaced-scales" + "]"

def _readable(p):
    """True only if we can actually OPEN the file.

    Path.exists() is insufficient: it returns False when stat() fails with
    EACCES, so a file that exists but is not readable by this uid is reported as
    missing. This mod's pre_exec may run as a different uid than the serving
    process, and the sglang tree is root-owned, so distinguish the two cases
    rather than repeating a confusing "not found".
    """
    try:
        with open(p, "rb"):
            return True
    except FileNotFoundError:
        return False
    except OSError as e:
        raise SystemExit(
            f"diag-unplaced-scales: {p} exists but is not readable by uid "
            f"{os.getuid()}: {type(e).__name__}: {e}. Run this mod with the same "
            f"privileges the serving process uses."
        )


def _find_qwen4():
    """Locate qwen4_exp.py.

    Do NOT rely on importlib.util.find_spec alone. The first launch of this mod
    reported "qwen4_exp.py not found" inside the serving container while sibling
    mods in that same container imported sglang happily, so the lookup itself is
    not dependable across sparkrun's pre_exec environments. Try find_spec, then
    the known editable-install root, then a bounded filesystem search, and report
    everything tried on failure so the next attempt is diagnosable.
    """
    tried = []
    try:
        spec = importlib.util.find_spec("sglang")
        tried.append(f"find_spec={getattr(spec, 'origin', None)}")
        if spec and spec.origin:
            c = pathlib.Path(spec.origin).parent / "srt/models/qwen4_exp.py"
            tried.append(f"spec-derived={c} readable={_readable(c) if c else False}")
            if c.exists() and _readable(c):
                return c
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        tried.append(f"find_spec raised {type(e).__name__}: {e}")

    for c in (
        pathlib.Path("/sgl-workspace/sglang/python/sglang/srt/models/qwen4_exp.py"),
        pathlib.Path("/usr/local/lib/python3/dist-packages/sglang/srt/models/qwen4_exp.py"),
    ):
        tried.append(f"literal={c}")
        if c.exists():
            if _readable(c):
                return c
            raise SystemExit(f"diag-unplaced-scales: {c} present but unreadable")

    import subprocess  # bounded search: this one filename, plausible roots only

    for root in ("/sgl-workspace", "/usr/local/lib", "/usr/lib/python3"):
        if not os.path.isdir(root):
            continue
        try:
            r = subprocess.run(
                ["find", root, "-maxdepth", "9", "-name", "qwen4_exp.py",
                 "-print", "-quit"],
                capture_output=True, text=True, timeout=90,
            )
            hit = r.stdout.strip().splitlines()
            if hit and _readable(pathlib.Path(hit[0])):
                return pathlib.Path(hit[0])
        except Exception:  # noqa: BLE001
            pass
    raise SystemExit(
        "diag-unplaced-scales: could not locate a readable qwen4_exp.py; tried "
        + "; ".join(tried)
    )


p = _find_qwen4()
print("diag-unplaced-scales: target", p)

s = p.read_text()
if FUNC in s:
    print("diag-unplaced-scales: already applied")
    sys.exit(0)

anchor = '                    if name.endswith("_scale") and name not in params_dict:\n'
n = s.count(anchor)
if n != 1:
    print(f"diag-unplaced-scales: anchor matched {n} times, expected exactly 1; "
          f"refusing to patch (base image has diverged?)")
    sys.exit(1)

s = s.replace(anchor, anchor + "                        " + FUNC + "(name, loaded_weight, params_dict)\n", 1)

body = '''

''' + MARK + ''' -- diagnostic only: explain an unplaceable `_scale` tensor, then
# let the caller's assert fire unchanged. Must never raise: a diagnostic that
# masks the real failure is worse than no diagnostic.
def ''' + FUNC + '''(name, loaded_weight, params_dict):
    try:
        import logging as _lg
        _log = _lg.getLogger("qwen4-diag")
        _log.error(
            "[diag] UNPLACED _scale name=%s shape=%s dtype=%s numel=%s",
            name, tuple(loaded_weight.shape), str(loaded_weight.dtype),
            loaded_weight.numel(),
        )
        _log.error("[diag] params_dict has %d entries", len(params_dict))

        def _show(title, keys, cap=48):
            _log.error("[diag] %s: %d keys", title, len(keys))
            for k in sorted(keys)[:cap]:
                pp = params_dict[k]
                try:
                    _log.error("        %-72s %-24s %s", k, type(pp).__name__,
                               tuple(pp.shape))
                except Exception:
                    _log.error("        %s <unprintable>", k)

        parts = name.split(".")
        for _cut in range(len(parts), 0, -1):
            _pref = ".".join(parts[:_cut]) + "."
            _keys = [k for k in params_dict if k.startswith(_pref)]
            if _keys:
                _log.error("[diag] deepest prefix owning ANY params: %r", _pref)
                _show("  its params", _keys)
                break
        else:
            _log.error("[diag] NO prefix of the failing name owns any params")

        _show("params containing 'shared_expert'",
              [k for k in params_dict if "shared_expert" in k])
        _show("params containing 'indexer'",
              [k for k in params_dict if "indexer" in k])
        _show("params containing 'scale'",
              [k for k in params_dict if "scale" in k])
        _show("params of layer 0 (reference: what a working layer looks like)",
              [k for k in params_dict if ".layers.0." in k], cap=64)
    except Exception as _e:
        import logging as _lg
        _lg.getLogger("qwen4-diag").error("[diag] dump failed: %r", _e)
'''

s = s.rstrip("\n") + "\n" + body
p.write_text(s)
print("diag-unplaced-scales: patched", p)
PY

# Smoke test: the patched module must still import. Cheaper to fail here than
# nine minutes into a weight load with a SyntaxError.
python3 - <<'PY'
import sys
try:
    import sglang.srt.models.qwen4_exp as m
    assert hasattr(m, "_diag_unplaced_scales"), "diag function not bound"
except Exception as e:
    print(f"diag-unplaced-scales: POST-PATCH IMPORT FAILED: {type(e).__name__}: {e}")
    sys.exit(1)
print("diag-unplaced-scales: post-patch import OK")
PY

chown -R "${USER_UID}:${USER_GID}" /cache/runtime
log "done (diagnostic only; the load is still expected to fail, now verbosely)"
