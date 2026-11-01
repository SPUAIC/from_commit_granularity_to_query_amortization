# Publication Data Integrity Amendment v1.2

**Date:** 2026-10-26  
**Status:** Versioned amendment to `publication_data_integrity_audit.md` and v1.1  
**Mode:** Read-only provenance validation  
**Decision:** PASS for the 72-run canonical corpus; historical B10 provenance corrected without changing canonical run selection or locked statistical results

## 1. Purpose and scope

This amendment preserves the run-local n-1 validation introduced in v1.1 and corrects the historical provenance of the non-canonical B10 values 1,439,975,834 and 19,176. It does not replace or silently edit the original audit or v1.1. It distinguishes three separate questions: whether a run completed correctly under its own input, whether its input was comparable with the later SF500 campaign, and whether it was admitted to the canonical scientific corpus.

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
| 1.2 | Recovered the 25 August B10 export set and assigned 1,439,975,834 and 19,176 to three concrete August executions | Corrects the v1.1 statement that their run provenance was no longer reconstructable | No change to the canonical corpus or results |
| 1.2 | Separated technical execution validity, input comparability, and canonical eligibility | A technically complete execution can still be unsuitable for a controlled comparison | Reporting clarification |
| 1.2 | Documented the intervening 4-executor/64-core replacement and the accepted 5-executor/80-core replacements | Completes the B10 replacement history | Confirms existing exclusion and inclusion decisions |
| 1.2 | Narrowed the interpretation of `startingOffsets=earliest` and `failOnDataLoss=true` | These settings do not independently prove that no offsets expired before consumer start | Validity-boundary clarification |
| 1.2 | Assigned Tables 1-3 to Section 3 and Table 4 to Section 4; reserved Table 5 for Section 5, Tables 6-9 for Section 6, and Tables 10-11 for Section 7 | Removes duplicate numbering across standalone drafts | Editorial renumbering only; later standalone sections require caption-only updates at assembly |

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

### 3.1 Historical B10 provenance sources added in v1.2

The following preserved exports were inspected as historical evidence. The first three files were exported on 25 August 2026 from the three earlier B10 replications. The remaining files document the first replacement attempt and the subsequently accepted replacement.

| Historical source | Evidential role | SHA-256 |
|---|---|---|
| `/home/ubuntu/work/exports/b10_metrics_select_all_20260825_051452Z/metrics_ingestion_b10_select_all.csv` | Three earlier B10 ingestion executions, resource profile, stored record sums, and final lag | `171BB484FA1EAB59BE7FB05C063A95F23F5A50D06E1AC89526D61D8744C8F4C5` |
| `/home/ubuntu/work/exports/b10_metrics_select_all_20260825_051452Z/query_metrics_b10_select_all.csv` | Earlier B10 Q1 results before and after maintenance | `7FFA05D951093DCA289595B6E1777F6D597594967DD7DE8871103A08E244C232` |
| `/home/ubuntu/work/exports/b10_metrics_select_all_20260825_051452Z/compaction_operation_metrics_b10_select_all.csv` | Six recorded Iceberg maintenance operations for the earlier B10 executions | `431654710F7D6CE030DE3A0DF6CCCBB7F98041F655CA846849FABC4A9A262F86` |
| `/home/ubuntu/work/metrics_exports/b10_select_all/metrics_ingestion_b10_select_all.csv` | First replacement ingestion with the later cardinality but a 4-executor/64-core profile | `89A27C05DA452B6754334380115D4713D4353ECDB7F2E18E5777CF2250797E00` |
| `/home/ubuntu/work/metrics_exports/b10_select_all/query_metrics_b10_select_all.csv` | Q1 validation for the 4/64 replacement | `5F166DA4541A67BD6E71A28D490EFA47FC3C0ED98A27A49AEE4718A3902057B9` |
| `/home/ubuntu/work/metrics_exports/b10_ingestion_select_all/metrics_ingestion_b10_current_select_all.csv` | Accepted Replication 1 ingestion with a 5-executor/80-core profile | `566096F48078AEC565B5B4AC557DBCD59AB634DE464978FCAE4482AEA054E5B7` |
| `publication_canonical_run_manifest.csv` and the 24 October canonical exports | Accepted B10 Replications 1-3 and all later canonical analyses | Hashes listed above |

The requested narrative file `consistency_check_findings.md` was not present in the local evidence directory, anywhere under `/home/ubuntu` on the RaaS master, or in the inspected ZIP archives at the time of this audit. Its statements are therefore not quoted as evidence. The numerical provenance below is reconstructed directly from the preserved CSV exports, and the absence of the narrative file is an explicit limitation rather than a basis for inference.

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

## 7. Corrected historical B10 provenance

### 7.1 Earlier technically valid B10 executions

The 25 August export contains three concrete Iceberg B10 executions:

| Replication | Full ingestion run ID | Stored batches | Sum of stored `record_count` | Q1 count | Calculated terminal | Last stored lag | Executors / cores |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | `B10_r01_store_sales_sf500_mopt160000_20260821_053601Z` | 9,000 | 1,439,956,658 | 1,439,975,834 | 19,176 | 19,176 | 5 / 80 |
| 2 | `B10_r02_store_sales_sf500_mopt160000_20260822_062516Z` | 9,000 | 1,439,956,658 | 1,439,975,834 | 19,176 | 19,176 | 5 / 80 |
| 3 | `B10_r03_store_sales_sf500_mopt160000_20260823_150951Z` | 9,000 | 1,439,956,658 | 1,439,975,834 | 19,176 | 19,176 | 5 / 80 |

