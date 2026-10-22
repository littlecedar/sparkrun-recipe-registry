#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Materialize the DRAFT pyannote diarization HTTP server at a path the recipe can name
# unconditionally.
#
# Why this exists:
#   `pyannote/speaker-diarization-community-1` is a pyannote.audio *pipeline* (a
#   segmentation net + a wespeaker embedding net + VBx/PLDA clustering), not a chat
#   model. No engine this registry pins can serve it -- sparkrun has no runtime family
#   for it either -- and upstream publishes no server image: the card's only dependency
#   is `pip install pyannote.audio` and the only documented entry point is the Python
#   API. So the arm is a small Python server behind the `runtime: vllm`
#   launcher/distribution contract, the kokoro/laya precedent, and the server has to
#   come from somewhere. This mod is that somewhere.
#
# What it does:
#   1. Writes the server to ${SERVER_DIR}/diarize_server.py (a sparkrun-managed cache
#      path), rewriting only when the bundled text changed, so a re-launch is idempotent.
#   2. Compiles the written file in-process before allowing the launch: a syntax error
#      here would otherwise surface as a dead port minutes into the pip install.
#   3. Hands the directory back to the cache owner, since mods run as root.
#
# The server contract (the lane's instrument drives it):
#   GET  /health   -> {"status":"ok","model":...,"revision":...,"device":"cpu"}
#   POST /diarize  -> raw WAV body; optional ?num_speakers=N / ?min_speakers= /
#                     ?max_speakers=; returns {"num_speakers", "segments",
#                     "audio_seconds", "exclusive_segments"}.
# The model path and revision arrive from the recipe as PYANNOTE_MODEL_PATH /
# PYANNOTE_REVISION, i.e. sparkrun's prepared snapshot, so the arm loads offline and the
# `model_revision:` pin decides the bytes.
#####################################################################

export MOD_NAME="pyannote-diarize-server"
export MOD_DESCRIPTION="Write the DRAFT pyannote speaker-diarization HTTP server into the runtime cache"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"
export TIMEOUT="${MOD_TIMEOUT:-180}"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CACHEDIR="${MOD_CACHEDIR:-${XDG_CACHE_HOME:-/cache/runtime}}"
export LOGDIR="${MOD_LOGDIR:-${CACHEDIR}/modlogs}"
export SERVER_DIR="${SERVER_DIR:-${CACHEDIR}/pyannote}"
export SERVER_DEST="${SERVER_DIR}/diarize_server.py"

reown() {
  if [[ "$(id -u)" != "0" ]]; then
    log "reown: not root (uid $(id -u)); skipping chown of ${*}"
    return 0
  fi
  log "resetting permissions to ${USER_UID}:${USER_GID} on ${*}"
  chown -R "${USER_UID}:${USER_GID}" "${@}"
}

log() {
  local _ts
  _ts="$(date -Ins)"
  printf '%s [%s] %s\n' "$_ts" "${MOD_NAME}" "${*}" | tee -a "${LOGDIR}/${MOD_NAME}.log"
}

if [[ ! -d "${CACHEDIR}" ]]; then
  echo "${MOD_NAME}: runtime cache ${CACHEDIR} is not mounted" >&2
  exit 1
fi
export USER_UID="$(stat -c '%u' "${CACHEDIR}")"
export USER_GID="$(stat -c '%g' "${CACHEDIR}")"

mkdir -p "${LOGDIR}" "${SERVER_DIR}"
if [[ -f "${LOGDIR}/${MOD_NAME}.log" ]]; then
  gzip -c "${LOGDIR}/${MOD_NAME}.log" > "${LOGDIR}/${MOD_NAME}.log.gz"
fi
: > "${LOGDIR}/${MOD_NAME}.log"
reown "${LOGDIR}"

log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log "${MOD_MAINTAINER}"

tmp="$(mktemp "${SERVER_DIR}/.diarize_server.XXXXXX.py")"
trap 'rm -f "${tmp}"' EXIT

cat > "${tmp}" <<'PY'
#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group
# SPDX-License-Identifier: AGPL-3.0-or-later
"""DRAFT pyannote diarization server: GET /health, POST /diarize (raw WAV body).

Written by mods/pyannote-diarize-server. PYANNOTE_MODEL_PATH is sparkrun's prepared
snapshot, so the pipeline loads offline and the recipe's pin decides the bytes.
"""
import io
import json
import os
import sys
import urllib.parse
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer

