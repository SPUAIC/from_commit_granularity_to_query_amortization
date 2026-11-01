from __future__ import annotations

import hashlib
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent

FORMAT_LABELS = {"iceberg": "Apache Iceberg 1.4.2", "delta": "Delta Lake 3.2.0"}
SF_VALUES = [50, 100, 200, 500]
MOPT_VALUES = [160_000, 640_000, 2_560_000]

# Okabe-Ito colors plus distinct markers/linestyles preserve separation in grayscale.
SF_STYLES = {
    50: {"color": "#0072B2", "marker": "o", "linestyle": "-"},
    100: {"color": "#E69F00", "marker": "s", "linestyle": "--"},
    200: {"color": "#009E73", "marker": "^", "linestyle": "-."},
    500: {"color": "#CC79A7", "marker": "D", "linestyle": ":"},
}


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9.0,
            "axes.titlesize": 10.0,
            "axes.labelsize": 9.0,
            "xtick.labelsize": 8.0,
            "ytick.labelsize": 8.0,
            "legend.fontsize": 8.0,
            "figure.titlesize": 12.0,
            "axes.linewidth": 0.8,
            "grid.color": "#D8D8D8",
            "grid.linewidth": 0.55,
            "grid.alpha": 0.75,
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
            "svg.fonttype": "none",
        }
    )


def save_figure(fig: plt.Figure, stem: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{stem}.svg", bbox_inches="tight", pad_inches=0.08)
    fig.savefig(OUT / f"{stem}.png", dpi=600, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)


def add_panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        -0.12,
        1.06,
        label,
        transform=ax.transAxes,
        fontsize=10,
        fontweight="bold",
        va="top",
    )


def format_mopt(value: int) -> str:
    return {160_000: "160k", 640_000: "640k", 2_560_000: "2.56M"}[int(value)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

