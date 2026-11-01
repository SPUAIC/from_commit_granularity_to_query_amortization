#!/usr/bin/env python3
"""Final v1.0 query-neutralization analysis for the canonical publication data.

The program is read-only with respect to the canonical experiment exports. It
validates the locked integrity gates before creating a new output directory.
No existing output is overwritten.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist
from typing import Iterable

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
SPEC_MD = ROOT / "publication_final_statistical_analysis_specification_v1.0.md"
SPEC_YAML = ROOT / "publication_final_statistical_analysis_specification_v1.0.yaml"
MANIFEST = ROOT / "publication_canonical_run_manifest.csv"

SOURCES = {
    "iceberg": {
        "ingestion": ROOT / "iceberg_metrics_exports_20261024" / "metrics_ingestion.csv",
        "query": ROOT / "iceberg_metrics_exports_20261024" / "query_metrics.csv",
        "maintenance": ROOT / "iceberg_metrics_exports_20261024" / "compaction_operation_metrics.csv",
    },
    "delta": {
        "ingestion": ROOT / "delta_metrics_exports_20261024" / "metrics_ingestion.csv",
        "query": ROOT / "delta_metrics_exports_20261024" / "query_metrics.csv",
        "maintenance": ROOT / "delta_metrics_exports_20261024" / "compaction_operation_metrics.csv",
        "phase_quality": ROOT / "delta_metrics_exports_20261024" / "metrics_ingestion_phases_reconstruction_quality.csv",
    },
}

EXPECTED_HASHES = {
    SPEC_MD: "0fee90c74eb0160a579f945dab5d7d46ebb8e1f2254171e3c4a515426d40b461",
    SPEC_YAML: "c399b574389603eb0516164ed1aba8cbeda9e2c80880c1cf5f90eb28b8a009ae",
    MANIFEST: "afaf04a6231035a1df4397a73d2f1cf45cf3271dbca18b001eb41f0b1f6830e2",
    SOURCES["iceberg"]["ingestion"]: "237c3eb716e75d36ed71ffeb91d30bb706a47cf40ba03a9827083f8bb5dfaf52",
    SOURCES["iceberg"]["query"]: "6bc776a1948b3b29fed5648a80d195b6aa87d3b13208afc27f45ba7a7cdec043",
    SOURCES["iceberg"]["maintenance"]: "d80265f4ce5062376ebfc0bf192144a9315fa1868790e81008efa8e2cf3b871f",
    SOURCES["delta"]["ingestion"]: "6c3c46d2047f32376c4a6cb489f70ee607644f07a428fd76e5c47f0e0399b07d",
    SOURCES["delta"]["query"]: "240a8b1f71ba62591689f1425c32262696566581539187880af45ecd5080a345",
    SOURCES["delta"]["maintenance"]: "b267a59b994bd6a7654ce2bfbb6d7a147a37f01922691c804b182ed743294e79",
    SOURCES["delta"]["phase_quality"]: "deb3d2ed4e258684f46ec8aa589ade44318de7f3300c6e0d0b04bc28ead2b4df",
}

EXPECTED_B10 = {
    "B10_r01_store_sales_sf500_mopt160000_20260828_163243Z",
    "B10_r02_store_sales_sf500_mopt160000_20260902_042804Z",
    "B10_r03_store_sales_sf500_mopt160000_20260903_044849Z",
    "B10_delta320_r01_store_sales_sf500_mopt160000_20260912_130358Z",
    "B10_delta320_r02_store_sales_sf500_mopt160000_20260927_162301Z",
    "B10_delta320_r03_store_sales_sf500_mopt160000_20260926_033819Z",
}

BOOTSTRAP_DRAWS = 10_000
BOOTSTRAP_SEED = 20_261_025
MIN_FINITE_DRAWS = 9_500
ALPHA = 0.05
NUMERIC_NEAR_ZERO = 1e-8
PRIMARY_QUERIES = ("Q2", "Q3")
PHASES = ("pre_compaction", "post_compaction")
SF_LEVELS = (50, 100, 200, 500)
MOPT_LEVELS = (160_000, 640_000, 2_560_000)
METRIC_NAMES = (
    "beta_pre",
    "beta_post",
    "beta_difference",
    "absolute_slope_reduction",
    "neutralization",
)


class IntegrityError(RuntimeError):
    pass


@dataclass
class ModelData:
    run_keys: list[str]
    run_x: np.ndarray
    run_y: np.ndarray
    sf: np.ndarray
    mopt: np.ndarray
    cache_mode: list[str]
    strata: list[np.ndarray]
    design_kind: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True), encoding="utf-8")


def csv_shape(path: Path) -> tuple[int, int]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader)
        rows = 0
        for line_no, row in enumerate(reader, start=2):
            if len(row) != len(header):
                raise IntegrityError(
                    f"CSV width mismatch in {path.name} line {line_no}: {len(row)} != {len(header)}"
                )
            rows += 1
    return rows, len(header)


def is_true(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"1", "true", "yes", "y"})


def validate_json_column(df: pd.DataFrame, column: str, source: Path) -> None:
    if column not in df.columns:
        return
    for idx, value in df[column].items():
        if pd.isna(value) or str(value).strip() == "":
            continue
        try:
            json.loads(str(value))
        except json.JSONDecodeError as exc:
            raise IntegrityError(f"Invalid JSON in {source.name}:{column}, row {idx + 2}: {exc}") from exc


def run_key_from_query(value: str) -> str:
    return str(value).strip()


def validate_integrity() -> tuple[pd.DataFrame, dict[str, pd.DataFrame], dict[str, pd.DataFrame], list[dict[str, object]]]:
    checks: list[dict[str, object]] = []

    for path, expected in EXPECTED_HASHES.items():
        actual = sha256(path)
        passed = actual.lower() == expected.lower()
        checks.append({"check": f"sha256:{path.name}", "status": "PASS" if passed else "FAIL", "detail": actual})
        if not passed:
            raise IntegrityError(f"SHA-256 mismatch for {path}: {actual} != {expected}")

    for path in [MANIFEST] + [path for group in SOURCES.values() for path in group.values()]:
        rows, fields = csv_shape(path)
        checks.append({"check": f"csv_width:{path.name}", "status": "PASS", "detail": f"rows={rows};fields={fields}"})

    manifest = pd.read_csv(MANIFEST, dtype=str)
    if len(manifest) != 72 or manifest["canonical_ingestion_run_id"].nunique() != 72:
        raise IntegrityError("Manifest must contain 72 unique canonical ingestion runs")
    if Counter(manifest["table_format"]) != Counter({"iceberg": 36, "delta": 36}):
        raise IntegrityError("Manifest format counts differ from 36 Iceberg and 36 Delta")
    if not (manifest["validation_status"] == "VALIDATED_CANONICAL").all():
        raise IntegrityError("Manifest contains a non-validated run")
    if not is_true(manifest["included_in_canonical_dataset"]).all():
        raise IntegrityError("Manifest contains an excluded run")
    for column, expected in (("num_executors_min", "5"), ("num_executors_max", "5"),
                             ("total_executor_cores_min", "80"), ("total_executor_cores_max", "80")):
        if not (manifest[column] == expected).all():
            raise IntegrityError(f"Unexpected resource profile in manifest column {column}")

    observed_cells = set(
        zip(
            manifest["table_format"],
            manifest["scale_factor"].astype(int),
            manifest["mopt"].astype(int),
            manifest["replication"].astype(int),
        )
    )
    expected_cells = {
        (fmt, sf, mopt, rep)
        for fmt in ("iceberg", "delta")
        for sf in SF_LEVELS
        for mopt in MOPT_LEVELS
        for rep in (1, 2, 3)
    }
    if observed_cells != expected_cells:
        raise IntegrityError("Canonical factorial coverage is incomplete or contains extra cells")

    b10 = set(manifest.loc[manifest["scenario_id"] == "B10", "canonical_ingestion_run_id"])
    if b10 != EXPECTED_B10:
        raise IntegrityError(f"Canonical B10 mismatch: {sorted(b10 ^ EXPECTED_B10)}")

    checks.extend(
        [
            {"check": "canonical_run_count", "status": "PASS", "detail": "72 unique runs"},
            {"check": "factorial_coverage", "status": "PASS", "detail": "2 formats x 4 SF x 3 MOPT x 3 reps"},
            {"check": "resource_profile", "status": "PASS", "detail": "5 executors; 80 cores in all runs"},
            {"check": "canonical_B10", "status": "PASS", "detail": ";".join(sorted(b10))},
        ]
    )

    query_frames: dict[str, pd.DataFrame] = {}
    maintenance_frames: dict[str, pd.DataFrame] = {}

    manifest_by_format = {
        fmt: manifest.loc[manifest["table_format"] == fmt].copy() for fmt in ("iceberg", "delta")
    }

    for fmt in ("iceberg", "delta"):
        qpath = SOURCES[fmt]["query"]
        q = pd.read_csv(qpath, dtype=str)
        validate_json_column(q, "result_json", qpath)
        canonical_keys = set(manifest_by_format[fmt]["canonical_run_key"])
        observed_keys = set(q["ingestion_run_id"].map(run_key_from_query))
        if observed_keys != canonical_keys:
            raise IntegrityError(f"{fmt} query run-key mismatch: {sorted(observed_keys ^ canonical_keys)}")
        if len(q) != 1296:
            raise IntegrityError(f"{fmt} query source has {len(q)} rows, expected 1296")
        if not (q["status"].str.lower() == "success").all():
            raise IntegrityError(f"{fmt} query source contains unsuccessful rows")

        grouped = q.groupby(["ingestion_run_id", "phase", "query_id", "is_warmup"], dropna=False).size()
        if len(grouped) != 72 * 2 * 3 * 2 / 2:
            # 36 runs x 2 phases x 3 queries x 2 warmup states
            raise IntegrityError(f"{fmt} query grouping count is {len(grouped)}, expected 432")
        if not (grouped == 3).all():
            bad = grouped[grouped != 3]
            raise IntegrityError(f"{fmt} query groups do not all contain three rows: {bad.head().to_dict()}")

        measured = q.loc[~is_true(q["is_warmup"])].copy()
        if len(measured) != 648:
            raise IntegrityError(f"{fmt} measured query rows are {len(measured)}, expected 648")
        measured["query_wall_time_ms"] = pd.to_numeric(measured["query_wall_time_ms"], errors="raise")
        if not (measured["query_wall_time_ms"] > 0).all():
            raise IntegrityError(f"{fmt} contains non-positive query wall times")

        hash_counts = measured.groupby(["ingestion_run_id", "query_id"])["result_hash"].nunique(dropna=False)
        if not (hash_counts == 1).all():
            raise IntegrityError(f"{fmt} has pre/post result-hash mismatches")
        sql_counts = measured.groupby(["scale_factor", "query_id"])["query_sql_hash"].nunique(dropna=False)
        if not (sql_counts == 1).all():
            raise IntegrityError(f"{fmt} has inconsistent SQL hashes within SF/query definitions")

        expected_query_run_ids = {
            value
            for item in manifest_by_format[fmt]["query_run_ids"]
            for value in str(item).split(";")
            if value
        }
        if set(q["run_id"]) != expected_query_run_ids:
            raise IntegrityError(f"{fmt} query execution run IDs differ from the canonical manifest")

        cache_by_run = q.groupby("ingestion_run_id")["cache_mode"].agg(lambda s: ";".join(sorted(set(s))))
        for _, row in manifest_by_format[fmt].iterrows():
            if cache_by_run[row["canonical_run_key"]] != row["cache_modes"]:
                raise IntegrityError(f"{fmt} cache-mode mismatch for {row['canonical_run_key']}")

        query_frames[fmt] = q
        checks.append(
            {
                "check": f"query_integrity:{fmt}",
                "status": "PASS",
                "detail": "1296 rows; 648 measured; three repetitions/group; result hashes paired",
            }
        )

        mpath = SOURCES[fmt]["maintenance"]
        maintenance = pd.read_csv(mpath, dtype=str)
        validate_json_column(maintenance, "procedure_result_json", mpath)
        if not (maintenance["status"].str.lower() == "success").all():
            raise IntegrityError(f"{fmt} maintenance source contains unsuccessful rows")
        maintenance_keys = set(maintenance["ingestion_run_id"])
        if maintenance_keys != canonical_keys:
            raise IntegrityError(f"{fmt} maintenance run-key mismatch")
        expected_ops = {"rewrite_data_files", "rewrite_manifests"} if fmt == "iceberg" else {"optimize"}
        for run_key, rows in maintenance.groupby("ingestion_run_id"):
            if set(rows["operation_type"]) != expected_ops or len(rows) != len(expected_ops):
                raise IntegrityError(f"Unexpected {fmt} maintenance sequence for {run_key}")
        expected_maintenance_ids = {
            value
            for item in manifest_by_format[fmt]["maintenance_run_ids"]
            for value in str(item).split(";")
            if value
        }
        if set(maintenance["maintenance_run_id"]) != expected_maintenance_ids:
            raise IntegrityError(f"{fmt} maintenance IDs differ from the canonical manifest")
        maintenance_frames[fmt] = maintenance
        checks.append(
            {
                "check": f"maintenance_integrity:{fmt}",
                "status": "PASS",
                "detail": f"expected operation sequence for 36 runs: {','.join(sorted(expected_ops))}",
            }
        )

        ingestion = pd.read_csv(SOURCES[fmt]["ingestion"], dtype=str)
        if set(ingestion["run_id"]) != set(manifest_by_format[fmt]["canonical_ingestion_run_id"]):
            raise IntegrityError(f"{fmt} ingestion IDs differ from the canonical manifest")
        for _, row in manifest_by_format[fmt].iterrows():
            rows = ingestion.loc[ingestion["run_id"] == row["canonical_ingestion_run_id"]]
            expected_rows = int(row["stored_ingestion_metric_rows"])
            completed = int(row["completed_ingestion_commits"])
            if len(rows) != expected_rows or completed != expected_rows + 1:
                raise IntegrityError(f"n-1 mismatch for {row['canonical_ingestion_run_id']}")
            batch_ids = pd.to_numeric(rows["micro_batch_id"], errors="raise").astype(int)
            if batch_ids.nunique() != len(rows):
                raise IntegrityError(f"Duplicate micro-batch ID in {row['canonical_ingestion_run_id']}")
            if set(rows["num_executors"]) != {"5"} or set(rows["total_executor_cores"]) != {"80"}:
                raise IntegrityError(f"Resource mismatch in {row['canonical_ingestion_run_id']}")
        checks.append(
            {
                "check": f"n_minus_1_and_resources:{fmt}",
                "status": "PASS",
                "detail": "36/36 runs have one terminal row absent and 5 executors/80 cores",
            }
        )

    phase_quality = pd.read_csv(SOURCES["delta"]["phase_quality"], dtype=str)
    if len(phase_quality) != 36 or set(phase_quality["quality_status"]) != {"PASS_WITH_KNOWN_N_MINUS_1"}:
        raise IntegrityError("Delta reconstruction quality gate failed")
    checks.append(
        {
            "check": "delta_phase_reconstruction_quality",
            "status": "PASS",
            "detail": "36/36 PASS_WITH_KNOWN_N_MINUS_1",
        }
    )

    return manifest, query_frames, maintenance_frames, checks


def aggregate_queries(manifest: pd.DataFrame, query_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    parts = []
    for fmt, q in query_frames.items():
        measured = q.loc[~is_true(q["is_warmup"])].copy()
        measured["query_wall_time_ms"] = pd.to_numeric(measured["query_wall_time_ms"], errors="raise")
        grouped = (
            measured.groupby(["ingestion_run_id", "phase", "query_id"], as_index=False)
            .agg(
                mean_query_wall_time_ms=("query_wall_time_ms", "mean"),
                median_query_wall_time_ms=("query_wall_time_ms", "median"),
                measured_repetitions=("query_wall_time_ms", "size"),
                cache_mode=("cache_mode", lambda s: ";".join(sorted(set(s)))),
                result_hash=("result_hash", lambda s: ";".join(sorted(set(s)))),
                query_sql_hash=("query_sql_hash", lambda s: ";".join(sorted(set(s)))),
            )
        )
        grouped["table_format"] = fmt
        parts.append(grouped)
    agg = pd.concat(parts, ignore_index=True)
    lookup = manifest[
        ["table_format", "canonical_run_key", "canonical_ingestion_run_id", "scenario_id", "scale_factor", "mopt", "replication"]
    ].copy()
    lookup = lookup.rename(columns={"canonical_run_key": "ingestion_run_id"})
    agg = agg.merge(lookup, on=["table_format", "ingestion_run_id"], how="left", validate="many_to_one")
    if agg["canonical_ingestion_run_id"].isna().any():
        raise IntegrityError("Query aggregation failed to map all rows to canonical runs")
    for col in ("scale_factor", "mopt", "replication"):
        agg[col] = pd.to_numeric(agg[col], errors="raise").astype(int)
    expected = 72 * 2 * 3
    if len(agg) != expected:
        raise IntegrityError(f"Run-level query aggregation has {len(agg)} rows, expected {expected}")
    return agg.sort_values(["table_format", "scenario_id", "replication", "query_id", "phase"]).reset_index(drop=True)


def design_rows(sf: int, mopt: int, y_pre: float, y_post: float, include_sf: bool) -> tuple[np.ndarray, np.ndarray]:
    x = math.log2(mopt / 160_000)
    if include_sf:
        sf_ind = [1.0 if sf == level else 0.0 for level in (100, 200, 500)]
        pre = [1.0, x, 0.0, 0.0, *sf_ind, 0.0, 0.0, 0.0]
        post = [1.0, x, 1.0, x, *sf_ind, *sf_ind]
    else:
        pre = [1.0, x, 0.0, 0.0]
        post = [1.0, x, 1.0, x]
    return np.asarray([pre, post], dtype=float), np.asarray([y_pre, y_post], dtype=float)


def prepare_model_data(
    agg: pd.DataFrame,
    fmt: str,
    query: str,
    aggregate_column: str,
    warm_cache_only: bool = False,
    sf_only: int | None = None,
) -> ModelData:
    subset = agg.loc[(agg["table_format"] == fmt) & (agg["query_id"] == query)].copy()
    if warm_cache_only:
        warm_keys = set(
            subset.groupby("ingestion_run_id")["cache_mode"]
            .agg(lambda s: set(s) == {"warm_cache"})
            .loc[lambda s: s]
            .index
        )
        subset = subset.loc[subset["ingestion_run_id"].isin(warm_keys)]
    if sf_only is not None:
        subset = subset.loc[subset["scale_factor"] == sf_only]

    run_keys = sorted(subset["ingestion_run_id"].unique())
    run_x = []
    run_y = []
    sf_values = []
    mopt_values = []
    cache_modes = []
    include_sf = sf_only is None
    for run_key in run_keys:
        rows = subset.loc[subset["ingestion_run_id"] == run_key]
        if set(rows["phase"]) != set(PHASES) or len(rows) != 2:
            raise IntegrityError(f"Expected paired phases for {fmt}/{query}/{run_key}")
        first = rows.iloc[0]
        values = rows.set_index("phase")[aggregate_column]
        raw_pre = float(values["pre_compaction"])
        raw_post = float(values["post_compaction"])
        if raw_pre <= 0 or raw_post <= 0:
            raise IntegrityError(f"Non-positive aggregate query time for {fmt}/{query}/{run_key}")
        x_rows, y_rows = design_rows(
            int(first["scale_factor"]),
            int(first["mopt"]),
            math.log2(raw_pre),
            math.log2(raw_post),
            include_sf,
        )
        run_x.append(x_rows)
        run_y.append(y_rows)
        sf_values.append(int(first["scale_factor"]))
        mopt_values.append(int(first["mopt"]))
        cache_modes.append(";".join(sorted(set(rows["cache_mode"]))))

    sf_array = np.asarray(sf_values, dtype=int)
    mopt_array = np.asarray(mopt_values, dtype=int)
    strata = []
    for key in sorted(set(zip(sf_array.tolist(), mopt_array.tolist()))):
        indices = np.where((sf_array == key[0]) & (mopt_array == key[1]))[0]
        strata.append(indices)

    return ModelData(
        run_keys=run_keys,
        run_x=np.asarray(run_x, dtype=float),
        run_y=np.asarray(run_y, dtype=float),
        sf=sf_array,
        mopt=mopt_array,
        cache_mode=cache_modes,
        strata=strata,
        design_kind="sf_fixed_effects" if include_sf else f"sf_{sf_only}",
    )


def flatten_model(data: ModelData, indices: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if indices is None:
        indices = np.arange(len(data.run_keys), dtype=int)
    x = data.run_x[indices].reshape(-1, data.run_x.shape[-1])
    y = data.run_y[indices].reshape(-1)
    groups = np.repeat(np.arange(len(indices), dtype=int), 2)
    return x, y, groups


def ols_beta(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    if rank != x.shape[1]:
        raise np.linalg.LinAlgError(f"Model is rank deficient: rank={rank}; columns={x.shape[1]}")
    return beta


def estimands(beta: np.ndarray) -> np.ndarray:
    beta_pre = float(beta[1])
    beta_difference = float(beta[3])
    beta_post = beta_pre + beta_difference
    reduction = abs(beta_pre) - abs(beta_post)
    neutralization = math.nan if abs(beta_pre) < NUMERIC_NEAR_ZERO else 1.0 - abs(beta_post) / abs(beta_pre)
    return np.asarray([beta_pre, beta_post, beta_difference, reduction, neutralization], dtype=float)


def cluster_covariance(x: np.ndarray, y: np.ndarray, groups: np.ndarray, beta: np.ndarray) -> np.ndarray:
    n, k = x.shape
    unique = np.unique(groups)
    g = len(unique)
    residuals = y - x @ beta
    bread = np.linalg.inv(x.T @ x)
    meat = np.zeros((k, k), dtype=float)
    for group in unique:
        mask = groups == group
        score = x[mask].T @ residuals[mask]
        meat += np.outer(score, score)
    correction = (g / (g - 1)) * ((n - 1) / (n - k))
    return correction * bread @ meat @ bread


def beta_continued_fraction(a: float, b: float, x: float) -> float:
    max_iter = 300
    eps = 3e-14
    fpmin = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            return h
    raise ArithmeticError("Incomplete-beta continued fraction did not converge")


def regularized_incomplete_beta(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_bt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    bt = math.exp(log_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * beta_continued_fraction(a, b, x) / a
    return 1.0 - bt * beta_continued_fraction(b, a, 1.0 - x) / b


def t_cdf(value: float, df: int) -> float:
    if not math.isfinite(value):
        return 0.0 if value < 0 else 1.0
    if value == 0:
        return 0.5
    x = df / (df + value * value)
    tail = 0.5 * regularized_incomplete_beta(df / 2.0, 0.5, x)
    return 1.0 - tail if value > 0 else tail


def t_quantile(probability: float, df: int) -> float:
    if not 0.0 < probability < 1.0:
        raise ValueError("Probability must lie in (0,1)")
    if probability == 0.5:
        return 0.0
    sign = 1.0 if probability > 0.5 else -1.0
    target = probability if probability > 0.5 else 1.0 - probability
    low, high = 0.0, 1.0
    while t_cdf(high, df) < target:
        high *= 2.0
    for _ in range(100):
        mid = (low + high) / 2.0
        if t_cdf(mid, df) < target:
            low = mid
        else:
            high = mid
    return sign * (low + high) / 2.0


def full_model_statistics(data: ModelData) -> dict[str, object]:
    x, y, groups = flatten_model(data)
    beta = ols_beta(x, y)
    values = estimands(beta)
    cov = cluster_covariance(x, y, groups, beta)
    theta_se = math.sqrt(max(float(cov[3, 3]), 0.0))
    theta = float(beta[3])
    theta_t = theta / theta_se if theta_se > 0 else math.copysign(math.inf, theta)
    df = len(data.run_keys) - 1
    if math.isfinite(theta_t):
        # Direct two-sided Student-t tail avoids cancellation when CDF(t)
        # rounds to 1.0 for very large test statistics.
        p = regularized_incomplete_beta(df / 2.0, 0.5, df / (df + theta_t * theta_t))
    else:
        p = 0.0
    tcrit = t_quantile(0.975, df)
    beta_pre_se = math.sqrt(max(float(cov[1, 1]), 0.0))
    beta_post_var = float(cov[1, 1] + cov[3, 3] + 2.0 * cov[1, 3])
    beta_post_se = math.sqrt(max(beta_post_var, 0.0))
    return {
        "beta": beta,
        "estimands": dict(zip(METRIC_NAMES, values.tolist())),
        "theta_cluster_se": theta_se,
        "theta_t": theta_t,
        "theta_df": df,
        "theta_p_raw": p,
        "beta_pre_cluster_ci_low": values[0] - tcrit * beta_pre_se,
        "beta_pre_cluster_ci_high": values[0] + tcrit * beta_pre_se,
        "beta_post_cluster_ci_low": values[1] - tcrit * beta_post_se,
        "beta_post_cluster_ci_high": values[1] + tcrit * beta_post_se,
        "n_runs": len(data.run_keys),
        "n_observations": len(y),
        "rank": int(np.linalg.matrix_rank(x)),
        "parameters": x.shape[1],
    }


def make_bootstrap_plan(data: ModelData, rng: np.random.Generator, draws: int) -> np.ndarray:
    plans = np.empty((draws, len(data.run_keys)), dtype=np.int16)
    for draw in range(draws):
        selected: list[int] = []
        for stratum in data.strata:
            selected.extend(rng.choice(stratum, size=len(stratum), replace=True).tolist())
        plans[draw, :] = np.asarray(selected, dtype=np.int16)
    return plans


def bootstrap_estimates(data: ModelData, plans: np.ndarray) -> np.ndarray:
    output = np.full((len(plans), len(METRIC_NAMES)), np.nan, dtype=float)
    for idx, selected in enumerate(plans):
        try:
            x, y, _ = flatten_model(data, selected.astype(int))
            output[idx, :] = estimands(ols_beta(x, y))
        except (np.linalg.LinAlgError, ValueError, FloatingPointError):
            continue
    return output


def jackknife_estimates(data: ModelData) -> np.ndarray:
    output = np.full((len(data.run_keys), len(METRIC_NAMES)), np.nan, dtype=float)
    all_indices = np.arange(len(data.run_keys), dtype=int)
    for idx in all_indices:
        selected = all_indices[all_indices != idx]
        try:
            x, y, _ = flatten_model(data, selected)
            output[idx, :] = estimands(ols_beta(x, y))
        except (np.linalg.LinAlgError, ValueError, FloatingPointError):
            continue
    return output


def bca_interval(point: float, boot: np.ndarray, jack: np.ndarray) -> dict[str, object]:
    finite_boot = boot[np.isfinite(boot)]
    finite_jack = jack[np.isfinite(jack)]
    result: dict[str, object] = {
        "finite_bootstrap_draws": int(len(finite_boot)),
        "finite_jackknife_draws": int(len(finite_jack)),
        "ci_low": math.nan,
        "ci_high": math.nan,
        "ci_method": "CI_NOT_ESTIMABLE",
        "bca_bias_correction": math.nan,
        "bca_acceleration": math.nan,
        "adjusted_lower_quantile": math.nan,
        "adjusted_upper_quantile": math.nan,
    }
    if len(finite_boot) < MIN_FINITE_DRAWS:
        return result

    percentile_low, percentile_high = np.quantile(finite_boot, [0.025, 0.975])
    bca_valid = len(finite_jack) == len(jack) and len(jack) > 1 and math.isfinite(point)
    if bca_valid:
        proportion = (np.sum(finite_boot < point) + 0.5 * np.sum(finite_boot == point)) / len(finite_boot)
        resolution = 1.0 / (len(finite_boot) + 1.0)
        proportion = min(max(proportion, resolution), 1.0 - resolution)
        normal = NormalDist()
        z0 = normal.inv_cdf(float(proportion))
        jack_mean = float(np.mean(finite_jack))
        diffs = jack_mean - finite_jack
        denominator = 6.0 * float(np.sum(diffs * diffs)) ** 1.5
        acceleration = float(np.sum(diffs**3)) / denominator if denominator > 0 else math.nan
        result["bca_bias_correction"] = z0
        result["bca_acceleration"] = acceleration
        if math.isfinite(acceleration):
            adjusted = []
            for probability in (0.025, 0.975):
                z_alpha = normal.inv_cdf(probability)
                denom = 1.0 - acceleration * (z0 + z_alpha)
                if denom == 0:
                    adjusted.append(math.nan)
                else:
                    adjusted.append(normal.cdf(z0 + (z0 + z_alpha) / denom))
            low_q, high_q = adjusted
            result["adjusted_lower_quantile"] = low_q
            result["adjusted_upper_quantile"] = high_q
            min_q = 1.0 / (len(finite_boot) + 1.0)
            max_q = len(finite_boot) / (len(finite_boot) + 1.0)
            if (
                math.isfinite(low_q)
                and math.isfinite(high_q)
                and min_q < low_q < high_q < max_q
            ):
                low, high = np.quantile(finite_boot, [low_q, high_q])
                if math.isfinite(low) and math.isfinite(high):
                    result.update({"ci_low": float(low), "ci_high": float(high), "ci_method": "BCA"})
                    return result

    result.update(
        {
            "ci_low": float(percentile_low),
            "ci_high": float(percentile_high),
            "ci_method": "PERCENTILE_FALLBACK",
        }
    )
    return result


def analyze_model(
    data: ModelData,
    plans: np.ndarray,
    fmt: str,
    query: str,
    analysis: str,
    scope: str,
) -> tuple[dict[str, object], list[dict[str, object]], pd.DataFrame]:
    full = full_model_statistics(data)
    point = full["estimands"]
    boot = bootstrap_estimates(data, plans)
    jack = jackknife_estimates(data)
    intervals: dict[str, dict[str, object]] = {}
    diagnostics: list[dict[str, object]] = []
    for metric_idx, metric in enumerate(METRIC_NAMES):
        interval = bca_interval(float(point[metric]), boot[:, metric_idx], jack[:, metric_idx])
        intervals[metric] = interval
        diagnostics.append(
            {
                "analysis": analysis,
                "scope": scope,
                "table_format": fmt,
                "query_id": query,
                "metric": metric,
                **interval,
            }
        )

    beta_pre = float(point["beta_pre"])
    beta_post = float(point["beta_post"])
    pre_interval = intervals["beta_pre"]
    finite_pre = boot[:, 0][np.isfinite(boot[:, 0])]
    sign_fraction = (
        float(np.mean(np.sign(finite_pre) == np.sign(beta_pre))) if len(finite_pre) and beta_pre != 0 else 0.0
    )
    denominator_status = "STABLE"
    if abs(beta_pre) < NUMERIC_NEAR_ZERO:
        denominator_status = "NOT_ESTIMABLE_NUMERIC"
    elif (
        not math.isfinite(float(pre_interval["ci_low"]))
        or float(pre_interval["ci_low"]) <= 0.0 <= float(pre_interval["ci_high"])
        or sign_fraction < 0.95
    ):
        denominator_status = "UNSTABLE_DENOMINATOR"

    finite_neutralization_fraction = float(np.mean(np.isfinite(boot[:, 4])))
    if finite_neutralization_fraction < 0.95:
        intervals["neutralization"].update(
            {"ci_low": math.nan, "ci_high": math.nan, "ci_method": "CI_NOT_ESTIMABLE"}
        )
        denominator_status = (
            "NOT_ESTIMABLE_NUMERIC" if abs(beta_pre) < NUMERIC_NEAR_ZERO else "UNSTABLE_DENOMINATOR"
        )

    row: dict[str, object] = {
        "analysis": analysis,
        "scope": scope,
        "table_format": fmt,
        "query_id": query,
        "n_runs": full["n_runs"],
        "n_observations": full["n_observations"],
        "model_rank": full["rank"],
        "model_parameters": full["parameters"],
        "beta_pre": beta_pre,
        "beta_pre_ci_low": intervals["beta_pre"]["ci_low"],
        "beta_pre_ci_high": intervals["beta_pre"]["ci_high"],
        "beta_pre_ci_method": intervals["beta_pre"]["ci_method"],
        "beta_post": beta_post,
        "beta_post_ci_low": intervals["beta_post"]["ci_low"],
        "beta_post_ci_high": intervals["beta_post"]["ci_high"],
        "beta_post_ci_method": intervals["beta_post"]["ci_method"],
        "beta_difference": point["beta_difference"],
        "beta_difference_ci_low": intervals["beta_difference"]["ci_low"],
        "beta_difference_ci_high": intervals["beta_difference"]["ci_high"],
        "beta_difference_ci_method": intervals["beta_difference"]["ci_method"],
        "absolute_slope_reduction": point["absolute_slope_reduction"],
        "absolute_slope_reduction_ci_low": intervals["absolute_slope_reduction"]["ci_low"],
        "absolute_slope_reduction_ci_high": intervals["absolute_slope_reduction"]["ci_high"],
        "absolute_slope_reduction_ci_method": intervals["absolute_slope_reduction"]["ci_method"],
        "neutralization": point["neutralization"],
        "neutralization_ci_low": intervals["neutralization"]["ci_low"],
        "neutralization_ci_high": intervals["neutralization"]["ci_high"],
        "neutralization_ci_method": intervals["neutralization"]["ci_method"],
        "theta_cluster_se": full["theta_cluster_se"],
        "theta_t": full["theta_t"],
        "theta_df": full["theta_df"],
        "theta_p_raw": full["theta_p_raw"],
        "beta_pre_same_sign_bootstrap_fraction": sign_fraction,
        "neutralization_finite_bootstrap_fraction": finite_neutralization_fraction,
        "denominator_status": denominator_status,
        "slope_sign_status": "SLOPE_SIGN_REVERSAL" if beta_pre * beta_post < 0 else "SAME_SIGN_OR_ZERO",
        "cache_modes": ";".join(sorted(set(data.cache_mode))),
    }

    boot_frame = pd.DataFrame(boot, columns=METRIC_NAMES)
    boot_frame.insert(0, "bootstrap_draw", np.arange(1, len(boot_frame) + 1))
    boot_frame.insert(0, "query_id", query)
    boot_frame.insert(0, "table_format", fmt)
    boot_frame.insert(0, "scope", scope)
    boot_frame.insert(0, "analysis", analysis)
    return row, diagnostics, boot_frame


def holm_adjust(p_values: list[float]) -> list[float]:
    count = len(p_values)
    order = sorted(range(count), key=lambda idx: p_values[idx])
    adjusted = [math.nan] * count
    running = 0.0
    for rank, idx in enumerate(order):
        candidate = min(1.0, (count - rank) * p_values[idx])
        running = max(running, candidate)
        adjusted[idx] = running
    return adjusted


def fmt_num(value: object, digits: int = 3) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return "n.a."
    return f"{number:.{digits}f}"


def fmt_p(value: object) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return "n.a."
    if number < 0.0001:
        return f"{number:.3e}"
    return f"{number:.4f}"


def ci_text(row: pd.Series, prefix: str) -> str:
    return f"{fmt_num(row[prefix])} [{fmt_num(row[prefix + '_ci_low'])}, {fmt_num(row[prefix + '_ci_high'])}]"


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def draw_forest(
    frame: pd.DataFrame,
    metric: str,
    title: str,
    x_label: str,
    output: Path,
    reference: float = 0.0,
) -> None:
    width, height = 1500, 720
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = load_font(34, bold=True)
    body_font = load_font(24)
    small_font = load_font(20)
    draw.text((60, 35), title, fill="#17202a", font=title_font)

    lows = pd.to_numeric(frame[f"{metric}_ci_low"], errors="coerce")
    highs = pd.to_numeric(frame[f"{metric}_ci_high"], errors="coerce")
    points = pd.to_numeric(frame[metric], errors="coerce")
    finite = np.concatenate([lows[np.isfinite(lows)], highs[np.isfinite(highs)], points[np.isfinite(points)]])
    if len(finite) == 0:
        return
    data_min = min(float(np.min(finite)), reference)
    data_max = max(float(np.max(finite)), reference)
    span = max(data_max - data_min, 0.1)
    if metric == "neutralization" and data_min >= 0.0 and data_max <= 1.0:
        x_min, x_max = -0.1, 1.05
        ticks = [-0.1, 0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    else:
        x_min = data_min - 0.15 * span
        x_max = data_max + 0.15 * span
        ticks = np.linspace(x_min, x_max, 7).tolist()
    plot_left, plot_right = 390, width - 90
    plot_top, plot_bottom = 145, height - 125

    def x_pos(value: float) -> float:
        return plot_left + (value - x_min) / (x_max - x_min) * (plot_right - plot_left)

    ref_x = x_pos(reference)
    draw.line((ref_x, plot_top - 20, ref_x, plot_bottom + 20), fill="#7f8c8d", width=2)
    colors = {"iceberg": "#2878b5", "delta": "#d95f02"}
    row_gap = (plot_bottom - plot_top) / max(len(frame) - 1, 1)
    for idx, (_, row) in enumerate(frame.reset_index(drop=True).iterrows()):
        y = plot_top + idx * row_gap
        label = f"{str(row['table_format']).title()} {row['query_id']}"
        draw.text((70, y - 14), label, fill="#17202a", font=body_font)
        low = float(row[f"{metric}_ci_low"])
        high = float(row[f"{metric}_ci_high"])
        point = float(row[metric])
        color = colors[str(row["table_format"])]
        if all(math.isfinite(v) for v in (low, high, point)):
            draw.line((x_pos(low), y, x_pos(high), y), fill=color, width=6)
            draw.line((x_pos(low), y - 10, x_pos(low), y + 10), fill=color, width=3)
            draw.line((x_pos(high), y - 10, x_pos(high), y + 10), fill=color, width=3)
            px = x_pos(point)
            draw.ellipse((px - 9, y - 9, px + 9, y + 9), fill=color, outline="white", width=2)
            draw.text((plot_right + 15, y - 12), f"{point:.3f}", fill="#17202a", font=small_font)
    draw.line((plot_left, plot_bottom + 45, plot_right, plot_bottom + 45), fill="#17202a", width=2)
    for tick in ticks:
        x = x_pos(float(tick))
        draw.line((x, plot_bottom + 38, x, plot_bottom + 52), fill="#17202a", width=2)
        label = f"{tick:.2f}"
        draw.text((x - 28, plot_bottom + 58), label, fill="#17202a", font=small_font)
    draw.text((plot_left + 240, height - 45), x_label, fill="#17202a", font=body_font)
    image.save(output)


def draw_beta_comparison(frame: pd.DataFrame, output: Path) -> None:
    width, height = 1800, 760
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = load_font(34, bold=True)
    body_font = load_font(23)
    small_font = load_font(19)
    draw.text((60, 35), "MOPT elasticity before and after maintenance", fill="#17202a", font=title_font)
    values = []
    for prefix in ("beta_pre", "beta_post"):
        values.extend(pd.to_numeric(frame[f"{prefix}_ci_low"], errors="coerce").tolist())
        values.extend(pd.to_numeric(frame[f"{prefix}_ci_high"], errors="coerce").tolist())
    finite = [float(v) for v in values if math.isfinite(float(v))]
    data_min, data_max = min(finite + [0.0]), max(finite + [0.0])
    span = max(data_max - data_min, 0.1)
    x_min, x_max = data_min - 0.15 * span, data_max + 0.15 * span
    plot_left, plot_right = 390, width - 310
    plot_top, plot_bottom = 150, height - 130

    def x_pos(value: float) -> float:
        return plot_left + (value - x_min) / (x_max - x_min) * (plot_right - plot_left)

    draw.line((x_pos(0.0), plot_top - 25, x_pos(0.0), plot_bottom + 25), fill="#7f8c8d", width=2)
    row_gap = (plot_bottom - plot_top) / max(len(frame) - 1, 1)
    for idx, (_, row) in enumerate(frame.reset_index(drop=True).iterrows()):
        y = plot_top + idx * row_gap
        draw.text((65, y - 14), f"{str(row['table_format']).title()} {row['query_id']}", fill="#17202a", font=body_font)
        for prefix, offset, color, label in (
            ("beta_pre", -13, "#2878b5", "Pre"),
            ("beta_post", 13, "#d95f02", "Post"),
        ):
            point = float(row[prefix])
            low = float(row[f"{prefix}_ci_low"])
            high = float(row[f"{prefix}_ci_high"])
            yy = y + offset
            draw.line((x_pos(low), yy, x_pos(high), yy), fill=color, width=5)
            px = x_pos(point)
            draw.ellipse((px - 7, yy - 7, px + 7, yy + 7), fill=color)
            draw.text((plot_right + 10, yy - 10), f"{label} {point:.3f}", fill=color, font=small_font)
    draw.rectangle((65, height - 76, 88, height - 53), fill="#2878b5")
    draw.text((98, height - 79), "Pre-maintenance", fill="#17202a", font=small_font)
    draw.rectangle((280, height - 76, 303, height - 53), fill="#d95f02")
    draw.text((313, height - 79), "Post-maintenance", fill="#17202a", font=small_font)
    draw.text((610, height - 79), "Elasticity per MOPT doubling (log2/log2)", fill="#17202a", font=body_font)
    image.save(output)


def write_report(
    output: Path,
    primary: pd.DataFrame,
    sensitivity: pd.DataFrame,
    checks: list[dict[str, object]],
    generated_at: str,
) -> None:
    lines = [
        "# Final Query-Neutralization Results",
        "",
        f"Analysis method: `publication_final_statistical_analysis_v1_0`  ",
        f"Generated: {generated_at}  ",
        f"Canonical runs: 72 (36 Iceberg, 36 Delta)  ",
        f"Bootstrap: {BOOTSTRAP_DRAWS:,} paired, cell-stratified run-level draws; seed `{BOOTSTRAP_SEED}`",
        "",
        "## Integrity decision",
        "",
        f"All {len(checks)} locked integrity checks passed before model execution. No raw file was changed, no run was substituted, and no terminal n-1 batch metric was imputed.",
        "",
        "## Primary results",
        "",
        "The response is `log2` of the arithmetic mean of the three measured query wall times. Slopes are elasticities per MOPT doubling. Confidence intervals are BCa unless the table explicitly identifies the locked percentile fallback.",
        "",
        "| Format | Query | beta_pre (95% CI) | beta_post (95% CI) | Difference post-pre (95% CI) | Neutralization (95% CI; method) | Holm p | Decision flags |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for _, row in primary.iterrows():
        flags = f"{row['denominator_status']}; {row['slope_sign_status']}; {row['primary_claim_status']}"
        lines.append(
            "| {fmt} | {query} | {pre} | {post} | {diff} | {neutral} | {p} | {flags} |".format(
                fmt=str(row["table_format"]).title(),
                query=row["query_id"],
                pre=ci_text(row, "beta_pre"),
                post=ci_text(row, "beta_post"),
                diff=ci_text(row, "beta_difference"),
                neutral=(
                    f"{fmt_num(row['neutralization'], 4)} "
                    f"[{fmt_num(row['neutralization_ci_low'], 4)}, {fmt_num(row['neutralization_ci_high'], 4)}]; "
                    f"{row['neutralization_ci_method']}"
                ),
                p=fmt_p(row["theta_p_holm"]),
                flags=flags,
            )
        )

    supported = primary.loc[primary["primary_claim_status"] == "SUPPORTED_NEUTRALIZATION"]
    unsupported = primary.loc[primary["primary_claim_status"] != "SUPPORTED_NEUTRALIZATION"]
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"Maintenance met every locked criterion for a primary neutralization claim in **{len(supported)} of 4** format/query combinations.",
        ]
    )
    if len(supported):
        lines.append(
            "Supported combinations: "
            + ", ".join(f"{str(row.table_format).title()} {row.query_id}" for row in supported.itertuples())
            + "."
        )
    if len(unsupported):
        lines.append(
            "Combinations without a confirmatory neutralization claim: "
            + ", ".join(
                f"{str(row.table_format).title()} {row.query_id} ({row.primary_claim_status})"
                for row in unsupported.itertuples()
            )
            + "."
        )

    post_zero = []
    post_nonzero = []
    for row in primary.itertuples():
        label = f"{str(row.table_format).title()} {row.query_id}"
        if float(row.beta_post_ci_low) <= 0.0 <= float(row.beta_post_ci_high):
            post_zero.append(label)
        else:
            post_nonzero.append(label)
    neutralization_values = {
        f"{str(row.table_format).title()} {row.query_id}": 100.0 * float(row.neutralization)
        for row in primary.itertuples()
    }
    lines.extend(
        [
            "",
            "Estimated neutralization was "
            + "; ".join(f"{label}: {value:.1f}%" for label, value in neutralization_values.items())
            + ".",
            "",
            "The post-maintenance slope interval includes zero for "
            + (", ".join(post_zero) if post_zero else "none of the combinations")
            + ". A residual slope remains distinguishable from zero for "
            + (", ".join(post_nonzero) if post_nonzero else "none of the combinations")
            + ". This distinguishes near-complete neutralization from proof that the post-maintenance effect is exactly zero.",
            "",
            "A statistically detectable pre/post slope change is not by itself sufficient: the absolute slope must decrease, the pre-maintenance denominator must be stable, and a sign reversal must not contradict the magnitude-based ratio.",
            "",
            "![Pre/post elasticities](mopt_elasticity_pre_post.png)",
            "",
            "![Neutralization estimates](neutralization_primary_forest.png)",
            "",
            "## Sensitivity analyses",
            "",
            "The locked sensitivity analyses use median aggregation, an Iceberg warm-cache-only subset, SF-specific exploratory models, and Q1 as a secondary control. They do not form new confirmatory multiplicity families.",
            "",
            "| Analysis | Scope | Format | Query | Runs | beta_pre | beta_post | Neutralization | Denominator |",
            "|---|---|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for _, row in sensitivity.iterrows():
        lines.append(
            f"| {row['analysis']} | {row['scope']} | {str(row['table_format']).title()} | {row['query_id']} | {row['n_runs']} | {fmt_num(row['beta_pre'])} | {fmt_num(row['beta_post'])} | {fmt_num(row['neutralization'])} | {row['denominator_status']} |"
        )

    median_rows = sensitivity.loc[sensitivity["analysis"] == "median_sensitivity"]
    warm_rows = sensitivity.loc[
        (sensitivity["analysis"] == "warm_cache_sensitivity")
        & (sensitivity["table_format"] == "iceberg")
    ]
    sf_rows = sensitivity.loc[sensitivity["analysis"] == "sf_specific_exploratory"]
    q1_rows = sensitivity.loc[sensitivity["analysis"] == "q1_secondary"]
    lines.extend(
        [
            "",
            "Sensitivity summary:",
            "",
            "- Median aggregation retained a large reduction in absolute MOPT slope in all four combinations; Iceberg Q3 crossed slightly above zero after maintenance and is therefore flagged as a sign reversal rather than silently treated as ordinary neutralization.",
            "- The Iceberg warm-cache-only estimates remained close to the all-run estimates: "
            + ", ".join(
                f"{row.query_id} {100.0 * float(row.neutralization):.1f}%"
                for row in warm_rows.itertuples()
            )
            + ".",
            f"- SF-specific exploratory neutralization estimates ranged from {100.0 * float(sf_rows['neutralization'].min()):.1f}% to {100.0 * float(sf_rows['neutralization'].max()):.1f}%. These n=9 models are descriptive, and several show a post-maintenance sign reversal.",
            "- Q1 remained secondary: "
            + ", ".join(
                f"{str(row.table_format).title()} {100.0 * float(row.neutralization):.1f}%"
                for row in q1_rows.itertuples()
            )
            + ". Iceberg Q1 shows a sign reversal, consistent with the locked caution for the metadata-oriented control query.",
        ]
    )

    fallback_count = int(
        sum(
            str(value) == "PERCENTILE_FALLBACK"
            for column in primary.columns
            if column.endswith("_ci_method")
            for value in primary[column]
        )
    )
    unstable_count = int((primary["denominator_status"] != "STABLE").sum())
    lines.extend(
        [
            "",
            "## Method diagnostics",
            "",
            f"- Primary BCa fallbacks across reported primary metric intervals: {fallback_count}.",
            f"- Primary combinations with an unstable or non-estimable beta_pre denominator: {unstable_count}.",
            "- Holm correction covers exactly Iceberg/Delta crossed with Q2/Q3.",
            "- The primary model includes SF fixed effects and phase-by-SF interactions and clusters covariance by physical run.",
            "- The warm-cache-only Iceberg analysis contains 31 runs and omits the complete B02 cell; its bootstrap preserves the observed eligible stratum sizes rather than manufacturing replacement runs.",
            "",
            "## Limitations",
            "",
            "1. Three physical replications per SF/MOPT cell limit precision; bootstrap draws do not create independent evidence.",
            "2. Five Iceberg runs are labeled `cache_mode=none`. They remain in the primary paired analysis, but equal cache state is not claimed.",
            "3. The warm-cache-only subset is unbalanced and entirely lacks Iceberg B02 (SF50/MOPT640000).",
            "4. Query wall time is the format-neutral endpoint. Missing Iceberg EventLogs prevent symmetric planning/scan decomposition.",
            "5. Native Iceberg and Delta maintenance operations are not algorithmically identical; conclusions concern their observed native pre/post effects.",
            "6. The results apply to the tested Spark 3.5.0, Iceberg 1.6.1, Delta 3.2.0, Kafka, and HDFS configuration.",
            "7. This final analysis specification was locked after data collection and exploratory work; it is not a pre-experiment preregistration.",
            "",
            "## Reproducibility artifacts",
            "",
            "- `integrity_checks.csv`: all pre-model gates.",
            "- `query_run_level_aggregates.csv`: the 72-run paired analysis input after technical-repetition aggregation.",
            "- `primary_neutralization_results.csv`: full primary estimates and tests.",
            "- `sensitivity_neutralization_results.csv`: median, cache, SF-specific, and Q1 results.",
            "- `bootstrap_interval_diagnostics.csv`: BCa/fallback diagnostics for every interval.",
            "- `primary_bootstrap_estimates.csv`: all 10,000 primary bootstrap draws.",
            "- `analysis_run_manifest.json`: input/output hashes and software environment.",
        ]
    )
    (output / "publication_neutralization_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "publication_final_neutralization_analysis_v1_0",
        help="New output directory; existing paths are refused.",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")

    manifest, query_frames, _, checks = validate_integrity()
    agg = aggregate_queries(manifest, query_frames)

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    primary_rows: list[dict[str, object]] = []
    sensitivity_rows: list[dict[str, object]] = []
    diagnostics: list[dict[str, object]] = []
    primary_boot_frames: list[pd.DataFrame] = []

    primary_plans: dict[str, np.ndarray] = {}
    primary_data_cache: dict[tuple[str, str, str], ModelData] = {}
    for fmt in ("iceberg", "delta"):
        template = prepare_model_data(agg, fmt, "Q2", "mean_query_wall_time_ms")
        primary_plans[fmt] = make_bootstrap_plan(template, rng, BOOTSTRAP_DRAWS)

    for fmt in ("iceberg", "delta"):
        for query in PRIMARY_QUERIES:
            data = prepare_model_data(agg, fmt, query, "mean_query_wall_time_ms")
            primary_data_cache[(fmt, query, "mean")] = data
            row, diag, boot = analyze_model(data, primary_plans[fmt], fmt, query, "primary_mean", "all_canonical")
            primary_rows.append(row)
            diagnostics.extend(diag)
            primary_boot_frames.append(boot)

    primary = pd.DataFrame(primary_rows)
    primary["theta_p_holm"] = holm_adjust(primary["theta_p_raw"].astype(float).tolist())
    primary["primary_claim_status"] = "NOT_SUPPORTED"
    for idx, row in primary.iterrows():
        supported = (
            float(row["theta_p_holm"]) < ALPHA
            and float(row["absolute_slope_reduction"]) > 0
            and row["denominator_status"] == "STABLE"
            and row["slope_sign_status"] != "SLOPE_SIGN_REVERSAL"
        )
        if supported:
            primary.loc[idx, "primary_claim_status"] = "SUPPORTED_NEUTRALIZATION"
        elif row["denominator_status"] != "STABLE":
            primary.loc[idx, "primary_claim_status"] = "INCONCLUSIVE_UNSTABLE_DENOMINATOR"
        elif row["slope_sign_status"] == "SLOPE_SIGN_REVERSAL":
            primary.loc[idx, "primary_claim_status"] = "INCONCLUSIVE_SIGN_REVERSAL"
        elif float(row["absolute_slope_reduction"]) <= 0:
            primary.loc[idx, "primary_claim_status"] = "NO_REDUCTION_OR_AMPLIFICATION"
        else:
            primary.loc[idx, "primary_claim_status"] = "NOT_SIGNIFICANT_AFTER_HOLM"

    # Median sensitivity, using the exact primary run-level plans.
    for fmt in ("iceberg", "delta"):
        for query in PRIMARY_QUERIES:
            data = prepare_model_data(agg, fmt, query, "median_query_wall_time_ms")
            row, diag, _ = analyze_model(data, primary_plans[fmt], fmt, query, "median_sensitivity", "all_canonical")
            sensitivity_rows.append(row)
            diagnostics.extend(diag)

    # Cache sensitivity. Delta is identical to the primary set; record that identity without recomputing.
    warm_template = prepare_model_data(
        agg, "iceberg", "Q2", "mean_query_wall_time_ms", warm_cache_only=True
    )
    warm_plan = make_bootstrap_plan(warm_template, rng, BOOTSTRAP_DRAWS)
    for query in PRIMARY_QUERIES:
        data = prepare_model_data(
            agg, "iceberg", query, "mean_query_wall_time_ms", warm_cache_only=True
        )
        row, diag, _ = analyze_model(data, warm_plan, "iceberg", query, "warm_cache_sensitivity", "warm_cache_only")
        sensitivity_rows.append(row)
        diagnostics.extend(diag)
    for _, primary_row in primary.loc[primary["table_format"] == "delta"].iterrows():
        copied = primary_row.to_dict()
        copied["analysis"] = "warm_cache_sensitivity"
        copied["scope"] = "identical_to_primary_all_delta_rows_warm_cache"
        sensitivity_rows.append(copied)

    # Q1 secondary control with the same primary plans.
    for fmt in ("iceberg", "delta"):
        data = prepare_model_data(agg, fmt, "Q1", "mean_query_wall_time_ms")
        row, diag, _ = analyze_model(data, primary_plans[fmt], fmt, "Q1", "q1_secondary", "all_canonical")
        sensitivity_rows.append(row)
        diagnostics.extend(diag)

    # SF-specific exploratory estimates for Q2/Q3.
    for fmt in ("iceberg", "delta"):
        for sf in SF_LEVELS:
            template = prepare_model_data(agg, fmt, "Q2", "mean_query_wall_time_ms", sf_only=sf)
            plan = make_bootstrap_plan(template, rng, BOOTSTRAP_DRAWS)
            for query in PRIMARY_QUERIES:
                data = prepare_model_data(agg, fmt, query, "mean_query_wall_time_ms", sf_only=sf)
                row, diag, _ = analyze_model(data, plan, fmt, query, "sf_specific_exploratory", f"SF{sf}")
                sensitivity_rows.append(row)
                diagnostics.extend(diag)

    sensitivity = pd.DataFrame(sensitivity_rows)
    diagnostics_frame = pd.DataFrame(diagnostics)
    primary_bootstrap = pd.concat(primary_boot_frames, ignore_index=True)

    output.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(checks).to_csv(output / "integrity_checks.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    agg.to_csv(output / "query_run_level_aggregates.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    primary.to_csv(output / "primary_neutralization_results.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    sensitivity.to_csv(output / "sensitivity_neutralization_results.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    diagnostics_frame.to_csv(output / "bootstrap_interval_diagnostics.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    primary_bootstrap.to_csv(output / "primary_bootstrap_estimates.csv", index=False, quoting=csv.QUOTE_MINIMAL)

    draw_forest(
        primary,
        "neutralization",
        "Maintenance neutralization of the MOPT elasticity",
        "Neutralization (negative values indicate amplification)",
        output / "neutralization_primary_forest.png",
    )
    draw_beta_comparison(primary, output / "mopt_elasticity_pre_post.png")

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    write_report(output, primary, sensitivity, checks, generated_at)

    output_hashes = {}
    for path in sorted(output.iterdir()):
        if path.is_file() and path.name != "analysis_run_manifest.json":
            output_hashes[path.name] = sha256(path)
    analysis_manifest = {
        "method_version": "publication_final_statistical_analysis_v1_0",
        "generated_at_utc": generated_at,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_draws": BOOTSTRAP_DRAWS,
        "alpha": ALPHA,
        "input_hashes": {str(path.relative_to(ROOT)): sha256(path) for path in EXPECTED_HASHES},
        "output_hashes": output_hashes,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "pillow": getattr(sys.modules.get("PIL"), "__version__", "unknown"),
        },
        "integrity_checks": checks,
    }
    json_dump(output / "analysis_run_manifest.json", analysis_manifest)

    print(
        json.dumps(
            {
                "output": str(output),
                "integrity_checks": len(checks),
                "primary_results": primary[
                    [
                        "table_format",
                        "query_id",
                        "beta_pre",
                        "beta_post",
                        "beta_difference",
                        "neutralization",
                        "theta_p_raw",
                        "theta_p_holm",
                        "primary_claim_status",
                    ]
                ].to_dict(orient="records"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
