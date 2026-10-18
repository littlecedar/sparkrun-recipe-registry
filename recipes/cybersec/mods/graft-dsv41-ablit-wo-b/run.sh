#!/bin/bash
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Pre-launch mod for the cybersec lane's DeepSeek-V4.1-Flash abliterated arm.
#
# The overlay repo (drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed) ships
# NO weights: it is two small `attn.wo_b` L10-35 sidecars plus the author's graft scripts. The
# arm is the sidecar spliced onto a stock EXL3 2.9bpw pack. This mod builds that graft into
# sparkrun's managed runtime cache, from the *container's own* HF cache, without ever writing
# the stock snapshot (the author's script hardlinks unchanged shards and refuses src == dst).
# The stock it grafts onto is the combined littlecedar pack, so the Engram tables the launcher
# reads (via --stock-model) are the ones already on the node: no second ~189 GiB copy.
#
# The stock pack's attention is EXL3 mul1 K=5, not FP8, so the EXL3 sidecar + the
# EXL3-specific graft script ("recipe D" in the overlay's INSTALL.md) are the correct pair;
# the FP8 sidecar + apply_wo_b_graft.py belongs to native / Pollard / TR3 stock and mixing them
# is explicitly forbidden by that document. Combining the tables into the stock repo
# (tools/build-dsv41-combined.py) leaves the weights byte-identical, so the sidecar pair is
# unchanged.
#
# Modifies no file under the stock snapshot. Fail closed: a graft that cannot be built and
# verified aborts the launch rather than serving the stock (non-abliterated) checkpoint under
# this arm's name.
#
# Budget note: the graft rewrites every shard carrying layers.10-35 attn.wo_b (24 shards,
# 118.58 GiB) and must finish inside sparkrun's hard-coded 600 s pre-exec hook budget
# (sparkrun/orchestration/hooks.py::run_pre_exec). A detached graft cannot be used instead: the
# cluster launch holds the head on a ~300 s rendezvous gate before the serve command's own
# readiness budget applies, so a serve wrapper that waits on a background graft never gets the
# head up (measured 2026-10-14 -- see attic/cybersec/AGENTS.md).
set -euo pipefail

export MOD_NAME="graft-dsv41-ablit-wo-b"
export MOD_DESCRIPTION="Graft the drowzeys L10-35 attn.wo_b abliteration sidecar onto the stock EXL3 2.9bpw pack"
export MOD_MAINTAINER="Little Cedar Group <sparkrun@littlecedar.net>"

export TIMEOUT="${MOD_TIMEOUT:-180}"
export MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CACHEDIR="${MOD_CACHEDIR:-/cache/runtime}"
export LOGDIR="${MOD_LOGDIR:-/cache/runtime/modlogs}"
export UV_LINK_MODE=copy
export USER_UID="$(stat -c '%u' /cache/runtime)"
export USER_NAME="$(stat -c '%U' /cache/runtime)"
export USER_GID="$(stat -c '%g' /cache/runtime)"
export USER_GROUP="$(stat -c '%G' /cache/runtime)"

# Overlay repo + revision, pinned. Overridable for a re-pin A/B.
OVERLAY_REPO="${OVERLAY_REPO:-drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed}"
export OVERLAY_REVISION="${OVERLAY_REVISION:-87bb9850e6f49fd20ad9c8516b7817215cbbf5fc}"
# The stock pack, by repo id (resolved in the container's HF cache). The combined repo: its
# weights are the Mia 2.9bpw shards byte-for-byte, and its engram/ subdir is what the launcher
# hands the engine, so this arm adds no Engram copy to the node.
STOCK_REPO="${STOCK_REPO:-littlecedar/DeepSeek-V4.1-Flash-EXL3-2.9bpw-with-engram}"
export STOCK_REPO
export OUTDIR="${OUTDIR:-${CACHEDIR}/dsv41-ablit}"
export WORKDIR="${WORKDIR:-${CACHEDIR}/dsv41-ablit-sidecar}"
export TOKENFILE="${TOKENFILE:-/cache/huggingface/token}"
export HF_HUB="${HF_HUB:-/cache/huggingface/hub}"
EXPECTED_N_EDITED=104

