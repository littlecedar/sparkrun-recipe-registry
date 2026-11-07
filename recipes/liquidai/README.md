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
picks the instrument the deliverable needs: `benchmarking/concurrency-ladder.yaml`
(`llama-benchy`) and `benchmarking/standard-suite.yaml` for the **text** arms; the decision ladder
(`tools/decision-ladder.py`, `tools/jev-decision-bench.py`) for `d1-*`; and for `LFM3-Audio-2B` a
word error rate against known text — [`tools/audio-asr-tts-probe.py`](../../tools/audio-asr-tts-probe.py)
scores `/v1/audio/transcriptions` against the sentence the clip is known to speak, then speaks that
sentence back through `/tts` and scores the round trip. Reporting a `C1 t/s` from an audio model
would be a category error, not a measurement.

**Vision has no instrument yet, and that is a scope fact rather than a gap to paper over.**
`benchmarking/standard-suite.yaml` is tool-eval-bench's core 15 — text tool-calling, greedy, 8
turns — and carries no image or audio task; nothing else in this tree scores image understanding
(`tools/pooling-bench.py`'s `image_url` paths feed *embedding and rerank* arithmetic, not a VLM
answer, and `tools/synthetic_png.py` synthesises solid-colour fixtures for those). So
`liquidai-lfm3-vl-2b-arm` and `liquidai-lfm3-omni-2b-arm` can honestly produce throughput and
**acceptance** — the request took an image part and the reply was not blank — never an accuracy
number, and a queue row promising them a "standard suite" score overstates what exists. The media
lane's whistle chain is speech in, not vision. The speech member is the only one of the three with
a real quality cell, which is why `zz-liquidai-lfm3-audio-2b-llamacpp` is the only one of them
authored so far.

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

**The family's decision members live in the decision lane.** `d1-2B` ships as
[`recipes/decision/liquidai-d1-2b-q8-systemone-llamacpp.yaml`](../decision/liquidai-d1-2b-q8-systemone-llamacpp.yaml)
because its instrument does — a prefill-only `/v1/systemone` scorer measured by
`tools/decision-ladder.py`, never `llama-benchy`. It is a `lfm3_vl` fine-tune of `LFM3-VL-2B`, so
it also needs the `lfm3vl` projector, which the same pinned llama.cpp build carries; a d1 arm
alone covers the endpoint and head-semantics question that `d1-Omni-2B` then extends with audio.

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

## Control arm — `zz-liquidai-lfm3-1.7b-base-f16-llamacpp` (booted 2026-11-07)

The fine-tune control for this lane's instruct pair: `LiquidAI/LFM3-1.7B-Base`, the same tokenizer
and conv+attention body without instruction training. It keeps `zz-` until a second boot
reproduces the cells below. Recipe [`zz-liquidai-lfm3-1.7b-base-f16-llamacpp.yaml`](zz-liquidai-lfm3-1.7b-base-f16-llamacpp.yaml).

**Why an F16 GGUF and not a vendor mirror.** No first-party base GGUF exists —
`LiquidAI/LFM3-1.7B-GGUF` carries the *instruct* weights only (BF16/F16/NVFP4/Q4_K_M/Q5_K_M/Q6_K/Q8_0/
QAD-Q4_0), so the instruct mirror is exactly what a base control must not use. The base weights were
therefore converted here: llama.cpp `6023692`'s own `conversion/lfm3.py` registers
`Lfm3ForCausalLM` and even names `LiquidAI/LFM3-1.7B-Base` as its example. The conversion runs
**outside** the runtime image, because that image ships no Python (only `llama-server` and
`llama-cli`):

```bash
# one-shot, CPU only, no GPU and no cluster: ~3.5 min once torch is in the env
curl -sL https://codeload.github.com/ggml-org/llama.cpp/tar.gz/6023692 | tar xz
cd llama.cpp-6023692
uv run --no-project --with torch --with numpy --with transformers --with huggingface_hub \
       --with requests python convert_hf_to_gguf.py --outtype f16 --remote LiquidAI/LFM3-1.7B-Base \
       --outfile LFM3-1.7B-Base-F16.gguf
```

The result is 3,466,613,856 B / 287 tensors, `general.architecture = lfm3`,
`general.finetune = 7bca5038…`, 24 blocks, native context 262,144, sliding window 256, gpt2 BPE
tokenizer, **no embedded chat template** — and it is the same byte size as the vendor's instruct F16,
which is the shape check that the conversion is faithful. sha256
`86bfa3eb5f6cf0c297e4b84b26049db064ce829d64ec39d20dbdb90884626eef`.

