# pyannote-diarize-server

Writes the DRAFT pyannote speaker-diarization HTTP server to
`${MOD_CACHEDIR:-/cache/runtime}/pyannote/diarize_server.py` so a recipe can name the
path unconditionally, and refuses the launch if the bundled file does not compile.

Used by `recipes/media/zz-pyannote-community-1-diarization-cpu.yaml` only. It exists
because `pyannote/speaker-diarization-community-1` is a `pyannote.audio` pipeline with no
published server image and no engine in this registry that can serve it (see the lane
item in `mad-science/TODO.md` §explore).

## Contract

| Route | Shape |
|---|---|
| `GET /health` | `{"status":"ok","model":"pyannote/speaker-diarization-community-1","revision":…,"device":"cpu","threads":N}` |
| `POST /diarize` | body = raw WAV bytes (mono/stereo, any rate; the pipeline downmixes and resamples to 16 kHz). Optional query `num_speakers`, `min_speakers`, `max_speakers`. Returns `{"num_speakers", "segments":[{start,end,speaker}], "audio_seconds", "exclusive_segments"}` |

Behaviour worth knowing:

- `POST /diarize` is **serial** (`HTTPServer`, not the threading variant): diarization is
  an offline batch job and the pipeline's clustering is not documented as thread-safe.
- The raw-body contract exists so the server needs no multipart parser; a client sends
  `curl --data-binary @file.wav`.
- `PYANNOTE_MODEL_PATH` must be the prepared snapshot (the recipe passes `{model}`), so
  the pipeline never re-resolves the gated repo at request time.
- Determinism is an instrument requirement, not a knob: `torch.set_num_threads()` is
  fixed from `PYANNOTE_THREADS` (default 5, matching the recipe's `taskset` span) and
  nothing in the request path samples.

## Not claimed

This mod has **never run in a container**: the draft recipe is research-only and no boot
has happened (all six nodes were busy on 2026-10-22). `pyannote.audio`'s exact response
shape is taken from the model card's quick start (`output.speaker_diarization`), not from
a measured call.
