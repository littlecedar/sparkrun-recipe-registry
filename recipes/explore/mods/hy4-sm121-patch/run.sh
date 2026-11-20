#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Stage atakann's six Hy4-flash SM121/ModelOpt files into the vendor vLLM tree.
#
# Why a mod and not an image: atakann publishes no container (ghcr.io/atakann/...
# answers 404, and the Docker Hub user has no repositories), so his recipe's
# `dgx-spark-recipes/vllm-hy4-flash:77766db` is a local build only. The six files
# are plain Python — no compiled extension, no import-time side effect (checked:
# no cpp_extension/load_inline/ctypes/subprocess/os.system/importlib and no
# `if __name__` block in any of them) — so staging them at pre-exec is the same
# filesystem write the Dockerfile did, without a 10 GB image build.
#
# Fail closed: every anchor is checked before a single byte is written, the
# vendored files are digest-checked against the pinned atakann commit, and each
# staged file is compiled in-process (no bytecode written) after the copy. A
# refused launch here means the image is not the Hy4-flash build this patch was
# made against; re-vendor the files (see README) rather than editing the recipe.
#
# The two runtime knobs the Dockerfile used to set are the RECIPE's, not this
# mod's: CUTE_DSL_ARCH=sm_121a and VLLM_WORKER_MULTIPROC_METHOD=spawn live in
# the recipe's `env:` so they are visible in the config chain.
#
# Cache ownership: the mod only writes under site-packages (image-owned, and the
# serve user only reads it), so no /cache/runtime reown is needed. The one cache
# this must not touch is Python's own: `python3 -B` everywhere, and the staged
# files are compiled with compile() rather than py_compile, so no root-owned
# __pycache__ entry can be left behind for a uid-1000 serve.

set -euo pipefail

MOD_NAME="hy4-sm121-patch"
MOD_DESCRIPTION="Stage atakann's six Hy4-flash SM121/ModelOpt files into the vendor vLLM tree"
MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"
MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
PYTHON="${PYTHON:-python3}"
PATCH_DIR="${MOD_DIR}/patch"

# The commit that introduced the six files (README carries the blob map).
UPSTREAM_REPO="https://github.com/atakann/dgx-spark-recipes"
UPSTREAM_COMMIT="e764efa3efed3e21fe543c3fffc927eb6a00bff8"
UPSTREAM_DIR="images/vllm-hy4-flash"

log() {
  printf '%s [%s] %s\n' "$(date -u +%FT%TZ)" "${MOD_NAME}" "${*}"
}

die() {
  log "FATAL: ${*}"
  exit 1
}

log_var() {
  log "${1}=${!1}"
}

if mkdir -p "${LOGDIR}" 2>/dev/null; then
  exec >>"${LOGDIR}/${MOD_NAME}.log" 2>&1
fi

log "${MOD_NAME} starting: ${MOD_DESCRIPTION}"
log_var UPSTREAM_COMMIT

#####################################################################
# Locate the vLLM package root without importing vLLM
#####################################################################
# `import vllm` here would run the engine's import graph as root before the
# serve starts; sysconfig is inert and needs no bytecode (-B).
SITE="$("${PYTHON}" -B -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')" \
  || die "cannot read sysconfig purelib with ${PYTHON}"
# VLLM_PACKAGE_ROOT is a test hook (fake tree); unset in a real launch.
V="${VLLM_PACKAGE_ROOT:-${SITE}/vllm}"
log_var V

[[ -d "${V}/models/hy_v4_flash/nvidia" ]] \
  || die "${V}/models/hy_v4_flash/nvidia missing: this is not the Hy4-flash vLLM build"
[[ -d "${V}/models/hy_v4/nvidia" ]] \
  || die "${V}/models/hy_v4/nvidia missing: this is not the Hy4-flash vLLM build"

#####################################################################
# Anchors: the stock tree must be the one the patch was made against
#####################################################################
require_file() {
  [[ -f "${1}" ]] || die "missing anchor file ${1}"
}

require_text() {
  [[ -f "${1}" ]] || die "missing anchor file ${1} (looking for '${2}')"
  grep -F -q -- "${2}" "${1}" \
    || die "anchor ${1} does not contain '${2}'"
}

