from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from figure_common import (
    FORMAT_LABELS,
    ROOT,
    SF_STYLES,
    SF_VALUES,
    add_panel_label,
    configure_style,
    save_figure,
)


SEALED = ROOT / "publication_metadata_growth_final_analysis_v1_0_2_sealed"
RUNS = SEALED / "metadata_growth_run_level.csv"
ELASTICITIES = SEALED / "metadata_growth_primary_elasticities.csv"
PRIMARY_COEFFICIENTS = SEALED / "metadata_growth_primary_coefficients.csv"
SECONDARY_MODELS = SEALED / "metadata_growth_secondary_model_comparison.csv"


def primary_coefficients(frame, fmt, endpoint):
    rows = frame[(frame.table_format == fmt) & (frame.endpoint == endpoint)]
    return dict(zip(rows.coefficient, rows.estimate.astype(float)))


def power_prediction(coeffs, commits, sf):
    value = coeffs["intercept"] + coeffs["log2_completed_ingestion_commits"] * np.log2(commits)
    if sf != 50:
        value += coeffs[f"sf_{sf}_fixed_effect"]
    return np.power(2.0, value)


def main() -> None:
    configure_style()
    runs = pd.read_csv(RUNS)
    elasticities = pd.read_csv(ELASTICITIES)
    primary = pd.read_csv(PRIMARY_COEFFICIENTS)
    secondary = pd.read_csv(SECONDARY_MODELS)

    assert len(runs) == 72
    assert len(elasticities) == 4
    assert len(primary) == 20
    assert len(secondary) == 12

    endpoints = [
        ("metadata_file_count_before", "Retained metadata files"),
        ("metadata_total_size_mib_before", "Retained metadata size (MiB)"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 8.0), constrained_layout=False)
    fig.subplots_adjust(left=0.08, right=0.985, bottom=0.11, top=0.82, wspace=0.22, hspace=0.30)
    panel = 0

    for row, fmt in enumerate(["iceberg", "delta"]):
        for col, (endpoint, ylabel) in enumerate(endpoints):
            ax = axes[row, col]
            subset = runs[runs.table_format == fmt]
            pcoef = primary_coefficients(primary, fmt, endpoint)
            for sf in SF_VALUES:
                s = subset[subset.scale_factor == sf]
                style = SF_STYLES[sf]
                ax.scatter(
                    s.completed_ingestion_commits,
                    s[endpoint],
                    color=style["color"],
                    marker=style["marker"],
                    s=27,
                    alpha=0.72,
                    edgecolors="white",
                    linewidths=0.35,
                    zorder=3,
                )
                xmin = float(s.completed_ingestion_commits.min())
                xmax = float(s.completed_ingestion_commits.max())
                grid = np.geomspace(xmin, xmax, 120)
                ax.plot(
                    grid,
                    power_prediction(pcoef, grid, sf),
                    color=style["color"],
                    linestyle="--" if col == 1 else style["linestyle"],
                    linewidth=1.25,
                    alpha=0.95,
                )
            ax.set_xscale("log")
            ax.set_yscale("log")
            ax.grid(True, which="major")
            ax.set_xlabel("Completed ingestion commits (log scale)")
            ax.set_ylabel(f"{ylabel} (log scale)")
            if col == 0:
                ax.set_title(f"{FORMAT_LABELS[fmt]}: file count", fontweight="bold")
            else:
                eta = elasticities[
                    (elasticities.table_format == fmt) & (elasticities.endpoint == endpoint)
                ].eta.iloc[0]
                ax.set_title(f"{FORMAT_LABELS[fmt]}: bytes, η = {eta:.3f}", fontweight="bold")
                qrow = secondary[
                    (secondary.table_format == fmt)
                    & (secondary.endpoint == endpoint)
                    & (secondary.model == "quadratic")
                ].iloc[0]
                prow = secondary[
                    (secondary.table_format == fmt)
                    & (secondary.endpoint == endpoint)
                    & (secondary.model == "power")
                ].iloc[0]
                ax.text(
                    0.03,
                    0.97,
                    "Original-scale RMSE (MiB)\n"
                    f"quadratic {float(qrow.rmse_original_scale):.1f}; "
                    f"power {float(prow.rmse_original_scale):.1f}\n"
                    "quadratic not overlaid on log axes",
                    transform=ax.transAxes,
                    ha="left",
                    va="top",
                    fontsize=6.8,
                    color="#4D4D4D",
                    bbox={"facecolor": "white", "edgecolor": "#BDBDBD", "alpha": 0.9, "pad": 2.5},
                )
            add_panel_label(ax, chr(ord("a") + panel))
            panel += 1

    sf_handles = [
        Line2D([0], [0], color=SF_STYLES[sf]["color"], marker=SF_STYLES[sf]["marker"], lw=0, label=f"SF{sf}")
        for sf in SF_VALUES
    ]
    model_handles = [Line2D([0], [0], color="#333333", lw=1.25, ls="--", label="SF-adjusted power fit")]
    fig.legend(
        sf_handles + model_handles,
        [h.get_label() for h in sf_handles + model_handles],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.925),
        ncol=5,
        frameon=False,
    )
    fig.suptitle("Retained metadata scaling within the observed commit ranges", y=0.985, fontweight="bold")
    fig.text(
        0.5,
        0.02,
        "Dashed curves are SF-specific predictions from stored power-model coefficients; no model was re-estimated. "
        "The stored original-scale quadratic fit has lower byte RMSE but is not drawn on log axes because some Iceberg fits are nonpositive. "
        "Retained footprint includes historical objects.",
        ha="center",
        fontsize=7.7,
    )
    save_figure(fig, "figure_03_metadata_scaling")


if __name__ == "__main__":
    main()

