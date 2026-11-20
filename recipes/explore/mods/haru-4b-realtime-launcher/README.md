# `haru-4b-realtime-launcher` — the duplex acceptance probe

`probe.py` is the arm's acceptance client. It opens one conversation on the
serve's realtime duplex WebSocket, feeds a fixed synthetic clip frame by frame,
prints a summary, and exits non-zero when the session delivers nothing.

It is a fixture, not a shipped tool: it lives beside `run.sh` and `deploy/haru.yaml`
because sparkrun copies this mod to `/workspace/mods/haru-4b-realtime-launcher/`
at boot, so the script is already inside the serve container. A separate
`mods/haru-4b-realtime-client/` directory would have to ship a `run.sh` to pass
`tests/test_mods_lane_locality.py` (every lane mod dir does), i.e. a boot-time
mod whose only job is to make a file appear. This one costs no boot step.

## The client is the wheel's, not this repo's

The protocol is vLLM-Omni's realtime duplex API (OpenAI Realtime events), and
`haru-speech==0.1.1` already ships a client for it. Inspected from PyPI, not from
the fleet:

- `haru_speech-0.1.1-py3-none-any.whl`, `entry_points.txt`:
  `haru-inference = haru.run_inference:main` and `haru-server = haru.server:main`.
  `haru-server` is the browser demo (it serves `haru/static/`), so it is not a
  headless acceptance client.
- `haru/backends.py` is the importable client: `VllmBackend` (:279) opens
  `ws://<host>/v1/realtime?duplex=1` (`:220`), sends `session.update`, waits for
  `session.created`, then one `input_audio_buffer.append` of 3,200 `pcm_f32le`
  samples per `step()` (:232) and returns the matching `response.output_audio.delta`
  (PCM16, 24 kHz) plus any `response.output_audio_transcript.delta`.
- The same module documents the two facts the probe relies on: `speak_first`
  makes the model open the conversation, and `ref_audio` is optional
  (`haru_vllm/duplex/plugin.py:_decode_reference` returns silence for a missing
  reference), so no voice clip has to be recorded to run this.

So `probe.py` is a driver, ~150 lines: the character card, a synthetic clip, the
frame loop, timeouts and the verdict. No protocol code is re-implemented; a
change in the wire format is the wheel's to make.

`haru.backends` imports `haru.session` → `torch`/`transformers`, so this runs only
where those exist — inside the serve container. `run.sh` Gate 3 imports it at
every boot, so a wheel whose client surface is broken fails the launch by name
instead of at receipt time.

## Invocation

Inside the serve container, after readiness:

```bash
python3 /workspace/mods/haru-4b-realtime-launcher/probe.py --url http://127.0.0.1:8000
```

From the head or the node, without entering the container:

```bash
docker exec "$(docker ps -qf name=haru)" python3 /workspace/mods/haru-4b-realtime-launcher/probe.py --url http://127.0.0.1:8000
```

Flags: `--url` (default `http://127.0.0.1:8000`), `--frames` (default 8 appends
after the opening frame, 8 × 133 ms of input), `--timeout` (seconds for `/health`
and for frame 0, default 600), `--step-timeout` (per output frame, default 60),
`--no-speak-first` (the model listens until the input sounds like speech).

The clip is generated, not tracked: `voiced_clip()` is a 110-130 Hz pulse train
through two formants with a ~2 Hz syllable envelope, peak 0.3, deterministic, so
the receipt carries the formula instead of a binary. It is speech-*like* (voiced
energy, syllabic), not speech: it proves the input path carries real audio, not
that the model transcribes.

Seed is fixed at 1234, so two runs against the same serve should produce the
same frames.

## What a pass looks like

Exit 0, with these lines. This block is a **template**: the arm is unbooted, so
every number in it is a placeholder and none is a measurement.

```text
endpoint: ws://127.0.0.1:8000/v1/realtime?duplex=1
card: 1180 chars, seed 1234, speak_first True, 8 appends
phase health: waiting for /health (<= 600 s)
phase session: session.update, then session.created and frame 0 (<= 600 s)
phase frames: 8 appends, one output frame each (<= 60 s per frame)
health: /health answered after 0.0 s
frames: in 9 (the first opens the session), out 9
audio: 28800 samples at 24000 Hz, 9 of 9 frames non-silent, peak 0.412
text: 34 chars, first 160: 'Hey, hi! I was just thinking about'
timing: opening frame 12.40 s; steps median 168 ms, min 141 ms, max 402 ms
probe ok: the duplex session delivered output
```

Exit codes, and what each one is evidence for:

| rc | last line | means |
|:--|:--|:--|
| 0 | `probe ok: the duplex session delivered output` | frames arrived and at least one carried audio or text |
| 2 | `probe silent: frames delivered, all silent and textless` | the transport and the engine step work; the model produced nothing. A finding about the model, not the wire |
| 1 | `probe failed: <Type>: <message>` | no output frame. The preceding `phase` line names the wait that expired, so a timeout is attributable |

A receipt quotes the block verbatim plus the exit code. `frames: out` counts
model frames; `in` is appends. `opening frame` is the prompt run (card + the
session's first append); `steps` are the steady-state frame times and are the
first real-time-factor evidence this arm produces.

## What it does not prove

- Real-time behaviour. The probe sends frames back to back, not on a 133 ms
  clock, so `steps median` is compute per frame, not latency under a real
  conversation. A duplex latency claim needs a paced client.
- Anything about reply quality: one synthetic vowel, one seeded conversation.
- That the character card reached the model. `instructions` is sent in
  `session.update` and the plugin refuses to change it after creation; the
  probe prints the card's length as the only visible confirmation.
- Multi-session behaviour (`duplex_session.max_sessions: 2` is untested here).
- Anything on a second node: this is a TP=1 arm by construction.
