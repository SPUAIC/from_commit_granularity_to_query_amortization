# Active Data Footprint Validation

**Validation date:** 2026-10-26  
**Scope:** Read-only reconciliation of the 72 canonical native-maintenance runs  
**Decision:** **PASS** for use as an additional descriptive result

## 1. Objective and Evidence Boundary

This validation examines the logical size of the active Parquet data-file set immediately before and after native maintenance. It uses only `publication_canonical_run_manifest.csv`, `iceberg_metrics_exports_20261024/compaction_operation_metrics.csv`, and `delta_metrics_exports_20261024/compaction_operation_metrics.csv`. The exact canonical ingestion run ID governed inclusion. No historical record, canonical identifier, locked statistical result, or maintenance output was modified.

For Iceberg, the relevant state transition is the `rewrite_data_files` row. The subsequent `rewrite_manifests` row was checked as a separate metadata operation and was not counted as a second data rewrite. For Delta, the relevant row is `OPTIMIZE`.

The endpoint is the sum of the logical lengths of active Parquet data files represented by `total_data_size_mib_before` and `total_data_size_mib_after`. It is not total HDFS space consumption and does not include inactive data files, historical metadata, replication overhead, or directories outside the active file set.

## 2. Canonical Join and Completeness

The manifest-to-maintenance join produced exactly one relevant data-operation row for every canonical run.

| Validation check | Result |
|---|---:|
| Canonical runs | 72 |
| Iceberg `rewrite_data_files` rows | 36 |
| Delta `OPTIMIZE` rows | 36 |
| Missing or multiply matched canonical runs | 0 |
| Non-successful relevant operations | 0 |
| Explicit target-size values in relevant rows | 0 |
| Nonempty operation option maps | 0 |

The complete run-level reconciliation is provided in `publication_active_data_footprint_runlevel.csv`. It contains the full timestamped canonical run ID, maintenance ID, source export, operation boundary, active data state, and consistency diagnostics for each run.

## 3. Active-Byte Arithmetic Validation

For every run, the stored byte sum was checked against

```text
reconstructed_total_mib = data_file_count * avg_data_file_size_mib.
```

The tolerance was the larger of `1e-6 MiB` and `1e-12 * abs(total_data_size_mib)`. All 144 before/after checks passed. The maximum absolute discrepancy was below `4.90e-10 MiB`, consistent with floating-point serialization and far below the defined tolerance. The explicit byte sums are therefore arithmetically consistent with the stored counts and means.

The per-run active-volume change was calculated as requested:

```text
delta_pct = 100 * (total_data_size_mib_after / total_data_size_mib_before - 1).
```

No row was estimated or imputed.

## 4. Cell-Level Active-Volume Change

Each cell contains three independent physical runs. `Mean delta` is the arithmetic mean of the three individual percentage changes. SD is the sample SD of those three changes. Because every mean is negative and materially separated from zero, CV is reported as `100 * SD / abs(mean delta)`. `Ratio of means` is calculated separately as `100 * (mean after / mean before - 1)`.

The pre-maintenance active byte total was identical across the three replications in every cell. Consequently, the mean of individual percentage changes and the ratio of aggregate means coincide to the displayed precision; the maximum computational difference was `1.60e-14` percentage points. They remain conceptually distinct estimands.

### 4.1 Iceberg

| Scenario | SF | MOPT | Mean before MiB | Mean after MiB | Mean delta | SD | CV | Ratio of means |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B01 | 50 | 160,000 | 7,255.765 | 6,467.539 | -10.8634% | 0.0016 pp | 0.02% | -10.8634% |
| B02 | 50 | 640,000 | 6,832.891 | 6,395.261 | -6.4048% | 0.0251 pp | 0.39% | -6.4048% |
| B03 | 50 | 2,560,000 | 6,615.709 | 6,304.601 | -4.7026% | 0.0752 pp | 1.60% | -4.7026% |
| B04 | 100 | 160,000 | 14,599.083 | 12,978.542 | -11.1003% | 0.0071 pp | 0.06% | -11.1003% |
| B05 | 100 | 640,000 | 13,740.779 | 12,865.162 | -6.3724% | 0.0084 pp | 0.13% | -6.3724% |
| B06 | 100 | 2,560,000 | 13,298.284 | 12,743.641 | -4.1708% | 0.0800 pp | 1.92% | -4.1708% |
| B07 | 200 | 160,000 | 29,435.628 | 26,125.671 | -11.2447% | 0.0286 pp | 0.25% | -11.2447% |
| B08 | 200 | 640,000 | 27,701.308 | 25,960.404 | -6.2846% | 0.0070 pp | 0.11% | -6.2846% |
| B09 | 200 | 2,560,000 | 26,812.150 | 25,684.892 | -4.2043% | 0.0632 pp | 1.50% | -4.2043% |
| B10 | 500 | 160,000 | 73,819.390 | 65,203.534 | -11.6715% | 0.0264 pp | 0.23% | -11.6715% |
| B11 | 500 | 640,000 | 69,418.697 | 65,048.593 | -6.2953% | 0.0051 pp | 0.08% | -6.2953% |
| B12 | 500 | 2,560,000 | 67,180.456 | 64,348.753 | -4.2151% | 0.0302 pp | 0.72% | -4.2151% |

