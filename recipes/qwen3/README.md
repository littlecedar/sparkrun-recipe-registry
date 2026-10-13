# Qwen3 lane — `recipes/qwen3/`

_Brought to you by Little Cedar Group._

Shipped `sparkrun` recipes for the **Qwen3.8-27B** (SGLang, single DGX Spark) family.
All run on NVIDIA DGX Spark (GB10, 128 GB unified memory), TP=1 unless stated. The four
Qwen3-VL embedding/reranking recipes moved to their own lanes on 2026-10-10:
[`recipes/embed/`](../embed/README.md) and [`recipes/rerank/`](../rerank/README.md).

> Working here? Read [`AGENTS.md`](AGENTS.md) first — it is the lane's durable guide (traps,
> knob rationale, negative results, validation ritual). The deep research record is archived in
> [`attic/qwen3/`](../../attic/qwen3/) with a manifest. This README is the human-facing summary.

## Recipes

| recipe | runtime | model | flags | C1 t/s | notes |
|---|---|---|---|---|---|
| `qwen3.8-27b-nvfp4-dflash2-sglang` | sglang | [RadixArk/Qwen3.8-27B-NVFP4] + [incoai/Qwen3.8-27B-DFlash2] draft | 🌲🚀👀 | **33.8** | **shipping.** DFLASH2 spec decode, block 8. Decode-only, d=0, c=1. |
| `qwen3-coder-next-int4-autoround-vllm` | vllm | [Intel/Qwen3-Coder-Next-int4-AutoRound] | 🌲🚀 | **71.7** | Measured 2026-10-11, `benchmarking/decode-triage.yaml`: **71.7 t/s @ d0** (σ 0.2, n=5) and 67.8 @ d8k (σ 0.1) — **2.1× the DFlash2 lane's C1**, the lane's fastest decode by a wide margin. Serve line pinned to the prepared snapshot (`79c8a6bb`, `--revision=79c8a6bb` literal — see the recipe for why). No accuracy measurement yet; the keep call follows the quality pass. |

Flags: 🚀 fast (≥ 50 t/s) · 🌲 lcg_favorite · 👀 vision.

### Paired house-battery quality (2026-10-11, `tools/quality-battery.py`, n=1)

The lane had **no quality numbers at all** before this pass. Same instrument, same window, one paired
boot per arm:

| arm | easy | hard | total | C1 t/s |
|---|---|---|---|---|
| `qwen3.8-27b-nvfp4-dflash2-sglang` (shipping) | 19/19 | **18/18** | **37/37** | 33.8 |
| `qwen3-coder-next-int4-autoround-vllm` | 19/19 | 16/18 | 35/37 | **71.7** |

coder-next's two misses are `hard-arith-1` and `hard-arith-2` — both multi-step arithmetic; everything
else, including the format/trick/code tiers, is clean on both arms. 35/37 at 2.1× the decode speed is a
**role split, not a loser**: DFlash2 stays the quality reference (37/37), coder-next is the speed/coder
arm. Both keep their place — no attic move is warranted (nothing is dominated on both axes).

Flags note: `no accuracy evaluation yet` on the coder row is now discharged.

### Archived to [`attic/qwen3/`](../../attic/qwen3/)

- `qwen3.8-27b-nvfp4-nospec-control-sglang.yaml` — the plain-decode control (12.56 t/s at c=1).
  Copy it back into this lane to re-run a spec-vs-nospec comparison; the pairing rule is in
  [`AGENTS.md`](AGENTS.md) §6.
- `qwen3.8-27b-nvfp4-dspark-sglang.yaml` — the DSpark draft arm, measured 2026-10-10 and **not an
  upgrade** (28.5 vs 33.8 t/s).
- `QWEN3-MODEL-OPTIMIZATION-WORK.md`, `DEPTH-COST.md`, `SSM-STATE-DTYPE.md`,
  `ANSWERED-QUEUES.md`, `NOTES.md` — the research record. Cite by `§N`; the section numbers were
  not renumbered.

## Qwen3-Coder-Next — the empty-`content` trap (2026-10-11)

Measured on the pinned eugr vLLM: with the model's native thinking ON, a short reply comes back
in the **reasoning** channel and `content` stays `null` — the `qwen3` reasoning parser never sees a
closing think tag. A client that reads `content` (the house battery, most OpenAI SDK callers) sees an
empty reply: the house battery scored **0/19 + 0/18 on empty strings** while `/v1/completions`
answered the same prompt correctly (`391`). The recipe now ships
`--default-chat-template-kwargs '{"enable_thinking": false}'`, so the default surface answers in
`content`; a caller wanting the scratchpad opts back in per request with
`chat_template_kwargs {"enable_thinking": true}`. **Do not measure this lane without that knob** —
and record the `finish_reason` + `reasoning` histogram beside any score (repo rule G3/G4).

## Qwen3.8-27B — what the numbers mean

- **The model is dense, so it is a streaming-bandwidth problem, not a gather problem.** 64 layers = 48
  GDN (linear-attention) + 16 full-attention, no experts. Every weight is read every token:
  **17,608 MB/token** of weights, against ~**221 GB/s** effective read → a plain-decode ceiling of
  **~14 tok/s** at TP=1 (`VERIFIED`). Every published throughput is that ceiling times speculative
  amplification (`tok/s ≈ A_eff × BW / B_token`).
- **Speculative decoding is where the speed is.** The DFLASH2 draft raises decode to **33.8 t/s** at
  block 8 (d=0, c=1). Block 8 vs block 4 is **+22.5 %** ([1.188, 1.262]), pooled over 24 boots — the
  recipe ships block 8 because the draft was *trained* at 8.
- **`max_num_seqs: 48` in the recipe is a deliberate artifact.** The mamba/GDN state pool silently
  clamps it to **21** on a fresh container (`K=85`) — the clamp is logged, not an error. Read the grant
  from the server log (`grep -F 'capped to'`) rather than trusting the literal.
- **Long context costs decode.** At `c=8`, depth above ~8k is **~20 %** slower (congested/pool-limited;
  boot-level 8–29 %); uncongested at `c=4` the cost is **~11 %**. Do not quote a KV-bandwidth figure
  (four were retracted).
- **`mamba_ssm_dtype: bfloat16` doubles granted concurrency** (21 vs the checkpoint's declared
  `float32`'s 10) and is bit-identical on the state-read path. This is a deliberate override of the
  checkpoint; see [`AGENTS.md`](AGENTS.md) §4. Do not "restore float32 for safety".

## Notes

- **Evidence docs are archived** at [`attic/qwen3/`](../../attic/qwen3/) (2026-10-11; manifest in the
  same directory — search `ANSWERED-QUEUES.md` by profile name before running anything).
- **Guards:** `tests/test_qwen3_vl_embeddings.py` covers the moved VL recipes in the
  `embed`/`rerank` lanes. There is no test for the 27B lane yet.
- **Raising a bug upstream?** Name the pinned container commit you read and cite `file.py:line`
  (`AGENTS.md` and the archived docs do this throughout).

<!-- Links -->
[RadixArk/Qwen3.8-27B-NVFP4]: https://huggingface.co/RadixArk/Qwen3.8-27B-NVFP4
[incoai/Qwen3.8-27B-DFlash2]: https://huggingface.co/incoai/Qwen3.8-27B-DFlash2
[Intel/Qwen3-Coder-Next-int4-AutoRound]: https://huggingface.co/Intel/Qwen3-Coder-Next-int4-AutoRound