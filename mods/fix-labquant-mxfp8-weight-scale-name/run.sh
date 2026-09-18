#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Let Qwen4-Exp place the MXFP8 (ue8m0) weight scales that
# local-inference-lab/Qwen3.8-Flash-Next-NVFP4 stores as `weight_scale`, where
# the engine registers the identical tensor under `weight_scale_inv`.
#
# Evidence, all read from the pinned image rather than inferred:
#   * fp8.py Fp8LinearMethod.create_fp8_weight_, block_quant branch:
#         scale_dtype = torch.uint8 if use_mxfp8 else torch.float32
#         scale = BlockQuantScaleParameter(... dtype=scale_dtype)
#         scale.format_ue8m0 = use_mxfp8
#         layer.register_parameter("weight_scale_inv", scale)
#     and use_mxfp8 forces weight_block_size == [1, 32].
#   * the checkpoint ships shared_expert.{gate,up,down}_proj.weight_scale as
#     uint8 with one value per 32 elements of K -- same dtype, same block
#     layout, same semantics. Only the suffix differs.
#   * observed shapes reconcile: full [2560, 20] (640/32 = 20 blocks along K)
#     sharded to the [2560, 10] parameter (320/32) seen at TP=2.
#
# The rename is deliberately CONDITIONAL, and that is the whole design:
#   rename <X>.weight_scale -> <X>.weight_scale_inv only when
#     (1) "<X>.weight_scale"    is NOT in params_dict, and
#     (2) "<X>.weight_scale_inv"    IS in params_dict.
# Condition (2) means the rename can only ever fire on a tensor whose load was
# already going to fail, so nothing that loaded correctly before can change
# behaviour. A blanket rename would have broken the routed experts, whose
# scales are registered as w13_weight_scale / w2_weight_scale and arrive via
# stacked_params_mapping: renaming gate_up_proj.weight_scale to
# gate_up_proj.weight_scale_inv would defeat that mapping. With the guard,
# condition (2) is false there, so the rename declines.
#
# This changes where a byte array is stored, not its contents. It is NOT a
# claim of numerical correctness -- see README.md and the work doc.
#
# Anchored, idempotent, and smoke-tested by import. Runs alongside
# diag-qwen4-unplaced-scales (different anchor), so any scale that still cannot
# be placed will report which one instead of dying on a nameless assert.
#####################################################################

MOD_NAME="fix-labquant-mxfp8-weight-scale-name"
MOD_DESCRIPTION="Map MXFP8 weight_scale -> weight_scale_inv where the model expects it"
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

HELPER = "_labq_remap_mxfp8_weight_scale"
MARK = "# [" + "fix-labquant-mxfp8-weight-scale-name" + "]"


def _readable(p):
    """True only if we can actually OPEN p.

    Path.exists() returns False when stat() fails with EACCES, so a file that
    exists but is unreadable by this uid would be misreported as missing.
    """
    try:
        with open(p, "rb"):
            return True
    except FileNotFoundError:
        return False
    except OSError as e:
        raise SystemExit(
            f"{p} exists but is not readable by uid {os.getuid()}: "
            f"{type(e).__name__}: {e}"
        )


def _find_qwen4():
    tried = []
    try:
        spec = importlib.util.find_spec("sglang")
        tried.append(f"find_spec={getattr(spec, 'origin', None)}")
        if spec and spec.origin:
            c = pathlib.Path(spec.origin).parent / "srt/models/qwen4_exp.py"
            if c.exists() and _readable(c):
                return c
            tried.append(f"spec-derived={c} exists={c.exists()}")
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        tried.append(f"find_spec raised {type(e).__name__}: {e}")

    for c in (
        pathlib.Path("/sgl-workspace/sglang/python/sglang/srt/models/qwen4_exp.py"),
    ):
        tried.append(f"literal={c}")
        if c.exists():
            if _readable(c):
                return c
            raise SystemExit(f"{c} present but unreadable")

    import subprocess

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
    raise SystemExit("could not locate a readable qwen4_exp.py; tried "
                     + "; ".join(tried))


