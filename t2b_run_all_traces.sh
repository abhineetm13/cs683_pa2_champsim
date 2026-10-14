set -euo

echo "Building..."
./build_champsim.sh no rrip baseline > outputs/rrip_build_logs.txt 2>&1
./build_champsim.sh no dyn_irrip baseline > outputs/dyn_irrip_build_logs.txt 2>&1
echo "Build done"

RRIP_BIN="./bin/hashed_perceptron-no-no-no-no-no-no-no-lru-lru-lru-rrip-lru-lru-lru-lru-1core-baseline"
DYN_IRRIP_BIN="./bin/hashed_perceptron-no-no-no-no-no-no-no-lru-lru-lru-dyn_irrip-lru-lru-lru-lru-1core-baseline"

for i in {1..3}
do
  echo "Trace $i"
  RRIP_OUT="outputs/rrip-Trace$i.txt"
  DYN_IRRIP_OUT="outputs/dyn_irrip-Trace$i.txt"
  echo "RRIP"
  $RRIP_BIN -warmup_instructions 25000000 -simulation_instructions 25000000 -traces ./traces/Trace$i.gz > $RRIP_OUT 2>&1
  grep IPC $RRIP_OUT

  echo "Dynamic I-RRIP"
  $DYN_IRRIP_BIN -warmup_instructions 25000000 -simulation_instructions 25000000 -traces ./traces/Trace$i.gz > $DYN_IRRIP_OUT 2>&1
  grep IPC $DYN_IRRIP_OUT
done

