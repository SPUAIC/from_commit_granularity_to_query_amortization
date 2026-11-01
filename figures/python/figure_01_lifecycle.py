from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

from figure_common import configure_style, save_figure


def box(ax, x, y, w, h, text, face="#F7F7F7", edge="#333333", size=8.2):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.012",
        linewidth=1.0,
        facecolor=face,
        edgecolor=edge,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size)
    return patch


def arrow(ax, x1, y1, x2, y2):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle="-|>",
            mutation_scale=11,
            linewidth=1.0,
            color="#404040",
        )
    )


def span(ax, x1, x2, y, text, color="#4D4D4D", level=0):
    yy = y - 0.035 * level
    ax.plot([x1, x1, x2, x2], [yy + 0.012, yy, yy, yy + 0.012], color=color, lw=1.2)
    ax.text((x1 + x2) / 2, yy - 0.014, text, color=color, ha="center", va="top", fontsize=7.4)


def main() -> None:
    configure_style()
    fig, ax = plt.subplots(figsize=(13.0, 6.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    xs = [0.025, 0.17, 0.315, 0.46, 0.61, 0.745, 0.88]
    widths = [0.105, 0.115, 0.115, 0.115, 0.105, 0.105, 0.105]
    labels = [
        "TPC-DS\nstore_sales\nin Kafka",
        "Spark Structured\nStreaming\nMOPT upper bound",
        "Format-specific\ntransactional sink",
        "Active Parquet files\n+ retained metadata",
        "Pre-maintenance\nQ1-Q3",
        "Native\nmaintenance",
        "Post-maintenance\nQ1-Q3",
    ]
    colors = ["#EAF2F8", "#E8F6F3", "#FDF2E9", "#F4ECF7", "#F7F7F7", "#FFF4D6", "#F7F7F7"]
    y, h = 0.62, 0.17
    for x, w, label, color in zip(xs, widths, labels, colors):
        box(ax, x, y, w, h, label, face=color)
    for i in range(len(xs) - 1):
        arrow(ax, xs[i] + widths[i] + 0.006, y + h / 2, xs[i + 1] - 0.006, y + h / 2)

    box(ax, 0.317, 0.48, 0.052, 0.075, "Iceberg\n1.4.2", face="#D9EAF7", size=7.3)
    box(ax, 0.375, 0.48, 0.052, 0.075, "Delta\n3.2.0", face="#FCE4D6", size=7.3)
    ax.text(0.372, 0.445, "Separate campaigns on the same Spark framework", ha="center", fontsize=7.2, color="#4D4D4D")

    box(ax, 0.722, 0.47, 0.073, 0.085, "Iceberg\nrewrite_data_files\n+ rewrite_manifests", face="#D9EAF7", size=6.8)
    box(ax, 0.803, 0.47, 0.073, 0.085, "Delta\nOPTIMIZE", face="#FCE4D6", size=7.2)

    ax.text(0.025, 0.365, "Measured timing boundaries", fontweight="bold", fontsize=9.2)
    span(ax, 0.17, 0.43, 0.335, "Complete Spark trigger duration (end-to-end)")
    span(ax, 0.25, 0.43, 0.285, "Append interval", color="#0072B2")
    span(ax, 0.19, 0.42, 0.235, "Collector instrumentation occurs inside the trigger", color="#A65E00")
    span(ax, 0.61, 0.715, 0.335, "Query wall time")
    span(ax, 0.745, 0.85, 0.335, "Native maintenance wall time")
    span(ax, 0.88, 0.985, 0.335, "Query wall time")

    ax.add_patch(Rectangle((0.02, 0.075), 0.96, 0.105, facecolor="#FAFAFA", edgecolor="#B5B5B5", lw=0.8))
    ax.text(0.04, 0.142, "Independent statistical unit", fontweight="bold", fontsize=8.2)
    ax.text(0.245, 0.142, "one physical ingestion run", fontsize=8.2)
    ax.text(0.515, 0.142, "Query executions", fontweight="bold", fontsize=8.2)
    ax.text(0.64, 0.142, "technical warm-up and measurement repetitions", fontsize=8.0)
    ax.text(0.04, 0.102, "Alignment note", fontweight="bold", fontsize=8.2)
    ax.text(0.145, 0.102, "stored ingestion metrics follow the known n-1 alignment; the terminal commit was reconciled separately", fontsize=8.0)

    ax.text(
        0.5,
        0.025,
        "Arrows denote the measured execution sequence, not isolated causal effects. Timing instrumentation and internal observability were format dependent.",
        ha="center",
        va="bottom",
        fontsize=7.5,
        color="#4D4D4D",
    )
    fig.suptitle("Experimental lifecycle and measurement boundaries", y=0.97, fontweight="bold")
    save_figure(fig, "figure_01_lifecycle")


if __name__ == "__main__":
    main()

