# Qwen3 lane — `recipes/qwen3/`

_Brought to you by Little Cedar Group._

Shipped `sparkrun` recipes for the **Qwen3.8-27B** (SGLang, single DGX Spark) family.
All run on NVIDIA DGX Spark (GB10, 128 GB unified memory), TP=1 unless stated. The four
Qwen3-VL embedding/reranking recipes moved to their own lanes on 2026-10-10:
[`recipes/embed/`](../embed/README.md) and [`recipes/rerank/`](../rerank/README.md).

> Working here? Read [`NOTES.md`](NOTES.md) first (state, plan, constraints) and [`COOP.md`](COOP.md)
> (live node/bench claims) before touching anything. This README is the human-facing summary.

## Recipes

| recipe | runtime | model | flags | C1 t/s | notes |
|---|---|---|---|---|---|
| `qwen3.8-27b-nvfp4-dflash2-sglang` | sglang | [RadixArk/Qwen3.8-27B-NVFP4] + [incoai/Qwen3.8-27B-DFlash2] draft | ✨🚀🌲 | **33.8** | **shipping.** DFLASH2 spec decode, block 8. Decode-only, d=0, c=1. |
| `qwen3.8-27b-nvfp4-nospec-control-sglang` | sglang | [RadixArk/Qwen3.8-27B-NVFP4] | 🧪 | 12.6 | **control only** — same bytes, no `--speculative-*`. Not for serving. |
| `qwen3.8-27b-nvfp4-dspark-sglang` | sglang | [RadixArk/Qwen3.8-27B-NVFP4] + [RadixArk/Qwen3.8-27B-DSpark] draft | 🌲 | 28.5 | **measured 2026-10-10, NOT an upgrade** — DSPARK boots on GB10 but loses ~16% to the DFlash2 lane (28.5 vs 33.8 t/s, decode-triage). Kept as the documented DSPARK-path arm. |

Flags: ✨ official · 🚀 fast (≥ 50 t/s) · 🌲 lcg_favorite · 🧪 measurement-only.


### Qwen3.8-27B — what the numbers mean

- **The model is dense, so it is a streaming-bandwidth problem, not a gather problem.** 64 layers = 48
  GDN (linear-attention) + 16 full-attention, no experts. Every weight is read every token:
  **17,608 MB/token** of weights, against ~**221 GB/s** effective read → a plain-decode ceiling of
  **~14 tok/s** at TP=1 (`VERIFIED`). Every published throughput is that ceiling times speculative
  amplification (`tok/s ≈ A_eff × BW / B_token`).
- **Speculative decoding is where the speed is.** The DFLASH2 draft raises decode to **33.8 t/s** at
  block 8 (d=0, c=1). Block 8 vs block 4 is **+22.5 %** ([1.188, 1.262]), pooled over 24 boots — the
  recipe ships block 8 because the draft was *trained* at 8, not because 12 is better (12 is flat, and
  A_eff saturates at ≈3.75).
- **`max_num_seqs: 48` in the recipe is a deliberate artifact.** The mamba/GDN state pool silently
  clamps it to **21** on a fresh container (`K=85`) — the clamp is logged, not an error. Read the grant
  from the server log (`grep -F 'capped to'`) rather than trusting the literal.
- **Long context costs decode.** At `c=8`, depth above ~8k is **~20 %** slower (congested/pool-limited;
  boot-level 8–29 %); uncongested at `c=4` the cost is **~11 %**. The mechanism is unsettled — do not
  quote a KV-bandwidth figure (four were retracted).
- **`mamba_ssm_dtype: bfloat16` doubles granted concurrency** (21 vs the checkpoint's declared
  `float32`'s 10) and is bit-identical on the state-read path. This is a deliberate override of the
  checkpoint; see `SSM-STATE-DTYPE.md`. Do not "restore float32 for safety".

## Notes

- **Evidence docs:** `QWEN3-MODEL-OPTIMIZATION-WORK.md` (decision record, `§N`; git-ignored),
  `DEPTH-COST.md`, `SSM-STATE-DTYPE.md`, `ANSWERED-QUEUES.md` (search by profile name before running
  anything), and the narrative `JOURNAL.md` / `EMBED-JOURNAL.md` / `QWEN3-EMBED-OPTIMIZATION-WORK.md`.
- **Guards:** `tests/test_qwen3_vl_embeddings.py` now covers the moved VL recipes in the
  `embed`/`rerank` lanes. There is no test for the 27B lane yet.
- **Raising a bug upstream?** Name the pinned container commit you read and cite `file.py:line`
  (`README`/`WORK` do this throughout).

<!-- Links -->
[RadixArk/Qwen3.8-27B-NVFP4]: https://huggingface.co/RadixArk/Qwen3.8-27B-NVFP4
[incoai/Qwen3.8-27B-DFlash2]: https://huggingface.co/incoai/Qwen3.8-27B-DFlash2
[Intel/Qwen3-Coder-Next-int4-AutoRound]: https://huggingface.co/Intel/Qwen3-Coder-Next-int4-AutoRound