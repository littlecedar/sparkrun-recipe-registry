#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

#####################################################################
# README
#####################################################################
# Per-node launcher for the picom (dsgb10) arm. One container per rank;
# every rank runs this script and branches on PICOM_NODE_RANK, rendered
# from {launch.node_rank} in the recipe's env.
#
#   rank 0    : prepare rank 0's artifacts, start the engine, wait for its
#               socket, then run dsfront (the OpenAI HTTP front-end) in the
#               foreground.
#   rank r>0  : prepare rank r's artifacts, then exec the engine.
#
# This replaces upstream's service.sh, whose only unavoidable job is
# starting ranks 1-3 over ssh — impossible when sparkrun owns one container
# per node. What it keeps from service.sh: the page-cache drop before the
# engine starts (GB10's CUDA sees only free pages), the 100 GiB
# MemAvailable gate, and the same engine argv. What it drops: the ring
# lock, restart supervision and kept sessions (a sparkrun arm is one
# dedicated serve; sparkrun's own lifecycle owns restarts).
#
# First boot is expensive and one-time per node: dsw_convert writes this
# rank's 72.38 GiB weight file from the shared checkpoint and engram_pack
# writes its 50.7 GB Engram shards. sparkrun binds this path into its
# per-runtime cache leaf (core/runtime_cache.py, core/launcher.py), so later
# boots reuse them; the .ok marker files are what make that reuse safe.
#
# short-cut: unknown argv is ignored, because the vllm-distributed family
# runtime may append its own flags; when a sparkrun release starts gating on
# them, switch this arm to a dedicated runtime plugin.
#####################################################################

ROOT="${PICOM_ROOT:-/cache/runtime/picom}"
MODEL=""
REVISION=""
SERVED=""
PORT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) MODEL="${2:?--model needs a value}"; shift 2 ;;
    --revision) REVISION="${2:?--revision needs a value}"; shift 2 ;;
    --served-model-name) SERVED="${2:?--served-model-name needs a value}"; shift 2 ;;
    --port) PORT="${2:?--port needs a value}"; shift 2 ;;
    *) shift ;;
  esac
done
[[ -n "${MODEL}" && -n "${SERVED}" && -n "${PORT}" ]] || {
  echo "picom-launcher: launch.sh needs --model DIR --served-model-name NAME --port N" >&2
  exit 2
}

R="${PICOM_NODE_RANK:?PICOM_NODE_RANK missing: the recipe must render it from the launch node_rank template}"
[[ "${R}" =~ ^[0-3]$ ]] || { echo "picom-launcher: PICOM_NODE_RANK '${R}' is not 0-3" >&2; exit 2; }

# The fleet's shared-cache profile makes sparkrun hand over the repo id, not a
# prepared path (distribution.model disabled: nothing is bound at launch), so
# resolve the pinned snapshot from the mounted HF cache here — never the
# cache's moving refs/main.
resolve_model() {
  if [[ -d "${MODEL}" ]]; then
    printf '%s\n' "${MODEL}"
    return 0
  fi
  local hub="/cache/huggingface/hub" dir
  [[ -n "${REVISION}" ]] || {
    echo "picom-launcher: '${MODEL}' is a repo id but --revision is empty; refusing to follow refs/main" >&2
    return 2
  }
  dir="${hub}/models--${MODEL//\//--}/snapshots/${REVISION}"
  [[ -d "${dir}" ]] || {
    echo "picom-launcher: pinned snapshot ${dir} is absent; refusing to serve another revision" >&2
    return 2
  }
  printf '%s\n' "${dir}"
}
MODEL=$(resolve_model) || exit 2
[[ -f "${MODEL}/tokenizer.json" ]] || { echo "picom-launcher: ${MODEL}/tokenizer.json missing" >&2; exit 2; }

LOG="${ROOT}/logs/rank.${R}.log"
FLEET="${ROOT}/fleet.conf"
SOCK="${ROOT}/run/engine.sock"
KEY="${ROOT}/run/api-key"
WEIGHTS="${ROOT}/weights/rank${R}.dsw"
ENGRAM="${ROOT}/engram"
MIN_AVAIL_GIB="${PICOM_MIN_AVAIL_GIB:-100}"
MIN_DISK_GIB="${PICOM_MIN_DISK_GIB:-150}"
READY_S="${PICOM_ENGINE_READY_S:-900}"

log() { echo "[picom-launcher] $*" | tee -a "${LOG}"; }
die() { log "FATAL: $*"; exit 2; }

