# Liquid AI lane

Liquid AI's LFM3 family and its `d1-*` system-one siblings: small (1.7B–2.2B) edge models with a
**hybrid `conv` + `sliding_attention` + `full_attention`** stack, shipped as `transformers`
custom-code architectures (`auto_map` → `trust_remote_code` required) with vendor GGUF mirrors
carrying LEAP quantization metadata.

**One arm ships, booted and measured 2026-11-07.** `LFM3-1.7B` runs on llama.cpp from the
vendor's Q4_K_M GGUF (§Arms, §Measurement): c1 137.51 tg t/s, house 93, and the boot was the
engine-support test that mattered — the pinned image loads `lfm3`. A bf16 vLLM arm was authored
and retired the same day, because the pinned vLLM predates the architecture (§Engine routes).
The remaining collection members are queue rows in `mad-science/queue.json`.

## Roster — the `LiquidAI/lfm3` collection, read 2026-11-02

| repo | params | `model_type` | task | GGUF mirror |
|---|---|---|---|---|
|`LiquidAI/LFM3-1.7B-Base`|1728.8M|`lfm3`|text-generation|— (fine-tune target)|
|`LiquidAI/LFM3-1.7B`|1728.8M|`lfm3`|text-generation|`LFM3-1.7B-GGUF` — Q4_K_M 1.1 GB … BF16 3.5 GB|
|`LiquidAI/LFM3-VL-2B`|1918.2M|`lfm3_vl`|image-text-to-text|`LFM3-VL-2B-GGUF`|
|`LiquidAI/LFM3-Audio-2B`|2002.3M|`lfm3_audio`|any-to-any (ASR + TTS)|`LFM3-Audio-2B-GGUF`|
|`LiquidAI/LFM3-Omni-2B`|2166.9M|`lfm3_omni`|any-to-any (vision + audio)|`LFM3-Omni-2B-GGUF`|
|`LiquidAI/d1-Omni-2B`|2166.9M|`lfm3_omni`|audio-text-to-text, `AutoModel` — system-one decision|`d1-Omni-2B-GGUF`|
|`LiquidAI/d1-2B`|1918.2M|`lfm3_vl`|image-text-to-text, `AutoModel` — system-one decision|`d1-2B-GGUF`|

`d1-*` are **not chat models**: they are `AutoModel` system-one scorers (tags `decision`,
`calibration`, `feature-extraction`) fine-tuned from `LFM3-VL-2B` / `LFM3-Omni-2B`. They belong to
this lane by family and to the **decision lane** by instrument — measure them with the decision
lane's prefill-only ladder (`tools/jev-decision-bench.py`, `recipes/decision/README.md`), not with
`llama-benchy`, which will find no chat completion to drive.

## Architecture, from `LFM3-1.7B/config.json` (read 2026-11-02)

24 layers, hidden 2048, 16 heads / 4 KV heads, `head_dim` 128, vocab 128,000, 262,144-token
context, `tie_word_embeddings`, sandwich norm, `transformers_version` 5.12.1. The stack is
**hybrid, not transformer-uniform**: `conv` layers with a 7-slot cache, `sliding_attention` at
window 256, and `full_attention` — the shipped pattern is `conv, conv, full, conv, sliding, …`,
i.e. 13 conv + 6 full + 5 sliding. Consequences an operator will otherwise trip on:

- **`trust_remote_code` is mandatory.** The repo ships `configuration_lfm3.py` / `modeling_lfm3.py`
  via `auto_map`; a server that refuses remote code cannot load the arm at all.
- **KV cache is not the whole cache.** Conv state is per-layer and fixed-size, so the usual
  `mem-fraction-static` × context heuristic over-estimates reserve and under-estimates the
  non-KV state. Measure the resident footprint; do not compute it from the text config.
