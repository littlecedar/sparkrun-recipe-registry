# Media lane

Generation and tooling models on one DGX Spark: speech synthesis, speaker diarization, image and
video generation, and a text rewriter. This lane was split out of Explore on **2026-10-22** (owner
directive): Explore keeps the language and agentic arms, and every arm whose product is not text —
or whose job is to transform text rather than answer — lives here. Everything in this lane is
1 node, and the two CPU serves cost no GPU.

The lane ships **ten recipes**: seven measured arms (drama TTS, Kokoro TTS, Qwen-Image on both
routes, LTX-2.5, humanizer Q6_K, Kromoss image) and three probe/draft arms (`zz-minimax-h3`,
`zz-qwen-image-…-4step`, `zz-pyannote-…`). Design and bring-up
history lives in [`attic/explore/`](../../attic/explore/), written while these arms were in that
lane; the recipe YAML keeps only the crucial operational notes.

## Contents

- [Selection (2026-10-22)](#selection-2026-10-22)
- [drama-3-35b-a3b-fp8-vllm-omni-tts](#drama-3-35b-a3b-fp8-vllm-omni-tts)
- [kokoro-82m-tts-cpu](#kokoro-82m-tts-cpu)
- [qwen-image-2.1-turbo-7b-bf16-diffusers-script](#qwen-image-21-turbo-7b-bf16-diffusers-script)
- [qwen-image-2.1-turbo-7b-bf16-vllm-omni](#qwen-image-21-turbo-7b-bf16-vllm-omni)
- [kromoss-mossimage-5b-bf16-diffusers-script](#kromoss-mossimage-5b-bf16-diffusers-script)
- [zz-qwen-image-2.1-turbo-4step-diffusers-script](#zz-qwen-image-21-turbo-4step-diffusers-script)
- [ltx-2.5-22b-nvfp4-t2v-comfyui-script](#ltx-25-22b-nvfp4-t2v-comfyui-script)
- [LTX-2.5 measured cells (runbook)](#ltx-25-measured-cells-runbook)
- [zz-minimax-h3-fl2va-t2va-sglang](#zz-minimax-h3-fl2va-t2va-sglang)
- [humanizer-12b-q6k-llamacpp](#humanizer-12b-q6k-llamacpp)
- [zz-pyannote-community-1-diarization-cpu](#zz-pyannote-community-1-diarization-cpu)
- [phonon-31m-tts-cpu](#phonon-31m-tts-cpu)
- [Mods](#mods)
- [Lane notes](#lane-notes)

---

## Selection (2026-10-22)

This lane is organized by **task**, not by a single scored axis: a TTS arm is judged on real-time
factor and wav integrity, an image arm on seconds per image and peak memory, a rewriter on fact
fidelity. None of them is a chat arm, so the house decode ladder does not apply — the `—` cells
below are by design, not missing measurements.

| arm | C1 / task rate | size · memory | tested surface | receipt |
|---|---|---|---|---|
| `drama-3-35b-a3b-fp8-vllm-omni-tts` | **RTF 0.848 ± 0.015** at 4.6 s audio; **0.813** at 28.7 s; streaming TTFA **0.646 s** | 36.88 GiB checkpoint · **37.69 GiB loaded** · TTR 437.0 s cold / 417.0 s warm | WAV integrity (44.1 kHz mono 16-bit, peak 0.48–0.95 FS), seeded byte-identical decodes; intelligibility now scored by the whistle instrument below (WER 0–1.2 % on this render set) | `~/benchmarks/drama-20261022/` |
| `kokoro-82m-tts-cpu` | **RTF 0.588–0.601** (1.66–1.70× realtime) | 0.305 GiB ONNX weights · **1.55 GiB process RSS** · HTTP-ready 14.4 s | wav round-trip + `/health`; 24 kHz mono 16-bit | `~/benchmarks/kokoro-tts-20261019/` |
| `qwen-image-2.1-turbo-7b-bf16-diffusers-script` | **0.088 img/s** (11.33–11.41 s @1024²; **53.24 s @2048²**) | 32.5 GB · peak 36.85/37.68 GiB @1024², **56.51/59.78 GiB @2048²** | single denoise lock, one request at a time | `~/benchmarks/qwen-image-20261014/`, `~/benchmarks/media-gen-20261018/REPORT.md` |
| `qwen-image-2.1-turbo-7b-bf16-vllm-omni` | **8.610–8.704 s warm** (11.0 s first request of a boot) @1024² 8-step; **10/10 PNGs byte-identical** | same checkpoint · engine peak **34.91 GiB** (`peak_memory_mb` 35,748) · TTR **251 s cold / 209 s warm** | seeded renders deterministic across boots; **two-ink prompt violated** (6 hue families); 4/8/12 steps byte-identical; stopped, node back to 0 containers | `~/benchmarks/omni-qwen-image-20261022/` |
| `kromoss-mossimage-5b-bf16-diffusers-script` | **143.884 s/img** control (50-step CFG-3); **18.341 s/img** with the 8-step dmd2 LoRA | ≈27.2 GiB resident (bf16 10.16 GB + TE 16.79 GB + VAE 0.25 GB) · peak alloc 28.19 GiB control / 26.44 GiB LoRA | seeded renders; **step knob proven live** (8- vs 12-step) | `head:~/benchmarks/tp4-lane-20261024/kromoss/` |
| `ltx-2.5-22b-nvfp4-t2v-comfyui-script` | **78.1 s/clip warm** (100.13 s cold) @1344×768, 121 f, 24 fps | 36.9 GB · peak **83.45–84.00 GiB** | ffprobe (h264 + AAC) and a decoded frame | `~/benchmarks/ltx25-recipe-20261021/` |
| `humanizer-12b-q6k-llamacpp` | **C1 17.92 ± 0.04 t/s** @ d0 (`/v1/completions`) | 10.03 GB · TTR 10.8 s | 40-rewrite fact-fidelity instrument: **0 genuine fact errors** (bf16 baseline 1) | `~/benchmarks/humanizer-20261022-q6k/` |
| `zz-minimax-h3-fl2va-t2va-sglang` | **never booted** (draft) | 39.54 GiB / ~42.5 GB resident plan | none — task `t2va`/`fl2va`, territorial license | — |
| `zz-minimax-h3-fl2va-t2va-tp4-sglang` | **measured negative 2026-10-24** — four-rank serve deadlocks in the first video request (denoise exchange; see the arm section) | 13.94 GiB/node resident at TP=4 | walls 1–2 fixed in-recipe; wall 3 is engine-side | `head:~/benchmarks/tp4-window-20261024/H3-TP4-CELL-RESULT.md` |
| `zz-qwen-image-…-4step-diffusers-script` | 4-step request **6.365 s** on the launcher's native `sigmas` path | same peak as the shipped arm | probe only, not a shipped arm | `head:~/benchmarks/vllm-032-20261022/qwen-image/` |
| `zz-pyannote-community-1-diarization-cpu` | **TTR 9.56 s**, RTF **0.247** (real two-voice dialogue) / 0.62 (30 s synthetic) on 5 cores, no GPU | 8.1M params, 33.7 MB repo, CPU only | **DER = JER 2.83 %** on `tier-b-two-voice.wav` (real speech, correct 2-speaker count, deterministic); **one speaker** on 2- and 3-voice synthetic tonal files (DER 50.0 / 69.9 %) | `.35:~/benchmarks-pyannote/` |
| `whistle-asr-cpu` (probe, no recipe yet) | **WER 0.000** on c1/c2/c3/t0/para renders, **0.0118** on the 85-word long render (1 sub: "Rita"→"Reader"); transcripts **byte-identical 11/11** across runs; silence/−60 dBFS noise hard-rejected (exit 1, no hallucination) | 16.9 MB `whistle.cact` + 1.4 MB vendor `linux-arm64` needle binary, CPU only | vendor binary runs unmodified on GB10 aarch64; depth A/B (depth 2 = 2.6× faster, costs accuracy) | `~/benchmarks/tp4-lane-20261024/whistle/` |
| `phonon-31m-tts-cpu` (probe, no recipe yet) | **RTF ~0.17** (4.56 s audio / 0.755 s wall, q8, CPU); **WER 0.000** through the whistle instrument on all four renders | 64.5 MB q8 gguf + tokenizer, ~1 ptts wheel install | `ptts` aarch64 wheel exists (0.4.1, no source fallback); **not byte-deterministic per invocation** (same seed/text/threads differs in PCM) | `~/benchmarks/tp4-lane-20261024/phonon/` |

**What is not here.** indra-ocr remains a research-only entry in `mad-science/TODO.md`
(no recipe, no download, no boot). MOSS-Image ships above as
`kromoss-mossimage-5b-bf16-diffusers-script`; Timestral, the time-series forecaster, ships in the
[decision lane](../decision/README.md#timestral-209m-forecast-cpu).
A recipe appears in this lane only once it is authored.

## whistle ASR probe (no recipe yet)

`Cactus-Compute/whistle` · **16.9 MB single-file ASR** · **probed 2026-10-24 (`.34`, CPU-only one-shot containers)**.

- **What it is:** the lane's missing WER instrument — the pyannote diarizer answers speaker structure,
  whistle answers word fidelity. Vendor `needle3` `linux-arm64` binary (sha256 `a7dd07f7…`) +
  `whistle.cact` (sha256 `b6e02f04…`), Apache-2.0, ungated; runs unmodified on the GB10 aarch64 host
  inside `python:3.12-slim@sha256:a6e34c598f24…` (the pyannote recipe's pinned base). No build, no GPU.
- **Measured** (`~/benchmarks/tp4-lane-20261024/whistle/`, `REPORT.md`): WER 0.000 on c1-plain/-r3/-r4/-r5,
  c2-clone, t0-r1, c3-tags (`[sighs]`/`[laughs]` neither rendered nor transcribed) and para-r1
  ("ten percent" → "10 %" normalizes equal under the card's Whisper-normalizer convention);
  **0.0118 on the 85-word long render** ("Rita" → "Reader", one sub). c1-plain-r2 scores 0.46 only
  because that take is the known 2.368 s under-render — needle transcribed exactly the words present.
  **Transcripts byte-identical 11/11** across independent runs. Digital silence and −60 dBFS noise are
  hard-rejected (exit 1, `cannot read … (RIFF WAV)`) — no hallucination path. `--audio-depth` ladder:
  depth 2 is ~2.6× faster on 28 s audio (1,419 vs 550 tok/s) and costs accuracy; full depth is the
  instrument default. `needle whistle compare` is absent from this build's flag surface.
- **Unblocks:** the phonon-31m item's full TTS-intelligibility cell (render → transcribe → WER).
  A `whistle` serve recipe is a candidate once the instrument chain is exercised end-to-end.

## phonon-31m TTS probe (no recipe yet)

`gradium/phonon-31m-en` · **31M-param English TTS, 64.5 MB q8** · **probed 2026-10-24 (`.34`, CPU-only one-shot containers)**.

- **Install:** `pip install ptts` on aarch64 resolves `ptts-0.4.1` from a manylinux-aarch64 wheel —
  the item's documented transformers-from-source fallback is not needed. Model staged as a local
  snapshot (`-m <dir>`), so the Hub is never contacted at render time.
- **Render:** fixed default voice, drama-3 c1 text: 4.56 s of 24 kHz mono audio in 0.755 s wall
  (**RTF ~0.17**, ~6× realtime).
- **Determinism caveat:** ptts 0.4.1 is **not byte-reproducible across invocations** — same text,
  seed and temperature produce identical-length but different PCM (persists with `-t 0` and
  `--threads 1`). Score phonon A/Bs at the transcript/metric level, never byte level.
- **Intelligibility (the lane's first full cell):** whistle transcribes all four renders at
  **WER 0.000** against the c1 ground truth (`~/benchmarks/tp4-lane-20261024/phonon/REPORT.md`).
  The kokoro-vs-phonon hard-sentence A/B is closed below.

### The kokoro-vs-phonon hard-sentence WER A/B (2026-10-25, `.35`)

The card's hard set is unpublished, so the A/B renders an authored 12-sentence structured-data set
(numbers, dates, codes, units; `.scratch/tplt4/hard-sentences.tsv`) plus the c1 control, twice per
arm — kokoro through the shipped recipe's `kokoro-fastapi-cpu` image (`af_heart`), phonon through
`ptts` q8 seed 1234 — and transcribes every wav twice with whistle at full depth (104 rows, rc 0
across the board). Scoring is **literal WER** (whisper-normalizer + difflib, no LLM-assisted
equivalence), so the numbers sit far above the card's published 1.5 %/3.5 % and are comparable only
to each other:

| arm | renders | literal WER | typical misses |
|---|---|---:|---|
| **phonon-31m q8** | 26 (2 takes × 13 sentences) | **0.1747** | calibration words ("mL" → "millilitres"), "shipped" → "ship" |
| **kokoro-82m** | 26 (2 takes × 13 sentences) | **0.2329** | flight codes ("BA 287" → "B.A. 200, and 87"), serials ("SN-00-7X-4412" → "SN0 to 7x4412"), "gate T-9" → "189" |

**Verdict: phonon wins the hard-sentence cell** (over 584 scored reference-word instances),
direction agreeing with the card's claim that kokoro is weakest on structured text. Instrument
question decided: **whistle + transcript-level scoring is the lane's hard-sentence instrument**;
whistle transcripts were byte-identical across independent container runs (52/52), while phonon's
same-seed take pairs differ in PCM (13/13) — confirming both instruments' known determinism
properties. Operational trap for any ptts caller: pass the model **directory** to `-m` (`ptts -m
/m …`); a bare `.gguf` path fails, and mounting a symlinked HF snapshot dir breaks the checkpoint
check — copy the snapshot files first. Receipts: `~/benchmarks/tplt4-20261024/ab/`.


## [drama-3-35b-a3b-fp8-vllm-omni-tts](drama-3-35b-a3b-fp8-vllm-omni-tts.yaml)

vLLM-Omni · **1 node (TP=1)** · **booted 2026-10-22 (`.34`), two boots**.

> **LICENSE — revenue-gated.** `fishaudio/drama-3` is under the **FISH AUDIO COMMUNITY LICENSE
> AGREEMENT v1.0**: non-commercial and research use only, and commercial use only below a USD
> 500,000 annual-revenue threshold. Read `LICENSE.md` in the checkpoint before serving this to
> anyone. Weights stay in the HF cache, never in the image.

- **Model:** `fishaudio/drama-3` (pinned `b2b5ee99…`) — 35B total / 3B active TTS with a 10-codebook
  audio decoder, served by `vllm-omni serve --omni` on one DGX Spark.
- **Engine / knobs:** `vllm/vllm-omni:nightly-15bce345…` digest-pinned; two-stage omni pipeline (AR
  backbone + DAC codec stage), util split `0.55` / `0.06`. `--stage-init-timeout 1800` ships because
  the engine's 300 s default is a deadline for the load+compile budget, not a load time.
- **Boot trap, worth keeping:** the first boot loaded the model in 242.84 s and was killed 2 s after
  `torch.compile` finished, because cold load + compile was ~298 s against the 300 s default. A port
  answer is not readiness either — a foreign listener once satisfied a port probe; gate on
  `/v1/models` naming `fishaudio/drama-3`.
- **Measured:** warm RTF **0.848 ± 0.015** at ~4.6 s of audio and **0.813** at 28.7 s, streaming PCM
  TTFA **0.646 s**, 44.1 kHz mono 16-bit out; TTR **437.0 s cold / 417.0 s warm** (compile cache).
  **Pass a `seed`**: seeded takes are byte-identical (10/10) and length scales with input
  (0.357 s/word at 13 words, 0.327 at 44); unseeded, one 13-word sentence returns 4.2–7.7 s of audio
  (σ 0.93, n=10). `temperature` is not a request field on this API.
- **Open cell:** intelligibility is unmeasured — no ASR model on the node; the owner's ears on four
  named wavs decide it (`zz-pyannote-community-1-diarization-cpu` covers who-spoke-when only).
- **License:** FISH AUDIO COMMUNITY LICENSE AGREEMENT v1.0 (revenue-gated, see banner).
- **Details:** [`attic/explore/AGENTS.md`](../../attic/explore/AGENTS.md).

## [kokoro-82m-tts-cpu](kokoro-82m-tts-cpu.yaml)

Kokoro-FastAPI CPU image · **1 node, CPU only** · **boot-verified 2026-10-19 (`.34`)**.

| field | value |
|---|---|
| repo id | [`hexgrad/Kokoro-82M`](https://huggingface.co/hexgrad/Kokoro-82M) (pinned `f3ff3571` — checkpoint identity; the image serves its baked ONNX export) |
| accuracy | **not scorable** — no instrument in the registry has a TTS pass; the gate is a wav round-trip + real-time factor |
| size | 0.305 GiB of ONNX weights; **1.55 GiB container / 1.41 GiB server RSS** measured |
| API | `POST /v1/audio/speech` (OpenAI shape) + `GET /health`; **CPU** |
| TP | 1 |
| flags | 🤏 smol · 🖥 cpu · 👄 speech |
| status | **BOOT-VERIFIED 2026-10-19** (`.34`, container-start TTR HTTP-ready 14.4 s) |

An 82M StyleTTS2/ISTFTNet model served by Kokoro-FastAPI's CPU image
(`ghcr.io/remsky/kokoro-fastapi-cpu@sha256:ee3111d6…`, the only published digest-pinned multi-arch
CPU image with kokoro-onnx, onnxruntime and espeak-ng and the model set baked at build). The image
bakes the voices and takes no model argument, so the recipe declares
`distribution_config.models.enabled: false` — otherwise the launch contract rejects a command that
never names the staged snapshot. It runs on the same `taskset -c 0-4,10-14` A725 set as the decision
CPU arms and costs no GPU. Pinned to a digest because the image's default `DOWNLOAD_MODEL=true`
would re-fetch weights on every boot; the recipe passes `DOWNLOAD_MODEL=false`.

Measured on the first boot (`~/benchmarks/kokoro-tts-20261019/`): RTF **0.588-0.601** over two text
lengths (77 and 1,062 chars, two measured repeats each after a warm-up), i.e. **1.66-1.70x
realtime**; `/health` 200 in 21 ms; the server process observed at 317 % CPU. The wav is 24 kHz mono
16-bit. **Client caveat:** the response is streamed and its `data` chunk size is `0xFFFFFFFF`, so
decode by byte length — a naive header read reports tens of thousands of seconds.

The memory line matters for any co-location budget: the quoted 0.305 GiB is the weights, while the
process carries Python, onnxruntime, espeak-ng and the voice tensors — `docker stats` read
**1.552 GiB**. The decision lane's co-location arithmetic counts this 1.55 GiB.

**License:** Apache-2.0. Receipt: `~/benchmarks/kokoro-tts-20261019/` (`REPORT.md`, `probe.json`,
four wavs).

## [qwen-image-2.1-turbo-7b-bf16-diffusers-script](qwen-image-2.1-turbo-7b-bf16-diffusers-script.yaml)

diffusers engine (no `sglang`/vLLM serves it) + [`recipes/media/mods/qwen-image-2.1-turbo-launcher`](mods/qwen-image-2.1-turbo-launcher) ·
**1 node** · eval-only · **kept 2026-10-19 — media-gen arm whose cells are closed**.

> **LICENSE — NON-COMMERCIAL ONLY.** `Qwen/Qwen-Image-2.1-Turbo` is under the **Qwen Research
> License Agreement** (card `license: other`, `license_name: qwen-research`): **FOR NON-COMMERCIAL
> PURPOSES ONLY**. This registry is distributed to third parties. A recipe ships a repo id, not
> weights — each downloader fetches from the Hub and accepts the license there — but **neither the
> weights nor images generated from them may be used commercially**. An operator needing commercial
> use must swap the checkpoint; the serving path
> (`recipes/media/mods/qwen-image-2.1-turbo-launcher` + this recipe) is checkpoint-agnostic. **Owner
> call 2026-10-14: ship the recipe with this banner.**

- **Model:** `Qwen/Qwen-Image-2.1-Turbo` (pinned `fc13ba1986`), text-to-image + editing, 8-step
  distilled at CFG=1.
- **Size / memory:** 32.5 GB bf16 (DiT 14.2 + text encoder 17.5 + VAE 0.68); peak ~36.85 GiB torch
  alloc / 37.68 GiB reserved at 1024².
- **Flags / non-obvious knobs:** `runtime: vllm` is the family whose distribution + single-node
  launcher contract the command satisfies; `command:` runs a stdlib HTTP server (`POST /generate`,
  `GET /health`) out of a `diffusers>=0.41` / `transformers>=5.17` venv the mod stages on the image's
  own torch (`vllm/vllm-openai:v0.32.0`, re-pinned 2026-10-22; the venv's own `transformers>=5.17`
  satisfies the card's floor — the image's copy is unused). **VAE tiling OFF** (tiled decode → a
  pink seam column) and **`cpu_offload` OFF** (costs ~4× on a reference image);
  `--served-model-name` is rendered explicitly.
- **Status contract (2026-10-22):** `POST /generate` answers **400** with `{"error": …}` for a
  request this server cannot accept (bad JSON, non-object body, missing prompt, non-integer
  size/seed, `sigmas: []`, unreadable `image_path`, bad `Content-Length`) and **500** only for a
  fault of the server itself (no image returned, unwritable sample dir, missing
  `diffusers.utils.load_image`) — its traceback goes to the log, never to the client. `/health`
  reports `attempts`/`failed` alongside `requests`, so a serve rejecting everything cannot read as
  idle. Full table: [`mods/qwen-image-2.1-turbo-launcher/README.md`](mods/qwen-image-2.1-turbo-launcher/README.md).
- **Measured:** 1024² / 8-step CFG=1 → **11.3–11.4 s** steady (a same-boot control on the 2048² run
  read 11.240 s ± 0.008); a reference image fed back for editing +3.5 s; same prompt+seed → a
  byte-identical PNG. **2048² cell closed 2026-10-18**: **53.24 s/image** (mean of 3, σ 0.20) — 4×
  the pixels for 4.74× the time — peak **56.51 GiB** alloc / 59.78 GiB reserved, node
  `MemAvailable` floor 53.8 GiB; the lane's ~26 s prediction is falsified 2.04×.
- **Step-count trap:** a non-null `num_inference_steps` is accepted silently and ignored (`12` still
  returned `steps: 8`: the pipeline is configured from the checkpoint's saved 8-step
  `sample_sigmas`) — since 2026-10-21 an explicit `sigmas` list does take, which is what makes the
  other schedules reachable at all.
- **Re-pin boot (2026-10-22, `.34`, `sparkrun_138e576f5771494d_8ed3ce77d78f`):** `/health` 200
  **222 s** after launch (188.9 s of it the pipeline load), `/v1/models` = the repo id, `torch
  2.13.0+cu130` / `diffusers 0.41.0` / `transformers 5.19.0`. The 1024² 8-step cell (same prompt and
  seed 42 as the 2026-10-21 reference) read **12.686 s** server / 13.019 s client, `steps: 8`,
  `sigmas_used: null`, peak **36.824 GiB** alloc / **37.648 GiB** reserved — identical to the
  `v0.30.0` cell — and produced a **byte-identical PNG (`e24f6e3a…`)**. The reason is visible in the
  images: `v0.30.0` and `v0.32.0` both ship **torch 2.13.0+cu130**, so this bump moves the vLLM
  wheel, not the torch build the mod stages on. A 4-step request on the same boot took the
  launcher's native path: `steps: 4`, `sigmas_used: [1.0, 0.944995, 0.861792, 0.414568]` (the saved
  8-point curve resampled, endpoints kept), **6.365 s**, same peak, PNG `2e41a540…` — which is the
  probe the `qwen-image-sigmas` mod used to exist for; the launcher's own `schedule_kwargs` now does
  it, and that mod's fail-closed anchor no longer matches the launcher (see the probe recipe's
  header). Receipt `head:~/benchmarks/vllm-032-20261022/qwen-image/`.
- **Hardened server re-verified live (2026-10-22, `.34`, same task id):** the 400/500 split and the
  `/health` counters boot and serve, not just stub-test. `/health` 200 at **207 s** (load 179.6 s,
  payload now carrying `attempts`/`failed`); the same 1024² 8-step seed-42 cell returned **200** at
  **12.311 s** server / 12.624 s client, `steps: 8`, `sigmas_used: null`, peak **36.824 / 37.648
  GiB**, and a **byte-identical PNG (`e24f6e3a…`)** — the success path did not move. Against the
  live serve, `{"sigmas": []}` and a missing `prompt` both answered **400** with their reason and no
  traceback (`generate rejected: …` + `400` in the serve log, zero `Traceback` lines), and `/health`
  then read `requests 1, attempts 3, failed 2`. Receipt
  `head:~/benchmarks/vllm-032-20261022/qwen-image-live/` (cell JSON, PNG, serve log, preflight).
- **A faster route exists and now ships as its own arm** (the next section; booted and measured
  2026-10-22 on `.35`): `vllm/vllm-omni:nightly` serves this checkpoint natively (its own
  `QwenImage21Pipeline`) at **8.66–8.75 s warm / 11.19 s cold** for the same 1024² 8-step image,
  **~24 % faster** than this arm's 11.49 s at *the same* peak memory (36.84 vs 36.82 GiB) — measured
  2026-10-21 on `.34`, one serve per route. Two properties stay attached to that route: its
  `num_inference_steps` is inert *and* its own
  `denoise_step_latency_ms` divides one total by the requested count (4/8/12 → the byte-identical
  PNG at 8.7 s while claiming 2164/1086/721 ms per step), and same seed ≠ same image (`38ce554a…`
  vs this arm's `e24f6e3a…`). **Both 8-step images were inspected at full resolution against the
  prompt**, whose string is identical in both recorded bodies (`cells-premod.json` cells 0–1 vs
  `vllm-omni/omni.json` cells 0–3: same `prompt`, 1024×1024, seed 42 — only the CFG spelling
  differs, `guidance_scale: 1.0` in the OMNI request vs CFG=1 from this arm's serve config, plus
  `use_kv_cache`, which is a launcher-only knob), so the divergence is a route property and not a
  request artifact; and it says `two-color screenprint`: this arm honors it — two inks, blue over
  orange on cream, correct spelling, crisp edges — and OMNI **violates** it, rendering `SPARKRUN` as
  a rainbow of many hues on white (correctly spelled and crisply edged, but not two inks). No
  blended glyphs or step-starvation artifacts in either, so the ~24 % win is real and defect-free;
  it is simply spent on the wrong instruction. **That is a prompt-adherence defect, not a style
  difference** — and it is scoped to one prompt, one seed, one image per route, so it is evidence
  against swapping on latency alone, **not** a measured general quality gap. **This arm stays the
   default**; the OMNI variant is a *different look* the owner likes — declined as an arm on
   2026-10-21, **reversed 2026-10-22 (`QUESTIONS.md` `#13`: "ship both")**, so that look now has its
   own arm below, booted 2026-10-22. The §6 "quality judged by eye" item stays open for
   **this** arm's gallery comparison. Notes:
   [`attic/explore/QWEN-IMAGE.md`](../../attic/explore/QWEN-IMAGE.md) §"vLLM-OMNI route".
- **Details:** [`attic/explore/QWEN-IMAGE.md`](../../attic/explore/QWEN-IMAGE.md).

## [qwen-image-2.1-turbo-7b-bf16-vllm-omni](qwen-image-2.1-turbo-7b-bf16-vllm-omni.yaml)

vLLM-Omni · **1 node (TP=1)** · **booted and measured 2026-10-22 (`.35`)**, four acceptance cells
closed.

> **LICENSE — NON-COMMERCIAL ONLY.** Same checkpoint as the Diffusers arm, and the license follows
> the checkpoint, not the engine: `Qwen/Qwen-Image-2.1-Turbo` is under the **Qwen Research License
> Agreement** (card `license: other`, `license_name: qwen-research`), **FOR NON-COMMERCIAL PURPOSES
> ONLY** — neither weights nor generated images may be used commercially. Read the sibling arm's
> banner above for the full note; the recipe repeats it.

- **Model:** `Qwen/Qwen-Image-2.1-Turbo` (pinned `fc13ba1986`) — the same 8-step distilled,
  CFG=1 checkpoint and revision as the Diffusers arm, so the two arms differ only in route.
- **Engine:** `vllm/vllm-omni:nightly-15bce345…@sha256:f3473cb3…`, **digest-pinned** (index digest;
  arm64 child `sha256:9c155dff…`, 11.23 GB). It carries `vllm_omni 0.32.0rc2.dev29+g15bce3458` —
  the version the OMNI measurement reported, and the version the drama-3 boot read inside the same
  digest on `.34` (`docker run … python -c "import vllm, vllm_omni"`). **The pipeline is in the
  image**, verified 2026-10-22 without running a container: exporting the pinned image's rootfs and
  reading it shows `vllm_omni/diffusion/registry.py` mapping `QwenImage21Pipeline` →
  `qwen_image_21` / `pipeline_qwen_image_21` / `QwenImage21Pipeline`, and
  `models/qwen_image_21/pipeline_qwen_image_21.py:297` defining that class. No launcher mod and no
  staged venv are needed.
- **Tag trap, the reason for the pin:** `vllm/vllm-omni:latest` is 0.31.0rc1 and its diffusion
  registry has **`QwenImagePipeline` only**, while the checkpoint's `model_index.json` declares
  `_class_name: QwenImage21Pipeline` — a guaranteed dead boot, not a degraded one.
- **Command / surface:** `vllm-omni serve {model} --omni --served-model-name
  Qwen/Qwen-Image-2.1-Turbo`; `POST /v1/images/generations` is the generation endpoint and `/health`
  answers `{"status":"healthy"}`, so `readiness.inference: false`. `stage_init_timeout: 900` ships
  because the measured TTR is ~4 min against the engine's 300 s stage default.
- **Measured on this arm's own boots** — 2026-10-22, `.35`, task
  `sparkrun_ff85d35d30f290e3_64af2f7668b6` twice (`~/benchmarks/omni-qwen-image-20261022/`): TTR
  **251 s cold** (container start → `/v1/models` naming the served id; `StartedAt` 19:22:28.978Z,
  `Application startup complete` 19:26:34, weights 30.21 GiB in 214.6 s, engine init 229.87 s) and
  **209.2 s warm** on a second boot taken through sparkrun's own readiness gate
  (`container-start TTR port-open 209.181s, HTTP-ready 209.217s`, weights in 181.75 s, engine init
  193.25 s), both against `stage_init_timeout: 900`. The load line reads
  `model_class_name='QwenImage21Pipeline'` on both boots and the attention backend resolved to
  `CUDNN_ATTN` (Blackwell sm_121, cuDNN 92000, head_dim 128). 1024² 8-step seed 42: **10.995 /
  11.084 s first request after readiness**, then **8.610–8.704 s warm** (six requests across the two
  boots, mean 8.652; server `stage_gen_time_ms` 8,492–8,589 ms) — inside the research band and
  slightly under it. **Peak memory 35,748 MB = 34.91 GiB** (engine gauge
  `vllm_omni:peak_memory_mb{stage="0"}`; 30.42 GiB process-scoped after load), lower than the
  research boot's 37,726 MB at the same request shape. **Ten requests — seven on the first boot,
  three on the second — returned one byte-identical PNG**
  (`49927f99993c8c0fb1e8db646ce6f10880e16597028a5102a0773c00dcd9508e`, 4,196,804 B), so a seeded
  render is reproducible **across boots on this node**, not only within one process. It is still not
  reproducible **across serves**: the 2026-10-21 research serve returned `38ce554a…45704690` for the
  identical request body, and since two of this arm's boots agree with each other the difference sits
  between the two serves (the research one was a plain `docker run` without `--revision`), not in
  boot-to-boot memory layout — cause unestablished, image hash therefore a provenance stamp for a
  serve rather than a cross-serve check.
- **Measured — research receipt (route comparison, 2026-10-21)** (one serve per route, same
  prompt and seed 42, 1024² 8-step): **8.66–8.75 s warm / 11.19 s cold** against the Diffusers arm's
  11.49 / 12.64 s — **~24 % faster**, 1.08 vs 1.43 s per step — at the **same** peak memory
  (36.84 GiB `vllm_omni:peak_memory_mb{stage="0"}` = 37,726 MB vs 36.82 GiB torch alloc). Receipt
  `head:~/benchmarks/media-gen-20261021/vllm-omni/` (`REPORT.md`, `omni.json`, `omni-warm8.json`);
  numbers and route in [`attic/explore/QWEN-IMAGE.md`](../../attic/explore/QWEN-IMAGE.md)
  §"vLLM-OMNI route".
- **The inert step knob — re-verified by hash on this engine version, not repeated from memory.**
  `num_inference_steps` 4 / 8 / 12 at seed 42 returned the **byte-identical PNG** (same hash, same
  4,196,804 B) in 8.594 / 8.644 / 8.622 s, while the engine's claimed `denoise_step_latency_ms` fell
  **2,124.6 → 1,064.5 → 711.0 ms** — one total divided by the requested count, so asking for more
  steps makes each step *look* cheaper. There is no working 4-step or 12-step cell on this route.
- **Adherence defect — this arm ships with a caveat, not a clean bill.** Both 8-step PNGs were
  inspected at full resolution against the prompt, whose string is identical in both recorded
  request bodies. It says `two-color screenprint`: the Diffusers render honors it (two inks, blue
  over orange on cream), and OMNI **violates** it — `SPARKRUN` in a rainbow of many hues on white,
  correctly spelled and crisply edged, but not two inks. That is a **prompt-adherence defect, not a
  style difference**, and the earlier reading of it as "composition" was wrong about the constraint.
  Scope: one prompt, one seed, one image per route — evidence against swapping on latency alone,
  **not** a measured general quality gap (no multi-prompt adherence battery was run). Owner decision
  2026-10-22 (`QUESTIONS.md` `#13`): **ship both looks** as separate arms. Re-reviewed on this arm's
  own boot (2026-10-22, `.35`, `cold-0.png`): the render **reproduces the defect** — single-line
  `SPARKRUN` on white, each glyph a different ink, spelling correct and edges crisp; chromatic
  pixels (12 % of the frame) fall into **6 hue families with no dominant one** (red/orange 27.8 %,
  cyan 25.1 %, magenta 23.7 %, yellow-orange 12.7 %, blue 10.7 %). So the arm ships with this defect
  as its caveat, unchanged.
- **Acceptance closed 2026-10-22 (`.35`) — all four cells pass.** This recipe file was booted twice
  on that node with `-H <node-ip>` (once detached for timing, once through sparkrun's readiness
  gate) and stopped by its task id each time (`docker ps -aq` = 0 on the node afterwards):
  1. readiness gated on `/health` + `/v1/models` naming `Qwen/Qwen-Image-2.1-Turbo`, and the
     **engine's own load line names `QwenImage21Pipeline`** — the identity gate, not a file listing;
     the shipped `readiness:` block also resolves on its own (sparkrun reported `HTTP-ready
     209.217s`, `TTFT not applicable (inference disabled)`, no timeout);
  2. the 1024² 8-step seed-42 re-render read **8.610–8.704 s warm** over six requests on the two
     boots, inside the 8.66–8.75 s research band, so the pin has not drifted in speed (the first
     request of a boot costs ~11.0–11.1 s: lazy regional `torch.compile` fires there);
  3. the two-color screenprint prompt re-rendered and reviewed at full resolution — **same defect**
     (see above), not a resolution, so the row still ships with the caveat;
  4. cold TTR **251 s** (warm boot **209.2 s**) against `stage_init_timeout: 900` — the 900 s stage
     budget is comfortable, and the engine's own 300 s default would also have covered these boots
     (load+init 229.9 s cold / 193.3 s warm), but only by 70 s on the cold one.
  One property to keep beside the numbers: the seeded PNG is byte-identical **across boots on this
  node** (10/10 here) but **not across serves** — the 2026-10-21 research serve returned
  `38ce554a…` for the same request body, so an image hash is a provenance stamp for one serve, not a
  reproducibility check. Receipt: `~/benchmarks/omni-qwen-image-20261022/` (`SUMMARY.md`,
  `serve.log`/`serve2.log`, per-cell JSON, ten PNGs, `/metrics` peak gauge).

## [kromoss-mossimage-5b-bf16-diffusers-script](kromoss-mossimage-5b-bf16-diffusers-script.yaml)

diffusers' custom `MOSSImagePipeline` + [`recipes/media/mods/kromoss-launcher`](mods/kromoss-launcher) ·
**1 node** · **measured 2026-10-24 on `.30`, shipped 2026-10-25**.

- **Model:** `lodestones/Kromoss`, a 5.08B-param MOSS-Image text-to-image full fine-tune
  (base `OpenMOSS-Team/MOSS-Image-Base`, 1024 px, Qwen3.5-9B text encoder + FLUX.2-small VAE
  decoder), Apache-2.0 (weights and the bundled pipeline code). No sglang/vLLM engine serves the
  checkpoint: the pipeline file ships inside it and loads via
  `custom_pipeline="pipeline_moss_image"` + `trust_remote_code=True`; the mod stages a
  diffusers ≥ 0.41 / transformers ≥ 5.17 venv on the image's own torch.
- **Measured cells** (receipt `head:~/benchmarks/tp4-lane-20261024/kromoss/` — `REPORT.md`,
  3 PNGs, `boot9-serve.log`): control 1024² 50-step CFG-3 `uncond_skip_layers=[22]` =
  **143.884 s** (2.88 s/step, peak alloc 28.19 GiB); fast cell with `8-steps-dmd2-lora`
  applied UNMERGED via the card's own forward-hook recipe = **18.341 s** at 8 steps CFG-1
  (2.29 s/step, 252 modules hooked, peak 26.44 GiB). **The step knob is proven live.**
  Pass `-o lora=/cache/huggingface/hub/models--lodestones--Kromoss/snapshots/
  a4fe97449297af2e3be7841e1c18e431f3b06031/8-steps-dmd2-lora.safetensors` for the fast
  cell; the default runs the plain control.
- **Not measured:** image-quality scoring (the lane has no image instrument) and the
  int8_convrot single-file route — expected kernel-dead on sm_121 (same ConvRot-W8A8 class
  MiniMax-H3's INT8 boot verified as rejected), so it is not staged.

## [zz-qwen-image-2.1-turbo-4step-diffusers-script](zz-qwen-image-2.1-turbo-4step-diffusers-script.yaml)

diffusers engine + [`recipes/media/mods/qwen-image-2.1-turbo-launcher`](mods/qwen-image-2.1-turbo-launcher) ·
**1 node** · **probe recipe, not shipped, no index row**.

Same image and checkpoint as the shipped arm (read its license banner: Qwen Research License,
NON-COMMERCIAL ONLY), but the serve command exercises the launcher's `sigmas` field (and a
`num_inference_steps` that resamples the checkpoint's grid) instead of silently ignoring the step
count. It used to run a second server generated by [`mods/qwen-image-sigmas`](mods/qwen-image-sigmas);
that mod's fail-closed patch anchors the pre-2026-10-21 step plumbing and refuses to launch against
the launcher's `schedule_kwargs`, so the native path is the one source of the schedule now. The
4-step cell measured **6.365 s** on the shipped arm's re-pin boot (see above).

## [ltx-2.5-22b-nvfp4-t2v-comfyui-script](ltx-2.5-22b-nvfp4-t2v-comfyui-script.yaml)

ComfyUI v0.34.0 (no `sglang`/vLLM engine serves it) + [`recipes/media/mods/ltx-25-launcher`](mods/ltx-25-launcher) ·
**1 node** · **booted 2026-10-21 on `.35` — first receipt**.

> **LICENSE — read before shipping outputs.** `Lightricks/LTX-2.5` is under the
> **ltx-2.x-community-license-agreement** (card `license: other`): free commercial use for a
> Commercial Entity below a $10M annual-revenue threshold — read
> <https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x>. The repo is **`gated: auto`**: each
> node needs an `HF_TOKEN` whose account accepted the release. A recipe ships a repo id, not weights.

- **Model:** `Lightricks/LTX-2.5` (pinned `49b093a3`) — 22B distilled DiT (nvfp4) + Gemma-4-12B text
  encoder (comfy-int8) + video/audio VAEs + x2 latent upscaler, **36.9 GB**.
- **Engine / staging:** the recipe pins the media-gen lane's arm64 cu130 base
  (`vllm/vllm-openai:v0.32.0@sha256:befccf0e…`, re-pinned 2026-10-22 from `v0.30.0@sha256:8a69…`) and
  the mod stages ComfyUI v0.34.0 plus its package set and a torch venv (resolved
  `torch 2.14.1+cu130`, `comfy-kitchen 0.2.31`), then the five gated weight files — detached,
  because the 600 s `pre_exec` hook cannot hold a 36.9 GB fetch. `runtime: vllm` is only the
  launcher/distribution contract.
- **Re-pin boot (2026-10-22, `.34`, clock-capped, `sparkrun_14f1a40e099ae86c_8ed3ce77d78f`):**
  `/health` 200 **233 s** after launch (68 s engine install/verify, weights from the node cache),
  `/v1/models` = `Lightricks/LTX-2.5`. One T2V cell (1344×768, 121 frames, 24 fps, seed 42): **wall
  98.24 s**, peak **81.77 GiB**, `status success`, 1,569,011 B mp4 (`0aa0ff1994…`; `avc1` 121
  samples + `mp4a`). The engine bump is inert here by construction — the mod stages its own torch
  venv on the image — and the 2026-10-21 cells were 100.13 s / 84.00 GiB, so this is parity, not a
  new measurement: that receipt used the workflow template's own prompt while this cell used a plain
  one. Receipt `head:~/benchmarks/vllm-032-20261022/RECEIPT-media-and-ltx.md`.
- **Flags / non-obvious knobs:** `distribution_config.models.enabled: false` (sparkrun's anonymous
  distribution cannot fetch a gated repo); `readiness.inference: false`, `port_timeout_s: 3600`
  (cold stage); `entrypoint: ""` clears the image's `vllm serve`; `--served-model-name` rendered
  explicitly so `/v1/models` answers the repo id. **sparkrun injects `HF_HUB_OFFLINE=1`** — the mod
  sets it to 0 for its own fetch (an `unset` inside the `hf` CLI wrapper was not enough).
- **Measured 2026-10-21, `.35`, clock-capped at 2200 MHz**, one boot, seeds 42 then 44 (a same-seed
  rerun is fully cached at 0.01 s), prompt = the template's own positive text, 1344×768 / 121
  frames / 24 fps:

  | cell | wall | peak GiB | output |
  |---|---|---|---|
  | cold (model load in) | **100.13 s** | 84.00 | h264 1344×768, 121 f, 5.0417 s + AAC 5.010 s, 848 KB |
  | warm (seed 44) | **78.1 s** | 83.45 | same container, 1.09 MB |

  Both land on the runbook's own cells (cold 100.3 s, warm 78.1 s, peak 83.6 GiB). The frames are
  real content (luma 96.6 / 166.5 / 164.3 at f0/f60/f120; frame-to-frame Δ 0 / 79.6 / 14.3) and the
  audio is not silent (max −26 dB, RMS −43.8 dB). Cold stage: ComfyUI + venv in 121 s, then 36.9 GB
  of weights in 148 s. Receipt `~/benchmarks/ltx25-recipe-20261021/`.
- **Details:** [`ltx-2.5-runbook/README.md`](ltx-2.5-runbook/README.md),
  [`mods/ltx-25-launcher/README.md`](mods/ltx-25-launcher/README.md).

## LTX-2.5 measured cells (runbook)

`Lightricks/LTX-2.5` (video+audio world model, 22B distilled DiT + Gemma-4-12B encoder) is measured
in the runbook at [`ltx-2.5-runbook/README.md`](ltx-2.5-runbook/README.md); its T2V cell now ships as
the recipe above — the I2V and FLF2V templates and the 4K/50 preset are measured on the **runbook
only**, not on the recipe, which serves T2V. Weights ≈36.9 GB; T2V/I2V run the two-stage shape
(8-step @ 672×384 → `LTXVLatentUpsampler` ×2 → 3-step refine @ 1344×768); license
`ltx-2.x-community-license-agreement` (free below a $10M-revenue Commercial Entity threshold).
Lane notes: [`attic/explore/LTX-25.md`](../../attic/explore/LTX-25.md).

**Cells measured 2026-10-18** on `.34` (clock cap 2200 MHz; seeds 42 then 44 — a same-seed rerun is
fully cached at 0.01 s, so the second seed is the first non-cached rep). 1344×768 / 121 frames / 24
fps unless noted. Receipt `~/benchmarks/ltx25-20261018/REPORT.md`.

| cell | template | warm s/clip | peak GiB | what the output actually decodes to |
|---|---|---|---|---|
| T2V control | `video_ltx2_5_t2v.json` | **78.1** | 83.70 | h264 1344×768, 121 frames, 5.0417 s + AAC 5.010 s; frame at t=1.0 s decodes to a PNG (`4da91f2a…`) |
| I2V | `video_ltx2_5_i2v.json` | **84.3** (**+7.9 %**) | 83.79 | same container; frame 0 vs the start image MAD **4.1** (0–255) → the guide is applied, not merely "it decoded" |
| FLF2V | `video_ltx2_5_flf2v.json` | **120.2** (**+54 %**) | 81.94 | same container; frame 0 MAD **7.8** vs start / 59.5 vs end, frame 120 MAD **16.9** vs end / 59.1 vs start → both guides land |
| 4K / 50 fps | `video_ltx2_5_t2v.json`, 3840×2160, 249 f | **OOM** | **121.16 of 121** | **no output** — killed at the ×2 latent upscale |

- **The T2V baseline is 78.1 s, not the recorded 80.1 s** — same cell, same cap, resident weights:
  **−2.5 %** on the 2026-10-14 `.35` figure, so 78.1 is the number to compare against.
- **FLF2V is slower by mechanism, not regression:** that template has no `LTXVLatentUpsampler`, so
  the guides ride one full-res 8-step pass (76.9 s @ 9.6 s/it at 1344×768) instead of half-res
  8-step + 3-step refine — ~1.5× the T2V wall for the same output size.
- **4K/50 is a measured ceiling, not an untried preset:** stage 1 completed (8/8, 461.3 s @ 57.7
  s/it at the 1920×1080 latent, 249 f) and the process died right after `Requested to load
  LatentUpsampler` with 590 `NV_ERR_NO_MEMORY` kernel lines, at **121.16 GiB of 121** (85.0 GiB
  steady in stage 1, weights-only baseline 78.4 → not a two-tenant artifact). The node stayed up: a
  process kill, not a node loss. 3840×2160×249 does not fit one GB10 with this template.
- **Cold rep = 204.3 s is an upper bound** (it overlapped a peer's serve; model load 25 s, first
  sampler step 12 s, cold tiled VAE decode 82.7 s vs 43.5 s warm). It decodes to the same frame hash
  as the resident-model seed-42 rep — content is seed-deterministic, the h264 mux is not.

## [zz-minimax-h3-fl2va-t2va-sglang](zz-minimax-h3-fl2va-t2va-sglang.yaml)

SGLang diffusion · **1 node** · **DRAFT, never booted**.

> **LICENSE — territorial condition.** `MiniMaxAI/MiniMax-H3` is under the **MiniMax H3 Community
> License Agreement** (`license: other`). It is not a revenue license and not an open license: the
> **Excluded Territories** are the European Union, the United Kingdom, the Republic of Korea and the
> United States of America (`LICENSE:3`, `:5`), and use outside the Applicable Territory is
> prohibited (`LICENSE:42`). **The owner's decision is that this arm runs at a non-US site, where
> the condition is met by the deployment location** — a boot is permitted at a non-US site and NOT
> permitted at a US site. Do not re-litigate the license; enforce the location. Obligations that
> still bind: separate written authorization above 20M USD/yr (IV.1), prominent "MiniMax H3"
> display on any commercial UI (IV.2), NOTICE carriage (III.4), and no use of the Works or Outputs
> to improve another AI model (V.3). Governing law: Hong Kong. The Qwen3-VL-32B text encoder is
> Apache-2.0; the aggregate is not.

- **Model:** `MiniMaxAI/MiniMax-H3` (pinned `42ed227e…`) — joint video+stereo-audio diffusion model:
  33.1B DiT ×50 layers + a 33.4B Qwen3-VL-32B text encoder + f16t4d24 visual VAE + a 0.56 GiB audio
  VAE, served on one DGX Spark with SGLang v0.5.22's native diffusion pipeline.
- **Why the shipped set is pruned:** the full bf16 set is 134.1 GiB against ~109 GB of usable
  unified memory. This arm runs the AdaLN-pruned FP8 DiT (19.52 GiB) with an NVFP4-AWQ text encoder
  (14.61 GiB), the fp16 visual VAE and the fp32 audio VAE: 39.54 GiB / 42.5 GB resident, ~58 GB
  headroom. INT8 ConvRot is deliberately absent — GB10 is sm_121 and has no int8 scaled GEMM
  ("No implemented int8_scaled_mm for current compute capability"), so every INT8/W6A8/W4A8
  component in the Hub census is unavailable here, not untested.
- **Task:** `t2va` / `fl2va` — text or first/last frame → video + 32 kHz stereo audio, 4–15 s,
  768p, 24 fps. Never booted; the first boot decides the AdaLN cache question and the wall time.
- **License:** MiniMax H3 Community License (territorial; non-US deployment only).

### The four-rank probe [`zz-minimax-h3-fl2va-t2va-tp4-sglang.yaml`](zz-minimax-h3-fl2va-t2va-tp4-sglang.yaml) — measured negative (2026-10-24)

The QUESTIONS #7 four-rank cell ran on `.31`–`.34` (SGLang v0.5.22, `--num-gpus 4`,
`nnodes: 4, sp_degree: 4, ulysses_degree: 4` all rendered correctly). Three walls, in boot order:

1. **Arg parse** (`performance_mode: auto`): the auto-tuner probes torch device ids
   `0..num_gpus-1` as *local* (`auto_tune.py:840` → `AssertionError: Invalid device id`) — a
   1-GPU-per-node fleet cannot satisfy it. `speed` mode skips the auto-tuner; TP=4 resident is
   13.94 GiB/node, so `speed` fits trivially. **Fixed in-recipe.**
2. **Component staging**: repo-id-shaped `--component-weights-paths.*` overrides resolve via
   `HfApi().model_info`, which `HF_HUB_OFFLINE=1` kills before any cache fallback
   (`OfflineModeIsEnabled`, `weights/source.py:277`). Absolute pool paths short-circuit to the
   local branch. **Fixed in-recipe** (commit `b9ca89a`; all three Comfy files du-verified on the
   shared cache).
3. **The warmup + denoise wall — engine-side, unresolved.** With input saving *disabled* (the
   tp2-queue single-node fix) the engine's post-init warmup fails `FileNotFoundError` on the staged
   `warmup_image.png` on every rank and `/health` never flips past `workers_ready` — the four-rank
   serve needs input saving **enabled** at an absolute writable path (`/tmp/h3-inputs`, fixed
   in-recipe). With that fixed, the warmup request is accepted and then **the denoise loop
   deadlocks**: ~25 min frozen at `Warmup requests 0/1`, all four GPUs **0 % utilization**, zero
   errors in the serve log. The per-step activation exchange across ranks does not complete a
   single video request on this engine state; Torch SDPA is the auto-fallback attention backend on
   SM12.x and `nccl_port` is unset — the candidate axes for an upstream investigation.

Verdict: arg-plumbing and staging are solved and recorded in the recipe; the TP=4 video cell
cannot produce numbers on SGLang v0.5.22. Receipt:
`head:~/benchmarks/tp4-window-20261024/H3-TP4-CELL-RESULT.md` (the full four-boot chain).

## [humanizer-12b-q6k-llamacpp](humanizer-12b-q6k-llamacpp.yaml)

llama.cpp · **1 node (TP=1)** · **kept 2026-10-22** — the lane's text-rewriting arm.

The lane's **text-rewriting** arm, shipped on the owner's ask (2026-10-22): any draft in, the same
draft out in a human voice with every number, unit, date, name and quotation intact. It is
off-brief for the chat selection axes by construction (no reasoning, no tool calls), so it ships as
a *measured capability*, not as a selection candidate — and its bar was set before the run.

- **Model:** `jialinyyzz/humanizer-GGUF:humanizer-12b-Q6_K.gguf` (10,029,799,584 B) — the vendor's
  own Q6_K of a 12B `gemma4_unified` fine-tune of `google/gemma-4-12B`, Apache-2.0, ungated,
  262,144-token native window. **No chat template exists in the checkpoint** — the working surface
  is `/v1/completions` with the byte-exact prompt from the repo's `prompt_format.json`
  (`instr + "\n\n" + draft + sep`, fingerprint `cc51d66b4c593fbe`, asserted on every call), which is
  also why the archived vLLM bf16 arm's chat route 400'd. That was a property of the checkpoint,
  never an engine fault: vLLM says so verbatim ("you must provide a chat template if the tokenizer
  does not define one"), and this boot's `/v1/models` advertises no template either.
- **Boot (`.33`, `sparkrun_7b0a21d0dbeb323d_80fa71eb085e`):** TTR port-open **10.8 s** (engine init
  0.8 s, model load 10.0 s); `GET /v1/models` → `jialinyyzz/humanizer-GGUF`; 10,029,799,584 B pack.
  Engine `scitrera/dgx-spark-llama-cpp:b10549-cu131` — stock upstream llama.cpp carries
  `src/models/gemma4.cpp` at our `b2e5e9b` pin, so the arch needs no fork.
- **Speed:** `decode-triage` C1 **17.92 ± 0.04 t/s @ d0** (pp 999 t/s; five samples 17.87–17.96) and
  **17.87 ± 0.05 @ d8192** (pp 1,366 t/s). **2.36× the archived bf16 arm's 7.6 t/s**, at 10 GB
  instead of 88 GB of repo. The 40-rewrite harness independently read 55.1 s per 1k output tokens
  (18.1 t/s), matching the bench.
- **Quality — PASS at the pre-registered bar.** Same instrument, same 40 rewrites as the bf16 arm:
  **0 genuine fact errors vs the baseline's 1**. 69 heuristic flags, every one reviewed: numbers 8,
  dates 8, names 8, added numbers 45 — all the same value in another notation (`3,140`→`3140`,
  `2,840 EUR`→`2.840 EUR`, `4,100 USD`→`4.1k USD`, `September 25`→`9/25`), word→digit
  (`eleven`→`11`, `four years`→`4 years`), enumeration (`Step 1/2/3`) or a heading re-worded
  (`Little Cedar Group Opens Second…` → `Second Bristol Facility Launched by…`, company name
  intact). One compression worth knowing: the policy memo's "50 Mbps down and 10 Mbps up" becomes
  "50/10 (download/upload)" — both values survive, the unit is implied. No CJK output in 40
  rewrites; 42 formatting drops, all markdown markers.
- **Why Q6_K ships and Q4_K_M does not** (the same 20×2 instrument, one boot each, one variable):
  Q4_K_M (7.63 GB) is **29 % faster — 23.18 ± 0.19 t/s @ d0** — and loses **2 facts**: the
  tutorial's "about 90 minutes" became "A couple hours", and the trip report's year `2026` became
  `2006`. The falsifier was "no more genuine fact errors than the bf16 baseline (1/40)", so Q4_K_M
  is measured-rejected and Q6_K (10.03 GB) is the smallest tier that passes. Q8_0 (12.67 GB) and
  the `hoja-solutions` NVFP4 packs (8.25 GB, vLLM route) are unmeasured; the MLX packs and the
  CortiQ `.cmf` have no engine here.
- **Read honestly:** 0/40 vs 1/40 is not a quality *win* — the bar was "no worse than the
  baseline", and it met that. A one-event difference cannot rank two arms; the 29 % speed gap
  between Q6_K and Q4_K_M is far outside the 7–25 % inter-boot noise floor, which is why the
  quantization variable is the one that decided the ship. Sampling is per-request (temp 1.0,
  top_p 0.95, top_k off, min_p 0, rep 1.0, ≤2048 tokens); do not raise the temperature for longer
  drafts without re-running the instrument.
- **License:** Apache-2.0.
- **Receipts:** `head:~/benchmarks/humanizer-20261022-q6k/` (`boot.log`, `serve.log`,
  `models.json`, `decode-triage.{yaml,json,csv}`, `measure.json`, `analyze.log`, `probe-q6k.yaml`)
  and `head:~/benchmarks/humanizer-20261022/` for the Q4_K_M rejection; nodes `.33` and `.34`
  re-censused to 0 containers after each stop. Instrument: `tools/humanizer-measure.py` +
  `tools/humanizer-analyze.py`, guarded by `tests/test_humanizer_measure.py`.

## [zz-pyannote-community-1-diarization-cpu](zz-pyannote-community-1-diarization-cpu.yaml)

pyannote.audio on CPU + [`recipes/media/mods/pyannote-diarize-server`](mods/pyannote-diarize-server) ·
**1 node, CPU only** · **booted 2026-10-22** (task `4ee5df7e273859ab_64af2f7668b6`, HTTP-ready
9.56 s, stopped after measurement, 0 containers left).

- **Model:** `pyannote/speaker-diarization-community-1` (pinned `3533c8cf…`) — an 8.1M-param fp32
  speaker-diarization pipeline: a 5.9 MB powerset segmentation net over a 26.6 MB wespeaker ResNet34
  embedding net, plus VBx/PLDA clustering, all three bundled in one 33.7 MB repo.
- **Why it exists:** it is the instrument the drama-3 TTS arm lacks. It can report how many speakers
  a clip contains and whether speaker segments are self-consistent, and it cannot report whether any
  word was dropped. Served on 5 A725 cores at no GPU cost.
- **Route:** pyannote.audio + torch (aarch64 PyPI wheels) on CPU behind a stdlib HTTP server written
  by the lane mod — no engine here can serve it. `runtime: vllm` is only the launcher/distribution
  contract. Card DER 8.9 (REPERE) to 46.8 (Ego4D), no collar, overlaps scored.
- **Instrument:** measured by `tools/diarize-score.py` against `tools/diarize-fixture.py` (collar
  0.25, permutations mapped, DER>10% = falsifier), which scores who-spoke-when only: whether a TTS
  clip's words are intelligible still needs an ASR pass or the owner's ears.
- **Measured (2026-10-22, `.35`, 5 A725 cores, no GPU):** TTR port-open 9.540 s / HTTP-ready
  9.560 s from container start (`port_timeout_s: 1800` never bound); RTF **0.247** on an 11.4 s real
  two-voice dialogue and 0.62 on the 30 s synthetic file; **DER = JER 2.83 %** (collar 0.25, overlaps
  scored, speaker error 0) on `tier-b-two-voice.wav`; identical segments across repeat runs.
  Receipts: `.35:~/benchmarks-pyannote/`.
- **Tier A is adversarial by construction:** synthetic harmonic stacks are adversarial to
  embedding-based clustering — the arm reports **one speaker for a 2- and a 3-voice tonal file
  (DER 50.0 / 69.9 %, unchanged when the count is forced)**, while real speech scores DER/JER
  2.83 %. The failure is the fixture, not the arm; the tier-A bar must be evaluated on
  `tier-b-two-voice.wav`. Fixture hashes are not quoted in docs on purpose — the fixture manifest is
  the single source of truth and `tools/diarize-fixture.py --check` proves it, including that the
  files are real RIFF/WAVE containers (an earlier `--check` passed on headerless PCM).
- **Image:** boots only on an image carrying `libgomp1` (the aarch64 torchaudio wheel links
  `libgomp.so.1`; `python:*-slim` has no GCC OpenMP runtime) and the server must decode the WAV
  in-process, because torchaudio 2.8's only decode backend (torchcodec) dlopens `libnvrtc` and
  cannot load on a CPU-only image. `pyannote-cpu:4.0.7` on `.35` is that image
  (`~/pyannote-img/Dockerfile`), and the recipe documents both requirements next to the base digest.
- **License:** CC-BY-4.0, gated (auto-approve form), so preparing the snapshot needs an HF token
  with the conditions accepted on the launching host.

## [phonon-31m-tts-cpu](phonon-31m-tts-cpu.yaml)

`ptts` (PyPI, the vendor runtime) on `python:3.12-slim` +
[`recipes/media/mods/phonon-tts-server`](mods/phonon-tts-server) ·
**1 node, CPU only** · **authored and boot-verified 2026-10-25 (`.35`)** — the
kokoro-82m-tts-cpu shape (`runtime: vllm` as the launcher contract, `readiness.inference:
false`, kill shim, `distribution_config.models.enabled: false` because the server reads the
pool snapshot itself through the mod's real-file copy).

- **Contract:** `POST /v1/audio/speech` with `{"input": text, "seed": N}` (seed default 1234)
  answers 24 kHz mono 16-bit WAV; `GET /health` carries the model id + revision. The mod gates
  fail-closed: it stages the `ptts` venv (floor 0.4.1), a **real-file copy** of the checkpoint
  (a symlinked snapshot fails ptts' checkpoint check — measured), and the server at
  `/cache/runtime/phonon/`.
- **Boot receipt (`.35`, fixed recipe):** TTR **8.227 s** port-open / **8.257 s** HTTP-ready;
  c1 render **0.622 s wall for 4.56 s audio (RTF 0.136)**, repeat 0.641 (RTF 0.140); h01
  structured-data render 0.776 s / 7.52 s (**RTF 0.103**) — RTF consistent with the 2026-10-24
  probe (~0.17), byte-length identical to it.
- **Why this arm ships beside kokoro:** it **won the hard-sentence WER A/B** (literal WER
  **0.1747 vs kokoro 0.2329**, section above) — the two CPU TTS arms now split on measured
  strengths; clients choose per text class. Known limit (measured, both boots): **not
  byte-deterministic per invocation** — same seed/text, different PCM; score at the
  transcript/metric level. English only; Apache-2.0 (the 40m siblings are CC BY-NC).
- **Boot chain fixes recorded in the recipes' history:** the server accepts the
  runtime-appended `--served-model-name`; render uses the venv's `ptts` binary explicitly
  (`--ptts`); `--model-dir` feeds the render config; an explicit `command:` template consumes
  only placeholders, so every server flag is spelled in the template.
- **Receipt:** `head:~/benchmarks/tplt4-20261024/phonon-arm/` (`boot*.launch.log`,
  `RENDER-TIMINGS.txt`, `c1-boot5.wav`), stopped by literal task id, 0 containers after.

## Mods

All lane-local; each is referenced **unscoped** as `mods/<name>`, which sparkrun resolves adjacent
to the recipe (`core/mods.py` rule 2):

| mod | used by |
|---|---|
| [`ltx-25-launcher`](mods/ltx-25-launcher) | the LTX-2.5 recipe |
| [`qwen-image-2.1-turbo-launcher`](mods/qwen-image-2.1-turbo-launcher) | the shipped Qwen-Image recipe and its 4-step probe |
| [`qwen-image-sigmas`](mods/qwen-image-sigmas) | no recipe reference — the prior 4-step server, kept with the arm it was written for |
| [`pyannote-diarize-server`](mods/pyannote-diarize-server) | the pyannote diarization recipe |

## Lane notes

The bring-up notes written while these arms lived in Explore stay in that archive, frozen:

| file | what it holds |
|---|---|
| [`attic/explore/QWEN-IMAGE.md`](../../attic/explore/QWEN-IMAGE.md) | Qwen-Image-2.1-Turbo bring-up: license banner, engine/venv design, the §6 acceptance table, the two mod defects, and the faster vLLM-OMNI route (measured 2026-10-21; its separate arm booted 2026-10-22). |
| [`attic/explore/LTX-25.md`](../../attic/explore/LTX-25.md) | LTX-2.5 bring-up: access/prerequisite, the pinned ComfyUI unit, weights, the two-stage measurement table, the traps re-learned. |
| [`attic/explore/EXPLORE-MODELS-RESEARCH.md`](../../attic/explore/EXPLORE-MODELS-RESEARCH.md) §6–§7 | The media-gen and humanizer research passes that produced these arms. |
| [`attic/explore/AGENTS.md`](../../attic/explore/AGENTS.md) | Per-arm measured histories and serving traps, including drama-3 and the media-gen arms. |

The humanizer bf16 sibling and the media-gen probes that never shipped remain archived under
[`attic/explore/`](../../attic/explore/) — the archive is frozen provenance, so a retired arm is
not resurrected into this lane.

## Lane notes (pyannote arm, 2026-10-22)

- **A `--check` that compares sha256 proves byte-stability, not shape.** The fixture builder wrote raw
  PCM frames under a `.wav` name, so `--check` and the determinism cells both passed on files no
  decoder could open; the arm then answered `400 file does not start with RIFF id`. `--check` now
  decodes every fixture as well as comparing bytes, and a guard goes red on headerless PCM.
- **Push history, for anyone reading a reflog:** commit `92b7931` quoted the tier-A *reference speech
  seconds* (20.0 / 24.0) as DER; the real values are 50.0 % / 69.9 %. It was replaced by `811f67f`
  with a `--force-with-lease` over my own commit — the one sanctioned force-push case here. `92b7931`
  may survive in another clone's reflog carrying the wrong numbers; `811f67f` is the record.
