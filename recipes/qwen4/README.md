# Qwen3.8-Flash-Next (`qwen4`) — serving recipes

Serving recipes for **Qwen3.8-Flash-Next**, a 180B MoE with hybrid GDN + full attention and a PLE
n-gram table, on a **two-node DGX Spark (GB10) TP=2 pair** (128 GB unified memory per node, 200 GbE
RoCE). This directory is the `qwen4` model family (`model_symbol: qwen4`).

Two checkpoints are in play; everything shipped here is on the second one:

| checkpoint | role |
|---|---|
| [`RadixArk/Qwen3.8-Flash-Next-NVFP4`](https://huggingface.co/RadixArk/Qwen3.8-Flash-Next-NVFP4) | the **quality reference**; mixed NVFP4/BF16/FP8, vision tower intact |
| [`local-inference-lab/Qwen3.8-Flash-Next-NVFP4`](https://huggingface.co/local-inference-lab/Qwen3.8-Flash-Next-NVFP4) | locally-quantised export, **lower bytes/token** (MXFP8 attention/GDN, FP8 PLE). **Text only** — a required mod drops the quantised vision tower. |

> **This directory runs as a git-distributed artifact.** Read [`AGENTS.md`](AGENTS.md) before editing
> anything here — it is the condensed operating guide (constraints, traps, runbook, validation
> ritual). Long-form evidence is in the lane's research record, now archived at
> [`../../attic/qwen4/QWEN4-MODEL-OPTIMIZATION-WORK.md`](../../attic/qwen4/QWEN4-MODEL-OPTIMIZATION-WORK.md)
> (`§N` cite-target, git-ignored); per-session coordination was in
> [`../../attic/qwen4/COOP.md`](../../attic/qwen4/COOP.md).

---

## The two production TP=2 lanes

The lane's deliverable is **two** recipes off the same checkpoint, each tuned for one serving regime.
They differ from the balanced base recipe in **one or two `defaults` knobs each**, so nothing about
the model, the container, or the mod chain changes between them.

| # | recipe | regime | key knobs | aggregate target |
|---|---|---|---|---|
| **A** | `qwen3.8-flash-next-nvfp4-labquant-highcon-sglang.yaml` | **high concurrency** (throughput) | `max_num_seqs: 32`, `max_mamba_cache_size: 128` | ~88 tok/s at k≈16–24 |
| **B** | `qwen3.8-flash-next-nvfp4-labquant-longctx-sglang.yaml` | **long context** (up to 1M) | `max_model_len: 1000000` + YaRN override | single long sessions |
| — | `qwen3.8-flash-next-nvfp4-labquant-sglang.yaml` | balanced base / **control** | `max_num_seqs: 24`, `max_mamba_cache_size: 112`, ctx 262144 | ~91 tok/s peak at k=16 |

Both lanes inherit the base recipe's 7-mod labquant chain and its two **mandatory** engine flags
(`--moe-runner-backend flashinfer_cutlass`, `--cuda-graph-backend-prefill disabled`). See the recipe
headers; the reasons are in `AGENTS.md` §1.

### Lane A — high concurrency

For many concurrent streams where **aggregate** tokens/s is the metric (batch jobs, agent fan-out,
evals). This is **not** the low-latency config: at the aggregate peak a single request gets roughly a
third of its single-stream rate and waits ~10 s for first token.

Why these two knobs:

- `max_num_seqs` must stay **strictly above** every served `k`. At `k == cap` the running batch
  saturates at `cap − 1` with one request permanently queued and per-request decode loses ~6%.
  Raising it to **32** keeps every served `k ≤ 31` strictly below the flag.
- The **effective admission ceiling is the mamba state pool**, not `max_num_seqs`:
  `run ≤ min(max_num_seqs, max_mamba_cache_size // slots_per_request)` with `slots_per_request = 4`
  on the lazy strategy. Pool 112 → ceiling **28**; pool **128** → ceiling **32**. Raising the pool
  112 → 128 is associated with **~13% more k=24 throughput** (88.35/87.78 vs 78.02 across four
  boots at matched config) — at a `k` where the pool formula says it cannot bind. **The mechanism is
  unestablished**; treat it as a measured association, not a law.
- `chunked_prefill_size` is **kept at 4096**. Raising it to 8192 helps k=24 on the *RadixArk*
  checkpoint but **regresses k=8 (−6.2%) and k=16 (−5.5%) in aggregate on labquant** — the
  checkpoint this lane ships. It does not transfer.

Cost: pool 128 ≈ +850 MB/rank (traded against KV); cap 32 ≈ +0.42 GB intermediate scratch for
−4.55% KV. Boot-verified on the assigned pair (see `../../attic/qwen4/NOTES.md`) — see the header's STATUS note.

### Lane B — long context (up to 1M)

Makes the server **accept and allocate** for a 1 M-token request via `--context-length 1000000` plus
a **YaRN RoPE override** (`--json-model-override-args`, injecting `rope_type: yarn`, `factor 3.815`
= 1 000 000/262 144, `original_max_position_embeddings: 262144`).

> **Read this before trusting any number above ~262144.** The checkpoint declares
> `max_position_embeddings = 262144` with **no** YaRN/NTK config; the override is an
> **extrapolation**, not a trained capability. `partial_rotary_factor: 0.25` (only a quarter of each
> head carries position) makes a quiet failure more likely, and a neighbouring lane's needle test was
> exact at 240k but **failed at 300k**. So the recipe ships the 1 M route, but the **quality-verified
> serving point is `max_model_len: 262144`** — run `-o max_model_len=262144` (and drop the YaRN
> argument) for anything user-facing until a needle gate at 512k/768k/1M **passes**.

This is the lane's honest limit: memory is **not** the gate (a 1 M-token sequence is ~13 GB/rank,
inside the ~23 GB pool), the **trained positional ceiling** is. `bf16` KV is deliberate — `fp8_e4m3`
boots and allocates a bigger pool but then dies in QSA decode (`unsupported SM121 QSA call`; the
SM121 packed-decode path requires BF16 queries). Do not "fix" the KV dtype to buy context.

### Why there is no TP=1 lane

The tasking for this lane named "a TP=1 and TP=2 lane", but **TP=1 is not deliverable for this
checkpoint, on memory, and the one published TP=1 route was closed NO-GO**:

- **Memory.** 180B NVFP4 weights are ~83.8 GB and the KV pool at the 262k trained ceiling is ~24 GB,
  for ~107.8 GB per rank — **infeasible** on a single GB10 (128 GB unified; the lane's
  `gpu_memory_utilization: 0.80` budget is ~96.8 GB, and the kernel/OS need headroom). The base
  RadixArk recipe declares 135 GB; a single Spark cannot hold it.
- **The only TP=1 route was EXL3** ([turboderp 3.05 bpw](https://huggingface.co/turboderp/Qwen3.8-Flash-Next-exl3)),
  a third quant family on a third runtime. Its author-stated and code-enforced topology is **TP=1
  single-Spark**, against this registry's TP=2/4 grid, and its headline tok/s are MTP-inflated — so
  **W2 closed NO-GO** on policy/topology (memo: `.scratch/q4/exl3/W2-EXL3-GO-NO-GO.md`). Its useful
  free result — the `Qwen4Exp QSA requires a BF16 main KV cache` error, and a needle test exact at
  240k / failing at 300k — is folded into Lanes A/B above.

Both production lanes are therefore **TP=2**, as is every other recipe here (the TP=4 arm is
experimental and has never produced a number).

---

## All recipes

**This directory holds only the production recipes and their guides** (`README.md`, `AGENTS.md`,
`../../attic/qwen4/NOTES.md`) — the same convention the `ds4` lane uses:

| recipe | checkpoint | runtime | TP | lane / purpose |
|---|---|---|---|---|
| `qwen3.8-flash-next-nvfp4-labquant-sglang.yaml` | local-inference-lab | sglang | 2 | **balanced base + control** |
| `qwen3.8-flash-next-nvfp4-labquant-highcon-sglang.yaml` | local-inference-lab | sglang | 2 | **Lane A — high concurrency** |
| `qwen3.8-flash-next-nvfp4-labquant-longctx-sglang.yaml` | local-inference-lab | sglang | 2 | **Lane B — long context (1M)** |
| `qwen3.8-flash-next-nvfp4-sglang.yaml` | RadixArk | sglang | 2 | **quality reference** (vision intact) |

Everything else is archived under [`../../attic/qwen4/`](../../attic/qwen4/) and is **not** part of the
production surface:

- **`attic/qwen4/arms/`** — all experiment arms and contributor/alternative recipes that were under
  `recipes/qwen4/` (`zz-*`, the `eugr-` vLLM recipes, `ursuciprian-…-fastqsa…`, the TP=4 arm, the
  cross-runtime `…-vllm` recipe), each with a provenance row in
  [`../../attic/qwen4/ARMS-MANIFEST.md`](../../attic/qwen4/ARMS-MANIFEST.md).
- **`attic/qwen4/`** — the lane's research record (`QWEN4-MODEL-OPTIMIZATION-WORK.md`), journal
  (`JOURNAL.md`), cross-agent ledger (`COOP.md`), and status memos (`status/`). The record and
  journal are git-ignored and stay private; `COOP.md` was IP-redacted before archiving.

~~~text
attic/qwen4/
├── ARMS-MANIFEST.md      # what each archived arm is and why
├── arms/                 # 24 archived recipes
├── status/               # W3/W4/W8 report memos
├── COOP.md  JOURNAL.md  QWEN4-MODEL-OPTIMIZATION-WORK.md
~~~

---

## Performance (measured, TP=2)

All `VERIFIED` in the lane record `attic/qwen4/QWEN4-MODEL-OPTIMIZATION-WORK.md` §3/§4/§19; quote
aggregate **and** per-request together, and read the cell's noise floor before comparing.

| quantity | RadixArk | labquant |
|---|---|---|
| single-stream decode (k=1, d=0) | **37.973 tok/s** | ~44 tok/s |
| aggregate peak (d=8192) | **86.86** @ k=16 | **91.38** @ k=16 |
| aggregate at k=24 (d=8192) | ~54 | ~56 |
| batching gain (bs=8 vs bs=1, aggregate) | **+119%** | — |
| NEXTN acceptance `A` | 2.18 (n=21) | 2.1924 (n=7) |

Two structural facts worth internalising before tuning anything here:

- **Decode is not purely byte-bound.** `t_step = F + bytes/B` with `B = 145.5 GB/s` and a fixed
  per-step cost **`F = 8.375 ms`** that no quantisation removes — 22% of a RadixArk step, 30% of a
  labquant step. This is why "fewer weight bytes" has been a weak lever.
- **There is no single noise floor.** Per-cell inter-boot floors span ~0.6–35%. Read your cell's
  floor (WORK §4b) or say you have not measured one. Same-boot/interleaved beats more repetitions.

The labquant checkpoint is faster but **more aggressively quantised and text-only**; no accuracy
evaluation exists for it, so a speed win is **not** evidence of equal quality. Use the RadixArk recipe
as the quality reference until an eval lands (`attic/qwen4/status/W3-QUALITY-EVAL-STATUS.md`).