- **Custom architecture means engine support is a boot gate, not an assumption.** A `lfm3*`
  `model_type` must exist in the shipping engine: llama.cpp support is *evidenced* by the vendor
  publishing GGUFs (LIKELY, not verified for the fleet's resident image commit), and vLLM/SGLang
  support for `lfm3` is **unverified** — LFM2 was upstream in vLLM, LFM3 has not been checked here.

## License posture — `license: other`, LFM Open License v1.0

All seven repos carry `license: other`; the GGUF mirror's `LICENSE` file is **LFM Open License
v1.0**, Liquid AI's own terms with the usual use/control definitions. That is a license class this
registry had not shipped, so per `AGENTS.md` ("a new license class goes to the register first") the
ship posture went to the owner rather than a lane — **ruling 2026-11-02: ship as ordinary arms**,
no eval-only banner, recorded as `mad-science/QUESTIONS.md` `#56` (settled, in
`mad-science/TODO.md` §"Settled questions"). A *published fine-tune* is still a redistribution under
Liquid's own terms, which is `finetuning/`'s business and not a recipe flag.

## Instruments — one per modality, and they are not interchangeable

A 1.7B text model, a VL shim, an ASR/TTS model and an omni model do not share a ladder. The lane
picks the instrument the deliverable needs: `benchmarking/llama-benchy/*` and
`benchmarking/standard-suite.yaml` for the text and VL arms; the media lane's WER instrument (the
`Cactus-Compute/whistle` needle route, `recipes/media/README.md`) for `LFM3-Audio-2B`, with the
open TTS leaderboard as the external reference; and the decision ladder for `d1-*`. Reporting a
`C1 t/s` from an audio model would be a category error, not a measurement.

## Arms — measured 2026-11-07

| recipe | engine / pin | weights | result |
|---|---|---|---|
|[`liquidai-lfm3-1.7b-q4km-llamacpp.yaml`](liquidai-lfm3-1.7b-q4km-llamacpp.yaml)|llama.cpp — the registry's own arm64/sm_121 build at upstream `6023692` (2026-11-05), `ghcr.io/littlecedar/dgx-spark-llama-cpp:upstream-6023692-cu130@sha256:f2579b80…`, built by `llamacpp-engine` run 42361240306|vendor Q4_K_M GGUF, 1,099,627,808 B|**loaded and served `lfm3`** (no unknown-arch), ladder and house below|

It ships as an **ordinary arm**, not eval-only: LFM Open License v1.0 (`license: other`) went to
the owner rather than a lane, and the 2026-11-02 ruling (`mad-science/QUESTIONS.md` `#56`) is ship
ordinary — §License posture above. It is booted and measured (§Measurement); the root index's
C1–C10 for the row stay `—` anyway, because this arm serves one slot and its `c > 1` cells time
queuing, not concurrency — a number there would not be the index's shape.

