#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Move ERNIE 5.5 Flash's six MLA layers from FlashMLA's SM100-only sparse
# decode onto FlashInfer's SM120/121 sparse kernel, keeping the
# `top-k + last window` page set, its per-row length and the learnable sink.
#
# The mod is fail-closed: the patch script aborts the launch and writes nothing
# if any of the five anchors does not match exactly once, and the verify script
# fails the launch if the patched behaviour or the GPU-less kernel envelope is
# not what the boot assumes. A refused launch here is a diagnostic, not a
# recipe failure: read the log and the mod's README before changing anything.
#
# Cache ownership is the mod's, not the boot's: this hook runs as root, and
# FlashInfer reads its cache root once at import, so a bare import in the
# verifier would leave root-owned entries in the shared cache and brick every
# later non-root serve on the node. The verifier's import is therefore pointed
# at a mod-owned directory (below), and the launch is refused if the shared
# tree gains a root-owned entry anyway.
#
# Boot does not accept this port; only the quality cell does. A wrong-logits
# port boots, captures CUDA graphs, and serves. See the mod README's
# acceptance ladder.

MOD_NAME="ernie55-flashinfer-sparse-sglang"
MOD_DESCRIPTION="ERNIE 5.5 Flash MLA layers onto FlashInfer's SM121 sparse-MLA kernel"
MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
PYTHON="${PYTHON:-python3}"

# Mods run as root and cannot see the serve user, so infer it from the mount.
if [[ -d /cache/runtime ]]; then
  USER_UID="$(stat -c '%u' /cache/runtime)"
  USER_GID="$(stat -c '%g' /cache/runtime)"
else
  USER_UID="${USER_UID:-1000}"
  USER_GID="${USER_GID:-1000}"
fi
reown() { chown -R "${USER_UID}:${USER_GID}" "${@}" 2>/dev/null || true; }

mkdir -p "$LOGDIR"
reown "$LOGDIR"
LOG="$LOGDIR/${MOD_NAME}.log"
exec >>"$LOG" 2>&1

echo "[$(date -u +%FT%TZ)] ${MOD_NAME} starting: ${MOD_DESCRIPTION}"
command -v "$PYTHON" >/dev/null 2>&1 || {
  echo "FATAL: ${PYTHON} not on PATH in this image; cannot patch sglang."
  exit 1
}

# FlashInfer 0.7.3 fixes its cache root at import: FLASHINFER_WORKSPACE_BASE
# (default $HOME) + .cache/flashinfer. The verifier imports it as root, so point
# that import (and TMPDIR) at a mod-owned directory rather than the shared cache.
MOD_CACHE="${MOD_CACHE:-/cache/runtime/${MOD_NAME}-verify}"
SHARED_FI="${HOME:-/cache/runtime/flashinfer}/.cache/flashinfer"
mkdir -p "$MOD_CACHE/tmp"
reown "$MOD_CACHE"
export FLASHINFER_WORKSPACE_BASE="$MOD_CACHE" TMPDIR="$MOD_CACHE/tmp"
STAMP="$MOD_CACHE/stamp"
: > "$STAMP"

"$PYTHON" -B "${MOD_DIR}/apply-ernie55-flashinfer-sparse-patch.py" || {
  echo "FATAL: patch refused; see the error above. Refusing to launch unpatched."
  exit 1
}
"$PYTHON" -B "${MOD_DIR}/verify-ernie55-flashinfer-sparse.py" || {
  echo "FATAL: rung (i) failed after patching. Refusing to launch."
  exit 1
}

# Ownership guard: the shared tree must either be absent/untouched by this
# import, or owned by the cache owner. A uid-1000 serve cannot write a
# root-owned flashinfer_jit.log and cannot unlink it, so refuse the launch here
# instead of failing on the node's next start.
for _shared in "$SHARED_FI" "/cache/runtime/flashinfer/.cache/flashinfer"; do
  [[ -d "$_shared" ]] || continue
  _owner="$(stat -c '%u:%g' "$_shared")"
  [[ "$_owner" == "${USER_UID}:${USER_GID}" ]] || {
    echo "FATAL: shared flashinfer cache ${_shared} is ${_owner}, expected ${USER_UID}:${USER_GID}; the serve cannot write it. Repair with a chown -R, then relaunch."
    exit 1
  }
  _leaked="$(find "$_shared" -uid 0 -newer "$STAMP" -print -quit 2>/dev/null)"
  [[ -z "$_leaked" ]] || {
    echo "FATAL: rung (i) wrote a root-owned entry into the shared flashinfer cache: ${_leaked}"
    exit 1
  }
done

reown "$MOD_CACHE"
echo "[$(date -u +%FT%TZ)] ${MOD_NAME} done"
