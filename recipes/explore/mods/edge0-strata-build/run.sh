#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Build Edge0's `strata` engine for the `zz-edge0-145b-nvfp4-latentmoe-strata` arm.
#
# Why a from-source build is the only route. `Edge0/Edge0-145B-NVFP4` is a
# `strata pack index v3` folder, not an HF checkpoint: the routed experts live in
# `experts.bin` (latent, l=1792, 1,630,720 B records) and the per-layer D/U
# projections in `latent_dense_q8.bin`, so llama.cpp (no external-pack reader, no
# expert tensors in the skeleton GGUF) and vLLM/SGLang (no config.json, no
# safetensors, no architecture) cannot load it. Only `strata` can, and:
#   * Edge0's GitHub releases carry no Linux asset at all (Windows x64/arm64,
#     macOS arm64, Android only), so there is nothing to download;
#   * Niko1221/Strata's signed feed does publish a `linux-aarch64` engine, but it
#     is upstream Strata WITHOUT the latent-MoE support this pack needs;
#   * `edge0-strata/EDGE0.md` records that `spark/` (their DGX Spark build
#     script) and `packaging/` were removed from the published snapshot, so the
#     documented generic Linux CUDA build is what is left — which that same file
#     says shares the aarch64 CPU path with the Spark build.
#
# Pinned by commit, not by branch: the build key below is a hash of both pins and
# the build flags, so a moved `main` or a changed flag rebuilds instead of
# silently reusing a binary that does not match what this recipe claims.
#
# Not done here, on purpose: no `strata-vision` (the arm serves text only; the
# picture reader is a second CMake project and needs a llama.cpp checkout), no
# `spark/build_engine.sh` (absent from the snapshot), no prebuilt feed.
set -euo pipefail

export MOD_NAME="edge0-strata-build"
export MOD_DESCRIPTION="Build Edge0 strata (latent-MoE) for GB10 and stage its run config"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

export TIMEOUT="${MOD_TIMEOUT:-180}"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export RUNTIME_DIR="${CACHEDIR}/edge0-strata"

# Pins. EDGE0_COMMIT is the `main` head probed 2026-11-20; LLAMA_CPP_COMMIT is
# the ggml source `EDGE0.md` "Build (Linux, NVIDIA)" step 1 names (strata uses
# llama.cpp's ggml, not its loader, so this pin is a kernel-library pin).
export EDGE0_REPO="${EDGE0_REPO:-https://github.com/Edge0-AI/Edge0.git}"
export EDGE0_COMMIT="${EDGE0_COMMIT:-43ceac675bf94b5a292e56f97a738b0eed15195f}"
export LLAMA_CPP_COMMIT="${LLAMA_CPP_COMMIT:-3cf03257f219afbe7334045ff7c6a06ac68c627d}"
export JOBS="${JOBS:-$(nproc)}"

export USER_UID="$(stat -c '%u' "${CACHEDIR}")"
export USER_GID="$(stat -c '%g' "${CACHEDIR}")"

die() { log "FATAL: ${*}"; exit 1; }

reown() {
  if [[ "$(id -u)" != "0" ]]; then
    log "reown: not root (uid $(id -u)); skipping chown of ${*}"
    return 0
  fi
  chown -R "${USER_UID}:${USER_GID}" "${@}"
}

log() {
  local _ts _message
  _message="${*}"
  _ts="$(date -Ins)"
  printf '%s [%s] %s\n' "$_ts" "${MOD_NAME}" "${_message}" | tee -a "${LOGDIR}/${MOD_NAME}.log"
  [[ -x "$(type -fp logger)" ]] && logger -t "${MOD_NAME}" -- "${_message}" || true
}

# Run a command, stream it into the mod log, and fail the mod when it fails: a
# build that half-succeeds must not leave a marker behind.
step() {
  log "=== ${1} ==="
  shift
  "$@" 2>&1 | log || die "step failed: ${*}"
}

if [[ ! -d "${LOGDIR}" ]]; then mkdir -p "${LOGDIR}"; fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log.gz" ]]; then rm -f "${LOGDIR}/${MOD_NAME}.log.gz"; fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log" ]]; then gzip "${LOGDIR}/${MOD_NAME}.log" || true; fi
touch "${LOGDIR}/${MOD_NAME}.log"
reown "${LOGDIR}"

log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log "edge0=${EDGE0_COMMIT} llama.cpp=${LLAMA_CPP_COMMIT} jobs=${JOBS}"

# --- fail-closed platform gate ---------------------------------------------
# The pins above are aarch64/CUDA-13 only: the build has no x86 CPU kernels and
# no CUDA 12 path, and the pack is 106 GiB of pages that only a unified-memory
# node can hold beside its KV cache.
[[ "$(uname -m)" == "aarch64" ]] || die "not aarch64 ($(uname -m)): this arm is GB10-only"
command -v nvcc >/dev/null 2>&1 || die "no nvcc: use an nvidia/cuda:*-devel image"
log "nvcc: $(nvcc --version | tail -n1)"

KEY="$(printf '%s|%s|native|cuda' "${EDGE0_COMMIT}" "${LLAMA_CPP_COMMIT}" | sha256sum | cut -c1-16)"
BUILD_ROOT="${RUNTIME_DIR}/${KEY}"
STRATA_SRC="${BUILD_ROOT}/edge0-strata"
STRATA_BIN="${STRATA_SRC}/build/strata"
MARKER="${BUILD_ROOT}/.built"
PY="${STRATA_SRC}/.venv/bin/python"
log "key=${KEY} build_root=${BUILD_ROOT}"

