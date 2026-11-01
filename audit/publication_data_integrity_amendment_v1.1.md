# Publication Data Integrity Amendment v1.1

**Date:** 2026-10-26  
**Status:** Versioned amendment to `publication_data_integrity_audit.md`  
**Mode:** Read-only validation  
**Decision:** PASS for the 72-run terminal-batch reconciliation; no change to canonical run selection or locked statistical results

## 1. Purpose and scope

This amendment adds an explicit run-local validation of the known n-1 ingestion-metrics alignment. It does not replace or silently edit the original audit. It validates all 72 canonical physical ingestion runs selected by `publication_canonical_run_manifest.csv` and clarifies the format-specific strength of the independent commit evidence.

No raw export, HDFS table, canonical run identifier, statistical model, or result file was changed. No missing terminal latency or resource row was synthesized.

## 2. Version change log

| Version | Change | Reason | Effect on results |
|---|---|---|---|
| 1.1 | Recomputed `Q1 COUNT - sum(record_count)` independently for every canonical run | The v1.0 audit inherited `missing_final_batch_rows` from an upstream run summary | None; all inherited values were confirmed |
| 1.1 | Checked the calculated terminal count against the last stored `lag_records_total` | Adds an explicit second consistency condition | None; all 72 checks passed |
| 1.1 | For Delta, checked the EventLog terminal row and pre-maintenance table version | Provides direct format-specific confirmation | None; all 36 Delta checks passed |
| 1.1 | Reclassified Iceberg file-count/12 as structural corroboration, not snapshot counting | Historical Iceberg EventLogs and native snapshot-count exports are unavailable | Wording correction only |
| 1.1 | Corrected the printed SHA-256 for the Iceberg query export | The hash in the original prose audit was a transcription error | None; source content and row-level validation are unchanged |
| 1.1 | Incorporated the SF500 reconciliation decision | Resolves the competing historical cardinality and terminal-batch values | Confirms canonical values; no run replacement |

## 3. Immutable evidence set

| Source | Rows relevant to this amendment | SHA-256 observed on 2026-10-26 |
|---|---:|---|
| `publication_canonical_run_manifest.csv` | 72 | `afaf04a6231035a1df4397a73d2f1cf45cf3271dbca18b001eb41f0b1f6830e2` |
| `iceberg_metrics_exports_20261024/metrics_ingestion.csv` | 60,234 | `237c3eb716e75d36ed71ffeb91d30bb706a47cf40ba03a9827083f8bb5dfaf52` |
| `iceberg_metrics_exports_20261024/query_metrics.csv` | 1,296 | `6bc776a1948b3b29fed5648a80d195b6aa87d3b13208afc27f45ba7a7cdec043` |
| `iceberg_metrics_exports_20261024/compaction_operation_metrics.csv` | 72 | `d80265f4ce5062376ebfc0bf192144a9315fa1868790e81008efa8e2cf3b871f` |
| `delta_metrics_exports_20261024/metrics_ingestion.csv` | 60,234 | `6c3c46d2047f32376c4a6cb489f70ee607644f07a428fd76e5c47f0e0399b07d` |
| `delta_metrics_exports_20261024/query_metrics.csv` | 1,296 | `240a8b1f71ba62591689f1425c32262696566581539187880af45ecd5080a345` |
| `delta_metrics_exports_20261024/compaction_operation_metrics.csv` | 36 | `b267a59b994bd6a7654ce2bfbb6d7a147a37f01922691c804b182ed743294e79` |
| `delta_metrics_exports_20261024/metrics_ingestion_phases_reconstructed.csv` | Available reconstructed Delta batches | `57c1d0a32c899529e439f4fcf038ab761f29db9ac7d74a8f20388413142e891` |

The original audit printed `6bc776a1948b3b29fed5648a80d195b6aa87d3b13208afc27f45ecd5080a345` for the Iceberg query file. Direct hashing of the preserved file gives `6bc776a1948b3b29fed5648a80d195b6aa87d3b13208afc27f45ba7a7cdec043`. The file timestamp predates the original audit, and all 1,296 rows remain width-valid and parseable. The discrepancy is therefore documented as a report-level hash transcription error, not as evidence of a changed raw export.

## 4. Run-local validation procedure

For each manifest row, the validation performed the following operations using its exact canonical full run ID and canonical run key:

