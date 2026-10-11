# Explore lane

Frontier reasoning + tool-calling models that push the frontier on DGX Spark, chosen by the
registry's selection weighting (**node count → speed → accuracy → memory**). No recipe cap (owner
decision 2026-10-11). Full candidate research — 8 families, five corrections to the earlier
`mad-science/EXPLORE-CANDIDATES.md`, per-candidate verification checklists — is in
[`EXPLORE-MODELS-RESEARCH.md`](EXPLORE-MODELS-RESEARCH.md).

| recipe | runtime | model | nodes | C1 t/s | status |
|---|---|---|---|---|---|
| [`nemotron-3.5-lightning-30b-nvfp4-dspark-vllm.yaml`](nemotron-3.5-lightning-30b-nvfp4-dspark-vllm.yaml) | vLLM | [nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4][nem] + [DSpark draft][nemd] | 1 | **77.7** | **BOOT-VERIFIED 2026-10-11** |
| [`ling-3.0-flash-int4-dspark-sglang.yaml`](ling-3.0-flash-int4-dspark-sglang.yaml) | SGLang | [inclusionAI/Ling-3.0-flash-int4][ling] + [DSpark draft][lingd] | 1 | **45.5** | **BOOT-VERIFIED 2026-10-11** (quality 37/37; C1 measured; DSPARK engagement unconfirmed) |

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
  the `ling3` parser — no empty-content trap on this template). **Boot-log caveat:** sglang warns
  `rope_scaling missing 'factor', defaulting to 1.0` — before trusting the advertised 262 k window
  on this checkpoint, confirm the context extension is real (a needle probe at depth), since a
  defaulted factor of 1.0 means "no extension applied".
- **Quality: 37/37** (`tools/quality-battery.py`, one boot) — 19/19 easy + 18/18 hard, **zero
  failures**. That ties ornith and qwen3.8-27B DFlash2 at the top of the pass.
- **Measured C1: 45.5 t/s @ d0** (σ 5.5, n=5) and 32.3 @ d8k (σ 8.2) on `decode-triage.yaml` —
  well below the third-party ~83 t/s. **DSPARK engagement could not be confirmed**: the
  `decode-triage` run's `--fresh` boot replaced the pre-existing serve (same intent id) and destroyed
  the serve log, so no acceptance-length evidence was retained; 45.5 sits between the third-party
  plain-NEXTN baseline (37) and its DSPARK figure (83) — exactly the ambiguity an unconfirmed draft
  leaves. Re-boot with the serve log retained before quoting this as a spec-decode number.
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