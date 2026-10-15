#!/bin/bash
# Task 3 controlled experiment: run SPP + Dynamic I-RRIP at threshold 0.15,
# inserting L2 prefetch fills at RRPV3 rather than RRPV2. Existing no-prefetch,
# standalone SPP, and original RRPV2 results are reused for comparison.
#
# Usage: ./t3_pf_rrpv3_experiment.sh [--no-build] [--only-parse]
#   CXX (default g++-7), WARMUP, and SIM (default 25M each) can be overridden.
set -euo pipefail

WARMUP=${WARMUP:-25000000}
SIM=${SIM:-25000000}
export CXX=${CXX:-g++-7}
POLICY=dyn_irrip_pf3_t015
CONFIG=t3_spp_dyn_irrip_pf3_t015
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
  echo "Building SPP + $POLICY with $CXX..."
  ./build_champsim.sh spp "$POLICY" baseline \
    > "outputs/${CONFIG}_build_logs.txt" 2>&1 \
    || { echo "Build failed; see outputs/${CONFIG}_build_logs.txt"; exit 1; }
  echo "Build done"
fi

if [ "$RUN" -eq 1 ]; then
  echo "Running $CONFIG on ${#TRACES[@]} traces in parallel (warmup=$WARMUP sim=$SIM)..."
  bin="./bin/hashed_perceptron-no-spp-no-no-no-no-no-lru-lru-lru-${POLICY}-lru-lru-lru-lru-1core-baseline"
  pids=()
  for trace in "${TRACES[@]}"; do
    name=$(basename "$trace" .gz)
    "$bin" -warmup_instructions "$WARMUP" -simulation_instructions "$SIM" \
      -traces "$trace" > "outputs/${CONFIG}-${name}.txt" 2>&1 &
    pids+=("$!")
  done

  fail=0
  for pid in "${pids[@]}"; do
    wait "$pid" || fail=1
  done
  [ "$fail" -eq 0 ] || { echo "ERROR: one or more simulations failed"; exit 1; }
  echo "Simulations done"
fi

for required in no spp t3_spp_dyn_irrip_t015 "$CONFIG"; do
  for trace in "${TRACES[@]}"; do
    name=$(basename "$trace" .gz)
    [ -f "outputs/${required}-${name}.txt" ] \
      || { echo "Missing comparison output: outputs/${required}-${name}.txt" >&2; exit 1; }
  done
done

SUMMARY_CSV=task3_pf_rrpv3_summary.csv \
  python3 parse_stats.py outputs no spp t3_spp_dyn_irrip_t015 "$CONFIG"
