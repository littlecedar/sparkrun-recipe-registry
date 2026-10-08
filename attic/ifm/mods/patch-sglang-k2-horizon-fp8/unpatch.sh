#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
#
# mods/patch-sglang-k2-horizon-fp8/unpatch.sh
#
# Restore srt/models/xllm.py to the stock copy this mod saved on its first run.
#
# Why this exists as a separate script rather than "just re-pull the image":
#   * A container is often reused across boots, and the mod's own backup is the
#     only guaranteed-pristine copy of the file *as that container shipped*.
#   * It gives a reviewer a way to see the diff: restore, diff against the backup,
#     re-apply. Without it the only way to check what the mod changed is to read
#     the anchors in run.sh and trust them.
#   * If the post-patch self-check ever fails (upstream moved the MoVA value path),
#     run.sh tells the operator to run this. A recovery instruction that has no
#     implementation is not a recovery instruction.
#
# Exit codes: 0 restored (or nothing to restore), 1 could not restore.
#
# ESCAPE HATCHES
#   SPARKRUN_SGLANG_PKG=<dir>   override package discovery
#   SPARKRUN_K2_FP8_BACKUP=<dir> where the stock copy lives (must match run.sh)

set -euo pipefail

MOD_NAME="patch-sglang-k2-horizon-fp8"
SPARKRUN_ROOT="${SPARKRUN_ROOT:-/cache}"
SPARKRUN_RUNTIME_ROOT="${SPARKRUN_RUNTIME_ROOT:-${SPARKRUN_ROOT}/runtime}"
SPARKRUN_NODE_ID="${SPARKRUN_NODE_ID:-$(hostname -s 2>/dev/null || echo node)}"
LOG_DIR="${SPARKRUN_LOG_DIR:-${SPARKRUN_RUNTIME_ROOT}/_logs}"
MOD_ROOT="${SPARKRUN_MOD_ROOT:-${SPARKRUN_ROOT}/mods}"
BACKUP_DIR="${SPARKRUN_K2_FP8_BACKUP:-${MOD_ROOT}/${MOD_NAME}/.backup}"
LOG_FILE="${LOG_DIR}/${MOD_NAME}.${SPARKRUN_NODE_ID}.unpatch.log"

log() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*" | tee -a "${LOG_FILE}"; }
mkdir -p "${LOG_DIR}" 2>/dev/null || true
: > "${LOG_FILE}"

SGLANG_ROOT="${SPARKRUN_SGLANG_PKG:-}"
if [ -z "${SGLANG_ROOT}" ]; then
    SGLANG_ROOT="$(python3 -c 'import importlib.util,pathlib;print(pathlib.Path(importlib.util.find_spec("sglang").origin).parent)' 2>/dev/null || true)"
fi
XLM="${SGLANG_ROOT}/srt/models/xllm.py"
STOCK="${BACKUP_DIR}/xllm.py.stock"

if [ -z "${SGLANG_ROOT}" ] || [ ! -f "${XLM}" ]; then
    log "FATAL: cannot locate ${XLM}"; exit 1
fi
if [ ! -f "${STOCK}" ]; then
    log "FATAL: no stock copy at ${STOCK}."
    log "       run.sh never completed a backup, so there is nothing to restore from."
    log "       Restore from the container image instead, e.g.:"
    log "         docker run --rm --entrypoint cat <image> \\$(python3 -c \\"
    log "           'import sglang,pathlib;print(pathlib.Path(sglang.__file__).parent/\"srt/models/xllm.py\")'\\)"
    log "       ... and write it to the running container at that path."
    exit 1
fi

if ! grep -q "\[k2-horizon-fp8\]" "${XLM}" 2>/dev/null; then
    log "already stock (no sentinel present); nothing to do"
    # Still verify the backup matches, because a mismatch means something else
    # edited this file and the operator should know before they trust either copy.
    if cmp -s "${STOCK}" "${XLM}"; then
        log "backup and working copy are byte-identical"
    else
        log "WARN: working copy differs from the backup but carries no sentinel."
        log "      Something other than this mod edited ${XLM}. Not overwriting it."
        exit 1
    fi
    exit 0
fi

# Keep the patched version alongside the restore so a failed boot can be diffed.
KEEPTIME="$(date -u +%Y%m%dT%H%M%SZ)"
cp "${XLM}" "${BACKUP_DIR}/xllm.py.patched-${KEEPTIME}" 2>/dev/null || true

cp "${STOCK}" "${XLM}"
log "restored ${XLM} from ${STOCK}"

if grep -q "\[k2-horizon-fp8\]" "${XLM}"; then
    log "FATAL: sentinel still present after restore -- the copy did not take"
    exit 1
fi
python3 -c "import py_compile,sys; py_compile.compile(sys.argv[1], doraise=True)" "${XLM}" \
    || { log "FATAL: restored file does not compile"; exit 1; }
log "restored file compiles; patch is gone"
exit 0