p = _find_qwen4()
print("mod: target", p)
s = p.read_text()

if HELPER in s:
    print("mod: already applied")
    sys.exit(0)

anchor = (
    '            is_fused_expert = (\n'
    '                "experts.gate_up_proj" in name or "experts.down_proj" in name\n'
    '            )\n'
)
n = s.count(anchor)
if n != 1:
    print(f"mod: anchor matched {n} times, expected exactly 1; refusing to patch "
          f"(base image has diverged?)")
    sys.exit(1)

call = "            name = " + HELPER + "(name, loaded_weight, params_dict)\n"
s = s.replace(anchor, anchor + call, 1)

body = '''

''' + MARK + '''
# The labquant export names MXFP8 (ue8m0) weight scales `<X>.weight_scale`;
# Fp8LinearMethod registers the identical tensor as `<X>.weight_scale_inv`
# (uint8, format_ue8m0, weight_block_size=[1,32]). Rename only when the
# original name has no destination AND the _inv name does, so this can only
# affect a load that was already failing. Never raises.
def ''' + HELPER + '''(name, loaded_weight, params_dict):
    def _log(src, dst, w):
        try:
            import logging as _lg
            _lg.getLogger("labq-remap").info(
                "[remap] %s -> %s dtype=%s shape=%s",
                src, dst, str(w.dtype), tuple(w.shape),
            )
        except Exception:
            pass

    def _forms(n):
        # The loader applies several name rewrites AFTER this hook runs, at the
        # point where it resolves the parameter:
        #     "model.visual." -> "visual."
        #     "attn.qkv."     -> "attn.qkv_proj."
        # So a name arriving here can be in checkpoint spelling while params_dict
        # is in loader-final spelling. Enumerate the spellings the loader could
        # end up with and match against those; guessing one is how the visual
        # tower's MXFP8 scales looked unplaceable. Ordered, first hit wins, and
        # the unmodified name is always tried first so nothing already correct
        # is disturbed.
        out, seen = [], set()

        def add(x):
            if x not in seen:
                seen.add(x)
                out.append(x)

        add(n)
        cands = [n]
        for a, b in (("model.visual.", "visual."), ("visual.", "model.visual.")):
            cands += [c.replace(a, b, 1) for c in cands if a in c]
        for c in list(cands):
            cands += [c.replace("attn.qkv.", "attn.qkv_proj.")]
        for c in cands:
            add(c)
        return out

    try:
        if not name.endswith(".weight_scale"):
            return name

        # Try each spelling of the name; act on the first that has a destination.
        for cand in _forms(name):
            base = cand[: -len(".weight_scale")]
            inv = base + ".weight_scale_inv"
            if cand in params_dict:
                return cand                      # already has a destination
            if inv in params_dict:
                _log(name, inv, loaded_weight)
                return inv

        base = _forms(name)[0][: -len(".weight_scale")]
        # Fused module (shared_expert.gate/up_proj -> one gate_up_proj, and the
        # qkv case). The engine's own stacked_params_mapping runs AFTER this hook
        # and performs the merge plus the correct shard_id, but it can only match
        # if the name still contains the un-fused weight name. So swap ONLY the
        # suffix and hand it back unchanged otherwise: stacking then maps
        # `<X>.gate_proj.weight_scale_inv` onto `<X>.gate_up_proj.weight_scale_inv`,
        # which is the parameter that actually exists. Rewriting the fused name
        # here would defeat that match and silently drop the tensor.
        # The in_proj pairs mirror the engine's own stacked_params_mapping entries
        # (qwen4_exp.py:1839-1842): in_proj_qkv+in_proj_z -> in_proj_qkvz (shards
        # 0,1,2 / 3) and in_proj_b+in_proj_a -> in_proj_ba (0 / 1). Without these
        # the GDN projections fail the scalar assert at qwen4_exp.py:2140 on a
        # [48, 80] in_proj_a/in_proj_b scale. Order-insensitive because the
        # `cand in params_dict` guard rejects bogus compositions ("gate_gate_up_proj").
        for unfused, fused in (
            ("gate_proj", "gate_up_proj"),
            ("up_proj", "gate_up_proj"),
            ("q_proj", "qkv_proj"),
            ("k_proj", "qkv_proj"),
            ("v_proj", "qkv_proj"),
            ("in_proj_qkv", "in_proj_qkvz"),
            ("in_proj_z", "in_proj_qkvz"),
            ("in_proj_b", "in_proj_ba"),
            ("in_proj_a", "in_proj_ba"),
        ):
            if base.endswith(unfused):
                cand = base[: -len(unfused)] + fused + ".weight_scale_inv"
                if cand in params_dict:
                    _log(name, cand + " (via stacking)", loaded_weight)
                    return inv
        # Still unresolved BY THIS HOOK. Convert the imminent, nameless crash into
        # a line that names the tensor: qwen4_exp.py:2140 asserts
        # abs(w.item()-1.0)<1e-6 and .item() raises before its f-string can print
        # the name, so without this the only clue is a RuntimeError carrying an
        # element count.
        #
        # Wording matters. This hook runs BEFORE the engine's expert_params_mapping
        # and stacked_params_mapping, so "no parameter" here is a statement about
        # this hook, not about the load. Per-expert scales (experts.N.gate_proj...)
        # legitimately have no destination at this point and are placed correctly a
        # stage later -- an early version of this line said "no parameter of this
        # name", which made 4,845 perfectly healthy expert scales look like failures
        # and sent me chasing a non-bug. Only multi-element scales that survive to
        # the assert are real failures; the engine's own exception is the signal.
        try:
            n_el = int(loaded_weight.numel())
        except Exception:
            n_el = -1
        if n_el != 1 and ".experts." not in name and "mtp.layers" not in name:
            _log(name, f"no destination known to this hook ({n_el} elems); "
                       f"if the load dies here, this is the tensor", loaded_weight)
        return name
    except Exception:
        return name
'''

