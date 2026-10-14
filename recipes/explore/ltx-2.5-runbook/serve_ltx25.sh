#!/bin/bash
# Start ComfyUI on .35 with a 1 Hz unified-memory sampler and a timestamped
# log. tstamp.py splits stdout on \r too, so tqdm sampler bars get their own
# timestamped segments (needed for the two-stage split).
# Sustained-load power-loss mitigation (see lane doc): cap the GPU clock.
set -euo pipefail
cd "$HOME/ComfyUI"
R="${LTX_RECEIPTS:-$HOME/ltx25/receipts2}"
mkdir -p "$R"
# shellcheck disable=SC1091
. .venv/bin/activate

if [ "${SKIP_CLOCK_CAP:-0}" != "1" ]; then
  echo "capping GPU clock at 2200 MHz (sustained-load fix)"
  sudo nvidia-smi -lgc 0,2200 2>&1 || echo "WARN clock cap unsupported here"
fi

# unified-memory sampler: peak used = MemTotal - min(MemAvailable)
(
  while true; do
    awk '/^MemTotal:/{t=$2} /^MemAvailable:/{a=$2} END{printf "%s %.3f\n", systime(), (t-a)/1048576}' \
      /proc/meminfo
    sleep 1
  done
) > "$R/mem.tsv" &
MEM=$!
trap 'kill $MEM 2>/dev/null || true' EXIT

exec python -u "$HOME/ltx25/tstamp.py" > "$R/server.log" 2>&1
