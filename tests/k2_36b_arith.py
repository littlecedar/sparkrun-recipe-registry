"""Exact byte census + roofline arithmetic for the K2-Horizon MoVA-36B-A4B lane.

Single source of truth for every number quoted in
recipes/ifm/K2-36B-A4B-MODEL-OPTIMIZATION-WORK.md, the four 36B recipes, and
tests/test_ifm_36b_recipes.py. Run it before editing any of those prose figures; the
guard test imports these constants and fails if the prose disagrees.

Why this exists. While drafting this lane I shipped four wrong figures into prose that
no linter can see: routed experts written as 26.521 GB instead of 26.542 GB, the
expert scale tensors as 0.028 GB instead of 0.0065 GB, the attention projection count
as 219 instead of 195, and a TP=2 table whose gains were wrong because the fixed
per-step cost was dropped from the TP=2 leg. Recomputing from the tensor census and
asserting the prose matches is the only thing that catches that class of mistake.

Modes:
  python3 k2_arith.py print    print the derived table the docs quote
  python3 k2_arith.py check    if the header cache is present, assert BUCKETS still
                               reconciles against it; otherwise skip (the constants
                               below are the pinned authority -- re-downloading 48
                               shard headers to run a unit test is not acceptable)
  python3 k2_arith.py selftest assert internal consistency (sums, divisibility)

Header cache: /tmp/IFM_K2-Horizon-MoVA-36B-A4B-FP8_hdr/*.json, produced by HTTP range
reads of the 48 shard headers (fetcher: .scratch/ifm/k2_anatomy.py, git-ignored). The
cache is machine-local by design, so `check` SKIPS without it and the unit test does
not depend on it: the pinned BUCKETS/COUNTS below are the authority the prose is
checked against, and re-downloading 48 headers to run a unit test is not acceptable.
"""
import glob
import json
import os
import sys

REPO = "IFM/K2-Horizon-MoVA-36B-A4B-FP8"
REPO_BYTES = 48_390_779_584           # HF API tree total, incl. non-weight files
WEIGHTS_BYTES = 48_353_984_040        # sum of safetensors tensor bytes
TENSOR_COUNT = 30_498
HDR_CACHE = "/tmp/IFM_K2-Horizon-MoVA-36B-A4B-FP8_hdr"

# ---- pinned census, in bytes, by bucket ------------------------------------
# Derivations in workdoc table 1.1. Exact, not rounded.
BUCKETS = {
    "routed_expert_weights": 26_542_080_000,   # 13,500 x F8_E4M3, 3 per expert x 100 x 45
    "routed_expert_scales":       6_480_000,   # 13,500 x F32 [6,20]/[20,6] = 480 B each
    "mova_value_experts":      15_099_494_400,  # 2,880 x [1024, 2560] BF16
    "attn_projections":         3_287_285_760,  # 195 BF16 (q/o/gate 48 each, k 48, v_proj 3)
    "embed_and_lm_head":        2_566_389_760,  # 2 BF16, each 250624 x 2560
    "shared_expert":              530_841_600,  # 135 BF16
    "dense_ffn_layers_0_2":       283_115_520,  # 9 BF16
    "moe_router":                  23_049_000,  # 45 BF16 weight [100,2560] + 45 F32 bias
    "mova_router":                 14_751_360,  # 45 BF16 weight [64,2560] + 45 F32 bias
    "layernorms":                     496_640,  # 97
}
COUNTS = {
    "routed_expert_weights": 13_500,
    "routed_expert_scales": 13_500,
    "mova_value_experts": 2_880,
    "attn_projections": 195,
    "embed_and_lm_head": 2,
    "shared_expert": 135,
    "dense_ffn_layers_0_2": 9,
    "moe_router": 90,
    "mova_router": 90,
    "layernorms": 97,
}

# ---- architecture ----------------------------------------------------------
H, L = 2560, 48
NH, NKV, HD = 32, 8, 128
VOCAB, MAX_POS = 250_624, 524_288
N_EXPERTS, TOP_K, MOE_INTER = 100, 8, 768
MOVA_N, MOVA_K = 64, 4
DENSE_LAYERS = 3
BLOCK = 128

KV_BYTES_PER_TOKEN = 2 * L * NKV * HD * 2       # K+V, bf16 = 196_608