1. Selected all ingestion rows by the full `run_id`.
2. Selected all query rows by `ingestion_run_id` and parsed every Q1 `result_json`.
3. Required 12 Q1 executions and one unique Q1 value per run.
4. Calculated:

   ```text
   terminal_batch_records
     = Q1_COUNT - sum(record_count over stored ingestion rows).
   ```

5. Required `terminal_batch_records == lag_records_total` in the last stored batch.
6. Required `stored ingestion rows + 1 == completed ingestion commits`.
7. Required `data_file_count_before == 12 * completed ingestion commits` for the first data-file maintenance operation.
8. For Delta, additionally required:
   - exactly one reconstructed row with `source_metrics_present=false`;
   - terminal EventLog `write_stage_output_records` equal to the calculated terminal batch;
   - terminal EventLog batch ID equal to the number of stored metrics rows; and
   - `table_version_before == completed ingestion commits`.

The terminal row remains absent from latency, CPU, GC, shuffle, spill, and other batch-level analyses because those measurements cannot be recovered from Q1 or lag arithmetic.

## 5. Results for all 72 canonical runs

All three replications passed in every format/scenario cell. The values below are identical across the three replications of the listed cell.

| Format | Scenario | SF | MOPT | Replications checked | Q1 count | Sum of stored `record_count` | Stored batches | Calculated terminal records | Last stored lag | Completed commits | Pre-maintenance files | Result |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| Iceberg | B01 | 50 | 160,000 | 1, 2, 3 | 144,004,764 | 143,995,141 | 900 | 9,623 | 9,623 | 901 | 10,812 | PASS |
| Iceberg | B02 | 50 | 640,000 | 1, 2, 3 | 144,004,764 | 143,998,626 | 225 | 6,138 | 6,138 | 226 | 2,712 | PASS |
| Iceberg | B03 | 50 | 2,560,000 | 1, 2, 3 | 144,004,764 | 143,359,657 | 56 | 645,107 | 645,107 | 57 | 684 | PASS |
| Iceberg | B04 | 100 | 160,000 | 1, 2, 3 | 287,997,024 | 287,990,520 | 1,800 | 6,504 | 6,504 | 1,801 | 21,612 | PASS |
| Iceberg | B05 | 100 | 640,000 | 1, 2, 3 | 287,997,024 | 287,996,971 | 450 | 53 | 53 | 451 | 5,412 | PASS |
| Iceberg | B06 | 100 | 2,560,000 | 1, 2, 3 | 287,997,024 | 286,719,398 | 112 | 1,277,626 | 1,277,626 | 113 | 1,356 | PASS |
| Iceberg | B07 | 200 | 160,000 | 1, 2, 3 | 575,995,635 | 575,983,059 | 3,600 | 12,576 | 12,576 | 3,601 | 43,212 | PASS |
| Iceberg | B08 | 200 | 640,000 | 1, 2, 3 | 575,995,635 | 575,994,766 | 900 | 869 | 869 | 901 | 10,812 | PASS |
| Iceberg | B09 | 200 | 2,560,000 | 1, 2, 3 | 575,995,635 | 573,438,412 | 224 | 2,557,223 | 2,557,223 | 225 | 2,700 | PASS |
| Iceberg | B10 | 500 | 160,000 | 1, 2, 3 | 1,439,977,468 | 1,439,956,943 | 9,000 | 20,525 | 20,525 | 9,001 | 108,012 | PASS |
| Iceberg | B11 | 500 | 640,000 | 1, 2, 3 | 1,439,977,468 | 1,439,346,221 | 2,249 | 631,247 | 631,247 | 2,250 | 27,000 | PASS |
| Iceberg | B12 | 500 | 2,560,000 | 1, 2, 3 | 1,439,977,468 | 1,438,717,211 | 562 | 1,260,257 | 1,260,257 | 563 | 6,756 | PASS |
| Delta | B01 | 50 | 160,000 | 1, 2, 3 | 144,004,764 | 143,995,141 | 900 | 9,623 | 9,623 | 901 | 10,812 | PASS |
| Delta | B02 | 50 | 640,000 | 1, 2, 3 | 144,004,764 | 143,998,626 | 225 | 6,138 | 6,138 | 226 | 2,712 | PASS |
| Delta | B03 | 50 | 2,560,000 | 1, 2, 3 | 144,004,764 | 143,359,657 | 56 | 645,107 | 645,107 | 57 | 684 | PASS |
| Delta | B04 | 100 | 160,000 | 1, 2, 3 | 287,997,024 | 287,990,520 | 1,800 | 6,504 | 6,504 | 1,801 | 21,612 | PASS |
| Delta | B05 | 100 | 640,000 | 1, 2, 3 | 287,997,024 | 287,996,971 | 450 | 53 | 53 | 451 | 5,412 | PASS |
| Delta | B06 | 100 | 2,560,000 | 1, 2, 3 | 287,997,024 | 286,719,398 | 112 | 1,277,626 | 1,277,626 | 113 | 1,356 | PASS |
| Delta | B07 | 200 | 160,000 | 1, 2, 3 | 575,995,635 | 575,983,059 | 3,600 | 12,576 | 12,576 | 3,601 | 43,212 | PASS |
| Delta | B08 | 200 | 640,000 | 1, 2, 3 | 575,995,635 | 575,994,766 | 900 | 869 | 869 | 901 | 10,812 | PASS |
| Delta | B09 | 200 | 2,560,000 | 1, 2, 3 | 575,995,635 | 573,438,412 | 224 | 2,557,223 | 2,557,223 | 225 | 2,700 | PASS |
| Delta | B10 | 500 | 160,000 | 1, 2, 3 | 1,439,977,468 | 1,439,956,943 | 9,000 | 20,525 | 20,525 | 9,001 | 108,012 | PASS |
| Delta | B11 | 500 | 640,000 | 1, 2, 3 | 1,439,977,468 | 1,439,346,221 | 2,249 | 631,247 | 631,247 | 2,250 | 27,000 | PASS |
| Delta | B12 | 500 | 2,560,000 | 1, 2, 3 | 1,439,977,468 | 1,438,717,211 | 562 | 1,260,257 | 1,260,257 | 563 | 6,756 | PASS |

