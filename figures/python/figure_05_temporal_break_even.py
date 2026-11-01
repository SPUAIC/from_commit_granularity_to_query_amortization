from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

from figure_common import MOPT_VALUES, ROOT, SF_VALUES, configure_style, format_mopt, save_figure


RESULTS = ROOT / "publication_query_break_even_analysis_v1_0_sealed" / "query_break_even_cell_results.csv"


def main() -> None:
    configure_style()
    data = pd.read_csv(RESULTS)
    data = data[data.analysis_role == "primary"].copy()
    assert len(data) == 48
    assert (data.break_even_status == "ESTIMABLE").all()

    vmin = float(data.break_even_query_executions.min())
    vmax = float(data.break_even_query_executions.max())
    norm = LogNorm(vmin=vmin, vmax=vmax)

    fig, axes = plt.subplots(2, 2, figsize=(9.3, 7.0), constrained_layout=True)
    panels = [("iceberg", "Q2"), ("iceberg", "Q3"), ("delta", "Q2"), ("delta", "Q3")]
    image = None
    for ax, (fmt, query) in zip(axes.flat, panels):
        subset = data[(data.table_format == fmt) & (data.query_id == query)]
        pivot = subset.pivot(index="scale_factor", columns="mopt", values="break_even_query_executions").loc[SF_VALUES, MOPT_VALUES]
        values = pivot.to_numpy(float)
        image = ax.pcolormesh(
            np.arange(values.shape[1] + 1) - 0.5,
            np.arange(values.shape[0] + 1) - 0.5,
            values,
            cmap="cividis",
            norm=norm,
            shading="flat",
        )
        for i in range(values.shape[0]):
            for j in range(values.shape[1]):
                rgba = image.cmap(norm(values[i, j]))
                luminance = 0.2126 * rgba[0] + 0.7152 * rgba[1] + 0.0722 * rgba[2]
                color = "black" if luminance > 0.55 else "white"
                ax.text(j, i, f"{values[i, j]:.1f}", ha="center", va="center", color=color, fontsize=8.2, fontweight="bold")
        ax.set_xticks(range(3), [format_mopt(v) for v in MOPT_VALUES])
        ax.set_yticks(range(4), [f"SF{sf}" for sf in SF_VALUES])
        ax.set_xlim(-0.5, 2.5)
        ax.set_ylim(3.5, -0.5)
        ax.set_xlabel("MOPT")
        ax.set_ylabel("TPC-DS scale factor")
        operation = "rewrite_data_files" if fmt == "iceberg" else "OPTIMIZE"
        title_fmt = "Apache Iceberg 1.4.2" if fmt == "iceberg" else "Delta Lake 3.2.0"
        ax.set_title(f"{title_fmt}, {query}\nPrimary boundary: {operation}", fontweight="bold", fontsize=9.4)

    cbar = fig.colorbar(image, ax=axes, location="right", shrink=0.86, pad=0.025)
    cbar.solids.set_rasterized(False)
    cbar.set_label("Temporal break-even (comparable query executions; log color scale)")
    fig.suptitle("Temporal query break-even after native maintenance", y=1.02, fontweight="bold")
    fig.text(
        0.5,
        -0.015,
        "Temporal, not monetary, amortization. Estimates assume repeated comparable queries and sufficiently stable positive time savings. "
        "Iceberg rewrite_manifests sensitivity is reported in the Supplementary Material.",
        ha="center",
        fontsize=7.7,
    )
    save_figure(fig, "figure_05_temporal_break_even")


if __name__ == "__main__":
    main()

