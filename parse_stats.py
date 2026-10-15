#!/usr/bin/env python3
"""Parse ChampSim ROI statistics into one table.

Usage: parse_stats.py <outputs_dir> <baseline_tag> <tag1> [tag2 ...]

Expects files named <outputs_dir>/<tag>-Trace<N>.txt. Writes a CSV named by
$SUMMARY_CSV (default: summary.csv) and prints a table per metric group.
Speedup and L1D coverage are computed against <baseline_tag>.
"""
import csv
import glob
import os
import re
import sys

NUM = r"([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?|-?nan|inf)"


def fnum(s):
    try:
        return float(s)
    except ValueError:
        return float("nan")


def cache_line(text, cache, kind):
    """Return (access, hit, miss, mpki) for e.g. ('L1D', 'LOAD')."""
    m = re.search(rf"^{cache} {kind}\s+ACCESS:\s+(\d+)\s+HIT:\s+(\d+)\s+MISS:\s+(\d+).*?MPKI:\s+{NUM}",
                  text, re.M)
    if not m:
        return (0, 0, 0, float("nan"))
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), fnum(m.group(4))


def parse(path):
    with open(path) as f:
        text = f.read()
    # Only look at the Region of Interest section.
    roi = text.split("Region of Interest Statistics", 1)
    if len(roi) < 2:
        return None
    text = roi[1]
    d = {}
    m = re.search(rf"CPU 0 cumulative IPC:\s+{NUM}\s+instructions:\s+(\d+)\s+cycles:\s+(\d+)", text)
    d["ipc"] = fnum(m.group(1))
    d["instrs"] = int(m.group(2))
    d["cycles"] = int(m.group(3))

    for cache in ("L1D", "L2C", "LLC"):
        a, h, mi, mpki = cache_line(text, cache, "LOAD")
        d[f"{cache}_load_access"] = a
        d[f"{cache}_load_miss"] = mi
        d[f"{cache}_load_mpki"] = mpki
        d[f"{cache}_total_mpki"] = cache_line(text, cache, "TOTAL")[3]

    m = re.search(rf"^L2C DATA LOAD MPKI:\s+{NUM}", text, re.M)
    d["L2C_data_load_mpki"] = fnum(m.group(1)) if m else float("nan")
    m = re.search(rf"^L2C INSTRUCTION LOAD MPKI:\s+{NUM}", text, re.M)
    d["L2C_instr_load_mpki"] = fnum(m.group(1)) if m else float("nan")

    m = re.search(r"^L1D PREFETCH\s+REQUESTED:\s+(\d+)\s+ISSUED:\s+(\d+)\s+USEFUL:\s+(\d+)\s+USELESS:\s+(\d+)",
                  text, re.M)
    d["pf_requested"], d["pf_issued"], d["pf_useful"], d["pf_useless"] = map(int, m.groups())
    m = re.search(r"^L1D USEFUL LOAD PREFETCHES:\s+(\d+) PREFETCH ISSUED TO LOWER LEVEL:\s+(\d+)", text, re.M)
    d["pf_to_lower"] = int(m.group(2))
    m = re.search(r"^L1D TIMELY PREFETCHES:\s+(\d+) LATE PREFETCHES:\s+(\d+) DROPPED PREFETCHES:\s+(\d+)",
                  text, re.M)
    d["pf_late"], d["pf_dropped"] = int(m.group(2)), int(m.group(3))
    # Same definition ChampSim prints: useful / issued to lower level.
    d["pf_accuracy"] = 100.0 * d["pf_useful"] / d["pf_to_lower"] if d["pf_to_lower"] else float("nan")
    m = re.search(rf"^L1D AVERAGE MISS LATENCY:\s+{NUM}", text, re.M)
    d["L1D_miss_lat"] = fnum(m.group(1)) if m else float("nan")
    m = re.search(rf"Branch Prediction Accuracy:\s+{NUM}%\s+MPKI:\s+{NUM}", text)
    d["branch_mpki"] = fnum(m.group(2)) if m else float("nan")
    return d


def main():
    out_dir, base_tag, tags = sys.argv[1], sys.argv[2], sys.argv[3:]
    all_tags = [base_tag] + [t for t in tags if t != base_tag]
    traces = sorted({re.search(r"-(Trace\d+)\.txt$", p).group(1)
                     for p in glob.glob(os.path.join(out_dir, "*-Trace*.txt"))},
                    key=lambda s: int(s[5:]))
    rows = []
    data = {}
    for tag in all_tags:
        for tr in traces:
            p = os.path.join(out_dir, f"{tag}-{tr}.txt")
            if os.path.exists(p):
                d = parse(p)
                if d:
                    data[(tag, tr)] = d

    for tag in all_tags:
        for tr in traces:
            d = data.get((tag, tr))
            if d is None:
                continue
            b = data.get((base_tag, tr))
            d["speedup"] = d["ipc"] / b["ipc"] if b else float("nan")
            if b and b["L1D_load_miss"]:
                d["coverage"] = 100.0 * (b["L1D_load_miss"] - d["L1D_load_miss"]) / b["L1D_load_miss"]
            else:
                d["coverage"] = float("nan")
            rows.append({"config": tag, "trace": tr, **d})

    if not rows:
        print("No results parsed.")
        return

    # Geomean speedup per config.
    import math
    geo = {}
    for tag in all_tags:
        s = [r["speedup"] for r in rows if r["config"] == tag and r["speedup"] == r["speedup"]]
        if s:
            geo[tag] = math.exp(sum(math.log(x) for x in s) / len(s))

    cols = list(rows[0].keys())
    summary_name = os.environ.get("SUMMARY_CSV", "summary.csv")
    summary_path = os.path.join(out_dir, summary_name)
    with open(summary_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    groups = [
        ("Performance", [("ipc", "IPC", ".4f"), ("speedup", "Speedup", ".4f"),
                         ("branch_mpki", "BrMPKI", ".2f")]),
        ("L1D prefetch", [("pf_requested", "Requested", "d"), ("pf_issued", "Issued", "d"),
                          ("pf_to_lower", "ToLower", "d"), ("pf_useful", "Useful", "d"),
                          ("pf_useless", "Useless", "d"), ("pf_late", "Late", "d"),
                          ("pf_accuracy", "Acc%", ".2f"), ("coverage", "Cov%", ".2f")]),
        ("Cache MPKI", [("L1D_load_mpki", "L1D-LD", ".3f"), ("L1D_total_mpki", "L1D-TOT", ".3f"),
                        ("L2C_load_mpki", "L2C-LD", ".3f"), ("L2C_data_load_mpki", "L2C-D", ".3f"),
                        ("L2C_instr_load_mpki", "L2C-I", ".3f"), ("LLC_load_mpki", "LLC-LD", ".3f")]),
    ]
    for title, metrics in groups:
        print(f"\n== {title} ==")
        hdr = f"{'config':<22}{'trace':<8}" + "".join(f"{name:>11}" for _, name, _ in metrics)
        print(hdr)
        print("-" * len(hdr))
        for r in rows:
            line = f"{r['config']:<22}{r['trace']:<8}"
            for key, _, fmt in metrics:
                v = r[key]
                line += f"{format(v, fmt):>11}" if fmt != "d" else f"{v:>11d}"
            print(line)
    print("\n== Geomean speedup ==")
    for tag, g in geo.items():
        print(f"{tag:<22}{g:.4f}")
    print(f"\nCSV written to {summary_path}")


if __name__ == "__main__":
    main()
