#!/usr/bin/env bash
# Overnight hard-battery driver. One invocation runs EVERY benchmark for ONE
# model, sequentially, so the two models can run as two parallel processes
# (the engine serves >=4 streams; quality is unaffected by that concurrency).
#
#   recipes/ds4/benchmarks/run_overnight.sh <model> <logfile>
#
# Every harness is resumable, so re-running after an interruption continues
# instead of restarting.  Order is deliberate: the headline (HLE) runs first while
# the machine is quietest; the large suites are capped; the small ones run in full.
#
# Thinking mode: PRIMARY arms are thinking OFF (the only mode that produces graded
# answers on HLE-class prompts -- see _probe_size.py / bench_reason.py docstring).
# A SECONDARY thinking-ON arm is included for gpqa + math500 because those
# terminate in seconds even with reasoning on; a thinking-ON HLE/AIME arm is
# deliberately omitted because it streams the whole budget and stalls.
set -u
cd "$(dirname "$0")"
MODEL="${1:?usage: run_overnight.sh <model> <logfile>}"
LOG="${2:-results/_raw/overnight.${MODEL}.log}"
BASE="${BASE:-http://spark-head.internal.littlecedar.net:4000}"
VQA=".venv-qa/bin/python"

log() { echo "[$(date +%H:%M:%S)] $*" >>"$LOG"; }
run() { log "$*"; "$@" >>"$LOG" 2>&1; }

log "START model=$MODEL base=$BASE"

# primary, thinking off
run $VQA bench_reason.py --base-url "$BASE" --model "$MODEL" --bench hle      --thinking off --limit 200
run $VQA bench_reason.py --base-url "$BASE" --model "$MODEL" --bench gpqa     --thinking off
run $VQA bench_reason.py --base-url "$BASE" --model "$MODEL" --bench mmlu_pro --thinking off --limit 400
run $VQA bench_reason.py --base-url "$BASE" --model "$MODEL" --bench math500  --thinking off --limit 200
run $VQA bench_reason.py --base-url "$BASE" --model "$MODEL" --bench aime     --thinking off
run python3             bench_code.py   --base-url "$BASE" --model "$MODEL" --bench both --thinking off --seed 1234

# secondary, thinking on (only the arms that terminate quickly)
run $VQA bench_reason.py --base-url "$BASE" --model "$MODEL" --bench gpqa     --thinking on --limit 100
run $VQA bench_reason.py --base-url "$BASE" --model "$MODEL" --bench math500  --thinking on --limit 40

log "DONE model=$MODEL"
echo "DONE model=$MODEL (see $LOG)"