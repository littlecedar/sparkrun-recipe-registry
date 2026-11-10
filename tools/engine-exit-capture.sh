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
# the start, so an attach that begins before `start` still yields every line), on `die` it
# records the exit code the event itself carries, and on `oom` it records that the container's
# cgroup memory limit killed a process in it. Docker emits `oom` BEFORE `die` (measured
# 2026-11-10), so it survives `--rm` and is the only evidence of a `--memory` kill: the victim
# may be a child of `sleep infinity` while the container lives on, in which case the exit code
# is 0 (`# capture: die exit=0`) and the `oom` line is the whole verdict. All three are plain
# writes on the node, so they outlive the container. A capture that cannot run or saw nothing
# says so in `<dir>/no-capture.txt`; it never leaves an empty file to be read as "no output".
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

filters=(--filter type=container --filter event=create --filter event=die --filter event=oom)
[ -n "$LABEL" ] && filters+=(--filter "label=$LABEL")

# A FIFO, not a pipeline or a coprocess: a pipeline hides docker's pid, and a named coproc
# runs the command in a subshell whose pid is not docker's -- killing either leaves a docker
# client on the node forever (measured). Here `$EV` is the docker process itself, and the
# FIFO keeps it out of the caller's stdout so the caller's ssh session ends with this script.
FIFO="$CAP.fifo"
rm -f "$FIFO"
mkfifo "$FIFO" 2>/dev/null || { echo "engine-exit-capture: cannot create $FIFO" >&2; exit 1; }
exec 3<> "$FIFO"

FOLLOW=()
EV=
cleanup() {
  [ -n "$EV" ] && kill "$EV" 2>/dev/null
  for p in ${FOLLOW[@]+"${FOLLOW[@]}"}; do kill "$p" 2>/dev/null; done
  rm -f "$FIFO"
}
trap cleanup EXIT TERM INT HUP

declare -A died=()
start=$SECONDS
last=$SECONDS
created=0
deadline=0

# The read loop records `read`'s own status, and the event client is restarted rather than
# trusted. On the 2026-11-08 marlin lease (7 boots, 4 nodes) every capture said "no container
# ... in 5 s" with an empty stderr, because the old loop took `rc=$?` AFTER `if read ...; then
# ...; fi` -- the status of the `if` statement, always 0 when no branch runs -- so the first idle
# read timeout looked like a dead stream and the watcher stopped after exactly one 5 s wait while
# `docker events` was still alive (`bash -x` shows `read -r -t 5` / `rc=0` / `[ 0 -le 128 ]` /
# `break`; the liveness check never ran). A timeout is the normal idle case: only `kill -0`
# decides whether the instrument is broken, and a broken one is recorded in events.err and
# restarted -- the container it was armed for has not existed yet, so its absence is not a
# verdict.
while [ "$deadline" -eq 0 ]; do
  # Checked here as well as in the read loop: a client that dies instantly must not spin past
  # the deadline (a dead docker daemon would otherwise restart the stream forever).
  [ $((SECONDS - start)) -ge "$MAX" ] && break
  docker events "${filters[@]}" \
    --format '{{.Action}} {{.Actor.ID}} {{.Actor.Attributes.name}} {{.Actor.Attributes.exitCode}}' \
    < /dev/null > "$FIFO" 2> "$CAP/events.stream.err" &
  EV=$!
  stream_start=$SECONDS
  while :; do
    kill -0 "$EV" 2>/dev/null || break      # the client died: a broken instrument, not a verdict
    read -r -t 5 act id name code <&3
    rc=$?
    if [ "$rc" -eq 0 ]; then
      # `read -t` returns success with no fields when a reaped child interrupts it (the
      # `docker logs -f` attach is such a child on the first event): not an event.
      [ -z "${act:-}" ] && continue
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
        oom)
          # The container's cgroup memory limit killed a process in it. Names the container,
          # NOT the victim: a child can die while PID 1 (`sleep infinity`) lives on, which is
          # the shape sparkrun launches, so the exit code may still be 0. Read this beside
          # whether the serve died, never instead of it.
          printf '# capture: oom %s %s\n' "$id" "$name" >> "$CAP/$name.oom"
          ;;
      esac
      continue
    fi
    # Classify the failure before the deadline is considered: a client that died is a broken
    # instrument and must be named in events.err even when the deadline falls inside the same
    # read timeout, or a broken capture reads as "no container was created".
    if ! kill -0 "$EV" 2>/dev/null; then break; fi
    if [ $((SECONDS - start)) -ge "$MAX" ]; then deadline=1; break; fi
    if [ "$rc" -gt 128 ]; then
      if [ "$created" -gt 0 ] && [ "${#died[@]}" -ge "$created" ] \
         && [ $((SECONDS - last)) -ge "$IDLE_EXIT" ]; then deadline=1; break; fi
      continue
    fi
    break                                    # stream ended (EOF, or the client died)
  done
  [ "$deadline" -eq 1 ] && break
  if [ "$created" -gt 0 ]; then
    # Containers were seen; a stream that then ends is the shape the old script exited on too.
    # Record it and stop: their logs are already on disk.
    printf '# capture: docker events ended after %s s (%s container(s) captured)\n' \
      "$((SECONDS - stream_start))" "$created" >> "$CAP/events.err"
    break
  fi
  wait "$EV" 2>/dev/null
  printf '# capture: docker events exited rc=%s with no container after %s s; docker said: %s; restarting\n' \
    "$?" "$((SECONDS - stream_start))" "$(sed -n '1p' "$CAP/events.stream.err" 2>/dev/null)" \
    >> "$CAP/events.err"
  kill "$EV" 2>/dev/null
  sleep 2
done
kill "$EV" 2>/dev/null

if [ "$created" -eq 0 ]; then
  said=$(sed -n '1p' "$CAP/events.stream.err" 2>/dev/null)
  watch=$(sed -n '1p' "$CAP/events.err" 2>/dev/null)
  printf '# capture failed: no container%s was created in %s s of watching %s; docker said: %s%s\n' \
    "${LABEL:+ carrying $LABEL}" "$((SECONDS - start))" "$CAP" "${said:-nothing}" \
    "${watch:+; watch: $watch}" > "$CAP/no-capture.txt"
fi
