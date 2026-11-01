# Final Statistical Analysis Specification v1.0

Status: **LOCKED FOR IMPLEMENTATION BEFORE FINAL RESULT CALCULATION**  
Specification date: 2026-10-25  
Bootstrap seed: `20261025`  
Nominal two-sided alpha: `0.05`

## 1. Purpose and scope

This document fixes the remaining statistical analyses for the Iceberg/Delta Lake journal article. It is based on the completed integrity audit, the v5.1 methodology proposal, the documented deviations, and the canonical 72-run manifest.

No result is calculated in this specification. It is a prospective lock for the final analysis stage, not a retrospective preregistration of the completed experiments or exploratory analyses.

## 2. Authoritative inputs

Only rows whose exact `canonical_ingestion_run_id` occurs in `publication_canonical_run_manifest.csv` with `included_in_canonical_dataset=true` and `validation_status=VALIDATED_CANONICAL` are eligible.

Authoritative metric sources are the paths recorded per run in that manifest:

- Iceberg: `iceberg_metrics_exports_20261024/`
- Delta: `delta_metrics_exports_20261024/`

Older exports, superseded B10 identifiers, malformed CSV exports, and deleted experimental attempts are ineligible. Inputs are read-only. Final-analysis code must abort rather than silently repair, impute, or substitute a run.

## 3. Analysis units and query dataset

### 3.1 Independent unit

The independent experimental unit is the physical ingestion run. There are 36 runs per format and three runs per SF/MOPT cell.

Micro-batches, query repetitions, and pre/post observations are repeated measurements within a physical run and are not independent replications.

### 3.2 Eligible query records

For every canonical run, query records must satisfy all of the following:

- `status = success`;
- `is_warmup = false`;
- `phase` is exactly `pre_compaction` or `post_compaction`;
- `query_id` is Q2 or Q3 for the primary analysis, or Q1 for the secondary control;
- `query_wall_time_ms > 0`;
- exactly three measured repetitions exist per run, phase, and query;
- the SQL hash is constant within each query definition;
- pre/post result hashes agree for a run and query.

Failure of any condition is an integrity error. The affected result is not automatically repaired or replaced.

### 3.3 Run-level query value

The primary run-level value is the arithmetic mean, in milliseconds, of the three measured repetitions:

`T_mean(i,p,q) = mean(T(i,p,q,1), T(i,p,q,2), T(i,p,q,3))`

The sensitivity value is their median:

`T_median(i,p,q) = median(T(i,p,q,1), T(i,p,q,2), T(i,p,q,3))`

Warmups are excluded. The logarithmic response is calculated after aggregation:

`y(i,p,q) = log2(T_mean(i,p,q))`

The sensitivity analysis replaces `T_mean` with `T_median` and changes nothing else.

## 4. Primary research question

**To what extent does native maintenance neutralize the association between micro-batch size and analytical query wall time?**

Primary queries: Q2 and Q3.  
Formats: Iceberg and Delta, modeled separately.  
Q1: secondary control, excluded from the primary multiplicity family.

The term “neutralize” refers to a reduction in the absolute MOPT elasticity after maintenance. It does not imply causal isolation of a storage-format mechanism beyond the controlled experiment.

## 5. Primary regression model

For each format `f` and query `q` separately, fit one joint pre/post ordinary least-squares model over 72 observations (36 runs times two phases):

`y(i,p,q) = alpha + beta_pre*x(i) + delta*Post(p) + theta*x(i)*Post(p) + SF_FE(i) + Post(p)*SF_FE(i) + error(i,p,q)`

where:

- `x(i) = log2(MOPT(i) / 160000)`;
- `Post = 0` for pre-maintenance and `1` for post-maintenance;
- SF is categorical with SF50 as the reference level;
- `SF_FE` contains indicators for SF100, SF200, and SF500;
- `Post*SF_FE` permits the phase shift to differ by SF.

The estimands are:

