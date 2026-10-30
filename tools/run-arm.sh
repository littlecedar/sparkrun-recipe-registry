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
# The decision lane's 400-case split as the instrument ships it (gzip);
# decision-ladder.py accepts .jsonl.gz directly.
DECISION_CASES=${DECISION_CASES:-$HOME/benchmarks/jev27-20261021/test.jsonl.gz}
# A leftover container of this recipe still running on the target holds the serve
# port, so the new engine never binds while the OLD one answers /v1/models -- a
# plausible 200 attributed to the wrong boot, which is what happened on .35 on
# 2026-10-29. The recipe path is a container label, so this is exact, not a guess.
LEFTOVER=$(ssh -o ConnectTimeout=4 -o BatchMode=yes "red@$NODE" \
  "for n in \$(docker ps --format '{{.Names}}'); do
     r=\$(docker inspect --format '{{index .Config.Labels \"sparkrun.recipe\"}}' \$n 2>/dev/null)
     [ \"\$r\" = \"$RECIPE\" ] && echo \$n
   done" 2>/dev/null)
for old in $LEFTOVER; do
  old_tid=${old#sparkrun_}; old_tid=${old_tid%_solo}
  echo "stopping leftover container of this recipe: $old"
  sparkrun stop "$old_tid" >/dev/null 2>&1 || ssh -o ConnectTimeout=4 -o BatchMode=yes \
    "red@$NODE" "docker rm -f $old" >/dev/null 2>&1
done

# A relaunch of the same arm would overwrite the earlier receipt, so an
# instrument that failed partway silently becomes a truncated one.
if [ -n "$(ls -A "$L" 2>/dev/null)" ]; then
  PREV="$L.prev-$(date +%H%M%S)"
  mv "$L" "$PREV" && echo "previous receipt moved to $PREV"
fi
mkdir -p "$L"
cd "$HOME/src/sparkrun-recipe-registry" || exit 1
rc=0

# A benchmark can print a complete table and still leave no machine-readable
# output (measured 2026-10-29: the 9B dflash arm exited 0 with both tables in its
# logs and no yaml/json on disk). rc=0 must mean the numbers are in files another
# tool can read, never that a table scrolled past.
artifacts() {
  for f in "$@"; do
    [ -s "$f" ] || { echo "no artifact: $f (the tables may exist only in the logs)"; rc=5; }
  done
}

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
for _ in $(seq 1 150); do
  if [ "$(curl -s -m 3 -o /dev/null -w '%{http_code}' "http://$NODE:$PORT/v1/models")" = 200 ]; then
    ready=yes; break
  fi
  sleep 15
done
echo "readiness=$ready"

# A decision arm answers /v1/systemone (or JEV's /v1/completions), never
# /chat/completions, so llama-benchy and tool-eval-bench's chat suite both fail
# its first task -- the same instrument gap the pooling lanes document. Measured
# 2026-10-29: clef-flash readied in 239 s and then scored rc=3 with [1/1] FAILED.
# Its instruments are the lane's own: decision-ladder.py for the cells and
# tool-eval-bench --decision-bench-only for the accuracy number.
SERVED=$(curl -s -m 10 "http://$NODE:$PORT/v1/models" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"][0]["id"])' 2>/dev/null)

if [ "$ready" = yes ]; then
  case "$RECIPE" in
    */decision/*)
      api=${ARM_LADDER_API:-systemone}
      head_opt=()
      [ -n "${ARM_DECISION_HEAD:-}" ] && head_opt=(--decision-head "$ARM_DECISION_HEAD")
      if [ "$api" = completions ] && [ ${#head_opt[@]} -eq 0 ]; then
        echo "note: $NAME serves /v1/completions; set ARM_DECISION_HEAD to score it"
      fi
      python3 tools/decision-ladder.py --base-url "http://$NODE:$PORT" --api "$api" \
        --model "$SERVED" --cases "$DECISION_CASES" --concurrency 1,2,5,10 \
        --runs 1 --limit 100 "${head_opt[@]}" --json "$L/ladder.json" \
        > "$L/ladder.log" 2>&1 || { echo "ladder failed for $NAME"; rc=2; }
      uvx tool-eval-bench@2.8.0 --base-url "http://$NODE:$PORT" --decision-bench-only \
        > "$L/teb-decision.log" 2>&1 || { echo "decision bench failed for $NAME"; rc=3; }
      artifacts "$L/ladder.json" "$L/teb-decision.log"
      ;;
    *)
      sparkrun benchmark performance "$RECIPE" --profile benchmarking/concurrency-ladder.yaml \
        --skip-run -H "$NODE" --cluster WOPR --output "$L/ladder.yaml" > "$L/ladder.log" 2>&1 \
        || { echo "ladder failed for $NAME"; rc=2; }
      sparkrun benchmark run "$RECIPE" --profile benchmarking/standard-suite.yaml \
        --skip-run -H "$NODE" --cluster WOPR --output "$L/house.yaml" > "$L/house.log" 2>&1 \
        || { echo "suite failed for $NAME"; rc=3; }
      artifacts "$L/ladder.yaml" "$L/house.yaml"
      ;;
  esac
else
  rc=4
fi

# Always tear down: an idle serve is a held node, which is the defect this
# script exists to prevent. `sparkrun stop` can be refused when its resource
# claim bookkeeping is stale ("held by pid ... which has exited without
# releasing it"), which left a measured arm's container Up for eight minutes on
# 2026-10-29 -- so the stop is verified and, failing that, this launch's own
# container is removed by name. Only a container this script resolved is ever
# removed.
sparkrun stop "$TID" 2>&1 | tail -1
kill "$WD" 2>/dev/null
sleep 5
if [ -n "${N:-}" ] && ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$NODE" \
     "docker ps --format '{{.Names}}'" 2>/dev/null | grep -qx "$N"; then
  echo "container survived sparkrun stop; removing $N by name"
  ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$NODE" "docker rm -f $N" >/dev/null 2>&1
  sleep 3
fi
for n in 30 35; do
  left=$(ssh -o ConnectTimeout=4 -o BatchMode=yes "red@10.0.4.$n" \
    "printf '%s ctns=%s vols=%s\n' \$(hostname) \$(docker ps -aq | wc -l) \$(docker volume ls -q | wc -l)")
  echo "$left"
  # A held node is the defect this script exists to prevent, so leftover state
  # is a failure, not a line of trivia in an otherwise green run.
  case "$left" in *"ctns=0 vols=0") ;; *) echo "leftover state on .$n: $left"; rc=6 ;; esac
done
echo "ARM DONE $NAME rc=$rc"
exit "$rc"