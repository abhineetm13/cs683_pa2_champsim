#!/bin/bash
# Task 2b: build RRIP and five Dynamic I-RRIP threshold variants, run one
# configuration at a time (with that configuration's traces in parallel), and
# report IPC, speedup, and L2C/L2 instruction/L2 data load MPKI for the
# required sensitivity study.
#
# Usage: ./t2b_run_all_traces.sh [--no-build] [--only-parse]
#   CXX (default g++-7), WARMUP, and SIM (default 25M each) can be overridden.
set -euo pipefail

WARMUP=${WARMUP:-25000000}
SIM=${SIM:-25000000}
export CXX=${CXX:-g++-7}
THRESHOLDS=(0.15 0.20 0.25 0.30 0.35)
CONFIGS=(rrip)
for threshold in "${THRESHOLDS[@]}"; do
  CONFIGS+=("t2b_dyn_irrip_t${threshold/./}")
done
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

generated_policies=()
cleanup_generated_policies() {
  if [ "${#generated_policies[@]}" -gt 0 ]; then
    rm -f "${generated_policies[@]}"
  fi
}
trap cleanup_generated_policies EXIT

if [ "$BUILD" -eq 1 ]; then
  echo "Building with $CXX..."
  # Builds share obj/, so they must run sequentially.
  ./build_champsim.sh no rrip baseline > outputs/rrip_build_logs.txt 2>&1 \
    || { echo "Build of rrip failed, see outputs/rrip_build_logs.txt"; exit 1; }

  for threshold in "${THRESHOLDS[@]}"; do
    policy="t2b_dyn_irrip_t${threshold/./}"
    policy_file="replacement/${policy}.l2c_repl"
    generated_policies+=("$policy_file")
    sed "s/^#define IRRIP_THRESHOLD .*/#define IRRIP_THRESHOLD ${threshold}/" \
      replacement/t2b_dyn_irrip.l2c_repl > "$policy_file"
    ./build_champsim.sh no "$policy" baseline \
      > "outputs/${policy}_build_logs.txt" 2>&1 \
      || { echo "Build of $policy failed, see outputs/${policy}_build_logs.txt"; exit 1; }
  done
  echo "Build done"
fi

if [ "$RUN" -eq 1 ]; then
  echo "Running ${#CONFIGS[@]} configs one at a time, with ${#TRACES[@]} traces per config in parallel (warmup=$WARMUP sim=$SIM)..."
  overall_fail=0
  for policy in "${CONFIGS[@]}"; do
    echo "Running configuration: $policy"
    bin="./bin/hashed_perceptron-no-no-no-no-no-no-no-lru-lru-lru-${policy}-lru-lru-lru-lru-1core-baseline"
    pids=()
    for trace in "${TRACES[@]}"; do
      name=$(basename "$trace" .gz)
      "$bin" -warmup_instructions "$WARMUP" -simulation_instructions "$SIM" \
        -traces "$trace" > "outputs/${policy}-${name}.txt" 2>&1 &
      pids+=("$!")
    done

    config_fail=0
    for pid in "${pids[@]}"; do
      wait "$pid" || config_fail=1
    done
    if [ "$config_fail" -ne 0 ]; then
      echo "WARNING: one or more $policy simulations exited non-zero"
      overall_fail=1
    else
      echo "Completed configuration: $policy"
    fi
  done
  [ "$overall_fail" -eq 0 ] || echo "WARNING: some simulations exited non-zero"
  echo "Simulations done"
fi

SUMMARY_CSV=task2b_summary.csv python3 parse_stats.py outputs rrip "${CONFIGS[@]}"
