# DeepSeek-V4-Pro-0813 on the WOPR fleet — feasibility, 2026-10-24

**Status: analysis complete; no boot attempted; nothing in `recipes/` changed.** Every weight byte
below is a Hub API file-sum (tree endpoint, recursive), recorded in the 2026-10-24 quant census —
not `usedStorage`. Evidence labels: **MEASURED** = read from a primary artifact or measured on this
fleet; **AUTHOR-REPORTED** = a model card's own claim, not verified here; **INFERRED** = arithmetic
on cited figures. (Directory vocabulary maps these to VERIFIED / LIKELY / SPECULATIVE; the census
and this file use the tighter trio.)

Inputs: the 2026-10-24 13-repo quant census (session artifact, re-derivable from the Hub API) and
the fleet-constraints brief drawn from [`DEEPSEEK.md`](DEEPSEEK.md),
[`attic/ds4/DS4-CANDIDATES.md`](../attic/ds4/DS4-CANDIDATES.md) and
[`LLAMACPP-GGUF.md`](LLAMACPP-GGUF.md). This file covers **DeepSeek-V4-Pro-0813** (`deepseek_v4`,
the 1.65T MoE) — a different model from the served DeepSeek-V4.1-Flash (`deepseek_v41`) stack, and
no figure from this file transfers to it without its own boot.

## Contents