- `beta_pre = coefficient(x)`;
- `beta_post = beta_pre + theta`;
- `slope_change = theta`;
- `absolute_slope_reduction = abs(beta_pre) - abs(beta_post)`;
- `neutralization = 1 - abs(beta_post)/abs(beta_pre)`.

Because both response and MOPT are on a log2 scale, each beta is an elasticity. `2^beta - 1` is the proportional query-time change associated with a doubling of MOPT, conditional on SF.

Point estimates use all eligible runs. Cluster-robust covariance uses physical run ID as the cluster, finite-sample correction enabled, and `G-1 = 35` reference degrees of freedom. The primary raw p-value tests the two-sided null `theta = 0`.

## 6. Neutralization interpretation rules

Neutralization is never truncated.

- `neutralization = 1`: complete removal of the estimated slope magnitude.
- `0 < neutralization < 1`: partial reduction.
- `neutralization = 0`: unchanged magnitude.
- `neutralization < 0`: amplification after maintenance.
- A pre/post sign reversal is flagged as `SLOPE_SIGN_REVERSAL`; the two slopes must then be interpreted directly because an absolute-value ratio hides the reversal.

### 6.1 Near-zero and unstable denominator

The ratio is `NOT_ESTIMABLE_NUMERIC` if `abs(beta_pre) < 1e-8`.

It is flagged `UNSTABLE_DENOMINATOR` if either condition holds:

1. the 95% interval for `beta_pre` contains zero; or
2. fewer than 95% of finite bootstrap estimates of `beta_pre` have the same sign as the full-sample estimate.

For `UNSTABLE_DENOMINATOR`, the point ratio may be listed for transparency but cannot support the primary scientific conclusion. If more than 5% of bootstrap ratios are non-finite because of a near-zero denominator, no neutralization interval is reported. In every such case, `beta_pre`, `beta_post`, `theta`, and `absolute_slope_reduction` remain the primary interpretable quantities.

## 7. Bootstrap specification

### 7.1 Resampling design

- Number of draws: 10,000.
- Pseudorandom seed: `20261025`.
- Resampling unit: physical ingestion run.
- Strata: exact `(table_format, scale_factor, mopt)` cells.
- Draw three run IDs with replacement from each of the 24 strata in every bootstrap draw.
- A selected run carries both phases, all three queries, and all three measured repetitions together.
- Repeated selections receive distinct bootstrap cluster-copy IDs.
- The same draw is used for Q2 and Q3 so their covariance is retained.
- Formats are fitted separately, but their stratum draws are generated within the same numbered bootstrap iteration.

This preserves the paired pre/post structure and the balanced factorial allocation. It does not treat batches or query repetitions as independent observations.

### 7.2 BCa intervals

Primary 95% confidence intervals for `beta_pre`, `beta_post`, `theta`, `absolute_slope_reduction`, and neutralization use bias-corrected and accelerated (BCa) intervals.

Acceleration is computed from a delete-one-physical-run jackknife within each format. A jackknife fit may be unbalanced but must remain full rank.

BCa is accepted only if:

- at least 9,500 of 10,000 estimates are finite;
- all required jackknife fits are finite and full rank;
- the acceleration and bias-correction values are finite;
- both adjusted quantiles lie strictly inside the empirical bootstrap range;
- interval endpoints are finite.

### 7.3 Locked fallback

If BCa fails the criteria above but at least 9,500 finite estimates exist, use the two-sided 2.5th and 97.5th percentile interval and label it `PERCENTILE_FALLBACK`.

If fewer than 9,500 finite estimates exist, report `CI_NOT_ESTIMABLE`; do not substitute a normal-theory interval for that derived estimand. Model coefficients may still retain their cluster-robust intervals if the model is full rank.

The low count of three runs per cell limits precision. Bootstrap intervals quantify sampling variability under the observed cell structure; they do not create additional independent replications.

## 8. Multiplicity control

The primary family contains exactly four two-sided tests of `theta = 0`:

1. Iceberg Q2;
2. Iceberg Q3;
3. Delta Q2;
4. Delta Q3.

