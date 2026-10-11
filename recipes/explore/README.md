# Explore lane

Frontier reasoning + tool-calling models that push the frontier on DGX Spark, chosen by the
registry's selection weighting (**node count → speed → accuracy → memory**). No recipe cap (owner
decision 2026-10-11). Full candidate research — 8 families, five corrections to the earlier
`mad-science/EXPLORE-CANDIDATES.md`, per-candidate verification checklists — is in
[`EXPLORE-MODELS-RESEARCH.md`](EXPLORE-MODELS-RESEARCH.md).

| recipe | runtime | model | nodes | C1 t/s | status |
|---|---|---|---|---|---|
| [`nemotron-3.5-lightning-30b-nvfp4-dspark-vllm.yaml`](nemotron-3.5-lightning-30b-nvfp4-dspark-vllm.yaml) | vLLM | [nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4][nem] + [DSpark draft][nemd] | 1 | **77.7** | **BOOT-VERIFIED 2026-10-11** |
| [`ling-3.0-flash-int4-dspark-sglang.yaml`](ling-3.0-flash-int4-dspark-sglang.yaml) | SGLang | [inclusionAI/Ling-3.0-flash-int4][ling] + [DSpark draft][lingd] | 1 | **45.5** | **BOOT-VERIFIED 2026-10-11** (quality 37/37; DSPARK engaged, accept len 2.73) |

## Measured

- **77.7 t/s @ d0** (σ 9.8, n=5) and 76.3 @ d8k (σ 26.0) on `benchmarking/decode-triage.yaml`, TP=1,
  20.8 GB NVFP4 weights. The DSpark draft engages: **acceptance length 3.67 at an 88.9% acceptance
  rate**. The 93–96 t/s third-party figure was not reproduced on our node — quote ours.
- **Quality: 33/37** (`tools/quality-battery.py`, one boot, 2026-10-11) — 18/19 easy + 15/18 hard.
  Misses: `wp-3`, `hard-arith-1`, `hard-arith-2`, `trick-3`. For scale against the other lanes in this
  pass: ornith 37/37 and qwen3.8-27B DFlash2 37/37 (both single-node, ~100 / 33.8 t/s), coder-next
  35/37 at 71.7 t/s. Nemotron is the fastest measured quality arm below ornith and pays ~4 tasks for it.

### Ling-3.0-flash-int4 (2026-10-11)

- **BOOT-VERIFIED** on one node: DSPARK configured with the external 1.36B draft and the KDA
  ReplaySSM verify path; answers correctly in `content` (`391` for 17×23, reasoning split cleanly by
  the `ling3` parser — no empty-content trap on this template).
  **Long context (needle-probed 2026-10-11):** the `rope_scaling missing 'factor'` boot warning is
  **benign** — the checkpoint declares no scaling at all (`rope_scaling: null`, native 262,144,
  rope_theta 6e6), so SGLang's 1.0 default is a no-op and the native window is real: a verbatim
  needle is retrieved at 8k, 64k (depths 10/50/100) and 150k tokens. **But 262k is not servable on
  this boot**: at `mem-fraction-static 0.75` the KV pool holds **176,203 tokens**, and a 200k
  request is auto-truncated to 176,197 and then fails HTTP 500 OOM (`--allow-auto-truncate` masks
  the truncation, not the OOM). The third-party notebook's 0.87 rung reported a 576,930-token pool,
  so reaching the advertised window means raising mem-fraction toward the documented OOM-risk
  ceiling. Receipts: `~/benchmarks/ling-needle-20261011/` on the head node.
- **Quality: 37/37** (`tools/quality-battery.py`, one boot) — 19/19 easy + 18/18 hard, **zero
  failures**. That ties ornith and qwen3.8-27B DFlash2 at the top of the pass.
- **Measured C1: 45.5 t/s @ d0** (σ 5.5, n=5) and 32.3 @ d8k (σ 8.2) on `decode-triage.yaml`.
  **DSPARK engagement CONFIRMED on a retained boot**: SGLang decode lines report
  `accept len: 2.73, accept rate: 0.22` — that is an **engagement proof** (accept len > 1 means the
  draft works), read off a single short decode request. **Steady state under real decode load**
  (4 concurrent ~400-token generations): **accept len 3.64–3.73, accept rate 0.29–0.34**, aggregate
  gen throughput up to 116.7 t/s. So the draft genuinely works, but steady-state acceptance sits
  below the third-party port's 5.2–6.4 — and that difference DOES arithmetically account for most
  of the C1 gap (45.5 × 5.8/3.5 ≈ 75, against their ~83): same recipe flags, different acceptance.
  Whether their higher acceptance is prompt-mix, engine build, or tuning is untested.
- Third-party (not reproduced here): ~83 t/s C1 with DSPARK, GPQA-D 83.65 on the INT4 column.

## Next by the ranking

`inclusionAI/Ling-3.0-flash-int4` (~77 GB + draft, 83 t/s C1 third-party, GPQA-D 83.65 on the INT4
column, first-party Spark notebook) is downloading; then `Aleph-Alpha/Kolibri-1` FP8 (~75 GiB,
AIME-25 96.9 / BFCL v4 61.4) and `vllm-sr/d3-edge`. All are single-node TP=1 candidates.

## Serving traps this lane hit (all fixed in the recipe)

1. `vllm/vllm-openai` images declare `ENTRYPOINT ["vllm","serve"]` → `executor_config: {entrypoint: ""}`.
2. The speculative config must live in `defaults.speculative_config` (referenced `'{speculative_config}'`),
   or sparkrun never distributes the draft and the offline engine dies resolving it.
3. `--default-chat-template-kwargs '{"enable_thinking": false}'`, or short replies land in the
   reasoning channel with `content: null`.

[nem]: https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4
[nemd]: https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4-DSpark
[ling]: https://huggingface.co/inclusionAI/Ling-3.0-flash-int4
[lingd]: https://huggingface.co/inclusionAI/Ling-3.0-flash-dspark