mkdir -p "${ROOT}"/{run,logs,weights,engram,spill}
[[ -s "${FLEET}" ]] || die "${FLEET} missing: the picom-launcher mod must run before the command"
[[ -s "${KEY}" ]] || die "${KEY} missing: the picom-launcher mod must run before the command"
chmod 600 "${KEY}"

#####################################################################
# One-time per-rank artifacts from the shared checkpoint
#####################################################################
# Markers carry the resolved snapshot path ($MODEL includes the revision): an empty
# marker from a cache written before this change is a miss and re-converts once.
prepare_weights() {
  if [[ -s "${WEIGHTS}" && -f "${WEIGHTS}.ok" ]]; then
    local wmarker
    wmarker=$(cat "${WEIGHTS}.ok")
    if [[ "${wmarker}" == "${MODEL}" ]]; then return 0; fi
    log "rank ${R}: weight marker names '${wmarker}', not ${MODEL}: re-converting"
  fi
  command -v dsw_convert >/dev/null || die "dsw_convert missing from the image"
  local avail
  avail=$(df -Pk "${ROOT}" | awk 'NR==2 {print int($4/1048576)}')
  [[ "${avail}" -ge "${MIN_DISK_GIB}" ]] ||
    die "rank ${R} weight file needs ~78 GiB (and Engram ~51 GB) but ${ROOT} has ${avail} GiB free"
  log "rank ${R}: converting ${MODEL} -> ${WEIGHTS} (72.38 GiB; one-time, in sparkrun's runtime cache)"
  dsw_convert --ckpt "${MODEL}" --rank "${R}" --plan ||
    die "dsw_convert --plan refused the checkpoint ${MODEL}"
  dsw_convert --ckpt "${MODEL}" --rank "${R}" --out "${WEIGHTS}.new" ||
    die "dsw_convert failed for rank ${R}"
  mv -f "${WEIGHTS}.new" "${WEIGHTS}"
  if [[ "${PICOM_VERIFY:-0}" = 1 ]]; then
    log "rank ${R}: verifying every byte of ${WEIGHTS} (PICOM_VERIFY=1)"
    dsw_verify --ckpt "${MODEL}" --file "${WEIGHTS}" --threads 4 ||
      die "dsw_verify failed for rank ${R}: the weight file is not this checkpoint's"
  fi
  printf '%s\n' "${MODEL}" > "${WEIGHTS}.ok"
  log "rank ${R}: weight file ready"
}

prepare_engram() {
  if [[ -f "${ENGRAM}/rank${R}.ok" ]] &&
    [[ -s "${ENGRAM}/engram-l1-r${R}of4.bin" && -s "${ENGRAM}/engram-l14-r${R}of4.bin" ]]; then
    local emarker
    emarker=$(cat "${ENGRAM}/rank${R}.ok")
    if [[ "${emarker}" == "${MODEL}" ]]; then return 0; fi
    log "rank ${R}: Engram marker names '${emarker}', not ${MODEL}: re-packing"
  fi
  command -v engram_pack >/dev/null || die "engram_pack missing from the image"
  log "rank ${R}: packing Engram shards into ${ENGRAM} (50.7 GB; one-time, in sparkrun's runtime cache)"
  engram_pack "${MODEL}" "${ENGRAM}" "${R}" ||
    die "engram_pack failed for rank ${R}"
  python3 /opt/picom/bin/make_hashmap_stdlib.py "${MODEL}" "${ENGRAM}/engram_hashmap.bin" ||
    die "engram hash map failed"
  printf '%s\n' "${MODEL}" > "${ENGRAM}/rank${R}.ok"
  log "rank ${R}: Engram shards ready"
}

prepare_weights
prepare_engram

#####################################################################
# GB10 start conditions: page cache dropped, free memory checked
#####################################################################
python3 /opt/picom/bin/evict_cache.py "${WEIGHTS}" "${ENGRAM}"/engram-l1-r"${R}"of4.bin \
  "${ENGRAM}"/engram-l14-r"${R}"of4.bin >> "${LOG}" 2>&1 ||
  log "WARN: page-cache eviction failed; the engine may under-use the free-memory budget"
avail_gib=$(awk '/^MemAvailable:/ {printf "%d", $2 / 1048576}' /proc/meminfo)
[[ "${avail_gib:-0}" -ge "${MIN_AVAIL_GIB}" ]] ||
  die "MemAvailable ${avail_gib} GiB is under ${MIN_AVAIL_GIB} GiB: the four ranks need ~90 GiB each and a GB10 OOM can hang the box (another model loaded?)"

