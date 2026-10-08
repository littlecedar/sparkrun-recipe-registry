#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
#
# mods/patch-sglang-k2-horizon-fp8/run.sh
#
# Let SGLang's *native* K2-Horizon path serve the published
# IFM/K2-Horizon-MoVA-36B-A4B-FP8 checkpoint.
#
# =====================================================================================
# WHAT IS ACTUALLY BROKEN  (VERIFIED against sglang main @ 95521da, 2026-09-20)
# =====================================================================================
# SGLang gained native K2-Horizon support in 3bac084d4 (2026-09-03, #37654) and a
# "compressed-tensors FP8" branch in 756d0e0a8 (2026-09-05, #38033). The FP8 repo on
# the Hub is NOT compressed-tensors. Its quantization_config is DeepSeek-style block
# FP8:
#
#   quant_method      = "fp8"          -> SGLang resolves Fp8Config, get_name()=="fp8"
#   weight_block_size = [128, 128]
#   activation_scheme = "dynamic"
#   ignored_layers    = [3408 dotted module paths]
#
# Two hard gates reject it before a single weight is read.
#
#   GATE 1  srt/models/xllm.py:664-668, inside _validate_mova_config(), which
#           XllmForCausalLM.__init__ calls at xllm.py:1707:
#             if quant_config is not None and quant_config.get_name() != "compressed_tensors":
#                 raise ValueError("Native xLLM/K2 Horizon serving supports only
#                                   compressed-tensors quantized model weights")
#
#   GATE 2  srt/models/xllm.py:1229-1232, inside _XllmMoVAAttentionBase.__init__():
#             if quant_config is not None:
#                 raise ValueError("K2 Horizon MoVA supports unquantized bf16/fp16
#                                   weights only")
#           XllmDecoderLayer passes the live quant_config into both gated
#           attention classes (xllm.py:1470-1487), and BOTH subclass
#           _XllmMoVAAttentionBase -- XllmMoVAAttention for layers 3-47 and
#           XllmGatedAttention for the dense prefix layers 0-2 -- so this fires
#           once per layer, 48 times, not 45. Getting that number wrong matters
#           for the safety argument below: it is the base class, shared by the
#           dense-prefix path too, that hard-codes quant_config=None at every
#           value-side construction site (including XllmGatedAttention.v_proj at
#           xllm.py:1360-1368), so no layer's value path can be quantised either.
#
# =====================================================================================
# WHY RELAXING THEM IS SAFE, NOT MERELY CONVENIENT  (this is the whole argument)
# =====================================================================================
# The fear when deleting gate 2 is "a quant method now reaches weights that were only
# ever built BF16". It cannot, and the reason is structural rather than hopeful:
#
#   * The MoVA value path cannot be quantised even with a quant_config in hand.
#     q_proj, k_proj, gate_proj and o_proj are constructed with a LITERAL
#     quant_config=None (xllm.py:1264-1298). v_router likewise (xllm.py:1394-1399),
#     and its bias is force-materialised as a plain fp32 nn.Parameter
#     (xllm.py:1400-1406). The value experts are `RoutedValueExperts`
#     (xllm.py:1407-1413), a class that takes no quant_config at all. So all 2880
#     `self_attn.v_experts.N.weight` tensors (15.1 GB), both routers and the whole
#     of MoVA attention stay BF16 no matter what we pass down. Note this is
#     *stronger* than an ignore-list argument: they are BF16 even if a future
#     checkpoint drops them from ignored_layers. The post-patch self-check below
#     re-asserts it on every run, because a future upstream refactor that starts
#     threading quant_config into those sites would silently quantise the value
#     path -- and then `attention_backend`/`fp8_gemm_backend` reasoning written
#     against BF16 attention would be void.
#   * The only modules that DO receive the live quant_config are FusedMoE
#     (xllm.py:936-944) and the shared-expert XllmMLP (xllm.py:951-957).
#   * The shared expert is spelled `model.layers.N.mlp.shared_experts.gate_proj` in
#     ignored_layers, which is exactly the SGLang module name (add_prefix
#     ("shared_experts"), xllm.py:951-957). The fused `gate_up_proj` prefix is
#     expanded back to {gate_proj, up_proj} by _FALLBACK_FUSED_SHARDS before
#     matching (srt/layers/quantization/utils.py:61-66), so it matches and stays
#     BF16. NOTE: the reference HF implementation spells this `shared_expert`
#     singular (modeling_k2_horizon.py:547) while SGLang uses the plural; this
#     checkpoint follows SGLang. A checkpoint that flips that spelling would
#     silently quantise the shared expert -- see the boot checklist. The
#     `mlp.gate` router entry does NOT collide with it: _module_path_match
#     (utils.py:47-59) matches on dotted boundaries precisely so `mlp.gate` cannot
#     hit `mlp.gate_up_proj`.
#   * So the routed experts are the ONLY thing that ends up FP8, and their names
#     line up exactly. `FusedMoE.make_expert_params_mapping` rewrites
#     `experts.7.gate_proj.weight_scale_inv` -> `experts.w13_weight_scale_inv`
#     (srt/layers/moe/fused_moe_triton/layer.py:1650-1675) and `Fp8MoEMethod`
#     registers `w13_weight_scale_inv` / `w2_weight_scale_inv` for block_quant
#     (srt/layers/quantization/fp8.py:1509-1536). **The checkpoint's
#     `weight_scale_inv` naming IS SGLang's native-fp8 convention. There is no
#     scale-rename landmine on this path.**
#
#     That last point is why this mod patches two `if` statements instead of
#     rewriting the checkpoint's metadata into compressed-tensors. The
#     compressed-tensors scheme names the same buffer `weight_scale`
#     (srt/layers/quantization/compressed_tensors/schemes/
#      compressed_tensors_w8a8_fp8.py:106-113) and would introduce exactly the
#     silent-wrong-scale failure that a re-wrap invites -- a failure whose symptom
#     is plausible-looking garbage, not a crash. The re-wrap is the wrong lever
#     here; the gate is the right one.
#
# So both gates are policy, not invariants: upstream shipped and tested the
# compressed-tensors route and declined to certify the fp8 route. Nothing in the
# model code depends on what we are about to let through.
#
# =====================================================================================
# WHAT REMAINS GENUINELY UNKNOWN -- read this before quoting any number
# =====================================================================================
#   U1  Kernel availability. Block-FP8 (w8a8_block_fp8) GEMM on SM121/GB10 has to land
#       on cutlass or triton: DeepGEMM is blocked on SM121 per the qwen4 lane, and
#       SGLang's own `is_sm120_supported()` is documented as EXCLUDING SM121/GB10
#       (srt/utils/common.py:323-333). If the only reachable kernel is slow at M=1, the
#       FP8 checkpoint can LOSE to BF16 at c=1 -- it would not be the first time a
#       smaller checkpoint measured slower than its larger sibling on this chip.
#       Experiment E5 in the worklog.
#   U2  Nobody has run this combination. Upstream's FP8 PR says it was "verified to
#       load the corresponding checkpoint", but no compressed-tensors K2 checkpoint
#       exists on the Hub, so the fp8 branch is very likely unexercised.
#   U3  Numerics. Everything above is a *static* argument about which method objects
#       get selected. Strong, but not a test. Gate every throughput number produced
#       through this mod behind the BF16-vs-patched greedy continuation (D2) in the
#       worklog before believing it. "Plausible but wrong text" is precisely the
#       failure mode this mod can produce.
#   U4  TP ceiling. With block-FP8 MoE, Fp8MoEMethod requires
#       moe_intermediate_size / tp % block_n == 0 (fp8.py:1368-1390). 768/1 = 768 and
#       768/2 = 384 are divisible by 128; 768/4 = 192 and 768/8 = 96 are not. So this
#       path is TP in {1,2} and a TP4/TP8 arm will die at build time with a clear
#       message. That is a constraint on the mod, not a bug in it.
#
# =====================================================================================
# VERSION STAMP -- the guard tests assert these; bump them together
# =====================================================================================
#   MOD_VERSION="1.0.0"   EXPECTED_SGLANG="95521da"   ANCHORS_ON_SUCCESS=2
#   MODIFIED_UPSTREAM_FILES=( srt/models/xllm.py )
#   tests/test_recipe_guards.py::test_ifm_k2_fp8_mod_version_stamp_tracks_recipe pins
#   MOD_VERSION and EXPECTED_SGLANG against the recipes' metadata.upstream_pins.
#
# HOW TO TELL IT WORKED
# ---------------------
#   k2-horizon-fp8: gate1: relaxed (1 anchor)
#   k2-horizon-fp8: gate2: relaxed (1 anchor)
#   k2-horizon-fp8: patched ok, compiles, 2 anchor(s) rewritten
#   k2-horizon-fp8: self-check ok: value path still unquantised by construction
# Everything else exits 1 and never leaves a half-patched tree: each anchor is counted
# before any file is written, and the result is compiled before it is renamed into
# place. Same discipline as mods/fix-sglang-radix-chunked-insert.
#
# DEPENDENCIES: none (stdlib + coreutils).
# IDEMPOTENT: re-running prints "already patched" and exits 0.
# REVERSIBLE: mods/patch-sglang-k2-horizon-fp8/unpatch.sh restores the stock file
#   from the mod's own backup copy.
#
# ESCAPE HATCHES
#   SPARKRUN_SKIP_MOD=1               skip, exit 0
#   SPARKRUN_K2_FP8_GATE_ONLY=1       relax gate 1 only. The build then dies at gate 2
#                                     with upstream's own message -- that IS the E0
#                                     falsification arm, it is supposed to fail.
#   SPARKRUN_SGLANG_PKG=<dir>         override package discovery
#   SPARKRUN_K2_FP8_ALLOW_DRIFT=1     anchor mismatch becomes a warning. Triage only:
#                                     the tree is then NOT certified and every numeric
#                                     claim in the recipe that used it is void.