reown() { chown -R "${USER_UID}:${USER_GID}" "${@}" 2>/dev/null || true; }

# Timestamped, so the graft's wall-clock cost against sparkrun's 600 s pre-exec hook budget is
# readable from the mod log after the fact (this lane's mods must not need a stopwatch).
log() {
  local _ts
  _ts="$(date -Ins)"
  if [[ $# -gt 0 ]]; then
    printf '[%s] %s\n' "${_ts}" "$*"
  else
    while IFS= read -r _line; do printf '[%s] %s\n' "${_ts}" "${_line}"; done
  fi
}

log_var() { printf '  %s=%s\n' "$1" "${!1-}"; }

die() {
  log "FATAL: $*"
  exit 1
}

#####################################################################
# Rotate logs
#####################################################################
if ! [[ -d "${LOGDIR}" ]]; then
  mkdir -p "${LOGDIR}"
fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log.gz" ]]; then
  rm -f "${LOGDIR}/${MOD_NAME}.log.gz"
fi
if [[ -f "${LOGDIR}/${MOD_NAME}.log" ]]; then
  gzip -c "${LOGDIR}/${MOD_NAME}.log" > "${LOGDIR}/${MOD_NAME}.log.gz"
  rm -f "${LOGDIR}/${MOD_NAME}.log"
fi
exec > >(tee -a "${LOGDIR}/${MOD_NAME}.log") 2>&1

#####################################################################
# Main
#####################################################################
log "${MOD_NAME} - ${MOD_DESCRIPTION}"
log "${MOD_MAINTAINER}"
log_var STOCK_REPO
log_var OUTDIR


mkdir -p "${WORKDIR}" "${OUTDIR}"
reown "${WORKDIR}" "${OUTDIR}"

[[ -s "${TOKENFILE}" ]] || die "no HF token at ${TOKENFILE}; the overlay repo is gated"
TOKEN="$(cat "${TOKENFILE}")"

# 1) Fetch the author's script + the EXL3 sidecar at the pinned revision.
python3 - "$OVERLAY_REPO" "$OVERLAY_REVISION" "$WORKDIR" "$TOKEN" <<'PY'
import os, sys, urllib.request
repo, rev, workdir, token = sys.argv[1:5]
base = f"https://huggingface.co/{repo}/resolve/{rev}"
for name in ("apply_mia_exl3_wob.py", "mia_exl3_wo_b_l10_35.safetensors"):
    dest = os.path.join(workdir, name)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        print(f"  present {name}")
        continue
    req = urllib.request.Request(f"{base}/{name}", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = r.read()
    if not data:
        raise SystemExit(f"empty body for {name}")
    tmp = dest + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dest)
    print(f"  fetched {name} ({len(data)} bytes)")
PY

SCRIPT="${WORKDIR}/apply_mia_exl3_wob.py"
SIDECAR="${WORKDIR}/mia_exl3_wo_b_l10_35.safetensors"
[[ -s "${SCRIPT}" ]] || die "graft script missing"
[[ -s "${SIDECAR}" ]] || die "sidecar missing"

# 2) Locate the stock pack in the container's HF cache (refs/main first, else newest
#    config-bearing snapshot). The recipe's `{model}` is not what the launcher serves, so this
#    resolves independently -- same mechanism as the tensorfold launcher's resolver.
STOCK="$(python3 - "$HF_HUB" "$STOCK_REPO" <<'PY'
import sys
from pathlib import Path
hub, repo = sys.argv[1], sys.argv[2]
root = Path(hub) / ("models--" + repo.replace("/", "--"))
ref = root / "refs" / "main"
if ref.is_file():
    snap = root / "snapshots" / ref.read_text().strip()
    if (snap / "config.json").is_file():
        print(snap); raise SystemExit(0)
snaps = sorted((root / "snapshots").glob("*")) if (root / "snapshots").is_dir() else []
for snap in reversed(snaps):
    if (snap / "config.json").is_file():
        print(snap); raise SystemExit(0)
raise SystemExit(1)
PY
)" || die "stock pack ${STOCK_REPO} not found under ${HF_HUB}"
log "stock: ${STOCK}"

# Never write through the stock directory: the author's script also refuses this.
[[ "$(realpath -m "${STOCK}")" != "$(realpath -m "${OUTDIR}")" ]] || die "OUTDIR equals the stock snapshot"

# The Engram tables live in the stock pack, and both TP=2 arms must share ONE copy. The
# author's script *copytrees* every directory of --src, and `engram/` is one: grafting
# straight from the snapshot copies the ~189 GiB table set into the graft tree (~200 s of
# the 600 s hook budget, measured 2026-10-17). So: link the tables into the graft tree and
# hand the script a view without engram/. The link step also repairs a graft built before
# this change. It is safe before a first graft: the script skips a destination that already
# exists (apply_mia_exl3_wob.py:58-62), and the 2026-10-17 re-boot ran with an empty OUTDIR
# (modlog: the engram link, then `src view`, then `DONE ` -- edited 104).
link_engram() {
  if [[ -d "${STOCK}/engram" ]] && [[ "$(readlink "${OUTDIR}/engram" 2>/dev/null)" != "${STOCK}/engram" ]]; then
    rm -rf "${OUTDIR}/engram"
    ln -s "${STOCK}/engram" "${OUTDIR}/engram"
    log "engram: ${OUTDIR}/engram -> ${STOCK}/engram (one table set per node, not a copy)"
  fi
}
link_engram

# Idempotence from the artifact, not a timestamp: a completed graft carries the
# author's ABLIT_META.json with n_edited == 104.
if python3 - "${OUTDIR}/ABLIT_META.json" "${EXPECTED_N_EDITED}" <<'PY'
import json, sys
try:
    meta = json.load(open(sys.argv[1]))
except Exception:
    raise SystemExit(1)
raise SystemExit(0 if meta.get("n_edited") == int(sys.argv[2]) else 1)
PY
then
  log "graft already present and complete (n_edited=${EXPECTED_N_EDITED}) -- no-op"
  reown "${OUTDIR}"
  log "Done."
  exit 0
fi

# The src view: every stock entry except engram/, as ABSOLUTE symlinks. Absolute matters --
# the script os.link()s each shard it does not edit (apply_mia_exl3_wob.py:70-77), and
# Python's os.link uses link(2), which hardlinks the *symlink inode*, not the blob: over the
# snapshot's own relative `../../blobs/...` links the graft tree would hold links that do not
# resolve, while over this view's absolute ones it holds links that do. Nothing is copied but
# the 24 shards the graft rewrites (118.58 GiB; `du` == `du --apparent-size`, 2026-10-17).
VIEW="${WORKDIR}/stock-view"
rm -rf "${VIEW}"
mkdir -p "${VIEW}"
for entry in "${STOCK}"/*; do
  [[ "$(basename "${entry}")" == "engram" ]] && continue
  ln -s "${entry}" "${VIEW}/$(basename "${entry}")"
done
shopt -s nullglob
view_entries=("${VIEW}"/*)
shopt -u nullglob
log "src view: ${VIEW} (${#view_entries[@]} entries, engram/ excluded)"

# 3) Graft. The author's script rewrites only the shards carrying layers.10-35 attn.wo_b
#    (24 shards, 118.58 GiB of new bytes, ~150 s measured 2026-10-17) and links the rest.
#    It must fit sparkrun's 600 s pre-exec budget; a cold node that cannot is a launch
#    failure, not a degraded serve.
log "grafting (this rewrites the 24 shards carrying layers.10-35 attn.wo_b)..."
python3 "${SCRIPT}" --src "${VIEW}" --wo-b "${SIDECAR}" --dst "${OUTDIR}"
link_engram

# 4) Verify the artifact the launch depends on.
python3 - "${OUTDIR}/ABLIT_META.json" "${EXPECTED_N_EDITED}" <<'PY'
import json, sys
meta = json.load(open(sys.argv[1]))
n = meta.get("n_edited")
if n != int(sys.argv[2]):
    raise SystemExit(f"graft incomplete: n_edited={n}, expected {sys.argv[2]}")
print(f"  verified n_edited={n} method={meta.get('method')}")
PY
reown "${OUTDIR}"
log "Done."
