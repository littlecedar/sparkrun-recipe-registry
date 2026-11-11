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
#
# Readiness ceiling: ARM_READY_TIMEOUT seconds (default 2250 = the historical 150 polls
# x 15 s) drives the poll count together with ARM_POLL_SLEEP; a boot still loading at the
# ceiling exits 4 and the message names the effective ceiling. GLM-753B's measured TTR is
# 2538.9 s (~42 min, recipes/glm/README.md), so a campaign sets 3000 for that arm.
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
if [ -z "$NODE" ]; then
  echo "usage: run-arm.sh <recipe-path> [node-ip]  (or set ARM_NODE)"
  exit 1
fi
# ARM_TAG suffixes the receipt name (`-d4`, `-d8`): a sweep re-runs ONE recipe with different
# `-o` overrides, and without a tag every leg writes the same directory and rotates the previous
# leg to `.prev-<HHMMSS>` -- the numbers survive but the attribution does not.
NAME=$(basename "$RECIPE" .yaml)${ARM_TAG:+-$ARM_TAG}
# Receipt root: a campaign may own its measurements (`ARM_RECEIPTS_ROOT`), so the arm's numbers sit
# at `<root>/<arm>` beside the campaign's state instead of in the fleet-wide dated tree that
# `next-arms.py` and the drip scan. Default keeps the historical ~/benchmarks/tp12-<date>/<arm>.
if [ -n "${ARM_RECEIPTS_ROOT:-}" ]; then
  L="$ARM_RECEIPTS_ROOT/$NAME"
else
  L="$HOME/benchmarks/tp12-$(date +%Y%m%d)/$NAME"
fi
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

# ARM_OPTS carries `-o key=value` overrides for one-off knobs (a sweep leg, a different
# draft-token count). Without it every setting needs its own recipe file. A campaign row's `env`
# reaches this script as environment, so `ARM_OPTS` is the row's launch-override field: no
# stop/edit/boot ritual for one trial. Two documented forms:
#   * plain -- `-o parallel=10`, word-split exactly as the old code did;
#   * unit-separated ($'\x1f' between fields) -- `$'-o\x1fextra_args=--moe-runner-backend marlin'`,
#     fields taken whole so a value containing a space stays ONE argv entry.
# Unquoted word-splitting cannot express the second form: it hands `-o` the truncated value and
# leaves `marlin` a stray positional, which sparkrun's parser rejects (`--option/-o` is click's
# `multiple=True`, one value per occurrence; `cli/_common.py:1499-1504`). Measured 2026-11-08:
# the marlin `-o extra_args=--moe-runner-backend marlin` row would have split exactly that way.
ARM_OPTS_ARR=()
if [ -n "${ARM_OPTS:-}" ]; then
  if [[ "$ARM_OPTS" == *$'\x1f'* ]]; then
    IFS=$'\x1f' read -r -a ARM_OPTS_ARR <<< "$ARM_OPTS"
  else
    read -r -a ARM_OPTS_ARR <<< "$ARM_OPTS"
  fi
fi

# A c10 rung over fewer than ten slots measures the slot limit, not the model: the same arm read
# 135.97 t/s at `parallel: 8` and 176.30 at `parallel: 10` an hour later (2026-11-03). The ladder this
# script runs includes c10, so fail closed unless the recipe grants >= 10, ARM_OPTS raises it, or a
# caller deliberately waives it. Durable form of the rule: mad-science/METHODOLOGY.md section 3.
if [ -z "${ARM_ALLOW_FEW_SLOTS:-}" ]; then
  RECIPE_SLOTS=$(sed -n 's/^[[:space:]]*parallel:[[:space:]]*\([0-9][0-9]*\).*/\1/p' "$RECIPE" | head -1)
  OPT_SLOTS=
  for opt in ${ARM_OPTS_ARR[@]+"${ARM_OPTS_ARR[@]}"}; do
    case "$opt" in parallel=[0-9]*) OPT_SLOTS=${opt#parallel=} ;; esac
  done
  SLOTS=${OPT_SLOTS:-${RECIPE_SLOTS:-}}
  if [ -n "$SLOTS" ] && [ "$SLOTS" -lt 10 ]; then
    echo "ARM REFUSED $NAME: ladder includes c10 but the grant is parallel=$SLOTS."
    echo "  A c10 cell over $SLOTS slots measures the slot limit, not the model (135.97 vs 176.30 t/s,"
    echo "  2026-11-03). Pass ARM_OPTS=\"-o parallel=10\", raise the recipe default, or set"
    echo "  ARM_ALLOW_FEW_SLOTS=1 to record a deliberately slot-limited cell."
    exit 8
  fi
fi

# An inactive per-node daemon cannot create a container, and sparkrun reports that as a
# resource-distribution failure instead of a dead daemon: `[3/6] Distributing resources` then
# `[Errno 70] Communication error on send: /home/red/.cache/huggingface/token` (leases @3-@6,
# 2026-11-08), which reads as a token/permission error and is not one -- the token file was
# byte-identical on all six nodes. Asked here, before the exit capture is armed and before the
# launch, so a refused arm spends none of its evidence window and leaves no watcher behind.
# `sparkrun daemon status` is a state-file + pid read (`cli/_daemon.py:171-181`) that starts
# nothing and EXITS 0 either way, so the JSON field decides, never `$?`. The remote binary and
# `HOME` are resolved in the same non-interactive ssh form the probe uses, then pinned: a wrong
# `HOME` reports a running daemon as down (measured 2026-11-08: HOME=/tmp/wrong-home answered
# "running": false where HOME=/home/red answered true), which would refuse the fleet on this
# script's own environment.
# Three outcomes, not two: true proceeds; false refuses at 9 naming the host; anything
# unreadable (ssh failure, no binary, no `running` field) refuses at 10 and is never reported as
# "daemon not running". Each host's resolved binary, HOME, field and raw first line land in
# daemon-preflight.txt, so a refusal says which environment it probed.
# daemon-preflight: start
DP_FAIL=() DP_DOWN=()
: > "$L/daemon-preflight.txt"
for hn in $(echo "$HOSTS" | tr ',' ' '); do
  dp_out=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$hn" \
    'export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
     exe=$(command -v sparkrun 2>/dev/null) || { echo "EXE=-"; echo "HOME=$HOME"; echo "FIELD=no-binary"; exit 0; }
     echo "EXE=$exe"
     echo "HOME=$HOME"
     out=$(HOME="$HOME" "$exe" daemon status 2>&1) || { echo "FIELD=status-failed"; echo "RAW=$(printf "%s" "$out" | head -1 | cut -c1-120)"; exit 0; }
     echo "FIELD=$(printf "%s" "$out" | sed -n "s/.*\"running\": *\(true\|false\).*/\1/p" | head -1)"
     echo "RAW=$(printf "%s" "$out" | head -1 | cut -c1-120)"' 2>/dev/null) || dp_out=
  dp_exe=$(printf '%s\n' "$dp_out" | sed -n 's/^EXE=//p' | head -1)
  dp_home=$(printf '%s\n' "$dp_out" | sed -n 's/^HOME=//p' | head -1)
  dp_field=$(printf '%s\n' "$dp_out" | sed -n 's/^FIELD=//p' | head -1)
  dp_raw=$(printf '%s\n' "$dp_out" | sed -n 's/^RAW=//p' | head -1)
  : "${dp_field:=unreadable}"
  printf '%s,%s,%s,%s,%s\n' "$hn" "${dp_exe:--}" "${dp_home:--}" "$dp_field" "${dp_raw:--}" \
    >> "$L/daemon-preflight.txt"
  case "$dp_field" in
    true) ;;
    false) DP_DOWN+=("$hn") ;;
    *) DP_FAIL+=("$hn ($dp_field)") ;;
  esac