# ---- roofline constants, imported from the qwen4 lane ----------------------
# LIKELY for this model, not measured here. Re-fitting B and F on this checkpoint
# is experiment E1 and every t/s below inherits its error bars.
BW_MARGINAL = 145.5e9      # B in t = F + bytes/B, marginal GB/s during real decode
BW_PEAK = 241.8e9          # best f32.sum observed
FIXED_STEP = 8.4e-3        # F, s
SPEC_BW = 273e9            # LPDDR5X theoretical per GB10
N_ALLREDUCE_PER_TOKEN = 2 * L                   # post-attn + post-MLP, 48 layers


def gb(x):
    return x / 1e9


def replicated_bytes():
    """Buckets that TP cannot shard: the two routers are ReplicatedLinear."""
    return BUCKETS["moe_router"] + BUCKETS["mova_router"]


def bytes_per_token(fp8=True):
    """Weight bytes read per decoded token at c=1.

    embed_tokens is a row gather and is excluded; lm_head is a full [V, H] GEMV every
    token and is included, which is 15.1 % of the total and the single largest
    non-expert term. MoVA selects 4 of 64 value experts; MoE selects 8 of 100.
    """
    moe = BUCKETS["routed_expert_weights"] * (TOP_K / N_EXPERTS) * (1 if fp8 else 2)
    return (
        BUCKETS["attn_projections"]
        + BUCKETS["mova_value_experts"] * (MOVA_K / MOVA_N)
        + moe
        + BUCKETS["shared_expert"]
        + BUCKETS["dense_ffn_layers_0_2"]
        + BUCKETS["embed_and_lm_head"] / 2      # lm_head half only
        + replicated_bytes()
    )


def per_rank_at_tp2(bpt=None):
    bpt = bytes_per_token(True) if bpt is None else bpt
    rep = replicated_bytes()
    return (bpt - rep) / 2 + rep


def t_step(bytes_read, F=FIXED_STEP, B=BW_MARGINAL, allreduce_us=0.0):
    """Decode step time. The F term is NOT divided by TP: synchronising two ranks does
    not halve per-step launch and bookkeeping overhead. Dropping that fact from the
    TP=2 leg is what made my first TP=2 table wrong."""
    return F + bytes_read / B + N_ALLREDUCE_PER_TOKEN * allreduce_us * 1e-6


# ---- ignored_layers census -------------------------------------------------
# Fetching config.json at unit-test time is not acceptable (network in a test suite),
# so this is pinned from a fetch performed 2026-09-21 and reconciled to 3408. The
# reason it is pinned here rather than left in prose is that three of the seven wrong
# numbers this lane produced were prose enumerations that no assertion added up.
IGNORED_LAYER_BUCKETS = {
    "self_attn.v_experts.{e}": 2880,          # 64 value experts x 45 MoVA layers
    "self_attn.{q,k,v,o,gate}_proj": 195,     # 4/layer x 48 + 3 v_proj on layers 0-2
    "mlp.shared_experts.{gate,up,down}_proj": 135,   # 3 x 45
    "{input,post_attention}_layernorm": 96,   # 2 x 48
    "self_attn.v_router": 45,
    "mlp.gate (routed-MoE router)": 45,       # BARE module path, no ".weight"
    "layers.{0,1,2}.mlp.{gate,up,down}_proj": 9,
    "lm_head": 1,
    "model.embed_tokens": 1,
    "model.norm": 1,
}
IGNORED_LAYER_TOTAL = 3408
# Absent from ignored_layers, and that absence is the whole point:
NOT_IGNORED = "mlp.experts.*"


def kv_read_bytes(context, fp8_kv=False):
    """KV bytes one decode step READS for a single sequence of `context` tokens.

    This is the term my first roofline omitted, and it is the largest correction in
    this file. Attention over a sequence of length S reads S keys and S values per KV
    head per layer, so the per-step read equals the sequence's whole KV footprint --
    the same 196,608 B/token as the cache grows by, but consumed every step rather
    than written once. At S = 32 768 that is 6.44 GB against an 8.49 GB weight read;
    at S = 131 072 it is 25.77 GB, three times the weights.

    Consequences that change recipe decisions:
      * the weight-only figure quoted elsewhere in the docs is valid at SHORT context
        only, and must be labelled as such;
      * weight-vs-KV crossover is at bytes_per_token / KV_BYTES_PER_TOKEN ~= 43k
        tokens, so 32K already sits near it and 131K is deep in KV-bound territory;
      * fp8 KV is therefore not merely a capacity knob -- past crossover it halves the
        dominant term, which makes it the biggest long-context lever in this family;
      * TP=2 splits the KV read as well as the weight read, an independent second
        reason the long-context arm wants two nodes.
    """
    return KV_BYTES_PER_TOKEN * context * (0.5 if fp8_kv else 1.0)