**The arm does not use the resident scitrera pin, and that is a finding, not a preference.**
`scitrera/dgx-spark-llama-cpp:b10549-cu131` carries llama.cpp `b2e5e9b` (2026-08-21), and `lfm3`
did not exist in llama.cpp until `19cce691` (2026-10-27, PR #31252 `model : add
LiquidAI/LFM3-1.7B and LiquidAI/LFM3-VL-2B`); the registry's own previous `upstream-a37cc46`
build is 2026-10-21, also short of it. The GGUF itself declares `general.architecture = lfm3`
(read from the pinned file's header), so either older image would die in model load with an
unknown architecture rather than test anything. The arm therefore pins the 2026-11-05 ref, which
also carries the later LFM3 work (#31598 spec-decode, #31608 NVFP4 GGUF, #31683 KV-shift fix), and
takes `executor_config: entrypoint: ""` because that image keeps `llama-server` as its
`ENTRYPOINT`.

The command was authored as the **honest test**: nothing is passed that a successful boot would
make true by assertion. It uses `--jinja` and no `--reasoning-format`, and no parser flag exists
anywhere in the arm — the GGUF embeds the current template (12,129 B, byte-identical to the repo's
`chat_template.jinja`). The boot answered the parser question in passing: the suite's 15 scenarios
came back with **0 failures**, so the Jinja path does drive `<tool_call><function=…>` tool calls
without a `--tool-call-parser` flag; whether a thinking trace is split into `reasoning_content`
versus left in content is still unrecorded (see below).

**Measurement (2026-11-07).** First boot, `.30`, through the campaign driver (180 s, rc=0). The
GGUF header reads `general.architecture = lfm3` with 24 blocks and 16 heads, and the pinned
`upstream-6023692-cu130` image — llama.cpp at `6023692`, the ref that carries `LLM_ARCH_LFM3` —
loaded and served it, so the engine-support question this arm existed to answer is **yes**. The
checkpoint is pinned `cd0c74c5` and was pre-staged on the node's shared cache as
`HuggingFace/LiquidAI/LFM3-1.7B-GGUF@cd0c74c5…` (Q4_K_M, 1,099,627,808 B; `refs/main` and trees
written), the image pulled by digest.

Ladder, `benchmarking/concurrency-ladder.yaml` (depth 0, pp 2048, tg 128, five runs):
| cell | pp t/s | tg t/s | ttfr |
|---|---:|---:|---:|
|c1|12762.8 ± 99.6|**137.51 ± 2.90**|143.9 ms|
|c2|3099.9 ± 71.8|127.56 ± 2.64|681.2 ms|
|c5|2123.6 ± 27.1|121.37 ± 1.03|2295.3 ms|
|c10|1921.7 ± 12.6|121.16 ± 1.27|4927.7 ms|

**Read the `c > 1` cells as queue time, not as concurrency.** The arm serves `parallel: 1`, so
every extra request waits for the single slot: the drop from 137.5 to 121 t/s while ttfr grows
0.14 s → 4.9 s is one slot serialising work, not a throughput ceiling. The ladder was taken with
`ARM_ALLOW_FEW_SLOTS=1` for that reason; a `parallel: 8` variant would be a different arm and a
different claim, and none of these cells belongs in the root index's concurrency columns.

House: **score 93** — 15 scenarios, 13 pass, 2 partial (`TC-11`, `TC-14`), 0 fail. The engine's
own timings agree with the instrument (serve log: prompt 1,831 tokens at 13,630 t/s; decode 128
tokens at 133.65 t/s). Receipt
`~/benchmarks/liquidai-20261107/receipts/liquidai-lfm3-1.7b-q4km-llamacpp.json`, window
`~/benchmarks/tp12-20261107/liquidai-lfm3-1.7b-q4km-llamacpp/`, campaign journal in the campaign
root.

**Engine routes (2026-11-07 survey).** llama.cpp is the only LFM3-capable *pinned* engine this
registry holds: the `upstream-6023692-cu130` image carries `LLM_ARCH_LFM3` and covers the whole
family — text, the `lfm3vl` projector, `lfm3a`/`lfm3a_gen` audio, and `d1` through
`/v1/systemone`. Three other routes are closed at their current pins: the pinned vLLM b12x image
(`cf5a2a53…`) is vLLM `0.1.dev21830+g8244d1c44` (2026-10-15) and its model registry carries only
`Lfm2`/`Lfm2Moe` — upstream vLLM added LFM3 text on 2026-11-06 (`c96e5f60bb`, PR #65826), after
that image, which is why the bf16 vLLM arm authored alongside this one was retired unshipped
rather than queued; SGLang v0.5.22 has no `Lfm` entry at all; and the resident scitrera llama.cpp
pin predates LFM3 (above). A vLLM or SGLang arm becomes viable only on a re-pin. Two instrument
gaps follow from the same survey: `benchmarking/standard-suite.yaml` is **text-only** — it has no
VL cells, so a VL queue row's "standard suite" wording overstates what exists today — and audio
arms need the media lane's `Cactus-Compute/whistle` WER chain (§Instruments).

**Instruments — the text lane's, and one boot.** Ladder:
`sparkrun benchmark performance <recipe> --profile benchmarking/concurrency-ladder.yaml`
(`llama-benchy`, c 1/2/5/10, depth 0, pp 2048, tg 128, five runs). Suite:
`benchmarking/standard-suite.yaml` (`tool-eval-bench` core 15, greedy, 8 turns). A tool-calling
cell of 0 on the first boot is a **parser** question before it is a model question: check the
serve log's template/tool lines, then add a parser flag only if the engine lists one for this
template. Receipts belong in `~/benchmarks/liquidai-<date>/`.

## Fine-tuning

`finetuning/` is where the toolkit survey lands — one entry per toolkit that can actually train an
`lfm3` custom-code, conv-hybrid stack on aarch64/Blackwell, with the blocker that decided it. See
[`finetuning/README.md`](finetuning/README.md). Position as of 2026-11-03: the
`transformers`+`peft`+`trl` reference path is **usable** and was measured on CPU; Axolotl 0.21.1 is a
usable patch with `sample_packing: false`; five other candidates are rejected with their failing gate
recorded. The binding constraint is not the conv layers — it is that `lfm3` ships outside
`transformers` entirely and its custom code needs `transformers>=5.18.0` (5.15/5.16 load but fail on
the first forward, 5.17.0 fails at config load).