done
if [ ${#DP_FAIL[@]} -gt 0 ]; then
  echo "ARM REFUSED $NAME: the daemon preflight could not be read on ${DP_FAIL[*]};"
  echo "  an unreadable probe is neither a dead daemon nor a healthy one, so nothing is launched."
  echo "  Probe evidence: $L/daemon-preflight.txt"
  exit 10
fi
if [ ${#DP_DOWN[@]} -gt 0 ]; then
  echo "ARM REFUSED $NAME: no running sparkrun daemon on ${DP_DOWN[*]}; the launch would die in"
  echo "  resource distribution as [Errno 70] Communication error on send on the HF token path,"
  echo "  a token/permission error it is not. Start it on each:"
  for hn in "${DP_DOWN[@]}"; do echo "    ssh red@$hn 'sparkrun daemon start'"; done
  echo "  verify with: sparkrun daemon status -> \"running\": true. Evidence: $L/daemon-preflight.txt"
  exit 9
fi
# daemon-preflight: end

# The shared cache presents an empty mount, not an error: after a slow pool mount a container can
# see an empty `/cache`, a boot can pass readiness and hand the engine a model that is not there,
# and a launch can freeze in planning while a probe returns zero snapshots (AGENTS.md, shared-cache
# section; measured 2026-11-08 with `beegfs-storage` down).
# But a client-side `df`/`ls` is NOT a verdict on the pool: the BeeGFS client only retries within
# `connCommRetrySecs=600`, so an `ECOMM` seconds after mgmtd returns is normal on a healthy pool
# and calling it dead is the instrument talking (tools/README.md:217-226). Authority is
# server-side -- `systemctl is-active` on the mgmtd, meta and storage units plus the listening
# ports (`8008` mgmtd, `8003` storage) -- because `beegfs-ctl` and `beegfs-check-servers` are not
# installed on this fleet. The snapshot `ls` is a bounded follow-up inside a reconnect window,
# never a one-shot refusal.
# Three pool verdicts, then the model verdict:
#   pool-unhealthy      an installed unit is not active, or mgmtd/storage is not listening: exit 11
#   pool-reconnecting   the server side is healthy and the client still cannot read the snapshot
#                       inside `ARM_POOL_WAIT` (default 60 s): exit 13, never called dead
#   pool-ready          a snapshot `ls` succeeded
# and the model path `<hf_cache>/hub/models--<org>--<name>/snapshots/<revision>`
# (`models/acquisition.py:49`, `models/_cache_agent.py:68`; a GGUF spec drops its `:quant`,
# `models/download.py:model_cache_path`). `<hf_cache>` is the cluster profile's
# `distribution.hf_cache` (this script launches with `--cluster WOPR`), the host dir bind-mounted
# at the container's `/cache/huggingface` (`runtimes/base.py:787`). Exit 12 is the model verdict:
# the pool answered and the snapshot is absent or empty.
# The probe is HOST-SIDE by construction: no container exists yet, so a host-side `ls` passing
# does not prove the container's `/cache` is populated, and both evidence files say `view=host`.
# model-path: start
MP_MODEL=$(sed -n 's/^model:[[:space:]]*//p' "$RECIPE" | head -1)
MP_MODEL=${MP_MODEL%%:*}   # a GGUF spec is repo:quant; the snapshot lives under the repo
MP_REV=$(sed -n 's/^model_revision:[[:space:]]*//p' "$RECIPE" | head -1)
MP_CLUSTER="$HOME/.config/sparkrun/clusters/WOPR.yaml"
MP_DRIVER=$(hostname 2>/dev/null || echo unknown)
MP_HUB=$(sed -n 's/^[[:space:]]*hf_cache:[[:space:]]*//p' "$MP_CLUSTER" 2>/dev/null | head -1)
MP_HUB=${MP_HUB%/}
MP_PATH=
if [ -n "$MP_HUB" ] && [ -n "$MP_MODEL" ]; then
  MP_PATH="$MP_HUB/hub/models--${MP_MODEL%%/*}--${MP_MODEL#*/}/snapshots${MP_REV:+/$MP_REV}"
fi
POOL_WAIT=${ARM_POOL_WAIT:-60}
POOL_POLL=${ARM_POOL_POLL:-10}
: > "$L/pool-preflight.txt"
: > "$L/model-preflight.txt"
printf '# hub=%s model=%s revision=%s path=%s wait=%ss driver=%s view=host\n' \
  "${MP_HUB:--}" "${MP_MODEL:--}" "${MP_REV:--}" "${MP_PATH:--}" "$POOL_WAIT" "$MP_DRIVER" \
  > "$L/model-preflight.txt"
printf '# wait=%ss view=host\n' "$POOL_WAIT" > "$L/pool-preflight.txt"
# A cluster-less host cannot name the cache root, and reporting that as "the model path could not
# be resolved" sends the reader hunting staging instead of a missing definition. A launch always
# names `--cluster WOPR` and never falls back to an anonymous cluster -- that would fan the weights
# out per node and measure a different arm -- so this host is simply not a driver for this arm, and
# the fix is to run it where the definition lives (the head). Its own exit code, so a workstation
# refusal can never be read as a model fault.
if [ ! -f "$MP_CLUSTER" ]; then
  printf 'cluster=absent driver=%s view=host\n' "$MP_DRIVER" >> "$L/model-preflight.txt"
  echo "ARM REFUSED $NAME: not a launch host -- no WOPR cluster definition here ($MP_CLUSTER)."
  echo "  \`sparkrun cluster list\` shows no cluster on this host, and the WOPR profile (its hf_cache"
  echo "  and skip_fan_out) lives on the head. Run this arm from the head: the anonymous-cluster"
  echo "  path would fan the weights out per node and measure a different arm."
  echo "  Driver host: $MP_DRIVER"
  echo "  Probe evidence: $L/model-preflight.txt"
  exit 14
fi
if [ -z "$MP_PATH" ]; then
  echo "ARM REFUSED $NAME: the model path could not be resolved (hub=${MP_HUB:--}," \
       "model=${MP_MODEL:--}); a boot would hand the engine whatever an empty cache holds."
  echo "  Probe evidence: $L/model-preflight.txt"
  exit 11
fi
MP_BAD=() MP_CONN=() MP_MISS=()
for hn in $(echo "$HOSTS" | tr ',' ' '); do
  mp_out=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$hn" \
             "MP='$MP_PATH' WAIT='$POOL_WAIT' POLL='$POOL_POLL' sh -s" 2>/dev/null <<'PROBE'
units= fault=
# The mount names its server (`sysMgmtdHost`); the host does not. So the mgmtd/meta requirement
# is derived by asking whether this host owns that address -- moving the mgmtd to another node
# re-hosts the requirement instead of leaving the gate green everywhere. `beegfs-meta=failed`
# with no metadata directory is the standing state on the five client hosts (since 2026-11-05),
# and it is not a fault there.
mgmtd=$(mount 2>/dev/null | sed -n 's/.*sysMgmtdHost=\([0-9.]*\).*/\1/p' | head -1)
role=client
if [ -n "$mgmtd" ] && ip -4 -o addr show 2>/dev/null | grep -qw "$mgmtd"; then role=mgmtd; fi
for u in beegfs-mgmtd beegfs-meta beegfs-storage; do
  s=$(systemctl is-active "$u" 2>&1 | head -1)
  case "$s" in
    active) units="$units $u=active"; continue ;;
    *"could not be found"*|*"not-found"*|*"No such file"*) units="$units $u=absent"; continue ;;
  esac
  case "$u" in
    beegfs-storage) units="$units $u=$s"; fault="$fault,unit-$u-$s" ;;
    *) if [ "$role" = mgmtd ]; then units="$units $u=$s"; fault="$fault,unit-$u-$s"
       else units="$units $u=$s-no-role"; fi ;;
  esac
done
mport=n/a
if [ -n "$mgmtd" ]; then
  if timeout 4 python3 -c 'import socket,sys
socket.create_connection((sys.argv[1], int(sys.argv[2])), 2).close()' "$mgmtd" 8008 2>/dev/null; then
    mport=open
  else
    mport=closed; fault="$fault,mgmtd-port"
  fi
fi
sport=n/a
case "$units" in
  *beegfs-storage=active*)
    if timeout 4 python3 -c 'import socket
socket.create_connection(("127.0.0.1", 8003), 2).close()' 2>/dev/null; then
      sport=open
    else
      sport=closed; fault="$fault,storage-port"
    fi ;;
