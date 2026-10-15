#!/bin/bash
# Compare baseline RRIP with the PSEL-based, insertion-only Dynamic I-RRIP.
# One configuration runs at a time; its traces run in parallel.
#
# Usage: ./t2b_duel_run_all_traces.sh [--no-build] [--only-parse]
#   CXX (default g++-7), WARMUP, and SIM (default 25M each) can be overridden.
set -euo pipefail

WARMUP=${WARMUP:-25000000}
SIM=${SIM:-25000000}
export CXX=${CXX:-g++-7}
CONFIGS=(duel_rrip duel_irrip)
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

policy_for() {
  case $1 in
    duel_rrip) echo rrip ;;
    duel_irrip) echo duel_irrip ;;
  esac
}

if [ "$BUILD" -eq 1 ]; then
  echo "Building with $CXX..."
  for config in "${CONFIGS[@]}"; do
    policy=$(policy_for "$config")
    ./build_champsim.sh no "$policy" duel \
      > "outputs/${config}_build_logs.txt" 2>&1 \
      || { echo "Build of $config failed, see outputs/${config}_build_logs.txt"; exit 1; }
  done
  echo "Build done"
fi

if [ "$RUN" -eq 1 ]; then
  echo "Running ${#CONFIGS[@]} configs one at a time, with ${#TRACES[@]} traces per config in parallel (warmup=$WARMUP sim=$SIM)..."
  overall_fail=0
  for config in "${CONFIGS[@]}"; do
    echo "Running configuration: $config"
    policy=$(policy_for "$config")
    bin="./bin/hashed_perceptron-no-no-no-no-no-no-no-lru-lru-lru-${policy}-lru-lru-lru-lru-1core-duel"
    pids=()
    for trace in "${TRACES[@]}"; do
      name=$(basename "$trace" .gz)
      "$bin" -warmup_instructions "$WARMUP" -simulation_instructions "$SIM" \
        -traces "$trace" > "outputs/${config}-${name}.txt" 2>&1 &
      pids+=("$!")
    done

    config_fail=0
    for pid in "${pids[@]}"; do
      wait "$pid" || config_fail=1
    done
    if [ "$config_fail" -ne 0 ]; then
      echo "WARNING: one or more $config simulations exited non-zero"
      overall_fail=1
    else
      echo "Completed configuration: $config"
    fi
  done
  [ "$overall_fail" -eq 0 ] || echo "WARNING: some simulations exited non-zero"
  echo "Simulations done"
fi

SUMMARY_CSV=task2b_duel_summary.csv python3 parse_stats.py outputs duel_rrip "${CONFIGS[@]}"