#####################################################################
# Engine argv — identical on every rank except --rank
#####################################################################
export DSGB10_RING_DIRECT="${PICOM_RING_DIRECT:-2}"
export DSGB10_CF_MLP="${DSGB10_CF_MLP:-/opt/picom/cfmlp_cml.bin}"
[[ -f "${DSGB10_CF_MLP}" ]] || die "DSGB10_CF_MLP ${DSGB10_CF_MLP} missing: the engine exits at start without it"
read -r -a EARGS <<< "${PICOM_ENGINE_ARGS:---max-ctx 1048576 --slots 16 --big-slots 4 --setenv DSGB10_BUDGET=1 --setenv DSGB10_DRAFT1=6 --setenv DSGB10_WIDE=64 --setenv DSGB10_WIDE_COST=24,2.2,57,1.1 --draft-head4 --draft-markov8 --setenv DSGB10_HEAD4_C1=1 --setenv DSGB10_CF_ALPHA=1.0 --setenv DSGB10_CERT=1}"
if [[ -n "${PICOM_OEA:-}" ]]; then
  # Upstream's lossy batch-aware MoE re-route (DSGB10_OEA=4,12,9 in their
  # production line). Opt-in: the default arm stays strictly lossless.
  EARGS+=(--setenv "DSGB10_OEA=${PICOM_OEA}")
fi

engine() {
  dsgb10_rank --rank "${R}" --mode serve --fleet "${FLEET}" \
    --socket "${SOCK}" --disk-dir "${ROOT}/spill" --disk-tag arm --keep-gib 0 \
    "${EARGS[@]}"
}

# Fail closed on the shape that cost a boot on 2026-11-17: the image carried
# libibverbs without ibverbs-providers, so enumeration returned 0 devices and
# the engine aborted with "RDMA device rocep1s0f0 not found" after the
# one-time weight/Engram work. One line here names the container's RDMA user
# space instead of an abort three processes later.
require_rdma_devices() {
  command -v ibv_devices >/dev/null ||
    die "ibv_devices missing from the image (install ibverbs-utils): the container's RDMA user space cannot be checked"
  local listed dev
  listed=$(ibv_devices 2>&1 | awk 'NR > 2 && NF { print $1 }' | tr '\n' ' ')
  for dev in "${PICOM_DEV_A:-rocep1s0f0}" "${PICOM_DEV_B:-roceP2p1s0f0}"; do
    printf '%s\n' ${listed} | grep -qx "${dev}" ||
      die "RDMA device ${dev} is not visible in the container's RDMA user space (ibv_devices lists: ${listed:-none}); the engine would abort with 'RDMA device ${dev} not found' — the image's libibverbs/provider stack is incomplete"
  done
  log "rank ${R}: RDMA devices visible: ${PICOM_DEV_A:-rocep1s0f0} ${PICOM_DEV_B:-roceP2p1s0f0}"
}
require_rdma_devices

if [[ "${R}" != 0 ]]; then
  log "rank ${R}: starting the engine (ring direct=${DSGB10_RING_DIRECT})"
  exec > >(tee -a "${LOG}") 2>&1
  exec dsgb10_rank --rank "${R}" --mode serve --fleet "${FLEET}" \
    --socket "${SOCK}" --disk-dir "${ROOT}/spill" --disk-tag arm --keep-gib 0 \
    "${EARGS[@]}"
fi

#####################################################################
# Rank 0: vision encoder (PR #15), then the engine, then the front-end;
# the shell stays pid 1 so a container stop ends them in the service's
# order (front-end and encoder first, rank 0 last so it stops 1-3).
#####################################################################
# The runtime cache persists, so the previous boot's socket is still on disk
# and the `-S` wait below would report the engine ready at once. Drop the stale
# engine and admin sockets; front.table is dsfront's session table and survives.
rm -f "${SOCK}" "${ROOT}/run/front.admin" ||
  die "rank 0: cannot remove the stale ${SOCK} or ${ROOT}/run/front.admin"
VISION="${PICOM_VISION:-1}"
VISION_PORT="${PICOM_VISION_PORT:-18950}"
STREAM_ARGS=()
[[ "${PICOM_STREAM_TOOL_ARGS:-1}" = 1 ]] && STREAM_ARGS+=(--stream-tool-args)
FRONT_VISION=()
VLOOP=""
FPID=""
if [[ -n "${PICOM_VISION_CMD:-}" ]]; then
  read -r -a VCMD <<< "${PICOM_VISION_CMD}"