esac
echo "ROLE=$role"
echo "UNITS=$units"
echo "PORTS=mgmtd=$mport storage=$sport"
if [ -n "$fault" ]; then echo "POOL=pool-unhealthy"; echo "DETAIL=$fault"; exit 0; fi
deadline=$(( $(date +%s) + WAIT ))
while :; do
  out=$(timeout 10 ls -A "$MP" 2>&1); rc=$?
  if [ "$rc" -eq 0 ]; then echo "POOL=entries:$(printf '%s\n' "$out" | grep -c .)"; exit 0; fi
  case "$out" in
    *"No such file or directory"*) echo "POOL=absent"; exit 0 ;;
  esac
  if [ "$(date +%s)" -ge "$deadline" ]; then
    echo "POOL=pool-reconnecting"; echo "DETAIL=$(printf '%s' "$out" | head -1 | cut -c1-100)"
    exit 0
  fi
  sleep "$POLL"
done
PROBE
)
  mp_role=$(printf '%s\n' "$mp_out" | sed -n 's/^ROLE=//p' | head -1)
  mp_units=$(printf '%s\n' "$mp_out" | sed -n 's/^UNITS=//p' | head -1)
  mp_ports=$(printf '%s\n' "$mp_out" | sed -n 's/^PORTS=//p' | head -1)
  mp_detail=$(printf '%s\n' "$mp_out" | sed -n 's/^DETAIL=//p' | head -1)
  mp_kind=$(printf '%s\n' "$mp_out" | sed -n 's/^POOL=//p' | head -1)
  case "${mp_kind%%:*}" in
    entries) mp_status=pool-ready ;;
    *) mp_status=${mp_kind%%:*} ;;
  esac
  printf '%s role=%s units=%s ports=%s status=%s detail=%s view=host\n' "$hn" \
    "${mp_role:-unknown}" "${mp_units:-unknown}" "${mp_ports:-unknown}" "${mp_status:-unknown}" \
    "${mp_detail:--}" >> "$L/pool-preflight.txt"
  case "$mp_kind" in
    entries:0) printf '%s status=empty path=%s entries=0 view=host\n' "$hn" "$MP_PATH" \
                 >> "$L/model-preflight.txt"; MP_MISS+=("$hn (entries=0)") ;;
    entries:*) printf '%s status=present path=%s entries=%s view=host\n' \
                 "$hn" "$MP_PATH" "${mp_kind#entries:}" >> "$L/model-preflight.txt" ;;
    absent) printf '%s status=absent path=%s entries=- view=host\n' "$hn" "$MP_PATH" \
              >> "$L/model-preflight.txt"; MP_MISS+=("$hn (absent)") ;;
    pool-reconnecting) printf '%s status=unread path=%s entries=- detail=%s view=host\n' \
                         "$hn" "$MP_PATH" "${mp_detail:--}" >> "$L/model-preflight.txt"
                       MP_CONN+=("$hn (${mp_detail:-client ECOMM})") ;;
    pool-unhealthy) printf '%s status=pool-unhealthy path=%s entries=- detail=%s view=host\n' \
                      "$hn" "$MP_PATH" "${mp_detail:--}" >> "$L/model-preflight.txt"
                    MP_BAD+=("$hn (${mp_detail:--server-side fault})") ;;
    *) printf '%s status=pool-unhealthy path=%s entries=- detail=probe-unreadable view=host\n' \
         "$hn" "$MP_PATH" >> "$L/model-preflight.txt"; MP_BAD+=("$hn (probe unreadable)") ;;
  esac
