from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from figure_common import ROOT, configure_style, save_figure


RESULTS = ROOT / "publication_final_neutralization_analysis_v1_0" / "primary_neutralization_results.csv"


def main() -> None:
    configure_style()
    data = pd.read_csv(RESULTS)
    assert len(data) == 4
    order = [("iceberg", "Q2"), ("iceberg", "Q3"), ("delta", "Q2"), ("delta", "Q3")]
    data = data.set_index(["table_format", "query_id"]).loc[order].reset_index()

    y = np.array([3.2, 2.2, 0.8, -0.2])
    fig, ax = plt.subplots(figsize=(9.0, 4.8), constrained_layout=True)
    ax.axvspan(-0.75, 0.10, color="#FAFAFA", zorder=0)
    ax.axvline(0, color="#222222", lw=1.0, ls=":", zorder=1)
    ax.axhline(1.5, color="#B0B0B0", lw=0.8)

    for phase, offset, color, marker, label in [
        ("pre", 0.12, "#222222", "o", "Pre-maintenance"),
        ("post", -0.12, "#0072B2", "^", "Post-maintenance"),
    ]:
        values = data[f"beta_{phase}"].to_numpy(float)
        lows = data[f"beta_{phase}_ci_low"].to_numpy(float)
        highs = data[f"beta_{phase}_ci_high"].to_numpy(float)
        ax.errorbar(
            values,
            y + offset,
            xerr=np.vstack([values - lows, highs - values]),
            fmt=marker,
            color=color,
            ecolor=color,
            capsize=3,
            markersize=6,
            linewidth=1.4,
            label=label,
            zorder=3,
        )

    labels = ["Iceberg Q2", "Iceberg Q3", "Delta Q2", "Delta Q3"]
    ax.set_yticks(y, labels)
    ax.set_xlabel(r"MOPT elasticity $\beta$ (change in log$_2$ query time per MOPT doubling)")
    ax.set_xlim(-0.76, 0.11)
    ax.grid(True, axis="x")
    ax.legend(frameon=False, loc="lower left")
    ax.text(0.01, 0.97, "Apache Iceberg 1.4.2 campaign", transform=ax.transAxes, fontsize=8.2, fontweight="bold", va="top")
    ax.text(0.01, 0.47, "Delta Lake 3.2.0 campaign", transform=ax.transAxes, fontsize=8.2, fontweight="bold", va="top")
    ax.annotate(
        r"Iceberg Q3 $\beta_{post}$ = -0.00008",
        xy=(float(data.loc[1, "beta_post"]), y[1] - 0.12),
        xytext=(-0.27, 1.68),
        arrowprops={"arrowstyle": "->", "color": "#555555", "lw": 0.8},
        fontsize=7.5,
    )
    ax.set_title("MOPT elasticity of query wall time before and after native maintenance", fontweight="bold", pad=14)
    fig.text(
        0.5,
        -0.015,
        "Points are SF-adjusted run-level model coefficients; bars are the locked 95% intervals. "
        "Format groups derive from temporally separate campaigns.",
        ha="center",
        fontsize=7.7,
    )
    save_figure(fig, "figure_04_query_elasticities")


if __name__ == "__main__":
    main()

