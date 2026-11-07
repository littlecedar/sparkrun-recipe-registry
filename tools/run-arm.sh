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

# Resolve the recipe's relative path before anything reads it: the campaign passes manifest paths
# relative to the repo root, and the caller's cwd is the campaign directory.
cd "$HOME/src/sparkrun-recipe-registry" || exit 1

RECIPE=${1:?usage: run-arm.sh <recipe-path> [node[,node...]]}
# A TP=2 arm needs a PAIR: pass `a,b` and sparkrun gets both hosts while the endpoint, watchdog and
# container resolution use the FIRST (the API rank). Single-node arms are unaffected -- `HOSTS` is
# just `NODE` there, so every `-H` site stays the same expression.
HOSTS=${2:-${ARM_NODE:-}}
NODE=${HOSTS%%,*}
# ARM_TAG suffixes the receipt name (`-d4`, `-d8`): a sweep re-runs ONE recipe with different
# `-o` overrides, and without a tag every leg writes the same directory and rotates the previous
# leg to `.prev-<HHMMSS>` -- the numbers survive but the attribution does not.
NAME=$(basename "$RECIPE" .yaml)${ARM_TAG:+-$ARM_TAG}
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
  old_tid=${old#sparkrun_}; old_tid=${old_tid%_node_*}; old_tid=${old_tid%_solo}
  echo "stopping leftover container of this recipe: $old"
  sparkrun stop "$old_tid" >/dev/null 2>&1 || ssh -o ConnectTimeout=4 -o BatchMode=yes \
    "red@$NODE" "docker rm -f $old" >/dev/null 2>&1
done

# A container of a DIFFERENT recipe holding the serve port collides just as hard,
# and the same-recipe probe above cannot see it. Measured 2026-10-29: a dead int8
# container held 8000 on .35, this arm's launcher bound nothing, and the runner then
# resolved the int8 container as its own and measured a dead serve. Refuse instead
# of removing: the container may be another session's, and silently killing it is
# the mistake this register has made before.
# Containers are not the only holders: on .30 the BeeGFS management daemon owns
# *:8010 (`beegfs-mgmtd`), so any recipe serving on 8010 -- every embed and rerank
# arm defaults to it -- can never bind there. Measured 2026-10-30: vLLM died with
# `OSError: [Errno 98] Address already in use` while `docker port` showed nothing.
# The probe is fed on stdin so no quoting layer has to agree with another.
BLOCKER=$(ssh -o BatchMode=yes -o ConnectTimeout=4 "red@$NODE" "PORT=$PORT sh -s" <<'PROBE' 2>/dev/null | head -1
for n in $(docker ps --format '{{.Names}}'); do
  if docker port "$n" 2>/dev/null | grep -qE ":$PORT$"; then echo "$n (container)"; fi
done
if command -v ss >/dev/null 2>&1; then
  # Name the owning process when sudo allows it, and never fail the probe when it does
  # not: the refusal is the point, the name is a courtesy.
  line=$(sudo -n ss -ltnp 2>/dev/null | grep -E ":$PORT\b" | head -1)
  [ -n "$line" ] || line=$(ss -ltn 2>/dev/null | grep -E ":$PORT\b" | head -1)
  [ -n "$line" ] && echo "a host socket: $(echo "$line" | tr -s ' ')"
fi
PROBE
)
if [ -n "$BLOCKER" ]; then
  echo "ARM FAIL $NAME: port $PORT on $NODE is held by $BLOCKER"
  echo "stop it (or pick another node) before relaunching; nothing was launched"
  exit 7
fi

# A relaunch of the same arm would overwrite the earlier receipt, so an
# instrument that failed partway silently becomes a truncated one.
if [ -n "$(ls -A "$L" 2>/dev/null)" ]; then
  PREV="$L.prev-$(date +%H%M%S)"
  mv "$L" "$PREV" && echo "previous receipt moved to $PREV"
fi
mkdir -p "$L"
rc=0

# A benchmark can print a complete table and still leave no machine-readable
# output (measured 2026-10-29: the 9B dflash arm exited 0 with both tables in its
# logs and no yaml/json on disk). rc=0 must mean the numbers are in files another
# tool can read, never that a table scrolled past.
artifacts() {
  for f in "$@"; do
    [ -s "$f" ] && continue
    # llama-benchy sometimes prints a complete table and writes nothing (four times on
    # 2026-10-29, with no `CSV output` line in its own log). Transcribe it into the same
    # JSON shape, labelled with its provenance, so the receipt carries machine-readable
    # numbers that cannot be mistaken for the framework's own file.
    case "$f" in
      */ladder.yaml|*/ladder.json)
        logs=$(dirname "$f")/ladder.log
        if [ -s "$logs" ] && python3 tools/bench-table-to-json.py "$logs" \
             --json "$(dirname "$f")/ladder.transcribed.json" >/dev/null 2>&1; then
          echo "note: $f missing; transcribed the printed table into ladder.transcribed.json"
          continue
        fi ;;
      */house.yaml)
        logs=$(dirname "$f")/house.log
        if [ -s "$logs" ] && grep -q "score" "$logs"; then
          grep -hE "pass;|score" "$logs" | tail -1 > "$(dirname "$f")/house.transcribed.txt"
          echo "note: $f missing; kept the suite's own summary in house.transcribed.txt"
          continue
        fi ;;
    esac
    echo "no artifact: $f (and the log held nothing to transcribe)"; rc=5
  done
}

