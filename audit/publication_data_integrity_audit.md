# Publication Data Integrity Audit

Audit date: 2026-10-25  
Scope: Apache Iceberg and Delta Lake micro-batch experiments for the planned journal article  
Audit type: read-only retrospective integrity audit

## 1. Audit conclusion

The canonical dataset contains **72 valid physical ingestion runs**: 36 Apache Iceberg runs and 36 Delta Lake runs. It covers the complete factorial grid of four scale factors (SF50, SF100, SF200, SF500), three MOPT values (160,000; 640,000; 2,560,000), and three physical replications per format and cell.

All included ingestion rows report the fixed resource profile of **5 executors and 80 executor cores**. No surviving run with a 4-executor/64-core profile is included in the canonical exports or in the current master analyses. The current B10 reruns are present in the canonical exports and the relevant analysis tables.

The data-integrity layer is therefore suitable for release to the final statistical analysis under a **conditional GO** decision. Before inferential analysis begins, the final analysis execution specification must be frozen and hashed, including the aggregation statistic for query repetitions, the cache-mode rule, the bootstrap seed, and the multiplicity procedure. The present work is a retrospective audit and must not be described as preregistration.

## 2. Canonical source set

The canonical sources are the dated exports below. Older exports remain historical evidence but are not analysis inputs.

| Format | Metric family | Canonical source | Rows | Fields | SHA-256 |
|---|---|---:|---:|---:|---|
| Iceberg | Ingestion | `iceberg_metrics_exports_20261024/metrics_ingestion.csv` | 60,234 | 82 | `237c3eb716e75d36ed71ffeb91d30bb706a47cf40ba03a9827083f8bb5dfaf52` |
| Iceberg | Query | `iceberg_metrics_exports_20261024/query_metrics.csv` | 1,296 | 45 | `6bc776a1948b3b29fed5648a80d195b6aa87d3b13208afc27f45ecd5080a345` |
| Iceberg | Maintenance | `iceberg_metrics_exports_20261024/compaction_operation_metrics.csv` | 72 | 47 | `d80265f4ce5062376ebfc0bf192144a9315fa1868790e81008efa8e2cf3b871f` |
| Delta | Ingestion | `delta_metrics_exports_20261024/metrics_ingestion.csv` | 60,234 | 82 | `6c3c46d2047f32376c4a6cb489f70ee607644f07a428fd76e5c47f0e0399b07d` |
| Delta | Query | `delta_metrics_exports_20261024/query_metrics.csv` | 1,296 | 45 | `240a8b1f71ba62591689f1425c32262696566581539187880af45ecd5080a345` |
| Delta | Maintenance | `delta_metrics_exports_20261024/compaction_operation_metrics.csv` | 36 | 47 | `b267a59b994bd6a7654ce2bfbb6d7a147a37f01922691c804b182ed743294e79` |
| Delta | Reconstructed phase quality | `delta_metrics_exports_20261024/metrics_ingestion_phases_reconstruction_quality.csv` | 36 | 46 | `deb3d2ed4e258684f46ec8aa589ade44318de7f3300c6e0d0b04bc28ead2b4df` |

The complete row-level run inventory is in `publication_canonical_run_manifest.csv`. It records the actual batch start and last recorded batch completion timestamps rather than relying only on timestamps embedded in run IDs.

## 3. Canonical coverage

| Integrity condition | Result |
|---|---:|
| Physical ingestion runs | 72 |
| Iceberg / Delta runs | 36 / 36 |
| Factor cells per format | 12 |
| Replications per cell | 3 |
| Ingestion metric rows per format | 60,234 |
| Query executions per format | 1,296 |
| Total query executions | 2,592 |
| Warmup / measured query executions | 1,296 / 1,296 |
| Iceberg maintenance records | 72: data-file rewrite plus manifest rewrite |
| Delta maintenance records | 36: OPTIMIZE |
| Included resource profile | 5 executors, 80 total executor cores |
| Excluded canonical runs | 0 |

Every physical run has 36 query records: 18 warmups and 18 measured executions. These arise from two phases, three queries, three warmups, and three measured repetitions. The independent experimental units remain the 72 physical ingestion runs; the 2,592 query rows are not 2,592 independent experiments.

## 4. B10 rerun determination

The following runs are canonical:

| Format | Rep | Canonical run ID |
|---|---:|---|
| Iceberg | 1 | `B10_r01_store_sales_sf500_mopt160000_20260828_163243Z` |
| Iceberg | 2 | `B10_r02_store_sales_sf500_mopt160000_20260902_042804Z` |
| Iceberg | 3 | `B10_r03_store_sales_sf500_mopt160000_20260903_044849Z` |
| Delta | 1 | `B10_delta320_r01_store_sales_sf500_mopt160000_20260912_130358Z` |
| Delta | 2 | `B10_delta320_r02_store_sales_sf500_mopt160000_20260927_162301Z` |
| Delta | 3 | `B10_delta320_r03_store_sales_sf500_mopt160000_20260926_033819Z` |

Each canonical B10 run has 9,000 stored n-1 ingestion rows, batch IDs 0 through 8,999, a final Q1 row count of 1,439,977,468, and the fixed 5-executor/80-core profile.

An older Delta export contains superseded B10 identifiers for Rep 2 (`...20260915_150148Z`) and Rep 3 (`...20260917_113218Z`). Those runs do not occur in the 2026-10-24 canonical bundle and are not used by the current analyses. The current B10 IDs are present in the metadata-amplification run-level table, the temporal-performance run-level table, and the Delta EventLog manifest.

No surviving B10 artifact with 4 executors/64 cores was found. This confirms that such a run is not included; it does not reconstruct metadata for any already deleted invalid attempt.

