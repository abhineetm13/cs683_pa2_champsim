#!/usr/bin/env python3
"""Shared Pillow-based line plotting for threshold sensitivity CSV files."""

import csv
import math
import re
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:
    raise SystemExit("Pillow is required: python3 -m pip install Pillow") from exc


WIDTH, HEIGHT = 1600, 900
LEFT, RIGHT, TOP, BOTTOM = 175, 70, 145, 135
COLORS = ["#4C78A8", "#F58518", "#54A24B", "#7A5195"]


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
FONT_SUBTITLE = load_font(22)
FONT_AXIS = load_font(21)
FONT_TICK = load_font(18)
FONT_LEGEND = load_font(18)
FONT_VALUE = load_font(15, bold=True)


def text_size(draw, text, font):
    box = draw.textbbox((0, 0), str(text), font=font)
    return box[2] - box[0], box[3] - box[1]


def centered_text(draw, xy, text, font, fill="#202124"):
    width, height = text_size(draw, text, font)
    draw.text((xy[0] - width / 2, xy[1] - height / 2), text,
              font=font, fill=fill)


def dashed_line(draw, xy, fill, width=2, dash=12, gap=8):
    x0, y0, x1, y1 = xy
    if abs(y1 - y0) < 1:
        x = x0
        while x < x1:
            draw.line((x, y0, min(x + dash, x1), y1), fill=fill, width=width)
            x += dash + gap
    else:
        draw.line(xy, fill=fill, width=width)


def finite(values):
    return [value for value in values if math.isfinite(value)]


def mean(values):
    values = finite(values)
    return sum(values) / len(values) if values else float("nan")


def geomean(values):
    values = [value for value in finite(values) if value > 0]
    return math.exp(sum(math.log(value) for value in values) / len(values)) \
        if values else float("nan")


def read_csv(path):
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        for key, value in list(row.items()):
            if key in ("config", "trace"):
                continue
            try:
                row[key] = float(value)
            except (TypeError, ValueError):
                row[key] = float("nan")
    return rows


def threshold_rows(rows, tag_prefix):
    prefixes = [tag_prefix] if isinstance(tag_prefix, str) else tag_prefix
    patterns = [re.compile(rf"^{re.escape(prefix)}(\d+)$")
                for prefix in prefixes]
    found = {}
    for row in rows:
        match = next((pattern.match(row["config"]) for pattern in patterns
                      if pattern.match(row["config"])), None)
        if match:
            threshold = int(match.group(1)) / 100.0
            found[(threshold, row["trace"])] = row
    thresholds = sorted({key[0] for key in found})
    traces = sorted({key[1] for key in found},
                    key=lambda value: int(re.search(r"\d+", value).group()))
    if not thresholds:
        raise SystemExit(f"No configurations matching {prefixes}<digits> in CSV")
    return found, thresholds, traces


def axis_bounds(values, baseline):
    values = finite(values + [baseline])
    low, high = min(values), max(values)
    span = high - low
    if span == 0:
        span = max(abs(high) * 0.04, 0.01)
    return low - 0.18 * span, high + 0.22 * span


