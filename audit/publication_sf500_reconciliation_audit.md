# SF500 Cardinality and Terminal-Batch Reconciliation Audit

**Audit date:** 2026-10-25  
**Scope:** Apache Iceberg and Delta Lake scenarios B10, B11, and B12, all three canonical replications per format  
**Mode:** Read-only reconciliation; no source data, canonical manifests, statistical specifications, or published result files were modified

## 1. Executive decision

**Decision: CONDITIONAL PASS.**

The numerical reconciliation passes for all 18 canonical SF500 runs. Every preserved Q1 execution, including warm-up and measured executions before and after maintenance, returns **1,439,977,468 rows**. For every run, the difference between this Q1 count and the sum of the stored `record_count` values equals both the last stored `lag_records_total` and the independently reconstructed terminal batch where Delta EventLogs are available. The canonical B10 terminal batch is **20,525 records**, not 19,176.

The condition concerns provenance wording and audit implementation, not the canonical numbers. The previously mentioned values **1,439,975,834** and **19,176** cannot be tied to any surviving canonical query row, ingestion row, maintenance row, or reconstructed Delta EventLog row. They must not be presented as values from a canonical run. In addition, the final publication audit copied the n-1 terminal-row value from an upstream run summary instead of recalculating and asserting it locally. The upstream calculation is correct, but this weakens the audit trail. A versioned, non-statistical amendment should make that assertion explicit before manuscript release.

No evidence was found that requires replacing a canonical run or recomputing the neutralization, break-even, or retained-metadata analyses.

## 2. Evidence base and definitions

### 2.1 Canonical sources

The audit used only retained original or canonical exports:

| Evidence | Iceberg source | Delta source |
|---|---|---|
| Canonical run selection | `publication_canonical_run_manifest.csv` | `publication_canonical_run_manifest.csv` |
| Q1 results | `iceberg_metrics_exports_20261024/query_metrics.csv` | `delta_metrics_exports_20261024/query_metrics.csv` |
| Stored micro-batch metrics | `iceberg_metrics_exports_20261024/metrics_ingestion.csv` | `delta_metrics_exports_20261024/metrics_ingestion.csv` |
| Pre-maintenance state | `iceberg_metrics_exports_20261024/compaction_operation_metrics.csv` | `delta_metrics_exports_20261024/compaction_operation_metrics.csv` |
| EventLog reconstruction | Not historically available | `delta_metrics_exports_20261024/metrics_ingestion_phases_reconstructed.csv` |
| Final integrity audit | `audit_publication_data_integrity.py` and `publication_data_integrity_audit.md` | Same |
| Upstream n-1 reconstruction | `analyze_metadata_amplification_scaling.py` | Same |

The complete run-level evidence is preserved in `publication_sf500_run_reconciliation.csv`. Its SHA-256 digest at creation was:

```text
B8A291B4D5E68BE357D51D17BBB87F7EF882C93AED152A92FF9CFF11729BC58B
```

### 2.2 Reconciliation definitions

- **Q1 count:** the `row_count` returned by the concrete canonical `SELECT COUNT(*)` query row.
- **Stored batch count:** number of rows retained by the ingestion metrics collector for the run.
- **Stored record sum:** sum of `record_count` over those retained rows.
- **Calculated terminal batch:** `Q1 count - stored record sum`.
- **Completed commits:** stored batch count plus the known terminal commit omitted by the n-1 collector alignment.
- **Independent commit evidence:** Delta table version and reconstructed EventLog batch count; for Iceberg, the exact pre-maintenance active-file count together with the consistently observed 12 files per completed commit.
- **Last stored lag:** `lag_records_total` in the last stored metrics row. This is supporting evidence derived from the streaming progress offset lag, not an independent row count.

The collector records batch *n* only when progress for batch *n + 1* is available. It therefore omits the final completed batch. No missing terminal row was imputed into the original metrics table.

## 3. Q1 cardinality audit

### 3.1 Direct query evidence

Each of the 18 canonical runs contains 12 Q1 executions:

- three pre-maintenance warm-up executions;
- three pre-maintenance measured executions;
- three post-maintenance warm-up executions; and
- three post-maintenance measured executions.

All **216 Q1 executions** return exactly **1,439,977,468**. Every run has one unique Q1 value, and all rows share the result hash:

```text
b62dc94a5d7b89181fd7272d3a78937f8f852c37fcdf209a30d974501906346b
```

Pre- and post-maintenance equality also confirms that native maintenance did not change table cardinality.

### 3.2 Scenario-level reconciliation

The following values are identical across all three replications and both formats within each scenario:

| Scenario | MOPT | Q1 count | Stored rows | Stored batch IDs | Last stored batch records | Calculated terminal batch | Last stored lag | Completed commits | Pre-maintenance files |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| B10 | 160,000 | 1,439,977,468 | 1,439,956,943 | 0-8,999 | 159,995 | **20,525** | 20,525 | 9,001 | 108,012 |
| B11 | 640,000 | 1,439,977,468 | 1,439,346,221 | 0-2,248 | 639,993 | **631,247** | 631,247 | 2,250 | 27,000 |
| B12 | 2,560,000 | 1,439,977,468 | 1,438,717,211 | 0-561 | 2,559,994 | **1,260,257** | 1,260,257 | 563 | 6,756 |

For each scenario, the identity

```text
stored record sum + calculated terminal batch = Q1 count
```

holds exactly.

### 3.3 Independent commit and terminal-batch evidence

For Delta, the pre-maintenance table versions are 9,001, 2,250, and 563 for B10, B11, and B12, respectively. The EventLog postprocessing contains the same number of reconstructed batches and explicitly identifies the omitted terminal batches:

| Scenario | Reconstructed terminal batch ID | EventLog output records | Reconstruction status |
|---|---:|---:|---|
| B10 | 9,000 | 20,525 | `missing_original_metrics_row` |
| B11 | 2,249 | 631,247 | `missing_original_metrics_row` |
| B12 | 562 | 1,260,257 | `missing_original_metrics_row` |

This is direct independent confirmation of the n-1 reconciliation for Delta.

Historical Iceberg EventLogs are unavailable. Iceberg nevertheless has exact pre-maintenance active-file totals of 108,012, 27,000, and 6,756. Dividing by the consistently observed 12 output files per completed commit yields 9,001, 2,250, and 563. This corroborates the commit counts, but it is not a native Iceberg snapshot-count measurement. Publication text should preserve this distinction.

## 4. Resolution of the contradictory values

### 4.1 Cardinality 1,439,977,468

**Status: confirmed.**

This value is read directly from every concrete canonical SF500 query run. It is also consistent with the stored ingestion record sums plus the reconstructed terminal batches for B10, B11, and B12.

### 4.2 Cardinality 1,439,975,834

**Status: not supported by retained canonical evidence.**

The value is 1,634 below the canonical count. It does not occur in the canonical manifest, query exports, ingestion exports, maintenance exports, Delta reconstruction, current analysis reports, or surviving local historical exports examined by this audit. The retained audit narrative records that an earlier, invalid SF500/B10 attempt differed by 1,634 rows, but the raw metrics or source manifest for that attempt no longer exists.

Therefore:

- the 1,634 discrepancy cannot be assigned to a particular retained run ID;
- its cause cannot be proven as HDFS input loss, producer truncation, Kafka loss, consumer failure, or another mechanism; and
- 1,439,975,834 must not be used as the SF500 cardinality of any canonical run.

### 4.3 B10 terminal value 20,525

**Status: confirmed.**

For all six canonical B10 runs:

```text
1,439,977,468 - 1,439,956,943 = 20,525
```

The last stored lag is 20,525 in every run. Delta EventLogs independently reconstruct batch 9,000 with 20,525 output records.

### 4.4 B10 terminal value 19,176

**Status: not supported by retained canonical evidence.**

No canonical B10 source contains this value. It is incompatible with the direct Q1 count and stored-record sum. It may have originated from a superseded calculation or invalid execution, but no retained artifact permits that attribution to be established. It must not appear in the manuscript as a canonical terminal-batch value.

## 5. Audit of the previous canonical audit

### 5.1 Was Q1 read per canonical run?

**Yes.** The final audit did not copy one global SF500 reference value into all runs.

In `audit_publication_data_integrity.py`, query rows are first selected by the concrete canonical ingestion-run key. `extract_q1_count()` then parses Q1 results from those selected rows and requires one unique value. The result is compared with the run-level summary value and written to the manifest. The upstream metadata analysis likewise reads the measured pre-maintenance Q1 result for each run directly from the canonical query export.

The claim that every canonical SF500 run has 1,439,977,468 rows is therefore based on concrete run-level query rows.

### 5.2 Weakness in the final audit

The field `missing_final_batch_rows` in the final audit is copied from the upstream run-level summary. The final audit does not itself recompute:

```text
Q1 count - sum(record_count)
```

nor assert equality with `lag_records_total` or the Delta EventLog terminal row. The upstream script does compute the subtraction directly, so the resulting values are numerically correct. The weakness is a missing independent assertion in the final audit layer, not a wrong result.

### 5.3 Overbroad independent-validation wording

The statement that the terminal commit was independently validated from “Q1/maintenance state” needs a format-specific qualification:

