#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Serve the Edge0 pack through Edge0's own HTTP server.
#
# Why this shim exists at all. `serve/server.py` takes one `--config` JSON and
# resolves a relative `"exe"` against that config's `"cwd"`, then starts the
# engine there — so the pack's shipped `model.json` (exe `strata`, cwd `.`, log
# `./serve.log`) only works when the engine binary sits inside the model folder,
# which is a shared, read-only-by-convention snapshot. This writes a run config
# under `/cache/runtime` with absolute `exe`/`cwd`/`tokenizer`/`log` instead, and
# changes nothing else about the pack's `args`/`env`.
#
# It also absorbs one argument shape sparkrun appends: the vLLM runtime contract
# this arm borrows renders `--served-model-name <name>` onto the command, and
# server.py has no such flag. The template passes the same name, so the runtime's
# copy is a duplicate here — the value is not dropped, it becomes the config's
# `model_name`, which is what `/v1/models` advertises and what sparkrun's
# readiness probe then asks for.
set -euo pipefail

MODEL_DIR=""
REVISION=""
PORT=8000
HOST=0.0.0.0
NAME=""

while [[ $# -gt 0 ]]; do
  case "${1}" in
    --model) MODEL_DIR="${2:-}"; shift 2 ;;
    --revision) REVISION="${2:-}"; shift 2 ;;
    --port) PORT="${2:-}"; shift 2 ;;
    --host) HOST="${2:-}"; shift 2 ;;
    --served-model-name) NAME="${2:-}"; shift 2 ;;
    *) echo "edge0-launch: ignoring argument ${1}" >&2; shift ;;
  esac
done

die() { echo "edge0-launch: FATAL: ${*}" >&2; exit 1; }

ENGINE_DIR="${EDGE0_ENGINE_DIR:-/cache/runtime/edge0-strata/current}"
RUNDIR="${EDGE0_RUNDIR:-/cache/runtime/edge0-strata}"
[[ -n "${MODEL_DIR}" ]] || die "no --model given"

# `{model}` renders the repo id under this profile (the WOPR profile does not
# rebind it to a prepared path), while every check below needs the pack folder.
# Resolve the id to its staged snapshot under the mounted HF cache: the recipe's
# revision when it passes one, else refs/main, else the only staged snapshot.
if [[ ! -d "${MODEL_DIR}" ]]; then
  MODEL_ID="${MODEL_DIR}"
  HUB="${HF_HUB_CACHE:-${HF_HOME:-/cache/huggingface}/hub}"
  REPO_DIR="${HUB}/models--${MODEL_ID//\//--}"
  SNAP_ROOT="${REPO_DIR}/snapshots"
  [[ -d "${SNAP_ROOT}" ]] || die "model '${MODEL_ID}' is not a folder and has no staged repo at ${REPO_DIR} (is the HF cache mounted at ${HUB}?)"
  if [[ -n "${REVISION}" ]]; then
    [[ -d "${SNAP_ROOT}/${REVISION}" ]] || die "model '${MODEL_ID}' has no staged snapshot ${REVISION} under ${SNAP_ROOT}"
    MODEL_DIR="${SNAP_ROOT}/${REVISION}"
  elif [[ -f "${REPO_DIR}/refs/main" ]]; then
    MODEL_DIR="${SNAP_ROOT}/$(cat "${REPO_DIR}/refs/main")"
  else
    shopt -s nullglob
    CANDIDATES=("${SNAP_ROOT}"/*/)
    shopt -u nullglob
    [[ "${#CANDIDATES[@]}" -eq 1 ]] || die "model '${MODEL_ID}' has ${#CANDIDATES[@]} staged snapshots under ${SNAP_ROOT}; pass --revision to pick one"
    MODEL_DIR="${CANDIDATES[0]%/}"
  fi
  echo "edge0-launch: resolved ${MODEL_ID} -> ${MODEL_DIR}" >&2
fi
[[ -d "${MODEL_DIR}" ]] || die "model folder ${MODEL_DIR} does not exist"
[[ -f "${MODEL_DIR}/model.json" ]] || die "no model.json in ${MODEL_DIR} (not an Edge0 pack)"
[[ -x "${ENGINE_DIR}/build/strata" ]] || die "no engine at ${ENGINE_DIR}/build/strata (did the build mod run?)"
[[ -x "${ENGINE_DIR}/.venv/bin/python" ]] || die "no server venv at ${ENGINE_DIR}/.venv"

# Fail closed on an incomplete pack: every one of these is named by model.json or
# by the env block, and the engine dies minutes into a load without them.
for f in experts.bin latent_dense_q8.bin labels.bin model-skeleton.gguf ple-fp8.gguf profile.bin; do
  [[ -s "${MODEL_DIR}/${f}" ]] || die "pack file missing or empty: ${f}"
done
[[ -s "${MODEL_DIR}/tokenizer/chat_template.jinja" ]] || die "pack ships no chat template"
[[ -s "${MODEL_DIR}/mtp/experts.bin" ]] || die "pack ships no MTP draft head"

mkdir -p "${RUNDIR}/logs"

# One deviation from the pack's own args, and only where memory forces it: on a
# GB10 the engine would otherwise pin a second copy of the 44.3 GiB expert pool in
# host RAM. `--mmap-experts` is the setting Edge0 measured on this part
# (docs/DGX_SPARK_LINUX.md). The other three measured Spark switches
# (`--prefill auto:32768`, `--mtp-q4 all`, `--mtp-hnorm stream`) are performance
# tuning, not fit, and are left for the first measured round.
"${ENGINE_DIR}/.venv/bin/python" - "${MODEL_DIR}" "${ENGINE_DIR}" "${RUNDIR}" "${PORT}" "${NAME}" <<'PY'
import json, os, sys

model_dir, engine_dir, rundir, port, name = sys.argv[1:6]
cfg_path = os.path.join(model_dir, "model.json")
with open(cfg_path, encoding="utf-8") as fh:
    cfg = json.load(fh)

args = list(cfg.get("args") or [])
if "--mmap-experts" not in args:
    args.append("--mmap-experts")

cfg.update({
    "exe": os.path.join(engine_dir, "build", "strata"),
    "cwd": os.path.abspath(model_dir),
    "tokenizer": os.path.join(os.path.abspath(model_dir), "tokenizer"),
    "log": os.path.join(rundir, "logs", "serve.log"),
    "port": int(port),
    "args": args,
})
# The served id: sparkrun's rendered name when it sent one, else the pack's own.
if name:
    cfg["model_name"] = name

out = os.path.join(rundir, "run-config.json")
with open(out, "w", encoding="utf-8") as fh:
    json.dump(cfg, fh, indent=1)
print(f"edge0-launch: config {out} model={cfg.get('model_name')} port={cfg['port']}", flush=True)
PY

echo "edge0-launch: serving ${NAME:-the pack} on ${HOST}:${PORT}" >&2
exec "${ENGINE_DIR}/.venv/bin/python" "${ENGINE_DIR}/serve/server.py" \
  --engine strata \
  --config "${RUNDIR}/run-config.json" \
  --host "${HOST}" \
  --port "${PORT}"
