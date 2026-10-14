set -euo

echo "Building..."
./build_champsim.sh no rrip baseline > outputs/rrip_build_logs.txt 2>&1
./build_champsim.sh no irrip baseline > outputs/irrip_build_logs.txt 2>&1
echo "Build done"

RRIP_BIN="./bin/hashed_perceptron-no-no-no-no-no-no-no-lru-lru-lru-rrip-lru-lru-lru-lru-1core-baseline"
IRRIP_BIN="./bin/hashed_perceptron-no-no-no-no-no-no-no-lru-lru-lru-irrip-lru-lru-lru-lru-1core-baseline"

for i in {1..3}
do
  echo "Trace $i"
  RRIP_OUT="outputs/rrip-Trace$i.txt"
  IRRIP_OUT="outputs/irrip-Trace$i.txt"
  echo "RRIP"
  $RRIP_BIN -warmup_instructions 25000000 -simulation_instructions 25000000 -traces ./traces/Trace$i.gz > $RRIP_OUT 2>&1
  grep IPC $RRIP_OUT

  echo "I-RRIP"
  $IRRIP_BIN -warmup_instructions 25000000 -simulation_instructions 25000000 -traces ./traces/Trace$i.gz > $IRRIP_OUT 2>&1
  grep IPC $IRRIP_OUT
done