For every one of these executions, the ingestion rows are contiguous from batch 0 through batch 8,999, the Q1 value is constant across the twelve pre/post warm-up and measured Q1 executions, pre/post Q1 hashes agree, and the terminal arithmetic closes exactly:

```text
1,439,975,834 - 1,439,956,658 = 19,176.
```

The preserved maintenance export also contains the two expected Iceberg operations for each replication. These observations support **technical execution validity under that topic population**. The runs were not rejected because they crashed, were incomplete, or used the wrong executor profile.

### 7.2 Why the executions were not scientifically canonical

The later SF500 population used by the accepted comparison campaign has Q1 count 1,439,977,468, which is 1,634 records greater than the earlier population. The earlier B10 executions therefore did not share the validated input cardinality and result hash of the later canonical SF500 population used to align B10 with the retained B11/B12 evidence and the later Delta campaign. They were superseded on **input-comparability grounds**, despite being technically complete.

This provenance finding does not identify why the two separately produced Kafka populations differ by 1,634 records. No retained payload checksum, producer-completion manifest, or complete partition-offset manifest establishes whether the difference arose during source generation, HDFS staging, production, retention, broker handling, or another step. The origin of the numerical values is now known; the technical mechanism that produced the difference remains unresolved. These are separate statements.

### 7.3 Replacement sequence and canonical admission

The first replacement, `B10_r01_store_sales_sf500_mopt160000_20260827_061333Z`, used the later Q1 cardinality 1,439,977,468 and reconciled to a 20,525-record terminal batch. It completed with four executors and 64 total executor cores. It was therefore excluded because its resource profile differed from the experiment's fixed five-executor/80-core profile.

The accepted Iceberg B10 replacements were:

| Replication | Canonical ingestion run ID | Q1 count | Terminal batch | Executors / cores |
|---:|---|---:|---:|---:|
| 1 | `B10_r01_store_sales_sf500_mopt160000_20260828_163243Z` | 1,439,977,468 | 20,525 | 5 / 80 |
| 2 | `B10_r02_store_sales_sf500_mopt160000_20260902_042804Z` | 1,439,977,468 | 20,525 | 5 / 80 |
| 3 | `B10_r03_store_sales_sf500_mopt160000_20260903_044849Z` | 1,439,977,468 | 20,525 | 5 / 80 |

The canonical Delta B10 runs also use Q1 count 1,439,977,468, terminal batch 20,525, and the 5/80 profile. Thus, canonical admission required both input comparability and the intended resource profile, in addition to technical completion.

### 7.4 Kafka offset-setting interpretation

The consumers used fresh checkpoints, `startingOffsets=earliest`, and `failOnDataLoss=true`. `earliest` means the earliest offset still available when a new query starts; it does not prove that no older offsets had already expired. Likewise, `failOnDataLoss=true` can detect relevant offset discontinuities encountered by the query, but it is not an independent historical proof that retention had removed nothing before startup.

For the 72 canonical runs, no incomplete consumption was observed: final sink cardinalities match the concrete canonical Q1 results, terminal-batch reconciliation closes, and the validated scenario-specific results agree. The stronger claim that pre-start historical retention loss was technically impossible is not made.

## 8. Consequence for prior analyses

The amendment confirms the run counts, terminal-row counts, and commit counts already used by the locked analyses. It does not change the 72-run manifest, query neutralization estimates, temporal break-even estimates, retained-metadata models, or any inferential rule.

It supersedes two historical-provenance statements only:

1. `publication_data_integrity_audit.md` described the 1,634-short B10 execution as an invalid execution lacking a retained raw export. The preserved 25 August export instead shows three technically complete executions. They were scientifically excluded because their input population differed from the later canonical SF500 population.
2. `publication_data_integrity_amendment_v1.1.md` stated that the run provenance of 1,439,975,834 and 19,176 was no longer reconstructable. Their provenance is now assigned to the three full run IDs in Section 7.1. The cause of the 1,634-record population difference remains not reconstructable.

No manuscript result based on the canonical 72 runs changes. The amendment strengthens the audit trail and narrows claims about topic retention, Iceberg commit verification, cross-topic data identity, and the distinction between execution validity and scientific comparability.

## 9. Final amendment decision

**PASS.** The n-1 reconciliation remains explicitly validated for all 72 canonical runs, and the earlier B10 values now have a documented non-canonical provenance. Manuscript release may use the confirmed cardinalities and terminal-batch values, provided that:

1. Delta's direct table-version/EventLog confirmation and Iceberg's structural file-count corroboration are not described as equivalent evidence;
2. separate Kafka topic populations are not described as byte-identical without a retained payload or offset manifest; and
3. `startingOffsets=earliest` and `failOnDataLoss=true` are not treated as proof that no offsets expired before consumer startup;
4. the technically valid but input-incomparable August B10 executions are not described as failed runs; and
5. the old printed Iceberg query-export hash is superseded by the corrected hash in this amendment.
