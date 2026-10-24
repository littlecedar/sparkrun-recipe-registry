#!/usr/bin/env python3
"""sparkrun -> boot.py launcher shim for the knapcio DSV41 SGLang stack.

The `dsv41-4x-spark:canary-roce` image is built from knapcio's
DeepSeek-V4.1-Flash-4x-DGX-Spark-TP4 repo. Its normal entrypoint is
`python3 -u /opt/dsv41/boot.py run`, which reads every serve parameter from
environment variables (MODEL_PATH, NNODES, NODE_RANK, DIST_INIT_ADDR, ...) and
builds the full `sglang.launch_server` argv itself.

sparkrun's SGLang runtime appends the per-node rendezvous flags
`--dist-init-addr HOST:PORT --nnodes N --node-rank R` to the recipe's serve
command (it assumes the command is `sglang serve ...`). This shim consumes those
flags, maps them onto boot.py's environment, and execs boot.py unchanged -- so
the recipe stays a normal sparkrun recipe and the vendored overlay is untouched.

Usage (rendered by the recipe's `command:` template, with sparkrun's node args
appended):

    python3 /workspace/mods/dsv41-sglang-overlay/launcher.py --boot --model M \
        --port 8888 --tp 4 --served-model-name M --context-length 1048576 \
        [--dist-init-addr H:P] [--nnodes N] [--node-rank R]

`--health` forwards to boot.py's health probe (used for a manual check).

The recipe's `--context-length {max_model_len}` maps onto boot.py's
CONTEXT_LENGTH. This is load-bearing: `boot.py` builds the whole
`sglang.launch_server` argv from the environment, so a `--context-length` it
never parses would leave CONTEXT_LENGTH at its default and the server would
advertise the wrong context. CONTEXT_LENGTH is applied AFTER `apply_recipe_env`
so the recipe's value wins over the launcher's own default (see main()).

Engram shards. The overlay serves the two 203 GB Engram tables from node-local
packed shards, one per rank, under `$DSV41_PACKED_DIR` (the recipe points this at
`/cache/runtime/engram`, the sparkrun-managed runtime cache). Those shards are a
cacheable artifact -- ~47 GiB/rank, derived from the checkpoint -- and must not
live in a user's home directory. They are produced by the image's
`/opt/dsv41/scripts/pack_engram.py`. This shim materializes *this rank's* shards
before booting:

  * rank from `--node-rank` (sparkrun passes it to the head and every worker),
  * if both shards already exist -> nothing to do,
  * otherwise launch the packer **detached** (flock-guarded, one per node) and
    boot immediately. boot.py then reads Engram straight from the checkpoint for
    that boot; the packed shards are picked up on the next boot.

The pack is deliberately not synchronous: a cold pack is minutes long, and
sparkrun only waits ~150 s for the head to open its rendezvous port before it
declares the launch dead. Backgrounding keeps every boot inside that budget;
correctness is unaffected because the checkpoint fallback is exact (see
`adapter/engram_backend.py`: the packed shard is an optional acceleration, and
`row_store.cpp` fails closed if a shard does not match the rank's row range).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

BOOT = "/opt/dsv41/boot.py"
PACKER = "/opt/dsv41/scripts/pack_engram.py"
ENGRAM_LAYERS = (1, 14)
# The HF cache is bind-mounted at a fixed path inside the container (sparkrun's
# orchestration/primitives.py), so the launcher can resolve the checkpoint here
# instead of the recipe spelling a snapshot hash in env:.
HF_HUB = "/cache/huggingface/hub"

# ---------------------------------------------------------------------------
# Recipe-owned environment.
#
# The recipe's `env:` block is deliberately thin: it carries only the external
# checkpoint path and the TP degree. Everything else the engine needs is the
# production configuration for this stack, and it lives here so the recipe does
# not have to spell engine internals (and so the values travel with the mod
# rather than with each recipe that uses it). These OVERRIDE (not setdefault):
# the image bakes several of them into its ENV (STATE_PATH=/state,
# DSV41_CACHE_GIB=16, PYTORCH_CUDA_ALLOC_CONF=...True, SGLANG_RUST_BUILD_MODE,
# OFFLOAD_MODE), and those live in the launcher's process env, so a setdefault
# would let the image value win and silently undo the production config
# (unwritable /state, the NaN-logits allocator mode). The keys here are disjoint
# from the recipe-owned MODEL_PATH / DSV41_SOURCE / TP_SIZE, so those pass through.
# The exception is AB_ENV (defined under RECIPE_ENV): the knobs a sweep flips
# apply with setdefault instead, so `-o env.KEY=VALUE` on the launch wins. That
# is only sound for keys the image does NOT bake; AB_ENV says which, and why.
#
# REDUNDANT vars (recipe value == runtime default) are NOT here and are NOT in
# the recipe: SKIP_SMOKE(0), WARMUP(1), HOST(0.0.0.0), SERVED_MODEL_NAME,
# SPARK_PREFILL_TP_MIN_CONTEXT(32768), SPARK_PREFILL_TP_MIN_ROWS(1024),
# DSV41_FAST_LOAD_TP_SLICE(auto), DSV41_FAST_LOAD_INFLIGHT_GB(6),
# CUDA_GRAPH_MAX_BS_DECODE (boot.py defaults it to MAX_RUNNING_REQUESTS, so
# pinning it separately would be a second place to drift).
#
# DSV41_FAST_LOAD("1") is NOT redundant: adapter/fast_load.py's enabled() reads
# the variable with a "0" default, so the image's loader is stock unless this
# line turns the eager path on. It is stated here to record the 2026-10-22
# decision (fast boot over the larger pool); "0" is the rollback. (Its N_EXPERTS
# companion is gone: it only served the fast path and defaults from
# config.json's n_routed_experts when unset.)
#
# NCCL_NET / NCCL_IB_HCA / NCCL_IB_GID_INDEX / NCCL_IB_DISABLE / NCCL_CROSS_NIC
# and B12X_ROCE_HCA are also absent on purpose: sparkrun's InfiniBand probe fills
# them per cluster, and b12x falls back to the detected NCCL_IB_HCA. Naming a
# host device here would break portability.
# ---------------------------------------------------------------------------
_CACHE = "/cache/runtime"
# The 1017 refresh ships no Jinja template on purpose (its card points at
# encoding/encoding.py), and SGLang resolves the chat template from
# <model_dir>/chat_template.jinja, so the launcher serves a symlink farm whose one
# real file is this mod's copy (see ensure_template_overlay).
TEMPLATE_NAME = "chat_template.jinja"
OVERLAY_DIR = f"{_CACHE}/model-overlay"
# Rendezvous for the image's baked HEALTHCHECK: a fixed path the health probe
# reads its port from. A literal (not $STATE_PATH) because the image bakes
# STATE_PATH=/state while the launcher relocates it under /cache/runtime.
HEALTH_PORT_FILE = "/tmp/sparkrun_health_port"

# The accurate KV pool pin for the STOCK loader (DSV41_FAST_LOAD=0): the
# measured 2026-10-24 control pool. Under the fast loader the pin is dropped
# entirely (see apply_recipe_env) — that is a per-mode decision, not a value.
MAX_TOTAL_TOKENS_STOCK = "6849792"
RECIPE_ENV: dict[str, str] = {
    # --- locations (all under the sparkrun-managed runtime cache) ----------
    "STATE_PATH": f"{_CACHE}/state",
    "DSV41_PACKED_DIR": f"{_CACHE}/engram",
    "B12X_ROCE_CACHE_DIR": f"{_CACHE}/b12x-roce",
    "B12X_COMPILE_CACHE_DIR": f"{_CACHE}/b12x-compile",
    # --- boot.py -----------------------------------------------------------
    "SKIP_PREPARE": "1",       # checkpoint distributed to this node by sparkrun
    "SKIP_VERIFY": "1",
    "READY_TIMEOUT_S": "3600",
    "OFFLOAD_MODE": "nvme",    # Engram on NVMe (host = the GPU's unified memory)
    # --- Engram reader (adapter/engram_backend.py, row_store.cpp) ----------
    "DSV41_CACHE_GIB": "4",
    "DSV41_CACHE_WAYS": "16",
    "DSV41_IO_THREADS": "96",
    "DSV41_RESIDENT_SCALES": "0",
    "DSV41_STATS_SECONDS": "60",
    "DSV41_ENGRAM_PREFETCH": "1",
    # --- parallelism / serving (boot.py reads these) -----------------------
    "EP_SIZE": "1",            # b12x_next production line; EP>1 dies at decode
    "CONTEXT_LENGTH": "1048576",
    # v2.4's serve line (upstream README "What runs in production", CHANGELOG
    # 2026-10-12): 0.78 and 8192-token chunks. 0.78 is what pays for the larger
    # chunk -- at 0.80 a 1M prefill left the head 2.7 GiB available, at 0.78 it
    # leaves 5.7 GiB (upstream, same image). HEAD_MEM_FRACTION_STATIC is a
    # start-tp4.sh-level knob: at TP4 it just equals MEM_FRACTION_STATIC
    # (.env.tp4.example) and boot.py reads only MEM_FRACTION_STATIC
    # (boot.py:312 @ 27616bec), so there is nothing to set separately here.
    "MEM_FRACTION_STATIC": "0.78",
    # 16, not 8. The v2.4 launch line (README: "boot log must show ...
    # max_running_requests=16") and the profile table ("Slots:
    # MAX_RUNNING_REQUESTS=16 adds the c16 tier") both say 16. The 8s in that
    # repo are its *pre-knapcio* profile (README rollback: "Upstream's profile:
    # MAX_RUNNING_REQUESTS=8, CHUNKED_PREFILL_SIZE=1024") and the stale comment
    # above MAX_RUNNING_REQUESTS=16 in .env.tp4.example. No conflict with the
    # v2.4 release note -> 16 stays. It also sizes --cuda-graph-max-bs-decode
    # (boot.py:315 defaults that to this value and the launcher does not pin it),
    # so one knob answers both and an A/B cannot leave a 16-wide graph capture
    # behind after lowering the request cap.
    "MAX_RUNNING_REQUESTS": "16",
    # CHUNKED_PREFILL_SIZE flipped 8192 -> 16384 on 2026-10-24 (the QUESTIONS.md #2
    # cell, quartet .31-.34, image acfc331a, task a2e141223b52793c_e2c160f10849):
    # the 1M prefill is chunk-launch-bound, and doubling the chunk halves the launch
    # count (122 -> 61) — five ~999k cold prefills ran 235.3-269.8 s (mean 245.0 s,
    # ~4.09k t/s) against the 8192 control's 543.9-626.2 s (mean ~576 s, 1738 t/s),
    # 2.35x; per-chunk mean 4179 t/s (n=299, median 4159) against the control's
    # saturated ~1500; needle 5/5 PASS at ~999k prompt tokens, so accuracy is intact.
    # Receipts ~/benchmarks/tp4-window-20261024/ (chunk16k-needle.*, boot4-*); the
    # owner's 2026-10-18 [#36] rule (>=2% same-window win, accuracy-neutral flag,
    # boot receipt + lane-doc record) authorizes the flip. DEEPSEEK.md §9.
    "CHUNKED_PREFILL_SIZE": "16384",
    # KV pool pin, re-derived for v2.4 from the engine's own budget arithmetic
    # (pool_configurator.DSV4PoolConfigurator.calculate_pool_sizes):
    #   full_token = (available_bytes - fixed_bytes) / bytes_per_full_token
    #   available_bytes = available_gpu_memory - pre_model_load*(1-mem_frac)
    #                     (kv_cache_configurator._profile_available_bytes)
    # so lowering mem_frac by 0.02 costs 0.02 x pre_model_load of budget, and
    # bytes_per_full_token does NOT move with it (in cap mode the SWA pool is
    # bias bytes, not part of the coefficient).
    # Measured input, current config, TP=4 on this fleet (attic/ds4/AGENTS.md
    # §12.18, two boots 2026-10-18): full_token=9,277,952 at 0.80 with the stock
    # loader at bytes_per_full_token=1670.75 -- that is the engine's profiled
    # value, which the old 9.4M pin was already being clamped down to
    # ("max_total_tokens=9400000 is larger than the profiled value 9277952").
    # (The 2026-10-06 four-boot range 9,493,504..9,589,504 in §7.1 is the older
    # number; both derivations are carried below and the pin fits under both.)
    #   pre_model_load is the rank's 121.7 GiB unified memory (upstream docs;
    #     sparkrun's own platform table agrees: gb10 ~121.0 GiB):
    #     0.02 x 121.7 GiB = 2,613.5 MB / 1670.75 B = 1,564,260 tokens
    #   prefix tails 64 -> 128: each extra tail is one sliding window plus one
    #     page = 128 + 256 = 384 SWA slots, and bytes_per_swa_token is
    #     kv_bytes x draft layers x spec inflation = 584 x 3 x 41/40 = 1,795.8 B
    #     (kv_bytes = 448 nope + 2x64 rope + 8; page_size 256 is hardcoded for
    #     DSV4, deepseek_v4_backend.py:1189). 64 x 384 x 1,795.8 B = 44.1 MB
    #     = 26,415 tokens. The 2026-10-18 boot line confirms the slot count:
    #     swa=51,712 at 64 tails -> 76,288 at 128 (+24,576 = 64 x 384).
    #   => the budget the engine actually profiles at 0.78 on this fleet is
    #      **6,993,408 tokens** (boot 2026-10-18 21:33Z, TP=4: "max_total_tokens=
    #      7500000 is larger than the profiled value 6993408"). The 7.69M
    #      formula above under-estimated the tails' cost by ~0.7M tokens, so the
    #      boot line, not the formula, decides.
    # KV pool pin history, kept because the numbers are the lane's record:
    # the 2026-10-22 pin 6,850,000 was a STOCK-loader measurement (97.9 % of
    # the 6,993,408 budget the engine profiles at 0.78) and the engine clamped
    # it to 6,849,792. Under the fast loader every boot profiles a smaller,
    # variable budget (3,424,000 / 3,846,656 / 4,238,080 / 4,355,584 across the
    # 2026-10-23/24 boots — DEEPSEEK.md §18.2), so a literal there is always
    # clamped and inert. Owner 2026-10-24: pins must be ACCURATE — the static
    # entry is gone; apply_recipe_env derives the pin per mode (6,849,792 on
    # the stock loader via MAX_TOTAL_TOKENS_STOCK, unpinned under the fast
    # loader, an explicit launch override still wins).
    "SPEC_ALGO": "DSPARK",
    # MEASURED, REJECTED (2026-10-10 A/B, same-window pair, profile
    # ds4-sglang-depth0-ladder, nodes .30-.33): the verify window gamma ships
    # at 5. The bertholomus/deepseek-v4.1-flash-dspark-tp4-4xgb10 fork @
    # 90cf3a2b (AGPL — finding tested, code not copied) pre-registered gamma=2
    # as +6-12% over bracketed gamma=3 controls at 8k/32k/96k; our retired
    # EXL3 k-sweep agreed in direction. On THIS lane it does not transfer:
    # paired boots (gamma2 vs gamma5, same day, same nodes) measured
    #   C1 37.70 vs 37.67 (~0), C4 85.29 vs 90.10 (-5.3%),
    #   C8 92.12 vs 94.88 (-2.9%), C16 102.58 vs 98.19 (+4.5%)
    # — gamma=2 loses at moderate concurrency, matching the counter-evidence
    # the fork itself recorded (a peer sweep where wider windows win at 8k).
    # Probable mechanism for the divergence: our shipped DSV41_VERIFY_CAP=
    # conf:0.1 + DSV41_BLOCK_VERIFY=1 interact with the window width (the
    # fork ran no conf cap). Receipts: ~/benchmarks/ds4-gamma2-20261010/
    # {ladder-gamma2,ladder-gamma5-control}.{json,yaml}. Caveat: both boots
    # sit well below the 2026-10-06 receipts (C1 46.5, C16 193) — inter-boot
    # drift on this lane is documented (README caveat); the verdict above is
    # within-pair and survives it, the absolute numbers do not.
    # `--dspark-block-size` (the recipe's `dspark_block_size`) overrides this
    # per launch; this is the shipped default it must stay equal to.
    "DSPARK_BLOCK_SIZE": "5",
    # --- v2.4 serve-line flags (boot.py's EXTRA_SGLANG_ARGS) -----------------
    # boot.py appends EXTRA_SGLANG_ARGS verbatim to the argv it builds
    # (boot.py:373-375 @ 27616bec) and then runs required_sglang_args() over the
    # whole list (boot.py:264-287, called at :376): that guard STRIPS every
    # --fp8-gemm-backend the extras carry and appends
    # `--fp8-gemm-backend flashinfer_cutlass` last (warning when the effective
    # value differed), so an extra flag cannot win the ARG ORDER -- the v2.4 fix
    # (CHANGELOG: "the required --fp8-gemm-backend flashinfer_cutlass survives a
    # custom EXTRA_SGLANG_ARGS", MiaAI-Lab#31). Verified in the pinned image's
    # build source: knapcio boot.py @ 27616bec with this registry's
    # recipes/ds4/boot.py.health-port.patch applied, whose hunks are the health
    # probe, request()'s port argument and __main__'s health branch only --
    # serve(), required_sglang_args() and the extras merge are upstream's bytes.
    # The route is therefore DECLARED, not inherited: the recipe's `command:`
    # passes --fp8-gemm-backend (FP8_GEMM_BACKEND below), so the value the guard
    # re-emits is the one the recipe asked for and its substitution warning
    # ("effective value 'auto (omitted)' replaced") cannot fire. The declaration
    # is also what survives if the image's DSV41_MXFP8_BACKEND default ever goes
    # away: with that backend disabled the guard returns the argv untouched and
    # this flag is the only thing naming the dense-kernel route.
    # Values are assembled by extra_sglang_args() below; each is individually
    # disablable from the launch (0/off/none/false/empty omits the flag and the
    # engine's own default applies).
    #   --swa-prefix-tails 128:  room for 128 radix-cached prefix tails instead
    #     of the engine default (4 x max_running_requests = 64 here), so a 388K
    #     session stays cached while another 388K runs: revisit 1.5 s instead of
    #     an 89 s re-prefill. Each extra tail costs window+page = 384 SWA slots.
    "SWA_PREFIX_TAILS": "128",
    #   --prefill-decode-interval 2:  decode between prefill chunks, so a short
    #     request is answered 4.6 s into a 400K cold prefill instead of after it
    #     (upstream v2.4). MEASURED COST on this fleet's ladder (2026-10-18,
    #     two TP=4 boots differing only in this flag): c2 73.2 -> 88.4, c5 95.1
    #     -> 131.8, c10 101.5 -> 123.5 t/s with it OFF, i.e. it costs 17-28 % of
    #     steady-state ladder throughput. It is a multi-user latency feature, not
    #     a throughput one, so it ships OFF and is flipped per launch with
    #     `-o env.PREFILL_DECODE_INTERVAL=2` when long-prefill interleaving is
    #     what is wanted. The engine default (0) leaves it off.
    "PREFILL_DECODE_INTERVAL": "0",
    # --- overlay adapters (the upstream production line) -------------------
    "DSV41_INDEXER_CHUNKED": "1",
    "SGLANG_DSPARK_FOLDED_SAMPLING": "2",
    "SGLANG_RUST_BUILD_MODE": "never",
    "SPARK_PREFILL_TP_SPLIT": "1",
    # Fast weight loading is ON BY CHOICE (owner decision 2026-10-22; the
    # pool-vs-boot-time tradeoff was re-weighed and boot time won). The gate
    # ships on upstream ("The gate ships on", docs/fast-load.md) and cuts
    # engine start from 343 s to ~124 s. The cost: SGLang sizes the KV pool
    # from the head's MemAvailable right after the loads and the eager pinned
    # reads leave memory visible-but-uncounted then, so the pool comes out
    # smaller and more variable between boots. Upstream's own two documents
    # quote different widths -- docs/fast-load.md 3-6 % at EP2 (7.27M vs
    # 7.47-7.82M tokens), README's summary line the older 3-13 % -- and the
    # EP1 slab rework "gave back ~0.7M tokens" against its per-tensor
    # precursor. The EP1 delta on THIS lane is still UNMEASURED, so the pin is
    # NOT pre-scaled: the first fast-loader boot's `full_token` is the receipt,
    # and the pin is re-derived from it if it clamps. "0" is the stock loader
    # and the rollback; the image's own default is "0" too
    # (adapter/fast_load.py enabled()), so "1" here is a real enablement, not a
    # recorded no-op.
    "DSV41_FAST_LOAD": "1",
    "DSV41_SHARED_PAD_K": "1",
    "DSV41_WO_A_W8": "1",
    "DSV41_WO_A_W8_MID": "1",
    "DSV41_WO_A_W8_DROP": "1",
    "DSV41_DRAFT_TAU": "0.7",
    "DSV41_DRAFT_HEAD_FP8": "1",
    "DSV41_BLOCK_VERIFY": "1",
    "DSV41_FOLDED_FENCE": "1",
    "DSV41_VERIFY_CAP": "conf:0.1",
    "DSV41_AUTOTUNE_KEEP": "1",
    "DSV41_REPLICATED_SPLIT": "wqkv_a,engram.wkv",
    "DSV41_DRAFT_MAIN_PROJ_SPLIT": "1",
    "DSV41_SPLIT_COMPACT_GATHER": "1",
    "DSV41_ROUTER_LIVE": "1",
    "DSV41_MOE_B12X_NEXT": "1",
    "DSV41_MOE_B12X_NEXT_DETERMINISTIC": "1",
    "DSV41_HC_FUSED": "1",
    "DSV41_PREFILL_SP": "1",
    "DSV41_PREFILL_SP_FP8": "1",
    "DSV41_L2_PREFETCH": "1",
    "DSV41_L2_PREFETCH_WOA": "1",
    "DSV41_SPEC_SYNC_FREE": "all",
    "DSV41_EAGER_GLUE": "all",
    # NOTE: DSPARK_SPS_TABLE / DSPARK_STS_TABLE are deliberately NOT set --
    # upstream lists the SPS table under "Not used: crashes the Engram path".
    # --- RoCEnante + NCCL transport (device names come from detection) -----
    "SGLANG_ROCE_ALLREDUCE": "1",
    "SGLANG_ROCE_MAX_SIZE": "2097152",
    "DSV41_ROCE_GATHER": "2097152",
    "NCCL_P2P_DISABLE": "1",
    "NCCL_SHM_DISABLE": "1",
    "NCCL_CUMEM_ENABLE": "0",
    "NCCL_BUFFSIZE": "1048576",
    "NCCL_LL128_BUFFSIZE": "262144",
    "NCCL_PROTO": "^LL128",
    "NCCL_MAX_NCHANNELS": "8",
    "NCCL_DEBUG": "WARN",
    "NCCL_DEBUG_SUBSYS": "INIT,ENV",
    # expandable_segments False: the V4.1 SGLang lane reports NaN logits above 64
    # prefill query tokens with it on (ds4 AGENTS.md §6.4). boot.py's default too.
    "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:False",
    # The image's torch is 2.13.0+cu130, which renamed the collectives
    # all_gather_into_tensor -> all_gather_single and reduce_scatter_tensor ->
    # reduce_scatter_single (PyTorch 2.13 release; the old names remain as
    # aliases behind a FutureWarning). The overlay and the engine still call the
    # old names, so every such call logs, via the _exception_logger wrapper at
    # torch/distributed/c10d_logger.py:83:
    #   FutureWarning: `torch.distributed.all_gather_into_tensor` is deprecated.
    #   Please use `torch.distributed.all_gather_single` instead.
    # (and the reduce_scatter twin). It is a benign once-per-callsite notice
    # about a rename, not a deprecation of behaviour we rely on, and we cannot
    # patch it out -- the callers are in the image's sglang tree and its vendored
    # kernels. Silence ONLY the c10d_logger re-emission of these two torch
    # FutureWarnings. Module-scoped and empirically verified against the pinned
    # image (a bare `message='is deprecated'` filter does NOT take: warnings
    # filterwarnings() anchors the message with re.match, so the leading
    # backtick defeats it; a module filter is robust to the message rewording).
    # `::` with an empty message = any message. Other FutureWarnings, and the
    # c10d debug logger, are untouched. Rollback is deleting this line.
    "PYTHONWARNINGS": ("ignore::FutureWarning:torch.distributed.c10d_logger"),
}


# Knobs a benchmark profile flips per launch: `-o env.MEM_FRACTION_STATIC=0.80`
# (or `-e KEY=VALUE`) lands in this process's env, so for these keys RECIPE_ENV
# is a DEFAULT, not an override. Safe because the pinned image bakes none of
# them (Dockerfile.canary-roce ENV = MODEL_PATH, STATE_PATH, OFFLOAD_MODE,
# DSV41_CACHE_GIB, PYTHONPATH), so a value already present can only have come
# from the launch. Do NOT add an image-baked key to this set (RECIPE_ENV's own
# comment lists them): for those the launcher must win or the image silently
# wins. Everything else here stays an override.
AB_ENV: frozenset[str] = frozenset({
    "MEM_FRACTION_STATIC", "MAX_RUNNING_REQUESTS", "CHUNKED_PREFILL_SIZE",
    "MAX_TOTAL_TOKENS", "SWA_PREFIX_TAILS", "PREFILL_DECODE_INTERVAL",
    # EP_SIZE is here so an experiment recipe can override the production
    # EP=1 without editing this file. The shipped value stays "1" (the
    # b12x_next production line); a launch that sets EP_SIZE>1 is asking for
    # the expert-parallel dispatch path that the lane records as dying at the
    # first decode plan (attic/ds4/AGENTS.md §11, "planned dynamic direct
    # routing is unsupported for this launch shape").
    # DSV41_FAST_LOAD is here for the same reason: the image does not bake it
    # (adapter/fast_load.py enabled() defaults to "0"), and the 2026-10-24
    # FAST_LOAD=0 control boot needs `-o env.DSV41_FAST_LOAD=0` to reach the
    # engine — measured 2026-10-24: with the key left as an override, the
    # launcher's RECIPE_ENV clobbered the override and the serve still logged
    # "DSV41 fast load ARMED" (the §6.2 RECIPE_ENV trap, third instance).
    "DSV41_FAST_LOAD",
    "EP_SIZE",
})

def apply_recipe_env(env: dict[str, str]) -> None:
    """Apply the production config, overriding the image's baked ENV.

    Override, not setdefault: the image bakes several of these (STATE_PATH,
    DSV41_CACHE_GIB, PYTORCH_CUDA_ALLOC_CONF, ...) and those values are in the
    launcher's process env, so setdefault would let the image win. The keys here
    never include the recipe-owned MODEL_PATH / DSV41_SOURCE / TP_SIZE. The
    AB_ENV exceptions are documented at the set.
    """
    for key, value in RECIPE_ENV.items():
        if key in AB_ENV:
            env.setdefault(key, value)
        else:
            env[key] = value
    # The KV pool pin is PER-MODE (owner 2026-10-24, closing QUESTIONS.md #21:
    # "Any pins should be accurate, even if a wrong pin would be harmless").
    #   FAST_LOAD=0: the stock loader profiles 6,999,040 full tokens at 0.78
    #     (control 2026-10-24) and the accurate pool is the MEASURED clamp
    #     6,849,792 — bit-identical to the 2026-10-22 baseline.
    #   FAST_LOAD=1 (the shipped default): four boots profile 3.42-4.36M,
    #     variable with page-cache timing, so no literal is accurate — leave
    #     the pin off (0) and the engine's own profile is the number.
    # A launch that supplies MAX_TOTAL_TOKENS explicitly still wins (the
    # AB_ENV launch-wins semantics, implemented here because the key is no
    # longer a static RECIPE_ENV entry).
    if "MAX_TOTAL_TOKENS" not in env:
        if env.get("DSV41_FAST_LOAD", RECIPE_ENV["DSV41_FAST_LOAD"]) == "1":
            env["MAX_TOTAL_TOKENS"] = "0"
        else:
            env["MAX_TOTAL_TOKENS"] = MAX_TOTAL_TOKENS_STOCK


# The env key and the sglang flag it contributes to EXTRA_SGLANG_ARGS.
SGLANG_EXTRA_FLAGS = (
    ("SWA_PREFIX_TAILS", "--swa-prefix-tails"),
    ("PREFILL_DECODE_INTERVAL", "--prefill-decode-interval"),
    # Deliberately has NO RECIPE_ENV default: the backend is one value the recipe
    # declares in its own `command:` (see the guard note above), so this table only
    # carries whatever the launch supplied.
    ("FP8_GEMM_BACKEND", "--fp8-gemm-backend"),
)
# A value in this set disables its flag (the engine's own default applies).
_DISABLED_VALUES = frozenset({"", "0", "off", "none", "false", "no"})


def extra_sglang_args(env: dict[str, str]) -> str:
    """boot.py's EXTRA_SGLANG_ARGS: the v2.4 flags, then any user extras.

    boot.py splits this on whitespace (boot.py:375), so flag values must not
    contain spaces. An unset knob contributes nothing; so does one disabled in
    the launch. A user-supplied EXTRA_SGLANG_ARGS is appended verbatim and is
    still subject to boot.py's required_sglang_args() guard.
    """
    flags: list[str] = []
    for key, flag in SGLANG_EXTRA_FLAGS:
        value = env.get(key, "").strip()
        if value.lower() not in _DISABLED_VALUES:
            flags += [flag, value]
    extra = env.get("EXTRA_SGLANG_ARGS", "").strip()
    if extra:
        flags.append(extra)
    return " ".join(flags)


def _pack_env(env: dict[str, str]) -> dict[str, str]:
    """Environment for the background packer (inherit, but pin HOME)."""
    return dict(env, HOME=env.get("HOME") or "/tmp")


def ensure_engram_shards(env: dict[str, str], rank: int | None) -> None:
    """Materialize this rank's packed Engram shards, detached if absent.

    Never raises: a shard it cannot build costs the checkpoint fallback (correct,
    slower), while an exception here would cost the launch.
    """
    packed_dir = env.get("DSV41_PACKED_DIR", "").strip()
    if not packed_dir:
        return
    if rank is None:
        print("launcher: no --node-rank/NODE_RANK; skipping Engram pack "
              "(boot.py will read Engram from the checkpoint)", flush=True)
        return
    try:
        tp = int(env.get("TP_SIZE", "4"))
    except ValueError:
        tp = 4

    missing = [
        layer for layer in ENGRAM_LAYERS
        if not _shard_complete(os.path.join(packed_dir, "engram-l%d-r%dof%d.bin" % (layer, rank, tp)))
    ]
    if not missing:
        print("launcher: Engram shards present for rank %d/%d at %s" % (rank, tp, packed_dir), flush=True)
        return
    if not os.path.isfile(PACKER):
        print("launcher: packer %s missing; booting without packed Engram" % PACKER, flush=True)
        return

    os.makedirs(packed_dir, exist_ok=True)
    lock_path = os.path.join(packed_dir, ".pack.lock")
    log_path = os.path.join(env.get("STATE_PATH", packed_dir), "engram-pack.log")
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        log = open(log_path, "ab", buffering=0)
    except OSError:
        log = subprocess.DEVNULL

    # flock -n: if another pack is already running on this node, leave it alone.
    # nice/ionice: the pack is background work; keep it behind the cold boot's
    # weight load (both compete for the same NVMe and the unified memory pool).
    cmd = [
        "flock", "-n", lock_path,
        "nice", "-n", "10", "ionice", "-c", "3",
        sys.executable, PACKER,
        "--rank", str(rank), "--tp", str(tp), "--out", packed_dir,
    ]
    try:
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=_pack_env(env),
            cwd="/opt/dsv41",
        )
        print("launcher: Engram shards missing for rank %d/%d (layers %s); "
              "packing in the background -> %s (log: %s). Booting on the "
              "checkpoint fallback for this boot." % (rank, tp, missing, packed_dir, log_path), flush=True)
    except OSError as exc:
        print("launcher: could not start Engram packer (%r); booting on the "
              "checkpoint fallback" % (exc,), flush=True)


def _shard_complete(path: str) -> bool:
    """Cheap completeness test: the packer renames the finished file into place,
    so a non-empty target with no `.partial` sibling is the done state."""
    try:
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            return False
        return not os.path.exists(path.replace(".bin", ".partial"))
    except OSError:
        return False


def _repo_cache_dir(model: str) -> str:
    """`deepseek-ai/DeepSeek-V4.1-Flash` -> its dir under the HF hub cache."""
    return os.path.join(HF_HUB, "models--" + model.replace("/", "--"))


def _resolved_models_dir(model: str) -> str | None:
    """The local:local dir to serve *model* from, or ``None`` if not resolvable.

    The recipe names the model (``{model}``) and the launcher locates it in the
    fixed in-container HF cache, so no snapshot hash is spelled in `env:` (where
    it would read as a path the user must maintain). Robust to the cache
    re-resolving: prefer `refs/main`, else any snapshot carrying both `config.json`
    and `model.safetensors.index.json`. ``None`` means "not found", and the caller
    leaves MODEL_PATH unset so the engine's own error is the one seen.
    """
    import glob

    repo = _repo_cache_dir(model)
    if not os.path.isdir(repo):
        return None

    candidates: list[str] = []
    try:
        with open(os.path.join(repo, "refs", "main")) as handle:
            revision = handle.read().strip()
        if revision:
            candidates.append(os.path.join(repo, "snapshots", revision))
    except OSError:
        pass
    candidates += sorted(glob.glob(os.path.join(repo, "snapshots", "*")), reverse=True)

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if os.path.isfile(os.path.join(candidate, "config.json")) and \
           os.path.isfile(os.path.join(candidate, "model.safetensors.index.json")):
            return candidate
    return None


def _is_checkpoint_dir(path: str) -> bool:
    """A directory that is itself a servable checkpoint (carries config.json)."""
    return bool(path) and os.path.isfile(os.path.join(path, "config.json"))


def _model_id_from_snapshot(path: str) -> str | None:
    """Invert the HF hub cache layout: `.../models--<org>--<name>/...` -> `<org>/<name>`.

    ``None`` when no ``models--`` segment is present. The HF id grammar keeps a
    ``--`` out of an org name, so the first split is the org/name boundary.
    """
    for segment in os.path.normpath(path).split(os.sep):
        if segment.startswith("models--"):
            org, _, name = segment[len("models--"):].partition("--")
            if org and name:
                return org + "/" + name
    return None


def _clean_served_name(value: str) -> str:
    """A served-model name that arrived as a filesystem path -> a clean name."""
    if not os.path.isabs(value):
        return value
    return _model_id_from_snapshot(value) or os.path.basename(value.rstrip("/")) or value


def ensure_template_overlay(
    env: dict[str, str],
    checkpoint: str,
    template: str | None = None,
    overlay_dir: str | None = None,
) -> None:
    """Serve a dir carrying a ``chat_template.jinja`` when the checkpoint has none.

    boot.py hands ``MODEL_PATH`` to SGLang's OpenAI server, which resolves the chat
    template from ``<model_dir>/chat_template.jinja``
    (``srt/utils/hf_transformers/processor.py:383-390``: when the tokenizer carries
    no embedded template it reads ``Path(local_path)/"chat_template.jinja"``). The
    2026-10-17 refresh ships no template by design (its card replaces the Jinja
    template with ``encoding/encoding.py``), and boot.py exposes no
    template flag of its own, so a straight re-pin would serve a templateless
    endpoint. The overlay is a symlink farm of the checkpoint with one real file:
    nothing is copied (a 475 GB checkpoint), the node's HF snapshot is never
    written through, and a checkpoint that already carries a template (the V4.1
    arm) is served exactly as resolved.

    Rebuilt from content every boot, not from timestamps: links to another
    checkpoint's entries are dropped, so a re-pin cannot serve a mixed tree.
    ``template``/``overlay_dir`` are seams for the guard test; both default to the
    mod-side file and the runtime cache.
    """
    if os.path.isfile(os.path.join(checkpoint, TEMPLATE_NAME)):
        return
    template = template or os.path.join(
        os.path.dirname(os.path.realpath(__file__)), TEMPLATE_NAME)
    overlay = overlay_dir or OVERLAY_DIR
    if not os.path.isfile(template):
        print(f"launcher: {checkpoint} ships no {TEMPLATE_NAME} and the mod dir has "
              "none; refusing to serve a templateless endpoint", flush=True)
        raise SystemExit(2)

    target_file = os.path.join(overlay, TEMPLATE_NAME)
    try:
        os.makedirs(overlay, exist_ok=True)
        names: set[str] = set()
        for name in os.listdir(checkpoint):
            if name == TEMPLATE_NAME:
                continue
            names.add(name)
            target = os.path.join(checkpoint, name)
            link = os.path.join(overlay, name)
            if os.path.islink(link) and os.readlink(link) == target:
                continue
            if os.path.islink(link) or os.path.exists(link):
                os.unlink(link)
            os.symlink(target, link)
        for name in os.listdir(overlay):
            if name == TEMPLATE_NAME or name in names:
                continue
            stale = os.path.join(overlay, name)
            if os.path.islink(stale) or os.path.isfile(stale):
                os.unlink(stale)

        with open(template, "rb") as handle:
            data = handle.read()
        try:
            with open(target_file, "rb") as handle:
                current = handle.read()
        except OSError:
            current = None
        if current != data:
            tmp = target_file + ".tmp"
            with open(tmp, "wb") as handle:
                handle.write(data)
            os.replace(tmp, target_file)
    except OSError as exc:
        # An unwritable runtime cache must not surface as a traceback: the launch
        # would fail with no statement of what was missing from where.
        print(f"launcher: could not stage the chat template under {overlay} "
              f"({exc!r}); refusing to serve a templateless endpoint", flush=True)
        raise SystemExit(2)

    # Never chown through a link: that would rewrite the node's HF snapshot owner.
    try:
        cache = os.stat(_CACHE)
        os.chown(overlay, cache.st_uid, cache.st_gid)
        os.chown(target_file, cache.st_uid, cache.st_gid)
    except OSError:
        pass

    env["MODEL_PATH"] = overlay
    env["DSV41_SOURCE"] = overlay
    print(f"launcher: {checkpoint} ships no {TEMPLATE_NAME}; serving {overlay} "
          f"({TEMPLATE_NAME} from the mod dir)", flush=True)


def resolve_checkpoint(env: dict[str, str]) -> None:
    """Set MODEL_PATH / DSV41_SOURCE for the checkpoint to serve.

    Runs before any checkpoint validation. Three shapes are accepted, in order:

    1. A caller-supplied ``MODEL_PATH`` that is a checkpoint dir (a container
       bind that is not the HF hub cache -- read-only, but boot.py's
       SKIP_PREPARE only needs it to exist). Left as supplied.
    2. ``MODEL_ID`` itself already a checkpoint dir. This is the prepared-model
       path sparkrun renders for ``{model}`` whenever the recipe carries a
       ``command:`` template (``models/runtime.py:bind_runtime_models`` sets
       ``overrides["model"] = <snapshot path>``), so on a *launch* -- unlike a
       dry run -- the repo id never arrives; the on-disk path does. Without
       this branch MODEL_PATH stays unset and boot.py dies on
       ``missing /models/<name>/config.json`` (the 2026-10-09 field failure).
    3. ``MODEL_ID`` a repo id, located in the fixed in-container HF cache
       (``refs/main``, else the newest complete snapshot). Keeps the dry-run /
       manual-invocation form working and the recipe free of a snapshot hash.

    Whichever shape resolved, a checkpoint that ships no ``chat_template.jinja``
    is served through the overlay farm (``ensure_template_overlay``: a symlink
    farm of the checkpoint whose one real file is this mod's template), because the
    engine would otherwise advertise a templateless chat endpoint.
    """
    model = env.get("MODEL_ID", "").strip()
    supplied = env.get("MODEL_PATH", "").strip()
    if _is_checkpoint_dir(supplied):
        env.setdefault("DSV41_SOURCE", supplied)
    elif _is_checkpoint_dir(model):
        print(f"launcher: MODEL_ID is an on-disk checkpoint dir; serving {model}", flush=True)
        env["MODEL_PATH"] = model
        env["DSV41_SOURCE"] = model
    elif model:
        resolved = _resolved_models_dir(model)
        if resolved:
            print(f"launcher: resolved checkpoint {model} -> {resolved}", flush=True)
            env["MODEL_PATH"] = resolved
            env["DSV41_SOURCE"] = resolved
        else:
            print(f"launcher: checkpoint for {model} not found under {HF_HUB}; "
                  "leaving MODEL_PATH unset", flush=True)
    if _is_checkpoint_dir(env.get("MODEL_PATH", "")):
        ensure_template_overlay(env, env["MODEL_PATH"])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--boot", action="store_true", help="start the engine (default)")
    parser.add_argument("--health", action="store_true", help="run boot.py health probe")
    parser.add_argument("--dist-init-addr", default=None)
    parser.add_argument("--nnodes", default=None)
    parser.add_argument("--node-rank", default=None)
    parser.add_argument("--port", default=None)
    parser.add_argument("--tp", default=None,
                        help="TP degree (sparkrun's {tensor_parallel}); mapped to "
                             "boot.py's TP_SIZE")
    parser.add_argument("--context-length", default=None,
                        help="served context length (sparkrun's {max_model_len}); "
                             "mapped to boot.py's CONTEXT_LENGTH")
    parser.add_argument("--dspark-block-size", default=None,
                        help="DSpark verify window gamma (sparkrun's {dspark_block_size}); "
                             "mapped to boot.py's DSPARK_BLOCK_SIZE")
    parser.add_argument("--fp8-gemm-backend", default=None,
                        help="dense FP8 GEMM backend for boot.py's EXTRA_SGLANG_ARGS "
                             "(MAPPED to FP8_GEMM_BACKEND). boot.py re-stamps the last "
                             "--fp8-gemm-backend itself, so this declares the value "
                             "instead of racing it")
    parser.add_argument("--served-model-name", default=None)
    parser.add_argument("--model-path", default=None)
    parser.add_argument("--model", default=None,
                        help="HF repo id (sparkrun's {model}); the checkpoint is "
                             "located in the fixed HF hub cache from this")
    # Everything else (unused sglang flags, the recipe's own args) is ignored.
    args, _unknown = parser.parse_known_args(argv)

    env = dict(os.environ)
    if args.dist_init_addr:
        env["DIST_INIT_ADDR"] = args.dist_init_addr
    if args.nnodes:
        env["NNODES"] = args.nnodes
    if args.node_rank is not None:
        env["NODE_RANK"] = args.node_rank
    if args.port:
        env["SERVER_PORT"] = args.port
    if args.tp:
        # boot.py reads TP_SIZE from the env; the recipe passes the TP degree as
        # `--tp {tensor_parallel}` (sparkrun renders the template but does NOT
        # emit --tp-size when one is present, so this mapping is load-bearing --
        # without it boot.py would fall back to its default TP=3).
        env["TP_SIZE"] = args.tp
    if args.served_model_name:
        # sparkrun renders `{served-model-name}` (== {model}) as the prepared
        # on-disk snapshot path too; serve under the repo id, not a path.
        env["SERVED_MODEL_NAME"] = _clean_served_name(args.served_model_name)
    if args.model_path:
        env["MODEL_PATH"] = args.model_path
    if args.model:
        env["MODEL_ID"] = args.model

    if not os.path.isfile(BOOT):
        print(f"launcher: boot.py not found at {BOOT}; is the image dsv41-4x-spark:canary-roce?", file=sys.stderr)
        return 2

    # Fill the production env (locations, engine flags, adapter enablement,
    # RoCEnante, NCCL tuning). The launcher owns these and overrides the image.
    apply_recipe_env(env)

    # `--context-length {max_model_len}` is the recipe's context knob. boot.py
    # builds the whole `sglang.launch_server` argv from the environment and
    # refuses CONTEXT_LENGTH outside 4096..1048576, so an unparsed flag would
    # leave the launcher's default in place and the server would advertise the
    # wrong context. Applied AFTER apply_recipe_env so the recipe's value wins
    # over the launcher's own default (e.g. `-o max_model_len=…`).
    if args.context_length is not None:
        env["CONTEXT_LENGTH"] = args.context_length

    # Same reasoning for the DSpark verify window: the recipe's
    # `--dspark-block-size {dspark_block_size}` must win over the launcher's
    # shipped 5, or `-o dspark_block_size=3` would be silently clobbered.
    if args.dspark_block_size is not None:
        env["DSPARK_BLOCK_SIZE"] = str(args.dspark_block_size)

    # The dense FP8 GEMM backend is the ONE serve flag the recipe has to declare
    # itself: boot.py's required_sglang_args() re-stamps it (see the RECIPE_ENV
    # note by the v2.4 flags), so a launch cannot override it and there is no
    # launcher default either -- the recipe is the single declaration.
    if args.fp8_gemm_backend:
        env["FP8_GEMM_BACKEND"] = args.fp8_gemm_backend

    # Assemble boot.py's EXTRA_SGLANG_ARGS once every source has been applied
    # (RECIPE_ENV defaults, then a launch's `-o env.KEY=` override on top).
    env["EXTRA_SGLANG_ARGS"] = extra_sglang_args(env)

    # Locate the checkpoint in the fixed HF cache (MODEL_ID from `{model}`).
    # After apply_recipe_env, which is where /cache/runtime paths are set.
    resolve_checkpoint(env)

    if args.health:
        os.execve(sys.executable, [sys.executable, BOOT, "health"], env)

    rank = env.get("NODE_RANK")
    ensure_engram_shards(env, int(rank) if rank is not None and str(rank).lstrip("-").isdigit() else None)

    # Belt-and-suspenders for the image's baked HEALTHCHECK: persist the served
    # port to the fixed path boot.py's dynamic health probe reads. The healthcheck
    # runs from the container's *creation* env, so it cannot see SERVER_PORT that
    # this launcher sets in-process -- but it CAN read this file. The path is a
    # literal (not $STATE_PATH) because the image bakes STATE_PATH=/state while the
    # launcher relocates it under /cache/runtime; the health probe only needs a
    # fixed rendezvous. boot.py's own --port/cmdline/proc-net discovery would also
    # find the port; this just makes the answer deterministic from the first probe.
    if env.get("SERVER_PORT"):
        try:
            with open(HEALTH_PORT_FILE, "w") as handle:
                handle.write(str(env["SERVER_PORT"]) + "\n")
        except OSError as exc:
            print(f"launcher: could not write {HEALTH_PORT_FILE} ({exc!r}); "
                  "health probe will discover the port from the process", flush=True)

    # The receipt line. It prints the memory knobs and the extras because those
    # are the values only a boot can confirm: the engine's own
    # `DSV4 memory calculation: ... full_token=` line then says whether the
    # MAX_TOTAL_TOKENS pin fits under the budget or was clamped.
    print(
        "launcher: boot.py run "
        f"NNODES={env.get('NNODES')} NODE_RANK={env.get('NODE_RANK')} "
        f"DIST_INIT_ADDR={env.get('DIST_INIT_ADDR')} TP={env.get('TP_SIZE')} "
        f"EP={env.get('EP_SIZE')} PORT={env.get('SERVER_PORT')} "
        f"CONTEXT={env.get('CONTEXT_LENGTH')} "
        f"DSPARK_BLOCK_SIZE={env.get('DSPARK_BLOCK_SIZE')} "
        f"MEM_FRACTION_STATIC={env.get('MEM_FRACTION_STATIC')} "
        f"CHUNKED_PREFILL_SIZE={env.get('CHUNKED_PREFILL_SIZE')} "
        f"MAX_TOTAL_TOKENS={env.get('MAX_TOTAL_TOKENS')} "
        f"MAX_RUNNING_REQUESTS={env.get('MAX_RUNNING_REQUESTS')} "
        f"EXTRA_SGLANG_ARGS={env.get('EXTRA_SGLANG_ARGS')!r}",
        flush=True,
    )
    os.execve(sys.executable, [sys.executable, "-u", BOOT, "run"], env)
    return 1  # unreachable


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