**Where the file lives.** The shared pool, as a hand-placed cache entry:
`/mnt/beegfs/huggingface/hub/models--littlecedar--LFM3-1.7B-Base-GGUF/` with `blobs/86bfa3eb…`,
`snapshots/7bca5038…/LFM3-1.7B-Base-F16.gguf`, `refs/main` and `trees/7bca5038….json`. The recipe's
`model:` names that repo id, so **publish `littlecedar/LFM3-1.7B-Base-GGUF` with this file before any
host that is not pool-mounted boots the arm** — sparkrun's offline probe resolves the pool copy, its
download path cannot.

**The cells this arm can honestly produce.** A base model has no chat template and no instruction
following, so the lane's house battery and tool suite would measure their own 400. The arm serves raw
completions, and its cells come from llama.cpp's own per-request `timings` — engine-native, the same
instrument class the lane's llama.cpp rule already names. Save this beside the receipt and run it
against the live serve (prompt is a ~2,000-token filler so pp is a real prefill, and
`cache_prompt: false` keeps it from being a cache hit):

```bash
cat > raw-ladder.py <<'EOF'
import json, statistics, threading, time, urllib.request
B, M = "http://<node>:8000", "LiquidAI/LFM3-1.7B-Base"
prompt = "the quick brown fox jumps over the lazy dog. " * 220
def one(n=128):
    body = json.dumps({"prompt": prompt, "n_predict": n, "temperature": 0,
                       "cache_prompt": False}).encode()
    r = urllib.request.urlopen(urllib.request.Request(
        B + "/v1/completions", body, {"Content-Type": "application/json"}), timeout=600)
    t = (json.load(r).get("timings") or {})
    return t.get("prompt_per_second"), t.get("predicted_per_second")
for c in (1, 10):
    cells, lock = [], threading.Lock()
    def work():
        got = one()
        with lock: cells.append(got)
    ts = [threading.Thread(target=work) for _ in range(c)]
    [t.start() for t in ts]; [t.join() for t in ts]
    pp = [x[0] for x in cells if x[0]]; tg = [x[1] for x in cells if x[1]]
    print(f"c={c}: pp {statistics.median(pp):.1f} t/s, tg {statistics.median(tg):.1f} t/s (n={len(cells)})")
EOF
python3 raw-ladder.py     # repeat at c=1 n=5 and quote medians, never one sample
```

`accuracy_status: n/a` — base weights, raw completions; a score from a chat battery would measure the
absence of a template, not the model. `tools/run-arm.sh` should not drive this arm either: its generic
branch runs the chat ladder and the standard suite, both of which address `/v1/chat/completions`.

**Measurement (2026-11-07, `.30`, task `sparkrun_8570e971ede06a8c_1bf4b73daabb`).** First boot,
`raw-ladder.py` against the live serve, medians of five runs per cell, `cache_prompt: false`:

| cell | pp t/s | tg t/s |
|---|---:|---:|
|c1 (n=5)|10,197.23|63.77|
|c10 (n=5)|2,270.66|37.48|

`prompt_n` 2201, `predicted_n` 128 — engine-native timings, so the cells are the model's own
prefill and decode rather than a harness's view. Read `c10` as serialisation, not concurrency: the
arm serves `parallel: 1`. `accuracy_status: n/a` is recorded for the reason above — the house and
tool batteries speak chat and would score a missing template. Receipt
`~/benchmarks/tp12-20261107/zz-liquidai-lfm3-1.7b-base-f16-llamacpp/`. No instruct comparison is
claimed from these numbers alone: the instruct arms were measured under `llama-benchy`'s depth-0
shape, and a base decoder's `tg` over a filler prompt is not the same measurement.

