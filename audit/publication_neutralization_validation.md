# Validation of the Neutralization Results

Validation date: 2026-10-25  
Scope: historical Iceberg runtime version and Iceberg Q3 neutralization interval  
Method: read-only artifact validation; no new model fit and no benchmark execution

## Executive conclusion

1. The 36 canonical Iceberg runs used **Apache Iceberg 1.4.2**, not 1.6.1. The 1.6.1 references belong to code and configuration copies changed after the canonical Iceberg campaign.
2. The Iceberg Q3 point estimate `0.9998817568` and percentile fallback interval `[0.9448856103, 0.9991611999]` are arithmetically and procedurally correct. The point estimate should be displayed as **0.9999** or **99.99%**, not as 1.000/100.0% in narrative text.
3. No statistical result changes. A versioned reporting correction is recorded in `publication_neutralization_results_v1.0.1_correction.md`.

## 1. Historical Apache Iceberg version

### 1.1 Canonical run period

The canonical manifest shows that Iceberg ingestion ran from 2026-07-20 through 2026-09-03. The latest associated Iceberg maintenance and query executions finished on 2026-09-04.

The 36 canonical ingestion rows are linked to the B01-B12 run IDs in `publication_canonical_run_manifest.csv`. No Iceberg 1.11 test run is present in the canonical manifest.

### 1.2 Direct launch artifact

The preserved launch instructions in:

`Iceberg - Delta/scripts/consumers/help.txt`

were last modified on 2026-07-13, before the first canonical run, and contain:

```text
--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.4.2
```

The command launches `consumers/run_spark_consumer_iceberg.py`, the production path used for the benchmark rather than the notebook draft.

SHA-256:

`d9d425c0f7ebb47fc0236386569353f21cdc80fc8469e580dbe8f5324113d6fd`

### 1.3 Previously captured cluster evidence

The read-only historical investigation in:

`Iceberg - Delta/scripts/analysis/iceberg_ingestion_phase_comparability_report.md`

documents two independent cluster observations:

1. shell history contained repeated benchmark invocations with `iceberg-spark-runtime-3.5_2.12:1.4.2`;
2. a surviving June pilot driver log contained:

```text
engine-version=3.5.0
iceberg-version=Apache Iceberg 1.4.2
app-id=app-20260629035730-0014
```

The report also records that the Iceberg EventLogs for the 36 main runs were no longer retained: the canonical applications ended before the oldest retained EventLog of 2026-09-09.

Report SHA-256:

`f83f73acc821c3b50b1d8746cfc9a2a8af8bacac59039071ad7eff49eb27225d`

A fresh live SSH inspection was unavailable during this validation (`ssh` access was denied). Current cluster JAR contents would in any case be insufficient by themselves to prove a historical runtime version; the dated launch and run evidence is the relevant provenance.

### 1.4 Why 1.6.1 appears in current copies

The current configuration contains:

```text
org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1
```

However:

- `config/lakehouse_pipeline_config.json` was last modified on 2026-09-08;
- the preserved `run_spark_consumer_iceberg.py`, query script, and compaction script were created on 2026-09-05 and modified on 2026-09-08;
- all canonical Iceberg ingestion runs ended by 2026-09-03;
- all associated canonical Iceberg query and maintenance executions ended by 2026-09-04.

Therefore the current 1.6.1 configuration postdates the complete canonical Iceberg experiment and cannot identify its runtime.

The initial Git notebook draft from commit `7a814e437c17f1539879dc759bb1e20e3692e446` contains 1.5.2. It is also not execution evidence: it is explicitly a notebook variant, while the dated benchmark launch artifact invokes the Python consumer with an explicit 1.4.2 package.

### 1.5 Version verdict

| Component | Canonical version | Evidence status |
|---|---:|---|
| Spark | 3.5.0 | Confirmed in metrics and historical log evidence |
| Scala artifact line | 2.12 | Confirmed by package coordinate |
| Apache Iceberg | **1.4.2** | Confirmed by dated launch artifact, shell-history audit, and pilot driver log |
| Iceberg 1.6.1 | Not used by the 36 canonical runs | Later code/configuration state, dated after the campaign |

The statements that the canonical comparison used Iceberg 1.6.1 in `publication_prior_work_overlap.md` and in the v1.0 neutralization report are reporting errors. They do not affect the selected run IDs, measurements, regression inputs, or estimates.

The historical binary JAR itself was not archived with a SHA-256 value, and the main-run EventLogs and driver logs are no longer available. Version provenance is therefore confirmed at the Maven-coordinate and runtime-self-report level, not by a retained binary hash for every application. This limitation should be stated in the reproducibility section of the article.

## 2. Iceberg Q3 neutralization validation

### 2.1 Point estimate

The stored primary estimates are:

```text
beta_pre  = -0.6937232424440585
beta_post = -0.0000820280709361576
```

