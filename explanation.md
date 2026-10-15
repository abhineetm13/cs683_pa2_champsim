# Task 1 — L1D Stride Pattern Prefetcher (SPP): explanation

Goal: improve L1D prefetch **accuracy** and, ultimately, **IPC**, on the three
provided traces (25M warmup + 25M simulation instructions, L2C replacement = LRU).

## How to reproduce

```bash
./t1_run_all_traces.sh            # build no / ip_stride / spp, run all traces in parallel, print tables
./t1_run_all_traces.sh --no-build # reuse existing binaries
./t1_run_all_traces.sh --only-parse
```

* The build uses `CXX=g++-7` (the Makefile honours `$(CXX)`); the system default
  `g++` on our machine is GCC 16.
* `parse_stats.py` extracts IPC, speedup (vs. no prefetching), L1D prefetch
  requested / issued / useful / useless / late, accuracy, coverage and
  L1D / L2C / LLC MPKI, and writes `outputs/summary.csv`.
* Raw simulator outputs: `outputs/<config>-Trace<N>.txt`.

Definitions used:

* **Speedup** = IPC with prefetcher / IPC without prefetcher
* **Accuracy** = useful prefetches / prefetches issued to the lower level (as printed by ChampSim)
* **Coverage** = (L1D load misses baseline − L1D load misses with prefetcher) / L1D load misses baseline

## Final results

| Config | Trace | IPC | Speedup | L1D load MPKI | Accuracy % | Coverage % |
|---|---|---|---|---|---|---|
| no prefetch | Trace1 | 0.2323 | 1.0000 | 10.678 | – | – |
| no prefetch | Trace2 | 0.2512 | 1.0000 | 13.538 | – | – |
| no prefetch | Trace3 | 0.3821 | 1.0000 | 3.403 | – | – |
| ip_stride | Trace1 | 0.2335 | 1.0048 | 10.119 | 52.71 | 5.24 |
| ip_stride | Trace2 | 0.2513 | 1.0004 | 13.438 | 38.18 | 0.74 |
| ip_stride | Trace3 | 0.3829 | 1.0021 | 3.318 | 15.99 | 2.51 |
| SPP (before, commit a303c9d) | Trace1 | 0.2331 | 1.0033 | 10.256 | 56.19 | 3.95 |
| SPP (before) | Trace2 | 0.2512 | 1.0002 | 13.455 | 52.47 | 0.61 |
| SPP (before) | Trace3 | 0.3824 | 1.0008 | 3.368 | 25.86 | 1.04 |
| **SPP (final)** | Trace1 | **0.2345** | **1.0094** | **9.566** | **65.70** | **10.42** |
| **SPP (final)** | Trace2 | **0.2552** | **1.0161** | **12.812** | **70.38** | **5.36** |
| **SPP (final)** | Trace3 | **0.3903** | **1.0215** | **2.747** | **55.05** | **19.28** |

Geometric-mean speedup: ip_stride **1.0024**, old SPP **1.0014**, final SPP **1.0157**.

Other prefetch statistics for the final SPP:

| Trace | Requested | Issued to L2 | Useful | Useless | Late |
|---|---|---|---|---|---|
| Trace1 | 209,922 | 58,972 | 38,746 | 16,368 | 3,621 |
| Trace2 | 133,552 | 29,071 | 20,460 | 7,872 | 750 |
| Trace3 | 150,512 | 31,196 | 17,173 | 9,504 | 4,509 |

Prefetching also reduces the L2C and LLC load MPKI. For example, on Trace3 the
L2C data load MPKI goes from 2.830 to 2.024 and the LLC load MPKI from 3.144 to
2.394. The L1D *total* MPKI goes up slightly because ChampSim counts the
prefetch requests that miss in L1D as misses. That is expected and does not
affect demand loads.

## What was wrong with the starting SPP

Running the original SPP and reading its statistics showed four problems:

1. **Too few IPs tracked.** There were only 24 trackers, and each one carried a
   private 16-entry signature table. That made every tracker expensive and
   kept the number of tracked IPs small. The load-IP working set of these
   (server-like) traces is much larger than 24, so trackers were constantly
   evicted before they learned anything.
2. **Redundant requests.** On every access the whole window
   `cl+s … cl+d·s` was re-requested. About 90% of those requests were for
   lines already in L1D or already in flight (requested 227k vs. issued to L2
   21k on Trace1). They wasted PQ slots and L1D tag bandwidth.
3. **Fill to L2 when the MSHR was half full.** These prefetches count in the
   accuracy denominator (`pf_lower_level`) but can never be an L1D useful hit,
   so they only lower the measured accuracy.
4. The throttle thresholds were not tuned.

## Final design

### Structures

