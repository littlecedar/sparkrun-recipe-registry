# IFM K2-Horizon (IFM) — serving recipes

The IFM `K2-Horizon` family on NVIDIA DGX Spark (GB10, sm_121), served with native
SGLang. Two recipes ship: the dense `0.9B` (BF16) and the dense `7B-FP8` served with
UNO speculative decoding against the `7B-Uno` conditional-LoRA diffusion draft.

This file is the shipped-recipe summary. Lane state, constraints, guards, measurement
histories and the archived material live in [`attic/ifm/`](../../attic/ifm/ARMS-MANIFEST.md),
indexed below. The deep research record (`K2-*-MODEL-OPTIMIZATION-WORK.md` /
`K2-*-JOURNAL.md`) is git-ignored by design and absent from a fresh checkout.

## Contents

- [Checkpoints](#checkpoints)
- [k2-horizon-0.9b-bf16-sglang](#k2-horizon-09b-bf16-sglang)
- [k2-horizon-0.9b-bf16-uno-sglang](#k2-horizon-09b-bf16-uno-sglang)
- [k2-horizon-7b-fp8-uno-sglang](#k2-horizon-7b-fp8-uno-sglang)
- [Container](#container)
- [Engine bump to SGLang 0.5.22 (executed 2026-10-22 — all three arms validated)](#engine-bump-to-sglang-0522-executed-2026-10-22--all-three-arms-validated)
- [Attic index](#attic-index)

## Checkpoints

| Model | repo | size | quant | notes |
|---|---|---|---|---|
| 0.9B | `IFM/K2-Horizon-0.9B` | 2.16 GB | BF16 | dense, 28 layers, 56 KiB KV/token |
| 7B | `IFM/K2-Horizon-7B-FP8` | 11.05 GB | block-FP8 (compressed-tensors) | dense, 36 layers, 144 KiB KV/token |
| 7B-Uno | `IFM/K2-Horizon-7B-Uno` | 1.40 GB adapter | — | conditional-LoRA diffusion draft for the 7B |
| 0.9B-Uno | `IFM/K2-Horizon-0.9B-Uno` | 223,917,616 B adapter | — | conditional-LoRA diffusion draft for the 0.9B (`sha256 5a499229…`, r=128 / alpha 2048, 7 target modules) |

The two models declare **different context**: the 0.9B's `max_position_embeddings` is
**131072** (YaRN 16 x 8192 — its hard ceiling), while the 7B's is **524288** (plain
rope); the 7B was measured serving a **176,045-token** prompt at the 512K configuration
(bench `bench_6518bc429d05`). Both checkpoints are **Apache-2.0**.

## `k2-horizon-0.9b-bf16-sglang`

Dense 0.9B (body 0.98B + 98.7M lm_head, `model_params: 1.08B`), single node, **TP=1**,
131072-token context (the model's hard YaRN ceiling), no mods.

- **repo id** `IFM/K2-Horizon-0.9B`, SHA-pinned at `383cb66347be…`.
- **flags** `--attention-backend flashinfer`, `--dtype bfloat16` (spelled, not `auto` —
  the config declares `float32`), `--kv-cache-dtype auto`, `--chunked-prefill-size 4096`.
- **memory** weights 2.16 GB; `gpu_memory_utilization: 0.85`, `max_num_seqs: 64`
  (a CPU/scheduler limit, not a memory one — a full 131k sequence is ~7.0 GiB and the
  pool spans ~14 of them).
- **tuning** `gpu_memory_utilization` is overridable (`-o gpu_memory_utilization=0.30`): the
  engine floors near `f=0.10`, so several 0.9B engines fit on one box, and
  `extra_args: "--max-total-tokens 262144"` pins a deterministic 2×131k (14 GiB) pool.
  `chunked_prefill_size` is *not* in sparkrun's `_SGLANG_FLAG_MAP`, so it reaches sglang only
  through the placeholder — `-o chunked_prefill_size=…` prints "unmapped" while still taking
  effect. `extra_args` is appended last so argparse resolves a repeated flag in favour of the
  override; `--cuda-graph-max-bs` does not exist at v0.5.20 (use the `-decode`/`-prefill`
  spellings). `--kv-cache-dtype fp8_e4m3` is legal and would halve KV to 28 KiB/token, but its
  accuracy gate is unmet — treat fp8 KV as an arm whose gate is accuracy, not throughput.
- **measured** 77.6 / 67.3 t/s single-stream (d0 / d8192, `benchmarking/decode-triage.yaml`).

**Concurrency ladder, 2026-10-15 (one node, `benchmarking/concurrency-ladder.yaml` — d0, pp 2048 /
tg 128, 5 runs per cell, decode-phase rows only; bench `bench_edd4029e004f`, receipt
`~/benchmarks/ifm-09b-ladder-20261015/`).** Aggregate decode **C1 80.4 · C2 181.6 · C5 317.6 ·
C10 503.9 t/s** (σ 0.2 / 0.6 / 31.6 / 0.9) — **6.3× single-stream at c10** — with per-request
decode 80.4 / 93.1 / 70.3 / 59.4 t/s and ttfr 86 / 122 / 285 / 453 ms. C1 re-measures 3.6 % above
the 77.6 recorded above; same profile shape, one boot, inside the inter-boot spread (the profile's
own noise floor is 7–25 %), so the headline stands. The **c5 cell is bimodal on this boot**
(273.8 / 284.6 vs 342.8 / 343.6 / 343.4) and that spread *is* its σ; c1/c2/c10 repeat to ≤ 0.6 %.
Boot grants from the serve log: `max_running_requests=64` (= `max_num_seqs`, **not** clamped —
this arm allocates **no mamba pool**, so there is no state-pool ceiling to clamp it),
`max_total_num_tokens=1773893` of **bf16** KV (47.37 GB K + 47.37 GB V), `available_gpu_mem=12.12 GB`,
weights 2.22 GB loaded in 13.2 s, TTR 82.7 s port / 90.1 s HTTP. Do **not** pool these cells with the
`concurrency-sweep` columns in [`NOTES.md`](../../attic/ifm/NOTES.md): that profile is tg=256 at
c=1/4/8, this one tg=128 at c=1/2/5/10.

## `k2-horizon-0.9b-bf16-uno-sglang`

The 0.9B arm plus the `K2-Horizon-0.9B-Uno` conditional-LoRA diffusion draft: single node, **TP=1**
(the same hard requirement the 7B UNO arm has), 131,072-token window, native SGLang UNO in the linear
form (topk 1, draft width 8). **Boot-verified and measured 2026-10-18**, receipt
`~/benchmarks/ifm-09b-uno-20261018/`.

- **Adapter identity, proved on disk:** `IFM/K2-Horizon-0.9B-Uno` @ `cbb5d835…` staged by
  [`mods/provide-uno-lora-k2-horizon-0.9b`](mods/provide-uno-lora-k2-horizon-0.9b) at
  `/cache/runtime/uno-lora/K2-Horizon-0.9B-Uno` — **223,917,616 B**, `sha256 5a499229…`, r=128 /
  alpha 2048 (scaling 16), 7 target modules. The engine logs `Using uno_cublas as backend of LoRA
  kernels`, `loaded weights for target modules ['down_proj', 'gate_up_proj', 'o_proj', 'qkv_proj']`,
  and a verify graph with `num_tokens_per_req=8`; acceptance is nowhere near 1.0, so this is a UNO
  result and not a silently-plain serve. [`mods/probe-uno-fa4-sm121`](mods/probe-uno-fa4-sm121)
  relaxes UNO's fa3-only gate (device capability `(12,1)`).
- **Boot:** HTTP-ready **102.75 s** from container start; `max_total_num_tokens=1695086` of **bf16**
  KV, `max_running_requests=64` (unclamped), `mem_fraction_static=0.82`, context 131072.
- **Measured (one boot):** C1 **123.2 ± 13.2** @ d0 / **90.5 ± 3.6** @ d8192
  (`bench_a42c59ba1ec8`) at acceptance length **2.75 / 2.64** — every cell 0.6–0.7 tokens/step above
  the ~2.07 break-even for width 8 / topk 1; ladder **118.5 · 205.2 · 388.4 · 534.3 t/s**
  (`bench_ddb8a41a69d3`, acceptance 2.65 / 2.70 / 2.80 / 2.73). Against a **same-node plain + fa4
  control** (79.0 / 68.0 at C1; 78.6 · 178.8 · 343.3 · 500.1 on the ladder) that is **1.56× / 1.33×**
  at C1 and 1.15× / 1.13× / 1.07× up the ladder. fa4-vs-flashinfer is a wash on the plain model
  (79.0 vs the recorded 80.4 base), so the gain is UNO's, not the backend's. Depth 8192 costs almost
  no acceptance (2.75 → 2.64) while costing 27 % of throughput — the depth cost is per-step KV work,
  not drafted-token quality.
- **Accuracy:** house **33/37**, GSM8K **173/200**, ARC-Challenge **144/200**, against the recorded
  base's 31/37 · 174/200 · 133/200. House and GSM8K are inside the lane's ±3-item ≈ 1 SE protocol.
  **ARC is +11 items (≈1.8 SE) in UNO's favour and is NOT claimed as an improvement:** it was taken
  with four *more* truncations than the base (so it is not truncation inflation), and the most likely
  mechanism is that a speculative verify batch changes the target forward's batch shape and flips
  near-tie argmaxes. **Open item —** settling it needs an item-level diff against a same-window
  plain-fa4 control on ARC, which was not taken. What *is* established: no accuracy loss on any of
  the three instruments.
- **Dispersion:** UNO's c1 run-to-run spread is ±10–13 t/s against the plain arm's ±0.3, so read C1 as
  a boot-level number (123.2 in the dedicated profile, 118.5 in the ladder), not a 0.1 %-resolved one.
- The recipe's `metadata.caveats` record the same measured state as this section — one boot, C1
  against the fa4 control, ARC not claimed (corrected 2026-10-19 from the stale "Unmeasured arm").

## `k2-horizon-7b-fp8-uno-sglang`

Dense 7B-FP8 (`model_params: 9.0B` = base + 0.35B adapter), single node, **TP=1** (a
hard requirement — UNO raises `"UNO requires TP=PP=1."`), native SGLang UNO speculative
decoding (the 7B target plus the `K2-Horizon-7B-Uno` conditional-LoRA diffusion draft),
verified by the target, so it is lossless by construction.

- **repo id** `IFM/K2-Horizon-7B-FP8`, SHA-pinned at `ea739ec816e0…`; the UNO adapter is
  a **second artifact** (`IFM/K2-Horizon-7B-Uno` @ `669f041a…`, `model:` cannot carry it).
- **flags** `--attention-backend fa4`, `--fp8-gemm-backend cutlass`, `--page-size 1`,
  `--kv-cache-dtype auto`, `--chunked-prefill-size 4096`; speculative: `--speculative-algorithm UNO`,
  `--speculative-eagle-topk 1` (linear), `--speculative-num-draft-tokens 8` (draft width F).
- **memory** `gpu_memory_utilization: 0.82` (headroom for the resident target+draft LoRA
  slots and the `[batch, F, 250624]` draft/verify logits); `max_num_seqs: 32`.
- **tuning** `gpu_memory_utilization: 0.82` is deliberate — **do not raise it to 0.85** on the
  theory that "UNO needs it": linear UNO builds no second attention backend and captures no
  second CUDA-graph pool, so the three points of headroom cover only the resident target+draft
  LoRA slots and the `[batch, F, 250624]` draft/verify logits. `page_size: 1` is deliberate too:
  nothing forces 128 on GB10 (`_fa4_page_constraint` gates on `is_sm100`) and page_size 1 never
  reaches the EAGLE topk>1 page-tree cascade. `chunked_prefill_size` stays modest because UNO
  force-disables mixed chunked prefill, so a large chunk would compete with the draft workspace
  for the same pool.
- **speculative** `--speculative-num-draft-tokens` is **mandatory** (a positive integer —
  `_handle_uno` raises otherwise) and doubles as the linear draft width F; `--speculative-eagle-topk 1`
  selects linear over tree (tree adds Q≥F, Q≤128, Q·K≤2048, exact-1.0 accept thresholds, no
  PDMux, no two-batch overlap, and a second CUDA-graph backend — all avoidable and unmeasured here).
- **FP8 base is deliberate** the Uno adapter's own `adapter_config.json` declares the BF16 base
  `IFM/K2-Horizon-7B`, so the vendor-validated pairing is BF16+Uno; on a bandwidth-bound box the
  base read dominates, so the FP8+Uno pairing is itself part of what this arm validates.
- **measured** 32.4 / 27.1 t/s single-stream (d0 / d8192) — the fastest arm in the lane,
  +52 % / +41 % over the plain 7B; 145.5 / 90.2 aggregate at c=8.

**Concurrency ladder, 2026-10-15 (one node, `benchmarking/concurrency-ladder.yaml` — d0, pp 2048 /
tg 128, 5 runs per cell, decode-phase rows only; bench `bench_679cd870a74a`, receipt
`~/benchmarks/ifm-7b-ladder-20261015/`).** Aggregate decode **C1 31.3 · C2 56.1 · C5 94.0 ·
C10 126.0 t/s** (σ 1.4 / 2.6 / 1.3 / 1.2) — still climbing at the top of the ladder, **4.0×
its same-boot single-stream at c10** — with per-request decode 31.3 / 28.8 / 22.4 / 17.2 t/s and ttfr 492 / 989 /
1582 / 2739 ms. C1 re-measures 3.4 % below the 32.4 recorded above (same profile shape, one boot,
inside the 7–25 % inter-boot spread). **UNO is engaged on this boot**: serve-log `accept len` mean
**2.95** (25 samples, min 2.62, max 3.27 — every sample > 1); that is a *narrower window* than the
838-sample mean 4.15 the 2026-10-14 re-pin recorded (this one covers only the ladder's 128-token
generations), so read the two as two windows, not a trend. Boot grants from the serve log:
`max_running_requests=32` (= `max_num_seqs`, **not** clamped — the arm allocates **no mamba pool**),
`max_total_num_tokens=577994` of **bf16** KV (39.69 GB K + 39.69 GB V), `available_gpu_mem=15.93 GB`,
weights 10.66 GB loaded in 69.1 s, TTR 250.8 s port / 255.7 s HTTP. Do **not** pool these cells with
the `concurrency-sweep` figures above (tg=256 at c=1/4/8) or with the retired 7B arms' rows in
[`NOTES.md`](../../attic/ifm/NOTES.md) — only the same profile is comparable.

**`kv_cache_dtype: fp8_e4m3` accuracy gate — passes, on `triton` only (2026-10-18).** The shipped `fa4`
backend cannot carry an fp8 KV cache: the override allocated the pool (`dtype: torch.float8_e4m3fn`,
1,150,989 tokens) and then died in warmup on `AssertionError: q.dtype torch.bfloat16 != k.dtype
torch.float8_e4m3fn` (`flashattention_backend.py:1553`, `present[a].dtype == present[b].dtype`) — a
kernel dtype constraint, not a flag typo, because the arm serves bf16 queries. The sanctioned route is
the one `probe-uno-fa4-sm121` admits and the recipe comment names: `-o attention_backend=triton -o
kv_cache_dtype=fp8_e4m3` (1,151,086 tokens, `max_running_requests=32` unclamped). Accuracy: house
**36/37**, GSM8K **188/200** (94.0 %), ARC-Challenge **179/200** (89.5 %) — 0 / 0 / +1 items against the
documented plain-7B bf16-KV baseline (36/37 · 188/200 · 178/200), and no truncation inflation against a
bf16-KV control on the same triton backend in the same window: 22 vs 19 `finish_reason: length` of 400,
discordant pairs near-symmetric (GSM8K 7 fp8-only / 7 control-only over 5 shared misses; ARC 10 / 6 over
15), and 21 of the 22 are empty replies whose think block spent the 1024/2048-token budget — an item
property, not a KV-precision one. **No throughput is claimed for this leg**: a triton number is not a
peer of the fa4 figures above, and the shipped recipe stays `fa4` + bf16 KV. Receipts
`~/benchmarks/sweep2-20261018/` (`ifm-7b-fp8kv/`, `ifm-7b-ctl/`, `ifm-7b-fp8kv-{fa4,triton}-serve.log`).

**Standard suite on the shipped `fa4`/bf16 line — all five legs `ok` (2026-10-19).** Contract
`max_model_len=131072`, ready, `finish=stop`; house **36/37** (easy 19/19, hard 17/18); needle
**3/3 at 32,768 and 3/3 at 131,072**; hard ARC-Challenge **181/200 (90.5 %)** and GSM8K **189/200
(94.5 %)**; tools **1079/1239 (87.1 %, 1 transport error)** — the BFCL leg alone took **6,555 s of its 7,200 s
per-check cap** (91 %), the whole suite 9,805 s. Against the fp8-KV override's
36/37 · 188/200 · 179/200 the shipped line is +0 / +1 / +2 items, i.e. the triton+fp8 route cost no
accuracy and the bf16 line needs no trade — the shipped configuration is the one measured here.
Receipt `~/benchmarks/ifm-7b-uno-shipped-20261019/` (`summary.json`, per-check JSON, `bfcl.json`).

**The two mods the UNO arm needs — and why.** The recipe mounts
`recipes/ifm/mods/provide-uno-lora-k2-horizon-7b` and `recipes/ifm/mods/probe-uno-fa4-sm121` (bare `mods/NAME`
form, in that order — the provide mod lands the adapter on disk before the server starts,
and both run before sglang reads `--uno-lora-path`):

1. `provide-uno-lora-k2-horizon-7b` — fetches the draft adapter at a fixed container path.
   The adapter is a **second artifact**: it is not a `model:`, and sparkrun's model sync
   only fetches `model:`, so the mod is the only way to land it.
2. `probe-uno-fa4-sm121` — relaxes UNO's literal `("fa3","fa3")` gate to also accept
   `("fa4","fa4")`. GB10 `(12,1)` cannot construct `fa3` (`create_flashattention_v3_backend`
   asserts major in {8,9}); without the mod the recipe fails at argument validation with
   `"UNO requires FA3 …"` (intended stock behaviour). The fa4 kernels run on this chip.

**UNO tree mode is measured-rejected (2026-10-19).** A probe arm with `--speculative-eagle-topk 2`,
`--speculative-num-steps 3` (draft width F=4) and `--speculative-num-draft-tokens 6` (verify width Q)
booted cleanly on `.34` — the constraints are a system, not a flag: Q >= F, Q <= 128, Q*K <= 2048,
`1+K+K^2+...` >= Q, and Q-1 <= K*(F-2)+1 in EAGLE's parent-list ABI, with PDMux, two-batch overlap
and non-1.0 accept thresholds refused. In a same-window paired screen it lost **12.4 % at C1**,
5.2 % at C2 and 3.1 % at C5 (equal at C10), accepted less (2.878 vs 3.058 mean accept length) and
allocated a second CUDA graph (0.61 GB), so the shipped linear arm stands. Probe archived at
`attic/ifm/arms/zz-k2-horizon-7b-uno-tree-sglang.yaml`; receipt
`~/benchmarks/ifm-uno-tree-20261019/`.

**`max_num_seqs` note.** `max_num_seqs: 32` is **load-bearing** on this arm — it is a
scheduler *admission* limit, not a memory limit. At 8 the arm flatlines at c=8 (97.5
aggregate, below its own c=4 of 98.6); at 32 it scales to 145.5, the best c8 figure in
the lane. Do not lower it — `tests/test_k2_7b_recipes.UnoConcurrencyCap` enforces a floor.

## Container

All recipes pin the container to `lmsysorg/sglang:v0.5.22-cu130` by **digest**
(`sha256:e3a4f06001a29542fc4a8638536d9ffc5eb9c9942b08603c09b19a56eae4a1ae` — the **published**
multi-arch index digest, which `docker buildx imagetools inspect` prints and `docker images` never
will: that shows a config digest), bumped from `v0.5.20-cu130@06e4f2ed…` on 2026-10-22 —
§"Engine bump to SGLang 0.5.22". `v0.5.22-cu130` and `v0.5.22` are the same index digest, so the
`-cu130` spelling is cosmetic and kept for lane continuity. v0.5.20 remains the **version floor**, and
it is a floor no longer equal to the pin: it is the first release that ships `models/xllm.py`, which
registers `K2HorizonForCausalLM`, and `tests/test_k2_7b_recipes.ContainerPin` now parses the version
and asserts `>= v0.5.20` rather than matching that literal tag. A moving `dev-*` tag is not a guarantee.

## Engine bump to SGLang 0.5.22 (executed 2026-10-22 — all three arms validated)

**Status: validated on the new digest; the pins are applied.** One serve per arm, sequential on `.35`,
each boot log's `Image:` line naming `v0.5.22-cu130@sha256:e3a4f060…` and the engine reporting
`sglang: 0.5.22` / torch `2.14.1+cu130` (was `2.13.0+cu130`). Receipts
`~/benchmarks/sglang-0522-20261022/{arm-d-09b,arm-e-09b-uno,arm-f-7b-uno}/`; evidence history in
[`attic/ifm/AGENTS.md`](../../attic/ifm/AGENTS.md) §"Engine-bump adjudication — 0.5.20 → 0.5.22".

This is the lane's **first engine bump**, so it is also the first test of the assumption the UNO arms
were built on: that `mods/probe-uno-fa4-sm121`'s anchored patch still applies to a newer
`arg_groups/speculative_hook.py`. It does — the mod's own probe logged
`PROBE UNO fa3 gate anchor  OK  anchor count = 1` and the arms booted `--attention-backend fa4` with
`--speculative-algorithm UNO`, which stock 0.5.22 refuses at argument validation
(`"UNO requires FA3 …"`). A patch that no longer applied would have failed the launch closed; nothing
was worked around.

| arm | boot / grant (0.5.20 on file) | house (on-file bar) | verdict |
|---|---|---|---|
| `k2-horizon-0.9b-bf16-sglang` | HTTP-ready **94 s** (82.7 port / 90.1 HTTP); `max_total_num_tokens=1,764,610` (1,773,893), `max_running_requests=64`, 12.24 GB free | **32/37** — easy 17/19 (`fmt-2`, `needle-1`), hard 15/18 (`hard-rev`, `trick-1`, `trick-2`) vs the recorded 17/19 + 15/18 with the **same five items** | keep |
| `k2-horizon-0.9b-bf16-uno-sglang` | HTTP-ready **94 s** (102.75); `max_total_num_tokens=1,690,881` (1,695,086), `max_running_requests=64`, 16.30 GB free | **33/37** — easy 18/19 (`needle-1`), hard 15/18 (same three) == the recorded **33/37** | keep |
| `k2-horizon-7b-fp8-uno-sglang` | HTTP-ready **240 s** (250.8 port / 255.7 HTTP); `max_total_num_tokens=574,698` (577,994), `max_running_requests=32`, 15.38 GB free | **36/37** — easy 19/19, hard 17/18 (`hard-rev`) == the recorded **36/37** | keep |

**About the 37/37 bar.** The house battery's ceiling is per model, not per lane: the Ornith arms score
37/37 on it, and the IFM arms have never — their on-file bars are 32/37 / 33/37 / 36/37, with the same
miss lists reproduced here item for item. A 37/37 requirement applied to this lane would have failed
every arm on its own baseline, so the gate used is **no regression against the arm's recorded score and
misses**, which all three meet.

**Engine-log delta vs the 0.5.20 boots: none** — `WARNING`/`ERROR`/`Traceback` count is 0 in all three
serve logs, and 0 in the FA4 mod log apart from the probe notes.

**Ops notes.** Boot by recipe file path, never `@littlecedar/<name>` (the registry ref resolves the
published copy and silently serves the previous pin — root `AGENTS.md` §"Development Commands"); a
`docker pull …@sha256:…` leaves the image untagged and prune-able, so re-tag it; and re-verify the
`container:` line on the node immediately before each boot, because a peer's checkout of the shared
tree can revert an uncommitted pin.

## Attic index

Everything that is not a shipped recipe lives under [`attic/ifm/`](../../attic/ifm/):

| file / dir | what it holds — and the question it answers |
|---|---|
| [`ARMS-MANIFEST.md`](../../attic/ifm/ARMS-MANIFEST.md) | The manifest of the archived material: Wave 1 (the withdrawn `MoVA-36B-A4B` sub-lane) and Wave 2 (the two retired 7B spec arms), each with a row and its measured numbers. *What moved out of the lane, and why?* |
| [`AGENTS.md`](../../attic/ifm/AGENTS.md) | The lane guide (§1–§9): state, evidence locations, hard constraints, falsified claims, guards, validation ritual, sprawl policy, traps, and the recipe research record. *Where does a constraint or a `§N` citation resolve?* |
| [`NOTES.md`](../../attic/ifm/NOTES.md) | The dated working record: the 2026-10-08 first hardware run, the 2026-10-09 instrument repair / accuracy re-measure / arm sweeps / UNO campaign, and the 2026-10-14 re-pin. *What happened, when, with which numbers?* |
| `K2-36B-A4B-JOURNAL.md` | The withdrawn 36B sub-lane's dated narrative (git-ignored by design; on disk only). *How did the 36B sub-lane go, week by week?* |
| `K2-36B-A4B-MODEL-OPTIMIZATION-WORK.md` | The withdrawn 36B sub-lane's model/roofline/byte math (git-ignored by design; on disk only). *What is the 36B model, and what were its ceilings?* |
| `test_ifm_36b_recipes.py` | The 36B sub-lane's guard suite (invariants I1–I17); no longer auto-discovered by `unittest discover -s tests`. *What invariants governed the archived 36B arms?* |
| `k2_36b_arith.py` | The exact byte census + roofline arithmetic the 36B arms' prose quotes; imported by the guard above. *How were the 36B byte/roofline figures derived?* |
| `arms/` | The archived recipe YAMLs: the four 36B arms (`k2-horizon-36b-a4b-{fp8-tp1,fp8-tp2,bf16-tp1}-sglang.yaml`, `zz-k2-36b-a4b-fp8-unpatched-probe-sglang.yaml`) and the two retired 7B arms (`k2-horizon-7b-fp8-sglang.yaml`, `k2-horizon-7b-fp8-ngram-sglang.yaml`). *What did the archived arms actually contain?* |
| `mods/` | The two archived mods: `patch-sglang-k2-horizon-fp8/` (relaxes SGLang's native-K2-Horizon quant gates; serves only the withdrawn FP8 checkpoint) and `make-roce-env/` (renders NCCL/RoCE env for legacy runners; served the withdrawn TP=2 arm). *Which mods no longer mount in a shipped recipe?* |

See [`ARMS-MANIFEST.md`](../../attic/ifm/ARMS-MANIFEST.md) for the per-file manifest rows
and the provenance behind each archive decision.
