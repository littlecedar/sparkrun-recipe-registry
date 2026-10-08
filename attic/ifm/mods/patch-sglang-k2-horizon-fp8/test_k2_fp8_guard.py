#!/usr/bin/env python3
"""Negative control for the K2-Horizon block-FP8 gate patch.

Reads a REAL sglang `srt/models/xllm.py` and answers one question: would this file
let `IFM/K2-Horizon-MoVA-36B-A4B-FP8` (quant_method "fp8") through, or does it still
refuse it? It does not import sglang and it does not trust any copy of the source I
typed myself -- the text is read from the very file `run.sh` edits, which is the same
convention `mods/fix-sglang-spec-metrics-empty-verify/test_spec_metrics_guard.py`
uses and the reason a guard here cannot pass by inspecting a fixture.

Three states are distinguished, and collapsing them is what makes a guard useless:

  A  stock        gate 1 present, gate 2 present  -> the FP8 checkpoint is refused
  B  gate-only   gate 1 relaxed, gate 2 present   -> still refused, differently
  C  patched     gate 1 relaxed, gate 2 replaced by the mod's narrow re-assertion
  D  unknown     neither anchor recognised        -> the container moved; no verdict

State B is the interesting one and the reason this is not a two-way check.
`SPARKRUN_K2_FP8_GATE_ONLY=1` produces it on purpose (it is the falsification arm's
mechanism), and a guard that only asks "is the sentinel present?" reports B as
unpatched, which is right, while a guard that asks "was gate 1 relaxed?" reports B as
patched, which is wrong in a way that could ship a broken recipe.

Exit codes (same contract as the spec-metrics guard):
  0  state C, and the safety invariants still hold  -> usable
  1  state A or B                                   -> this checkpoint will not boot
  2  state D, or the file could not be read          -> NOT a verdict about the patch
"""
import argparse
import re
import sys

HARNESS_FAIL = 2

# Exact texts. If these do not appear, the tree is not the tree this mod was
# reasoned about and every conclusion below is void -- so we say state D rather than
# quietly reporting "unpatched".
STOCK_GATE1 = (
    'if quant_config is not None and quant_config.get_name() != "compressed_tensors":'
)
PATCHED_GATE1 = '"compressed-tensors or block-fp8 quantized model weights"'
STOCK_GATE2 = '"K2 Horizon MoVA supports unquantized bf16/fp16 weights only"'
PATCHED_GATE2 = '"[k2-horizon-fp8] this mod certifies weight_block_size='
SENTINEL = "[k2-horizon-fp8]"

# The invariants the mod's safety argument rests on. If any disappears, a patched
# tree is not safe to run even though it patches cleanly -- this is the check that
# catches an upstream refactor that starts threading quant_config into MoVA's value
# path, which would silently quantise 15.1 GB of value experts.
INVARIANTS = [
    ("q_proj built unquantised",
     re.compile(r"self\.q_proj = ColumnParallelLinear\(\s*"
                r"config\.hidden_size,\s*"
                r"self\.total_num_heads \* self\.head_dim,\s*"
                r"bias=False,\s*"
                r"quant_config=None,")),
    ("k_proj built unquantised",
     re.compile(r"self\.k_proj = ColumnParallelLinear\(\s*"
                r"config\.hidden_size,\s*"
                r"self\.total_num_kv_heads \* self\.head_dim,\s*"
                r"bias=False,\s*"
                r"quant_config=None,")),
    ("v_router built unquantised",
     re.compile(r"quant_config=None,\s*\n\s*prefix=add_prefix\(\"v_router\", prefix\)")),
    ("value experts are RoutedValueExperts (takes no quant_config)",
     re.compile(r"self\.v_experts = RoutedValueExperts\(")),
]


def classify(src: str):
    """Return (state, notes)."""
    gate1_stock = STOCK_GATE1 in src
    gate1_patched = PATCHED_GATE1 in src
    gate2_stock = STOCK_GATE2 in src
    gate2_patched = PATCHED_GATE2 in src

    if gate1_stock and gate2_stock:
        return "A", "stock: both gates present"
    if gate1_patched and gate2_stock:
        return "B", "gate 1 relaxed, gate 2 still refuses MoVA quantisation"
    if gate1_patched and gate2_patched:
        return "C", "both gates relaxed for block-fp8"
    if not (gate1_stock or gate1_patched):
        return "D", "neither gate-1 form recognised; sglang has moved"
    if not (gate2_stock or gate2_patched):
        return "D", "neither gate-2 form recognised; sglang has moved"
    return "D", "unrecognised combination"


def check_invariants(src):
    bad = []
    for name, pat in INVARIANTS:
        if not pat.search(src):
            bad.append(name)
    # A patch that references a `logger` this module does not define would
    # NameError at build time on every boot. Cheap to check; expensive to learn
    # on a node.
    for m in re.finditer(r"^\s*logger\.\w+\(", src, re.M):
        # only complain about occurrences inside the mod's own injected block
        start = max(0, m.start() - 1200)
        if SENTINEL in src[start:m.start()] and "logger = logging.getLogger" not in src:
            bad.append("injected code calls logger.* but xllm.py defines no logger")
        break
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="path to sglang's srt/models/xllm.py")
    ap.add_argument("--expect", choices=["auto", "stock", "patched"], default="auto",
                    help="fail if the file is not in this state (for CI use)")
    args = ap.parse_args()

    try:
        with open(args.path, encoding="utf-8") as f:
            src = f.read()
    except OSError as e:
        print(f"HARNESS: cannot read {args.path}: {e}")
        return HARNESS_FAIL

    if "XllmForCausalLM" not in src:
        print(f"HARNESS: {args.path} is not an xllm.py (no XllmForCausalLM)")
        return HARNESS_FAIL

    state, note = classify(src)
    print(f"state={state}  {note}")

    bad = check_invariants(src)
    for b in bad:
        print(f"INVARIANT MISSING: {b}")

    if args.expect == "stock" and state != "A":
        print(f"EXPECTED stock, found {state}")
        return 1
    if args.expect == "patched":
        if state != "C":
            print(f"EXPECTED patched, found {state}")
            return 1
        if bad:
            print("PATCHED BUT UNSAFE: the value path no longer matches the "
                  "mod's safety argument. Do not run this tree; re-read "
                  "xllm.py's MoVA construction sites and update the mod.")
            return HARNESS_FAIL

    if state == "A":
        print("VERDICT: unpatched. The FP8 checkpoint is refused at "
              "_validate_mova_config before any weight is read.")
        return 1
    if state == "B":
        print("VERDICT: gate-only. Still refused, now at "
              "_XllmMoVAAttentionBase.__init__ -- once per layer, 48 times, because "
              "both XllmMoVAAttention (layers 3-47) and XllmGatedAttention (the dense "
              "prefix 0-2) subclass that base. This is what "
              "SPARKRUN_K2_FP8_GATE_ONLY=1 produces and what the falsification "
              "arm expects.")
        return 1
    if state == "D":
        print("VERDICT: NONE. Anchors do not match this sglang; do not read "
              "anything into this result.")
        return HARNESS_FAIL
    if bad:
        print("VERDICT: patched but the invariants above are gone.")
        return HARNESS_FAIL
    print("VERDICT: patched, invariants intact.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