done
if [ ${#MP_BAD[@]} -gt 0 ]; then
  echo "ARM REFUSED $NAME: the shared model cache is unhealthy on ${MP_BAD[*]};"
  echo "  the server side says so (unit state / listening port), so this is the pool and not the"
  echo "  recipe. Path: $MP_PATH"
  echo "  Probe evidence: $L/pool-preflight.txt, $L/model-preflight.txt"
  exit 11
fi
if [ ${#MP_CONN[@]} -gt 0 ]; then
  echo "ARM REFUSED $NAME: the pool is up and this host has not reconnected on ${MP_CONN[*]};"
  echo "  the snapshot read still failed inside ${POOL_WAIT}s (the client retries for up to 600 s:"
  echo "  tools/README.md:217-226). Re-run with ARM_POOL_WAIT=<seconds> to wait longer -- this is"
  echo "  neither a missing model nor a dead pool. Path: $MP_PATH"
  echo "  Probe evidence: $L/pool-preflight.txt, $L/model-preflight.txt"
  exit 13
fi
if [ ${#MP_MISS[@]} -gt 0 ]; then
  echo "ARM REFUSED $NAME: the model snapshot is missing or empty on ${MP_MISS[*]};"
  echo "  the pool answered, so the model was never staged at this revision."
  echo "  Path: $MP_PATH (revision=${MP_REV:--})"
  echo "  Probe evidence: $L/model-preflight.txt"
  exit 12
fi
# model-path: end

launch_arm() {
  sparkrun run "$RECIPE" -H "$HOSTS" --cluster WOPR "${ARM_OPTS_ARR[@]}" > "$L/launch.log" 2>&1 &
  LAUNCH=$!
}
# The effective overrides verbatim: `-o ...` is a CLI argument, not container env, so
# `docker inspect` cannot recover it and the receipt would not say which knob produced its
# numbers (2026-11-08: a marlin `--moe-runner-backend` trial left no such record). `(none)` when
# unset: an absent file is indistinguishable from evidence that was never written.
printf '%s\n' "${ARM_OPTS:-(none)}" > "$L/arm_opts.txt"
# An engine that dies during init takes its own stdout with it: sparkrun launches containers
# `--rm` (auto_remove defaults true, orchestration/executors/docker.py:555), so the daemon
# deletes one ~26 ms after its `die` event -- measured on the fleet head 2026-11-08, where a
# `docker logs` started on that event already answered "No such container". The marlin trial
# lost both lines it had printed exactly that way. Arm the capture on every host BEFORE the
# launch: it attaches `docker logs -f` at `create` (docker replays the log from the start) and
# takes the exit code off the `die` event, so the text is on the node's disk before the
# container can be removed. Scoped by the recipe label -- `sparkrun.recipe` is
# `Recipe.qualified_name` (`orchestration/executors/_base.py:942,1005-1006`), the recipe path as
# passed (`core/recipe.py:1589-1597,1924`), so the filter is exactly $RECIPE and a peer's boot on
# a shared node is not captured.
CAPTURE_DIR="/tmp/sparkrun-exitcap.$$"
CAPTURE=()
for hn in $(echo "$HOSTS" | tr ',' ' '); do
  ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$hn" \
    "bash -s -- '$CAPTURE_DIR' '$(( ${ARM_READY_TIMEOUT:-2250} + 900 ))' 'sparkrun.recipe=$RECIPE'" \
    < tools/engine-exit-capture.sh &
  CAPTURE+=("$!")
done
# The watcher writes <dir>/pid before it starts `docker events`, and docker answers no
# subscription check, so give each host this settle before a container can exist.
sleep 1
# The watcher is its own docker client and does not end with the boot: kill it by the pid it
# wrote, and its EXIT trap takes `docker events` with it. ConnectTimeout bounds this when a
# node is unreachable, so it cannot hang a teardown.
stop_capture() {
  for hn in $(echo "$HOSTS" | tr ',' ' '); do
    ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$hn" \
      "kill \$(cat '$CAPTURE_DIR/pid' 2>/dev/null) 2>/dev/null" 2>/dev/null
  done
  for p in ${CAPTURE[@]+"${CAPTURE[@]}"}; do kill "$p" 2>/dev/null; done
}
# oom-watchdog: start
# earlyoom kills with SIGTERM, so the engine exits 143 (128+15) and prints no traceback: a dead
# boot reads clean-but-unexplained and the next fit verdict blames the engine. 137 is SIGKILL (a
# cgroup OOM or docker's own kill). The journal is the only place that names the killer, so this
# reads it per lease host over the arm's own window and records the matching line verbatim in
# `oom-watchdog.txt`. `house.yaml` gets one field, `oom_watchdog`, whose four values are the
# contract: `clean` needs a readable journal, an exit outside {137,143} and a result artifact;
# `earlyoom-terminated` needs a journal line, never suspicion; `cgroup-oom` needs the docker
# `oom` event the capture recorded for this arm's container AND no result artifact -- a
# `--memory` breach kills the serve whose PID 1 is `sleep infinity`, so the container survives
# with exit 0 and the event is the only evidence (see tools/engine-exit-capture.sh). Anything
# else is `unknown`. A cgroup kill is never `clean`, and an `oom` event on an arm that did
# produce a result is a capped child, not an arm death: the fact goes in `cgroup_oom=` and the
# state stays what the artifact and journal say.
oom_watchdog_check() {
  [ -n "${OOM_SINCE:-}" ] || return 0        # never launched: there is no window to read
  [ -z "${OOM_DONE:-}" ] || return 0         # INT then TERM must not append the field twice
  OOM_DONE=1
  local hn j jrc jbody hit jstate line= unread=0 exit_codes= artifact= state= cgroup_oom=
  exit_codes=$( { sed -n 's/^# capture: die exit=\([0-9][0-9]*\)$/\1/p' "$L"/docker-*.log 2>/dev/null
                  sed -n 's/.*exit status \([0-9][0-9]*\).*/\1/p' "$L/launch.log" 2>/dev/null
                } | sort -u | tr '\n' ',' | sed 's/,$//' )
  # Container names whose cgroup emitted an `oom` event, from the capture merged at harvest.
  cgroup_oom=$(sed -n 's/^# capture: oom [^ ]* \(.*\)$/\1/p' "$L"/docker-*.log 2>/dev/null \
               | sort -u | tr '\n' ',' | sed 's/,$//')
  for f in "$L/house.yaml" "$L/ladder.yaml" "$L/ladder.json" "$L/teb-decision.log"; do
    [ -s "$f" ] && { artifact=yes; break; }
  done
  : > "$L/oom-watchdog.txt.hosts"
  for hn in $(echo "$HOSTS" | tr ',' ' '); do
    j=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$hn" \
          "journalctl --since '@$OOM_SINCE' -u earlyoom -o cat --no-pager 2>&1; echo \"__rc=\$?\"" \
          2>/dev/null)
    jrc=$(printf '%s\n' "$j" | sed -n 's/^__rc=//p' | head -1)
    jbody=$(printf '%s\n' "$j" | sed '/^__rc=/d')
    hit= jstate=unreadable
    if [ "$jrc" = 0 ]; then
      jstate=ok
      hit=$(printf '%s\n' "$jbody" | grep -i -m1 'sending SIGTERM\|low memory' || true)
    else
      unread=$((unread + 1))
    fi
    [ -n "$hit" ] && line=$hit
    printf '%s exit=%s journal=%s line=%s view=host\n' "$hn" "${exit_codes:--}" "$jstate" \
      "${hit:--}" >> "$L/oom-watchdog.txt.hosts"
  done
  if [ -n "$line" ]; then
    state=earlyoom-terminated
  elif [ -n "$cgroup_oom" ] && [ -z "$artifact" ] && [ "$unread" -eq 0 ]; then
    # The container was capped and the arm produced nothing: the serve died to SIGKILL, which
    # with PID 1 = `sleep infinity` leaves no exit code at all. Evidence is the container name.
    # An unreadable journal outranks it: we could not rule out earlyoom naming a victim too.
    state=cgroup-oom
    line="oom $cgroup_oom"
  elif [ "$unread" -gt 0 ] || [ -z "$artifact" ] || [ -z "$exit_codes" ]; then
    state=unknown
  else
    case ",$exit_codes," in
      *,137,*|*,143,*) state=unknown ;;   # a kill with no journal line is not a clean death
      *) state=clean ;;
    esac
  fi
  printf '# oom_watchdog=%s since=@%s hosts=%s exit=%s unread=%s artifact=%s cgroup_oom=%s evidence=%s view=host\n' \
    "$state" "$OOM_SINCE" "$HOSTS" "${exit_codes:--}" "$unread" "${artifact:-no}" "${cgroup_oom:--}" "${line:--}" \
    > "$L/oom-watchdog.txt"
  cat "$L/oom-watchdog.txt.hosts" >> "$L/oom-watchdog.txt"
  rm -f "$L/oom-watchdog.txt.hosts"
  if [ -e "$L/house.yaml" ]; then
    printf 'oom_watchdog: %s\n' "$state" >> "$L/house.yaml"
  fi
  echo "oom-watchdog: $state (exit=${exit_codes:--} unread=$unread artifact=${artifact:-no})"
}
# oom-watchdog: end
# The OOM window opens at the launch: a boot killed by earlyoom leaves its only trace in the
# journal, timed from here. The check itself runs in the EXIT trap, so a dead boot (exit 4) is
# attributed the same way a finished arm is.
OOM_SINCE=$(date +%s)
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

# The stop path is installed BEFORE the appearance loop: a launch abandoned there used to
# outlive the executor and leave unowned containers (measured 2026-11-08: a pair boot was
# called failed while its serve went on to answer). TID is empty until a container resolves
# and `$LAUNCH` is the launcher itself, so every reference is guarded.
trap 'oom_watchdog_check; stop_capture; [ -n "${TID:-}" ] && sparkrun stop "$TID" >/dev/null 2>&1; [ -n "${GUARD_PID:-}" ] && kill "$GUARD_PID" 2>/dev/null; declare -F stop_samplers >/dev/null 2>&1 && stop_samplers; [ -n "${LAUNCH:-}" ] && kill "$LAUNCH" 2>/dev/null; [ -n "${WD:-}" ] && kill "$WD" 2>/dev/null; [ -n "${EXTRA_PID:-}" ] && kill "$EXTRA_PID" 2>/dev/null; exit' EXIT INT TERM

# How long a container may take to appear follows the LAUNCHER's progress, not a fixed clock.
# A 129.6 GB pair distribution took 340 s to produce a container, and the old 300 s window
# called that a failure while the launch went on to serve (measured 2026-11-08,
# `zz-ripple-65b-preview-bf16-tp2-vllm` attempt 3: containers at 10:32:47Z, `/v1/models` 200).
# 900 s is the floor for a multi-rank body; a campaign raises it with
# `ARM_CONTAINER_APPEAR_TIMEOUT`. `ARM_APPEAR_POLL` exists so a guard can drive this loop.
APPEAR_TIMEOUT=${ARM_CONTAINER_APPEAR_TIMEOUT:-900}
APPEAR_POLL=${ARM_APPEAR_POLL:-5}
appear_start=$SECONDS
while :; do
  # Both container shapes: `_solo` for TP=1, `_node_<rank>` for a multi-rank launch. Matching only
  # `_solo` made every TP=2 launch print ARM FAIL 301 s in while its containers booted happily
  # underneath (measured 2026-10-30, first pair run) -- same class as the boot-watchdog `_solo` fix,
  # opposite direction.
  N=$(on_node "docker ps --format '{{.Names}}' | grep -m1 -E '_solo|_node_0'" 2>/dev/null | tr -d '\r' || true)
  [ -n "$N" ] && break
  waited=$((SECONDS - appear_start))
  # A refused launch (a stale resource claim, a missing recipe, a placement failure) exits at
  # once. This is the only prompt verdict: the launcher being gone AND no container existing.
  if ! kill -0 "$LAUNCH" 2>/dev/null; then
    echo "ARM FAIL $NAME: launcher exited with no container after ${waited}s" \
         "(ceiling ${APPEAR_TIMEOUT}s). Last lines:"
    tail -5 "$L/launch.log"
    # This is exactly the marlin shape: an engine killed during init leaves no container, so
    # its 137/143 is attributable only from here.
    oom_watchdog_check
    exit 5
  fi
  # At the ceiling the launcher is still alive, so it is killed first and the failure is then
  # stated on the same two conditions: gone AND no container.
  if [ "$waited" -ge "$APPEAR_TIMEOUT" ]; then
    echo "ARM FAIL $NAME: no container appeared after ${waited}s (ceiling ${APPEAR_TIMEOUT}s," \
         "ARM_CONTAINER_APPEAR_TIMEOUT); launcher was still running, killing it"
    tail -5 "$L/launch.log"
    kill "$LAUNCH" 2>/dev/null
    oom_watchdog_check
    exit 1
  fi
  sleep "$APPEAR_POLL"
done
TID=${N#sparkrun_}; TID=${TID%_node_*}; TID=${TID%_solo}
# The receipt cell a pre-ready client waits on: the task id does not exist until the launch
# resolves, and a client armed before it must not invent one.
printf '%s\n' "$TID" > "$L/task-id.txt"
echo "arm=$NAME container=$N task=$TID port=$PORT"

# guard-arm: start
# The window's memory guard and its per-rank trigger writers, armed only for an arm that declared
# a window (the campaign exports the row's `window` as ARM_WINDOW). This is the executor half of
# the stop rule ratified 2026-11-11: a guard, not a measured sampler, stops a risky boot. It is
# armed here -- after the task id resolves, before the first readiness sample -- because a boot
# that dies in load never reaches a readiness verdict and no readiness-cell instrument sees it.
GUARD_PID=""
GUARD_DIR=""
GUARD_CELL="$L/guard-armed.txt"
GUARD_SAMPLERS_ARMED=0

guard_fail() {
  { printf 'state=not-armed\nreason=%s\ntid=%s\nscript=%s\n' \
      "$1" "$TID" "$GUARD_DIR/mem-guard.sh"; } > "$GUARD_CELL"
  # Stop by the literal id resolved above: the exit trap's stop is not the only stop, and a
  # stale guard must never keep triggering against a task that is already gone.
  sparkrun stop "$TID" >/dev/null 2>&1 || true
  [ -n "$GUARD_PID" ] && kill "$GUARD_PID" 2>/dev/null
  [ "$GUARD_SAMPLERS_ARMED" = 1 ] && stop_samplers
  echo "ARM FAIL $NAME: window guard not armed ($1); task $TID stopped, no readiness or benchmark step"
  exit 15
}

stop_samplers() {
  # The sampler loops forever by design; leaving one behind leaks exactly as the guard did.
  # Scoped to this window's path so a peer arm on a shared rank keeps its own sampler.
  [ -n "${GUARD_DIR:-}" ] || return 0
  for hn in $(echo "$HOSTS" | tr ',' ' '); do
    ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$hn" \
      "pkill -f '$GUARD_DIR/mem-sampler.sh' 2>/dev/null; rm -f '$GUARD_DIR/sampler.pid'" \
      >/dev/null 2>&1 || true
  done
}

arm_guard() {
  [ -n "${ARM_WINDOW:-}" ] || return 0
  GUARD_DIR="$HOME/benchmarks/$ARM_WINDOW"
  local script="$GUARD_DIR/mem-guard.sh" ranks sampler_out samplers="" guard_line="" waited=0
  if [ ! -x "$script" ]; then
    guard_fail "script missing or not executable: $script"
  fi
  ranks=$(echo "$HOSTS" | tr ',' ' ')
  # The guard runs on this host (the head), its own session so a later stop cannot reap it, and
  # reads every rank's trigger over ssh. TP4_DIR/TP4_RANKS are the names its own script requires.
  setsid nohup env TP4_DIR="$GUARD_DIR" TP4_RANKS="$ranks" \
    bash "$script" "$TID" > "$L/mem-guard.out" 2>&1 < /dev/null &
  GUARD_PID=$!
  printf '%s %s\n' "$GUARD_PID" "$(date -u +%FT%TZ)" > "$L/mem-guard.pid"
  # The guard's own startup line is the proof it is running the task it was given; a live pid
  # alone can be a shell that died right after fork. Bounded, then refuse rather than proceed.
  while [ "$waited" -lt "${ARM_GUARD_WAIT:-10}" ]; do
    if ! kill -0 "$GUARD_PID" 2>/dev/null; then
      guard_fail "guard $GUARD_PID died before its start line"
    fi
    guard_line=$(grep -h "guard start tid=$TID " "$GUARD_DIR/mem-guard.log" 2>/dev/null | tail -1 || true)
    [ -n "$guard_line" ] && break
    sleep 1
    waited=$((waited + 1))
  done
  if [ -z "$guard_line" ]; then
    guard_fail "no guard start line for tid=$TID in $GUARD_DIR/mem-guard.log after ${ARM_GUARD_WAIT:-10}s"
  fi
  # Per-rank trigger writers, the window's own sampler with the arguments its launcher uses:
  # TP4_DIR/TP4_TID/TP4_RANK/TP4_FLOOR_KB/TP4_SLEEP. The pkill is scoped to this window's path.
  for hn in $ranks; do
    sampler_out=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$hn" \
      "bash -s -- '$TID' '$hn' '$GUARD_DIR' '${TP4_FLOOR_KB:-6291456}' '${TP4_SLEEP:-1}'" <<'EOS' 2>&1
TID=$1; IP=$2; D=$3; FLOOR=$4; SLOW=$5
pkill -f "$D/mem-sampler.sh" 2>/dev/null
sleep 1
setsid nohup env TP4_DIR="$D" TP4_TID="$TID" TP4_RANK="$IP" TP4_FLOOR_KB="$FLOOR" TP4_SLEEP="$SLOW" \
  bash "$D/mem-sampler.sh" > "$D/sampler-$IP.log" 2>&1 < /dev/null &
echo $! > "$D/sampler.pid"
sleep 2
echo "$IP pid=$(cat "$D/sampler.pid" 2>/dev/null) rows=$(wc -l < "$D/mem-series-$IP.csv" 2>/dev/null) last_avail_kB=$(awk -F, 'END{print $4}' "$D/mem-series-$IP.csv" 2>/dev/null)"
EOS
)
    case "$sampler_out" in
      *"pid="*) GUARD_SAMPLERS_ARMED=1; samplers="${samplers:+$samplers }$sampler_out" ;;
      *) guard_fail "sampler did not start on $hn: ${sampler_out:-(no output)}" ;;
    esac
  done
  if ! kill -0 "$GUARD_PID" 2>/dev/null; then
    guard_fail "guard $GUARD_PID died before the first readiness sample"
  fi
  { printf 'state=armed\ntid=%s\npid=%s\nstart_utc=%s\nscript=%s\nranks=%s\nsamplers=%s\nguard_line=%s\n' \
      "$TID" "$GUARD_PID" "$(date -u +%FT%TZ)" "$script" "$ranks" "$samplers" "$guard_line"; } \
    > "$GUARD_CELL"
  echo "guard=armed pid=$GUARD_PID script=$script ranks=$ranks"
}

stop_guard() {
  [ -n "${GUARD_PID:-}" ] && kill "$GUARD_PID" 2>/dev/null
  stop_samplers
}
arm_guard
# guard-arm: end

# The stop path is already installed, above the appearance loop.

# The image cell belongs to every receipt, not to the arms that happen to carry a quality client:
# the concurrency rows had to smuggle an image-id gate into ARM_EXTRA_CLIENT because this block
# used to live inside the hook. The value is the container's own config sha
# (`docker inspect -f '{{.Image}}'`), never a registry manifest digest this host cannot know.
# A miss is a visible failure, not an "unknown" placeholder: a receipt that looks complete while
# naming no image cannot be audited, and three reads cover one ssh hiccup.
IMAGE_ID=""
for _ in $(seq 1 3); do
  IMAGE_ID=$(on_node "docker inspect -f '{{.Image}}' '$N'" 2>/dev/null | tr -d '\r' || true)
  [ -n "$IMAGE_ID" ] && break
  sleep 2
done
if [ -z "$IMAGE_ID" ]; then
  echo "ARM FAIL $NAME: no image id from container $N on $NODE; the receipt cannot name what ran"
  exit 5
fi
printf '%s\n' "$IMAGE_ID" > "$L/image.txt"
export ARM_IMAGE_ID="$IMAGE_ID"
echo "image=$IMAGE_ID"

# A pre-ready extra client (`ARM_EXTRA_CLIENT_AT=pre-ready`) samples while the boot loads. The
# post-ready hook below cannot see a boot that dies during load, and a load-only probe
# (Kimi `--load-format dummy`) dies exactly there: measured 2026-11-10, three attempts held four
# ranks ~5 min each and every receipt lacked the floor only the load could show. Armed once the
# container and image resolve (both receipt cells the client waits on), so the exit trap reaps it
# and an early refusal leaves no sampler behind.
EXTRA_PID=""
if [ -n "${ARM_EXTRA_CLIENT:-}" ] && [ "${ARM_EXTRA_CLIENT_AT:-post-ready}" = pre-ready ]; then
  export ARM_HOSTS="$HOSTS" ARM_RECIPE="$RECIPE" ARM_RECEIPT_DIR="$L"
  echo "extra client (pre-ready): $ARM_EXTRA_CLIENT (timeout ${ARM_EXTRA_TIMEOUT:-1800}s)"
  eval "timeout -k 30 ${ARM_EXTRA_TIMEOUT:-1800} $ARM_EXTRA_CLIENT" \
    > "$L/extra-client.log" 2>&1 &
  EXTRA_PID=$!
  # The post-ready hook must not run the same command a second time. Clearing the variable is
  # what skips it without editing the guard the existing tests extract; the teardown line keeps
  # the saved copy so the receipt still names the command.
  ARM_EXTRA_CLIENT_ARMED=$ARM_EXTRA_CLIENT
  unset ARM_EXTRA_CLIENT
fi

# The per-rank stdout the follower used to stream is owned by the exit capture armed before the
# launch: it attaches at `create` (the follower waited for `docker ps` to see the container, which
# a boot that dies in ~1 s never allows) and its text survives the `--rm` removal. `/tmp/sparkrun_serve.log`
# is still written by the engine after the hooks, so a boot that dies in a pre_exec hook leaves no
# serve log at all (2026-11-03 cyankiwi, 2026-11-04 labquant trio) -- the harvest below is the copy
# of that file, and the capture is the only copy of the engine's own stdout.

# Every rank in the lease, not just the API rank: on a TP=4 rendezvous rank 0 can sit quiet
# while ranks 1-3 stream shards, and a rank-0-only watchdog stops that boot as stalled. Ranks
# are numbered by their position in $HOSTS, which is the order sparkrun launches them in; rank 0
# stays --node/--container (it owns the endpoint and the death evidence).
RANK_ARGS=()
_rank=0
for hn in $(echo "$HOSTS" | tr ',' ' '); do
  if [ "$_rank" -gt 0 ]; then
    RANK_ARGS+=(--rank "$hn:sparkrun_${TID}_node_$_rank")
  fi
  _rank=$((_rank + 1))
done

python3 tools/boot-watchdog.py --endpoint "http://$NODE:$PORT" --task-id "$TID" \
  --node "$NODE" --container "$N" --interval 10 \
  "${RANK_ARGS[@]}" --log "$L/watchdog.log" &
WD=$!

# Only so the readiness-loop guard can drive this loop at 0 s; 15 s in a real arm.
POLL_SLEEP=${ARM_POLL_SLEEP:-15}
# Readiness ceiling, in seconds. The historical literal was 150 polls x 15 s = 2250 s, which
# rejected a legitimately loading arm: GLM-753B's own measured TTR is 2538.9 s (42 min,
# recipes/glm/README.md), so a campaign recorded rc=4 "never ready" on a boot that was still
# loading. The ceiling is now a knob; the poll count follows from it.
READY_TIMEOUT=${ARM_READY_TIMEOUT:-2250}
# A zero poll interval is the readiness guard's instant-loop device, not an arm setting: a ratio
# needs a positive denominator, so keep the historical 150 attempts for it. Otherwise
# ceil(timeout / interval), never below one attempt.
POLLS=$(awk -v t="$READY_TIMEOUT" -v s="$POLL_SLEEP" 'BEGIN {
  if (s + 0 <= 0) { print 150; exit }
  n = int(t / s)
  if (n * s < t - 1e-9) n++
  if (n < 1) n = 1
  print n
}')
ready=no
wd_done=0
for _ in $(seq 1 "$POLLS"); do
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
      3) # rc=3 covers both of the watchdog's stop verdicts (`dead` and `stalled`), so the
         # receipt must carry the word the instrument actually printed: filing a stall as a
         # death blames the engine for a frozen instrument (measured 753B attempt 5: the
         # watchdog log says verdict=stalled at t=2532s and the arm said "serve dead").
         wd_verdict=$(sed -n 's/.*verdict=\([a-z_]*\).*/\1/p' "$L/watchdog.log" 2>/dev/null | tail -1)
         wd_verdict=${wd_verdict:-unknown}
         printf 'verdict=%s rc=%s at_s=%s\n' "$wd_verdict" "$wd_rc" "$SECONDS" > "$L/watchdog-verdict.txt"
         echo "watchdog: serve ${wd_verdict} and stopped (rc=$wd_rc) at t=$((SECONDS))s -- never ready"
         ready=no; break ;;                             # rc=4 below, then harvest + teardown:
                                                        # the watchdog's captured log is the evidence
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
      # An arm whose accuracy instrument has no schema for it says so in its own recipe
      # (`metadata.decision_accuracy: none`), and this branch must obey the recipe instead of
      # running the instrument anyway: `tool-eval-bench --decision-bench-only` sends the Typed
      # Decisions/JEV case shape, while a Liquid d1 arm takes the vendor's own
      # `{state, questions}` body. A score produced over the wrong schema is the instrument's
      # failure wearing a number, so none is taken and the cells stay the result.
      accuracy_gap=""
      if grep -qE '^[[:space:]]*decision_accuracy:[[:space:]]*none[[:space:]]*$' "$RECIPE" 2>/dev/null; then
        accuracy_gap="tool-eval-bench --decision-bench-only speaks the Typed Decisions/JEV case set, and this arm answers only the vendor's noul/choice/score contract — a score from it would measure the instrument, not the model"
      fi
      accuracy_rc=0
      if [ "$api" = completions ]; then
        echo "accuracy: tool-eval-bench --decision-bench-only speaks /v1/systemone only; this arm" \
             "answers /v1/completions, so no score is taken (the cells are the result)" \
             > "$L/teb-decision.log"
      elif [ -n "$accuracy_gap" ]; then
        echo "accuracy: no score taken — $accuracy_gap (the cells are the result)" \
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
        if [ -n "$accuracy_gap" ]; then
          echo "accuracy: none — $accuracy_gap" >> "$L/house.yaml"
        else
          echo "accuracy: tool-eval-bench --decision-bench-only" >> "$L/house.yaml"
        fi
        echo "accuracy_log: teb-decision.log" >> "$L/house.yaml"
        if [ "$api" = completions ]; then
          echo "accuracy_status: not-taken — the instrument speaks /v1/systemone only and this arm answers /v1/completions" >> "$L/house.yaml"
        elif [ -n "$accuracy_gap" ]; then
          echo "accuracy_status: n/a — $accuracy_gap" >> "$L/house.yaml"
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
      # shape check -- measured 2026-10-30: [1/4] FAILED in 3.1 s with no traceback. The
      # text 0.6B tier is 1024-d and no other shorthand supplies that width.
      pooling_args=()
      case "$NAME" in
        *-0.6b-*|*0.6b-*) pooling_args=(-b dimension_check=1024) ;;
        *-2b-*|*2b-*) pooling_args=(-b dimension_check=2048) ;;
      esac
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

  # Arm-scoped extra client (`ARM_EXTRA_CLIENT`): a quality client that must speak to THIS boot's
  # serve -- house battery, BFCL, 1M/trtllm -- runs after the arm's own cells and before the
  # unconditional stop below. A second process polling the serve cannot work: this executor tears
  # the serve down, and the client's load would pollute the ladder cells the arm is measuring.
  # The command string is shell-evaluated here, so it may use `$L`, `$NODE`, `$PORT`, `$SERVED`.
  # Unset = exactly the previous executor. A nonzero rc is the client's result, never the arm's.
  if [ -n "${ARM_EXTRA_CLIENT:-}" ]; then
    extra_timeout=${ARM_EXTRA_TIMEOUT:-1800}
    # The hook gets the launch facts, never a node address in the tracked row: ARM_HOSTS is the
    # exact host list this arm runs on, ARM_RECIPE its tracked path, ARM_RECEIPT_DIR its receipt.
    # ARM_IMAGE_ID comes from the unconditional image cell above, so every arm has it with or
    # without a client.
    export ARM_HOSTS="$HOSTS" ARM_RECIPE="$RECIPE" ARM_RECEIPT_DIR="$L"
    echo "extra client: $ARM_EXTRA_CLIENT (timeout ${extra_timeout}s)"
    # Snapshot the candidate files' identities BEFORE the client runs. The log is appended after
    # it exits, so a timestamp filter would drop a client that prints a summary after writing its
    # JSON (`run_benchmarks.py` does exactly that) -- the defect this snapshot replaces. Identity
    # is content (sha256), so a new file or one the client overwrote is this hook's; a stale file
    # from a previous boot is not. `.json` only, `_raw` excluded, same root the after-walk uses.
    timeout 30 python3 -B - "$L" <<'PY'
