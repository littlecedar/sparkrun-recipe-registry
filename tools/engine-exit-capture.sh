#!/usr/bin/env bash
# engine-exit-capture.sh <capture-dir> <max-seconds> [label-filter]
#
# Runs ON the node that holds the container, armed BEFORE the launch. Written after the
# 2026-11-08 marlin trial on zz-ds4-1017-sm121-arm3-control: the engine printed two lines
# (`Auto-detected DSV4 routed-expert layout...`, `[TP0] Init parallel begin.`) and the
# container was gone ~1 s later, leaving launch.log's `exit status 137` as the only trace.
# Every post-mortem read missed it because sparkrun launches containers `--rm`
# (`orchestration/executors/docker.py:555`, `auto_remove` defaults to True): the daemon
# deletes the container ~26 ms after its `die` event -- measured on the fleet head, 2026-11-08,
# where a `docker logs` started on that event already answered "No such container". Nothing
# that runs after the exit can read the log; the capture has to own the container from
# `create`.
#
# On each `create` it attaches `docker logs -f` by container id (docker replays the log from
# the start, so an attach that begins before `start` still yields every line), and on `die`
# it records the exit code the event itself carries. Both are plain file writes on the node,
# so they outlive the container. A capture that cannot run or saw nothing says so in
# `<dir>/no-capture.txt`; it never leaves an empty file to be read as "no output".
#
# Exits on: its deadline, an idle window after every created container died, the event
# stream ending, or SIGTERM (the caller kills it at teardown via <dir>/pid).
set -uo pipefail

CAP=${1:?usage: engine-exit-capture.sh <capture-dir> <max-seconds> [label-filter]}
MAX=${2:-3600}
LABEL=${3:-}
IDLE_EXIT=${CAPTURE_IDLE_EXIT:-120}

mkdir -p "$CAP" 2>/dev/null || { echo "engine-exit-capture: cannot create $CAP" >&2; exit 1; }
printf '%s\n' "$$" > "$CAP/pid"

filters=(--filter type=container --filter event=create --filter event=die)
[ -n "$LABEL" ] && filters+=(--filter "label=$LABEL")

# A FIFO, not a pipeline or a coprocess: a pipeline hides docker's pid, and a named coproc
# runs the command in a subshell whose pid is not docker's -- killing either leaves a docker
# client on the node forever (measured). Here `$EV` is the docker process itself, and the
# FIFO keeps it out of the caller's stdout so the caller's ssh session ends with this script.
FIFO="$CAP.fifo"
rm -f "$FIFO"
mkfifo "$FIFO" 2>/dev/null || { echo "engine-exit-capture: cannot create $FIFO" >&2; exit 1; }
docker events "${filters[@]}" \
  --format '{{.Action}} {{.Actor.ID}} {{.Actor.Attributes.name}} {{.Actor.Attributes.exitCode}}' \
  < /dev/null > "$FIFO" 2> "$CAP/events.err" &
EV=$!
# Read-write open never blocks: a docker that fails to start must not hang the capture.
exec 3<> "$FIFO"

FOLLOW=()
cleanup() {
  kill "$EV" 2>/dev/null
  for p in ${FOLLOW[@]+"${FOLLOW[@]}"}; do kill "$p" 2>/dev/null; done
  rm -f "$FIFO"
}
trap cleanup EXIT TERM INT HUP

declare -A died=()
start=$SECONDS
last=$SECONDS
created=0
while :; do
  if read -r -t 5 act id name code <&3; then
    last=$SECONDS
    case "$act" in
      create)
        created=$((created + 1))
        unset "died[$name]"
        printf '# capture: create %s %s\n' "$name" "$id" >> "$CAP/$name.log"
        ( docker logs -f "$id" < /dev/null >> "$CAP/$name.log" 2>> "$CAP/$name.err" \
            || printf "# capture failed: docker logs -f %s ended in docker's error (see %s.err); the container was removed before or during the attach\n" \
                 "$id" "$name" >> "$CAP/$name.log" ) &
        FOLLOW+=($!)
        ;;
      die)
        [ "$code" = "<no value>" ] && code=unknown
        printf '# capture: die exit=%s\n' "$code" >> "$CAP/$name.die"
        died[$name]=1
        ;;
    esac
    continue
  fi
  rc=$?
  if [ "$rc" -le 128 ]; then break; fi     # not a timeout: the stream itself failed
  kill -0 "$EV" 2>/dev/null || break        # docker events exited
  [ $((SECONDS - start)) -ge "$MAX" ] && break
  if [ "$created" -gt 0 ] && [ "${#died[@]}" -ge "$created" ] && [ $((SECONDS - last)) -ge "$IDLE_EXIT" ]; then
    break
  fi
done

if [ "$created" -eq 0 ]; then
  detail=$(sed -n '1p' "$CAP/events.err" 2>/dev/null)
  printf '# capture failed: no container%s was created in %s s of watching %s; docker said: %s\n' \
    "${LABEL:+ carrying $LABEL}" "$((SECONDS - start))" "$CAP" "${detail:-nothing}" \
    > "$CAP/no-capture.txt"
fi
