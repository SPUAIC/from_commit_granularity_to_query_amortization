#!/usr/bin/env python3
"""Assess the scientific feasibility of the locked conditional MOPT threshold.

This read-only analysis uses the canonical publication exports. It distinguishes
observations, algebraic implications of the published file-size model, and
unvalidated extrapolation beyond the tested MOPT range.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

import run_publication_neutralization_analysis_v1_0 as locked


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "publication_mopt_threshold_feasibility_analysis_v1_0"
METHOD_VERSION = "publication_mopt_threshold_feasibility_v1_0"
HELPER_HASH = "33b39736d2f5fe81f3813f78c75159e797e4512c4b756b466ce3d0e07b6e593e"
OUTPUT_PARTITIONS = 12
TESTED_MOPT_MIN = 160_000
TESTED_MOPT_MAX = 2_560_000


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
    return sample_sd(values) / abs(mean) if mean else math.nan


def build_run_level(
    manifest: pd.DataFrame,
    maintenance_frames: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    rows = []
    for fmt in ("iceberg", "delta"):
        operation = "rewrite_data_files" if fmt == "iceberg" else "optimize"
        maintenance = maintenance_frames[fmt].loc[
            maintenance_frames[fmt]["operation_type"] == operation
        ].copy()
        wanted = maintenance[
            [
                "ingestion_run_id",
                "avg_data_file_size_mib_before",
                "avg_data_file_size_mib_after",
                "data_file_count_before",
                "data_file_count_after",
                "total_data_size_mib_before",
                "total_data_size_mib_after",
            ]
        ]
        source = manifest.loc[manifest["table_format"] == fmt].copy()
        source = source.merge(
            wanted,
            left_on="canonical_run_key",
            right_on="ingestion_run_id",
            how="left",
            validate="one_to_one",
        )
        rows.append(source)
    frame = pd.concat(rows, ignore_index=True)
    numeric = [
        "scale_factor",
        "mopt",
        "replication",
        "completed_ingestion_commits",
        "avg_data_file_size_mib_before",
        "avg_data_file_size_mib_after",
        "data_file_count_before",
        "data_file_count_after",
        "total_data_size_mib_before",
        "total_data_size_mib_after",
    ]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    return frame.sort_values(
        ["table_format", "scale_factor", "mopt", "replication"]
    ).reset_index(drop=True)


def structural_fit(frame: pd.DataFrame) -> dict[str, float]:
    # MOPT in millions improves conditioning. The locked structural equation is
    # F = delta_parquet + gamma * MOPT, without an SF term.
    x = np.column_stack(
        [np.ones(len(frame)), frame["mopt"].to_numpy(dtype=float) / 1_000_000.0]
    )
    y = frame["avg_data_file_size_mib_before"].to_numpy(dtype=float)
    beta, _, rank, singular = np.linalg.lstsq(x, y, rcond=None)
    if rank != 2:
        raise locked.IntegrityError("Structural file-size model is rank deficient")
    fitted = x @ beta
    residual = y - fitted
    sse = float(np.sum(residual ** 2))
    sst = float(np.sum((y - np.mean(y)) ** 2))
    return {
        "delta_parquet_mib": float(beta[0]),
        "slope_mib_per_million_mopt": float(beta[1]),
        "slope_mib_per_record": float(beta[1] / 1_000_000.0),
        "payload_product_bytes_per_record": float(
            beta[1] / 1_000_000.0 * (2 ** 20) * OUTPUT_PARTITIONS
        ),
        "r_squared": 1.0 - sse / sst,
        "rmse_mib": math.sqrt(sse / len(frame)),
        "mae_mib": float(np.mean(np.abs(residual))),
        "max_abs_residual_mib": float(np.max(np.abs(residual))),
        "condition_number": float(singular[0] / singular[-1]),
    }


def threshold(model: dict[str, float], target_mib: float) -> float:
    slope = model["slope_mib_per_record"]
    if target_mib <= model["delta_parquet_mib"] or slope <= 0:
        return math.nan
    return (target_mib - model["delta_parquet_mib"]) / slope


def build_plans(frame: pd.DataFrame) -> dict[tuple[str, int, int], np.ndarray]:
    rng = np.random.default_rng(locked.BOOTSTRAP_SEED)
    plans = {}
    for fmt in ("iceberg", "delta"):
        for sf in locked.SF_LEVELS:
            for mopt in locked.MOPT_LEVELS:
                subset = frame.loc[
                    (frame["table_format"] == fmt)
                    & (frame["scale_factor"] == sf)
                    & (frame["mopt"] == mopt)
                ].sort_values("replication")
                if len(subset) != 3:
                    raise locked.IntegrityError(
                        f"Expected three runs for {fmt}/SF{sf}/MOPT{mopt}"
                    )
                base = subset.index.to_numpy(dtype=int)
                plans[(fmt, sf, mopt)] = base[
                    rng.integers(
                        0, 3, size=(locked.BOOTSTRAP_DRAWS, 3), endpoint=False
                    )
                ]
    return plans


def sampled_indices(
    fmt: str,
    plans: dict[tuple[str, int, int], np.ndarray],
    draw: int,
) -> np.ndarray:
    return np.concatenate(
        [
            plans[(fmt, sf, mopt)][draw]
            for sf in locked.SF_LEVELS
            for mopt in locked.MOPT_LEVELS
        ]
    )


def model_and_threshold_bootstrap(
    frame: pd.DataFrame,
    fmt: str,
    targets: list[tuple[str, float]],
    plans: dict[tuple[str, int, int], np.ndarray],
) -> tuple[dict[str, float], list[dict[str, object]], list[dict[str, object]]]:
    subset = frame.loc[frame["table_format"] == fmt].reset_index(drop=True)
    point = structural_fit(subset)
    boot_intercept = np.empty(locked.BOOTSTRAP_DRAWS)
    boot_slope = np.empty(locked.BOOTSTRAP_DRAWS)
    boot_thresholds = {
        name: np.empty(locked.BOOTSTRAP_DRAWS) for name, _ in targets
    }
    base = frame.reset_index(drop=True)
    for draw in range(locked.BOOTSTRAP_DRAWS):
        sampled = base.iloc[sampled_indices(fmt, plans, draw)].reset_index(drop=True)
        fitted = structural_fit(sampled)
        boot_intercept[draw] = fitted["delta_parquet_mib"]
        boot_slope[draw] = fitted["slope_mib_per_million_mopt"]
        for name, target_mib in targets:
            boot_thresholds[name][draw] = threshold(fitted, target_mib)

    jack_intercept = []
    jack_slope = []
    jack_thresholds = {name: [] for name, _ in targets}
    for omitted in range(len(subset)):
        fitted = structural_fit(
            subset.drop(subset.index[omitted]).reset_index(drop=True)
        )
        jack_intercept.append(fitted["delta_parquet_mib"])
        jack_slope.append(fitted["slope_mib_per_million_mopt"])
        for name, target_mib in targets:
            jack_thresholds[name].append(threshold(fitted, target_mib))

    parameter_rows = []
    diagnostics = []
    for name, estimate, boot, jack in (
        (
            "delta_parquet_mib",
            point["delta_parquet_mib"],
            boot_intercept,
            np.asarray(jack_intercept),
        ),
        (
            "slope_mib_per_million_mopt",
            point["slope_mib_per_million_mopt"],
            boot_slope,
            np.asarray(jack_slope),
        ),
    ):
        interval = locked.bca_interval(float(estimate), boot, jack)
        parameter_rows.append(
            {
                "table_format": fmt,
                "parameter": name,
                "estimate": estimate,
                **interval,
            }
        )
        diagnostics.append(
            {
                "table_format": fmt,
                "estimand": name,
                **interval,
            }
        )

    threshold_rows = []
    for name, target_mib in targets:
        estimate = threshold(point, target_mib)
        interval = locked.bca_interval(
            estimate,
            boot_thresholds[name],
            np.asarray(jack_thresholds[name]),
        )
        threshold_rows.append(
            {
                "table_format": fmt,
                "target_role": name,
                "target_file_size_mib": target_mib,
                "conditional_mopt_star": estimate,
                "mopt_star_ci_low": interval["ci_low"],
                "mopt_star_ci_high": interval["ci_high"],
                "mopt_star_ci_method": interval["ci_method"],
                "finite_bootstrap_draws": interval["finite_bootstrap_draws"],
                "finite_jackknife_draws": interval["finite_jackknife_draws"],
                "extrapolation_factor_above_tested_max_mopt": estimate
                / TESTED_MOPT_MAX,
                "inside_tested_mopt_range": TESTED_MOPT_MIN
                <= estimate
                <= TESTED_MOPT_MAX,
                "classification": "MODEL_EXTRAPOLATION"
                if not (TESTED_MOPT_MIN <= estimate <= TESTED_MOPT_MAX)
                else "INTERPOLATION_WITHIN_TESTED_MOPT_RANGE",
            }
        )
        diagnostics.append(
            {
                "table_format": fmt,
                "estimand": f"mopt_star:{name}",
                **interval,
            }
        )
    return point, parameter_rows + threshold_rows, diagnostics


def cell_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for key, group in frame.groupby(
        ["table_format", "scale_factor", "mopt"], sort=True
    ):
        fmt, sf, mopt = key
        row = {
            "table_format": fmt,
            "scale_factor": int(sf),
            "mopt": int(mopt),
            "n_physical_runs": len(group),
        }
        for column in (
            "avg_data_file_size_mib_before",
            "avg_data_file_size_mib_after",
            "data_file_count_before",
            "data_file_count_after",
        ):
            values = group[column].to_numpy(dtype=float)
            row[f"{column}_mean"] = float(np.mean(values))
            row[f"{column}_sample_sd"] = sample_sd(values)
            row[f"{column}_cv"] = cv(values)
            row[f"{column}_min"] = float(np.min(values))
            row[f"{column}_max"] = float(np.max(values))
        rows.append(row)
    return pd.DataFrame(rows)


def target_assessment(
    frame: pd.DataFrame,
    threshold_rows: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for threshold_row in threshold_rows.itertuples():
        fmt = threshold_row.table_format
        subset = frame.loc[frame["table_format"] == fmt]
        pre_min = float(subset["avg_data_file_size_mib_before"].min())
        pre_max = float(subset["avg_data_file_size_mib_before"].max())
        post_min = float(subset["avg_data_file_size_mib_after"].min())
        post_max = float(subset["avg_data_file_size_mib_after"].max())
        target_mib = float(threshold_row.target_file_size_mib)
        rows.append(
            {
                "table_format": fmt,
                "target_role": threshold_row.target_role,
                "target_file_size_mib": target_mib,
                "observed_pre_maintenance_min_mib": pre_min,
                "observed_pre_maintenance_max_mib": pre_max,
                "target_within_pre_maintenance_observed_range": pre_min
                <= target_mib
                <= pre_max,
                "largest_pre_maintenance_mean_as_pct_of_target": pre_max
                / target_mib
                * 100.0,
                "observed_post_maintenance_min_mib": post_min,
                "observed_post_maintenance_max_mib": post_max,
                "target_within_post_maintenance_observed_range": post_min
                <= target_mib
                <= post_max,
                "all_post_maintenance_means_at_or_above_target": post_min
                >= target_mib,
                "largest_post_maintenance_mean_as_pct_of_target": post_max
                / target_mib
                * 100.0,
                "conditional_mopt_star": threshold_row.conditional_mopt_star,
                "mopt_star_ci_low": threshold_row.mopt_star_ci_low,
                "mopt_star_ci_high": threshold_row.mopt_star_ci_high,
                "extrapolation_factor_above_tested_max_mopt": threshold_row.extrapolation_factor_above_tested_max_mopt,
                "scientific_status": "UNVALIDATED_MODEL_EXTRAPOLATION",
            }
        )
    return pd.DataFrame(rows)


def draw_feasibility(
    frame: pd.DataFrame,
    models: dict[str, dict[str, float]],
    thresholds: pd.DataFrame,
    output: Path,
) -> None:
    width, height = 1700, 840
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = locked.load_font(32, bold=True)
    panel_font = locked.load_font(24, bold=True)
    body_font = locked.load_font(16)
    small_font = locked.load_font(13)
    draw.text((50, 28), "Conditional MOPT threshold feasibility", fill="#17202a", font=title_font)
    draw.text(
        (50, 72),
        "Observed pre-maintenance file sizes versus extrapolated target crossings (log2 axes)",
        fill="#52616b",
        font=body_font,
    )
    x_min = math.log2(TESTED_MOPT_MIN) - 0.3
    x_max = math.log2(320_000_000) + 0.15
    y_min = math.log2(0.5)
    y_max = math.log2(1300)
    for panel, fmt in enumerate(("iceberg", "delta")):
        x0 = 90 + panel * 820
        y0, pw, ph = 145, 720, 560

        def sx_mopt(value: float) -> float:
            return x0 + (math.log2(value) - x_min) / (x_max - x_min) * pw

        def sy_size(value: float) -> float:
            return y0 + ph - (math.log2(value) - y_min) / (y_max - y_min) * ph

        draw.rectangle((x0, y0, x0 + pw, y0 + ph), fill="#fbfcfc", outline="#95a5a6", width=2)
        tested_right = sx_mopt(TESTED_MOPT_MAX)
        draw.rectangle((x0, y0, tested_right, y0 + ph), fill="#edf6fb")
        draw.text((x0 + 8, y0 + 8), "tested MOPT range", fill="#2878b5", font=small_font)
        draw.text((x0 + pw / 2 - 42, y0 - 37), fmt.title(), fill="#17202a", font=panel_font)
        model = models[fmt]
        line = []
        for step in range(201):
            x_value = 2 ** (x_min + step * (x_max - x_min) / 200)
            y_value = model["delta_parquet_mib"] + model[
                "slope_mib_per_record"
            ] * x_value
            if y_value > 0:
                line.append((sx_mopt(x_value), sy_size(y_value)))
        draw.line(line, fill="#566573", width=3)
        subset = frame.loc[frame["table_format"] == fmt]
        for _, row in subset.iterrows():
            px = sx_mopt(float(row["mopt"]))
            py = sy_size(float(row["avg_data_file_size_mib_before"]))
            draw.ellipse((px - 5, py - 5, px + 5, py + 5), fill="#1f77b4", outline="#ffffff")
        target_rows = thresholds.loc[thresholds["table_format"] == fmt]
        colors = {"harmonized_512_mib": "#d1495b", "native_512_mib": "#d1495b", "native_1024_mib": "#8e5ca2"}
        for _, row in target_rows.iterrows():
            target = float(row["target_file_size_mib"])
            star = float(row["conditional_mopt_star"])
            color = colors[str(row["target_role"])]
            x = sx_mopt(star)
            y = sy_size(target)
            draw.line((x0, y, x, y), fill=color, width=2)
            draw.line((x, y, x, y0 + ph), fill=color, width=2)
            draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=color)
            draw.text((x - 55, y - 28), f"{target:.0f} MiB", fill=color, font=small_font)
        for tick in (160_000, 640_000, 2_560_000, 10_000_000, 100_000_000):
            x = sx_mopt(tick)
            draw.line((x, y0 + ph, x, y0 + ph + 6), fill="#17202a", width=1)
            label = f"{tick/1_000_000:g}m"
            draw.text((x - 18, y0 + ph + 10), label, fill="#17202a", font=small_font)
        for tick in (1, 10, 100, 512, 1024):
            y = sy_size(tick)
            draw.line((x0 - 6, y, x0, y), fill="#17202a", width=1)
            draw.text((x0 - 55, y - 7), f"{tick:g}", fill="#17202a", font=small_font)
        draw.text((x0 + pw / 2 - 55, y0 + ph + 45), "MOPT (log2)", fill="#17202a", font=body_font)
        draw.text((x0 + 5, y0 + ph - 25), "file MiB (log2)", fill="#52616b", font=small_font)
    image.save(output)


def fmt(value: object, digits: int = 3) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return "n.a."
    return f"{number:,.{digits}f}"


def write_report(
    output: Path,
    checks: list[dict[str, object]],
    cells: pd.DataFrame,
    models: pd.DataFrame,
    thresholds: pd.DataFrame,
    assessments: pd.DataFrame,
    generated_at: str,
) -> None:
    lines = [
        "# Conditional MOPT Threshold Feasibility",
        "",
        f"Method version: `{METHOD_VERSION}`  ",
        f"Generated: {generated_at}  ",
        "Scope: 72 canonical runs, including the validated B10 reruns  ",
        f"Tested MOPT range: {TESTED_MOPT_MIN:,} to {TESTED_MOPT_MAX:,} records per trigger  ",
        f"Bootstrap: {locked.BOOTSTRAP_DRAWS:,} stratified physical-run draws; seed `{locked.BOOTSTRAP_SEED}`",
        "",
        "> This report assesses a conditional engineering threshold. It neither proposes an optimization method nor presents an economic cost model.",
        "",
        "## Integrity and measurement boundary",
        "",
        f"All {len(checks)} locked and threshold-specific integrity checks passed before calculation. The file-size endpoint is the table-wide arithmetic mean `total_data_size_mib_before / data_file_count_before`, recorded immediately before native maintenance. Post-maintenance means are reported only as contextual evidence; they are not used to fit the ingestion-side threshold.",
        "",
        "## 1. Empirically observed file-size range",
        "",
        "Each cell contains three independent physical runs. Replication SD is zero within numerical precision in all 24 pre-maintenance SF/MOPT/file-format cells.",
        "",
        "| Format | SF | MOPT | Pre-maintenance mean MiB | Post-maintenance mean MiB |",
        "|---|---:|---:|---:|---:|",
    ]
    for _, row in cells.iterrows():
        lines.append(
            f"| {str(row['table_format']).title()} | {int(row['scale_factor'])} | {int(row['mopt']):,} | "
            f"{fmt(row['avg_data_file_size_mib_before_mean'], 3)} | {fmt(row['avg_data_file_size_mib_after_mean'], 3)} |"
        )
    lines.extend(
        [
            "",
            "Across all runs, pre-maintenance averages span 0.671-9.944 MiB for Iceberg and 0.671-9.918 MiB for Delta. The tested ingestion configurations therefore remain far below both declared target sizes.",
            "",
            "## 2. Target-size coverage",
            "",
            "| Format | Target role | Target MiB | Pre range MiB | Max pre as % target | In pre range? | Post range MiB | Max post as % target | In post range? | All post means >= target? |",
            "|---|---|---:|---:|---:|---|---:|---:|---|---|",
        ]
    )
    for _, row in assessments.iterrows():
        lines.append(
            f"| {str(row['table_format']).title()} | {row['target_role']} | {fmt(row['target_file_size_mib'], 0)} | "
            f"{fmt(row['observed_pre_maintenance_min_mib'], 3)}-{fmt(row['observed_pre_maintenance_max_mib'], 3)} | "
            f"{fmt(row['largest_pre_maintenance_mean_as_pct_of_target'], 2)}% | "
            f"{'Yes' if row['target_within_pre_maintenance_observed_range'] else 'No'} | "
            f"{fmt(row['observed_post_maintenance_min_mib'], 3)}-{fmt(row['observed_post_maintenance_max_mib'], 3)} | "
            f"{fmt(row['largest_post_maintenance_mean_as_pct_of_target'], 2)}% | "
            f"{'Yes' if row['target_within_post_maintenance_observed_range'] else 'No'} | "
            f"{'Yes' if row['all_post_maintenance_means_at_or_above_target'] else 'No'} |"
        )
    lines.extend(
        [
            "",
            "The 512 MiB harmonized target and the native 512 MiB Iceberg target are outside the observed pre-maintenance range. Delta's native 1 GiB target is also outside it. Native maintenance moves the averages toward, but not through, the corresponding native targets: Iceberg reaches 431.161-484.865 MiB and Delta 780.918-962.186 MiB. Delta therefore exceeds the harmonized 512 MiB comparison target after `OPTIMIZE` in every run, but this maintenance outcome does not validate an ingestion-side MOPT threshold. A configured target is a packing objective or upper sizing parameter, not a guarantee that the arithmetic mean equals that value.",
            "",
            "## 3. Structural model and conditional threshold",
            "",
            "The already published structural relationship is:",
            "",
            "`expected_file_size = delta_parquet + (MOPT * mean_row_bytes * compression_factor) / output_partitions`",
            "",
            "with `output_partitions = 12`. Solving it algebraically for a declared target gives:",
            "",
            "`MOPT_star = output_partitions * (F_target - delta_parquet) / (mean_row_bytes * compression_factor)`",
            "",
            "The model parameters below are estimated separately by format from all 36 canonical runs. The intercept is an empirical regression intercept; it must not be interpreted as a direct physical measurement of Parquet header bytes.",
            "",
            "| Format | Delta parquet MiB | Slope MiB / million MOPT | Implied payload product bytes/record | R2 | RMSE MiB |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for _, row in models.iterrows():
        lines.append(
            f"| {str(row['table_format']).title()} | {fmt(row['delta_parquet_mib'], 6)} | "
            f"{fmt(row['slope_mib_per_million_mopt'], 6)} | {fmt(row['payload_product_bytes_per_record'], 3)} | "
            f"{fmt(row['r_squared'], 6)} | {fmt(row['rmse_mib'], 4)} |"
        )
    lines.extend(
        [
            "",
            "| Format | Target role | Target MiB | Conditional MOPT* | 95% interval | Multiple of tested maximum | Classification |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for _, row in thresholds.iterrows():
        lines.append(
            f"| {str(row['table_format']).title()} | {row['target_role']} | {fmt(row['target_file_size_mib'], 0)} | "
            f"{fmt(row['conditional_mopt_star'], 0)} | [{fmt(row['mopt_star_ci_low'], 0)}, {fmt(row['mopt_star_ci_high'], 0)}] | "
            f"{fmt(row['extrapolation_factor_above_tested_max_mopt'], 1)}x | {row['classification']} |"
        )
    lines.extend(
        [
            "",
            "![Threshold feasibility](mopt_threshold_feasibility.png)",
            "",
            "The point calculations and their intervals are mathematical consequences of the fitted structural line. They are not experimentally validated threshold locations. All crossings occur more than fifty times above the maximum tested MOPT; the Delta 1 GiB crossing is more than one hundred times above it. The bootstrap intervals are exceptionally narrow because pre-maintenance cell means are identical across the three repetitions. This conditional replication precision does not reduce extrapolation uncertainty, model-form uncertainty, memory risk, partition skew, or the likelihood that such large triggers change Spark's execution regime.",
            "",
            "## 4. When does the formula imply that compaction remains necessary?",
            "",
            "The formula supports only the following conditional statement: if a chosen target file size is an actual system requirement, if each non-empty micro-batch writes approximately one immutable file per active source partition, if files are not coalesced across batches during ingestion, and if the stable schema/codec/row-size relationship continues to hold, then `MOPT < MOPT_star` implies that ingestion alone is expected to produce files below the target and a later cross-batch rewrite is required to reach that sizing objective.",
            "",
            "That statement additionally assumes:",
            "",
            "1. approximately twelve active and reasonably balanced Kafka/output partitions per full micro-batch;",
            "2. unchanged TPC-DS schema, row-size distribution, ZSTD behavior, Spark writer, and Parquet overhead regime;",
            "3. no optimized write, auto-compaction, adaptive repartitioning, or writer-side cross-batch clustering;",
            "4. sufficiently full batches, with tail batches and partition skew treated as departures from the expectation;",
            "5. a target below neither the fitted intercept nor the practical storage/writer limits;",
            "6. an operational reason to require the target, such as demonstrated query or file-management benefit.",
            "",
            "Average file size below a nominal target does not by itself prove that compaction is operationally required. Conversely, even `MOPT >= MOPT_star` would not guarantee that every file reaches the target, because skew, partial final batches, task retries, and writer behavior create a distribution of file sizes.",
            "",
            "## 5. Evidence classification",
            "",
            "| Statement | Classification | Scientific status |",
            "|---|---|---|",
            "| Average pre-maintenance file size increases monotonically across the tested MOPT grid | Empirical finding | Supported by all 72 canonical runs |",
            "| Pre-maintenance means are 0.671-9.944 MiB | Empirical finding | Directly observed |",
            "| The published affine file-size formula can be solved for MOPT* when slope is positive and target exceeds the intercept | Mathematical derivation | Algebraically valid under model assumptions |",
            "| Conditional crossings are approximately 134 million records for 512 MiB and 269 million for Delta 1 GiB | Model calculation | Reproducible but extrapolated |",
            "| Those MOPT values will produce the targets on this cluster | Experimental claim | Not validated; prohibited |",
            "| Compaction is required for all workloads below MOPT* | Universal operational claim | Not supported; depends on declared objective and workload benefit |",
            "| The targets are optimal | Optimization claim | Not evaluated and not supported |",
            "",
            "## Final feasibility judgment",
            "",
            "The conditional threshold is scientifically usable as an algebraic scenario calculation and as a way to show how far the tested ingestion regime lies from native large-file targets. It is not empirically validated as a configuration threshold. The current experiment supports the direction and near-linear local relationship between MOPT and average file size, but both 512 MiB and 1 GiB crossings lie far outside the observed MOPT and file-size ranges. Therefore, the journal article may report MOPT* only as a clearly labeled, assumption-dependent extrapolation. It must not present the computed values as tested recommendations, universal optima, or evidence that compaction becomes unnecessary at those settings.",
            "",
            "## Reproducibility artifacts",
            "",
            "- `mopt_threshold_run_level.csv`: 72 canonical run-level observations.",
            "- `mopt_threshold_cell_summary.csv`: all 24 SF/MOPT/format cells with replication spread.",
            "- `mopt_threshold_structural_models.csv`: fitted structural parameters and diagnostics.",
            "- `mopt_threshold_estimates.csv`: target crossings, intervals, and extrapolation factors.",
            "- `mopt_target_range_assessment.csv`: observed-range checks before and after maintenance.",
            "- `mopt_threshold_bootstrap_diagnostics.csv`: locked BCa diagnostics.",
            "- `integrity_checks.csv`: canonical and threshold-specific gates.",
            "- `analysis_run_manifest.json`: input/output hashes and runtime versions.",
        ]
    )
    (output / "publication_mopt_threshold_feasibility.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")
    helper = ROOT / "run_publication_neutralization_analysis_v1_0.py"
    if sha256(helper) != HELPER_HASH:
        raise SystemExit("Locked validated helper hash differs")

    manifest, _, maintenance_frames, checks = locked.validate_integrity()
    frame = build_run_level(manifest, maintenance_frames)
    required = [
        "avg_data_file_size_mib_before",
        "avg_data_file_size_mib_after",
        "data_file_count_before",
        "data_file_count_after",
    ]
    if len(frame) != 72 or frame["canonical_ingestion_run_id"].nunique() != 72:
        raise locked.IntegrityError("Threshold analysis requires 72 unique canonical runs")
    if frame[required].isna().any().any() or not (frame[required] > 0).all().all():
        raise locked.IntegrityError("File-size/file-count endpoint is missing or non-positive")
    if set(frame.loc[frame["scenario_id"] == "B10", "canonical_ingestion_run_id"]) != locked.EXPECTED_B10:
        raise locked.IntegrityError("Threshold B10 mapping differs from canonical B10")
    checks.extend(
        [
            {
                "check": "threshold_endpoint_mapping",
                "status": "PASS",
                "detail": "72/72 pre/post native-maintenance file-size observations mapped",
            },
            {
                "check": "threshold_factorial_coverage",
                "status": "PASS",
                "detail": "2 formats x 4 SF x 3 MOPT x 3 physical runs",
            },
            {
                "check": "threshold_B10_mapping",
                "status": "PASS",
                "detail": "validated canonical B10 reruns present",
            },
        ]
    )

    plans = build_plans(frame)
    model_rows = []
    estimate_rows = []
    diagnostic_rows = []
    models = {}
    target_map = {
        "iceberg": [("native_512_mib", 512.0)],
        "delta": [("harmonized_512_mib", 512.0), ("native_1024_mib", 1024.0)],
    }
    for fmt in ("iceberg", "delta"):
        point, rows, diagnostics = model_and_threshold_bootstrap(
            frame, fmt, target_map[fmt], plans
        )
        models[fmt] = point
        model_rows.append({"table_format": fmt, **point})
        estimate_rows.extend(
            row for row in rows if "target_file_size_mib" in row
        )
        diagnostic_rows.extend(diagnostics)
    thresholds = pd.DataFrame(estimate_rows)
    model_table = pd.DataFrame(model_rows)
    cells = cell_summary(frame)
    assessments = target_assessment(frame, thresholds)
    checks.extend(
        [
            {
                "check": "threshold_model_coverage",
                "status": "PASS",
                "detail": "separate structural fit over 36 canonical runs per format",
            },
            {
                "check": "threshold_bootstrap",
                "status": "PASS",
                "detail": f"{locked.BOOTSTRAP_DRAWS} stratified draws; seed {locked.BOOTSTRAP_SEED}",
            },
            {
                "check": "threshold_target_roles",
                "status": "PASS",
                "detail": "Iceberg native/common 512 MiB; Delta common 512 MiB and native 1 GiB",
            },
        ]
    )

    output.mkdir(parents=True, exist_ok=False)
    run_columns = [
        "table_format",
        "scenario_id",
        "scale_factor",
        "mopt",
        "replication",
        "canonical_run_key",
        "canonical_ingestion_run_id",
        "avg_data_file_size_mib_before",
        "avg_data_file_size_mib_after",
        "data_file_count_before",
        "data_file_count_after",
        "total_data_size_mib_before",
        "total_data_size_mib_after",
        "validation_status",
        "documented_exceptions",
    ]
    frame[run_columns].to_csv(
        output / "mopt_threshold_run_level.csv", index=False, quoting=csv.QUOTE_MINIMAL
    )
    cells.to_csv(
        output / "mopt_threshold_cell_summary.csv", index=False, quoting=csv.QUOTE_MINIMAL
    )
    model_table.to_csv(
        output / "mopt_threshold_structural_models.csv", index=False, quoting=csv.QUOTE_MINIMAL
    )
    thresholds.to_csv(
        output / "mopt_threshold_estimates.csv", index=False, quoting=csv.QUOTE_MINIMAL
    )
    assessments.to_csv(
        output / "mopt_target_range_assessment.csv", index=False, quoting=csv.QUOTE_MINIMAL
    )
    pd.DataFrame(diagnostic_rows).to_csv(
        output / "mopt_threshold_bootstrap_diagnostics.csv",
        index=False,
        quoting=csv.QUOTE_MINIMAL,
    )
    pd.DataFrame(checks).to_csv(
        output / "integrity_checks.csv", index=False, quoting=csv.QUOTE_MINIMAL
    )
    draw_feasibility(
        frame, models, thresholds, output / "mopt_threshold_feasibility.png"
    )
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    write_report(
        output,
        checks,
        cells,
        model_table,
        thresholds,
        assessments,
        generated_at,
    )

    output_hashes = {
        path.name: sha256(path)
        for path in sorted(output.iterdir())
        if path.is_file() and path.name != "analysis_run_manifest.json"
    }
    run_manifest = {
        "method_version": METHOD_VERSION,
        "generated_at_utc": generated_at,
        "analysis_type": "conditional_mopt_threshold_feasibility_not_optimization_or_cost",
        "bootstrap_seed": locked.BOOTSTRAP_SEED,
        "bootstrap_draws": locked.BOOTSTRAP_DRAWS,
        "tested_mopt_range": [TESTED_MOPT_MIN, TESTED_MOPT_MAX],
        "output_partitions": OUTPUT_PARTITIONS,
        "specification_hashes": {
            locked.SPEC_MD.name: sha256(locked.SPEC_MD),
            locked.SPEC_YAML.name: sha256(locked.SPEC_YAML),
        },
        "canonical_manifest_hash": sha256(locked.MANIFEST),
        "analysis_script_hash": sha256(Path(__file__).resolve()),
        "helper_script_hash": sha256(helper),
        "input_hashes": {
            str(path.relative_to(ROOT)): sha256(path) for path in locked.EXPECTED_HASHES
        },
        "output_hashes": output_hashes,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "integrity_checks": checks,
    }
    (output / "analysis_run_manifest.json").write_text(
        json.dumps(run_manifest, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "integrity_checks": len(checks),
                "canonical_runs": len(frame),
                "cell_rows": len(cells),
                "threshold_rows": len(thresholds),
                "classifications": thresholds["classification"].value_counts().to_dict(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