### 4.2 Delta

| Scenario | SF | MOPT | Mean before MiB | Mean after MiB | Mean delta | SD | CV | Ratio of means |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B01 | 50 | 160,000 | 7,257.415 | 6,247.600 | -13.9143% | 0.0042 pp | 0.03% | -13.9143% |
| B02 | 50 | 640,000 | 6,833.305 | 6,247.669 | -8.5703% | 0.0057 pp | 0.07% | -8.5703% |
| B03 | 50 | 2,560,000 | 6,598.355 | 6,246.132 | -5.3380% | 0.0008 pp | 0.02% | -5.3380% |
| B04 | 100 | 160,000 | 14,602.381 | 12,563.382 | -13.9635% | 0.0046 pp | 0.03% | -13.9635% |
| B05 | 100 | 640,000 | 13,741.604 | 12,564.979 | -8.5625% | 0.0019 pp | 0.02% | -8.5625% |
| B06 | 100 | 2,560,000 | 13,263.573 | 12,561.997 | -5.2895% | 0.0035 pp | 0.07% | -5.2895% |
| B07 | 200 | 160,000 | 29,442.222 | 25,339.574 | -13.9346% | 0.0025 pp | 0.02% | -13.9346% |
| B08 | 200 | 640,000 | 27,702.958 | 25,344.694 | -8.5127% | 0.0020 pp | 0.02% | -8.5127% |
| B09 | 200 | 2,560,000 | 26,742.417 | 25,339.718 | -5.2452% | 0.0003 pp | 0.01% | -5.2452% |
| B10 | 500 | 160,000 | 73,835.872 | 63,498.462 | -14.0005% | 0.0012 pp | 0.01% | -14.0005% |
| B11 | 500 | 640,000 | 69,422.817 | 63,516.354 | -8.5080% | 0.0009 pp | 0.01% | -8.5080% |
| B12 | 500 | 2,560,000 | 67,006.250 | 63,503.873 | -5.2269% | 0.0008 pp | 0.02% | -5.2269% |

These are descriptive cell summaries. No new inferential neutralization endpoint was defined.

## 5. SF500 Reconciliation

### 5.1 Run-Level After Values

| Format | Scenario | Rep 1 MiB | Rep 2 MiB | Rep 3 MiB | Cell mean MiB | Cell mean GiB |
|---|---|---:|---:|---:|---:|---:|
| Iceberg | B10 | 65,204.761 | 65,183.456 | 65,222.384 | 65,203.534 | 63.675 |
| Iceberg | B11 | 65,049.911 | 65,044.569 | 65,051.299 | 65,048.593 | 63.524 |
| Iceberg | B12 | 64,332.163 | 64,342.737 | 64,371.359 | 64,348.753 | 62.841 |
| Delta | B10 | 63,499.127 | 63,497.493 | 63,498.764 | 63,498.462 | 62.010 |
| Delta | B11 | 63,517.028 | 63,515.763 | 63,516.271 | 63,516.354 | 62.028 |
| Delta | B12 | 63,503.251 | 63,504.074 | 63,504.294 | 63,503.873 | 62.016 |

The approximate values supplied for checking are confirmed after allowing for rounding. In particular, `63,500 MiB` is approximately `62.0 GiB`, because binary GiB uses 1,024 MiB.

### 5.2 MOPT-Dependent Convergence

