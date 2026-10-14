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
| `qwen3.8-27b-mlx4bit-tensorfold-sglang` | sglang (TensorFold shim) | [TensorFold/Qwen3.8-27B-MLX-4bit] (MLX 4-bit) + [z-lab/Qwen3.8-27B-DFlash2] draft | 👀 | **41.3** | **booted + measured 2026-10-14** on `.30`, boot `fe3054ad67464c54_2d38dfc4605e`. A foreign engine behind the `runtime: sglang` shim (the ds4 lane's pattern); house battery **37/37**. Decode-only, d=0, c=1. |

Flags: 🚀 fast (≥ 50 t/s) · 🌲 lcg_favorite · 👀 vision.

### The TensorFold arm (`qwen3.8-27b-mlx4bit-tensorfold-sglang`, added 2026-10-14)

[TensorFold](https://github.com/ashhart/TensorFold) is **not** an SGLang or vLLM route: it is its own
engine, and the recipe's `runtime: sglang` is only the declaration that makes sparkrun render a
`command:` template (on one node it appends no rendezvous flags, so the template reaches the engine
unchanged). The upstream project is Mia's AI Lab's
[Qwen3.8-27B-DGX-Spark-TensorFold](https://github.com/MiaAI-Lab/Qwen3.8-27B-DGX-Spark-TensorFold):
TensorFold v0.6.0 (`c464617`) plus five patches — up to 50 images and video input, opt-in YaRN,
an FP8 attention cache, a 0 GiB memory reserve, and a KV pool pinned at startup — baked into the
public image `ghcr.io/miaai-lab/qwen3.8-27b-dgx-spark-tensorfold` (patch set `fb91a0019fdc`,
digest-pinned in the recipe). One DGX Spark, TP=1: MLX affine-4-bit weights (~15 GB), the DFlash2
drafter (~3.6 GB), a 262,144-token window, FP8 KV, and image/video input.

What the registry changed from the upstream launcher, and why:

- **Checkpoint id**: the upstream card names `Vontra/Qwen3.8-27B-MLX-4bit`; the Hub repo has moved to
  the **`TensorFold`** org (the old id 307-redirects), so the recipe pins the canonical id at the
  same commit.
- **Port 8000**, the lane's convention, where upstream serves 8888.
- **`TORCH_EXTENSIONS_DIR`** is moved into sparkrun's runtime cache (`/cache/runtime/…`): the image
  bakes `/cache/torch_extensions`, but `/cache` is a mount parent docker creates as root while
  sparkrun runs the container as the invoking uid, so the engine's `sm_121a` kernel compile could not
  write there. As set, the compile is paid once a node instead of once a boot.
- **The drafter is declared** (`speculative_draft_model` + its own revision) so sparkrun stages it in
  the node's HF cache the way it stages the checkpoint. `TensorFold --drafter` reads it from there;
  an undeclared drafter leaves the offline engine without one.
- **The KV pool is left to the engine** (caches grow on demand). Upstream's `KV_POOL_GB=auto` is a
  host-side computation in `start.sh` — free memory at start minus ~31 GiB, capped at 78 — which a
  static recipe cannot run. To pin it, pass it at launch:
  `sparkrun run … -e TENSORFOLD_KV_POOL_GIB=78` (the engine refuses a pool that does not fit).

Upstream's own measurements (its `sparkDash` benchmark, one Spark): **58.3 t/s** decode single-stream
on prose and **136.9** on code, **220.6 / 323.2 t/s aggregate at 8 clients**, and 1,793 tok/s prefill
at 8k. Those are the upstream project's numbers, not this registry's, and its own fixed-seed rerun
reads lower on a different prompt/counting setup — so do not put them beside this lane's
`decode-triage` C1 column. This arm's own boot and measurements are below.

### Measured 2026-10-14 — boot, C1, and house battery

First registry boot of the arm, one node (`.30`), the recipe as shipped except for the one required
correction below. **Boot receipt** `fe3054ad67464c54_2d38dfc4605e`: `GET /v1/models` →
`{"id": "Qwen3.8-27B", "owned_by": "tensorfold"}` (not a `/cache/…` path), TTR port-open **71.5 s**,
TTFT 98.7 s. The serve log shows the TensorFold startup estimate (**37.77 GiB within 116.72 GiB**),
the `sm_121a` kernel builds (`tensorfold_qmm_v3`, `tensorfold_gdn_v2`,
`tensorfold_prefill_attention_v1`), and `serving Qwen3.8-27B at http://0.0.0.0:8000/v1 … drafts: on;
context: 262144; loaded in 70.2s`. The drafter `z-lab/Qwen3.8-27B-DFlash2` was staged at its pinned
commit `50307d4c…`, and the serving line reports **`drafts: on`**. The KV pool was left to the
engine (the recipe default; `TENSORFOLD_KV_POOL_GIB` is unset → grow on demand, "up to 8 streams");
`-e TENSORFOLD_KV_POOL_GIB=<n>` pins it (`tensorfold/cuda/kv_fp8.py` in the pinned image reads it).

`benchmarking/decode-triage.yaml` — bench `30c35dc7ade7`, `--skip-run --no-stop`, c=1, runs=5, the
served name resolved to `Qwen3.8-27B`:

| depth | tg t/s (decode-phase mean ± σ) | ttfr |
|---|---|---|
| 0 | **41.3 ± 4.0** | 6.2 ms |
| 8192 | **41.7 ± 2.4** | 23.5 ms |

Read the decode-phase records only: the d=8192 cell also emits a context-prefill record (tg 37.5,
`is_context_prefill_phase: true`) that must not be pooled. **At c=1 this arm out-decodes the
DFlash2 arm (41.3 vs 33.8 t/s) at no depth penalty from 0→8k** — the mirror image of the coder arm's
trade (41.3 here is *below* coder-next's 71.7, so the lane's speed arm is unchanged). One boot only,
σ 4.0 > the DFlash2 arm's spread, so treat 41.3 as provisional until a second boot.

House battery (`tools/quality-battery.py --tier both --max-tokens 2048`, n=1, thinking on):
**37/37** (19/19 easy + 18/18 hard) — ties the DFlash2 reference arm. The server returns the answer
in `content` and the think block in `reasoning_content`, so the battery's `content` read is not the
empty-content trap; the tool's 384-token default is nonetheless too small for a thinking model.

**The one correction the boot required.** As authored the first boot died instantly with
`tensorfold: error: unrecognized arguments: --served-model-name Qwen3.8-27B`: sparkrun's `sglang`
shim appends its own `--served-model-name` to any `command:` template that declares
`served_model_name` (`runtimes/base.py::_augment_served_model_name`), and TensorFold has no such flag
(it spells the id `--name`). The command now names the flag in a trailing comment — the helper's
substring check then skips the append, and the line is a shell comment so the engine never sees it.
See [`AGENTS.md`](AGENTS.md) §12.

Staged boot (one free node; render first, then launch):

```bash
H=$PWD/.local/sparkrun-home
HOME="$H" sparkrun run @littlecedar/qwen3.8-27b-mlx4bit-tensorfold-sglang -H .34 -n
HOME="$H" sparkrun run @littlecedar/qwen3.8-27b-mlx4bit-tensorfold-sglang -H .34
```

The first boot builds the `sm_121a` CUDA extensions and loads ~19 GB of weights — measured TTR
port-open **71.5 s** on `.30`, so the kernel build is not the slow part. `readiness` gives it 3600 s
before the port has to open. Three knowns: plain `validate` passes with the strict-only
`unpinned-model-revision` warning (this engine has no revision flag — it is handed the prepared
snapshot path; see [`AGENTS.md`](AGENTS.md) §12); **TP=2 is not expressible** in this recipe (§13);
and the launch logs a non-fatal `Could not install SGLang FP8 tuning configs` (the sglang runtime's
tuning-sync step against a non-SGLang image) — it does not block the serve.

Guard: [`tests/test_qwen3_recipes.py`](../../tests/test_qwen3_recipes.py).

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
  `embed`/`rerank` lanes; `tests/test_qwen3_recipes.py` guards the TensorFold arm (engine identity,
  digest pin, drafter, served id). The lane's SGLang arms are covered by
  `tests/test_recipe_placeholder_resolution.py` (served-name rebinding, inert defaults).
- **Raising a bug upstream?** Name the pinned container commit you read and cite `file.py:line`
  (`AGENTS.md` and the archived docs do this throughout).

<!-- Links -->
[RadixArk/Qwen3.8-27B-NVFP4]: https://huggingface.co/RadixArk/Qwen3.8-27B-NVFP4
[incoai/Qwen3.8-27B-DFlash2]: https://huggingface.co/incoai/Qwen3.8-27B-DFlash2
[Intel/Qwen3-Coder-Next-int4-AutoRound]: https://huggingface.co/Intel/Qwen3-Coder-Next-int4-AutoRound

[TensorFold/Qwen3.8-27B-MLX-4bit]: https://huggingface.co/TensorFold/Qwen3.8-27B-MLX-4bit
[z-lab/Qwen3.8-27B-DFlash2]: https://huggingface.co/z-lab/Qwen3.8-27B-DFlash2