| Structure | Organisation | Purpose |
|---|---|---|
| IP table (IPT) | 64 sets × 4 ways, LRU, index = folded hash of the IP | per-load state |
| Pattern table (PT) | 2048 entries, direct mapped, index = hash(signature, IP) | signature → next stride |
| Recent-prefetch filter | 128 entries, direct mapped | drop redundant prefetches |
| Throttle | 2 epoch counters + degree register | accuracy-based degree |

**IPT entry**: partial IP tag, low 16 bits of the last line address (enough
for an in-page stride), the uniform stride and a 2-bit confidence, a 12-bit
signature `sig = (sig << 4) ^ stride` that compresses the last ~3 strides, a
history-length counter, and LRU bits.

**PT entry**: partial signature tag, next stride, 2-bit confidence with
hysteresis. When a stride mismatches, the confidence is decremented first and
the stride is replaced only when the confidence reaches 1.

### Algorithm (per demand load)

1. Look up or allocate the IPT entry and compute the stride from the last line.
   Stride 0 is ignored. If |stride| > 63 the access left the page region, so the
   pattern state is reset.
2. **Training.** The *old* signature is trained in the PT with the observed
   stride. The uniform predictor is updated (confidence counts consecutive
   repeats). The new stride is folded into the signature.
3. **Prediction.**
   * **Uniform first.** If the same stride was seen 3 times in a row
     (confidence ≥ 2), issue `degree` prefetches at `+s, +2s, …`.
   * **Otherwise fall back to non-uniform.** Look up the next stride for the
     current signature, compute the *speculative* next signature from it, and
     look up again, up to `degree` times. The real history is never modified by
     predictions. This captures repeating stride sequences like
     `(+1,+2,+2,+2,+3)^n`, because each window of the last strides maps uniquely
     to the next stride.
4. Every prefetch must stay in the page of the triggering access, must not hit
   in the recent-prefetch filter, and is filled into L1D. The walk stops when
   the PQ is full.

### Accuracy-based throttling

Every 256 prefetches issued to L2, accuracy = Δuseful / Δissued is computed for
that epoch, and the degree for the next epoch is set from it:

| Accuracy of last epoch | Degree |
|---|---|
| ≥ 70 % | 6 |
| 40 – 70 % | 3 |
| < 40 % | 1 |

* **Why these thresholds?** We swept them (see below). 70/40 gave 1–2 points
  higher accuracy than 60/30 at the same IPC, and 50/25 lowered accuracy with no
  IPC gain. At ≥ 70%, at least 2 of 3 prefetches are used, so running far
  ahead (degree 6) pays off and hides the latency of later accesses. Below 40%,
  most prefetches are pollution, so we keep only the next one (degree 1). We
  never go to degree 0, because the throttle needs prefetches to keep measuring
  accuracy and recover.
* **Why these degrees?** 8/4/2 gave slightly more coverage but 3–4 points lower
  accuracy. 4/2/1 gave the highest accuracy but lost coverage and IPC. 6/3/1 is
  the best balance.
* **Epoch length:** 128 behaved the same as 256, while 1024 reacted too slowly
  (Trace3 accuracy dropped to 49%).

The throttle histogram (low/mid/high epochs) is printed at the end of every run.
For example, on Trace2 there were 16 / 234 / 231 epochs, so the prefetcher spends
most of its time at degree 3–6.

## Storage overhead (exact bit-level breakdown)

| Structure | Field | Bits |
|---|---|---|
| IPT entry | valid | 1 |
| | IP tag | 8 |
| | last line address (low bits) | 16 |
| | uniform stride (−63..63) | 7 |
| | uniform confidence | 2 |
| | signature | 12 |
| | history length (0..3) | 2 |
| | LRU (4 ways) | 2 |
| | **total per entry** | **50** |
| IPT | 256 entries × 50 | **12,800** |
| PT entry | valid 1 + signature tag 6 + stride 7 + confidence 2 | **16** |
| PT | 2048 entries × 16 | **32,768** |
| Filter entry | valid 1 + line tag 16 | **17** |
| Filter | 128 entries × 17 | **2,176** |
| Throttle | issued-in-epoch 9 + useful-in-epoch 9 + degree 3 | **21** |
| **Total** | | **47,765 bits ≈ 5.83 KB** |

(The `used`/`path` bits stored in the filter entries in the code only feed the
statistics printed at the end. They are not part of the prefetcher.)

A cheaper option: with a 1024-entry PT the total is ≈ 3.8 KB, and the geomean
speedup drops only from 1.0157 to 1.0149.

## Design-space exploration (what we tried and what the data said)

All numbers are for the full 25M + 25M runs on all three traces. The sweeps were
done with a temporary copy of the prefetcher compiled with `SPP_TUNE`, which
reads every parameter from an environment variable. That hook is still in the
code for sensitivity studies.

### 1. Fixes applied to the original SPP one at a time