# A claim left behind by a dead sparkrun process refuses every launch on the fleet
# ("*: held by pid N, which has exited without releasing it") -- hit four times on
# 2026-10-29, once with both nodes idle. Reconcile only claims whose owner is dead;
# a live claim belongs to another session's run and must not be touched.
for owner in $(sparkrun daemon resources list 2>/dev/null \
    | python3 -c 'import json,sys
try: rows = json.load(sys.stdin)
except Exception: sys.exit(0)
print("\n".join(r.get("owner","") for r in rows if not r.get("alive", True) and r.get("owner")))' \
    | tr -d '"'); do
  echo "releasing a claim whose owner has exited: $owner"
  sparkrun daemon resources reconcile "$owner" --acknowledge-effects 2>&1 | tail -1
done

# A c10 rung over fewer than ten slots measures the slot limit, not the model: the same arm read
# 135.97 t/s at `parallel: 8` and 176.30 at `parallel: 10` an hour later (2026-11-03). The ladder this
# script runs includes c10, so fail closed unless the recipe grants >= 10, ARM_OPTS raises it, or a
# caller deliberately waives it. Durable form of the rule: mad-science/METHODOLOGY.md section 3.
if [ -z "${ARM_ALLOW_FEW_SLOTS:-}" ]; then
  RECIPE_SLOTS=$(sed -n 's/^[[:space:]]*parallel:[[:space:]]*\([0-9][0-9]*\).*/\1/p' "$RECIPE" | head -1)
  OPT_SLOTS=$(printf '%s' "${ARM_OPTS:-}" | tr ' ' '\n' | sed -n 's/^parallel=\([0-9][0-9]*\)$/\1/p' | tail -1)
  SLOTS=${OPT_SLOTS:-${RECIPE_SLOTS:-}}
  if [ -n "$SLOTS" ] && [ "$SLOTS" -lt 10 ]; then
    echo "ARM REFUSED $NAME: ladder includes c10 but the grant is parallel=$SLOTS."
    echo "  A c10 cell over $SLOTS slots measures the slot limit, not the model (135.97 vs 176.30 t/s,"
    echo "  2026-11-03). Pass ARM_OPTS=\"-o parallel=10\", raise the recipe default, or set"
    echo "  ARM_ALLOW_FEW_SLOTS=1 to record a deliberately slot-limited cell."
    exit 8
  fi
fi

# ARM_OPTS carries `-o key=value` overrides for one-off knobs (a sweep leg, a different
# draft-token count). Without it every setting needs its own recipe file.
launch_arm() {
  # shellcheck disable=SC2086
  sparkrun run "$RECIPE" -H "$HOSTS" --cluster WOPR ${ARM_OPTS:-} > "$L/launch.log" 2>&1 &
  LAUNCH=$!
}
launch_arm
for attempt in 1 2 3; do
  # Give the launcher a moment to fail fast on a held claim before deciding it is fine.
  for _ in $(seq 1 12); do
    kill -0 "$LAUNCH" 2>/dev/null || break
    sleep 1
  done
  grep -q "Execution resources are busy" "$L/launch.log" 2>/dev/null || break
  echo "claim busy (attempt $attempt): waiting for the holder to release $NODE"
  for _ in $(seq 1 60); do
    if ! sparkrun daemon resources list 2>/dev/null | grep -q '"resource": "\*"'; then break; fi
    sleep 5
  done
  launch_arm
done

# The container lives on the TARGET node, which is not necessarily the host this
# script runs on (the head launches onto either free node). Resolve it locally
# when the target is this host, over ssh otherwise.
if hostname -I 2>/dev/null | tr ' ' '\n' | grep -qx "$NODE"; then
  on_node() { sh -c "$1"; }
else
  on_node() { ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$NODE" "$1"; }
fi

for _ in $(seq 1 60); do
  # Both container shapes: `_solo` for TP=1, `_node_<rank>` for a multi-rank launch. Matching only
  # `_solo` made every TP=2 launch print ARM FAIL 301 s in while its containers booted happily
  # underneath (measured 2026-10-30, first pair run) -- same class as the boot-watchdog `_solo` fix,
  # opposite direction.
  N=$(on_node "docker ps --format '{{.Names}}' | grep -m1 -E '_solo|_node_0'" 2>/dev/null | tr -d '\r' || true)
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
TID=${N#sparkrun_}; TID=${TID%_node_*}; TID=${TID%_solo}
echo "arm=$NAME container=$N task=$TID port=$PORT"

# Whatever happens to this script -- SIGINT, SIGTERM, an early exit, a timeout --
# the task does not outlive it. The explicit stop below is the normal path; this
# trap is the one that covers the script being killed mid-measurement, which is
# the same class of leak as forgetting the stop entirely.
LOGFOLLOW=()
trap 'sparkrun stop "$TID" >/dev/null 2>&1; [ -n "${WD:-}" ] && kill "$WD" 2>/dev/null; for p in ${LOGFOLLOW[@]:-}; do kill "$p" 2>/dev/null; done; exit' EXIT INT TERM

# Each rank's own stdout/stderr, captured from the moment its container exists. `/tmp/sparkrun_serve.log`
# is written by the engine after the hooks, so a boot that dies in a pre_exec hook leaves no serve
# log at all (2026-11-03 cyankiwi, 2026-11-04 labquant trio). `docker logs` is the only copy that
# survives the container, and reading it live is what the cyankiwi retry is for.
for hn in $(echo "$HOSTS" | tr ',' ' '); do
  (
    for _ in $(seq 1 60); do
      c=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$hn" \
            "docker ps --format '{{.Names}}' | grep -F '$TID' | head -1" 2>/dev/null)
      if [ -n "$c" ]; then
        ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$hn" "docker logs -f '$c'" \
          > "$L/docker-$(echo "$hn" | tr '.' '_').log" 2>&1
        # A silent death (OOM kill, non-zero exit with no stderr) leaves `docker logs` holding only
        # the entrypoint banner. Append the container's own state while it still exists; if the
        # watchdog or the stop already removed it, the inspect error is itself the record.
        ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$hn" \
          "docker inspect -f 'exit={{.State.ExitCode}} oom={{.State.OOMKilled}} status={{.State.Status}}' '$c'" \
          >> "$L/docker-$(echo "$hn" | tr '.' '_').log" 2>&1
        break
      fi
      sleep 5
    done
  ) &
  LOGFOLLOW+=("$!")
done

python3 tools/boot-watchdog.py --endpoint "http://$NODE:$PORT" --task-id "$TID" \
  --node "$NODE" --container "$N" --interval 10 --log "$L/watchdog.log" &
WD=$!

# Only so the readiness-loop guard can drive this loop at 0 s; 15 s in a real arm.
POLL_SLEEP=${ARM_POLL_SLEEP:-15}
ready=no
wd_done=0
for _ in $(seq 1 150); do
  if [ "$(curl -s -m 3 -o /dev/null -w '%{http_code}' "http://$NODE:$PORT/v1/models")" = 200 ]; then
    ready=yes; break
  fi
  # The watchdog is the liveness instrument; poll it, not just the endpoint. Without this
  # the loop sat out its full 2250 s after the watchdog had already declared the serve
  # dead and stopped it (measured 2026-11-03: 28 min on a boot that died at t=98 s).
  # One shot only: `wait` reaps the child, so a second `kill -0` always fails and a second
  # `wait` warns forever (rc=127 under a POSIX shell, the cached status under bash) --
  # ~150 lines, against a loop that then has no liveness instrument at all.
  if [ "$wd_done" = 0 ] && ! kill -0 "$WD" 2>/dev/null; then
    wait "$WD"; wd_rc=$?; wd_done=1
    case "$wd_rc" in
      0) ready=yes ;;                                   # watchdog saw the endpoint answer
      3) echo "watchdog: serve dead and stopped (rc=3) at t=$((SECONDS))s -- never ready"
         ready=no; break ;;                             # rc=4 below, then harvest + teardown:
                                                        # a dead arm's serve log is the evidence
      *) echo "watchdog exited rc=$wd_rc (its own error) -- this boot has no liveness" \
              "instrument left; polling the endpoint only" ;;
    esac
    [ "$ready" = yes ] && break
  fi
  sleep "$POLL_SLEEP"
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
      ladder_rc=0
      python3 tools/decision-ladder.py --base-url "http://$NODE:$PORT" --api "$api" \
        --model "$SERVED" --cases "$DECISION_CASES" --concurrency 1,2,5,10 \
        --runs 1 --limit 100 "${head_opt[@]}" --json "$L/ladder.json" \
        > "$L/ladder.log" 2>&1 || {
          ladder_rc=$?
          echo "ladder failed for $NAME"
          rc=2
        }
      # --model is mandatory here: an arm that serves a base plus a LoRA adapter lists TWO models,
      # and the instrument's model picker then blocks on a prompt nothing will answer -- measured
      # 2026-10-30 on jev-9b, which sat at "Select model [1-2]:" until the run was killed.
      # And its decision mode speaks ONLY /v1/systemone (its own error text says so), so a JEV arm
      # on /v1/completions cannot be scored by it at all -- that is a gap in the instrument, not a
      # failure of the arm, and it made a clean cell run report rc=3.
      accuracy_rc=0
      if [ "$api" = completions ]; then
        echo "accuracy: tool-eval-bench --decision-bench-only speaks /v1/systemone only; this arm" \
             "answers /v1/completions, so no score is taken (the cells are the result)" \
             > "$L/teb-decision.log"
      else
        # The marker's accuracy_status is this command's outcome, not the configuration that
        # chose to run it: `taken` off `$api` alone claimed a score for an instrument run that
        # failed (same defect class as any marker derived from configuration rather than work).
        uvx tool-eval-bench@2.8.0 --base-url "http://$NODE:$PORT" --decision-bench-only \
          --model "$SERVED" > "$L/teb-decision.log" 2>&1 || {
            accuracy_rc=$?
            echo "decision bench failed for $NAME"
            rc=3
          }
      fi
      # The decision lane wrote `ladder.json` + `teb-decision.log` and no `house.*` at all, so a
      # driver whose arm-finished predicate wants a house artefact re-booted four finished arms
      # on 2026-11-04 (three rc=3 whose accuracy log is real, one rc=0). Same shape as the
      # pooling marker: machine-readable, written only once the ladder artefact exists because
      # the rc=2 above does not exit -- presence must not mean "finished" for a dead ladder. It
      # names the accuracy instrument and the file its output lives in rather than copying the
      # score: a number transcribed into a marker can drift from the log that measured it.
      # Presence says the arm finished; `accuracy_status` says what the instrument did. They are
      # deliberately not inferred from each other: a failed bench still leaves a finished arm (and
      # its log), and suppressing the marker for it would re-boot a measured arm.
      if [ -s "$L/ladder.json" ]; then
        echo "suite: n/a" > "$L/house.yaml"
        echo "reason: decision arm — the chat suite cannot address /v1/systemone" >> "$L/house.yaml"
        if [ "$ladder_rc" = 0 ]; then
          echo "ladder: ok" >> "$L/house.yaml"
        else
          # `-s` above only proves the file is non-empty: `decision-ladder.py --json` writes as it
          # goes, so a run that died partway leaves a partial artifact that the gate cannot see.
          # The field is what says the measurement failed, and presence still means "finished".
          echo "ladder: failed (rc=$ladder_rc) — the artifact is partial and is not a cell; re-attempt" >> "$L/house.yaml"
        fi
        echo "accuracy: tool-eval-bench --decision-bench-only" >> "$L/house.yaml"
        echo "accuracy_log: teb-decision.log" >> "$L/house.yaml"
        if [ "$api" = completions ]; then
          echo "accuracy_status: not-taken — the instrument speaks /v1/systemone only and this arm answers /v1/completions" >> "$L/house.yaml"
        elif [ "$accuracy_rc" = 0 ]; then
          echo "accuracy_status: taken — the score is in teb-decision.log" >> "$L/house.yaml"
        else
          echo "accuracy_status: failed (rc=$accuracy_rc) — the instrument ran and failed; its output is in teb-decision.log" >> "$L/house.yaml"
        fi
      fi
      artifacts "$L/ladder.json" "$L/teb-decision.log"
      ;;
    */embed/*|*/rerank/*)
      # A pooling engine has no /chat/completions, so llama-benchy fails its first task
      # and tool-eval-bench has no rows -- the gap the pooling lane documents. These arms
      # are measured by `benchmark pooling` against the shipped ladder profile, and the
      # chat suite does not apply to them at all.
      kind=embed; case "$RECIPE" in */rerank/*) kind=rerank ;; esac
      # The ladder profile checks reply dimensions against the shipped 8B encoder (4096);
      # its own note says a 2B arm needs -b dimension_check=2048 or EVERY reply fails the
      # shape check -- measured 2026-10-30: [1/4] FAILED in 3.1 s with no traceback.
      pooling_args=()
      case "$NAME" in *-2b-*|*2b-*) pooling_args=(-b dimension_check=2048) ;; esac
      pooling_rc=0
      sparkrun ${BENCH_VERBOSE:+-v} benchmark pooling "$RECIPE" \
        --profile "benchmarking/pooling-ladder-$kind.yaml" --skip-run --fresh \
        -H "$HOSTS" --cluster WOPR "${pooling_args[@]}" \
        --output "$L/ladder.yaml" > "$L/ladder.log" 2>&1 || {
          pooling_rc=$?
          echo "pooling ladder failed for $NAME"
          rc=2
        }
      echo "suite: n/a (pooling arm — the chat suite cannot address /v1/embeddings or /v1/rerank)" \
        > "$L/house.log"
      # A campaign driver calls an arm finished on a machine-readable `house.yaml|json|csv`
      # beside a ladder artefact, so the log line above left three completed pooling arms
      # looking unfinished on 2026-11-04 (each re-booted for nothing). Say the same n/a in a
      # file such a consumer can read -- but only once the ladder artefact exists, because the
      # rc=2 above does not exit and file presence must never mean "finished" for an arm whose
      # ladder died. No numbers: the chat suite has no rows for a pooling engine.
      if [ -s "$L/ladder.yaml" ]; then
        echo "suite: n/a" > "$L/house.yaml"
        echo "reason: pooling arm — the chat suite cannot address /v1/embeddings or /v1/rerank" >> "$L/house.yaml"
        echo "kind: $kind" >> "$L/house.yaml"
        if [ "$pooling_rc" = 0 ]; then
          echo "ladder: ok" >> "$L/house.yaml"
        else
          # Same convention as the decision marker: `-s` only proves the file is non-empty, and
          # sparkrun's exporter writes as it runs, so a ladder that died partway can leave a
          # partial artifact. The field carries the outcome; presence carries "finished".
          echo "ladder: failed (rc=$pooling_rc) — the artifact is partial and is not a cell; re-attempt" >> "$L/house.yaml"
        fi
      fi
      artifacts "$L/ladder.yaml"
      ;;
    *)
      sparkrun ${BENCH_VERBOSE:+-v} benchmark performance "$RECIPE" --profile benchmarking/concurrency-ladder.yaml \
        --skip-run --fresh -H "$HOSTS" --cluster WOPR --output "$L/ladder.yaml" > "$L/ladder.log" 2>&1 \
        || { echo "ladder failed for $NAME"; rc=2; }
      sparkrun ${BENCH_VERBOSE:+-v} benchmark run "$RECIPE" --profile benchmarking/standard-suite.yaml \
        --skip-run --fresh -H "$HOSTS" --cluster WOPR --output "$L/house.yaml" > "$L/house.log" 2>&1 \
        || { echo "suite failed for $NAME"; rc=3; }
      # A state-key match means the engine was never asked: sparkrun re-emits the previous cells and
# writes no per-cell artefact. Reporting that as a measurement is worse than reporting nothing --
# two boots on 2026-10-30 were spent this way (07:11 and 07:52), and their receipts carry the
# 06:04 numbers. `--fresh` above should make this unreachable; the check stays as the backstop.
for f in "$L/ladder.log" "$L/house.log"; do
  if grep -qi "Prior benchmark state for .* is COMPLETE" "$f" 2>/dev/null; then
    echo "REPLAYED, NOT MEASURED: $f re-emitted cached state -- cells in this receipt are stale"
    rc=7
  fi
done
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
# Harvest the engine's own log BEFORE the stop. `/tmp/sparkrun_serve.log` lives inside the
# container and dies with it, and it is the only place the acceptance / decode lines exist --
# without it a cell cannot be adjudicated against the lane's row, and the 2026-10-30 TP=2
# investigation burned three boots on receipts that could not answer "did the drafts land?".
# Best-effort on purpose: a failed copy must never fail an arm that measured fine.
# Every host the arm runs on, not just $NODE: a TP=2 arm's rank 1 lives on the second host,
# and the first version of this loop harvested rank 0 only -- losing exactly the log the
# investigation needed. A zero count is printed because a silent no-op reads as success.
harvested=0
for hn in $(echo "$HOSTS" | tr ',' ' '); do
  for c in $(ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$hn" \
               "docker ps --format '{{.Names}}' | grep -F '${TID}'" 2>/dev/null); do
    if ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$hn" \
         "docker cp '$c:/tmp/sparkrun_serve.log' /tmp/serve-$c.log" >/dev/null 2>&1 \
       && scp -q -o BatchMode=yes "red@$hn:/tmp/serve-$c.log" \
            "$L/serve-$(echo "$c" | sed 's/.*_//').log" 2>/dev/null; then
      harvested=$((harvested + 1))
      echo "harvested serve log from $c on $hn"
    fi
    # Node hygiene: $HOME and /tmp on every node are shared, so the staging copy goes.
    ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$hn" "rm -f /tmp/serve-$c.log" >/dev/null 2>&1
  done
done
echo "serve logs harvested: $harvested (expected one per running rank; 0 means the log was gone)"

for p in ${LOGFOLLOW[@]:-}; do kill "$p" 2>/dev/null; done
sparkrun stop "$TID" 2>&1 | tail -1
kill "$WD" 2>/dev/null
sleep 5
if [ -n "${N:-}" ] && ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$NODE" \
     "docker ps --format '{{.Names}}'" 2>/dev/null | grep -qx "$N"; then
  echo "container survived sparkrun stop; removing $N by name"
  ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$NODE" "docker rm -f $N" >/dev/null 2>&1
  sleep 3
fi
# `$N` above is the API rank only, so a TP=2 arm's rank 1 was never even looked at: on
# 2026-11-04 it was still running on the second host 39 s after the stop and 4 s after ARM
# DONE. Sweep every host in $HOSTS instead, matching the container-NAMING grammar anchored
# (`sparkrun_${TID}_solo`, `sparkrun_${TID}_node_*`) and only over names the task-id filter
# returned. The harvest loop above greps the bare id because it only READS -- that substring
# form is deliberately not reused for removal, where a hit could name another task whose id
# contains ours. No `docker ps -aq`, no xargs, no prune: a blanket remove on a shared node
# has already deleted a peer's containers once. Best-effort -- nothing to remove is the
# normal case, and a failed ssh must print and continue, never fail an arm that measured.
for hn in $(echo "$HOSTS" | tr ',' ' '); do
  if ! left=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$hn" \
      "docker ps -a --filter name=$TID --format '{{.Names}}'" 2>/dev/null); then
    echo "teardown: cannot list containers on $hn (ssh failed); continuing"
    continue
  fi
  for c in $left; do
    case "$c" in
      "sparkrun_${TID}_solo"|"sparkrun_${TID}_node_"*)
        echo "removing leftover $c on $hn"
        ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$hn" "docker rm -f $c" >/dev/null 2>&1 \
          || echo "could not remove $c on $hn; continuing" ;;
      *) echo "teardown: leaving $c on $hn (not this arm's container)" ;;
    esac
  done
done
for n in 30 35; do
  ssh -o ConnectTimeout=4 -o BatchMode=yes "red@10.0.4.$n" \
    "printf '%s ctns=%s vols=%s\n' \$(hostname) \$(docker ps -aq | wc -l) \$(docker volume ls -q | wc -l)"
done
# Gate on THIS arm's containers, never on a node-wide count: the other free node may be
# running a different arm, and counting its container as leftover failed a clean run
# (2026-10-29, bf16 control vs int8). Every host in $HOSTS, though: checking only $NODE/$N
# left a rank-1 survivor on the second host reported by nothing, so the arm ended rc=0
# (2026-11-04) and a monitor noticed an hour later.
for hn in $(echo "$HOSTS" | tr ',' ' '); do
  if ! left=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$hn" \
      "docker ps -a --filter name=$TID --format '{{.Names}}'" 2>/dev/null); then
    echo "teardown: cannot verify containers on $hn (ssh failed); continuing"
    continue
  fi
  for c in $left; do
    case "$c" in
      "sparkrun_${TID}_solo"|"sparkrun_${TID}_node_"*)
        echo "this arm's container is still running after teardown: $c on $hn"; rc=6 ;;
    esac
  done
done
echo "ARM DONE $NAME rc=$rc"
exit "$rc"