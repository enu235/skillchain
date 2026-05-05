#!/usr/bin/env python3
"""Deterministic chart renderer for the research pipeline.

Reads a JSON spec on stdin, writes a PNG to argv[1].

Spec shape:
{
  "title": "string",
  "chart_type": "bar | line | pie | scatter",
  "x_label": "string",
  "y_label": "string",
  "series": [
    {"name": "string, optional", "x": [...], "y": [...]}
  ]
}

Exit codes:
  0  success, PNG written
  1  malformed spec
  2  unsupported chart_type
  3  rendering failure
"""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ACCENT = "#1C7293"
SECONDARY = "#065A82"
TERTIARY = "#21295C"
PALETTE = [ACCENT, SECONDARY, TERTIARY, "#84B59F", "#B85042", "#6D2E46"]


def fail(code, msg):
    sys.stderr.write(msg.rstrip() + "\n")
    sys.exit(code)


def setup_axes(ax, title, x_label, y_label, show_grid):
    ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
    ax.set_xlabel(x_label, fontsize=10)
    ax.set_ylabel(y_label, fontsize=10)
    if show_grid:
        ax.grid(True, axis="y", alpha=0.3, linewidth=0.6)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def render_bar(spec, output_path):
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    series_list = spec["series"]
    if not series_list:
        fail(1, "bar chart requires at least one series")

    if len(series_list) == 1:
        series = series_list[0]
        ax.bar(range(len(series["x"])), series["y"], color=ACCENT, edgecolor="none")
        ax.set_xticks(range(len(series["x"])))
        ax.set_xticklabels([str(x) for x in series["x"]], rotation=20, ha="right")
    else:
        n = len(series_list[0]["x"])
        width = 0.8 / len(series_list)
        for idx, series in enumerate(series_list):
            offsets = [i + idx * width - 0.4 + width / 2 for i in range(n)]
            ax.bar(offsets, series["y"], width=width,
                   color=PALETTE[idx % len(PALETTE)],
                   label=series.get("name", f"series {idx + 1}"),
                   edgecolor="none")
        ax.set_xticks(range(n))
        ax.set_xticklabels([str(x) for x in series_list[0]["x"]], rotation=20, ha="right")
        ax.legend(frameon=False, fontsize=9)

    setup_axes(ax, spec.get("title", ""), spec.get("x_label", ""), spec.get("y_label", ""), True)
    fig.tight_layout()
    fig.savefig(output_path, format="png", bbox_inches="tight")
    plt.close(fig)


def render_line(spec, output_path):
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    series_list = spec["series"]
    if not series_list:
        fail(1, "line chart requires at least one series")
    for idx, series in enumerate(series_list):
        ax.plot(series["x"], series["y"],
                color=PALETTE[idx % len(PALETTE)],
                linewidth=2.0,
                marker="o", markersize=4,
                label=series.get("name", f"series {idx + 1}"))
    if len(series_list) > 1 or series_list[0].get("name"):
        ax.legend(frameon=False, fontsize=9)
    setup_axes(ax, spec.get("title", ""), spec.get("x_label", ""), spec.get("y_label", ""), True)
    fig.tight_layout()
    fig.savefig(output_path, format="png", bbox_inches="tight")
    plt.close(fig)


def render_pie(spec, output_path):
    fig, ax = plt.subplots(figsize=(7, 5), dpi=150)
    series_list = spec["series"]
    if not series_list:
        fail(1, "pie chart requires a single series")
    series = series_list[0]
    labels = [str(x) for x in series["x"]]
    values = series["y"]
    if not values or sum(values) <= 0:
        fail(1, "pie chart requires positive values")
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(values))]
    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        colors=colors,
        autopct="%1.1f%%",
        pctdistance=0.78,
        startangle=90,
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
        textprops={"fontsize": 9},
    )
    for t in autotexts:
        t.set_color("white")
        t.set_fontweight("bold")
    ax.set_title(spec.get("title", ""), fontsize=14, fontweight="bold", pad=12)
    fig.tight_layout()
    fig.savefig(output_path, format="png", bbox_inches="tight")
    plt.close(fig)


def render_scatter(spec, output_path):
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    series_list = spec["series"]
    if not series_list:
        fail(1, "scatter chart requires at least one series")
    for idx, series in enumerate(series_list):
        ax.scatter(series["x"], series["y"],
                   color=PALETTE[idx % len(PALETTE)],
                   alpha=0.75, s=40, edgecolors="white",
                   label=series.get("name", f"series {idx + 1}"))
    if len(series_list) > 1 or series_list[0].get("name"):
        ax.legend(frameon=False, fontsize=9)
    setup_axes(ax, spec.get("title", ""), spec.get("x_label", ""), spec.get("y_label", ""), True)
    fig.tight_layout()
    fig.savefig(output_path, format="png", bbox_inches="tight")
    plt.close(fig)


RENDERERS = {
    "bar": render_bar,
    "line": render_line,
    "pie": render_pie,
    "scatter": render_scatter,
}


def main():
    if len(sys.argv) != 2:
        fail(1, "usage: render_chart.py <output_path>  (spec JSON on stdin)")
    output_path = Path(sys.argv[1])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        spec = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        fail(1, f"malformed spec JSON: {e}")

    chart_type = spec.get("chart_type")
    if chart_type not in RENDERERS:
        fail(2, f"unsupported chart_type: {chart_type!r}")

    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Helvetica", "Arial", "DejaVu Sans"]

    try:
        RENDERERS[chart_type](spec, str(output_path))
    except Exception as e:
        fail(3, f"render failed: {e}")


if __name__ == "__main__":
    main()
