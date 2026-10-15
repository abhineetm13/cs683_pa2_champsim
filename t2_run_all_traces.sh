#!/bin/bash
# Task 2a: build RRIP and I-RRIP, run all traces in parallel, and report
# IPC, speedup, and L2C/L2 instruction/L2 data load MPKI.
#
# Usage: ./t2_run_all_traces.sh [--no-build] [--only-parse]
#   CXX (default g++-7), WARMUP, and SIM (default 25M each) can be overridden.
set -euo pipefail

WARMUP=${WARMUP:-25000000}
SIM=${SIM:-25000000}
export CXX=${CXX:-g++-7}
CONFIGS=(rrip irrip) # RRIP is the Task 2a speedup baseline.
TRACES=(traces/Trace*.gz)

BUILD=1
RUN=1
for arg in "$@"; do
  case $arg in
    --no-build) BUILD=0 ;;
    --only-parse) BUILD=0; RUN=0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

mkdir -p outputs

if [ "$BUILD" -eq 1 ]; then
  echo "Building with $CXX..."
  # Builds share obj/, so they must run sequentially.
  for policy in "${CONFIGS[@]}"; do
    ./build_champsim.sh no "$policy" baseline \
      > "outputs/${policy}_build_logs.txt" 2>&1 \
      || { echo "Build of $policy failed, see outputs/${policy}_build_logs.txt"; exit 1; }
  done
  echo "Build done"
fi

if [ "$RUN" -eq 1 ]; then
  echo "Running ${#CONFIGS[@]} configs x ${#TRACES[@]} traces in parallel (warmup=$WARMUP sim=$SIM)..."
  pids=()
  for policy in "${CONFIGS[@]}"; do
    bin="./bin/hashed_perceptron-no-no-no-no-no-no-no-lru-lru-lru-${policy}-lru-lru-lru-lru-1core-baseline"
    for trace in "${TRACES[@]}"; do
      name=$(basename "$trace" .gz)
      "$bin" -warmup_instructions "$WARMUP" -simulation_instructions "$SIM" \
        -traces "$trace" > "outputs/${policy}-${name}.txt" 2>&1 &
      pids+=("$!")
    done
  done

  fail=0
  for pid in "${pids[@]}"; do
    wait "$pid" || fail=1
  done
  [ "$fail" -eq 0 ] || echo "WARNING: some simulations exited non-zero"
  echo "Simulations done"
fi

SUMMARY_CSV=task2a_summary.csv python3 parse_stats.py outputs rrip "${CONFIGS[@]}"
