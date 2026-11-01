# Temporal Methods and Delta Version-Mapping Validation

**Validation date:** 2026-10-26  
**Scope:** Read-only methodological reconciliation for manuscript Sections 4 and 6  
**Decision:** **PASS**, subject to the exploratory and associational qualifications stated below

## 1. Purpose and Constraints

This validation addressed three bounded questions: whether the manuscript documents the temporal micro-batch analysis exactly as implemented; whether the scenario-outcome table double-counted overlapping categories; and whether Delta batch IDs were aligned with table versions before retaining the reported modulo-10 association. It did not fit a new model, recompute a locked primary analysis, alter a historical record, execute a benchmark, or perform the proposed shifted-position placebo analysis.

The validation used only the 72 canonical runs identified in `publication_canonical_run_manifest.csv`, the stored metrics exports, the historical consumer and collector code, and the already generated temporal-analysis artifacts.

## 2. Evidence Sources

| Source | Role | Integrity/provenance note |
|---|---|---|
| `publication_canonical_run_manifest.csv` | Canonical run IDs and completed commit counts | Restricted validation to 36 canonical Delta runs and 36 canonical Iceberg runs |
| `delta_metrics_exports_20261024/metrics_ingestion.csv` | Stored Delta batch IDs and table versions | 60,234 canonical rows evaluated read-only |
| `delta_metrics_exports_20261024/compaction_operation_metrics.csv` | Pre-maintenance Delta table version | 36 canonical `OPTIMIZE` rows evaluated read-only |
| `Iceberg - Delta/scripts/consumers/run_spark_consumer_delta.py` | Table-creation and append order | Creates the empty Delta table before starting the stream, then appends each batch with `txnVersion=micro_batch_id` |
| `Iceberg - Delta/scripts/lib/lakehouse_metrics_collector_delta.py` | Version capture | Reads the latest `DESCRIBE HISTORY` version after the batch append |
| `analyze_microbatch_temporal_performance.py` | Authoritative temporal-analysis implementation | SHA-256 `81A19B35C498318ECE42F69E4419A74DA4058191D3D33D22FB1CD2C85CAFC477` |
| `microbatch_temporal_performance_analysis.md` | Existing analysis report | SHA-256 `F45A199FB3D63A41703EB97960B27779F33F336CF8CC84A833A905D6D32036A4` |
| `microbatch_temporal_performance_artifacts/microbatch_temporal_group_statistics.csv` | Scenario effects and nominal intervals | Contains 24 format/scenario groups |
| `microbatch_temporal_performance_artifacts/microbatch_temporal_delta_periodicity.csv` | Existing Delta version-position association | No new periodicity estimate was calculated |
| `publication_data_integrity_amendment_v1.2.md` | Current integrity boundary | Used as the governing amendment |

The principal data/code inputs were fixed by the following SHA-256 values at validation time:

| Source | SHA-256 |
|---|---|
| `publication_canonical_run_manifest.csv` | `AFAF04A6231035A1DF4397A73D2F1CF45CF3271DBCA18B001EB41F0B1F6830E2` |
| `delta_metrics_exports_20261024/metrics_ingestion.csv` | `6C3C46D2047F32376C4A6CB489F70EE607644F07A428FD76E5C47F0E0399B07D` |
| `delta_metrics_exports_20261024/compaction_operation_metrics.csv` | `B267A59B994BD6A7654CE2BFBB6D7A147A37F01922691C804B182ED743294E79` |
| `microbatch_temporal_performance_artifacts/microbatch_temporal_group_statistics.csv` | `A12DE28F78805935893D03069CC4A90895C1C8569102C87CB5F85B8D7D5979DB` |
| `microbatch_temporal_performance_artifacts/microbatch_temporal_delta_periodicity.csv` | `7825E1B6C0C53AB7DE149AF773F56F616A5D4FEE7B056DA117B0BB70F7835B18` |
| `Iceberg - Delta/scripts/consumers/run_spark_consumer_delta.py` | `0A008FCFFB44F6541D71EA9378303C353D645EAB2F4EF7D4D098360930879F45` |
| `Iceberg - Delta/scripts/lib/lakehouse_metrics_collector_delta.py` | `938FF4DB99C76E8404675C551D107ECD1C4831DC3C736D0B3D440896A22565CE` |

## 3. Implemented Temporal Method

Inspection of `analyze_microbatch_temporal_performance.py` confirms the following implementation.

### 3.1 Startup and Batch-Fill Rules

For each run containing *N* recorded rows, the startup-window size is

```text
W = min(10, max(3, ceil(0.05 * N)))
```

The first *W* recorded batches are marked as startup. A batch is comparably filled when

```text
record_count / MOPT >= 0.95.
```

The primary temporal comparison excludes the first *W* batches and retains post-startup batches that meet the fill threshold and have a nonmissing `spark_duration_triggerExecution_ms`. The implementation found no recorded batch below the 95% threshold. This does not recover the known unrecorded terminal batch.

### 3.2 Positional Sections and Run Effect

Eligible rows are sorted by batch ID. If *K* rows remain and *j* is a zero-based eligible-row index, the script assigns:

- early when `j/K < 1/3`, equivalent to indices `0` through `ceil(K/3)-1`;
- middle when `1/3 <= j/K < 2/3`, equivalent to `ceil(K/3)` through `ceil(2K/3)-1`;
- late for all remaining indices.

The run-level effect is

```text
LateVsEarly_i = 100 * (mean_late_i / mean_early_i - 1).
```

This is a positional comparison, not an elapsed-time partition.

### 3.3 Scenario Interval and Sensitivity

