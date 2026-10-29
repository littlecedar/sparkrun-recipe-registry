# DS4 candidate survey — quant/engine variants of DeepSeek-V4.1-Flash-1017 for a TP=4 arm (2026-10-24)

**Status:** survey, 2026-10-24, read-only — **no boot was run and no node was contacted**. Produced in
parallel with the 2026-10-24 TP=4 window (`QUESTIONS.md` header, `.31`–`.34`); it proposes candidates for
the *next* window and does not touch `recipes/`, `mods/` or any live lane file.

**Question:** which quant or engine variant of `deepseek-ai/DeepSeek-V4.1-Flash-1017` (pin
`1bae0e1088993b9b82de08f59de5be5a34e42170`) could become a TP=4 arm on four GB10 Sparks, beyond the
shipped knapcio SGLang arm and the TensorFold TP=2 pair?

**Evidence vocabulary** (directory convention, `mad-science/DEEPSEEK.md` §1): **VERIFIED** = read from
a primary artifact or measured on GB10; **LIKELY** = strong secondary evidence or someone else's
measurement; **SPECULATIVE** = reasoning without a source. Hub card claims are treated as **LIKELY**
until a file census or boot confirms them.

## Contents

- [1. The fit frame](#1-the-fit-frame)
- [2. Candidates](#2-candidates)
- [3. Screened, not candidates (post-2026-10-17 Hub sweep, one line each)](#3-screened-not-candidates-post-2026-10-17-hub-sweep-one-line-each)
- [4. Ranked recommendation — top 3 to boot-test in the next window](#4-ranked-recommendation--top-3-to-boot-test-in-the-next-window)
- [5. Settled-negative — falsified variants (do not re-propose)](#5-settled-negative--falsified-variants-do-not-re-propose)
- [6. Method and limits](#6-method-and-limits)

## 1. The fit frame

| anchor | value | provenance |
|:--|--:|:--|
| device per node | 121.69 GiB unified; **~103.7 GiB usable** after the ~18 GiB the OS and page cache hold — the envelope for weights + KV + activations, not "beyond" them | `DEEPSEEK.md` §17 |
| official body at TP=4 | non-Engram weights **71.6 GiB/rank**; Engram **47.2 GiB/rank** resident, or packed to NVMe (2 × 23.6 GiB/rank) and streamed | `DEEPSEEK.md` §17 |
| KV cost | **1,670.75 B/token/rank**; `num_key_value_heads: 1`, so KV never shards | `DEEPSEEK.md` §17; `attic/ds4/AGENTS.md` §2.4 |
| shipped KV pool | 6,849,792 tokens ≈ 10.7 GiB/rank | `DEEPSEEK.md` §17 |
| shipped arm bars | C1 ≥ 64.0, C10 ≥ 110.5 t/s, house ≥ 36/37 at 4096 thinking-on, needle 3/3 to 983,040 | `DEEPSEEK.md` §17 |

Every EXL3 fit below assumes the Engram stays NVMe-streamed as the TensorFold lane serves it
(`attic/ds4/AGENTS.md` §12.7 — the Engram belongs to the official repo, not the EXL3 pack), so the
memory cost is weights only; the token headroom is `(103.7 − weights_GiB) × 2^30 / 1,670.75`, engine
overheads not yet subtracted — **LIKELY**, arithmetic on cited sizes. SGLang/knapcio-route fits instead
carry the Engram resident (47.2 GiB/rank) and are marked so.

## 2. Candidates

| variant | source repo + revision | expected size | engine route | fit at TP=4 (weights + KV headroom) | known blockers | provenance |
|:--|:--|:--|:--|:--|:--|:--|
| **Stack C — vLLM b12x fork, official checkpoint** | `deepseek-ai/DeepSeek-V4.1-Flash-1017` @ `1bae0e10…` on `local-inference-lab/vllm` fork `dev/karmic-kraken` @ `8244d1c4`; image `eugr/spark-vllm-b12x@sha256:03a9565…` | 510.29 GB (unchanged) | vLLM TP=4, disk-Engram (`table_memory: "disk"`), b12x attention/MoE/linear, RoCE allreduce; full serve-line sketch exists | 71.6 GiB weights + 10.7 GiB KV = 82.3 GiB/rank — inside 103.7, not with much room (`DEEPSEEK.md` §17) | io_uring seccomp route: the fork ships `scripts/seccomp/spark-io-uring.json` and this repo's `executor_config` cannot express a profile (mod or executor-level change first). Fork-held capability, no release wheel. C10 has no number anywhere | `DEEPSEEK.md` §17; `TODO.md` §"Settled questions" `#17` (**authorized 2026-10-24, pending the seccomp route**); `QUESTIONS.md` #17 |
...branch — neither demonstrated in-tree | **43.0 GiB/rank** weights → **~39.0M-token** KV headroom — the largest of any candidate | Author gates it TP=2, not TP=4; tool calls lose most (KL 0.595, top-1 79.4%); below the lane's parity bar (EXL3 2.9 bpw measured at parity) — a different product, like §13's 1.77 bpw verdict | card (VERIFIED claims, author-measured cells: C1 code 105.7 / prose 60.3, 4-stream 152.5 aggregate, KL 0.1305 short); Hub API usedStorage; `DEEPSEEK.md` §13 (parity bar) |
| **EXL3 4.0 bpw, 1017** | `bertholomus/DeepSeek-V4.1-Flash-1017-EXL3-4.0bpw` @ `f3657818` | 288.43 GB | same as above; the card itself positions 4.0 bpw as the **four-node** pick "for agent work that needs the closest match" | **67.2 GiB/rank** → **~23.5M-token** headroom | Same engine-route gap; no TP=4 receipt anywhere | 2.5 bpw card §Quality (KL 0.0331 / top-1 96.17% short — near the parity bar); Hub API usedStorage |
...1-Flash-1017-EXL3-EAQ-v1.1-2.9-bpw` @ `aee640e2` (2026-10-22) | 210.79 GB (same class as the shipped LibertAIDAI 2.9 bpw, 210.72 GB) | TensorFold TP=2 (drop-in body swap; Mia-AiLab publishes the reference TP=2 stacks) | **49.1 GiB/rank** → **~35.1M-token** headroom | Same-size alternative to the shipped EXL3 body — value is only a fidelity claim over EAQ vs mul1, unmeasured here; TP=4 engine route unproven | Hub API usedStorage + tags (`eaq`, `exllamav3`); shipped-body comparison `DEEPSEEK.md` §13 |
| **EXL3 2.8 bpw, 1017** | `sudoingx/DeepSeek-V4.1-Flash-1017-EXL3-2.8bpw` @ `aba08ea0` (2026-10-22) | 203.94 GB | tags `vllm`, `dgx-spark`, `gb10` — vLLM EXL3 route (retired attic recipes) | **47.5 GiB/rank** → **~36.1M-token** headroom | No published quality panel, gates, or boot receipt on the card — below the survey's evidence bar until one exists | Hub API usedStorage + tags |
| **EXL3 3.5 / 3.75 bpw, 1017** | `easthambuilds/DeepSeek-V4.1-Flash-1017-EXL3-3.5bpw` @ `1a8bb600` (2026-10-20); `…-3.75bpw` @ `3c39fdf9` (2026-10-22) | 253.32 GB / 270.30 GB | TensorFold / vLLM EXL3 | **59.0 / 62.9 GiB/rank** → **~28.7M / 26.2M-token** headroom | Higher-bpw EXL3 buys nothing at TP=4 that the official checkpoint does not already deliver — the official body at TP=4 costs 71.6 GiB/rank, and the whole reason for EXL3 at TP=4 would be a smaller/better product, not a bigger one | Hub API usedStorage; the survey's own sizing logic (`DEEPSEEK.md` §13) |
| **REAP192 (192-of-384 experts kept, MXFP4, bit-exact)** | `patrickbdevaney/DeepSeek-V4.1-Flash-1017-REAP192-MXFP4` @ `20675372` (2026-10-24); Engram from base shards 47/48 | 162.75 GB body (Hub usedStorage) + 203 GB Engram from base | knapcio SGLang image (native MXFP4) with a 192-expert `config.json`; TensorFold refuses it (`family.check()` rejects non-`exl3`, `attic/ds4/AGENTS.md` §12.12) | SGLang route: 37.9 + 47.2 Engram resident = **85.1 GiB** before KV → **~5.7M-token** headroom, *below* the shipped 6.85M pool — the pruning does not buy KV headroom on this lane | Quality gate **FAILED as originally registered** (kl32 not better than a random keep-set, −0.1014 [−0.220, +0.040]; amended post-hoc 2026-10-24); multilingual top-1 0.52; DSpark draft refit not finished ("being refit"); `n_routed_experts 192` unproven on any engine here | card (evaluation tables, gate-amendment paragraph, Engram pointer); Hub API usedStorage |
...llama.cpp does not support DeepSeek-V4.1 as of 2026-10-23 | weights 32.2 + Engram 25.8 = 58.0 GiB/rank → ~29.4M-token headroom — moot without an engine | **No multi-node TP path in Strata** (12 GB VRAM single-host design); llama.cpp gate closed; IQ2_XXS quality is the best published (100.0% task-average recovery on AIME25/GPQA/LCB) — the *checkpoint* is interesting, the *route* is not | card (§Available files, §Runtime support); same engine wall as `kaushikvira` strata (`DEEPSEEK.md` §15.2) |
| **dsx-t16 / dsx-ud** | `lxe/DeepSeek-V4.1-Flash-1017-dsx-t16` @ `8bf76fe6` (2026-10-22); `…-dsx-ud` @ `870106a8` (2026-10-21) | 712.55 GB / 446.84 GB Hub usedStorage | `dsx` (Rust + CUDA) | **size-excluded at TP=4**: 178 / 111.7 GB/rank against a 103.7 GiB envelope | The earlier `dsx-2bit` body (148.09 GB) would fit (37 GB/rank) but `dsx` has no demonstrated GB10 build (`DEEPSEEK.md` §13) — and the newer lxe exports above it do not fit at all | Hub API usedStorage; `DEEPSEEK.md` §13 |

## 3. Screened, not candidates (post-2026-10-17 Hub sweep, one line each)

Method: HF API `models?filter=base_model:quantized:deepseek-ai/DeepSeek-V4.1-Flash-1017&sort=createdAt`
fetched 2026-10-24; ~40 repos, 2026-10-20 → 10-24. Full-size FP8/MXFP4 abliteration re-uploads
(`overhand`, `fribourgquants`, `Lordking998`, `cyberneurova`, `distributedcognition`, `BeriaLabs`,
`ktobik` — 510.3 GB class) change content policy, not fit or speed, and inherit the §15.2 provenance
caution (settled abliteration provenance before quoting as an official-weights variant).

| repo | size (usedStorage) | why not |
|:--|--:|:--|
| `smalinin/…-1017-IQ2_XXS-GGUF` @ `d7db647b` | 307.70 GB | fits (76.9 GB/rank) but llama.cpp does not support this family (`LLAMACPP-GGUF.md` §2; ISTA card) — no engine |
| `cliecy/…-IQ1S/IQ2XS-GGUF` × 8 (expert-pruned) @ `d0151c81` (representative) | 99–224 GB | llama.cpp gate again, plus self-declared `experimental` pruning; multilingual fragility pattern per REAP card |
| `staccs/…-lecore-vq10sh12-GGUF` @ `9b6cfac8` | **99.12 GB** | TP=1-class VQ body; engine `lecore` unidentified — nothing this lane ships reads it |
| `Baekpica/…-1017-iVQ-GGUF` @ `7d1daa21` | 317.60 GB total (body 113.56 GB + official Engram shards + vision sidecar) | engine `ds4-dfm-rs` is single-node DGX Spark CUDA; card's own top-1 82.5%, "exploratory… not a drop-in replacement" |
| `wenzhouwu/YoungAi-DeepSeek-V4.1-Flash` (VQ, 113.6 GB + 40 MB domain sidecars) | ~113.6 GB body | measured **on a single DGX Spark** (prefill 489 t/s, decode 30.7 t/s, Engram on SSD) — a TP=1 exception to §13's byte wall worth recording, but the ds4 engine is single-node with no TP=4 path |
| `mlx-community/…-oQ{2,2.5,3,4}e-ngram-mtp` | — | MLX/Apple only; no CUDA route |
| `kernelpool/…-MXFP4-GGUF` @ — | — | `metal` tag; GGUF gate |
| `JERRYNPC/…-int3-v100`, `philbert440/…-EXL3-franken-v100` | — | SM70/V100 targets, custom-code loaders |
| `x00byte/DeepSeek-V4.1-Flash-1017-Dual-Spark` | TP=2 recipe repo | a TP=2 community route (TensorFold + vLLM, measured C1 code 103.4 / C8 267.0 aggregate, 2026-10-18) — a data point for the TP=2 lane, not a TP=4 arm |
| `bertholomus/…-EXL3-3.0bpw` | query returned none | repo absent/empty at fetch time |

**Note the VQ class against §13:** `DEEPSEEK.md` §13 closes TP=1 on the strength of published
safetensors/GGUF/EXL3/dsx bodies. The VQ route (YoungAi's 113.6 GB vector-quantized body, Engram kept on
SSD at ~6 KB/token reads) is a measured single-Spark counterexample dated 2026-09-28 — **LIKELY**
(author-measured, hardware we own a twin of), single-node only. It does not change any TP=4 conclusion
here, but §13's "no 1017-class body fits TP=1" sentence should be read with this exception named.

## 4. Ranked recommendation — top 3 to boot-test in the next window

1. **Stack C — the vLLM b12x parity boot** (`DEEPSEEK.md` §17 sketch + acceptance test). It is the only
   TP=4 candidate that is *authorized* (`QUESTIONS.md` #17, settled 2026-10-24) with a written serve
   line and a pre-registered pass bar; the remaining gate is engineering (io_uring/seccomp profile), and
   the qwen4 b12x arm boots disk-Engram on this fleet without one (`DEEPSEEK.md` §17), so probe
   `io_uring_setup` under `--rm` first. One boot settles the route's only open axis (C10).
2. **bertholomus EXL3 2.5 bpw (1017)** as the survey's cheapest new-body trial: the author publishes the
   richest evidence package of any 1017 quant (revision pin, KL/top-1 panel with CIs, served-gate
   receipts, a working TP=2 recipe repo). Boot it on the **TP=2 pair first** (`TODO.md`'s existing
   TensorFold arm, drop-in body swap, Engram unchanged) — a zero-new-engine trial — and only promote a
   TP=4 EXL3 arm if the pair result clears the house bar.
3. **bertholomus EXL3 4.0 bpw at TP=4** as the parity-grade EXL3 four-node arm: the author's own
   four-node pick, 67.2 GiB/rank with ~23.5M-token KV headroom, short-context top-1 96.17% — the only
   candidate body besides the official checkpoint whose published fidelity sits at the lane's parity
   bar. Route through the retired attic EXL3-vLLM recipes (boot-proven engine, mods in
   `attic/ds4/mods/`), with the honest caveat that they were retired for aggregate throughput (63–67%
   of SGLang at every batch cell, `DEEPSEEK.md` §17), so this arm competes on KV headroom and
   quality, not on expected decode.

Ranking logic: the shipped arm is untouched and remains the production answer; 1 is authorized and
settles an engine question the register already owns; 2 and 3 are the only post-1017 quants with
author-published fidelity evidence at or near the parity bar, and both reuse engines this repo has
already booted.

## 5. Settled-negative — falsified variants (do not re-propose)

| variant | where falsified |
|:--|:--|
| Any 1017-class body at TP=1 in safetensors/EXL3/GGUF/dsx formats (552B needs ≤1.52 bpw effective to fit 105 GB; smallest published is 1.77 bpw / 122.38 GB) | `DEEPSEEK.md` §13, `attic/ds4/AGENTS.md` §1 — *with the VQ exception named in §3 above, which postdates the survey* |
| 1017 NVFP4 (W4A4) on SGLang — the 1017 pack quantizes Engram to MXFP4, unsupported by SGLang; no FP8-Engram 1017 NVFP4 pack exists; and `nvidia/…-NVFP4` is 17 GB *larger* than the MXFP4 original | `DEEPSEEK.md` §10.12, `attic/ds4/AGENTS.md` §2.3 |
| EP > 1 (EP=2, EP=4 + graphs off) on the knapcio image — dies at the first decode plan, both re-tested | `DEEPSEEK.md` §8.1, `attic/ds4/AGENTS.md` §11 |
| Strata-format GGUF (the `kaushikvira` 382.8 GB export) — no shipped engine opens it; engine has no arm64/GB10 build and no multi-node path | `DEEPSEEK.md` §15.2 |
| llama.cpp GGUF route for this family — the pinned runtime's arch map lacks the arch, and the ISTA card confirms upstream llama.cpp does not support DeepSeek-V4.1 (2026-10-23) | `DEEPSEEK.md` §13; `mad-science/LLAMACPP-GGUF.md` §2; ISTA card §Runtime support |
| Upstream vLLM Engram placement (device or pinned host RAM) at TP=4 — 118.8 GiB/rank against 103.7 usable, a ~15 GiB deficit at zero KV; host RAM is GPU RAM on GB10 | `DEEPSEEK.md` §17; `attic/ds4/AGENTS.md` §3.2; `DEEPSEEK.md` §10.14 |
| HiCache / host-tier KV / `OFFLOAD_MODE=ram` as memory tools | `DEEPSEEK.md` §10.14; `attic/ds4/AGENTS.md` §9 |
| DCP2 decode context parallelism with `dsv4` + DSpark — upstream allowlists only Kimi Linear + DSpark | `DEEPSEEK.md` §10.13 |
| TP=2 by quantizing harder (EXL3 at 3.5 bpw is still 37 GB over the pair's RAM for the *old* base; the shipped 2.9 bpw TP=2 arm exists, the "escape" framing is dead) | `attic/ds4/AGENTS.md` §9 |
| TensorFold loading the official MXFP4 checkpoint — `family.check()` rejects a non-`exl3` `quant_method` | `attic/ds4/AGENTS.md` §12.12 |
| Retired vLLM/EXL3 lane as a *throughput upgrade* — measured 63–67% of SGLang at every batch cell on the same four nodes (vLLM 0.28.1 + NCCL, pre-1017 base) | `DEEPSEEK.md` §17; `attic/ds4/AGENTS.md` §1, §7.12 |
| Serving V4.1/1017 on SGLang from any published image other than the vendored canary-roce build | `attic/ds4/AGENTS.md` §9 — superseded only by the vendored image itself |

## 6. Method and limits

- **No boot, no node contact, no file outside this document and read-only sources.** Every fit cell is
  arithmetic on Hub `usedStorage` (API, fetched 2026-10-24) or card-published sizes — **LIKELY**, not
  VERIFIED-by-census; no GGUF/EXL3 header was opened.
- **Card claims are the publishers' own.** The bertholomus and ISTA panels are self-measured with
  stated methodology; the REAP192 gate history is quoted from its card including the post-hoc
  amendment, which is itself evidence about the release discipline.
- **Engine routes are the binding constraint, not size.** Every sub-104-GB/rank body except the EXL3
  family lacks a multi-node engine this repo boots; the EXL3 route's TP=4 engine path is proven only on
  the pre-1017 base via the retired attic recipes.
- The `#4`-fence-era survey (`DEEPSEEK.md` §10) covered engine/scheduler knobs, not quants; this
  document is the quant complement and deliberately repeats none of §10's items.
