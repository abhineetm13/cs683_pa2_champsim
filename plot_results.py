#!/usr/bin/env python3
"""Generate all plots required by CS683 PA2 from ChampSim output files.

The script expects files named ``<config>-Trace<N>.txt`` in the outputs
directory. It uses parse_stats.py to read the Region of Interest statistics.

Default report groups:
  Task 1:  no, ip_stride, spp
  Task 2a: no, rrip, irrip
  Task 2b: no, rrip, irrip, dyn_irrip
  Task 3:  no, spp, dyn_irrip, spp_dyn_irrip

Usage:
  python3 plot_results.py
  python3 plot_results.py --only task1 task3
  python3 plot_results.py --sensitivity-tags dyn_t10 dyn_t20 dyn_t30 dyn_t40 dyn_t50

Plots are written as PNG files below plots/<task>/ by default. Pillow is the
only plotting dependency; install it with ``python3 -m pip install Pillow`` if
it is not already available.
"""

import argparse
import math
import re
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:
    raise SystemExit("Pillow is required: python3 -m pip install Pillow") from exc

from parse_stats import parse


WIDTH = 1600
HEIGHT = 900
LEFT = 155
RIGHT = 55
TOP = 155
BOTTOM = 135

COLORS = [
    "#4C78A8",  # blue
    "#F58518",  # orange
    "#54A24B",  # green
    "#E45756",  # red
    "#72B7B2",  # cyan
    "#B279A2",  # purple
    "#FF9DA6",  # pink
]

LABELS = {
    "no": "Baseline (No PF + LRU)",
    "ip_stride": "IP Stride",
    "spp": "SPP",
    "rrip": "RRIP",
    "irrip": "I-RRIP",
    "dyn_irrip": "Dynamic I-RRIP",
    "spp_rrip": "SPP + RRIP",
    "spp_dyn_irrip": "SPP + Dynamic I-RRIP",
}

METRICS = {
    "ipc": {
        "title": "IPC",
        "ylabel": "Instructions per cycle",
        "filename": "ipc.png",
        "format": lambda x: f"{x:.4f}",
    },
    "speedup": {
        "title": "Speedup over baseline",
        "ylabel": "Speedup",
        "filename": "speedup.png",
        "format": lambda x: f"{x:.4f}",
        "reference": 1.0,
        "geomean": True,
    },
    "L1D_load_mpki": {
        "title": "L1D Load MPKI",
        "ylabel": "Misses per 1,000 instructions",
        "filename": "l1d_load_mpki.png",
        "format": lambda x: f"{x:.3f}",
    },
    "L2C_load_mpki": {
        "title": "L2C Load MPKI",
        "ylabel": "Misses per 1,000 instructions",
        "filename": "l2c_load_mpki.png",
        "format": lambda x: f"{x:.3f}",
    },
    "L2C_instr_load_mpki": {
        "title": "L2 Instruction Load MPKI",
        "ylabel": "Misses per 1,000 instructions",
        "filename": "l2_instruction_mpki.png",
        "format": lambda x: f"{x:.3f}",
    },
    "L2C_data_load_mpki": {
        "title": "L2 Data Load MPKI",
        "ylabel": "Misses per 1,000 instructions",
        "filename": "l2_data_mpki.png",
        "format": lambda x: f"{x:.3f}",
    },
    "pf_accuracy": {
        "title": "L1D Prefetch Accuracy",
        "ylabel": "Accuracy (%)",
        "filename": "prefetch_accuracy.png",
        "format": lambda x: f"{x:.1f}%",
        "percent": True,
    },
    "coverage": {
        "title": "L1D Prefetch Coverage",
        "ylabel": "Coverage (%)",
        "filename": "coverage.png",
        "format": lambda x: f"{x:.1f}%",
        "percent": True,
        "reference": 0.0,
    },
}

TASKS = {
    "task1": {
        "title": "Task 1 - Data Prefetching",
        "configs": ["no", "ip_stride", "spp"],
        "metrics": ["ipc", "speedup", "L1D_load_mpki", "pf_accuracy", "coverage"],
    },
    "task2a": {
        "title": "Task 2a - Instruction-Conscious L2 Replacement",
        "configs": ["no", "rrip", "irrip"],
        "metrics": ["ipc", "speedup", "L2C_load_mpki", "L2C_instr_load_mpki", "L2C_data_load_mpki"],
    },
    "task2b": {
        "title": "Task 2b - Dynamic I-RRIP",
        "configs": ["no", "rrip", "irrip", "dyn_irrip"],
        "metrics": ["ipc", "speedup", "L2C_load_mpki", "L2C_instr_load_mpki", "L2C_data_load_mpki"],
    },
    "task3": {
        "title": "Task 3 - SPP with Dynamic I-RRIP",
        "configs": ["no", "spp", "dyn_irrip", "spp_dyn_irrip"],
        "metrics": [
            "ipc", "speedup", "pf_accuracy", "coverage", "L1D_load_mpki",
            "L2C_load_mpki", "L2C_instr_load_mpki", "L2C_data_load_mpki",
        ],
    },
}