- Delta has exact table-version and EventLog evidence.
- Iceberg has Q1 plus active-file-count corroboration under the observed 12-files-per-commit pattern, but no preserved native snapshot-count export and no historical EventLog.

### 5.4 Historical 1,634-record statement

The earlier audit correctly said that the exact cause could not be proven. However, wording that the invalid source “was regenerated/replayed” should be confined to documented canonical topic populations. The lifecycle of the rejected 1,634-short attempt itself is not reconstructable from a retained raw run artifact.

## 6. Kafka data lifecycle reconstruction

### 6.1 Evidence classes

The lifecycle reconstruction uses three evidence classes:

1. **Documented fact:** broker controller-log create/delete records, topic configuration, canonical source timestamps, and canonical metrics rows.
2. **Derived fact:** a topic population window inferred from the minimum and maximum Kafka source-event timestamps retained in ingestion metrics.
3. **Not reconstructable:** an operation for which neither a timestamped producer log nor an offset manifest survives.

Kafka source-event maxima exclude the omitted terminal batch and are therefore “last observed in stored metrics,” not exact producer completion times.

### 6.2 Topic operations and effective retention

The retained broker history shows repeated deletion and recreation of `store_sales`, including operations on 2026-06-27, 2026-06-28, 2026-07-11, 2026-07-15, multiple times on 2026-07-28, 2026-08-05, 2026-08-09, 2026-08-18 through 2026-08-20, 2026-08-25/26, 2026-09-10, 2026-09-25, 2026-10-06, 2026-10-18, and 2026-10-21.

The normal topic-creation script configured:

```text
partitions=12
replication.factor=3
cleanup.policy=delete
retention.ms=1209600000       # 14 days
delete.retention.ms=86400000  # 1 day
segment.ms=3600000            # 1 hour
min.insync.replicas=2
compression.type=zstd
```

One retained 2026-07-28 creation record shows no explicit topic overrides. During that topic lifetime the broker-level fallback was `log.retention.hours=168`, or seven days. The effective historical retention was therefore not uniformly 14 days for every topic incarnation.

### 6.3 Reconstructed scale-factor populations

| Scale factor | Format/campaign | Observed source-event window | Relevant topic evidence | Interpretation |
|---|---|---|---|---|
| SF50 | Iceberg | 2026-07-28 13:28:03 to 14:55:45 UTC | Topic recreated around 13:26 | One observed population used by the Iceberg SF50 campaign |
| SF50 | Delta | 2026-10-22 01:25:13 to 02:22:25 UTC | Topic recreated on 2026-10-21 | Separate later population |
| SF100 | Iceberg, initial | 2026-08-05 05:47 to 08:16 UTC | Topic recreated on 2026-08-05 | Population used by the initial Iceberg runs |
| SF100 | Iceberg, B04 reruns | 2026-08-18 06:12 to 09:38 UTC | Topic recreated on 2026-08-18 | Separate replay for retained B04 reruns |
| SF100 | Delta | 2026-10-18 03:23 to 08:00 UTC | Topic recreated immediately beforehand | Separate later population |
| SF200 | Iceberg | 2026-08-09 17:13 to 21:29 UTC | Topic recreated on 2026-08-09 | One observed population |
| SF200 | Delta | 2026-10-06 16:56 to 21:07 UTC | Topic recreated immediately beforehand | Separate later population |
| SF500 | Iceberg B11/B12 | 2026-07-15 06:02:17 to approximately 16:19:26 UTC | Topic recreated on 2026-07-15 | Shared population for these canonical runs |
| SF500 | Iceberg B10 | 2026-08-26 13:13:44 to 2026-08-27 01:30:58 UTC | Topic recreated at 13:13 on 2026-08-26 | Separate B10 replay |
| SF500 | Delta B10 Rep 1 | 2026-09-10 03:02:19 to 16:10:08 UTC | Topic recreated at 03:00 on 2026-09-10 | Separate population |
| SF500 | Delta B10 Rep 2/3 and B11/B12 | From 2026-09-25 09:30:56 UTC; last observed time varies by MOPT up to 21:19:04 | Topic recreated at 09:29 on 2026-09-25 | Shared later population |

Only one standalone producer log survives, for an earlier SF1000 operation. Shell history contains producer invocations but lacks timestamps. Consequently, the exact start and completion time of every historical producer process cannot be reconstructed independently of the Kafka source timestamps.

### 6.4 Were replications fed identical data?

Within each preserved topic population, equal Kafka source timestamp ranges and equal per-batch record/lag sequence hashes provide strong evidence that replications consumed the same offset sequence. Across separate topic recreations, byte-identical payload equality cannot be proven because no per-record payload hash or partition-offset manifest was retained.