set -euo pipefail

#####################################################################
# Metadata
#####################################################################
MOD_NAME="patch-sglang-k2-horizon-fp8"
MOD_VERSION="1.0.0"
MOD_DESCRIPTION="Relax SGLang's two native-K2-Horizon quant gates so the published block-FP8 checkpoint loads"
MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"
EXPECTED_SGLANG="95521da"
SENTINEL="[k2-horizon-fp8]"

SPARKRUN_ROOT="${SPARKRUN_ROOT:-/cache}"
SPARKRUN_RUNTIME_ROOT="${SPARKRUN_RUNTIME_ROOT:-${SPARKRUN_ROOT}/runtime}"
SPARKRUN_NODE_ID="${SPARKRUN_NODE_ID:-$(hostname -s 2>/dev/null || echo node)}"
LOG_DIR="${SPARKRUN_LOG_DIR:-${SPARKRUN_RUNTIME_ROOT}/_logs}"
LOCK_DIR="${SPARKRUN_LOCK_DIR:-${SPARKRUN_RUNTIME_ROOT}/_locks}"
MOD_ROOT="${SPARKRUN_MOD_ROOT:-${SPARKRUN_ROOT}/mods}"
BACKUP_DIR="${SPARKRUN_K2_FP8_BACKUP:-${MOD_ROOT}/${MOD_NAME}/.backup}"
LOG_FILE="${LOG_DIR}/${MOD_NAME}.${SPARKRUN_NODE_ID}.log"
STATUS_FILE="${LOG_DIR}/${MOD_NAME}.${SPARKRUN_NODE_ID}.status"
LOCK_FILE="${LOCK_DIR}/${MOD_NAME}.lock"

log() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*" | tee -a "${LOG_FILE}"; }

if [ "${SPARKRUN_SKIP_MOD:-0}" = "1" ]; then
    log "SPARKRUN_SKIP_MOD=1, skipping."; exit 0
fi

mkdir -p "${LOG_DIR}" "${LOCK_DIR}" "${BACKUP_DIR}" 2>/dev/null || true
exec 9>"${LOCK_FILE}"
flock -w 600 9 || { log "FATAL: lock timeout after 600s"; exit 1; }
: > "${LOG_FILE}"
log "=== ${MOD_NAME} v${MOD_VERSION} node=${SPARKRUN_NODE_ID} ==="

#####################################################################
# 1. locate sglang, and refuse to guess
#####################################################################
SGLANG_ROOT="${SPARKRUN_SGLANG_PKG:-}"
if [ -z "${SGLANG_ROOT}" ]; then
    SGLANG_ROOT="$(python3 -c 'import importlib.util,pathlib;print(pathlib.Path(importlib.util.find_spec("sglang").origin).parent)' 2>/dev/null || true)"
fi
XLM="${SGLANG_ROOT}/srt/models/xllm.py"
if [ -z "${SGLANG_ROOT}" ] || [ ! -f "${XLM}" ]; then
    log "FATAL: cannot find sglang/srt/models/xllm.py (SGLANG_ROOT='${SGLANG_ROOT}')."
    log "       This mod is SGLang-only. If it appears in a vLLM recipe chain that is a"
    log "       wiring bug: vLLM registers K2HorizonForCausalLM natively with no arch"
    log "       gate (vllm/model_executor/models/registry.py maps it to k2_horizon.py,"
    log "       merged as vllm-project/vllm#55063) and its Fp8Config already reads"
    log "       quant_method=fp8 + weight_block_size + ignored_layers"
    log "       (vllm/model_executor/layers/quantization/fp8.py:96-184, VERIFIED)."
    echo "failed" > "${STATUS_FILE}"; exit 1