Apply Holm's step-down procedure at family-wise alpha 0.05 to the four cluster-robust raw p-values. Report both raw and Holm-adjusted p-values.

A primary neutralization claim requires all of the following:

- Holm-adjusted `p < 0.05` for `theta`;
- `absolute_slope_reduction > 0`;
- a stable `beta_pre` denominator;
- no contradictory slope-sign interpretation.

Q1, per-SF models, warm-cache-only models, and median-based models are sensitivity or secondary analyses and cannot generate a new confirmatory claim.

## 9. Cache-mode handling

The primary analysis includes all 36 runs per format. The five Iceberg runs labeled `cache_mode=none` remain included because each has paired pre/post measurements and passed the integrity audit.

No claim of equal cache state is permitted.

A locked sensitivity analysis repeats the entire Iceberg model using only runs whose query rows are all `warm_cache`. This leaves 31 Iceberg runs and removes the complete B02 cell. The resulting design is unbalanced and must be labeled accordingly. Delta remains unchanged because all Delta query rows are `warm_cache`.

## 10. Additional sensitivity analyses

### 10.1 Median aggregation

Repeat the four primary models using the median of the three measured repetitions. Use the same transformations, model terms, bootstrap draws, and reporting rules. No separate multiplicity family is created.

### 10.2 SF-specific slopes

For each format, query, phase, and SF, estimate a descriptive OLS slope of `log2(query time)` on `log2(MOPT/160000)` using the nine physical runs at that SF. Report the estimate and uncertainty as exploratory sensitivity only.

The three MOPT levels and three replications provide limited leverage. These estimates cannot replace the pooled SF-fixed-effects model.

### 10.3 Q1 secondary control

Apply the primary model to Q1 as a secondary control. Report effect estimates and intervals without adding Q1 to the Holm family. Interpret Q1 cautiously because it may use table metadata rather than a physical scan and because the cache-mode sensitivity is incomplete at SF50.

## 11. Query break-even specification

Break-even is the number of subsequent executions of a query required for observed post-maintenance time savings to offset the one-time native maintenance wall time.

For run `i` and query `q`:

`saving(i,q) = T_mean_pre(i,q) - T_mean_post(i,q)`

No individual negative or zero savings are removed. For each format/SF/MOPT/query cell:

`break_even = mean(maintenance_wall_time_ms) / mean(saving_ms)`

The value is reported only when the cell-level mean saving is positive. If it is zero or negative, report `NO_FINITE_BREAK_EVEN`. If its bootstrap interval includes zero, flag the ratio `UNSTABLE_SAVING_DENOMINATOR` and do not use it for a substantive threshold claim.

### 11.1 Primary maintenance boundary

- Delta: `operation_type=optimize` wall time.
- Iceberg: `operation_type=rewrite_data_files` wall time only.

This boundary compares native data-file rewrite work. It does not assert identical internal algorithms.

### 11.2 Iceberg sensitivity boundary

For Iceberg only, repeat with the sum of sequential `rewrite_data_files` and `rewrite_manifests` wall times from the same maintenance run. Delta has no separately invoked manifest rewrite, so no synthetic Delta equivalent is created.

Break-even is reported separately for Q2 and Q3. Any equal-mix workload result is exploratory and must be explicitly defined as one Q2 plus one Q3 execution per cycle. No universal workload mix is assumed.

## 12. Retained-metadata growth specification

The endpoint is the immediately pre-maintenance `metadata_total_size_mib_before` value linked to each canonical run. It represents **retained metadata footprint**, not active metadata, planning cost, or format-neutral metadata efficiency.

For each format separately, fit:

`log2(metadata_total_size_mib_before) = alpha + eta*log2(completed_ingestion_commits) + SF_FE + error`

`eta` is the retained-footprint elasticity with respect to completed commits within the tested design. SF is categorical with SF50 as reference. The primary 95% interval uses the same 10,000-draw stratified run-level BCa procedure and fallback rules.