For SF500, all canonical runs nevertheless agree on:

- Q1 count and Q1 hash;
- Q2 aggregate and result hash;
- Q3 aggregate and result hash; and
- per-scenario batch record/lag sequence hash.

The sequence hashes are:

| Scenario | SHA-256 over `micro_batch_id|record_count|lag_records_total` |
|---|---|
| B10 | `4af730a66c5c5fc40be186f363a1196611d6606ec6ada41ad3f5bffcee5e4666` |
| B11 | `791ac5cd5081421dfc30b276cb2ef4672c2cb55c9c25db08d0764631a4332c60` |
| B12 | `0a6a8a717d4c6e1bbb02f59718629e199ad1abb2e3a5f4bde21829a6c2187102` |

This supports content equivalence for the measured aggregates and batch cardinalities. It does not establish that every replication read the same physical Kafka topic incarnation or byte-identical serialized records.

### 6.5 Cause of the 1,634-record difference

**Not reconstructable.** No surviving producer log, offset manifest, rejected-run metrics export, or payload checksum identifies where those records were lost or omitted. Assigning the difference to TPC-DS generation, HDFS storage, Kafka production, retention, broker failure, or consumer behavior would be speculation.

## 7. Consequences for the canonical evidence

### 7.1 Canonical 72-run dataset

The SF500 subset passes direct reconciliation. No canonical run has the short count. No canonical-run replacement is required.

### 7.2 Neutralization analysis

No numerical effect is identified. The analysis uses canonical query rows selected by canonical run identifiers. All SF500 pre/post Q1 checks agree, and the primary Q2/Q3 query rows belong to those same validated run keys.

### 7.3 Query break-even analysis

No numerical effect is identified. The break-even inputs are canonical pre/post query times and canonical maintenance times. The cardinality and terminal-batch reconciliation does not alter those inputs.

### 7.4 Retained metadata analysis

No numerical effect is identified. The SF500 commit counts used by the analysis are consistent with the exact n-1 reconstruction. Delta is independently confirmed by table versions and EventLogs. Iceberg commit counts are corroborated by the pre-maintenance active-file totals and observed files-per-commit pattern, subject to the evidence qualification stated above.

### 7.5 Manuscript locations affected

The following locations are numerically correct but need careful wording:

- `manuscript_section_03_experimental_design.md`: the SF500 cardinality **1,439,977,468** is confirmed. The phrase “independently verified ... by maintenance state” should distinguish Delta table-version evidence from Iceberg file-count corroboration.
- `manuscript_section_03_experimental_design.md`: the n-1 description is correct, but the validation source should be format-specific.
- `manuscript_section_05_ingestion_created_physical_state.md`: B10 terminal **20,525**, B11 terminal **631,247**, and B12 terminal **1,260,257** are confirmed.
- Any statement that all replications used an “identical Kafka dataset” should be narrowed to identical measured cardinalities, query-result hashes, and per-scenario batch-count sequences. Some canonical groups were produced in separate topic incarnations.
- Any surviving mention of **1,439,975,834** or **19,176** as canonical must be removed through a versioned editorial amendment.

## 8. Required versioned amendment before release

The following amendment is recommended without changing raw data, the canonical manifest, or statistical results:

1. Add a run-local assertion to the publication audit that recomputes `Q1 - sum(record_count)` and checks it against the final stored lag.
2. For Delta, assert equality with reconstructed terminal EventLog output and table version.
3. For Iceberg, label the file-count/12 relation as corroboration rather than a native snapshot-count observation.
4. State explicitly that 1,439,975,834 and 19,176 are unsupported historical values excluded from the canonical evidence.
5. Replace “identical Kafka datasets” with the exact supported statement: identical canonical query results and batch cardinality sequences, with separate topic populations documented where applicable.

This amendment is an audit-trail and wording correction. It does not authorize or require recalculation of any statistical endpoint.

## 9. Final disposition

**CONDITIONAL PASS** is appropriate because:

- all 18 run-level reconciliations pass;
- all 216 concrete canonical Q1 executions agree;
- the n-1 terminal arithmetic closes exactly for every run;
- Delta supplies independent EventLog and table-version confirmation;
- no canonical result uses the 1,634-short cardinality or the 19,176 terminal value; but
- lifecycle provenance is incomplete for the rejected historical attempt, and the final audit should explicitly recalculate rather than inherit its n-1 assertion.

The manuscript results may proceed only after the versioned wording and audit-trail amendment above is recorded. No statistical model or canonical-run selection needs to be changed on the evidence currently available.