For each format/SF/MOPT cell, the three physical-run effects are summarized by their arithmetic mean and sample SD. The nominal interval is

```text
mean +/- 4.303 * SD / sqrt(3),
```

where 4.303 is the two-sided 97.5th percentile of the *t* distribution with `df=2`. The all-batch sensitivity applies the same positional thirds to all recorded rows, including startup and any underfilled rows, and recalculates the effect.

This analysis was developed after data collection. It is exploratory, not preregistered, and not part of the locked four-test Holm family. Its 24 scenario intervals were not multiplicity-adjusted.

## 4. Scenario-Category Reconciliation

The prior manuscript table incorrectly displayed `Mixed replicate signs` beside mutually exclusive null-assessment outcomes, although sign consistency overlaps those outcomes. The source artifact gives the following mutually exclusive partition:

| Nominal scenario outcome | Iceberg | Delta | Total |
|---|---:|---:|---:|
| Positive interval excluding zero | 1 | 2 | 3 |
| Negative interval excluding zero | 1 | 0 | 1 |
| Zero not rejected | 10 | 10 | 20 |
| **Total** | **12** | **12** | **24** |

`Mixed replicate signs` is an overlapping diagnostic: 6 Iceberg groups and 4 Delta groups, 10 in total. It is now reported only as an `of which` subset. The four nominally nonzero groups are Iceberg B01, Iceberg B03, Delta B10, and Delta B11. Because the 24 comparisons were not multiplicity-corrected, they are exploratory signals rather than confirmatory findings.

## 5. Retained-Metadata Model Interpretation

Methodology version 5.1 anticipated a mixed linear-plus-quadratic mechanism:

```text
M(n) \approx a*n + b*n^2.
```

The linear term can represent contributions accumulated approximately once per commit. The quadratic term can represent cumulative retention of state representations whose individual size increases with commit index. Under positive `a`, `b`, and `n`, its local elasticity is

```text
eta(n) = (a + 2*b*n) / (a + b*n)
       = 1 + (b*n) / (a + b*n),
```

which lies between one and two and varies with *n*. The observed effective elasticities, reported in the manuscript as 1.874 for Iceberg and 1.740 for Delta, are compatible with such curvature over the tested interval; they are not independent universal power laws.

The already validated original-scale diagnostics favor the quadratic description much more strongly than the power model: RMSE 22.42 versus 1,163.33 MiB for Iceberg and 3.57 versus 747.14 MiB for Delta. This is evidence about fit over the observed range, not proof that fitted coefficients map to particular metadata-object mechanisms. Full-precision elasticities and bootstrap intervals remain in the Supplementary Material.

## 6. Delta Batch/Version Validation

### 6.1 Checks Performed

The following conditions were checked over the canonical Delta corpus:

1. each canonical run in the manifest had its expected number of stored ingestion rows;
2. `(run_id, micro_batch_id)` was unique;
3. every stored row satisfied `delta_table_version = micro_batch_id + 1`;
4. every run contained batch 0 at version 1;
5. every run contained batch 9 at version 10;
6. the last stored version equaled `completed_ingestion_commits - 1`;
7. the pre-maintenance version in the canonical `OPTIMIZE` row equaled `completed_ingestion_commits`.

### 6.2 Results

| Validation quantity | Result |
|---|---:|
| Canonical Delta runs | 36 |
| Canonical stored batch rows | 60,234 |
| Unexpected row-count runs | 0 |
| Duplicate run/batch keys | 0 |
| Rows violating `version = batch + 1` | 0 |
| Runs without batch 0 at version 1 | 0 |
| Runs without batch 9 at version 10 | 0 |
| Runs with an unexpected last stored version | 0 |
| Pre-maintenance version mismatches | 0 |

The consumer creates the empty Delta table before streaming, which establishes version 0. The first append therefore produces version 1. The collector reads the current history version only after that append. The known n-1 alignment suppresses the final metrics row because the collector finalizes batch *n* after progress for batch *n+1* becomes available; it does not alter the version attached to a row that was stored. The final unrecorded commit is independently visible in the pre-maintenance table version.

### 6.3 Consequence for the Periodicity Statement

No run-specific exception was found, so release of the existing modulo-10 association need not be stopped. Rows with `delta_table_version mod 10 = 0` correspond to batch IDs 9, 19, 29, and so forth. The reported 15.06% latency difference remains an association with expected checkpoint positions. It is not a direct checkpoint-duration measurement and does not prove that a checkpoint completed at every such position. A shifted-position placebo test may be useful as a later exploratory robustness check, but it was not performed here.

## 7. Versioned Documentation Changes

| Artifact | Versioned change | Data/model consequence |
|---|---|---|
| `manuscript_section_04_measurement_and_statistical_methodology_v1.3.md` | Added the exact temporal rules, exploratory status, and Delta mapping validation | None |
| `manuscript_section_06_metadata_and_temporal_behavior_v1.1.md` | Corrected Tables 6-9, scenario categorization, metadata-scaling interpretation, and Delta mapping explanation | None |
| `publication_temporal_methods_validation.md` | Added reproducible validation record | None |

## 8. Final Assessment

**PASS.** The temporal method is now documented as implemented, including its post-hoc exploratory status. The corrected scenario categories form twelve mutually exclusive groups per format, with mixed replicate signs shown only as an overlapping diagnostic. The retained-byte elasticities are properly bounded as effective descriptions within a linear-plus-quadratic expectation rather than universal laws. Finally, the Delta batch/version relationship is consistent in every canonical run, and the n-1 collector behavior introduces no additional version offset. The modulo-10 statement may remain in the manuscript only with its existing associational limitation.
