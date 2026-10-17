# Qwen3 lane — `recipes/qwen3/`

_Brought to you by Little Cedar Group._

Shipped `sparkrun` recipes for the **Qwen3.x** family on NVIDIA DGX Spark (GB10, 128 GB unified
memory), TP=1 unless stated. This README covers **shipped recipes only**: repo ids, sizes, flags, the
non-obvious knobs, and licenses. Everything else — lane state, traps, knob rationale, negative
results, measurement histories, boot receipts, the validation ritual, and the research docs — lives in
[`attic/qwen3/`](../../attic/qwen3/), including the lane's former `AGENTS.md`, and is indexed at the
bottom of this file. The four **Qwen3-VL** embedding/reranking recipes moved to their own lanes on
2026-10-10: [`recipes/embed/`](../embed/README.md) and [`recipes/rerank/`](../rerank/README.md).

## Contents

- [`qwen3.8-27b-nvfp4-dflash2-sglang`](#qwen38-27b-nvfp4-dflash2-sglang) — shipping; Qwen3.8-27B NVFP4 + DFLASH2 spec decode (SGLang)
- [`qwen3-coder-next-int4-autoround-vllm`](#qwen3-coder-next-int4-autoround-vllm) — Intel/Qwen3-Coder-Next int4 (vLLM); the lane's fastest decode
- [`qwen3.8-27b-mlx4bit-tensorfold-sglang`](#qwen38-27b-mlx4bit-tensorfold-sglang) — MLX 4-bit TensorFold engine behind the `runtime: sglang` shim
- [Flags](#flags)
- [Attic index](#attic-index)

### qwen3.8-27b-nvfp4-dflash2-sglang

| | |
|---|---|
| recipe | `qwen3.8-27b-nvfp4-dflash2-sglang.yaml` |
| runtime / container | SGLang (`lmsysorg/sglang:dev-cu13@sha256:0a1ba33aa4e0…`, digest-pinned — the tag is rebuilt upstream) |
| model | [RadixArk/Qwen3.8-27B-NVFP4] — NVFP4 quant of `Qwen/Qwen3.8-27B`, 17.6 GB weights, qwen3_5 dense hybrid, image-text-to-text |
| draft | [z-lab/Qwen3.8-27B-DFlash2] — DFLASH2 spec decode, block 8 |
| size / mem / TP | 27B dense (64 layers = 48 GDN + 16 full-attention, no experts); `gpu_memory_utilization: 0.85`; TP=1 and **TP=2 both measured** (2026-10-15): with the shipped fix mounted, `-o tensor_parallel=2` boots and serves on two nodes — decode C1 46.8 / C2 79.2 / C5 117.7 / C10 120.3 t/s, ~+48 %/+46 %/+23 %/+27 % over TP=1 (`bench_a09eb0ce2b85`, receipt `~/benchmarks/qwen3-27b-tp2-20261015/`); the *unfixed* loader cannot boot the model at TP=2 (attic `AGENTS.md` §7, §14); 262,144 ctx declared and **reachable on the shipped chain** (KV pool 497,878 tokens, top rung of the needle probe served as a 256,650-token prompt) |
| flags | 🌲🚀👀 (fast, lcg_favorite, vision) |
| decode C1 | **33.8 t/s** @ d=0, c=1 (block 8, decode-triage) — the arm's historical reference, measured with the weight loader **unfixed** (house battery 37/37) |
| decode ladder | **C1 31.7 ± 3.0 · C2 54.3 ± 4.2 · C5 95.5 ± 6.8 · C10 94.5 ± 4.6 t/s** @ d=0, pp 2048, tg 128, n=5, shipped boot, 2026-10-15 — `bench_017bdc06394d` (a `--fresh` re-measurement: the same bench id also covers the earlier partial-patch probe boot, whose artifacts live in the receipt's `partial-patch-probe/`) |
| decode ladder (re-measure) | **C1 29.6 ± 2.6 · C2 57.4 ± 3.3 · C5 89.5 ± 6.5 · C10 100.9 ± 3.4 t/s** @ d=0, pp 2048, tg 128, n=5, shipped chain, one GB10, 2026-10-17 — `bench_355eee9f476f`, receipt `~/benchmarks/ladders-solo-20261017/` (the index row's C2/C5/C10 quote this boot; the two boots' spread — up to 11 % at C10, the widest cell — sits inside this profile's documented 7–25 % inter-boot noise floor, so neither is "the" number and the row's C1 33.8 stays the arm's **pre-loader-fix** triage reference) |
| suite (2026-10-15) | eval-suite 1.0.1 verdict `ok`: contract ok (served id is the HF repo id, 262,144 ctx); house **37/37**; needle **3/3** at 32k, 131k, and 262k (the top rung is a 256,650-token prompt, i.e. the declared window really is served); hard ARC **93.5 %** (187/200) and GSM8K **96.0 %** (192/200, `finish_reason` stop 198 + length 2, no empty replies); BFCL v3 **87.7 %** (1087/1240) |
| tool score (2026-10-15) | tool-eval-bench v2.6.0, core 15, greedy, 8 turns, sequential: **14 pass, 1 partial (TC-14), 0 fail → score 97** (29/30 points) — `bench_a8fa9f246154` |
| receipt | `~/benchmarks/qwen3-27b-suite-20261015/` on the head — `launch.log`, `provenance.txt`, `summary.json`, `bfcl.json`, `hard/`, `needle-*.json`, `perf-ladder.*`, `teb.*`; SGLang `dev-cu13` image `sha256:c802d7b6…`, checkpoint `319f741c…`, draft `z-lab@50307d4c…` |
| license | Apache-2.0 (checkpoint and draft) |

Non-obvious knobs (full rationale in [`attic/qwen3/AGENTS.md`](../../attic/qwen3/AGENTS.md) §4):

- **`max_num_seqs: 48` is exactly what the shipped chain grants, but never read the grant from the
  literal.** With the weight-loader fix mounted the mamba/GDN state pool does not clamp it (`K=252` →
  63 slots, so 48 is granted in full); the *same* literal was silently clamped to **40** (`K=161`,
  then `K=163`) on every boot whose loader stranded its device staging buffer, and the recipe's own
  historical figure was **21** (`K=85`) on the 2026-09-19 image. Measured 2026-10-15 across three
  boots of one node; the receipt above carries all three.
- **The shipped mods chain is what makes that grant possible.**
  `@littlecedar/mods/fix-fastsafetensors-tp2-sglang` patches SGLang's fastsafetensors loader in
  place: the device-selection half matters at TP>1, and the staging-buffer-release half frees ~21 GB
  on the target's weight load and ~3.6 GB on the draft's at TP=1 too (41.90 → 20.59 GB, and 7.41 →
  3.78 GB), which is what doubles the KV pool (221,836 → 497,878 tokens). The patch is anchor-checked
  and **fails closed**: a future `dev-cu13` that moves the code aborts the launch with the mod's own
  message rather than silently reverting to the leaky loader.
- **`mamba_ssm_dtype: bfloat16` deliberately overrides the checkpoint's declared float32**: it halves
  the per-slot state size, which is what doubles granted concurrency (21 vs 10 slots on the
  2026-09-19 image; the relative effect is the durable part) and is bit-identical on the state-read
  path. Do not "restore float32 for safety".
- **`mamba_full_memory_ratio: 3.51`** is the high-leverage, context-length-dependent knob; the optimum
  is interior (≈3.6 at 4k, ≈2.3 at 8k, ≈1.2 at 16k) and flipping it is a traffic-shape decision —
  **ask before changing it**. Those optima were measured under the loader that stranded ~21 GB, so
  they have **not** been retuned against the doubled pool: treat the ratio as re-checkable rather
  than settled.
- **`speculative_draft_tokens: 8`** is what the draft was trained for; any other value wins silently.
  `z-lab` and `incoai` drafts are the same weights (same blob), so a draft-provider A/B measures
  nothing — re-confirmed 2026-10-15, where the two repos' draft load lines read the same 7.41 GB
  under the same (unfixed) loader.
- **`kv_cache_dtype: auto`** keeps the checkpoint owning the KV dtype (it resolves to `fp8_e4m3`
  because the checkpoint's `hf_quant_config` says FP8).
- **`chunked_prefill_size: 4096`** is a scheduler token budget, **not** draft length.
- **`served_model_name` is a literal, never `{model}`**: sparkrun rebinds every `{model}` occurrence to
  the prepared snapshot path, so the engine would advertise a `/cache/…` path as its model id.
- A plain-decode control arm exists in the attic for a spec-vs-nospec comparison (12.56 t/s at c=1);
  the pairing rule is in attic `AGENTS.md` §6.
- **`mamba_radix_cache_strategy: extra_buffer_lazy` reuses non-obviously.** `cached_tokens` *grows*
  with repeat visits (a 128-token prefix: 1 absorb → 0, 2 → 64, 3 → 64, 4 → 128), so a warm-up that
  must read stored state has to absorb the prefix several times, and `prefix_caching: true` in a
  benchmark does not mean prefixes are shared on the first pass.
- **`extra_args` is the one-off experimentation escape hatch** (mirrors the qwen4 recipes): appended
  last so argparse lets a repeated flag win, with a quoted empty string as the no-op default.

### qwen3-coder-next-int4-autoround-vllm

| | |
|---|---|
| recipe | `qwen3-coder-next-int4-autoround-vllm.yaml` |
| runtime / container | vLLM (`ghcr.io/spark-arena/dgx-vllm-eugr-nightly@sha256:cc47adc1b210066dca421bdcd7ca6f16680b6579533f348c0d8c072da194cf98` — digest-pinned 2026-10-16, resolved from the boot that produced the ladder below) |
| model | [Intel/Qwen3-Coder-Next-int4-AutoRound] — int4 (group 128) AutoRound quant of `Qwen/Qwen3-Coder-Next` (11.8B, qwen3_next); revision pinned `79c8a6bb…` (literal `--revision=` in the serve line, see the recipe for why) |
| size / mem / TP | `gpu_memory_utilization: 0.85`; TP=1; 262,144 ctx; `load_format: instanttensor`, `max_num_batched_tokens: 8192` |
| flags | 🌲🚀 (fast, lcg_favorite) |
| decode C1 | **71.7 t/s** @ d0 (σ 0.2, n=5) and 67.8 @ d8k (σ 0.1) — 2.1× the DFlash2 arm, the lane's fastest decode |
| decode ladder (2026-10-16) | **C1 70.4 ± 0.2 · C2 114.0 ± 2.6 · C5 177.1 ± 14.9 · C10 249.5 ± 3.9 t/s** @ d0, pp 2048, tg 128, n=5 — `benchmarking/concurrency-ladder.yaml` on the pinned boot, decode rows read from the `--output` file (`~/benchmarks/pins-20261016/qwen3coder-ladder.{yaml,json}`). C1 here (70.4) vs the 71.7 above is the same shape re-measured on a different boot: 1.8 %, i.e. within inter-boot noise. C5's spread is the wide one. |
| tool score (2026-10-16) | tool-eval-bench **v2.6.0**, core 15, greedy, 8 turns, sequential, thinking enabled: **90/100 (27/30 points), ★★★★★ Excellent** — deployability 89, responsiveness 87 (median turn 0.8 s), error rate 0.0. The report's engine block pins the provenance of the new image digest: **vLLM 0.32.0rc1.dev301+g1ac942555.d20261016** inside `dgx-vllm-eugr-nightly@sha256:cc47adc1…`. Receipt `~/benchmarks/pins-20261016/qwen3coder-tools.{yaml,json}`, `bench_e8e91f06209d`. |
| quality | 35/37 house battery (misses `hard-arith-1`/`hard-arith-2`, both multi-step arithmetic) — the speed/coder arm to the DFlash2 quality reference |
| license | the Intel card declares none and defers to the base model `Qwen/Qwen3-Coder-Next` (**Apache-2.0**) |

**The non-obvious knob — the empty-`content` trap.** With the model's native thinking ON, a short
reply comes back in the **reasoning** channel and `content` stays `null` (the `qwen3` reasoning parser
never sees a closing think tag), which every client that reads `content` sees as an empty reply — the
house battery scored 0/19 + 0/18 on empty strings while `/v1/completions` answered the same prompt
correctly. The recipe therefore ships `--default-chat-template-kwargs '{"enable_thinking": false}'`;
a caller wanting the scratchpad opts back in per request with
`chat_template_kwargs {"enable_thinking": true}`. **Do not measure this lane without that knob** — and
record the `finish_reason` + `reasoning` histogram beside any score.

### qwen3.8-27b-mlx4bit-tensorfold-sglang

| | |
|---|---|
| recipe | `qwen3.8-27b-mlx4bit-tensorfold-sglang.yaml` |
| runtime / engine | the recipe's `runtime: sglang` is only the declaration that makes sparkrun render a `command:` template — the engine is **TensorFold v0.6.0** (its own engine, not SGLang/vLLM) plus five MiaAI-Lab patches, in the digest-pinned public image `ghcr.io/miaai-lab/qwen3.8-27b-dgx-spark-tensorfold@sha256:043d192b…` (patch set `fb91a0019fdc`) |
| model | [TensorFold/Qwen3.8-27B-MLX-4bit] — MLX affine-4-bit weights (~15 GB), 27.4B params, image-text-to-text |
| draft | [z-lab/Qwen3.8-27B-DFlash2] (~3.6 GB), declared so sparkrun stages it; the engine reads it from the node's HF cache |
| size / mem / TP | one DGX Spark, TP=1 (TP=2 is **not expressible** in this recipe — attic `AGENTS.md` §13); 262,144-token window; FP8 KV; image/video input |
| flags | 👀 (vision) |
| decode C1 | **41.3 ± 4.0 t/s** @ d0 and 41.7 ± 2.4 @ 8k (one boot, 2026-10-14 — treat as provisional); house battery **37/37** |
| standard suite (2026-10-17) | ladder @ d0 pp2048 tg128 n=5 — C1 **44.8** (σ 3.5) / C2 57.7 (σ 2.8) / C5 64.4 (σ 2.3) / C10 65.6 (σ 1.3) t/s (`bench_b10e422bb046`; per-request decode falls 44.8 → 16.0, so the aggregate flattens past c5); eval-suite ok on contract/house/needle/hard — house **37/37** (easy 19/19, hard 18/18), needle **3/3** at 32k and 131k (the engine reports no `max_model_len`, so the auto depths stop at 128k), arc **94.0%** / gsm8k **96.5%** (n=200 each); TEB **100** (15/15). Receipt `head:~/benchmarks/qwen3-tf-suite-20261017/` (+ `NOTES.md`). The **`tools` (bfcl) leg** was killed at 3,878 s on a misread buffered log and re-ran unbuffered into `head:~/benchmarks/qwen3-tf-tools-20261017/` (4,487 s): **85.7%** (1063/1240) — `simple` 90.5 / `multiple` 93.0 / `parallel` 85.5 / `parallel_multiple` 72.0 / `irrelevance` 83.3 (clean leg, `verdict ok`). That leg ran at bfcl-eval's **512-token completion default**: the suite's `check_tools` passed no `--max-tokens` at all until 2026-10-17, when it gained `--bfcl-max-tokens` (default 4096), and 25 of the 400 parallel questions came back with `calls: []`. Treat 85.7 % as **budget-annotated**, not a capability ceiling, and re-measure at 4096 before comparing it with an arm measured on the new default (`tools/README.md` §bfcl-eval.py). |
| license | Apache-2.0 (checkpoint); engine/patches are upstream's, kept under their licenses |

Non-obvious knobs and caveats (details in [`attic/qwen3/AGENTS.md`](../../attic/qwen3/AGENTS.md)
§12–§13):

- **`TENSORFOLD_KV_POOL_GIB` is a launch-time knob, not a recipe value.** Upstream's `KV_POOL_GB=auto`
  is a host-side computation in its `start.sh` (free memory minus ~31 GiB, capped at 78) that a static
  recipe cannot run, so the arm leaves the pool to the engine (caches grow on demand) and you pin it at
  launch with `sparkrun run … -e TENSORFOLD_KV_POOL_GIB=<n>` (the pinned image reads it; the engine
  refuses a pool that does not fit).
- **A trailing `#` comment in `command:` names `--served-model-name`, and must stay.** sparkrun's
  `sglang` shim appends its own `--served-model-name` to any template that declares
  `served_model_name`; TensorFold parses no such flag and the first boot died on
  `unrecognized arguments: --served-model-name`. The helper is a substring test, so the comment skips
  the append and the shell discards it. **Do not "tidy" it away — removing it stops the arm booting.**
- **`model_revision` pins distribution, not serving.** This engine has no revision flag (`{model}`
  reaches it as the prepared snapshot path), so `sparkrun recipe validate --strict` reports
  `unpinned-model-revision`; plain `validate` passes and is the repo's gate. Do not clear it by
  dropping the pin or by adding a flag the engine cannot parse.
- `TORCH_EXTENSIONS_DIR` points at sparkrun's runtime cache so the `sm_121a` kernel compile is paid
  once a node instead of once a boot; `executor_config.entrypoint: ""` clears the image's inherited
  entrypoint. TP=2 needs a launcher shim (the ds4 lane's pattern), not this recipe.
- **Upstream's engine env is preserved as-is**: `TENSORFOLD_NO_UPDATE_CHECK: '1'` (the engine's update
  check writes into `HOME` and calls GitHub), `TENSORFOLD_KV_DTYPE: fp8` (the opt-in FP8 attention
  cache, 32 KiB/token rather than 64), and `TENSORFOLD_MEMORY_RESERVE_GIB: '0'` (a 0 GiB startup
  reserve where TensorFold's own default is a tenth of RAM — raise it if the node is shared).
- **`parallel: 8`** streams decoded together; upstream measures no single-request cost up to 8.

### Flags

🚀 fast (≥ 50 t/s) · 🌲 lcg_favorite · 👀 vision.

## Attic index

[`attic/qwen3/`](../../attic/qwen3/) holds the lane's frozen record — the former lane guide, the
research docs, the retired arms, and the spec-metrics guard mod. Section numbers (`§N`) were **not**
renumbered on archival, so existing `§N` cites still resolve; the copies are frozen provenance — do
not tidy or re-edit them.

| file | what it holds / what question it answers |
|---|---|
| [`AGENTS.md`](../../attic/qwen3/AGENTS.md) | The lane's durable guide, moved verbatim from `recipes/qwen3/AGENTS.md` on 2026-10-14 with its `§N` numbering intact: the model thesis (§1–2), load-bearing constraints and traps (§3), why each shipped value is what it is (§4), the capacity model and its `depth + pp` divisor (§5), the archived control and its pairing rule (§6), negative results not to re-run (§7), open items (§8), where the evidence lives (§9), the validation ritual (§10), references (§11), and the TensorFold arm's strict-warning/flag-suppression and TP=2 runbook (§12–§13). Read this before touching a recipe here. |
| [`ARMS-MANIFEST.md`](../../attic/qwen3/ARMS-MANIFEST.md) | The archival manifest: which arms left the lane on 2026-10-11, why each was retired, and where its facts now live — the index of last resort when a `§N` cite needs a source. |
| [`QWEN3-MODEL-OPTIMIZATION-WORK.md`](../../attic/qwen3/QWEN3-MODEL-OPTIMIZATION-WORK.md) | Decision record (`WORK §N`): the dense-hybrid bandwidth model, the block 4→8 campaign, the pool/clamp analysis, the mamba pool + dtype threads, negative results, and the open-question queue at archive time. |
| [`DEPTH-COST.md`](../../attic/qwen3/DEPTH-COST.md) | The depth/ratio thread (`DEPTH-COST §12.NN`): the `usable = min(cap, #tokens // (depth + pp))` correction (§12.54), the c=8 vs c=4 depth-cost split, retractions marked inline — read its bottom line before quoting any depth figure. |
| [`SSM-STATE-DTYPE.md`](../../attic/qwen3/SSM-STATE-DTYPE.md) | The bf16-vs-fp32 recurrent-state probes (`SSM §12.NN`), the positive control, and the resolution limits of the claim — the evidence behind the shipped `mamba_ssm_dtype: bfloat16`. |
| [`ANSWERED-QUEUES.md`](../../attic/qwen3/ANSWERED-QUEUES.md) | Every closed question (`AQ item N`) with its verdict, cost, and why the wrong prediction looked right — **search by benchmark profile name before running anything**. |
| [`NOTES.md`](../../attic/qwen3/NOTES.md) | The lane's action-plan snapshot, drift list, and sprawl log at archive time. |
| [`qwen3.8-27b-nvfp4-nospec-control-sglang.yaml`](../../attic/qwen3/qwen3.8-27b-nvfp4-nospec-control-sglang.yaml) | Archived arm: the plain-decode control that supplies the denominator the DFlash2 recipe cannot produce on its own (12.56 t/s at c=1). Copy it back into this lane before a spec-vs-nospec run — pairing rule in `AGENTS.md` §6. |
| [`qwen3.8-27b-nvfp4-dspark-sglang.yaml`](../../attic/qwen3/qwen3.8-27b-nvfp4-dspark-sglang.yaml) | Archived arm: the DSpark draft, measured 2026-10-10 and **not an upgrade** (28.5 vs 33.8 t/s). Nothing here is served by the registry — do not re-add it. |
| [`mods/fix-sglang-spec-metrics-empty-verify/`](../../attic/qwen3/mods/fix-sglang-spec-metrics-empty-verify/) | The spec-metrics guard mod (anchored, idempotent SGLang patch with its own negative-control harness) that served the retired no-spec campaign; no shipped recipe mounts it, and it is the repo's convention exemplar for mod-local guard harnesses. |

What is no longer in `recipes/qwen3/`: the lane's measurement histories, boot receipts, A/B receipts,
quality-battery tables, and per-knob campaign notes — all of that is in the archived `AGENTS.md` and
the docs above. Guard: [`tests/test_qwen3_recipes.py`](../../tests/test_qwen3_recipes.py) covers the
TensorFold arm; the lane's SGLang arms are covered by
[`tests/test_recipe_placeholder_resolution.py`](../../tests/test_recipe_placeholder_resolution.py);
the moved VL recipes are covered by
[`tests/test_qwen3_vl_embeddings.py`](../../tests/test_qwen3_vl_embeddings.py).

<!-- Links -->
[RadixArk/Qwen3.8-27B-NVFP4]: https://huggingface.co/RadixArk/Qwen3.8-27B-NVFP4
[Intel/Qwen3-Coder-Next-int4-AutoRound]: https://huggingface.co/Intel/Qwen3-Coder-Next-int4-AutoRound
[TensorFold/Qwen3.8-27B-MLX-4bit]: https://huggingface.co/TensorFold/Qwen3.8-27B-MLX-4bit
[z-lab/Qwen3.8-27B-DFlash2]: https://huggingface.co/z-lab/Qwen3.8-27B-DFlash2