def kv_crossover_context(fp8=True):
    """Context length at which the per-step KV read equals the weight read."""
    return bytes_per_token(fp8) / KV_BYTES_PER_TOKEN


def bytes_per_step(context=1024, fp8=True, fp8_kv=False):
    return bytes_per_token(fp8) + kv_read_bytes(context, fp8_kv)


def decode(context=1024, fp8=True, fp8_kv=False, tp=1, allreduce_us=0.0,
           F=FIXED_STEP, B=BW_MARGINAL):
    """Modelled single-stream decode speed including the KV read.

    c=1 only: at higher concurrency the weight read amortises across the batch while
    the KV read does not, so the mix moves further toward KV. Nothing here models that.
    """
    b = bytes_per_step(context, fp8, fp8_kv)
    if tp == 2:
        rep = replicated_bytes()
        b = (b - rep) / 2 + rep
    return 1.0 / t_step(b, F=F, B=B, allreduce_us=allreduce_us)


def ts(bytes_read, **kw):
    return 1.0 / t_step(bytes_read, **kw)


def tp2_break_even_us(context=1024, fp8_kv=False):
    """Cross-node allreduce latency at which TP=2 stops beating TP=1, AT A GIVEN
    CONTEXT.

    Context matters because TP=2 splits the KV read too, so the bytes saved -- and
    therefore the latency TP=2 can afford -- grow with sequence length. Quoting one
    break-even number without a context is how the first version of this table
    overstated the short-context case and understated the long one.
    """
    b1 = bytes_per_step(context, True, fp8_kv)
    rep = replicated_bytes()
    b2 = (b1 - rep) / 2 + rep
    return (b1 - b2) / BW_MARGINAL / N_ALLREDUCE_PER_TOKEN * 1e6


def tp2_table(context=1024, fp8_kv=False):
    """[(L_us, t/s, gain over TP=1)] using the same F on both legs."""
    base = decode(context, True, fp8_kv, tp=1)
    rows = []
    for L in (10, 30, 100, 300, 600):
        v = decode(context, True, fp8_kv, tp=2, allreduce_us=L)
        rows.append((L, v, v / base - 1.0))
    return base, rows


def outside_fp8_fraction():
    b = bytes_per_token(True)
    quantised = BUCKETS["routed_expert_weights"] * (TOP_K / N_EXPERTS)
    return (b - quantised) / b


def fp8_gain_over_bf16():
    return ts(bytes_per_token(True)) / ts(bytes_per_token(False)) - 1.0


# ---- verification ----------------------------------------------------------
def check_against_cache(strict=False):
    files = sorted(glob.glob(os.path.join(HDR_CACHE, "*.json")))
    if not files:
        if strict:
            raise SystemExit(f"header cache {HDR_CACHE} is empty; cannot verify")
        print(f"SKIP: no header cache at {HDR_CACHE}; constants are pinned")
        return None
    seen, total, n = {}, 0, 0
    for f in files:
        for k, v in json.load(open(f)).items():
            if k == "__metadata__":
                continue
            esz = {"BF16": 2, "F32": 4, "F8_E4M3": 1}[v["dtype"]]
            nb = esz
            for d in v.get("shape", []):
                nb *= d
            seen[k] = nb
            total += nb
            n += 1
    ok = True
    if total != WEIGHTS_BYTES:
        print(f"MISMATCH total bytes: cache {total} != pinned {WEIGHTS_BYTES}")
        ok = False
    if n != TENSOR_COUNT:
        print(f"MISMATCH tensor count: cache {n} != pinned {TENSOR_COUNT}")
        ok = False
    # per-bucket reconciliation by name pattern
    def bucket(k):
        if "v_experts." in k:
            return "mova_value_experts"
        if "v_router" in k:
            return "mova_router"
        if "experts." in k and "shared" not in k:
            return "routed_expert_scales" if k.endswith("weight_scale_inv") else "routed_expert_weights"
        if "shared_experts" in k:
            return "shared_expert"
        if "self_attn" in k:
            return "attn_projections"
        if any(re_k in k for re_k in (".mlp.gate_proj", ".mlp.up_proj", ".mlp.down_proj")):
            return "dense_ffn_layers_0_2"
        if ".mlp.gate." in k:
            return "moe_router"
        if k in ("lm_head.weight", "model.embed_tokens.weight"):
            return "embed_and_lm_head"
        return "layernorms"
    agg = {}
    for k, nb in seen.items():
        agg[bucket(k)] = agg.get(bucket(k), 0) + nb
    for name, want in BUCKETS.items():
        got = agg.get(name, 0)
        if got != want:
            print(f"MISMATCH {name}: cache {got} != pinned {want}")
            ok = False
    print("CACHE CHECK:", "OK" if ok else "FAILED")
    return ok


