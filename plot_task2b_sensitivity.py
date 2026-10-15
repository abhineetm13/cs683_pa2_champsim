#!/usr/bin/env python3
"""Plot Task 2b Dynamic I-RRIP threshold sensitivity results."""

import argparse
from pathlib import Path

from sensitivity_plot_common import generate_sensitivity


METRICS = {
    "ipc": {"title": "IPC sensitivity", "ylabel": "Instructions per cycle",
            "filename": "ipc_sensitivity.png", "tick": lambda x: f"{x:.4f}",
            "value": lambda x: f"{x:.4f}"},
    "speedup": {"title": "Speedup sensitivity", "ylabel": "Speedup over RRIP",
                "filename": "speedup_sensitivity.png", "tick": lambda x: f"{x:.4f}",
                "value": lambda x: f"{x:.4f}", "geomean": True},
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
    parser.add_argument("--input", type=Path, default=Path("outputs/task2b_summary.csv"))
    parser.add_argument("--low-input", type=Path,
                        default=Path("outputs/task2b_low_threshold_summary.csv"))
    parser.add_argument("--output", type=Path, default=Path("plots/task2b_sensitivity"))
    args = parser.parse_args()
    paths = generate_sensitivity([args.low_input, args.input], args.output,
                                 "Task 2b - Dynamic I-RRIP sensitivity",
                                 ["t2b_low_dyn_irrip_t", "t2b_dyn_irrip_t"],
                                 "rrip", METRICS)
    print(f"Generated {len(paths)} plots in {args.output}")
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