**Launch (ready for the operator's next `.30` slot):**

```bash
sparkrun run recipes/liquidai/zz-liquidai-lfm3-1.7b-base-f16-llamacpp.yaml -H <node> --cluster WOPR
```

## Audio arm — `zz-liquidai-lfm3-audio-2b-llamacpp` (authored 2026-11-07, not booted)

The family's speech member — `LiquidAI/LFM3-Audio-2B`, ASR and TTS in one 2B hybrid
conv+attention body. Recipe
[`zz-liquidai-lfm3-audio-2b-llamacpp.yaml`](zz-liquidai-lfm3-audio-2b-llamacpp.yaml), `zz-` until a
boot produces cells.

**Route decided from evidence, and it is the server — not the card's `llama-tts` script.** The card
documents `llama cli --audio` and a `llama-tts -o out.wav` binary; this image ships neither
(`/usr/local/bin` holds `llama-server` and `llama-cli` only), so a script arm would be unrunnable and
an image build would be unjustified. What the pin actually contains, read before authoring:

| evidence | reading |
|---|---|
| GGUF `general.architecture = lfm3`, 24 blocks, 128,000 ctx, 2,048 embed | the decoder is the same `lfm3` body the text arms already load |
| projector GGUF `general.architecture = clip`, `clip.has_audio_encoder = 1`, 285M | audio goes in through the ordinary mtmd media path, not a bespoke one |
| GGUF carries `tokenizer.chat_template` (9,328 B) **and** `chat_template.tts` (875 B, language-name map) | the renderer the endpoints need ships in the file |
| `tools/server/server.cpp` at `6023692` registers `POST /v1/audio/transcriptions`, `POST /tts`, WS `/v1/realtime` | both directions are HTTP surface of the pinned server |
| `common/chat.cpp` at the pin has `lfm3_asr_system_prompt()` (ISO code → language name, auto-detect when absent) and `common_chat_get_tts_prompt()` reading the model's `tts` template; `server-context.cpp` names **LFM3-Audio** as the model that renders its TTS prompt from that template | first-class support for this family, not a generic audio toy |
| binary strings: `/v1/audio/speech` absent, `/tts` present, no `llama-tts` executable | TTS is `/tts`, not the OpenAI speech route, and not a second process |

So the arm is a server recipe: `--mmproj` beside the weights, ASR at
`/v1/audio/transcriptions`, TTS at `/tts`. F16 weights and F16 projector on purpose — this is the
lane's measurement arm for speech, and quantisation noise has no business in a word-error-rate cell.

**Cells, and what they can assert.** [`tools/audio-asr-tts-probe.py`](../../tools/audio-asr-tts-probe.py)
runs three against one boot:

| cell | request | asserts |
|---|---|---|
| `asr` | multipart `/v1/audio/transcriptions` with the drama-3 clip | transcript scores **WER ≤ 0.25** against the sentence the clip is known to speak |
| `tts` | `POST /tts {"input": <that sentence>, "lang": "en", "response_format": "wav"}` | a RIFF/WAVE body with a real duration, a sample rate and non-silent PCM — not an HTTP 200 |
| `roundtrip` | the synthesised wav back through the ASR endpoint | **WER ≤ 0.40** against the text it was asked to speak |

Falsifiers, all in the tool's `--selftest`: a transcript produced without hearing the audio scores
1.0 against the ground truth and fails the cell; a round trip whose transcript is a paraphrase crosses
its threshold; silence is rejected by the wav check rather than counted as speech; a server that
answers `/tts` with 501 "does not support audio generation" surfaces that body instead of a null.

**Cannot prove.** This is one clean sentence from one voice. It says nothing about accent, noise,
overlap, long-form or another language, and the round trip is bounded by the same model on both
ends, so it measures mutual intelligibility of its own render — never a MOS or a listener's verdict.
A low WER here is the arm being alive and hearing one fixture, not an ASR benchmark. The media lane's
whistle chain is the reference instrument when renders have no ground-truth text.

**`accuracy_status: n/a`** for the house battery for the same reason as the omni arm: the battery
speaks chat tool-calling and cannot address a speech arm.

```bash
python3 tools/audio-asr-tts-probe.py --selftest        # offline stub, ~1 s

# the cells
python3 tools/audio-asr-tts-probe.py \
  --base-url http://<node>:8022 \
  --wav ~/benchmarks/omni-repin-20261107/drama-weights/drama.wav \
  --statement "The quarterly report is due on Thursday, so please finish it by noon." \
  --lang en --json ~/benchmarks/tp12-$(date +%Y%m%d)/zz-liquidai-lfm3-audio-2b-llamacpp/asr-tts.json
```

**Launch (ready for the operator's next `.30` slot):**

```bash
sparkrun run recipes/liquidai/zz-liquidai-lfm3-audio-2b-llamacpp.yaml -H <node> --cluster WOPR
```

## Vision arm — `zz-liquidai-lfm3-vl-2b-llamacpp` (authored 2026-11-07, not booted)

`LiquidAI/LFM3-VL-2B` — the lane's 1.7B body plus a 189M vision tower, vendors' Q4_K_M weights and
the release's smallest projector (Q8_0). Recipe
[`zz-liquidai-lfm3-vl-2b-llamacpp.yaml`](zz-liquidai-lfm3-vl-2b-llamacpp.yaml).

**Cells it produces, and nothing more.** No image-quality instrument exists here (§Instruments), so
the arm is measured on cost and acceptance:

| cell | instrument | asserts |
|---|---|---|
| image cost | [`tools/vl-arm-probe.py`](../../tools/vl-arm-probe.py): the same prompt twice, with and without the picture | `usage.prompt_tokens` difference = the image's token cost; `n_ctx` ÷ cost = how many images fit |
| prefill / decode | the engine's own per-request `timings`, `cache_prompt: false` | image prefill t/s against text-only prefill t/s (the ratio is what an image costs in wall time), plus decode parity |
| footprint | the boot's serve log, parsed — `model size`, `KV self size`, `model buffer size` | resident trunk + tower and KV for the served window, measured not estimated |
| acceptance | the same probe | the `image_url` part was taken and the reply was non-blank |

**What acceptance is not.** A model that ignored the image answers non-blank too, so a pass here
proves the request was served, never that it was understood. The fixture is a synthetic solid colour
from `tools/synthetic_png.py` — the same patch grid a photograph presents to the tower, so token
count and prefill cost are fair; flat pixels say nothing about answering photographic content.
`accuracy_status: n/a`, and no standard-suite number is claimed: that suite is text tool-calling.

```bash
python3 tools/vl-arm-probe.py --selftest        # offline stub, ~1 s
python3 tools/vl-arm-probe.py \
  --base-url http://<node>:8023 \
  --prompt "Describe this image in one sentence." \
  --serve-log ~/benchmarks/tp12-$(date +%Y%m%d)/zz-liquidai-lfm3-vl-2b-llamacpp/serve.log \
  --json ~/benchmarks/tp12-$(date +%Y%m%d)/zz-liquidai-lfm3-vl-2b-llamacpp/vl.json
```

**Launch (ready for the operator's next `.30` slot):**

```bash
sparkrun run recipes/liquidai/zz-liquidai-lfm3-vl-2b-llamacpp.yaml -H <node> --cluster WOPR
```

## Omni arm — `zz-liquidai-lfm3-omni-2b-llamacpp` (authored 2026-11-07, not booted)

`LiquidAI/LFM3-Omni-2B` — vision and speech in, through one 475M projector that carries both towers
(the GGUF reads `clip.has_vision_encoder = 1` **and** `clip.has_audio_encoder = 1`, arch `lfm3`, so
this pin loads it). Recipe [`zz-liquidai-lfm3-omni-2b-llamacpp.yaml`](zz-liquidai-lfm3-omni-2b-llamacpp.yaml).

**Two cells, one boot**, which is the whole point of the row:

| half | instrument | what it asserts |
|---|---|---|
| vision | `tools/vl-arm-probe.py`, port 8024 | image token cost, image-vs-text prefill, footprint from the serve log, acceptance |
| speech | `tools/audio-asr-tts-probe.py` against the same port | `/v1/audio/transcriptions` WER on the drama fixture, `/tts` returns real audio, round-trip WER |

**The audio half is a measurement, not an assumption.** d1-Omni-2B's `/v1/systemone` refused audio on
this build by tokenising the base64 as text (364,286 tokens, 500). This arm asks a different endpoint —
the generative chat/mtmd path and `/v1/audio/transcriptions` — so it may work; if it does not, the
probe records the endpoint's own body and the cell fails loudly. Either answer is the result, and
neither is written down as expected here.

`accuracy_status: n/a` for vision for the same reason as the arm above, and a reachable audio cell
still scores one known-text fixture only.

```bash
python3 tools/vl-arm-probe.py --base-url http://<node>:8024 --serve-log <receipt>/serve.log \
  --json <receipt>/vl.json
python3 tools/audio-asr-tts-probe.py --base-url http://<node>:8024 \
  --wav ~/benchmarks/omni-repin-20261107/drama-weights/drama.wav \
  --statement "The quarterly report is due on Thursday, so please finish it by noon." \
  --lang en --json <receipt>/asr-tts.json
```

**Launch (ready for the operator's next `.30` slot):**

```bash
sparkrun run recipes/liquidai/zz-liquidai-lfm3-omni-2b-llamacpp.yaml -H <node> --cluster WOPR
```

## Fine-tuning

`finetuning/` is where the toolkit survey lands — one entry per toolkit that can actually train an
`lfm3` custom-code, conv-hybrid stack on aarch64/Blackwell, with the blocker that decided it. See
[`finetuning/README.md`](finetuning/README.md). Position as of 2026-11-03: the
`transformers`+`peft`+`trl` reference path is **usable** and was measured on CPU; Axolotl 0.21.1 is a
usable patch with `sample_packing: false`; five other candidates are rejected with their failing gate
recorded. The binding constraint is not the conv layers — it is that `lfm3` ships outside
`transformers` entirely and its custom code needs `transformers>=5.18.0` (5.15/5.16 load but fail on
the first forward, 5.17.0 fails at config load).