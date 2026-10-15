#!/bin/bash
# Task 3: compare the no-prefetch baseline, standalone Dynamic I-RRIP,
# standalone SPP, and SPP + prefetch-aware Dynamic I-RRIP. Run all traces
# in parallel and report every metric required by the assignment.
#
# Usage: ./t3_run_all_traces.sh [--no-build] [--only-parse]
#   CXX (default g++-7), WARMUP, and SIM (default 25M each) can be overridden.
set -euo pipefail

WARMUP=${WARMUP:-25000000}
SIM=${SIM:-25000000}
export CXX=${CXX:-g++-7}
CONFIGS=(no dyn_irrip spp spp_dyn_irrip)
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

prefetcher_for() {
  case $1 in
    no|dyn_irrip) echo no ;;
    spp|spp_dyn_irrip) echo spp ;;
  esac
}

policy_for() {
  case $1 in
    no|spp) echo lru ;;
    dyn_irrip|spp_dyn_irrip) echo dyn_irrip ;;
  esac
}

if [ "$BUILD" -eq 1 ]; then
  echo "Building with $CXX..."
  # Builds share obj/, so they must run sequentially.
  for config in "${CONFIGS[@]}"; do
    prefetcher=$(prefetcher_for "$config")
    policy=$(policy_for "$config")
    ./build_champsim.sh "$prefetcher" "$policy" baseline \
      > "outputs/${config}_build_logs.txt" 2>&1 \
      || { echo "Build of $config failed, see outputs/${config}_build_logs.txt"; exit 1; }
  done
  echo "Build done"
fi

if [ "$RUN" -eq 1 ]; then
  echo "Running ${#CONFIGS[@]} configs x ${#TRACES[@]} traces in parallel (warmup=$WARMUP sim=$SIM)..."
  pids=()
  for config in "${CONFIGS[@]}"; do
    prefetcher=$(prefetcher_for "$config")
    policy=$(policy_for "$config")
    # The L1D prefetcher occupies the second prefetcher field in the name.
    bin="./bin/hashed_perceptron-no-${prefetcher}-no-no-no-no-no-lru-lru-lru-${policy}-lru-lru-lru-lru-1core-baseline"
    for trace in "${TRACES[@]}"; do
      name=$(basename "$trace" .gz)
      "$bin" -warmup_instructions "$WARMUP" -simulation_instructions "$SIM" \
        -traces "$trace" > "outputs/${config}-${name}.txt" 2>&1 &
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

# The no-prefetch + LRU configuration supplies baseline IPC and L1D misses for
# speedup and coverage. The other three rows directly test Task 3's requirement
# to beat standalone Dynamic I-RRIP and standalone SPP.
SUMMARY_CSV=task3_summary.csv python3 parse_stats.py outputs no "${CONFIGS[@]}"