import hashlib, json, os, sys

root = sys.argv[1]
skip = {"quality.json", "house.json", "ladder.json", "ladder.transcribed.json"}
before = {}
for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = [name for name in dirnames if name != "_raw"]
    for name in filenames:
        rel = os.path.relpath(os.path.join(dirpath, name), root)
        if not name.endswith(".json") or rel in skip:
            continue
        try:
            with open(os.path.join(root, rel), "rb") as fh:
                before[rel] = hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            continue
with open(os.path.join(root, ".client-before.sha256"), "w", encoding="utf-8") as fh:
    json.dump(before, fh, sort_keys=True)
PY
    extra_rc=0
    # Bound a wedged client so it cannot hold a TP4 boot; `-k 30` kills one that ignores TERM.
    eval "timeout -k 30 $extra_timeout $ARM_EXTRA_CLIENT" > "$L/extra-client.log" 2>&1 || extra_rc=$?
    echo "extra-client: rc=$extra_rc — $ARM_EXTRA_CLIENT" >> "$L/extra-client.log"
    # The campaign reads fixed receipt-root names, and a quality client writes its own
    # (`run_benchmarks.py`'s `<stem>.json`, `h2h-client`'s `client/house.json`): a scored arm then
    # files as "no machine-readable artefact" and is re-booted. Normalise the JSON this successful
    # hook wrote -- new or changed against the before-snapshot, anywhere under the receipt root --
    # into one `quality.json`, values unchanged, producer naming the command. A failed hook or one
    # that wrote no JSON gets nothing here: this normalises a client cell, it never manufactures one.
    if [ "$extra_rc" = 0 ] && [ ! -e "$L/quality.json" ] && [ -s "$L/.client-before.sha256" ]; then
      timeout 30 python3 -B - "$L" "$L/.client-before.sha256" "$ARM_EXTRA_CLIENT" <<'PY'