fi
SGLANG_VER="$(python3 -c 'import sglang;print(getattr(sglang,"__version__","?"))' 2>/dev/null || echo '?')"
log "sglang root=${SGLANG_ROOT} version=${SGLANG_VER} (anchors authored at ${EXPECTED_SGLANG})"

# One pristine backup per container, so unpatch.sh can restore even after we edit.
STOCK="${BACKUP_DIR}/xllm.py.stock"
if [ ! -f "${STOCK}" ]; then
    cp "${XLM}" "${STOCK}" 2>/dev/null && log "stock copy saved: ${STOCK}" \
        || log "WARN: could not save a stock copy (read-only?); unpatch.sh unavailable"
fi

#####################################################################
# 2. patch. Anchors are counted for ALL edits before ANY write, and the
#    result is compiled before it is renamed into place.
#####################################################################
export K2FP8_XLM="${XLM}"
export K2FP8_SENTINEL="${SENTINEL}"
export K2FP8_GATE_ONLY="${SPARKRUN_K2_FP8_GATE_ONLY:-0}"
export K2FP8_ALLOW_DRIFT="${SPARKRUN_K2_FP8_ALLOW_DRIFT:-0}"

K2FP8_PY="$(mktemp)"
cat > "${K2FP8_PY}" <<'PYEOF'
import os, sys, pathlib, tempfile, py_compile

p = pathlib.Path(os.environ["K2FP8_XLM"])
sentinel = os.environ["K2FP8_SENTINEL"]
gate_only = os.environ.get("K2FP8_GATE_ONLY", "0") == "1"
allow_drift = os.environ.get("K2FP8_ALLOW_DRIFT", "0") == "1"

src = p.read_text(encoding="utf-8")
if sentinel in src:
    print("k2-horizon-fp8: already patched")
    sys.exit(0)

# ---------------------------------------------------------------------------
# GATE 1 (xllm.py:664-668). The anchor is the full five-line raise so that a
# reformat of the message cannot half-match.
# ---------------------------------------------------------------------------
G1_OLD = '''        if quant_config is not None and quant_config.get_name() != "compressed_tensors":
            raise ValueError(
                "Native xLLM/K2 Horizon serving supports only "
                "compressed-tensors quantized model weights"
            )'''
G1_NEW = '''        # [k2-horizon-fp8] mods/patch-sglang-k2-horizon-fp8: accept DeepSeek-style
        # block fp8 (quant_method="fp8" + weight_block_size=[128,128]) next to
        # compressed-tensors. Which submodules actually get quantised is decided by
        # the checkpoint's ignored_layers and by the literal quant_config=None at
        # each MoVA construction site -- NOT by this gate. See the mod header.
        if quant_config is not None and quant_config.get_name() not in (
            "compressed_tensors",
            "fp8",
        ):
            raise ValueError(
                "Native xLLM/K2 Horizon serving supports only "
                "compressed-tensors or block-fp8 quantized model weights"
            )'''