# --- content-based idempotence ---------------------------------------------
if [[ -f "${MARKER}" ]] && [[ "$(cat "${MARKER}")" == "${KEY}" ]] \
   && [[ -x "${STRATA_BIN}" ]] && [[ -x "${PY}" ]]; then
  log "engine already built for ${KEY}; skipping build"
else
  # Toolchain. The cuda devel image carries nvcc and g++, not cmake, ninja or a
  # python; apt is idempotent, so it runs whenever the build runs.
  if ! command -v cmake >/dev/null 2>&1 || ! command -v ninja >/dev/null 2>&1 \
     || ! command -v python3 >/dev/null 2>&1; then
    step "apt: build toolchain" bash -c \
      'apt-get update && apt-get install -y --no-install-recommends \
         git ca-certificates curl build-essential cmake ninja-build \
         python3 python3-venv python3-pip && rm -rf /var/lib/apt/lists/*'
  fi

  rm -rf "${BUILD_ROOT}"
  mkdir -p "${BUILD_ROOT}"
  # Fetch one commit, then prove it landed: a shallow branch clone would drift.
  step "fetch Edge0 ${EDGE0_COMMIT}" bash -c \
    "git init --quiet '${BUILD_ROOT}/repo' \
     && cd '${BUILD_ROOT}/repo' \
     && git remote add origin '${EDGE0_REPO}' \
     && git fetch --quiet --depth 1 origin '${EDGE0_COMMIT}' \
     && git checkout --quiet FETCH_HEAD \
     && test \"\$(git rev-parse HEAD)\" = '${EDGE0_COMMIT}'"
  mv "${BUILD_ROOT}/repo/edge0-strata" "${STRATA_SRC}"
  rm -rf "${BUILD_ROOT}/repo"

  # ggml at the pinned commit (EDGE0.md step 1). `third_party/llama.cpp` is
  # gitignored upstream, so the directory must be created first.
  mkdir -p "${STRATA_SRC}/third_party/llama.cpp"
  step "fetch llama.cpp ${LLAMA_CPP_COMMIT}" bash -c \
    "curl -fsSL 'https://github.com/ggml-org/llama.cpp/archive/${LLAMA_CPP_COMMIT}.tar.gz' \
       | tar -xz --strip-components=1 -C '${STRATA_SRC}/third_party/llama.cpp'"

  # The documented Linux CUDA build. `native` resolves to sm_121 on a GB10; the
  # only target built is `strata` (EDGE0.md: the parity/bench targets do not link).
  step "cmake configure" bash -c \
    "cd '${STRATA_SRC}' \
     && cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_CUDA_COMPILER=\"\$(command -v nvcc)\" \
        -DCMAKE_CUDA_ARCHITECTURES=native \
        -DSTRATA_ENABLE_CUDA=ON -DSTRATA_GGML_DIR='${STRATA_SRC}/third_party/llama.cpp'"
  step "cmake build strata" bash -c \
    "cd '${STRATA_SRC}' && cmake --build build --target strata -j '${JOBS}'"

  # The server's own environment (requirements.txt pins numpy/jinja2/regex/...;
  # no torch, no fastapi — serve/server.py is stdlib http.server).
  step "python venv" bash -c \
    "python3 -m venv '${STRATA_SRC}/.venv' \
     && '${STRATA_SRC}/.venv/bin/pip' install --quiet --upgrade pip \
     && '${STRATA_SRC}/.venv/bin/pip' install --quiet -r '${STRATA_SRC}/requirements.txt'"

  # Gates. (a) the checkout is Edge0's fork, not upstream Strata: latent-MoE
  # support is the whole reason this pack can run, and `src/core/latent_dense.cpp`
  # is where it lives (EDGE0.md, "Changes from upstream Strata"). (b) the binary
  # carries sm_121 device code — the same gate the lane's llama.cpp images use, and
  # the only proof that `-DCMAKE_CUDA_ARCHITECTURES=native` resolved to this part.
  # (c) the env-var literal the pack's `env` block sets is in the binary, so a build
  # that lost the latent path cannot mark itself done.
  [[ -x "${STRATA_BIN}" ]] || die "no ${STRATA_BIN} after the build"
  [[ -f "${STRATA_SRC}/src/core/latent_dense.cpp" ]] || die "checkout has no latent-MoE source"
  command -v cuobjdump >/dev/null 2>&1 || die "no cuobjdump: cannot prove the engine carries sm_121 code"
  # Through a file, not a pipe: `grep -q` closes the pipe and `pipefail` would
  # report cuobjdump's SIGPIPE as a gate failure.
  cuobjdump -lelf "${STRATA_BIN}" > "${BUILD_ROOT}/elf.txt" || die "cuobjdump failed on ${STRATA_BIN}"
  grep -q sm_121 "${BUILD_ROOT}/elf.txt" || die "engine has no sm_121 device code"
  rm -f "${BUILD_ROOT}/elf.txt"
  grep -qa "STRATA_LATENT_DENSE" "${STRATA_BIN}" || die "engine has no latent-dense path"
  "${PY}" -c 'import numpy, jinja2, regex, yaml' || die "server imports do not resolve"
  log "gate: latent_dense.cpp, sm_121 device code, STRATA_LATENT_DENSE literal, server imports"

  printf '%s' "${KEY}" > "${MARKER}"
fi

# Stable handle for the launcher: the recipe's command never names a build key.
ln -sfn "${STRATA_SRC}" "${RUNTIME_DIR}/current"
reown "${RUNTIME_DIR}"
log "engine: ${RUNTIME_DIR}/current -> ${STRATA_SRC}"
log "Done."