s = s.rstrip("\n") + "\n" + body
p.write_text(s)
print("mod: patched", p)
PY

python3 - <<'PY'
import sys
try:
    import sglang.srt.models.qwen4_exp as m
    helper = getattr(m, "_labq_remap_mxfp8_weight_scale", None)
    assert helper is not None, "helper not bound"
except Exception as e:
    print(f"mod: POST-PATCH IMPORT FAILED: {type(e).__name__}: {e}")
    sys.exit(1)

# Importing only proves the module compiles and the name is bound at module scope.
# It does NOT execute the function body, so a NameError on a helper the edit removed
# (or a typo in a branch never taken at import time) sails straight through and only
# surfaces 20 minutes into a weight load at 6% progress. Exercise the paths directly.
# These are synthetic dicts, but the function only does dict membership and string
# surgery, so a fake is faithful here -- unlike probes that fake rich objects.
try:
    class W:
        dtype = "u8"
        shape = (1, 1)

    # 1. non-scale names pass through untouched
    assert helper("model.layers.0.self_attn.q_proj.weight", W(), {}) == \
        "model.layers.0.self_attn.q_proj.weight", "passthrough broken"

    # 2. un-fused: weight_scale -> weight_scale_inv when only the _inv exists
    pd = {"m.gate_proj.weight_scale_inv": object()}
    assert helper("m.gate_proj.weight_scale", W(), pd) == "m.gate_proj.weight_scale_inv", \
        "un-fused rename broken"

    # 3. already-placed name must NOT be rewritten
    pd = {"m.gate_proj.weight_scale": object()}
    assert helper("m.gate_proj.weight_scale", W(), pd) == "m.gate_proj.weight_scale", \
        "clobbered a tensor that already had a destination"

    # 4. fused gate/up: keep the un-fused stem, swap only the suffix, so the
    #    engine's stacked_params_mapping still matches and applies shard_id
    pd = {"m.shared_expert.gate_up_proj.weight_scale_inv": object()}
    got = helper("m.shared_expert.gate_proj.weight_scale", W(), pd)
    assert got == "m.shared_expert.gate_proj.weight_scale_inv", \
        f"fused path must leave the stem for stacking, got {got!r}"

    # 5. nothing to map to -> unchanged, and must not raise
    assert helper("m.nope.weight_scale", W(), {}) == "m.nope.weight_scale", \
        "no-destination case should be a no-op"

    # 6. must never raise, whatever it is handed
    assert helper("x.weight_scale", None, None) == "x.weight_scale", \
        "helper must be exception-safe"

    # 6b. GDN fused projections: the pairs that were missing, and whose absence
    #     surfaced as a 3840-element scalar assert rather than a name error.
    for unfused, fused in (
        ("in_proj_qkv", "in_proj_qkvz"),
        ("in_proj_z", "in_proj_qkvz"),
        ("in_proj_b", "in_proj_ba"),
        ("in_proj_a", "in_proj_ba"),
    ):
        pd = {f"l.linear_attn.{fused}.weight_scale_inv": object()}
        got = helper(f"l.linear_attn.{unfused}.weight_scale", W(), pd)
        assert got == f"l.linear_attn.{unfused}.weight_scale_inv", (
            f"GDN fused path broken for {unfused}: got {got!r}")

    # 6c. a name that is ALREADY fused must be resolved by the first (exact) loop
    #     and must not be re-composed by the fused loop -- "in_proj_qkvz" does not
    #     end with "in_proj_qkv", so the guard holds structurally, but assert it.
    pd = {"l.linear_attn.in_proj_qkvz.weight_scale_inv": object()}
    assert helper("l.linear_attn.in_proj_qkvz.weight_scale", W(), pd) == \
        "l.linear_attn.in_proj_qkvz.weight_scale_inv", \
        "already-fused name should resolve directly to its _inv parameter"

    # 7. visual tower: the loader renames "model.visual." -> "visual." AFTER this
    #    hook, so the incoming name carries the checkpoint prefix while
    #    params_dict carries the loader-final one. This is what actually killed
    #    the last boot, and it is the case that must not regress.
    pd = {"visual.blocks.0.attn.proj.weight_scale_inv": object()}
    got = helper("model.visual.blocks.0.attn.proj.weight_scale", W(), pd)
    assert got == "visual.blocks.0.attn.proj.weight_scale_inv", \
        f"visual prefix normalisation broken, got {got!r}"

    # 8. visual attention qkv: loader also rewrites "attn.qkv." -> "attn.qkv_proj."
    #    after the hook, and visual names are excluded from stacked_params_mapping,
    #    so the suffix swap is the only way to land it.
    pd = {"visual.blocks.0.attn.qkv_proj.weight_scale_inv": object()}
    got = helper("model.visual.blocks.0.attn.qkv.weight_scale", W(), pd)
    assert got == "visual.blocks.0.attn.qkv_proj.weight_scale_inv", \
        f"visual qkv normalisation broken, got {got!r}"

    # 9. the normalisations must not leak into language-model names
    pd = {"model.layers.0.self_attn.q_proj.weight_scale_inv": object()}
    assert helper("model.layers.0.self_attn.q_proj.weight_scale", W(), pd) == \
        "model.layers.0.self_attn.q_proj.weight_scale_inv", \
        "normalisation leaked into a language-model name"
except Exception as e:
    print(f"mod: POST-PATCH BEHAVIOUR TEST FAILED: {type(e).__name__}: {e}")
    sys.exit(1)
print("mod: post-patch import OK and 9/9 behaviour checks passed")
PY

chown -R "${USER_UID}:${USER_GID}" /cache/runtime
log "done"
