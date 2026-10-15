#!/usr/bin/env python3
"""Plot Task 3 SPP + Dynamic I-RRIP threshold sensitivity results."""

import argparse
from pathlib import Path

from sensitivity_plot_common import generate_sensitivity


METRICS = {
    "ipc": {"title": "IPC sensitivity", "ylabel": "Instructions per cycle",
            "filename": "ipc_sensitivity.png", "tick": lambda x: f"{x:.4f}",
            "value": lambda x: f"{x:.4f}"},
    "speedup": {"title": "Speedup sensitivity", "ylabel": "Speedup over no-prefetch LRU",
                "filename": "speedup_sensitivity.png", "tick": lambda x: f"{x:.4f}",
                "value": lambda x: f"{x:.4f}", "geomean": True},
    "pf_accuracy": {"title": "L1D prefetch accuracy sensitivity", "ylabel": "Accuracy (%)",
                    "filename": "prefetch_accuracy_sensitivity.png",
                    "tick": lambda x: f"{x:.1f}", "value": lambda x: f"{x:.1f}%"},
    "coverage": {"title": "L1D prefetch coverage sensitivity", "ylabel": "Coverage (%)",
                 "filename": "coverage_sensitivity.png",
                 "tick": lambda x: f"{x:.1f}", "value": lambda x: f"{x:.1f}%"},
    "L1D_load_mpki": {"title": "L1D load MPKI sensitivity",
                       "ylabel": "Misses per 1,000 instructions",
                       "filename": "l1d_load_mpki_sensitivity.png",
                       "tick": lambda x: f"{x:.2f}", "value": lambda x: f"{x:.3f}"},
    "L2C_load_mpki": {"title": "L2C load MPKI sensitivity",
                       "ylabel": "Misses per 1,000 instructions",
                       "filename": "l2c_load_mpki_sensitivity.png",
                       "tick": lambda x: f"{x:.2f}", "value": lambda x: f"{x:.3f}"},
    "L2C_instr_load_mpki": {"title": "L2 instruction MPKI sensitivity",
                             "ylabel": "Misses per 1,000 instructions",
                             "filename": "l2_instruction_mpki_sensitivity.png",
                             "tick": lambda x: f"{x:.2f}", "value": lambda x: f"{x:.3f}"},
    "L2C_data_load_mpki": {"title": "L2 data MPKI sensitivity",
                            "ylabel": "Misses per 1,000 instructions",
                            "filename": "l2_data_mpki_sensitivity.png",
                            "tick": lambda x: f"{x:.2f}", "value": lambda x: f"{x:.3f}"},
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,
                        default=Path("outputs/task3_threshold_summary.csv"))
    parser.add_argument("--output", type=Path, default=Path("plots/task3_sensitivity"))
    args = parser.parse_args()
    paths = generate_sensitivity(args.input, args.output,
                                 "Task 3 - SPP + Dynamic I-RRIP sensitivity",
                                 "t3_spp_dyn_irrip_t", "spp", METRICS)
    print(f"Generated {len(paths)} plots in {args.output}")
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
