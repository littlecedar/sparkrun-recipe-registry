#!/bin/bash
# SPDX-FileCopyrightText: 2026 Little Cedar Group
#
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail
# A dead filter must cost log lines, never the serve: SIG_IGN survives exec, so
# the engine's next write returns EPIPE instead of raising SIGPIPE.
trap '' PIPE

#####################################################################
# README
#####################################################################
# Per-node launcher for the aneda arm (a picom (dsgb10) fork). One container
# per rank; every rank runs this script and branches on ANEDA_NODE_RANK,
# rendered from {launch.node_rank} in the recipe's env.
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
# shortcut: unknown argv is ignored, because the `aneda` runtime appends no
# flags today; when a sparkrun release starts appending one that matters, make
# this launcher parse strictly.
#####################################################################

NODE="${ANEDA_NODE_HOST:-${HOSTNAME:-$(hostname)}}"
# Launcher lines are records too: the same envelope the filter writes, with the
# old text inside msg= so it stays greppable.
emit() {  # level msg
  local level=$1 msg=$2 now ts
  # EPOCHREALTIME + bash's printf: GNU and uutils `date` disagree on `%3N`.
  now=${EPOCHREALTIME/,/.}
  ts=$(TZ=UTC0 printf '%(%Y-%m-%dT%H:%M:%S)T' "${now%.*}")
  ts="${ts}.${now#*.}"
  msg=${msg//\\/\\\\}
  msg=${msg//\"/\\\"}
  msg=${msg//$'\n'/\\n}
  printf 'ts=%sZ level=%s node=%s rank=%s src=launcher event=launcher.log msg="%s"\n' \
    "${ts:0:23}" "${level}" "${NODE}" "${ANEDA_NODE_RANK:-0}" "${msg}"
}
refuse() { emit error "aneda-launcher: $*" >&2; exit 2; }

ROOT="${ANEDA_ROOT:-/cache/runtime/aneda}"
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
[[ -n "${MODEL}" && -n "${SERVED}" && -n "${PORT}" ]] ||
  refuse "launch.sh needs --model DIR --served-model-name NAME --port N"

R="${ANEDA_NODE_RANK:-}"
[[ -n "${R}" ]] || refuse "ANEDA_NODE_RANK missing: the recipe must render it from the launch node_rank template"
[[ "${R}" =~ ^[0-3]$ ]] || refuse "ANEDA_NODE_RANK '${R}' is not 0-3"

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# The mod runs first and publishes what the hook environment carries (rank 0's
# management address, this node's rail tail, the resolved fabric) beside the
# cache root sparkrun exported. Consumed, not re-derived.
FABRIC_ENV="${ROOT}/fabric.env"
[[ -s "${FABRIC_ENV}" ]] ||
  refuse "${FABRIC_ENV} missing: the aneda-launcher mod must run before the command"
. "${FABRIC_ENV}"

# sparkrun hands over one of two shapes: a prepared container path when model
# distribution ran (a bare `-H` launch), or the repo id when it did not (a
# profile with distribution.model disabled). The cache root is the exported one
# (`HF_HOME`, carried in fabric.env as ANEDA_CACHE) — never a guessed `/cache`.
resolve_model() {
  if [[ -d "${MODEL}" ]]; then
    printf '%s\n' "${MODEL}"
    return 0
  fi
  local hub="${ANEDA_CACHE:-${HF_HOME:-/cache/huggingface}}/hub" dir
  [[ -n "${REVISION}" ]] ||
    refuse "'${MODEL}' is a repo id but --revision is empty; refusing to follow refs/main"
  dir="${hub}/models--${MODEL//\//--}/snapshots/${REVISION}"
  [[ -d "${dir}" ]] ||
    refuse "pinned snapshot ${dir} is absent under the cache root ${hub}; refusing to serve another revision"
  printf '%s\n' "${dir}"
}
MODEL=$(resolve_model) || exit 2
[[ -f "${MODEL}/tokenizer.json" ]] || refuse "${MODEL}/tokenizer.json missing"

LOG="${ROOT}/logs/rank.${R}.log"
FLEET="${ROOT}/fleet.conf"
SOCK="${ROOT}/run/engine.sock"
KEY="${ROOT}/run/api-key"
WEIGHTS="${ROOT}/weights/rank${R}.dsw"
ENGRAM="${ROOT}/engram"
MIN_AVAIL_GIB="${ANEDA_MIN_AVAIL_GIB:-100}"
MIN_DISK_GIB="${ANEDA_MIN_DISK_GIB:-150}"
# Re-convert peak is one extra copy, not two: dsw_convert writes ${WEIGHTS}.new
# beside the old 72.38 GiB file and itself demands "72.38 GiB + 2" (74.4 GiB),
# then the mv -f frees the old file before engram_pack's 50.7 GB check runs.
MIN_DISK_RECONVERT_GIB=78
READY_S="${ANEDA_ENGINE_READY_S:-900}"

log() { emit info "[aneda-launcher] $*" | tee -a "${LOG}"; }
die() { emit fatal "FATAL: $*" | tee -a "${LOG}"; exit 2; }

# One filter per stream, restarted after a crash (a restart loses only the gap's
# bytes). A clean exit means the stream ended, so the loop stops with it.
stream() {  # src logfile
  while :; do
    python3 -u "${SCRIPT_DIR}/logprefix.py" --src "$1" --rank "${R}" && break
    sleep 0.2
  done | tee -a "$2"
}

mkdir -p "${ROOT}"/{run,logs,weights,engram,spill}

# Retention: the live filename never changes; previous boots become .1…KEEP.
# rotate() shifts whole boots at launch; the per-stream tickers below rotate_live()
# a long boot in place, so ANEDA_LOG_MIB caps a single boot too.
LOG_MIB="${ANEDA_LOG_MIB:-16}"
LOG_KEEP="${ANEDA_LOG_KEEP:-3}"
rotate() {  # file: file -> file.1 -> ... -> file.KEEP, older generations pruned
  local f=$1 i stale
  for stale in "$f".[0-9]*; do
    [[ -e "$stale" ]] || continue
    (( ${stale##*.} > LOG_KEEP )) && rm -f "$stale"
  done
  [[ -s "$f" ]] || return 0
  for ((i = LOG_KEEP - 1; i >= 1; i--)); do
    [[ -f "$f.$i" ]] && mv -f "$f.$i" "$f.$((i + 1))"
  done
  mv -f "$f" "$f.1"
  return 0
}
# Copy-then-truncate keeps the tee's append fd on the live inode; a rename would strand it.
rotate_live() {  # file: rotate a log a running process appends to, once past LOG_MIB
  local f=$1 i
  [[ "$(stat -c %s "$f" 2>/dev/null || echo 0)" -gt $((LOG_MIB << 20)) ]] || return 0
  for ((i = LOG_KEEP - 1; i >= 1; i--)); do
    [[ -f "$f.$i" ]] && mv -f "$f.$i" "$f.$((i + 1))"
  done
  cp "$f" "$f.1" && : > "$f"
  return 0  # a failed copy retries on the next tick; the ticker must not die
}
rotate "${LOG}"
if [[ "${R}" = 0 ]]; then rotate "${ROOT}/logs/front.log"; fi
# Auth off by default: this fleet serves behind an API proxy that sends no bearer,
# and dsfront runs keyless (frontend/src/main.rs:120-121 warns, server.rs:215-216
# skips the check). ANEDA_AUTH=1 restores the mod's key and `--api-key-file`.
AUTH="${ANEDA_AUTH:-0}"
KEY_ARGS=()
if [[ "${AUTH}" = 1 ]]; then
  [[ -s "${KEY}" ]] || die "ANEDA_AUTH=1 but ${KEY} is missing: the aneda-launcher mod must run before the command"
  chmod 600 "${KEY}"
  KEY_ARGS=(--api-key-file "${KEY}")
fi

#####################################################################
# Fleet file: this rank's tail list, assembled on the management network
#####################################################################
# Every rank knows its own rail tail (the mod proved it against the RoCE GID)
# and rank 0's management address (SPARKRUN_HEAD_HOST, hook-only, carried in
# fabric.env). Rank 0 collects the three peers' tails and answers each with the
# assembled list; RANK_TAILS from the recipe env still wins verbatim.
if [[ -z "${ANEDA_RANK_TAILS:-}" ]]; then
  log "rank ${R}: no ANEDA_RANK_TAILS; exchanging rail tails with rank 0 at ${ANEDA_HEAD:?fabric.env carries no rank 0 address}:19110"
  ANEDA_RANK_TAILS=$(python3 "${SCRIPT_DIR}/rendezvous.py" \
    --head "${ANEDA_HEAD}" --rank "${R}" --tail "${ANEDA_OWN_TAIL:?fabric.env carries no own tail}" \
    --timeout "${ANEDA_RENDEZVOUS_TIMEOUT_S:-300}" \
    2> >(python3 -u "${SCRIPT_DIR}/logprefix.py" --src mod --rank "${R}" >&2)) ||
    die "rank ${R}: the tail rendezvous failed; the engine is not started on a partial fleet"
  log "rank ${R}: tails assembled: ${ANEDA_RANK_TAILS}"
fi
export ANEDA_RANK_TAILS ANEDA_FABRIC_A ANEDA_FABRIC_B ANEDA_DEV_A ANEDA_DEV_B ANEDA_GID_INDEX
bash "${SCRIPT_DIR}/fleet-render.sh" "${FLEET}.new" ||
  die "fleet rendering refused the fabric inputs (see the message above)"
mv -f "${FLEET}.new" "${FLEET}"
log "rank ${R}: rendered ${FLEET} for tails [${ANEDA_RANK_TAILS}] on ${ANEDA_FABRIC_A}/${ANEDA_FABRIC_B} via ${ANEDA_DEV_A}/${ANEDA_DEV_B}, GID ${ANEDA_GID_INDEX}"

#####################################################################
# One-time per-rank artifacts from the shared checkpoint
#####################################################################
# Markers carry the resolved snapshot path ($MODEL includes the revision): an empty
# marker from a cache written before this change is a miss and re-converts once.
# Two cases, two totals: a fresh convert lays the weight file and then the Engram
# shards down from nothing, while a re-convert runs beside the artifacts already
# here — dsw_convert writes ${WEIGHTS}.new and engram_pack writes .part shards,
# both renamed into place — so it needs one extra copy at a time, never both.
disk_gate() {
  local avail need why
  avail=$(df -Pk "${ROOT}" | awk 'NR==2 {print int($4/1048576)}')
  if [[ -s "${WEIGHTS}" ]]; then
    need="${MIN_DISK_RECONVERT_GIB}"
    why="re-convert beside the existing artifact (72.38 GiB new weight file, then a 50.7 GB Engram shard copy)"
  else
    need="${MIN_DISK_GIB}"
    why="fresh convert (72.38 GiB weight file, then 50.7 GB Engram, from nothing)"
  fi
  [[ "${avail}" -ge "${need}" ]] ||
    die "rank ${R}: ${why} needs ${need} GiB free but ${ROOT} has ${avail} GiB"
}

prepare_weights() {
  if [[ -s "${WEIGHTS}" && -f "${WEIGHTS}.ok" ]]; then
    local wmarker
    wmarker=$(cat "${WEIGHTS}.ok")
    if [[ "${wmarker}" == "${MODEL}" ]]; then return 0; fi
    log "rank ${R}: weight marker names '${wmarker}', not ${MODEL}: re-converting"
  fi
  command -v dsw_convert >/dev/null || die "dsw_convert missing from the image"
  disk_gate
  log "rank ${R}: converting ${MODEL} -> ${WEIGHTS} (72.38 GiB; one-time, in sparkrun's runtime cache)"
  dsw_convert --ckpt "${MODEL}" --rank "${R}" --plan ||
    die "dsw_convert --plan refused the checkpoint ${MODEL}"
  dsw_convert --ckpt "${MODEL}" --rank "${R}" --out "${WEIGHTS}.new" ||
    die "dsw_convert failed for rank ${R}"
  mv -f "${WEIGHTS}.new" "${WEIGHTS}"
  if [[ "${ANEDA_VERIFY:-0}" = 1 ]]; then
    log "rank ${R}: verifying every byte of ${WEIGHTS} (ANEDA_VERIFY=1)"
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
export DSGB10_RING_DIRECT="${ANEDA_RING_DIRECT:-2}"
export DSGB10_CF_MLP="${DSGB10_CF_MLP:-/opt/picom/cfmlp_cml.bin}"
[[ -f "${DSGB10_CF_MLP}" ]] || die "DSGB10_CF_MLP ${DSGB10_CF_MLP} missing: the engine exits at start without it"
read -r -a EARGS <<< "${ANEDA_ENGINE_ARGS:---max-ctx 1048576 --slots 16 --big-slots 4 --setenv DSGB10_BUDGET=1 --setenv DSGB10_DRAFT1=6 --setenv DSGB10_WIDE=64 --setenv DSGB10_WIDE_COST=24,2.2,57,1.1 --draft-head4 --draft-markov8 --setenv DSGB10_HEAD4_C1=1 --setenv DSGB10_CF_ALPHA=1.0 --setenv DSGB10_CERT=1}"
if [[ -n "${ANEDA_OEA:-}" ]]; then
  # Upstream's lossy batch-aware MoE re-route (DSGB10_OEA=4,12,9 in their
  # production line). Opt-in: the default arm stays strictly lossless.
  EARGS+=(--setenv "DSGB10_OEA=${ANEDA_OEA}")
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
  # The devices are the ones the fleet file names, resolved by the mod from
  # sparkrun's NCCL_IB_HCA / the RoCE GIDs: no literal device name lives here.
  local dev_a dev_b listed dev
  dev_a=$(sed -n 's/^NEXT_DEV0=//p' "${FLEET}")
  dev_b=$(sed -n 's/^NEXT_DEV1=//p' "${FLEET}")
  [[ -n "${dev_a}" && -n "${dev_b}" ]] ||
    die "${FLEET} names no RDMA devices: the aneda-launcher mod must run before the command"
  listed=$(ibv_devices 2>&1 | awk 'NR > 2 && NF { print $1 }' | tr '\n' ' ')
  for dev in "${dev_a}" "${dev_b}"; do
    printf '%s\n' ${listed} | grep -qx "${dev}" ||
      die "RDMA device ${dev} is not visible in the container's RDMA user space (ibv_devices lists: ${listed:-none}); the engine would abort with 'RDMA device ${dev} not found' — the image's libibverbs/provider stack is incomplete"
  done
  log "rank ${R}: RDMA devices visible: ${dev_a} ${dev_b}"
}
require_rdma_devices

if [[ "${R}" != 0 ]]; then
  log "rank ${R}: starting the engine (ring direct=${DSGB10_RING_DIRECT})"
  # Background children survive exec, so the ticker outlives this shell.
  ( while :; do sleep 60; rotate_live "${LOG}"; done ) & disown
  exec > >(stream engine "${LOG}") 2>&1
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
VISION="${ANEDA_VISION:-1}"
VISION_PORT="${ANEDA_VISION_PORT:-18950}"
STREAM_ARGS=()
[[ "${ANEDA_STREAM_TOOL_ARGS:-1}" = 1 ]] && STREAM_ARGS+=(--stream-tool-args)
FRONT_VISION=()
VLOOP=""
FPID=""
if [[ -n "${ANEDA_VISION_CMD:-}" ]]; then
  read -r -a VCMD <<< "${ANEDA_VISION_CMD}"
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
    emit warn "vision encoder exited (rc ${rc}); next start in ${delays[$i]} s"
    sleep "${delays[$i]}" & wait $!
    (( i < 4 )) && i=$((i + 1))
  done
}

if [[ "${VISION}" = 1 ]]; then
  log "rank 0: starting the vision encoder on 127.0.0.1:${VISION_PORT}"
  FRONT_VISION=(--vision-addr "127.0.0.1:${VISION_PORT}")
  ( while :; do sleep 60; rotate_live "${ROOT}/logs/vision.log"; done ) & disown
  vision_loop > >(tee -a "${ROOT}/logs/vision.log") 2>&1 &
  VLOOP=$!
fi

# rank.0.log keeps the receipt; the filter (then the tee) is what puts rank 0's
# `stats:` line (and the engine's other lines) in the container stdout sparkrun
# captures — ranks 1-3 and dsfront take the same path. Same shape as the
# rank != 0 branch above.
( while :; do sleep 60; rotate_live "${LOG}"; done ) & disown
engine > >(stream engine "${LOG}") 2>&1 &
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

LISTEN_IP="${ANEDA_LISTEN_ADDR:-}"
if [[ -z "${LISTEN_IP}" ]]; then
  host="${ANEDA_NODE_HOST:?ANEDA_NODE_HOST missing: the recipe must render it from the launch node_host template}"
  if [[ "${host}" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    LISTEN_IP="${host}"
  else
    LISTEN_IP=$(getent ahostsv4 "${host}" | awk '{print $1; exit}')
    [[ -n "${LISTEN_IP}" ]] || die "cannot resolve ${host} to an IPv4 address; set ANEDA_LISTEN_ADDR"
  fi
fi

read -r -a FARGS <<< "${ANEDA_FRONT_ARGS:-}"
# dsfront's single value for both the default and the hard cap on one reply's
# generated tokens (frontend/src/server.rs:522-528 clamps, never refuses).
MAX_TOKENS="${ANEDA_MAX_TOKENS:-32768}"
if [[ "${AUTH}" = 1 ]]; then AUTH_MODE="bearer required"; else AUTH_MODE="keyless"; fi
log "rank 0: starting dsfront on ${LISTEN_IP}:${PORT} (served name ${SERVED}, max_tokens ${MAX_TOKENS}, auth ${AUTH_MODE})"
( while :; do sleep 60; rotate_live "${ROOT}/logs/front.log"; done ) & disown
dsfront serve \
  --listen "127.0.0.1:${PORT}" \
  --listen "${LISTEN_IP}:${PORT}" \
  --engine-socket "${SOCK}" \
  "${KEY_ARGS[@]}" \
  --admin-socket "${ROOT}/run/front.admin" \
  --table-file "${ROOT}/run/front.table" \
  --hold-s 600 \
  --tokenizer "${MODEL}/tokenizer.json" \
  --model-name "${SERVED}" \
  --encoding "${ANEDA_ENCODING:-1017}" \
  --max-tokens "${MAX_TOKENS}" \
  "${FRONT_VISION[@]}" \
  "${STREAM_ARGS[@]}" \
  "${FARGS[@]}" \
  > >(stream front "${ROOT}/logs/front.log") 2>&1 &
FPID=$!

if wait -n; then rc=0; else rc=$?; fi
log "rank 0: a serve process exited (rc ${rc}); stopping the rest"
[[ -n "${FPID}" ]] && kill -TERM "${FPID}" 2>/dev/null
kill -TERM "${EPID}" 2>/dev/null || true
wait 2>/dev/null || true
exit "${rc}"
