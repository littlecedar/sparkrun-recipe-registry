# Liquid AI lane

Liquid AI's LFM3 family and its `d1-*` system-one siblings: small (1.7B–2.2B) edge models with a
**hybrid `conv` + `sliding_attention` + `full_attention`** stack, shipped as `transformers`
custom-code architectures (`auto_map` → `trust_remote_code` required) with vendor GGUF mirrors
carrying LEAP quantization metadata.

**No arm ships yet.** The lane opens with one recipe row per collection member plus a
fine-tuning-toolkit survey row, all in `mad-science/queue.json`; measured cells land here.

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

## Fine-tuning

`finetuning/` is where the toolkit survey lands — one entry per toolkit that can actually train an
`lfm3` custom-code, conv-hybrid stack on aarch64/Blackwell, with the blocker that decided it. See
[`finetuning/README.md`](finetuning/README.md). Position as of 2026-11-03: the
`transformers`+`peft`+`trl` reference path is **usable** and was measured on CPU; Axolotl 0.21.1 is a
usable patch with `sample_packing: false`; five other candidates are rejected with their failing gate
recorded. The binding constraint is not the conv layers — it is that `lfm3` ships outside
`transformers` entirely and its custom code needs `transformers>=5.18.0` (5.15/5.16 load but fail on
the first forward, 5.17.0 fails at config load).