Applying the locked definition:

```text
neutralization
  = 1 - abs(beta_post) / abs(beta_pre)
  = 1 - 0.0000820280709361576 / 0.6937232424440585
  = 0.9998817567786151
```

The value in `primary_neutralization_results.csv` is therefore correct.

### 2.2 Bootstrap distribution

The stored `primary_bootstrap_estimates.csv` contains exactly 10,000 finite Iceberg Q3 neutralization estimates generated with seed `20261025` and the locked paired, SF/MOPT-stratified physical-run resampling.

| Distribution property | Value |
|---|---:|
| Finite draws | 10,000 / 10,000 |
| Minimum | 0.9123533963 |
| P2.5 | 0.9448856103 |
| Median | 0.9826995548 |
| Mean | 0.9798208318 |
| P97.5 | 0.9991611999 |
| P99 | 0.9996682209 |
| Maximum | 0.9999981067 |
| Draws below the point estimate | 9,963 |
| Draws above the point estimate | 37 |

The full-sample point estimate is at approximately the 99.63rd percentile of the bootstrap distribution. It is not outside the bootstrap support, but it is above the ordinary 97.5th percentile.

This asymmetry is expected for this derived ratio. The full sample places `beta_post` extremely close to zero. Cell-stratified resampling perturbs that near-cancellation; taking `abs(beta_post)` then shifts nearly all resampled neutralization values downward. The absolute-value transformation is non-smooth at zero.

### 2.3 BCa decision and locked fallback

For Iceberg Q3 neutralization, the diagnostics are:

```text
bias correction z0 = 2.6782860097
acceleration        = 0.0598065301
adjusted lower q    = 0.9996969307
adjusted upper q    = 1.0000000000
```

The locked v1.0 rule accepts BCa only when both adjusted quantiles lie strictly inside the empirical bootstrap range. The adjusted upper quantile equals 1.0, so BCa is invalid under the prespecified rule.

The prespecified fallback is the ordinary percentile interval when at least 9,500 finite draws exist. With 10,000 finite draws, the correct fallback is:

```text
[P2.5, P97.5] = [0.9448856103, 0.9991611999]
```

The fact that a percentile interval does not contain the original point estimate is possible for a highly biased/skewed bootstrap distribution. It is not a calculation error. It is, however, a reason to report the fallback method and the underlying slopes alongside the ratio.

The same BCa boundary issue also causes a percentile fallback for the Iceberg Q3 `absolute_slope_reduction`; all 10,000 estimates and all 36 jackknife estimates are finite.

### 2.4 Formatting verdict

The exact point estimate must be reported as:

- `0.9999` at four decimals; or
- `99.99%` as a percentage.

Rendering it as `1.000` or `100.0%` obscures that the point estimate is below one and creates an apparent contradiction with the percentile upper bound of `0.9992`.

Recommended publication form:

> Iceberg Q3: neutralization = 0.9999 (percentile-fallback 95% CI [0.9449, 0.9992]); beta_pre = -0.6937 and beta_post = -0.00008.

This wording does not claim exact complete neutralization.

## 3. Affected and unaffected artifacts

### Correction required

- `publication_final_neutralization_analysis_v1_0/publication_neutralization_results.md`: change the runtime label from Iceberg 1.6.1 to 1.4.2 and display Iceberg Q3 as 99.99%, not 100.0%.
- `publication_prior_work_overlap.md`: change the tested Iceberg version in the final scope statement from 1.6.1 to 1.4.2.

These existing files were not overwritten. The correction is recorded separately in `publication_neutralization_results_v1.0.1_correction.md`.

### No numerical correction required

- `primary_neutralization_results.csv`
- `primary_bootstrap_estimates.csv`
- `bootstrap_interval_diagnostics.csv`
- Holm-adjusted tests and all four primary decisions

Relevant SHA-256 values:

| Artifact | SHA-256 |
|---|---|
| `primary_neutralization_results.csv` | `0364c6507c4a2439d875f2acf82f2de905e0330e3c5b157fb4a162cad24bfa50` |
| `primary_bootstrap_estimates.csv` | `ee3a0ceb698b5865d3d67a629b85d25b4f6646c7f67340fe14b19f371d7dacb8` |
| `bootstrap_interval_diagnostics.csv` | `f47ab32411b4e96879f8c5e684ab7623c6ed9614bdfacad25fb34703356c9785` |
| analysis script | `33b39736d2f5fe81f3813f78c75159e797e4512c4b756b466ce3d0e07b6e593e` |

## 4. Release decision

**Validated with a versioned reporting correction.**

The neutralization calculations and statistical decisions remain valid. Journal-facing materials must identify the historical Iceberg runtime as 1.4.2 and must use non-rounded Iceberg Q3 wording that explicitly labels the percentile fallback.