## 5. Historical data issues

### 5.1 B10 rerun

**Status: CONFIRMED.**

The canonical IDs and timestamps are listed above. Current master exports and analysis files use those IDs. Superseded Delta B10 Rep 2 and Rep 3 identifiers remain only in an older export and are excluded.

### 5.2 CSV escaping

**Status: CONFIRMED.**

The old file `exports/delta_metrics_export_20261006_0820/delta_compaction_operation_metrics_select_all.csv` is malformed: its header has 47 fields while every one of its nine data records is split into 88 fields because `procedure_result_json` was not RFC 4180 quoted.

The corrected file `exports/delta_metrics_rfc4180_20261006/delta_compaction_operation_metrics_select_all_rfc4180.csv` has 47 fields for every record and valid JSON in all nine rows. The first 42 fields match the malformed export by `maintenance_run_id`. The current canonical Delta maintenance export has 47 fields in all 36 rows and valid JSON. All six canonical metric CSVs pass exact-width parsing; all applicable JSON fields parse successfully.

The malformed export must never be read with naive delimiter splitting and must not be used as a canonical source.

### 5.3 Difference of 1,634 records

**Status: PARTIALLY CLARIFIED.**

The historical discussion reports one invalid SF500/B10 execution whose row count differed by 1,634. The retained valid data show 1,439,977,468 rows for every canonical SF500 run in both formats. The invalid B10 execution was replaced by a rerun and is absent from the canonical exports.

The exact technical cause cannot be proven from the surviving artifacts: no separate raw metrics export or source manifest for the 1,634-row-deficient attempt is available. It would therefore be unsupported to attribute the discrepancy specifically to missing HDFS chunks, producer truncation, or Kafka delivery. The defensible statement is that the discrepant execution was rejected, the source was regenerated/replayed, and only runs matching the verified SF500 total were retained.

### 5.4 `cache_mode`

**Status: CONFIRMED.**

All 1,296 Delta query rows and 1,116 Iceberg query rows are labeled `warm_cache`. The following five Iceberg runs have all 36 query rows labeled `none`:

- `B01_r02_store_sales_sf50_mopt160000`
- `B01_r03_store_sales_sf50_mopt160000`
- `B02_r01_store_sales_sf50_mopt640000`
- `B02_r02_store_sales_sf50_mopt640000`
- `B02_r03_store_sales_sf50_mopt640000`

These rows are internally consistent between pre- and post-maintenance phases but are not identically labeled to the primary warm-cache pool. The primary query analysis must either exclude these five runs or model/report cache mode explicitly. A sensitivity analysis may retain them. Existing exploratory results indicate stable Q2/Q3 conclusions and uncertainty for Q1; this observation does not replace the prospective primary-analysis rule.

### 5.5 n-1 micro-batch alignment

**Status: CONFIRMED.**

Every run has exactly one fewer ingestion-metric record than completed sink commits. This is the known collector alignment: metrics for batch n are persisted while batch n+1 is available, so the terminal batch lacks a metrics row. The manifest records, for every run, the completed commit count, stored row count, and terminal-batch row count inferred from the independently validated final table count.

The final row must not be imputed for latency or resource metrics. Commit count and final ingested row count may use the independently observed table/maintenance state. Analyses of per-batch performance must operate only on observed metric rows and state the n-1 limitation.

### 5.6 Query warmups and measured repetitions

**Status: CONFIRMED.**

The 2,592 query rows comprise:

- 1,296 warmup executions;
- 1,296 measured executions;
- 3 measured technical repetitions for each format/run/phase/query combination;
- 432 format/run/phase/query measured groups, or 216 format/run/query pre/post pairs.

Warmups are excluded from performance estimates. The three measured repetitions are technical repetitions and must be aggregated within a physical run. They must not be treated as independent experimental replications.

## 6. Supporting validation evidence

- Delta phase reconstruction covers all 36 Delta runs and reports `PASS_WITH_KNOWN_N_MINUS_1`; no resource-profile or output-count mismatch is reported.
- Query EventLogs cover all 72 Delta query applications and all 1,296 Delta query executions. The 72 Iceberg query EventLogs are absent and cannot be reconstructed.
- Pre/post query result hashes match for all 216 format/run/query pairs.
- Historical pure transaction-commit duration is not directly observable for either format. Iceberg `metadata_commit_duration_ms` must be treated as a proxy, not as an isolated commit duration.
- `metadata_total_size_mib` and `metadata_file_count` describe retained metadata footprint under the applied retention policy, not active metadata.

## 7. Reproducibility

The manifest was generated by `audit_publication_data_integrity.py` without changing any experiment data. The script validates field widths, JSON fields, factor coverage, resource profiles, n-1 alignment, query composition, maintenance coverage, Delta reconstruction status, and B10 references.

Manifest SHA-256:

`afaf04a6231035a1df4397a73d2f1cf45cf3271dbca18b001eb41f0b1f6830e2`

## 8. Release decision

**Conditional GO for final statistical analysis.**

The canonical 72-run dataset is internally coherent and complete for the stated design. No further experiment is required to establish dataset integrity. Final statistical execution should start only after a dated and hashed analysis specification fixes:

1. the primary aggregation of the three measured query repetitions;
2. the primary and sensitivity handling of the five `cache_mode=none` Iceberg runs;
3. the exact model formulas and endpoint hierarchy;
4. the BCa-bootstrap seed and resampling unit;
5. the multiplicity-control rule;
6. the treatment of reconstructed Delta phase metrics and unavailable Iceberg EventLogs.

This later freeze is a prospective lock for the final analysis, not evidence of a pre-existing preregistration.
