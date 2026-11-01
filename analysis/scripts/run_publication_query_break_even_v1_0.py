#!/usr/bin/env python3
"""Temporal query break-even analysis under the locked v1.0 specification.

This script reads only canonical publication exports. It performs no economic
cost calculation and refuses to overwrite an existing output directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

import run_publication_neutralization_analysis_v1_0 as locked


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "publication_query_break_even_analysis_v1_0"
HELPER_HASH = "33b39736d2f5fe81f3813f78c75159e797e4512c4b756b466ce3d0e07b6e593e"
METHOD_VERSION = "publication_query_break_even_v1_0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sample_sd(values: np.ndarray) -> float:
    return float(np.std(values, ddof=1)) if len(values) > 1 else math.nan


def cv(values: np.ndarray) -> float:
    mean = float(np.mean(values))
    return sample_sd(values) / abs(mean) if mean != 0 else math.nan


def jackknife_metric(pre: np.ndarray, post: np.ndarray, maintenance: np.ndarray, metric: str) -> np.ndarray:
    output = []
    all_indices = np.arange(len(pre))
    for omitted in all_indices:
        idx = all_indices[all_indices != omitted]
        mean_pre = float(np.mean(pre[idx]))
        mean_post = float(np.mean(post[idx]))
        mean_saving = mean_pre - mean_post
        mean_maintenance = float(np.mean(maintenance[idx]))
        if metric == "pre":
            output.append(mean_pre)
        elif metric == "post":
            output.append(mean_post)
        elif metric == "saving":
            output.append(mean_saving)
        elif metric == "maintenance":
            output.append(mean_maintenance)
        elif metric == "break_even":
            output.append(mean_maintenance / mean_saving if mean_saving > 0 else math.nan)
        else:
            raise ValueError(metric)
    return np.asarray(output, dtype=float)


def interval(point: float, boot: np.ndarray, jack: np.ndarray) -> dict[str, object]:
    return locked.bca_interval(point, boot, jack)


def bootstrap_cell(
    pre: np.ndarray,
    post: np.ndarray,
    maintenance: np.ndarray,
    plan: np.ndarray,
) -> dict[str, object]:
    boot_pre = np.mean(pre[plan], axis=1)
    boot_post = np.mean(post[plan], axis=1)
    boot_saving = boot_pre - boot_post
    boot_maintenance = np.mean(maintenance[plan], axis=1)
    boot_break_even = np.divide(
        boot_maintenance,
        boot_saving,
        out=np.full(len(plan), np.nan, dtype=float),
        where=boot_saving > 0,
    )

    point_pre = float(np.mean(pre))
    point_post = float(np.mean(post))
    point_saving = point_pre - point_post
    point_maintenance = float(np.mean(maintenance))
    point_break_even = point_maintenance / point_saving if point_saving > 0 else math.nan

    intervals = {
        "pre": interval(point_pre, boot_pre, jackknife_metric(pre, post, maintenance, "pre")),
        "post": interval(point_post, boot_post, jackknife_metric(pre, post, maintenance, "post")),
        "saving": interval(point_saving, boot_saving, jackknife_metric(pre, post, maintenance, "saving")),
        "maintenance": interval(
            point_maintenance,
            boot_maintenance,
            jackknife_metric(pre, post, maintenance, "maintenance"),
        ),
        "break_even": interval(
            point_break_even,
            boot_break_even,
            jackknife_metric(pre, post, maintenance, "break_even"),
        ) if math.isfinite(point_break_even) else {
            "ci_low": math.nan,
            "ci_high": math.nan,
            "ci_method": "CI_NOT_ESTIMABLE",
            "finite_bootstrap_draws": int(np.isfinite(boot_break_even).sum()),
            "finite_jackknife_draws": 0,
            "bca_bias_correction": math.nan,
            "bca_acceleration": math.nan,
            "adjusted_lower_quantile": math.nan,
            "adjusted_upper_quantile": math.nan,
        },
    }

    saving_ci = intervals["saving"]
    if point_saving <= 0:
        status = "NO_FINITE_BREAK_EVEN"
        point_break_even = math.nan
        intervals["break_even"].update(
            {"ci_low": math.nan, "ci_high": math.nan, "ci_method": "CI_NOT_ESTIMABLE"}
        )
    elif (
        saving_ci["ci_method"] == "CI_NOT_ESTIMABLE"
        or not math.isfinite(float(saving_ci["ci_low"]))
        or float(saving_ci["ci_low"]) <= 0.0 <= float(saving_ci["ci_high"])
    ):
        status = "UNSTABLE_SAVING_DENOMINATOR"
        intervals["break_even"].update(
            {
                "ci_low": math.nan,
                "ci_high": math.nan,
                "ci_method": "CI_NOT_REPORTED_UNSTABLE_DENOMINATOR",
            }
        )
    elif int(intervals["break_even"]["finite_bootstrap_draws"]) < locked.MIN_FINITE_DRAWS:
        status = "CI_NOT_ESTIMABLE"
        intervals["break_even"].update(
            {"ci_low": math.nan, "ci_high": math.nan, "ci_method": "CI_NOT_ESTIMABLE"}
        )
    else:
        status = "ESTIMABLE"

    return {
        "mean_pre_query_wall_time_ms": point_pre,
        "sd_pre_query_wall_time_ms": sample_sd(pre),
        "cv_pre_query_wall_time": cv(pre),
        "mean_post_query_wall_time_ms": point_post,
        "sd_post_query_wall_time_ms": sample_sd(post),
        "cv_post_query_wall_time": cv(post),
        "mean_query_time_saving_ms": point_saving,
        "sd_query_time_saving_ms": sample_sd(pre - post),
        "cv_query_time_saving": cv(pre - post),
        "positive_saving_runs": int(np.sum((pre - post) > 0)),
        "mean_maintenance_wall_time_ms": point_maintenance,
        "sd_maintenance_wall_time_ms": sample_sd(maintenance),
        "cv_maintenance_wall_time": cv(maintenance),
        "break_even_query_executions": point_break_even,
        "break_even_status": status,
        "bootstrap_positive_saving_fraction": float(np.mean(boot_saving > 0)),
        "pre_ci": intervals["pre"],
        "post_ci": intervals["post"],
        "saving_ci": intervals["saving"],
        "maintenance_ci": intervals["maintenance"],
        "break_even_ci": intervals["break_even"],
    }


def add_interval_columns(row: dict[str, object], prefix: str, result: dict[str, object]) -> None:
    details = result[f"{prefix}_ci"]
    row[f"{prefix}_ci_low"] = details["ci_low"]
    row[f"{prefix}_ci_high"] = details["ci_high"]
    row[f"{prefix}_ci_method"] = details["ci_method"]
    row[f"{prefix}_finite_bootstrap_draws"] = details["finite_bootstrap_draws"]
    row[f"{prefix}_finite_jackknife_draws"] = details["finite_jackknife_draws"]
    row[f"{prefix}_bca_bias_correction"] = details["bca_bias_correction"]
    row[f"{prefix}_bca_acceleration"] = details["bca_acceleration"]
    row[f"{prefix}_adjusted_lower_quantile"] = details["adjusted_lower_quantile"]
    row[f"{prefix}_adjusted_upper_quantile"] = details["adjusted_upper_quantile"]


def fmt(value: object, digits: int = 1) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return "n.a."
    return f"{number:,.{digits}f}"


def heat_color(value: float, low: float, high: float) -> tuple[int, int, int]:
    if high <= low:
        t = 0.5
    else:
        t = min(max((math.log10(value) - low) / (high - low), 0.0), 1.0)
    start = np.asarray([226, 239, 218], dtype=float)
    middle = np.asarray([254, 224, 139], dtype=float)
    end = np.asarray([215, 48, 39], dtype=float)
    if t < 0.5:
        rgb = start + (middle - start) * (t * 2.0)
    else:
        rgb = middle + (end - middle) * ((t - 0.5) * 2.0)
    return tuple(int(x) for x in rgb)


def draw_primary_heatmap(frame: pd.DataFrame, output: Path) -> None:
    width, height = 1700, 1120
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = locked.load_font(34, bold=True)
    panel_font = locked.load_font(27, bold=True)
    body_font = locked.load_font(21)
    small_font = locked.load_font(17)
    draw.text((55, 28), "Temporal query break-even after native maintenance", fill="#17202a", font=title_font)
    draw.text((55, 78), "Cell values are query executions; U = unstable saving denominator; N = no finite break-even", fill="#34495e", font=small_font)

    stable = frame.loc[(frame["break_even_status"] == "ESTIMABLE") & np.isfinite(frame["break_even_query_executions"])]
    logs = np.log10(stable["break_even_query_executions"].astype(float).to_numpy()) if len(stable) else np.asarray([0.0, 1.0])
    low, high = float(np.min(logs)), float(np.max(logs))

    panels = [("iceberg", "Q2"), ("iceberg", "Q3"), ("delta", "Q2"), ("delta", "Q3")]
    panel_width, panel_height = 770, 450
    origins = [(55, 135), (875, 135), (55, 620), (875, 620)]
    cell_w, cell_h = 185, 72
    for (fmt_name, query), (ox, oy) in zip(panels, origins):
        draw.text((ox, oy), f"{fmt_name.title()} {query}", fill="#17202a", font=panel_font)
        grid_x, grid_y = ox + 155, oy + 62
        for col, mopt in enumerate(locked.MOPT_LEVELS):
            label = f"{mopt // 1000}k" if mopt < 1_000_000 else f"{mopt / 1_000_000:.2f}m"
            draw.text((grid_x + col * cell_w + 55, grid_y - 33), label, fill="#17202a", font=small_font)
        for row_idx, sf in enumerate(locked.SF_LEVELS):
            draw.text((ox + 15, grid_y + row_idx * cell_h + 22), f"SF{sf}", fill="#17202a", font=body_font)
            for col, mopt in enumerate(locked.MOPT_LEVELS):
                rec = frame.loc[
                    (frame["table_format"] == fmt_name)
                    & (frame["query_id"] == query)
                    & (frame["scale_factor"] == sf)
                    & (frame["mopt"] == mopt)
                ].iloc[0]
                x0 = grid_x + col * cell_w
                y0 = grid_y + row_idx * cell_h
                value = float(rec["break_even_query_executions"])
                status = rec["break_even_status"]
                if status == "ESTIMABLE" and math.isfinite(value):
                    fill = heat_color(value, low, high)
                    label = f"{value:,.0f}"
                elif status == "UNSTABLE_SAVING_DENOMINATOR":
                    fill = (220, 220, 220)
                    label = "U"
                else:
                    fill = (185, 185, 185)
                    label = "N"
                draw.rectangle((x0, y0, x0 + cell_w - 8, y0 + cell_h - 8), fill=fill, outline="#ffffff", width=2)
                bbox = draw.textbbox((0, 0), label, font=body_font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                draw.text((x0 + (cell_w - 8 - tw) / 2, y0 + (cell_h - 8 - th) / 2 - 2), label, fill="#17202a", font=body_font)
    image.save(output)


def draw_iceberg_sensitivity(frame: pd.DataFrame, output: Path) -> None:
    primary = frame.loc[(frame["table_format"] == "iceberg") & (frame["maintenance_boundary"] == "rewrite_data_files")]
    total = frame.loc[(frame["table_format"] == "iceberg") & (frame["maintenance_boundary"] == "rewrite_data_files_plus_rewrite_manifests")]
    merged = primary.merge(
        total,
        on=["scale_factor", "mopt", "query_id"],
        suffixes=("_data", "_total"),
        validate="one_to_one",
    )
    finite = merged.loc[
        np.isfinite(merged["break_even_query_executions_data"])
        & np.isfinite(merged["break_even_query_executions_total"])
    ]
    width, height = 1450, 820
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = locked.load_font(34, bold=True)
    body_font = locked.load_font(22)
    small_font = locked.load_font(18)
    draw.text((55, 30), "Iceberg break-even sensitivity to rewrite_manifests", fill="#17202a", font=title_font)
    plot_left, plot_right = 140, width - 100
    plot_top, plot_bottom = 135, height - 165
    values = np.concatenate(
        [
            finite["break_even_query_executions_data"].astype(float).to_numpy(),
            finite["break_even_query_executions_total"].astype(float).to_numpy(),
        ]
    ) if len(finite) else np.asarray([1.0, 10.0])
    y_min = max(float(np.min(values)) * 0.7, 0.1)
    y_max = float(np.max(values)) * 1.4
    log_min, log_max = math.log10(y_min), math.log10(y_max)

    def y_pos(value: float) -> float:
        return plot_bottom - (math.log10(value) - log_min) / (log_max - log_min) * (plot_bottom - plot_top)

    groups = []
    for query in ("Q2", "Q3"):
        for sf in locked.SF_LEVELS:
            for mopt in locked.MOPT_LEVELS:
                groups.append((query, sf, mopt))
    x_gap = (plot_right - plot_left) / max(len(groups) - 1, 1)
    colors = {"Q2": "#2878b5", "Q3": "#d95f02"}
    axis_font = locked.load_font(12)
    for idx, (query, sf, mopt) in enumerate(groups):
        row = merged.loc[
            (merged["query_id"] == query) & (merged["scale_factor"] == sf) & (merged["mopt"] == mopt)
        ].iloc[0]
        data_value = float(row["break_even_query_executions_data"])
        total_value = float(row["break_even_query_executions_total"])
        x = plot_left + idx * x_gap
        if math.isfinite(data_value) and math.isfinite(total_value) and data_value > 0 and total_value > 0:
            color = colors[query]
            draw.line((x, y_pos(data_value), x, y_pos(total_value)), fill="#95a5a6", width=2)
            draw.ellipse((x - 5, y_pos(data_value) - 5, x + 5, y_pos(data_value) + 5), fill=color)
            draw.rectangle((x - 5, y_pos(total_value) - 5, x + 5, y_pos(total_value) + 5), fill=color)
        mopt_label = {160000: "160k", 640000: "640k", 2560000: "2.56m"}[int(mopt)]
        label = f"SF{int(sf)}\n{mopt_label}"
        label_box = draw.multiline_textbbox((0, 0), label, font=axis_font, align="center", spacing=1)
        label_width = label_box[2] - label_box[0]
        draw.multiline_text(
            (x - label_width / 2, plot_bottom + 9),
            label,
            fill="#34495e",
            font=axis_font,
            align="center",
            spacing=1,
        )
    separator_x = (plot_left + 11 * x_gap + plot_left + 12 * x_gap) / 2
    draw.line((separator_x, plot_top, separator_x, plot_bottom), fill="#d5d8dc", width=2)
    draw.text((plot_left + 5.5 * x_gap - 18, plot_top - 32), "Q2", fill=colors["Q2"], font=small_font)
    draw.text((plot_left + 17.5 * x_gap - 18, plot_top - 32), "Q3", fill=colors["Q3"], font=small_font)
    draw.line((plot_left, plot_bottom, plot_right, plot_bottom), fill="#17202a", width=2)
    draw.line((plot_left, plot_top, plot_left, plot_bottom), fill="#17202a", width=2)
    for tick in [1, 10, 100, 1000, 10000, 100000]:
        if y_min <= tick <= y_max:
            y = y_pos(tick)
            draw.line((plot_left - 8, y, plot_left, y), fill="#17202a", width=2)
            draw.text((55, y - 10), f"{tick:,}", fill="#17202a", font=small_font)
    draw.text((50, 90), "Queries to break even (log scale)", fill="#17202a", font=body_font)
    draw.ellipse((490, height - 38, 502, height - 26), fill="#34495e")
    draw.text((512, height - 44), "rewrite_data_files", fill="#17202a", font=small_font)
    draw.rectangle((740, height - 38, 752, height - 26), fill="#34495e")
    draw.text((762, height - 44), "+ rewrite_manifests", fill="#17202a", font=small_font)
    image.save(output)


def write_report(output: Path, cells: pd.DataFrame, checks: list[dict[str, object]], generated_at: str) -> None:
    primary = cells.loc[cells["analysis_role"] == "primary"].copy()
    sensitivity = cells.loc[cells["analysis_role"] == "iceberg_manifest_sensitivity"].copy()
    counts = primary.groupby(["table_format", "query_id", "break_even_status"]).size().reset_index(name="cells")

    lines = [
        "# Temporal Query Break-Even Results",
        "",
        f"Method version: `{METHOD_VERSION}`  ",
        f"Generated: {generated_at}  ",
        "Scope: 72 canonical runs; Q2 and Q3; 24 SF/MOPT cells per primary maintenance boundary  ",
        f"Bootstrap: {locked.BOOTSTRAP_DRAWS:,} paired run-level draws per cell; seed `{locked.BOOTSTRAP_SEED}`",
        "",
        "> This is a temporal amortization analysis measured in future query executions. It is not an economic cost model.",
        "",
        "## Integrity decision",
        "",
        f"All {len(checks)} locked canonical-data checks passed before calculation. The validated B10 reruns are included. No source row was altered or imputed.",
        "",
        "## Definition",
        "",
        "For each format/SF/MOPT/query cell, the three physical runs are the independent replications. Each run contributes the arithmetic mean of its three measured query repetitions before and after maintenance.",
        "",
        "`mean saving = mean(pre query time - post query time)`",
        "",
        "`break-even queries = mean(maintenance wall time) / mean saving`",
        "",
        "All three run-level savings enter the mean, including zero or negative values. A nonpositive cell mean yields `NO_FINITE_BREAK_EVEN`. A positive mean whose bootstrap interval includes zero yields `UNSTABLE_SAVING_DENOMINATOR` and no break-even confidence interval.",
        "",
        "Primary maintenance boundaries are Iceberg `rewrite_data_files` and Delta `optimize`. Iceberg additionally reports the locked sensitivity using `rewrite_data_files + rewrite_manifests`.",
        "",
        "## Primary status summary",
        "",
        "| Format | Query | Status | Cells |",
        "|---|---|---|---:|",
    ]
    for row in counts.itertuples():
        lines.append(f"| {str(row.table_format).title()} | {row.query_id} | {row.break_even_status} | {row.cells} |")

    lines.extend(
        [
            "",
            "## Primary cell results",
            "",
            "Times are milliseconds. Break-even is the number of subsequent executions of the indicated query.",
            "",
            "| Format | SF | MOPT | Query | Mean pre | Mean post | Mean saving (95% CI) | Mean maintenance | Break-even (95% CI) | Status | Replication CV: saving / maintenance |",
            "|---|---:|---:|---|---:|---:|---:|---:|---:|---|---:|",
        ]
    )
    for row in primary.sort_values(["table_format", "query_id", "scale_factor", "mopt"]).itertuples():
        saving = f"{fmt(row.mean_query_time_saving_ms)} [{fmt(row.saving_ci_low)}, {fmt(row.saving_ci_high)}]"
        if math.isfinite(float(row.break_even_query_executions)):
            if math.isfinite(float(row.break_even_ci_low)):
                be = f"{fmt(row.break_even_query_executions)} [{fmt(row.break_even_ci_low)}, {fmt(row.break_even_ci_high)}]"
            else:
                be = fmt(row.break_even_query_executions)
        else:
            be = "n.a."
        lines.append(
            f"| {str(row.table_format).title()} | {row.scale_factor} | {row.mopt} | {row.query_id} | "
            f"{fmt(row.mean_pre_query_wall_time_ms)} | {fmt(row.mean_post_query_wall_time_ms)} | {saving} | "
            f"{fmt(row.mean_maintenance_wall_time_ms)} | {be} | {row.break_even_status} | "
            f"{fmt(row.cv_query_time_saving, 3)} / {fmt(row.cv_maintenance_wall_time, 3)} |"
        )

    lines.extend(
        [
            "",
            "![Primary break-even heatmap](query_break_even_primary_heatmap.png)",
            "",
            "## Iceberg manifest-rewrite sensitivity",
            "",
            "Adding `rewrite_manifests` increases the one-time maintenance boundary but does not change query savings. This is a format-specific sensitivity; no synthetic Delta manifest operation is introduced.",
            "",
            "| SF | MOPT | Query | Data-file rewrite break-even | Including manifest rewrite | Added maintenance ms | Sensitivity status |",
            "|---:|---:|---|---:|---:|---:|---|",
        ]
    )
    primary_ice = primary.loc[primary["table_format"] == "iceberg"]
    merged = primary_ice.merge(
        sensitivity,
        on=["scale_factor", "mopt", "query_id"],
        suffixes=("_data", "_total"),
        validate="one_to_one",
    )
    for row in merged.sort_values(["query_id", "scale_factor", "mopt"]).itertuples():
        added = float(row.mean_maintenance_wall_time_ms_total) - float(row.mean_maintenance_wall_time_ms_data)
        lines.append(
            f"| {row.scale_factor} | {row.mopt} | {row.query_id} | {fmt(row.break_even_query_executions_data)} | "
            f"{fmt(row.break_even_query_executions_total)} | {fmt(added)} | {row.break_even_status_total} |"
        )

    lines.extend(
        [
            "",
            "![Iceberg sensitivity](iceberg_manifest_rewrite_sensitivity.png)",
            "",
            "## Uncertainty and replication spread",
            "",
            "- Every cell uses three independent physical runs; technical query repetitions were aggregated before cell analysis.",
            "- SD and CV columns in `query_break_even_cell_results.csv` describe between-run dispersion for pre time, post time, saving, and maintenance.",
            "- The same 10,000 within-cell paired resamples are used for Q2 and Q3 and, for Iceberg, both maintenance boundaries.",
            "- BCa is used only when the locked validity checks pass; otherwise the locked percentile fallback is identified in the result table.",
            "- With only three runs per cell, intervals can be broad or discrete. A stable pooled neutralization result does not guarantee a finite break-even in every individual cell.",
            "",
            "## Interpretation boundary",
            "",
            "Break-even counts answer how many later query executions would be required to offset measured maintenance wall time under the observed query and system conditions. They do not include cloud prices, staff time, energy prices, or a monetary valuation. Native Iceberg and Delta maintenance operations remain structurally different and are not described as identical algorithms.",
            "",
            "## Reproducibility artifacts",
            "",
            "- `query_break_even_cell_results.csv`: complete primary and Iceberg-sensitivity cell estimates.",
            "- `query_break_even_primary_results.csv`: the 48 primary format/SF/MOPT/query estimates.",
            "- `query_break_even_iceberg_sensitivity_results.csv`: the 24 Iceberg estimates including `rewrite_manifests`.",
            "- `query_break_even_run_level.csv`: run-level paired query and maintenance values.",
            "- `query_break_even_bootstrap_diagnostics.csv`: interval diagnostics and fallback decisions.",
            "- `integrity_checks.csv`: locked input gates.",
            "- `analysis_run_manifest.json`: input/output hashes and software versions.",
        ]
    )
    (output / "publication_query_break_even_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")
    helper_path = ROOT / "run_publication_neutralization_analysis_v1_0.py"
    if sha256(helper_path) != HELPER_HASH:
        raise SystemExit("Locked neutralization helper hash differs from the validated version")

    manifest, query_frames, maintenance_frames, checks = locked.validate_integrity()
    agg = locked.aggregate_queries(manifest, query_frames)

    maintenance_maps: dict[tuple[str, str, str], float] = {}
    for fmt_name, frame in maintenance_frames.items():
        frame = frame.copy()
        frame["operation_wall_time_ms"] = pd.to_numeric(frame["operation_wall_time_ms"], errors="raise")
        for row in frame.itertuples():
            maintenance_maps[(fmt_name, row.ingestion_run_id, row.operation_type)] = float(row.operation_wall_time_ms)

    rng = np.random.default_rng(locked.BOOTSTRAP_SEED)
    plans: dict[tuple[str, int, int], np.ndarray] = {}
    for fmt_name in ("iceberg", "delta"):
        for sf in locked.SF_LEVELS:
            for mopt in locked.MOPT_LEVELS:
                plans[(fmt_name, sf, mopt)] = rng.integers(0, 3, size=(locked.BOOTSTRAP_DRAWS, 3), endpoint=False)

    cell_rows: list[dict[str, object]] = []
    run_rows: list[dict[str, object]] = []
    diagnostic_rows: list[dict[str, object]] = []

    for fmt_name in ("iceberg", "delta"):
        format_manifest = manifest.loc[manifest["table_format"] == fmt_name].copy()
        for sf in locked.SF_LEVELS:
            for mopt in locked.MOPT_LEVELS:
                cell_manifest = format_manifest.loc[
                    (format_manifest["scale_factor"].astype(int) == sf)
                    & (format_manifest["mopt"].astype(int) == mopt)
                ].sort_values("replication")
                if len(cell_manifest) != 3:
                    raise locked.IntegrityError(f"Expected three runs for {fmt_name}/SF{sf}/MOPT{mopt}")
                run_keys = cell_manifest["canonical_run_key"].tolist()
                plan = plans[(fmt_name, sf, mopt)]

                boundaries = (
                    [
                        ("rewrite_data_files", "primary", ["rewrite_data_files"]),
                        (
                            "rewrite_data_files_plus_rewrite_manifests",
                            "iceberg_manifest_sensitivity",
                            ["rewrite_data_files", "rewrite_manifests"],
                        ),
                    ]
                    if fmt_name == "iceberg"
                    else [("optimize", "primary", ["optimize"])]
                )

                for query in locked.PRIMARY_QUERIES:
                    pre = []
                    post = []
                    for run_key in run_keys:
                        query_rows = agg.loc[
                            (agg["table_format"] == fmt_name)
                            & (agg["ingestion_run_id"] == run_key)
                            & (agg["query_id"] == query)
                        ].set_index("phase")
                        pre.append(float(query_rows.loc["pre_compaction", "mean_query_wall_time_ms"]))
                        post.append(float(query_rows.loc["post_compaction", "mean_query_wall_time_ms"]))
                    pre_array = np.asarray(pre, dtype=float)
                    post_array = np.asarray(post, dtype=float)

                    for boundary, role, operations in boundaries:
                        maintenance = np.asarray(
                            [
                                sum(maintenance_maps[(fmt_name, run_key, operation)] for operation in operations)
                                for run_key in run_keys
                            ],
                            dtype=float,
                        )
                        result = bootstrap_cell(pre_array, post_array, maintenance, plan)
                        row: dict[str, object] = {
                            "method_version": METHOD_VERSION,
                            "analysis_role": role,
                            "table_format": fmt_name,
                            "scale_factor": sf,
                            "mopt": mopt,
                            "query_id": query,
                            "maintenance_boundary": boundary,
                            "n_runs": 3,
                            "run_keys": ";".join(run_keys),
                        }
                        for key, value in result.items():
                            if not key.endswith("_ci"):
                                row[key] = value
                        for prefix in ("pre", "post", "saving", "maintenance", "break_even"):
                            add_interval_columns(row, prefix, result)
                            diag = {
                                "table_format": fmt_name,
                                "scale_factor": sf,
                                "mopt": mopt,
                                "query_id": query,
                                "maintenance_boundary": boundary,
                                "metric": prefix,
                            }
                            diag.update(result[f"{prefix}_ci"])
                            diagnostic_rows.append(diag)
                        cell_rows.append(row)

                        for idx, run_key in enumerate(run_keys):
                            saving = pre_array[idx] - post_array[idx]
                            run_rows.append(
                                {
                                    "method_version": METHOD_VERSION,
                                    "analysis_role": role,
                                    "table_format": fmt_name,
                                    "scale_factor": sf,
                                    "mopt": mopt,
                                    "query_id": query,
                                    "maintenance_boundary": boundary,
                                    "canonical_run_key": run_key,
                                    "canonical_ingestion_run_id": cell_manifest.iloc[idx]["canonical_ingestion_run_id"],
                                    "replication": int(cell_manifest.iloc[idx]["replication"]),
                                    "pre_query_wall_time_ms": pre_array[idx],
                                    "post_query_wall_time_ms": post_array[idx],
                                    "query_time_saving_ms": saving,
                                    "maintenance_wall_time_ms": maintenance[idx],
                                    "run_break_even_query_executions": maintenance[idx] / saving if saving > 0 else math.nan,
                                    "run_saving_status": "POSITIVE" if saving > 0 else "NONPOSITIVE",
                                }
                            )

    cells = pd.DataFrame(cell_rows)
    run_level = pd.DataFrame(run_rows)
    diagnostics = pd.DataFrame(diagnostic_rows)

    expected_primary = 2 * 4 * 3 * 2
    expected_sensitivity = 4 * 3 * 2
    if len(cells.loc[cells["analysis_role"] == "primary"]) != expected_primary:
        raise locked.IntegrityError("Primary break-even cell count mismatch")
    if len(cells.loc[cells["analysis_role"] == "iceberg_manifest_sensitivity"]) != expected_sensitivity:
        raise locked.IntegrityError("Iceberg sensitivity cell count mismatch")
    checks.extend(
        [
            {"check": "break_even_primary_cell_coverage", "status": "PASS", "detail": f"{expected_primary} format/SF/MOPT/query cells"},
            {"check": "iceberg_manifest_sensitivity_coverage", "status": "PASS", "detail": f"{expected_sensitivity} SF/MOPT/query cells"},
            {"check": "break_even_run_pairing", "status": "PASS", "detail": "three canonical physical runs per cell; pre/post/maintenance paired"},
        ]
    )

    output.mkdir(parents=True, exist_ok=False)
    cells.to_csv(output / "query_break_even_cell_results.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    cells.loc[cells["analysis_role"] == "primary"].to_csv(
        output / "query_break_even_primary_results.csv", index=False, quoting=csv.QUOTE_MINIMAL
    )
    cells.loc[cells["analysis_role"] == "iceberg_manifest_sensitivity"].to_csv(
        output / "query_break_even_iceberg_sensitivity_results.csv", index=False, quoting=csv.QUOTE_MINIMAL
    )
    run_level.to_csv(output / "query_break_even_run_level.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    diagnostics.to_csv(output / "query_break_even_bootstrap_diagnostics.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    pd.DataFrame(checks).to_csv(output / "integrity_checks.csv", index=False, quoting=csv.QUOTE_MINIMAL)

    primary = cells.loc[cells["analysis_role"] == "primary"]
    draw_primary_heatmap(primary, output / "query_break_even_primary_heatmap.png")
    draw_iceberg_sensitivity(cells, output / "iceberg_manifest_rewrite_sensitivity.png")
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    write_report(output, cells, checks, generated_at)

    output_hashes = {
        path.name: sha256(path)
        for path in sorted(output.iterdir())
        if path.is_file() and path.name != "analysis_run_manifest.json"
    }
    analysis_manifest = {
        "method_version": METHOD_VERSION,
        "generated_at_utc": generated_at,
        "analysis_type": "temporal_query_amortization_not_economic_cost",
        "bootstrap_seed": locked.BOOTSTRAP_SEED,
        "bootstrap_draws": locked.BOOTSTRAP_DRAWS,
        "specification_hashes": {
            locked.SPEC_MD.name: sha256(locked.SPEC_MD),
            locked.SPEC_YAML.name: sha256(locked.SPEC_YAML),
        },
        "canonical_manifest_hash": sha256(locked.MANIFEST),
        "analysis_script_hash": sha256(Path(__file__).resolve()),
        "helper_script_hash": sha256(helper_path),
        "input_hashes": {str(path.relative_to(ROOT)): sha256(path) for path in locked.EXPECTED_HASHES},
        "output_hashes": output_hashes,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "status_counts_primary": {
            key: int(value)
            for key, value in Counter(primary["break_even_status"]).items()
        },
        "integrity_checks": checks,
    }
    (output / "analysis_run_manifest.json").write_text(
        json.dumps(analysis_manifest, indent=2, ensure_ascii=True), encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "output": str(output),
                "integrity_checks": len(checks),
                "primary_cells": len(primary),
                "iceberg_sensitivity_cells": len(cells) - len(primary),
                "status_counts_primary": analysis_manifest["status_counts_primary"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
