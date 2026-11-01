from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from figure_common import (
    FORMAT_LABELS,
    MOPT_VALUES,
    ROOT,
    SF_STYLES,
    SF_VALUES,
    add_panel_label,
    configure_style,
    format_mopt,
    save_figure,
)


MANIFEST = ROOT / "publication_canonical_run_manifest.csv"
MAINTENANCE = ROOT / "lakehouse_publication_synthesis_artifacts" / "publication_maintenance_group_summary.csv"
METADATA_RUNS = ROOT / "publication_metadata_growth_final_analysis_v1_0_2_sealed" / "metadata_growth_run_level.csv"


def main() -> None:
    configure_style()
    manifest = pd.read_csv(MANIFEST)
    maintenance = pd.read_csv(MAINTENANCE)
    metadata_runs = pd.read_csv(METADATA_RUNS)

    assert len(manifest) == 72
    assert len(maintenance) == 24
    ratios = metadata_runs["data_file_count_before"] / metadata_runs["completed_ingestion_commits"]
    assert np.allclose(ratios.to_numpy(), 12.0)

    commits = (
        manifest.groupby(["table_format", "scale_factor", "mopt"], as_index=False)
        .agg(commits_mean=("completed_ingestion_commits", "mean"), commits_sd=("completed_ingestion_commits", "std"))
    )
    data = maintenance.merge(commits, on=["table_format", "scale_factor", "mopt"], validate="one_to_one")
    x = np.arange(len(MOPT_VALUES))

    fig, axes = plt.subplots(2, 3, figsize=(12.2, 7.3), sharex=True, constrained_layout=False)
    fig.subplots_adjust(left=0.07, right=0.985, bottom=0.11, top=0.82, wspace=0.23, hspace=0.30)
    endpoints = [
        ("commits_mean", "commits_sd", "Completed commits", True),
        ("data_file_count_before_mean", "data_file_count_before_sd", "Active Parquet files", True),
        ("avg_data_file_size_mib_before_mean", "avg_data_file_size_mib_before_sd", "Mean active file size (MiB)", True),
    ]

    panel = 0
    for row, fmt in enumerate(["iceberg", "delta"]):
        for col, (value_col, sd_col, ylabel, log_scale) in enumerate(endpoints):
            ax = axes[row, col]
            subset = data[data["table_format"] == fmt]
            for sf in SF_VALUES:
                s = subset[subset["scale_factor"] == sf].set_index("mopt").loc[MOPT_VALUES]
                style = SF_STYLES[sf]
                y = s[value_col].to_numpy(float)
                err = s[sd_col].fillna(0).to_numpy(float)
                ax.errorbar(
                    x,
                    y,
                    yerr=err,
                    color=style["color"],
                    marker=style["marker"],
                    linestyle=style["linestyle"],
                    linewidth=1.4,
                    markersize=5.2,
                    capsize=2.2,
                    label=f"SF{sf}",
                )
            if log_scale:
                ax.set_yscale("log")
            ax.grid(True, which="major", axis="y")
            ax.set_ylabel(ylabel)
            ax.set_xticks(x, [format_mopt(v) for v in MOPT_VALUES])
            ax.set_xlabel("MOPT (maximum Kafka offsets per trigger)")
            if col == 1:
                ax.set_title(FORMAT_LABELS[fmt], fontweight="bold", pad=10)
            add_panel_label(ax, chr(ord("a") + panel))
            panel += 1

    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.925),
        ncol=4,
        frameon=False,
        title="TPC-DS scale factor",
    )
    fig.suptitle("Micro-batch granularity and ingestion-created physical state", y=0.985, fontweight="bold")
    fig.text(
        0.5,
        0.025,
        "Points are arithmetic means of three physical runs; error bars show run-level SD. "
        "Every completed commit produced 12 active files in this writer configuration. Format rows are separate experimental campaigns.",
        ha="center",
        fontsize=7.7,
    )
    save_figure(fig, "figure_02_ingestion_physical_state")


if __name__ == "__main__":
    main()