# ---------------------------------------------------------------------------
# GATE 2 (xllm.py:1229-1232). Replaced with a *narrower* check rather than a
# deletion, so we still refuse quant methods whose Fp8 schemes we have not
# reasoned about, and so a checkpoint whose block geometry differs from the one
# this mod was reasoned about fails loudly at build time instead of loading
# something nobody looked at.
# ---------------------------------------------------------------------------
G2_OLD = '''        if quant_config is not None:
            raise ValueError(
                "K2 Horizon MoVA supports unquantized bf16/fp16 weights only"
            )'''
G2_NEW = '''        # [k2-horizon-fp8] mods/patch-sglang-k2-horizon-fp8: was a hard reject of
        # any quant_config. Relaxed for the published block-FP8 checkpoint.
        #
        # Why this is not "just delete the guard": MoVA's value path cannot be
        # quantised regardless of what reaches here. q_proj/k_proj/gate_proj/o_proj
        # and v_router are built with a literal quant_config=None (see just below),
        # and RoutedValueExperts takes no quant_config at all. So the 15.1 GB of
        # value experts and every router stay BF16 by construction; only FusedMoE
        # and the shared-expert MLP can receive a quant method, and the
        # checkpoint's ignored_layers keeps the shared expert BF16 while quantising
        # exactly the 13,500 routed expert weights. Those weights' scales are named
        # weight_scale_inv, which IS the name Fp8MoEMethod registers for
        # block_quant (quantization/fp8.py:1509-1536) -- no rename needed.
        #
        # The mod's certified envelope, asserted rather than assumed:
        if quant_config is not None:
            _k2fp8_name = quant_config.get_name()
            if _k2fp8_name not in ("fp8", "compressed_tensors"):
                raise ValueError(
                    "[k2-horizon-fp8] MoVA accepts unquantized bf16/fp16 or "
                    "certified block-fp8 weights only, got "
                    f"{_k2fp8_name!r}")
            _k2fp8_block = tuple(getattr(quant_config, "weight_block_size", None) or ())
            if _k2fp8_block != (128, 128):
                raise ValueError(
                    "[k2-horizon-fp8] this mod certifies weight_block_size="
                    f"[128,128] only, got {_k2fp8_block!r}. A narrower block has "
                    "no SM12x block kernel and would be silently demoted.")
            if str(getattr(quant_config, "activation_scheme", "dynamic")) != "dynamic":
                raise ValueError(
                    "[k2-horizon-fp8] this mod certifies activation_scheme="
                    "'dynamic' only, got "
                    f"{getattr(quant_config, 'activation_scheme', None)!r}")
            if getattr(quant_config, "use_mxfp8", False):
                raise ValueError(
                    "[k2-horizon-fp8] MXFP8 (uint8/UE8M0 scales) is not certified "
                    "by this mod; it takes a different runner path.")'''

edits = [("gate1", G1_OLD, G1_NEW)]
if not gate_only:
    edits.append(("gate2", G2_OLD, G2_NEW))

counts = {tag: src.count(old) for tag, old, _new in edits}
bad = {t: c for t, c in counts.items() if c != 1}
if bad:
    print(f"k2-horizon-fp8: FATAL anchor mismatch {bad}; expected exactly 1 each.")
    print("k2-horizon-fp8: the container's sglang has drifted from 95521da. DO NOT "
          "widen the anchors -- re-read srt/models/xllm.py around lines 664 and 1229 "
          "and update this mod, or the recipes using it lose their claim to have been "
          "reasoned about.")
    if allow_drift:
        print("k2-horizon-fp8: SPARKRUN_K2_FP8_ALLOW_DRIFT=1 -> continuing WITHOUT "
              "certification; numeric claims from this run are void.")
        edits = [e for e in edits if counts[e[0]] == 1]
        if not edits:
            sys.exit(1)
    else:
        sys.exit(1)

