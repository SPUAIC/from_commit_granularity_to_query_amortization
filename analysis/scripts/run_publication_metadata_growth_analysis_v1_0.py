#!/usr/bin/env python3
"""Final retained-metadata analysis under the locked publication v1.0 plan.

The program reads the immutable canonical exports only. It refuses to overwrite
an existing output directory and does not connect to Spark, HDFS, or Kafka.
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
DEFAULT_OUTPUT = ROOT / "publication_metadata_growth_final_analysis_v1_0"
METHOD_VERSION = "publication_metadata_growth_final_v1_0"
HELPER_HASH = "33b39736d2f5fe81f3813f78c75159e797e4512c4b756b466ce3d0e07b6e593e"
PRIOR_EXPONENTS = {"iceberg": 1.874732889279489, "delta": 1.7343046399194524}
ENDPOINTS = {
    "metadata_total_size_mib_before": "Retained metadata footprint (MiB)",
    "metadata_file_count_before": "Retained metadata file count",
}
SF_COLORS = {50: "#2878b5", 100: "#d95f02", 200: "#2a9d55", 500: "#8e5ca2"}
MODEL_COLORS = {"linear": "#2878b5", "quadratic": "#d1495b", "power": "#2a9d55"}


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


def design_matrix(frame: pd.DataFrame, model: str) -> tuple[np.ndarray, list[str]]:
    commits = frame["completed_ingestion_commits"].to_numpy(dtype=float)
    columns = [np.ones(len(frame), dtype=float)]
    names = ["intercept"]
    if model == "power":
        columns.append(np.log2(commits))
        names.append("log2_completed_ingestion_commits")
    else:
        scaled = commits / 1000.0
        columns.append(scaled)
        names.append("completed_ingestion_commits_per_1000")
        if model == "quadratic":
            columns.append(scaled * scaled)
            names.append("completed_ingestion_commits_per_1000_squared")
    for sf in (100, 200, 500):
        columns.append((frame["scale_factor"].to_numpy(dtype=int) == sf).astype(float))
        names.append(f"sf_{sf}_fixed_effect")
    return np.column_stack(columns), names


def fit_model(frame: pd.DataFrame, endpoint: str, model: str) -> dict[str, object]:
    x, names = design_matrix(frame, model)
    y_original = frame[endpoint].to_numpy(dtype=float)
    y_native = np.log2(y_original) if model == "power" else y_original
    beta, _, rank, singular = np.linalg.lstsq(x, y_native, rcond=None)
    if rank != x.shape[1]:
        raise locked.IntegrityError(f"Rank-deficient {model} model for {endpoint}")
    fitted_native = x @ beta
    fitted_original = np.exp2(fitted_native) if model == "power" else fitted_native
    residual_native = y_native - fitted_native
    residual_original = y_original - fitted_original
    n, k = x.shape
    sse_native = float(np.sum(residual_native ** 2))
    sst_native = float(np.sum((y_native - np.mean(y_native)) ** 2))
    sse_original = float(np.sum(residual_original ** 2))
    sst_original = float(np.sum((y_original - np.mean(y_original)) ** 2))
    r2_native = 1.0 - sse_native / sst_native if sst_native else 1.0
    r2_original = 1.0 - sse_original / sst_original if sst_original else 1.0
    adjusted_r2_native = 1.0 - (1.0 - r2_native) * (n - 1) / (n - k)
    adjusted_r2_original = 1.0 - (1.0 - r2_original) * (n - 1) / (n - k)
    sigma = float(np.std(residual_original, ddof=0))
    skewness = (
        float(np.mean((residual_original / sigma) ** 3)) if sigma > 0 else 0.0
    )
    excess_kurtosis = (
        float(np.mean((residual_original / sigma) ** 4) - 3.0) if sigma > 0 else 0.0
    )
    residual_fitted_correlation = (
        float(np.corrcoef(residual_original, fitted_original)[0, 1])
        if np.std(residual_original) > 0 and np.std(fitted_original) > 0
        else math.nan
    )
    return {
        "model": model,
        "coefficient_names": names,
        "coefficients": beta,
        "rank": int(rank),
        "condition_number": float(singular[0] / singular[-1]),
        "fitted_original": fitted_original,
        "residual_original": residual_original,
        "residual_native": residual_native,
        "r_squared_native_response": r2_native,
        "adjusted_r_squared_native_response": adjusted_r2_native,
        "r_squared_original_scale": r2_original,
        "adjusted_r_squared_original_scale": adjusted_r2_original,
        "rmse_original_scale": math.sqrt(sse_original / n),
        "mae_original_scale": float(np.mean(np.abs(residual_original))),
        "max_abs_residual_original_scale": float(np.max(np.abs(residual_original))),
        "max_abs_residual_pct": float(np.max(np.abs(residual_original) / y_original) * 100.0),
        "nonpositive_fitted_count": int(np.sum(fitted_original <= 0)),
        "residual_mean_original_scale": float(np.mean(residual_original)),
        "residual_skewness": skewness,
        "residual_excess_kurtosis": excess_kurtosis,
        "residual_fitted_correlation": residual_fitted_correlation,
        "aic_native_response": n * math.log(max(sse_native / n, 1e-300)) + 2 * k,
        "bic_native_response": n * math.log(max(sse_native / n, 1e-300)) + k * math.log(n),
    }


def predict_one(train: pd.DataFrame, test: pd.DataFrame, endpoint: str, model: str) -> float:
    fit = fit_model(train, endpoint, model)
    x, _ = design_matrix(test, model)
    value = float(x[0] @ fit["coefficients"])
    return 2.0 ** value if model == "power" else value


def loocv_rmse(frame: pd.DataFrame, endpoint: str, model: str) -> float:
    errors = []
    for idx in range(len(frame)):
        train = frame.drop(frame.index[idx]).reset_index(drop=True)
        test = frame.iloc[[idx]].reset_index(drop=True)
        predicted = predict_one(train, test, endpoint, model)
        errors.append(float(test.iloc[0][endpoint]) - predicted)
    return math.sqrt(float(np.mean(np.square(errors))))


def add_interval_columns(row: dict[str, object], interval: dict[str, object]) -> None:
    for key, value in interval.items():
        row[key] = value


def build_run_level(
    manifest: pd.DataFrame,
    maintenance_frames: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    parts = []
    for fmt in ("iceberg", "delta"):
        operation = "rewrite_data_files" if fmt == "iceberg" else "optimize"
        maintenance = maintenance_frames[fmt].loc[
            maintenance_frames[fmt]["operation_type"] == operation
        ].copy()
        selected = maintenance[
            [
                "ingestion_run_id",
                "metadata_total_size_mib_before",
                "metadata_file_count_before",
                "data_file_count_before",
                "total_data_size_mib_before",
            ]
        ]
        source = manifest.loc[manifest["table_format"] == fmt].copy()
        source = source.merge(
            selected,
            left_on="canonical_run_key",
            right_on="ingestion_run_id",
            how="left",
            validate="one_to_one",
        )
        parts.append(source)
    frame = pd.concat(parts, ignore_index=True)
    numeric = [
        "scale_factor",
        "mopt",
        "replication",
        "completed_ingestion_commits",
        "metadata_total_size_mib_before",
        "metadata_file_count_before",
        "data_file_count_before",
        "total_data_size_mib_before",
    ]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    frame = frame.sort_values(
        ["table_format", "scale_factor", "mopt", "replication"]
    ).reset_index(drop=True)
    return frame


def build_bootstrap_plans(frame: pd.DataFrame) -> dict[tuple[str, int, int], np.ndarray]:
    rng = np.random.default_rng(locked.BOOTSTRAP_SEED)
    plans = {}
    for fmt in ("iceberg", "delta"):
        for sf in locked.SF_LEVELS:
            for mopt in locked.MOPT_LEVELS:
                subset = frame.loc[
                    (frame["table_format"] == fmt)
                    & (frame["scale_factor"] == sf)
                    & (frame["mopt"] == mopt)
                ]
                if len(subset) != 3:
                    raise locked.IntegrityError(
                        f"Expected three runs for {fmt}/SF{sf}/MOPT{mopt}"
                    )
                base = subset.sort_values("replication").index.to_numpy(dtype=int)
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
    indices = []
    for sf in locked.SF_LEVELS:
        for mopt in locked.MOPT_LEVELS:
            indices.extend(plans[(fmt, sf, mopt)][draw].tolist())
    return np.asarray(indices, dtype=int)


def bootstrap_power_coefficients(
    frame: pd.DataFrame,
    fmt: str,
    endpoint: str,
    plans: dict[tuple[str, int, int], np.ndarray],
) -> tuple[dict[str, object], np.ndarray, np.ndarray]:
    subset = frame.loc[frame["table_format"] == fmt].reset_index(drop=True)
    point_fit = fit_model(subset, endpoint, "power")
    point = np.asarray(point_fit["coefficients"], dtype=float)
    draws = np.empty((locked.BOOTSTRAP_DRAWS, len(point)), dtype=float)
    for draw in range(locked.BOOTSTRAP_DRAWS):
        idx = sampled_indices(fmt, plans, draw)
        sampled = frame.reset_index(drop=True).iloc[idx].reset_index(drop=True)
        draws[draw] = fit_model(sampled, endpoint, "power")["coefficients"]
    jackknife = np.empty((len(subset), len(point)), dtype=float)
    for omitted in range(len(subset)):
        jackknife[omitted] = fit_model(
            subset.drop(subset.index[omitted]).reset_index(drop=True), endpoint, "power"
        )["coefficients"]
    return point_fit, draws, jackknife


def cell_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for key, group in frame.groupby(["table_format", "scale_factor", "mopt"], sort=True):
        fmt, sf, mopt = key
        row = {
            "table_format": fmt,
            "scale_factor": int(sf),
            "mopt": int(mopt),
            "n_physical_runs": len(group),
        }
        for column in (
            "completed_ingestion_commits",
            "metadata_total_size_mib_before",
            "metadata_file_count_before",
        ):
            values = group[column].to_numpy(dtype=float)
            row[f"{column}_mean"] = float(np.mean(values))
            row[f"{column}_sample_sd"] = sample_sd(values)
            row[f"{column}_cv"] = cv(values)
        rows.append(row)
    return pd.DataFrame(rows)


def prior_power_reconciliation(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for fmt in ("iceberg", "delta"):
        groups = (
            frame.loc[frame["table_format"] == fmt]
            .groupby(["scale_factor", "mopt"], as_index=False)
            .agg(
                completed_ingestion_commits=("completed_ingestion_commits", "mean"),
                metadata_total_size_mib_before=("metadata_total_size_mib_before", "mean"),
            )
        )
        x = np.column_stack(
            [
                np.ones(len(groups)),
                np.log2(groups["completed_ingestion_commits"].to_numpy(dtype=float)),
            ]
        )
        y = np.log2(groups["metadata_total_size_mib_before"].to_numpy(dtype=float))
        beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
        if rank != 2:
            raise locked.IntegrityError(f"Prior-model reproduction is rank deficient for {fmt}")
        reproduced = float(beta[1])
        expected = PRIOR_EXPONENTS[fmt]
        if abs(reproduced - expected) > 1e-10:
            raise locked.IntegrityError(
                f"Prior exponent did not reproduce for {fmt}: {reproduced} != {expected}"
            )
        rows.append(
            {
                "table_format": fmt,
                "prior_analysis_unit": "12_SF_MOPT_scenario_means",
                "prior_sf_fixed_effects": False,
                "prior_reported_exponent": expected,
                "exactly_reproduced_exponent": reproduced,
                "absolute_reproduction_difference": abs(reproduced - expected),
            }
        )
    return pd.DataFrame(rows)


def model_comparisons(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    comparison_rows = []
    residual_rows = []
    for fmt in ("iceberg", "delta"):
        subset = frame.loc[frame["table_format"] == fmt].reset_index(drop=True)
        for endpoint in ENDPOINTS:
            for model in ("linear", "quadratic", "power"):
                fit = fit_model(subset, endpoint, model)
                comparison_rows.append(
                    {
                        "table_format": fmt,
                        "endpoint": endpoint,
                        "model": model,
                        "n_physical_runs": len(subset),
                        "parameter_count": len(fit["coefficients"]),
                        "coefficient_names": ";".join(fit["coefficient_names"]),
                        "coefficients_json": json.dumps(
                            {
                                name: float(value)
                                for name, value in zip(
                                    fit["coefficient_names"], fit["coefficients"]
                                )
                            },
                            sort_keys=True,
                        ),
                        "r_squared_native_response": fit["r_squared_native_response"],
                        "adjusted_r_squared_native_response": fit[
                            "adjusted_r_squared_native_response"
                        ],
                        "r_squared_original_scale": fit["r_squared_original_scale"],
                        "adjusted_r_squared_original_scale": fit[
                            "adjusted_r_squared_original_scale"
                        ],
                        "rmse_original_scale": fit["rmse_original_scale"],
                        "mae_original_scale": fit["mae_original_scale"],
                        "loocv_rmse_original_scale": loocv_rmse(subset, endpoint, model),
                        "max_abs_residual_original_scale": fit[
                            "max_abs_residual_original_scale"
                        ],
                        "max_abs_residual_pct": fit["max_abs_residual_pct"],
                        "nonpositive_fitted_count": fit["nonpositive_fitted_count"],
                        "residual_mean_original_scale": fit[
                            "residual_mean_original_scale"
                        ],
                        "residual_skewness": fit["residual_skewness"],
                        "residual_excess_kurtosis": fit[
                            "residual_excess_kurtosis"
                        ],
                        "residual_fitted_correlation": fit[
                            "residual_fitted_correlation"
                        ],
                        "condition_number": fit["condition_number"],
                        "aic_native_response": fit["aic_native_response"],
                        "bic_native_response": fit["bic_native_response"],
                        "response_scale": "log2" if model == "power" else "original",
                    }
                )
                actual = subset[endpoint].to_numpy(dtype=float)
                for idx, source in subset.iterrows():
                    residual_rows.append(
                        {
                            "table_format": fmt,
                            "endpoint": endpoint,
                            "model": model,
                            "canonical_run_key": source["canonical_run_key"],
                            "scale_factor": int(source["scale_factor"]),
                            "mopt": int(source["mopt"]),
                            "replication": int(source["replication"]),
                            "completed_ingestion_commits": int(
                                source["completed_ingestion_commits"]
                            ),
                            "observed": actual[idx],
                            "fitted": float(fit["fitted_original"][idx]),
                            "residual": float(fit["residual_original"][idx]),
                            "residual_pct": float(
                                fit["residual_original"][idx] / actual[idx] * 100.0
                            ),
                        }
                    )
    return pd.DataFrame(comparison_rows), pd.DataFrame(residual_rows)


def fmt_number(value: object, digits: int = 4) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return "n.a."
    return f"{number:,.{digits}f}"


def draw_loglog_fit(
    frame: pd.DataFrame,
    primary_coefficients: pd.DataFrame,
    endpoint: str,
    output: Path,
) -> None:
    width, height = 1650, 760
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = locked.load_font(32, bold=True)
    panel_font = locked.load_font(24, bold=True)
    body_font = locked.load_font(17)
    small_font = locked.load_font(14)
    draw.text((50, 26), ENDPOINTS[endpoint], fill="#17202a", font=title_font)
    draw.text(
        (50, 70),
        "Run-level observations and fitted log2 model with SF fixed effects",
        fill="#52616b",
        font=body_font,
    )
    for panel, fmt in enumerate(("iceberg", "delta")):
        x0 = 95 + panel * 805
        y0, pw, ph = 145, 690, 495
        subset = frame.loc[frame["table_format"] == fmt]
        xs = np.log2(subset["completed_ingestion_commits"].to_numpy(dtype=float))
        ys = np.log2(subset[endpoint].to_numpy(dtype=float))
        xmin, xmax = float(xs.min()) - 0.15, float(xs.max()) + 0.15
        ymin, ymax = float(ys.min()) - 0.25, float(ys.max()) + 0.25

        def sx(value: float) -> float:
            return x0 + (value - xmin) / (xmax - xmin) * pw

        def sy(value: float) -> float:
            return y0 + ph - (value - ymin) / (ymax - ymin) * ph

        draw.rectangle((x0, y0, x0 + pw, y0 + ph), fill="#fbfcfc", outline="#95a5a6", width=2)
        for grid in range(1, 5):
            gx = x0 + grid * pw / 5
            gy = y0 + grid * ph / 5
            draw.line((gx, y0, gx, y0 + ph), fill="#e5e7e9", width=1)
            draw.line((x0, gy, x0 + pw, gy), fill="#e5e7e9", width=1)
        draw.text((x0 + pw / 2 - 42, y0 - 36), fmt.title(), fill="#17202a", font=panel_font)
        coefficient_map = {
            row["coefficient"]: float(row["estimate"])
            for _, row in primary_coefficients.loc[
                (primary_coefficients["table_format"] == fmt)
                & (primary_coefficients["endpoint"] == endpoint)
            ].iterrows()
        }
        eta = coefficient_map["log2_completed_ingestion_commits"]
        for sf in locked.SF_LEVELS:
            intercept = coefficient_map["intercept"] + (
                coefficient_map.get(f"sf_{sf}_fixed_effect", 0.0) if sf != 50 else 0.0
            )
            line = []
            for step in range(101):
                x_value = xmin + step * (xmax - xmin) / 100
                line.append((sx(x_value), sy(intercept + eta * x_value)))
            draw.line(line, fill=SF_COLORS[sf], width=3)
        for _, row in subset.iterrows():
            px = sx(math.log2(float(row["completed_ingestion_commits"])))
            py = sy(math.log2(float(row[endpoint])))
            color = SF_COLORS[int(row["scale_factor"])]
            draw.ellipse((px - 5, py - 5, px + 5, py + 5), fill=color, outline="#ffffff")
        draw.text((x0 + pw / 2 - 95, y0 + ph + 28), "log2(completed commits)", fill="#17202a", font=body_font)
        draw.text((x0 + 5, y0 + 5), "log2 endpoint", fill="#52616b", font=small_font)
    legend_x = 455
    for idx, sf in enumerate(locked.SF_LEVELS):
        x = legend_x + idx * 160
        draw.ellipse((x, height - 43, x + 12, height - 31), fill=SF_COLORS[sf])
        draw.text((x + 20, height - 49), f"SF{sf}", fill="#17202a", font=body_font)
    image.save(output)


def draw_residuals(residuals: pd.DataFrame, endpoint: str, output: Path) -> None:
    width, height = 1750, 1060
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = locked.load_font(32, bold=True)
    panel_font = locked.load_font(20, bold=True)
    body_font = locked.load_font(17)
    small_font = locked.load_font(13)
    draw.text((50, 26), f"Residual diagnostics: {ENDPOINTS[endpoint]}", fill="#17202a", font=title_font)
    draw.text((50, 70), "Residual percent on original endpoint scale; each model has its own y-range", fill="#52616b", font=body_font)
    selected = residuals.loc[residuals["endpoint"] == endpoint]
    models = ("linear", "quadratic", "power")
    for row_index, fmt in enumerate(("iceberg", "delta")):
        for column_index, model in enumerate(models):
            x0 = 75 + column_index * 565
            y0 = 145 + row_index * 430
            pw, ph = 500, 330
            model_rows = selected.loc[
                (selected["table_format"] == fmt) & (selected["model"] == model)
            ]
            log_commits = np.log2(model_rows["completed_ingestion_commits"].to_numpy(dtype=float))
            xmin, xmax = float(log_commits.min()) - 0.15, float(log_commits.max()) + 0.15
            bound = max(0.5, float(np.max(np.abs(model_rows["residual_pct"]))) * 1.08)

            def sx(value: float) -> float:
                return x0 + (value - xmin) / (xmax - xmin) * pw

            def sy(value: float) -> float:
                return y0 + ph / 2 - value / bound * ph / 2

            draw.rectangle((x0, y0, x0 + pw, y0 + ph), fill="#fbfcfc", outline="#95a5a6", width=2)
            draw.line((x0, sy(0), x0 + pw, sy(0)), fill="#566573", width=2)
            draw.text(
                (x0 + 8, y0 - 31),
                f"{fmt.title()} / {model}",
                fill=MODEL_COLORS[model],
                font=panel_font,
            )
            draw.text((x0 + 6, y0 + 5), f"+/-{bound:.1f}%", fill="#52616b", font=small_font)
            for _, row in model_rows.iterrows():
                px = sx(math.log2(float(row["completed_ingestion_commits"])))
                py = sy(float(row["residual_pct"]))
                color = MODEL_COLORS[model]
                draw.ellipse((px - 4, py - 4, px + 4, py + 4), fill=color)
            draw.text((x0 + pw / 2 - 85, y0 + ph + 12), "log2(completed commits)", fill="#17202a", font=small_font)
    image.save(output)


def write_report(
    output: Path,
    checks: list[dict[str, object]],
    elasticities: pd.DataFrame,
    comparisons: pd.DataFrame,
    reconciliation: pd.DataFrame,
    generated_at: str,
) -> None:
    size = elasticities.loc[
        elasticities["endpoint"] == "metadata_total_size_mib_before"
    ].sort_values("table_format")
    files = elasticities.loc[
        elasticities["endpoint"] == "metadata_file_count_before"
    ].sort_values("table_format")
    lines = [
        "# Final Retained Metadata Footprint Analysis",
        "",
        f"Method version: `{METHOD_VERSION}`  ",
        f"Generated: {generated_at}  ",
        f"Scope: 72 canonical physical ingestion runs, 36 per format  ",
        f"Bootstrap: {locked.BOOTSTRAP_DRAWS:,} stratified run-level draws; seed `{locked.BOOTSTRAP_SEED}`",
        "",
        "> The endpoint is the retained physical metadata-directory footprint immediately before native maintenance. It is not active metadata, query-planning work, or an economic cost.",
        "",
        "## Integrity decision",
        "",
        f"All {len(checks)} locked and metadata-specific integrity checks passed before model fitting. The validated B10 reruns are included. The input exports and historical data were read only.",
        "",
        "## Primary model",
        "",
        "Each format is modeled separately with the locked equation:",
        "",
        "`log2(metadata_total_size_mib_before) = alpha + eta*log2(completed_ingestion_commits) + SF_FE + error`",
        "",
        "The independent unit is the physical ingestion run. SF50 is the reference category. The 95% intervals use BCa unless the locked fallback criteria require a percentile interval.",
        "",
        "| Format | Runs | Eta | 95% CI | CI method | R2 log2 | Adjusted R2 log2 | Original-scale RMSE MiB |",
        "|---|---:|---:|---:|---|---:|---:|---:|",
    ]
    for _, row in size.iterrows():
        lines.append(
            f"| {str(row['table_format']).title()} | {int(row['n_physical_runs'])} | {fmt_number(row['eta'], 6)} | "
            f"[{fmt_number(row['ci_low'], 6)}, {fmt_number(row['ci_high'], 6)}] | {row['ci_method']} | "
            f"{fmt_number(row['r_squared_native_response'], 6)} | {fmt_number(row['adjusted_r_squared_native_response'], 6)} | "
            f"{fmt_number(row['rmse_original_scale'], 2)} |"
        )
    lines.extend(
        [
            "",
            "Eta is an empirical elasticity conditional on SF and on the tested commit, retention, checkpoint, Spark, HDFS, and table-format settings. It is not a universal format constant.",
            "The intervals are exceptionally narrow because the locked stratified bootstrap resamples only the three physical repetitions inside each fixed SF/MOPT cell, while the observed within-cell metadata endpoints are highly reproducible. They quantify conditional replication uncertainty, not uncertainty under different infrastructure or retention regimes.",
            "",
            "![Retained metadata fit](metadata_footprint_loglog_sf_fixed_effects.png)",
            "",
            "## Metadata-file count",
            "",
            "The same locked log2/SF-fixed-effects structure was applied to the secondary file-count endpoint.",
            "",
            "| Format | File-count elasticity | 95% CI | CI method | R2 log2 | Original-scale RMSE files |",
            "|---|---:|---:|---|---:|---:|",
        ]
    )
    for _, row in files.iterrows():
        lines.append(
            f"| {str(row['table_format']).title()} | {fmt_number(row['eta'], 6)} | "
            f"[{fmt_number(row['ci_low'], 6)}, {fmt_number(row['ci_high'], 6)}] | {row['ci_method']} | "
            f"{fmt_number(row['r_squared_native_response'], 6)} | {fmt_number(row['rmse_original_scale'], 2)} |"
        )
    lines.extend(
        [
            "",
            "The file-count intervals collapse to the point estimates because all three repetitions have exactly the same metadata-file count in every SF/MOPT stratum. This is a degenerate conditional bootstrap distribution, not evidence that the relationship is uncertainty-free under other retention or infrastructure conditions.",
            "",
            "![Metadata file count fit](metadata_file_count_loglog_sf_fixed_effects.png)",
            "",
            "## Complementary model and residual analysis",
            "",
            "Linear and quadratic models use the original endpoint scale and commits in thousands. The power model uses log2 endpoint and log2 commits. All include the same SF fixed effects and all 36 runs per format. Original-scale RMSE and leave-one-run-out RMSE are supplied for descriptive comparison; native-response AIC/BIC must not be compared across original-scale and log-scale response models.",
            "",
            "### Retained metadata size",
            "",
            "| Format | Model | R2 original | Adjusted R2 original | RMSE MiB | LOOCV RMSE MiB | Max residual % | Nonpositive fits | Residual/fitted correlation |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for _, row in comparisons.loc[
        comparisons["endpoint"] == "metadata_total_size_mib_before"
    ].iterrows():
        lines.append(
            f"| {str(row['table_format']).title()} | {row['model']} | {fmt_number(row['r_squared_original_scale'], 6)} | "
            f"{fmt_number(row['adjusted_r_squared_original_scale'], 6)} | {fmt_number(row['rmse_original_scale'], 2)} | "
            f"{fmt_number(row['loocv_rmse_original_scale'], 2)} | {fmt_number(row['max_abs_residual_pct'], 2)} | "
            f"{int(row['nonpositive_fitted_count'])} | "
            f"{fmt_number(row['residual_fitted_correlation'], 4)} |"
        )
    lines.extend(
        [
            "",
            "![Metadata-size residuals](metadata_footprint_model_residuals.png)",
            "",
            "The linear and, at the smallest footprints, quadratic original-scale fits can produce nonphysical predictions near or below zero. This explains their extreme percentage residuals despite a small absolute error for the quadratic model. The power fit guarantees positive predictions and describes relative scaling, whereas the quadratic fit describes absolute curvature over the observed range. Neither is promoted to a universal asymptotic law.",
            "",
            "### Metadata file count",
            "",
            "| Format | Model | R2 original | Adjusted R2 original | RMSE files | LOOCV RMSE files | Max residual % | Nonpositive fits | Residual/fitted correlation |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for _, row in comparisons.loc[
        comparisons["endpoint"] == "metadata_file_count_before"
    ].iterrows():
        lines.append(
            f"| {str(row['table_format']).title()} | {row['model']} | {fmt_number(row['r_squared_original_scale'], 6)} | "
            f"{fmt_number(row['adjusted_r_squared_original_scale'], 6)} | {fmt_number(row['rmse_original_scale'], 2)} | "
            f"{fmt_number(row['loocv_rmse_original_scale'], 2)} | {fmt_number(row['max_abs_residual_pct'], 2)} | "
            f"{int(row['nonpositive_fitted_count'])} | "
            f"{fmt_number(row['residual_fitted_correlation'], 4)} |"
        )
    lines.extend(
        [
            "",
            "![File-count residuals](metadata_file_count_model_residuals.png)",
            "",
            "## Reconciliation with the previous power exponents",
            "",
            "| Format | Previous exponent | Exactly reproduced | Final SF-adjusted eta | Difference |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for _, old in reconciliation.sort_values("table_format").iterrows():
        current = size.loc[size["table_format"] == old["table_format"]].iloc[0]
        difference = float(current["eta"]) - float(old["prior_reported_exponent"])
        lines.append(
            f"| {str(old['table_format']).title()} | {fmt_number(old['prior_reported_exponent'], 4)} | "
            f"{fmt_number(old['exactly_reproduced_exponent'], 4)} | {fmt_number(current['eta'], 4)} | "
            f"{fmt_number(difference, 4)} |"
        )
    lines.extend(
        [
            "",
            "The earlier exponents are exactly reproducible from the same canonical measurements. They came from an unadjusted power fit over twelve SF/MOPT scenario means. The final model instead uses all 36 physical runs per format and controls SF categorically. Any difference is therefore caused by the locked estimand and model design, not by replacing the data. Because commit count is largely generated by SF/MOPT, the unadjusted exponent partly mixes commit scaling with scale-factor level differences.",
            "",
            "## Technical interpretation",
            "",
            "- Iceberg counts every regular file recursively retained under the table `metadata/` directory. Frequent commits create snapshots, manifest lists, manifests, and progressively larger table metadata JSON versions. Old physical metadata versions remained retained under the tested defaults.",
            "- Delta counts transaction-log JSON files and checkpoint-named files under `_delta_log/`. Incremental commit JSONs accumulate, while the default ten-commit cadence retains repeated full-state checkpoints that grow with table state during these short runs.",
            "- Consequently, superlinear retained-byte growth can coexist with an approximately linear growth in metadata-file count. File count and bytes represent different accumulation mechanisms.",
            "",
            "## Interpretation limits",
            "",
            "1. The endpoint is a physically retained directory footprint, not the minimum metadata required to reconstruct the current table and not active query-planning input.",
            "2. The formats count different native object classes. A cross-format byte ratio is not a like-for-like metadata-object efficiency comparison.",
            "3. Commit count, SF, and MOPT are structurally related. SF fixed effects reduce one source of confounding but do not turn eta into a causal or universal law.",
            "4. No historical file-type split is reconstructed for overwritten table directories. Aggregate historical measurements are used without estimating unavailable composition.",
            "5. The quadratic model is a descriptive fit over the observed commit range. Compatibility with quadratic growth does not establish an asymptotic O(C^2) law outside that range.",
            "6. The three repetitions per SF/MOPT cell limit uncertainty precision. Bootstrap draws preserve the physical-run unit and do not treat metadata files or commits as independent experiments.",
            "7. This analysis contains no economic valuation or cost model.",
            "",
            "## Reproducibility artifacts",
            "",
            "- `metadata_growth_run_level.csv`: canonical run-level inputs and endpoints.",
            "- `metadata_growth_cell_summary.csv`: mean, SD, and CV across the three physical repetitions.",
            "- `metadata_growth_primary_elasticities.csv`: eta estimates and locked intervals.",
            "- `metadata_growth_primary_coefficients.csv`: complete SF-fixed-effects coefficients.",
            "- `metadata_growth_secondary_model_comparison.csv`: linear, quadratic, and power diagnostics.",
            "- `metadata_growth_model_residuals.csv`: run-level fitted values and residuals.",
            "- `metadata_growth_prior_power_model_reconciliation.csv`: exact reproduction of the earlier exponents.",
            "- `metadata_growth_bootstrap_diagnostics.csv`: BCa/fallback diagnostics.",
            "- `integrity_checks.csv`: locked input and metadata-specific validation gates.",
            "- `analysis_run_manifest.json`: hashes and runtime versions.",
        ]
    )
    (output / "publication_metadata_growth_final_results.md").write_text(
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
    if len(frame) != 72 or frame["canonical_ingestion_run_id"].nunique() != 72:
        raise locked.IntegrityError("Metadata input does not contain 72 unique canonical runs")
    if frame[list(ENDPOINTS)].isna().any().any():
        raise locked.IntegrityError("Metadata endpoint contains missing values")
    if not (frame[list(ENDPOINTS)] > 0).all().all():
        raise locked.IntegrityError("Metadata endpoint contains non-positive values")
    expected_b10 = locked.EXPECTED_B10
    observed_b10 = set(
        frame.loc[frame["scenario_id"] == "B10", "canonical_ingestion_run_id"]
    )
    if observed_b10 != expected_b10:
        raise locked.IntegrityError("Metadata analysis B10 mapping differs from locked canonical B10")
    checks.extend(
        [
            {
                "check": "metadata_endpoint_mapping",
                "status": "PASS",
                "detail": "72/72 canonical runs mapped one-to-one to immediate pre-maintenance metadata fields",
            },
            {
                "check": "metadata_endpoint_positivity",
                "status": "PASS",
                "detail": "metadata_total_size_mib_before and metadata_file_count_before complete and positive",
            },
            {
                "check": "metadata_B10_mapping",
                "status": "PASS",
                "detail": ";".join(sorted(observed_b10)),
            },
        ]
    )

    plans = build_bootstrap_plans(frame)
    elasticity_rows = []
    coefficient_rows = []
    bootstrap_rows = []
    primary_fits: dict[tuple[str, str], dict[str, object]] = {}
    for fmt in ("iceberg", "delta"):
        subset = frame.loc[frame["table_format"] == fmt].reset_index(drop=True)
        for endpoint in ENDPOINTS:
            fit, draws, jackknife = bootstrap_power_coefficients(
                frame.reset_index(drop=True), fmt, endpoint, plans
            )
            primary_fits[(fmt, endpoint)] = fit
            names = fit["coefficient_names"]
            intervals = []
            for index, name in enumerate(names):
                interval = locked.bca_interval(
                    float(fit["coefficients"][index]), draws[:, index], jackknife[:, index]
                )
                intervals.append(interval)
                coefficient_row = {
                    "method_version": METHOD_VERSION,
                    "table_format": fmt,
                    "endpoint": endpoint,
                    "coefficient": name,
                    "estimate": float(fit["coefficients"][index]),
                }
                add_interval_columns(coefficient_row, interval)
                coefficient_rows.append(coefficient_row)
                diagnostic = {
                    "table_format": fmt,
                    "endpoint": endpoint,
                    "coefficient": name,
                }
                diagnostic.update(interval)
                bootstrap_rows.append(diagnostic)
            eta_index = names.index("log2_completed_ingestion_commits")
            eta_interval = intervals[eta_index]
            elasticity_rows.append(
                {
                    "method_version": METHOD_VERSION,
                    "table_format": fmt,
                    "endpoint": endpoint,
                    "n_physical_runs": len(subset),
                    "eta": float(fit["coefficients"][eta_index]),
                    **eta_interval,
                    "r_squared_native_response": fit["r_squared_native_response"],
                    "adjusted_r_squared_native_response": fit[
                        "adjusted_r_squared_native_response"
                    ],
                    "r_squared_original_scale": fit["r_squared_original_scale"],
                    "adjusted_r_squared_original_scale": fit[
                        "adjusted_r_squared_original_scale"
                    ],
                    "rmse_original_scale": fit["rmse_original_scale"],
                    "mae_original_scale": fit["mae_original_scale"],
                    "condition_number": fit["condition_number"],
                    "model": "log2_endpoint_on_log2_commits_plus_SF_fixed_effects",
                    "sf_reference": 50,
                }
            )

    elasticities = pd.DataFrame(elasticity_rows)
    coefficients = pd.DataFrame(coefficient_rows)
    bootstrap_diagnostics = pd.DataFrame(bootstrap_rows)
    summaries = cell_summary(frame)
    reconciliation = prior_power_reconciliation(frame)
    comparisons, residuals = model_comparisons(frame)
    checks.extend(
        [
            {
                "check": "primary_model_coverage",
                "status": "PASS",
                "detail": "2 formats x 2 endpoints; 36 physical runs per format",
            },
            {
                "check": "bootstrap_coverage",
                "status": "PASS",
                "detail": f"{locked.BOOTSTRAP_DRAWS} stratified draws; seed {locked.BOOTSTRAP_SEED}",
            },
            {
                "check": "prior_power_exponent_reproduction",
                "status": "PASS",
                "detail": "Iceberg 1.874732889279489; Delta 1.7343046399194524 reproduced exactly",
            },
        ]
    )

    output.mkdir(parents=True, exist_ok=False)
    run_columns = [
        "method_version",
        "table_format",
        "scenario_id",
        "scale_factor",
        "mopt",
        "replication",
        "canonical_run_key",
        "canonical_ingestion_run_id",
        "completed_ingestion_commits",
        "metadata_total_size_mib_before",
        "metadata_file_count_before",
        "data_file_count_before",
        "total_data_size_mib_before",
        "maintenance_metrics_source",
        "validation_status",
        "documented_exceptions",
    ]
    export_frame = frame.copy()
    export_frame.insert(0, "method_version", METHOD_VERSION)
    export_frame[run_columns].to_csv(
        output / "metadata_growth_run_level.csv", index=False, quoting=csv.QUOTE_MINIMAL
    )
    summaries.to_csv(
        output / "metadata_growth_cell_summary.csv", index=False, quoting=csv.QUOTE_MINIMAL
    )
    elasticities.to_csv(
        output / "metadata_growth_primary_elasticities.csv", index=False, quoting=csv.QUOTE_MINIMAL
    )
    coefficients.to_csv(
        output / "metadata_growth_primary_coefficients.csv", index=False, quoting=csv.QUOTE_MINIMAL
    )
    comparisons.to_csv(
        output / "metadata_growth_secondary_model_comparison.csv", index=False, quoting=csv.QUOTE_MINIMAL
    )
    residuals.to_csv(
        output / "metadata_growth_model_residuals.csv", index=False, quoting=csv.QUOTE_MINIMAL
    )
    reconciliation.to_csv(
        output / "metadata_growth_prior_power_model_reconciliation.csv",
        index=False,
        quoting=csv.QUOTE_MINIMAL,
    )
    bootstrap_diagnostics.to_csv(
        output / "metadata_growth_bootstrap_diagnostics.csv",
        index=False,
        quoting=csv.QUOTE_MINIMAL,
    )
    pd.DataFrame(checks).to_csv(
        output / "integrity_checks.csv", index=False, quoting=csv.QUOTE_MINIMAL
    )

    draw_loglog_fit(
        frame,
        coefficients,
        "metadata_total_size_mib_before",
        output / "metadata_footprint_loglog_sf_fixed_effects.png",
    )
    draw_loglog_fit(
        frame,
        coefficients,
        "metadata_file_count_before",
        output / "metadata_file_count_loglog_sf_fixed_effects.png",
    )
    draw_residuals(
        residuals,
        "metadata_total_size_mib_before",
        output / "metadata_footprint_model_residuals.png",
    )
    draw_residuals(
        residuals,
        "metadata_file_count_before",
        output / "metadata_file_count_model_residuals.png",
    )
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    write_report(
        output, checks, elasticities, comparisons, reconciliation, generated_at
    )

    output_hashes = {
        path.name: sha256(path)
        for path in sorted(output.iterdir())
        if path.is_file() and path.name != "analysis_run_manifest.json"
    }
    manifest_out = {
        "method_version": METHOD_VERSION,
        "generated_at_utc": generated_at,
        "analysis_type": "retained_metadata_footprint_not_active_metadata_or_economic_cost",
        "bootstrap_seed": locked.BOOTSTRAP_SEED,
        "bootstrap_draws": locked.BOOTSTRAP_DRAWS,
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
        json.dumps(manifest_out, indent=2, ensure_ascii=True), encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "output": str(output),
                "integrity_checks": len(checks),
                "canonical_runs": len(frame),
                "elasticity_rows": len(elasticities),
                "secondary_models": len(comparisons),
                "ci_methods": elasticities["ci_method"].value_counts().to_dict(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
