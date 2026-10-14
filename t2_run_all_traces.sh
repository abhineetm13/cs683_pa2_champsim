set -euo

echo "Building..."
./build_champsim.sh baseline rrip baseline > outputs/rrip_build_logs.txt 2>&1
./build_champsim.sh spp irrip baseline > outputs/irrip_build_logs.txt 2>&1
echo "Build done"

for i in {1..3}
do
  echo "Trace $i"
  RRIP_OUT="outputs/rrip-Trace$i.txt"
  IRRIP_OUT="outputs/irrip-Trace$i.txt"
  echo "RRIP"
  ./bin/hashed_perceptron-no-ip_stride-no-no-no-no-no-lru-lru-lru-lru-lru-lru-lru-lru-1core-baseline -warmup_instructions 25000000 -simulation_instructions 25000000 -traces ./traces/Trace$i.gz > $RRIP 2>&1
  grep IPC $RRIP

  echo "I-RRIP"
  ./bin/hashed_perceptron-no-spp-no-no-no-no-no-lru-lru-lru-lru-lru-lru-lru-lru-1core-baseline -warmup_instructions 25000000 -simulation_instructions 25000000 -traces ./traces/Trace$i.gz > $IRRIP 2>&1
  grep IPC $IRRIP
done

