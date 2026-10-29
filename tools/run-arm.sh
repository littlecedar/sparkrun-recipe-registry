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
mkdir -p "$L"
cd "$HOME/src/sparkrun-recipe-registry" || exit 1
rc=0

sparkrun run "$RECIPE" -H "$NODE" --cluster WOPR > "$L/launch.log" 2>&1 &

for _ in $(seq 1 60); do
  N=$(docker ps --format '{{.Names}}' | grep -m1 _solo || true)
  [ -n "$N" ] && break
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
echo "arm=$NAME container=$N task=$TID"

python3 tools/boot-watchdog.py --endpoint "http://$NODE:8000" --task-id "$TID" \
  --node "$NODE" --container "$N" --grace 1800 --log "$L/watchdog.log" &
WD=$!

ready=no
for _ in $(seq 1 90); do
  if [ "$(curl -s -m 3 -o /dev/null -w '%{http_code}' "http://$NODE:8000/v1/models")" = 200 ]; then
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