import hashlib, json, os, sys

root, before_path, command = sys.argv[1:4]
try:
    with open(before_path, encoding="utf-8") as fh:
        before = json.load(fh)
except (OSError, ValueError):
    sys.exit(0)               # no identity baseline: not this run's cell, never a timestamp guess
skip = {"quality.json", "house.json", "ladder.json", "ladder.transcribed.json"}
found = {}
for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = [name for name in dirnames if name != "_raw"]
    for name in filenames:
        rel = os.path.relpath(os.path.join(dirpath, name), root)
        if not name.endswith(".json") or rel in skip:
            continue
        path = os.path.join(root, rel)
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
            if before.get(rel) == hashlib.sha256(raw).hexdigest():
                continue          # unchanged since before the hook: a previous boot's file
            found[rel] = json.loads(raw.decode("utf-8"))
        except (OSError, ValueError):
            continue              # unparseable is not a cell; it must not measure
if found:
    payload = {"producer": {"component": "ARM_EXTRA_CLIENT", "command": command, "rc": 0,
                            "source": "run-arm.sh", "files": sorted(found)},
               "client": found}
    tmp = os.path.join(root, "quality.json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, os.path.join(root, "quality.json"))
PY
    fi
    # Never manufactures house.yaml: an absent one is "unfinished" to the receipt consumer.
    if [ -e "$L/house.yaml" ]; then
      echo "extra-client: rc=$extra_rc — output in extra-client.log" >> "$L/house.yaml"
    fi
    echo "extra client rc=$extra_rc"
  fi
else
  echo "ARM FAIL $NAME: /v1/models never answered 200 within ${READY_TIMEOUT}s" \
       "(${POLLS} polls at ${POLL_SLEEP}s) on $NODE:$PORT"
  rc=4
fi

# Per-cell /metrics scrape BEFORE the stop, from INSIDE the arm's own container. sparkrun
# launches `--rm`, so the container and every socket in it are gone ~26 ms after `die` (the same
# fact the exit capture exists for); and a host-side curl is on the wrong side of the namespace:
# sglang serves /metrics on port_base + 3 *inside* the container (recipes/MECHANICS.md:603-605),
# a port sparkrun never publishes, so a host-side probe would manufacture `absent` on an
# instrumented arm -- the exact inversion this field exists to prevent. Every existing poller
# already lives where the socket is: the omni bridge polls its own serve in-container
# (recipes/media/mods/vllm-omni-metrics-bridge/launcher.py) and the GLM launchers poll
# 127.0.0.1 (recipes/glm/mods/tensorfold-glm-exl3-launcher/launcher.py:302). This block reuses
# that placement without their republishing: it stores the raw body and classifies its shape,
# so no per-lane mod change is needed and every runtime gets one uniform probe. curl exists in
# the sglang and vLLM images (measured 2026-11-08); an image without one -- the llama.cpp tiers
# carry neither curl nor wget -- reads no_probe with the exec's exit code, never absent.
# The port is resolved per runtime from the engine's own source, not from folklore: sglang mounts
# Prometheus on the SERVED app when --enable-metrics is set (`srt/entrypoints/http_server.py:301-304`
# `add_prometheus_middleware(app)`, `/metrics` attached at `srt/utils/common.py:2797-2804`), so it is
# the API port -- the old `port_base + 3` was the scheduler's ZMQ metrics channel
# (`srt/server_args.py:829-833`), not HTTP. sparkrun maps that key at runtimes/sglang.py:95, so a
# `defaults:` key counts as well as a command token. The tensorfold launcher ships /metrics
# unconditionally (`server/http.py:106`, `server/metrics.py`), so those arms are probed on the serve
# port with no flag to look for. llama.cpp serves it only with --metrics
# (mad-science/LLAMACPP-GGUF.md:37), on the port it launched with. One exec per host, connect 3 s /
# total 5 s, no retries.
# Four states, never conflated. captured: a Prometheus body -- a `# TYPE`/`# HELP` line or a
# known runtime family prefix -- so a 200 from something that is not the engine is wrong_port.
# absent: the probe ran in the container and the engine exposes nothing (404, an empty 200, or
# a refusal on the metrics port while the serve was ready), or the recipe carries no metrics flag.
# no_probe: the probe could not run or could not read (no container, exec failure, no curl, a
# timeout, or a refusal on a boot that never readied). wrong_port: a listener answered with
# something that is not a metrics surface.
# metrics-scrape: start
M_RUNTIME=$(sed -n 's/^[[:space:]]*runtime:[[:space:]]*//p' "$RECIPE" | head -1)
M_PORT= M_SKIP=
case "$M_RUNTIME" in
  sglang)
    if grep -q 'tensorfold' "$RECIPE"; then
      M_PORT=$PORT            # tensorfold's shim serves /metrics unconditionally
    elif grep -q -- '--enable-metrics' "$RECIPE"; then
      M_PORT=$PORT            # sglang mounts /metrics on the served app
    else
      M_SKIP=recipe-has-no-flag
    fi ;;
  llama-cpp) grep -q -- '--metrics' "$RECIPE" && M_PORT=$PORT || M_SKIP=recipe-has-no-flag ;;
  *) M_PORT=$PORT ;;