import torch
import torchaudio.functional
from pyannote.audio import Pipeline

MODEL_PATH = os.environ["PYANNOTE_MODEL_PATH"]
REVISION = os.environ.get("PYANNOTE_REVISION", "")
HOST = os.environ.get("PYANNOTE_HOST", "0.0.0.0")
PORT = int(os.environ.get("PYANNOTE_PORT", "8881"))
THREADS = int(os.environ.get("PYANNOTE_THREADS", "5"))
MAX_BYTES = 512 << 20
SAMPLE_RATE = 16000


def load_wav(raw):
    """Raw 16-bit PCM WAV bytes -> pyannote's in-memory input.

    Decoding here rather than handing the pipeline a path is deliberate: torchaudio 2.8
    decodes only through torchcodec, whose aarch64 wheel dlopens libnvrtc (a CUDA runtime
    lib) at import, so a path input fails on a CPU-only image. A dict input never touches
    torchcodec.
    """
    with wave.open(io.BytesIO(raw), "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError("16-bit PCM wav required")
        channels = w.getnchannels()
        sr = w.getframerate()
        pcm = torch.frombuffer(bytearray(w.readframes(w.getnframes())), dtype=torch.int16)
    signal = pcm.float().div_(32768.0).view(-1, channels).mean(dim=1)
    if sr != SAMPLE_RATE:
        signal = torchaudio.functional.resample(signal, sr, SAMPLE_RATE)
    return {"waveform": signal.unsqueeze(0), "sample_rate": SAMPLE_RATE}


def turns(annotation):
    return [
        {"start": round(seg.start, 3), "end": round(seg.end, 3), "speaker": label}
        for seg, _, label in annotation.itertracks(yield_label=True)
    ]


class Handler(BaseHTTPRequestHandler):
    pipeline = None

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _reply(self, code, body):
        data = json.dumps(body, sort_keys=True).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if urllib.parse.urlparse(self.path).path != "/health":
            return self._reply(404, {"error": "not found"})
        self._reply(200, {
            "status": "ok",
            "model": "pyannote/speaker-diarization-community-1",
            "revision": REVISION,
            "device": "cpu",
            "threads": THREADS,
        })

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        if url.path != "/diarize":
            return self._reply(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BYTES:
            return self._reply(400, {"error": "raw wav body required (Content-Length 1..%d)" % MAX_BYTES})
        query = urllib.parse.parse_qs(url.query)
        kwargs = {k: int(query[k][0]) for k in ("num_speakers", "min_speakers", "max_speakers") if k in query}
        raw = self.rfile.read(length)
        try:
            audio = load_wav(raw)
        except (ValueError, wave.Error) as exc:
            return self._reply(400, {"error": str(exc)})
        output = self.pipeline(audio, **kwargs)
        segments = turns(output.speaker_diarization)
        body = {
            "num_speakers": len({s["speaker"] for s in segments}),
            "segments": segments,
            "audio_seconds": round(max((s["end"] for s in segments), default=0.0), 3),
        }
        exclusive = getattr(output, "exclusive_speaker_diarization", None)
        if exclusive is not None:
            body["exclusive_segments"] = turns(exclusive)
        self._reply(200, body)


def main():
    torch.set_num_threads(THREADS)
    Handler.pipeline = Pipeline.from_pretrained(MODEL_PATH)
    Handler.pipeline.to(torch.device("cpu"))
    print("diarize: loaded %s (revision %s, %d threads)" % (MODEL_PATH, REVISION or "-", THREADS), flush=True)
    HTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
PY

# Fail closed: a syntax error here would surface as a dead port minutes into the install.
if ! python3 - "${tmp}" <<'CHECK'
import sys
path = sys.argv[1]
with open(path, "r", encoding="utf-8") as fh:
    compile(fh.read(), path, "exec")
CHECK
then
  log "FATAL: bundled server does not compile"
  exit 1
fi

if [[ -f "${SERVER_DEST}" ]] && cmp -s "${tmp}" "${SERVER_DEST}"; then
  log "server unchanged at ${SERVER_DEST}"
else
  install -m 0644 "${tmp}" "${SERVER_DEST}"
  log "server written to ${SERVER_DEST}"
fi

reown "${SERVER_DIR}"
log "mod complete"