def draw_ylabel(image, text):
    canvas = Image.new("RGBA", (560, 55), (255, 255, 255, 0))
    draw = ImageDraw.Draw(canvas)
    centered_text(draw, (280, 27), text, FONT_AXIS)
    rotated = canvas.rotate(90, expand=True)
    image.alpha_composite(rotated, (25, (HEIGHT - rotated.height) // 2))


def plot_metric(rows, found, thresholds, traces, metric, spec, title,
                baseline_config, output_path):
    series = {
        trace: [found[(threshold, trace)][metric] for threshold in thresholds]
        for trace in traces
    }
    aggregate_fn = geomean if spec.get("geomean") else mean
    aggregate = [aggregate_fn([series[trace][i] for trace in traces])
                 for i in range(len(thresholds))]

    baseline_values = [row[metric] for row in rows
                       if row["config"] == baseline_config]
    baseline = aggregate_fn(baseline_values)
    all_values = [value for values in series.values() for value in values]
    all_values += aggregate
    ymin, ymax = axis_bounds(all_values, baseline)

    image = Image.new("RGBA", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    centered_text(draw, (WIDTH / 2, 35), spec["title"], FONT_TITLE)
    centered_text(draw, (WIDTH / 2, 73), title, FONT_SUBTITLE, "#4A4A4A")

    plot_left, plot_right = LEFT, WIDTH - RIGHT
    plot_top, plot_bottom = TOP, HEIGHT - BOTTOM
    plot_width = plot_right - plot_left
    plot_height = plot_bottom - plot_top

    def xcoord(index):
        if len(thresholds) == 1:
            return (plot_left + plot_right) / 2
        return plot_left + index * plot_width / (len(thresholds) - 1)

    def ycoord(value):
        return plot_bottom - (value - ymin) * plot_height / (ymax - ymin)

    for tick in range(6):
        value = ymin + tick * (ymax - ymin) / 5
        y = ycoord(value)
        draw.line((plot_left, y, plot_right, y), fill="#DADCE0", width=2)
        label = spec["tick"](value)
        tw, th = text_size(draw, label, FONT_TICK)
        draw.text((plot_left - tw - 14, y - th / 2), label,
                  font=FONT_TICK, fill="#4A4A4A")

    draw.line((plot_left, plot_top, plot_left, plot_bottom), fill="#202124", width=3)
    draw.line((plot_left, plot_bottom, plot_right, plot_bottom), fill="#202124", width=3)

    if math.isfinite(baseline):
        dashed_line(draw, (plot_left, ycoord(baseline), plot_right, ycoord(baseline)),
                    "#6B7280", width=3)

    plotted = []
    for index, trace in enumerate(traces):
        plotted.append((trace, series[trace], COLORS[index % len(COLORS)], 4))
    plotted.append(("Aggregate", aggregate, "#111827", 6))

    for label, values, color, width in plotted:
        points = [(xcoord(i), ycoord(value)) for i, value in enumerate(values)]
        draw.line(points, fill=color, width=width, joint="curve")
        radius = 7 if label == "Aggregate" else 6
        for x, y in points:
            draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                         fill=color, outline="white", width=2)

    for i, threshold in enumerate(thresholds):
        x = xcoord(i)
        label = f"{threshold:.2f}"
        tw, _ = text_size(draw, label, FONT_TICK)
        draw.text((x - tw / 2, plot_bottom + 18), label,
                  font=FONT_TICK, fill="#202124")
        value_label = spec["value"](aggregate[i])
        tw, th = text_size(draw, value_label, FONT_VALUE)
        draw.text((x - tw / 2, ycoord(aggregate[i]) - th - 12), value_label,
                  font=FONT_VALUE, fill="#111827")

    legend_items = [(trace, COLORS[i % len(COLORS)]) for i, trace in enumerate(traces)]
    legend_items += [("Aggregate", "#111827"),
                     (f"{baseline_config} aggregate", "#6B7280")]
    total_width = sum(text_size(draw, label, FONT_LEGEND)[0] + 58
                      for label, _ in legend_items)
    x = max(LEFT, (WIDTH - total_width) / 2)
    for label, color in legend_items:
        y = 105
        if label.endswith("aggregate") and label != "Aggregate":
            dashed_line(draw, (x, y + 9, x + 30, y + 9), color, width=3)
        else:
            draw.line((x, y + 9, x + 30, y + 9), fill=color, width=5)
            draw.ellipse((x + 10, y + 3, x + 22, y + 15), fill=color)
        draw.text((x + 38, y), label, font=FONT_LEGEND, fill="#202124")
        x += text_size(draw, label, FONT_LEGEND)[0] + 58

    centered_text(draw, ((plot_left + plot_right) / 2, HEIGHT - 48),
                  "Dynamic I-RRIP threshold", FONT_AXIS)
    draw_ylabel(image, spec["ylabel"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(output_path, quality=95)


def generate_sensitivity(csv_path, output_dir, title, tag_prefix,
                         baseline_config, metrics):
    csv_paths = csv_path if isinstance(csv_path, (list, tuple)) else [csv_path]
    rows = []
    for path in csv_paths:
        rows.extend(read_csv(Path(path)))
    found, thresholds, traces = threshold_rows(rows, tag_prefix)
    written = []
    for metric, spec in metrics.items():
        path = Path(output_dir) / spec["filename"]
        plot_metric(rows, found, thresholds, traces, metric, spec, title,
                    baseline_config, path)
        written.append(path)
    return written