esac
M_RANK=-1 M_AGG= M_DECIDE= M_CAPTURED=0 M_ABSENT=0 M_WRONG=0 M_NOPROBE=0
printf '# runtime=%s port=%s\n' "${M_RUNTIME:-unknown}" "${M_PORT:-none}" > "$L/metrics-status.txt"
for hn in $(echo "$HOSTS" | tr ',' ' '); do
  body= url=- why= ms= cid=
  if [ -n "$M_SKIP" ]; then
    ms=absent; why=$M_SKIP
  else
    url="http://127.0.0.1:$M_PORT/metrics"
    # This arm's container on this host, matched on the naming grammar, so another task whose
    # id contains ours is never probed.
    cid=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$hn" \
            "docker ps --format '{{.ID}} {{.Names}}'" 2>/dev/null \
          | sed -n "s/^\([0-9a-f]\{12\}\) sparkrun_${TID}_\(solo\|node_[0-9][0-9]*\)$/\1/p" | head -1)
    if [ -z "$cid" ]; then
      ms=no_probe; why=no-container
    else
      out=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$hn" \
              "docker exec '$cid' curl -sS --connect-timeout 3 --max-time 5 \
                -w '\n%{http_code}' '$url'" 2>"$L/metrics-$hn.err"); erc=$?
      code=${out##*$'\n'}
      body=${out%$'\n'*}
      if [ "$erc" -eq 0 ] && [ -z "$code" ]; then
        ms=no_probe; why=unparseable-http-status
      elif [ "$erc" -eq 0 ] && [ "$code" != 200 ]; then
        case "$code" in
          404|405|501|503) ms=absent; why="http-$code" ;;
          *) ms=no_probe; why="http-$code" ;;
        esac
      elif [ "$erc" -eq 0 ] && [ -z "$body" ]; then
        ms=absent; why=http-200-empty
      elif [ "$erc" -eq 0 ] \
           && { printf '%s\n' "$body" | grep -qE '^# (TYPE|HELP) ' \
                || printf '%s\n' "$body" | grep -qE '^(sglang|vllm|llamacpp)[:_]'; }; then
        ms=captured; why="http-$code"
      elif [ "$erc" -eq 0 ]; then
        ms=wrong_port; why="not-prometheus: $(printf '%s' "$body" | head -1 | cut -c1-80)"
      elif [ "$erc" -eq 7 ] && [ "$ready" = yes ]; then
        ms=absent; why=listener-refused
      elif [ "$erc" -eq 7 ]; then
        ms=no_probe; why=serve-not-ready
      else
        ms=no_probe; why="exec-or-curl-exit-$erc"
      fi
    fi
  fi
  { printf '%s host=%s container=%s url=%s reason=%s\n' "$ms" "$hn" "${cid:--}" "$url" "$why"
    printf '%s\n' "$body"; } > "$L/metrics-$hn.txt"
  printf '%s host=%s container=%s url=%s reason=%s\n' \
    "$ms" "$hn" "${cid:--}" "$url" "$why" >> "$L/metrics-status.txt"
  case "$ms" in
    captured) M_CAPTURED=$((M_CAPTURED + 1)); rank=1 ;;
    absent) M_ABSENT=$((M_ABSENT + 1)); rank=0 ;;
    wrong_port) M_WRONG=$((M_WRONG + 1)); rank=2 ;;
    *) M_NOPROBE=$((M_NOPROBE + 1)); rank=3 ;;
  esac
  if [ "$rank" -gt "$M_RANK" ]; then
    M_RANK=$rank; M_AGG=$ms
    M_DECIDE="$ms host=$hn container=${cid:--} url=$url reason=$why"
  fi
