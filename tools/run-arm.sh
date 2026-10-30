#!/usr/bin/env bash
# run-arm.sh <recipe-path> [node] — one arm end to end: boot, watch, measure, STOP, verify.
#
# Written after a 122B arm finished its two benchmarks and left the serve running
# for 18 minutes until someone noticed: the ad-hoc chain had no stop step, so a
# finished arm idled a node with a live container on it. The stop and the
# verification are the point of this script as much as the measurement is, and
# they run even when a benchmark fails.
#
# Receipts land in ~/benchmarks/tp12-<YYYYMMDD>/<arm>/. A failed benchmark does
# not skip the stop: everything after the readiness gate is attempted, and the
# exit status records which step failed.
set -uo pipefail

RECIPE=${1:?usage: run-arm.sh <recipe-path> [node]}
NODE=${2:-${ARM_NODE:-}}
NAME=$(basename "$RECIPE" .yaml)
L="$HOME/benchmarks/tp12-$(date +%Y%m%d)/$NAME"
# The serve port is the recipe's, not always 8000 -- the decision lane uses
# 8020 and the ling arm 8030. Probing the wrong port looks exactly like a boot
# that never becomes ready, which cost two arms a full 22-minute wait on
# 2026-10-29 before the port was even suspected.
PORT=$(sed -n -e 's/^[[:space:]]*port:[[:space:]]*"\([0-9][0-9]*\)".*/\1/p' \
                -e 's/^[[:space:]]*port:[[:space:]]*\([0-9][0-9]*\).*/\1/p' "$RECIPE" | head -1)
PORT=${PORT:-8000}
mkdir -p "$L"
cd "$HOME/src/sparkrun-recipe-registry" || exit 1
rc=0

sparkrun run "$RECIPE" -H "$NODE" --cluster WOPR > "$L/launch.log" 2>&1 &
LAUNCH=$!

# The container lives on the TARGET node, which is not necessarily the host this
# script runs on (the head launches onto either free node). Resolve it locally
# when the target is this host, over ssh otherwise.
if hostname -I 2>/dev/null | tr ' ' '\n' | grep -qx "$NODE"; then
  on_node() { sh -c "$1"; }
else
  on_node() { ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$NODE" "$1"; }
fi

for _ in $(seq 1 60); do
  N=$(on_node "docker ps --format '{{.Names}}' | grep -m1 _solo" 2>/dev/null | tr -d '\r' || true)
  [ -n "$N" ] && break
  # A refused launch (a stale resource claim, a missing recipe, a placement
  # failure) exits at once. Waiting the full five minutes for a container that
  # will never appear burns another lane's window -- measured 2026-10-29 when a
  # dead pid's reservation blocked `.35` and the script spun anyway.
  if ! kill -0 "$LAUNCH" 2>/dev/null; then
    echo "ARM FAIL $NAME: launcher exited with no container. Last lines:"
    tail -5 "$L/launch.log"
    exit 5
  fi
  sleep 5
done
if [ -z "$NODE" ]; then
  echo "usage: run-arm.sh <recipe-path> [node-ip]  (or set ARM_NODE)"
  exit 1
fi

if [ -z "${N:-}" ]; then
  echo "ARM FAIL $NAME: no container appeared (see $L/launch.log)"
  exit 1
fi
TID=${N#sparkrun_}; TID=${TID%_solo}
echo "arm=$NAME container=$N task=$TID port=$PORT"

# Whatever happens to this script -- SIGINT, SIGTERM, an early exit, a timeout --
# the task does not outlive it. The explicit stop below is the normal path; this
# trap is the one that covers the script being killed mid-measurement, which is
# the same class of leak as forgetting the stop entirely.
trap 'sparkrun stop "$TID" >/dev/null 2>&1; [ -n "${WD:-}" ] && kill "$WD" 2>/dev/null; exit' EXIT INT TERM

python3 tools/boot-watchdog.py --endpoint "http://$NODE:$PORT" --task-id "$TID" \
  --node "$NODE" --container "$N" --grace 1800 --log "$L/watchdog.log" &
WD=$!

ready=no
for _ in $(seq 1 90); do
  if [ "$(curl -s -m 3 -o /dev/null -w '%{http_code}' "http://$NODE:$PORT/v1/models")" = 200 ]; then
    ready=yes; break
  fi
  sleep 15
done
echo "readiness=$ready"

if [ "$ready" = yes ]; then
  sparkrun benchmark performance "$RECIPE" --profile benchmarking/concurrency-ladder.yaml \
    --skip-run -H "$NODE" --cluster WOPR --output "$L/ladder.yaml" > "$L/ladder.log" 2>&1 \
    || { echo "ladder failed for $NAME"; rc=2; }
  sparkrun benchmark run "$RECIPE" --profile benchmarking/standard-suite.yaml \
    --skip-run -H "$NODE" --cluster WOPR --output "$L/house.yaml" > "$L/house.log" 2>&1 \
    || { echo "suite failed for $NAME"; rc=3; }
else
  rc=4
fi

# Always tear down: an idle serve is a held node, which is the defect this
# script exists to prevent.
sparkrun stop "$TID" 2>&1 | tail -1
kill "$WD" 2>/dev/null
sleep 5
for n in 30 35; do
  ssh -o ConnectTimeout=4 -o BatchMode=yes "red@10.0.4.$n" \
    "printf '%s ctns=%s vols=%s\n' \$(hostname) \$(docker ps -aq | wc -l) \$(docker volume ls -q | wc -l)"
done
echo "ARM DONE $NAME rc=$rc"
exit "$rc"