- [1. Architecture brief (all from the base config + cards)](#1-architecture-brief-all-from-the-base-config--cards)
- [2. The fleet envelope (MEASURED, fleet docs)](#2-the-fleet-envelope-measured-fleet-docs)
- [3. Fit table — every whole-model artifact](#3-fit-table--every-whole-model-artifact)
- [4. The llama.cpp multi-node question — answered](#4-the-llamacpp-multi-node-question--answered)
- [5. Ranked feasibility list](#5-ranked-feasibility-list)
- [6. Provenance](#6-provenance)

## 1. Architecture brief (all from the base config + cards)

`deepseek-ai/DeepSeek-V4-Pro-0813` (MIT, ungated; config.json + cards, read 2026-10-24):

- **1.65T total / 49B active** (NVIDIA card; HF `safetensors` metadata expands to
  1,650,497,936,906). Third-party cards (unsloth, 6block, qtum) say 1.57T/48B — cards disagree,
  the count that matters for serving is per-tensor, so this changes nothing below. MEASURED
  (config/metadata), the disagreement AUTHOR-REPORTED.
- 61 layers + 3 hash layers + 1 MTP layer; MLA with **1 KV head**, `head_dim: 512`;
  hybrid Compressed-Sparse + Heavily-Compressed attention (indexer: 64 heads × 128 dim,
  top-k 1024); hyper-connections (`hc_mult: 4`).
- **384 routed experts, top-6**, one shared expert; `moe_intermediate_size: 3072`.
- 1,048,576-token context (YaRN ×16 from 65,536); vocab 129,280.
- **Factory weights are already 4-bit for the experts**: routed experts ship MXFP4 (E2M1 nibbles,
  one E8M0 scale per 32 elements), non-experts FP8 e4m3 (ue8m0 scales). This is why the factory
  pack is only 831.44 GiB for 1.65T params (4.33 bpw) and why third-party requants must pass
  `--allow-requantize` (6block card).
- **No chat template in the base repo** ("does not include a Jinja-format chat template"; a
  dedicated `encoding` folder instead). unsloth's mirror adds `chat_template.jinja` (13,772 B) —
  a GGUF/safetensors arm from the base repo would need unsloth's template or an explicit
  `--chat-template`, else every serve is a templateless checkpoint.
- Reference runtimes named by the base card: vLLM (`--moe-backend deep_gemm_mega_moe`,
  fp8 KV) and SGLang (`--moe-runner-backend flashinfer_mxfp4`), plus an in-tree PyTorch
  reference (`inference/`). The card's examples are GB300-class, not GB10.
- **DSpark speculative decoding is native**: `dspark_block_size: 5`, target layers 58–60,
  drafter weights ship inside the checkpoint (shards 64–66). The nvidia `nvfp4-DSpark` repo is the
  same model with the drafter additionally NVFP4-cast (+44.36 GB `model-dspark-mtp.safetensors`).

## 2. The fleet envelope (MEASURED, fleet docs)

| fact | value | source |
|---|---|---|
| device | 121.69 GiB unified | [`DEEPSEEK.md`](DEEPSEEK.md):1362 |
| usable per node | **103.7 GiB** (weights + KV + activations) | same |
| TP=4 aggregate | 414.8 GiB | arithmetic |
| TP=6 aggregate | 622.2 GiB | arithmetic |
| working boot precedent | ~105 GB weights/rank booted (TP=2 EXL3 arm); hard ceiling 128 GB | `DEEPSEEK.md:1101-1107` |
| `mem_fraction_static` ceiling | 0.80 (0.90 wedged three nodes, 2026-10-06) | `DEEPSEEK.md` §8.6 |

**KV arithmetic.** MEASURED on the dsv41 knapcio TP=4 arm: **1,670.75 B/token/rank**, replicated
not sharded (`num_key_value_heads: 1`), so a full 1M window costs **1.75 GB/rank** and KV is never
the constraint — weights are (`DEEPSEEK.md:1103`, `attic/ds4/AGENTS.md:243-247`). DSV4-Pro shares
the shape that produces the rule (1 KV head; MLA; sparse-compressed attention on top), so the
figure is used below as the anchor, but **no DSV4-Pro bytes/token has been measured here — the
transference is INFERRED**, and the headroom column treats 1M KV as ≈1.7 GiB/rank, i.e. it is an
upper-bound-scaled estimate, not a spec.

**Engine matrix** (MEASURED/READ, `DEEPSEEK.md` §17, `DS4-CANDIDATES.md`, `LLAMACPP-GGUF.md`):
SGLang is the shipped TP=4 class of engine on this fleet (dsv41 line); upstream vLLM lacks the
disk-Engram route that makes dsv41 TP=4 fit; the vLLM EXL3 fork precedent measured **63–67% of
SGLang at every batch cell** before retirement (dsv41, pre-1017); TensorFold's CUDA engine reads
EXL3 only and gates dsv41 at TP=2 via `CUDA_TP4` (`tensorfold/cli.py:253`,
`families/deepseek_v41/__init__.py`); llama.cpp arms in this repo are **single-node only** (§4
below); and one bespoke engine (DS4RT) exists for this exact model — see the fit table.

## 3. Fit table — every whole-model artifact

Per-rank = weight GiB ÷ TP degree. Headroom = 103.7 − per-rank − 1.7 (1M KV, INFERRED anchor).
"nodes needed" is weights alone, zero KV. Sizes: Hub tree-API sums (census, 2026-10-24).

| # | artifact | format | GiB | bpw | TP=4 rank | TP=6 rank | headroom @TP4 | verdict | engine route |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `deepseek-ai/DeepSeek-V4-Pro-0813` (and unsloth mirror #5) | FP8 + MXFP4 factory | 831.44 | 4.33 | 207.86 | 138.57 | − | **impossible on six nodes** (needs ≥9) | SGLang / vLLM (card) — moot here |
| 2 | `nvidia/…-NVFP4` (+ identical `AxionML` mirror #4) | NVFP4 | 876.48 | 4.56 | 219.12 | 146.08 | − | **impossible on six nodes** (needs ≥9) | SGLang / vLLM, card says B200-class 8×B200 — moot |
| 3 | `nvidia/…-nvfp4-DSpark` | NVFP4 + quantized drafter | 878.70 | 4.57 | 219.68 | 146.45 | − | **impossible on six nodes** | vLLM nightly (card) — moot |
| 6 | `unsloth/…-GGUF` UD-Q4_K_XL / UD-Q8_K_XL | GGUF | 791.35 / 858.08 | 4.12 / 4.47 | 197.84 / 214.52 | 131.89 / 143.01 | − | **impossible on six nodes** | llama.cpp — moot |
| 7 | `DevQuasar/…-GGUF` Q2_K / Q3_K_M / Q4_K_M | GGUF | 762.00 / 697.01 / 885.58 | 3.97 / 3.63 / 4.61 | 190.50 / 174.25 / 221.40 | 127.00 / 116.17 / 147.60 | − | **impossible on six nodes** | llama.cpp — moot |
| 8a | `ryant0000/…-gguf` BF16-hybrid / Q4_0 / Q4_1 | GGUF | 793.66 / 824.51 / 916.01 | 4.13 / 4.29 / 4.77 | 198.42 / 206.13 / 229.00 | 132.28 / 137.42 / 152.67 | − | **impossible on six nodes** | llama.cpp — moot |
| 8b | `ryant0000/…-gguf` Q2_K | GGUF | 530.31 | 2.76 | 132.58 | 88.39 | − | **fits TP6 only (bytes)** — no multi-node llama.cpp in this fleet's set (§4) | llama.cpp (blocked) |
| 8c | `ryant0000/…-gguf` Q2_0 | GGUF | 413.02 | 2.15 | 103.25 | 68.84 | −0.4 (0.45 before KV) | **fits TP6 only** — TP4 is 0.45 GiB from the wall with no KV room | llama.cpp (blocked) |
| 8d | `ryant0000/…-gguf` Q1_0 | GGUF | 206.91 | 1.08 | 51.73 | 34.49 | ≈+50.3 | **fits TP4 (bytes)** — needs the RPC image build (§4) | llama.cpp |
| 9/10 | `6block` / `qtum` IQ1_M | GGUF imatrix | 346.58 | 1.89 | 86.65 | 57.76 | ≈+15.3 | **fits TP4 (bytes)** — needs the RPC image build (§4) | llama.cpp |
| 9/10 | `6block` / `qtum` IQ1_S | GGUF imatrix | 314.10 | 1.72 | 78.53 | 52.35 | ≈+23.5 | **fits TP4 (bytes)** — needs the RPC image build (§4) | llama.cpp |
| 9/10 | `6block` / `qtum` Q2_K | GGUF imatrix | 546.96 | 2.99 | 136.74 | 91.16 | − | **fits TP6 only (bytes)** — blocked, as 8b | llama.cpp (blocked) |
| 9/10 | `6block` / `qtum` IQ3_XXS | GGUF imatrix | 576.99 | 3.15 | 144.25 | 96.17 | − | **fits TP6 only (bytes)**, 5.8 GiB/rank spare — blocked, as 8b | llama.cpp (blocked) |
| 9/10 | `6block` / `qtum` Q3_K_M | GGUF imatrix | 711.29 | 3.88 | 177.82 | 118.55 | − | **impossible on six nodes** (needs ≥7) | llama.cpp — moot |
| 11 | `pokey2025/dspark-…-gguf` | GGUF drafter only | 28.65 | mixed | — | — | — | **add-on, not a model** — pairs with a main model under ik_llama.cpp `--spec-type dspark`; untested on upstream | ik_llama.cpp (not in fleet set) |
| 12 | `bullerwins/…-exl3-2.04bpw` | EXL3 safetensors | 411.23 | 2.14 | 102.81 | 68.54 | −0.4 (0.89 before KV) | **fits TP6 only (bytes)** — and no fleet engine reads EXL3 for this arch (§5) | TensorFold? / vLLM-EXL3 fork — unverified for `deepseek_v4` |
| 13 | `wrldsuksgo2mars/…-EXL3-K2-calibrated-v1` | EXL3 K2 calibrated | 407.69 | 2.12 | 101.92 | 67.95 | −0.5 (1.78 before KV) | **fits TP6 only (bytes)** — bespoke engine; see below | **DS4RT** (bespoke) |

Row 13 caveat, stated explicitly: DS4RT's supported topology is **one RTX PRO 6000 Blackwell 96 GB
coordinator + four DGX Spark workers on a dedicated 400 Gb/s path** (card). This fleet has six GB10
Sparks and no RTX PRO 6000 — the card's served numbers (**AUTHOR-REPORTED**: 38.08 tok/s semantic
decode, 63.98% adaptive-dSpark acceptance, Tool Eval 86/100 with a failed safety gate; calibrated on
1,426 prompts / 1.081M tokens) were produced on that other topology and are **not** evidence anything
boots here. The same applies to row 12's card, which names no engine at all.

Not in the table because they are not model artifacts: the DSpark drafter files (28.65 GiB GGUF;
the NVFP4 drafter shard set inside row 3) — add-ons that ride with a main model. The `usedStorage`
field is not used anywhere above: for the base repo it reads 1,781,787,608,346 = exactly 2.00× the
892,744,322,880 B file sum (census anomaly; unsloth's identical mirror reports the file sum exactly),
and three further repos report usedStorage below their sums.

## 4. The llama.cpp multi-node question — answered

**Can a 206–350 GiB GGUF run across 4 GB10 nodes with llama.cpp? Yes in principle, not with the
image this fleet pins today, and at an expected heavy throughput penalty.**

1. **The route exists upstream.** The RPC backend (`ggml-rpc-server`) exposes ggml devices on
   remote hosts; `llama-cli`/`llama-server` attaches them with `--rpc host:port,…` and, by default,
   "distributes model weights and the KV cache across all available devices — both local and
   remote — in proportion to each device's available memory" (overridable with `--tensor-split`).
   RDMA is supported: RoCEv2 via libibverbs, negotiated at handshake, TCP fallback
   (https://github.com/ggml-org/llama.cpp/blob/master/tools/rpc/README.md, READ 2026-10-24). Our
   200 GbE RoCE fabric is therefore the intended transport class. Two caveats from the same
   document, quoted: the backend is "in a proof-of-concept development stage … fragile and
   insecure. Never run the RPC server on an open network", and RDMA is point-to-point (a
   connection made on the wrong interface stays on TCP).
2. **The `deepseek4` arch is in upstream master** — verified in source today 2026-10-24:
   `LLM_ARCH_DEEPSEEK4` at `src/llama-arch.h:94`, mapped to `"deepseek4"` at
   `src/llama-arch.cpp:89`, with graph/tensor wiring at `src/llama-arch.cpp:1241,1267,1284`
   (https://github.com/ggml-org/llama.cpp/blob/master/src/llama-arch.h). The 6block card's pin —
   llama.cpp @ `4ed2b13`, "needs `LLM_ARCH_DEEPSEEK4`; older builds reject `deepseek4`" — is
   satisfied by current master, and the pinned GB10 image's stock arch map already lists
   `deepseek4` as loadable ([`LLAMACPP-GGUF.md`](LLAMACPP-GGUF.md):71).
3. **But the pinned image cannot do multi-node**: `scitrera/dgx-spark-llama-cpp:b10549-cu131` ships
   `llama-server` only — "`rpc-server` **absent** — the image ships `llama-server` only, so the
   experimental multi-node RPC path cannot be exercised with this tier"
   ([`LLAMACPP-GGUF.md`](LLAMACPP-GGUF.md):38). Multi-node GGUF therefore costs a **self-built
   image** (`-DGGML_RPC=ON` + CUDA) — consistent with the standing owner direction to build our own
   containers rather than install third-party packages (`QUESTIONS.md #6`). Until that build
   exists, every llama.cpp arm in this fleet is single-node, which caps it at 103.7 GiB — no
   DSV4-Pro GGUF tier fits single-node (smallest is Q1_0 at 206.91 GiB).
4. **Expected penalty: INFERRED, unmeasured here.** RPC is not tensor parallelism: tensors are
   split across devices and every op dispatched to its device crosses the network, with no fused
   TP allreduce and no CUDA-graph equivalent spanning nodes; the docs ship it as proof-of-concept.
   Against the shipped SGLang dsv41 baseline (C1 69.28 / C10 116.27 t/s, `STATUS.md`) the honest
   expectation is a large decode deficit — community consensus and the architecture both point that
   way, but no number exists for this fleet, so the first boot gate below is to measure one.

**Plain answer:** a 206–350 GiB GGUF (rows 8c–9) *can* span 4 GB10 nodes byte-wise
(4 × 103.7 = 414.8 GiB usable vs ≤346.6 GiB of weights), via the RPC backend with RoCE RDMA, on
current upstream whose `deepseek4` arch is present — but only after building our own image, with
PoC-grade fragility, and at an expected penalty no measurement on this fleet bounds yet.

## 5. Ranked feasibility list

Each entry: what it is, why it ranks there, the falsifier (what kills it), and the boot gates.

**R1 — `6block`/`qtum` IQ1_M (346.58 GiB, 1.89 bpw) at TP=4, llama.cpp RPC multi-node.**
The largest imatrix quant that fits TP=4 with usable headroom (86.65 GiB/rank, ≈15.3 GiB spare
after 1M KV). Same engine work as every GGUF candidate; ranked over IQ1_S purely on quant quality.
- Falsifier: the RPC 4-node boot fails to dispatch (`--rpc` connect/graph errors), or decode is
  unmeasurably slow (no completion inside a benchmark window).
- Boot gates: (i) build the image (`-DGGML_RPC=ON`, CUDA for sm_121), `rpc-server` present in
  `PATH`; (ii) arch loads at a ref ≥ `4ed2b13` (`deepseek4` accepted, `--allow-requantize`-era
  build); (iii) 4-node boot with `--rpc` ×3, weights + KV resident under 103.7 GiB/rank;
  (iv) one C1 decode cell — this produces the fleet's first RPC penalty number; (v) accuracy only
  if a decode number exists: card PPL table is AUTHOR-REPORTED, the house 37/37 battery is the bar.

**R2 — `6block`/`qtum` IQ1_S (314.10 GiB, 1.72 bpw) at TP=4, same route.** 78.53 GiB/rank,
≈23.5 GiB spare — the most comfortable TP=4 fit in the census. Falls below R1 only on quant
quality (card PPL table, AUTHOR-REPORTED; the 6block card documents that IQ2_XS/IQ2_XXS blew up on
this sparse MoE and were rejected, so the IQ1 band is already the survivable floor).

**R3 — `ryant0000` Q1_0 (206.91 GiB, 1.08 bpw) at TP=4.** Only artifact with generous TP=4
headroom (≈50 GiB/rank); a single 206.91 GiB file (simplest fetch on the shared cache). Ranked last
of the fitting trio because it is a non-imatrix flat quant of a 1.65T sparse MoE — quality
expectation worst — and the card says "UPLOADS IN PROGRESS" with "weird templating issues".
- Extra gate before any fetch: verify on the Hub API that the Q1_0 tier is actually complete
  (single-file 222,163,604,736 B, sha present) — the census read the card mid-upload.

**R4 — the EXL3 pair (`bullerwins` 2.04 bpw 411.23 GiB; `wrldsuksgo2mars` K2 calibrated 407.69
GiB) — best bytes-per-quality in the fitting band, engine-blocked.** At TP=4 each rank lands at
~102–103 GiB: at or past the usable line with zero KV room, so bytes-wise they are TP=6-only — and
no fleet engine reads EXL3 for `deepseek_v4`:
  - **DS4RT** (row 13's named engine) requires the RTX PRO 6000 coordinator topology — not ours.
  - **TensorFold**'s CUDA engine is EXL3-only, and its dsv41 family package gates multi-GPU at
    TP≤2 (`CUDA_TP4`, `tensorfold/cli.py:253`); whether a `deepseek_v4` family package exists at
    all is **unverified** — this is the first falsifier to check, and it is free: read
    `families/` in the TensorFold image for a `deepseek_v4` package before paying anything.
  - **vLLM EXL3 fork**: the 63–67%-of-SGLang precedent is dsv41-class; `deepseek_v4` support in
    that fork is unverified.
- Falsifier: TensorFold has no `deepseek_v4` family (or repeats the CUDA_TP4 gate); the fork's
  model loader rejects `DeepseekV4ForCausalLM`.

**R5 — the TP6-only GGUF tiers (Q2_K 546.96 / IQ3_XXS 576.99 / ryant Q2_K 530.31 / Q2_0 413.02).**
Bytes-fit on all six nodes but strictly worse than R1–R3 on every axis: more nodes consumed, an
unbuilt image, and per-rank headroom that shrinks toward the IQ3_XXS 5.8 GiB floor. No path unless
R1–R3 establish the RPC route and someone still wants the quality step up.

**Impossible on six nodes (needs ≥7–10):** rows 1–3 and 6–7 and 8a and 9's Q3_K_M — every artifact
≥622.2 GiB: the factory FP8+MXFP4 pack and its unsloth mirror (831.44 → 9 nodes), both NVFP4 packs
(876.48/878.70 → 9), unsloth UD-Q4_K_XL/Q8_K_XL (791.35/858.08 → 8/9), DevQuasar Q2_K/Q3_K_M/Q4_K_M
(762.00/697.01/885.58 → 8/7/9), ryant BF16/Q4_0/Q4_1 (793.66/824.51/916.01 → 8/8/9), 6block Q3_K_M
(711.29 → 7). These are the *good* quants (Q3+ and factory FP8/MXFP4/NVFP4) — the structural result
of this analysis is that **every artifact this fleet can actually serve is in the sub-2-bpw band**,
so a DSV4-Pro arm would be a quality gamble even before the engine penalty; nothing here threatens
the dsv41 baseline's role, and the `#4` fence on `.30`–`.33` applies to any boot attempt anyway.

## 6. Provenance

- Weight sums: `https://huggingface.co/api/models/<id>/tree/main?recursive=true`, census 2026-10-24
  (13 repos; per-repo anomalies flagged in §3 and §1 of the census and restated above where used).
- Cards: the Hub READMEs of the listed repos (NVIDIA quant-method/dspark cards, 6block requant
  card, wrldsuksgo2mars DS4RT card, unsloth, DevQuasar, ryant0000, pokey2025, bullerwins).
- Fleet envelope, engine matrix, KV arithmetic: [`DEEPSEEK.md`](DEEPSEEK.md),
  [`attic/ds4/DS4-CANDIDATES.md`](../attic/ds4/DS4-CANDIDATES.md),
  [`LLAMACPP-GGUF.md`](LLAMACPP-GGUF.md), [`STATUS.md`](STATUS.md) — line refs inline.
- llama.cpp: `tools/rpc/README.md` and `src/llama-arch.h` / `src/llama-arch.cpp` on master, READ
  2026-10-24 (URLs inline).
- Not verified here: any boot, any RPC latency, TensorFold's `deepseek_v4` family support, the
  ryant0000 Q1_0 tier's upload completeness. All INFERRED entries are labelled.