done
[ -n "$M_AGG" ] || M_AGG=absent
[ -n "$M_DECIDE" ] || M_DECIDE="absent host=${HOSTS%%,*} container=- url=- reason=no-host"
echo "metrics: $M_AGG ($M_CAPTURED captured, $M_ABSENT absent, $M_WRONG wrong_port, $M_NOPROBE no_probe)"
# The single authority for this fact is metrics-status.txt plus the metrics-<host>.txt bodies:
# nothing is appended to house.yaml, and no `metrics_*` key is written into a marker, so a marker
# reader is never tempted to look for one (campaign/sparkrun_campaign/evidence.py:metrics_status
# reads the sidecar for exactly that reason).
# metrics-scrape: end

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
captured=0
for hn in $(echo "$HOSTS" | tr ',' ' '); do
  # The engine's own stdout comes from the capture armed before the launch, not from a read taken
  # here: a boot that died is gone from the node (`--rm`), and a reaped one answers `docker logs`
  # with docker's own error, which then reads as engine output. One file per container on the
  # node, merged into the receipt's per-rank `docker-<rank>.log` with the exit state the `die`
  # event carried. A host with no stream says so in cap-<host>.log; an absent file would read as
  # "the engine printed nothing", which is the one thing this block exists to disprove.
  capfiles=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$hn" \
               "ls -1 '$CAPTURE_DIR' 2>/dev/null | grep -v -x pid" 2>/dev/null)
  [ -n "$capfiles" ] || echo "# capture failed: no engine-exit capture on $hn for this arm" \
                          "($CAPTURE_DIR is empty or the host is unreachable); the engine's stdout" \
                          "for this host is lost" > "$L/cap-$hn.log"
  for f in $capfiles; do
    case "$f" in
      *.log)
        rank=${f%.log}; rank=${rank##*_}
        ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$hn" \
          "cat '$CAPTURE_DIR/$f' '$CAPTURE_DIR/${f%.log}.die' '$CAPTURE_DIR/${f%.log}.oom'" > "$L/docker-$rank.log" 2>/dev/null
        captured=$((captured + 1))
        echo "capture: $f on $hn -> docker-$rank.log" ;;
      *.die|*.oom) : ;;                  # merged into its log above
      *)
        ssh -o ConnectTimeout=5 -o BatchMode=yes "red@$hn" \
          "cat '$CAPTURE_DIR/$f'" >> "$L/cap-$hn.log" 2>/dev/null ;;
    esac
  done
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
# harvest-report: start
# Report what the receipt HOLDS, not only what this loop copied: a boot the watchdog stopped
# leaves `serve-reaped-<container>.log` (written before its stop), and that used to be invisible
# to the count — the arm whose only surviving log was the reaped one still printed 0.
live_logs=()
reaped_logs=()
for f in "$L"/serve-*.log; do
  [ -e "$f" ] || continue
  case "${f##*/}" in
    serve-reaped-*) reaped_logs+=("${f##*/}") ;;
    *) live_logs+=("${f##*/}") ;;
  esac
done
for name in "${live_logs[@]+"${live_logs[@]}"}"; do echo "serve log: $name (harvested)"; done
for name in "${reaped_logs[@]+"${reaped_logs[@]}"}"; do echo "serve log: $name (reaped by the watchdog)"; done
echo "serve logs harvested: $harvested live copy/copies; receipt holds" \
     "${#live_logs[@]} live and ${#reaped_logs[@]} reaped serve log(s)"
# harvest-report: end
echo "engine stdout captured: $captured container stream(s) (a boot that died has no other copy)"

stop_capture
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
# A pre-ready client writes its cell once the boot's containers are gone, so it is reaped
# elsewhere; wait for it here so the receipt is complete when this script exits, and never
# leave a sampler running on a shared node. A bounded wait, not a join: a wedged client must
# not hold the arm open (an absent cell is a failed client, which the campaign retries).
if [ -n "${EXTRA_PID:-}" ]; then
  waited=0
  while kill -0 "$EXTRA_PID" 2>/dev/null && [ "$waited" -lt 60 ]; do
    sleep 1; waited=$((waited + 1))
  done
  if kill -0 "$EXTRA_PID" 2>/dev/null; then
    echo "extra client still sampling ${waited}s after teardown; killing it (no cell written)"
    kill "$EXTRA_PID" 2>/dev/null
  else
    wait "$EXTRA_PID"; extra_rc=$?
    echo "extra-client: rc=$extra_rc — ${ARM_EXTRA_CLIENT_ARMED:-}" >> "$L/extra-client.log"
    echo "extra client rc=$extra_rc (pre-ready)"
  fi
fi
echo "ARM DONE $NAME rc=$rc"
exit "$rc"