The validation covered **72 unique physical run IDs** and all **864 concrete Q1 executions**, with **36/36 PASS for Iceberg** and **36/36 PASS for Delta**. No run was repaired, substituted, or excluded by this amendment.

## 6. Format-specific evidential strength

### 6.1 Delta Lake

For every Delta run, the calculated terminal records agree with the single EventLog-reconstructed terminal batch that lacks an original metrics row. The reconstructed terminal batch ID is the next contiguous ID after the final stored metrics row. The pre-maintenance Delta table version also equals the completed commit count. Delta therefore has direct, mutually consistent row, EventLog, and table-version evidence.

### 6.2 Apache Iceberg

For every Iceberg run, Q1 minus the stored record sum agrees with the final stored lag. Pre-maintenance active files equal 12 times the completed commit count. This file-count/12 relationship is an independent **structural plausibility check** under the observed 12 active output partitions and one file per active partition per commit. It is not a native Iceberg snapshot count, and it does not replace the unavailable historical Iceberg EventLogs or snapshot-history export.

## 7. SF500 reconciliation incorporated

The amendment adopts the separately documented SF500 reconciliation:

- canonical SF500 Q1 cardinality: **1,439,977,468**;
- canonical B10 terminal batch: **20,525**;
- canonical B11 terminal batch: **631,247**;
- canonical B12 terminal batch: **1,260,257**.

The historical values 1,439,975,834 and 19,176 are not present in the retained canonical exports and are not assigned to a canonical run. Their original invalid-run provenance is no longer reconstructable.

## 8. Consequence for prior analyses

The amendment confirms the run counts, terminal-row counts, and commit counts already used by the locked analyses. It does not change the 72-run manifest, query neutralization estimates, temporal break-even estimates, retained-metadata models, or any inferential rule. Its effect is limited to strengthening the audit trail and narrowing claims about Iceberg commit verification and cross-topic data identity.

## 9. Final amendment decision

**PASS.** The n-1 reconciliation is explicitly validated for all 72 canonical runs. Manuscript release may use the confirmed cardinalities and terminal-batch values, provided that:

1. Delta's direct table-version/EventLog confirmation and Iceberg's structural file-count corroboration are not described as equivalent evidence;
2. separate Kafka topic populations are not described as byte-identical without a retained payload or offset manifest; and
3. the old printed Iceberg query-export hash is superseded by the corrected hash in this amendment.