else
  VCMD=(python3 /opt/picom/vision/vision_encoder.py --model "${MODEL}")
fi

# The encoder's life is the front-end's: started before the engine so its
# weights load meanwhile, restarted on exit with a widening delay, never
# counted as a serve failure (text requests are unaffected). Upstream's
# service.sh does the same; this arm's launcher replaces it.
vision_loop() {
  local delays=(2 10 60 300 900) i=0 pid="" rc
  trap '[[ -n "${pid}" ]] && kill -TERM "${pid}" 2>/dev/null; exit 0' TERM INT
  while :; do
    "${VCMD[@]}" --host 127.0.0.1 --port "${VISION_PORT}" &
    pid=$!
    if wait "${pid}"; then rc=0; else rc=$?; fi
    echo "$(date '+%F %T') vision encoder exited (rc ${rc}); next start in ${delays[$i]} s"
    sleep "${delays[$i]}" & wait $!
    (( i < 4 )) && i=$((i + 1))
  done
}

if [[ "${VISION}" = 1 ]]; then
  log "rank 0: starting the vision encoder on 127.0.0.1:${VISION_PORT}"
  FRONT_VISION=(--vision-addr "127.0.0.1:${VISION_PORT}")
  vision_loop >> "${ROOT}/logs/vision.log" 2>&1 &
  VLOOP=$!
fi

engine >> "${LOG}" 2>&1 &
EPID=$!
on_term() {
  log "rank 0: stopping (SIGTERM)"
  [[ -n "${VLOOP}" ]] && kill -TERM "${VLOOP}" 2>/dev/null || true
  [[ -n "${FPID}" ]] && kill -TERM "${FPID}" 2>/dev/null || true
  kill -TERM "${EPID}" 2>/dev/null || true
  wait 2>/dev/null || true
  exit 0
}
trap on_term TERM INT

log "rank 0: waiting for ${SOCK} (up to ${READY_S} s)"
deadline=$((SECONDS + READY_S))
until [[ -S "${SOCK}" ]]; do
  kill -0 "${EPID}" 2>/dev/null || die "the engine died before its socket appeared; tail of ${LOG}:"$'\n'"$(tail -n 20 "${LOG}")"
  (( SECONDS < deadline )) || die "the engine's socket did not appear in ${READY_S} s; tail of ${LOG}:"$'\n'"$(tail -n 20 "${LOG}")"
  sleep 2
done
log "rank 0: engine ready"

LISTEN_IP="${PICOM_LISTEN_ADDR:-}"
if [[ -z "${LISTEN_IP}" ]]; then
  host="${PICOM_NODE_HOST:?PICOM_NODE_HOST missing: the recipe must render it from the launch node_host template}"
  if [[ "${host}" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    LISTEN_IP="${host}"
  else
    LISTEN_IP=$(getent ahostsv4 "${host}" | awk '{print $1; exit}')
    [[ -n "${LISTEN_IP}" ]] || die "cannot resolve ${host} to an IPv4 address; set PICOM_LISTEN_ADDR"
  fi
fi

read -r -a FARGS <<< "${PICOM_FRONT_ARGS:-}"
log "rank 0: starting dsfront on ${LISTEN_IP}:${PORT} (served name ${SERVED})"
dsfront serve \
  --listen "127.0.0.1:${PORT}" \
  --listen "${LISTEN_IP}:${PORT}" \
  --engine-socket "${SOCK}" \
  --api-key-file "${KEY}" \
  --admin-socket "${ROOT}/run/front.admin" \
  --table-file "${ROOT}/run/front.table" \
  --hold-s 600 \
  --tokenizer "${MODEL}/tokenizer.json" \
  --model-name "${SERVED}" \
  --encoding "${PICOM_ENCODING:-1017}" \
  "${FRONT_VISION[@]}" \
  "${STREAM_ARGS[@]}" \
  "${FARGS[@]}" \
  > >(tee -a "${ROOT}/logs/front.log") 2>&1 &
FPID=$!

if wait -n; then rc=0; else rc=$?; fi
log "rank 0: a serve process exited (rc ${rc}); stopping the rest"
[[ -n "${FPID}" ]] && kill -TERM "${FPID}" 2>/dev/null
kill -TERM "${EPID}" 2>/dev/null || true
wait 2>/dev/null || true
exit "${rc}"
