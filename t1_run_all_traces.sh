#!/bin/bash
# Task 1: build baseline (no prefetcher), IP-stride and SPP, run all traces
# in parallel and print IPC, speedup, L1D/L2C/LLC MPKI, prefetch accuracy,
# coverage etc. in one table (also saved to outputs/summary.csv).
#
# Usage: ./t1_run_all_traces.sh [--no-build] [--only-parse]
#   CXX (default g++-7), WARMUP, SIM (default 25M each) can be overridden.
set -euo pipefail

WARMUP=${WARMUP:-25000000}
SIM=${SIM:-25000000}
export CXX=${CXX:-g++-7}
CONFIGS=(no ip_stride spp)   # "no" = baseline, used for speedup/coverage
TRACES=(traces/Trace*.gz)

BUILD=1
RUN=1
for arg in "$@"; do
  case $arg in
    --no-build) BUILD=0 ;;
    --only-parse) BUILD=0; RUN=0 ;;
  esac
done

mkdir -p outputs

if [ $BUILD -eq 1 ]; then
  echo "Building with $CXX..."
  # Builds share obj/, so they must run sequentially.
  for p in "${CONFIGS[@]}"; do
    ./build_champsim.sh "$p" lru baseline > "outputs/${p}_build_logs.txt" 2>&1 \
      || { echo "Build of $p failed, see outputs/${p}_build_logs.txt"; exit 1; }
  done
  echo "Build done"
fi

if [ $RUN -eq 1 ]; then
  echo "Running ${#CONFIGS[@]} configs x ${#TRACES[@]} traces in parallel (warmup=$WARMUP sim=$SIM)..."
  pids=()
  for p in "${CONFIGS[@]}"; do
    BIN="./bin/hashed_perceptron-no-${p}-no-no-no-no-no-lru-lru-lru-lru-lru-lru-lru-lru-1core-baseline"
    for t in "${TRACES[@]}"; do
      name=$(basename "$t" .gz)
      "$BIN" -warmup_instructions "$WARMUP" -simulation_instructions "$SIM" \
        -traces "$t" > "outputs/${p}-${name}.txt" 2>&1 &
      pids+=($!)
    done
  done
  fail=0
  for pid in "${pids[@]}"; do wait "$pid" || fail=1; done
  [ $fail -eq 0 ] || echo "WARNING: some simulations exited non-zero"
  echo "Simulations done"
fi

python3 parse_stats.py outputs no "${CONFIGS[@]}"