# The patched attention.py imports these siblings from its own package.
require_file "${V}/models/hy_v4_flash/configs.py"
require_file "${V}/models/hy_v4_flash/nvidia/compressed_indexer.py"
require_file "${V}/models/hy_v4_flash/nvidia/swa.py"
require_file "${V}/models/hy_v4_flash/nvidia/moe.py"

# hy_v4_attention.py replaces this module and subclasses its class.
require_text "${V}/models/hy_v4/nvidia/attention.py" "class HYV4MLAAttention"
require_file "${V}/models/hy_v4/nvidia/model.py"
require_text "${V}/models/hy_v4/nvidia/model.py" "HYV4ForCausalLM"
require_file "${V}/models/hy_v4/nvidia/hc.py"

# dfly_config.py subclasses the engine's DFly speculator config.
require_text "${V}/v1/worker/gpu/spec_decode/dfly/config.py" "DFlySpeculatorConfig"

# sm120.py imports the FlashInfer SM120 backend and its workspace helper.
require_text "${V}/v1/attention/backends/mla/flashinfer_mla_sparse.py" \
  "FlashInferMLASparseSM120Backend"
require_text "${V}/v1/attention/backends/mla/flashinfer_mla_sparse.py" \
  "_get_workspace_buffer"
require_text "${V}/v1/attention/backends/mla/flashinfer_mla_sparse_sm120.py" \
  "FlashInferMLASparseSM120Impl"

# mla_attention.py is a whole-file replacement of this core module.
require_text "${V}/model_executor/layers/attention/mla_attention.py" \
  "class MLACommonImpl"

# The three overwrite targets must exist; the patch adds behaviour to them.
require_file "${V}/models/hy_v4_flash/nvidia/attention.py"
require_file "${V}/models/hy_v4_flash/nvidia/model.py"
require_file "${V}/models/hy_v4/dfly_config.py"

log "anchors ok"

#####################################################################
# Vendored files must match the pinned commit
#####################################################################
( cd "${PATCH_DIR}" && sha256sum -c SHA256SUMS ) \
  || die "vendored patch files do not match patch/SHA256SUMS (registry checkout damaged)"

#####################################################################
# Stage: source|target, target paths are the Dockerfile's COPY destinations
#####################################################################
# `sm120.py` is new; the other five replace the image's own file at the same
# path the Dockerfile overwrote. Renaming hy_v4_attention.py onto attention.py
# is deliberate: that is the module the patched hy_v4_flash/attention.py imports.
MAP=(
  "sm120.py|${V}/models/hy_v4_flash/nvidia/sm120.py"
  "attention.py|${V}/models/hy_v4_flash/nvidia/attention.py"
  "model.py|${V}/models/hy_v4_flash/nvidia/model.py"
  "hy_v4_attention.py|${V}/models/hy_v4/nvidia/attention.py"
  "dfly_config.py|${V}/models/hy_v4/dfly_config.py"
  "mla_attention.py|${V}/model_executor/layers/attention/mla_attention.py"
)

STAGED=()
for entry in "${MAP[@]}"; do
  src="${PATCH_DIR}/${entry%%|*}"
  dst="${entry##*|}"
  want="$(sha256sum "${src}" | cut -d' ' -f1)"
  if [[ -f "${dst}" ]] && [[ "$(sha256sum "${dst}" | cut -d' ' -f1)" == "${want}" ]]; then
    log "already staged: ${dst}"
  else
    tmp="${dst}.hy4-sm121.$$"
    install -m 0644 "${src}" "${tmp}" \
      || die "cannot write ${tmp} (read-only image tree?)"
    mv -f "${tmp}" "${dst}" || die "cannot replace ${dst}"
    log "staged: ${dst}"
  fi
  got="$(sha256sum "${dst}" | cut -d' ' -f1)"
  [[ "${got}" == "${want}" ]] || die "digest mismatch after staging ${dst}"
  STAGED+=("${dst}")
done

#####################################################################
# Compile in-process: no imports, no bytecode, no side effects
#####################################################################
"${PYTHON}" -B - "${STAGED[@]}" <<'PY' || die "a staged file does not compile"
import sys
for path in sys.argv[1:]:
    with open(path, "r", encoding="utf-8") as fh:
        compile(fh.read(), path, "exec")
print("compiled", len(sys.argv) - 1, "staged files")
PY

log "done: six files staged from ${UPSTREAM_REPO}@${UPSTREAM_COMMIT} (${UPSTREAM_DIR})"