| Change | Geomean speedup | Acc T1/T2/T3 % | Cov T1/T2/T3 % |
|---|---|---|---|
| original SPP | 1.0014 | 56.2 / 52.5 / 25.9 | 3.9 / 0.6 / 1.0 |
| 16-bit IP hash instead of 8-bit mask | ≈ same | 55.8 / 52.2 / 26.0 | 3.9 / 0.6 / 1.0 |
| always fill L1 | ≈ +0.03% | 59.5 / 55.6 / 27.5 | 4.2 / 0.6 / 1.2 |
| 64 trackers | 1.0029 | 63.4 / 57.4 / 42.7 | 5.6 / 0.9 / 3.6 |
| 128 trackers | 1.0053 | 65.1 / 64.7 / 45.5 | 6.3 / 2.0 / 4.3 |
| 256 trackers | 1.0068 | 65.8 / 71.1 / 45.1 | 6.7 / 2.8 / 5.0 |

**Conclusion:** IP aliasing is not the problem. The *number of tracked IPs*
is. Per-tracker signature tables make that very expensive, which motivated the
shared pattern table.

### 2. New design (shared PT): main knobs

| Variant | Geomean speedup | Acc T1/T2/T3 % | Cov T1/T2/T3 % |
|---|---|---|---|
| PT 512, conf ≥ 2 | 1.0113 | 65.9 / 67.5 / 53.3 | 8.5 / 3.4 / 14.5 |
| PT 1024, conf ≥ 2 | 1.0122 | 66.0 / 69.8 / 53.5 | 8.7 / 4.0 / 15.3 |
| PT 2048, conf ≥ 2 | 1.0131 | 66.2 / 71.8 / 54.5 | 9.0 / 4.6 / 16.7 |
| PT 2048, conf ≥ 1 | 1.0157 | 64.0 / 68.7 / 53.8 | 10.8 / 5.5 / 20.5 |
| PT 4096, conf ≥ 1 | 1.0162 | 64.0 / 68.4 / 53.7 | 11.1 / 5.7 / 21.2 |
| PT not keyed by IP (patterns shared across IPs) | 1.0165 | 56.0 / 55.8 / 50.9 | 12.1 / 5.1 / 20.4 |
| + IP-agnostic fallback table | 1.0177 | 55.2 / 55.0 / 49.8 | 12.9 / 5.9 / 23.2 |
| uniform after 2 repeats instead of 3 | +0.1–0.3% | −1 to −6 pts | + coverage |
| fill L2 when MSHR half full | −0.01% | −1 to −2 pts | − |
| IPT 32×4 / 64×8 / 128×4 / 256×1 | 1.0113 / 1.0113 / 1.0115 / 1.0105 | ≈ same | ≈ same |
| no filter (vs 64-entry filter) | same IPC | same | same, but **5× more requests** |

### 3. Ideas that did not help (removed from the final code)

* **Per-IP accuracy checker.** Each IP had a usefulness score: credited when a
  demand hits a line it prefetched, penalised when its prefetch is overwritten
  unused. Inaccurate IPs were capped at degree 1 or suppressed, and recovered by
  verifying their predictions. Result: no change in accuracy or IPC (±0.1%).
  Instrumentation showed why: useless prefetches are spread over many IPs and
  over both prediction paths (uniform ~68% of issued lines demanded, pattern
  ~75%). There is no small set of "bad" IPs to filter out.
* **Higher confidence for deeper lookahead steps:** lower coverage, same accuracy.
* **Larger signatures (15 bits) or smaller (9 bits):** no gain.

## Conclusion

* The final SPP improves **accuracy** from 56 / 52 / 26 % (old SPP) and
  53 / 38 / 16 % (IP-stride) to **66 / 70 / 55 %**. At the same time,
  **coverage** goes up 2.6× / 9× / 19× compared with the old SPP, to
  10.4 / 5.4 / 19.3 %.
* **IPC** improves on every trace: speedups of 1.0094 / 1.0161 / 1.0215, geomean
  **1.0157**. That is about 6.5× the gain of IP-stride (1.0024) and 11× the gain
  of the old SPP (1.0014).
* The biggest single factor was tracking many more load IPs cheaply. A small
  per-IP entry with a 12-bit signature plus a shared IP-hashed pattern table
  replaced per-IP signature tables. The recent-prefetch filter removed about 80%
  of redundant prefetch requests at no cost. Always filling into L1D and tuning
  the throttle thresholds (70/40, degrees 6/3/1) raised accuracy further.
* Absolute speedups stay small because these traces are dominated by
  instruction misses and irregular data accesses: L2C instruction MPKI is larger
  than data MPKI on Traces 1 and 2, and branch MPKI is high. Stride-based data
  prefetching can only cover a limited part of the L1D load misses.
* There is a clear coverage-vs-accuracy trade-off. Sharing patterns across IPs
  gives up to 1.018 geomean speedup, but accuracy falls to about 55%. We chose
  the IP-keyed design because it improves *both* accuracy and IPC by a wide
  margin over the baselines, with about 5.8 KB of storage.
