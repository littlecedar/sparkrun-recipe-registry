#!/usr/bin/env bash
# Enable the three io_uring syscalls for containers on the whole fleet, node by node.
#
# Per-node work lives in tools/enable-io-uring.py (piped over ssh stdin, no temp copy on the node);
# this file is only the loop, the argument handling and the summary.  Read the tool's header for the
# ordering and the rollback; the two things worth repeating here:
#
#   * `--probe-only` changes nothing: one `--rm` container per node and a verdict, so the "before"
#     evidence and a re-check after any later event cost one command.
#   * a node with a running container is skipped, never forced — the change needs a Docker daemon
#     restart and that would stop it (live-restore is off on this fleet).
#
#   tools/enable-io-uring.sh --probe-only --nodes node-a,node-b   # aliases from your ssh config
#   tools/enable-io-uring.sh                                       # owner-authorized fleet change,
#                                                                  # nodes from $SPARKRUN_FLEET_NODES
#
# Exit: 0 all nodes ok (or, with --probe-only, allowed), 1 any failure, 3 any node skipped,
# 2 no node list given.  No fleet aliases are compiled in — see the usage block.

set -uo pipefail

usage() {
  sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
  cat <<'EOF'

usage: enable-io-uring.sh (--nodes LIST | --nodes-file FILE | $SPARKRUN_FLEET_NODES) [--probe-only] [tool args...]

  --nodes LIST   comma-separated ssh aliases to act on (repeatable)
  --nodes-file   file of aliases, one per line (# comments and blanks ignored)
  --probe-only   run the syscall probe only, change nothing
  other args     forwarded to tools/enable-io-uring.py (e.g. --probe-image, --profile-source)

No node list is compiled in: this repository ships to third parties, so the fleet's own aliases live
in ssh config / the environment, never in the tree (tests/test_tracked_address_hygiene.py enforces
the address half of that). Give one of the three sources; exit 2 if none.
EOF
}

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
tool="$here/enable-io-uring.py"

nodes=()
nodes_file=""
probe_only=0
forward=()

while (($#)); do
  case "$1" in
    --nodes)
      IFS=, read -r -a _split <<<"${2:?--nodes needs a value}"
      nodes+=("${_split[@]}")
      shift 2
      ;;
    --nodes-file)
      nodes_file=${2:?--nodes-file needs a value}
      shift 2
      ;;
    --probe-only)
      probe_only=1
      forward+=(--probe-only)
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      forward+=("$1")
      shift
      ;;
  esac
done

# The fleet comes from the caller: --nodes / --nodes-file, else $SPARKRUN_FLEET_NODES.
if [[ -z "$nodes_file" && ${#nodes[@]} -eq 0 && -n "${SPARKRUN_FLEET_NODES:-}" ]]; then
  IFS=$', \t\n' read -r -a _split <<<"$SPARKRUN_FLEET_NODES"
  nodes+=("${_split[@]}")
fi
if [[ -n "$nodes_file" ]]; then
  mapfile -t _file_nodes < <(sed -e 's/#.*//' "$nodes_file")
  for n in "${_file_nodes[@]}"; do [[ -n "${n// /}" ]] && nodes+=("${n// /}"); done
fi
if [[ ${#nodes[@]} -eq 0 ]]; then
  echo "enable-io-uring.sh: no nodes — pass --nodes a,b, --nodes-file FILE, or set \$SPARKRUN_FLEET_NODES" >&2
  exit 2
fi
[[ -r "$tool" ]] || { echo "enable-io-uring.sh: missing $tool" >&2; exit 1; }

ok=0
skipped=0
failed=0
summary=()

for node in "${nodes[@]}"; do
  [[ -n "$node" ]] || continue
  echo "=== $node"
  out=$(ssh -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=15 "$node" \
    "sudo -n python3 - --node '$node' ${forward[*]:-}" <"$tool" 2>&1)
  rc=$?
  printf '%s\n' "$out" | sed 's/^/    /'
  result=$(printf '%s\n' "$out" | grep -m1 '^RESULT ')
  status=${result#RESULT "$node" }
  status=${status%% *}
  case "$rc" in
    0) ok=$((ok + 1)) ;;
    3) skipped=$((skipped + 1)) ;;
    *) failed=$((failed + 1)) ;;
  esac
  summary+=("$(printf '%-12s rc=%-2s %s' "$node" "$rc" "${status:-no-result}")")
done

echo
echo "=== summary"
printf '%s\n' "${summary[@]}"
if ((probe_only)); then
  echo "probe-only: $ok allowed, $failed denied/unreachable, $skipped skipped"
else
  echo "$ok enabled (or already), $failed failed, $skipped skipped"
fi

((failed == 0 && skipped == 0)) || exit $((skipped > 0 ? 3 : 1))
exit 0