for tag, old, new in edits:
    src = src.replace(old, new, 1)
    print(f"k2-horizon-fp8: {tag}: relaxed (1 anchor)")

# xllm.py has no module-level `logger` (verified by grep on 95521da: the file
# never mentions one), so the injected code must not reference one. A NameError
# at build time on every boot is exactly the sort of thing to assert before
# shipping rather than to discover on a Spark.
if "logger." in G1_NEW or "logger." in G2_NEW:
    print("k2-horizon-fp8: FATAL the injected patch references `logger`, which "
          "xllm.py does not define; this would NameError at build time.")
    sys.exit(1)

fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".k2fp8-", suffix=".py")
try:
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(src)
    py_compile.compile(tmp, doraise=True)
    os.chmod(tmp, p.stat().st_mode & 0o777)
    os.replace(tmp, p)
except py_compile.PyCompileError as e:
    print(f"k2-horizon-fp8: FATAL patched file does not compile: {e}")
    try:
        os.unlink(tmp)
    except OSError:
        pass
    sys.exit(1)
except PermissionError as e:
    print(f"k2-horizon-fp8: FATAL cannot write {p}: {e}")
    try:
        os.unlink(tmp)
    except OSError:
        pass
    sys.exit(1)
print(f"k2-horizon-fp8: patched ok, compiles, {len(edits)} anchor(s) rewritten")
PYEOF

python3 "${K2FP8_PY}"; rc=$?
rm -f "${K2FP8_PY}"
if [ "${rc}" -ne 0 ]; then
    log "FATAL: patch stage failed rc=${rc}; ${XLM} left untouched (or reverted by rename)."
    echo "failed" > "${STATUS_FILE}"; exit 1
fi

#####################################################################
# 3. post-patch self-check. This is the only automated defence against an
#    upstream refactor that starts threading quant_config into the MoVA value
#    path -- which would quietly quantise 15.1 GB of value experts and produce
#    numerics nobody argued for. Cheap, and it fails the boot rather than the
#    benchmark.
#####################################################################
export K2FP8_XLM="${XLM}"
python3 - <<'PY' || rc=1
import os, sys, pathlib
src = pathlib.Path(os.environ["K2FP8_XLM"]).read_text()
need = [
    ("q_proj stays unquantised",
     'self.q_proj = ColumnParallelLinear(\n            config.hidden_size,\n            self.total_num_heads * self.head_dim,\n            bias=False,\n            quant_config=None,'),
    ("v_router stays unquantised",
     'quant_config=None,\n            prefix=add_prefix("v_router", prefix)'),
    ("value experts stay unquantisable",
     "self.v_experts = RoutedValueExperts("),
    ("gate1 patch present", "block-fp8 quantized model weights"),
    ("mod sentinel present", "[k2-horizon-fp8]"),
]
missing = [name for name, needle in need if needle not in src]
if missing:
    print("k2-horizon-fp8: SELF-CHECK FAILED: " + "; ".join(missing))
    print("k2-horizon-fp8: upstream moved the MoVA value path. This mod's safety "
          "argument no longer holds -- stop and re-read xllm.py:1264-1298 and "
          "1394-1413 before running anything.")
    sys.exit(1)
print("k2-horizon-fp8: self-check ok: value path still unquantised by construction")
PY
if [ "${rc:-0}" -ne 0 ]; then
    log "FATAL: post-patch self-check failed. The patched tree is NOT safe to run."
    log "       Restore with: mods/${MOD_NAME}/unpatch.sh"
    echo "failed" > "${STATUS_FILE}"; exit 1
fi

chown "${SPARKRUN_UID:-1000}:${SPARKRUN_GID:-1000}" "${LOG_FILE}" "${STATUS_FILE}" 2>/dev/null || true

log "patched: ${XLM}"
log "reminder: this is a NUMERICS-BEARING change. Do not report t/s from a recipe"
log "          using this mod until the BF16-vs-patched greedy continuation (D2)"
log "          in K2-36B-A4B-MODEL-OPTIMIZATION-WORK.md has passed."
echo "success" > "${STATUS_FILE}"
log "=== ${MOD_NAME} done ==="
exit 0