def selftest():
    assert sum(BUCKETS.values()) == WEIGHTS_BYTES, (
        f"buckets sum {sum(BUCKETS.values())} != weights {WEIGHTS_BYTES}")
    assert sum(COUNTS.values()) == TENSOR_COUNT
    # ignored_layers must add up: this is the check that would have caught the
    # 3362-vs-3408 prose error before it was written down.
    assert sum(IGNORED_LAYER_BUCKETS.values()) == IGNORED_LAYER_TOTAL, (
        f"ignored_layers buckets sum {sum(IGNORED_LAYER_BUCKETS.values())} "
        f"!= {IGNORED_LAYER_TOTAL}")
    # and the counts that appear in BOTH censuses must agree with each other
    assert COUNTS["mova_value_experts"] == IGNORED_LAYER_BUCKETS["self_attn.v_experts.{e}"]
    assert COUNTS["attn_projections"] == IGNORED_LAYER_BUCKETS["self_attn.{q,k,v,o,gate}_proj"]
    assert COUNTS["shared_expert"] == IGNORED_LAYER_BUCKETS["mlp.shared_experts.{gate,up,down}_proj"]
    assert COUNTS["dense_ffn_layers_0_2"] == IGNORED_LAYER_BUCKETS["layers.{0,1,2}.mlp.{gate,up,down}_proj"]
    # scale buffer geometry: [6,20] and [20,6] F32 = 480 B
    assert BUCKETS["routed_expert_scales"] == 13_500 * 480
    # block divisibility, the TP ceiling
    assert MOE_INTER % BLOCK == 0 and (MOE_INTER // 2) % BLOCK == 0
    assert (MOE_INTER // 4) % BLOCK != 0 and (MOE_INTER // 8) % BLOCK != 0
    assert KV_BYTES_PER_TOKEN == 196_608
    b = bytes_per_token(True)
    assert 8.4 < gb(b) < 8.6, gb(b)
    assert outside_fp8_fraction() > 0.7
    # lm_head must be included and must be exactly half the embed bucket
    assert abs(BUCKETS["embed_and_lm_head"] / 2 - VOCAB * H * 2) < 1, "embed/head asymmetry"
    assert fp8_gain_over_bf16() > 0.2
    assert 200 < tp2_break_even_us() < 400
    # KV term: 196,608 B/token, and crossover must be a sane short-context length
    assert abs(kv_read_bytes(1) - KV_BYTES_PER_TOKEN) < 1
    assert 30_000 < kv_crossover_context() < 50_000
    # at 131k the KV read must dominate the weight read by a wide margin
    assert kv_read_bytes(131_072) > 3 * bytes_per_token(True)
    # TP=2 must help more at long context than at short (KV splits too)
    assert tp2_break_even_us(131_072) > tp2_break_even_us(1024)
    # decode() and ts() must agree at context -> 0, or the two code paths drifted
    assert abs(decode(0) - ts(bytes_per_token(True))) < 1e-9
    print("SELFTEST OK")


def show():
    b8, b16 = bytes_per_token(True), bytes_per_token(False)
    print("=== per-token weight bytes at c=1")
    terms = [
        ("attention q/k/o/gate(+v_proj)", BUCKETS["attn_projections"]),
        ("MoVA value experts, 4 of 64", BUCKETS["mova_value_experts"] * MOVA_K / MOVA_N),
        ("routed experts, 8 of 100 (fp8)", BUCKETS["routed_expert_weights"] * TOP_K / N_EXPERTS),
        ("shared expert", BUCKETS["shared_expert"]),
        ("dense FFN, layers 0-2", BUCKETS["dense_ffn_layers_0_2"]),
        ("lm_head (full GEMV)", BUCKETS["embed_and_lm_head"] / 2),
        ("MoVA + MoE routers (replicated)", replicated_bytes()),
    ]
    for n, v in terms:
        print(f"  {n:36s} {gb(v):7.4f} GB  {gb(v)/gb(b8):5.1%}")
    print(f"  {'TOTAL FP8 checkpoint':36s} {gb(b8):7.4f} GB")
    print(f"  {'TOTAL BF16 checkpoint':36s} {gb(b16):7.4f} GB")
    print(f"  outside the FP8-quantised set: {outside_fp8_fraction():.1%}")
    print(f"  lm_head share of the FP8 step:  {gb(BUCKETS['embed_and_lm_head']/2)/gb(b8):.1%}")

    print("\n=== modelled decode (t = F + bytes/B, F=8.4 ms, B=145.5 GB/s)")
    print(f"  FP8 c=1 TP=1 : {t_step(b8)*1e3:6.2f} ms  {ts(b8):5.1f} t/s")
    print(f"  FP8 pure-BW  : {gb(b8)*1e9/BW_PEAK*1e3:6.2f} ms  {BW_PEAK/1e9/gb(b8):5.1f} t/s"
          f"   (F=0, peak BW: unreachable ceiling)")
    print(f"  FP8 F=16 ms  : {t_step(b8, F=0.016)*1e3:6.2f} ms  {ts(b8, F=0.016):5.1f} t/s")
    print(f"  BF16 c=1 TP=1: {t_step(b16)*1e3:6.2f} ms  {ts(b16):5.1f} t/s"
          f"   (FP8 worth {fp8_gain_over_bf16():+.1%})")

    pr = per_rank_at_tp2(b8)
    print(f"\n=== TP=2 (cross-node). per-rank {gb(pr):.4f} GB, "
          f"saving {gb(b8-pr):.4f} GB = {gb(b8-pr)*1e9/BW_MARGINAL*1e3:.2f} ms")
    print(f"  break-even allreduce latency: {tp2_break_even_us():.0f} us "
          f"({N_ALLREDUCE_PER_TOKEN} collectives/token)")
    print(f"  {'L_us':>6s} {'t2_ms':>8s} {'t/s':>6s} {'vs TP1':>8s}")
    for L_us in (10, 30, 100, 300, 600):
        t2 = t_step(pr, allreduce_us=L_us)
        print(f"  {L_us:6d} {t2*1e3:8.2f} {1/t2:6.1f} {1/t2/ts(b8)-1:+7.1%}")
    print("  CAVEAT: this model is optimistic at small L. It holds F constant and "
          "assumes a 5 KB allreduce costs only its wire latency; it does not charge "
          "for the NCCL kernel's own launch, for the synchronisation making F grow "
          "under TP, or for NVLink-free PCIe staging. Read the +40 % at L=100 us as "
          "'up to tens of percent, sign unknown', not as a promise. E3 measures it.")

    print("\n=== KV cache")
    print(f"  {KV_BYTES_PER_TOKEN} B/token = {KV_BYTES_PER_TOKEN/1024:.1f} KiB "
          f"(48 layers x 8 KV heads x 128 head_dim x 2 x 2 B)")
    for c in (8192, 32_768, 131_072, 524_288):
        print(f"  ctx {c:7d}: {gb(KV_BYTES_PER_TOKEN*c):7.2f} GB  "
              f"fp8-KV {gb(KV_BYTES_PER_TOKEN*c/2):7.2f} GB  "
              f"| TP=2 bf16 {gb(KV_BYTES_PER_TOKEN*c/2):6.2f} GB/rank")
    print(f"  full 524 288 at bf16 KV is {gb(KV_BYTES_PER_TOKEN*MAX_POS):.2f} GB "
          f"= {gb(KV_BYTES_PER_TOKEN*MAX_POS)/128:.0%} of one node's unified memory")

    print("\n=== TP legality for block-FP8 (Fp8MoEMethod requires "
          "moe_intermediate/TP % 128 == 0)")
    for tp in (1, 2, 4, 8):
        q = MOE_INTER // tp
        print(f"  TP={tp}: {MOE_INTER}/{tp} = {q:4d}  {q % BLOCK == 0 and 'OK' or 'RAISES'}")
    print("  => FP8 arms are TP in {1,2}. BF16 arms have no block gate.")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "print"
    if mode == "print":
        selftest(); show()
    elif mode == "check":
        selftest(); check_against_cache(strict="--strict" in sys.argv)
    elif mode == "selftest":
        selftest()
    else:
        raise SystemExit(f"unknown mode {mode!r}")
