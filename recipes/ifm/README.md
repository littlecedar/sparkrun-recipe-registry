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
- [`k2-horizon-0.9b-bf16-sglang`](#k2-horizon-09b-bf16-sglang)
- [`k2-horizon-7b-fp8-uno-sglang`](#k2-horizon-7b-fp8-uno-sglang)
- [Container](#container)
- [Attic index](#attic-index)

## Checkpoints

| Model | repo | size | quant | notes |
|---|---|---|---|---|
| 0.9B | `IFM/K2-Horizon-0.9B` | 2.16 GB | BF16 | dense, 28 layers, 56 KiB KV/token |
| 7B | `IFM/K2-Horizon-7B-FP8` | 11.05 GB | block-FP8 (compressed-tensors) | dense, 36 layers, 144 KiB KV/token |
| 7B-Uno | `IFM/K2-Horizon-7B-Uno` | 1.40 GB adapter | — | conditional-LoRA diffusion draft for the 7B |

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

**`max_num_seqs` note.** `max_num_seqs: 32` is **load-bearing** on this arm — it is a
scheduler *admission* limit, not a memory limit. At 8 the arm flatlines at c=8 (97.5
aggregate, below its own c=4 of 98.6); at 32 it scales to 145.5, the best c8 figure in
the lane. Do not lower it — `tests/test_k2_7b_recipes.UnoConcurrencyCap` enforces a floor.

## Container

All recipes pin the container to `lmsysorg/sglang:v0.5.20-cu130` by **digest**
(`sha256:06e4f2ed21afde4ff513cda65070124e727ba23ccaeff7712b8c40e1097d611f`). v0.5.20 is
the version floor: it is the first release that ships `models/xllm.py`, which registers
`K2HorizonForCausalLM`. A moving `dev-*` tag is not a guarantee.

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