def load_font(size, bold=False):
    names = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"]
        if bold else
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]
    )
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


FONT_TITLE = load_font(34, bold=True)
FONT_SUBTITLE = load_font(23, bold=True)
FONT_AXIS = load_font(21)
FONT_TICK = load_font(18)
FONT_VALUE = load_font(15, bold=True)
FONT_LEGEND = load_font(18)


def text_size(draw, text, font):
    box = draw.textbbox((0, 0), str(text), font=font)
    return box[2] - box[0], box[3] - box[1]


def centered_text(draw, xy, text, font, fill="#202124"):
    width, height = text_size(draw, text, font)
    draw.text((xy[0] - width / 2, xy[1] - height / 2), text, font=font, fill=fill)


def rotated_ylabel(image, text):
    canvas = Image.new("RGBA", (500, 55), (255, 255, 255, 0))
    draw = ImageDraw.Draw(canvas)
    width, height = text_size(draw, text, FONT_AXIS)
    draw.text(((500 - width) / 2, (55 - height) / 2), text, font=FONT_AXIS, fill="#202124")
    rotated = canvas.rotate(90, expand=True)
    image.alpha_composite(rotated, (22, (HEIGHT - rotated.height) // 2))


def trace_number(name):
    match = re.search(r"(\d+)$", name)
    return int(match.group(1)) if match else 10**9


def discover_traces(outputs_dir):
    traces = set()
    for path in outputs_dir.glob("*-Trace*.txt"):
        match = re.search(r"-(Trace\d+)\.txt$", path.name)
        if match:
            traces.add(match.group(1))
    return sorted(traces, key=trace_number)


def read_results(outputs_dir, configs, traces, baseline="no"):
    data = {}
    for config in configs:
        for trace in traces:
            path = outputs_dir / f"{config}-{trace}.txt"
            if not path.exists():
                print(f"warning: missing {path}", file=sys.stderr)
                continue
            result = parse(str(path))
            if result is None:
                print(f"warning: no ROI statistics in {path}", file=sys.stderr)
                continue
            data[(config, trace)] = result

    for trace in traces:
        base = data.get((baseline, trace))
        if base is None:
            continue
        for config in configs:
            result = data.get((config, trace))
            if result is None:
                continue
            result["speedup"] = result["ipc"] / base["ipc"]
            misses = base["L1D_load_miss"]
            result["coverage"] = (
                100.0 * (misses - result["L1D_load_miss"]) / misses
                if misses else float("nan")
            )
    return data


def finite_values(values):
    return [value for value in values if value is not None and math.isfinite(value)]


def geomean(values):
    values = [value for value in finite_values(values) if value > 0]
    if not values:
        return float("nan")
    return math.exp(sum(math.log(value) for value in values) / len(values))


def nice_upper(value):
    if value <= 0:
        return 1.0
    exponent = math.floor(math.log10(value))
    fraction = value / (10 ** exponent)
    for nice in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if fraction <= nice:
            return nice * (10 ** exponent)
    return 10 ** (exponent + 1)


def axis_range(metric, values):
    values = finite_values(values)
    if metric == "pf_accuracy":
        return 0.0, 100.0
    if metric == "coverage":
        minimum = min([0.0] + values)
        maximum = max([0.0] + values)
        span = max(maximum - minimum, 1.0)
        return min(0.0, minimum - 0.12 * span), max(1.0, maximum + 0.18 * span)
    maximum = max(values, default=1.0)
    return 0.0, nice_upper(maximum * 1.18)


def draw_legend(draw, configs):
    columns = min(len(configs), 4)
    cell_width = (WIDTH - LEFT - RIGHT) / columns
    rows = math.ceil(len(configs) / columns)
    start_y = 83 if rows == 1 else 72
    for i, config in enumerate(configs):
        row, column = divmod(i, columns)
        x = LEFT + column * cell_width
        y = start_y + row * 31
        draw.rounded_rectangle((x, y, x + 23, y + 18), radius=3,
                               fill=COLORS[i % len(COLORS)])
        draw.text((x + 32, y - 2), LABELS.get(config, config.replace("_", " ")),
                  font=FONT_LEGEND, fill="#202124")


def plot_metric(task_name, task, metric, data, traces, output_dir):
    spec = METRICS[metric]
    configs = task["configs"]
    categories = list(traces)

    values = {
        config: [data.get((config, trace), {}).get(metric, float("nan"))
                 for trace in traces]
        for config in configs
    }
    if spec.get("geomean"):
        categories.append("Geomean")
        for config in configs:
            values[config].append(geomean(values[config]))

    all_values = [value for config in configs for value in values[config]]
    ymin, ymax = axis_range(metric, all_values)

    image = Image.new("RGBA", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(image)

    centered_text(draw, (WIDTH / 2, 35), spec["title"], FONT_TITLE)
    centered_text(draw, (WIDTH / 2, 68), task["title"], FONT_SUBTITLE, "#4A4A4A")
    draw_legend(draw, configs)

    plot_left, plot_right = LEFT, WIDTH - RIGHT
    plot_top, plot_bottom = TOP, HEIGHT - BOTTOM
    plot_width = plot_right - plot_left
    plot_height = plot_bottom - plot_top

    def ycoord(value):
        return plot_bottom - (value - ymin) * plot_height / (ymax - ymin)

    # Grid and y-axis tick labels.
    ticks = 5
    for i in range(ticks + 1):
        value = ymin + i * (ymax - ymin) / ticks
        y = ycoord(value)
        draw.line((plot_left, y, plot_right, y), fill="#DADCE0", width=2)
        label = f"{value:.0f}" if spec.get("percent") else f"{value:.3g}"
        tw, th = text_size(draw, label, FONT_TICK)
        draw.text((plot_left - tw - 13, y - th / 2), label, font=FONT_TICK, fill="#4A4A4A")

    draw.line((plot_left, plot_top, plot_left, plot_bottom), fill="#202124", width=3)
    draw.line((plot_left, plot_bottom, plot_right, plot_bottom), fill="#202124", width=3)

    if ymin <= 0 <= ymax:
        draw.line((plot_left, ycoord(0), plot_right, ycoord(0)), fill="#202124", width=2)
    if "reference" in spec and ymin <= spec["reference"] <= ymax:
        y = ycoord(spec["reference"])
        for x in range(plot_left, plot_right, 18):
            draw.line((x, y, min(x + 10, plot_right), y), fill="#6B7280", width=3)

    group_width = plot_width / max(len(categories), 1)
    usable_width = group_width * 0.78
    bar_width = min(82, usable_width / max(len(configs), 1))
    zero_y = ycoord(0)

    for group_index, category in enumerate(categories):
        center = plot_left + (group_index + 0.5) * group_width
        group_start = center - bar_width * len(configs) / 2
        for config_index, config in enumerate(configs):
            value = values[config][group_index]
            if not math.isfinite(value):
                continue
            x0 = group_start + config_index * bar_width + 3
            x1 = group_start + (config_index + 1) * bar_width - 3
            value_y = ycoord(value)
            top, bottom = min(zero_y, value_y), max(zero_y, value_y)
            if bottom - top < 2:
                top = bottom - 2
            draw.rectangle((x0, top, x1, bottom), fill=COLORS[config_index % len(COLORS)])

            label = spec["format"](value)
            tw, th = text_size(draw, label, FONT_VALUE)
            label_y = top - th - 6 if value >= 0 else bottom + 5
            draw.text(((x0 + x1 - tw) / 2, label_y), label, font=FONT_VALUE, fill="#202124")

        centered_text(draw, (center, plot_bottom + 31), category, FONT_AXIS)

    centered_text(draw, ((plot_left + plot_right) / 2, HEIGHT - 43), "Benchmark trace", FONT_AXIS)
    rotated_ylabel(image, spec["ylabel"])

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / spec["filename"]
    image.convert("RGB").save(path, quality=95)
    return path


def generate_task(task_name, task, outputs_dir, plots_dir, traces):
    data = read_results(outputs_dir, task["configs"], traces)
    for config in task["configs"]:
        if not config.startswith("spp"):
            continue
        issued = [data[(config, trace)]["pf_issued"]
                  for trace in traces if (config, trace) in data]
        if issued and not any(issued):
            print(f"warning: {config} issued zero L1D prefetches in every trace; "
                  "check that the intended SPP binary was built and run",
                  file=sys.stderr)
    written = []
    for metric in task["metrics"]:
        written.append(plot_metric(task_name, task, metric, data, traces,
                                   plots_dir / task_name))
    return written


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs", type=Path, default=Path("outputs"),
                        help="directory containing <config>-Trace<N>.txt files")
    parser.add_argument("--plot-dir", type=Path, default=Path("plots"),
                        help="directory in which plots are written")
    parser.add_argument("--only", nargs="+", choices=sorted(TASKS),
                        help="generate only the selected task groups")
    parser.add_argument("--sensitivity-tags", nargs="+", metavar="TAG",
                        help="five or more dynamic I-RRIP sensitivity configuration tags")
    args = parser.parse_args()

    traces = discover_traces(args.outputs)
    if not traces:
        raise SystemExit(f"No <config>-Trace<N>.txt files found in {args.outputs}")

    selected = args.only or list(TASKS)
    written = []
    for task_name in selected:
        written.extend(generate_task(task_name, TASKS[task_name], args.outputs,
                                     args.plot_dir, traces))

    if args.sensitivity_tags:
        configs = ["no"] + [tag for tag in args.sensitivity_tags if tag != "no"]
        sensitivity = {
            "title": "Task 2b - Parameter Sensitivity",
            "configs": configs,
            "metrics": list(TASKS["task2b"]["metrics"]),
        }
        written.extend(generate_task("task2b_sensitivity", sensitivity,
                                     args.outputs, args.plot_dir, traces))

    print(f"Generated {len(written)} plots in {args.plot_dir}")
    for path in written:
        print(path)


if __name__ == "__main__":
    main()