Before maintenance, the SF500 mean active footprint differed substantially across MOPT. For Iceberg, the difference between B10 and B12 was 6,638.934 MiB; after maintenance, the range across B10-B12 was 854.781 MiB. For Delta, the B10-to-B12 pre-maintenance difference was 6,829.622 MiB, whereas the post-maintenance range across B10-B12 was only 17.892 MiB.

This is descriptive evidence that the MOPT-dependent difference in active Parquet bytes was attenuated by the native maintenance operations. It is not a new inferential neutralization measure and does not establish that actual query scan bytes changed by the same amount.

## 6. Native Target-Size Provenance

### 6.1 Iceberg

All 36 canonical `rewrite_data_files` rows have `target_file_size_bytes=NULL` and `operation_options_json={}`. The archived maintenance script uses `default=None` and only passes `target-file-size-bytes` when explicitly supplied. The Bronze-table DDL does not set `write.target-file-size-bytes`, and no preserved per-run table-property capture establishes an override.

The historically supported classification is therefore **non-overridden Iceberg 1.4.2 default**, documented as `536870912` bytes, or 512 MiB. The numeric value is a version default, not a directly logged run-time argument in the 36 maintenance rows.

### 6.2 Delta

All 36 canonical `OPTIMIZE` rows likewise have `target_file_size_bytes=NULL` and `operation_options_json={}`. The archived Delta script only sets `spark.databricks.delta.optimize.maxFileSize` when the optional CLI parameter is supplied. Neither the archived Bronze-table DDL nor the Spark-session builder sets that configuration.

The historically supported classification is therefore **non-overridden Delta Lake 3.2.0 default**, documented as `1073741824` bytes, or 1,024 MiB. Again, the value was not captured as an explicit per-run argument. The observed post-maintenance means are consistent with, but do not independently prove, that default.

The different native targets are essential when interpreting output file counts. Delta generally produced fewer, larger active files because its native target is twice Iceberg's. The resulting file counts therefore cannot be compared as though both operations had been asked to produce the same file size or had executed the same algorithm.

## 7. Maintenance Wall Time and Replication Variation

For SF500, the mean `rewrite_data_files` duration increased across Iceberg B10, B11, and B12: 299.392, 378.939, and 448.872 seconds. Delta showed the opposite descriptive order for `OPTIMIZE`: 994.031, 743.475, and 661.788 seconds. No mechanism is inferred from those opposing sequences.

The large Iceberg B11 and B12 SDs arise from the following valid run times:

| Scenario | Replication 1 | Replication 2 | Replication 3 | Mean | Sample SD | CV |
|---|---:|---:|---:|---:|---:|---:|
| B11 | 687.437 s | 241.823 s | 207.558 s | 378.939 s | 267.716 s | 70.6% |
| B12 | 411.090 s | 745.723 s | 189.804 s | 448.872 s | 279.879 s | 62.4% |

These run-level differences are important for the uncertainty of later temporal break-even estimates, but they do not identify a cause. Iceberg B04 also had high `rewrite_data_files` variation (CV 57.9%). This co-occurred with the previously documented temporal ingestion drift in B04. The two observations were not isolated experimentally, and no causal connection is asserted.

## 8. Interpretation Boundaries

Four storage quantities must remain separate:

1. **Active Parquet data bytes:** the logical byte sum of files in the current table state, measured here.
2. **Physically retained inactive data files:** rewritten files no longer active in the current state but potentially still stored until snapshot expiration, orphan cleanup, or Delta `VACUUM`; these are not included in the active-byte endpoint.
3. **Retained historical metadata:** Iceberg metadata objects and Delta transaction-log/checkpoint files measured by the separate retained-metadata endpoint.
4. **Bytes actually read by Q2 or Q3:** Spark execution input under the specific query plan, pruning behavior, and cache state.

A smaller active Parquet footprint is a plausible mechanism that may contribute to later query behavior, but it is not direct evidence that Q2 or Q3 read proportionally fewer bytes. Query scan metrics and wall times must be evaluated separately.

## 9. Final Decision

**PASS.** The run-level original data support the additional descriptive finding. All canonical joins and arithmetic reconciliations passed; the supplied SF500 approximations were confirmed; no `rewrite_manifests` row was double-counted as a data rewrite; and no target-size override was present in the recorded operations. The result may be added to Section 7 with the stated endpoint and interpretation boundaries. It does not alter any locked primary analysis.