Secondary analyses apply the same model to `metadata_file_count_before` and inspect linear, quadratic, and power residual patterns already specified in the exploratory work. Model comparison must report residual diagnostics and uncertainty; it must not promote a quadratic-compatible fit to a universal law.

Interpretation is limited to the tested retention, checkpoint, Spark, HDFS, Iceberg, and Delta settings. Commit count, SF, and MOPT are not fully independent, so `eta` is an empirical conditional association rather than a causal format constant.

## 13. Conditional MOPT threshold

The threshold analysis uses the previously established structural mean-file-size model:

`expected_file_size = delta_parquet + (MOPT * mean_row_bytes * compression_factor) / output_partitions`

For a declared target file size `F_target`, the conditional threshold is:

`MOPT_star(F_target) = output_partitions * (F_target - delta_parquet) / (mean_row_bytes * compression_factor)`

Rules:

- report `MOPT_star` as a conditional engineering threshold, not an optimum;
- use the documented 12 output partitions;
- estimate model parameters only from canonical runs;
- do not extrapolate when `F_target <= delta_parquet` or when the threshold lies outside the tested MOPT range without explicitly labeling it extrapolation;
- report a harmonized 512 MiB target for cross-format sensitivity;
- report native-target sensitivity separately: 512 MiB for Iceberg and 1 GiB for Delta;
- attach uncertainty obtained by resampling physical runs with the locked bootstrap design;
- do not combine file size, query time, metadata, and maintenance into a single utility score unless a utility function is declared in a later, separately labeled analysis.

## 14. Integrity gates before execution

The final-analysis program must stop before calculating results unless all gates pass:

1. exactly 72 unique canonical run IDs are loaded: 36 per format;
2. all IDs match the canonical manifest and no extra ID is present;
3. every included run has the 5-executor/80-core profile recorded in the manifest;
4. every run/query/phase has exactly three successful measured and three warmup rows;
5. all 216 format/run/query pre/post result-hash pairs agree;
6. B10 IDs exactly match the six canonical B10 IDs;
7. maintenance rows match the expected format-specific operation sequence;
8. CSV field widths and JSON fields pass the canonical parser checks;
9. the known n-1 ingestion alignment is retained and no terminal batch metric is imputed;
10. cache-mode labels are retained unchanged;
11. input file hashes match the audit record.

Any failure must be written to an integrity log and must stop the affected analysis. No silent correction is permitted.

## 15. Reporting requirements

For each primary model report:

- number of physical runs and observations;
- full model formula and reference levels;
- `beta_pre`, `beta_post`, `theta`, and `absolute_slope_reduction`;
- neutralization and its stability flag;
- interval type: `BCA`, `PERCENTILE_FALLBACK`, or `CI_NOT_ESTIMABLE`;
- raw and Holm-adjusted p-values for `theta`;
- cluster definition and bootstrap strata;
- residual and influential-run diagnostics;
- arithmetic-mean primary result and median sensitivity;
- all-runs primary result and warm-cache-only sensitivity;
- explicit distinction between confirmatory, secondary, and exploratory outputs.

All result tables must retain format, query, phase/model, SF scope, run count, method version, input-manifest hash, code revision, software environment, bootstrap seed, and execution timestamp.

## 16. Prohibited interpretations

The final analysis must not:

- treat 2,592 query executions as independent experiments;
- claim equal cache state across all runs;
- call retained metadata active metadata;
- interpret historical Iceberg or Delta post-write metrics as pure transaction-commit time;
- equate Iceberg manifest rewrite with an invented Delta operation;
- claim Delta modulo-10 behavior is isolated checkpoint cost;
- present `MOPT_star` as a universal optimum;
- reuse findings already published in DOI 10.1109/ACCESS.2026.3715629 as new contributions;
- describe this specification as a pre-experiment preregistration.

## 17. Change control

Any change after this lock requires a dated amendment containing:

1. the exact changed clause;
2. the reason;
3. whether any final result had already been viewed;
4. the expected scientific consequence;
5. new hashes for the specification and executable analysis code.

Results under different specifications must never be merged without an explicit method-version field.
