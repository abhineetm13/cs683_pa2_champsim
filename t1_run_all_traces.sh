echo "Building..."
./build_champsim.sh ip_stride lru baseline > outputs/ip_stride_build_logs.txt 2>&1
./build_champsim.sh spp lru baseline > outputs/spp_build_logs.txt 2>&1
echo "Build done"

for i in {1..3}
do
  echo "Trace $i"
  IP_STRIDE_OUT="outputs/ip_stride-Trace$i.txt"
  SPP_OUT="outputs/spp-Trace$i.txt"
  echo "IP Stride Prefetching"
  ./bin/hashed_perceptron-no-ip_stride-no-no-no-no-no-lru-lru-lru-lru-lru-lru-lru-lru-1core-baseline -warmup_instructions 25000000 -simulation_instructions 25000000 -traces ./traces/Trace$i.gz > $IP_STRIDE_OUT 2>&1
  grep IPC $IP_STRIDE_OUT

  echo "Stride Pattern Prefetching"
  ./bin/hashed_perceptron-no-spp-no-no-no-no-no-lru-lru-lru-lru-lru-lru-lru-lru-1core-baseline -warmup_instructions 25000000 -simulation_instructions 25000000 -traces ./traces/Trace$i.gz > $SPP_OUT 2>&1
  grep IPC $SPP_OUT
done

